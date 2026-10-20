# Radiance Cascades

Radiance cascades global illumination in Godot 4.7.2, written in GDScript with GLSL compute shaders through `RenderingDevice`.

## Docs

Read [docs/rendering_device.md](docs/rendering_device.md) before writing or debugging `RenderingDevice` code.

Engine behavior that took a capture, a crash, or a source read to find, and that the code does not make obvious, goes into `docs/`, checked against the engine first. When a doc and the engine disagree, fix the doc.

## Plans

Feature and tool work follows [plans/README.md](plans/README.md).

## Research

[research/README.md](research/README.md) indexes notes on radiance cascades and related GI techniques. Check it before designing a feature.

## Papers

[papers/README.md](papers/README.md) indexes original papers on radiance cascades, with the experiments behind them. Check them too before designing a feature.

## Design

[design/README.md](design/README.md) specifies the GI system the code implements. A measurement that changes a design figure or decision updates the design file that owns it and its script in `design/checks/`.

## GDScript

Read [.claude/rules/gdscript.md](.claude/rules/gdscript.md) before creating a `.gd` file.

The `gdls` language server answers symbol questions through the LSP tool. Prefer it over Grep for anything symbol-related:

| Task | Use |
|------|-----|
| Where is this class/function/variable defined? | `goToDefinition` |
| Where is this symbol used? | `findReferences` |
| Find a class/symbol by (partial) name | `workspaceSymbol` |
| Type, signature, or docs of a symbol | `hover` (Godot built-ins too) |
| Who calls this / what does it call? | `incomingCalls` / `outgoingCalls` |
| All overrides of a base method | `goToImplementation` on the base method |
| A file's structure | `documentSymbol` |

Edit `.gd` files with Edit or Write: gdls misses changes made any other way and keeps serving the old symbols.

## Layout

| Directory | Contents |
|-----------|----------|
| `src/<feature>/` | GDScript, with each compute shader next to the script that dispatches it; Python tools for the scenes and metrics in `src/reference/` |
| `assets/` | Scenes, models, textures, materials |

| Asset prefix | Asset |
|--------------|-------|
| `scn` | Scene |
| `mdl` | Model |
| `tex` | Texture |
| `mat` | Material |
| `shd` | Godot shader (`.gdshader`) |
| `cshd` | Compute shader (`.glsl`) |
