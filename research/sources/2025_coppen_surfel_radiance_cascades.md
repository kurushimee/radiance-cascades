# Surfel Radiance Cascades (src-dgi)

| | |
|---|---|
| Author | Max Coppen (mxcop / m4xc) |
| Date | Article dated 2025-01-22; repository last commit 2026-08-10 |
| Kind | repository + articles |
| Link | https://github.com/mxcop/src-dgi and https://m4xc.dev/articles/surfel-maintenance/ |
| License | MIT |

The repository is a Vulkan implementation written in Slang (compiled to SPIR-V) inside a custom C++ engine named "wyre" in the source. It is not a Godot project. It keeps six cascades of surfel probes, where cascade 0 has 262,144 probes and each later cascade has a quarter as many. Each probe holds a 4x4 to 128x128 grid of directional intervals, which are ray traced against the scene BVH, merged from the coarsest cascade down, and finally gathered per pixel from cascade 0.

## Frame order

Order taken from GIStage::enqueue in the stage file:

1. Primary G-buffer pass (ray-tracing/primary.slang, ray traced from the camera). Written before the GI stage.
2. Spawn, for cascades 0 to 5. It reads the hash grid and list left by the previous frame.
3. Clear each cascade's hash grid to zero.
4. Count, for all cascades.
5. Prefix sum, for all cascades.
6. Read back each cascade's live surfel count (used only by the debug panel).
7. Insert (acceleration pass), for all cascades.
8. Gather, for all cascades.
9. Merge, in this order: cascade 4 from 5, cascade 3 from 4, 2 from 3, 1 from 2, 0 from 1.
10. Composite, cascade 0 only.
11. Optional debug passes (direct draw, heatmap).
12. Recycle, for all cascades.

A separate ground-truth pass replaces steps 2 to 12 when its flag is set.

## Parameters

Defaults from SurfelCascadeParameters (cascade.cpp) unless noted.

| Name | Value | Notes |
|---|---|---|
| CASCADE_COUNT | 6 | Constant with a TODO to make it a parameter. |
| c0_probe_capacity | 262144 (2^18) | Cascade N capacity = 262144 / 4^N. |
| c0_memory_width | 4 | Intervals per probe side. Cascade N uses 4 * 2^N. |
| c0_probe_radius | 0.002 | Cascade N radius = 0.002 * 2^(N+1). |
| max_solid_angle | 0.005 | Used for the interval length. |
| c0_grid_capacity | 262143 (512*512 - 1) | Same for every cascade. The grid buffer has one extra entry. |
| c0_grid_scale | 70.0 | Cascade N scale = 70 / 2^N. |
| cell_capacity | 11 | Stored and bound to the UI; no shader reads it for logic. |
| Surfel list entries per probe | 16 | List size = 16 * capacity. |
| SPATIAL_FACTOR | 4 | Probe count divides by 4 per cascade. |
| ANGULAR_FACTOR | 4 | Interval count multiplies by 4 per cascade. |
| Spawn chance | 1 / 2^N | See Spawning. |
| Camera vertical FOV | 90 degrees by default | Passed to shaders in radians (renderer.cpp, camera.h). |
| Near and far planes | 0.1 and 1000 | From renderer.cpp. |
| Radiance texture format | RGBA16 float, 2048 x 2048 | Same size for every cascade (see Cascade layout). |

The cascade_t comment in cascade.slang says the struct is 36 bytes. The C++ struct has seven 4-byte fields (28 bytes). The source does not reconcile the two.

## Surfel storage

Per cascade, allocated in SurfelCascadeResources::alloc. Sizes use the cascade's own capacity C.

| Set 0 binding | Name | Size in bytes | Layout |
|---|---|---|---|
| 0 | params | sizeof(SurfelCascadeParameters) | Uniform buffer, uploaded once at allocation. |
| 1 | surfel_stack | 4 * (1 + C) | Entry [0] is the live count. Entries [1..count] hold live surfel IDs. Entries above count are free IDs. Initially count = 0 and entry 1+k = k. |
| 2 | surfel_grid | 4 * (262144) | Hash bucket start indices. |
| 3 | surfel_list | 4 * 16 * C | Surfel IDs grouped by bucket. |
| 4 | surfel_posr | 16 * C | xyz = world position, w = radius squared. Radius 0 means dead. |
| 5 | surfel_norw | 16 * C | xyz = normal, w = recycle marker. |
| 6 | surfel_rad | RGBA16F 2048 x 2048 | Radiance cache written by gather. |
| 7 | surfel_merge | RGBA16F 2048 x 2048 | Merged radiance cache. |

Totals per cascade (C from the table above):

| Cascade | Probes | Bytes (all buffers and textures) |
|---|---|---|
| 0 | 262144 | 94,371,844 |
| 1 | 65536 | 74,711,044 |
| 2 | 16384 | 69,795,844 |
| 3 | 4096 | 68,567,044 |
| 4 | 1024 | 68,259,844 |
| 5 | 256 | 68,183,044 |

All six together come to 443,888,664 bytes (about 423 MiB). Each radiance texture is 32 MiB. The hash grid is 1 MiB per cascade.

A surfel ID is an index into posr and norw. The same ID is the probe index used to find the probe's block in the radiance textures.

## Spawning (spawn.slang)

- Dispatch: 8x8 threads per group, ceil(W/16) by ceil(H/16) groups. Each thread handles one pixel of a 2x2 block.
- The pixel inside each 2x2 block is chosen by the frame index bits (frame & 1, (frame >> 1) & 1). Each frame therefore tests one quarter of the pixels, rotating through the four positions over four frames. A 16x16 pixel tile is one group.
- Skipped pixels: albedo alpha between 0.4 and 0.6 (emitters), depth at or below 0 or at or above 1000 (sky has depth 2000), and grazing pixels where dot(-view ray, normal) is below 0.01.
- The surface point is origin + ray * depth + normal * 0.0001.
- Coverage test: look up the hash bucket of that point at the cascade's grid scale, using the previous frame's grid and list. For each surfel in the bucket, cover = (squared distance to surfel) / radius_squared - 1. If any cover is below 1, the pixel is rejected (the point is inside sqrt(2) radii).
- Each surviving pixel makes a candidate = (min(65535, uint(cover * 1000)) << 16) | local index in the tile. The group keeps the candidate with the highest value by atomic max. Only the lane holding that value continues.
- Random gate: accept if pcg1d(frame * W * H + y * W + x) <= UINT_MAX / 2^N. The seed does not include the cascade index.
- Allocation: pop the stack with an atomic increment. If the popped index is at or above the capacity, clamp the counter to capacity and stop.
- Stored values: position, radius squared, normal, and recycle marker 2.0. Radius = max(R_N, R_N * depth * fov), where both terms use the same expression in the code (R_N is the cascade radius).

## Acceleration structure (hash grid)

Functions are in shared/hash.slang.

- Grid level of a point: L = clamp(2 + trunc(log2(d^2)), 0, 31), where d is the distance to the camera (renderview origin). The code computes log(d^2) * 0.7213477 and truncates it.
- Cell size at level L: 2^L / (4 * scale_N).
- Cell index on an axis: floor(coordinate / cell size).
- Hash key: x, y, z each taken mod 512 and packed in 9 bits, level taken mod 32 in 5 bits (bits 27 to 31). The packed key goes through xxhash32, then mod the grid capacity.
- Surfel footprint: the axis-aligned box around (position +/- radius). The code computes two levels: the level of the point farther from the camera (position + radius * normalized(position - camera)) and the level of the point nearer to it. It inserts into the first level, and into the second if the two levels differ. The code names the first value "min", but it is the farther point's level, which is usually the larger one.
- Count pass: one atomic increment per (cell, level) bucket the footprint covers.
- Prefix pass: inclusive prefix sum over the whole grid buffer, including the sentinel entry at index capacity.
- Insert pass: each surfel decrements its buckets' counters and writes its ID at the new counter value. After this, grid[h] = start of bucket h, and grid[h+1] = end of bucket h. The sentinel holds the total.
- Insert overflow: if the write index reaches 16 * capacity, that level's insert stops.
- Query: each consumer reads one bucket, at the query point's own level. It does not search neighboring cells. Hash collisions can return distant surfels, so each consumer filters by distance.

## Recycling (recycle.slang)

- Dispatch: 256 threads per group over the whole pool. Only live surfels (radius squared not zero) do work.
- Radius update: R_N * max(1, distance to camera) * fov, stored squared.
- Marker: the recycle marker is reduced by 0.125 each pass. The value read at the start of the pass is used for the forced test.
- Heuristic: if the marker read is below zero, recycle with probability 1. Otherwise, count the other live surfels in the same bucket for which (squared distance / radius squared - 1) is below 0.5 (i.e. the other surfel's center is within about 1.22 radii). Each one adds 0.2. The total is not clamped.
- Random gate: recycle when pcg-based random value / 2^32 is below the heuristic. The seed is frame index plus surfel ID.
- Recycle: set radius squared to 0, decrement the counter, and write the ID into the slot the decrement opened.
- Marker resets: merge sets the marker to 1.0 on each source surfel it reads, and composite does the same on each surfel it reads. Gather does not.
- A surfel that is never read keeps the marker it was given at spawn (2.0) and is forced out at about the 18th recycle pass after spawn. A surfel read by merge or composite is forced out about 9 passes after its last read.
- Commented-out code contains a frustum test and a coverage test that are not active.

## Cascade layout and interval geometry

- Probes per cascade: 262144 / 4^N.
- Intervals per probe: (4 * 2^N)^2 = 16 * 4^N.
- Every cascade has the same number of texels: 2048 x 2048 = 4,194,304. The cache width is memory_width * sqrt(capacity) = 2048 for every N.
- Probe to texel block: probe index p maps to block (p mod 2048/mw, p div 2048/mw), and each block is mw by mw texels. Within a block, interval (u, v) is at texel offset (u, v).
- Directions: interval center uv = (id + 0.5) / mw, mapped to a unit vector with the equal-area octahedral decode (shared/octahedral.slang). Directions cover the full sphere. No hemisphere mapping is used.
- Parent-child nesting: a 2x2 block of cascade N+1 intervals covers exactly one cascade N interval. The four child centers sit at the parent's uv plus or minus 0.25 cells.
- Base interval: base = max_solid_angle * 16 / 4pi = 0.0063662 (cascade.slang uses 12.56637 for 4pi).
- Interval range (ray t from the probe): cascade 0 = [0, 4 * base]; cascade N >= 1 = [4^N * base, 4^(N+1) * base].

| Cascade | Probes | Memory width | Intervals per probe | Probe radius R | Grid scale | Interval range (world units) |
|---|---|---|---|---|---|---|
| 0 | 262144 | 4 | 16 | 0.004 | 70 | [0, 0.025465] |
| 1 | 65536 | 8 | 64 | 0.008 | 35 | [0.025465, 0.101859] |
| 2 | 16384 | 16 | 256 | 0.016 | 17.5 | [0.101859, 0.407437] |
| 3 | 4096 | 32 | 1024 | 0.032 | 8.75 | [0.407437, 1.629747] |
| 4 | 1024 | 64 | 4096 | 0.064 | 4.375 | [1.629747, 6.518987] |
| 5 | 256 | 128 | 16384 | 0.128 | 2.1875 | [6.518987, 26.075947] |

- Rays per frame if every probe is alive: 6 * 4,194,304 = 25,165,824 (one per texel).
- Probe spacing: the source does not state a spacing value. Cascade density comes from the count quartering, the spawn chance 1/2^N, and the hash grid scale.

Radiance-cache layout detail: the cache texel of an interval belongs to a single probe, so gather writes whole blocks by probe.

## Gathering (gather.slang)

- Dispatch: one thread per texel of the 2048 x 2048 cache, 16x16 threads per group, so 128 x 128 groups for every cascade.
- A thread finds its probe (texel / mw) and interval (texel mod mw), then the interval direction.
- Dead probe: writes (0, 0, 0, 1) to both rad and merge for each of its texels.
- Trace: the ray starts at probe position + direction * interval start, runs for (end - start), and is intersected with the scene BVH. The BVH is a binary tree with a 32-entry traversal stack. Triangles are tested with Moller-Trumbore. The traversal code credits tinybvh.
- Result: visibility = 1 if no hit within the interval length, otherwise 0.
- Radiance:
  - No hit, cascade 5 only: sky color from sky.slang at an animated sun direction (time = frame * 0.01666).
  - No hit, other cascades: 0.
  - Hit on an emitter (any color component above 0): the emitter color.
  - Hit on a non-emitter: 0. Non-emissive surfaces are not shaded and do not re-emit.
- The cosine term is fixed to 1.0 here. Composite applies it (see Composite).
- Output: rad = merge = (radiance, visibility).
- Options in the file, both off by default: JITTER (random position in the interval, blended over 8 frames) and TEMPORAL (trace one texel per 4x4 block per frame).
- The file gather_tx4.slang is a variant using a 4x4 temporal pattern. No C++ code references it.

The radiance cache therefore holds only direct emitter and sky light. The source does not state whether a bounce term is intended.

## Merging (merge.slang)

- Dispatch: 16x16 threads per group over the destination cascade's 2048 x 2048 texture, so 128 x 128 groups.
- Only live destination probes do work. Dead probes keep the (0, 0, 0, 1) written by gather.
- For each destination texel:
  1. Look up the source (cascade N+1) bucket at the destination probe's position offset by 0.01 times its normal, using the source grid scale.
  2. Keep up to four source surfels from that bucket. Skip any with squared distance above 25 times the source radius squared. Score = squared distance + (1 - dot(normal, source normal))^2. Keep the four lowest scores.
  3. For each kept source surfel i, read the 2x2 block of source texels at (2u, 2v) to (2u+1, 2v+1), where (u, v) is the destination interval. Compute far = average of merge(near, far_j) over the four texels, where near is the destination merged texel and merge(near, far) = (near.rgb + near.a * far.rgb, near.a * far.a).
  4. Result = sum over i of w_i * far_i divided by sum of w_i, with w_i = 1 / (score_i + 0.0001).
- Source surfels read here get marker 1.0.
- For N = 5 the source texels come from the source rad texture rather than merge (the code says this should not be hard-coded).
- Only the merge texture is written.

## Composite (composite.slang)

- Dispatch: 8x8 threads per group over the window, ceil(W/8) by ceil(H/8).
- Pixels with albedo alpha between 0.4 and 0.6, or depth at or above 1000, or at or below 0 are returned unchanged. Emitter and sky pixels therefore keep the primary pass color.
- Position = origin + ray * depth + normal * 0.00001.
- Candidates: up to four cascade-0 surfels from the bucket at that position. Score = squared distance + (1 - dot)^2. Candidates with score above 8.0 are dropped, which is a fixed threshold in world units (about 2.8 units of distance on position alone). No radius filter is applied.
- For each candidate i: S_i = (1 / 16) * sum over the 4x4 texels of its cascade-0 merge block of (L * (1/pi) * max(0, dot(normal, interval direction))). The factor 1/16 is solid_contribution = (1/mw)^2 with mw = 4.
- Final = albedo * (sum of w_i * S_i / sum of w_i) * 4pi, then ACES tonemapping. Output is (color, 1.0), written over the albedo buffer.
- Candidate surfels get marker 1.0.
- The file header comment reads as a copy of the debug pass header. The code is the composite.

## Pass table

Thread counts are from the shaders. Dispatch sizes are for cascade 0 at its default capacity, with W and H the window size.

| Pass (file) | Threads per group | Dispatch | Reads | Writes |
|---|---|---|---|---|
| Primary G-buffer (ray-tracing/primary.slang) | 16x8 | ceil(W/16) x ceil(H/8) | BVH, prims, normals, view | albedo (rgb, alpha), normal-depth |
| Spawn (spawn.slang) | 8x8 | ceil(W/16) x ceil(H/16), per cascade | albedo, normal-depth, grid, list, posr, norw | stack, posr, norw |
| Count (count.slang) | 128 | ceil(C/128), per cascade | posr | grid (atomic increments) |
| Prefix sum, pass 1 (prefix_sum.slang) | 512 | 512 groups (see Observations) | grid | grid (in place), segments |
| Prefix sum, pass 2 (prefix_segments.slang) | 512 | 1 group | grid, segments | segments |
| Prefix sum, pass 3 (prefix_merge.slang) | 512 | 512 groups | grid, segments | grid |
| Insert (accelerate.slang) | 128 | ceil(C/128), per cascade | posr | grid (atomic decrements), list |
| Gather (gather.slang) | 16x16 | 128 x 128 | posr, BVH | rad, merge |
| Merge (merge.slang) | 16x16 | 128 x 128 | dst and src grid, list, posr, norw, rad, merge | dst merge; src marker |
| Composite (composite.slang) | 8x8 | ceil(W/8) x ceil(H/8) | albedo, normal-depth, cascade 0 grid, list, posr, norw, merge | albedo |
| Recycle (recycle.slang) | 256 | ceil((1 + C)/256), per cascade | stack, grid, list, posr, norw | posr, norw, stack |
| Direct draw (direct_draw.slang, debug) | 16x8 | ceil(W/16) x ceil(H/8) | not read in detail | not read in detail |
| Heatmap (heatmap.slang, debug) | 16x16 | ceil(W/16) x ceil(H/16) | not read in detail | not read in detail |
| Ground truth (ray-tracing/ground_truth.slang) | 8x8 | ceil(W/8) x ceil(H/8) | BVH, albedo, normal-depth | accumulator, albedo |

## Ground-truth pass (reference)

- Enabled by a GIStage flag. It bypasses the entire RC pipeline.
- Per pixel per frame: trace one uniformly random direction from the surface. If it hits an emitter, add material * (1/pi) * max(0, dot(normal, direction)). Blend into the accumulator with alpha. Misses add nothing, so this reference has no sky term.
- Output: albedo * accumulator * 4pi, then ACES tonemapping.

## Artifacts and fixes

The source names few artifacts. The points it does address:

- Grazing views are rejected (spawn) "to avoid floating point imprecision".
- Depth at or above 1000 is rejected (spawn) to avoid NaN surfels.
- Emitters are excluded from spawning, and composite leaves emitter pixels unchanged.
- Dead probes write (0, 0, 0, 1), so later passes see an empty interval.
- The prefix sum keeps the last grid entry empty as its sentinel.
- Cosine term: the code comments say that applying the cosine in composite, and also applying it in gather, both produced artifacts. The current code fixes it to 1.0 in gather and applies it in composite. The artifacts themselves are not described (unclear in source).
- Spawn cost: the article reports spawn time going from about 6 ms to about 1 ms on an AMD Radeon 890M iGPU after the quarter-pixel rotation was added. The article says the quality loss was not significant.
- WHITE_FURNACE (off) writes constant radiance 0.5 at cascade 5 for a furnace test.

## Performance

Captured timings are read from the figures; the article text does not repeat them.

| Pass | AMD Radeon 890M iGPU (article fig. L) | RTX 4070 Mobile (article fig. M) |
|---|---|---|
| Surfel spawning | 0.6 ms | 0.18 ms |
| Hash counting | 0.25 ms | 0.10 ms |
| Hash prefix sum | 0.2 ms | 0.15 ms |
| Hash insertion | 1.0 ms | 0.19 ms |
| Recycling | 0.4 ms | 0.20 ms |

- Both captures use six cascades. Resolution is not stated (unclear in source).
- The article says insertion is the most expensive pass on the 890M, and recycling on the 4070.
- README profile (pipeline.png): a frame of 16.27 ms with 12.15 ms active. Surfel Gathering is 5.35 ms and Surfel Merging is 2.04 ms. The spawn and composite bars are not labeled with values. Hardware and resolution are not stated (unclear in source).

## Limitations and future work

From the author's article:

- The transform pass is not implemented. Surfels are stored in world space and do not move with the geometry they sit on. The article describes the GIBS-style transform-ID approach but says it was skipped for time.
- Hash collisions can return distant surfels.
- A plain uniform grid was rejected for scaling. The trapezoidal grid used by GIBS was not implemented.
- The 16x16 tile size may need changing for different surfel sizes.
- The article lists "time since used" and "live count" as heuristic terms. The code does not use them.

From the source comments (TODO and WARN):

- Branch factors must be divisible by 2 for the half-scale helpers. The factors are not parameters.
- The cascade count is a constant. The top cascade is hard-coded as index 5 in gather and merge.
- Radiance is stored as 16-bit float. A TODO asks for a 32-bit HDR format.
- Tonemapping is inside composite. A TODO asks for a separate pass.
- Lambert's term is applied in composite. A TODO asks to move it into merge.
- HDR encode and decode are identity functions (the mapping code is commented out).
- JITTER and TEMPORAL are off.

## Observations from reading the code (not run)

These are readings of the source. None was tested.

1. Stack push may corrupt the free list. stack_push writes the recycled ID into slot 1 + new_count, which was the last live slot before the decrement. The recycled ID stays in its original live slot, and the previous last live ID is overwritten and lost from the array. Per the code, this can duplicate one ID and drop another. The article describes the same write and does not address the case where the recycled ID is not in that slot.
2. Barrier in divergent flow. Spawn returns early (albedo skip, depth, grazing, coverage fail) before GroupMemoryBarrierWithGroupSync. Only some lanes of a group reach the barrier. Vulkan leaves a barrier undefined unless every invocation in the group reaches it.
3. Merge with no source candidates writes zero. If no candidates are kept, radiance_sum stays zero and weights_sum is about 4e-30. The result is 0 / tiny = 0, which overwrites the near radiance from gather with (0, 0, 0, 0). A zero alpha is read later as fully occluded.
4. Random seeds are shared across cascades. The spawn seed omits the cascade index. The accept test is monotone in N, so a pixel accepted at a higher cascade is also accepted at every lower one, if the coverage test passes.

## Links found

- https://github.com/mxcop/src-dgi (repository)
- https://m4xc.dev/articles/surfel-maintenance/ (article read)
- https://m4xc.dev/articles/ (article index)
- https://m4xc.dev/articles/fundamental-rc/ (covered by another agent)
- https://github.com/Raikiri/RadianceCascadesPaper (cited in readme for radiance cascades)
- https://www.ea.com/seed/news/siggraph21-global-illumination-surfels (EA SEED GIBS, cited in readme and article)
- https://youtu.be/h1ocYFrtsM4 (GIBS talk, SIGGRAPH 2021, cited in article)
- https://media.contentapi.ea.com/content/dam/ea/seed/presentations/2019-ray-tracing-gems-chapter-25-barre-brisebois-et-al.pdf (Ray Tracing Gems 2019 chapter, cited in article)
- https://github.com/h3r2tic/kajiya (prefix sum source and surfel GI reference, cited in article and shader headers)
- https://github.com/jbikker/tinybvh (BVH traversal credit in bvh.slang)
- https://jcgt.org/published/0003/02/01/paper.pdf (octahedral mapping, cited in octahedral.slang)
- https://pbr-book.org/4ed/Geometry_and_Transformations/Spherical_Geometry#x3-Equal-AreaMapping (equal-area mapping, cited in octahedral.slang)
- https://jcgt.org/published/0009/03/02/ (xxhash32, cited in hash.slang)
