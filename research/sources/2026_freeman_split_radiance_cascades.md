# Split Radiance Cascades: Real-Time Global Illumination via Sparse Radiance Probes

| | |
|---|---|
| Authors | Rouli Freeman (Oxford), Alexander Sannikov (Grinding Gear Games), Joe Pitt-Francis (Oxford) |
| Date | 2026-07 (arXiv v2) |
| Kind | Paper |
| Link | https://arxiv.org/abs/2607.20384 |
| Related | [2023_sannikov_radiance_cascades_paper.md](2023_sannikov_radiance_cascades_paper.md), [2025_freeman_holographic_radiance_cascades.md](2025_freeman_holographic_radiance_cascades.md) |

The first full world-space 3D RC with a published evaluation. Probes live in a sparse hash map near visible surfaces, with distance-based levels of detail. Instead of tracing rays from probes per cascade, rays are traced once from visible pixels and **split** by hit distance into the cascade intervals they cover. It gives one diffuse bounce in a single frame (no temporal reuse needed) and supports accumulation and multi-bounce. It also gives the best current argument for parameter choice.

## Contents

- [Parameters and why](#parameters-and-why)
- [Merge with cones](#merge-with-cones)
- [Sparse probes](#sparse-probes)
- [Ray splitting](#ray-splitting)
- [Implementation details](#implementation-details)
- [Numbers (RTX 3080 Laptop, single frame, fp32 storage, not micro-optimized)](#numbers-rtx-3080-laptop-single-frame-fp32-storage-not-micro-optimized)
- [Quality versus DDGI and reference](#quality-versus-ddgi-and-reference)
- [Extensions shown](#extensions-shown)
- [Context from related work](#context-from-related-work)

## Parameters and why

- Cascade `n`: probe spacing `Δsₙ = Δs₀·2ⁿ`, direction count `|Ωₙ| = |Ω₀|·Kⁿ`, cutoff length `tₙ = t₀·lⁿ`, with branching factor `K` and length scaling `l`.
- Probe positions are offset by half a cell, `Δsₙ·(v + ½)`, so cascades do not align and interpolation error spreads evenly. Directions get the same half-offset treatment.
- Angular error at the end of a 3D ray: `Δωₙ = tₙ·√(4π / |Ωₙ|) = (l / √K)ⁿ · Δω₀`.
- The goal is equal angular and spatial error in every cascade, `Δωₙ = Δsₙ`. In 3D that means `K = 4, l = 4`, then tuning `t₀`. Most earlier implementations used `l = 2` (constant angular error per cascade); `l = 4` reduced artifacts in their tests (appendix A).
- In 2D the matching choice is `K = 2, l = 4`; per-cascade cost then falls by `K / 2^d = 1/2`, so total work is bounded. One cascade 0 probe per pixel with 4 directions is enough; `K = 4` is better but HRC is better still at that cost.
- Screen-space RC places probes on the depth buffer (a 2D probe set) and raises angular resolution on both axes, `K = 4`, so each cascade costs the same. PoE2 uses `l = 2`, which works only because it traces the depth buffer with a top-down camera and the scene's vertical extent does not grow with distance.
- With `l = 4`, 4 or 5 cascades span a whole scene; the top cascade's misses sample the environment map.
- Final settings: `l = 4`, `K = 4`, `|Ω₀| = 32` directions, `t₀ ≈ 1.6·Δs₀`, 4 cascades.
- Appendix A (2D, 32 directions per cascade 0 probe, one probe per pixel): with `l = 4`, aliasing (too few directions) and blur (too few probes) appear evenly over the image, and `t₀ = 1·Δs₀` balanced them best. With `l = 2`, error drifts from aliasing near the light to blur far away, whatever `t₀` is. The theory predicts `t₀ ≈ 5·Δs₀`; aliasing looks worse than blur, so shorter is better unless several rays per direction average it out.

## Merge with cones

Per cascade and direction, store radiance `J` and transmittance `β` for the interval `[tₙ₋₁, tₙ]` (`t₋₁ = 0`). Merging is `Lᵢ(x, ω) = J + β·Lᵢ(x + tₙ·ω, ω)`, identical to premultiplied alpha. Ignoring hits closer than `tₙ₋₁` stops a small occluder sitting on a probe from shadowing all its upper rays.

For diffuse lighting, each cascade direction stores the average radiance of its **cone**: all higher-cascade directions whose nearest direction it is, merged with its own interval:

```
Cₙ(x, ω) = Jₙ(x, ω) + βₙ(x, ω) · (1 / |πₙ⁻¹(ω)|) · Σ over ω' in πₙ⁻¹(ω) of Cₙ₊₁(x, ω')
```

`C₀` then holds full radiance per cone, and shading integrates over `Ω₀` with the cosine weight, interpolating `C₀` between probes.

## Sparse probes

- One hash map per cascade. Each frame, every pixel inserts the nearest cascade 0 probe to its world position; every cascade `n` probe then inserts its nearest cascade `n+1` probe. This creates the nearest probe of every cascade to each visible point.
- Trilinear neighbors are not all created (halves probe count for little loss), so interpolation is **sparse trilinear**: sum existing neighbors times trilinear weight and divide by the total weight.
- **Levels of detail:** each probe also stores an LOD. LOD = binary log of the Chebyshev distance to the camera (fewer artifacts than Euclidean with grid-aligned probes), so probes keep a constant on-screen size. Each LOD doubles `Δs₀` and `t₀`. LODs never mix; seams are hidden by starting each LOD at 0.9 of its distance to overlap the previous one and blending linearly across the overlap.
- Directions use an equal-area cylindrical mapping: `encode(ω) = (frac(atan2(y, x) / 2π), (z + 1) / 2)`; `decode(u, v)`: `φ = 2πu`, `z = 2v − 1`, `r = √(1 − z²)`, `ω = (r·cos φ, r·sin φ, z)`. A cascade with resolution `n` has `2n × n` directions at cell centers. The parent of direction `(j, k)` is `(⌊j/2⌋, ⌊k/2⌋)`, exactly 4 to 1. Octahedral and Clarberg equal-area mappings gave worse quality despite more uniform spacing.

## Ray splitting

Probes near surfaces end up partly inside geometry, which over-darkens interpolated light; outward rays from a recessed probe hit the wall immediately. So rays are spawned from visible surface points, as in NVIDIA's SHaRC:

- A ray hitting at distance `t` with `tₘ₋₁ < t ≤ tₘ` tells every cascade below `m` that its interval is transparent (`J = 0, β = 1`) and tells cascade `m` that it is opaque with the hit radiance (`J = L_hit, β = 0`).
- Each contribution is atomically added to the nearest probe and nearest direction in that cascade, with a counter; merge divides by the count and skips directions with zero count.
- Cascades above `m` get nothing. Extending the hit into them biases toward short rays.
- Directions pointing into the surface are flipped (`ω ← ω·sign(ω·n)`), so probe directions facing into walls stay empty and are never read.
- Uniform random directions fill higher cascades badly (coupon-collector `O(b·log b)`), so rays use the R2 low-discrepancy sequence mapped through the equal-area map. Probes sharing a parent get contiguous R2 ranges via a hierarchical prefix sum, so every cascade's directions are covered evenly. The whole sequence is jittered per frame.
- Flat surfaces keep the ray count per cascade constant: 4× fewer probes, 4× more directions.

## Implementation details

- Rust with LuisaCompute over CUDA; OptiX for ray tracing.
- Hash key: 64-bit integer, 18 bits per axis and 10 bits of LOD; lock-free linear probing with atomics. Values index into an indirection buffer holding all directions of a probe, so the table can run at low occupancy. The tables are rebuilt each frame from the indirection buffer, which removes stale probes without deletion logic.
- Directions are stored in Morton order, so the 4 children of a parent direction are contiguous; merging reads coherently and averages with warp shuffles. Higher cascades store pre-averaged cone values directly. One thread block per probe shares upper-probe lookups in shared memory.
- Shading per pixel from 32 directions × 8 probes would need up to 256 samples, so each probe first converts its cones to a 6×6 octahedral irradiance map (Lambertian) with a 1-texel border, and pixels take at most 8 filtered samples in the normal direction.
- Multi-bounce: last frame's hit points spawn probes and rays for a secondary cache two LODs coarser; all hits sample it, so it feeds itself over time.
- Temporal accumulation is simple in world space: blend new intervals into the previous frame's cascades without reprojection.

## Numbers (RTX 3080 Laptop, single frame, fp32 storage, not micro-optimized)

| Stage | Sponza | San Miguel |
|---|---|---|
| Initialize probes | 1.2 ms | 1.3 ms |
| Generate rays | 0.4 ms | 0.6 ms |
| Trace rays | 1.3 ms | 4.5 ms |
| Deposit | 2.2 ms | 1.9 ms |
| Merge | 1.0 ms | 0.8 ms |
| Shade pixels | 2.5 ms | 2.4 ms |
| Total | 8.6 ms | 11.5 ms |

Cost is roughly constant across scenes because LODs keep the probe count steady; only tracing depends on geometry.

## Quality versus DDGI and reference

- Soft penumbras are resolved at every distance because the cascade that captures them scales with occluder distance; DDGI misses penumbras smaller than its probe spacing.
- Medium-scale AO appears (fine on-screen probe spacing); DDGI shows none.
- Artifacts: misses detail below the cascade 0 spacing, leaks from interpolation during merging (brightened shadows), slight bias from only 32 cascade 0 directions, and overblurred hard shadows (foliage).

## Extensions shown

- Rough specular: pick the cascade whose cone size matches the lobe and merge it with the intervals of the lower cascades. Sharp reflections need another method.
- **Cascade −1:** start cascade 0 rays at a small distance and fill the gap with per-pixel screen-space raymarching (as in visibility-bitmask SSGI) merged as a "cascade −1". It recovers contact detail smaller than the cascade 0 spacing (1.4 ms extra; the unoptimized directional gather cost 23 ms).
- Seen as a denoiser over 1 spp rays, Split RC reconstructs undersampled detail better than OIDN.

## Context from related work

- Earlier 3D RC variants: a Shadertoy by Mathis (2024, probes in texture space so the problem stays 2D, https://www.shadertoy.com/view/X3XfRM), Surfel RC by Max Coppen (2025, https://github.com/mxcop/src-dgi, visible interpolation artifacts), and RC in the mobile game Love and Deepspace (Tianlong Ruan, GDC 2026) to boost standard irradiance probes.
- 2D games shipping RC: Core Keeper and Kyora. Neither game's own posts name the technique. Core Keeper's Steam notes describe a rewritten pipeline with reworked indirect light that spreads further and takes surface colour into account (0.5.2, 2023-02-08), AO that uses directional indirect light (0.7.0, 2023-10-04) and "a new indirect lighting solution that should be more accurate, faster and nicer looking" (1.0, 2024-08-27), with no technique, resolution or timing; the game is built in Unity. Kyora, Pugstorm's next game published by Chucklefish and not yet released, has dev blogs (2025-03 to 2026-07) that mention no GI technique. The attribution therefore rests on this paper.
- Path space filtering (Binder et al. 2021) and SHaRC (NVIDIA 2024) use similar world-space hash maps of averaged rays.
