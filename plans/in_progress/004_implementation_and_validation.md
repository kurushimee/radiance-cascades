---
id: 004
title: Implement and validate the radiance cascades GI in Godot
status: in_progress
created: 2026-10-20
updated: 2026-10-21
---

# Implement and validate the radiance cascades GI in Godot

Build the GI that [design/](../../design/README.md) specifies, in Godot (NVIDIA's fork, 4.8-dev) with GDScript and GLSL compute through `RenderingDevice`, and validate it against a path-traced reference on the test scenes of [design/evaluation.md](../../design/evaluation.md). Each milestone ends with a measurement, and each names the fallback if the measurement fails. Measured values replace the design's planning figures in `design/` and its checks as they arrive.

## Phases

### M0. Harness and scenes

Done when every test scene loads with UV2 and the GI material, and the metrics script compares two captures.

- [x] Project layout under `src/` as in [godot_host.md](../../design/godot_host.md#code-layout)
- [x] `GI` node and a `CompositorEffect` at PRE_OPAQUE that runs once per frame, with debug labels and GPU timestamps
- [x] Editor script: scene surface area, texel spacing from [checks/budget.py](../../design/checks/budget.py), import texel size, reimport
- [x] Import script that converts materials to the GI `ShaderMaterial` (albedo, emission, alpha, two-sidedness); fixtures are the meshes that cast no shadow
- [x] Built scenes: Cornell box, ~~sealed sunlit rooms (single-plane and thick walls)~~ leak house, two rooms ~~at albedo 0.9~~, pillar hall, small objects (rebuilt in M1)
- [x] Downloaded scenes: Crytek Sponza, Bistro, Intel Sponza with ivy; kept out of the repository
- [x] Camera poses and static and animated lighting per scene
- [x] Capture of `E/π` and final-image buffers to EXR, and a Python metrics script (relative RMSE, bias, HDR-FLIP via `flip-evaluator`, leak)

**Fallback.** If a scene's import fails to unwrap, it is replaced by another scene that tests the same thing.

### M1. Tracer and reference

Done when the tracer's rates and build times are measured on the RTX 2070, the reference agrees with Mitsuba 3 on the Cornell box and renders every scene without visible defects, and the acceptance limits are fixed.

- [x] Vertex, index and UV2 upload; ~~chunked storage buffers above 128 MiB~~ (one buffer each, see [M1 facts](#m1))
- [x] GPU LBVH build: Morton codes, radix sort, hierarchy, box fitting
- [x] Traversal from tinybvh's `tiny.comp`: segments, any-hit, alpha test, hit triangle and barycentrics, stack guard
- [x] Measure: build time and ray rate for short segments and shadow rays on Crytek Sponza and Intel Sponza; stack overflows
- [x] H-PLOC in place of LBVH (the fallback below), measured again on Crytek Sponza and Intel Sponza
- [x] Hardware ray queries in place of the software traversal, on Godot 4.7.2 built with PR #122051, checked against brute force and measured against H-PLOC
- [x] ~~Path tracer for indirect `E/π` per pixel, using Godot's light formulas~~ (NVIDIA's path tracer replaces it, see [M1 facts](#m1))
- [x] Cornell box cross-check against Mitsuba 3, done again on NVIDIA's path tracer
- [x] Displayed frames: AgX at each camera's exposure, MSAA and SMAA, sun shadows that meet thin objects
- [x] The whole project on NVIDIA's fork, with the engine patch: irradiance view, Russian roulette under a 255-bounce cap, camera-only fixtures, omni attenuation, hashed seed
- [x] Godot-side materials and lights: roughness, metalness and normal maps, Bistro's ORM and DirectX normal maps, glass left out, lamps with inverse-square falloff and a radius, no sun disk in the skies, SSR, `E/π` as the indirect specular in place of Godot's specular occlusion, textures with mipmaps
- [x] Scenes reconsidered: the leak house for the sealed rooms, two rooms lit from one side, pillar hall lit from one end, walls 0.7 and floors 0.45, a matte Cornell box
- [x] Reference capture with DLSS Ray Reconstruction, and a frame accumulator for the cross-check
- [x] Every scene's reference rendered and looked at
- [x] Fix the acceptance limits from the reference's error and the lab's floors, before any GI exists, including the HDR-FLIP limit

**Fallback.** Below 0.5 G rays/s, the per-frame ray lines of the budget shrink (fewer moving lights, coarser retrace) and H-PLOC replaces LBVH. ~~If the stack overflows on a scene, the stack grows or moves to private memory.~~ (the hardware traversal keeps no stack, see [M1 facts](#m1))

### M2. Atlas and direct light

Done when the GI's light code, run at each pixel's primary hit with every light's cone sampled, agrees with the path tracer's direct irradiance view on every scene with Godot lights: the squared difference's excess over the reference's noise is within three of its standard errors of zero, and the relative bias is within three standard deviations of the reference's mean, once the pixels lit on one side alone are counted out and their cause is measured. On the scenes without lights the GI's direct light is zero. The path tracer renders only camera pixels, so the probes run the same code and their one sun ray is measured, not gated.

- [x] The engine's direct irradiance view, and hit matching between the raster, the GI's tracer and the path tracer
- [x] Packing of instance rectangles; atlas use per scene
- [x] Capture pass at 4×4 samples per texel: position, normal, albedo, emission, coverage
- [x] Probes, frames from the normal, two-sided charts
- [x] Dilation map
- [x] Direct light: sun shadow rays, cached visibility for static lights, shadow rays for moving lights, Godot's attenuation and units
- [x] Sky table from the baked panorama, with the sun's disk removed
- [x] Debug views of the atlas and the texels' direct light
- [x] Measure: albedo capture at 4×4 against 16×16 samples; one sun ray against several

### M3. Cascades and one bounce

Done when the furnace, sealed-box and determinism checks of [cascades.md](../../design/cascades.md#checks-in-the-engine) pass, the first gathered bounce is within the lab's error of the reference, and the cost per record is measured.

- [ ] Probe insertion, needed bins and hash tables at load
- [ ] Record tracing at load: bent segments to front parents, sphere-fix rays with parent flags, hit distances
- [ ] The pass: top cascade, world cascades, cascade 0, irradiance
- [ ] Checks: furnace, sealed box, bit-identical frames after different histories
- [ ] Measure: cost per record and records per texel on Crytek Sponza and Intel Sponza; update `design/checks/budget.py` and the texel spacing
- [ ] Measure: 16 against 36 bins at equal cost
- [ ] Measure: the sphere fix against Kuhn at the first world hand-over in the sealed sunlit rooms
- [ ] Measure: pre-averaged cascade 1 reads against the exact reads
- [ ] Decide the sun's rays per probe: one ray toward its centre, or a few, from the first bounce's aliasing and M2's measurement of the one ray

**Fallback.** If world probes cost more than the budget allows on large planar charts, those charts take lattice upper cascades (E1). If the sealed rooms leak more than 0.001 of the outside, the first world hand-over takes the Kuhn fix.

### M4. All bounces

Done when the indirect error after the tail meets the acceptance limits on the Cornell box, Crytek Sponza and the sealed rooms, with the passes within 4 ms on Crytek Sponza.

- [ ] Passes with the radiance update and the geometric tail
- [ ] Per-scene pass count
- [ ] Measure: error against passes on every scene, at the scenes' albedos

**Fallback.** For scenes like the two rooms that converge slowly, more passes for that scene, or GMRES from pass 6 if more passes do not fit.

### M5. Composite and near field

Done when the full frame meets the indirect-error limits on every scene and the decision on cascade −1 is recorded.

- [ ] GI material: atlas read at UV2, `IRRADIANCE = RADIANCE = vec4(E/π, 1)`; SSAO and SSIL off
- [ ] Seam pairs at load; dilation and seam stitching after the last pass; seams checked in renders
- [ ] The material's atlas lookup without `instance uniform`, which the path tracer's hit groups cannot compile
- [ ] Measure: error under objects smaller than a texel, on the small-objects scene and Bistro
- [ ] If that error decides acceptance: the cascade −1 candidate of [near_field.md](../../design/near_field.md#the-candidate-for-m5), against the default, within 1 ms

**Fallback.** Without a cascade −1 the 1 ms reserve goes to the passes, for texels about 11% closer.

### M6. Acceptance

Done when every check in the acceptance table of [evaluation.md](../../design/evaluation.md#acceptance) passes with static and animated lighting.

- [ ] Emitters: fixtures for lamps; the size below which an emitter must be a fixture
- [ ] Sky changes: cost of rebaking the panorama
- [ ] The acceptance table on every scene, recorded in this plan

**Fallback.** A scene that fails a limit gets its cause measured and recorded; the limit changes only with a reason the evaluation states.

### M7. Moving objects and performance

Done when moving objects stay within the budget's 0.5 ms on the test scenes and the whole GI meets the timing limits with them.

- [ ] BLAS per moving mesh, TLAS per frame
- [ ] Moving objects' charts and per-frame records
- [ ] Retrace of static records near moving objects
- [ ] Performance pass: occupancy, memory layout of records and probe-bins, the direct pass's ray rate on Bistro's exterior
- [ ] Skinned meshes, if the budget allows

**Fallback.** If retracing near moving objects exceeds its line, moving objects receive GI but stop casting indirect shadows on static surfaces beyond their own texels.

## Facts / research

- The design and the measurements behind it: [design/README.md](../../design/README.md), [design/experiments.md](../../design/experiments.md); planning figures in [design/budget.md](../../design/budget.md).
- Engine behaviour checked against NVIDIA's fork at `135dff3887`: [docs/rendering_device.md](../../docs/rendering_device.md), [docs/compositor_and_shading.md](../../docs/compositor_and_shading.md), [docs/lightmap_uv2.md](../../docs/lightmap_uv2.md), [docs/path_tracer.md](../../docs/path_tracer.md).
- What the research could not settle: [research/topics/single_frame_3d_rc.md](../../research/topics/single_frame_3d_rc.md#where-the-evidence-stops).
- Engine import behaviour behind the M0 tools: [docs/scene_import.md](../../docs/scene_import.md).

### M0

- **Rebuilding the built scenes.** `python src/reference/build_scenes.py`, then `godot --headless --path . --import` for new models, then `godot --headless --path . --script res://src/editor/import_options.gd -- res://assets/scenes/<scene>.tscn ...`. The tool sums the surface over all of a scene's models, gives the textures their materials use Godot's 3D import, and reimports only the files whose options changed.
- **Texel sizes** at the planning point (8 M records, 16 bins):

  | Scene | Surface | Across | Texel size |
  |---|---|---|---|
  | Cornell box | 1.9 m² | 1.0 m | 0.009 m |
  | Leak house (single-plane walls counted on both sides) | 524.3 m² | 22.9 m | 0.133 m |
  | Two rooms | 432.1 m² | 13 m | 0.121 m |
  | Pillar hall | 521.9 m² | 13 m | 0.133 m |
  | Small objects | 1642 m² | 56.6 m | 0.235 m |

- **No T-junctions.** Neighbouring quads must share corners: greedy-merged rectangles in the voxel rooms rasterized with black pinholes along their edges. The builder writes one quad per voxel face and merges equal vertices, which also keeps each plane one connected chart for the unwrap.
- **Godot's sun shadow leaks** thin bright lines along the foot of the single-plane walls, where the wall meets the ground. The leak is in Godot's direct light, so it shows in the final image and not in `E/π`.
- **The Cornell light** reads (18.375, 13.98, 6.75) in the half-float final image: Mitsuba's radiance (18.387, 13.987, 6.754) to half precision.
- **Without GI**, the global `gi_irradiance` is unset and samples black, so `E/π` is zero and the relative figures and the leak come out null. The pillar hall's final images are black too, since its only light is the ceiling panel's, which reaches surfaces only through the GI.
- **HDR-FLIP on a dark reference.** `flip-evaluator` sets its exposure range from the reference's luminance, `log2(xMax / Ymax)` to `log2(xMax / max(Ymedian, ε))`, and calls `exit(-1)` when the start exceeds the stop, which happens when the peak luminance is below float32 ε (`computeExposures` in `src/cpp/FLIP.h`). The metrics script returns null for such a reference instead.
- **Render times without GI**, 1280×720: GPU median 0.15 to 0.43 ms over the six built scenes.
- **Downloaded scenes.** `python src/reference/fetch_scenes.py` fetches Khronos' Crytek Sponza glTF folder (52.7 MB), Intel Sponza (3.99 GB), its ivy (1.38 GB) and Bistro (894 MB), checks each against its pinned size, keeps the models, textures and licences in `assets/downloaded/` and deletes the archives. Then `godot --headless --path . --import`, then the import tool on the four scenes. The first import with UV2 took 13.6 minutes for all four models, about 2 of them for the ivy.
- **Triangles:** Intel Sponza 3.75 M plus 5.07 M of ivy, Bistro exterior 2.83 M, Bistro interior 1.05 M, Crytek Sponza 262 K.
- **Units.** Crytek Sponza's vertices are in centimetres and its glTF node scales them to metres; Intel Sponza and Bistro are in metres. The import's texel size is in the model's own units, so the import tool reports an error when a scene scales a model.
- **Texel sizes** of the downloaded scenes: [budget.md](../../design/budget.md#texel-spacing). Bistro's exterior, 137,297 m² over 259 m, gets 2.149 m.
- **Lights.** Intel Sponza exports its 24 lights with zero intensity, so they import dark. Bistro's own lights are hidden through editable-children overrides, since its FBX lights carry its authoring tool's intensities and a range of 4096 ([docs/scene_import.md](../../docs/scene_import.md#fbx-materials-and-lights)).
- **Bistro's emitters.** Its FBX materials put emission in a texture over a black colour, which Godot adds; the import script turns that into a white colour multiplied by the texture. Besides the ceiling lamps (the fixtures), Bistro's interior keeps three emissive materials (ceiling fans, wall lights, and the hanging lanterns that glow in its own camera's view) and its exterior glows in string lights, street lamps, spotlights and two shop signs: emitters that stay in the solve, mostly small, for M6's fixture-size question.
- **Cameras.** Khronos' Crytek Sponza has none, so the builder adds three, placed by trial renders. Bistro's exterior camera looks mostly at shadowed facades; the builder adds a corner, a terrace and a plaza with sky in view. Bistro's streets lie 0.15 to 0.37 m above the origin.
- **Render times without GI**, 1280×720, GPU median over two or three captures each, some with other camera poses: Crytek Sponza 0.70 to 1.07 ms, Bistro interior 1.04 to 1.27 ms, Bistro exterior 1.45 to 1.72 ms, Intel Sponza 6.19 to 6.27 ms.

### M1

- **Running the tracer's benchmark.** A capture with `--benchmark=<texel spacing>` traces the benchmark's rays from the current camera every frame, and `--check` adds the brute-force check first ([capture-scene skill](../../.claude/skills/capture-scene/SKILL.md)). Brute force over Intel Sponza's 8.8 M triangles would outlast the driver's timeout, so that scene runs without `--check`.
- **One storage buffer each** for nodes, triangles and attributes, so the chunk task is struck. Godot's `storage_buffer_create` checks no size, the RTX 2070's `maxStorageBufferRange` is 4 GiB (67 M nodes), and Godot cannot bind an array of storage buffers in any case ([docs](../../docs/rendering_device.md#limits)).
- **Correctness.** Closest-hit and any-hit queries agree with brute force over every triangle on all 11,134 checked rays of the Cornell box and all 21,261 of Crytek Sponza. Every triangle sits in exactly one leaf, and every box lies inside its parent's. No stack overflowed on the Cornell box, Crytek Sponza or Intel Sponza.
- **Winding.** Godot's front faces wind clockwise. All 74 triangles of the Cornell box agree with their vertex normals; 18 of Crytek Sponza's disagree, and 86,844 of Intel Sponza's (1%). The disagreements only feed a diagnostic count.
- **Build and memory**, LBVH with leaves of up to 4 triangles:

  | Scene | Triangles | Build | Resident | Peak during the build |
  |---|---|---|---|---|
  | Cornell box | 74 | 0.067 ms | | |
  | Crytek Sponza | 262,267 | 1.0 ms | 44.1 MB | 61.9 MB |
  | Intel Sponza | 8,790,466 | 29.8 ms | 1.48 GB | 2.07 GB |

  Resident memory is 168 bytes per triangle: 64 of nodes (N − 1 are allocated, the collapsed ones included), 48 of triangle and 56 of attributes (UV0 and UV2 at each corner, material and instance).
- **Ray rates**, LBVH, G rays/s from the median pass time over 120 frames at 1280×720. The rays start at the camera's surfaces and use the scene's texel spacing (0.46 m on Crytek Sponza, 0.53 m on Intel Sponza), so `t0` is 0.74 m and 0.85 m:

  | Rays | Crytek Sponza | Intel Sponza |
  |---|---|---|
  | Primary, closest hit, back faces culled | 0.16 | 0.14 |
  | Cascade 0, `[0, t0]` | 0.15 | 0.17 |
  | Cascade 1, `[t0, 4 t0]` | 0.13 | 0.17 |
  | Cascade 2, `[4 t0, 16 t0]` | 0.09 | 0.07 |
  | Top, `[16 t0, ∞)` | 0.24 | 0.13 |
  | Sun shadow, any hit | 0.28 | 0.13 |

  Crytek Sponza's figures are the mean of two runs. The same pass drifted by up to 20% between runs at a steady 2055 MHz, so ratios are read from runs made back to back.
- **The tree is the cause.** For comparison, tinybvh (main branch, fetched 2026-10-21) built a binned SAH tree over Crytek Sponza's triangles on the CPU with `Build` and `Optimize(25)`, in 8 and 73 ms. Written into the same node layout, it traced with no mismatches against brute force on 21,261 rays. Interior-node visits per ray come from temporary counters, which missed any-hit rays that hit.

  | | LBVH | tinybvh |
  |---|---|---|
  | SAH cost, unit costs over the root's area | 142.8 | 62.0 |
  | Leaves, and the largest | 91,992 (4) | 131,842 (29) |
  | Visits per primary ray | 122 | 44 |
  | Visits per cascade 0, 1, 2 and top ray | 80, 75, 81, 18 | 33, 23, 29, 5.5 |
  | Speed-up: primary, cascades 0 to 2, top, shadow | | 2.6, 2.8, 3.0, 2.8, 2.5, 1.6 |
  | G rays/s in the same order | | 0.33, 0.36, 0.33, 0.21, 0.49, 0.40 |

- **The traversal code is not the cause.** A private stack traced 0 to 10% slower than the shared one, in two runs of each back to back. Without the alpha test, rays ran about 10% faster. An empty dispatch over the same 921,600 threads measured 0.04 ms, so the timestamps bracket only the pass ([docs](../../docs/rendering_device.md#timestamps)).
- **Decision.** Every rate is below 0.5 G rays/s, so both halves of the fallback apply. H-PLOC replaces LBVH: the tinybvh tree marks about the quality it reaches, since H-PLOC's trees trace within 5 to 17% of the best builder's. The per-frame ray lines shrink to what the measured rates buy ([budget.md](../../design/budget.md#the-frame)). Even the tinybvh tree stays below 0.5 G rays/s on every kind of ray.
- **H-PLOC** replaces the LBVH. The Morton codes and the radix sort stay. One kernel (`cshd_ploc.glsl`) then grows ranges of the sorted order from the leaves up, and once a range holds more than half a subgroup of clusters, its subgroup merges them by PLOC. A second kernel (`cshd_layout.glsl`) writes tinybvh's nodes and turns subtrees of up to 8 triangles into leaves where the SAH cost says so. Every check passes: closest-hit and any-hit queries agree with brute force on 11,134 rays on the Cornell box and 21,261 on Crytek Sponza, every triangle sits in exactly one leaf, every box lies inside its parent's, and no stack overflowed on either Sponza.

  | | LBVH | H-PLOC | tinybvh |
  |---|---|---|---|
  | Crytek Sponza: build | 1.0 ms | 2.5 ms | |
  | SAH cost, unit costs over the root's area | 142.8 | 75.7 | 62.0 |
  | Leaves, and the largest | 91,992 (4) | 145,775 (8) | 131,842 (29) |
  | G rays/s: primary, cascades 0 to 2, top, shadow | 0.16, 0.15, 0.13, 0.09, 0.24, 0.28 | 0.26, 0.38, 0.35, 0.19, 0.50, 0.47 | 0.33, 0.36, 0.33, 0.21, 0.49, 0.40 |
  | Intel Sponza: build | 29.8 ms | 50 ms | |
  | Resident, and peak during the build | 1.48 GB, 2.07 GB | 1.48 GB, 2.57 GB | |
  | G rays/s in the same order | 0.14, 0.17, 0.17, 0.07, 0.13, 0.13 | 0.25, 0.33, 0.37, 0.13, 0.29, 0.28 | |

  The peak comes from holding a 32-byte cluster for every triangle and interior node while the final nodes and triangles are written.
- **Leaf settings.** Leaf limits of 4, 8 and 16 triangles gave SAH costs of 76.4, 75.7 and 75.7, and the largest leaf at 16 held 10 triangles. A node cost of 0.5, 1 and 2 triangle tests gave 77.2, 75.7 and 77.7. The same tree traced up to 25% slower in one run than in the next, so the settings were chosen by SAH cost.
- **Hardware ray queries** replace the software traversal and H-PLOC. Stock Godot 4.7.2 never requests `VK_KHR_ray_query`; upstream PR #122051 (merged for 4.8) requests it and also fixes indexed BLASes in release builds and push constants in ray tracing stages. 4.7.2 with that PR applied builds from source with scons and MSVC in 18 minutes ([README](../../README.md#engine)). One BLAS holds the opaque triangles as an opaque geometry and the alpha-tested ones as a second geometry, whose candidates the shader tests against the material's alpha; primary rays make every triangle a candidate to cull the back of single-sided ones. No ray tracing pipeline exists: `tlas_build` only checks that an instance's hit-table range is nonzero ([docs](../../docs/rendering_device.md#ray-tracing)). Closest-hit and any-hit queries agree with brute force, side included, on all 11,134 checked rays of the Cornell box and 21,261 of Crytek Sponza, and the Cornell box's primary rays hit the raster's 483,196 pixels. Two alternations of hardware and software runs, G rays/s:

  | | Hardware | H-PLOC |
  |---|---|---|
  | Crytek Sponza: primary, cascades 0 to 2, top, shadow | 1.49–1.50, 2.47–2.49, 2.59–2.61, 1.41–1.43, 3.93–3.96, 2.38–2.40 | 0.23–0.26, 0.29–0.34, 0.28–0.35, 0.17–0.18, 0.36–0.50, 0.36–0.48 |
  | Intel Sponza, in the same order | 1.21–1.22, 1.88–1.89, 2.49–2.52, 0.64–0.78, 1.75–1.76, 1.47 | 0.21–0.25, 0.28–0.33, 0.29–0.37, 0.11–0.13, 0.23–0.29, 0.22–0.28 |
  | Build, Crytek Sponza and Intel Sponza | 2.7–3.3 ms, 54–86 ms | 1.6–1.7 ms, 44–70 ms |
  | Resident, and peak during the build, Intel Sponza | 2.04 GB, 2.04 GB | 1.48 GB, 2.57 GB |

  Every rate is above 0.5 G rays/s, so the fallback no longer applies, and the per-frame ray lines of the budget grow to what these rates buy ([budget.md](../../design/budget.md#the-frame)). The structures take 128 bytes per triangle on both Sponzas, measured as the change in the driver's allocated bytes, since Godot keeps each structure's build scratch and offers no compaction.
- **The sky without its sun.** The path tracer samples the sky on every ray that misses and the sun light as well, so a disk in the sky counts the sun twice. Procedural skies leave it out with the sun's `sky_mode` set to light only. For Bistro's exterior, `build_scenes.py` paints the disk out of a copy of the HDR panorama, filling it from the pixels around it, and gives the sun light the disk's irradiance above its surroundings and its direction, about 29° up.
- **The Arcade camera stood 1.6 m from the arcade's outer wall**, with the column line on its right. Half the frame was that wall, at a median `E/π` of 1/30 of the image mean, so its noise came from the bright far end. It now stands at (−11, 1.7, −4.4) and looks at (10, 2, 0), down the arcade and through its arches onto the atrium's floor. Its noise at 64 samples fell from 3.30 to 1.65 unguided and to 1.05 guided.
- **The displayed frame.** Every capture, of the GI or of a reference, saves each camera's `final.png`: the frame as the game shows it, with AgX at the camera's exposure, 4× MSAA with SMAA, and debanding. In a reference's, the GI materials read its `E/π` per screen pixel (`GI.View.REFERENCE`). The linear EXRs that the metrics read are rendered with the Linear tonemapper at exposure 1 and without anti-aliasing or debanding, so each pixel still holds the one surface that the path tracer's primary ray hit. Under MSAA, every surface in a silhouette pixel reads the irradiance of the surface at the pixel's centre; at the Cornell box's box edges no fringe shows, so the reference image reads no neighbourhood. The views at an irradiance of 0 and 1 are captured with an opaque background, so the composed image has the sky that a GI capture's `final.exr` has; with a transparent background the sky was black, which would have shifted HDR-FLIP's exposure range against a GI capture.
- **Exposure.** The test views span about 13 stops of incident light (`E/π` plus direct light over albedo): the sunlit lab scenes meter at a median of 0.8 to 0.9, Crytek Sponza's Arcade at 0.0001. Godot's camera exposure multiplier leaves a material's `IRRADIANCE` unscaled ([docs](../../docs/compositor_and_shading.md#irradiance)), so a camera that needs its own exposure gets its own Environment, which shares the scene's sky and differs only in `tonemap_exposure`. Starting from 0.45 over the median incident light and set by eye, the exposures run from 0.45 in the two rooms to 4,000 in the Arcade.
- **Sun shadows.** With Godot's defaults, a bias of 0.1 and a normal bias of 2.0 on a 4,096 map over 100 m, the small objects' shadows started well away from posts 3 to 6 cm wide and broke into stairs. A bias of 0.03, a normal bias of 0.5, an 8,192 map over 40 m (100 m in Bistro's streets), the High soft filter and a sun 0.5° across give shadows that meet the posts, with penumbrae. A normal bias of 0, or a shadow blur of 0, covers lit surfaces with acne. In the unlit leak house's room with single-plane walls, the shadow map lets a line of sunlight one pixel wide in along the walls' base, 752 pixels at up to 0.40; the path tracer's own light there stays below 1e-5 of the outside, and the GI's frame carries the same line.
- **Alpha-tested edges.** Godot's alpha-to-coverage (`ALPHA_ANTIALIASING_EDGE`) feathers alpha and discards in the depth prepass at its own threshold ([docs](../../docs/compositor_and_shading.md#hdr-readback)), so the raster's alpha mask would part from the tracer's alpha test at `alpha_scissor`. It stays off, and SMAA smooths the leaf edges.
- **Sky ground.** The ProceduralSkyMaterial's default ground, dark brown, showed past the lab's slabs and floor as a black band under AgX, so the procedural skies have a grey ground of 0.35.
- **NVIDIA's fork.** The project runs on NVIDIA-RTX/godot at `135dff3887` (4.8-dev) with `engine/nvidia_path_tracer.patch`, built as the [README](../../README.md#engine) says. It carries PR #122051's fixes, so the GI code runs on it unchanged. The path tracer's behaviour and what the patch changes are in [docs/path_tracer.md](../../docs/path_tracer.md). The compute path tracer, its path guide and `SkyPanorama` are deleted.
- **The fork's own limits.** It clamped `pathtracing_max_bounces` to 8 and ended paths after two diffuse bounces, which left the Cornell box's irradiance about 1% low, most of it in red. Its linear seed gave pixel `(x, y)` at frame `f + 27` the seeds of `(x − 832, y + 412)` at frame `f`. The patch lifts the cap to 255 under Russian roulette from the fourth bounce and hashes the frame before it meets the pixel.
- **Specular energy.** At Godot's default specular of 0.5 and roughness 1, the path tracer's single-scattering GGX lobe left the Cornell box's irradiance 3.7% below a Lambertian path tracer's (red 5.4%, green 2.3%, blue 1.1%); at specular 0 it matched to 0.04%. The Cornell box is matte, through a `specular` in its glTF materials' extras that the import script reads, since Godot imports no glTF specular. The other scenes keep Godot's default for now.
- **Cross-check on the fork.** 65,536 accumulated frames of one sample, in 199 s (about 3 ms a frame), give a relative noise of 0.0386; Mitsuba at 8,192 samples gives 0.0193. Against Mitsuba the bias was −0.00046, 8.8 standard deviations, and the RMSE the noise's (0.0403 against 0.0403). Against the compute path tracer it was −0.00044 (6.7 standard deviations), and that tracer against Mitsuba −0.00003 (−0.6). The fork's frames are half float, and storing a float rounds toward zero, about −0.034% for one rounding. With the minimum ray distance of 0, 65,536 frames in 481 s give a bias of +0.00021 against Mitsuba, 4.0 standard deviations, with the RMSE still the noise's: the 1 mm gap had lost about 0.07% of the light through the box's corners, and the rest is 1/140 of the bias limit.
- **Ray Reconstruction is the reference.** Its output is judged by looking at it, not against a measured truth. In the Cornell box's irradiance view, one sample per pixel per frame smears it visibly: the red wall's bleed spreads and the tall block's indirect shadow on the left wall is lost. At 16 samples both hold, and at 255 the image matches 65,536 accumulated frames. It settles within 64 frames of a start and within 128 after a change of view, so the capture leaves DLSS for a few frames before each view, which gives the view a new Ray Reconstruction instance.
- **Stale Ray Reconstruction instances.** The fork handed a deleted DLSS context's Streamline viewport handle to the next context without freeing the Ray Reconstruction instance on it. The unlit leak house's Back view then carried a soft dark patch on the ground, 15% below the raw path tracer's mean of 0.334 over it, in the normal view after the irradiance view; it grew from the eighth frame, and resetting the history did not clear it. A fresh handle for each context removed it, and the patch frees a handle's instances before reuse, a few frames after its context is gone, since freeing them in the context's destructor hung the process. A patch that took the camera jitter out of the irradiance view made it worse with every frame, so it was dropped.
- **Seams of single-plane walls.** The fork skipped hits closer than 1 mm on top of its origin offset, so rays that left a wall within a millimetre of the ceiling passed through it. The unlit leak house's single-plane room showed bright lines along every seam, up to 0.028 against an outside `E/π` of 0.16, in both views; with a minimum distance of 0 it is black, below 1e-5 of the outside. The thick room was black throughout, since a ray that skipped its inner face still met the wall's outer one.
- **Fireflies on Crytek Sponza.** In 65,536 accumulated frames of the Atrium's irradiance view, 0.01% of the pixels carry 98% of the variance, from single samples up to 8 million times the mean; without them the noise is 8 times lower. Two of its metals have roughness maps that reach 0, and the path tracer samples the sun with no roughness floor and no MIS. At 255 samples a frame takes 5 to 10 s there.
- **`flip-limit`** compares the perturbed frames with the reference's own composed frame: a denoised reference has no mean over even frames to stand in for a second noisy sample.
- **A view of direct light alone.** The fork had none, so the patch adds one beside the irradiance view, for M2's check ([docs](../../docs/path_tracer.md#the-engine-patch)).
- **Godot's specular occlusion.** Godot scaled the indirect specular by `min(8 · luminance(IRRADIANCE), 1)`, so in Bistro's shaded Corner a hedge kept 70% of the open sky's reflection and showed grey-blue, its lamp post light grey and its cobbles flat, where the path tracer shows them green, dark and textured. The frame was also not affine in `E/π`: Godot's frame with the reference's `E/π` was 65% above the composed frame in the median pixel of the Corner, 8 to 36% in Bistro's other views, 14 to 17% in Crytek Sponza's and 0.3 to 1.5% in the leak house's, and equal indoors. The GI materials now write `E/π` as `RADIANCE` too, with the occlusion off ([lighting.md](../../design/lighting.md#sky)); the frame then agrees with the composed one within 0.06% in 98% of the pixels of every view except the two Sponzas', where screen-space reflections, the one term left that reads other pixels, move 1 to 18% of the pixels by more than 1% and the frame's mean by at most 0.2%.
- **Textures without mipmaps.** Every downloaded texture had imported lossless and without mipmaps, since only the editor's first 3D draw switches a texture to VRAM compression with mipmaps ([docs](../../docs/scene_import.md#textures-used-in-3d)). On Intel Sponza, Ray Reconstruction then failed with `sl::eWarnOutOfVRAM`, also without the GI node. The import tool now sets the 3D import on the 144 textures that the materials of Crytek Sponza, Intel Sponza and its ivy use; Bistro's are DDS.
- **Acceptance limits.** The reference counts as exact, so the lab's indirect-error limits stand, with both Sponzas and Bistro under the tighter ones of open scenes and single rooms. The HDR-FLIP limits per camera run from 0.023 on the leak house's sunlit facade to 0.157 in the two rooms and the pillar hall ([evaluation.md](../../design/evaluation.md#acceptance)). On the downloaded scenes the image floor is 1.7 to 3.6 times the limit, so Godot's ready-made rendering, not the GI, decides how close their final images come to the path tracer's. Blurring both images by 4 pixels lowers the floor by only 2 to 20%, so it is not anti-aliasing or texture filtering. Denoised references had saved `irradiance.exr` without alpha, since an opaque viewport reads back RGB; the capture now adds the alpha that marks the surfaces, and the rendered references got it from their `position.exr`.
- **The sky behind the path tracer.** Camera rays that miss read the sky's radiance map, 256² by default ([docs](../../docs/path_tracer.md#lights)), which blurred the buildings of Bistro's panorama behind the plaza into horizontal smears. Bistro's sky now has a 2048² map.

### M2

- **The direct check.** The GI's light code ran at each pixel's primary hit with every light's cone sampled by 1,024 directions, against the path tracer's direct view averaged over 1,024 raw frames. The excess is the squared difference beyond the reference's noise, as a share of the noise's: the square of the RMSE's ratio to the noise's RMSE, less 1. Its standard error comes from the spread of the pixels' own excesses. The bias is in standard deviations of the reference's mean. The Cornell box, the pillar hall and the two rooms have no Godot lights, and the GI's direct light there is zero.

  | Scene | Camera | Excess | Bias | Flips |
  |---|---|---|---|---|
  | Leak house | Back, Facade, InsidePlane, InsideThick | +0.1 ± 0.4%, −0.3 ± 0.3%, −0.3 ± 0.3%, −0.3 ± 0.3% | −0.09σ, +0.01σ, +2.24σ, +2.20σ | 0 |
  | Leak house without lamps | Back, Facade | +1.0 ± 2.5%, −22 ± 15% | −1.07σ, +2.94σ | 0 |
  | | InsidePlane, InsideThick | zero on both sides | | |
  | Small objects | Low, Overview | +0.0 ± 4.1%, +3.8 ± 3.3% | +3.36σ, +1.16σ | 0 |
  | Crytek Sponza | Arcade, Atrium, Gallery | −33 ± 33%, +3.2 ± 5.9%, −2.1 ± 8.7% | −0.26σ, +0.57σ, −0.96σ | 0 |
  | Intel Sponza | 001, 002, 004, 005 | +9.1 ± 7.0%, +0.7 ± 8.0%, +14 ± 14%, +10.5 ± 5.0% | −0.63σ, −0.41σ, −1.28σ, +0.15σ | 0, 0, 1, 0 |
  | | 006 | +147 ± 147%, +0.0 ± 3.0% without its flip | +1.50σ, +2.71σ without | 1 |
  | | 003 | zero on both sides | | |
  | Bistro interior | Camera | −0.0 ± 0.4% | +0.19σ | 1 |
  | Bistro exterior | Camera | +1.8 ± 1.6% | −1.94σ | 0 |
  | | Corner | +9.3 ± 4.9%, +5.5 ± 3.1% without flips | +0.75σ, +0.55σ without | 2 |
  | | Plaza | +87 ± 24%, +13.6 ± 5.3% without flips | −1.52σ, −1.01σ without | 13 |
  | | Terrace | +130 ± 55%, −0.4 ± 1.8% without flips | +5.12σ, +1.96σ without | 9 |

  Without the flips, every excess is within 2.6 standard errors of zero, the most on Bistro's Plaza and Intel's 005, and every bias is within three standard deviations but small objects' Low, where the GI's quadrature decides it (below). The ratio of the RMSEs alone hides how well the noise itself is known: the excess's standard error runs from 0.3% of the noise on the leak house to 33% on Crytek's Arcade.
- **Hit matching.** Both sides must see the raster's surface. A GI pixel counts when its primary ray's hit distance `t` is within `t/4096` of the raster's. A reference pixel counts when its depth, scaled by the median ratio of the two views' depths, is within 1/1024 of the raster's, and its normal meets the raster's at a cosine of at least 0.99999. At 0.99 the stacked cloth layers of Bistro's awnings passed as one surface: Terrace's RMSE was 0.0211 against the noise's 0.0118, with a bias of 8.4σ. At 0.99999 the awnings differ by an RMS of 0.0016 against the noise's 0.0017. The path tracer's half-float normal view keeps one surface within a cosine of 0.999999 of the raster's. The raster draws its views at full detail, as the tracers hold the meshes: at Godot's default level-of-detail threshold, 12% of Intel Sponza's pixels had normals more than 0.26° from the path tracer's ([docs](../../docs/path_tracer.md#frames)), and each of its cameras compared about 800,000 pixels instead of about 920,000.
- **Quadrature.** A grid of rings and sectors over the cone errs along a whole sector edge where a shadow's edge crosses the cone's centre: Crytek's Arcade gave an RMSE of 0.151 at 8×8 and 0.089 at 16×16 against the noise's 0.083. A Fibonacci lattice spreads that error, which falls at an edge about as `N^(−3/4)`. The check uses 1,024 directions and the static lamps' cache the same lattice at 64. At 2,048 directions the excess fell by 1 to 3% of the noise on most sunlit cameras: Bistro's Camera from +1.8% to +0.2%, Corner's from +5.5% to +3.1% and Plaza's from +13.6% to +10.7% without flips, and Intel's 001 from +9.1% to +6.8%. Small objects' Low bias fell from +3.36σ to +0.75σ. The lampless leak house's Facade went from +2.94σ to −6.94σ, at relative biases of 7·10⁻⁷ and −1.7·10⁻⁶: where the reference's noise is that low, the GI's own quadrature decides a bias of a few σ.
- **Flips.** A pixel lit on one side and below 5% of it on the other, where the lit side is above a fifth of the frame's mean, is counted apart. Intel Sponza had 23 to 64 per camera, dim tails of sun streaks through the ivy, 0.008 to 0.026 on the GI side and 0 in the reference. The model brings 24 lights of zero intensity, and the path tracer samples every visible light, so the sun got one light sample in 25, and a pixel that sees a few percent of its disk often got none in 1,024 frames ([docs](../../docs/path_tracer.md#lights)). The reference's relative noise on the fully sunlit floor, 0.153 or √(24/1,024), measured that share. With the lights hidden, Intel's 004 and 006 keep 1 flip each. What remains on Intel and Bistro are single pixels of three kinds:
  - **The shadow terminator.** Where a mesh's interpolated normal turns far from its triangle's face, a ray toward the light grazes the face or leaves below its plane, and whether it clears its own mesh is decided within a millimetre. Both sides start it at Wächter and Binder's offset along the interpolated normal, so rounding decides. At Intel 006's flip, on a carved corbel, the normal is 41° from the face and the sun 9.5° above the face's plane: the GI's ray met its own triangle from behind at 10⁻⁷ m, which left the pixel dark against the reference's 0.76, while a start 1 mm out or an offset along the face lit it fully. At 001's largest difference, on a column's base, 0.305 against 0.401 and three quarters of that camera's excess, the sun is 6° below the face: a start 1 mm out lights the pixel fully, and an offset along the face leaves it dark. Bistro's exterior has such rays too, grazing the surfaces they leave.
  - **Leaves** on Bistro that the reference's depth view cannot tell from parallel ones behind them.
  - **Dim penumbrae of a dark frame.** Intel's 004 looks almost entirely into shade, with a mean of 0.001, so a tail of 0.001 on the GI side against 0 in the reference counts.

  Corner's 2, Terrace's 9, 6 of Plaza's 13 and the Bistro interior's 1 are lit on the GI side.
- **Intel Sponza's reference**, rendered again with the model's lights hidden, has a mean `E/π` 0.3 to 1.8% higher per camera than it had with one sun sample in 25. Its HDR-FLIP limits moved by at most 0.001, and its floors fell by 0.010 to 0.021 ([evaluation.md](../../design/evaluation.md#acceptance)).
- **Views at full precision.** The GI's light code reaches the capture through Godot's half-float frame as a half and its remainder, split with a mantissa mask ([docs](../../docs/compositor_and_shading.md#hdr-readback)), and so do the raster's distances and normals. Half-float normals alone match the same pixels within a few dozen per camera, but they turned the GI's direct light by an RMS of 0.03% per pixel on Intel's 001 and 005, up to 2% where the light grazes, and moved 005's bias from +0.15σ to +0.68σ. The path tracer's first two frames after it is enabled are blank ([docs](../../docs/path_tracer.md#frames)).
- **The path tracer's normals** turn wrongly under a non-uniform scale. Among the test scenes, only Bistro's four string-light cables and one building of Bistro's interior are scaled that way ([docs](../../docs/path_tracer.md#materials)).
- **`instance uniform` in hit groups** does not compile ([docs](../../docs/path_tracer.md#materials)), so the debug views trace their own primary rays, and M5 gives the material its atlas rectangle another way.
- **Non-uniform indexing** of sampled images is on for Vulkan 1.2 devices ([docs](../../docs/rendering_device.md#texture-arrays)). The tracer keeps its subgroup loop until its cost matters.
- **Lights.** No test scene has a spot light, a light without shadows that gives light, or physical light units, so those are errors. A model's light that gives no light at load, because the scene's own lights replace it, is left out ([lighting.md](../../design/lighting.md#direct-light)). The path tracer still samples such a light, so the scenes hide them (Flips, above).
- **Packing.** Godot binds `Geometry2D.make_atlas` for scripts, so no packer of the project's own is needed.
- **The atlas** at 4×4 samples, with the build's wall-clock time on the render thread. The first capture after a shader import took 157 ms on Crytek Sponza, the next 23.4 ms:

  | Scene | Atlas | Texel | Rectangles | Covered texels | Use | Probes | Own | Groups | Moved | Memory | Build |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | Cornell box | 220×160 | 0.009 m | 4 | 27,289 | 0.775 | 24,992 | 24,992 | 0 | 0 | 2.1 MB | 8.4 ms |
  | Two rooms | 240×188 | 0.121 m | 4 | 33,972 | 0.753 | 31,029 | 30,816 | 213 | 81 | 2.7 MB | 9.8 ms |
  | Leak house | 244×264 | 0.133 m | 7 | 35,335 | 0.549 | 31,683 | 31,275 | 408 | 204 | 2.8 MB | 10.7 ms |
  | Pillar hall | 340×284 | 0.133 m | 3 | 55,204 | 0.572 | 34,764 | 18,804 | 15,960 | 6,384 | 3.2 MB | 12.9 ms |
  | Small objects | 448×268 | 0.235 m | 2 | 57,644 | 0.480 | 33,918 | 29,584 | 4,334 | 862 | 3.2 MB | 12.8 ms |
  | Crytek Sponza | 568×1136 | 0.462 m | 2 | 131,653 | 0.204 | 48,186 | 35,310 | 12,876 | 10,019 | 6.4 MB | 23.4 ms |
  | Intel Sponza | 2036×1168 | 0.529 m | 119 | 452,868 | 0.190 | 58,017 | 25,393 | 32,624 | 15,438 | 14.2 MB | 267 ms |
  | Bistro interior | 1024×1260 | 0.219 m | 955 | 264,159 | 0.205 | 61,011 | 19,849 | 41,162 | 23,103 | 10.1 MB | 53.4 ms |
  | Bistro exterior | 2048×3160 | 2.146 m | 1,264 | 1,253,522 | 0.194 | 84,196 | 13,790 | 70,406 | 35,135 | 32.7 MB | 199 ms |

  The probes run from 24,992 to 84,196 against the budget's 30,000 ([budget.md](../../design/budget.md#texel-spacing)), and groups of charts smaller than a texel make the difference. A fifth to two fifths of the downloaded scenes' probes move out of a back face, most of them groups. At 16×16 the build takes 27 ms on small objects, 99 ms on Crytek Sponza, 1,242 ms on Intel Sponza, 247 ms on Bistro's interior and 781 ms on its exterior. The probes pass takes 0.04 to 5.1 ms of GPU time.
- **Albedo.** Read at the footprint of a sample, the textured scenes' albedo came out 3.1% darker than read at full resolution on Crytek Sponza, 1.7% on Intel Sponza and 1.3 and 1.4% on Bistro's interior and exterior, and 0.2 to 2.0% darker at 4×4 than at 16×16: Godot averages mipmaps in sRGB terms ([docs](../../docs/scene_import.md#textures-used-in-3d)). The capture now reads full resolution, as the path tracer does. On texels that are probes of their own in both captures, 4×4 against 16×16:

  | Scene | Texels | RMSE | Bias |
  |---|---|---|---|
  | Crytek Sponza | 48,607 | 10.5% | 0.00% |
  | Intel Sponza | 41,096 | 9.2% | −0.20% |
  | Bistro interior | 34,762 | 4.5% | +0.09% |
  | Bistro exterior | 26,847 | 5.2% | −0.10% |

  Small objects' materials are untextured, and both captures agree exactly. The alpha test reads full resolution too, so Bistro's exterior covers 9% more texels than at the footprint and Crytek Sponza 3% more; Intel Sponza's ivy is opaque and keeps its count.
- **One sun ray toward the centre against the sampled cone**, over the atlas's texels:

  | Scene | RMSE | Bias |
  |---|---|---|
  | Leak house | 0.0152 | +0.0002 |
  | Leak house without lamps | 0.0179 | +0.0003 |
  | Small objects | 0.0145 | −0.0001 |
  | Crytek Sponza | 0.083 | −0.0025 |
  | Intel Sponza | 0.124 | +0.0020 |
  | Bistro exterior | 0.557 | +0.0057 |

  Bistro's interior has no sun, and its lamps are cached. One ray is unbiased within 0.6%, and apart texel by texel by up to 56% on Bistro's exterior, whose texels are 2.1 m across. M3 decides the rays from the first bounce's aliasing.
- **Times.** With the sun alone, the direct pass takes 0.017 ms on the leak house and small objects, 0.045 ms on Crytek Sponza, 0.068 ms on Intel Sponza and 0.30 to 0.33 ms on Bistro's exterior, which runs at a quarter of the Sponzas' ray rate for a cause not yet measured. Bistro's interior, with cached lamps only, takes 0.02 ms. The lamps' visibility at load takes 1.8 ms on the leak house and 9.0 ms on Bistro's interior, and the sky table 0.02 to 0.047 ms.
- **Determinism.** Two captures of Crytek Sponza write byte-identical atlas images, probe direct light and texel views.
- **Sky.** The table's `E/π` on surfaces facing the six axes is within 1.1·10⁻⁴ of the panorama's cosine integral on the leak house and small objects, 128×64 bins, 5.9·10⁻⁴ on the Sponzas, 64×32 bins, and 8.1·10⁻⁴ on Bistro's exterior. A bake in `_ready` returned black, since Godot fills the radiance map while it draws the first frame ([docs](../../docs/compositor_and_shading.md#sky)).
- **Settings before the GI's `_ready`.** The main scene enters the tree before an autoload's `_ready`, so a `node_added` handler connected there misses it. The capture sets `--atlas-samples` on the GI from its own `_ready`, which runs before the GI's.
