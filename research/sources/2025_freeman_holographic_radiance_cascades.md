# Holographic Radiance Cascades for 2D Global Illumination

| | |
|---|---|
| Authors | Rouli Freeman (Oxford), Alexander Sannikov (Grinding Gear Games), Adrian Margel |
| Date | 2025-05 |
| Kind | Paper |
| Link | https://arxiv.org/abs/2505.02041 |
| Related | [2024_osborne_radiance_cascades_radiative_transfer.md](2024_osborne_radiance_cascades_radiative_transfer.md), [2026_freeman_split_radiance_cascades.md](2026_freeman_split_radiance_cascades.md) |

A 2D-only variant of RC (HRC) that removes RC's main remaining error: penumbras from small, distant lights, which plain RC blurs because the cascade that sees the occluder has coarse probe spacing. HRC keeps full probe resolution across the direction of travel and coarsens only along it. It also replaces ray tracing above the first three levels with an acceleration structure built by merging short rays, so cost does not depend on the scene at all. Results come within reach of a converged path tracer.

## What it fixes in plain RC

With base probe spacing `s` and ray length `r`, a small light of size `l` far away, partly blocked by an occluder halfway, casts a penumbra about `l` wide near the probe. The occluder is seen by cascade `log₄(D/r)`, whose probe spacing is `s·D/r`. Once that spacing exceeds `l`, interpolation smears the penumbra. In the paper's test, standard RC tuned to equal time had twice the RMSE of HRC, all of it in penumbras.

## Formulation

- Work in **fluence** (radiance integrated over all directions, no cosine term), since 2D points need not lie on surfaces. Everything is participating media; surfaces are dense volumes.
- Interval radiance and transmittance merge like premultiplied alpha: `Merge((L₁, β₁), (L₂, β₂)) = (L₁ + β₁·L₂, β₁·β₂)`, with `β = 1 − α`.
- Split the problem into **4 quadrants**; each pass handles directions in `[−π/4, π/4]` around +x, then the world rotates 90°.
- Cascade `n` places probes at `p = (x·2ⁿ, y)`: spacing grows only along the travel axis. Direction index `i` takes half-integer values from `1/2` to `2ⁿ − 1/2`; cone `i` is bounded by `p + v(i ± 1/2)` with `v_n(k) = (2ⁿ, 2k − 2ⁿ)`, which is the offset to a probe of the next column. Angular resolution doubles each level and so does trace distance, so ray ends stay evenly spaced at every level.
- Cone angular size: `A_n(i) = angle(v_n(i + 1/2)) − angle(v_n(i − 1/2))`, with `angle([x, y]) = atan(y/x)`.

### Merging down (`R_n` from `R_n+1`)

`R_n(p, i) = F₊ + F₋`, the two halves of the cone.

- **Odd `x`** (no `n+1` probe here): trace along each cone edge to `q± = p + v_n(i ± 1/2)`, which lands on an `n+1` probe, and merge with that probe's closest direction `j± = 2i ± 1/2`: `F± = Merge(A_n+1(j±) × Trace(p, q±), R_n+1(q±, j±))`.
- **Even `x`**: reusing `R_n+1(p, j±)` directly biases toward cone centers, so average two estimates: `F± = (R_n+1(p, j±) + Merge(A_n+1(j±) × Trace(p, q±), R_n+1(q±, j±))) / 2` with `q± = p + 2·v_n(i ± 1/2)`.

### Ray acceleration structure (`T_n`)

`T_n(p, k)` approximates `Trace(p, p + v_n(k))` for `p = (x·2ⁿ, y)`.

- Levels 0–2 are traced directly (DDA through pixels, analytic per-pixel emission and absorption), because merge error grows as rays get shorter.
- Higher levels are built by merging: for even `2k`, `T_n+1(p, 2k) = Merge(T_n(p, k), T_n(p + v_n(k), k))`; for odd `2k`, average the two nearest merged pairs (`F± = Merge(T_n(p, k ± 1/2), T_n(p + v_n(k ± 1/2), k ∓ 1/2))`, result `(F₋ + F₊)/2`).
- The structure needs no empty-space skipping, so dense volumetrics (fractal clouds) cost the same as empty scenes, while a path tracer took 12× longer on them.

### Final gather and cleanup

- Fluence at `[x, y]` for the +x quadrant is read from `R₀([x+1, y], 0)`. The +1 offset stops diagonal rays of adjacent quadrants from overlapping into bright crosses.
- Lookups at `R_N` (beyond the domain) are zero; off-screen lights or an environment map can be supplied there, for example by cone tracing or by reading the map in direction `v_N(i)`.
- Probes with odd and even `y` never interact because `v_n(k)` is always even for `n ≥ 1`, causing a **checkerboard**. A 1-pixel cross blur `[0 1 0; 1 4 1; 0 1 0] / 8`, skipping neighbors with very different opacity, cleans it up.
- Only `4·(2² + 1) = 20` truly traced directions exist per point, which blurs specular BRDFs. Output fluence has 4 directions, enough for diffuse multi-bounce fed back temporally.

## Numbers (RTX 3080 Laptop, Rust with LuisaCompute over CUDA, fp16 RGB radiance and transmittance)

| Grid | Merge up (build `T`) | Merge down (build `R`) | Total |
|---|---|---|---|
| 256² | 0.30 ms | 0.25 ms | 0.55 ms |
| 512² | 1.00 ms | 0.85 ms | 1.85 ms |
| 1024² | 4.10 ms | 3.57 ms | 7.67 ms |
| 2048² | 18.1 ms | 15.8 ms | 33.9 ms |

- 1024²: RMSE 0.0063 versus 0.0667 for a 52 spp path tracer at equal sample count (98.6 ms), about 10× better.
- Time is `O(X·Y·log X)`; memory is dominated by the `T` structure, about `log₂X · 4·X·Y·(r + t)` bytes, and could drop to `2·4·X·Y·r` with a BVH instead.
- Ray count: `4·(log₂X + 3 + 2^−log₂X)` intervals per output value without acceleration (52 for 1024²); with the acceleration structure only 19 traced rays per base probe, all shorter than 6× base spacing.
- In practice the fluence would be computed at a lower resolution and upsampled 2–4× to the screen, merging with rays traced to the probes to avoid leaks.

## Limitations

- Lights smaller than about 8 base probes show moiré-like aliasing because ray segments are fixed; larger lights are fine.
- 3D needs `O(N⁴)` memory for an `N³` volume, so only small volumes are practical (an experimental 128³ voxel version exists).
- Residual blur of about 4 px on sharp shadows compared to the reference.
