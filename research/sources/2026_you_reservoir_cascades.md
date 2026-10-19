# Reservoir Cascades: Principled Multi-Scale Sample Reuse by Resampling Radiance Cascade Merges

| | |
|---|---|
| Author | Ivan You |
| Date | 2026-07-23 |
| Kind | preprint |
| Link | https://doi.org/10.5281/zenodo.21520422 |

This is version 2 of the preprint (file reservoir-cascades-preprint-v2.pdf, 10 pages). The concept DOI for all versions is 10.5281/zenodo.21506521. The Zenodo record holds only this PDF; the code is at https://github.com/ivanyou028/reservoir-cascades (MIT, read at 15b4557), described at the end of this note. The paper keeps the Radiance Cascades (RC) discretization, rewrites the level merge as a GRIS-style resampling step, and tests the result on three 2D scenes with a CPU oracle and a WebGPU build.

## Contents

- [Abstract (restated)](#abstract-restated)
- [1 Introduction](#1-introduction)
- [2 Related Work](#2-related-work)
- [3 Background and Notation](#3-background-and-notation)
  - [Cascade discretization](#cascade-discretization)
  - [Estimand](#estimand)
  - [GRIS in brief](#gris-in-brief)
- [4 Method](#4-method)
  - [Reprojected bin lookup](#reprojected-bin-lookup)
  - [Per-level collapse (layered RIS)](#per-level-collapse-layered-ris)
  - [Validation: renormalize before selecting](#validation-renormalize-before-selecting)
  - [Merge as RIS, with beta in the proposal and never in the target](#merge-as-ris-with-beta-in-the-proposal-and-never-in-the-target)
  - [Temporal reuse, re-evaluation, and revival](#temporal-reuse-re-evaluation-and-revival)
  - [Block-consistent interval jitter](#block-consistent-interval-jitter)
  - [Per-frame algorithm (Figure 2, transcribed)](#per-frame-algorithm-figure-2-transcribed)
  - [Degenerate mode](#degenerate-mode)
- [5 Theory](#5-theory)
- [6 Experiments](#6-experiments)
  - [Setup](#setup)
  - [Main results (Table 1)](#main-results-table-1)
  - [Cost accounting](#cost-accounting)
  - [Where the rho-dial recovery cost lives](#where-the-rho-dial-recovery-cost-lives)
  - [Equal-ray attribution (Table 2)](#equal-ray-attribution-table-2)
  - [Flat world-space control (Table 3)](#flat-world-space-control-table-3)
  - [Dynamics (S3)](#dynamics-s3)
  - [The leak ring: residual bias with a predicted address](#the-leak-ring-residual-bias-with-a-predicted-address)
  - [WebGPU](#webgpu)
  - [Negative results](#negative-results)
- [7 Discussion and Limitations](#7-discussion-and-limitations)
  - [Scope](#scope)
  - [Hypotheses and constants](#hypotheses-and-constants)
  - [Design axes exposed by the theory](#design-axes-exposed-by-the-theory)
- [8 Conclusion](#8-conclusion)
- [Source inconsistencies and unclear items](#source-inconsistencies-and-unclear-items)
- [Links found](#links-found)
- [Code](#code)

## Abstract (restated)

RC discretizes radiance over a hierarchy of probes and angular bins, with spatial and angular resolution following the penumbra condition. Levels are merged by deterministic bilinear interpolation. The paper argues that this merge causes biases that more samples cannot remove: light leaks, ringing, a hard per-level angular resolution ceiling, and a visibility-radiance factorization error.

The paper keeps the discretization and moves the bilinear weights out of the target and into the selection weights of a GRIS-style merge over the four parent reservoirs. Errors in those weights then cost variance rather than bias.

Reported results on canonical failure scenes, at an identical candidate-ray budget:

- Leaks drop to 0 to 11 percent of vanilla RC's leaked energy. Validation shadow rays add at most 20 percent extra rays.
- Sub-bin emitters that vanilla RC loses are recovered at 93 to 101 percent of reference energy.
- Dynamic lights adapt in about 3 frames.

An equal-budget flat world-space reuse control isolates what the hierarchy contributes. Theory sections give orders and scalings under an explicit bounded-radiance hypothesis. Leading constants are labelled as measured calibrations. The paper also reports two failure modes and three negative results. A CPU oracle, whose degenerate mode reproduces vanilla RC bit-exactly, and a 120 fps WebGPU implementation are said to accompany the paper; both are in the repository.

## 1 Introduction

Real-time global illumination is described as following two largely separate lines. RC [13, 11] uses a probe hierarchy in which spatial density halves and angular density quadruples per level, following the penumbra condition: radiance from distance r varies spatially on scale proportional to r and angularly on scale proportional to 1/r. The paper calls this a discrete analogue of light-transport frequency analysis [3]. The data structure has fixed cost, is geometry-agnostic, and lives in world space.

RC merges levels by deterministic bilinear interpolation, which asserts that a parent probe's value equals the child's value. The paper lists the consequences: light leaks through thin occluders, ringing from deterministic ray placement, a per-level angular resolution ceiling that destroys small bright emitters, and a visibility-radiance factorization error.

ReSTIR-family estimators [1, 12, 8] reuse samples across pixels and frames with resampled importance sampling and proper weights, so structural error shows up as variance. The paper says the machinery around these estimators is ad hoc: reuse neighborhoods are hand-tuned kernels, screen-space temporal reuse must handle motion vectors and disocclusion, and reuse under a visibility-free target carries a bias that GRIS's correctness notes call real but leave unbounded [8].

The paper's contribution is a mechanism. RC's discretization is kept. Interpolation is demoted from an assertion to a proposal. The bilinear weights beta_q move into the resampling weights of a GRIS merge over the four parent reservoirs, where errors cost variance. They are removed from the target, where errors would cost bias. The paper says this one change converts each structural RC bias into variance that reuse can amortize.

The theory is said to explain why the cascade is the right structure for this, not to certify tight constants.

Contributions as listed in the source:

1. A unified estimator framework. Vanilla RC is the exact degenerate case, verified bit-exactly against an independent RC implementation. The merge becomes GRIS-style resampling with per-parent reprojected bin lookup, per-level contribution-weight collapse (no cross-level W products), validation as renormalized visibility re-evaluation, and temporal reuse with sample re-evaluation and revival (section 4).
2. Practice (section 6). On canonical failure scenes, leaks drop to 0 to 11 percent of vanilla's leaked energy at an identical candidate-ray budget, with validation shadow rays counted explicitly. Both acceptance bars clear at 20 percent or less extra rays. Sub-bin emitters are recovered at 93 to 101 percent energy. Dynamic lights adapt in about 3 frames. An equal-budget flat world-space reuse control (Table 3) fails in three ways: leak, validation collapse, and weight-chain divergence. The cascade closes each of these structurally. A 120 fps WebGPU build reproduces the CPU oracle metrics.
3. Theory (section 5). The merge is mapped onto GRIS condition by condition. Its coverage bias is identified as a violation of GRIS's coverage condition. The visibility gap is identified as GRIS's "unoccluded target" problem, and the paper gives an O(eps_n) bound that GRIS's analysis leaves open. The paper gives a depth-uniform variance non-amplification theorem and an AR(1) model of the temporal reservoir. Two negative results are proved: bin-space parallax grows as 2^n in bin units under x4 angular branching, and per-frame interval jitter is incompatible with temporal reuse.

## 2 Related Work

Radiance Cascades. Sannikov [13] introduced RC for real-time 2D and screen-space GI, shipped in Path of Exile 2. Osborne and Sannikov [11] formalized the merge operator and the penumbra criterion for non-LTE radiative transfer. Holographic Radiance Cascades [4] take a more deterministic route with single-shot transfer and no stochastic rays. The paper calls it orthogonal, and says combining HRC far fields with its stochastic near fields is future work.

Community implementations reduce merge artifacts with the "bilinear fix", which reprojects parent rays through child ray endpoints. The paper calls its reprojected bin lookup the RIS counterpart of this fix. Lemma 2 and Proposition 2 state what the fix can and cannot correct. Measured as a baseline (Table 1), the fix removes only the misalignment component of error: lit-region MAPE halves, but 95 percent of the leak remains, which the paper attributes to merge-semantics bias.

## 3 Background and Notation

### Cascade discretization

All lengths are in pixels. The scene is 2D ("flatland").

- Level n is in {0, ..., N-1}.
- Probe spacing: s_n = s0 * 2^n. Probes sit at (i + 1/2) * s_n.
- Angular bins: B_n = B0 * 4^n, each of angular width 2*pi / B_n.
- Radial interval: [t_n, t_{n+1}) with t_n = t0 * (4^n - 1) / 3. The intervals are contiguous from 0, and interval n has length t0 * 4^n.
- Defaults: s0 = 1, B0 = 4, t0 = 4.

### Estimand

Along a ray, radiance decomposes recursively over intervals:

- L_{>=n} = L_{[t_n, t_{n+1})} + V_{[t_n, t_{n+1})} * L_{>=n+1}

The text does not define the interval terms L_[a,b) and V_[a,b) beyond this recursion. Prop. 3 writes V(p, y) for visibility.

The reservoir at (probe p, bin b, level n) estimates the bin mean of p's own field, not an interpolated field:

- Lbar_n(p, b) = (1 / |Omega_b|) * integral over Omega_b of L_{>=n}(p, omega) d omega

The source says this choice is what moves the bilinear weights into the proposal.

### GRIS in brief

- A random X with unbiased contribution weight W satisfies E[f(X) W] = integral over supp X of f.
- Samples X_i from domains Omega_i are merged into a target domain Omega through shift maps T_i (bijections on subsets).
- Resampling weights: w_i = m_i(T_i X_i) * p_hat(T_i X_i) * W_i * |dT_i / dX_i|.
- The selected sample Y = T_s X_s carries W_Y = (sum over j of w_j) / p_hat(Y).
- Unbiased integration over supp Y = supp p_hat intersected with the union over i of T_i(supp X_i) needs MIS weights that form a per-point partition of unity over the realizing techniques.
- Convergence and finite-variance bounds also need coverage (supp p_hat is inside supp Y) and a bounded-ratio target.
- Canonical samples, drawn by importance sampling p_hat directly, are GRIS's device for coverage. The paper's tail merge has none.

## 4 Method

Each frame has three phases: candidate generation (one jittered ray per reservoir, tracing only its own interval), a top-down merge (n = N-1 down to 0), and a gather from level 0. Figure 1 shows the merge, and Figure 2 gives the full per-frame algorithm.

### Reprojected bin lookup

- The bin to consult in each parent is chosen per parent by reprojection through the child's characteristic far point:
  - z = p + t_c * omega, with t_c = sqrt(t_{n+1} * t_{n+2}).
  - Parent q consults bin_{n+1}(dir(q -> z)).
- A single shared bin fails at depth. Parallax, measured in bin units, grows as 2^n under x4 branching (Lemma 2, Fig. 4). Misaligned parents return darkness. The paper measured this as 2x column striping before the fix.

### Per-level collapse (layered RIS)

- The selected tail is resolved to a value at once: L_tail_hat = c_s * W_s.
- The child stores c = c_near + L_tail_hat, with a fresh UCW for its own domain only.
- No W crosses a level boundary. The paper says an N-level chain of multiplied random W values would have exponentially growing variance. Collapsing per level keeps each level's RIS closed. Unbiasedness follows by induction, and variance follows from Theorem 2.
- The stored target is p_hat = lum(c) + lambda. This keeps the estimator's value/target ratio at or below 1 (the chromaticity bound). Section 5 turns this into a zero-selection-variance property.

### Validation: renormalize before selecting

- With probability rho per merge, each parent's reconnection segment [t_{n+1}, |y_q - p|) is shadow-tested from p (Fig. 3b).
- A blocked parent leaves the proposal set, and beta is renormalized over the survivors.
- If all four parents are blocked, the tail is zero ("true umbra"), so leaks are not filled in.
- Order matters. Killing after selection multiplies the estimate by the visible-beta fraction v_p. The paper measured this as an O(1) shrink, at -16 percent and -33 percent. The reason is that the cascade chain already bakes each parent's visibility into sample existence.
- Renormalizing before selection compensates for that embedded factor. Its residual bias is O(eps_n) (Prop. 3), measured at -2.2 percent.

### Merge as RIS, with beta in the proposal and never in the target

For a child (p, b, n) whose candidate escaped its interval, the tail L_{>=n+1}(p, omega) is resampled from the four bilinear parents q:

- w_q = m_q * p_hat(c_q) * J_q * W_q, with p_hat(c) = lum(c) + lambda.
- c_q and W_q are parent q's stored, already collapsed radiance and UCW.
- J_q = r_q / r_p is the 2D reconnection Jacobian. Its kept point is y_q, and it is never hard-coded to 1. The source notes level 0 to 1 has the largest s/t.
- lambda > 0 is a defensive floor. The text gives no value; the code uses 0.05 (`core/restir.h:32`).
- m_q is the bilinear weight beta_q, renormalized under validation.
- The target is the luminance of p's own field. Reconnection re-anchors every parent sample to p, so all four techniques estimate the same quantity. beta_q is only a selection prior. A wrong beta costs variance, not bias.

The source gives the reconnection geometry as: r_p = |y - p|, r_q = |y - q|.

### Temporal reuse, re-evaluation, and revival

- Reservoirs merge with their previous-frame state under a confidence cap: M_n = min(m0 * 2^n, M_max). The paper says far levels are temporally smoother ("temporal penumbra condition"). The text gives no M_max; the code uses M_max = 64 and m0 = 8 (`core/restir.h:33-34`, `core/restir.cpp:559-561`), so the cap reaches 64 at level 3.
- Each stored sample keeps an immutable as-resolved radiance c_ref and an emitter luminance e0 at its reconnection point.
- Each frame the live value is re-evaluated as c = c_ref * lum_now(y) / e0.
- Without re-evaluation, a luminance-proportional target keeps preferring stale bright samples. The paper measured zero response 48 frames after a light turned off.
- Because c_ref is never overwritten, a geometrically valid sample revives as soon as its emitter returns. The paper calls this impossible in screen space.
- Scene changes raise a frame-indexed dirty flag that hard-resets M. The paper says this is unbiased, since it does not depend on any sample draw. Candidate-triggered clamps are biased (+25 percent) and were reverted.

### Block-consistent interval jitter

- The interval boundaries t_n are scaled by a log-uniform factor 4^(xi - 1/2), where xi is a random draw. The text does not state the range of xi; the code draws xi uniform on [0, 1) once per block (`core/restir.cpp:85-88`), so the level-0 split length lies in [t0/2, 2·t0).
- The scale is resampled every K frames. The text does not give a numeric K; the code uses K = 8 (`core/restir.h:55`), matching the experiments' "boundary-jitter block 8". The WebGPU page defaults to 9999 frames, which leaves the split fixed in the browser.
- Stored radiance bakes in the split, and mixing splits double-counts interval overlaps. Per-frame jitter was measured at 3x leak inflation.
- Within a block the cascade is consistent. At block switches the temporal history is dropped (frame-indexed, unbiased).
- The jitter converts the deterministic interval-boundary bands into variance that frame averaging removes. The fan-energy ratio moves from 0.91 to 1.003.

### Per-frame algorithm (Figure 2, transcribed)

Step 1, candidates. All levels run in parallel. Each (p, b, n):

- omega <- jitter(Omega_b)
- trace [t_n, t_{n+1})
- store (omega, hit, c_near)

Step 2, top-down merge for n = N-1, ..., 0. Each escaped (p, b, n) with n < N-1:

- z <- p + t_c * omega, with t_c = sqrt(t_{n+1} * t_{n+2}). This is the reprojected lookup.
- For each parent q: b_q <- bin_{n+1}(dir(q -> z)).
- With probability rho: shadow-test p -> y_q on [t_{n+1}, |y_q - p|). Drop blocked parents and renormalize beta over the survivors before selecting.
- RIS over survivors: w_q proportional to beta_q * p_hat(c_q) * (r_q / r_p) * W_q.
- Selected parent: c_sel, W_sel. Then c <- c_near + c_sel * W_sel. This is the per-level collapse, with no cross-level W.
- R_new <- (·, w = lum(c) / pdf(omega)). The source leaves the first tuple field as a dot, and does not define pdf. Then a temporal merge with cap M_n.
- Stored samples are re-evaluated as c = c_ref * lum_now(y) / e0. This gives re-evaluation and revival.
- M <- 0 on a scene-change flag or a jitter-block switch. This is frame-indexed and unbiased.

Step 3, gather. Integrate level-0 reservoirs per pixel. The text does not give the gather weighting.

Figure 2 states that each italic margin note marks a design decision in section 4. Omitting any one of them gives a measured failure mode (section 6, negative results).

### Degenerate mode

Setting candidates to bin centers, p_hat = 1, value-passing beta-weighted merges, and no reuse reproduces vanilla RC bit-exactly. The paper checks this against an independently written implementation, and uses it as a regression gate. Each vanilla bias is localized to the degenerate step that reintroduces it.

## 5 Theory

Full proofs are in supplemental theory notes, which are not in the Zenodo record but in the repository's `docs/theory/` (`variance.md`, `integrand-mismatch.md`, `lemma-3_2.md`, `gris-anchoring.md`). The paper states the results and their dependencies.

Throughout, the scene has at most K silhouette arcs, emission is bounded by L_max (Assumption 1), and:

- eps_n = sqrt(2) * s_{n+1} / t_{n+1} <= eps_0 * 2^(-n)
- eps_0 = 3 * sqrt(2) * s0 / (2 * t0), which is about 0.53 at defaults.

Section 5 writes this bound without an extra factor. Section 1 and Theorem 1 use (4/3) times this bound (see the inconsistency list below).

Assumption 1 (bounded radiance). L <= L_max. The target is then reasonable in GRIS's sense, with C_f approximately (L_max + lambda) / lambda per level. The source says this is load-bearing for the mean bias bounds, not only for variance. A near-point emitter with O(1) energy inside an O(eps_n) strip gives an O(1) over-count. The paper constructs one, and its small-source scene is the designated stress test.

Lemma 1 (Jacobian). Under non-grazing reconnection, |J - 1| <= C_J * eps_n.

Lemma 2 (direction shift; the x4 parallax obstruction).

- |omega_p - omega_q| <= eps_n * (1 + O(eps_n)) radians. This decays as 2^(-n).
- In parent-bin units, the shift is delta_n = Theta(2^n), because bins satisfy B_n proportional to 4^n. Bin width shrinks as 4^(-n), twice as fast as parallax.
- The folklore claim that the shift stays within O(1) bins holds only for x2 branching.
- Reprojection through t_c cancels the parallax exactly at one depth and halves the worst case (residual delta'_n). The paper says it covers the n of about 3 to 4 levels its prototypes use, but gives no asymptotic result.

Lemma 3 (integrand mismatch; no Lipschitz term). Outside a penumbra set P' with |P'| <= C_1 * (K + K_t) * eps_n, reconnection re-anchors to the identical emitter point. So:

- F_p(T omega) * J = F_q(omega) * (1 + eta), with |eta| <= C_2 * eps_n^gamma.
- The emitter texture never enters. Interpolation, by contrast, pays a Lipschitz term.
- gamma = 1 for polygonal scenes. gamma = 1/2 for smooth convex obstacles, where grazing corridors force the weaker exponent.
- The paper says eps_n is pointwise tight, since it constructs the extremal corridor. But that term contributes only O(eps_n) to the aggregate mismatch, because curvature spreads grazing directions. The supplement carries the proof.
- K_t and psi are not defined in the text. The supplement defines K_t as the number of transversal obstacle-boundary crossings of the circle of radius t_{n+1} (`lemma-3_2.md:433-434`), and psi_0 as a grazing-angle threshold: off the excluded set G(psi_0), |eta| <= eps_n * (2 + cot psi_0), with psi_0 = sqrt(eps_n) for smooth boundaries and any fixed psi_0 for flat ones (`integrand-mismatch.md:202-216`).

Proposition 1 (coverage bias equals GRIS coverage violation). A single-bin lookup gives supp Y = Omega_b \ A, a strict subset of supp p_hat (GRIS Eq. 15). The merge is then unbiased for the wrong integral:

- bias = minus the integral over A of L d omega. It is always negative.
- |A| / |Omega_b| = O(eps_n).

The paper says this is not analogous to GRIS's coverage condition. It is that condition, violated.

Proposition 2 (windowed lookup restores coverage). Consulting 2w+1 bins per parent, with per-direction weights m_q(y) proportional to beta_q * 1[covered_q(y)], is a legal GRIS partition of unity. Coverage is support-determined and checkable at merge time, unlike visibility. If w >= delta'_n, then supp Y = supp p_hat exactly. The cost is (2w+1) times the read cost, with zero extra rays. The paper analyzes this window but does not implement it. All section 6 measurements are within reprojection's reach.

Proposition 3 (validation). The cascade evaluates f_parent(Y), not f_p(Y) = V(p, y) * radiance. The stored value carries the parent's visibility. This is GRIS's "unoccluded target" problem, which GRIS's Appendix B leaves unbounded.

- rho-validation is a stochastic re-evaluation of the missing V(p, y).
- Renormalize-before-select has bias O(eps_n) under Assumption 1. Off the O(eps_n)-width penumbra set, the survivor set is unanimous, so the self-normalized estimator's random denominator is deterministic there.
- Kill-after-select shrinks the estimate by the visible-beta fraction, which is an O(1) bias.
- Survivor renormalization is not itself a GRIS partition of unity, because occlusion is not non-realization. The paper says this bias must be bounded, not certified.
- Section 6 checks the localization: the energy removed by rho concentrates on the penumbra band, and the fan core is validation-neutral.

Theorem 1 (per-level reuse soundness). The merge is a GRIS instance. Its finite-variance guarantee holds through the lambda floor. Its bias has three separable O(eps_n) sources: coverage (Prop. 1), shift distortion (Lemma 3), and the visibility gap (Prop. 3). With eps_n <= (4/3) * eps_0 * 2^(-n), the total over all levels satisfies sum over n of eps_n < 3 * eps_0. The source says this is independent of N and scene scale. Reuse radius proportional to 2^n is a corollary of the penumbra condition, not a tuned hyperparameter.

Remark (coverage at depth). Theorem 1 assumes each level's lookup is coverage-complete. Reprojection alone secures this only for the about 3 to 4 levels used in the prototypes. Deeper cascades need the windowed lookup of Prop. 2, which leaves the theorem's constant unchanged.

Lemma 4 (selection noise = lambda). Conditioned on the parents, E[X^2] <= mu * (mu + lambda * Jbar).

- At lambda = 0, value-proportional RIS selection is zero-variance given its inputs. The source calls this the chromaticity bound at work.
- The defensive floor adds at most lambda * (1 + C * eps_n) * mu variance per level.
- The rare dark-selected-against-bright spike has probability proportional to lambda. So second moments stay small, even though almost-sure weight bounds compound with depth.
- The symbols mu and Jbar are not defined in the main text. The supplement defines mu_n = E_sel[X_n | {c_q}] = sum over q of m_q * J_q * c_q, and Jbar = sum over q of m_q * J_q <= 1 + C * eps_n (`variance.md:24-28`).

Theorem 2 (depth-uniform variance non-amplification). Under arbitrary inter-parent correlation, the level-transfer factor is a* * (1 + C * eps_n)^2, with a* in [sum over q of beta_q^2, 1].

- Correlation can slow convergence but cannot make it diverge.
- Unrolling gives V_0 <= e^(6 * C * eps_0) * sum over n of iota_n. The cascade multiplies the summed per-level injections by a constant that does not depend on depth or scene scale.
- The penumbra ratio that bounds every bias term also bounds variance compounding.
- C and iota_n are not defined in the main text. In the supplement C is the absolute constant of Lemma J (J_q <= 1 + C * eps_n), and the per-level injection is written iota'_n = lambda * (1 + kappa_n) * mu_n + Var_cand,n + kappa_n * (1 + kappa_n) * Lbar^2: defensive selection noise, own-candidate noise and coefficient fluctuation (`variance.md:155-157`), with kappa = max channel / luminance <= 3.

Temporal model. At stationarity, the reservoir weight follows an AR(1) recursion with coefficient cap / (1 + cap).

- Predicted lag-1 autocorrelation is cap / (1 + cap). Measured values are given in section 6.
- Flicker (temporal CV) scales with exponent 1/2 in (1 + cap). The measured exponent is 0.38 +/- 0.05.
- Adaptation takes about 1 + cap frames without invalidation.
- Turn-off is instant, because re-evaluation is multiplicative. Turn-on is limited by the chain unless invalidation resets M.
- The gap in the flicker exponent is attributed to sample switching (a jump process of rate about gamma) and to the noise floor inherited through the fresh candidate's parent chain. A one-component model captures the scaling to about 15 percent. A two-component refinement (AR(1) plus switch process) brackets the measurements.

Canonical samples. GRIS guarantees coverage with canonical samples. The paper's tail merge has none, since all four inputs are reused. The lambda floor serves as a surrogate weight bound, and Theorem 1 serves as the surrogate coverage argument.

## 6 Experiments

### Setup

- Zero-dependency C++ CPU oracle, double precision, seeded PCG32, analytic intersections.
- Resolution 128 x 128 unless noted. B0 = 4, t0 = 4, and 4 to 5 levels.
- Ground truth from 4096 stratified rays per pixel.
- Vanilla RC is the bit-exact degenerate mode.
- Unless noted: temporal reuse on, boundary-jitter block 8, 128 frames, 6 to 8 seeds, mean +/- sd.
- Hardware for the CPU runs is not stated in the text.

Scenes:

| Scene | Setup | Target failure |
|---|---|---|
| S1 | Area light behind a tilted thin bar (width < s1) | Light leaks |
| S2 | Sub-bin point source through a pinhole | Angular resolution |
| S3 | Blinking emitter | Temporal behavior |

### Main results (Table 1)

Table 1 is at 128 x 128, 128 frames, block-8 jitter, 6 seeds. The two deterministic baselines have no seeds.

| Method | S1 leak (% of vanilla leaked energy) | S2 recovery (% of reference energy) |
|---|---|---|
| vanilla RC | 100 | 115 (dagger) |
| vanilla + bilinear fix | 94.9 | 114 (dagger) |
| ours, rho = 0.25 | 21.4 +/- 4.4 | 99.4 +/- 6.0 |
| ours, rho = 0.5 | 10.7 +/- 2.4 | 93.5 +/- 6.2 |
| ours, rho = 1 | 0.1 +/- 0.1 | 86.4 +/- 6.9 |

- Dagger: these recoveries exceed 100 percent only because ringing misplaces energy.
- Room MAPE is 9.9 (vanilla) and 8.8 (fix), against 1.9 for "our" method. The rho value for that figure is not stated, and the room scene is not otherwise described.
- At rho = 0.5, every acceptance bar is cleared with margin. The numeric bar thresholds are not given in the text.
- At rho = 1, S1 leak is approximately 0 and exactly zero on most seeds.
- Boundary jitter removes a systematic 9 percent deficit. Fan energy moves from 0.91 to 1.003.
- Overall MAPE improves 2.5 to 12 times over vanilla.
- The rho dial trades S1 leak against S2 recovery, as Prop. 3 predicts (Fig. 8a).

### Cost accounting

- All modes trace the same candidate budget: one interval-bounded ray per reservoir per frame. At 128 x 128 this is 262,144 rays per frame.
- Validation shadow rays are the only overhead when rho > 0. They are interval-bounded segments that start at t_{n+1}.
- Measured extra rays by rho (S1 and S2):

| rho | Extra rays |
|---|---|
| 0.25 | +8 to +13 percent |
| 0.375 | +13 to +20 percent |
| 0.5 | +17 to +26 percent |
| 1 | +33 to +53 percent |

- The cheapest setting that clears both acceptance bars is rho = 0.375. It gives leak 15.8 +/- 3.4 percent and recovery 96.0 +/- 6.0 percent, with both bars cleared at 20 percent or less extra rays.
- At rho = 0 the method gives 35 percent of vanilla's leak with zero extra rays.

### Where the rho-dial recovery cost lives

- At 256 x 256, with a frozen split and seed 3, the energy removed between rho = 0 and rho = 1 is 5.8 percent of reference.
- Of that removed energy, 67 percent lies within 2 px of the fan's penumbra boundary, and 85 percent within 4 px. These bands cover 19 and 37 percent of the area.
- The fan core is validation-neutral (+0.04 percent).
- The remaining rho-independent core deficit under a frozen split is -4.4 percent. The paper attributes it to interval-boundary bias, which boundary jitter removes.

### Equal-ray attribution (Table 2)

Table 2 (seed 1, rho = 0.25). Leak energy in the S1 shadow mask. The caption says percentages of vanilla are in parentheses, but only the first row has one.

| Configuration | S1 leak | S1 MAPE |
|---|---|---|
| stochastic RC (no RIS) | 0.0115 (97 percent) | 2.39 |
| + merge-as-RIS | 0.0023 | 0.40 |
| + temporal | 0.0023 | 0.42 |

- Jittered rays with the vanilla merge retain 97 percent of vanilla's leak. The source concludes that the leak is structural in the merge, not caused by ray starvation.
- Adding merge-as-RIS alone captures essentially the entire gain.
- Temporal reuse adds little to frame-averaged statics. Its value is per-frame quality and dynamics.
- The rho = 0.25 configurations add the 8 to 13 percent validation rays from the cost accounting above.

### Flat world-space control (Table 3)

The control is a Boisse-style flat baseline. It has one probe per pixel and 4N angular bins, which matches the cascade's per-pixel candidate count. It uses full-length rays, the same temporal machinery (immutable c_ref re-evaluation, revival, confidence cap), and standard ReSTIR spatial reuse (k = 4 disk neighbors, reconnection shifts with Jacobians, per-candidate generalized-balance MIS, and the same renormalize-before-select validation). Its reuse radius r, confidence cap, and validation rate are single global dials.

Table 3 (128 x 128, 128 frames, cap 8, 6 seeds). Flat shadow rays are full-length. The cascade's rays are interval-bounded.

| Configuration | S1 leak | S2 recovery | MAPE S1 / S2 | Extra rays |
|---|---|---|---|---|
| flat r = 0 (no reuse) | 0.0 | 100.4 +/- 2.9 | 0.06 / 0.15 | 0 percent |
| flat r = 8, rho = 0 | 2819 +/- 362 | 166 +/- 6 | 40.6 / 21.9 | 0 percent |
| flat r = 8, rho = 0.5 | 121 +/- 12 | 50.3 +/- 1.8 | 3.9 / 3.9 | 17 to 29 percent |
| flat r = 8, rho = 1 | 0.0 | 27.2 +/- 0.5 | 1.1 / 0.18 | 33 to 58 percent |
| flat r = 2, rho = 1 | 0.0 | 92.5 +/- 3.2 | 0.44 / 0.19 | 64 to 99 percent (see inconsistency list) |
| ours (cascade), rho = 0.5 | 10.7 +/- 2.4 | 93.5 +/- 6.2 | 0.38 / 0.80 | 18 to 28 percent |

The Table 3 caption says no flat configuration reaches both bars with a reuse radius beyond 2 px. At cap 32, every sharing configuration diverges.

The paper's four regimes:

1. With reuse off (r = 0), per-pixel brute force wins frame-averaged statistics at equal ray count. It is unbiased and hard to beat once accumulation converges. Its rays are full length. The source says this is about 24 times the nominal per-pixel path budget when intersections are analytic, and that DDA or BVH tracers do not get that for free. Nothing is amortized, so per-frame quality equals accumulated quality only after long accumulation.
2. Sharing without validation leaks badly. The leak is 1.7 to 43 times vanilla's leaked energy at cap 8, and it grows with radius and cap. Reused world-space samples carry their source's visibility, and the flat kernel has no scale at which that error is small.
3. Sharing with full validation kills the leak but collapses S2 recovery at any radius beyond 2 px. The text gives 59 percent at r = 4 and 27 percent at r = 8. Validation splits the survivor set on an O(1) part of the domain when the kernel spans a visibility boundary. This is the unanimity condition of Prop. 3, violated at scale-mismatched radii.
4. At cap 32, the flat spatiotemporal chain diverges. Leak reaches up to 4,700 times vanilla, and error grows exponentially with frame count. Stored contribution weights multiply across frames and random-walk. The source says the cascade's per-level W collapse is designed to prevent this.

The cascade uses +18 to +28 percent interval-bounded segments, with reuse radii growing to about 23 px at its deepest level. The text says the only flat configurations that hold both scenes confine sharing to r = 2.

### Dynamics (S3)

- Flicker (temporal CV) decays monotonically with the confidence cap: 1.27, 0.89, 0.54, 0.40 at cap 2, 8, 32, and 64.
- Light-off responds in 2 to 3 frames (temporal re-evaluation).
- Light-on takes 3 frames with scene-change invalidation, and about cap frames without it.
- Figure 6 (frozen split, m0 = 8, rho = 0.25). The ratio E_floor / E_ref is plotted per frame. Turn-off takes 2 to 3 frames in both variants. Turn-on with the frame-indexed reset converges in 3 frames. Without it, the revival jump is followed by a chain-limited climb that does not reach the plus or minus 10 percent band within the half-period.
- The paper says all four behaviors are consistent with the AR(1) model (section 5, Fig. 8b, 8c).

Predicted and measured lag-1 autocorrelation in the text:

| Cap | Predicted | Measured |
|---|---|---|
| 2 | 0.667 | 0.651 |
| 8 | 0.889 | 0.849 |
| 32 | 0.970 | 0.908 |

The paper says switching decorrelates the higher caps.

### The leak ring: residual bias with a predicted address

- With validation and jitter both off, the remaining interval-boundary bias is not diffuse. It concentrates on an arc (Fig. 7).
- Level-3 parents closer than t_3 to the occluding wall start their interval beyond the wall. Their rays hit the emitter untested, and their children reconnect the energy into the shadow.
- The affected pixels are those whose sight line toward the emitter crosses the wall at a distance of about t_3. The wall-crossing histogram spikes 6 times in the predicted band.
- Figure 7 (S2 at 256 x 256, rho = 0, frozen split, seed 3):
  - (a) Ghost blobs lie inside the predicted band t_w in [80, 92) around the level 2 to 3 boundary t_3 = 84.
  - (b) The histogram of wall-crossing distance over leak pixels spikes at t_3.
  - (c) Leak pixels in the t_3 band, by mechanism: rho = 0 frozen 523; rho = 0 with jitter 318; rho = 0.5 frozen 229; rho = 1 gives 0.
- Each mechanism suppresses it with a different signature. rho = 0.5 halves the count. Boundary jitter trades the leak for more pixels that are dimmer. rho = 1 eliminates it.
- The paper says this is the rare failure whose location the theory predicts, and the WebGPU demo reproduces it.

### WebGPU

- A WGSL compute implementation: a fused per-level kernel, ping-pong reservoirs, SDF sphere tracing, and shared scene files.
- Runs at 120 fps at 256 x 256 on an Apple-silicon laptop. The model is not named.
- Reproduces the oracle metrics live: S1 leak approximately 0, and S2 recovery 100.9 percent.
- Has a one-click vanilla/full toggle that reproduces every failure mode and fix in the paper.

### Negative results

- Kill-after-select validation: -16 percent and -33 percent. This is the v_p shrink in Prop. 3.
- Candidate-triggered confidence clamps: +25 percent. MIS weights that depend on the sample draw are biased.
- Per-frame interval jitter under temporal reuse: 3 times leak inflation. Stored radiance bakes in the split.

The paper says each of these is a one-line change away from the correct algorithm.

## 7 Discussion and Limitations

### Scope

- The prototype is 2D flatland with direct emission only.
- Multi-bounce is listed as a next step. The proposed method is an emissive surface cache with a one-frame lag, as in DDGI-family systems.
- The 3D lift is another next step. The paper gives J = r_q^2 / r_p^2 for 3D. Bins map to direction textures. The paper says the eps_n calculus does not depend on dimension.
- Single-frame output has one candidate per bin and is noisy, like all ReSTIR-family estimators. The paper says production use presumes temporal accumulation or denoising. Its variance theorem says the hierarchy does not amplify what those steps consume.

### Hypotheses and constants

- The O(eps_n) mean-bias bounds need bounded radiance (Assumption 1).
- Near-singular emitters degrade gracefully and detectably. Per-probe variance spikes act as a built-in leak detector. The degradation is confined to the penumbra band (section 6).
- Several constants are order-only. The coverage sliver fraction and the un-validated leak (27 to 35 percent of vanilla across configurations, approximately eps_1) are measured calibrations, not derived.
- Turn-on adaptation without scene-change flags costs about cap frames. The paper says a sample-driven detector (temporal-gradient MIS) is open.

### Design axes exposed by the theory

- Angular branching: x2 is alignment-safe. x4 is resolution-rich but needs reprojection or the windowed lookup (Lemma 2, Prop. 2).
- Jitter block length: trades boundary-bias decorrelation against temporal depth.
- lambda: trades dark-region coverage against per-level selection noise (Lemma 4).
- rho: trades leak against shadow-ray cost. It costs +13 to +20 percent rays at the cheapest bar-clearing setting and +33 to +53 percent at rho = 1. The paper says that in 3D, where shadow rays dominate frame budgets, this dial is where the method will be priced.
- Memory is about 3 times vanilla RC, since a reservoir is stored per bin instead of a radiance value.

## 8 Conclusion

RC supplies the discretization that ReSTIR lacks. ReSTIR supplies the estimator that RC lacks. The penumbra condition is the bridge: one geometric ratio sets the order of each bias the cascade merge introduces, of the hierarchy's variance compounding, and of its temporal dynamics. The flat-reuse control measures what breaks without this structure: leak at every unvalidated radius, validation collapse at every wide radius, and divergence once stored weights chain.

## Source inconsistencies and unclear items

- Bound on eps_n. Section 5 gives eps_n <= eps_0 * 2^(-n) with eps_0 = 3 * sqrt(2) * s0 / (2 * t0), about 0.53 at defaults. Section 1 and Theorem 1 give eps_n <= (4/3) * eps_0 * 2^(-n). At defaults, eps_1 = sqrt(2) * s_1 / t_1 = sqrt(2) * 2 / 4, about 0.707. That value equals (4/3) * 0.53 and exceeds 0.53. So the section 5 form does not hold at n = 0 with this eps_0. The 4/3 form is the one that matches the defaults. This check uses the source's own numbers; the paper does not state it. The supplement states the 4/3 form (`lemma-3_2.md:36`).
- Parameters not given numerically in the text: lambda, M_max, K (the jitter block interval), K_t, C, C_1, C_2, C_J, delta'_n, iota_n, mu, Jbar, psi, the pdf in the reservoir weight, and the gather weighting. The code and supplement give lambda, M_max and K and define K_t, C, iota, mu, Jbar and psi (above); C_1 (which depends on alpha_0), C_2, C_J and delta'_n stay order-only. Figure 8b's gamma is undefined.

## Links found

- Reservoir Cascades preprint (this paper), Zenodo | https://doi.org/10.5281/zenodo.21520422 | Version 2 record, PDF only; concept DOI 10.5281/zenodo.21506521
- Sannikov, Radiance cascades: A novel approach to calculating global illumination (2023) | github.com/Raikiri/RadianceCascadesPaper | Cited as the RC reference [13]; the link is given in the reference list. No repository for the paper's own code is given.
- Osborne and Sannikov, Radiance cascades: A novel high-resolution formal solution for multidimensional non-LTE radiative transfer | arXiv:2408.14425 (https://arxiv.org/abs/2408.14425) | Formalized the merge operator and penumbra criterion [11]
- Freeman et al., Holographic radiance cascades for 2D global illumination | arXiv:2505.02041 (https://arxiv.org/abs/2505.02041) | HRC, deterministic RC variant [4]
- Majercik et al., Dynamic diffuse global illumination resampling | arXiv:2108.05263 (https://arxiv.org/abs/2108.05263) | DDGI resampling [10] ([notes](2021_majercik_ddgi_resampling.md))
- Other references without links in the source: [1] Bitterli et al. 2020 (ReSTIR); [2] Boisse 2021 (world-space reuse); [3] Durand et al. 2005 (frequency analysis of light transport); [5] Hedstrom et al. 2026 (stochastic pairwise MIS); [6] Junkins et al. 2026 (compatibility-guided neighbor selection); [7] Kern et al. 2024 (ReSTIR FG); [8] Lin et al. 2022 (GRIS); [9] Liu et al. 2025 (reservoir splatting); [12] Ouyang et al. 2021 (ReSTIR GI); [14] Talbot et al. 2005 (importance resampling); [15] Wyman et al. 2023 (gentle introduction to ReSTIR, SIGGRAPH Courses)

## Code

https://github.com/ivanyou028/reservoir-cascades (MIT, read at 15b4557):

- `core/` holds the estimator. `core/restir.h:6-18` describes two modes: Full (jittered candidates with merge-as-RIS in the proposal) and StochasticRC (the equal-ray value-passing baseline of Table 2). `core/vanilla.cpp` and `core/flat.cpp` are the vanilla RC and the flat world-space control.
- `cpu-ref/` is the CPU oracle (defaults `--lambda 0.05`, `--mcap0 8`, `--bjitter-block 8`; its sweep covers xi in {0, 1/8, ..., 1}), `metrics/` the evaluation, `scenes/s1.json` to `s3.json` the three scenes, and `webgpu/` the browser build (lambda 0.05 and cap 64 in its parameter buffer, `#mcap` 8, jitter block 9999).
- The jitter seed hashes the block index into a PCG32 (`hashCombine(seed, f/block + 0xB007)`). A separate xi, 0.5 for bin centers or uniform otherwise, is the angular offset inside a direction bin (`core/restir.cpp:102-110`).
- The supplement's continuous form of the jitter uses a log-uniform density over [t/2, 2t] (`integrand-mismatch.md:123-128`).
