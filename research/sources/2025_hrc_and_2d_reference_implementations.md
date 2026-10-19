# Holographic RC and other 2D reference implementations

HRC (see [2025_freeman_holographic_radiance_cascades.md](2025_freeman_holographic_radiance_cascades.md)) is 2D only; in 3D it needs `O(N⁴)` memory. These implementations matter for this project mainly for their merge variants, their cost figures and a few lessons that carry over to 3D.

| Repository | Variant | Language | Last commit |
|---|---|---|---|
| https://github.com/entropylost/amitabha | HRC, reference for the paper | Rust on LuisaCompute (CUDA) | 2025-11 |
| https://github.com/Yaazarai/Volumetric-HRC | HRC with volumetrics | GameMaker | 2026-07 |
| https://github.com/entropylost/amida | plain RC with four merge variants and a bounce cascade set | Rust on LuisaCompute (CUDA) | 2026-04 |
| https://github.com/AdrianMargel/radiance-cascades | "nested" RC with probes on circles | WebGL2 | 2024-10 |

Other HRC implementations they link: https://github.com/entropylost/nihil (CPU, continuous line functions) and Suslik's Shadertoy 4ctczl. Both, with entropylost's visualizers and a half-HRC copy, are described at the end of this note.

## Contents

- [amitabha: reference HRC](#amitabha-reference-hrc)
- [Volumetric-HRC (Yaazarai)](#volumetric-hrc-yaazarai)
- [amida: merge variants compared](#amida-merge-variants-compared)
- [AdrianMargel: nested RC](#adrianmargel-nested-rc)
- [nihil: HRC with continuous line functions](#nihil-hrc-with-continuous-line-functions)
- [entropylost's visualizers (hrcviz and hrcviz2)](#entropylosts-visualizers-hrcviz-and-hrcviz2)
- [Half HRC (brucelevis copy)](#half-hrc-brucelevis-copy)

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
- RTX 3080 timings from the README: 256² about 1 ms, 512² 1–2 ms, 1024² 5–6 ms, 2048² 9–11 ms, 4096² 35–45 ms; 8192² runs out of memory. The README's header gives a "simple" 2048² volumetric scene at 11 to 12 ms on the same GPU.
- The README also describes a half-probe option: cast only half as many probes along each plane and let rays interpolate between them when extending and merging, to "double performance where needed".
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

## nihil: HRC with continuous line functions

A CPU test (Rust, 512², 10 cascades) that treats each line of probes as a continuous function of position and angle, discretized and interpolated bilinearly. Its README says it "functions significantly worse than normal HRC".

- Only the +x frame exists. Cascade `i` has vertical lines `2^i` px apart, 512 probes 1 px apart on each, and `2^i` angles across ±45° at `((a + 0.5)/N − 0.5)·π/2`.
- Each texel traces its own segment to the next cascade's line once, then merges with the next cascade sampled on a 100 × 100 grid of offsets over ±1 probe and ±1 angle with tent weights, each sample projected to the next line and read bilinearly. The per-sample trace is commented out, so all samples reuse the center ray.
- Segments use `T = exp(−σL)` and radiance `emission·(1 − T)` through a 2D DDA. The output image is the single +x ray of cascade 0, not a full fluence.
- Every other line of a cascade lies exactly on a line of the next, so its projected segment has length zero (derived). The cost is about 2.6 M texels times 10,000 samples (derived, not measured).

## entropylost's visualizers (hrcviz and hrcviz2)

- **Indexing (hrcviz):** a 32 × 32 grid of index cells over 512 px shows which index lines pass through a hovered cell, with the stroke alpha set by the chord length. Seven schemes: left and right edge points, left point and slope, left and bottom points, radius and angle, height and angle, ring and angle, and two ring points.
- **Basis:** four clicks define a basis element as the lines between two segments, plotted in slope–intercept space, where each element is a quadrilateral tile.
- **Weights:** compares bilinear interpolation of the transmission weight `1/|probe − emitter|` over an 8 px grid with the exact value.
- **hrcviz2 (Rust, WebAssembly):** a frustum has a focus, a size `2^level` and an index in `[−size, size)`, covering slopes `[index/size, (index + 1)/size)`. Odd merges keep the focus and take children `2i` and `2i + 1` with weight 1; even merges step the focus by the lower and upper ray and weight children ½. A generator precomputes, for 6 levels, sparse per-pixel weights as transmission-weighted polygon areas, with error masks for each merge kind. The tiling is by clipped polygon areas, not Bresenham lines.

## Half HRC (brucelevis copy)

The half-HRC shader linked in the community notes under Yaazarai's name lives in brucelevis/Holographic-Radiance-Cascades ("Extremely naive implementation using 1/2 HRC model"); the Yaazarai repository of that name does not exist.

- Probes are 1 px apart, but ray ends are 2 px apart, so each ray merges with two next-level rays at ±1 px across, and each lookup averages two texels: 8 taps at 1/8 each. A comment says ray ends are 1 px apart, which contradicts the 2 px step.
- Each frustum's cascades run top-down at 1920×1080 in 11 cascades of 2048² RGBA16F (`ceil(log2(1920))`). A hit returns the sRGB-decoded scene color with alpha 0, and a miss merges. Rays are weighted by `1 − 0.5·|index − I/2|/(I/2)`, 1 at the center ray and 0.5 at the edges.
- The four frustums are averaged with weights 0.25, each shifted one texel outward, and gamma-encoded. No timings.
