# Lab experiments

Five experiments settle the choices a voxel model can settle before any engine code exists. They run on the voxel lab of the papers (`papers/lab/`), with CUDA ray marching through CuPy, and each reruns from its script:

```bash
uv run --project papers python design/experiments/e1_layout.py
```

Results are cached in `design/build/results/` and Monte Carlo references in `design/build/cache/`; deleting a file reruns what made it. `design/experiments/selftest.py` checks the simulator: the hemisphere's cosine weights sum to π, every layout and merge passes the furnace test, and reference rows sum to one.

## Contents

- [The model](#the-model)
- [Metrics](#metrics)
- [E1: where the upper cascades live](#e1-where-the-upper-cascades-live)
- [E2: merges per hand-over](#e2-merges-per-hand-over)
- [E3: cascade 0 directions and interval](#e3-cascade-0-directions-and-interval)
- [E4: the near field below the texel](#e4-the-near-field-below-the-texel)
- [E5: bounce passes](#e5-bounce-passes)
- [What the lab cannot show](#what-the-lab-cannot-show)

## The model

- **Scenes** are 32³ voxel volumes. Every exposed face is one atlas texel with a cascade 0 probe 0.05 voxels in front of its centre.
  - *room*: a closed room with one-voxel walls, a ceiling light, a free-standing panel and a pillar (5,838 texels);
  - *thick room*: the same with two-voxel walls (5,088);
  - *two rooms*: two rooms joined by a door in a one-voxel partition, the light in one (6,914);
  - *courtyard*: a floor between two walls, open to a sky of radiance 1 above and at both ends (2,730);
  - *sealed box*: a closed box with one-voxel walls on a floor under the sky, so any light inside it leaked in (3,280);
  - *columns*: a closed hall lit from the ceiling, with a grid of one-voxel pillars (8,350).
- **Cascade 0** is a hemisphere of 16 bins on each texel, with the equal-error interval `t0 = sqrt(2 · bins / 4π)` voxels ([paper 1](../papers/01_error_model/paper.md)).
- **Upper cascades** are either world sphere grids (spacing 2^c voxels, four times the directions and intervals per cascade, as in [paper 2](../papers/02_merging_3d/paper.md)) or lattices of spacing 2^c clamped to each planar chart of faces.
- **Hit records** are the stored hits a static solve keeps: one per ray or bent segment. A pass re-shades them with the current face radiance and re-merges, with no rays ([paper 3](../papers/03_bounces_one_frame/paper.md)).
- **References** are Monte Carlo irradiance at every probe point, 16,384 rays per point and two seeds. The two seeds differ by under 1.5% (relative RMSE between them halved: 0.04% to 1.4% by scene), which bounds the noise in every error below.

## Metrics

All errors are relative RMSE over the receivers, normalized by the mean of the exact value, with the relative bias in brackets where it matters.

| Metric | What it measures |
|---|---|
| first | irradiance from the light and sky, gathered by RC |
| second | irradiance from faces lit by the exact first bounce |
| split | face radiance after 5 GMRES passes at albedo 0.9, with the light's direct irradiance exact and RC gathering the rest |
| deficit | the furnace deficit of a closed scene: faces of radiance 1, no sky, `1 − E/π` |
| leak | sky light inside the sealed box, as a share of the outside |
| records | hit records the static solve keeps, in millions |

`split` is the number the design rests on, because the design lights texels with exact direct light and lets RC gather only reflected light and the sky ([lighting.md](lighting.md)). `first` mostly measures RC gathering one small light, which the design never asks it to do.

## E1: where the upper cascades live

`e1_layout.py` compares world sphere grids above cascade 0, with all eight trilinear parents or only those in front of the texel's tangent plane, against chart lattices. Each layout uses one merge at every hand-over.

| Scene | world, all parents, trilinear fix | world, front parents, trilinear fix | world, front, Kuhn fix | lattices, bilinear fix |
|---|---|---|---|---|
| room | 0.200 · 6.22 M | 0.110 · 4.37 M | 0.116 · 1.70 M | 0.110 · 1.32 M |
| thick room | 0.037 · 6.13 M | 0.023 · 4.33 M | 0.028 · 1.74 M | 0.057 · 1.13 M |
| two rooms | 0.261 · 6.76 M | 0.181 · 4.82 M | 0.196 · 1.91 M | 0.201 · 1.57 M |
| courtyard | 0.050 · 3.60 M | 0.016 · 2.55 M | 0.023 · 1.05 M | 0.011 · 0.63 M |
| columns | 0.188 · 8.95 M | 0.128 · 6.59 M | 0.141 · 2.68 M | 0.149 · 2.98 M |

Split error · records. Leaks into the sealed box: 0.0001 (trilinear fix), 0.0000 (Kuhn fix, lattices); the self test leaks 0.017 and vanilla 0.036 to 0.040.

- **Parents behind the surface bias bent merges dark.** With all eight parents, the first bounce is 10 to 20% too dark (bias −0.095 to −0.203) and the split error is 1.4 to 3 times higher, because a parent behind the wall sees the wall's back. Keeping only front parents and renormalizing removes the bias. Front parents are therefore part of the world layout, not an option.
- **Vanilla and the self test do not seal.** In the closed scenes their furnace deficits are 0.012 to 0.065 and their split errors 0.21 to 0.56, against 0.0000 to 0.0033 and 0.023 to 0.20 for the fixes on front parents.
- **Kuhn with front parents fails at cascade 0.** Its first-bounce error reaches 0.87 to 1.04 in two rooms and columns, probably because the Kuhn simplex has only four corners and the front filter can leave one. Cascade 0 seals with the trilinear fix.
- **Lattices are cheaper here, but only on planar charts.** With one merge everywhere, lattices keep 2 to 4 times fewer records at a similar error. E2 closes most of the gap by choosing the merge per hand-over, and the voxel scenes favour lattices: their charts are large, planar and axis-aligned, and no chart is narrower than a lattice spacing. Curved, thin and small charts, where lattice parents are undefined, cannot be built in the lab.

## E2: merges per hand-over

`e2_merges.py` varies the surface hand-over (cascade 0 to 1) and the world hand-overs above it independently, all with front parents, and reads each sub-direction from four bilinear bins of a cascade 1 probe or from the nearest one.

| Surface · world merges | room | thick room | two rooms | courtyard | columns | sealed box leak |
|---|---|---|---|---|---|---|
| self test · self test | 0.333 · 0.86 | 0.223 · 0.55 | 0.342 · 0.90 | 0.020 · 0.59 | 0.257 · 1.13 | 0.0166 |
| self test · Kuhn fix | 0.160 · 1.95 | 0.027 · 1.80 | 0.222 · 2.15 | 0.022 · 1.18 | 0.157 · 3.08 | 0.0057 |
| trilinear fix · depth self test, then sphere fix | 0.174 · 1.15 | 0.093 · 0.98 | 0.232 · 1.25 | 0.015 · 0.72 | 0.184 · 1.54 | 0.0073 |
| trilinear fix · Kuhn fix | 0.111 · 2.25 | 0.024 · 2.20 | 0.179 · 2.50 | 0.016 · 1.31 | 0.127 · 3.50 | 0.0000 |
| trilinear fix · trilinear fix | 0.110 · 4.37 | 0.023 · 4.33 | 0.181 · 4.82 | 0.016 · 2.55 | 0.128 · 6.59 | 0.0001 |
| trilinear fix · Kuhn fix, then sphere fix | 0.123 · 1.52 | 0.046 · 1.47 | 0.181 · 1.68 | 0.015 · 0.91 | 0.136 · 2.46 | 0.0001 |
| **trilinear fix · sphere fix** | **0.118 · 1.15** | **0.046 · 0.98** | **0.195 · 1.25** | **0.016 · 0.72** | **0.146 · 1.54** | **0.0008** |

Split error · records in millions, bilinear reads.

- **The surface hand-over must be bent to seal.** With the self test at cascade 0, the sealed box leaks 0.006 even when every world hand-over is bent.
- **The Kuhn fix seals the world hand-overs at half the trilinear fix's records** and the same error.
- **The sphere fix at the top hand-over** cuts records by about a third and seals; the split error rises from 0.024 to 0.046 in the thick room and by under 0.013 elsewhere.
- **The sphere fix at every world hand-over** keeps another quarter to third fewer records (0.65 to 1.54 M, 181 to 265 per texel) with split errors within 0.015 of Kuhn-then-sphere, better in the room and worse in two rooms and columns. It lets 0.0008 of the sky into the sealed box, against 0.0001, and its furnace deficits are 0.0010 to 0.0052. This is the design's default, with Kuhn at the first world hand-over as the sealed alternative ([cascades.md](cascades.md)).
- **Nearest reads save about 20% of records and cost accuracy.** The split error barely moves, but the second bounce is about 25% worse (room 0.047 → 0.059) and the first 20 to 55% worse, so bilinear reads stay.

## E3: cascade 0 directions and interval

`e3_cascade0.py` sets cascade 0 to 16, 36 or 64 bins and `t0` to 0.5, 1 or 2 times the equal-error length; every cascade above scales from it. World solves use the E2 default.

| World solve | room | thick room | two rooms | courtyard | columns | sealed box leak | records per texel |
|---|---|---|---|---|---|---|---|
| 16 bins, t0 × 0.5 | 0.178 | 0.089 | 0.310 | 0.037 | 0.187 | 0.0120 | 240 to 440 |
| **16 bins, t0 × 1** | **0.118** | **0.046** | **0.195** | **0.016** | **0.146** | **0.0008** | **180 to 270** |
| 16 bins, t0 × 2 | 0.137 | 0.073 | 0.214 | 0.016 | 0.180 | 0.0058 | 170 to 260 |
| 36 bins, t0 × 0.5 | 0.068 | 0.021 | 0.166 | 0.017 | 0.110 | 0.0014 | 400 to 590 |
| 36 bins, t0 × 1 | 0.077 | 0.021 | 0.153 | 0.011 | 0.134 | 0.0006 | 390 to 580 |
| 64 bins, t0 × 1 | 0.059 | 0.015 | 0.146 | 0.008 | 0.111 | 0.0010 | 680 to 1,010 |

Split error. Lattices with the bilinear fix: 0.110, 0.057, 0.201, 0.011, 0.149 at 16 bins (220 to 360 records per texel) and 0.089, 0.027, 0.166, 0.007, 0.145 at 36 bins (500 to 800).

- **Records per texel are set by the bins, not the scene.** At 16 bins and the equal-error interval, cascade 0 keeps 64 records per texel (16 bins times about 4 front parents), world cascade 1 20 to 35, cascade 2 42 to 66 and the top cascade 44 to 109. Each world cascade needs more of its bins than the one below, so a scene that needs more world cascades than the lab's three keeps more records per texel ([budget.md](budget.md)).
- **36 bins cuts the error by a third to a half in single rooms** (room 0.118 → 0.077, thick room 0.046 → 0.021) for 2.1 to 2.2 times the records. At a fixed record budget that means texels about 1.5 times as far apart; which wins is an engine measurement.
- **Two rooms and columns keep 0.11 to 0.15** whatever the bins, against 0.06 to 0.08 in the single room at 36 or 64 bins. The error comes from interpolating world probes through the door and around one-voxel pillars, so more directions do not reach it.
- **The equal-error interval is the best `t0` at 16 bins.** Halving it raises every error and lets 0.012 of the sky into the sealed box, because the sphere fix needs the lower interval to reach past its parents' interval starts; doubling it raises the error too.

## E4: the near field below the texel

`e4_near_field.py` evaluates irradiance at four points per texel, a quarter texel from its centre in each tangent axis, against Monte Carlo at those points (16,384 rays, two seeds), with the converged radiance of albedo 0.9 as the field and the light's own emission left out. Contact points lie on faces with a solid voxel beside the voxel in front.

| Estimate | room | thick room | courtyard | columns |
|---|---|---|---|---|
| the texel's value | 0.024 | 0.010 | 0.032 | 0.053 |
| the chart's texels, bilinear | 0.021 | 0.009 | 0.028 | 0.059 |
| a probe at the point, merged into world cascade 1 | 0.025 | 0.009 | 0.033 | 0.033 |
| a probe at the point over `[0, t0]`, misses read the texel's merged bin | 0.029 | 0.012 | 0.036 | 0.059 |
| the same over `[0, t0/2]` | 0.027 | 0.010 | 0.035 | 0.044 |
| the chart's bilinear value times the point's unoccluded share over `[0, t0]`, divided by its texel's | 0.023 | 0.012 | 0.034 | 0.081 |
| the same over `[0, t0/2]` | 0.195 | 0.183 | 0.195 | 0.201 |

Error at contact points (656 to 4,384 per scene). Over all points, every estimate lies within 0.001 of the texel's own error (0.011 to 0.020) in three scenes; in columns the point's own probe brings 0.032 down to 0.028.

- **At texel-aligned geometry, the texel already holds the near field.** Bilinear reads of the chart are within 1 to 6% of the reference at contact points.
- **Only thin occluders gain from a probe at the point**: around the pillars, merging a point's own probe into world cascade 1 cuts the contact error from 0.053 to 0.033.
- **A contact factor darkens wrongly.** Scaling the texel by how much more of the point's hemisphere is blocked nearby, as ambient occlusion does, treats the near occluder as black. At contact points the near occluder is a lit wall, so over half the interval the factor biases them 13 to 15% dark; over the full interval point and texel see the same wall and the factor stays near one.
- **A short trace with the texel behind it does not help.** At cascade 0's full interval it is no better than the texel, and at half the interval it recovers about half of the pillars' gain while doing slightly worse elsewhere. The reason is structural: with the bent surface merge, a texel's merged radiance already comes from rays that start at the texel, so a miss from the point reads near occluders the point's own ray may have passed, counting them twice.

## E5: bounce passes

`e5_passes.py` runs world and lattice solves at their defaults for 1 to 8 passes, from zero, with the direct light exact, and compares GMRES against plain bounces whose last difference is extended by a geometric tail.

Error against the solve's own fixed point at albedo 0.9, world solves:

| Passes | 2 | 3 | 4 | 5 | 6 | 8 |
|---|---|---|---|---|---|---|
| room, tail | 0.228 | 0.092 | 0.029 | 0.015 | 0.008 | 0.003 |
| room, GMRES | 0.750 | 0.378 | 0.063 | 0.016 | 0.005 | 0.000 |
| two rooms, tail | 0.425 | 0.261 | 0.177 | 0.143 | 0.117 | 0.081 |
| two rooms, GMRES | 0.851 | 0.549 | 0.226 | 0.134 | 0.099 | 0.018 |
| columns, tail | 0.402 | 0.187 | 0.085 | 0.047 | 0.026 | 0.009 |
| columns, GMRES | 0.754 | 0.608 | 0.339 | 0.087 | 0.022 | 0.002 |

- **At albedo 0.5, three tail passes** reach 0.001 to 0.023 of the fixed point, and four passes under 0.007.
- **At albedo 0.9, five tail passes** reach 0.015 to 0.047 in single rooms and columns. Two rooms joined by a door converge slowly: the tail is at 0.143 after 5 passes and 0.081 after 8, and GMRES overtakes it from pass 5 there and from pass 6 elsewhere.
- **The tail wins at a fixed small count.** GMRES needs as many passes as the error's dominant modes before it gains; up to 5 passes, the tail is as good or better everywhere except two rooms at pass 5 and the courtyard, where both are under 0.001.
- Against the exact solution, some tail runs at 3 passes fall below the solve's own floor (room: 0.078 against a floor of 0.108). That is cancellation between the unconverged tail and the solver's dark bias, not accuracy, and the design does not count on it.

## What the lab cannot show

- Geometry finer than a texel, curved or thin charts, and chart borders that cut through flat walls.
- The cost of a record or a merge read on a GPU, the hit rate of caches, and the number of world cascades a large scene needs: the lab's scenes stop at 3 or 4 world cascades.
- Seams, packing, and the UV distortion of real unwraps.
- Screen-space tracing.

Plan 004 measures each of these in the engine.
