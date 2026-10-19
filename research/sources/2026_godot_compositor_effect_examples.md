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

## Contents

- [Common skeleton](#common-skeleton)
- [Normal and depth decoding](#normal-and-depth-decoding)
- [Own textures](#own-textures)
- [Writing light back](#writing-light-back)
- [Mistakes in these projects](#mistakes-in-these-projects)
- [The projects in detail](#the-projects-in-detail)
  - [post_shader (official demo)](#post_shader-official-demo)
  - [Ambient occlusion (LoganKeenan55)](#ambient-occlusion-logankeenan55)
  - [Sun shafts (godot-forest-demo)](#sun-shafts-godot-forest-demo)
  - [Aerial perspective (Godot-RealisticEnvironments)](#aerial-perspective-godot-realisticenvironments)
  - [Path tracer (compositor-effect-library)](#path-tracer-compositor-effect-library)
- [Multiple views in other effects](#multiple-views-in-other-effects)

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
- The path tracer reassigns its uniform textures every frame, which rebuilds the uniform set every frame (the helper's texture setter marks the set dirty on every assignment, even with the same RID).
- Only one project handles more than one view correctly; the path tracer reads view 0 only.

## The projects in detail

### post_shader (official demo)

Two effects at POST_TRANSPARENT. The grayscale effect compiles a fixed `.glsl` file once on the render thread. The template effect keeps user code in a `shader_code` export, marks the shader dirty under a mutex when it changes, substitutes the code at `#COMPUTE_CODE` and compiles it with `RDShaderSource`, reporting errors. The template binds the engine scene UBO (`SceneDataBlock { SceneData data; SceneData prev_data; }` from `godot/scene_data_inc.glsl`) at binding 0, the color layer as an `rgba16f` image at 1 and the depth layer through a nearest sampler at 2, with a 16-byte push constant (`raster_size`, view index, padding). Size comes from `get_internal_size()`, uniform sets from `UniformSetCacheRD`, and each view gets its own compute list with one dispatch. The sample code unprojects depth with the include's per-view `inv_projection_matrix_view[view]` and shows view-space position divided by 20.

### Ambient occlusion (LoganKeenan55)

Four AO shaders behind one GDScript effect at POST_TRANSPARENT, with the shipped scene set to GTAO (the script default is SSAO), radius 0.3 and three render modes (flat, AO only, composited). All shaders reconstruct view space from depth the same way. The AO target is R16F; a 4×4 RGBA8 noise texture holds random unit vectors as `v·0.5 + 0.5`. The AO pass and a 5×5 bilateral blur run in separate compute lists, relying on the device to order them, and the camera UBO and uniform sets are created and freed every frame.

| Shader | Method | Constants | Comment's cost (RTX 2070) |
|---|---|---|---|
| SSAO | 16 hemisphere offsets on a TBN from the noise vector; a sample is occluded when the stored surface is in front of it, weighted by `smoothstep(0, 1, radius/|dz|)` and `N·D`; `ao = (1 − occlusion)²` | radius from the export | about 0.80 ms |
| HBAO | after Scanberg's version of NVIDIA's HBAO: 8 directions rotated by noise, 6 steps, tracking the running horizon tangent and adding `(d²·(−1/R²) + 1)·(sin S − sin H)`; `ao = clamp(1 − 2·sum/8, 0, 1)` | intensity 2, tangent bias tan 30°, radius at most 50 px | about 1.45 ms |
| SAO | 11 samples on a 7-turn screen spiral from a random angle; term `(r² − d²)³·max((h − bias)/(ε + d²), 0)`; `ao = max(0, 1 − 5·intensity·sum/(r⁶·samples))^1.5` | ε 0.01, intensity 0.3, bias `0.05·radius` | about 0.70 ms |
| GTAO | after Activision's paper and Intel's XeGTAO: 8 slices, 8 steps per side, horizon cosines with a falloff over 0.4 of the radius, the slice arc integral, `ao = (visibility/slices)^1.5` | | none given |

- **Noise not decoded:** SSAO, SAO and HBAO read the stored `[0, 1]` values as signed vectors, so SSAO's kernel rotation stays in one quadrant, SAO's start angle stays in `[0, π/2]`, and HBAO's "rotation" is not a rotation; only GTAO uses the values as `[0, 1)` offsets, which matches the encoding.
- **Other issues found by reading:** the blur's fixed 0.01 threshold on raw nonlinear depth covers a different distance at every depth; flat mode still runs the AO pass; the AO texture is created before the zero-size check; background pixels at depth 0 are not skipped; and every view gets the first view's projection and the same normal texture. SSAO decodes the normal through `normal_roughness_compatibility`, SAO and GTAO with `·2 − 1` only, and HBAO binds the normal texture without reading it.

### Sun shafts (godot-forest-demo)

A controller node installs the effect into the WorldEnvironment's compositor at run time and each frame projects the sun (the light's `basis.z`, 10,000 units from the camera) to screen UV, hiding the effect when the sun is behind the camera. The shader reads `get_texture("render_buffers", "color")` through a linear sampler and writes `get_color_layer(view)`: from each pixel it marches 40 steps toward the sun over `density` of the way, adding `smoothstep(threshold, 1, luminance)·decay^i·weight`, then adds `shaft_color·sum·exposure·falloff` with `falloff = smoothstep(max_radius, 0, distance)`. That call has `edge0 > edge1`, which GLSL leaves undefined. Defaults: density 0.92, threshold 0.7, weight 0.028, decay 0.95, exposure 1.1, max radius 0.9 (the demo scene overrides them). In mono the source and destination are probably the same image, so the dispatch reads pixels that other workgroups are writing; a capture would settle it.

### Aerial perspective (Godot-RealisticEnvironments)

The only raster pass of the set: one full-screen triangle into the color layer at PRE_TRANSPARENT, with single-sample and MSAA variants (`sampler2DMS`, `texelFetch` with `gl_SampleID`, sample shading on). It reconstructs position from depth with a camera-relative inverse view-projection that keeps only the camera rotation, discards depth 0 (the sky under reversed z), and looks up a 32 × 128 × 64 RGBA16F camera volume whose distance slices are spaced by `√(d/max)`, so they are denser near the camera, out to 100 km. A 256² transmittance LUT and a 32² multiple-scattering LUT feed it. The blend writes in-scatter (with a Henyey–Greenstein lobe, g = 0.97 by default) as output 0 and transmittance as output 1. Haze density is `3.912/visibility`. The LUT compute passes are the only code in the set with explicit `compute_list_add_barrier` calls.

### Path tracer (compositor-effect-library)

128 samples per pixel per frame, up to 5 bounces, over four hard-coded spheres (three of radius 1.2 at x = −4, 0 and 4 with roughness 0, 0.2 and 0.6, and a ground sphere of radius 100 at y = −101) with no acceleration structure, no Fresnel, no light sampling and no accumulation. The environment, baked once to a 1080×540 panorama, is the only light. Depth and normals are bound but never read, so the spheres draw over Godot's geometry with no depth test, and only pixels whose samples hit a sphere are written.

## Multiple views in other effects

A code search for `get_view_count` and `get_view_projection` found these patterns (not exhaustive):

- **Complete:** BastiaanOlij's RERadialSunRays loops over views "just in case we're doing stereo rendering", takes per-view slices of its own textures with `get_texture_slice(context, texture, view, 0, 1, 1)`, and uses `get_view_projection(view)` with `get_view_eye_offset(view)` added to the sun's screen position; the view matrix is one camera transform for every view.
- **Per-view resources:** GodotRetro's base effect, an SMAA port, an SSIL-with-visibility-bitmask effect and a Gaussian-splatting compositor keep per-view textures or matrices.
- **One camera for every view:** the AO and sun-shaft projects above, SunshineClouds2 (one `get_cam_projection()` for all views; its author writes that the engine's scene UBO returns the wrong camera with several cameras) and GDVoxelTerrain's atmosphere.
