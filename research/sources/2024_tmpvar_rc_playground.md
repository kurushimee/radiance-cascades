# tmpvar's Radiance Cascades playground

| | |
|---|---|
| Author | tmpvar |
| Date | Not stated (2024 by its links) |
| Kind | Interactive demo page (WebGPU playground) with linked JavaScript source |
| Link | https://tmpvar.com/poc/radiance-cascades/ |

This page is a set of small interactive demos with short explanations, meant to build intuition for radiance cascades (RC). The 2D section has four demos: radiance interval shapes, ray distributions per level, probe ray interpolation (ray geometry only), and a full WebGPU 2D global illumination playground called "Flatland". The 3D section has a settings panel that estimates storage for screen-space probes with world-space intervals, and a table of storage costs for world-space probes.

## Contents

- [Files and sources](#files-and-sources)
- [Demo 1: Radiance Intervals (2D)](#demo-1-radiance-intervals-2d)
- [Page text for the 2D section](#page-text-for-the-2d-section)
- [Demo 2: Ray Distributions (2D)](#demo-2-ray-distributions-2d)
- [Demo 3: Probe Ray Interpolation (2D)](#demo-3-probe-ray-interpolation-2d)
- [Demo 4: Flatland (2D global illumination, WebGPU)](#demo-4-flatland-2d-global-illumination-webgpu)
  - [Controls and defaults](#controls-and-defaults)
  - [GPU resources](#gpu-resources)
  - [Index math](#index-math)
  - [Frame order (RenderFrame)](#frame-order-renderframe)
  - [Shaders and roles](#shaders-and-roles)
  - [Per-ray math (ProbeAtlasRaymarch, ComputeMain)](#per-ray-math-probeatlasraymarch-computemain)
  - [Upper-level merge (SampleUpperProbes, SampleUpperProbe)](#upper-level-merge-sampleupperprobes-sampleupperprobe)
  - [Raymarch](#raymarch)
  - [Fluence (BuildFluenceTexture)](#fluence-buildfluencetexture)
  - [Derived from reading the code (not stated by the author, not tested)](#derived-from-reading-the-code-not-stated-by-the-author-not-tested)
  - [Limitations and notes stated in the source](#limitations-and-notes-stated-in-the-source)
- [Demo 5: Screenspace probes with worldspace intervals (3D)](#demo-5-screenspace-probes-with-worldspace-intervals-3d)
- [Demo 6: World-space probe storage table (3D)](#demo-6-world-space-probe-storage-table-3d)
- [Links found](#links-found)

## Files and sources

- `flatland-2d/flatland-2d.js`: 2,025 lines, 61,092 bytes. Holds all WGSL shaders and the WebGPU pipeline for the 2D GI demo.
- `flatland-2d/params.js`: 2,980 bytes. Shared control reader, imported by every demo script.
- `flatland-2d/radiance-intervals-2d.js`: 3,353 bytes.
- `flatland-2d/probe-ray-distributions-2d.js`: 4,960 bytes.
- `flatland-2d/probe-interpolation-2d.js`: 3,438 bytes.
- `ssprobes-wsintervals/ssprobes-wsintervals.js`: 2,997 bytes. Imports `./params.js` from its own folder.
- The world-space storage table is an inline module at the bottom of the page HTML.
- The 2D playground loads `flatland-2d/flatland-2d-demo.png` as its starting scene. This image was not fetched.
- Code is MIT; page text and images are CC BY 4.0.

## Demo 1: Radiance Intervals (2D)

| Control | Range | Default | Meaning |
|---|---|---|---|
| level 0 ray count | 4 to 8 | 4 | Raw ray count at level 0 |
| branching factor B | 1 to 3 | 2 | Label shows 2^B |

Drawing rules (canvas 1024 x 1024, background #111, seven level colors, levels 0 to 6):

- The center is at (512, 512). The starting radius is 16, and there is no padding.
- Outer radius of level l: `16 << (l * B)`.
- Inner radius: 0 for level 0, otherwise `16 << ((l - 1) * B)`.
- The loop stops once inner radius * 2 is greater than 1024.
- Ray count at level l: `level0RayCount << (l * B)`.
- Ray k has angle `2 * pi * (k + 0.5) / count`. Each ray is a segment from the inner radius to the outer radius.
- Each level draws one circle at its outer radius.
- Ray direction uses sin for x and cos for y.

Default example (ray count 4, B = 2): levels 0 to 3 are drawn. Outer radii are 16, 64, 256 and 1024. Ray counts are 4, 16, 64 and 256. Level 4 stops the loop.

The page bullets (see the next section) match the B = 1 case of these formulas. The total-ray bullet is not computed in this demo.

## Page text for the 2D section

The page says each cascade level, relative to the previous one:

- doubles the inner radius of the band,
- doubles the width of the band,
- doubles the number of rays per probe,
- halves the total number of rays,
- offsets the rays by half a step, with `angle = TAU * (rayIndex + 0.5) / rayCount`.

The page labels the per-level factor as N^level. The code uses 2^(B * level) per level, so N = 2^B.

## Demo 2: Ray Distributions (2D)

The page notes that this demo uses spatial doubling per level for any branching factor. It calls this the common case for flatland.

| Control | Range | Default | Meaning |
|---|---|---|---|
| max level | 0 to 6 | 2 | Levels drawn: 0 to max |
| 2^r raycount (level 0) | r = 2 to 5 | r = 2 (4 rays) | R0 = 2^r |
| probe diameter (level 0) | exponent 2 to 10 | 7 (128 px) | D0 = 2^e |
| interval radius (level 0) | 0 to 64 | 18 | I, used as an integer |
| branching factor B | 1 to 3 | 2 | Per-level ray growth |
| color lower levels | checkbox | on | When off, levels below max are drawn in #222 |
| show cascade ray counts | checkbox | off | Prints ray count per level and in total |

Formulas for level l from 0 to max:

- Probe diameter: `D_l = D0 << l`. Spacing doubles per level whatever B is.
- Rays per probe: `R_l = R0 << (B * l)`.
- Interval start: `S_l = 0` for level 0, otherwise `I << ((l - 1) * B)`.
- Interval end: `E_l = I << (B * l)`.
- Probes sit on a grid with step D_l, starting at (0, 0). Each probe center is the cell corner plus D_l / 2.
- Each probe draws R_l segments from S_l to E_l. Angle is `2 * pi * (k + 0.5) / R_l`, with direction (sin, cos).
- Ray count per level: `(1024 / D_l)^2 * R_l`.

Default example (max 2, R0 = 4, D0 = 128, I = 18, B = 2):

- Level 0: D = 128, 8 x 8 probes, 4 rays each, 256 rays, interval [0, 18].
- Level 1: D = 256, 4 x 4 probes, 16 rays each, 256 rays, interval [18, 72].
- Level 2: D = 512, 2 x 2 probes, 64 rays each, 256 rays, interval [72, 288].
- Total: 768 rays.

Derived from the formulas (not stated on the page): with B = 2 the ray count per level stays constant. With B = 1 it halves per level. With B = 3 it doubles per level.

## Demo 3: Probe Ray Interpolation (2D)

| Control | Range | Default | Meaning |
|---|---|---|---|
| min level | 0 to 6 | 1 | First level drawn |
| max level | 0 to 6 | 2 | Last level drawn |
| level 0 ray count | 1 to 32 | 4 | L0 |
| branching factor B | 1 to 3 | 1 | Per-level ray growth |

Drawing (canvas 1024): the probe radius is fixed at 64 and the grid step is fixed at 128. Spacing does not change per level. For each level from min to max:

- Ray count: `L0 << (B * l)`.
- Outer radius: `64 << (B * l)`. Inner radius: 0 for level 0, otherwise `64 << ((l - 1) * B)`.
- Each probe at cell origin + 64 draws its rays as segments from inner to outer radius.

Observations:

- The demo draws only ray segments. The code computes no interpolation and draws no merged values, even though the section title says "interpolation".
- The function inside the file is named `DrawRayDistributions2D`. The name was copied from the previous demo.
- An unused variable in the branch-factor label code reads `state.params.probeRayCount`, which this demo never sets. It has no effect on the output.

Default example (min 1, max 2, L0 = 4, B = 1): level 1 draws 8 segments per probe, from radius 64 to 128. Level 2 draws 16 segments per probe, from 128 to 256. There are 64 probes.

## Demo 4: Flatland (2D global illumination, WebGPU)

The demo needs WebGPU (Chrome or Edge). It also uses the optional `timestamp-query` feature for per-pass timings. A console warning describes a Chrome Canary flag for that feature. The canvas is fixed at 1024 x 1024, and all textures and buffers are sized from it.

### Controls and defaults

Cascade parameters:

| Control | Range | Default | Meaning in code |
|---|---|---|---|
| 2^i spacing (level 0) | i = 1 to 9 | 1 | D0 = 2^i px, probe cell diameter. Default 2 px. Stored as radius D0 / 2. |
| 2^r raycount (level 0) | r = 1 to 6 | 2 | R0 = 2^r. Default 4 rays. |
| branching factor | B = 1 to 3 | 2 | N = 2^B. Default N = 4. |
| interval radius (level 0) | s = 0 to 32, step 0.1 | 2.6 | I = s^2. Default 6.76 (see truncation note). |
| levels | 0 to 9 | 5 | Top level index computed. |

Debug parameters:

| Control | Range | Default | Meaning in code |
|---|---|---|---|
| run continuously and collect frame timings | checkbox | off | Prints GPU pass times. Needs `timestamp-query`. |
| render world mip level | disabled, 0 to 9 | disabled | Shows a mip of the preview texture instead of fluence. |
| render probe directions | checkbox | off | Fluence shows only rays aimed at each pixel's probe cell. |
| disable brush preview | checkbox | off | Skips the preview brush paint. Id is spelled `debugDisbleBrushPreview`. |
| raymarch mipmap N on cascade level N | checkbox | on | Marches on mip level equal to the cascade level. |
| raymarch with dda | checkbox | off | Uses grid traversal instead of fixed steps. |
| raymarch fixed size step multiplier | 1 to 1000 | 100 (1.00) | Step multiplier is max(0.1, value / 100). Disabled when DDA is on. |
| accumulate non-linearly | checkbox | off | Switches the accumulation formula. |
| accumulation decay | 1 to 400 | 100 (1.00) | Decay is value / 100. Disabled unless non-linear is on. |

### GPU resources

- `worldTexture`: rgba16float, 1024 x 1024. RGB holds emission times alpha (premultiplied). Alpha holds opacity.
- `worldAndBrushPreviewTexture`: rgba16float, 1024 x 1024, 10 mip levels (log2 of 1024). The raymarch reads this texture, so the brush preview affects lighting unless it is disabled.
- `probeBuffer`: storage array of vec4f. Size is `2 * maxLevel0Rays * 16` bytes. `maxLevel0Rays = 2^6 * (1024 / 2)^2 = 16,777,216`, so the buffer is 536,870,912 bytes (512 MiB). It is allocated at startup from the slider limits.
- `fluenceTexture`: rgba8unorm, 1024 x 1024. This is the final image.
- Per-level uniform block: 16 int32 fields (totalRays, probeRadius, probeRayCount, level, levelCount, width, height, maxLevel0Rays, intervalStartRadius, intervalEndRadius, branchingFactor, and the five debug flags and values). Each level has its own slot at a dynamic offset. The source reserves 10 levels and assumes the device alignment is at most 256 bytes (see its TODO).

### Index math

Symbols:

- `D_l = D0 * 2^l`: probe diameter at level l, in pixels.
- `W_l = 1024 / D_l`: probes per row and per column.
- `R_l = R0 * 2^(B * l)`: rays per probe.
- Probe linear index `p = row * W_l + col`. In code, `col = p % W_l` and `row = p / W_l` (integer division).
- Ray slot: `base_l + p * R_l + k`, where `k` runs from 0 to `R_l - 1` and `base_l = (l mod 2) * maxLevel0Rays`.
- Ray angle `theta = 2 * pi * (k + 0.5) / R_l`. Direction is `(cos theta, sin theta)`.
- Probe center in pixels: `(col * D_l + D_l / 2, row * D_l + D_l / 2)`.
- Total rays at level l: `W_l^2 * R_l`.
- Dispatch uses 256 threads per group. Linear id is `gid.x + gid.y * 256`. Probe index is `id / R_l` and ray index is `id % R_l`. Threads with `id > totalRays` exit.

### Frame order (RenderFrame)

1. Read all controls. Nothing else runs unless a value changed, the mouse moved, or the clear button was pressed (or timing is on).
2. If the mouse is down, paint a capsule from the last mouse point to the current one into `worldTexture`. Y is flipped (`canvas.height - y`).
3. Copy `worldTexture` to the preview texture, then paint the brush disc on the preview (unless disabled).
4. Build the preview mip chain with 2 x 2 box averages, levels 1 to 9.
5. Run `ProbeAtlasRaymarch` once per level, from the top level down to level 0. Each level is its own compute pass.
6. Run `BuildFluenceTexture` from the level 0 probes.
7. Run `DebugWorldBlit` to draw the fluence (or a world mip) to the canvas.

### Shaders and roles

| Name | Kind | Role |
|---|---|---|
| DebugWorldBlit | Render pipeline (full-screen triangle) | Draws `fluenceTexture`, or a mip of the preview texture when the debug option is set. |
| ProbeAtlasRaymarch | Compute, 256 x 1 x 1 | One dispatch per level. Each ray marches its interval and merges the upper level. Functions: `DDACursorInit`, `RayMarchDDA`, `RayMarchFixedSize`, `AccumulateSample`, `SampleUpperProbe`, `SampleUpperProbes`, `ComputeMain`. |
| BuildFluenceTexture | Compute, 16 x 16 | Writes one value per pixel from the level 0 probes. Uses `sdSegment` for the direction debug view. |
| WorldClear | Compute, 16 x 16 | Writes a constant color to a storage texture. |
| WorldPaint | Compute, 16 x 16 | Paints a capsule (segment with radius) into a storage texture. Used for the world and for the preview. Uses `SDFSegment`. |
| GenerateMipmapsBoxFilter | Compute, 16 x 16 | Each mip is the 2 x 2 average of the previous mip. |

### Per-ray math (ProbeAtlasRaymarch, ComputeMain)

For probe center P, direction d and ray index k at level l:

1. Lower segment: march from `P + d * S_l` to `P + d * E_l`. Start with accumulator (0, 0, 0, 1). The result is `Lower` = (rgb, a).
2. Upper term: `Upper = SampleUpperProbes(P, k)`.
3. Store: `rgb = Lower.rgb + Lower.a * Upper.rgb`, and `a = Lower.a * Upper.a`.

Interval layout in code: `S_0 = 0`, `E_l = I * 2^(B * l)`, and `S_l = E_(l-1)` for l > 0. Here `I` is the stored interval value (see the truncation note below).

### Upper-level merge (SampleUpperProbes, SampleUpperProbe)

- If `l + 1 >= levelCount`, the upper term is (0, 0, 0, 1). That means no contribution from above. The source has a TODO for sky or environment lighting here.
- `N = 2^B`. Lower ray k maps to upper rays `k * N` through `k * N + N - 1`. Derived from the angle formula: these sub-rays fall inside the lower ray's angular sector.
- Upper cell diameter: `D_(l+1) = 2 * D_l`.
- Fractional probe index per axis: `f = P / D_(l+1) - 0.5`. Base cell: `b = floor(f)`.
- Four upper probes: `b`, `b + (1, 0)`, `b + (0, 1)`, `b + (1, 1)`. Each index is clamped to `[0, W_(l+1) - 1]` per axis. The source calls the clamping an intentional reuse of edge probes. Its planned real fix is an extra ring of probes just outside the scene.
- Each upper probe value is the sum of its N upper rays divided by N. Upper ray slot: `base_(l+1) + p' * R_(l+1) + k * N + m` for m from 0 to N-1, where `p' = x + y * W_(l+1)`.
- Bilinear blend with `w = fract(f)`. Let s0 to s3 be the four probes in the order listed above. Then `r1 = s0 * (1 - wx) + s1 * wx`, `r2 = s2 * (1 - wx) + s3 * wx`, and the result is `r1 * (1 - wy) + r2 * wy`.

### Raymarch

Two modes. The mode is chosen by the DDA checkbox.

Fixed step (default):

- Start at `O = P + d * S_l`.
- Step size is `2^l * m` when mipmaps are on, and `m` otherwise, where `m = max(0.1, value / 100)`.
- Each sample is at `O + d * t`, in full-resolution pixels. Sample UV is position / 1024, with mip level l (or 0 when mipmaps are off).
- Stop when the distance from P is greater than `E_l`, or the position leaves the texture.

DDA:

- Grid traversal following the raycasting tutorial at lodev.org, which the source cites.
- Works in mip-level pixel coordinates (positions scaled by 1 / 2^l when mipmaps are on).
- Each visited cell is sampled at `cell_corner / dims` with mip l. The sample uses the cell corner, not the cell center.
- Stop when the cell is farther than `E_l` from P, or leaves the texture.

Accumulation (`AccumulateSample`):

- Linear (default): `acc.rgb += acc.a * s.rgb` and `acc.a *= (1 - s.a)`.
- Non-linear: `acc.rgb += acc.a * s.rgb` and `acc.a *= exp(-s.a * decay)`, with decay = value / 100.
- The step size argument is passed in but not used in either branch. Opacity is not scaled by step length.

### Fluence (BuildFluenceTexture)

- Each texel uses its pixel center `c`. Its probe cell is `floor(c / 1024 * W_0)`.
- Default output: the average of the R_0 level 0 rays of that probe. No interpolation is done between probes.
- Direction debug view: average only the rays whose line passes within about one pixel of the texel. The test uses `sdSegment`, from the Shadertoy source cited below.
- The store format is rgba8unorm, so values are clamped to 0 to 1 when written.

### Derived from reading the code (not stated by the author, not tested)

1. Level count off by one. The dispatch runs levels 0 to `levelCount` inclusive. The upper merge runs only when `l + 1 < levelCount`. So level `levelCount - 1` sees no upper term, and level `levelCount` is computed but never read. Fluence reads only level 0.
2. Ray id linearization. The dispatch splits work into x and y when the group count exceeds the per-dimension limit. The id formula still uses `gid.y * 256` and not `gid.y * (x groups * 256)`. This matters once the ray count passes 65,535 * 256 = 16,776,960. The maximum level 0 count, 16,777,216, is above that.
3. The guard uses `>` instead of `>=`, so one extra id is processed per dispatch.
4. Interval truncation. Interval values go through the JavaScript `<<` operator, which truncates to an integer. The default `s = 2.6` gives `I = 6.76`, which becomes 6 in the shifts and in the uniform. The label still shows 6.76. Default ends are 6, 24, 96, 384, 1536 and 6144 for levels 0 to 5.
5. Buffer overflow with branching factor 3. Total rays per level grow by 2 per level when B = 3. At the maximum level 0 settings, level 1 needs 2 * 16,777,216 slots, but its ping-pong half holds 16,777,216. The buffer has only 33,554,432 slots in total, so level 1 overruns it.
6. Default worked numbers (D0 = 2, R0 = 4, B = 2, I = 6, levels = 5): probe grids are 512, 256, 128, 64, 32 and 16 per side. Rays per probe are 4, 16, 64, 256, 1024 and 4096. Total rays per level stay at 1,048,576 for levels 0 to 5, so the per-level total is constant at B = 2.
7. The second bound check in `BuildFluenceTexture` uses `ubo.width` for y. This is only correct for a square canvas.
8. The 2D intro demos use `(sin, cos)` for ray direction. The GPU code uses `(cos, sin)`. The angle for each ray index is the same; only the axis convention differs.

### Limitations and notes stated in the source

- The top level contributes no upper term (sky or environment TODO).
- Probes near the edge reuse edge probes instead of reading outside the scene. A ring of out-of-bounds probes is the stated real fix.
- Uniform block alignment: a TODO says it must change if the block exceeds 256 bytes.
- Mapping the staging buffer for timing may take more than one frame (comment in the render pass).
- `rgba16float` is used because radiance values scaled by a multiplier are averaged in the mip chain.
- The debug timing UI prints per-pass milliseconds. The page gives no timing numbers.
- The source has no performance measurements and gives no hardware details.

## Demo 5: Screenspace probes with worldspace intervals (3D)

Page text: "Compute a storage cost table for screen-space probes with world space intervals." This is a calculator. It does not render anything.

| Control | Range | Default | Meaning |
|---|---|---|---|
| probe directions (world space) | 1 to 32 | 2 | Label shows d^2. Default 4 directions. |
| probe spacing (screen space) | 0 to 10 | 2 | Spacing is 2^s px. Default 4 px. |
| keep merged and unmerged cascades | checkbox | on | Doubles storage. The note says the data is used for reflections on GGX or similar rough surfaces. |
| place screenspace probes on min and max depth | checkbox | on | Doubles storage. The note says it helps scenes with thin objects and high depth complexity. |

Calculation (`Update`, runs when values change). For each resolution in 1920 x 1080, 2560 x 1440, 3840 x 2160 and 7680 x 4320:

- Grid: `gx = ceil(W / spacing)`, `gy = ceil(H / spacing)`. Cell count `gx * gy`.
- Bytes per level: cell count * directions. Times 2 if "keep unmerged" is on. Times 2 if "min and max depth" is on.
- Cascade levels: `ceil(log2(min(gx, gy)))`.
- Total: levels * bytes per level.
- Display: `NiceBytes` divides by 1024 while the value is at least 1, rounds up, and adds a unit (B, KB, MB, GB, TB).

Derived from the code: the header says "assuming 32bit vec4f(rgb, throughput)", but the formula has no 16-byte factor. The printed numbers count entries per level, not bytes.

Worked default at 1920 x 1080: grid 480 x 270 = 129,600 cells. Times 4 directions, times 2 times 2 = 2,073,600 entries per level. Levels: ceil(log2 270) = 9. Total: 18,662,400 entries.

The source header lists these open items: a basic calculation for cascade 0, the same calculation for other cascades, a doubling for min and max probes, and a doubling for pre-merged and raw data. The code already covers the last two with the two checkboxes.

## Demo 6: World-space probe storage table (3D)

Page text: "Compute a storage cost table for world space probes, using a ping-pong buffer, at various spatial resolutions." The formula on the page is `diameter^3 * rayCount * bytesPerRay * 2`, with rayCount = 6, bytesPerRay = 16, and a factor of 2 for ping-pong. The script hard-codes both constants.

The script builds one row for each diameter 2^d, with d from 4 to 10. Column "megabytes" is the full volume. Column "MB per slice" is one face, using diameter^2. MB here means 1024^2 bytes. The values below come from the same formulas:

| Diameter | Megabytes (volume) | MB per slice |
|---|---|---|
| 16 | 0.75 | 0.046875 |
| 32 | 6 | 0.1875 |
| 64 | 48 | 0.75 |
| 128 | 384 | 3 |
| 256 | 3072 | 12 |
| 512 | 24576 | 48 |
| 1024 | 196608 | 192 |

Derived: total bytes = diameter^3 * 192, and slice bytes = diameter^2 * 192.

## Links found

- Paper (linked as "paper") | https://drive.google.com/file/d/1L6v1_7HY2X-LV3Ofb6oyTIxgEaP4LOI6/view?usp=sharing | Paper linked from the page. Not fetched.
- Demo video (linked as "demo") | https://www.youtube.com/watch?v=xkJ6i2N32Pc | Video linked from the page: "Radiance Cascades Rendered Directly" ([notes](2022_sannikov_youtube_rc_videos.md#radiance-cascades-rendered-directly-2023)).
- Exilecon talk | https://www.youtube.com/watch?v=B-ODrtmtpzM | Talk linked from the page. The video is private; the public ExileCon 2019 renderer talk is https://youtu.be/whyJzrVEgVc ([notes](2019_sannikov_poe_gi_talks.md)).
- Radiance Cascades, Shadertoy by fad | https://www.shadertoy.com/view/mtlBzX | 2D implementation. The page says it has temporal latency because of Shadertoy limits.
- Radiance Cascades 2d Smooth WIP, Shadertoy by Suslik | https://www.shadertoy.com/view/mlSfRD | Fork of fad's work. The page calls it work in progress.
- Radiance Cascades, GM Shader Tuts by Yaazarai | https://mini.gmshaders.com/p/radiance-cascades | Written introduction linked from the page.
- Exploring a New Approach to Realistic Lighting: Radiance Cascades, SimonDev | https://www.youtube.com/watch?v=3so7xdZHKxw | Introductory video linked from the page.
- Radiance cascades calculator, kornel | https://kornel.ski/radiance | Computes cascade interval lengths from penumbra angle, minimum light size and probe spacing.
- sdSegment, Shadertoy 3tdSDj (MIT) | https://www.shadertoy.com/view/3tdSDj | Source of the segment distance function used in `BuildFluenceTexture`.
- Raycasting tutorial (lodev.org) | https://lodev.org/cgtutor/raycasting.html | Cited in the source for the DDA cursor setup.
- Radiance Cascades 3D, tmpvar | https://tmpvar.com/poc/radiance-cascades-3d/ | Other RC page listed on the POC index. Not fetched.
- radiance-cascades-3d-grid, tmpvar (GitHub) | https://github.com/tmpvar/radiance-cascades-3d-grid | "A rough implementation of Radiance Cascades using world space dense grids."
