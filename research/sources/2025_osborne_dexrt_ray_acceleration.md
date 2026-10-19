# DexRT: sparse, mipmapped tracing for radiance cascades

| | |
|---|---|
| Author | Christopher Osborne |
| Date | 2025-11 (arXiv) |
| Kind | Paper, plus the DexRT code (C++20, Apache 2.0) |
| Link | https://arxiv.org/abs/2511.08498 (published as "A Simple Ray Acceleration Structure for Non-LTE Radiative Transfer", RASTI, https://doi.org/10.1093/rasti/rzaf055), code https://github.com/Goobley/DexRT |
| Related | [2024_osborne_radiance_cascades_radiative_transfer.md](2024_osborne_radiance_cascades_radiative_transfer.md) |

DexRT is the astrophysics RC solver. This paper speeds up its interval tracing about 8× by letting each cascade march a coarser mip of the scene and by skipping empty blocks with a hierarchical DDA. The domain is solar plasma, but the tracing scheme carries over to a voxel scene for graphics, and the code shows the merge variants and memory tricks in a mature, tested form.

## Contents

- [Scene representation](#scene-representation)
- [Tracing](#tracing)
- [Cascades (2D defaults)](#cascades-2d-defaults)
- [Merge variants in the code](#merge-variants-in-the-code)
- [3D settings](#3d-settings)
- [Results](#results)
- [Paper details](#paper-details)

## Scene representation

- The volume is split into blocks (16² in 2D, 8³ in 3D). Each block has one 3-bit state: empty, or the highest mip level it may be sampled at. 21 states pack into one 64-bit word, so a 512² model needs 392 bytes of block map.
- Each mip averages 2×2 (or 2×2×2) children of the level below. Mip storage is allocated only for active blocks, in Morton order, which costs 1.33× the base level in 2D and 1.14× in 3D.
- **Variance-limited mipmapping:** a parent is accepted only if its children agree. The test is the index of dispersion `|Var/Mean|` of `ln(χ·Δs)` and of `ln(η·Δs)` over the children, limit 1.0, checked only when some child has optical depth `χ·Δs > 0.25` (thin regions always average). A block's level rises only while every parent in it passes. This keeps sharp structure at full resolution and lets smooth or thin regions coarsen.
- **Per-cascade mip cap:** cascade `n` may sample at most mip `[0, 0, 1, 2, 3, 4][n]`. Near intervals keep full resolution; far intervals read coarse proxies, which is where most of the run time goes.

## Tracing

- Hierarchical DDA (Museth 2014): step through cells whose size is `2^level` of the current block, jump whole blocks when empty, and recompute the cell and next-plane distances when the level changes. Each segment gets its exact path length, so no fixed-step oversampling.
- Per segment with constant emission and opacity: `I = I·exp(−τ) + (η/χ)·(1 − exp(−τ))`, with `τ = χ·dt` and `1 − exp(−τ)` computed with `expm1` for precision.
- Robustness: entering an empty region pushes `t` forward by 0.01 cell; the next-plane `t` must always exceed the current `t`; a level change adds 1e−3. Negative coordinates use an arithmetic shift, not division, so `−1 >> 4 = −1`.
- Intervals are marched from the far end toward the probe.

## Cascades (2D defaults)

- Cascade 0: one probe per cell, interval 1.5 cells, 4 azimuth directions times 4 inclinations. Branching factor 2: probes halve per axis, directions ×4, interval end ×4 (`[0, 1.5], [1.5, 6], [6, 24], …`), so every cascade has the same memory. Six cascades; the top one is extended to 2×10⁴ cells so it reaches the boundary.
- **Ping-pong storage:** only two cascade buffers, each sized for the largest cascade, alternate between read and write during the top-down merge.
- **Direction-by-direction:** cascade 0's 4 directions are processed as 4 separate passes through all cascades, each pass storing only the upper directions that descend from one cascade 0 direction. Storage drops to a quarter. It cannot be combined with the parallax fixes, which read neighboring directions.
- Upper probe `k` sits at `(2k + 1)·2^n` and lower probe `c` at `(c + 0.5)·2^n`, so bilinear fractions are 0.25 or 0.75; the first row and column clamp to weight 1.

## Merge variants in the code

| Variant | What it does | Note in the code |
|---|---|---|
| Vanilla (default) | trace once; upper value is the bilinear mix of 4 upper probes times the mean of 4 upper directions | rings around small, bright, optically thick sources |
| BilinearFix | for each of the 4 upper probes, re-trace from this ray's start to that probe's interval start (taken along its middle child direction), merge with that probe only, then weight bilinearly | "near-exact" at 4× the rays |
| ParallaxFix | interpolate the upper direction toward the ray's end point | applied only above cascade 1, since the lowest cascades have their own artifacts; adding a commented-out alternative direction caused ringing |
| ParallaxFixInner | second pass that needs stored optical depth per texel | doubles cascade memory |

## 3D settings

The 3D solver uses blocks of 8³, a cascade 0 interval of 6 cells, 12 azimuth rays from a HEALPix order 1 sphere with ×4 per cascade, and interval ends that **double** per cascade (`6·2^n`), not quadruple. The 3D merge uses 8 trilinear corners and 4 upper rays; a trilinear fix exists but is turned off.

## Results

On a 512×768 prominence model with 880 wavelengths (RTX 4070), sparsity plus mips cut one iteration from 95 s to 11.8 s (8×), with the 99.9th percentile error under 0.5% and a peak of about 12% in a few cells. Mipmapping alone gave 3.5×; sparsity alone gave 1.5× on this half-empty model.

## Paper details

- Setup: DexRT v0.5.0 on an RTX 4070 with an i7-13700, CUDA 12.4 and NVIDIA HPC 24.5. The model is 2D, 512 × 768 cells of 7.5 km, with 880 wavelengths from 5+1-level H, 5+1-level Ca II and Ca III atoms. Cascade 0 has 16 rays, 4 azimuths times a 4-point Gauss-Radau rule in inclination. Iteration stops when the largest relative change of level populations drops below 10⁻³ (MALI with a diagonal operator). Blocks hotter than 250 kK are skipped, about half the model.
- A 512³ model needs a block map of 669 words (5.4 kB). The paper gives no block size or packing for this figure, and it fits neither 8³ blocks (12,484 words) nor 16³ (1,561) at 21 blocks per word (derived). The code (commit 40b86e9) uses 8³ blocks in 3D (`source/UserConfig3d.hpp:11`) with a fixed 3 bits per block (`:15`), where the paper says the minimum number of bits for the range; it packs 21 entries per 64-bit word (`source/BlockMap.hpp:259`) over the full block grid in linear order (`:285-293, 310-315`; Morton order is used only for the active tiles and their mips). A 512³ model's map is therefore 12,484 words (99,872 B), 18.7 times the stated 5.4 kB, while the same rule reproduces the 2D figure of 49 words. 669 equals 32,768 (the 16³ block count) divided by 49 (the 2D word count) and rounded up, which reads as an arithmetic slip (inference).
- Anisotropic data (sec. 3): a velocity grid keeps mip chains at a set of velocities per voxel, interpolated by the ray's projected velocity over 21 directional bins per quadrant (84 in all). The "Core and Voigt" variant splits emission and opacity into direction-independent mipmapped parts times a line profile evaluated per direction, with the Voigt profile from the HUM1WEI24 approximation (Humlíček region I plus a 24-term Weideman series), four mip chains per line and at most four overlapping lines.
- Table 3, time per iteration and error against the dense classic solver:

| Variant | s / iteration | Iterations | Max error % | 99.9th percentile % |
|---|---|---|---|---|
| DenseClassic (reference) | 95.0 | 86 | 0.0 | 0.0 |
| DenseCav | 70.0 | 97 | 12.39 | 0.295 |
| DenseCavMips | 20.2 | 97 | 12.35 | 0.445 |
| SparseClassic | 62.9 | 87 | 1.20 | 0.031 |
| SparseCav | 30.7 | 91 | 12.58 | 0.294 |
| SparseVelInterp | 22.1 | 82 | 12.38 | 0.495 |
| SparseCavMips | 11.8 | 101 | 12.31 | 0.445 |
| SparseVelInterpMips | 10.0 | 91 | 12.36 | 0.889 |

- The column order of Table 3 was rebuilt from the text extraction. The abstract's "under 0.5 %" refers to Core and Voigt with mips; velocity interpolation with mips is about 15 % faster per iteration but nearly doubles the 99.9th-percentile error (0.889 %). The peak errors near 12 % sit in a vanishing fraction of voxels.
- For graphics RC, the paper suggests running the lower cascades locally per patch and giving the upper cascades a compacted mip structure that stores only the highest permitted level per block (sec. 6). It cites Crassin et al. 2011 ([voxel cone tracing](2011_crassin_voxel_cone_tracing.md)) and Han et al. 2007 as prefiltering for anisotropic data.
- Data: https://doi.org/10.5281/zenodo.16759894.
