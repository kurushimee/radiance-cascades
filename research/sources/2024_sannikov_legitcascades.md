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

The code comment says the circle should be the interval start of the upper probe, but the code uses the interval end `f`. Cascades 0 and 1 still use the bilinear fix, because the chronicl fix shows a checkerboard on them. The final gather here interpolates the stored cascade 0 texels bilinearly and marches no rays.

## Later experiments (2025–2026)

These scripts explore 2D variants and mostly test one idea each, often with a single hard-coded light and no scene.

| Script | Idea |
|---|---|
| `EnergyConservingHRC.ls` | Probes on vertical planes. A partly covered direction bin splits its energy between emission (coverage) and transmittance (1 − coverage), so the bins conserve energy. |
| `ExtendedHRC.ls` | The same plane cascade built bottom-up by interval extension. |
| `BlockHRC.ls`, `IntegerBlockHRC.ls` | Square probe blocks, each holding a grid of lines (angle and offset); parents copy radiance from child blocks along the same lines. |
| `PolygonalHRC.ls`, `PolygonalHRC45.ls`, `PolygonalPrimalHRC.ls`, `PolygonalBlock*RC.ls` | Each texel covers a polygon (trapezoid or wedge) between two boundary lines instead of a ray, giving alias-free light from a one-pixel source (shown in the "Polygonal Radiance Cascades" video). |
| `GradientRC.ls` | Each interval stores a value and its slope, tested on 1/distance from a point source. |
| `Holograms.ls`, `HologramPropagation.ls`, `HolographicCharges.ls`, `BundleBasisExploration.ls` | Wave-optics (Fourier hologram) and line-bundle basis tests, not RC pipelines. |

The last commit, "Added 4x scaling RC" (2026-04-09), adds `PolygonalBlockExtendedRC4x.ls`, which is still a byte-identical copy of `PolygonalBlockExtendedRC.ls`.
