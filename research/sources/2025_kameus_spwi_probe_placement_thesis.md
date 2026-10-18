# Kaméus: probe placement for screen probes with world intervals (thesis, 2025)

| | |
|---|---|
| Title | Probe placement strategies for Radiance Cascades with screen-space probes and world-space intervals |
| Author | David Kaméus; supervisor Björn Thuresson, examiner Tino Weinkauf |
| Institution | KTH, master's thesis, October 2025 (TRITA-EECS-EX-2025:854) |
| Link | https://urn.kb.se/resolve?urn=urn:nbn:se:kth:diva-375827 |

The thesis measures what min/max probe placement buys over a single bilaterally merged probe per tile in SPWI, diffuse first bounce only, with no temporal reuse.

## Setup

- AMD Capsaicin 1.1 on DirectX 12, HLSL compute with DXR ray queries, one thread per pixel. RTX 2070 (8 GB), 2048×1024, TAA off, timings averaged over 256 frames.
- Scenes: a Cornell box with a ceiling light, and Sponza lit only by its sky. Reference images from a Monte Carlo path tracer; error measured with LIP (NVIDIA's FLIP tool) and SSIM.
- Cascades run top-down. Cascade `i` uses tiles of `2^(i+1)` px, intervals `[4^i·scale, 4^(i+1)·scale]`, and 4 pre-averaged rays per texel; the top cascade reaches infinity and a miss there reads the environment. The merge is the usual `(r_n + t_n·r_f, t_n·t_f)` with binary transmittance. The value of `scale` and the direction mapping used for the results are not stated.
- Probes are placed from a min/max depth pyramid whose mip matches each cascade's tile size, and pushed off the surface by a depth bias: too much leaks, too little self-intersects.
- The final gather averages each 2×2 tile of cascade 0.

## The two strategies

- **Bilateral:** one probe per tile at the tile's minimum depth; the merge weights upper probes by depth difference, used for cascades 0 to 2 only. When all weights are near zero, normalization produces bright or dark splotches across depth edges, and discarded probes give jagged edges.
- **Min+Max:** two probes per tile, at the world positions of the tile's minimum-depth and maximum-depth pixels, found through a hierarchical buffer. Each layer is merged bilinearly, then the two layers are blended linearly by depth. It needs twice the rays and twice the memory.

## Results

| | 1 probe per pixel | 1 per 2×2 px | 1 per 4×4 px |
|---|---|---|---|
| Cornell, Bilateral | 68.03 ms | 21.21 ms | 9.72 ms |
| Cornell, Min+Max | 79.76 ms | 23.8 ms | 9.96 ms |
| Sponza, Bilateral | 137.49 ms | 37.16 ms | 11.75 ms |
| Sponza, Min+Max | 158.85 ms | 43.02 ms | 13.34 ms |
| Memory, Bilateral | 128 MB | 32 MB | 8 MB |
| Memory, Min+Max | 256 MB | 64 MB | 16 MB |

- Min+Max cost 2 to 17% more time. It improved LIP-LDR error by 0.5 to 5.8% and tone-mapped SSIM by 0.2 to 1.9%, more in the Cornell box than in Sponza, and was slightly worse than Bilateral on Sponza's HDR error.
- The visible difference is larger than the metrics: Min+Max removes the splotchy edge leaks and the worst flicker under motion, leaving softer seams between cascades.
- Nsight showed the time going to waiting on ray queries, about 10 ms per cascade for Bilateral and 15 ms for Min+Max at full density.
- Only the 1-probe-per-4×4 runs fit a 16 ms budget on the RTX 2070.

## Problems in both

- Leaks through thin walls and corners where intervals do not join up and walls align with the grid.
- Halos where depths differ greatly, and at coarse density from the 2×2 final averaging.
- Ringing near cascade boundaries.
- Darker bottom and right screen edges at high cascade counts, from upper probes that would sit off screen.
- Flicker as probes are recomputed at changing depths; the author names reprojection, temporal reuse and a cascade −1 gather as the next steps.

The abstract and conclusion call Min+Max better in every measure except time, but the tables show Bilateral ahead on Sponza's HDR error and on the Cornell box's HDR SSIM.
