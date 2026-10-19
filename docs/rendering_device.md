# RenderingDevice from GDScript

## Upload before the compute list

```
ERROR: Updating buffers is forbidden during creation of a compute list.
```

`buffer_update` and `buffer_clear` fail between `compute_list_begin()` and `compute_list_end()`, and the dispatch then reads stale data.

## Barriers between dispatches

Dispatches in one compute list get no barrier between them, so a dispatch that reads what an earlier dispatch in the same list wrote can read stale data. Call `compute_list_add_barrier()` between them: it ends the list and begins a new one with the same pipeline, uniform sets and push constants, and the render graph orders separate lists when one writes a resource the other uses. `barrier()` and `full_barrier()` only print a deprecation warning.

## Shader includes

`#include "file.glsl"` works only in `.glsl` files imported as shader files, with a path relative to that file's folder or starting with `res://`. Includes do not nest: an `#include` inside an included file reaches glslang unexpanded and fails the compile. Shaders compiled at runtime from `RDShaderSource` cannot include files.

## Atomics

The Vulkan driver enables no float atomics and no 64-bit atomics. Accumulate floats as scaled integers with 32-bit `atomicAdd` on a storage buffer or an `r32ui` image. Give an atomic image `TEXTURE_USAGE_STORAGE_ATOMIC_BIT` as well, so `texture_create` checks that the device supports atomics on its format.

## Subgroups and half floats

GDScript cannot read the subgroup size or check half-float support: `LIMIT_SUBGROUP_*` and `SUPPORTS_HALF_FLOAT` are not bound. No pipeline requests a fixed subgroup size, so a shader using `GL_KHR_shader_subgroup_*` must read `gl_SubgroupSize` instead of assuming 32 or 64. `packHalf2x16` into a `uint` stores half floats on any device.

## Limits

No limit reports the largest storage buffer, and Vulkan only guarantees 128 MiB (`maxStorageBufferRange`).

## Indirect dispatch

Pass `STORAGE_BUFFER_USAGE_DISPATCH_INDIRECT` as the usage argument of `storage_buffer_create`. `compute_list_dispatch_indirect` checks only that `offset + 12` fits in the buffer, not that the offset is a multiple of 4 or that the group counts are in range.

## 3D texture mips

`texture_create_shared_from_slice(view, texture, 0, mip, 1, TEXTURE_SLICE_3D)` exposes one mip of a 3D texture, for example to write a mip chain from compute. The layer argument must be 0, so a single depth slice cannot be selected.

## Render thread

Call the main device (`RenderingServer.get_rendering_device()`) through `RenderingServer.call_on_render_thread()` or from `CompositorEffect._render_callback()`.

A callable passed to `call_on_render_thread()` from `_process` runs before that frame's render: with the default Safe thread model at once, and with a separate render thread from the command queue, ahead of the frame's draw.

## Uniform sets

```
ERROR: All the shader bindings for the given set must be covered by the uniforms provided. Binding (1), set (0) was not provided.
```

A set must cover every binding the shader declares, including bindings the code never reads. An optional texture binding still needs a real texture: a null RID fails the set with `Texture (binding: 0, index 0) is not a valid texture.`, so bind a 1×1 stand-in. Every later bind and dispatch of a failed set errors too; fix the first error.

## Push constants

A push constant block needs no padding to 16 bytes: a 4-byte block works.

## Shader compile errors

A failed GLSL compile does not stop the run, and `shader_create_from_spirv` then logs only `Can't create a shader from an errored bytecode. Check errors in source bytecode.` Check `RDShaderSPIRV.compile_error_compute` right after compiling and `push_error()` it.

## Texture2DRD

Create the RD texture with `TEXTURE_USAGE_SAMPLING_BIT`. Without it, the assignment fails with `Condition "!(tf.usage_bits & RD::TEXTURE_USAGE_SAMPLING_BIT)" is true.`, and that `Texture2DRD` keeps failing even with a correct texture; create a new one.

## Texture3DRD

A `Texture3DRD` works as a global `sampler3D` shader parameter. `set_texture_rd_rid()` accepts only a 3D texture with one layer and applies it on the render thread; until then the resource is a 2D placeholder. Later calls replace the texture under the same RID, so materials keep working.

## Timestamps

- `get_captured_timestamp_gpu_time()` returns nanoseconds, not the microseconds the class reference states: a 36.9 ms dispatch measured 36 791 872.
- Only differences within one frame mean anything; absolute values look like nanoseconds since the Unix epoch.
- On the main device, a frame's timestamps become readable two frames later (`get_frame_delay()` is 2) and stay for one frame only. Read the list every frame on the render thread, match names, and check `get_captured_timestamps_frame()`.
- On a local device, timestamps are readable right after `sync()`.
- The engine captures no timestamps of its own.

## Labels

Wrap every pass in `draw_command_begin_label()` / `draw_command_end_label()` so GPU debuggers show it by name.

## Ray tracing

The ray tracing API (`blas_create`, `tlas_build`, `raytracing_pipeline_create`, `raytracing_list_*`, hit shader binding tables) is experimental and has these limits in 4.7.2:

- Only Vulkan implements it. D3D12 and Metal stub every call and report no support; Vulkan on macOS and iOS compiles it out.
- `has_feature(SUPPORTS_RAY_QUERY)` is always false: the Vulkan driver never requests `VK_KHR_ray_query`. Compute shaders cannot trace; tracing needs a ray tracing pipeline (`#[raygen]`, `#[miss]`, `#[closest_hit]`, `#[any_hit]`, `#[intersection]` sections in the `.glsl` file).
- `blas_create` fails with `The index buffer contains an index that is outside the specified vertex range.` for every indexed geometry in release builds, because release index buffers record `max_index` as `0xFFFFFFFF`. Debug builds pass only when the index buffer was created with data. Give the BLAS non-indexed triangles to work in both.
- The engine's mesh buffers cannot feed a BLAS: `RenderingServer` returns no buffer RID for a mesh surface, and its index buffers lack the needed creation bits. Read the arrays with `mesh_surface_get_arrays()` and create the vertex buffer with `BUFFER_CREATION_DEVICE_ADDRESS_BIT | BUFFER_CREATION_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT`.
- Push constants arrive as zeros in ray tracing stages: the shader container ORs the stage enum values instead of their bits, so the push constant range never includes the ray tracing stages. Pass per-dispatch values in a uniform buffer.
