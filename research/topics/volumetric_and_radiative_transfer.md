# Volumetric RC and radiative transfer

Volumetric RC treats the scene as emitting and absorbing media, so every interval carries radiance and transmittance instead of a binary hit. This topic covers integration and merging in media, storage, marching on mip levels, DexRT (the astrophysics solver and its acceleration structure), extensions with media, volumetrics in 3D, RC for CT volumes, transmittance estimation, radiance caching in media, and spectral transport. The interval definition, the merge operator in optical-depth form and Osborne's penumbra criterion are in [core theory](core_theory.md#radiance-intervals); HRC's use of stored transmittance is in [holographic RC](holographic_rc.md#building-rays-the-acceleration-structure); voxel cone tracing as a GI method is in [related probe GI](related_probe_gi.md).

Statements marked "derived" were computed with a script from the sources' formulas; "inference" marks conclusions drawn here; "read from the code" marks behaviour found by reading, not by running. Community findings come from the [volumetric notes](../sources/2026_volumetric_rc.md) and are unverified unless a public link backs them; most were tested in 2D.

## RC as a radiative transfer solver

Osborne and Sannikov applied RC to 2D solar-atmosphere radiative transfer in the GPU code DexRT, where it is a formal solver inside a non-LTE iteration: each iteration computes the radiation field from level populations, and the populations are updated from it until they converge ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md)). Their restatement of the penumbra criterion, the interval as `[I(b→a), τ(b→a)]`, the branching factor `α`, the ringing analysis and the bilinear fix are in [core theory](core_theory.md#the-penumbra-condition), [cascade layout](cascade_layout_and_merging.md) and [artifacts and fixes](artifacts_and_fixes.md#the-bilinear-fix). Dell'Ova's literature review notes that their computation times are several orders of magnitude above real-time rendering costs, that they say the logic generalizes to 3D, and that they leave some inconsistencies and optimizations for later work ([Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md)).

Their solver computes only what it needs: it flags the cascade 0 probes of interest, flags their bilinear parents up the hierarchy and computes intervals only for flagged probes. Each interval is independent, so the work is embarrassingly parallel, with threads grouped so a warp shares a branch and reads contiguous memory; the GPU solve ran 80× faster than the CPU solve at 2× the power, the about 40× performance per watt that Osborne's DexRT slides quote (derived).

The RC paper points out that world-space cascades can be sampled anywhere in space, which participating media and atmospheric scattering need, while screen-space cascades can be sampled only on the G-buffer surface ([paper](../sources/2023_sannikov_radiance_cascades_paper.md)). That is the reason volumetrics belong to the world-space family ([3D world space](3d_world_space.md)).

## Integration and merging

- **Per step**, marching near to far from the probe: `T_step = exp(−σ·Δs)`, `L += emission·(1 − T_step)·T_acc`, `T_acc *= T_step`, starting from `L = 0, T_acc = 1`. Adding emission without the `(1 − T_step)` factor is wrong. Radiance accumulates the same at any step size; only the transmittance term depends on it, and forgetting the step size made a cone tracer look worse. `exp2` is faster and looks the same.
- **Merge:** `L = L_near + T_near·L_far`, `T = T_near·T_far`. It needs only the near interval's transmittance and applies to every RC variant, opaque scenes included. Standard RC never reads the upper cascade's transmittance, because its radiance already reaches infinity; only HRC extensions need it stored, which doubles memory.
- **Optical depth is additive** and transmittance is `exp(−optical depth)`, so storing optical depth makes the merge exponent-free until the end. A single cascade is fully linear; merging is not, because occlusion multiplies.
- **Step length on a grid.** For line-slope tracing, `slope = delta/max(|dx|, |dy|)` and the step length is `length(slope)`, which makes integration exact at step 1.0. A DDA needs the true per-voxel segment length. Taking the step length as the plain step instead gives results an angular bias. Fixed-step marchers that apply one opacity per sample instead of per length attenuate differently per cascade, which [2D implementations](2d_implementations.md#scene-representations) lists by code; the opacity correction for a changed step is in the [glossary](supporting_techniques.md#light-transport-and-solver-math).
- **Exact pixels.** Volumetric pixel squares can be integrated analytically (amitabha's voxel tracer, `src/trace/voxel.rs` lines 372 to 425). A DDA was recommended over fixed steps for media.
- **Endpoints.** Rays must start and stop exactly where the next interval does; double-counted endpoints ring, and translucent ringing shows darker.
- **Translucent scenes.** Every interval runs its full length. A ray that never reaches a light must still carry the volumetric colour it accumulated, or a ring appears around the light.
- **Check.** An infinite medium with fixed absorption converges to fluence = emission/absorption; one build matched vanilla RC to ten digits.

**Emission conventions.** The codes split into two forms, and the community dispute over whether emission requires opacity ("hot plasma emits while barely absorbing") is the choice between them:

| Form | Radiance a segment of length `s` adds | At `σ = 0` | Codes |
|---|---|---|---|
| Source function (emission is the radiance of an opaque emitter) | `E·(1 − e^(−σs))` | nothing | the per-step rule above, PathTraced-Volumetrics, Volumetric-HRC (`R = (1 − T)·E`), jason.today/hrc, folkjs, hbattal, amitabha, nihil ([implementations](holographic_rc_implementations.md)) |
| Emission per unit length | `(η/σ)·(1 − e^(−σs))` | `η·s` | DexRT (`I·e^(−τ) + (η/χ)(1 − e^(−τ))`), CoreCascade (`(E/σ)(1 − e^(−σs))`), TypeGPU's holographic runner (`emission·(1 − T)/σ`, or `emission·length` below `σ = 1e−5`) |

The second form is the radiative transfer equation's own, with source function `η/σ`; it reduces to the first when `η = E·σ`, which is what TypeGPU's drawing example does by setting emission `rgb·16` and extinction `alpha·16`, so an opaque painted pixel shows radiance equal to its colour (derived). A renderer that wants both glowing gas and opaque emitters needs the per-length form; one that only paints opaque emitters can use either (inference).

**Reference: PathTraced-Volumetrics** (Yaazarai, GameMaker, Unlicense). One fragment pass over a 256² world casts 256 evenly spaced rays per pixel with a fixed per-pixel blue-noise offset and steps one texel along the major axis. Each step's length (1 to √2 texels) scales the absorption, which the README says removed a bias along diagonals. Per channel, a step adds `E·(1 − T)·transmit` and multiplies `transmit` by `T = exp(−σ·stepLength)`; emission and absorption come from RGBA8 textures decoded with a 2.2 power, so coloured emitters and coloured absorbers can overlap. Emission takes the source-function form, so a texel with `σ = 0` emits nothing. The output is the ray average, a fluence, from 16.8 M rays per frame, with no scattering, sky or temporal filtering. The README's copy of the shader is older than the repository's (no jitter, `vec3` types), and it calls `σ` the mean free path, which is the inverse of `σ` ([volumetric notes](../sources/2026_volumetric_rc.md#links)).

**Reference: Global-Irradiance** (Yaazarai, GameMaker, 2023), 2D GI with a fixed step budget and partly occluding texels. Per pixel at 512², 32 rays (8 to 256) start from a rotating blue-noise angle and sphere-trace a jump-flood field for at most 32 steps; a ray that runs out returns black, the only forced termination in the code. The field combines, by a per-channel `max`, a field of the world and a field of the inverted occluders that measures distance inside visible occluders. A hit returns `max(base(p), base(p − dir/res))·0.95·r`, the second sample stepping back one texel to avoid self-hits. The factor `r` starts at the visibility of the ray's first texel and is multiplied by a texel's occlusion value whenever that value changes along the ray; the update stores the running product instead of the sampled value, so attenuation inside a partly occluding region likely compounds per step (read from the code). The pixel sum, including the pixel's own colour, is divided by `N + 2` without explanation, and the composite draws the result twice additively. There is one bounce; a temporal blend, a 5×5 Gaussian and a bilateral denoiser are off by default. Coordinates and distances pack into two 8-bit channels as `x + y/255`, and the per-channel `max` of two packed values can exceed both (0.5035 and 0.6004 combine to 0.6035), overstating the distance near the boundary between the fields. There are no timings.

Other 2D media references are described with their code: tmpvar's playground ([2D articles and demos](2d_articles_and_demos.md#tmpvars-playground)), CoreCascade's absorption branch ([2D implementations](2d_implementations.md#cpu-references-and-research-harnesses)), and codyjbennett's wfyyDz and its JSFiddle twin ([2D Shadertoys](2d_shadertoys.md)). Mathis's M3ycWt is "volumetric" only in the sense of a voxel volume and has no participating media ([3D world-space implementations](3d_world_space_implementations.md#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes)).

## Storage and colour

- 16-bit volume textures are the minimum; 8-bit transmittance fails. Per-channel transmittance needs three alphas (an aqua absorber leaves red); a single transmittance in alpha halves bandwidth at the cost of coloured glass.
- Normalized textures cap absorption at 1, so scale it (values up to 1e4 were used). Combine overlapping absorbers by summing; taking the max broke lights.
- Read sRGB inputs as linear, merge in linear, and encode only at output. RGBA16F emission is already linear; converting it again dims it. Build mips in linear space.
- Format dominated one 4096² test: RGBA16F against RGBA8 cost 500 ms against 40 ms, not the `exp` calls.
- In the CT repository, 8-bit transmittance rounds very small values to exactly 0, which the march treats as opaque ([below](#rc-for-ct-volumes-repository)).

**Small floats** (Bart Wronski, 2017). R11G11B10F has 11-bit R and G (5 exponent and 6 mantissa bits) and a 10-bit B (5 and 5), all unsigned; RGBA16F is 5 and 10 with a sign. All share the 5-bit exponent, so the range tops out near 65000. Near 1 the error is about 4× that of 8-bit linear and about 2× that of 8-bit sRGB, though better than sRGB below 0.125; the 10-bit channel cannot separate 252/255 to 254/255. Relative error is bounded and bands double in size at each exponent step. B's shorter mantissa shifts hues toward yellow or blue, visible as discoloured banding in a 0.5 to 0.6 gradient and worse after contrast. Scaling by a constant does not help, since it only moves the exponent. Storing `x³` instead gives asymptotically smaller error than sRGB-8 near 1 at a cost of 2 multiplies to encode and about 9 instructions per channel for `pow(x, 1/3)` to decode (about 4 for `sqrt` with a squared encoding); the maximum drops to about 40 for cubes and about 255 for squares, the smallest normal value becomes 0.03125, and the encoded values can no longer be filtered or blended without over-brightening. Against 10-bit sRGB, the float format is equal or slightly better only from 0 to 0.1. It halves memory against RGBA16F and suits HDR colour buffers without blending or filtering, and it has no sign bit for YCoCg. The comments add that dithering by mantissa noise then truncation recovers at most one bit, and triangular dither overshoots at exponent boundaries by about one epsilon, `2^(E − mantissaBits)` for `2^E ≤ f < 2^(E+1)` ([volumetric notes](../sources/2026_volumetric_rc.md#links)). The format's layout is in the [glossary](supporting_techniques.md#formats-and-colour) and its drift under repeated writes in [artifacts and fixes](artifacts_and_fixes.md#banding-and-precision).

An R11G11B10F cascade holds radiance but cannot hold the transmittance alpha the merge needs, and repeated merges round each time; 11-bit opacity also tops out at 0.996 below 1 ([holographic RC](holographic_rc.md#artifacts-and-fixes)), so transmittance needs at least a 16-bit channel of its own (derived).

## Marching on mips

Every volumetric RC implementation is a form of voxel cone tracing: cascade `N` marches mip `N` (or `N − 1` or `N − 2` for less blur) with step `2^mip`, which keeps steps per cascade constant. Marching above the storage resolution gains nothing.

- **Brightness drift.** Using one mip for every cascade brightened results by under 10% at mip 1, 15 to 20% at mip 2 and about 30% at mip 3 with a single light in flatland, because transparency is nonlinear in density and depends on direction. A fractional level of `cascade + dist/rayLength` with step `2^mip·0.5` mitigated it in one playground (a jason.today mdxish page, gist 24f6577fd45962112a26dd09bb20bff7), which still leaked.
- **Furnace check.** Brightness must not change with mip level or step size; only blur may.
- **What to average** is disputed. One side averages absorption coefficients (optical density) and exponentiates, because density is linear per length. The other showed counterexamples: a 1%-coverage infinite-density dot makes a whole texel opaque under density averaging, while averaging transmittance gives the expected 99%; a 2×2 block with one opaque texel averages to opacity 0.25 but infinite density. Choosing by variance was suggested.
- **Thin walls.** 2×2×2 averaging halves a wall's opacity at each mip, since the wall fills about 4 of 8 sub-voxels, so light leaks. Directional opacity, six directions per voxel as in GIVoxels (Crassin et al. 2011), fixes it; dropping it clearly failed. Anisotropic density works as `T *= exp(−Δs·dot(|dir|, densityXYZ))`. One normal per cube cannot represent a plane: Sponza's floor became transparent at grazing angles. Leaks in media can be minimized, not solved.
- **Max-filtered mips** suit binary opacity and keep 1 px lights, but they do not conserve energy in media.
- **Two-level DDA** skips uniform blocks with no error and no leaks: 16×16 block flags, or an 8×8 bitmask per block as a u64, with analytic radiance and transmittance between changes (Shadertoy lfyGRW, "multi-level DDA"). Reading 4 to 6 values per thread is fine; going from 4 to 8 bytes per voxel was 100× slower in one pathological case. The traversal is described in [scene representation and tracing](scene_representation_and_tracing.md).
- **Step size.** Fixed steps fail in inhomogeneous media; steps near the mean free path, delta tracking, or a step chosen so radiance changes below a visible threshold are better. Large steps skip small lights and make point lights noisy. Variable step sizes flicker with moving lights, also in plain ray marching.
- **Early exit** at transmittance about 0.01, or when the light the ray carries exceeds 99× what could remain. A `break` at low transmittance stalled D3D11 for seconds in one build; a loop condition plus a hard iteration cap that colours overruns is safer.

**Why both averaging rules fail (derived).** Optical depths add along a ray and transmittances average across a ray's footprint. A mip voxel mixes both, so the right average depends on how the structure lies relative to the ray:

| 2×2 block, one column a wall of optical depth `W` per cell | True transmittance | Density averaged | Opacity averaged |
|---|---|---|---|
| Ray crossing the wall, `W = 20` | 0.000 | 0.000 | 0.500 |
| Ray running along the wall, `W = 20` | 0.500 | 0.000 | 0.500 |
| Ray crossing, `W = 1` | 0.368 | 0.368 | 0.684 |
| Ray along, `W = 1` | 0.568 | 0.368 | 0.684 |

Density averaging is exact across slabs and over-occludes partial coverage (the 1% dot); opacity averaging is exact for coverage and leaks through slabs (the thin wall). Six directional opacities store the answer per direction, which is why they fix thin walls, and a variance test detects when the two rules disagree (inference from the table).

For a footprint where one child of `n` has optical depth `τ` and the rest are empty, the density average underestimates the true footprint transmittance by:

| `τ` of the dense child | 2 children | 4 children (2D) | 8 children (3D) |
|---|---|---|---|
| 0.1 | 0.12% | 0.09% | 0.05% |
| 0.25 | 0.78% | 0.56% | 0.32% |
| 0.5 | 3.05% | 2.12% | 1.20% |
| 1 | 11.3% | 7.5% | 4.2% |
| 2 | 35.2% | 22.6% | 12.7% |
| 4 | 73.4% | 51.3% | 30.9% |

DexRT's variance-limited mipmapping checks a block only when some child exceeds optical depth 0.25 per step ([below](#dexrt)); below that, density averaging is within 0.6% in 2D and 0.3% in 3D of the coverage answer, which is the margin that makes its threshold safe (derived). The same convexity of `exp` is the bias Peters removes for noisy optical-depth estimates ([below](#transmittance-estimation-peters-2025)): mips are the deterministic case of Jensen's inequality (inference).

## DexRT

Osborne's sparse, mipmapped tracing for DexRT ("A Simple Ray Acceleration Structure for Non-LTE Radiative Transfer", arXiv 2511.08498, 2025-11, published in RASTI, doi 10.1093/rasti/rzaf055; code C++20, Apache 2.0) speeds up interval tracing about 8× by letting each cascade march a coarser mip of the scene and by skipping empty blocks with a hierarchical DDA ([DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md)). The domain is solar plasma, but the scheme carries over to a voxel scene for graphics.

**Scene representation.**

- The volume is split into blocks (16² in 2D, 8³ in 3D). Each block has one 3-bit state: empty, or the highest mip level it may be sampled at. 21 states pack into one 64-bit word, so a 512² model needs 392 bytes of block map. A 512³ model is said to need 669 words (5.4 kB), with no block size or packing given for it. At the typical 8³ blocks it has 262,144 blocks, which need 12,484 words, and at 16³ it has 32,768, which need 1,561; 669 words hold 14,049 blocks, so the 3D figure fits neither size (derived; the 2D figure checks out).
- Each mip averages 2×2 (or 2×2×2) children of the level below. Mip storage is allocated only for active blocks, in Morton order, costing 1.33× the base level in 2D and 1.14× in 3D, the geometric sums `Σ 4^−k` and `Σ 8^−k` (derived).
- **Variance-limited mipmapping.** A parent is accepted only if its children agree: the index of dispersion `|Var/Mean|` of `ln(χ·Δs)` and of `ln(η·Δs)` over the children must stay below 1.0, checked only when some child has optical depth `χ·Δs > 0.25` (thin regions always average). A block's level rises only while every parent in it passes, so sharp structure keeps full resolution and smooth or thin regions coarsen.
- **Per-cascade mip cap.** Cascade `n` may sample at most mip `[0, 0, 1, 2, 3, 4][n]`. Near intervals keep full resolution; far intervals read coarse proxies, which is where most of the run time goes. From cascade 1 up this is the community's "mip `N − 1`" choice, bounded per block by the variance test (inference).

**Tracing.**

- Hierarchical DDA (Museth 2014, the VDB traversal): step through cells of size `2^level` of the current block, jump whole blocks when empty, and recompute the cell and next-plane distances when the level changes. Each segment gets its exact path length, so there is no fixed-step oversampling.
- Per segment with constant emission and opacity: `I = I·exp(−τ) + (η/χ)·(1 − exp(−τ))`, with `τ = χ·dt` and `1 − exp(−τ)` computed with `expm1` for precision.
- Robustness: entering an empty region pushes `t` forward by 0.01 cell; the next-plane `t` must always exceed the current `t`; a level change adds 1e−3. Negative coordinates use an arithmetic shift, not division, so `−1 >> 4 = −1`.
- Intervals are marched from the far end toward the probe, the order that gives up early exit, which the formal solution's per-segment update `I·exp(−τ) + S·(1 − exp(−τ))` needs (inference).

**Cascades, 2D defaults.**

- Cascade 0: one probe per cell, interval 1.5 cells, 4 azimuth directions times 4 inclinations. Branching factor 2: probes halve per axis, directions ×4, interval end ×4 (`[0, 1.5], [1.5, 6], [6, 24], …`), so every cascade has the same memory. Six cascades; the top one is extended to 2×10⁴ cells so it reaches the boundary. The 2024 paper's run used 8 inclinations ([cascade layout](cascade_layout_and_merging.md#2d-parameters-across-implementations)).
- **Ping-pong storage:** only two cascade buffers, each sized for the largest cascade, alternate between read and write during the top-down merge.
- **Direction by direction:** cascade 0's 4 directions are processed as 4 separate passes through all cascades, each pass storing only the upper directions that descend from one cascade 0 direction, so storage drops to a quarter. It cannot be combined with the parallax fixes, which read neighbouring directions.
- Upper probe `k` sits at `(2k + 1)·2^n` and lower probe `c` at `(c + 0.5)·2^n`, so bilinear fractions are 0.25 or 0.75; the first row and column clamp to weight 1.

**Merge variants in the code.**

| Variant | What it does | Note in the code |
|---|---|---|
| Vanilla (default) | trace once; upper value is the bilinear mix of 4 upper probes times the mean of 4 upper directions | rings around small, bright, optically thick sources |
| BilinearFix | for each of the 4 upper probes, re-trace from this ray's start to that probe's interval start (taken along its middle child direction), merge with that probe only, then weight bilinearly | "near-exact" at 4× the rays |
| ParallaxFix | interpolate the upper direction toward the ray's end point | applied only above cascade 1, since the lowest cascades have their own artifacts; adding a commented-out alternative direction caused ringing |
| ParallaxFixInner | a second pass that needs stored optical depth per texel | doubles cascade memory |

**3D settings.** Blocks of 8³, a cascade 0 interval of 6 cells, 12 azimuth rays from a HEALPix order 1 sphere with ×4 per cascade, and interval ends that double per cascade (`6·2^n`), not quadruple. The 3D merge uses 8 trilinear corners and 4 upper rays; a trilinear fix exists but is turned off.

**Results.** On a 512×768 prominence model with 880 wavelengths (RTX 4070), sparsity plus mips cut one iteration from 95 s to 11.8 s (8×), with the 99.9th-percentile error under 0.5% and a peak of about 12% in a few cells. Mipmapping alone gave 3.5×; sparsity alone gave 1.5× on this half-empty model.

**Paper details.**

- Setup: DexRT v0.5.0 on an RTX 4070 with an i7-13700, CUDA 12.4 and NVIDIA HPC 24.5. The model is 2D, 512 × 768 cells of 7.5 km, with 880 wavelengths from 5+1-level H, 5+1-level Ca II and Ca III atoms. Cascade 0 has 16 rays, 4 azimuths times a 4-point Gauss-Radau rule in inclination. Iteration stops when the largest relative change of level populations drops below 10⁻³ (MALI with a diagonal operator). Blocks hotter than 250 kK are skipped, about half the model.
- Anisotropic data (sec. 3): a velocity grid keeps mip chains at a set of velocities per voxel, interpolated by the ray's projected velocity over 21 directional bins per quadrant (84 in all). The "Core and Voigt" variant splits emission and opacity into direction-independent mipmapped parts times a line profile evaluated per direction, with the Voigt profile from the HUM1WEI24 approximation (Humlíček region I plus a 24-term Weideman series), four mip chains per line and at most four overlapping lines.
- Table 3, time per iteration and error against the dense classic solver (column order rebuilt from the text extraction):

| Variant | s / iteration | Iterations | Max error % | 99.9th percentile % |
|---|---|---|---|---|
| DenseClassic (reference) | 95.0 | 86 | 0.0 | 0.0 |
| DenseCav | 70.0 | 97 | 12.39 | 0.295 |
| DenseCavMips | 20.2 | 97 | 12.35 | 0.445 |
| SparseClassic | 62.9 | 87 | 1.20 | 0.031 |
| SparseCav | 30.7 | 91 | 12.58 | 0.294 |
| SparseVelInterp | 22.1 | 82 | 12.38 | 0.495 |
| SparseCavMips | 11.8 | 101 | 12.31 | 0.445 |
| SparseVelInterpMips | 10.0 | 91 | 12.36 | 0.889 |

- The abstract's "under 0.5%" refers to Core and Voigt with mips; velocity interpolation with mips is about 15% faster per iteration but nearly doubles the 99.9th-percentile error (0.889%). The peak errors near 12% sit in a vanishing fraction of voxels.
- For graphics RC, the paper suggests running the lower cascades locally per patch and giving the upper cascades a compacted mip structure that stores only the highest permitted level per block (sec. 6). It cites Crassin et al. 2011 and Han et al. 2007 as prefiltering for anisotropic data.
- Data: Zenodo 16759894.

**The 2024 paper's build.** The paper ran DexRT v0.2.0 (https://github.com/Goobley/DexRT at a9e4bdd); in that run cascade 5 took 63.6% of the time ([core theory](core_theory.md#rays-traced-and-rays-built), [notes](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#dexrt-v020-and-the-data-archive)).

- **Constants** (`source/Config.hpp`): `PROBE0_LENGTH` 1.5 (a cascade 0 interval of 1.5 voxels), `PROBE0_NUM_RAYS` 4, `PROBE0_SPACING` 1.0, `CASCADE_BRANCHING_FACTOR` 2 (the paper's `α`, also the shift the code uses to reach the 4 child directions), `MAX_CASCADE` 5 (six cascades), `LAST_CASCADE_TO_INFTY` with `LAST_CASCADE_MAX_DIST` 10⁶ so top-cascade rays leave the domain, `PREAVERAGE` off and `DIR_BY_DIR` on, `RC_CONFIG` `Vanilla`, `PARALLAX_MERGE_ABOVE_CASCADE` 1 with an inner parallax threshold of −1, ping-pong buffers, `NUM_INCL` 8 (4, 8 or 16 allowed by a `static_assert`), `WAVE_BATCH = 32/NUM_INCL`, and compile-time `MODEL_X` and `MODEL_Y` of 1024 with `NUM_DIM` 2, where the paper's run is 3072 × 2048.
- **Merges:** `RcConfiguration { Vanilla, ParallaxFix, ParallaxFixInner, BilinearFix }`. BilinearFix (`march_and_merge_bilinear_fix`) re-anchors the lower ray to end at each of the 4 upper probes' interval start, marches it with a 2D DDA, averages that probe's `2^α` child rays (weight `1/num_rays_per_ray`), merges the two intervals and accumulates intensity and optical depth with the bilinear weights. The paper's figure scripts set `BILINEAR_MERGE = True` and title the disc test "Radiance Cascades (Bilinear Fix)", so its ringing comparison was drawn with the fix while the production default is Vanilla, which the paper's data did not need.
- **Into J** (`MergeToJ.hpp`): cascade 0 values are weighted by `1/c0_dirs_to_average` in azimuth and by the inclination weight `wmuy(θ)`. The 8-point inclination table puts a node at 0 with weight 1/64 (1/16 in the 4-point table), the `1/n²` endpoint weight of [Gauss–Radau](supporting_techniques.md#numerics-and-statistics) on [0, 1], consistent with the paper's "Gauss–Radau quadrature with eight rays", though the code names no rule; `gauss_lobatto.py` generates a 4-point Lobatto set for azimuthal rays.
- **Archive** (Zenodo 13375365, inputs and results only, 2024-08-26, netCDF 4 with YAML configs): a Jenkins and Keppens 2021 levitation-condensation prominence snapshot `jk20200550.dat` (509.5 MB); DexRT outputs `_dex.nc` (201 MB), `_ray.nc` (8.9 GB), `_ray_lyb_cfn.nc` (10.2 GB) and `_synth.nc` (18.5 GB); Lightweaver comparisons (18.9 MB each) and an `_hea2015_proxy.nc` (20.6 MB); plotting scripts (66.7 MB), rendered videos (11.9 MB) and an H I 102.57 nm video (2.4 MB); and the atom models `H_4.yaml`, `H_6.yaml` and `test_CaII.yaml` with `preprocess_2d_cube_dex.py`.
- **Run config** (`jk20200550.yaml`): non-LTE with active Ca II and 6-level H atoms, a Promweaver boundary, charge and pressure conservation, 2 initial lambda iterations, up to 1000 iterations to a population tolerance of 0.001, sparse calculation, J stored on the CPU, threshold temperature 250,000 and `alo: false`. The synthesis run uses 91 viewing angles and 3765 wavelengths with a rotated bounding box; the Lyman β contribution-function run uses one line of sight and 101 wavelengths over 102.49 to 102.6 nm.

Mips cut the time 3.5× where the top cascades hold most of it, which fits the 63.6% share: if mips leave the near cascades alone and speed the far ones up by a factor `k`, the total falls by `1/(0.15 + 0.85/k)` with about 85% of the time in cascades 4 and 5, so 3.5× needs `k` near 6 (derived from the 2024 run's shares, 63.6% and 21.4%, which come from a different model). Sparsity's 1.5× on a half-empty model is below the 2× an ideal skip would give, the overhead of the block map and the boundary blocks (inference).

## Ray extensions with media

- Extensions on any layout: `lerp(near, merge(near, far), weight)`, with occlusion respected in the merge. Interpolating across a discrete field leaks light behind a ray that crosses at another angle.
- Interpolate transmittance like radiance (bilinear, or linear for one forward sample). Linear transmittance usually beat interpolating optical depth, with cases each way. HRC extensions interpolate transmittance linearly between two angles and must carry it up to merge down.
- HRC extensions were preferred for real-time volumetrics; vanilla RC can use them as cone-tracing mips ([holographic RC](holographic_rc.md#building-rays-the-acceleration-structure)).

## Volumetrics in 3D

- Full 3D RC was judged worth its cost mainly for volumetric lighting; screen probes and sparse surface probes cannot light a volume. One 3D volumetric RC took about half of a 60 fps frame.
- Sparse RC was said not to work for volumetrics. Ideas left untested: activate sparse probes along rays through fog, or set grid density by fog density. In one sparse build, spawning all trilinear neighbours cost about 30% more probes in a volumetric scene, against 2 to 4× on flat surfaces ([sparse and 3D RC](../sources/2026_sparse_and_3d_rc.md)).
- Writing each ray-march step into the probe of its own cascade gives accurate volumetrics without a depth measure.
- A screen-plane layout puts probes on a 2D plane with 3D intervals over the forward hemisphere for volumetric fog, interpolating along the camera ray.
- Volumetric clouds: RC can accelerate optical depth, but in-scattering needs full 3D. Baking clouds into the sky integral merged with the top cascade is cheaper.
- Almost-transparent media are almost sparse, which suggests lossy compression or quantizing to about 256 transfer functions.
- Scattering can be approximated as extra absorption plus in-scattering from the previous frame's cascades with a phase function. Prisms need more wavelengths than RGB; 6 to 11 bins were planned or cited ([spectral](#spectral-transport)).
- The 3D HRC memory model and its volumetric case are in [holographic RC](holographic_rc.md#3d); a 32³ local HRC volume fits in about 0.1 GB.

## RC for medical volumes (Rulkens)

Rulkens's TU/e thesis "Radiance Cascades for Medical Volume Data" (report dated 2025-11-07) builds a dense world-space 3D RC over CT scans ([Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md)). Its direction mappers, merge formula and parameters are in [cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d).

**Goal and background.** The one stated goal is physically based single-bounce GI for CT scans in real time, with no limit on the number or shape of lights and no convergence (p. 5). The abstract says adding lights does not change performance (p. 3); the results say it changes little (p. 26), and no light-count sweep is measured. Earlier real-time volume lighting is limited: deep shadow maps and shadow volume propagation take one light; extinction-based shading and SH lighting slow down per light (p. 8). Monte Carlo renderers (Kroes et al.'s Exposure Renderer, Rezk-Salama) converge over time; Jönsson et al.'s historygrams and photon mapping allow editable transfer functions at high memory cost; Yang et al.'s screen-space occlusion handles only lights in front of the image plane (p. 6). Game irradiance volumes are cited for light leaks and a probe-count trade-off (p. 5). RC is explained from Sannikov's paper alone (p. 9-10).

**Method.** The light field is computed once per scene change and read every frame (Fig. 4.2, p. 12):

| Stage | Runs |
|---|---|
| Combine the CT volume with an RGB light volume into one transmittance volume and one emitted-colour volume | on scene change |
| Ray-march the combined volume for every probe and cascade | on scene change |
| Merge the cascades into a radiance volume | on scene change |
| Ray-march the CT and light volumes from the camera, reading the radiance volume | every frame |
| Gamma correction and display | every frame |

- The field is independent of the camera and is recomputed only when the transfer function, the volume or the lights change (p. 11-12, 32). Nothing is accumulated over frames, and whether one recomputation fits in one frame is not stated.
- Transparent voxels emit nothing, so colour is read only where transmittance is near 0; the combined volume exists to cut texture fetches, the largest cost (p. 12).
- Cascade 0 probes are spread evenly over the volume, and higher cascades sit between the probes below (p. 11). Probe and light volumes span a unit cube that the CT is scaled into (p. 25).

**Shading (sec. 6).**

- Surfaces sample the field at `s = p + o·n` to keep probes behind the surface out of the sum, with the normal from finite differences (p. 22). The thesis gives no value for `o`; the code uses 1.7 probe spacings.
- Lambertian shading: `L_r ≈ (π·ρ/N)·Σ_j V_{s,j}·max(f_d(j)·n, 0)`, normalized so a cone fully on a unit light sums to the hemisphere area (p. 22-23).
- An interval `[a, b]` integrates `T(s)·L_e(x_s)` with no in-scatter term, so the field holds only light seen directly from the light volume (p. 20).
- Volumes march front to back with `T(0) = 1`, multiplying `T` by `exp(−σ_t·Δs)` and adding `T·(σ_a·L_e + σ_s·L_s)·Δs`; in-scatter is `L_s ≈ (4π/N)·Σ_j f_p·V_{x,j}`, which for the isotropic phase `1/(4π)` used throughout is the mean of the `N` directions (p. 23-24).
- The transfer function maps density to `σ_s` and `σ_a` by linear interpolation between control points; voxels above a threshold render as surfaces with zero `σ` (p. 24).

**Results.** Table 7.1, recalculation time of the radiance field in ms, cube ("square") and tetrahedron mappers (p. 27):

| Scene | 2 cube | 2 tetra | 3 cube | 3 tetra | 4 cube | 4 tetra | 5 cube | 5 tetra |
|---|---|---|---|---|---|---|---|---|
| CT Philips, large white light | 25.88 | 17.65 | 28.28 | 19.68 | 29.16 | 20.40 | 28.70 | 19.95 |
| Bonsai, four small coloured lights | 29.64 | 20.99 | 32.21 | 22.66 | 31.90 | 22.73 | 30.43 | 21.49 |
| Iguana, white background light | 28.05 | 19.18 | 29.96 | 20.95 | 30.45 | 21.48 | 29.55 | 20.91 |
| AVM | 30.82 | 22.05 | 33.89 | 23.95 | 33.39 | 24.17 | 31.45 | 22.70 |

- The cube mapper costs 1.38 to 1.47 times the tetrahedron in every cell, and 2 to 5 cascades adds only 2 to 13% (derived). The ground-truth tests use 5 cascades; neither the 192³ grid nor the 1/100 base is justified. Times fall from 4 to 5 cascades, which the thesis guesses, untested, comes from top-cascade probes sitting farther from the volume edge.
- Quality rises with cascade count mainly for small lights, which distant probes miss with few cascades; large lights change little. The cube mapper looks better, mostly for small lights, and the gap narrows with more cascades (p. 25-26).
- Against a single-bounce Monte Carlo reference (sample count and time not given): surfaces come out slightly darker because cones partly below the surface are dropped whole, some lights are missed, and light bleeds through thin structures such as eye sockets (p. 28). Volumes look nearly identical, with brighter spots from bleeding and darker ones from limited angular resolution, worst for the tetrahedron (p. 30). At very high extinction (`σ_a = 152`, `σ_s = 8`) probes inside the volume collect little light and dark rings appear, so surface rendering is advised there (p. 30-31). One-voxel lights leave dark spots because few directions hit them (p. 31).
- Exposure Renderer needs about 2 s to settle after a change, against at most 20 to 30 ms for RC (p. 32); hardware and method for the comparison are not given, and Table 7.1 reaches 33.89 ms.
- No numeric image metric, memory figure, per-pass timing or run statistics are reported.

**Reading the timings (derived and inference).**

- The cube mapper has 1.5× the tetrahedron's directions (`6·4^c` against `4·4^c`), and it costs 1.38 to 1.47×, so per-direction work dominates and a small part of the time does not scale with directions.
- With the paper's 3D law (probes ÷8, directions ×4, intervals ×2 per cascade), every fixed-length cascade marches the same number of steps, and the top cascade runs to the cube edge. In free space the total march over a 192³ grid then falls as cascades are added, to 0.53, 0.31 and 0.21 of the 2-cascade figure for 3, 4 and 5 cascades, because a long top interval is replaced by shorter ones (derived, with a mean exit distance of 0.449 of the cube side). The stored texels grow from 1.5 to 1.94 times cascade 0 over the same range. The measured times instead rise 2 to 13% and dip at 5, which fits a cost dominated by per-texel work (merging, writes) and by rays ending early in dense tissue, with the falling march length showing at 5 cascades (inference).

**Limits and future work.** Specular reflection is poor, though the nearest direction approximates it; only one bounce is covered; the probe grid is coarser than the surfaces, which causes bleeding; small lights need more directions; mip-based empty-space skipping made the method slower, and acceleration structures may not help (p. 33). Future work: Cook-Torrance and other BRDFs, acceleration structures, and MRI data.

**Inconsistencies.**

- Fig. 5.4 gives cube blocks of `2·3^c` by `2·2^c` where the formulas and base case give `2^(c+1)` by `3·2^c`; the text says the cube direction count rises "by 4" per cascade and the tetrahedron block "by 2", where the formulas multiply.
- The tetrahedron point modulus is printed `2^c`, while four triangles per face at cascade 1 need `4^c`; the flattened index `i_d = i_d_y·2^c + i_d_y` repeats the y component; the cube point index uses the side index where a local index is meant.
- p. 10 says merging yields the last cascade's angular resolution; p. 20-24 keep cascade 0's.
- The reference is called closed-form tracking on p. 29 and regular tracking on p. 30; reference [32] is cited as Yang et al. but lists other authors; Fig. 5.11 has a placeholder caption.

**What it means for RC.**

- **Cone weights.** Shading by the cosine at each cone's centre discards how much of the cone lies above the surface. With the 6 cube directions and normal `+z`, the exact projected solid angles are 1.741 sr for the top face (55.4% of π) and 0.350 sr for each side face (11.1%), while the centre cosine gives the top face everything and the sides nothing. Under uniform unit radiance the centre-cosine sum with cone solid angle `4π/6` gives 2/3 of the exact irradiance for an axis-aligned normal and 1.155 times it for a `(1, 1, 1)` normal, so shading varies by `√3` with normal orientation alone; the thesis's `π/N` prefactor scales both cases down further, to 0.52 and 0.91 of the exact value (derived by numeric integration). This fits the darker surfaces in the ground-truth comparison and the code's half-irradiance bug; precomputed per-cone projected solid angles against a normal fix it at the cost of a small table (inference). The gather rules across codes are in [cascade layout](cascade_layout_and_merging.md#final-gather).
- **Cascade 0 with 4 or 6 directions** is the least angular resolution any 3D RC uses, and every quality problem reported here (missed small lights, dark one-voxel lights, the mapper gap shrinking with more cascades) is an angular-resolution limit of cascade 0 rather than of the hierarchy (inference).
- **Doubling intervals in 3D** keep the paper's 3D scaling but reach only 31 probe spacings after 5 cascades, so the hierarchy never covers the unit cube's 192 spacings; the top cascade runs to the edge instead (inference from the code).
- **Cost.** 20 to 34 ms per full recalculation of a dense 192³ grid (C++ and OpenGL on an Intel i9-13900HX with a 12 GB RTX 4080 Laptop GPU; NIfTI sources up to 535³ downsampled to 192³, p. 25), with the field reused while the camera moves; a per-frame dense world grid at this size would exceed a real-time budget, which is the cost the sparse and screen-space families avoid (inference).

## RC for CT volumes (repository)

The thesis code (https://github.com/ReneeR33/radiance-cascades-volume-rendering, OpenGL 4.4 compute; [Gigi and volume repositories](../sources/2026_gigi_and_volume_rc_repositories.md#rc-for-ct-volumes)) is a full-resolution world-space 3D grid over a unit cube: 192³ probes in cascade 0, 5 cascades, probes halving per axis (192, 96, 48, 24, 12).

- **Scene:** a 192³ combined volume of colour and transmittance (RGBA8 each). Emitter voxels and CT values at or above a cutoff are opaque; lower CT values attenuate as `exp(−(absorption + scatter)/190)` per voxel.
- **Directions:** cube-face subdivision, `6·4^c` per probe (6, 24, 96, 384, 1536). Each direction is the normalized cell centre; its weight is the cell's solid angle (two spherical triangles by Girard's theorem) divided by `4π/n`. A tetrahedral mapper with `4·4^c` directions also exists.
- **Intervals:** doubling, not quadrupling: `[0, 1/r]`, then `[2^(c−1)/r, 2^c/r]` with `r = 100` (about 1.9, 3.8, 7.7, 15.4 voxels), the top cascade running to the cube edge. This is the paper's 3D grid law: spacing ×2, directions ×4, intervals ×2.
- **March:** 1-voxel steps with nearest reads; transmittance multiplies by `T^(190·step)`; an opaque voxel adds its colour times 20 and ends the ray.
- **Merge:** trilinear over the 8 upper probes, each the mean of the 4 child directions `4a … 4a+3`: `colour = c + t·Σ w_q·mean_q`, `trans = t·Σ w_q·meanT_q`. Out-of-range upper probes return the background with transmittance 1. No bilinear fix.
- **Storage:** RG32UI texels holding colour and transmittance as hand-packed 11-11-10 floats.
- **Shading:** a separate ray march through the CT finds surfaces, offsets the lookup 1.7 probe spacings along the normal, interpolates cascade 0 trilinearly, and sums `L_i·max(d_i·n, 0)` over the 6 directions. Translucent samples use a per-probe irradiance texture (the mean of the 6 directions) for single scattering.

Lessons from its problems:

- **Child ordering.** With row-major cells per cube face, children `4a … 4a+3` are four cells in a row of the finer grid, not the 2×2 block under the parent, from cascade 1 upward. Direction indices must be laid out as a quadtree (Morton order per face, or equal-area layouts ordered the same way) for the `4a + l` child rule to hold.
- **Normalization.** Stored values are pre-weighted by solid angle, and the shading sum uses `2π/n` on top, which for uniform light gives half the correct irradiance. Pick one convention and check a uniform-sky case.
- **Memory.** About 1.5 GB of allocations at 192³ (raw cascades 628 MB, merged copies 608 MB, half of the latter never used). A dense full-resolution 3D grid is the method's worst case, as the paper warns. The cascades hold 82.3 M texels at 8 bytes, 658.2 MB or 627.8 MiB, and the merged copies of cascades 0 to 3 are 607.5 MiB, so the note's 628 and 608 are MiB, and the 658 MB in [cascade layout](cascade_layout_and_merging.md) is the same allocation in decimal units (derived). The tetrahedron mapper's 4·4^c directions against the cube's 6·4^c need two thirds of that, about 439 MB (derived).
- **Precision.** 8-bit transmittance rounds very small values to exactly 0, which the march treats as opaque.

## Transmittance estimation (Peters 2025)

Christoph Peters, "Jackknife Transmittance and MIS Weight Estimation", SIGGRAPH Asia 2025 (ACM TOG 44(6), article 204, doi 10.1145/3763273), with code in the `jackknife` branch of MomentsInGraphics/path_tracer ([Peters](../sources/2025_peters_jackknife_transmittance.md)). Ray marching estimates optical depth `τ` without bias, but `exp(−τ̂)` is then biased high, because `exp` is convex (Jensen's inequality). Splitting a fixed sample budget into two independent estimates of `τ` gives a transmittance estimate that is unbiased when `τ̂` is normally distributed, at no extra cost. Text extraction dropped most Greek symbols; formulas marked "reconstructed" were rebuilt from the surrounding text and notation.

**Method.**

- With two independent optical-depth estimates `τ₀` and `τ₁`, `μ̂ = (τ₀ + τ₁)/2` and `σ̂ = |τ₀ − τ₁|/2`. The jackknife transmittance is `T̂ = cos(σ̂)·exp(−μ̂)`, equivalently `Re exp(−(μ̂ + iσ̂))` (eqs. 4 and 7, reconstructed). It is the uniformly minimum-variance unbiased estimate for normal samples (Gray et al. 1973).
- Normality holds approximately for stratified jittered marching with independent jitter per sample, by the Lyapunov central limit theorem, and is close by N = 10 samples. Uniform jittered sampling with one shared offset does not become normal (sec. 4.1, Fig. 4).
- `T̂` stays in [−1, 1] when no control variate exceeds the minimum extinction. Negative values are rare except near zero transmittance, and clamping them adds bias.
- The two estimates share one traversal, so the correction costs nothing measurable.
- Errors (App. A, reconstructed): for one estimate with standard deviation `σ`, the naive estimate has bias `exp(−τ)(exp(σ²/2) − 1)` and variance `(exp(2σ²) − exp(σ²))·exp(−2τ)`; the jackknife with two estimates has variance `½(exp(2σ²) − 1)·exp(−2τ)` and relative RMSE `sqrt((exp(2σ²) − 1)/2)`. Its relative RMSE is never worse than the naive one and up to about 2× lower at large `σ` (Fig. 3).

**Optical-depth estimator (sec. 4).**

- Stratified jittered samples at `t_k = (k + ξ_k)·Δ_max/N` with independent `ξ_k` in [0, 1).
- Variance-aware importance sampling: super-voxels of 16³ voxels store an importance from the mean of `(σ − σ_min)²` over their voxels (eq. 5, reconstructed). The minimum extinction is a control variate, removed before sampling and added back by exact regular tracking; without it estimates go negative and fireflies appear.
- The CDF step is `ξ/N`, so the sample count is fixed. A first pass computes the importance integral and tightens the segment.
- Extinction is stored in FP16, with densities rounded up and minima rounded down so estimates stay non-negative. Super-voxel grids use BC4, jitter uses PCG3D, and trilinear filtering is replaced by stochastic texture filtering.
- The budget is exactly 20 high-resolution samples (two estimates of 10) per non-empty super-voxel and none otherwise.

**Accuracy at 24 samples (Table 1).**

| Estimates | Samples each | Mean | Bias | Std |
|---|---|---|---|---|
| 2 | 12 | 0.13411 | 0.00000 | 0.0405 |
| 3 | 8 | 0.13425 | 0.00014 | 0.0440 |
| 4 | 6 | 0.13421 | 0.00010 | 0.0528 |
| 6 | 4 | 0.13433 | 0.00022 | 0.0490 |
| 8 | 3 | 0.13485 | 0.00074 | 0.0694 |
| 1 (naive `exp(−μ̂)`) | 24 | 0.13797 | 0.00386 | 0.0331 |

Two estimates give a bias below the margin of error over 10⁸ trials and the lowest standard deviation of the jackknife rows. The naive estimate has a slightly lower standard deviation but about 5× the bias of the 8-estimate row.

**Results** (RTX 5070 Ti with clocks locked to 2452 MHz GPU and 13801 MHz memory, Vulkan fragment shader, 1920×1080; volumes Bunny cloud 576×571×437, Intel cloud 625×349×566, Disney cloud 993×675×1224, explosion 200×271×229):

- Intel cloud, direct light from a probe, 32 spp (Fig. 1): biased ray marching 32.9 ms, unbiased ray marching 68.8 ms, jackknife with 2 × 10 samples 42.0 ms, track-length 28.4 ms, ratio tracking 69.4 ms.
- Biased estimators at 1 spp (Fig. 8): the jackknife with N = 10 has the lowest bias on three of four volumes; the naive estimate with the same total samples has about 3× the bias, and biased marching with twice the samples still has more.
- The variance-aware control variate cuts bias considerably and standard deviation slightly (Fig. 9).
- Unbiased comparison (Fig. 10), frame time in ms / mean standard deviation:

| Scene | Track-length | Ratio tracking | Unbiased marching | Unbiased marching 2× | Jackknife |
|---|---|---|---|---|---|
| Bunny | 0.47 / 5.7e-2 | 1.07 / 3.2e-2 | 0.90 / 4.5e-2 | 1.46 / 1.6e-2 | 0.40 / 9.3e-3 |
| Intel | 0.81 / 5.7e-2 | 2.26 / 3.4e-2 | 1.40 / 3.9e-2 | 2.15 / 1.9e-2 | 0.79 / 9.9e-3 |
| Disney | 0.64 / 4.4e-2 | 1.28 / 1.5e-2 | 1.05 / 1.7e+0 | 2.20 / 5.5e-2 | 0.26 / 8.1e-3 |
| Explosion | 0.37 / 5.4e-2 | 0.89 / 2.2e-2 | 0.65 / 2.1e-2 | 1.00 / 1.1e-2 | 0.34 / 6.9e-3 |

  The Disney value of 1.7 for unbiased marching is out of line with the other rows and may be an extraction error.
- Ratio tracking and unbiased marching spend most samples where transmittance is low; the jackknife spends a fixed 20 per non-empty super-voxel (Fig. 11).
- Limitation (sec. 6.3): a ray crossing non-empty super-voxels without passing through the medium can miss all extinction with its 10 samples; in Fig. 14, 86% of samples contribute nothing. Smaller super-voxels (12³ removes most failures in the explosion) or more samples help.

**MIS weights for distance sampling (sec. 2.3, 5).**

- Balance-heuristic weights between free-flight sampling (density `σ(t)·T(t)`) and equiangular sampling need the free-flight density, which is not exact without regular tracking.
- Eq. 9 is unbiased with biased weights, using the jackknife for the transmittance term; eq. 10 merges weight, density and transmittance into one cheaper, biased jackknife call.
- Theorem 2 generalizes the trick to any analytic `g(τ)` as `g(μ̂ + iσ̂)`. The MIS weight has poles, so it is not analytic, but the bias stays small for `σ` below about 1.645 (5% negative mass, Fig. 7). Bias in MIS weights does not bias the radiance of an unbiased MIS estimator (App. D).
- Disney cloud, two point lights, 16 spp, MIS with 32 distance samples (Fig. 12): free-flight only 14.5 ms, SMAPE 11.87; equiangular only 34.0 ms, 20.24; MIS after Miller et al. 2019 45.4 ms, 11.03; naive unbiased MIS 53.0 ms, 7.963; biased MIS (eq. 10) 50.5 ms, 7.941; unbiased MIS (eq. 9) 55.5 ms, 7.957. The order of the last two SMAPE values is ambiguous in extraction. Naive biased MIS visibly brightens the image (Fig. 13).

In RC the jackknife applies wherever an interval's transmittance comes from a few jittered samples instead of exact per-cell path lengths. A DDA with analytic segments, which DexRT and amitabha use, has no estimation noise and needs no correction; a single-frame RC that jitters samples to save steps gets a bias of `exp(σ²/2) − 1` per interval that the merge then multiplies down the chain, which the two-estimate split removes for free (inference).

## Radiance caching in media (Jarosz et al. 2008)

Jarosz, Donner, Zwicker and Jensen, "Radiance Caching for Participating Media", ACM TOG 27(1), article 7, March 2008 (doi 10.1145/1330511.1330518), caches inscattered radiance at sparse points in a medium, each record holding radiance and its spatial gradient, and reuses each record within a radius set by its gradient ([Jarosz](../sources/2008_jarosz_radiance_caching_participating_media.md)). It is linked from RC discussions of volumetric transport and is the volumetric member of the Ward-style irradiance caching family, whose surface members are in [related radiance caches](related_radiance_caches.md). Equation numbers are the paper's; eqs. 34 and 35 are partly garbled in text extraction and follow the surrounding prose.

**Transport and estimators.**

- Extinction `σ_t = σ_a + σ_s`; transmittance `T_r(x ↔ x')` is the exponential of minus the integrated extinction (eq. 3); inscattered radiance is `L_i(x, ω) = ∫ p(x, ω, ω')·L(x, ω') dω'` over the sphere; radiance is constant along empty segments (sec. 2).
- Single scattering as an area integral over surfaces (eqs. 7-9): `L_s(x, ω) = ∫_A p(x, ω, ω̂)·L_r(x' → x)·V(x, x')·H(x, x') dx'`, with reduced radiance `L_r = T_r·L`, visibility `V` and the geometry term `H` with its cosine clamped at 0. The estimator (eq. 11) samples lights and surfaces with `pdf(x_j)`; its gradient (eq. 10) applies the product rule over `p`, `L_r`, `V` and `H`, and the implementation ignores the visibility gradient.
- Multiple scattering (sec. 4, eqs. 28-30): random walks with `N` samples at the first event and one at each later event, distance pdf `σ_t·exp(−σ_t·r_j)` (eq. 29). The gradient translates the whole path, so the phase-function term vanishes because the path's angles do not change. The example scenes use 2K to 8K paths per cache point (sec. 6).
- Directions (sec. 3.4, 4.2, 5.1): isotropic media sample uniformly with pdf `1/(4π)`; anisotropic media store spherical harmonics with `M = 9` coefficients, which the paper says suffice for Henyey-Greenstein with `|g| < 0.6`. A record holds 16 floats (48 bytes) for isotropic media and 28 floats (27 SH coefficients and a radius, 112 bytes by the paper's count) for anisotropic ones. Sixteen 4-byte floats are 64 bytes, not 48; 48 bytes is 12 floats, so one of the two figures is off (derived).

**Cache.**

- Three independent caches, each with its own tolerance: single scattering from lights, surface scattering, and multiple scattering, stored in octrees after Ward et al. 1988 (sec. 5).
- Valid radius (sec. 5.2): ideally the largest `r` for which the relative extrapolation error over the ball stays below `ε` (eq. 31), relative because vision responds to contrast. With the log-space gradient `∇ln L = ∇L/L` (eq. 32), the practical radius is `R(x) = ε·Σ_j L_j(x)/Σ_j |∇L_j(x)|` over the record's samples (eq. 34), summing gradient magnitudes so saddle points do not get infinite radii. Colour radii are computed per channel and the minimum kept; anisotropic records use the zero-order SH coefficient. `ε = 0` never reuses, and `ε = 1` reuses until values differ by about 2×. Radii are clamped in world and screen space, gradients are clamped after Křivánek et al. 2006, and the smaller of the shadowed and unshadowed radii is used.
- Extrapolation (eq. 35) is linear in log space: `L(x) = exp(Σ_k w(d_k)·[ln L_k + (∇L_k/L_k)·(x − x_k)]/Σ_k w(d_k))`, with `w(d) = 3d² − 2d³` and `d_k = 1 − |x_k − x|/r_k`, so a record weighs 1 at its centre and 0 at its radius.
- Queries take a third to a half of render time; there are millions of queries and thousands of records, and a new record costs 100 to 1000 queries (sec. 6).

**Results** (1K×1K, up to 16 spp, one core of a 2.4 GHz Core 2 Duo, sec. 6 and captions):

| Scene | Time | Records | Queries | Notes |
|---|---|---|---|---|
| Cornell smoke (Fig. 6) | 1.42, 2.45, 3.65, 7.50 min | | | equal-time path tracing is noisy |
| Sponza atrium (Fig. 8) | 19 min | about 46K | 79M | 512 walks per multiple-scattering record; 40 min of photon tracing left under 1K usable photons |
| Animated smoke (Fig. 9) | 5.8 min per frame | 9K | 8.2M | cache rebuilt per frame, no flicker |
| Two cars in fog (Fig. 10) | 20.35 min | 175K | 27M | 4K paths per record, 60 lights; 8M photons still showed artifacts |

The abstract claims speedups of several orders of magnitude over path tracing and higher quality than volumetric photon mapping.

**Limitations.** Without the visibility gradient the error metric cannot adapt at volumetric shadow edges, so a lower global tolerance is needed. Spherical harmonics suit highly directional scattering poorly; a 5D cache with separate spatial and angular error terms is suggested (sec. 7).

**What it means for RC (inference).**

- The valid radius is an adaptive form of RC's fixed spatial spacing: a record covers a region inversely proportional to its log-gradient, where cascades space probes by interval length alone. The paper also shows the cost of adaptivity: an octree lookup per query and a record set rebuilt per frame for dynamic media.
- Rebuilding the cache every frame of the animated smoke without flicker is a single-frame result: when every record is recomputed from scratch with enough samples, interpolation between records does not flicker (inference from Fig. 9).
- Exponential, log-space extrapolation suits radiance that falls off exponentially in a medium, a candidate for interpolating volumetric probes where bilinear blending of linear values smears transmittance.

## Spectral transport

DexRT carries 880 wavelengths through its cascades ([above](#dexrt)), and prisms in graphics RC were planned with 6 to 11 bins. Per-channel storage and bandwidth then grow 2 to 3.7× over RGB at 6 to 11 bins and 293× at DexRT's count (derived), which is why a graphics cascade would carry a few bins or a compact basis.

The SIGGRAPH 2021 course "Spectral Imaging in Production" (chapters by Weidlich; Forsythe and Dyer; Mansencal; Hanika; Wilkie; Emrose; Langlands, about 90 pages) covers how film renderers carry colour spectrally ([spectral course](../sources/2021_spectral_imaging_in_production.md)). Chapters: 1 Weidlich, material system (pp. 3-8); 2 Forsythe and Dyer, camera characterization (pp. 9-19); 3 Mansencal, LED walls (pp. 21-42); 4 Hanika, spectral upsampling (pp. 43-53); 5 Wilkie, fluorescence, the ART workflow and Spectral OpenEXR (pp. 54-62); 6 Emrose, hero wavelengths at Animal Logic (pp. 63-70); 7 Langlands, Weta's Manuka (pp. 72-79).

**Spectral sample counts.**

| Use | Samples |
|---|---|
| Smits 1999 basis | 7 basis spectra of 10 samples each (sec. 4.2.2) |
| Hanika's constrained optimization | for example 39 wavelength bins (sec. 4.2.3) |
| Manuka per-vertex spectral inputs | 10 equally spaced bins; heavy on memory and hidden from artists (sec. 1.3.2.2) |
| ART path tracing | 1 nm buckets from a precomputed spectrum; output bands chosen by the user, 16 in Fig. 5.3 |
| Animal Logic Glimpse | hero wavelength chosen stochastically among fixed R, G and B wavelengths (sec. 6.2.2) |
| Manuka paths | 4 randomly offset, uniformly spaced wavelengths per path; colour noise mostly gone by 8 to 16 spp (sec. 7.1) |
| Camera measurement | monochromator sweep 350 to 800 nm in 5 nm steps, 91 samples (sec. 2.2.1.1) |

- Sampling at 10 nm stores about ten times more per colour than RGB, which is why Manuka uplifts RGB to spectra at shading time (sec. 7.1.1).
- Each extra output channel adds image size, splatting hero samples aliases unless the kernel spans more than the nearest bucket, and only lossless compression is considered safe (sec. 5.3).

**RGB to spectrum (ch. 4).**

- A spectrum must reproduce its XYZ, the integral of the colour matching functions times `f(λ)` (eq. 4.1). Reflectances are bounded to [0, 1]; emission is unbounded, and scaling keeps its chromaticity, so emission can use a 2D table over xy (Meng) while reflectance needs a 3D table because the spectral shape changes with brightness (sec. 4.1).
- Glassner: convex combinations of three basis wavelengths, with staircase spectra and negative coefficients outside the primaries' gamut.
- Sigmoid polynomial (Jakob and Hanika 2019): `f(λ) = s(p(λ))` with `p(λ) = Σ_i c_i·λ^(d−i−1)` and `s(x) = ½ + x/(2·sqrt(1 + x²))` (eqs. 4.5-4.6). With `d = 3` coefficients it covers all colours. The RGB-to-coefficient map needs Gauss-Newton or a table, and the coefficients need 32-bit floats in a 3D table and do not interpolate linearly (sec. 4.2.4).
- Fourier moments (Peters et al. 2019): the arctangent of a truncated Fourier series with Lagrange multipliers (eq. 4.7), bounded to [0, 1] by construction. Moments interpolate linearly, so ordinary texture filtering works, and they quantize to 10 bits without trouble; 8 bits needs care.
- Clustered PCA (Otsu 2018) recovers shapes from training data per kd-tree cell over xy, with discontinuities at cell borders and possible negative values.
- The AVX sigmoid variant is fastest on CPUs; the table size dominates cost, and GPUs are more memory-bound (sec. 4.2.5).
- Table 4.1 compares methods by compute, table memory, texture format, filterability, gamut, reflectance or emission, and shape. Its texture and filter cells for Jakob-Hanika (3× ui8, filterable) and Peters (3× f32, not filterable) contradict the chapter text, which says the opposite, so those cells were probably shifted in extraction.
- Manuka replaced its Smits solver with Fourier moments for reflectance: three coefficients round-trip the full wide gamut, and although slower in micro-benchmarks than Smits and the sigmoid, the difference is not measurable in a render (sec. 7.2).
- Manuka solves emission curves at startup from `C = M_sRGB·∫ f(λ)·I(λ)·W_cam(λ) dλ` (eq. 7.1) with D65 and the camera response, relaxing the bound to positivity only. It clips to [0, 1] after uplifting rather than before, which keeps more saturation. sRGB covers most of Pointer's gamut of about 4000 real surface colours; the saturated colours outside it are accepted as lost (sec. 7.2.1).

**Precision and transport (ch. 5, 6).**

- Hero wavelength sampling weights all wavelengths on a path with the balance heuristic (Wilkie et al. 2014, eq. 6.1); one wavelength per path gives rainbow noise.
- In single precision the product of throughput `f` and pdf `p` underflows: with a 1 mm mean free path and albedo 1 it reaches `FLT_MIN` after 8.73 cm (eq. 6.6). Multiplying both by `1/max(f_r, f_g, f_b, p_r, p_g, p_b)` at each bounce makes single precision match double (eq. 6.5, Fig. 6.5).
- Nested dielectrics count crossings (+1 entering, −1 leaving), which ignores internal surfaces in overlapping or holed geometry (sec. 6.3.2).
- Fluorescence is a 2D re-radiation matrix over input and output wavelength, with ordinary reflectance on the diagonal. Dense storage grows with the square of the sampling; Gaussian mixtures (2021) cut it by orders of magnitude and allow importance sampling. Hero sampling handles it in a path tracer (Mojzik et al. 2018). Spectral OpenEXR (Fichet et al. 2021) stores layered and bi-spectral data with an RGB preview layer.

**Cameras and LED walls (ch. 2, 3).** Real sensors do not meet the Luther condition, so the 3×3 camera matrix is optimized against spectral measurements. CRI uses 8 samples and is poorly uniform; CFI uses 99; TM-30-18 is the reporting standard. Adding an amber primary to an LED wall cut mean ΔE00 by 2.6 and raised Rf from 60 to 80; stacked LEE gels 642 and 738 gave SSI 45 and cut mean ΔE00 by 3.1.

**For a spectral cascade (inference).** Fourier moments interpolate linearly, which suits the bilinear and trilinear blends of RC; the merge, though, multiplies per-wavelength transmittance, and the moments of a product are not the product of the moments, so a moment-encoded cascade would have to merge in the spectral domain or keep transmittance in a few explicit bins. Hero wavelengths are a stochastic choice and need accumulation to lose their colour noise, so they do not fit a single-frame cascade. Tantalum, the 2D spectral light tracer used for reference images in the community, is described in [core theory](core_theory.md#radiometry-in-flatland).

## Connections

- **One composition rule.** The merge is the radiative transfer formal solution's composition of segments; DexRT's per-segment update, TypeGPU's `integrate`, the per-step rule and HRC's merge are the same operator in different variables ([core theory](core_theory.md#the-merge-operator)).
- **Mips are cone tracing.** Per-cascade mip marching is voxel cone tracing with a fixed number of steps per cascade, and both inherit its thin-wall leak and its remedy, directional opacity from GIVoxels ([related probe GI](related_probe_gi.md)). DexRT's variance test is the "choose by variance" suggestion made precise, and its 0.25 threshold sits where the averaging error falls below 1% (derived above).
- **Convexity twice.** Mip brightness drift, the density-against-transmittance dispute and the bias of `exp(−τ̂)` are all Jensen's inequality on `exp`, deterministic in the first two and statistical in the third (inference).
- **3D grids agree on doubling.** DexRT's 3D solver, Rulkens and the RC paper's 3D law all double interval length per cascade with ×4 directions, so every fixed-length cascade marches the same number of steps ([core theory](core_theory.md#cascade-scaling)).
- **Hierarchical DDA.** DexRT's HDDA (Museth's VDB traversal), the two-level bitmask DDA and HDDAGI's voxel traversal are one family ([scene representation and tracing](scene_representation_and_tracing.md)); Rulkens found mip-based empty-space skipping slower, while DexRT gained 1.5× from sparsity on a half-empty model, so the payoff depends on how empty the volume is (inference).
- **Per-frame rebuilds.** Jarosz's animated smoke and Rulkens's per-change recalculation both recompute everything without temporal reuse and report no flicker, the same property as single-frame RC.
- **Emission conventions** separate the codes into source-function and per-length families, which decides whether thin glowing media can exist at all.

## Single-frame assessment

- **Deterministic marching needs no accumulation.** A DDA with exact segment lengths has no noise, so volumetric RC in world space is single-frame by construction. Jittered sampling to save steps reintroduces noise and a convexity bias; the jackknife removes the bias at no cost, but the variance stays.
- **In-scattering is the temporal piece.** The community approximates scattering with the previous frame's cascades. Rulkens's single scattering reads the same solve's per-probe irradiance, which is single-frame for one scattering event; multiple scattering needs further solves seeded from the first, each a full cost (inference).
- **Cost of a dense grid.** A dense 192³ grid with 5 cascades took 20 to 34 ms on a laptop RTX 4080 and about 0.6 GB of cascades; one 3D volumetric RC took about half of a 60 fps frame. A full-scene volumetric grid per frame does not fit beside surface GI, so volumetrics in a single-frame budget point to a bounded fog volume or a screen-plane layout, with the far cascades on mips (inference).
- **Mips are cheap and lossy.** Per-cascade mips gave DexRT 3.5× and keep steps per cascade constant; thin walls need six directional opacities per voxel, about 6× the opacity storage of one channel, or a variance limit that keeps walls at full resolution (inference).
- **Formats.** Transmittance needs 16 bits; R11G11B10F holds radiance only; RGBA16F with a single transmittance channel is the common working format. All of this maps onto `RenderingDevice` storage textures and 3D textures; a u64 block bitmask maps to two u32 words. Godot's own volumetric fog uses froxels, described in [Godot integration](godot_integration.md#volumetric-fog).

## Open questions

- Which mip rule loses least for thin walls in a single-frame 3D budget: six directional opacities, a variance limit like DexRT's, or max-filtering for binary occluders with averaging only in media?
- Can the Jensen-gap bound be used directly to pick per block between density averaging and coverage averaging, by the orientation of the structure?
- Does sparse RC work for volumetrics if probes are activated along camera rays through fog, and how many probes does that add per frame?
- What does single-frame multiple scattering cost, and is one scattering event from the same solve plus an ambient term enough for fog?
- Can a spectral cascade keep transmittance in a few bins and radiance in moments, and does the merge stay accurate?
- What is DexRT's actual 3D block-map size, given that the stated 669 words fit neither 8³ nor 16³ blocks at 512³?
- How much do the darker surfaces in Rulkens's comparison shrink once cones are weighted by projected solid angle?
