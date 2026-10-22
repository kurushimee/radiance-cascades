---
name: capture-scene
description: >-
  Renders a scene, saves each camera's frame and render timings, and quits. Use
  before finishing any change that can affect what the project renders, before
  claiming that something renders correctly, and when asked to show,
  screenshot, or measure a scene.
---

# Capture a scene

```bash
capture_dir="$TEMP/rc_capture"
timeout 300 godot --path "$(pwd -W)" --resolution 1280x720 --position 40,40 --disable-vsync \
  --scene res://assets/scenes/scn_<name>.tscn -- --capture="$capture_dir"
```

`godot` is the project's engine build ([README](../../../README.md#engine)): a stock Godot has neither the ray queries nor the path tracer.

The capture directory then holds `capture.json` and a folder per camera with `final.png`, the frame as the game shows it, and `final.exr` and `irradiance.exr`, the final image and the `E/π` the GI materials receive, both linear and without tonemapping or anti-aliasing. Look at `final.png` before saying anything about how the scene looks. Run one capture at a time.

A GI capture also saves the GI's state. `atlas/` holds the atlas's `albedo.exr` and `albedo.png`, `normal.png`, `position.exr`, `emission.exr`, the probe and kind maps `probes.png` and `kinds.png`, and the probes' direct light: `direct.exr` with one ray toward the sun's centre, as each frame computes it, and `direct_sampled.exr` with every light's cone sampled. Each camera folder adds the probes its pixels read, in `texels_albedo.png`, `texels_normal.png`, `texels_probes.png`, `texels_kinds.png` and `texels_direct.exr`, and `direct.exr`, the GI's light code at the pixels. `capture.json` gains `atlas`: the atlas's size, rectangles, texel and probe counts, build time, and `sky`, the sky table's `E/π` on surfaces facing the six axes beside the integral of the panorama it was built from and Godot's own irradiance map. `--atlas-samples=<n>` sets the capture's sample points along each side of a texel, and `metrics.py texels` compares two atlas images.

`--direct=<frames>` captures the path tracer's direct irradiance view instead, averaged over that many raw frames into `direct.exr` and over the even ones into `direct_half.exr`, with alpha 0 where its primary hit is not the raster's. `metrics.py direct` compares a GI capture's `direct.exr` with it, and gives the agreement again without the pixels lit on one side alone.

`--animation=animated` plays the scene's animated lighting, and `--time=<seconds>` holds it at that time. `uv run src/reference/metrics.py` compares two camera folders.

`--benchmark=<texel spacing in metres>` traces the tracer's benchmark rays every frame and times each kind as a pass in `gi_ms`. `--check` adds a check of the tracer's hits against brute force over every triangle, which takes too long on scenes of millions of triangles. Their counts go into `capture.json` under `tracer`.

`--reference` captures the path-traced reference instead of the GI, denoised by DLSS Ray Reconstruction ([evaluation.md](../../../design/evaluation.md#reference)). Each camera folder then holds `irradiance.exr`, the path tracer's `E/π`; `path_traced.exr` and `path_traced.png`, the path-traced frame; `final.exr` and `final.png`, Godot's frame with the reference's `E/π`; `no_indirect.exr` and `unit_indirect.exr`, Godot's final image at an irradiance of 0 and 1; and `position.exr`, the surfaces' world positions. `--accumulate=<frames>` averages that many raw frames of one sample per pixel instead, writing `irradiance_half.exr` over the even ones in place of the path-traced frame, for the Cornell box's cross-check against Mitsuba. The test scenes' references are kept in `references/<scene>`; compare a GI capture with those. `metrics.py flip-limit` gives the HDR-FLIP that the indirect-error limits allow, and `flip-floor` the HDR-FLIP between Godot's frame with the reference's `E/π` and the path-traced one.

`metrics.py agree` reads `albedo.exr` from its first folder, which only `src/reference/mitsuba_cornell.py` writes, so Mitsuba's Cornell box goes first.

Editing a `.glslinc` file does not reimport the shaders that include it: delete their `.godot/imported/<shader>.glsl-*` files before the import.

Any entry in `errors` invalidates the capture, so the first logged error ends it: `capture.json` keeps the errors so far, and Godot exits with code 1. A clean capture exits with 0. The `timeout` ends a capture that hangs without logging an error; size it to the run, since the window stays on screen until then. Engine errors before the project boots, and crashes, show only in the command output.

The downloaded scenes (Crytek Sponza, Intel Sponza, Bistro) load only after `python src/reference/fetch_scenes.py` and an import.

A new `class_name` is unknown to a capture until `godot --headless --path "$(pwd -W)" --import` runs.

## Timings

`gpu_ms` and `cpu_ms` cover the main viewport's rendering, not the whole frame; a single pass needs GPU timestamps, see `docs/rendering_device.md`. Capture each configuration at least three times: a spread above a couple of percent means the setup is not controlled yet. When time moved from A to B, show that `total_before − moved_part ≈ total_after`.
