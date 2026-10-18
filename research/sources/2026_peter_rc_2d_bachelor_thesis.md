# Peter: performant global illumination with radiance cascades (bachelor thesis, 2026)

| | |
|---|---|
| Title | Performante globale Beleuchtung durch Radiance Cascades (German) |
| Author | Robert Peter |
| Institution | Hochschule Hannover, bachelor thesis, 14 May 2026 |
| Code | https://github.com/RP-content/radiance-cascades-opengl (code MIT, thesis CC BY 4.0, PDF in `docs/`) |

A native 2D RC in C++ and OpenGL 4.5 compute, built to check the theory's cost scaling with per-pass GPU timestamps. Its value here is a clean per-pass cost split on an AMD GPU and a measured penalty for widening the merge kernel.

## Setup

- Spacing ×2 and directions ×2 per cascade, 4 rays per cascade 0 probe, one probe per pixel, 9 cascades, base interval one pixel diagonal, bilinear merge. Intervals are geometric: `t_min = t0·(f^c − 1)/(f − 1)`, `t_max = t_min + t0·f^c`, with no overlap.
- Scene: SDF circles and boxes, sphere traced with up to 128 steps. A hit stores the normalized hit distance in alpha; an empty interval stores 0.
- One RGBA16F atlas holds all cascades. With 4 rays and doubled height it has 8 times the image's pixels: 15360×4320 at 4K.
- Measured with OpenGL timestamp queries, 200 warm-up frames and the median of 1000, on a Radeon RX 7900 XTX (Ryzen 9 9950X3D, Windows 11).

## Results (CornellLike scene)

| Resolution | Trace | Merge | Copy | RC total | Frame |
|---|---|---|---|---|---|
| 1280×720 | 0.236 ms | 0.345 ms | 0.148 ms | 0.73 ms | 0.88 ms |
| 1920×1080 | 0.511 ms | 0.789 ms | 0.535 ms | 1.84 ms | 2.11 ms |
| 2560×1440 | 0.937 ms | 1.543 ms | 0.935 ms | 3.42 ms | 3.78 ms |
| 3840×2160 | 2.206 ms | 3.459 ms | 2.285 ms | 7.95 ms | 8.66 ms |

- From 720p to 4K the pixel count grows 9×; trace grew 9.3× and merge 10.0×, which supports the bounded total cost. The atlas copy grew 15.4×, which the author puts down to memory bandwidth once tens of megapixels no longer fit any cache.
- The merge is the most expensive pass at 37 to 41% of the frame, trace 25 to 27%, copy 17 to 26%. The RC passes take 83% of the frame at 720p and 92% at 4K.
- The merge cost varied by under 5% across six scenes.

## Merge kernel

At 1024×1024, a 3×3 distance-weighted kernel (weight `1/(1 + |d − f|)`) in place of bilinear raised the merge from 0.41 to 0.63 ms (+54%) and the frame from 1.03 to 1.33 ms. It removed the block artifacts at shadow edges but leaked more light through walls, because it averages across geometry. The author suggests depth weights or rejecting probes behind edges as the fix. The kernel sits behind a `BLUR` define that the repository never sets.

## Limits

- 2D only, point emitters, no BRDF and no multiple bounces; no memory measurement and no error metric against a reference.
- The thesis says 9 cascades for the timings and 8 elsewhere; the code defaults to 8. Its FPS figures for the kernel comparison do not match its frame times.
- The merge reads and writes the same atlas image in place, and with filtering enabled a never-set flag array skips the atlas copy.
