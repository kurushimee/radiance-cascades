# Holographic RC

Holographic radiance cascades (HRC) is a 2D variant of RC by Rouli Freeman (Oxford), Alexander Sannikov and Adrian Margel (arXiv 2505.02041, 2025-05). It keeps full probe resolution across each ray's direction of travel and coarsens only along it, and it builds long rays by merging short ones instead of tracing them, so its cost does not depend on the scene ([HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md)). This file covers the method, what implementers learned after the paper, its artifacts, cost, 3D prospects and variants; every HRC code is described in [holographic RC implementations](holographic_rc_implementations.md). The penumbra error HRC removes is stated in [core theory](core_theory.md#which-distance-occluder-and-light-separated), the merge operator it relies on in [core theory](core_theory.md#the-merge-operator), and HRC's place in the shift-and-extend view in [core theory](core_theory.md#where-the-merge-is-exact-derived).

Statements marked "derived" were computed with a script from the sources' formulas; "inference" marks conclusions drawn here; "read from the code" marks behaviour found by reading, not by running. Community findings come from the [HRC notes](../sources/2026_holographic_rc.md) and are unverified unless a public link backs them.

## Contents

- [What it fixes](#what-it-fixes)
- [Geometry](#geometry)
- [Merging down](#merging-down)
- [Building rays: the acceleration structure](#building-rays-the-acceleration-structure)
- [Final gather and cleanup](#final-gather-and-cleanup)
- [Measured results and the cost model](#measured-results-and-the-cost-model)
- [Where it works](#where-it-works)
- [Artifacts and fixes](#artifacts-and-fixes)
- [Performance](#performance)
- [3D](#3d)
- [Off-screen light](#off-screen-light)
- [Variants](#variants)
  - [Half HRC](#half-hrc)
  - [Equal-angle, ring, radial and axis-aligned HRC](#equal-angle-ring-radial-and-axis-aligned-hrc)
  - [Plane cascades](#plane-cascades)
  - [Block cascades](#block-cascades)
  - [Polygonal cascades](#polygonal-cascades)
  - [Gradient RC](#gradient-rc)
  - [Line space](#line-space)
  - [Background: light fields and line space](#background-light-fields-and-line-space)
  - [Other uses](#other-uses)
- [Debugging](#debugging)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)

## What it fixes

Plain RC blurs the penumbra of a small, distant light behind an occluder halfway to it, because the cascade that sees the occluder has coarse probe spacing; in the paper's test, plain RC tuned to equal time had twice HRC's RMSE, all of it in penumbras ([core theory](core_theory.md#which-distance-occluder-and-light-separated)). HRC keeps transverse resolution at every level, so interpolation is always 1D between adjacent probe lines and never spans a long distance, and its results come within reach of a converged path tracer. Implementers add that it has no ringing and no leaks and needs no bilinear fix, because its rays continue each other without overlapping, and that its penumbras are sharper than with the bilinear or parallax fix ([HRC notes](../sources/2026_holographic_rc.md#how-it-behaves-next-to-vanilla-rc)). Vanilla RC's minimum penumbra angle, which makes shadows behind small sharp sources look soft or splotchy, is by design, and HRC is what removes it in 2D ([merging notes](../sources/2026_merging_and_ringing.md)).

## Geometry

- **Fluence and media.** HRC works in fluence, radiance integrated over all directions with no cosine, since 2D points need not lie on surfaces; everything is participating media, and surfaces are dense volumes. Interval radiance and transmittance merge like premultiplied alpha, `Merge((L₁, β₁), (L₂, β₂)) = (L₁ + β₁·L₂, β₁·β₂)` with `β = 1 − α`.
- **Quadrants.** The problem splits into four quadrants. Each pass handles directions within ±π/4 of +x, then the world rotates by 90°.
- **Probes.** Cascade `n` places probes at `p = (x·2ⁿ, y)`: spacing grows only along the travel axis, so each cascade is a set of probe lines (planes) `2ⁿ` px apart with one probe per pixel row.
- **Directions.** Direction index `i` takes half-integer values from `1/2` to `2ⁿ − 1/2`. Cone `i` is bounded by `p + v(i ± 1/2)` with `v_n(k) = (2ⁿ, 2k − 2ⁿ)`, the offset to a probe of the next column, so every boundary ray ends exactly on a probe. Angular resolution and trace distance both double per level, so ray ends stay evenly spaced at every level. A cone's angular size is `A_n(i) = angle(v_n(i + 1/2)) − angle(v_n(i − 1/2))` with `angle([x, y]) = atan(y/x)`.
- **Counts.** A cascade `N` probe has `2^N + 1` boundary rays and its rays are as long as the plane spacing, so length doubles per cascade, where vanilla 2x/4x quadruples it. Each cascade halves the probes along one axis and doubles the directions, so the interval count per cascade stays constant and, in 2D, equals vanilla 4x's per-cascade memory. A 1024 px scene needs 10 cascades where vanilla 4x needs 5 (9 against 5 at 512 px, 11 against 6 at 2048 px, derived), and every cascade is needed: dropping from 11 to 8 left artifacts ([HRC notes](../sources/2026_holographic_rc.md#how-it-behaves-next-to-vanilla-rc)). Extensions read every cascade, so vanilla RC's two-texture ping-pong does not work.
- **The penumbra condition.** One argument says HRC does not exploit the penumbra condition: its spatial-to-angular ratio rises per cascade, so far-field penumbras can come out sharper with vanilla 4x.
- **Line space.** An HRC frustum stores radiance per pair of points on two planes, the two-plane line parameterization of the 1996 light field papers ([below](#background-light-fields-and-line-space)).

## Merging down

The radiance arriving at probe `p` through cone `i` of cascade `n` is built from cascade `n + 1` as the sum of the cone's two halves, `R_n(p, i) = F₊ + F₋` ([HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#merging-down-r_n-from-r_n1)):

- **Odd `x`**, with no `n + 1` probe at `p`: trace along each cone edge to `q± = p + v_n(i ± 1/2)`, which lands on an `n + 1` probe, and merge with that probe's closest direction `j± = 2i ± 1/2`: `F± = Merge(A_n+1(j±) × Trace(p, q±), R_n+1(q±, j±))`.
- **Even `x`**: reusing `R_n+1(p, j±)` directly biases toward cone centres, so two estimates are averaged, `F± = (R_n+1(p, j±) + Merge(A_n+1(j±) × Trace(p, q±), R_n+1(q±, j±)))/2` with `q± = p + 2·v_n(i ± 1/2)`.

Rules implementers found ([HRC notes](../sources/2026_holographic_rc.md#merging-rules)):

- **Half-integer tangents.** Directions at tangents `(i + 0.5)/N` never reach 45°, so adjacent frustums do not count the diagonal twice; integer indices with `2^N + 1` rays give bright crosses on diagonals.
- **Cone weights.** Tangent-spaced rays cover unequal angles, so each cone's radiance is multiplied by its angular size, the `atan` of one edge minus the other, when the cone is built; weighting after merging counts rays twice. Missing weights give an X pattern and equal weights square isolines. `1/dot(mid, mid)` is said to approximate the weight within 0.002; checked here against the exact width `atan((2k + 2 − s)/s) − atan((2k − s)/s)` with `s = 2ⁿ`, the approximation `(2/s)/(1 + m²)` for midpoint slope `m` is off by up to 0.015 rad at level 1 (about 2%), 0.007 at level 2, 0.0012 at level 3 and 0.0002 at level 4 (derived), so the stated 0.002 holds from level 3 up. Weights scale radiance only, not transmittance.
- **The X in any tracer.** Equal-length rays at all angles show the same X, so traced rays need the optical-depth correction too, a step length of `1/|cos θ|`.
- **Even planes.** Even planes (b-type rays) have no upper probe at their position: trace twice as far, merge the near and the far plane, and average. Merge first and interpolate after; the other order breaks occlusion, and Volumetric-HRC's README agrees that interpolating before merging cannot replace it. Weighting b-type rays is the main unsolved problem: distance-based weights work for opaque scenes and fail with transparency. Merging only odd planes removes that dependence and halves tracing.
- **Quadrant offset.** Offset each quadrant by 1 px when combining the four frustums, or diagonal rays counted by two quadrants form a plus sign; the offset also lets the last cascade be dropped. This is the paper's `+1` in the final gather.
- **Normalization.** Accumulating each ray's weight in alpha during merge-down and dividing at the end makes contributions sum to 1 for any merge pattern.

How the codes weight cones (each read from its source, [implementations](holographic_rc_implementations.md)):

| Code | Cone weight |
|---|---|
| paper, amitabha, lancimir | `A_n(i)`, the `atan` (or `atan2`) difference of the cone edges |
| TypeGPU | `(atan(slope1) − atan(slope0))/(2π)`, so the output is radiance normalized by 2π |
| folkjs | exact arc widths `atan2(2s − N + 2, N) − atan2(2s − N, N)` with `N = 2^(L+1)` |
| jason.today/hrc | slope-bin widths `atan2(2s − 2n + 2, 2n) − atan2(2s − 2n, 2n)`, `n = 2^level`, π/4 at level 0 |
| pixi-GI | `0.5·atan(I/(I² + k(k + 1)))` with `I = 2^n`, half the angle between slopes `k/I` and `(k + 1)/I`; the weights sum to π, so the resolve multiplies by 1/π |
| tfKyRw, WfyyDm | `angle(ray1, mid)/angle(ray1, ray2)` with `mid` the average of the two rays: 0.5 and 0.5 at level 0, about 0.41 and 0.59 for level 1 cone 0 |
| Youssef-Afella's Unity port | the same ratio with `mid` normalized from unnormalized integer vectors, so both weights come out near 0.5 (a bug) |
| hbattal | `atan` differences at merge-down; the top reads a sky texture times the cone width |
| Half HRC | a tent `1 − 0.5·|index − I/2|/(I/2)`, 1 at the centre ray and 0.5 at the edges, not an angle |
| hrcviz2 | 1 for odd merges, ½ for even merges, with precomputed polygon-area weights |
| 4ctczl | none: 16 sub-steps averaged with equal weights |

The `atan` difference of a cone's edges equals `atan(Δ/(1 + m₀m₁))` for edge slopes `m₀` and `m₁ = m₀ + Δ`, which is pixi-GI's argument with `Δ = 1/I`; the codes that agree with the paper differ only in the slope scale and in whether the constant (½, 1/2π, 1/π) is applied per cone or at the end (derived). The ratio form of the Shadertoys splits a cone between its two boundary rays rather than weighting the cone, a different quantity that happens to give 0.5 at level 0 (inference).

## Building rays: the acceleration structure

`T_n(p, k)` approximates `Trace(p, p + v_n(k))` for `p = (x·2ⁿ, y)` ([HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#ray-acceleration-structure-t_n)):

- Levels 0 to 2 are traced directly, by a DDA through pixels with analytic per-pixel emission and absorption, because merge error grows as rays get shorter.
- Higher levels are built by merging ("merge-up"). For even `2k`, `T_n+1(p, 2k) = Merge(T_n(p, k), T_n(p + v_n(k), k))`. For odd `2k` the midpoint falls between cells, so the two nearest merged pairs are averaged: `F± = Merge(T_n(p, k ± 1/2), T_n(p + v_n(k ± 1/2), k ∓ 1/2))` and the result is `(F₋ + F₊)/2`.
- The structure needs no empty-space skipping, so dense volumetrics (fractal clouds) cost the same as empty scenes, while a path tracer took 12× longer on them.

The merge is associative, which is what lets a long ray be assembled from short ones in any grouping ([core theory](core_theory.md#the-merge-operator)).

**Extensions in practice** ([HRC notes](../sources/2026_holographic_rc.md#tracing-and-extensions)):

- The community calls merge-up "extension": a cascade `N` interval is two cascade `N − 1` intervals chained end to end, merging radiance and transmittance without tracing. The usual split traces cascades 0 to 2 or 0 to 3 and extends the rest; with plain DDA, turning extensions off made one stress scene about 40× slower.
- Starting extensions at cascade 0 leaves a cross (X) around small emitters and around emitters inside occluders, because extensions lack the angle term of a traced ray, and it caps angular resolution at the 16 to 20 starting rays, which rules out mirrors. Starting at cascade 3 removes the cross but aliases more per pixel. Reports disagree on which is more accurate; tracing to cascade 4 and extending to 7 matched or beat pure tracing.
- Extensions bend rays slightly ([visualization](https://deadlyredcube.com/RCStuff/extensions.html)) and are blurrier rather than more accurate; some rays must connect exactly, or the result over-diffuses. Computing a shorter and a longer extension and interpolating the endpoint between the two nearest planes reproduces exact lengths, such as vanilla interval starts, and is still cheaper than tracing.
- Extensions also speed up vanilla RC: one pixel-art project used them that way, and vanilla RC can use them as cone-tracing mips ([volumetric RC](../sources/2026_volumetric_rc.md)).
- Cascade 0 is 1 px long, so it needs no tracing or storage; the final gather traces one ray per pixel to the cascade 0 start.
- Transmittance: plain RC never reads the upper cascade's transmittance, because its radiance already reaches infinity, while extensions need it stored and carried up to the merge-down, interpolating it linearly between two angles; implementers preferred extensions for real-time volumetrics ([volumetric RC](../sources/2026_volumetric_rc.md)).

| Code | Traced levels | Built by extension |
|---|---|---|
| paper | 0 to 2 | 3 up |
| amitabha | its two lowest, the paper's levels 1 and 2 ([implementations](holographic_rc_implementations.md#amitabha)) | the rest |
| TypeGPU | `tracedLevels`, default 3 (spans of 1, 2 and 4 px) | the rest; each extra traced level doubles the longest traced span, giving more medium reads and fewer approximate joins for the same memory |
| lancimir (GPU) | 0 to 2, transmittance by brute-force point samples | the rest |
| cute_framework, folkjs | 0 to 2, through raw scene texels (merging them gave Manhattan-shaped artifacts) | the rest |
| hbattal | cascade 0 alone, by a texel DDA | 1 to `n − 1` |
| Volumetric-HRC, pixi-GI | cascade 0, seeded per pixel | from cascade 0 up (the README says this reduces aliasing and is more stable through angular diffusion) |
| 4ctczl, tfKyRw, WfyyDm | every level marches its full length | none |

**The bend, drawn.** deadlyredcube's `extensions.html` shows how long rays are assembled ([HRC notes](../sources/2026_holographic_rc.md#deadlyredcube-extensions-and-oriented-probe-lines)). On a square grid (default 32×32, width 2 to 64), level `c` has `2^(c+1)` rays; level 0's two rays both cover cells (0, 0) and (1, 0), and the cell list of ray `r` at level `c` is that of ray `r >> 1` at level `c − 1` followed by the same list shifted by `(2^(c−1), ((r + 1) >> 1) − 2^(c−1))`, skipping repeated cells (`extensions.js` 121-146); levels run to `ceil(log₂W) − 1`. A long ray of `Extent = W − 1` is assembled from the levels whose bit is set in `Extent`, descending into the lower or upper child by ray index (`DrawRayCover`, 203-272), so width 32 (`Extent` 0b11111) draws levels 0 to 4 while width 33 (`Extent` 32) draws level 5 alone. In `RenderProbes` (275-349) each segment ends at `(x + 2^c, y + r − 2^c + 0.5)` and its two children start there offset ±0.5 in y, so an extended ray is a polyline whose direction changes at every junction: these are the bent rays that make extensions blurrier than straight traces. `GetCascadeDistance` and `RayFromIndex` are never called, and several globals are implicit. fad's Desmos graph (1syt8xa8xl, 2025-01-11) draws the same binary tree of segments with a recursive `g(p, d, i)` up to level 4, splitting a ray into children `2d ± (0, 1/2)` or drawing a segment from `p + k·d` to `p + d` when `p.x` is not a multiple of `2^(i+1)`, with `k = −0.97` ([wiki](../sources/2026_rc_community_site_and_wiki.md)).

**The discrete Radon transform.** Press (PNAS 103(51):19249-19254, 2006, read from the PMC copy PMC1697830 with equations as images) defines digital lines `D_N(h, s)` on an `N × N` image (`N` a power of 2) from row `h` of column 0 to row `h + s` of column `N − 1`, covering 0° to 45°, recursively from d-lines of half-width images, deviating from the continuous line by at most `(1/6)·log₂N` vertically ([HRC notes](../sources/2026_holographic_rc.md#discrete-radon-transform-press-2006)). The transform (Götz and Druckmüller 1996, Brady 1998) sums pixels along every d-line in `log₂N` sweeps, each merging adjacent half-width partial sums into full-width ones with additions only, `(N² − N/2)·log₂N + N(N − 1)` additions in all; flipping the image gives the other three quadrants, and the `6N² − 2N` values over-complete the image, so the inverse is a pseudo-inverse, with backprojection running the same sweeps in reverse. The exact inverse is iterative (a recursive approximate inverse with half-size inverse, prolongation, forward transform, residual backprojection and a local high-pass filter, inside a residual correction using the exact forward operator), with convergence shown numerically, not proved, and empirical work `O(N²·(log N)³·log ε)` fitted for `N` from 16 to 1024 and converging up to 2048; a Fourier inverse in the supplement cannot be iterated. Any associative and commutative operation can replace addition: a median transform detects a 4 px line 0.5 σ above Gaussian noise among heavy point clutter. Its sweep is HRC's merge-up without occlusion: d-lines of width `2n` are built from two of width `n`, as HRC builds level `c` rays from level `c − 1` segments, and the d-lines' bounded deviation is the extension's bend; HRC's merge is associative but not commutative, which keeps the sweep valid as long as every combination keeps the nearer segment first (inference).

## Final gather and cleanup

- **Gather.** Fluence at `[x, y]` for the +x quadrant is read from `R₀([x + 1, y], 0)`; the `+1` stops diagonal rays of adjacent quadrants overlapping into bright crosses ([layout](cascade_layout_and_merging.md#final-gather)).
- **Beyond the domain.** Lookups at `R_N` are zero; off-screen lights or an environment map can be supplied there, by cone tracing or by reading the map in direction `v_N(i)`. folkjs integrates a sky table into a prefix-sum table per direction row, so any merge bin's sky light is one subtraction ([implementations](holographic_rc_implementations.md#cute_framework-and-folkjs)).
- **Directions.** Only `4·(2² + 1) = 20` truly traced directions exist per point, which blurs specular BRDFs ([core theory](core_theory.md#specular)). The output fluence has 4 directions, enough for diffuse multi-bounce fed back over frames.
- **Checkerboard.** Probes with odd and even `y` never interact, because `v_n(k)` is always even for `n ≥ 1`. The approaches:

| Approach | Used by |
|---|---|
| 1-pixel cross blur `[0 1 0; 1 4 1; 0 1 0]/8`, skipping neighbours with very different opacity | paper; amitabha (5 taps among equal opacities); TypeGPU's integrate pass (`|Δopacity| < 0.1` per channel); folkjs; lancimir (centre 1/2, neighbours 1/8, the same kernel) |
| 2×2 box with a half-texel offset, equal to a 3×3 binomial | community |
| a 0.25/0.5/0.25 filter against phases alternating along the probe axis, then a 4×2 kernel over the four fields | jason.today/hrc |
| four diagonal taps at `2^(i−1)` texels in pass `i`, up to 3 passes, cancelling the 2, 4 and 8 px lattice patterns (checkerboard from 1.5% to 0.05% of mean luma) | pixi-GI |
| dense offsets `(2^i, k − 2^i)` with `2^(i+1) + 1` directions, which couples every row and doubles angular resolution | cute_framework |
| drop every other probe row and interpolate at the end, about 2× faster | Half HRC |

## Measured results and the cost model

The paper's numbers (RTX 3080 Laptop, Rust with LuisaCompute over CUDA, fp16 RGB radiance and transmittance):

| Grid | Merge up (build `T`) | Merge down (build `R`) | Total |
|---|---|---|---|
| 256² | 0.30 ms | 0.25 ms | 0.55 ms |
| 512² | 1.00 ms | 0.85 ms | 1.85 ms |
| 1024² | 4.10 ms | 3.57 ms | 7.67 ms |
| 2048² | 18.1 ms | 15.8 ms | 33.9 ms |

- **Accuracy.** At 1024², RMSE is 0.0063 against 0.0667 for a 52 spp path tracer at equal sample count (98.6 ms), about 10× better.
- **Time and memory.** Time is `O(X·Y·log X)`. Memory is dominated by the `T` structure, about `log₂X·4·X·Y·(r + t)` bytes, and could drop to `2·4·X·Y·r` with a BVH instead.
- **Rays.** Without acceleration each output value needs `4·(log₂X + 3 + 2^−log₂X)` intervals, 52 at 1024². With the acceleration structure only 19 traced rays per base probe remain, all shorter than 6× the base spacing. Both check out: `4·Σ_{L=0..2}(1 + 2^−L) = 19`, and the longest traced segment, level 2's diagonal, is `√(4² + 4²) = 5.66` base spacings (derived).
- **In practice** the fluence would be computed at a lower resolution and upsampled 2 to 4× to the screen, merging with rays traced to the probes to avoid leaks.
- **Limitations.** Lights smaller than about 8 base probes show moiré-like aliasing, because ray segments are fixed; larger lights are fine. Sharp shadows keep about 4 px of blur against the reference. 3D needs `O(N⁴)` memory for an `N³` volume ([below](#3d)).

Worked numbers from a script over the paper's formulas (derived):

| Quantity | 512² | 1024² | 2048² |
|---|---|---|---|
| Paper `T` memory, `log₂X·4·X²·12 B` (fp16 RGB radiance plus RGB transmittance) | 108 MiB | 480 MiB | 2112 MiB |
| TypeGPU's stated layout, all levels inclusive ([implementations](holographic_rc_implementations.md#typegpu-holographic-runner)) | 38 MiB | 160 MiB | 672 MiB |
| Measured time ratio to the next smaller size | ×3.36 | ×4.15 | ×4.42 |
| Ratio predicted by `X·Y·log X` | ×4.50 | ×4.44 | ×4.40 |

- **Scaling.** The measured ratios approach the `X·Y·log X` prediction as the grid grows; small grids pay a fixed overhead per pass, which flattens the first step (inference).
- **Bandwidth.** The paper's layout at 1024² holds about 50.3 million intervals and 41.9 million fluence values over the four quadrants. At 2, 3 or 4 reads per stored value, one frame moves 2.82, 3.76 or 4.70 GB, which takes 6.3, 8.4 or 10.5 ms at 448 GB/s and 7.3, 9.8 or 12.2 ms at 384 GB/s, the two memory configurations the RTX 3080 Laptop shipped with (bandwidths assumed from the GPU's specifications, not from the paper). The measured 7.67 ms sits between 2 and 3 reads per value, consistent with the community's finding that HRC is bound by memory bandwidth ([performance](#performance)) (derived).
- **Normalized.** Scaled to a desktop RTX 3080's 760 GB/s (also assumed from the GPU's specifications), the paper's 7.67 ms becomes about 4.5 ms; community builds at 1.8 to 3 ms at 1024² on that card are 1.5 to 2.5× faster, which matches what their bandwidth savings (one transmittance channel, fewer probes per plane, packed formats) predict (inference).
- **Cascade count.** HRC needs `log₂` cascades where vanilla 4x needs `log₄`, so about twice as many passes over constant-size cascades, which fits the community estimate of "about 2× vanilla 4x" in cost (inference).

The community wiki describes HRC as single-shot and noiseless, close to a 2D reference, and able to resolve hard shadows and volumetrics at a cost similar to standard RC; it gives the memory as `O(N·X²)` without defining `N` or `X` ([wiki](../sources/2026_rc_community_site_and_wiki.md)). Reading `N` as the cascade count and `X` as the side length, this is the paper's `log₂X·X²` (inference).

## Where it works

- HRC works for lights larger than about 8×8 px, and 16 px circles looked clean, in line with the paper's 8-probe limit. It is poor at pixel-art resolutions, where single-pixel lights show crosses and streaks ([HRC notes](../sources/2026_holographic_rc.md#how-it-behaves-next-to-vanilla-rc)).
- Vanilla RC's counterpart is the ray-end gap: a light resolves when it is larger than the gap between neighbouring rays at the end of the interval that reaches it, and about twice that by the Nyquist limit ([choosing cascade 0](core_theory.md#choosing-cascade-0-derived-and-reported)). In 3D at the equal-error `t0` the gap at cascade 0's end is one probe spacing. With `l = 2` it stays one cascade 0 spacing at every cascade's end, a fixed minimum of 1 to 2 base spacings, 4 to 8 times smaller than HRC's 8 probes; with `l = 4` it is the spacing of the cascade that reaches the light, `Δs0·√(t/t0)` at distance `t`, and two gaps pass 8 base spacings from the end of cascade 2, `16·t0` away (derived, [check](../checks/ray_end_gap_3d.py)).
- The merging notes say the opposite about low resolutions: for 240p to 360p pixel art, either use HRC or run RC above output resolution and downscale, because low resolutions suit HRC better than vanilla RC ([merging notes](../sources/2026_merging_and_ringing.md)). The two fit if "suits better" refers to vanilla RC's minimum penumbra angle, which is worst when a few pixels span the whole scene, while "poor" refers to lights one or two pixels wide, under HRC's 8-probe limit: the deciding quantity is light size in probes, not output resolution (inference).

## Artifacts and fixes

| Artifact | Cause | Fix |
|---|---|---|
| Checkerboard | Odd and even probe rows never interact | The blurs in the [gather table](#final-gather-and-cleanup), or half HRC |
| Cross around small or enclosed emitters | Extensions from cascade 0 lack the angle term | Trace the first 3 or 4 cascades |
| X pattern or square isolines | Missing or equal cone weights | `atan` cone weights ([merging](#merging-down)) |
| Bright crosses on diagonals | Integer direction indices with `2^N + 1` rays | Half-integer tangents |
| Plus sign where quadrants meet | Diagonal rays counted by two quadrants | 1 px quadrant offset |
| Striations | Even-plane merging and heavy hardware interpolation in extensions | Costly to fix; fewer interpolated extensions |
| Flicker at frustum edges in motion | Edge rays get no diffusion | Extend left and right, then lerp the middle (2× extension cost), or shift edge rays 1 px |
| Leaks along the frustum | Probe density drops across thin solids | More probes along the plane |
| Seams between frustums | High air absorption | Lower absorption or more cascades |
| Opacity pop near 1 | 11-bit floats top out at 0.996 below 1 | Store absorption `1 − T` instead of `T` |
| False opacity on diagonals | R16F rounding gave 0.00138 against a 0.001 epsilon | Epsilon 1/512 |
| Colour shift and smoke flicker | R11G11B10F cannot reach full white | RGBA16F; RGB9E5 crashed as a render target on an RTX 3080 and is not a WebGPU storage format |
| Dim or wrong brightness | sRGB converted twice, or before dividing by the four frustums | Linearize inputs once (pre-linearized textures also halved tracing cost) |
| Moiré on lights under about 8 probes | Fixed ray segments | Larger lights; polygonal variants ([below](#polygonal-cascades)) |

The format rows are general RC precision issues and sit with the other packed-format findings in [artifacts and fixes](artifacts_and_fixes.md). folkjs stores RGB9E5 in a storage buffer it packs by hand, which sidesteps the render-target and storage-format limits in the table ([implementations](holographic_rc_implementations.md#cute_framework-and-folkjs)) (inference).

## Performance

HRC is bound by memory bandwidth (96% in one profile), so most gains come from writing less ([HRC notes](../sources/2026_holographic_rc.md#performance)):

- One transmittance channel in alpha instead of RGB doubled speed in one build and cut cost by 25% and memory by 50% in another, at the cost of coloured glass.
- Radiance and transmittance belong in one texture: splitting them slowed extension from 0.08 to 0.15 ms and cone merging from 0.09 to 0.14 ms at 1024².
- Fewer probes along each plane: spacing growing to 8 px saved 70%, to 4 px 52%, to 2 px 27%. Half the probes with hardware vertical interpolation saved 50% at 4K and took 1024² from 27 to 14 ms.
- At 16:9, 44% of the short-axis probes are off screen. Dispatching fewer threads, or separate 1920×1080 and 1080×1920 textures, saved 20% to 40%.
- Dropping a pre-clear pass saved about 50% at 4K. Replacing `atan(y/x)` code with `atan(y, x)` or a lookup table saved about 5 ms at 1024². Per-level workgroup shapes gained 15%.
- On Apple GPUs, fragment shaders ran 1.2 to 1.8× faster than compute, because render targets are compressed and storage buffers are not. The speedup is the community's measurement; the [WWDC 2021 talk](https://developer.apple.com/videos/play/wwdc2021/10148/?time=581) (session 10148) gives the mechanism and no comparison: from 581 s it says the ShaderWrite or PixelFormatView usage flag disables lossless compression of a texture, that ShaderWrite is needed for `write()` from fragment or compute functions but not for rendering into a colour attachment, and that uncompressed textures cost bandwidth when stored from tile memory. So the penalty follows the write path, not the shader stage (inference).
- Luminance at full resolution with colour at quarter resolution: 4K in 8 ms instead of 12 (RTX 3080 Ti, WebGL) and 17 instead of 26 (M4 Max); 1024² under 14 ms on an iPhone 16. jason.today/hrc ships this split, and its algebra is in the [implementations](holographic_rc_implementations.md#jasontodayhrc).
- Quarter-resolution HRC with an edge-aware upscale ran 4K at 135 to 144 fps against 78 fps native on an RX 9060 XT, with softer shadows.
- Tracing an 8×8 probe block from shared memory cost 0.06 ms for four cascade 0 directions against 1.6 ms for DDA.

| Setup | Time |
|---|---|
| 512², 4×4 px light, 10 cascades (the Shadertoys [tfKyRw and WfyyDm](holographic_rc_implementations.md#shadertoys) are similar builds without the extension step) | 0.88 ms |
| 1024², 4 traced and 6 extended cascades, RTX 3080 | about 7 ms; about 3 ms with RGBA16 merges, RGBA8 extensions and cones built on the fly |
| 1024² and 2048² without stored cascade 0 or cone transmittance, RTX 3080 | 1.8 ms and 7.5 ms |
| Volumetric extensions from cascade 0, all four frustums | under 2 ms at 1024², 5 ms at 2048² |
| Volumetric-HRC, open source | 2.61 ms at 1024² on an RTX 3080; 0.75 ms at 512² on a GTX 970 |
| 1080p without extensions, 2x/2x with pre-averaging, RTX 3080 | 7 ms, against 23 ms for per-pixel SDF marching |
| 2048² and 4096² | 3 + 7 ms and 15 + 25 ms (extensions + merging) |
| 2048×1024 in WebGL on an RTX 4060 Ti | 5 ms |
| Godot luminance-only HRC, 1080p, RTX 3090 | 7.57 ms, 5.10 ms with caching |
| 1024², Radeon 760M | about 23 ms, then 60+ fps after a fix |
| Steam Deck | about 40 ms at 1024², about 10 ms at 512² |
| Unreal Engine 5 showcase: three HRC passes for three light layers, BVH tracing | 120+ fps at 4K |
| pixi-GI, Apple M1 Pro in Chrome | 3.0 ms at 256² (8 cascades), 8.5 to 10.4 ms at 512² ([implementations](holographic_rc_implementations.md#pixi-gi)) |
| Equal-angle HRC, 2D, RTX 5090 | 1.05 ms ([below](#equal-angle-ring-radial-and-axis-aligned-hrc)) |

How HRC compares with vanilla RC depends on cascade count and cascade 0 length, and reports conflict: about 2× vanilla 4x and 2× faster than the bilinear fix at equal base probes; 14 ms without extensions against 1.5 ms vanilla, about equal once mips are added; and poor on a Steam Deck, where 3× angular scaling was much faster than 2x/4x for similar quality. The Godot luminance-only build at 7.57 ms is the only Godot number; 2D timings across all RC kinds are compared in [performance](performance.md).

## 3D

- **Cost.** 3D HRC needs `O(N⁴ log N)` memory and compute for an `N³` volume, and extensions are unsolved in 3D. Reported numbers: a 64³ cascade volume at 77 ms and 1.5 GB, 128³ at minutes per frame, a demo at about 20 fps on a laptop RTX 4090, and 512³ does not fit in memory ([HRC notes](../sources/2026_holographic_rc.md#3d-and-screen-space)). The paper mentions an experimental 128³ voxel version; Sannikov's 37-second video "Exploring 3d holographic radiance cascades" (xT_7JtYXdNc, 2025-09-02) renders Sponza stored in HRC directly and gives no grid sizes, memory, frame rate or GPU ([videos](../sources/2022_sannikov_youtube_rc_videos.md)); Dell'Ova's thesis repeats the `N⁴` growth as limiting 3D HRC to small volumes ([Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md)).
- **Memory model (derived).** A 3D frustum generalizing the 2D layout has, at level `L`, `N/2^L` planes of `N²` probes with `(2^L + 1)²` directions. Summed over the levels below `log₂N`, one frustum holds 1.20 `N⁴` intervals at `N = 64`, and 2.23 `N⁴` with the top level included; the constant falls toward 1 and 2 as `N` grows. With six frusta at 8 B per interval (RGBA16F, radiance plus one transmittance channel):

| `N³` | Memory, without and with the top level |
|---|---|
| 32³ | 0.07 to 0.12 GB |
| 64³ | 0.97 to 1.80 GB |
| 128³ | 14.4 to 27.5 GB |
| 256³ | 220 to 428 GB |
| 512³ | 3.4 to 6.7 TB |

  The range brackets the reported 1.5 GB at 64³, and 512³ is three orders of magnitude past any GPU, matching "does not fit". The 3D equal-angle HRC for caustics took about 9 GiB at 128³ ([light transport alternatives](light_transport_alternatives.md#caustics-and-refraction)), below this model's 14 to 27 GB, so that build stores less per interval or fewer levels (inference).
- **Below `N⁴` (derived).** A store that makes the extend identity exact for every line through the volume holds on the order of `N⁴` values ([core theory](core_theory.md#where-the-merge-is-exact-derived)), so a layout below it keeps transverse resolution only for some lines. In the memory model level `L` holds `N³·(2^L + 1)²/2^L` intervals per frustum, roughly doubling per level from `L = 3` up, so stopping HRC at segment length `d = 2^L` and handing longer intervals to vanilla RC drops the largest levels: up to `d = 8` a frustum holds 24.9 `N³`, and up to `d = 16` 42.9 `N³`. Level 0 alone holds `4·N³`, so over six frusta at 8 B per interval the near field still needs 0.31 and 0.54 GB at 64³ and 2.5 and 4.3 GB at 128³, against 0.97 and 14.4 GB for the full stack below the top level ([check](../checks/hrc_line_count.py)). Frusta placed only where occluders are, and the polygonal block layout with sparse extensions, save in proportion to a scene's empty space, which no source has measured.
- **A constant-memory layout** that worked: halve probes and planes per axis and multiply directions by 4 per axis, starting from 256×256 probes, one direction and 16×16 planes. Keeping probes while doubling directions violates the penumbra condition and looked bad. Plane spacing ×4 worked in 3D but added nothing in 2D. This layout is vanilla RC's 3D scaling with planes instead of points, so it gives up HRC's full transverse resolution, the property that makes HRC's shadows sharp (inference).
- **When it pays.** The case for 3D HRC is volumetrics. For surfaces, vanilla or sparse RC with shadow maps or next-event estimation for hard shadows is simpler. The polygonal block layout ([below](#polygonal-cascades)) is the 3D candidate that supports sparse extensions.
- **Screen space.** Screen-space HRC was judged impractical: extensions need intervals that meet end to end, which probes placed on the depth buffer break, and focal points must lie on probe lines.

## Off-screen light

- Extensions only cover the screen, so off-screen light must be traced separately and merged. Every cascade that leaves the screen needs world-space tracing, and covering twice the off-screen distance costs about 4×.
- Workable shortcuts: render 4× the area at a quarter of the resolution and crop; or cast about 30 CPU rays per light to find occluders and pass analytic circular light proxies to the shader (about 1 ms for 10 lights, no penumbra).
- The paper's alternative is to supply radiance at `R_N`, by cone tracing or from an environment map, which handles light from beyond the domain but not occluders beyond it ([gather](#final-gather-and-cleanup)).

## Variants

### Half HRC

Half HRC drops every other probe row, which removes the checkerboard and simplifies the math, for about 2× speed. The community notes credit it to Yaazarai, whose repository of it was deleted; the shader survives in a copy by brucelevis that holds Yaazarai's commits, described in the [implementations](holographic_rc_implementations.md#half-hrc).

### Equal-angle, ring, radial and axis-aligned HRC

- **Equal-angle HRC** gives each frustum equal width in radians instead of equal slope spacing, which removes HRC's crosses; one 2D build ran in 1.05 ms on an RTX 5090. Its refraction and 3D caustics work is in [light transport alternatives](light_transport_alternatives.md#caustics-and-refraction), where refraction across quadrant boundaries remained the error source.
- **Ring HRC** places probes on rings; about half the probes fall outside the scene, and ring counts need a lookup table. It was judged better suited than frustums to refraction, because bent rays break frustums.
- **Radial HRC** was an earlier community test of whether small perpendicular probe spacing could resolve sharp shadows ([wiki](../sources/2026_rc_community_site_and_wiki.md)).
- **Axis-aligned HRC** turns probes toward each ray direction. It cut tracing from 100 to 10 ms at 1024², but rays no longer share directions, so extensions and pre-tracing are impossible, and it ended up slightly slower than plain HRC.
- **Sheared probe lines.** deadlyredcube's `orientedProbeLines.html` lays out probe lines by shearing instead of rotating (default grid 37×24, 5 levels). Level `c` has `4·2^c` directions at `(a + 0.5)/(4·2^c) − 0.125` turns, split into horizontal and vertical quadrants by `|cos| > |sin|` (`orientedProbeLines.js` 137-142). Probe spacing along the probe axis is `W/⌊W/2^c⌋`, so probes tile the view exactly instead of sitting at exactly `2^c`: at `W = 37` the spacing is 2.056, 4.111 and 18.5 at levels 1, 2 and 4 (153-170). Horizontal directions get grids of `⌊W/2^c⌋ × H` probes, vertical ones `W × ⌊H/2^c⌋`. Probe space maps to screen by scaling along the probe axis, then one shear about the view centre (`skewX = −sin/cos` for horizontal directions, `skewY = −cos/sin` for vertical ones), an origin offset and a toroidal wrap (219-306); since only one shear is non-zero, the sequential inverse is exact. `FindConnectingProbes` (384-458) links a probe at level `c`, direction `a`, to level `c + 1`, direction `2a + o`, at the next lattice row or column the ray crosses, accepting the link only if direction and offset agree within a dot product of 0.95 (about 18°) and the bracketing probes lie within squared distance 2; hovering shows accepted links in yellow and failures in red ([HRC notes](../sources/2026_holographic_rc.md#deadlyredcube-extensions-and-oriented-probe-lines)). The rounding to `W/⌊W/2^c⌋` is what forces the tolerance test: probes no longer sit where an exact power-of-two layout would put them, so links are found by search rather than by index (inference).

### Plane cascades

Sannikov's LegitCascades scripts test HRC ideas in 2D, mostly with one hard-coded light, no scene and no recorded results, and several header comments link to the script they were copied from ([LegitCascades](../sources/2024_sannikov_legitcascades.md#later-experiments-20252026)). Two put probes on vertical planes 8 px apart, 8 px apart along each plane, with 2 directions at cascade 0. Cascade `k` has `planes >> k` planes `8·2^k` px apart and `2·2^k` directions with the probe spacing fixed, so the atlas width `planes·dirs` stays at `W/4` on every level. The light is a vertical segment (by default at x = 100 px, 100 px tall), and merging is `(near.rgb + near.a·far.rgb, near.a·far.a)`.

- **EnergyConservingHRC.ls** traces nothing. A direction bin's coverage by the light is its angular overlap in bin units, `max(0, min(end, dir + 0.5) − max(start, dir − 0.5))`, stored as emission `colour·coverage` with transmittance `1 − coverage`, so partly covered bins conserve energy. The direction index of a slope is `(dy/dx·0.5 + 0.5)·dirs − 0.5`. Merging runs top-down over 6 cascades: an even plane reads parent plane `plane/2` and averages child directions `2·dir` and `2·dir + 1`; an odd plane reads parent plane `(plane + 1)/2` at probe `p − dirs/2 + dir`, also with weight ½. The gather reads the nearest probe on the next plane and averages over directions.
- **ExtendedHRC.ls** builds cascades 1 to 3 bottom-up by extension. An even direction merges plane `2p` with plane `2p + 1` at probe `p + dir/2`, both in direction `dir/2`; an odd direction averages two such chains with the near and far directions swapped (`dir/2 + i` and `dir/2 + 1 − i`). The gather reads cascade 3. Read from the code: the direction mapping divides by `plane_spacing/(dirs·probe_spacing)` in integer arithmetic, which is 0 at every level (the exact value is ½), so the script divides by zero; a loop index in the unused top-down merge is uninitialized; and 6 cascades are configured while 5 images are allocated.

Coverage as emission with `1 − coverage` as transmittance is the partial-coverage rule a polygon or wedge representation needs, and it is the same energy argument as the polygonal scripts' falloff (inference).

### Block cascades

- **BlockHRC.ls:** a probe is an `N × N` block of texels indexing lines by angle (x) and offset (y). Level 0 has 30 px blocks with `N = 20`, and both spacing and `N` double per level over 9 levels. The active parameterization ("diagonal line space") puts a line's origin on whichever block diagonal is closer to perpendicular to it, with angle `2π·x`; an angle-and-distance form, a circle line space and a box line space are defined but unused. Extension builds level `k` from the 2×2 child blocks of level `k − 1`: each parent line finds the child blocks it crosses with a ray–box test and reads the child line nearest in index (bilinear weights rounded). Weight normalization is commented out, so contributions are summed unweighted. The emitter is one level 0 block, (8, 4). The gather scans every angle, rounds the offset index and sums texels times 0.1, computing a Jacobian weight it does not use.
- **IntegerBlockHRC.ls** keeps the BlockHRC core and adds exact integer line tests. Lines are integer `(start, delta)` pairs inside a power-of-two box, split recursively into quadrants (to depth 10), so whether a line passes through a tile is decided without a floating-point ray. Only the test shader runs: on 32 px tiles it draws every integer line through both a pixel's tile and a source tile. It tests exact lattice visibility and is not a working pipeline.

Blocks that hold all lines through them, built from 2×2 children, are the 2D analogue of a sparse 3D layout: each block is self-contained, so only occupied blocks need storage (inference).

### Polygonal cascades

Polygonal HRC tiles space with polygons that never overlap or leave gaps: 1:1, 1:2 and 1:3 cones, or 1:1 bands and 0:1 wedges in line space, where the tiling is Bresenham lines and extending a level reduces to `srcD = D >> 1, err = D & 1`. It gives near-exact falloff with fewer directions, but no version has shadows yet ([demo](https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/PolygonalHRC45.ls&rev=master), [indexing code](https://github.com/entropylost/hrcviz2/blob/main/src/main.rs), [scripts](../sources/2024_sannikov_legitcascades.md#polygonal-cascades), [HRC notes](../sources/2026_holographic_rc.md#variants)). Sannikov's video "Polygonal Radiance Cascades" (AhbnwZFp5iE, 2026-02-28) presents it as aliasing-free light from a single-pixel source, and "Testing polygonal block RC layout" (JcWFXYnYC5M, 2026-03-15, no description, probably unlisted) shows the block layout ([videos](../sources/2022_sannikov_youtube_rc_videos.md)). hrcviz2's polygon-area weights are the indexing side of the same idea ([implementations](holographic_rc_implementations.md#hrcviz-and-hrcviz2)).

- **Primal and dual.** Primal polygons gather from every pixel that contributes to a point; dual polygons splat to every pixel a source reaches. They looked equal in speed and accuracy. Primal handles point sources anywhere but aliases penumbras at probe size; dual gathers at any point, gives clean cone-shaped shadows and is easier to debug, but stores unoccluded radiance. Both capture radiance on a plane and rebuild it elsewhere, and they alias only when the source or the receiver lies on the capture line ([light transport alternatives](light_transport_alternatives.md#resampling-view-of-rc)).
- **PolygonalHRC45.ls** splits the plane into quadrilaterals indexed by line, probe, direction and a frustum flag. Probe spacing stays at 10 px on every level, while line spacing (10 px at level 0) and direction count (1) double, over 9 levels. A polygon spans from line `i` to line `i + 1`, or to `i + 2` for even ("extended") lines, and its frustum form widens by 2 or 3 probes. Its value falls from `1/2^k` to `1/2^(k+1)` across the polygon. Extension builds level `k + 1` from source lines `2i − 2` and `2i − 1` as plain sums with no ½ factor, and gathering sums every polygon that contains a pixel, with the cosine ("Euclidean flux") correction disabled. The negative source line at `i = 0` is not bounds-checked.
- **PolygonalHRC.ls** uses 30 px spacing and no frustum flag: each target polygon sums one texel from each of two source lines.
- **PolygonalPrimalHRC.ls** propagates top-down (primal) instead of bottom-up (dual). The source writes its falloff into the polygons of every cascade, then each cascade from 4 down to 0 adds two or three polygons of the coarser one, each times a placeholder weight of 1. The dual pipeline is present but commented out.
- **PolygonalBlockRC.ls** only draws the wedge geometry of block probes: an inner box `probe ± length_scale` and an outer box from the half-index probe at twice the spacing. **PolygonalBlockExtendedRC.ls** seeds one tile with a random colour per direction, sums four children per parent with no weights, and gathers over a 7×7 probe neighbourhood. The last commit, "Added 4x scaling RC" (2026-04-09), adds `PolygonalBlockExtendedRC4x.ls`, a byte-identical copy of `PolygonalBlockExtendedRC.ls`.
- **The polygonal block layout for 3D** supports sparse extensions and sits closer to vanilla RC than to HRC ([demo](https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/PolygonalBlockRC.ls&rev=master)).

A polygon carries the radiance of a whole region of line space where a ray carries one line, which is why a one-pixel source stops aliasing: the light is integrated over each polygon instead of sampled. Shadows are the missing piece because an occluder that cuts a polygon partly needs the polygon split or its coverage estimated, the problem EnergyConservingHRC's coverage rule addresses for the light (inference).

### Gradient RC

Gradient RC stores a value and a directional derivative per probe direction and skips interpolation. Point-light falloff was good, motion stable and memory low, which fits sparse 3D, but occlusion still aliases ([demo](https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/GradientRC.ls&rev=master)). `GradientRC.ls` propagates nothing: each of 6 cascades (5 px spacing and 4 to 20 directions at level 0, both doubling) is loaded straight from a point source. The wedge of each probe direction, between an inner and an outer box, stores `1/r` at its midpoint and the slope of `1/r` along its centre line, but only if the wedge contains the source. Gathering evaluates `value + dot(pos − midpoint, dir·slope)` at every pixel and cascade, with a display gain of 20. The reconstruction is first order along the wedge's centre line only, with no slope across it, so the across-wedge error that causes penumbra aliasing is untouched (inference).

### Line space

- An HRC probe direction is a bundle of lines, which makes HRC a Hough or Radon transform. Without occlusion it reduces to a convolution solvable with an FFT; occlusion is the open part. Press's discrete Radon transform is the occlusion-free sweep ([above](#building-rays-the-acceleration-structure)).
- A diagonal basis, with probes `√2` px apart so each line crosses every pixel once, looked far more regular than a circular one. Exact point-light falloff needs each pixel painted by its line's intersection length with the pixel.
- **Margel's line-space demos.** `linespace` plots the 400 lines between two vertical segments (20 × 20 endpoints, 5 apart) as points `(b, 100·m)`, the intercept at `x = 0` and the scaled slope, so a bundle of lines becomes a region of line space; vertical lines divide by zero. `linespace-rotation` turns the endpoints by 0.01 rad per frame about a pin and plots both `(b, b + 100·m)` and `(b, 100·m)`, so the cloud moves as the segments rotate ([HRC notes](../sources/2026_holographic_rc.md#adrian-margel-line-space-and-a-hierarchical-diffusion-solver)).
- **BundleBasisExploration.ls** tests a basis of line bundles for an HRC probe. Each of 20 × 10 basis functions is the family of rays between an origin edge (a 20 px segment on a vertical line at x = 300) and a direction edge (one of 10 slope steps over [−1, 1]). A vertical source segment is projected onto the bundles with 50 × 50 rays each, and each pixel is rebuilt from four neighbouring bundles with bilinear weights estimated from 30 × 30 rays. Only the source-edge parameter is tested, so each ray acts as an infinite line ([LegitCascades](../sources/2024_sannikov_legitcascades.md#bundlebasisexplorationls)).
- Extensions and merges are both reinterpolations of a radiance field over line space; integrating over each target's footprint, a trapezoid in line space, beat point sampling ([light transport alternatives](light_transport_alternatives.md#resampling-view-of-rc)).

### Background: light fields and line space

Light Field Rendering (Levoy and Hanrahan) and The Lumigraph (Gortler, Grzeszczuk, Szeliski and Cohen), both SIGGRAPH 1996, store radiance in free space as a 4D function of lines, each line given by its crossings of two parallel planes, and reconstruct images by interpolating that function. RC discussions cite them as the discretization behind HRC: an HRC frustum stores radiance per pair of points on two planes ([light field note](../sources/1996_light_field_and_lumigraph.md)). The plane names are swapped between the papers: the Lumigraph calls the camera plane `st` and the image plane `uv`, while Levoy and Hanrahan call the first plane `uv` and the second `st`. Section numbers below are the papers' own.

**The Lumigraph:**

- **Representation (sec. 2.1-2.2).** With transparent air, radiance is constant along empty rays, so the plenoptic function reduces to 4D on the surface of a convex hull. A cube encloses the object, and each face is a pair of parallel planes: `st` at `z = 1`, `uv` at `z = 0` with the origin at its centre. A ray is the tuple `(s, t, u, v)` of its two crossings, and the full Lumigraph uses six pairs with normals along ±x, ±y and ±z. A straight eye path along `st` moves the projection of a fixed surface point along straight lines in `uv`, the optical flow that depth correction uses.
- **Discretization (sec. 2.3).** `M` subdivisions in `s` and `t` and `N` in `u` and `v`; `L̃(s, t, u, v) = Σ x_ijpq·B_ijpq(s, t, u, v)` over `i, j = 0..M` and `p, q = 0..N`. The chosen basis is quadralinear: 1 at its grid point and 0 at its neighbours, so each sample comes from the 16 grid points of its hypercube. It is C0 but not band-limited to Nyquist, so the grid is slightly visible (sec. 2.3.1).
- **Projection (eq. 1).** In the L2 metric `x_ijpq = ⟨L, B̃_ijpq⟩`, the inner product with the dual basis, which equals point sampling after low-pass filtering with `B̃`. For the box basis `B = B̃`; for the quadralinear basis the dual is approximated by the basis itself.
- **Resolution (sec. 2.3.3).** `N` near the final image resolution (128 to 512 tested), `M` much lower (16 to 64), because the surface seen in `uv` changes little across `st`. Radiance needs fine spatial resolution on the image plane and only coarse sampling of the viewpoint, the same kind of asymmetry that lets RC trade positions against directions (inference).
- **Depth correction (eq. 2, sec. 2.3.4).** With a proxy depth `z` (0 at `uv`, 1 at `st`), `u' = u + (s − s_i)·z/(1 − z)` and `v' = v + (t − t_j)·z/(1 − z)`, and `B'_ijpq(s, t, u, v) = B_ijpq(s, t, u', v')`; the weights still sum to 1. The pseudocode loops over the four `(s_i, t_j)`, corrects `(u, v)` per corner, then weights the four `(u_p, v_q)` by `(h_uv − |u_p − u'|)(h_uv − |v_q − v'|)/h_uv²` and the corner by `(h_st − |s_i − s|)(h_st − |t_j − t|)/h_st²`. The equation is garbled in text extraction; the pseudocode and a similar-triangle derivation agree on `z/(1 − z)`. This near-field correction, a coarse depth proxy shifting the lookup so interpolation between viewpoints lands on the same surface point, solves the problem parallax-corrected RC merges solve ([artifacts and fixes](artifacts_and_fixes.md)) (inference).
- **Capture (sec. 3.1-3.3).** Synthetic data comes from a pinhole camera at each `(s_i, t_j)` with a skewed frustum onto `uv`; real data from a hand-held camera with Tsai calibration against a 30-marker stage (about 0.5 s per frame on an SGI Indy) and blue-screen silhouettes. An octree visual hull (typically 4 subdivisions) with Taubin smoothing gives the depth proxy.
- **Rebinning (sec. 3.4).** Scattered samples become grid coefficients in three phases. Splat (eq. 4): `w_i⁰ = Σ_k B̃_i(s_k)` and `x_i⁰ = (1/w_i⁰)·Σ_k B̃_i(s_k)·L(s_k)`, undefined where `w = 0`. Pull (eq. 5): coarser levels with `h̃ = {1/2, 1, 1/2}`, `w^{r+1}_i = Σ_k h̃_{k−2i}·w^r_k` and `x^{r+1}_i = (1/w^{r+1}_i)·Σ_k h̃_{k−2i}·w^r_k·x^r_k`, with `min(w^r_k, 1)` in both sums after Mitchell, so dense regions do not dominate. Push: each coarser level fills the gaps of the finer one, keeping fine coefficients with weight at least 1 and blending lower weights with the coarse estimate. This is the pull-push scheme, usually credited to this paper, for filling gaps between sparse samples.
- **Compression (sec. 3.5).** A face of 32×32 `(s, t)` and 256×256 `(u, v)` at 24 bpp over six faces is `32²·256²·6·3` bytes, 1.125 GB. Per-image JPEG gives about 20:1, and inter-image prediction was expected to give about 200:1 (under 6 MB); the results are preliminary.
- **Rendering (sec. 3.6).** By ray: compute `(s, t, u, v)` per pixel and interpolate 16 grid points, with depth from a proxy render whose vertex colours are positions. By texture mapping: each `st` grid point owns a texture `tex_ij(u_p, v_q) = x_ijpq`; the constant basis draws at most `M²` textured squares, and the quadralinear basis draws at most `6M²` alpha-blended triangles that approximate the bilinear `st` weights with a hexagonal pyramid summing to one (Fig. 15c). Depth correction is exact at triangle vertices and approximate inside; triangles subdivide adaptively by screen size or depth variation.
- **Results (sec. 4).** Capture under an hour with an analog camera; processing under a day on an SGI Indy; ray-by-ray rendering a few seconds per 450×450 frame; texture-mapped rendering several frames per second on an SGI Reality Engine, nearly independent of output resolution, limited by texture-cache transfers. Only one cube face was captured, and compression and error reduction are future work.

**Light Field Rendering:**

- **Definition (sec. 2).** The light field is radiance as a function of position and direction, 4D in free space. A light slab parameterizes lines by a point `(u, v)` on a first plane and `(s, t)` on a second, all in [0, 1]. The map from `(u, v)` to its plane, and from pixel `(x, y)` to `(u, v, s, t)`, is projective (a 3×3 matrix, with `u = u_w/w`). One plane can sit at infinity, giving point-plus-direction lines.
- **Tiling line space (sec. 2, Figs. 2-4).** One slab cannot hold every line through a convex hull, so several slabs tile line space, and sampling density in line space should be uniform. Planes meeting at a corner sample poorly near the singularity, so parallel planes or a plane at infinity are preferred. The paper measures density in `(r, θ)` line coordinates, where equal areas mean equal density. RC's per-cascade direction sets face the same question of uniform line-space sampling, and HRC's frustums are slabs that tile the directions in four parts; equal-angle HRC moves toward the uniform `θ` density the paper asks for (inference).
- **Creation (sec. 3.1, Fig. 5).** Each `uv` sample is an image rendered with a sheared perspective so its pixels align with `st`.
- **Prefiltering (sec. 3.1, Figs. 7-8).** The ideal sampling filter is a 4D box in line space: a pixel filter in `st` and an aperture filter in `uv`, which a camera focused on `st` with an aperture equal to the `uv` spacing provides. That aperture turns aliasing (images jumping by the stereo disparity) into blur whose circle of confusion equals the disparity; too small or too large an aperture leaves gaps or overlaps in line space. This is the light-field form of the ringing trade-off in RC: undersampled directions either alias or, when prefiltered, blur; polygonal HRC's integral over each polygon is such a box prefilter in line space (inference).
- **Acquisition (sec. 3.2, Table II).** A four-axis gantry (x, y, pan, tilt), a 10-120 mm zoom locked at 10 mm, f/8, four 90° slabs for 360°. Camera spacing was 3.125 cm against a 1.25 mm aperture, so the aperture problem is acknowledged, not solved. About 3 s per image and 4 h for the lion.
- **Compression (sec. 4, Table III).** Fixed-rate vector quantization of 2D (12-dimensional) or 4D (48-dimensional) tiles at rate `k·l/log₂N`, which for `k = 48`, `l = 8`, `N = 16384` is 384/14 ≈ 27:1, or 24:1 with 2-byte indices; the codebook is trained on a subset and adds under 20%. Gzip on the indices gives about 5:1 more. Decoding is random access (tile index, then codebook lookup) and took about 25% of CPU time. Buddha (50.3 MB raw) reached 45:1 at 36 dB PSNR (15 min training, 1 min encoding); lion (402.7 MB, 2×2×2×2 tiles, 16384 codewords) 118:1 at 27 dB (4 h training, 8 min encoding). Artifacts become objectionable only above about 200:1 (sec. 6). The paper notes that a plain 4D block code compresses well because the scene's 3D structure is already in the coherence.
- **Display (sec. 5).** Compute line parameters by the projective map, then resample with quadralinear interpolation and no band-pass prefilter; 4D mipmapping is suggested for small images. Fig. 13 compares nearest, `uv`-linear and `uvst`-linear.
- **Performance (Table IV).** Lion at 192×192 on a 250 MHz MIPS R4400 in software: 30 ms without interpolation, 75 ms with `uv`-linear and 230 ms with `uvst`-linear. Playback cost depends on image size, not light-field size.
- **Datasets (Table I).** Buddha 1 slab, 16×16 images of 256², 50 MB; kidney 1 slab, 64×64 images of 128², 201 MB; hallway 4 slabs, 8192 images of 256², 1608 MB; lion 4 slabs, 2048 images of 256², 402 MB.
- **Limitations (sec. 7).** Sampling must be dense; the observer must stay in free space (stitching convex regions or adding depth are suggested); lighting is fixed (storing normals and materials is suggested); interreflection could come from superposing light fields lit by basis illuminations.

What the light-field papers mean for RC (inference):

- Both sample radiance per line between two planes and interpolate quadralinearly, which is HRC's storage and, in 2D, its bilinear interpolation between plane points. Neither builds a hierarchy over line-space resolution; that hierarchy is what RC adds.
- The Lumigraph's coarse `st` and fine `uv` sampling, and the depth correction that keeps a coarse viewpoint grid usable, carry the same idea as the penumbra condition and parallax-corrected merges: angular sampling can be coarse where a depth estimate fixes the parallax.
- The memory figures, hundreds of MB to over 1 GB per object at 1996 resolutions, show why a full 4D radiance store cannot be dense, and why RC keeps a constant per-cascade size by trading resolution between space and angle. A 3D HRC frustum is a stack of such 4D slabs, one per plane pair, which is its `N⁴` memory.

### Other uses

- **Diffusion solver.** Margel's [`holographic-cascades-diffusion`](https://adrianmargel.ca/demo/holographic-cascades-diffusion/) (titled "Holographic Cascades") solves steady-state diffusion on a 129² node grid (`2^7 + 1`), each node weighted 1/8 toward each of its eight neighbours (`init.js` 64-72). Positive scene alpha absorbs; barriers are stored as negative alpha and act as reflectors through the node's self term; each colour channel is a separate source term at 0.25. The solve is direct: 15 merge steps (`2·7 + 1`) alternate between merging block pairs along x and along y, eliminating the seam nodes between blocks by Gaussian elimination with `P[y] = M[m][y]/(1 − min(M[m][m], 0.9999999))` and `M'[a][b] = M[a][b] + M[a][m]·P[b]` (`nodePrimer.js`, `nodeElimination.js`), store each block's boundary-to-interior transfer operator, and apply the operators top-down to recover interior values (`valuePropagation.js`). This is nested dissection, a Schur-complement elimination over a block hierarchy, so the "HRC-based diffusion solver" (3 to 4 ms at 129²) shares HRC's merge-up structure of blocks rather than its rays (inference). A Jacobi residual pass with a 4-neighbour stencil, which does not match the 8-neighbour equation, is disabled. The input is a 129 × 129 texture with nearest filtering and repeat wrap (`cascadeManager.js:113-119`), sampled at `coord/2^7` (`getCascadeSize()`, 128) with y flipped (`shader/init.js:25-28`), so node column 128 reads texel column 0, rows 0 and 128 both read texel row 0, and the texture's last row and column are never read ([HRC notes](../sources/2026_holographic_rc.md#adrian-margel-line-space-and-a-hierarchical-diffusion-solver)).
- **Audio.** An audio-attenuation prototype added about 50% on top of HRC.
- **Far fields for stochastic methods.** Reservoir Cascades calls HRC orthogonal to its stochastic approach and names combining HRC far fields with its stochastic near fields as future work ([sampling and guiding](rc_for_sampling_and_guiding.md)).

## Debugging

- Test with one small light and one occluder, a white furnace scene, and point-source falloff against a path tracer. A moving source should show no preferred direction.
- Traced and extended versions of the same ray should match exactly. Streaks with alternating phases mean offset or UV bugs; non-uniform far-plane gaps mean an off-by-one.
- Visualize every interval that contributes to the pixel under the mouse, and push ray lengths 10× to reproduce the merge diagram.
- If two of the four frustums work, the bug is outside the shader. Compute dispatch IDs need +0.5 to hit texel centres, and wgpu storage textures are Y-down.
- folkjs's debug mode shows a path-traced reference and its difference from HRC, the comparison this list asks for ([implementations](holographic_rc_implementations.md#cute_framework-and-folkjs)).

## Connections

- **Merge-up is a Radon sweep with occlusion.** HRC's acceleration structure, Press's discrete Radon transform and deadlyredcube's extension drawing are one construction: lines of width `2n` built from two of width `n` in `log₂N` sweeps, with a bounded deviation from the straight line that shows up as the extension's bend. HRC replaces addition by the transmittance merge, which is associative but not commutative ([above](#building-rays-the-acceleration-structure)) (inference).
- **Extension is the shift-and-extend identity.** Chaining two half-length intervals end to end is the extend identity of [core theory](core_theory.md#where-the-merge-is-exact-derived) applied to rays that share a direction, which HRC's layout guarantees and vanilla RC's does not; that is why vanilla RC can use extensions only as approximate cone-tracing mips (inference).
- **Frustums are light slabs.** HRC's four frustums are Levoy and Hanrahan's slabs tiling line space, and its two-plane storage is the Lumigraph's; what HRC adds is the hierarchy over line-space resolution ([background](#background-light-fields-and-line-space)) (inference).
- **Transmittance has to be stored.** Plain RC never reads the upper cascade's transmittance; HRC extensions need it stored, which doubles memory. This ties HRC's memory to the [volumetric](volumetric_and_radiative_transfer.md) merge rules, where the same `L = L_near + T_near·L_far` operator is shared by every RC variant ([volumetric RC](../sources/2026_volumetric_rc.md)).
- **One lattice is enough.** Odd and even probe rows never interact, so HRC computes two independent solutions on interleaved lattices. Half HRC keeps one and interpolates, trading half the transverse samples for about 2× speed; the cross blurs and jason.today's phase filter average the two lattices, which also low-passes across them (inference).
- **The X has one cause.** The X pattern from missing cone weights, the X from equal-length rays in any tracer and the cross from cascade 0 extensions all come from treating rays of different angular width or path length as equal; the fixes (cone weights, `1/|cos θ|` steps, traced low levels) correct the same measure (inference).
- **Bandwidth rules everywhere.** HRC's bandwidth-bound profile and its savings (fewer channels, combined textures, fewer probes per plane) are the same levers as vanilla RC's packed formats in [performance](performance.md); a cost model in bytes moved predicts the paper's time within the 2 to 3 reads-per-value range (derived above).
- **Gather and splat.** Primal and dual polygonal cascades are the gather and splat forms of one transport operator; vanilla RC is primal ([light transport alternatives](light_transport_alternatives.md#resampling-view-of-rc)) (inference).
- **Split RC's comparison.** The Split RC paper finds that in 2D its matching choice (`K = 2`, `l = 4`) halves per-cascade cost (`K/2^d = 1/2`), so total work is bounded, that one cascade 0 probe per pixel with 4 directions is enough and `K = 4` better, and that HRC is better still at that cost ([3D world space](3d_world_space.md)).
- **A contradiction about lengths.** The Tauray RCPG note says the HRC paper uses `4^i` interval lengths ([Tauray RCPG](../sources/2026_tauray_rcpg_path_guiding.md)). HRC's own rays double per level (`v_n(k) = (2ⁿ, ·)`); the `log₄(D/r)` in the paper is its model of plain RC in the penumbra argument. The evidence favours `2ⁿ` for HRC, and the note's `4^i` describes the plain RC baseline (inference).
- **Lineage.** amitabha (entropylost, also the author of hrcviz, nihil and chandra) is the reference code; pixi-GI credits Volumetric-HRC (Yaazarai) and the paper; the Shadertoys 4ctczl, tfKyRw and WfyyDm are independent; TypeGPU, lancimir, hbattal, cute_framework and folkjs follow the paper's equations ([implementations](holographic_rc_implementations.md)).

## Single-frame assessment

- **2D HRC is single-frame by construction.** It traces no stochastic rays, so one frame gives the full result with no noise, no temporal accumulation and no denoiser. Only bounce light is fed back over frames (the paper's 4-direction fluence output, folkjs's one-frame latency, pixi-GI's temporal accumulation). A single-frame second bounce means a second full HRC solve seeded from the first, doubling cost (inference).
- **Dense 3D HRC does not fit a frame budget.** At 64³ it needs 1 to 1.8 GB and 77 ms, and 128³ needs 14 to 27 GB by the model above. For whole-scene 3D GI it is out; a 32³ local volume (0.07 to 0.12 GB) is within memory and could serve a bounded volumetric region, with timing unknown (inference).
- **Screen-space HRC is out** for the reason given above: depth-buffer probes break end-to-end extensions.
- **What carries to 3D RC:**
  - Building long intervals from short traced ones without tracing (extensions, or cone-tracing mips for vanilla RC) cuts the cost of the far cascades, which matters where tracing is software marching in compute, as under Godot's `RenderingDevice`, which has no ray queries ([Godot integration](godot_integration.md)). It costs stored transmittance and bent rays.
  - The cone-weight, normalization, half-integer-direction and quadrant-offset rules apply to any frustum or cube-face direction layout ([cascade layout](cascade_layout_and_merging.md)).
  - The bandwidth lessons apply unchanged: one transmittance channel, radiance and transmittance in one texture, no pre-clear passes, no threads for off-screen probes.
  - Region integrals (polygonal cascades) and gradient storage are the two ideas aimed at small lights and sparse 3D.
- **Mapping to Godot's `RenderingDevice`.** 2D HRC needs only compute dispatches, storage textures and barriers: no atomics, no float atomics and no ray queries. The pass count is high, 76 to 82 dispatches at 512² to 1024² in the codes that count them ([implementations](holographic_rc_implementations.md)), so dispatch and barrier overhead per pass is part of the budget; a Godot luminance-only build ran 1080p in 7.57 ms on an RTX 3090 (5.10 ms with caching).
