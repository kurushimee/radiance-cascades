# Jackknife Transmittance and MIS Weight Estimation

| | |
|---|---|
| Author | Christoph Peters |
| Date | 2025-12, SIGGRAPH Asia 2025 (ACM TOG 44(6), article 204) |
| Kind | Paper with code |
| Link | https://momentsingraphics.de/SiggraphAsia2025.html ; paper https://momentsingraphics.de/Media/SiggraphAsia2025/peters2025-jackknife-paper.pdf ; DOI 10.1145/3763273 ; code https://github.com/MomentsInGraphics/path_tracer/tree/jackknife |

Ray marching estimates optical depth `τ` without bias, but `exp(−τ̂)` is then biased high, because `exp` is convex (Jensen's inequality). The paper splits a fixed sample budget into two independent estimates of `τ` and combines them into a transmittance estimate that is unbiased when `τ̂` is normally distributed, at no extra cost. In RC it applies wherever an interval's transmittance comes from a few jittered samples of a volume instead of exact per-cell path lengths ([volumetric RC](2026_volumetric_rc.md)).

Text extraction dropped most Greek symbols; formulas marked "reconstructed" were rebuilt from the surrounding text and notation.

## Method

- With two independent optical-depth estimates `τ₀` and `τ₁`, `μ̂ = (τ₀ + τ₁)/2` and `σ̂ = |τ₀ − τ₁|/2`. The jackknife transmittance is `T̂ = cos(σ̂)·exp(−μ̂)`, equivalently `Re exp(−(μ̂ + iσ̂))` (eqs. 4 and 7, reconstructed). It is the uniformly minimum-variance unbiased estimate for normal samples (Gray et al. 1973).
- Normality holds approximately for stratified jittered marching with independent jitter per sample, by the Lyapunov central limit theorem, and is close by N = 10 samples. Uniform jittered sampling with one shared offset does not become normal (sec. 4.1, Fig. 4).
- `T̂` stays in [−1, 1] when no control variate exceeds the minimum extinction. Negative values are rare except near zero transmittance, and clamping them adds bias.
- The two estimates share one traversal, so the correction costs nothing measurable.
- Errors (App. A, reconstructed): for one estimate with standard deviation `σ`, the naive estimate has bias `exp(−τ)(exp(σ²/2) − 1)` and variance `(exp(2σ²) − exp(σ²))·exp(−2τ)`; the jackknife with two estimates has variance `½(exp(2σ²) − 1)·exp(−2τ)` and relative RMSE `sqrt((exp(2σ²) − 1)/2)`. Its relative RMSE is never worse than the naive one and up to about 2× lower at large `σ` (Fig. 3).

## Optical-depth estimator (sec. 4)

- Stratified jittered samples at `t_k = (k + ξ_k)·Δ_max/N` with independent `ξ_k` in [0, 1).
- Variance-aware importance sampling: super-voxels of 16³ voxels store an importance from the mean of `(σ − σ_min)²` over their voxels (eq. 5, reconstructed). The minimum extinction is a control variate, removed before sampling and added back by exact regular tracking; without it estimates go negative and fireflies appear.
- The CDF step is `ξ/N`, so the sample count is fixed. A first pass computes the importance integral and tightens the segment.
- Extinction is stored in FP16, with densities rounded up and minima rounded down so estimates stay non-negative. Super-voxel grids use BC4, jitter uses PCG3D, and trilinear filtering is replaced by stochastic texture filtering.
- The budget is exactly 20 high-resolution samples (two estimates of 10) per non-empty super-voxel and none otherwise.

## Accuracy at 24 samples (Table 1)

| Estimates | Samples each | Mean | Bias | Std |
|---|---|---|---|---|
| 2 | 12 | 0.13411 | 0.00000 | 0.0405 |
| 3 | 8 | 0.13425 | 0.00014 | 0.0440 |
| 4 | 6 | 0.13421 | 0.00010 | 0.0528 |
| 6 | 4 | 0.13433 | 0.00022 | 0.0490 |
| 8 | 3 | 0.13485 | 0.00074 | 0.0694 |
| 1 (naive `exp(−μ̂)`) | 24 | 0.13797 | 0.00386 | 0.0331 |

Two estimates give a bias below the margin of error over 10⁸ trials and the lowest standard deviation of the jackknife rows. The naive estimate has a slightly lower standard deviation but about 5× the bias of the 8-estimate row.

## Results

RTX 5070 Ti with clocks locked to 2452 MHz (GPU) and 13801 MHz (memory), Vulkan fragment shader, 1920×1080. Volumes: Bunny cloud 576×571×437, Intel cloud 625×349×566, Disney cloud 993×675×1224, explosion 200×271×229.

- Intel cloud, direct light from a probe, 32 spp (Fig. 1): biased ray marching 32.9 ms, unbiased ray marching 68.8 ms, jackknife with 2 × 10 samples 42.0 ms, track-length 28.4 ms, ratio tracking 69.4 ms.
- Biased estimators at 1 spp (Fig. 8): the jackknife with N = 10 has the lowest bias on three of four volumes; the naive estimate with the same total samples has about 3× the bias, and biased marching with twice the samples still has more.
- The variance-aware control variate cuts bias considerably and standard deviation slightly (Fig. 9).
- Unbiased comparison (Fig. 10), frame time in ms / mean standard deviation:

| Scene | Track-length | Ratio tracking | Unbiased marching | Unbiased marching 2× | Jackknife |
|---|---|---|---|---|---|
| Bunny | 0.47 / 5.7e-2 | 1.07 / 3.2e-2 | 0.90 / 4.5e-2 | 1.46 / 1.6e-2 | 0.40 / 9.3e-3 |
| Intel | 0.81 / 5.7e-2 | 2.26 / 3.4e-2 | 1.40 / 3.9e-2 | 2.15 / 1.9e-2 | 0.79 / 9.9e-3 |
| Disney | 0.64 / 4.4e-2 | 1.28 / 1.5e-2 | 1.05 / 1.7e+0 | 2.20 / 5.5e-2 | 0.26 / 8.1e-3 |
| Explosion | 0.37 / 5.4e-2 | 0.89 / 2.2e-2 | 0.65 / 2.1e-2 | 1.00 / 1.1e-2 | 0.34 / 6.9e-3 |

The Disney value of 1.7 for unbiased marching is out of line with the other rows and may be an extraction error.

- Ratio tracking and unbiased marching spend most samples where transmittance is low; the jackknife spends a fixed 20 per non-empty super-voxel (Fig. 11).
- Limitation (sec. 6.3): a ray crossing non-empty super-voxels without passing through the medium can miss all extinction with its 10 samples; in Fig. 14, 86 % of samples contribute nothing. Smaller super-voxels (12³ removes most failures in the explosion) or more samples help.

## MIS weights for distance sampling (sec. 2.3, 5)

- Balance-heuristic weights between free-flight sampling (density `σ(t)·T(t)`) and equiangular sampling need the free-flight density, which is not exact without regular tracking.
- Eq. 9 is unbiased with biased weights, using the jackknife for the transmittance term; eq. 10 merges weight, density and transmittance into one cheaper, biased jackknife call.
- Theorem 2 generalizes the trick to any analytic `g(τ)` as `g(μ̂ + iσ̂)`. The MIS weight has poles, so it is not analytic, but the bias stays small for `σ` below about 1.645 (5 % negative mass, Fig. 7). Bias in MIS weights does not bias the radiance of an unbiased MIS estimator (App. D).
- Disney cloud, two point lights, 16 spp, MIS with 32 distance samples (Fig. 12): free-flight only 14.5 ms, SMAPE 11.87; equiangular only 34.0 ms, 20.24; MIS after Miller et al. 2019 45.4 ms, 11.03; naive unbiased MIS 53.0 ms, 7.963; biased MIS (eq. 10) 50.5 ms, 7.941; unbiased MIS (eq. 9) 55.5 ms, 7.957. The order of the last two SMAPE values is ambiguous in extraction. Naive biased MIS visibly brightens the image (Fig. 13).
