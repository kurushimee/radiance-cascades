# 3D world space

World-space RC stores its probes in the scene instead of on the screen. It sees light from off screen and from hidden surfaces, can light volumes, and keeps probes still while the camera moves. Its obstacle is memory: a dense 3D grid at useful resolution needs gigabytes, so every design that reaches a frame budget stores only the probes near visible surfaces. This topic covers dense grids and their cost model, sparse probes in hash maps, Split RC's ray splitting, leaks and temporal reuse in world space, and the GPU building blocks sparse designs use. The theory behind the parameters is in [core theory](core_theory.md#cascade-scaling), the direction maps and the gather tiles in [cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d), and each world-space code base in [world-space implementations](3d_world_space_implementations.md). Surfels and UV charts are in [3D surface probes](3d_surface_probes.md), and screen probes with world intervals in [3D screen space](3d_screen_space.md).

## Contents

- [Why world space](#why-world-space)
  - [Sannikov's sparse 3D RC (2025)](#sannikovs-sparse-3d-rc-2025)
- [Dense grids](#dense-grids)
  - [Memory and rays](#memory-and-rays)
  - [Reach and cascade count](#reach-and-cascade-count)
  - [Marching cost](#marching-cost)
  - [Dense projects](#dense-projects)
- [Sparse probes near surfaces](#sparse-probes-near-surfaces)
  - [Why sparse](#why-sparse)
  - [Placement and levels of detail](#placement-and-levels-of-detail)
  - [Hash maps for probes](#hash-maps-for-probes)
- [Ray splitting](#ray-splitting)
  - [Samples per direction per frame (derived)](#samples-per-direction-per-frame-derived)
- [Merge and interpolation](#merge-and-interpolation)
  - [Leak defences in world space](#leak-defences-in-world-space)
- [Shading](#shading)
- [Tracing for world-space cascades](#tracing-for-world-space-cascades)
- [Other sparse designs](#other-sparse-designs)
- [Multi-bounce, specular and comparisons](#multi-bounce-specular-and-comparisons)
  - [Split RC against DDGI and a reference](#split-rc-against-ddgi-and-a-reference)
- [Measurements](#measurements)
- [Temporal reuse in world space](#temporal-reuse-in-world-space)
- [Adoption and plans](#adoption-and-plans)
- [GPU building blocks](#gpu-building-blocks)
  - [Spatial hashing for ray-traced AO](#spatial-hashing-for-ray-traced-ao)
  - [Parallel hash maps (cuCollections)](#parallel-hash-maps-cucollections)
  - [A simple lock-free GPU hash table](#a-simple-lock-free-gpu-hash-table)
  - [GPUSorting](#gpusorting)
  - [Morton codes](#morton-codes)
  - [In Godot's `RenderingDevice`](#in-godots-renderingdevice)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)

## Why world space

- **Off-screen and hidden light.** A world-space probe traces the scene, not the depth buffer, so a light behind a column or in another room still reaches it. Sannikov's sparse RC gained off-screen lights by moving from a screen-space marcher to hardware ray tracing ([videos](../sources/2022_sannikov_youtube_rc_videos.md#sparse-radiance-cascades-goodbye-screenspace-2025)).
- **Volumes.** Fog and media need radiance at points off every surface, which world-space cascades hold and screen-space cascades do not ([volumetric](volumetric_and_radiative_transfer.md)).
- **Stability.** World-stable probes make sparse RC steadier than screen probes and need no screen-space upscaling. One build found it comparable to SPWI in quality, while SPWI was much faster ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#why-sparse)).
- **Temporal reuse without reprojection.** New intervals can be blended into the previous frame's cascades directly ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details)).
- **The obstacle** is the memory of a dense 3D cascade 0 and the occlusion-aware interpolation it needs. The positions people take on that obstacle are in [history](history_and_landscape.md#positions-on-3d-rc).

Sannikov's first 3D RC (October 2022) was already world space, in voxels re-voxelized each frame with every cascade recomputed each frame ([history](history_and_landscape.md)). The later sparse videos are the direct ancestors of Split RC.

### Sannikov's sparse 3D RC (2025)

**"Sparse 3d Radiance Cascades" (2025-11-02):**

- Classic full 3D world-space RC with sparse storage: only probes directly visible on screen are added.
- Storage is a large GPU hash map, cascaded like a radiance cache, but holding radiance intervals instead of radiance.
- Each pixel picks the world-space resolution of its interval tiles so that a tile covers nearly the same screen area. The number of tiles in memory stays nearly constant, so the method scales almost like a screen-space one while staying in world space, with no upscaling.
- Tiles are cached by world position and by desired resolution. A missing tile of the needed size renders as missing; with streaming frozen, tiles vanish when the camera moves too close or too far.
- The demo traces with a basic screen-space ray marcher. The method does not depend on it and could use hardware ray tracing or SDF marching.
- There is no interpolation between tiles, which gives a blocky look.
- 60 to 100 fps on a laptop, with no denoising, no temporal accumulation and no upscaling.

**"Sparse Radiance Cascades: goodbye screenspace" (2025-12-25):**

- Hardware ray tracing replaces the screen-space marcher, which allows off-screen lights and is faster.
- 60 fps on a laptop RTX 4090, stable under small camera moves, with all GI computed from scratch each frame and no denoiser.
- A visible seam between cascades remains, and the code is not optimized. The CPU does little work; the slow CPU frame in the video comes from validation layers and a debug build.
- The description does not say world space, but off-screen lights imply data not tied to the screen. It gives no resolution, cascade count or per-stage timings.

Sources: [videos](../sources/2022_sannikov_youtube_rc_videos.md#sparse-3d-radiance-cascades-2025).

The two videos are the only world-space 3D RC shown running from scratch every frame at a game frame rate before Split RC, and they state the design's core idea: probe size tied to screen size makes world-space memory follow the screen (inference from the descriptions).

## Dense grids

A dense grid puts probes over a whole box, as the paper's 3D grid case does. It is the easiest design to write and the most expensive to run.

### Memory and rays

With `N³` cascade 0 probes and `D0` directions, each cascade has 8× fewer probes and `K = 4`× more directions, so its texel count halves. The whole stack holds about `2·N³·D0` texels and, with one ray per texel, traces as many rays per full update. The interval scaling `l` does not enter: it changes how far the cascades reach, not how much they store (derived).

| `N` | `D0` | Texels and rays | fp16 RGBA (8 B) | fp32 RGBA (16 B) |
|---|---|---|---|---|
| 32 | 16 | 1.0 M | 8 MiB | 16 MiB |
| 32 | 32 | 2.1 M | 16 MiB | 32 MiB |
| 32 | 64 | 4.1 M | 32 MiB | 63 MiB |
| 64 | 16 | 8.3 M | 63 MiB | 126 MiB |
| 64 | 32 | 16.5 M | 126 MiB | 252 MiB |
| 64 | 64 | 33.0 M | 252 MiB | 504 MiB |
| 128 | 16 | 66.1 M | 504 MiB | 1,008 MiB |
| 128 | 32 | 132.1 M | 1,008 MiB | 2,016 MiB |
| 128 | 64 | 264.2 M | 2,016 MiB | 4,032 MiB |
| 256 | 16 | 528.5 M | 4,032 MiB | 8,064 MiB |
| 256 | 32 | 1,057 M | 8,064 MiB | 16,128 MiB |
| 256 | 64 | 2,114 M | 16,128 MiB | 32,256 MiB |

Six cascades, computed; the sum is within 2% of `2·N³·D0` (derived).

The model reproduces the measured projects:

- jumeder's 32³ grid with 2048 lat-long directions and 4 cascades: 960 MiB and 125.8 M rays, exactly the repository's 960 MiB and 126 M rays ([implementations](3d_world_space_implementations_grids.md#jumederdx12-radiance-cascades)).
- tmpvar's 64³ grid with 36 directions and levels 0 to 5: 18,579,456 texels, 283.5 MiB of payload at 16 bytes, while the code allocates 1,792 MiB per atlas because every level gets a full 4096² layer. Only 15.8% of the allocation holds probes (derived; [implementations](3d_world_space_implementations_grids.md#tmpvars-radiance-cascades-3d-grid)).
- tmpvar's playground computes one cascade's storage as `diameter³·rayCount·bytesPerRay·2`, with 6 directions (cube faces), 16 bytes per ray and a factor of 2 for ping-pong buffers, so 192 bytes per probe: 0.75 MB at 16³, 6 at 32³, 48 at 64³, 384 at 128³, 3,072 at 256³, 24,576 at 512³ and 196,608 at 1024³ ("MB" being MiB), and 0.046875, 0.1875, 0.75, 3, 12, 48 and 192 MiB for one `diameter²` slice ([playground](../sources/2024_tmpvar_rc_playground.md#demo-6-world-space-probe-storage-table-3d)). The table covers cascade 0 only; the full stack doubles it (derived).

At 128³ with 32 directions a dense grid already needs 1 GiB in fp16 and 132 M rays per full update. One ray per pixel at 1080p is 2.07 M rays. A grid fine enough near the camera is therefore out of a frame budget unless it is small, coarse, or updated over many frames, which is what every dense project does (derived).

### Reach and cascade count

The top cascade must reach across the grid. With `t0 = 1.6·Δs0` (the equal-error choice for 32 directions, [core theory](core_theory.md#choosing-cascade-0-derived-and-reported)), reaching the diagonal `√3·N` spacings takes 4, 5, 5 and 6 cascades at `l = 4` for `N` = 32, 64, 128 and 256, against 7, 8, 9 and 10 at `l = 2` (derived). Memory is the same either way, since the extra `l = 2` cascades hold little.

### Marching cost

Time follows how far rays march, not only how many there are.

- **Dense volume probes** (probes ÷8 per cascade): march distance per cascade relative to cascade 0 is 1, 0.5, 0.5, 0.5, 0.5, 0.5 at `l = 2`, and 1, 1.5, 3, 6, 12, 24 at `l = 4`, where it doubles per cascade (derived, uniform step length).
- **Surface-bound probes** (probes ÷4 per cascade, the flat-surface case of sparse designs): rays per cascade stay constant, so march distance per cascade is 1, 1, 2, 4, 8 at `l = 2` and 1, 3, 12, 48, 192 at `l = 4`. The top two cascades take 75% and 94% of all marching (derived).

So `l = 4`, which [core theory](core_theory.md#two-criteria-for-interval-scaling-derived) favours for error, is affordable with a marching tracer only if the step length grows with the interval. Each cascade needs a scene proxy filtered to its own resolution, the 3D form of the mip marching in [volumetric RC](volumetric_and_radiative_transfer.md#marching-on-mips), or a tracer whose cost does not grow with distance (hardware RT, a BVH, or a hierarchical DDA), or Split RC's single long ray per pixel (inference).

**Which mip.** At the equal-error setting (`|Ω0| = 32`, `t0 = 1.6·Δs0`, `K = l = 4`), the gap between neighbouring ray ends inside cascade `n` grows from `Δs_n/4` at the interval start to `Δs_n` at its end: 0 to 1.0, 0.5 to 2.0, 1.0 to 4.0, 2.0 to 8.0 and 4.0 to 16.0 cascade 0 spacings for cascades 0 to 4 (derived). A proxy whose cell matches the gap therefore spans two mip levels within one interval. A single mip per cascade is either too coarse at the start or too fine at the end, which fits the report that tracing mip `N` with cascade `N` gave blocky upscaling ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#tracing-without-hardware-rt)). Choosing the level per sample from the distance along the ray, as creikey's clipmap trace does with `LOD = 0.5·log2(t/2)`, follows the gap ([implementations](3d_world_space_implementations_grids.md#creikeyvoxel-radiance-cascades)) (inference).

### Dense projects

| Project | Probes | Cascade 0 directions | Per cascade | Intervals | Cascades | Storage |
|---|---|---|---|---|---|---|
| tmpvar 3D grid | 64³ over 16 units, 0.25 spacing | 36 (octahedral 6×6) | probes ÷8, directions ×4 | `[0.05·4^(l−1), 0.05·4^l)` | 6 | RGBA32F atlas, 1,792 MiB per copy |
| jumeder DX12 | 32³ over a 2×2×2 box | 2048 (lat-long 64×32) | ÷8, ×4 | ×8, ends 0.031, 0.28, 2.28, 18.3 | 4 | RGBA16F, 960 MiB |
| rbnelr voxel_game (3D module) | 25³, 4 m apart | 4 (octahedral 2×2) | single cascade, no merge | | 1 | debug view only |
| erhe | up to 65,536 fitted to visible content, 1.5 m | 64 (octahedral 8×8) | ÷8, ×4 | `[r0(2^i − 1), r0(2^(i+1) − 1)]`, `r0 = 3.46·s0` | up to 8 | RGBA16F raw and merged, 288 MiB (derived) |
| SultanAladin | world probe grids | octahedral tiles | | | | Vulkan GLSL |
| mpalenque/sim | world probe grid in three.js | octahedral | spacing ×2, ×4 | `base·(4^i − 1)/3` to `base·(4^(i+1) − 1)/3` | | cascade 0 resolved into an SH volume |
| EggyStudio 3DEngine | 8 field cells apart per clipmap level | 64 | presets | spacing to 4× spacing | 2 to 4 | 1.65 to 9.16 MB |
| M3ycWt (Mathis) | 32×32×48 to 2×2×3, six hemispheres each | 9 per hemisphere at level 0 | `3·2^L` per hemisphere side | none: rays run to the first hit | 5 | Shadertoy buffers |
| gomezzz (Godot) | 24×16×24 over 12×8×12 units, 0.5 spacing | 32 (8×4, uniform in longitude and cosine) | ÷8, ×4 | `[0.75(2^L − 1), 0.75(2^(L+1) − 1)]` at spacing 0.5 | 5 | one vec4 per direction, 8.94 MiB, about 1 KiB per base probe ([Godot projects](godot_projects.md#gomezzz-world-space-3d-rc)) |
| CT volume RC (Rulkens's thesis code) | 192³ over a unit cube | 6 cube faces | ÷8, ×4 | ×2 | 5 | 627.8 MiB of cascades, about 1.5 GB allocated ([volumetric](volumetric_and_radiative_transfer.md#rc-for-ct-volumes-repository)) |
| tauray RCPG | 128³, live probes only | 16 (octahedral 4×4) | ÷8, ×4 | angle table | 5+ | luminance only, about 325 MB ([sampling and guiding](rc_for_sampling_and_guiding.md)) |

A short write-up of an honours project, "3D Radiance Cascades" (https://noamzeise.com/drafts/2025-05-10-dissertation.html, Common Lisp and OpenGL in the author's own framework, ambient light only; not a dissertation draft despite the URL), which credits RC to Sannikov as GI without ray-tracing hardware, found a fixed 3D probe grid too slow for real time and probes in projection space that move with the camera hard to interpolate, so its final version keeps probes in view space, where world-space distances between probes are easy; its comparison with SSAO is screenshots only ([discussions](../sources/2026_rc_discussions.md)).

Sources: [world-space implementations](3d_world_space_implementations.md) and [Godot projects](godot_projects.md); erhe's storage is computed from its defaults in that file.

Every dense project either keeps the grid small (32³ to 64³ over a room), stores less per texel (luminance, SH), updates a fixed texel budget per frame (erhe refreshes everything only every 64 frames), or does not run per frame at all (tmpvar builds once; the CT code recomputes in 20 to 34 ms on a laptop RTX 4080 and reuses the field while the camera moves; jumeder and rbnelr are demonstrations). The grid codes are useful for index math and edge cases, not as designs to ship (inference). Their recurring bugs (upper-index clamps one past the grid edge, wrong edge weights for probe 0, half-cell gather offsets when probe centres sit at `i + 0.5`, solid-angle weights missing from lat-long grids) are listed with the code in [world-space implementations](3d_world_space_implementations.md).

## Sparse probes near surfaces

Sparse RC is vanilla 3D RC that stores only the probes near visible surfaces, with probe size growing with camera distance so that the on-screen probe count stays nearly constant. Split RC ([paper](../sources/2026_freeman_split_radiance_cascades.md)) is the published form; the engineering around it comes from several builds ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md)).

### Why sparse

- In Sponza, sparse RC used 100 to 1000× less memory and compute than dense 3D RC at the same resolution. Cost scales with cascade 0 resolution squared, the surface area, not its cube, and stays nearly constant while moving through a world.
- Interval count per cascade grows only about 1.1 to 1.4× in 3D (2×2 directions over 2×2×2 probes), against exactly 1.0× in flatland. One build counted 110,518 cascade 0 probes with 934,557 intervals and 124 cascade 6 probes with 5,129,224 intervals. That is ×1.33 intervals and ÷3.10 probes per cascade, with 8.46 intervals per probe at cascade 0 and 41,365 at cascade 6 (derived from the counts).
- Keeping about 6% of the cascade 0 probes gave a worst-case error of about 0.5% in one test.
- Memory follows the projected area of geometry and moved by ±30% as the camera rotated.
- Open issues: tracing cost (the probe side was judged shippable, the tracing side not), and the per-instance memory that skinned meshes and particles need in a ray-tracing structure.

Sources: [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#why-sparse).

A probe count falling ÷3.1 per cascade sits between a flat surface (÷4) and a line (÷2). Adding the 8 neighbours of each parent cell, as that build does, keeps more coarse probes than a flat surface needs (inference).

### Placement and levels of detail

**Split RC's rule.** One hash map per cascade. Each frame every pixel inserts the nearest cascade 0 probe to its world position, and every cascade `n` probe inserts its nearest cascade `n + 1` probe, which creates the nearest probe of every cascade to each visible point. Trilinear neighbours are not all created, which halves the probe count for little loss, so interpolation is **sparse trilinear**: sum the existing neighbours times their trilinear weights and divide by the total weight ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#sparse-probes)).

**Levels of detail.** Each probe also stores an LOD, the binary log of its Chebyshev distance to the camera, which gives fewer artifacts than the Euclidean distance with grid-aligned probes and keeps probes at a constant on-screen size. Each LOD doubles `Δs0` and `t0`. LODs never mix: each starts at 0.9 of its distance to overlap the previous one, and the two blend linearly across the overlap ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#sparse-probes)). Half-cell probe offsets keep cascades from aligning ([cascade layout](cascade_layout_and_merging.md#probe-placement)).

**What other builds found** ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#probe-placement-and-levels-of-detail)):

- **Size:** probe size equals the world size of a pixel at that distance, rounded to a power of two, so a probe covers `[P, 2P)` pixels. Probe centres sit at `(grid_idx + 0.5)·2^grid_level`, and negative levels are allowed. Going up one cascade adds the 8 neighbours of the parent cell.
- **Key:** `grid_level mod 4` in the top two bits plus a 28-bit Z-order grid index is collision-free within its window and memory-coherent, and the parent key is a bit shift. 32-bit hashes of larger worlds collide and leave fireflies or one or two dead pixels per screen; a 2048³ world needs 33 bits. Sponza needed at most 4 levels. 28 bits give at most 9 bits per axis, a window of 512 cells per axis (derived).
- **Ray origin:** start rays at the average world position of the pixels inside the probe (count in one pass, average in a second), which keeps probes on the surface and fixed a seam where float rounding put probes on both sides of a floor. Higher cascades average up to 8 children weighted by pixel count. The pixel closest to the probe centre, found with an atomic min over a packed (distance, dx, dy) key, works better for thin features.
- **Inside geometry:** pushing cascade 0 out of the ground made a large difference; probes inside geometry gave a dark cross under spheres. Ray origins taken from pixel positions bias surfaces near the camera darker.
- **Spacing:** constant world-space spacing cost 2.7 ms from one angle and over 30 ms from another, so spacing must stay constant in screen space.
- **Level transitions** are very visible. Fading over an overlap zone costs about 25% more intervals; cubic, axis-aligned level boundaries greatly reduced artifacts; with 4× interval scaling one build needed no transition blending at all.
- **Pop-in:** spawning only the nearest upper probe made higher cascades pop in. Spawning all trilinear neighbours cost 2 to 4× the probes on flat surfaces and about 30% more in a volumetric scene.
- **Frustum-space grid** (alternative): `z_idx = log(view_z)/tan(probe_angle)` gives near-cubic froxels of one size in screen pixels, a single continuous grid with no power-of-two levels or seams, stable under sideways motion ([derivation](https://www.desmos.com/calculator/xitcustpds)). These probes change as the player moves, so they accumulate over time worse than world-space probes. Deduplicating per screen cell gave 50k to 200k probes on screen, about 2 per cell on average and 12 to 15 at most.

**Probe size in pixels.** chandra sets `lod = ceil(log2(chebyshev/1200))` with base spacing 4 to 8 scene units, so a probe spans `base/1200` to `2·base/1200` radians across its LOD band. At 1080 rows and an assumed 60° vertical field of view, that is 3.4 to 6.9 pixels across for base 4 (12 to 47 pixels of a facing surface) and 6.9 to 13.8 for base 8 (47 to 189 pixels) (derived; chandra does not fix the field of view). The size sets how many rays each probe receives per frame, below.

### Hash maps for probes

Split RC keys each table with a 64-bit integer, 18 bits per axis and 10 bits of LOD, inserted lock-free with linear probing and atomics. Values index an indirection buffer holding all directions of a probe, so the table can run at low occupancy. The tables are rebuilt each frame from the indirection buffer, which removes stale probes without deletion logic ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details)).

Other builds ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#gpu-hash-maps)):

- **Probing:** linear probing took over 20 iterations with linear and Morton keys; probing with `(hash + pcg(attempt)) % count` capped it at 6 to 8 ([paper](https://inria.hal.science/inria-00624777v1/file/paper.pdf)). Using the same probe sequence for all pixels keeps memory access coherent. 300k probes fitted with no collisions using 10 bits per axis and 2 level bits. Keep the load at or under 20 to 25%.
- **Inserting:** check whether a slot already holds the key before the compare-and-swap; only empty slots need it. Deduplicating within a subgroup first helps, since about 300 threads can hit the same probe. 64-bit keys need a Vulkan extension for 64-bit atomics. A subgroup-bucket design (buckets of subgroup size, one compare-and-swap per bucket) usually finds its slot on the first try.
- **Pipeline:** spawn entries from on-screen pixels, compact used entries into a dense list with an indirect dispatch, then trace and merge per cascade, then draw. Rebuilding the map every frame from visible and retained probes was the simplest approach. Storing the 8 dense parent indices per probe lets the merge run without hash lookups; in another build caching parents gained only 0.2 ms for a lot of memory.
- **Sizing:** allocate for the worst case of one cascade 0 probe per pixel, profile real scenes, and allocate twice the maximum. One build over-allocated 10×, with 10M probe slots per cascade and 700 MB; another needed 120k probes. 4×4-pixel patches at one megapixel give about 65k probes; 2^18 slots were enough in tests.
- **Costs:** filling a map took about 0.1 ms in one build and 0.4 ms for a 2^21 table on a laptop RTX 3060; initializing all cascades took 0.155 ms; the spatial-hashing approach of Interplay of Light's RTAO article took about 2 ms for cascade 0 alone on an RTX 2080. That figure is the poster's own; the article reports 0.4 ms cached and 1.72 ms uncached RTAO on an RTX 3080 Mobile at 1080p ([below](#spatial-hashing-for-ray-traced-ao)). Hashing at 2×2 downscale gives the same probes 4× faster. Lookups are much cheaper than insertions.
- **Sorting instead:** radix-sorting 1M 32-bit keys took 0.16 ms on an RX 9070 XT, 0.21 ms on an RTX 4080, over 1 ms on a laptop RTX 3060, and 2.84 ms in WebGPU on a GTX 1650 ([demo](https://mebyz.github.io/adaptive-radiance-cascades/df-full-radix-sort-webgpu.html)). Hashing 1080p probes with deduplication took 0.3 ms, so a sort has to beat that. Single-pass scans with decoupled look-back need forward-progress guarantees and can deadlock ([GPUSorting](#gpusorting)).
- Sparse merging ran about 50% faster than a dense SPWI merge in one comparison, probably from better cache use after compaction.

The key layouts in use:

| Build | Key | Bits | Load |
|---|---|---|---|
| Split RC paper | 18 bits per axis, 10 bits LOD | 64 | low occupancy, indirection buffer |
| chandra | 18 bits per axis plus LOD, cascade implied by the table | 64 | at most 1/4 (capacity `4·base_probes`) |
| wroughtinator native | signature, token, key low, key high, probe index in five 32-bit words | 2 × 32 | slots 2× probe capacity at cascade 0 |
| wroughtinator browser | 9 bits per axis, 2 bits LOD, 3 bits surface class | 32 | |
| Unreal Split RC port | 19 bits per axis, 4 LOD bits | 62 (61 used, derived) | table 4× cascade 0 slots |
| one sparse build | `grid_level mod 4` (2 bits) plus 28-bit Z-order index | 30 | collision-free within its window |

Sources: [Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details), [implementations](3d_world_space_implementations.md), [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#probe-placement-and-levels-of-detail).

**Under Godot's `RenderingDevice`** the Vulkan driver enables no 64-bit atomics ([RenderingDevice notes](../../docs/rendering_device.md)), so Split RC's 64-bit compare-and-swap is not available. Two existing layouts already avoid it: wroughtinator's native build splits the key across 32-bit words and claims a slot with a 32-bit signature and token, and the 30-bit level-plus-Z-order key fits a single word within a 512-cell window (inference).

## Ray splitting

**Why.** Probes near surfaces end up partly inside geometry, which over-darkens interpolated light, and outward rays from a recessed probe hit the wall at once. So Split RC spawns rays from visible surface points, as NVIDIA's SHaRC does, instead of from probes ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#ray-splitting)):

- A ray hitting at distance `t` with `t_{m−1} < t ≤ t_m` tells every cascade below `m` that its interval is transparent (`J = 0`, `β = 1`) and tells cascade `m` that it is opaque with the hit radiance (`J = L_hit`, `β = 0`).
- Each contribution is atomically added to the nearest probe and nearest direction in that cascade, with a counter; the merge divides by the count and skips directions with a zero count.
- Cascades above `m` get nothing. Extending the hit into them biases toward short rays.
- Hits closer than `t_{n−1}` are ignored for cascade `n`, so a small occluder sitting on a probe does not shadow all of its upper rays.
- Directions pointing into the surface are flipped (`ω ← ω·sign(ω·n)`), so probe directions facing into walls stay empty and are never read.
- Uniform random directions fill higher cascades badly (the coupon collector's `O(b·log b)`), so rays use the R2 low-discrepancy sequence mapped through the equal-area map ([glossary](supporting_techniques.md)). Probes sharing a parent get contiguous R2 ranges through a hierarchical prefix sum, so every cascade's directions are covered evenly, and the whole sequence is jittered per frame.
- Flat surfaces keep the ray count per cascade constant: 4× fewer probes, 4× more directions.

**What other builds found** ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#ray-splitting)):

- **The idea, restated:** a ray that hits at distance `d` gives an opaque interval to the cascade whose range contains `d` and a transparent one (radiance 0, transmittance 1) to every cascade below; averaging many rays per cone gives fractional transmittance. Vanilla RC traces about 6 rays per direction chain, one per cascade; splitting traces one.
- **When it pays:** only when one long ray costs less than several short rays plus the merge, which is true with hardware RT and its per-query overhead. Without hardware RT, plain sparse RC was simpler and faster.
- **Pitfalls:** writing only to the hit cascade lowered error from 0.15 to 0.11. Directions that get no rays must contribute nothing in the weighted merge, or fully open or fully enclosed scenes break. Rounding that forced upper-cascade opacity to exactly 0 or 1 stopped convergence. R2 directions instead of PCG random ones improved edge cases a lot, about 20% in early tests. Over-darkening appeared when every occluding ray applied half transmittance at every level.
- **Analytical splitting:** a permutation maps a cascade 0 position to a cascade `N` direction, so each ray serves `N` cascades and all directions get covered over `4^(cascades−1)` frames. Black lines came from depth-reconstructed points not matching the BVH; moving the near plane from 0.01 to 0.05 removed them.
- **Deposits:** atomic deposits took about 16 ms against 0.3 ms without atomics; sorting 10M deduplicated texels took about 1.5 ms. Writing each ray into two adjacent cascades with interpolated weights removed seams at twice the cost.
- **RC as a filter on 1-sample path tracing:** rays from a 1 spp image are binned by hit distance, and each bin is shared over an exponentially larger pixel radius. One build cast 14.7M rays per frame at 5120×2880 on an RX 9070 XT. Hashing positions and directions gives at most one entry per ray per cascade, a fixed memory budget. Against OIDN at 1 spp without temporal reuse, OIDN was blotchy and lost detail, while RC lost contact shadows. It assumes samples on surfaces, not in volumes ([2D proof of concept](https://www.shadertoy.com/view/tf3BDS)). Split RC makes the same comparison: seen as a denoiser over 1 spp rays, it reconstructs undersampled detail better than OIDN ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#extensions-shown)).

**Splitting as visibility from the receiver.** Spawning rays at the receiving surface is the same move as kajiya's choice of ray origins among the points that queried a cache cell, and SHaRC's hash of averaged path vertices: light is gathered from where it is used, so a probe embedded in a wall never fires rays from inside it ([related radiance caches](related_radiance_caches.md)) (inference).

### Samples per direction per frame (derived)

With one ray per pixel, a cascade 0 probe covering `A` pixels of a surface receives `A` rays per frame, spread over the 16 directions of its hemisphere when `|Ω0| = 32`. Each direction cell then gets `s = A/16` samples per frame. On a flat surface a cascade `n` probe covers `4^n·A` pixels and holds `4^n` times the directions, so every cascade gets the same `s` per cell (derived from Split RC's flat-surface statement).

| Probe footprint | Cascade 0 probes at 1080p | `s` | Samples behind one cascade 0 cone through cascades 1, 2, 3 |
|---|---|---|---|
| 2×2 px | 518,400 | 0.25 | 1, 4, 16 |
| 4×4 px | 129,600 | 1.0 | 4, 16, 64 |
| 6×6 px | 57,600 | 2.25 | 9, 36, 144 |
| 8×8 px | 32,400 | 4.0 | 16, 64, 256 |

A cascade 0 cone is the mean of the 4^n cascade `n` cells under it, so light that arrives through cascade `n` is averaged over `s·4^n` distinct rays, and its noise falls by `2^n` per cascade. The near field, light and occlusion inside cascade 0's own interval, rests on `s` rays per cone. At 4×4-pixel probes that is one ray: cascade 0's transmittance is 0 or 1 in each direction in a single frame, and only the 8-probe interpolation and the 16-direction cosine gather smooth it (derived).

This places the single-frame noise of Split RC at contact range, the same range the paper fills with a screen-space cascade −1 ([cascade layout](cascade_layout_and_merging.md#cascade-1-and-contact-detail)), and the same weakness the 1 spp filter comparison found (RC lost contact shadows). Larger probes buy samples at the cost of spatial detail; chandra's 12 to 189 pixels per probe give `s` from about 0.75 to 12 (derived). wroughtinator's native build caps cascade 0 at 4096 probes, so at its maximum 960×540 internal resolution the average probe covers at least 127 pixels, `s ≥ 7.9` (derived from the capacity; an upper bound on probe count, so a lower bound on `s`).

## Merge and interpolation

Split RC's cone merge and its reading as premultiplied "over" are in [core theory](core_theory.md#the-merge-operator). In world space the merge reads up to 8 parents per child, and the sparse builds record how that goes wrong ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#interpolation-and-leaks)):

- Long-distance interpolation causes most sparse 3D artifacts, and trilinear interpolation always leaks through thin walls. A fix that removed leaks through a 2 to 3 voxel cave wall: interpolate with a parent neighbour only when the nearest child rays in that direction were unoccluded, using one bit of hit/miss data per ray, at about 50% more merge time. Interpolation must be centred on voxel centres, or everything shifts half a voxel.
- Nearest spreading with linear gathering gave lower L2 error than bilinear spread and gather. Renormalize weights when trilinear neighbours are missing.
- Requesting only the nearest upper probe showed no artifacts in one build; full cube interpolation was about 4× slower.
- Split RC's remaining artifacts include leaks from interpolation during merging, seen as brightened shadows ([below](#split-rc-against-ddgi-and-a-reference)).

Parent weights follow from where parents sit. With half-cell offsets, a parent's centre is a quarter of its cell from each child's, so the 8 corner weights are `0.25^n·0.75^(3−n)` for `n` mismatched axes, `{27, 9, 3, 1}/64` (chandra, the Unreal port; [implementations](3d_world_space_implementations.md#chandra)). The parents then sit at 0.433, 0.829, 1.090 and 1.299 upper spacings from the child, with total weights 27/64, 27/64, 9/64 and 1/64 per distance (derived, [merging in 3D](../sources/2026_kurushimee_merging_3d.md#the-hand-over-in-3d-derived)). A dense grid with even probe counts gets the same per-axis (0.25, 0.75), and an odd one (1, 0) and (0.5, 0.5) (erhe).

### Leak defences in world space

Probe grids leak through walls thinner than the probe spacing. Every world-space design adds one of these defences:

| Defence | What it uses | Cost | Where |
|---|---|---|---|
| Rays from the receiving surface, flipped into its hemisphere | no probe fires from inside a wall; wall-facing directions stay empty | none beyond splitting | Split RC (above) |
| One hit bit per ray gates each parent | the child's own rays in that direction | about +50% merge time | a sparse build (above) |
| One visibility ray to each of the 8 parents | short rays from `p + t_{i+1}·d` to `u_n + t_{i+1}·d` | up to 8 short rays per texel | erhe's default merge ([implementations](3d_world_space_implementations.md#erhe)) |
| Sample each parent along the direction from it to the child interval's end | geometry of the 8 parents | 8 direction computations | SultanAladin ([implementations](3d_world_space_implementations_grids.md#other-world-probe-grids)) |
| A parent counts only if its stored hit distance does not fall short of the child | the parent's own hit distance | free | M3ycWt, yhyu13's surface charts, X3XfRM ([implementations](3d_world_space_implementations_grids.md#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes), [surface probes](3d_surface_probes.md)) |
| A parent counts only if the child's own stored ray toward the start of that parent's ray reaches it (self test) | the child's own hit distance | one texel read per parent | measured against exact references ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#the-self-test-derived-and-measured)) |
| Surface class (dominant normal axis) in the probe key | 3 key bits | more probes at thin walls | wroughtinator's browser build |
| Exclude probes deep inside walls | probe validity | none | EggyStudio, genos ([implementations](3d_world_space_implementations.md#rc-design-documents)) |
| Indoor and outdoor tags | authored tags | authoring | Love and Deepspace ([surface probes](3d_surface_probes.md)) |
| Chebyshev test on stored distance moments, backface fraction, relocation | DDGI's distance maps | a distance atlas per probe | DDGI ([related probe GI](related_probe_gi.md)); erhe keeps the distance maps for it |
| Push probes out along the SDF, kill probes whose summed ray distance is under 1 mm | the SDF | none | Enshrouded ([related probe GI](related_probe_gi.md)) |
| Offsets only: half a probe along the normal, up to one toward the camera | nothing | none | daGI2's world grid ([related engine GI](related_engine_gi.md)) |
| Ray origins chosen among the points that queried a cell, ranked by bounce | query history | per-cell rank | kajiya ([related radiance caches](related_radiance_caches.md)) |
| Resampled parent choice validated by a shadow ray | GRIS over the 4 parents | +17 to 26% rays, 2D only | Reservoir Cascades ([sampling and guiding](rc_for_sampling_and_guiding.md)) |

The rows fall into three kinds (inference):

- **Where rays start:** surface-spawned rays, query-ranked origins, SDF push-out and offsets keep a probe's rays from starting inside geometry.
- **Which parents count:** hit bits, visibility rays, hit-distance tests and resampling are binary or stochastic forms of the 2D bilinear fix ([artifacts](artifacts_and_fixes.md)) applied to the 8 parents of a 3D merge. They differ only in where the visibility comes from: a new ray, a stored bit, or a stored distance. Whose stored distance matters. A parent's rays start at its interval start `t_c`, so it records no hit nearer than that, and the parent test can drop a parent only if the parent lies farther than `t_c` plus the tolerance from the child: at the equal-error `t0` with a half-voxel tolerance that is 10/64 of the weight at the first hand-over and none above, and any parent at all only for `t0` below 2.10, 1.17 and 0.62 spacings at the first three hand-overs (derived). The child's own rays cover on average 0.64 to 0.78 of the way to each parent's interval start, so the self test reduces leaks but cannot seal. Measured in a dense voxel grid, the parent test changed nothing, while the self test halved the leak through one-voxel walls and lowered the room errors 13% to 17% ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#every-merge-measured)).
- **Which probes exist:** surface-class keys, validity flags and tags split probes that would otherwise straddle a wall.

Only the first kind is free in a single frame with no extra rays. Split RC gets it from ray splitting, and its residual leaks come from the merge, which the second kind addresses (inference).

## Shading

Split RC turns each cascade 0 probe's cones into a 6×6 octahedral irradiance map with a 1-texel border, so a pixel takes at most 8 filtered samples instead of up to 256 ([cascade layout](cascade_layout_and_merging.md#final-gather)). Other builds on drawing the result ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#interpolation-and-leaks)):

- A per-pixel trilinear gather took 27 ms of a 37.5 ms frame in one build. Rasterizing one cube per probe, twice the probe size, additively with trilinear weights took about 1 ms and handled level seams, at the cost of overdraw.
- Another build found the trilinear gather faster. Nearest sampling cost 3.6 ms against 18 ms trilinear in a third.

Irradiance from cones (cosine sampling per cone, SH against per-direction sums) is in [core theory](core_theory.md#diffuse) and [cascade layout](cascade_layout_and_merging.md#final-gather).

## Tracing for world-space cascades

World-space cascades trace the scene itself, so the tracer sets most of the cost. The tracers and their internals are in [scene representation](scene_representation_and_tracing.md). What the RC builds found about pairing a tracer with cascades ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#tracing-without-hardware-rt)):

- An optimized software ray-tracing kernel ran about 4× slower than hardware RT on Apple M3 and later. For Split RC rays on an AMD Radeon 8060S (owoDra/real-time-gi-lab #3), the best software path (a segment DDA over a hash plus a quantized 8-wide BVH) averaged 231 µs against 66 µs for hardware ray tracing, about 3.5× ([discussions](../sources/2026_rc_discussions.md#implementer-notes)).
- Sparse voxel cone tracing with naive linear marching came close to hardware RT in one build and was about 1.8× slower in another; a DDA per occupied probe with hash lookups ran 2 to 4× slower than ray tracing. Nearest-probe marching was undersampled at 4 ms against hardware RT.
- Each cascade needs a scene proxy filtered to its probe spacing, like texture mips: voxels as large as the gap between adjacent rays avoid blur and aliasing. Tracing mip `N` with cascade `N` gave blocky upscaling in an early build ([which mip](#marching-cost)). Cone tracing trades noise for blocky, aliased shadows, and replacing a cone with one ray adds aliasing, not sharpness.
- Averaging 2×2×2 voxels makes thin walls half transparent at every mip, so directional (six-direction) opacity is needed ([volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)).
- One proposal precomputes static intersections per texel and retraces only intervals that overlap the bounds of dynamic objects, through a TLAS holding only dynamic objects and capped by the static hit distance.

Ray splitting and the tracer are coupled. Splitting traces one ray per pixel to its first hit whatever the cascade, so the interval scaling no longer drives tracing cost. That removes the 94% top-cascade march share of surface-bound probes at `l = 4` ([marching cost](#marching-cost)), but only if one long ray is cheap, which is what hardware RT gives and a fixed-step marcher does not. Per-probe tracing over filtered proxies is the other consistent pairing: short rays near, coarse mips far (inference).

## Other sparse designs

- **Sparse 2D RC:** ray-march bottom-up from cascade 0, enabling parent tasks only for rays that hit nothing, then merge top-down. A contrived edge-only scene needed 340k rays against 49M dense; very dense scenes cost the same as dense RC. The design and its measurements are in [2D implementations](2d_implementations.md), and a [video of a 3D sparse version](https://www.youtube.com/watch?v=vHk4a7Nzw-c) says it was made sparse because 3D RC needs a lot of VRAM, with SPWI the alternative the author chose against.
- **Primal and dual hierarchies:** primal probes collect incoming radiance; dual probes store radiance emitted by the geometry in their cube. They share one hash map, but a missing dual probe means zero radiance while a missing primal probe means unknown, so sparse cone extensions fail.
- **Intervals instead of probes:** an occluded cascade 0 interval needs no higher intervals, so storing sparse intervals could waste about 10× less, and stored hit points allow reprojection. A one-bit-per-interval occupancy bitmap gives O(1) existence checks.
- **Surface parameterizations:** quad patches from slicing a mesh with axis-aligned planes, or 2×2 voxel blocks replaced by quads through their mass centres, merged hierarchically for higher cascades. Lightmap-UV probes grow with the scene and distort with automatic UVs.
- **Surfels plus a dense clipmap** shipped in Love and Deepspace ([3D surface probes](3d_surface_probes.md)). Surfels handle corners better than a sparse grid; one opinion called surfels pointless next to a sparse grid.

Sources: [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#other-designs).

The "intervals instead of probes" idea is the 3D form of sparse 2D RC's bottom-up enabling: a parent interval is needed only where some child interval saw nothing. Its saving grows with how enclosed the scene is, which is where dense RC wastes most (inference).

## Multi-bounce, specular and comparisons

- **Split RC's multi-bounce:** last frame's hit points spawn probes and rays for a secondary cache two LODs coarser; all hits sample it, so it feeds itself over time ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details)).
- **Other builds:** insert last frame's secondary hits into the hash map two levels coarser and resolve them over frames. Anderson or Ng acceleration could speed up infinite-bounce convergence. A two-bounce darkening bug came from shadow rays written to the bounce origin instead of its endpoint.
- **Specular:** with ray splitting, rough surfaces stop climbing cascades early, a box-filtered split-sum prefilter. Reflective gathers are 6D, so multilinear interpolation needs 64 taps. Split RC's rough specular is in [core theory](core_theory.md#specular).
- **Against DDGI:** at similar ray counts, RC's multi-level interpolation was much smoother than DDGI's trilinear. Numerically DDGI scored better in one study (RC with 8 directions was biased; error 3000 against 2500, FLIP 0.19 against 0.15), while RC looked better because DDGI over-darkened. Without multi-bounce RC was much noisier. erhe's gated comparison is in [world-space implementations](3d_world_space_implementations.md#erhe).

Sources: [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#multi-bounce-specular-and-comparisons).

### Split RC against DDGI and a reference

- Soft penumbras are resolved at every distance, because the cascade that captures them scales with occluder distance; DDGI misses penumbras smaller than its probe spacing.
- Medium-scale AO appears, from the fine on-screen probe spacing; DDGI shows none.
- Remaining artifacts: detail below the cascade 0 spacing is missed, interpolation during merging leaks (brightened shadows), only 32 cascade 0 directions add slight bias, and hard shadows are overblurred (foliage, the penumbra-condition limit in [core theory](core_theory.md#which-distance-occluder-and-light-separated)).

Sources: [Split RC](../sources/2026_freeman_split_radiance_cascades.md#quality-versus-ddgi-and-reference).

The paper places itself among earlier 3D RC: Mathis's X3XfRM keeps probes in texture space so the problem stays 2D, Coppen's Surfel RC shows visible interpolation artifacts, and Love and Deepspace uses RC to boost standard irradiance probes ([3D surface probes](3d_surface_probes.md)). It names path space filtering (Binder et al. 2021) and SHaRC (NVIDIA 2024) as using similar world-space hash maps of averaged rays ([related radiance caches](related_radiance_caches.md)), and Core Keeper and Kyora as 2D games shipping RC, an attribution that rests on the paper alone ([history](history_and_landscape.md)) ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#context-from-related-work)).

## Measurements

**Split RC** (RTX 3080 Laptop, single frame, fp32 storage, not micro-optimized; [paper](../sources/2026_freeman_split_radiance_cascades.md#numbers-rtx-3080-laptop-single-frame-fp32-storage-not-micro-optimized)):

| Stage | Sponza | San Miguel |
|---|---|---|
| Initialize probes | 1.2 ms | 1.3 ms |
| Generate rays | 0.4 ms | 0.6 ms |
| Trace rays | 1.3 ms | 4.5 ms |
| Deposit | 2.2 ms | 1.9 ms |
| Merge | 1.0 ms | 0.8 ms |
| Shade pixels | 2.5 ms | 2.4 ms |
| Total | 8.6 ms | 11.5 ms |

Cost is roughly constant across scenes because LODs keep the probe count steady; only tracing depends on geometry. The cascade −1 adds 1.4 ms ([cascade layout](cascade_layout_and_merging.md#cascade-1-and-contact-detail)).

**Other sparse builds** ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#measurements)):

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
| Variance-guided retracing: 4 full-length rays per probe in high-variance cascade 0 directions, about 2.8M long rays against 4.5M RC rays | +1 ms on a 4 ms scene, RTX 2080 Ti, also reducing leaks ([video](https://www.youtube.com/watch?v=yTxFZp_RK5U); [core theory](core_theory.md#interpolation-and-band-limits)) |

**Dense and clipmap world probes:**

| Setup | Time | Source |
|---|---|---|
| RC in a 256³ voxel volume, scale 4, RTX 4090, 1080p, worst case (jtbirdsell/voxel2026 #4) | 1.98 ms (0.17 volume, 1.55 build, 0.26 query); voxel cone tracing 2.06 ms (0.17 volume, 1.88 gather) | [discussions](../sources/2026_rc_discussions.md#implementer-notes) |
| EggyStudio world probes plus screen probes, laptop GPU, 800×450 | 0.59 to 1.00 ms | [implementations](3d_world_space_implementations.md#eggystudio3dengine) |
| erhe against DDGI | 1.15 to 1.57× DDGI's update; 0.7 ms per million rays against about 6 | [implementations](3d_world_space_implementations.md#erhe) |
| Dense 192³ CT grid, laptop RTX 4080 | 20 to 34 ms per full recalculation | [volumetric](volumetric_and_radiative_transfer.md#rc-for-ct-volumes-repository) |

In the voxel-volume comparison RC's cost follows probe count, not pixels, so the 0.26 ms query is the per-frame cost when cascades are not rebuilt. RC memory was 124 MB of cascades plus 24 MB of cubes, the largest RC pass was merging into cascade 0 (0.43 ms), and scale 2 cost 1.88 ms with 504 units of reach against 1.55 ms and 1364 at scale 4. Quality was not compared ([discussions](../sources/2026_rc_discussions.md#implementer-notes)).

**What the numbers say** (inference unless marked):

- In Split RC's Sponza run the deposit (2.2 ms) costs more than the trace (1.3 ms). With hardware RT, splitting moves the bottleneck from tracing to atomics, which matches the separate finding that atomic deposits took 16 ms against 0.3 ms without atomics, and the RTX 3080 build whose time grew 11× for 3× the rays.
- Scaling Split RC's trace by the measured 3.5 to 4× software penalty gives 4.5 to 5.2 ms for Sponza and 15.8 to 18.0 ms for San Miguel (derived). Without hardware ray queries the trace, not the deposit, would dominate a Split RC frame in a complex scene.
- Shading (2.4 to 2.5 ms) is the largest fixed cost after the deposit, and it is the stage the 6×6 tiles were added to cut, so the gather deserves as much design as the cascades.

## Temporal reuse in world space

World-space probes need no reprojection: new intervals blend into the stored ones. The patterns in use:

| Pattern | Rule | Where |
|---|---|---|
| Exponential blend | hysteresis 0.9 to 0.97; after a reset the `k`-th trace uses `h = min(hysteresis, k/(k + 1))` | erhe ([implementations](3d_world_space_implementations.md#erhe)) |
| Decayed sums | `weighted_fluence` and `weights` × 0.97 once `weights > 2`; no reset on camera motion | chandra ([implementations](3d_world_space_implementations.md#merge-and-temporal-reuse)) |
| Decay with age | weight and radiance × 0.9 when the weight passes 3 or a bin is older than 12 frames | the Unreal Split RC port |
| Sample-count average | exact running average with history capped at 16384 (static), `mix(current, previous, 0.92)` for moving lights, none above 50 ms | wroughtinator's native build |
| Counter blend | `blend = max(1/(history + 1), 0.033)` per voxel, neighbour fill for new probes | tauray RCPG ([sampling and guiding](rc_for_sampling_and_guiding.md)) |
| Fixed budget | 131,072 texels per frame round-robin, a full refresh every 64 frames (derived) | erhe |
| Spread tracing | tracing over frames with a cached hit distance per ray | Love and Deepspace ([surface probes](3d_surface_probes.md)) |
| Adaptive blend | α = 0.08 below 10% luminance change, 0.3 below 50%, 1.0 above | an O3DE Gem ([implementations](3d_world_space_implementations.md#erhe)) |
| Cached hits | reuse each probe texel's hit cell until its region's version changes or the cascade scrolls along the hit axis | Godot's HDDAGI and reduz's SDFGI plan ([Godot integration](godot_integration.md#the-sdfgi-plan)) |
| Light on demand | hits mark a coarse dirty volume, and only marked regions are relit next frame | reduz's SDFGI plan ([Godot integration](godot_integration.md#the-sdfgi-plan)) |
| Priority queue | a fixed number of probes retraced per frame, newly revealed first | Lumen's world cache ([related engine GI](related_engine_gi.md)) |
| Probability with feedback | one clip per frame; retrace chance from age, cut outside the frustum and away from surfaces, held at 6.25% of the clip | daGI2 ([related engine GI](related_engine_gi.md)) |
| Local resets | a global epoch that resets every probe on any light change is wasteful; reset only probes within a changed light's old and new reach, except for the sun and sky | Trillion3D issue #1284 ([discussions](../sources/2026_rc_discussions.md#implementer-notes)) |

Every open Split RC code blends over time even though the paper's table is single-frame: chandra, wroughtinator and the Unreal port all keep history, and none documents a single-frame mode (inference from the code notes). Temporal reuse in world space hides two different deficits that a single-frame design must meet another way: undersampling (few rays per direction cell, above) and update cost (budgets of texels or probes per frame). The first is a noise problem and the second a time problem (inference).

## Adoption and plans

- **Blackline Interactive** shows a closed-source 3D RC with HUD timings on a Radeon Pro 5500M. Its first build used world probes rebuilt on demand; the later builds point to probes on a generated surface atlas, covered in [3D surface probes](3d_surface_probes.md#a-generated-surface-atlas-blackline-interactive) ([Blackline](../sources/2026_blackline_interactive_spatium_rc.md)).
- **Trillion3D** (pasquelin, #1285): the camera-centred probe bounce (64 full-length rays per probe, SH2) had 18.6% mean error against a path-traced reference, target 10%, at 1.1 ms against a 0.8 ms budget, and Split RC was planned as the alternative ([discussions](../sources/2026_rc_discussions.md#implementer-notes)).
- The 2D games Split RC names, Core Keeper and Kyora, and the projects that chose other methods are in [history](history_and_landscape.md).

## GPU building blocks

Sparse and surfel RC designs link these for storing probes only where surfaces are: a hash table keyed by cell coordinates, a sort to group work, and Morton codes to order cells ([GPU hash tables](../sources/2026_gpu_hash_tables_and_sorting.md)). All five use only integer atomics, which Godot's `RenderingDevice` compute shaders also have. Definitions are in the [glossary](supporting_techniques.md).

| Source | Author | Date | Link |
|---|---|---|---|
| Spatial hashing for raytraced ambient occlusion | Kostas Anagnostou (Interplay of Light) | 2025-11-23, updated 2026-02-10 | https://interplayoflight.wordpress.com/2025/11/23/spatial-hashing-for-raytraced-ambient-occlusion/ |
| Maximizing Performance with Massively Parallel Hash Maps on GPUs | Jünger, Iskos, Wang, Hemstad, Hundt, Lan, Nyland (NVIDIA) | 2023-03-06 | https://developer.nvidia.com/blog/maximizing-performance-with-massively-parallel-hash-maps-on-gpus/ ; https://github.com/NVIDIA/cuCollections |
| A Simple GPU Hash Table | nosferalatu | 2020-03-08 | http://nosferalatu.com/SimpleGPUHashTable.html ; https://github.com/nosferalatu/SimpleGPUHashTable (read at `d3f5b74`) |
| GPUSorting | b0nes164 (Thomas Smith) | read at `09a6081` | https://github.com/b0nes164/GPUSorting |
| Decoding Morton Codes | Fabian Giesen | 2009-12-13 | https://fgiesen.wordpress.com/2009/12/13/decoding-morton-codes/ |

Other links the sparse builds cite: NVIDIA's SHaRC hash grid (https://github.com/NVIDIA-RTX/SHARC/blob/main/include/HashGridCommon.h), Coppen's surfel hash grid (https://github.com/mxcop/src-dgi/blob/main/assets/shaders/shared/hash.slang#L30), and mebyz's adaptive RC with ray skipping by local variance (https://mebyz.github.io/adaptive-radiance-cascades/) ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#links)).

### Spatial hashing for ray-traced AO

The post caches AO hit ratios in a world-space hash table whose cells grow with distance, then reuses cached cells instead of tracing new rays.

- Key, as printed: `H(p, s) = h(s + h(floor(p_x/s) + h(floor(p_y/s) + h(floor(p_z/s)))))`, nesting one hash per coordinate. A normal-aware key hashes `floor(n·s_n)` the same way on top; the code uses `floor(normal·3.0)`. The slot is `H % N`.
- The hash is a PCG variant: `state = v·747796405u + 2891336453u; word = ((state >> ((state >> 28) + 4)) ^ state)·277803737u; return (word >> 22) ^ word`.
- A checksum built the same way with xxhash32 (`PRIME32_2 = 2246822519`, `PRIME32_3 = 3266489917`, `PRIME32_4 = 668265263`, `PRIME32_5 = 374761393`) tells cells apart within a slot; it is forced to at least 1 because 0 marks an empty slot. The code multiplies the cell size by 10000 before hashing to spread small sizes.
- Insertion: `InterlockedCompareExchange(hash[idx], 0, checksum, cmp)` succeeds if `cmp` is 0 or the checksum. Linear probing tries 10 slots (`SEARCH_COUNT`); failure returns `0xFFFFFFFF` and the pixel shows a black cell. The post notes that rehashing distributes better but linear probing keeps cache locality.
- Each cell packs hits in the top 16 bits and samples in the low 16 bits of one uint, updated with `InterlockedAdd`, so it overflows past 65,535 samples.
- Eviction: a `hashTime` buffer stores each slot's last-use frame, and a slot unused for more than 20 frames is reset and taken over while probing. The stress test used a table of 1M entries.
- Cell size was first a constant 0.1 m (2 m AO radius, one ray per pixel), blocky up close. The distance-based size follows Gautron et al. (SIGGRAPH 2020): `h = d·tan(fov/2)`, `s_w = s_p·2h/R_y`, `s = 2^floor(log2(s_w/s_min))·s_min`, so sizes come in power-of-two steps of `s_min`. Examples use `s_p = 10` px, `s_min = 0.4`, and `s_p = 3`, `s_min = 0.07` with a 10M-cell table for the main image.
- A cell with at least 500 samples skips new rays and returns its cached ratio. With `s_p = 5` this costs 0.4 ms against 1.72 ms for uncached RTAO, which is also noisier and needs a denoiser (RTX 3080 Mobile, 1080p).
- Memory: 1M entries × 4 B × 3 buffers (hash, hashTime, spatialData), "about 11.4 MB".
- Jitter: `worldPos += JitterScale·cellSize·(random tangent and bitangent offset)` before the lookup, removed before tracing, acts as a free spatial filter.
- Limits: static scenes only, and only cells the screen touches are updated.
- Reader comments, unanswered in the text: the table has no guard band, so the last slots get fewer than 10 probes and show black squares; how eviction affects disocclusion noise; how to size the table.

### Parallel hash maps (cuCollections)

- The simplified design has fixed capacity, a sentinel empty key, key plus value of at most 8 bytes and no deletion. Buckets are a flat array of `cuda::std::atomic<pair<K, V>>` with linear probing wrapping at capacity; insertion is a compare-and-swap on the bucket, and a duplicate key returns false.
- Cooperative probing: a group of 4 threads loads a window of consecutive buckets in one coalesced read, detects duplicates with `group.any`, finds empty slots with `group.ballot`, elects the lowest with `__ffs` and broadcasts with `shfl`, then advances by the group size.
- On an A100 80GB, groups of 4 give up to 13% more insert and 40% more lookup throughput at high load factors; at low load the plain version is close to optimal.
- Random 64-bit read bandwidth (GUPS), peak and measured GB/s: Xeon Platinum 8360Y 204 and 15, A100-80GB 2039 and 141, H100-80GB 3352 and 256.
- 2^27 unique pairs of 4-byte keys and values (1 GB) at 50% load on an H100-80GB-SXM: `cuco::static_map` inserts at 87.5 GB/s and finds at 134.6 GB/s, 3.8× and 2.6× faster than Kokkos `UnorderedMap`; the fastest CPU maps are more than 10× slower.
- cuDF joins use `cuco::static_multimap` with the row hash as key and the row index as payload, resolving collisions by comparing rows.

### A simple lock-free GPU hash table

- 32-bit keys and values, power-of-two capacity, `0xffffffff` reserved as empty for both. The code uses 128M slots at 50% load, 8 bytes per slot, 1 GiB in all.
- The hash is the 32-bit Murmur3 finalizer: `k ^= k >> 16; k *= 0x85ebca6b; k ^= k >> 13; k *= 0xc2b2ae35; k ^= k >> 16; return k & (cap − 1)`. Only keys and values are stored.
- Insertion: `prev = atomicCAS(&slot.key, kEmpty, key)`; if `prev` is empty or equal to the key, a plain store writes the value; otherwise the next slot is tried, with no bound on the loop. Lookup has no bound either.
- Deletion stores `kEmpty` in the value and leaves the key, so the slot is never reused for another key; re-inserting the same key reuses it.
- The lock-free argument: keys never move, and each slot is in one of four states (empty, key only, both, value seen before key), all valid to observe, so memory ordering does not matter. With duplicate keys in one batch the surviving value is undefined; separate dispatches make it defined.
- No resizing; the suggested method is reinserting into a larger table without deleted entries. Iteration keeps slots whose key and value are both set, through an `atomicAdd` counter into a buffer sized for 64M entries.
- On a GTX 1060 laptop: 64M random inserts in about 210 ms (about 300M/s), 32M deletes in about 64 ms (about 500M/s); 984 ms with copies, allocation and iteration, 271 ms in kernels, against 70,691 ms for `std::unordered_map`.
- Insert time per 4M-key batch against load factor: 0.00 11.61 ms; 0.25 12.88 ms; 0.50 14.69 ms; 0.72 20.28 ms; 0.75 22.55 ms; 0.90 105.70 ms; 0.94 240.20 ms. Probe length averages 0.48 (max 60) at 0.50 load and 10.2 (max 6474) at about 0.97.
- At a 0.25 target load, 768 MB of a 128M-slot table sits unused.

### GPUSorting

- DeviceRadixSort: 8-bit LSD radix sort, four passes for 32-bit keys (`RADIX_PASSES 4`, `SortCommon.hlsl:55`), with a reduce-then-scan prefix across blocks in separate kernels. The README calls it the portable choice.
- OneSweep: the same binning with a chained scan and decoupled look-back (Merrill and Garland 2016; Adinets and Merrill, arXiv 2206.01784). Predecessor flags are NOT_READY 0, REDUCTION 1 and INCLUSIVE 2 (`SweepCommon.hlsl:25-28`), and `Lookback` spins on them (`SweepCommon.hlsl:268-296`). It relies on forward thread-progress guarantees; the author's rule of thumb is that anything except mobile, software rasterizers and Apple has them.
- ForwardSweep (D3D12 and Unity only): OneSweep without the forward-progress requirement. Each wave polls a predecessor flag at most once (`MAX_SPIN_COUNT = 1`); if any wave sees NOT_READY it sets a group-shared flag, and the block recomputes that predecessor's digit histogram from the raw keys and publishes it with `InterlockedCompareExchange` (`LookbackWithFallback`, `SweepCommon.hlsl:317-395`). The fallback needs no cross-block cooperation, but the predecessor keys must stay unmodified during the pass. The sparse builds name it as the variant that needs no forward-progress guarantee.
- EmulatedDeadlocking (D3D12 and CUDA) emulates GPUs without forward progress, so the fallback path can be tested on any hardware. SplitSort (CUDA) is a proof-of-concept segmented sort.
- Defaults (`SortCommon.hlsl:14-46`): 512 threads per group, 15 keys per thread, 7680 keys per partition, radix 256, 7936 uints of shared memory, at most 65535 groups per dispatch. Wave size is handled at runtime (16 or more lanes against fewer, with bit-packed histograms below 16); tested on 4, 16, 32 and 64 lanes.
- D3D12 buffers are `globallycoherent` and flags use interlocked stores; a Vulkan port needs the same coherence on the flag buffer (inferred; the repository does not discuss Vulkan).
- Throughput read from the README charts (2^28 uniform random uint32, RTX 2080 Super, elements/s): OneSweep keys 1.09e10 (CUB), 1.10e10 (CUDA), 9.67e9 (D3D12); DeviceRadixSort keys 7.69e9, 7.69e9, 7.38e9; OneSweep pairs 5.15e9, 5.74e9, 5.46e9; DeviceRadixSort pairs 3.40e9, 4.80e9, 4.77e9. On an RX 7900 XT under D3D12: OneSweep keys 1.57e10, DeviceRadixSort keys 1.13e10, pairs 8.17e9 and 6.52e9. FidelityFX ParallelSort reaches about 1.7e9 to 2.1e9 keys/s on the same sweep, where OneSweep reaches 7.6e9 to 9.7e9. ForwardSweep has no published numbers.

### Morton codes

- Encoding: 2D `(Part1By1(y) << 1) + Part1By1(x)` for 16-bit inputs; 3D `(Part1By2(z) << 2) + (Part1By2(y) << 1) + Part1By2(x)` for 10-bit inputs. Decoding applies `Compact1By1` or `Compact1By2` to the code shifted by the axis index. The spreading masks are in the [glossary](supporting_techniques.md).
- `Compact1By1`: `x &= 0x55555555; x = (x ^ (x >> 1)) & 0x33333333; x = (x ^ (x >> 2)) & 0x0f0f0f0f; x = (x ^ (x >> 4)) & 0x00ff00ff; x = (x ^ (x >> 8)) & 0x0000ffff`.
- `Compact1By2`: `x &= 0x09249249; x = (x ^ (x >> 2)) & 0x030c30c3; x = (x ^ (x >> 4)) & 0x0300f00f; x = (x ^ (x >> 8)) & 0xff0000ff; x = (x ^ (x >> 16)) & 0x000003ff`.
- A reimplementation of these masks passed all single-axis cases and 200,000 random 2D and 3D round trips against a bit-by-bit reference.
- Method: for a 1:2 spread, bit `N` moves `2N` places, built from power-of-two moves in turn; a move is safe with XOR only when the target bits are empty. For non-square 2D, Giesen suggests rounding each axis to a power of two and packing the major axis linearly once the minor axis runs out of bits. For 64 bits Giesen recommends generating the masks with a small program.

Sources: [GPU hash tables](../sources/2026_gpu_hash_tables_and_sorting.md).

### In Godot's `RenderingDevice`

- The AO cache and nosferalatu's table need only 32-bit compare-and-swap and add, so they port directly; Split RC's 64-bit keys do not (no 64-bit atomics in Godot's Vulkan driver, [RenderingDevice notes](../../docs/rendering_device.md)).
- The AO post's 16-bit packed counters overflow at 65,535 samples; RC deposits as fixed-point sums need the same care, which wroughtinator handles with a scale of 4096 and a clamp at 16, and the Unreal port with `uint(value·10000)` (inference).
- nosferalatu's load table shows insert time flat up to 0.5 load and 9× worse at 0.9. The sparse builds' advice to stay under 20 to 25% load trades memory for short probe chains, which matter more on a GPU whose threads wait for the slowest lane (inference).
- OneSweep's decoupled look-back can deadlock without forward-progress guarantees, which a portable engine cannot assume; DeviceRadixSort's separate reduce and scan passes, or ForwardSweep's fallback, are the safe choices (inference).
- cuCollections' cooperative probing is subgroup ballot and shuffle, which Godot exposes through `GL_KHR_shader_subgroup` with a runtime subgroup size ([RenderingDevice notes](../../docs/rendering_device.md)).

## Connections

- **One idea under four names.** Sannikov's per-pixel tile resolution, Split RC's Chebyshev LOD, Interplay of Light's distance-scaled cells (after Gautron et al. 2020) and SHaRC's hash grid all tie a cell's world size to its projected size, so storage follows the screen while values stay in the world. Split RC adds the cascade hierarchy over that cache (inference).
- **Splitting is a receiver-side gather.** Spawning rays at visible surfaces is the shared answer of Split RC, SHaRC, path space filtering and kajiya's query-chosen origins to probes embedded in geometry ([related radiance caches](related_radiance_caches.md)) (inference).
- **`l = 4` and splitting fit together.** Equal error asks for `l = 4`, which makes per-probe marching dominated by the top cascades (94% for surface-bound probes); splitting traces each ray once to its first hit, so its cost no longer depends on `l` (derived above).
- **The bilinear fix in 3D.** Hit bits, erhe's visibility rays, parent hit-distance tests and Reservoir Cascades' validated parents are the 2D bilinear fix in binary, stored or stochastic form for 8 parents ([leak defences](#leak-defences-in-world-space)).
- **Small emitters leave RC everywhere.** EggyStudio lights emitters no larger than twice the cascade 0 spacing analytically, wroughtinator's browser build cuts emitters within `1.5·ds0` and adds them back analytically, and creikey caps injected emitter radiance and adds an analytic falloff ([implementations](3d_world_space_implementations.md)). erhe, without such a term, fails its 0.25 m emitter gate at 1.5 m spacing. All are the penumbra condition's limit: light smaller than the cascade 0 spacing cannot be resolved by cascade 0 ([core theory](core_theory.md#the-penumbra-condition)) (inference).
- **erhe's far-field failure is `l = 2`'s drift.** erhe grows intervals only 2× per cascade, starts at `r0 = 3.46·s0` against the equal-error 2.26 for 64 directions, and fails its corridor far-field gate. That matches the 2D finding that `l = 2` drifts from aliasing near to blur far away ([core theory](core_theory.md#two-criteria-for-interval-scaling-derived)) (inference).
- **Dense grids are memory-bound and sparse ones atomic-bound.** Dense codes fail on gigabytes, while Split RC's measured bottleneck is the deposit; neither is limited by the merge, which is about 1 ms in both families' measurements (inference from the tables above).
- **Volumetrics stay with world space.** Sparse surface probes hold radiance only near surfaces; fog needs the dense or clipmap form over a bounded region ([volumetric](volumetric_and_radiative_transfer.md#volumetrics-in-3d)).

## Single-frame assessment

- **Split RC is the evidence.** It is the first full world-space 3D RC with a published evaluation and the only one with a published single-frame evaluation: 8.6 ms in Sponza and 11.5 ms in San Miguel on an RTX 3080 Laptop with hardware RT and fp32 storage, one diffuse bounce, no temporal reuse. Sannikov's sparse videos (60 to 100 fps, then 60 fps with hardware RT, all from scratch) point the same way without numbers, and Blackline's single-frame results without RT hardware come from a surface atlas, not a world grid ([surface probes](3d_surface_probes.md#a-generated-surface-atlas-blackline-interactive)).
- **Its noise floor is the cascade 0 near field.** With one ray per pixel, each direction cell gets `s = A/16` rays per frame for an `A`-pixel probe: one ray at 4×4-pixel probes, so cascade 0's transmittance is binary per direction in a frame, while far light is averaged over `s·4^n` rays (derived). The single-frame levers are bigger probes (more `s`, less detail), more rays per pixel (which grew cost 11× for 3× rays in one build), and a cascade −1 for contact light.
- **Without hardware ray queries the trace dominates.** Scaling by the measured 3.5 to 4× software penalty puts Sponza's trace at 4.5 to 5.2 ms and San Miguel's at 15.8 to 18.0 ms (derived), against a 1.3 to 4.5 ms deposit and merge budget. A compute tracer whose cost grows slowly with ray length (a BVH or a hierarchical DDA, [scene representation](scene_representation_and_tracing.md)) is a precondition for splitting under Godot's `RenderingDevice`; with a fixed-step marcher, per-probe tracing on filtered proxies is the consistent alternative (inference).
- **The atomics have to be 32-bit.** Hash keys must fit 32-bit words or a multi-word slot (wroughtinator's five-word slots), and deposits must be fixed-point integer sums with a clamp, since Godot's driver has neither float nor 64-bit atomics ([RenderingDevice notes](../../docs/rendering_device.md)).
- **No CPU round trips.** chandra reads probe and ray counts back to the CPU twice per frame to size dispatches; a single-frame pipeline sizes them with indirect dispatch arguments written on the GPU, as wroughtinator's compaction does and as Godot's `RenderingDevice` supports (inference).
- **One bounce per frame.** Split RC's multi-bounce feeds a coarser secondary cache over frames. A single-frame second bounce needs a second solve. Two LODs up (`lod + 2`), at 4× the spacing, it has 1/16 of the probes and rays of the first on probes that follow surfaces and 1/64 in a filled volume, and it carries `ρ/(1 + ρ)` of two bounces' light, a third at albedo 0.5 (derived, [check](../checks/bounce_energy_share.py), [energy per bounce](light_transport_alternatives.md#multi-bounce)). One bounce plus an ambient or sky term is the single-frame baseline (inference). Re-merging the first solve's stored hits gives every bounce with no rays: in a `32³` voxel lab a pass costs 0.42 to 0.97 of a solve's reads and voxel steps, GMRES converges in 2 to 5 passes, and the merge's leak deficit decides the accuracy, vanilla's converged bias at albedo 0.9 reaching −44% to −59% in rooms where the trilinear fix behind two-voxel walls keeps its first-bounce −15% (−2% at 128 directions) (measured, [bounces in one frame](../sources/2026_kurushimee_bounces_one_frame.md#bounces-in-3d-measured)).
- **Dense grids are out for whole scenes.** At 128³ and 32 directions a dense stack is 1 GiB in fp16 and 132 M rays (derived). A 32³ to 64³ local volume (16 to 252 MiB) fits memory and could light a bounded fog region ([volumetric](volumetric_and_radiative_transfer.md)).
- **Leaks without history.** Ray splitting removes probes firing from inside walls for free; merge leaks then need a binary parent test, of which the one-bit hit mask (+50% merge time) and the parent hit-distance test (free) need no extra rays (inference). In a dense grid at the equal-error `t0` the parent hit-distance test cannot act above the first hand-over (derived) and changed nothing measured; the free test that works is the self test, along the child's own stored rays, which halves the merge leak; sealing needs rays toward the parents ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#every-merge-measured)).
