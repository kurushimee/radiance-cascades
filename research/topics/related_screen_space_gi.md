# Related screen-space GI

Screen-space GI and AO read only the depth, normal and lit-colour buffers, so their cost does not depend on the scene. They are the closest relatives of screen-space RC: each pixel looks along a few screen-space slices, finds what blocks its hemisphere, and gathers light from the pixels below the horizon. This topic covers the horizon family (SSAO, HBAO, GTAO, SAO and line-sweep AO), the indirect-light methods built on it (Mayaux's horizon-based indirect lighting, Path of Exile 1's GI and Therrien's visibility bitmasks), and what each means for single-frame RC. Screen-space RC itself is in [screen space](3d_screen_space.md); depth-buffer tracers are in [scene representation](scene_representation_and_tracing.md#depth-buffer).

| Method | Per slice or sample | Cost per pixel | Thickness model | Indirect light |
|---|---|---|---|---|
| [SSAO](supporting_techniques_structures_and_tracing.md#ssao) | point samples in a hemisphere | N samples | none, or a range check | no |
| [HBAO](supporting_techniques_structures_and_tracing.md#hbao) | one horizon angle per direction | K directions × N steps | infinite (height field) | no |
| [GTAO](supporting_techniques_structures_and_tracing.md#gtao) | two horizons per slice, cosine-weighted closed form | slices × steps | infinite, with falloff | no |
| [SAO](supporting_techniques_structures_and_tracing.md#sao) | spiral samples on a depth mip pyramid | constant in radius | range falloff | no |
| [LSAO](#line-sweep-ambient-obscurance) | a stack of occluders along a swept line | about 2K operations, any radius | infinite | no |
| [HBIL](#horizon-based-indirect-lighting) | horizon per slice, bent cone | 2 slices × 16 steps | infinite | near field from last frame's radiance |
| [PoE1 GI](#path-of-exile-1s-screen-space-gi) | random screen points with mips | fixed sample count | not stated | every pixel a shadowed point light |
| [Visibility bitmask](#visibility-bitmask-ssgi) | 32 sector bits per slice | about 15 instructions per sample over GTAO | constant world thickness `t` | newly occluded sectors × cosines |

The glossary entries explain SSAO, HBAO, GTAO, SAO, bent normals and bent cones; Godot compute implementations of all four AO methods, with their parameters and bugs, are in [Godot projects](godot_projects.md#compositor-effect-projects).

## Contents

- [Line-sweep ambient obscurance](#line-sweep-ambient-obscurance)
- [Horizon-based indirect lighting](#horizon-based-indirect-lighting)
- [Path of Exile 1's screen-space GI](#path-of-exile-1s-screen-space-gi)
- [Visibility-bitmask SSGI](#visibility-bitmask-ssgi)
- [Heightmap horizons](#heightmap-horizons)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)

## Line-sweep ambient obscurance

Ville Timonen, "Line-Sweep Ambient Obscurance", EGSR 2013 (Computer Graphics Forum 32(4); [paper](http://wili.cc/research/lsao/lsao.pdf), BSD-licensed CUDA [source](http://wili.cc/research/lsao/); [notes](../sources/2013_timonen_line_sweep_ambient_obscurance.md)). LSAO sweeps parallel lines across the depth buffer, one family per direction, and keeps along each line a stack of the occluders that can still matter. Each pixel then costs O(K) for K directions with no limit on the radius, where HBAO costs O(K·N) for N steps per direction. The depth buffer is a height field, so every occluder extends infinitely behind its surface. Page numbers are journal pages.

**Estimator (p. 3).**
- `AO(p, n) ≈ (1/K)·Σ_k [sin τ_k + (sin h_k − sin τ_k)·ρ(‖h_k‖)]` (eq. 1), with directions `D_k = (sin φ_k, cos φ_k)`, `φ_k = 2πk/K`, `u_k = −(p_xy·D_k, p_z)`, tangent `t_k = (−n_z, n_xy·D_k)` and occluder vector `h_k = (o_xy·D_k, o_z)`, where `o` points from `p` to the largest occluder along the direction; `sin τ_k = t̂_k·û_k` and `sin h_k = ĥ_k·û_k`.
- Falloff `ρ(d) = r/(r + d²)` (eq. 2), an inverse quadratic after Filion and McNaughton, `r` setting the decay. HBAO's is `ρ₀(d) = max(0, r(1 + C)/(r + d²) − C)` with `C = 0.3` (eq. 3, p. 8), 1 at `d = 0` and 0 at `d = √(r/C)`; eq. 2 has the same shape for small `C`.

**Sweep (Algorithm 1, sec. 4).**
- Each line steps through the depth buffer. At each step `p` is the de-projected sample, `pk = (p_xy·dir, p_z)`, `u = −pk/‖pk‖`, and `h1`, `h2` are the vectors to the top two stack points. While the occlusion from `h1` is less than from `h2` (and an angle condition holds) the top is popped; the result is the occlusion of `h1`, and `pk` is pushed.
- `occlusion(h, u) = sin τ + max(0, h·u/‖h‖ − sin τ)·ρ(‖h‖)` with a fixed tangent `sin τ = −0.85`, which mainly under-occludes; the falloff can compensate (Fig. 7).
- The pop test compares the obscurance of the top two points instead of testing convexity (as Timonen and Westerholm 2010 did), so the hull need not be convex; degenerate cases cost 0.02 to 0.3% in the paper's scenes (sec. 4.1).
- A line of M steps does exactly M pushes and at most M pops, so it costs O(M) (sec. 4.2).

**Sampling and gather (sec. 5).**
- Dense mode places lines 1 px apart with 1 px steps. Sparse mode uses line spacing `D_L` and step `D_S`, for `K/(D_S·D_L)` samples per pixel and `K·W·H/(D_S·D_L)` floats of intermediate storage, about 11 MB in the 1080p examples.
- The gather averages, per pixel, the K nearest sweep values within `√((D_S/2)² + (D_L/2)²)`. Snapping samples to texel centres is safe only for aligned direction sets, `K = 8n` from a `(2n + 1)×(2n + 1)` template. Writing results by atomic scatter was slower than an intermediate buffer, because the writes are uncoalesced.

**Timings (GTX 480, CUDA).** 1920×1080 with a 10% guard band took 1.7 ms (Fig. 1) and 1920(+192)×1080(+108) 2.3 ms (Fig. 13), both at about 1.33 evaluations per pixel (`K = 8, D_S = 2.83, D_L = 2.12`; `K = 16, D_S = 4.87, D_L = 2.46`). Table 1, Sponza, `K = 16`, 20% guard band:

| Resolution | LSAO | HBAO | HBAO/LSAO (derived) |
|---|---|---|---|
| 800×600 | 1.49 ms | 10.5 ms | 7.0 |
| 1280×720 | 2.56 ms | 24.2 ms | 9.5 |
| 1920×1080 | 5.24 ms | 92.5 ms | 17.7 |
| 2560×1600 | 9.58 ms | 249 ms | 26.0 |

From 800×600 to 2560×1600 the pixel count grows 8.5 times, LSAO's time 6.4 times and HBAO's 23.7 times, so LSAO scales about as pixels^0.87 and HBAO as pixels^1.48 (derived). HBAO's exponent near 1.5 fits a step count that grows with the radius in pixels, which grows with the square root of the pixel count at a fixed world radius (inference). Table 2 (1280(+256)×720(+144), sweep and gather): `K = 8` (`D_S = D_L = 1.41`) 1.91 and 0.38 ms; `K = 16` (2.43, 1.64) 1.80 and 0.59; `K = 24` (3.56, 1.69) 1.67 and 0.73; `K = 32` (4.69, 1.70) 1.60 and 0.90; totals 2.29 to 2.50 ms (derived). Fig. 12 at the same resolution, HBAO with N steps against LSAO: `K = 16, N = 48` 37.2 against 1.93 ms; `K = 16, N = 32` 24.2 against 2.56; `K = 8, N = 12` 5.8 against 1.67; `K = 8, N = 16` 7.2 against 2.96. LSAO does about 2K operations per pixel (K in the sweeps, K in the gather) against K·N for HBAO.

**Limitations (pp. 8-9).** All pixels share one direction set, so small K bands; more directions or sparser sampling trade banding for blur. Keeping only the largest occluder per direction underestimates occlusion, and the fixed tangent under-occludes. Without snapping, sampling artifacts appear (Fig. 9). It works on one depth layer; the paper calls it "a balancing act of performance, banding, and blur". Sweeps through volumes and line-sweep transport are in [light transport alternatives](light_transport_alternatives.md).

## Horizon-based indirect lighting

Benoît Mayaux (Patapom), "Horizon-Based Indirect Lighting (HBIL)", March 2018, a 40-page write-up with source for an Eko Software ARPG on the Warhammer Fantasy Battles licence ([PDF](https://github.com/Patapom/GodComplex/blob/master/Tests/TestHBIL/2018%20Mayaux%20-%20Horizon-Based%20Indirect%20Lighting%20(HBIL).pdf), [code](https://github.com/Patapom/GodComplex/tree/master/Tests/TestHBIL); 80.lv covered the source release on 2018-09-21; [notes](../sources/2018_mayaux_horizon_based_indirect_lighting.md)). HBIL extends HBAO into near-field indirect light: the horizon in each azimuthal slice gives AO, a bent normal and cone for far-field probe lighting, and the radiance of the surfaces below the horizon for near-field bounce. Sannikov's paper calls PoE1's GI similar to it; the write-up does not mention Path of Exile. Several formulas are garbled in text extraction, as marked.

- **AO** becomes an integral over azimuthal slices with horizon angle `θ(φ)`; per slice the inner integral is `1 − cos θ(φ)`, and AO is one minus a normalized average of `cos θ(φ)` (normalization garbled, p. 4). A local view vector from each sample to the camera defines the slice frame, with screen-space horizon angles converted by a trigonometric correction (sec. 1.3, garbled). Front and back horizons start from the slice direction projected on the normal plane, which adds much detail (sec. 2.1, Fig. 8). The AO uses GTAO's cosine-weighted form (Jimenez et al. 2016).
- **Bent normal and cone:** the mean unoccluded direction, with per-slice closed forms built from `½[1 − θ₀ + sin θ₀ cos θ₀ − sin θ₁ cos θ₁]` and `½[2 − cos²θ₀ − cos²θ₁]` (sec. 2.2.1). The cone whose solid angle `2π(1 − cos α)` equals the unoccluded fraction gives `α = cos⁻¹(1 − AO)`; `cos α` is kept for dot products (sec. 2.2.2). Far-field light comes through the bent cone from a pre-convolved cube map scaled by a factor, or from order-2 SH (9 coefficients) with a reduced aperture, which the paper finds more accurate (sec. 2.2.3-2.2.4).
- **Indirect light** splits as `E = E_direct + E_far + E_near`, with `E_near(x, n) = ∫(1 − V)·cos θ·L dω` over the occluded part (garbled); the paper notes the near field is usually ignored, simplified or baked. Near-field radiance is the neighbour's diffuse radiance from the previous frame, `L_N ≈ B_{N−1}`, reprojected, which gives unlimited bounces under an independence assumption (sec. 2.3.1). Diffuse radiance is `ρ(x)·(E_direct + E_far + E_near)`. When the horizon rises from `θ₀` to `θ₁` in a slice, the neighbour's radiance is weighted by the matching sine and cosine integral; the only buffer beyond HBAO's is one radiance buffer (sec. 2.3.2). Diffuse is weighted by `1 − F₀` with Schlick Fresnel, dropping a cross term worth at most 0.03% of irradiance, so metals get almost no indirect diffuse (sec. 2.3.3).
- **Pipeline (sec. 3):** reproject last frame's diffuse radiance by scatter in compute with a z-test, fill holes by push-pull (Kraus 2009), compute HBIL at quarter resolution, recompose with lighting and post-processing (Fig. 21); gathering with TAA motion vectors is an alternative. Buffers: full-resolution HDR diffuse lighting with mips (RGB10A2 or R11G11B10 tried), a full-resolution push-pull buffer with mips, and quarter-resolution 4×4-split radiance (texture array), normal (R8G8_SNORM), depth (R16F), irradiance (HDR) and bent cone (R8G8B8A8_SNORM).
- **Slices:** two per pixel, 90° apart, interleaved over 4×4 tiles at quarter resolution, so `4·4·2 = 32` slices per pixel over the tile; temporal filtering smooths the noise, and a bilateral spatial filter is future work (sec. 3.3). Neighbour samples whose normal faces away are rejected with tolerances, though their depth still counts for AO (sec. 3.4, Figs. 24-25).
- **Cost (sec. 3.5):** GTX 680 (2 GB, driver 388.13), 1280×720, 2 slices per pixel, 16 samples per direction, averaged over many scenes: reprojection 0.16 ms (optional), push-pull 0.32 ms (optional), buffer split 0.78 ms, HBIL 1.97 ms; 3.23 ms in all and 2.75 ms for the core.
- **Limits:** off-screen lights and geometry are lost (an off-screen paraboloid buffer is suggested); about two directions per pixel need TAA and more denoising; merging specular with SSR is future work.

## Path of Exile 1's screen-space GI

Sannikov's "hierarchical screen-space variance-based GI", developed in 2017 and shipped in 2018, was by Sannikov's account the first screen-space GI in a released game. The RC paper describes it as horizon-based screen-space sectors over screen-space mipmaps with a Chebyshev occlusion test on two depth moments, close to Mayaux's HBIL above. The ExileCon 2019 talk describes it ([notes](../sources/2019_sannikov_poe_gi_talks.md#screen-space-global-illumination-about-1830-to-2800); its history is in [history](history_and_landscape.md#path-of-exile-1-shadows-and-gi)).

- **Scope.** GI adds a secondary bounce: light from a staircase reaches areas that would otherwise be black, spells act as lights, and an emissive dragon lights its surroundings with no lights placed. Demos include a scene lit by one spotlight and one lit only indirectly. It is optional and on by default in all demos, and gives an AO-like feel that ties the picture together.
- **Model.** Every visible pixel is a point light with its own shadows, optimized for "infinitely many" lights, in a budget of about 3 ms. A path tracer for the same task takes about fifteen lines of code and, by the captions, whose wording is unclear here, about five hours; offline renderers such as Maya, a Max renderer and V-Ray do the same job far slower than 3 ms.
- **Methods not used.** Temporal reprojection, because PoE changes too fast and the result would blur and AO would lag moving objects; baking, because the level generator joins any tile to any other; ray-tracing hardware, with the claim that the algorithm is faster anyway (no figures).
- **Sampling, at fixed cost.** The baseline gathers from a finite set of screen points in an exponential pattern, as AO does, and looks poor. Then neighbouring pixels use different random seeds, spreading the same samples more randomly; a box filter runs over the fixed 4×4 random pattern; samples far from the receiving pixel read lower depth mips, and colour is mip-mapped too. Every step keeps the same sample count and shader cost.
- **Execution.** GI and the point-light shadows run entirely on the GPU, leaving the CPU, which gameplay already loads heavily, free for it, and the two do not block each other.
- **What it lacked.** Its denoiser blurred detail, and it did not compute each part of the result at its own resolution, as PoE's cascaded screen-space shadows did ([ExileCon 2023](../sources/2023_sannikov_exilecon_rendering_poe2.md)); RC was built to give GI that property.

## Visibility-bitmask SSGI

Therrien, Levesque and Gilet, "Screen Space Indirect Lighting with Visibility Bitmask", The Visual Computer 2022 ([arXiv 2301.11376](https://arxiv.org/abs/2301.11376), [doi 10.1007/s00371-022-02703-y](https://doi.org/10.1007/s00371-022-02703-y)), with a [code post](https://cdrinmatane.github.io/posts/ssaovb-code/) of 2023-05-11 ([notes](../sources/2022_therrien_visibility_bitmask_ssgi.md)). It replaces the two horizon angles of GTAO and HBIL with a bit field of `N_b` sectors per hemisphere slice, and treats each depth sample as a slab of constant world-space thickness `t`, so light passes behind it. One bitmask drives AO, directionally occluded ambient light and one-bounce indirect diffuse, and it can be added to any horizon-based technique at small cost. Split RC uses it as cascade −1 ([cascade −1](cascade_layout_and_merging.md#cascade-1-and-contact-detail)), and a Chalmers thesis combines it with screen-space RC ([theses](3d_screen_space_theses.md)).

**Motivation.** Indirect diffuse light is hard to compute in real time, and screen-space methods keep the cost independent of scene complexity. Screen-space ray marching like SSR is noisy for hemisphere integrals; horizon methods (HBAO, GTAO, HBIL) integrate analytically between horizons but assume infinite thickness, which gives halos and over-darkening around thin surfaces; falloff heuristics reduce the artifacts but fail at large radii. The paper says HBAO and GTAO solve the inner integral analytically from two horizons. Multi-layer methods (Deep G-Buffer, multi-layer SSRT) cost too much, so the paper keeps one layer.

**Algorithm.**
- The depth buffer becomes unconnected samples, each with thickness `t`. The slice is split into `N_b` equal sectors, a bit field centred on the projected normal `n` while samples are still taken on both sides of the view vector `v`, each occluded or not; each sample marks a range, and occlusion is a bit count. The paper says this approximates tracing `N_b` rays for the cost of one horizon search.
- **Samples:** the front sample sits at the depth sample (its angle `θ_f` is GTAO's `θ`); the back sample is the front one minus `t·p/|p|`, with `p` the view-space position (Algorithm 1, line 15); the paper does not say which way that moves it. The code post fixes the direction: `dback = dpos − V·t` with `V` from the pixel to the camera, so the back sample lies farther from the camera (inference from that definition). The occluded range runs from `min(θ_f, θ_b)` to `max(θ_f, θ_b)`, converted from cosine to angle space so samples spread evenly.
- **Bits:** the index formula implies, without the text saying so, that θ runs over a range of π centred on zero. Per step, `start = floor((lo + π/2)/π·N_b)`, `width = ceil((hi − lo + π/2)/π·N_b)` as printed, `step_mask = ((1 << width) − 1) << start`, `gi += popcount(step_mask & ~slice_mask)/N_b·light·cos_receiver·cos_emitter`, `slice_mask |= step_mask`, with `slice_mask = 0` at the start of each slice; per slice `ao = 1 − popcount(slice_mask)/N_b`, and the result is `AO/N_d` and `GI/N_d` over the `N_d` slice directions. The code post normalizes each angle as `saturate((sgn·(−θ) − N + π/2)/π)`, `N` the angle from `V` to the projected normal, and computes the width as `ceil((max − min)·32)`, so the paper's extra `π/2` in the width belongs to the start offset only (inference). Setting all of a sample's sectors at once keeps the work O(1) in the sector count.
- **Hit rule:** the paper sets a sector when the sample covers at least half of it, while its listing's `floor` and `ceil` set every touched sector; the code post names `round` (half covered), `floor` (fully covered) and `ceil` (touched) as the options and uses `ceil`.
- **Loop:** inputs `t`, `N_b`, view position, view normal and the radius `r`, a hemisphere radius in world units projected to the screen; step `r/(N_s + 1)` with randomized offsets; per slice direction, `N_s + 1` steps, then the slice's AO. The listing computes a slice tangent and angle it never uses, and does not show how the two sides of `V` map onto the loop. The code post rotates slices randomly about `V`, so the projected normal differs per slice, and steps at a fixed `rayStep`.
- **Sectors:** 32 fit one `uint` and are just past the point where banding (worst near thin objects) nearly vanishes; 128 need four words and vector instructions, at 5 to 10% more cost.
- **Thickness:** small, because over-occlusion near thin objects shows more than leaks behind thick ones. GTAO without falloff equals infinite `t`. Values used: 0.2 for GI, and 1, 0.5, 0.25 and 0.1 in the AO figure at radius 2. A fixed `t` leaks at depth discontinuities, which the paper shows against GTAO with and without falloff. `t` may grow linearly with camera distance to stop distant objects being over-attenuated, which is barely noticeable; per-pixel thickness is future work.
- **AO:** one minus a cosine-weighted visibility integral over `π`, split into slice angle `φ` and inner angle `θ`. The bitmask replaces the inner integral with an average over sectors, which drops its `cos θ·sin θ` weight; the paper does not discuss this and the code post says it ignores the cosine. The outer integral is Monte Carlo over a few slices; `N_s` fetches per side make `2·N_s` per slice, and `N_s` should grow with the radius. The AO is a modification of Unity's GTAO. Benchmarks take one slice per pixel, jittered over several frames.
- **Directional ambient:** the hemisphere splits into as many regions as ambient samples, each sampled at its centre and multiplied by its unoccluded fraction. A bent normal gives one direction and misrepresents ambient light near thin objects such as text; averaging colour then multiplying by AO loses colour variation.
- **Indirect diffuse:** each sample reads the light buffer (direct light with shadows, ambient excluded) and the normal buffer, and contributes its newly occluded fraction times light times both cosines, so samples behind it contribute less. Multi-bounce writes indirect light back into the light buffer for the next frame, which needs balancing or it accumulates. Samples are spaced exponentially, denser near the pixel, which keeps detail around small nearby objects (formula not given), and jittered along the direction to hide banding. Too few samples cause banding and lose detail; jitter and exponential spacing ease that trade-off without removing it. Light and normal reads are incoherent, so the cache is used poorly and the method is bandwidth-heavy. Against SSR-like tracing with the same maximum sample count it is far less noisy, because SSR keeps at most one hit per ray and the bitmask keeps every visible sample.

**Results.** Lumberyard Bistro, chosen for its many thin and shallow surfaces, at 1920×1080 on an RTX 2080 with 32 sectors for AO (the GI table names no GPU); denoising costs a constant 0.3 ms for AO and 0.33 ms (full) or 0.1 ms (half resolution) for GI. No numeric image-error metric appears in the text; comparisons with ray-traced references are visual. The code post gives no timings.

| AO radius | Samples | GTAO (ms) | Bitmask (ms) |
|---|---|---|---|
| 0.8 | 8 | 0.49 | 0.51 |
| 1 | 12 | 0.75 | 0.77 |
| 1 | 16 | 0.95 | 0.97 |
| 2 | 16 | 1.12 | 1.13 |
| 3 | 16 | 1.12 | 1.13 |

The bitmask adds 0.01 to 0.02 ms, about 15 instructions per sample, 1 to 4% (derived), hidden at large radii where the pass is bandwidth-bound; time grows about linearly with samples, and wider radii raise cache misses and can lower performance.

| Indirect diffuse (`t` = 0.2) | Sampling | Denoise | Total |
|---|---|---|---|
| 8 samples, radius 1, constant steps, full res | 0.9 | 0.33 | 1.23 ms |
| 8 samples, radius 4, constant steps, full res | 1.7 | 0.33 | 2.03 ms |
| 16 samples, radius 4, constant steps, full res | 2.3 | 0.33 | 2.63 ms |
| 16 samples, radius 4, exponential steps, full res | 2.6 | 0.33 | 2.93 ms |
| 32 samples, radius 4, exponential steps, full res | 4.0 | 0.33 | 4.33 ms |
| 16 samples, radius 4, exponential steps, half res | 0.97 | 0.1 | 1.07 ms |

The text calls half resolution with a bilateral upsample about 4 times more efficient; the table gives 2.7 times (derived), with more flicker and blur. Doubling samples from 16 to 32 cost 1.54 times (derived). Qualitatively, GTAO over-occludes behind fence bars and leaves halos around poles where the bitmask lets light through; at wide radii GTAO blurs into a blob while the bitmask keeps detail; ambient light is smoother and multi-directional than with surface normals or bent normals; multi-bounce comes close to a path tracer but not exactly, because the method only sees screen pixels.

| Aspect | GTAO and HBIL | Visibility bitmask |
|---|---|---|
| Per-slice state | two horizon angles | `N_b` sector bits |
| Depth model | height field, infinite thickness | constant thickness `t` |
| Integration | analytic between horizons | sector count |
| Visibility per slice | one cone | any number of occluded and open ranges |
| Ambient | one bent-normal direction | several directions, each with its own visibility |
| GI weight | angle difference between samples (HBIL) | newly occluded sectors times cosines |

**Limits.** One depth layer, so hidden surfaces are guessed; unknown thickness, so small `t` leaks at discontinuities and large `t` over-occludes thin objects; too few sectors or samples band; indirect light vanishes when its source is off screen; multi-bounce needs balancing; GI is bandwidth-heavy and cache-unfriendly; half resolution flickers; ambient light sources are static or costly to update, and dynamic low-frequency ambient irradiance is unsolved. Future work: per-pixel thickness, LSAO-style caching to cut bandwidth, and runtime ambient irradiance.

## Heightmap horizons

The Shadertoy sXcGRB stores, per heightmap pixel, the steepest slope toward +x and −x from a row scan and lights terrain from the visible fraction of a moving sun disc above each horizon, a one-axis precomputed horizon map ([2D Shadertoys](2d_shadertoys.md#shaders-that-are-not-rc)).

## Connections

- **One family, three state sizes.** HBAO keeps one horizon per direction, GTAO two per slice, the bitmask 32 sectors per slice; screen-space RC keeps a transmittance per interval per direction and adds a hierarchy over distance; HBIL's slices are one probe direction set per pixel with no hierarchy, which screen-space RC replaces with cascades of probes whose sector count grows with interval length ([screen-space connections](3d_screen_space.md#connections)). The bitmask's newly-occluded rule, which counts each sector's light once from the nearest sample, is front-to-back compositing, the same operation as RC's merge of a near interval over a far one (inference).
- **Exponential sampling is interval scaling.** AO's exponential sample patterns, PoE1's baseline and Therrien's exponential GI steps all space samples by distance from the pixel, and PoE1 reads coarser mips for far samples. RC turns that habit into a rule: spacing, angular resolution and resolution of the source all scale with distance ([penumbra condition](core_theory.md#the-penumbra-condition)) (inference).
- **Mips prefilter the source, pre-averaging the result.** PoE1's distance-dependent mips average the depth and colour that far samples read, so their RC counterpart is per-cascade mip marching, a coarser scene for longer intervals ([volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)), not pre-averaging. Pre-averaging stores the mean of a parent cell's child rays after each ray has applied its own occlusion, the mean the merge would take anyway ([pre-averaging](cascade_layout_and_merging.md#pre-averaging)); a mip averages occluders before any ray meets them, which thins small occluders ([mip occluder dilution](../checks/mip_occluder_dilution.py)), and PoE1 recovers occlusion from the averaged depth with its Chebyshev test on two moments (derived).
- **LSAO is RC's cost argument in screen space.** A sweep shares each occluder among all pixels on its line, so cost stops depending on radius, as RC's cost stops depending on range ([constant cost](core_theory.md#constant-cost)). HBAO's pixels^1.48 scaling against LSAO's pixels^0.87 is the measured penalty of per-pixel marching (derived), and line sweeps are the transport form of the same idea ([light transport alternatives](light_transport_alternatives.md)).
- **Thickness is the shared unknown.** Therrien's constant `t`, screen-space RC's thickness constants and min/max pyramids, and Lumen's step-back at screen-trace hand-off all guess what lies behind one depth layer ([depth-buffer marching](3d_screen_space.md#depth-buffer-marching)).
- **Near-field bounce from last frame.** HBIL's reprojected radiance and the bitmask's multi-bounce feedback are the screen-space form of the lit-frame reuse that every engine cache uses ([engine GI](related_engine_gi.md#connections)).

## Single-frame assessment

- **AO and the first bounce are single-frame by construction**; the noise comes from few slices per pixel. Therrien jitters one slice per pixel over frames and HBIL interleaves two slices over 4×4 tiles with TAA, so both lean on time for their slice count. LSAO is deterministic and noise-free, trading noise for banding and blur, the trade RC makes with its fixed direction sets.
- **PoE1's GI is the shipped single-frame precedent**: no reprojection, a fixed sample budget made to look like more by per-pixel seeds, a 4×4 box filter and mips for distant samples, in 3 ms. Its weakness, a denoiser that blurred detail, is what RC's per-band resolution removes.
- **Multi-bounce is temporal** in HBIL and in the bitmask's feedback; a single-frame design gets one screen-space bounce unless it traces further.
- **Cost of noise-free slices.** The bitmask's GI pass grows about linearly with samples (1.54 times for twice the samples), so replacing temporal jitter with more slices per pixel multiplies sampling time by the slices added; screen-space RC instead shares one cascade's slices among the pixels a probe covers (inference).
