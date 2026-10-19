# 3D surface probes

Surface designs tie RC's probes, or the scene the probes trace, to the surfaces themselves. Probes on surfaces scale with surface area, the "surface" row of the [memory model](core_theory.md#memory-by-domain), and cannot sit inside a wall. This topic covers Coppen's surfel radiance cascades, Love and Deepspace's shipped surfel scene with clipmap probes, probes on UV charts (X3XfRM, yhyu13's demo and the generated surface atlas that Blackline Interactive's results point to), on-surface radiance caches outside RC, and a radiance field stored on a plane. Probes in a sparse world grid near visible surfaces are in [3D world space](3d_world_space.md), and probes on the depth buffer in [3D screen space](3d_screen_space.md).

| Design | Probes | Scene for tracing | Memory follows | Shipped |
|---|---|---|---|---|
| Surfel RC (Coppen) | screen-spawned surfels, 6 cascades | triangle BVH | spawned surfels | no |
| Love and Deepspace | world clipmap, 3 levels | surfels per mesh in a hash grid | clipmap size | yes, phones |
| X3XfRM (Mathis) | UV texels of an analytic room | analytic | surface texels | no |
| yhyu13 surface charts | UV charts of a Cornell box | analytic | surface texels | no |
| Spatium (Blackline Interactive), reconstructed | texels of a generated surface atlas, 3 to 6 cascades | compute BVH | atlas texels | no |
| On-surface caches (Tatzgern et al.) | 2×2 texel blocks on mesh islands, not RC | hardware RT | visible islands | no |

## Contents

- [Surfel Radiance Cascades (src-dgi)](#surfel-radiance-cascades-src-dgi)
  - [Frame order](#frame-order)
  - [Parameters](#parameters)
  - [Surfel storage](#surfel-storage)
  - [Spawning (`spawn.slang`)](#spawning-spawnslang)
  - [Hash grid (`shared/hash.slang`)](#hash-grid-sharedhashslang)
  - [Recycling (`recycle.slang`)](#recycling-recycleslang)
  - [Cascade layout and intervals](#cascade-layout-and-intervals)
  - [Gathering (`gather.slang`)](#gathering-gatherslang)
  - [Merging (`merge.slang`)](#merging-mergeslang)
  - [Composite (`composite.slang`)](#composite-compositeslang)
  - [Pass table](#pass-table)
  - [Ground-truth pass](#ground-truth-pass)
  - [Artifacts and fixes](#artifacts-and-fixes)
  - [Performance](#performance)
  - [Limitations and future work](#limitations-and-future-work)
  - [Found by reading the code (not run)](#found-by-reading-the-code-not-run)
  - [Links in the repository and article](#links-in-the-repository-and-article)
  - [Read against the theory (derived)](#read-against-the-theory-derived)
- [Love and Deepspace](#love-and-deepspace)
  - [Scene representation](#scene-representation)
  - [Cascades and probes](#cascades-and-probes)
  - [Artifacts and fixes](#artifacts-and-fixes-1)
  - [Gather and timing](#gather-and-timing)
- [Probes on surface charts](#probes-on-surface-charts)
  - [X3XfRM (Mathis)](#x3xfrm-mathis)
  - [yhyu13 surface-chart RC](#yhyu13-surface-chart-rc)
  - [A generated surface atlas (Blackline Interactive)](#a-generated-surface-atlas-blackline-interactive)
  - [Other surface parameterizations](#other-surface-parameterizations)
- [On-surface radiance caches (Tatzgern et al. 2024)](#on-surface-radiance-caches-tatzgern-et-al-2024)
- [A radiance field stored on a plane](#a-radiance-field-stored-on-a-plane)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)
- [Open questions](#open-questions)

## Surfel Radiance Cascades (src-dgi)

| | |
|---|---|
| Author | Max Coppen (mxcop / m4xc) |
| Date | article dated 2025-01-22; repository last commit 2026-08-10 |
| Kind | repository and articles |
| Link | https://github.com/mxcop/src-dgi and https://m4xc.dev/articles/surfel-maintenance/ |
| License | MIT |

The repository is a Vulkan implementation written in Slang (compiled to SPIR-V) inside a custom C++ engine named "wyre" in the source. It keeps six cascades of surfel probes, where cascade 0 has 262,144 probes and each later cascade a quarter as many. Each probe holds a 4×4 to 128×128 grid of directional intervals, which are ray traced against the scene BVH, merged from the coarsest cascade down, and gathered per pixel from cascade 0 ([surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md)).

### Frame order

From `GIStage::enqueue`:

1. Primary G-buffer pass (`ray-tracing/primary.slang`, ray traced from the camera), written before the GI stage.
2. Spawn, for cascades 0 to 5, reading the hash grid and list left by the previous frame.
3. Clear each cascade's hash grid to zero.
4. Count, for all cascades.
5. Prefix sum, for all cascades.
6. Read back each cascade's live surfel count (used only by the debug panel).
7. Insert (acceleration pass), for all cascades.
8. Gather, for all cascades.
9. Merge: cascade 4 from 5, 3 from 4, 2 from 3, 1 from 2, 0 from 1.
10. Composite, cascade 0 only.
11. Optional debug passes (direct draw, heatmap).
12. Recycle, for all cascades.

A separate ground-truth pass replaces steps 2 to 12 when its flag is set.

### Parameters

Defaults from `SurfelCascadeParameters` (`cascade.cpp`) unless noted.

| Name | Value | Notes |
|---|---|---|
| CASCADE_COUNT | 6 | constant, with a TODO to make it a parameter |
| c0_probe_capacity | 262144 (2^18) | cascade `N` capacity `262144/4^N` |
| c0_memory_width | 4 | intervals per probe side; cascade `N` uses `4·2^N` |
| c0_probe_radius | 0.002 | cascade `N` radius `0.002·2^(N+1)` |
| max_solid_angle | 0.005 | used for the interval length |
| c0_grid_capacity | 262143 (512·512 − 1) | the same for every cascade; the grid buffer has one extra entry |
| c0_grid_scale | 70.0 | cascade `N` scale `70/2^N` |
| cell_capacity | 11 | stored and bound to the UI; no shader reads it |
| Surfel list entries per probe | 16 | list size `16·capacity` |
| SPATIAL_FACTOR | 4 | probe count ÷4 per cascade |
| ANGULAR_FACTOR | 4 | interval count ×4 per cascade |
| Spawn chance | `1/2^N` | see spawning |
| Camera vertical FOV | 90° by default | passed to shaders in radians (`renderer.cpp`, `camera.h`) |
| Near and far planes | 0.1 and 1000 | `renderer.cpp` |
| Radiance texture format | RGBA16F, 2048 × 2048 | the same size for every cascade |

The `cascade_t` comment in `cascade.slang` says the struct is 36 bytes. The Slang struct and the C++ `SurfelCascadeParameters` (`cascade.h:17-29`) have the same seven 4-byte fields in the same order, so both are 28 bytes and the comment is stale.

### Surfel storage

Per cascade, allocated in `SurfelCascadeResources::alloc`, with `C` the cascade's capacity:

| Set 0 binding | Name | Size in bytes | Layout |
|---|---|---|---|
| 0 | params | `sizeof(SurfelCascadeParameters)` | uniform buffer, uploaded once at allocation |
| 1 | surfel_stack | `4·(1 + C)` | entry [0] is the live count, entries [1..count] live surfel IDs, entries above count free IDs; initially count = 0 and entry `1 + k = k` |
| 2 | surfel_grid | `4·262144` | hash bucket start indices |
| 3 | surfel_list | `4·16·C` | surfel IDs grouped by bucket |
| 4 | surfel_posr | `16·C` | xyz world position, w radius squared; radius 0 means dead |
| 5 | surfel_norw | `16·C` | xyz normal, w recycle marker |
| 6 | surfel_rad | RGBA16F 2048 × 2048 | radiance cache written by gather |
| 7 | surfel_merge | RGBA16F 2048 × 2048 | merged radiance cache |

| Cascade | Probes | Bytes (all buffers and textures) |
|---|---|---|
| 0 | 262144 | 94,371,844 |
| 1 | 65536 | 74,711,044 |
| 2 | 16384 | 69,795,844 |
| 3 | 4096 | 68,567,044 |
| 4 | 1024 | 68,259,844 |
| 5 | 256 | 68,183,044 |

All six come to 443,888,664 bytes (about 423 MiB). Each radiance texture is 32 MiB and the hash grid 1 MiB per cascade. The per-cascade totals leave out the 28-byte params buffer; with it each is 28 bytes larger (derived). A surfel ID indexes `posr` and `norw`, and the same ID is the probe index that finds the probe's block in the radiance textures.

The two radiance textures are 64 MiB of every cascade's 65 to 90 MiB, so the cascades cost almost the same memory whatever their surfel count: equal texels per cascade, as in 2D RC, at 2048² × 8 bytes × 2 (derived).

### Spawning (`spawn.slang`)

- Dispatch: 8×8 threads per group, `ceil(W/16)` by `ceil(H/16)` groups; each thread handles one pixel of a 2×2 block.
- The pixel inside each 2×2 block is chosen by the frame index bits (`frame & 1`, `(frame >> 1) & 1`), so each frame tests one quarter of the pixels, rotating through the four positions over four frames. A 16×16 pixel tile is one group.
- Skipped pixels: albedo alpha between 0.4 and 0.6 (emitters), depth at or below 0 or at or above 1000 (sky has depth 2000), and grazing pixels where `dot(−view ray, normal)` is below 0.01.
- The surface point is `origin + ray·depth + normal·0.0001`.
- Coverage test: look up the hash bucket of that point at the cascade's grid scale, using the previous frame's grid and list. For each surfel in the bucket, `cover = (squared distance)/radius² − 1`; if any cover is below 1, the pixel is rejected (the point is inside √2 radii).
- Each surviving pixel makes a candidate `(min(65535, uint(cover·1000)) << 16) | local index in the tile`. The group keeps the highest by atomic max, and only the lane holding it continues.
- Random gate: accept if `pcg1d(frame·W·H + y·W + x) ≤ UINT_MAX/2^N`. The seed does not include the cascade index.
- Allocation: pop the stack with an atomic increment. If the popped index is at or above the capacity, clamp the counter to capacity and stop.
- Stored values: position, radius squared, normal and recycle marker 2.0. Radius `= max(R_N, R_N·depth·fov)`, where both terms use the same expression in the code (`R_N` is the cascade radius).

### Hash grid (`shared/hash.slang`)

- Grid level of a point: `L = clamp(2 + trunc(log2(d²)), 0, 31)` with `d` the distance to the camera (the renderview origin); the code computes `log(d²)·0.7213477` and truncates it.
- Cell size at level `L`: `2^L/(4·scale_N)`; cell index on an axis `floor(coordinate/cell size)`.
- Hash key: x, y, z each mod 512 in 9 bits, the level mod 32 in 5 bits (bits 27 to 31); the packed key goes through xxhash32, then mod the grid capacity.
- Surfel footprint: the axis-aligned box around `position ± radius`. The code computes the level of the point farther from the camera (`position + radius·normalize(position − camera)`) and of the nearer one, inserts into the first and also into the second if they differ. The code names the first "min", but it is the farther point's level, usually the larger.
- Count pass: one atomic increment per (cell, level) bucket the footprint covers.
- Prefix pass: inclusive prefix sum over the whole grid buffer, including the sentinel at index `capacity`.
- Insert pass: each surfel decrements its buckets' counters and writes its ID at the new value, so `grid[h]` is the start of bucket `h` and `grid[h+1]` its end; the sentinel holds the total. If the write index reaches `16·capacity`, that level's insert stops.
- Query: each consumer reads one bucket at the query point's own level, with no search of neighbouring cells. Hash collisions can return distant surfels, so each consumer filters by distance.

### Recycling (`recycle.slang`)

- Dispatch: 256 threads per group over the whole pool; only live surfels (radius² not zero) work.
- Radius update: `R_N·max(1, distance to camera)·fov`, stored squared.
- Marker: reduced by 0.125 each pass; the value read at the start of the pass is used for the forced test.
- Heuristic: if the marker read is below zero, recycle with probability 1. Otherwise count the other live surfels in the same bucket with `squared distance/radius² − 1 < 0.5` (centres within about 1.22 radii), 0.2 each, unclamped.
- Random gate: recycle when a PCG value/2^32 is below the heuristic, seeded by frame index plus surfel ID.
- Recycle: set radius² to 0, decrement the counter, and write the ID into the slot the decrement opened.
- Merge sets the marker to 1.0 on each source surfel it reads, and composite on each surfel it reads; gather does not.
- A surfel never read keeps its spawn marker (2.0) and is forced out at about the 18th recycle pass after spawn; one read by merge or composite is forced out about 9 passes after its last read.
- Commented-out code holds an inactive frustum test and coverage test.

### Cascade layout and intervals

- Probes per cascade `262144/4^N`, intervals per probe `(4·2^N)² = 16·4^N`, so every cascade has 2048 × 2048 = 4,194,304 texels (cache width `memory_width·√capacity = 2048`).
- Probe `p` maps to block `(p mod 2048/mw, p div 2048/mw)` of `mw × mw` texels, interval `(u, v)` at offset `(u, v)`.
- Directions: interval centre `uv = (id + 0.5)/mw` through the equal-area octahedral decode (`shared/octahedral.slang`), over the full sphere, with no hemisphere mapping.
- A 2×2 block of cascade `N + 1` intervals covers exactly one cascade `N` interval; the four child centres sit at the parent's `uv ± 0.25` cells.
- Base interval `base = max_solid_angle·16/4π = 0.0063662` (`cascade.slang` uses 12.56637 for 4π). Cascade 0 covers `[0, 4·base]` and cascade `N ≥ 1` covers `[4^N·base, 4^(N+1)·base]`.

| Cascade | Probes | Memory width | Intervals per probe | Probe radius | Grid scale | Interval (world units) |
|---|---|---|---|---|---|---|
| 0 | 262144 | 4 | 16 | 0.004 | 70 | [0, 0.025465] |
| 1 | 65536 | 8 | 64 | 0.008 | 35 | [0.025465, 0.101859] |
| 2 | 16384 | 16 | 256 | 0.016 | 17.5 | [0.101859, 0.407437] |
| 3 | 4096 | 32 | 1024 | 0.032 | 8.75 | [0.407437, 1.629747] |
| 4 | 1024 | 64 | 4096 | 0.064 | 4.375 | [1.629747, 6.518987] |
| 5 | 256 | 128 | 16384 | 0.128 | 2.1875 | [6.518987, 26.075947] |

- Rays per frame with every probe alive: 6 × 4,194,304 = 25,165,824, one per texel.
- **Spacing.** No spacing is set directly. A surfel's world radius at depth `d` is `max(min_radius, radius·d·fov)` with both radii `0.002·2^(N+1)` (`cascade.slang:70-75`, `spawn.slang:133-138`), so `radius = 0.002·2^(N+1)·max(1, d·fov)`: linear in depth beyond `d = 1/fov` and doubling per cascade. `fov` is the vertical field of view in radians (π/2 by default, `renderer.cpp:82`), not `tan(fov/2)`. Density comes from the count quartering, the spawn chance `1/2^N` and the hash grid. The grid cell is `2^L/(4·grid_scale)` with `grid_scale = 70/2^N` and the level from `hash.slang:31-45`; since `0.7213477 = 1/(2 ln 2)`, `L = 2 + floor(log₂ d)`, so `2^L` lies in `(2d, 4d]` and cells grow linearly with distance, about `2^(L+N)/280` (derived).

The cache texel of an interval belongs to a single probe, so gather writes whole blocks by probe.

### Gathering (`gather.slang`)

- Dispatch: one thread per texel of the 2048² cache, 16×16 per group, 128 × 128 groups for every cascade.
- A thread finds its probe (`texel / mw`) and interval (`texel mod mw`), then the interval direction.
- A dead probe writes (0, 0, 0, 1) to both `rad` and `merge` for each of its texels.
- Trace: from `probe position + direction·interval start` for `end − start`, against the scene BVH: a binary tree with a 32-entry traversal stack and Möller-Trumbore triangles, with traversal credited to tinybvh.
- Visibility is 1 with no hit within the interval, otherwise 0.
- Radiance: a miss at cascade 5 only returns the sky from `sky.slang` at an animated sun direction (`time = frame·0.01666`), with index 5 hard-coded rather than taken from `CASCADE_COUNT`. `getSkyColor` (`shared/sky.slang:29-57`) blends day, dusk and night colours by sun height (`smoothstep(−0.1, 0.1, sunHeight)`), with a horizon term `pow(1 − max(rd.y, 0), 6 + night)`, sun and moon discs, and stars hashed from `rd.xz/(rd.y + 1)`; `getAnimatedSunDir(t) = normalize(cos a, sin a, cos a)` with `a = t·0.05·2·3.14` (:61-63), so the sky changes every frame. A miss at other cascades returns 0, a hit on an emitter (any colour component above 0) the emitter colour, and a hit on a non-emitter 0: non-emissive surfaces are neither shaded nor re-emit.
- The cosine term is fixed to 1.0 here and applied in composite.
- Output: `rad = merge = (radiance, visibility)`.
- Options, both off by default: JITTER (a random position in the interval, blended over 8 frames) and TEMPORAL (one texel per 4×4 block per frame).
- `gather_tx4.slang` (`TEMPORAL 1`, `TEMPORAL_WIDTH 4`, `JITTER 0`) traces one texel per 4 × 4 tile per frame at `thread_id·4 + (frame & 3, (frame >> 2) & 3)`, so a full refresh takes 16 frames while the other 15 texels keep their old values. It never writes `surfel_merge` and applies the cosine in gather, which composite (line 136) applies again. The build compiles only `gather.slang` and `merge.slang` (`assets/CMakeLists.txt:40-42`) and the C++ loads `gather.slang.spv`, so the tx4 files are dead code.

The radiance cache therefore holds only direct emitter and sky light, and nothing in the repository says whether a bounce term is intended. Non-emissive materials use the sentinel colour −1 (`examples/basic/main.cpp:159-174`), so `any(material > 0)` fails for them, while `add_cube`'s default colour (1, 1, 1) makes any default cube an emitter. The only albedo multiply is in composite (`g_albedo·(radiance_sum/weights_sum)·4π`, with `merge·(1/π)·cos θ` per surfel, `composite.slang:137-145`): one bounce of emitter and sky light, applied at the pixel. A `WHITE_FURNACE` switch writes a constant 0.5 at cascade 5 as a test.

### Merging (`merge.slang`)

- Dispatch: 16×16 per group over the destination cascade's 2048² texture, 128 × 128 groups. Only live destination probes work; dead ones keep gather's (0, 0, 0, 1).
- For each destination texel:
  1. Look up the source (cascade `N + 1`) bucket at the destination probe's position offset by 0.01 times its normal, at the source grid scale.
  2. Keep up to four source surfels from that bucket, skipping any with squared distance above 25 times the source radius squared. Score = squared distance + `(1 − dot(normal, source normal))²`; keep the four lowest.
  3. For each kept surfel `i`, read the 2×2 source texels at `(2u, 2v)` to `(2u + 1, 2v + 1)` for destination interval `(u, v)`, and take `far_i` as the mean of `merge(near, far_j)` over the four, with `merge(near, far) = (near.rgb + near.a·far.rgb, near.a·far.a)` and `near` the destination's merged texel.
  4. Result `Σ w_i·far_i / Σ w_i` with `w_i = 1/(score_i + 0.0001)`.
- Source surfels read here get marker 1.0.
- For `N = 5` the source texels come from the source `rad` texture rather than `merge` (the code says this should not be hard-coded).
- Only the merge texture is written.

### Composite (`composite.slang`)

- Dispatch: 8×8 per group over the window.
- Pixels with albedo alpha between 0.4 and 0.6, or depth at or above 1000 or at or below 0, are returned unchanged, so emitter and sky pixels keep the primary colour.
- Position `origin + ray·depth + normal·0.00001`.
- Up to four cascade 0 surfels from the bucket at that position, scored by squared distance plus `(1 − dot)²`; candidates scoring above 8.0 are dropped, a fixed threshold in world units (about 2.8 units of distance on position alone), with no radius filter.
- For each candidate, `S_i = (1/16)·Σ over its 4×4 cascade 0 merge texels of L·(1/π)·max(0, dot(normal, direction))`, where `1/16 = solid_contribution = (1/mw)²`.
- Final = `albedo·(Σ w_i·S_i/Σ w_i)·4π`, then ACES tone mapping, written over the albedo buffer as (colour, 1.0).
- Candidate surfels get marker 1.0.
- The file's header comment is a copy of the debug pass header; the code is the composite.

### Pass table

Thread counts from the shaders; dispatch sizes for cascade 0 at its default capacity, with `W × H` the window.

| Pass (file) | Threads per group | Dispatch | Reads | Writes |
|---|---|---|---|---|
| Primary G-buffer (`ray-tracing/primary.slang`) | 16×8 | `ceil(W/16) × ceil(H/8)` | BVH, prims, normals, view | albedo (rgb, alpha), normal-depth |
| Spawn | 8×8 | `ceil(W/16) × ceil(H/16)`, per cascade | albedo, normal-depth, grid, list, posr, norw | stack, posr, norw |
| Count (`count.slang`) | 128 | `ceil(C/128)`, per cascade | posr | grid (atomic increments) |
| Prefix sum pass 1 (`prefix_sum.slang`) | 512 | 512 groups | grid | grid (in place), segments |
| Prefix sum pass 2 (`prefix_segments.slang`) | 512 | 1 group | grid, segments | segments |
| Prefix sum pass 3 (`prefix_merge.slang`) | 512 | 512 groups | grid, segments | grid |
| Insert (`accelerate.slang`) | 128 | `ceil(C/128)`, per cascade | posr | grid (atomic decrements), list |
| Gather | 16×16 | 128 × 128 | posr, BVH | rad, merge |
| Merge | 16×16 | 128 × 128 | destination and source grid, list, posr, norw, rad, merge | destination merge; source marker |
| Composite | 8×8 | `ceil(W/8) × ceil(H/8)` | albedo, normal-depth, cascade 0 grid, list, posr, norw, merge | albedo |
| Recycle | 256 | `ceil((1 + C)/256)`, per cascade | stack, grid, list, posr, norw | posr, norw, stack |
| Direct draw (`direct_draw.slang`, debug) | 16×8 | `ceil(W/16) × ceil(H/8)` | params, grid, list, posr, norw, renderview, normal-depth | albedo where surfels cover the pixel, `Σ color·(−w)/Σ(−w)` over surfels with `w ≤ 0`; skips depth > 1000; declares an unused writable stack |
| Heatmap (`heatmap.slang`, debug) | 16×16 | `ceil(W/16) × ceil(H/16)` | params, grid, normal-depth, renderview | albedo: the cell's surfel count times 1/16 through a colour ramp |
| Ground truth (`ray-tracing/ground_truth.slang`) | 8×8 | `ceil(W/8) × ceil(H/8)` | BVH, albedo, normal-depth | accumulator, albedo |

The prefix sum over the 262,144-entry grid uses 512 groups of 512 threads in passes 1 and 3, one thread per entry.

### Ground-truth pass

Enabled by a GIStage flag, it bypasses the whole RC pipeline. Per pixel per frame it traces one uniformly random direction from the surface; a hit on an emitter adds `material·(1/π)·max(0, dot(normal, direction))`, blended into the accumulator with alpha. Misses add nothing, so this reference has no sky term. Output is `albedo·accumulator·4π`, then ACES.

### Artifacts and fixes

The source names few artifacts. The points it addresses:

- Grazing views are rejected in spawn "to avoid floating point imprecision".
- Depth at or above 1000 is rejected in spawn to avoid NaN surfels.
- Emitters are excluded from spawning, and composite leaves emitter pixels unchanged.
- Dead probes write (0, 0, 0, 1), so later passes see an empty interval.
- The prefix sum keeps the last grid entry empty as its sentinel.
- Cosine term: the comments say applying the cosine in composite, and also in gather, both produced artifacts; the code fixes it to 1.0 in gather and applies it in composite. The artifacts are not described.
- Spawn cost: the article reports spawn time going from about 6 ms to about 1 ms on an AMD Radeon 890M iGPU after the quarter-pixel rotation, and says the quality loss was not significant.
- `WHITE_FURNACE` (off) writes constant radiance 0.5 at cascade 5 for a furnace test.

### Performance

Read from the article's figures (the text does not repeat them):

| Pass | AMD Radeon 890M iGPU (fig. L) | RTX 4070 Mobile (fig. M) |
|---|---|---|
| Surfel spawning | 0.6 ms | 0.18 ms |
| Hash counting | 0.25 ms | 0.10 ms |
| Hash prefix sum | 0.2 ms | 0.15 ms |
| Hash insertion | 1.0 ms | 0.19 ms |
| Recycling | 0.4 ms | 0.20 ms |

- Both captures use six cascades; the resolution is not stated. The article says insertion is the most expensive of these passes on the 890M and recycling on the 4070.
- README profile (`pipeline.png`): a frame of 16.27 ms with 12.15 ms active, of which surfel gathering is 5.35 ms and surfel merging 2.04 ms. The spawn and composite bars carry no values, and hardware and resolution are not stated.

### Limitations and future work

From the article:

- The transform pass is not implemented: surfels are stored in world space and do not move with the geometry they sit on. The article describes GIBS's transform-ID approach ([related radiance caches](related_radiance_caches.md)) but skipped it for time.
- Hash collisions can return distant surfels.
- A plain uniform grid was rejected for scaling; GIBS's trapezoidal grid was not implemented.
- The 16×16 tile size may need changing for different surfel sizes.
- The article lists "time since used" and "live count" as heuristic terms; the code uses neither.
- The article's spawn snippet packs `(min(65535, uint(coverage·1000)) << 16) | local_index`, starts the group-shared value at 0xFFFFFFFF and takes `atomicMin`, so the least-covered pixel wins. The code takes `atomicMax` of a distance-based `cover`, which also picks the least-covered pixel. The snippet also starts `coverage` at 1e30 and then takes `max(coverage, point_coverage(...))`, which leaves it at 1e30 as written, and never defines `point_coverage`.
- The article gives no spawn threshold, recycling weights, grid capacity, base of the level logarithm or default radius. Its stack allocation has no overflow check; the code clamps the counter.

From the source comments (TODO and WARN): branch factors must be divisible by 2 for the half-scale helpers and are not parameters; the cascade count is a constant and the top cascade is hard-coded as index 5 in gather and merge; radiance is 16-bit float, with a TODO for a 32-bit HDR format; tone mapping is inside composite, with a TODO for a separate pass; Lambert's term is applied in composite, with a TODO to move it into merge; HDR encode and decode are identity functions (the mapping is commented out); JITTER and TEMPORAL are off.

### Found by reading the code (not run)

1. **Stack push may corrupt the free list.** `stack_push` writes the recycled ID into slot `1 + new_count`, the last live slot before the decrement. The recycled ID stays in its original live slot, and the previous last live ID is overwritten and lost, so one ID can be duplicated and another dropped. The article describes the same write and does not address the case where the recycled ID is not in that slot.
2. **Barrier in divergent flow.** Spawn returns early (albedo skip, depth, grazing, coverage fail) before `GroupMemoryBarrierWithGroupSync`, so only some lanes reach the barrier, which Vulkan leaves undefined.
3. **Merge with no source candidates writes zero.** With no candidates, `radiance_sum` stays zero and `weights_sum` is about 4e−30, so the result 0/tiny = 0 overwrites gather's near radiance with (0, 0, 0, 0), and a zero alpha is later read as fully occluded.
4. **Random seeds are shared across cascades.** The spawn seed omits the cascade index and the accept test is monotone in `N`, so a pixel accepted at a higher cascade is also accepted at every lower one if the coverage test passes.

### Links in the repository and article

The article index (https://m4xc.dev/articles/) and sitemap list three articles: Surfel Maintenance for Global Illumination (2025-01-22, 2943 words), [Fundamentals of Radiance Cascades](../sources/2024_coppen_fundamentals_of_radiance_cascades.md) (2024-10-22), and Amanatides and Woo's fast voxel traversal (2024-04-20), a C++20 walkthrough over a 32×32×32 grid in the unit box that steps on the axis with the smallest `tmax` and returns the entry time of the first non-empty voxel, or 1e30 on a miss or after 128 steps. The README and article cite the RC paper repository (https://github.com/Raikiri/RadianceCascadesPaper), EA SEED's GIBS article and SIGGRAPH 2021 talk and Ray Tracing Gems chapter 25 ([related radiance caches](related_radiance_caches.md)), and kajiya (https://github.com/h3r2tic/kajiya) for the prefix sum and surfel GI. Shader headers credit tinybvh (https://github.com/jbikker/tinybvh) for BVH traversal, Cigolle et al. (https://jcgt.org/published/0003/02/01/paper.pdf) and PBRT's equal-area mapping (https://pbr-book.org/4ed/Geometry_and_Transformations/Spherical_Geometry#x3-Equal-AreaMapping) for directions, and Jarzynski and Olano's hash survey (https://jcgt.org/published/0009/03/02/) for xxhash32 ([glossary](supporting_techniques.md)).

### Read against the theory (derived)

- **Intervals are fixed in world units while surfels grow with depth.** Cascade 0's interval ends at 0.0255 everywhere, while a cascade 0 surfel's radius is `0.004·max(1, 1.571·d)`. The interval end equals the surfel radius at depth 4.1 for cascade 0, and at 8.1, 16.2, 32.4, 64.8 and 129.7 for cascades 1 to 5. With 16 directions (`Δω0 = 0.886`), the gap between cascade 0 ray ends is 0.0226, which equals a spacing of √2 radii (the spawn test's minimum) at depth 2.5 and of 2 radii at 1.8. So the angular error dominates nearer the camera and the spatial error farther away, and the equal-error balance holds at one depth only. Split RC scales `t0` with each LOD for this reason ([3D world space](3d_world_space.md#placement-and-levels-of-detail)).
- **Spawning is rate-limited.** One candidate per 16×16-pixel tile per frame gives at most 8,160 new surfels per cascade per frame at 1080p, so filling cascade 0's 262,144 slots from empty takes at least 32 frames, and the `1/2^N` gate caps cascade 5 at about 255 per frame for its 256 slots. The surfel set is temporal state even though the gather traces every texel each frame.
- **Rays per frame** are 25.2 M with all slots alive, 12.6× one ray per pixel at 1080p, against which the 5.35 ms gather is the measured cost.
- **The merge's parent choice is a nearest-neighbour search,** not a trilinear blend: up to 4 parents by position and normal similarity, with no visibility test, so leaks depend on the hash bucket's contents.

## Love and Deepspace

The only shipped world-space 3D RC found, presented by Tianlong Ruan (Infold Games) at GDC 2026 in the Arm partner summit, "The Evolution of Real-Time Global Illumination in Love and Deepspace" (https://www.youtube.com/watch?v=H49TUZY1pL0, https://gdcvault.com/play/1035619/The-Evolution-of-Real-Time, and a re-upload with machine-translated Chinese subtitles at https://www.bilibili.com/video/BV1gAdBBcE9B). Only auto-captions exist, so names and terms are corrected from context and the GDC Vault listing, and the numbers are as spoken ([talks](../sources/2026_rc_conference_talks.md#love-and-deepspace-surfel-rc-on-mobile)).

The game (Unity 2019 with a custom pipeline, over 80 million players) lets players place furniture and follows real-world time of day, so GI must be dynamic, need no baking and run on phones without hardware ray tracing. It went through three versions:

1. SH-warped irradiance volumes with baked probes: cheap, but small-angle detail was lost and baked material data was needed.
2. Simplified ReSTIR with 8 steps of screen-space marching plus marching through probe data for off-screen hits, denoised with BMFR (chosen over SVGF because each pixel reads only its own features). It looked much better but cost 3.2 ms on an iPhone 12, ghosted after big changes, and still needed hand-placed probes.
3. Surfel radiance cascades, shipped.

The probes are world-space clipmap probes; the surfels are the scene the rays trace. So the design is a dense clipmap grid whose tracing proxy is surface-bound, unlike Coppen's surfel probes (derived from the description).

### Scene representation

- Each mesh asset gets surfels (position, normal, radius about 10 cm, four LOD levels) when it loads. They are generated by rendering the mesh into its lightmap UVs and spawning one surfel per texel, then thinning and respawning until coverage converges. Positions are stored in local space.
- Surfel IDs live in a multi-level hash grid keyed by cell position and LOD (prime table size 51,481, about 19 surfels per cell). Inserting or removing a surfel checks only its own cell.
- Rays march the hash grid, then test ray-disk intersections in each cell they cross. Ray-disk tests are cheaper than ray-triangle tests, and software BVH traversal of triangles was too slow on mobile.
- A coarse surfel BVH is rebuilt on the GPU every 4 frames, used for an early out on rays from probes that sit on the ground or high in the air.

At about 19 surfels per bucket, 51,481 buckets hold roughly 978,000 surfels (derived; the talk gives no total).

### Cascades and probes

- World-space probes in a three-level camera-following clipmap, 32×32×16 probes per level, about 1 m apart at level 0, doubling per level, about 64 m reach.
- Each probe's radiance is split by distance into cascades: probe count ÷8 per cascade (spacing ×2 per axis), directions ×4. Total storage is about twice cascade 0.
- Direction-first memory, so neighbouring probes for one direction sit together and hardware filtering works when probes are not occluded. Pre-averaging over 4 directions cuts memory above cascade 0 to about a quarter.
- Irradiance is stored as luma in SH and two chroma scalars, 16 bits per channel, as in Assassin's Creed Shadows.
- Ray tracing is spread across frames, and each ray's hit distance is cached after its path completes so the next trace starts at the right hash grid. The cache scrolls with the camera. The talk says this nearly removes the ray tracing cost.

The three levels hold 49,152 probes (derived). "About twice cascade 0" is the dense-grid model's `2·N³·D0` ([3D world space](3d_world_space.md#memory-and-rays)).

### Artifacts and fixes

| Problem | Fix |
|---|---|
| Light leaks through gaps between surfels | Each surfel gets a transparent outer ring. A hit counts if it lands on an inner disk once or on outer rings several times; overlapping hits blend albedo using four power moments of the hit points ([glossary](supporting_techniques.md)). |
| Indoor pixels read outdoor probes through trilinear filtering | Probes are tagged by indoor volume (one probe may have several tags) and the gather rejects mismatched types. Planned: movable occlusion planes on wall assets. |
| Cascade probes do not line up | Lower cascades overlap the higher ones. |
| All higher cascades occluded at a point | The lower cascade's ray length is raised temporarily; rare in practice. |

### Gather and timing

- Each pixel reads 8 probes with trilinear weights and type rejection. At full resolution this took 2.8 ms on an iPhone 12, so it runs at about 70% resolution (about half the time and bandwidth) and is upscaled.
- Each bounce converges in 28 frames, or 5 frames in a fast mode used on scene entry and light switches.
- Total GI is about 2 ms on an iPhone 12. Low-end devices use baked probes with six time-of-day keyframes instead.

At 70% per axis, 0.49 of the pixels are gathered, which matches "about half the time" (derived). The 2 ms total rests on spreading tracing over frames and on hit-distance caching, so the shipped figure is not a single-frame cost (inference).

## Probes on surface charts

Probes on a surface's UV chart keep each surface a 2D probe grid with hemisphere directions, so memory scales with surface texels and no probe sits inside a wall.

### X3XfRM (Mathis)

The Shadertoy "Radiance Cascades 3D" (https://www.shadertoy.com/view/X3XfRM, by Mathis, 2024-11-02; the community wiki credits Suslik, but the Shadertoy page names Mathis). The notes come from a Rust and wgpu port that keeps the original GLSL in `reference/shadertoy/` (https://github.com/uziiDevelopment/providentia-cascades, wgpu 26, 2026-07), because Shadertoy is behind a bot check ([X3XfRM](../sources/2024_mathis_x3xfrm_surface_probe_rc.md)).

**Scene and atlas:**

- An analytic box room (1 × 0.5 × 1) with an interior wall with two round holes, a mirror sphere and a mirror box, a moving sun and a sky, intersected analytically.
- Each cascade is one 1280×256 RGBA16F layer: floor and ceiling take 256×256 texels each and six walls 128×256 each, packed side by side without padding. The original uses a cube-map layout. There are six cascades.
- Cascade `c` probes are `P = 2^(c+1)` texels wide, so cascade 0 has 4 directions per probe and a probe every 1/128 units; each cascade has 4× the directions and ¼ the probes.
- The layout is direction-first: probe index `texel mod grid`, direction index `floor(texel/grid)`, with `grid = res/P`.

**Hemisphere directions:** a `P×P` square of texels mapped onto the hemisphere around the normal with concentric square rings. Offset `r = (k + 0.5) − P/2`, ring `m = max(|r.x|, |r.y|)`, polar angle `θ = m/P·π` (the source writes π as 3.14192653, a typo the port keeps), and `4 + 8·floor(m)` azimuth bins on ring `m`. Each sample's weight is its ring band's solid angle split across the ring, `(cos(θ − π/P) − cos(θ + π/P))/(4 + 8·floor(m))`, times `cos θ` for the diffuse integral. The same ring map is in [cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d).

**Trace:** rays start at the probe plus 0.001 along the normal. Cascades 0 to 4 trace up to `(1/64)·P·2` (0.0625 to 1.0 units) and cascade 5 to infinity. The stored alpha is the hit distance (−1 on a miss), not a transmittance. A hit on lit geometry stores `(previous-frame irradiance at the hit + shadowed sun)·albedo`, so the bounce comes from the previous frame's cascade 0 and builds up over frames; emitters store their emission, mirrors zero, and misses the sky.

**Merge:** each ray is cross-faded into its parent by hit distance instead of being composited with transparency. `l = 1 − clamp((t_hit − minDist)/maxInterval, 0, 1)` and `result = radiance·l + parent·(1 − l)`, with `minDist = maxInterval = 1.5·P/256` (cascade 0 starts at 0 with double the length), so rays that hit within the cascade's range keep their own value and rays that miss hand over to the parent. The parent value blends four parent probes bilinearly; for each, the parent direction pointing at the child is chosen and its stored hit distance read, and the parent counts only if it missed or if the child lies closer than that hit distance plus 0.01 (scaled by `cos(π/2 − θ)`). Hidden parents get zero weight, and the sum is divided by `max(0.01, weight)`.

The original merges from the previous frame's parent cascade, because Shadertoy runs each buffer once per frame. Its header lists the resulting flicker and light lag, light leaking from naive bilinear fetches at the smallest probes, static probe positions and no complex BRDFs. For the last two it suggests moving probes with the scene, as DDGI does, and importance-sampling both ray directions and probe positions from screen-space BRDF changes so that high-frequency detail is not blurred away. The port merges top-down within one frame, which removes the lag.

**Final gather:** per pixel, a primary ray finds the surface, and the irradiance is the sum of the probe's four cascade 0 direction texels (already weighted by solid angle and cosine), each read bilinearly between probes, times albedo, plus the shadowed sun. Mirrors get one reflection bounce, and the output goes through an ACES curve.

**Numbers** (derived): the six charts fill the 1280×256 layer exactly (327,680 texels), and six RGBA16F layers take 15.7 MB. At cascade `c` the probe spacing is `P/256` (0.0078 at cascade 0 to 0.25 at cascade 5), each ray traces up to 8 spacings, and the hand-over runs from 1.5 to 3 spacings (from 0 to 3 at cascade 0).

### yhyu13 surface-chart RC

https://github.com/yhyu13/radiance-cascades-demo (`3d/`, MIT) puts probes on the UV charts of a Cornell box, so each surface's cascades stay a 2D problem on its chart, as in X3XfRM ([survey](../sources/2026_rc_repository_survey.md#surface-chart-rc-yhyu13)).

- 8 charts (floor and ceiling 256×256 texels, walls and two interior boxes 128×256), texel scale 1/256 unit, 6 cascades in one 1024×512 RGBA32F atlas each, double buffered: 100.7 MB in all.
- Cascade `c` uses probes of `2^(c+1)` texels with one direction per texel, direction-first. Directions follow square rings: ring `i` has `4 + 8i` bins, polar angle from the ring and azimuth around it. Each direction is weighted by its solid angle times `cos θ`.
- The interval is `probeSize/32` units; the last cascade reaches 10000. Rays are traced analytically against quads, boxes, a cylinder and a mirror sphere, with one sun shadow ray at each diffuse hit.
- The merge blends 4 upper probes bilinearly. An upper sample counts only if it hit nothing or the lower probe lies inside its cone at the hit distance, a cheap visibility test. A miss uses the upper value alone.
- Bounce: a hit reads last frame's cascade 0 at its chart texel, so each frame adds a bounce.
- RTX 2080 SUPER, RenderDoc replay: 28.6 ms for all cascades on the full atlas, 5.95 ms once padding texels were skipped. The repository warns that replay timings vary 2 to 5×. Its earlier 128³ volume RC took about 37.7 ms.

The charts use 62.5% of each atlas (327,680 of 524,288 texels), so skipping padding explains 1.6× of the 4.8× speed-up; the rest is beyond what the texel count accounts for, within the 2 to 5× replay variance the repository warns about (derived).

### A generated surface atlas (Blackline Interactive)

Blackline Interactive's Spatium is a closed-source 3D RC in the author's own Metal engine, shown on a 2019 MacBook Pro's Radeon Pro 5500M, which has no ray-tracing hardware ([Blackline](../sources/2026_blackline_interactive_spatium_rc.md)). The author claims a single frame with no TAA, accumulation or denoiser, and no light leaks, and keeps the code and design closed. Nothing published states the design, but its HUDs, settings and pass names point to X3XfRM's chart RC generalized to arbitrary meshes (inference).

- **Lineage.** On 2026-08-17 the author ran a 2024 RC Shadertoy natively in the same engine, whose title and scene match X3XfRM (inference), two days before the first version of their own RC GI, and the RC builds keep its window title format. A world-probe build came first (2026-08-29: 7 cascades, cell size 1, 4 bounces, a rebuild button and no GI pass in the per-frame pass list) and was dropped.
- **What the HUDs and panels show.** Sponza reads "Atlas: 1024x1024 (19.9 cm/tex)", and the texel grows with the scene from 1.7 cm (Cornell box) to 24.7 cm (Sponza with 4K textures). The GI settings are "Interval (texels)" 2.0, "Normal Bias" 0.5, "Merge Cutoff" 0.35 and an irradiance filter with normal weights. Debug modes show the atlas UV apart from the material UV, and the irradiance. The passes are one per cascade, an irradiance filter, seams and a 0.5 to 0.7 ms gather, plus a camera pass for Whitted mirrors and glass. The author says the result is not a lightmap, since lightmaps need UVs made in advance.
- **Reconstruction.** Probes sit on the texels of a generated atlas, offset along the normal. Each cascade traces one ray per texel over its probe's hemisphere, as X3XfRM's layers do, in world space through a compute BVH (tinybvh is in the engine's library list). Irradiance per texel is filtered and seam-fixed in atlas space, then looked up per pixel (inference). The rays per cascade (0.68 and 0.85 M on a 1024² atlas, later 0.69 to 1.23 M) and the Cornell box's implied 198 m² of coverage against its 181.5 m² of walls fit one ray per texel per cascade. Two Sponza builds disagree by 2.1×, so this stays a hypothesis (derived).
- **Cost.** In the 2026-09-12 build the three cascade passes take 62 to 71% of the measured GPU time. On 2026-10-03 the GI takes 12.1 to 12.6 ms in a pillar room and the Cornell box, 11.4 to 18 ms in Sponza (5 cascades, 4.89 M rays per frame) and 15.9 to 27.8 ms in Intel Sponza with ivy (10.8 M triangles, 6.15 M rays), 55 to 79% of the GPU time. GI time follows rays and scene complexity, not pixels; the author reports 720p and 2K about 7 FPS apart. VRAM is 722 to 780 MB in the smallest scenes ([performance](performance.md#3d-world-space-and-surfaces)).
- **Leaks and limits.** The Cornell box's walls are single planes and do not leak, consistent with probes that cannot sit behind a wall and rays that hit true geometry. Indirect contact shadows are weak in every scene, which the author calls the only real problem: the texel, 10 to 25 cm, is cascade 0's probe spacing, so occlusion below it is lost (inference). A bug in the "visibility check" leaves black and white cuts in Bistro.

It is the only single-frame world-space RC on a compute tracer shown with timings, and it runs on a 50 W laptop GPU from 2019. The material does not show whether bounces use earlier frames, how the atlas is generated, or how moving meshes enter it.

### Other surface parameterizations

Quad patches from slicing a mesh with axis-aligned planes, 2×2 voxel blocks replaced by quads through their mass centres, and lightmap-UV probes (which grow with the scene and distort with automatic UVs) are listed among the sparse designs in [3D world space](3d_world_space.md#other-sparse-designs). Love and Deepspace uses lightmap UVs only to spawn its surfels.

## On-surface radiance caches (Tatzgern et al. 2024)

| | |
|---|---|
| Title | Radiance Caching with On-Surface Caches for Real-Time Global Illumination |
| Authors | Wolfgang Tatzgern, Alexander Weinrauch, Pascal Stadlbauer, Joerg H. Mueller, Martin Winter, Markus Steinberger (Graz University of Technology, Huawei) |
| Venue | Proc. ACM Comput. Graph. Interact. Tech. 7(3), article 38, July 2024 (HPG) |
| DOI | https://doi.org/10.1145/3675382 |

Not RC. It stores hemispheres of radiance in texture space on the surfaces themselves, the same placement idea as X3XfRM's UV probes, and shows what surface-bound caches gain and cost against screen probes and hash grids ([on-surface caches](../sources/2024_tatzgern_on_surface_radiance_caches.md)).

**Structure:**

- Meshes are split into texture-space islands (connected pieces limited by triangle count and normal spread). Cache entries live in blocks of 2×2 texels on these islands at several mip levels; 2×2 blocks instead of the earlier 8×8 cut memory by up to 14×.
- **Primary cache:** incoming radiance for surfaces visible from the camera, one entry per visible pixel's island texel, 8×8 hemisphere texels of RGB radiance plus hit distance in alpha. A mip bias of 1.5 to 3.5 sets the entry footprint.
- **Secondary cache:** outgoing radiance, 8×8 hemisphere texels, allocated where primary rays hit surfaces without one, at a fixed footprint of about 20 to 30 cm. Secondary entries trace into each other, so bounces build up over frames, and direct light comes from ReSTIR with a 28-byte reservoir per entry.
- A triangle ID map at its own resolution (mip bias −2) turns a jittered cache texel into a world position each update; too coarse a map gives black artifacts where many triangles share an entry.
- Entry size: two 8×8 arrays of half4 (radiance and hit distance), position and normal in full precision, plus 54 bytes of SH and four 64-bit neighbour pointers for the primary cache: 1134 bytes primary, 1076 bytes secondary.
- Entries not updated for 64 frames are freed.

**Update:**

- Each frame refreshes one quad in four; new entries update at once.
- Primary rays are guided by the cached radiance toward incoming light (as in GI-1.0 and Lumen). Small emitters can still be missed, which flickers.
- Each secondary update traces 32 cosine-weighted rays and applies the BRDF over all 64 directions per ray, one thread per hemisphere texel.
- Temporal filter: exponential average with weight `1/n`, `n` clamped to 4 to 8, reading last frame's value directly from the cache with no reprojection.
- Spatial filter: a separable blur of radius 3 in cache space, which needs no depth or normal tests because neighbours are on the same surface; it stops at island borders, so flat surfaces split into several islands show seams. Angle-error rejection (from Lumen) and parallax-corrected neighbour directions limit bleeding.
- After a light turns off, most entries converge within 32 frames; after one turns on, within 16.

**Lookup:**

- Pixels interpolate trilinearly between two mip levels of the primary cache. Diffuse shading converts the hemisphere to SH; glossy shading importance-samples it by the BRDF.
- One trilinear tap is picked at random with probability equal to its weight, which turns 8 cache reads into 1 at the cost of noise that the temporal filter removes.
- Reflections with roughness below 0.2 trace rays and read the secondary cache at the hit.
- Entries sit on the surface, so thin occluders do not leak, without the heuristics probes and hash grids need.

**Numbers** (RTX 3090 Ti, 1920×1080, Falcor, environment and emissive light only; in the extracted Table 1 the Effect and Display pairs sit one row low, and shifted back each row sums to its total):

| Scene | GI-1.0 | Cache | Effect | Display | Total |
|---|---|---|---|---|---|
| PicaPica | 1.78 ms | 0.27 | 0.78 | 0.40 | 1.45 ms |
| Sponza | 2.23 ms | 0.31 | 1.25 | 0.62 | 2.18 ms |
| Flying World | 1.82 ms | 0.32 | 1.01 | 0.39 | 1.72 ms |
| Bistro Exterior | 2.56 ms | 0.31 | 1.72 | 0.61 | 2.64 ms |

| Cache memory, one viewer | PicaPica | Sponza | Flying World | Bistro |
|---|---|---|---|---|
| Primary | 69 to 171 MB | 44 to 127 MB | 32 to 106 MB | 75 to 224 MB |
| Secondary | 89 to 185 MB | 93 to 134 MB | 55 to 242 MB | 116 to 456 MB |

- Error against a path-traced reference (FLIP, lower is better): 0.129 against GI-1.0's 0.256 on PicaPica, 0.063 against 0.073 on Sponza, 0.091 against 0.138 on Flying World, 0.153 against 0.226 on Bistro.
- Sampling the primary cache per pixel on Sponza: 0.54 ms at 1 sample, 0.98 ms at 8.
- Several viewers share the secondary cache, so cost grows sub-linearly with the viewer count.

**Limits:** quality depends on the island split, with seams at island borders, and neighbouring pixels on different islands each allocate an entry. Foliage and fine geometry multiply allocations (Bistro is the one scene slower than GI-1.0). 8×8 hemispheres lose highlights and mirror detail. There is no transparency, translucency or volumes.

The authors' HPG 2024 slides (https://highperformancegraphics.org/slides24/hpg24_oscgi.pdf) add that the predecessor (Weinrauch and Tatzgern 2023) stored only diffuse irradiance on surfaces and lost surface detail; that bad ray starts inside geometry caused artifacts until triangle IDs were decoupled at a higher resolution; that new primary entries are initialized from the adjacent mip level so mip transitions stay seamless; that glossy reflections from stochastic trilinear lookups are noisy; that one secondary entry can serve up to 20 readers; and that a single viewer needs 300 to 700 MB. The abstract claims a 5 to 10% gain in speed and quality over the state of the art. GI-1.0, the baseline, is in [related radiance caches](related_radiance_caches.md).

## A radiance field stored on a plane

Sannikov's "Radiance Cascades Rendered Directly" (2023-08-19) renders stored cascades directly, to show what data they hold ([videos](../sources/2022_sannikov_youtube_rc_videos.md#radiance-cascades-rendered-directly-2023)):

- A volume was path traced once, and its radiance field was stored as a cross-section on one plane. The volume is then unloaded; the demo does no tracing or ray marching.
- Rendering takes under 0.5 ms on the GPU, at constant cost: each pixel reads only the data stored for it. The CPU side in the recording is slower because validation layers are on (01:13).
- There are four cascades, each covering one depth range. Cascade 0 has the highest spatial and lowest angular resolution; cascade 3 has the opposite and is in effect an environment map of infinitely distant light.
- Each next cascade has twice the angular resolution and half the spatial resolution.
- All cascades are stored in one 2D texture of about 8K. Each cascade is an atlas of small cube maps in a parabolic projection, one per probe. The size is more than GI needs and was chosen for direct viewing.
- Penumbras need fine spatial resolution near their origin and less farther away; angular resolution follows the opposite pattern. RC is built to hold both, so the same structure holds ambient occlusion, soft shadows and environment light.

The video stores a 3D scene's light on a 2D surface, the plane, which is the surface-probe idea taken to its limit: a light field over one plane, the two-plane form HRC's frustums also use ([holographic RC](holographic_rc.md#background-light-fields-and-line-space)) (inference). tmpvar's playground links it as its demo video ([2D articles and demos](2d_articles_and_demos.md#tmpvars-playground)).

## Connections

- **Hit distance as free visibility.** X3XfRM, yhyu13's charts and Mathis's M3ycWt all store each ray's hit distance and count a parent only if the child lies in front of the parent's hit; Love and Deepspace's outer rings and Tatzgern's on-surface entries reach the same no-leak goal from the scene side. Surface designs get visibility from geometry they already store, where world grids need extra rays or bits ([3D world space](3d_world_space.md#leak-defences-in-world-space)) (inference).
- **Hand-over instead of intervals.** X3XfRM and M3ycWt trace every ray from the probe and cross-fade it into the parent by hit distance, while Coppen and Love and Deepspace use RC intervals. The cross-fade is a soft form of ray splitting: a ray to its first hit decides which cascade holds it ([3D world space](3d_world_space.md#ray-splitting)) (inference).
- **Surfels in two roles.** Coppen's surfels are probes that need spawning, recycling and a hash grid every frame; Love and Deepspace's surfels are a tracing proxy built once per mesh, with ordinary clipmap probes. Only the second shipped, and its probes are a dense world grid ([3D world space](3d_world_space.md#dense-grids)) (inference).
- **Islands and charts trade leaks for seams.** On-surface storage removes leaks through thin walls and adds seams at chart or island borders, the same trade lightmaps make (Tatzgern's seams, yhyu13's and X3XfRM's per-wall charts) (inference).
- **Charts scale from rooms to scenes.** X3XfRM and yhyu13 put RC on hand-made charts of analytic rooms. Blackline's builds point to the same layout on a generated atlas of arbitrary meshes, which trades hand-made charts for an atlas generator and seams: the lightmap pipeline without the bake (inference).
- **GIBS is the common ancestor of surfel maintenance.** Coppen's spawn and recycle heuristics, transform IDs and trapezoidal grid all come from GIBS ([related radiance caches](related_radiance_caches.md)).

## Single-frame assessment

- **Surfel probes are temporal state.** Coppen's spawning adds at most one surfel per 16×16-pixel tile per frame, so a cleared set takes at least 32 frames to fill at 1080p, and the recycling heuristic keeps surfels for 9 to 18 passes. The gather and merge run every frame without history, but the probe set itself converges over frames, and fast camera motion exposes surfaces without surfels (derived).
- **Love and Deepspace is not single-frame.** Tracing is spread over frames with cached hit distances, and each bounce converges in 28 frames (5 in a fast mode).
- **UV charts are single-frame compatible; the chart is the cost.** X3XfRM's port merges top-down within one frame; the bounce still comes from the previous frame. Charts need authored or generated UVs, at a seam cost. Blackline's builds suggest that a generated atlas carries Sponza, Bistro and a 10.8 M-triangle scene in 11 to 28 ms of GI on a 2019 laptop GPU, which makes the chart requirement an engineering cost rather than a limit on arbitrary meshes (inference from video HUDs; [surface atlas](#a-generated-surface-atlas-blackline-interactive)).
- **Under `RenderingDevice`:** Coppen's pipeline needs only 32-bit atomics (counters, stack, atomic max per tile) and a compute BVH, so it maps onto Godot compute, but its 423 MiB at six cascades of 2048² RGBA16F textures (64 MiB per cascade before buffers) is set by texture size, not by surfel count (derived).
- **What carries over:** surface-bound tracing proxies (surfels with ray-disk tests, as on phones) for a compute tracer without hardware RT, and hit-distance visibility tests in the merge (inference).

## Open questions

- Can surfel probes be spawned fast enough for a single frame, for example one per pixel block every frame as Split RC inserts probes, without the coverage test's dependence on last frame's grid?
- Does an interval length that scales with surfel size (Split RC's `t0` per LOD) fix Coppen's depth-dependent error balance?
- Would a surfel tracing proxy built per mesh (Love and Deepspace) make long software rays cheap enough for ray splitting under `RenderingDevice`?
- How do on-surface charts handle dynamic and skinned meshes, given that their islands and triangle ID maps are built per mesh?
- Is the hit-distance parent test enough to stop leaks in a 3D sparse grid, where parents are not on the same surface as the child?
- How would a generated atlas handle moving and skinned meshes, and can it be rebuilt per change at Godot's mesh counts?
- Can a screen-space cascade −1 restore the contact shadows that a 10 to 25 cm atlas texel loses, without the screen-space family's disocclusion problems?
