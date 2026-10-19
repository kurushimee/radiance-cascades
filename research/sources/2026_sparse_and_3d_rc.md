# Sparse and 3D RC

| | |
|---|---|
| Date | 2024-08 to 2026-10 |
| Kind | Collected implementation findings; claims are unverified unless a public link backs them |
| Related | [2026_freeman_split_radiance_cascades.md](2026_freeman_split_radiance_cascades.md), [2026_split_rc_implementations.md](2026_split_rc_implementations.md), [2024_bevy_2d_rc_repositories.md](2024_bevy_2d_rc_repositories.md), [../topics/3d_world_space.md](../topics/3d_world_space.md), [../topics/scene_representation_and_tracing.md](../topics/scene_representation_and_tracing.md) |

Sparse RC is vanilla 3D RC that stores only the probes near visible surfaces, with probe size growing with camera distance so the on-screen probe count stays nearly constant. Split RC is the published form; this note covers the engineering around it: probe placement and levels of detail, GPU hash maps, ray splitting, interpolation leaks, direction counts, tracing without hardware RT, and timings. The parts that matter most for a compute-only tracer are in "Tracing without hardware RT".

## Why sparse

- In Sponza, sparse RC used 100 to 1000× less memory and compute than dense 3D RC at the same resolution. Cost scales with cascade 0 resolution squared, the surface area, not its cube, and stays nearly constant while moving through a world.
- Interval count per cascade grows only about 1.1 to 1.4× in 3D (2×2 directions over 2×2×2 probes), against exactly 1.0× in flatland. One build counted 110,518 cascade 0 probes with 934,557 intervals and 124 cascade 6 probes with 5,129,224 intervals.
- Keeping about 6% of the cascade 0 probes gave a worst-case error of about 0.5% in one test.
- Memory follows the projected area of geometry and moved by ±30% as the camera rotated.
- World-stable probes make sparse RC steadier than screen probes and need no screen-space upscaling. One build found it comparable to SPWI in quality but SPWI much faster.
- Open issues: tracing cost (the probe side was judged shippable and the tracing side not), and the per-instance memory that skinned meshes and particles need in a ray-tracing structure.

## Probe placement and levels of detail

- **Size:** probe size equals the world size of a pixel at that distance, rounded to a power of two, so a probe covers `[P, 2P)` pixels. Probe centers sit at `(grid_idx + 0.5)·2^grid_level`, and negative levels are allowed. Going up one cascade adds the 8 neighbors of the parent cell.
- **Key:** `grid_level mod 4` in the top two bits plus a 28-bit Z-order grid index is collision-free within its window and memory-coherent, and the parent key is a bit shift. 32-bit hashes of larger worlds collide and leave fireflies or one or two dead pixels per screen; a 2048³ world needs 33 bits. Sponza needed at most 4 levels.
- **Ray origin:** start rays at the average world position of the pixels inside the probe (count in one pass, average in a second), which keeps probes on the surface and fixed a seam where float rounding put probes on both sides of a floor. Higher cascades average up to 8 children weighted by pixel count. The pixel closest to the probe center, found with an atomic min over a packed (distance, dx, dy) key, works better for thin features.
- **Inside geometry:** pushing cascade 0 out of the ground made a large difference; probes inside geometry gave a dark cross under spheres. Ray origins taken from pixel positions bias surfaces near the camera darker.
- **Spacing:** constant world-space spacing cost 2.7 ms from one angle and over 30 ms from another, so spacing must stay constant in screen space.
- **Level transitions** are very visible. Fading over an overlap zone costs about 25% more intervals; cubic, axis-aligned level boundaries greatly reduced artifacts; with 4× interval scaling one build needed no transition blending at all.
- **Pop-in:** spawning only the nearest upper probe made higher cascades pop in. Spawning all trilinear neighbors cost 2 to 4× the probes on flat surfaces and about 30% more in a volumetric scene.
- **Frustum-space grid** (alternative): `z_idx = log(view_z)/tan(probe_angle)` gives near-cubic froxels of one size in screen pixels, a single continuous grid with no power-of-two levels or seams, stable under sideways motion ([derivation](https://www.desmos.com/calculator/xitcustpds)). These probes change as the player moves, so they accumulate over time worse than world-space probes. Deduplicating per screen cell gave 50k to 200k probes on screen, about 2 per cell on average and 12 to 15 at most.

## GPU hash maps

- **Probing:** linear probing took over 20 iterations with linear and Morton keys; probing with `(hash + pcg(attempt)) % count` capped it at 6 to 8 ([paper](https://inria.hal.science/inria-00624777v1/file/paper.pdf)). Using the same probe sequence for all pixels keeps memory access coherent. 300k probes fitted with no collisions using 10 bits per axis and 2 level bits. Keep the load at or under 20 to 25%.
- **Inserting:** check whether a slot already holds the key before the compare-and-swap; only empty slots need it. Deduplicating within a subgroup first helps, since about 300 threads can hit the same probe. 64-bit keys need a Vulkan extension for 64-bit atomics. A subgroup-bucket design (buckets of subgroup size, one compare-and-swap per bucket) usually finds its slot on the first try.
- **Pipeline:** spawn entries from on-screen pixels, compact used entries into a dense list with an indirect dispatch, then trace and merge per cascade, then draw. Rebuilding the map every frame from visible and retained probes was the simplest approach. Storing the 8 dense parent indices per probe lets the merge run without hash lookups; in another build caching parents gained only 0.2 ms for a lot of memory.
- **Sizing:** allocate for the worst case of one cascade 0 probe per pixel, profile real scenes, and allocate twice the maximum. One build over-allocated 10×, with 10M probe slots per cascade and 700 MB; another needed 120k probes. 4×4-px patches at one megapixel give about 65k probes; 2^18 slots were enough in tests.
- **Costs:** filling a map took about 0.1 ms in one build and 0.4 ms for a 2^21 table on a laptop RTX 3060; initializing all cascades took 0.155 ms; the spatial-hashing approach from [this RTAO article](https://interplayoflight.wordpress.com/2025/11/23/spatial-hashing-for-raytraced-ambient-occlusion/) took about 2 ms for cascade 0 alone on an RTX 2080. That figure is the poster's own measurement; the article itself reports 0.4 ms for cached and 1.72 ms for uncached RTAO on an RTX 3080 Mobile at 1080p ([notes](2026_gpu_hash_tables_and_sorting.md#spatial-hashing-for-ray-traced-ao-interplay-of-light)). Hashing at 2×2 downscale gives the same probes 4× faster. Lookups are much cheaper than insertions.
- **Sorting instead:** radix-sorting 1M 32-bit keys took 0.16 ms on an RX 9070 XT, 0.21 ms on an RTX 4080, over 1 ms on a laptop RTX 3060, and 2.84 ms in WebGPU on a GTX 1650 ([demo](https://mebyz.github.io/adaptive-radiance-cascades/df-full-radix-sort-webgpu.html)). Hashing 1080p probes with deduplication took 0.3 ms, so a sort has to beat that. Single-pass scans with decoupled lookback need forward-progress guarantees and can deadlock.
- Sparse merging ran about 50% faster than a dense SPWI merge in one comparison, probably from better cache use after compaction.

## Ray splitting

- **Idea:** cast rays from visible surface points instead of per probe and interval. A ray that hits at distance `d` gives an opaque interval to the cascade whose range contains `d` and a transparent interval (radiance 0, transmittance 1) to every cascade below; averaging many rays per cone gives fractional transmittance. Vanilla RC traces about 6 rays per direction chain (one per cascade); splitting traces one.
- **When it pays:** only when one long ray costs less than several short rays plus the merge, which is true with hardware RT and its per-query overhead. Without hardware RT, plain sparse RC was simpler and faster.
- **Pitfalls:** writing only to the hit cascade lowered error from 0.15 to 0.11. Directions that get no rays must contribute nothing in the weighted merge, or fully open or fully enclosed scenes break. Rounding that forced upper-cascade opacity to exactly 0 or 1 stopped convergence. R2 directions instead of PCG random ones improved edge cases a lot, about 20% in early tests. Over-darkening appeared when every occluding ray applied half transmittance at every level.
- **Analytical splitting:** a permutation maps a cascade 0 position to a cascade `N` direction, so each ray serves `N` cascades and all directions get covered over `4^(cascades−1)` frames. Black lines came from depth-reconstructed points not matching the BVH; moving the near plane from 0.01 to 0.05 removed them.
- **Deposits:** atomic deposits took about 16 ms against 0.3 ms without atomics; sorting 10M deduplicated texels took about 1.5 ms. Writing each ray into two adjacent cascades with interpolated weights removed seams at twice the cost.
- **RC as a filter on 1-sample path tracing:** rays from a 1 spp image, binned by hit distance, each bin shared over an exponentially larger pixel radius. One build cast 14.7M rays per frame at 5120×2880 on an RX 9070 XT. Hashing positions and directions gives at most one entry per ray per cascade, a fixed memory budget. Against OIDN at 1 spp without temporal reuse, OIDN was blotchy and lost detail, while RC lost contact shadows. It assumes samples on surfaces, not in volumes ([2D proof of concept](https://www.shadertoy.com/view/tf3BDS)).

## Interpolation and leaks

- Long-distance interpolation causes most sparse 3D artifacts, and trilinear interpolation always leaks through thin walls. A fix that removed leaks through a 2 to 3 voxel cave wall: interpolate with a parent neighbor only when the nearest child rays in that direction were unoccluded, using one bit of hit/miss data per ray, at about 50% more merge time. Interpolation must be centered on voxel centers, or everything shifts half a voxel.
- Nearest spreading with linear gathering gave lower L2 error than bilinear spread and gather. Renormalize weights when trilinear neighbors are missing.
- Requesting only the nearest upper probe showed no artifacts in one build; full cube interpolation was about 4× slower.
- **Drawing:** a per-pixel trilinear gather took 27 ms of a 37.5 ms frame in one build; rasterizing one cube per probe, twice the probe size, additively with trilinear weights took about 1 ms and handled level seams, at the cost of overdraw. Another build found the trilinear gather faster. Nearest sampling cost 3.6 ms against 18 ms trilinear in a third.

## Parameters and directions

- **Interval scaling:** 4× per cascade was called the only correct value in 3D (a 2.2× result was a bug). 4× gives uniform error at the same compute and memory with one fewer cascade; 2× error is dominated by angular error near and spatial error far. Sponza took 6 cascades at 4× or 7 at 2×, about 200k cascade 0 probes, and a cascade 0 interval of about 0.01 to 0.05 (0.015 typical; 0.005 was too short). Shorter cascade 0 intervals sharpen contact shadows and worsen peter-panning.
- **Cascade 0 directions:** 8 showed obvious artifacts and gave no performance or memory gain over 32 in one build; 32 against 8 was "really quite noticeable". Cutting cascade 0 spatial resolution before angular resolution smooths GI, while cutting angular resolution aliases. Another option inserts a new cascade before cascade 0 with a quarter of the distance, half the probe size and a quarter of the directions.
- **Rays per cone:** the penumbra condition concerns rays cast, not directions stored. 4×2 stored cones with 8×8 rays each use the same memory as 4×2 cones with one ray, so average many rays per stored cone.
- **Gathering to irradiance:** one cosine per cone is wrong (a cube-face cone pointing along the floor gets zero weight); 4×4 cosine samples per cone cost about 0.3 ms, the same as 8×8. Per-direction sums of `max(0, dot(dir, n))` had fewer failure modes than SH1; in one build an SH clamp hid negative radiance caused by wrong mesh normals. SH1 fits cascade 0 only; higher cascades need more angular resolution.
- **Mappings:** classic octahedral maps are poor at low resolution; equal-area octahedral looks better, and equal-area cylindrical maps need a 2:1 or π:1 aspect ([Clarberg mapping](https://fileadmin.cs.lth.se/graphics/research/papers/2008/simdmapping/clarberg_simdmapping08_preprint.pdf), [notes](2008_clarberg_equal_area_sphere_mapping.md), [HEALPix](https://healpix.sourceforge.io/), [notes](2005_gorski_healpix.md)). Cross-shaped artifacts from small lights on walls tracked the cascade 0 direction count, not the octahedral Jacobian.
- **Hard shadows:** cascade 0 probes inherit occlusion from cascade 1, so a shadow darkens uniformly below the level that saw the occluder, and interpolation cannot add resolution. Variance-guided retracing helps: one build found high-variance cascade 0 directions and cast 4 full-length rays per probe, about 2.8M long rays against 4.5M RC rays, adding 1 ms to a 4 ms scene on an RTX 2080 Ti and also reducing leaks ([video](https://www.youtube.com/watch?v=yTxFZp_RK5U)).

## Tracing without hardware RT

- An optimized software ray-tracing kernel ran about 4× slower than hardware RT on Apple M3 and later.
- Sparse voxel cone tracing with naive linear marching came close to hardware RT in one build and about 1.8× slower in another; a DDA per occupied probe with hash lookups ran 2 to 4× slower than ray tracing. Nearest-probe marching was undersampled at 4 ms against hardware RT.
- Each cascade needs a scene proxy filtered to its probe spacing, like texture mips: voxels as large as the gap between adjacent rays avoid blur and aliasing. Tracing mip `N` with cascade `N` gave blocky upscaling in an early build. Cone tracing trades noise for blocky, aliased shadows, and replacing a cone with one ray adds aliasing, not sharpness.
- Averaging 2×2×2 voxels makes thin walls half transparent at every mip, so directional (six-direction) opacity is needed ([GIVoxels](https://research.nvidia.com/sites/default/files/publications/GIVoxels-pg2011-authors.pdf), [notes](2011_crassin_voxel_cone_tracing.md)).
- A two-level grid (16³ cells over 4³ bricks) traced 2× faster than an H-PLOC BVH, though more slowly on AMD than on NVIDIA. A binary BVH beat wide BVHs for coherent RC rays. 4×4×4 brick bitmasks with a lookup table are another option ([subspace culling](https://gpuopen.com/download/I3D2023_SubspaceCulling.pdf)).
- A 2D DDA over 8×8 bit planes traced 11M rays in 1.2 ms; a 3D DDA over 4×4×4 bit cubes traced 15M rays in about 5 ms.
- One proposal precomputes static intersections per texel and retraces only intervals that overlap the bounds of dynamic objects, through a TLAS holding only dynamic objects and capped by the static hit distance.

## Other designs

- **Sparse 2D RC:** ray-march bottom-up from cascade 0, enabling parent tasks only for rays that hit nothing, then merge top-down. A contrived edge-only scene needed 340k rays against 49M dense; very dense scenes cost the same as dense RC. The repository's slides give 0.40 M against 13.3 M rays (0.52 against 1.77 ms) in the star scene at 1080p, and the design is described in [2024_bevy_2d_rc_repositories.md](2024_bevy_2d_rc_repositories.md#icekontroisparse_rc_2d) ([repository](https://github.com/IceKontroI/sparse_rc_2d), [slides](https://docs.google.com/presentation/d/1shDaU-fOrhVIg4lGkITJcxVnf-VkVVTahlxngPiqeMs/edit?usp=sharing), [video of a 3D sparse version](https://www.youtube.com/watch?v=vHk4a7Nzw-c)).
- **Primal and dual hierarchies:** primal probes collect incoming radiance; dual probes store radiance emitted by the geometry in their cube. They share one hash map, but a missing dual probe means zero radiance while a missing primal probe means unknown, so sparse cone extensions fail.
- **Intervals instead of probes:** an occluded cascade 0 interval needs no higher intervals, so storing sparse intervals could waste about 10× less, and stored hit points allow reprojection. A one-bit-per-interval occupancy bitmap gives O(1) existence checks.
- **Surface parameterizations:** quad patches from slicing a mesh with axis-aligned planes, or 2×2 voxel blocks replaced by quads through their mass centers, merged hierarchically for higher cascades. Lightmap-UV probes grow with the scene and distort with automatic UVs.
- **Surfels plus a dense clipmap** shipped in Love and Deepspace (see [2026_rc_conference_talks.md](2026_rc_conference_talks.md)). Surfels handle corners better than a sparse grid; one opinion called surfels pointless next to a sparse grid.

## Multi-bounce, specular and comparisons

- **Multi-bounce:** insert last frame's secondary hits into the hash map two levels coarser and resolve them over frames. Anderson or Ng acceleration could speed up infinite-bounce convergence. A two-bounce darkening bug came from shadow rays written to the bounce origin instead of its endpoint.
- **Specular:** with ray splitting, rough surfaces stop climbing cascades early, a box-filtered split-sum prefilter. Reflective gathers are 6D, so multilinear interpolation needs 64 taps.
- **Against DDGI:** at similar ray counts, RC's multi-level interpolation was much smoother than DDGI's trilinear. Numerically DDGI scored better in one study (RC with 8 directions was biased; error 3000 against 2500, FLIP 0.19 against 0.15), while RC looked better because DDGI over-darkened. Without multi-bounce RC was much noisier.

## Measurements

| Setup | Time |
|---|---|
| Sparse RC demo, hardware RT, 1 ray per probe per direction | 6 ms unoptimized; converges in about 4 frames at 100 fps |
| Sponza on a laptop RTX 4090, hardware RT | 3 to 5 ms |
| 2048² frame: trace, merge, screen pass, draw | 34.7 ms: 4.1 + 17.8 + 7.5 + 1.9 |
| Hybrid RC and RT frame: merge, draw, lower cache, radiance | 32.1 ms: 4.3 + 3.8 + 5.8 + 18.3 |
| 4 cascades, 16 cascade 0 directions into SH1, 8 px probes, 1 ray per direction | about 20 ms with ray tracing, about 12 ms with ray marching |
| Box room on an M3 Max (wgpu), after adding one emitter | 120 → 30 fps, mostly ray splitting |
| Software-RT prototype on an M2, 16 cascade 0 directions | 512 ms (30% tracing, 50% hash insertion) |
| Laptop RTX 3080 | about 2 ms at 1 ray per pixel, 22 ms at about 3 |
| Split RC build: tracing, then merge | 3.6 ms + 0.9 ms |
| 2-means placement of upper probes | 0.18 ms, against 3.5 ms tracing |
| Ray-splitting deposit | 6 ms, 4 ms of it in the last two cascades |
| Ray splitting from 1 spp: write, then final interpolation with 32 cascade 0 directions | 7 ms + 11 ms |

## Links

- Sparse 3D RC prototype video: https://www.youtube.com/watch?v=TGLAxW0xVDU ([notes](2022_sannikov_youtube_rc_videos.md#sparse-3d-radiance-cascades-2025))
- Surfel RC (screen-spawned surfels): https://github.com/mxcop/src-dgi, hash grid at https://github.com/mxcop/src-dgi/blob/main/assets/shaders/shared/hash.slang#L30, maintenance at https://m4xc.dev/blog/surfel-maintenance/ (now served at https://m4xc.dev/articles/surfel-maintenance/; [notes](2025_coppen_surfel_radiance_cascades.md))
- NVIDIA SHARC hash grid: https://github.com/NVIDIA-RTX/SHARC/blob/main/include/HashGridCommon.h
- GPU hash maps: https://developer.nvidia.com/blog/maximizing-performance-with-massively-parallel-hash-maps-on-gpus/ and https://nosferalatu.com/SimpleGPUHashTable.html ([notes](2026_gpu_hash_tables_and_sorting.md))
- GPU sorting: https://github.com/b0nes164/GPUSorting (ForwardSweep is the variant that needs no forward-progress guarantee; [notes](2026_gpu_hash_tables_and_sorting.md#gpusorting-b0nes164))
- Morton decoding on GPUs: https://fgiesen.wordpress.com/2009/12/13/decoding-morton-codes/ ([notes](2026_gpu_hash_tables_and_sorting.md#morton-codes-giesen))
- Adaptive RC (ray skipping by local variance): https://mebyz.github.io/adaptive-radiance-cascades/
- Probes on visible surfaces: https://dl.acm.org/doi/10.1145/3675382 (Tatzgern et al. 2024: radiance hemispheres cached in texture space on the surfaces themselves rather than probes in a volume; [notes](2024_tatzgern_on_surface_radiance_caches.md))
- Gigavoxels thesis: https://maverick.inria.fr/Publications/2011/Cra11/CCrassinThesis_EN_Web.pdf (sparse voxel octree with bricks, pre-integrated cone tracing and ray-guided streaming; [notes](2011_crassin_gigavoxels_thesis.md))
- Distance impostors for a spherical radiance field: https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-17-robust-multiple-specular-reflections-and-refractions (layered distance cube maps searched in texture space; [notes](2007_umenhoffer_layered_distance_maps.md))
- Wavelet radiance encoding: https://perso.telecom-paristech.fr/boubek/papers/WPBGI/WPBGI_lowres.pdf (Haar-compressed cube maps on a point hierarchy; [notes](2015_wang_wavelet_point_based_gi.md))
- Quasirandom R2 sequence: https://extremelearning.com.au/unreasonable-effectiveness-of-quasirandom-sequences/ (read from a Wayback copy; the live site failed its TLS handshake). Roberts defines `R_d`: `t_n = {n·α}` with `α = (1/φ_d, 1/φ_d², …, 1/φ_d^d)` and `φ_d` the positive root of `x^(d+1) = x + 1`, so `φ_1` is the golden ratio 1.6180339887, `φ_2` the plastic constant 1.324717957244746 and `φ_3` 1.2207440846; this gives `α = 0.6180339887` in 1D, (0.7548776662, 0.5698402910) in 2D and (0.8191725134, 0.6710436067, 0.5497004779) in 3D (derived from the formula). It needs no base or direction numbers, unlike Halton (coprime bases), Kronecker (independent irrationals) or Sobol; on a 1D test integral with `10^6` points it reaches about 10^−7 error against 10^−6 for van der Corput and 10^−4 for random, and the post says R2's normalized packing distance does not tend to zero. As a dither mask, `I(x, y) = {α₁x + α₂y}` or its triangle-wave form `T(z) = 2z` below 1/2 and `2 − 2z` above, which needs no precomputation, costs 2 multiplies and one mod against 3 and two for interleaved gradient noise, and competes with blue noise while not being isotropic. On the sphere, `z = 2u − 1` and `φ = 2πv` give an equal-area map that, unlike a Fibonacci lattice, takes points one at a time. For RC, an R2 offset per probe or per frame is a stratified jitter of ray directions that needs no table (inference).
