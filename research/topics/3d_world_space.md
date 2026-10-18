# World-space 3D radiance cascades

World-space RC stores probes in the scene rather than on the screen, so it sees off-screen and hidden light and can light volumes. The open problem is cost: a dense 3D grid at useful resolution needs gigabytes, so every working design is sparse. This note compares the designs found, from naive dense grids to the shipped mobile system. Screen-space designs are in [3d_screen_space.md](3d_screen_space.md); theory is in [core_theory.md](core_theory.md).

## Parameter choice in 3D

Split RC gives the clearest rule. With probe spacing `Δs_n = Δs0·2^n`, directions `|Ω_n| = |Ω0|·K^n`, and interval cutoff `t_n = t0·l^n`, the angular error at the end of a ray is `Δω_n = (l/√K)^n·Δω0`. Making angular and spatial error equal in every cascade gives `K = 4, l = 4` in 3D. Most earlier 3D projects used `l = 2` (the paper's original 3D law: directions ×4, intervals ×2), which keeps angular error constant but lets error drift from aliasing near lights to blur far away. Split RC's settings: `|Ω0| = 32`, `t0 ≈ 1.6·Δs0` (chosen so the gap between ray ends matches the probe spacing, `√(32/4π) ≈ 1.596`), 4 cascades. With `l = 4`, 4 or 5 cascades span a whole scene.

| Project | Cascade 0 directions | ×dirs | Interval ratio | Cascades |
|---|---|---|---|---|
| Split RC paper, chandra, wroughtinator | 32 (equal-area 8×4) | 4 | 4 | 4 |
| Surfel RC (Coppen) | 16 (oct 4×4) | 4 | 4 | 6 |
| Love and Deepspace | not given | 4 | not given | 3 clipmap levels, cascades per probe |
| erhe | 64 (oct 8×8) | 4 | 2 | up to 8 |
| tmpvar 3D grid | 36 (oct 6×6) | 4 | 4 | 6 |
| CT volume RC | 6 (cube faces) | 4 | 2 | 5 |
| tauray RCPG | 16 (oct 4×4) | 4 | angle table | 5+ |
| jumeder DX12 | 2048 (lat-long) | 4 | 8 | 4 |

Other sparse RC builds ([sparse 3D notes](../sources/2026_sparse_and_3d_rc.md)) agree with the table: 4× interval scaling, 6 cascades and about 200k cascade 0 probes for Sponza, and a cascade 0 interval of about 0.015 scene units. 8 cascade 0 directions showed obvious artifacts and saved nothing over 32, and the penumbra condition counts rays cast, so several rays per stored cone help more than more stored directions.

## Direction layouts

- **Children must be contiguous.** The merge averages the 4 child directions `4a … 4a+3` of a parent, so direction indices must follow a quadtree. Morton order over a 2D direction grid does this. The CT volume project used row-major cells per cube face, so from cascade 1 up its "children" were four cells in a row, two of them outside the parent.
- **Equal-area cylindrical** (Split RC): `encode(ω) = (frac(atan2(y, x)/2π), (z + 1)/2)`, `2n × n` cells, parent of `(j, k)` is `(j/2, k/2)`. It beat octahedral and Clarberg equal-area maps in quality despite less uniform spacing.
- **Octahedral** (Surfel RC, erhe, tmpvar, tauray): children of texel `(u, v)` are `(2u…2u+1, 2v…2v+1)`. Texels differ in solid angle, so weight by true texel solid angle (erhe precomputes lobe weights by splitting each texel into sub-squares, `dA·|w|₁³`). Equal-area octahedral decode (Surfel RC) avoids the weights. Filtering across the fold needs a 1-texel border ([octahedral notes](../sources/2014_cigolle_octahedral_unit_vectors.md)).
- **Fibonacci sphere** (creikey's screen-space voxel RC): no clean child structure; indices `4k…4k+3` share a height band but spread in azimuth.
- Lat-long grids need solid-angle weights; jumeder's project did not apply them.

## Designs

### Dense grids

A full grid over a box is the paper's 3D grid case and the easiest to write, but memory explodes. tmpvar's 64³ grid with a 4096² atlas per level took 1.8 GB per atlas; jumeder's 32³ grid with 2048 directions took 960 MB and 126 M rays per update; the 192³ CT volume grid allocated about 1.5 GB. tauray's RCPG keeps a 128³ volume affordable (about 325 MB) by storing luminance only and tracing only "live" probes found from a conservative voxelization's occupancy mips. These projects are useful for index math and edge cases, not as a design to ship. Known bugs in them: upper-index clamps one past the grid edge and wrong edge weights for probe 0 (tmpvar), and half-cell gather offsets when probe centers sit at `i + 0.5`.

### Dense grid reduced into DDGI probes (erhe)

erhe fits a grid of up to 65,536 cascade 0 probes (1.5 m spacing) to visible content, traces 131,072 texels per frame round-robin with hysteresis 0.9, merges, then cosine-convolves cascade 0 into DDGI's 6×6 irradiance and 14×14 distance octahedral maps. The renderer's DDGI sampling then works unchanged. The default merge, `per_neighbour_trace`, traces one visibility ray from `p + t_{i+1}·d` to each of the 8 upper probes' interval starts and drops blocked ones, a binary 3D bilinear fix. Measured against DDGI on its own test scenes: 1.15 to 1.57× the update cost, passes room-pair leak tests, but fails on probes embedded in floors (no relocation), small emitters, corridor far fields, and settling speed. The reduction to DDGI maps is 60% of the update cost. Jittering ray directions helped the near field but leaked through thin walls and added noise.

### Sparse probes near visible surfaces (Split RC)

The most complete published design ([paper](../sources/2026_freeman_split_radiance_cascades.md), [implementations](../sources/2026_split_rc_implementations.md)):

- **Probes:** one hash map per cascade. Each pixel inserts its nearest cascade 0 probe, and each probe inserts its nearest parent, so only probes near visible surfaces exist. Interpolation is sparse trilinear: sum the existing neighbors' weights and renormalize. Probe positions sit at half-cell offsets so cascades never align.
- **LOD:** `lod = log2(Chebyshev distance to camera)`, doubling `Δs0` and `t0` per LOD, so probes keep a constant on-screen size. LODs never mix; each starts at 0.9 of its boundary and blends linearly across the overlap.
- **Ray splitting:** rays start at visible surface points, not at probes. A ray that hits at distance `t` in cascade `m`'s interval deposits "transparent" (`J = 0, β = 1`) into every lower cascade and "opaque" (`J = L_hit, β = 0`) into cascade `m`, at the nearest probe and direction of each, with a count. Higher cascades get nothing. Directions are flipped into the surface's hemisphere, so probe directions facing into walls stay empty and are never read. This avoids probes recessed in walls and the over-darkening they cause.
- **Ray distribution:** uniform random directions fill high cascades badly, so rays use the R2 sequence through the equal-area map, with contiguous R2 ranges per parent from a hierarchical prefix sum, jittered per frame.
- **Merge:** per cone, `C_n = J + β·mean(C_{n+1} over children)`. Parent weights are `0.25^n·0.75^(3−n)` because a parent's center sits a quarter cell from each child's. Morton-ordered directions let a warp average children with shuffles.
- **Shading:** each cascade 0 probe becomes a 6×6 octahedral irradiance tile with a border; each pixel takes 8 filtered samples in its normal direction.
- **Multi-bounce:** last frame's hit points spawn probes two LODs coarser; every hit reads that secondary cache, which feeds itself.
- **Temporal:** blend in world space with no reprojection (chandra decays sums by 0.97; wroughtinator keeps an exact running average for static scenes and a 0.92 blend for moving lights).
- **Numbers:** 8.6 ms (Sponza) and 11.5 ms (San Miguel) single-frame on an RTX 3080 Laptop with fp32 storage, unoptimized; only tracing depends on the scene.
- **Artifacts left:** detail below cascade 0 spacing (a screen-space cascade −1 fixes it for 1.4 ms), interpolation leaks, overblurred hard shadows.
- **Implementation details** ([sparse 3D notes](../sources/2026_sparse_and_3d_rc.md)): linear probing took over 20 steps with Morton keys while `(hash + pcg(attempt)) % count` capped it at 6 to 8; a level-plus-Z-order key is collision-free within its window and makes the parent a bit shift; ray origins at the average position of a probe's pixels keep probes on the surface; a one-bit hit/miss test per ray stops trilinear leaks through thin walls. Without hardware RT, ray splitting did not pay off, and plain sparse RC with a software tracer or voxel cone tracing was simpler. Variance-guided retracing of high-variance cascade 0 directions sharpened shadows for about 1 ms.

wroughtinator's native build runs the whole pipeline as one GLSL compute file with a software BVH, integer atomics (fixed-point scale 4096, values clamped to 16), and 5-word hash slots with retry queues. It is the closest existing match to what Godot's `RenderingDevice` can run without hardware ray queries. Its browser build adds a surface class (dominant normal axis) to the probe key so the two sides of a thin wall never share probes, and an analytic near-emitter term that removes fireflies from small lights.

### Surfel probes (Surfel RC, Love and Deepspace)

Probes live on surfaces as surfels, which makes probe count follow visible surface area (the "surface" row of the memory table in [core_theory.md](core_theory.md)). Probes on UV charts are the other surface-bound option: a Cornell-box demo runs 2D cascades on each chart, and on-surface caches outside RC show the cost of island seams and foliage ([repository survey](../sources/2026_rc_repository_survey.md), [on-surface caches](../sources/2024_tatzgern_on_surface_radiance_caches.md)).

- **Surfel RC** ([Coppen](../sources/2025_coppen_surfel_radiance_cascades.md)): six cascades of screen-spawned surfels, 262,144 at cascade 0 and ÷4 per cascade, 16 directions ×4 per cascade, intervals `[4^N, 4^(N+1)]·base`. Surfels spawn from a rotating quarter of pixels where coverage is low, live in a hash grid with distance-based cell levels, and are recycled by a usage marker and an overlap heuristic. The merge picks up to four upper surfels by distance and normal similarity. Each cascade's radiance is a 2048² RGBA16F atlas, 423 MB in all. Gathering cost 5.35 ms and merging 2 ms in one profile. Surfels do not follow moving objects, hash collisions return distant surfels, and interpolation artifacts are visible.
- **Love and Deepspace** ([GDC 2026](../sources/2026_rc_conference_talks.md)), the only shipped 3D RC found: surfels are generated per mesh asset from its lightmap UVs (about 10 cm, four LODs) and stored in local space; a multi-level hash grid (51,481 buckets) holds them; rays march the hash grid and test ray-disk intersections, which beat software triangle BVHs on phones. Probes are a three-level camera clipmap of 32×32×16 probes, about 1 m apart, with cascades per probe (probes ÷8, directions ×4), direction-first with pre-averaging. Irradiance is stored as luma SH plus two chroma scalars. Ray tracing is spread over frames with a cached hit distance per ray. Leaks through gaps between surfels are handled with transparent outer rings on each surfel; indoor and outdoor probes carry tags so interpolation never mixes them. The gather runs at about 70% resolution. Total about 2 ms on an iPhone 12, 28 frames to converge per bounce (5 in a fast mode).

## Visibility and leaks in world space

Probe grids leak through walls thinner than the probe spacing. The fixes found:

- Hemisphere-flipped rays from surfaces so wall-facing directions are never read (Split RC).
- Per-upper-probe visibility rays in the merge (erhe), a 3D binary bilinear fix.
- A free visibility test from the upper probe's own hit distance: count an upper sample only if it missed or the lower probe lies inside its cone at that distance (the surface-chart demo).
- Sampling each of the 8 upper probes along the direction from it to the lower interval's end instead of the shared direction (SultanAladin), the 3D form of the parallax correction in Reservoir Cascades below.
- Surface class in the probe key (wroughtinator browser build).
- Indoor/outdoor probe tags (Love and Deepspace).
- DDGI's Chebyshev test on stored distance moments, backface-fraction probe deactivation, and probe relocation ([DDGI](../sources/2019_majercik_ddgi.md); erhe keeps the distance maps for this).
- Enshrouded pushes probes out of walls along the SDF and kills probes whose summed ray distance is under 1 mm ([talks](../sources/2026_rc_conference_talks.md)).
- Offsets alone: daGI2's world grid has no visibility term. It samples half a probe along the normal and up to one probe toward the camera, and rays that end in a coarser clip read it pulled back √3 coarser probes ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).
- Trace from where the probe is used, not from a fixed point: kajiya's sparse irradiance cache picks each cell's ray origin at random among the points that queried it that frame, so a cell queried from inside a building lights the inside. Each cell also keeps the lowest bounce index that reached it, and only queries of equal or lower rank move its origin, so the cache's own outside rays cannot drag it back out ([kajiya](../sources/2022_stachowiak_kajiya_gi.md)). Sparse hashed RC probes placed from visible surfaces get the first half of this for free; the rank rule applies to any probe the cascades spawn from their own hits.

Reservoir Cascades ([You 2026](../sources/2026_you_reservoir_cascades.md)), so far tested in 2D only, attacks the merge itself: it treats the four parents as resampling candidates (GRIS) with the bilinear weights in the selection, not in the target, and validates the chosen parent with a shadow ray with probability ρ. Leaks drop to 11% of plain RC at +17 to 26% rays, sub-bin emitters are recovered, and lights adapt in 3 frames. It also proves that with ×4 angular branching the parallax between parents grows as `2^n` bins, so lookups must reproject each parent's bin through the child's far point (`z = p + √(t_{n+1}·t_{n+2})·ω`). Per-frame interval jitter breaks temporal reuse; jitter in blocks of frames instead. Memory is about 3× plain RC.

## Temporal accumulation

World-space probes need no reprojection: blend new intervals into the stored ones. Patterns found:

- Exponential blend with a hysteresis around 0.9 to 0.97, replaced on the first traces after a reset (`h = min(hysteresis, k/(k+1))`, erhe).
- Sample-count averaging capped at a maximum count, with a faster blend when lights move (wroughtinator).
- `blend = max(1/(history + 1), 0.033)` with a per-voxel history counter, and neighbor fill for new probes (tauray).
- Round-robin tracing of a fixed texel budget per frame (erhe) or across frames (Love and Deepspace).
- An adaptive blend from luminance change: 0.08 under 10%, 0.3 under 50%, 1.0 above (an O3DE attempt).
- Cached hits: Godot's HDDAGI stores each probe texel's hit cell and reuses it until a version counter on the hit region changes or the cascade moves along the hit axis, so hits in unchanged regions are not traced again. reduz's earlier plan states the scroll rule: a hit stays valid if it remains in the same cascade, or if the ray leaves an upper cascade through the same face ([SDFGI plan](../sources/2023_linietsky_godot_sdfgi_plan.md)).
- Light on demand: ray hits set bits in a coarse dirty volume, and only marked regions are relit the next frame, so lighting work follows what probes actually see (the same plan).
- A fixed number of probes retraced per frame, chosen from a GPU priority queue, with newly revealed probes traced first (Lumen's world cache).
- Probability with feedback: daGI2's world radiance clipmap updates one clip per frame and gives each probe a chance to be retraced from its age, cut to 1/16 outside the frustum or behind the HZB and to 1/16 again with no surface within 3 probes. A multiplier fed back from last frame's count holds the total at 6.25% of the clip. Probes entering a clip are traced at once and averaged over up to 27 samples; invalidated probes blend at 0.3 to 1 for a while ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).
