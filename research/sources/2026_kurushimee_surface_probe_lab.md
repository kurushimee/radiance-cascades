# Surface probes with world upper cascades, measured

| | |
|---|---|
| Author | kurushimee (independent researcher) |
| Date | 2026-10 |
| Kind | Original measurements with code: a surface-probe simulator over the voxel lab of the papers, Monte Carlo references at the probes, seeded experiments |
| Link | scripts in [design/experiments/](../../design/experiments/) (`surface.py` the simulator, `e1_layout.py` to `e5_passes.py` the experiments); voxel lab in [papers/lab/volume.py](../../papers/lab/volume.py) |
| Related | [2026_kurushimee_merging_3d.md](2026_kurushimee_merging_3d.md), [2026_kurushimee_bounces_one_frame.md](2026_kurushimee_bounces_one_frame.md), [2026_kurushimee_rc_error_model.md](2026_kurushimee_rc_error_model.md), [2026_lightmap_atlases_seams_and_packing.md](2026_lightmap_atlases_seams_and_packing.md) |

Cascade 0 on surface texels, as hemisphere probes, with the upper cascades either on world-locked sphere grids or on lattices clamped to each chart, measured against Monte Carlo irradiance in six voxel scenes. Hits are stored, so every solve is a frozen solve and bounces are re-merges. The measurements cover where the upper cascades live, the merge at each hand-over, cascade 0's directions and interval, the light below a texel, and how many passes bounces need.

## Contents

- [Setup](#setup)
- [Where the upper cascades live (measured)](#where-the-upper-cascades-live-measured)
- [Merges per hand-over (measured)](#merges-per-hand-over-measured)
- [Cascade 0 directions and interval (measured)](#cascade-0-directions-and-interval-measured)
- [Records per texel (measured)](#records-per-texel-measured)
- [Below the texel (measured)](#below-the-texel-measured)
- [Bounce passes (measured)](#bounce-passes-measured)
- [Limits](#limits)

## Setup

- **Scenes**, 32³ voxels, every exposed face one texel with its probe 0.05 voxels in front of its centre: a closed room with one-voxel walls, a ceiling light, a free-standing panel and a pillar (5,838 texels); the same with two-voxel walls (5,088); two rooms joined by a door in a one-voxel partition, the light in one (6,914); a courtyard open to a sky of radiance 1 (2,730); a closed box with one-voxel walls under the sky (3,280); a closed hall lit from the ceiling with a grid of one-voxel pillars (8,350).
- **Cascade 0**: 16 hemisphere bins (8 azimuth sectors by 2 bands of equal height in `cos θ`, turned by 0.3 rad) on each texel, interval `[0, t0]`, `t0 = sqrt(2 · bins / 4π) = 1.60` voxels.
- **World upper cascades**: sphere probes at spacing `2^c` voxels on the papers' turned equal-area map, directions and intervals ×4 per cascade, three world cascades in these scenes. Only the probe-bins that some lower probe reads are traced and stored.
- **Chart lattices**: lattices of spacing `2^c` clamped to each planar chart of faces, merged with the bilinear fix.
- **Reference**: Monte Carlo irradiance at every probe, 16,384 rays per point and two seeds, which differ by 0.04% to 1.4% (relative RMSE, halved) by scene.
- **Metrics**, relative RMSE over receivers normalized by the exact mean: the first bounce (irradiance from the light and sky); the second (from faces lit by the exact first bounce); "split", the face radiance after 5 GMRES passes at albedo 0.9 with the light's direct irradiance exact and RC gathering the rest; the furnace deficit of a closed scene; the sky's leak into the closed box; and the hit records the solve stores.

## Where the upper cascades live (measured)

Split error and records, one merge at every hand-over:

| Scene | world, all 8 parents, trilinear fix | world, front parents, trilinear fix | world, front, Kuhn fix | chart lattices, bilinear fix |
|---|---|---|---|---|
| room | 0.200 · 6.22 M | 0.110 · 4.37 M | 0.116 · 1.70 M | 0.110 · 1.32 M |
| thick room | 0.037 · 6.13 M | 0.023 · 4.33 M | 0.028 · 1.74 M | 0.057 · 1.13 M |
| two rooms | 0.261 · 6.76 M | 0.181 · 4.82 M | 0.196 · 1.91 M | 0.201 · 1.57 M |
| courtyard | 0.050 · 3.60 M | 0.016 · 2.55 M | 0.023 · 1.05 M | 0.011 · 0.63 M |
| columns | 0.188 · 8.95 M | 0.128 · 6.59 M | 0.141 · 2.68 M | 0.149 · 2.98 M |

- **A surface probe's world parents behind its surface bias bent merges dark.** With all eight trilinear parents, the first bounce is 9.5 to 20% dark and the split error 1.4 to 3 times higher. A parent behind the wall sees the wall's back. Dropping the parents on or behind the texel's tangent plane and renormalizing the rest removes the bias.
- **Only bent merges seal.** Vanilla and the self test leave furnace deficits of 0.012 to 0.065 and split errors of 0.21 to 0.56 in the closed scenes; the fixes on front parents 0.0000 to 0.0033 and 0.023 to 0.20. Sky leaks into the box: vanilla 0.036 to 0.040, the self test 0.017, the fixes 0.0000 to 0.0001.
- **The Kuhn fix with front parents fails at cascade 0**: first-bounce errors of 0.87 to 1.04 in two rooms and columns, probably because the Kuhn simplex has only four corners and the front filter can leave one.
- **Chart lattices keep 2 to 4 times fewer records at a similar error** on these charts, which are large, planar and axis-aligned, with none narrower than a lattice spacing. Curved, thin or small charts, where lattice parents are undefined, are not in the lab.

## Merges per hand-over (measured)

The surface hand-over (cascade 0 to 1) and the world hand-overs above it varied independently, all on front parents, with bilinear sub-direction reads. Split error · records in millions:

| Surface · world | room | thick room | two rooms | courtyard | columns | box leak |
|---|---|---|---|---|---|---|
| self test · self test | 0.333 · 0.86 | 0.223 · 0.55 | 0.342 · 0.90 | 0.020 · 0.59 | 0.257 · 1.13 | 0.0166 |
| self test · Kuhn fix | 0.160 · 1.95 | 0.027 · 1.80 | 0.222 · 2.15 | 0.022 · 1.18 | 0.157 · 3.08 | 0.0057 |
| trilinear fix · depth self test, sphere fix at the top | 0.174 · 1.15 | 0.093 · 0.98 | 0.232 · 1.25 | 0.015 · 0.72 | 0.184 · 1.54 | 0.0073 |
| trilinear fix · Kuhn fix | 0.111 · 2.25 | 0.024 · 2.20 | 0.179 · 2.50 | 0.016 · 1.31 | 0.127 · 3.50 | 0.0000 |
| trilinear fix · trilinear fix | 0.110 · 4.37 | 0.023 · 4.33 | 0.181 · 4.82 | 0.016 · 2.55 | 0.128 · 6.59 | 0.0001 |
| trilinear fix · Kuhn fix, sphere fix at the top | 0.123 · 1.52 | 0.046 · 1.47 | 0.181 · 1.68 | 0.015 · 0.91 | 0.136 · 2.46 | 0.0001 |
| trilinear fix · sphere fix | 0.118 · 1.15 | 0.046 · 0.98 | 0.195 · 1.25 | 0.016 · 0.72 | 0.146 · 1.54 | 0.0008 |

- **The surface hand-over decides the seal.** With the self test there, the box leaks 0.006 even when every world hand-over is bent.
- **Kuhn at the world hand-overs** seals at half the trilinear fix's records and the same error. **The sphere fix at the top** cuts records by about a third, at split errors up to 0.022 higher (thick room 0.024 → 0.046). **The sphere fix at every world hand-over** keeps 21 to 37% fewer records again, with split errors within 0.015 of Kuhn-then-sphere, a box leak of 0.0008 and furnace deficits of 0.0010 to 0.0052.
- **Reading one bin instead of four.** Nearest-bin sub-direction reads keep about 20% fewer records; the split error barely moves, but the second bounce is about 25% worse (room 0.047 → 0.059) and the first 20 to 55% worse.

## Cascade 0 directions and interval (measured)

World solves with the trilinear fix on front parents and the sphere fix at every world hand-over. Split error:

| Cascade 0 | room | thick room | two rooms | courtyard | columns | box leak |
|---|---|---|---|---|---|---|
| 16 bins, `t0` × 0.5 | 0.178 | 0.089 | 0.310 | 0.037 | 0.187 | 0.0120 |
| 16 bins, `t0` × 1 | 0.118 | 0.046 | 0.195 | 0.016 | 0.146 | 0.0008 |
| 16 bins, `t0` × 2 | 0.137 | 0.073 | 0.214 | 0.016 | 0.180 | 0.0058 |
| 36 bins, `t0` × 0.5 | 0.068 | 0.021 | 0.166 | 0.017 | 0.110 | 0.0014 |
| 36 bins, `t0` × 1 | 0.077 | 0.021 | 0.153 | 0.011 | 0.134 | 0.0006 |
| 64 bins, `t0` × 1 | 0.059 | 0.015 | 0.146 | 0.008 | 0.111 | 0.0010 |

Chart lattices with the bilinear fix: 0.110, 0.057, 0.201, 0.011, 0.149 at 16 bins and 0.089, 0.027, 0.166, 0.007, 0.145 at 36 bins.

- **At 16 bins the equal-error interval is best.** Halving it lets 0.012 of the sky into the box: the sphere fix needs the lower interval to reach past its parents' interval starts (paper 2 gives `0.75√3` upper spacings). Doubling it raises the error too.
- **36 bins cut the split error by a third to a half in single rooms** (0.118 → 0.077, 0.046 → 0.021) for 2.1 to 2.2 times the records.
- **Two rooms and the pillar hall keep 0.11 to 0.15** at any bin count, against 0.06 to 0.08 in the single room at 36 or 64 bins: world probes interpolate through the door and around one-voxel pillars, which more directions do not fix.

## Records per texel (measured)

At 16 bins and the equal-error interval with the sphere fix at every world hand-over, records per texel are 181 to 265: 64 at cascade 0 (16 bins times about four front parents), 20 to 35 at world cascade 1, 42 to 66 at cascade 2 and 44 to 109 at the top. Each world cascade needs more of its bins than the one below. 36 bins take 389 to 577 records per texel, and 64 bins 682 to 1,009.

**Derived.** Surface-near sphere probes at spacing `2^c s` number about `A / (2^c s)²` times the depth of the shell they fill, and carry `32 · 4^c` bins, so the probe-bins per unit of surface stay about the same at every cascade once every bin is needed; records per texel then grow with the number of world cascades, about `log4` of the scene's size over `t0`.

## Below the texel (measured)

Irradiance at four points per texel, a quarter texel from its centre in each tangent axis, against Monte Carlo at those points (16,384 rays, two seeds), with converged radiance at albedo 0.9 and the light's emission removed. Error at contact points, on faces with a solid voxel beside the voxel in front (656 to 4,384 per scene):

| Estimate | room | thick room | courtyard | columns |
|---|---|---|---|---|
| the texel's value | 0.024 | 0.010 | 0.032 | 0.053 |
| the chart's texels, bilinear | 0.021 | 0.009 | 0.028 | 0.059 |
| a probe at the point, merged into world cascade 1 like a texel | 0.025 | 0.009 | 0.033 | 0.033 |
| a probe at the point over `[0, t0]`, misses read the texel's merged bin | 0.029 | 0.012 | 0.036 | 0.059 |
| the same over `[0, t0/2]` | 0.027 | 0.010 | 0.035 | 0.044 |
| the bilinear value times the point's unoccluded cosine share over `[0, t0]`, over the texel's | 0.023 | 0.012 | 0.034 | 0.081 |
| the same over `[0, t0/2]` | 0.195 | 0.183 | 0.195 | 0.201 |

- With geometry aligned to the texels, the texel holds most of the near field: bilinear reads are within 1 to 6% at contact points, and over all points every estimate is within 0.001 of the texel's error in three scenes.
- Only thin occluders gain from a probe at the point, and only when it merges into the upper cascade like a texel: 0.053 → 0.033 around the pillars.
- **A short trace with the texel behind it counts near occluders twice.** With a bent surface merge, the texel's merged radiance comes from rays that start at the texel; where the point's short ray misses, reading that radiance brings back occluders the point's ray passed.
- **An occlusion ratio darkens wrongly.** Scaling the texel by the point's unoccluded share over the texel's treats near occluders as black; the occluders at contact points are lit walls, and over half the interval the ratio biases contact points 13 to 15% dark.

## Bounce passes (measured)

Plain bounces with a geometric tail against GMRES, from zero, direct light exact. Error against the solve's own fixed point (GMRES after 40 passes) at albedo 0.9, world solves:

| Passes | 2 | 3 | 4 | 5 | 6 | 8 |
|---|---|---|---|---|---|---|
| room, tail | 0.228 | 0.092 | 0.029 | 0.015 | 0.008 | 0.003 |
| room, GMRES | 0.750 | 0.378 | 0.063 | 0.016 | 0.005 | 0.000 |
| two rooms, tail | 0.425 | 0.261 | 0.177 | 0.143 | 0.117 | 0.081 |
| two rooms, GMRES | 0.851 | 0.549 | 0.226 | 0.134 | 0.099 | 0.018 |
| columns, tail | 0.402 | 0.187 | 0.085 | 0.047 | 0.026 | 0.009 |
| columns, GMRES | 0.754 | 0.608 | 0.339 | 0.087 | 0.022 | 0.002 |

- At albedo 0.5, three tail passes reach 0.001 to 0.023 of the fixed point and four under 0.007.
- At albedo 0.9, five tail passes reach 0.015 to 0.047 in single rooms and the pillar hall. Two rooms joined by a door converge slowly: 0.143 after five tail passes and 0.081 after eight; GMRES overtakes the tail from pass 5 there and from pass 6 elsewhere.
- Up to five passes the tail is as good as GMRES or better, except two rooms at pass 5 and the courtyard, where both are under 0.001.
- Against the exact solution, a tail at three passes can fall below the solve's own floor (room 0.078 against 0.108): its unconverged light cancels part of the solve's dark bias.

## Limits

- Geometry is aligned to the texels, so nothing is finer than a texel, and charts are planar, large and axis-aligned.
- No GPU costs: records count stored hits, not time, and merge reads are not counted.
- At most three world cascades.
