# 2D articles and demos

The tutorials and teaching demos that explain 2D RC with working code: the GM Shaders posts and repository, jason.today's two articles, Coppen's fundamentals article, the community site's demo and its twin in Osborne's slides, tmpvar's playground, and the shorter write-ups by Otavio Peixoto, Théo Le Goc, SimonDev and Kelkar et al. Libraries, engine ports and CPU references are in [2D implementations](2d_implementations.md), Shadertoy code in [2D Shadertoys](2d_shadertoys.md). Interval formulas, index math, cascade counts and parameter tables shared with other codes are in [cascade layout and merging](cascade_layout_and_merging.md), merge fixes and artifacts in [artifacts and fixes](artifacts_and_fixes.md), timings in [performance](performance.md), and who published what when in [history and landscape](history_and_landscape.md).

Statements marked "derived" were computed from the sources' formulas; "inference" marks conclusions drawn here; "read from the code" marks behaviour found by reading, not by running.

The GM Shaders and jason.today series each have their own file: [GM Shaders](2d_articles_and_demos_gm_shaders.md) and [jason.today](2d_articles_and_demos_jason_today.md).

## Contents

- [radiance-cascades.com demo and Osborne's slide demo](#radiance-cascadescom-demo-and-osbornes-slide-demo)
- [tmpvar's playground](#tmpvars-playground)
- [Max Coppen, Fundamentals of Radiance Cascades](#max-coppen-fundamentals-of-radiance-cascades)
- [Otavio Peixoto, OPEngine](#otavio-peixoto-opengine)
- [Théo Le Goc (tlegoc), Vulkan](#théo-le-goc-tlegoc-vulkan)
- [SimonDev's demo](#simondevs-demo)
- [Kelkar et al. (IEEE ICWITE 2025)](#kelkar-et-al-ieee-icwite-2025)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)
- [Open questions](#open-questions)

## radiance-cascades.com demo and Osborne's slide demo

The site's `public/js/rc.js` (2,237 lines) is one WebGL2 2D demo ([demo](../sources/2026_rc_community_site_and_wiki.md#demo-publicjsrcjs)). Osborne's slides embed `rc-demo.html`, described as a WebGL port of the jason.today demo, with base rays 4, 16 or 64, the cascade count `ceil(log(diagonal)/log(base)) + 1`, R11G11B10 float targets, interval start `base^(i−1)·len` and end `((1 + 3·overlap)·base^i − i²)·len` with overlap 0.1, the "hand-wavy rule" comment, and a merge skipped for hits and for every top-cascade ray ([slides](../sources/2024_rc_blog_posts_and_slides.md#osborne-slides)). rc.js matches that description term for term and shares jason.today's `modifierHack = p if B < 16 else √B`, its control names and its reversed-smoothstep old sun, so both are the same port of jason.today's final demo with a new interval formula (inference). Its intervals, index math and merge are in [layout](cascade_layout_and_merging.md#intervals).

**Pipeline and targets.** A drawing pass at RC resolution (`W×H`, 512² by default) with a high-resolution copy at `dpr` = `rcScale` = 2, then seed, flood, distance, one pass per cascade from the top down to the "Layer to Render" cascade, and an overlay that shows painted pixels' own colour at layer 0 and the cascade output otherwise; on desktop a brush disc is drawn at the pointer on the screen only. The backing store is 1024 px shown at 512 CSS px.

| Target | Size | Format | Filter | Use |
|---|---|---|---|---|
| Drawing | W×H | RGBA8 | nearest | 2, ping-pong |
| Drawing, high resolution | W·dpr × H·dpr | RGBA8 | nearest | 2, ping-pong |
| Seed and flood | W×H | RG16F; RG32F above 1024 px off mobile | nearest | 2 seed (one used), 2 flood |
| Distance field | W×H | R16F | nearest | one used |
| Cascades | W×H | R11F_G11F_B10F (RGB, HALF_FLOAT) | LINEAR_MIPMAP_LINEAR, mag LINEAR | 2, ping-pong |
| Overlay | W·dpr × H·dpr | RGBA16F | nearest | 2, ping-pong |
| Indicator | W·dpr × H·dpr | RGBA8 | nearest | created, never used |

Every sampler bound to a texture triggers `gl.generateMipmap` in `setUniform`, so mips regenerate on every render.

**Distance field.** Seeds store the UV where drawing alpha is above 0. `P = ceil(log2(max(W, H))) + 1` passes, 10 at 512² with offsets 512 down to 1, each reading the pixel and its 8 neighbours and keeping the non-empty seed nearest by squared distance; a value counts as empty when both components are at most 0, so a seed exactly at `(0, 0)` is empty, and a pixel with no seed stores `(−1, −1)`. The field is `min(1, |UV − seed|)` in UV units, 1 for `(−1, −1)`; the source says nothing on the approximation's accuracy.

**Probes and intervals.** Cascade 0 has `E` (`cascadeExtent`) `= floor(W/p) × floor(H/p)` probes for `p` = `basePixelsBetweenProbes` = `2^e` (slider `e` from 0 to 4), and interval lengths scale by `M` (`modifiedInterval`) `= modifierHack·rI·cI`, with `rI` (`rayInterval`) the Interval Length slider (default 1.0) and `cI` (`cascadeInterval`) fixed at 1.

**Lookup and merge.** For cascade `i` with spacing `s^i`, grid texel `c` (per axis, `0 ≤ c < E`) has `uv = (c + 0.5)/E`. The cascade grid lives in a W×H texture looked up at `(grid coordinate)/E`, from mip `log2(p)`, which has `E` texels per side, when `p > 1`. A ray that misses below the top cascade (`i < max(1, N − 1)`) merges from cascade `i + 1`, with upper spacing `s^(i+1)` and upper grid `U = floor(E/s^(i+1))`; the merged value is added to the ray's colour and alpha is set to 1.

**Ray march.** Sphere tracing with steps in pixels (`df·min(W, H)`), a hit at half a texel (`0.5·min(1/W, 1/H)`) returning `scene.rgb^srgb` with the scene alpha, and a miss `(0, 0, 0, 0)` once the travelled distance reaches the segment length or the position leaves `[0, 1]²`; there is no iteration cap.

**Sun, sky and sRGB.** Only with the sun button, only on the top cascade: `max(sky(θ), radiance)` per channel, hits included. The default sky is `mix(sunColor·I, skyColor, 0.3)` = `0.7·sunColor·I + 0.3·skyColor` with `I = max(0, cos φ)^4`, `φ = mod(θ − sunAngle, 2π)`, sun `(0.95, 0.9, 0.8)·3`, sky `(0.2, 0.24, 0.35)·4`; with Naive GI Noise on, the old `smoothstep(1.0, 0.0, φ)` sun with reversed edges and part 1's colours. The sun angle is in radians, inferred from the modulo by `TAU`. Hits are decoded with `rgb^srgb`, the cascade at Layer to Render is encoded with `1/srgb` and the ones above stay linear; with the checkbox off nothing converts, and the overlay never converts.

**Other bases** (derived at 512², overlap 0.1; base 4 is in [layout](cascade_layout_and_merging.md#intervals)):

| Base | Cascades | `modifierHack` | Rays per probe | Spacing | Probes per axis | Start | Length |
|---|---|---|---|---|---|---|---|
| 16 | 4 | 4 | 16, 256, 4096, 65,536 | 1, 4, 16, 64 | 512, 128, 32, 8 | 0, 4, 64, 1024 | 5.2, 79.2, 1315.2, 21,263.2 |
| 64 | 3 | 8 | 64, 4096, 262,144 | 1, 8, 64 | 512, 64, 8 | 0, 8, 512 | 10.4, 657.6, 42,566.4 |

At base 16 and 64 the top cascades have 8×8 probes, and their intervals run tens of times past the 724 px diagonal (derived).

**The slide animations.** Osborne's manim scripts draw 2D cascades with probe spacing `2^L`, `4·2^L` rays per probe, interval ends `0.25·2^L` with each starting where the last ended, ray `k` of `N` at `2π(k + 0.5)/N`, and parent ray `floor(i/2)` at the next level: rays only double per level, the 2x/2x branching the slides compare ([core theory](core_theory.md#rays-traced-and-rays-built)).

## tmpvar's playground

A page of interactive demos (https://tmpvar.com/poc/radiance-cascades/, 2024 by its links; code MIT, text and images CC BY 4.0) with four 2D demos and two 3D calculators ([playground](../sources/2024_tmpvar_rc_playground.md)). The 2D code is in `flatland-2d/`: `flatland-2d.js` (2,025 lines, 61,092 bytes, every WGSL shader and the WebGPU pipeline), `params.js` (2,980 bytes, the shared control reader imported by every demo script), `radiance-intervals-2d.js` (3,353 bytes), `probe-ray-distributions-2d.js` (4,960 bytes) and `probe-interpolation-2d.js` (3,438 bytes); Flatland starts from `flatland-2d-demo.png`, which was not fetched. The 3D calculators (Demo 5 in `ssprobes-wsintervals/ssprobes-wsintervals.js`, 2,997 bytes, which imports `./params.js` from its own folder, and Demo 6, the world-space storage table, an inline module at the bottom of the page HTML) are in [3D screen space](3d_screen_space.md) and [3D world space](3d_world_space.md#memory-and-rays).

The page's text says each level doubles the band's inner radius, its width and the rays per probe, halves the total rays, and offsets rays by half a step with `angle = TAU·(rayIndex + 0.5)/rayCount`; it writes the factor as `N^level`, while the code uses `2^(B·level)`, so `N = 2^B` and the text describes `B = 1`; the demo does not compute the page's total-ray figure.

**Demo 1, Radiance Intervals.** Controls: level 0 ray count 4 to 8 (default 4), branching factor `B` 1 to 3 (default 2, labelled `2^B`). On a 1024² canvas (background #111, seven level colours) centred at (512, 512) with no padding, level `l` draws a circle at outer radius `16 << (l·B)`, inner radius 0 at level 0 and `16 << ((l − 1)·B)` above, and `level0RayCount << (l·B)` segments from the inner to the outer radius at `2π(k + 0.5)/count`, with direction `(sin, cos)`; the loop stops once twice the inner radius passes 1024. At the defaults levels 0 to 3 draw radii 16, 64, 256 and 1024 with 4, 16, 64 and 256 rays.

**Demo 2, Ray Distributions.** Probe spacing doubles per level for any `B`, which the page calls the common flatland case.

| Control | Range | Default |
|---|---|---|
| max level | 0 to 6 | 2 |
| level 0 ray count `2^r` | r = 2 to 5 | 4 rays |
| level 0 probe diameter `2^e` | e = 2 to 10 | 128 px |
| level 0 interval radius `I` | 0 to 64, used as an integer | 18 |
| branching factor `B` | 1 to 3 | 2 |
| colour lower levels | checkbox | on (off draws them #222) |
| show cascade ray counts | checkbox | off; prints the ray count per level and in total |

Level `l` has diameter `D0 << l`, `R0 << (B·l)` rays per probe, interval `[0, I]` at level 0 and `[I << ((l − 1)·B), I << (B·l)]` above, probes on a grid of step `D_l` from (0, 0) with centres at the cell corner plus `D_l/2`, `(1024/D_l)²·R_l` rays per level and direction `(sin, cos)`. Defaults: 8×8 probes of 4 rays over `[0, 18]`, 4×4 of 16 over `[18, 72]`, 2×2 of 64 over `[72, 288]`, 256 rays per level and 768 in all. With `B = 2` the count per level stays constant, at `B = 1` it halves and at `B = 3` it doubles (derived).

**Demo 3, Probe Ray Interpolation.** Controls: min level 0 to 6 (1), max level 0 to 6 (2), level 0 ray count 1 to 32 (4), `B` 1 to 3 (1). On a 1024 canvas, probes at cell origin + 64 have a fixed radius of 64 on a fixed 128 px grid, so spacing does not change per level; each level draws `L0 << (B·l)` segments from `64 << ((l − 1)·B)` (0 at level 0) to `64 << (B·l)`. At the defaults 64 probes draw 8 segments from 64 to 128 and 16 from 128 to 256. Despite the title it computes no interpolation and draws no merged values; its function is named `DrawRayDistributions2D`, copied from the previous demo, and the branching label reads `state.params.probeRayCount`, which this demo never sets, with no effect on the output.

**Demo 4, Flatland.** A 1024² WebGPU GI demo for Chrome or Edge; per-pass timing needs the optional `timestamp-query` feature, and a console warning names a Chrome Canary flag for it. Every texture and buffer is sized from the canvas.

| Cascade control | Range | Default | Meaning |
|---|---|---|---|
| level 0 spacing `2^i` | i = 1 to 9 | 2 px | probe cell diameter, stored as radius |
| level 0 ray count `2^r` | r = 1 to 6 | 4 rays | `R0` |
| branching factor | B = 1 to 3 | 2 | `N = 2^B` = 4 |
| level 0 interval radius `s` | 0 to 32, step 0.1 | 2.6 | `I = s²` = 6.76, truncated to 6 |
| levels | 0 to 9 | 5 | top level index |

| Debug control | Default | Meaning |
|---|---|---|
| run continuously and collect frame timings | off | prints GPU pass times |
| render world mip level | disabled (0 to 9) | shows a preview mip instead of fluence |
| render probe directions | off | fluence only from rays aimed at each pixel's probe cell |
| disable brush preview | off | id spelled `debugDisbleBrushPreview` |
| raymarch mipmap N on cascade level N | on | march mip `l` on level `l` |
| raymarch with dda | off | grid traversal instead of fixed steps |
| fixed step multiplier | 100 (1.00), 1 to 1000 | `max(0.1, value/100)`; disabled with DDA |
| accumulate non-linearly | off | switches the accumulation formula |
| accumulation decay | 100 (1.00), 1 to 400 | `value/100`, only when non-linear |

- **Resources.** `worldTexture` rgba16float (rgb premultiplied emission, alpha opacity); `worldAndBrushPreviewTexture` rgba16float with 10 mips, which the march reads, so the brush preview lights the scene unless disabled; `probeBuffer` of vec4f sized `2·maxLevel0Rays·16` bytes with `maxLevel0Rays = 2^6·(1024/2)²` = 16,777,216, so 512 MiB allocated at startup from the slider limits; `fluenceTexture` rgba8unorm, so the final image clamps at 1. rgba16float is chosen because multiplier-scaled radiance is averaged down the mip chain. A per-level uniform block holds 16 int32 fields (total rays, probe radius, ray count, level, level count, width, height, `maxLevel0Rays`, interval start and end radii, branching factor and five debug values) at a dynamic offset per level, with 10 levels reserved and a TODO noting it assumes an alignment of at most 256 bytes.
- **Index math.** `D_l = D0·2^l`, `W_l = 1024/D_l` probes per axis, `R_l = R0·2^(B·l)` rays; probe `p = row·W_l + col`, decoded as `col = p mod W_l`, `row = p div W_l`; ray slot `base_l + p·R_l + k` with `base_l = (l mod 2)·maxLevel0Rays`, so levels alternate between the buffer's halves; angle `2π(k + 0.5)/R_l` with direction `(cos, sin)` (the intro demos use `(sin, cos)` for the same angles); centre `(col·D_l + D_l/2, row·D_l + D_l/2)`; 256 threads per group, `id = gid.x + gid.y·256`, probe `id/R_l`, ray `id % R_l`.
- **Frame order.** Nothing runs unless a control changed, the mouse moved, clear was pressed or timing is on. A mouse drag paints a capsule into `worldTexture` (y flipped); the world is copied to the preview, the brush disc painted on it, and mips 1 to 9 built by 2×2 box averages; `ProbeAtlasRaymarch` runs once per level from the top down, each level its own compute pass; `BuildFluenceTexture` reads level 0 and `DebugWorldBlit` draws it.
- **Shaders.** `DebugWorldBlit` (full-screen triangle; draws `fluenceTexture`, or a mip of the preview texture when the debug option is set), `ProbeAtlasRaymarch` (compute, 256×1×1, with `DDACursorInit`, `RayMarchDDA`, `RayMarchFixedSize`, `AccumulateSample`, `SampleUpperProbe`, `SampleUpperProbes`, `ComputeMain`), `BuildFluenceTexture`, `WorldClear` (a constant colour into a storage texture), `WorldPaint` (a capsule via `SDFSegment`, used for world and preview) and `GenerateMipmapsBoxFilter`, all 16×16 except the march.
- **Per ray.** March `[S_l, E_l]` from `(0, 0, 0, 1)` to get `Lower`, read `Upper`, store `rgb = Lower.rgb + Lower.a·Upper.rgb`, `a = Lower.a·Upper.a`, with `S_0 = 0`, `E_l = I·2^(B·l)` and `S_l = E_(l−1)`. The top level's upper term is `(0, 0, 0, 1)`, with a TODO for sky or environment light.
- **Merge.** Lower ray `k` maps to upper rays `k·N … k·N + N − 1`, which fall inside its angular sector (derived from the angle formula). Upper probe index `f = P/D_(l+1) − 0.5`, base `floor(f)`, four probes each clamped to `[0, W_(l+1) − 1]`, which the source calls an intentional reuse of edge probes, with a ring of probes outside the scene as the planned fix; each probe value is the mean of its `N` rays at slots `base_(l+1) + p′·R_(l+1) + k·N + m` (`m < N`, `p′ = x + y·W_(l+1)`), and the four blend bilinearly with `w = fract(f)`.
- **March.** Fixed steps of `2^l·m` on mip `l` (or `m` on mip 0 without mips) from `P + d·S_l`, sampled at position/1024, until the distance from `P` passes `E_l` or the ray leaves the texture; or a DDA after the lodev.org raycasting tutorial in mip-level pixels that samples each visited cell at its corner, not its centre, and stops when the cell is farther than `E_l` from `P` or leaves the texture. Accumulation is `acc.rgb += acc.a·s.rgb` with `acc.a *= 1 − s.a`, or `acc.a *= exp(−s.a·decay)`; the step size is passed in and unused, so opacity does not scale with step length.
- **Fluence.** Each pixel takes the mean of its level 0 probe's rays, with the probe cell `floor(c/1024·W_0)` and no interpolation between probes; the direction debug view keeps only rays whose line passes within about a pixel, tested with `sdSegment` from a cited Shadertoy.
- **Read from the code.** The dispatch runs levels 0 to `levelCount` while the merge runs only for `l + 1 < levelCount`, so level `levelCount − 1` sees no upper term and level `levelCount` is computed and never read; the ray id ignores the x-group count once groups split into y, which matters past 65,535·256 = 16,776,960 rays, below the 16,777,216 maximum at level 0; the guard uses `>` instead of `>=`, processing one extra id; JavaScript's `<<` truncates the interval, so the label shows 6.76 while the ends are 6, 24, 96, 384, 1536 and 6144; with `B = 3` rays per level double, and at the maximum level 0 settings level 1 needs 33,554,432 slots in a half that holds 16,777,216, overrunning the buffer; the fluence bounds check uses the width for y, correct only on a square canvas. At the defaults the grids are 512 down to 16 per side with 4 to 4096 rays, 1,048,576 rays per level (derived).
- **Stated in the source.** Mapping the staging buffer for timings may take more than one frame; the debug UI prints per-pass milliseconds, but the page reports no timings and names no hardware.

## Max Coppen, Fundamentals of Radiance Cascades

Coppen's 2D explainer (2024-10-22) is a good first read, and its merge loop is the most reusable part ([notes](../sources/2024_coppen_fundamentals_of_radiance_cascades.md)). Its theory is in [core theory](core_theory.md), its storage in [cascade layout](cascade_layout_and_merging.md#position-first-and-direction-first) and its merge artifacts in [artifacts and fixes](artifacts_and_fixes.md).

- **Terms.** The green probes are "bilinear probes" and the blue one the "destination probe" (Figures M and N). Radiance is light from one direction at one point, which the author compares to a ray; irradiance is light from a subset of directions at one point, which the author describes as light from all directions. A probe's angular resolution is the angle between its evenly spaced rays.
- **Storage.** The most common storage is a 2D texture. Instead of one texture per probe, a whole cascade goes in one texture with its probes packed together; a probe with 16 intervals is a 4×4 block of texels, one direction per texel. The direction-first layout is mentioned with no index math and no exact block layout.
- **Code names.** Directions are `vec2(cos(angle), sin(angle))`. `interval_scale(cascade_index)` gives the scale and `interval_range` returns `base_length * vec2(interval_scale(cascade_index), interval_scale(cascade_index + 1))`. `bilinear_weights(ratio)` returns the four weights, and `bilinear_samples(dest_center, bilinear_size, out weights, out base_index)` computes the ratio and calls it; `dest_center` is the centre of the destination probe in pixels and `bilinear_size` the size of a bilinear probe in pixels.
- **Merge.** Splitting by angle alone does not reduce the ray count, since each probe still casts many rays. Merging each direction through every cascade would be too costly; with a branch factor of 4 each cascade merges 4 intervals of the cascade above into 1, and repeating this over all cascades captures a cone of radiance. The division by 4.0 in the merge loop is not explained.
- **Parameters.** Probe counts halve along each axis "most of the time"; the branch factor 4 is recommended, with 2 only in Figure O, drawn that way for readability with its green intervals coloured by bilinear weight; the examples use 16 directions (4×4 texels) and probe grids of 4×4 at cascade 0 and 2×2 at cascade 1. The article gives no cascade count, no value for `base_length`, no probe spacing, no texture format or size beyond "2D texture", and no performance, hardware or resolution; the author states only that it runs in real time. The top cascade's skybox option has no detail.
- **Artifacts.** Ringing, a visible disconnect between probes of different cascades, is left out of scope, with a "bilinear fix" and a "parallax fix" named but not described. Merging with only the nearest upper probe gives blocky penumbrae (Figure L); merging with the four bilinear probes (Figure M) gives smooth penumbrae (Figure N), though the author notes that Figure M's weights are wrong. The interval lengths in Figure F are not to scale on purpose. The final pass has no code, so whether it uses the same bilinear sampling is unclear, and the article leaves open whether its bilinear merging is the "bilinear fix" it names for ringing.

Figures (the eight animations are video elements whose content is not transcribed; videos under `https://m4xc.dev/anim/articles/fundamental-rc/`, images under `https://m4xc.dev/img/articles/fundamental-rc/`):

| Figure | File | Caption |
|---|---|---|
| Intro | `showcase.mp4` | Diffuse global illumination in flatland |
| A | `angular-anim.mp4` | Circular object with a radiance probe |
| B | `spatial-anim.mp4` | Penumbra created by line light and line occluder, resolved by interpolating 2 probes |
| C | `penumbra-anim.mp4` | Moving the line occluder around |
| D | `splitting-anim.mp4` | Probe being split into "rings" |
| E | `inc-angular-split.png` | Increasing angular resolution for more distant rings, doubling the interval count per ring |
| F | `spatial-exploit-anim.mp4` | Increasing probe/ring spacing |
| G1 | `cascade0.png` | Cascade 0, with 4×4 probes |
| G2 | `cascade1.png` | Cascade 1, with 2×2 probes |
| H | `probe-memory-anim.mp4` | 4×4 probe in texture memory |
| I | `cascade-memory.png` | Cascade in texture memory |
| J | `interval-merge-anim.mp4` | Green interval should occlude red interval |
| K | `interval-cone.png` | Cone made out of intervals |
| L | `nearest-interp.png` | Merging with nearest probe only |
| M | `bilinear-probes.png` | Merging with 4 bilinear probes |
| N | `bilinear-interp.png` | Smooth penumbrae using bilinear interpolation |
| O | `full-merge.png` | Merging for 1 interval (in blue) |
| P | `final-result.png` | Final result (credit: Fad's Shadertoy) |

## Otavio Peixoto, OPEngine

A 2D RC renderer inside the author's own C++/OpenGL engine, with a portfolio page (https://otaviopeixoto1.github.io/portfolio/2DRadianceCascades/) and code in `src/render/RadianceCascades/` and `data/shaders/RadianceCascades/2D/` of https://github.com/Otaviopeixoto1/OPEngine (repository from 2023-10, RC commits 2024-06-01 to 06-05, no license) ([Peixoto](../sources/2024_peixoto_opengine_2d_rc.md)). Light comes from mouse strokes; each cascade is a full-size square texture, rays sphere-trace a distance field, and cascades merge top-down with bilinear weights over four upper probes and an average of four upper rays. No timings, hardware or tested resolution are given; profiler scopes (March Cascades, Merge Cascades, Capture Mouse) exist with no recorded numbers.

**The page** says each cascade has 4× the rays and 4× fewer probes, with spacing doubling per axis, and that rays reach twice as far per cascade, while the code uses 4×. Probes must sit uniformly; merging takes the 4 nearest upper probes and the 4 upper rays sharing the ray's direction; the final pass sums cascade radiance per pixel; sharp shadows come out poorly. Its memory figure draws 4 cascades and its march figure 5. The README credits tmpvar's playground, fad's and Suslik's Shadertoys and Sannikov's paper.

**Parameters and storage.** `MAX_CASCADES` 10, `c0Angular` 4 rays, `c0Interval` 4 px, `c0Spacing` 2 px. The region is square with side `R = max(W, H)`, storage side `S = floor(R/2)·√4`, equal to `R` for even `R`. The count `N = min(floor(log2(4·√2·R)/2) − 1, max(ceil(log2(S/2)), MAX_CASCADES))` uses `max` where a cap needs `min`, making 10 a floor of the second term, so the first term decides: `N = 5` at 1920×1080, 4 at 512². `N + 1` square RGBA16F textures with `GL_LINEAR`, one per cascade plus a ping-pong buffer, take 6 × 1920² × 8 B = 176.9 MB at 1920×1080, and two viewport-sized RGBA16F distance textures 33.2 MB.

**Layout.** Position-first: cascade `i` has `4^(i+1)` rays (4, 16, 64, 256, 1024) in a `2^(i+1)`-texel block per probe, probe `floor(texel/probeSize)`, ray index `ty·probeSize + tx` row-major, spacing `2^(i+1)` px, so 960, 480, 240, 120 and 60 probes per axis at 1920 and `S²` texels in every cascade. Ray angle `θ = 2π(rayIndex + 0.5)/rayCount`, direction `(cos θ, −sin θ)`; probe UV `(probePos + 0.5)·spacing/(W, H)`; rays start at `probeUV + dir·minimum/R`.

**Intervals.** Raw `minimum_i = 4·(4^i − 1)/3` and `range_i = 4·4^i`: `[0, 4], [4, 20], [20, 84], [84, 340], [340, 1364]` px. An overlap adjustment `minimum −= (range_i/4)·sign(i − 1)` then gives `[1, 4], [4, 20], [4, 84], [20, 340], [84, 1364]`: cascade 0 starts 1 px out, and from cascade 2 up each cascade starts where the one below starts, re-tracing the lower interval from coarser probe positions. Since the merge runs only where the lower ray missed, a hit inside that re-traced range, seen from the upper probe, can reach the result after the lower ray missed it (derived). Measured in this cascade's probe spacing `2^(i+1)`, the overlap with the cascade below is 2, 4 and 8 spacings for cascades 2 to 4, 1.4, 2.8 and 5.7 times the `√2` that fixes leaks ([overlap](cascade_layout_and_merging.md#overlap); [check](../checks/peixoto_interval_overlap.py)). So the re-tracing hides leaks as any overlap does and, from cascade 3 up, acts as the large overlap that gives halos: light and shadow from objects the lower ray passed by appear around them, offset by the upper probes' positions. With binary hits, partial absorbers are never counted twice. Cascade 0's 1 px start leaves `[0, 1)` px around each probe untraced by any cascade (derived). The top reaches 1364 px, short of the 2716 px diagonal at 1920×1080.

**Tracing.** Sphere tracing in UV: `rt = range/R`, each step adds the field value, the sample is `start + dir·min(rd, rt)`; a miss is `rd ≥ rt` or leaving `[0, 1)²`, a hit `d < 1e-4` returning the emission with alpha 1. The loop cap `ii < range` gives 3, 16, 80, 320 and 1280 iterations for cascades 0 to 4, sized as if each step covered a pixel; sphere-tracing steps shrink near surfaces, so a ray can stop before its interval ends.

**Merge.** The loop runs `i = N − 1` down to 1 with cascade `i` as the upper input (the raw top, then the previous step's buffer); the uniform `cascadeIndex` is `i − 1`, the cascade written, though the renderer's comment calls it the upper index. Hits (alpha 1) are skipped. Upper base index `floor((p − 1)/2)` with weight `0.25 + 0.5·(p − (2·base + 1))`, 0.25 or 0.75, the correct bilinear weights for upper centres at `(2j + 1)·spacing`. For each of 4 upper probes the shader averages upper rays `4·rayIndex + k`, `k = 0..3`, blends the four bilinearly, adds the result and sets alpha 1: 16 upper reads per texel, with no pre-averaging pass.

**Final pass.** `probePos = sceneCoord/2 − 0.5`; the 4 cascade 0 rays of each of the 4 nearest probes are averaged with equal weights and the probes blended bilinearly. There is no cosine term and no 2π, so the output is mean radiance.

**Distance field.** Not a jump flood: each stroke is a quadratic Bézier from mid(A, B) through B to mid(B, C) with distance `sdBezier(uv) − brushRadius`, updated as `sd = min(d, sd)` where `d < max(0, sd)`, the emission taking the brush colour. Both buffers clear to `1e20`, which RGBA16F (maximum 65504) stores as +inf, and the tracer relies on inf acting as a far distance (IEEE conversion, read from the code). Distances are in UV, not pixels.

**Read from the code.** `FetchUpperCascade` and `CascadeFetch` turn integer texel coordinates into UV without the +0.5 texel-centre offset, and the y term `rayIndex/probeSize` has no floor, so with `GL_LINEAR` the reads should land between texels and blend neighbouring rays and probes (a capture would confirm it). Probe positions divide by `(W, H)` but lengths by `max(W, H)`, so at 1920×1080 a UV unit is 1920 px in x and 1080 px in y and lengths are right only on square viewports. At 1920×1080, 960 × 540 of cascade 0's 960 × 960 probes are on screen, so 43.75% of every cascade is off screen, which a comment says is intended.

**Code locations** (on `main`; `R.h` is `src/render/RadianceCascades/Radiance2DRenderer.h`, shaders in `data/shaders/RadianceCascades/2D/`, the stroke shader in `data/shaders/2D/LineDraw/`): constants R.h 53, 68-70; square region R.h 64, 71, and the off-screen comment R.h 64-66; cascade count R.h 74-78; textures R.h 107-115, 146-154; layout `MarchCascade.frag` 45-55, ray direction 22-29 and 61-62, raw interval 61-62, overlap adjustment 68-69, tracing 32-40; merge `MergeCascades.frag` 37-80 and R.h 329-351, `FetchUpperCascade` 37-47; final pass `RenderRadiance.frag` 16-67, `CascadeFetch` 16-22; distance field `genLineSDF.frag` and R.h 103, 180.

## Théo Le Goc (tlegoc), Vulkan

A blog post (https://tlegoc.github.io/blogs/radiance-cascade/, 2024-10-22) and C++/Slang code (https://github.com/tlegoc/RadianceCascadesGIVulkan, last commit 2024-11, no license) for a 2D Vulkan compute version on a screen-space SDF in RGBA32F, colour plus distance ([blog posts](../sources/2024_rc_blog_posts_and_slides.md#tlegoc-vulkan-blog-post)). The author first tried 3D with screen-space marching in Unity and moved to 2D to learn the method. The cascade count and the top cascade's vertical probe count are fixed and the texture width stretches to the screen, keeping the layout symmetric at any aspect ratio with extra probes on the sides. All cascades trace in parallel, then merge top-down one dispatch at a time, each waiting on the one before; the merge reads the 4 nearest rays of each nearby upper probe, averages them and interpolates bilinearly across probes. It crashes when rays are too long or the march step too small and shows artifacts at low resolution. Read from the code: three of four bilinear corners get the wrong weights, `output += final·output.a` also changes alpha, skipped edge taps still count toward the divisor of 4 (darkening edges), and a sign-keeping `%` wraps `index − 1` at index 0 into the previous probe block ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#bugs-worth-recognizing)).

## SimonDev's demo

The code behind SimonDev's video (https://github.com/simondevyoutube/Shaders_RadianceCascades, JS and GLSL, MIT, 2024-07), which the video does not link; the video's own content is in [history](history_and_landscape.md) ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#simondev-demo)). Plain RC with 7 levels, 4 directions per cascade 0 probe ×4 per level, intervals `(4^L − 1)/3` to `(4^(L+1) − 1)/3` scene pixels, and every level in one target of the same size, so rays per level are constant.

- **Scene.** A lazy-brush pen paints a 1920×1080 distance field whose texels hold colour and distance; the march sphere-traces up to 64 steps, hits below 0.1 px, and returns alpha 0 for a hit and 1 for an escape.
- **Sizes.** The cascade target is `1024·16/9` = 1820.44 texels wide, a non-integer size, by 1024. The level count comes from a loop that stops at the first level whose interval end passes the screen diagonal (5461 > 2203 px gives 7), overriding an earlier formula.
- **Layout.** Probe `P`, angle `a` sits at texel `(dims·Px + a mod dims, dims·Py + floor(a/dims))` with `dims = 2^(n+1)`, and the angle is `a·2π/dims² − π/dims²`, half a step back from the bin centre.
- **Merge.** The upper lookup averages four angular taps at `index − 1 … index + 2`, centred half a bin off the child range `4k … 4k + 3`; several helpers are marked "fixme". The bilinear probe set is chosen from `pixel − dims/2` while its weights are measured from centres at `dims·k + (dims − 1)/2`, a half-texel mismatch that wraps the fraction in a narrow band at probe boundaries (found by reading). Probes outside the texture return `(0, 0, 0, 0)`, which reads as opaque and stops the merge; `index − 1` at index 0 wraps into the previous probe block. A 13-tap merge option calls a function that does not exist.
- **Output.** The radiance field averages cascade 0's 4 directions per probe with no cosine term; the composite multiplies a background mixed in Oklab by the radiance and applies ACES with a 1/2.2 power.

## Kelkar et al. (IEEE ICWITE 2025)

"Radiance Cascades for Real-Time 2D Global Illumination" by Nikhil Kelkar, Ganesh Bhutkar, Shriya Nagarkar and Nandini Naik (Vishwakarma Institute of Technology, Pune), in the 2025 IEEE International Conference for Women in Innovation, Technology & Entrepreneurship, pp. 1-6, published 2025-09-26, DOI 10.1109/ICWITE64848.2025.11307155 ([assorted 2D](../sources/2026_assorted_2d_rc_experiments.md#kelkar-et-al-ieee-icwite-2025)). Only the abstract is reachable: a 2D GI engine with soft shadows for fully dynamic scenes that ray-marches a signed distance field and a lightmap, uses a 4× angular branching factor with screen-resolution textures per cascade for O(n) memory, merges cascades by hardware bilinear interpolation, and runs in real time on a cave scene with several emitters and occluders, relit every frame. It gives no timings, GPU, resolution or scene size, and no open copy was found.

## Connections

- **One lineage, three rewrites.** GM Shaders' Part One follows fad's Shadertoy; jason.today names GM Shaders as its main influence; the community demo and Osborne's slide demo are both a port of jason.today's final demo with a new interval formula; Sohojoe's Godot branch `mix-Yaazarai-and-jason` merges two of them ([2D implementations](2d_implementations.md#godot)). The teaching codes form one chain, so they share choices: one pass per cascade from the top, direction-first tiles, a single hardware-filtered merge fetch, sRGB handled by a 2.2 power, sky on the top cascade only (inference, from the sections above).
- **Shared hacks travel with the code.** `modifierHack` appears in jason.today (`1`, then `P`, against `√B` above base 16), the multipass demo (a literal 4) and rc.js; the reversed-smoothstep old sun appears in all three; the `+1` cascade from jason.today's top-left light is in rc.js and Osborne's demo. Each was a local fix for one artifact, kept without explanation; `modifierHack` turns out to be an interval tuning ([artifacts](artifacts_and_fixes.md#base-ray-counts-other-than-4)).
- **Article and code disagree in every series.** GM Shaders' posts and repository disagree on the visibility convention, the leak term and comments; jason.today's text and code differ in ten listed places in part 2 and nine in part 1; Peixoto's page says ×2 intervals where the code uses ×4. Reading the code, not the prose, gives the method each demo actually runs.
- **Off-by-one levels recur.** jason.today's multipass loop starts one pass above the top and tmpvar's dispatch computes one level that is never read; each wastes a full cascade of work without changing the image, which is why neither was noticed (inference). Peixoto's overlap adjustment re-traces a whole lower interval, which does change the image ([Peixoto](#otavio-peixoto-opengine)).
- **Normalization varies.** jason.today and rc.js average rays (mean radiance), Peixoto and SimonDev average without a cosine, tmpvar averages one probe's rays without interpolation, and GM Shaders divides by the ray count; none multiplies by 2π, so their brightness is comparable to each other and about 2π below fluence outputs ([layout](cascade_layout_and_merging.md#final-gather)).
- **Opacity per sample.** tmpvar's playground ignores the step size, the same flaw as wfyyDz and knowdawg ([2D implementations](2d_implementations.md#scene-representations)).

## Single-frame assessment

For single-frame 3D RC (inference, from the sections above):

- Every teaching demo computes its cascades from scratch each frame; the temporal parts (part 1's accumulation, GM Shaders' bounce feedback, jason.today's Reduce Demand) are optional, and jason.today's Reduce Demand never even reads its first frame. The method needs no history in 2D.
- The demos' cost claims are unmeasured: jason.today disables its GPU timer and tmpvar prints timings without recording any. Their value for a 3D design is the pipeline structure, not numbers; GM Shaders' stress test is the only measurement among them ([performance](performance.md)).
- jason.today's two-pass step shows the core economy in its simplest form: 32 raymarches per pixel reach 256 directions. In 3D the same split is what keeps per-pixel cost bounded while upper cascades resolve distant lights.
- The tile-and-single-fetch merge that all these demos share is the cheapest merge, but tmpvar's bilinear-of-means and Peixoto's 16-read merge show the explicit forms a 3D merge would need where hardware filtering cannot cross tile boundaries ([layout](cascade_layout_and_merging.md#merge-kernels)). By read count it is the cheapest: one hardware-filtered fetch per lower texel after pre-averaging, against 16 shader reads without it, as in GM Shaders' original, Coppen and Peixoto, or tmpvar's four probe means of `N` rays ([storage layouts](cascade_layout_and_merging.md#position-first-and-direction-first)) (derived).
- Edge handling matters more in 3D, where the share of off-screen or out-of-volume probes grows: Peixoto keeps 43.75% of every cascade off screen, and tmpvar clamps edge probes and plans an outside ring. A ring of one probe per side at every level that serves as an upper cascade adds `((n + 2)^d − n^d)/n^d` of that level, about `2d/n` for `n` probes per axis: 9.7% at 64³ and 237.5% at 4³. Weighted by memory per level, a 64³ cascade 0 with five levels above it pays 35.2% more with 4 directions per parent, where memory halves per level, and 182.5% with 8, where it stays constant; a 512² 2D stack down to 8² pays 15.3%. Clamping costs nothing but turns the bilinear merge into the nearest edge probe within half an upper spacing of each face, a share `1 − (1 − 1/n)^d` of the level: 57.8% at 4³ and 43.8% at 4² (derived; [check](../checks/edge_probe_ring.py)).

## Open questions

