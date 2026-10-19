# Line-Sweep Ambient Obscurance (LSAO)

| | |
|---|---|
| Author | Ville Timonen |
| Date | 2013, Eurographics Symposium on Rendering (Computer Graphics Forum 32(4)) |
| Kind | Paper (9 pages) with BSD-licensed CUDA source |
| Link | http://wili.cc/research/lsao/lsao.pdf ; source http://wili.cc/research/lsao/ |

LSAO computes screen-space ambient obscurance by sweeping parallel lines across the depth buffer, one family of lines per direction, and keeping along each line a stack of the occluders that can still matter. Every pixel then costs O(K) for K directions, with no limit on the occlusion radius, where horizon-based AO (HBAO) costs O(K·N) for N steps per direction. It is the screen-space ancestor of the line sweeps discussed for RC ([light transport alternatives](2026_light_transport_alternatives.md)) and of the caching Therrien proposes for visibility-bitmask SSGI ([2022_therrien_visibility_bitmask_ssgi.md](2022_therrien_visibility_bitmask_ssgi.md)). The depth buffer is treated as a height field, so every occluder extends infinitely behind its visible surface.

Page numbers are journal pages.

## Estimator (p. 3)

- `AO(p, n) ≈ (1/K)·Σ_k [sin τ_k + (sin h_k − sin τ_k)·ρ(‖h_k‖)]` (eq. 1), with directions `D_k = (sin φ_k, cos φ_k)`, `φ_k = 2πk/K`, `u_k = −(p_xy·D_k, p_z)`, tangent `t_k = (−n_z, n_xy·D_k)` and occluder vector `h_k = (o_xy·D_k, o_z)`, where `o` points from `p` to the largest occluder along the direction. `sin τ_k = t̂_k·û_k` and `sin h_k = ĥ_k·û_k`.
- Falloff `ρ(d) = r/(r + d²)` (eq. 2), an inverse quadratic after Filion and McNaughton, with `r` setting the decay.
- For comparison, HBAO's falloff is `ρ₀(d) = max(0, r(1 + C)/(r + d²) − C)` with `C = 0.3` (eq. 3, p. 8): 1 at `d = 0`, reaching 0 at `d = √(r/C)`. Eq. 2 has the same shape for small `C`.

## Sweep (Algorithm 1, sec. 4)

- Each line steps through the depth buffer. At each step: `p` is the de-projected sample, `pk = (p_xy·dir, p_z)`, `u = −pk/‖pk‖`, and `h1`, `h2` are the vectors to the top two stack points. While the occlusion from `h1` is less than from `h2` (and an angle condition holds), the top is popped. The result is the occlusion of `h1`, and `pk` is pushed.
- `occlusion(h, u) = sin τ + max(0, h·u/‖h‖ − sin τ)·ρ(‖h‖)` with a fixed tangent `sin τ = −0.85`.
- The pop test compares the obscurance of the last two stack points instead of testing convexity as in Timonen and Westerholm 2010, so the hull need not be convex. Degenerate cases cost 0.02 % to 0.3 % in the paper's scenes (sec. 4.1).
- The fixed tangent mainly under-occludes, which the falloff can compensate (Fig. 7).
- A line of M steps does exactly M pushes and at most M pops, so it costs O(M) (sec. 4.2).

## Sampling and gather (sec. 5)

- Dense mode places lines 1 px apart with 1 px steps. Sparse mode uses line spacing `D_L` and step `D_S`, for `K/(D_S·D_L)` samples per pixel on average and `K·W·H/(D_S·D_L)` floats of intermediate storage, about 11 MB in the 1080p examples.
- The gather averages, per pixel, the K nearest sweep values within radius `√((D_S/2)² + (D_L/2)²)`.
- Snapping samples to texel centers is safe only for aligned direction sets, `K = 8n` directions from a `(2n + 1) × (2n + 1)` template.
- Writing results by atomic scatter instead of an intermediate buffer was slower, because the writes are uncoalesced.

## Timings (GTX 480, CUDA)

- 1920×1080 with a 10 % guard band in 1.7 ms (Fig. 1); 1920(+192)×1080(+108) in 2.3 ms (Fig. 13). Both run at about 1.33 evaluations per pixel (K = 8, D_S = 2.83, D_L = 2.12; and K = 16, D_S = 4.87, D_L = 2.46).
- Table 1, Sponza, K = 16, 20 % guard band:

| Resolution | LSAO | HBAO |
|---|---|---|
| 800×600 | 1.49 ms | 10.5 ms |
| 1280×720 | 2.56 ms | 24.2 ms |
| 1920×1080 | 5.24 ms | 92.5 ms |
| 2560×1600 | 9.58 ms | 249 ms |

- Table 2, 1280(+256)×720(+144), sweep / gather: K = 8, D_S = D_L = 1.41: 1.91 / 0.38 ms; K = 16 (2.43, 1.64): 1.80 / 0.59 ms; K = 24 (3.56, 1.69): 1.67 / 0.73 ms; K = 32 (4.69, 1.70): 1.60 / 0.90 ms.
- Fig. 12, same resolution, HBAO with N steps against LSAO: K = 16, N = 48: 37.2 against 1.93 ms; K = 16, N = 32: 24.2 against 2.56 ms; K = 8, N = 12: 5.8 against 1.67 ms; K = 8, N = 16: 7.2 against 2.96 ms.
- LSAO does about 2K operations per pixel (K in the sweeps, K in the gather) against K·N for HBAO.

## Limitations (p. 8-9)

- All pixels share one direction set, so small K bands; more directions or sparser sampling trade banding for blur.
- Keeping only the largest occluder per direction underestimates occlusion, and the fixed tangent under-occludes.
- Without snapping, sampling artifacts appear (Fig. 9).
- The method works in screen space on one depth layer. The paper sums it up as "a balancing act of performance, banding, and blur".
