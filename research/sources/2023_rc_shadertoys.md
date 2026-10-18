# Radiance cascades Shadertoys

Shadertoy is behind a bot check, so these notes come from copies on GitHub, mostly the Shadertoy API dump in https://github.com/GabeRundlett/shadertoy-api-shaders (`shaders/<id>.json`). The shaders have no license. They are the reference 2D implementations most other projects descend from: mtlBzX → clVcD3 (Quinchilion) → MctXRr → 4ctXD8 (Suslik).

| ID | Title | Author | Date |
|---|---|---|---|
| mtlBzX | Radiance Cascades | fad | 2023-09-02 |
| mlSfRD | Radiance Cascades 2d Smooth WIP | Suslik | (Godot port only) |
| 4ctXD8 | RC Experimental Testbed | Suslik | 2024-04-24 |
| 4XXSWS | Novel depth aware upscaling | Suslik | 2024-03-14 |
| 4clcWn | Radiance Cascades Diagram | Mytino | 2024-07-15 |
| XcB3Ry, MfS3Wm | Continuous gravity simulation 2, CFD gravity simulation | Suslik | 2024-01 |
| XcfyDj | Parallax fix | mxcop | not copied |
| XffcD7 | Gear fix | kornelski | not copied |
| M3ycWt | Volumetric Radiance Cascades | unknown | not copied |
| X3XfRM | Radiance Cascades 3D | Suslik | 2024-11; see [2024_suslik_x3xfrm_surface_probe_rc.md](2024_suslik_x3xfrm_surface_probe_rc.md) |
| NttSW7 | Analytic Direct Illumination | Mathis | source of the sky integral |

## mtlBzX (fad): the original 2D implementation

- Passes: mouse smoothing, an SDF paint buffer (`.r` signed distance, `.gba` emission), a cube-map buffer holding all cascades, and the image pass. Every cascade reads the previous frame's cube map, so a full update takes `n` frames for `n` cascades.
- Five cascades. Cascade 0 has 16 directions and about `6·W·H/17` texels' worth of probes; each cascade halves the probes per axis and has 4× the directions.
- Pre-averaging: cascade 0 stores one value per probe (the mean of 16 rays), and each texel of cascade `n ≥ 1` stores the mean of 4 rays, so cascade `n` stores `16·4^(n−1)` texels per probe.
- Intervals: with `L0 = 4·|res|/(4^5 − 1)`, cascade `n` covers `[4^(n−1)·L0, 4^n·L0]` (cascade 0 starts at 0), so `[0, L0], [L0, 4L0], …, [64L0, 256L0]`. The top interval ends just past the screen diagonal.
- Trace: sphere tracing with at most 100 steps; a hit needs `t > 0.2` and `d < 1` px. A ray starting inside a shape returns that shape's emission at once.
- Merge: for rays that did not hit, read cascade `n+1` at the same direction index from four probes, with `pf = (p + 0.5)/2`, `q = round(pf) − 1`, `w = pf − q − 0.5`, then `rgb += a·S.rgb`, `a *= S.a`.
- Sky: the top cascade adds the analytic sky integral over each ray's angular bin, divided by the bin width. For a bin `(a0, a1)`: sky `(a1 − a0 − 0.5(cos a1 − cos a0))·SkyColor` plus sun `(atan(8(SunA − a0)) − atan(8(SunA − a1)))/8·SunColor`, all divided by 6; bins that cross 2π are split. Integrating the sky over the bin, instead of sampling one direction, avoids aliasing from the coarse top-cascade bins.
- Gather: bilinear over four cascade 0 probes, times 2π for fluence, tone map `1 − 1/(1 + F)^2.5`. Emission colors are linearized with `pow(c, 2.2)`.

## 4ctXD8 (Suslik): testbed of merge fixes

Six cascades, cascade 0 with 4 directions and 512 probes across, `L0 = 0.0015·W`, interval starts `(4^k + 1)·L0` for `k ≥ 1`. Every cascade holds the same number of texels. The `MERGE_FIX` switch picks the merge:

| Value | Function | What it does |
|---|---|---|
| 0 | `CastMergedInterval` | one ray per direction; four upper probes blended bilinearly for that direction |
| 1 (default) | `CastMergedIntervalBilinearFix` | four rays from the probe, each ending at one upper probe's interval start, each merged with that probe and weighted bilinearly |
| 2 | `CastMergedIntervalMidpointBilinearFix` | splits each ray at a midpoint |
| 3 | `CastMergedIntervalMaskFix` | masks upper probes by hit distance; the "Dolkar fix" |
| 4 | `CastMergedIntervalParallaxFix` | per-upper-probe direction interpolation, intervals stretched by 1.1 for overlap |
| 5 | `CastMergedIntervalInnerParallaxFix` | inner variant of the parallax fix |

The bilinear fix core is short: start at `probe + dir·t_start`, end at `upper_probe + dir·t_end`, march along the normalized difference, merge with the upper probe's value, weight. Each cascade texel also averages its 4 upper directions.

`C_MINUS1_GATHERING`: the image pass traces `[0, L0]` from every pixel for each cascade 0 direction and merges it in front of the interpolated cascade 0 value. This "cascade −1" removes the blur from interpolating cascade 0 near contact. The result is the mean over directions, with no 2π factor.

## mlSfRD (Suslik): smooth interval edges

Known from thmasn's Godot port. Four cascades on a 320×180 cascade 0 grid with 16 directions, intervals `[0, 7], [7, 28], [28, 112], [112, 448]` px. The trace extends each interval by half a fade length on both sides (fade `10·2^n` px at the start, `10·2^(n+1)` at the end) and fades hits near both ends toward empty `(0, 0, 0, 1)`. Neighboring cascades then cross-fade instead of meeting at a hard boundary, which hides the seam between them.

## 4XXSWS (Suslik): depth-aware upscaling

A test of upscaling a 1/8-resolution buffer of `(color, depth)` to full resolution, with four panels: plain bilinear, reference, bilateral, and "bilinear 3D". three-rc ports it for screen-space probes.

- Bilateral: weight each of the four neighbors by `bilinear_i·exp(−100·|depth_i − depth|)` and normalize.
- Bilinear 3D: rebuild the four neighbors' world points `P_i` from their depths and the target point `Q`. Starting from the plain bilinear ratio, run two iterations that alternate solving `ratio.x` and `ratio.y` by projecting `Q` onto the line between the two edge points interpolated at the other ratio (`ProjectLinePerp(A, B, p) = dot(p − A, B − A)/dot(B − A, B − A)`, saturated). The final bilinear weights at that ratio sum to 1, so no normalization is needed, and they follow the actual surface instead of rejecting samples.
- There is no guard against zero-length edges or a zero total bilateral weight.

## 4clcWn (Mytino): diagram of the fixes

Draws the rays of two cascades. The bilinear fix ends each ray at `upper_probe + dir·t_end` (one ray per upper probe). The forking fix starts each ray at `probe + dir_lower·t_start`, where `dir_lower` is the center of the coarser direction bin that contains it, so the four child rays fork from the end of their parent ray. With both off, the diagram shows plain RC.

## XcB3Ry and MfS3Wm (Suslik): RC structure for gravity

A gravitational fluid simulation that uses the cascade hierarchy for an N-body field. Level `k` holds 2×2-averaged mass at `1/2^k` resolution, and each level sums gravity only from sources in its distance band `((4^(k−1) or 0) + 1, 4^k + 1)·5.1`, with smooth fades at both band edges. It shows the method applies to any long-range field whose detail falls off with distance.
