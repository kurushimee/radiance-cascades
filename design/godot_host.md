# Godot host

The system is GDScript plus GLSL compute shaders on Godot 4.7.2's main `RenderingDevice`. A scene node builds everything at load, and a `CompositorEffect` at PRE_OPAQUE runs the frame, so the irradiance atlas is complete before the opaque pass samples it. Engine behaviour that the code depends on is recorded, checked against the 4.7.2 source, in [docs/](../docs/).

## Contents

- [Load](#load)
- [Frame](#frame)
- [Materials and import](#materials-and-import)
- [RenderingDevice rules](#renderingdevice-rules)
- [Code layout](#code-layout)

## Load

A `GI` node in the scene collects every GI mesh instance and light, then runs these steps on the render thread through `RenderingServer.call_on_render_thread`:

1. Upload vertices, indices and UV2 once; build the static BVH and the moving objects' BLASes ([scene_and_tracer.md](scene_and_tracer.md)).
2. Pack the atlas and capture it with a raster pass ([atlas.md](atlas.md)).
3. Insert the cascade probes and needed bins, and fill the hash tables ([cascades.md](cascades.md#which-probes-and-bins-exist)).
4. Trace every static record, and the visibility of static lights.
5. Precompute the dilation map and the seam pairs.

## Frame

The `CompositorEffect` runs at PRE_OPAQUE, where Forward+ has ended the depth pre-pass's draw list and none is open ([docs](../docs/compositor_and_shading.md)). The solve needs neither depth nor normals; this callback is simply the last point in the frame before the opaque pass reads the atlas. Its compute list:

1. Moving objects: TLAS build, retrace of their own records and of the static records near them.
2. Direct light into the texels ([lighting.md](lighting.md#direct-light)).
3. The bounce passes, each merging the cascades from the top down ([cascades.md](cascades.md#a-pass)), then the geometric tail.
4. Dilation and seam stitching, writing the irradiance atlas as `E/π`.

- **Once per frame.** A callback runs per viewport, while the solve is in world space, so the effect skips work when this frame's solve has already run.
- **Inputs from GDScript.** Light parameters and moving transforms are uploaded with `buffer_update` before the compute list opens, since updates inside an open list are not allowed ([docs](../docs/rendering_device.md)).
- **Timing.** Every pass is wrapped in a debug label and timed with GPU timestamps, which are readable two frames later on the main device ([docs](../docs/rendering_device.md)).

## Materials and import

- **One project material.** Every GI mesh uses a project `ShaderMaterial` with albedo, emission and fixture parameters. Its fragment shader samples the irradiance atlas at UV2 and writes `IRRADIANCE` ([near_field.md](near_field.md#the-composite)). An import script converts imported materials to it.
- **UV2 at import.** Scenes import with `meshes/light_baking` set to Static Lightmaps, and an editor script sets `meshes/lightmap_texel_size` to the spacing the [budget](budget.md#texel-spacing) gives for the scene's area ([docs](../docs/lightmap_uv2.md)).
- **Environment.** SSAO and SSIL are off; the environment's sky stays, as the solve reads it ([lighting.md](lighting.md#sky)).

## RenderingDevice rules

From [docs/rendering_device.md](../docs/rendering_device.md), which plan 004 reads before writing any `RenderingDevice` code:

- Dispatches in one compute list get no barrier between them; dependent dispatches need `compute_list_add_barrier`.
- A uniform set must cover every binding the shader declares.
- `#include` works only in imported `.glsl` files and does not nest, so shared code (direction maps, traversal, the hash) lives in single-level include files.
- Only 32-bit integer atomics exist, and the design uses atomics only in the BVH build.
- `has_feature(SUPPORTS_RAY_QUERY)` is always false.

## Code layout

Following the repository's layout, each feature folder holds its scripts with the compute shaders they dispatch:

| Folder | Contents |
|---|---|
| `src/tracer/` | BVH build, traversal include, TLAS |
| `src/atlas/` | packing, capture, dilation, seams |
| `src/cascades/` | probe insertion, hash, records, merge passes |
| `src/lighting/` | direct light, sky table, bounces and tail |
| `src/composite/` | the material conversion at import; the GI shader itself is an asset (`shd` prefix) |
| `src/reference/` | the path tracer and the measurement harness ([evaluation.md](evaluation.md)) |
