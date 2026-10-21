# GI evaluation: FLIP, reference renderers and test scenes

| | |
|---|---|
| FLIP | https://github.com/NVlabs/flip (BSD 3-Clause, NVIDIA 2020 to 2025); package `flip-evaluator`, https://pypi.org/project/flip-evaluator/ |
| Mitsuba 3 | https://github.com/mitsuba-renderer/mitsuba3; plugin docs https://mitsuba.readthedocs.io/en/stable/ |
| Blender | glTF importer, https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html (search result) |
| Crytek Sponza | https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Sponza |
| Intel Sponza | https://www.intel.com/content/www/us/en/developer/topic-technology/graphics-research/samples.html |
| Bistro | https://developer.nvidia.com/orca/amazon-lumberyard-bistro |
| Read | 2026-10-20 |

Tools and assets for measuring GI against a reference: the FLIP image metric's Python package, offline renderers that can serve as references, and the licences and sizes of standard test scenes.

## FLIP's Python package

- `pip install flip-evaluator`, version 1.7 of 2025-11-07. PyPI lists Python 3.8 or newer and the GitHub page 3.10 or newer; the wheel metadata settles it.
- `evaluate(reference, test, dynamicRangeString, inputsRGB=True, applyMagma=True, computeMeanError=True, parameters={})` returns the error map, the mean error and the parameters used. `"HDR"` as the third argument selects HDR-FLIP.
- HDR inputs are H×W×C arrays of nonnegative linear sRGB values; the dtype is not stated. `load(path)` reads PNG, EXR, BMP and TGA.
- Pixels per degree default to 67. The start and stop exposures, their count and the tone mapper (ACES, Hable or Reinhard) are computed when not given; the docstring mislabels the stop exposure. With `computeMeanError=False` the mean comes back as −1.
- The repository's example, `src/python/api_example.py`, calls `flip.evaluate(ref, test, "HDR")` on EXR paths; its README's sample HDR output reads a mean of 0.283478.

## Reference renderers

- **Mitsuba 3** installs with `pip install mitsuba` from prebuilt wheels, under a BSD-style licence (copyright Wenzel Jakob, 2017; the clauses were not checked). Its mesh loaders read OBJ, PLY and its serialized format, not glTF. Its AOV integrator outputs albedo, depth, position, UV, geometric and shading normals, UV derivatives and primitive and shape indices, but no irradiance; `mi.cornell_box()` builds a Cornell box as a Python dictionary, not a file.
- **Blender** imports and exports glTF 2.0 (`.glb`, `.gltf`) with metallic-roughness and specular-glossiness materials, enabled by default. Cycles' pass list was not read.

**Inferred.** A glTF scene reaches Mitsuba only through conversion to OBJ or PLY, and irradiance from it has to be composed from path-traced output. On a diffuse surface that does not emit, the radiance is the albedo times `E/π`, so the radiance over the albedo AOV gives `E/π`; setting every albedo to one instead would change the light the surfaces exchange. Blender opens glTF directly.

## Test scenes

| Scene | Source and licence | Size |
|---|---|---|
| Crytek Sponza | Khronos glTF-Sample-Assets; the CRYENGINE Limited License Agreement, © 2016 Crytek, not Creative Commons. Credits: Crytek's OBJ export, Marko Dabrovic (2002 original), Frank Meinl (2010 improved version), Morgan McGuire (2011 revisions), Alexandre Pestana (PBR textures) | not stated on the page; about 260 K triangles from memory, unverified |
| Intel Sponza | Intel GPU Research Samples, Creative Commons Attribution for all downloads; 3ds Max 2022 source, USD, glTF and FBX | base scene 3.71 GB, curtains add-on 750 MB, ivy add-on 1.29 GB (an older copy listed 3.60 GB, 709 MB and 1.15 GB); no triangle counts given |
| Amazon Lumberyard Bistro | NVIDIA ORCA, CC BY 4.0, cited as "Amazon Lumberyard Bistro, Open Research Content Archive (ORCA)", 2017; FBX plus a Falcor scene file | interior 1,046,609 triangles, interior with wine 1,293,691, exterior 2,832,120 (a third-party blog gives 1,020,895 and 2,836,717) |
| Cornell box | No canonical glTF version found. A WebGL Cornell box under WTFPL (https://github.com/Vinc3r/cornellBox) has folders named for glTF exports, not checked | |

McGuire's Computer Graphics Archive (https://casual-effects.com/data/) returned no content, so its copies of Sponza and Bistro were not checked.
