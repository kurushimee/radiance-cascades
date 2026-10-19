# Godot projects

The public RC implementations built on Godot, and the compositor-effect projects that show how screen-space work plugs into Forward+. The engine side they rely on (hooks, buffers, entry points into shading, SDFGI and HDDAGI) is in [Godot integration](godot_integration.md); `RenderingDevice` rules are in [docs/rendering_device.md](../../docs/rendering_device.md).

| Project | What it is | Godot path |
|---|---|---|
| [gomezzz](#gomezzz-world-space-3d-rc) | working world-space 3D grid: 24×16×24 base probes, 5 cascades, CPU-built BVH plus 64 analytic primitives, six-lobe irradiance atlas | `call_on_render_thread`, one compute list, `Texture2DRD` on generated `ShaderMaterial`s, RC written as `EMISSION` |
| [Phreakyx](#phreakyx-voxel-cone-rc-as-a-gdextension) | untested GDExtension design: voxel clipmaps, sparse hashed probes, cone tracing | POST_TRANSPARENT compositor effect, albedo guessed from the lit color |
| [2D projects](#2d-projects) | seven 2D repositories, four of them working | local device with readback, SubViewport chains, or the main device with `Texture2DRD` |
| [compositor effects](#compositor-effect-projects) | seven screen-space effects that read depth or normals and write light or occlusion | CompositorEffect, editing the color layer |

## gomezzz: world-space 3D RC

[gomezzz/godot-3d-radiance-cascades](https://github.com/gomezzz/godot-3d-radiance-cascades) (last commit 2026-09-13; MIT for code, some assets under their own licences) is a world-space 3D RC solver for Godot 4.7 Forward+ ([notes](../sources/2026_gomezzz_godot_3d_radiance_cascades.md)). Five cascade levels (`LEVELS`) sit on a 24 × 16 × 24 base grid, and each level is a Vulkan compute pass on the main device. Static geometry enters as a CPU-built triangle BVH snapshot, up to 64 moving analytic boxes and spheres are packed every frame, and spatial shaders sample the resulting irradiance atlas. The addon in `addons/radiance_cascades/` is meant to be copied into other projects; the rest of the repository holds demos, tests and tools. Only Windows with an RTX 4060 Ti was tested, and the README says Compatibility, WebGL and headless rendering cannot run the solver.

### Files

| File | Bytes | Role |
|---|---|---|
| `radiance_cascades.gd` | 7142 | `RadianceCascades` node: exports, lifecycle, material install and restore, per-frame primitive packing, render-thread scheduling, `rebuild_geometry()`, `set_view()` |
| `rc_gpu.gd` | 9932 | `RCGPU` (RefCounted): constants, device resources, runtime shader compile, dispatch, debug atlas, teardown |
| `rc_mesh_bvh.gd` | 6407 | `RCMeshBVH` (RefCounted): CPU triangle extraction from `MeshInstance3D` and the BVH build |
| `rc_primitive.gd` | 1504 | `RCPrimitive` (`@tool` `MeshInstance3D`): a BoxMesh or SphereMesh with `albedo`, `radiance`, `point_source`, `point_range`; packs 112 bytes |
| `rc_pbr_material.gd` | 2053 | `RCPBRMaterial` (RefCounted): copies supported `BaseMaterial3D` properties onto `pbr_surface.gdshader` |
| `shaders/common.glslinc` | 7009 | shared buffers and push constants, analytic intersection, point-source term, interval tracer, history lookup; holds the `// MESH` placeholder |
| `shaders/mesh.glslinc` | 2207 | BVH node and triangle structs, bindings 4 and 5, `box_hit`, `triangle_hit`, `trace_mesh` |
| `shaders/cascade.glslinc` | 3475 | the merge kernel, one dispatch per level |
| `shaders/resolve.glslinc` | 1192 | six-lobe irradiance from level 0, with the temporal blend |
| `shaders/debug.glslinc` | 1405 | a 256 × 640 diagnostic atlas read from the level buffers; self-contained |
| `shaders/validate_mesh.glslinc` | 531 | ray-query kernel for CPU-versus-GPU BVH checks, not on the production path |
| `shaders/surface.gdshader` | 1809 | unshaded default surface for primitives and meshes |
| `shaders/pbr_surface.gdshader` | 7592 | PBR surface with RC diffuse in `EMISSION` and only GGX specular in `light()`, plus metro-specific paint and reflection-clip code |

The root (downloaded as text) holds `README.md` (43,555 bytes: documentation, test counts, performance records, limitations, licence, credits), `TODO.md` (2,048 bytes, open items under Next and Someday), `docs/implementation.md` (16,675 bytes: cascade layout, memory, BVH format, merge and resolve, approximations, extension points) and `docs/validation.md` (26,011 bytes: dated verification and performance records, test counts, known warnings). `tests/test_mesh.gd` checks GPU triangle traversal against Godot's CPU triangle intersection on four indexed cylinders and a non-indexed surface: more than 100 triangles and 12 BVH nodes, shader compilation, emission reaching the cascade radiance (maximum above 0.1), reference rays hitting geometry, triangle extraction keeping every face, a BVH that survives glTF export and import, 72,012 triangles in the full hall, and material restoration when the controller is removed (`:54-234`). It renders nothing and measures no lighting error. The eight metro shaders (display, ember, flame, focus, postfx, reflection, steam, steam_volume) are effects only and do not reference RC. The addon files, README, docs, TODO, `project.godot`, `classic_example.gd` and `reactor_hall.gd` were read in full, `test_mesh.gd`, `metro_station.gd`'s RC setup and the metro shaders as well, and the other scripts and tests only by function names and an RC API grep.

### Godot integration

- **Entry and threads.** `RadianceCascades` is a node added to the scene. `_ready()` collects geometry, builds the BVH on the main thread, installs materials and schedules `call_on_render_thread(_initialize_gpu)`. All device work runs in render-thread callbacks: `_initialize_gpu`, `_render` (one per update), `_release_gpu` (on exit) and `_reinitialize_gpu` (on rebuild).
- **Device.** The main device; the tests use a local device instead and read results back.
- **Output.** One `Texture2DRD`, `texture`, receives `gpu.output` through `texture_rd_rid` on the render thread and is set as the `irradiance_tex` parameter on every material the controller creates. A second, `debug_texture`, receives `gpu.debug_output`, the debug atlas, when `debug_enabled` is set.
- **No engine buffers.** The solver reads no color, depth, normal-roughness or motion buffer and uses no CompositorEffect, no `RenderSceneBuffersRD` and no screen-space texture; the field is world-space and independent of the camera.
- **Materials.** `_collect` (and `_collect_visual`) sets a new `ShaderMaterial` on each `RCPrimitive.material_override` and on each mesh surface through `set_surface_override_material`, storing the originals in `_original_overrides` and `_original_surfaces` and restoring them in `_restore_materials()` on exit and before a rebuild.
- **Per frame.** `_process` returns early if not ready, paused or pending; packs every primitive; writes `surface_color` and `emission_color` on the primitives' materials only (mesh colors are set once); returns unless `_tick % update_every_frames == 0`; then sets `_pending` and enqueues `_render` with the packed bytes, object count, bounce, blend, sky color and debug flags. `_render` dispatches, updates the debug atlas if asked, and defers `_finish_frame`, which clears `_pending` and counts the frame.
- **Shader compile.** `RCGPU._compile` reads `common.glslinc` and `mesh.glslinc` with `FileAccess.get_file_as_string`, replaces `// MESH` in the common text with the mesh text and `// COMMON` in the target with the common text, compiles with `shader_compile_spirv_from_source`, reads `get_stage_compile_error`, appends errors to `failure` and creates the shader RID. Export presets must include `*.glslinc` in the non-resource filter, and shader paths are rooted at `res://addons/radiance_cascades/shaders/`, so the folder must keep its layout.
- **Failures.** `initialize` sets `failure` for a null device or a compile error, and `_initialize_gpu` then emits `failed(message)` through a deferred call and `push_error`.
- **Rebuild.** `rebuild_geometry()` sets `is_ready = false`, waits while pending, restores materials, clears the lists, re-collects, rebuilds the BVH, reapplies materials and enqueues `_reinitialize_gpu`, which releases the GPU state, makes a new `RCGPU` and initializes it. `initialized` fires again, and history resets.
- **Teardown.** `_exit_tree` restores materials and enqueues `_release_gpu`, which clears both `Texture2DRD` RIDs and calls `gpu.release()`, freeing the tracked RIDs in reverse order.
- **Asserts** guard the setup, and GDScript strips `assert` in release builds; `RCGPU.dispatch`'s check that the packed scene is `object_count × 112` bytes is one of them.

### Scene

Everything traced is world-space and lives under `geometry_root`.

**Static triangles.** Every `MeshInstance3D` under `geometry_root` except Box and Sphere `RCPrimitive`s (other `RCPrimitive` meshes come here too) is read with `surface_get_arrays`, indexed or not, and multiplied by `global_transform`, so translation, rotation and non-uniform scale are baked in. Skinned meshes (asserted), singular transforms and non-triangle primitives are rejected, and triangles with `|cross(b − a, c − a)|² < 1e−14` are skipped. Each triangle carries three world vertices, a linear albedo (`albedo_color` through `srgb_to_linear()`) and a linear emission (`emission.srgb_to_linear() · emission_energy_multiplier` when `emission_enabled`); no material means white albedo and no emission, `RCPrimitive` meshes use their own `albedo` and `radiance`, and texture maps are not read. The BVH layout, split rule and build time are in [scene representation](scene_representation_and_tracing.md#other-software-bvhs-in-rc-projects). Beyond those: the split cost is `area(left)·n_left + area(right)·n_right` over 8 bins on all three centroid axes, with no traversal or intersection constants despite the "surface-area splitting" comment; a node with no valid split is cut at its index midpoint; traversal shrinks `closest` as hits are found; triangles are opaque and two-sided, with the normal flipped toward the ray; hits closer than 0.0001 are ignored; and moving meshes keep their build-time transform until `rebuild_geometry()`.

**Analytic primitives.** Box and Sphere `RCPrimitive`s, at most 64 (`RCGPU.MAX_OBJECTS`), pack 112 bytes each (`STRIDE`) in `RCPrimitive.pack()`: the inverse world transform (`global_transform.affine_inverse()`) as a mat4 (64 bytes), a `shape` vec4, linear albedo, and radiance with the point flag in `.w`. A box stores its size in `shape.xyz` with `w = 0`; a sphere stores `(radius, point_range or 0, 0, 1)` and must have `height = 2·radius` (asserted). Boxes use the slab test in object space with the direction transformed but not normalized, so `t` stays in world units; spheres solve the full quadratic with `dot(d, d)`; normals return through the inverse transpose; a ray starting inside a solid hits at `t = 0`. A sphere with `point_source` sets `emission.w = 1`, is never intersected and acts as the one explicit light (at most one, asserted). Any other primitive with radiance emits from its surface and also occludes.

**Volume.** `probe_spacing` (default 0.5, range 0.1 to 4.0) and `volume_origin` (default (−6, 0, −6), the `ORIGIN` constant of `rc_gpu.gd`) give 12 × 8 × 12 world units at the default. The volume does not follow the camera, lookups outside clamp to the boundary probes, and changing origin or spacing needs `rebuild_geometry()` because both are copied into each material and the GPU only at setup.

The other exports of `radiance_cascades.gd` are `bounce_feedback` (0.65, range 0 to 1), `temporal_blend` (0.3, range 0.01 to 1), `update_every_frames` (1, range 1 to 8), `sky_radiance` ((0.015, 0.02, 0.03)) and `visibility_merge` (false).

The demos set these values in code before `add_child`:

| Demo | Origin | Spacing | Extent | Sky | Bounce | Temporal blend | Other |
|---|---|---|---|---|---|---|---|
| Default | (−6, 0, −6) | 0.5 | 12 × 8 × 12 | (0.015, 0.02, 0.03) | 0.65 | 0.3 | |
| Classic (Cornell and occlusion) | (−6, −1, −6) | 0.5 | 12 × 8 × 12 | black | 0.65 | 0.15 | `visibility_merge`; `pbr_surfaces` only for the occlusion study |
| HELIOS (`reactor_hall.gd`) | (−12, 0, −12) | 1.0 | 24 × 16 × 24 | (0.035, 0.05, 0.075) | 0.55 | 0.45 | |
| NORTHLINE (`metro_station.gd`) | (−18, −3, −18) | 1.5 | 36 × 24 × 36 | (0.0002, 0.0004, 0.0006) | 0.55 | 0.5 | `pbr_surfaces`; `visual_geometry_root = train.visual` |
| README minimal example | (−6, 0, −6) | 0.5 | 12 × 8 × 12 | black | 0.65 | 0.3 (default) | `pbr_surfaces` not set |

### Passes

An update runs only when the controller is ready, not paused, not pending and on an `update_every_frames` tick. Inside one `compute_list_begin()`/`compute_list_end()` pair:

1. **Cascade passes**, levels 4, 3, 2, 1, 0. One pipeline (`cascade.glslinc` with the common and mesh text) serves all levels, each with its own uniform set and push constants, and `compute_list_add_barrier()` follows every level, level 0 included. Each thread is one (probe, direction), in `ceil(probes × directions / 64)` groups. Bindings: 0 the scene buffer, 1 the upper level (a 16-byte dummy for level 4), 2 this level's output, 3 the history atlas as a read-only `rgba16f` image, 4 and 5 the BVH nodes and triangles, 6 a linear sampler with the history atlas.

   | Level | Probe grid | Probes | Directions | Threads | Groups of 64 |
   |---|---|---|---|---|---|
   | 0 | 24 × 16 × 24 | 9216 | 32 | 294,912 | 4608 |
   | 1 | 12 × 8 × 12 | 1152 | 128 | 147,456 | 2304 |
   | 2 | 6 × 4 × 6 | 144 | 512 | 73,728 | 1152 |
   | 3 | 3 × 2 × 3 | 18 | 2048 | 36,864 | 576 |
   | 4 | 2 × 1 × 2 | 4 | 8192 | 32,768 | 512 |

2. **Resolve**, 864 groups, one thread per (probe, face), from level 0 into the six-lobe atlas, mixed with history by `temporal_blend`. Bindings match the cascade pass, with binding 0 declared but unused.
3. **History copy** after the list ends: `texture_copy` of the whole 144 × 384 atlas into the history, the feedback for the next update. No explicit barrier is needed, because the render graph orders lists and copies that touch the same resource, and `compute_list_add_barrier` is needed only between dispatches inside one list, which the code does after every level ([barriers](../../docs/rendering_device.md#barriers-between-dispatches)).
4. **Debug pass** (`update_debug()`), only with `debug_enabled`, in the same render callback after the copy: lazily creates its shader, a 256 × 640 RGBA16F output and its uniform set, and dispatches 32 × 80 groups of 8 × 8 over the five level buffers, with no readback. The atlas has one 128-row block per level, azimuth across and the cosine of the polar angle down, stretched to 256 × 128; RGB is merged radiance and A transmittance (0 blocked, 1 open).

Production never reads results on the CPU.

### Cascade layout and merge

| Level | Spacing | Grid | Directions | Angular grid | Interval at base 0.5 | Bytes |
|---|---|---|---|---|---|---|
| 0 | 0.5 | 24 × 16 × 24 | 32 | 8 × 4 | [0, 0.75] | 4,718,592 |
| 1 | 1.0 | 12 × 8 × 12 | 128 | 16 × 8 | [0.75, 2.25] | 2,359,296 |
| 2 | 2.0 | 6 × 4 × 6 | 512 | 32 × 16 | [2.25, 5.25] | 1,179,648 |
| 3 | 4.0 | 3 × 2 × 3 | 2048 | 64 × 32 | [5.25, 11.25] | 589,824 |
| 4 | 8.0 | 2 × 1 × 2 | 8192 | 128 × 64 | [11.25, 23.25] | 524,288 |

- **Formulas.** `interval_at(L) = (0.75·(2^L − 1), 0.75·(2^(L+1) − 1))`, scaled by `base_spacing/0.5` at run time (HELIOS's level 0 is [0, 1.5]). The grid is `ceil(GRID/2^L)` per axis, which makes level 4 2 × 1 × 2.
- **Storage.** One vec4 (16 bytes) per direction: 585,728 directions, 9,371,648 bytes (8.94 MiB). The two RGBA16F irradiance atlases are 144 × 384 (`GRID.x·6` by `GRID.y·GRID.z`), 442,368 bytes each. An update traces 585,728 × 4 = 2,342,912 segments.
- **Directions.** Level `L` stores cell `(cx, cy)` of an `(8·2^L) × (4·2^L)` grid, indexed `cx + cy·ax`, with `phi = (cx + 0.5)/ax·2π`, `y = 1 − 2(cy + 0.5)/ay`, `r = √(1 − y²)` and `dir = (cos phi·r, y, sin phi·r)`. Bins are uniform in longitude and in `cos` of the polar angle, so they are equal-area over the sphere ([direction maps](cascade_layout_and_merging.md#direction-maps-in-3d)); the hemisphere comes from clamping cosines in the resolve. A cell's four children are `(2cx + (c & 1), 2cy + (c >> 1))` on the next level's grid.
- **Merge.** For each stored direction and each child `c`: trace `(L_near, T_near)` over the level's interval from the probe center; if `T_near > 0` and a level above exists, `(L_far, T_far)` comes from `sample_upper`, otherwise `(sky, 1)`; then `L_c = L_near + T_near·L_far` and `T_c = T_near·T_far`. The stored value is the mean of the four children. `sample_upper` interpolates the 8 surrounding upper probes trilinearly at the probe center, at `(pos − origin)/(2s) − 0.5` clamped to the grid, with child index `cx + cy·(2·ax)` and `4×` the direction count.
- **Visibility merge** (`visibility_merge`): each corner with weight above 1e−5 is tested by a segment from the position to that probe and dropped if blocked; if the remaining weight is at most 1e−5, `sample_upper` returns `(0, 0, 0, 0)`, treated as opaque black, not sky. The comments call the test optional for small scenes because of its cost.
- **Interval tracing.** The ray starts at `p_center + dir·start` and runs `end − start`, testing analytic primitives first and then the BVH up to the nearest hit. A miss returns `(0, T = 1)`. A hit closer than 0.0001 (starting inside a solid) returns opaque black. Any other hit returns `T = 0` and `emission + albedo·bounce·(history_irradiance(p, n) + point_irradiance(hit + 0.001n, n))` with `p = hit + 0.6·base_spacing·n` and `bounce = bounce_feedback`; the point term is added only when `bounce > 0`.
- **Point light.** `I·cos/d²·fade²` with `fade = max(1 − (d/R)⁴, 0)`, `R` from the source's `shape.y`, `cos` clamped at zero, and a shadow ray against all primitives and the BVH with limit `d − 0.001`.
- **Resolve.** For each base probe and face (+X, −X, +Y, −Y, +Z, −Z as `2·axis + (sign < 0)`), `Σ_d L_0(d)·max(n·d, 0) / Σ_d max(n·d, 0)` over the 32 level-0 directions, which returns a constant environment exactly and is the `E/π` the code comment names ([normalization](3d_screen_space.md#final-gather)); then `mix(history, result, temporal_blend)` into pixel `(p.x + face·24, p.y + p.z·16)`.
- **Lookup.** For each axis pick the face matching the normal's sign, sample the atlas bilinearly in x and y and blend two z slices by `fract(q.z)`, and weight the axis by `n_a²`: six filtered fetches, against the merge's eight explicit probe reads. Coordinates are clamped inside each face and slice (x to `[0, 23]` before the half-texel offset).
- **Surfaces.** `surface.gdshader` outputs `emission + albedo·irradiance·gi_strength`, looked up at `world_position + 0.6·probe_spacing·normal`, with `view_mode` 1 for irradiance and 2 for albedo. `pbr_surface.gdshader` writes `EMISSION = emission·station_power + albedo·irradiance·gi_strength·(1 − metallic)` and adds only GGX specular in `light()` (plus diffuse with `local_diffuse`), since RC already carries emitter-to-surface diffuse. Neither shader's `volume_grid` uniform is set by code; it keeps its default `(24, 16, 24)`.
- **Push constants**, 112 bytes as seven vec4: `origin_spacing` (origin, level spacing), `grid_level` (grid, level), `upper_grid_objects` (upper grid, object count), `interval_bounce_blend` (start, end, bounce, blend), `base_grid_enabled` (base grid, visibility flag), `sky` (sky RGB, BVH node count), `volume_params` (base spacing, normal bias `0.6·spacing`, point index or −1, 0).

### Limitations and discrepancies

- A diffuse solver only: no specular transport, no roughness-dependent queries, no participating media. Highlights come from raster GGX on native lights.
- One albedo and emission per surface; textures, normal maps, alpha masks, skinning, blend shapes and custom shaders are not transported.
- Static topology: moving triangle meshes need `rebuild_geometry()`, which can stall and resets history. Analytic primitives move per frame.
- Spacing 0.5 gives coarse contact shadows, and thin walls and small emitters can leak or be missed.
- The temporal blend adds lag and shimmer for moving emitters; the README says a slower blend reduces shimmer.
- The six-lobe reconstruction and the unoccluded final surface gather are documented as approximations, not paper-exact. Interval shifting and cached extension are not implemented; each interval is intersected directly. One point source only.
- No sparse streaming, skeletal animation, hardware ray-tracing backend, export validation, or tests on Mobile or other GPU vendors. `TODO.md` lists independent brute-force references, thin-wall visibility, near-field surface reconstruction, GPU timestamp profiling, sparse and scrolling volumes, specular transport and export validation.
- `implementation.md` gives the material and bounce offsets as 0.3 world units; the code uses `0.6·probe_spacing`, which is 0.3 only at spacing 0.5 (0.6 for HELIOS).
- Materials under `visual_geometry_root` get RC materials once at setup, and only `RCPrimitive`s under `geometry_root` are packed per frame, so an `RCPrimitive` under the visual root keeps its setup colors. `point_range` is used only for point sources.
- Visibility merge's opaque-black fallback can darken regions near thin walls.

### Measurements

| Scene | Setup | Result |
|---|---|---|
| HELIOS: 72,012 triangles, 535 assemblies, 46,095 BVH nodes | 1920×1080, 2× MSAA, RTX 4060 Ti, Godot 4.7 stable, 1,200 frames | 161.3 FPS mean, median 6.24 ms, p95 7.69 ms, capped by VSync at 165 Hz; CPU BVH build about 1.22 s (1220.664 ms in one record); an earlier median-split BVH reached about 52 FPS |
| NORTHLINE, earlier revision | 1080p, 4,800 frames | 163.11 FPS mean, display-capped; BVH build 168.288 ms |
| NORTHLINE, expanded revision | native QHD, 180 frames | 29.81 FPS (median 33.77 ms, p95 45.78 ms); 60 FPS at QHD not reached |
| NORTHLINE, expanded revision | QHD, 2,400 frames | 139.05 FPS mean; the gap to the 29.81 FPS run was not isolated |

The docs say load from other processes affected some runs and treat old figures as historical.

### Derived points

- **Scaling class.** Spacing ×2, interval length ×2 (0.75, 1.5, 3, 6, 12 at base 0.5) and directions ×4 per level put gomezzz on the 3D `K = 4, l = 2` row, where the parallax error measured in parent bins doubles every level ([parallax in bin units](core_theory.md#parallax-in-bin-units-derived)). With a child at offsets of 0.25 or 0.75 parent cells per axis, the nearest of the 8 parent probes sits 0.87 child spacings away, and the trilinear-weighted mean distance is 1.41 spacings. Seen from the start of the parent interval, against the parent's azimuth bin:

  | Merge | Nearest parent | Weighted mean, perpendicular part | Parent bin |
  |---|---|---|---|
  | 0 → 1 | 33.1°, 1.5 bins | 42.4°, 1.9 bins | 22.5° |
  | 1 → 2 | 22.1°, 2.0 bins | 28.2°, 2.5 bins | 11.25° |
  | 2 → 3 | 18.9°, 3.4 bins | 24.2°, 4.3 bins | 5.6° |
  | 3 → 4 | 17.6°, 6.3 bins | 22.6°, 8.0 bins | 2.8° |

  The perpendicular part uses the sphere average `|Δ|·π/4`. The plain trilinear merge therefore reads the top levels 6 to 8 bins off, so most of level 4's 8,192 directions blur into parallax error (derived).
- **Storage per base probe.** Each level holds half the directions of the one below (×4 directions, ÷8 probes), so storage converges to twice level 0: about 1 KiB per base probe (1,016.9 bytes here), with level 0 at 50% and level 4 at 5.6% (level 4 does not halve because its grid rounds up). Level 0 alone is 512 bytes per probe, so one level-0 storage buffer reaches Vulkan's guaranteed 128 MiB at 262,144 base probes, a 64³ grid ([limits](../../docs/rendering_device.md#limits)). At 0.5 m spacing, 48 × 16 × 48 m would need 286 MiB and 64 × 16 × 64 m 508 MiB (derived).
- **Reach.** The top interval ends at 23.25 m at base 0.5, about twice the 12 m volume width, and rays trace the BVH beyond the volume, so off-volume geometry occludes and emits even though probes clamp at its edge (derived).
- **Throughput floor.** 2.34 M segments inside a 6.24 ms median frame, raster included, is at least 0.375 G segments per second on an RTX 4060 Ti against a 72,012-triangle BVH; the true rate is higher, since the frame was capped and also rasterized (derived).

## Phreakyx: voxel-cone RC as a GDExtension

[Phreakyx/RadianceCascadeGDext](https://github.com/Phreakyx/RadianceCascadeGDext) (2026-06, no licence) is a C++ GDExtension (godot-cpp) with 28 GLSL compute shaders run from a `CompositorEffect` ([notes](../sources/2026_phreakyx_godot_rc_gdextension.md)). The README says the code "wasn't compiled here", the submodules and binaries are missing, and many shader header comments disagree with the code, so it is an untested design. It is still the most complete published plan for world-space RC inside Forward+, and it shows how an effect without an albedo buffer has to fake the composite.

**Godot integration.**
- `RCCompositorEffect` runs at POST_TRANSPARENT with `access_resolved_depth` and `needs_normal_roughness`, reading `render_buffers/depth`, `render_buffers/color` and `forward_clustered/normal_roughness`, on the main device. An autoload adds the solver node when the `WorldEnvironment`'s compositor holds the effect.
- The first `dispatch()` scans the scene tree on the render thread (meshes, collision shapes, lights, `Texture2D.get_image()`), bakes the voxels and returns without compositing.
- Normals are decoded as `normal_roughness.xyz·2 − 1` in view space and rotated to world space, and depth is linearized as `z_near/raw`; neither was checked against the engine's encoding, and the first ignores the best-fit packing ([buffers](godot_integration.md#buffers-in-a-callback)).
- The composite guesses albedo from the lit color: `albedo = clamp((scene/lum)·clamp(lum/0.3, 0.04, 0.95), 0, 1)`, zero below luminance 0.001 (`approximate_albedo`, `rc_composite.glsl:24-31`), and the active line is `scene + irradiance·approximate_albedo(scene)·gi_intensity` (:60). The 0.3 is `ESTIMATED_LIGHTING`, commented as the assumed average incident level and "the scene knob"; the 0.95 cap is stricter than the comment's "a surface can't reflect >100%". `ANALYSIS.md` calls it a "guessed albedo". The declared `scene_albedo` binding is never read.

**Scene.**
- Static meshes are cut into 16 m chunks, subdivided until every edge is at most 2 m, and voxelized on the GPU. Albedo is the material color times the texture's average color.
- Five clipmap levels of 256³ voxels (0.25, 0.5, 1, 2 and 4 m), addressed toroidally (`index mod 256`). A level recenters when the player is more than 12.5% of its extent from the center; worker threads build the uncovered shells and the render thread commits one per frame.
- Level 0 stores occupancy and lit radiance (RGBA16F with 9 mips), emission, albedo and normal, six anisotropic directional mips at 128³, and a jump-flood distance field at 128³ updated two passes per frame.
- Direct light is injected into voxels: soft shadow marches over the distance field at level 0 (up to 96 steps), and occupancy marches with a "roof test" for the sun on coarse levels. After a rebake, light fades in over 10 frames.
- Moving rigid bodies are voxelized every frame into a binary grid with a decaying accumulator, `max(current, 0.95·previous)`.

**Probes and cascades.**

| Cascade | Directions (octahedral) | Spacing (m) | Interval (m) | Probe pool |
|---|---|---|---|---|
| 0 | 4×4 | 0.25 | 0 to 1.1 | 1,048,576 |
| 1 | 4×4 | 0.5 | 1 to 3.2 | 524,288 |
| 2 | 8×8 | 1 | 3 to 7.4 | 65,536 |
| 3 | 8×8 | 2 | 7 to 15.8 | 16,384 |
| 4 | 8×8 | 4 | 15 to 32.6 | 4,096 |

- Spacing and interval length double per cascade (`_cascade_scale = 2.0`, `CRadianceCascade.h:589`), while the direction table is `{4, 4, 8, 8, 8}` per side (`CRadianceCascade.cpp:1576`): angular branching per axis is 2 from cascade 1 to 2 and 1 elsewhere, and `rc_patch_merge.glsl:73` takes the ratio as `max(oct_{c+1}/oct_c, 1)`. Each interval is extended by 10% for overlap.
- Against the penumbra rule from cascade 0's 4 × 4 (directions per axis doubling as interval starts double), cascades 1 to 4 are 2×, 2×, 4× and 8× coarser per axis. The cone aperture `2/oct_c` widens to match, so the coarse cascades blur rather than alias (derived in the notes).
- Probes exist only near visible surfaces. Cascade 0 is seeded from a half-resolution pixel grid and higher cascades from a grid up to 1080 rows tall, and each sample creates the 8 cells its gather will read. Probe ids come from a free list and live in a hash (load 0.5, 64-step linear probing); ids unseen for 60 frames are freed.
- Each (probe, direction) is traced as a cone through the voxel mips with aperture `2/oct_c`, in steps of half the cone diameter (one to four voxels), with distance-field skips at level 0, stopping below 1% transmittance.
- Radiance is packed in 32 bits: a shared 5-bit exponent, three 7-bit mantissas and 6-bit transmittance.
- The merge is `rgb = own + own.a·parent`, the parent a trilinear mix of the 8 cascade `c + 1` neighbours with missing ones dropped and the weights renormalized; where the parent has 4× the directions, its 2×2 blocks are averaged first. An option re-traces only 1 in N directions per frame.

**Gather and denoise.**
- At half resolution each pixel reads the 8 cascade-0 probes with trilinear weights times `step(0, f)·(0.5 + 0.5f)`, where `f` is the normal dotted with the direction to the probe, so probes behind the surface are ignored.
- `E = Σ_d (R + T·sky(d))·max(n·d, 0)·4π/16`, with the sky gated by elevation, `sky_color·smoothstep(−0.2, 0.3, d.y)` (`rc_patch_gather.glsl:126`).
- Four [à-trous](supporting_techniques.md#denoising-upscaling-and-temporal-reuse) passes (steps 1, 2, 4, 8, B-spline 5×5) with depth, normal (power 8) and luminance weights, then a bilateral upsample with an edge fallback (`rc_irradiance_upsample.glsl:28-29, 70-76`): `edge = 1 − smoothstep(0.20, 0.60, wsum)` of the bilateral weight sum, and where `edge > 0.001` and a full-resolution cascade-0 gather finds a probe, the result is `mix(bilateral, gather, edge)`. The gather replaces the bilateral result below a weight sum of 0.2 and is unused above 0.6.

**Header comments against the code.**

| File | Header says | Code does |
|---|---|---|
| `rc_patch_merge.glsl:8` | direction table `{4, 4, 8, 8, 16}` | `{4, 4, 8, 8, 8}`, as `ANALYSIS.md` 2.1 says |
| `rc_patch_trace.glsl:8-9` | walk the whole hash region, skip empty slots; indirect size `bucket_cap·dirs` | walks the compact live list with a guard on `alloc_count`; `rc_patch_indirect.glsl:30` sizes it `alloc_count·dirs` |
| `rc_patch_gather.glsl:1-12` | trilinear blend of 8 cascade-0 probes; sky weighted by residual transparency | weights also multiplied by the facing term (:105-108); sky also gated by elevation (:126) |
| `rc_composite.glsl:7, 34-36` | albedo read "dummy for now"; GI "today additive" | albedo binding never read; GI multiplied by the guessed albedo (the additive form is commented out at :40, and `apply_gi` is not on the active path) |
| `rc_composite.glsl:30` | cap at 100% reflectance | luminance capped at 0.95 |
| `rc_clip_inject.glsl:6-7` | no distance-field march, visibility 1 | occupancy march `clip_vis` (:77) |
| `rc_patch_reduce.glsl:3-6` | identical to the in-merge `r²` average | the merge's `r` is 1 or 2; the reduce path was not checked |

The headers of `rc_patch_lookup.glsl`, `rc_irradiance_atrous.glsl` and `rc_irradiance_upsample.glsl`, and the schedule in `ANALYSIS.md`, match the code.

**Derived points.**
- With every pool full, the probe texels are 16.8 M, 8.4 M, 4.2 M, 1.0 M and 0.26 M, 30.7 M in all, and at 32 bits each 64, 32, 16, 4 and 1 MiB, 117 MiB in all.
- Level 0's RGBA16F radiance at 256³ is 128 MiB, 146 MiB with its 9 mips, before emission, albedo, normal, the anisotropic mips and the other four levels. 256 is also Vulkan's required minimum for `maxImageDimension3D`, so 256³ clipmaps stored as 3D images sit exactly at the portable limit.
- At 1080p the half-resolution seed grid is 518,400 samples, each creating up to 8 cells, 4.1 M cell requests against a 1,048,576-probe pool; neighbouring samples share cells, so the live count is lower, but the pool's "fills" behaviour depends on surface area on screen (derived).

## 2D projects

Seven public Godot projects implement or attempt 2D RC; their algorithms (Sohojoe's Yaazarai port, the Suslik ports, knowdawg's mip pyramid) are in [2D implementations](2d_implementations.md) ([notes](../sources/2024_godot_2d_rc_repositories.md)). Their Godot wiring:

| Pattern | Used by | Effect |
|---|---|---|
| `create_local_rendering_device()`, then `submit()`, `sync()` and `texture_get_data()` every frame, with the bytes copied into an `ImageTexture` | Sohojoe | every frame stalls and round-trips the image through the CPU; works, but slowly |
| SubViewports chained with canvas_item shaders, the cascade viewport reading a copy of itself from the previous frame | thmasn | no scripts; each frame merges once, so cascade `n` uses cascade `n + 1` from the last frame |
| main device, results in `Texture2DRD` and `Texture2DArrayRD` exposed as global shader parameters | knowdawg | no readback; material shaders sample the GI directly |
| main device with setup through `call_on_render_thread`, output in a `Texture2DRD` | TheCubeOfFire | no readback |

Bugs found by reading them:
- Sohojoe's distance pass reads the output of the second-to-last jump-flood pass, because of the ping-pong swap order.
- Sohojoe's Suslik port updates the six cascade images in place with no ping-pong. Dispatches for different cascades read and write the same images, and one cascade can span two images, so a read may see either the old or the new value.
- knowdawg dispatches 2048 × 2048 threads over 1024 × 1024 images with no bounds check, and two shaders declare `rgba32f` storage images bound to RGBA16F textures, which Vulkan leaves undefined.
- Recreating textures on a quality change without `free_rid` leaks GPU memory.
- TheSandwichCoder passes `width / 32` as a float to `compute_list_dispatch`; at 1080 rows that is 33.75 groups, so the last partial group of rows is dropped. Group counts need a ceiling division.
- The same project merges one cascade into the next in a texture array through two image bindings to one RID (one read-only, one write-only), relying on each thread touching only its own texel, and calls one `barrier` after all cascade dispatches instead of between them.

## Compositor effect projects

None of these feeds GI into the engine's lighting; every one edits the finished color layer ([notes](../sources/2026_godot_compositor_effect_examples.md)). Their shared skeleton and the engine facts they rely on are in [Godot integration](godot_integration.md#running-the-compute-work).

| Repository | Godot | Licence | Last commit | Effect |
|---|---|---|---|---|
| [post_shader](https://github.com/godotengine/godot-demo-projects/tree/master/compute/post_shader) | 4.7 | MIT | 2026-07 | official compute post-process demo plus a template that injects GLSL |
| [SSRT_GI_CompositorEffect](https://github.com/jebbyk/SSRT_GI_CompositorEffect) | 4.6 | MIT | 2026-03 | screen-space ray-traced GI: trace, blur, mix |
| [ambient-occlusion](https://github.com/LoganKeenan55/ambient-occlusion) | 4.7 | MIT | 2026-08 | SSAO, HBAO, SAO and GTAO in compute |
| [Godot-HBAO](https://github.com/KawaiiPrincess/Godot-HBAO) | 4.x | MIT | 2026-06 | HBAO as raster passes, works on Mobile |
| [godot-forest-demo](https://github.com/GamesNotDeveloped/godot-forest-demo) | 4.6 | CC-BY-4.0 | 2026-04 | sun shafts |
| [Godot-RealisticEnvironments](https://github.com/itzMeerkat/Godot-RealisticEnvironments) | 4.8 | MIT | 2026-10 | aerial perspective with dual-source blending |
| [compositor-effect-library](https://github.com/DevPoodle/compositor-effect-library) | 4.6 | MIT | 2026-04 | path tracer over hard-coded spheres |

**post_shader.** Two effects at POST_TRANSPARENT. The grayscale effect compiles a fixed `.glsl` once on the render thread. The template keeps user code in a `shader_code` export, marks the shader dirty under a mutex when it changes, substitutes the code at `#COMPUTE_CODE` and compiles it with `RDShaderSource`, reporting errors. It binds the engine scene UBO (`SceneDataBlock` from `godot/scene_data_inc.glsl`) at binding 0, the color layer as an `rgba16f` image at 1 and the depth layer through a nearest sampler at 2, with a 16-byte push constant (`raster_size`, view index, padding); size comes from `get_internal_size()`, sets from `UniformSetCacheRD`, and each view gets its own compute list with one dispatch. The sample unprojects depth with the include's per-view `inv_projection_matrix_view[view]` and shows view-space position divided by 20.

**SSRT.** The mix is `(color + color·gi)·(1 − occlusion)`, so the lit color stands in for albedo and unlit surfaces get no bounce. The depth helper builds NDC from the integer pixel without dividing by the size, so its linear depth is wrong, while the ray start does divide, so the two disagree. The settings UBO writes integers as floats and declares them `int` in GLSL (the author notes `PackedInt32Array` did not convert as expected); `PackedByteArray.encode_s32` encodes them correctly. Its scene-UBO include warns about buffer-size errors after engine updates.

**Ambient occlusion (LoganKeenan55).** Four AO shaders behind one GDScript effect at POST_TRANSPARENT; the shipped scene uses GTAO (the script default is SSAO), radius 0.3, and three render modes (flat, AO only, composited). All reconstruct view space from depth the same way. The AO target is R16F, and a 4×4 RGBA8 noise texture holds random unit vectors as `v·0.5 + 0.5`. The AO pass and a 5×5 bilateral blur run in separate compute lists, relying on the device to order them, and the camera UBO and uniform sets are created and freed every frame.

| Shader | Method | Constants | Cost in its comment (RTX 2070) |
|---|---|---|---|
| SSAO | 16 hemisphere offsets on a TBN from the noise vector; a sample is occluded when the stored surface is in front of it, weighted by `smoothstep(0, 1, radius/|dz|)` and `N·D`; `ao = (1 − occlusion)²` | radius from the export | about 0.80 ms |
| HBAO | after Scanberg's version of NVIDIA's HBAO: 8 noise-rotated directions, 6 steps, tracking the running horizon tangent and adding `(d²·(−1/R²) + 1)·(sin S − sin H)`; `ao = clamp(1 − 2·sum/8, 0, 1)` | intensity 2, tangent bias tan 30°, radius at most 50 px | about 1.45 ms |
| SAO | 11 samples on a 7-turn screen spiral from a random angle; term `(r² − d²)³·max((h − bias)/(ε + d²), 0)`; `ao = max(0, 1 − 5·intensity·sum/(r⁶·samples))^1.5` | ε 0.01, intensity 0.3, bias `0.05·radius` | about 0.70 ms |
| GTAO | after Activision's paper and Intel's XeGTAO: 8 slices, 8 steps per side, horizon cosines with a falloff over 0.4 of the radius, the slice arc integral, `ao = (visibility/slices)^1.5` | | none given |

The methods themselves are in [related screen-space GI](related_screen_space_gi.md). Issues found by reading:
- SSAO, SAO and HBAO read the stored `[0, 1]` noise as signed vectors, so SSAO's kernel rotation stays in one quadrant, SAO's start angle in `[0, π/2]`, and HBAO's "rotation" is not a rotation; only GTAO uses the values as `[0, 1)` offsets, which matches the encoding.
- The blur's fixed 0.01 threshold on raw nonlinear depth covers a different distance at every depth. Flat mode still runs the AO pass, the AO texture is created before the zero-size check, and background pixels at depth 0 are not skipped.
- Every view gets the first view's projection and the same normal texture. SSAO decodes normals through `normal_roughness_compatibility`, SAO and GTAO with `·2 − 1` only, and HBAO binds the normal texture without reading it.

**HBAO (KawaiiPrincess).** Its matrix UBO names a field `inv_proj` but fills it with the plain projection, never refreshes it after the first resize, and creates an R32F pass from an RGBA8 framebuffer format.

**Sun shafts (godot-forest-demo).** A controller installs the effect into the `WorldEnvironment`'s compositor at run time and each frame projects the sun (the light's `basis.z`, 10,000 units from the camera) to screen UV, hiding the effect when the sun is behind the camera. The shader reads `render_buffers/color` through a linear sampler and writes `get_color_layer(view)`: from each pixel it marches 40 steps toward the sun over `density` of the way, adding `smoothstep(threshold, 1, luminance)·decay^i·weight`, then adds `shaft_color·sum·exposure·falloff` with `falloff = smoothstep(max_radius, 0, distance)`, a call with `edge0 > edge1` that GLSL leaves undefined. Defaults are density 0.92, threshold 0.7, weight 0.028, decay 0.95, exposure 1.1 and max radius 0.9, which the demo scene overrides. It compiles on the main thread inside `_init`, which works but is not where the device is meant to be used. In mono the source and destination are probably the same image, so the dispatch reads pixels other workgroups are writing; a capture would settle it.

**Aerial perspective (Godot-RealisticEnvironments).** The only raster pass of the set: one full-screen triangle into the color layer at PRE_TRANSPARENT, with single-sample and MSAA variants (`sampler2DMS`, `texelFetch` with `gl_SampleID`, sample shading on). It reconstructs position with a camera-relative inverse view-projection that keeps only the camera rotation, discards depth 0 (the sky under reversed z), and reads a 32 × 128 × 64 RGBA16F camera volume whose distance slices are spaced by `√(d/max)`, denser near the camera, out to 100 km. A 256² transmittance LUT and a 32² multiple-scattering LUT feed it. The dual-source blend writes in-scatter (with a Henyey-Greenstein lobe, g = 0.97 by default) as output 0 and transmittance as output 1, and haze density is `3.912/visibility`. Its LUT compute passes are the only code in the set with explicit `compute_list_add_barrier` calls.

**Path tracer (compositor-effect-library).** 128 samples per pixel per frame and up to 5 bounces over four hard-coded spheres (three of radius 1.2 at x = −4, 0 and 4 with roughness 0, 0.2 and 0.6, and a ground sphere of radius 100 at y = −101), with no acceleration structure, Fresnel, light sampling or accumulation. The environment, baked once into a 1080×540 panorama, is the only light. Depth and normals are bound but never read, so the spheres draw over Godot's geometry with no depth test, and only pixels whose samples hit a sphere are written. It reassigns its uniform textures every frame, which rebuilds the uniform set every frame because the helper's texture setter marks the set dirty on every assignment, even with the same RID, and it reads view 0 only.

### Multiple views

A code search for `get_view_count` and `get_view_projection` found these patterns (not exhaustive):
- **Complete:** BastiaanOlij's RERadialSunRays loops over views "just in case we're doing stereo rendering", takes per-view slices of its own textures with `get_texture_slice(context, texture, view, 0, 1, 1)`, and adds `get_view_eye_offset(view)` to the sun's screen position under `get_view_projection(view)`; the view matrix is one camera transform for every view.
- **Per-view resources:** GodotRetro's base effect, an SMAA port, an SSIL-with-visibility-bitmask effect and a Gaussian-splatting compositor keep per-view textures or matrices.
- **One camera for every view:** the AO and sun-shaft projects above, SunshineClouds2 (one `get_cam_projection()` for all views; its author writes that the engine's scene UBO returns the wrong camera with several cameras) and GDVoxelTerrain's atmosphere. Of the seven projects in the table, only one handles more than one view correctly.

## Checklist from these projects

Each item is a failure seen above, stated as the rule that avoids it.

- Dispatch with a ceiling division, `(size − 1)/group + 1`, and bounds-check threads (TheSandwichCoder, knowdawg).
- Sample at `(pixel + 0.5)/size`, and divide by the size before building NDC (several projects sample at `pixel/size`, and the SSRT depth helper skips the division).
- Declare storage images in the format of the bound texture (knowdawg's `rgba32f` on RGBA16F).
- Free replaced textures with `free_rid` (2D projects), and do not free textures made by `RenderSceneBuffersRD.create_texture` ([own textures](godot_integration.md#buffers-in-a-callback)).
- Do not reassign uniform textures every frame, since that rebuilds the set; take sets from `UniformSetCacheRD` (path tracer).
- Encode integers with `PackedByteArray.encode_s32` (SSRT).
- Match a copied scene UBO struct to the engine version's `scene_data_inc.glsl` (SSRT, post_shader).
- Loop over views with per-view projections and textures (most effects).
- Ping-pong any pass that reads what another dispatch of the same pass writes, and check the swap parity (Sohojoe's jump flood and in-place cascades, TheSandwichCoder's two bindings to one RID, the sun shafts' same-image read).
- Keep `smoothstep`'s edges ordered (sun shafts).
- Under wgpu, Helio (Far-Beyond-Pulsar/Helio) found that one texture bound as both storage output and sampled input (cascade output and parent, history read and write) is invalid and needs ping-pong pairs, that some drivers reject `textureLoad` on depth textures or `textureLod` on shadow samplers (it read depth from an R32F Hi-Z mip instead), and that rebuilding bind groups every frame was a measurable cost ([discussions](../sources/2026_rc_discussions.md#implementer-notes)). The first and last carry over to Godot as the ping-pong and uniform-set rules above (inference).

## Connections

- **gomezzz is vanilla 3D RC with a trilinear merge on the doubling row.** Its interval doubling with ×4 directions puts the merge error in parent bins at 1.5 to 8 by the top level, the case the parallax fixes, Reservoir Cascades' reprojected lookup and the `l = 4` scaling address ([core theory](core_theory.md#parallax-in-bin-units-derived), [sampling and guiding](rc_for_sampling_and_guiding.md#connections)). Its optional visibility merge is the probe-visibility family of world-space leak defences ([leak defences](3d_world_space.md#leak-defences-in-world-space)).
- **gomezzz belongs with the dense grids.** At about 1 KiB per base probe it sits with tmpvar, jumeder and erhe in [dense world-space projects](3d_world_space.md#dense-projects), and like them it stays small (12 × 8 × 12 m at 0.5 m) to fit.
- **Phreakyx is a cone-traced RC.** Tracing each (probe, direction) as a cone through voxel mips is voxel cone tracing with cascade-sized apertures, the "mips are cones" equivalence ([scene representation](scene_representation_and_tracing.md#connections)), and its sparse hashed probes near visible surfaces are the sparse world-space design ([sparse probes](3d_world_space.md#sparse-probes-near-surfaces)). Its angular deficit of 2 to 8× per axis is hidden by the wider cones, which trades aliasing for blur.
- **Two ways around the missing albedo buffer.** gomezzz replaces every material and writes RC through `EMISSION`; Phreakyx composites after shading with a guessed albedo, which also tints transparent pixels at POST_TRANSPARENT. The engine's correct path, per-material `IRRADIANCE` ([getting GI into shading](godot_integration.md#getting-gi-into-shading)), costs the same material replacement as gomezzz's (inference).
- **One working path from 2D to 3D.** knowdawg's 2D addon and gomezzz's 3D solver use the same wiring: main device, `Texture2DRD`, sampled by material shaders, with no readback.
- **AO costs set the screen-space budget.** The AO passes cost 0.7 to 1.45 ms on an RTX 2070; a screen-space RC pass replaces both AO and indirect light, so it competes with that budget plus SSIL's (inference).

## Single-frame assessment

- **gomezzz is closest to single-frame.** Every update solves all five levels top-down with no frame-lagged merge. Its temporal parts are the resolve's blend (0.15 to 0.5 in the demos) and bounce light read from the previous update's atlas. With `temporal_blend = 1`, direct light and emitters are single-frame, and each frame adds one bounce from the frame before (inference).
- **Phreakyx leans on time in its scene, not its cascades.** Its light fades in over 10 frames after a rebake, moving voxels decay by 0.95 per frame, and the 1-in-N re-trace option spreads tracing over frames. With N = 1 and no fade, the cascades and the à-trous filter are spatial only.
- **Neither has single-frame multi-bounce.** Both get bounces by reading last frame's light at hits.
- **Dynamic triangles cannot enter in the same frame.** gomezzz's CPU BVH takes 1.2 s for 72,012 triangles, and only its 64 analytic primitives move per frame; a single-frame design with moving meshes needs a GPU-built structure ([Wicked Engine](scene_representation_and_tracing.md#wicked-engine-a-bvh-built-on-the-gpu-every-frame)).
- **The dense layout limits the volume.** At 1 KiB per base probe and a 128 MiB guaranteed buffer for level 0, gomezzz's layout stops near a 64³ grid unless levels are split across buffers, which caps a 0.5 m grid at 32 m on a side (derived).

## Open questions

- How large is gomezzz's error per level against a path-traced reference, and how much does it drop with a parallax-correct parent lookup or with `l = 4` intervals?
- How much of gomezzz's frame is tracing? It records no GPU timestamps, and its TODO lists timestamp profiling.
- Does Phreakyx's design compile and run, and how full do its probe pools get in a real scene?
- At what scene size does a dense grid like gomezzz's lose to sparse probes near surfaces, in memory and in rays per frame?
- Can the analytic-primitive path (64 per frame, 112 bytes each) grow into a per-frame proxy scene for moving objects, as a cheap same-frame alternative to rebuilding a BVH?
