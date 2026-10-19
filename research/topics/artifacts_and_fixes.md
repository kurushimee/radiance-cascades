# Artifacts and fixes

RC artifacts, their causes and the fixes in use, with costs: ringing and the merge fixes built against it, gaps and seams between cascades, blocky penumbras, light leaks, domain edges, sky aliasing, banding and precision, sharp shadows, rays that start inside geometry, latency, the implementation bugs that recur across codes, and a debugging routine. Most artifacts come from one fact: a lower probe merges with upper probes that sit elsewhere, so their intervals start at other points and see the scene from other angles. The exactness of each merge scheme is in [core theory](core_theory.md#where-the-merge-is-exact-derived); interval formulas, kernels and layouts are in [cascade layout and merging](cascade_layout_and_merging.md); HRC's own artifacts are in [holographic RC](holographic_rc.md) and 3D leak guards in the 3D topics.

Statements marked "derived" were computed from the sources' formulas; "inference" marks conclusions drawn here.

## Ringing

Bright rings around small, bright sources in open space, at the distances where one cascade hands off to the next. They show most clearly once colours are handled in linear space ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#35-ringing-article)). fad's original header notes that small point lights ring and that the author found no fix, and most forks keep the comment ([Shadertoys](../sources/2023_rc_shadertoys.md#mtlbzx-fad-the-original-2d-implementation)); SimonDev's video shows a small light ringing and a large light leaking behind a thin wall ([SimonDev](../sources/2024_simondev_exploring_radiance_cascades_video.md#demo-limits-and-artifacts-1300-to-1456)).

**Cause: parallax.** A lower probe blends four upper probes. Each upper interval starts at its own probe, so it sees the source at a slightly different angle, and its occlusion was never tested from the lower ray's point of view. An upper probe can add an unoccluded copy of the source (double counting) or miss part of it (a gap that leaks), so energy is not conserved where a cascade boundary crosses a source. Osborne and Sannikov measured just over 10% error in the worst case, a tiny, very opaque source in vacuum, and a few percent in practical cases ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#ringing-and-the-bilinear-fix)). In the terms of [core theory](core_theory.md#where-the-merge-is-exact-derived), vanilla merging replaces the shift of the extend identity with spatial interpolation, and every fix below is a way of restoring the shift.

What the community established about the mechanism ([merging notes](../sources/2026_merging_and_ringing.md#why-it-works)):

- Ringing comes from mismatches across the ray direction, not gaps along it. Overlapping intervals along the ray, `L[a,+∞](p) ≈ Merge(L[a, b+D](p), L[b,+∞](p − d·D))`, did not remove it.
- Ringing and leaks have the same cause, rays that do not connect across cascades, so a fix that connects them removes both ([merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs)).
- The theory that any "watertight" scheme, one whose paths connect, must conserve fluence and remove ringing has a counterexample: starting the bilinear fix halfway along the interval to save tracing (`MERGE_FIX 2` in 4ctXD8) still rings.
- A second 2D explanation, the `1/r` falloff of 2D light against linear interpolation between probes, is in [core theory](core_theory.md#interpolation-and-band-limits).

The wiki separates two problems that the fixes target: interpolation discontinuities at probe boundaries, which the bilinear fix addresses, and duplicated energy from the offset between levels, which the parallax fix addresses ([wiki](../sources/2026_rc_community_site_and_wiki.md#parallax-fix)). The mechanism above makes them one problem seen from two sides (inference): duplicated energy is what an unconnected path adds, and the discontinuity is where it switches between upper probes.

## The bilinear fix

The reference fix, given formally in Osborne and Sannikov's appendix A and in Sannikov's `Scaling.ls` ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#ringing-and-the-bilinear-fix), [LegitCascades](../sources/2024_sannikov_legitcascades.md#bilinear-fixed-merge)). Vanilla RC traces one ray, interpolates four upper probes, then merges. The fix traces one ray to each of the four upper probes, merges each ray with its own probe, and only then blends the four results with the usual bilinear weights:

1. Find the four upper probes around the lower probe `p` from `p`'s position, not from where its ray ends, and their bilinear weights; clamp indices to the grid.
2. For upper probe `P_j`, march from `p + d·t_start` to `P_j + d·t_end`, where `t_end` is the lower interval's end and so the start of `P_j`'s interval. The ray length is the distance between these points, not the interval length, so a tracer that marches a fixed length from the start gets it wrong, and the marched direction `normalize(P_j + d·t_end − p − d·t_start)` differs slightly from `d`.
3. Merge each march with `P_j`'s stored value for the child direction, weight it, and sum.
4. The top cascade has nothing above it and needs no fix.

Sources for the steps: [merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix), [LegitCascades](../sources/2024_sannikov_legitcascades.md#bilinear-fixed-merge). Implementations: 4ctXD8's default `CastMergedIntervalBilinearFix` ([Shadertoys](../sources/2023_rc_shadertoys.md#4ctxd8-suslik-testbed-of-merge-fixes)); MctXRr's 16 traces per texel, 4 child rays times 4 upper probes, with a discarded plain trace still computed ([Shadertoys](../sources/2023_rc_shadertoys.md#mctxrr-suslik-a-fixed-grid-and-one-trace-per-upper-probe)); GM Shaders' active `BilinearFix` shader, which forks each ray from its coarser parent direction and ends it at `originN1 + delta·(interval + limit)` with 16 raymarches and 16 nearest fetches per texel against the base shader's 4 and 4 ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#bilinear-fix-in-detail-shd_radiancecascades_bilinearfixfsh)); CoreCascade's CPU harness, which traces from `probe + dir·TStart` to `far + dir·TEnd_near` ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#corecascade)); Gigi's and the 2D reference codes ([2D implementations](2d_implementations.md)).

Rules for getting it right ([merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix)):

- Interpolate by hand from direct texel reads. Leaving hardware filtering on is the most common reason a fix shows banding or still leaks.
- With pre-averaged storage the rays of an upper group start at slightly different points, so the four fix rays do not land exactly on them; tracing 16 rays, one to each upper ray start, is very slightly better and not worth 4× the rays.
- Near cascade 0 the four rays can point in nearly opposite directions. This looks wrong in diagrams and causes no visible error, because the bend shrinks as intervals grow.
- With a watertight tracer (sphere tracing or DDA, not fixed steps) it needs no interval overlap ([merging notes](../sources/2026_merging_and_ringing.md#why-it-works)).

**How far the rays bend (derived).** A cell-centred lower probe sits a quarter of an upper cell from its nearest upper probe on each axis and three quarters from the farthest, so the farthest of its `2^D` upper neighbours is `0.75·√D·Δs_{c+1}` away. With contiguous ×4 intervals from 0 and `t0 = Δs0` in 2D, the interval length is `4^c·t0` and the offset `2.12·2^c·Δs0`:

| Cascade | Interval length | Farthest offset | Largest bend | Can the ray reverse? |
|---|---|---|---|---|
| 0 | 1 | 2.12 | 64.8° | yes |
| 1 | 4 | 4.24 | 46.7° | yes |
| 2 | 16 | 8.49 | 27.9° | no |
| 3 | 64 | 17.0 | 14.9° | no |
| 4 | 256 | 33.9 | 7.6° | no |
| 5 | 1024 | 67.9 | 3.8° | no |

The ratio halves per cascade, since spacing doubles and length quadruples. This is the "nearly opposite directions near cascade 0" that the merging notes report as harmless.

**What it removes.** Ringing, and most light leaking through occluders thinner than the probe spacing ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#ringing-and-the-bilinear-fix)). It interpolates continuous paths, never the end points of disconnected intervals, so it has no parallax. It does not remove blocky interpolation patches in dark areas, which come from probe resolution ([core theory](core_theory.md#interpolation-and-band-limits)). DexRT did not need it for its data ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#dexrt-v020-and-the-data-archive)).

### Cost

Stated costs: 4× the traced rays on every cascade except the top ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#ringing-and-the-bilinear-fix), [wiki](../sources/2026_rc_community_site_and_wiki.md#bilinear-fix)); about the cost of vanilla at twice the resolution, and one unoptimized build went from 5 to 11 ms at 1080p ([merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs)); known fixes roughly double the frame time ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#35-ringing-article)); CoreCascade's 800² default traces 19.8 M rays plain and 79.4 M with the fix ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#corecascade)). Rendering at half or a quarter of the resolution with the fix was preferred to vanilla at full resolution ([merging notes](../sources/2026_merging_and_ringing.md#cost-in-3d)).

In 3D the fix costs one ray per interpolation corner: 8× on a rectilinear grid, called a dealbreaker; 4× on a simplex (tetrahedral) grid; and 3× with two-tap diagonal grids ([merging notes](../sources/2026_merging_and_ringing.md#cost-in-3d)).

Total cost by ray count, with the fix's `k` rays per lower ray on every cascade but the top (derived):

| Domain | `k` | Rays per cascade | Total, 5 cascades | Total, 7 cascades |
|---|---|---|---|---|
| 2D grid 2x/4x, or screen and surface probes | 4 | constant | 3.40× | 3.57× |
| 3D grid, ×4 directions, ⅛ probes | 8 (trilinear) | halving | 7.77× | 7.94× |
| 3D simplex grid | 4 | halving | 3.90× | 3.98× |
| 3D two-tap diagonal | 3 | halving | 2.94× | 2.98× |

Ray count overstates the time when ray cost grows with interval length, because the top cascade, which the fix leaves alone, holds the longest rays (derived). If trace time is proportional to rays times interval length, the 2D fix costs 1.75× (the top cascade holds 75% of the time at `l = 4`); with DexRT's measured top share of 63.6% it costs 2.09× ([core theory](core_theory.md#memory-and-cost) for the shares). The reported 5 to 11 ms (2.2×) and "roughly doubling" fit this rather than the 4× ray count (inference). In 3D the length weighting depends on the interval scaling: the trilinear fix costs about 4.4× at `l = 4`, where the top cascade holds about half the time, and about 6.7× at `l = 2`, where every cascade costs the same (derived). Sphere tracing in open space takes fewer steps than its length suggests, so the true figure for a given tracer sits between the two models.

## Straight-ray fixes

These keep the vanilla ray and instead choose, per upper probe, the upper direction that continues it.

**Parallax fix.** Keep the vanilla ray. For each upper probe, take the angle of `ray_end − upper_probe`, convert it to a fractional direction index (`angle·count − 0.5`), interpolate the two nearest upper directions, merge, then blend the four upper probes bilinearly ([merging notes](../sources/2026_merging_and_ringing.md#other-fixes)). 4ctXD8 has outer and inner variants (`CastMergedIntervalParallaxFix` and `CastMergedIntervalInnerParallaxFix`, `MERGE_FIX` 4 and 5), stretching intervals by 1.1 for overlap ([Shadertoys](../sources/2023_rc_shadertoys.md#4ctxd8-suslik-testbed-of-merge-fixes)); Osborne's figure 8 is its formal form ([wiki](../sources/2026_rc_community_site_and_wiki.md#parallax-fix)). It costs about 20% over vanilla, is not watertight, needs interval overlap, and is weakened noticeably by pre-averaging, because averaged upper texels no longer hold separate directions; the inner variant needs a continuous alpha ([merging notes](../sources/2026_merging_and_ringing.md#parameters-that-look-like-merge-bugs)). mxcop's XcfyDj diagram, listed on the site as "Parallel fix", draws the reprojected direction `normalize(E − U)` from the nearest upper probe `U` to the lower ray's end `E`; its bilinear and reprojection switches are copied into variables nothing reads, and the author says the diagram may be wrong ([Shadertoys](../sources/2023_rc_shadertoys.md#xcfydj-mxcop-reprojection-diagram)).

**Circle-intersection (chronicl) fix.** Keep the ray straight and end it where it crosses the circle of radius `t_end` around each upper probe, the circle where that probe's interval begins; then read the upper probe's two nearest directions toward the exit point ([LegitCascades](../sources/2024_sannikov_legitcascades.md#chroniclfixls-the-chronicl-fix)). Mytino's MfXyRj solves `|S + t·dir − C| = t_end` with `S = P + dir·t_start`, `(a, b) = S − C`, `(u, v) = dir`, `D = t_end²·(u² + v²) − (a·v − b·u)²`, and takes the far root `t₊ = (−(a·u + b·v) + √D)/(u² + v²)` ([Shadertoys](../sources/2023_rc_shadertoys.md#mfxyrj-mytino-the-circle-projection-fix)). It was about 3× faster than the bilinear fix in early optimized tests (the unoptimized version about the same speed), with a small checkerboard on cascades 0 and 1, which keep a vanilla or bilinear merge ([merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs), [LegitCascades](../sources/2024_sannikov_legitcascades.md#chroniclfixls-the-chronicl-fix)). chronicl's patch adds "fix checkerboard" (the bilinear fix on cascades 0 and 1) and "force bilinear fix" switches; lcfcR2's variant 0 moves the circle into a helper whose clamp compares distances in one frame and returns −1 for a negative discriminant, a zero-length segment that `normalize` cannot handle ([Shadertoys](../sources/2023_rc_shadertoys.md#lcfcr2-mxcop-four-merges-in-one-playground)).

**When the circle fix is defined (derived).** `D ≥ 0` for every direction exactly when `t_end` is at least the distance from the lower probe to the upper probe, so the fix needs `t_end(c) ≥ 0.75·√D·Δs_{c+1}`, which is `2.12·Δs_c` in 2D and `2.60·Δs_c` in 3D, for the farthest of the bracketing upper probes. Every code that uses it fails this on its lowest cascades:

| Setup | Fails on |
|---|---|
| LegitCascades ChroniclFix defaults (1920 px, 128 probes, `c0_dist` 3 px): `t_end` 9, 45, 189 px against 31.8, 63.6, 127 px | cascades 0 and 1 |
| Contiguous ×4 from 0 with `t0 = Δs0`, 2D | cascade 0 |
| The same in 3D | cascades 0 and 1 |
| Split RC-style `t_n = 1.6·Δs0·4^n`, 2D or 3D | cascade 0 |
| XcfyDj (`t_end` 0.5 spacings against a nearest upper probe 0.707 spacings away) | cascade 0, two of four directions of every probe |
| MfXyRj (`t_end` 0.006 W against 0.0041 W), square view | none; taller views fail |

With `l = 4` the required `t0/Δs0` halves per cascade: 2.12, 1.06, 0.53 in 2D and 2.60, 1.30, 0.65 in 3D. The LegitCascades note found the same failing cascades with a looser bound of `√2` upper spacings and proposed that rays starting outside the circle cause the checkerboard; the source notes for MfXyRj and XcfyDj found the same undefined square root independently ([LegitCascades](../sources/2024_sannikov_legitcascades.md#chroniclfixls-the-chronicl-fix), [Shadertoys](../sources/2023_rc_shadertoys.md#mfxyrj-mytino-the-circle-projection-fix)). The checkerboard appearing exactly where the condition fails supports that explanation; it remains untested (inference). In 3D, a sphere-intersection fix would need the bilinear (trilinear) fix or a vanilla merge on cascade 0 at any usual `t0`.

## Cheaper fixes

Costs are relative to vanilla RC in 2D unless stated ([merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs) unless another source is linked).

| Fix | How it works | Cost and result |
|---|---|---|
| Nearest fix with forking | each group of four rays shares a start and runs to the start of the nearest upper probe's rays (GM Shaders `NearestFix`, upper probe `floor(probe/2)`) | no more rays than vanilla, about a quarter of the bilinear fix; removes ringing and leaks; 2×2 blocks of lower probes share an upper probe, so penumbras are blocky and the blocks grow with distance. Without forking, nearest merging leaves halos |
| Nearest-interlaced | one of the four upper probes per lower probe, so that no upper probe is nearest to two lower probes in a 2×2 block; GM Shaders picks by `mod(2·px + py, 4)` and ships a "blurrier" order with a "sharper" one commented out | free, plus a quarter of the merge reads; smooth field with a dithered look; neighbours disagree, so penumbras jitter. GM Shaders' README says it reduces ringing and occlusion errors |
| Stochastic bilinear fix | trace to one random upper probe per sample | 1× rays; film-grain noise, acceptable mainly for pixel art |
| Hashed pick | lcfcR2's active mode: a hash of the lower probe index picks one upper probe with equal odds, ignoring time and direction | a fixed white-noise pattern: every direction and every cascade's probe with the same index picks the same upper probe (derived, [Shadertoys](../sources/2023_rc_shadertoys.md#lcfcr2-mxcop-four-merges-in-one-playground)) |
| Temporal bilinear fix | trace one of the four fix rays per frame | 1× rays per frame, four frames to converge |
| Two-tap diagonal | offset the grids so each lower probe sits on a diagonal between two upper probes, then interpolate those two | fix rays drop from 4× to 2× in 2D and from 8× to 3× in 3D; one build cut frame cost by 33%; worse in motion, with JPEG-like artifacts; a parallax fix on top cancels most of the gain |
| Connection points | each 2×2 block of lower probes shares one point at its centre plus half the interval, and each upper probe has four; rays are joined there | watertight at the cost of vanilla; removed halos but made resolution change unevenly along penumbras; worked for participating media ([merging notes](../sources/2026_merging_and_ringing.md#other-fixes)) |
| Midpoint fix | MfXyRj's `MERGE_FIX 2`: a shared leg to a midpoint at `t_end` minus 1.5 upper spacings, then one leg to each upper probe | 1 + 4 traces per ray; the halfway-start variant still rings ([Shadertoys](../sources/2023_rc_shadertoys.md#mfxyrj-mytino-the-circle-projection-fix)) |
| Mask (Dolkar) fix | trace past the interval end, then mask each upper probe by whether its own interval would also see the hit | 1 ray; described as unreliable; details below |
| Gear-tooth intervals | alternate interval starts and ends by direction parity so each boundary overlaps slightly and steps in and out | about free; halves ringing and moves the problem edge; angle-based offsets give star shapes; details below |
| Cross-faded interval ends | mlSfRD: fade hits near each boundary between the two cascades | free; removes halos; details below |
| Interior mask | rays that start inside a solid return black on every cascade but 0 ([gist](https://gist.github.com/RandyGaul/7a2b53eced08dcec4e08f591dad7724c)) | free; ringing becomes hard to see above 1080p when solids are larger than the cascade 0 interval; darker at 512², and shadow ringing stays |
| Interval overlap | extend each interval by about `√2` upper spacings | free; fixes leaks, not ringing; large overlaps give halos and count partial absorbers twice ([layout](cascade_layout_and_merging.md#overlap)) |
| Wider merge filter | blur 5 taps while upsampling during the merge | no extra rays; smooths vanilla penumbra aliasing, since vanilla merging uses only about half the cones; does not help the bilinear fix |
| Angular five-tap merge | ZY4N's Unity build: lower direction `k` reads upper directions `4k − 2 … 4k + 2` with weights 0.5, 1, 1, 1, 0.5 (÷4) | a light angular blur that softens ringing at a little sharpness ([Unity 2D](../sources/2024_unity_2d_rc_repositories.md#zy4n)) |
| Fixed blur weights | kornelski's Bevy port weights the lower neighbour 1/3 or 2/3 by parity where the geometric weights are 1/8 and 5/8 | a deliberate blur toward one neighbour, not an interpolation (derived, [Bevy](../sources/2024_bevy_2d_rc_repositories.md#kornelskibevy_flatland_radiance_cascades)) |
| Bilinear fix as a 2×2 post pass | trace vanilla, then interpolate 2×2 probe blocks afterwards | an idea; nobody found a watertight way to do it ([merging notes](../sources/2026_merging_and_ringing.md#other-fixes)) |
| Staggered interval sets | two sets of overlapping intervals whose seams fall in different places, each point reading the set that is reliable there | an idea; choosing is easy with hit distance and unsolved for media ([merging notes](../sources/2026_merging_and_ringing.md#other-fixes)) |
| Cascade −1 | a per-pixel interval in front of cascade 0 | no ringing added; see [layout](cascade_layout_and_merging.md#cascade-1-and-contact-detail) |

Sources for GM Shaders' rows: [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#shader-variants-optimized-folder), [wiki](../sources/2026_rc_community_site_and_wiki.md#nearest-fix). Odd branching, simplex and hexagonal grids, bicubic merging and adaptive ray skipping are merge-kernel choices in [cascade layout and merging](cascade_layout_and_merging.md#merge-kernels).

**Forking.** Start every group of child rays at one shared point, the parent's end, drawn from the parent's centre direction ([Shadertoys](../sources/2023_rc_shadertoys.md#4clcwn-mytino-diagram-of-the-fixes)). Paths become fully continuous, removing the last bit of leaking, but angular resolution drops; people saw no measurable gain alone and sometimes worse aliasing, so it is usually left off ([merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix)). With the bilinear fix it worked for walls at least 4 px thick without mipmaps, and doubling cascade 0 directions compensates for the lost resolution ([merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs)). GM Shaders uses forking in place of its interval overlap term ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#shader-variants-optimized-folder)).

**The mask fix in its three forms.**

- 4ctXD8's `MERGE_FIX = 3`, `CastMergedIntervalMaskFix`, masks upper probes by hit distance, fading between the masks of two cascades where they overlap ([Shadertoys](../sources/2023_rc_shadertoys.md#4ctxd8-suslik-testbed-of-merge-fixes), [merging notes](../sources/2026_merging_and_ringing.md#other-fixes)).
- MfXyRj traces one ray to `t_end` plus three upper spacings and forms four masks from the hit distance against each upper probe's interval start projected on the ray, blended bilinearly with a formula from a Desmos graph; in this mode a ray starting inside a shape returns `(0, 0, 0, 0)`, because the variant works better when misses terminate ([Shadertoys](../sources/2023_rc_shadertoys.md#mfxyrj-mytino-the-circle-projection-fix)).
- clVcD3's `RINGING_FIX` marches past the interval end to `tMax + 2^(n+1)` px; for a hit beyond `tMax − 2^(n+1)` it projects the hit from each of the four upper probes, counts a probe as covering it when that distance reaches `tMax`, mixes the four coverage bits bilinearly, and when the mix is below 1 scales the colour by it and sets alpha to 1. This removes the share of the hit that the upper cascade will also see. Its bilinear bracket uses `floor(pf)` and `pf − q` without the probe-centre offset while the merge uses `round(pf) − 1` and `w − 0.5`, so mask and merge disagree on probes and weights ([Shadertoys](../sources/2023_rc_shadertoys.md#clvcd3-quinchilion-a-ringing-mask)).

**Gear teeth.** kornelski's XffcD7 multiplies `tMin` by `1 + teeth` when `(j >> 2) & 1` is 0 and by `1 − teeth·overlap` otherwise, and `tMax` by `1 + teeth·overlap` when `j` is even and by `1 − teeth` otherwise; with `teeth = 0.1` and `overlap = 1.15` the start factors are 1.1 and 0.885 and the end factors 1.115 and 0.9. A parent and its four children share parity, so every boundary overlaps by `0.015·4^(n−1)·t1`, `teeth·(overlap − 1)` of the base, while it steps in and out from one direction to the next. The comment says 1.1 works well, but the value is 0.1, and at 1.1 the factor `1 − teeth` would be negative ([Shadertoys](../sources/2023_rc_shadertoys.md#xffcd7-kornelski-gear-shaped-intervals)). kornelski's later Bevy port staggers interval ends by about ±10% and its README calls the seam workaround a "gear fix" without defining it, so the port most likely carries the same teeth (inference, [Bevy](../sources/2024_bevy_2d_rc_repositories.md#kornelskibevy_flatland_radiance_cascades)).

**Cross-faded ends.** Suslik's mlSfRD ("I just fixed haloes") traces cascade `n` from `max(0, start − s_n/2)` to `end + s_(n+1)/2` with `s_n = 10·2^n` px, and blends a hit toward empty `(0, 0, 0, 1)` with a weight rising linearly from 0 at `start − s_n/2` to 1 at `start + s_n/2` and falling back to 0 between `end − s_(n+1)/2` and `end + s_(n+1)/2`. Cascade `n`'s end ramp and cascade `n + 1`'s start ramp share their centre and width, so their weights sum to 1 and a boundary hit is split between the two cascades; blending alpha with colour lets the upper cascade through by the same share (derived). The ramps around 7, 28 and 112 px span `[−3, 17]`, `[8, 48]` and `[72, 152]` px, the first wider than cascade 0's whole interval, and cascade 0's start ramp still applies, so a contact hit at the probe keeps weight 0.5 and reaches full weight only at 5 px (derived, [Shadertoys](../sources/2023_rc_shadertoys.md#mlsfrd-suslik-smooth-interval-edges)).

### Fixes compared

| Fix | Rays (2D) | Removes ringing | Removes leaks | Side effect |
|---|---|---|---|---|
| Vanilla | 1× | no | no | the reference artifacts |
| Bilinear fix | 4× (about 2× in time) | yes | most | bent rays near cascade 0 |
| Circle-intersection | as bilinear, about 3× faster optimized | yes above cascade 1 | not reported | undefined on low cascades (derived) |
| Parallax fix | 1×, +20% | partly, not watertight | with overlap | weakened by pre-averaging |
| Nearest with forking | 1× | yes | yes | blocky penumbras |
| Nearest-interlaced | 1× | partly | partly | dithered, jittering penumbras |
| Two-tap diagonal | 2× | not reported | not reported | motion artifacts |
| Connection points | 1× | halos removed | watertight | uneven penumbra resolution |
| Gear teeth | 1× | halves it | no | moved edges, stars if angle-based |
| Cross-fade | 1× | halos | no | half-weight contact hits |
| Mask fix | 1× | partly | no | unreliable |
| Interior mask | 1× | hides it at high resolution | no | darker at low resolution |
| Overlap | 1× | no | yes | halos when large |

Assembled from the sections above; "not reported" marks what no source measured. Read together (inference), the bilinear fix is the reference, the nearest fix with forking is the cheapest fix reported to remove both artifacts, and the rest trade one artifact for another.

## Gaps and seams between cascades

- **Intervals that do not meet.** A cascade 0 interval that is short against the probe spacing, or interval series that leave gaps, let thin occluders fall between segments of neighbouring cascades. The parameter rules (cascade 0 interval at least the cell diagonal, intervals from one geometric series) are in [core theory](core_theory.md#choosing-cascade-0-derived-and-reported) and [cascade layout](cascade_layout_and_merging.md#intervals).
- **Flicker under motion** comes from low probe density, short intervals, or rays that start at the probe centre instead of the interval start; adding noise hides it, more cascade 0 rays or probes fix it ([merging notes](../sources/2026_merging_and_ringing.md#parameters-that-look-like-merge-bugs)). A 5 px light flickered with 16 directions and a 10 px interval, the light-size rule of [core theory](core_theory.md#choosing-cascade-0-derived-and-reported).
- **Overlap, gear teeth and cross-fades** are the three ways to soften a seam, above and in [layout](cascade_layout_and_merging.md#overlap).
- **Contact detail** finer than the cascade 0 grid needs cascade −1 ([layout](cascade_layout_and_merging.md#cascade-1-and-contact-detail)).
- **Shadow offset.** jason.today's early two-pass demo shifted shadows in proportion to the upper interval's offset; a shorter split made them look reasonable and the cause was not otherwise resolved ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#7-artifacts-and-fixes-as-stated-or-shown)).

## Grid and blocky penumbras

- Merging with only the nearest upper probe shows the probe grid; bilinear blending of four upper probes, or the direction-first hardware fetch, fixes it ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#artifacts-and-fixes)). In jason.today the grid appeared until the render targets used linear filtering, an upscale it calls nearly free ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#7-artifacts-and-fixes-as-stated-or-shown)).
- A wider 3×3 distance-weighted merge kernel (weight `1/(1 + |d − f|)`) removed the blocks at shadow edges but averaged across walls and leaked more light; it raised the merge from 0.41 to 0.63 ms (+54%) at 1024², and the author suggests depth weights or rejecting probes behind edges ([Peter](../sources/2026_peter_rc_2d_bachelor_thesis.md#merge-kernel)).
- Blocky patches in dark areas survive every merge fix ([core theory](core_theory.md#interpolation-and-band-limits)).

The two results bound a design choice (inference): a wider kernel trades blocks for leaks, so it needs the same occlusion test a bilinear fix provides, at which point the bilinear fix is the cheaper path to both.

## Light leaks

In 2D:

- **Merge reads across tiles.** A hardware-filtered fetch near a direction tile's edge blends in a neighbouring direction; clamp the coordinate at least half a texel inside the tile, a full texel in jason.today's final code, which fixed a leak along edges with the interval split at 0 ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#34-light-leak-clamp-article), [layout](cascade_layout_and_merging.md#merge-kernels)).
- **Spacing too coarse for the occluders.** Walls thinner than cascade 0's spacing let light through because the penumbra condition is violated; the bilinear fix helps, otherwise make the base grid finer ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#ringing-and-the-bilinear-fix)).

In the traced structure and in 3D, where each topic owns the details:

- **Thin walls in a distance field** may never cross zero between samples; Lumen expands surfaces by half a voxel's diagonal at trace time, starting GI rays with no expansion and growing it with distance ([Lumen](../sources/2022_wright_lumen_siggraph_advances.md#distance-fields), [scene representation](scene_representation_and_tracing.md)).
- **Averaged volume mips** halve a thin wall's opacity at each level, since it fills about 4 of 8 sub-voxels; six-direction opacity per voxel fixes it ([volumetric notes](../sources/2026_volumetric_rc.md#marching-on-mips), [volumetric RC](volumetric_and_radiative_transfer.md)).
- **Coarse scene cascades.** Godot's HDDAGI leaked at the default 0.2 cell size because rays reached the third voxel cascade within a short distance; 0.03 with 5 cascades, or the cascades pushed 0.3 forward of the camera, removed it ([HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md#occlusion-and-leaks), [Godot integration](godot_integration.md)).
- **Filtered reads at a ray's far end** reach through walls; daGI2 pulls the read back along the ray by half a grid probe for screen probes and √3 coarser probe sizes for its grid ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md#radiance-grid), [related engine GI](related_engine_gi.md)).
- **Sparse trilinear interpolation** with an upper probe behind a 2 to 3 voxel wall leaks; interpolating with a parent neighbour only when the nearest child rays in that direction were unoccluded, one hit bit per ray, removed it at about 50% more merge time ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#interpolation-and-leaks), [3D world space](3d_world_space.md#leak-defences-in-world-space)).
- **Probes inside or behind walls** interpolate light from the other side; world-space designs add visibility weights, relocation, normal offsets or hit masks, and screen-space designs depth-aware weights ([3D world space](3d_world_space.md#leak-defences-in-world-space), [3D screen space](3d_screen_space.md), [related probe GI](related_probe_gi.md)).

## Domain edges

- Lookups past the outermost probe row clamp, which flattens falloff near the border, and reads outside the texture must return zero or light wraps to the opposite edge ([layout](cascade_layout_and_merging.md#probe-placement)).
- Screens get dark edges when the top interval does not reach the diagonal: add a cascade or extend the top interval to the domain edge. jason.today added one cascade for a top-left light at 300×400 ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#7-artifacts-and-fixes-as-stated-or-shown)); agrdino's Unity README lists ringing and dark screen edges as unsolved ([Unity 2D](../sources/2024_unity_2d_rc_repositories.md#agrdino)).
- Edge darkening also comes from code that skips the merge or miscounts at the border: CptNemo0's out-of-bounds rays skip the upper merge; AliMoghimii's Vulkan build darkened grid borders through an uninitialized transmittance accumulator for missing parents; tlegoc counts skipped edge taps toward its divisor of 4; tf2XRc extrapolates border cells with negative weights and reads zero alpha; 3cKczD's pixels outside its work area read as opaque black, leaving 8 black rows at 1080 px ([repository survey](../sources/2026_rc_repository_survey.md#bugs-that-recur), [assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#bugs-worth-recognizing), [Shadertoys](../sources/2023_rc_shadertoys.md#tf2xrc-sjarod-every-cascade-merged-per-pixel)).

## Sky aliasing

Point-sampling a small sun in the top cascade's coarse bins gives banding and stepped shadows; integrating the sky over each bin removes it ([core theory](core_theory.md#sky-and-environment)). Two bugs recur in the integral: Hybrid46 and the futureengine2 gist integrate from the ray's centre angle one bin forward, so every bin sits half a bin off its ray, and lcfcR2's sky sums four bin averages without dividing by 4 ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#bugs-worth-recognizing), [Shadertoys](../sources/2023_rc_shadertoys.md#lcfcr2-mxcop-four-merges-in-one-playground)).

## Banding and precision

- Very dark scenes banded in 8-bit output in one 2D game; Valve's animated dithering fixed it with the least change in perceived brightness ([discussions](../sources/2026_rc_discussions.md#implementer-notes)).
- 8-bit cascades clip the sun and bright emitters (futureengine2, Hybrid46), and 8-bit jump-flood fields fail ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#bugs-worth-recognizing), [layout formats](cascade_layout_and_merging.md#formats)).
- GPUs truncate when writing R11G11B10F and RGB9E5, so repeated blending drifts the image yellow (blue for RGB9E5); daGI2 rounds each channel before writing and stores its screen GI as squared colour in half floats ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md#lessons-for-rc-in-godot)). HRC builds found R11G11B10F unable to reach full white and 11-bit opacity topping out at 0.996 ([HRC notes](../sources/2026_holographic_rc.md#artifacts-and-fixes)). A single-frame pipeline re-stores merged values once per cascade rather than once per frame, so drift has `N` writes to accumulate over instead of hundreds, but truncation still biases each write (inference).

## Sharp shadows and small lights

RC blurs shadows from small, distant lights because the cascade that sees the occluder has coarse spacing, and its minimum penumbra angle is by design ([core theory](core_theory.md#the-penumbra-condition)); more cascade 0 resolution helps only near the occluder. Lights smaller than the ray-end gap alias and flicker ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)), and at usual settings the sun disc is resolved only from cascade 7 to 9, so 4 to 5 cascades never give sun shadows ([core theory](core_theory.md#which-distance-occluder-and-light-separated)). Coppen lists poor sharp shadows with no fix ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#artifacts-and-fixes)). HRC fixes this in 2D by keeping full probe resolution across the travel direction, at `O(N⁴)` memory in 3D, and still aliases lights smaller than about 8 base probes ([holographic RC](holographic_rc.md)). A square light looks darker along the axes than along the diagonals because it covers a smaller angle there, which is not a bug ([merging notes](../sources/2026_merging_and_ringing.md#debugging-routine)).

## Rays starting inside geometry

Codes disagree on what a ray whose interval starts inside a solid returns:

| Rule | Codes |
|---|---|
| that solid's emission, at once | fad's mtlBzX and its forks; MfXyRj's modes 0 to 2 |
| nothing, for cascades above 0 | GM Shaders' base shader (its "volume-start check"), the interior mask gist |
| nothing, in every cascade | MfXyRj's mask mode, since misses must terminate |
| must not exit through the far side | genos-engine, after a bug painted lit faces onto back faces |

Sources: [Shadertoys](../sources/2023_rc_shadertoys.md#mtlbzx-fad-the-original-2d-implementation), [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#shader-variants-optimized-folder), [merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs), [engine design documents](../sources/2026_engine_rc_design_documents.md#genos-engine). Returning the emission counts a thick emitter once per cascade whose interval starts inside it (inference); returning black is the interior mask, which hides ringing at high resolution and darkens the image at 512². genos-engine also skips probes inside walls at shading, since they store no light.

## Base ray counts other than 4

jason.today saw much worse artifacts at base 16 and suspected "a bug somewhere"; its interval multiplier and the community demo's `modifierHack` ("hand-wavy") came from that ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#91-limitations-stated-by-the-author), [layout](cascade_layout_and_merging.md#intervals)). In that scheme base `B` multiplies directions and interval lengths by `B` and spacing by `√B` per cascade ([layout](cascade_layout_and_merging.md#intervals)), so in the terms of [core theory](core_theory.md#cascade-scaling) the angular ratio stays constant while the spatial ratio falls by `√B/B` per cascade: ×0.5 at base 4 and ×0.25 at base 16 (derived). No source tested whether that imbalance, or a bug, causes the artifacts.

## Latency and flicker over frames

Merging against last frame's upper cascade (Shadertoy, LegitScript, temporal surface RC) delays a change by one frame per cascade and can flicker ([layout](cascade_layout_and_merging.md#tracing-and-merging-order)). Updating each cascade at its own rate, as CptNemo0's thesis code does, or one per frame in Brixelizer's 0 1 0 2 0 1 0 3 order, trades latency in the far cascades for cost ([repository survey](../sources/2026_rc_repository_survey.md), [Brixelizer](../sources/2024_amd_brixelizer_gi.md#building)). In 3D nearly every design accumulates over frames, so history rejection and hysteresis matter there ([3D world space](3d_world_space.md#temporal-reuse-in-world-space), [3D screen space](3d_screen_space.md)).

## Recurring implementation bugs

Bugs found by reading the codes fall into a few classes (assembled from the sources linked):

| Class | Examples |
|---|---|
| Intervals that do not tile | lantrol's level 1 ends at 4 while level 2 starts at 5; nff747's comments disagree with its code; lcfcR2's optional scaling leaves cascade 0 zero-length and a gap between cascades 1 and 2; start and length from different series ([repository survey](../sources/2026_rc_repository_survey.md#bugs-that-recur), [Shadertoys](../sources/2023_rc_shadertoys.md#lcfcr2-mxcop-four-merges-in-one-playground), [merging notes](../sources/2026_merging_and_ringing.md#parameters-that-look-like-merge-bugs)) |
| Wrong bilinear weights | tlegoc's three of four corners; w3XSz4's −0.25 and 1.25 on the wrong parents while a correct helper goes unused; Coppen's figure; ZY4N's integer `−1/2` rounding to 0, giving weight −0.25 in the first column ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#bugs-worth-recognizing), [Shadertoys](../sources/2023_rc_shadertoys.md#w3xsz4-neylick-branching-factor-2-in-a-cube-map), [Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#merging-spatially), [Unity 2D](../sources/2024_unity_2d_rc_repositories.md#zy4n)) |
| Wrong normalization | w3XSz4 divides two child terms by 4; nixonyh's mip divides by `2w` instead of `w²`; CoreCascade's merged visibility `(1 + Σv)/4`, 1.25 in empty space ([Bevy](../sources/2024_bevy_2d_rc_repositories.md#nixonyhbevy_radiance_cascades), [assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#corecascade)) |
| Transmittance mishandled | w3XSz4's hits return alpha 1, so surfaces never block; Hybrid46 keeps transmittance 1 on emitter hits; tlegoc's `output += final·output.a` changes alpha; inverted hit conventions within GM Shaders ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#bugs-worth-recognizing), [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#inconsistencies-in-the-repository)) |
| Merges or levels missing | Yaocenji's last merge step; nff747's "bilinear" merge reading one texel; CoreCascade and w3XSz4 tracing toward cascades that were never computed or have zero probes; jason.today's extra top pass that is never merged ([repository survey](../sources/2026_rc_repository_survey.md#bugs-that-recur), [jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#92-differences-between-article-text-and-final-code)) |
| Index arithmetic | `index − 1` at 0 wrapping into the previous block under a signed `%` (tlegoc, SimonDev); float ray indices inexact above 2^24 (CptNemo0, cascade 12 on); missing `+0.5` texel centres (Peixoto; HRC dispatch IDs); float rounding in probe indices ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#bugs-worth-recognizing), [Peixoto](../sources/2024_peixoto_opengine_2d_rc.md#issues-read-from-the-code), [HRC notes](../sources/2026_holographic_rc.md#debugging)) |
| Non-square views | MctXRr's non-square cells; Peixoto's lengths in `max(W, H)` units against positions in `(W, H)`; tmpvar's `screenDims` built from the width twice; MfXyRj's and lcfcR2's x-only spacing; tf2XRc's UV directions ([Shadertoys](../sources/2023_rc_shadertoys.md#mctxrr-suslik-a-fixed-grid-and-one-trace-per-upper-probe), [tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md#issues-and-notes)) |
| Unguarded geometry | circle fixes taking the root of a negative discriminant; MfXyRj's `intersect()` dropping the clip offset; hit tests with no minimum `t` ([Shadertoys](../sources/2023_rc_shadertoys.md#mfxyrj-mytino-the-circle-projection-fix)) |
| Resource hazards | one texture bound as storage output and sampled input, invalid in wgpu; an atlas read and written in place (Peter) ([discussions](../sources/2026_rc_discussions.md#implementer-notes), [Peter](../sources/2026_peter_rc_2d_bachelor_thesis.md#limits)) |

The first five classes break energy in ways that look like ringing, leaks or dark borders, so the test scenes below catch them before any fix is judged (inference).

## Debugging routine

From the merging notes ([merging notes](../sources/2026_merging_and_ringing.md#debugging-routine)), with additions from the screen-space and HRC notes:

- **White furnace test.** Draw a closed hollow emitter with a known colour such as `(1.0, 0.5, 0.0)`; outside, radiance should approach half the emitted value and inside match it. A hue shift or a dark result means wrong sRGB handling; a wrong inside means a missing top cascade or intervals that are too short. The expected values are derived in [core theory](core_theory.md#radiometry-in-flatland).
- **One level at a time.** Render one cascade alone merged down (only cascade 4, say), or cascade 1 alone without merging in 3D ([screen-space RC](../sources/2026_screen_space_rc.md#other-findings)).
- **Make rays visible.** Stretch the cascade 0 interval 50×, or push ray lengths 10× to reproduce the merge diagram; use constant interval lengths to see cascades as shells around a light; visualize every interval contributing to the pixel under the mouse ([HRC notes](../sources/2026_holographic_rc.md#debugging)).
- **Check the reads.** Return zero outside the texture; breaks along the cardinal directions mean the merge reads the wrong probes; compare manual interpolation on plain texels with hardware filtering; sampling at the origin should give 0.25 to each upper probe in every cascade; use integer index math.
- **Separate the tracer from RC.** Replace the tracer with a per-pixel stepper that stops on a hit (step `d/max(|dx|, |dy|)`, length in whole pixels); jump-flood fields can return zero just outside a surface, and a step cap shorter than the interval ends rays early. In 3D, return radiance 1 on a miss and 0 on a hit, times 0.5, so flat surfaces integrate to 1.0 ([screen-space RC](../sources/2026_screen_space_rc.md#other-findings)).
- **Keep scenes trivial.** One emitter and one occluder, thin walls, hollow boxes; one emissive cube on a floor in 3D; point-source falloff against a path tracer, and a moving source should show no preferred direction ([HRC notes](../sources/2026_holographic_rc.md#debugging)).
- **Scale exposes some bugs.** Small screen-space downscale factors (2×, 4×) hide min/max bugs that show at 64× and above ([screen-space RC](../sources/2026_screen_space_rc.md#other-findings)).

## Connections

- **The bilinear fix has binary and stochastic forms in 3D.** Hit bits, erhe's visibility rays, parent hit-distance tests and Reservoir Cascades' validated parents all test whether a child can see a parent's interval start, the question the 2D fix answers with extra rays ([3D world space](3d_world_space.md#connections), [sampling and guiding](rc_for_sampling_and_guiding.md#connections)).
- **Pull-back is the cheapest leak defence on record.** daGI2 and Lumen read the far level from a point stepped back along the ray, which RC's merge could do at each interval end ([engine GI](related_engine_gi.md#connections)).
- **Small emitters are a probe-gather limit everywhere.** Lumen's emissive noise limit, kajiya's advice to make them lights and RC's cascade 0 limit are one problem, and 3D RC codes answer it by lighting small emitters analytically ([engine GI](related_engine_gi.md#connections), [3D world space](3d_world_space.md#connections)).
- **Ringing has an astrophysics name.** Piskunov's "light defocusing" in short-characteristics solvers is the angular blur that ringing and the parallax fixes deal with ([alternatives](light_transport_alternatives.md#connections)).
- **X patterns share one cause.** Missing cone weights, equal-length rays and extensions from cascade 0 all treat rays of different angular width or length as equal ([holographic RC](holographic_rc.md#connections)).
- **Thin-wall leaks from mips are Jensen's inequality.** Averaged occupancy brightens through walls for the same reason mip brightness drifts ([volumetric](volumetric_and_radiative_transfer.md#connections)).
- **Flicker follows moving samples.** Gautron's analysis of rebuilt irradiance caches, where the error pattern moves with the records, explains why screen-anchored probes flicker and world-locked ones do not ([radiance caches](related_radiance_caches.md#single-frame-assessment)) (inference).

## Single-frame assessment

For single-frame 3D RC (inference, from the sections above):

- None of the merge artifacts is noise. Ringing, leaks, blocky penumbras and small-light aliasing are deterministic and repeat every frame, so temporal accumulation would not remove them without jitter; they must be fixed in the merge or accepted. The stochastic and temporal bilinear fixes depend on accumulation and are out.
- The full trilinear fix costs about 4.4× in time at `l = 4` on a 3D grid (7.8× by rays). Cheaper routes with evidence behind them: a simplex grid (4 corners, about 3.9× by rays), two-tap diagonal grids (3×, with motion artifacts), the nearest fix with forking (1×, blocky), and cascade −1, which removes ringing at the lowest level where the circle-type fixes are undefined.
- Straight-ray fixes need `t_end ≥ 2.6·Δs_c` in 3D, so at usual `t0` they cannot serve cascade 0, and a hybrid (cascade −1 or a trilinear fix low, straight-ray fixes above) matches what the 2D codes converged on.
- Single-frame scheduling removes the frame-lag artifacts outright and cuts the number of lossy writes per frame to one per cascade.
- Leaks in 3D come mostly from the scene representation and probe placement, not the merge, and are owned by those topics.

## Open questions

- How large is vanilla merging's error in 3D, measured against a reference? The 10% worst case is a 2D figure.
- Does the length-weighted cost model hold for the tracers available in compute shaders (sphere tracing a distance field, voxel DDA), or does the fix cost track ray count?
- Is the circle-fix checkerboard on cascades 0 and 1 caused by rays starting outside the circle? A guarded intersection would test it directly.
- Can a nearest fix with forking in 3D avoid visibly blocky penumbras if cascade 0 is dense or replaced by cascade −1?
- Does a simplex (tetrahedral) probe grid keep its 4× fix cost advantage once its merge indexing and direction interpolation are written out?
- Which fix, if any, stays watertight with participating media, where hit distances are not defined? Connection points worked for media in 2D.
