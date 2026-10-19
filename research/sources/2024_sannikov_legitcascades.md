# LegitCascades: Sannikov's RC experiment scripts

| | |
|---|---|
| Author | Alexander Sannikov (Raikiri), with the chronicl fix by GitHub user chronicl |
| Date | 2024-10 to 2026-04 |
| Kind | Repository of LegitScript render graphs (MIT) |
| Link | https://github.com/Raikiri/LegitCascades |
| Run in browser | https://radiance-cascades.github.io/LegitScriptEditor/ (the README links `Scaling.ls`) |

The repository holds Sannikov's 2D experiments. `Scaling.ls` is a compact reference for plain RC with the bilinear fix. `ChroniclFix.ls` adds a cheaper fix for the upper cascades. Everything after 2025 explores holographic and polygonal variants in 2D and is listed briefly at the end.

## Scaling.ls: reference pipeline

### Frame structure

One atlas pass per frame computes every cascade at once. Cascade `k` merges with cascade `k+1` from the previous frame's atlas, so a change at the top cascade takes `N` frames to reach cascade 0. The passes are: scene to an rgba16f texture, atlas pass (reads the scene and last frame's atlas), copy the atlas to the previous-frame texture, final gather, debug overlay.

The scene is an orange emitting circle at the screen center and a black occluding circle at `center + (150, 50)`.

### Defaults

| Parameter | Default | Meaning |
|---|---|---|
| `c0_size.x` | 256 | width of the cascade 0 region in atlas texels; height follows the screen aspect |
| cascade count | 3 (4 in ChroniclFix) | |
| `dir_scaling` D | 4 | direction multiplier per cascade, also the interval ratio |
| `c0_probe_size` P | 2×2 | direction texels per cascade 0 probe, so 4 directions |
| `c0_dist` | 10 px (3 px in ChroniclFix) | interval length scale |
| `cm1_mult` | 1.0 | length of the cascade −1 interval in cascade 0 probe spacings |

### Layout

- Probe spacing per cascade is `screen_size / N_k`, with probe `i` at `(i + 0.5)·spacing`.
- Directions per probe: `dirs_k = P.x·P.y·D^k`. Each probe's direction block grows by `sqrt(D)` per axis, so with D = 4 every cascade uses the same atlas area.
- Cascade regions stack vertically in one atlas. An option lets regions halve or double per cascade instead.
- The active layout is direction-major: each direction is a block of probe texels (`texel = C·(dir mod B.x, dir div B.x) + probe`, where `C` is the probe count per axis and `B` the direction grid).
- Direction `j` of `n` points at angle `2π(j + 0.5)/n`.

### Intervals

Cascade `k` covers `[c0_dist·(D^k − 1) + cm1, c0_dist·(D^(k+1) − 1) + cm1]`, where `cm1` is one cascade 0 probe spacing. The intervals tile the ray with no gap. The final gather traces `[0, cm1]` per pixel, a per-pixel "cascade −1" that recovers contact detail finer than the cascade 0 grid. Beyond the top cascade, the far value is zero radiance with zero transmittance.

### Ray march

The march takes fixed steps of `2·spacing_scaling^k` pixels (so the step doubles per cascade), sampling the scene at the start of each step. It accumulates `L += rgb·T·a` and `T *= 1 − a`, where the scene alpha is opacity and the stored alpha is transmittance. The merge is `(near.rgb + near.a·far.rgb, near.a·far.a)`.

### Bilinear-fixed merge

For a cascade `k` probe at `p`, direction `d` and interval `[n, f]`:

1. Find the four cascade `k+1` probes around `p` and their bilinear weights. Clamp indices to the grid.
2. For each neighbor `P_j`, march from `p + d·n` to `P_j + d·f`, so the ray ends where that neighbor's interval starts.
3. Merge the march result with neighbor `P_j`'s stored value for the child direction, weight it, and sum.

Each cascade `k` texel averages its `D` child directions, so a cascade `k` texel costs `4·D` marches. The marched direction is `normalize(P_j + d·f − p − d·n)`, which differs slightly from `d`.

### Final gather

For each pixel, for each cascade 0 direction, run the same bilinear-fixed merge with the interval `[0, cm1]` and average over directions. The result is the mean radiance over directions (fluence divided by 2π), with no further normalization.

## ChroniclFix.ls: the chronicl fix

The chronicl fix replaces the four bent rays of the bilinear fix with straight ones.

1. Find the four cascade `k+1` neighbors and bilinear weights as before.
2. For neighbor `P_j`, intersect the ray `p + t·d` with the circle of radius `f` around `P_j` and take the far intersection `t`. March from `p + d·n` to `p + d·t`, which stays on the original direction.
3. Compute the direction from `P_j` to the exit point and convert it to a fractional direction index of cascade `k+1`. Linearly interpolate the neighbor's two nearest directions.
4. Merge, weight and sum as in the bilinear fix.

The code comment says the circle is the interval start of the upper probe, and the code's radius `f`, the end of cascade `k`'s interval, is exactly that start, since the intervals tile the ray. The intersection helper returns −1 when the ray misses the circle, which the caller does not check; its comment assumes the ray starts inside the circle. That holds only while `f` exceeds the distance from `p` to each of its four upper neighbours, up to `√2` upper spacings. With the defaults (128 cascade 0 probes across the screen, `c0_dist` = 3 px, D = 4), cascade 0 has `f` = 9 px against neighbours up to 42 px away at 1920 px width, and cascade 1 has 45 px against 85 px, while cascade 2 has 189 px against 170 px (computed from the script's formulas). A ray that starts outside the circle can miss it and march to `p − d`, or end at the wrong root, on exactly the two cascades where the checkerboard appears, which may be its cause (a hypothesis, not tested).

chronicl's patch drops the `cm1` offset, so cascade `k` covers `[c0_dist·(D^k − 1), c0_dist·(D^(k+1) − 1)]`, and adds two switches: "fix checkerboard", which uses the bilinear fix on cascades 0 and 1, and "force bilinear fix" for every cascade. `ChroniclFix.ls` in Sannikov's repository is the same file with "fix checkerboard" on by default, so cascades 0 and 1 use the bilinear fix because the chronicl fix shows a checkerboard on them. The author's comment calls this unoptimized version about as fast as the bilinear fix and says early tests put an optimized one at about 3× faster. The final gather here interpolates the stored cascade 0 texels bilinearly and marches no rays.

## Later experiments (2025–2026)

These scripts explore 2D variants and mostly test one idea each, often with a single hard-coded light and no scene. Several header comments link to another file (copied from it), and no script records results.

| Script | Idea |
|---|---|
| `EnergyConservingHRC.ls` | Probes on vertical planes. A partly covered direction bin splits its energy between emission (coverage) and transmittance (1 − coverage), so the bins conserve energy. |
| `ExtendedHRC.ls` | The same plane cascade built bottom-up by interval extension. |
| `BlockHRC.ls`, `IntegerBlockHRC.ls` | Square probe blocks, each holding a grid of lines (angle and offset); parents copy radiance from child blocks along the same lines. |
| `PolygonalHRC.ls`, `PolygonalHRC45.ls`, `PolygonalPrimalHRC.ls`, `PolygonalBlock*RC.ls` | Each texel covers a polygon (trapezoid or wedge) between two boundary lines instead of a ray, giving alias-free light from a one-pixel source (shown in the "Polygonal Radiance Cascades" video). |
| `GradientRC.ls` | Each interval stores a value and its slope, tested on 1/distance from a point source. |
| `Holograms.ls`, `HologramPropagation.ls`, `HolographicCharges.ls`, `BundleBasisExploration.ls` | Wave-optics (Fourier hologram) and line-bundle basis tests, not RC pipelines. |

The last commit, "Added 4x scaling RC" (2026-04-09), adds `PolygonalBlockExtendedRC4x.ls`, which is still a byte-identical copy of `PolygonalBlockExtendedRC.ls`.

### Plane cascades

Both scripts put probes on vertical planes 8 px apart, 8 px apart along each plane, with 2 directions at cascade 0. Cascade `k` has `planes >> k` planes 8·2^k px apart and `2·2^k` directions, with the probe spacing fixed, so the atlas width `planes·dirs` stays at W/4 on every level. The light is a vertical segment (by default at x = 100 px with height 100 px), and merging is `(near.rgb + near.a·far.rgb, near.a·far.a)`.

- **EnergyConservingHRC** traces nothing. A direction bin's coverage by the light is its angular overlap in bin units, `max(0, min(end, dir + 0.5) − max(start, dir − 0.5))`, stored as emission `color·coverage` with transmittance `1 − coverage`. The direction index of a slope is `(dy/dx·0.5 + 0.5)·dirs − 0.5`. Merging runs top-down over 6 cascades: an even plane reads parent plane `plane/2` and averages the two child directions `2·dir` and `2·dir + 1`; an odd plane reads parent plane `(plane + 1)/2` at probe `p − dirs/2 + dir`, also with weight ½. The final gather reads the nearest probe on the next plane and averages over directions.
- **ExtendedHRC** builds cascades 1 to 3 bottom-up from cascade 0 by extension. An even direction merges plane `2p` with plane `2p + 1` at probe `p + dir/2`, both in direction `dir/2`; an odd direction averages two such chains with the near and far directions swapped (`dir/2 + i` and `dir/2 + 1 − i`). The gather reads cascade 3. Found by reading: the direction mapping divides by `plane_spacing/(dirs·probe_spacing)` in integer arithmetic, which is 0 at every level (the exact value is ½), so the script divides by zero; a loop index in the unused top-down merge is uninitialized; and 6 cascades are configured while 5 images are allocated.

### Block cascades

- **BlockHRC:** a probe is an `N × N` block of texels indexing lines by angle (x) and offset (y). Level 0 has 30 px blocks with N = 20, and both the spacing and N double per level over 9 levels. The active parameterization ("diagonal line space") puts a line's origin on whichever block diagonal is closer to perpendicular to it, with angle `2π·x`; an angle-and-distance form, a circle line space and a box line space are defined but unused. Extension builds level `k` from the 2×2 child blocks of level `k − 1`: each parent line finds the child blocks it crosses with a ray–box test and reads the child line nearest in index (bilinear weights rounded). Weight normalization is commented out, so contributions are summed unweighted. The emitter is one level 0 block, (8, 4). The gather scans every angle, rounds the offset index and sums texels times 0.1, computing a Jacobian weight it does not use.
- **IntegerBlockHRC** keeps the BlockHRC core unchanged and adds exact integer line tests. Lines are integer `(start, delta)` pairs inside a power-of-two box, split recursively into quadrants (to depth 10), so whether a line passes through a tile is decided without a floating-point ray. Only the test shader runs: on 32 px tiles it draws every integer line through both a pixel's tile and a source tile. It tests exact lattice visibility and is not a working pipeline.

### Polygonal cascades

- **PolygonalHRC45** splits the plane into quadrilaterals indexed by line, probe, direction and a frustum flag. Probe spacing stays at 10 px on every level, while the line spacing (10 px at level 0) and the direction count (1) double, over 9 levels. A polygon spans from line `i` to line `i + 1`, or to `i + 2` for even ("extended") lines, and its frustum form widens by 2 or 3 probes. Its value falls from `1/2^k` to `1/2^(k+1)` across the polygon. Extension builds level `k + 1` from source lines `2i − 2` and `2i − 1` as plain sums with no ½ factor, and gathering sums every polygon that contains a pixel, with the cosine ("Euclidean flux") correction disabled. The negative source line at `i = 0` is not bounds-checked.
- **PolygonalHRC** uses 30 px spacing and no frustum flag: each target polygon sums one texel from each of two source lines.
- **PolygonalPrimalHRC** propagates top-down ("primal") instead of bottom-up ("dual"). The source writes its falloff into the polygons of every cascade, then each cascade from 4 down to 0 adds two or three polygons of the coarser one, each times a placeholder weight of 1. The dual pipeline is present but commented out.
- **PolygonalBlockRC** only draws the wedge geometry of block probes: an inner box `probe ± length_scale` and an outer box from the half-index probe at twice the spacing. **PolygonalBlockExtendedRC** seeds one tile with a random color per direction, sums four children per parent with no weights, and gathers over a 7×7 probe neighbourhood.

### GradientRC.ls

Nothing propagates: each of 6 cascades (5 px spacing and 4 to 20 directions at level 0, both doubling) is loaded straight from a point source. The wedge of each probe direction, between an inner and an outer box, stores `1/r` at its midpoint and the slope of `1/r` along its center line, but only if the wedge contains the source. Gathering evaluates `value + dot(pos − midpoint, dir·slope)` at every pixel and cascade, with a display gain of 20. The reconstruction is first order along the wedge's center line only, with no slope across it.

### Wave-optics tests

These ask whether a field sampled on a line can be re-expanded into plane waves (an angular spectrum) and propagated, the wave analogue of storing radiance on a line.

- **Holograms:** an outgoing cylindrical wave `J0 + iY0` (the Hankel function H0⁽¹⁾) of wavelength 0.5 px from a point is sampled along a 2048-sample row, transformed by a naive O(N²) DFT, and each harmonic is rebuilt as a plane wave with vector `dir·k_lin + tangent·√(k² − k_lin²)` inside a 500 px zone. Evanescent harmonics are zeroed, and an optional occlusion test keeps a plane wave only between the row ends. A slit mask passes 0.35 to 0.45 and 0.5 to 0.7 of the row. The display shows the residual against the true field; as written, the reference pass stores zeros, so nothing is subtracted.
- **HologramPropagation:** 1000 random-phase point sources on a 200 px segment seed row 0. Each later row (8 by default, with a 1024-sample DFT and wavelength 2) is rebuilt from the plane waves of the row above, with a random obstacle 10% of the width per row and a window from 0.2 to 0.8 of the width. Magnitudes are averaged over frames with re-randomized phases. If images persist between frames, the field reaches the last row only after about as many frames as there are rows.
- **HolographicCharges:** a field sampled on a line is divided in Fourier space by the 2D Green function `(i/4)·H0⁽¹⁾(kr)` sampled on the same line. That gives "charges" on the line, which are propagated with the Green function to rebuild the field in a 100 px zone (wavelength 10, 256 samples). The division has no regularization, so near-zero kernel frequencies amplify noise without bound, and the occlusion and evanescent toggles are passed but never read.

### BundleBasisExploration.ls

Tests a basis of line bundles for an HRC probe. Each of 20 × 10 basis functions is the family of rays between an origin edge (a 20 px segment on a vertical line at x = 300) and a direction edge (one of 10 slope steps over [−1, 1]). A vertical source segment is projected onto the bundles with 50 × 50 rays each, and each pixel is rebuilt from four neighbouring bundles with bilinear weights estimated from 30 × 30 rays. Only the source-edge parameter is tested, so each ray acts as an infinite line.

### Sweeping.ls

A library, included by no script, with a transform from a sweep direction to the pixel grid (using `1/|cos θ| = √(1 + tan² θ)`) and a skewed-rectangle transform.
