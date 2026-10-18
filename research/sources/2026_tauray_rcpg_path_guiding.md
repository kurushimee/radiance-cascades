# RCPG: radiance cascades for path guiding (tauray code)

| | |
|---|---|
| Authors | Julius Ikkala, Pekka Jääskeläinen, Markku Mäkitalo (Tampere University) |
| Date | 2026-10 (paper in ACM Transactions on Graphics, DOI 10.1145/3840291) |
| Kind | Paper (paywalled, not read) and its renderer code |
| Link | https://doi.org/10.1145/3840291, code https://github.com/vga-group/tauray (LGPL-2.1, `--renderer=rc` and `--renderer=rc-restir`) |

"RCPG: Real-Time Product Path Guiding Using Radiance Cascades" uses a world-space 3D RC volume as a guiding distribution for a path tracer, not as the final lighting. The notes come from tauray's default branch; the README says the paper's exact version lives in a separate `rcpg` branch and that tauray is no longer developed. The volume, culling and temporal parts apply to RC for GI too.

## Volume and layout

- One cube around the scene bounds (1.01× the largest extent). Cascade `c` has `2^(L−c)` probes per axis, with `L = 7` by default (128³ probes at cascade 0).
- Octahedral directions, `(c0 << c)²` per probe with `c0 = 4`: 16, 64, 256, 1024, 4096. Each cascade is a 2D array texture of `c0·2^L` squared (512²) with one layer per probe slice; a probe's directions sit in one block.
- Storage is luminance only (R32F) plus an R8 visibility, about 325 MB at the defaults, more with ping-pong copies.
- Intervals derive from the probe spacing and an angle table: `t0(c) = l/sin(θ_c)` with `l = 2^(c−1)·E/2^L` and `θ = 1.5708, 0.7854, 0.3218, 0.1419, 0.0666, …`. Cascade 0 starts at zero so a surface inside a probe's cell can see its own cell. The code doubles the computed length on purpose: too long makes probe resolution the limit, too short makes parallax the limit, and longer was faster and looked better. Cascades are added while `t0` is within the volume diagonal.

## Live probe culling

- The scene is voxelized every frame at `2^L` by conservative rasterization (dominant-axis projection in a geometry shader). Each mip takes the maximum of its 8 children.
- A probe is live when the occupancy mip matching its cascade is occupied. Starting from every top-cascade probe, the children of live probes are tested cascade by cascade, and live probes are appended to one list, which feeds indirect dispatches (`ceil(live·dirs/64)` groups per cascade). Only live probes are traced and merged.
- A per-voxel history counter (occupied frames, capped at 65536) tells whether a probe has valid history.

## Trace

- One invocation per texel of a live probe. A hardware ray query traces the segment `[t0(c), t0(c+1)]` with back-face culling; the last cascade ends at 10⁹ and alone receives environment light.
- A hit returns emission plus optional direct light (shadow maps, or light-tree samples with shadow rays) plus, when enabled, a recursive term that reads the cascades again at the hit point for multi-bounce. Back-face hits return black and opaque.
- Texel directions and probe origins are jittered per frame with R2 and R3 sequences, the same offset for all probes in a frame.

## Merge and temporal reuse

- The parent probe is simply `child/2`, with no spatial interpolation. Each texel takes the mean of its 4 child directions, gated by its own visibility: `dst += mean(r0..r3)·(1 − vis)`.
- Blend with the previous frame: `blend = max(1/(history + 1), 0.033)`. Probes with almost no history are filled from the average of their 6 face neighbors' previous values.
- An optional bias exponent blends in a power domain to lean toward the larger value, reducing underestimation and fireflies at the cost of noise.
- The value read by the path tracer is `dst + 0.05·local_mean`, floored at 0.01, so no direction gets zero guiding probability.

## Guiding

To sample a bounce, the path tracer starts at cascade 0, picks one 2×2 texel block by weighted reservoir sampling over radiance times the BSDF (diffuse and an LTC-fitted GGX lobe integrated over each quad), then descends into the chosen block's children at the next cascade, adjusting the weights by the accumulated transmittance. The final direction is uniform inside the chosen finest texel. The same structure gives the PDF for multiple importance sampling with next-event estimation.

## vlam (entropylost)

https://github.com/entropylost/vlam (2025-04, no license) is a 2D experiment in the same direction: a path tracer through refracting circles that picks its direction by descending six cascades of stored luminance (4 to 4096 angle bins), choosing one of 4 children at each level in proportion to the stored values, and depositing each path segment's radiance back into the matching cascade. There is no merge pass and, despite the repository description, no light sampling.
