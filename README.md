# Radiance Cascades

World-space diffuse global illumination for Godot, built from radiance cascades alone. The lighting of the whole scene is rebuilt every frame, with no temporal accumulation and no denoiser. The aim is to match a path-traced reference while leaving most of a 60 FPS frame to the rest of a game.

## Engine

The project runs on NVIDIA's fork of Godot 4.8-dev, which adds a real-time path tracer and DLSS (NVIDIA-RTX/godot, branch `nvidia-pt-dlss`), with this project's [patch](engine/nvidia_path_tracer.patch) on top ([docs](docs/path_tracer.md)). The GI traces rays in compute shaders with hardware ray queries, which the fork enables with upstream PR #122051's fixes ([docs](docs/rendering_device.md#ray-tracing)), and the reference is path traced and denoised by DLSS Ray Reconstruction, so the project needs an NVIDIA RTX GPU under Vulkan. `d3d12=no` and `accesskit=no` leave out two drivers the project does not use, whose SDKs a plain checkout lacks:

```bash
git init godot-nvidia
cd godot-nvidia
git fetch --depth 1 https://github.com/NVIDIA-RTX/godot.git 135dff3887a3d2ccf45cafbd9bdffa7b718e1e76
git checkout FETCH_HEAD
git apply ../radiance-cascades/engine/nvidia_path_tracer.patch
scons platform=windows target=editor d3d12=no accesskit=no
```

DLSS loads its runtime from beside the executable: the DLLs in `bin/x64` of the Streamline SDK 2.14.16 release (github.com/NVIDIA-RTX/Streamline/releases), which carries DLSS 310.9.16 with Ray Reconstruction's preset F. The project's commands call this build as `godot`.

## Layout

| Folder | Contents |
|---|---|
| [research/](research/README.md) | Notes on published work about radiance cascades and related GI techniques |
| [papers/](papers/README.md) | Original papers on radiance cascades, with derivations, checks and lab experiments |
| [design/](design/README.md) | The GI system's design, with the lab experiments and checks behind it |
| [plans/](plans/README.md) | Plans for feature and tool work |
| [docs/](docs/) | Godot engine behaviour checked against the engine source |
| `engine/` | The patch on NVIDIA's Godot fork |
| `src/` | GDScript, with compute shaders next to the scripts that dispatch them, and Python tools for the test scenes and metrics |
| `assets/` | Scenes, models and shaders of the test scenes; downloaded models go to `assets/downloaded/`, which git ignores |
| `references/` | The test scenes' path-traced references, one folder per scene, which git ignores ([evaluation](design/evaluation.md#reference)) |
| `scripts/` | Repository tooling |
