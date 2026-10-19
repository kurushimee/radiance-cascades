# GI-1.0: two-level radiance caching

| | |
|---|---|
| Authors | Guillaume Boissé, Sylvain Meunier, Heloise de Dinechin, Matthew Oliver, Pieterjan Bartels, Alexander Veselov, Kenta Eto, Takahiro Harada (AMD) |
| Date | 2022-10 (technical report), arXiv 2023-10 |
| Kind | Paper; code in AMD Capsaicin |
| Link | https://arxiv.org/abs/2310.19855, code https://github.com/GPUOpen-LibrariesAndSDKs/Capsaicin |

Not RC, but the Split RC paper cites it with Lumen as a screen-space radiance cache, and it solves problems any screen-probe RC variant meets: placing probes on visible surfaces, reusing them across frames, filling holes, and avoiding leaks. It uses hardware ray tracing at a quarter sample per pixel at 1080p and needs no precomputation.

## Screen cache

- One probe per 8×8 tile at a random pixel in the tile. Each probe stores 8×8 octahedral incoming radiance over its hemisphere, plus hit distance in alpha. Probes are also projected to 3-band SH for interpolation.
- New probes are spawned over several frames: a Halton jitter picks one pixel per enlarged spawn tile, so a quarter of probes are new each frame.
- **Reprojection:** a pixel may reuse last frame's probe if `|dot(probe_pos − pixel_pos, n)| < cell_size` and the normals' dot product exceeds 0.95. The closest valid probe wins through an atomic min on `half(distance) << 16 | lane`.
- **Holes keep a fixed budget:** tiles that failed to reproject take rays from newly spawned tiles that did reproject, instead of adding rays.
- **Ray guiding:** a CDF over the reprojected probe's cell luminance, built by a parallel scan in shared memory, picks ray directions. Reprojected radiance is scattered into the new probe's cells after parallax correction from stored hit distance.
- **Blend:** a plain moving average lost detail because a cell covers a large solid angle. The shadow-preserving hysteresis keeps the older value when the new one is brighter in a way typical of fireflies:
  - `l1 = luma(cur)`, `l2 = luma(prev)`
  - `a = max(l1 − l2 − min(l1, l2), 0) / max(max(l1, l2), 1e−4)`, then `a = clamp(a, 0, 0.95)²`
  - result `lerp(cur, prev, a)`. It keeps shadows at the cost of some darkening and filters fireflies smaller than a cell.
- **Finding probes:** a mip chain of the probe mask keeps the first valid probe of each 2×2, so a pixel walks up the mips to the nearest probe in a direction.
- **Filtering:** a separable 7×7 sparse blur in probe space that rejects taps by plane distance, normal sign, and the angle between a direction and the tap's hit point (`cos(π/50)`), which keeps small occlusion detail.
- `cell_size` grows with distance: `tan(fov_y · 8 · max(1/h, h/w²)) · distance`, where 8 is the probe spacing in pixels.
- **Thin geometry:** probes that fail reuse are pushed into a persistent LRU side cache with world position and normal, and are found again by splatting them into screen tiles. This stops lighting on thin features from wobbling.

## World cache

- Outgoing radiance at secondary hits, keyed by quantized position, quantized direction and a LOD that grows with camera distance (from Binder 2019, see [2019_binder_path_space_filtering_and_sharc.md](2019_binder_path_space_filtering_and_sharc.md)). Two hashes give the bucket and a fingerprint, with linear probing in the bucket. Cells decay when not touched.
- **Leak fix:** a dark enclosed hit and a bright outside hit can share a cell when the secondary ray is shorter than the cell. Adding the bit `ray_length < cell_size` to the key separates them.
- Cells are grouped into 8×8 2D tiles, dropping the dominant direction axis, with mips rebuilt each frame; queries read the finest mip with enough samples.
- **Temporal radiance feedback:** a hit visible last frame reads last frame's lit result instead of evaluating lights, which gives unlimited bounces for free over frames, but only for surfaces that were on screen. The paper names indoor scenes as the weak case.
- Direct light uses world-space ReSTIR reservoirs in a hash grid with a light grid of the most important lights per cell.

## Gather and timings

- Per pixel, find a probe in four directions, weight by depth and normal, and fall back to equal weights (flagged for the denoiser) when all are rejected. Irradiance is the SH dotted with the cosine lobe. Screen-space horizon AO and short-range GI fill in detail smaller than the probe spacing through a bent-cone mask.
- Totals at 1080p: 1.9 to 3.1 ms on an RX 6900 XT and similar on an RTX 3080, for scenes from 99k to 9M triangles. In a UE5 scene GI-1.0 took 2.4 ms against Lumen's 2.6 ms.

## Capsaicin code

- Screen probes are 8×8 hemi-octahedral with 64 rays each and 9 SH coefficients, spawned once per 16×16 spawn tile. Radiance reuse requires the directions to agree within `cos(0.02π)`, and cell values are quantized by 10⁴ for integer atomics.
- The screen cell size uses the probe size, `tan(fov_y·8·max(1/h, h/w²))`, as in the paper; the world hash grid uses the same form with 32 in place of 8 (a 4× coarser footprint) and a minimum cell of 0.1. The hash grid stores 8×8 tiles with mips (8, 4, 2 and 1, so 85 cells per tile) in 65,536 tiles with 4-way buckets, decays untouched tiles after 50 frames, and blends counts with `lerp(old, new, 1/min(n_old + n_new, 16))`.
- The probe filter has radius 3 with weights raised to the 8th power. World-space ReSTIR uses 2^18 cells of 16 entries and 8 samples. Multi-bounce paths are discarded with probability 0.7 and the survivors scaled by `1/(1 − 0.7)`.
- A frame runs about 25 passes: purge the radiance cache, reproject, look up, spawn, patch and sample screen probes, populate cells, generate, compact and resample reservoirs, populate, update and resolve the cache, blend, reorder, filter, project and interpolate screen probes, reflections, then reproject, filter and resolve GI.
- Direct lighting is on by default, though a comment says it is off.
