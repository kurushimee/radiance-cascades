---
title: "Merging Radiance Cascades in 3D Probe Grids"
subtitle: "Leaks, parallax and cost of thirteen merges against a voxel reference"
author:
  - name: kurushimee
    affiliation: Independent researcher
abstract: |
  In a 3D grid of radiance cascades, a probe whose ray misses its distance interval takes the radiance that its eight parent probes saw beyond it. The parents sit up to 1.3 of their own spacings away, so they see past walls that the probe's line of sight would hit, and they see the far scene from another place. Many merges have been proposed against these leaks and this parallax, but none has been measured against a reference in 3D. We measure thirteen merges in a voxel lab against exact and brute-force references: the light that leaks into closed boxes with walls one to three voxels thick, the error in two rooms and around a small light, and the cost in rays, voxel steps and texture reads, all on held-out grid offsets. We derive why each merge behaves as it does. The parent hit-distance test cannot act at all above the first hand-over at the usual interval. Reading parents toward an estimated hit depth is exact for any plane all parents see, but it keeps only about $3.7(a/h)^2$ of a light of width $a$ narrower than the parent spacing $h$. The sphere-intersection fix is undefined for 40% of the first hand-over. We propose a self test that drops a parent when the probe's own stored ray toward that parent's interval start stops short of it, at two texture reads per parent and no rays. It halves the leak and lowers the room errors by 13% to 17%. Merges chosen per hand-over on training offsets cut the leak 4.3-fold and the room errors by 17% to 20% at 1.03 times the voxel steps; merges that trace toward each parent seal the boxes to $3 \times 10^{-4}$ of the sky or less at 2.3 to 8.2 times the steps and raise the error. In 3D the angular error of a small light falls as about $x^{-0.68}$ in the number of bins it covers, not as $x^{-1}$ as in flatland.
keywords: [global illumination, radiance cascades, light leaks, probe interpolation, light fields]
ccs:
  - concept: Computing methodologies
    sub: Rendering
    weight: 500
  - concept: Computing methodologies
    sub: Ray tracing
    weight: 300
bibliography: ../references.bib
teaser:
  image: figures/teaser.png
  caption: "Fluence on a vertical slice through the doorway of a room split by a wall one voxel thick, on a log scale, with the lamp on the left side's ceiling. Vanilla merging lets light through the wall into the dark half. The self test proposed here removes much of that leak at no extra rays, and merges chosen per hand-over remove more. Solids are white."
---

# Introduction {#sec:intro}

Radiance cascades compute global illumination from a hierarchy of probe grids [@sannikov2023]. Each cascade traces only a short distance interval, and each level up has sparser probes, finer directions and a longer interval. A probe's ray that hits nothing in its interval takes the radiance its upper cascade saw farther out. That step, the merge, is where most of the method's artifacts come from. In 3D the upper cascade's probes nearest a lower probe, its eight parents, sit up to 1.3 of their own spacings away. They see past a wall that the lower probe's line of sight would hit, which leaks light into closed rooms, and they see the scene from another place, which bends shadows and rings around small lights.

Many merges address this. Bent-ray fixes trace from the lower probe to each parent [@mytino2024; @osborne2024]. Visibility tests drop parents that the lower probe cannot see [@mathis2024x3xfrm; @erhe]. Reprojection reads each parent in the direction of the lower ray's estimated hit point [@reservoircascades; @osborne2025dexrt]. Each was tested by eye, in flatland, or in one engine on one scene. In 3D none has been measured against a reference for leaks, error and cost together, and the cheap ones rest on arguments that no one has checked: whether a parent's own hit distance can show that it sits behind a wall, whether a parent's depth predicts the lower ray's, and when a straight ray to a parent's interval start exists at all.

This paper measures thirteen merges in a 3D voxel lab against exact and brute-force references and derives why each behaves as it does. The contributions, each marked as derived (with an assert-checked script), measured, or conjectured, are:

1. **A merge benchmark in 3D.** Closed boxes under a uniform sky give an exact leak of zero inside and an exact fluence outside; a cube light in empty space has exact solid angles; two rooms have brute-force references. Every merge is measured for leaks through walls of one to three voxels, errors and cost in rays, voxel steps and texture reads, on grid offsets held out from every choice (measured, @sec:merges).
2. **Limits of the cheap tests.** The parent hit-distance test can only act on a parent farther from the lower probe than that parent's interval start. At the equal-error interval that is 10/64 of the weight at the first hand-over and none above it, and measured it changes nothing (derived, @sec:geometry; measured, @sec:merges). The straight-ray sphere-intersection fix is defined for 0.60, 0.997 and 1.000 of the parents and directions at the three hand-overs; used where it is undefined it more than doubles the error (derived, @sec:bent; measured).
3. **Reading toward a depth.** A parent read toward the point at depth $D$ on the lower ray is off by about $|\delta_\perp|\,|1/d - 1/D|$ for a hit at depth $d$, so the parallax fix ($D$ at the interval end) is worse than vanilla for hits beyond twice that distance. Averaging the parents' depths with trilinear weights is exact for any plane all parents see; averaging inverse depths is not (derived, @sec:depth). The depth estimate fails for lights narrower than the parent spacing: the merge keeps only the share $K(a/h)$ of such a light, 0.68 at $a/h = 1/2$ and about $3.7(a/h)^2$ below it (derived, @sec:smalllight); measured, 0.81 to 0.87 and 0.27 (@sec:lamp).
4. **The self test** (new). A parent is dropped when the lower probe's own stored ray toward the start of that parent's interval stops short of it. It uses what DexRT's inner parallax fix uses [@osborne2025dexrt], as a gate instead of a blend, and costs one extra texture read per parent and no rays. It halves the leak behind one-voxel walls, cuts it eightfold behind three-voxel walls, and lowers the room errors by 13% and 17%, where the blend raises them (measured, @sec:merges, @sec:handover).
5. **Merges chosen per hand-over.** The hand-overs fail differently: the first one punishes any change of read direction, the second leaks most, the last suits bent rays. Chosen on training offsets and reported on held-out ones, depth reprojection with the self test at the first two hand-overs and the sphere fix at the last cuts the leak 4.3-fold and the room errors by 20% and 17% at 1.03 times the voxel steps; sealing every hand-over with bent rays costs six times the steps and raises the error (measured, @sec:handover).
6. **Parameters and small lights in 3D.** The equal-error interval $\sqrt{N_0/4\pi}$ is the best vanilla interval at 32 directions, but only on a direction map turned against the voxel axes; aligned with them, the error jumps by half just above it (measured; cause conjectured). Overlapping intervals trades leak for error with no kink at the derived closing value. The angular error of a small light falls as about $x^{-0.68}$, not $x^{-1}$ (measured, @sec:lamp, @sec:parameters).

The merges other than the self test and the depth estimate are prior art, credited in @sec:background. What is new here is the self test, the depth estimate, the per-hand-over choice, the limits derived for each merge, and the measurements.

# Background and related work {#sec:background}

## Radiance cascades in 3D {#sec:rc}

Cascade $c$ holds probes at spacing $\Delta s_c = 2^c\,\Delta s_0$, each with $N_c = 4^c N_0$ directions, and traces the interval $[t_{c-1}, t_c]$ with $t_c = 4^c t_0$ and $t_{-1} = 0$; the top cascade runs to infinity. Each bin of cascade $c$ has four child bins in cascade $c+1$. A texel stores the radiance its ray hits within the interval, or nothing and full transmittance on a miss. Merging runs from the top down: a texel whose ray missed takes the merged radiance of its upper cascade in the same direction. In the vanilla merge that is the trilinear blend, over the eight upper probes around the lower probe, of each probe's mean over the four child bins [@sannikov2023]. We call the merge from cascade $c+1$ into cascade $c$ hand-over $c$.

The parents' view differs from the lower probe's in two ways. A parent offset by $\delta$ from the lower probe sees a surface at depth $d$ in a direction off by about $|\delta_\perp|/d$; at the start of the parent's interval that shift is 1.7 to 5.2 mean parent bins at the equal-error interval, the same at every hand-over (derived). And the parent's interval starts at $q + t_c\omega$, not at the lower ray's end $p + t_c\omega$: a wall between those two points is seen by neither ray, and light from beyond it leaks through. Parent offsets up to 1.3 upper spacings make both effects large in 3D. In flatland the error of radiance cascades splits into angular and spatial parts, the spatial part dominates at short intervals, and the bilinear fix gives the lowest error measured [@kurushimee2026error]; this paper takes the merge question to 3D.

## Merges {#sec:priormerges}

**Bent rays.** The bilinear fix traces, for each parent, a ray from the lower interval's start to that parent's interval start, merges it with that parent, and blends the results with the interpolation weights [@mytino2024; @osborne2024; @sannikov2024testbed]. No light can pass between the two intervals, at four times the rays in 2D. Its 3D form, the trilinear fix, traces eight; DexRT has one but turns it off [@osborne2025dexrt]. A tetrahedral variant interpolates over the four corners of the Kuhn simplex holding the probe [@kuhn1960], which needs two to four rays instead of eight. The circle fix keeps one straight ray and reads each parent where that ray crosses the parent's interval-start circle [@mytino2024circle; @chronicl]; we call its 3D form the sphere fix.

**Reading parents in another direction.** The parallax fix reads each parent in the direction of the lower ray's end point [@sannikov2024testbed; @osborne2025dexrt]. Reservoir Cascades reproject the read through one point per hand-over, at depth $\sqrt{t_{c}\,t_{c+1}}$, the geometric middle of the parent's interval, and show that this cancels parallax exactly at that depth [@reservoircascades]. Screen-space probes reproject each coarser hit point into the finer probe [@mathis2024lxbyrh] or correct parallax from stored hit distances [@boisse2023gi10]. DexRT's inner parallax fix composites the lower probe's own radiance toward each parent's interval start in front of that parent [@osborne2025dexrt; @sannikov2024testbed].

**Visibility tests.** In 3D surface and voxel probes, a parent counts only if its own stored hit distance toward the lower probe does not fall short of it [@mathis2024x3xfrm; @mathis2025m3ycwt], or if the lower probe lies inside its cone at the hit distance [@yhyu13]. erhe traces one visibility ray per parent from the lower ray's end toward that parent's interval start and drops the parents it blocks [@erhe]. Reservoir Cascades shadow-test the segment from the lower probe to each parent's sample with some probability and renormalize over the survivors [@reservoircascades]. Probe grids outside radiance cascades test visibility with stored depth moments [@majercik2019].

**Overlap.** Extending each interval past the next one's start closes the gaps between them; in flatland an overlap of $0.75\sqrt2$ upper spacings closes every gap, and in 3D $0.75\sqrt3 = 1.30$ [@kurushimee2026error].

**What is measured.** Reservoir Cascades measure in flatland that the bilinear fix keeps 95% of vanilla's leak behind a thin bar, while their validation removes most of it [@reservoircascades]. erhe measures leaks between two rooms in one scene [@erhe]. No 3D study measures the merges' leaks, errors and costs against a reference.

# The lab {#sec:lab}

**Scene and tracer.** A cube of $48^3$ voxels holds solid voxels, each with an emitted radiance, and a sky of uniform radiance outside the cube. Rays march voxel by voxel (DDA) to their first solid voxel and return its radiance; a ray that leaves the cube returns the sky's. Lengths are in voxels.

**Cascades.** Cascade 0 has one probe at each voxel centre, $\Delta s_0 = 1$, and cascade $c$ has probes at the centres of cells $2^c$ voxels wide. A lower probe therefore sits at a quarter or three quarters of its upper cell on each axis, and its trilinear weights are 0.75 and 0.25 per axis. Directions use an equal-area cylindrical map of $2m \times m$ bins in azimuth and height, $m = 4 \cdot 2^c$, so $N_0 = 32$; each bin's four children are its $2 \times 2$ subdivision. One ray per bin leaves along the bin's centre direction. The map is turned by a fixed generic rotation, so no bin direction lines up with the voxel axes (@sec:parameters shows why). At $t_0 = t_{\mathrm{eq}} = \sqrt{N_0/4\pi} = 1.60$, the equal-error interval [@kurushimee2026error], four cascades cover the cube: hand-overs 0, 1 and 2 start at 1.60, 6.38 and 25.5 voxels.

**Stored values.** Each texel stores the radiance its ray hit and the hit distance, infinite on a miss. After merging, each texel also stores a merged depth: its own hit distance if it hit, otherwise the depth its merge estimates (@sec:depth).

**References.** Fluence at a point is the integral of incoming radiance over the sphere. The references are exact where the scene allows: zero inside a closed box, $4\pi$ less the box's solid angle outside it under a unit sky, and the solid angle of a cube light, all in closed form. Elsewhere the reference averages $2r^2 = 18\,432$ stratified jittered rays per point; two references with independent rays differ by 0.9% relative RMS in the rooms, small against the errors measured. The lab runs on a GPU; one solve takes about 35 ms.

**Cost.** Each solve counts the rays traced, the voxels the DDA visits (steps), and the texels read. Costs are reported relative to vanilla, which traces $8.2 \times 10^6$ rays and visits $3.5 \times 10^7$ voxels in one solve of the room.

# Theory {#sec:theory}

## The hand-over in 3D {#sec:geometry}

The eight parents of a lower probe sit at offsets of 0.25 or 0.75 upper spacings per axis, at four distances: 0.433, 0.829, 1.090 and 1.299 upper spacings, with total weights 27/64, 27/64, 9/64 and 1/64 (derived). The upper spacing at hand-over $c$ is $2^{c+1}$ voxels.

**The parent hit-distance test.** It keeps parent $q$ when $q$'s stored hit distance toward $p$ is at least $|q - p| - \tau$. But $q$'s rays start at $t_c$, so $q$ records no hit nearer than $t_c$, and the test can drop $q$ only if
$$|q - p| - \tau > t_c.$$ {#eq:hitdistance}
At $t_0 = 1.60$ and $\tau = 0.5$ voxels, hand-over 0 has $t_0 = 1.60$ against parent distances of 0.87, 1.66, 2.18 and 2.60 voxels, so only the two farthest classes, 10/64 of the weight, can ever be dropped. At hand-over 1, $t_1 = 6.38$ exceeds the farthest parent's 5.20 voxels, and at hand-over 2 $t_2 = 25.5$ exceeds 10.4: the test never acts. It can act at all only for $t_0$ below 2.10, 1.17 and 0.62 at the three hand-overs (derived).

## Reading toward a depth {#sec:depth}

A lower ray from $p$ in direction $\omega$ that misses its interval would, at depth $D$, reach $p + D\omega$. Reading parent $q$ toward that point,
$$u_q = \frac{p + D\omega - q}{|p + D\omega - q|},$$ {#eq:reproject}
instead of along $\omega$, makes the parent look at what the lower ray sees if the hit lies at depth $D$. Vanilla is $D = \infty$; the parallax fix is $D = t_c$, the end of the lower ray; the fixed-depth reprojection of Reservoir Cascades is $D = \sqrt{t_c t_{c+1}}$. For a hit at depth $d$ instead, the read is off by the angle
$$\theta \approx |\delta_\perp|\,\left|\frac1d - \frac1D\right|,$$ {#eq:parallax}
where $\delta_\perp$ is the parent's offset across the ray (derived, within 5% for offsets small against both depths). Vanilla's error is $|\delta_\perp|/d$, so any fixed $D$ helps for hits nearer than $2D$ and hurts beyond: the parallax fix is worse than vanilla for every hit beyond $2t_c$ (derived). The parent's interval runs from $t_c$ to $4t_c$, so two thirds of it lies beyond $2t_c$.

**The depth estimate.** Each parent stores a merged depth $d_q$ along each child direction $\omega$. The lower ray's depth is estimated from the parents that see a surface,
$$\hat D = \frac{\sum_{q \in S} w_q \left(d_q + (q - p)\cdot\omega\right)}{\sum_{q \in S} w_q},$$ {#eq:depth}
clamped to at least $t_c$, and $\hat D = \infty$ when no parent sees a surface. The term $(q-p)\cdot\omega$ moves each parent's depth to the lower probe's origin. Depth to a plane is linear in the origin and trilinear weights reproduce linear functions, so @eq:depth is exact for any plane that every parent sees (derived). The alternative that averages inverse depths, counting a parent that sees the sky as infinitely far, is exact only for a plane that faces the ray; tilted by 60° at six upper spacings it falls 2.4% short (derived). We call the merge that reads each parent toward $\hat D$ with @eq:reproject *depth reprojection*.

## The self test {#sec:selftest}

The lower probe has already traced its own interval in every direction. Parent $q$, read in direction $u$, starts its ray at $S_q = q + t_c u$. If the lower probe's own ray in the bin toward $S_q$ hit something before reaching it, a surface lies between the lower probe and the start of the parent's ray, and the parent sees from the other side. The self test keeps parent $q$ when
$$h_p(\mathrm{bin}(S_q - p)) \ge |S_q - p| - \tau,$$ {#eq:selftest}
with $h_p$ the lower probe's stored hit distance and $\tau$ half a lower spacing, $2^{c-1}$ voxels. The merge renormalizes over the kept parents. When all of them are dropped, it returns what the lower probe's rays toward the parents' starts saw. Each test reads one texel of the lower probe and traces nothing.

**What it sees.** The lower ray from $p$ to its end $X = p + t_c\omega$ is clear, or the merge would not run. A planar wall that separates $X$ from $S_q$ therefore crosses the segment from $p$ to $S_q$, and the self test sees it if the crossing lies inside the stored ray's range $[t_{c-1}, \min(t_c, |S_q - p|)]$. Over parents and directions at the equal-error interval, $S_q$ lies beyond $t_c$ for 0.72, 0.61 and 0.56 of the cases at the three hand-overs, and the stored ray covers on average 0.78, 0.64 and 0.69 of the segment (derived). So the self test sees walls near the lower probe and misses those in the uncovered part: it can reduce leaks, but not seal them.

**Gate and blend.** DexRT's inner parallax fix reads the same rays and composites the lower probe's radiance toward $S_q$ in front of the parent [@osborne2025dexrt]. When a wall blocks $S_q$, the blend replaces the parent's value with the wall's radiance, but the wall does not lie on the lower ray; the gate instead trusts the parents that the lower probe can see. @sec:handover compares the two.

## Bent rays {#sec:bent}

The trilinear fix replaces the lower ray, for each parent, with a ray from $p + t_{c-1}\omega$ to $q + t_c\omega$; a hit on it returns the hit's radiance, and otherwise the parent is read in its four child directions. The Kuhn fix does the same for the four vertices of the Kuhn simplex holding $p$, skipping vertices of zero weight. Both leave a small leak: the bent ray ends at the parent's interval start along $\omega$, while the parent's four child rays start up to $t_c$ times half a lower bin away from it, and a wall between those points goes unseen.

The sphere fix keeps one straight lower ray and continues it until it leaves the sphere of radius $t_c$ around each parent, where that parent's interval starts; there it reads the parent toward the exit point. The exit lies ahead of the ray's start for every parent and direction only if the lower interval is at least $0.75\sqrt3$ upper spacings long: 2.60, 5.20 and 10.4 voxels at the three hand-overs, against interval lengths of 1.60, 4.79 and 19.1 at the equal-error interval. The fix is defined for 0.60, 0.997 and 1.000 of the weight and directions; where it is undefined the parent is read along $\omega$, as in vanilla. The read bends by 1.8, 2.3 and 2.2 parent bins on average, and up to 32.9° for the nearest parent at hand-over 0 (derived). *Sphere where defined* uses the sphere fix only at hand-overs where it is defined everywhere, hand-over 2 here, and the Kuhn fix elsewhere.

## Depth reprojection and small lights {#sec:smalllight}

All probes of a cascade share their bin directions, so the parents' rays in a child direction $\omega$ are parallel to the lower probe's. The depth estimate of @eq:depth along $\omega$ exists only where some parent's ray along $\omega$ hits a surface. Take a small light of side $a$ in otherwise empty space. Where the lower probe would see it along $\omega$ but no parent's parallel ray hits it, $\hat D = \infty$, the read stays along $\omega$, and every parent misses the light. Where a parent hits it but the lower probe would not, the read moves to the empty point $p + \hat D\omega$. The lower probe keeps the light only in the directions where at least one of its eight parents also hits it.

For $p$ uniform in its upper cell of side $h$, $\omega$ uniform and the hit point uniform over the light's cross-section, the kept share depends on $a/h$ alone. Sampling that condition gives $K = 1.00$, 0.68, 0.22 and 0.057 at $a/h = 1$, 1/2, 1/4 and 1/8 (derived). For a light much smaller than the cell, $K$ is the density of the parents' offsets across the ray at zero times the light's cross-section. The offsets $q - p$ of the eight parents tile the doubled cell $[-h, h]^3$ once, so their density across the ray at zero is the doubled cell's chord, $2h/\max_i|\omega_i|$, over $h^3$, and the cross-section is $a^2\sum_i|\omega_i|$:
$$K \approx 2\left(\frac ah\right)^2 \mathrm{E}\!\left[\frac{\sum_i|\omega_i|}{\max_i|\omega_i|}\right] = 3.70\left(\frac ah\right)^2,$$ {#eq:kept}
within 2% of the sampled value at $a/h = 1/8$ (derived). A hand-over loses most of a light narrower than half its parent spacing. The parallel parent rays that make the estimate fail are also what make it exact for planes: a plane all parents see is hit by every parallel ray.

# Experiments {#sec:experiments}

## Setup {#sec:setup}

Seven scenes in the $48^3$ cube cover leaks, open space and rooms:

- *Sealed 1, 2, 3*: a closed hollow box 20 voxels wide with walls of one, two or three voxels, under a sky of radiance 1. The **leak** is the mean fluence inside over $4\pi$, the share of the sky that gets in; the **outside** error is the relative RMSE of fluence at every empty voxel outside against the exact $4\pi - \Omega_{\mathrm{box}}$.
- *Lamp by wall*: the same box with walls of one voxel, in a black sky, with a lamp of $2^3$ voxels and radiance 50 two voxels outside one wall. Its leak is the mean fluence inside over the lamp's mean fluence at the wall's outer face.
- *Lamp*: a cube light of side 2 and radiance 1 in empty black space. Its error is the RMS over every empty voxel of the relative error against the exact solid angle, so far and near voxels count alike.
- *Room*: a closed room 40 voxels wide with walls of two voxels, a ceiling emitter $12 \times 12$ voxels of radiance 4, and two dark blocks on the floor.
- *Partition*: the same room split by a wall one voxel thick with a doorway 8 voxels wide and 18 tall, the emitter on one side and a block on the other, so the far side is lit only through the door.

The room errors are the relative RMSE of fluence at 4096 random empty voxels against the brute-force reference. Surfaces emit and absorb; nothing reflects.

Error depends on where a scene sits against the probe grids, so every scene is moved by whole-voxel offsets drawn from $[0, 8)^3$, which vary the alignment of every cascade. Four training offsets serve every choice made from the data; every number reported below, unless marked as training, is the mean over four other test offsets. Parameters are $N_0 = 32$, $t_0 = t_{\mathrm{eq}} = 1.60$ and no overlap unless stated.

## Every merge {#sec:merges}

@tbl:merges gives each merge used at all three hand-overs.

| Merge | Leak, walls of 1 / 2 / 3 voxels | Lamp by wall | Outside | Lamp | Room | Partition | Rays | Steps | Reads |
|--------------------|-------------------------|-------|--------|------|------|----------|------|------|-------|
| vanilla | 4.51 / 1.37 / 0.263 | 1.41 | 1.53 | 37.2 | 14.8 | 16.6 | 1.00 | 1.00 | 1.00 |
| parallax fix | 0.86 / 0.15 / 0.023 | 0.17 | 1.95 | 41.1 | 22.6 | 31.0 | 1.00 | 1.00 | 4.00 |
| fixed depth | 1.98 / 0.36 / 0.039 | 0.52 | 1.63 | 38.4 | 17.0 | 22.1 | 1.00 | 1.00 | 3.49 |
| depth, inverse mean | 2.33 / 0.29 / 0.030 | 0.38 | 1.14 | 39.7 | 15.6 | 19.4 | 1.00 | 1.00 | 3.78 |
| depth | 1.28 / 0.17 / 0.024 | 0.30 | 1.18 | 60.7 | 14.9 | 18.4 | 1.00 | 1.00 | 3.78 |
| hit-distance test | 4.49 / 1.38 / 0.264 | 1.41 | 1.47 | 37.2 | 14.6 | 16.3 | 1.00 | 1.00 | 1.25 |
| visibility rays | 0.00 / 0.00 / 0.000 | 0.00 | 1.11 | 36.9 | 20.3 | 23.3 | 5.99 | 5.11 | 1.00 |
| inner parallax fix | 3.43 / 0.80 / 0.169 | 1.05 | 1.90 | 35.3 | 18.1 | 23.6 | 1.00 | 1.00 | 6.99 |
| self test | 2.25 / 0.43 / 0.032 | 0.58 | **0.58** | 37.2 | 12.9 | **13.8** | 1.00 | 1.00 | 2.00 |
| depth + self test | 1.05 / 0.13 / 0.016 | 0.28 | 0.91 | 60.7 | **12.2** | 14.1 | 1.00 | 1.00 | 4.78 |
| trilinear fix | 0.01 / 0.00 / 0.000 | 0.00 | 1.45 | **29.9** | 16.1 | 21.5 | 7.11 | 8.22 | 0.97 |
| Kuhn fix | 0.01 / 0.00 / 0.000 | 0.00 | 1.54 | 43.1 | 19.2 | 24.9 | 2.53 | 2.83 | 0.34 |
| sphere fix | 0.57 / 0.01 / 0.001 | 0.14 | 3.38 | 45.0 | 38.4 | 46.1 | 1.00 | 1.26 | 2.99 |
| sphere where defined | 0.03 / 0.00 / 0.000 | 0.00 | 1.45 | 39.6 | 19.2 | 24.8 | 2.23 | 2.29 | 0.96 |

: Each merge at every hand-over, on the test offsets. Leaks are percent of the sky (sealed boxes) or of the lamp's fluence at the wall (lamp by wall); errors are percent; costs are per solve relative to vanilla. Bold marks the lowest error per column. Fixed depth, depth and depth, inverse mean are the reprojections of @sec:depth. {#tbl:merges}

**No straight-ray merge seals.** Vanilla lets 4.5% of the sky into a box with walls one voxel thick and still 0.26% through three voxels. Every merge that reads parents along straight lines leaks; only the merges that trace between the lower probe and each parent (visibility rays, trilinear and Kuhn fixes, and the sphere fix where it is defined) seal, to $3 \times 10^{-4}$ of the sky or less, at 2.3 to 8.2 times the voxel steps.

**Sealing costs accuracy.** Every sealing merge has a higher room error than vanilla: the trilinear fix 16.1% and 21.5% against 14.8% and 16.6%, the Kuhn fix 19.2% and 24.9%, visibility rays 20.3% and 23.3%. Bent rays look along directions off the bin's centre, by up to the parent offset over the interval length, which we conjecture is what raises their error; visibility rays drop parents and return nothing when all are dropped. The trilinear fix has the lowest error around the small light (29.9% against 37.2%), as the bilinear fix does in flatland [@kurushimee2026error].

**The hit-distance test does nothing.** It is within 0.3 points of vanilla everywhere, as @eq:hitdistance predicts: it can act on only 10/64 of the weight at hand-over 0 and on none above.

**The self test costs no rays and helps on every scene but the small light.** At two reads per parent it halves the leak behind one-voxel walls, cuts it threefold behind two and eightfold behind three, lowers the room errors from 14.8% and 16.6% to 12.9% and 13.8%, and cuts the outside error from 1.53% to 0.58%. It leaves the small light unchanged. The inner parallax fix, which reads the same rays and blends them, raises the room errors to 18.1% and 23.6% at seven times the reads.

**Reprojection helps leaks and hurts error.** Reading parents toward a point on the lower ray cuts the leak, since it looks at the region the lower probe would see: the parallax fix to 0.86%. But it raises the room errors, the parallax fix to 22.6% and 31.0%, as @eq:parallax predicts for hits beyond $2t_c$. With the depth estimate the room error stays at vanilla's, the partition error rises by 11%, and the leak falls 3.5-fold; with the self test added, the room error falls to 12.2%. The inverse mean is worse than the surface mean on leaks and partition error. Both depth reprojections raise the small light's error to 60.7%, which @sec:lamp explains.

**The sphere fix fails where it is undefined.** Used at every hand-over it more than doubles the room errors, 38.4% and 46.1%. @sec:handover shows that the damage is at hand-over 0, where it is undefined for 40% of the cases. Used only at hand-over 2 with the Kuhn fix below, it seals the box to $3 \times 10^{-4}$ at 2.29 times the steps, against the Kuhn fix's 2.83, with the same errors.

## Merges by hand-over {#sec:handover}

Each merge was then used at one hand-over, with vanilla at the other two, on the training offsets (@fig:handover). The hand-overs differ.

![Each merge used at one hand-over, with vanilla at the others, on the training offsets. Left: change of the mean room and partition error against vanilla's 17.5%, on a scale linear within ±10%. Right: the share of the sky leaked into the box with one-voxel walls; the vertical line is vanilla's 4.63%.](figures/handover.png){#fig:handover width=100%}

**Hand-over 0** punishes any change of read direction. The parallax fix raises the error by 40%, visibility rays by 15% and the sphere fix by 131%. The self test lowers it by 12%, depth reprojection with the self test by 9% and the trilinear fix by 8%; the inner parallax fix, which reads the same rays as the self test, raises it by 6%.

**Hand-over 1** leaks most. With the trilinear fix at the other two, vanilla at hand-over 1 alone lets in 3.38% of the sky, against 1.11% at hand-over 0 and 0.05% at hand-over 2. Here depth reprojection lowers the error by 6% and, with the self test, by 7%, while the trilinear and Kuhn fixes raise it by 15% and 22%.

**Hand-over 2** suits bent rays: the trilinear, Kuhn and sphere fixes each lower the error by 4%, and its parents' intervals start 25.5 voxels out, beyond most walls, so its leak is small.

Combinations were chosen from the four best merges at each hand-over by training error, plus the trilinear and Kuhn fixes, 120 combinations in all, under three rules: the lowest error at no more than 1.05 times vanilla's voxel steps; the lowest error with a leak under 0.05%; and the lowest error overall. @tbl:chosen reports them on the test offsets.

| Choice | Training error | Leak, walls of 1 / 2 / 3 voxels | Lamp by wall | Outside | Lamp | Room | Partition | Steps | Reads |
|-----------------|---------|----------------------|-------|--------|------|------|----------|------|-------|
| vanilla | 17.5 | 4.51 / 1.37 / 0.263 | 1.41 | 1.53 | 37.2 | 14.8 | 16.6 | 1.00 | 1.00 |
| few steps | 13.4 | 1.06 / 0.13 / 0.016 | 0.29 | 0.86 | 35.6 | 11.9 | 13.8 | 1.03 | 4.88 |
| sealed | 19.5 | 0.03 / 0.00 / 0.000 | 0.00 | 1.37 | 31.7 | 16.0 | 21.3 | 6.01 | 1.49 |
| lowest error | 13.4 | 1.53 / 0.13 / 0.015 | 0.57 | 0.77 | 27.4 | 11.8 | 12.9 | 3.23 | 2.67 |

: Merges chosen per hand-over on the training offsets, reported on the test offsets. At hand-overs 0, 1 and 2, *few steps* uses depth reprojection with the self test, the same, and the sphere fix; *sealed* uses the trilinear fix, the trilinear fix and the sphere fix; *lowest error* uses the self test, depth reprojection with the self test, and the trilinear fix. The training error is the mean room and partition error on the training offsets. Few steps and lowest error tie on it, at 13.40%. {#tbl:chosen}

At 1.03 times vanilla's voxel steps and 4.9 times its reads, the few-steps choice cuts the leak 4.3-fold and the room errors by 20% and 17%. Its training error fell from 17.5% to 13.4%, by 23%; on the test offsets the mean of the two room errors fell by 18%, so about a fifth of the training gain came from fitting the training offsets. The lowest-error choice adds the trilinear fix at hand-over 2 for 3.2 times the steps, which lowers the partition error to 12.9% and the small light's to 27.4%. Sealing every hand-over costs six times the steps and leaves the room errors above vanilla's.

## Small lights {#sec:lamp}

**The angular term.** One ray per bin estimates a light's solid angle by the bins whose ray hits it. We measured that estimate alone, for a unit cube seen from 96 000 random points through maps of 32 to 32 768 bins, against the exact solid angle, as a function of the number of bins the light covers, $x$ (@fig:lamp, left). In flatland a light spanning $x$ rays errs as $x^{-1}$, since only its two ends are uncertain [@kurushimee2026error]; in 3D its whole outline is, and the flatland paper conjectured $x^{-3/4}$ by analogy with lattice-point counts. The fitted exponent over $4 \le x \le 256$ is $-0.69$ for all maps pooled, and $-0.67$ to $-0.68$ over each two-octave window; single maps give $-0.56$ to $-0.86$. So $x^{-1}$ is ruled out, and the error falls a little more slowly than the conjectured $x^{-3/4}$ (measured). The outline of a cube is a polygon whose edges change with the viewpoint, and the bins are not square, so lattice-point results need not carry over.

![Left: relative RMS error of the one-ray-per-bin solid angle of a cube against the number of bins it covers, pooled over maps of 32 to 32 768 bins, with three power laws. Right: relative RMS error of the full solve at every empty voxel around cube lights of three widths, against distance; vertical lines mark the hand-overs at 1.60, 6.38 and 25.5 voxels.](figures/lamp.png){#fig:lamp width=100%}

**The full solve.** Around cube lights of width 2, 4 and 8, the error of the full vanilla solve peaks just inside the end of each interval (@fig:lamp, right). A light of width $a$ facing a probe at distance $D$ covers $x = a^2 N_c/(4\pi D^2)$ bins of cascade $c$; at $t_0 = t_{\mathrm{eq}}$ that is $(a/2^c)^2$ at the end of cascade $c$'s interval, 16 times more at its start, and four times more across each hand-over (derived). The peaks sit where $x$ is smallest. From the peak at 23 voxels to 32 voxels, past the hand-over at 25.5, $x$ grows 2.2-fold, for which the angular law predicts a fall of 41% (derived); the error falls by 53% to 65% for the three widths (measured). At the peak the error also falls by only 44% and 29% per doubling of the light's width, against 61% for the angular law. Both point to a second term that depends less on the light's size and also peaks at the hand-overs; we conjecture it is the spatial term of the merge, as in flatland.

**Depth reprojection.** @tbl:kept uses depth reprojection at one hand-over at a time and compares each probe's fluence with vanilla's, over the probes that the light reaches only through that hand-over: those farther than the hand-over's start by the light's half-diagonal and the reach of the hand-over's lower probes.

| Light width $a$ | Hand-over | Parent spacing $h$ | $a/h$ | Kept share, derived $K$ | Kept share, measured |
|----|----|----|----|----|----|
| 2 | 0 | 2 | 1 | 1.00 | 0.99 |
| 4 | 1 | 4 | 1 | 1.00 | 0.99 |
| 8 | 2 | 8 | 1 | 1.00 | 1.00 |
| 2 | 1 | 4 | 1/2 | 0.68 | 0.87 |
| 4 | 2 | 8 | 1/2 | 0.68 | 0.81 |
| 2 | 2 | 8 | 1/4 | 0.22 | 0.27 |

: Mean ratio of the fluence with depth reprojection at one hand-over to vanilla's, where the light arrives only through that hand-over, against the share $K(a/h)$ of @sec:smalllight. Lights at least as wide as the parent spacing keep 0.97 to 1.00 at every hand-over. {#tbl:kept}

The loss follows $a/h$ as derived: none when the light is as wide as the parent spacing, an eighth to a fifth at half that width, three quarters at a quarter. The measured shares lie above $K$ by 0.05 to 0.19. The derivation assumes exact reads, while the reprojected read interpolates four parent bins, whose footprint near the light can reach part of it when the read point lies beside it (conjectured). Used at every hand-over, depth reprojection raises the small light's error from 37.2% to 60.7% (@tbl:merges); in the chosen combinations it sits only at hand-overs 0 and 1, where a light two voxels wide loses 13% or less.

## The cascade 0 interval and overlap {#sec:parameters}

@fig:parameters (left) varies $t_0$ from half to twice $t_{\mathrm{eq}}$ for 8, 32 and 128 directions at cascade 0.

![Left: mean room and partition error against $t_0/t_{\mathrm{eq}}$ for three direction counts and three merges, and for vanilla at 32 directions with the direction map aligned with the voxel axes (grey). Right: the share of the sky leaked into the box with one-voxel walls against interval overlap; the vertical line marks $0.75\sqrt3 = 1.30$ upper spacings.](figures/parameters.png){#fig:parameters width=100%}

**The equal-error interval holds in 3D.** At 32 directions the vanilla error is lowest at $t_{\mathrm{eq}}$ (15.7%) and within 13% of that from 0.84 to 1.41 $t_{\mathrm{eq}}$. At 128 directions it is flat, 9.0% to 9.9%, from 0.84 to 2 $t_{\mathrm{eq}}$; at 8 directions it varies between 24.0% and 28.6% from 0.71 $t_{\mathrm{eq}}$ up, with no clear optimum (measured). The self test's best interval is a little shorter at 8 and 32 directions, 0.84 $t_{\mathrm{eq}}$, and 1.41 $t_{\mathrm{eq}}$ at 128. The trilinear fix wants longer intervals, still falling at 2 $t_{\mathrm{eq}}$ for 8 and 32 directions and lowest at 1.68 $t_{\mathrm{eq}}$ for 128, where at 6.9% it is the best merge measured. Its bent rays leave the bin's direction by up to the parent offset over the interval length, and a longer interval straightens them (conjectured).

**Axis alignment.** With the direction map aligned with the voxel axes, vanilla at 32 directions is close to the turned map at $t_{\mathrm{eq}}$ (16.6%), but its error jumps to 25.0% at 1.19 $t_{\mathrm{eq}}$ and 30.5% at 1.41 $t_{\mathrm{eq}}$, against 16.5% and 17.7% on the turned map (measured). The scenes' walls are axis-aligned, and an aligned map meets them with symmetric sets of bin directions, so whole sets of rays end at the same wall at once (conjectured). Every other experiment uses the turned map.

**Overlap.** Extending each interval end by an overlap (@fig:parameters, right) lowers vanilla's leak from 4.51% to 2.18%, 1.15%, 0.64% and 0.45% at 0.33, 0.65, 1.0 and 1.30 upper spacings, and on to 0.22% at 2, with no kink at the closing value of 1.30. Overlap closes the gaps between intervals, but the leak in 3D comes mostly from parents that see past a wall from where they stand, which only a longer lower ray that reaches the wall itself can stop. Meanwhile the room error rises from 14.8% to 28.0% at 1.30, since the lower cascade's coarser bins take over the parents' near range. The self test leaks less: 0.53% at 0.33 and 0.13% at 0.65 upper spacings, with room errors of 14.9% and 18.1% (measured). @sec:further gives the full tables.

# Discussion {#sec:discussion}

**What to use.** Where leaks through thin walls matter and rays are the budget, the self test is the merge to start from: it costs reads only and helps on every scene measured. Depth reprojection adds to it at the lower hand-overs, but at a hand-over whose parent spacing exceeds twice the width of the scene's smallest lights it loses those lights (@eq:kept); there the trilinear or sphere fix is the better choice. Sealing a closed room completely needs rays from the lower probe toward its parents at every hand-over that leaks, and in these scenes it costs accuracy: bent and visibility rays raise the room errors by 9% to 50%. A renderer that must cut leaks with few rays could seal hand-over 1 first: left to vanilla with the other two sealed, it lets in 3.38% of the sky, against 1.11% for hand-over 0.

**Why the cheap tests fail in 3D.** Both the parent hit-distance test and the self test look along stored rays, and stored rays only cover their own interval. The parent's rays start at $t_c$, beyond its distance to the lower probe above hand-over 0, so the parent cannot see the lower probe. The lower probe's rays cover most of the way to the parent's interval start, which is why the self test works where the hit-distance test cannot. Neither can close the remaining gap without a ray of its own.

**Per hand-over choice.** The hand-overs have different geometry, which is why one merge does not suit all: at hand-over 0 the interval is shorter than the parent offsets, at hand-over 1 the parents start beyond thin walls that their offsets cross, and at hand-over 2 the interval is long enough for straight rays to reach every parent's sphere. The per-hand-over choices made on training offsets held on test offsets.

# Limitations {#sec:limitations}

The scenes are small, $48^3$ voxels and four cascades, and their walls are axis-aligned; the direction map is turned against them, and the aligned map behaves differently near $t_{\mathrm{eq}}$. Surfaces emit and absorb and nothing reflects, so the errors are those of direct light from emitters, and fluence stands in for irradiance. Every probe of cascade 0 sits at a voxel centre where it is evaluated, so the leak of the final gather from cascade 0 to a shading point is not measured; upper probes sit at voxel corners, and a grid offset from the voxels would change the hit-distance and self-test geometry. One ray per bin is used throughout. The room metrics are aggregates: ringing around small lights and penumbra errors are measured only through the lamp and partition scenes, not separately. Costs are counts of rays, voxel visits and texel reads, not time on a GPU. The comparison of the self test with Reservoir Cascades' validation, which traces the segment it tests, was not run.

# Conclusion {#sec:conclusion}

Measured against exact and brute-force references in 3D, merges that read parents along straight lines leak, and merges that seal leak through rays of their own and pay in error. The cheap parent test fails for a reason of geometry: a parent's rays start beyond its distance to the lower probe. The lower probe's own stored rays reach most of the way to each parent's interval start, and a self test along them halves the leak and lowers the error for two texture reads per parent. Reading parents toward a depth estimated from their stored depths is exact for planes and loses lights narrower than the parent spacing, by a share that follows from the geometry of parallel rays. Choosing the merge per hand-over gives most of the leak reduction at almost no extra rays. In 3D the equal-error interval remains the right default, on a direction map turned against the scene's axes.

# Acknowledgments {.unnumbered}

The derivations, experiments and drafting of this paper were carried out with Claude, a large language model by Anthropic, working under the author's direction.

# Further results {#sec:further .appendix}

@tbl:t0 and @tbl:outside give the sweeps of $t_0$ behind @fig:parameters, and @tbl:overlap the sweep of overlap.

| $N_0$ | Merge | 0.50 | 0.59 | 0.71 | 0.84 | 1.00 | 1.19 | 1.41 | 1.68 | 2.00 |
|------|----------------------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
| 8 | vanilla | 33.5 | 29.6 | 24.1 | 24.0 | 25.3 | 28.6 | 24.6 | **24.0** | 24.5 |
| 8 | self test | 30.1 | 27.1 | 22.0 | **20.1** | 21.8 | 23.8 | 20.9 | 22.2 | 23.7 |
| 8 | trilinear fix | 58.9 | 53.9 | 50.5 | 46.0 | 41.8 | 38.2 | 34.3 | 31.1 | **27.8** |
| 32 | vanilla | 21.5 | 21.1 | 19.2 | 16.7 | **15.7** | 16.5 | 17.7 | 18.9 | 18.7 |
| 32 | vanilla, aligned map | 28.1 | 25.1 | 24.0 | 19.0 | **16.6** | 25.0 | 30.5 | 27.9 | 26.8 |
| 32 | self test | 17.3 | 16.2 | 13.2 | **12.2** | 13.4 | 13.4 | 15.0 | 16.3 | 17.0 |
| 32 | trilinear fix | 37.5 | 33.4 | 28.7 | 23.0 | 18.8 | 16.4 | 15.0 | 13.8 | **13.4** |
| 128 | vanilla | 13.5 | 12.4 | 11.0 | 9.5 | 9.6 | 9.1 | **9.0** | 9.9 | 9.9 |
| 128 | self test | 10.0 | 9.2 | 9.2 | 8.6 | 8.5 | 8.6 | **8.3** | 9.2 | 9.6 |
| 128 | trilinear fix | 18.0 | 14.6 | 12.1 | 10.0 | 8.7 | 7.5 | 7.0 | **6.9** | 7.4 |

: Mean room and partition error, percent, against $t_0/t_{\mathrm{eq}}$; bold marks each row's lowest. {#tbl:t0}

| $N_0$ | Merge | 0.50 | 0.59 | 0.71 | 0.84 | 1.00 | 1.19 | 1.41 | 1.68 | 2.00 |
|------|----------------------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
| 8 | vanilla | 4.09 | 3.59 | 3.24 | 2.98 | 2.70 | 2.64 | 2.25 | 1.96 | 1.91 |
| 8 | self test | 2.31 | 2.00 | 1.59 | 1.27 | 1.20 | 1.20 | 1.07 | 1.03 | 1.19 |
| 8 | trilinear fix | 4.68 | 4.25 | 3.78 | 3.40 | 3.09 | 2.79 | 2.52 | 2.26 | 2.05 |
| 32 | vanilla | 2.60 | 2.38 | 2.10 | 1.77 | 1.53 | 1.35 | 1.18 | 1.09 | 1.09 |
| 32 | self test | 0.90 | 0.79 | 0.66 | 0.59 | 0.58 | 0.55 | 0.53 | 0.56 | 0.64 |
| 32 | trilinear fix | 2.67 | 2.35 | 2.05 | 1.70 | 1.45 | 1.25 | 1.09 | 0.98 | 0.91 |
| 128 | vanilla | 1.37 | 1.16 | 0.96 | 0.84 | 0.75 | 0.69 | 0.62 | 0.57 | 0.51 |
| 128 | self test | 0.43 | 0.39 | 0.36 | 0.33 | 0.32 | 0.31 | 0.32 | 0.33 | 0.36 |
| 128 | trilinear fix | 1.28 | 1.06 | 0.87 | 0.72 | 0.62 | 0.54 | 0.48 | 0.43 | 0.41 |

: Error outside the sealed box with one-voxel walls, percent, against $t_0/t_{\mathrm{eq}}$. {#tbl:outside}

| Overlap | Vanilla: leak | outside | room | Self test: leak | outside | room |
|---|---|---|---|---|---|---|
| 0 | 4.51 | 1.53 | 14.8 | 2.25 | 0.58 | 12.9 |
| 0.33 | 2.18 | 1.82 | 19.4 | 0.53 | 0.77 | 14.9 |
| 0.65 | 1.15 | 2.04 | 22.7 | 0.13 | 1.00 | 18.1 |
| 1.0 | 0.64 | 2.29 | 26.3 | 0.05 | 1.31 | 22.0 |
| 1.3 | 0.45 | 2.43 | 28.0 | 0.03 | 1.48 | 23.9 |
| 1.6 | 0.35 | 2.54 | 28.7 | 0.02 | 1.63 | 24.7 |
| 2.0 | 0.22 | 2.75 | 31.3 | 0.01 | 1.89 | 27.6 |

: Leak into the box with one-voxel walls, error outside it, and room error, percent, against interval overlap in upper spacings. {#tbl:overlap}

# Reproducibility {#sec:reproducibility .appendix}

The lab, the checks and the experiments are Python with NumPy; the voxel lab compiles its tracer, cascades and reference as CUDA kernels through CuPy, and figures use Matplotlib. Each derived number in the text has an assert-based check script, and each measured number comes from a seeded experiment script that regenerates its figure and prints its table:

| Script | Content |
|-----------------------------------|-----------------------------------------------------------------|
| `lab/selftest.py` | the voxel tracer against exact slab tests; exact box solid angles; every merge in a white furnace, on both direction maps; bent rays sealing a closed box |
| `checks/hand_over_geometry.py` | parent distances and weights, @eq:hitdistance and its thresholds, the sphere fix's definedness and bend, the self test's coverage, bins covered at interval ends |
| `checks/depth_estimate.py` | @eq:parallax, the plane exactness of @eq:depth, the inverse mean's error, the parallax fix's break-even depth |
| `checks/depth_light_loss.py` | $K(a/h)$ and @eq:kept |
| `experiments/merges.py` | @tbl:merges, vanilla's cost, the reference noise |
| `experiments/handover.py` | @fig:handover, @tbl:chosen |
| `experiments/lamp.py` | @fig:lamp, @tbl:kept, the angular exponents |
| `experiments/parameters.py` | @fig:parameters, @tbl:t0, @tbl:outside, @tbl:overlap |
| `experiments/teaser.py` | the teaser |

: Scripts behind each result. Paths are relative to the paper's directory, except the lab. {#tbl:scripts}
