# Related engine GI

Four shipped or open engine GI systems solve the problem RC solves, light from every direction at every visible point, with layered caches instead of one cascade rule: Unreal's Lumen, AMD's Brixelizer GI, Gaijin's daGI2 and Tencent's HSGI. None is RC, but each splits rays into a near and a far part with a hand-chosen hand-off, fights the same leaks, and has measured costs on real hardware. Their tracers and scene structures (Lumen's distance fields and surface cache, Brixelizer's bricks, daGI2's SDF and lit voxels, HSGI's voxel cache) are in [scene representation](scene_representation_and_tracing.md); this topic covers how they gather light, what they cost, and what they teach a single-frame RC. Godot's own SDFGI and HDDAGI are in [Godot integration](godot_integration.md#sdfgi-the-shipped-gi), and GI-1.0, which Brixelizer GI simplifies, is in [radiance caches](related_radiance_caches.md#gi-10).

| System | Near field | Far field | Hand-off | Tracer | Reported cost |
|---|---|---|---|---|---|
| [Lumen](#lumen) | screen probes, 8×8 directions, one per 16 px | world probes, 32×32 directions, to 200 m | screen ray of about 2 m, then the world probe | screen, mesh SDF, global SDF or hardware RT | 2.77 to 11.31 ms on PS5 at 1080p |
| [Brixelizer GI](#brixelizer-gi) | screen probes, 8×8 directions, one per 8×8 tile | SH2 per brick | blended at the pixel | sparse brick SDF, compute only | 1.7 to 2.2 ms |
| [daGI2](#dagi2) | screen probes, 8×8 radiance, 16 px tiles | radiance clipmap of 8×8 probes | screen ray of 3 to 6 grid probe sizes | screen march, then SDF clipmap | no timings; counts only |
| [HSGI](#hsgi) | ReSTIR GI (PC) or screen probes (phones) | DDGI-style probe volume and voxel cache | trace-probe mode: one probe size, then the probe | Hi-Z, HDDA voxels or hardware RT | 8.53 ms on an RTX 3080; 3.18 ms on an iPhone 13 Pro |

## Lumen

Wright, Narkowicz and Kelly, "Lumen: Real-time Global Illumination in Unreal Engine 5", SIGGRAPH 2022 Advances in Real-Time Rendering ([slides](https://advances.realtimerendering.com/s2022/SIGGRAPH2022-Advances-Lumen-Wright%20et%20al.pdf), 200 pages with speaker notes; [notes](../sources/2022_wright_lumen_siggraph_advances.md)), with Wright's 2021 course talk on its final gather, the Lumen technical-details docs and performance guide, and a May 2022 tech blog. It is the most complete shipped account of a layered GI cache. Page numbers are slide numbers.

### Cache levels

The opaque final gather has four levels from near to far, each given the precision its range needs (p. 168):

| Level | Range | Directions per probe | Notes |
|---|---|---|---|
| Contact AO | 16 px | | applied after the temporal filter so it has no lag; restores shadow detail lost to probe downsampling |
| Screen radiance cache | up to about 2 m of world tracing | 8×8 | one probe per 16 px in each dimension, more where geometry is detailed |
| World radiance cache | out to 200 m | 32×32 | clipmaps with bounded probe spacing on screen; the screen-probe ray is shortened and the world probe interpolated on a miss |
| Skylight | beyond | | updated over many frames |

- The world cache has 16 times the screen cache's directional resolution and far lower spatial resolution, which keeps its error stable in world space (p. 161). The shortest range cannot afford latency and the skylight can afford a lot (p. 168).
- World probes persist in a free list. Each frame keeps last frame's probes that are still needed, traces probes revealed by camera motion, and retraces a fixed number chosen from a GPU priority queue to propagate lighting changes, so cost is fixed and latency varies (p. 163). Too low a budget makes lighting pop in during fast camera motion (performance guide).
- Emissive-lit scenes (The Matrix Awakens at night) rely on the world cache, whose higher directional resolution resolves small emitters more accurately and stably (p. 164).
- A low-cost mode, Irradiance Field Gather (for Switch 2 and low-end PCs), places world-cache probes around pixels, precomputes their irradiance and interpolates with probe occlusion; probes left inside geometry are not used (performance guide).

### Screen probes

- Probes sit on pixels of a uniform grid, subdivided where geometry is detailed; the grid is jittered and accumulated over time (pp. 146, 153). Pixels interpolate only from probes on the same plane, which limits leaks (p. 146).
- **Product importance sampling.** Rays follow the product of the BRDF and the incoming light, culling unimportant directions and supersampling important ones, with a whole thread group per probe (p. 158). The light estimate is last frame's screen cache reprojected, with the world cache as fallback where reprojection fails, such as screen edges (p. 157). The speaker puts the gain at the quality of four times the rays for the same ray count (p. 159).
- **Spatial filtering in probe space:** 3×3 probes cover 48×48 pixels and need only probe positions, not every pixel's position and normal (p. 156).
- **Temporal filter:** at full resolution, history is rejected by depth and normal with no neighbourhood clamp, because jittered probe positions need a reliable history. That is stable but slow to react (ghosting), so accumulation speeds up where rays hit fast-moving objects (pp. 166-167).
- **Reflections:** rough reflections (roughness 0.4 to 1, often half the screen) reuse the screen cache instead of tracing, which cuts reflection cost by 50 to 70%; glossy ones (0.3 to 0.4) shorten their ray and fall back to the world cache (pp. 183-184). The tech blog adds that this gives clear-coat a second reflection layer for free, and that smooth reflections trace extra rays shared between neighbouring pixels and accumulated over frames.
- **Translucency and fog** use a froxel grid of 3×3 or 4×4 octahedral probes, skip probes hidden by an HZB test, and pre-integrate to SH2 irradiance at about an eighth of the opaque gather's budget (pp. 170-171).

### The 2021 final gather

Wright's earlier course talk, "Radiance Caching for real-time Global Illumination" ([pptx](https://advances.realtimerendering.com/s2021/Radiance%20Caching%20for%20real-time%20Global%20Illumination%20(SIGGRAPH%202021).pptx), read from the slide and note XML; numbers are slide indices), gives the gather's parameters.

- **Budget:** half a ray per pixel (slides 11, 41, 54). Screen probes are usually 8×8 octahedral texels, 64 traces each (33), on a grid every 16 pixels and refined adaptively where interpolation fails, with the extra probes at the bottom of the atlas up to a limit and flood fill when it runs out (34-36). Probes sit on pixels, with grid and directions jittered per frame, and the temporal filter hides occlusion differences inside a cell (37, 98-100). At 1080p the base grid is 8,100 probes and 518,400 rays, a quarter ray per pixel, so the other quarter of the budget goes to adaptive probes and the world cache (derived).
- The screen cache runs at 1/16 resolution and the world cache at about 1/64, with integration and the temporal filter at full resolution (31).
- **Importance sampling** culls rays with zero BRDF from the G-buffer and spreads the rest by structured importance sampling over the octahedral mip quadtree, with the lighting PDF from last frame's reprojected cache: "Lighting PDF is approximate, BRDF is accurate" (44-52).
- **Filtering** happens in radiance-cache space, not screen space: a large kernel with depth weighting only, gathering the matching octahedral cell from neighbour probes (25, 57-58, 64). The temporal filter rejects by depth and has a fast-update mode for fast-moving hits (68, 98-100).
- **World cache:** a sparse set of camera-centred 3D clipmap grids storing indices into a probe atlas (75), typically 32×32 radiance texels per probe (76), traced on a fixed budget at full resolution with cache misses at lower resolution (79), in tiles of up to 64×64 effective resolution, about 4096 traces per world probe near the camera (80).
- Probe radiance becomes third-order SH per screen probe, which full-resolution pixels read, and a full-resolution bent normal restores contact shadows (90, 94-97).
- **Cost:** PS5 at 1080p with TSR to 4K, half a ray per pixel: 3.74 ms for the final gather, about half of it tracing. The listed parts are 0.53 (unlabelled in the extracted text), 0.62 (interpolate and integrate), 0.32 (temporal filter), 0.39 (screen bent normal), 0.13 (place probes), 0.35 (generate rays), 1.07 (trace) and 0.24 ms (probe-space filtering), which sum to 3.65 ms (102). The trace pass alone moves 1.04 M rays in 1.07 ms, about 0.97 G rays per second on PS5 through distance fields (derived). At an eighth of a ray per pixel, with caches at 1/32 and 1/128 and no bent normal, the gather took 2.15 ms (103); 2 rays per pixel took 4.23 ms on an RTX 2080 Ti (110).

### Timings

PS5 at 1080p with TSR to 4K. High targets 60 fps with global SDF tracing only (no mesh SDFs), 1/16 ray per pixel for the final gather and ¼ for reflections; Epic targets 30 fps with four times the rays (¼ ray per pixel for the gather, 1 for reflections) (p. 192). Neither gives a probe resolution.

| Scene | Setting | Surface cache | Final gather | Reflections | Total |
|---|---|---|---|---|---|
| Lumen in the Land of Nanite (software) | High | 0.47 ms | 2.07 ms | 0.23 ms | 2.77 ms |
| | Epic | 0.93 ms | 3.46 ms | 0.24 ms | 4.63 ms |
| Lyra (software) | High | 0.36 ms | 1.65 ms | 2.28 ms | 4.29 ms |
| | Epic | 0.66 ms | 3.30 ms | 4.74 ms | 8.70 ms |
| The Matrix Awakens (hardware, far field) | High | 1.03 ms | 3.05 ms | 2.30 ms | 6.38 ms |
| | Epic | 1.17 ms | 5.52 ms | 4.62 ms | 11.31 ms |
| Lake House (hardware, RTX 2080 Ti) | Epic | 1.68 ms | 4.01 ms | 1.56 ms | 7.25 ms |

- Four times the gather rays cost 1.67 to 2.0 times the gather time across the three scenes (derived), so at these budgets more than half the gather is cost that does not grow with rays: placement, filtering, interpolation and the bent normal (inference).
- Software and hardware gather tracing cost about the same in The Matrix Awakens (1.83 against 1.79 ms; 2.52 ms with far field) (p. 136).
- Far-field instances in the same TLAS cost near-field traversal 44%; offsetting them in space cut that to 7% (near field 1.65 ms alone, 2.37 overlapped, 1.77 offset) (pp. 123-124; percentages derived).
- The docs give console budgets of 8 ms at 30 fps and 4 ms at 60 fps at 1080p, covering GI, reflections and volumetric fog, each lower scalability level costing about half the one above. Epic targets 30 fps and High 60 fps on current consoles; Medium targets 60 fps on Switch 2 and medium PCs and uses screen-space reflections on smooth surfaces (Lumen Lite); Low disables Lumen; Cinematic is for Movie Render Queue. Reflection rays are traced below roughness 0.4 by default. The guide's only cost figure is about 1 ms saved on Xbox Series S by replacing Lumen reflections with SSR.
- **Emissive light:** the notes on p. 18 mention a limit to how small and bright emissive areas can be, set by noise, with no number. The Matrix Awakens' night mode, lit only by emissive meshes, is called an absolute stress test because the light sources are not sampled explicitly (p. 164), and explicit sampling of emissive meshes in the downsampled radiance cache is future work (p. 197).

### Limits and the 2022 overview

From the docs:

- Walls thinner than 10 cm leak with software tracing; one-sided meshes seen from behind and very thin features cannot be represented.
- Small emissive meshes are culled from the scene and light it only through screen traces; small, bright emissive areas cause noise past a limit.
- Global lighting changes such as turning off the sun take seconds to propagate.
- The scene covers 200 m by default (800 m at most); beyond that only screen traces give GI.

The tech blog ([UE 5.0 overview](https://www.unrealengine.com/en-US/tech-blog/unreal-engine-5-goes-all-in-on-dynamic-global-illumination-with-lumen), Wright and Narkowicz, 27 May 2022) adds:

- Lumen gives infinite diffuse bounces and sky shadowing, which makes interiors darker than exteriors. It also lights translucency and volumetric fog, at lower quality.
- Emissive meshes light the scene at no extra cost, though small bright ones cause noise; The Matrix Awakens' experimental night mode lights the city only through Lumen GI and reflections from millions of emissive window meshes, with no placed lights.
- Reflections work at any roughness and replace reflection captures, planar reflections and SSR.
- Software tracing is the default; Lumen in the Land of Nanite and Valley of the Ancients traced only the global distance field because their Megascans overlap heavily. Hardware ray tracing is more accurate and more expensive, covers skinned meshes, and is required for mirror reflections; The Matrix Awakens used it.
- The surface cache only supports meshes with simple interiors: walls, floors and ceilings must be separate meshes, and a furnished room imported as one mesh is not expected to work. Uncovered areas show black in reflections and make GI view-dependent, since only screen traces see them.
- A world-space radiance cache traces many more rays for distant light, which matters most for rooms lit by sky through a small window.
- Lumen relies on TSR to reach 4K and reaches 60 fps on current consoles at High. Quality scales up through Final Gather Quality, hardware ray tracing, and hit lighting in place of the surface cache.

GI-1.0 measured 2.4 ms against Lumen's 2.6 ms in one UE5 scene ([radiance caches](related_radiance_caches.md#gi-10)). Lumen's tracing, distance fields, surface cache and rejected designs are in [scene representation](scene_representation_and_tracing.md#lumen-mesh-and-global-distance-fields).

## Brixelizer GI

AMD FidelityFX Brixelizer GI (GDC 2024, 74 slides; [gpuopen.com/fidelityfx-brixelizer](https://gpuopen.com/fidelityfx-brixelizer/); code in the [FidelityFX SDK](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK) at tag `v1.1.4`, MIT, with `docs/techniques/brixelizer-gi.md`; [notes](../sources/2024_amd_brixelizer_gi.md)) is a simplified GI-1.0 on top of Brixelizer's compute-only sparse distance field ([Brixelizer](scene_representation_and_tracing.md#brixelizer)).

1. **Radiance cache:** a 256³ `R11G11B10` atlas of 4³ blocks keyed by brick, 64 MiB. Each frame a random pixel per 4×4 tile reprojects last frame's lit image to its world position and writes it into the brick there, 129,600 writes per frame at a 1080p internal resolution (derived). The SDF stores no materials, so this is the only way hits get colour, and a surface must have been on screen to bounce light. The atlas holds 64³ = 2^18 blocks, exactly one per possible brick ID (derived).
2. **Screen probes:** one per 8×8 tile with 8×8 octahedral directions. Placement tries up to 8 Hammersley-jittered positions for a valid depth. Probes are reprojected by picking the best-matching old probe per tile; tiles that fail trace one ray per probe texel, reading the radiance cache at hits and the environment map on misses. At the default half resolution of a 4K output that is 32,400 probes and at most 2.07 M rays, a quarter ray per output pixel (derived).
3. **Irradiance cache:** probes are projected to SH2 and blended into a world SH probe per brick, and SH spreads to neighbouring bricks one cascade per frame.
4. **Resolve:** screen-probe SH evaluated at the pixel normal is blended with world SH, then with reprojected history; a bilateral blur widens its radius as samples drop; a split-sum composite follows.
5. **Specular:** a quarter-resolution pre-trace stores brick IDs, then full resolution resumes inside those bricks, starting two cascades coarser than diffuse.

Feeding the composited output back as the next frame's input adds bounces. Internal resolution defaults to half the output, with 0.75× and native as options.

**Cost.** About 2 ms at 4K on an RX 7900 XTX, 2.2 ms at 4K on an RTX 4080, 1.7 ms at 1080p on an RX 7600 XT. These share slide 54 with the statement that the default works at half resolution internally, so they are most likely at 0.5× (inference). Slide 55 lists the GI's memory as about 110, 150 and 200 MB in columns for 0.5×, 0.75× and 1×, with the row label lost in extraction; the fixed buffers (radiance cache 64 MiB, two SH buffers of 18 MiB, state 4 MiB) come to about 104 MiB before screen-sized data, and the slides give the total as roughly 110 to 500 MB depending on resolution and scale. On top come Brixelizer's own 128 MiB atlas, 1 MiB per cascade and 16 MB of internal buffers. Neither the GI page nor the deck compares Brixelizer GI with DXR GI; the deck presents it as a fallback for hardware without ray tracing and compares it with a path tracer in images only.

**Problems.** Light from surfaces never seen on screen is missing until they come into view. AMD suggests SSAO or SSGI on top for small-scale detail. Foliage cards voxelize as solid quads, which over-darkens grass, and leaving them out leaves flickering gaps in the caches ([Brixelizer problems](scene_representation_and_tracing.md#brixelizer)).

## daGI2

The dynamic GI of Gaijin's open-source Dagor Engine ([DagorEngine](https://github.com/GaijinEntertainment/DagorEngine), BSD-3-Clause, read at commit 2baf194; `prog/gameLibs/daGI2/`, `prog/gameLibs/daSDF/`, `samples/testGI/`; [notes](../sources/2026_gaijin_dagi2_dynamic_gi.md)). It needs no hardware ray tracing: rays march an SDF clipmap, and hits read light from a voxel copy of the lit frame. It is the closest open match to a world-space RC in Godot, because it splits rays into intervals much as RC does. The SDF, lit scene, albedo and media scenes are in [scene representation](scene_representation_and_tracing.md#dagi2-narrow-band-clips-without-bricks) and [radiance at the hit](scene_representation_and_tracing.md#radiance-at-the-hit-from-the-lit-frame).

### Pieces and frame flow

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

- The SDF clips span 19.2 m to 307 m and take about 1.1 MB each with their border slices, 5.4 MB for all five (derived).
- The sample app has three GI modes: "Only AO" runs sky visibility alone; "Colored" runs the radiance grid with a denser irradiance grid and two extra irradiance clips and no screen probes; "Screen probes" runs everything, with tiles sized from the screen height (8 pixels at 1080p) and half the screen probes re-traced each frame.
- The lit scene, SDF depth marking and parts of the grids read and write the same texel in one pass (typed UAV loads). daGI2 checks R8, RGBA8, RGBA16F, R11G11B10F and R16F at start-up and turns the lit scene off if any lacks it.
- No timing appears anywhere in daGI2; every per-frame budget is a count.

A frame runs in four steps:

1. `beforeRender` copies the new settings, clamps them, and creates or frees pieces.
2. `updatePosition` scrolls the clipmaps: albedo, media, the world SDF, then the radiance grid. The SDF rebuild rasterizes collision geometry for the region that scrolled in, and the same pass writes first-guess lit voxels there; the sample culls its lights to that region for it.
3. During lighting, `beforeFrameLit` places and traces screen probes, then volumetric GI.
4. `afterFrameRendered` feeds the finished frame back. On alternate frames it removes SDF where depth shows empty space, or marks SDF from depth. Then it updates the lit scene, albedo and media from the G-buffer and runs the radiance grid's probe updates.

### Screen probes

**Placement.**
- One probe per tile (8 to 32 pixels), plus extra probes on tiles with depth edges, from a pool of 0.75 times the probe count at 16-pixel tiles (6,120 extra probes at 1080p, derived). The pool grows with tile area.
- A probe keeps last frame's pixel if that pixel reprojects into the tile and its depth still matches; otherwise it moves to the tile centre. Re-placing probes every frame under TAA jitter breaks temporal reuse and makes them blink.
- Extra probes are added over up to `log2(tile size)` passes. Each finds the tile pixel least covered by nearby probes, where coverage is `exp2(−10000·d²)` and `d` is the pixel's distance to each probe's surface plane, and places a probe there if coverage is below 0.01.

**Tracing.**
- About `(radiance resolution/√2)²` rays per probe, 36 (6×6) for 8×8 radiance. At 16-pixel tiles and 1080p that is 8,160 probes and 293,760 rays, 0.14 rays per pixel; the sample's 8-pixel tiles with half re-traced give 583,200 rays, 0.28 per pixel (derived). Blue noise jitters rays per tile and rotates each frame, because one offset shared by neighbours shows as shimmer.
- Each ray first marches the screen: 16 linear samples on half-resolution depth, which a comment puts at 10 to 30% of the cost and credits with better quality and stability. If it does not hit, the ray continues as a project trace hook (hardware RT or a BVH) or an SDF march, pushed out along the normal by up to half the screen-ray length, because the screen trace skips thin meshes.
- Hit light comes from last frame's lit pixel where the hit reprojects with depth within 5%, otherwise from the voxel lit scene.
- Ray length inside a radiance grid clip is 3 to 6 grid probe sizes, 3 for new probes rising to 6 as they settle; outside the grid it is 64 m.
- A miss reads the radiance grid at the ray end pulled back half a grid probe, so trilinear filtering does not reach through a wall, or the sky outside the grid.

**Filtering and output.**
- Temporal: a probe's first samples weigh 1, 1/2 and 1/3, then 0.025 per frame; moving probes use 0.125. Probes on moving objects within 50 m reproject by motion vectors.
- Spatial: the 4 nearest neighbours always, plus diagonals and the next ring (12 in all) for new or moving probes, weighted by distance to the centre probe's plane. An optional angle weight uses each neighbour's hit distance and needs RGBA16F storage; the settings comment says it changes little.
- Irradiance is a 6×6 octahedral map per probe (plus a 1-texel border), the cosine-weighted average of the radiance texels, or a projection to 3-band SH. The octahedral maps are equal-area, so every texel has the same solid angle.
- Values are rounded before being stored as R11G11B10F, because hardware truncates and temporal blending then drifts the image yellow; the screen GI buffer stores squared colour (gamma 2) for the same reason ([precision](artifacts_and_fixes.md#banding-and-precision)).
- Upsampling takes the 4 nearest probes with bilinear weights times a plane-distance weight; an extra probe replaces a corner when its weight is higher.

### Radiance grid

- **Layout:** up to 4 clips of 32×32×d probes, 8×8 octahedral R11G11B10F texels per probe, probe size doubling per clip. A separate SH1 irradiance grid is projected from it, or traced on its own when denser, packed into RGBA8 plus RGBA16F with blue rebuilt from luminance and the red and green ratios.
- **Scrolling:** probes that enter a clip are traced at once, written without blending and marked young.
- **Which probes update:** one clip per frame. Each probe is tested once every 8 updates of its clip, in a stride pattern. Its chance to be picked starts from its age (young probes about 8 times likelier), is cut to 1/16 outside the frustum or behind the HZB, and cut to 1/16 again with no surface within 3 probes. A feedback multiplier steers the count to 6.25% of the clip, traced by indirect dispatch. That is `64·d` probes and `4096·d` rays per frame, and with 3 clips a probe is retraced on average once every 48 frames (derived).
- **Rays:** 64 per probe, one per texel, by SDF march or the project trace, up to 128 m, reading the sky on a miss.
- **Hand-off on scroll-in:** a probe entering a clip stops its rays at 4 probe sizes of the next coarser clip (8 of its own) and reads that clip's texel for the same direction, interpolated from its 8 nearest probes at the end point pulled back √3 coarser probe sizes. A comment says features smaller than a quarter of the solid angle can be missed, and that this is about 16 m against 128 m, so 8 times fewer traces. Ongoing updates turn this off and trace the full length.
- **Blending:** new probes average up to 27 samples (weight `1/n`). An invalidated region marks its probes as quick-updating, and they then blend with weights from 0.3 to 1 for up to 36 updates.
- **Sampling:** the finest clip holding the point, offset half a probe along the normal and up to one probe toward the camera, blended into the next coarser clip over a dithered border. There is no visibility term; these offsets are the only leak control ([leak defences](3d_world_space.md#leak-defences-in-world-space)).

### Volumetric GI

Froxels on 64-pixel tiles with 16 exponential slices, 8,160 froxels at 1080p (derived), out to half the radiance grid's reach. Near slices trace a 3×3 octahedral map per froxel, up to 1.5 grid probe sizes, reading the lit scene at SDF hits and the radiance grid otherwise. Each froxel stores SH1 with temporal reprojection at 3% new per frame; far slices and quality 0 just sample the irradiance grid.

### Problems on record

From `todo.txt` and comments:

- Large lit-scene voxels leak more light than the SDF plus albedo, so the number of lit clips is capped.
- The first voxelization of a region comes out too bright in corners, because the irradiance grid is undersampled and the lit scene and the SDF depend on each other.
- DX11 has no typed UAV loads, which disables the lit scene there.
- 32-pixel tiles are needed at 4K.
- Sparse foliage needs its own handling: the media scene, and a top-down "trees above" depth map whose consumer is outside daGI2.

### daGI v1 in Enlisted (2019)

Anton Yudintsev, "Scalable Real-Time Ray Traced Global Illumination for Large Scenes", GDC 2019 ([GDC Vault](https://gdcvault.com/play/1026469/Scalable-Real-Time-Global-Illumination), members only, no public slides), written up in the [Enlisted news post](https://enlisted.net/en/news/show/25-gdc-talk-scalable-real-time-ray-traced-global-illumination-for-large-scenes-en/) of 2 May 2019, whose formulas are images.

- The scene was a nested clipmap of lit voxels with colour and opacity, grids sharing one texture size, filled from random G-buffer pixels each frame as in daGI2. New voxels could be seeded from heightmaps, cascaded shadow maps, GPU-voxelized collision or low-LOD models, which mostly helps opacity and so bleeding; static scenes need no removal, and changed regions are invalidated.
- Irradiance lived in 3 levels of ambient cubes covering 1/8, 1/4 and all of a camera-centred box with the same texel count, so texel size doubles per level, all in one volume atlas. The 6 directions sat in 3 hardware-filtered volume textures, because a lit pixel never needs both the positive and negative direction of an axis. Texture dimensions are not given.
- Cells were picked stochastically, with a probability set from how many passed in the previous frame, after frustum and HZB culling. Queue A held cells touching geometry (512 to 1024), A' the never-updated ones among them, processed first, and queue B (64 to 128) cells in open air, which still light dynamic and transparent objects. One compute pass filled the queues and an indirect dispatch relit them. New fine cells started from the coarser level; the coarsest started in a "new" state lit by a few rays.
- Tracing was Monte Carlo through the voxel grid, one thread group per cell and one thread per ray with a parallel reduction, accumulated over time with a weight from the cell's age; "thousands of rays" per scene, no per-cell count. Voxel cone tracing was rejected because it reports thin obstacles as partial occluders ([voxel cone tracing](related_probe_gi.md#voxel-cone-tracing)).
- Diffuse shading sampled the finest available level, blended toward the next to hide seams. Glossy reflections and eye-ray hits came from the voxel scene with parallax correction (Lagarde and Zanuttini 2012). "Convex offset filtering" moved samples off the border of the convex volume to stop leaks.
- Memory: irradiance 13.5 MB, scene 16.5 MB (33 MB at higher quality), temporal buffers under 1 MB, about 31 MB in all; the text also gives 32 to 62 MB overall.
- Costs: 0.57 ms in all on a GTX 1070. On Xbox One, 0.7 ms with one bounce or async and about 1.6 ms with synchronous multi-bounce, with the irradiance update itself 1.2 ms (async or optional); movement 0.1 to 1 ms spread over 8 to 16 frames (about 0.1 ms); scene feedback about 0.02 ms; updating voxels from 100,000 pixels under 0.2 ms; extra lighting at 1080p 0.3 ms.
- Limits: bleeding where fill data or opacity is missing, over-dark ground under sparse foliage (fixed by skipping its pixels or storing opacity), no glossy from the irradiance map, dynamic objects excluded from voxel updates, and a camera-centred extent.

## HSGI

LIGHTSPEED STUDIOS (Tencent), "HSGI: Cross-Platform Hierarchical Surfel Global Illumination", GDC 2023 ([slides](https://media.gdcvault.com/gdc2023/Slides/HSGI+Cross-Platform_Jiaxuan_Zhang.pdf), 90 pages, filed under Jiaxuan Zhang; the Vault page names Jiancong Huang and Jiaxuan Zhang; [notes](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md)). It is dynamic GI for huge open worlds with moving geometry on PC, consoles and phones. Its "surfels" are voxels with a normal in a sparse brick clipmap traced by a hierarchical DDA, the same structure as HDDAGI; the cache and how it is filled from the lit screen are in [scene representation](scene_representation_and_tracing.md#hsgis-sparse-voxel-cache). Hardware RT is optional on every path.

### Mobile path

One sample per pixel was too slow on phones, so mobile uses probes:

- A DDGI-style probe volume ([DDGI](related_probe_gi.md#ddgi)): ambient-cube irradiance, VSM visibility and relocation per probe, 2 clipmap LODs (4 on PC). Only probes near surfaces, found through the voxel hierarchy, update; each frame one random face of each traces one ray.
- Gathering 8 probes per pixel in the forward pass cost too much, so indirect light moved to deferred screen probes: 64×64-pixel tiles with one jittered probe each, storing a 4×4 hemisphere octahedral tile, with visibility rays in place of VSM.
- Probes are gathered at half resolution with depth and normal tests, accumulated over time and upsampled with a bilateral filter. A tile where all four probes fail gets an extra probe the next frame.
- One extra G-buffer target (RGB8 diffuse plus an 8-bit hemisphere normal in view space, dithered before encoding) makes this work in a lite deferred pass.
- With no velocity buffer, one bit of the diffuse colour marks dynamic objects: they read the 3D probes directly, screen probes are generated before they are drawn, and history marked dynamic is discarded.
- **Cost on an iPhone 13 Pro (A15):** 3.18 ms per frame in all. Gathering screen probes takes 1.07 ms, indirect lighting 1.00, injection 0.33 and generating screen probes 0.08, leaving 0.70 ms for structure and volume updates (derived). The base pass dropped from 2.20 to 1.88 ms. Frames that shift the clipmap or voxelize objects add 1.79 ms, mostly shifting the hierarchy (1.51), for about 5 ms on those frames (derived).

### PC and console path

- Rays use screen traces (Hi-Z), then HDDA voxels or hardware RT, and read radiance from the scene colour, the voxels or a probe.
- Diffuse GI runs ReSTIR GI at half resolution ([ReSTIR](supporting_techniques.md#resampling-and-sampling-theory)). One visibility ray after spatial reuse restores indirect shadows that visibility-free reuse washes out, and neighbours are reused only when their shadow state matches. Shading samples 3×3 to 7×7 neighbour reservoirs to cut colour noise.
- **Trace-probe mode:** for scenes with 4 or more important bounces or small bright lights, rays go only one probe size and then read a 6×6 octahedral probe, trading detail for stability, switchable per area.
- Reflections below roughness 0.4 trace; rougher ones reuse the diffuse result, and above 0.8 they blend to diffuse GI.
- **Against Lumen:** RTX 3080, 4K output via TSR from 1932×1084, GI traced at 966×542 (a quarter of the internal pixels, 6.3% of the output's). HSGI's GI passes took 8.53 ms (73.48 fps) against 9.63 ms for UE5 Lumen (59.62 fps), 11% less, with RMSE against a path tracer of 29.36 against 32.12. Of HSGI's 8.53 ms, diffuse denoising was the largest pass at 2.65 ms, 4.1 times diffuse tracing's 0.64 ms; a pass labelled "Ray Tracing Scene" took 2.14 ms (4.90 in UE5), light propagation 0.33 and screen injection 0.15 (ratios derived). No source states the RMSE's units, value range or tone mapping: the Vault page has only an abstract, no paper or preprint exists, and the Chalmers thesis sometimes linked with it is Ekberg's 2022 reimplementation of GIBS ([GIBS](related_radiance_caches.md#gibs-and-pica-pica-surfels)).

## Connections

- **Every system hand-picks an RC interval.** Lumen's screen ray stops at about 2 m and reads the world cache; daGI2's screen rays stop at 3 to 6 grid probe sizes and its scrolled-in grid probes at 4 coarser probe sizes; HSGI's trace-probe mode stops at one probe size; Godot's screen-probe draft stops its Hi-Z trace at 2 units ([HDDAGI](godot_integration.md#screen-probes-in-122999)); EggyStudio's screen probes stop at twice the world spacing ([hybrids](3d_screen_space.md#hybrids)). Each is a two- or three-level RC merge with one direction fetch at the end, and the lengths are stated in probe sizes, the unit the [penumbra condition](core_theory.md#the-penumbra-condition) uses (inference). daGI2's case, a coarser level read after a few of its own probe sizes, is RC's cascade-to-cascade step.
- **The far-level read sits on the RC trade.** Lumen's world probes have 16 times the screen probes' directions and far fewer positions. In 3D RC with four times the directions per cascade, 16 times is two cascades' worth (derived), so Lumen's two levels are about two cascades apart.
- **Pull-back and plane tests are the same leak fix.** daGI2 reads the grid half a probe (or √3 coarser probes) back along the ray; Lumen's screen trace steps back to its last unoccluded point before handing off and interpolates only from probes on the pixel's plane; GI-1.0 and Brixelizer weight by plane distance. RC's merge reads a coarser probe at the end of an interval with the same exposure to walls, and the pull-back is the cheapest known defence ([light leaks](artifacts_and_fixes.md#light-leaks)) (inference).
- **Hits take light from the lit frame.** Brixelizer's radiance cache, daGI2's lit scene, HSGI's screen injection and Lumen's surface cache (whose indirect feeds back over frames) all give an off-screen hit a radiance value from earlier frames, with bounces accumulating for free ([radiance at the hit](scene_representation_and_tracing.md#radiance-at-the-hit-from-the-lit-frame)). Each pays for it with missing light from surfaces never seen and with latency.
- **Budgets are counts with feedback.** Lumen's priority queue, daGI2's probability steered to 6.25%, daGI v1's queues sized from last frame's pass count, Brixelizer's cascade schedule `0 1 0 2 0 1 0 3`, and HSGI's 9- and 121-frame brick cycles all fix the work per frame and let latency float ([temporal reuse in world space](3d_world_space.md#temporal-reuse-in-world-space)). HSGI's cycles are 3² and 11², which suggests square interleave patterns over bricks (inference).
- **Fixed costs dominate at low ray counts.** Lumen's gather took 1.7 to 2.0 times as long for 4 times the rays, and HSGI's denoiser cost 4.1 times its tracing. A single-frame RC replaces the denoiser and the temporal filter with more rays and a merge, so its cost is mostly rays, which makes ray throughput (Lumen's 0.97 G rays per second through distance fields on PS5) the number to plan with (inference).
- **Small bright emitters are everyone's limit.** Lumen's noise limit on small emissives, kajiya's advice to treat them as lights ([kajiya](related_radiance_caches.md#kajiya)) and RC's cascade 0 spacing limit ([sharp shadows and small lights](artifacts_and_fixes.md#sharp-shadows-and-small-lights)) are the same problem: probe-based gathers cannot find sources smaller than a texel's solid angle.
- **Foliage is unsolved everywhere.** Lumen's coverage channel, daGI2's media scene and trees-above map, daGI v1's over-dark ground and Brixelizer's solid quads are four answers that each trade leaks for over-darkening; RC's transmittance per interval is the same density problem ([volumetric](volumetric_and_radiative_transfer.md#integration-and-merging)) (inference).

## Single-frame assessment

- **All four rely on time.** Lumen jitters probes and directions per frame and hides occlusion differences in its temporal filter; global changes "take seconds to propagate". daGI2's screen-probe weight of 0.025 is worth about 79 frames of history and its fog's 3% about 66 (from the [history equivalence](related_probe_gi.md#ddgi)); its grid probes refresh about once every 48 frames. Brixelizer GI reprojects probes and history and spreads SH one cascade per frame. HSGI accumulates its probes and amortizes bricks over 9 to 121 frames (derived).
- **Removing amortization multiplies cost by the cycle length.** A daGI2 grid updated in full each frame costs 16 times its budget; HSGI's near field 9 times and far field 121 times. A single-frame design either accepts those factors or shrinks the work per level, which RC's angular-spatial trade does by construction (inference).
- **What transfers unchanged:** Lumen's tracer chain (screen, then SDF, then sky, each resuming from the last), plane-only interpolation, probe-space filtering within a frame, BRDF-only importance sampling (the BRDF half needs no history), daGI2's adaptive placement by plane coverage, the pull-back on far reads, blue-noise ray rotation per tile within a frame, rounding before packed writes, HSGI's in-voxel origin fix, and every count-based indirect dispatch. daGI2's narrow-band SDF needs only `InterlockedMin`, one relaxation pass, and depth marking with HZB removal for moving things, all within Godot's integer atomics; its start-up check of storage loads per format maps to `RenderingDevice.texture_is_format_supported_for_usage`.
- **What does not:** product sampling from last frame's light, reprojected probe positions and history, hits lit from the previous frame, and multi-bounce built over frames. In Godot the GI pass runs before the opaque pass ([frame order](godot_integration.md#frame-order-and-compositor-hooks)), so the lit frame a hit could read is always last frame's; same-frame hit light has to come from direct-light evaluation at the hit, as Lumen's surface cache does with shadow-map masks.

## Open questions

- Lumen spends a quarter ray per pixel on its base screen probes and ships at 1/16 on High. What does a single-frame RC need at cascade 0 to match Lumen High's quality without the temporal filter, and does that fit the 4 ms budget Lumen holds at 60 fps?
- daGI2 lengthens screen-probe rays from 3 to 6 grid probe sizes as probes settle. In a single frame there is no settling: which fixed interval-to-spacing ratio best trades the far level's coarseness against tracing cost?
- Can direct light at a hit come from Godot's shadow maps in the same frame, through the PRE_OPAQUE hook, so that a single-frame RC has first-bounce light at off-screen hits without last frame's lit image?
- Does the pull-back distance (half a probe for screen rays, √3 coarser probes for grid rays) generalize into an RC merge rule tied to the parent probe's spacing?
- How much of HSGI's 2.65 ms denoiser and Lumen's fixed gather costs would a single-frame RC spend instead on rays, at the same quality?
