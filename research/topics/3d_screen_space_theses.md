# Screen-space RC theses

Six academic works build or measure screen-probe 3D RC: four master's theses from 2025 (Gavras, Kaméus, Abou Dan and Jensen, Dell'Ova), Kung's thesis with a game studio, and Gerassimov's 2026 conference paper. Together they hold nearly all published measurements of screen-space RC. The design questions they answer are discussed in [3D screen space](3d_screen_space.md), which also holds the cross-project parameter table.

| Work | Family | Tracing | Hardware | Main result |
|---|---|---|---|---|
| Gavras (Chalmers) | SPWI | Metal ray tracing | M1 MacBook Air | 33 to 156 ms at 1080p; bilinear 3D merge; proposes min/max probes |
| Kaméus (KTH) | SPWI | DXR ray queries | RTX 2070 | min/max probes: 2 to 17% more time, small metric gains, fewer edge leaks |
| Abou Dan and Jensen (Chalmers) | SSRC | visibility-bitmask GI | "modern" | 2 to 26 ms in a game, no temporal reuse |
| Dell'Ova (BTH) | SPWI | DXR | RTX 3080 | 96 configurations: probe spacing dominates; gather is 87 to 96% |
| Kung (Linköping, Beartwigs) | SSRC | fixed-thickness depth march | RTX 3060 | 4.9 to 295 ms; artifact catalogue against VCT |
| Gerassimov (DiGRA 2026) | unnamed | unnamed | RTX 4060 Laptop | RC about as fast as realtime lightmaps, 2× faster than SSGI |

## Contents

- [Gavras (2025): SPWI on Metal](#gavras-2025-spwi-on-metal)
- [Kaméus (2025): min/max probe placement](#kaméus-2025-minmax-probe-placement)
- [Abou Dan and Jensen (2025): visibility-bitmask screen probes](#abou-dan-and-jensen-2025-visibility-bitmask-screen-probes)
- [Dell'Ova (2025): performance scaling with DXR](#dellova-2025-performance-scaling-with-dxr)
- [Kung (2025): RC against voxel cone tracing](#kung-2025-rc-against-voxel-cone-tracing)
- [Gerassimov (2026): RC against Unity's GI](#gerassimov-2026-rc-against-unitys-gi)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)
- [Open questions](#open-questions)

## Gavras (2025): SPWI on Metal

| | |
|---|---|
| Title | Exploration and Optimization of Radiance Cascades for Real-Time Applications |
| Author | Kyriakos Gavras; supervisor Ulf Assarsson, examiner Erik Sintorn |
| Institution | Chalmers University of Technology, master's thesis, 2025 (67 pages) |
| Link | https://odr.chalmers.se/items/3ee9fb4e-1880-46c2-802a-a660e38dc9ee, PDF https://odr.chalmers.se/bitstreams/256da4eb-990c-4e51-aae1-c7878609e314/download, handle https://hdl.handle.net/20.500.12380/310889 |

The thesis explains 2D screen-space RC, then builds a 3D variant it calls Screen-Space Probes with World-Space Intervals (SPWI) that traces rays in world space for one bounce of diffuse light. Its figures are images, so these notes rest on captions and text; in the notes, "(derived)" marks arithmetic from the thesis's own formulas and "(compiled)" a summary of several parts that is not a thesis section ([Gavras](../sources/2025_gavras_screen_probes_world_intervals_thesis.md)).

**Framing.** Real-time path tracing relies on denoisers and temporal accumulation, which can ghost in dynamic scenes; RC is presented, citing Sannikov's paper, as a single-frame method that responds to changes in lighting, geometry and viewpoint without temporal accumulation, for video games and interactive visualization. The previous-work chapter groups real-time GI into path tracing (Monte Carlo, ReSTIR, ReSTIR GI: needs denoisers and accumulation, can ghost or be unstable in dynamic scenes), screen space (SSAO, SSGI: fast, no off-screen light) and probes (irradiance volumes, LPV, DDGI: covers 3D space, high memory and complex placement). It calls SPWI single-shot, says it reaches off-screen light through world rays, and concedes that the existing approaches are generally more temporally stable because SPWI repositions screen-space probes.

**2D observations.** The angular observation is `Δω < w/Δ` with `Δ` the distance to the farthest object and `w` the size of the smallest, after Coppen's article (Figure 3.1: a probe casting 16 rays misses a far light when its angular resolution is too low); the spatial observation is its inverse (a point near a light needs a dense grid, a far point a coarse grid with more directions; Figures 3.2 and 3.3, from Sannikov's paper); together they give, as Equation 3.1, the penumbra condition `Δp ≲ D`, `Δω ≲ 1/D`, where `A ≲ B` means `A` is below some function linear in `B` ([core theory](core_theory.md)).

**2D implementation.** Everything in 2D happens on one flat plane, interval casting included. Following jason.today, the scene is a user-drawn texture (Figure 3.4) turned into a distance field by jump flooding ([scene representation and tracing](scene_representation_and_tracing.md)):

- Algorithm 1, the host procedure `JFAPass`, runs `ceil(log2(max(width, height)))` passes with steps `2^(passes − stage − 1)`, ping-ponging two textures; Algorithm 2 keeps, per pixel, starting from seed (0, 0) at infinite distance, the nearest non-zero seed by L2 distance among the 3×3 offsets inside the texture at the current step. A later shader turns seed coordinates into Euclidean distances, the distance texture (Figure 3.6) that ray marching steps through. The thesis states JFA's time as `O(log n)`; for 512² the steps are 256 down to 1 in 9 passes (derived).
- Cascade count `ceil(log(diagonal)/log(baseRayCount)) + 1` from the screen diagonal; branching factor 4; probe spacing `√(baseRayCount^c)` px (`2^c` for base 4) and `baseRayCount^(c+1)` rays per probe spread over the full circle. Cascades run highest first, so far radiance is carried down, with two ping-pong targets.
- Algorithm 3 (RCPass) ping-pongs two render targets at the screen resolution (`renderA` and `renderB`, from `pingPong = 0` and `lastMerge = null`) and loops from the top cascade down with `rayCount = baseRayCount^(cascade + 1)`, setting `lastMerge` to the target above cascade 0 and writing cascade 0 to the final output; each pass runs `RayMarch` into the target with the drawing texture, distance texture, `lastMerge`, cascade and `rayCount`. Algorithm 4 (RayMarch with cascade sampling) first computes the cascade's grid size, spacing and interval, which the thesis does not define for 2D, then marches each ray from `probe + intervalStart·direction` by the SDF distance up to `maxSteps`, stopping with no hit once the point leaves the bounds or passes the interval end, counts `d ≤ minStep` as a hit and takes the hit colour, takes the upper cascade's value on a miss below the top, and outputs `sum/rayCount`. `maxSteps` and `minStep` are not given, nor how distance travelled is measured, and the upper-cascade step sits inside the bounds check in the pseudocode.
- The merge maps each probe into the upper level and samples it with linear interpolation, merging 4 rays from each of the 4 nearest probes; the angle mapping is not given.
- At 512² with 6 cascades (Figure 3.7) the grids run from 512² probes of 4 rays at 1 px to 16² probes of 4096 rays at 32 px; each cascade has 4× the probes and ¼ the rays of the one above, and traces 1,048,576 rays (derived).

**Comparison of 3D approaches** (Table 4.1): screen-space marching is extremely fast and memory efficient but cannot capture off-screen light, which suits top-down games such as Path of Exile 2; a 3D probe grid captures off-screen light, is view independent and very stable under camera motion, but uses much memory and is very slow; SPWI captures off-screen light with a memory-efficient hierarchy but is very slow against screen-space marching. SPWI is called a middle ground: one-bounce light close to full 3D quality with memory near screen-space methods.

**Probe placement.** Probes sit at their screen positions, with world positions from the depth buffer (Figures 4.1 and 4.2 show cascade 0 probes). A linear depth buffer stores camera distances, needed for thresholding depth differences. Algorithm 5 forms `clip = (ndc.x, ndc.y, −1, 1)`, takes `view = inverse(projection)·clip / w`, scales by `linearDepth/|view.z|` and by 0.98, and transforms back to world space; the 0.98 puts the point at 98% of its depth to prevent surface acne.

**Directions.** Octahedral mapping (Cigolle et al.), called area-preserving and cheap; the encode and decode bodies are not given. Cascades 0, 1 and 2 have 16, 64 and 256 rays. The Figure 4.4 caption says the map covers the hemisphere, while the text describes the sphere.

**Intervals and hierarchy.** Algorithm 6 sets `start = 0` at level 0, else `0.016·4^(level − 1)`, and `end = 0.016·4^level`, with no units stated and an unused `intervalLength` argument: 0 to 0.016, 0.064, 0.256, 1.024, 4.096 and 16.384. The factor 4 matches the branching factor, and interval lengths must be adjusted to the scale of the world. Each level multiplies rays per probe by 4 and halves the grid per axis, which the thesis says keeps total cost roughly constant; Figures 4.5 and 4.6 show the probe-ray layout of the first three cascades from the top and from an angle. Table 4.2, for 512² with 16 base rays and 4 px spacing:

| Level | Probe grid | Rays per probe | Spacing (px) | Rays per axis (derived) | Probes × rays (derived) |
|---|---|---|---|---|---|
| 0 | 128 × 128 | 16 | 4 | 4 | 262,144 |
| 1 | 64 × 64 | 64 | 8 | 8 | 262,144 |
| 2 | 32 × 32 | 256 | 16 | 16 | 262,144 |
| 3 | 16 × 16 | 1,024 | 32 | 32 | 262,144 |
| 4 | 8 × 8 | 4,096 | 64 | 64 | 262,144 |
| 5 | 4 × 4 | 16,384 | 128 | 128 | 262,144 |

Each level is one ray per texel of a 512² texture, and the tile size per probe equals the spacing (derived). Six levels gave the best balance on the test scenes, chosen experimentally. When the camera is very close to a non-emissive surface the probes sit on it and the higher cascades' intervals extend behind the camera.

**Merging.** Plain bilinear interpolation over the 4 nearest upper probes creates artifacts because they can sit at different depths (Figure 4.7); outliers should weigh less.

- Algorithm 7, bilateral (after pixelmager's gist, cited as Gjoel 2021): find the 4 upper probes and their linear depths, convert the direction to upper octahedral coordinates, take bilinear weights, and where `(max − min)/mean > 0.1` of the four depths multiply each weight by `1/(|depth_i − currentDepth| + 0.0001)`; normalize, then sample each probe's octahedral map bilinearly at the direction. Depth awareness is not needed between directions, because the probe weights already handle depth.
- Algorithm 8, bilinear 3D (Sannikov's 4XXSWS, released after the RC paper and incorporated per the abstract): reconstruct the 4 upper probes' world positions, start from a screen-space ratio (`CalculateScreenSpaceRatio`, not defined), run `GetBilinear3DRatio` for 2 iterations (alternately project the destination onto the line between `mix(src0, src2, ratio.y)` and `mix(src1, src3, ratio.y)` for `ratio.x`, then between `mix(src0, src1, ratio.x)` and `mix(src2, src3, ratio.x)` for `ratio.y`), and blend with the resulting weights. The corner order src0 to src3 is implied by the pairings (src0–src1, src2–src3, src0–src2, src1–src3), not named. Bilateral filtering shows striations, easier to see from steep angles. No quantitative comparison of the merge methods appears: Figure 4.9 compares bilateral filtering and bilinear 3D by eye, and plain bilinear's artifacts are described in text only.
- Algorithm 9 dispatches levels top-down, ping-ponging two targets, with `tileSize = probeSpacing·2^level`, `raysPerDim = 2^(level + 2)` and `totalThreads = gridX·gridY·raysPerDim²`, the same for every level at branching factor 4 (262,144 in Table 4.2). As written it sets `lastMergedTexture` to null for level `max − 1`, so the top cascade's result would not reach it.
- Algorithm 10, one thread per (probe, ray): compute the probe's UV from its index and the grid size, reconstruct the probe, compute the ray UV from the ray index and `raysPerDim` and decode it with `OctDecode`, trace within `[start, end]`, set occlusion 0 on a hit and 1 otherwise, take `GetSurfaceRadiance` on a hit or, at the top level with sky and sun enabled, `CalculateSkyAndSunRadiance(direction)`, then below the top merge with the upper cascade: on a miss take the upper value, on a hit `rgb += upper.rgb·occlusion` (zero) and `a *= upper.a`. Sky radiance enters only at the top and propagates down, and once every cascade has run, cascade 0 holds the merged radiance of all levels (Figure 4.10 shows the maps from cascade 5 down to 0). The alpha channel's meaning, the output position formula (from the probe UV, ray UV and `tileSize`) and which merge function is called are not stated.

**Final gather.** Only cascade 0 is needed. Algorithm 11 (`FinalGatherFragment`, per pixel) reads albedo, normal and depth from the G-buffer, returns the sky for empty albedo, gets the grid size and the 4 nearest cascade 0 probes' coordinates, UVs and depths, flags an edge where the relative spread exceeds 0.05 (not 0.1 as in the merge) and adjusts the bilinear weights by an unspecified `ApplyDepthBasedWeighting`, then per probe sums `radiance·max(0, n·dir)` over all 16 directions and divides by the summed cosines (`max(totalWeight, 0.0001)`), blends the four probes and multiplies by albedo. Bilateral filtering suffices here because striations do not show over cascade 0's short intervals. The thesis calls this Lambert's cosine law integration and mentions no `1/π`; dividing by the summed cosines already returns irradiance over π ([3D screen space](3d_screen_space.md#final-gather)).

**Direction-first layout.** Each texture block is one ray direction, its pixels holding that direction for every probe (Figure 4.12: cascades 0 and 1 at 512 × 512). Moving from probe-first to direction-first made results more cohesive, eased debugging and allowed hardware interpolation between similar rays during merging; no timing, quality figure or index formula is given.

Rays are stored in textures rather than storage buffers, for simplicity, so each cascade's octahedral texture matches the drawable resolution.

**Pre-averaging** (Alex and Xor's proposal): four probe rays averaged into one during tracing keep texture sizes, cut merge operations by 75% and draw radiance from a finer grid; Figure 5.1 draws probe #0, the one written, with orange neighbours traced only during ray tracing and averaged into it for matching directions. Algorithm 12 maps each thread ID to a quad index, a local probe index (0 to 3) and a ray index, so 2×2 neighbouring probes sit on adjacent threads of one SIMD group (32 or 64 threads); it computes the probe position from the quad and local index and then its screen UV, the ray UV from the ray index and then the direction, traces, shuffles radiance and occlusion from lanes `baseLane = laneID − localIndex` to `baseLane + 3` with Metal SIMD shuffles (no shared memory or synchronization) and averages them ×0.25; only local probe 0 merges with the upper cascade and writes, at a position from the quad and ray index. The test build predated depth-aware upscaling, showed halos around emitters, and used twice as many probes per axis, Sannikov's grid and 4× the final one. Tracing 4× the rays was not viable on the test system, and the SIMD gain was negligible because ray tracing dominates. Halving cascade 0 spacing from 4 to 2 px would make each texture 4× larger; cascade textures match the drawable size.

**Results.** All scenes use 6 cascades, one ray per pixel each, called 6 samples per pixel. Performance is said not to depend on light count because rays per cascade are fixed, and to be bound by acceleration-structure traversal; memory scales with resolution and cascade count; no scaling measurement is shown. Table 6.1, M1 MacBook Air with 8 GB unified memory, 1920×1080, memory including acceleration structures, models, buffers and textures:

| Scene | Time (ms) | Memory (MiB) |
|---|---|---|
| One emissive cube (Fig. 6.3) | 32.77 | 147.00 |
| Four emissive cubes of different colours and two plain cubes (Fig. 6.2) | 34.42 | 146.88 |
| Stanford bunny with a matte cube (Fig. 6.5) | 37.07 | 184.66 |
| Bunny with two emissive cuboids, daylight (Fig. 6.6) | 39.87 | 184.90 |
| Sponza lit by sky (Fig. 6.1) | 143.74 | 405.00 |
| Sponza with three emissive hornbugs, pink, blue and yellow (Fig. 6.4) | 155.90 | 408.50 |

Fig. 6.7 shows the bunny cuboids without daylight. The Sponza scenes take 4.4 to 4.5× as long as the cube scenes (derived), and the only pair that differs in light count (cube and cubes) also differs in geometry, so the light-count claim is untested. For comparison the thesis cites Sannikov's analytic-SDF SPWI at 30 to 50 ms on an RTX 3060. There is no per-pass breakdown and no upscaler timing.

**Min/max probes (future work).** Presented as a better merge with the upper cascade, giving bilateral filtering and bilinear 3D better depth bounds. Algorithm 13 writes the depth to both channels, then builds a min/max mip chain (red the minimum, green the maximum of each 2×2 block, so in Figure 7.1 similar values look yellow and large gaps green); the proposal places one probe on each plane, picks the mip matching each cascade's grid, traces and merges both sets, and blends trilinearly between the current probe and the upper min and max probes. It doubles tracing, so odd rays go to the minimum plane and even rays to the maximum. Nothing was implemented or measured.

**Conclusions.** RC gives effective single-shot diffuse GI over several distance scales, with soft shadows and indirect light; cost depends on geometry more than light count; intervals must fit the world scale. Limits: screen-space placement flickers under camera motion, which depth-aware interpolation reduces but does not remove (the thesis expects depth-aware techniques to give better quality per unit of performance, with no numbers), and complex scenes need too much compute for mainstream hardware. Future work: probe placement for temporal stability, with min/max probes the most promising.

**Inconsistencies in the thesis.** Two 512² configurations appear (6 cascades with a 16² top grid and 4096 rays in Section 3.5 and Figure 3.7, a 4² top grid and 16,384 rays in Table 4.2); "base ray count" means the log base and ray base (4) in Section 3.5 and the cascade 0 count (16) in Section 4.2; Algorithm 9's null merge texture; Algorithm 6's unused argument and missing units; mismatched argument lists (Algorithm 10 calls `MergeWithUpperCascade` with five arguments, the upper texture, probe UV, direction, probe depth and world position, where Algorithms 7 and 8 take three, Algorithm 8's being probe UV, direction and world position, so the call carries both the probe depth bilateral filtering uses and the world position bilinear 3D uses; Algorithm 12 calls `ReconstructWorldPosition` with one where Algorithm 5 takes two, and the merge with two); edge thresholds of 0.1 and 0.05; the hemisphere caption of Figure 4.4; the 2D spacing formula; two spellings of SPWI ("Screen-Space Probes with World-Space Intervals" and "Screen-space Probes World Intervals"); the bounds-check placement in Algorithm 4; and the untested light-count claim. Unstated: interval units, the 2D interval values (absent from all of Section 3), 2D step constants, the grid (`CalculateProbeGrid`), UV, output and thread mappings, the octahedral formulas, how the linear depth and G-buffer are produced, the alpha channel, the 2D angle mapping, the `1/π`, the cascade interval in Algorithm 12, the ray-tracing API (beyond Metal, named in Section 5.1.2 and the Algorithm 12 heading, and a `TraceRay` call in the pseudocode) and scene representation, and which merge Algorithm 10 calls. Test assets: Sponza (Dabrovic 2002, casual-effects.com), the Stanford bunny (Turk and Levoy 1994) and McGuire's hornbug models.

**Read against the other measurements (derived).** At 12.4 M rays per frame, Gavras's scenes run at 0.31 to 0.38 G rays/s for cubes and bunnies and 0.08 to 0.09 G rays/s for Sponza. The M1 has no ray-tracing hardware, so these are software-traversal figures, two orders of magnitude below Dell'Ova's hardware DXR rate on the same Sponza (inference from Apple's hardware generations; [3D screen space](3d_screen_space.md#ray-throughput-across-the-measured-spwi-codes-derived)).

## Kaméus (2025): min/max probe placement

| | |
|---|---|
| Title | Probe placement strategies for Radiance Cascades with screen-space probes and world-space intervals |
| Author | David Kaméus; supervisor Björn Thuresson, examiner Tino Weinkauf |
| Institution | KTH, master's thesis, October 2025 (TRITA-EECS-EX-2025:854) |
| Link | https://urn.kb.se/resolve?urn=urn:nbn:se:kth:diva-375827 |

The thesis measures what min/max probe placement buys over a single bilaterally merged probe per tile in SPWI, diffuse first bounce only, with no temporal reuse ([Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md)).

**Setup.**

- AMD Capsaicin 1.1 on DirectX 12, HLSL compute with DXR ray queries, one thread per pixel; RTX 2070 (8 GB), 2048×1024, TAA off, timings averaged over 256 frames.
- Scenes: a Cornell box with a ceiling light, and Sponza lit only by its sky. References from a Monte Carlo path tracer; error measured with LIP (NVIDIA's FLIP tool) and SSIM.
- Cascades run top-down. Cascade `i` uses tiles of `2^(i+1)` texels, intervals `[4^i·scale, 4^(i+1)·scale]` and 4 pre-averaged rays per texel; the top cascade reaches infinity and reads the environment on a miss. The merge is `(r_n + t_n·r_f, t_n·t_f)` with binary transmittance. A `sphere_map` function (Appendix A.1) switches between cos-θ, octahedral and equal-area octahedral maps, and Fig. 3.2 shows the equal-area one as least skewed; which produced the results is not said, equal-area being likely.
- `scale` is chosen with the cascade count so the merged intervals cover the scene, with no value given and no scene units or sizes; camera planes are 0.1 and 10000, and two depths count as similar within 2 linearized units. Each cascade overlaps slightly into the next one's range to limit leaks. The Cornell capture is described as 5 cascades with C5 computed first, so the index range is ambiguous.
- Cascade 0 probes take 2×2 texels, and the probe textures are 4096×2048, 2048×1024 and 1024×512 for one probe per pixel, per 2×2 and per 4×4 px.
- Probes come from a min/max depth pyramid whose mip matches each cascade's tile, pushed off the surface by a depth bias: too much leaks, too little self-intersects. The final gather averages each 2×2 tile of cascade 0.

**Strategies.**

- **Bilateral:** one probe per tile at its minimum depth; the merge weights upper probes by depth difference, for cascades 0 to 2 only. When all weights are near zero, normalization produces bright or dark splotches across depth edges, and discarded probes give jagged edges.
- **Min+Max:** two probes per tile, at the world positions of its minimum-depth and maximum-depth pixels, found through a hierarchical buffer; each layer is merged bilinearly and the two are blended linearly by depth. Twice the rays and memory.

**Results.**

| | 1 probe per pixel | 1 per 2×2 px | 1 per 4×4 px |
|---|---|---|---|
| Cornell, Bilateral | 68.03 ms | 21.21 ms | 9.72 ms |
| Cornell, Min+Max | 79.76 ms | 23.8 ms | 9.96 ms |
| Sponza, Bilateral | 137.49 ms | 37.16 ms | 11.75 ms |
| Sponza, Min+Max | 158.85 ms | 43.02 ms | 13.34 ms |
| Memory, Bilateral | 128 MB | 32 MB | 8 MB |
| Memory, Min+Max | 256 MB | 64 MB | 16 MB |

Image metrics (Table 4.5, read from the rendered page because the text layer garbles it), one probe per pixel / per 2×2 / per 4×4:

| Metric | Bilateral | Min+Max |
|---|---|---|
| Cornell LIP-HDR | 0.306 / 0.313 / 0.335 | 0.298 / 0.304 / 0.324 |
| Cornell LIP-LDR | 0.155 / 0.157 / 0.171 | 0.15 / 0.15 / 0.161 |
| Cornell SSIM, tone-mapped | 0.924 / 0.918 / 0.898 | 0.932 / 0.93 / 0.915 |
| Cornell SSIM, HDR | 0.028 / 0.031 / 0.039 | 0.027 / 0.029 / 0.034 |
| Sponza LIP-HDR | 0.661 / 0.670 / 0.687 | 0.663 / 0.676 / 0.701 |
| Sponza LIP-LDR | 0.489 / 0.494 / 0.499 | 0.486 / 0.487 / 0.485 |
| Sponza SSIM, tone-mapped | 0.535 / 0.526 / 0.516 | 0.536 / 0.529 / 0.519 |
| Sponza SSIM, HDR | 0.115 / 0.117 / 0.119 | 0.114 / 0.114 / 0.113 |

- Memory assumes four 16-bit channels per texel without compression. Min+Max took 117 / 112 / 102% of Bilateral's time in the Cornell box and 116 / 116 / 114% in Sponza (Table 4.1).
- Min+Max cost 2 to 17% more time, improved LIP-LDR error by 0.5 to 5.8% and tone-mapped SSIM by 0.2 to 1.9%, more in the Cornell box than in Sponza, and was slightly worse on Sponza's HDR error.
- The visible difference is larger than the metrics: Min+Max removes the splotchy edge leaks and the worst flicker under motion, leaving softer seams between cascades.
- Nsight showed the time going to waiting on ray queries, about 10 ms per cascade for Bilateral and 15 ms for Min+Max at full density. Only the one-probe-per-4×4 runs fit a 16 ms budget on the RTX 2070.

**Problems in both:** leaks through thin walls and corners where intervals do not join and walls align with the grid; halos where depths differ greatly, and at coarse density from the 2×2 final averaging; ringing near cascade boundaries; darker bottom and right screen edges at high cascade counts, from upper probes that would sit off screen; flicker as probes are recomputed at changing depths. The author names reprojection, temporal reuse and a cascade −1 gather as the next steps.

**Abstract against tables.** The abstract and conclusion call Min+Max better in every measure except time. The tables show Bilateral ahead on Sponza's LIP-HDR at every density (0.661, 0.670, 0.687 against 0.663, 0.676, 0.701; lower is better). The HDR SSIM rows (0.03 to 0.12) sit far below the tone-mapped ones (0.52 to 0.93) and the thesis does not say which direction is better there: read as similarities, Bilateral leads in both scenes, read as dissimilarities Min+Max does. The tables are the evidence, so Min+Max wins on LDR and tone-mapped metrics and on visible edge artifacts, and loses Sponza's HDR error; the HDR SSIM verdict is open.

**Read against the model (derived).** The memory column is exactly two ping-pong RGBA16F textures: 4096×2048×8 B×2 = 128 MiB, 32 MiB and 8 MiB, doubled for Min+Max. At one probe per pixel each cascade traces 2048×1024 probes × 16 rays = 33.6 M rays, so 10 ms per cascade is about 3.4 G rays/s on an RTX 2070 with ray queries; Min+Max's 2× rays in 1.5× the time is about 4.5 G rays/s.

## Abou Dan and Jensen (2025): visibility-bitmask screen probes

| | |
|---|---|
| Title | Screen Space Global Illumination Using Radiance Cascades in 3D Video Games |
| Authors | Ghaith Abou Dan, Mati Jensen; supervisor Erik Sintorn, examiner Ulf Assarsson |
| Institution | Chalmers University of Technology, master's thesis, 2025 |
| Link | https://odr.chalmers.se/items/9e42007a-bb60-440f-ba28-04410822758f |

The repository record holds only the abstract and a licence file; the full text is not public, so everything here comes from the abstract ([Abou Dan and Jensen](../sources/2025_abou_dan_jensen_rc_vbgi_thesis.md)).

- Built for the game As We Descend (Box Dragon): a camera with limited movement, all relevant geometry on screen, many short-lived emissive effects, and a budget of a few milliseconds per frame.
- Screen-space probes in a radiance cascade hierarchy, traced with visibility-bitmask GI ([related screen-space GI](related_screen_space_gi.md)) instead of plain depth marching; one bounce of screen-space GI plus emissive light, with a radius covering the whole screen.
- No temporal accumulation or reuse, no separate denoiser and no high-frequency noise.

| Setting | Time | Memory |
|---|---|---|
| Lowest | 2 ms | from 0.03 GiB |
| Medium | 6 ms | |
| High | 26 ms | up to 3.9 GiB |

Hardware is described only as "modern"; the GPU and resolution are not given. Problems reported: anything off screen neither lights nor occludes; the screen-space tracing over-brightens the background; upscaling the radiance data causes artifacts, worst at low settings; and flicker during small movements, worst at low settings, makes every other artifact flicker too.

Gerassimov cites this thesis for SSGI's reliance on previous frames and, with Kung, for RC's noise and blur up close.

## Dell'Ova (2025): performance scaling with DXR

| | |
|---|---|
| Title | Analyzing the Performance Scaling of Radiance Cascades: Exploring a Novel Solution for Dynamic Diffuse Real-Time Global Illumination |
| Author | Jonathan Dell'Ova |
| Institution | Blekinge Institute of Technology, MSc in Engineering (Game and Software Engineering), 2025 (cover "10 2025"), 84 pages |
| Link | https://bth.diva-portal.org/smash/get/diva2:2007296/FULLTEXT01 |
| Code | https://github.com/ClaikoCode/DX12RadianceCascades ([implementations](3d_screen_space_implementations.md#claikocodedx12radiancecascades)) |

A from-scratch 3D RC in DirectX 12 with hardware ray tracing on MiniEngine, measured for frame time and VRAM over 48 parameter sets at each of 1920×1080 and 2560×1440 in Sponza. The PDF text layer garbles some math; equations 4.4 and 4.5 are rebuilt from the text and Table 5.4 ([Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md)).

**Question and scope.** How do frame time (GPU time for specific work, excluding CPU) and VRAM (GPU memory allocated for a resource or group) of 3D RC with hardware RT scale with resolution, probe spacing, cascade count and initial rays per probe? Diffuse only (specular, possible per Sannikov's preprint, is not evaluated); image quality is checked only for clear bugs; one scene. Three academic RC texts were found (Google Scholar, DiVA, Scopus); only Kung covers real-time 3D RC, varying one parameter without hardware RT.

**Background as stated.** RC is a deterministic, non-stochastic probe GI technique first shown by Sannikov and the main GI of Path of Exile 2, resting on the penumbra condition (Figure 2.3: distant objects need angular resolution, near ones spatial). Angular resolution is the density of directions, spatial resolution the density of probes, probe spacing the uniform distance between probes, and a cascade a grid of probes with one spatial resolution, angular resolution and distance interval, each interval starting where the previous ended (Figures 2.4 and 2.5). The probe and ray scaling factors together form the cascade scaling factor; Section 2.4's example "2x/4x" (twice the rays, a quarter of the probes) and Section 4.1's "4x/4x" (4× rays, a quarter of the probes, as the implementation does) use the label for different ray scalings ([core theory](core_theory.md) has the notation). The related work cites Osborne and Sannikov's 2D radiative transfer (orders of magnitude slower than rendering, said to generalize to 3D); HRC at 1.85 ms at 512² and 7.67 ms at 1024² on an RTX 3080 laptop GPU, visually indistinguishable from a 2D reference, with a 3D HRC whose `N⁴` memory limits it to small volumes ([holographic RC](holographic_rc.md)); and Kung's 3D RC for Romestead (below), median about 5, 20 and 30 ms at SPS 4 and 70, 196 and 294 ms at SPS 1 for three scenes, 6 cascades with branching 2 in spatial and polar directions read as 4x/4x, about 3× faster per doubling of sample spacing, no VRAM, published after the thesis plan was set.

**Implementation.** Written from scratch with no 3D reference; Coppen's article ("Max's blog", ref. 15) and the GM Shaders post (by Xor and Alex, ref. 37, which the thesis calls co-authored by Sannikov) were the 2D references, and 2D intuition was essential. Parameters: cascade 0 spacing `ps0` px, rays `rc0`, target `(w, h)`, a maximum cascade count, cascade 0 ray length, probe scaling `sp = 2` per axis and ray scaling `sr = 4`.

- Probe count (eq. 4.1) `pc0 = floor((w, h)/ps0)`; cascade count (eq. 4.2) `N = floor(log_sp(min(pc0x, pc0y)))`, capped by the user's maximum, the short axis limiting it. At 1080p, spacing 4 gives a minimum count of 270 and `N = 8`, spacing 5 gives 216 and `N = 7`, matching the statement that spacing above 4 does not reach cascade 8 at 1080p (derived). Figures 4.1 and 4.2 illustrate counts and levels without sizes; Figure 4.1's example gives 16 probes at spacing 1 and 4 at spacing 2, without saying whether per axis or in total; Figure 4.2, a 1D illustration with probe scaling 2, gives 3 levels at spacing 1 and 2 at spacing 2, with no sizes to check against eq. 4.2.
- Texture size (eq. 4.3) `(w_i, h_i) = pc_i·√rc_i` without pre-averaging, with `rc_i = rc0·sr^i` (4.4) and `pc_i = pc0/sp^i` per axis (4.5); with pre-averaging (4.6, used) `pc_i·√(rc_i/sr)`. The texture is a `√(rc_i/4)`-per-side grid of elements, each `pc_i` pixels, one element per direction holding every probe, each pixel of an element one probe (Figure 4.3, with 4 rays). The thesis gives no exact linear index; one reading is that texel `(X, Y)` of cascade `i` is probe `(X mod pc_ix, Y mod pc_iy)` in direction block `(floor(X/pc_ix), floor(Y/pc_iy))`, which is the code's direction-first index. Every cascade texture then has the same size, `pc0·√rc0/2` per axis, slightly smaller in height at high cascades from floor division (derived; Table 5.4 agrees). Pre-averaging gathers 4 rays per thread and stores their average, so the merge needs 1 sample instead of 4 and VRAM falls 4×; no comparison without it was measured.
- Valid ray counts (eq. 4.7): `√(rc_i/sr)` must be whole for all `i`, so `rc0 = 4k²` (4, 16, 36, 64, 100, …). 16, 36 and 64 were tested; 4 is excluded because four symmetric sphere directions lie in one plane, 100 because most configurations exceed 33 ms.
- The coalesced result has one texel per cascade 0 probe, the merged radiance of that probe.

**Pipeline.** Figure 4.4 shows example outputs of the passes.

| Pass | Dispatch | Reads | Writes | Timed |
|---|---|---|---|---|
| G-buffer and depth | MiniEngine raster | scene | albedo, depth | no |
| RC gather | one thread per cascade texel (4 rays), one dispatch per cascade | depth, camera, scene (ray tracing), emissive textures | cascade `i` (RGB, alpha) | yes |
| RC merge | one thread per texel of cascade `i − 1`, top down | cascade `i` and `i − 1` alpha | cascade `i − 1` in place (from the code) | yes |
| RC coalesce | one thread per cascade 0 probe | all cascade 0 directions | coalesce buffer | yes |
| Deferred lighting | one thread per pixel | albedo, coalesce buffer | lit output | yes |

- Gather: per thread, compute the probe index, base ray index, spacing and interval; map the four ray indices of a 2×2 block of the direction grid, `[0, √rc_i]²`, to `[−1, 1]²` and through the equal-area map of Pharr et al. (ref. 30, *Physically Based Rendering*, 4th ed., sec. 3.8, formula not given); place probes over the depth buffer at the cascade's spacing offset by half a spacing, reconstruct world positions with the inverse projection and view; trace 4 rays over the interval, a hit returning the hit surface's emissive texture and a miss black except at the last cascade (an analytic sky, which made no measurable difference; the latest code reads an HDR skybox), alpha 1 for a miss and 0 for a hit; average the four rays, hits and misses alike.
- Merge, following Sannikov's diffuse method: if the lower texel's alpha is 0 (all 4 rays hit), skip so no upper radiance passes through geometry; otherwise merge 16 upper rays into 4 lower rays by sampling four sets of neighbouring upper directions, one sample each thanks to pre-averaging, interpolated bilinearly over the four nearest upper probes. The thesis gives no weights or what a skipped merge keeps.
- Coalesce sums each probe's directions into one irradiance value; the normalization is not stated.
- Lighting reads the coalesce buffer bilinearly. Probes sit on surfaces and inward rays carry nothing after the occlusion test, so the result approximates the outward hemisphere. The diffuse term is `fr = 1.0·albedo` with the cosine set to 1, outgoing light `albedo·(coalesced irradiance)`, written `albedo·∫Li dωi`; no `1/π` appears.

**Test setup.** MiniEngine's Sponza (about 262k triangles, chosen for its use in GI research), scaled ×100 for MiniEngine's camera speed to a bounding radius of 2590 units, with a floating 31k-triangle emissive sphere oscillating between Sponza's far sides. Ray length 5.0 for every test (it does not affect RC resource creation), chosen by hand for a cohesive diffuse look; output is unchanged if scene and ray length scale together. Spacing 1 to 4, maximum cascades 5 to 8, rays 16, 36, 64: 4 × 4 × 3 = 48 configurations per resolution, 64 frames averaged per test (counted in frames so each test gets the same sample count), 30 full runs per resolution by a central-limit rule of thumb, each 64-frame mean one sample. Spacing stops at 4 because higher spacing does not reach 8 cascades at 1080p; cascades start at 5 because 5 to 6 are called the minimum for full radiance capture and, for the tested camera, cascade levels had no meaningful visual effect. Total frame time is the sum of RC pass times, excluding the G-buffer. MSI GeForce RTX 3080 SUPRIM X 10 GB, driver 580.88 (2025-07-31), clocks locked. Fig. 4.6 shows 1440p, 64 rays, ray length 5.0, 8 cascades, spacing 1; Figs. 5.1 and 5.2 show Sponza at 2048² for spacing 1 to 4 (36 rays) and rays 16, 36, 64 (spacing 2), not evaluated for quality.

**Consistency.** Standard deviation of the mean over 30 runs: 0.005 to 0.056 ms at 1080p, 0.006 to 0.104 ms at 1440p; 95% confidence half-widths within ±0.0210 ms at 1080p and ±0.0385 ms at 1440p (the abstract rounds to ±0.04 ms). Means range from under 2 ms (R16-S4-C5 at 1080p) to over 240 ms (R64-S1-C8 at 1440p).

**All 96 configurations** (Tables 5.1 to 5.3 and A.3 to A.5), each cell total RC time in ms / VRAM in MB / gather share in %:

| Resolution | Spacing | Rays | 5 cascades | 6 | 7 | 8 |
|---|---|---|---|---|---|---|
| 1080p | 4 | 16 | 1.94 / 24 / 88.2 | 2.04 / 27 / 87.6 | 2.21 / 31 / 87.3 | 2.36 / 34 / 87.0 |
| 1080p | 4 | 36 | 3.76 / 49 / 91.8 | 4.21 / 57 / 91.8 | 4.61 / 65 / 91.6 | 4.97 / 72 / 91.3 |
| 1080p | 4 | 64 | 6.45 / 84 / 93.8 | 7.25 / 99 / 93.7 | 7.97 / 113 / 93.4 | 8.59 / 125 / 93.1 |
| 1080p | 3 | 16 | 3.00 / 39 / 90.8 | 3.36 / 47 / 90.8 | 3.68 / 53 / 90.6 | 3.95 / 58 / 90.3 |
| 1080p | 3 | 36 | 6.43 / 86 / 93.6 | 7.24 / 103 / 93.6 | 7.96 / 118 / 93.3 | 8.55 / 129 / 93.0 |
| 1080p | 3 | 64 | 11.21 / 149 / 94.8 | 12.64 / 177 / 94.8 | 13.92 / 202 / 94.5 | 14.96 / 222 / 94.2 |
| 1080p | 2 | 16 | 6.39 / 89 / 93.7 | 7.18 / 104 / 93.6 | 7.94 / 119 / 93.4 | 8.66 / 133 / 93.2 |
| 1080p | 2 | 36 | 14.08 / 188 / 95.1 | 15.83 / 221 / 95.0 | 17.54 / 255 / 94.7 | 19.16 / 286 / 94.5 |
| 1080p | 2 | 64 | 24.78 / 323 / 95.7 | 27.89 / 383 / 95.6 | 30.95 / 443 / 95.3 | 33.81 / 499 / 95.0 |
| 1080p | 1 | 16 | 24.74 / 336 / 95.6 | 27.94 / 399 / 95.6 | 30.99 / 459 / 95.3 | 34.04 / 519 / 95.1 |
| 1080p | 1 | 36 | 55.31 / 748 / 96.1 | 62.52 / 889 / 96.0 | 69.35 / 1024 / 95.7 | 76.19 / 1159 / 95.5 |
| 1080p | 1 | 64 | 97.77 / 1292 / 96.4 | 110.53 / 1539 / 96.3 | 122.67 / 1779 / 96.0 | 134.82 / 2019 / 95.7 |
| 1440p | 4 | 16 | 3.08 / 39 / 90.1 | 3.45 / 47 / 90.2 | 3.77 / 53 / 90.0 | 4.04 / 58 / 89.8 |
| 1440p | 4 | 36 | 6.55 / 86 / 93.3 | 7.36 / 103 / 93.3 | 8.08 / 118 / 93.1 | 8.66 / 129 / 92.8 |
| 1440p | 4 | 64 | 11.40 / 149 / 94.7 | 12.83 / 177 / 94.6 | 14.11 / 202 / 94.3 | 15.16 / 222 / 94.0 |
| 1440p | 3 | 16 | 5.15 / 70 / 92.6 | 5.80 / 83 / 92.6 | 6.39 / 94 / 92.4 | 6.86 / 103 / 92.1 |
| 1440p | 3 | 36 | 11.23 / 153 / 94.6 | 12.66 / 182 / 94.5 | 13.96 / 209 / 94.2 | 15.01 / 229 / 93.9 |
| 1440p | 3 | 64 | 19.69 / 253 / 95.4 | 22.24 / 301 / 95.3 | 24.57 / 347 / 95.0 | 26.45 / 383 / 94.7 |
| 1440p | 2 | 16 | 11.26 / 158 / 94.6 | 12.68 / 185 / 94.6 | 14.08 / 212 / 94.3 | 15.36 / 238 / 94.1 |
| 1440p | 2 | 36 | 24.96 / 326 / 95.5 | 28.18 / 390 / 95.5 | 31.31 / 454 / 95.2 | 34.19 / 510 / 94.9 |
| 1440p | 2 | 64 | 44.03 / 582 / 96.0 | 49.71 / 692 / 95.9 | 55.27 / 802 / 95.6 | 60.37 / 902 / 95.3 |
| 1440p | 1 | 16 | 43.86 / 605 / 95.9 | 49.64 / 720 / 95.9 | 55.20 / 830 / 95.6 | 60.77 / 940 / 95.3 |
| 1440p | 1 | 36 | 98.16 / 1305 / 96.3 | 111.21 / 1560 / 96.2 | 123.68 / 1808 / 95.9 | 136.19 / 2055 / 95.6 |
| 1440p | 1 | 64 | 173.97 / 2280 / 96.5 | 197.18 / 2730 / 96.4 | 219.36 / 3170 / 96.1 | 241.56 / 3610 / 95.8 |

**Findings as stated.**

- Probe spacing has the largest effect on VRAM and frame time and dominates the plots; probe count should scale with the inverse square of spacing, as Kung also found. Dense probes come closer to the theory, perhaps from memory-bandwidth stalls at high load, a hypothesis with no hardware counters (Vasiou et al., cited for it, find in a simulator that memory stalls and DRAM traffic follow ray incoherence rather than raw bandwidth; [Vasiou et al.](../sources/2018_vasiou_ray_tracing_performance.md)).
- VRAM and frame time rise linearly with cascade count, the step growing with ray count; each cascade adds a fixed amount. With ray length 5.0, cascades 7 and 8 start outside the scene radius and only miss; misses still count as valid black results, the hardware may skip rays that start outside the scene (untested), and including those cascades did not change the scaling. A shorter ray or a larger scene could change this.
- Resolution: the 1440p/1080p pixel ratio is 1.78; frame-time ratios run from 1.59 to 1.79 and VRAM ratios from 1.67 to 1.81 (VRAM is reported in whole MB, so exact ratios cannot be recomputed), with both minima at R16-S4-C5 and the maxima not named and most configurations near 1.78; R64-S3 and R36-S1 scale linearly with cascade count and others do not. The 5-decimal data give frame-time ratios of 1.588 to 1.792 over all 48 (derived). A larger target means a proportionally larger cascade 0 and every level with it; the light R16-S4 set deviates most (1.59), which the thesis links, without firm evidence, to the same cache effects that favour cheap configurations.
- Ray count: 16 → 36 and 16 → 64 scale below the theoretical 2.25 and 4.0, closest at spacing 1 and furthest at spacing 4 (1080p: 1.94 to 2.24 and 3.33 to 3.96; 1440p: 2.12 to 2.24 and 3.70 to 3.97, derived from the data). The thesis reads it as an upper bound, attributes it to cache effects favouring cheap configurations, and rules out pre-averaging since tracing stays near or above 90% of the time.

Tables 5.1 (1080p) and 5.2 (1440p) give the same data rounded to 3 decimals, and the 5-decimal values are in Tables A.1 and A.2 and Data table D1. Figure 5.5's bars and Figure 5.6's log-scale plot of frame time against probe spacing (with 30, 60 and 120 FPS lines) are shown only as images. Frame-time ratios for the two ray-count steps, from the 5-decimal data (derived):

| Spacing | Cascades | 1080p 16 to 36 | 1080p 16 to 64 | 1440p 16 to 36 | 1440p 16 to 64 |
|---|---|---|---|---|---|
| 4 | 5 | 1.94 | 3.33 | 2.12 | 3.70 |
| 4 | 6 | 2.06 | 3.54 | 2.14 | 3.72 |
| 4 | 7 | 2.09 | 3.61 | 2.14 | 3.75 |
| 4 | 8 | 2.10 | 3.64 | 2.15 | 3.76 |
| 3 | 5 | 2.15 | 3.74 | 2.18 | 3.82 |
| 3 | 6 | 2.15 | 3.76 | 2.18 | 3.83 |
| 3 | 7 | 2.16 | 3.78 | 2.18 | 3.85 |
| 3 | 8 | 2.16 | 3.79 | 2.19 | 3.85 |
| 2 | 5 | 2.20 | 3.88 | 2.22 | 3.91 |
| 2 | 6 | 2.21 | 3.89 | 2.22 | 3.92 |
| 2 | 7 | 2.21 | 3.90 | 2.22 | 3.93 |
| 2 | 8 | 2.21 | 3.90 | 2.23 | 3.93 |
| 1 | 5 | 2.24 | 3.95 | 2.24 | 3.97 |
| 1 | 6 | 2.24 | 3.96 | 2.24 | 3.97 |
| 1 | 7 | 2.24 | 3.96 | 2.24 | 3.97 |
| 1 | 8 | 2.24 | 3.96 | 2.24 | 3.97 |

- Gather share rises with ray count, 87 to 96% overall.
- Equivalences: R16-S1 and R64-S2 cost 24.74 and 24.78 ms at 5 cascades (confidence intervals do not overlap; the gap is about 0.04 ms), with 4× the spatial and ¼ the angular resolution of each other and the same rays per cascade; their VRAM differs (335.6 against 323.4 MB) from integer rounding and the coalesce buffer (1920×1080 against 960×540 probes). Table 5.4 shows their per-cascade buffers (3840×2160 for both down to 3840×2144 and 3840×2112 at cascade 4) and probe counts (1920×1080 down to 120×67, and 960×540 down to 60×33). R64-S4, R36-S3 and R16-S2 form another such set: equal `rc0/sp²` (here `sp` is the probe spacing), similar cost, so spatial and angular density trade at fixed cost.
- Real time (RC passes only; shadows and post-processing need the rest): at 1080p 79.2% of configurations are under 33.33 ms, 62.5% under 16.67 ms and 43.8% under 8.33 ms; at 1440p 64.6%, 50.0% and 22.9%. At 1080p everything except R64-S4-C8 reaches 120 FPS in the thesis's wording, spacing 1 with 36 or 64 rays lands above 30 FPS, and Section 5.5 calls R64-S2-C8 (33.81 ms) and R16-S1-C8 (34.04 ms) "at the 30 FPS line", both just above 33.33 ms; at 1440p no spacing 1 configuration is under 33 ms, the lowest being 43.86 ms (R16-S1-C5). The ray-count groups form three bands in Fig. 5.6 (frame time on a log scale against probe spacing, with 30, 60 and 120 FPS lines) (its values are shown only as images), each with a predictable scaling, which could drive a quality preset.
- Validity threats: 30 runs averaged; parameter interactions not analyzed; one GPU, while other ray-tracing hardware may scale differently; locked clocks, so real measurements would vary more; one scene; no counters, so the bandwidth and cache explanations are speculation.
- Conclusions claim the first systematic multi-parameter scaling analysis of 3D RC with hardware RT. Future work: hardware counters (cache behaviour, memory bandwidth, RT core occupancy) to turn correlation into cause, deeper statistics, visual quality across parameters and quality/performance trade-offs, comparison with other GI, outdoor scenes where far-field probes matter and interiors with small objects where near probes matter, and specular with scenes other than Sponza. The abstract calls probe spacing of 2 or more promising for real-time use.

**Inconsistencies.** Section 6.2.1's 64.4% against Table 5.5's 64.6% (31 of 48 rows); Section 7.1's claim that spacing 2 or more "consistently achieved over 60+ FPS at 1080p" against the data (R64-S2 at 24.78 to 33.81 ms, R36-S2 at 7 and 8 cascades at 17.54 and 19.16 ms, and only 62.5% of 1080p configurations under 16.67 ms); the 1440p half-width of ±0.0385 ms against a maximum of 0.0388 ms in Table A.2 (R64-S1-C6, [197.14082, 197.21834]); "at the 30 FPS line" for two rows above 33.33 ms; the double use of "2x/4x"; and whether the lighting pass is in the totals. The 1080p counts below the three thresholds (38, 30 and 21 of 48) match the table (derived), and "all configurations except R64-S4-C8 reach 120 FPS" holds only within spacing 4, where R64-S4-C8 (8.59 ms) is the one row above 8.33 ms, against 43.8% of all 1080p rows (derived from the table).

**Answers from the code** (ClaikoCode at commit 21024b5, newer than the thesis, with two passes that differ from the text):

| Gap | Code |
|---|---|
| Formats | cascades and coalesce buffer `R16G16B16A16_FLOAT`, cleared to (0, 0, 0, 0) (`src/RadianceCascadeManager3d.cpp:11, 74-100`); gather-filter masks `R8_UNORM` per cascade with a `uint32` reduction buffer (:16, 84, 103); depth copy `R32_FLOAT` and Hi-Z `R32G32_FLOAT` (`src/RadianceCascades.cpp:249-252`); albedo in MiniEngine's HDR color format `R11G11B10_FLOAT`, normals `R16G16B16A16_FLOAT` with alpha as the emissive flag (`MiniEngine/Core/BufferManager.cpp:85, 113-114`) |
| Thread groups | merge and coalesce `[numthreads(8, 8, 1)]` with ceil division; ray generation one DXR invocation per (probe, direction) texel |
| Intervals | none in the thesis; in the code, start `|rayLength0·(1 − r^c)/(1 − r)|` and length `rayLength0·r^c`, with `r = rayScalingFactor = 4` (commented "needs to be a perfect square") and `rayLength0 = 5`, so `[0, 5], [5, 25], [25, 105], …`; `TMin = start`, `TMax = start + length` (`Assets/shaders/RCCommon3D.hlsli:86-89, 143-144`, `RCRaytraceRT.hlsl:109-110`) |
| Equal-area map | `OctToFloat3EqualArea` (`RCCommon3D.hlsli:112-126`), the Clarberg map ([cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d)); directions are texel centres remapped to `[−1, 1]²` (`GetRCRayDir`, :149-159) |
| Direction rotation | none; directions depend only on the ray index |
| Merge | each pre-averaged texel reads its 4 upper sub-rays at the 4 bilinear upper probes with standard `frac` weights, carries each as `near.a·far` and averages over the sub-rays; `near + far` is written back into the same UAV, so the merge runs in place, top-down (`RCMerge3DCS.hlsl:40, 115-159`, `RadianceCascades.cpp:1408-1425`). A texel with alpha 0 returns early and keeps its own value, as do rays the gather filter dropped (never written, so still cleared). Alpha is not clamped and can exceed 1 after a merge; only the near alpha, which stays in [0, 1], scales radiance, so rgb is unaffected |
| Coalesce | `rgb = Σ/rayCount` over all directions (the count divided by 4 first with pre-averaging), alpha 1: a plain average with no 1/π and no cosine (`RCCoalesce3DCS.hlsl:23-45`) |
| Final lighting | differs from the thesis. The active path (`DeferredLightingPassPS.hlsl`, inside an `if (true)`) skips the coalesce buffer: it reads the cascade 0 probe at `int2(uv·probeCounts)` (nearest, no interpolation), sums each direction's radiance times `clamp(n·d, 0, 1)`, divides by the ray count and multiplies by albedo. The thesis's bilinear read of the coalesce buffer survives only in the dead `else` branch. Emissive pixels show their albedo directly, and a depth-aware branch is commented "Completely broken for now" |
| Sky | differs from the thesis. Only top-cascade misses with the skybox enabled read an equirectangular HDR skybox (`u = atan2(z, x)/2π + 0.5`, `v = acos(y)/π`); other misses return black, and the procedural `SimpleSunsetSky` call is commented out (`RCRaytraceRT.hlsl:262-278`, `Common.hlsli:83-109, 187-194`) |
| Emissive | glTF emissive textures load as sRGB block formats (BC7, BC3 or BC1 `_UNORM_SRGB`); the closest-hit shader samples mip 0 at the interpolated UV and returns `(emission, 0)`; the material's `emissiveFactor` is never read (`RCRaytraceRT.hlsl:241-258`, `MiniEngine/Model/TextureConvert.cpp:171-175`) |
| Probe counts | `floor(width/spacing0)` per axis (a comment says rounding up would place probes off screen), cascade count `floor(log_2(min count))` capped at 8, and integer division by `2^c` per cascade (`RadianceCascadeManager3d.cpp:48-56, 180-188`); directions per side `(uint)sqrt(rays/4)`, which truncates non-square counts |
| Pre-averaging off | implemented and switchable at run time ("Use Pre Average Intervals", on by default), but the ray payload array holds 4 entries, so a ray scaling factor above 4 would overflow (`RCRaytraceRT.hlsl:165, 187-195`) |

The active lighting returns `albedo·(1/N)·Σ L·max(0, n·d)`, a quarter of Lambert's `(albedo/π)·E` with `E ≈ (4π/N)·Σ L·max(0, n·d)`: under a uniform sky `L` it gives `albedo·L/4`. The thesis's coalesce path, a plain direction average, gives `albedo·L` only if no direction is blocked; on surfaces the inward directions return black, which halves it (derived).

**Read against the model (derived).**

- **The reported VRAM is the texture allocation.** RGBA16F cascades at the floor-divided sizes plus the coalesce buffer, read in MiB, match all 96 VRAM entries to within 0 to 23 MiB.
- **Throughput is nearly constant.** Rays per frame are `(w/s)·(h/s)·rc0` per cascade; at 5 cascades the gather runs 6.1 G rays/s at R16-S4 and 7.0 G rays/s at R16-S1 and R64-S2, which is why equal `rc0/sp²` gives equal cost. The C8 rows reach about 8.2 G rays/s, inflated by rays that cannot hit anything.
- **Rays that cannot hit still cost about 60%.** At spacing 1 the 6th, 7th and 8th cascades add nearly equal time (1080p R16: +3.20, +3.05, +3.05 ms; 1080p R64: +12.76, +12.14, +12.15; 1440p R64: +23.21, +22.18, +22.20), and cascades 7 and 8 start outside the scene. Each such cascade costs 58 to 64% of an average cascade among the first five, so per-ray fixed cost (launch, payload, write) outweighs traversal on this hardware, and cutting ray count saves more than shortening rays.
- **Spacing scales almost exactly quadratically.** Halving spacing from 2 to 1 multiplies time by 3.93 to 4.00, and from 4 to 2 by 3.67 to 3.98, against the 4× of the probe count; "super-linear" in the thesis means this near-quadratic growth.
- At 1080p one cascade of 16 rays at spacing 1 is 33.2 M rays and takes about 4.7 ms of gather. Under 4 ms at 5 cascades the table allows 16 rays at spacing 3 or 4 and 36 rays at spacing 4.

## Kung (2025): RC against voxel cone tracing

| | |
|---|---|
| Title | Comparing Radiance Cascades to Voxel Cone Tracing for Interactive Global Illumination in Dynamic Scenes |
| Author | Johannes Kung |
| Institution | Linköping University, MSc thesis, June 2025 (LiTH-ISY-EX--25/5758--SE), with Beartwigs AB (the game Romestead) |
| Link | https://www.diva-portal.org/smash/get/diva2:1967544/FULLTEXT01.pdf |

Screen-space 3D RC in a shipping game engine, compared with voxel cone tracing on Sponza. The implementation is naive and its timings poor, so its value lies in its catalogue of artifacts and their causes; a probe placement bug found late makes results at sparse spacing less reliable ([Kung](../sources/2025_kung_rc_vs_voxel_cone_tracing_thesis.md)).

**Implementation.**

- Probes on a 2D screen grid every SPS pixels (1, 2 or 4), each at the depth of its pixel and pushed out along the normal.
- Directions: `n` azimuth × `m` polar angles on the full sphere, `φ_j = (j + 0.5)·2π/n`, `θ_k = (k + 0.5)·π/m`, 4×4 at cascade 0. Equal polar steps oversample the poles, which the author flags as a possible bias.
- Branching 2 per axis: probes halve per screen axis and directions double per angle axis per cascade, so each cascade texture has the same size; direction-first layout, an `n×m` grid of tiles, one per direction.
- Rays march the depth buffer with a fixed thickness and return the G-buffer emission at a hit; no bounces. The prototype also has a voxel marcher over a 256³ texture.
- Merge: for each direction, average the 4 nearest upper directions, each read bilinearly from 4 upper probes; β is interpolated like radiance; two textures alternate.
- Shading `E ≈ (1/N)·Σ L0(ω)·(ω·n)` from bilinearly interpolated cascade 0, then `albedo·E + emission`.

**Performance** (RTX 3060, 1280×720, 6 cascades, D3D11 timestamps, medians):

| Scene | SPS 1 | SPS 2 | SPS 4 |
|---|---|---|---|
| House (small indoor) | 70 ms | 18 ms | 4.9 ms |
| Dungeon | 196 ms | 66 ms | 21 ms |
| Plains (large outdoor) | 294 ms | 100 ms | 30 ms |
| Vulcano (large outdoor) | 295 ms | 99 ms | 30 ms |

Doubling SPS cuts time by about 3×, not 4×. Time grows with scene size because rays march fixed steps (`20·1.2^i` per cascade) until they hit, so open scenes produce long rays; moving objects did not change the cost. SPS 1 is not real time and SPS 2 might be after optimizing the march, the main cost.

**Artifacts against VCT.**

| Artifact | Cause given | Remedy given |
|---|---|---|
| Light leaks through thin objects | the depth buffer lacks hidden surfaces; coarse voxels merge emitter and occluder; large steps; a ray missing an edge then merging with an upper ray beyond it | better tracing |
| Light and dark leaks at depth edges | merge and shading interpolation ignore depth | depth-aware (bilateral) weights |
| Flicker under camera or object motion | screen probes jump in depth between frames | world-space probes with reprojection, low-pass filtered depth, or temporal accumulation |
| Small lights too dim, with ray streaks | too few cascade 0 directions hit them | more directions, or per-frame direction offsets accumulated |
| Light drifting toward the lower left at large SPS | probably a probe placement bug | fix placement |

Every artifact but the small-light one grows with SPS. VCT only showed leaks, stronger than RC's through thin objects.

**The VCT baseline** (compix/VoxelConeTracingGI, MIT): six clip regions of 128³ voxels, each twice the extent of the last, in one RGBA8 3D texture of `(130·6) × (6·130) × 130` texels with face-based anisotropic storage weighted by squared direction components; clip levels revoxelized toroidally, one per frame by priority. Passes: geometry, voxelization, shadow map, radiance injection (MSAA by default, conservative rasterization optional), border wrap, GI, forward. Diffuse uses 16 cones of 0.872665 rad (50°) aperture stepping `max(diameter, voxel)·stepFactor` (minimum 0.2) out to 30 units with occlusion decay 5; specular cones use aperture `max(roughness, 0.05)`; AO factor 2, indirect diffuse 15, specular 2, trace offset 1. Voxel cone tracing itself is in [related probe GI](related_probe_gi.md).

**Read against the model (derived).** Rays stay at 1280·720·16/SPS² per cascade, 88.5 M per frame at SPS 1. House runs at 1.13 to 1.26 G rays/s at every SPS, while Dungeon falls from 0.45 to 0.26 and the outdoor scenes from 0.30 to 0.18 G rays/s as SPS grows. The 3× instead of 4× per doubling therefore comes from per-ray cost rising at sparse spacing in large scenes, where the fixed-step march dominates; the small House scales almost 4× (3.89 and 3.67).

## Gerassimov (2026): RC against Unity's GI

| | |
|---|---|
| Title | Radiance Cascades Compared to Unity's Standard Global Illumination Methods |
| Author | Mikhail Gerassimov (Kazakh-British Technical University, Almaty) |
| Venue | DiGRA CA 2026 proceedings, 2026-04-18, https://doi.org/10.26503/dl.v2026i2.2775 |
| Link | https://dl.digra.org/index.php/dl/article/view/2775; data https://github.com/Zertass-2-0/Radiance-Cascades-Compared-to-Unity-s-Standard-Global-Illumination-Methods |

The paper compares SSGI, built-in Realtime Lightmaps (RTLM) and RC in Unity's URP across three scenes with fixed camera paths and synchronized dynamic lights ([Gerassimov](../sources/2026_gerassimov_rc_vs_unity_gi.md)).

**Scope as stated.** Only free, openly available URP methods; one hardware configuration; qualitative visual evaluation without user studies; one controlled run per method and scene, so statistical robustness may be limited; relative comparison, not reproducibility. Intel Core i7-13620H, RTX 4060 Laptop GPU, 16 GB, Windows 11, Unity 6000.2.12f1, URP; render resolution not stated; timing by Unity Recorder and a CSV script.

**Scenes.** Each is a representative scene from its asset pack, with controlled lighting and test conditions added. Realistic FPS (urban exterior from Industrial Set V2.0, dynamic light, partial occlusion); Isometric (the Tanks Complete Project scene; RC has no orthographic support, so every method used a perspective camera with a very narrow field of view); Stylized (low-poly interior from the FPS Microgame, mobile-tier limits). Cameras follow identical spline paths; muzzle flashes, door sequences and moving point lights are synchronized; each run lasts about a minute and covers the path twice; metrics are frame time and FPS, analyzed for trends, stability and relative differences; representative frames and screenshots were captured per scene and method, and artifacts were annotated by hand and grouped (temporal instability and ghosting, dynamic emissive surfaces, inconsistent indirect light, method-specific artifacts).

**Methods.** SSGI, URP's screen-space method (implementation not named), relies on previous frames (citing Abou Dan and Jensen) and computes indirect light mainly for visible geometry; RTLM bakes emissive light only for static geometry, so opening doors cannot be baked (citing Lambru et al. 2021, [notes](../sources/2021_lambru_realtime_gi_game_engines_comparison.md), a study the paper says predates current URP pipelines); RC is "recently proposed", with no algorithm, parameters, layout or implementation named. The data repository (read at 52c7393, MIT) holds no RC code, package name or settings either, and no SSGI or RTLM settings are given anywhere; the paper says only that GI solutions "are currently not freely available for URP environments" and that free, openly available methods were tested. The DiGRA landing page lists no data link; the repository URL is printed in the PDF. The paper cites Kung's comparison of RC with voxel cone tracing and notes that voxel GI implementations are not freely available for URP.

**Performance** (the paper has no FPS tables; recomputed from the repository's CSVs, frames with `time_sec ≥ 5`, 270 to 274 steady frames per run):

| Scene | Method | FPS median | FPS mean | FPS sd | ms median | ms sd |
|---|---|---|---|---|---|---|
| Isometric | NoGI | 343.0 | 338.7 | 30.1 | 2.92 | 0.42 |
| Isometric | RC | 225.7 | 224.2 | 10.6 | 4.43 | 0.32 |
| Isometric | RTLM | 216.5 | 213.3 | 14.1 | 4.62 | 0.44 |
| Isometric | SSGI | 104.0 | 104.0 | 1.0 | 9.62 | 0.09 |
| Realistic | NoGI | 387.3 | 393.2 | 52.8 | 2.58 | 0.43 |
| Realistic | RC | 229.9 | 225.7 | 20.3 | 4.35 | 0.40 |
| Realistic | RTLM | 208.5 | 206.1 | 12.7 | 4.80 | 0.34 |
| Realistic | SSGI | 140.1 | 142.1 | 12.2 | 7.14 | 0.57 |
| Stylized | NoGI | 391.0 | 415.5 | 78.4 | 2.56 | 0.45 |
| Stylized | RC | 266.9 | 266.1 | 17.9 | 3.75 | 0.26 |
| Stylized | RTLM | 272.2 | 283.3 | 39.1 | 3.67 | 0.46 |
| Stylized | SSGI | 144.1 | 144.1 | 13.2 | 6.94 | 0.61 |

NoGI, a baseline without GI, appears only in the charts and CSVs. The CSVs (`gi_run_{NoGI,SSGI,RTLM,RC}_2026-02-19_*.csv` per scene, with an xlsx summary and Unity analytics files) have the header `time_sec,ms_per_frame,fps,gi_mode` but write decimals with commas, so a row has more fields than the header and needs a locale-aware parse; each RC run has about 288 rows.

**Visual artifacts.**

| Scene | Method | Observed | Cause as stated |
|---|---|---|---|
| Isometric | RC | convincing indirect light from emissive materials and dynamic lights | none |
| Isometric | RTLM | no dynamic emissive contribution | emissive light baked only for static geometry |
| Isometric | SSGI | overall darkening | none |
| Isometric | SSGI | light trails behind moving emitters, like long-exposure photography | reliance on previous frames |
| Realistic | RC | a bloom-like effect on lit surfaces even in neutral daylight, excessive bleeding, loss of material definition | appears to over-amplify indirect radiance in strong light; not suited to physically plausible daylight |
| Realistic | RTLM | the most natural and stable indirect light; doors need extra artificial light | doors cannot be baked |
| Realistic | SSGI | little indirect light over large areas, which look unnaturally dark | most contributing geometry is outside the frustum |
| Stylized | RTLM | ignores dynamic emissive contributions, which limits interactive lighting | baking limit |
| Stylized | RC | excessive noise and blur, most visible up close | none (cites Abou Dan and Jensen, Kung) |
| Stylized | SSGI | the most pleasing result; multi-coloured noise for the first few frames | none |

**Ratings and recommendations** (Table 1): performance high for RC and RTLM, low for SSGI; dynamic objects full for RC and SSGI, limited for RTLM; temporal stability medium for RC, low for SSGI, high for RTLM. RC suits many dynamic lights seen from a distance, SSGI contained interiors whose reflecting surfaces stay on screen, RTLM a supplement to baking for static geometry under dynamic lights. Future work: HDRP, custom GI, more hardware tiers, user studies and hybrid pipelines.

**Read against the other sources.**

- Over the NoGI baseline RC adds 1.19 to 1.77 ms, RTLM 1.11 to 2.22 ms and SSGI 4.38 to 6.70 ms (derived from the medians).
- The only free URP RC found is alexmalyutindev's plugin, whose README calls its direction-first mode unstable under camera motion and whose modes have no timings; if it is the one tested, the "medium" stability and the noise and blur up close match that README (inference, [implementations](3d_screen_space_implementations.md#unity-urp-plugin)).
- The bloom-like over-brightening in daylight is the same symptom as over-normalized gathers elsewhere: several codes return 1.27× to 3× too much light under a uniform sky ([3D screen space](3d_screen_space.md#final-gather)); without the code the cause cannot be checked (inference).

## Connections

- **Every SPWI thesis measures tracing, not RC.** Dell'Ova's 87 to 96% gather share, Kaméus's ray-query waits and Gavras's negligible SIMD gain say the same thing: the RC parts (merge, layout, pre-averaging) are cheap and the ray budget is the design.
- **The flicker reports converge.** Gavras, Kaméus, Abou Dan and Jensen, Kung and Gerassimov all report flicker under camera motion, and all trace it to probes re-placed at new depths each frame; Kaméus's Min+Max is the only measured single-frame mitigation ([3D screen space](3d_screen_space.md#temporal-stability)).
- **Two theses agree on spacing.** Dell'Ova's near-quadratic spacing scaling and Kung's 3× per doubling differ because Kung's fixed-step march makes per-ray cost depend on scene size, while hardware RT keeps per-ray cost almost constant (derived above).
- **No thesis measures quality against cost together.** Dell'Ova measures cost without quality, Kaméus quality at three densities, Gerassimov qualitative impressions; the quality-per-ms curve that a design needs is missing.

## Single-frame assessment

- All five RC theses run without temporal reuse; Gerassimov's paper and data repository do not identify the RC tested. Single-frame screen-probe RC is the tested default, not an exception.
- Measured single-frame costs at 1080p-class resolution: 1.9 ms (spacing 4, 16 rays, 5 cascades) to 8.7 ms (spacing 2, 16 rays, 8 cascades) on an RTX 3080 with DXR (Dell'Ova), about 10 ms on an RTX 2070 at one probe per 4×4 px (Kaméus), 2 to 26 ms for SSRC in a game (Abou Dan and Jensen), and 33 to 156 ms with software traversal on an M1 (Gavras).
- What a single frame lacks is stability, not convergence: every thesis reports flicker and none reports noise.

## Open questions

