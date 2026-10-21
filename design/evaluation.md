# Evaluation and acceptance

The GI is accepted when, on fixed test scenes, its indirect light matches a path-traced reference within set error limits, it does not leak into closed rooms, it renders the same frame whatever came before, and it fits the [budget](budget.md). "On par with path tracing" means exactly these limits. They are fixed in plan 004 M1, once the reference exists and before any GI does, so they cannot be fitted to results.

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
| Leak house | built in Godot: two closed rooms in sunlight, one with walls a voxel thick and one with single-plane two-sided walls, each with a ceiling lamp | leaks, two-sided surfaces, lamps |
| Two rooms | built in Godot: rooms joined by a door, with the panel and a red wall in one | slow bounce convergence, coloured light through an opening |
| Pillar hall | built in Godot: a hall with a grid of thin pillars, lit by a panel at one end | interpolation around thin occluders, indirect shadows |
| Small objects | built in Godot: objects smaller than a texel on a floor | the near field ([near_field.md](near_field.md#the-candidate-for-m5)) |

Sources, licences and sizes are recorded in [research](../research/sources/2026_gi_evaluation_tools_and_scenes.md).

**Built scenes.** `src/reference/build_scenes.py` writes them as glTF models and Godot scenes. The rooms are built on the lab's 32-voxel grid ([experiments.md](experiments.md)) at 0.25 m per voxel, with walls of albedo 0.7 and floors of 0.45 where the lab had 0.9 throughout. A lower albedo weakens the higher bounces, through which the solve's error compounds, so the lab's errors at 0.9 bound the rooms' from above. The Cornell box has the published geometry with Mitsuba 3's RGB reflectances and light radiance, so Mitsuba builds the same box from the same numbers. Those are diffuse reflectances, so its surfaces are matte: with Godot's default specular, the path tracer's GGX lobe at roughness 1 reflects 3.7% less light than a Lambertian surface of the same albedo ([docs](../docs/path_tracer.md#materials)).

**Downloaded scenes.** `src/reference/fetch_scenes.py` fetches them from their sources into `assets/downloaded/`, which git ignores, and `build_scenes.py` writes their Godot scenes. Their own lights are replaced: Intel Sponza exports its lights with zero intensity, and Bistro's FBX intensities are in its authoring tool's units. The sun points the way Intel Sponza's and Bistro's own suns do, Crytek Sponza takes Intel Sponza's, and Bistro's interior gets a lamp at each of its four point lights, with the ceiling lamps as fixtures. Bistro's exterior keeps its HDR sky, with the sun's disk painted out of a copy and its light moved into the sun. Bistro's other emissive materials, such as its string lights, shop signs, lanterns, fans and wall lights, stay in the solve. Its glass panes are left out: neither the GI nor the path tracer transmits light, and thin panes pass nearly all of it. Intel Sponza and Bistro bring their own cameras; Crytek Sponza gets three and Bistro's exterior three more, in its streets and plaza.

**Lighting.** Every scene has a static setup and an animated one: the sun moving across the sky, lamps switching, an emissive panel changing colour. Lamps are Godot lights with fixture meshes ([lighting.md](lighting.md#emitters)), with inverse-square falloff and a radius that softens their shadows. The leak house also comes unlit, without its lamps and fixtures, so that no light belongs inside its rooms.

## Reference

- **The path tracer.** The reference is the path tracer of NVIDIA's Godot fork with this project's patch ([docs](../docs/path_tracer.md)), on the same scenes, materials and lights: every light path is traced, nothing is rasterized. Its irradiance view gives the indirect irradiance `E/π` at every pixel: the primary hit is a white diffuse surface that neither emits nor samples lights, and the rest of the path is unchanged. Its normal view gives the path-traced frame.
- **Denoising.** DLSS Ray Reconstruction 4.5 at native resolution denoises both views, and its output is the reference. At one sample per pixel per frame it smears colour bleeding and indirect shadows in the irradiance view, so each frame takes 16. Its history starts over for each view of each camera, and each image is saved 64 frames later, once it has settled ([docs](../docs/path_tracer.md#dlss-ray-reconstruction)). Its images are checked by eye for defects.
- **The cross-check.** On the Cornell box lit by an emissive ceiling panel, which needs no engine light formulas, the accumulated irradiance view is compared with Mitsuba 3 at 8,192 samples. Mitsuba does not read glTF, so `src/reference/mitsuba_cornell.py` builds the box from the same numbers as `build_scenes.py`. Mitsuba has no irradiance output either: on a diffuse surface that does not emit, its radiance over its albedo output is `E/π`, so the panel is left out ([research](../research/sources/2026_gi_evaluation_tools_and_scenes.md#reference-renderers)). `metrics.py agree` compares the two away from edges, where Mitsuba's pixel filter blends surfaces. Their relative RMSE is the one their noise accounts for (0.0403), and the path tracer's mean is 0.021% higher, 4.0 standard deviations of the difference and 1/140 of the bias limit.
- **Images.** Each camera gets two kinds of frame. The metrics read linear EXR frames, rendered without tonemapping, anti-aliasing or debanding, so that each pixel holds the one surface at its centre. People look at `final.png`, the frame as the game shows it: AgX at the camera's exposure, 4× MSAA with SMAA, and debanding, with the reference's irradiance read per screen pixel. A GI capture writes the same two kinds, so its `final.png` and the reference's compare directly. Godot's shadow maps draw the direct light in both, so a contact leak under a zero-thickness wall shows in both. The reference also saves `path_traced.png`, the path tracer's own frame at the same exposure.

## Metrics

| Metric | How |
|---|---|
| Indirect error | relative RMSE and relative bias of the `E/π` buffer against the reference, over the pixels of each camera |
| Image error | mean HDR-FLIP of the final images. Both images use Godot's direct light, and the reference adds its own indirect term, so only the GI differs |
| Image floor | mean HDR-FLIP of the reference's final image against its path-traced frame: how far Godot's direct light, shadows and reflections sit from path tracing. Reported, not gated |
| Leak | in the unlit leak house, the mean irradiance inside each room as a share of the outside |
| Time | GPU timestamps per pass, median and maximum over 600 frames with the sun moving |
| Determinism | the same frame rendered after two different histories, compared bit for bit |
| Memory | `RenderingDevice` allocations of the GI |

The GI's `E/π` buffer is a render in which the GI materials show the irradiance they receive and nothing else; pixels without a surface are left out. HDR-FLIP comes from the `flip-evaluator` Python package, which takes linear HDR arrays ([research](../research/sources/2026_gi_evaluation_tools_and_scenes.md#flips-python-package)).

## Acceptance

The limits depend on the kind of scene, because the solve's own error does. In the lab at 16 bins, after five bounces with exact direct light, the error was 0.02 to 0.12 in open scenes and single rooms, and 0.15 to 0.20 in rooms joined by a door and around thin pillars, where world probes interpolate through openings (E3 in [experiments.md](experiments.md)). The reference counts as exact: its path tracer agrees with Mitsuba to 0.02%, and Ray Reconstruction's output is judged by looking at it ([reference](#reference)). So the lab's errors are the limits, with the downloaded scenes held to the tighter ones:

| Check | Limit |
|---|---|
| Indirect error, open scenes and single rooms: the Cornell box, the leak house, small objects, both Sponzas and Bistro | relative RMSE ≤ 0.12, \|bias\| ≤ 0.03 |
| Indirect error, linked rooms and pillar halls: the two rooms and the pillar hall | relative RMSE ≤ 0.20, \|bias\| ≤ 0.05 |
| Leak, unlit leak house | ≤ 0.001 of the outside |
| Time, Crytek Sponza at 1080p on the RTX 2070 | median ≤ 6 ms, maximum ≤ 12 ms |
| Determinism | bit-identical |
| HDR-FLIP | per camera, below |

**HDR-FLIP.** A camera's limit is the FLIP between the reference's final image and the same image with the reference's `E/π` perturbed to the indirect-error limits: scaled by 1 ± the bias limit and by value noise on a world lattice at the scene's texel spacing, sized to the RMSE limit, whichever sign of the bias gives the smaller FLIP (`metrics.py flip-limit`). The floor, reported and not gated, is the FLIP between the reference's final image and its path-traced frame (`flip-floor`). On the downloaded scenes the floor is 1.7 to 4.0 times the limit: Godot's ready-made direct light, shadows and reflections sit further from path tracing than the GI may. The unlit leak house measures leaks only, so it has no FLIP limit.

| Scene | Camera | Limit | Floor |
|---|---|---|---|
| Cornell box | Front | 0.072 | 0.058 |
| Leak house | Back | 0.085 | 0.082 |
| Leak house | Facade | 0.023 | 0.041 |
| Leak house | InsidePlane | 0.084 | 0.061 |
| Leak house | InsideThick | 0.070 | 0.065 |
| Two rooms | RoomA | 0.157 | 0.104 |
| Two rooms | RoomB | 0.106 | 0.120 |
| Pillar hall | Aisle | 0.130 | 0.092 |
| Pillar hall | Corner | 0.154 | 0.101 |
| Pillar hall | End | 0.157 | 0.125 |
| Small objects | Low | 0.028 | 0.050 |
| Small objects | Overview | 0.029 | 0.052 |
| Crytek Sponza | Arcade | 0.066 | 0.209 |
| Crytek Sponza | Atrium | 0.079 | 0.270 |
| Crytek Sponza | Gallery | 0.062 | 0.180 |
| Intel Sponza | PhysCamera001 | 0.085 | 0.227 |
| Intel Sponza | PhysCamera002 | 0.100 | 0.225 |
| Intel Sponza | PhysCamera003 | 0.097 | 0.240 |
| Intel Sponza | PhysCamera004 | 0.058 | 0.231 |
| Intel Sponza | PhysCamera005 | 0.093 | 0.213 |
| Intel Sponza | PhysCamera006 | 0.081 | 0.223 |
| Bistro exterior | Camera | 0.102 | 0.226 |
| Bistro exterior | Corner | 0.115 | 0.191 |
| Bistro exterior | Plaza | 0.074 | 0.143 |
| Bistro exterior | Terrace | 0.098 | 0.206 |
| Bistro interior | Camera | 0.056 | 0.161 |
