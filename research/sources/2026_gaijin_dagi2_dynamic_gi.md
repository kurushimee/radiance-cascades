# daGI2: Gaijin's open-source dynamic GI (Dagor Engine)

| | |
|---|---|
| Repository | https://github.com/GaijinEntertainment/DagorEngine (BSD-3-Clause), read at commit 2baf194 |
| Code | `prog/gameLibs/daGI2/` (GI), `prog/gameLibs/daSDF/` (world SDF), `samples/testGI/` (sample app) |
| Predecessor | daGI in Enlisted: "Scalable Real-Time Ray Traced Global Illumination for Large Scenes", Anton Yudintsev, GDC 2019, https://gdcvault.com/play/1026469/Scalable-Real-Time-Global-Illumination, written up at https://enlisted.net/en/news/show/25-gdc-talk-scalable-real-time-ray-traced-global-illumination-for-large-scenes-en/ (2 May 2019) |

Not RC. daGI2 is the dynamic GI of Gaijin's engine, and all of its C++ and shader source is open. It needs no hardware ray tracing: rays march a signed distance field (SDF) clipmap, and hits read light from a voxel copy of the lit frame. It is the closest open match to a world-space RC in Godot, because it splits rays into intervals much like RC does. Screen probes trace a few world-probe sizes and then read a world probe clipmap, and world probes that scroll into a clip trace a few coarser-probe sizes and then read the next coarser clip.

## Contents

- [Pieces and defaults](#pieces-and-defaults)
- [Frame flow](#frame-flow)
- [World SDF](#world-sdf)
- [Voxel lit scene](#voxel-lit-scene)
- [Albedo and media scenes](#albedo-and-media-scenes)
- [Screen probes](#screen-probes)
- [Radiance grid](#radiance-grid)
- [Volumetric GI](#volumetric-gi)
- [Problems recorded in todo.txt and comments](#problems-recorded-in-todotxt-and-comments)
- [daGI v1 in Enlisted (2019)](#dagi-v1-in-enlisted-2019)
- [Lessons for RC in Godot](#lessons-for-rc-in-godot)

## Pieces and defaults

`DaGISettings` in `daGI2.h` turns each piece on with a nonzero size.

| Piece | Default | What it holds |
|---|---|---|
| World SDF (daSDF) | 5 clips, 128 voxels wide and half as tall, 0.15 m voxels in clip 0 | distance in an R8 narrow band |
| Voxel lit scene | half the SDF resolution, SDF clip 1 and up, 6 directions per voxel | outgoing radiance (R11G11B10F) and coverage (R8) |
| Albedo scene | 2 clips | sparse 8³ blocks of albedo |
| Media scene | 3 clips, 32 voxels wide | in-scatter and density of fog and foliage (RGBA16F) |
| Screen probes | 16-pixel tiles, 8×8 octahedral radiance | diffuse GI per pixel |
| Radiance grid | 3 clips, 32 probes wide, 8×8 octahedral | world radiance probes, plus an SH1 irradiance grid |
| Volumetric GI | 64-pixel tiles, 16 slices | froxel irradiance for fog |
| Sky visibility | off | SH1 sky visibility, used instead of the radiance grid at the lowest quality |

- The sample app has three GI modes. "Only AO" runs sky visibility alone. "Colored" runs the radiance grid with a denser irradiance grid and two extra irradiance clips, and no screen probes. "Screen probes" runs everything. It sets the tile size from the screen height, 8 pixels at 1080p, and re-traces half the screen probes each frame.
- The lit scene, SDF depth marking and parts of the grids read and write the same texel in one pass (typed UAV loads). daGI2 checks R8, RGBA8, RGBA16F, R11G11B10F and R16F at start-up, and if any one lacks it, the lit scene is turned off.
- No timing appears anywhere in daGI2. Every per-frame budget is a count.

## Frame flow

1. `beforeRender` copies the new settings, clamps them and creates or frees pieces.
2. `updatePosition` scrolls the clipmaps: albedo, media, the world SDF, then the radiance grid. The SDF rebuild rasterizes collision geometry for the region that scrolled in, and the same pass writes first-guess lit voxels there; the sample culls its lights to that region for it.
3. During lighting, `beforeFrameLit` places and traces screen probes, then volumetric GI.
4. `afterFrameRendered` feeds the finished frame back. On alternate frames it removes SDF where depth shows empty space, or marks SDF from depth. Then it updates the lit scene, albedo and media from the G-buffer, and runs the radiance grid's probe updates.

## World SDF

- **Layout:** clip i has voxel size 0.15·2ⁱ m, so clip 0 is 19.2 m wide and clip 4 is 307 m wide. One R8 3D texture holds every clip, each with a copy of its top and bottom slice so filtering wraps. Addressing is toroidal. Only a band of ±4 voxels is stored: value a decodes to (2a − 1)·4 voxels, and empty space reads as +4 voxels. A clip takes about 1.1 MB.
- **Build** for a scrolled region, with no jump flood:
  1. Clear a 32-bit scratch buffer over the region plus one voxel.
  2. Write candidate distances from geometry with `InterlockedMin`. The sign sits in bit 0, so an unsigned minimum orders by magnitude.
  3. Relax: each voxel takes the minimum over its 26 neighbors of neighbor distance plus offset length. One pass by default; the code notes that more passes give a better field.
  4. Write the result into the R8 clip, then copy the border slices.
- **Geometry sources:** collision meshes, rasterized with a pixel shader below a voxel-size threshold and voxelized in compute above it. Each rasterized pixel writes its voxel and the six face neighbors with the exact distance to its triangle.
- **Updates from the depth buffer** keep moving objects and opened doors current without re-rasterizing:
  - Marking: random depth pixels each write a 4×4×4 block of distances to the pixel's point, only lowering values. 12.5% of them go to a coarser clip.
  - Removal: random points along random view rays, up to 128 m. If a voxel's band box lies wholly in front of the hierarchical depth (HZB) on screen, its distance is raised.
- **Scrolling:** clips snap to 2 voxels and rebuild only after moving 4 voxels. Only the newly exposed slab is rebuilt, coarsest clip first and at most one clip per frame.
- **Tracing:** march with step `max(d − 0.5·voxel, 0.25·voxel)`. A hit is `d` below a surface bias that grows from 0 to half a voxel over the first voxel of travel, so rays leaving a surface do not hit it. There is no step limit. A ray that leaves a clip starts in the next coarser clip one finer voxel back, because the coarse clip likely hits earlier. Normals come from 6 taps at ±0.5 voxel. A soft-shadow variant uses k = 8.
- **Object SDFs:** daSDF also has an offline mesh-SDF baker and a sparse object atlas merged into the clipmap, but `HAS_OBJECT_SDF` is 0, so that path is compiled out.

## Voxel lit scene

- **What it stores:** the light leaving surfaces, in 6 slots per voxel (± each axis, picked by the signs of the surface normal), at half the SDF resolution from SDF clip 1 up. Its finest voxel is 4 times the SDF clip-0 voxel, 0.6 m by default.
- **From the frame:** each frame takes 128 + 8192 × speed random pixels, spread over screen tiles. Each goes to the finest clip that holds it, or a coarser clip 12.5% of the time, because coarse clips are seen less. It reads the pixel's final lit color plus emission. That color already includes GI, so bounces build up over frames. It blends into the three slots facing the normal with weight 0.05 × the normal's component, or replaces a slot that was empty.
- **Stable mode** averages 64 jittered taps on a disk half a voxel wide, keeping only taps in the same voxel, facing the same way, and not on dynamic objects.
- **Off screen:** rasterized collision geometry is lit by a project callback (default 0.1 × albedo) and written with alpha 32/255, so screen updates soon outweigh it.
- **Reading at a ray hit:** loop over clips, finest first. Divide filtered radiance by filtered alpha. With 6 slots, weight the three slots facing the normal by the squared normal and their alpha. If no clip has data, use the albedo scene times the project's hit lighting.
- **Teleports:** a shader gate stops lit-scene writes where the irradiance grid is not yet valid, so a brief low-detail ambient does not get baked into voxels that outlast it. The sample also waits up to 24 frames for its scene data around the camera to be ready before updating radiance.

## Albedo and media scenes

- **Albedo:** sparse. Each clip is a toroidal window of 8×8×8-texel blocks. A uint per window cell points into a 256×256×N atlas, and free blocks sit on a LIFO stack with an atomic counter. A thread claims a cell by swapping in a token with compare-and-swap; other threads spin 32 times, then recover a stranded token. The atlas is sized for half the window by default. G-buffer samples blend in 5% at a time, and a background pass fills empty texels from their neighbors over 32 frames.
- **Media:** a dense RGBA16F volume per clip: in-scatter times density in rgb, density in alpha. 256 taps around a voxel measure how much translucent surface covers it, and density = −log2(1 − coverage) / voxel size. Rays march it with exact in-scatter per step. The comments warn that 16×16 taps miss sparse leaves, so forests can leak skylight, and that canopies lit from below converge dark unless updates ignore small changes.

## Screen probes

**Placement**

- One probe per tile (8 to 32 pixels), plus extra probes on tiles with depth edges, from a pool of 0.75 × the probe count at 16-pixel tiles. The pool grows with tile area.
- A probe keeps last frame's pixel if that pixel reprojects into the tile and its depth still matches; otherwise it moves to the tile center. The comment says that re-placing probes every frame under TAA jitter breaks temporal reuse and makes them blink.
- Extra probes are added over up to log2(tile size) passes. Each pass finds the tile pixel least covered by nearby probes, where coverage is `exp2(−10000 · d²)` and d is the pixel's distance to each probe's surface plane. A probe goes there if coverage is below 0.01.

**Tracing**

- Rays per probe: about radiance resolution / √2 squared, so 36 rays (6×6) for 8×8 radiance. Blue noise jitters them per tile and rotates each frame, because one offset shared by neighbors shows as shimmer.
- Each ray first marches the screen: 16 linear samples on half-resolution depth. A comment puts its cost at 10% to 30% and credits it with better quality and stability. If it does not hit, the ray continues as a project trace hook (hardware RT or a BVH) or an SDF march. The SDF march starts pushed out along the normal by up to half the screen-ray length, because the screen trace skips thin meshes.
- Hit light: last frame's lit pixel where the hit reprojects with depth within 5%, otherwise the voxel lit scene.
- Ray length inside a radiance grid clip is 3 to 6 grid probe sizes: 3 for new probes, rising to 6 as they settle. Outside the grid it is 64 m.
- A miss reads the radiance grid at the ray end pulled back half a grid probe, so trilinear filtering does not reach through a wall, or the sky outside the grid.

**Filtering and output**

- Temporal: a probe's first samples weigh 1, 1/2 and 1/3, then 0.025 each frame. Moving probes use 0.125. Probes on moving objects within 50 m reproject by motion vectors.
- Spatial: the 4 nearest neighbors always, plus diagonals and the next ring (12 in all) for new or moving probes, weighted by distance to the center probe's plane. An optional angle weight uses each neighbor's hit distance and needs RGBA16F storage; the settings comment says it changes little.
- Irradiance: a 6×6 octahedral map per probe (plus a 1-texel border), the cosine-weighted average of the radiance texels, or a projection to 3-band SH. The octahedral maps are equal-area, so every texel has the same solid angle.
- Encoding: values are rounded before being stored as R11G11B10F, because hardware truncates and temporal blending then drifts the image yellow. The screen GI buffer stores squared color (gamma 2) for the same reason.
- Upsampling: the 4 nearest probes, with bilinear weights times a plane-distance weight. An extra probe replaces a corner when its weight is higher.

## Radiance grid

- **Layout:** up to 4 clips of 32 × 32 × d probes, 8×8 octahedral R11G11B10F texels per probe, probe size doubling per clip. A separate SH1 irradiance grid is projected from it, or traced on its own when denser. The SH1 is packed into RGBA8 plus RGBA16F, with blue rebuilt from luminance and the red and green ratios.
- **Scrolling:** probes that enter a clip are traced at once, written without blending and marked young.
- **Which probes update:** one clip per frame. Each probe is tested once every 8 updates of its clip, in a stride pattern. Its chance to be picked starts from its age (young probes about 8 times likelier), is cut to 1/16 outside the frustum or behind the HZB, and cut to 1/16 again with no surface within 3 probes. A feedback multiplier steers the count to 6.25% of the clip, and the picked probes are traced by indirect dispatch.
- **Rays:** 64 per probe, one per texel, by SDF march or the project trace, up to 128 m, reading the sky on a miss.
- **Hand-off on scroll-in:** when a probe enters a clip, its rays stop at 4 probe sizes of the next coarser clip (8 of its own) and read that clip's texel for the same direction, interpolated from its 8 nearest probes at the end point pulled back √3 coarser probe sizes. A comment says that features smaller than 1/4 of the solid angle can be missed, and that this is about 16 m against 128 m, so 8 times fewer traces. The ongoing updates turn this off and trace the full length.
- **Blending:** new probes average up to 27 samples (weight 1/n). An invalidated region marks its probes as quick-updating, and they then blend with weights from 0.3 to 1 for up to 36 updates.
- **Sampling:** the finest clip holding the point, offset half a probe along the normal and up to one probe toward the camera, blended into the next coarser clip over a dithered border. There is no visibility term; these offsets are the only leak control.

## Volumetric GI

- Froxels on 64-pixel tiles with 16 exponential slices, out to half the radiance grid's reach. Near slices trace a 3×3 octahedral map per froxel, up to 1.5 grid probe sizes, reading the lit scene at SDF hits and the radiance grid otherwise.
- Each froxel stores SH1 with temporal reprojection, at 3% new per frame. Far slices and quality 0 just sample the irradiance grid.

## Problems recorded in todo.txt and comments

- Large lit-scene voxels leak more light than the SDF plus albedo, so the number of lit clips is capped.
- The first voxelization of a region comes out too bright in corners, because the irradiance grid is undersampled, and the lit scene and the SDF depend on each other.
- DX11 has no typed UAV loads, which disables the lit scene there.
- 32-pixel tiles are needed at 4K.
- Sparse foliage needs its own handling: the media scene, and a top-down "trees above" depth map whose consumer is outside daGI2.

## daGI v1 in Enlisted (2019)

The talk page names the speaker Anton Yudintsev and has no public slides (members-only on GDC Vault); the Enlisted write-up is the readable source, and its formulas are images. What it adds beyond the summary below:

- The three irradiance levels cover 1/8, 1/4 and all of a camera-centered box with the same texel count, so texel size doubles per level, and all live in one volume atlas. Ambient cubes sit in three hardware-filtered volume textures because a lit pixel never needs both the positive and negative direction of an axis. Texture dimensions are not given.
- The scene clipmap's nested grids share their texture size and hold only already-lit voxels, with colour and opacity.
- Cells are picked stochastically with a probability set from how many cells passed in the previous frame. Queue A holds cells that intersect the scene (512 to 1024), A' the never-updated ones among them, processed first, and queue B (64 to 128) cells that touch no geometry, which still light dynamic and transparent objects. One compute pass fills the queues and an indirect dispatch relights them. New fine cells start from the coarser level; the coarsest starts in a "new" state lit by a few rays.
- Tracing is Monte Carlo through the voxel grid, one thread group per cell and one thread per ray with a parallel reduction, accumulated over time with a weight from the cell's age; "thousands of rays" per scene, no per-cell count. Voxel cone tracing was rejected because it reports thin obstacles as partial occluders (Fig. 3).
- New scene voxels can be filled from heightmaps, cascaded shadow maps, GPU-voxelized collision or low-LOD models, which mostly helps opacity and so bleeding; static scenes need no removal, and changed regions are invalidated.
- Diffuse shading samples the finest available level, blended toward the next to hide seams. Glossy reflections and eye-ray hits come from the voxel scene with parallax correction (Lagarde and Zanuttini 2012); hardware ray tracing could improve the voxel casts while voxels keep supplying radiance.
- Memory: irradiance 13.5 MB, scene 16.5 MB (33 MB at higher quality), temporal buffers under 1 MB, about 31 MB in all; the text gives 32 to 62 MB overall. Costs: movement 0.1 to 1 ms spread over 8 to 16 frames (about 0.1 ms), scene feedback about 0.02 ms, irradiance update 1.2 ms (async or optional), extra lighting at 1080p 0.3 ms.
- Limits: bleeding where fill data or opacity is missing, over-dark ground under foliage, no glossy from the irradiance map, dynamic objects excluded from voxel updates, and a camera-centered extent.

- The scene was a nested clipmap of lit voxels, filled from random G-buffer pixels each frame, as in daGI2. New voxels were seeded from heightmaps, shadows or collision to reduce bleeding.
- Irradiance lived in 3 nested cascades of ambient cubes (6 directions in 3 textures, for hardware trilinear). Cells were picked at random by age after frustum and HZB culling, in two queues: 512 to 1024 cells touching geometry, zero-age ones first, and 64 to 128 in open air. Each cell was one thread group with one thread per ray, and new cells started from the coarser cascade.
- "Convex offset filtering" moved samples off the border of the convex volume to stop leaks. Sparse foliage over-darkened the ground; the fixes were skipping its pixels or storing opacity.
- Measured: 0.57 ms in all on a GTX 1070. On Xbox One, 0.7 ms with one bounce or async and about 1.6 ms with synchronous multi-bounce, with the irradiance update itself at 1.2 ms. Updating voxels from 100,000 pixels took under 0.2 ms. Memory was about 31 MB: 13.5 MB of irradiance and 16.5 MB of scene.

## Lessons for RC in Godot

- **Interval hand-off.** Screen probes stop a ray after 3 to 6 grid probe sizes and take the rest from the grid, and grid probes that scroll in stop at 4 coarser-clip probe sizes and take the rest from the coarser clip. That is the RC merge with a single direction fetch. The far read is pulled back half a probe or √3 probes so filtering does not reach through walls. A world-space RC can reuse these lengths and the pull-back.
- **Light from the lit frame.** The lit-scene voxels give every off-screen hit a radiance value, with extra bounces for free, without relighting any voxels.
- **An SDF from atomics.** The narrow-band SDF needs only `InterlockedMin`, one relaxation pass, and depth marking and HZB removal for moving things. Godot's compute shaders have the integer atomics this needs.
- **Format support.** The read-modify-write passes need storage loads of R11G11B10F, R8 and RGBA16F. `RenderingDevice.texture_is_format_supported_for_usage` can check this at start-up, as daGI2 does.
- **Count budgets with feedback.** Picking probes by probability and steering the count with a feedback multiplier keeps cost flat as the camera moves.
- **Round before packing.** Writing R11G11B10F without rounding drifts accumulated light yellow.
