# Evaluation and acceptance

The GI is accepted when, on fixed test scenes, its indirect light matches an in-engine path tracer within set error limits, it seals rooms, it renders the same frame whatever came before, and it fits the [budget](budget.md). "On par with path tracing" means exactly these limits. They are fixed in plan 004 M1, once the reference exists and before any GI does, so they cannot be fitted to results.

## Contents

- [Scenes](#scenes)
- [Reference](#reference)
- [Metrics](#metrics)
- [Acceptance](#acceptance)

## Scenes

Each scene is pinned by its asset source, camera poses and lighting, and kept outside the repository where its licence or size requires.

| Scene | Source | What it tests |
|---|---|---|
| Cornell box | built in Godot from published dimensions | the cross-check against an independent renderer |
| Crytek Sponza | Khronos glTF-Sample-Assets, CRYENGINE licence | the budget scene: atrium, sun and sky, colour bleeding |
| Intel Sponza with ivy | Intel GPU Research Samples, CC BY; 3.71 GB base, 1.29 GB ivy | 8.8 M triangles, 5.1 M of them ivy leaves modelled as geometry, load time |
| Bistro, interior and exterior | NVIDIA ORCA, CC BY 4.0; 1.05 M and 2.83 M triangles | many small objects, alpha-tested foliage, emissive signs, lamps |
| Sealed sunlit rooms | built in Godot: closed rooms with single-plane and thick walls in sunlight | leaks, two-sided surfaces |
| Two rooms | built in Godot: rooms joined by a door, albedo 0.9 | slow bounce convergence |
| Pillar hall | built in Godot: a hall with a grid of thin pillars | interpolation around thin occluders |
| Small objects | built in Godot: objects smaller than a texel on a floor | the near field ([near_field.md](near_field.md#the-candidate-for-m5)) |

Sources, licences and sizes are recorded in [research](../research/sources/2026_gi_evaluation_tools_and_scenes.md).

**Built scenes.** `src/reference/build_scenes.py` writes them as glTF models and Godot scenes. The rooms are the lab's 32-voxel scenes ([experiments.md](experiments.md)) at 0.25 m per voxel and albedo 0.9, so their errors compare with the lab's. The Cornell box has the published geometry with Mitsuba 3's RGB reflectances and light radiance, so Mitsuba builds the same box from the same numbers.

**Downloaded scenes.** `src/reference/fetch_scenes.py` fetches them from their sources into `assets/downloaded/`, which git ignores, and `build_scenes.py` writes their Godot scenes. Their own lights are replaced: Intel Sponza exports its lights with zero intensity, and Bistro's FBX intensities are in its authoring tool's units. The sun points the way Intel Sponza's and Bistro's own suns do, Crytek Sponza takes Intel Sponza's, Bistro's exterior keeps its HDR sky, and Bistro's interior gets a lamp at each of its four point lights, with the ceiling lamps as fixtures. Bistro's other emissive materials, such as its string lights, shop signs, fans and wall lights, stay in the solve. Intel Sponza and Bistro bring their own cameras; Crytek Sponza gets three and Bistro's exterior three more, in its streets and plaza.

**Lighting.** Every scene has a static setup and an animated one: the sun moving across the sky, lamps switching, an emissive panel changing colour. Lamps are Godot lights with fixture meshes ([lighting.md](lighting.md#emitters)).

## Reference

- **An in-engine path tracer** in compute, using the same BVH and traversal ([scene_and_tracer.md](scene_and_tracer.md)) and the same light formulas ([lighting.md](lighting.md#direct-light)). For each camera it writes the indirect irradiance `E/π` at every pixel, accumulated over as many frames as its noise needs; accumulation is allowed for the reference only. It reads full-resolution materials, not the atlas.
- **The cross-check.** On the Cornell box lit by an emissive ceiling panel, which needs no engine light formulas, the path tracer must agree with Mitsuba 3 within its noise. Mitsuba has no irradiance output and does not read glTF, so the box is built from the same numbers in both, and irradiance comes from a render with every albedo set to one ([research](../research/sources/2026_gi_evaluation_tools_and_scenes.md#reference-renderers)).

## Metrics

| Metric | How |
|---|---|
| Indirect error | relative RMSE and relative bias of the `E/π` buffer against the reference, over the pixels of each camera |
| Image error | mean HDR-FLIP of the final images. Both images use Godot's direct light, and the reference adds its own indirect term, so only the GI differs |
| Leak | in the sealed rooms, the mean irradiance inside as a share of the outside |
| Time | GPU timestamps per pass, median and maximum over 600 frames with the sun moving |
| Determinism | the same frame rendered after two different histories, compared bit for bit |
| Memory | `RenderingDevice` allocations of the GI |

The GI's `E/π` buffer is a render in which the GI materials show the irradiance they receive and nothing else; pixels without a surface are left out. HDR-FLIP comes from the `flip-evaluator` Python package, which takes linear HDR arrays ([research](../research/sources/2026_gi_evaluation_tools_and_scenes.md#flips-python-package)).

## Acceptance

The limits depend on the kind of scene, because the solve's own error does. In the lab at 16 bins, after five bounces with exact direct light, the error was 0.02 to 0.12 in open scenes and single rooms, and 0.15 to 0.20 in rooms joined by a door and around thin pillars, where world probes interpolate through openings (E3 in [experiments.md](experiments.md)). M1 confirms or tightens these starting limits once it knows the reference's noise:

| Check | Limit |
|---|---|
| Indirect error, open scenes and single rooms | relative RMSE ≤ 0.12, \|bias\| ≤ 0.03 |
| Indirect error, linked rooms and pillar halls | relative RMSE ≤ 0.20, \|bias\| ≤ 0.05 |
| Leak, sealed sunlit rooms | ≤ 0.001 of the outside |
| Time, Crytek Sponza at 1080p on the RTX 2070 | median ≤ 6 ms, maximum ≤ 12 ms |
| Determinism | bit-identical |
| HDR-FLIP | set in M1: the FLIP that the indirect-error limit allows, found by perturbing the reference's indirect term by that much |
