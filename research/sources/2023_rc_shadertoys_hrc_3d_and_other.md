# Radiance cascades Shadertoys: holographic, media, 3D and other shaders

Shadertoys that use holographic cascades, participating media, 3D and screen-space probes, depth-aware upscaling, cascades for gravity, and related shaders that are not RC. Where the code was read, the licence and code-reference conventions, the frame-lag rules, the index of all shaders, the lineage and the 2D merge shaders are in [Radiance cascades Shadertoys](2023_rc_shadertoys.md).

## Contents

- [Holographic cascades](#holographic-cascades)
  - [4ctczl (Suslik): two families of probe lines](#4ctczl-suslik-two-families-of-probe-lines)
  - [tfKyRw (youssef_afella): one frustum with paper geometry](#tfkyrw-youssef_afella-one-frustum-with-paper-geometry)
  - [WfyyDm (youssef_afella): four frustums in one buffer](#wfyydm-youssef_afella-four-frustums-in-one-buffer)
- [NfVXRc and sfVSzd (Suslik): extended gathering](#nfvxrc-and-sfvszd-suslik-extended-gathering)
- [Media and transmittance](#media-and-transmittance)
  - [wfyyDz (codyjbennett): 2D volumetric cascades with the bilinear fix](#wfyydz-codyjbennett-2d-volumetric-cascades-with-the-bilinear-fix)
  - [ffl3Rf (codyjbennett): hardware bilinear without the fix](#ffl3rf-codyjbennett-hardware-bilinear-without-the-fix)
  - [NfySzt (codyjbennett): hardware bilinear upper fetches](#nfyszt-codyjbennett-hardware-bilinear-upper-fetches)
- [3D and screen space](#3d-and-screen-space)
  - [M3ycWt (Mathis): voxel cascades with hemisphere probes](#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes)
  - [lXByRh (Mathis): screen-space probes merged by hit-point reprojection](#lxbyrh-mathis-screen-space-probes-merged-by-hit-point-reprojection)
  - [scy3Dd (codyjbennett): SPWI in one shader](#scy3dd-codyjbennett-spwi-in-one-shader)
  - [33ycDm (youssef_afella): GTAO from cascaded horizons](#33ycdm-youssef_afella-gtao-from-cascaded-horizons)
- [Depth-aware upscaling and occlusion](#depth-aware-upscaling-and-occlusion)
  - [4XXSWS (Suslik): depth-aware upscaling](#4xxsws-suslik-depth-aware-upscaling)
  - [MXjcWK (Suslik): selective bilinear subsets](#mxjcwk-suslik-selective-bilinear-subsets)
  - [4cffDX (mxcop): normal- and depth-weighted upsampling](#4cffdx-mxcop-normal--and-depth-weighted-upsampling)
  - [ffSSz1 (Suslik): linear min/max interpolation](#ffssz1-suslik-linear-minmax-interpolation)
  - [NfBSz1 (Suslik): perspective-correct min/max interpolation](#nfbsz1-suslik-perspective-correct-minmax-interpolation)
  - [l3scz8 (Suslik): occlusion from depth variance](#l3scz8-suslik-occlusion-from-depth-variance)
- [XcB3Ry and MfS3Wm (Suslik): cascades for gravity](#xcb3ry-and-mfs3wm-suslik-cascades-for-gravity)
- [Related shaders that are not RC](#related-shaders-that-are-not-rc)
  - [McSyWm (Suslik): sRGB against linear averaging](#mcsywm-suslik-srgb-against-linear-averaging)
  - [3tdSDj (iq): distance to a segment](#3tdsdj-iq-distance-to-a-segment)
  - [fld3R4 (paniq): 2D light propagation volume](#fld3r4-paniq-2d-light-propagation-volume)
  - [7c2XDw and 7f2SzV (Suslik): sweeping and diffusion tests](#7c2xdw-and-7f2szv-suslik-sweeping-and-diffusion-tests)
  - [XXVfW3 (fb01): a per-pixel gather without cascades](#xxvfw3-fb01-a-per-pixel-gather-without-cascades)
  - [MsV3zR (FabriceNeyret2): a max pyramid](#msv3zr-fabriceneyret2-a-max-pyramid)
  - [sXcGRB (SpinningCube): two-way horizon map shadows](#sxcgrb-spinningcube-two-way-horizon-map-shadows)

## Holographic cascades

### 4ctczl (Suslik): two families of probe lines

Forked from 4ctXD8. It uses HRC's line structure but not its extension step.

- Four levels. Level `n` has lines spaced `2^n` times the base spacing (512 lines across at level 0), a constant probe spacing along each line, and `D_n = 8·2^n` directions uniform over 360°, offset by −45° (Common:30-32, 88-90, 231-236). Directions double per level instead of quadrupling.
- Two families: directions within 45° of horizontal live on vertical lines and the rest on horizontal lines (Common:111-115). For `D = 8`, family 0 is −22.5°, 22.5°, 157.5° and 202.5°. Each (line, probe) holds `D/2` intervals per family, `2^21` per level on a square view (derived).
- Merge (Cube A:54-112): each interval takes 16 sub-steps. Each sub-step slides the origin across the probe's cell and picks a fractional direction, then finds where its ray meets the next level's line and interpolates linearly between two neighboring level `n+1` directions and along that line. The near segment runs from the origin to the crossing; the top level uses 1000 px rays with no far term. The 16 results are averaged with equal weights, with no angular weights. The comment above the origin slide says nobody knows why it works.
- Every interval marches to the next level's line, which is top-down RC on HRC-like geometry with no extension.
- Gather: for each of 8 level-0 directions, interpolate the nearest line's interval; output `1.5 ×` the mean, tone mapped.
- One level per frame through the cube map's previous frame, so about three frames of lag. Inactive: three other merge variants (`CastMergedInterval`, `CastMergedIntervalExtended`, `CastMergedIntervalNumericalFast`), a slower gather, the sky integral, and a Dolkar miss-handling variant.

### tfKyRw (youssef_afella): one frustum with paper geometry

- Eleven levels (0 to 10) for one 90° frustum facing +x. Level `n` has planes `2^n` px apart with one probe per pixel row, and rays `(2^n, 2k − 2^n)` for `k = 0…2^n`: the paper's `2^n + 1` rays spanning slopes −1 to 1 (Common:62-63, 103-107). Each texel is one cone between neighboring rays, so every level is a full-viewport texture.
- Cone weights come from angles: with `mid` the average of the two rays, `w1 = angle(ray1, mid)/angle(ray1, ray2)` and `w2 = 1 − w1` (Common:82-94). Level 0 gives 0.5 and 0.5; level 1 cone 0 gives about 0.41 and 0.59. Each ray is weighted by the angular width of its half of the cone.
- Merge (Common:97-159): each ray marches its full length and, unless it hit, composites level `n+1` at its far end. Odd planes read one sample on the next level's plane. Even planes march twice the length and average two samples, which the code calls a fix for discontinuous rays on even planes. No ray is built from two shorter rays, so the extension step is absent, and the cross-level merge has no angular weights.
- Buffers A to C compute three levels each over a three-frame ring (10/9/8, 7/6/5, 4/3/2), Buffer D level 1, and Image level 0 every frame, so levels refresh every three frames and the image lags about two frames while mixing times across levels. The author accepts losing about two thirds of the frame rate and states the ideal as one pass from the top level to level 0.
- The scene is a pulsing white light behind a black occluder, sphere traced for 32 steps; misses are black. There is no sky, no frustum rotation and no division by the frustum count. Output is linear radiance with an sRGB encode.

### WfyyDm (youssef_afella): four frustums in one buffer

"HRC 2D GI" (2025-12-03) recreates the HRC paper's figure, and its comment calls tfKyRw a simpler version of it. It shares tfKyRw's cone weights, doubled even-plane rays, two-sample even-plane average, buffer ring and sRGB encode, and like it has no extension step.

- Four 90° frustums (toward −x, +x, −y and +y) at half resolution, stored as the four quadrants of each buffer; the author says full resolution would need about 40 dispatches (Common:8, 229-233).
- Ten levels. Level `n` has planes `2^n` px apart with one probe per lateral pixel row and `2^n` cones per probe, each cone between rays `(L, 2k − L)` and `(L, 2k + 2 − L)` with `L = 2^n`, spanning ±45° (Common:112-158). Odd-plane rays reach the next parent plane (length `L` to `√2·L`) and read one nearest parent texel; even-plane rays are twice as long and average two parent samples (Common:169-211). Ray `i` of cone `c` reads parent cone `2c + i`.
- Cone weights are each ray's angle to the cone's chord midpoint over the angle between the rays: 0.5 and 0.5 at level 0, 0.41 and 0.59 for level 1 cone 0 (Common:127-143). The first and last rays of a frustum have their direct hits scaled by `0.5/L + 0.5` before the merge, so light merged onto them is not scaled (Common:174-178).
- Schedule: Buffers A to C compute levels 9/8/7, 6/5/4 and 3/2/1 over a three-frame ring, and Buffer D computes level 0 on the third frame and holds it otherwise; levels 6 and 3 read the level above from the previous frame. Level 0 is 0 to 2 frames old on screen and level 9's light 2 to 4 frames old, while the ball overlay updates every frame (inference from the schedule). The author accepts losing two thirds of the frame rate.
- Image averages the four quadrants with weight 0.25, which at level 0 averages four diagonal rays (inference). The scene is 80 emissive balls on a spiral (angle step 2.3067 rad, not the golden angle), sphere traced for 32 steps, with no sky or tone map and an sRGB encode.
- Read from the code: planes at multiples of `2^n` own `2^n` cones, so when the quadrant width is not a multiple of `2^n` the last plane is partial and its high cones are never stored, which matches the author's note about problems at non-power-of-two resolutions; the spiral takes the square root of a negative number for inner balls when its time term is large; and an odd-width buffer puts its last column in the wrong frustum.

## NfVXRc and sfVSzd (Suslik): extended gathering

Both fork the 4ctXD8 framework with one live cascade: 512 probes across, spaced `W/512`, each with 8 directions at `(k + 0.5)·45°` (Common:4, 33-35). Nothing merges: `MergeIntervals` is never called and three of the six listed `MERGE_FIX` modes change no code.

- **NfVXRc** traces every probe direction over `[0.12·W, 0.18·W]` (scale `(80, 120)` times `0.0015·W`) each frame. The image pass gathers `N = 200` directions per pixel (8 while the mouse is held): each gather direction's sample point lies 120 px from the pixel, and for the two stored directions that bracket it, the source probe sits at the sample point minus that direction times 120 px; four probes around it are read bilinearly and the two directions weighted linearly (Image:70-112). The gather radius is a fixed 120 px while the trace ends at `0.18·W`, which match only at a width of about 667 px.
- **sfVSzd** moves the angular smoothing into the cube pass: even frames trace over `[0.075·W, 0.18·W]`, odd frames replace each texel by 200 samples over one direction spacing on each side of its own direction, with source probes on circles of radius `R = 0.18·W` around the sample points (Cube A:96-136). A final pass sums the 8 stored directions over four bilinear probes. The ring gather declares a second `probe_location` that shadows the outer one, leaving its cascade index uninitialized (Cube A:122-127). The mouse state chooses whether the trace-only or the gathered frames are shown.
- `MERGE_FIX 3` (Dolkar) returns zero instead of the origin's emission when a ray starts inside a shape; the outer and inner parallax modes only stretch the trace end by 1.1. `intersect()` clips rays to the screen without adding the clip offset back, so rays that start off screen sample short of the hit. The sky integral is defined and never called.

## Media and transmittance

### wfyyDz (codyjbennett): 2D volumetric cascades with the bilinear fix

- Six levels with probe spacing `2^c` px, `4^c` directions and intervals `0.2·[4^c, 4^(c+1)]` px, so level 0 has a single direction pointing left (Common:106-120). Each probe owns a `2^c × 2^c` block of texels.
- Casts sample `16·2^c` evenly spaced points; each adds `rgb·T·a` and multiplies `T` by `1 − a` (Common:63-79). The opacity applies per sample, not per length, so the same absorber attenuates differently on each level and in each of the four bilinear-fix casts, whose step lengths differ (derived).
- The bilinear fix casts from `probe + dir·start` to `upper_b + dir·end` for each of four upper probes, reads that probe's four child directions, merges, weights bilinearly and averages (Common:141-174).
- Three emitters and absorbers move with time and are drawn at twice their radius; there is no sky. The radiance accumulator starts with alpha 1, so stored alpha is not a transmittance at levels below the top, though the displayed color does not depend on it.
- Buffers A to C alternate between levels 5/4/3 and 2/1/0, so the chain refreshes every two frames. Output: exposure ×2, ACES fit, sRGB. The author calls the bilinear fix a nonphysical trick that hides ringing, and suggests HRC to keep shadow edges sharp.

### ffl3Rf (codyjbennett): hardware bilinear without the fix

"2D RC with Hardware Bilinear" (2026-03-10) forks wfyyDz and is NfySzt's parent. Its description still advertises volumetrics and a four-ray bilinear fix; the code has no bilinear fix.

- The pass graph, the two-frame schedule (levels 5/4/3 on even frames and 2/1/0 on odd frames), the intervals `0.2·[4^c, 4^(c+1)]` px with `16 << c` steps, the scene and the Image pass are wfyyDz's.
- The layout becomes direction-major: each direction is a tile holding that direction for every probe (Common:85-94). The merge reads each of the four upper directions `4·dir + i` with one `texture()` call, which the comment calls a bilinear sampler, clamped to the upper grid, and averages the four (Common:112-127). One filtered read per direction replaces wfyyDz's manual four-probe blend, which that shader's author wrote because float linear filtering is unreliable on some targets (wfyyDz Common:145-146).
- `texture()` takes its mip level from screen-space derivatives, which jump at tile boundaries; NfySzt pins level 0 with `textureLod` (inference; the channel's mip setting is not in the code).
- Shared with wfyyDz, read from the code: the disc test `distance − r < r` draws discs at twice their radius (Common:34); the absorber removes 1 % per sample whatever the step length, an optical depth of about 0.20 per pixel at level 0 and 0.008 at level 5, a factor of about 24 (derived); samples sit at step starts, so interval ends are never sampled; and on resolutions that are not multiples of the spacing the coarse levels misplace probes, by up to about 24 px at level 4 of 1280×720.

### NfySzt (codyjbennett): hardware bilinear upper fetches

Labeled elsewhere as a refraction fix, this shader has no refraction and no angle correction. It keeps wfyyDz's pass graph, two-frame schedule and intervals, and changes the rest:

- The scene is an opaque blocker of radius 50 and one pulsing emitter, intersected analytically per ray and clipped to the interval; a blocker hit stores 0 and skips the merge (Common:52-132).
- The layout is direction-major: each direction is one tile of the probe grid (Common:109-119).
- A miss adds a quarter of the sum of four upper directions, each one hardware-bilinear fetch at the upper position, clamped so the filter stays inside its tile (Common:138-153). There is no bilinear fix and no sky.
- Compared with ffl3Rf, its parent, it keeps the passes, schedule, constants, intervals, direction-major tiles and four-direction hardware fetch (now `textureLod` at level 0), and replaces the marched scene with analytic circles at their nominal radius, half the drawn size of the parent's discs.
- With binary hits its three-way branch equals the parent's merge: an emitter hit returns 1, a blocker hit 0 and a miss the mean of four upper samples (derived). The level-5 sky branch is empty and the stored alpha is fixed at 1.
- Probe positions go through `probeUV·resolution`, which keeps the levels aligned with each other on resolutions that are not multiples of the spacing but stretches them in pixels (Common:60, 122, 142).

## 3D and screen space

### M3ycWt (Mathis): voxel cascades with hemisphere probes

"Volumetric" here means a voxel volume; there are no participating media.

- A procedural 32×32×48 voxel room (columns, arches, cloth, a fountain lamp, a partial roof, a moving floor emitter and a moving sphere), rebuilt each frame, traced by voxel DDA for up to 128 steps. A sun shadow map stores the distance to the first solid voxel along the sun.
- Five levels with probe grids from 32×32×48 (spacing 1) to 2×2×3 (spacing 16). Each probe has six hemispheres, one per face normal. Level `L` uses an `s×s` grid per hemisphere with `s = 3·2^L`: level 0 has the normal plus 8 directions at 45°, and higher levels use concentric square rings with polar angle `(ring/s)·π` and `4 + 8k` azimuth bins per ring (Common:96-121). Each texel stores radiance times solid angle over `2π` times `cos θ`; `w` holds the hit distance (1e7 for sky, −1 for an invalid probe).
- Level 0 traces from every empty voxel, 0.25 voxels off each face; coarser levels move the probe toward an empty fine voxel by ±0.05 per axis.
- There are no intervals: every ray runs to its first hit. A hit distance `t` keeps the probe's own value below `2^L` voxels, hands over to the parent beyond `3·2^L`, and blends linearly between (Cube A:258-259).
- The parent value blends eight parent probes trilinearly. For each, the parent hemisphere facing the child is read in the one direction pointing at the child; if that stored distance is shorter than the offset minus 0.5, the parent counts as occluded and its weight drops to `10^−5` (Cube A:44-103). This is the same visibility test as X3XfRM's.
- Hits add the shadowed sun and last frame's level-0 irradiance in front of the hit, times albedo, so each frame adds a bounce and level 4 reaches level 0 in about four frames. The camera pass sums nine level-0 texels in front of the hit, adds the sun, multiplies by albedo, and applies an ACES fit and a 0.45 power.
- Findings from the code: level 0's direction weights use uncentered grid coordinates, so the zenith texel gets a ring weight of 0.088 and a corner texel the center weight of 0.293; stored values weighted by solid angle over `2π` make the indirect term half of Lambert's `E/π` while the sun term has no `1/π` at all; the visibility test uses the parent's nominal position rather than its nudged one; `BRDF_GGX` is defined and never called.

### lXByRh (Mathis): screen-space probes merged by hit-point reprojection

"RC - Screen Space Probes" (2024-12-16) places hemispherical probes on a half-resolution G-buffer and merges each cascade from the next coarser one by reprojecting the coarser rays' hit points into the finer probe with a visibility test, instead of compositing intervals. Its only smoothing is temporal; the comments say there is no spatial denoising and some flicker remains (Image:2-25).

- Six cascades in the top and bottom halves of Buffers B, C and D (cascades 2 and 5, 1 and 4, 0 and 3). Cascade `n` tiles the half-resolution G-buffer into probes of `P × P` texels with `P = 2^(n+1)`, one texel per direction, so every cascade traces about one ray per half-resolution texel.

| Cascade | Probe tile (half-res texels) | Spacing (px) | Directions | Polar angles of texel centers |
|---|---|---|---|---|
| 0 | 2 | 4 | 4 | 45° |
| 1 | 4 | 8 | 16 | 22.5° to 67.5° |
| 2 | 8 | 16 | 64 | 11.25° to 78.75° |
| 3 | 16 | 32 | 256 | 5.63° to 84.38° |
| 4 | 32 | 64 | 1024 | 2.81° to 87.19° |
| 5 | 64 | 128 | 4096 | 1.41° to 88.59° |

- Directions cover the hemisphere around the pixel normal: texel ring `r` (Chebyshev distance from the tile center) sits at polar angle `(r + 0.5)·π/P` with `8r + 4` evenly spread azimuths. The map is not octahedral, equal-area or cosine-weighted (Common:398-429); it and its inverse round-trip exactly for `P` from 2 to 64 (checked with a port of the code).
- There are no intervals: every ray runs to its first hit, up to 1e6 (Buffer B:65). A hit stores sun light through a shadow ray times albedo, and a miss stores sky radiance at distance 1e6.
- Merge (Buffer B:3-110): each texel picks the four upper probes around its own screen position with bilinear weights. For each, it projects its direction into the upper tile and scans a 5×5 window of upper texels. Each upper hit point (upper probe position plus direction times stored distance) is re-expressed from the current probe and kept if it falls in the current texel's direction bin and is not hidden by the texel's own nearer hit within a visibility window. Kept samples are averaged per probe, weighted by a normal ramp (cosine 0.8 to 1) and a plane test (0.02) floored at 0.001, and combined by the bilinear weights. If the total weight passes 0.0005, the texel's radiance is replaced by the result while its distance stays its own: the merge is a replacement, not `near + near.a·far`.
- After a merge a texel pairs upper radiance with its own hit distance, and the next cascade down rebuilds a hit point from that pair, so the position and the radiance come from different rays (inference). The comments say scattering would beat the 5×5 gather but may be slower.
- The visibility window is 8 times the world size of half a tile at the probe's depth `d`, about `2^(n+3)·d/H_half`: 0.015·d at cascade 0 and 0.47·d at cascade 5 for 540 half-resolution rows. The code builds it with the full-resolution reciprocal on half-resolution coordinates, which halves it (Common:391-395, inference).
- Temporal: a cube-map pass reprojects each pixel's world hit point into the camera of two frames earlier and blends `(old·count + new)/(count + 1)` with the count capped at 15, a 16-frame window that matches the 16-frame period of the probe jitter. History is rejected by normal (0.5) and plane (0.05) tests, with no colour clamp. The top bands read the previous frame's G-buffer and camera, so the displayed image is a frame old and no single frame is correct by itself (Cube A:88-127, Buffer B:48-56).
- The final pass shades half-resolution pixels with the cube's irradiance from the four nearest cascade 0 probes (the mean of their four 45° texels, with no cosine weighting and no `1/π`) plus direct sun, times albedo: one bounce. Output is an ACES fit, then a 0.45 power.
- Read from the code: the probe jitter has no tile index, so every probe in a band moves together, unlike the comment's random placement; the tilted slab's face normals are rotated back by −0.9 rad instead of −1.08 rad, about 10° off; `info.n *= −dot(info.n, d)` scales the normal instead of flipping it; the merge gate (0.0005) sits below the weight floor (0.001), so any accepted sample replaces the radiance; the emissive branches need albedo above 1 and never run; and Image binds Buffers B and D without reading them. The comments add that samples are not BRDF weighted, that visibility is naive, and ask whether stochastic probes can be dropped.

### scy3Dd (codyjbennett): SPWI in one shader

Screen-space probes with world-space intervals (SPWI), six cascades over two frames.

| Cascade | Probe spacing (px) | Directions per probe | Interval (world units) |
|---|---|---|---|
| 0 | 4 | 16 | 0.006 to 0.030 |
| 1 | 8 | 64 | 0.030 to 0.102 |
| 2 | 16 | 256 | 0.102 to 0.390 |
| 3 | 32 | 1,024 | 0.390 to 1.542 |
| 4 | 64 | 4,096 | 1.542 to 6.150 |
| 5 | 128 | 16,384 | 6.150 to 24.582 |

- Intervals are `[s(N), s(N+1)]·0.006` with `s(0) = 1` and `s(N) = 4^N + 1`. Directions per axis equal the probe spacing in pixels, so a direction-major atlas exactly fills one resolution-sized texture per cascade, which holds only for the 4 px base spacing. Directions use the equal-area octahedral map at cell centers.
- The scene is an emissive unit cube colored by its face normals above a floor, traced analytically. Each probe reads one depth at its cell center; there is no G-buffer and no min/max. A non-emissive hit counts as a miss, so the floor neither blocks nor emits.
- Merge: Bilinear3D, from 4XXSWS, iterates four times to find the ratio at which the four upper probes' world positions best interpolate the probe's own position. The bilinear fix then traces from `probe + dir·lo` to each upper probe's `upper + dir·hi`, averages that probe's four child directions with weights 0.25 each, and weights by the 3D ratio.
- Gather: the 16 cascade 0 directions, each read by a hardware-bilinear fetch at the 3D ratio and weighted by `max(0, n·dir)`, divided by the sum of cosines, plus a cascade −1 contact trace over `[0, 0.006]` per pixel. Output: albedo times radiance, exposure ×2, ACES fit, sRGB.
- Buffers A to C compute cascades 5/4/3 and 2/1/0 on alternate frames, and both frames of a pair use one camera time, so the image refreshes every other frame.
- Comments name what is left out: min/max depth probes (which fix bilateral flicker but need binning or temporal data), discontinuity-aware interpolation, the parallax fix, holographic cascades, and split-sum specular from the interpolated intervals.
- Defects from the code: the G-buffer trace starts at the near-plane point but adds its distance to the camera origin, so reconstructed hits sit roughly `0.1/cos θ` too close to the camera; the gather's hardware-bilinear fetch clamps only the base probe, so the last probe column of a direction tile can blend in the next tile's first probe.

### 33ycDm (youssef_afella): GTAO from cascaded horizons

- Three effective levels (a fourth buffer returns −1 and is never read), all from the current frame. Level `n` has origins every `2^n` px and `4^(n+1)` directions, 45° apart at level 0, 22.5° at level 1 and 5.625° at level 2. The radial intervals are `[4^n − 1, 4^(n+1) − 1]·0.1/63` in UV, divided by `1 + depth`, with 2, 4 and 4 samples.
- Each direction keeps the maximum cosine to the view vector over its samples, minus twice a falloff that starts at 0.1 view units. The merge takes `max(own, parent − w)`, where the parent is the bilinear mean of the four child horizons of block `4b + i` and `w = 2·clamp(|Δdepth|, 0, 1)`. The author notes the depth weight should be applied per probe, not to an average.
- The image pass converts level 0's four horizons into two GTAO slices along the diagonals, clamps them to the normal's hemisphere and evaluates GTAO's per-slice integral. A camera-facing open surface gives exactly 1.
- The author calls it noiseless and full of artifacts, and still needing depth-aware merging and upsampling. Taking the maximum horizon per interval and across levels is the HBAO step; the result approximates GTAO with two slices, two to four samples per ray and averaged horizons.

## Depth-aware upscaling and occlusion

### 4XXSWS (Suslik): depth-aware upscaling

A test of upscaling a 1/8-resolution buffer of `(color, depth)` to full resolution, with four panels: plain bilinear, reference, bilateral, and "bilinear 3D". three-rc ports it for screen-space probes.

- Bilateral: weight each of the four neighbors by `bilinear_i·exp(−100·|depth_i − depth|)` and normalize.
- Bilinear 3D: rebuild the four neighbors' world points `P_i` from their depths and the target point `Q`. Starting from the plain bilinear ratio, run two iterations that alternate solving `ratio.x` and `ratio.y` by projecting `Q` onto the line between the two edge points interpolated at the other ratio (`ProjectLinePerp(A, B, p) = dot(p − A, B − A)/dot(B − A, B − A)`, saturated). The final bilinear weights at that ratio sum to 1, so no normalization is needed, and they follow the actual surface instead of rejecting samples. scy3Dd runs four iterations.
- There is no guard against zero-length edges or a zero total bilateral weight.

### MXjcWK (Suslik): selective bilinear subsets

Quadrants show hardware linear, reference, bilateral (`exp(−100·|Δd|)` as in 4XXSWS), and a selective method on an Apollonian fractal at 1/8 resolution. The selective method keeps the 2D bilinear ratio, tries the 15 non-empty subsets of the four taps with the bilinear weights masked to the subset and renormalized, and keeps the subset whose weighted world point lands closest to the full-resolution point. It chooses among discrete subsets rather than solving a continuous 3D ratio; comments describing continuous coefficients and Newton iterations do not match the code, and a variant blending subsets by inverse squared distance is never called.

### 4cffDX (mxcop): normal- and depth-weighted upsampling

Four boxes shaded at one sample per 16×16 cell and upsampled with full-resolution depth and normals. Each tap's weight is its bilinear weight times `clamp(1.5·dot(N, N_i), 0, 1)`; when the spread of the four tap depths exceeds 20% of their mean, each weight is also multiplied by `1/(|d_i − d| + 10^−4)`. Weights are normalized without a guard, so four taps facing away divide by zero. Depth is ray distance, not view depth.

### ffSSz1 (Suslik): linear min/max interpolation

"Basic Minmax Interpolation" (2026-04-15) forks NfSXRh ("Perspective interpolation tests") and is NfBSz1's parent; both describe themselves as deliberately simple and slow demos.

- For each 8×8 cell, all 64 full-resolution samples are traced, and the cell stores the minimum and maximum depth with the red radiance at each (Buffer A:11-37). The image blends the four nearest cells bilinearly in all four channels, then outputs `mix(R_min, R_max, saturate((d − d_min)/(d_max − d_min)))` with the full-resolution depth `d` (Image:12-25). Everything is linear; there is no `1/d` step.
- The scene is an Apollonian fractal sphere traced for 128 steps, shaded by albedo times an orbit-trap AO times 0.9 with fog `exp(−0.1·t)`; depth is ray distance (Common:68-160).
- Shared with NfBSz1, read from the code: flat cells with `d_max = d_min` divide by zero; neighbour indices are not clamped at the border; a shadow ray and a normal are computed and never used; and the camera uses 3.1315 where π is likely meant (Common:168).

### NfBSz1 (Suslik): perspective-correct min/max interpolation

- Cells are 8×8 px (a comment says 32×32). For each cell, 256 full-resolution samples around the center give the minimum and maximum depth, and the cell stores `(dmin, dmax, xmin, xmax)`, where `x` is the world x of the center ray at those depths. A tent weight is computed and not applied.
- The image interpolates `1/d` bilinearly: `dmin' = Σw/Σ(w/dmin_i)`, and `xmin' = Σ(w·xmin_i/dmin_i)/Σ(w/dmin_i)`, likewise for max. Then `t = clamp((d − dmin')/(dmax' − dmin'), 0, 1)` and the output mixes `xmin'` and `xmax'` by `t`. Nothing guards `dmax' = dmin'`.
- The test shows `fract(10·x)` of the interpolated world x against the full-resolution x when the mouse is held, so errors show as broken stripes. There is no error metric, and a ratio-first variant is not in the code.
- Compared with ffSSz1, it widens the window from 8×8 aligned samples to 16×16 centered ones, which reach 4 px into neighbouring cells, stores world x instead of radiance, and blends the endpoints in `1/d` while `t` stays linear in depth. Depth is ray length rather than view z, so the blend is perspective-correct only approximately (inference). Buffer A binds its own output, which only an uncalled `mainImage_experimental` reads.

### l3scz8 (Suslik): occlusion from depth variance

A closed-form test for moment-based depth marching. With a fixed interval `I = [a, b]`, a sample interval of half-width `s` centered at `m`, and a uniform offset on `[−h, h]` with `h = √3·σ` (variance `σ²`), the probability that a point is covered is a trapezoid: `c = |s − h|`, `l = 2·min(s, h)`, height `min(1, s/h)`, `T(x) = H·clamp(1 − (|x − m| − c)/l, 0, 1)`. Its antiderivative gives the mean overlap `O = (F(b) − F(a))/(b − a)` exactly, which the shader checks against a 100-step brute-force sum. The offset is uniform, so only its variance enters, and a Gaussian with the same variance would differ. The comments target SSGI and SSAO from a prefiltered buffer of depth and depth squared; the Chebyshev bound that the tags suggest is not in the code.

## XcB3Ry and MfS3Wm (Suslik): cascades for gravity

A gravitational fluid simulation that uses the cascade hierarchy for an N-body field; XcB3Ry's header names mlSfRD as its RC reference. Both store everything in one viewport-sized texture: the left half holds matter (impulse, density, color) and the right half acceleration, each split into cascades stacked vertically with `(W/2 >> k) × (H/2 >> k)` cells.

- **XcB3Ry** (six cascades, scaling factor 4): level `k` of the matter field is the 2×2 average of level `k − 1`. Level `k` of the gravity field sums `density·4^k·Δ/|Δ|³` (Newton with `G = 1`, no softening) over sources whose distance lies in `((4^(k−1) or 0) + 1, 4^k + 1)·5.1` base pixels, with linear fades of width `2·(2^k, 2^(k+1))` at both band edges, and then adds the bilinear sample of level `k + 1` from the previous frame. So each level holds its own band plus everything coarser, the RC merge, and far fields arrive over frames. Matter advects by scattering each source within radius 10 to its moved position with tent weights. Mass and momentum are conserved, energy is not. The mouse adds mass and impulse; space or the first ten frames reseed about 250 orbiting blobs.
- **MfS3Wm**, the earlier version (seven cascades, factor 2, base distance 15): hard bands `[2^(k−1), 2^k)·15` and the coarser-level accumulation commented out, so each level holds only its own band.
- The scheme carries over to any long-range field whose needed resolution falls with distance.

## Related shaders that are not RC

### McSyWm (Suslik): sRGB against linear averaging

Two cosine-driven colors alternate in rows on the left (a checkerboard with `USE_CHECKERBOARD 1`). The top right shows their average taken on sRGB-encoded values, the bottom right the average taken after a 2.2 power and re-encoded. With black and white (mouse held), the encoded average is 0.5 (128 of 255) and the linear one encodes to 0.730 (186 of 255). The author asks why the checkerboard looks worse than lines. RC merges average many values, so the same rule applies to them: average linear radiance.

### 3tdSDj (iq): distance to a segment

MIT-licensed. The function is `udSegment`: `h = clamp(dot(pa, ba)/dot(ba, ba), 0, 1)` and the distance `|pa − h·ba|`. The demo subtracts a breathing radius to make a capsule and draws a ring of the distance around the mouse. Copies in RC shaders call it `sdSegment`, though it is unsigned.

### fld3R4 (paniq): 2D light propagation volume

Labeled elsewhere as a frustum sweep with angular falloff and Gaussian penumbras; the code is a 2D light propagation volume with none of those.

- Each pixel is a cell holding order-1 circular harmonics (two directional terms and a constant, basis `√((2, 2, 1)/2π)`), one buffer per color channel.
- Each frame, a cell gathers from its four neighbors through three lobes per neighbor: one along the face normal with solid angle `acos(3/5) ≈ 53.13°` and two tilted ones of `acos(3/√10) ≈ 18.43°`, which sum to 90° per neighbor, 12 terms in all. For each lobe, the arriving light `L` and the neighbor's occupancy `E` (from an SDF-derived opacity, 0.5 on the surface) give transmitted light `L·(1 − min(E, 1))` plus a reflection `min(E, 1)·L·albedo`, or `albedo·E` for emitters at a surface.
- Light moves one cell per frame through each buffer's previous frame, so it needs many frames to cross the screen. The inputs are declared as 8-bit, which would clip negative harmonics and the emitters' 20× radiance if that is the storage format. A strip on the right ray-marches a rotated 1D view of the scene. Output: ACES fit, exact sRGB.

### 7c2XDw and 7f2SzV (Suslik): sweeping and diffusion tests

Linked elsewhere for angular falloff and Gaussian penumbras; neither shader has them.

- **7c2XDw:** a scan column moves one pixel per frame. Two carrier columns move one row up and one row down per frame from each single-pixel source, so they cross the scan at 45°, and an accumulator writes the column into the image: a 90° wedge from each source. There are no cascades and no per-level occluder counts. Negative values paint red as a check.
- **7f2SzV:** each frame, every non-source pixel takes the mean of three taps one column to the left at offsets `−δ, 0, +δ` rows, with `δ = 2·mouse.y/H` (0 until the mouse moves). Light spreads to the right in a cone of half-angle `atan δ` through a gap in a wall. The kernel is a box; repeated over many columns it approaches a Gaussian, but the code has no Gaussian term.

### XXVfW3 (fb01): a per-pixel gather without cascades

"clunky cascade fb01" (2025-02-04) carries the radiancecascade tag but has no cascades, probes, intervals or merge. One pass simulates 27 shapes (balls, blocks, triangles and ovals) moving on triangle-wave paths with three collision passes, recomputed in every pixel, and each pixel averages 50 rays sphere-traced for at most six steps up to `t = 4`, with misses black and an ACES fit. It keeps no state, so it has no lag.

### MsV3zR (FabriceNeyret2): a max pyramid

"pyramid op" (2016-01-18) builds a pyramid of 2×2 maxima of the webcam image in one buffer, one level per frame, and divides the image by the top value to normalize brightness. It shares only the stack of resolution levels with RC.

### sXcGRB (SpinningCube): two-way horizon map shadows

Linked elsewhere for isometric terrain; the shader has no isometric view. For each heightmap pixel, a row scan stores the steepest slope toward +x and toward −x (`O(W)` per pixel, cached until the resolution changes). The sun moves overhead along x with a 0.2 rad disc, and visibility is the visible fraction of that disc above each horizon, from the area of a circular segment, combined as east plus west minus one. Ambient occlusion is `0.5 + 0.5·cos(atan(east) + atan(west))`, blended in at 1%. There is no horizon along y.
