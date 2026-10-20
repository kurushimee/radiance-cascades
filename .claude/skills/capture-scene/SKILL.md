---
name: capture-scene
description: >-
  Renders a scene, saves a screenshot and render timings, and quits. Use
  before finishing any change that can affect what the project renders, before
  claiming that something renders correctly, and when asked to show,
  screenshot, or measure a scene.
---

# Capture a scene

```bash
capture_dir="$TEMP/rc_capture"
godot --path "$(pwd -W)" --resolution 1280x720 --position 40,40 --disable-vsync \
  --scene res://assets/scenes/scn_<name>.tscn -- --capture="$capture_dir"
```

The capture directory then holds `screenshot.png`, `capture.json` and a folder per camera with `final.exr` and `irradiance.exr`, the final image and the `E/π` the GI materials receive, both linear. Look at the screenshot before saying anything about how the scene looks. Run one capture at a time.

`--animation=animated` plays the scene's animated lighting, and `--time=<seconds>` holds it at that time. `uv run src/reference/metrics.py` compares two camera folders.

Any entry in `errors` invalidates the capture. Engine errors before the project boots, and crashes, show only in the command output.

The downloaded scenes (Crytek Sponza, Intel Sponza, Bistro) load only after `python src/reference/fetch_scenes.py` and an import.

A new `class_name` is unknown to a capture until `godot --headless --path "$(pwd -W)" --import` runs.

## Timings

`gpu_ms` and `cpu_ms` cover the main viewport's rendering, not the whole frame; a single pass needs GPU timestamps, see `docs/rendering_device.md`. Capture each configuration at least three times: a spread above a couple of percent means the setup is not controlled yet. When time moved from A to B, show that `total_before − moved_part ≈ total_after`.
