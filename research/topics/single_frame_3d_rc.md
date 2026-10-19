# Single-frame 3D radiance cascades

What the whole body of research says about 3D global illumination from radiance cascades alone, computed from scratch every frame with no temporal accumulation and no denoiser, including what Godot's `RenderingDevice` allows as a host. Each conclusion names the evidence it rests on and links the topic that holds it. Conclusions drawn here, not stated in any source, are marked "inference" or "derived" as in the other topics.

## Contents

- [What a single frame allows](#what-a-single-frame-allows)
- [Why RC fits](#why-rc-fits)
- [Where existing designs lean on time](#where-existing-designs-lean-on-time)
- [Design families](#design-families)
  - [Screen-space RC](#screen-space-rc)
  - [Screen probes with world intervals (SPWI)](#screen-probes-with-world-intervals-spwi)
  - [Sparse world probes near surfaces (Split RC)](#sparse-world-probes-near-surfaces-split-rc)
  - [Dense and clipmap world grids](#dense-and-clipmap-world-grids)
  - [Hybrids: screen near field, world far field](#hybrids-screen-near-field-world-far-field)
  - [Surface probes](#surface-probes)
  - [Holographic RC and volumetric grids](#holographic-rc-and-volumetric-grids)
  - [The families compared](#the-families-compared)
- [Budgets](#budgets)
- [Tracing and scene representation under `RenderingDevice`](#tracing-and-scene-representation-under-renderingdevice)
- [Leaks without history](#leaks-without-history)
- [Lighting the hits and the composite](#lighting-the-hits-and-the-composite)
- [Bounces](#bounces)
- [Parameters the evidence supports](#parameters-the-evidence-supports)
- [Where the evidence stops](#where-the-evidence-stops)

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
| Blackline Interactive (Spatium) | surface atlas (inferred) | compute BVH | GI 12.1 to 12.6 ms in a room and a Cornell box, 11.4 to 18 ms in Sponza, 15.9 to 27.8 ms in a 10.8 M-triangle scene; from video HUDs, single-frame by the author's claim | Radeon Pro 5500M (2019 laptop, no RT hardware) | [3D surface probes](3d_surface_probes.md#a-generated-surface-atlas-blackline-interactive) |
| Peter (2D reference) | 2D, one probe per pixel | distance field | 0.73 ms at 720p to 7.95 ms at 4K | RX 7900 XTX | [2D implementations](2d_implementations.md) |

Sannikov's two sparse 3D videos (60 to 100 fps with a screen-space marcher, 60 fps with hardware RT, all from scratch) point the same way without published numbers or code ([history](history_and_landscape.md#positions-on-3d-rc)). Blackline Interactive's row is read from video HUDs of closed code, and its single-frame operation is the author's claim.

The systems that do not run in one frame are informative too: Love and Deepspace converges each bounce over 28 frames, Coppen's surfel probes fill over at least 32 frames, every open Split RC code keeps history although the paper's table is single-frame, RCPG and Reservoir Cascades accumulate by design, and every engine GI (Lumen, daGI2, Brixelizer GI, HSGI, SDFGI, HDDAGI) relies on time ([surface probes](3d_surface_probes.md#single-frame-assessment), [world-space codes](3d_world_space_implementations.md#single-frame-assessment), [sampling and guiding](rc_for_sampling_and_guiding.md#single-frame-assessment), [engine GI](related_engine_gi.md#single-frame-assessment)).

**Where the evidence stands.** Single-frame RC is proven in screen space (shipped) and in world space with hardware ray tracing (one paper with a stage table). In world space with a compute tracer, the case of hosts without ray queries such as Godot, the one instance is Blackline's surface-atlas build: its HUDs show 11 to 28 ms of GI on a 2019 laptop GPU without RT hardware, but there is no code or quality measurement, and nothing shown rules out history. No 3D single-frame result has been measured for quality against a reference at a known cost (inference).

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

The 3D designs fall into seven families. Each is judged here for single-frame use and for Godot's `RenderingDevice` as a host; the measurements behind the costs are in [performance](performance.md).

### Screen-space RC

Probes and intervals both live in the depth buffer, marched along screen lines with occlusion bitmasks ([3D screen space](3d_screen_space.md#two-families)).

- **For:** it is the one shipped single-frame RC (PoE2), cheap at 1 to 3 ms, needs no world structure, and shares cost along screen lines like visibility-bitmask SSGI and horizon AO ([screen-space GI](related_screen_space_gi.md#connections)).
- **Against:** off-screen and hidden light is missing, thickness behind one depth layer is a guess, and upper cascades need prefiltered depth moments to stay stable.
- **In Godot:** at PRE_OPAQUE this frame's depth and normals exist but its lit colour does not, and Forward+ has no albedo buffer ([Godot integration](godot_integration.md#buffers-in-a-callback)). In PoE2 only on-screen effects cast indirect light, point and spot lights are analytic with shadow maps, and RC adds the second bounce ([PoE2](3d_screen_space.md#path-of-exile-2)), which reads as RC gathering the directly lit screen (inference). In Godot that recipe either reads last frame's colour (a lag, with GI feeding back into the next solve) or runs after the opaque pass, where no albedo exists to multiply the result. A pure screen-space RC therefore cannot be both single-frame and correctly composited in Godot without an extra source of hit radiance (inference).

### Screen probes with world intervals (SPWI)

Probes come from the depth buffer and rays run through a world structure ([3D screen space](3d_screen_space.md#screen-probes-with-world-intervals)).

- **For:** off-screen light is reached, three theses (Dell'Ova, Kaméus, Gavras) ran it in one frame, and with hardware RT at 1080p the cost is a few ms.
- **Against:** tracing takes 87 to 96% of the time, so the tracer decides the cost; software traversal ran 4 to 80 times slower than DXR in the measured codes (Gavras's M1 at 0.08 to 0.38 G rays/s against 6 to 7 G on an RTX 3080, [throughput](3d_screen_space.md#ray-throughput-across-the-measured-spwi-codes-derived)). Probes re-placed each frame flicker under motion in every thesis.
- **In Godot:** it needs a compute tracer and a world structure that carries albedo and emission and is lit this frame. The floor at 1080p for 4 px probes with 16 directions over 6 cascades is 12.4 M rays per frame ([budgets](performance.md#budgets-for-single-frame-3d-rc-derived)).

### Sparse world probes near surfaces (Split RC)

Probes sit in world space at a level of detail chosen per pixel, stored in hash maps, with rays spawned at visible surfaces and split into cascades ([3D world space](3d_world_space.md#sparse-probes-near-surfaces)).

- **For:** the only published single-frame world-space RC with a stage table, 8.6 to 11.5 ms with hardware RT; probes sit on world grid cells and move only when a cell changes level of detail, so most of the error pattern stays fixed under camera motion (inference); ray splitting removes probes inside walls for free; cost is steady across scenes because LODs fix the probe count.
- **Against:** the deposit costs more than the trace with hardware RT (2.2 against 1.3 ms in Sponza), cascade 0 rests on `s = A/16` rays per direction per frame, and contact detail needs a separate cascade −1 (1.4 ms).
- **In Godot:** 32-bit integer atomics with fixed-point deposits, multi-word hash slots and indirect dispatch sized on the GPU all map onto `RenderingDevice` ([world space](3d_world_space.md#single-frame-assessment)). Without hardware ray queries the trace grows to an estimated 4.5 to 5.2 ms in Sponza and 15.8 to 18.0 ms in San Miguel (derived there).

### Dense and clipmap world grids

Probes on a regular grid or nested clipmap, every cascade stored ([3D world space](3d_world_space.md#dense-grids)).

- **For:** simple indexing, hardware trilinear lookups, world-locked, and the natural form for volumetrics.
- **Against:** memory scales with volume: 128³ with 32 directions is about 1 GiB in fp16 and 130 M rays per frame, while 32³ to 64³ fits in 16 to 124 MiB (derived, [budgets](performance.md#budgets-for-single-frame-3d-rc-derived)). Probes inside walls need validity rules, and 8-probe interpolation leaks through thin walls.
- **In Godot:** gomezzz's dense Godot solver stops near a 64³ grid at its layout; Vulkan guarantees only 128 MiB per storage buffer ([Godot projects](godot_projects.md#single-frame-assessment)). Fits a bounded volume (a room, a fog region), not a whole open scene.

### Hybrids: screen near field, world far field

A screen-space layer for contact detail over world probes for the far field: EggyStudio, creikey, Split RC's own screen-space cascade −1, and reduz's plan for Godot ([world-space codes](3d_world_space_implementations.md#connections), [Godot integration](godot_integration.md#connections)).

- **For:** every hybrid puts the world representation where the screen fails; EggyStudio runs at 0.59 to 1.00 ms and under 10 MB at 800×450, creikey at 0.76 ms at 640×360.
- **Against:** two representations must agree at the hand-off, which every engine system tunes by hand ([engine GI](related_engine_gi.md#connections)), and the measured hybrids settle over frames (EggyStudio in 5) or were not measured for quality.
- **In Godot:** the screen layer runs at PRE_OPAQUE on depth and normals; its hits read the world layer's same-frame radiance, which removes the lit-colour problem of pure screen-space RC (inference).

### Surface probes

Surfels or UV charts carry the probes ([3D surface probes](3d_surface_probes.md)).

- **Against for single-frame:** surfel probe sets are temporal state, and charts need authored or generated UVs with seams. Love and Deepspace, the shipped member, converges over frames.
- **For single-frame:** a generated surface atlas appears to carry Blackline's Spatium, the one single-frame world-space RC on a compute tracer shown with timings: 11.4 to 18 ms of GI in Sponza at 4.89 M rays per frame on a Radeon Pro 5500M, a cost set by atlas texels instead of pixels, and no probe inside a wall ([surface atlas](3d_surface_probes.md#a-generated-surface-atlas-blackline-interactive)). Its costs are weak contact shadows at 10 to 25 cm texels, chart seams, and an atlas build that must handle arbitrary and moving meshes (inference).
- **What carries over:** surfels as a tracing proxy built once per mesh, hit-distance visibility in the merge, and the atlas as a probe domain.

### Holographic RC and volumetric grids

- **Dense 3D HRC** needs 1 to 1.8 GB and 77 ms at 64³, so it is out for scene GI; its extension idea (building long intervals from short ones) and its bandwidth lessons carry over ([holographic RC](holographic_rc.md#single-frame-assessment)).
- **Volumetric RC** is single-frame by construction with deterministic marching, but a dense 192³ grid took 20 to 34 ms; a bounded fog volume with far cascades on mips is the affordable form ([volumetric](volumetric_and_radiative_transfer.md#single-frame-assessment)).

### The families compared

| Family | Single-frame evidence | Hardware RT used | Memory at 1080p | Main single-frame risk | Fit to Godot's `RenderingDevice` (inference) |
|---|---|---|---|---|---|
| Screen-space RC | shipped (PoE2) | no | tens of MB | off-screen light, hit radiance at PRE_OPAQUE | near-field layer only |
| SPWI | three theses | yes, except Gavras (M1, software traversal) | 24 MB to 3.6 GB (Dell'Ova) | tracer throughput, probe flicker | needs a fast compute tracer |
| Sparse world probes | Split RC | yes | not reported | deposit atomics, cascade 0 noise, compute trace cost | the strongest world-space fit |
| Dense or clipmap grid | jumeder, creikey | mixed | 16 MiB (32³) to 1 GiB (128³) | memory, wall leaks | bounded regions, volumetrics |
| Hybrid screen plus world | EggyStudio, creikey | no | under 10 MB to 12 MiB | hand-off tuning, unmeasured quality | matches reduz's plan for Godot |
| Surface probes | observed only (Blackline's HUDs, closed code) | no (Blackline's compute BVH) | 423 MiB (Coppen); 722 MB to 3.7 GB of VRAM in all (Blackline) | probe convergence (surfels); atlas generation, seams and contact shadows (atlas) | an atlas as the world part; tracing proxies |
| 3D HRC | none | no | 1 to 1.8 GB at 64³ | memory | out |

The evidence favours a hybrid of a screen-space near field over world-locked world-space cascades, with the world part sparse probes near surfaces, a bounded clipmap or a generated surface atlas (inference). It is the only arrangement that keeps the error pattern fixed under camera motion, reaches off-screen light, gives screen hits a same-frame radiance source and has a measured cost below 1 ms in some form. Its weakest point is that no hybrid has been measured for quality against a reference. The surface atlas is the only world part with an observed single-frame instance on a compute tracer, and a screen-space near field would supply the contact shadows its texel size loses (inference).

## Budgets

The detailed tables are in [performance](performance.md#budgets-for-single-frame-3d-rc-derived). The figures that bound a single-frame design:

- **Ray throughput sets the cost.** Tracing is 87 to 96% of SPWI time, and a single-frame RC spends on rays what other systems spend on denoising and history ([3D screen space](3d_screen_space.md#connections), [engine GI](related_engine_gi.md#connections)). Measured rates range from 6 to 8 G rays/s for hardware RT on short coherent rays to 0.08 G rays/s for software traversal of Sponza on an M1, with compute BVH and voxel DDA figures at 2.8 to 3.9 G rays/s ([performance](performance.md#normalized-throughput-derived)).
- **At 1080p in 4 ms,** a compute tracer taken at 1 to 3 G rays/s, at and below the measured compute rates, affords 4 to 12 M rays. That covers screen probes at 8 px spacing (3.1 M rays) or 4 px spacing (12.4 M) with 16 cascade 0 rays and 6 cascades, or 2 to 6 rays per pixel in a splitting design (2.07 M rays per ray per pixel), but not a dense 128³ grid (130 M) (derived).
- **Memory is not the limit for screen-anchored and sparse designs:** 1080p screen probes at 4 px spacing with 16 directions need 95 MiB for six cascades in RGBA16F, 32 MiB with two live cascades, and 35.6 MiB for six cascades with pre-averaged storage above cascade 0, the order of Dell'Ova's 34 MB (derived). Dense grids are the exception.
- **Reference budgets:** Lumen holds GI and reflections to 4 ms at 60 fps on PS5; HDDAGI's light update and probe trace take 0.93 ms on a GTX 1650; Godot's AO passes cost 0.7 to 1.45 ms on an RTX 2070, a budget a screen-space RC layer replaces ([engine GI](related_engine_gi.md), [Godot integration](godot_integration.md), [Godot projects](godot_projects.md#connections)).

## Tracing and scene representation under `RenderingDevice`

- **The tracer is a compute shader.** Compute shaders cannot issue ray queries in Godot 4.7.2, and the ray tracing pipeline is experimental, Vulkan-only and fails on indexed geometry in release builds ([RenderingDevice notes](../../docs/rendering_device.md#ray-tracing)). Every hardware-RT figure above overstates the throughput a compute tracer under `RenderingDevice` reaches (inference).
- **Exact near, coarse far.** Cascade 0 decides contact shadows and leaks and needs an exact structure (triangles, fine voxel bits, or the depth buffer for a screen near field); upper cascades can march coarse mips with directional opacity, which gave DexRT 3.5× from mips alone ([scene representation](scene_representation_and_tracing.md#single-frame-assessment), [volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)).
- **Segment length picks the structure.** Grids and fields with empty-space skipping win on short segments, BVHs and hardware RT on long divergent rays, and RC's segments grow 2 to 4 times per cascade ([scene representation](scene_representation_and_tracing.md#connections)).
- **Compute routes exist for every family:** JFA or `InterlockedMin` distance fields, HDDA over 32-bit bitmask words, a GPU LBVH with integer atomics and indirect dispatch, and tinybvh's GLSL kernels ([scene representation](scene_representation_and_tracing.md#single-frame-assessment)). The one figure measured under `RenderingDevice` is a floor: gomezzz's BVH tracer fits 2.34 M segments into a 6.24 ms frame, at least 0.375 G segments per second on an RTX 4060 Ti ([Godot projects](godot_projects.md#derived-points)). Its compute shaders are ordinary Vulkan compute dispatches, so the compute-class rates apply there ([performance](performance.md#normalized-throughput-derived)).
- **Moving geometry must enter in the same frame.** The engine exposes no mesh buffer RIDs, so triangles come from `mesh_surface_get_arrays()` on the CPU or from rasterizing into an own structure without a geometry shader; gomezzz's CPU BVH took 1.2 s for 72,012 triangles ([Godot integration](godot_integration.md#world-space-inputs), [Godot projects](godot_projects.md#single-frame-assessment)). A static structure plus a small per-frame dynamic one is the consistent answer (inference).
- **Atomics are 32-bit integers only.** Deposits, splats and counters use fixed-point integer sums; hash keys fit 32 bits or a multi-word slot ([RenderingDevice notes](../../docs/rendering_device.md#atomics)).
- **No CPU round trips.** Probe and ray counts size dispatches through indirect arguments written on the GPU ([RenderingDevice notes](../../docs/rendering_device.md#indirect-dispatch)).

## Leaks without history

- **Placement first.** Leaks in 3D come mostly from the scene representation and probe placement, not the merge ([artifacts](artifacts_and_fixes.md#single-frame-assessment)). Ray splitting spawns rays at visible surfaces, so no probe fires from inside a wall ([world space](3d_world_space.md#single-frame-assessment)).
- **Binary parent tests at the merge.** The parent hit-distance test is free given stored hit distances, the one-bit hit mask costs about 50% more merge time, and validated parents cost extra rays (+33 to 53% in 2D) ([world space](3d_world_space.md#leak-defences-in-world-space), [sampling and guiding](rc_for_sampling_and_guiding.md#single-frame-assessment)). Measured in a dense voxel grid with exact tracing, the vanilla merge lets 4.5% of the sky through walls one voxel thick and 0.26% through three; the parent hit-distance test cannot act above the first hand-over at the equal-error `t0`, since a parent's rays start beyond its distance to the lower probe, and changes nothing; a test along the lower probe's own stored ray toward each parent's interval start (the self test) halves the leak for one extra texel read per parent ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#the-self-test-derived-and-measured)).
- **Pull-back on far reads** is the cheapest defence in engine GI and applies at each interval end ([engine GI](related_engine_gi.md#connections)).
- **The full trilinear fix** costs about 4.4× in time on a 3D grid at `l = 4`; a simplex grid needs 4 corners instead of 8, and a cubic grid split into tetrahedra 2 or 3 per cell-centred probe, about 1.85× in time ([artifacts](artifacts_and_fixes.md#single-frame-assessment), [cost](artifacts_and_fixes.md#cost)). Measured in a voxel grid, the trilinear fix traces 7.1× the rays and 8.2× the voxel steps of vanilla and the Kuhn (tetrahedral) fix 2.5× and 2.8×; both seal a closed box to `3 × 10⁻⁴` of the sky or less, and both raise the room errors over vanilla's ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#every-merge-measured)).
- **Scaling holds the bin shift constant.** With ×4 directions and ×4 intervals per cascade in 3D, the parallax of a parent's bin stays constant across cascades, so a reprojected parent lookup needs no widening window; at the equal-error `t0` the shift is 1.7 to 5.2 parent bins, the vanilla merge's parallax, which a merge without reprojection keeps ([sampling and guiding](rc_for_sampling_and_guiding.md#single-frame-assessment), [core theory](core_theory.md#parallax-in-bin-units-derived)). gomezzz's interval doubling with ×4 directions grows the error to 1.5 to 8 parent bins by its top level ([Godot projects](godot_projects.md#connections)). Reading parents toward a fixed depth `D` helps only hits nearer than `2D`; toward a depth estimated from the parents' stored depths it is exact for planes every parent sees but loses lights narrower than half the parent spacing ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#reading-toward-a-depth-derived)).

## Lighting the hits and the composite

- **Direct light stays outside RC.** RC alone does not resolve sun and small-light shadows at practical probe spacings; direct light keeps its own shadows, and RC carries the indirect part ([core theory](core_theory.md#single-frame-assessment)). Emitters smaller than about twice the cascade 0 spacing are lit analytically in EggyStudio, wroughtinator and creikey ([world space](3d_world_space.md#connections)).
- **Hit radiance in the same frame** comes from emission plus direct light at the hit: shadow rays through the same structure, or light injected into the scene structure each frame ([shading the hit](scene_representation_and_tracing.md#shading-the-hit)).
- **Godot's shadow maps arrive too late for PRE_OPAQUE.** The renderer draws shadows in `_pre_opaque_render`, after the PRE_OPAQUE callbacks ([frame order](godot_integration.md#frame-order-and-compositor-hooks)), so a solve that must feed this frame's opaque pass cannot read this frame's shadow maps, even apart from whether a script can reach the shadow atlas at all (derived from the frame order). Same-frame hit lighting therefore needs the RC tracer's own shadow rays or its own light injection (inference).
- **The composite** goes through per-material `IRRADIANCE`, which takes `E/π` and requires every opaque material to be a `ShaderMaterial`; SSAO multiplies on top, so a pure RC setup turns SSAO and SSIL off ([Godot integration](godot_integration.md#getting-gi-into-shading)).
- **Double counting** is avoided by construction: an emitter shaded directly keeps its geometry in the RC scene but not its emission, and the surfaces it lights carry its reflected light, so its bounce still reaches the RC result ([core theory](core_theory.md#splitting-direct-light-derived)).

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
| Interval scaling | ×4 per cascade (`l = 4`), about 5 cascades per scene | equal error; three independent derivations agree ([core theory](core_theory.md#connections)); in flatland, against an exact reference, scales from 2.5 to 4 differ by under 3% once `t0` is tuned ([core theory](core_theory.md#two-criteria-for-interval-scaling-derived)) |
| Cascade 0 directions | 32 | smallest count that tested well; 8 showed obvious artifacts ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)) |
| Cascade 0 interval | 1.6 to 1.7 cascade 0 spacings | equal-error 1.60 and diagonal 1.73 nearly coincide at 32 directions; in flatland the equal-error value is the minimax choice, within 1.42 times every scene's optimal error, while the optimum moves eightfold with light size and rises with rays per bin ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)); in two 3D rooms the equal-error value is vanilla's best at 32 directions, within 13% from 0.84 to 1.41 times it ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#the-cascade-0-interval-axis-alignment-and-overlap-measured)) |
| Direction map | nested equal-area (cylindrical or Clarberg's octahedral), turned against the scene's axes | avoids per-texel weights ([layout](cascade_layout_and_merging.md#single-frame-assessment)); aligned with axis-aligned walls, vanilla's error jumped by half just above the equal-error `t0` in 3D rooms ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#the-cascade-0-interval-axis-alignment-and-overlap-measured)) |
| Merge | trilinear over 8 parents with a binary visibility test: the self test, along the lower probe's own stored ray toward each parent's interval start; depth reprojection at hand-overs whose parent spacing is under twice the smallest light's width; rays toward the parents where a hand-over must seal | [layout](cascade_layout_and_merging.md#single-frame-assessment), [world space](3d_world_space.md#leak-defences-in-world-space); in a 3D voxel lab the parent hit-distance test never acts above the first hand-over, and merges chosen per hand-over cut the leak 4.3-fold and the room errors 17 to 20% at 1.03× the voxel steps ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#merges-by-hand-over-measured)) |
| Schedule | one dispatch per cascade top-down, two live buffers | [layout](cascade_layout_and_merging.md#single-frame-assessment) |
| Final gather | 6×6 octahedral irradiance tiles per probe | Split RC, erhe |
| Formats | RGBA16F with one transmittance channel; R11G11B10F for radiance only | [volumetric](volumetric_and_radiative_transfer.md#single-frame-assessment), [layout](cascade_layout_and_merging.md#formats) |
| Contact detail | a screen-space cascade −1 | Split RC (1.4 ms), PoE2 |

## Where the evidence stops

The measured record of single-frame 3D RC ends at these points. Each states what is established or derived, a hypothesis the evidence points to, and that evidence (inference).

1. **Compute tracer throughput under `RenderingDevice`.** Its compute shaders are ordinary Vulkan compute dispatches, so a GLSL tracer there runs at the compute class's rates, measured at 2.8 to 3.9 G rays/s for compute BVHs and voxel DDA; the one figure taken in Godot is a floor, gomezzz's 0.375 G segments per second from a whole-frame time, and every budget above scales with the rate it assumes, 1 to 3 G rays/s ([performance](performance.md#normalized-throughput-derived)). *Hypothesis:* an HDDA over bitmask bricks for cascades 0 and 1 with mip marching above reaches 2 to 3 G short rays per second on mid-range desktop GPUs, enough for 8 to 12 M rays in 4 ms. *Evidence:* 15 M rays in 5 ms through 4×4×4 bit cubes, tinybvh's 2.8 G primary rays per second, DexRT's mip speedups ([scene representation](scene_representation_and_tracing.md#single-frame-assessment)).
2. **Same-frame radiance at hits.** Godot's frame order gives neither this frame's lit colour nor its shadow maps to a solve that must feed the opaque pass. *Hypothesis:* per-frame light injection into the scene structure (one shadow ray per lit surface cell per light) costs less than shadow rays per hit, because surface cells are far fewer than RC's per-frame rays. *Evidence:* SDFGI's and HDDAGI's injection passes, the hit-shading options ([scene representation](scene_representation_and_tracing.md#shading-the-hit), [Godot integration](godot_integration.md#single-frame-assessment)).
3. **Cascade 0 noise and stability in one frame.** Split RC's `s = A/16` gives one ray per direction cell at 4×4-pixel probes, and screen-placed probes flicker. *Hypothesis:* world-locked probes with `s ≥ 4` (8×8-pixel footprints or four rays per pixel) plus a screen-space cascade −1 give stable contact light without history. *Evidence:* the samples-per-direction table, Kaméus's Min+Max, Gautron's moving-sample flicker ([world space](3d_world_space.md#samples-per-direction-per-frame-derived), [screen-space theses](3d_screen_space_theses.md#connections), [radiance caches](related_radiance_caches.md#single-frame-assessment)).
4. **A leak-free merge at bounded cost.** At `K = 4, l = 4` the bin shift is constant but not small: 1.7 to 5.2 parent bins at the equal-error `t0`, the vanilla merge's own parallax ([sampling and guiding](rc_for_sampling_and_guiding.md#single-frame-assessment)). The parent hit-distance test is free, but in a 3D grid a parent across a wall passes it, so off-surface parents also need a child-to-parent visibility test ([surface probes](3d_surface_probes.md#connections)). The bilinear fix on a cubic grid split into tetrahedra takes 2 or 3 rays per lower ray, 2.75 on average and about 1.85× the time at `l = 4`, against the trilinear fix's 4.4× ([artifacts](artifacts_and_fixes.md#cost)) (derived). *Hypothesis:* the constant bin shift plus a free parent hit-distance test removes most ringing and merge leaks without the 4.4× trilinear fix; the results above narrow it, since the shift stays at the vanilla parallax and the test needs the child-to-parent visibility it was meant to replace. *Evidence:* the bin-shift derivation and the leak defences ([core theory](core_theory.md#parallax-in-bin-units-derived), [world space](3d_world_space.md#leak-defences-in-world-space)). *Measured* in a voxel lab against exact and brute-force references ([merging in 3D](../sources/2026_kurushimee_merging_3d.md)): no merge that reads parents along straight lines seals; the parent hit-distance test cannot act above the first hand-over and changes nothing, so the hypothesis fails as stated; the self test halves the leak and lowers the room errors 13% to 17% at one extra read per parent; depth reprojection with the self test at the first two hand-overs and the sphere fix at the last cut the leak 4.3-fold at 1.03× the voxel steps; the Kuhn fix seals at 2.5× the rays and 2.8× the steps, and every sealing merge raises the room errors. Leaks shrink without rays but close only with rays toward the parents.
5. **Quality against cost.** No 3D study measures quality per millisecond against a reference; Dell'Ova measures cost only and Kaméus quality at three densities ([screen-space theses](3d_screen_space_theses.md#connections)). *Hypothesis:* a path-traced reference of the same scene, computed offline, is enough to rank the families and parameters above. Every other comparison rests on such a reference. In flatland that comparison exists against an exact reference: over 122 settings the error falls about as the inverse square root of the rays along the Pareto front, the rule settings lie within 1.15 times of it except `t0 = 1·Δs0` counted in rays (1.59 times), and the lowest errors need the bilinear fix ([error model](../sources/2026_kurushimee_rc_error_model.md#interval-scale-and-cost-measured)). In 3D a voxel lab measures the leaks, errors and cost counts (rays, voxel steps and texel reads, not milliseconds) of thirteen merges against exact and brute-force references ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#every-merge-measured)).
6. **Deposits without float or 64-bit atomics.** *Hypothesis:* per-probe tracing for cascade 0 with splitting only above it, or sort-based binning, avoids the atomic contention that made Split RC's deposit its largest stage. *Evidence:* 16 ms with atomics against 0.3 ms without in one build, 1.5 ms sort-based binning for 10 M texels ([world space](3d_world_space.md#ray-splitting)).
7. **Moving geometry in the same frame.** *Hypothesis:* a static structure plus a per-frame dynamic one capped by the static hit distance keeps rebuild cost proportional to moving content. *Evidence:* the sparse-build proposal, Wicked Engine's per-frame LBVH, creikey's dynamic clipmap ([scene representation](scene_representation_and_tracing.md#single-frame-assessment)).
8. **A second bounce in one frame.** Two LODs up, a second solve has 1/16 of the first's probes and rays on probes that follow surfaces (1/64 in a filled volume), and the second bounce carries `ρ/(1 + ρ)` of two bounces' light, a third at albedo 0.5; in a closed scene `n` bounces hold `1 − ρ^n` of the indirect light (derived, [world space](3d_world_space.md#single-frame-assessment), [alternatives](light_transport_alternatives.md#multi-bounce)). *Hypothesis:* a coarse second solve two LODs up captures most of the second bounce's light despite its 4× spacing. *Evidence:* Split RC's multi-bounce over frames, the stored-hit-distance route ([world space](3d_world_space.md#single-frame-assessment), [alternatives](light_transport_alternatives.md#single-frame-assessment)).
9. **Small lights and the direct split.** Double counting is excluded by construction for any division of the emitters: an emitter shaded directly keeps its geometry in the RC scene and drops its emission there, while the surfaces it lights carry its reflected light ([core theory](core_theory.md#splitting-direct-light-derived)). A light resolves in RC when it exceeds the ray-end gap at the end of the interval that reaches it: one cascade 0 spacing at the equal-error `t0`, and with `l = 4` a gap of `Δs0·√(t/t0)` at distance `t`, so a fixed threshold of twice the cascade 0 spacing matches the Nyquist bound only up to the end of cascade 0 ([holographic RC](holographic_rc.md#where-it-works)) (derived). Two gaps still err by up to 25%: a light spanning `x` gaps errs by `√(f(1−f))/x`, so 10% takes five, and in 3D a light of width `w` spans one gap out to `w²·s·N0/(4π·t0)`, 6.4 spacings for a light two spacings wide at 32 directions and the equal-error `t0` ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)) (derived). Measured in 3D, the one-ray-per-bin error of a small light falls as about `x^−0.68` in the bins it covers, not `x^−1`, and depth reprojection at a hand-over whose parent spacing exceeds twice a light's width loses most of that light ([merging in 3D](../sources/2026_kurushimee_merging_3d.md#small-lights-derived-and-measured)). *Hypothesis:* lights and emitters below twice the cascade 0 spacing are shaded directly, with their emission out of the RC scene and their geometry kept, and larger emitters stay in it. *Evidence:* the penumbra condition's light-size limit and the analytic small-emitter terms ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported), [world space](3d_world_space.md#connections)).
10. **The hand-off in a hybrid.** *Hypothesis:* stating the screen-to-world hand-off as an RC interval boundary (length in probe sizes, pull-back on the far read) replaces the hand tuning of engine GI. *Evidence:* every engine system's hand-picked lengths ([engine GI](related_engine_gi.md#connections)).
11. **A generated surface atlas as the world part.** *Hypothesis:* probes on the texels of an automatically generated chart atlas (one ray per texel per cascade, hemisphere directions, intervals in texels) give leak-free single-frame world-space GI at a cost set by atlas size, and a screen-space cascade −1 restores the contact shadows lost below the texel. *Evidence:* X3XfRM and yhyu13 on analytic rooms, Blackline's observed 11.4 to 18 ms of GI in Sponza on a 2019 laptop GPU, the seams of on-surface caches ([surface probes](3d_surface_probes.md#a-generated-surface-atlas-blackline-interactive)).

Two theory results bear on the method rather than on a working system (derived). No interval scaling holds both the angular ratio and the gap-to-spacing ratio constant, since per cascade the second changes by half the first's factor ([core theory](core_theory.md#two-criteria-for-interval-scaling-derived)). A lattice that makes the extend identity exact for every line through an `N³` volume stores on the order of `N⁴` values, the count HRC's `O(N⁴)` memory reaches ([core theory](core_theory.md#where-the-merge-is-exact-derived)).
