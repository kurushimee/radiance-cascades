# Holographic RC

| | |
|---|---|
| Date | 2024-11 to 2026-10 |
| Kind | Collected implementation findings; claims are unverified unless a public link backs them |
| Related | [2025_freeman_holographic_radiance_cascades.md](2025_freeman_holographic_radiance_cascades.md), [2025_hrc_and_2d_reference_implementations.md](2025_hrc_and_2d_reference_implementations.md), [2026_merging_and_ringing.md](2026_merging_and_ringing.md), [../topics/core_theory.md](../topics/core_theory.md), [../topics/artifacts_and_fixes.md](../topics/artifacts_and_fixes.md) |

HRC (holographic RC) works in 2D in practice. This note covers what implementers learned after the paper: which cascades to trace and which to build from extensions, the artifacts and their fixes, bandwidth-driven optimizations with timings, why 3D and screen-space HRC are not practical, and later variants such as half HRC, polygonal HRC, gradient RC and the line-space view. For a 3D project, the useful parts are the cost of 3D HRC, the cone-weighting rules, and the idea of building long intervals from short ones.

## How it behaves next to vanilla RC

- Each cascade halves probes along one axis only and doubles directions, so the total interval count per cascade stays constant. A probe in cascade `N` has `2^N + 1` rays, and ray length equals plane spacing, so length only doubles per cascade: a 1024 px scene needs 10 cascades where vanilla 4x needs 5. Every cascade is needed; dropping from 11 to 8 left artifacts.
- HRC has no ringing and no leaks and needs no bilinear fix, because its rays continue each other without overlapping. Interpolation is always 1D between adjacent probe lines and never spans a long distance, so penumbras are sharper than with the bilinear or parallax fix.
- It works for lights larger than about 8×8 px; 16 px circles looked clean. It is poor at pixel-art resolutions, where single-pixel lights show crosses and streaks.
- In 2D each cascade uses the same memory as vanilla RC with 4× interval scaling. Extensions need every cascade stored, so the two-texture ping-pong of vanilla RC does not work.
- One argument says HRC does not exploit the penumbra condition: its spatial-to-angular ratio rises per cascade, so far-field penumbras can be sharper with vanilla 4x.

## Tracing and extensions

- **Extension** builds a cascade `N` interval by chaining two cascade `N−1` intervals end to end, merging radiance and transmittance without tracing. The usual split is to trace cascades 0 to 2 or 0 to 3 and extend the rest. With plain DDA, turning extensions off made one stress scene about 40× slower.
- **Starting extensions at cascade 0** leaves a cross (X) around small emitters and around emitters inside occluders, because extensions lack the angle term of a traced ray, and it caps angular resolution at the 16 to 20 starting rays, so mirrors are out. Starting at cascade 3 removes the cross but aliases more per pixel. Reports disagree on which is more accurate; tracing to cascade 4 and extending to 7 matched or beat pure tracing.
- Extensions bend rays slightly ([visualization](https://deadlyredcube.com/RCStuff/extensions.html), [code notes](#deadlyredcube-extensions-and-oriented-probe-lines)) and are blurrier rather than more accurate. Some rays must connect exactly, or the result over-diffuses.
- **Exact lengths:** computing a shorter and a longer extension and interpolating the endpoint between the two nearest planes reproduces vanilla interval starts and is still cheaper than tracing.
- Extensions also speed up vanilla RC; one pixel-art project used them that way.
- Cascade 0 is 1 px long, so it needs no tracing or storage; the final gather traces one ray per pixel to the cascade 0 start.

## Merging rules

- **Directions:** use half-integer tangents, `(i + 0.5)/N`. They never reach 45°, so adjacent frustums do not count the diagonal twice. Integer indices with `2^N + 1` rays give bright crosses on diagonals.
- **Cone weights:** tangent-spaced rays cover unequal angles, so multiply each cone's radiance by its angular size, `atan` of one edge minus the other, when the cone is built. Weighting after merging counts rays twice. Missing weights give an X pattern; equal weights give square isolines. `1/dot(mid, mid)` approximates the weight within 0.002. Weights scale radiance only, not transmittance.
- The X also appears in any tracer with equal-length rays at all angles, so traced rays need the optical-depth correction too (step length `1/|cos θ|`).
- **Even planes** (b-type rays) have no upper probe at their position. Trace twice as far, merge the near and the far plane, and average. Merge first and interpolate after; the other order breaks occlusion. Weighting b-type rays is the main unsolved problem: distance-based weights work for opaque scenes and fail with transparency. Merging only odd planes removes that dependence and halves tracing.
- **Quadrant offset:** offset each quadrant by 1 px when combining the four frustums, or diagonal rays counted by two quadrants form a plus sign. The offset also lets the last cascade be dropped.
- **Normalization:** accumulating each ray's weight in alpha during merge-down and dividing at the end makes contributions sum to 1 for any merge pattern.

## Artifacts and fixes

| Artifact | Cause | Fix |
|---|---|---|
| Checkerboard | Odd and even probe rows never interact | The paper's cross blur; an opacity-aware blur that skips neighbors with different opacity; or half HRC, which drops odd rows and interpolates at the end for about 2× speed. A 2×2 box with a half-texel offset equals a 3×3 binomial |
| Cross around small or enclosed emitters | Extensions from cascade 0 lack the angle term | Trace the first 3 or 4 cascades |
| Striations | Even-plane merging and heavy hardware interpolation in extensions | Costly to fix; fewer interpolated extensions |
| Flicker at frustum edges in motion | Edge rays get no diffusion | Extend left and right, then lerp the middle (2× extension cost), or shift edge rays 1 px |
| Leaks along the frustum | Probe density drops across thin solids | More probes along the plane |
| Seams between frustums | High air absorption | Lower absorption or more cascades |
| Opacity pop near 1 | 11-bit floats top out at 0.996 below 1 | Store absorption `1 − T` instead of `T` |
| False opacity on diagonals | R16F rounding gave 0.00138 against a 0.001 epsilon | Epsilon 1/512 |
| Color shift and smoke flicker | R11G11B10F cannot reach full white | RGBA16F; RGB9E5 crashed as a render target on an RTX 3080 and is not a WebGPU storage format |
| Dim or wrong brightness | sRGB converted twice, or before dividing by the four frustums | Linearize inputs once (pre-linearized textures also halved tracing cost) |

## Performance

HRC is bound by memory bandwidth (96% in one profile), so most gains come from writing less.

- One transmittance channel in alpha instead of RGB doubled speed in one build and cut cost by 25% and memory by 50% in another, at the cost of colored glass.
- Keep radiance and transmittance in one texture. Splitting them slowed extension from 0.08 to 0.15 ms and cone merging from 0.09 to 0.14 ms at 1024².
- Fewer probes along each plane: spacing growing to 8 px saved 70%, to 4 px 52%, to 2 px 27%. Half the probes with hardware vertical interpolation saved 50% at 4K and took 1024² from 27 to 14 ms.
- At 16:9, 44% of the short-axis probes are off screen. Dispatching fewer threads, or separate 1920×1080 and 1080×1920 textures, saved 20% to 40%.
- Dropping a pre-clear pass saved about 50% at 4K. Replacing `atan(y/x)` code with `atan(y, x)` or a lookup table saved about 5 ms at 1024². Per-level workgroup shapes gained 15%.
- On Apple GPUs, fragment shaders ran 1.2 to 1.8× faster than compute, because render targets are compressed and storage buffers are not ([WWDC 2021](https://developer.apple.com/videos/play/wwdc2021/10148/?time=581)). The speedup is the community's measurement; the talk gives the mechanism and no comparison: from 581 s it says that the ShaderWrite or PixelFormatView usage flag disables lossless compression of a texture, that ShaderWrite is needed for `write()` from fragment or compute functions but not for rendering into a colour attachment, and that uncompressed textures cost bandwidth when stored from tile memory. So the penalty follows the write path, not the shader stage (inference).
- Luminance at full resolution with color at quarter resolution: 4K in 8 ms instead of 12 (RTX 3080 Ti, WebGL) and 17 instead of 26 (M4 Max); 1024² under 14 ms on an iPhone 16.
- Quarter-resolution HRC with an edge-aware upscale ran 4K at 135 to 144 fps against 78 fps native on an RX 9060 XT, with softer shadows.
- Tracing an 8×8 probe block from shared memory cost 0.06 ms for four cascade 0 directions against 1.6 ms for DDA.

| Setup | Time |
|---|---|
| 512², 4×4 px light, 10 cascades ([tfKyRw](https://www.shadertoy.com/view/tfKyRw) is a similar 11-cascade build of one frustum without the extension step, over a three-frame ring; [code notes](2023_rc_shadertoys.md#tfkyrw-youssef_afella-one-frustum-with-paper-geometry); the same author's [WfyyDm](https://www.shadertoy.com/view/WfyyDm) runs four frustums at half resolution with ten levels, also without the extension step ([code notes](2023_rc_shadertoys.md#wfyydm-youssef_afella-four-frustums-in-one-buffer))) | 0.88 ms |
| 1024², 4 traced and 6 extended cascades, RTX 3080 | about 7 ms; about 3 ms with RGBA16 merges, RGBA8 extensions and cones built on the fly |
| 1024² and 2048² without stored cascade 0 or cone transmittance, RTX 3080 | 1.8 ms and 7.5 ms |
| Volumetric extensions from cascade 0, all four frustums | under 2 ms at 1024², 5 ms at 2048² |
| Volumetric-HRC, open source | 2.61 ms at 1024² on an RTX 3080; 0.75 ms at 512² on a GTX 970 |
| 1080p without extensions, 2x/2x with pre-averaging, RTX 3080 | 7 ms, against 23 ms for per-pixel SDF marching |
| 2048² and 4096² | 3 + 7 ms and 15 + 25 ms (extensions + merging) |
| 2048×1024 in WebGL on an RTX 4060 Ti | 5 ms |
| Godot luminance-only HRC, 1080p, RTX 3090 | 7.57 ms, 5.10 ms with caching |
| 1024², Radeon 760M | about 23 ms, then 60+ fps after a fix |
| Steam Deck | about 40 ms at 1024², about 10 ms at 512² |
| Unreal Engine 5 showcase: three HRC passes for three light layers, BVH tracing | 120+ fps at 4K |

How HRC compares with vanilla RC depends on cascade count and cascade 0 length, and reports conflict: about 2× vanilla 4x and 2× faster than the bilinear fix at equal base probes; 14 ms without extensions against 1.5 ms vanilla, about equal once mips are added; and poor on a Steam Deck, where 3× angular scaling was much faster than 2x/4x for similar quality.

## 3D and screen space

- 3D HRC needs `O(N⁴ log N)` memory and compute for an `N³` volume, and extensions are unsolved in 3D. Reported numbers: a 64³ cascade volume at 77 ms and 1.5 GB, 128³ at minutes per frame, a demo at about 20 fps on a laptop RTX 4090 ([video](https://www.youtube.com/watch?v=xT_7JtYXdNc)). 512³ does not fit in memory.
- A constant-memory 3D layout that worked: halve probes and planes per axis and multiply directions by 4 per axis, starting from 256×256 probes, one direction and 16×16 planes. Keeping probes while doubling directions violates the penumbra condition and looked bad. Plane spacing ×4 worked in 3D but added nothing in 2D.
- The case for 3D HRC is volumetrics. For surfaces, vanilla or sparse RC with shadow maps or next-event estimation for hard shadows is simpler.
- Screen-space HRC was judged impractical: extensions need intervals that meet end to end, which probes placed on the depth buffer break, and focal points must lie on probe lines.

## Off-screen light

- Extensions only cover the screen, so off-screen light must be traced separately and merged. Every cascade that leaves the screen needs world-space tracing, and covering twice the off-screen distance costs about 4×.
- Workable shortcuts: render 4× the area at a quarter of the resolution and crop; or cast about 30 CPU rays per light to find occluders and pass analytic circular light proxies to the shader (about 1 ms for 10 lights, no penumbra).

## Variants

- **Half HRC** drops every other probe row, which removes the checkerboard and simplifies the math ([shader](https://github.com/brucelevis/Holographic-Radiance-Cascades/blob/main/Half-HRC/shaders/Shd_HolographicRC/Shd_HolographicRC.fsh), described in [2025_hrc_and_2d_reference_implementations.md](2025_hrc_and_2d_reference_implementations.md#half-hrc-brucelevis-copy); the community notes credit it to a Yaazarai repository that does not exist).
- **Ring HRC** places probes on rings; about half the probes fall outside the scene, and ring counts need a lookup table.
- **Axis-aligned HRC** turns probes toward each ray direction. It cut tracing from 100 to 10 ms at 1024², but rays no longer share directions, so extensions and pre-tracing are impossible, and it ended up slightly slower than plain HRC.
- **Polygonal HRC** tiles space with polygons that never overlap or leave gaps: 1:1, 1:2 and 1:3 cones, or 1:1 bands and 0:1 wedges in line space, where the tiling is Bresenham lines and extending a level reduces to `srcD = D >> 1, err = D & 1`. It gives near-exact falloff with fewer directions, but no version has shadows yet ([demo](https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/PolygonalHRC45.ls&rev=master), [video](https://www.youtube.com/watch?v=AhbnwZFp5iE), [indexing code](https://github.com/entropylost/hrcviz2/blob/main/src/main.rs); the scripts are described in [2024_sannikov_legitcascades.md](2024_sannikov_legitcascades.md#polygonal-cascades)).
- **Primal and dual:** primal polygons gather from every pixel that contributes to a point; dual polygons splat to every pixel a source reaches. They looked equal in speed and accuracy. Primal handles point sources anywhere but aliases penumbras at probe size; dual gathers at any point, gives clean cone-shaped shadows and is easier to debug, but stores unoccluded radiance.
- **Gradient RC** stores a value and a directional derivative per probe direction and skips interpolation. Point-light falloff was good, motion stable and memory low, which fits sparse 3D, but occlusion still aliases ([demo](https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/GradientRC.ls&rev=master), [script](2024_sannikov_legitcascades.md#gradientrcls)).
- **Polygonal block layout** for 3D supports sparse extensions and sits closer to vanilla RC than to HRC ([demo](https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/PolygonalBlockRC.ls&rev=master), [video](https://www.youtube.com/watch?v=JcWFXYnYC5M)).
- **Line space:** an HRC probe direction is a bundle of lines, which makes HRC a Hough or Radon transform. Without occlusion it reduces to a convolution solvable with an FFT; occlusion is the open part. A diagonal basis, with probes `√2` px apart so each line crosses every pixel once, looked far more regular than a circular one. Exact point-light falloff needs each pixel painted by its line's intersection length with the pixel.
- **Other uses:** an HRC-based diffusion (Laplace) solver ran 129² in 3 to 4 ms ([demo](https://adrianmargel.ca/demo/holographic-cascades-diffusion/), [code notes](#adrian-margel-line-space-and-a-hierarchical-diffusion-solver)); an audio-attenuation prototype added about 50% on top of HRC.

## Debugging

- Test with one small light and one occluder, a white furnace scene, and point-source falloff against a path tracer. A moving source should show no preferred direction.
- Traced and extended versions of the same ray should match exactly. Streaks with alternating phases mean offset or UV bugs; non-uniform far-plane gaps mean an off-by-one.
- Visualize every interval that contributes to the pixel under the mouse, and push ray lengths 10× to reproduce the merge diagram.
- If two of the four frustums work, the bug is outside the shader. Compute dispatch IDs need +0.5 to hit texel centers, and wgpu storage textures are Y-down.

## Demos and visualizers read from code

None of these pages has prose or measurements; what follows is read from their scripts.

### deadlyredcube: extensions and oriented probe lines

`extensions.html` draws how HRC builds long rays from shorter segments on a square grid (default 32×32, width slider 2 to 64).

- Level `c` has `2^(c+1)` rays. Level 0's two rays both cover cells (0, 0) and (1, 0). The cell list of ray `r` at level `c` is the list of ray `r >> 1` at level `c − 1`, followed by the same list shifted by `(2^(c−1), ((r + 1) >> 1) − 2^(c−1))`, skipping repeated cells (`extensions.js` 121-146). Levels run up to `ceil(log₂W) − 1`.
- With `Extent = W − 1`, a long ray is assembled from the levels whose bit is set in `Extent`, descending into the lower or upper child by ray index (`DrawRayCover`, 203-272): width 32 (`Extent` 0b11111) draws levels 0 to 4, while width 33 (`Extent` 32) draws level 5 alone.
- Bent rays (`RenderProbes`, 275-349): each segment ends at `(x + 2^c, y + r − 2^c + 0.5)` and its two children start at that endpoint, offset ±0.5 in y, so a ray is a polyline whose direction changes at every junction. These are the bent rays that make extensions blurrier than straight traces ([tracing and extensions](#tracing-and-extensions)).
- `GetCascadeDistance` and `RayFromIndex` are never called, and several globals are implicit.

`orientedProbeLines.html` lays out probe lines by shearing instead of rotating (default grid 37×24, 5 levels).

- Level `c` has `4·2^c` directions at `(a + 0.5)/(4·2^c) − 0.125` turns, split into horizontal and vertical quadrants by `|cos| > |sin|` (`orientedProbeLines.js` 137-142).
- Probe spacing along the probe axis is `W/⌊W/2^c⌋`, so probes tile the view exactly instead of sitting at exactly `2^c`: at `W = 37` the spacing is 2.056, 4.111 and 18.5 at levels 1, 2 and 4 (153-170). Horizontal directions get grids of `⌊W/2^c⌋ × H` probes, vertical ones `W × ⌊H/2^c⌋`.
- Probe space maps to screen by scaling along the probe axis, then one shear about the view center, `skewX = −sin/cos` for horizontal directions or `skewY = −cos/sin` for vertical ones, an origin offset and a toroidal wrap (219-306). Since only one shear is non-zero, the sequential inverse is exact.
- `FindConnectingProbes` (384-458) links a probe at level `c`, direction `a`, to level `c + 1`, direction `2a + o`, at the next lattice row or column the ray crosses, accepting the link only if the direction and the offset agree within a dot product of 0.95 (about 18°) and the bracketing probes lie within squared distance 2. Hovering shows the accepted links in yellow and the failures in red.

### Adrian Margel: line space and a hierarchical diffusion solver

- `linespace` plots the 400 lines between two vertical segments (20 × 20 endpoints, 5 apart) as points `(b, 100·m)`, the intercept at `x = 0` and the scaled slope, so a bundle of lines becomes a region of line space; vertical lines divide by zero. `linespace-rotation` turns the endpoints by 0.01 rad per frame about a pin and plots both `(b, b + 100·m)` and `(b, 100·m)`, so the line-space cloud moves as the segments rotate.
- `holographic-cascades-diffusion` (titled "Holographic Cascades") solves steady-state diffusion on a 129² node grid (`2^7 + 1`), each node weighted 1/8 toward each of its eight neighbours (`init.js` 64-72). Positive scene alpha absorbs; barriers are stored as negative alpha and act as reflectors through the node's self term; each colour channel is a separate source term at 0.25.
- The solve is direct: 15 merge steps (`2·7 + 1`) alternate between merging block pairs along x and along y, eliminating the seam nodes between blocks by Gaussian elimination with `P[y] = M[m][y]/(1 − min(M[m][m], 0.9999999))` and `M'[a][b] = M[a][b] + M[a][m]·P[b]` (`nodePrimer.js`, `nodeElimination.js`), store each block's boundary-to-interior transfer operator, and apply the operators top-down to recover interior values (`valuePropagation.js`). This is nested dissection, a Schur-complement elimination over a block hierarchy, so the "HRC-based diffusion solver" (3 to 4 ms at 129²) shares HRC's merge-up structure of blocks rather than its rays (inference).
- A Jacobi residual pass with a 4-neighbour stencil, which does not match the 8-neighbour equation, is disabled. Sampling the input at `coord/2^7` with repeat wrap may make the last row and column read the first ones (not verified by rendering).

### jason.today/hrc

The page serves no article text; the HRC code is in its inline scripts.

- Defaults: probes at 1 px spacing (`hrcExtentScales` [0.25, 0.5, 1, 2], index 2), linear upscale, density scale 0.25, footprint seeding on, exposure 1, sRGB exponent 2.2, sun off. Four direction fields come from axis swaps and flips of the probe grid.
- Seeding: transmittance `t = exp(−densityScale·spacing·(−ln max(1 − α, 10^−4)))`, that is `(1 − α)^(spacing/4)` by default, and 0 for `α ≥ 0.999`; emission is the part of the scene colour above 1, `max(rgb − 1, 0)`, and the seeded radiance is `(1 − t)·source^2.2`. When the spacing exceeds 1.01 px, the seed averages 2×2, 4×4 or 8×8 sub-samples. Each axis pair has one atlas holding a direction and its opposite.
- Merging: `(near.r + far.r·near.t, near.t·far.t)`; an extended ray averages two such merges of lower-level rays in radiance and transmittance. Cone weights are slope-bin widths, `atan2(2s − 2n + 2, 2n) − atan2(2s − 2n, 2n)` with `n = 2^level`, π/4 at level 0. Even probes average two phases and odd probes use one; the comments say the phases alternate along the probe axis at level 0, which a 0.25/0.5/0.25 filter removes. The output sums the four direction fields with a 4×2 kernel and clamps at 0.
- Sky, only with the sun on: `max(0, cos(ray − sun))^(4/sunDistance)` in sun colour (0.95, 0.9, 0.8) and sky colour (0.2, 0.24, 0.35), scaled by 3 and mixed 0.7/0.3.
- Luminance and colour split, the default ("Luminance + 0.5x Scale Color"): HRC runs at full resolution on Rec. 709 luminance and separately on colour averaged over `k × k` blocks with `k` = 2 (or 4). A block's averaged radiance `j` and transmittance `t` become `J = j·Σ_{i<k} t^i` and `T = t^k`, so a coarse texel stands for `k` fine steps. The result is `y·c/luma(c)`, with `y` the full-resolution luminance and `c` the bilinearly upsampled colour, `y` alone where `luma(c) ≤ 10^−8`, and a clamp at 64512. Colour HRC then costs `1/k²` of the probes, while shadow edges keep full resolution in luminance and colour bleeds at `k`-pixel resolution (inference).
- Storage: radiance R11G11B10F and transmittance R16F; packed luminance RGBA16F by default or RGBA8, which the UI says halves the packed storage but can lose faint light.

### Discrete Radon transform (Press 2006)

Press, "Discrete Radon transform has an exact, fast inverse and generalizes to operations other than sums along lines", PNAS 103(51):19249-19254, read from the free PMC copy (PMC1697830); equations are images there, so the statements follow the prose.

- Digital lines `D_N(h, s)` on an `N × N` image (`N` a power of 2) join row `h` of column 0 to row `h + s` of column `N − 1`, covering slopes from 0° to 45°. They are defined recursively from d-lines of half-width images and deviate from the continuous line by at most `(1/6)·log₂N` vertically.
- The transform (Götz and Druckmüller 1996, Brady 1998) sums pixels along every d-line in `log₂N` sweeps, each merging adjacent half-width partial sums into full-width ones with additions only: `(N² − N/2)·log₂N + N(N − 1)` additions in all. Flipping the image gives the other three quadrants; the full transform has `6N² − 2N` values, so it is over-complete and its inverse is a pseudo-inverse. Backprojection runs the same sweeps in reverse.
- The exact inverse is iterative: a recursive approximate inverse (half-size inverse, prolongation, forward transform of the estimate, backprojection of the residual, a local high-pass filter) inside a residual correction that uses the exact forward operator. Convergence is shown numerically, not proved, with empirical work `O(N²·(log N)³·log ε)` for accuracy `ε`, fitted for `N` from 16 to 1024 and converging up to 2048. A Fourier inverse is discussed in the supplement and cannot be iterated.
- Any associative and commutative operation can replace addition; a median transform detects a 4 px line 0.5 σ above Gaussian noise among heavy point clutter.
- Its sweep is HRC's merge without occlusion: d-lines of width `2n` are built from two d-lines of width `n`, as HRC builds level `c` rays from level `c − 1` segments, and the d-lines' bounded deviation is the extension's bend (inference). Replacing the sum with HRC's merge, which is associative but not commutative, keeps the sweep valid as long as every combination keeps the nearer segment first (inference).

## Links

- Reference HRC (Rust): https://github.com/entropylost/amitabha
- Volumetric HRC, including a ray-traced variant, with a write-up: https://github.com/Yaazarai/Volumetric-HRC
- HRC Unity URP 2D port: https://github.com/Youssef-Afella/UnityURP-HolographicRadianceCascades2DGI
- Browser HRC demo and its source: https://folkjs.org/demos/shaders/holographic-rc.html and https://github.com/folk-js/folkjs/blob/main/packages/labs/src/folk-holographic-rc.ts
- HRC demo with luminance and color split: https://jason.today/hrc ([code notes](#jasontodayhrc))
- HRC and basis visualizers: https://entropylost.github.io/hrcviz/ and https://entropylost.github.io/hrcviz/basis.html
- Line-space demos: https://adrianmargel.ca/demo/linespace/ and https://adrianmargel.ca/demo/linespace-rotation/ ([code notes](#adrian-margel-line-space-and-a-hierarchical-diffusion-solver))
- Skewed instead of rotated probe lines: https://deadlyredcube.com/RCStuff/orientedProbeLines.html ([code notes](#deadlyredcube-extensions-and-oriented-probe-lines))
- HRC Shadertoy proof of concept: https://www.shadertoy.com/view/4ctczl (two families of probe lines with directions doubling per level and no extension step; [code notes](2023_rc_shadertoys.md#4ctczl-suslik-two-families-of-probe-lines))
- Discrete Radon transform: https://www.pnas.org/doi/10.1073/pnas.0609228103 ([notes](#discrete-radon-transform-press-2006))
- Line-sweep ambient occlusion on height maps: http://wili.cc/research/lsao/lsao.pdf (Timonen 2013, screen-space depth buffer; [notes](2013_timonen_line_sweep_ambient_obscurance.md))
- Thesis comparing RC methods with voxel cone tracing: https://www.diva-portal.org/smash/get/diva2:1967544/FULLTEXT01.pdf
