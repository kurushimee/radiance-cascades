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

An included file can have any extension. Give it one other than `.glsl`: the importer takes every `.glsl` file for a shader, and one without a stage section such as `#[compute]` fails its import with `Text was found that does not belong to a valid section`.

Editing an included file does not reimport the shaders that include it, and neither does touching a shader, since the import compares file hashes. Delete the shader's `.godot/imported/<shader>.glsl-*` files and run `godot --headless --path . --import`.

## Atomics

The Vulkan driver enables no float atomics and no 64-bit atomics. Accumulate floats as scaled integers with 32-bit `atomicAdd` on a storage buffer or an `r32ui` image. Values that span too many orders of magnitude for one scale can be added as float bits in an `atomicCompSwap` loop on a `coherent` buffer. Give an atomic image `TEXTURE_USAGE_STORAGE_ATOMIC_BIT` as well, so `texture_create` checks that the device supports atomics on its format.

## Subgroups and half floats

GDScript cannot read the subgroup size or check half-float support: `LIMIT_SUBGROUP_*` and `SUPPORTS_HALF_FLOAT` are not bound. No pipeline requests a fixed subgroup size, so a shader using `GL_KHR_shader_subgroup_*` must read `gl_SubgroupSize` instead of assuming 32 or 64. `packHalf2x16` into a `uint` stores half floats on any device.

## Limits

No limit reports the largest storage buffer, and Vulkan only guarantees 128 MiB (`maxStorageBufferRange`). `storage_buffer_create` checks no size of its own, so a buffer up to the device's range works: the RTX 2070 reports 4 GiB, and a 563 MB buffer binds and reads correctly.

A storage-buffer uniform takes exactly one buffer, so an array of storage buffers (`buffer B { ... } b[4];`) cannot be bound.

## Texture arrays

On Vulkan 1.2 devices that support them, the Vulkan driver enables non-uniform indexing of sampled image arrays, runtime descriptor arrays and partially bound bindings (`rendering_device_driver_vulkan.cpp`):

- An array of textures or samplers indexed per invocation needs `nonuniformEXT` on the index.
- A sized array's uniform must supply exactly the declared count, so fill unused slots with a stand-in texture.
- A runtime-sized array (`uniform texture2D textures[];`) takes any count: its binding is partially bound with a variable count, and `uniform_set_create` skips the count check (`rendering_device.cpp`).

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

A push constant block needs no padding to 16 bytes: a 4-byte block works. The size handed to `compute_list_set_push_constant` or `draw_list_set_push_constant` must equal the block's exactly; debug builds reject any other size (`rendering_device.cpp`).

## Raster passes

- A render pipeline created with `INVALID_FORMAT_ID` as its vertex format takes no vertex array: `draw_list_draw(list, false, 1, vertex_count)` runs the vertex shader `vertex_count` times, and the shader reads its data from storage buffers by `gl_VertexIndex`.
- An `R32_UINT` colour attachment stores an integer per pixel, such as a triangle's index, with blending off, as `RDPipelineColorBlendStateAttachment` has it by default.
- `texture_clear` needs `TEXTURE_USAGE_CAN_COPY_TO_BIT` on the texture, storage textures included.

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
- `capture_timestamp()` fails inside a compute list that has dispatched, a draw list that has drawn or a ray tracing list that has traced (`rendering_device.cpp`). Time a pass by capturing before its list begins and after it ends.
- The render graph orders every command recorded before a timestamp ahead of it and every later command after it (`rendering_device_graph.cpp`), so two captures bracket only the commands between them. An empty dispatch of 921,600 threads measured 0.04 ms.
- `buffer_get_data()` between the two captures of a span loses the span: it flushes and stalls the device, and neither capture appears among the frame's timestamps. Read data back after the span ends.
- The engine captures timestamps of its own only for the editor's profiler, `--gpu-profile` or a viewport set to measure its render time (`viewport_set_measure_render_time`).

## Labels

Wrap every pass in `draw_command_begin_label()` / `draw_command_end_label()` so GPU debuggers show it by name.

## Ray tracing

The ray tracing API (`blas_create`, `tlas_build`, `raytracing_pipeline_create`, `raytracing_list_*`, hit shader binding tables) is experimental. Only Vulkan implements it: D3D12 and Metal stub every call and report no support, and Vulkan on macOS and iOS compiles it out.

Stock 4.7.2 has three bugs that upstream PR #122051 fixes for 4.8, and NVIDIA's fork, which this project runs on ([README](../README.md#engine)), carries the same fixes:

- `has_feature(SUPPORTS_RAY_QUERY)` is always false, because the Vulkan driver never requests `VK_KHR_ray_query`, so compute shaders cannot trace.
- `blas_create` fails with `The index buffer contains an index that is outside the specified vertex range.` for every indexed geometry in release builds, because release index buffers record `max_index` as `0xFFFFFFFF`. The fix skips the check for that value.
- Push constants arrive as zeros in ray tracing stages: the shader container ORs the stage enum values instead of their bits, so the push constant range never includes the ray tracing stages.

With ray queries:

- A compute shader traces with `GL_EXT_ray_query`, which needs `#version 460`. The TLAS binds as a `UNIFORM_TYPE_ACCELERATION_STRUCTURE` uniform with one RID. The `committed` argument of the `rayQueryGetIntersection*EXT` functions must be a compile-time constant.
- `tlas_build` refuses an instance whose `hit_sbt_range` is 0, even though ray queries never read the hit shader table, and a range comes only from a hit table, which needs a ray tracing pipeline. The check accepts any nonzero value, and `1 << 32` encodes one hit group at offset 0, so a ray-query-only scene needs no pipeline.
- `blas_create` reads only buffers made by `vertex_buffer_create`. One made with `BUFFER_CREATION_AS_STORAGE_BIT | BUFFER_CREATION_DEVICE_ADDRESS_BIT | BUFFER_CREATION_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT` also binds as a storage buffer, so a compute shader can write the BLAS's vertices. `RenderingServer.mesh_surface_get_vertex_buffer_rd_rid()` returns a mesh surface's own vertex buffer, which the engine creates with those flags when the device supports ray tracing or ray queries (`mesh_storage.cpp`).
- The vertex format `DATA_FORMAT_R32G32B32_SFLOAT` with a 16-byte stride reads `xyz` and leaves each vertex's `w` free for other data.
- Freeing a BLAS's vertex buffer frees the BLAS, so the buffer must live as long as the BLAS. Freeing or rebuilding a BLAS invalidates every TLAS built over it.
- With each triangle's corners ordered so that `cross(v1 − v0, v2 − v0)` points out of its front, `rayQueryGetIntersectionFrontFaceEXT` is true on the front with no instance flag.
- GDScript has no BLAS update (`blas_update` is C++ only), and there is no compaction or size query. A structure keeps its build scratch buffer for as long as it lives. Only `get_memory_usage(MEMORY_TOTAL)`, the driver's allocated bytes, shows their size, from its change across the creation and build.
