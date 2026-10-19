# Merging fixes and ringing

| | |
|---|---|
| Date | 2024-08 to 2026-09 |
| Kind | Collected implementation findings; claims are unverified unless a public link backs them |
| Related | [2024_osborne_radiance_cascades_radiative_transfer.md](2024_osborne_radiance_cascades_radiative_transfer.md), [2023_rc_shadertoys.md](2023_rc_shadertoys.md), [2024_yaazarai_gmshaders_radiance_cascades.md](2024_yaazarai_gmshaders_radiance_cascades.md), [../topics/artifacts_and_fixes.md](../topics/artifacts_and_fixes.md) |

Most of this note is about 2D RC, where the bilinear fix and its alternatives were built and debugged. It adds the exact order of operations for the bilinear fix, the reasons behind it, the costs of the cheaper fixes, the scaling and format choices that worked, the parameter mistakes that look like merge bugs, a debugging routine, and measured 2D timings. The parts that matter for 3D are the cost argument for the fix on different grids and the parameter rules, which hold in any dimension.

## Contents

- [Building the bilinear fix](#building-the-bilinear-fix)
- [Why it works](#why-it-works)
- [Other fixes](#other-fixes)
- [Cheaper fixes and their costs](#cheaper-fixes-and-their-costs)
- [Scaling and setups](#scaling-and-setups)
- [Formats and color](#formats-and-color)
- [Measured 2D timings](#measured-2d-timings)
- [Cost in 3D](#cost-in-3d)
- [Parameters that look like merge bugs](#parameters-that-look-like-merge-bugs)
- [Debugging routine](#debugging-routine)
- [Links](#links)

## Building the bilinear fix

- Vanilla RC traces one ray, interpolates four upper probes, then merges. The bilinear fix traces one ray to each of the four upper probes, merges each ray with its own probe, and only then interpolates the four results with the usual bilinear weights.
- All four rays start where the vanilla ray starts, at `probe + d·t_start`. Each ends at the interval start of one upper probe's ray group, `upper_k + d·t_end`. With a bilinear fix the ray length is the distance between those two points, not the interval length, so a tracer that marches a fixed length from the start gets it wrong.
- The upper probes are found from the lower probe's position, not from where its ray ends. In 2D with cell-centered probes the top-left upper probe is `floor((probe − 1)/2)` and the weights are `fract(probe·0.5 + 0.25)`.
- Interpolation must be done by hand from direct texel reads. Leaving hardware filtering on is the most common reason a bilinear fix shows banding or still leaks.
- The top cascade has nothing above it and needs no bilinear fix.
- Near cascade 0 the four rays can point in nearly opposite directions. This looks wrong in diagrams but causes no visible error, because the bend shrinks as intervals grow.
- With pre-averaged storage, the rays of an upper group start at slightly different points, so the four fix rays do not land exactly on them. Tracing 16 rays, one to each upper ray start, is very slightly better and not worth 4× the rays.
- **Forking** starts every group of child rays at one shared point, which makes paths fully continuous and removes the last bit of leaking. It also lowers angular resolution, and in practice people saw no measurable gain and sometimes worse aliasing, so it is usually left off.
- **Two samples instead of four:** with direction-first storage, two neighboring upper samples with weights `a` and `b` can be read with one hardware-filtered fetch, `a·s0 + b·s1 = lerp(s0, s1, b/max(a + b, 1e−7))·(a + b)`. Rays still cost the same, so this only trims merge reads.

## Why it works

- In vanilla RC a lower ray takes light from four upper probes that it cannot all see, because the upper probes look at the scene from other positions. Their occlusion was never tested from the lower ray's point of view, so light is double counted or missed where a cascade boundary crosses a source. The bilinear fix traces a path to each upper probe and tests that occlusion before interpolating.
- The bilinear fix interpolates continuous paths, never the end points of disconnected intervals, so it has no parallax. The theory that any such "watertight" scheme must conserve fluence and remove ringing has a known counterexample: starting the fix halfway along the interval to save tracing (`MERGE_FIX 2` in Shadertoy [4ctXD8](https://www.shadertoy.com/view/4ctXD8)) still rings.
- Ringing comes from mismatches across the ray direction, not gaps along it. Overlapping intervals along the ray, `L[a,+∞](p) ≈ Merge(L[a, b+D](p), L[b,+∞](p − d·D))`, did not remove ringing.
- A second 2D explanation: light falls off as `1/r` in 2D, but interpolation between probes falls off linearly, and the mismatch shows up as rings.
- The bilinear fix removes most leaking through thin walls. With a watertight tracer (sphere tracing or DDA, not fixed steps) it needs no interval overlap, while parallax fixes depend on overlap.
- The fix does not remove blocky interpolation patches in dark areas. Those come from the probe resolution and show most on OLED screens; cubic interpolation was suggested but not tested.
- Vanilla RC has a minimum penumbra angle by design. Shadows that look too soft or splotchy behind small, sharp sources are expected and are what HRC fixes in 2D.

## Other fixes

- **Parallax fix:** keep the vanilla ray. For each upper probe, take the angle of `ray_end − upper_probe`, convert it to a fractional direction index (`angle·count − 0.5`), interpolate the two nearest upper directions, merge, then blend the four upper probes bilinearly. Shadertoy [4ctXD8](https://www.shadertoy.com/view/4ctXD8) has inner and outer variants (`CastMergedIntervalParallaxFix`). Pre-averaging weakens it noticeably, because the averaged upper texels no longer hold separate directions.
- **Connection points:** each 2×2 block of lower probes shares one connection point at its center plus half the interval, and each upper probe has four. Rays run to the points and are joined there, which is watertight at the cost of vanilla. It removed halos but made resolution change unevenly along penumbras. It worked for participating media too.
- **Staggered interval sets** (idea): two sets of overlapping intervals whose seams fall in different places, with each point reading the set that is reliable there. Choosing is easy with hit distance and unsolved for media.
- **Mask fix** (`MERGE_FIX = 3` in 4ctXD8): fades between the masks of two cascades where they overlap. Described as unreliable.
- **Odd branching:** with ×3 directions per cascade, a third of the upper rays line up with lower rays and can be extended without interpolation. It made little visible difference.
- **Bilinear fix as a 2×2 post pass** (idea): trace vanilla and interpolate 2×2 probe blocks afterwards. Nobody found a watertight way to do it.

## Cheaper fixes and their costs

Costs are relative to vanilla RC in 2D unless the row says otherwise. Ringing and leaks have the same cause, rays that do not connect across cascades, so a fix that connects them removes both.

| Fix | How it works | Cost and result |
|---|---|---|
| Bilinear fix | Four rays per lower ray, one to each upper probe | About 4× the rays; the reference result. One estimate puts it at the cost of rendering vanilla at twice the resolution; one unoptimized build went from 5 to 11 ms at 1080p |
| Parallax fix | Per upper probe, interpolate the upper direction that sees the vanilla ray's end | About 20% slower than vanilla. Not watertight; needs interval overlap |
| Nearest fix with forking | Each group of four rays shares a start and runs to the start of the nearest upper probe's rays | No more rays than vanilla, about a quarter of the bilinear fix. Removes ringing and leaks; blocky penumbras that grow with distance. Without forking, nearest merging leaves halos |
| Nearest-interlaced | Pick one of the four upper probes per lower probe so that no upper probe is nearest to two lower probes in a 2×2 block | Free, plus 1/4 of the merge reads. Smooth field with a dithered look; neighbors disagree, so penumbras jitter |
| Circle-intersection fix | Keep the ray straight and end it where it crosses each upper probe's interval-start circle | About 3× faster than the bilinear fix; a small checkerboard on cascades 0 and 1, which keep a vanilla or bilinear merge |
| Two-tap diagonal | Offset the grids so each lower probe sits on a diagonal between two upper probes, then interpolate those two | Bilinear-fix rays drop from 4× to 2× in 2D and from 8× to 3× in 3D. One build cut frame cost by 33%; worse in motion, JPEG-like artifacts. A parallax fix on top cancels most of the gain |
| Stochastic bilinear fix | Trace to one random upper probe per sample | 1× rays; film-grain noise, acceptable mainly for pixel art |
| Temporal bilinear fix | Trace one of the four fix rays per frame | 1× rays per frame, four frames to converge |
| Gear-tooth intervals | Alternate interval starts and ends by direction parity (starts ×1.1 or ×0.885, ends ×1.115 or ×0.9), so each boundary overlaps by 1.5% of the base and steps in and out like gear teeth ([XffcD7](https://www.shadertoy.com/view/XffcD7), [code notes](2023_rc_shadertoys.md#xffcd7-kornelski-gear-shaped-intervals)) | About free; halves ringing and moves the problem edge. Angle-based offsets give star shapes |
| Interior mask | Rays that start inside a solid return black on every cascade but 0 ([gist](https://gist.github.com/RandyGaul/7a2b53eced08dcec4e08f591dad7724c)) | Free; ringing becomes hard to see above 1080p when solids are larger than the cascade 0 interval. Darker at 512², and shadow ringing stays |
| Interval overlap | Extend each interval by about `√2` × the upper probe spacing | Free; fixes leaks, not ringing. Large overlaps give halos and count partial absorbers twice |
| Wider merge filter | Blur 5 taps while upsampling during the merge | No extra rays; smooths vanilla penumbra aliasing (vanilla merging uses only about half the cones). Does not help the bilinear fix |

- **Cascade −1 gathering:** when cascade 0 has fewer probes than pixels, trace each pixel from 0 to the cascade 0 start during the final gather and blend the four nearest cascade 0 probes. It adds no ringing and works like a bilinear fix with one cascade 0 ray. With probes every 2 px it matches one probe per pixel in quality, and with fp16 storage it makes the bilinear fix cost about what vanilla did. Skip pre-averaging on cascade 0 when using it. `C_MINUS1_GATHERING` in [4ctXD8](https://www.shadertoy.com/view/4ctXD8) is the reference; in 3D it removes the need to store cascade 0, the largest memory saving found.
- **Forking with the bilinear fix** worked for walls at least 4 px thick without mipmaps. Forking lowers angular resolution, so doubling cascade 0 directions compensates.
- **Simplex grids** cut interpolation lookups from 4 to 3 in 2D and from 8 to 4 in 3D. A hexagonal 2D grid interpolates 3 neighbors, slightly better than bilinear at the same cost ([Dddfz7](https://www.shadertoy.com/view/Dddfz7)).
- **Bicubic** merging from four hardware taps helps vanilla a little ([GPU Gems 2, ch. 20](https://developer.nvidia.com/gpugems/gpugems2/part-iii-high-quality-rendering/chapter-20-fast-third-order-texture-filtering)); whether it helps with the bilinear fix is disputed.
- **Adaptive ray skipping:** skipping angular rays in upper cascades where about 8 nearby lower probes agree saved about 19% of rays at above 50 dB PSNR over 50 scenes; an aggressive 40% mode was visible ([demo](https://mebyz.github.io/adaptive-radiance-cascades/)).

## Scaling and setups

- **Notation:** `2x/4x` means probe spacing ×2 per axis (a quarter of the probes in 2D) and directions ×4 per cascade. 2x/4x keeps every cascade the same size; 2x/2x halves each cascade, so the total stays under twice cascade 0. Some people write the spatial factor in full, so 2x/4x per axis becomes 4x/4x.
- **Defaults that work in 2D:** one probe per pixel, 4 cascade 0 rays of length about `√2` (1.4 to 2 px), intervals ×4 per cascade, about `log4` of the screen diagonal cascades (about 5 at 512², rarely more than 6). Interval scaling should match angular scaling.
- **2x/3x** costs a fraction of 2x/4x for similar quality with the bilinear fix and was preferred on a Steam Deck; a third of the rays line up with the cascade below. Memory is 2.75× cascade 0 against 1.0× for constant-size cascades. Three cascade 0 rays may show moiré.
- **2x angular branching** needs many more cascade 0 directions (about 32) and longer first intervals (16 to 32 px). It looks poor without them, and running out of memory at 32 rays was reported. Switching from 4x to 2x after about 64 directions is an option for large scenes.
- **Higher branching** (8× and up) gives sharper results at equal memory and suits cheap per-ray methods such as line sweeping; 16× looks bad without cascade −1 gathering. Two cascades at 64× were sharper than 4× but slower.
- **Probe reduction** should be at most half per axis per cascade; quartering per axis aliases heavily.
- **One shipped 2D game** (Switch target) used three 2x/2x cascades: C0 384×256×4, C1 192×128×8, C2 96×64×16, stored in 3D textures with the angle on Z (repeat wrap, hardware filtering). Each cascade reads a progressively downsampled scene with one fetch per direction, weighted by `pow(2, i²)` per cascade to keep the single fetch from leaking (others argued 12 fetches are needed). A Gaussian after downsampling stabilized it. RC carries indirect light only; point lights are direct, with shadows marched in a GI depth buffer.
- **Low resolutions** suit HRC better than vanilla; for 240p to 360p pixel art, either use HRC or run RC above output resolution and downscale.

## Formats and color

- **Formats that worked:** RG16F for jump-flood coordinates, R11G11B10F for radiance, R16F for distance, RGBA16F when volumetric alpha is needed, RGBA8 for surfaces. Going from RGBA32F everywhere to these took one build from 81 to 240 fps at 768² on an RTX 3050 laptop, because RC is memory bound and speed tracks format size.
- **8-bit jump flood or distance textures fail:** they cannot hold positions beyond 256 and return false hits 1 to 2 px from surfaces. RGB10A2 is also too small. Full-precision JFA fixed shimmer in one build.
- **Color space:** do all RC math in linear space. Convert sRGB inputs before any interpolation, since converting after a hardware bilinear fetch is not equivalent, and encode once at output. A plain power curve in place of the piecewise sRGB curve gave blocky shadows that cut to black. Gamma applied only when sampling gave green ringing.
- **Range:** RC values exceed 1, so RGBA8 cascades clamp and band. White emitters at 1.0 look muted; emission around 5 to 10 looked right. Tone mapping per ray is wrong; tone map the result.
- **Merge result:** RC merging already produces `1/r` falloff in 2D, so no manual attenuation is needed.

## Measured 2D timings

Hardware and settings are as reported; most builds are unoptimized research code.

| Setup | Time |
|---|---|
| 512² probes, laptop RTX 3080 | 1.85 ms |
| 1024² vanilla, WebGL half floats, RTX 3080 Ti | about 2.5 ms |
| 1024², 6 cascades, RTX 4070 Super (framework overhead included) | 8.8 ms |
| 3440×1440, probes every 2 px, direction-first vanilla in Godot, RTX 2070 Super | about 4.5 ms |
| 1080p, vanilla plus bilinear fix, 4 to 5 cascades | 7 ms |
| 3840×2160, 2x/3x with bilinear fix | 8 ms |
| 8K, 6x/6x, 238M mostly short rays | 3.5 ms |
| 480×272 upscaled to 1080p | 2 ms |
| 1080p on a GTX 1080, after moving ray marching to quarter resolution | 200 → 15.6 ms |
| 4K output from quarter-resolution cascades, GTX 1060 | about 12 ms |
| Steam Deck, 320p | about 7 ms |
| 640×480 on a Radeon 760M | about 16 ms |
| Jump flood at 512×256, RTX 2080 Super | about 10 µs |

A basic compute path tracer took about 10× vanilla RC's time at the same resolution, and vanilla RC at 1024² matched about 16 path-traced rays per pixel.

## Cost in 3D

- The bilinear fix costs one ray per interpolation node. A rectilinear 3D grid has 8 trilinear corners, so the fix costs 8× and was called a dealbreaker. A simplex (tetrahedral) grid has 4 corners, so the fix would cost 4×.
- In 2D the fix costs 4× the rays. Rendering at half or a quarter of the resolution with the fix was preferred to vanilla at full resolution.

## Parameters that look like merge bugs

- **Cascade 0 interval:** it should be at least the diagonal of the cascade 0 probe spacing (`√2·spacing` in 2D). Shorter intervals bring cascade `N` and `N+1` ray ends so close that interpolation squeezes into a small space, which shows as bent rays, small leaks and flicker under motion. Too-short intervals were the most common mistake.
- **Flicker under motion:** caused by low probe density, short intervals, or rays that start at the probe center instead of the interval start. Adding noise hides it; more cascade 0 rays or probes fix it.
- **Light size:** a light resolves only if its size is above `2π·t0/N0` (`t0` cascade 0 ray length, `N0` cascade 0 directions), and about twice that by the Nyquist limit. A 5 px light flickered with 16 directions and a 10 px interval.
- **Interval starts** must form one geometric series with no gaps or overlaps, `[0, 1), [1, 4), [4, 16), …`. A common bug computes the start from one series and the length from another.
- **Scaling factor:** a 2D test of ×2, ×3, ×3.5, ×4, ×6 and ×8 found ×3 and ×3.5 best by eye and the rest clearly worse. All parameters depend on each other and there is no measured optimum; the trade is between aliasing (longer intervals) and softness (shorter ones). Interval scaling is usually matched to angular scaling.
- **Merge rule:** merging is front-to-back premultiplied alpha, not addition. Schemes that fade, pre-average, use mips or the inner parallax fix need a continuous alpha, so binary alpha shortcuts break them.

## Debugging routine

- **White furnace test (2D):** draw any closed, hollow emitter with a known color such as `(1.0, 0.5, 0.0)`. Outside, radiance should approach half the emitted value; inside, it should match it. A hue shift or a dark result means sRGB handling is wrong; a wrong inside means a missing top cascade or intervals that are too short.
- Render one cascade alone merged down (for example only cascade 4) to find which level is wrong.
- Stretch the cascade 0 interval 50× to see individual rays.
- Return zero radiance for reads outside the texture. Without it, light wraps around to the opposite edge.
- Breaks along the cardinal directions mean the merge reads the wrong probes.
- Check the interpolation code on plain texels against hardware filtering. Probe placement and the fix's ray offsets must use the same convention; sampling at the origin should give 0.25 to each of the four upper probes in every cascade. Vertex-centered probes look aliased.
- Use integer math for probe and texel indices. Float rounding in index math caused wrong merges.
- Replace the tracer with a plain per-pixel stepper that stops on a hit (step `d/max(|dx|, |dy|)`, length in whole pixels) to separate tracer bugs from RC bugs. Distance fields from jump flooding can return zero just outside a surface, and a step cap shorter than the interval ends rays early.
- Keep test scenes trivial: one emitter, one occluder, thin walls and hollow boxes.
- A square light looks darker along the axes than along the diagonals because it covers a smaller angle there; this is not a bug.

## Links

- Ray visualizer with bilinear and other fix modes: https://www.shadertoy.com/view/4clcWn
- GLSL bilinear-fix shader (GM Shaders): https://github.com/Yaazarai/GMShaders-Radiance-Cascades/blob/main/RadianceCascades-Optimized/shaders/Shd_RadianceCascades_BilinearFix/Shd_RadianceCascades_BilinearFix.fsh
- Ray layout visualization: https://www.desmos.com/calculator/uvnbzgmrmf. The graph ("radiance cascades vis", 2025-09) draws cascade `c` and `c + 1` for one probe block: cascade `c` has `4^(c+1)` direction bins centered at `360°·n/4^(c+1) − 360°/(8·4^c)`, each with four children in cascade `c + 1`; with `i = 2√2`, cascade `c` spans `[4^(c−1)·i, 4^c·i]` (from 0 at `c = 0`) and the children `[4^c·i, 4^(c+1)·i]`, the same `base^(k−1)` to `base^k` pattern as jason.today's intervals. Its folder title warns that the probe positions are wrong.
- WebGL demo with vanilla, bilinear, linear and nearest toggles: https://jason.today/ascii-gi. "ASCII: Globally Illuminated" lets typed glyphs (8×8 cells of a 128² font atlas) emit and block light on a 512² canvas (300×400 on mobile). It is jason.today's RC: `cascadeCount = ceil(log(diagonal)/log(base)) + 1`, 6 at 512² with base 4; cascade `j` traces `base^(j+1)` rays at spacing `√base^j` texels; the interval is `1.41·modifierHack·rayInterval·cascadeInterval` with `modifierHack = base < 16 ? basePixelsBetweenProbes : √base`; misses take the upper cascade at mip `log₂(basePixelsBetweenProbes)` with the early-return merge. Defaults: 1 px between base probes, base 4, interval overlap 0.04 (−1 to 2), bilinear fix on, sun off, and a "reduce demand" mode that spreads the work over two frames. The bilinear-fix uniform's effect was not traced.
- 2D volumetric RC with the bilinear fix: https://jsfiddle.net/cbenn/c0dyh6pm. The fiddle ("Volumetric Radiance Cascades 2D", WebGL2) is the same design as codyjbennett's wfyyDz: 8 cascades with spacing `2^c` px and `4^c` directions (one at cascade 0), intervals `0.2·[4^c, 4^(c+1)]` px (cascade 0 [0, 0.8]) marched in `16·2^c` integer-texel steps with `rgb += scene.rgb·T·scene.a` and `T *= 1 − scene.a`, merged as `near.rgb + far.rgb·near.a`, `near.a·far.a`, and the bilinear fix casting four intervals to the four upper probes, each blended over four upper directions, averaged with weight 0.25. The scene is an orange and a white emitter with a near-transparent absorber between them (alpha 0.01), drawn at twice their radius by the same `length − r < r` test; it adds sRGB conversion and dithering and cites the m4xc fundamentals article.
- CoreCascade, a 2D reference in Go with path tracing for comparison: https://github.com/s-macke/CoreCascade
- Discontinuity-aware interpolation, suggested for sharper shadows in vanilla RC: https://dl.acm.org/doi/10.1145/1944846.1944849. The DOI resolves to Egan, Hecht, Durand and Ramamoorthi, "Frequency analysis and sheared filtering for shadow light fields of complex occluders" (ACM TOG 2011), whose abstract describes diffuse soft shadows from mid-to-far complex occluders through a frequency analysis of planar area lights, a 4D cache of shadowing and depth, and a sheared reconstruction filter applied at receiver points; it says nothing about discontinuity-aware interpolation, and the full text was not reachable. Either the link or its label is wrong. The paper's idea still bears on RC: a sheared filter reconstructs penumbrae from sparse shadow samples by following the occluder's depth, which is what a depth-aware merge between cascades would need (inference).
- Reference fix shaders (bilinear, nearest, interlaced) from GM Shaders: https://github.com/Yaazarai/GMShaders-Radiance-Cascades/tree/main/RadianceCascades-Optimized/shaders
- Circle-intersection fix: https://www.shadertoy.com/view/lcfcR2 and https://github.com/chronicl/LegitCascades/blob/patch-1/Scaling.ls. In Shadertoy code the fix comes from Mytino's MfXyRj, a fork of 4ctXD8 that makes it the default: each of the four bilinear-fix rays ends where it meets the circle of radius `t_end` around its upper probe, the start of that probe's interval, without a guard for rays that miss the circle. lcfcR2 keeps it as work-in-progress variant 0 with the circle measured from the probe, and XcfyDj draws it ([code notes](2023_rc_shadertoys.md#mfxyrj-mytino-the-circle-projection-fix)).
- Configurable 2D implementation for comparing parameters (imnethen, Rust and wgpu, no license): https://github.com/imnethen/theradiancecascades. A GUI sets the cascade 0 interval length (default 1 px), probe spacing (1 px) and ray count (4), the spatial scaling S (1.1 to 9, default 2), the angular scaling A (2 to 16, default 4), the cascade count (7), an Offset or Stacked probe layout, and vanilla or bilinear-fix merging. Intervals start at `L0·(A^c − 1)/(A − 1)` with length `L0·A^c`, so they stay contiguous for any A. Probes sit at `0.5 + s_c·i`; the Offset layout moves them back by `0.5·(S^c − 1)/(S − 1)` cascade 0 spacings, which puts each coarse probe midway between finer ones, while Stacked puts it on top of a fine probe. Cascades are RGBA16F packed into pairs of `u32` in two ping-pong buffers, and every cascade is its own queue submit. Every painted pixel is a solid emitter of its own color, with no transmittance or sky, and the jump-flood sphere trace takes up to 1024 steps. The vanilla merge interpolates the same ray index bilinearly across four upper probes; the bilinear fix traces from `p + dir·start_c` to each of the four upper probes' `start_(c+1)`, up to four times the marching. At 1080p with the defaults each of the 7 cascades holds 2.1 to 2.3 M texels, a frame runs 14.9 M threads and 59.8 M rays, and the two buffers take 36.6 MB (derived from the code). Two sentinel constants (1e9 and −2e9) exceed the half-float range of the distance and seed textures and store as infinity, and the jump flood's `dist < 2e9` test never accepts them.
- 2D volumetric RC with the bilinear fix and per-sample absorption: https://shadertoy.com/view/wfyyDz ([code notes](2023_rc_shadertoys_hrc_3d_and_other.md#wfyydz-codyjbennett-2d-volumetric-cascades-with-the-bilinear-fix))
- 4K browser demo with one cascade 0 probe per 4 px: https://mdxish.com/jasonjmcghee/f71708c18ee3604e8249ccb824275fbc?width=3840&height=2160. The page renders gist f71708c18ee3604e8249ccb824275fbc, a version of jason.today's RC article that predates the interval-overlap term; the "4k" is the URL's resolution, not a feature of the text. A second playground gist, 24f6577fd45962112a26dd09bb20bff7 ("webgl rc", code only), holds the article's classes plus a `VolumetricRC` whose march accumulates `rgb += radiance.a·rgb·(1 − T)/max(a, 0.001)` with `T = exp(−a·step)` or `(1 − a)^step` and merges `cur.rgb + cur.a·up.rgb`, `cur.a·up.a` for every ray, while the plain `RC` keeps the early return (a hit stops merging); both default the interval overlap to 0.1. The mdxish pages themselves were not rendered.
- Animated RC explanations (Motion Canvas): https://github.com/mxcop/mocan-graphics/tree/main/src/scenes/radiance-cascades (mxcop's animations for the fundamentals article). Fourteen scenes, each one idea: a 16-ray probe with rays of length 240 beside a 32-ray probe with rays of length 480, with a target that turns red while the shorter probe cannot reach it; doubled spacing and doubled rays per level; the 4×4 texel block per probe in memory, with direction index `x + 4y` at angle `2π(i + 0.5)/16`; four lower probes sharing one upper probe; incremental interval splits (6 rays on [0, 120], 12 on [120, 280], 24 on [280, 640]) against the same long interval re-split with a constant ray count; bilinear weights from the fractional part of `dest/size − 0.5` (0.5625, 0.1875, 0.1875, 0.0625 for a probe a quarter of the way between upper probes); a blocked interval stopping a merge; spatial weights of 0.5, 1.0, 0.25 and 0.5 around a cell; and a brute-force 2D direct-light shader (512 rays per pixel, a bar light and a bar occluder) animated as the occluder moves and as probe spacing sweeps from 0 to 256 px. The cascade helper uses branch factor B (2 or 4) with `tmin = L·2^(s·i)`, `tmax = L·2^(s·(i+1))` and `N0·2^(s·i)` directions, `s = B/2`; the "forked" probe draws child rays from the center angle of their parent group.
- Tantalum, a 2D spectral path tracer used for reference images: https://benedikt-bitterli.me/tantalum/ (Benedikt Bitterli; WebGL demo and libpng/zlib-licensed code at https://github.com/tunabrain/tantalum). It is a light tracer in intrinsic 2D radiometry (Jarosz et al. 2012), so radiance is per metre and BRDFs are rederived for 2D: Lambert is 1/2, normalized Phong uses `Γ((3 + n)/2)/(√π·Γ((2 + n)/2))` and is not sampled, and a logistic microfacet distribution `D(θ) = (1/4s)·coth(π/4s)·sech²(θ/2s)` samples by `2s·artanh((2ξ − 1)·tanh(π/4s))`, dropping the cosine term, which the article calls wrong at high roughness. Photons are emitted and traced in wavefront passes, one bounce per pass (Laine et al. 2013), with state in four RGBA float textures, and each path segment is drawn as a line into every pixel it crosses with additive blending, trading noise for line-shaped error; the measured quantity is fluence per pixel with a box filter. GPU lines deposit too little energy off-axis, so each segment is scaled by `√(dx² + dy²)/max(|dx|, |dy|)`, about 1.41 at 45°. Dispersion uses Sellmeier indices with invented coefficients, over 256 spectral samples from 360 to 750 nm drawn by a 1024-entry inverse CDF, in batches of 512 × 512 rays. The demo has 7 scenes, 5 emitter shapes, white, incandescent (1000 to 10000 K, default 5000 K) and gas-discharge spectra, paths of up to 20 segments (default 12, so 11 bounces) and 10⁴ to 10⁷ light paths (default 10⁶), at resolutions from 820 × 461 to 4096 × 2160. It has no participating media; homogeneous media exist only in an unreleased C++ version, and the article calls heterogeneous media very challenging.
- Texture formats supported on the web: https://floooh.github.io/sokol-html5/pixelformats-sapp.html. The demo fills its sample, filter, render, blend and MSAA columns from `sg_query_pixelformat` at run time, so the values depend on the browser and GPU; the rules come from `sokol_gfx.h` (master, fetched 2026-10-18; the demo's pinned version may differ). On WebGL2, RGBA16F always samples and filters, and with `EXT_color_buffer_float` or `EXT_color_buffer_half_float` it also renders, blends and multisamples. R11G11B10F renders and multisamples but never blends, and filters only with `OES_texture_float_linear`. RGBA32F filters only with `OES_texture_float_linear` and blends with `EXT_float_blend`, though one branch sets blending without checking that extension. RGB9E5 can only be sampled and filtered, on WebGL2 and on WebGPU. On WebGPU, RGBA16F supports all five uses, R11G11B10F only sampling and filtering, and RGBA32F filters only with `float32-filterable` and blends only with `float32-blendable`. RGBA16F is therefore the one portable filterable float render target for a web RC.
