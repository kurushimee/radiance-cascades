# Merging fixes and ringing

| | |
|---|---|
| Date | 2024-08 to 2026-09 |
| Kind | Collected implementation findings; claims are unverified unless a public link backs them |
| Related | [2024_osborne_radiance_cascades_radiative_transfer.md](2024_osborne_radiance_cascades_radiative_transfer.md), [2023_rc_shadertoys.md](2023_rc_shadertoys.md), [2024_yaazarai_gmshaders_radiance_cascades.md](2024_yaazarai_gmshaders_radiance_cascades.md), [../topics/artifacts_and_fixes.md](../topics/artifacts_and_fixes.md) |

Most of this note is about 2D RC, where the bilinear fix and its alternatives were built and debugged. It adds the exact order of operations for the bilinear fix, the reasons behind it, the costs of the cheaper fixes, the scaling and format choices that worked, the parameter mistakes that look like merge bugs, a debugging routine, and measured 2D timings. The parts that matter for 3D are the cost argument for the fix on different grids and the parameter rules, which hold in any dimension.

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
| Gear-tooth intervals | Make every other ray longer ([XffcD7](https://www.shadertoy.com/view/XffcD7)) | About free; halves ringing and moves the problem edge. Angle-based offsets give star shapes |
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
- Ray layout visualization: https://www.desmos.com/calculator/uvnbzgmrmf
- WebGL demo with vanilla, bilinear, linear and nearest toggles: https://jason.today/ascii-gi
- 2D volumetric RC with the bilinear fix: https://jsfiddle.net/cbenn/c0dyh6pm
- CoreCascade, a 2D reference in Go with path tracing for comparison: https://github.com/s-macke/CoreCascade
- Discontinuity-aware interpolation, suggested for sharper shadows in vanilla RC: https://dl.acm.org/doi/10.1145/1944846.1944849
- Reference fix shaders (bilinear, nearest, interlaced) from GM Shaders: https://github.com/Yaazarai/GMShaders-Radiance-Cascades/tree/main/RadianceCascades-Optimized/shaders
- Circle-intersection fix: https://www.shadertoy.com/view/lcfcR2 and https://github.com/chronicl/LegitCascades/blob/patch-1/Scaling.ls
- Configurable 2D implementation for comparing parameters: https://github.com/imnethen/theradiancecascades
- 2D RC Shadertoy: https://shadertoy.com/view/wfyyDz
- 4K browser demo with one cascade 0 probe per 4 px: https://mdxish.com/jasonjmcghee/f71708c18ee3604e8249ccb824275fbc?width=3840&height=2160
- Animated RC explanations (Motion Canvas): https://github.com/mxcop/mocan-graphics/tree/main/src/scenes/radiance-cascades
- Tantalum, a 2D spectral path tracer used for reference images: https://benedikt-bitterli.me/tantalum/
- Texture formats supported on the web: https://floooh.github.io/sokol-html5/pixelformats-sapp.html
