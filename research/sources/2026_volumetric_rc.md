# Volumetric RC

| | |
|---|---|
| Date | 2024-09 to 2026-09 |
| Kind | Collected implementation findings; claims are unverified unless a public link backs them |
| Related | [2024_osborne_radiance_cascades_radiative_transfer.md](2024_osborne_radiance_cascades_radiative_transfer.md), [2025_osborne_dexrt_ray_acceleration.md](2025_osborne_dexrt_ray_acceleration.md), [2026_holographic_rc.md](2026_holographic_rc.md), [../topics/scene_representation_and_tracing.md](../topics/scene_representation_and_tracing.md) |

Volumetric RC treats the scene as emitting and absorbing media, so every interval carries radiance and transmittance instead of a binary hit. This note covers the integration order and merge rule, the storage needed, how to march on mip levels without darkening or leaking, and where volumetrics fit in 3D. Most of it was tested in 2D.

## Contents

- [Integration and merging](#integration-and-merging)
- [Storage and color](#storage-and-color)
- [Marching on mips](#marching-on-mips)
- [Ray extensions with media](#ray-extensions-with-media)
- [Volumetrics in 3D](#volumetrics-in-3d)
- [Links](#links)

## Integration and merging

- **Per step,** marching near to far from the probe: `T_step = exp(−σ·Δs)`, `L += emission·(1 − T_step)·T_acc`, `T_acc *= T_step`, starting from `L = 0, T_acc = 1`. Adding emission without the `(1 − T_step)` factor is wrong. Radiance accumulates the same at any step size; only the transmittance term depends on it, and forgetting the step size made a cone tracer look worse. `exp2` is faster and looks the same.
- **Merge:** `L = L_near + T_near·L_far`, `T = T_near·T_far`. It needs only the near interval's transmittance and applies to every RC variant, opaque scenes included. Standard RC never reads the upper cascade's transmittance, because its radiance already reaches infinity; only HRC extensions need it stored, which doubles memory.
- **Optical depth is additive** and transmittance is `exp(−optical depth)`, so storing optical depth makes the merge exponent-free until the end. A single cascade is fully linear; merging is not, because occlusion multiplies.
- **Step length on a grid:** for line-slope tracing, `slope = delta/max(|dx|, |dy|)` and the step length is `length(slope)`, which makes integration exact at step 1.0. A DDA needs the true per-voxel segment length. With step length taken as the plain step instead, results gain an angular bias.
- **Exact pixels:** volumetric pixel squares can be integrated analytically ([amitabha voxel tracer](https://github.com/entropylost/amitabha/blob/main/src/trace/voxel.rs#L372-L425)). A DDA was recommended over fixed steps for media.
- **Endpoints:** rays must start and stop exactly where the next interval does; double-counted endpoints ring, and translucent ringing shows darker.
- **Translucent scenes:** every interval runs its full length. A ray that never reaches a light must still carry the volumetric color it accumulated, or a ring appears around the light.
- **Check:** an infinite medium with fixed absorption converges to fluence = emission/absorption; one build matched vanilla RC to ten digits.

## Storage and color

- 16-bit volume textures are the minimum; 8-bit transmittance fails. Per-channel transmittance needs three alphas (an aqua absorber leaves red); a single transmittance in alpha halves bandwidth at the cost of colored glass.
- Normalized textures cap absorption at 1, so scale it (values up to 1e4 were used). Combine overlapping absorbers by summing; taking the max broke lights.
- Read sRGB inputs as linear, merge in linear, and encode only at output. RGBA16F emission is already linear; converting it again dims it. Build mips in linear space.
- Format dominated one 4096² test: RGBA16F against RGBA8 cost 500 ms against 40 ms, not the `exp` calls.
- Whether emission requires opacity (source function = emission/absorption) is disputed; hot plasma emits while barely absorbing.
- Scattering can be approximated as extra absorption plus in-scattering from the previous frame's cascades with a phase function. Prisms need more wavelengths than RGB; 6 to 11 bins were planned or cited.

## Marching on mips

- Every volumetric RC implementation is a form of voxel cone tracing: cascade `N` marches mip `N` (or `N − 1` or `N − 2` for less blur) with step `2^mip`, which keeps steps per cascade constant. Marching above the storage resolution gains nothing.
- **Darkening:** using one mip for every cascade brightened results by under 10% at mip 1, 15 to 20% at mip 2 and about 30% at mip 3 with a single light in flatland, because transparency is nonlinear in density and depends on direction. A fractional level of `cascade + dist/rayLength` with step `2^mip·0.5` mitigated it in one playground, which still leaked ([playground](https://mdxish.com/jasonjmcghee/24f6577fd45962112a26dd09bb20bff7)).
- **Furnace check:** brightness must not change with mip level or step size; only blur may.
- **What to average** is disputed. One side averages absorption coefficients (optical density) and exponentiates, because density is linear per length. The other showed counterexamples: a 1%-coverage infinite-density dot makes a whole texel opaque under density averaging, while averaging transmittance gives the expected 99%; a 2×2 block with one opaque texel averages to opacity 0.25 but infinite density. Choosing by variance was suggested.
- **Thin walls:** 2×2×2 averaging halves a wall's opacity at each mip, since the wall fills about 4 of 8 sub-voxels, so light leaks. Directional opacity, six directions per voxel as in [GIVoxels](https://research.nvidia.com/sites/default/files/publications/GIVoxels-pg2011-authors.pdf) ([notes](2011_crassin_voxel_cone_tracing.md)), fixes it; dropping it clearly failed. Anisotropic density works as `T *= exp(−Δs·dot(|dir|, densityXYZ))`. One normal per cube cannot represent a plane: Sponza's floor became transparent at grazing angles. Leaks in media can be minimized, not solved.
- **Max-filtered mips** suit binary opacity and keep 1 px lights, but they do not conserve energy in media.
- **Two-level DDA** skips uniform blocks with no error and no leaks: 16×16 block flags, or an 8×8 bitmask per block as a u64, with analytic radiance and transmittance between changes ([multi-level DDA](https://www.shadertoy.com/view/lfyGRW)). Reading 4 to 6 values per thread is fine; going from 4 to 8 bytes per voxel was 100× slower in one pathological case.
- **Step size:** fixed steps fail in inhomogeneous media; steps near the mean free path, delta tracking, or a step chosen so radiance changes below a visible threshold are better. Large steps skip small lights and make point lights noisy. Variable step sizes flicker with moving lights, also in plain ray marching.
- **Early exit:** at transmittance about 0.01, or when the light the ray carries exceeds 99× what could remain. A `break` at low transmittance stalled D3D11 for seconds in one build; a loop condition plus a hard iteration cap that colors overruns is safer.

## Ray extensions with media

- Extensions on any layout: `lerp(near, merge(near, far), weight)`, with occlusion respected in the merge. Interpolating across a discrete field leaks light behind a ray that crosses at another angle.
- Interpolate transmittance like radiance (bilinear, or linear for one forward sample). Linear transmittance usually beat interpolating optical depth, with cases each way. HRC extensions interpolate transmittance linearly between two angles and must carry it up to merge down.
- HRC extensions were preferred for real-time volumetrics; vanilla RC can use them as cone-tracing mips.

## Volumetrics in 3D

- Full 3D RC was judged worth its cost mainly for volumetric lighting; screen probes and sparse surface probes cannot light a volume. One 3D volumetric RC took about half of a 60 fps frame.
- Sparse RC was said not to work for volumetrics. Ideas left untested: activate sparse probes along rays through fog, or set grid density by fog density.
- Writing each ray-march step into the probe of its own cascade gives accurate volumetrics without a depth measure.
- A screen-plane layout puts probes on a 2D plane with 3D intervals over the forward hemisphere for volumetric fog, interpolating along the camera ray.
- Volumetric clouds: RC can accelerate optical depth, but in-scattering needs full 3D. Baking clouds into the sky integral merged with the top cascade is cheaper.
- Almost-transparent media are almost sparse, which suggests lossy compression or quantizing to about 256 transfer functions.

## Links

- Linked as a volumetric ray-marching formalization with an acceleration structure: https://arxiv.org/abs/2511.08498. The paper is Osborne's sparse, mipmapped hierarchical DDA for DexRT's non-LTE solver ([2025_osborne_dexrt_ray_acceleration.md](2025_osborne_dexrt_ray_acceleration.md)).
- SIGGRAPH Asia 2025 paper on transmittance: https://momentsingraphics.de/SiggraphAsia2025.html. Peters's jackknife estimate `cos(σ̂)·exp(−μ̂)` from two optical-depth estimates removes the bias of `exp(−τ̂)` at no extra cost ([2025_peters_jackknife_transmittance.md](2025_peters_jackknife_transmittance.md)).
- Path-traced 2D volumetrics reference (Yaazarai, GameMaker, Unlicense): https://github.com/Yaazarai/PathTraced-Volumetrics. One fragment pass over a 256² world casts 256 evenly spaced rays per pixel with a fixed per-pixel blue-noise offset and steps one texel along the major axis. Each step's length (1 to √2 texels) scales the absorption, which the README says removed a bias along diagonals. Per channel, a step adds `E·(1 − T)·transmit` and multiplies `transmit` by `T = exp(−σ·stepLength)`; emission and absorption come from RGBA8 textures decoded with a 2.2 power, so colored emitters and colored absorbers can overlap. Emission takes the source-function form, so a texel with σ = 0 emits nothing, while CoreCascade's `(E/σ)(1 − e^(−σs))` treats `E` as emission per unit length and keeps it at σ = 0. The output is the ray average, a fluence, from 16.8 M rays per frame, with no scattering, sky or temporal filtering. The README's copy of the shader is older than the repository's (no jitter, `vec3` types), and it calls σ the mean free path, which is the inverse of σ.
- 2D volumetric RC reference: https://tmpvar.com/poc/radiance-cascades/
- Voxel RC Shadertoy by Mathis; "volumetric" refers to the voxel volume, and there are no participating media ([code notes](2023_rc_shadertoys_hrc_3d_and_other.md#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes)): https://www.shadertoy.com/view/M3ycWt
- 2D RC with media in Go, absorption branch: https://github.com/s-macke/CoreCascade/tree/absorption. Its absorption model, branch differences and bugs are in [2026_assorted_2d_rc_experiments.md](2026_assorted_2d_rc_experiments.md#corecascade).
- 2D GI with a fixed step budget (Yaazarai, GameMaker, 2023): https://github.com/Yaazarai/Global-Irradiance. Per pixel at 512², 32 rays (8 to 256) start from a rotating blue-noise angle and sphere-trace a jump-flood field for at most 32 steps; a ray that runs out returns black, which is the only forced termination in the code. The field combines, by a per-channel `max`, a field of the world and a field of the inverted occluders that measures distance inside visible occluders. A hit returns `max(base(p), base(p − dir/res))·0.95·r`, the second sample stepping back one texel to avoid self-hits. The factor `r` starts at the visibility of the ray's first texel and is multiplied by a texel's occlusion value whenever that value changes along the ray; the update stores the running product instead of the sampled value, so attenuation inside a partly occluding region likely compounds per step (found by reading). The pixel sum, including the pixel's own color, is divided by `N + 2` without explanation, and the composite draws the result twice additively. There is one bounce; a temporal blend, a 5×5 Gaussian and a bilateral denoiser are off by default. Coordinates and distances pack into two 8-bit channels as `x + y/255`, and the per-channel `max` of two packed values can exceed both (0.5035 and 0.6004 combine to 0.6035), overstating the distance near the boundary between the fields. The repository has no timings.
- Spectral imaging notes: https://jo.dreggn.org/home/2021_spectral_imaging.pdf (SIGGRAPH 2021 course on spectral rendering in film production; sample counts, RGB-to-spectrum methods and single-precision fixes are in [2021_spectral_imaging_in_production.md](2021_spectral_imaging_in_production.md))
- Small float formats and their precision: https://bartwronski.com/2017/04/02/small-float-formats-r11g11b10f-precision/. R11G11B10F has 11-bit R and G (5 exponent and 6 mantissa bits) and a 10-bit B (5 and 5), all unsigned; RGBA16F is 5 and 10 with a sign. All share the 5-bit exponent, so the range tops out near 65000. Near 1 the error is about 4× that of 8-bit linear and about 2× that of 8-bit sRGB, though better than sRGB below 0.125; the 10-bit channel cannot separate 252/255 to 254/255. Relative error is bounded and bands double in size at each exponent step. B's shorter mantissa shifts hues toward yellow or blue, visible as discoloured banding in a 0.5 to 0.6 gradient and worse after contrast. Scaling by a constant does not help, since it only moves the exponent. Storing `x³` instead gives asymptotically smaller error than sRGB-8 near 1 at a cost of 2 multiplies to encode and about 9 instructions per channel for `pow(x, 1/3)` to decode (about 4 for `sqrt` with a squared encoding); the maximum drops to about 40 for cubes and about 255 for squares, the smallest normal value becomes 0.03125, and the encoded values can no longer be filtered or blended without over-brightening. Against 10-bit sRGB, the float format is equal or slightly better only from 0 to 0.1. The format halves memory against RGBA16F and suits HDR colour buffers without blending or filtering, and it has no sign bit for YCoCg. The comments add that dithering by mantissa noise then truncation recovers at most one bit, and triangular dither overshoots at exponent boundaries by about one epsilon, `2^(E − mantissaBits)` for `2^E ≤ f < 2^(E+1)`. For RC, an R11G11B10F cascade holds radiance but cannot hold the transmittance alpha the merge needs, and repeated merges round each time (derived).
