# RC for sampling and guiding: Reservoir Cascades

Ivan You's Reservoir Cascades keeps RC's discretization and rewrites the merge between levels as resampled importance sampling, tested in 2D flatland: the argument, notation, method, theory, experiments, limits and code. Its comparison with RCPG and vlam, and the connections and single-frame assessment for both are in [RC for sampling and guiding](rc_for_sampling_and_guiding.md).

## Contents

- [Reservoir Cascades](#reservoir-cascades)
  - [The argument](#the-argument)
  - [Notation](#notation)
  - [GRIS in brief](#gris-in-brief)
  - [Method](#method)
  - [Theory](#theory)
  - [Experiments](#experiments)
  - [Limits and design axes](#limits-and-design-axes)
  - [Code](#code)

## Reservoir Cascades

Ivan You's preprint "Reservoir Cascades: Principled Multi-Scale Sample Reuse by Resampling Radiance Cascade Merges" is dated 2026-07-23 ([notes](../sources/2026_you_reservoir_cascades.md)). Version 2 (`reservoir-cascades-preprint-v2.pdf`, 10 pages) is at https://doi.org/10.5281/zenodo.21520422, under the concept DOI 10.5281/zenodo.21506521; the Zenodo record holds only the PDF. The code is at https://github.com/ivanyou028/reservoir-cascades (MIT, read at commit 15b4557). The paper tests three 2D scenes with a CPU oracle and a WebGPU build.

### The argument

RC merges levels by deterministic bilinear interpolation, which asserts that a parent probe's value equals the child's. The paper traces four biases to that assertion, none of which more samples remove: light leaks through thin occluders, ringing from deterministic ray placement, a per-level angular resolution ceiling that destroys small bright emitters, and a visibility-radiance factorization error ([notes](../sources/2026_you_reservoir_cascades.md#1-introduction)).

ReSTIR-family estimators (Bitterli et al. 2020, Ouyang et al. 2021, Lin et al. 2022) reuse samples across pixels and frames with resampled importance sampling and proper weights, so their structural error shows up as variance. The paper calls their machinery ad hoc: reuse neighbourhoods are hand-tuned kernels, screen-space temporal reuse must handle motion vectors and disocclusion, and reuse under a visibility-free target carries a bias that the GRIS paper's correctness notes call real but leave unbounded.

The proposal keeps RC's discretization and demotes interpolation from an assertion to a proposal. The bilinear weights `β_q` leave the target, where errors cost bias, and enter the resampling weights of a GRIS merge over the four parent reservoirs, where errors cost variance. The paper says this one change turns each structural RC bias into variance that reuse can amortize, and that its theory explains why the cascade is the right structure for reuse, not tight constants.

It describes real-time GI as two largely separate lines, RC and the ReSTIR family, and frames RC through the penumbra condition: radiance from distance `r` varies spatially on a scale proportional to `r` and angularly on a scale proportional to `1/r`, a discrete analogue of the frequency analysis of light transport (Durand et al. 2005). The data structure has fixed cost, is geometry-agnostic and lives in world space.

The listed contributions:

1. **An estimator framework** in which vanilla RC is the exact degenerate case, verified bit-exactly against an independent RC implementation. The merge becomes GRIS-style resampling with per-parent reprojected bin lookup, per-level collapse of contribution weights (no products of `W` across levels), validation as renormalized visibility re-evaluation, and temporal reuse with sample re-evaluation and revival.
2. **Practice.** On canonical failure scenes, leaks drop to 0 to 11% of vanilla RC's leaked energy at an identical candidate-ray budget, with validation shadow rays counted; both acceptance bars clear at 20% or fewer extra rays; sub-bin emitters are recovered at 93 to 101% of reference energy; dynamic lights adapt in about 3 frames. An equal-budget flat world-space reuse control fails three ways (leak, validation collapse, weight-chain divergence) that the cascade closes structurally. A 120 fps WebGPU build reproduces the CPU oracle's metrics. The paper counts two failure modes and three negative results.
3. **Theory.** The merge is mapped onto GRIS condition by condition. Its coverage bias is a violation of GRIS's coverage condition, and its visibility gap is GRIS's "unoccluded target" problem, for which the paper gives an `O(ε_n)` bound that GRIS's analysis leaves open. A depth-uniform variance non-amplification theorem and an AR(1) model of the temporal reservoir follow. Two negative results are proved: bin-space parallax grows as `2^n` bins under ×4 angular branching, and per-frame interval jitter is incompatible with temporal reuse.

**Related work as the paper places it.** Sannikov introduced RC for real-time 2D and screen-space GI, shipped in Path of Exile 2; Osborne and Sannikov formalized the merge operator and penumbra criterion for non-LTE radiative transfer ([volumetric](volumetric_and_radiative_transfer.md)). Holographic RC takes a more deterministic route, single-shot transfer with no stochastic rays; the paper calls it orthogonal and names combining HRC far fields with its own stochastic near fields as future work ([HRC](holographic_rc.md)). The community "bilinear fix" reprojects parent rays through child ray endpoints ([artifacts](artifacts_and_fixes.md#the-bilinear-fix)), and the paper calls its reprojected bin lookup the RIS counterpart of that fix. Measured as a baseline, the fix removes only the misalignment part of the error: lit-region MAPE halves, but 95% of the leak remains, which the paper attributes to the merge's semantics ([notes](../sources/2026_you_reservoir_cascades.md#2-related-work)).

### Notation

All lengths are in pixels in a 2D scene ([notes](../sources/2026_you_reservoir_cascades.md#3-background-and-notation)):

- Level `n ∈ {0, …, N−1}` has probe spacing `s_n = s0·2^n`, with probes at `(i + 1/2)·s_n`.
- Angular bins number `B_n = B0·4^n`, each `2π/B_n` wide.
- The radial interval is `[t_n, t_{n+1})` with `t_n = t0·(4^n − 1)/3`, contiguous from 0, so interval `n` has length `t0·4^n`.
- Defaults: `s0 = 1`, `B0 = 4`, `t0 = 4`. The interval starts are then 0, 4, 20, 84, 340 and 1364 px (derived).

Along a ray, radiance decomposes recursively over intervals, `L_{≥n} = L_{[t_n, t_{n+1})} + V_{[t_n, t_{n+1})}·L_{≥n+1}`, the [merge operator](core_theory.md#the-merge-operator) in the paper's notation. The text does not define the interval terms beyond this recursion; Proposition 3 writes `V(p, y)` for visibility.

The reservoir at probe `p`, bin `b`, level `n` estimates the bin mean of `p`'s own field, not an interpolated field: `L̄_n(p, b) = (1/|Ω_b|)·∫_{Ω_b} L_{≥n}(p, ω) dω`. The paper says this choice is what moves the bilinear weights into the proposal.

### GRIS in brief

Generalized resampled importance sampling (Lin et al. 2022), as the paper restates it:

- A random `X` with unbiased contribution weight `W` satisfies `E[f(X)·W] = ∫_{supp X} f`.
- Samples `X_i` from domains `Ω_i` merge into a target domain `Ω` through shift maps `T_i`, bijections on subsets.
- Resampling weights are `w_i = m_i(T_i X_i)·p̂(T_i X_i)·W_i·|∂T_i/∂X_i|`. The selected sample `Y = T_s X_s` carries `W_Y = (Σ_j w_j)/p̂(Y)`.
- Unbiased integration over `supp Y = supp p̂ ∩ ⋃_i T_i(supp X_i)` needs MIS weights that form a per-point partition of unity over the techniques that can produce each point.
- Convergence and finite-variance bounds also need coverage (`supp p̂ ⊆ supp Y`) and a target with bounded ratio.
- Canonical samples, drawn by importance sampling `p̂` directly, are GRIS's device for coverage. The paper's tail merge has none, since all four inputs are reused.

### Method

Each frame runs three phases: candidate generation (one jittered ray per reservoir, tracing only its own interval), a top-down merge from `n = N−1` to 0, and a gather from level 0; Figure 1 shows the merge and Figure 2 the per-frame algorithm ([notes](../sources/2026_you_reservoir_cascades.md#4-method)).

**Reprojected bin lookup.** Each parent consults the bin it sees through the child's characteristic far point, `z = p + t_c·ω` with `t_c = √(t_{n+1}·t_{n+2})`, the geometric mean of the parent's interval: parent `q` reads `bin_{n+1}(dir(q → z))`. At the defaults `t_c` is 8.9, 41, 169 and 681 px for `n = 0` to 3 (derived). A single shared bin fails at depth: parallax in bin units grows as `2^n` under ×4 branching (Lemma 2), misaligned parents return darkness, and the paper measured 2× column striping before this fix (Fig. 4).

**Per-level collapse (layered RIS).** The selected tail resolves to a value at once, `L̂_tail = c_s·W_s`, and the child stores `c = c_near + L̂_tail` with a fresh unbiased contribution weight for its own domain only. No `W` crosses a level boundary: an `N`-level chain of multiplied random weights would have exponentially growing variance, and collapsing per level keeps each level's RIS closed. Unbiasedness follows by induction, variance from Theorem 2. The stored target `p̂ = lum(c) + λ` keeps the value-to-target ratio at or below 1 (the chromaticity bound), which section 5 turns into zero selection variance.

**Merge as RIS.** For a child `(p, b, n)` whose candidate escaped its interval, the tail `L_{≥n+1}(p, ω)` is resampled from the four bilinear parents `q`:

```
w_q = m_q · p̂(c_q) · J_q · W_q        p̂(c) = lum(c) + λ        J_q = r_q / r_p
```

- `c_q` and `W_q` are parent `q`'s stored, already collapsed radiance and contribution weight.
- `J_q` is the 2D reconnection Jacobian with `r_p = |y − p|` and `r_q = |y − q|` for the kept point `y_q`; it is never hard-coded to 1, and the step from level 0 to 1 has the largest `s/t`.
- `λ > 0` is a defensive floor. The text gives no value; the code uses 0.05 (`core/restir.h:32`).
- `m_q` is the bilinear weight `β_q`, renormalized under validation.
- The target is the luminance of `p`'s own field. Reconnection re-anchors every parent sample to `p`, so all four techniques estimate the same quantity and `β_q` is only a selection prior: a wrong `β` costs variance, not bias.

**Validation: renormalize before selecting.** With probability `ρ` per merge, each parent's reconnection segment `[t_{n+1}, |y_q − p|)` is shadow-tested from `p` (Fig. 3b). A blocked parent leaves the proposal set and `β` is renormalized over the survivors; if all four are blocked the tail is zero (a true umbra), so leaks are not filled in. Order matters. Killing a sample after selection multiplies the estimate by the visible-β fraction `v_p`, an `O(1)` shrink measured at −16% and −33%, because the cascade chain already bakes each parent's visibility into whether its sample exists. Renormalizing before selection compensates for that embedded factor, with residual bias `O(ε_n)` (Proposition 3), measured at −2.2%.

**Temporal reuse, re-evaluation and revival.**

- Reservoirs merge with their previous-frame state under a confidence cap `M_n = min(m0·2^n, M_max)`, on the argument that far levels are temporally smoother (a "temporal penumbra condition"). The text gives no `M_max`; the code uses `M_max = 64` and `m0 = 8` (`core/restir.h:33-34`, `core/restir.cpp:559-561`), so the caps are 8, 16, 32 and 64 from level 0 to 3 (derived).
- Each stored sample keeps an immutable as-resolved radiance `c_ref` and the emitter luminance `e0` at its reconnection point, and each frame re-evaluates `c = c_ref·lum_now(y)/e0`. Without re-evaluation a luminance-proportional target keeps preferring stale bright samples; the paper measured zero response 48 frames after a light turned off.
- Because `c_ref` is never overwritten, a geometrically valid sample revives as soon as its emitter returns. The paper calls this impossible in screen space.
- Scene changes raise a frame-indexed dirty flag that hard-resets `M`. That reset does not depend on any sample draw, so it is unbiased; candidate-triggered clamps were biased (+25%) and were reverted.

**Block-consistent interval jitter.**

- The interval boundaries `t_n` are scaled by a log-uniform factor `4^(ξ − 1/2)`. The text does not give the range of `ξ`; the code draws `ξ` uniform on `[0, 1)` once per block (`core/restir.cpp:85-88`), so the level 0 split length lies in `[t0/2, 2·t0)`. The supplement's continuous form uses a log-uniform density over `[t/2, 2t]` (`integrand-mismatch.md:123-128`).
- The scale is redrawn every `K` frames. The text gives no number; the code uses `K = 8` (`core/restir.h:55`), matching the experiments' "boundary-jitter block 8". The WebGPU page defaults to 9999 frames, which leaves the split fixed in the browser.
- Stored radiance bakes in the split, and mixing splits double-counts interval overlaps; per-frame jitter inflated leaks 3×. Within a block the cascade is consistent, and at block switches the temporal history is dropped (frame-indexed, unbiased).
- The jitter turns the deterministic interval-boundary bands into variance that frame averaging removes: the fan-energy ratio moves from 0.91 to 1.003.

**Per-frame algorithm (Figure 2).**

1. Candidates, all levels in parallel. Each `(p, b, n)` draws `ω ← jitter(Ω_b)`, traces `[t_n, t_{n+1})` and stores `(ω, hit, c_near)`.
2. Top-down merge for `n = N−1, …, 0`. Each escaped `(p, b, n)` with `n < N−1`: compute `z = p + t_c·ω`; for each parent `q` take `b_q = bin_{n+1}(dir(q → z))`; with probability `ρ` shadow-test `p → y_q` on `[t_{n+1}, |y_q − p|)`, drop blocked parents and renormalize `β`; run RIS over the survivors with `w_q ∝ β_q·p̂(c_q)·(r_q/r_p)·W_q`; set `c ← c_near + c_sel·W_sel`; form `R_new` with weight `lum(c)/pdf(ω)` (the figure leaves the first tuple field as a dot and does not define `pdf`); merge temporally under cap `M_n`; re-evaluate stored samples as `c_ref·lum_now(y)/e0`; reset `M ← 0` on a scene-change flag or a jitter-block switch.
3. Gather: integrate level 0 reservoirs per pixel. The text does not give the gather weighting.

Figure 2 marks each design decision with an italic margin note, and omitting any one of them gives a measured failure mode (the negative results below).

**Degenerate mode.** Candidates at bin centres, `p̂ = 1`, value-passing β-weighted merges and no reuse reproduce vanilla RC bit-exactly. The paper checks this against an independently written implementation, uses it as a regression gate, and localizes each vanilla bias to the degenerate step that reintroduces it.

### Theory

Full proofs are not in the Zenodo record but in the repository's `docs/theory/` (`variance.md`, `integrand-mismatch.md`, `lemma-3_2.md`, `gris-anchoring.md`); the paper states the results and their dependencies ([notes](../sources/2026_you_reservoir_cascades.md#5-theory)). Throughout, the scene has at most `K` silhouette arcs, emission is bounded by `L_max`, and the error parameter is

```
ε_n = √2 · s_{n+1} / t_{n+1}
```

the parallax angle of a parent at diagonal distance seen from the start of its interval. At the defaults `ε_n` is 0.71, 0.28, 0.135, 0.067 and 0.033 for `n = 0` to 4, summing to 1.22 (derived).

**The bound on `ε_n` is stated two ways.** Section 5 writes `ε_n ≤ ε0·2^(−n)` with `ε0 = 3√2·s0/(2·t0) ≈ 0.53` at the defaults; section 1 and Theorem 1 write `ε_n ≤ (4/3)·ε0·2^(−n)`. The `n = 0` term at the defaults is `√2·2/4 ≈ 0.707 = (4/3)·0.53`, which exceeds 0.53, so only the 4/3 form holds; the supplement states the 4/3 form (`lemma-3_2.md:36`).

**Assumption 1 (bounded radiance), `L ≤ L_max`.** The target is then reasonable in GRIS's sense, with `C_f ≈ (L_max + λ)/λ` per level. The paper says the assumption carries the mean bias bounds, not only the variance: a near-point emitter with `O(1)` energy inside an `O(ε_n)` strip gives an `O(1)` over-count, and the paper constructs one. Its small-source scene is the designated stress test.

**Lemma 1 (Jacobian).** Under non-grazing reconnection, `|J − 1| ≤ C_J·ε_n`.

**Lemma 2 (direction shift; the ×4 parallax obstruction).** `|ω_p − ω_q| ≤ ε_n·(1 + O(ε_n))` radians, which decays as `2^(−n)`. In parent-bin units the shift is `δ_n = Θ(2^n)`, because bins shrink as `4^(−n)`, twice as fast as parallax. The folklore claim that the shift stays within `O(1)` bins holds only for ×2 branching. Reprojection through `t_c` cancels the parallax exactly at one depth and halves the worst case (residual `δ'_n`); the paper says that covers the 3 to 4 levels its prototypes use, but gives no asymptotic result. The same scaling read across 2D and 3D, with the conditions under which the shift stays constant, is in [core theory](core_theory.md#parallax-in-bin-units-derived).

**Lemma 3 (integrand mismatch, no Lipschitz term).** Outside a penumbra set `P'` with `|P'| ≤ C1·(K + K_t)·ε_n`, reconnection re-anchors to the identical emitter point, so `F_p(Tω)·J = F_q(ω)·(1 + η)` with `|η| ≤ C2·ε_n^γ`. The emitter's texture never enters, whereas interpolation pays a Lipschitz term. `γ = 1` for polygonal scenes and `γ = 1/2` for smooth convex obstacles, where grazing corridors force the weaker exponent. The paper says `ε_n` is pointwise tight, since it constructs the extremal corridor, but that term contributes only `O(ε_n)` to the aggregate mismatch because curvature spreads grazing directions. The main text does not define `K_t` or `ψ`; the supplement defines `K_t` as the number of transversal obstacle-boundary crossings of the circle of radius `t_{n+1}` (`lemma-3_2.md:433-434`) and `ψ0` as a grazing-angle threshold: off the excluded set `G(ψ0)`, `|η| ≤ ε_n·(2 + cot ψ0)`, with `ψ0 = √ε_n` for smooth boundaries and any fixed `ψ0` for flat ones (`integrand-mismatch.md:202-216`).

**Proposition 1 (coverage bias is a GRIS coverage violation).** A single-bin lookup gives `supp Y = Ω_b \ A`, a strict subset of `supp p̂` (GRIS Eq. 15), so the merge is unbiased for the wrong integral: the bias is `−∫_A L dω`, always negative, with `|A|/|Ω_b| = O(ε_n)`. The paper stresses that this is GRIS's coverage condition itself, violated, not an analogue of it.

**Proposition 2 (windowed lookup restores coverage).** Consulting `2w + 1` bins per parent, with per-direction weights `m_q(y) ∝ β_q·1[covered_q(y)]`, is a legal GRIS partition of unity. Coverage depends only on supports and can be checked at merge time, unlike visibility. If `w ≥ δ'_n` then `supp Y = supp p̂` exactly, at `(2w + 1)` times the read cost and no extra rays. The window is analysed but not implemented; all measurements stay within reprojection's reach.

**Proposition 3 (validation).** The cascade evaluates `f_parent(Y)`, not `f_p(Y) = V(p, y)·radiance`: the stored value carries the parent's visibility. This is GRIS's "unoccluded target" problem, which GRIS's Appendix B leaves unbounded.

- `ρ`-validation is a stochastic re-evaluation of the missing `V(p, y)`.
- Renormalize-before-select has bias `O(ε_n)` under Assumption 1: off the `O(ε_n)`-wide penumbra set the survivor set is unanimous, so the self-normalized estimator's random denominator is deterministic there.
- Kill-after-select shrinks the estimate by the visible-β fraction, an `O(1)` bias.
- Survivor renormalization is not itself a GRIS partition of unity, because occlusion is not non-realization, so the paper says this bias must be bounded rather than certified. The experiments check where the removed energy goes: it concentrates on the penumbra band, and the fan core is validation-neutral.

**Theorem 1 (per-level reuse soundness).** The merge is a GRIS instance whose finite-variance guarantee holds through the `λ` floor. Its bias has three separable `O(ε_n)` sources: coverage (Proposition 1), shift distortion (Lemma 3) and the visibility gap (Proposition 3). With `ε_n ≤ (4/3)·ε0·2^(−n)`, the total over all levels satisfies `Σ_n ε_n < 3·ε0`, independent of `N` and scene scale. A reuse radius proportional to `2^n` is a corollary of the penumbra condition, not a tuned hyperparameter. A remark adds that the theorem assumes each level's lookup is coverage-complete, which reprojection alone secures only for about 3 to 4 levels; deeper cascades need the windowed lookup, which leaves the constant unchanged.

**Lemma 4 (selection noise equals `λ`).** Conditioned on the parents, `E[X²] ≤ μ·(μ + λ·J̄)`. At `λ = 0`, value-proportional RIS selection has zero variance given its inputs (the chromaticity bound at work). The floor adds at most `λ·(1 + C·ε_n)·μ` variance per level, and the rare spike of a dark sample selected against bright ones has probability proportional to `λ`, so second moments stay small even though almost-sure weight bounds compound with depth. The main text leaves `μ` and `J̄` undefined; the supplement defines `μ_n = E_sel[X_n | {c_q}] = Σ_q m_q·J_q·c_q` and `J̄ = Σ_q m_q·J_q ≤ 1 + C·ε_n` (`variance.md:24-28`).

**Theorem 2 (depth-uniform variance non-amplification).** Under arbitrary correlation between parents, the level-transfer factor is `a*·(1 + C·ε_n)²` with `a* ∈ [Σ_q β_q², 1]`. Correlation can slow convergence but cannot make it diverge. Unrolling gives `V_0 ≤ e^(6·C·ε0)·Σ_n ι_n`: the cascade multiplies the summed per-level injections by a constant independent of depth and scene scale, and the penumbra ratio that bounds every bias term also bounds variance compounding. In the supplement `C` is the absolute constant of the Jacobian bound of Lemma J (`J_q ≤ 1 + C·ε_n`), and the per-level injection is `ι'_n = λ·(1 + κ_n)·μ_n + Var_cand,n + κ_n·(1 + κ_n)·L̄²`, the defensive selection noise, the own-candidate noise and a coefficient fluctuation, with `κ = max channel/luminance ≤ 3` (`variance.md:155-157`).

**Temporal model.** At stationarity the reservoir weight follows an AR(1) recursion with coefficient `cap/(1 + cap)`:

- The predicted lag-1 autocorrelation is `cap/(1 + cap)`.
- Flicker (temporal coefficient of variation) scales with exponent 1/2 in `1 + cap`; the measured exponent is 0.38 ± 0.05.
- Adaptation takes about `1 + cap` frames without invalidation. Turn-off is instant because re-evaluation is multiplicative; turn-on is limited by the chain unless invalidation resets `M`.
- The paper attributes the exponent gap to sample switching (a jump process of rate about `γ`) and to the noise floor inherited through the fresh candidate's parent chain. A one-component model captures the scaling to about 15%, and a two-component refinement (AR(1) plus a switching process) brackets the measurements.

With no canonical samples, the `λ` floor serves as a surrogate weight bound and Theorem 1 as the surrogate coverage argument.

### Experiments

The CPU oracle is zero-dependency C++ in double precision with seeded PCG32 and analytic intersections ([notes](../sources/2026_you_reservoir_cascades.md#6-experiments)). Runs are 128 × 128 unless noted, with `B0 = 4`, `t0 = 4` and 4 to 5 levels; ground truth uses 4096 stratified rays per pixel; vanilla RC is the bit-exact degenerate mode; unless noted, temporal reuse is on with jitter block 8, over 128 frames and 6 to 8 seeds, reported as mean ± sd. The hardware for the CPU runs is not stated.

| Scene | Setup | Target failure |
|---|---|---|
| S1 | area light behind a tilted thin bar (width below `s1`) | light leaks |
| S2 | sub-bin point source through a pinhole | angular resolution |
| S3 | blinking emitter | temporal behaviour |

**Main results (Table 1: 128 × 128, 128 frames, block-8 jitter, 6 seeds; the deterministic baselines have no seeds).**

| Method | S1 leak (% of vanilla's leaked energy) | S2 recovery (% of reference energy) |
|---|---|---|
| vanilla RC | 100 | 115 |
| vanilla + bilinear fix | 94.9 | 114 |
| ours, `ρ = 0.25` | 21.4 ± 4.4 | 99.4 ± 6.0 |
| ours, `ρ = 0.5` | 10.7 ± 2.4 | 93.5 ± 6.2 |
| ours, `ρ = 1` | 0.1 ± 0.1 | 86.4 ± 6.9 |

- The vanilla recoveries above 100% come only from ringing misplacing energy.
- Room MAPE is 9.9 for vanilla, 8.8 with the fix and 1.9 for the method; the `ρ` for that figure is not stated, and the room scene is not otherwise described.
- At `ρ = 0.5` every acceptance bar clears with margin; the bars' thresholds are not given. At `ρ = 1` the S1 leak is about zero and exactly zero on most seeds.
- Boundary jitter removes a systematic 9% deficit (fan energy 0.91 to 1.003). Overall MAPE improves 2.5 to 12 times over vanilla.
- The `ρ` dial trades S1 leak against S2 recovery, as Proposition 3 predicts (Fig. 8a).

**Cost accounting.** All modes trace the same candidate budget, one interval-bounded ray per reservoir per frame: 262,144 rays at 128 × 128. Every level holds `128²·4 = 65,536` reservoirs, since spacing ×2 and bins ×4 cancel in 2D, so the count is 4 levels (derived). Validation shadow rays, interval-bounded segments starting at `t_{n+1}`, are the only overhead when `ρ > 0`:

| `ρ` | Extra rays (S1 and S2) |
|---|---|
| 0.25 | +8 to +13% |
| 0.375 | +13 to +20% |
| 0.5 | +17 to +26% |
| 1 | +33 to +53% |

The extra rays grow linearly in `ρ`, 32 to 53% per unit of `ρ` in every row (derived). The cheapest setting that clears both bars is `ρ = 0.375`, with leak 15.8 ± 3.4% and recovery 96.0 ± 6.0% at 20% or fewer extra rays; at `ρ = 0` the method still cuts the leak to 35% of vanilla's with no extra rays.

**Where the `ρ` cost lives.** At 256 × 256 with a frozen split and seed 3, the energy removed between `ρ = 0` and `ρ = 1` is 5.8% of reference. Of that, 67% lies within 2 px of the fan's penumbra boundary and 85% within 4 px, bands that cover 19% and 37% of the area; the fan core is validation-neutral (+0.04%). The remaining `ρ`-independent core deficit under a frozen split, −4.4%, is interval-boundary bias, which boundary jitter removes.

**Equal-ray attribution (Table 2: seed 1, `ρ = 0.25`, leak energy in the S1 shadow mask).** The caption promises percentages of vanilla in parentheses, but only the first row has one.

| Configuration | S1 leak | S1 MAPE |
|---|---|---|
| stochastic RC (jittered rays, vanilla merge, no RIS) | 0.0115 (97%) | 2.39 |
| + merge as RIS | 0.0023 | 0.40 |
| + temporal | 0.0023 | 0.42 |

Jittered rays with the vanilla merge keep 97% of vanilla's leak, so the leak is structural in the merge, not ray starvation. Merge as RIS alone captures essentially the whole gain; temporal reuse adds little to frame-averaged statics, and its value is per-frame quality and dynamics. These configurations add the 8 to 13% validation rays of `ρ = 0.25`.

**Flat world-space control (Table 3).** The control is a flat baseline after Boisse (2021): one probe per pixel with `4N` angular bins, which matches the cascade's per-pixel candidate count; full-length rays; the same temporal machinery (immutable `c_ref` re-evaluation, revival, confidence cap); and standard ReSTIR spatial reuse with `k = 4` disk neighbours, reconnection shifts with Jacobians, per-candidate generalized-balance MIS and the same renormalize-before-select validation. Its reuse radius `r`, confidence cap and validation rate are single global dials. The table is at 128 × 128, 128 frames, cap 8 and 6 seeds; flat shadow rays are full length and the cascade's are interval-bounded.

| Configuration | S1 leak | S2 recovery | MAPE S1 / S2 | Extra rays |
|---|---|---|---|---|
| flat `r = 0` (no reuse) | 0.0 | 100.4 ± 2.9 | 0.06 / 0.15 | 0% |
| flat `r = 8`, `ρ = 0` | 2819 ± 362 | 166 ± 6 | 40.6 / 21.9 | 0% |
| flat `r = 8`, `ρ = 0.5` | 121 ± 12 | 50.3 ± 1.8 | 3.9 / 3.9 | 17 to 29% |
| flat `r = 8`, `ρ = 1` | 0.0 | 27.2 ± 0.5 | 1.1 / 0.18 | 33 to 58% |
| flat `r = 2`, `ρ = 1` | 0.0 | 92.5 ± 3.2 | 0.44 / 0.19 | 64 to 99% |
| cascade, `ρ = 0.5` | 10.7 ± 2.4 | 93.5 ± 6.2 | 0.38 / 0.80 | 18 to 28% |

The caption says no flat configuration reaches both bars with a reuse radius beyond 2 px, and that at cap 32 every sharing configuration diverges. The source gives no reason why `r = 2` needs more extra rays than `r = 8` at the same `ρ`. The paper reads four regimes from it:

1. **No reuse wins at equal rays once accumulated.** Per-pixel brute force (`r = 0`) is unbiased and hard to beat once accumulation converges, but its rays are full length, about 24 times the nominal per-pixel path budget with analytic intersections, which DDA or BVH tracers do not get for free. Nothing is amortized, so its per-frame quality equals its accumulated quality only after long accumulation.
2. **Sharing without validation leaks badly:** 1.7 to 43 times vanilla's leaked energy at cap 8, growing with radius and cap. Reused world-space samples carry their source's visibility, and a flat kernel has no scale at which that error is small.
3. **Sharing with full validation kills the leak but collapses S2 recovery** at any radius beyond 2 px: 59% at `r = 4` and 27% at `r = 8`. Validation splits the survivor set on an `O(1)` part of the domain when the kernel spans a visibility boundary, the unanimity condition of Proposition 3 violated at scale-mismatched radii.
4. **At cap 32 the flat spatiotemporal chain diverges:** leak reaches 4,700 times vanilla and error grows exponentially with frame count, because stored contribution weights multiply across frames and random-walk. The cascade's per-level collapse exists to prevent this.

The cascade spends +18 to +28% interval-bounded segments, with reuse radii growing to about 23 px at its deepest level; the only flat configurations that hold both scenes confine sharing to `r = 2`. A parent's diagonal distance at level 4 is `√2·16 ≈ 22.6` px, so the 23 px radius implies a 5-level run, while the 262,144-ray cost accounting implies 4 levels (derived; both fall within the stated 4 to 5).

**Dynamics (S3).** Flicker decays monotonically with the confidence cap: 1.27, 0.89, 0.54 and 0.40 at caps 2, 8, 32 and 64. A least-squares fit of these four points against `1 + cap` gives exponent 0.375 (derived), inside the paper's 0.38 ± 0.05. Light-off responds in 2 to 3 frames through re-evaluation; light-on takes 3 frames with scene-change invalidation and about `cap` frames without it. In Figure 6 (frozen split, `m0 = 8`, `ρ = 0.25`, the ratio of floor energy to reference per frame), turn-off takes 2 to 3 frames in both variants and turn-on with the reset converges in 3 frames, while without it the revival jump is followed by a chain-limited climb that does not reach the ±10% band within the half-period. The paper calls all four behaviours consistent with the AR(1) model.

| Cap | Predicted lag-1 autocorrelation | Measured |
|---|---|---|
| 2 | 0.667 | 0.651 |
| 8 | 0.889 | 0.849 |
| 32 | 0.970 | 0.908 |

Switching decorrelates the higher caps.

**The leak ring: a residual bias with a predicted address.** With validation and jitter both off, the remaining interval-boundary bias concentrates on an arc rather than spreading out. Level 3 parents closer than `t_3` to the occluding wall start their interval beyond the wall; their rays hit the emitter untested, and their children reconnect that energy into the shadow. The affected pixels are those whose sight line toward the emitter crosses the wall at a distance of about `t_3`, and the histogram of wall-crossing distance over leak pixels spikes 6 times in the predicted band. In Figure 7 (S2 at 256 × 256, `ρ = 0`, frozen split, seed 3) ghost blobs lie in `t_w ∈ [80, 92)` around the level 2 to 3 boundary `t_3 = 84` (the defaults' `t0·(4³ − 1)/3`, derived). Leak pixels in that band number 523 with `ρ = 0` frozen, 318 with jitter, 229 at `ρ = 0.5` frozen and 0 at `ρ = 1`. Each mechanism leaves its own signature: `ρ = 0.5` halves the count, jitter trades the leak for more but dimmer pixels, and `ρ = 1` removes it. The WebGPU demo reproduces it. This is the same mechanism as RC's classic leak through occluders thinner than a parent's interval start ([artifacts](artifacts_and_fixes.md#light-leaks)) (inference).

**WebGPU.** A WGSL compute build with a fused per-level kernel, ping-pong reservoirs, SDF sphere tracing and shared scene files runs at 120 fps at 256 × 256 on an unnamed Apple-silicon laptop. It reproduces the oracle's metrics live (S1 leak about 0, S2 recovery 100.9%) and has a one-click vanilla/full toggle that shows every failure mode and fix in the paper.

**Negative results**, each one line away from the correct algorithm:

- Kill-after-select validation: −16% and −33%, the `v_p` shrink of Proposition 3.
- Candidate-triggered confidence clamps: +25%, since MIS weights that depend on the sample draw are biased.
- Per-frame interval jitter under temporal reuse: 3× leak inflation, since stored radiance bakes in the split.

### Limits and design axes

- **Scope.** The prototype is 2D flatland with direct emission only ([notes](../sources/2026_you_reservoir_cascades.md#7-discussion-and-limitations)). Multi-bounce is a next step, proposed as an emissive surface cache with a one-frame lag as in DDGI-family systems ([related probe GI](related_probe_gi.md)). The 3D lift is another: `J = r_q²/r_p²`, bins map to direction textures, and the paper says the `ε_n` calculus does not depend on dimension.
- **Single frame.** Single-frame output has one candidate per bin and is noisy, like every ReSTIR-family estimator; the paper says production use presumes temporal accumulation or denoising, and that its variance theorem says the hierarchy does not amplify what those steps consume.
- **Hypotheses and constants.** The `O(ε_n)` mean-bias bounds need bounded radiance. Near-singular emitters degrade gracefully and detectably: per-probe variance spikes act as a built-in leak detector, and the degradation stays in the penumbra band. Several constants are order-only; the coverage sliver fraction and the un-validated leak (27 to 35% of vanilla across configurations, about `ε_1`) are measured calibrations. At the defaults `ε_1 = √2·4/20 ≈ 0.28`, which matches that range (derived). Turn-on without scene-change flags costs about `cap` frames, and a sample-driven detector (temporal-gradient MIS) is open.
- **Design axes the theory exposes.** Angular branching: ×2 is alignment-safe, ×4 is richer in resolution but needs reprojection or the windowed lookup. Jitter block length trades boundary-bias decorrelation against temporal depth. `λ` trades dark-region coverage against per-level selection noise. `ρ` trades leak against shadow rays, +13 to +20% at the cheapest bar-clearing setting and +33 to +53% at `ρ = 1`; the paper says that in 3D, where shadow rays dominate frame budgets, this dial is where the method will be priced. Memory is about 3 times vanilla RC, since each bin stores a reservoir instead of a radiance value.
- **Conclusion as stated.** RC supplies the discretization that ReSTIR lacks and ReSTIR supplies the estimator that RC lacks. The penumbra condition bridges them: one geometric ratio sets the order of each merge bias, of the hierarchy's variance compounding and of its temporal dynamics, and the flat control measures what breaks without that structure.

**Parameters the text leaves out:** `λ`, `M_max`, the jitter block `K`, `K_t`, `C`, `C1`, `C2`, `C_J`, `δ'_n`, `ι_n`, `μ`, `J̄`, `ψ`, the `pdf` in the reservoir weight and the gather weighting. The code and supplement give `λ`, `M_max` and `K` and define `K_t`, `C`, `ι`, `μ`, `J̄` and `ψ` (`μ_n = E_sel[X_n | {c_q}] = Σ_q m_q·J_q·c_q` and `J̄ = Σ_q m_q·J_q ≤ 1 + C·ε_n`); `C1` (which depends on an `α0`), `C2`, `C_J` and `δ'_n` stay order-only, and Figure 8b's `γ` is undefined ([notes](../sources/2026_you_reservoir_cascades.md#source-inconsistencies-and-unclear-items)).

### Code

The repository's layout ([notes](../sources/2026_you_reservoir_cascades.md#code)):

- `core/` holds the estimator. `core/restir.h:6-18` describes two modes: Full (jittered candidates with merge as RIS in the proposal) and StochasticRC (the equal-ray value-passing baseline of Table 2). `core/vanilla.cpp` and `core/flat.cpp` are vanilla RC and the flat world-space control.
- `cpu-ref/` is the CPU oracle, with defaults `--lambda 0.05`, `--mcap0 8` and `--bjitter-block 8`; its sweep covers `ξ ∈ {0, 1/8, …, 1}`. `metrics/` is the evaluation, `scenes/s1.json` to `s3.json` the three scenes, and `webgpu/` the browser build, whose parameter buffer holds `λ = 0.05` and cap 64, with `#mcap` 8 and jitter block 9999.
- The jitter seed hashes the block index into a PCG32 (`hashCombine(seed, f/block + 0xB007)`); a separate `ξ`, 0.5 for bin centres or uniform otherwise, is the angular offset inside a direction bin (`core/restir.cpp:102-110`).
