# Exploration and Optimization of Radiance Cascades for Real-Time Applications

| | |
|---|---|
| Author | Kyriakos Gavras |
| Date | 2025 |
| Kind | Master's thesis (Chalmers) |
| Link | https://odr.chalmers.se/items/3ee9fb4e-1880-46c2-802a-a660e38dc9ee |

Master's thesis from Chalmers University of Technology, supervised by Ulf Assarsson and examined by Erik Sintorn. It explains 2D screen-space radiance cascades (RC), then a 3D variant called Screen-Space Probes with World-Space Intervals (SPWI) that traces rays in world space for one bounce of diffuse light.

Source files: PDF at https://odr.chalmers.se/bitstreams/256da4eb-990c-4e51-aae1-c7878609e314/download (67 pages), handle https://hdl.handle.net/20.500.12380/310889. Figures are images; these notes use captions and text only. Sections marked "(derived)" are arithmetic from the source's own formulas, not values the source states. Sections marked "(compiled)" summarize several parts of the source and are not thesis sections.

## Contents

- [1 Introduction](#1-introduction)
- [2 Previous Work](#2-previous-work)
- [3 Observations in 2D](#3-observations-in-2d)
  - [3.1 Angular observation](#31-angular-observation)
  - [3.2 Spatial observation](#32-spatial-observation)
  - [3.3 Penumbra condition](#33-penumbra-condition)
  - [3.4 Radiance cascade in 2D](#34-radiance-cascade-in-2d)
    - [3.4.1 Efficient ray marching](#341-efficient-ray-marching)
  - [3.5 Cascade creation process](#35-cascade-creation-process)
- [4 Implementation in a Higher Dimension](#4-implementation-in-a-higher-dimension)
  - [4.1 Comparison of approaches](#41-comparison-of-approaches)
  - [4.2 Placing the probes in depth](#42-placing-the-probes-in-depth)
  - [4.3 Encoding intervals using octahedral maps](#43-encoding-intervals-using-octahedral-maps)
  - [4.4 Cascade hierarchy in SPWI](#44-cascade-hierarchy-in-spwi)
  - [4.5 Merging with the upper cascade](#45-merging-with-the-upper-cascade)
    - [4.5.1 Bilateral filtering (Algorithm 7)](#451-bilateral-filtering-algorithm-7)
    - [4.5.2 Bilinear 3D (Algorithm 8)](#452-bilinear-3d-algorithm-8)
    - [4.5.3 Dispatch strategy (Algorithm 9)](#453-dispatch-strategy-algorithm-9)
    - [4.5.4 Ray tracing kernel (Algorithm 10)](#454-ray-tracing-kernel-algorithm-10)
    - [4.5.5 Tracing and merging results](#455-tracing-and-merging-results)
    - [Merge and upscaling methods (compiled)](#merge-and-upscaling-methods-compiled)
  - [4.6 Final composition](#46-final-composition)
    - [4.6.1 Direction-first layout](#461-direction-first-layout)
  - [4.7 Pass summary (compiled)](#47-pass-summary-compiled)
- [5 Experiments](#5-experiments)
  - [5.1 Pre averaging](#51-pre-averaging)
    - [5.1.1 Thread organization](#511-thread-organization)
    - [5.1.2 SIMD shuffle operations (Metal)](#512-simd-shuffle-operations-metal)
    - [5.1.3 Pre-averaging algorithm (Algorithm 12)](#513-pre-averaging-algorithm-algorithm-12)
    - [5.1.4 Pre averaging result](#514-pre-averaging-result)
- [6 Results](#6-results)
- [7 Discussion and Future Work](#7-discussion-and-future-work)
  - [7.1 Min max depth buffer](#71-min-max-depth-buffer)
- [8 Conclusion](#8-conclusion)
- [Inconsistencies and unclear points (compiled)](#inconsistencies-and-unclear-points-compiled)
- [Links found](#links-found)

## 1 Introduction

Real-time global illumination with path tracing relies on denoisers and temporal accumulation. The thesis says these can cause artifacts such as ghosting in dynamic scenes.

The thesis presents RC as a single-frame global illumination method. It responds to changes in lighting, geometry, and viewpoint without temporal accumulation, citing [1].

The thesis names video games and interactive visualization as target uses.

## 2 Previous Work

The chapter groups real-time global illumination into three families.

| Family | Methods cited | Trade-off stated in the thesis |
|---|---|---|
| Path tracing | Monte Carlo path tracing [11]; ReSTIR [12]; ReSTIR GI [13] | Needs denoisers [14] and temporal accumulation; can ghost or be unstable in dynamic scenes |
| Screen-space | SSAO [15]; SSGI [16] | Fast, but cannot capture off-screen indirect light |
| Probe-based | Irradiance Volumes [17]; Light Propagation Volumes [18]; DDGI [19] | Covers 3D space; high memory use and complex probe placement |

The thesis says SPWI is single-shot, so it avoids the denoisers that path tracing needs.

The thesis says SPWI reaches off-screen light through world-space ray tracing.

The thesis also says the existing approaches generally give better temporal stability than SPWI, because SPWI repositions screen-space probes.

## 3 Observations in 2D

### 3.1 Angular observation

Figure 3.1 shows a probe that casts 16 rays. A far light source can be missed when the angular resolution is too low.

Angular resolution is the angle between neighboring evenly spaced rays.

Two quantities set the angle the probe needs:
- Δ: the distance to the furthest object.
- w: the size of the smallest object.

The thesis gives the relation Δω < w/Δ, where Δω is the angle between rays. It says this formalizes the paper's observation and cites [2].

### 3.2 Spatial observation

A point close to a light needs a dense probe grid to resolve the penumbra with interpolation (Figure 3.2, from [1]).

A point far from the light can use a coarse grid with higher angular resolution (Figure 3.3, from [1]).

The thesis calls this the inverse of the angular observation.

### 3.3 Penumbra condition

Equation 3.1 combines both observations:

- Δp ≲ D
- Δω ≲ 1/D

Δp is the spacing between probes, Δω is the angle between rays, and D is the distance to the occluder.

The thesis footnote defines A ≲ B as: A is less than the output of some function that scales linearly with B.

### 3.4 Radiance cascade in 2D

Everything in 2D happens on a flat plane, including the casting of intervals.

The thesis bases its efficient ray marching on Jason's blog [3].

#### 3.4.1 Efficient ray marching

Ray marching needs a signed distance field (SDF) so each step can be as large as possible without crossing a surface.

The scene is a user-drawn texture (Figure 3.4). The SDF is built from it with the Jump Flood Algorithm (JFA).

Algorithm 1, the host procedure JFAPass, works as follows:
1. Take the seed texture, width, and height. Create two textures, A and B.
2. Set input to the seed texture and output to A.
3. Set passes to ceil(log2(max(width, height))).
4. For stage = 0 to passes − 1, set step = 2^(passes − stage − 1), run the JFA shader from input into output with that step, then swap input and output.

Algorithm 2, the JFA shader, works per pixel at position uv:
1. Start with nearest seed = (0, 0) and nearest distance = infinity.
2. For each offset (x, y) with x and y in {−1, 0, 1}, sample at uv + (x, y) × step × (1 / textureSize).
3. If the sample is inside the texture and its stored seed (xy) is not (0, 0), compute dist = L2 distance between that seed and uv.
4. If dist is less than the nearest distance, keep this seed and distance.
5. Return the nearest seed.

Each pixel of the JFA result stores the coordinates of its nearest edge seed (Figure 3.5).

A later shader converts those coordinates into Euclidean distances, giving the distance texture (Figure 3.6) that ray marching steps through.

The thesis says JFA takes O(log n) time.

Derived: for a 512 × 512 texture, passes = 9 and the steps are 256, 128, 64, 32, 16, 8, 4, 2, 1.

### 3.5 Cascade creation process

The cascade count is set by the screen diagonal:
- diagonal = sqrt(width² + height²)
- cascadeCount = ceil(log(diagonal) / log(baseRayCount)) + 1

The thesis uses a branching factor of 4 to scale angular and spatial resolution.

Probe spacing at cascade c is sqrt(baseRayCount^c). With base 4 this is 2^c pixels.

Rays per probe at cascade c is baseRayCount^(c + 1).

Each probe's rays are evenly spaced over the full circle.

Cascades are processed from highest to lowest. The thesis gives the reason: radiance from the furthest points is carried down to the nearest points during merging.

Two render targets alternate between cascades (ping-pong). The thesis says only two textures are needed for the merge.

Algorithm 3, RCPass, works as follows:
1. Compute the diagonal and cascadeCount.
2. Create renderA and renderB at the screen resolution. Set pingPong = 0 and lastMerge = null.
3. For cascade from cascadeCount − 1 down to 0:
   a. rayCount = baseRayCount^(cascade + 1).
   b. Target is the final output when cascade = 0; otherwise it is renderA or renderB, chosen by pingPong.
   c. Flip pingPong.
   d. Run RayMarch into the target with the drawing texture, distance texture, lastMerge, cascade, and rayCount.
   e. If cascade > 0, set lastMerge to the target.
4. Return the final output.

Algorithm 4, RayMarch with cascade sampling, runs for each probe and each of its rays:
1. Compute the probe parameters for the cascade: grid size, spacing, and interval. The source does not define these values for the 2D case.
2. Set the start point to the probe position + intervalStart × ray direction.
3. If the start point is inside the bounds:
   a. Repeat up to maxSteps times: read the SDF distance d at the current point, move the point by d along the ray, and stop with no hit if the point leaves the bounds or goes beyond the interval.
   b. If d ≤ minStep, count it as a hit: the ray's contribution is the color at the point, and stop.
   c. If there was no hit and the cascade is not the highest, the contribution is taken from the upper cascade.
4. Add the ray's contribution to a running sum.
5. Output sum / rayCount.

The source does not give values for maxSteps or minStep, and it does not say how distance traveled is measured. In the pseudocode, the upper-cascade step sits inside the "start point is inside the bounds" branch.

For the merge, the text says each probe takes the radiance of the upper cascade by mapping its position into the upper level (which has a different resolution) and sampling with linear interpolation. The text says each level merges 4 rays from each of the 4 nearest probes. The exact angle mapping is unclear in source.

Derived table for a 512 × 512 target with base 4 and 6 cascades. Figure 3.7 and the text confirm the top cascade values.

| Cascade | Probe grid | Probe spacing (px) | Rays per probe |
|---|---|---|---|
| 5 | 16 × 16 | 32 | 4096 |
| 4 | 32 × 32 | 16 | 1024 |
| 3 | 64 × 64 | 8 | 256 |
| 2 | 128 × 128 | 4 | 64 |
| 1 | 256 × 256 | 2 | 16 |
| 0 | 512 × 512 | 1 | 4 |

The text says each step down in cascade has 4 times more probes and 4 times fewer rays than the previous pass.

Derived: each cascade traces 1,048,576 rays in total (4 × 512²). The source does not state this total.

Figure 3.7 shows the 6 cascades for a 512 × 512 target.

## 4 Implementation in a Higher Dimension

### 4.1 Comparison of approaches

Table 4.1 as stated in the source:

| Technique | Description | Pros | Cons |
|---|---|---|---|
| Screen-space ray marching | Works entirely in screen space; sampling is limited to visible surfaces | Extremely fast; very memory efficient | Cannot capture off-screen indirect light |
| 3D probe grid | Probes spread through the whole 3D scene in a volumetric grid | Captures off-screen indirect light; view-independent; very stable across camera motion | High memory use; very slow compared to screen-space ray marching |
| SPWI | Places probes in screen space and samples rays in world space | Captures off-screen indirect light; memory-efficient probe hierarchy | Very slow compared to screen-space ray marching |

The thesis says the screen-space approach (which it says Path of Exile 2 uses) suits viewpoints such as top-down games, where off-screen light matters less.

The thesis says 3D grids cost much memory and frame time.

The thesis calls SPWI a middle ground: 1-bounce indirect lighting close to full 3D quality, with memory use closer to screen-space methods.

### 4.2 Placing the probes in depth

The implementation uses a linear depth buffer, which stores distances from the camera. The thesis needs it for thresholding depth differences in bilateral filtering.

Algorithm 5 turns a normalized device coordinate and a linear depth into a world position:
1. Form clip = (ndc.x, ndc.y, −1, 1).
2. Compute view = inverse(projection) × clip, then divide by view.w.
3. Compute scale = linearDepth / |view.z|.
4. Compute viewAtDepth = view.xyz × scale × 0.98.
5. Return inverse(view matrix) × (viewAtDepth, 1), as xyz.

Derived: the 0.98 factor puts the reconstructed point at 98% of its linear depth from the camera. The source says the factor prevents surface acne in later ray tracing.

Probes sit at their screen positions, and their world positions come from the depth buffer (Figures 4.1 and 4.2 show cascade 0 probes).

### 4.3 Encoding intervals using octahedral maps

Octahedral mapping stores unit directions in a 2D square. The source calls it area-preserving and cheap to compute, and cites Cigolle et al. [4].

The thesis describes the mapping as projecting a unit sphere onto an octahedron and unfolding it into a square (Figure 4.3).

The encoding and decoding formulas are not given. The pseudocode uses OctDecode(uv) to get a direction and ToOctahedralCoordinates(direction, raysPerDim) to get a UV. Their bodies are unclear in source.

Figure 4.4 shows the ray distribution for cascades 0, 1, and 2 with 16, 64, and 256 rays.

### 4.4 Cascade hierarchy in SPWI

Each cascade has a start and end distance along the ray. Rays only look for geometry inside that interval. The source does not state the units.

Algorithm 6 (CalculateInterval) uses baseCascadeRange = 0.016 and cascadeRangeMultiplier = 4.0:
- start = 0 when level = 0; otherwise start = 0.016 × 4^(level − 1).
- end = 0.016 × 4^level.

The procedure takes an intervalLength argument that its body does not use.

Derived intervals (the values are arithmetic; units are not stated in source):

| Level | Start | End |
|---|---|---|
| 0 | 0 | 0.016 |
| 1 | 0.016 | 0.064 |
| 2 | 0.064 | 0.256 |
| 3 | 0.256 | 1.024 |
| 4 | 1.024 | 4.096 |
| 5 | 4.096 | 16.384 |

The thesis says the factor 4 in the interval scaling matches the branching factor. The thesis also says interval lengths need to be adjusted to the scale of the world.

Table 4.2 configuration for a 512 × 512 scene, with base ray count 16 and initial probe spacing 4 px:

| Level | Probe grid | Rays per probe | Probe spacing (px) | Rays per dimension (derived) | Probes × rays (derived) |
|---|---|---|---|---|---|
| 0 | 128 × 128 | 16 | 4 | 4 | 262,144 |
| 1 | 64 × 64 | 64 | 8 | 8 | 262,144 |
| 2 | 32 × 32 | 256 | 16 | 16 | 262,144 |
| 3 | 16 × 16 | 1,024 | 32 | 32 | 262,144 |
| 4 | 8 × 8 | 4,096 | 64 | 64 | 262,144 |
| 5 | 4 × 4 | 16,384 | 128 | 128 | 262,144 |

Derived: each level's probes times rays equals 262,144, which is one ray per texel of a 512 × 512 texture. The tile size per probe equals the probe spacing column.

The thesis says six cascade levels gave the best balance of performance and quality on its test scenes. It describes this choice as experimental.

Each level multiplies rays per probe by 4 and halves the probe grid per axis. The thesis says this keeps total cost roughly constant across levels.

Figures 4.5 and 4.6 show the probe-ray layout for the first three cascades from the top and from an angle.

The thesis notes that when the camera is very close to a non-emissive surface, the probes sit on that surface, and the higher cascades' intervals extend behind the camera.

### 4.5 Merging with the upper cascade

After tracing, each cascade merges with the upper cascade, except the highest one.

Plain bilinear interpolation over the 4 nearest upper probes creates artifacts. Upper probes can sit on different depths (Figure 4.7). Outlier probes should get smaller weights, based on their distance from the current probe.

#### 4.5.1 Bilateral filtering (Algorithm 7)

The thesis cites Gjoel [5] for the bilateral filtering method.

The steps of MergeWithUpperCascade are:
1. Get the upper level, grid size, and rays per dimension.
2. Find the 4 nearest upper probes for the current probe's UV.
3. Read the linear depth of each of those probes.
4. Convert the ray direction to octahedral coordinates in the upper map.
5. Compute bilinear weights from the current probe's UV.
6. Compute depthRange = max − min of the 4 depths and avgDepth = their mean. Set isDepthEdge = (depthRange / avgDepth) > 0.1.
7. If isDepthEdge is true, multiply each weight by 1 / (|depth_i − currentDepth| + 0.0001).
8. Normalize the weights to sum to 1.
9. For each probe with weight > 0, bilinearly sample its octahedral map at the direction coordinates, and add the result times its weight.
10. Return the sum.

Figure 4.8 shows every upper ray that contributes to one cascade 0 ray. The thesis says depth awareness is not needed when interpolating between directions, because the probe weighting already handles depth.

#### 4.5.2 Bilinear 3D (Algorithm 8)

The thesis credits Sannikov's Shadertoy [6], released after the original RC paper. The abstract says the implementation incorporates it.

Bilinear 3D works in world space. It uses the 3D positions of the upper probes, not only their depths.

The steps of MergeWithUpperCascade3D are:
1. Get the upper cascade parameters.
2. Find the 4 nearest upper probes (coordinates and UVs).
3. Reconstruct the world position of each of the 4 probes.
4. Compute an initial ratio from screen space with CalculateScreenSpaceRatio(probeUV). The definition is not given in source.
5. Compute ratio3d = GetBilinear3DRatio(the 4 world positions, the current world position, the initial ratio, 2 iterations).
6. Compute bilinear weights from ratio3d.
7. Convert the ray direction to octahedral coordinates for the upper rays per dimension.
8. Blend the samples at the probe coordinates and direction coordinates with those weights.

GetBilinear3DRatio takes 4 source points, a destination point, an initial ratio, and an iteration count. It repeats this for each iteration:
1. Mix src0 with src2 at ratio.y, and src1 with src3 at ratio.y. Project the destination onto the line between the two results, and store the projection parameter as ratio.x.
2. Mix src0 with src1 at ratio.x, and src2 with src3 at ratio.x. Project the destination onto the line between those results, and store the projection parameter as ratio.y.

The corner order src0 to src3 is implied by the pairing, not named in source. The pairs share edges as src0–src1, src2–src3, src0–src2, and src1–src3.

Figure 4.9 compares bilateral filtering and bilinear 3D. The thesis says the striations seen with bilateral filtering are easier to see from steep angles.

The thesis says a better interpolation approach exists, discussed in Future Work (min-max probes, Section 7).

#### 4.5.3 Dispatch strategy (Algorithm 9)

Cascades are dispatched from the highest level down to 0. Level 0 writes to the final gather target.

Two render targets alternate (ping-pong). The thesis says each cascade only needs the cascade just before it.

For each level, the pseudocode sets:
- tileSize = probeSpacing × 2^level.
- probeGridSize from the framebuffer size and tileSize. The function is not defined in source.
- raysPerDim = 2^(level + 2).
- totalThreads = gridX × gridY × raysPerDim².

Derived: totalThreads is 262,144 for every level in Table 4.2.

The text says one ray is dispatched per thread, and the thread count is the same for every cascade when the branching factor is 4.

The pseudocode sets lastMergedTexture to null for the level maxCascadeLevel − 1, and keeps the previous target for lower levels. See the inconsistency list.

#### 4.5.4 Ray tracing kernel (Algorithm 10)

Each thread handles one (probe, ray) pair. The steps are:
1. Compute tileSize = probeSpacing × 2^level, the probe grid size, and raysPerDim = 2^(level + 2).
2. Map the thread ID to a probe index and a ray index.
3. Compute the probe's UV from its index and the grid size.
4. Read the depth texture at the probe UV.
5. Reconstruct the probe's world position (Algorithm 5 semantics).
6. Compute the ray UV from the ray index and raysPerDim, then decode it to a direction with OctDecode.
7. Compute intervalStart and intervalEnd with the Algorithm 6 formulas.
8. Trace a ray from the world position along the direction within [start, end]. This gives a hit result.
9. Set occlusion = 0 on a hit and 1 otherwise.
10. If there is a hit, radiance = GetSurfaceRadiance(hit). Otherwise, if this is the highest level and sky/sun is enabled, radiance = CalculateSkyAndSunRadiance(direction).
11. If the level is below the highest:
    - Get upperRadiance from MergeWithUpperCascade(upper texture, probe UV, direction, probe depth, world position).
    - On a miss, radiance = upperRadiance.
    - On a hit, radiance.rgb += upperRadiance.rgb × occlusion (which is zero on a hit), and radiance.a *= upperRadiance.a.
12. Write radiance to the output position computed from the probe UV, ray UV, and tileSize.

The thesis says the interval makes each cascade cover one distance band, so cascade 0 covers nearby geometry.

The thesis says sky radiance is computed only at the highest level and propagates down through merging.

The thesis says a hit blocks light from beyond it, because occlusion is 0 on a hit.

Unclear in source: the meaning of the alpha channel, the exact formulas for probe UV and output position, and which merge function the kernel calls. The call passes both the probe depth that bilateral filtering uses and the world position that bilinear 3D uses, so its arguments do not settle which one it is.

#### 4.5.5 Tracing and merging results

After all cascades run, cascade 0 holds the merged radiance from every level (Figure 4.10 shows the maps from cascade 5 to cascade 0).

#### Merge and upscaling methods (compiled)

| Method | Where the source uses it | Evidence in source |
|---|---|---|
| Plain bilinear over 4 probes | Shown as the baseline that creates artifacts | Text only |
| Bilateral filtering (Algorithm 7) | Tested for cascade merging; used in final gather (Algorithm 11) | Figure 4.9 (qualitative), no numbers |
| Bilinear 3D (Algorithm 8) | Cascade merging; abstract says the implementation includes it | Figure 4.9 (qualitative), no numbers |

No quantitative upscaler comparison appears anywhere in the source.

### 4.6 Final composition

Only the cascade 0 maps are needed for the final image. The text says they already hold the full merged result.

Each pixel samples the 16 directions of each of the 4 nearest cascade 0 probes. It uses depth-aware weights and cosine weighting.

The final gather uses bilateral filtering, not bilinear 3D. The thesis says bilateral filtering alone was enough here, because striations are not visible across cascade 0's short intervals.

Algorithm 11, FinalGatherFragment, works per pixel:
1. Read albedo, normal, and depth from the G-buffer.
2. If the albedo marks an empty surface, return the sky for this pixel.
3. Get the grid size, the 4 nearest cascade 0 probe coordinates, and their UVs.
4. Read the depth of each of the 4 probes.
5. Set isDepthEdge = (depthRange / avgDepth) > 0.05. Note the threshold differs from Algorithm 7 (0.1).
6. Compute bilinear weights from the pixel position and grid size. If isDepthEdge, adjust them with ApplyDepthBasedWeighting(weights, probe depths, pixel depth). The body of that function is not given.
7. For each of the 4 probes i:
   a. Set radianceSum = 0 and totalWeight = 0.
   b. For every direction in that probe's octahedral map: compute dir = OctDecode(dirUV), cosTheta = max(0, dot(normal, dir)), radiance = GetRadianceSample(probeUVs[i], dirUV, isEmissive, albedo). Add radiance × cosTheta to radianceSum and cosTheta to totalWeight.
   c. probeRadiance_i = radianceSum / max(totalWeight, 0.0001).
8. finalRadiance = sum over i of weights_i × probeRadiance_i.
9. Return albedo × finalRadiance.rgb.

The source calls step 7 "Lambert's cosine law integration". The source does not mention a 1/π factor. Whether one applies is unclear in source.

#### 4.6.1 Direction-first layout

In the earlier layout (probe-first), each probe's directions were stored together. Similar directions from different probes ended up far apart in memory.

In the direction-first layout, each block of the texture is one ray direction. The pixels in a block hold that direction for every probe (Figure 4.12 shows cascades 0 and 1 at 512 × 512).

The thesis gives three reasons for the change: the results are more cohesive, debugging is easier, and hardware interpolation becomes possible for similar rays during merging with higher cascades.

The thesis gives no timing or quality numbers for this layout. It gives no index formula.

### 4.7 Pass summary (compiled)

| Order | Pass | Reads | Writes |
|---|---|---|---|
| 1 | JFA passes (Algorithms 1 and 2) | Drawn scene texture (seed) | JFA texture of nearest seeds |
| 2 | Distance shader | JFA texture | Distance texture (2D only) |
| 3 | Per-cascade pass, highest to 0 (Algorithms 9 and 10) | Depth texture, scene acceleration structure, upper cascade texture | Cascade texture at drawable size |
| 4 | Final gather (Algorithm 11) | Cascade 0 texture, G-buffer (albedo, normal, depth) | Final color |

The thesis does not say how the linear depth buffer or the G-buffer is produced.

Each cascade texture matches the drawable resolution (Section 5). A probe at (level, probe, direction) maps to one texel.

The thesis names Metal in Section 5.1.2 and in the Algorithm 12 heading. Table 6.1 was measured on an M1 MacBook Air. The thesis mentions acceleration structures in the Table 6.1 caption and TraceRay in the pseudocode. No engine or ray tracing API is named beyond Metal.

## 5 Experiments

Storing rays can use storage buffers or textures. The thesis uses textures for simplicity, so each cascade's octahedral texture matches the drawable resolution.

The thesis says halving probe spacing in cascade 0 (4 px to 2 px) would make each cascade's texture 4 times larger.

### 5.1 Pre averaging

Alex and Xor [7] proposed pre-averaging. It averages 4 probe rays into 1 during tracing.

The thesis lists three claimed benefits:
- Texture sizes stay the same, which saves memory.
- The number of merging operations drops by 75%.
- Radiance comes from a finer probe grid, which improves quality.

Figure 5.1 shows the layout. Probe #0 is the main probe that gets written. The orange probes are traced only during ray tracing, and their results are averaged into probe #0 for matching directions.

#### 5.1.1 Thread organization

Adjacent probes in a 2 × 2 neighborhood are handled by adjacent threads in the same SIMD group. The thesis says SIMD groups have 32 or 64 threads.

#### 5.1.2 SIMD shuffle operations (Metal)

SIMD shuffle lets a thread read a register from another thread in the same group. The thesis says this avoids shared memory and synchronization.

#### 5.1.3 Pre-averaging algorithm (Algorithm 12)

1. Map the thread ID to a quad index, a local probe index (0 to 3), and a ray index.
2. Compute the probe position from the quad and local index, then its screen UV.
3. Reconstruct the world position from the depth buffer.
4. Compute the ray UV from the ray index, then decode the direction.
5. Trace the ray from the world position within the cascade interval, giving radiance and occlusion.
6. Set baseLane = lane ID − local probe index.
7. Shuffle radiance from lanes baseLane to baseLane + 3, and average them as sum × 0.25.
8. Do the same for occlusion.
9. Only the probe with local index 0 writes. It merges the averaged radiance and occlusion with the upper cascade and writes to the texture at a position from the quad and ray index.

The source does not define the cascade interval used in step 5.

#### 5.1.4 Pre averaging result

The result comes from an early SPWI build made before depth-aware upscaling. That build shows halos around emissive surfaces (Figure 5.2).

The grid in that build had twice as many probes per axis (4 times as many in total). The thesis says this matches Alexander Sannikov's grid, and is 4 times the grid used in the final solution.

The thesis says tracing 4 times more rays was not viable on its test system. The SIMD gain was negligible because ray tracing dominates the cost.

The thesis expects depth-aware techniques to give better quality per unit of performance. No numbers are given.

## 6 Results

All scenes use 6 cascades. The thesis says each cascade has one ray per pixel, which it calls 6 samples per pixel.

The thesis says performance does not depend on light count, because the rays per cascade are fixed. It also says the cost is bound by acceleration structure traversal, so complex geometry takes longer. It says memory scales with screen resolution and cascade count. No measurement of scaling is shown.

Scene list:

| Figure | Scene |
|---|---|
| 6.1 | Sponza, lit only by sky |
| 6.2 | Four emissive cubes of different colors and two non-emissive cubes |
| 6.3 | One emissive cube |
| 6.4 | Sponza with three emissive hornbug models (pink, blue, yellow) by McGuire [10], showing off-screen light |
| 6.5 | Stanford bunny [9] with a matte cube, showing soft shadows |
| 6.6 | Stanford bunny with two emissive cuboids, with daylight |
| 6.7 | Stanford bunny with two emissive cuboids, without daylight |

Table 6.1 as stated in the source. Measured on an M1 MacBook Air with 8 GB unified memory, 1920 × 1080, 6 cascades. Memory covers acceleration structures, models, buffers, and textures.

| Scene | Rendering time (ms) | Memory (MiB) |
|---|---|---|
| Cube scene (Fig. 6.3) | 32.77 | 147.00 |
| Cubes scene (Fig. 6.2) | 34.42 | 146.88 |
| Bunny cube scene (Fig. 6.5) | 37.07 | 184.66 |
| Bunny cuboids scene (Fig. 6.6) | 39.87 | 184.90 |
| Sponza sky illuminated (Fig. 6.1) | 143.74 | 405.00 |
| Sponza with emissive hornbugs (Fig. 6.4) | 155.90 | 408.50 |

Derived: the two Sponza scenes take about 4.4 to 4.5 times as long as the cube scenes.

The Cube and Cubes scenes are the only pair in Table 6.1 that differ in light count. They also differ in geometry (two extra non-emissive cubes in Cubes).

For comparison, the thesis cites [1]: Sannikov's SPWI with world-space ray marching on an analytic SDF takes about 30 to 50 ms per frame on an RTX 3060.

Table 6.1 is the only timing table in the source. The source gives no per-pass breakdown and no upscaler timing.

## 7 Discussion and Future Work

### 7.1 Min max depth buffer

The thesis calls this "Min Max Probes." It is presented as a better way to merge with the upper cascade, by giving bilateral filtering and bilinear 3D better depth bounds.

Algorithm 13 builds the min-max buffer:
1. Initialization: write the depth to both channels, red as minimum and green as maximum.
2. Mip generation: for each texel of the next level, read the 2 × 2 block at (2x, 2y) of the previous level. Take the minimum of the red values and the maximum of the green values, and write them as (min, max).

Figure 7.1 shows the mip chain. Similar min and max values appear yellow, and large gaps appear green.

The proposed use in cascades:
1. Place two probes per probe, one on the minimum depth plane and one on the maximum depth plane.
2. For each cascade level, select the mip level that matches that cascade's grid resolution.
3. Trace rays from both sets of probes and merge each set separately with the upper cascade.
4. Blend between the current probe and the upper cascade's min and max probes with trilinear interpolation.

The thesis says this doubles the tracing work. It proposes splitting the rays: odd-numbered rays go to the minimum plane and even-numbered rays go to the maximum plane.

The thesis reports no implementation or measured results for this method.

## 8 Conclusion

The thesis says RC gives an effective single-shot diffuse global illumination method across several distance scales. It reports soft shadows and indirect light in its scenes.

The thesis says cost depends on scene geometry more than on light count. It says interval lengths must be adjusted to the world scale.

Limitations stated in the conclusion:
- Screen-space probe placement causes temporal instability, with flicker during camera motion.
- Depth-aware interpolation reduces some of this, but not all.
- Complex scenes need substantial compute, which limits real-time use on mainstream hardware.

Future work named in the conclusion: better probe placement for temporal stability. The thesis says the min-max depth buffer approach looks more promising for quality and stability.

## Inconsistencies and unclear points (compiled)

1. Two different 512 × 512 configurations appear. Section 3.5 and Figure 3.7 have 6 cascades with a 16 × 16 top grid and 4096 rays. Table 4.2 has 6 cascades with a 4 × 4 top grid and 16,384 rays. The source does not explain how they relate.
2. "Base ray count" has two meanings. Section 3.5 uses baseRayCount as the log base and the ray count base (4 in the 2D examples). Section 4.2 gives a base ray count of 16 for cascade 0, with a factor of 4 per level.
3. Algorithm 9 sets lastMergedTexture to null for level maxCascadeLevel − 1. As written, the highest cascade's result is not passed to that level.
4. Algorithm 6 declares intervalLength but never uses it. Interval units are not stated.
5. Algorithm 10 calls MergeWithUpperCascade with five arguments. Algorithm 7 takes three and Algorithm 8 takes three (probe UV, direction, world position). The kernel's merge variant is not named.
6. Algorithm 12 calls ReconstructWorldPosition with one argument. Algorithm 5 takes two. Algorithm 12 also calls MergeWithUpperCascade with two arguments.
7. The depth-edge threshold is 0.1 in Algorithm 7 and 0.05 in Algorithm 11.
8. The Figure 4.4 caption says the octahedral mapping covers the hemisphere. The text describes a unit sphere.
9. Section 3.5 describes the highest cascade of the 2D case as having the most rays. The 2D cascade spacing uses the square root of baseRayCount to the power of the cascade index.
10. The abstract spells the method "Screen-Space Probes with World-Space Intervals". The acronym list spells it "Screen-space Probes World Intervals".
11. Algorithm 4 is shown with the upper-cascade step inside the bounds check. The 2D interval values are not given anywhere in Section 3.
12. The thesis states that performance does not depend on light count. Table 6.1 has only one pair of scenes that differ in light count, and that pair also differs in geometry.

Unclear in source:
- Interval units.
- maxSteps and minStep values in 2D.
- Formulas for grid size (CalculateProbeGrid), probe UV, output position, thread-to-probe mapping, and screen-space ratio.
- Octahedral encode and decode formulas.
- How the linear depth and G-buffer are produced.
- Meaning of the alpha channel in the cascade textures.
- How the 2D merge maps angles between cascades.
- Whether a 1/π factor applies in the final gather.
- The ray tracing API and scene representation.
- Which merge function Algorithm 10 calls.

## Links found

- Sannikov, A. (2023). Radiance Cascades (unpublished manuscript) | https://github.com/Raikiri/RadianceCascadesPaper | Original RC paper; source of the probe-spacing figures and the 30 to 50 ms SPWI reference.
- Coppen, M. (2024). The Fundamental Observation of Radiance Cascades | https://m4xc.dev/articles/fundamental-rc/ | Source of the angular bound Δω < w/Δ.
- MGCHEE, J. (2024). Building a Real-Time Global Illumination | https://jason.today/gi | 2D RC and JFA ray marching that the thesis follows.
- Cigolle, Z. H., et al. (2014). A Survey of Efficient Representations for Independent Unit Vectors. JCGT 3(2) | http://jcgt.org/published/0003/02/01/ | Octahedral mapping reference.
- Gjoel, M. (2021). Depth Aware Upscaling | https://gist.github.com/pixelmager/a4364ea18305ed5ca707d89ddc5f8743 | Bilateral depth-aware upscaling used in Algorithms 7 and 11. The gist is by GitHub user pixelmager and names no author ([notes](2021_pixelmager_depth_aware_upscaling.md)).
- Sannikov, A. (2024). Novel Depth Aware Upscaling | https://www.shadertoy.com/view/4XXSWS | Bilinear 3D method used for cascade merging.
- Alex and Xor (2024). GM Shaders Guest: Radiance Cascades 2 | https://mini.gmshaders.com/p/radiance-cascades2 | Pre-averaging proposal.
- Dabrovic, M. (2002). Sponza Atrium | https://casual-effects.com/data/ | Test scene.
- Turk, G. and Levoy, M. (1994). The Stanford 3D Scanning Repository | http://graphics.stanford.edu/data/3Dscanrep/ | Stanford bunny test model.
- McGuire, M. (2017). Computer Graphics Archive | https://casual-effects.com/data | Hornbug models used in Figure 6.4.
