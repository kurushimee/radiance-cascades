# Godot CompositorEffect examples

| Repository | Godot | License | Last commit | Effect |
|---|---|---|---|---|
| https://github.com/godotengine/godot-demo-projects/tree/master/compute/post_shader | 4.7 | MIT | 2026-07 | official compute post-process demo, plus a template that injects GLSL |
| https://github.com/jebbyk/SSRT_GI_CompositorEffect | 4.6 | MIT | 2026-03 | screen-space ray-traced GI: trace, blur, mix |
| https://github.com/LoganKeenan55/ambient-occlusion | 4.7 | MIT | 2026-08 | SSAO, HBAO, SAO, GTAO in compute |
| https://github.com/KawaiiPrincess/Godot-HBAO | 4.x | MIT | 2026-06 | HBAO as raster passes, works on Mobile |
| https://github.com/GamesNotDeveloped/godot-forest-demo | 4.6 | CC-BY-4.0 | 2026-04 | sun shafts |
| https://github.com/itzMeerkat/Godot-RealisticEnvironments | 4.8 | MIT | 2026-10 | aerial perspective with dual-source blending |
| https://github.com/DevPoodle/compositor-effect-library | 4.6 | MIT | 2026-04 | path tracer over hard-coded spheres |

These are the public CompositorEffect projects that read depth or normals and write light or occlusion back. None feeds GI into the engine's lighting: every one edits the finished color layer. They show the working skeleton for a screen-space RC pass in Godot and several mistakes to avoid. Engine facts below were checked against the 4.7.2-stable source. See [2026_godot_gi_internals.md](2026_godot_gi_internals.md) for the callback order, flags, and texture names.

## Common skeleton

- **Setup:** compile the shader and create the pipeline on the render thread (`RenderingServer.call_on_render_thread` from `_init`), and free the shader in `NOTIFICATION_PREDELETE`. Freeing a shader frees its pipelines. The sun-shaft project compiles on the main thread inside `_init`, which works but is not where the device is meant to be used.
- **Callback:** `_render_callback(type, render_data)` returns early unless `type` matches. `get_render_scene_buffers()` (cast to `RenderSceneBuffersRD`), `get_internal_size()` (return on zero), then a loop over `get_view_count()`.
- **Buffers:** `get_color_layer(view)` as an `rgba16f` storage image, read and written in place; `get_depth_layer(view)` as a sampler or image; `get_texture("forward_clustered", "normal_roughness")` with `needs_normal_roughness = true`. With MSAA, `get_color_layer(view, msaa)`, `get_msaa_3d()` and `get_texture_samples()` choose per-sample shader variants.
- **Camera:** `render_data.get_render_scene_data()` gives `get_cam_projection()`, `get_cam_transform()`, `get_view_projection(view)`, and `get_uniform_buffer()` (the engine's scene UBO).
- **Uniform sets:** `UniformSetCacheRD.get_cache(shader, set, uniforms)` per view per frame. The cache drops sets when the viewport changes. Building sets with `uniform_set_create` and freeing them after each dispatch also works but costs more.
- **Push constants:** 16-byte blocks: `vec2 raster_size` plus a view index or padding; larger blocks pack matrices column by column.
- **Dispatch:** 8×8 groups, `(size − 1)/8 + 1` per axis. No project calls `barrier()`; the device inserts barriers since 4.3.
- **Labels:** wrap passes in `draw_command_begin_label` / `draw_command_end_label`.

## Normal and depth decoding

- The normal buffer holds the **view-space** normal, packed with CryEngine's best-fit normal encoding (`encode24`) and stored as `n·0.5 + 0.5`. Decode with `normalize(rgb·2 − 1)`. The class reference's `normal_roughness_compatibility` returns the same normal re-packed into `[0, 1]`, so undo that too.
- The alpha channel holds roughness scaled by `127/255`, flipped to `1 − value` for dynamic instances. `w > 0.5` therefore marks pixels of dynamic objects, a free signal for rejecting history on moving geometry.
- `get_cam_projection()` returns `correction · jitter · projection`, where the correction flips y (always true for camera views), reverses z, and remaps it to `[0, 1]`. Depth is 1 at the near plane and 0 at the far plane and sky. Reconstruct view space with `inverse(cam_projection) · vec4((pixel + 0.5)/size·2 − 1, depth, 1)` and divide by `w`. The matrix includes the TAA jitter.
- The engine scene UBO layout changes between versions, so a copied struct must match the engine's `scene_data_inc.glsl` for the version in use. The SSRT project's include warns about buffer-size errors after updates.

## Own textures

`RenderSceneBuffersRD.create_texture(context, name, format, usage, samples, size, layers, mipmaps, unique, discardable)` makes screen-sized textures that the engine frees with the buffers. Read them back with `get_texture_slice(context, name, layer, mip, layers, mips)`, check `has_texture` first, and call `clear_context(context)` when the size or settings change. Freeing these RIDs by hand causes errors. Textures with a fixed size, such as probe atlases, are created with `texture_create` and freed by the effect.

## Writing light back

- **Compute store:** read color, add or multiply, `imageStore`. This changes the whole lit color, including specular and, at POST_TRANSPARENT, transparent surfaces.
- **Multiply blend:** a fullscreen raster pass whose blend multiplies the destination by the source, for AO.
- **Dual-source blend:** output 0 is added light, output 1 is per-channel transmittance; with source factor ONE and destination factor SRC1_COLOR the result is `added + destination·transmittance` in one pass. The aerial perspective effect runs it at PRE_TRANSPARENT so transparent surfaces handle their own haze.
- The SSRT mix computes `(color + color·gi)·(1 − occlusion)`. Scaling the lit color stands in for albedo, so unlit surfaces receive no bounce light. A real diffuse GI composite needs albedo, which the compositor does not provide.
- For the sky, `RenderingServer.environment_bake_panorama(render_data.get_environment(), false, size)` returns an equirectangular image of the environment, usable for rays that leave the scene.

## Mistakes in these projects

- The SSRT depth helper builds NDC from the integer pixel coordinate without dividing by the size, so its linear depth is wrong; its ray start does divide, so the two disagree.
- Several projects sample at `pixel/size` without the half-texel offset.
- The SSRT settings UBO writes integers as floats and declares them `int` in GLSL; the author notes that `PackedInt32Array` did not convert as expected. Encode with `PackedByteArray.encode_s32` instead.
- The HBAO project's matrix UBO names a field `inv_proj` but fills it with the plain projection, never refreshes it after the first resize, and creates an R32F pass from an RGBA8 framebuffer format.
- The path tracer reassigns its uniform textures every frame, which rebuilds the uniform set every frame.
- Only one project handles more than one view correctly; the path tracer reads view 0 only.
