# RenderingDevice from GDScript

## Upload before the compute list

```
ERROR: Updating buffers is forbidden during creation of a compute list.
```

`buffer_update` fails between `compute_list_begin()` and `compute_list_end()`, and the dispatch then reads stale data.

## Render thread

Call the main device (`RenderingServer.get_rendering_device()`) through `RenderingServer.call_on_render_thread()` or from `CompositorEffect._render_callback()`.

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

## Timestamps

- `get_captured_timestamp_gpu_time()` returns nanoseconds, not the microseconds the class reference states: a 36.9 ms dispatch measured 36 791 872.
- Only differences within one frame mean anything; absolute values look like nanoseconds since the Unix epoch.
- On the main device, a frame's timestamps become readable two frames later (`get_frame_delay()` is 2) and stay for one frame only. Read the list every frame on the render thread, match names, and check `get_captured_timestamps_frame()`.
- On a local device, timestamps are readable right after `sync()`.
- The engine captures no timestamps of its own.

## Labels

Wrap every pass in `draw_command_begin_label()` / `draw_command_end_label()` so GPU debuggers show it by name.
