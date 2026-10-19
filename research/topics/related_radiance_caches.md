# Related radiance caches

Radiance caches store light at points on or near surfaces, found by hashing or by screen tiles, and reuse each value across pixels and frames. RC shares their problems: where to put sample points, how to key them so light does not cross walls, how to accumulate without float atomics, and what to do when a point is new. This topic covers irradiance and radiance caching, the root of the family; the hashed caches (path space filtering, SHaRC, the GI-1.0 and Solari world caches); the screen caches of GI-1.0 and kajiya; and EA SEED's surfels. Related material lives elsewhere: world-space ReSTIR in [sampling and guiding](rc_for_sampling_and_guiding.md#methods-compared-and-cited), ReSTIR itself in the [glossary](supporting_techniques.md#resampling-and-sampling-theory), on-surface texture-space caches in [surface probes](3d_surface_probes.md#on-surface-radiance-caches-tatzgern-et-al-2024), Lumen's radiance cache in [engine GI](related_engine_gi.md), and radiance caching in media in [volumetric](volumetric_and_radiative_transfer.md#radiance-caching-in-media-jarosz-et-al-2008).

| Cache | Where values live | Key or placement | Temporal reuse | Reported cost |
|---|---|---|---|---|
| [Irradiance caching](#irradiance-caching) (1988 on) | records in an octree, or splatted on screen | valid radius from distance to geometry; behind test | none, or record lifespans of 5 to 10 frames (2007) | offline; 14 s per 1000×1000 image on a 2005 GPU |
| [Path space filtering](#path-space-filtering) (2019) | hash cells over path vertices | quantized position, LOD from distance, normal | optional | |
| [SHaRC](#sharc) | hash cells, 40 bytes each | 64-bit key: position, level, normal signs | capped history | 160 MiB baseline |
| [GI-1.0](#gi-10) (AMD) | screen probes plus a hashed world cache | 8×8 tiles; position, direction, LOD and a ray-length bit | reprojection and blending | 1.9 to 3.1 ms at 1080p |
| [kajiya](#kajiya) | 12 sparse clipmaps of 32³ cells | cells placed by where they are queried | reservoirs and SH history | 8.4 ms frame at 1080p |
| [Bevy Solari](#bevy-solari) | hashed world cache | position, normal, LOD | `1/n` blend, one bounce per frame | under 0.2 ms for the cache |
| [GIBS](#gibs-and-pica-pica-surfels) (EA SEED) | surfels spawned from the G-buffer | 16×16 tile coverage | adaptive moving average | 3.4 to 11.3 ms on PS5 |

## Contents

- [Irradiance caching](#irradiance-caching)
  - [Ward's rule](#wards-rule)
  - [Radiance's practice](#radiances-practice)
  - [Fixes from production](#fixes-from-production)
  - [Radiance caching](#radiance-caching)
  - [Splatting and time](#splatting-and-time)
- [Path space filtering](#path-space-filtering)
- [SHaRC](#sharc)
- [GI-1.0](#gi-10)
- [kajiya](#kajiya)
- [Bevy Solari](#bevy-solari)
- [GIBS and PICA PICA surfels](#gibs-and-pica-pica-surfels)
  - [PICA PICA (Ray Tracing Gems chapter 25)](#pica-pica-ray-tracing-gems-chapter-25)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)
- [Open questions](#open-questions)

## Irradiance caching

Ward, Rubinstein and Clear's "A Ray Tracing Solution for Diffuse Interreflection" (SIGGRAPH 1988) computes indirect diffuse light at sparse records and interpolates between them, and every cache in this topic descends from it. Ward and Heckbert added gradients in 1992, Tabellion and Lamorlette took it into film production at PDI/DreamWorks in 2004, Křivánek et al. extended it to glossy surfaces as radiance caching (2005, 2006), and Gautron et al. moved it to the GPU (2005) and through time (2007). The formulas come from the SIGGRAPH 2008 class "Practical Global Illumination with Irradiance Caching" ([course page](https://cgg.mff.cuni.cz/~jaroslav/papers/2008-irradiance_caching_class/)), and the current rules from Radiance's source ([notes](../sources/2008_ward_krivanek_irradiance_caching.md)). Jarosz et al.'s volumetric member of the family is in [volumetric](volumetric_and_radiative_transfer.md#radiance-caching-in-media-jarosz-et-al-2008).

### Ward's rule

- **Lazy evaluation.** A query near enough records interpolates or extrapolates from them; otherwise it samples its hemisphere and adds a record. Ward called it lazy evaluation; the name "irradiance caching" came from someone else. Radiance implemented it around 1986, in about 1,500 of its 30,000 lines, after a SIGGRAPH rejection and two rewrites.
- **Hemisphere sampling** is stratified over altitude and azimuth, with divisions of equal projected area (the Nusselt analog). Samples that hit light sources count as zero, since direct light is separate, and deeper bounces use fewer samples, filling the deepest cache level first. Radiance's controls are `-ab` bounces, `-ad` and `-as` samples per hemisphere, `-aa` accuracy and `-ar` spatial resolution.
- **Split sphere.** The assumed "pretty bad case" (not a strict worst case) is a point at the centre of a sphere half light and half dark, looking at the break. Bounding its partial derivatives gives `ε ≤ (4E/(πR))·|x − x₀| + E·|ξ − ξ₀|` and, for reusing a record at `P₀` from `P`, `ε(P) ≤ (4/π)·E·|P − P₀|/R₀ + E·sqrt(2 − 2·N(P)·N(P₀))`, where `R₀` is the harmonic mean of the hemisphere rays' lengths (a harmonic mean because the radius sits in a denominator; zero lengths are forbidden), which the slide labels "average distance to surfaces".
- **Weight:** dropping constants, `w_i(P) = 1/(|P − P_i|/R_i + sqrt(1 − N(P)·N(P_i)))`, and `E(P) = Σ w_i·E_i/Σ w_i` over records with `w_i > 1/a`, `a` being the error tolerance. With equal normals a record reaches `a·R_i`. Weights track 1/error, so the average spreads error evenly.
- **Behind test:** a record is used only if `(P − P_i)·(N(P) + N(P_i))/2 ≥ 0`, which rejects a point below a step that the record's radius would otherwise cover.
- **Storage:** an octree independent of the surfaces, each node listing records whose radius is less than its width. A record holds `pos[3]`, `dir[3]` (the normal), `lvl` and `weight` (the parent ray's recursion level and weight), `rad` (valid radius), `val` (colour), and `gpos[3]` and `gdir[3]` (gradients with respect to position and direction), 18 numbers or 72 bytes (derived). Level and weight decide when to truncate the ray tree. The octree even works for volume data, "sort of".
- **Gradients** (Ward and Heckbert 1992) come almost free from the same samples. Rotational: the surface sees more or less of a bright object as its normal turns, zero at the zenith because the cosine's derivative is zero there; what lies over the horizon cannot be known. Translational: motion exposes or hides objects, with disocclusions assumed to look like the visible background, so boundaries move with the nearer edge. Interpolation becomes `E(P) = Σ w_i·[E_i + (n̂_i × n̂)·∇_r E_i + (P − P_i)·∇_t E_i]/Σ w_i`. Gradients were first meant to set spacing; a year later using them in interpolation proved better, since it reduces discontinuities and avoids bias, and they also cap the radius.
- Records space out on flat open surfaces and bunch up on outside curves and especially inside corners.

### Radiance's practice

- An "ambient constant" stands in for the rest of the bounce series, estimated as a moving average of top-level values (`-aw`); over-estimating it is worse than under-estimating, and in practice it is little used. Adaptive super-sampling (`-as`) samples high-variance hemisphere regions until the error is uniform or a limit is reached, and helps most in daylit interiors.
- A minimum spacing stops corners resolving to single pixels; a maximum of 64 times the minimum "seems about right". Pixel size could set spacing instead, at the cost of view independence. The gradient caps spacing only when `‖∇‖·R > 1`, cutting `R` to `1/‖∇‖` to avoid negative values, and at the minimum spacing the gradient is reduced instead; the gradient should not set spacing in general because it is unknown before sampling, and a conservative geometric rule is safer.
- Bump maps apply the rotational gradient with the perturbed normal at the final interpolation, so bumps neither reduce sharing nor leak. Materials can be excluded from interreflection (grass fields save hours). Processes share records through cache files with lock, read, write and unlock, with a buffer of about 13 records for up to about 10 processors, though the NFS lock manager is not always reliable; records are sorted by recency at growing intervals for memory coherence, which turns off once more than a third of records are shared.
- Limits: values cached across very different scales leak if spacing is not limited, and "hairy" geometry such as forests and grass is better left to path tracing. Bias comes from naive adaptive super-sampling, bounce truncation (caching overrides Russian roulette), spacing limits and an assumed average reflectance. Scaling sample counts by reflectance and spacing by reflectance^−0.5 distributes errors.
- **Today's code** replaces the 1988 weight: valid radii are anisotropic, `sqrt(sqrt(4/λ))` along each eigenvector of a radiometric Hessian (Schwarzhaupt, Jensen and Jarosz, "Practical Hessian-Based Error Control for Irradiance Caching", SIGGRAPH Asia 2012), clamped between the minimum and maximum, falling back to a geometric Hessian; `sumambient` uses a record if its normal is within 10° plus `ambacc` radians (relaxed for low-weight rays), it passes a modified behind test, its elliptical distance with the two radii and the offset along the normal is under `ambacc`, and, for records with a "corral", it passes the leak test `plugaleak`; the weight is the product of two linear ramps in angle and distance (`ambient.c`, `ambcomp.c`).

### Fixes from production

Křivánek's implementation and Tabellion and Lamorlette's production system (as summarized in the 2008 course; the production details in their own course talk were not read):

- **Neighbour clamping** (Křivánek et al., EGSR 2006). Rays that miss small features or leak through cracks overestimate `R` and spread a wrong value widely. On adding record `j`, each record `k` with `‖p_j − p_k‖ < R_j + R_k` clamps `R_j = min(R_j, R_k + ‖p_j − p_k‖)`, then `R_k = min(R_k, R_j + ‖p_j − p_k‖)`, enforcing the triangle inequality. Spacing then falls off smoothly from features (7,761 records at `a = 0.15` without it against 7,752 at `a = 0.35` with it; Sponza 9,638 against 9,416); it cannot fix a leaked record's own value.
- **Spacing in pixels.** A world-space minimum (Radiance gives it as a fraction of scene size) leaves records too sparse near the camera and too dense far away; Tabellion and Lamorlette use 1.5 to 3 projected pixels for `R_min` and 10 for `R_max`. They also use the minimum ray length instead of the harmonic mean, which catches small features: without neighbour clamping or a gradient limit the minimum looks much better (mean at `a = 0.07` against minimum at `a = 0.5`, both 14k records); with neighbour clamping, the mean works.
- **Insertion order of operations:** sample; `R = min(R, 1/‖∇_t‖)`; `R' = max(min(R, R_max), R_min)`; if `R < R'`, scale the gradient by `R/R'`; neighbour-clamp with the unclamped `R`, redoing it whenever `R` shrinks, so each record stores `R`, `R'`, `R_min` and `R_max`; insert. Translational gradients explode in corners and are clamped.
- **Two passes.** A new record never reaches pixels already shaded, so one scanline pass leaves seams. Filling the cache first in best-candidate order (6,043 records, against 6,167 hierarchical and 7,395 scanline) and then rendering removes them, and raising `a` 1.8 times in the second pass (for example 0.25 to 0.45) smooths results from as few as 400 rays per hemisphere, at the cost of some detail.
- **Bounded weights.** Ward's weight is infinite at the record and cut off at the border (Radiance randomizes acceptance to hide the seam). Tabellion and Lamorlette's `w = 1 − 2a·max(‖p − p_i‖/R_i, 4·sqrt(1 − n·n_i))` and Gautron's `w = 1/(‖p − p_i‖/R_i + sqrt(1 − n·n_i)) − 1/a` both reach zero at the border.
- An octree that references a record from every node it overlaps (as in PBRT) makes lookup one root-to-leaf walk, at more memory and slower insertion. Reusing the last query's result within a supersampled pixel (same pixel and shader, distance under a projected pixel, normals' dot above 0.95) costs almost nothing, and production images make tens of millions of queries. Glossy terms are left out of hemisphere sampling because they corrupt translational gradients, and with motion blur in a ray tracer hits are reprojected to `t = 0` before the query.

### Radiance caching

Křivánek, Gautron, Pattanaik and Bouatouch (IEEE TVCG 2005) store incoming radiance per record as (hemi)spherical harmonic coefficients in the record's local frame, with a translational gradient per coefficient along the two tangent axes only, since motion along the normal is small in interpolation. Interpolation applies the gradients, then rotates the coefficients into the query's frame, the method's bottleneck, which needs an optimized routine. Outgoing radiance is the dot product with precomputed BRDF-times-cosine coefficients, tabulated per outgoing direction in a parabolic map (about a minute per BRDF) and looked up from a texture. Surfaces are chosen by BRDF roughness: it suits low-frequency glossy BRDFs and complements importance-sampled Monte Carlo, which is left the sharp reflections and complex geometry; at equal time it is smooth where Monte Carlo is noisy. Glossy indirect light depends on lighting, BRDF sharpness and view, so a geometric spacing rule fails more often than for irradiance. The adaptive version (EGSR 2006) gives each record its own `a_i` and shrinks it when contributing records differ by more than a Weber-law threshold of 2 to 3% of luminance, so density follows lighting and BRDF sharpness instead of geometry alone.

### Splatting and time

- **Irradiance splatting** (Gautron et al. 2005) inverts the lookup: each record is drawn as a screen quad over the projection of its sphere of radius `a·R_k`, and a fragment shader evaluates the weight from the G-buffer and blends `w·ρ·E_k` and `w` into a float buffer that a last pass normalizes before adding direct light. The shader rejects early on `‖p − p_k‖²/R_k² + 0.2·(1 − n·n_k) > a²`, then computes `1/w = sqrt(e1) + sqrt(e2)` clamped from below, and adds the gradient terms per colour channel. Every record reaches every pixel it covers, so one pass in any order matches the octree method's two. Subtracting `1/a` from the weight removes circular seams with few records. New records rasterize the scene from the record through one camera of about 126° with border pixels stretched to grazing angles (RMS error over 10,000 values in Sibenik 5.8%, against 10.4% for plain plane sampling and 18.1% for Larsen and Christensen's coverage scaling), lit with view-independent uniform shadow maps (1024², 16-sample PCF) the final image reuses; cache misses are found on the CPU by walking the splat buffer. A record is about 22 floats, 88 bytes: irradiance, rotational and translational gradients per channel, and the harmonic mean distance; reading back and summing on the CPU beat GPU mipmap summation. On a Quadro FX 3400 and a 3.6 GHz Pentium 4, with 64×64 hemisphere rasterization, this rendered Sibenik (80K triangles, `a = 0.15`, 4,076 records) and Sponza (66K triangles, `a = 0.1`, 4,123 records) at 1000×1000 in 14.3 s and 13.71 s against Radiance's 425 s and 645 s, 30 and 47 times faster (ratios derived), with splatting itself 188 and 242.5 ms. Records are view-independent, so static scenes fill the cache progressively during walkthroughs.
- **Temporal radiance caching** (Gautron et al. 2007) states why per-frame caches flicker: rebuilding the cache each frame moves the records, and since extrapolation is most accurate at a record, the pattern of error moves with them. It fixes record positions over time, gives each a lifespan from its change rate `τ = E₁/E₀` (for radiance, the largest ratio over the projection coefficients; weight `1/((τ − 1)(t − t₀))` against `1/a_t`, capped at an ad hoc `t_max` of 5 to 10 frames, which a static neighbourhood needs because `τ = 1` gives an infinite lifespan), replaces expired records in place, and adds temporal gradients, the change of irradiance and of its spatial gradients over time, which extrapolate in one pass or interpolate in two between a record's estimates and suppress the remaining flicker; the method assumes the animation is known in advance. Speedups reach 9 times; with a moving light flicker goes but the speedup is 1.25 times.

## Path space filtering

Binder, Fricke and Keller, "Massively Parallel Path Space Filtering", 2019 ([arXiv 1902.05942](https://arxiv.org/abs/1902.05942); [notes](../sources/2019_binder_path_space_filtering_and_sharc.md)). It is the hashing scheme SHaRC, the GI-1.0 world cache, Solari's world cache and Split RC's probe maps descend from; with SHaRC it gives tested parameters for slot layout, LOD, fixed-point atomics and eviction.

- Each path vertex gets a key from a quantized descriptor, and vertices with the same key share one average. One hash lookup replaces a neighbour search, and no motion vectors are needed.
- Voxel size grows with distance from the camera, most easily as a multiple of the projected pixel size.
- The normal in the key stops smearing across edges; glossy surfaces add the incident angle, and mirrors should not be filtered.
- Positions are jittered in the tangent plane before quantizing, which trades block artifacts for noise that is easier to filter.
- Key build: `l = lod(|cam − x|)`, `x' = x + jitter(n)·s·2^l`, `l' = lod(|cam − x'|)`, cell `floor(x'/(s·2^l'))`; index `hash(cell)`, fingerprint `hash2(cell, n)` (32 bits). Collisions use capped linear probing, and on overflow the vertex keeps its own unfiltered value.
- Each vertex atomically adds its value and increments a counter. A moving average does not converge in cells with few samples; `α = N_old/(N_old + N_new)` does, but only while the scene is static, so the paper blends the two with a finite-difference change test.
- Eviction can use one `atomicMin` when the fingerprint's high bits hold a priority (count and age).
- Leaks are the price: averaging across a voxel always risks light and shadow leaking.

## SHaRC

NVIDIA's Spatially Hashed Radiance Cache, versions 2023 to 2026 (v1.8.3), [github.com/NVIDIA-RTX/SHARC](https://github.com/NVIDIA-RTX/SHARC); its licence forbids use without an NVIDIA agreement.

**Passes.** An update traces a sparse subset of paths (for example one random pixel per 5×5 block, about 4%, which is 82,944 paths at 1080p, derived) and adds each vertex's radiance into its cell and into the earlier vertices of the path. A resolve, one thread per entry, blends this frame's sums into the stored value and evicts stale entries. A query at a hit reads the cell's radiance instead of tracing further. Each pass needs a storage barrier before the next touches the cache.

**Hash grid.**
- The default 64-bit key has 17 bits per axis of quantized position, 9 bits of level, 3 normal sign bits and one spare bit; a compact 32-bit key uses 8 bits per axis.
- Level from distance: `level = clamp(0.5·log_b(dist²) + bias, 1, 511)` with base 2, voxel size `b^(level − bias)/sceneScale`, position `floor((p + 1e−4)/voxelSize)`.
- The slot is `Jenkins32(lo) ^ Jenkins32(hi)` modulo `capacity − 15`, then a 16-slot bucket probed linearly without wrapping ([hashing](supporting_techniques_structures_and_tracing.md#gpu-hash-tables)). Key 0 marks an empty slot. Insertion uses a 64-bit atomic compare-exchange, or a lock buffer where 64-bit atomics are missing, as in Godot ([atomics](../../docs/rendering_device.md#atomics)).
- An entry is 8 bytes of key, 16 bytes of accumulation (`uint` RGB sums and a count) and 16 bytes of resolved data (half RGB, count, age), 40 bytes. The baseline of 2²² entries is 160 MiB, and a static camera uses about 10 to 20% of them, 16 to 32 MiB (derived).

**Accumulation and resolve.**
- Radiance is added as `uint(radiance·weight·scale)` with integer atomic adds (`InterlockedAdd`), `scale` starting at 1000 and lowered for bright scenes to avoid overflow, the same portable approach Split RC uses.
- An entry with no samples for `staleFrameNumMax` frames (at least 8) is evicted.
- The blend is `rad = (prev·Nprev + cur·Ncur)/(Nprev + Ncur)`, with `Nprev` rescaled so history covers at most `accumulationFrameNum` frames.
- A new entry after camera motion borrows history from the same cell one level coarser or finer, so LOD changes do not reset lighting.
- An optional directional mode stores luma as L1 SH (YCoCg) to keep glossy light from leaking into other directions.

**Query rules.** Skip the cache at the primary hit. Use it only when the path segment is longer than the voxel, or the glossy lobe's spread `2·len·sqrt(0.5a²/(1 − a²))` exceeds it; otherwise keep tracing.

## GI-1.0

Boissé, Meunier, de Dinechin, Oliver, Bartels, Veselov, Eto and Harada (AMD), "GI-1.0: A Fast and Scalable Two-Level Radiance Caching Scheme for Real-Time Global Illumination", technical report 2022, [arXiv 2310.19855](https://arxiv.org/abs/2310.19855), with code in [AMD Capsaicin](https://github.com/GPUOpen-LibrariesAndSDKs/Capsaicin) ([notes](../sources/2023_boisse_gi10_two_level_radiance_cache.md)). The Split RC paper cites it with Lumen as a screen-space radiance cache. It uses hardware ray tracing at a quarter sample per pixel at 1080p with no precomputation, and it solves what any screen-probe RC meets: placing probes on visible surfaces, reusing them across frames, filling holes and avoiding leaks.

**Screen cache.**
- One probe per 8×8 tile at a random pixel in the tile, storing 8×8 octahedral incoming radiance over its hemisphere with hit distance in alpha, and projected to 3-band SH for interpolation.
- New probes spawn over several frames: a Halton jitter picks one pixel per enlarged spawn tile, so a quarter of probes are new each frame.
- **Reprojection:** a pixel may reuse last frame's probe if `|dot(probe_pos − pixel_pos, n)| < cell_size` and the normals' dot product exceeds 0.95. The closest valid probe wins through an atomic min on `half(distance) << 16 | lane`.
- **Holes keep a fixed budget:** tiles that failed to reproject take rays from newly spawned tiles that did reproject, instead of adding rays.
- **Ray guiding:** a CDF over the reprojected probe's cell luminance, built by a parallel scan in shared memory, picks ray directions; reprojected radiance is scattered into the new probe's cells after parallax correction from stored hit distance.
- **Blend:** a plain moving average lost detail because a cell covers a large solid angle. The shadow-preserving hysteresis keeps the older value when the new one is brighter in the way fireflies are: `l1 = luma(cur)`, `l2 = luma(prev)`, `a = max(l1 − l2 − min(l1, l2), 0)/max(max(l1, l2), 1e−4)`, `a = clamp(a, 0, 0.95)²`, result `lerp(cur, prev, a)`. It keeps shadows at the cost of some darkening and filters fireflies smaller than a cell.
- **Finding probes:** a mip chain of the probe mask keeps the first valid probe of each 2×2, so a pixel walks up the mips to the nearest probe in a direction.
- **Filtering:** a separable 7×7 sparse blur in probe space that rejects taps by plane distance, normal sign and the angle between a direction and the tap's hit point (`cos(π/50)`), which keeps small occlusion detail.
- `cell_size` grows with distance: `tan(fov_y·8·max(1/h, h/w²))·distance`, where 8 is the probe spacing in pixels.
- **Thin geometry:** probes that fail reuse go into a persistent LRU side cache with world position and normal, found again by splatting into screen tiles, which stops lighting on thin features from wobbling.

**World cache.**
- Outgoing radiance at secondary hits, keyed by quantized position, quantized direction and a LOD that grows with camera distance, after path space filtering. Two hashes give the bucket and a fingerprint, with linear probing in the bucket, and cells decay when not touched.
- **Leak fix:** a dark enclosed hit and a bright outside hit can share a cell when the secondary ray is shorter than the cell. Adding the bit `ray_length < cell_size` to the key separates them.
- Cells are grouped into 8×8 2D tiles that drop the dominant direction axis, with mips rebuilt each frame; queries read the finest mip with enough samples.
- **Temporal radiance feedback:** a hit visible last frame reads last frame's lit result instead of evaluating lights, which gives unlimited bounces for free over frames for surfaces that were on screen; the paper names indoor scenes as the weak case.
- Direct light uses world-space ReSTIR reservoirs in a hash grid with a light grid of the most important lights per cell.

**Gather and timings.** Per pixel, find a probe in four directions, weight by depth and normal, and fall back to equal weights (flagged for the denoiser) when all are rejected. Irradiance is the SH dotted with the cosine lobe. Screen-space horizon AO and short-range GI fill in detail smaller than the probe spacing through a bent-cone mask. The total at 1080p is 1.9 to 3.1 ms on an RX 6900 XT, and similar on an RTX 3080, for scenes of 99k to 9M triangles; in a UE5 scene GI-1.0 took 2.4 ms against Lumen's 2.6 ms.

**Capsaicin code.**
- Screen probes are 8×8 hemi-octahedral with 64 rays each and 9 SH coefficients, spawned once per 16×16 spawn tile. One new probe per 256 pixels with 64 rays is exactly the quarter sample per pixel the paper states (derived). Radiance reuse requires directions to agree within `cos(0.02π)`, and cell values are quantized by 10⁴ for integer atomics.
- The screen cell size uses `tan(fov_y·8·max(1/h, h/w²))`; the world hash grid uses the same form with 32 in place of 8 (4× coarser) and a minimum cell of 0.1. It stores 8×8 tiles with mips (8, 4, 2 and 1, so 85 cells per tile) in 65,536 tiles with 4-way buckets, 5.57 M cells in all (derived), decays untouched tiles after 50 frames, and blends counts with `lerp(old, new, 1/min(n_old + n_new, 16))`.
- The probe filter has radius 3 with weights raised to the 8th power. World-space ReSTIR uses 2^18 cells of 16 entries and 8 samples. Multi-bounce paths are discarded with probability 0.7 and survivors scaled by `1/(1 − 0.7)`.
- A frame runs about 25 passes: purge the radiance cache, reproject, look up, spawn, patch and sample screen probes, populate cells, generate, compact and resample reservoirs, populate, update and resolve the cache, blend, reorder, filter, project and interpolate screen probes, reflections, then reproject, filter and resolve GI.
- Direct lighting is on by default, though a comment says it is off.

## kajiya

Tomasz Stachowiak's (h3r2tic, later a developer of Tiny Glade) research renderer, with its 2022 GI design document ([gi-overview.md](https://github.com/h3r2tic/kajiya/blob/main/docs/gi-overview.md); code Apache-2.0, Rust and HLSL; [notes](../sources/2022_stachowiak_kajiya_gi.md)): half-resolution ReSTIR GI for the first bounce and a sparse world irradiance cache for the rest. It needs hardware ray tracing, so none of it runs as-is on a compute-only host such as Godot's `RenderingDevice`. HDDAGI's screen-probe draft names it as one of its two models ([Godot integration](godot_integration.md#screen-probes-in-122999)).

**Cost.** 1920×1080 on an RX 6800 XT, 8.4 ms in all: G-buffer 1.15 ms, indirect diffuse about 2.3 ms, irradiance cache about 0.55 ms, reflections about 2.2 ms, sun shadows 0.52 ms, SSAO 0.17 ms, sky 0.1 ms. The cache usually holds fewer than 16k entries, which trace 128k G-buffer rays and 384k shadow rays per frame, exactly 8 and 24 rays per entry, the documented per-entry budget below (derived).

**Irradiance cache.**
- 12 camera-aligned clipmaps of 32³ cells, allocated sparsely: a dense 32×32×32×12 indirection array points into payload buffers of up to 65,536 entries, allocated on first use and freed a few frames after their last.
- Only rays query it: a diffuse or reflection ray asks it for the remaining bounces at its hit. Hits visible on screen reproject last frame's result instead and never touch the cache.
- **Output-sensitive trace origins:** a cell has no fixed probe point. Each query location is a candidate, and every frame one candidate per cell is picked at random to trace from. With the camera inside a building the queries come from inside, so the cell lights the inside; this is what keeps thin sunlit walls from leaking, a case where any cache with a fixed point runs out of resolution.
- **Ranking:** each entry stores the lowest bounce index that reached it (1 for rays from the screen, 2 for rays from a rank-1 entry, and so on), and a new vote counts only if its rank is lower or equal, so the cache's own rays cannot let outside cells vote for outside positions. This removed leaks into a torch-lit room inside repeated Sun Temple scenes.
- **Normal bias:** the lookup moves along the normal, so the underside of a table lit from above stays dark more often.
- Each entry keeps temporal reservoirs stratified over a 4×4 octahedral map; 4 texels make new candidates per frame, lit by the sun and by the cache itself (single-buffered, races accepted), plus 4 validation rays and 16 short accessibility rays. A compute pass turns them into L1 SH irradiance.
- The cache is blocky and not temporally stable, which shows where reflections read it directly; stochastic interpolation between entries reduced this.

**Indirect diffuse.**
- One pixel per 2×2 tile traces a ray each frame from its G-buffer position, with a hemispherical (not cosine) distribution. A hit visible on screen reprojects last frame's irradiance; other hits are lit from the ray payload.
- Results feed ReSTIR reservoirs at half resolution: temporal reuse with `M` clamped to 10 (the code clamps `M` to 20 and the weight `W` to 10), permutation sampling, then two spatial passes (radius 12 to 32 pixels with 8 samples, then 6 to 16 with 5), shrinking as reservoirs fill and in corners by SSAO. The last pass marches up to 6 half-resolution depth taps toward each neighbour's hit for a rough contact shadow.
- **Near and far split:** spatial reuse erodes small-scale bounce in corners, which are not a large source of variance anyway, so the resolve takes near hits from the raw rays traced that frame and far hits from the reservoirs, blended by a threshold that grows with distance from the camera. This recovered the corner detail.
- **Validation:** every third frame retraces all reservoir samples instead of generating new ones; a sample whose radiance changed has its `M` cut, and one that hits the same point has its radiance updated, growing at most 10× to avoid fireflies. Validation frames also trace short rays so the near field stays filled.
- A 4-sample resolve to full resolution, a temporal filter with color box clamping, and TAA follow.

**Lessons it states.** Small bright emitters defeat ReSTIR's reuse and are better treated as explicit lights, the advice RC sources give for emitters smaller than cascade 0's spacing. Newly disoccluded areas are noisy until reservoirs refill. SSAO only guides filter radii and bilateral weights and never darkens lighting.

**Code values.**
- The cache's base cell is 0.02 m, doubling per clipmap, each centered at `floor(eye/d) − 16` cells; 32 cells of 0.02 to 40.96 m give clipmap extents from 0.64 m to about 1.3 km (derived). Entries live 4 frames per rank over 3 ranks before aging recycles them. An entry holds L1 SH with basis `(0.282095, 0.488603·dir)` and 16 octahedral texels (4×4), 4 updated per frame with blend 0.25; traced reservoirs clamp `M` at 30.
- A lookup takes one entry with a stochastic jitter capped at `min(distance/2, cell diameter)`, and position votes are accepted with probability `1/(n + 1)`.
- Ray budget: per cache entry 4 G-buffer and 4 shadow rays for the main trace, 4 and 4 more for validation, and 16 accessibility rays; per pixel 1 sun shadow ray, 0.25 to 0.5 final-gather rays and 0.25 reflection rays.
- ReSTIR GI validates every third frame with permutation sampling. The spatial passes use 8 then 5 samples, radii 32 to 12 and 16 to 6 pixels (8 in later passes), and clamp `M` at 500; the temporal resolve takes 5 samples, with permutation while `M_sum < 1.25·20`. Reservoirs are half-resolution `R32G32_UINT` with packed f16 `M` and `W`.

## Bevy Solari

JMS55's post on Bevy 0.17's hardware ray-traced lighting, 2025-09-20 ([post](https://jms55.github.io/posts/2025-09-20-solari-bevy-0-17/); [notes](../sources/2025_jms55_bevy_solari.md)). Solari started in 2023 with Lumen-style screen probes, moved to radiance cascades, and was shelved and rebuilt on ReSTIR with DLSS Ray Reconstruction. The post says screen probes were hard to make look good because one probe is reused and reprojected across many pixels, and that RC "brought their own artifacts and performance costs", with no details ([history](history_and_landscape.md)).

**World cache.**
- Cells are found by hashing the quantized world position (`floor(p/cell + 0.0001)`), the quantized geometric normal (`floor(n + 0.0001)`) and a LOD that grows cells with distance. A PCG hash chain gives the slot and a second hash a checksum; on a mismatch the lookup rehashes to another slot a bounded number of times. Hashing was picked over clipmaps, cards or bricks because it needs no build step, adapts to geometry and leaks little.
- A query of a live cell returns its irradiance and resets its lifetime; a query of an empty slot claims it and returns zero, and the cell starts updating next frame. Every cell's life drops by 1 per frame, and it is freed at 0.
- A prefix sum compacts live cells into a list with indirect dispatch arguments.
- Each live cell traces two rays per frame: one light sample chosen by RIS, and one cosine-hemisphere ray that reads the cache at its hit times the hit's albedo. Light spreads one bounce per frame.
- The blend keeps `min(n + 1, max)` samples in alpha and sets `mix(old, new, 1/n)`, in its own dispatch so cells that read each other do not race.
- The cache "significantly improved quality" and halved the cost of initial GI samples.

**Problems.** A cell's position and normal are fixed at creation, so a bad first sample stays. The cache seems to lose energy: ending paths at a random light instead of the cache was brighter despite more noise. Bright outlier cells flicker, and with no validation rays the recursive cache leaves trails behind moving lights.

**ReSTIR settings.** Neighbours are rejected at a tangent-plane distance over view depth above 0.003 or a normal dot below 0.906 (25°). DI uses 32 light candidates by RIS, one visibility ray, temporal reuse without re-tracing visibility and one spatial sample in a 30 px disk; one spatial sample beat more, and subgroup or workgroup resampling caused tiling or broke the denoiser. GI traces one uniform hemisphere ray per pixel and reads the world cache at the hit; temporal reuse jitters the reprojected position a few pixels to break correlation. The Jacobian for reusing neighbours' samples is the hardest part: neighbours with a Jacobian above 2 are rejected, and it still overflows if left for minutes.

**Timings.** RTX 3080, 1600×900 upscaled to 3200×1800 with DLSS-RR: PICA PICA 8.2 ms, Bistro 14.5 ms, Cornell box 8.3 ms, of which DLSS-RR alone takes 5.8 to 6.3 ms. The post does not pair each figure with a scene, so its share lies between 40% and 77% of the frame (derived). The world cache costs under 0.2 ms except its lighting pass in Bistro (2.1 ms). The main passes are memory bound or limited by ray-tracing throughput.

## GIBS and PICA PICA surfels

EA SEED's Global Illumination based on Surfels, a surfel GI talk and not RC (Halén, Brinck, Hayward and Bei, SIGGRAPH 2021; [slides](https://media.contentapi.ea.com/content/dam/ea/seed/presentations/seed-siggraph21-surfel-gi.pdf), 211 pages; [talk](https://youtu.be/h1ocYFrtsM4), 47:39, given by Henrik Halén) and its predecessor in PICA PICA (Barré-Brisebois et al., Ray Tracing Gems chapter 25, 2019) ([notes](../sources/2021_seed_gibs_surfel_gi.md)). GIBS computes indirect diffuse with hardware ray tracing on surfels, small oriented discs spawned from the G-buffer, with no precomputation, special meshes or UVs, and ships in Frostbite; it began in 2018 in PICA PICA, and the talk calls it still in development (00:44-01:47). Surfel RC takes its spawning, stack allocation and transform-ID plan from it ([surfel RC](3d_surface_probes.md#surfel-radiance-cascades-src-dgi)). Page numbers are PDF pages of the slides and printed pages of the chapter.

**Surfels and spawning.**
- A surfel has a position, radius and normal (p. 13).
- The screen is split into 16×16 texel tiles. Each tile finds its least-covered texel and spawns a surfel from the G-buffer position and normal if the coverage passes a randomized threshold, and stops once it reaches its coverage target (pp. 14-17).
- Surfels are scaled to keep their projected size about constant, so count and radius follow distance (p. 23).
- The G-buffer writes a per-geometry transform ID. A surfel stores its position in that transform's local space and is moved each frame from a global transform buffer that includes skinned bones; skinned meshes write only the highest-weight bone, so surfels slip in some cases, which the lighting tolerates (pp. 18-20).

**Pool and recycling.** All surfel memory is allocated up front, and a GPU stack of free indices with an atomic counter serves allocation: spawning pops, recycling pushes (pp. 26-29). The recycle decision combines the live count, frames since the surfel last contributed and its distance, and is compared with a uniform random number, so less relevant surfels are likelier to go.

**Acceleration structure.** PICA PICA used a uniform grid with each surfel inserted into its own cell and every neighbour its radius overlaps, radius at most one cell side (pp. 30-33). The shipped structure is a uniform grid at the center plus a trapezoidal grid along each principal axis whose slices thicken with distance (pp. 36-38): lookups and inserts stay as cheap as a regular grid's, and surfels per screen area stay about constant.

**Gather and leaks.** A pixel reconstructs its world position, finds its cell, reads the first N surfels (N not given) and accumulates irradiance weighted by normal and distance, adding the cell's weighted average irradiance if the total weight is below 1 (p. 40). Each surfel keeps a radial depth function of 4×4 texels per hemisphere, initialized to its diameter; rays that hit within the diameter update a moving average of depth and squared depth, and a Chebyshev bound gives a smooth visibility test, as in variance shadow maps and DDGI ([related probe GI](related_probe_gi.md#ddgi)) (pp. 41-58).

**Rays, integration and guiding.**
- Content sets a total ray budget. Each surfel requests rays from its frames since last contributing (more when active), its variance (more when high) and a bonus when new; dormant surfels send just enough rays to notice change. A count pass sums requests into a global counter and a binning pass gives each surfel a proportional share (pp. 60, 75-79).
- Irradiance integrates with a modified moving average whose blend factor follows short-term mean and variance estimates, so it reacts fast to change and converges in static scenes. High variance also triggers irradiance sharing between neighbouring surfels (pp. 53, 75-76, 117-122).
- Ray guiding maps each surfel's hemisphere to a 6×6 radiance map at 8 bits per component plus one 16-bit scale per surfel, normalized after each update, sampled by inverse CDF over all 36 texels. A Müller-style quadtree inspired it but was not built. Guiding helps when much light enters through large openings (pp. 83-110).
- Rays are sorted by a bin built from the surfel's cell coordinate flattened to 1D as a spatial hash, plus the ray direction, with two counting passes and a reorder pass in the Battlefield V style (p. 123).

**Many lights and transparency.** The stress scene has 1400 lights in view. Stochastic lightcuts (Yuksel, HPG 2019) sort lights by the Morton code of their view-space position, build a tree bottom-up, choose a cut of 2 to 8 nodes and walk it stochastically; ReSTIR-style reservoir sampling takes 4 to 8 candidates and one shadow ray; spatiotemporal reservoir reuse needs per-surfel or per-cell storage and was not finished (pp. 127-150). Transparent G-buffers spawn no surfels, so transparent surfaces read ray-traced probes in a volume clipmap of 3 or 4 nested levels, projected to SH (order not given) with the same adaptive integrator and Sloan's de-ringing. A level shifts its probes when the camera leaves its center cell, newly exposed probes start from the coarser level, and level borders blend with two samples per shade or one blue-noise dithered sample (pp. 155-175).

**Performance.** PS5, 4K output, screen-space passes at 1080p, no spawn distance limit, no ray cutoff, 8-sample reservoirs unless noted, the worst case an empty, converged scene. From the slides and the talk (read from English auto-captions, with Kyle Hayward of Frostbite presenting from 26:27):

| Scene | Lights | Convergence | Average cost |
|---|---|---|---|
| PvZ town center, sun only | none local | about 3.5 s | about 7 ms, from the large draw distance (pp. 184-186) |
| Stress test, view 1 | about 1400 in view | never at the default budget; about 10 s with a 1M-ray budget, still noisy | about 11 ms once converging, with a spike at spawn (pp. 187-191) |
| Stress test, view 2 | about 1400 | about 7 s with reservoirs, about 5 s with 4-sample lightcuts (near the reference within 15 frames, at higher cost, pp. 141-154) | about 11.3 ms with lightcuts |
| Internal demo, constrained view | about 140 | about 2 s | about 5.5 ms |
| PvZ roaming path | not stated | already converged | about 5.4 ms |
| PvZ roaming path, 1800p checkerboard | not stated | already converged | about 3.4 ms |

Filtering averages about 0.2 ms, applying the surfels is dominated by the lighting pass (pp. 179-181), and the 3-level probe clipmap solve is "very reasonable", with sampling in a full-resolution 900p pass at about 0.2 ms (pp. 203-206). The talk adds that converged surfels drop to about one ray per frame or fewer (16:32-17:44); that irradiance sharing between surfels of the same cell turns a blotchy result after 64 samples into a reasonable one (25:14-26:17); that guiding does not help where light is uniform and matches the cosine lobe, and fails for very small lights the 6×6 map is too coarse to find (24:33-25:04); that with about 700 lights in view and 700 outside, against a reference that converges in about 5 s, after 15 frames 2-sample random sampling is very noisy, 8-sample reservoirs are closer but leave fireflies, and 4-sample lightcuts are closest but cost more on console (32:18-33:09); and that the probe clipmap demo shows four levels and the cost test three, with blue-noise dithered level selection said to work well with their TAA (36:23, 37:57-38:08, 44:08). These costs are GIBS's per-frame cost while it accumulates over seconds, so they bound what a temporal surfel cache spends per frame, not what a converged single-frame result costs (inference).

**Known problems.** Procedural geometry keeps spawning and recycling surfels, and high-detail geometry over-spawns (p. 204). Planned: combining with SSGI, sharing guiding data between surfels, ReSTIR-style guiding, light visibility per cell, and reservoirs per cell or surfel. Not given: pool size, bytes per surfel, grid dimensions, the irradiance format, the probe SH order and N in the gather.

### PICA PICA (Ray Tracing Gems chapter 25)

The chapter describes the PICA PICA renderer, in which only GI, transparency and translucency require ray tracing, while shadows, reflections and AO can be rasterized or traced (pp. 2-3).

**Surfel GI (pp. 22-27).**
- 250,000 rays per frame for diffuse interreflection and up to 250,000 surfels, one ray per surfel per frame, costing 0.35 ms on Turing, at least 0.71 G rays/s with shading (derived).
- A surfel holds position, normal, radius and irradiance in a pre-allocated array. Spawning uses an atomic counter fed by the least-covered pixel of each 16×16 tile, with probability proportional to the pixel's projected world area so a wall coming into view does not spawn a burst. The counter resets only on scene reload, and there is no recycling.
- Surfels remember their object and follow animated objects each frame.
- Irradiance per surfel comes from a one-segment path whose hit reads the previous frame's surfel result, which gives multiple bounces over time; new surfels get more paths, falling to one per frame.
- Surfels are splatted with smoothstep distance attenuation, a Mahalanobis metric that squashes the falloff along the normal (Lehtinen et al.), and an angular falloff, culled and looked up through a world-space grid of surfel lists. Colored multi-bounce SSAO is multiplied in.
- Disoccluded areas start dark (the "first frame" problem). Recycling was not needed for the demo, and LOD for open worlds is left as research.
- The multiscale mean estimator updates `x_{n+1} = lerp(x_n, x_{n+1}, k)` with adaptive `k`. Listing constants: short-window blend 0.08; variance blend 0.5 × 0.08 = 0.04; firefly clamp `0.1 + shortMean + 8·dev`; inconsistency blend 0.08; variance-based reduction clamped to [1/32, 1]; catch-up blend clamped to [1/256, 1]; `vbbr` blend 0.1; luma weights (0.299, 0.587, 0.114).

**Other passes.**
- Shadows (pp. 3-7): rays from depth-reconstructed positions, penumbrae from cone sampling with Halton points rotated per pixel, `TMin = max(1, |pos|)·1e−3`, and a single-scalar SVGF variant with a Karis bounding-box clamp, a Salvi variance box and a 5×5 footprint.
- Reflections (pp. 8-14): half resolution, a quarter ray per pixel, sampled from the microfacet distribution only, with rays below the horizon regenerated. Reconstruction sums `colour(hit)·localBrdf(hit)/hitPdf` over a neighbourhood normalized by the weights, then a bilateral pass; reprojection uses motion vectors or hit points with `w = exp2(−10·luma((rgb − mean)/dev))`.
- AO (pp. 14-16): one or two cosine-weighted rays per pixel with a per-scene maximum length, filtered like shadows; the reference used 1000 spp.
- Transparency (pp. 16-19): a texture-space parameterization per object, Snell refraction or a microfacet BTDF, Beer's law absorption and a recursion limit from the performance target. Translucency (pp. 20-21) traces one scattering ray per texel per frame and accumulates with an adaptive moving average.
- Halton indexing (pp. 29-30): `((h2inv(x % 256, 8)·76545 + h3inv(y % 256, 6)·110080) % m_increment) + i·186624`, with bit reversal for base 2, digit reversal for base 3 and primes up to 131 for 32 dimensions. The chapter calls the listing pseudocode; `m_increment` is never defined and `sampleIndex` is undeclared.

**Timings (Fig. 31, p. 28).** Volta is a Titan V; Turing ran pre-release drivers.

| Pass | Volta (ms) | Turing (ms) | Speedup |
|---|---|---|---|
| Shadows 1 / 2 / 4 / 8 / 16 spp | 1.48 / 2.98 / 5.89 / 11.53 / 23.54 | 0.44 / 0.77 / 1.31 / 2.33 / 4.65 | 3.3 / 3.9 / 4.5 / 4.9 / 5.0× |
| AO 1 spp, max distance 0.5 / 2 / 20 m | 1.67 / 2.18 / 2.50 | 0.54 / 0.62 / 0.62 | 3.0 to 3.6× |
| AO 2 spp | 3.41 / 4.48 / 5.08 | 0.88 / 1.01 / 1.01 | 3.8 to 4.4× |
| AO 4 spp | 6.71 / 8.81 / 10.03 | 1.48 / 1.64 / 1.64 | 4.5 to 5.3× |
| AO 8 spp | 13.27 / 17.44 / 19.85 | 2.55 / 3.02 / 3.02 | 5.2 to 5.7× |
| AO 16 spp | 26.56 / 34.90 / 39.96 | 4.90 / 5.82 / 5.82 | 5.4 to 6.0× |
| Reflections | 2.97 | 1.45 | 2.0× |
| Transparency and translucency | 0.47 | 0.25 | 1.9× |
| GI (250,000 surfels) | 1.70 | 0.35 | 4.8× |

The table was rebuilt from the PDF's text order, and its speedups match the printed ratios.

## Connections

- **Ward's split sphere is the spatial half of the penumbra condition.** Moving a point by `Δ` near a surface at distance `R` changes its irradiance by about `(4/π)·E·Δ/R`, so records may sit `a·R` apart, a spacing proportional to distance. RC spaces probes in proportion to the distance its intervals start at ([penumbra condition](core_theory.md#the-penumbra-condition)), which is the same rule applied per distance band instead of per record; Ward's harmonic mean picks the nearest band that matters, and Tabellion and Lamorlette's minimum picks the nearest outright, which is what cascade 0 spacing has to resolve (inference).
- **Every hashed cache ties cell size to projected size.** Tabellion and Lamorlette's `R_min` of 1.5 to 3 projected pixels (2004) is the first instance. Path space filtering's pixel-multiple voxels, SHaRC's `0.5·log2(dist²)` level, GI-1.0's `tan(fov·8·…)·distance` and Solari's distance LOD are the same rule as Split RC's Chebyshev LOD and Sannikov's per-pixel tile resolution ([world space](3d_world_space.md#connections)). RC's cascades apply it to direction as well as to position (inference).
- **Neighbour clamping is a Lipschitz bound on spacing.** Clamping `R_j ≤ R_k + ‖p_j − p_k‖` makes the spacing field 1-Lipschitz, the property a distance field has; an adaptive RC probe density built from a distance field would inherit it without a clamping pass (inference).
- **Splatting is the GPU form of a scattered merge.** Gautron's splat buffer accumulates `Σ w·E` and `Σ w` per pixel and divides at the end, the shape of any normalized scatter; in Godot's compute path it maps to integer atomics or to raster blending into a float target ([atomics](../../docs/rendering_device.md#atomics)).
- **Records in a local frame cost a rotation.** Radiance caching rotates SH coefficients at every interpolation, its bottleneck; RC and DDGI store directions in the world frame and interpolate them directly (inference).
- **Leak keys are visibility in disguise.** Ward's behind test and Radiance's leak test are the first ones. GI-1.0's `ray_length < cell_size` bit, the normal sign bits in SHaRC and Solari, and kajiya's ranked, output-sensitive trace origins each stop a cell from mixing light that reached it from two sides of a surface, which RC's per-interval transmittance does structurally inside a probe but not between probes ([leak defences](3d_world_space.md#leak-defences-in-world-space)) (inference).
- **Fixed-point atomics are the common currency.** SHaRC's `scale` of 1000, Capsaicin's 10⁴, HDDAGI's 14-bit splats and Split RC's integer deposits all use 32-bit integer adds, the only accumulation Godot offers ([atomics](../../docs/rendering_device.md#atomics)); SHaRC's 64-bit key needs its compact 32-bit form or a lock buffer there.
- **Near and far splits recur.** kajiya takes near hits from raw rays and far hits from reservoirs; GI-1.0 adds horizon AO under its probes; RC's cascade 0 and cascade −1 play the same role, and kajiya's result argues for filtering the near field least ([cascade −1](cascade_layout_and_merging.md#cascade-1-and-contact-detail)) (inference).
- **Ray sorting is shared engineering.** GIBS bins rays by cell and direction, Enshrouded by position and octahedral bin ([probe GI](related_probe_gi.md#enshrouded)); RC's direction-first layouts group rays by direction already (inference).
- **Bounces come from last frame everywhere.** GI-1.0's temporal radiance feedback, Solari's one bounce per frame, PICA PICA's one-segment paths, kajiya's reprojected hits and DDGI's previous-iteration shading all read the previous frame at a hit, the same mechanism world-space RC projects use ([shading the hit](scene_representation_and_tracing.md#shading-the-hit)).

## Single-frame assessment

- **Irradiance caching was single-frame first.** Its original form builds and uses the cache within one image, and the two-pass scheme (fill, then render) or splatting is a single-frame GPU structure. Its timing on 2005 hardware was seconds per image, but the cost was in rasterized hemisphere sampling, not in the structure.
- **Rebuilt caches flicker because their samples move.** Gautron's analysis applies to any single-frame design whose sample positions shift between frames: interpolation error is lowest at samples, so the error pattern moves with them. World-locked probes keep a fixed pattern under camera motion, while screen-anchored probes move it every frame; Jarosz's smoke cache rebuilt per frame without flicker because it sampled densely enough that the pattern stopped mattering ([volumetric](volumetric_and_radiative_transfer.md#radiance-caching-in-media-jarosz-et-al-2008)) (inference).
- **Spatial reuse within a frame is single-frame.** Path space filtering's basic operation, averaging vertices that share a key in the same frame, is a spatial filter keyed by position, and Boissé's world-space ReSTIR rebuilds its grid every frame. Both carry to a single-frame design; what does not is their temporal blend (inference).
- **The rest leans on time.** SHaRC's capped history, GI-1.0's reprojection and blend, kajiya's reservoirs and clamped `M`, Solari's `1/n` blend and GIBS's adaptive average all accumulate, and GIBS's measured convergence takes seconds.
- **Their bounces are lagged.** Every cache here gets multiple bounces by reading the previous frame at hits; a single-frame design needs another source of second-bounce light, or accepts one bounce.
- **Budget figures bound single-frame costs from below.** A cache spending 0.2 to 2 ms per frame while accumulating over many frames shows what one frame's rays buy, not what a converged single-frame result costs.
- **The geometric parts transfer.** Hash keys, LOD rules, leak bits, ranking of query origins, compaction into live lists with indirect dispatch, and free-index stacks are structure, not history, and work in one frame.

## Open questions

- Irradiance gradients come almost free from a record's hemisphere samples. Could each RC probe compute translational gradients from its own rays and use them in the merge's spatial interpolation, the way first-order interpolation removed Radiance's seams?
- Can neighbour clamping or a Weber-law test, as in adaptive radiance caching, set a single-frame RC's probe density per region without history?
- Can kajiya's output-sensitive origins, with one query point per cell picked from this frame's queries, place RC probes in a single frame without the history its votes rely on?
- Does GI-1.0's ray-length bit, or an equivalent, have a cascade form, such as keying merged values by whether the child interval was blocked?
- How much of the energy loss Solari saw in its voxelized cache comes from fixed cell positions and normals, and does a world-space RC grid lose energy the same way?
- What is the cheapest single-frame source of second-bounce light once last frame's lit result is ruled out?
