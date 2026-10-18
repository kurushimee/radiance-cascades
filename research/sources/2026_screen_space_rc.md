# Screen-space RC

| | |
|---|---|
| Date | 2024-08 to 2026-09 |
| Kind | Collected implementation findings; claims are unverified unless a public link backs them |
| Related | [2023_sannikov_exilecon_rendering_poe2.md](2023_sannikov_exilecon_rendering_poe2.md), [2025_kameus_spwi_probe_placement_thesis.md](2025_kameus_spwi_probe_placement_thesis.md), [2026_screen_space_probe_repositories.md](2026_screen_space_probe_repositories.md), [../topics/3d_screen_space.md](../topics/3d_screen_space.md) |

This note covers screen-space RC (SSRC, rays marched in the depth buffer) and screen probes with world intervals (SPWI, rays traced in a world structure). It adds the optimization stack that makes depth-buffer RC real time, how min/max probes are built and debugged, direction mappings and counts for 3D, how SSRC and SPWI compare, temporal stability fixes, and a few measurements.

## SSRC or SPWI

- The two differ only in the ray march function; storage, merging and upscaling are the same.
- SSRC marches a screen line, which serves many world rays at once, so it gets an order of magnitude more rays for free and runs on weak hardware. It cannot see off-screen or hidden geometry or lights.
- SPWI needs a BVH or similar but not hardware RT. It sees off-screen emitters and off-screen directly lit objects, which gives the first indirect bounce, called about 90% of the GI look. It computes irradiance only on visible surfaces, so a second bounce from off screen needs a cache or fallback.
- One view: with hardware RT and quality as the goal, sparse world-space RC is preferable to either, because screen probes move with the camera and flicker, while world-stable probes do not. Sparse RC also needs no screen-space upscaling and looks fine at any resolution.

## The optimization stack

A forwarded claim, with no hardware given, lists the steps that made depth-buffer RC real time. Each step multiplies the previous gain, and missing one leaves it too slow.

| Step | Time |
|---|---|
| Naive vanilla RC | about 1000 ms |
| fp16 storage | about 500 ms |
| Half resolution with depth-aware upscaling | 125 ms |
| Sector casting | about 20 ms |
| Occlusion bitmasks | 10 ms |

- **Sector casting** is called the most important screen-space optimization. All cones from one pixel that project onto the same screen line form a depth sector, and each depth sample along that line updates every cone in the sector at once. It is dozens of times faster than marching cones one by one. Visibility-bitmask AO is the same idea with one bit per cone.
- **Prefiltering** depth and color mips gives about another 4×, and only screen space allows it. Min and max depths lose meaning under blur, so store depth moments `(z, z²)` and treat occlusion as a probability from mean and variance, as in summed-area variance shadow maps. A uniform distribution worked as well as a normal one and is simpler. Moments cost about the same as bitmasks and win because they can be prefiltered; horizon-based methods cannot. Upper cascades need heavy prefiltering to stay stable under camera motion. An analytic cone-against-depth-patch test is in [l3scz8](https://www.shadertoy.com/view/l3scz8).
- **Horizon starts:** each cascade can start at the horizon of the first sample of its interval. Taking the max of horizons gives HBAO far faster than regular HBAO, and GTAO can be computed exactly with RC ([33ycDm](https://www.shadertoy.com/view/33ycDm)).
- One design stored 4 color cones with 16 opacity sub-cones (4 per color cone). Bitmasks cannot be interpolated when merging, so they were converted to opacity. Bitmasks can also be mixed bit by bit, choosing each bit with probability equal to the weight from a precomputed pattern.

## Path of Exile 2 details

- Budget: 1.5 ms on a GTX 1650 in one statement and about 3 ms on a GTX 1060 in another. Single shot, no temporal reuse.
- SH probes every 2 px (one 4-coefficient SH per 2×2 block); cascade 0 probes about every 15 to 16 px on the lowest settings, with 4 directions. Cascade −1 marches from each SH probe to the cascade 0 interval start, so SH probes must be denser than cascade 0, and reading cascade 0 once per SH probe is 4× less work.
- Production upscales by 16×16 and uses min/max between cascades and when upscaling cascade 0 into the half-resolution SH.
- Tiles without a depth discontinuity, most of them, read the central depth texel and need no min/max pair.
- Only on-screen effects cast indirect light. Point and spot lights are analytic with shadow maps, and RC adds the second bounce.

## Min/max probes

- **Placement:** two probes per tile, at the min and max depth. A cascade `N` probe should lie within the `[min, max]` range of its cascade `N+1` tile. Merge with bilinear weights on the min plane and on the max plane, then lerp between them by `clamp((z − zmin)/(zmax − zmin), 0, 1)`. Stored in a `W×H×2` texture, one hardware trilinear tap does the whole depth-aware lookup.
- **Cost and gain:** about 2× the tracing (two rays per interval) for about 10× the quality; its artifacts are an order of magnitude smaller than any one-probe-per-tile method. In SSRC both probes march together at the same screen position; in SPWI they share nothing. A sparse 3D variant clustered child positions with 2-means and split only where the gap was large, for 20 to 30% extra rays instead of 100%.
- **Building the pyramid:** a 2×2 box chain lets max creep into min under bilinear filtering, so widen by half a texel with an overlapping 4×4 box on top. Nearest min/max selection is easier to make exact. A 2×2 upscaling window was poor; 3×3 was stable and mostly artifact free. Reverse depth swaps min and max. One WebGPU build packed both into one R32_UINT.
- **Interval start** must lie outside the tile, at least its diagonal (`√32` px for 4×4), or a black band appears. Cascade 0 starting at 0 needs full resolution or cascade −1.
- **Failure cases:** two overlapping fences; tiles where per-texel min/max cannot represent a sloped plane, which looks blocky and moves in motion; and GI computed inside objects when the max plane falls under the surface. Haloing comes from max-probe rays interpolated into min probes. Choosing min/max over a square 50% larger than the tile removed artifacts in one build.
- **Continuous min/max** ([s3B3WR](https://www.shadertoy.com/view/s3B3WR)) classifies each sample as foreground or background against the average depth and blurs each class separately. It is stable under camera motion and works at any downscale factor. Defining the ratio first and deriving depths from it was smoother than the reverse. Reference upscaler: [NfBSz1](https://www.shadertoy.com/view/NfBSz1), nearly exact for world positions.
- **Two-surface construction** (current state): a full-resolution nonlinear bilateral filter with radius equal to the downscale factor finds discontinuities and computes min/max only there, then decimates. Flat planes get equal min and max; elsewhere probes sit on exact full-resolution depth pixels stored as two int16 indices, with discontinuities pushed slightly outward. A threshold of about 1% depth change per pixel caught thin banners in Sponza. It is costly on mobile, and a mip-like construction is still open.
- **Smooth envelopes** around depth are an open problem; tried: Beurling–Selberg majorants, FFT band limits, an `[1, 2, 1]` blur, and a slope-corrected envelope fitted with IRLS.
- Min and max are equal for about 99% of pixels, so a classification plus a neighbor reference could replace the second value.

## Depth-aware upscaling

- Interpolate by depth, not in screen space. A good upscaler reconstructs any linear function on any plane exactly; test it on world position, low-resolution normals and AO against full resolution, with no halos around emitters. Interpolating `1/z` instead of `z` is exact on flat planes.
- The upscaler must use the same depth the probe was placed at, or light bleeds.
- Bilateral upsampling was called one of the worst methods. Its dark edges come from unnormalized weights, and all-zero weights treated as ones leak upper probes. Storing one depth plus a ratio halos because a ratio cannot be lerped; do not pack min and max into one channel if hardware interpolation is needed.
- Mip aliasing: use a negative mip bias equal to the upscaling ratio, as temporal upscalers do, and blur the depth and color buffers rather than the probes.
- Depth-aware merging test scenes: [4cffDX](https://www.shadertoy.com/view/4cffDX), [4XXSWS](https://www.shadertoy.com/view/4XXSWS), and [MXjcWK](https://www.shadertoy.com/view/MXjcWK), which compares bilateral and selective upscaling.

## Directions in 3D

- Use a fixed world orientation. Classic octahedral mapping biases rays toward the axes and puts 8 of 16 directions on the equator; equal-area octahedral mapping fixes this for a trivial cost, and at 32² it comes close to a 768-direction HEALPix grid. HEALPix had lower error in analytic tests but is costly to build; Lebedev and spiral sets have no merge scheme ([visualizer](https://simulationcorner.net/clarberg/main.html), [pbrt equal-area mapping](https://pbr-book.org/4ed/Geometry_and_Transformations/Spherical_Geometry#x3-Equal-AreaMapping)).
- **Cascade 0 count:** 8 directions (one per octant) is the minimum. 4 over the full sphere gave large cosine-law error, 16 still visible error, and 4 azimuth × 8 polar cos-weighted rings over 10%. Polar angles must be uniform in `cos θ`; fixed unbranched altitudes gave a bright ring with a sharp cutoff.
- **SPWI interval scaling:** directions double per axis per cascade, so intervals should grow 2×, not 4×, to keep world ray density constant. In a 5 m box, a 0.2 m base with 2× growth was stable; 4× and 8× needed many more samples. Steps proportional to interval length allow a constant step count at 2×.
- Upper cascades alias with 2×2 angular scaling, because the gap between interval ends doubles each level. Too few rays per cone causes most artifacts: halving stored directions and casting 2 rays per cone was a free speedup with about 2× less memory.
- About half of cascade 0's intervals face into the surface and can be skipped when nothing is transmissive. Higher cascades are not on the surface, so holes are possible.

## Temporal stability

- Screen probes flicker over high depth complexity even with min/max; the probe stage, more than upscaling, is the main source. A cascade 0 pixel moving between cascade `N` texels changes min/max depth abruptly.
- Random per-probe jitter boils and never converges. A structured pattern of offsets indexed by frame (for example repeating every 16 frames) is stable, "TAA in probe space", and works best with a good upscaler. Accumulating in probes was far more effective than accumulating per-pixel radiance.
- Stronger exponential averaging on higher cascades removed wobble. A tiny sun in the sky dome adds wobble from cascade 4 up; inject it as a point source into its probe direction instead.
- TAA jitter flips normals and makes RC flicker; a pixel's normal should affect only that pixel. Keep GI independent of normals: compute the directional distribution and convolve with the normal at the end, as with image-based lighting.

## Other findings

- **Thickness:** infinite thickness over-brightens areas under emitters; near-zero leaks. 8 cascade 0 directions instead of 4 reduced view-dependent bias. For visibility bitmasks, 0.1 view-space units was too thin and infinite looked right.
- **Self-intersection:** offset the ray start by at least the base interval (about 0.05 m) rather than along the normal; a normal offset of 0.01 worked in another build, but RGBA8 octahedral normals were too coarse.
- **Specular:** sampling octahedral cascade 0 by the reflection vector shows bilinear artifacts, and 16-coefficient SH is too low frequency. A split-sum-like scheme stops merging at a cascade chosen by glossiness and then merges one to one along the reflected direction.
- **Off-screen fallback:** a camera-centered cubemap rendered every frame with world depth in alpha works but is costly; 64×64 per face was suggested for the near field.
- **Non-power-of-two screens:** probe pixel `(idx + 0.5)·spacing`, counts rounded down and clamped indices at the edges. Under dynamic resolution, allocate for the swapchain and let probes spread.
- **Multi-bounce** in screen space: feed last frame's reprojected lighting back as emission.
- **Learning order:** flatland, then screen-space shadows from one point light, then depth-aware upscaling alone, then the combination.
- **Debugging:** render cascade 1 alone without merging; use one emissive cube on a floor; use constant interval lengths to see cascades as shells around a light; return radiance 1 on miss and 0 on hit, times 0.5, so flat surfaces integrate to 1.0; small downscale factors (2×, 4×) hide min/max bugs, which show at 64× and above.

## Measurements

| Setup | Time |
|---|---|
| SSRC AO: min and max cascade generation, then merging down to cascade 0 (hardware not given) | about 2.7 ms and 8 ms |
| Min/max SSRC with accumulation (about 1 sample per cascade per frame, 1% blend) | 2.8 ms |
| Vulkan hardware-RT port at 2K with bilinear fix and cascade −1, no accumulation | about 14 ms, much faster than its software BVH |
| SPWI pass on an RTX 4070 | 0.89 ms |
| Ray-guided edge refinement: trace, then retrace high-variance cascade 0 directions | 5 ms + 1 ms |
| One sample per interval, probe-major, hardware bilinear at 2560² | cascade build from about 10 to 60 fps |

- A binary BVH beat an 8-wide compressed BVH by 2× for SPWI, because RC rays are coherent ([tinybvh issue](https://github.com/jbikker/tinybvh/issues/238)). Smaller BVH stacks saved a few ms on an M2.
- Quad shuffles (`quadSwapX/Y` in WGSL) averaging four ray threads gained about 10% on the ray pass.
- 2× upscaling of a 2560×1440 cascade texture was about 10× faster, but probes swam because spatial density fell 4× while angular density did not.

## Links

- SSRC for Unity URP: https://github.com/alexmalyutindev/unity-urp-radiance-cascades
- SPWI with hardware RT: https://github.com/Qirias/RC-SPWI
- SPWI in WebGL: https://github.com/CodyJasonBennett/three-rc
- SPWI on Shadertoy, amortized over 2 frames: https://shadertoy.com/view/scy3Dd
- Surfel RC: https://github.com/mxcop/src-dgi
- Depth-buffer ray march for contact shadows, SSGI and SSR: https://gist.github.com/h3r2tic/9c8356bdaefbe80b1a22ae0aaee192db
- Visibility bitmask paper and code: https://arxiv.org/pdf/2301.11376 and https://cdrinmatane.github.io/posts/ssaovb-code
- Min/max buffer precision: https://martinfullerblog.wordpress.com/2023/01/13/min-max-buffer-precision-improvement/
- Equal-area warp: https://gist.github.com/tonsa1/0db419349ad1a1ca332d2823fc9f6ceb
- Depth-aware upsampling: https://c0de517e.blogspot.com/2016/02/downsampled-effects-with-depth-aware.html
- Mip bias under upscaling: https://gpuopen.com/manuals/fsr_sdk/techniques/super-resolution-temporal/#mipmap-biasing
- SPWI clip with min/max probes: https://youtu.be/c3cQ64qbJqk
