# radiance-cascades-3d-grid

| | |
|---|---|
| Author | Elijah Insua (GitHub: tmpvar) |
| Date | 2024-04-28 (last commit, 00:18:05 UTC) |
| Kind | Repository (C++, OpenGL compute) |
| Link | https://github.com/tmpvar/radiance-cascades-3d-grid |

A rough, unoptimized C++ and GLSL implementation of radiance cascades on a world-space dense 3D probe grid. The scene is an analytic signed distance function with one emitter sphere. The cascades are built once by sphere tracing rays from every probe into a 2D-array octahedral atlas, merged from the top level down, and read per pixel by a trilinear lookup of level-0 probes. The code includes headers from HotCart, an unreleased engine wrapper that is not in the repository. The README states the project cannot run as published.

## Files

| File | Contents |
|---|---|
| README.md | Project description and media links. States the project is unrunnable without HotCart. |
| NOTES.md | Two short notes on reflection skew and merge interpolation. |
| DEVLOG.md | Dated log from 2024-01-30 to 2024-02-08, with Next and Pending lists. |
| radiance-cascades-3d-grid.cpp | App entry (CartSetup, CartLoop). Sets up the camera, ticks the cascades, draws the final pass and debug UI, presents. |
| radiance-cascades/radiance-cascades.h | Host class RadianceCascades: init, level and memory math, Tick (build, copy, stitch, merge), debug UI and debug draws. |
| radiance-cascades/shared.h | RadianceCascadesConfig struct and OCTAPROBE macros. Included by both C++ and GLSL. |
| shaders/shared.glsl | MapResult struct, pack and unpack, Lerp wrappers, scene map(), SDF primitives, boolean operations, normals. |
| shaders/octahedral.glsl | Octahedral encode and decode. |
| shaders/lerp.glsl | Lerp2D and Lerp3D for vec3 and vec4. |
| shaders/probes.glsl | World-to-probe-grid mapping, probe SDF (debug only), upper-grid index helpers. |
| shaders/radiance-cascades-build.comp | Ray march per atlas texel. Writes one level. |
| shaders/radiance-cascades-merge.comp | Merges level l+1 into level l. |
| shaders/radiance-cascades-octaprobe-stitch.comp | Copies interior edges and corners into the 1-texel border of each probe slot. |
| shaders/fractal.frag | Final pass. Sphere traces the scene and shades hits from level-0 probes. |
| shaders/debug-probe-merge.frag | Debug view of one probe, its 8 upper probes, and merge results. |
| shaders/radiance-cascade-atlas-debug.frag | Debug view of atlas layers. |

Git history: five commits by the author, from 2024-04-27 to 2024-04-28.

Referenced but not in the repository: engine/dust.h, hotcart/hotcart.h, hotcart/types.h, hotcart/debug.h, engine/linalg.h, engine/gpu/morton.h (MortonEncode, MortonDecode, MortonDecode2D), engine/gpu/colormap-turbo.glsl, engine/renderer/shaders/debug-fullscreen.vert (the final pass uses it for its full-screen triangle).

## Scene representation

- No voxels and no stored SDF. The scene is the function map(p) in shaders/shared.glsl. It returns a MapResult (distance d, color, emission, throughput, level) and is evaluated on demand.
- Active scene (the `#if 1` branch):
  - Solid box, half-size 12, color red.
  - Inner box, half-size 11.8, subtracted. The walls are 0.2 thick.
  - Slab, half-size (18, 18, 0.3), centered at (0, 0, 12), subtracted. This removes the +Z wall, so that side is open.
  - Emitter sphere, radius 1.4, centered at the origin, color (1, 1, 1), emission (100, 100, 100), combined by union.
- Inactive scene (the `#else` branch): a white floor box, half-size (3.5, 0.25, 3.5), centered at (0, -3, 0), and a pink box, half-size (0.5, 2, 0.5), centered at (0, -1.25, 2.5). This scene has no emitter.
- Union takes the minimum of the two distances. Cut takes max(a.d, -b.d). Material comes from whichever operand has the smaller |d|.
- After boolean operations the distance is a bound, not an exact distance.
- Normals use a four-tap tetrahedron difference with h = 0.0001 (CalcNormal).
- The scene is static. map() does not read time or uniforms.
- Probe coverage: at default settings the level-0 grid spans [-8, 8] on each axis. The room walls at |x|, |y|, |z| = 12 lie outside it. The emitter lies inside.

## Passes

Tick returns early unless debug.dirty is set. Dirty is set at init, when any ImGui config value changes (ray length, scale, max level, branching factor), when the gather radius or ratio sliders change, and on keys 0 to 4 (max level). Passes marked [dirty] run only then. Passes marked [frame] run every frame.

Init (once, RadianceCascadesInit):
- octahedralProbeAtlas: GL_TEXTURE_2D_ARRAY, RGBA32F, 4096 x 4096, 7 layers, GL_LINEAR filter, clamp to edge.
- octahedralProbeAtlasOriginal: same size and format, GL_NEAREST filter.
- configUBO: uniform buffer holding a copy of RadianceCascadesConfig (48 bytes).
- Debug defaults: atlas scale 1, render probe level -1, gather radius 1.0, gather ratio 0.75, sample original off.

[dirty] P1. Clear the atlas to zero (glClearTexImage).

[dirty] P2. Build (shaders/radiance-cascades-build.comp).
- One dispatch per level, from maxLevel down to 0. The default maxLevel is 5, so levels 5 to 0 run.
- Uniforms: location 0 = level (uint), location 1 = rayRange (vec2). UBO on binding 0. Image on binding 1 = atlas, write-only.
- Local size 128. Thread count = (texels per probe) x (probes at that level). The shader has no bounds check.
- Thread decode: probe index = id / rays, ray index = id % rays. Probe texel = (ray % d, ray / d), where d = atlasProbeDiameter x 2^level.
- Direction = OctahedralDecode((texel + 0.5) / d).
- Origin = probe center. March t from rayRange.x to rayRange.y. At each step, r = map(origin + dir * t). If r.d <= 0.001, store the hit (color, emission, throughput 0) and stop. Otherwise t += max(1e-6, r.d). There is no iteration cap.
- Miss: store color 0, emission 0, throughput 1.
- Write to layer = level at slot origin + (1, 1) + texel, where slot origin = MortonDecode2D(probe index) x (d + 2).

[dirty] P3. Copy the atlas into the original atlas (glCopyImageSubData, all layers). The original keeps build-only values.

[dirty] P4. Stitch the original atlas for levels maxLevel down to 0 (shaders/radiance-cascades-octaprobe-stitch.comp).
- Local size 16. Uniforms: location 0 = level, location 1 = probeCount = N / 8^level. Image on binding 1 = original.
- Thread count = probeCount. The shader returns early for indices at or above probeCount.

[dirty] P5. Merge and stitch loop, from level maxLevel+1 down to 0. For default settings this is 6 down to 0. Each level runs:
- Memory barrier.
- Merge (shaders/radiance-cascades-merge.comp). Thread count = d_l^2 x probes_l, one per texel of level l. Local size 16. Sampler unit 0 is the atlas, read with texelFetch from layer l+1. Image unit 1 is the atlas, read-write, writing layer l. Uniform location 0 = lowerLevel.
- Memory barrier.
- Stitch for the same level, using the same shader as P4. See Issues for the uniform mismatch.

[frame] P6. Final pass (shaders/fractal.frag, three-vertex triangle with debug-fullscreen.vert).
- Uniforms: 0 worldToScreen (mat4), 1 screenToWorld (mat4), 2 eye (vec3), 3 fov (float), 4 screenDims (vec2), 5 sampler (merged atlas, or original if sample-original is on), 6 debugRenderProbeLevel (default -1), 7 and 8 gather offset and ratio (declared, not used by this shader).
- Per pixel: one primary ray, up to 128 sphere-trace steps, hit threshold 2 x cone radius at distance t.
- Miss color: (0.1, 0.1, 0.1).

[frame, optional] P7. Debug views. debug-probe-merge.frag draws when "debug merge" is on. radiance-cascade-atlas-debug.frag draws one strip per level, left to right, when the render-atlas checkbox is on.

## RC parameters and math

Defaults (RadianceCascadesDefaultConfig):

| Field | Default | Meaning |
|---|---|---|
| gridDiameter | 64 | Level-0 probes per axis. Level-0 probe count = 64^3 = 262,144. |
| scale | 0.25 | Level-0 probe spacing in world units. |
| rayLength | 0.05 | Length of the level-0 interval in world units. Base unit for all intervals. |
| atlasProbeDiameter | 6 | Level-0 octahedral texels per side, interior only. |
| OCTAPROBE_PADDING | 1 | Border texels on each side of each probe slot. |
| maxLevel | -1 | -1 builds levels 0 to totalLevels-2. Otherwise builds 0 to maxLevel. |
| branchingFactor | 1 | Shown in the UI only. No shader or build path reads it. |

Per level, derived from the defaults. Level 6 is not built with the default maxLevel.

| Level | Probes per axis | Probes | Spacing (world) | Texels per probe | Slot size (d+2) | Interval (world) | Rays |
|---|---|---|---|---|---|---|---|
| 0 | 64 | 262,144 | 0.25 | 6x6 = 36 | 8 | [0, 0.05) | 9,437,184 |
| 1 | 32 | 32,768 | 0.5 | 12x12 = 144 | 14 | [0.05, 0.2) | 4,718,592 |
| 2 | 16 | 4,096 | 1 | 24x24 = 576 | 26 | [0.2, 0.8) | 2,359,296 |
| 3 | 8 | 512 | 2 | 48x48 = 2,304 | 50 | [0.8, 3.2) | 1,179,648 |
| 4 | 4 | 64 | 4 | 96x96 = 9,216 | 98 | [3.2, 12.8) | 589,824 |
| 5 | 2 | 8 | 8 | 192x192 = 36,864 | 194 | [12.8, 51.2) | 294,912 |
| 6 | 1 | 1 | 16 | 384x384 = 147,456 | 386 | [51.2, 204.8) | not built |

Rays = probes x texels per probe. One ray per texel.

Probe placement:
- Level l has D_l = 64 >> l probes per axis and spacing s_l = 0.25 x 2^l.
- Probe i along an axis has world center (i + 0.5 - D_l / 2) x s_l. The grid is centered on the origin.
- World extent D_l x s_l is 16 at every level.
- Probe index is the 3D Morton index of the grid cell. The Morton helpers come from engine/gpu/morton.h, which is not in the repository.

Directions:
- Octahedral mapping. +Y is at the map center (0.5, 0.5). -Y is at the four corners. The edge midpoints give +X, -X, +Z, -Z.
- Texel t of a d x d block has direction OctahedralDecode((t + 0.5) / d).
- Encode divides by the L1 norm, then folds the lower hemisphere. The encode and decode functions are inverses.
- Directions per probe = d^2 = 36 x 4^l. Probes = 262,144 / 8^l. Rays per level therefore halve at each level.

Intervals:
- rayRange(l) = [start, end). end = rayLength x 4^l. start = 0 for l = 0, and rayLength x 4^(l-1) for l >= 1.
- Intervals are contiguous. The ray origin is the probe center, and marching starts at start.

Atlas layout:
- One array layer per level. Layer index = level.
- Each layer is baseDiameter^2 texels. A probe slot is (d + 2) texels square. Slot origin = MortonDecode2D(probe index) x (d + 2).
- atlasGridDiameter = NextPowerOfTwo(sqrt(262,144)) = 512 slots per side at level 0.
- baseDiameter = NextPowerOfTwo(512 x 8) = 4096. This assumes NextPowerOfTwo returns its argument when it is already a power of two. The engine header is not in the repository.
- Level 0 fills its layer exactly (262,144 x 64 = 4096^2 texels).
- Share of each layer used by probe slots: level 1 38.3%, level 2 16.5%, level 3 7.6%, level 4 3.7%, level 5 1.8%, level 6 0.9%.

Memory (RGBA32F, 16 bytes per texel):
- One layer: 4096^2 x 16 bytes = 256 MiB.
- One atlas (7 layers): 1,792 MiB.
- Original copy: 1,792 MiB. Both atlases: 3,584 MiB.
- The Init printout reports 1,792 MB for one atlas. The value is in MiB.

Packing (four 32-bit words per texel):
- x: color rgb as packUnorm4x8. 8 bits per channel, clamped to [0, 1].
- y: emission.xy as half2.
- z: half2(emission.z, throughput.x).
- w: half2(throughput.yz).
- d and level are not packed.

Build values:
- Hit: color = material color, emission = material emission, throughput = 0.
- Miss: color 0, emission 0, throughput 1.

Merge, per lower texel, from the top level down:
- Upper-grid index per axis: idx = (p + 0.5) x (d_l / d_(l+1)) - 0.5. Because d_(l+1) = 2 d_l, idx = p/2 - 0.25.
- Code from radiance-cascades-merge.comp:

```
vec3 index = (lowerProbeGridPos + 0.5) * lowerAtlasProbeDiameter / upperAtlasProbeDiameter - 0.5;
vec3 upperProbeGridPos = clamp(floor(index), vec3(0.0), vec3(config.gridDiameter >> upperLevel));
vec3 hi = vec3((config.gridDiameter >> (lowerLevel + 1)));
t = fract(index);
```

- Eight upper probes at base + {0,1}^3, each clamped to hi. The weights are trilinear, using t. See Issues for the clamp.
- For each upper probe, the lower texel t maps to upper texels 2t and 2t+1 on each axis. The merge averages that 2 x 2 block with weights 0.25.
- The eight upper values are combined trilinearly. Then:
  - color = lower.color + upper.color x lower.throughput
  - emission = lower.emission + upper.emission x lower.throughput
  - throughput = lower.throughput x upper.throughput
- Lower values are the build values, read from the same texel before it is written. Upper values come from layer l+1, which was already merged.
- A lower hit (throughput 0) blocks upper contributions in that texel. A lower miss passes them through.
- Layer l+1 for the top merge (level 6) does not exist. The read returns zero. Layer 6 is never built with default settings, so the merged throughput is zero at every level. Color and emission do not depend on merged throughput, because merge reads only the build throughput of the lower texel.

Stitch, one thread per probe (d = atlasProbeDiameter x 2^level):
- Interior texels are 1 to d on each axis. Border texels are 0 and d+1.
- Each border edge copies the adjacent interior row or column in reverse order (index i maps to d+1-i). This is the octahedral edge wrap.
- Each corner copies the diagonally opposite interior corner.

Final gather, per hit pixel (fractal.frag):
- Surface point pos, normal n = CalcNormal(pos).
- Level-0 grid coordinate per axis: g = pos / scale + D/2 (WorldToProbeGrid).
- base = floor(g), t = fract(g). The eight probes at base + {0,1}^3 are read at level 0 in direction n.
- ReadProbeLinear: uv = OctahedralEncode(n). src = slot origin + uv x d + 0.5. Four texels at floor(src) + {0,1}^2 are blended bilinearly with fract(src). Edge reads use the border texels.
- The eight values are blended trilinearly with t.
- Output is the rgb of emission only. Color (albedo) is not multiplied in, and the hit surface's own emission is not added.

Cost (no timings are recorded in the code):
- One full build traces 18,579,456 rays for levels 0 to 5. Each ray step evaluates map() once. map() has four primitives and three boolean operations.
- Merge threads for levels 0 to 6 total 18,726,912. Each thread reads 32 texels.
- Each hit pixel calls map() four times for the normal and reads 32 texels for the probe lookup.

## Issues and notes

Author notes (NOTES.md):
- Reflections that look skewed suggest a problem in the merge.
- The merge is not a plain 0.25/0.75 blend. A lower probe can sit in a negative cell relative to the upper cascade.

DEVLOG pending items:
- Add a computed probe view.
- Make the merged view use pentalinear interpolation, so it can be compared with the expected value.

DEVLOG next items:
- Lit fog by sampling probes along a DDA, possibly pre-cooked into a small voxel grid.
- Grid layout with deinterleaved directions.
- A second test scene for reflections.
- Non-cubic cascade diameters. The atlas packing would need to change.
- Ray data stored in octahedral maps. The atlas already uses octahedral maps.

Code TODOs and comments:
- radiance-cascades-3d-grid.cpp: "TODO: memory barrier for image reading" before the final pass.
- fractal.frag: "TODO: make this multiplier a slider" (cone radius factor).
- shared.glsl and fractal.frag: "replace by an appropriate value" on the finite-difference step h.
- fractal.frag: a commented line samples along reflect(rayDir, normal). The active line samples along the normal.
- fractal.frag: commented lines multiply the probe value by result.color. Not active.

Found by reading (not executed):
1. Merge upper-index clamp is one too high. Both the clamp on floor(index) and hi use D_(l+1). Valid indices are 0 to D_(l+1) - 1. For the last lower probe, one of the eight upper neighbors has index D_(l+1), outside the grid.
2. Merge edge weights are wrong for lower probe 0. Its idx is -0.25. The base is clamped to 0, but t = fract(-0.25) = 0.75 is not clamped. So 75% of the weight goes to upper probe 1 instead of upper probe 0. Interior probes are not affected.
3. The final gather is shifted by half a probe cell. WorldToProbeGrid puts probe centers at integer + 0.5 (see Probe placement). SampleProbesWorldSpace then uses floor and fract as if centers were at integers. The merge subtracts 0.5 and the gather does not. At level 0 with default scale, the shift is 0.125 world units.
4. The gather reads outside the grid for scene surfaces. The level-0 grid covers [-8, 8] per axis, and the walls are at 12. The grid coordinate for x = 12 is 80, and for x = -12 it is -16. Indices of 64 and above, and negative coordinates, fall outside the level. Negative values passed through uvec3() are undefined in GLSL.
5. The stitch probe-count uniform is set at the wrong location. The merge loop calls glUniform1ui(2, levelProbeCount), but the stitch shader declares only locations 0 and 1. Location 1 keeps the value from the last P4 call, which is level 0 with 262,144. So every stitch dispatch in P5 covers 262,144 probe indices, not N/8^l. Writes for indices beyond a level's real probe count go to slots that level does not use, so output is not affected, but each level launches 262,144 threads.
6. Build and merge have no bounds check on the thread index. The default dispatch sizes are multiples of their local sizes (128 for build, 16 for merge), so the default config does not overrun. GLDispatch is HotCart code, and its rounding is not visible here.
7. Merge uniform locations 2 (gather offset), 3 (gather ratio), and 4 (maxLevel) are declared but unused. The gather radius and ratio sliders still set the dirty flag, so changing them triggers a full rebuild that does not read them. Those values are used only in debug-probe-merge.frag.
8. d and level are not packed. UnpackMapResult leaves them unset. The merge reads d from unpacked values and discards it. ProcessMaterial reads level, which is unset for scene primitives, but that field is not used on the scene-hit path.
9. Screen-size bug in the host. radiance-cascades-3d-grid.cpp line 136 builds screenDims from width for both components. The final pass computes its cone radius from screenDims.y, so the hit threshold is wrong when the window is not square.
10. Level 6 is never built. With the default maxLevel of -1, levels 0 to 5 are built and layer 6 stays zero. Rays longer than 51.2 world units are never cast.
11. Only emitter light is shaded. Build stores albedo, but the final pass never reads color. Surfaces other than the emitter contribute no emission, so no light bounces off walls in the output.
12. The gather samples one direction, the surface normal. There is no hemisphere integral, no cosine weight, and no albedo multiplication.

## Links found

- https://tmpvar.com/poc/radiance-cascades/ (README, the author's 2D version)
- https://handmade.network/p/75/monter/blog/p/7288-engine_work__global_illumination_with_irradiance_probes (DEVLOG, interpolation seams)
- https://twitter.com/SebAaltonen/status/1327188239451611139 (DEVLOG, cascade chain debug view)
- https://knarkowicz.wordpress.com/2014/04/16/octahedron-normal-vector-encoding/ (DEVLOG and octahedral.glsl)
- https://www.gdcvault.com/play/1026182/ (octahedral.glsl, DDGI reference)
- https://gist.github.com/pyalot/cc7c3e5f144fb825d626 (octahedral.glsl reference)
- https://twitter.com/Stubbesaurus/status/937994790553227264 (octahedral.glsl reference)
