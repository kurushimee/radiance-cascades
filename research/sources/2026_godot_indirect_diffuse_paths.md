# Godot 4.7.2: how indirect diffuse reaches opaque surfaces

| | |
|---|---|
| Kind | engine source read, tag 4.7.2-stable |
| Files | `servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp` (RFC), `scene_forward_clustered.glsl` (GLSL), `effects/ss_effects.cpp` (SSE), `storage_rd/material_storage.cpp`, `scene/resources/texture_rd.cpp` |
| Checked | The SSIL gating and composite lines and the SSIL texture binding were re-read at the tag. Other line numbers come from one read. |

This complements [2026_godot_gi_internals.md](2026_godot_gi_internals.md) and answers one question: where can a custom diffuse GI result enter the Forward+ opaque shading, and in what order does the engine combine its own terms?

## Frame order around the opaque pass

1. Depth pre-pass (with normal-roughness when SSAO, SSIL, SSR, SDFGI, a compositor effect with `needs_normal_roughness`, or a normal map needs it), then its MSAA resolve.
2. PRE_OPAQUE compositor callbacks (RFC:2173).
3. `_pre_opaque_render` (RFC:2182): shadows, `process_gi` (writes `rbgi/ambient` and `rbgi/reflection`), last-frame buffer allocation, depth downsample, SSAO, SSIL, SSR, light clustering, volumetric fog, in that order.
4. The render-pass uniform set is built (RFC:2200), binding whatever textures exist under `rb_ssao/final`, `rbgi/ambient`, `rbgi/reflection`, `rb_ssil/final`, `rb_ssr/...` at that moment, or default black.
5. Opaque draw (RFC:2221).
6. After the transparent pass, the color buffer is copied into SSIL's last-frame texture (RFC:2452), so SSIL always reads the previous frame's lit color.

## How the opaque shader builds `ambient_light`

In order, in `scene_forward_clustered.glsl`:

1. Start at zero; take the environment color or sky cubemap.
2. Mix in material `IRRADIANCE` (`mix(ambient, IRRADIANCE.rgb, IRRADIANCE.a)`), only when the material writes it.
3. Add lightmap and lightmap-capture terms.
4. Forward (per-pixel) SDFGI or VoxelGI replaces the value on transparent surfaces; opaque surfaces instead mix the `rbgi/ambient` buffer when SDFGI or VoxelGI is active.
5. Reflection-probe ambient mixes in.
6. `ambient_light *= ao`, where `ao = min(material AO, SSAO)`.
7. `ambient_light *= albedo`.
8. SSIL, when the environment enables it: `ambient_light *= 1 − ssil.a; ambient_light += ssil.rgb·albedo`.
9. Energy compensation, then `·(1 − metallic)`, then the final sum with emission, direct diffuse, and specular; fog last.

So the terms that land in the right place for diffuse GI (multiplied by albedo, AO, and `1 − metallic`, before fog) are `IRRADIANCE` and SSIL.

## Entry points for custom GI

| Entry | Works? | Notes |
|---|---|---|
| Material `IRRADIANCE` | Yes, per material | Every opaque material must be a `ShaderMaterial` that writes it. Combined before AO and albedo, so composition is correct. Can read a screen-sized texture through a global shader uniform and `SCREEN_UV`. |
| Material `EMISSION` | Yes, per material | Bypasses AO and the metallic factor unless the shader applies them; the gomezzz project uses it with `albedo·irradiance·(1 − metallic)`. |
| `rbgi/ambient` from PRE_OPAQUE | No | Read only when SDFGI or VoxelGI is active, and `process_gi` overwrites it after PRE_OPAQUE. |
| `rb_ssil/final` from PRE_OPAQUE | No | The shader reads it only when the environment enables SSIL, and then `using_ssil` is true regardless of the depth pre-pass setting (RFC:1839), so the built-in SSIL overwrites the texture after the callback. If an effect creates the texture first, the engine reuses it without a format check (SSE:706-708). |
| POST_OPAQUE compute on the color buffer | Partly | Adds light after shading, but Forward+ has no albedo buffer, so the GI cannot be multiplied by albedo. |

## Texture2DRD as a global shader parameter

- A `sampler2D` global shader parameter accepts a `Texture2DRD`. The material storage resolves the Variant to its RID and then to the RD texture (`material_storage.cpp`, `texture_storage.cpp:2246-2256`).
- `Texture2DRD` accepts an RD texture only if it is 2D, depth 1, single layer, has `TEXTURE_USAGE_SAMPLING_BIT`, and has a format that maps to an Image format (`texture_storage.cpp:2163-2215`).
- Changing the global value re-queues every material that uses it.

## Other details

- `rendering/driver/depth_prepass/enable` defaults to true; its `disable_for_vendors` list is read only by the Compatibility (GLES3) backend.
- SSAO runs only with the depth pre-pass on, but its shader flag comes from the environment alone. With the pre-pass off and SSAO enabled, the shader reads whatever `rb_ssao/final` holds (untested).
- SSIL's final texture is RGBA16F; SSAO's is R8 even though its interleave shader declares an `rgba8` image.
- The normal-roughness buffer is RGBA8_UNORM.
