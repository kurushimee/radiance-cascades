# Several Bounces of Radiance Cascades in One Frame

| | |
|---|---|
| Author | kurushimee (independent researcher) |
| Date | 2026-10 |
| Kind | Paper, original research with code: exact flatland radiosity and a 3D Monte Carlo reference, derivations with assert-based checks, seeded experiments |
| Link | [paper.pdf](../../papers/03_bounces_one_frame/paper.pdf), source [paper.md](../../papers/03_bounces_one_frame/paper.md); labs in [papers/lab/radiosity.py](../../papers/lab/radiosity.py) and [papers/lab/radiosity3d.py](../../papers/lab/radiosity3d.py) |
| Related | [2026_kurushimee_rc_error_model.md](2026_kurushimee_rc_error_model.md), [2026_kurushimee_merging_3d.md](2026_kurushimee_merging_3d.md), [2026_light_transport_alternatives.md](2026_light_transport_alternatives.md), [2026_holographic_rc.md](2026_holographic_rc.md) |

The first measurement of multi-bounce RC within one frame. With geometry fixed, an RC solve is a linear map from surface radiance to irradiance; storing each ray's hit lets a re-merge apply it again with no rays, so the infinite-bounce answer is a linear fixed point reached in a few passes. The solve's estimate of the form-factor matrix is measured against exact radiosity in flatland and a Monte Carlo reference in a 3D voxel lab. The central finding is the leak deficit: furnace-exact merges still read light from behind walls, that loss acts as an albedo loss on the dominant eigenvalue, and it alone compounds over bounces.

## Contents

- [Lab and setup](#lab-and-setup)
- [The frozen solve (derived)](#the-frozen-solve-derived)
- [Furnace and leak deficit (derived)](#furnace-and-leak-deficit-derived)
- [How the error carries through bounces (derived)](#how-the-error-carries-through-bounces-derived)
- [Iterations (derived and measured)](#iterations-derived-and-measured)
- [Deficit and eigenvalues in flatland (measured)](#deficit-and-eigenvalues-in-flatland-measured)
- [Albedo and bounces in flatland (measured)](#albedo-and-bounces-in-flatland-measured)
- [Coarse later bounces (measured)](#coarse-later-bounces-measured)
- [Bounces in 3D (measured)](#bounces-in-3d-measured)
- [Limits](#limits)

## Lab and setup

- **Radiosity form:** patch radiance `L = E + P(F·L + f·s)`, `P = diag(ρ)`, `F_ij` the share of patch `i`'s cosine-weighted view taken by patch `j`, `f_i` the sky's share, `s` the sky radiance. Irradiance at a collocation point is `c(F·L + f·s)`, `c = π` in 3D and 2 in flatland (the cosine over a half circle). Bounce operator `K = PF`, dominant eigenvalue `μ`, left and right Perron vectors `u`, `v`. In a closed region each row of `F` sums to one over the region.
- **Flatland:** segments in a `128 × 128` window on a 4-unit lattice; each receiving side cut into unit patches, collocation points half a unit off the wall on cascade 0 probes. The exact reference sweeps angles around each collocation point for the nearest patch and integrates the cosine per angular piece. RC: `N₀ = 32` doubling per level, intervals ×4, spacing ×2, `t₀ = t_eq = N₀Δs₀/2π ≈ 5.09`, four cascades; vanilla and the bilinear fix; six placements moved by multiples of 4, results averaged. Scenes: a closed room (hanging lamp, free-standing wall, shelf), two rooms joined by an opening above a partition, an open half-roofed canyon under a unit sky. Lamps emit 1 and reflect nothing.
- **Voxels:** `32³`; every exposed face a unit patch, collocation point at the centre of the empty voxel in front of it (a cascade 0 probe). `N₀ = 32` on the turned equal-area map, directions and intervals ×4, spacing ×2, `t₀ = t_eq = √(N₀/4π) ≈ 1.60`; vanilla, self test, few steps (depth reprojection with the self test at hand-overs 0 and 1, sphere fix at 2) and trilinear fix, plus vanilla and the trilinear fix at `N₀ = 128`. Hits store voxel and face; an upper ray starting inside a solid voxel reads the mean of its exposed faces (or the nearest voxel's). Reference: `2¹⁴` stratified cosine rays per collocation point; two seeds differ by 0.16% to 0.19% in the rooms at albedo 0.9 and 0.01% in the courtyard. Scenes: a room with 1-voxel walls, panel and pillar; the same with 2-voxel walls; two rooms joined by a door in a 1-voxel partition; a courtyard open to a unit sky above and at both ends. Closed scenes have a `10 × 10` ceiling light.
- Both references share the estimate's patches and collocation points, so the errors are those of RC's operator at one patch resolution. Errors are relative RMS over the receivers normalized by the exact mean; bias is the ratio of means less one.

## The frozen solve (derived)

- With hit records and merge weights fixed, the solve computes `c(F̂·L + f̂·s)` for a fixed nonnegative `F̂`; all bounces are `L̂ = (I − K̂)⁻¹(E + P·f̂·s)`, `K̂ = PF̂`.
- **Pass:** shade every stored hit with the current `L`, merge, gather. No rays; cost one read per stored hit plus the merge's reads; memory one hit record per ray texel (patch index, or voxel and face), the size of a one-channel cascade texture. A merge that tests visibility can store its decisions or re-read the depths. Re-merges reproduce the solve to `10⁻¹²` in flatland and to rounding in 3D.
- **Needs:** a radiance value at every surface a ray can hit (dense or clipmap grids, surface atlases; not screen-space probes over visible surfaces) and geometry fixed between passes.

## Furnace and leak deficit (derived)

- **Furnace:** if every merge's weights sum to one and the gather's cosine weights sum to `c`, uniform unit radiance (sky included) gives 1 in every texel by induction from the top cascade, so `F̂·1 + f̂ = 1` for every such merge.
- **Leak deficit:** with unit radiance on a closed region's patches and zero on the far sides of its walls, `δ_i = 1 − Σ_{j∈region} F̂_ij`, the share of receiver `i`'s view the merge reads from outside. It is the estimate's defect in the enclosure closure of exact form factors, and acts as light leaving the room. One re-merge measures it.
- **Eigenvalue shift:** for `K̂ = (I − diag δ)K`, first-order perturbation gives `μ̂ ≈ μ(1 − Σu_iv_iδ_i / Σu_iv_i)`: an albedo loss weighted where the dominant mode lives (checked to second order on random matrices).
- **Bilinear fix's arcs (flatland):** a fixed ray ends at an upper probe's interval start in the child bin's direction; if that texel misses, it reads its own upper probes from the same distance in its children's directions, a quarter of a child bin away. The chain is continuous except an arc `a_c = t_c·π/(2N_c₊₁) = t₀·π·2ᶜ/(4N₀)` at each hand-over into a fixed cascade: `Δs₀/8` and `Δs₀/4` at 5.1 and 20.4 spacings at `t_eq` with four cascades; `Δs₀/40` to `Δs₀/10` at `t_eq/5` with five. Light leaves a closed region only where a wall crosses an arc.

## How the error carries through bounces (derived)

- **Converged error:** `L̂ − L = (I − K̂)⁻¹(K̂ − K)[L; s]`, one pass's error on the exact solution carried through every bounce of the estimate: the operator-perturbation identity of Arvo, Torrance and Smits (1994).
- **Dominant mode:** `uᵀ(L̂ − L) = uᵀ(K̂ − K)[L̂; s]/(1 − μ)`; a pass error along `u` is amplified by up to `1/(1 − μ)`, ten at `μ = 0.9`, one orthogonal to `u` is not.
- **Mean and contrast:** for a receiver in a closed region and any scalar `L̄`, `((F̂ − F)L)_i = ((F̂ − F)(L − L̄·1_region))_i − L̄·δ_i`. The contrast part vanishes for a uniform field and has both signs; the deficit part has one sign, scales with the mean and lies largely along the positive `u`. Each bounce averages over the hemisphere, so later bounces lose contrast while the mean persists (inference): a merge with a deficit gains error with albedo and bounces, a merge without one has its largest error at the first bounce. In the first bounce the field is the lights alone, whose mean is small, so the deficit hardly shows there.
- **Bias gain (first order):** the light reflected at least once, `R = L − E = (I − K)⁻¹F₁` with first bounce `F₁ = K[E; s]`, so `uᵀR = uᵀF₁/(1 − μ)` exactly. Taking the estimate's Perron vector close to `u`: `uᵀR̂/uᵀR ≈ (uᵀF̂₁/uᵀF₁)·(1 − μ)/(1 − μ̂)`. At high albedo the converged bias follows from the first bounce's `u`-weighted bias and the two eigenvalues. It fails where the eigenvector moves, which first-order theory scales with the operator's error over the gap to the second eigenvalue.

## Iterations (derived and measured)

- **Plain:** `x_n = E + K̂x_{n−1}`, error `∝ μ̂ⁿ`; cutting the remaining light to 1% takes 28 passes at `μ̂ = 0.85`.
- **Ambient term** (progressive radiosity, Cohen et al. 1988): add `ρ_i·⟨d_n⟩/(1 − ρ̄)`, `d_n = x_n − x_{n−1}`, means over the scene's surfaces. Exact mean with reciprocal form factors, one albedo and a closed scene. It assumes the remaining light is uniform and decays at `ρ̄`.
- **Geometric tail:** `x_n + d_n·r_n/(1 − r_n)`, `r_n = Σd_n/Σd_{n−1}`. As `d_n → κμ̂ⁿv̂` and `r_n → μ̂` it removes the dominant mode whatever its shape and rate: Aitken's process on the bounce series with one ratio for all patches, two global sums per pass. The ambient term errs in shape (uniform, not `v̂`) and rate (`ρ̄` ignores what emitters absorb, the sky takes and the deficit removes, all of which put `μ̂` below `ρ̄`).
- **GMRES** on `(I − K̂)L = E + Pf̂s` from `L = E`: the first pass gives the residual and the first bounce, each later pass one Krylov vector; the estimate is the residual minimizer plus one free bounce; pass `k` adds `k` inner products and one stored vector. Anderson acceleration with full memory is essentially GMRES on a linear problem (Walker and Ni 2011).
- **Passes needed** = passes until the iterate is as close to the frozen fixed point as that is to the reference. The count depends on that floor, so it compares methods for one merge, not merges.
- **Flatland, albedo 0.9 (measured):** for the bilinear fix (floor 0.22% to 0.51%) plain needs 21 to 34 passes, the ambient term 22 to 27, the tail 7 to 18, GMRES 6 to 8. For vanilla (floor 5.5% to 16%) every method needs 2 to 12. The ambient term helps in the closed rooms and needs more passes than plain in the open canyon (11.7 against 9 for vanilla, 23.3 against 21.3 for the fix), where for the fix it adds 3.0 times the light remaining along the dominant mode. The tail is slowest in two rooms, whose exact second eigenvalue, 0.735, is the highest of the three scenes (room 0.668, canyon 0.475): once the tail removes the dominant mode, the second remains.
- **3D (measured):** the tail and GMRES need 2 to 5 passes everywhere; plain 3 to 18 where the floor is high and more than 30 for the trilinear fix at 128 directions in the thick room, the most accurate case (floor 2.2%).

## Deficit and eigenvalues in flatland (measured)

At albedo 0.9; stored hits 1.15M for vanilla, 8.30M for the bilinear fix:

| Scene | Merge | Deficit mean / max | `μ` | `μ̂` | shift predicts | Converged bias | gain predicts |
|---|---|---|---|---|---|---|---|
| room | vanilla | 2.75% / 11.2% | 0.8465 | 0.8238 | 0.8223 | −15.9% | −16.3% |
| room | bilinear fix | ≈ 0 | 0.8465 | 0.8467 | 0.8465 | −0.19% | −0.29% |
| two rooms | vanilla | 2.68% / 11.2% | 0.8606 | 0.8338 | 0.8369 | −11.9% | −15.3% |
| two rooms | bilinear fix | ≈ 0 | 0.8606 | 0.8608 | 0.8606 | −0.36% | −0.31% |
| canyon | vanilla | – | 0.7488 | 0.7157 | – | +4.72% | +4.80% |
| canyon | bilinear fix | – | 0.7488 | 0.7495 | – | −0.16% | −0.15% |

- The eigenvalue shift is predicted within 0.0031; the gain predicts the bias within 0.4 points except vanilla in two rooms, where the exact second eigenvalue is closest to the first.
- The bilinear fix's deficit is about `10⁻¹⁶` at `t_eq` (no wall crosses its arcs in these placements) and 0.03% to 0.18% at other `t₀`, a twelfth to a hundredth of vanilla's.
- Mean deficit against `t₀` (0.2, 0.5, 1, 2 `t_eq`) and with overlap 0.5 upper spacings at `t_eq`: vanilla room 21.0%, 4.21%, 2.75%, 1.70%, 1.06%; vanilla two rooms 21.2%, 3.45%, 2.68%, 1.18%, 0.99%; fix room 0.18%, 0.03%, 0, 0.13%, 0; fix two rooms 0.17%, 0.03%, 0, 0.12%, 0. Only light a merge hands over can leak: a longer `t₀` resolves more of the view with cascade 0's own rays, and overlap starts each upper interval before the lower one ends (inference).

## Albedo and bounces in flatland (measured)

- **Room, vanilla:** first bounce 10.0% (bias −3.74%); converged 8.77%, 8.34%, 9.28%, 16.1% at albedo 0.3, 0.5, 0.7, 0.9, bias −4.74% to −15.9%; amplification (converged error over one pass's error on the exact solution) 1.09 to 4.37, share along the dominant mode 0.48 to 0.98, against `1/(1 − μ̂) = 5.7`.
- **Room, bilinear fix:** first bounce 2.81% (−0.44%); converged 1.99%, 1.46%, 0.94%, 0.40%; amplification 1.02 to 1.35, dominant share 0.16 to 0.53.
- **Two rooms:** vanilla first bounce 7.50% with bias only −0.41%, converged 6.69% to 12.9% with bias −1.20% to −11.9% (amplification 1.08 to 3.47); the fix 2.60%, converged 1.90% to 0.51%.
- **Canyon:** vanilla reads sky where the exact view sees the canyon's walls; with its view still summing to one, its first bounce is 9.61% too bright and `μ̂` too low. The errors oppose: bias +10.0% at 0.3 to +4.72% at 0.9, error 13.7% to 5.49% (first bounce 14.5%). The fix: 1.21% first, converged 0.89% to 0.22%.
- **Per bounce at albedo 0.9:** vanilla's error after `n` bounces against `n` exact bounces falls from 10.0% to 8.3% at four bounces, then grows to 14.0% at sixteen in the room (7.5% to 11.3% in two rooms); the fix's falls from 2.81% to 0.45% (2.60% to 0.57%).

## Coarse later bounces (measured)

First bounce from the full solve, every later one from a frozen solve with cascade 0 spacing 2 or 4 (a quarter or a sixteenth of the stored hits: 2.30M and 0.53M for the fix, 0.33M and 0.09M for vanilla), collocation points half that spacing off the walls and interpolated:

- **Bilinear fix:** the second bounce's light is within 1.7% of exact (0.983 to 1.003), but its error is 1.5 to 3.4 times the re-merge's (room 1.91% → 2.95%, 4.63%), and the converged error at albedo 0.9 grows 6 to 14 times (room 0.40% → 2.87%, 4.51%; two rooms 0.51% → 3.04%, 5.19%; canyon 0.22% → 2.02%, 3.10%). At albedo 0.5 the room grows 1.3 and 1.6 times (1.46% → 1.92%, 2.40%).
- **Vanilla:** the converged error changes by −2% to +41% in the closed scenes (room 16.1% → 19.2%, 22.7% at 0.9); in the canyon spacing 4 lowers it from 5.49% to 3.50% by an offsetting error.
- Negative result for the hypothesis that later bounces need less resolution: every later bounce carries the coarse solve's error. The full re-merge already avoids tracing, so a coarse solve saves only reads per pass.

## Bounces in 3D (measured)

At 32 directions unless marked; deficit in percent; bias at albedo 0.9 with the gain's prediction:

| Scene | Merge | Deficit | `μ` / `μ̂` / predicted | First bounce (bias) | Converged at 0.3, 0.6, 0.9 (bias at 0.9) | Gain predicts |
|---|---|---|---|---|---|---|
| room | vanilla | 13.4 | 0.884 / 0.767 / 0.766 | 27.9% (−16.6%) | 26.0%, 31.5%, 58.9% (−58.9%) | −58.2% |
| room | self test | 7.43 | 0.884 / 0.819 / 0.818 | 24.4% (−12.0%) | 20.7%, 22.5%, 44.2% (−44.1%) | −43.5% |
| room | few steps | 4.67 | 0.884 / 0.844 / 0.843 | 25.9% (−12.6%) | 21.2%, 20.8%, 36.5% (−36.4%) | −34.9% |
| room | trilinear fix | 2.28 | 0.884 / 0.865 / 0.864 | 27.3% (−10.6%) | 20.3%, 16.8%, 24.4% (−24.3%) | −22.6% |
| room | vanilla, 128 | 5.38 | 0.884 / 0.837 / 0.837 | 19.0% (−7.7%) | 15.7%, 16.5%, 35.0% (−34.9%) | −34.1% |
| room | trilinear fix, 128 | 1.05 | 0.884 / 0.875 / 0.875 | 10.9% (−2.8%) | 7.8%, 6.0%, 10.3% (−10.2%) | −9.5% |
| thick room | vanilla | 7.11 | 0.881 / 0.821 / 0.819 | 35.2% (−15.8%) | 27.9%, 26.4%, 44.5% (−44.4%) | −43.7% |
| thick room | self test | 3.30 | 0.881 / 0.853 / 0.851 | 28.4% (−8.5%) | 21.0%, 16.8%, 27.0% (−26.8%) | −25.9% |
| thick room | few steps | 1.29 | 0.881 / 0.872 / 0.870 | 30.1% (−10.9%) | 21.9%, 16.6%, 19.0% (−18.8%) | −17.1% |
| thick room | trilinear fix | 0.18 | 0.881 / 0.882 / 0.879 | 35.5% (−15.0%) | 26.1%, 19.1%, 14.7% (−14.4%) | −13.8% |
| thick room | vanilla, 128 | 2.57 | 0.881 / 0.860 / 0.859 | 17.9% (−6.1%) | 13.5%, 11.5%, 21.1% (−21.0%) | −20.4% |
| thick room | trilinear fix, 128 | 0.00 | 0.881 / 0.881 / 0.881 | 12.4% (−2.0%) | 8.4%, 4.9%, 2.2% (−1.9%) | −1.7% |
| two rooms | vanilla | 10.6 | 0.890 / 0.797 / 0.797 | 56.5% (−18.9%) | 47.9%, 47.8%, 65.9% (−53.7%) | −55.0% |
| two rooms | self test | 6.02 | 0.890 / 0.837 / 0.838 | 44.4% (−7.8%) | 34.0%, 28.9%, 43.8% (−36.4%) | −37.3% |
| two rooms | few steps | 3.94 | 0.890 / 0.855 / 0.856 | 47.0% (−12.5%) | 37.0%, 31.5%, 40.2% (−32.8%) | −32.8% |
| two rooms | trilinear fix | 1.85 | 0.890 / 0.875 / 0.874 | 41.8% (−13.4%) | 31.1%, 25.2%, 28.1% (−23.5%) | −23.6% |
| courtyard | vanilla | – | 0.420 / 0.390 / – | 4.9% (−1.7%) | 4.4%, 5.0%, 7.2% (−6.5%) | −5.6% |
| courtyard | self test | – | 0.420 / 0.404 / – | 4.0% (−0.1%) | 2.9%, 2.6%, 3.7% (−3.1%) | −2.1% |
| courtyard | few steps | – | 0.420 / 0.413 / – | 4.1% (−1.0%) | 3.2%, 2.9%, 3.6% (−3.0%) | −1.6% |
| courtyard | trilinear fix | – | 0.420 / 0.462 / – | 9.1% (−8.1%) | 7.7%, 6.1%, 3.6% (−3.4%) | −1.0% |

- **Eigenvalues:** the shift predicts every closed scene within 0.003, at deficits up to 13.4%; the gain predicts the converged bias within 1.7 points in the closed scenes and 2.4 in the courtyard.
- **The deficit sets the growth:** the first bounce is 7.8% to 18.9% too dark at 32 directions for every merge, independent of the deficit (the trilinear fix in the thick room, deficit 0.18%, has −15.0%); at albedo 0.9 the merges order by deficit in every closed scene. The thick room's trilinear fix keeps its bias at −15.0%, −15.0%, −14.4% while its error falls from 35.5% to 14.7%. At 128 directions the first-bounce darkening falls to 2.0% to 7.7%; the thick room's fix, with no measurable deficit, keeps −2.0% at every albedo while its error falls from 12.4% to 2.2%. With 1-voxel walls the fix still misses 1.05% at 128 directions, enough to take its bias from −2.8% to −10.2%.
- **Gain factor** `(1 − μ)/(1 − μ̂)`: 0.50 for vanilla in the room (the deficit halves the converged reflected light on top of the first bounce's darkening), 0.86 for the trilinear fix, 1.00 for the fix at 128 directions in the thick room.
- **Courtyard** (open, `μ = 0.42`): the trilinear fix reads the courtyard's surfaces where the exact view sees sky, so its sky-lit first bounce is 8.1% dark and `μ̂ = 0.462` high; the errors offset and its bias falls from −8.1% to −3.4%. Vanilla's `μ̂` falls to 0.390 and its bias grows from −1.7% to −6.5%.
- **Cost** (rays = stored hits; solve reads + voxel steps against one pass's reads): vanilla 2.7M rays, 10.9M steps, 51M reads per solve, 53M per pass; self test 101M / 104M; few steps 274M / 276M (re-merges re-read the depths they test); trilinear fix 18.9M rays, 92.9M steps (8.5 times vanilla's), 48M / 67M; at 128 directions vanilla 11.0M rays, 52.8M steps, 189M / 200M, the fix 75.6M, 438.6M, 186M / 261M. At equal cost per step and read a pass costs 0.83 to 0.88 of a vanilla solve, 0.93 of a self test solve, 0.97 of a few-steps solve and 0.42 to 0.50 of a trilinear fix solve; at ten reads per step a vanilla pass costs 0.33 of a solve.

## Limits

Small scenes (`128²` flatland, `32³` voxels), axis-aligned walls, one uniform albedo, diffuse surfaces; collocation points on cascade 0 probes, so the gather to shading points adds no error; references share the estimate's patches, so errors are RC's operator error at one patch resolution; the 3D reference is Monte Carlo (noise ≤ 0.2%); cost in reads and voxel steps, not time; the cause of the 3D first-bounce darkening, which falls from 32 to 128 directions, is not separated from the merges' other errors.
