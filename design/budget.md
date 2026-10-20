# Budget

The GI aims at 6 ms per frame at 1080p on an RTX 2070, half of its 12 ms ceiling, so a 60 FPS game keeps more than 10 ms of its 16.7 ms frame for everything else. The bounce passes take two thirds of that, and their cost sets how far apart the atlas texels can be. Every figure here is derived in [checks/budget.py](checks/budget.py).

## Contents

- [The frame](#the-frame)
- [What a pass costs](#what-a-pass-costs)
- [Texel spacing](#texel-spacing)
- [What buys finer texels](#what-buys-finer-texels)
- [Memory and load time](#memory-and-load-time)

## The frame

| Pass | ms | Set by | Measured in |
|---|---|---|---|
| Bounce passes | 4.0 | passes × hit records × cost per record | plan 004 M3, M4 |
| Direct light into the texels | 0.2 | one shadow ray per texel and moving light; cached visibility for static lights | M2 |
| Moving objects | 0.5 | records retraced near moving objects, and the objects' own texels | M7 |
| Near field | 1.0 | a reserve, not part of the default frame ([near_field.md](near_field.md)) | M5 |
| Composite | 0.1 | one bilinear atlas read per pixel inside the opaque pass | M5 |
| Setup | 0.2 | clears, the light list, dilation and seam stitching | M4 |
| **Total** | **6.0** | | M6 |

The ray rates behind the fixed lines assume 1 G rays/s for software traversal, below the 1.3 to 1.6 G rays/s scaled from an RTX 2080 Ti ([research](../research/sources/2026_gpu_bvh_builders_and_wide_traversal.md#software-traversal-against-rt-cores)). At that rate the direct-light line covers 200,000 shadow rays and the moving-object line 500,000 retraced records.

## What a pass costs

A pass traces nothing. It reads every stored hit record, looks up the radiance of the texel it hit, and merges the cascades from the top down into the texels ([lighting.md](lighting.md)). Its cost is records × `c_r`.

- **The bandwidth floor.** A record moves 8 to 16 bytes: the record, its share of a merged write, and a parent read when it misses. At 70% of the RTX 2070's 448 GB/s that is 0.026 to 0.051 ns per record. The texel radiance it reads (30,000 texels of 8 bytes) stays in the 4 MB L2 cache.
- **The planning cost** is 0.1 ns per record, two to four times the floor, for divergence, latency and occupancy. Plan 004 measures the real cost first (M3), because every texel spacing below scales with its square root.
- **The record budget.** Five passes in 4 ms at 0.1 ns allow 8 M records.

## Texel spacing

Records per texel depend on the bins and on how many world cascades the scene needs. The lab measured 181 to 265 at 16 bins with three world cascades (E2 and E3 in [experiments.md](experiments.md)): 64 for cascade 0 (16 bins times about four front parents), 20 to 35 for world cascade 1, 42 to 66 for cascade 2 and 44 to 109 for the top. Each cascade needs more of its bins than the one below, so the model charges 60 per texel for each world cascade above the first:

`records per texel = 4 · bins + bins/16 · (25 + 60 · (K − 1))`

`K` is the number of world cascades, `ceil(log4(D / t0))` for a scene `D` across. Its central value at `K = 3` is 209, within 10% of the lab's mean of 203; with the lab's largest values per cascade (35 and 110) it is 319, above every scene. A scene 45 m across has `K = 4` and about 270 records per texel at 16 bins.

The texel spacing follows from the scene's surface area `A` and the record budget `R`: `s = sqrt(A · records per texel / R)`. At the planning point the 8 M records buy about 30,000 texels:

| Surface area | 1,000 m² | 3,000 m² | 6,000 m² |
|---|---|---|---|
| Texel spacing | 0.18 m | 0.32 m | 0.45 m |

At 3,000 m², the spacing moves with each assumption:

| Change | Spacing |
|---|---|
| Planning point: 16 bins, 5 passes, 0.1 ns | 0.32 m |
| 0.03 ns per record | 0.17 m |
| 0.3 ns per record | 0.48 m |
| 3 passes | 0.25 m |
| 36 bins | 0.42 m |

**So the GI resolves light at 20 to 45 cm on typical game scenes.** Light that changes faster than that, such as contact shading under small objects, is below the solve's resolution. The texel spacing of each scene is computed from its surface area at import.

The downloaded test scenes have more surface than the planning point assumed, with double-sided surfaces counted twice:

| Scene | Surface area | Across | Texel spacing |
|---|---|---|---|
| Bistro interior | 1,445 m² | 26 m | 0.22 m |
| Crytek Sponza | 8,145 m² | 37 m | 0.46 m |
| Intel Sponza with ivy | 10,783 m² | 48 m | 0.53 m |
| Bistro exterior | 137,297 m² | 259 m | 2.15 m |

The budget scene, Crytek Sponza, gets 0.46 m texels rather than the 0.32 m of 3,000 m². Bistro's exterior is a city block: at 8 M records, its whole surface gets texels over 2 m apart.

## What buys finer texels

- **Fewer passes where albedo allows.** Three passes reach the fixed point within 0.023 at albedo 0.5 (E5) and give 0.25 m at 3,000 m². The pass count is a per-scene setting, so each frame stays deterministic.
- **A lower cost per record**, if M3 measures one.
- **The near-field reserve.** If M5 ships no near-field pass, its 1 ms goes to the passes, for texels about 11% closer.

Four other levers lose more than they buy:

- **Coarse later bounces** (a coarser solve for every bounce after the first) multiply the converged error 6 to 14 times at albedo 0.9 ([paper 3, coarse later bounces](../papers/03_bounces_one_frame/paper.md)).
- **Nearest-bin reads** save 20% of records and make the second bounce about 25% worse (E2).
- **A shorter `t0`** costs records and leaks, because the sphere fix needs a long lower interval (E3).
- **The Kuhn fix at world hand-overs** costs a third more records for no better split error (E2). It stays the sealed alternative.

## Memory and load time

- **Hit records** keep a 4-byte hit texel (or a miss), a byte of parent flags for the sphere fix and a 2-byte hit distance that only the moving-object pass reads: 56 MB at 8 M records.
- **Merged world radiance** needs one value per probe-bin, about one per world record: 6 M values of 4 bytes (shared-exponent RGB) at the planning point.
- **Texels** keep radiance, irradiance and their capture data, about 2 MB at 30,000 texels.
- **Geometry** takes 48 bytes per triangle plus 19 to 24 bytes of binary BVH nodes, 17 to 19 MB for a 260,000-triangle scene. A 10.8 M-triangle scene needs about 0.8 GB, within the RTX 2070's 8 GB ([research](../research/sources/2026_gpu_bvh_builders_and_wide_traversal.md#memory-per-triangle)).
- **At load**, the static records are traced once: 8 M segments at 1 G rays/s take 8 ms, after the BVH build ([scene_and_tracer.md](scene_and_tracer.md)).
