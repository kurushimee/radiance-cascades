# Radiance Cascades: Building Real-Time Global Illumination

| | |
|---|---|
| Author | Jason McGhee |
| Date | 2024-08-31 |
| Kind | Article (interactive tutorial with WebGL demos); part 2 of a series |
| Link | https://jason.today/rc |

The page builds 2D radiance cascades (RC) step by step on top of a jump-flood distance field. It starts from the naive ray-marched GI of part 1, moves through the penumbra hypothesis and a two-pass ray budget, packs directions into pixels, and ends with a generalized N-cascade merge with sRGB handling and a light-leak clamp. Every step has a live canvas; the shader source of each step is embedded in the page. The final canvas is the `rc-fragment` shader driven by class `RC`.

Conventions: "Article" means the prose and snippets. "Code" means the embedded scripts. "Code note" marks observations from reading the code, not statements by the author. "Derived" marks numbers computed from the code's formulas with default settings.

## 0. Page layout and demos

The demos appear in this order on the page.

| Demo (canvas id) | Class and shader script id | Canvas | What it shows |
|---|---|---|---|
| one-pass-raymarch | OnePassRaymarch / `one-pass-raymarch-fragment` | 300x400 | Naive per-pixel raymarch from N rays, optional noise |
| penumbra-hypothesis-canvas | PenumbraHypothesis (extends OnePassRaymarch) | 300x400 | 512 rays, noise on, no sun |
| two-pass-raymarch | TwoPassRaymarch / `two-pass-raymarch-fragment` | 300x400 | Two passes: high ray count at half resolution, base ray count at full resolution |
| two-pass-raymarch-v2 | TwoPassRaymarchV2 / `two-pass-raymarch-fragment-v2` | 300x400 | Directions packed into probe texels |
| multi-pass-raymarch | MultipassRaymarch / `multipass-raymarch-fragment` | 300x400 | Generalized N-cascade merge |
| penumbra-hypothesis-canvas-rc | PenumbraHypothesisRC (extends MultipassRaymarch) | 300x400 | Multipass shader, no sun, fixed srgb 1.0 |
| radiance-cascades-canvas | RC (extends DistanceField) / `rc-fragment` | 512x512 default | Final demo with all controls |

## 1. Why the naive method is slow (article)

- Part 1 casts N rays at equal angles around a circle, adds noise to the angle, and sphere-marches each ray on a distance field.
- The stop condition is an epsilon test, which the author calls hand-wavy.
- Part 1 used 32 rays. Quality came from style and temporal accumulation.
- The author's cost estimate, not a measurement: a 1024x1024 canvas (about 1M pixels) at 512 rays is about 500M rays per frame. At about 10 steps per ray and about 2 texture lookups per ray, that is about 1B lookups. At 1 ns per lookup that is about 1 s per frame. A 60 fps target needs about 16 ms, so "roughly 100x faster" is needed.
- The author says the 16-ray naive setting costs roughly the same as radiance cascades, but has no noise.

## 2. Penumbra hypothesis (article)

For the shadow cast by an edge:
- The linear (pixel-space) resolution needed to capture an area is inversely proportional to that area's distance from the origin.
- The angular resolution needed is proportional to that area's distance from the origin.

Restated by the author: the farther the light, the more rays per pixel are needed and the fewer pixels need to be looked at.

Test shown by the author: with 4 rays, a black dot placed in a dark area is lost or misrepresented when far from the light. Raising the ray count step by step recovers it.

Design problem stated by the author:
- Raising the ray count mid-march is a branch, which the author says is not GPU friendly.
- The distance field already skips steps, so reducing resolution with distance is not obvious.

Answer used: split GI into passes. A high-resolution pass with few rays, and a low-resolution pass with many rays.

## 3. Build-up steps (article)

### 3.1 Two levels, ping-pong, interval split

Host loop (article):
- Inputs: distance field texture, scene texture, and `lastTexture` (the previous pass output, initially null).
- Passes alternate between two render targets (ping-pong), as in the multi-pass JFA of part 1.
- Loop: for i = 2 down to 1, set `rayCount = baseRayCount^i`. For i > 1, render into the ping-pong target and set `lastTexture` to it. For i = 1, render to the screen with `rayCount = baseRayCount`.
- The first configuration is 256 rays at 1/16 resolution, then 16 rays at full resolution (base 16).

Three shader changes (article):
1. Render at lower resolution.
2. Merge with the previous pass.
3. Start and stop the march at a chosen distance (an interval).

Step A, half resolution (article): the lower-resolution pass uses `effectiveUv = floor(coord/2)*2/resolution`. The author notes that 3 of every 4 rays are then redundant.

Interval rule (code, article snippet shows the same rule):
- Base-ray pass (rayCount == baseRayCount, full resolution): interval [0, partial].
- High-ray pass: interval [partial, sqrt(2)].
- `partial` starts at 0.125 (one eighth of UV space, the author's arbitrary choice). The max length is sqrt(2).
- Code note: the article text says the low-res pass starts at `partial`. The code does the reverse: the high-ray pass starts at `partial`. The code is what the demo runs.

Step B, probe packing (article, "Packing Direction in Pixels"):
- A probe is a group of pixels that share one ray origin (the probe center). For base 16 the high-ray pass runs on a grid with 4 px spacing (one probe per 16 pixels).
- Each probe casts `baseRayCount` rays per pixel of the downsampled grid, and the ray angles are offset per pixel.
- Total cost per output pixel is 2 x 16 = 32 raymarches, the same as the earlier 32-ray method. The author says the penumbra hypothesis predicts better accuracy here: 256 angular directions versus 32.
- Index variables (article snippet):
  - `sqrtBase = sqrt(baseRayCount)`
  - `spacing = (rayCount == baseRayCount) ? 1 : sqrtBase`
  - `size = floor(resolution / spacing)` (probes per axis)
  - `probeRelativePosition = mod(coord, size)`
  - `rayPos = floor(coord / size)` (which group of rays this texel holds)
  - `baseIndex = baseRayCount * (rayPos.x + spacing * rayPos.y)`
  - `angleStepSize = TAU / rayCount`
  - `probeCenter = (probeRelativePosition + 0.5) * spacing`
- Ray loop: for i in [0, baseRayCount), `index = baseIndex + i`, `angle = (index + 0.5) * angleStepSize`.

Step C, interval split as a slider (article): the slider is "Interval Split". Code: `intervalStart = (rayCount == baseRayCount) ? 0 : split`, `intervalEnd = (rayCount == baseRayCount) ? split : sqrt(2)`. The Interval Split slider in the V2 demo is 0 to 1, step 0.001, default 0.125.

Step D, merge with the upper cascade (article):
- Merge only in the lower pass (rayCount == baseRayCount) and only on non-opaque rays (radiance alpha == 0).
- Decode the upper texture:
  - `upperSpacing = sqrtBase`
  - `upperSize = floor(resolution / upperSpacing)`
  - `upperPosition = (mod(index, sqrtBase), floor(index / upperSpacing)) * upperSize`
  - `offset = (probeRelativePosition + 0.5) / sqrtBase`
  - sample `lastTexture` at `(upperPosition + offset) / resolution`
- Storage (article): 16 directions are stored in 16 quadrants of a 4x4 grid. Each quadrant is one upper tile.
- Article: index 0 of the cascade view starts at bottom-left, moves right, then up a row, with a clockwise rotation.

Step E, linear filter (article): sampling the upper texture gives a grid pattern because one point is sampled per pixel group. Setting the render target to linear filtering gives bilinear upscaling "for nearly free". A checkbox ("Use Linear Filter") compares the two.

Interval tuning (article):
- The ideal split is close to zero but not zero.
- About 0.02 (about 8 px) looks a bit too long but reasonable.
- The author's rule of thumb: half the probe width, which is 8 px for 16 px probes. Stated as probably too long and to be tuned.
- Shadows look offset in proportion to the upper interval offset. The author defers this, then says shadows look reasonable with a lower split.

Step F, the arithmetic for many cascades (article): with 16 px probes and 256 rays, the upper interval would need about 128 px, which needs another layer. This leads to the generalization.

### 3.2 Generalizing to N cascades (article)

Parameters:
- `base` (4 or 16 in the article), `cascadeIndex` k (0 is the lowest), `cascadeCount`.
- `shortestSide = min(resolution.x, resolution.y)`.
- `scale = shortestSide / resolution` (per axis). The stated purpose is to keep the rays on a unit circle for non-square resolutions.

Formulas (article):
- Ray count: `N_k = base^(k+1)`.
- Probe spacing in cascade texels: `spacing_k = sqrtBase^k` (1 for k = 0).
- Interval start: `start_k = 0` for k = 0, otherwise `base^(k-1) / shortestSide`.
- Interval length: `len_k = base^k / shortestSide`.
- Lowest cascade: starts at the probe center and covers 1 pixel.
- Merge: applies when `k < cascadeCount - 1` and the ray is non-opaque. The upper spacing is `upperSpacing = sqrtBase^(k+1)`.

Cascade count (article host code):
- `diagonal = sqrt(W^2 + H^2)`
- `cascadeCount = ceil(log(diagonal) / log(base)) + 1`
- Article example: 300x400 gives a longest ray of 500. With base 4, log4(500) is about 4.5, so at least 5 cascades. A light at the top-left did not reach the edge, so the author added one more layer and called it "the most naive way". The "+1" is that extra layer.

Extra modifier (article, appendix "Additional Hacks"):
- Artifacts are much worse at base 16. The author writes: "I either have a bug somewhere or am missing something regarding bases other than 4."
- Hack: multiply the interval start and length by `modifierHack = base < 16 ? 1.0 : sqrtBase`.

### 3.3 sRGB correction (article)

- Scene reads are linearized with an approximate gamma of 2.2, and the final output is encoded with 1/2.2.
- Reason given: WebGL uses sRGB, and light should be summed in linear space. A Shadertoy example (McSyWm) is linked.
- Author: this "produces a much brighter (accurate) result" and "illuminates a clear ringing artifact" of vanilla RC.

### 3.4 Light-leak clamp (article)

- Leak: with interval split 0, the merge reads across edges. The author shows it by drawing along an edge.
- Fix: clamp the probe offset so the sample stays inside the upper tile.
  - Article: `clamp(offset, 0.5, upperSize - 0.5)` (texel units).
  - Final demo: `clamp(offset, 1.0, upperSize - 1.0)` (see section 9).

### 3.5 Ringing (article)

- Seen with a single dot, especially with Correct sRGB on.
- Author: "still an active area of research". Fixes "incur a fair amount of overhead (as in doubling the frame time) or cause other artifacts".
- The penumbra appendix shows subtle ringing in the shadow.
- The final page has a "Ringing Fix" checkbox. It is hidden (`display: none`), and the code reads it into `this.ringingFix` and never uses it. There is no ringing fix in the shipped code.

## 4. Final demo: full algorithm (`rc-fragment`, class `RC`)

### 4.1 Sizes and query parameters

Query parameters:
- `width` (default 512 on desktop, 300 on mobile)
- `height` (default 512 on desktop, 400 on mobile)
- `pixelRatio` (default 2; called `dp` in code)
- `rcScale` (default equal to pixelRatio)
- `autosize=true` scales the CSS size when the canvas is wider than the window minus 80 px

Derived sizes (code):

| Quantity | Formula | Default |
|---|---|---|
| Simulation size W_s, H_s (drawing, JFA, DF, RC textures) | `pixelRatio * width / rcScale` (not rounded in code) | 512 |
| Backing store of the canvas | W_s x rcScale (equals pixelRatio x width) | 1024 |
| CSS size | W_s x rcScale / pixelRatio (equals width) | 512 |
| High-res drawing target and overlay target | W_s x rcScale | 1024 |
| Probe-grid extent E (all cascades) | floor(W_s / P), P = pixels between base probes | 512 |

Code note: the RC render targets are allocated at the simulation size (`width x height`, no scale), not at the probe-grid extent. Only the probe indexing uses the extent. Sampling is normalized by the extent, so the texels beyond the extent repeat. The article does not discuss this.

Brush radius: the default is `4 * pixelRatio` = 8 (drawing px). The simulation-pass radius is the brush radius divided by rcScale (derived from the drawing shader).

Sampling of the scene: the RC reads the low-resolution painted scene. The overlay reads the high-resolution painted scene for display (section 4.6).

### 4.2 Host parameters and derived cascade count

Code (`initializeParameters`):
- `angularSize = sqrt(W_s^2 + H_s^2)` (simulation size, not divided by P).
- `radianceCascades = ceil(log(angularSize) / log(4)) + 1`. The base 4 is a literal in the code. Changing the Base Ray Count slider does not recompute this.
- `basePixelsBetweenProbes P = 2^exponent` (exponent 0 by default, so P = 1).
- `radianceInterval (cascadeInterval) = 1.0`.
- `cascadeExtent = (floor(W_s / P), floor(H_s / P))`.

Derived: 512x512 at base 4 gives angularSize 724.08, log4 about 4.75, ceil 5, plus 1 = 6 cascades (k = 0..5).

Pixels-between-probes slider: setting it re-runs `initializeParameters(true)`, which also resets the cascade count uniform to `radianceCascades`.

### 4.3 Per-frame pipeline (`doRenderPass`)

1. Draw (Drawing base class): stroke segments are drawn on the GPU into the simulation-size target and into the high-resolution target. The brush paints where the squared distance to the segment is at most r^2. A thin white outline is drawn for the cursor indicator.
2. Seed: `seedPass(drawPassTexture)`. Each texel outputs `(vUv * round(alpha), 0, 1)`. Occupied texels (alpha rounded to 1) store their own UV in xy. Empty texels store 0.
3. JFA: `passes = ceil(log2(max(W_s, H_s)))` (9 for 512). Pass i uses offset `2^(passes - 1 - i)` texels. Each texel samples the 3x3 neighborhood at that offset (out-of-range samples skipped), and keeps the stored seed with the smallest squared UV distance to `vUv`. Ping-pong between two targets.
4. Distance field: `texel = floor(vUv * resolution)`, `nearest = JFA(texel).xy`, `dist = clamp(|vUv - nearest|, 0, 1)` written to the red channel. Distances are in UV units.
5. RC cascades: section 4.4 and 4.5.
6. Overlay and display: section 4.6.

The RC `animate()` loop keeps rendering for about 1 s after the last mouse event (`lastRequest` timeout), then stops.

### 4.4 `rc-fragment` uniforms (values set by the host)

| Uniform | Set to | Default |
|---|---|---|
| resolution | (W_s, H_s) | 512, 512 |
| sceneTexture | low-res painted scene, rebound each pass | |
| distanceTexture | DF texture, set each pass | |
| lastTexture | previous cascade output (null for the first pass of a frame in full mode) | |
| cascadeExtent | (floor(W_s/P), floor(H_s/P)) | 512, 512 |
| cascadeCount | radianceCascades, or the Layer Count slider | 6 |
| cascadeIndex | loop variable k | |
| basePixelsBetweenProbes | P | 1 |
| cascadeInterval | 1.0 | 1.0 |
| rayInterval | Interval Length slider | 2.0 |
| intervalOverlap | Interval Overlap slider | 0.04 |
| baseRayCount | 4^slider | 4 |
| addNoise | Naive GI Noise checkbox | false |
| enableSun | Sun button | false |
| sunAngle | Sun Angle slider | 4.2 |
| srgb | 2.2 if Correct sRGB is checked, else 1.0 | 1.0 |
| firstCascadeIndex | Layer to Render slider | 0 |
| lastCascadeIndex | declared in the shader, never set or used | |
| time | set to 0.1 in JS, not declared in the shader | |

Constants in the shader: `SQRT_2 = 1.41` (this rounded value, not the exact root), `PI = 3.14159265`, `TAU = 2 PI`, `sunDistance = 1.0`, `skyColor = (0.2, 0.24, 0.35) * 6`, `sunColor = (0.95, 0.9, 0.8) * 4`.

Raymarch loop safety: at most 100 iterations.

### 4.5 `rc-fragment` algorithm

Restated in pseudocode. Symbols: k = cascadeIndex, b = baseRayCount, r = sqrt(b), s = r^k (spacing), N = b^(k+1) (ray count), E = cascadeExtent, R = resolution (simulation size), P = basePixelsBetweenProbes, top = cascadeCount - 1.

```
coord = floor(uv * E)
if k == 0 and scene(uv).a > 0: output scene(uv) unchanged, stop

modifier = (b < 16) ? P : r                      # article: 1.0 instead of P
size = floor(E / s)
probe = coord mod size
tile  = floor(coord / size)
modInt = modifier * rayInterval * cascadeInterval
start  = (k == 0) ? cascadeInterval : modInt
prev   = b^(k-1)
offsetUV = start * prev / R                      # per axis
L = modInt * ((b^k - prev) + overlap * b^(k+1) / 1.41)
center   = (probe + 0.5) * P * s
centerUV = center / R
scale = min(R.x, R.y)
invR = 1 / R
minStep = 0.5 * min(invR)
baseIdx = b * (tile.x + s * tile.y)
dstep = 2*PI / N
noise = addNoise ? rand(uv * (k+1)) : 0
acc = 0
for i in 0 .. b-1:
    idx = baseIdx + i
    ang = (idx + 0.5 + noise) * dstep
    d = (cos(ang), -sin(ang))
    hit = raymarch(centerUV, d, scale, invR, offsetUV, L, minStep)
    m = merge(hit, idx, probe, r)
    if enableSun and k == top:
        m.rgb = max(sun(ang), m.rgb)              # applied to every ray, no hit test
    acc += m / b
out.rgb = (k > firstCascadeIndex) ? acc.rgb : pow(acc.rgb, 1/srgb)
out.a   = acc.a
```

Raymarch:

```
raymarch(p, d, scale, invR, offset, L, minStep):
    uv = p + d * offset
    if uv is outside [0,1)^2: return 0
    stepVec = d * scale * invR
    dist = 0
    repeat (max 100) while dist < L:
        df = DF(uv).r
        if df <= minStep:
            c = scene(uv)
            c.rgb = (c.a < 0.99) ? 0 : pow(c.rgb, srgb)
            return c
        dist += df * scale
        if dist >= L: break
        uv += stepVec * df
        if uv is outside [0,1)^2: break
    return 0
```

Merge:

```
merge(r, idx, pos, rs):
    if r.a > 0 or k >= top: return r
    up = rs^(k+1)
    upSize = floor(E / up)
    upPos = (idx mod up, floor(idx / up)) * upSize
    o = clamp((pos + 0.5) / rs, 1, upSize - 1)    # article: clamp to 0.5 and upSize - 0.5
    return r + textureLod(last, (upPos + o) / E, (P == 1) ? 0 : log2(P))
```

Sun and sky (`sunAndSky`, used when Naive GI Noise is off):
- `t = mod(angle - sunAngle, TAU)`
- `I = max(0, cos t)^4`
- `result = mix(sunColor * I, skyColor, 0.3)`

Old sun (`oldSunAndSky`, used when Naive GI Noise is on):
- `t = mod(angle - sunAngle, TAU)`
- `I = smoothstep(1.0, 0.0, t)`
- `result = (0.95, 0.95, 0.9) * I + (0.02, 0.08, 0.2)`

Noise: `rand(co) = fract(sin(dot(co, (12.9898, 78.233))) * 43758.5453)`.

Index math for the stored layout (direct from the formulas):
- A cascade texture (extent E) is a grid of s x s tiles, each tile `floor(E / s)` texels wide.
- Tile index `T = tile.x + s * tile.y`, numbered from bottom-left, x fastest. There are s^2 = b^k tiles.
- A texel is a probe, at position `probe` within its tile. Probe count per cascade is `(E/s)^2`.
- A texel in tile T stores the average of the b rays with indices `b*T + i`.
- Ray angle for index idx is `(idx + 0.5) * 2*PI / N_k`.
- Derived: the upper cascade has `N_k = b^(k+1)` tiles, one per lower ray index. The lower index `idx` addresses upper tile `idx` directly, through `(idx mod up, floor(idx / up))`.
- Derived: upper ray `b*idx + i` has angle `(idx + (i + 0.5)/b) * 2*PI / N_k`. So the b upper rays averaged in tile `idx` cover the angular bin of width `2*PI/N_k` that lower ray `idx` is centered in. The source does not state this.
- Derived: each cascade casts `b * E^2` rays per frame in full mode (probes times rays per probe: `(E/s)^2 * b^(k+1)`).

### 4.6 Cascade loop, frame modes, and overlay

`rcPass(DF, sceneTex)`:
- Binds the DF and scene textures.
- If `frame == 0`, sets `lastTexture = null`.
- `halfway = floor((firstLayer - lastLayer) / 2)`.
- `stop = (frame == 0 and not fullPass) ? halfway + 1 : lastLayer`.
- For k from `firstLayer` down to `stop`: set `cascadeIndex = k`, render into `RT[prev]`, set `lastTexture = RT[prev]`, toggle `prev`.
- Returns `RT[1 - prev]`.
- `firstLayer = radianceCascades - 1` (or Layer Count minus 1). `lastLayer = Layer to Render value`.

Full mode (Reduce Demand off, the default): `frame` stays 0. Every frame runs seed, JFA, DF, and all cascades from `firstLayer` to `lastLayer`.

Reduce Demand mode (checkbox on): `frame` alternates each pass.
- Frame 0: seed, JFA and DF run. The loop runs from `firstLayer` down to `halfway + 1`. The overlay uses the previous overlay output (`OT[0]`) as the RC input and writes `OT[1]`, so the new partial RC result is not displayed on that frame.
- Frame 1: the DF from frame 0 is reused. The loop runs from `firstLayer` down to `lastLayer`, reading only cascades computed in that same frame. The overlay uses the fresh RC output.
- Code note: the code never reads the frame-0 cascade results on frame 1, so frame 0's partial cascades do not feed frame 1. The article has only the label "Reduce Demand (Calculate over 2 frames)" and no explanation of the intent.

`doRenderPass`:
- If `frame == 0`: if Stage == 0, show the scene and stop. Otherwise run seed and JFA; if Stage == 1, show JFA and stop. Otherwise run DF; if Stage == 2, show DF and stop.
- Run `rcPass`, then `overlayPass`, then toggle `frame` (only in Reduce Demand mode).

`overlayPass(rc)`:
- Overlay target is rcScale times the simulation size (2x by default) with linear filtering.
- Overlay shader: `out = (painted && showSurface) ? highResPaint.rgb : rc.rgb`, alpha 1. `painted` is `highRes.a > 0`. `showSurface` is true only when Layer to Render is 0.
- The display plane samples the overlay target and draws the brush cursor indicator on top.
- The RC output textures use `LinearMipmapLinearFilter` for minification, `LinearFilter` for magnification, and `generateMipmaps: true`. So the cascades are sampled bilinearly, and `textureLod` takes a mip level. The article only states the linear filter for the V2 demo.

### 4.7 Paint semantics (code)

- Alpha 1 texels are both occluders and emitters: their color is linearized (when srgb is 2.2) and used as radiance.
- Partially transparent texels (alpha in [0.5, 0.99)) are occluders with zero radiance.
- Erased texels (alpha 0) are not seeds and do not occlude.

## 5. Interactive controls (final demo)

| Control | Element or name | Default | What it changes |
|---|---|---|---|
| Correct sRGB | `#enable-srgb` | off | srgb 2.2 when on, 1.0 when off. On: scene reads are linearized and the displayed cascade output is encoded. Off: all math on encoded values. The article says turning it on exposes ringing. |
| Naive GI Noise | `#add-noise` | off | On: each ray angle is offset by `rand(uv*(k+1))` (up to one ray step). Top-cascade sun uses the old sun function. |
| Ringing Fix | `#ringing-fix` | hidden, off | Read into `this.ringingFix`, never used. No effect. |
| Sun Angle | `#rc-sun-angle-slider` | 4.2 (range 0 to 6.2, step 0.1) | `sunAngle`. Disabled until the sun is on. |
| Sun button | `radiance-cascades-canvas-sun` | off | `enableSun`. Enabling it also enables the Sun Angle slider. |
| Reduce Demand | `#reduce-demand` | off (full mode) | Two-frame mode, section 4.6. |
| Pixels Between Base Probes | slider, exponent 0 to 4 | exponent 0, so 1 px (range 1 to 16 px) | P. Recomputes extent and resets the cascade count to `radianceCascades`. |
| Interval Length | slider 1 to 512, step 0.1 | 2.0 | `rayInterval`. |
| Base Ray Count | slider, values 1 to 3 | 4 (values 4, 16, 64) | `baseRayCount`. Does not recompute the cascade count. |
| Interval Overlap % | slider 0 to 2, step 0.01 | 0.04 | The overlap term in the interval length. |
| (RC) Layer to Render | slider 0 to radianceCascades - 1 | 0 | `firstCascadeIndex` and `lastLayer`. Shows RC-only output when not 0. |
| (RC) Layer Count | slider 1 to radianceCascades | radianceCascades | `cascadeCount` and `firstLayer = value - 1`. |
| Stage To Render | slider 0 to 3 | 3 | 0 scene, 1 seed and JFA, 2 adds DF, 3 full. |

## 6. Earlier demo shaders (what each step adds)

### 6.1 One-pass naive (`one-pass-raymarch-fragment`)

- Ray count `2^slider` (slider 2 to 10, default 5, so 32 rays). Max 32 march steps.
- For each unpainted pixel (alpha below 0.001): `angle = TAU/N * (i + offset + 0.5)`, where `offset = rand(uv)` when noise is on.
- Hit test is strict: `dist < minStep` (0.5 texel). A hit adds the pixel color with alpha 1.
- When sun is on, `sunAndSky(angle)` is added to every ray (no hit test).
- Output `max(paint, radiance / N)`. The `srgb` constant is 1.0.

### 6.2 Penumbra, naive

- Same shader as 6.1 with 512 rays, noise on, no sun.

### 6.3 Two-pass (`two-pass-raymarch-fragment`)

- Two passes. Base pass: `rayCount = baseRayCount` (default 16 for base 16), full resolution, interval [0, partial]. High-ray pass: `rayCount = base^2` (256), coordinates quantized with `floor(coord/2)*2`, interval [partial, sqrt(2)].
- Merge: only in the base pass and only on rays with alpha 0. The merge samples `lastTexture` at the same UV and adds the upper result after linearizing it. No probe packing here.
- `srgb` constant 2.2. Output is always encoded with 1/2.2.
- Slider: Base Ray Count, values 4 or 16 (default 16). `intervalPartial` is 0.125 with no slider.

### 6.4 Two-pass V2, packed (`two-pass-raymarch-fragment-v2`)

- Probe packing as in section 3.1 Step B. `spacing = 1` for the base pass and `sqrtBase` for the high-ray pass. Each texel is a probe.
- Base pass: `intervalStart = 0`, `intervalEnd = partial`. High-ray pass: `intervalStart = partial`, `intervalEnd = sqrt(2)`.
- Merge only in the base pass (`firstLevel`) on non-opaque rays. Sample `lastTexture` at `(upperPosition + offset) / extent`, with `offset = (pos + 0.5) / sqrtBase`. No clamp in this version.
- Output: `radiance / base`. Encoded with 1/2.2 only on the last pass (`lastIndex`); intermediate passes stay linear.
- Sun: added only on the last pass and only on non-opaque rays.
- Sliders: Base Ray Count (4 or 16, default 16), Cascade Index (0 or 1, default 0; 1 renders the upper cascade directly), Interval Split (0 to 1, step 0.001, default 0.125).
- Use Linear Filter (off by default): rebuilds the render targets with linear filtering. Initial state is nearest, matching the unchecked box.

### 6.5 Multi-pass N-cascade (`multipass-raymarch-fragment`)

- `base` uniform from the slider (4 or 16, default 4). `rayCount = base^(k+1)`. Spacing `sqrtBase^k`. Probe centers have no `P` factor in this version.
- `modifierHack = base < 16 ? 1 : 4` (literal 4 in code).
- `intervalStart = (k == 0) ? 0 : modifierHack * base^(k-1) / shortestSide` and `intervalLength = modifierHack * base^k / shortestSide`. Ray length is counted from the start point (`traveled = 0`).
- Merge: applies when `k < cascadeCount - 1` and the ray is non-opaque. Sun applies when `k == cascadeCount - 1` and the ray is non-opaque, using `max` on rgb.
- Output: `radiance / base` with alpha forced to 1. Encoded with `1/srgb` on the last pass only.
- Host loop: `cascadeCount = ceil(log(diagonal)/log(base)) + 1`. The loop runs k from `cascadeCount` down to `lastRenderPassIndex`, one more than the article snippet (see section 9).
- Correct SRGB checkbox (`#multipass-enable-srgb`) is checked by default, so srgb 2.2 is the default here.
- The Cascade Index slider's max is `ceil(log(min(W,H))/log(base)) + 1 - 1`, computed with the shorter side, while rcPass uses the diagonal.

### 6.6 Penumbra with RC (`PenumbraHypothesisRC`)

- Uses the multipass shader with `srgb` fixed at 1.0, linear filtering, base 4, no sliders, colors light, black and erase.

## 7. Artifacts and fixes (as stated or shown)

| Artifact | Where | Cause (source) | Fix (source) |
|---|---|---|---|
| Grid pattern | Upper cascade in packed pass | One sample per pixel group | Linear filter on the render target, giving bilinear upscale |
| Light leak across edges | Merge with interval split 0 | Sample reads outside the upper tile near an edge | Clamp the upper sample offset inside the tile |
| Ringing | Single dot, especially with Correct sRGB | Vanilla RC; author calls it an active research problem | No fix in source. Some known fixes double frame time or add other artifacts (author). Ringing Fix control is hidden and unused. |
| Subtle ringing in shadows | Penumbra appendix | Not explained | Not fixed in source |
| Shadows offset | Packed pass | Proportional to upper interval offset | Lower interval split; author says shadows then look reasonable. Not otherwise resolved. |
| Light not reaching the far edge | Light at top-left, 300x400 | Cascade reach shorter than the diagonal | One extra cascade: `ceil(log_base(diag)) + 1` |
| Worse artifacts at base 16 | Base 16 | Unknown (author suspects a bug or a missing piece) | `modifierHack` multiplier on intervals |
| Noise | Naive method | Random angle jitter and too few rays | Packed rays (deterministic). The Naive GI Noise checkbox re-adds jitter for comparison. |
| Dots lost at few rays | Penumbra test | Angular under-sampling | More rays at coarser probes (penumbra hypothesis) |

## 8. Performance notes

- Article estimates (section 1): about 500M rays per frame at 1024x1024 with 512 rays. About 1B lookups. About 1 s per frame at 1 ns per lookup. Target 16 ms. "Roughly 100x" needed.
- Article claim: 16 RC rays cost roughly the same as the naive method's 16 rays, and the result has no noise.
- Article claim: the two-pass design costs 2 x 16 = 32 raymarches per pixel, the same as the 32-ray method.
- Article: the linear filter upscale is "nearly free".
- Article: some ringing fixes roughly double frame time.
- No measured timings are reported anywhere. Every demo constructs `GPUTimer(renderer, true)`, which disables the timer extension. No hardware is named.
- Performance options listed on the page:
  - Pixels Between Base Probes set to 2 (or more).
  - `rcScale` above 1 (renders the radiance at a lower scale).
  - `pixelRatio` set to 1 (draws at 1x).
  - Reduce Demand (two-frame mode).
- Render targets default to half float. A `#full-precision` checkbox is referenced in code but not present on the page, so the default half-float path is always taken (except JFA targets above 1024 px on non-mobile).
- Mobile defaults: 300x400.
- Derived (section 11): full mode casts b x E^2 rays per cascade per frame.

## 9. Limitations, open problems, and code/article differences

### 9.1 Limitations stated by the author

- The naive method cannot reach 512 or 1024 rays in real time at large resolutions.
- Ringing is unresolved. Fixes have costs.
- Bases other than 4 are not understood. The hack in 3.2 helps but is not explained.
- Shadow offset from the upper interval is deferred, then improved only by tuning the split.
- The extra cascade is "the most naive way" to reach the far edge.
- Subtle ringing in penumbra shadows.
- The post calls the method still under active research and mentions 3D RC work by others, with no details.

### 9.2 Differences between article text and final code

1. Interval modifier: article `base < 16 ? 1.0 : sqrtBase`. Final code `base < 16 ? P : sqrtBase`. Multipass demo uses `base < 16 ? 1 : 4`.
2. Merge clamp: article `[0.5, upperSize - 0.5]`. Final code `[1, upperSize - 1]`. V2 has no clamp.
3. Cascade 0 interval start: article 0. Final code `1 * base^-1` (0.25 px for base 4).
4. Output encoding: article snippet encodes when `cascadeIndex > firstCascadeIndex`. Final code encodes when `cascadeIndex <= firstCascadeIndex` (the display cascade). These are opposite conditions.
5. Output alpha: article snippet sets alpha to 1. Final `rc-fragment` keeps `acc.a`. Multipass demo forces alpha 1.
6. Sun: final `rc-fragment` applies sun to every top-cascade ray with no non-opaque test. Multipass demo applies it only to non-opaque rays.
7. Top-cascade loop: article loops from `cascadeCount - 1`. Multipass demo loops from `cascadeCount`. The extra top pass is never merged, because the shader's merge condition is false for both `cascadeCount - 1` and `cascadeCount`.
8. Cascade count: final `rc-fragment` uses log base 4 regardless of Base Ray Count. Multipass uses the chosen base, with the shorter side for the slider limit and the diagonal in rcPass.
9. Penumbra text: article says the low-res pass starts at `partial`. Code runs the high-ray pass from `partial`.
10. Reduce Demand: the article does not describe the scheme (section 4.6).

## 11. Derived values (default settings)

Settings: simulation 512x512, pixels between probes 1, base 4, interval length 2.0, overlap 0.04, cascade interval 1.0, modifier 1 (base below 16 uses P = 1). Values computed from the code's formulas, not stated by the author.

| k | Rays per probe N | Spacing s (px) | Probes per axis E/s | Tiles s^2 | Interval start (px) | Interval end (px) |
|---|---|---|---|---|---|---|
| 0 | 4 | 1 | 512 | 1 | 0.25 | 1.977 |
| 1 | 16 | 2 | 256 | 4 | 2 | 8.908 |
| 2 | 64 | 4 | 128 | 16 | 8 | 35.63 |
| 3 | 256 | 8 | 64 | 64 | 32 | 142.5 |
| 4 | 1024 | 16 | 32 | 256 | 128 | 570.1 |
| 5 | 4096 | 32 | 16 | 1024 | 512 | 2280 |

Notes:
- Cascade 0 start: `1 * 4^-1 = 0.25`. Its end: `0.25 + 2 * ((1 - 0.25) + 0.04 * 4 / 1.41)`.
- Each cascade casts `b * E^2 = 4 * 512^2 = 1,048,576` rays per frame in full mode. Six cascades give about 6.3M rays per frame.
- With overlap 0, each interval would end at `modInt * base^k`.

## Links found

- Radiance Cascades Paper | https://github.com/Raikiri/RadianceCascadesPaper | Paper repository, named in the acknowledgements.
- Yaazarai's blog post | https://mini.gmshaders.com/p/radiance-cascades | Blog post with the biggest direct influence on this work, per the author.
- Post as Markdown (gist) | https://gist.github.com/jasonjmcghee/0c72d185830685f67d3b8d9c7f330c3a | The article with canvases replaced by code. It is an earlier version: it lacks "Packing Direction in Pixels", "Nailing the Details" and "Generalizing to Many Cascades", the `intervalOverlap` slider and term, and the `alpha < 0.99` threshold, while its other values match (32-ray naive demo, base slider `4^value`, the 512-ray example on 1024²). The gist f71708c18ee3604e8249ccb824275fbc (`.4k-rc.md`) has all sections but still predates the overlap term, its 0.04 default, the 0.99 threshold and `SQRT_2 = 1.41`.
- Part 1 | https://jason.today/gi | Raymarching, JFA, distance fields; see [2024_mcghee_building_realtime_gi_part1.md](2024_mcghee_building_realtime_gi_part1.md).
- Shadertoy McSyWm | https://www.shadertoy.com/view/McSyWm | Example of why sRGB math should be done in linear space (section 3.3).
