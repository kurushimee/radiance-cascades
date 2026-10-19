# Where the Error of Radiance Cascades Comes From

| | |
|---|---|
| Author | kurushimee (independent researcher) |
| Date | 2026-10 |
| Kind | Paper, original research with code: an exact flatland reference, derivations with assert-based checks, seeded experiments |
| Link | [paper.pdf](../../papers/01_error_model/paper.pdf), source [paper.md](../../papers/01_error_model/paper.md); simulator in [papers/lab/flatland.py](../../papers/lab/flatland.py) |
| Related | [2026_freeman_split_radiance_cascades.md](2026_freeman_split_radiance_cascades.md), [2026_merging_and_ringing.md](2026_merging_and_ringing.md), [2024_osborne_radiance_cascades_radiative_transfer.md](2024_osborne_radiance_cascades_radiative_transfer.md), [2024_sannikov_legitcascades.md](2024_sannikov_legitcascades.md) |

The first measurement of RC's error against an exact answer across parameters, in flatland. An exact reference gives the radiance and transmittance of any distance interval, so every quantity RC estimates has a true value; the error then splits exactly into parts with one cause each, and the parameter rules become testable predictions. Scenes emit and absorb only (no reflection), the quantity is fluence (no cosine), and the RC under test traces rays analytically, so the only errors are RC's own. Claims are marked derived (with a check script in `papers/01_error_model/checks/`) or measured (with a seeded script in `papers/01_error_model/experiments/`).

## Contents

- [Reference and setup](#reference-and-setup)
- [Error decomposition](#error-decomposition)
- [Resolution against distance (derived)](#resolution-against-distance-derived)
- [Small lights (derived and measured)](#small-lights-derived-and-measured)
- [Seams and overlap (derived and measured)](#seams-and-overlap-derived-and-measured)
- [The cascade 0 interval (derived and measured)](#the-cascade-0-interval-derived-and-measured)
- [Interval scale and cost (measured)](#interval-scale-and-cost-measured)
- [Fixes compared (measured)](#fixes-compared-measured)
- [Three dimensions (derived and conjectured)](#three-dimensions-derived-and-conjectured)
- [Limits](#limits)

## Reference and setup

- **Exact reference:** segments are clipped to the annulus `a ≤ |y − p| ≤ b` (at most two pieces each); the angles of the piece endpoints split the circle into cells with one nearest piece each, so one ray per cell gives `L[a,b](p, ω)` and `β[a,b](p, ω)` exactly as step functions of angle, and bin means and fluence follow by exact integration. Checked against a lone segment's fluence, the `2πc` inside and `πc` just outside a closed emitter, traced rays and dense ray averages.
- **Notation:** `Δsₙ = 2ⁿΔs₀`, `Mₙ = N₀Kⁿ` bins of width `2π/Mₙ`, hand-overs `tₙ = t₀lⁿ`, `s` rays per bin, overlap `o` in upper spacings, `t_eq = N₀Δs₀/2π` (5.09 at 32 directions, 1.27 at 8).
- **Scenes** on a window `128·Δs₀` wide: lamp (a light two spacings long in empty space), wall (long light, thin occluding wall), penumbra (small bright light, thin occluders at several distances), room (closed, ceiling lamp, two blocks), scatter (five small lights, eight boxes), skyline (blocks under a uniform sky). Every number is a mean over six random whole-spacing grid offsets.
- **Metrics:** relative RMSE of fluence `‖F̂ − F‖₂/(√P·F̄)` (primary), and a display RMSE after Reinhard tone mapping at mean 0.18. **Cost** per unit area: rays, ray steps at a fixed step of `Δs₀`, and mip steps (cascade `n` marches at its own spacing). The bilinear fix traces `4K` rays per bin below the top cascade; the top cascade counts to the window's diagonal.

## Error decomposition

- Merging cascade `n` with an exact upper cascade, `R̃ₙ = Ĵ + β̂X̂`, errs by exactly four parts (derived): **angular radiance** `Ĵ − J̄`, **angular transmittance** `(β̂ − β̄)X̂`, **spatial** `β̄(X̂ − X̄)` (reading the upper cascade at other probes: merge parallax), and **correlation** `β̄X̄ − (Rₙ − J̄)`, minus the within-bin covariance of transmittance and far radiance. The first, second and fourth vanish as bins narrow or rays multiply; the spatial term vanishes as probes move together.
- The merge is linear, so full errors carry down: `R̂ₙ − Rₙ = (R̃ₙ − Rₙ) + β̂ₙX̂[R̂ₙ₊₁ − Rₙ₊₁]`; with the gather term (bilinear interpolation of exact probe fluence) the image error is an exact sum of per-cascade local terms.
- The spatial term splits into a **seam** part along each ray (stretches seen by neither cascade or by both) and a **parallax** part across it.
- **Where the error is (measured):** with 32 directions at `t₀ = 1` the spatial term dominates every scene (0.19 to 0.52 of mean fluence, against at most 0.17 for angular radiance), in bands where cascades meet. With 4 directions branching by 4 (`t₀ = √2`) angular radiance dominates the small-light scenes (lamp 0.61, penumbra 0.54, scatter 0.43). At the equal-error `t₀` the spatial term falls 2.4 to 4.4× and angular radiance rises 2.2 to 2.7×. Angular transmittance and correlation stay at or below 0.05 at 32 directions. Halving cascade 0's resolution makes the gather term the largest near small lights (lamp 0.47, scatter 0.38). The cascade 0 merge holds 52 to 64% of the squared spatial error and the next merge 27 to 30%; the angular error is spread over cascades.

## Resolution against distance (derived)

- At distance `D` the gap between ray ends is `g = D·Δωₙ/s` and the probe spacing `Δsₙ`; at the end of cascade `n`, `g/Δsₙ = (t₀/(s·t_eq))·(l/2K)ⁿ`, constant over cascades only when `l = 2K`.
- Under `K = 2, l = 4`: `g(D) = (2π/(sN₀))·√(D·t₀)` and `Δs(D) = Δs₀·√(D/t₀)`. Both grow as `√D`, so `t₀` trades angular for spatial resolution at every distance at once, including the far field: at `N₀ = 32` a scene `181·Δs₀` across takes five cascades (top cascade 512 directions) at `t₀ = 1` and three (128 directions) at `t₀ = 16`.

## Small lights (derived and measured)

- **Aliasing law:** a light spanning `x = α·s/Δωₙ` ray spacings is hit by `⌊x⌋` or `⌈x⌉` rays, so the relative RMS error is `√(f(1−f))/x ≤ 1/(2x)` with `f = x − ⌊x⌋`; over a spread of `x` the mean of `f(1−f)` is 1/6, so the typical error is `0.41/x`. One gap wide errs up to 50%, two gaps (the Nyquist width) up to 25%, and below 10% needs five gaps (derived).
- **Resolvable distance:** a light of width `w` spans one gap out to `D_max = (w·s·N₀/2π)²/t₀`, quadratic in `N₀` and `s`, inverse in `t₀`: 104·Δs₀ for `w = 2` at `N₀ = 32, t₀ = 1`, and 20·Δs₀ at `t_eq`. Beyond it the error grows as `√(D/D_max)`. The light-size rule (ray-end gap `2π·t₀/N₀`) is the case `D = t₀` (derived).
- Probe errors follow the law within 0.69 to 1.23× in every bin with 30+ probes, for lights 0.5 to 8 spacings wide, `t₀` 1 and 5.09, `s` 1 and 4. Image error around twelve lamps collapses on `D/D_max`: beyond `0.3·D_max` one power law, `0.32·(D/D_max)^0.42`, fits 84 distance bands within ×1.32; closer, ringing of the spatial term keeps it at 0.1 to 0.3 (measured).
- **Sizing rule:** an error below about 10% at the farthest distance `D` a light must be seen from needs `s·N₀ ≥ 10π·√(D·t₀)/w`.

## Seams and overlap (derived and measured)

- On cell-centred grids with spacing ×2 per cascade, a lower probe's four upper probes lie at 0.35, 0.79, 0.79 and 1.06 upper spacings with bilinear weights 9/16, 3/16, 3/16, 1/16. Without overlap the mean stretch seen by neither cascade is `Σw|δ|/π = 0.562/π = 0.179` upper spacings, and the same length is seen by both. An overlap of `0.75·√2 = 1.06` upper spacings (the farthest upper probe) closes every gap; `o = 0.5` leaves 16%. The double-seen length is the unseen length plus `o`, growing one for one with overlap (derived).
- A double-seen surface survives the merge only where a bin is partly covered: a fraction `c` covered by radiance `L_S` over background `L_B` errs by `c(1−c)(L_S − L_B)`. Overlap therefore trades leaks through thin occluders for double counting at silhouettes, worst for small bright lights (derived).
- **Most spatial error is parallax, not seams (measured):** at cascade 0 the unseen part is 1.9 to 2.2× smaller than parallax in wall, 3.7 to 6.5× in room and penumbra, over 40× in scatter. The unseen part falls with overlap as the law predicts and vanishes at 1.06 at `t₀ = 5.09`; at `t₀ = 1` it falls more slowly in room and scatter, where the gap is as long as cascade 0's whole interval. The double-seen part grows 2.5 to 4.4× by 1.06 upper spacings.

## The cascade 0 interval (derived and measured)

- **Balance model (derived):** with squared error `A(D)·g² + B(D)·Δs²` summed over distance under `K = 2, l = 4`, `E²(t₀) = Ā·t₀/t_eq + B̄·t_eq/t₀`, optimal at `t₀* = t_eq·√(B̄/Ā)` where the angular and spatial parts are equal. Equal error is optimal only for a scene that weights aliasing and blur alike. For `E² = a·t₀^α + b·t₀^(−β)` the optimum is `(β/α)^(1/(α+β))` times the crossing: 0.63 for aliasing (`α = 1`) against a blurred step edge (`β = 1/2`). `s` rays per bin cut the aliasing weight by `s²` and move the optimum up by `s`.
- **Measured optima** (`K = 2, l = 4`, `t₀` 0.5 to 16 spacings, parabola in `log t₀`):

| Scene | N₀ = 8, s = 1 | N₀ = 8, s = 4 | N₀ = 32, s = 1 | Crossing, N₀ = 32 | t₀*/t_eq, N₀ = 32 |
|---|---|---|---|---|---|
| lamp | ≤ 0.5 | 1.58 | 1.59 | 2.06 | 0.31 |
| wall | 5.73 | 11.49 | 12.95 | 8.97 | 2.54 |
| penumbra | 1.64 | 5.35 | 5.71 | 5.59 | 1.12 |
| room | 3.16 | 7.71 | 12.69 | 7.54 | 2.49 |
| scatter | ≤ 0.5 | 2.01 | 2.06 | 1.96 | 0.40 |
| skyline | 2.40 | 3.54 | 6.77 | 4.33 | 1.33 |

- The optimum spans a factor of 8 between scenes: about `0.3·t_eq` where the light comes from small sources, about `2.5·t_eq` where large emitters light the scene and the error sits in shadows. The small-light scenes reproduce the 2D finding that `t₀ = 1` looks best at 32 directions; the same short interval costs the other scenes 2.1 to 3.5× their optimal error.
- The model holds: angular terms grow at log-log slopes +0.28 to +0.55 (model +0.5), spatial terms fall at −0.56 to −0.94 (−0.5 for a blur, −1 in the smooth skyline); optima lie 0.77 to 1.68× the crossing. From 8 to 32 directions the optimum grows 2.3 to 4.0× (model 4).
- **Rays, not bins:** 8 directions with 4 rays per bin match the optimum of 32 directions within 3% in lamp and scatter and 6% in penumbra, with matching error curves, as Split RC's remark that several rays per direction favour longer intervals anticipated. Going from 1 to 4 rays moves the optimum 3.3× in penumbra and at least 3.2 and 4.0× in lamp and scatter (model 4), and 1.5 to 2.4× in the others, where bin-mean blur adds to the angular error. The equal-error rule has no term for `s`.
- **Equal error is the robust choice:** at 32 directions `t₀ = 5.66`, the grid point nearest `t_eq`, keeps every scene within 1.42× its optimal error; `t₀ = 1` allows 3.48×. The minimax `t₀` is 2 spacings at 8 directions (1.6·t_eq) and 4 with four rays per bin. By display RMSE the optima are lower, by up to 2.2× in the small-light scenes, and the minimax is 4 spacings (within 1.76×).

## Interval scale and cost (measured)

- At each scene's best `t₀`, with `K = 2` scales from 2.5 to 4 come within 3% in mean error; `l = 2` is 9% worse and `l = 8` 18% worse. The ×3 to ×3.5 found best by eye sit in this shallow minimum with the equal-error `l = 4`. With `K = 4` the scale changes the mean error by at most 7% between 3 and 8. Once `t₀` is tuned, `l` matters little.
- Over 122 settings (the `l` sweep, the rule settings and 48 random settings of `K, l, N₀, t₀, s`, overlap and merge) the rule settings lie near the Pareto front: equal error at 8 directions on it, the 2x/4x scheme with the diagonal `t₀` within 1.03× by rays and 1.15× by mip steps, equal error at 32 directions within 1.08×; `t₀ = 1` at 32 directions is on the front by mip steps (a short interval is cheap to march) but 1.59× above it by rays. Along the front error falls about as rays^−0.5, from 0.33 at 16 rays per unit area to 0.041 at 832. The two lowest errors, 0.067 and 0.041, use the bilinear fix with 2 or 4 rays per bin; at moderate error the front spends rays on directions and rays per bin instead.

## Fixes compared (measured)

Relative RMSE at `N₀ = 32, K = 2, l = 4`, with cost in mip steps relative to vanilla:

| Scene | vanilla, t₀ = 1 | overlap 0.5 | overlap 1.06 | bilinear fix | vanilla, t₀ = 5.09 | overlap 0.5 | overlap 1.06 | bilinear fix |
|---|---|---|---|---|---|---|---|---|
| lamp | 0.418 | 0.413 | 0.650 | 0.198 | 0.423 | 0.435 | 0.494 | 0.127 |
| wall | 0.196 | 0.069 | 0.060 | 0.062 | 0.085 | 0.039 | 0.027 | 0.015 |
| penumbra | 0.543 | 0.300 | 0.430 | 0.262 | 0.258 | 0.190 | 0.206 | 0.087 |
| room | 0.253 | 0.128 | 0.119 | 0.138 | 0.099 | 0.049 | 0.049 | 0.028 |
| scatter | 0.264 | 0.307 | 0.475 | 0.160 | 0.291 | 0.309 | 0.356 | 0.119 |
| skyline | 0.021 | 0.026 | 0.030 | 0.025 | 0.008 | 0.008 | 0.009 | 0.006 |
| mip steps | 1 | 1.51 | 2.07 | 7.14 | 1 | 1.12 | 1.26 | 7.24 |

- Overlap 1.06 cuts wall and room error 2.0 to 3.3× (closed gaps) and raises lamp and scatter error up to 1.8× (double counting): the "fixes leaks, not ringing" trade, measured.
- Overlap is cheap at `t_eq` (+12 to 26% mip steps) but costs +51 to 107% at `t₀ = 1`, where 1.06 upper spacings is twice the cascade 0 interval.
- The bilinear fix lowers the error everywhere except skyline at `t₀ = 1`; at `t_eq` it is the lowest for all six scenes (3.3× below vanilla in the lamp, 5.7× in wall) at about 7.5× the rays and 7.2× the mip steps of vanilla with one ray per bin.

## Three dimensions (derived and conjectured)

- With `K = 4, l = 4` a bin's angular width halves per cascade while the spacing doubles, so both resolutions grow as `√D` and `t₀` trades one for the other as in 2D; the equal-error interval is `Δs₀·√(N₀/4π)`, 1.60 spacings at 32 directions (derived).
- With `s` rays spread over each cell the gap is `t·Δω/√s`, so a light of width `w` spans one gap out to `D_max = w²·s·N₀/(4π·t₀)`, linear rather than quadratic in `N₀`: 6.4 spacings for a light two spacings wide at 32 directions and the equal-error `t₀` (derived).
- Trilinear reads from cell-centred grids: mean unseen seam `Σw|δ|/4 = 0.706/4 = 0.177` upper spacings, closed by an overlap of `0.75·√3 = 1.30` (against the diagonal `√3`) (derived).
- A light's outline on the sphere crosses many ray cells, so the hit count is conjectured to fluctuate with the perimeter, as lattice-point counts do, giving relative error `∝ x^(−3/4)` rather than `x^(−1)` (conjectured, untested).
- Whether the optimal `t₀` spreads as widely across 3D scenes needs a 3D reference.

## Limits

Flatland, emission and absorption only, fluence without a cosine; six scenes on one window; an exact tracer, so tracer errors (voxels, distance fields, depth buffers) are absent and cost is counted in rays and steps, not GPU time; fixed stratified directions, so jitter and temporal accumulation (which turn aliasing into noise) are not modelled; RMSE metrics, so whether aliasing looks worse than blur is neither confirmed nor refuted; the Pareto front samples a seven-dimensional space with 122 settings.
