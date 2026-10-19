# RC for sampling and guiding

Two research lines use the cascade hierarchy as a sampling structure, not only as a deterministic lighting solver. Reservoir Cascades keeps RC's discretization and rewrites the merge between levels as resampled importance sampling, tested in 2D. RCPG builds a world-space 3D cascade volume and samples path-tracing directions from it. vlam is a small 2D experiment in the same direction. The cascade theory these build on is in [core theory](core_theory.md), and the resampling vocabulary (RIS, reservoirs, ReSTIR, MIS, NEE, path guiding) is in the [glossary](supporting_techniques.md#resampling-and-sampling-theory).

| Work | Domain | What the cascades do | Temporal reuse | Code |
|---|---|---|---|---|
| Reservoir Cascades (You, 2026-07) | 2D flatland, direct emission | final lighting; the merge selects one parent sample by RIS | temporal reservoirs, block interval jitter | C++ CPU oracle and WebGPU, MIT |
| RCPG (Ikkala, Jääskeläinen and Mäkitalo, ACM TOG 2026) | 3D world-space volume | a guiding distribution for a path tracer | exponential moving average, `α = 1/30` | tauray, LGPL-2.1 |
| vlam (entropylost, 2025-04) | 2D, refracting circles | a direction distribution for a path tracer, trained from its own paths | accumulates deposits | no licence |

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

## RCPG: product path guiding with radiance cascades

"RCPG: Real-Time Product Path Guiding Using Radiance Cascades" by Julius Ikkala, Pekka Jääskeläinen and Markku Mäkitalo (Tampere University) appeared in ACM Transactions on Graphics 46(2), 1-25, online 2026-10-09, DOI 10.1145/3840291; the Tampere group page lists it under 2027, the issue year. It is open access (25 pages), and the renderer is tauray (https://github.com/vga-group/tauray, LGPL-2.1, `--renderer=rc` and `--renderer=rc-restir`). The README says the paper's exact version lives in a separate `rcpg` branch and that tauray is no longer developed; the code described here is the default branch, and its volume, culling and temporal parts apply to RC for GI too ([notes](../sources/2026_tauray_rcpg_path_guiding.md)).

The world-space 3D cascade volume serves as a guiding distribution for a path tracer, not as the final lighting. The paper claims bounds on radiance intervals so the hierarchy does not misplace incoming directions; one sampler for the product of incoming radiance and the BSDF; a PDF that can be evaluated for any direction, so it combines with MIS and unbiased ReSTIR; and a world-space structure that serves off-screen path vertices, which multi-bounce guiding needs. Against earlier real-time guiding with multi-sample MIS it traces about twice the paths per pixel in a real-time frame.

### Cascades

- Every cascade is a power-of-two cube grid over the whole scene, each texel holding radiance and transparency. A step up halves probe density, doubles angular resolution per axis and moves the interval out, each interval longer than the last ([notes](../sources/2026_tauray_rcpg_path_guiding.md#cascades-sec-31)).
- A cascade holds `M³N²` texels and the next `(M/2)³·(2N)² = M³N²/2`, so storage is `O(M0³·N0²)`, the same as one probe grid at cascade 0's resolution, and most texels belong to short intervals, which trace faster. At most `log₂ M0` cascades exist, and one whose `t_min > L·√3` (`L` the largest extent of the scene bounds) starts outside all geometry and is skipped.
- Spatial lookups are nearest-neighbour, so each probe has one parent. Each texel is integrated over its solid angle and its cell's volume by jittering ray origins in the cell and directions in the texel, averaged with an exponential moving average of `α = 1/30`. One deterministic ray per texel, as in the original paper, cannot represent detail below a minimum size.
- Unlike SD-trees, the structure never splits adaptively, which keeps GPU traversal free of divergence, and space and direction are coupled: short-range light at high spatial and low angular resolution, long-range light the reverse.

### Parallax-based interval bounds

- Jittering origins over the cell low-pass filters the probe image: a point at distance `t` is smeared over the parallax angle under which the cell sees it. The bound uses the cell's inscribed circle (edge `l`), smaller than the cell from every direction, which carries to 3D as a sphere's equator: `θ_min = 2·arcsin(l/(2·t_max))` ([notes](../sources/2026_tauray_rcpg_path_guiding.md#parallax-based-interval-bounds-sec-32)).
- Taking `θ_min` as the window width, the passband tops out at `f_max = 1/θ_min`, and Nyquist requires `f_max < f_s/2` for the probe's angular sampling rate `f_s`, precomputed by brute force from the longest angle across the largest texel. Then `t_max = l/(2·sin(1/f_s))`.
- With `l` and `f_s` doubling per cascade and `sin` nearly linear near zero, `t_max ∝ 4^i`. The original paper's penumbra condition gives `t ∝ 2^i` (its 3D `l = 2`), while Osborne and Sannikov use `4^i`. Power-of-two lengths let adjacent probes see parallax larger than a texel's angular radius, giving double images under linear interpolation or wasted resolution under jitter; diffuse lighting hides this, but the direction of incoming light is misrepresented, which rules them out for guiding. The source note also credits `4^i` to the HRC paper, whose own rays double per level; the [HRC topic](holographic_rc.md#connections) resolves that attribution.
- The conservative bound wastes probe resolution over most of the interval, so the measured configuration doubles it, `t'_max = l/sin(1/f_s)`, with `f_s` taken across the shortest edge of the smallest texel, which switches from wasted resolution to lost detail near the middle of the interval. Using the conservative bound as `t_min` instead also works but samples slightly worse.

### Mapping and culling

- Equal-area maps (Clarberg; Mortari et al. 2011) give uniform resolution per solid angle and a constant Jacobian, but sampling projects every corner of every texel it visits, so the octahedral map, with no transcendental functions, wins ([direction maps](supporting_techniques.md#direction-parameterizations)). Its Jacobian is `|J| = (1 + 2·min(1 − |x| − |y|, 0) − 2|x| − 2|y| + 2|xy| + 2x² + 2y²)^(−3/2)` for `x, y ∈ [−1, 1]`, computed once per sample ([notes](../sources/2026_tauray_rcpg_path_guiding.md#probe-mapping-and-culling-sec-33-34)).
- A 128³ cascade 0 with 16 texels per probe, two rays per texel (primary and shadow) and 5 cascades would need about 130 million rays. Probes whose cell overlaps no geometry are never used under nearest-neighbour lookup, so the scene is voxelized conservatively by rasterization at cascade 0's resolution, coarser levels mark a voxel occupied if any of its 2×2×2 children is, and empty cells are culled. A per-cell count of occupied frames lets returning geometry reuse old probe data. The paper calls the culling not core to the method.

### Ray casting and gathering

- One ray per texel per frame, with origin and direction jittered by an `R_5` sequence (3 dimensions of position, 2 of direction), averaged over frames, which delays updates. Back faces are ignored so that jittered origins inside geometry still pass through and contribute ([notes](../sources/2026_tauray_rcpg_path_guiding.md#ray-casting-and-gathering-sec-35-36)).
- A hit is shaded with one light sample per frame from a light BVH; any light type works if the probe-update light sampler supports it (area lights, environment maps and spotlights are shown).
- Multiple bounces shade hits from the previous frame's gathered cascade 0, treating each texel as an area light evaluated with LTC; shading a 1280×720 image this way took about 0.5 ms, with colour lost and nearest-neighbour blocks obvious (Fig. 7). Errors there only add noise to guiding.
- Explicit point and directional lights stay out of the probes and go to next-event estimation, since texels are too coarse for small lights; RCPG targets indirect light and emissive meshes. With the sun inside the cascades, 8 spp leave shaded areas near sunlit edges slow to converge, worse than 4 spp with NEE at about equal ray counts (Fig. 8).
- Gathering runs from the highest cascade down: each texel takes the light of its 4 child texels in the next cascade, alpha-blended behind it by its coverage, so a texel holds all light from its direction, not only its interval's. A floor `L_avg·γ` with `γ = 0.05` (probe-wide average luminance at cascade 0, a 2×2 neighbourhood above) keeps stochastic zeros from biasing sampling; a larger `γ` means more noise but fewer outliers.

### Sampling

- Texels are weighted as polygonal area lights through LTC, with irradiance `E = (1/2π)·Σ arccos(p_i·p_j)·((p_i × p_j)/|p_i × p_j|)·n` over vertices clipped to the upper hemisphere ([LTC](supporting_techniques.md#shading)). The inverse matrix uses a 3-parameter fit with rows `(a, 0, b)`, `(0, 1, 0)` and `(0, 0, c)`, `a, b, c ∈ [0, 1]`: the lobe stays non-zero over the whole hemisphere, which keeps sampling unbiased, and points above the horizon stay above, so clipping can precede the transform and the diffuse and specular lobes share it. At grazing angles with low roughness the fit turns bimodal with a weak retro-reflective lobe ([notes](../sources/2026_tauray_rcpg_path_guiding.md#sampling-sec-4)).
- A sample descends the hierarchy: every texel of the cascade 0 probe containing the point is weighed and one is chosen by weighted random sampling, then one of the 4 texels it covers in the next cascade, and so on to the finest cascade. Weights use the separability approximation `∫L·ρ·cos dω ≈ ∫L dω · ∫ρ·cos dω`, with the stored luminance as the first factor and LTC with clamped vertices as an approximate horizon clip for the second; that underestimates grazing texels but cannot bias, because the PDF uses the same weights.
- Inside the final texel the direction is uniform over its solid angle (used in all measurements; faster, but it can go below the horizon) or drawn by LTC polygon-light sampling (Peters 2021) with exact clipping, which never goes below the horizon and helps large texels with narrow lobes. In the ablation the latter was 25% slower in path tracing for SSIM 0.0842 against 0.0837 (Fig. 22).

### Implementation and bandwidth

- A baseline with 16 texels at cascade 0, four floats per texel, 5 cascades and linear spatial interpolation reads 4096 bytes per sample, about 475 GB/s at 1920×1080 and 60 Hz ([notes](../sources/2026_tauray_rcpg_path_guiding.md#implementation-sec-5)). RCPG stores luminance in R32F and visibility in R8 in separate textures, so one gather reads a 2×2 luminance footprint and visibility only for the chosen texel; half floats caused artifacts in the moving average. Nearest-neighbour lookups in space and direction cut bandwidth by 8× more, leaving visible edges in noise level that denoisers or ReSTIR hide. The total is about 15.4 GB/s.
- The 4096 bytes are all 16 cascade 0 texels plus 4 child texels in each of 4 more cascades, at 16 bytes and 8 trilinear corners each: `(16 + 4·4)·16·8`. RCPG's footprint is the 16 cascade 0 luminances plus one visibility byte, then 4 luminances and one visibility byte per further cascade: `64 + 1 + 4·17 = 133` bytes. At 124.4 million samples per second these give 474.6 and 15.4 GiB/s, so the paper's GB are GiB (derived).
- The arccos term is rewritten for a tangent-space normal as `Σ arccos(p_i·p_j)/(2π·|sin(arccos(p_i·p_j))|)·(p_ix·p_jy − p_iy·p_jx)`, and `arccos(d)/(2π·|sin(arccos d)|)` is approximated by `(−0.709693·d³ + 3.787823·d² + 20.448902·d + 15.951386)^(−1/2)`. Most sampling math runs in 16-bit floats for double-rate FMA.
- Bounces use RCPG samples alone, not MIS with BSDF samples: single-sample MIS raised noise at equal sample counts and frame time by 40 to 80% through divergence. MIS with NEE or a light tree is recommended.

### Evaluation

The setup: RTX 3090, 1920×1080, 1000 warm-up frames, GPU timings averaged over 250 frames, references at 262,144 spp, and MAE in linear colour plus PSNR, SSIM and FLIP after Reinhard tone mapping ([metrics](supporting_techniques.md#image-metrics)); equal-time runs target 33.33 ms ([notes](../sources/2026_tauray_rcpg_path_guiding.md#evaluation-sec-6-8)). RCPG uses 4×4 texels at cascade 0, a 128³ grid, uniform in-texel sampling and 5 cascades: 2,396,672 probes and 310 MB allocated in every scene. Scenes keep roughness above 0.05 and lose normal maps and transparency; explicit lights replace emissive surfaces because VXPG did not sample them, and NEE picks lights uniformly. ReSTIR GI runs unbiased, one bounce, with one temporal and one spatial neighbour, a 32-pixel radius and a history cap of 8. VXPG runs at 128³ (its default is 64³) with multi-sample MIS.

| Scene (Table 1) | Bounds | Active probes | Active memory | `t_0` | `t_1` | `t_2` | `t_3` | `t_4` |
|---|---|---|---|---|---|---|---|---|
| Ajar | 11.30 × 4.80 × 9.20 | 127,067 | 31.7 MB | 0.126 | 0.564 | 2.521 | 10.72 | 44.24 |
| Breakfast | 11.62 × 9.32 × 14.43 | 99,447 | 27.4 MB | 0.161 | 0.720 | 3.221 | 13.69 | 56.51 |
| Classroom | 10.17 × 3.11 × 8.51 | 113,740 | 26.9 MB | 0.113 | 0.508 | 2.270 | 9.652 | 39.83 |
| Rungholt | 655 × 69 × 550 | 70,936 | 13.9 MB | 7.309 | 32.69 | 146.2 | 621.6 | 2565 |
| Staircase | 7.02 × 7.84 × 10.59 | 175,886 | 40.0 MB | 0.118 | 0.528 | 2.363 | 10.05 | 41.47 |
| Kitchen | 6.92 × 3.38 × 8.65 | 117,288 | 30.1 MB | 0.097 | 0.432 | 1.931 | 8.213 | 33.89 |

FLIP against the reference (lower is better), with spp for the equal-time runs and ms for the ReSTIR runs at 1 spp (Tables 2 to 7):

| Scene | 1 bounce: PT / SSPG / VXPG / RCPG | 2 bounces: PT / VXPG / RCPG | ReSTIR: PT / VXPG / RCPG |
|---|---|---|---|
| Ajar | 0.235 (37) / 0.186 (14) / 0.039 (13) / 0.094 (23) | 0.336 (22) / 0.127 (4) / 0.164 (11) | 0.155 (5.55) / 0.105 (15.16) / 0.083 (12.43) |
| Breakfast | 0.174 (28) / 0.158 (8) / 0.156 (7) / 0.112 (19) | 0.197 (16) / 0.277 (2) / 0.183 (9) | 0.156 (7.03) / 0.147 (32.32) / 0.116 (14.38) |
| Classroom | 0.215 (21) / 0.175 (7) / 0.226 (6) / 0.151 (16) | 0.261 (12) / 0.347 (2) / 0.223 (6) | 0.181 (8.55) / 0.183 (32.48) / 0.137 (17.92) |
| Rungholt | 0.144 (20) / 0.113 (5) / 0.212 (5) / 0.106 (13) | 0.169 (12) / 0.273 (2) / 0.133 (7) | 0.180 (11.73) / 0.213 (27.75) / 0.120 (22.80) |
| Staircase | 0.232 (29) / 0.171 (9) / 0.217 (8) / 0.132 (19) | 0.289 (17) / 0.343 (3) / 0.212 (8) | 0.173 (6.68) / 0.214 (23.66) / 0.116 (14.67) |
| Kitchen | 0.245 (27) / 0.261 (9) / 0.282 (7) / 0.216 (18) | 0.365 (15) / 0.414 (3) / 0.344 (8) | 0.299 (8.57) / 0.350 (18.11) / 0.282 (15.37) |

- VXPG wins Ajar, whose single rectangular slit fits voxels. RCPG leads Classroom, Rungholt and Staircase in every metric with 2 to 3 times the samples, and samples Breakfast's caustic best. In Kitchen, with metallic surfaces and occluded lights, unguided PT beats RCPG in PSNR and SSIM. With ReSTIR, RCPG is best by most metrics, but VXPG wins MAE in Ajar, Breakfast and Rungholt, plausibly from temporal flicker of its stochastic light injection.
- After one bounce, intersection points diverge between neighbouring pixels, and the scattered reads into the guiding structure slow both VXPG and RCPG: in Breakfast unguided PT manages twice RCPG's sample count at two bounces.
- Over the first 64 frames PT and VXPG are flat, RCPG stabilizes more slowly because of its moving average, and SSPG takes hundreds of frames, settling at MAE 0.158 in Staircase. RCPG's PDFs sit between SSPG's and VXPG's in detail and match the ground-truth magnitudes better than either (Fig. 15). Fireflies from small high-contribution regions make RCPG's MSE worse than PT's in Breakfast and Staircase; a single-sample MIS configuration with a plain average (9 to 12 spp) improves only MSE.
- At the 33.33 ms budget one sample per pixel costs 0.90 to 1.67 ms for PT and 1.45 to 2.56 ms for one-bounce RCPG (derived from the spp).

Per-pass cost at 1 spp in ms (Table 8):

| Scene | Voxelization | Probe culling | RC trace | RC gather | Path tracing | Tone mapping | Total |
|---|---|---|---|---|---|---|---|
| Ajar, 1 bounce | 0.29 | 0.06 | 0.70 | 0.27 | 1.66 | 0.09 | 3.04 |
| Breakfast, 1 bounce | 0.24 | 0.06 | 0.63 | 0.22 | 1.99 | 0.08 | 3.22 |
| Classroom, 1 bounce | 0.35 | 0.06 | 0.83 | 0.23 | 2.47 | 0.09 | 4.03 |
| Rungholt, 1 bounce | 2.27 | 0.05 | 1.67 | 0.12 | 2.41 | 0.08 | 6.60 |
| Staircase, 1 bounce | 0.27 | 0.06 | 0.99 | 0.33 | 1.92 | 0.09 | 3.66 |
| Kitchen, 1 bounce | 0.38 | 0.06 | 0.78 | 0.23 | 1.95 | 0.08 | 3.48 |
| Ajar, 2 bounces | 0.29 | 0.06 | 1.10 | 0.26 | 3.18 | 0.08 | 4.97 |
| Breakfast, 2 bounces | 0.25 | 0.06 | 1.07 | 0.22 | 4.18 | 0.08 | 5.86 |
| Classroom, 2 bounces | 0.36 | 0.06 | 1.35 | 0.24 | 5.55 | 0.08 | 7.64 |
| Rungholt, 2 bounces | 2.31 | 0.06 | 1.77 | 0.12 | 4.59 | 0.09 | 8.94 |
| Staircase, 2 bounces | 0.28 | 0.06 | 1.75 | 0.34 | 4.12 | 0.09 | 6.64 |
| Kitchen, 2 bounces | 0.39 | 0.06 | 1.32 | 0.25 | 4.00 | 0.08 | 6.10 |

The cascade passes (voxelization, culling, trace and gather) take 1.15 to 1.65 ms, 36 to 45% of the one-bounce frame, in the indoor scenes and 4.11 ms (62%) in Rungholt, where voxelization alone is 2.27 ms; the recursive second bounce multiplies the trace by 1.57 to 1.77 indoors and 1.06 in Rungholt (derived).

Ablations at 1 spp (Tables 9 and 10):

| Cascade 0 grid (Staircase) | RC build (ms) | Sampling (ms) | FLIP |
|---|---|---|---|
| 16³ | 0.09 | 1.56 | 0.462 |
| 32³ | 0.15 | 1.70 | 0.436 |
| 64³ | 0.36 | 1.69 | 0.412 |
| 128³ | 1.38 | 1.92 | 0.383 |
| 256³ | 6.06 | 1.82 | 0.360 |

| Cascade 0 texels (Classroom) | RC build (ms) | Sampling (ms) | FLIP |
|---|---|---|---|
| 4×4 | 1.12 | 2.47 | 0.364 |
| 8×8 | 3.20 | 2.74 | 0.341 |
| 16×16 | 12.57 | 7.12 | 0.324 |

4×4 is the smallest supported resolution, because 2×2 texels are so large that the LTC integration hits corner cases. With `α = 1/30`, a worst case in which Sponza's spotlights jump from one curtain to the other makes guiding briefly worse than plain path tracing until the probes adapt over tens of frames (Figs. 25-26).

### Limits and future work

- The cascades hold only visible surfaces, and with jitter and detail thinner than a cell, light leaks across cascade transitions. Caustics and other very local, directional light show the grid as edges in noise level, and LTC weighting fits very low roughness poorly. Moving geometry entering cells without history shows noisier patches, softened by seeding new probes from visited neighbours and by coarser cascades more often having history ([notes](../sources/2026_tauray_rcpg_path_guiding.md#limits-and-future-work-sec-9-10)).
- Only about 10% of the allocated memory is touched, so a sparse voxel octree or spatial hash grid would scale to larger worlds.
- Proposed: sharing traced rays across cascades; RGB storage as an FP32 copy for the moving average plus an RGBE copy for sampling; culling by distance queries on hardware ray-tracing structures; and computing each texel by cone or beam tracing in one sample, which would remove the temporal reuse but has no hardware support (sparse voxel octrees might serve).

### Tauray code

**Volume and layout** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#code-volume-and-layout)):

- One cube around the scene bounds at 1.01× the largest extent. Cascade `c` has `2^(L−c)` probes per axis, with `L = 7` by default (128³ probes at cascade 0).
- Octahedral directions, `(c0 << c)²` per probe with `c0 = 4`: 16, 64, 256, 1024 and 4096. Each cascade is a 2D array texture of `c0·2^L` squared (512²) with one layer per probe slice, and a probe's directions sit in one block. Each cascade holds half the texels of the one below: 33.6, 16.8, 8.4, 4.2 and 2.1 million, 65,011,712 in all (derived).
- Storage is luminance only (R32F) plus an R8 visibility: 65,011,712 texels at 5 bytes are 325 MB, or 310 MiB, so the paper's 310 MB and the code's 325 MB are the same figure, more with ping-pong copies (derived).
- Intervals derive from the probe spacing and an angle table: `t0(c) = l/sin(θ_c)` with `l = 2^(c−1)·E/2^L` and `θ = 1.5708, 0.7854, 0.3218, 0.1419, 0.0666, …`. Cascade 0 starts at zero so that a surface inside a probe's cell can see its own cell. The code doubles the computed length on purpose: too long makes probe resolution the limit, too short makes parallax the limit, and longer was faster and looked better. Cascades are added while `t0` is within the volume diagonal.

**Live probe culling** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#live-probe-culling)):

- The scene is voxelized every frame at `2^L` by conservative rasterization (dominant-axis projection in a geometry shader); each mip takes the maximum of its 8 children.
- A probe is live when the occupancy mip matching its cascade is occupied. Starting from every top-cascade probe, the children of live probes are tested cascade by cascade, and live probes are appended to one list, which feeds indirect dispatches of `ceil(live·dirs/64)` groups per cascade. Only live probes are traced and merged.
- A per-voxel history counter (occupied frames, capped at 65536) tells whether a probe has valid history.

**Trace** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#trace)):

- One invocation per texel of a live probe. A hardware ray query traces the segment `[t0(c), t0(c+1)]` with back-face culling; the last cascade ends at 10⁹ and alone receives environment light.
- A hit returns emission plus optional direct light (shadow maps, or light-tree samples with shadow rays) plus, when enabled, a recursive term that reads the cascades again at the hit point for multi-bounce. Back-face hits return black and opaque.
- Texel directions and probe origins are jittered per frame with R2 and R3 sequences ([R2](supporting_techniques.md#sampling-and-noise)), the same offset for all probes in a frame; the paper describes this as one `R_5` sequence.

**Merge and temporal reuse** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#merge-and-temporal-reuse)):

- The parent probe is simply `child/2`, with no spatial interpolation. Each texel takes the mean of its 4 child directions, gated by its own visibility: `dst += mean(r0..r3)·(1 − vis)`.
- The blend with the previous frame is `blend = max(1/(history + 1), 0.033)`. Probes with almost no history are filled from the average of their 6 face neighbours' previous values.
- An optional bias exponent blends in a power domain to lean toward the larger value, reducing underestimation and fireflies at the cost of noise.
- The path tracer reads `dst + 0.05·local_mean`, floored at 0.01, so no direction gets zero guiding probability.

**Guiding** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#guiding)). To sample a bounce, the path tracer starts at cascade 0, picks one 2×2 texel block by weighted reservoir sampling over radiance times the BSDF (diffuse and an LTC-fitted GGX lobe integrated over each quad), then descends into the chosen block's children at the next cascade, adjusting the weights by the accumulated transmittance. The final direction is uniform inside the chosen finest texel. The same structure gives the PDF for multiple importance sampling with next-event estimation.

**The `rcpg` branch** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#the-rcpg-branch)):

- It shares the trace, merge and sampling code and adds texel sampling modes (uniform, BRDF and hybrid), a BRDF texel sampler, a visualizer, a path-guiding stub and a replication note listing the implementation files.
- Its `rcpg.cfg` sets grid size 7, `c0` 4, no recursion, uniform texel sampling, ray depth 3 and 19 samples, and leaves the temporal ratio at the stage default. Defaults disagree between layers: the command line has temporal ratio 0.033, recursion on and hybrid sampling, while the stage itself has 0.005, recursion off and uniform sampling.
- The interval code uses angle index `i = c + msb(c0) − 2`, `l = 2^(c−1)·E/2^L` and `t_max = l/(2·sin θ_i)`, then doubles `t_max`. The memory estimate counts 5 bytes per texel.
- Guided sampling is the only active sampler: next-event estimation is combined by MIS with the RC PDF, and a single-sample MIS alternative is compiled out. Without the bias exponent the merge takes `max(prev, dst)`.

### Derived points

- **Table 1 is the code's formula.** The intervals equal `t_n = l_n/sin θ_{n+1}` within 0.5%, with `l_n = 2^n·1.01·E/128` the cascade-`n` cell edge and `θ` from the angle table. In cell edges of their own cascade the intervals end at 1.41, 3.16, 7.07, 15.0 and 31.1; in cascade 0 cells at 1.4, 6.3, 28.3, 120 and 497. Cascade 0 reaches only about one and a half cells, and the ratio between successive bounds falls from 4.48 toward 4.13, approaching the `4^n` of the derivation ([notes](../sources/2026_tauray_rcpg_path_guiding.md#for-rc)).
- **Cascade 0's interval against the other rules.** Its end at 1.41 cells sits between the equal-error rule's 1.13 spacings for 16 directions and the diagonal rule's 1.73 ([choosing cascade 0](core_theory.md#choosing-cascade-0-derived-and-reported)); the undoubled conservative bound would be 0.71 cells, well below the diagonal. The diagonal rule protects interpolation between ray ends, which RCPG does not do, since its parent lookup is nearest-neighbour (inference).
- **Live probes and memory.** Live probes are 3.0 to 7.3% of all probes, but active memory is 4.5 to 12.9% of the allocation, about 200 to 280 bytes per live probe. Coarse probes hold more texels and are live more often, so memory concentrates in the upper cascades (inference, reading the active memory as live texels at 5 bytes).
- **Trace throughput.** Read that way, the live texels number 5.4 to 8.0 million indoors and 2.8 million in Rungholt, and the one-bounce trace handles 6.5 to 9.1 billion texels per second indoors and 1.7 billion in Rungholt, each texel one ray plus an optional light-tree shadow ray, on an RTX 3090 with ray queries (inference). That sits near Dell'Ova's 6.1 to 7.0 billion rays per second for screen-probe DXR on an RTX 3080 ([theses](3d_screen_space_theses.md)).
- **Build cost follows surface area.** Each doubling of the cascade 0 grid multiplies build time by 1.67, 2.4, 3.83 and 4.39, rising toward the 4× that surface area grows and far below the 8× of the volume; with culling, a dense address space costs what a sparse surface set costs (inference). Each 4× more cascade 0 texels multiplies it by 2.86 and 3.93, approaching linear.
- **The bound is a direction-fidelity criterion,** the angular counterpart of the penumbra condition: it asks when a texel can stand for its direction from anywhere in its cell, which is the question a 3D merge with spatial interpolation faces too. Standard RC's `2^n` intervals violate it and rely on diffuse integration to hide the error; any use that reads directions from the cascades (specular, guiding, directional shading) inherits that error (inference).
- **The one temporal dependency.** The method leans on temporal reuse in exactly one place, the moving average that turns one jittered ray per texel into a cell- and texel-integrated value, and the paper's own replacement is a cone or beam integral per texel in one sample (inference). At stationarity an exponential moving average with `α = 1/30` has the variance of `(2 − α)/α = 59` samples, so reaching the same noise in one frame by brute force means about 59 rays per texel, 37 to 58 ms of trace indoors on the RTX 3090 (derived). A single-frame 3D RC faces the same requirement and has to get the cell-and-cone integral from rays traced in that frame, through pre-averaging several rays per texel or a cone-traced representation ([cascade layout](cascade_layout_and_merging.md)) (inference).
- **Cost reference for world-space 3D RC with hardware ray queries.** Building 128³ with 4×4 texels and 5 cascades, one ray per live texel, costs 1.0 to 1.9 ms on an RTX 3090 for 71k to 176k live probes, 2.9 to 4.0 ms with voxelization, and 1.4 to 2.2 ms for recursive two-bounce cascades. Build time grows about 2.9× and 3.9× for each 4× more texels at cascade 0, and 4.4× from 128³ to 256³ (derived). RGB radiance for lighting instead of luminance would hold 41 to 61 MiB of live RGBA16F texels indoors, or half that in R11G11B10 (derived).

## vlam

https://github.com/entropylost/vlam (entropylost, 2025-04, no licence) is a 2D path tracer through refracting circles that picks its direction by descending six cascades of stored luminance (4 to 4096 angle bins), choosing one of 4 children at each level in proportion to the stored values, and depositing each path segment's radiance back into the matching cascade ([notes](../sources/2026_tauray_rcpg_path_guiding.md#vlam-entropylost)). A sample's density is the product of its choices, so the path weight divides by `4·w` per level, `w` being the chosen child's share ([survey](../sources/2026_rc_repository_survey.md#2d-variants-worth-knowing)). There is no merge pass and, despite the repository description, no light sampling. The project is written in Rust, and the community wiki files it under "RC-guided NEE", a pathtracer in which RC augments ray tracing rather than replacing it ([wiki](../sources/2026_rc_community_site_and_wiki.md#rc-guided-nee)). The deposit makes the cascades a learned guiding distribution trained by the paths themselves, the role an SD-tree plays in offline path guiding ([path guiding](supporting_techniques.md#resampling-and-sampling-theory)) (inference). entropylost also wrote amida, amitabha and hrcviz ([2D implementations](2d_implementations.md), [HRC](holographic_rc.md)).

## Cascades and light sampling

No source uses RC to guide next-event estimation itself. What exists is the split between the cascades and explicit light sampling:

- RCPG keeps point and directional lights out of the cascades because texels are too coarse for them, shades probe hits with one light-tree sample and a shadow ray, and combines NEE with the RC PDF by MIS in the `rcpg` branch. Its sun experiment (8 spp with the sun in the cascades losing to 4 spp with NEE) measures the cost of putting a small, bright light into texels.
- vlam is filed as RC-guided NEE by the wiki and promises light sampling in its repository description, but its code guides path directions and samples no lights.
- Reservoir Cascades stores, with each sample, the emitter point and its luminance `e0`, and its validation rays test visibility from the child probe to that point. A stored sample with an emitter point and a shadow test toward it is the shape of a light sample, generated by the cascade rather than by a light list (inference).
- The 3D world-space builds that light small emitters analytically make the same split for the same reason ([3D world space](3d_world_space.md#connections)).

Every source that meets lights smaller than cascade 0 resolves moves them to a direct term outside the cascades (inference, from RCPG's Fig. 8 and the world-space builds; the rule is the [penumbra condition's](core_theory.md#choosing-cascade-0-derived-and-reported) smallest resolvable light).

## Methods compared and cited

The two papers measure against, or build on, the methods below. Details marked "abstract" come only from a paper's abstract; VXPG's come from its code.

**VXPG** (Lu, Chang, Hedstrom and Li, "Real-time Path Guiding Using Bounding Voxel Sampling", ACM TOG 43(4), SIGGRAPH 2024, [DOI 10.1145/3658203](https://doi.org/10.1145/3658203); [code](https://github.com/SuikaSibyl/vxpg)) is RCPG's main baseline. Each frame it injects irradiance from light-path vertices into a world-space voxel grid, compacts the populated voxels, clusters them into supervoxels seeded by k-means++ over visibility bitfields, and merges the clusters into a tree that stores a bounding box and an irradiance sum per node. A path vertex samples a direction toward a cluster's bounding voxels (the shader calls it "voxel to sphere"), and the GI pass combines that with BSDF sampling by two-technique MIS under the balance or power heuristic. The code's default grid is 64 voxels along each axis of the world bounding box, with a 65,536-entry hash map; RCPG ran it at 128³ with multi-sample MIS. The structure is rebuilt from the current frame's light paths, which is why its error is flat from the first frame in RCPG's convergence plot and why its stochastic injection flickers (inference from the RCPG evaluation above).

**SSPG** is RCPG's screen-space guiding baseline, measured only at one bounce. The notes do not name its paper. Screen-space real-time guiding methods of this kind include Derevyannykh's per-pixel Gaussian-and-BRDF mixture trained online by EM (Eurographics 2022 short paper, [arXiv 2112.09728](https://arxiv.org/abs/2112.09728)) and the vMF mixtures of Dittebrandt et al. ("Markov Chain Mixture Models for Real-Time Direct Illumination", CGF 2023), which Alber, Hanika and Dachsbacher extend with world-space hash grids to global illumination ("Real-Time Markov Chain Path Guiding for Global Illumination and Single Scattering", I3D 2025, [DOI 10.1145/3728296](https://doi.org/10.1145/3728296)). Of these, the last two appear in RCPG's reference list.

**World-space ReSTIR** (Boissé, "World-Space Spatiotemporal Reservoir Reuse For Ray-Traced Global Illumination", SIGGRAPH Asia 2021 Technical Communications, [DOI 10.1145/3478512.3488613](https://doi.org/10.1145/3478512.3488613), [PDF](https://gpuopen.com/download/SA2021_WorldSpace_ReSTIR.pdf)) is the model for Reservoir Cascades' flat control.
- It caches the reservoirs of path vertices in the cells of a hash grid built on the GPU every frame: count, prefix sum, then scatter into a flattened list per cell.
- The table has 100,000 cells of up to 32 entries, found by a 32-bit checksum with linear probing, with pcg and xxhash32 as the two hashes ([hashes](supporting_techniques.md#sampling-and-noise)).
- Temporal reuse reads last frame's grid. Spatial reuse picks a random subset of 4 reservoirs from the cell. Cell descriptors are jittered, cell size adapts, and a per-reservoir normal test limits bias.
- The method covers single-bounce diffuse GI. At half resolution from 1080p, 1 spp and 16 initial samples, the Hangar scene costs 0.298 ms to generate reservoirs, 0.252 ms to build the grid, 0.318 ms for one temporal pass and 1.051 ms for four spatial passes on an RX 6900 XT, 1.919 ms in all; the RTX 3080 totals 2.901 ms (0.429, 0.265, 0.509 and 1.698 ms) (sums derived). Memory is not reported.
- Reservoir Cascades' control and this cache share one cell scale per position. The cascade version makes the reuse cell grow with interval distance instead (inference).

**BRDF importance sampling for polygonal lights** (Peters, ACM TOG 40(4), Article 140, SIGGRAPH 2021, [DOI 10.1145/3450626.3459672](https://doi.org/10.1145/3450626.3459672), [project](https://cg.ivd.kit.edu/polygonal_lights.php)) is the in-texel sampler RCPG offers as its alternative to uniform sampling.
- For diffuse surfaces it samples a polygon in proportion to projected solid angle. The polygon is clipped exactly to the hemisphere `z ≥ 0`, partitioned, and sampled by inverting its distribution, which converges cubically in two iterations.
- For glossy surfaces it samples [LTC](supporting_techniques.md#shading) lobes and combines the two strategies with variants of optimal MIS. It is unbiased, unlike closed-form LTC shading, and leaves almost no variance outside penumbrae for Lambertian lights (abstract).
- Its Fig. 1, on an RTX 2080 Ti at 1440² and 2 spp, shows RMSE 0.144 at 1.47 ms for projected solid angle plus LTC under clamped optimal MIS, against 0.225 at 0.91 ms for projected solid angle plus BRDF sampling under the balance heuristic (values matched to labels by their order in the caption). Per unit time that is about 1.5 times the efficiency, `1/(RMSE²·t)` (derived).
- A cascade texel's solid angle is a spherical quadrilateral, so a polygonal-light sampler draws exactly inside it and never below the horizon. That exactness is what RCPG measured as 25% slower for a 0.0005 SSIM gain (inference from Fig. 22 above).

**ReSTIR follow-ups that Reservoir Cascades cites.** The base methods, RIS, ReSTIR, ReSTIR GI and GRIS, are in the [glossary](supporting_techniques.md#resampling-and-sampling-theory); Talbot et al.'s RIS paper (EGSR 2005, [DOI 10.2312/EGWR/EGSR05/139-146](https://doi.org/10.2312/EGWR/EGSR05/139-146)) reports 10 to 70% variance reduction. The others:

| Work | What it adds | Venue |
|---|---|---|
| Majercik et al. 2021, DDGI resampling | Prior work on combining a probe cache with resampling ([related probe GI](related_probe_gi.md#ddgi-resampling)) | arXiv 2108.05263 |
| Durand et al. 2005, frequency analysis of light transport | Occlusion is a convolution in the Fourier domain and free propagation a shear, the basis of the penumbra condition's frequency reading | ACM TOG 24(3), SIGGRAPH 2005 |
| Wyman et al. 2023, a gentle introduction to ReSTIR | Course notes on the method | SIGGRAPH Courses |
| Kern et al. 2024, ReSTIR FG | Photon final gathering with spatiotemporal resampling, aimed at caustics (abstract) | EGSR 2024, [DOI 10.2312/sr.20241155](https://doi.org/10.2312/sr.20241155) |
| Liu et al. 2025, reservoir splatting | Forward-projects the previous frame's primary hits instead of back-projecting, which keeps temporal reuse under motion blur (abstract) | SIGGRAPH 2025, [DOI 10.1145/3721238.3730646](https://doi.org/10.1145/3721238.3730646) |
| Hedstrom et al. 2026, stochastic pairwise MIS | Unbiased reuse over large kernels in real time (title and abstract) | CGF 45, EG 2026, [DOI 10.1111/cgf.70391](https://doi.org/10.1111/cgf.70391) |
| Junkins et al. 2026, compatibility-guided neighbor selection | Picks reuse neighbours by sample compatibility: SMAPE down 6 to 29% and temporal covariance down 22 to 49% for 2 to 5% more cost (abstract) | Proc. ACM CGIT 9(4) Art. 52, HPG 2026 best paper, [DOI 10.1145/3820024](https://doi.org/10.1145/3820024) |

Hedstrom's and Junkins's papers attack the same problem as Reservoir Cascades, choosing which neighbours to reuse, from inside flat ReSTIR. The cascade answers it by scale, they by weighting and selection (inference).

## Connections

- **One error parameter.** Reservoir Cascades measures every bias in `ε_n = √2·s_{n+1}/t_{n+1}`, the parallax of a parent's diagonal seen from its interval start, and RCPG bounds its intervals by `θ_min ≈ l/t`, the parallax of a cell's inscribed circle. Both are the ratio of probe spacing to interval distance that the penumbra condition's spatial criterion constrains, read as an angle (derived).
- **Three arguments, one scaling.** Split RC's equal-error criterion, Reservoir Cascades' alignment lemma and RCPG's Nyquist parallax bound select the same interval scaling, `l = 2·K^(1/m)`: `K = 2, l = 4` in 2D and `K = 4, l = 4` in 3D. Off that scaling, parallax in bin units doubles per cascade ([core theory](core_theory.md#parallax-in-bin-units-derived)) (derived).
- **Both replace bilinear interpolation of radiance.** RCPG takes the nearest parent and makes each texel a cell-and-cone average by jittering origins and directions; Reservoir Cascades keeps the bilinear weights only as a proposal and re-anchors the selected sample to the child. Both treat interpolating radiance between probes as the error that matters once directions are read, not only irradiance (inference).
- **Validation is the bilinear fix with rays.** Reservoir Cascades' renormalize-before-select is the visibility form of the 2D bilinear fix, the same family as hit bits, erhe's visibility rays and parent hit-distance tests ([world-space leak defences](3d_world_space.md#leak-defences-in-world-space)). Its measured kill-after-select shrink (−16 and −33%) shows that the order of the test and the weighting matters in any of them (inference).
- **Scale-matched reuse.** The flat control's failures are the probe-GI problem in reservoir form: shared samples carry their source's visibility, so a flat kernel either leaks or, validated, loses penumbra energy. The cascade's reuse radius growing as `2^n` is the penumbra condition applied to reuse, as probe grids with Chebyshev tests ([related probe GI](related_probe_gi.md)) and world-space ReSTIR caches ([related radiance caches](related_radiance_caches.md)) lack (inference).
- **Temporal state scales with the cascade.** Reservoir Cascades caps confidence as `8·2^n` because far levels change more slowly, and RCPG notes that coarser cascades more often have history; both give the upper cascades the longest memory, which in a single frame means the upper cascades are where averaging over rays is cheapest to replace by other means (inference).
- **Jitter and pre-averaging.** RCPG's jittered origins and directions are pre-averaging spread over frames; block-consistent interval jitter is an interval overlap spread over frames. A single frame needs both done spatially: several rays per texel, and blended or overlapping interval boundaries ([gaps and seams](artifacts_and_fixes.md#gaps-and-seams-between-cascades)) (inference).
- **A merged cascade is a direction hierarchy.** After RCPG's top-down gather each texel holds all light from its direction, so cascades 0 upward form a fixed directional quadtree over each region, the structure an SD-tree learns adaptively. Sampling descends it as a light tree is descended ([glossary](supporting_techniques.md#resampling-and-sampling-theory)) (inference).
- **Near and far splits.** Reservoir Cascades proposes HRC far fields with stochastic near fields; RCPG keeps small lights in NEE; both separate the part of the field the cascades represent well from the part they do not ([HRC](holographic_rc.md)) (inference).

## Single-frame assessment

- **Neither method is single-frame.** RCPG's texels are moving averages of one jittered ray per frame (`α = 1/30`, about 59 samples' worth). Reservoir Cascades' production form needs temporal reservoirs and block jitter, and the paper itself says one candidate per bin is noisy and presumes accumulation or denoising. Its per-frame error without temporal reuse is not reported; extrapolating its flicker fit to no history gives a temporal coefficient of variation near 1.9 in S3 (inference, from four measured caps).
- **The deterministic parts carry over.** Without history these pieces still apply: visibility-validated parents renormalized before weighting (at `ρ = 1`, leak 0.1% for +33 to 53% rays in 2D, at the price of 86% recovery in the sub-bin case); the reprojected bin lookup through `t_c`; the reconnection Jacobian `r_q²/r_p²` in 3D parent weights; and the diagnosis of the leak ring at interval starts. In 3D a validated merge tests up to 8 parents per escaped child, against 4 in 2D, so its ray cost roughly doubles where the shadow-ray budget is already the expensive part (inference).
- **3D with `K = 4, l = 4` avoids the alignment problem.** Lemma 2's growing shift comes from ×4 bins per level in 2D; in 3D with ×4 directions (×2 per axis) and ×4 intervals the shift stays constant, so a 3D lift at Split RC's scaling would need neither the window nor deeper reprojection (derived, [core theory](core_theory.md#parallax-in-bin-units-derived)).
- **Interval-boundary bias needs a spatial fix.** Block jitter turns the boundary bands into variance only across frames. A single frame needs overlapping or blended interval boundaries, or validation at the boundary, which removed the leak ring entirely at `ρ = 1` (inference).
- **RCPG prices a world-space cascade.** With hardware ray queries, a culled 128³ volume with 16 directions at cascade 0 builds in 1.0 to 1.9 ms on an RTX 3090 at one ray per texel. Matching its averaged quality in one frame by brute force would cost about 37 to 58 ms, so a single-frame version needs integrated texels from cone or beam tracing through a prefiltered scene, or several rays per texel at lower resolution ([scene representation](scene_representation_and_tracing.md)) (derived and inference).
- **Mapping onto `RenderingDevice`.** The live-probe list and `ceil(live·dirs/64)` indirect dispatches map onto Godot's indirect compute dispatch; RCPG's per-texel ray query does not, since compute shaders cannot trace and only the experimental Vulkan ray tracing pipeline can; its geometry-shader voxelization needs another route; and its 310 MiB dense allocation exceeds the 128 MiB storage-buffer range Vulkan guarantees, so the cascades belong in textures or split buffers, as tauray's 2D array textures already are ([RenderingDevice notes](../../docs/rendering_device.md)) (inference).
- **Guiding is outside a pure-RC design,** since it feeds a path tracer. What it offers a single-frame RC is the descent sampler over a merged cascade, which could importance-sample a near-field pass (cascade −1 or screen-space rays) or specular rays from the same frame's cascades (inference, untested).

## Open questions

- Does a deterministic form of the RIS merge (all four or eight parents kept, weighted by validated `β·J`) keep Reservoir Cascades' leak reduction without its selection noise, and does Proposition 3's `O(ε_n)` bias bound still hold for it?
- What is merge-as-RIS's per-frame error with no temporal reuse, against vanilla RC at equal rays?
- How many of the 8 parent validation segments does a 3D merge need, and can stored hit distances replace them as the free test does in world-space builds?
- Is Split RC's 3D scaling (`K = 4, l = 4`) enough to drop reprojected parent lookups altogether, as the bin-shift scaling predicts, and does the leftover constant shift still need correcting?
- Can interval-boundary bias be removed in one frame by overlapping or blended intervals at a cost below block jitter's history?
- Can RCPG's cell-and-texel average come from one cone or beam trace through a prefiltered voxel or distance-field scene within a few milliseconds?
- How does a culled dense volume like RCPG's build on a compute tracer under `RenderingDevice`, and does its cost still follow surface area?
- Can a merged cascade's descent sampler importance-sample cascade 0 or near-field rays inside the same frame, and does that reduce single-frame noise at equal rays?
