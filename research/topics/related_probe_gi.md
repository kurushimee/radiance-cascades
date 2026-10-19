# Related probe GI

Probe and volume methods that store light on a grid and interpolate it to surfaces: the line from irradiance volumes through light-field probes to DDGI, the propagation and cone-tracing volumes, and the probe caches shipped in games. World-space RC is a probe grid too, so each of these solves a problem an RC grid meets: placement, visibility between probes, leaks, update budgets and blending. Godot's own probe GI, SDFGI and HDDAGI, is described in [Godot integration](godot_integration.md#sdfgi-the-shipped-gi).

| Method | Probes and directions | How light is found | Time | Same-frame result |
|---|---|---|---|---|
| [Irradiance volumes](#irradiance-volumes) (1998) | a grid of irradiance over all directions | precomputed | none | no: probes are baked |
| [Light-field probes](#light-field-probes) (2017) | a few probes, 1024² octahedral radiance with distance and normal | precomputed; rays traced through the probes' depth maps | 98% hysteresis on the per-pixel result | no: probes are baked |
| [DDGI](#ddgi) (2019, 2021) | one grid, 8×8 irradiance and 16×16 distance moments per probe | 32 to 256 rays per probe per frame | hysteresis 0.85 to 0.98 | no |
| [DDGI resampling](#ddgi-resampling) (2021) | DDGI queried at the second vertex | ReSTIR over emitters and DDGI | spatiotemporal reuse | no |
| [Enshrouded](#enshrouded) (shipped) | 12 cascades of 32³ cells | SDF tracing, fixed ray budget | 16 rays per stable probe per frame | no |
| [Light propagation volumes](#light-propagation-volumes) (2010) | 3 cascades of 32³ cells, 4 SH coefficients per colour | reflective-shadow-map lights propagated cell to cell, 8 iterations | none | yes, blurred and leaky |
| [Voxel cone tracing](#voxel-cone-tracing) (2011) | none: a prefiltered voxel octree | about five cones per pixel | light reinjected only when lights move | yes, with the scene blurred into mips |
| [Godot SDFGI, HDDAGI](godot_integration.md#sdfgi-the-shipped-gi) | 17³ or 17 × 9 × 17 probes per cascade, 16 to 25 rays | SDF or voxel DDA | 6 to 32 frames | no |

## Contents

- [Irradiance volumes](#irradiance-volumes)
- [Light-field probes](#light-field-probes)
- [DDGI](#ddgi)
- [DDGI resampling](#ddgi-resampling)
- [Other probe grids](#other-probe-grids)
  - [Chen's Monter probes](#chens-monter-probes)
  - [Enshrouded](#enshrouded)
- [Light propagation volumes](#light-propagation-volumes)
- [Voxel cone tracing](#voxel-cone-tracing)
- [Lambru's comparison of engine GI classes](#lambrus-comparison-of-engine-gi-classes)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)
- [Open questions](#open-questions)

## Irradiance volumes

Greger, Shirley, Hubbard and Greenberg, "The Irradiance Volume", IEEE CG&A 18(2):32-43, 1998 (doi 10.1109/38.656788), extends irradiance to every point and direction in space for scenes that overwhelm conventional GI (abstract excerpt), a 5D function of position and direction, so objects anywhere in a lit scene can be shaded from it. At the time this meant static scenes, precomputation and interpolation; partial real-time updates of such grids came around 2010 ([LIRIS talk](history_and_landscape.md#non-english-overviews)). The full text could not be read: the Cornell pages and PDF returned 403 or timed out, the IEEE and DOI routes returned empty shells or reset connections, and no other copy turned up (2026-10; [notes](../sources/2010_kaplanyan_cascaded_light_propagation_volumes.md#irradiance-volumes-greger-et-al-1998)), so its storage and interpolation details are not recorded here. Its descendants in this topic keep the idea and add what it lacked: DDGI adds per-probe visibility and runtime updates, LPVs compute the volume in one frame by propagation, and the ambient cubes of daGI v1 and HSGI's mobile probes are compact irradiance volumes ([engine GI](related_engine_gi.md)).

## Light-field probes

McGuire, Mara, Nowrouzezahrai and Luebke, "Real-Time Global Illumination using Precomputed Light Field Probes", I3D 2017 ([notes](../sources/2017_mcguire_light_field_probes.md), DOI 10.1145/3023368.3023378). A regular grid of probes stores, per octahedral texel, radiance, the normal of the nearest surface and its radial distance, so the probe set is a ray-traceable approximation of the scene. Diffuse light comes from prefiltered irradiance weighted by a Chebyshev test on distance moments, the visibility test DDGI later made dynamic. Section, figure and table numbers below are the paper's.

**Storage (sec. 3).**
- Probes sit on a regular grid inside the scene bounds, unjittered in the results; each is one layer of a 2D texture array, in Cigolle's octahedral map ([direction maps](cascade_layout_and_merging.md#direction-maps-in-3d)), which the paper says saves about 4× in space and bandwidth over cube maps at equal quality.
- Radiance R11G11B10F (32 bits), normal RG8 (16 bits) and radial distance R16F (16 bits), 8 bytes per texel; a compressed alternative (BC6H radiance, two BC4 for normals, R16F distance) gives 4 bytes. Results use uncompressed textures to shorten generation.
- Radiance probes are 1024² in all results, sized so a texel's solid angle does not exceed a pixel's at the probe center, which avoids aliasing in mirror reflections; Fig. 18 compares 64², 256² and 1024². That is 8 MiB per probe uncompressed and 4 MiB compressed (derived).
- Irradiance probes are 128² at 8 bytes (128 KiB, derived), with squared distance (16-bit float) in place of the normal channel for the Chebyshev test; the paper says 32² often suffices.
- Generation rasterizes six cube faces per probe and resamples to octahedral. Direct light is the first bounce, and more bounces come from re-shading and re-rendering the probes, 1 to 2 minutes per scene (sec. 6).

**Tracing (sec. 4).**
- A ray is traced in the probe whose center is closest to the ray's line. In the octahedral map it projects to at most four 2D polyline segments, one per octahedral face crossed, and a probe answers HIT, MISS or UNKNOWN, the last when the ray passes behind a surface the probe cannot see.
- On UNKNOWN the ray origin advances to the exit point and the next of the eight surrounding probes is tried, by `i' = (i + 3) mod 8` with offsets `(i mod 2, ⌊i/2⌋ mod 2, ⌊i/4⌋ mod 2)`, which moves to the farthest probe (Fig. 3). If all eight fail, the ray is taken to hit at the last seen location.
- A two-level min-mip hierarchy of radial depth, the second level at 1/16² resolution, speeds the depth tests; more levels would need a stack, which shaders cannot hold without spilling to memory (sec. 4.2). Back faces are rejected with the stored normal.

**Shading (sec. 5).** Each pixel traces two indirect rays, one Lambertian and one glossy, with cosine-weighted BRDF sampling (sec. 5.1). Lambertian results get a 12-pixel cross-bilateral filter at stride 2 and an exponential moving average with 98% hysteresis; glossy a 3-pixel filter and 75%. Visibility-aware irradiance (sec. 5.2): probes prefilter cosine-weighted irradiance and the first two moments of radial distance, `E[r]` and `E[r²]`, and a query blends 8 probes with trilinear weights times a clamped dot product between the normal and the direction to the probe, times a Chebyshev test with `σ² = |E[r]² − E[r²]|` ([Chebyshev bound](supporting_techniques_structures_and_tracing.md#variance-shadow-maps-and-the-chebyshev-bound)), normalized to sum to one: eight texture fetches per shading point. This removes light and dark leaks around occluders (Figs. 10-12), while probe-indexing noise remains where visibility is complex.

**Results (sec. 6).** GeForce 1080, 1920×1080, full-resolution shading (Table 1, ms):

| Scene | Probes | Radiance texels | Lambertian (ms) | Glossy (ms) |
|---|---|---|---|---|
| Cornell Box | 2×2×2 | 2048² | 0.358 | 0.000 |
| Cornell Box | 2×2×2 | 256² | 0.302 | 0.000 |
| Sponza (statue) | 8×2×4 | 512² | 0.332 | 0.151 |
| Living Room | 4×4×4 | 1024² | 0.293 | 4.401 |
| Luxury Kitchen | 4×4×4 | 1024² | 0.358 | 9.334 |
| San Miguel | 8×2×8 | 1024² | 0.520 | 47.170 |

The squares on the texel counts are lost in text extraction and restored. The Living Room's 4.7 ms total matches Fig. 1. Fig. 11 shows ray-cast indirect at 13 ms against 0.2 ms for prefiltered visibility (about 65×) in a 3×2×3 grid. San Miguel's 128 probes take about 500 MB compressed, against about 2 GB for its compressed geometry and textures (sec. 7), which matches 128 × 4 MiB = 512 MiB (derived).

**Limits.** Probes are precomputed for static geometry; dynamic receivers are lit, but dynamic objects cast no indirect light (Fig. 16), and real-time probe updates are future work. Glossy cost follows glossy coverage, so San Miguel, with broad glossy lobes everywhere, is slow. Primary rays alias (Fig. 20), and too few probes leave interreflection artifacts. Spherical harmonics were rejected because they ring and need 2 to 3× the bandwidth (sec. 7).

## DDGI

Majercik, Guertin, Nowrouzezahrai and McGuire, "Dynamic Diffuse Global Illumination with Ray-Traced Irradiance Fields", JCGT 8(2), 2019; Majercik, Marrs, Spjut and McGuire, "Scaling Probe-Based Real-Time Dynamic Global Illumination for Production", JCGT 10(2), 2021; and NVIDIA's RTXGI-DDGI SDK, 2019 to 2024 ([notes](../sources/2019_majercik_ddgi.md)). DDGI makes light-field probes dynamic: one grid of probes, each tracing a full sphere every frame and blending into octahedral irradiance and depth maps. It is the probe method world-space RC is most often compared with, and its blend and query code is mature. Its octahedral mapping and border copy are Cigolle's ([notes](../sources/2014_cigolle_octahedral_unit_vectors.md)).

**Probes and storage.**
- Probes sit on a uniform grid with power-of-two counts and per-axis spacing (sec. 4.1), one cage of 8 per cell; 1 to 2 m suits human-scale scenes (the SDK docs say 2 to 3 m), and at least one full cage should fit in each room.
- Per probe: 8×8 octahedral irradiance (R11G11B10F, or RGB10A2 in the timed setup) and 16×16 mean and mean-squared distance (RG16F), in an atlas with a one-texel border ([octahedral borders](cascade_layout_and_merging.md#direction-maps-in-3d)). That is 1,696 bytes per probe with borders (derived). 8-bit formats show artifacts, and R11G11B10F tints grays green.
- 32 to 256 rays per probe in a spherical Fibonacci pattern, rotated randomly each frame (Arvo's method in the SDK; [sampling](supporting_techniques.md#sampling-and-noise)). Probe count matters more than angular resolution.

**Update.**
1. Trace all probe rays in one batch.
2. Shade the hits with the normal shading path, reading last frame's probes for indirect light, which adds one bounce per frame.
3. Blend into each texel: irradiance `Σ max(0, n·ω)·L / (2·Σ w)`, distance with a cosine power of 50 and distances clamped to `1.5·|spacing|`.

[Hysteresis](supporting_techniques.md#hysteresis) is 0.85 to 0.98 (SDK default 0.97). The 2021 paper adds a perceptual encoding, storing `pow(irradiance, 1/5)`, blending in that space and at query raising each sample to `5/2`, interpolating and squaring; gamma 5 converged fastest and damps fireflies. Its convergence heuristics: per texel, a change above 25% lowers hysteresis by 0.15 and above 80% sets it to 0, and scene events lower it for a few frames (15% for 4 frames after a small light change, 50% for 10 frames after a large one). The SDK instead lowers hysteresis by 0.75 past its threshold, scales large brightness jumps by 0.25, and bounds each update so dark-going texels still move at least 1/1024 per frame.

**Query.** For each of the 8 surrounding probes:
- Bias the sample point by `(0.2·n + 0.8·v)·0.75·minSpacing·0.3` in the 2021 paper (`v` toward the camera), or `0.1·n + 0.1·v` in the SDK; too much bias leaks through walls.
- Apply the wrapped backface weight `((dot(dirToProbe, n) + 1)/2)² + 0.2`.
- Apply Chebyshev visibility from the stored moments toward the point: if `d > μ`, `p = σ²/(σ² + (d − μ)²)`, cubed, and the weight is multiplied by `max(0.05, p)`.
- Crush tiny weights (`w < 0.2` becomes `w³/0.04`), then multiply by the trilinear weight.

Normalize the sum, square to undo the encoding, and multiply by 2π. Rays that hit backfaces store depth shortened by 80% and are skipped in irradiance blending, so probes inside walls drop out through the visibility test.

**Relocation and states.**
- 32 fixed, unrotated rays per probe decide moves. With more than 25% backface hits the probe is inside geometry and moves through the closest backface; with a front face closer than a minimum distance it moves away along the farthest free direction. Offsets stay within 45% of a cell, and only static geometry moves probes, because dynamic objects made them unstable.
- A probe is inactive when it is inside geometry or none of its rays hits a surface within one cell; inactive probes trace only their fixed rays. The 2021 paper adds sleeping probes that wake when a dynamic object's bounds, grown by one cell, reach them, which saved 30 to 50% of update time.

**Volumes.** A camera-following volume is a circular buffer that spawns a new plane of probes when the camera moves a cell, as in a clipmap. Several volumes cascade outward at falling density, each fading out linearly over its last cell, and the shader accumulates densest first and stops once the weights reach 1. The 2021 update moved to compute with ray results in shared memory, 3× faster than the pixel-shader version.

**Timings.** On an RTX 2080 Ti with 32×8×32 probes, 64 rays and 8×8 maps: trace 0.8 ms, shade hits 0.4 ms, update 0.7 ms and sample at pixels 0.5 ms, 2.6 ms in all (the text also says 7 ms), with throughput above 1.5 G rays/s. Known limits: ghosting behind small bright moving lights, and no fixed ray budget. The 2019 paper adds 32 to 256 rays on 16×8×16, 32×8×32 and 32×16×32 grids at 1.48 to 1.66 G rays/s on the 876,127-primitive Greek Temple (Table 1), every probe updated every frame with the same rays (sec. 4.2), and irradiance under 5% of the range down-weighted (p. 14). Its Table 2 caption lists color as RGB10A2 while the text says R11G11B10F. The Table 2 rows sum to 2.6 ms, and adding the 2.4 ms brute-force glossy pass gives 5.0 ms, neither of which is the 7 ms in the prose; Fig. 1 gives 6 ms per frame (derived). The 32×8×32 grid's 524,288 probe rays in 0.8 ms are 0.66 G rays/s, under half the stated throughput, so the 1.5 G rays/s likely counts more rays than the probe trace (derived).

**GDC and GTC 2019.** McGuire presented DDGI at GDC 2019 as "Ray-Traced Irradiance Fields (Presented by NVIDIA)" ([GDC Vault 1026182](https://www.gdcvault.com/play/1026182/), session 400013301; the video was not read). The page pitches glossy ray tracing plus irradiance-field probes that scale across DXR GPUs, cut leaks without per-probe or lightmap work, update without denoising or convolving radiance probes, and stop leaks through walls with moment-based depth. The matching 90-page deck, "Dynamic Diffuse Global Illumination with Ray-Traced Irradiance Fields" (April 2019, GTC session S9900, [PDF](https://developer.download.nvidia.com/video/gputechconf/gtc/2019/presentation/s9900-irradiance-fields-rtx-diffuse-global-illumination-for-local-and-cloud-graphics.pdf); PDF pages, two below the printed footers) adds:
- Diffuse GI 1.0 ms and glossy 1.1 ms per frame at 1080p on an RTX 2080 Ti at 1.5 G rays/s (pp. 7-8), mip generation about 0.1 ms, glossy down to about 0.5 ms as in Battlefield V (p. 33); a summary of 1 ms per frame and 4.5 MB per cascade, scaling down to Xbox One by updating less often and up to 4K, 240 Hz and VR (p. 86).
- Cascades of 32×4×32 = 4,096 probes around the camera updated often, with coarser cascades in space and time for large scenes; placement can be optimized around static geometry and overridden by artists (p. 42).
- Irradiance 6×6 R11G11B10F and distance 16×16 RG16F, "5 MB GPU RAM for 8k probes" (p. 43), 1,024 + 144 = 1,168 bytes per probe with bilinear borders (p. 74). The paper uses 8×8 irradiance; which came later is not stated. At 1,168 bytes, 4,096 probes are 4.78 MB, which matches the 4.5 MB per cascade, while 8,192 probes would be 9.6 MB, not 5 MB (derived).
- Three passes, trace (packed with the glossy rays), blend with duplicated borders and sample; shading reads the previous iteration, which gives infinite bounces at a cost independent of frame rate and resolution (p. 44). Irradiance is blurred over a cosine hemisphere and depth over a power cosine to keep some sharpness (p. 66).
- Hysteresis is the lever for scaling down, with no value given, and bright scenes can use fewer diffuse rays (p. 84); the deck gives no ray count per probe.
- The query code (pp. 69-74, read from extracted PDF text) matches the paper's terms, with the weight times `trilinear + 0.001`, the shading point moved by `bias·(n − view)`, and irradiance accumulated as `sqrt(texel)·weight` and returned as `(rgb/a)²`, so the blend runs in a square-root domain (inference from the pairing).

**SDK code.** Defaults: 256 rays per probe, hysteresis 0.97, distance exponent 50, irradiance gamma 5, view and normal biases 0.1, minimum front-face distance 1.0. A texel whose stored mean is zero gets hysteresis 0, so new probes fill at once. Found by reading: the distance texture's byte size is set to 8 only when the irradiance format (not the distance format) is two 32-bit floats, so other combinations undercount it; and the sample's default build traces probe rays through NVAPI with back faces culled, while relocation and classification count back-face hits, which that build may then never see (not confirmed by running). The SDK publishes no costs.

**What history buys.** An exponential average with new-sample weight `α = 1 − h` has `α/(2 − α)` of one frame's variance, so it is worth `(2 − α)/α` frames of rays. For the 32×8×32 grid at 64 rays:

| Hysteresis | Frames' worth | Rays per probe | Single-frame rays for the same noise | At 1.5 G rays/s |
|---|---|---|---|---|
| 0.85 | 12.3 | 789 | 6.5 M | 4.3 ms |
| 0.90 | 19.0 | 1,216 | 10.0 M | 6.6 ms |
| 0.97 | 65.7 | 4,203 | 34.4 M | 23.0 ms |
| 0.98 | 99.0 | 6,336 | 51.9 M | 34.6 ms |

At the SDK default a single-frame DDGI of equal noise would trace 34 M rays, about 23 ms of tracing on the hardware it was measured on (derived). This is the cost RC's cascades are meant to avoid: they spend many rays only at the coarse levels, where probes are few ([core theory](core_theory.md#rays-traced-and-rays-built)).

## DDGI resampling

Majercik, Müller, Keller, Nowrouzezahrai and McGuire, "Dynamic Diffuse Global Illumination Resampling", arXiv 2108.05263, 2021 ([notes](../sources/2021_majercik_ddgi_resampling.md)). It queries DDGI at the second path vertex instead of the first and makes DDGI a light source inside ReSTIR ([glossary](supporting_techniques.md#resampling-and-sampling-theory)), so direct and indirect samples compete in one resampling step. The paper gives no probe grid sizes, rays per probe or texture formats, and some equations are garbled in extraction.

**Method (sec. 2-3).**
- The rendering equation `L = L_e + T_f·L` (eq. 1) splits transport into diffuse and glossy, `T_f = T_fd + T_fg`. DDGI approximates `L ≈ L_e + T_fd·L_e + L_DDGI + T_fg·L` (eq. 2), with `L_DDGI = Σ_{i≥2} (T_fd)^i·L_e`.
- Per pixel (sec. 3.1): generate candidates from a few emitter points and BSDF-sampled secondary rays; pick one by weighted reservoir sampling in proportion to `L_e + L_DDGI`, resampling among spatial neighbours and across frames (1 temporal and 3 spatial candidates, sec. 3.6); trace one shadow ray; if visible, shade with `L_e` plus the DDGI term. The paper likens it to final gathering with photon mapping.
- Augmented probes (sec. 3.2, eq. 5): the probe update gathers `L_DDGI+ + L_e` at its ray hits instead of the double-bounce form (eq. 4), a single-bounce recursion that converges to the full `T_f·L`. Direct light in the update is attenuated by the inverse square of the total distance (probe-to-surface plus probe-center offset), scaled by a per-scene slider.
- Glossy (sec. 3.3, eq. 6): irradiance at the specular direction approximates prefiltered radiance, with one Monte Carlo sample in proportion to the glossy lobe; converting irradiance to radiance needs a factor of 2 (prefactor garbled). Glossy recursion stops when the path footprint (squared vertex distances weighted by sampling density, after Bekaert et al.) exceeds 0.2 times the camera footprint (eqs. 7-8).
- The combined estimator (eq. 9) is `L ≈ L_e + T̄_f(L_e + L_DDGI+) + T̃_f(L_e + L_DDGI+)`, where `T̄_f` clamps the geometry term at `G_max = 1` and `T̃_f` estimates the residual with an extra BSDF sample (Kollig and Keller 2006, sec. 3.5).
- Bias (sec. 3.4, Fig. 5): DDGI's view-and-normal offset leaks at short distances, so the query point moves a fixed distance back along the incoming path instead.
- Caching (sec. 3.6): each candidate reuses the DDGI value computed when its vertex was shaded, removing one query per candidate; MAPE goes from 0.63 to 0.64 and frame time from 50.3 to 18.4 ms (Fig. 7), the added error being noise, not bias. The error metric (sec. 4) is `MAPE = (1/N)·Σ |v_i − v̂_i|/(v̂_i + 0.01)` ([metrics](supporting_techniques_transport_and_math.md#image-metrics)).

**Results.** Direct3D 12 in Falcor, Core i7-6800K and RTX 3090, 1920×1080, 1 spp. Frame time (ms) and MAPE (Fig. 8):

| Scene | Primary DDGI | PT + ReSTIR | Secondary DDGI | + DDGI in ReSTIR | + denoising |
|---|---|---|---|---|---|
| Pink Room | 10.2 / 0.44 | 49.1 / 1.35 | 10.8 / 0.79 | 15.8 / 0.45 | 24.0 / 0.22 |
| Greek Villa | 12.2 / 0.80 | 22.5 / 1.10 | 12.8 / 0.78 | 18.4 / 0.64 | 26.6 / 0.38 |
| Room Door | 8.62 / 0.07 | 18.9 / 1.73 | 9.05 / 0.52 | 13.5 / 0.23 | 22.0 / 0.08 |
| Split Room | 6.73 / 0.22 | 12.4 / 0.76 | 7.00 / 0.38 | 10.9 / 0.18 | 18.3 / 0.12 |
| Red Ball | 7.89 / 0.18 | 12.7 / 0.88 | 8.15 / 0.54 | 13.1 / 0.17 | 21.2 / 0.05 |
| Living Room | 10.0 / 0.27 | 54.5 / 1.18 | 10.8 / 0.45 | 18.4 / 0.46 | 26.3 / 0.19 |

Frames, time and MAPE to equal error (Table 1):

| Scene | PT + ReSTIR | + secondary DDGI | + DDGI resampling |
|---|---|---|---|
| Greek Villa | 129, 2908.00 ms, 0.573 | 8, 113.52 ms, 0.578 | 1, 19.83 ms, 0.572 |
| Living Room | 315, 17157.04 ms, 0.366 | 1, 10.82 ms, 0.366 | 3, 56.57 ms, 0.365 |
| Pink Room | 29, 1423.70 ms, 0.384 | 9, 97.21 ms, 0.390 | 1, 16.85 ms, 0.383 |
| Red Ball | 109, 1381.71 ms, 0.140 | 29, 254.17 ms, 0.142 | 1, 13.37 ms, 0.140 |
| Room Door | 4095, 77278.05 ms, 0.206 | 79, 748.51 ms, 0.200 | 1, 13.28 ms, 0.199 |
| Split Room | 150, 1854.92 ms, 0.162 | 27, 202.42 ms, 0.162 | 1, 10.92 ms, 0.161 |
| Average | 804.50, 17000.57 ms, 0.305 | 25.50, 237.77 ms, 0.306 | 1.33, 21.81 ms, 0.303 |

Cost per component, trace and shade / resampling / probe update (Table 2, ms):

| Scene | PT + ReSTIR | + secondary DDGI | + DDGI resampling |
|---|---|---|---|
| Greek Villa | 20.38 / 1.10 / – | 10.65 / 1.20 / 1.54 | 14.03 / 3.13 / 1.55 |
| Living Room | 52.72 / 1.42 / – | 8.18 / 1.62 / 0.57 | 13.32 / 4.47 / 0.57 |
| Pink Room | 46.60 / 1.08 / – | 8.08 / 1.26 / 1.13 | 11.99 / 2.41 / 1.14 |
| Red Ball | 10.71 / 0.95 / – | 5.47 / 1.27 / 1.02 | 8.57 / 3.23 / 1.01 |
| Room Door | 16.91 / 1.10 / – | 6.71 / 1.50 / 1.07 | 9.64 / 2.33 / 1.08 |
| Split Room | 10.90 / 0.88 / – | 5.33 / 1.24 / 0.44 | 7.63 / 2.65 / 0.44 |
| Average | 26.37 / 1.09 / – | 7.40 / 1.35 / 0.96 | 10.86 / 3.04 / 0.97 |

- DDGI resampling reaches equal error fastest everywhere except the Living Room, where DDGI leaks through thin walls under strong sun; on average it needs 1.33 frames and 21.81 ms against 804.5 frames and 17,000.57 ms for PT with ReSTIR, about 780 times less time (derived). Resampling costs 1.7 ms more on average with DDGI as a light. Fig. 1 (Greek Villa): PT with ReSTIR 22.5 ms, secondary DDGI 12.8 ms, DDGI resampling 18.4 ms, with OptiX denoising 26.6 ms. Primary DDGI is fastest and biased.
- Limits (sec. 5): ReSTIR works in screen space and depends on motion vectors, slow camera motion and no transparency, and resampling correlates samples in space and time, which leaves less for a denoiser. DDGI is grid-based, scales poorly to large scenes and cannot resolve caustics, shadows, AO or near-specular detail; a more accurate cache would give better quality. A control-variate variant produced leaks and negative fireflies, and a path-guiding variant was too slow (sec. 5.1, Fig. 9).
- Querying the cache one bounce later hides its low resolution behind a BSDF sample; an RC volume queried at secondary vertices meets the same trade between query position and leak exposure. Equal error in about one frame depends on ReSTIR's spatial and temporal reuse, and without temporal candidates the 1 spp noise is what the denoiser column shows (inference).

## Other probe grids

### Chen's Monter probes

Chen's 2020 Monter devlog post ([handmade.network](https://handmade.network/p/75/monter/blog/p/7288-engine_work__global_illumination_with_irradiance_probes), cited by tmpvar's 3D grid; [notes](../sources/2024_tmpvar_rc_3d_grid.md#links-found)) describes a small engine's irradiance probes:
- Each probe stores indirect light plus sky as four SH coefficients per channel in R11G11B10F, 16 bytes per probe, with the basis `0.2821`, `−0.4886·y`, `0.4886·z`, `−0.4886·x`, and shading blends eight probes trilinearly, convolved with the BRDF.
- Probes are ray traced in batched compute passes; rasterizing cube maps is called a terrible case for raster. Updating only a few key probes at a time is what makes real-time updates possible, with no rate or timing given.
- A tangent-plane weight still leaks in corners, such as a probe inside a ceiling, so visibility follows DDGI with 16×16 octahedral depth and depth squared. SH depth rang and failed, and smaller maps showed artifacts.
- The interpolation seams are the octahedral borders: the cut edges of the unfolded map must be stitched to their mirrored neighbours, and duplicating border texels alone is not enough for bilinear filtering. Depth is truncated before prefiltering, backface hits store 0 so probes inside walls drop out, and the lookup moves along the normal and toward the camera.
- The world is 100 × 100 × 40 m at 0.5 m spacing (1 m showed artifacts), given as 800,000 probes and 784 MB at 1 KB of visibility each. A uniform 0.5 m grid there has 3.2 million points, and 800,000 × 1 KB is about 819 MB, so the figures are approximate or the placement is not uniform (derived). The post says placement follows Remedy's 2015 GI talk, deferred to a later post.

### Enshrouded

Keen Games' shipped cascaded probe cache, from a conference talk ([notes](../sources/2026_rc_conference_talks.md#enshrouded-a-cascaded-probe-cache)). It is not RC, but a world-space probe system with cascaded grids, SDF tracing and a fixed ray budget, built to run on a Steam Deck.
- A "spatial cascaded cache": a 32³ world-aligned grid around the player, 12 cascades, 2 m spacing at cascade 0 doubling per cascade, with at most 16,000 active cells, activated from the depth buffer and garbage-collected lazily. A 16³ ambient grid with 8 cascades covers distance, its last cascade centered on the world as a fallback.
- Rays trace an SDF of the voxel world, the same on all hardware. Hits are shaded with emission, sun with a shadow ray, point lights from a light list per cell, and probe GI for further bounces.
- Probes that land in a wall are pushed out to the nearest SDF surface, then offset toward the camera and along the normal. A probe whose summed ray distance is under 1 mm is dead and skipped.
- A new probe starts with 512 rays and drops to 16 per frame, which only checks for change; activity raises it again. The whole budget is fixed per platform at 100k, 250k or 500k rays per frame. 16,000 active cells at 16 rays is 256,000 rays, the middle budget (derived).
- Rays are importance sampled from each probe's own radiance, with uniform sampling every 5 frames so the guide cannot starve directions; uniform sampling alone flickered at 16 to 32 rays.
- Rays are sorted by position (8³ bins) and octahedral direction (4×4 bins), and hits are shaded by separate sky, terrain and building shaders, because mixed rays diverged badly.
- Radiance is stored in E5B9G9R9 (32 bits) to save bandwidth, occlusion moments in RGBA16F, and visibility uses a Chebyshev test on mean and squared distance as in DDGI.
- Overlapping cascades blend stochastically: in the overlap zone the coarser cascade is picked with a probability that rises from 0 to 1.
- A probe on a surface that sees ground on one side and sky on the other queries the other side through its stored distances and moves its ray start.
- Known hole: trees are not in the SDF, so characters under trees look too bright.

## Light propagation volumes

Kaplanyan and Dachsbacher, "Cascaded Light Propagation Volumes for Real-Time Indirect Illumination", I3D 2010 ([author copy](https://cg.ivd.kit.edu/publications/p2010/CLPVFRII_Kaplanyan_2010/CLPVFRII_Kaplanyan_2010.pdf); [notes](../sources/2010_kaplanyan_cascaded_light_propagation_volumes.md)), shipped in CryENGINE 3 on PC, Xbox 360 and PS3. LPVs inject reflective-shadow-map lights into a coarse grid of low-order SH and spread the light cell to cell, computing indirect light from scratch every frame. They are the propagation member of the probe family, and the closest earlier method to RC in being both cascaded and single-frame. Section numbers are the paper's; page numbers were not printed in the copy.

**Injection (sec. 3.1, 6).**
- Each light renders a reflective shadow map (RSM) of depth (32-bit float) plus normals and flux (RGBA8 each), 256² on PC or 128² on consoles, so each texel is a virtual point light (VPL), 2^16 or 2^14 per light; environment maps inject VPLs into the outer grids.
- A VPL is a clamped-cosine lobe around its normal, projected into SH and scaled by its flux, which already accounts for the surface area it stands for; it moves half a cell along its normal before its cell is chosen, to avoid self-lighting. Two SH bands (4 coefficients) per colour channel are stored in three RGBA16F 32³ textures per grid (QUVW8, 8-bit signed per component, on consoles). VPLs are injected by point rendering with vertex texture fetch (DirectX 9 and 10, Xbox 360) or, faster on PS3, render-to-vertex-buffer.

**Geometry volume (sec. 3.2, 3.3).** A second grid holds blocking potential `B(ω) = A_s/s²·⟨n_s, ω⟩₊`, for area `A_s`, normal `n_s` and cell size `s`, from surfels taken from the camera's depth and normal buffers (down-sampled) and the RSMs, projected into SH and merged across buffers by a maximum; static surfels from earlier frames can be reused, with care not to accumulate their blocking twice. It is offset half a cell so its centres sit on LPV cell corners and is read bilinearly at each face crossed; the first step skips occlusion to avoid self-shadowing. A cell assumes its surfaces do not occlude each other, and surfaces smaller than a cell (foliage) cast no resolved shadows.

**Propagation (sec. 3.3, 6).**
- Each cell gathers from its 6 axial neighbours (4 in 2D), against 26 (8 in 2D) for an 8-direction discrete ordinates method (DOM8). For each face of the destination cell, the visibility cone's solid angle `Δω_f = ∫_Ω V(ω) dω` and central direction `ω_c` give the flux `Φ_f = Δω_f/(4π)·I(ω_c)`, taking the intensity in `ω_c` as the average over the solid angle; precomputed SH transfer vectors were rejected as too inaccurate at low order.
- The face flux is reprojected as a clamped-cosine point light at the destination centre with the same total flux, `Φ_f = ∫_Ω Φ_l⟨n_l, ω⟩₊ dω`, so `Φ_l = Φ_f/π`, and accumulated into the destination's SH; each iteration's output sums into a separate grid. Propagation conserves energy in vacuum but adds spatial and directional discretization at every step, as in all lattice methods.
- Ping-pong passes over all cells; 8 iterations sufficed in most scenes, which limits how far light travels and shows in large sparse scenes. Iterating twice the longest side would be correct and too slow.
- In flatland the scheme keeps main directions better than a 4-direction DOM, without its ray effects at higher SH orders, while an 8-direction DOM keeps the distribution best; it suits 2 to 4 SH bands and lights larger than a cell.
- Multiple bounces add a GV lookup one cell ahead, reflecting the propagated light off the approximated blocker, for about 0.3 ms on a GTX 285 (32³, 8 iterations); later bounces use monochrome reflectivity, since spectral reflectivity would triple GV memory.

**Lookup (sec. 3.4).** A trilinear SH lookup evaluated for the negative surface orientation, "similar to irradiance volumes" (citing Greger et al. 1998 and Oat 2006), with intensity turned into incident radiance by assuming the surface lies half a cell from the cell centre. Self-illumination and bleeding are reduced by damping the coefficients where their directional derivative along the normal (by differencing) is large and disagrees with them. Glossy reflections march the LPV along the reflection ray, averaging `I(−r)` over the squared distance for 4 cells, reading light before propagation smears it; participating media are single-scattered by ray marching the LPV.

**Cascades (sec. 4).** Three nested 32³ grids move with the viewer, displaced along the view direction so more of each grid lies in front of the camera, and snapped to multiples of their cell size ("one-cell grid snapping") so injection stays consistent; VPLs and geometry go into all grids, propagation runs per grid, and lookups use the finest grid holding the point, blended into the next at its border. The teaser's "50, 25 and 12.5 meters grid spacing" for a Sponza of about 37 × 15 × 22 m reads as grid extents, so cells of 1.56, 0.78 and 0.39 m and an 8-iteration reach of 12.5, 6.25 and 3.1 m (derived, inference on the meaning). Objects smaller than a grid's cell inject no VPLs there, and small moving objects are faded out because they make light unsteady.

**Results.** Per 32³ grid with 8 iterations at 1280×720 (Table 1):

| Stage (ms) | GTX 285 | Xbox 360 | PS3 |
|---|---|---|---|
| RSM rendering | 0.16 | 0.5 | 0.8 |
| VPL injection | 0.05 | 0.2 | 0.4 |
| GV injection | 0.02 | 0.15 | 0.15 |
| Propagation (no occlusion / fuzzy / fuzzy and bounces) | 0.8 / 1.1 / 1.4 | 0.8 / 1.1 / 1.5 | 0.7 / 1.1 / 1.5 |
| LPV lookup | 2.4 | 2.0 | 1.5 |
| Total | 3.4 / 3.7 / 4.0 | 3.5 / 3.8 / 4.2 | 3.4 / 3.8 / 4.2 |

Only RSM rendering depends on scene complexity, and the per-pixel lookup is 71% of the GTX 285's base total (derived). Crytek Sponza (262k triangles) with 3 cascades ran at 58 fps on a GTX 285, about 10 ms for indirect light, three grids at about 3.4 ms each (derived), plus about 18 ms for ray-marched single scattering; a 3-cascade run at 60 fps was compared against a single-bounce PBRT photon-mapping reference (200,000 photons, 1024 final-gather samples, about 45 minutes) and Imperfect Shadow Maps at 15.6 fps. One 32³ LPV ran at 130 fps without occlusion, 90 with fuzzy occlusion and 85 with bounces. Memory with ping-pong targets is `32³·(2·4)·3·(cascades + 2)` = 3.75 MB for the LPV and `32³·(2·4)·cascades` = 0.75 MB for the GV, halved on consoles.

**Limits.** Low-frequency diffuse light, mainly one bounce, with surface detail from bump mapping and SSAO; bleeding through thin geometry and missing small shadows from the coarse grid, reduced by cascades; propagation blurs, so glossy surfaces cannot use it; low RSM resolution flickers; cost is linear in iterations and cells.

**Elsewhere.** Lambru et al. implemented LPVs with these cascades and geometry volume as their discrete-ordinates class ([below](#lambrus-comparison-of-engine-gi-classes)); paniq's Shadertoy fld3R4 is a 2D LPV with circular harmonics that moves light one cell per frame ([2D Shadertoys](2d_shadertoys.md#shaders-that-are-not-rc)); CoreCascade renders plain RC, RC with the bilinear fix, LPVs and a path tracer side by side ([2D implementations](2d_implementations.md)).

## Voxel cone tracing

Crassin, Neyret, Sainz, Green and Eisemann, "Interactive Indirect Illumination Using Voxel Cone Tracing", Pacific Graphics 2011, CGF 30(7) ([notes](../sources/2011_crassin_voxel_cone_tracing.md), the GIVoxels paper; section numbers refer to the PDF). VCT voxelizes the scene into a sparse octree, prefilters light and occlusion up the mip levels, and gathers indirect light along a few wide cones per pixel by sampling the level whose voxel size matches the cone's radius. RC shares its core idea, that far light needs less spatial detail, but VCT applies it inside each cone by blurring the scene, while RC keeps exact rays and coarsens probe spacing. The octree's construction and the GigaVoxels thesis behind it are in [scene representation](scene_representation_and_tracing_voxels_and_bvhs.md#gigavoxels-sparse-voxel-octrees-with-ray-guided-streaming).

**Structure (sec. 4).**
- A sparse voxel octree with pointer-based nodes in 2×2×2 tiles, so one pointer addresses 8 children (sec. 4.1). Each node has a 3×3×3 brick with voxel centers at node corners, a vertex-centered layout that needs less than half the memory of bricks with a one-voxel border at the same sampling precision; neighbour pointers are stored.
- Construction (sec. 4.2.1) rasterizes the mesh three times along the main axes at 512² with depth testing off, one fragment thread per potential leaf. Subdivision uses atomic counters and per-node mutexes, and threads that lose a race are deferred to a later pass. It needs `NV_shader_buffer_load` and `NV_shader_buffer_store`.
- Dynamic objects (sec. 4.2.2) are rasterized each frame into a separate part of the buffer, leaving static data untouched.
- Mipmapping (sec. 4.2.3) takes `n − 1` passes for `n` levels with a 3³ Gaussian kernel (weights 1/16, 1/8, 1/4), each brick voxel weighted by the inverse of its multiplicity since brick borders are shared. Filtering runs in three passes over octants, and an add-and-copy pass per axis fixes the duplicated border voxels (Fig. 9, sec. 8.2). A mip pyramid of leaf indices lets threads that share an ancestor stop early, more than a 2× speedup (sec. 8.2).

**Voxel contents (sec. 4.3, 9).**
- Directional distributions are isotropic Gaussian lobes, the lobe width encoded in the length of the mean direction in a Toksvig-style relation; sec. 6 gives `σ² = (1 − |N|)/|N|` for the normal lobe.
- Occlusion is one average visibility value, not a density. Color and normal are premultiplied by opacity.
- Anisotropic voxels keep six values, one per major axis direction, each from a depth integration averaged over four directional values; a lookup interpolates the three of the six closest to the view direction. This fixes the leak where two walls of different colors blend into one voxel, for 1.5× the memory, since directional values are stored only above the finest level. This is the precedent for directional opacity in mipmapped RC volumes ([marching on mips](volumetric_and_radiative_transfer.md#marching-on-mips)).

**Cone tracing (sec. 5, 6, 8).**
- A cone steps along its axis and samples the mip level matching its radius with quadrilinear interpolation ([interpolation](supporting_techniques_transport_and_math.md#interpolation-and-footprints)).
- Accumulation is front-to-back emission-absorption (Max 1995): `c := c + (1 − α)·α₂·c₂` and `α := α + (1 − α)·α₂`. A step `d` that differs from the voxel size gets an opacity correction with exponent `d/d_voxel` (partly garbled in extraction).
- Ambient occlusion is `A(p) = (1/N)·Σ V_c(p, ω_i)` over `N` cones, with falloff `f(r) = 1/(1 + r)` on occlusion.
- Indirect diffuse uses about five wide cones and indirect specular one narrow cone whose aperture follows the specular exponent (sec. 8.1).
- Light injection renders a light-view map with one photon per pixel and splats it into the octree. Splatting needs 16-bit normalized textures because atomic add works only on integer types, and the duplicated brick voxels need three axis passes to resolve collisions (sec. 8.2).

**Results (sec. 10).** GTX 480 with a Core 2 Duo E6850; Sponza (280K triangles), a 9-level octree (512³ virtual resolution), 512² screen unless stated.
- 30 FPS with no specular cone and 20 FPS with one; 11.4 FPS at 1024×768 with three diffuse cones and one specular cone. The Fig. 1 caption gives 25 to 70 FPS with two bounces.
- About 1024 MB of video memory, which the paper counts among its limits (usually less than [KD10] needs for comparable quality), mostly spent on indirect specular; out-of-core caching is future work.
- A dynamic hand of 16K triangles updates in about 5.5 ms per frame. The static octree takes about 280 ms to build, and light injection and filtering about 16 ms, run only when the light moves.
- Table 1 (three diffuse cones and one 10° specular cone) extracts as 1.0, 2.0, 7.8, 14.2, 8.0 and 22.0 ms for rasterization, direct, indirect diffuse, direct plus diffuse, indirect specular and total. The combined direct-plus-diffuse pass and the specular pass give 22.2 ms, close to the total, while the three separate figures sum to 10.8 ms, so the separate columns appear to be measured apart from the combined pass (derived; the column mapping stays uncertain).
- Table 2 (AO with three cones at 512²) by cone aperture: 10° 16.6 ms, 20° 9.0 ms, 30° 6.5 ms, 60° 3.9 ms.
- Against light propagation volumes (Fig. 12): 32 ms against 37 ms, closer to the Mental Ray reference (14 min 12 s) and with less leaking.
- Limits: light leaks from the discrete geometry and irradiance resolution, and wide AO cones overestimate far occlusion (sec. 10-11).

**Measured against RC.** Kung compared screen-space RC with VCT on Sponza: VCT showed only leaks, stronger than RC's through thin objects, while RC showed leaks, flicker and dim small lights ([Kung](3d_screen_space_theses.md#kung-2025-rc-against-voxel-cone-tracing)). A world-space RC over a 256³ voxel volume cost 1.98 ms against 2.06 ms for VCT on an RTX 4090 at 1080p, quality not compared ([world-space measurements](3d_world_space.md#measurements)).

## Lambru's comparison of engine GI classes

Lambru, Morar, Moldoveanu, Asavei and Moldoveanu, "Comparative analysis of real-time global illumination techniques in current game engines", IEEE Access 9, 125158-125183, 2021 ([notes](../sources/2021_lambru_realtime_gi_game_engines_comparison.md), DOI 10.1109/ACCESS.2021.3109663, CC BY). The survey sorts rasterization-based real-time GI into four classes, implements one of each in one OpenGL 4.6 framework, and compares them on Sponza; hardware ray-traced GI is described but not implemented. Gerassimov cites it for engine GI limits ([theses](3d_screen_space_theses.md)).

| Class | Implemented technique | Notes from the implementation |
|---|---|---|
| Reflective shadow map (RSM) | Dachsbacher and Stamminger's stochastic RSM sampling, gathered at low resolution and reused per pixel where normals and positions match | one bounce only; a fixed quasi-random sample set reused every frame avoids brightness jumps; banding along light directions, because pixels on one light ray project to the same RSM texel and pick the same samples |
| Discrete ordinate method (DOM) | light propagation volumes with Kaplanyan and Dachsbacher's cascades and geometry occlusion volume, the occlusion built only from the RSM and the G-buffer | OpenGL 4.6 has no float atomics, so injection could not write RGBA32F cells; packing into one R32F left 8 bits per SH coefficient, too few, so four R32F volumes hold one coefficient each. Leaks through walls at low resolution, and more resolution needs more propagation iterations |
| Voxels | voxel cone tracing with anisotropic mips, 6 colors per voxel from the second mip level up, one shadow cone and 5 short AO cones | one color per voxel at the finest level bleeds light through thin walls lit from one side, more so at low resolution |
| Screen space | screen-space directional occlusion with SSR, screen-space shadows, Mittring's SSAO (4×4 rotated patterns, 5×5 Gaussian blur) and screen-space refraction | needs a direct-lighting pass first; small lit areas give noise at any sample count; lighting changes as the camera moves |

All four need a light intensity scale factor to reach the intended brightness, and translucent objects are left out of the RSM so it keeps the opaque surfaces that reflect light.

**Effects (Table 1).**

| Class | Indirect diffuse | Glossy | Shadows | AO | Subsurface and translucency | Volumetric | Area lights |
|---|---|---|---|---|---|---|---|
| RSM | yes | partly (1, 3) | yes | partly (1) | partly (1, 4) | yes | no |
| DOM | yes | partly (3) | no | no | partly (3, 4) | no (4) | yes |
| Voxels | yes | yes | yes | yes | yes | no (4) | yes |
| Screen space | partly (1, 2) | partly (1) | partly (1; a second mark is unreadable) | yes | partly (1, 4) | partly (5) | partly (1, 2) |

Footnotes: (1) the class partly lacks the information the effect needs; (2) temporal coherence problems in dynamic scenes; (3) no high-frequency information; (4) possible only with significant changes to the class; (5) inflexible approximations for particular cases. Voxel AO needs long cones because voxels cannot resolve short-range occlusion, so it comes out much darker than the screen-space and RSM versions. Volumetric light needs a second LPV or voxel volume holding direct rather than reflected light, doubling the expensive passes. Screen-space area lights miss emitters that face away or sit off screen.

**Performance (Table 2).** GTX 1070, Sponza (262k triangles), frame rates for indirect diffuse, shadows and AO only, read from the table image:

| Class | Setting | 1280×720 fps | 1920×1080 fps |
|---|---|---|---|
| RSM, 512² | 100 / 200 / 300 / 400 samples | 226 / 187 / 157 / 136 | 122 / 99 / 84 / 73 |
| RSM, 1024² | 100 / 200 / 300 / 400 samples | 190 / 144 / 116 / 96 | 109 / 84 / 68 / 58 |
| LPV | 32³ / 64³ | 196 / 94 | 111 / 68 |
| VCT, voxelized once | 64³ / 128³ / 256³ / 512³ | 283 / 250 / 216 / 178 | 145 / 128 / 109 / 89 |
| VCT, voxelized every frame | 64³ / 128³ / 256³ / 512³ | 214 / 214 / 170 / 74 | 138 / 121 / 96 / 52 |
| SSDO | 100 / 200 / 300 / 400 samples | 85 / 50 / 35 / 27 | 36 / 21.4 / 15.0 / 11.6 |

Higher RSM resolution costs more than its rendering time because texture-cache misses grow with the sampled texture, worse with more samples. LPV cost sits in injection and propagation, and shading costs about the same at both resolutions. Per-frame voxelization costs more than the cone-traced shading at 512³. SSDO must gather from far away to match the others and thrashes the texture cache, so it suits only fine detail. As whole-frame times with shadows and AO, at 1080p these are about 7 to 19 ms for VCT with per-frame voxelization (64³ to 512³), 9.0 and 14.7 ms for LPVs, 8.2 to 17.2 ms for RSM sampling and 28 to 86 ms for SSDO on a 2016 GPU (derived as 1000/fps); per-technique cost is not separable.

**Conclusions.** Screen-space methods give the sharpest glossy reflections and acceptable AO but fail for long-range diffuse light and flicker under motion. The RSM is flexible but one bounce, and best as the photon source for other methods. LPVs give plausible, overly bright low-frequency diffuse light cheaply. Voxels cover the most effects with the most plausible results, at the price of voxelization.

## Connections

- **One lineage, three answers to visibility.** Irradiance volumes interpolate probes blindly; light-field probes and DDGI weight each probe by a Chebyshev test on stored distance moments; RC stores visibility in each interval's transmittance and merges far light only through what nearer intervals let pass. RC still interpolates between probes at its merges and final gather, which is where the moment test returns in probe-based RC upsampling and world-space RC, as erhe's kept distance maps show ([leak defences](3d_world_space.md#leak-defences-in-world-space)) (inference).
- **DDGI is cascade 0 with full-length rays.** Its probes trace whole spheres at one angular resolution, which is the regular grid Sannikov says 3D RC improves on ([history](history_and_landscape.md)), and its cascades of volumes are DDGI grids at falling density, not RC cascades: every level keeps the same rays per probe ([Godot integration](godot_integration.md#connections) makes the same point for SDFGI) (inference).
- **History is the cheap part of probe GI.** At DDGI's default hysteresis the history is worth 66 frames of rays, and SDFGI's 30-frame average and HDDAGI's 6 to 32 slots play the same role. A probe grid without history pays for that noise in rays every frame (derived above).
- **Single-frame probe methods prefilter the scene.** VCT and LPVs compute their result in one frame, VCT by sampling prefiltered mips along cones and LPVs by propagating low-order SH through a coarse grid; both blur and leak because one value per cell stands for both sides of a surface, the failure Lambru documents for every grid class, along with over-bright results at low resolution; world-space RC grids report both (inference). RC gets a same-frame result without prefiltering the scene, by trading spatial for angular resolution with distance (inference).
- **LPVs are cascades without the trade.** CLPV nests three grids at falling resolution, as RC does, but every grid keeps the same 4 SH coefficients, so far light gets no more directions than near light. Propagation re-projects light to a cosine lobe at every cell, a full angular blur per step, and moves light one cell per iteration, so 8 iterations reach a quarter of a grid. RC's merge carries far light in one step per cascade and keeps the parent's directions where they matter (inference).
- **Mips are cones.** VCT's level-per-radius lookup is what per-cascade mip marching does in volumetric RC, and its anisotropic voxels are the directional opacity those volumes borrow ([volumetric](volumetric_and_radiative_transfer.md#marching-on-mips), [scene representation](scene_representation_and_tracing.md#connections)).
- **Practical upkeep carries over unchanged.** DDGI's relocation and probe states, Enshrouded's push-out along the SDF and dead-probe test, and Chen's backface-zero trick all deal with probes inside geometry, which erhe's RC grid failed on without relocation ([erhe](3d_world_space_implementations.md#erhe)). Enshrouded's ray sort by position and direction bin is what a direction-first RC layout gives for free, since all rays of one direction sit together ([storage layouts](cascade_layout_and_merging.md#position-first-and-direction-first)) (inference).
- **Stochastic cascade blending is dithered interval overlap.** Enshrouded's probability ramp across the overlap zone is the blend RC applies between cascades ([gaps and seams](artifacts_and_fixes.md#gaps-and-seams-between-cascades)), done by choice instead of by weight (inference).
- **The light-field probe is one dense direction set with no cascade.** A 1024² probe resolves far light at the mirror criterion at every distance; RC gets the same far-field resolution from its top cascade at a cost spread over its coarse probes, and stored hit distances and normals per texel are what RC implementations keep for bounces and depth-aware merges (inference).
- **DDGI as a light in ReSTIR mirrors RCPG.** Querying the probe cache from inside a path tracer, as a light in resampling or as a guide, is the route [RCPG and Reservoir Cascades](rc_for_sampling_and_guiding.md) take with cascades.

## Single-frame assessment

- **DDGI, its resampling variant, Enshrouded, Chen's probes, SDFGI and HDDAGI all depend on history.** Their per-frame rays (16 to 256 per probe) are sized for averaging over tens of frames, and DDGI's own convergence heuristics exist to fight the lag that history causes.
- **The same-frame members of the family are VCT and LPVs.** Both are single-frame by construction but blur and leak; VCT's light reinjection at 16 ms on 2011 hardware ran only when lights moved, a lighting cache, while its per-frame cone gather is not.
- **DDGI without history is expensive.** Matching DDGI's default noise in one frame needs about 34 M rays for a 32×8×32 grid, 23 ms of tracing at its measured rate (derived), which is why a single-frame world-space method needs RC's ray distribution rather than more rays per probe.
- **Upkeep that is geometric, not temporal, transfers.** Relocation, probe states, push-out, dead-probe tests and octahedral border handling are all scene-side and work in a single frame.
- **Visibility tests at the gather.** The Chebyshev test reads precomputed moments; in a single-frame RC those moments would have to come from the same frame's cascade-0 hit distances, which RC traces anyway (inference). Short cascade 0 intervals do not make the test unnecessary: the merged cascade 0 holds full radiance from every cascade, so a probe on the far side of a wall carries that side's light whatever `t0` is, and the leak runs along the segment from the shading point to the probe, which no interval traces. It is confined to points within one probe spacing of a wall, at the full radiance difference across it (derived).

## Open questions

