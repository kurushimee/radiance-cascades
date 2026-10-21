# Compositor effects and Forward+ shading

Read in the 4.7.2-stable source and checked again in NVIDIA's fork at `135dff3887`; paths are relative to the engine repository.

## Raster passes at PRE_OPAQUE

Forward+ runs PRE_OPAQUE effects right after the depth pre-pass has ended its draw list (`render_forward_clustered.cpp`), so no draw list is open when the callback starts. A callback can begin its own draw list on a framebuffer made from its own textures, and must end it before returning: `draw_list_begin` fails with "Only one draw list can be active at the same time." while another is open. With MSAA, resolved color does not exist yet at PRE_OPAQUE, and resolved depth only exists with a depth pre-pass; asking for either then prints a one-time warning. With path tracing on, the fork renders through `RenderForwardClusteredPT`, which runs PRE_OPAQUE effects without a depth pre-pass (`render_forward_clustered_pt.cpp`). Reflection probe renders run no compositor effects (`renderer_scene_render_rd.cpp`).

## Camera matrices

`RenderSceneData.get_cam_projection()` and `get_view_projection(view)` return the projection with the depth correction for the flipped Y and the TAA jitter applied; `get_cam_transform()` carries neither (`render_scene_data_rd.cpp`). The jitter is nonzero whenever TAA is on (16 phases) or the viewport uses a temporal 3D scaler (FSR2, MetalFX or the fork's DLSS, `8 · (target width / render width)²` phases, `renderer_viewport.cpp`).

## IRRADIANCE

A material that writes `IRRADIANCE` replaces the ambient term: after the ambient color and sky, `ambient_light = mix(ambient_light, IRRADIANCE.rgb, IRRADIANCE.a)`, and the result is then multiplied by AO, albedo and `1 − metallic` and added to emission and direct light (`scene_forward_clustered.glsl`). Nothing on that path divides by π, so the slot expects irradiance over π, the cosine-weighted mean radiance: uniform radiance `L` gives outgoing radiance `albedo · L`.

`RADIANCE` does the same for the indirect specular: `indirect_specular_light = mix(indirect_specular_light, RADIANCE.rgb, RADIANCE.a)` replaces the sky's prefiltered reflection, and reflection probes then replace it where they cover the surface. Unless the shader sets `specular_occlusion_disabled` or writes `BENT_NORMAL_MAP`, Godot then scales that light by `min(8 · luminance(ambient light), 1)`, raised for smooth metals, where the ambient light is the one `IRRADIANCE` set. The factor is in absolute units, so it occludes little in a bright scene and most of the reflections in a scene lit in physical units. It also makes the frame non-affine in `IRRADIANCE`: on Bistro's shaded Corner, Godot's frame with a path-traced `E/π` was 65% brighter in the median pixel than the frame composed from the frames at `IRRADIANCE` 0 and 1, and with the occlusion off the two agreed within 0.04% in 90% of the pixels. SSR applies after the occlusion and is not scaled by it (`scene_forward_clustered.glsl`).

The camera's exposure multiplier reaches lights, emission and the sky through exposure-normalization factors (`emission *= scene_data.emissive_exposure_normalization`, `IBL_exposure_normalization` on the sky's ambient and reflections), but the mix with `IRRADIANCE` comes after them and leaves it unscaled. So under `CameraAttributes.exposure_multiplier` a material's own irradiance drifts against the rest of the frame, and only `Environment.tonemap_exposure`, applied at tonemapping, scales the whole frame.

## Diffuse

A spatial shader without a `diffuse_*` render mode uses Lambert: the render mode list starts with `lambert` (`shader_types.cpp`), only the other modes emit a define (`scene_shader_forward_clustered.cpp`), and the light code falls back to Lambert without one (`scene_forward_lights_inc.glsl`). `StandardMaterial3D` defaults to Burley. The project setting `rendering/shading/overrides/force_lambert_over_burley` turns Burley into Lambert.

## Global sampler parameters

A global sampler parameter without a texture binds the default texture of its hint, as a material sampler does: black for `hint_default_black` (`material_storage.cpp`). Setting it to `null` returns it to that default. `RenderingServer.global_shader_parameter_get` logs an error outside the editor and returns nothing, so a game cannot read a global back to restore it.

## Light units and attenuation

`scene_forward_lights_inc.glsl` and `light_storage.cpp`:

- Lambert diffuse is `N·L / π` times the light color times its energy. The color enters linear, as `light_color.srgb_to_linear()`.
- Without physical light units, every light type's energy is multiplied by π before upload, which cancels Lambert's 1/π: diffuse = `albedo · color · energy · N·L · attenuation`.
- With physical light units, directional energy is multiplied by the intensity in lux; omni, spot and area energy by the intensity in lumens and then by 1/(4π), 1/π and 1/(2π).
- Omni and spot attenuation is `max(1 − (d/r)⁴, 0)² · max(d, 0.0001)^(−decay)`.
- Spot lights multiply it by `1 − rim^(1 / spot_angle_attenuation)`, with `rim = max(1e−4, (1 − c) / (1 − cos(spot_angle)))` and `c = max(dot(−L, direction), cos(spot_angle))`. The spot shines along the light's −Z axis.
- `light_indirect_energy` scales the light in the engine's own GI (`gi.cpp`) and, in the fork, in the path tracer's light sampling after the first bounce (`raytracing_lights_inc.glsl`), never in Forward+ direct light.

## Sky

Scripts reach the sky only as a CPU `Image`: `RenderingServer.sky_bake_panorama(sky, energy, bake_irradiance, size)` or `environment_bake_panorama(environment, bake_irradiance, size)` returns a linear, untonemapped equirectangular panorama in `FORMAT_RGBAF` of the radiance map, or of the irradiance map with `bake_irradiance`. No method returns the sky's RD texture, and the engine stores the radiance map as an octahedral map (`sky.cpp`).

In the baked panorama, row 0 looks straight up, and the pixel at `(u, v)` in [0, 1]² looks along `(−sin φ sin θ, cos θ, −cos φ sin θ)` with `φ = 2πu` and `θ = πv`, measured from the brightest pixel of a procedural sky against its sun's direction. An environment with a colour background bakes to that colour, linear.

## HDR readback

With `use_hdr_2d`, a viewport renders to RGBA16F, and `get_texture().get_image()` returns `FORMAT_RGBAH` when `transparent_bg` is on and `FORMAT_RGBH` otherwise; an opaque viewport reads its alpha as one (`texture_storage.cpp`). An alpha-scissor material writes alpha one where it keeps a pixel (`scene_forward_clustered.glsl`), so a transparent background still separates surfaces from sky exactly. Alpha-to-coverage (`ALPHA_ANTIALIASING_EDGE`) gives up that exactness: it raises the edge to the scissor threshold plus its own value, feathers alpha across it (`compute_alpha_antialiasing_edge`), and discards in the depth prepass below `opaque_prepass_threshold`. With the Linear tonemapper the values are linear and unclamped. `Image.save_exr` works in exported builds too: the tinyexr module builds on every platform and registers the saver without an editor guard (`modules/tinyexr/`).

## Texture RIDs

`RenderingServer.texture_get_rd_texture(texture, srgb)` returns the texture's sRGB view when `srgb` is true and the texture has one, and its base RID otherwise, silently; neither choice converts data (`texture_storage.cpp`).
