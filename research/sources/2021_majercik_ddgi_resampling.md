# Dynamic Diffuse Global Illumination Resampling

| | |
|---|---|
| Authors | Zander Majercik, Thomas Müller, Alexander Keller, Derek Nowrouzezahrai, Morgan McGuire |
| Date | arXiv 2108.05263 v1, 2021-08-11 (submitted to Computer Graphics Forum) |
| Kind | Paper |
| Link | https://arxiv.org/abs/2108.05263 |

The paper queries DDGI at the second path vertex instead of the first, and makes DDGI a light source inside ReSTIR, so direct and indirect samples compete in one resampling step. Reservoir Cascades cites it as prior work on combining a probe cache with resampling ([2026_you_reservoir_cascades.md](2026_you_reservoir_cascades.md)); DDGI itself is in [2019_majercik_ddgi.md](2019_majercik_ddgi.md). The paper gives no probe grid sizes, rays per probe or texture formats. Some equations are garbled in extraction and are marked.

## Method (sec. 2-3)

- Rendering equation `L = L_e + T_f·L` (eq. 1) with transport split into diffuse and glossy, `T_f = T_fd + T_fg`. DDGI approximates `L ≈ L_e + T_fd·L_e + L_DDGI + T_fg·L` (eq. 2) with `L_DDGI = Σ_{i≥2} (T_fd)^i·L_e`.
- Per pixel (sec. 3.1): generate candidates from a few emitter points and BSDF-sampled secondary rays; pick one by weighted reservoir sampling in proportion to `L_e + L_DDGI`, resampling among spatial neighbours and across frames (1 temporal and 3 spatial candidates, sec. 3.6); trace one shadow ray; if visible, shade with `L_e` plus the DDGI term. The paper likens it to final gathering with photon mapping.
- Augmented probes (sec. 3.2, eq. 5): the probe update gathers `L_DDGI+ + L_e` at its ray hits instead of the double-bounce form (eq. 4), a single-bounce recursion that converges to the full `T_f·L`. Direct light in the update is attenuated by the inverse square of the total distance (probe-to-surface plus probe-center offset), scaled by a per-scene slider.
- Glossy (sec. 3.3, eq. 6): irradiance at the specular direction approximates prefiltered radiance, with one Monte Carlo sample in proportion to the glossy lobe; converting irradiance to radiance needs a factor of 2 (prefactor garbled). Glossy recursion stops when the path footprint (squared vertex distances weighted by sampling density, after Bekaert et al.) exceeds `0.2` times the camera footprint (eqs. 7-8).
- Combined estimator (eq. 9): `L ≈ L_e + T̄_f(L_e + L_DDGI+) + T̃_f(L_e + L_DDGI+)`, where `T̄_f` clamps the geometry term at `G_max = 1` and `T̃_f` estimates the residual with an extra BSDF sample (Kollig and Keller 2006, sec. 3.5).
- Bias (sec. 3.4, Fig. 5): DDGI's view-and-normal self-shadow offset leaks at short distances, so the query point is moved a fixed distance back along the incoming path instead.
- Caching (sec. 3.6): each candidate reuses the DDGI value already computed when its vertex was shaded, removing one DDGI query per candidate; MAPE goes from 0.63 to 0.64 and frame time from 50.3 to 18.4 ms (Fig. 7), with the added error being noise, not bias.
- Error metric (sec. 4): `MAPE = (1/N)·Σ |v_i − v̂_i|/(v̂_i + 0.01)`.

## Results (sec. 4)

Direct3D 12 in Falcor, Core i7-6800K and RTX 3090, 1920×1080, 1 spp.

Frame time (ms) and MAPE (Fig. 8):

| Scene | Primary DDGI | PT + ReSTIR | Secondary DDGI | + DDGI in ReSTIR | + denoising |
|---|---|---|---|---|---|
| Pink Room | 10.2 / 0.44 | 49.1 / 1.35 | 10.8 / 0.79 | 15.8 / 0.45 | 24.0 / 0.22 |
| Greek Villa | 12.2 / 0.80 | 22.5 / 1.10 | 12.8 / 0.78 | 18.4 / 0.64 | 26.6 / 0.38 |
| Room Door | 8.62 / 0.07 | 18.9 / 1.73 | 9.05 / 0.52 | 13.5 / 0.23 | 22.0 / 0.08 |
| Split Room | 6.73 / 0.22 | 12.4 / 0.76 | 7.00 / 0.38 | 10.9 / 0.18 | 18.3 / 0.12 |
| Red Ball | 7.89 / 0.18 | 12.7 / 0.88 | 8.15 / 0.54 | 13.1 / 0.17 | 21.2 / 0.05 |
| Living Room | 10.0 / 0.27 | 54.5 / 1.18 | 10.8 / 0.45 | 18.4 / 0.46 | 26.3 / 0.19 |

Frames, time and MAPE to equal error (Table 1):

| Scene | PT + ReSTIR | + secondary DDGI | + DDGI resampling |
|---|---|---|---|
| Greek Villa | 129, 2908.00 ms, 0.573 | 8, 113.52 ms, 0.578 | 1, 19.83 ms, 0.572 |
| Living Room | 315, 17157.04 ms, 0.366 | 1, 10.82 ms, 0.366 | 3, 56.57 ms, 0.365 |
| Pink Room | 29, 1423.70 ms, 0.384 | 9, 97.21 ms, 0.390 | 1, 16.85 ms, 0.383 |
| Red Ball | 109, 1381.71 ms, 0.140 | 29, 254.17 ms, 0.142 | 1, 13.37 ms, 0.140 |
| Room Door | 4095, 77278.05 ms, 0.206 | 79, 748.51 ms, 0.200 | 1, 13.28 ms, 0.199 |
| Split Room | 150, 1854.92 ms, 0.162 | 27, 202.42 ms, 0.162 | 1, 10.92 ms, 0.161 |
| Average | 804.50, 17000.57 ms, 0.305 | 25.50, 237.77 ms, 0.306 | 1.33, 21.81 ms, 0.303 |

Cost per component, trace and shade / resampling / probe update (Table 2, ms):

| Scene | PT + ReSTIR | + secondary DDGI | + DDGI resampling |
|---|---|---|---|
| Greek Villa | 20.38 / 1.10 / – | 10.65 / 1.20 / 1.54 | 14.03 / 3.13 / 1.55 |
| Living Room | 52.72 / 1.42 / – | 8.18 / 1.62 / 0.57 | 13.32 / 4.47 / 0.57 |
| Pink Room | 46.60 / 1.08 / – | 8.08 / 1.26 / 1.13 | 11.99 / 2.41 / 1.14 |
| Red Ball | 10.71 / 0.95 / – | 5.47 / 1.27 / 1.02 | 8.57 / 3.23 / 1.01 |
| Room Door | 16.91 / 1.10 / – | 6.71 / 1.50 / 1.07 | 9.64 / 2.33 / 1.08 |
| Split Room | 10.90 / 0.88 / – | 5.33 / 1.24 / 0.44 | 7.63 / 2.65 / 0.44 |
| Average | 26.37 / 1.09 / – | 7.40 / 1.35 / 0.96 | 10.86 / 3.04 / 0.97 |

- DDGI resampling reaches equal error fastest in every scene except the Living Room, where DDGI leaks through thin walls under strong sun. Resampling costs 1.7 ms more on average with DDGI as a light. Fig. 1 (Greek Villa): PT + ReSTIR 22.5 ms, secondary DDGI 12.8 ms, DDGI resampling 18.4 ms, with OptiX denoising 26.6 ms.
- Primary DDGI is fastest and biased.

## Limitations (sec. 5)

- ReSTIR works in screen space and depends on motion vectors, slow camera motion and no transparency; resampling correlates samples in space and time, which leaves less for a denoiser.
- DDGI is grid-based, scales poorly to large scenes and cannot resolve caustics, shadows, AO or near-specular detail; a more accurate cache would give better quality.
- A control-variate variant produced leaks and negative fireflies, and a path-guiding variant was too slow (sec. 5.1, Fig. 9).

## For RC

- Querying the cache one bounce later hides its low resolution behind a BSDF sample; an RC volume queried at secondary vertices would face the same trade between query position and leak exposure (inference).
- Equal error in one frame (1.33 frames on average) depends on ReSTIR's spatial and temporal reuse; without temporal candidates the single-frame noise of 1 spp is what the denoiser column shows (inference).
