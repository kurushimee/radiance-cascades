# Wright, Narkowicz and Kelly: Lumen in Unreal Engine 5 (SIGGRAPH 2022)

| | |
|---|---|
| Title | Lumen: Real-time Global Illumination in Unreal Engine 5 |
| Authors | Daniel Wright, Krzysztof Narkowicz, Patrick Kelly (Epic Games) |
| Venue | SIGGRAPH 2022, Advances in Real-Time Rendering in Games course |
| Slides | https://advances.realtimerendering.com/s2022/SIGGRAPH2022-Advances-Lumen-Wright%20et%20al.pdf (200 pages with speaker notes) |
| Tech blog | https://www.unrealengine.com/en-US/tech-blog/unreal-engine-5-goes-all-in-on-dynamic-global-illumination-with-lumen (Wright and Narkowicz, 27 May 2022) |
| Docs | https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine and the Lumen performance guide |

Not RC, but the most complete shipped account of a layered GI cache: screen probes for the near field, world probes for distant light, and a skylight beyond, each picked for the precision its range needs. That is the problem RC solves with one rule, and Lumen's specific fixes for leaks, thin walls, foliage, noise and update budgets apply to any RC tracer. Page numbers below are slide numbers.

## Contents

- [Cache levels](#cache-levels)
- [Screen probes](#screen-probes)
- [Tracing](#tracing)
- [Distance fields](#distance-fields)
- [Surface cache](#surface-cache)
- [Rejected designs](#rejected-designs)
- [Radiance caching (SIGGRAPH 2021)](#radiance-caching-siggraph-2021)
- [Timings](#timings)
- [Limits from the docs](#limits-from-the-docs)
- [Tech blog overview (May 2022)](#tech-blog-overview-may-2022)

## Cache levels

The opaque final gather has these levels, from near to far (p. 168):

| Level | Range | Directions per probe | Notes |
|---|---|---|---|
| Contact AO | 16 px | | applied after the temporal filter so it has no lag; restores shadow detail lost to probe downsampling |
| Screen radiance cache | up to about 2 m of world tracing | 8×8 | one probe per 16 px in each dimension, more where geometry is detailed |
| World radiance cache | out to 200 m | 32×32 | clipmaps with bounded probe spacing on screen; the screen-probe ray is shortened and the world probe is interpolated on a miss |
| Skylight | beyond | | updated over many frames |

- The world cache has a 16:1 higher directional resolution and a much lower spatial resolution than the screen cache, which keeps its error stable in world space (p. 161). The speaker says the shortest range cannot afford latency while the skylight can afford a lot (p. 168).
- World probes persist in a free list. Each frame keeps last frame's probes that are still needed, traces probes revealed by camera motion, and retraces a fixed number chosen from a GPU priority queue to propagate lighting changes. Cost is fixed and lighting latency varies (p. 163). Too low a budget makes lighting pop in during fast camera motion (performance guide).
- Emissive-lit scenes (The Matrix Awakens at night) rely on the world cache, whose higher directional resolution resolves small emitters more accurately and stably (p. 164).
- A low-cost mode ("Irradiance Field Gather", for Switch 2 and low-end PCs) places world cache probes around pixels, precomputes their irradiance and interpolates with probe occlusion; probes left inside geometry are not used (performance guide).

## Screen probes

- Probes are placed on pixels on a uniform grid, subdivided where geometry is detailed; the grid is jittered and accumulated over time (pp. 146, 153).
- Pixels interpolate only from probes on the same plane, which limits leaks (p. 146).
- Rays are product importance sampled from the BRDF and the incoming light, culling unimportant directions and supersampling important ones, with a whole thread group per probe (p. 158). The light estimate is last frame's screen cache reprojected, with the world cache as fallback where reprojection fails, such as screen edges (p. 157). The speaker puts the gain at the quality of four times more rays for the same ray count (p. 159).
- Spatial filtering runs in probe space: 3×3 probes cover 48×48 pixels and need only probe positions, not every pixel's position and normal (p. 156).
- The full-resolution temporal filter rejects history by depth and normal, with no neighborhood clamp, because jittered probe positions need a reliable history. That is stable but slow to react (ghosting), so accumulation speeds up where rays hit fast-moving objects (pp. 166 to 167).
- Rough reflections (roughness 0.4 to 1, often half the screen) reuse the screen cache instead of tracing, cutting reflection cost by 50 to 70%; glossy ones (0.3 to 0.4) shorten their ray and fall back to the world cache (pp. 183 to 184).
- Translucency and fog use a froxel grid of 3×3 or 4×4 octahedral probes, skip probes hidden by an HZB test, and pre-integrate to SH2 irradiance at about one eighth of the opaque gather's budget (pp. 170 to 171).

## Tracing

- Each ray goes through methods in order: screen trace, then software or hardware tracing, then skylight on a miss. Each method writes its trace distance and hit flag, and the next resumes from there (pp. 9, 22).
- **Screen traces** walk the closest HZB mips without a stack (linear steps skipped thin tables, doors and walkways). On going behind a surface or off screen, the ray steps back to its last unoccluded position before handing off, which avoids leaks at the hand-off. Diffuse rays trace at half resolution (pp. 25 to 27).
- **Compaction** after screen tracing removes finished lanes, order-preserving with a Z-order within 128×128 tiles, a wave prefix sum and global atomics, for up to 50% faster tracing (pp. 29 to 30).
- **Mesh SDFs** are traced for the first 2 m of a ray, at most 64 steps, where step 64 counts as a hit. Instances are found through a froxel grid of culled object lists rather than a BVH (pp. 36, 44).
- **The global SDF** covers the rest: loop over clipmaps from the smallest, sample a continuous coarse mip, and switch to sparse bricks near surfaces (p. 43).
- Directional shadow rays cull objects to a 2D grid in light space and stop at any hit (p. 45).

## Distance fields

- **Mesh SDFs** are built at import with Embree point queries; the sign comes from counting back-face hits among 64 rays per voxel. Storage is sparse 8³ bricks with a half-texel border, a narrow band of ±4 voxels in one byte, and one virtual volume texture per mip. A large 1.5M-triangle mesh builds in about 0.6 ms. Mips stream by camera distance from a fixed 320 MB pool (pp. 34 to 35).
- **The global SDF** merges instances at runtime into 4 camera-centered clipmaps of 256³, in the same sparse brick format. Static and dynamic bricks are cached separately and modified bricks are tracked on the GPU; distant clipmaps update less often and drop small objects. Non-uniformly scaled objects use the distance to their oriented bounding box. A quarter-resolution coarse mip is rebuilt with 5 iterations of Eikonal propagation (pp. 40 to 42).
- **Thin walls** may never cross zero between samples, which gives no hit and no gradient and leaks badly. The fix expands surfaces by half a voxel's diagonal at trace time and pulls back to fix the gradient. Expansion over-occludes and adds surface bias, so GI rays start with no expansion and grow it linearly with distance, fading it at the end of shadow rays. Reflections use `min(MaxExpand, DistanceToSurface)` per step (pp. 48 to 51).
- **One-sided meshes** get a virtual closing surface that wraps after 4 voxels (p. 47).
- **Foliage:** expansion can block all light between leaves, so each instance has a coverage value (and the global SDF a coverage channel) that reduces expansion, raises the minimum step and drives stochastic transparency at hits (pp. 53 to 54). SDFs do not animate.

## Surface cache

A distance-field hit has no UVs or material, so hits read a cache of material and lighting stored on cards (p. 57).

- Cards are axis-aligned projections picked at import by clustering surfels; 12 per mesh by default (docs), six around the bounds as a fallback and for skinned meshes. They live in a virtual 4096×4096 atlas of 128×128 pages, with low-resolution pages always resident and high-resolution pages requested by GPU feedback (pp. 60 to 67).
- Captures re-render mesh materials with Nanite at a budget of 512×512 texels per frame (p. 68). Direct light updates 1024×1024 texels per frame and indirect 512×512, ordered by `LastUsed − LastUpdated` with a radix sort (p. 74).
- Direct light: lights culled to 8×8 tiles, the first 8 per tile, a 1-bit shadow mask from shadow maps, and shadow rays only where maps cannot answer (p. 75).
- Indirect light: a 4×4 hemisphere probe per 4×4 texel tile, jittered over 4 frames, gathered from 4 probes with plane and hit-distance weights, and accumulated over at most 4 frames. Last frame's indirect feeds back, so bounces build up. It costs under one sixteenth of Lumen's budget (pp. 76 to 78).
- Rays that hit back faces return zero, so texels inside geometry stay black and filtering does not leak through walls (p. 73).
- The global SDF cannot tell which instance was hit, so it reads a coarse voxel lighting volume: 4 clipmaps of 64³, radiance in 6 directions per voxel, 3 interpolated by normal (pp. 80 to 82). The slides call this too coarse.
- Weak points: missing card coverage (shown pink), no animation, a limited number of surface layers (p. 83).

## Rejected designs

- Hardware ray tracing alone: no scaling down for PCs without DXR and 60 fps consoles, and slow with overlapping instances (pp. 4, 32).
- Software BVH or grids: too slow for long incoherent rays (p. 38).
- Voxel cone tracing and prefiltered cone tracing: leaks or over-occlusion that cannot be avoided, especially in coarse mips, and no hardware RT path (pp. 39, 139 to 141).
- Ray marching voxel bit bricks: surprisingly slow, replaced by the global SDF (p. 39).
- Irradiance fields: irradiance computed at the probe instead of the pixel, leaks and over-occlusion, hard placement, slow updates and a flat look (p. 143).
- Per-pixel tracing with a screen-space denoiser: slow decorrelated rays and poor disocclusions (p. 144).

## Radiance caching (SIGGRAPH 2021)

Wright's earlier course talk, "Radiance Caching for real-time Global Illumination" (https://advances.realtimerendering.com/s2021/Radiance%20Caching%20for%20real-time%20Global%20Illumination%20(SIGGRAPH%202021).pptx, read from the slide and note XML; numbers are slide indices), gives the final gather's parameters.

- Budget: half a ray per pixel (slides 11, 41, 54). Screen probes are usually 8×8 octahedral texels, 64 traces each (33), placed on a grid every 16 pixels and refined adaptively where interpolation fails, with the extra probes at the bottom of the atlas up to a limit and flood fill when it runs out (34-36). Probes sit on pixels, with grid and directions jittered per frame, and the temporal filter hides occlusion differences inside a cell (37, 98-100).
- The screen-space radiance cache runs at 1/16 resolution and the world cache at about 1/64, with integration and the temporal filter at full resolution (31).
- Importance sampling culls rays with zero BRDF from the G-buffer and distributes the rest by structured importance sampling over the octahedral mip quadtree, with the lighting PDF from last frame's reprojected cache: "Lighting PDF is approximate, BRDF is accurate" (44-52).
- Spatial filtering happens in radiance-cache space, not screen space: a large kernel with depth weighting only, gathering the matching octahedral cell from neighbour probes (25, 57-58, 64). The temporal filter rejects by depth and has a fast-update mode for fast-moving hits (68, 98-100).
- The world-space radiance cache is a sparse set of camera-centered 3D clipmap grids storing indices into a probe atlas (75), typically 32×32 radiance texels per probe (76), traced on a fixed budget at full resolution with cache misses at lower resolution (79), in tiles of up to 64×64 effective resolution, about 4096 traces per world probe near the camera (80).
- Probe radiance becomes third-order SH per screen probe, which full-resolution pixels read, and a full-resolution bent normal restores contact shadows (90, 94-97).
- PS5 at 1080p with TSR to 4K, half a ray per pixel: 3.74 ms for the final gather, about half of it tracing; the listed parts are 0.53 (unlabelled in the extracted text), 0.62 (interpolate and integrate), 0.32 (temporal filter), 0.39 (screen bent normal), 0.13 (place probes), 0.35 (generate rays), 1.07 (trace) and 0.24 ms (probe-space filtering), which sum to 3.65 ms (102). At 1/8 ray per pixel, with caches at 1/32 and 1/128 and no bent normal, it took 2.15 ms (103); 2 rays per pixel took 4.23 ms on an RTX 2080 Ti (110).

## Timings

All on PS5 at 1080p with TSR to 4K. High targets 60 fps with global SDF tracing only (no mesh SDFs), 1/16 ray per pixel for the final gather and ¼ for reflections; Epic targets 30 fps with four times the rays (¼ ray per pixel for the final gather, 1 for reflections) (p. 192). Neither gives a probe resolution.

| Scene | Setting | Surface cache | Final gather | Reflections | Total |
|---|---|---|---|---|---|
| Lumen in the Land of Nanite (software) | High | 0.47 ms | 2.07 ms | 0.23 ms | 2.77 ms |
| | Epic | 0.93 ms | 3.46 ms | 0.24 ms | 4.63 ms |
| Lyra (software) | High | 0.36 ms | 1.65 ms | 2.28 ms | 4.29 ms |
| | Epic | 0.66 ms | 3.30 ms | 4.74 ms | 8.70 ms |
| The Matrix Awakens (hardware, far field) | High | 1.03 ms | 3.05 ms | 2.30 ms | 6.38 ms |
| | Epic | 1.17 ms | 5.52 ms | 4.62 ms | 11.31 ms |
| Lake House (hardware, RTX 2080 Ti) | Epic | 1.68 ms | 4.01 ms | 1.56 ms | 7.25 ms |

- Software and hardware final-gather tracing cost about the same in The Matrix Awakens (1.83 against 1.79 ms; 2.52 ms with far field) (p. 136).
- Putting far-field instances in the same TLAS cost near-field traversal 44%; offsetting them in space cut that (near field 1.65 ms alone, 2.37 overlapped, 1.77 offset) (pp. 123 to 124).
- The docs give budgets of 8 ms at 30 fps and 4 ms at 60 fps on consoles at 1080p, covering GI, reflections and volumetric fog, each lower scalability level costing about half the one above. Epic targets 30 fps and High 60 fps on current consoles; Medium targets 60 fps on Switch 2 and medium PCs and uses screen-space reflections on smooth surfaces (Lumen Lite); Low disables Lumen; Cinematic is for Movie Render Queue. Reflection rays are traced below roughness 0.4 by default. The guide gives no per-pass breakdown; its only cost figure is about 1 ms saved on Xbox Series S by replacing Lumen reflections with SSR.
- Emissive light: the notes on p. 18 mention a limit to how small and bright emissive areas can be, set by noise, with no number; The Matrix Awakens' night mode, lit only by emissive meshes, is called an absolute stress test because the light sources are not sampled explicitly (p. 164), and explicit sampling of emissive meshes in the downsampled radiance cache is future work (p. 197).

## Limits from the docs

- Walls thinner than 10 cm leak with software tracing; one-sided meshes seen from behind and very thin features cannot be represented.
- Small emissive meshes are culled from the scene and light it only through screen traces; small, bright emissive areas cause noise past a limit.
- Global lighting changes such as turning off the sun take seconds to propagate.
- The scene covers 200 m by default (800 m at most); beyond that only screen traces give GI.

## Tech blog overview (May 2022)

The tech blog is a non-technical overview written for the UE 5.0 release. It adds these points to the slides and docs:

- Lumen gives infinite diffuse bounces and sky shadowing, which makes interiors darker than exteriors. It also lights translucency and volumetric fog, at lower quality.
- Emissive meshes light the scene at no extra cost, but emissive areas that are too small and bright cause noise. The experimental night mode of The Matrix Awakens lights the city only through Lumen GI and reflections from millions of emissive window meshes, with no placed lights.
- Reflections work at any roughness and replace reflection captures, planar reflections and screen-space reflections. Rough reflections reuse the screen-space radiance cache at no extra cost, which also gives clear-coat materials a second reflection layer for free. Smooth reflections trace extra rays, share them between neighboring pixels and accumulate them over frames.
- Software ray tracing is the default: mesh distance fields, merged into a global distance field for fast tracing through overlapping meshes. Lumen in the Land of Nanite and Valley of the Ancients traced only the global distance field because their Megascans overlap heavily. Hardware ray tracing is more accurate and more expensive, covers skinned meshes, and is required for mirror reflections; The Matrix Awakens used it.
- The surface cache picks capture directions per mesh so every surface is covered, recaptures nearby meshes into its atlas as the player moves (Nanite speeds this up but is not required), and lights the cached surfaces with multi-bounce GI and shadowed skylight. It only supports meshes with simple interiors: walls, floors and ceilings must be separate meshes, and a whole furnished room imported as one mesh is not expected to work. Uncovered areas show black in reflections and make GI view-dependent, since only screen traces see them.
- The final gather traces a screen-space radiance cache at reduced resolution and applies it to full-resolution material data. Filtering happens inside the radiance cache rather than in a screen-space denoiser. Ray directions are importance-sampled from last frame's lighting, which the authors say matches four times the rays at much lower cost. A world-space radiance cache traces many more rays for distant light, which matters most for rooms lit by sky through a small window.
- Lumen relies on TSR to reach 4K and reaches 60 fps on current consoles at the High scalability level. Quality scales up through Final Gather Quality, hardware ray tracing, and hit lighting in place of the surface cache.
