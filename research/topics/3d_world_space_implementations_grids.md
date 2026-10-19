# 3D world-space implementations: dense grids and voxel clipmaps

Codes that store world-space cascades on dense probe grids or trace a world voxel clipmap: tmpvar's 3D grid, jumeder's DXR build, rbnelr's voxel game and other world probe grids, Mathis's voxel cascades with hemisphere probes, and creikey's screen probes traced through a voxel clipmap. The table of all world-space codes, the Split RC codes, erhe and the engine design documents, and the connections and single-frame assessment for these codes are in [3D world-space implementations](3d_world_space_implementations.md).

## Contents

- [Dense grids](#dense-grids)
  - [tmpvar's radiance-cascades-3d-grid](#tmpvars-radiance-cascades-3d-grid)
    - [Files](#files)
    - [Scene](#scene)
    - [Passes](#passes)
    - [Parameters and math](#parameters-and-math)
    - [Issues and notes](#issues-and-notes)
    - [References in the devlog and code](#references-in-the-devlog-and-code)
  - [jumeder/dx12-radiance-cascades](#jumederdx12-radiance-cascades)
  - [rbnelr/voxel_game](#rbnelrvoxel_game)
  - [Other world probe grids](#other-world-probe-grids)
  - [M3ycWt (Mathis): voxel cascades with hemisphere probes](#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes)
- [creikey/voxel-radiance-cascades](#creikeyvoxel-radiance-cascades)

## Dense grids

### tmpvar's radiance-cascades-3d-grid

| | |
|---|---|
| Author | Elijah Insua (GitHub: tmpvar) |
| Date | 2024-04-28 (last commit, 00:18:05 UTC) |
| Kind | Repository (C++, OpenGL compute) |
| Link | https://github.com/tmpvar/radiance-cascades-3d-grid |

A rough, unoptimized C++ and GLSL implementation of RC on a world-space dense 3D probe grid. The scene is an analytic signed distance function with one emitter sphere. The cascades are built once by sphere tracing rays from every probe into a 2D-array octahedral atlas, merged from the top level down, and read per pixel by a trilinear lookup of level 0 probes. The code includes headers from HotCart, an unreleased engine wrapper that is not in the repository, and the README states the project cannot run as published ([3D grid](../sources/2024_tmpvar_rc_3d_grid.md)).

#### Files

| File | Contents |
|---|---|
| README.md | Project description and media links; states the project is unrunnable without HotCart. |
| NOTES.md | Two short notes on reflection skew and merge interpolation. |
| DEVLOG.md | Dated log from 2024-01-30 to 2024-02-08, with Next and Pending lists. |
| radiance-cascades-3d-grid.cpp | App entry (CartSetup, CartLoop): sets up the camera, ticks the cascades, draws the final pass and debug UI, presents. |
| radiance-cascades/radiance-cascades.h | Host class RadianceCascades: init, level and memory math, Tick (build, copy, stitch, merge), debug UI and debug draws. |
| radiance-cascades/shared.h | RadianceCascadesConfig struct and OCTAPROBE macros, included by both C++ and GLSL. |
| shaders/shared.glsl | MapResult struct, pack and unpack, Lerp wrappers, scene `map()`, SDF primitives, boolean operations, normals. |
| shaders/octahedral.glsl | Octahedral encode and decode. |
| shaders/lerp.glsl | Lerp2D and Lerp3D for vec3 and vec4. |
| shaders/probes.glsl | World-to-probe-grid mapping, probe SDF (debug only), upper-grid index helpers. |
| shaders/radiance-cascades-build.comp | Ray march per atlas texel; writes one level. |
| shaders/radiance-cascades-merge.comp | Merges level `l+1` into level `l`. |
| shaders/radiance-cascades-octaprobe-stitch.comp | Copies interior edges and corners into the 1-texel border of each probe slot. |
| shaders/fractal.frag | Final pass: sphere traces the scene and shades hits from level 0 probes. |
| shaders/debug-probe-merge.frag | Debug view of one probe, its 8 upper probes and the merge results. |
| shaders/radiance-cascade-atlas-debug.frag | Debug view of atlas layers. |

Git history: five commits by the author, from 2024-04-27 to 2024-04-28. Referenced but not in the repository: `engine/dust.h`, `hotcart/hotcart.h`, `hotcart/types.h`, `hotcart/debug.h`, `engine/linalg.h`, `engine/gpu/morton.h` (MortonEncode, MortonDecode, MortonDecode2D), `engine/gpu/colormap-turbo.glsl`, and `engine/renderer/shaders/debug-fullscreen.vert` (the final pass uses it for its full-screen triangle).

#### Scene

- No voxels and no stored SDF. The scene is the function `map(p)` in `shaders/shared.glsl`, evaluated on demand. It returns a MapResult (distance `d`, colour, emission, throughput, level).
- Active scene (the `#if 1` branch): a solid red box of half-size 12; an inner box of half-size 11.8 subtracted, so the walls are 0.2 thick; a slab of half-size (18, 18, 0.3) centred at (0, 0, 12) subtracted, which removes the +Z wall so that side is open; and an emitter sphere of radius 1.4 at the origin, colour (1, 1, 1), emission (100, 100, 100), combined by union.
- Inactive scene (the `#else` branch): a white floor box of half-size (3.5, 0.25, 3.5) at (0, −3, 0) and a pink box of half-size (0.5, 2, 0.5) at (0, −1.25, 2.5), with no emitter.
- Union takes the minimum of the two distances; cut takes `max(a.d, −b.d)`; the material comes from whichever operand has the smaller `|d|`. After boolean operations the distance is a bound, not an exact distance.
- Normals use a four-tap tetrahedron difference with `h = 0.0001` (CalcNormal).
- The scene is static: `map()` reads no time or uniforms.
- At default settings the level 0 grid spans [−8, 8] on each axis, so the room walls at `|x|, |y|, |z| = 12` lie outside it; the emitter lies inside.

#### Passes

Tick returns early unless `debug.dirty` is set. Dirty is set at init, when any ImGui config value changes (ray length, scale, max level, branching factor), when the gather radius or ratio sliders change, and on keys 0 to 4 (max level). Passes marked [dirty] run only then; passes marked [frame] run every frame.

- **Init (once, `RadianceCascadesInit`):** `octahedralProbeAtlas`, a GL_TEXTURE_2D_ARRAY of RGBA32F, 4096 × 4096 × 7 layers, linear filter, clamp to edge; `octahedralProbeAtlasOriginal`, the same with nearest filtering; `configUBO`, a 48-byte copy of RadianceCascadesConfig. Debug defaults: atlas scale 1, render probe level −1, gather radius 1.0, gather ratio 0.75, sample-original off.
- **P1 [dirty]:** clear the atlas to zero (`glClearTexImage`).
- **P2 [dirty] Build** (`radiance-cascades-build.comp`): one dispatch per level, from `maxLevel` down to 0 (default 5, so levels 5 to 0). Uniform 0 is the level (`uint`), uniform 1 the ray range (vec2), the UBO is on binding 0 and the atlas on image binding 1, write-only. Local size 128; thread count = texels per probe × probes at that level, with no bounds check. A thread decodes `probe = id / rays`, `ray = id % rays`, texel `(ray % d, ray / d)` with `d = atlasProbeDiameter·2^level`, and direction `OctahedralDecode((texel + 0.5)/d)`. From the probe centre it marches `t` from `rayRange.x` to `rayRange.y`: if `map(origin + dir·t).d ≤ 0.001` it stores the hit (colour, emission, throughput 0) and stops, otherwise `t += max(1e−6, r.d)`, with no iteration cap. A miss stores colour 0, emission 0, throughput 1. The write goes to layer = level at slot origin + (1, 1) + texel, with slot origin `MortonDecode2D(probe)·(d + 2)`.
- **P3 [dirty]:** copy the atlas into the original atlas (`glCopyImageSubData`, all layers), which keeps build-only values.
- **P4 [dirty] Stitch** the original atlas for levels `maxLevel` down to 0 (`radiance-cascades-octaprobe-stitch.comp`): local size 16, uniform 0 the level, uniform 1 the probe count `N/8^level`; thread count = probe count, with an early return at or above it.
- **P5 [dirty] Merge and stitch loop** from level `maxLevel + 1` down to 0 (6 down to 0 by default). Each level: a memory barrier; the merge (`radiance-cascades-merge.comp`), one thread per texel of level `l` (`d_l²·probes_l`), local size 16, sampler unit 0 the atlas read with `texelFetch` from layer `l + 1`, image unit 1 the atlas read-write on layer `l`, uniform 0 the lower level; a memory barrier; the stitch for the same level with the P4 shader (see the uniform mismatch below).
- **P6 [frame] Final pass** (`fractal.frag`, a three-vertex triangle with `debug-fullscreen.vert`): uniforms 0 `worldToScreen` (mat4), 1 `screenToWorld` (mat4), 2 `eye` (vec3), 3 `fov` (float), 4 `screenDims` (vec2), 5 the sampler (merged atlas, or the original if sample-original is on), 6 `debugRenderProbeLevel` (default −1), 7 and 8 the gather offset and ratio (declared, unused here). One primary ray per pixel, up to 128 sphere-trace steps, a hit threshold of 2 × the cone radius at distance `t`, and a miss colour of (0.1, 0.1, 0.1).
- **P7 [frame, optional] Debug views:** `debug-probe-merge.frag` when "debug merge" is on; `radiance-cascade-atlas-debug.frag` draws one strip per level, left to right, when the render-atlas box is on.

#### Parameters and math

Defaults come from `RadianceCascadesDefaultConfig`.

| Field | Default | Meaning |
|---|---|---|
| gridDiameter | 64 | level 0 probes per axis, 64³ = 262,144 |
| scale | 0.25 | level 0 probe spacing in world units |
| rayLength | 0.05 | length of the level 0 interval, the base unit for all intervals |
| atlasProbeDiameter | 6 | level 0 octahedral texels per side, interior only |
| OCTAPROBE_PADDING | 1 | border texels on each side of each probe slot |
| maxLevel | −1 | −1 builds levels 0 to `totalLevels − 2`, otherwise 0 to `maxLevel` |
| branchingFactor | 1 | shown in the UI only; no shader or build path reads it |

| Level | Probes per axis | Probes | Spacing | Texels per probe | Slot (`d + 2`) | Interval | Rays |
|---|---|---|---|---|---|---|---|
| 0 | 64 | 262,144 | 0.25 | 6×6 = 36 | 8 | [0, 0.05) | 9,437,184 |
| 1 | 32 | 32,768 | 0.5 | 12×12 = 144 | 14 | [0.05, 0.2) | 4,718,592 |
| 2 | 16 | 4,096 | 1 | 24×24 = 576 | 26 | [0.2, 0.8) | 2,359,296 |
| 3 | 8 | 512 | 2 | 48×48 = 2,304 | 50 | [0.8, 3.2) | 1,179,648 |
| 4 | 4 | 64 | 4 | 96×96 = 9,216 | 98 | [3.2, 12.8) | 589,824 |
| 5 | 2 | 8 | 8 | 192×192 = 36,864 | 194 | [12.8, 51.2) | 294,912 |
| 6 | 1 | 1 | 16 | 384×384 = 147,456 | 386 | [51.2, 204.8) | not built |

- **Placement:** level `l` has `D_l = 64 >> l` probes per axis at spacing `s_l = 0.25·2^l`; probe `i` sits at `(i + 0.5 − D_l/2)·s_l`, so the grid is centred on the origin and spans 16 units at every level. The probe index is the 3D Morton index of the cell.
- **Directions:** octahedral, with +Y at the map centre (0.5, 0.5), −Y at the four corners and the edge midpoints at ±X and ±Z. Encode divides by the L1 norm and folds the lower hemisphere; encode and decode are inverses. Directions per probe are `36·4^l`, probes `262,144/8^l`, so rays per level halve.
- **Intervals:** `rayRange(l) = [start, end)` with `end = rayLength·4^l` and `start = 0` at level 0, else `rayLength·4^(l−1)`. They are contiguous, from the probe centre.
- **Atlas:** one array layer per level. A probe slot is `(d + 2)` texels square at `MortonDecode2D(probe)·(d + 2)`. `atlasGridDiameter = NextPowerOfTwo(√262,144) = 512` slots per side at level 0, and `baseDiameter = NextPowerOfTwo(512·8) = 4096`, assuming NextPowerOfTwo returns a power of two unchanged (the header is missing). Level 0 fills its layer exactly (262,144 × 64 = 4096² texels). The share of each layer used by slots is 38.3% at level 1, 16.5% at 2, 7.6% at 3, 3.7% at 4, 1.8% at 5 and 0.9% at 6.
- **Memory** (RGBA32F, 16 bytes per texel): one layer 256 MiB, one 7-layer atlas 1,792 MiB, the original copy 1,792 MiB, both 3,584 MiB. The Init printout says 1,792 MB; the value is in MiB. Interior texels hold 283.5 MiB, 15.8% of one atlas (derived, [3D world space](3d_world_space.md#memory-and-rays)).
- **Packing** (four 32-bit words per texel): x colour rgb as `packUnorm4x8` (8 bits per channel, clamped to [0, 1]); y `emission.xy` as half2; z half2(`emission.z`, `throughput.x`); w half2(`throughput.yz`). `d` and `level` are not packed.
- **Merge** per lower texel, from the top level down. The upper index per axis is `idx = (p + 0.5)·(d_l/d_(l+1)) − 0.5`, which is `p/2 − 0.25` since `d_(l+1) = 2·d_l`:

```
vec3 index = (lowerProbeGridPos + 0.5) * lowerAtlasProbeDiameter / upperAtlasProbeDiameter - 0.5;
vec3 upperProbeGridPos = clamp(floor(index), vec3(0.0), vec3(config.gridDiameter >> upperLevel));
vec3 hi = vec3((config.gridDiameter >> (lowerLevel + 1)));
t = fract(index);
```

  Eight upper probes at `base + {0,1}³`, each clamped to `hi`, get trilinear weights from `t`. For each, lower texel `t` maps to upper texels `2t` and `2t + 1` per axis, averaged with weights 0.25. The eight values combine trilinearly, then `color = lower.color + upper.color·lower.throughput`, `emission = lower.emission + upper.emission·lower.throughput`, `throughput = lower.throughput·upper.throughput`. Lower values are the build values read from the texel before it is written; upper values come from layer `l + 1`, already merged. A lower hit (throughput 0) blocks upper contributions, a lower miss passes them. Layer `l + 1` for the top merge (level 6) does not exist and reads zero; layer 6 is never built with default settings, so the merged throughput is zero at every level. Colour and emission do not depend on merged throughput, because the merge reads only the lower texel's build throughput.
- **Stitch**, one thread per probe (`d = atlasProbeDiameter·2^level`): interior texels are 1 to `d` per axis and border texels 0 and `d + 1`. Each border edge copies the adjacent interior row or column in reverse order (index `i` maps to `d + 1 − i`), the octahedral edge wrap, and each corner copies the diagonally opposite interior corner.
- **Final gather** per hit pixel: surface point `pos`, normal `n = CalcNormal(pos)`, level 0 grid coordinate `g = pos/scale + D/2` (WorldToProbeGrid), `base = floor(g)`, `t = fract(g)`. The eight probes at `base + {0,1}³` are read at level 0 in direction `n`: `ReadProbeLinear` takes `uv = OctahedralEncode(n)`, `src = slot origin + uv·d + 0.5`, and blends the four texels at `floor(src) + {0,1}²` bilinearly with `fract(src)`, edge reads using the border texels. The eight values blend trilinearly with `t`. The output is the rgb of emission only: albedo is not multiplied in, and the hit surface's own emission is not added.
- **Cost** (no timings recorded): one full build traces 18,579,456 rays for levels 0 to 5, each step evaluating `map()` once (four primitives, three boolean operations). Merge threads for levels 0 to 6 total 18,726,912, each reading 32 texels. Each hit pixel calls `map()` four times for the normal and reads 32 texels for the probe lookup.

#### Issues and notes

Author notes (NOTES.md): skewed-looking reflections suggest a problem in the merge, and the merge is not a plain 0.25/0.75 blend because a lower probe can sit in a negative cell relative to the upper cascade. DEVLOG pending items: a computed probe view, and pentalinear interpolation for the merged view so it can be compared with the expected value. DEVLOG next items: lit fog by sampling probes along a DDA, possibly pre-cooked into a small voxel grid; a grid layout with deinterleaved directions; a second test scene for reflections; non-cubic cascade diameters (the atlas packing would have to change); ray data in octahedral maps (the atlas already uses them).

Code TODOs and comments: "TODO: memory barrier for image reading" before the final pass (`radiance-cascades-3d-grid.cpp`); "TODO: make this multiplier a slider" for the cone radius factor (`fractal.frag`); "replace by an appropriate value" on the finite-difference step `h` (`shared.glsl`, `fractal.frag`); a commented line samples along `reflect(rayDir, normal)` while the active line samples along the normal; commented lines multiply the probe value by `result.color`, inactive.

Found by reading (not executed):

1. The merge's upper-index clamp is one too high: both the clamp on `floor(index)` and `hi` use `D_(l+1)`, while valid indices are 0 to `D_(l+1) − 1`, so for the last lower probe one of the eight upper neighbours lies outside the grid.
2. Merge edge weights are wrong for lower probe 0: its `idx` is −0.25, the base clamps to 0, but `t = fract(−0.25) = 0.75` is not clamped, so 75% of the weight goes to upper probe 1 instead of 0. Interior probes are not affected.
3. The final gather is shifted by half a probe cell: WorldToProbeGrid puts probe centres at integer + 0.5, while SampleProbesWorldSpace uses floor and fract as if centres were at integers. The merge subtracts 0.5 and the gather does not; at level 0 with the default scale the shift is 0.125 world units.
4. The gather reads outside the grid for scene surfaces: the level 0 grid covers [−8, 8], the walls are at 12, so `x = 12` maps to 80 and `x = −12` to −16. Indices of 64 and above and negative coordinates fall outside the level, and negative values passed through `uvec3()` are undefined in GLSL.
5. The stitch probe-count uniform is set at the wrong location: the merge loop calls `glUniform1ui(2, levelProbeCount)`, but the stitch shader declares only locations 0 and 1. Location 1 keeps the value from the last P4 call (level 0, 262,144), so every P5 stitch covers 262,144 probe indices instead of `N/8^l`. Writes beyond a level's real count land in slots that level does not use, so output is unaffected, but each level launches 262,144 threads.
6. Build and merge have no bounds check on the thread index. The default dispatch sizes are multiples of their local sizes (128 and 16), so the defaults do not overrun; GLDispatch is HotCart code and its rounding is not visible.
7. Merge uniform locations 2 (gather offset), 3 (gather ratio) and 4 (`maxLevel`) are declared but unused. The gather sliders still set the dirty flag, so changing them triggers a full rebuild that does not read them; the values are used only in `debug-probe-merge.frag`.
8. `d` and `level` are not packed, and UnpackMapResult leaves them unset. The merge reads `d` from unpacked values and discards it; ProcessMaterial reads `level`, unset for scene primitives but unused on the scene-hit path.
9. The host builds `screenDims` from the width for both components (`radiance-cascades-3d-grid.cpp` line 136). The final pass takes its cone radius from `screenDims.y`, so the hit threshold is wrong when the window is not square.
10. Level 6 is never built: with the default `maxLevel` of −1, levels 0 to 5 are built and layer 6 stays zero, so rays longer than 51.2 world units are never cast.
11. Only emitter light is shaded: the build stores albedo, but the final pass never reads colour, and surfaces other than the emitter contribute no emission, so no light bounces off the walls.
12. The gather samples one direction, the surface normal, with no hemisphere integral, no cosine weight and no albedo.

#### References in the devlog and code

The DEVLOG cites tmpvar's 2D playground (https://tmpvar.com/poc/radiance-cascades/, [2D articles and demos](2d_articles_and_demos.md#tmpvars-playground)), Chen's 2020 Monter post on irradiance-probe interpolation seams ([related probe GI](related_probe_gi.md)) and Aaltonen's 2020 cascade-chain debug view, a mip chain packed into one atlas ([scene representation](scene_representation_and_tracing.md)). `octahedral.glsl` cites Narkowicz's 2014 octahedral encoding ([cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d)), pyalot's 2015 gist and Stubbe's 2017 decode ([cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d)), and McGuire's GDC 2019 DDGI talk (https://www.gdcvault.com/play/1026182/, [related probe GI](related_probe_gi.md)).

### jumeder/dx12-radiance-cascades

https://github.com/jumeder/dx12-radiance-cascades (C++, D3D12 DXR and HLSL compute) is full 3D RC with hardware ray tracing in a Cornell box, with a BLAS per model and the TLAS rebuilt each frame. It shows why a naive full 3D grid is impractical ([voxel and RT repositories](../sources/2026_voxel_3d_rc_repositories.md#jumederdx12-radiance-cascades)).

- Four cascades with 32³, 16³, 8³ and 4³ probes over a 2×2×2 box. Directions are a lat-long grid of `(64 << i)×(32 << i)` texels: 2048 directions at cascade 0, 4× more per cascade.
- Memory: 512, 256, 128 and 64 MiB of RGBA16F, 960 MiB in total; 126 M rays per frame.
- Intervals grow 8× per cascade: ends at 0.031, 0.28, 2.28 and 18.3 units. The cascade 0 interval is shorter than the probe spacing.
- The hit shader returns only the instance's emission, so the result is one bounce from emitters.
- Merge: trilinear over 8 upper probes. Looking up the same direction UV in the 2× finer upper tile lands on a 2×2 texel corner, so the hardware linear filter averages the four child directions.
- Shading integrates 2048 directions × 8 trilinear taps per pixel (16,384 samples), with no solid-angle weight for the lat-long grid and no temporal reuse.

The 2×2×2 box at 32³ gives a spacing of 0.0625, so cascade 0's interval (0.031) is half a spacing (derived). The 8× interval growth with 4× directions is the `l = 8, K = 4` point, which by Split RC's error rule makes the angular error at each ray's end grow 4× per cascade against a 2× spacing growth ([core theory](core_theory.md#two-criteria-for-interval-scaling-derived)) (derived).

### rbnelr/voxel_game

https://github.com/rbnelr/voxel_game (C++, OpenGL 4.6 compute) is a Minecraft-style engine with two experimental RC modules drawn only as debug views ([voxel and RT repositories](../sources/2026_voxel_3d_rc_repositories.md#rbnelrvoxel_game)).

- Scene: a 512³ window of R16UI block ids (256 MiB) addressed with `coord & 511`, so moving one chunk rewrites only the new slab. A matching R8I distance field (128 MiB) is built per chunk: mark solid cells and their neighbours, then sweep lines along x, y and z with `min(previous + 1)`, giving an L1-style distance within each chunk.
- Tracing steps by the distance field when it is above 1 (step `n·(1 − ε)/(|dx| + |dy| + |dz|)`, which cannot skip a solid cell) and falls back to a voxel DDA near surfaces.
- 2D module: a horizontal slice of the world, 7 cascades, base spacing 0.125 m, 4 rays at cascade 0, intervals `[√2·0.125·4^(k−1), √2·0.125·4^k]` m, about 145 MB of RGBA16F, 18 M rays per frame, with the bilinear fix.
- 3D module: a single cascade, 25³ probes 4 m apart, 2×2 octahedral directions, no merging.

### Other world probe grids

**SultanAladin/RadianceCascades** (https://github.com/SultanAladin/RadianceCascades, Vulkan GLSL compute): world probe grids with octahedral direction tiles per probe; an 8-probe trilinear merge that samples each upper probe along the direction toward the lower interval's end, a 3D bilinear fix; octahedral tiles filtered by hand so they do not bleed; sparse SDF bricks with brick skipping and 64 steps; and the nearest hit across SDF instances shaded with per-instance albedo ([survey](../sources/2026_rc_repository_survey.md#3d)).

**mpalenque/sim** (https://github.com/mpalenque/sim, three.js): a world probe grid with spacing ×2 and octahedral directions ×4 per level, intervals `base·(4^i − 1)/3` to `base·(4^(i+1) − 1)/3`, cone tangent `2/√dirs`, an 8-corner merge, and cascade 0 resolved into an SH volume ([survey](../sources/2026_rc_repository_survey.md#3d)).

**AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades** (https://github.com/AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades). The default branch `main` (and `develop`, `feature/caustics`) is a Vulkan compute path tracer (`Vulkan-Engine/shaders/raytracer.comp`, 972 lines: spheres, triangles, planes, quads, cubes, a BVH, PBR, glass, fog, depth of field, SSAA, soft shadows; `feature/caustics` adds photon mapping). The RC lives on other branches, which start with commit 52e595e (2026-05-25, "Started Phase 7: The Allocation Pass"):

| Branch | Tip | State |
|---|---|---|
| `scene-swapper` | 14752f4 (2026-06-17) | most complete; the README names it the latest |
| `refactor/radiance-cascades` | 9bb9cd3 (2026-06-16) | same RC files |
| `merge-caustics-RC` | b201233 (2026-06-05) | RC merged with the caustics layer |
| `merge-caustics-RC-second-bounce` | 9b04c58 (2026-06-05) | adds a world-space SH cache for second-bounce colour bleeding (`probe_shcache.comp`) |
| `testing-scaling-tex`, `testing-no-artifacts` | b2839fc, 462d305 | partial experimental shaders |

The design on `scene-swapper` (`include/gi/CascadeConfig.hpp`, `shaders/rc/*.comp`, `reference-files/technical_manual.md`):

- **Hierarchy:** a 3D world-space grid. `numCascades = 5` in the config, while the manual documents 3 levels. Level `k` has probe spacing `0.5·2^k`, an octahedral map of `4·2^k` texels per side (16, 64, 256, … directions), and a grid that halves per level from 64 × 60 × 92.
- **Intervals:** `end(k) = 0.5·4^k`, `start(k) = end(k − 1)`, so [0, 0.5], [0.5, 2], [2, 8], [8, 32], [32, 128]. Spacing doubles while interval length grows ×4.
- **Sparse probes:** level 0 probes are allocated from G-buffer pixels and level `k > 0` from the parent slots their children need; each level has a GPU hash map (`probe_alloc.comp`, `CascadeHashMap.cpp`) filled bottom-up with atomic inserts.
- **Tracing:** `probe_trace.comp` runs one thread per (slot × octahedral texel) ray, with `tMin = start + 0.001` and `tMax = end`, testing analytic planes and quads and then a BVH. It stores FP16 radiance and transmittance; level 0 adds direct light with shadow rays.
- **Merge:** `cascade_merge.comp` runs top-down, trilinear over the 8 parent probes and 2 × 2 bilinear over the parent's octahedral map, with `L = near.L + near.T·far.L` and `T = near.T·far.T`.
- **Gather:** `final_gather.comp` interpolates the 8 surrounding level 0 probes trilinearly; `probe_sh.comp` pre-integrates level 0 into SH.
- **Recorded bugs (manual):** BUG-1, darkening at grid borders from an uninitialized transmittance accumulator for missing parents; BUG-2, probe shadows that ignored walls, fixed with analytic plane and quad shadow tests; BUG-3 and BUG-4, typos. Both fixes are present at all four branch tips: `cascade_merge.comp`, identical on all four, starts the accumulator at `parentAccum = vec4(0.0, 0.0, 0.0, 1.0)` (line 97), and `probe_trace.comp` tests analytic planes and quads before the BVH shadow call in both its hard and soft shadow paths. The repository keeps these files under `Vulkan-Engine/`.
- No timings are published.

It is the only sparse hashed world-space RC with per-probe tracing (no ray splitting) whose code is complete enough to read end to end ([survey](../sources/2026_rc_repository_survey.md#alimoghimiivulkan-ray-tracing-with-radiance-cascades-3d-world-space-rc-on-branches)). With `K = l = 4` and 16 cascade 0 directions, its `t0 = 0.5` against a spacing of 0.5 is one spacing, below the equal-error 1.13 for 16 directions ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)) (derived). BUG-1 is the 3D form of the missing-parent case that sparse trilinear renormalization exists to handle ([3D world space](3d_world_space.md#placement-and-levels-of-detail)) (inference).

### M3ycWt (Mathis): voxel cascades with hemisphere probes

"Volumetric" in the Shadertoy's title ("Volumetric Radiance Cascades", 2025-02-08) means a voxel volume; there are no participating media ([Shadertoys](../sources/2023_rc_shadertoys_hrc_3d_and_other.md#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes)).

- A procedural 32×32×48 voxel room (columns, arches, cloth, a fountain lamp, a partial roof, a moving floor emitter and a moving sphere), rebuilt each frame and traced by voxel DDA for up to 128 steps. A sun shadow map stores the distance to the first solid voxel along the sun.
- Five levels with probe grids from 32×32×48 (spacing 1) to 2×2×3 (spacing 16). Each probe has six hemispheres, one per face normal. Level `L` uses an `s×s` grid per hemisphere with `s = 3·2^L`: level 0 has the normal plus 8 directions at 45°, and higher levels use concentric square rings with polar angle `(ring/s)·π` and `4 + 8k` azimuth bins per ring (Common:96-121). Each texel stores radiance times solid angle over `2π` times `cos θ`; `w` holds the hit distance (1e7 for sky, −1 for an invalid probe).
- Level 0 traces from every empty voxel, 0.25 voxels off each face; coarser levels move the probe toward an empty fine voxel by ±0.05 per axis.
- There are no intervals: every ray runs to its first hit. A hit distance `t` keeps the probe's own value below `2^L` voxels, hands over to the parent beyond `3·2^L`, and blends linearly between (Cube A:258-259).
- The parent value blends eight parent probes trilinearly. For each, the parent hemisphere facing the child is read in the one direction pointing at the child; if that stored distance is shorter than the offset minus 0.5, the parent counts as occluded and its weight drops to `10^−5` (Cube A:44-103). This is the same visibility test as X3XfRM's ([3D surface probes](3d_surface_probes.md)).
- Hits add the shadowed sun and last frame's level 0 irradiance in front of the hit, times albedo, so each frame adds a bounce and level 4 reaches level 0 in about four frames. The camera pass sums nine level 0 texels in front of the hit, adds the sun, multiplies by albedo, and applies an ACES fit and a 0.45 power.
- Found in the code: level 0's direction weights use uncentred grid coordinates, so the zenith texel gets a ring weight of 0.088 and a corner texel the centre weight of 0.293; stored values weighted by solid angle over `2π` make the indirect term half of Lambert's `E/π`, while the sun term has no `1/π` at all; the visibility test uses the parent's nominal position rather than its nudged one; `BRDF_GGX` is defined and never called.

Hit-distance hand-over in place of intervals is a soft split: each ray to its first hit feeds its own level near and its parent far, which is ray splitting with a linear blend between two cascades, the variant one sparse build found removed seams at twice the cost ([3D world space](3d_world_space.md#ray-splitting)) (inference).

## creikey/voxel-radiance-cascades

https://github.com/creikey/voxel-radiance-cascades (MIT; Rust, Sokol, GLSL compute on D3D11 and WebGPU) is screen-space RC at 640×360 whose probes sit on G-buffer pixels and whose intervals trace a world voxel clipmap, so it belongs to the screen-probes-with-world-intervals family ([3D screen space](3d_screen_space.md)). Its report has the most detailed timings of any small 3D RC project, and its tracer is the world-space part ([voxel and RT repositories](../sources/2026_voxel_3d_rc_repositories.md#creikeyvoxel-radiance-cascades)).

**Scene:**

- Static clipmap: four levels of 64³ cells, cell edge 1, 4, 16 and 64 m. One u32 per cell (albedo and density, unorm8) and two u32 of half-float radiance, 12 MiB in total.
- The clipmap recentres only when the camera moves more than 12 m from its centre, snapped to 2 m. A recentre rebuilds all four levels; there is no toroidal scrolling.
- Static radiance is albedo times direct light (sun, moon, ambient) with no shadow test, re-injected every frame, so probes see one bounce of unshadowed direct light.
- Dynamic objects go into a separate two-level clipmap (1 m and 4 m) rebuilt every frame as 8³ bricks per object. Overlaps resolve with `atomicMax` on the packed word, which fixed flicker from overlapping objects.

**Cascades:**

| Cascade | Probes | Directions | Interval (m) | Step (m) |
|---|---|---|---|---|
| 0 | 160×90 (every 4 px) | 32 | 0 to 1.6 | 0.1 |
| 1 | 80×45 | 128 | 1.6 to 6.4 | 0.3 |
| 2 | 40×23 | 512 | 6.4 to 25.6 | 1.2 |
| 3 | 20×12 | 2048 | 25.6 to 102.4 | 4.8 |

- Probes take the depth and normal of one G-buffer pixel. The ray origin is snapped to `max(0.125, 0.25·4^c)` m and pushed out along the normal by `0.82·4^c` m.
- Directions are a Fibonacci sphere with `N` points over the full sphere. The merge groups child indices `4k..4k+3`, which on a Fibonacci lattice share a height but spread around in azimuth.
- Each ray takes 16 samples. The clipmap level is chosen per sample from the distance along the ray, `LOD = clamp(0.5·log2(max(t/2, 1)), 0, 3)`, blending two levels, so the voxel size grows with distance like cone tracing.
- Extinction per sample is `clamp(0.36·density, 0, 0.9)`. Samples outside the cascade's own clipmap level add a faint sky term, and cascade 3 adds the sky after the loop.
- Merge: bilinear over 2×2 upper probes, four child directions each. The far transmittance is averaged, not multiplied.
- Cascade 0 becomes a 4×4 octahedral irradiance map per probe (32 directions, cosine weighted, weight 4π/32). Shading reads 2×2 probes bilinearly and the octahedral map bilinearly, with no border wrap.
- No temporal accumulation.

**Numbers** (D3D11, 640×360, GPU not named):

- Baseline GI compute 0.76 ms: trace 0.52 ms, merge and octahedral build 0.08 ms. Rays per frame: 1,884,160 with 16 samples each.
- Final build: 2.1 ms average, 2.5 ms worst, most of it G-buffer and shadow maps; trace 0.49 ms.
- Halving the cascade 0 spacing to 2 px (7.4 M rays) cost 3.5× the GPU time.
- Synthetic trace benchmark: 14.3 G rays/s on D3D11, 2.8 G rays/s on WebGPU in a browser.

**Lessons recorded:**

- Geometry thinner than one voxel leaks. Indirect detail is limited by the 4 px probe spacing and the 4×4 octahedral maps.
- A small emitter seen by only one or two cascade 0 directions becomes a bright firefly probe. The fix was to cap the emitter's injected radiance and add an analytic term for its nearby falloff.
- Screen-space contact AO multiplied onto the indirect light caused rings on terrain until same-material taps were skipped.

**Read against the cost model** (derived unless marked): the rays per cascade are 460,800, 460,800, 471,040 and 491,520, constant as on a flat surface, and they sum to the stated 1,884,160. Step lengths grow 3 to 4× per cascade with the ×4 intervals, so every ray takes 16 samples whatever its length; that is the filtered-proxy pairing that keeps `l = 4` affordable for a marcher ([3D world space](3d_world_space.md#marching-cost)). The per-sample LOD follows the gap between ray ends inside an interval. Averaging the far transmittance instead of multiplying it is an error unless each child holds one whole sample of the parent's transmittance (inference).
