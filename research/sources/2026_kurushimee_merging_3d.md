# Merging Radiance Cascades in 3D Probe Grids

| | |
|---|---|
| Author | kurushimee (independent researcher) |
| Date | 2026-10 |
| Kind | Paper, original research with code: a voxel lab with exact and brute-force references, derivations with assert-based checks, seeded experiments |
| Link | [paper.pdf](../../papers/02_merging_3d/paper.pdf), source [paper.md](../../papers/02_merging_3d/paper.md); lab in [papers/lab/volume.py](../../papers/lab/volume.py) |
| Related | [2026_kurushimee_rc_error_model.md](2026_kurushimee_rc_error_model.md), [2026_you_reservoir_cascades.md](2026_you_reservoir_cascades.md), [2025_osborne_dexrt_ray_acceleration.md](2025_osborne_dexrt_ray_acceleration.md), [2026_erhe_world_space_rc.md](2026_erhe_world_space_rc.md), [2024_mathis_x3xfrm_surface_probe_rc.md](2024_mathis_x3xfrm_surface_probe_rc.md), [2026_merging_and_ringing.md](2026_merging_and_ringing.md), [2024_sannikov_legitcascades.md](2024_sannikov_legitcascades.md) |

The first measurement of 3D merges against a reference. Thirteen merges run in a dense voxel grid with exact references where the scene allows (zero inside a closed box, the sky less the box's solid angle outside it, the solid angle of a cube light) and brute-force references in two rooms; leaks, errors and cost are reported on grid offsets held out from every choice. Derivations explain each merge's behaviour from the geometry of one hand-over. Scenes emit and absorb only (no reflection), and the quantity is fluence (no cosine). Claims are marked derived (with a check script in `papers/02_merging_3d/checks/`), measured (with a seeded script in `papers/02_merging_3d/experiments/`) or conjectured.

## Contents

- [Lab and setup](#lab-and-setup)
- [The hand-over in 3D (derived)](#the-hand-over-in-3d-derived)
- [Reading toward a depth (derived)](#reading-toward-a-depth-derived)
- [The self test (derived and measured)](#the-self-test-derived-and-measured)
- [Bent rays and the sphere fix (derived)](#bent-rays-and-the-sphere-fix-derived)
- [Every merge (measured)](#every-merge-measured)
- [Merges by hand-over (measured)](#merges-by-hand-over-measured)
- [Small lights (derived and measured)](#small-lights-derived-and-measured)
- [The cascade 0 interval, axis alignment and overlap (measured)](#the-cascade-0-interval-axis-alignment-and-overlap-measured)
- [Limits](#limits)

## Lab and setup

- **Grid:** a cube of `48³` voxels under a sky of uniform radiance; DDA rays return the first solid voxel's radiance. Cascade 0 has one probe per voxel centre (`Δs₀ = 1`), cascade `c` probes at the centres of cells `2ᶜ` wide, so a lower probe sits at 1/4 or 3/4 of its upper cell per axis with trilinear weights 0.75 and 0.25.
- **Directions:** an equal-area cylindrical map of `2m × m` bins, `m = 4·2ᶜ`, `N₀ = 32`, children by `2 × 2` subdivision, one ray per bin along the bin centre. The map is turned by a fixed generic rotation so no bin lines up with the voxel axes. At `t₀ = t_eq = √(N₀/4π) = 1.60` four cascades cover the cube, with hand-overs at 1.60, 6.38 and 25.5 voxels. Hand-over `c` is the merge from cascade `c+1` into cascade `c`.
- **Stored values:** radiance and hit distance (infinite on a miss) per texel, plus a merged depth: the texel's own hit distance, or the depth its merge estimates.
- **Scenes:** sealed boxes 20 voxels wide with walls of 1, 2, 3 voxels under a unit sky (**leak** = mean fluence inside over `4π`; **outside** = relative RMSE against the exact `4π − Ω_box`); the 1-voxel box in a black sky with a `2³` lamp of radiance 50 two voxels outside a wall; a cube light of side 2 in empty space (RMS relative error against the exact solid angle at every empty voxel); a closed room 40 wide with a ceiling emitter and two blocks; the same room split by a 1-voxel wall with a doorway. The room references average 18 432 stratified jittered rays per point (two independent references differ by 0.9% RMS).
- **Offsets and cost:** scenes are moved by whole-voxel offsets in `[0, 8)³`; four training offsets serve every choice, four test offsets every reported number. Cost counts rays, DDA voxel visits (steps) and texel reads relative to vanilla (`8.2 × 10⁶` rays and `3.5 × 10⁷` steps per solve of the room).

## The hand-over in 3D (derived)

- A lower probe's eight parents sit at 0.433, 0.829, 1.090 and 1.299 upper spacings, with total weights 27/64, 27/64, 9/64 and 1/64; the upper spacing at hand-over `c` is `2ᶜ⁺¹`.
- At the parent's interval start `t_c`, a parent offset by `δ` across the ray sees a point in a direction off by `δ·2ᶜ⁺¹/t_c`: 1.73 to 5.20 mean parent bins for the nearest and farthest parents at `t₀ = t_eq`, at every hand-over.
- **Parent hit-distance test** (keep `q` when its stored hit toward `p` is at least `|q − p| − τ`): `q` records no hit nearer than `t_c`, so the test can drop `q` only if `|q − p| − τ > t_c`. At `t₀ = 1.60, τ = 0.5` that is 10/64 of the weight at hand-over 0 (the two farthest classes, 2.18 and 2.60 voxels against 1.60) and none above (`t₁ = 6.38` against 5.20 voxels, `t₂ = 25.5` against 10.4). It can act at all only for `t₀` below 2.10, 1.17 and 0.62 at the three hand-overs.
- A light of width `a` facing a probe at distance `D` covers `x = a²N_c/(4πD²)` bins of cascade `c`; at `t₀ = t_eq` that is `(a/2ᶜ)²` at the end of cascade `c`'s interval, 16 times more at its start, and four times more across each hand-over at a fixed distance.

## Reading toward a depth (derived)

- Reading parent `q` toward `p + Dω` instead of along `ω` makes it look at what the lower ray sees if the hit lies at depth `D`. Vanilla is `D = ∞`, the parallax fix `D = t_c`, Reservoir Cascades' fixed-depth reprojection `D = √(t_c·t_c₊₁)`. For a hit at depth `d` the read is off by `θ ≈ |δ⊥|·|1/d − 1/D|` (within 5% for offsets small against both depths). Any fixed `D` helps for hits nearer than `2D` and hurts beyond: the parallax fix is worse than vanilla for hits beyond `2t_c`, two thirds of the parent's interval.
- **Depth estimate:** `D̂ = Σ_S w_q·(d_q + (q − p)·ω) / Σ_S w_q` over the parents that see a surface along `ω`, clamped to at least `t_c`, `∞` when none does. Depth to a plane is linear in the origin and trilinear weights reproduce linear functions, so `D̂` is exact for any plane every parent sees. Averaging inverse depths (sky as infinitely far) is exact only for a plane facing the ray, 2.4% short for one tilted 60° at six upper spacings. Reading each parent toward `D̂` is **depth reprojection**.
- **Small lights:** all probes of a cascade share bin directions, so the parents' rays along `ω` are parallel to the lower ray. The lower probe keeps a small light only in the directions where at least one parent's parallel ray also hits it; elsewhere `D̂ = ∞` (every parent misses it) or the read moves to an empty point. The kept share depends on `a/h` alone: `K = 1.00, 0.68, 0.22, 0.057` at `a/h = 1, 1/2, 1/4, 1/8`, and for small lights `K ≈ 2(a/h)²·E[Σ|ωᵢ|/max|ωᵢ|] = 3.70(a/h)²` (the parents' offsets tile the doubled cell once), within 2% at 1/8. A hand-over loses most of a light narrower than half its parent spacing. The parallel rays that make the estimate fail are what make it exact for planes.

## The self test (derived and measured)

- **Rule (new):** parent `q`, read in direction `u`, starts its ray at `S_q = q + t_c·u`. Keep `q` when the lower probe's own stored hit distance in the bin toward `S_q` is at least `|S_q − p| − τ`, `τ` half a lower spacing; renormalize over the kept parents, and when all are dropped return what the lower probe's rays toward the parents' starts saw. One texel read per parent, no rays. It reads the rays of DexRT's inner parallax fix, as a gate instead of a blend.
- **What it sees (derived):** the lower ray to `X = p + t_c·ω` is clear, so a planar wall separating `X` from `S_q` crosses the segment `p → S_q`; the test sees it if the crossing lies in the stored range `[t_c₋₁, min(t_c, |S_q − p|)]`. At `t_eq`, `S_q` lies beyond `t_c` for 0.72, 0.61, 0.56 of parents and directions at the three hand-overs, and the stored ray covers on average 0.78, 0.64, 0.69 of the segment: it can reduce leaks, not seal them.
- **Measured:** at two reads per parent (vanilla's one plus the test) it halves the leak behind 1-voxel walls (4.51% → 2.25% of the sky), cuts it threefold behind 2 and eightfold behind 3, lowers the room errors from 14.8% and 16.6% to 12.9% and 13.8%, and the outside error from 1.53% to 0.58%; the small light is unchanged. The inner parallax fix, the blend, raises the room errors to 18.1% and 23.6% at seven times the reads: when a wall blocks `S_q` it substitutes the wall's radiance, but the wall is not on the lower ray.

## Bent rays and the sphere fix (derived)

- The **trilinear fix** traces, per parent, a ray from `p + t_c₋₁·ω` to `q + t_c·ω`; the **Kuhn fix** does the same for the four vertices of the Kuhn simplex holding `p` (zero-weight vertices skipped). Both leave a small leak: the parent's four child rays start up to `t_c` times half a lower bin from the bent ray's end.
- The **sphere fix** continues one straight lower ray to where it leaves the sphere of radius `t_c` around each parent and reads the parent toward that exit. An exit ahead of the ray's start exists for every parent and direction only if the lower interval is at least `0.75·√3` upper spacings long (2.60, 5.20, 10.4 voxels against interval lengths 1.60, 4.79, 19.1 at `t_eq`): it is defined for 0.60, 0.997 and 1.000 of the weight and directions at the three hand-overs, read along `ω` elsewhere. The read bends by 1.8, 2.3, 2.2 parent bins on average, up to 32.9° for the nearest parent at hand-over 0.

## Every merge (measured)

Each merge at every hand-over, test offsets. Leaks in percent of the sky (lamp by wall: of the lamp's fluence at the wall), errors in percent, costs per solve relative to vanilla:

| Merge | Leak, walls 1 / 2 / 3 | Lamp by wall | Outside | Lamp | Room | Partition | Rays | Steps | Reads |
|---|---|---|---|---|---|---|---|---|---|
| vanilla | 4.51 / 1.37 / 0.263 | 1.41 | 1.53 | 37.2 | 14.8 | 16.6 | 1.00 | 1.00 | 1.00 |
| parallax fix | 0.86 / 0.15 / 0.023 | 0.17 | 1.95 | 41.1 | 22.6 | 31.0 | 1.00 | 1.00 | 4.00 |
| fixed depth `√(t_c·t_c₊₁)` | 1.98 / 0.36 / 0.039 | 0.52 | 1.63 | 38.4 | 17.0 | 22.1 | 1.00 | 1.00 | 3.49 |
| depth, inverse mean | 2.33 / 0.29 / 0.030 | 0.38 | 1.14 | 39.7 | 15.6 | 19.4 | 1.00 | 1.00 | 3.78 |
| depth reprojection | 1.28 / 0.17 / 0.024 | 0.30 | 1.18 | 60.7 | 14.9 | 18.4 | 1.00 | 1.00 | 3.78 |
| hit-distance test | 4.49 / 1.38 / 0.264 | 1.41 | 1.47 | 37.2 | 14.6 | 16.3 | 1.00 | 1.00 | 1.25 |
| visibility rays | 0.00 / 0.00 / 0.000 | 0.00 | 1.11 | 36.9 | 20.3 | 23.3 | 5.99 | 5.11 | 1.00 |
| inner parallax fix | 3.43 / 0.80 / 0.169 | 1.05 | 1.90 | 35.3 | 18.1 | 23.6 | 1.00 | 1.00 | 6.99 |
| self test | 2.25 / 0.43 / 0.032 | 0.58 | 0.58 | 37.2 | 12.9 | 13.8 | 1.00 | 1.00 | 2.00 |
| depth + self test | 1.05 / 0.13 / 0.016 | 0.28 | 0.91 | 60.7 | 12.2 | 14.1 | 1.00 | 1.00 | 4.78 |
| trilinear fix | 0.01 / 0.00 / 0.000 | 0.00 | 1.45 | 29.9 | 16.1 | 21.5 | 7.11 | 8.22 | 0.97 |
| Kuhn fix | 0.01 / 0.00 / 0.000 | 0.00 | 1.54 | 43.1 | 19.2 | 24.9 | 2.53 | 2.83 | 0.34 |
| sphere fix | 0.57 / 0.01 / 0.001 | 0.14 | 3.38 | 45.0 | 38.4 | 46.1 | 1.00 | 1.26 | 2.99 |
| sphere where defined | 0.03 / 0.00 / 0.000 | 0.00 | 1.45 | 39.6 | 19.2 | 24.8 | 2.23 | 2.29 | 0.96 |

- **No straight-ray merge seals.** Only the merges that trace between the lower probe and each parent (visibility rays, which trace from the lower ray's end to each parent's interval start; the trilinear and Kuhn fixes; the sphere fix at hand-over 2 with the Kuhn fix below, "sphere where defined") seal, to `3 × 10⁻⁴` of the sky or less, at 2.3 to 8.2 times the steps.
- **Sealing costs accuracy:** every sealing merge has a higher room error than vanilla. Bent rays look off the bin's centre by up to the parent offset over the interval length, conjectured to raise their error; visibility rays drop parents and return nothing when all are dropped. The trilinear fix has the lowest error around the small light (29.9% against 37.2%), as the bilinear fix in flatland.
- **The hit-distance test does nothing:** within 0.3 points of vanilla everywhere, as derived.
- **Reprojection helps leaks and hurts error:** the parallax fix cuts the leak to 0.86% and raises the room errors to 22.6% and 31.0%, as `θ` predicts for hits beyond `2t_c`. Depth reprojection keeps the room error at vanilla's, raises the partition error 11% and cuts the leak 3.5-fold; with the self test the room error falls to 12.2%. Both depth reprojections raise the small light's error to 60.7% (see small lights). The inverse mean is worse than the surface mean on leaks and partition error.
- **The sphere fix fails where it is undefined:** at every hand-over it more than doubles the room errors (38.4%, 46.1%), the damage being at hand-over 0; at hand-over 2 only, with the Kuhn fix below, it seals at 2.29 times the steps against the Kuhn fix's 2.83, with the same errors.

## Merges by hand-over (measured)

Each merge at one hand-over with vanilla at the other two, training offsets (vanilla: mean room and partition error 17.5%, leak 4.63%):

- **Hand-over 0 punishes any change of read direction:** the parallax fix raises the error 40%, visibility rays 15%, the sphere fix 131%, the inner parallax fix 6%; the self test lowers it 12%, depth reprojection with the self test 9%, the trilinear fix 8%.
- **Hand-over 1 leaks most:** with the trilinear fix at the other two, vanilla at hand-over 1 alone lets in 3.38% of the sky, against 1.11% at hand-over 0 and 0.05% at hand-over 2. Depth reprojection lowers the error 6%, with the self test 7%; the trilinear and Kuhn fixes raise it 15% and 22%.
- **Hand-over 2 suits bent rays:** the trilinear, Kuhn and sphere fixes each lower the error 4%; its parents start 25.5 voxels out, beyond most walls, so its leak is small.
- **Chosen per hand-over** from 120 combinations (the four best merges per hand-over plus the trilinear and Kuhn fixes) on training offsets, reported on test offsets:

| Choice (hand-overs 0, 1, 2) | Leak, walls 1 / 2 / 3 | Lamp | Room | Partition | Steps | Reads |
|---|---|---|---|---|---|---|
| vanilla | 4.51 / 1.37 / 0.263 | 37.2 | 14.8 | 16.6 | 1.00 | 1.00 |
| few steps: depth + self test, depth + self test, sphere fix | 1.06 / 0.13 / 0.016 | 35.6 | 11.9 | 13.8 | 1.03 | 4.88 |
| sealed: trilinear, trilinear, sphere fix | 0.03 / 0.00 / 0.000 | 31.7 | 16.0 | 21.3 | 6.01 | 1.49 |
| lowest error: self test, depth + self test, trilinear | 1.53 / 0.13 / 0.015 | 27.4 | 11.8 | 12.9 | 3.23 | 2.67 |

- The few-steps choice cuts the leak 4.3-fold and the room errors by 20% and 17% at 1.03 times the steps; its training error fell 23% and the test error 18%, so about a fifth of the training gain was fitting. Sealing every hand-over costs six times the steps and leaves the room errors above vanilla's. Few steps and lowest error tie on training error (13.40%).

## Small lights (derived and measured)

- **Angular term in 3D (measured):** one ray per bin estimating a unit cube's solid angle, from 96 000 random points through maps of 32 to 32 768 bins, errs as about `x^−0.69` in the number of bins covered (pooled fit over `4 ≤ x ≤ 256`; −0.67 to −0.68 per two-octave window; −0.56 to −0.86 on single maps). `x^−1`, the flatland law, is ruled out, and the fall is a little slower than the conjectured `x^−3/4`; a cube's outline is a polygon that changes with the viewpoint and the bins are not square, so lattice-point results need not carry over.
- **Full solve (measured):** around cube lights of width 2, 4, 8 the vanilla error peaks just inside the end of each interval, where `x` is smallest. From the peak at 23 voxels to 32, past the hand-over at 25.5, `x` grows 2.2-fold, for which the angular law predicts a 41% fall (derived); the error falls 53% to 65%. At the peak the error falls only 44% and 29% per doubling of the width, against 61% for the angular law. Both point to a second term that depends less on the light's size and also peaks at the hand-overs, conjectured to be the merge's spatial term, as in flatland.
- **Depth reprojection's loss (measured):** with depth reprojection at one hand-over, over the probes the light reaches only through it, the fluence kept relative to vanilla is 0.99 to 1.00 at `a/h = 1`, 0.87 and 0.81 at 1/2 (`K` = 0.68) and 0.27 at 1/4 (`K` = 0.22): the loss follows `a/h`, with measured shares 0.05 to 0.19 above `K`, conjectured because the reprojected read interpolates four parent bins whose footprint can reach part of the light.

## The cascade 0 interval, axis alignment and overlap (measured)

- **Equal error holds in 3D:** mean room and partition error over `t₀` from 0.5 to 2 `t_eq`. At 32 directions vanilla is lowest at `t_eq` (15.7%) and within 13% of that from 0.84 to 1.41 `t_eq`; at 128 directions flat (9.0% to 9.9%) from 0.84 to 2 `t_eq`; at 8 directions 24.0% to 28.6% from 0.71 `t_eq` up, with no clear optimum. The self test's best is 0.84 `t_eq` at 8 and 32 directions and 1.41 at 128. The trilinear fix wants longer intervals: still falling at 2 `t_eq` for 8 and 32 directions, lowest at 1.68 `t_eq` for 128, where at 6.9% it is the best merge measured (a longer interval straightens its bent rays, conjectured).
- **Axis alignment:** with the direction map aligned with the voxel axes, vanilla at 32 directions matches the turned map at `t_eq` (16.6%) but jumps to 25.0% at 1.19 `t_eq` and 30.5% at 1.41 `t_eq`, against 16.5% and 17.7% turned. Conjectured cause: an aligned map meets axis-aligned walls with symmetric sets of bin directions, so whole sets of rays end at the same wall at once.
- **Overlap:** vanilla's leak falls from 4.51% to 2.18%, 1.15%, 0.64%, 0.45% at 0.33, 0.65, 1.0, 1.30 upper spacings and 0.22% at 2, with no kink at the closing value 1.30: the leak in 3D comes mostly from parents that see past a wall from where they stand, which only a lower ray reaching the wall stops. The room error rises from 14.8% to 28.0% at 1.30, as the lower cascade's coarser bins take over the parents' near range. With the self test the leak is 0.53% at 0.33 and 0.13% at 0.65 upper spacings, at room errors of 14.9% and 18.1%.

## Limits

`48³` voxels and four cascades, axis-aligned walls; emission and absorption only, fluence without a cosine; cascade 0 probes sit where fluence is evaluated, so the final gather's leak is not measured, and upper probes sit at voxel corners (a grid offset from the voxels would change the hit-distance and self-test geometry); one ray per bin; room metrics aggregate ringing and penumbra errors; cost counted in rays, voxel visits and texel reads, not GPU time; the self test was not compared with Reservoir Cascades' traced validation.
