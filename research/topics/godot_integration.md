# Godot integration

What Godot 4.7.2 (Forward+, Vulkan) gives an RC implementation, what it withholds, and how a GI result reaches shaded surfaces. `RenderingDevice` rules verified against the engine are in [docs/rendering_device.md](../../docs/rendering_device.md); this note covers the renderer around them. Engine details come from source reads at the 4.7.2-stable tag ([GI internals](../sources/2026_godot_gi_internals.md), [indirect diffuse paths](../sources/2026_godot_indirect_diffuse_paths.md), [compositor examples](../sources/2026_godot_compositor_effect_examples.md)).

## Running the compute work

- Use the main device, `RenderingServer.get_rendering_device()`, on the render thread: inside `CompositorEffect._render_callback()` or through `RenderingServer.call_on_render_thread()`. A local device has its own resources, so its results reach the renderer only through a CPU readback; Sohojoe's 2D port does that every frame and stalls.
- **CompositorEffect** is the only way to read the depth, normal, color and velocity buffers, and it runs per viewport with that viewport's camera. Screen-space probes need it.
- **`call_on_render_thread` from `_process`** suits a world-space volume that does not depend on the camera. gomezzz schedules one update per frame this way and skips frames while the previous update is pending ([gomezzz](../sources/2026_gomezzz_godot_3d_radiance_cascades.md)).
- Record all cascades in one compute list with `compute_list_add_barrier()` between levels, as gomezzz does. Without it, a level reads its parent before the parent is written.
- Shader includes nest only one level in imported `.glsl` files. gomezzz instead compiles at runtime from source and splices includes with string replacement, which then requires adding `*.glslinc` to the export filter.
- Check `RDShaderSPIRV.compile_error_compute` after every compile; a failed compile does not stop the run.

## Screen-space inputs

### Timing

PRE_OPAQUE callbacks run after the depth pre-pass (with normals when requested) and before shadows, GI and the opaque draw. That is the slot for a same-frame screen-space solve: depth and normals for this frame exist, and the result can feed the opaque pass. The depth pre-pass setting `rendering/driver/depth_prepass/enable` defaults to true.

| Callback | Runs |
|---|---|
| PRE_OPAQUE | after the depth pre-pass, before shadows, `process_gi` and the opaque pass |
| POST_OPAQUE | after the opaque pass, before the sky |
| POST_SKY | after the sky |
| PRE_TRANSPARENT | before the alpha pass |
| POST_TRANSPARENT (default) | after the alpha pass, before built-in post-processing |

### Buffers

- **Depth:** `get_depth_layer(view)`; set `access_resolved_depth` when MSAA is on. Depth is reversed: 1 at the near plane, 0 at the far plane and the sky.
- **Normals:** set `needs_normal_roughness`, then `get_texture("forward_clustered", "normal_roughness")` (RGBA8). It holds the view-space normal packed with best-fit encoding and stored as `n·0.5 + 0.5`; decode with `normalize(rgb·2 − 1)`. Alpha is roughness times 127/255, flipped to `1 − value` for dynamic instances, so `a > 0.5` marks moving objects, which helps reject history.
- **Position:** `inverse(get_cam_projection())·vec4((pixel + 0.5)/size·2 − 1, depth, 1)`, divided by `w`, gives the view-space point. The projection includes the y flip, the reversed and remapped z, and the TAA jitter, so it matches the depth buffer exactly; under TAA the reconstructed probe positions shift every frame by the jitter. `get_cam_transform()` takes the point to world space.
- **Motion:** `needs_motion_vectors` fills the velocity buffer for reprojection.
- **Lit color:** the color layer is RGBA16F. There is no albedo buffer in Forward+. Godot's own SSIL copies the finished color after the transparent pass and reads it next frame; a screen-space RC that needs hit radiance can do the same.
- **Sizes:** use `get_internal_size()` (the 3D render size before upscaling) and loop over `get_view_count()` views.
- **Own screen-sized textures:** `RenderSceneBuffersRD.create_texture(context, name, …)` makes textures the engine frees with the buffers; call `clear_context(context)` when settings change, and never free them by hand. Fixed-size data such as probe atlases is created with `texture_create` and freed by the effect.

## World-space inputs

- **Geometry:** the engine exposes no mesh buffer RIDs, and the SDFGI volumes are private engine data that no script or compositor effect can reach. Read triangles with `mesh_surface_get_arrays()` on the CPU (gomezzz, and the ray tracing section of the docs) or rasterize the scene into an own structure; see [scene_representation_and_tracing.md](scene_representation_and_tracing.md).
- **Lights and materials:** collected from the scene tree by script. gomezzz reads `albedo_color`, `emission` and `emission_energy_multiplier` from each `BaseMaterial3D` and converts them to linear.
- **Sky:** `RenderingServer.environment_bake_panorama(environment, false, size)` returns an equirectangular image of the environment for rays that leave the scene.

## Engine GI under development

HDDAGI, reduz's replacement for SDFGI, has been an open pull request since 2023, rebased in 2026 (#119869) and extended with screen probes in a draft (#122999); none is merged and no maintainer has set a timeline ([HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md)). If it lands it still writes the engine's private GI buffers, so it changes nothing about the entry points below. Its shaders are the best reference for `RenderingDevice` GI code written by the engine's own authors: voxel bit masks walked with an integer DDA, wrapped cascade addressing, probe updates with fixed-point integer atomics, a Hi-Z detail trace, screen-probe placement and SVGF. Its pull requests also record what Godot users reported: leaks at corners and at coarse cell sizes, flicker from moving objects, and half-resolution GI as the default.

reduz's design deck for SDFGI and its redesign lists what Godot asks of its own GI: no per-scene or per-object setup, any Vulkan GPU including integrated ones, VR without relying on TAA, and light for transparent objects and volumetric fog, while giving up high-frequency detail and light from dynamic objects ([SDFGI plan](../sources/2023_linietsky_godot_sdfgi_plan.md)).

## Getting GI into shading

The opaque shader builds its ambient term in this order: environment ambient or sky; material `IRRADIANCE`; lightmaps; the `rbgi/ambient` buffer when SDFGI or VoxelGI is active; reflection-probe ambient; `×AO` (the smaller of material AO and SSAO); `×albedo`; SSIL when enabled; energy compensation; `×(1 − metallic)`; then the sum with emission, direct light and specular, and fog last.

| Entry point | Works? | Why |
|---|---|---|
| Material `IRRADIANCE` | yes | Mixed in before AO, albedo and `1 − metallic`, so the composite is correct. Every opaque material must be a `ShaderMaterial` that writes it. |
| Material `EMISSION` | yes, with care | Skips AO and the metallic factor unless the shader applies them; gomezzz writes `albedo·irradiance·(1 − metallic)`. |
| `rbgi/ambient` written at PRE_OPAQUE | no | Read only when SDFGI or VoxelGI is active, and `process_gi` overwrites it after PRE_OPAQUE. |
| `rb_ssil/final` written at PRE_OPAQUE | no | Read only when the environment enables SSIL, and then the built-in SSIL overwrites it after PRE_OPAQUE. |
| Compute on the color buffer after the opaque pass | partly | Adds light after shading, but without albedo. The SSRT effect scales the lit color instead, so unlit surfaces get no bounce; Phreakyx guesses albedo from the lit color. |

The path that composes correctly:

1. Write a screen-sized RGBA16F irradiance texture in a PRE_OPAQUE callback (screen-space probes), or a probe atlas from any callback (world-space probes).
2. Wrap it in a `Texture2DRD` and assign it to a global `sampler2D` shader parameter. The RD texture must be 2D, single-layer, and created with `TEXTURE_USAGE_SAMPLING_BIT`.
3. In every opaque `ShaderMaterial`, sample it (at `SCREEN_UV`, or at the world position and normal for a probe atlas) and write `IRRADIANCE = vec4(value, 1.0)`.

`IRRADIANCE` replaces the environment ambient: a constant color, or the most blurred mip of the sky radiance map, which approximates the cosine-weighted average radiance. So the value to write is `E/π` (for equal-solid-angle bins, `Σ L·cos/Σ cos`), not irradiance `E`, and the RC sky term has to supply the sky light that `IRRADIANCE.a = 1` removes. SSAO still multiplies the result, on top of the occlusion RC already contains, and SSIL adds to it when enabled. Reflection probes with an ambient mode mix in after `IRRADIANCE`.

A screen-space texture read at `SCREEN_UV` describes the opaque surface at that pixel, so transparent materials need a world-space lookup instead.

## Godot RC projects

| Project | What it is | Godot path |
|---|---|---|
| [gomezzz](../sources/2026_gomezzz_godot_3d_radiance_cascades.md) | World-space 3D grid (24×16×24 base probes, 5 cascades), CPU-built BVH plus 64 analytic primitives, six-lobe irradiance atlas | `call_on_render_thread`, one compute list, `Texture2DRD` on generated `ShaderMaterial`s, RC written as `EMISSION` |
| [Phreakyx](../sources/2026_phreakyx_godot_rc_gdextension.md) | Untested GDExtension design: voxel clipmaps, sparse hashed probes, cone tracing | POST_TRANSPARENT compositor effect, albedo guessed from color |
| [knowdawg](../sources/2024_godot_2d_rc_repositories.md) | 2D RC in a pixel-art sandbox | main device, `Texture2DRD` and `Texture2DArrayRD` as global shader parameters |
| [Sohojoe, thmasn](../sources/2024_godot_2d_rc_repositories.md) | 2D ports of Yaazarai's layout and Suslik's Shadertoys | local device with readback; SubViewport chains |

## Pitfalls seen in Godot projects

- Sampling at `pixel/size` without the half-texel offset, and building NDC from integer pixels without dividing by the size (SSRT).
- Float group counts passed to `compute_list_dispatch` (rows dropped); dispatch with `(size − 1)/group + 1`, and bounds-check threads.
- Storage images declared `rgba32f` in GLSL but bound to RGBA16F textures, which Vulkan leaves undefined.
- Recreating textures without `free_rid` leaks memory; reassigning uniform textures every frame rebuilds uniform sets. `UniformSetCacheRD.get_cache()` caches sets per frame.
- Integers in a uniform buffer written as floats; encode them with `PackedByteArray.encode_s32`.
- A copied engine scene UBO struct must match `scene_data_inc.glsl` of the engine version in use.
- Reading only view 0 breaks multi-view rendering.
- Ping-pong parity mistakes in jump floods and in-place cascade updates without ping-pong.
