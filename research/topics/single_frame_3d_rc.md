# Single-frame 3D radiance cascades

What the whole body of research says about 3D global illumination from radiance cascades alone, computed from scratch every frame with no temporal accumulation and no denoiser, for a Godot `RenderingDevice` implementation. Each conclusion names the evidence it rests on and links the topic that holds it. Conclusions drawn here, not stated in any source, are marked "inference" or "derived" as in the other topics.

## What a single frame allows

A single-frame result depends on this frame's scene, camera, lights and emitters only. That rules out every form of lighting history and keeps scene structures:

| Kept across frames | Ruled out |
|---|---|
| Static geometry structures: distance fields, voxel bits, BVHs, hash tables of probe positions keyed by world cell | Accumulated radiance, reprojected probe values, exponential averages, reservoirs carried over frames |
| Cached hit points of static geometry, read with fresh lighting each frame ([Godot integration](godot_integration.md#connections)) | Hits lit from last frame's image or from a lighting cache ([scene representation](scene_representation_and_tracing.md#single-frame-assessment)) |
| Probe sets placed by a deterministic rule from this frame's view | Probe sets that converge over frames (surfel spawning, adaptive voting) |
| | Bounce feedback, jitter averaged over frames, work amortized over frame cycles |

The rule that geometry caches are allowed and lighting caches are not comes from [scene representation](scene_representation_and_tracing.md#single-frame-assessment), and it decides most of what follows (inference).

Four consequences follow (inference):

- **Deterministic errors stay.** Ringing, leaks, blocky penumbras and small-light aliasing repeat every frame and must be fixed in the merge or accepted ([artifacts](artifacts_and_fixes.md#single-frame-assessment)).
- **Noise must be small in one frame.** Wherever a stored direction rests on one or two rays, there is nothing to average it with.
- **Placement must be stable by construction.** A probe set that moves with the camera moves its error pattern too, which reads as flicker ([radiance caches](related_radiance_caches.md#single-frame-assessment)).
- **Every hit needs a radiance source from this frame,** and the result holds one bounce unless more are solved within the frame.

## Why RC fits

The theory needs no history. RC is deterministic and noise-free once each stored direction has enough rays, its cost does not depend on light count or scene content, and the errors it has are structured, not noise ([core theory](core_theory.md#single-frame-assessment)). Temporal reuse in public code comes from the hosts (Shadertoy and LegitScript run one pass per frame), from cost spreading, from bounce feedback and from hiding aliasing, never from the method ([history](history_and_landscape.md#single-frame-assessment)).

Single-frame 3D RC has been run and measured in these systems:

| System | Domain | Tracer | Cost | Hardware | Topic |
|---|---|---|---|---|---|
| Path of Exile 2 (shipped) | screen space | depth-buffer march, 128-bit occlusion masks | about 1 ms; about 3 ms; 0.8 ms at 4K | not stated; GTX 1050; RTX 4090 | [3D screen space](3d_screen_space.md#path-of-exile-2) |
| Abou Dan and Jensen | screen space | visibility bitmasks | 2, 6 and 26 ms (low, medium, high) | "modern hardware" | [theses](3d_screen_space_theses.md) |
| Dell'Ova | screen probes, world intervals | DXR | 2.36 ms at 1080p (spacing 4, 16 rays, 8 cascades) to 241.56 ms | RTX 3080 | [theses](3d_screen_space_theses.md) |
| Kaméus | screen probes, world intervals | inline ray queries | 9.72 to 13.34 ms at 2048×1024, one probe per 4×4 px | RTX 2070 | [theses](3d_screen_space_theses.md) |
| Gavras | screen probes, world intervals | Metal RT on the M1 (no RT hardware) | 32.77 to 155.90 ms at 1080p | M1 | [theses](3d_screen_space_theses.md) |
| Split RC | sparse world probes | OptiX hardware RT | 8.6 ms Sponza, 11.5 ms San Miguel | RTX 3080 Laptop | [3D world space](3d_world_space.md#measurements) |
| creikey | screen probes over a world voxel clipmap | voxel march | 0.76 ms at 640×360 | not stated | [world-space codes](3d_world_space_implementations.md) |
| jumeder | dense world grid | DXR | 960 MiB, 126 M rays per frame for a Cornell box | not stated | [world-space codes](3d_world_space_implementations.md) |
| Peter (2D reference) | 2D, one probe per pixel | distance field | 0.73 ms at 720p to 7.95 ms at 4K | RX 7900 XTX | [2D implementations](2d_implementations.md) |

Sannikov's two sparse 3D videos (60 to 100 fps with a screen-space marcher, 60 fps with hardware RT, all from scratch) and Blackline Interactive's claims point the same way without published numbers or code ([history](history_and_landscape.md#positions-on-3d-rc)).

The systems that do not run in one frame are informative too: Love and Deepspace converges each bounce over 28 frames, Coppen's surfel probes fill over at least 32 frames, every open Split RC code keeps history although the paper's table is single-frame, RCPG and Reservoir Cascades accumulate by design, and every engine GI (Lumen, daGI2, Brixelizer GI, HSGI, SDFGI, HDDAGI) relies on time ([surface probes](3d_surface_probes.md#single-frame-assessment), [world-space codes](3d_world_space_implementations.md#single-frame-assessment), [sampling and guiding](rc_for_sampling_and_guiding.md#single-frame-assessment), [engine GI](related_engine_gi.md#single-frame-assessment)).

**Where the evidence stands.** Single-frame RC is proven in screen space (shipped) and in world space with hardware ray tracing (one paper with a stage table). It is unproven in world space with a compute tracer, which is the case Godot presents, and no 3D single-frame result has been measured for quality against a reference at a known cost (inference).

## Where existing designs lean on time

Every temporal element found in the 3D designs, with the single-frame replacement the research supports:

| Temporal element | Where it appears | Why it is there | Single-frame replacement | Evidence |
|---|---|---|---|---|
| One cascade merged per frame | Shadertoy and LegitScript ports, HRC Shadertoys | the host allows a fixed pass count per frame | one dispatch per cascade from the top, trace fused with merge, two live buffers | [layout](cascade_layout_and_merging.md#single-frame-assessment), [history](history_and_landscape.md#single-frame-assessment) |
| Bounce feedback from last frame | gomezzz, wroughtinator, X3XfRM, HDDAGI, most 2D codes | multi-bounce for free | one bounce plus a sky or ambient term; a second solve per extra bounce; stored hit distances for `N` bounces in opaque scenes | [world space](3d_world_space.md#single-frame-assessment), [alternatives](light_transport_alternatives.md#single-frame-assessment) |
| Jitter and accumulation to hide aliasing, stochastic bilinear fixes | RCPG, Reservoir Cascades, temporal fix variants | turns deterministic error into noise that averages out | deterministic merge fixes: parent hit-distance test, hit bits, trilinear fix where affordable, cascade −1 | [artifacts](artifacts_and_fixes.md#single-frame-assessment), [world space](3d_world_space.md#leak-defences-in-world-space) |
| Block-consistent interval jitter | Reservoir Cascades | hides interval-boundary bands | overlapping or blended boundaries, or validation at the boundary | [sampling and guiding](rc_for_sampling_and_guiding.md#single-frame-assessment) |
| Probe sets that converge | surfel RC, SPWI with reprojection (0.1 to 0.5 s), adaptive caches | spawning and voting need several frames | probes placed from this frame by a fixed rule: Split RC's per-pixel insertion at a Chebyshev LOD, world-locked clipmaps | [surface probes](3d_surface_probes.md#single-frame-assessment), [world space](3d_world_space.md#placement-and-levels-of-detail) |
| Screen-probe flicker hidden by accumulation | every SPWI thesis, Alpha-Renderer, lXByRh | probes re-placed at new depths each frame | min/max probes, two-surface construction, world-locked probes, placement from unjittered matrices | [screen space](3d_screen_space.md#single-frame-assessment), [Godot integration](godot_integration.md#single-frame-assessment) |
| Cascade 0 noise at one ray per direction | Split RC at 4×4-pixel probes | one ray per pixel spread over 16 directions | larger probe footprints, more rays per pixel, a cascade −1 for contact light | [samples per direction](3d_world_space.md#samples-per-direction-per-frame-derived) |
| Hits lit from the previous frame | Lumen's surface cache, daGI2's lit scene, HSGI's voxels, SSIL | off-screen hits get light for free | direct light evaluated at each hit, or injected into the scene structure each frame, from emission and same-frame shadows | [scene representation](scene_representation_and_tracing.md#single-frame-assessment) |
| Work amortized over cycles | daGI2 (16×), HSGI (9× near, 121× far), Brixelizer's cascade schedule | fixed work per frame | RC's angular-spatial trade, which shrinks work per level by construction | [engine GI](related_engine_gi.md#single-frame-assessment) |
| Denoisers and temporal filters | HSGI (2.65 ms against 0.64 ms of tracing), Lumen, Solari's DLSS-RR | low ray counts | more rays and a merge; the denoiser's time goes into rays | [engine GI](related_engine_gi.md#connections) |
| Incremental scene updates | Brixelizer (every second or fourth frame), daGI2, EggyStudio (8 still frames) | rebuild cost | a per-frame structure for moving objects: a GPU LBVH, a dynamic clipmap, or same-frame screen marking | [scene representation](scene_representation_and_tracing.md#single-frame-assessment) |

Two conclusions follow (inference). First, most temporal elements are cost savings, and each has a same-frame replacement with a known price. Second, the two that have no cheap replacement are lagged bounces and same-frame hit lighting, and both concern what lights a hit, not the cascades.

## Design families

The 3D designs fall into seven families. Each is judged here for single-frame use under `RenderingDevice`; the measurements behind the costs are in [performance](performance.md).

### Screen-space RC

Probes and intervals both live in the depth buffer, marched along screen lines with occlusion bitmasks ([3D screen space](3d_screen_space.md#two-families)).

- **For:** it is the one shipped single-frame RC (PoE2), cheap at 1 to 3 ms, needs no world structure, and shares cost along screen lines like visibility-bitmask SSGI and horizon AO ([screen-space GI](related_screen_space_gi.md#connections)).
- **Against:** off-screen and hidden light is missing, thickness behind one depth layer is a guess, and upper cascades need prefiltered depth moments to stay stable.
- **Godot:** at PRE_OPAQUE this frame's depth and normals exist but its lit colour does not, and Forward+ has no albedo buffer ([Godot integration](godot_integration.md#buffers-in-a-callback)). In PoE2 only on-screen effects cast indirect light, point and spot lights are analytic with shadow maps, and RC adds the second bounce ([PoE2](3d_screen_space.md#path-of-exile-2)), which reads as RC gathering the directly lit screen (inference). In Godot that recipe either reads last frame's colour (a lag, with GI feeding back into the next solve) or runs after the opaque pass, where no albedo exists to multiply the result. A pure screen-space RC therefore cannot be both single-frame and correctly composited in Godot without an extra source of hit radiance (inference).

### Screen probes with world intervals (SPWI)

Probes come from the depth buffer and rays run through a world structure ([3D screen space](3d_screen_space.md#screen-probes-with-world-intervals)).

- **For:** off-screen light is reached, three theses (Dell'Ova, Kaméus, Gavras) ran it in one frame, and with hardware RT at 1080p the cost is a few ms.
- **Against:** tracing takes 87 to 96% of the time, so the tracer decides the cost; software traversal ran 4 to 80 times slower than DXR in the measured codes (Gavras's M1 at 0.08 to 0.38 G rays/s against 6 to 7 G on an RTX 3080, [throughput](3d_screen_space.md#ray-throughput-across-the-measured-spwi-codes-derived)). Probes re-placed each frame flicker under motion in every thesis.
- **Godot:** needs a compute tracer and a world structure that carries albedo and emission and is lit this frame. The floor at 1080p for 4 px probes with 16 directions over 6 cascades is 12.4 M rays per frame ([budgets](performance.md#budgets-for-single-frame-3d-rc-derived)).

### Sparse world probes near surfaces (Split RC)

Probes sit in world space at a level of detail chosen per pixel, stored in hash maps, with rays spawned at visible surfaces and split into cascades ([3D world space](3d_world_space.md#sparse-probes-near-surfaces)).

- **For:** the only published single-frame world-space RC with a stage table, 8.6 to 11.5 ms with hardware RT; probes sit on world grid cells and move only when a cell changes level of detail, so most of the error pattern stays fixed under camera motion (inference); ray splitting removes probes inside walls for free; cost is steady across scenes because LODs fix the probe count.
- **Against:** the deposit costs more than the trace with hardware RT (2.2 against 1.3 ms in Sponza), cascade 0 rests on `s = A/16` rays per direction per frame, and contact detail needs a separate cascade −1 (1.4 ms).
- **Godot:** 32-bit integer atomics with fixed-point deposits, multi-word hash slots and indirect dispatch sized on the GPU all map onto `RenderingDevice` ([world space](3d_world_space.md#single-frame-assessment)). Without hardware ray queries the trace grows to an estimated 4.5 to 5.2 ms in Sponza and 15.8 to 18.0 ms in San Miguel (derived there).

### Dense and clipmap world grids

Probes on a regular grid or nested clipmap, every cascade stored ([3D world space](3d_world_space.md#dense-grids)).

- **For:** simple indexing, hardware trilinear lookups, world-locked, and the natural form for volumetrics.
- **Against:** memory scales with volume: 128³ with 32 directions is about 1 GiB in fp16 and 130 M rays per frame, while 32³ to 64³ fits in 16 to 124 MiB (derived, [budgets](performance.md#budgets-for-single-frame-3d-rc-derived)). Probes inside walls need validity rules, and 8-probe interpolation leaks through thin walls.
- **Godot:** gomezzz's dense Godot solver stops near a 64³ grid at its layout; Vulkan guarantees only 128 MiB per storage buffer ([Godot projects](godot_projects.md#single-frame-assessment)). Fits a bounded volume (a room, a fog region), not a whole open scene.

### Hybrids: screen near field, world far field

A screen-space layer for contact detail over world probes for the far field: EggyStudio, creikey, Split RC's own screen-space cascade −1, and reduz's plan for Godot ([world-space codes](3d_world_space_implementations.md#connections), [Godot integration](godot_integration.md#connections)).

- **For:** every hybrid puts the world representation where the screen fails; EggyStudio runs at 0.59 to 1.00 ms and under 10 MB at 800×450, creikey at 0.76 ms at 640×360.
- **Against:** two representations must agree at the hand-off, which every engine system tunes by hand ([engine GI](related_engine_gi.md#connections)), and the measured hybrids settle over frames (EggyStudio in 5) or were not measured for quality.
- **Godot:** the screen layer runs at PRE_OPAQUE on depth and normals; its hits read the world layer's same-frame radiance, which removes the lit-colour problem of pure screen-space RC (inference).

### Surface probes

Surfels or UV charts carry the probes ([3D surface probes](3d_surface_probes.md)).

- **Against for single-frame:** surfel probe sets are temporal state, and charts need authored or generated UVs with seams. Love and Deepspace, the shipped member, converges over frames.
- **What carries over:** surfels as a tracing proxy built once per mesh, and hit-distance visibility in the merge.

### Holographic RC and volumetric grids

- **Dense 3D HRC** needs 1 to 1.8 GB and 77 ms at 64³, so it is out for scene GI; its extension idea (building long intervals from short ones) and its bandwidth lessons carry over ([holographic RC](holographic_rc.md#single-frame-assessment)).
- **Volumetric RC** is single-frame by construction with deterministic marching, but a dense 192³ grid took 20 to 34 ms; a bounded fog volume with far cascades on mips is the affordable form ([volumetric](volumetric_and_radiative_transfer.md#single-frame-assessment)).

### The families compared

| Family | Single-frame evidence | Hardware RT used | Memory at 1080p | Main single-frame risk | Godot fit (inference) |
|---|---|---|---|---|---|
| Screen-space RC | shipped (PoE2) | no | tens of MB | off-screen light, hit radiance at PRE_OPAQUE | near-field layer only |
| SPWI | three theses | yes, except Gavras (M1, software traversal) | 24 MB to 3.6 GB (Dell'Ova) | tracer throughput, probe flicker | needs a fast compute tracer |
| Sparse world probes | Split RC | yes | not reported | deposit atomics, cascade 0 noise, compute trace cost | strongest world-space candidate |
| Dense or clipmap grid | jumeder, creikey | mixed | 16 MiB (32³) to 1 GiB (128³) | memory, wall leaks | bounded regions, volumetrics |
| Hybrid screen plus world | EggyStudio, creikey | no | under 10 MB to 12 MiB | hand-off tuning, unmeasured quality | matches the engine's own plan |
| Surface probes | none | mixed | 423 MiB (Coppen) | probe convergence | tracing proxies only |
| 3D HRC | none | no | 1 to 1.8 GB at 64³ | memory | out |

The evidence favours a hybrid of a screen-space near field over world-locked world-space cascades, with the world part either sparse probes near surfaces or a bounded clipmap (inference). It is the only arrangement that keeps the error pattern fixed under camera motion, reaches off-screen light, gives screen hits a same-frame radiance source and has a measured cost below 1 ms in some form. Its weakest point is that no hybrid has been measured for quality against a reference.

## Budgets

The detailed tables are in [performance](performance.md#budgets-for-single-frame-3d-rc-derived). The figures that set the design:

- **Ray throughput is the number to plan with.** Tracing is 87 to 96% of SPWI time, and a single-frame RC spends on rays what other systems spend on denoising and history ([3D screen space](3d_screen_space.md#connections), [engine GI](related_engine_gi.md#connections)). Measured rates range from 6 to 8 G rays/s for hardware RT on short coherent rays to 0.08 G rays/s for software traversal of Sponza on an M1, with compute BVH and voxel DDA figures at 2.8 to 3.9 G rays/s ([performance](performance.md#normalized-throughput-derived)).
- **At 1080p in 4 ms,** a compute tracer at 1 to 3 G rays/s affords 4 to 12 M rays. That covers screen probes at 8 px spacing (3.1 M rays) or 4 px spacing (12.4 M) with 16 cascade 0 rays and 6 cascades, or 2 to 6 rays per pixel in a splitting design (2.07 M rays per ray per pixel), but not a dense 128³ grid (130 M) (derived).
- **Memory is not the limit for screen-anchored and sparse designs:** 1080p screen probes at 4 px spacing with 16 directions need 95 MiB for six cascades in RGBA16F, 32 MiB with two live cascades, and 35.6 MiB for six cascades with pre-averaged storage above cascade 0, the order of Dell'Ova's 34 MB (derived). Dense grids are the exception.
- **Reference budgets:** Lumen holds GI and reflections to 4 ms at 60 fps on PS5; HDDAGI's light update and probe trace take 0.93 ms on a GTX 1650; Godot's AO passes cost 0.7 to 1.45 ms on an RTX 2070, a budget a screen-space RC layer replaces ([engine GI](related_engine_gi.md), [Godot integration](godot_integration.md), [Godot projects](godot_projects.md#connections)).

## Tracing and scene representation under `RenderingDevice`

- **The tracer is a compute shader.** Compute shaders cannot issue ray queries in Godot 4.7.2, and the ray tracing pipeline is experimental, Vulkan-only and fails on indexed geometry in release builds ([RenderingDevice notes](../../docs/rendering_device.md#ray-tracing)). Every hardware-RT figure above overstates the throughput a Godot compute build can reach (inference).
- **Exact near, coarse far.** Cascade 0 decides contact shadows and leaks and needs an exact structure (triangles, fine voxel bits, or the depth buffer for a screen near field); upper cascades can march coarse mips with directional opacity, which gave DexRT 3.5× from mips alone ([scene representation](scene_representation_and_tracing.md#single-frame-assessment), [volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)).
- **Segment length picks the structure.** Grids and fields with empty-space skipping win on short segments, BVHs and hardware RT on long divergent rays, and RC's segments grow 2 to 4 times per cascade ([scene representation](scene_representation_and_tracing.md#connections)).
- **Compute routes exist for every family:** JFA or `InterlockedMin` distance fields, HDDA over 32-bit bitmask words, a GPU LBVH with integer atomics and indirect dispatch, and tinybvh's GLSL kernels ([scene representation](scene_representation_and_tracing.md#single-frame-assessment)). The only figure under `RenderingDevice` is a floor: gomezzz's BVH tracer fits 2.34 M segments into a 6.24 ms frame, at least 0.375 G segments per second on an RTX 4060 Ti ([Godot projects](godot_projects.md#derived-points)).
- **Moving geometry must enter in the same frame.** The engine exposes no mesh buffer RIDs, so triangles come from `mesh_surface_get_arrays()` on the CPU or from rasterizing into an own structure without a geometry shader; gomezzz's CPU BVH took 1.2 s for 72,012 triangles ([Godot integration](godot_integration.md#world-space-inputs), [Godot projects](godot_projects.md#single-frame-assessment)). A static structure plus a small per-frame dynamic one is the consistent answer (inference).
- **Atomics are 32-bit integers only.** Deposits, splats and counters use fixed-point integer sums; hash keys fit 32 bits or a multi-word slot ([RenderingDevice notes](../../docs/rendering_device.md#atomics)).
- **No CPU round trips.** Probe and ray counts size dispatches through indirect arguments written on the GPU ([RenderingDevice notes](../../docs/rendering_device.md#indirect-dispatch)).

## Leaks without history

- **Placement first.** Leaks in 3D come mostly from the scene representation and probe placement, not the merge ([artifacts](artifacts_and_fixes.md#single-frame-assessment)). Ray splitting spawns rays at visible surfaces, so no probe fires from inside a wall ([world space](3d_world_space.md#single-frame-assessment)).
- **Binary parent tests at the merge.** The parent hit-distance test is free given stored hit distances, the one-bit hit mask costs about 50% more merge time, and validated parents cost extra rays (+33 to 53% in 2D) ([world space](3d_world_space.md#leak-defences-in-world-space), [sampling and guiding](rc_for_sampling_and_guiding.md#single-frame-assessment)).
- **Pull-back on far reads** is the cheapest defence in engine GI and applies at each interval end ([engine GI](related_engine_gi.md#connections)).
- **The full trilinear fix** costs about 4.4× in time on a 3D grid at `l = 4`; a simplex grid would need 4 corners instead of 8 ([artifacts](artifacts_and_fixes.md#single-frame-assessment)).
- **Scaling removes the bin shift.** With ×4 directions and ×4 intervals per cascade in 3D, the parallax of a parent's bin stays constant across cascades, so reprojected parent lookups may not be needed ([sampling and guiding](rc_for_sampling_and_guiding.md#single-frame-assessment), [core theory](core_theory.md#parallax-in-bin-units-derived)). gomezzz's interval doubling with ×4 directions grows the error to 1.5 to 8 parent bins by its top level ([Godot projects](godot_projects.md#connections)).

## Lighting the hits and the composite

- **Direct light stays outside RC.** RC alone does not resolve sun and small-light shadows at practical probe spacings; direct light keeps its own shadows, and RC carries the indirect part ([core theory](core_theory.md#single-frame-assessment)). Emitters smaller than about twice the cascade 0 spacing are lit analytically in EggyStudio, wroughtinator and creikey ([world space](3d_world_space.md#connections)).
- **Hit radiance in the same frame** comes from emission plus direct light at the hit: shadow rays through the same structure, or light injected into the scene structure each frame ([shading the hit](scene_representation_and_tracing.md#shading-the-hit)).
- **Godot's shadow maps arrive too late for PRE_OPAQUE.** The renderer draws shadows in `_pre_opaque_render`, after the PRE_OPAQUE callbacks ([frame order](godot_integration.md#frame-order-and-compositor-hooks)), so a solve that must feed this frame's opaque pass cannot read this frame's shadow maps, even apart from whether a script can reach the shadow atlas at all (derived from the frame order). Same-frame hit lighting therefore needs the RC tracer's own shadow rays or its own light injection (inference).
- **The composite** goes through per-material `IRRADIANCE`, which takes `E/π` and requires every opaque material to be a `ShaderMaterial`; SSAO multiplies on top, so a pure RC setup turns SSAO and SSIL off ([Godot integration](godot_integration.md#getting-gi-into-shading)).
- **Double counting** is unresolved: light that Godot shades directly must not reach the RC result again through an emitter, while its bounce must ([core theory](core_theory.md#open-questions)).

## Bounces

A single frame gives one bounce. The routes to more, none measured in 3D:

- a second full solve seeded from the first, doubling cost per bounce (2D HRC, TypeGPU) ([holographic RC](holographic_rc.md#single-frame-assessment));
- a coarse secondary solve at a lower LOD, as Split RC does over frames ([world space](3d_world_space.md#single-frame-assessment));
- `N` bounces from stored hit distances in opaque scenes, or a fixed number of Jacobi or Anderson iterations ([alternatives](light_transport_alternatives.md#single-frame-assessment)).

One bounce plus a sky and ambient term is the single-frame baseline every measured 3D system starts from (inference).

## Parameters the evidence supports

| Parameter | Value | Evidence |
|---|---|---|
| Angular branching | ×4 directions per cascade | the 3D RC law; Split RC |
| Interval scaling | ×4 per cascade (`l = 4`), about 5 cascades per scene | equal error; three independent derivations agree ([core theory](core_theory.md#connections)) |
| Cascade 0 directions | 32 | smallest count that tested well; 8 showed obvious artifacts ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)) |
| Cascade 0 interval | 1.6 to 1.7 cascade 0 spacings | equal-error 1.60 and diagonal 1.73 nearly coincide at 32 directions |
| Direction map | nested equal-area (cylindrical or Clarberg's octahedral) | avoids per-texel weights ([layout](cascade_layout_and_merging.md#single-frame-assessment)) |
| Merge | trilinear over 8 parents with a binary visibility test | [layout](cascade_layout_and_merging.md#single-frame-assessment), [world space](3d_world_space.md#leak-defences-in-world-space) |
| Schedule | one dispatch per cascade top-down, two live buffers | [layout](cascade_layout_and_merging.md#single-frame-assessment) |
| Final gather | 6×6 octahedral irradiance tiles per probe | Split RC, erhe |
| Formats | RGBA16F with one transmittance channel; R11G11B10F for radiance only | [volumetric](volumetric_and_radiative_transfer.md#single-frame-assessment), [layout](cascade_layout_and_merging.md#formats) |
| Contact detail | a screen-space cascade −1 | Split RC (1.4 ms), PoE2 |

## Open problems, ranked

Ranked by how much each blocks the goal. Each problem states a hypothesis for the theoretical phase and the evidence that motivates it.

1. **Compute tracer throughput under `RenderingDevice`.** Only a floor exists for GLSL tracing in Godot (gomezzz's 0.375 G segments per second from a whole-frame time), and every budget above depends on the real figure. *Hypothesis:* an HDDA over bitmask bricks for cascades 0 and 1 with mip marching above reaches 2 to 3 G short rays per second on mid-range desktop GPUs, enough for 8 to 12 M rays in 4 ms. *Evidence:* 15 M rays in 5 ms through 4×4×4 bit cubes, tinybvh's 2.8 G primary rays per second, DexRT's mip speedups ([scene representation](scene_representation_and_tracing.md#single-frame-assessment)).
2. **Same-frame radiance at hits.** Godot's frame order gives neither this frame's lit colour nor its shadow maps to a solve that must feed the opaque pass. *Hypothesis:* per-frame light injection into the scene structure (one shadow ray per lit surface cell per light) costs less than shadow rays per hit, because surface cells are far fewer than RC's per-frame rays. *Evidence:* SDFGI's and HDDAGI's injection passes, the hit-shading options ([scene representation](scene_representation_and_tracing.md#shading-the-hit), [Godot integration](godot_integration.md#single-frame-assessment)).
3. **Cascade 0 noise and stability in one frame.** Split RC's `s = A/16` gives one ray per direction cell at 4×4-pixel probes, and screen-placed probes flicker. *Hypothesis:* world-locked probes with `s ≥ 4` (8×8-pixel footprints or four rays per pixel) plus a screen-space cascade −1 give stable contact light without history. *Evidence:* the samples-per-direction table, Kaméus's Min+Max, Gautron's moving-sample flicker ([world space](3d_world_space.md#samples-per-direction-per-frame-derived), [screen-space theses](3d_screen_space_theses.md#connections), [radiance caches](related_radiance_caches.md#single-frame-assessment)).
4. **A leak-free merge at bounded cost.** *Hypothesis:* at `K = 4, l = 4` the constant bin shift plus a free parent hit-distance test removes most ringing and merge leaks without the 4.4× trilinear fix. *Evidence:* the bin-shift derivation and the leak defences ([core theory](core_theory.md#parallax-in-bin-units-derived), [world space](3d_world_space.md#leak-defences-in-world-space)).
5. **Quality against cost.** No 3D study measures quality per millisecond against a reference; Dell'Ova measures cost only and Kaméus quality at three densities ([screen-space theses](3d_screen_space_theses.md#connections)). *Hypothesis:* a path-traced reference of the same scene, computed offline, is enough to rank the families and parameters above. This is a precondition for every other comparison.
6. **Deposits without float or 64-bit atomics.** *Hypothesis:* per-probe tracing for cascade 0 with splitting only above it, or sort-based binning, avoids the atomic contention that made Split RC's deposit its largest stage. *Evidence:* 16 ms with atomics against 0.3 ms without in one build, 1.5 ms sort-based binning for 10 M texels ([world space](3d_world_space.md#open-questions)).
7. **Moving geometry in the same frame.** *Hypothesis:* a static structure plus a per-frame dynamic one capped by the static hit distance keeps rebuild cost proportional to moving content. *Evidence:* the sparse-build proposal, Wicked Engine's per-frame LBVH, creikey's dynamic clipmap ([scene representation](scene_representation_and_tracing.md#single-frame-assessment)).
8. **A second bounce in one frame.** *Hypothesis:* a coarse second solve two LODs up costs a fraction of the first and captures most second-bounce energy at typical albedos. *Evidence:* Split RC's multi-bounce over frames, the stored-hit-distance route ([world space](3d_world_space.md#open-questions), [alternatives](light_transport_alternatives.md#open-questions)).
9. **Small lights and the direct split.** *Hypothesis:* lights and emitters below twice the cascade 0 spacing leave the RC scene for analytic direct lighting, and larger emitters stay, which avoids double counting by construction. *Evidence:* the penumbra condition's light-size limit and the analytic small-emitter terms ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported), [world space](3d_world_space.md#connections)).
10. **The hand-off in a hybrid.** *Hypothesis:* stating the screen-to-world hand-off as an RC interval boundary (length in probe sizes, pull-back on the far read) replaces the hand tuning of engine GI. *Evidence:* every engine system's hand-picked lengths ([engine GI](related_engine_gi.md#connections)).

Theory questions that do not block a first implementation but bear on a paper: whether a 3D lattice can make the extend identity exact without HRC's `O(N⁴)` memory, which interval scaling minimizes perceived error in 3D, how far irradiance gradients from each probe's own rays improve the merge's spatial interpolation, and whether a deterministic RIS merge keeps Reservoir Cascades' leak reduction without its noise ([core theory](core_theory.md#open-questions), [radiance caches](related_radiance_caches.md#open-questions), [sampling and guiding](rc_for_sampling_and_guiding.md#open-questions)).
