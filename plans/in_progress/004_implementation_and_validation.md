---
id: 004
title: Implement and validate the radiance cascades GI in Godot
status: in_progress
created: 2026-10-20
updated: 2026-10-20
---

# Implement and validate the radiance cascades GI in Godot

Build the GI that [design/](../../design/README.md) specifies, in Godot 4.7.2 with GDScript and GLSL compute through `RenderingDevice`, and validate it against an in-engine path tracer on the test scenes of [design/evaluation.md](../../design/evaluation.md). Each milestone ends with a measurement, and each names the fallback if the measurement fails. Measured values replace the design's planning figures in `design/` and its checks as they arrive.

## Phases

### M0. Harness and scenes

Done when every test scene loads with UV2 and the GI material, and the metrics script compares two captures.

- [x] Project layout under `src/` as in [godot_host.md](../../design/godot_host.md#code-layout)
- [x] `GI` node and a `CompositorEffect` at PRE_OPAQUE that runs once per frame, with debug labels and GPU timestamps
- [x] Editor script: scene surface area, texel spacing from [checks/budget.py](../../design/checks/budget.py), import texel size, reimport
- [x] Import script that converts materials to the GI `ShaderMaterial` (albedo, emission, fixture flag)
- [x] Built scenes: Cornell box, sealed sunlit rooms (single-plane and thick walls), two rooms at albedo 0.9, pillar hall, small objects
- [ ] Downloaded scenes, each after the owner approves the download: Crytek Sponza, Bistro, Intel Sponza with ivy; kept out of the repository
- [x] Camera poses and static and animated lighting per scene
- [x] Capture of `E/π` and final-image buffers to EXR, and a Python metrics script (relative RMSE, bias, HDR-FLIP via `flip-evaluator`, leak)

**Fallback.** If a scene's import fails to unwrap, it is replaced by another scene that tests the same thing.

### M1. Tracer and reference

Done when the tracer's rates and build times are measured on the RTX 2070, the path tracer agrees with Mitsuba 3 on the Cornell box within its noise, and the acceptance limits are fixed.

- [ ] Vertex, index and UV2 upload; chunked storage buffers above 128 MiB
- [ ] GPU LBVH build: Morton codes, radix sort, hierarchy, box fitting
- [ ] Traversal from tinybvh's `tiny.comp`: segments, any-hit, alpha test, hit triangle and barycentrics, stack guard
- [ ] Measure: build time and ray rate for short segments and shadow rays on Crytek Sponza and Intel Sponza; stack overflows
- [ ] Path tracer for indirect `E/π` per pixel, using Godot's light formulas
- [ ] Cornell box cross-check against Mitsuba 3
- [ ] Fix the acceptance limits from the reference's noise and the lab's floors, before any GI exists, including the HDR-FLIP limit

**Fallback.** Below 0.5 G rays/s, the per-frame ray lines of the budget shrink (fewer moving lights, coarser retrace) and H-PLOC replaces LBVH. If the stack overflows on a scene, the stack grows or moves to private memory.

### M2. Atlas and direct light

Done when the texels' direct irradiance matches the path tracer's direct irradiance at the texel probes within 2%, on every scene.

- [ ] Packing of instance rectangles; atlas use and chart counts per scene
- [ ] Capture pass at 4×4 samples per texel: position, normal, albedo, emission, coverage
- [ ] Probes, frames from the normal, two-sided charts
- [ ] Dilation map and seam pairs
- [ ] Direct light: sun shadow rays, cached visibility for static lights, shadow rays for moving lights, Godot's attenuation and units
- [ ] Sky table from the baked panorama, with the sun's disk removed
- [ ] Debug views of the atlas and the texels' direct light
- [ ] Measure: albedo capture at 4×4 against 16×16 samples; one sun ray against several

**Fallback.** If Godot exposes no rectangle packer to GDScript, a skyline packer is written in GDScript. If one sun ray per texel shows texel-scale aliasing in the indirect light, the sun gets a few rays per texel.

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

**Fallback.** If world probes cost more than the budget allows on large planar charts, those charts take lattice upper cascades (E1). If the sealed rooms leak more than 0.001 of the outside, the first world hand-over takes the Kuhn fix.

### M4. All bounces

Done when the indirect error after the tail meets the acceptance limits on the Cornell box, Crytek Sponza and the sealed rooms, with the passes within 4 ms on Crytek Sponza.

- [ ] Passes with the radiance update and the geometric tail
- [ ] Per-scene pass count
- [ ] Measure: error against passes on every scene, at the scenes' albedos

**Fallback.** For scenes like the two rooms that converge slowly, more passes for that scene, or GMRES from pass 6 if more passes do not fit.

### M5. Composite and near field

Done when the full frame meets the indirect-error limits on every scene and the decision on cascade −1 is recorded.

- [ ] GI material: atlas read at UV2, `IRRADIANCE = vec4(E/π, 1)`; SSAO and SSIL off
- [ ] Dilation and seam stitching after the last pass; seams checked in renders
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
- [ ] Performance pass: occupancy, memory layout of records and probe-bins
- [ ] Skinned meshes, if the budget allows

**Fallback.** If retracing near moving objects exceeds its line, moving objects receive GI but stop casting indirect shadows on static surfaces beyond their own texels.

## Facts / research

- The design and the measurements behind it: [design/README.md](../../design/README.md), [design/experiments.md](../../design/experiments.md); planning figures in [design/budget.md](../../design/budget.md).
- Engine behaviour checked against 4.7.2: [docs/rendering_device.md](../../docs/rendering_device.md), [docs/compositor_and_shading.md](../../docs/compositor_and_shading.md), [docs/lightmap_uv2.md](../../docs/lightmap_uv2.md).
- What the research could not settle: [research/topics/single_frame_3d_rc.md](../../research/topics/single_frame_3d_rc.md#where-the-evidence-stops).
- Engine import behaviour behind the M0 tools: [docs/scene_import.md](../../docs/scene_import.md).

### M0

- **Rebuilding the built scenes.** `python src/reference/build_scenes.py`, then `godot --headless --path . --import` for new models, then `godot --headless --path . --script res://src/editor/texel_size.gd -- <models>`.
- **Texel sizes** at the planning point (8 M records, 16 bins):

  | Scene | Surface | Across | Texel size |
  |---|---|---|---|
  | Cornell box | 1.9 m² | 1.0 m | 0.009 m |
  | Sealed room, thick walls | 205 m² | 12 m | 0.084 m |
  | Sealed room, single-plane walls (both sides counted) | 224 m² | 12 m | 0.087 m |
  | Two rooms | 432.5 m² | 13 m | 0.121 m |
  | Pillar hall | 521.9 m² | 13 m | 0.133 m |
  | Small objects | 1642 m² | 56.6 m | 0.235 m |

- **No T-junctions.** Neighbouring quads must share corners: greedy-merged rectangles in the voxel rooms rasterized with black pinholes along their edges. The builder writes one quad per voxel face and merges equal vertices, which also keeps each plane one connected chart for the unwrap.
- **Godot's sun shadow leaks** thin bright lines along the foot of the single-plane walls, where the wall meets the ground. The leak is in Godot's direct light, so it shows in the final image and not in `E/π`.
- **The Cornell light** reads (18.375, 13.98, 6.75) in the half-float final image: Mitsuba's radiance (18.387, 13.987, 6.754) to half precision.
- **Without GI**, the global `gi_irradiance` is unset and samples black, so `E/π` is zero and the relative figures and the leak come out null. The pillar hall's final images are black too, since its only light is the ceiling panel's, which reaches surfaces only through the GI.
- **HDR-FLIP on a dark reference.** `flip-evaluator` sets its exposure range from the reference's luminance, `log2(xMax / Ymax)` to `log2(xMax / max(Ymedian, ε))`, and calls `exit(-1)` when the start exceeds the stop, which happens when the peak luminance is below float32 ε (`computeExposures` in `src/cpp/FLIP.h`). The metrics script returns null for such a reference instead.
- **Render times without GI**, 1280×720: GPU median 0.15 to 0.43 ms over the six built scenes.
- **Downloads awaiting approval**, none in the repository:

  | Scene | File | Source | Size |
  |---|---|---|---|
  | Crytek Sponza | `Models/Sponza/glTF/`, 71 files | github.com/KhronosGroup/glTF-Sample-Assets | 52.7 MB |
  | Intel Sponza | `main_sponza.zip` | cdrdv2.intel.com/v1/dl/getContent/830833 | 3.99 GB (3.71 GiB) |
  | Intel Sponza ivy | `pkg_b_ivy1.zip` | cdrdv2.intel.com/v1/dl/getContent/726656 | 1.38 GB (1.29 GiB) |
  | Bistro | `Bistro_v5_2.zip` | NVIDIA ORCA, developer.nvidia.com/downloads/bistro | 894 MB |
