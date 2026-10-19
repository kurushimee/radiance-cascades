# Radiance Cascades: GM Shaders series and companion repository

| | |
|---|---|
| Author | Alex (Yaazarai) and Xor (@xordev), GM Shaders guest series. Repository by Yaazarai (Alex). |
| Date | Part One: Apr 13, 2024. Part Two: Jul 13, 2024. Repository: not captured. |
| Kind | Two-part article series, plus a GameMaker repository (Unlicense). |
| Link | https://mini.gmshaders.com/p/radiance-cascades (Part One); https://mini.gmshaders.com/p/radiance-cascades2 (Part Two); https://github.com/Yaazarai/GMShaders-Radiance-Cascades (repository) |

Part One is an introduction to Radiance Cascades (RC) in 2D: the penumbra hypothesis, the cascade layout, the cascade count, interval math, merging, and the screen-space output. Part Two covers optimizations (pre-averaging and a direction-first layout), walks through the GameMaker shader code, and gives frame times. The repository holds the GameMaker projects behind both posts: a position-first version, a direction-first version with several merge variants, and a visual demo.

## Notation

The symbols below are labels for these notes; the sources do not use them.

| Symbol | Meaning |
|---|---|
| c, i | Cascade index. 0 is the finest cascade. |
| L0 | Probe spacing of cascade 0, in pixels. |
| L_c | Probe spacing of cascade c. L_c = L0 * 2^c per axis, as the code uses. Part Two's text also describes a "4x" per cascade, which matches the code only in area (see inconsistencies). |
| I0 | Interval (ray length) of cascade 0, in pixels. |
| off_c | Interval start of cascade c = I0 * (4^c - 1) / 3. |
| len_c | Interval length of cascade c = I0 * 4^c, before any overlap term. |
| E | Side of a cascade texture, in texels. Cascade textures are square in the position-first version and E_x by E_y in the direction-first version. |
| A | Angular resolution of cascade 0 in rays per probe (position-first). |
| TAU | 2 * pi. |

---

## Part One: Introduction to Radiance Cascades

| | |
|---|---|
| Author | Xor and Alex |
| Date | Apr 13, 2024 |
| Kind | Article (GM Shaders guest post, part one of two) |
| Link | https://mini.gmshaders.com/p/radiance-cascades |

The post introduces RC as a structured alternative to random ray sampling. It explains the penumbra hypothesis and how it sets the cascade layout. It gives the interval math, the merge step, and how the cascade 0 result becomes a screen-space radiance field. It gives no complete shader; the code it shows is short fragments.

### Overview claims

- The method casts a few short rays from each probe at the first cascade. Each later cascade has 4x the rays and 1/4 the probes (half the width and half the height).
- The post says the usual starting count is 4 directions. Its layout example uses 64 rays per probe in cascade 0 (see the inconsistencies section).
- The author states the method has occasional light leaks and non-linear attenuation transitions, and that it is still under active development.
- The author states the description covers one specific implementation.

### Penumbra hypothesis

- Stated rule: a penumbra needs higher linear resolution (more probes) near the light and higher angular resolution (more rays per probe) further from the light.
- Linear resolution is the number of sample points. Angular resolution is the number of ray directions per point.
- The two are inversely proportional, so the method can trade one for the other.

### Cascade layout

- Each cascade has N probes, and each probe emits R rays.
- Cascade 0 has the most probes and the fewest rays. Each cascade up has 1/4 the probes and 4x the rays.
- The 4x scaling is stated as optimal for 2D, chosen by Sannikov. It is not presented as a hard rule.
- With 4x scaling, all cascades stay the same size in memory, since probes times rays is constant.
- The 2D texture scales by 2 per axis (4 in area). The rays of one probe are a 1D list mapped into a 2D tile, so 4x rays means 2x per axis.

Example layout given in the post (1024 x 1024 scene):

| Cascade | Probes | Rays per probe | Total probes | Total rays |
|---|---|---|---|---|
| 0 | 16 x 16 | 8 x 8 (64) | 256 | 16,384 |
| 1 | 8 x 8 | 16 x 16 (256) | 64 | 16,384 |
| 2 | 4 x 4 | 32 x 32 (1024) | 16 | 16,384 |
| 3 | 2 x 2 | 64 x 64 (4096) | 4 | 16,384 |

- Cascade 0 probe spacing in this example: 1024 / 16 = 64 pixels.
- The post says each probe is evenly spaced to fit the scene size.
- Probe spacing and angular layout for each cascade are given as above; the post does not give an explicit texture size for this example (derived: the tile grid gives 128 x 128 texels for every cascade).

### Cascade count

The post gives this procedure:

1. diagonal = sqrt(width^2 + height^2)
2. factor = ceil(log4(diagonal / interval0))
3. intervalstart = interval0 * (1 - 4^factor) / (1 - 4)
4. cascadeCount = ceil(log4(intervalstart)) - 1

- The idea: stop adding cascades once the interval start passes the screen diagonal, since rays past the diagonal see nothing on screen.
- Example from the post: a 1920 x 1080 screen has a diagonal of about 2203 px. The post does not give interval0 for this example, so the resulting count is not stated.

### Raymarching from probes (index math)

Ray index and angle, as the post writes them:

    probeX = pixel.x % probeWidth
    probeY = pixel.y % probeHeight
    ray_index = probeY * probeWidth + probeX
    ray_count = probeWidth * probeHeight
    ray_angle = ray_index / ray_count * PI * 2

- probeWidth and probeHeight are the tile size of one probe in pixels. Each tile is one probe, so this is the position-first layout.
- The post does not say whether ray_angle is sampled at bin centres or edges. It is the bin's left edge as written.

Interval origin and length:

    origin = (interval * (1 - 4^cascadeIndex)) / (1 - 4)
    length = interval * 4^cascadeIndex

- interval is the cascade 0 ray length.
- The origin moves 4x further out per cascade index. Derived: origin of cascade c+1 equals origin of cascade c plus length of cascade c, so the intervals are contiguous.

### Visibility term

The post's raymarch returns:

- Outside the scene: radiance 0, visibility 0.
- Hit a surface: scene colour, visibility 1.0 (the post's convention: 1.0 = hit).
- Interval finished with no hit: radiance 0, visibility 0.

The post then says rays are merged only when the visibility term is non-zero. Read with the convention just given, that merges rays that hit. The repository and Part Two merge rays that did not hit (see the inconsistencies section).

### Merging cascades

- Merge runs in reverse: cascade N-1 merges with N, down to cascade 0 merging with cascade 1. All radiance ends up in cascade 0.
- For a cascade N probe, the post finds the 4 nearest cascade N+1 probes. For the current ray, it matches the 4 rays in the same direction within each of those 4 probes.
- Bilinear weights come from the probe's position between the 4 N+1 probes.
- The post says the four matching rays are added up per probe (TL, TR, BL, BR), then bilinearly interpolated. The exact averaging is not written out (unclear in source).
- Figure 8 in the post illustrates this (image not captured).

### Screen-space radiance field

- Render target size: one pixel per cascade 0 probe. Call this the cascade 0 mip.
- Each mip pixel sums all rays of its probe. The total is divided by the ray count.
- The mip is drawn scaled up to the screen with hardware interpolation.
- Each cascade's mip can also be drawn for inspection.

### Extensions mentioned

- Sky: the sky integral is merged into the highest angular-resolution cascade. This leaves occlusion unchanged. Part Two's conclusion says it has no extras this time. The repository's sky and sun colours are commented out as pending.
- Volumetrics: the post credits Mytino with volumetrics through fluids, skybox integrals, and directional light bleeding into caves.
- Other uses listed: gravity simulation (Sannikov), 3D screen-space GI (Sannikov), volumetrics in high-viscosity fluids (Mytino).

### Limitations and reader comments

- Author statements: occasional light leaks and non-linear attenuation transitions; still in active research.
- Reader question (Sagie Levy, Nov 6, 2025): does it handle view-dependent specular GI, or only diffuse. The reply is hidden in the text.
- Reader question (hood233, Jan 7, 2025): visible interference patterns; asks why light's wavelength is absent from the algorithm. The reply is hidden in the text.

### Inconsistencies in Part One

- Overview says the usual start is 4 rays. The layout example uses 64 rays in cascade 0.
- Visibility convention: the raymarch text uses 1.0 = hit. The merge rule, read with that convention, merges rays that hit. The repository's original code uses 1.0 = hit as well, but its comments say the reverse. The optimized code uses 0 = hit.
- The raymarch snippet's out-of-bounds test writes `raypos >= 1.0` without a component. The x-axis test in the same line is `raypos.x < 0.0`, so the intent is `raypos.x >= 1.0`.
- The cascade-count procedure uses `intervalstart`. The repository does not use this formula (see the repository section).

---

## Part Two: Optimizations and Code Deep Dive

| | |
|---|---|
| Author | Alex and Xor |
| Date | Jul 13, 2024 |
| Kind | Article (GM Shaders guest post, part two of two) |
| Link | https://mini.gmshaders.com/p/radiance-cascades2 |

Part Two lists three problems with the Part One demo: complicated pipeline, no non-square support, and high memory and texture cost. It then describes two fixes (pre-averaging and a direction-first layout). It walks through a single merged shader pass, and reports frame times on an RTX 3080. It states that the direction-first layout is not faster after all, because of a GameMaker issue at the time. The conclusion still claims a speedup, which conflicts with that update.

### Problems listed in the overview

- Complicated: raymarch and merge were two shader passes. Merged into one pass (raymarch plus merge with N+1).
- Not dynamic: all math assumed square resolutions, including SDF generation. The new version enforces stricter size rules.
- Performance: no texture-cache ordering. The author argues GPUs read nearby texels faster, so storage order should follow access order.
- Memory: at 1024 x 1024, a 4-ray-per-probe layout is described as a "4K texture"; doubling probe density gives an "8K texture". The layout behind these numbers is not shown (unclear in source).

### Optimization 1: Pre-averaging

- Instead of storing each ray, cast 4 rays per cascade texel and store their average.
- Merge lookups drop from 16 (4 rays times 4 probes) to 4 texture lookups. Storage drops from one pixel per ray to one pixel per four rays: a 75 percent reduction in both.
- The post gives the merge as: find the 4 nearest N+1 probes; average each probe's 4 same-direction rays; interpolate by the probe's relative position.

### Optimization 2: Direction-first layout and hardware interpolation

- The original layout is "position first": each block is one probe, and each pixel in the block is one ray from that probe.
- The alternative "direction first": each block is one ray direction, and each pixel in the block is that direction's ray from one probe.
- Direction-first groups all rays with the same direction together. Then the four neighbouring N+1 probes sit next to each other in memory, so hardware linear filtering can blend them in one sample (16 samples become 1 with pre-averaging).
- Stated benefit: easier to debug, since rays of one direction are grouped.
- Update (in the post): direction-first is NOT actually faster. A GameMaker issue at the time affected performance. The layout is kept for debugging.

### Shader inputs (as in the post)

- in_TexelCoord (fragment texel position).
- in_RenderScene: lights and occluders.
- in_DistanceField: SDF of the scene.
- in_RenderExtent (vec2): render area size.
- in_CascadeExtent (vec2): cascade surface size.
- in_CascadeCount, in_CascadeIndex (float).
- in_CascadeLinear: cascade 0 probe spacing.
- in_CascadeInterval: cascade 0 ray interval.

Cascade size rule, as given:

    cascade_width  = render_width  / cascade0_linear
    cascade_height = render_height / cascade0_linear

- With the 4x ray and 1/4x probe scaling, the cascade size is constant for all cascades.
- cascade0_linear is a power of two. Values 1, 2, 4, 8 give probes 1, 2, 4, 8 px apart. Values 0.5, 0.25, 0.125 give 2, 4, 8 probes per pixel. The post calls the last form higher cost.
- Post text: cascade c has linear scale N (c0), then N*4 (c1), N*16 (c2), N*64 (c3). The code (see repository) uses 2^c per axis, which matches the post's own "each dimension scales by 2x" statement. The N*4 wording is inconsistent with the code (see inconsistencies).

### Raymarching (post version)

The post's raymarch is in pixel space, not UV space, which it says avoids skew for non-square distance fields. Core logic, restated:

- Ray origin = probe point + direction * offset, converted to UV.
- Each step samples the distance field (2-byte encoded), adds the scaled distance to a running total rd, and moves along the direction by that distance.
- Stop when rd reaches the range, or when the ray leaves [0,1) in UV.
- For cascade c != 0, if the first sample and rd are both about zero, the ray started inside a volume. Return no hit, since 2D lights emit from their surfaces only.
- On a surface hit, return the scene colour with visibility 0.
- If nothing is hit, return zero radiance with visibility 1.

Changes from a standard raymarch, per the post:

- Offset and range: each cascade's ray starts at offset and runs for a fixed range.
- Surface-only emission for 2D (see above).
- All SDF samples are scaled by the render diagonal, length(in_RenderExtent). The SDF shader computes distances in pixel coordinates and divides by this diagonal, so the value fits in 2-byte precision.

### Probe and ray index math (post version, `cascadeTexelInfo`)

The post's struct holds: angular, linear, size, probe, index, offset, range, scale. Restated math:

- angular = 2^c (the direction-group grid side). Pre-averaging means the real rays per probe are 4 * angular^2.
- linear = L0 * 2^c (per axis).
- size = E / angular: side of one direction group, in texels.
- probe = (x mod size, y mod size): probe grid position inside the group.
- raypos = floor(uv * angular): which direction group the texel is in.
- index = raypos.x + angular * raypos.y: direction index (row-major).
- offset = I0 * (1 - 4^c) / (1 - 4), which equals I0 * (4^c - 1) / 3.
- range = I0 * 4^c, plus a light-leak term: length(vec2(L0 * 2^(c+1))). The post calls this a minimal overlap equal to the spacing of cascade N+1.
- scale = length(in_RenderExtent).

Index-order note: the post uses row-major order and says a Z-order curve is not worth the complexity.

### Merge (post version, `merge`)

Restated steps:

- Skip the merge if the current ray hit a surface (visibility 0), or if this is the highest cascade. Skipped rays return their radiance with inverted visibility.
- angularN1 = 2^(c+1). sizeN1 = size / 2, the N+1 group size.
- probeN1 = (index mod angularN1, floor(index / angularN1)) * sizeN1: the N+1 group that holds this direction.
- interpUVN1 = probe / 2, clamped to [1, sizeN1 - 1] so hardware interpolation does not pull from neighbouring groups.
- Final lookup = probeN1 + clampedUVN1 + 0.25, sampled with hardware interpolation.
- Result = current radiance + sample.

The post explains: an even probe index (2) maps to a probe at a whole N+1 position; an odd index (3) lands halfway, at 1.5. Adding 0.25 gives weights 0.25 and 0.75. The post writes "2,2 becomes 2.25", but its own steps give 1 + 0.25 = 1.25 (see inconsistencies).

Note: the post's version clamps before adding 0.25. The repository's base shader adds 0.25 before clamping (see the repository section).

### main() (post version)

- probe_info from the texel's position.
- Probe origin = (probe + 0.5) * linear.
- preavg_index = index * 4 (the actual index of the first of 4 rays).
- theta_scalar = TAU / (pinfo.angular * 4.0); the `probe_info` constructor stores `angular * angular` in its `angular` field, so the step is TAU/4^(c+1).
- Loop over 4 rays: index = preavg_index + i, theta = (index + 0.5) * theta_scalar, raymarch, merge with the actual index, accumulate with weight 0.25.

### Performance (post)

Frame-time stress test, RTX 3080, 120 FPS target:

| Layout | Resolution | Probe density | Rays per probe in c0 | Figure |
|---|---|---|---|---|
| A: position first | 1024 x 1024 | 0.25 (4 probes per pixel) | 4 | 29.91 / 8.33 ms (120 FPS) |
| B: direction first | 1920 x 1080 | 0.25 (4 probes per pixel) | 4 | 25.95 / 8.33 ms (120 FPS) |

- The post calls the first figure a frame-time delta, and the second 8.33 ms, the 120 FPS budget.
- The repository's on-screen timer (see the repository section) prints measured frame time in ms, then the target budget. Read that way, the first numbers are measured frame times, and 8.33 ms is the budget. Derived from code, not stated in the post.
- Pixel counts: 1024 x 1024 is about 1.05 million; 1920 x 1080 is about 2.07 million (derived).
- The post's conclusion says the direction-first layout roughly doubled performance at double the screen area. The overview update says it is not faster. These conflict.
- GameMaker version: not stated.

### Limitations and reader comments (Part Two)

- Disclaimer: the code covers one narrow design domain, screen-space raymarching.
- The post says the code is under 100 lines. Shader files use comments.
- Sky and sun colours are commented out as pending.
- The "Dolkar Mask Ringing Fix" is listed as a planned transition fix, not implemented.
- Reader comment (Zenith, Jan 5, edited): compares 6 cascades at 4 rays per pixel with 24 random rays per pixel, and reports RC sometimes slower when total ray operations match. The replies are hidden in the text.

### Inconsistencies in Part Two

- Direction-first: the overview update says not faster; the conclusion says roughly double the performance.
- "2,2 becomes 2.25": the post's own arithmetic gives 1.25.
- Cascade scaling: "N*4" for cascade 1 in the linear-scale paragraph, versus 2^c per axis in the code and in the "each dimension 2x" paragraph.
- The post's merge clamps before adding 0.25. The repository base adds it before clamping.

---

## Repository: GMShaders-Radiance-Cascades

| | |
|---|---|
| Author | Yaazarai (Alex) |
| Date | Not captured. |
| Kind | GameMaker project repository, three sub-projects. License: Unlicense (public domain, per the LICENSE file). |
| Link | https://github.com/Yaazarai/GMShaders-Radiance-Cascades |

README: a 2D implementation of Sannikov's method, based on fad's Shadertoy. Points at Alex's other repository, Yaazarai/RadianceCascades, as the demonstration this repo supports.

### Repository layout

| Path | Contents |
|---|---|
| `RadianceCascades/` | Position-first (original paper layout) implementation, multi-pass. |
| `RadianceCascades-Optimized/` | Direction-first, pre-averaged, single-pass implementation, with several merge variants. |
| `CascadeVisualDemo/` | Visual demo showing probe spacing and ray mapping for both layouts. |
| `README.md`, `LICENSE` | Readme and Unlicense text. |

### Distance field and JFA (both versions)

Both versions use the same four steps:

1. Seed pass: every opaque world pixel (alpha > 0) writes its own position, encoded as two 2-channel 8-bit pairs. Empty pixels are zero.
2. Jump flood: log2(max dimension) passes, with jump distances 2^(passes-1) down to 1. Each pass samples a 3 x 3 neighbourhood at the jump offset and keeps the nearest seed.
3. Distance pass: stores the distance from each pixel to its nearest seed, encoded in two channels.
4. The resulting SDF is sampled during raymarching.

Encoding (both versions, same code):

    encode(f): r = floor(f * 255) / 255,  g = fract(f * 255)
    decode(r, g) = r + g / 255

- Derived: decode(encode(f)) = f, with precision about 1/65025. Representable values run up to about 1.0039.
- The original stores distances in UV units. The optimized version divides the pixel distance by the render diagonal, so values stay at or below 1 for the stored range. The post gives the diagonal scale as the fix for non-square fields.

### Original version: `RadianceCascades/`

Setup (`Obj_RadianceCascades/Create_0.gml`):

- width = height = 1024 (square).
- `radiance_initialize(1024, 4, 4, 2, 1.0, 0.65)`: angular 4, interval 4, spacing 2, boost 1.0, decay 0.65.
- Comment at call site says the interval must be a multiple of 4. The helper rounds to a multiple of 2.
- Cascade textures: square, E = `cascade_extent`. `radiance_clear` clears them each frame.
- Memory printed in debug: 4 bytes times E^2 times cascade count (assumes 4-byte texels; format not set in code).

Derived values for these defaults (not run):

- E = floor(1024 / 2) * sqrt(4) = 1024.
- Max cascade count = ceil(log2(1024 / sqrt(4))) = 9.
- Desired count = min(floor(log4(4 * diag)) - 1, 9), where diag = distance(0,0,1024,1024) = 1448.15. This evaluates to 5.
- Memory: 4 * 1024^2 * 5 bytes, about 20 MiB.

Per-frame sequence (`Obj_RadianceCascades/Draw_72.gml`, `Draw_73.gml`):

1. Draw_72: world scene. Clears the world surface, draws the sample sprite, then a yellow light disc (color $F0F066, radius 8) at the mouse.
2. Draw_73, bounce: the previous frame's radiance is drawn into the bounce surface, then the world scene is drawn over it. This is a one-frame feedback term. The intervals stage reads the bounce surface as its scene.
3. Distance field: seed, jump flood, distance pass (the three steps above).
4. Intervals pass: for each cascade n = 0 .. count-1, raymarch every texel into cascade n. Reads the distance field and the bounce surface.
5. Merging pass: for n = count-1 down to 0, merge cascade n with cascade n+1 through a temporary surface, then copy back into cascade n.
6. Mip pass: average all rays of each probe for the cascade chosen by `global.showcascade` (default 0). Mip size = E / (2^(c+1)), per the code.
7. Output: the chosen mip is drawn scaled up with additive blending at 1.0 and again at 0.5, into the radiance surface, which is drawn to the screen.

#### Position-first index math (original shaders)

Shared index math (`Shd_RadianceIntervals.fsh`, `Shd_RadianceMerging.fsh`, `Shd_RadianceMipMap.fsh`):

- count_c = A * 4^c (rays per probe). With A = 4, count_c = 4^(c+1).
- size_c = sqrt(count_c) = block side in texels = 2^(c+1). This is the tile size of one probe.
- probe cell = floor(texel / size_c). Number of probe cells per axis = E / size_c.
- ray index inside the tile r = (texel.y mod size_c) * size_c + (texel.x mod size_c). Row-major.
- theta = TAU * (r + 0.5) / count_c; delta = (cos theta, -sin theta).
- probe centre (UV) = (cell + 0.5) * L_c * texel_size, with L_c = spacing * 2^c.
- Total rays per cascade is E^2, the same for every cascade.

Interval math (`Shd_RadianceIntervals.fsh`):

- minimum (interval start) = sign(c) * I0 * (1 - 4^c) / (1 - 4). The sign term makes cascade 0 start at 0.
- range = I0 * 4^c.
- Light-leak term, only for c > 0: range += sqrt(2) * spacing * 2^(c+1). Written as length(vec2(d, d)) with d = spacing * 2^(c+1).

Raymarch (`Shd_RadianceIntervals.fsh`):

- Works in UV space. Distances are read directly from the distance field, which stores UV units.
- The loop cap is `ii < range`, with range in pixels, as a bound on iterations.
- Each step: sample the field at the current point, add the distance to rd, step by min(rd, rt) where rt = range * texel (texel = 1 / render extent).
- Break when rd >= rt, or when the point leaves [0,1).
- On a hit (distance <= 0.0001): return scene colour with alpha 1.0.
- No hit: return zero with alpha 0.0.
- Note: the shader's comment says alpha 0 is a hit and 1 is no hit. The code does the reverse. The merge shader then inverts the stored alpha (see below).

Merge (`Shd_RadianceMerging.fsh`):

- Reads cascade n texel (`gm_BaseTexture`), inverts its alpha, then merges only if the inverted alpha is non-zero, that is, if the ray did not hit. The comment in the code says "on hit merge", which conflicts with the code. Behaviour follows the code.
- Top cascade (index >= count - 1) does not merge.
- For each of 4 rays with theta indices 4 * index + i, fetch from the N+1 texture at 4 neighbouring N+1 probes: probeN1 = floor((probe - 1) / 2) (lower-left), then +(1,0), (0,1), (1,1).
- For each N+1 probe, sum 4 fetched rays, then divide by 4 (average).
- Blend across the four probes with weights:
  - Active: weight = 0.33 + (probe - (2 * probeN1 + 1)) * 0.33, labelled "smoother".
  - Commented: weight = 0.25 + (probe - (2 * probeN1 + 1)) * 0.5, labelled "per specification". This matches the post's 0.25 / 0.75.
- Output: rgb of the merged radiance, alpha forced to 1.

Note on the N+1 fetch: the coordinate uses fractional offsets within the tile (theta index divided by size, not floored). This works only if the sampler picks the texel containing the coordinate, i.e. nearest filtering. The original does not call `gpu_set_tex_filter`, so its effective filter is the engine default at that point (not stated in the source).

Mip (`Shd_RadianceMipMap.fsh`):

- For each mip pixel, loop over all count_c rays of that probe, sum, and divide by count_c.
- The loop indexes the cascade with the mip pixel's position times the probe size. The position is not floored (`in_TextCoord * in_MipMapExtent`). The source does not discuss this (unclear in source).

Other shaders in `RadianceCascades/` (`Shd_JumpfloodSeed`, `Shd_JumpfloodAlgorithm`, `Shd_DistanceField`):

- Seed: writes uv * alpha into two encoded pairs (zero where alpha is zero).
- JFA: as in the common section. Distances are in UV units here (not pixel units).
- Distance field: distance in UV units, encoded.

### Optimized version: `RadianceCascades-Optimized/`

Setup (`Obj_RadianceCascades/Create_0.gml`):

- `game_set_speed(60, gamespeed_fps)`.
- render_linear = 1.0 (cascade 0 probe spacing in pixels). Comment: values should be powers of two, from 0.125 up. Lower spacing gives higher quality.
- render_interval = point_distance(0, 0, render_linear, render_linear) * 0.5. Comment says it should be the diagonal of the linear resolution; the code uses half that (see inconsistencies).
- render_width = 1920, render_height = 1080.
- Cascade count = ceil(log4(diagonal of render size)). Derived: diagonal 2203.13, log4 about 5.55, so 6.
- Render size is padded so it divides by 2^(count-1): error_rate = 2^(count-1) = 32. Derived: 1920 stays 1920, 1080 becomes 1088.
- Cascade texture size = floor(render / linear). Derived: 1920 x 1088 at spacing 1.
- Textures: world, JFA and SDF are rgba8unorm at render size. The two cascade textures (`radiance_current`, `radiance_previous`) are rgba16float at cascade size.
- Only two cascade textures exist; they are reused for every cascade. The original keeps one surface per cascade.
- `radiance_interval` is set to multiple_ofN(0.707, 2) = 2.
- Shader selection: `radiance_u_cascades = Shd_RadianceCascades_BilinearFix` (active). Other variants are listed as comments (see the variants table).
- Uniforms: in_RenderScene, in_DistanceField, in_RenderExtent, in_CascadeExtent, in_CascadeCount, in_CascadeIndex, in_CascadeLinear, in_CascadeInterval.
- Shader comments say: pre-averaging cannot be disabled. Cascade 0 always contains the displayable result with 4 rays per pixel.

Per-frame sequence (`Obj_RadianceCascades/Draw_73.gml`):

1. Disable blending; enable linear texture filtering and clamp repeat off.
2. Seed the JFA from the world surface (`Shd_SeedJumpFlood`). Clear the SDF surface.
3. JFA: `Shd_JumpFlood` passes with jump distances from 2^(passes-1) down to 1, ping-ponging between the JFA and SDF surfaces. Passes = ceil(log2(max(render w, render h))).
4. SDF: `Shd_DistanceField` writes pixel distance divided by the render diagonal.
5. Cascade chain: for n = count-1 down to 0, draw `Shd_RadianceCascades_BilinearFix` into `radiance_current` with the previous cascade bound as gm_BaseTexture. Then copy `radiance_current` into `radiance_previous`.
6. Output: draw `radiance_current` (cascade 0) scaled to the render size.

The optimized frame has no bounce term (it does not use the previous frame's radiance). The original does.

HUD (Draw_73, last lines): prints `delta_time / 1000` then `1000 / game speed`. These are measured frame time in ms and the target budget in ms.

#### Direction-first index math

Per cascade c = i, with S = 2^i (direction grid side) and E = texture side (E_x by E_y in the code):

- Direction group size = E / 2^i texels per axis. Each group holds one probe grid.
- Direction block (bx, by) = floor(uv * 2^i). Direction index d = bx + 2^i * by, row-major, range 0 .. 4^i - 1.
- Probe position inside group p = (x mod (E / 2^i), y mod (E / 2^i)).
- Probes per axis = E / 2^i. Total probes per cascade = E^2 / 4^i.
- Stored directions per probe = 4^i (one texel per direction).
- Actual rays per probe = 4 * 4^i = 4^(i+1). Actual ray index k = 4 * d + j, for j = 0..3.
- Theta for actual ray k = (k + 0.5) * TAU / 4^(i+1). Direction vector (cos theta, -sin theta).
- Probe origin (pixels) = (p + 0.5) * L0 * 2^i.
- Total stored texels = E^2, the same for every cascade. Total actual rays = 4 * E^2, the same for every cascade.

Compare with position-first:

| Item | Position-first (original) | Direction-first (optimized) |
|---|---|---|
| Block in texture | One probe, side 2^(c+1) texels | One direction, side E / 2^c texels |
| Probe location | Block index = floor(texel / block side) | Position inside block = texel mod (E / 2^c) |
| Ray location | Position inside the probe block | Block index = floor(uv * 2^c) |
| Rays stored per probe | 4^(c+1), one texel each | 4^c, one texel each, averaged over 4 rays |
| Rays cast per probe | 4^(c+1) | 4^(c+1) (4 per stored texel) |
| Ray index formula | r = (y mod S) * S + (x mod S) | d = bx + 2^c * by, then k = 4d + j |
| Neighbouring probes in memory | Adjacent (same probe block) | Adjacent for the same direction (same block) |
| N+1 lookup for one ray | 16 texel fetches (4 rays times 4 probes), bilinear in shader | 1 texel fetch with hardware linear filter, using the 4 probes |

Compare the cost per actual ray: position-first merges read 16 texels per ray. Direction-first reads 1 texel per ray (the four probes are blended by the sampler).

#### Pre-averaging and the merge (what changes)

Position-first merge (original): an N ray with index r merges with N+1 rays 4r .. 4r+3 at each of 4 N+1 probes, averages each probe's 4 rays, then blends the 4 probes in shader. Four rays per probe are read per N+1 probe.

Direction-first merge (optimized, one-pass):

1. Each stored texel in cascade c is the average of four rays. In the shader: cast 4 rays, merge each one, add with weight 0.25.
2. The N+1 texture stores one averaged texel per (direction, probe). The N+1 direction index equals the N actual ray index k, because N+1 stores 4^(c+1) directions and N casts 4^(c+1) rays.
3. For an N actual ray k, the N+1 group for direction k holds the average over N+1's rays 4k .. 4k+3. These cover the same angular arc as ray k of N.
4. The N+1 probe location is p/2 + 0.25 in N+1 texel units (the probe centre in N+1 coordinates). It is clamped to [1, size_N+1 - 1] in the base shader. Hardware linear filtering blends the four surrounding N+1 probes of that direction group in one fetch.
5. Result per ray = radiance of N + fetched N+1 value. The merge is applied to each of the four actual rays, then averaged.

The index scaling in code: preavg_index = stored d * 4; actual ray k = preavg_index + i; theta uses k; the N+1 lookup uses k directly (not scaled again).

Derived: the N+1 lookup for k is in N+1 direction group k, which is the same index as N's actual ray k.

#### Default configuration: derived values

Original defaults (1024 x 1024, angular 4, interval 4, spacing 2). Derived from the formulas, not run:

| Cascade c | Spacing L_c (px) | Probes per axis | Rays per probe | Tile side (texels) | Interval start off_c | Range (incl. light-leak term) |
|---|---|---|---|---|---|---|
| 0 | 2 | 512 | 4 | 2 | 0 | 4 (no leak term at c = 0) |
| 1 | 4 | 256 | 16 | 4 | 4 | 16 + 8*sqrt(2) = 27.31 |
| 2 | 8 | 128 | 64 | 8 | 20 | 64 + 16*sqrt(2) = 86.63 |
| 3 | 16 | 64 | 256 | 16 | 84 | 256 + 32*sqrt(2) = 301.25 |
| 4 | 32 | 32 | 1024 | 32 | 340 | 1024 + 64*sqrt(2) = 1114.51 |

Optimized defaults (1920 x 1088 render after padding, linear 1.0, interval 2, 6 cascades). Derived, not run:

| Cascade i | Spacing L_i (px) | Direction grid | Stored directions per probe | Actual rays per probe | Probes per axis (x by y) | Interval start off_i | Range |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 1 x 1 | 1 | 4 | 1920 x 1088 | 0 | 2 + 2*sqrt(2) = 4.83 |
| 1 | 2 | 2 x 2 | 4 | 16 | 960 x 544 | 2 | 8 + 4*sqrt(2) = 13.66 |
| 2 | 4 | 4 x 4 | 16 | 64 | 480 x 272 | 10 | 32 + 8*sqrt(2) = 43.31 |
| 3 | 8 | 8 x 8 | 64 | 256 | 240 x 136 | 42 | 128 + 16*sqrt(2) = 150.63 |
| 4 | 16 | 16 x 16 | 256 | 1024 | 120 x 68 | 170 | 512 + 32*sqrt(2) = 557.25 |
| 5 | 32 | 32 x 32 | 1024 | 4096 | 60 x 34 | 682 | 2048 + 64*sqrt(2) = 2138.51 |

Notes on the optimized table:

- The range formula uses length(vec2(L0 * 2^(i+1))), which equals L0 * 2^(i+1) * sqrt(2). The base shader applies it for every cascade, including cascade 0.
- These ranges follow the base shader. The active `Shd_RadianceCascades_BilinearFix` uses limit = I0 * 4^i with no leak term (2, 8, 32, 128, 512, 2048 px for i = 0 .. 5).
- The top cascade's range in the base formula is about 2138 px. The diagonal is 2203 px.

### Shader variants (optimized folder)

All variants use the direction-first index math. The differences are in the table.

| Shader | Active? | Raymarches per texel | N+1 fetches per ray | Ray start | Light-leak term in range | Other differences |
|---|---|---|---|---|---|---|
| `Shd_RadianceCascades` ("Vanilla", no fixes per README) | No | 4 (one per actual ray) | 1, hardware linear, clamped index | Probe origin + own direction * interval | Yes, for every cascade | Volume-start check (returns zero for c != 0). sRGB: samples linearised with pow 2.2; cascade 0 output encoded with pow 1/2.2. Comment marks Dolkar fix as not yet implemented. |
| `Shd_RadianceCascades_BilinearFix` | Yes | 16 (4 rays times 4 bilinear N+1 probes) | 4 nearest-texel fetches per ray, blended in shader with 0.25 / 0.75 weights | Each ray starts on a coarser direction ("forked") at offset along that direction | No (replaced by forking) | Reprojects each ray to the endpoint of each N+1 probe's ray. No volume-start check. |
| `Shd_RadianceCascades_NearestFix` | No | 4 | 1 nearest-texel fetch (N+1 probe = floor(probe / 2)) | Forked, as above | No (replaced by forking) | Pixelation expected: 2 x 2 blocks of N probes share one N+1 probe (README). No volume-start check. |
| `Shd_RadianceCascades_InterlacedFix` | No | 4 | 1 nearest-texel fetch, N+1 probe picked from 4 candidates by index mod(2 * px + py, 4) | Forked, as above | No (replaced by forking) | Dithering look, per README. Shows a "blurrier" candidate order active and a "sharper" order commented. No volume-start check. |
| `Shd_RadianceCascades_FPFixed` | No | 4 | 1, hardware linear, clamped index | Probe origin + own direction * interval | Yes | Uses floored half-size. Index is mod(sector.x + sector.y * angular, count). Volume-start check present. Name meaning not given in source. |
| `Shd_RadianceCascades_Final` | No | 4 | 1, hardware linear, clamped to [0.5, size - 0.5] | Probe origin + own direction * interval | No (commented out) | Raymarch runs to range `limit` from start point. No volume-start check. Name meaning not given in source. |

Notes:

- Only `Shd_RadianceCascades_BilinearFix` is active in `Create_0.gml`. The others are commented out in the same block.
- README wording for the fixes: bilinear fix reduces interpolation artifacts and fixes occlusion; nearest fix gives pixelation; interlaced fix gives dithering and reduces ringing and occlusion; vanilla has no fixes.
- The bilinear fix's merge is only applied when a ray did not hit (radiance.a != 0), as in the base.

#### Bilinear fix in detail (`Shd_RadianceCascades_BilinearFix.fsh`)

Per texel:

1. probe = (x mod extent, y mod extent) with extent = E / 2^c; block = floor(texel / extent). index = (block_x + 2^c * block_y) * 4.
2. interval = I0 * (1 - 4^c) / (1 - 4); limit = I0 * 4^c.
3. origin = (probe + 0.5) * L_c.
4. Four bilinear N+1 probes: probeN1 = floor((probe - 1) / 2), then +(0,0), (1,0), (0,1), (1,1). Weights: 0.25 + (probe - (2 * probeN1 + 1)) * 0.5 on each axis.
5. For each of the 4 rays preavg = index + i (i = 0 .. 3):
   - theta = (preavg + 0.5) * TAU / (4^(c+1)).
   - thetaNm1 = (floor(preavg / 4) + 0.5) * TAU / 4^c (direction of the coarser ray).
   - ray_start = origin + delta_Nm1 * interval.
   - For each of the 4 bilinear N+1 probes j: originN1 = (bilinearN1[j] + 0.5) * L_{c+1}; ray_end = originN1 + delta * (interval + limit); raymarch from ray_start toward ray_end, for the segment length.
   - Each result goes through mergeNearestProbe: fetch the N+1 texel of the same direction at that N+1 probe (nearest texel centre).
   - Blend the four results: top = mix(s0, s1, wx), bottom = mix(s2, s3, wx), result = mix(top, bottom, wy).
   - Accumulate result * 0.25.
6. Cascade 0: encode colour with pow 1/2.2.

Per-texel cost: 16 raymarches and 16 nearest fetches, versus 4 and 4 for the base shader.

#### Base shader per-texel flow (`Shd_RadianceCascades.fsh`)

- probe_info from the texel: angular = 2^c, linear = L0 * 2^c, size = E / angular, probe, index.
- origin = (probe + 0.5) * linear.
- preavg_index = index * 4; theta_scalar = TAU / (pinfo.angular * 4.0), where the `probe_info` constructor stores `angular * angular` in its `angular` field, so the step is TAU/4^(c+1).
- Loop i = 0..3: index = preavg_index + i, theta = (index + 0.5) * theta_scalar, raymarch, merge, accumulate * 0.25.
- For cascade 0 only: output = pow(rgb, 1/2.2).

### Inconsistencies in the repository

- Interval rule: `Create_0.gml` (original) comment says the interval must be a multiple of 4. `multiple_of2` rounds to a multiple of 2. Default interval 4 satisfies both.
- Cascade count formulas differ:
  - Post: ceil(log4(intervalstart)) - 1, using the geometric interval start.
  - Original: min(floor(log4(4 * diag)) - 1, max) = floor(log4(diag)), capped by log2 of the position-first size. Uses the screen diagonal directly.
  - Optimized: ceil(log4(diag)). Note the ceil and not floor.
  - Visual demo: floor(log2(size / sqrt(angular))) - 1, which is a different base.
- Linear scale: the original's helper comment describes spacing as N*4 per cascade. The code uses 2^c per axis (N*4 in area).
- Merge weights: the active original shader uses 0.33 / 0.66 "smoother" weights. The per-specification 0.25 / 0.75 form is commented out.
- Merge comment: the original merge comment says "on hit merge". The code merges on a no-hit (inverted alpha non-zero).
- Visibility convention: the original raymarch comment says 0 = hit, 1 = no hit. The code returns alpha 1 on hit and 0 on no hit, then merge inverts. The optimized code uses 0 = hit, 1 = no hit, as the comment says.
- Optimized `render_interval` comment says "should equal the diagonal of the linear resolution". The code multiplies by 0.5.
- Optimized `Create_0.gml` says cascade 0 with 4 rays per pixel; the spacing default is 1, so 1 probe per pixel. The post's performance test used 0.25 (4 probes per pixel).
- Post vs base shader: the post clamps the N+1 probe index before adding 0.25. The base shader adds 0.25 before clamping.

---

## Earlier post: 2D GI by random rays per pixel

Source: "Guest: GI: Exploring 2D Global Illumination with @yaazarai", Xor, 2023-12-08, https://mini.gmshaders.com/p/yaazarai-gi. The anchor https://mini.gmshaders.com/i/139316845/jumpflood-and-raymarching is its section "Distance Field Generation (Jump Flood Algorithm)". Part One links this post as its prerequisite. It traces rays from every pixel each frame, with no probes or cascades.

### Distance field

- The scene is an image. Each non-empty pixel stores its own coordinate, and a jump flood spreads the nearest seed; each pixel checks a 3×3 set of seeds and keeps the nearest. The post gives no pass offsets or pass count.
- The field value is the distance to the stored seed. Coordinates take 2 bytes each so the raymarch has enough precision; the post calls the resulting look of the field intentional.
- The direction to the seed can serve as a normal map.

### Raymarch and GI pass

- Each ray: `dir = (cos θ, −sin θ)`; for each of `stepsPerRay` steps, `s = DF(p)`, `p += dir·s`, and if `s < EPSILON` the ray returns the per-channel max of `colour(p)` and `colour(p − dir/screen)`, the hit texel and the empty texel one pixel before it. A ray that runs out of steps returns black. The post suggests 32 to 64 steps.
- Optional aspect correction: in landscape `p.x /= screen.y/screen.x`, in portrait `p.y /= screen.x/screen.y`.
- Per pixel (skipped where `DF < EPSILON`, inside walls): `L` = the pixel's scene colour, `B = max(L.r, L.g, L.b)`, `θ0 = 2π·n` with `n` from blue noise, and for `k = 0..R−1` with `θ_k = θ0 + 2πk/R`, `L += h_k` and `B += max(h_k)`.
- The output `(L/B)·(B/R)` is algebraically `L/R`, so the brightness normalization has no effect, and `B = 0` gives 0/0. The loop runs `ray < TAU` in steps of `TAU/R`, so float accumulation may give `R` or `R + 1` iterations (read from the text, not tested). `in_RaysPerPixel` has no default.
- Inputs: `gm_BaseTexture` RGB holds light colours, `in_DistanceField.r` the encoded field, `in_BlueNoise.r` the noise in [0, 1], and `screen` the resolution. The output alpha is 1.

### Bounces and noise

- The previous frame's output is fed back as the next frame's scene light, so bounces build up over frames. The post gives no bounce count.
- Static noise: `θ0 = 2π·n`. "3D-style" noise: `n' = fract(n + φ·t)` with the golden ratio and scene time. "2D-style" noise, the one recommended: `θ = mod(2π·n + t/(2π), 2π)`, written back to a texture as `θ/2π` each frame. Time units are not given.
- The blue noise is Calinou's open-source texture set, shown at 512×512.

### Limits and uses

- Rays are unbounded, so a step cap is needed, and misses return black.
- Non-square surfaces skew the field unless corrected.
- Static noise bands, more rays cost GPU time, denoisers add banding, and noise hurts video encoding.
- Light accumulates over frames. The method is 2D only and the post gives no timings.
- Uses named: pseudo-wave propagation, falling-sand games such as Noita, AI traversal, and planet gravity from the field's normals. The post links a GMShadersGI repository and Samuel Bigos's Godot GI tutorial.

### Voxels post

https://mini.gmshaders.com/p/voxels (Xor, 2024-06-01) is paywalled. The public part has the opening note, the motivation (how Teardown and SEUS-style Minecraft shader mods light scenes) and a Teardown versus SEUS Renewed comparison image. The web.archive.org copy shows the same paywall. No method content is public.

## Cross-source comparison

| Topic | Part One (post) | Part Two (post) | Repository (original) | Repository (optimized) |
|---|---|---|---|---|
| Layout | Position-first, tile per probe | Describes both; direction-first preferred for debugging | Position-first, tile per probe | Direction-first, one block per direction |
| Rays per probe, cascade 0 | 8 x 8 in example (64). Overview says "usually 4". | Fixed at 4 | 4 (angular 4) | 4 (fixed) |
| Probe spacing ratio | 2x per axis (4x area) | Same | 2x per axis (code) | 2x per axis (code) |
| Ray ratio | 4x | 4x, with pre-averaging storage | 4x | 4x, with pre-averaging storage |
| Light-leak term | Not stated | Added: length of N+1 spacing diagonal | Only for c > 0 | Base and FPFixed: always. BilinearFix, NearestFix, InterlacedFix: replaced by forked ray starts. Final: absent. |
| Visibility convention | 1 = hit (text) | 0 = hit, 1 = no hit | Code: 1 = hit, 0 = no hit | 0 = hit, 1 = no hit |
| Passes | Raymarch, then merge | One pass: raymarch plus merge | Intervals pass, then merge pass | One pass per cascade |
| Cascade storage | One surface per cascade (implied) | Two textures reused | One surface per cascade | Two textures reused |
| Merge fetch | 4 probes times 4 rays | 1 hardware-filtered fetch (pre-averaged) | 16 fetches | 1 fetch per actual ray |
| Colour space | Not stated | Not stated | No gamma conversion | Linear accumulation, sRGB in and out for cascade 0 |
| Distance units | Not stated | Pixel, scaled by diagonal | UV | Pixel, scaled by diagonal |
| Non-square | Not addressed | Supported in optimized | Square only | Non-square, padded to multiple of 2^(count-1) |
| Bounce term | Not stated | Not stated | Previous frame radiance added | None |

---

## Links found

- Radiance Cascades paper (Alexander Sannikov) | https://drive.google.com/file/d/1L6v1_7HY2X-LV3Ofb6oyTIxgEaP4LOI6/view | Original paper; the post cites its figure 8 for the constant-size layout.
- Yaazarai radiosity tutorial (GM Shaders) | https://mini.gmshaders.com/p/yaazarai-gi | Earlier post on random per-pixel ray sampling, linked as the prerequisite ([notes](#earlier-post-2d-gi-by-random-rays-per-pixel)).
- GM Shaders voxels post | https://mini.gmshaders.com/p/voxels | Earlier raymarching post, linked for raymarch background; paywalled ([notes](#voxels-post)).
- GM Shaders JFA/SDF section | https://mini.gmshaders.com/i/139316845/jumpflood-and-raymarching | Section on jump flood and SDF generation, inside the 2D GI post ([notes](#distance-field)).
- tmpvar Radiance Cascades playground | https://tmpvar.com/poc/radiance-cascades/ | Interactive demo of linear and angular resolution and interval scaling.
- Alex's 2D quick ray tracing GLSL | https://github.com/Yaazarai/2D-QuickRayTracing-GLSL | Single-probe method; Part One's figure 6 is an image from it. The repository (LGPL-2.1, with a 9-page write-up) places one probe at each light's center. A first pass traces `2πR` rays, one pixel apart at the light's radius `R`, in whole-pixel steps through a collision texture, and stores each ray's first hit distance over `R` in two 8-bit channels (`R = floor(255x)/255`, `G = fract(255x)`) in a square texture of side `2^ceil(log2 √(2πR))`. A second pass draws a quad per light and compares each pixel's distance with the nearest ray by angle, so shadows are hard and step at ray boundaries. Nothing is cached: every light is traced again each frame, about `O(R²)` samples per light. The size tables limit `R` to above 4 and at most 4096 px; the "65,535 px" maximum in the README is only a loop bound. Read from the code and not run: steps can skip walls thinner than a pixel along the ray, a solid texel at the exact center is ignored, and when `fract(2πR) ≥ 0.5` the rounded ray count leaves a final wedge just below 2π that reads as unobstructed.
- Alex's bilinear Shadertoy example | https://www.shadertoy.com/view/cslSW4 | Bilinear interpolation example for the merge. The shader (FatalSleep, 2022-11-19) predates RC and blends four corner-aligned samples per 50 px cell ([code notes](2023_rc_shadertoys.md#cslsw4-fatalsleep-local-bilinear-interpolation)).
- Fad's Shadertoy | https://www.shadertoy.com/view/mtlBzX | Base implementation the repository builds on; source of the skybox integral.
- Sannikov gravity simulation (Shadertoy) | https://www.shadertoy.com/view/XcB3Ry | Listed as another use of RC. Shadertoy lists it under Suslik, Sannikov's account ([code notes](2023_rc_shadertoys.md#xcb3ry-and-mfs3wm-suslik-cascades-for-gravity)).
- Sannikov 3D screen-space GI video | https://www.youtube.com/watch?v=N6RP3r1M9g4 | Listed as another use of RC. The video is "Single shot global illumination with no denoiser" (2023), cascaded image-space GI in one frame in about 5 ms ([notes](2022_sannikov_youtube_rc_videos.md#single-shot-global-illumination-with-no-denoiser-2023)).
- Mytino volumetrics (tweet) | https://x.com/MytinoGames/status/1777029143282295153 | Volumetrics through high-viscosity fluids. The April 2024 post shows a glowing slime simulation in Mytino's own engine; asked whether it is RC, Mytino answered that it is, or at least heavily based on it. No demo was planned.
- Yaazarai RadianceCascades demonstration | https://github.com/Yaazarai/RadianceCascades | Demonstration repository the README points to.
- GM Shaders repository | https://github.com/Yaazarai/GMShaders-Radiance-Cascades | Companion repository for both posts (described above).
- Repository, optimized shader | https://github.com/Yaazarai/GMShaders-Radiance-Cascades/blob/main/RadianceCascades-Optimized/shaders/Shd_RadianceCascades/Shd_RadianceCascades.fsh | Base optimized shader.
- Repository, distance field shader | https://github.com/Yaazarai/GMShaders-Radiance-Cascades/blob/main/RadianceCascades-Optimized/shaders/Shd_DistanceField/Shd_DistanceField.fsh | Pixel-scaled distance field shader.
