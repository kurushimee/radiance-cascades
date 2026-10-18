# Godot 4.7.2 internals relevant to custom GI

| | |
|---|---|
| Kind | engine source and docs |
| Engine ref | tag 4.7.2-stable. Docs pages were read at their "latest" URLs on 2026-10-16. The blog post is from June 2020. |
| Checked | The script binding of `RenderSceneBuffersRD` (no custom-data methods) and the order PRE_OPAQUE callbacks, `_pre_opaque_render` / `process_gi`, opaque pass, POST_OPAQUE callbacks were checked against the tag source. Other line numbers come from one source read and need checking before use. |

SDFGI keeps eight or fewer cascades of 128-cube voxel volumes (SDF, light, anisotropic light) and one 17x17x17 probe grid per cascade. Static geometry is voxelized each time a cascade window moves, and probe rays are traced through the SDF every frame. Per pixel, `gi.glsl` writes ambient and reflection colour into textures in the render-buffer context `rbgi`, and the opaque shader reads them. A CompositorEffect can read those two textures by name, but it cannot reach the SDFGI volumes. The source has no documented hook that feeds custom GI into the opaque pass, apart from per-material IRRADIANCE and RADIANCE outputs and a script-callable VoxelGI data path.

Source paths below are relative to the repository root at tag 4.7.2-stable. Line numbers refer to that tag. Docs citations give the section heading on the page.

## A. SDFGI design

### A.1 What the blog and docs say

The 2020 blog post is marked as possibly outdated. It says SDFGI needs no unwrapping and no ray tracing hardware. It says static meshes contribute light and dynamic meshes only receive it. It says light changes are real time and that emissive surfaces contribute. It says the technique is "mostly leak free" as long as walls are thicker than one voxel of the cascade that renders them. Its "How does it work?" section says an article will follow, so it gives no internal design. (Blog, sections "What can it do?" and "How does it work?")

The current docs say SDFGI supports dynamic lights but not dynamic occluders or dynamic emissive surfaces. (Docs, intro.)

SDFGI is only supported with the Forward+ renderer. (Docs, intro.)

SDFGI follows the camera. Users do not set an extent. (Docs, "Setting up SDFGI".)

Mesh bake modes: Static meshes contribute; Disabled and Dynamic meshes do not contribute and only receive. (Docs, "SDFGI interaction with lights and objects".)

Light bake modes: Static lights are baked into SDFGI; Dynamic lights (the default) still contribute in real time. (Docs, "SDFGI interaction with lights and objects".)

The SDF is only recomputed when the camera moves into or out of a cascade. A nearby static object that moves stays wrong until the camera moves away. (Docs, "SDFGI caveats".)

Sharp reflections appear only on opaque materials. (Docs, "SDFGI caveats".)

Indirect light takes about 30 frames to converge by default. (Docs, "SDFGI caveats".)

### A.2 Environment settings and defaults

| Environment property | Default | Range or note | Source |
|---|---|---|---|
| sdfgi_enabled | false | | scene/resources/environment.h:153 |
| sdfgi_cascades | 4 | 1 to 8 | environment.h:154; scene/resources/environment.cpp:1422 |
| sdfgi_min_cell_size | 0.2 | 0.01 to 64 | environment.h:155; environment.cpp:1423 |
| sdfgi_y_scale | 75% | 50%, 75%, 100% | environment.h:156; environment.cpp:1428; servers/rendering/rendering_server_enums.h:702-705 |
| sdfgi_use_occlusion | false | | environment.h:157 |
| sdfgi_bounce_feedback | 0.5 | | environment.h:158 |
| sdfgi_read_sky_light | true | | environment.h:159 |
| sdfgi_energy | 1.0 | | environment.h:160 |
| sdfgi_normal_bias | 1.1 | | environment.h:161 |
| sdfgi_probe_bias | 1.1 | | environment.h:162 |

Project settings read by the GI constructor: `probe_ray_count`, `frames_to_converge`, `frames_to_update_lights` (servers/rendering/renderer_rd/environment/gi.cpp:3515-3517).

Ray count options per probe are {4, 8, 16, 32, 64, 96, 128}. The default is 16 (gi.cpp:1322; gi.h:708).

Frames to converge options are {5, 10, 15, 20, 25, 30}. The default is 30 (render_forward_clustered.cpp:4053-4054; gi.h:709).

Frames to update light options are 1, 2, 4, 8, 16. The default is 4 (gi.h:710; gi.cpp:1291-1295).

Environment helper formulas: `get_sdfgi_max_distance()` returns min_cell_size x 64 x 2^cascades. `get_sdfgi_cascade0_distance()` returns min_cell_size x 64 (environment.cpp:511-526). The class reference lists the same defaults (doc/classes/Environment.xml).

### A.3 Constants and cascade geometry

| Item | Value | Source |
|---|---|---|
| Maximum cascades | 8 | gi.h:561 |
| Cells per cascade axis | 128 | gi.h:562; gi.h:646 |
| PROBE_DIVISOR | 16 | gi.h:563 |
| Cells between probes | 8 (128 / 16) | gi.cpp:566 |
| Probes per axis | 17 (PROBE_DIVISOR + 1, so the grid includes both endpoints) | gi.cpp:427; gi.h:665 |
| Probes per cascade | 17 x 17 x 17 | gi.cpp:427 |
| Octahedral tile per probe | 6x6 texels plus a 1-texel border, 8x8 stride | gi.h:567; gi.cpp:516-517 |
| SH coefficients per probe | 16 rows | gi.h:568; gi.cpp:494 |
| Dynamic light slots | 128 | gi.h:565 |
| Static light slots | 1024 | gi.h:566 |
| Solid cell fraction | 0.25 of cascade voxels (`solid_cell_count` = 128^3 x 0.25) | gi.h:712; gi.cpp:428-429 |
| Y multiplier | 2.0 (50%), 1.5 (75%), 1.0 (100%) | gi.cpp:423-424 |

Cascade i has cell size min_cell_size x 2^i (gi.cpp:431, 563, 573).

Cascade i covers cells from `position - 64` up to `position + 64` on each axis (gi.cpp:1520).

World Y is multiplied by `y_mult` before cells are indexed (gi.cpp:565, 1207-1209; gi.glsl:290).

Derived values with the defaults (arithmetic from the formulas above, not stated in the source): cell sizes are 0.2, 0.4, 0.8 and 1.6 m. Cascade extents are 25.6, 51.2, 102.4 and 204.8 m. The outermost extent matches the value from `get_sdfgi_max_distance()`.

### A.4 Textures

Per cascade (`SDFGI::Cascade`, gi.h:571-622). Each cascade has its own 3D textures of 128^3, created in gi.cpp:547-590.

| Texture | Format | Size | Source |
|---|---|---|---|
| sdf_tex | R8_UNORM, 3D, sampled and storage | 128^3 | gi.cpp:433-439, 550 |
| light_data / light_tex | R32_UINT stored, E5B9G9R9_UFLOAT view (RGBE) | 128^3 | gi.cpp:478-481, 552-561 |
| light_aniso_0_tex | R8G8B8A8_UNORM | 128^3 | gi.cpp:483-484, 554 |
| light_aniso_1_tex | R8G8_UNORM | 128^3 | gi.cpp:485-486, 555 |
| lightprobe_history_tex | R16G16B16A16_SINT, one layer per history frame | 289 x 272 per layer | gi.cpp:491-502, 577-579 |
| lightprobe_average_tex | R32G32B32A32_SINT | 289 x 272 | gi.cpp:504-506, 581-583 |
| solid_cell_buffer | storage buffer, `solid_cell_count` entries | | gi.cpp:587 |
| solid_cell_dispatch_buffer_* | indirect dispatch buffers | | gi.cpp:588-589 |
| lights_buffer | storage buffer of Light entries | | gi.cpp:590 |

Shared by all cascades in one SDFGI object.

| Texture | Format | Size | Source |
|---|---|---|---|
| lightprobe_data / lightprobe_texture | R32_UINT stored, E5B9G9R9 view. Array layers = 2 x cascades. Diffuse and specular octahedral probe maps. | 2312 x 136 per layer (289 x 8 by 17 x 8) | gi.cpp:511-525; gi.glsl:265 (specular read at layer offset max_cascades) |
| occlusion_data / occlusion_texture | R16_UINT stored, R4G4B4A4_UNORM view. Depth = 128 x cascades. | width 256 | gi.cpp:471-476, 540-545 |
| ambient_texture | R16G16B16A16_SFLOAT, 2D array (one layer per cascade). Used by volumetric fog. | 289 x 17 | gi.cpp:527-535; gi.h:654 |
| lightprobe_history_scroll | R16G16B16A16_SINT | | gi.cpp:508 |
| lightprobe_average_scroll | R32G32B32A32_SINT | | gi.cpp:509 |

Render-time textures, shared by all cascades and reused for each voxelization region (gi.cpp:441-469):

| Texture | Format | Size | Source |
|---|---|---|---|
| render_albedo | R16_UINT | 128^3 | gi.cpp:441-444 |
| render_emission, render_emission_aniso | R32_UINT | 128^3 | gi.cpp:447-448 |
| render_occlusion[8] | R8_UNORM | 128^3 | gi.cpp:452-454 |
| render_geom_facing | R32_UINT | 128^3 | gi.cpp:457 |
| render_sdf[2] | R8G8B8A8_UINT (ping-pong for jump flood) | 128^3 | gi.cpp:459-461 |
| render_sdf_half[2] | R8G8B8A8_UINT | 64^3 | gi.cpp:463-468 |

Voxel encoding:

- Albedo voxel (R16_UINT): bit 0 is the solid flag. Red, green and blue are 5-bit values at bits 11, 6 and 1 (scene_forward_clustered.glsl:2912-2915).
- SDF texel: empty cells store (1 + distance in cells) / 255. Solid cells store 0 (sdfgi_preprocess.glsl:958-968). The reader decodes `texel * 255 - 1` (sdfgi_integrate.glsl:227).
- Occlusion: eight 4-bit values per cell, split across two 16-bit stores (sdfgi_preprocess.glsl:973-980).
- Light: RGBE 9-9-9-5 through the E5B9G9R9 view (gi.cpp:478-481; sdfgi_direct_light.glsl:462).

### A.5 Voxelization

The entry point is `RenderForwardClustered::_update_sdfgi`, which calls `render_region` for each pending region (render_forward_clustered.cpp:1255-1281; gi.cpp:2061-2082).

`render_region` calls `_render_sdfgi` (render_forward_clustered.cpp:3099-3180).

`_render_sdfgi` makes three orthographic passes, one per axis, over the region's bounds (render_forward_clustered.cpp:3133-3176).

Each pass draws the scene with `PASS_MODE_SDF` (render_forward_clustered.cpp:398, 479-482).

The `MODE_RENDER_SDF` variant of the scene shader writes into the 3D images. It stores albedo, adds facing bits with `imageAtomicOr`, and stores emission (scene_forward_clustered.glsl:2906-2960).

The documentation says only Static meshes take part in SDFGI (docs, "SDFGI interaction with lights and objects").

### A.6 Camera follow and scrolling

`SDFGI::update` runs every frame (gi.cpp:1192-1247; called from render_forward_clustered.cpp:4068).

A cascade moves when the camera's cell index leaves a window of `drag_margin` = 4 cells around the cascade center (gi.cpp:1199, 1212-1222). Each move shifts the cascade by 8 cells, which is one probe spacing.

The shifted slab is recorded as a dirty region (gi.cpp:1215, 1220).

If a shift is 128 cells or more, the whole cascade is marked dirty (gi.cpp:1226-1230).

If more than half of the safe volume would be dirty, the whole cascade is marked dirty (gi.cpp:1240-1244).

`get_pending_region_data` turns dirty slabs into regions for voxelization (gi.cpp:1458-1512).

Existing voxel data moves with a scroll pass (gi.cpp:2119-2126; sdfgi_preprocess.glsl:173-200, MODE_SCROLL).

Existing probe data moves with the integrate scroll modes (gi.cpp:2177-2205).

### A.7 Per-frame pass order

Numbered by the order the calls run during one frame.

1. `RenderForwardClustered::sdfgi_update` creates the SDFGI object when SDFGI is enabled, or deletes it when disabled or reset. Otherwise it calls `update` (render_forward_clustered.cpp:4026-4070; gi.cpp:414, 1192). The caller is not in the files read here.
2. The region list comes from `sdfgi_get_pending_region_count`, `sdfgi_get_pending_region_bounds` and `sdfgi_get_pending_region_cascade` (render_forward_clustered.cpp:4072-4122; gi.cpp:1458-1512).
3. `_render_scene` calls `_update_sdfgi` (render_forward_clustered.cpp:1734; body 1255-1281). It runs `render_region` for each region, then `render_static_lights` when static lights need an update (gi.cpp:2061-2420, 2422-2609).
4. For normal views (not reflection probes), `_render_scene` calls `update_cascades`, `pre_process_gi` and `update_light` (render_forward_clustered.cpp:1748-1759; gi.cpp:1514, 1825, 1249).
5. In the depth pre-pass branch, `_post_prepass_render` calls `update_probes`. That runs sdfgi_integrate MODE_PROCESS (renderer_scene_render_rd.cpp:1348-1357; gi.cpp:1311-1411; render_forward_clustered.cpp:2119-2132). The branch runs only when the depth pre-pass is enabled (render_forward_clustered.cpp:2112-2113).
6. PRE_OPAQUE compositor callbacks run (render_forward_clustered.cpp:2173).
7. `_pre_opaque_render` runs (render_forward_clustered.cpp:2182, body 1517). It calls `store_probes`, which converts SH to octahedral maps (render_forward_clustered.cpp:1532-1534; gi.cpp:1414-1455). It then calls `process_gi` when GI is in use (render_forward_clustered.cpp:1580, 1606-1607; gi.cpp:3968-4276).
8. The opaque pass, POST_OPAQUE callbacks, sky, POST_SKY callbacks, PRE_TRANSPARENT callbacks, the alpha pass and POST_TRANSPARENT callbacks run in that order (render_forward_clustered.cpp:2188-2458).

### A.8 Shader files

All files are in servers/rendering/renderer_rd/shaders/environment/. Shaders have no header comments. Roles below come from each file's entry points and the mode defines in gi.cpp.

| Shader | Variants (define) | What it does |
|---|---|---|
| sdfgi_preprocess.glsl | MODE_SCROLL (gi.cpp:3634; shader 173-200) | Moves voxel albedo, facing and light to new positions when a cascade scrolls. |
| | MODE_SCROLL_OCCLUSION (3635; 203) | Moves occlusion with the voxels. |
| | MODE_INITIALIZE_JUMP_FLOOD, _HALF (3636-3637; 227, 245) | Seeds the jump flood with solid voxels. |
| | MODE_JUMPFLOOD, MODE_JUMPFLOOD_OPTIMIZED (3638-3639; 275, 351) | Jump-flood passes that find the nearest solid voxel for each cell. |
| | MODE_UPSCALE_JUMP_FLOOD (3640; 446) | Upscales the half-resolution jump-flood result. |
| | MODE_OCCLUSION (3641; 484) | Computes per-cell occlusion in eight directions. |
| | MODE_STORE (3642; 948-981) | Writes the SDF texture, the occlusion texture and the solid-voxel position list. |
| sdfgi_direct_light.glsl | MODE_PROCESS_STATIC (gi.cpp:3656; 31) | Marches each static light toward each voxel through the SDF (313) and writes the result to the light texture (447-470). Writes anisotropic light too (559-561). |
| | MODE_PROCESS_DYNAMIC (3657; 216) | Same for dynamic lights, with the bounce term from the probe texture (binding 11). Stores at 497-509. |
| sdfgi_integrate.glsl | MODE_PROCESS (gi.cpp:3674; 164) | For each probe, traces Vogel-distributed rays through the SDF (180-265), adds sky light (277) and light lookups, and stores SH in the history texture (324). |
| | MODE_STORE (3675; 350-433) | Converts SH to octahedral maps and writes `lightprobe_texture`. |
| | MODE_SCROLL (3676; 475) | Shifts probe history and average data when a cascade moves. |
| | MODE_SCROLL_STORE (3677; 600) | Writes the shifted probe maps. |
| sdfgi_debug.glsl | MODE_DEBUG_COLOR, MODE_DEBUG_LIGHT, MODE_DEBUG_EMISSION (gi.cpp:3609-3612) | Full-screen debug ray march through the SDF (72-183). Debug only. |
| sdfgi_debug_probes.glsl | MODE_PROBES, MODE_VISIBILITY, with multiview variants (gi.cpp:3783-3786) | Vertex and fragment shaders that draw probe spheres. Debug only. |
| environment/gi.glsl (shader name `gi`) | Modes VOXEL_GI, SDFGI, COMBINED and their no-sampler variants (gi.h:807-813; gi.cpp:3721-3725) | Per pixel: samples SDFGI probes (`sdfgi_process`, gi.glsl:288) and VoxelGI (gi.glsl:615-670). Writes `ambient_buffer` and `reflection_buffer` (gi.glsl:717-727). |

### A.9 Places where source comments disagree with the code

- gi.cpp:435 says the SDF is "Always 64x64". The code uses `cascade_size`, which is 128 (gi.h:646).
- gi.h:580 says albedo and emission are "half size". The code creates them at full cascade size (gi.cpp:441-448, 478-486).
- gi.h:663 sets `num_cascades = 6`. The constructor always overwrites it from the environment (gi.cpp:419).
- gi.cpp:1204-1205 computes `probe_half_size` and then sets it to zero. The drag test therefore uses no offset.
- gi.h:590-595 says the `SolidCell` struct is unused and only documents size.

## B. Access to GI data from CompositorEffect

### B.1 Script-visible API

`RenderSceneBuffersRD` binds these methods to scripts (render_scene_buffers_rd.cpp:51-83):

- Texture access: `has_texture`, `get_texture`, `get_texture_format`, `get_texture_slice`, `get_texture_slice_view`, `get_texture_slice_size` (lines 52, 56-60).
- Texture creation: `create_texture`, `create_texture_from_format`, `create_texture_view` (lines 53-55).
- Context management: `clear_context` (line 61).
- Named accessors for the common buffers: `get_color_texture`, `get_color_layer`, `get_depth_texture`, `get_depth_layer`, `get_velocity_texture`, `get_velocity_layer` (lines 64-69).
- Sizes and counts: `get_internal_size`, `get_target_size`, `get_view_count`, `get_render_target`, `get_texture_samples` and related getters (lines 72-82).

Custom data is not script-visible. `has_custom_data`, `set_custom_data` and `get_custom_data` are declared only in C++ (render_scene_buffers_rd.h:231-233). No bind call exists for them in render_scene_buffers_rd.cpp. The class reference has no entry for them (doc/classes/RenderSceneBuffersRD.xml contains no "custom" text).

SDFGI, the GI buffers object (`rbgi`), volumetric fog and the forward-clustered data all use custom data (gi.h:453-476, 556; render_forward_clustered.cpp:279-286, 3392-3395, 3711-3712).

`get_texture` on a missing name logs an error and returns an invalid RID (render_scene_buffers_rd.cpp:391-397). `has_texture` returns false in that case (lines 286-290). Check `has_texture` first.

### B.2 Context and texture names found in source

The context names are the `RB_SCOPE_*` defines. The texture names are the `RB_TEX_*` defines. Strings are as defined.

| Context (define, file:line) | Texture names (define, file:line) | Created at |
|---|---|---|
| "render_buffers" (RB_SCOPE_BUFFERS, storage/render_scene_buffers_rd.h:44) | "color", "color_msaa", "color_upscaled", "color_subsampled", "color_msaa_subsampled", "depth", "depth_msaa", "depth_subsampled", "depth_msaa_subsampled", "velocity", "velocity_msaa", "blur_0", "blur_1", "back_color", "back_depth" (h:48-64) | storage/render_scene_buffers_rd.cpp:186-206, 534-535, 724, 731-736; renderer_rd/renderer_scene_render_rd.cpp:345, 418 |
| "VRS" (RB_SCOPE_VRS, h:45) | "texture" (RB_TEXTURE, h:47) | render_scene_buffers_rd.cpp:206 |
| "forward_clustered" (RB_SCOPE_FORWARD_CLUSTERED, renderer_rd/forward_clustered/render_forward_clustered.h:49) | "specular", "specular_msaa" (h:51-52); "normal_roughness", "normal_roughness_msaa" (h:53-54); "voxel_gi", "voxel_gi_msaa" (h:55-56) | render_forward_clustered.cpp:51-84 |
| "rbgi" (RB_SCOPE_GI, renderer_rd/environment/gi.h:52) | "ambient", "reflection" (RB_TEX_AMBIENT, RB_TEX_REFLECTION, gi.h:55-56) | gi.cpp:3987-3997 |
| "sdfgi" (RB_SCOPE_SDFGI, gi.h:53) | none. SDFGI volumes are held as custom data (gi.cpp:404-412, 522, 540, 550). | not in the named registry |
| "Fog" (RB_SCOPE_FOG, renderer_rd/environment/fog.h:42) | not catalogued | used as custom data (render_forward_clustered.cpp:3711-3712) |
| "rb_ssao", "rb_ssil", "rb_ssr" (RB_SCOPE_SSAO, RB_SCOPE_SSIL, RB_SCOPE_SSR; renderer_rd/effects/ss_effects.h:52-54) | "final" (RB_FINAL, h:57); "ssr" (RB_SSR, h:67); "mip_level" (RB_MIP_LEVEL, h:68) | read at render_forward_clustered.cpp:2585-2592, 3641, 3727, 3740-3759 |
| "rb_sslf", "rb_ssds" (h:50-51); "rb_smaa" (renderer_rd/effects/smaa.h:39); "mobile" (renderer_rd/forward_mobile/render_forward_mobile.h:38); "sky_buffers" (renderer_rd/environment/sky.cpp:49) | not catalogued | |

### B.3 Can a CompositorEffect read SDFGI data

The SDFGI volumes and probe maps are not reachable by name. `SDFGI` owns them as RIDs created directly with `texture_create` (gi.cpp:404-412, 522, 540, 550, 577-583; gi.h:628-655). None is registered in the named texture registry, and the SDFGI object is not script-visible.

The per-pixel results are reachable by name. `get_texture("rbgi", "ambient")` and `get_texture("rbgi", "reflection")` return the GI output textures once `process_gi` has created them (gi.cpp:3987-3997; gi.h:55-56).

Those textures contain SDFGI and VoxelGI results combined per pixel, as written by gi.glsl (gi.glsl:717-727).

The textures use RGBA16F and carry sampling and storage usage (gi.cpp:3992-3996).

### B.4 Timing of the rbgi textures

`process_gi` creates the textures when they do not exist (gi.cpp:3987-3997). It runs inside `_pre_opaque_render` (render_forward_clustered.cpp:1607), after PRE_OPAQUE callbacks (line 2173) and before POST_OPAQUE callbacks (line 2270).

A PRE_OPAQUE callback therefore sees the previous frame's values, or nothing on the first frame. A POST_OPAQUE or later callback sees the current frame's values.

The textures are cleared when the GI half-resolution setting changes (gi.cpp:3978-3984).

The textures are reallocated when the context is cleared (gi.cpp:3984).

## C. Compositor hooks and buffers

### C.1 Callback types and order

The enum values are defined in servers/rendering/rendering_server_enums.h:629-635 and scene/resources/compositor.h:43-49. `CompositorEffect` defaults to POST_TRANSPARENT (compositor.h:55).

| Value | Name | Runs | Source |
|---|---|---|---|
| 0 | EFFECT_CALLBACK_TYPE_PRE_OPAQUE | After the depth pre-pass and its resolves. Before shadows, `store_probes`, `process_gi` and the opaque pass. | render_forward_clustered.cpp:2162-2173, 2182; CompositorEffect.xml:77-79 |
| 1 | POST_OPAQUE | After the opaque pass. Before the sky. | render_forward_clustered.cpp:2257-2270; CompositorEffect.xml:80-82 |
| 2 | POST_SKY | After the sky. Before back-buffer copies, subsurface scattering and specular merge. | render_forward_clustered.cpp:2296-2332; CompositorEffect.xml:83-85 |
| 3 | PRE_TRANSPARENT | After the back buffers are created. Before the alpha pass. | render_forward_clustered.cpp:2366-2408; CompositorEffect.xml:86-88 |
| 4 | POST_TRANSPARENT | After the alpha pass and the SSIL/SSR framebuffer copy. Before built-in post-processing. | render_forward_clustered.cpp:2425-2458; CompositorEffect.xml:89-91 |

`_process_compositor_effects` calls each matching effect's callable with the callback type and the RenderData object (renderer_rd/renderer_scene_render_rd.cpp:298-318). It returns early for reflection probe renders (lines 301-307).

The callbacks run on the rendering thread (compositor tutorial, section "Compositor effects").

### C.2 Flags

Flag values are in rendering_server_enums.h:621-625. Each `CompositorEffect` property sets its flag in scene/resources/compositor.cpp.

| Flag | Property | Effect in the renderer | Source |
|---|---|---|---|
| COMPOSITOR_EFFECT_FLAG_ACCESS_RESOLVED_COLOR (1) | access_resolved_color | Resolves MSAA color before the callback. Only when MSAA is on. | rendering_server_enums.h:621; compositor.cpp:131; render_forward_clustered.cpp:2102-2104, 2257-2259, 2394-2396 |
| COMPOSITOR_EFFECT_FLAG_ACCESS_RESOLVED_DEPTH (2) | access_resolved_depth | Resolves MSAA depth before the callback. Only when MSAA is on. | h:622; compositor.cpp:144; render_forward_clustered.cpp:2106-2108, 2263-2265, 2400-2402 |
| COMPOSITOR_EFFECT_FLAG_NEEDS_MOTION_VECTORS (4) | needs_motion_vectors | Computes motion vectors in the opaque pass. Writes the velocity buffer. | h:623; compositor.cpp:157; render_forward_clustered.cpp:1729, 1810-1821 |
| COMPOSITOR_EFFECT_FLAG_NEEDS_ROUGHNESS (8) | needs_normal_roughness | Writes normal and roughness in the depth pre-pass. Forward+ only. | h:624; compositor.cpp:170; render_forward_clustered.cpp:1730, 1933 |
| COMPOSITOR_EFFECT_FLAG_NEEDS_SEPARATE_SPECULAR (16) | needs_separate_specular | Writes specular to its own buffer and merges it after the effects. Forward+ only. | h:625; compositor.cpp:183; render_forward_clustered.cpp:1731, 1967-1968, 2345-2346 |

The editor hides `needs_separate_specular` unless the callback is POST_SKY (compositor.cpp:87-90). The flag itself is still set from the property.

The flags are checked across all effects in the compositor (renderer_scene_render_rd.cpp:257-279).

### C.3 Getting the buffers in a callback

The callback receives a RenderData object (CompositorEffect.xml:23-30 for the example; RenderData.xml:25-36).

- Scene buffers: `render_data.get_render_scene_buffers()` (RenderData.xml:25-30; render_data.cpp:36).
- Color: `get_color_texture(msaa)` or `get_color_layer(layer, msaa)` (render_scene_buffers_rd.cpp:64-65).
- Depth: `get_depth_texture(msaa)` or `get_depth_layer(layer, msaa)` (render_scene_buffers_rd.cpp:66-67).
- Velocity: `get_velocity_texture(msaa)` or `get_velocity_layer(layer, msaa)` (render_scene_buffers_rd.cpp:68-69; CompositorEffect.xml:45-51).
- Normal and roughness: `get_texture("forward_clustered", "normal_roughness")` (CompositorEffect.xml:53-59; render_forward_clustered.h:53). The raw format needs the conversion function in CompositorEffect.xml:60-70.
- Separate specular: `get_texture("forward_clustered", "specular")` (render_forward_clustered.h:51). It exists only when `needs_separate_specular` is set (render_forward_clustered.cpp:188, 242).
- Size and views: `get_internal_size()` returns the 3D render size before upscaling (render_scene_buffers_rd.cpp:74). `get_view_count()` returns the view count (line 73). The compute example loops over views (compositor tutorial, section "Compositor effects").

### C.4 View and projection matrices

`render_data.get_render_scene_data()` returns the RenderSceneData object (render_data.h:45; render_data.cpp:37; RenderData.xml:31-36).

The methods are bound in servers/rendering/storage/render_scene_data.cpp:36-43:

- `get_cam_transform()` (render_scene_data.h:42). For multiview, it returns a centered transform (RenderSceneData.xml, note on get_cam_transform).
- `get_cam_projection()` (render_scene_data.h:43; render_scene_data_rd.cpp:42-48). The result includes depth correction and the TAA jitter offset. For multiview, it is a combined projection (RenderSceneData.xml).
- `get_view_projection(view)` (render_scene_data.h:47; render_scene_data_rd.cpp:60-67). Per view, includes the eye offset and the same corrections.
- `get_view_eye_offset(view)` (render_scene_data.h:46; render_scene_data_rd.cpp:54-58).
- `get_view_count()` (render_scene_data.h:45; render_scene_data_rd.cpp:50-52).

## D. Injecting custom GI into opaque lighting

### D.1 The inputs the opaque shader reads

The forward-clustered render-pass uniform set binds the GI output textures as bindings 28 and 29 (render_forward_clustered.cpp:3649-3660). Binding 28 is `rbgi/ambient` and binding 29 is `rbgi/reflection`. Both fall back to a default black texture when missing. Both need `rb_data`, which is absent for reflection probes (line 3651).

Bindings 30 and 31 hold the SDFGI probe map and occlusion texture (render_forward_clustered.cpp:3666-3686). Binding 32 holds the VoxelGI buffer (line 3696-3703).

Scene shader code blends the buffer values over the environment ambient:

- `ambient_light` starts from the environment or sky ambient (scene_forward_clustered.glsl:1742, 1749-1756).
- The GI buffer blend is `ambient_light = mix(ambient_light, buffer_ambient.rgb, buffer_ambient.a)` (scene_forward_clustered.glsl:2016-2023).
- Specular is blended the same way (lines 2016-2024).

### D.2 When the buffer path is used

The buffer blend runs only when the instance has `USE_GI_BUFFERS` and `sc_use_forward_gi` is off (scene_forward_clustered.glsl:1982).

`USE_GI_BUFFERS` is set only when `p_using_opaque_gi` is true (render_forward_clustered.cpp:1034-1035).

`_fill_render_list` for the opaque list receives `using_sdfgi` and `using_sdfgi || using_voxelgi` (render_forward_clustered.cpp:1913).

`using_sdfgi` needs an enabled SDFGI environment and a non-unshaded debug mode (render_forward_clustered.cpp:1875-1877). `using_voxelgi` needs at least one VoxelGI instance (lines 1871-1872).

Opaque surfaces start with `uses_forward_gi = 0` (render_forward_clustered.cpp:1102). Alpha surfaces with GI set it to 1 (line 1152), so transparent surfaces use per-fragment forward GI instead.

With neither SDFGI nor VoxelGI active, the opaque shader does not read the GI buffers.

### D.3 Timing constraints

`process_gi` overwrites `ambient_buffer` and `reflection_buffer` for every pixel it dispatches (gi.glsl:717-727). It runs only when `render_gi` is true (render_forward_clustered.cpp:1580, 1606-1607).

The PRE_OPAQUE callbacks run before `process_gi` (lines 2173 and 2182).

No callback runs between `process_gi` and the opaque draw (lines 2182 and 2224). POST_OPAQUE runs after the opaque draw (line 2270).

So the rbgi textures do not carry custom data into the opaque pass when SDFGI or VoxelGI is active. `process_gi` overwrites them first. When neither is active, the opaque shader does not read them (D.2).

### D.4 Per-material hook: IRRADIANCE and RADIANCE outputs

The spatial shader fragment outputs `RADIANCE` and `IRRADIANCE` are documented as blends with the environment map (spatial shader reference, section "Fragment built-ins", the entries for `out vec4 RADIANCE` and `out vec4 IRRADIANCE`).

The docs say: "If written to on any branch, blends environment map irradiance with IRRADIANCE.rgb based on IRRADIANCE.a." The same wording applies to RADIANCE.

The compiler renames them to `custom_radiance` and `custom_irradiance` (renderer_rd/forward_clustered/scene_shader_forward_clustered.cpp:776-777).

Usage defines `CUSTOM_RADIANCE_USED` and `CUSTOM_IRRADIANCE_USED` are set when the identifier is used (scene_shader_forward_clustered.cpp:853-855; servers/rendering/shader_compiler.cpp:915-918, 1049-1052).

The scene shader blends them into specular (scene_forward_clustered.glsl:1735-1737) and ambient light (lines 1760-1761).

This hook applies per material, inside that material's own shader. It does not read or write the scene-wide GI buffers.

### D.5 VoxelGI data input from script

`RenderingServer.voxel_gi_allocate_data` is declared in servers/rendering/rendering_server.h:389 and bound to scripts at servers/rendering/rendering_server.cpp:2670.

The inputs are a to-cell transform, an AABB, the octree size, octree cells, data cells, an optional distance field and level counts (renderer_rd/environment/gi.cpp:67-70).

The size checks are: the octree cell buffer size is a multiple of 32 bytes, and the data cell buffer is `(octree cells / 32) x 16` bytes (gi.cpp:91-96).

The sources read here do not describe the byte layout of the octree or data cells beyond these checks.

The uploaded data is read by `voxel_gi_compute` (renderer_rd/shaders/scene_forward_gi_inc.glsl:51-105) and by the VoxelGI path of gi.glsl (gi.glsl:615-670). Its output goes to the same `rbgi` textures, so D.2 and D.3 apply.

### D.6 Built-in ambient sources

The environment ambient colour and energy are in `scene_data.ambient_light_color_energy` (scene_forward_clustered.glsl:1742).

Sky-based ambient uses the radiance cubemap (lines 1749-1756).

Lightmap captures and lightmaps contribute through separate code paths (lines 1804-1819 and 1860-1869).

### D.7 What the source shows, in short

- No documented API writes custom values into `rbgi/ambient` or `rbgi/reflection` before the opaque pass.
- The `rbgi` textures can be addressed by name from a CompositorEffect (section B). The opaque shader reads them only under the gating in D.2, and `process_gi` overwrites them before the opaque pass (D.3).
- Per-material IRRADIANCE and RADIANCE outputs are the script-facing shader hook that changes ambient and specular input for opaque materials (D.4).
- `RenderingServer.voxel_gi_allocate_data` lets a script supply VoxelGI volume data. That data reaches the opaque shader through the same `rbgi` path (D.5).
- CompositorEffect callbacks can read the opaque result at POST_OPAQUE and write color afterwards (section C, and the compositor tutorial). That is post-process composition, not lighting input.

## Sources

Engine source at tag 4.7.2-stable. The URL pattern is https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/<path>.

- servers/rendering/renderer_rd/environment/gi.h and gi.cpp
- servers/rendering/renderer_rd/shaders/environment/gi.glsl, sdfgi_preprocess.glsl, sdfgi_integrate.glsl, sdfgi_direct_light.glsl, sdfgi_debug.glsl, sdfgi_debug_probes.glsl
- servers/rendering/renderer_rd/storage_rd/render_scene_buffers_rd.h and render_scene_buffers_rd.cpp
- servers/rendering/renderer_rd/storage_rd/render_scene_data_rd.cpp
- servers/rendering/storage/render_data.h, render_data.cpp, render_scene_data.h, render_scene_data.cpp
- servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.h and render_forward_clustered.cpp
- servers/rendering/renderer_rd/forward_clustered/scene_shader_forward_clustered.cpp
- servers/rendering/renderer_rd/shaders/forward_clustered/scene_forward_clustered.glsl
- servers/rendering/renderer_rd/shaders/scene_forward_gi_inc.glsl
- servers/rendering/renderer_rd/renderer_scene_render_rd.cpp and renderer_scene_render_rd.h
- servers/rendering/renderer_rd/effects/ss_effects.h, smaa.h
- servers/rendering/renderer_rd/environment/fog.h, sky.cpp
- servers/rendering/renderer_rd/forward_mobile/render_forward_mobile.h
- servers/rendering/shader_compiler.cpp
- servers/rendering/rendering_server_enums.h, rendering_server.h, rendering_server.cpp
- scene/resources/compositor.h and compositor.cpp
- scene/resources/environment.h and environment.cpp
- doc/classes/CompositorEffect.xml, RenderSceneBuffersRD.xml, RenderSceneData.xml, RenderData.xml, Environment.xml

Docs and blog:

- https://godotengine.org/article/godot-40-gets-sdf-based-real-time-global-illumination/ (June 2020; the page says it may be outdated)
- https://docs.godotengine.org/en/latest/tutorials/3d/global_illumination/using_sdfgi.html (sections "Setting up SDFGI", "Environment SDFGI properties", "SDFGI interaction with lights and objects", "Adjusting SDFGI performance and quality", "SDFGI caveats")
- https://docs.godotengine.org/en/latest/tutorials/rendering/compositor.html (sections "The Compositor" and "Compositor effects")
- https://docs.godotengine.org/en/latest/tutorials/shaders/shader_reference/spatial_shader.html (section "Fragment built-ins")
- https://github.com/godotengine/godot/tree/master/doc/classes (class reference sources; the fetched copies are the 4.7.2 tag files listed above)
