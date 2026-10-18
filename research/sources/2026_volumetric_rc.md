# Volumetric RC

| | |
|---|---|
| Date | 2024-09 to 2026-09 |
| Kind | Collected implementation findings; claims are unverified unless a public link backs them |
| Related | [2024_osborne_radiance_cascades_radiative_transfer.md](2024_osborne_radiance_cascades_radiative_transfer.md), [2025_osborne_dexrt_ray_acceleration.md](2025_osborne_dexrt_ray_acceleration.md), [2026_holographic_rc.md](2026_holographic_rc.md), [../topics/scene_representation_and_tracing.md](../topics/scene_representation_and_tracing.md) |

Volumetric RC treats the scene as emitting and absorbing media, so every interval carries radiance and transmittance instead of a binary hit. This note covers the integration order and merge rule, the storage needed, how to march on mip levels without darkening or leaking, and where volumetrics fit in 3D. Most of it was tested in 2D.

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
- **Thin walls:** 2×2×2 averaging halves a wall's opacity at each mip, since the wall fills about 4 of 8 sub-voxels, so light leaks. Directional opacity, six directions per voxel as in [GIVoxels](https://research.nvidia.com/sites/default/files/publications/GIVoxels-pg2011-authors.pdf), fixes it; dropping it clearly failed. Anisotropic density works as `T *= exp(−Δs·dot(|dir|, densityXYZ))`. One normal per cube cannot represent a plane: Sponza's floor became transparent at grazing angles. Leaks in media can be minimized, not solved.
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

- Volumetric ray-marching formalization with an acceleration structure: https://arxiv.org/abs/2511.08498
- SIGGRAPH Asia 2025 paper on transmittance: https://momentsingraphics.de/SiggraphAsia2025.html
- Path-traced 2D volumetrics reference: https://github.com/Yaazarai/PathTraced-Volumetrics
- 2D volumetric RC reference: https://tmpvar.com/poc/radiance-cascades/
- Volumetric RC Shadertoy: https://www.shadertoy.com/view/M3ycWt
- 2D RC with media in Go, absorption branch: https://github.com/s-macke/CoreCascade/tree/absorption
- Global illumination with forced ray termination at object backs: https://github.com/Yaazarai/Global-Irradiance
- Spectral imaging notes: https://jo.dreggn.org/home/2021_spectral_imaging.pdf
- Small float formats and their precision: https://bartwronski.com/2017/04/02/small-float-formats-r11g11b10f-precision/
