# Holographic RC and other 2D reference implementations

HRC (see [2025_freeman_holographic_radiance_cascades.md](2025_freeman_holographic_radiance_cascades.md)) is 2D only; in 3D it needs `O(N⁴)` memory. These implementations matter for this project mainly for their merge variants, their cost figures and a few lessons that carry over to 3D.

| Repository | Variant | Language | Last commit |
|---|---|---|---|
| https://github.com/entropylost/amitabha | HRC, reference for the paper | Rust on LuisaCompute (CUDA) | 2025-11 |
| https://github.com/Yaazarai/Volumetric-HRC | HRC with volumetrics | GameMaker | 2026-07 |
| https://github.com/entropylost/amida | plain RC with four merge variants and a bounce cascade set | Rust on LuisaCompute (CUDA) | 2026-04 |
| https://github.com/AdrianMargel/radiance-cascades | "nested" RC with probes on circles | WebGL2 | 2024-10 |

Other HRC implementations they link: https://github.com/entropylost/nihil (CPU, continuous line functions) and Suslik's Shadertoy 4ctczl.

## amitabha: reference HRC

- Four rotated frames, each covering ±45°. Each frame has two interleaved probe grids offset by one pixel across the travel axis, so there is one probe per pixel across the rays.
- Level `i` has cells `2^(i+1)` px long along the travel axis and 2 px across, with `2^(i+1)` direction bins between `2^(i+1) + 1` boundary rays of slope `(k − D/2)/2^i`. Every level spans the same ±45°.
- The two lowest levels are traced directly. Higher levels build their rays by joining two rays of the level below ("merge-up"); odd directions average two joined pairs because the midpoint falls between cells.
- The merge-down treats even probes (which share a position with a level `i+1` probe) and odd probes (between them) differently, as in the paper. A 5-tap cross filter that only mixes pixels with equal opacity removes the checkerboard.
- Segment fluence from a cell over length `L`: `T = exp(−σL)`, radiance `= emission·(1 − T)`.
- No timings are published.

## Volumetric-HRC (Yaazarai)

- Plane spacing `2^i`, `2^i + 1` rays per plane, `2^i` cones between them. Cascade 0 is seeded per pixel with `T = 2^(−A)` and `R = (1 − T)·E` (E and A linearized with exponent 2.2).
- Rays are built by extension from cascade 0 upward, not from cascade 3 as in the paper. The README says this reduces aliasing and gives more stable results through angular diffusion.
- The README says the even-plane interpolation cannot be replaced by interpolating before merging. Emitters must be drawn into both the emission and the absorption textures.
- RTX 3080 timings from the README: 256² about 1 ms, 512² 1–2 ms, 1024² 5–6 ms, 2048² 9–11 ms, 4096² 35–45 ms; 8192² runs out of memory.
- The same author's earlier plain-RC port of fad's Shadertoy (https://github.com/Yaazarai/RadianceCascades) stores radiance in RGBA8 gamma space, which bands visibly; the GM Shaders version later moved to RGBA16F.

## amida: merge variants compared

Plain 2D RC at 512×512 with cascade 0 at 1 px spacing, 4 directions, interval ends `4^L` px, six cascades, and pre-averaged storage (each stored direction is the mean of the 4 children). All variants trace from the probe's interval start to a chosen upper probe's interval end:

| Variant | Rays per direction | Corner choice |
|---|---|---|
| single stochastic | 1 | one corner, picked per axis by comparing a fixed random number with the bilinear fraction |
| nearest | 1 | the nearest corner |
| bilinear fix | 4 | all corners, bilinear weights |
| diagonal | 2 | one diagonal pair chosen by which quadrant the fraction lies in, weights `(t.x + t.y)/2` style so each pair sums to 1 |

- The README says the bilinear fix is 4× slower than the single-ray variants.
- A second cascade set computes diffuse bounces at half resolution (base spacing 2 px, 16 directions, intervals starting at 1.5 px) with the single stochastic variant. The code comment says there is no observable difference between variants for the bounce, so the cheapest is used.
- The top cascade samples an environment map averaged into its direction bins (pre-averaged, so the bin count equals the top cascade's stored directions).
- Tracing uses a pixel DDA that skips 8×8 blocks with no change, using a per-block 64-bit mask of pixels that differ from a neighbor. Transmittance exits below 0.001.

## AdrianMargel: nested RC

Each level-`L` cell (`2^L` px) has `4·2^L` probes placed on a circle of radius `2^L·√2/2` around its center, each with `4·2^L` rays. A ray runs from its probe to where it leaves the next level's circle, and merges with the average of the next level's rays inside its cone. The final gather interpolates the four level-0 probes at each pixel's corners, weighted by the angle each covers. The design ties interval ends to geometry instead of fixed lengths, but samples rays only every 5 px, so the lower levels sample only their start points.
