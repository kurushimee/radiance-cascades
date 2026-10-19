# gomezzz/godot-3d-radiance-cascades

| | |
|---|---|
| Author | gomezzz (GitHub account) |
| Date | 2026-09-13 (last commit, committer date 2026-09-13T00:47:03Z) |
| Kind | repository (Godot 4.7) |
| Link | https://github.com/gomezzz/godot-3d-radiance-cascades |

A world-space 3D radiance cascades (RC) solver for Godot 4.7 Forward+. It has five cascade levels on a 24 x 16 x 24 base probe grid, and every level is a Vulkan compute pass dispatched through the main RenderingDevice. Static scene geometry enters as a CPU-built triangle BVH snapshot, and up to 64 moving analytic box or sphere primitives are packed every frame. Spatial shaders sample the resulting irradiance atlas. The addon lives in `addons/radiance_cascades/` and is meant to be copied into other projects; the rest of the repository holds the demos, tests and tools.

## Contents

- [Files](#files)
- [Godot integration](#godot-integration)
- [Scene representation](#scene-representation)
  - [1. Static triangles (CPU BVH snapshot)](#1-static-triangles-cpu-bvh-snapshot)
  - [2. Analytic primitives (per-frame packed)](#2-analytic-primitives-per-frame-packed)
  - [Volume](#volume)
- [Passes](#passes)
- [RC parameters and math](#rc-parameters-and-math)
  - [Constants and layout](#constants-and-layout)
  - [Per-level layout (base spacing 0.5)](#per-level-layout-base-spacing-05)
  - [Direction mapping](#direction-mapping)
  - [Merge (cascade pass), per probe p, per stored direction d at level L](#merge-cascade-pass-per-probe-p-per-stored-direction-d-at-level-l)
  - [Interval tracing (`trace_interval`)](#interval-tracing-trace_interval)
  - [Resolve (six-lobe irradiance)](#resolve-six-lobe-irradiance)
  - [Surface and hit lookup (`history_irradiance`, `sample_lighting`)](#surface-and-hit-lookup-history_irradiance-sample_lighting)
  - [Other numeric facts](#other-numeric-facts)
- [Issues and notes](#issues-and-notes)
  - [Stated limitations (README, implementation.md, TODO.md)](#stated-limitations-readme-implementationmd-todomd)
  - [Documentation discrepancies (text versus code)](#documentation-discrepancies-text-versus-code)
  - [Code-level notes](#code-level-notes)
  - [Performance and validation records (docs and README)](#performance-and-validation-records-docs-and-readme)

## Files

Addon files, all under `addons/radiance_cascades/`:

| File | Size (bytes) | Role |
|---|---|---|
| `radiance_cascades.gd` | 7142 | `class_name RadianceCascades` (Node). Exports, lifecycle, material install and restore, per-frame primitive packing, render-thread scheduling, `rebuild_geometry()`, `set_view()`. |
| `rc_gpu.gd` | 9932 | `class_name RCGPU` (RefCounted). Constants, RenderingDevice resources, runtime shader compile, dispatch, debug atlas, teardown. |
| `rc_mesh_bvh.gd` | 6407 | `class_name RCMeshBVH` (RefCounted). CPU triangle extraction from MeshInstance3D and BVH build. |
| `rc_primitive.gd` | 1504 | `class_name RCPrimitive` (`@tool`, MeshInstance3D). Analytic BoxMesh or SphereMesh with `albedo`, `radiance`, `point_source`, `point_range`. Packs 112 bytes. |
| `rc_pbr_material.gd` | 2053 | `class_name RCPBRMaterial` (RefCounted). Copies supported BaseMaterial3D properties onto `pbr_surface.gdshader`. |
| `shaders/common.glslinc` | 7009 | Shared SSBO and push-constant declarations, analytic intersection, point-source term, interval tracer, history lookup. Contains the `// MESH` placeholder. |
| `shaders/mesh.glslinc` | 2207 | BVH node and triangle structs, bindings 4 and 5, `box_hit`, `triangle_hit`, `trace_mesh`. |
| `shaders/cascade.glslinc` | 3475 | Cascade merge kernel. One dispatch per level. |
| `shaders/resolve.glslinc` | 1192 | Six-lobe irradiance resolve from level 0, with temporal blend. |
| `shaders/debug.glslinc` | 1405 | Diagnostic atlas (256 x 640) read from the production level buffers. Self-contained, does not include `common.glslinc`. |
| `shaders/validate_mesh.glslinc` | 531 | Ray-query kernel for CPU-versus-GPU BVH checks. Not used by the production path. |
| `shaders/surface.gdshader` | 1809 | `render_mode unshaded` surface. Default material for primitives and mesh surfaces. |
| `shaders/pbr_surface.gdshader` | 7592 | Spatial PBR surface. RC diffuse enters as EMISSION. The `light()` function adds only GGX specular. Also contains metro-specific paint and reflection-clip code. |

Repository root (downloaded, text):

- `README.md` (43555 bytes). Main user documentation, test counts, performance records, limitations, licence and credits. Licence is MIT for code; some assets keep their own licences.
- `TODO.md` (2048 bytes). Work tracker with open items listed under Next and Someday.
- `docs/implementation.md` (16675 bytes). Cascade layout, memory, BVH format, merge and resolve description, approximations, extension points.
- `docs/validation.md` (26011 bytes). Dated verification and performance records, test counts, known warnings.

Coverage: the addon files, README, docs, TODO, `project.godot`, `classic_example.gd` and `reactor_hall.gd` were read in full. `test_mesh.gd`, `metro_station.gd`'s RC setup and the eight metro shaders were read as well. The other scripts and test files were checked by function names and RC API grep; their roles above come from those checks and from the docs.
- `tests/test_mesh.gd` checks GPU triangle traversal against Godot's CPU triangle intersection on four indexed cylinders and a non-indexed surface. It asserts more than 100 triangles and 12 BVH nodes, shader compilation, emission reaching the cascade radiance (max above 0.1), reference rays hitting geometry, triangle extraction keeping every face, a BVH that survives glTF export and import, 72,012 triangles in the full hall, and material restoration when the controller is removed (`:54-234`). It renders nothing and measures no lighting error.
- The metro shaders (display, ember, flame, focus, postfx, reflection, steam, steam_volume) are effects only; none references RC.

## Godot integration

- Engine and renderer: Godot 4.7, Forward+ (`config/features=PackedStringArray("4.7", "Forward Plus")`). The README states Compatibility and WebGL cannot run the solver, and that headless rendering cannot run it. Only Windows with an NVIDIA RTX 4060 Ti was tested.
- Entry point: `RadianceCascades` is a Node added to the scene. Its `_ready()` collects geometry, builds the CPU BVH on the main thread, installs materials, and schedules `RenderingServer.call_on_render_thread(_initialize_gpu)`.
- Render thread: all RenderingDevice work runs inside `call_on_render_thread` callbacks. These are `_initialize_gpu`, `_render` (one per update), `_release_gpu` (on exit) and `_reinitialize_gpu` (on `rebuild_geometry`).
- Device: `RenderingServer.get_rendering_device()` (the main device). The tests use `RenderingServer.create_local_rendering_device()` instead.
- Output binding: one `Texture2DRD` named `texture` receives `texture_rd_rid = gpu.output` on the render thread. That same Texture2DRD is set as the `irradiance_tex` shader parameter on every material the controller creates.
- Debug binding: a second `Texture2DRD` named `debug_texture` receives `gpu.debug_output` when `debug_enabled` is set.
- Engine textures read: none. The solver does not read the color, depth, normal-roughness or motion buffers. It uses no CompositorEffect, no RenderSceneBuffersRD and no screen-space texture. The field is world-space and does not depend on the camera.
- Material installation: `_collect` (and `_collect_visual`) sets a new ShaderMaterial on each `RCPrimitive.material_override`, and on each mesh surface through `set_surface_override_material`. The original overrides are stored in `_original_overrides` and `_original_surfaces`, then restored by `_restore_materials()` on exit and before a rebuild.
- Per-frame parameters: `_process` writes `surface_color` and `emission_color` on the materials of the analytic primitives only. Mesh-surface colors are set once at setup.
- Per-frame ordering in `_process`: return early if not ready, paused or pending; pack every primitive; update each primitive material; return if `_tick % update_every_frames != 0`; otherwise set `_pending = true` and enqueue `_render` with the packed bytes, object count, bounce, blend, sky color and debug flags.
- `_render` (render thread): `gpu.dispatch(...)`, then `gpu.update_debug(...)` if requested, then `_finish_frame.call_deferred()`, which clears `_pending` and increments `frame_count`.
- Shader compile: `RCGPU._compile(filename)` reads `common.glslinc` and `mesh.glslinc` with `FileAccess.get_file_as_string`. It replaces `// MESH` in the common text with the mesh text, and `// COMMON` in the target file with the common text. It then calls `rd.shader_compile_spirv_from_source`, reads `get_stage_compile_error`, and creates the shader RID. Compile errors are appended to `failure`. Shaders are compiled at runtime, so export presets must include `*.glslinc` in the non-resource file filter (README).
- Shader root: `res://addons/radiance_cascades/shaders/`. Shader paths are rooted there, so the addon folder must keep its layout.
- Failure reporting: `initialize` sets `failure` for a null device or a compile error. `_initialize_gpu` then emits `failed(message)` through a deferred call. The message also goes to `push_error`.
- Rebuild: `rebuild_geometry()` sets `is_ready = false`, waits while `_pending`, restores materials, clears the primitive, material and mesh lists, re-collects, rebuilds the BVH, reapplies materials, and enqueues `_reinitialize_gpu`. That callback calls `_release_gpu()`, creates a new `RCGPU`, and runs `_initialize_gpu()`. `initialized` is emitted again on completion. History is reset.
- Teardown: `_exit_tree` restores materials, then enqueues `_release_gpu`, which clears both Texture2DRD RIDs and calls `gpu.release()`. `release()` frees the tracked RIDs in reverse order.
- `assert` statements guard the setup. Godot's GDScript `assert` is not evaluated in release builds.

## Scene representation

Two kinds of geometry are traced. Both are world-space and both live under `geometry_root`.

### 1. Static triangles (CPU BVH snapshot)

- Source: every `MeshInstance3D` under `geometry_root` that is not an `RCPrimitive` with a Box or Sphere mesh. `RCPrimitive` nodes with other mesh types also go here.
- Build: `RCMeshBVH.build()` runs on the main thread. Each surface is read with `surface_get_arrays`. Indexed and non-indexed triangle surfaces are supported. Each vertex is multiplied by `instance.global_transform`, so translation, rotation and non-uniform scale are baked into the snapshot.
- Rejected inputs: skinned meshes (`instance.skin` asserted null), singular transforms, and non-triangle primitive types. Degenerate triangles with `cross(b-a, c-a).length_squared() < 1e-14` are skipped.
- Per-triangle data: three world vertices, a linear albedo and a linear emission RGB. Albedo is `material.albedo_color` converted with `srgb_to_linear()`. Emission is `material.emission.srgb_to_linear() * emission_energy_multiplier` when `emission_enabled`. Unassigned materials give white albedo and black emission. `RCPrimitive` nodes use their own `albedo` and `radiance`. Texture maps are not read for transport.
- Tree layout: 3 vec4 per node (48 bytes). Fields are `lower.xyz`, `upper.xyz`, and `links = (first triangle index, triangle count, escape index)`. Triangle layout is 5 vec4 (80 bytes): `a`, `b`, `c`, `albedo`, `emission`.
- Split rule: binned surface-area split. Eight bins per axis are tested on all three centroid axes. The cost of a split is `area(left) * n_left + area(right) * n_right`. Leaves hold at most 4 triangles. When no valid split exists, the node splits at the index midpoint.
- Traversal order: nodes are flattened in preorder. The escape index is the index of the first node after the subtree. A missed box jumps to the escape index. Traversal is stackless and iterative in `trace_mesh`.
- Traversal details: `closest` is shrunk as hits are found, so later boxes and triangles are tested against the nearest hit so far.
- Two-sided: `triangle_hit` flips the normal toward the incoming ray. Triangles are opaque. Hits closer than 0.0001 are ignored.
- Static snapshot: the BVH is not updated per frame. Moving triangle meshes keep their build-time transform until `rebuild_geometry()` is called.

### 2. Analytic primitives (per-frame packed)

- Source: `RCPrimitive` nodes with `BoxMesh` or `SphereMesh` under `geometry_root`. Limit: 64 (`RCGPU.MAX_OBJECTS`).
- Packing: `RCPrimitive.pack()` writes 112 bytes per object. The first 64 bytes are the inverse world transform as a mat4 (`global_transform.affine_inverse()`). Then comes `shape` (vec4), then linear `albedo`, then `radiance` plus the point flag in `.w`.
- Shape encoding: Box stores size in `shape.xyz` and `shape.w = 0`. Sphere stores `(radius, point_range or 0, 0, 1)`. Spheres must have `height == 2 * radius` (asserted).
- Intersection: boxes use the slab method in object space, with the ray direction transformed without normalisation, so `t` stays in world units. Spheres use the full quadratic (`dot(d,d)`). Normals come back through the inverse transpose. A ray that starts inside a solid hits at `t = 0`.
- Point source: `point_source = true` on a sphere sets `emission.w = 1`. Such an object is never intersected. It acts only as a single explicit light (see RC section). At most one point source is allowed (asserted in `dispatch`).
- Emitter: a non-point primitive with `radiance > 0` emits from its surface and also appears as an intersectable occluder.

### Volume

- Base grid: 24 x 16 x 24 probes (`RCGPU.GRID`). Probe spacing at level 0 is `probe_spacing` (exported, default 0.5, range 0.1 to 4.0). Origin is `volume_origin` (default `(-6, 0, -6)`). Coverage at spacing 0.5 is 12 x 8 x 12 world units.
- The volume is world-space and does not follow the camera. Positions outside it clamp to boundary probes.
- Changing origin or spacing after initialization requires `rebuild_geometry()`.
- Demo settings (all set in code before `add_child`):

  | Demo | Origin | Spacing | Extent | Sky | Bounce | Temporal blend | Other |
  |---|---|---|---|---|---|---|---|
  | Default | (-6, 0, -6) | 0.5 | 12 x 8 x 12 | (0.015, 0.02, 0.03) | 0.65 | 0.3 | none |
  | Classic (Cornell and occlusion) | (-6, -1, -6) | 0.5 | 12 x 8 x 12 | black | 0.65 | 0.15 | `visibility_merge = true`; `pbr_surfaces = true` only for the occlusion study |
  | HELIOS (`reactor_hall.gd`) | (-12, 0, -12) | 1.0 | 24 x 16 x 24 | (0.035, 0.05, 0.075) | 0.55 | 0.45 | none |
  | NORTHLINE (`metro_station.gd`) | (-18, -3, -18) | 1.5 | 36 x 24 x 36 | (0.0002, 0.0004, 0.0006) | 0.55 | 0.5 | `pbr_surfaces = true`; `visual_geometry_root = train.visual` |
  | README minimal example | (-6, 0, -6) | 0.5 | 12 x 8 x 12 | black | 0.65 | 0.3 (default) | `pbr_surfaces` not set |

## Passes

Each update runs the following inside one `compute_list_begin()` / `compute_list_end()` pair, then copies the output. The update runs only when the controller is ready, not paused, not pending, and `_tick % update_every_frames == 0`.

1. **Cascade passes**, levels 4, 3, 2, 1, 0 in that order (`for level in range(LEVELS - 1, -1, -1)`).
   - Shader: `cascade.glslinc` with the common and mesh text included. One pipeline is bound for all levels. Each level binds its own uniform set and push constants.
   - Dispatch: `ceil(probes * directions / 64)` groups in x. One thread per (probe, direction).
   - Bindings (set 0): 0 scene SSBO (object data, read); 1 upper-level buffer (read; for level 4 a 16-byte dummy); 2 this level's output buffer (write); 3 history atlas as readonly `rgba16f` image; 4 mesh node SSBO; 5 mesh triangle SSBO; 6 linear sampler plus history atlas.
   - Push constants: 112 bytes (see RC section).
   - `compute_list_add_barrier` after every level, including level 0.
   - Dispatch counts:

     | Level | Probe grid | Probes | Directions per probe | Threads | Groups of 64 |
     |---|---|---|---|---|---|
     | 0 | 24 x 16 x 24 | 9216 | 32 | 294912 | 4608 |
     | 1 | 12 x 8 x 12 | 1152 | 128 | 147456 | 2304 |
     | 2 | 6 x 4 x 6 | 144 | 512 | 73728 | 1152 |
     | 3 | 3 x 2 x 3 | 18 | 2048 | 36864 | 576 |
     | 4 | 2 x 1 x 2 | 4 | 8192 | 32768 | 512 |

2. **Resolve pass** (`resolve.glslinc`). Input is level 0. Output is the six-lobe atlas.
   - Dispatch: `ceil(9216 * 6 / 64) = 864` groups in x.
   - Bindings: 0 scene SSBO (declared, not used by the body); 1 level-0 buffer (read); 2 output atlas (`rgba16f` image, write); 3 history atlas (`rgba16f` image, read); 4 and 5 mesh buffers; 6 sampler plus history.
   - Each thread is one (probe, face). Output is written into the atlas, then mixed with history using `temporal_blend`.
   - The copy is recorded after `compute_list_end()`. The code adds no explicit barrier before it, and none is needed: the render graph orders separate lists and copies that touch the same resource, and `compute_list_add_barrier` is only required between dispatches inside one list, which the code does after every level ([docs/rendering_device.md](../../docs/rendering_device.md)).
3. **History copy**: `rd.texture_copy(output, history, ...)` for the full 144 x 384 atlas. This is the feedback step for the next update.
4. **Debug pass** (only when `debug_enabled`). `update_debug()` runs in the same render callback, after the copy. It lazily creates `debug.glslinc`, its 256 x 640 RGBA16F output, and its uniform set. Dispatch is 32 x 80 groups of 8 x 8 threads. It reads the five level buffers directly, with no CPU readback.

No pass reads the output on the CPU in production. The tests do read back the results through a local device.

## RC parameters and math

### Constants and layout

| Name | Value | Where |
|---|---|---|
| `GRID` | 24 x 16 x 24 | `rc_gpu.gd` |
| `ORIGIN` | (-6, 0, -6) | `rc_gpu.gd`, default `volume_origin` |
| `LEVELS` | 5 | `rc_gpu.gd` |
| `MAX_OBJECTS` | 64 | `rc_gpu.gd` |
| `STRIDE` | 112 bytes per object | `rc_gpu.gd` |
| Exported `probe_spacing` | 0.5 (range 0.1 to 4.0) | `radiance_cascades.gd` |
| Exported `bounce_feedback` | 0.65 (range 0 to 1) | `radiance_cascades.gd` |
| Exported `temporal_blend` | 0.3 (range 0.01 to 1) | `radiance_cascades.gd` |
| Exported `update_every_frames` | 1 (range 1 to 8) | `radiance_cascades.gd` |
| Exported `sky_radiance` | (0.015, 0.02, 0.03) | `radiance_cascades.gd` |
| Exported `visibility_merge` | false | `radiance_cascades.gd` |

### Per-level layout (base spacing 0.5)

| Level | Spacing (s x 2^L) | Probe grid | Directions per probe | Angular grid | Interval (world units, base 0.5) | Storage (bytes per level) |
|---|---|---|---|---|---|---|
| 0 | 0.5 | 24 x 16 x 24 | 32 | 8 x 4 | [0, 0.75] | 4,718,592 |
| 1 | 1.0 | 12 x 8 x 12 | 128 | 16 x 8 | [0.75, 2.25] | 2,359,296 |
| 2 | 2.0 | 6 x 4 x 6 | 512 | 32 x 16 | [2.25, 5.25] | 1,179,648 |
| 3 | 4.0 | 3 x 2 x 3 | 2048 | 64 x 32 | [5.25, 11.25] | 589,824 |
| 4 | 8.0 | 2 x 1 x 2 | 8192 | 128 x 64 | [11.25, 23.25] | 524,288 |

- Interval formula in code: `interval_at(L) = (0.75 * (2^L - 1), 0.75 * (2^(L+1) - 1))`, then multiplied by `base_spacing / 0.5` at runtime. For HELIOS (spacing 1.0) the intervals are doubled, for example level 0 becomes [0, 1.5].
- Grid formula: `ceil(GRID / 2^L)` per axis. Level 4 grid is 2 x 1 x 2 because 16 / 16 = 1.
- Storage: each direction is one vec4 (16 bytes). Total for five levels is 585,728 directions, which is 9,371,648 bytes (8.9375 MiB).
- Irradiance atlases: two RGBA16F textures of 144 x 384 (`GRID.x * 6` by `GRID.y * GRID.z`), 442,368 bytes each, 0.84375 MiB together.
- Ray segments per update: 585,728 stored directions times 4 children = 2,342,912 traced segments (documented in `implementation.md`).

### Direction mapping

- Stored direction at level L is cell `(cx, cy)` in an angular grid of `(8 * 2^L) x (4 * 2^L)`, with index `cx + cy * ax`.
- Direction formula: `phi = (cx + 0.5) / ax * 2 * PI`, `y = 1 - 2 * (cy + 0.5) / ay`, `r = sqrt(1 - y*y)`, `dir = (cos(phi) * r, y, sin(phi) * r)`.
- The bins are uniform in longitude and in `y = cos(polar)`, so they are equal solid angle over the full sphere. The hemisphere restriction comes from clamping cosines to zero in the resolve.
- Four children of each parent cell are the level-(L+1) cells `(2 * cx + (c & 1), 2 * cy + (c >> 1))`. Their `direction_at` values use the doubled angular grid, which is the same grid as level L+1.

### Merge (cascade pass), per probe p, per stored direction d at level L

For each child c in 0..3:

1. `(Lnear, Tnear) = trace_interval(p_center, dir_child)`, traced over the level-L interval.
2. If `Tnear > 0` and an upper level exists: `(Lfar, Tfar) = sample_upper(p_center, child_index, upper_dirs)`. Otherwise `(Lfar, Tfar) = (sky, 1)`.
3. Child result: `L_c = Lnear + Tnear * Lfar`, `T_c = Tnear * Tfar`.

The stored value is the average of the four children: `L = 0.25 * sum L_c`, `T = 0.25 * sum T_c`.

- At the top level there is no upper level, so the far term is the constant `sky_radiance` with transmittance 1.
- `sample_upper` trilinearly interpolates the 8 surrounding upper-level probes, with upper spacing `2s`, at the position `p_center`. Sample coordinates are `(pos - origin) / (2s) - 0.5`, clamped to the grid.
- Visibility merge (only when `visibility_merge` is set): each corner whose weight exceeds 1e-5 is tested with a segment from the position to that corner's probe. Blocked corners get weight 0. If the remaining weight sum is at or below 1e-5, `sample_upper` returns `(0, 0, 0, 0)`. That value is treated as fully occluded black, not as sky.
- The `child_index` passed to the upper level is `cx + cy * (2 * ax)` in the upper level's indexing, with `direction_count * 4` as the upper direction count.

### Interval tracing (`trace_interval`)

- Ray origin is `p_center + dir * start`, where `start` is the level's lower interval bound. The search length is `end - start`.
- Analytic primitives are tested first, then the BVH with the nearest hit so far as the limit.
- Miss: returns `(0, 0, 0, T=1)`.
- Hit with `closest < 0.0001` (starts inside a solid): returns `(0, 0, 0, T=0)`, which is opaque black.
- Hit otherwise: returns `(radiance, T=0)` with `radiance = emission + albedo * bounce * (history_irradiance(p, n) + point_irradiance(hit + n * 0.001, n))` where `p = hit + n * 0.6 * base_spacing`. The `bounce` term is `bounce_feedback`. The point term is included only when `bounce > 0`.
- Point-source term: when a point source exists, `I * cos / d^2 * fade^2` with `fade = max(1 - (d / R)^4, 0)`, `R` from the source's `shape.y`, and a shadow test against all analytic primitives and the BVH with limit `d - 0.001`. `cos` is clamped to zero.

### Resolve (six-lobe irradiance)

- For each base probe and each of six faces (`face = 2 * axis + (sign < 0 ? 1 : 0)`, so +X, -X, +Y, -Y, +Z, -Z), sum over the 32 level-0 directions: `sum = sum over d of L_0(d) * max(dot(n, d), 0)`, and `norm = sum over d of max(dot(n, d), 0)`.
- Result: `sum / norm`. A constant environment gives back the same constant exactly. The code comment says the quantity approximates irradiance divided by pi.
- Temporal blend: `out = mix(history, result, temporal_blend)`.
- Atlas pixel: `(p.x + face * 24, p.y + p.z * 16)`.

### Surface and hit lookup (`history_irradiance`, `sample_lighting`)

- Input: position and unit normal. For each axis `a`, pick face `2a` if `n_a >= 0`, else `2a + 1`. Sample the atlas bilinearly in x and y, blending two z slices with `fract(q.z)`. Weight each axis result by `n_a * n_a`.
- Clamping keeps lookups inside each face and slice: x is clamped to `[0, 23]` in probe units before adding the half-texel offset. This is the six-filtered-fetch approach described in the docs, instead of the eight explicit probe fetches used for the cascade merge.
- Surface shading in `surface.gdshader`: `color = emission + albedo * irradiance * gi_strength`. The lookup point is `world_position + normal * 0.6 * probe_spacing`. `view_mode` 1 shows irradiance, 2 shows albedo.
- Surface shading in `pbr_surface.gdshader`: `EMISSION = emission * station_power + albedo * irradiance * gi_strength * (1 - metallic)`. The `light()` function adds only GGX specular, plus diffuse when `local_diffuse` is set. The comment states that RC already contains emitter-to-surface diffuse transport.
- The `volume_grid` uniform in both surface shaders is not set by the code. It keeps its shader default of `(24, 16, 24)`.

### Other numeric facts

- Push constant layout for cascade and resolve (112 bytes, seven vec4): `origin_spacing` (origin xyz, level spacing), `grid_level` (grid xyz, level), `upper_grid_objects` (upper grid xyz, object count), `interval_bounce_blend` (interval start, end, bounce, blend), `base_grid_enabled` (base grid xyz, visibility_merge flag), `sky` (sky rgb, mesh node count), `volume_params` (base spacing, normal bias 0.6 * spacing, point index or -1, 0).
- Debug atlas: 256 columns by 640 rows. Five blocks of 128 rows, one per level. Column maps to azimuth, row to `cos` of polar angle inside the level's angular grid stretched to 256 x 128. RGB is merged radiance. A is transmittance (0 blocked, 1 open).

## Issues and notes

### Stated limitations (README, implementation.md, TODO.md)

- The field is a diffuse solver. There is no specular transport, no roughness-dependent queries, and no participating media. Highlights come from raster GGX on native lights.
- Surface constants only: ray hits use one albedo and one emission value per surface. Textures, normal maps, alpha masks, skinning, blend shapes and custom shaders are not transported.
- Static topology: triangle meshes that move need `rebuild_geometry()`, which can stall and resets history. Analytic primitives can move per frame (up to 64).
- Probe spacing 0.5 gives coarse contact shadows. Thin walls and small emitters can leak or be missed. Documented as known.
- Temporal blending adds lag and shimmer for moving emitters. The README says a slower blend reduces shimmer.
- Six-lobe reconstruction and the unoccluded final surface gather are approximations. Documented as not paper-exact.
- Interval shifting and cached extension are not implemented. Each interval is intersected directly.
- Only one explicit point source is supported.
- No sparse streaming, no skeletal animation, no hardware ray-tracing backend, no export validation, and no tests on Mobile renderer or other GPU vendors.
- Open items in `TODO.md`: independent brute-force reference renders, thin-wall visibility, near-field surface reconstruction, GPU timestamp profiling, sparse and scrolling volumes, specular transport, export validation.

### Documentation discrepancies (text versus code)

- `implementation.md` says material and bounce gathers offset by "0.3 world units". The code uses `0.6 * probe_spacing`. This equals 0.3 only at spacing 0.5. For HELIOS (spacing 1.0) the offset is 0.6.
- `volume_origin` and `probe_spacing` are copied into each material in `_collect` and into the GPU in `_initialize_gpu`. Neither is re-applied per frame, so changing them later needs `rebuild_geometry()`.

### Code-level notes

- `RadianceCascades` applies RC materials to `visual_geometry_root` meshes once at setup. Only `RCPrimitive` nodes under `geometry_root` are packed each frame. An `RCPrimitive` placed under `visual_geometry_root` keeps the colors it had at setup.
- `RCGPU.dispatch` asserts `scene.size() == object_count * STRIDE`, but only in debug builds.
- `sample_upper` returns zero (opaque black) when visibility merge rejects every corner. This can darken regions near thin walls. The code comments say the visibility test is optional for small scenes because of its cost.
- `trace_interval` comment: an interval starting inside a solid is treated as opaque, not as an interior emitter. The code does this.
- `resolve.glslinc` comment: the stored quantity is irradiance divided by pi. The code computes a cosine-weighted average normalised by the cosine sum. For a constant environment the stored value equals the radiance, which matches that comment.
- `RCMeshBVH` comment says "Surface-area splitting" and the implementation uses a binned cost of `area * count` without traversal or intersection cost constants.
- `rc_primitive.gd` `point_range` is used only for point sources. `sphere.height` must equal `2 * radius`.

### Performance and validation records (docs and README)

- HELIOS (72,012 triangles, 535 assemblies, 46,095 BVH nodes), 1920 x 1080, 2x MSAA, RTX 4060 Ti, Godot 4.7.stable: 161.3 average FPS, median 6.24 ms, p95 7.69 ms, over 1,200 measured frames. The docs state VSync was enabled on a 165 Hz display, so the result is display-capped. Not an uncapped benchmark.
- HELIOS CPU BVH build: about 1.22 seconds (1220.664 ms in one record). Earlier median-split BVH reached about 52 FPS at the same detail.
- NORTHLINE metro, earlier revision (1080p): 163.11 average FPS over 4,800 frames, CPU BVH build 168.288 ms. Also display-capped.
- NORTHLINE metro, later expanded revision at native QHD: a 180-frame check measured 29.81 FPS (median 33.77 ms, p95 45.78 ms). The docs state 60+ FPS at native QHD was not achieved for that revision.
- NORTHLINE metro, a later 2,400-frame QHD capture measured 139.05 mean FPS. The docs say this large difference from the 29.81 FPS run was not causally isolated.
- The docs say GPU load from other processes affected some measurements, and that old figures are historical.
