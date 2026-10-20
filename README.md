# Radiance Cascades

World-space diffuse global illumination for Godot 4.7.2, built from radiance cascades alone. The lighting of the whole scene is rebuilt every frame, with no temporal accumulation and no denoiser. The aim is to match a path-traced reference while leaving most of a 60 FPS frame to the rest of a game.

| Folder | Contents |
|---|---|
| [research/](research/README.md) | Notes on published work about radiance cascades and related GI techniques |
| [papers/](papers/README.md) | Original papers on radiance cascades, with derivations, checks and lab experiments |
| [design/](design/README.md) | The GI system's design, with the lab experiments and checks behind it |
| [plans/](plans/README.md) | Plans for feature and tool work |
| [docs/](docs/) | Godot engine behaviour checked against the engine source |
| `src/` | GDScript, with compute shaders next to the scripts that dispatch them |
| `scripts/` | Repository tooling |
