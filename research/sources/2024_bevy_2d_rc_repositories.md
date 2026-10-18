# Bevy 2D RC repositories

Four 2D implementations in Rust and WGSL. None has temporal reuse, bounce light or published timings. They are useful for their layouts and for one sparse variant that skips empty screen areas.

| Repository | Bevy | License | Last commit | Notable for |
|---|---|---|---|---|
| https://github.com/nixonyh/bevy_radiance_cascades | 0.14 | none | 2024-08 | probe-first layout, JFA distance field, cascade count from interval sum |
| https://github.com/kornelski/bevy_flatland_radiance_cascades | 0.16 | CC0 | 2025-09 | volumetric march with transmittance, rays ×2 per cascade, interval stagger |
| https://github.com/Lommix/solis_2d | 0.15 | MIT/Apache | 2025-01 | direction-first layout with one hardware bilinear fetch per merge, normal maps |
| https://github.com/IceKontroI/sparse_rc_2d | 0.17-dev | MIT/Apache | 2025-09 | sparse cascades built as task lists in slab chains |

## nixonyh/bevy_radiance_cascades

- Pipeline: occluders drawn into an R16Uint mask, jump flood, R16Float distance field, cascades top-down in two ping-pong Rgba16Float textures at screen size, a probe-average mip, then a fullscreen add onto the HDR image.
- Probe-first: a cascade `c` probe is a `w×w` texel block with `w = 2^(c+1)`, one ray per texel, so every cascade has `W·H` rays. Intervals start at `i0·(4^c − 1)/3` with length `i0·4^c` (`i0 = 2`: `[0,2], [2,10], [10,42], …`).
- Cascade count `min(16, ceil(log4(1 + 3D/i0)))` with `D` the screen diagonal: the smallest count whose summed intervals reach `D` (6 at 1080p).
- Sphere tracing, at most 32 steps. Emitters are texels above 1.0; the hit returns `sign(c)·max(|c| − 1, 0)`, so negative "light" also works.
- Merge: rays that hit skip it. Others read 4 upper probes × 4 upper rays (16 reads), with bilinear weights 0.75/0.25 from probe parity, times 0.25. No ringing fix.
- Two bugs found by reading: the JFA's last step-1 pass never reaches the distance field (an off-by-one in ping-pong parity), and the probe-average mip divides by `2w` instead of `w²`, which is only right at the default `w = 2`.

## kornelski/bevy_flatland_radiance_cascades

- Branching factor 1 (rays per probe ×2, probe spacing ×2), 16 merged directions at cascade 0, probes 2 px apart, 6 cascades, intervals doubling (`[0,16], [16,32], [32,64], …`). The README calls the seam fix a "gear fix" without defining it.
- Direction-first storage in compute buffers, with pre-averaging of 2 raw rays per stored direction.
- A fixed-step volume march with `exp(−extinction·density·step)` per sample, so the alpha it returns is a transmittance, and the merge is `traced.rgb + traced.a·upper`. The march takes `min(L, (L + 10)/2)` samples per interval.
- Interval ends are staggered by about ±10% to hide cascade edges.
- Upper probe index `(probe − 1)/2` with blend weights 2/3 and 1/3, which matches its probe offset of a quarter spacing.

## Lommix/solis_2d

- Every pass is a fullscreen fragment pass: SDF, cascades in ping-pong, a probe-average mip, and a composite.
- Direction-first layout: cascade `c` is split into `2^c × 2^c` blocks, one per direction group, each the size of the probe grid. A texel holds four raw rays (`4^(c+1)` raw rays per probe), so pre-averaging is built in.
- Merge reads the upper cascade **once** with hardware bilinear filtering at `probe·0.5 + 0.25` inside the matching direction block, clamped half a texel from the block edge. This is the cheap merge that direction-first storage makes possible.
- Intervals `i0·(4^c − 1)/3` to `i0·4^c` with default `i0 = 6`, at most 16 sphere-tracing steps.
- Normal maps multiply by `N·L` at cascade 0, with the light at a configurable height.
- The composite adds `light / |sdf|` as an edge highlight with no guard against zero distance.

## IceKontroI/sparse_rc_2d

A test bed for sparse cascades meant for a later 3D version. It has a dense and a sparse model with the same march and merge.

- Layout: probes ×2 apart, rays ×4, intervals start at `2·(4^c − 1)/3`. Direction-first, one texel per probe and group of four raw rays. The parent texel is the same direction block at `coord/2` with no interpolation (a "nearest-neighbour fix" redirects child rays toward the parent group's center, based on a GMShaders shader).
- **Sparse model:** each workgroup walks a `2^N`-pixel tile in Z-order and seeds cascade 0 tasks only at texels next to an edge between empty and filled space (or every texel in the "filled" mode). A ray that misses adds its parent texel as a task for the next cascade. Duplicates are removed by comparing with the three previous threads.
- Tasks live in per-cascade linked lists of 256-entry slabs drawn from an atomic counter (64,000 slabs, about 197 MB). Colors are packed as 8-bit RGB plus 8 bits of hit and child flags.
- Merges run top-down over the task lists, and cascade 0 writes the lighting at the task's texel.
- Measured notes: about 60% thread use in a busy scene; statistics atomics cost about 1.5 ms per frame from contention, so they are off; 256 entries per slab beat 128 and 512.
- The 8-bit color storage limits dynamic range; the author lists an sRGB format mismatch as a TODO.
