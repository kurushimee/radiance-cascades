# Radiance Cascades: A Novel High-Resolution Formal Solution for Multidimensional Non-LTE Radiative Transfer

| | |
|---|---|
| Authors | Christopher M. J. Osborne, Alexander Sannikov |
| Date | 2024-08 (RAS Techniques and Instruments) |
| Kind | Paper |
| Link | https://arxiv.org/abs/2408.14425 ; code and data https://doi.org/10.5281/zenodo.13375365 |
| Related | [2023_sannikov_radiance_cascades_paper.md](2023_sannikov_radiance_cascades_paper.md) |

RC applied to solar-atmosphere radiative transfer in the GPU code DexRT. For a graphics implementation it is the most careful description of the 2D method, and the canonical source for the ringing artifact and the **bilinear fix**.

## Method, restated more precisely

- **Penumbra criterion.** A light of length `w` at distance `d` from a blocker casts a penumbra of angle `γ = 2·atan(w / 2d)`; at distance `h` from the blocker it is `γ·h` wide, so `Δs < γ·h`. The light subtends `ε(D) = 2·atan(w / 2D)` at distance `D`, so `Δω < ε(D)`. For `d ≪ D`: `Δs ≲ γ·D` and `Δω ≲ w/D`. Near-field radiance varies fast in space and slowly in angle; far-field radiance varies slowly in space and fast in angle. When `d ≈ D` and the penumbra angle is not small, `Δω` must shrink faster than `1/D`.
- **Radiance interval** `R[a,b](p, ω) = [I(b→a), τ(b→a)]`: intensity and optical depth accumulated along `p + t·ω` for `t ∈ [a, b]`. Any 1D solver can integrate it.
- **Merge** (optical depth form): `I = I(b→a) + exp(−τ(b→a)) · I(c→b)`, `τ = τ(b→a) + τ(c→b)`.
- **Scaling law with branching factor `α ≥ 1`:** `Δs ∝ 2^i`, `Δω ∝ 1/2^(α·i)`, `tᵢ ∝ 2^(α·i)`. Probe spacing always doubles; the branching factor applies to angle and interval length. In 2D, `α = 1` halves the ray count per cascade and `α = 2` keeps it constant. All examples in the paper use `α = 2`.
- Cascade 0 starts at `t = 0`; the top cascade's rays run until they leave the domain, and more cascades are added if its angular resolution is too coarse for the boundary.
- **Interpolated rays.** Cascade `i+1` probes are bilinearly interpolated (n-linearly in nD) onto cascade `i` probes. Each direction of cascade `i` has `2α` child directions in cascade `i+1` inside the same cone; merging all children approximates the cone. Interpolating in angle before merging gives a single thin ray instead of a cone.
- Count for `α = 1`: computing `< 2·N₀` rays builds `2^I · N₀` rays. Time does not scale with ray count alone, because upper-cascade intervals are longer.

## Ringing and the bilinear fix

Plain RC shows rings around bright, opaque sources in transparent space, where cascades meet. In the worst case (tiny, very opaque source in vacuum) the error reaches just over 10%; in practical cases it is a few percent.

**Cause: parallax.** A cascade `i` probe merges with the four bilinear neighbor probes of cascade `i+1`. Those neighbors sit at different positions, so their intervals start at different points and see the source at different angles. The cascade `i` probe's occlusion does not line up with what an offset neighbor sees, so one neighbor can add an unoccluded copy of the source. Energy is not conserved where a cascade boundary crosses a source.

**Bilinear fix.** For each of the four cascade `i+1` neighbors, trace the cascade `i` interval from its usual start point to the start point of that neighbor's child interval, merge it with that neighbor's value, and then blend the four results with the usual bilinear weights. This costs 4× more traced rays on every cascade except the top one. It removes ringing and also fixes light leaking through occluders that are too small. Leaks usually mean the penumbra criterion is violated, for example by a cascade 0 spacing that is too coarse.

## Other implementation notes

- Interpolation needs care at domain edges: past the outermost probe row, lookups are clamped, which flattens falloff near the border.
- Interval extension: trace an initial piece at least one probe spacing long, then extend recursively by merging with the interpolated value at the endpoint.
- Back-to-front and front-to-back integration both work; front-to-back allows early exit once a long interval becomes opaque.
- n-linear interpolation needs 8 upper probes per probe in 3D; a simplex-friendly grid could reduce that.
- Sparsity: flag only the cascade 0 probes of interest, flag their bilinear parents up the hierarchy, and compute intervals only for flagged probes.
- Each interval is independent, so the work is embarrassingly parallel; group threads so a warp shares a branch and reads contiguous memory. The GPU solve ran 80× faster than the CPU solve at 2× the power.
- Uniform grids traversed with DDA (Amanatides–Woo style).

## Numbers from the DexRT run

- 3072×2048 grid, 6 cascades, `α = 2`, cascade 0 interval length 1.5 voxels, 4 angular samples on cascade 0, 8 inclination rays per direction (Gauss–Radau) to turn the 2D problem into a 3D-symmetric one.
- The bilinear fix was not needed for that data.
- Time is dominated by the top cascades because of their long intervals: cascade 5 took 63.6% of the runtime, cascade 4 21.4%, cascade 0 only 0.5%.
