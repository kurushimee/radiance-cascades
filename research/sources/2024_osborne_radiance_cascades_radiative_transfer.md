# Radiance Cascades: A Novel High-Resolution Formal Solution for Multidimensional Non-LTE Radiative Transfer

| | |
|---|---|
| Authors | Christopher M. J. Osborne, Alexander Sannikov |
| Date | 2024-08 (RAS Techniques and Instruments) |
| Kind | Paper |
| Link | https://arxiv.org/abs/2408.14425 ; inputs and results https://doi.org/10.5281/zenodo.13375365 ; code DexRT v0.2.0 https://github.com/Goobley/DexRT (archived as https://doi.org/10.5281/zenodo.13376009) |
| Related | [2023_sannikov_radiance_cascades_paper.md](2023_sannikov_radiance_cascades_paper.md) |

RC applied to solar-atmosphere radiative transfer in the GPU code DexRT. For a graphics implementation it is the most careful description of the 2D method, and the canonical source for the ringing artifact and the **bilinear fix**.

## Method, restated more precisely

- **Penumbra criterion.** A light of length `w` at distance `d` from a blocker casts a penumbra of angle `γ = 2·atan(w / 2d)`; at distance `h` from the blocker it is `γ·h` wide, so `Δs < γ·h`. The light subtends `ε(D) = 2·atan(w / 2D)` at distance `D`, so `Δω < ε(D)`. For `d ≪ D`: `Δs ≲ γ·D` and `Δω ≲ w/D`. Near-field radiance varies fast in space and slowly in angle; far-field radiance varies slowly in space and fast in angle. When `d ≈ D` and the penumbra angle is not small, `Δω` must shrink faster than `1/D`.
- **Radiance interval** `R[a,b](p, ω) = [I(b→a), τ(b→a)]`: intensity and optical depth accumulated along `p + t·ω` for `t ∈ [a, b]`. Any 1D solver can integrate it.
- **Merge** (optical depth form): `I = I(b→a) + exp(−τ(b→a)) · I(c→b)`, `τ = τ(b→a) + τ(c→b)`.
- **Scaling law with branching factor `α ≥ 1`:** `Δs ∝ 2^i`, `Δω ∝ 1/2^(α·i)`, `tᵢ ∝ 2^(α·i)`. Probe spacing always doubles; the branching factor applies to angle and interval length. In 2D, `α = 1` halves the ray count per cascade and `α = 2` keeps it constant. All examples in the paper use `α = 2`.
- Cascade 0 starts at `t = 0`; the top cascade's rays run until they leave the domain, and more cascades are added if its angular resolution is too coarse for the boundary.
- **Interpolated rays.** Cascade `i+1` probes are bilinearly interpolated (n-linearly in nD) onto cascade `i` probes. Each direction of cascade `i` has `2^α` child directions in cascade `i+1` inside the same cone (4 for `α = 2`; the code indexes them as `dir·(1 << CASCADE_BRANCHING_FACTOR)`); merging all children approximates the cone. Interpolating in angle before merging gives a single thin ray instead of a cone.
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

## DexRT v0.2.0 and the data archive

The paper's code is DexRT v0.2.0 (https://github.com/Goobley/DexRT at a9e4bdd). The Zenodo record 13375365 holds the inputs and results of the paper's prominence run, not code.

- **Archive:** "DexRT Inputs and Results for Levitation-Condensation Prominence Snapshot (Supporting Paper)", published 2024-08-26, for a Jenkins and Keppens 2021 prominence simulation, in netCDF 4 with YAML configs. It holds the MHD snapshot `jk20200550.dat` (509.5 MB); DexRT outputs `jk20200550_dex.nc` (201 MB), `_ray.nc` (8.9 GB), `_ray_lyb_cfn.nc` (10.2 GB) and `_synth.nc` (18.5 GB); Lightweaver comparisons `_lw_fil.nc` and `_lw_prom_flip.nc` (18.9 MB each); `_hea2015_proxy.nc` (20.6 MB); the configs; plotting scripts (66.7 MB), rendered videos (11.9 MB) and an H I 102.57 nm video (2.4 MB); and a 19.8 KB zip with the atom models `H_4.yaml`, `H_6.yaml` and `test_CaII.yaml` and the script `preprocess_2d_cube_dex.py`.
- **Run config** (`jk20200550.yaml`): non-LTE mode with active Ca II and H (6-level) atoms, Promweaver boundary, charge and pressure conservation, 2 initial lambda iterations, up to 1000 iterations to a population tolerance of 0.001, sparse calculation, J stored on the CPU, threshold temperature 250,000, and `alo: false`; outputs J, populations, electron and hydrogen densities, LTE populations and wavelengths.
- **Ray configs:** the synthesis run uses 91 viewing angles (`mux`) and 3765 wavelengths with a rotated bounding box; the Lyman β contribution-function run uses one line of sight (`mux 0`, `muz 1`) and 101 wavelengths over 102.49–102.6 nm.

| Constant (`source/Config.hpp`) | Value | Paper |
|---|---|---|
| `PROBE0_LENGTH` | 1.5 | cascade 0 interval of 1.5 voxels |
| `PROBE0_NUM_RAYS` | 4 | 4 angular samples on cascade 0 |
| `PROBE0_SPACING` | 1.0 | |
| `CASCADE_BRANCHING_FACTOR` | 2 | `α = 2` |
| `MAX_CASCADE` | 5 | 6 cascades (0 to 5) |
| `LAST_CASCADE_TO_INFTY`, `LAST_CASCADE_MAX_DIST` | true, 10⁶ | top cascade rays run out of the domain |
| `PREAVERAGE`, `DIR_BY_DIR` | false, true | |
| `RC_CONFIG` | `Vanilla` | the bilinear fix was not needed for the paper's data |
| `PARALLAX_MERGE_ABOVE_CASCADE`, inner parallax threshold | 1, −1 | |
| `PINGPONG_BUFFERS` | true | |
| `NUM_INCL` | 8 (4, 8 or 16 allowed by a `static_assert`) | 8 inclination rays |
| `MODEL_X`, `MODEL_Y`, `NUM_DIM` | 1024, 1024, 2 | compile-time defaults; the paper's run is 3072 × 2048 |
| `WAVE_BATCH` | `32/NUM_INCL` | |

- **Merge variants:** `RcConfiguration { Vanilla, ParallaxFix, ParallaxFixInner, BilinearFix }` (`Config.hpp:44-50`), dispatched in `RadianceCascades.hpp:365-400`. Vanilla calls `march_and_merge_average_interval`. BilinearFix calls `march_and_merge_bilinear_fix` (lines 88-160): for each of the 4 bilinear upper probes it re-anchors the lower ray to end at that probe's interval start, marches it with a 2D DDA, averages that probe's `2^α` child rays (`upper_ray_start_idx = dir·(1 << CASCADE_BRANCHING_FACTOR)`, weight `1/num_rays_per_ray`), merges the two intervals, and accumulates intensity and optical depth with the bilinear weights. The figure scripts use the fixed merge (`PaperFigures/parallax.py` sets `BILINEAR_MERGE = True`, and the disc test plot is titled "Radiance Cascades (Bilinear Fix)"), so the paper's ringing comparison was drawn with the fix while the production default is Vanilla.
- **Into J** (`MergeToJ.hpp:9-40`): cascade 0 values are weighted by `1/c0_dirs_to_average` in azimuth and by the inclination quadrature weight `wmuy(θ)`.
- **Inclination quadrature:** the 8-point table puts a node at 0 with weight 1/64 (the 4-point table 1/16), which is the `1/n²` endpoint weight of Gauss–Radau on [0, 1], consistent with the paper's "Gauss–Radau quadrature with eight rays". The code does not name the rule. `gauss_lobatto.py` generates a 4-point Lobatto set used for azimuthal rays.
- The code reaches the 4 child directions by shifting by `CASCADE_BRANCHING_FACTOR`, so the paper's `α` and the constant are the same quantity.
- The 2025 ray-acceleration version is in [2025_osborne_dexrt_ray_acceleration.md](2025_osborne_dexrt_ray_acceleration.md); its setup uses 4 inclinations.
