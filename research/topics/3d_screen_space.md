# Screen-space 3D radiance cascades

Screen-space RC puts the probes on the depth buffer: a 2D grid of probes in screen space, each at the world position of its pixel, with full 3D directions. This is the "surface" row of the [memory model](core_theory.md#memory-by-domain). With directions ×4 and probe spacing ×2 per cascade, every cascade holds about the same number of texels, so memory and cost grow linearly with the cascade count. Path of Exile 2 shipped this way.

The material is split over three files. This one covers the two families, Path of Exile 2, the design choices every screen-probe code makes, temporal behaviour and the single-frame view. [Screen-space theses](3d_screen_space_theses.md) holds the six theses and papers with their measurements; [screen-space implementations](3d_screen_space_implementations.md) holds the repositories, Shadertoys, engine plugins and upscaling shaders. World-space designs are in [3D world space](3d_world_space.md) and surface-bound ones in [3D surface probes](3d_surface_probes.md).

## Contents

- [Two families](#two-families)
- [Path of Exile 2](#path-of-exile-2)
- [Screen probes with world intervals](#screen-probes-with-world-intervals)
- [Parameters across projects](#parameters-across-projects)
- [Interval units and view depth](#interval-units-and-view-depth)
- [Probe placement](#probe-placement)
  - [Min/max probes](#minmax-probes)
  - [Filling gaps and keeping anchors](#filling-gaps-and-keeping-anchors)
- [Directions in 3D](#directions-in-3d)
- [Tracing](#tracing)
  - [Depth-buffer marching](#depth-buffer-marching)
  - [World rays](#world-rays)
  - [What a hit returns](#what-a-hit-returns)
- [Merging across depth edges](#merging-across-depth-edges)
- [Depth-aware upscaling](#depth-aware-upscaling)
- [Final gather](#final-gather)
- [Temporal stability](#temporal-stability)
- [Hybrids](#hybrids)
- [Other findings](#other-findings)
- [Measurements](#measurements)
  - [Ray throughput across the measured SPWI codes (derived)](#ray-throughput-across-the-measured-spwi-codes-derived)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)

## Two families

The two families differ only in the ray march function; storage, merging and upscaling are the same ([screen-space RC](../sources/2026_screen_space_rc.md#ssrc-or-spwi)).

| | Screen-space tracing (SSRC) | Screen probes, world intervals (SPWI) |
|---|---|---|
| Rays | march the depth buffer | traced in a world structure: hardware RT, a BVH, an SDF or voxels |
| Cost | one screen line serves many world rays at once, an order of magnitude more rays for free; runs on weak hardware | needs a BVH or similar, but not hardware RT |
| Sees | only what is on screen and in front | off-screen emitters and off-screen directly lit objects, which gives the first indirect bounce, called about 90% of the GI look |
| Misses | off-screen and hidden geometry and lights | a second bounce from off screen, since irradiance exists only on visible surfaces; needs a cache or fallback |
| Shipped or built | Path of Exile 2; Abou Dan and Jensen; Kung; Alpha-Renderer; the Unreal and Unity plugins | Sannikov's demo; Coppen's 2024 build; Gavras; Dell'Ova; Kaméus; three-rc; RC-SPWI; KingTheFifth |

- The paper locates the screen-space artifacts (no off-screen lights, no hidden occluders, nothing behind the depth buffer) in tracing screen-space data, not in storing cascades in screen space ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#limitations-stated-by-the-author)).
- In both families radiance exists only on the depth-buffer surface. World-space cascades can be sampled anywhere, which participating media and atmospheric scattering need; screen-space cascades only on the G-buffer surface ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#early-implementations), [discussions](../sources/2026_rc_discussions.md)).
- Light through transparent objects needs extra work in both; one implementer says screen-space RC cannot pass light through transparent objects without hacks, and calls RC an approximation limited to one bounce unless bounces are added ([discussions](../sources/2026_rc_discussions.md#implementer-notes), vpinball #1843).
- One view: with hardware RT and quality as the goal, sparse world-space RC is preferable to either, because screen probes move with the camera and flicker while world-stable probes do not; sparse RC also needs no screen-space upscaling and looks fine at any resolution ([screen-space RC](../sources/2026_screen_space_rc.md#ssrc-or-spwi)). Pornel called SPWI the practical 3D form, full 3D RC being too expensive beyond voxel scenes ([history](history_and_landscape.md)).
- The paper's interval extension (doubling an interval by reading the cascade at a shifted position) needs a regular grid and does not work for screen probes, which each sit at their own depth ([core theory](core_theory.md)).

Gavras's comparison table puts SPWI between screen-space marching (extremely fast, memory efficient, no off-screen light) and a 3D probe grid (off-screen light, view independent, stable under camera motion, high memory, very slow), with off-screen light and a memory-efficient probe hierarchy but "very slow" against screen-space marching ([Gavras](3d_screen_space_theses.md#gavras-2025-spwi-on-metal)).

## Path of Exile 2

Path of Exile 2 is the shipped screen-space design. Its history, the ExileCon 2023 talk and the cost figures from every source (about 3 ms on a GTX 1050, about 1 ms constant, 0.8 ms at 4K on an RTX 4090) are in [history](history_and_landscape.md#exilecon-2023-and-path-of-exile-2). The design, as far as the sources describe it:

- Probes and data are screen-space, a "flatland-like hierarchy filled by screen-space raymarching". Each thread marches 4 rays at once and stores occlusion as a 128-bit bitmask per cascade texel, the equivalent of 128 binary occlusion rays; this works well with normal maps and can feed specular ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#early-implementations)).
- SH probes every 2 px, one 4-coefficient SH per 2×2 block. Cascade 0 probes sit about every 15 to 16 px on the lowest settings, with 4 directions. Cascade −1 marches from each SH probe to the cascade 0 interval start, so the SH probes must be denser than cascade 0; reading cascade 0 once per SH probe is 4× less work than once per pixel ([screen-space RC](../sources/2026_screen_space_rc.md#path-of-exile-2-details)).
- Production upscales by 16×16 and uses min/max probes between cascades and when upscaling cascade 0 into the half-resolution SH. Tiles without a depth discontinuity, most of them, read the central depth texel and need no min/max pair.
- Only on-screen effects cast indirect light. Point and spot lights are analytic with shadow maps, and RC adds the second bounce.
- Budgets stated in implementer threads: 1.5 ms on a GTX 1650 in one statement and about 3 ms on a GTX 1060 in another, single shot, no temporal reuse.
- A Hacker News commenter (Negitivefrags, 2024-10) says the input is screen-space but a 3D structure is built by marching the depth buffer, that data behind the camera is not needed because lights rarely sit there, and that particles light nearby surfaces through the GI with no extra authoring; the usual objection is that a light behind a column or in another room casts nothing, and the thread's suggested fixes are rendering a larger view and cropping, or giving each cascade only the range its interval needs ([discussions](../sources/2026_rc_discussions.md#path-of-exile-2-claims)).
- No temporal accumulation and no TAA, because the game changes too fast. Screen space is enough because the camera is a fixed top-down view with no relevant lights behind it. The diffuse result and specular cone queries come from the same cascades ([ExileCon 2023](../sources/2023_sannikov_exilecon_rendering_poe2.md)).

At 1080p the lowest setting's cascade 0 has about 120 × 68 probes and 32,400 direction texels, while the SH layer has 518,400 probes (derived): almost all per-pixel resolution comes from the SH layer and cascade −1, and the cascades themselves are coarse.

**The prototype.** Sannikov's "Single shot global illumination with no denoiser" (2023) is the first mostly working "cascaded image-space GI": it converges to a noise-free result in about 5 ms using only the current frame, with no reprojection, and has the usual screen-space drawbacks. Low spatial resolution cascades with high angular resolution capture far-field GI and high spatial resolution ones near-field GI. Work is spread evenly: level 6 is downscaled 64×64 times yet holds as much GI work at its frequency as level 0 ([videos](../sources/2022_sannikov_youtube_rc_videos.md#single-shot-global-illumination-with-no-denoiser-2023)).

## Screen probes with world intervals

**Sannikov's demo.** The paper's world-interval variant places octahedral probes of `2^i × 2^i` texels every `2^i` pixels on the depth buffer. Spatial interpolation is bilateral (only neighbours with similar depth count) and directional interpolation bilinear. Any ray-segment query fills the intervals; the demo used analytic SDFs. Each cascade reprojects from the last frame for temporal accumulation and converges in 0.1 to 0.5 s. It sees off-screen and depth-occluded light but runs one to two orders of magnitude slower than PoE2's approach, 30 to 50 ms on an RTX 3060 ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#early-implementations)).

**The name.** Max Coppen showed a first 3D RC on 12 August 2024 (https://x.com/mxacop/status/1822851233708732579), voxel cubes with one emissive cube, and named the design SPWI, "screen probes, world intervals" ([discussions](../sources/2026_rc_discussions.md#coppens-first-3d-rc-on-x-2024-08)):

- Probes sit on the depth buffer and are stored in 2D textures, but their intervals are traced in world space, so off-screen light is caught without the memory of a 3D grid. Coppen knew of two or three other screen-space 3D implementations besides Sannikov's and Coppen's own.
- Each cascade casts one ray per pixel, and five cascades gave the equivalent of 5 samples per pixel. Coppen expected to get under 2, with more than half of the rays very short, and to improve data locality.
- Leaks were rare because probe rays connect well across cascades. A bilateral depth filter avoided edge artifacts, to be replaced by min/max depth interpolation.
- It ran in real time but unoptimized, with a high base cost, single-bounce diffuse only and no tone mapping. Coppen had no 3D version of the 2D analytic sky integral.

**GPC 2024.** A student showcase (likely Max Coppen) explained 2D RC and gave a first look at 3D SPWI in Vulkan compute, the same split as Gavras's thesis. It compares branching: probe spacing ×2 with rays ×2 per cascade makes memory approach twice cascade 0, while rays ×4 keeps every cascade the same size. The 2D demo adds noise to the cascade interpolation for a painted look. It gives no numbers ([talks](../sources/2026_rc_conference_talks.md#gpc-2024-student-showcase)).

## Parameters across projects

| Project | Tracing | Cascade 0 spacing | Cascade 0 directions | Per cascade | Intervals | Cascades |
|---|---|---|---|---|---|---|
| Path of Exile 2 | depth march, 128-bit masks | about 15 to 16 px (lowest), SH every 2 px | 4 | not given | not given | not given |
| Sannikov's SPWI demo | analytic SDF | `2^i` px at cascade `i` | `2^i × 2^i` octahedral | dirs ×4, spacing ×2 | world | not given |
| Coppen 2024 | world rays | not given | not given | one ray per pixel per cascade | world | 5 |
| [Gavras](3d_screen_space_theses.md#gavras-2025-spwi-on-metal) | Metal ray tracing on an M1 | 4 px | 16 octahedral | dirs ×4, spacing ×2 | world, ends `0.016·4^L` | 6 |
| [Dell'Ova and ClaikoCode](3d_screen_space_theses.md#dellova-2025-performance-scaling-with-dxr) | DXR | 1 to 4 px (2 default) | 16, 36, 64 equal-area octahedral, pre-averaged | dirs ×4, spacing ×2 | world, start `5·(4^c − 1)/3`, length `5·4^c` | 5 to 8 |
| [Kaméus](3d_screen_space_theses.md#kaméus-2025-minmax-probe-placement) | DXR ray queries | 1, 2, 4 px | 4 stored, each 4 pre-averaged rays | dirs ×4, spacing ×2 | world, `[4^i, 4^(i+1)]·scale`, top to infinity | 5 in one capture |
| [Kung](3d_screen_space_theses.md#kung-2025-rc-against-voxel-cone-tracing) | depth march, fixed thickness | 1, 2, 4 px | 4 azimuth × 4 polar | dirs ×4, spacing ×2 | march steps `20·1.2^i` | 6 |
| [three-rc](3d_screen_space_implementations.md#three-rc) | BVH in GLSL | 4 px | 16 octahedral | dirs ×4, spacing ×2 | world, start `0.005·4^L` (0 at level 0), length `0.005·4^(L+1)`, so levels overlap | `ceil(ln max(W, H))` by a bug |
| [scy3Dd](3d_screen_space_implementations.md#scy3dd-spwi-in-one-shader) | analytic | 4 px | 16 equal-area octahedral | dirs ×4, spacing ×2 | world, `[s(N), s(N+1)]·0.006`, `s(0) = 1`, `s(N) = 4^N + 1` | 6 over 2 frames |
| [lXByRh](3d_screen_space_implementations.md#lxbyrh-hit-point-reprojection) | analytic, half resolution | 4 px | 4 hemisphere | dirs ×4, spacing ×2 | none: every ray to its first hit | 6 |
| [RC-SPWI](3d_screen_space_implementations.md#qiriasrc-spwi) | hardware RT (Metal) | 4 px | 16 octahedral | dirs ×4, spacing ×2 | world, `0.24·4^(L−1)` to `0.24·4^L` | 6 |
| [Alpha-Renderer](3d_screen_space_implementations.md#alexander-koutrakisalpha-renderer) | min/max depth pyramid march | 2 px | 2×2 hemisphere | dirs ×4, spacing ×2 | world, ends `0.08·4^(c+1)`, +15% overlap | 6 |
| [KingTheFifth](3d_screen_space_implementations.md#kingthefifthradiance-cascades) | 256³ voxel grid (or depth march, Hi-Z) | 4 px | 4 × 4 latitude-longitude | dirs ×4, spacing ×2 | world, `[4·(2^c − 1), 4·(2^(c+1) − 1))`, doubling | 6 |
| [Unreal bitmask RC](3d_screen_space_implementations.md#unreal-screen-space-bitmask-rc) | screen slices, 32-sector mask | 2 or 4 px | 4 or 16 | dirs ×R, spacing ×√R | pixels, start `2T·(R^c − 1)/(R − 1)`, length `2T·R^c` | `clamp(ceil(log(diag)/log R) + 1, 1, 32)` |
| [Unity direction-first](3d_screen_space_implementations.md#unity-direction-first-screen-probes) | 16 virtual rays against variance depth | 8 px, min and max probe | 4 azimuth × 4 polar | azimuth ×2, spacing ×2 | doubling, `(0, 1), (1, 2), …, (16, 32)·RayScale` | 6 |
| [BeansEngine software](3d_screen_space_implementations.md#beansengine) | inline ray queries | 1 px | `baseRayCount`, golden spiral | rays ×2, spacing ×1 | quadratic, `[s·L², s·(L + 1)²]` | not given |

Points that hold across them:

- **Directions.** Equal-area octahedral mapping removes the axis bias of plain octahedral, and cascade 0 needs at least 8 directions; the maps and their trade-offs are in [cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d) and the counts below.
- **Direction-first layout and pre-averaging** are standard ([cascade layout](cascade_layout_and_merging.md#storage-layouts)). With pre-averaging every cascade texture has the same size, `pc0·√rc0/2` per axis (Dell'Ova), and the valid base direction counts for a square pre-averaged layout are `4k²`: 4, 16, 36, 64. Dell'Ova excludes 4 in 3D because four symmetric sphere directions lie in one plane.
- **Equal cost for equal rays.** Configurations with the same `rc0/spacing²` cost about the same (16 rays at 1 px and 64 rays at 2 px both took about 24.7 ms in Dell'Ova's tests), so spatial and angular density trade freely at fixed cost.
- **Probes are not placed in 3D.** Every code reads one depth per tile (or a min and a max) and reconstructs a world position; none subdivides tiles where geometry is detailed, which non-RC screen-probe systems do (below).

## Interval units and view depth

World-unit intervals must be tuned to the scene's scale (Gavras, Dell'Ova). Screen probes are a fixed number of pixels apart, so their world spacing grows with view depth while a world-unit interval does not. Far from the camera the cascade 0 spacing outgrows `t0` and breaks the penumbra condition `Δp ≲ t0` ([core theory](core_theory.md)). Intervals in pixels (Unreal) or scaled with view depth keep the ratio fixed; Split RC solves the same problem for world probes with distance LODs ([3D world space](3d_world_space.md#placement-and-levels-of-detail)). What stays depth-dependent with pixel intervals is the Unreal plugin's fixed wall thickness of 300 view units: a screen ray moves `z·θp·tan β` in depth per pixel (`θp` the pixel's angular size, `β` the ray's angle into the screen), so beyond `z = 300/(θp·tan β·s)` for steps of `s` pixels it can pass through a slab between two samples and leak, while nearer than that a 300-unit slab behind thin objects over-occludes (derived).

A probe `s` pixels apart at view depth `d` covers `s·2d·tan(fov/2)/H` world units. At 1080p with a 60° vertical field of view this is `0.00428·d` for 4 px probes and `0.00214·d` for 2 px, so cascade 0's spacing reaches its interval length `t0` at a depth of `234·t0` for 4 px probes, `468·t0` for 2 px and `935·t0` for 1 px (derived). For the codes whose scene units are known:

| Code | Spacing | `t0` | Depth where spacing reaches `t0` | Scene |
|---|---|---|---|---|
| three-rc | 4 px | 0.02 | 4.7 (2.5 at its fiddle's 95° field of view) | glTF Sponza, metres, about 30 m long |
| scy3Dd | 4 px | 0.024 | 5.6 | unit cube over a floor |
| ClaikoCode | 2 px | 5 | 2338 | Sponza scaled ×100, bounding radius 2590 |
| Alpha-Renderer | 2 px | 0.32 | 150 | not given |
| KingTheFifth | 4 px | 4 | 935 | 30 × 15 × 16 box |

So three-rc violates the condition at cascade 0 over most of Sponza, while ClaikoCode's ray length 5 keeps it almost to the scene's edge (derived). Gavras's 0.016 and Kaméus's `scale` have no stated units and are left out.

The Unreal plugin's intervals are in pixels, so `t0` is twice the probe spacing at every depth. Its interval start over spacing then grows ×4 per cascade with `R = 16` (2, 8, 32, 128) and ×2 with `R = 4` (2, 4, 8, 16), and at 1080p its cascade count formula gives 4 cascades for `R = 16, T = 4` and 7 for `R = 4, T = 2` (derived). With directions ×4 and intervals ×4 per cascade, as in the world-unit codes, the margin also doubles per cascade, so cascade 0 is always the binding one (derived).

## Probe placement

- Each probe reads the depth at its tile centre and reconstructs the world position. Gavras and three-rc then pull it to 98% of its depth toward the camera to stop self-hits; Kung and Alpha-Renderer push it along the normal (`max(0.01, 0.0015·linear depth)` in Alpha-Renderer); Kaméus pushes probes off the surface by a depth bias, where too much leaks and too little self-intersects.
- Rays that start under the surface, or probes on a thin edge, return black and darken the result ([artifacts](artifacts_and_fixes.md#rays-starting-inside-geometry)).
- Full-sphere directions waste the half that points into the surface. About half of cascade 0's intervals face into the surface and can be skipped when nothing is transmissive; higher cascades are not on the surface, so skipping there can open holes ([screen-space RC](../sources/2026_screen_space_rc.md#directions-in-3d)). Dell'Ova notes those rays carry nothing after the merge's occlusion test. Full-sphere bins do let parents and children share directions whatever their normals; a hemisphere around each probe's normal (Alpha-Renderer, lXByRh) halves storage at the cost of matching bins between probes with different normals.

### Min/max probes

A probe at the tile centre can land on the background while most of the tile is foreground. Min/max probes place two probes per tile, at its minimum and maximum depth ([screen-space RC](../sources/2026_screen_space_rc.md#minmax-probes)):

- **Placement.** A cascade `N` probe should lie within the `[min, max]` range of its cascade `N + 1` tile. Merge with bilinear weights on the min plane and on the max plane, then lerp between them by `clamp((z − zmin)/(zmax − zmin), 0, 1)`. Stored in a `W × H × 2` texture, one hardware trilinear tap does the whole depth-aware lookup.
- **Cost and gain.** About 2× the tracing (two rays per interval) for about 10× the quality; its artifacts are an order of magnitude smaller than any one-probe-per-tile method. In SSRC both probes march together at the same screen position; in SPWI they share nothing. A sparse 3D variant clustered child positions with 2-means and split only where the gap was large, for 20 to 30% extra rays instead of 100%.
- **Building the pyramid.** A 2×2 box chain lets max creep into min under bilinear filtering, so widen by half a texel with an overlapping 4×4 box on top. Nearest min/max selection is easier to make exact. A 2×2 upscaling window was poor; 3×3 was stable and mostly artifact free. Reverse depth swaps min and max. One WebGPU build packed both into one R32_UINT.
- **Interval start** must lie outside the tile, at least its diagonal (`√32` px for 4×4), or a black band appears. Cascade 0 starting at 0 needs full resolution or cascade −1.
- **Failure cases.** Two overlapping fences; tiles where per-texel min/max cannot represent a sloped plane, which looks blocky and moves in motion; and GI computed inside objects when the max plane falls under the surface. Haloing comes from max-probe rays interpolated into min probes. Choosing min/max over a square 50% larger than the tile removed artifacts in one build.
- **Continuous min/max** ([s3B3WR](https://www.shadertoy.com/view/s3B3WR)) classifies each sample as foreground or background against the average depth and blurs each class separately. It is stable under camera motion and works at any downscale factor. Defining the ratio first and deriving depths from it was smoother than the reverse. The reference upscaler NfBSz1 is nearly exact for world positions ([implementations](3d_screen_space_implementations.md#nfbsz1-perspective-correct-minmax-interpolation)).
- **Two-surface construction** (the current state in one line of work): a full-resolution nonlinear bilateral filter with radius equal to the downscale factor finds discontinuities and computes min/max only there, then decimates. Flat planes get equal min and max; elsewhere probes sit on exact full-resolution depth pixels stored as two int16 indices, with discontinuities pushed slightly outward. A threshold of about 1% depth change per pixel caught thin banners in Sponza. It is costly on mobile, and that line of work has no mip-like construction for it.
- **Smooth envelopes** around depth, which the same discussions call an open problem: tried were Beurling–Selberg majorants, FFT band limits, an `[1, 2, 1]` blur and a slope-corrected envelope fitted with IRLS ([glossary](supporting_techniques.md)).
- Min and max are equal for about 99% of pixels, so a classification plus a neighbour reference could replace the second value; PoE2 skips the pair in tiles without a depth discontinuity.
- **Precision.** Fuller (2023) stores tile min and max linear depth in R16G16_UNORM as `(min/max, max)` and decodes `min = x·y`, so the min channel uses the full 16-bit range below max: its step becomes `max/65535`, four times finer at `max = 0.25`. In Fuller's deferred lighting it gave about 0.4% from fewer zero-attenuation pixels. Sky tiles are marked `(1, 0)` before encoding, and the post does not say how `max = 0` is handled after the division. Packing max and the delta into one R32_UINT (for example 17 and 15 bits) is suggested (https://martinfullerblog.wordpress.com/2023/01/13/min-max-buffer-precision-improvement/). For min/max probes the same ratio form keeps the depth range of near tiles precise (inference).

The variants found: the Unity plugin's direction-first mode stores min and max probe halves side by side and found them the most stable of its three modes; CorylusDonuts' design stores both intervals in one RGBA32UI texel; Gavras proposes them as future work with odd rays on the near probe and even rays on the far one; the Unreal plugin and three-rc list them as future work; RC-SPWI has an undispatched min/max pass. Kaméus measured them against one bilaterally merged probe per tile: 2 to 17% more time, twice the rays and memory, 0.5 to 5.8% lower LIP-LDR error, but no splotchy edge leaks and less flicker ([Kaméus](3d_screen_space_theses.md#kaméus-2025-minmax-probe-placement)). The "10× quality for 2× tracing" claim and Kaméus's metrics disagree by an order of magnitude; Kaméus's own reading is that the visible difference is larger than the metrics, which measure whole images where edge artifacts cover few pixels (inference).

### Filling gaps and keeping anchors

A uniform probe grid leaves pixels on fine geometry with no matching probe, and probes re-placed every frame jump. The non-RC screen-probe systems all add probes or keep them, and none of the RC codes does:

- Lumen subdivides the grid where geometry is detailed; Godot's screen-probe draft adds a probe at one of 8 jittered candidates per tile when the base probes cover it with weight under 0.01; Brixelizer GI tries up to 8 jittered positions per tile until one has valid depth; daGI2 runs up to `log2(tile size)` passes, each adding a probe at the tile pixel least covered by the planes of nearby probes ([related engine GI](related_engine_gi.md)).
- daGI2 leaves a probe at last frame's pixel when that pixel reprojects inside the tile with a matching depth, and moves it to the tile centre otherwise; re-placing probes every frame under TAA jitter stopped temporal reuse and made probes blink ([related engine GI](related_engine_gi.md)).

Adaptive probes are the screen-space counterpart of min/max probes: both put extra probes where one depth per tile fails, the first spatially and the second in depth (inference).

## Directions in 3D

- Use a fixed world orientation. The equal-area octahedral map, HEALPix and the sets that do not nest are compared in [cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d).
- **Cascade 0 count.** 8 directions (one per octant) is the minimum. 4 over the full sphere gave a large cosine-law error, 16 still visible error, and 4 azimuth × 8 polar cos-weighted rings over 10%. Polar angles must be uniform in `cos θ`; fixed unbranched altitudes gave a bright ring with a sharp cutoff ([screen-space RC](../sources/2026_screen_space_rc.md#directions-in-3d)). Kung's equal polar steps oversample the poles, and KingTheFifth's latitude-longitude split has the same bias.
- **SPWI interval scaling.** Directions double per axis per cascade, so intervals should grow 2×, not 4×, to keep world ray density constant. In a 5 m box a 0.2 m base with 2× growth was stable; 4× and 8× needed many more samples. Steps proportional to interval length allow a constant step count at 2×. KingTheFifth and the Unity plugin use doubling intervals; the others use ×4.
- **Upper cascades alias** with 2×2 angular scaling, because the gap between interval ends doubles each level. Too few rays per cone causes most artifacts: halving stored directions and casting 2 rays per cone was a free speed-up with about 2× less memory.

The 2× rule and the ×4 intervals that most codes use are the two criteria of [core theory](core_theory.md#two-criteria-for-interval-scaling-derived). With directions ×4 (×2 per axis) the ray-end gap `t·Δω` stays constant per cascade at `l = 2` and doubles at `l = 4`, while the probe spacing doubles either way. So `l = 2` resolves the same smallest light at every cascade, which is why the 5 m box stayed stable, but its error drifts from angular near the probe to spatial far away; `l = 4` balances the two errors at every cascade, the choice Split RC and the sparse 3D builds call correct, but the smallest resolvable light grows ×2 per cascade, which shows as the upper-cascade aliasing and the need for more rays per cone (derived). The two findings are therefore consistent, and each names the cost of the other's choice. Gavras, Dell'Ova, Kaméus, three-rc, scy3Dd, RC-SPWI and Alpha-Renderer use `l = 4`; KingTheFifth and the Unity plugin double their intervals; PoE2's `l = 2` comes from Split RC's reading.

## Tracing

### Depth-buffer marching

Fast, and the only option that needs no scene representation. A single depth layer has unknown thickness: Kung's fixed thickness leaked through thin objects, Alpha-Renderer marches a min/max pyramid coarse to fine, and the Unreal plugin treats each depth sample as a slab of fixed thickness, as in [visibility-bitmask SSGI](related_screen_space_gi.md). Thickness findings: infinite thickness over-brightens areas under emitters and near-zero thickness leaks; for visibility bitmasks 0.1 view-space units was too thin and infinite looked right; 8 cascade 0 directions instead of 4 reduced view-dependent bias ([screen-space RC](../sources/2026_screen_space_rc.md#other-findings)). Stachowiak's depth-buffer marcher, which tests each step against both the bilinear and the nearest-texel surface, is in [scene representation and tracing](scene_representation_and_tracing.md).

A forwarded claim, with no hardware given, lists the steps that made depth-buffer RC real time; each multiplies the previous gain, and missing one leaves it too slow ([screen-space RC](../sources/2026_screen_space_rc.md#the-optimization-stack)):

| Step | Time |
|---|---|
| Naive vanilla RC | about 1000 ms |
| fp16 storage | about 500 ms |
| Half resolution with depth-aware upscaling | 125 ms |
| Sector casting | about 20 ms |
| Occlusion bitmasks | 10 ms |

- **Sector casting** is called the most important screen-space optimization. All cones from one pixel that project onto the same screen line form a depth sector, and each depth sample along that line updates every cone in the sector at once. It is dozens of times faster than marching cones one by one. Visibility-bitmask AO is the same idea with one bit per cone.
- **Prefiltering** depth and colour mips gives about another 4×, and only screen space allows it. Min and max depths lose meaning under blur, so store depth moments `(z, z²)` and treat occlusion as a probability from mean and variance, as in summed-area variance shadow maps. A uniform distribution worked as well as a normal one and is simpler. Moments cost about the same as bitmasks and win because they can be prefiltered; horizon-based methods cannot. Upper cascades need heavy prefiltering to stay stable under camera motion. l3scz8 gives the closed-form occlusion of a depth interval by a uniform offset of known variance ([implementations](3d_screen_space_implementations.md#l3scz8-occlusion-from-depth-variance)), and the Unity plugin's "variance trapezoid integration" uses it.
- **Horizon starts.** Each cascade can start at the horizon of the first sample of its interval. Taking the max of horizons gives HBAO far faster than regular HBAO, and GTAO can be computed with RC; 33ycDm does so in one frame from three levels of cascaded horizons ([implementations](3d_screen_space_implementations.md#33ycdm-gtao-from-cascaded-horizons)).
- **Bitmasks and opacity.** One design stored 4 colour cones with 16 opacity sub-cones (4 per colour cone). Bitmasks cannot be interpolated when merging, so they were converted to opacity. Bitmasks can also be mixed bit by bit, choosing each bit with probability equal to the weight from a precomputed pattern.

Abou Dan and Jensen traced screen probes with visibility-bitmask GI for As We Descend and ran at 2 to 26 ms with no temporal reuse, but the screen-space tracing over-brightened the background and flickered under small camera moves ([theses](3d_screen_space_theses.md#abou-dan-and-jensen-2025-visibility-bitmask-screen-probes)).

The optimization stack and PoE2's 4 rays per thread with 128-bit masks are the same move: in screen space many directions share one screen line, so a march amortized across directions turns per-ray cost into per-sample cost. SPWI has no such sharing, which is the order of magnitude between the families (inference).

### World rays

- The ray from the probe position is traced in a world structure. Tracing dominates: the gather was 87 to 96% of all RC time in Dell'Ova's DXR measurements, Kaméus's Nsight capture showed the time going to waiting on ray queries, Gavras found SIMD pre-averaging gains negligible because ray tracing dominates, and Kung's naive depth march was the main cost there too.
- Godot's `RenderingDevice` has no ray queries in compute shaders ([docs/rendering_device.md](../../docs/rendering_device.md)), so world rays in Godot need a software structure; the options are in [scene representation and tracing](scene_representation_and_tracing.md).
- A binary BVH was reported 2× faster than an 8-wide compressed BVH for SPWI because RC rays are coherent; the tinybvh issue cited for it measures the primary-ray speedtest, not SPWI, and its maintainer puts the gap down to OpenCL traversal code rather than coherence alone ([scene representation and tracing](scene_representation_and_tracing.md)). Smaller BVH stacks saved a few ms on an M2.
- Quad shuffles (`quadSwapX/Y` in WGSL) averaging four ray threads gained about 10% on the ray pass ([screen-space RC](../sources/2026_screen_space_rc.md#measurements)); CorylusDonuts' design uses `subgroupClusteredAdd(…, 4)·0.25` and Gavras's SIMD shuffles the same way.
- **Self-intersection.** Offset the ray start by at least the base interval (about 0.05 m) rather than along the normal; a normal offset of 0.01 worked in another build, but RGBA8 octahedral normals were too coarse ([screen-space RC](../sources/2026_screen_space_rc.md#other-findings)).

### What a hit returns

The hit's radiance decides the bounce count. three-rc, Gavras, Dell'Ova, Kung and KingTheFifth return only emission, so lit non-emissive surfaces bounce nothing. Alpha-Renderer reads its direct-light buffer (light without albedo) and multiplies by the hit surface's albedo; lXByRh stores shadowed sun light times albedo. Reading the previous frame's lit colour or GI at the hit adds bounces over frames: feed last frame's reprojected lighting back as emission ([screen-space RC](../sources/2026_screen_space_rc.md#other-findings)).

## Merging across depth edges

Upper probes can sit on different surfaces than the lower probe, so plain bilinear interpolation leaks light and shadow across depth edges. The approaches, in order of quality:

- **Bilateral weights.** Gavras multiplies each bilinear weight by `1/(|d_i − d| + 0.0001)` only where the four depths differ by more than 10% of their mean (after pixelmager's gist); 4XXSWS uses `exp(−100·|d_i − d|)`; CorylusDonuts `exp(−16·|d_i − d|/d)`; 4cffDX adds a normal term. Bilateral merges show striations at steep angles (Gavras), and when all weights are near zero the normalization makes bright or dark splotches (Kaméus).
- **"Bilinear 3D"** (4XXSWS): reconstruct the four upper probes' world points and solve for the bilinear ratio at which they interpolate to the lower probe's point, alternating projections onto the two edge pairs for 2 to 4 iterations. Weights follow the surface instead of rejecting samples and need no normalization. three-rc, scy3Dd, RC-SPWI, the Unreal plugin and Gavras use it, and ClaikoCode has it switched off. Guard the projection against zero-length edges: three-rc divides by zero when two corners clamp to the same probe at the screen edge.
- **Selective subsets** (MXjcWK): try the 15 non-empty subsets of the four taps and keep the one whose weighted world point lands closest to the target.
- **Per-sector occlusion** (Unreal plugin): each interval stores a 32-sector mask of the screen slice it covers, and the upper value is scaled by the share of its covered sectors that the lower interval leaves open, `WeightedBitSum(UpMask & ~mask)/WeightedBitSum(UpMask)`. Light hidden in one part of a slice still passes in another.
- **Hit-point reprojection** (lXByRh): reproject each coarser ray's hit point into the finer probe and keep it if it falls in the right direction bin and is not hidden; the merge replaces radiance rather than compositing intervals.
- **Min/max probes**, above, address the problem at its source.

The shader details are in [implementations](3d_screen_space_implementations.md#depth-aware-upscaling-shaders).

## Depth-aware upscaling

The same reconstruction problem appears twice: when a cascade reads its parent and when pixels read cascade 0 ([screen-space RC](../sources/2026_screen_space_rc.md#depth-aware-upscaling)).

- Interpolate by depth, not in screen space. A good upscaler reconstructs any linear function on any plane exactly; test it on world position, low-resolution normals and AO against full resolution, with no halos around emitters. Interpolating `1/z` instead of `z` is exact on flat planes.
- The upscaler must use the same depth the probe was placed at, or light bleeds.
- Bilateral upsampling was called one of the worst methods. Its dark edges come from unnormalized weights, and all-zero weights treated as ones leak upper probes. Storing one depth plus a ratio halos because a ratio cannot be lerped; do not pack min and max into one channel if hardware interpolation is needed.
- Mip aliasing: use a negative mip bias equal to the upscaling ratio, as temporal upscalers do, and blur the depth and colour buffers rather than the probes. The FSR 2.3.4 manual sets `mipBias = log₂(renderResolution/displayResolution) − 1.0`: −1.58 for Quality (1.5×), −1.76 for Balanced (1.7×), −2.0 for Performance (2×) and −2.58 for Ultra Performance (3×), and says a negative bias gives better texture detail and should be reduced for high-frequency textures that alias temporally (https://gpuopen.com/manuals/fsr_sdk/techniques/super-resolution-temporal/#mipmap-biasing). The log term cancels the coarser default LOD of the lower render resolution, and the −1 sharpens by one more level for the temporal accumulation to resolve; a single-frame renderer has no accumulation to absorb that extra level (inference).
- 2× upscaling of a 2560×1440 cascade texture was about 10× faster, but probes swam because spatial density fell 4× while angular density did not ([screen-space RC](../sources/2026_screen_space_rc.md#measurements)).

**Choosing over weighting** (Pesce 2016, https://c0de517e.blogspot.com/2016/02/downsampled-effects-with-depth-aware.html, from quarter-resolution volumetric lighting in Call of Duty: Black Ops 3):

- Multiplying bilinear weights by depth weights can leave one tap that matches no surface, so the result should blend between bilinear and best-depth sampling with a sharp function of the depth discontinuity, as weights, as samples or as texture coordinates; Black Ops 3 switched sharply to depth-only weights at large discontinuities.
- Depth is downsampled with a checkerboard of min and max per low-resolution texel, so every 2×2 quad keeps at least two surfaces; second-smallest, second-largest and median variants traded spatial for depth resolution and worked less well.
- Separable bilateral blurs bleed along the second pass because it reads values mixed from other depths; rejecting by the centre depth or a staggered N×N grid helps. Artifacts remain where no good point sample exists in the 2×2 neighbourhood.
- The post leaves open depth clustering in compute, normals or other G-buffer data, wider filters, subtexel-aware weights and 1D interpolation along edges. In the comments the author adds that min and max work well when the function is monotonic in depth.
- The min/max checkerboard is the same choice as min/max probes that keep the extreme depths of a tile (inference).

pixelmager's gist, Gavras's bilateral source, is an earlier and softer variant: one rotated four-sample disc and inverse depth-difference weights only where the samples disagree ([implementations](3d_screen_space_implementations.md#pixelmagers-depth-aware-upscaling-gist)).

## Final gather

- Cascade 0 is reduced per probe to irradiance and then interpolated per pixel: a cosine-weighted average per probe (Gavras), a 6×6 octahedral irradiance tile or L1 spherical harmonics per probe (Split RC, Unity URP), PoE2's SH per 2×2 block, or every direction read per pixel (three-rc, scy3Dd). The 3D gathers are compared in [cascade layout](cascade_layout_and_merging.md#final-gather).
- **Normalization.** For `N` equal-solid-angle bins, irradiance is `E = Σ L(ω)·max(n·ω, 0)·4π/N`, and Lambertian outgoing light is `albedo·E/π`. Because `Σ max(n·ω, 0)·4π/N ≈ π`, a cosine-weighted average `Σ L·cos/Σ cos` is already `E/π` and only needs albedo (Gavras, scy3Dd, gomezzz). Under a uniform field `L` the codes return: three-rc 4/π too bright (16 terms with weight 1); ClaikoCode's active path `albedo·L/4`; KingTheFifth `(15/16)·albedo·L` after a diffuse intensity of 15; Alpha-Renderer a `GI_BOOST` of 3; Kung `albedo·E` with `E ≈ (1/N)·Σ L·(ω·n)`, which is a quarter of Lambert's term (derived from each code's formula).
- **Per-pixel weights.** Bilateral depth weights (Gavras, threshold 0.05), or the distance from each probe to the pixel's tangent plane, `saturate(1 − planeDistance/(0.03·depth))`, falling back to the nearest probe when all four fail (Unreal plugin).
- **Cascade −1.** Cascade 0's spacing blurs contact shadows and small detail; a per-pixel short trace over `[0, t0]` merged in front of interpolated cascade 0 fixes it ([cascade layout](cascade_layout_and_merging.md#cascade-1-and-contact-detail)). PoE2 runs it from its 2 px SH probes and scy3Dd per pixel over `[0, 0.006]`; three-rc and Kaméus name it as the next step.
- **Normals.** TAA jitter flips normals and makes RC flicker; a pixel's normal should affect only that pixel. Keep GI independent of normals: compute the directional distribution and convolve with the normal at the end, as with image-based lighting ([screen-space RC](../sources/2026_screen_space_rc.md#temporal-stability)).
- **Specular.** Sampling octahedral cascade 0 by the reflection vector shows bilinear artifacts, and 16-coefficient SH is too low frequency. A split-sum-like scheme stops merging at a cascade chosen by glossiness and then merges one to one along the reflected direction ([screen-space RC](../sources/2026_screen_space_rc.md#other-findings)). tmpvar's storage calculator offers to keep merged and unmerged cascades for this, doubling storage ([implementations](3d_screen_space_implementations.md#tmpvars-storage-calculator)).

## Temporal stability

Screen probes move with the camera and jump in depth between frames, so the GI flickers under motion. Gavras, Kung, Kaméus, Abou Dan and Jensen, the Unity plugin and Gerassimov's comparison (RC rated "medium" for temporal stability) all report it ([theses](3d_screen_space_theses.md)).

- Screen probes flicker over high depth complexity even with min/max; the probe stage, more than upscaling, is the main source. A cascade 0 pixel moving between cascade `N` texels changes min/max depth abruptly ([screen-space RC](../sources/2026_screen_space_rc.md#temporal-stability)).
- Random per-probe jitter boils and never converges. A structured pattern of offsets indexed by frame (for example repeating every 16 frames) is stable, "TAA in probe space", and works best with a good upscaler. Accumulating in probes was far more effective than accumulating per-pixel radiance. lXByRh pairs a 16-frame jitter period with a 16-frame accumulation window.
- Stronger exponential averaging on higher cascades removed wobble. A tiny sun in the sky dome adds wobble from cascade 4 up; inject it as a point source into its probe direction instead.
- Small lights flicker and streak when too few cascade 0 directions hit them; rotating directions per frame and accumulating helps (Kung).
- Fixes found in the codes: min/max probes; temporal accumulation with reprojection (Alpha-Renderer with the previous view-projection; Sannikov's SPWI demo; lXByRh); blending with the previous frame only where the surface is the same, clamped to the current neighbourhood's spread (EggyStudio's screen probes); world-space probes instead (Kung's suggestion).
- Non-RC screen-probe systems settle on the same recipe: Lumen jitters probe positions, rejects history by depth and normal with no neighbourhood clamp and speeds up accumulation where rays hit moving objects; Godot's draft blends each direction with `w = 1/(age + 1)`, age capped at 7, and 0.5 for dynamic receivers; daGI2 gives a new probe weights of 1, 1/2 and 1/3, then 0.025 per frame, and re-traces only a set fraction of probes each frame ([related engine GI](related_engine_gi.md)).

## Hybrids

Screen probes handle the near field well and world probes the far field, so several designs split the work:

- EggyStudio traces screen probes through the depth buffer out to twice the world probe spacing and takes world probes' light beyond it, 0.6 to 1.0 ms at 800×450 on a laptop GPU; genos-engine walks outward from near world-fixed probes to a screen cascade to a coarse world volume; creikey's screen probes trace a world voxel clipmap ([design documents](3d_world_space_implementations.md#rc-design-documents), [creikey](3d_world_space_implementations_grids.md#creikeyvoxel-radiance-cascades)).
- Godot's lead developer planned world-space GI for low-frequency light plus a screen-space layer for detail and occlusion; the 2026 draft that adds screen probes to HDDAGI does this, a Hi-Z trace up to 2 units, then the voxel cascades ([Godot integration](godot_integration.md#screen-probes-in-122999)).
- Lumen shortens the screen-probe ray and reads its world radiance cache when the ray misses, with a short contact AO in front; Brixelizer GI blends screen-probe SH with a world SH probe per brick; HSGI's phone path places one 4×4 hemisphere probe per 64×64-pixel tile and lets pixels on dynamic objects read the world probe volume directly; daGI2 cuts each screen-probe ray at 3 to 6 world-grid probe sizes and reads its world radiance clipmap there ([related engine GI](related_engine_gi.md)).
- KingTheFifth lifts screen probes by depth and traces their world intervals through voxels or Hi-Z; Split RC uses a screen-space cascade −1 below its world cascades.

Every hybrid puts the world representation where the screen fails, off screen and far, and keeps screen probes for the near field, where pixel density is highest ([3D world space implementations](3d_world_space_implementations.md#connections)).

## Other findings

- **Off-screen fallback:** a camera-centred cube map rendered every frame with world depth in alpha works but is costly; 64×64 per face was suggested for the near field ([screen-space RC](../sources/2026_screen_space_rc.md#other-findings)).
- **Non-power-of-two screens:** probe pixel `(idx + 0.5)·spacing`, counts rounded down and indices clamped at the edges. Under dynamic resolution, allocate for the swapchain and let probes spread. ClaikoCode floors its probe counts because rounding up places probes off screen; three-rc does not, and its merge reads past the texture at 1080p ([implementations](3d_screen_space_implementations.md#three-rc)); Kaméus's darker bottom and right edges come from upper probes that would sit off screen.
- **Learning order:** flatland, then screen-space shadows from one point light, then depth-aware upscaling alone, then the combination.
- **Debugging:** the routines (one cascade alone, an emissive cube on a floor, constant intervals as shells, radiance 1 on miss and 0 on hit times 0.5, large downscale factors for min/max bugs) are in [artifacts and fixes](artifacts_and_fixes.md#debugging-routine).

## Measurements

| Setup | Time | Source |
|---|---|---|
| SSRC AO: min and max cascade generation, then merging down to cascade 0 (hardware not given, forwarded) | about 2.7 ms and 8 ms | [screen-space RC](../sources/2026_screen_space_rc.md#measurements) |
| Min/max SSRC with accumulation (about 1 sample per cascade per frame, 1% blend) | 2.8 ms | same |
| Vulkan hardware-RT port at 2K with bilinear fix and cascade −1, no accumulation | about 14 ms, much faster than its software BVH | same |
| SPWI pass on an RTX 4070 | 0.89 ms | same |
| Ray-guided edge refinement: trace, then retrace high-variance cascade 0 directions | 5 ms + 1 ms | same |
| One sample per interval, probe-major, hardware bilinear at 2560² | cascade build from about 10 to 60 fps | same |
| Single-shot cascaded image-space GI (2023 prototype) | about 5 ms | [videos](../sources/2022_sannikov_youtube_rc_videos.md#single-shot-global-illumination-with-no-denoiser-2023) |
| Alpha-Renderer at 1080p, RTX 3070 (README claim) | about 5.5 ms, about 80 MB | [repositories](../sources/2026_screen_space_probe_repositories.md#alexander-koutrakisalpha-renderer) |

The thesis measurements are in [screen-space theses](3d_screen_space_theses.md); [performance](performance.md) normalizes all of them.

### Ray throughput across the measured SPWI codes (derived)

Rays per frame follow from each code's layout: one ray per stored texel, or four with pre-averaging.

| Code | Hardware | Rays per frame | Time | Rays per second |
|---|---|---|---|---|
| Dell'Ova, 1080p, 16 rays, spacing 1, 5 cascades | RTX 3080, DXR | 165.9 M | 23.65 ms of gather | 7.0 G |
| Dell'Ova, 1080p, 16 rays, spacing 4, 5 cascades | same | 10.4 M | 1.71 ms of gather | 6.1 G |
| Kaméus, one probe per pixel at 2048×1024 | RTX 2070, ray queries | 33.6 M per cascade | about 10 ms per cascade (Nsight) | about 3.4 G |
| Kung, House, SPS 1 | RTX 3060, depth march | 88.5 M | 70 ms | 1.26 G |
| Kung, Plains, SPS 1 | same | 88.5 M | 294 ms | 0.30 G |
| Gavras, cube and bunny scenes, 1080p | M1, Metal ray tracing | 12.4 M | 33 to 40 ms | 0.31 to 0.38 G |
| Gavras, Sponza, 1080p | same | 12.4 M | 144 to 156 ms | 0.08 to 0.09 G |

The M1 has no ray-tracing hardware (Apple added it with the M3 and A17 Pro), so Metal ray tracing runs as compute there, and Gavras's figures are a software-traversal data point, the class that applies to compute-only hosts such as Godot's `RenderingDevice` (inference from Apple's hardware). Kung's rows are depth-buffer marches with fixed steps, so their cost tracks scene size rather than geometry. The rows are not one benchmark: hardware, scenes and interval lengths all differ.

- Hardware RT on an RTX 3080 runs these short coherent rays at 6 to 8 G rays/s, so cost is set by ray count: Dell'Ova's `rc0/spacing²` rule follows (derived).
- Software traversal on the M1 lost 4.4× going from cubes to Sponza at the same ray count, while Dell'Ova's hardware ran Sponza at full speed: geometry complexity costs software tracers far more than hardware ones, consistent with owoDra's 3.5 to 4× software penalty on Split RC rays ([3D world space](3d_world_space.md#tracing-for-world-space-cascades)) (inference).
- At 1080p, 12.4 M rays per frame (Gavras's 6 cascades of one ray per pixel) is the floor for screen probes with 4 px spacing and 16 directions; at the M1's Sponza rate that is 140 ms, and at an RTX 3080's DXR rate under 2 ms (derived).

## Connections

- **The reconstruction problem is shared.** Merging a parent into a child, upscaling cascade 0 to pixels, reading a world probe at a pixel and reprojecting history are all depth-aware interpolation between points on different surfaces. Bilinear 3D, selective subsets, min/max probes and Pesce's choose-over-weight rule are four answers to one question, and the claim that a good upscaler reconstructs any linear function on any plane is the test for all of them (inference).
- **Min/max probes are Pesce's checkerboard and Kaméus's Min+Max under other names.** Keeping a tile's extreme depths appears in Black Ops 3's volumetrics (2016), CorylusDonuts' design (2024), Gavras's future work, PoE2's production upscale and Kaméus's measurement (2025).
- **Visibility-bitmask SSGI, horizon AO and SSRC are one family.** Sector casting, PoE2's 128-bit masks, the Unreal plugin's 32-sector masks, Abou Dan and Jensen's tracer and 33ycDm's cascaded horizons all treat the depth buffer as slabs swept along a screen line; RC adds the cascade hierarchy over distance ([related screen-space GI](related_screen_space_gi.md)) (inference).
- **Interval units are the screen-space form of Split RC's LOD problem.** World-unit intervals over pixel-spaced probes break the penumbra condition with depth, as fixed world intervals over depth-scaled surfels do in Coppen's surfel RC ([3D surface probes](3d_surface_probes.md#read-against-the-theory-derived)); pixel intervals or depth-scaled `t0` fix both (derived for surfels in [3D surface probes](3d_surface_probes.md#read-against-the-theory-derived)).
- **Tracing dominates everywhere.** Every SPWI measurement (Dell'Ova, Kaméus, Gavras) and Kung's depth march put 87% or more of the time in the gather, so pre-averaging, merge kernels and layouts are second-order for cost, and the tracer choice is the first-order one.

## Single-frame assessment

- **Screen-space RC is the one shipped single-frame RC.** PoE2 and Abou Dan and Jensen run without temporal reuse, as do Gavras, Dell'Ova, Kaméus, Kung, three-rc and scy3Dd. RC itself needs no history in screen space.
- **What breaks a single frame is the probe set.** Probes re-placed from the depth buffer each frame jump in depth under camera motion, and every report of flicker traces to that, not to noise. Every fix that works without history changes placement (min/max probes, continuous min/max, two-surface construction); every other fix (reprojection, jitter accumulation, exponential averaging on upper cascades) adds history.
- **Upper cascades need stability more than lower ones.** The forwarded findings say upper cascades need heavy prefiltering (SSRC) or stronger averaging (wobble) to stay stable, and a tiny sun aliases from cascade 4 up. In a single frame, prefiltered depth moments are the only fix found for SSRC; for SPWI none is known beyond more rays per cone (inference).
- **Cost at 1080p.** With hardware RT the per-frame cost is a few ms (Dell'Ova at 8 cascades: 2.4 ms at spacing 4 with 16 rays, 8.6 ms at spacing 2 with 16 rays or spacing 4 with 64); with software traversal it is one to two orders of magnitude more (Gavras on the M1); a depth march is cheap only with sector casting, bitmasks and prefiltering. Without hardware ray queries, as under Godot's `RenderingDevice`, SSRC stays affordable, while SPWI depends on a compute tracer reaching a few G rays/s on short coherent rays (derived from the table above).
- **Screen space limits what a single frame can know.** Off-screen and hidden light needs world rays (SPWI) or a world fallback; SPWI still gives only one bounce from off screen without a cache, and a cache is history.
