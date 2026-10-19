# 2D Radiance Cascades in OPEngine

| | |
|---|---|
| Author | Otavio Peixoto |
| Date | Commits to the RC renderer 2024-06-01 to 2024-06-05; repository created 2023-10-07 |
| Kind | Article (portfolio page) and C++/OpenGL repository |
| Link | https://otaviopeixoto1.github.io/portfolio/2DRadianceCascades/ ; https://github.com/Otaviopeixoto1/OPEngine (`src/render/RadianceCascades/`, shaders in `data/shaders/RadianceCascades/2D/` and `data/shaders/2D/LineDraw/`) |
| License | None stated |

A 2D RC renderer inside the author's own OpenGL engine. Light comes from strokes the user paints with the mouse. Each cascade is a full-size square texture, rays are sphere-traced through a distance field, and cascades merge top-down with bilinear weights over four upper probes and an average over four upper rays. The page and the repository give no timings, no hardware and no tested resolution.

File and line references below are to `Radiance2DRenderer.h` (here `R.h`) or to the named shader, on the `main` branch. Everything marked "read from the code" was not run.

## Contents

- [Article](#article)
- [Parameters and storage](#parameters-and-storage)
- [Cascade layout (MarchCascade.frag 45-55)](#cascade-layout-marchcascadefrag-45-55)
- [Intervals](#intervals)
- [Tracing (MarchCascade.frag 32-40)](#tracing-marchcascadefrag-32-40)
- [Merging (MergeCascades.frag 37-80; R.h 329-351)](#merging-mergecascadesfrag-37-80-rh-329-351)
- [Final pass (RenderRadiance.frag 16-67)](#final-pass-renderradiancefrag-16-67)
- [Distance field (genLineSDF.frag; R.h 103, 180)](#distance-field-genlinesdffrag-rh-103-180)
- [Issues read from the code](#issues-read-from-the-code)

## Article

- Each cascade has 4× the rays per probe and 4× fewer probes, with probe spacing doubling per axis.
- The page says rays reach twice as far per cascade. The code uses 4× (see Intervals).
- Probes must be placed uniformly; the page states no other constraint.
- Merging takes the 4 nearest upper probes and the 4 upper rays that share the current ray's direction.
- The final pass sums cascade radiance per pixel.
- Sharp shadows are represented poorly.
- The memory-layout figure draws 4 cascades and the march figure draws 5.
- The repository README credits tmpvar's playground, fad's and Suslik's Shadertoys, and Sannikov's paper.

## Parameters and storage

| Constant (R.h 53, 68-70) | Value | Meaning |
|---|---|---|
| `MAX_CASCADES` | 10 | Upper bound on cascades, used incorrectly (see cascade count) |
| `c0Angular` | 4 | Rays per probe at cascade 0 |
| `c0Interval` | 4 | Interval length of cascade 0, in px |
| `c0Spacing` | 2 | Probe spacing of cascade 0, in px |

- The region is square with side `R = max(viewportW, viewportH)` (R.h 64, 71).
- Storage side `S = floor(R / c0Spacing)·sqrt(c0Angular)`, so `S = R` for even `R`.
- Cascade count (R.h 74-78): `N = min(floor(log2(4·√2·R)/2) − 1, max(ceil(log2(S/√c0Angular)), MAX_CASCADES))`. The `max()` with `MAX_CASCADES` makes 10 a floor of the second term instead of a cap, which looks unintended; the first term decides in practice. 1920×1080 gives `N = 5` (cascades 0 to 4) and 512×512 gives `N = 4`.
- Textures (R.h 107-115, 146-154): `N + 1` square `S × S` RGBA16F textures with `GL_LINEAR` filtering, one per cascade plus one ping-pong buffer for merging. The distance field uses two viewport-sized RGBA16F textures, ping-ponged.
- Memory at 1920×1080: 6 × 1920² × 8 B = 176.9 MB for cascades and 2 × 1920 × 1080 × 8 B = 33.2 MB for the distance field.

## Cascade layout (MarchCascade.frag 45-55)

- `rayCount_i = c0Angular·4^i = 4^(i+1)`: 4, 16, 64, 256, 1024.
- Each probe is a `probeSize × probeSize` texel block with `probeSize_i = 2^(i+1)`. `probePos = floor(texel / probeSize)` and `rayIndex = ty·probeSize + tx`, row-major inside the block. This is the position-first layout.
- Probe spacing is `2^(i+1)` px. At 1920 the probes per axis are 960, 480, 240, 120 and 60, so every cascade holds `S²` texels.
- Ray direction: `θ = 2π(rayIndex + 0.5)/rayCount`, `dir = (cos θ, −sin θ)` (lines 22-29, 61-62).
- Probe UV = `(probePos + 0.5)·spacing / (viewportW, viewportH)`; the ray starts at `probeUV + dir·minimum / R`.

## Intervals

- Raw interval (lines 61-62): `minimum_i = c0Interval·(4^i − 1)/3`, `range_i = c0Interval·4^i`. In px: [0, 4], [4, 20], [20, 84], [84, 340], [340, 1364].
- Overlap adjustment (lines 68-69): `minimum −= (range_i / 4)·sign(i − 1)`, then the length is recomputed. Effective intervals: cascade 0 [1, 4], cascade 1 [4, 20], cascade 2 [4, 84], cascade 3 [20, 340], cascade 4 [84, 1364].
- From cascade 2 up, each cascade starts where the one below it starts, so it re-traces the whole lower interval from its own, coarser probe positions. Since the merge only runs where the lower ray missed (see Merging), a hit inside the re-traced range seen from the upper probe's position can still reach the result after the lower ray missed it (derived from the code, not tested).
- Cascade 0 starts 1 px out from the probe instead of at 0.
- The top cascade reaches 1364 px at `N = 5`, short of the 2716 px diagonal of a 1920×1080 frame.

## Tracing (MarchCascade.frag 32-40)

- Sphere tracing in UV: `rt = range / R`; each step reads `sdf.r` as its length, `rd += d`, and `ray = start + dir·min(rd, rt)`.
- A miss is `rd ≥ rt` or the ray leaving `[0, 1)²`. A hit is `d < 1e-4` and returns the emission with alpha 1.
- The loop cap is `ii < range`: 3, 16, 80, 320 and 1280 iterations for cascades 0 to 4. The cap is sized as if each step covered 1 px, but it counts sphere-tracing steps, which can be shorter near surfaces, so a ray can stop before its interval ends.

## Merging (MergeCascades.frag 37-80; R.h 329-351)

- The loop runs `i = N − 1` down to 1. Cascade `i` is the upper input: the raw top cascade at `i = N − 1`, otherwise the buffer merged in the previous step. The shader uniform `cascadeIndex` is `i − 1`, the cascade being written; the renderer's comment calls it the upper index.
- A texel whose alpha is 1 (a hit) is skipped.
- Upper base index per axis = `floor((p − 1)/2)`, with weight `0.25 + 0.5·(p − (2·base + 1))`, so 0.25 or 0.75. These are the correct bilinear weights for upper probe centers at `(2j + 1)·spacing`.
- For each of the 4 upper probes the shader reads upper rays `4·rayIndex + k`, `k = 0..3`, averages them, and blends the four results bilinearly. The sum is added to the current radiance and alpha is set to 1.
- 16 upper texel reads per texel (4 probes × 4 rays); there is no pre-averaging pass.

## Final pass (RenderRadiance.frag 16-67)

- `probePos = sceneCoord/2 − 0.5`. The shader averages the 4 cascade-0 rays of each of the 4 nearest probes with equal weights and blends the probes bilinearly.
- There is no cosine term and no 2π factor, so the output is mean radiance.

## Distance field (genLineSDF.frag; R.h 103, 180)

- The field is not built by jump flooding. Each mouse stroke is a quadratic Bezier from mid(A, B) through B to mid(B, C), with distance `sdBezier(uv) − brushRadius`.
- Update rule: `sd = min(d, sd)` where `d < max(0, sd)`, and the emission takes the brush colour.
- Both buffers are cleared to `1e20`. RGBA16F tops out at 65504, so the clear stores +inf, and the tracer relies on inf acting as a far distance (IEEE conversion, read from the code).
- Distances are in UV, not px.

## Issues read from the code

- `FetchUpperCascade` (MergeCascades.frag 37-47) and `CascadeFetch` (RenderRadiance.frag 16-22) turn integer texel coordinates into UV without the +0.5 texel-center offset, and the y term `rayIndex / probeSize` has no floor. With `GL_LINEAR` the reads should land between texels and blend neighbouring rays and probes. A capture would confirm it.
- Probe positions divide by `(W, H)` but interval and step lengths divide by `R = max(W, H)`. At 1920×1080 one UV unit is 1920 px in x and 1080 px in y, so lengths are correct in px only for square viewports.
- At 1920×1080 cascade 0 holds 960 × 960 probes, of which 960 × 540 are on screen: 43.75 % of every cascade is off screen. R.h 64-66 says this is intentional.
- The renderer has profiler scopes (March Cascades, Merge Cascades, Capture Mouse) but no recorded numbers.
