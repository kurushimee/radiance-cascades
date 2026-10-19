# Godot integration

What Godot 4.7.2 (Forward+, Vulkan) gives an RC implementation, what it keeps private, how a GI result reaches shaded surfaces, and what the engine's own GI does with the same API: SDFGI, which ships, and HDDAGI, which is still a pull request. `RenderingDevice` rules checked against the engine are in [docs/rendering_device.md](../../docs/rendering_device.md) and are linked here, not repeated. Engine facts come from source reads at the 4.7.2-stable tag ([GI internals](../sources/2026_godot_gi_internals.md), [indirect diffuse paths](../sources/2026_godot_indirect_diffuse_paths.md), [compositor examples](../sources/2026_godot_compositor_effect_examples.md)). Line numbers in those notes come from one read except where a note marks them as checked. The RC projects built on Godot, and the compositor-effect projects these patterns come from, are in [Godot projects](godot_projects.md).

## Running the compute work

- **Device and thread.** Use the main device, `RenderingServer.get_rendering_device()`, on the render thread: inside `CompositorEffect._render_callback()` or through `RenderingServer.call_on_render_thread()` ([render thread](../../docs/rendering_device.md#render-thread)). A local device from `create_local_rendering_device()` has its own resources, so its results reach the renderer only through a CPU readback, and a readback every frame stalls ([2D projects](godot_projects.md#2d-projects)).
- **CompositorEffect** is the only way to read the frame's depth, normal, color and velocity buffers. Its callbacks run on the rendering thread, per viewport, with that viewport's camera, and are skipped for reflection-probe renders. Screen-space probes need it.
- **`call_on_render_thread` from `_process`** suits a world-space volume that does not depend on the camera. gomezzz enqueues one update per frame this way and skips frames while the previous update is pending ([gomezzz](godot_projects.md#gomezzz-world-space-3d-rc)).
- **One compute list per cascade chain.** Record the levels in one list with `compute_list_add_barrier()` between them ([barriers](../../docs/rendering_device.md#barriers-between-dispatches)). The render graph orders separate lists, and copies after a list, when they touch the same resource, which is why most compositor effects never call a barrier.
- **Uploads** go before `compute_list_begin()`; `buffer_update` inside a list fails ([uploads](../../docs/rendering_device.md#upload-before-the-compute-list)).
- **Includes** nest one level, and only in imported `.glsl` files ([includes](../../docs/rendering_device.md#shader-includes)). Runtime compilation from source cannot include files, so gomezzz splices its includes by string replacement before `shader_compile_spirv_from_source`, and the official post_shader template substitutes user code at a marker. Both then need their source files in the export filter.
- **Compile errors** do not stop the run; check `compile_error_compute` after every compile ([compile errors](../../docs/rendering_device.md#shader-compile-errors)).
- **Atomics** are 32-bit integer only ([atomics](../../docs/rendering_device.md#atomics)). Sums become fixed-point integers, as in HDDAGI's 14-bit probe splats, and hash keys wider than 32 bits need multi-word slots, as in wroughtinator's five-word slots ([world-space building blocks](3d_world_space.md#what-carries-to-renderingdevice)).
- **Indirect dispatch** sizes work on the GPU ([indirect dispatch](../../docs/rendering_device.md#indirect-dispatch)). SDFGI's light pass and Phreakyx's probe trace both use it.
- **Timing.** Timestamps are in nanoseconds and readable two frames later on the main device ([timestamps](../../docs/rendering_device.md#timestamps)).

The compositor effects in [Godot projects](godot_projects.md#compositor-effect-projects) share one skeleton:

- Compile the shader and create the pipeline on the render thread (`call_on_render_thread` from `_init`), and free the shader in `NOTIFICATION_PREDELETE`, which frees its pipelines too.
- In the callback, return unless the type matches, cast `get_render_scene_buffers()` to `RenderSceneBuffersRD`, return on a zero `get_internal_size()`, and loop over `get_view_count()`.
- Take uniform sets from `UniformSetCacheRD.get_cache(shader, set, uniforms)` per view per frame; the cache drops them when the viewport changes. Creating sets with `uniform_set_create` and freeing them after each dispatch also works but costs more.
- Push 16-byte constants (`vec2 raster_size` plus a view index or padding); larger blocks pack matrices column by column.
- Dispatch 8×8 groups, `(size − 1)/8 + 1` per axis, and wrap each pass in a debug label ([labels](../../docs/rendering_device.md#labels)).
- With MSAA, `get_color_layer(view, msaa)`, `get_msaa_3d()` and `get_texture_samples()` choose per-sample shader variants.

## Frame order and compositor hooks

Forward+ renders a frame in this order. The order of PRE_OPAQUE callbacks, `_pre_opaque_render` with `process_gi`, the opaque pass and POST_OPAQUE callbacks was checked at the tag.

1. `sdfgi_update` creates the SDFGI object when SDFGI is enabled, deletes it when disabled or reset, and otherwise calls its `update`. The caller was not in the files read.
2. `_render_scene` calls `_update_sdfgi`, which voxelizes each pending region and relights static lights when they need it.
3. For normal views, not reflection probes: `update_cascades`, `pre_process_gi` and `update_light`.
4. The depth pre-pass, writing normal-roughness when SSAO, SSIL, SSR, SDFGI, a normal map or a compositor effect needs it, then its MSAA resolve. In this branch `_post_prepass_render` runs SDFGI's probe update (`sdfgi_integrate` MODE_PROCESS). The branch runs only with the pre-pass on; `rendering/driver/depth_prepass/enable` defaults to true, and its `disable_for_vendors` list is read only by the Compatibility backend.
5. PRE_OPAQUE callbacks.
6. `_pre_opaque_render`: shadows, `store_probes` (SDFGI's SH to octahedral maps), `process_gi` (writes `rbgi/ambient` and `rbgi/reflection`), last-frame buffer allocation, depth downsample, SSAO, SSIL, SSR, light clustering and volumetric fog, in that order.
7. The render-pass uniform set is built, binding whatever exists at that moment under `rb_ssao/final`, `rbgi/ambient`, `rbgi/reflection`, `rb_ssil/final` and `rb_ssr`, or a default black texture.
8. The opaque draw, POST_OPAQUE callbacks, the sky, POST_SKY, PRE_TRANSPARENT, the alpha pass, POST_TRANSPARENT.
9. After the transparent pass the color buffer is copied into SSIL's last-frame texture, so SSIL always reads the previous frame's lit color.

| Value | Callback | Runs |
|---|---|---|
| 0 | PRE_OPAQUE | after the depth pre-pass and its resolves; before shadows, `store_probes`, `process_gi` and the opaque pass |
| 1 | POST_OPAQUE | after the opaque pass, before the sky |
| 2 | POST_SKY | after the sky; before back-buffer copies, subsurface scattering and the specular merge |
| 3 | PRE_TRANSPARENT | after the back buffers are created, before the alpha pass |
| 4 | POST_TRANSPARENT (the default) | after the alpha pass and the SSIL/SSR copy, before built-in post-processing |

| Flag (value) | Property | Effect |
|---|---|---|
| ACCESS_RESOLVED_COLOR (1) | `access_resolved_color` | resolves MSAA color before the callback; only with MSAA on |
| ACCESS_RESOLVED_DEPTH (2) | `access_resolved_depth` | resolves MSAA depth before the callback; only with MSAA on |
| NEEDS_MOTION_VECTORS (4) | `needs_motion_vectors` | computes motion vectors in the opaque pass and writes the velocity buffer |
| NEEDS_ROUGHNESS (8) | `needs_normal_roughness` | writes normal and roughness in the depth pre-pass; Forward+ only |
| NEEDS_SEPARATE_SPECULAR (16) | `needs_separate_specular` | writes specular to its own buffer and merges it after the effects; Forward+ only. The editor shows the property only for POST_SKY, but the flag follows the property for any callback |

The renderer checks each flag across all effects in the compositor. PRE_OPAQUE is the slot for a same-frame screen-space solve: this frame's depth and normals exist, and a result written there can still feed the opaque pass. Motion vectors are written during the opaque pass, so a PRE_OPAQUE callback cannot use this frame's velocity (inference from the flag's description).

## Buffers in a callback

`render_data.get_render_scene_buffers()` gives the `RenderSceneBuffersRD`:

- **Color:** `get_color_texture(msaa)` or `get_color_layer(view, msaa)`, RGBA16F, used as an `rgba16f` storage image. Forward+ has no albedo buffer.
- **Depth:** `get_depth_texture(msaa)` or `get_depth_layer(view, msaa)`; set `access_resolved_depth` with MSAA. Depth is reversed: 1 at the near plane, 0 at the far plane and the sky.
- **Velocity:** `get_velocity_texture(msaa)` or `get_velocity_layer(view, msaa)`, with `needs_motion_vectors`.
- **Normal and roughness:** `get_texture("forward_clustered", "normal_roughness")`, RGBA8_UNORM, with `needs_normal_roughness`. It holds the view-space normal packed with CryEngine's best-fit normal encoding (`encode24`) and stored as `n·0.5 + 0.5`; decode with `normalize(rgb·2 − 1)`. The class reference's `normal_roughness_compatibility` returns the same normal re-packed into `[0, 1]`, which must be undone too. Alpha is roughness times 127/255, flipped to `1 − value` for dynamic instances, so `a > 0.5` marks pixels of moving objects.
- **Separate specular:** `get_texture("forward_clustered", "specular")`, only with `needs_separate_specular`.
- **Sizes:** `get_internal_size()` is the 3D render size before upscaling; `get_target_size()`, `get_view_count()`, `get_render_target()` and `get_texture_samples()` give the rest.
- **Missing names:** `get_texture` on a missing name logs an error and returns an invalid RID, so check `has_texture` first.

**Camera.** `render_data.get_render_scene_data()` gives:
- `get_cam_transform()`, a centered transform under multiview.
- `get_cam_projection()`, which is `correction · jitter · projection`: the correction flips y for camera views and reverses z into `[0, 1]`, and the jitter is TAA's. Under multiview it is a combined projection.
- `get_view_projection(view)` and `get_view_eye_offset(view)` per view, with the same corrections, and `get_view_count()`.
- `get_uniform_buffer()`, the engine's scene UBO, declared in GLSL as `SceneDataBlock { SceneData data; SceneData prev_data; }` from `scene_data_inc.glsl`. Its layout changes between engine versions, so a copied struct must match the version in use.

**Position.** `inverse(get_cam_projection())·vec4((pixel + 0.5)/size·2 − 1, depth, 1)`, divided by `w`, gives the view-space point and matches the depth buffer exactly. Because the matrix includes the TAA jitter, reconstructed points move by the jitter every frame under TAA. `get_cam_transform()` takes the point to world space.

**Named textures.** Context names are the engine's `RB_SCOPE_*` defines and texture names its `RB_TEX_*` defines:

| Context | Texture names |
|---|---|
| `render_buffers` | `color`, `color_msaa`, `color_upscaled`, `color_subsampled`, `color_msaa_subsampled`, `depth`, `depth_msaa`, `depth_subsampled`, `depth_msaa_subsampled`, `velocity`, `velocity_msaa`, `blur_0`, `blur_1`, `back_color`, `back_depth` |
| `VRS` | `texture` |
| `forward_clustered` | `specular`, `specular_msaa`, `normal_roughness`, `normal_roughness_msaa`, `voxel_gi`, `voxel_gi_msaa` |
| `rbgi` | `ambient`, `reflection` |
| `sdfgi` | none; the volumes are custom data |
| `Fog` | not catalogued; used as custom data |
| `rb_ssao`, `rb_ssil`, `rb_ssr` | `final`, `ssr`, `mip_level` |
| `rb_sslf`, `rb_ssds`, `rb_smaa`, `mobile`, `sky_buffers` | not catalogued |

**What stays private.** SDFGI, the `rbgi` GI-buffers object, volumetric fog and the forward-clustered data are stored as render-buffer custom data, and `has_custom_data`, `set_custom_data` and `get_custom_data` are declared only in C++, with no script binding and no class-reference entry (checked at the tag). The SDFGI volumes and probe maps are RIDs made directly with `texture_create`, outside the named registry, so no script or compositor effect can reach them.

**The `rbgi` outputs.** `get_texture("rbgi", "ambient")` and `get_texture("rbgi", "reflection")` return the per-pixel GI result, SDFGI and VoxelGI combined by `gi.glsl`, as RGBA16F with sampling and storage usage. `process_gi` creates them and runs only when `render_gi` is true, so a PRE_OPAQUE callback sees the previous frame's values (nothing on the first frame) and POST_OPAQUE and later see this frame's. They are cleared when the GI half-resolution setting changes and reallocated when their context is cleared.

**Other formats.** SSIL's final texture is RGBA16F. SSAO's is R8 even though its interleave shader declares an `rgba8` image.

**Own textures.** `create_texture(context, name, format, usage, samples, size, layers, mipmaps, unique, discardable)` makes screen-sized textures that the engine frees with the buffers; `create_texture_from_format` and `create_texture_view` are bound too. Read them with `get_texture_slice(context, name, layer, mip, layers, mips)` after `has_texture` (`get_texture`, `get_texture_format`, `get_texture_slice_view` and `get_texture_slice_size` are bound too), call `clear_context(context)` when the size or settings change, and never free them by hand, which causes errors. Fixed-size data such as probe atlases is made with `texture_create` and freed by the effect.

**Multiple views.** Loop over `get_view_count()`, take per-view slices of own textures with `get_texture_slice(context, name, view, 0, 1, 1)`, and use `get_view_projection(view)` with `get_view_eye_offset(view)`; most published effects use one camera for every view ([projects](godot_projects.md#multiple-views)).

## World-space inputs

- **Geometry.** The engine exposes no mesh buffer RIDs. Triangles come from `mesh_surface_get_arrays()` on the CPU ([ray tracing notes](../../docs/rendering_device.md#ray-tracing)), or the scene is rasterized into an own structure without a geometry shader ([voxelization in Godot](scene_representation_and_tracing.md#voxelization-in-godot)).
- **Lights and materials** are collected from the scene tree by script. gomezzz reads `albedo_color`, `emission` and `emission_energy_multiplier` from each `BaseMaterial3D` and converts them to linear; Phreakyx averages textures through `Texture2D.get_image()`.
- **Sky.** `RenderingServer.environment_bake_panorama(environment, false, size)` returns an equirectangular image of the environment for rays that leave the scene; in a callback the environment is `render_data.get_environment()`.
- **VoxelGI data from script.** `RenderingServer.voxel_gi_allocate_data` takes a to-cell transform, an AABB, the octree size, octree cells, data cells, an optional distance field and level counts. The octree buffer must be a multiple of 32 bytes and the data buffer `(octree cells / 32) × 16` bytes; the byte layouts beyond those checks were not read. The data reaches shading through `rbgi`, so the gating below applies. It feeds the engine's VoxelGI, not a custom solver.

## Getting GI into shading

The opaque shader (`scene_forward_clustered.glsl`) builds `ambient_light` in this order:

1. Start at zero and take the environment color (`scene_data.ambient_light_color_energy`) or the sky radiance cubemap.
2. Mix in material `IRRADIANCE`, `mix(ambient, IRRADIANCE.rgb, IRRADIANCE.a)`, when the material writes it.
3. Add lightmap and lightmap-capture terms.
4. On transparent surfaces, per-fragment SDFGI or VoxelGI replaces the value; opaque surfaces instead mix the `rbgi/ambient` buffer, `mix(ambient_light, buffer_ambient.rgb, buffer_ambient.a)`, when SDFGI or VoxelGI is active. Specular mixes `rbgi/reflection` the same way.
5. Reflection-probe ambient mixes in.
6. `ambient_light *= ao`, where `ao = min(material AO, SSAO)`.
7. `ambient_light *= albedo`.
8. SSIL, when the environment enables it: `ambient_light *= 1 − ssil.a; ambient_light += ssil.rgb·albedo`.
9. Energy compensation, then `·(1 − metallic)`, then the sum with emission, direct diffuse and specular; fog comes last.

The terms that land where diffuse GI belongs, multiplied by albedo, AO and `1 − metallic` and before fog, are `IRRADIANCE` and SSIL. The SSIL gating and composite lines were checked at the tag.

| Entry point | Works? | Why |
|---|---|---|
| Material `IRRADIANCE` | yes, per material | Mixed in before AO, albedo and `1 − metallic`, so the composite is correct. Every opaque material must be a `ShaderMaterial` that writes it; it can read a screen-sized texture through a global uniform at `SCREEN_UV` |
| Material `EMISSION` | yes, with care | Skips AO and the metallic factor unless the shader applies them; gomezzz writes `albedo·irradiance·(1 − metallic)` |
| `rbgi/ambient` written at PRE_OPAQUE | no | The opaque shader reads it only when SDFGI or VoxelGI is active, and `process_gi` then overwrites it after PRE_OPAQUE |
| `rb_ssil/final` written at PRE_OPAQUE | no | Read only when the environment enables SSIL, and then `using_ssil` is true whatever the pre-pass setting, so the built-in SSIL overwrites it. If an effect creates the texture first, the engine reuses it without checking its format |
| Compute on the color buffer after the opaque pass | partly | Adds light after shading, but with no albedo buffer the GI cannot be multiplied by albedo |

The gating behind the `rbgi` row: the buffer blend runs only for instances with `USE_GI_BUFFERS` and with `sc_use_forward_gi` off. `USE_GI_BUFFERS` is set only when opaque GI is in use, which needs an enabled SDFGI environment with a debug mode other than unshaded, or at least one VoxelGI instance. Opaque surfaces start with `uses_forward_gi = 0`, and alpha surfaces with GI set it to 1. `process_gi` writes every pixel it dispatches, no callback runs between it and the opaque draw, and with neither SDFGI nor VoxelGI active the opaque shader does not read the buffers, so the `rbgi` textures cannot carry custom GI into the opaque pass. The opaque pass binds `rbgi/ambient` and `rbgi/reflection` at bindings 28 and 29 (default black when missing, absent for reflection probes), SDFGI's probe map and occlusion texture at 30 and 31, and the VoxelGI buffer at 32. SSAO runs only with the pre-pass on, but its shader flag comes from the environment alone, so with the pre-pass off and SSAO on the shader reads whatever `rb_ssao/final` holds (untested).

**`IRRADIANCE` and `RADIANCE`.** The spatial shader reference describes both outputs as blends with the environment map: written on any branch, they blend environment irradiance (or radiance) with `.rgb` by `.a`. The compiler renames them `custom_irradiance` and `custom_radiance`, sets `CUSTOM_IRRADIANCE_USED` and `CUSTOM_RADIANCE_USED` when they appear, and the scene shader blends them into ambient and specular. The hook is per material and touches no scene-wide buffer.

The path that composes correctly:

1. Write a screen-sized RGBA16F irradiance texture in a PRE_OPAQUE callback (screen-space probes), or a probe atlas from any callback (world-space probes).
2. Wrap it in a `Texture2DRD` and assign it to a global `sampler2D` shader parameter. The material storage resolves the `Texture2DRD` to its RD texture, which must be 2D, depth 1, single-layer, created with `TEXTURE_USAGE_SAMPLING_BIT` ([Texture2DRD](../../docs/rendering_device.md#texture2drd)), and in a format that maps to an `Image` format. Changing the global value re-queues every material that uses it.
3. In every opaque `ShaderMaterial`, sample it at `SCREEN_UV`, or at the world position and normal for a probe atlas, and write `IRRADIANCE = vec4(value, 1.0)`.

`IRRADIANCE` replaces the environment ambient, which is a constant color or the most blurred mip of the sky radiance map, both approximating cosine-weighted average radiance. So the value to write is `E/π`, which for equal-solid-angle bins is `Σ L·cos/Σ cos` ([normalization](3d_screen_space.md#final-gather)), not irradiance `E`. With `IRRADIANCE.a = 1` the environment ambient is gone, so the RC sky term has to supply sky light. SSAO still multiplies the result on top of the occlusion RC already contains, SSIL adds to it when enabled, and reflection probes with an ambient mode mix in after it. A texture read at `SCREEN_UV` describes the opaque surface at that pixel, so transparent materials need a world-space lookup.

**Writing light after shading.** The compositor projects use three methods ([projects](godot_projects.md#compositor-effect-projects)):
- A compute store reads color, adds or multiplies, and stores. It changes the whole lit color, specular included, and at POST_TRANSPARENT transparent surfaces too.
- A full-screen raster pass with a multiply blend, for AO.
- A dual-source blend: output 0 is added light and output 1 per-channel transmittance, and with source factor ONE and destination factor SRC1_COLOR the result is `added + destination·transmittance` in one pass. The aerial-perspective effect runs it at PRE_TRANSPARENT so transparent surfaces add their own haze.

None of the three has albedo. The SSRT effect computes `(color + color·gi)·(1 − occlusion)`, which uses the lit color as albedo, so unlit surfaces get no bounce; Phreakyx guesses albedo from the lit color ([Phreakyx](godot_projects.md#phreakyx-voxel-cone-rc-as-a-gdextension)).

## SDFGI, the shipped GI

SDFGI keeps up to eight cascades of 128³ voxel volumes (distance field, light, anisotropic light) and one 17³ probe grid per cascade. Static geometry is voxelized when a cascade window moves, and probe rays are traced through the distance field every frame. Per pixel, `gi.glsl` writes ambient and reflection color into `rbgi`, which the opaque shader reads.

**What the docs and blog say.** The June 2020 blog post, marked as possibly outdated, says SDFGI needs no unwrapping and no ray-tracing hardware, that static meshes contribute light and dynamic meshes only receive it, that light changes are real time, that emissive surfaces contribute, and that it is "mostly leak free" while walls are thicker than one voxel of the cascade that renders them; its "How does it work?" section promises an article and gives no design. The current docs add:
- SDFGI is Forward+ only and follows the camera; there is no extent to set.
- It supports dynamic lights but not dynamic occluders or dynamic emissive surfaces. Static meshes contribute; Disabled and Dynamic meshes only receive. Static lights are baked in, and Dynamic lights (the default) contribute in real time.
- The distance field is recomputed only when the camera moves into or out of a cascade, so a nearby static object that moves stays wrong until the camera moves away.
- Sharp reflections appear only on opaque materials, and indirect light takes about 30 frames to converge by default.

**Settings.**

| Environment property | Default | Range or note |
|---|---|---|
| `sdfgi_enabled` | false | |
| `sdfgi_cascades` | 4 | 1 to 8 |
| `sdfgi_min_cell_size` | 0.2 | 0.01 to 64 |
| `sdfgi_y_scale` | 75% | 50%, 75%, 100% |
| `sdfgi_use_occlusion` | false | |
| `sdfgi_bounce_feedback` | 0.5 | |
| `sdfgi_read_sky_light` | true | |
| `sdfgi_energy` | 1.0 | |
| `sdfgi_normal_bias` | 1.1 | |
| `sdfgi_probe_bias` | 1.1 | |

Project settings: `probe_ray_count` from {4, 8, 16, 32, 64, 96, 128}, default 16; `frames_to_converge` from {5, 10, 15, 20, 25, 30}, default 30; `frames_to_update_lights` from {1, 2, 4, 8, 16}, default 4. `get_sdfgi_max_distance()` returns `min_cell_size × 64 × 2^cascades` and `get_sdfgi_cascade0_distance()` returns `min_cell_size × 64`.

**Cascade geometry.** At most 8 cascades of 128 cells per axis. `PROBE_DIVISOR` is 16, so probes sit 8 cells apart, 17 per axis including both ends, 4,913 per cascade. Each probe has a 6×6 octahedral tile plus a one-texel border (8×8 stride) and 16 rows of SH coefficients. There are 128 dynamic and 1,024 static light slots, and the solid-cell list holds a quarter of a cascade's voxels. Cascade `i` has cell size `min_cell_size·2^i` and covers `position ± 64` cells per axis. World y is multiplied by 2.0, 1.5 or 1.0 (for 50%, 75% or 100% y scale) before indexing. With the defaults, cells are 0.2, 0.4, 0.8 and 1.6 m, extents 25.6, 51.2, 102.4 and 204.8 m (the last equal to `get_sdfgi_max_distance()`), vertical extents at 75% are 17.1, 34.1, 68.3 and 136.5 m, and cascade 0's probes are 1.6 m apart (derived).

**Textures.** Per cascade, at 128³:

| Texture | Format | MiB (derived) |
|---|---|---|
| `sdf_tex` | R8_UNORM 3D, sampled and storage | 2 |
| `light_data` / `light_tex` | R32_UINT stored, E5B9G9R9_UFLOAT view (RGBE) | 8 |
| `light_aniso_0_tex` | R8G8B8A8_UNORM | 8 |
| `light_aniso_1_tex` | R8G8_UNORM | 4 |
| `lightprobe_history_tex` | R16G16B16A16_SINT, 289×272, one layer per history frame | 0.6 per layer |
| `lightprobe_average_tex` | R32G32B32A32_SINT, 289×272 | 1.2 |
| `solid_cell_buffer`, `solid_cell_dispatch_buffer_*`, `lights_buffer` | storage and indirect-dispatch buffers | |

The 289×272 layout is 17×17 probes across by 17 slices of 16 SH rows, 128 bytes per probe per history layer (derived). Shared by all cascades: `lightprobe_data` (R32_UINT with an E5B9G9R9 view, 2312×136 per layer, which is 289×8 by 17×8, with two layers per cascade for the diffuse and specular octahedral maps; specular is read at a layer offset of `max_cascades`), `occlusion_data` (R16_UINT stored with an R4G4B4A4_UNORM view, width 256, depth 128 × cascades), `ambient_texture` (RGBA16F 2D array, 289×17, one layer per cascade, read by volumetric fog) and the `lightprobe_history_scroll` and `lightprobe_average_scroll` textures. Scratch textures for voxelization, at 128³ unless noted: `render_albedo` R16_UINT, `render_emission` and `render_emission_aniso` R32_UINT, eight `render_occlusion` R8_UNORM, `render_geom_facing` R32_UINT, two `render_sdf` R8G8B8A8_UINT for the jump-flood ping-pong, and two `render_sdf_half` R8G8B8A8_UINT at 64³.

With the default four cascades this adds up to 88 MiB of cascade volumes, 9.6 MiB of probe maps, 4.8 MiB of probe averages and 62 MiB of scratch, about 164 MiB before the history layers, the occlusion texture and the buffers (derived).

**Encodings.**
- An albedo voxel (R16_UINT) has the solid flag in bit 0 and 5-bit red, green and blue at bits 11, 6 and 1.
- A distance texel stores `(1 + distance in cells)/255` for empty cells and 0 for solid ones, read back as `texel·255 − 1`.
- Occlusion is eight 4-bit values per cell split over two 16-bit stores.
- Light is RGBE 9-9-9-5 through the E5B9G9R9 view.

**Voxelization.** `_update_sdfgi` calls `render_region` for each pending region, and `_render_sdfgi` makes three orthographic passes over the region, one per axis, drawing the scene in `PASS_MODE_SDF`. That scene-shader variant stores albedo, ORs facing bits with `imageAtomicOr` and stores emission into the 3D images. Only Static meshes take part.

**Scrolling.** `SDFGI::update` runs every frame. A cascade moves when the camera's cell leaves a 4-cell `drag_margin` around its center, and each move shifts it by 8 cells, one probe spacing. The uncovered slab becomes a dirty region; a shift of 128 cells or more, or a dirty share above half the safe volume, marks the whole cascade dirty. `get_pending_region_data` turns dirty slabs into regions to voxelize, a scroll pass moves the existing voxel data, and the integrate shader's scroll modes move the probe data.

**Shaders** (all in `servers/rendering/renderer_rd/shaders/environment/`, none with header comments; roles from entry points and mode defines):

| Shader | Modes | Role |
|---|---|---|
| `sdfgi_preprocess.glsl` | SCROLL, SCROLL_OCCLUSION | move voxel albedo, facing, light and occlusion when a cascade scrolls |
| | INITIALIZE_JUMP_FLOOD (and _HALF), JUMPFLOOD, JUMPFLOOD_OPTIMIZED, UPSCALE_JUMP_FLOOD | seed the jump flood with solid voxels, run it at half resolution, upscale |
| | OCCLUSION | per-cell occlusion in eight directions |
| | STORE | write the distance field, the occlusion texture and the solid-voxel list |
| `sdfgi_direct_light.glsl` | PROCESS_STATIC, PROCESS_DYNAMIC | march each light toward each voxel through the distance field and write light and anisotropic light; the dynamic mode adds the bounce term from the probe texture |
| `sdfgi_integrate.glsl` | PROCESS | per probe, trace Vogel-distributed rays through the distance field, add sky light and light lookups, store SH into the history |
| | STORE | SH to octahedral maps in `lightprobe_texture` |
| | SCROLL, SCROLL_STORE | shift probe history and averages when a cascade moves, then write the shifted maps |
| `sdfgi_debug.glsl`, `sdfgi_debug_probes.glsl` | debug color, light, emission; probe and visibility spheres | debug only |
| `gi.glsl` | VOXEL_GI, SDFGI, COMBINED and no-sampler variants | per pixel, sample SDFGI probes and VoxelGI and write the ambient and reflection buffers |

**Comments that disagree with the code.** `gi.cpp` says the distance field is "Always 64x64" but uses `cascade_size`, 128. `gi.h` calls albedo and emission "half size", but they are made at full cascade size. `num_cascades = 6` in `gi.h` is always overwritten from the environment. `probe_half_size` is computed and then set to zero, so the drag test has no offset. The `SolidCell` struct is unused and only documents a size.

**Ray budget.** At the defaults SDFGI traces 4 × 4,913 × 16 = 314,432 probe rays per frame and averages each probe over 30 frames, about 480 rays per probe in its history (derived).

## Volumetric fog

Godot's volumetric fog is a froxel grid computed in `_pre_opaque_render` after `process_gi`, so it reads this frame's GI ([fog](../sources/2026_godot_gi_internals.md#e-volumetric-fog)). The grid formula, slice distribution, defaults, that call order and the fog shader's GI reads were checked twice at the tag; the rest of this section rests on one read.

- **Grid.** `volume_size` and `volume_depth` default to 64 and `use_filter` to 1 (filtering on), corrected for aspect as width `size·w/((w + h)/2)` and height `size·(w + h)/2/w`: 81 × 50 × 64 at 1920×1080 (derived). Slice `z` sits at `length·((z + 0.5)/depth)^detail_spread`, with length 64 m and spread 2.0 by default, so the middle slice is about 16.5 m away (derived).
- **Volumes.** In-scattered light and density, its previous-frame copy and the integrated result are RGBA16F 3D textures, about 2 MiB each at 1080p; FogVolume density, light and emission accumulate in R32_UINT 3D images with atomics, or 4-byte storage buffers without image atomics (sizes derived).
- **Passes.** FogVolume materials write the accumulators; a density pass in 4×4×4 groups computes direct light, ambient, GI and the temporal blend per froxel; an optional copy and a separable 7-tap Gaussian follow; an integrate pass in 8×8×1 groups accumulates front to back with Beer-Lambert ([media](supporting_techniques.md#light-transport-and-solver-math)).
- **Temporal reprojection** is on by default at 0.9 (range 0.5 to 0.99). It blends each froxel's in-scattered light and density with last frame's, not the integrated fog, and jitters froxel centers by a 16-entry Halton sequence when reprojection succeeds.
- **GI in fog.** `gi_inject` defaults to 1.0 and, by the docs, scales GI in the fog albedo. With SDFGI on, each froxel trilinearly weights 8 probes of the first cascade that contains it, reading SDFGI's `ambient_texture` (one RGBA16F texel per probe) and, with occlusion on, its occlusion texture. Up to 8 VoxelGI instances are composited front to back through all mips, scaled by `dynamic_range·gi_inject·exposure_normalization`, and the instance count is zero unless `gi_inject > 0.001`. `ambient_inject` defaults to 0, so sky and ambient light reach fog only when it is raised; the CPU multiplies that term by the ambient light energy.
- **Access.** The fog volumes are custom data under the `Fog` scope, registered under no texture name, and `VolumetricFog` binds no methods. Scripts reach fog only through FogVolume shaders, which write density, albedo and emission, not light.

So a custom GI can light Godot's fog only by emission through a FogVolume shader, which the fog then integrates as its own light, or by its own froxel pass composited after shading (inference). Fog's default blend of 0.9 is a ten-frame average (derived), so the engine's fog is temporal even when the GI feeding it is not.

## The SDFGI plan

Linietsky's undated 48-page deck, "Godot SDFGI plan for 4.1", is the design behind SDFGI and the redesign that became HDDAGI ([deck](../sources/2023_linietsky_godot_sdfgi_plan.md)). Shipped code differs in places.

**Requirements.**
- No per-scene or per-object setup: no distance fields, cards or lightmaps to author, ideally one switch.
- Real time, or at least fast updates, with few leaks.
- Diffuse and reflected light, light on transparent objects, and light for volumetric fog.
- Any Vulkan GPU, integrated ones included, and VR, so nothing may depend on TAA.

Accepted losses: no high-frequency GI (screen-space effects fill it in), dynamic objects receive light but add none, cascades are required, and small emitters look spotty with few samples.

**Structure.**
- Built on DDGI ([related probe GI](related_probe_gi.md)): per cascade 17³ probes over a 128³ distance field, up to 8 cascades. Irradiance probes are 5×5 octahedral tiles, one 25-thread workgroup each. Occlusion probes are 16×16 octahedral depth maps used with a Chebyshev test after pushing the point along the geometric normal.
- Geometry is rasterized into an empty framebuffer at 4× the cascade resolution per axis (512² for 128³), writing a 4³ bitfield per cell with `imageAtomicOr`, 16 MB per cascade. Albedo and emission are reduced with subgroup operations into 64³ grids.
- The jump flood is seeded from the sub-voxel bits, which gives distances finer than one cell. Occlusion rays whose distance-field value is under the probe range walk the bitfield with a DDA for an exact hit.
- Lighting runs over a list of empty cells next to solid ones, built when the distance field is stored, with a normal, an outline bitmask and an indirect dispatch count. Each entry sums lights with sphere-traced shadows plus indirect light from nearby probes and writes RGBE 9-9-9-5. The outline bits also write light into neighbouring cells, so the short step back after a sphere-traced hit lands on lit data.

**Probe tracing.** One workgroup per probe traces one jittered ray per tile texel, from the probe's cascade into coarser ones. A hit reads albedo and emission, takes a normal from the distance field and steps back until it finds a lit cell. After a barrier, shared memory averages the 25 results over each texel's hemisphere and blends them into history by a fixed fraction. Rays need no start bias, because the occlusion probe's depth already moves the start outward.

**Making it fast.**
- **Scrolling:** only the uncovered slab is rerendered when the camera passes the probe nearest the center. Keeping the jump flood's final pointers lets old and new regions merge by comparing each cell's pointer with its neighbour's across the seam. Occlusion probes on the seam retrace only the directions toward the new region, and the light texture scrolls with its new part marked dirty. The camera moves along one axis at a time in practice, so one side per update suffices.
- **Hit caching:** with static geometry each ray's hit (cascade, light-texture cell, normal) can be stored. A cached hit stays valid through a scroll if it stays in the same cascade, or if the ray leaves through the same face of an upper cascade.
- **Light on demand:** ray hits set bits in a coarse dirty volume, and only marked regions are relit the next frame, one frame late. Static lights go into a separate texture computed once.
- **Frustum:** probes far outside the view update every few frames, which slows more than half of them with a centered camera.

**Reflections.** Sharp reflections trace from each pixel's reconstructed position, and tracing two cascades together and blending by the nearer hit stops pops at cascade switches. Medium roughness reads a less blurred copy of the probes saved before the hemisphere average, and full roughness the irradiance probes. Each pixel blends two of the three by roughness.

**Dynamic objects (planned).**
- Each moving object gets its own distance field from a jump flood, built on demand. Writing all objects into every cell costs cells × objects, so cascades split into 8³ macro regions of 16³ cells, each with a bit list of overlapping objects built by one compute thread per cell with atomic OR, and a 64-byte empty-cell mask so the DDA skips empty space.
- They are lit through a card atlas: six axis views per object (albedo, normal, emission, depth) at about one pixel per voxel, lit in compute with shadows from the static cascades, and read where a card's depth meets a cell.
- Static hits stay cached, and a dynamic ray retraces only up to its cached static hit, reading dynamic light if something intercepts it first.
- The author of HDDAGI's 2026 screen-probe draft names this plan, and Lumen's per-object surface caching, as a possible route for moving geometry instead of frequent revoxelization; no work on it had started.

## HDDAGI

HDDAGI (hierarchical DDA GI) is reduz's replacement for SDFGI: voxel cascades traced with an integer hierarchical DDA instead of a distance field, feeding DDGI-like world probes ([notes](../sources/2026_godot_hddagi_dynamic_gi.md)). Its voxel cascades and DDA are described in [scene representation](scene_representation_and_tracing.md#hddagis-voxel-cascades). Three pull requests carry it, and none is merged:

| Pull request | Author | State |
|---|---|---|
| [#86267](https://github.com/godotengine/godot/pull/86267) | reduz | open draft since 2023-12, branch head 2024-07-11; 77 files, +8145/−6151; it replaced #86007, closed unmerged |
| [#119869](https://github.com/godotengine/godot/pull/119869) | OrangeeZ | rebase onto current Godot with reviewers' changes, open since 2026-05 |
| [#122999](https://github.com/godotengine/godot/pull/122999) | maidopi-usagi | screen-probe draft since 2026-08 |

**Status.**
- #86267 was reviewed in 2024. clayjohn measured a small overall gain and a large drop in probe cost, and the rendering meeting agreed to rename it `dynamic_gi`. The thread was locked in 2024-12, with the timeline depending on reduz's time. A null dereference in `process_gi` (reading `hddagi` members when only VoxelGI exists) and leaked RIDs were still in the head.
- High-density probes and dynamic objects were left for after merging; only static meshes are voxelized.
- #119869's open problems: wrong probe occlusion on D3D12, compute-pipeline error spam on RADV and macOS, brightness jumps at 50% and 70% cascade height, and 13 leaked "HDDAGI Voxel Disocclusion" textures.
- No maintainer has stated a merge decision. Calinou suggested an optional screen-space GI pass as the best fix for leaks.
- If it lands, it still writes the engine's private GI buffers, so it changes none of the entry points above.

**Lighting the voxels.**
- Static lights are injected once per region update and dynamic lights every frame or every 2, 4, 8 or 16 frames, spread over the process list; up to 1,024 static and 128 dynamic lights per cascade.
- Shadows are HDDA shadow rays from each cell toward each light, not shadow maps.
- Bounce: each lit cell adds `albedo · bounce_feedback` times the irradiance of its 8 surrounding probes from the previous update, weighted by its stored occlusion nibbles.
- The sky is never injected; probe rays that miss read the sky cubemap at mip 2, or the clear color.

**Probes.**
- One probe per 8 cells, so a default cascade has 17 × 9 × 17 = 2,601 probes. Each is a 5×5 octahedral tile (7×7 with a border), one thread and one ray per texel, 25 rays per update, jittered per frame. A full update of four cascades is 260,100 rays (derived).
- Rays start at the probe, pushed forward by `probe_bias`. Each result is splatted bilinearly into up to 4 octahedral texels with 14-bit fixed-point integer atomics.
- A hit cache stores the hit cell, cascade and axis per texel and history slot, so unchanged hits are reused. An entry is dropped when its region's version changes or the cascade moved along its axis.
- History is a moving average over `frames_to_converge` slots. In #119869 the default is 6, 150 rays per probe in history (derived); Calinou found 32 (800 rays) removes most flicker and suggested 18 to 24.
- Diffuse is a fixed weighted sum of neighbouring octahedral texels; specular reads the averaged texel.
- Probes near geometry update when their region is visible; probes in revoxelized regions within 1, 2, 4 or 8 frames; others every `inactive_update_frames`, staggered by the parity of their world position.
- Newly uncovered probes are seeded from the next coarser cascade with occlusion-weighted trilinear weights; the top cascade starts at zero.
- An optional filter averages each visible probe near geometry with its 6 axis neighbours at weight `0.7 · visibility`.

**Occlusion and leaks.**
- Occlusion between cells and their 8 surrounding probes is found by a wavefront from each probe corner across its 8³ block (22 steps), with solid-cell bias and back-face darkening, stored as 4-bit weights.
- In reduz's account, walls one voxel thick are sealed in the voxels, but the normal-based bias that moves lookups out of solid cells does not clear the outside probe's reach at corners. The proposed fixes were thicker walls, denser probes, or a depth- and normal-aware blur sized to one voxel on screen.
- In #122999 the leaks at the default 0.2 cell size were gone at 0.03 with 5 cascades, or with the cascades pushed 0.3 forward of the camera; the cause given is voxels jumping to the third cascade at short range ([leaks](artifacts_and_fixes.md#light-leaks)).
- Other reported problems: dark splotches that need an occlusion bias, artifacts on normal-mapped terrain and curved or overlapping geometry ("the main problem with DDGI", in reduz's words), visible cascade shifts while moving, light popping and blocky reflections.

**Reaching the pixels.** `process_gi` runs one compute dispatch per view at internal resolution, or half resolution (the default in #119869), reading depth and normal-roughness and writing RGBE ambient and reflection images plus a blend image. Reflections get an optional separable bilateral filter of radius 12 (6 at half resolution), weighted by depth, `pow(n·n', 4)` and roughness, skipped at roughness 0.3 and above.

**Cost.** With a static camera on a GTX 1650, light update and probe tracing cost 2.43 ms under SDFGI and 0.93 ms under HDDAGI, 2.6 times less (#86267; ratio derived). The official GI demo at 3840×2160 ran at 120 FPS on an RTX 3080 with #122999's changes, untuned. No memory figures are given; the texture formulas are in `gi.cpp`.

### Screen probes in #122999

The draft adds Lumen-style screen probes that trace through Hi-Z first and then the voxel cascades. Its author calls it a heuristic mix inspired by kajiya and Lumen, too large to merge as one change.

- **Placement:** one probe per tile of `probe_size` GI texels, at the valid pixel nearest the tile center, optionally jittered by an 8-sample Hammersley sequence per frame. Each probe stores its screen position, depth and packed normal with a dynamic-object flag.
- **Stochastic Integrated mode:** 1 to 8 cosine-weighted rays per probe per frame, optionally guided by 8 bins (2 radial × 4 azimuthal) weighted by `sqrt(luminance)` of the nearest HDDAGI probe and mixed 50/50 with uniform. Pixels gather 3×3 probes weighted by `pow(n·n', 6)`, depth and distance. It is better at detail and corners.
- **Directional Gather mode:** 64 rays per probe per frame into an 8×8 octahedral tile, one per texel with R2 jitter, radiance clamped to 10. With guiding on, a valid history and a static receiver, directions are sorted by a pdf built from the BRDF and last frame's radiance, and grouped as one high-pdf direction with three low-pdf ones. Where the low ones fall under 0.1 and the high one does not, the high direction splits into four 16×16 children traced in the low ones' ray slots, and the low ones reuse last frame's radiance; one frame in four skips the split so the low directions refresh. Pixels gather 2×2 probes bilinearly with a plane-distance test and read a per-normal irradiance table (the 64 directions summed with `max(n·ω, 0)` and scaled by `4/64`). It runs 20 to 40% faster than the stochastic mode and handles a bright small sun better.
- **Adaptive probes:** each tile has 8 jittered candidate positions. A candidate becomes a probe when the base probes cover it with weight under 0.01 and is retired once coverage rises above 0.06, up to 8 per tile, from a pool of half the base probe count that the author says fills easily.
- **History:** per direction `mix(previous, current, w)` with `w = 1/(age + 1)` and age capped at 7 (a steady 1/8), or 0.5 for dynamic receivers. Reprojection uses unjittered projections, plus velocity for dynamic receivers. A spatial pass blends each probe with its 4 neighbours by distance, plane and endpoint angle.
- **SVGF:** temporal accumulation with depth, normal and plane tests, then an [à-trous](supporting_techniques.md#denoising-upscaling-and-temporal-reuse) filter driven by luminance variance. NVIDIA NRD was removed.
- **Detail trace:** before the voxel DDA, a Hi-Z march (2×2 max-depth pyramid, 48, 32 or 16 iterations) out to 2 units for diffuse and 50 for specular. A hit reads the lit screen color, so visible dynamic objects occlude and bounce light. It costs extra on low-end GPUs, and probe jitter alone handles corners without it.
- **Irradiance cache:** first-order `[1, n]` moments per entry with a 16-sample history. It flickers and is left off.
- **Problems:** noisy and laggy screen-probe reflections, unstable light in hard-to-sample spots, and pixelated dark areas near corners and thin plates from over-occluding coarse voxels.
- **Dynamic objects** were prototyped in a fork with an object-level voxel cache at about 20% overhead; they flickered and leaked light from distant dynamic emitters. In maidopi-usagi's words (2026-09-08), rigid mesh instances with an "object level cache" toggle keep their own voxel cache, traced between the screen trace and the global trace, with extra storage. Their `dynamic_gi_hw` branch (34 commits ahead of master) has commits adding object-local caches for rigid geometry and `hddagi_rigid*` files; that it is the measured prototype is inferred from names and dates. David-Zuloyan reports dynamic objects on #119869 as "heavy", with no figure (fork branches `hddagi-4.7` and `pr-119869`).

## Connections

- **The engine's GI is a nested probe grid with fixed angular resolution.** SDFGI and HDDAGI keep the same probe count and the same 16 or 25 rays per probe in every cascade, and their rays run to the first hit. In RC terms each cascade is a cascade-0 grid at a coarser spacing, with no angular growth and no interval split: the "regular or nested grid of radiance probes" that Sannikov says 3D RC improves on in nearly every measure ([history](history_and_landscape.md)). Far light is resolved at the same angle as near light, and the temporal average over 6 to 30 frames is what makes 16 to 25 rays per probe enough (inference).
- **Ray budgets.** SDFGI traces about 0.31 M probe rays per frame and HDDAGI about 0.26 M per full update; gomezzz's single-frame cascades trace 2.34 M segments per update over a 12×8×12 m volume ([gomezzz](godot_projects.md#derived-points)), about 7.5 times SDFGI's per-frame count. Single-frame RC replaces the engine's history with rays (derived).
- **Hit caching is a scene cache.** SDFGI's planned and HDDAGI's working hit caches store where a ray lands, and the lit value at that cell is read fresh each frame. That keeps them compatible with single-frame GI under the rule that geometry caches are allowed and lighting caches are not ([single-frame assessment](scene_representation_and_tracing.md#single-frame-assessment)). For a world-space RC grid with static geometry, each probe texel's interval hit is fixed; caching it turns the trace into a lookup, and a scroll by whole probe steps shifts the cache (inference). Light on demand is the opposite: it caches lighting and adds a frame of latency.
- **The composite is fixed by the engine.** The only correct per-pixel entry is per-material `IRRADIANCE`, which forces every opaque material to be a `ShaderMaterial`. gomezzz installs and restores materials for this; Phreakyx avoids it at the cost of guessing albedo. Either is a cost every Godot RC carries (inference).
- **`IRRADIANCE` takes `E/π`,** which is exactly the cosine-weighted average that gomezzz's resolve and the screen-space codes compute ([normalization](3d_screen_space.md#final-gather)).
- **Lit color is a frame late.** At PRE_OPAQUE this frame's depth and normals exist but its lit color does not, so screen-space hits that read color, as Godot's SSIL and HDDAGI's Hi-Z detail trace do, see the previous frame ([radiance at the hit](scene_representation_and_tracing.md#radiance-at-the-hit-from-the-lit-frame)) (inference).
- **HDDAGI's leaks are the probe-interpolation leaks RC's world-space merge has.** Its corner leaks come from 8-probe interpolation reaching through walls that the voxels seal, the failure world-space RC fights with visibility-tested merges ([leak defences](3d_world_space.md#leak-defences-in-world-space)) (inference).
- **Directional Gather is ray splitting by importance.** Splitting a high-pdf direction into four children is RC's ×4 angular branching, driven by last frame's pdf instead of by distance ([ray splitting](3d_world_space.md#ray-splitting)) (inference).
- **reduz's plan is the hybrid the screen-space work arrived at.** World-space GI for low-frequency light plus a screen-space layer for detail and occlusion ([history](history_and_landscape.md), [screen space](3d_screen_space.md)) is what #122999 builds: a Hi-Z trace up to 2 units, then the voxel cascades.
- **SDFGI voxelizes without a geometry shader** by three orthographic raster passes, the route the engine itself takes under the same `RenderingDevice` limits ([voxelization in Godot](scene_representation_and_tracing.md#voxelization-in-godot)).

## Single-frame assessment

- **The API allows a full solve per frame.** Screen-space RC can run at PRE_OPAQUE on this frame's depth and normals, world-space RC from either hook, and the result reaches the opaque pass through `IRRADIANCE` in the same frame. Whether a `call_on_render_thread` update queued in `_process` runs before that frame's opaque pass was not checked.
- **Nothing in the engine's GI is single-frame.** SDFGI converges over 30 frames, HDDAGI over 6 to 32, and the screen-probe draft blends at 1/8 and adds SVGF. Their value here is as `RenderingDevice` code by the engine's own authors: integer DDA over voxel bit masks, wrapped cascade addressing, fixed-point atomic splats, indirect dispatch over solid-cell lists, Hi-Z marching and screen-probe placement.
- **Godot's own requirements fit the goal.** The SDFGI plan rules out dependence on TAA, for VR, and asks for integrated GPUs and no per-scene setup. A single-frame RC needs no TAA by construction, but the integrated-GPU target limits the ray budget that replaces history (inference).
- **The engine adds occlusion on top.** With SSAO on, the opaque shader multiplies RC irradiance by `min(material AO, SSAO)`, darkening contact regions twice, so a pure RC setup turns SSAO and SSIL off (inference).
- **Jitter moves screen probes.** Under TAA, depth-reconstructed probe positions shift every frame by the jitter, so a single-frame screen-space solve placed from `get_cam_projection()` flickers with it; HDDAGI's draft reprojects with unjittered projections, and placement can use them too (inference).
- **Hit radiance needs a same-frame source.** Screen-space hits cannot read this frame's lit color before the opaque pass, so a single-frame design lights its hits from a world-space structure lit this frame, or by evaluating direct light at each hit, as gomezzz does for its point light (inference).

## Open questions

- Does a `call_on_render_thread` callable queued from `_process` run before that frame's scene render, so a world-space solve lands in the same frame?
- Does a `Texture3DRD` work as a `sampler3D` global shader parameter? It would give hardware trilinear probe lookups in place of a flattened 2D atlas with manual slice blending, as gomezzz uses.
- What is the cheapest same-frame radiance source for screen-space hits at PRE_OPAQUE: a direct-light-only pass, voxel light injection, or direct light evaluated at each hit?
- How should an RC integration handle users who enable SSAO, given that the opaque shader applies it to `IRRADIANCE` unconditionally?
- How much of SDFGI's or HDDAGI's per-frame time is tracing, and how much is upkeep (voxelization, light injection, scrolling)? That split would show how much of a Godot GI budget a single-frame RC can spend on rays.
- Can a FogVolume shader sample an RC probe texture through a global uniform and write it as emission, so the engine's fog carries RC light without engine changes? Its temporal blend would still apply unless reprojection is turned off.
