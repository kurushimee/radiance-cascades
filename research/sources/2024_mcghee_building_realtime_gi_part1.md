# Building Real-Time Global Illumination: Part 1

| | |
|---|---|
| Author | Jason McGhee |
| Date | 2024-07-27 |
| Kind | article (interactive blog post; the WebGL demos and their GLSL shaders are inline in the page) |
| Link | https://jason.today/gi |

Part 1 of a two-part series on 2D global illumination (GI). It builds a "naive" GI method in three.js: a paintable scene, brute-force raymarching, a jump flood algorithm (JFA) that produces a distance field (DF), and a marcher that steps through that field. Part 2 is [2024_mcghee_building_realtime_gi_part2_rc.md](2024_mcghee_building_realtime_gi_part2_rc.md).

## 1. Drawable surface

Strokes are painted into a float scene texture S. Each pixel holds rgb = paint color and a = 1 when painted, a = 0 when empty.

GPU stroke pass (inline fragment shader in `Drawing.initializeSmoothSurface`):

- Reads: previous scene (`inputTexture`), `color`, segment endpoints `from` and `to` in pixels, `radiusSquared`, `resolution` (W, H), and the `drawing` flag.
- Per pixel: copy the input. If `drawing` is true and the squared distance from the pixel to the segment is at most `radiusSquared`, write `vec4(color, 1.0)`.
- Segment distance (`sdfLineSquared`): project the pixel onto the segment, clamp the projection parameter t to [0, 1], and return the squared length of the remainder. Squared values avoid a `sqrt`.
- Both endpoint y values are flipped (`height - y`) before upload, because canvas y grows downward and uv y grows upward.

Texture settings: RGBA, `THREE.FloatType` (32-bit float per channel), NearestFilter, ClampToEdgeWrapping. Each pass has two targets used as a ping-pong pair. Targets are cleared with `renderer.clearColor()`; the source sets no clear color.

## 2. Naive raymarching

Idea: for each empty pixel, cast several rays at equal angles, walk each ray one pixel per step, and average the colors of the first lit pixel each ray hits.

Article version, in steps:

1. If the pixel is painted (alpha > 0.1), return its own color. Painted pixels cannot receive light in this method.
2. Set `oneOverRayCount = 1 / N` and `tauOverRayCount = TAU / N`.
3. Set `noise = rand(uv)`, a per-pixel value in [0, 1).
4. For each ray i in 0 .. N-1: `angle = TAU/N * (i + noise)`; direction = `(cos angle, -sin angle) / size`, so one step moves one pixel.
5. Start at `uv + direction`. For each step: stop if outside [0, 1]^2; read the scene at the sample; if alpha > 0.1, add the sample to radiance and stop; otherwise move one step.
6. Return radiance / N.

Script version (`naive-raymarch-shader`) differences:

- `noise = rand(uv)` when `showNoise` is on, and the constant 0.1 when it is off.
- The sample for step k is `uv + direction * k`. Steps run from `initialStep` to `maxSteps - 1`. `initialStep` is 0 when `accumRadiance` is on, and `maxSteps - 1` when it is off. With it off, each ray tests one texel at `maxSteps - 1`, so the rays show up as separate dots.
- The hit test is alpha > 0.5. The early return for painted pixels stays at 0.1.
- This shader has no sun or sky term.
- Demo values: N = 8 (`rayCount: 8`), maxSteps from the slider (default 128, range 0 to 512), both toggles on by default.

Author's statements:

- The demo casts 8 rays per pixel and light spreads at most 256 pixels.
- The loop does a lot of overlapping work, but neighboring pixels run in parallel and cannot share results directly. This motivates the JFA approach.
- The author says the core loop is nearly the same as far more efficient methods.
- The random offset avoids aligned rays and visible repeating patterns. The author says the goal is not to use noise, and that any cheap noise works.

## 3. Jump flood algorithm (JFA)

Goal: for each pixel, store the uv of the nearest painted pixel (its seed).

Seed pass (`jfa-seed-shader`):

- Output = `vec4(uv * a, uv * (1 - a))`, where a is the paint alpha.
- Painted pixels: rg = uv. Empty pixels: rg = (0, 0).
- Only rg is read later.

Pass count:

- P = `ceil(log2(max(W, H)))`. For 300 x 300 and 300 x 400 this is 9.

Jump pass i = 0 .. P-1 (`jfa-shader`):

- Offset `o_i = 2^(P - 1 - i)` pixels. For P = 9 the offsets are 256, 128, 64, 32, 16, 8, 4, 2, 1. Offsets shrink over time.
- Uniforms: `inputTexture`, `oneOverSize` (1/W, 1/H), `uOffset` (o_i), `skip`.
- Look at the 3 x 3 grid of samples at `uv + (dx, dy) * o_i / (W, H)` with dx and dy in {-1, 0, 1}. The grid includes the center.
- Skip samples outside [0, 1]^2.
- A sample counts if its rg is not (0, 0).
- Keep the counted sample whose stored seed point is nearest to the current uv (squared distance via `dot`).
- Output: rg = that seed's uv, ba = 0. If no sample qualifies, output (0, 0).
- No early exit. The author's reason: "closer" depends on the stored seed, not on how far the jump went.

Ping-pong: two targets. Pass 0 reads the seed texture; each later pass reads the previous output. The author's reason: reads and writes cannot share a target during a pass.

Demo: "No Passes" shows the uv map (the `skip` path). The JFA slider sets how many passes run, from 0 to 9, with 5 as the HTML default. The offsets still come from P, so a partial run uses the largest offsets first.

## 4. Distance field (DF)

`dfa-shader`:

- `d = clamp(distance(uv, JFA.rg), 0, 1)`, with distance in uv units.
- Output: `vec4(d, d, d, 1)`.
- The clamp keeps distances beyond one uv unit at 1.
- The DF demo always runs all P passes, because `jfaPassesCount` returns P.

## 5. Naive GI with the distance field

Per empty pixel (`gi-fragment-shader`, class GI):

1. Ray count N = 32 (`let rayCount = 32.0`); `angleStep = TAU / N`.
2. `offset = showNoise ? rand(uv + coef) : 0`, where `coef = time` when temporal accumulation is on, else 0.
3. Ray angle for ray i: `angle_i = stepAngle * (i + offset) + sunAngle`. `stepAngle` is `angleStep` (an optional "sand grain" mode adds `offset * TAU` to it).
4. Ray direction = `(cos angle, -sin angle)`, in uv units (not divided by size).
5. Start at `p = uv`. For `step = 1 .. maxSteps - 1`:
   a. `d = DF(p).r` (nearest-texel sample).
   b. `p = p + direction * d`.
   c. If p is outside [0, 1]^2, stop with no hit.
   d. If `d < EPS` (0.001), add the scene color at p to radiance, mark a hit, and stop. The distance is read before the move, and the color is read after it.
6. If there was no hit and sun is enabled, add `(sunColor * intensity + skyColor, 1)`.
7. Sum over all rays.

After the loop, per pixel:

- Painted pixels (alpha >= 0.1) are not marched. If `length(rgb) >= 0.1`, the pixel's radiance is its own color (emitter). Otherwise its radiance is zero (occluder). In the palette, only #000000 falls below the threshold.
- `out.rgb = max(scene.rgb, radiance.rgb / N)`. Alpha is set to 1.
- With temporal accumulation active and time > 0: `out = mix(out, previous, 0.9)`.

Derived cost at default settings (32 rays, maxSteps 32): at most 31 DF reads per ray, so at most 992 per empty pixel, plus one scene read per hit.

Author's statement: with the DF, maxSteps "can be way smaller" (32 instead of 256), and it controls quality and scales with canvas size.

## Sun and sky (bonus)

- `angleToSun = mod(angle - sunAngle, TAU)`.
- `intensity = smoothstep(1.0, 0.0, angleToSun)`.
- `sunAndSky = sunColor * intensity + skyColor`.
- sunColor = (0.95, 0.95, 0.9); skyColor = (0.02, 0.08, 0.2).
- The sky term is constant. The sun term depends only on the ray angle.
- Sun and sky are added only to rays that did not hit a surface, and only when sun is enabled.
- Author's statement: most sky models they found were complicated or copied; this one is their own simple approach.

## Temporal accumulation (bonus)

- Adds `time` to the noise seed: `rand(uv + time)`. `time` increases by 1 per accumulated frame.
- Mixes each new frame with the previous accumulated frame: `out = mix(new, previous, 0.9)`. The history keeps weight 0.9.
- Accumulation runs while `time < 10` (`accumAmt = 10`). When the limit is reached, the next render resets time to 0, does not blend, and the animation loop stops.
- Accumulation pauses while the user draws (time is reset on each stroke event), while a slider is pressed (`drawingExample` flag), and while the toggle is off.
- Two ping-pong GI targets hold the history. The first GI render writes to the history target; the screen then renders again with time already incremented.
- Author's statements: it is "basically a hack to deal with noise", Radiance Cascades does not need it, and it costs a render-target switch and an extra texture lookup per frame.

## Code structure

Classes:

| Class | Extends | Role |
|---|---|---|
| PaintableCanvas | none | 2D canvas and CanvasTexture, pointer handling, stroke smoothing, CPU fallback (base `useFallbackCanvas()` returns false) |
| BaseSurface | none | owns the surface, delays init until visible (IntersectionObserver), reset animation, palette wiring; default radius 5 |
| Drawing | BaseSurface | GPU stroke ping-pong; `drawPass` and `renderPass` |
| NaiveRaymarchGi | Drawing | naive raymarch, N = 8 |
| JFA | Drawing | seed and jump passes |
| DistanceField | JFA | adds the DF pass; always full JFA |
| GI | DistanceField | GI shader, temporal accumulation, sun, toggles, reset scene |

Shaders:

| Script id or location | Stage | Purpose |
|---|---|---|
| `vertex-shader` | vertex | `vUv = uv`; full-screen 2 x 2 plane with an orthographic camera (-1, 1, 1, -1) |
| inline in `Drawing.initializeSmoothSurface` | fragment | stroke |
| `naive-raymarch-shader` | fragment | naive raymarch |
| `jfa-seed-shader` | fragment | seed |
| `jfa-shader` | fragment | one jump pass |
| `dfa-shader` | fragment | distance field |
| `gi-fragment-shader` | fragment | GI |

Each pass is one full-screen draw into one render target. The shaders use `texture()`, `in`, and `gl_FragColor`. The page loads three.js from a local `../js/three.js`; the source does not state its version.

Per-frame pass sequence in `GI.renderPass` (derived from the code):

1. `drawPass`: stroke shader, reads one target and writes the other. It runs every frame, even when not drawing, so the scene is copied each frame.
2. `seedPass`: seed shader.
3. `jfaPass`: P jump passes, ping-pong.
4. `dfPass`: DF shader.
5. `giPass`: GI shader to the screen. With temporal accumulation active and not drawing, it first renders to the history target.

Total: 13 full-screen draws per frame, or 14 with temporal accumulation. Each GI instance allocates 10 float render targets (two each for stroke, seed, JFA, DF, and GI). The seed and DF passes use only index 0.

Each stroke segment calls `renderPass`, so each segment runs the whole GI pipeline (derived).

Naive demo: `drawPass` plus the raymarch shader to the screen (two draws).

Texture contents:

| Texture | Written by | Content | Read by |
|---|---|---|---|
| Scene | stroke shader | rgb = paint color (0 when empty); a = 1 painted, 0 empty | seed, GI |
| Seed | `jfa-seed-shader` | rg = uv * a; ba = uv * (1 - a) | JFA pass 0 |
| JFA | `jfa-shader` | rg = nearest seed uv (0 if none); ba = 0 | DF |
| DF | `dfa-shader` | d in [0, 1] in rgb; a = 1 | GI |
| GI | `gi-fragment-shader` | radiance in rgb; a = 1 | screen, history |

## Parameters and defaults

| Parameter | Value | Where | Notes |
|---|---|---|---|
| Demo canvases (simple, naive, JFA, DF) | 300 x 300 | constructors | W x H in pixels |
| GI demo canvas | 300 x 400 | `new GI({ id: "gi", ... })` | |
| Stroke radius | 5 px | BaseSurface default | `radiusSquared` = 25 |
| Naive rays | 8 | NaiveRaymarchGi | |
| Naive steps | 128 default, 0 to 512 | HTML slider | author text says "like 256 steps" |
| Painted threshold | alpha > 0.1 | naive and GI shaders | |
| Naive hit threshold | alpha > 0.5 (script); 0.1 (article) | naive shader | |
| JFA passes P | ceil(log2(max(W, H))) = 9 | `innerInitialize` | 300 x 300 and 300 x 400 |
| JFA offsets | 2^(P-1-i) pixels | `jfaPass` | 256 down to 1 for P = 9 |
| JFA neighborhood | 3 x 3 | `jfa-shader` | center included |
| JFA slider | 0 to 9, default 5 | HTML | |
| DF clamp | 1.0 uv | `dfa-shader` | |
| GI rays | 32 | `let rayCount = 32.0` | not stated in article text |
| GI max steps | 32 default, 0 to 48 | HTML slider | loop runs maxSteps - 1 times |
| Hit epsilon | 0.001 uv | GI shader | |
| Sun angle | 4.2 rad default, 0 to 6.2, step 0.1 | HTML slider | code comment says TAU - 2.0 |
| Sun falloff | smoothstep(1.0, 0.0, angleToSun) | `sunAndSky` | |
| Sun color | (0.95, 0.95, 0.9) | constant | |
| Sky color | (0.02, 0.08, 0.2) | constant | added to every non-hit ray with sun on |
| Temporal limit | 10 frames | `accumAmt` | |
| Temporal mix | 0.9 history, 0.1 new | GI shader | |
| Hash | `fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453)` | `rand` | |

## Artifacts discussed

| Artifact | Cause as the source states it | Fix in the source |
|---|---|---|
| Repeating patterns across pixels | rays from all pixels line up | per-pixel random angle offset, `rand(uv)` |
| Noise in GI | random offsets | not avoided; temporal accumulation averages it over 10 frames |

Not discussed in the source: ringing, light leaking, aliasing, banding, and flicker.

## Performance

- The source gives no benchmark numbers (no hardware, timings, resolutions, or frame rates).
- Author's statements: the naive method is "wildly inefficient"; the canvas is small and cannot be made much larger and still run smoothly, even on stronger machines.
- The author says part 2 gives the same end result at much higher resolution and much better efficiency.
- Temporal accumulation has a per-frame cost (a render-target switch and an extra texture lookup).

## Limitations and open problems (author)

- The naive method is slow and the canvas is small.
- Noise is needed to avoid patterns in the naive method.
- Only painted surfaces are handled. Reflective, transparent, and subsurface-scattering materials would need extra processing (article text).
- The sky is one constant color and the sun is a single angular falloff.
- Temporal accumulation is a workaround for noise.

## Source versus code

- Seed output: the article shows `vec4(vUv * alpha, 0.0, 1.0)`; the script uses `vec4(vUv * alpha, vUv * (1.0 - alpha))`. The script is the code that runs.
- JFA initial value: the article uses `vec4(-2.0)` and copies the full vec4; the script uses `vec4(0.0)` and copies only `.xy`.
- Naive hit threshold: article 0.1; script 0.5.
- Naive stepping: the article starts one step out; the script samples from step 0 (the pixel itself, which is empty) and, with accumulation off, only at `maxSteps - 1`.
- Naive noise: the article always uses `rand(uv)`; the script uses it only when noise is on, and otherwise 0.1.
- Temporal accumulation: the article mixes every frame; the script mixes only when `time > 0` and not drawing or sliding, and it renders the GI pass a second time to the screen.
- Naive max steps: the article text says "like 256 steps"; the HTML default is 128.
- Sun angle: the code comment says `TAU - 2.0`; the HTML default is 4.2 (TAU - 2.0 is about 4.28).
- The GI ray count (32) and the DF clamp are in code only; the article text does not state them.

## Observations from the code (not stated by the source)

- Non-square canvases: GI rays are unit vectors in uv space and the DF is measured in uv units. On the 300 x 400 GI canvas, ray spacing and distances are not uniform in pixels. The naive shader divides by `size` and is uniform in pixels. The GI shader declares `oneOverSize` but does not use it. The source does not discuss this.
- A pixel with no seed after the JFA stores (0, 0), so the DF measures its distance to the corner, clamped to 1. The source does not handle this case. Partial JFA runs can leave pixels without a seed.
- Colors and sun and sky constants are used as given. No gamma or color-space conversion appears in the code.

## Links found

Series (Real-Time Global Illumination, from https://jason.today index):

- Part 1: Raymarching, Distance Fields, and Jump Flood Algorithm | https://jason.today/gi | this post, dated 2024-07-27.
- Part 2: Radiance Cascades | https://jason.today/rc | the follow-up post, dated 2024-08-31; linked from this post; not analyzed here.

Radiance Cascades material linked in the body:

- Radiance Cascades (technique document on Google Drive) | https://drive.google.com/file/d/1L6v1_7HY2X-LV3Ofb6oyTIxgEaP4LOI6/view | the link the intro uses for the technique; its content is not described here and was not fetched.

- Markdown version of this post | https://gist.github.com/jasonjmcghee/e78bc62874059d64ac9592b6b9e01bb2 | same post in Markdown, with the code in blocks.
