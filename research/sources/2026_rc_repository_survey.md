# RC repositories surveyed in 2026

About 55 public repositories found by searching GitHub for radiance cascades, read at their October 2026 heads without building or running them. Most are 2D implementations of the standard scheme, so this note lists only what departs from it or carries a measurement. The standard scheme here means probe spacing ×2 and directions ×4 per cascade, geometric intervals, a top-down merge, and a jump-flood distance field.

## Contents

- [3D](#3d)
  - [Surface-chart RC (yhyu13)](#surface-chart-rc-yhyu13)
  - [Screen probes with voxel intervals (KingTheFifth)](#screen-probes-with-voxel-intervals-kingthefifth)
- [2D variants worth knowing](#2d-variants-worth-knowing)
  - [YMM4-Radiance (video-editor effect)](#ymm4-radiance-video-editor-effect)
  - [pixi-GI (HRC for PixiJS)](#pixi-gi-hrc-for-pixijs)
  - [lancimir/holographic-cascades (CPU and GPU HRC)](#lancimirholographic-cascades-cpu-and-gpu-hrc)
  - [hbattal/2D-Lights (HRC and RC playground)](#hbattal2d-lights-hrc-and-rc-playground)
- [Bugs that recur](#bugs-that-recur)
- [AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades: 3D world-space RC on branches](#alimoghimiivulkan-ray-tracing-with-radiance-cascades-3d-world-space-rc-on-branches)
- [joelmartin-dev/BeansEngine: RC removed from history](#joelmartin-devbeansengine-rc-removed-from-history)
- [Checked with nothing usable](#checked-with-nothing-usable)

## 3D

| Repository | Design | Notes |
|---|---|---|
| [yhyu13/radiance-cascades-demo](https://github.com/yhyu13/radiance-cascades-demo) (`3d/`, MIT) | probes on surface charts | see below |
| [SultanAladin/RadianceCascades](https://github.com/SultanAladin/RadianceCascades) | world probe grids, Vulkan GLSL compute | octahedral direction tiles per probe; 8-probe trilinear merge that samples each upper probe along the direction toward the lower interval's end (a 3D bilinear fix); octahedral tiles filtered by hand so they do not bleed; sparse SDF bricks with brick skipping, 64 steps; shades the nearest hit across SDF instances with per-instance albedo |
| [KingTheFifth/radiance-cascades](https://github.com/KingTheFifth/radiance-cascades) | screen probes lifted by depth | world-space intervals traced through voxels or Hi-Z; direction-first layout |
| [mpalenque/sim](https://github.com/mpalenque/sim) | world probe grid in three.js | spacing ×2 and octahedral directions ×4 per level, intervals `base·(4^i − 1)/3` to `base·(4^(i+1) − 1)/3`, cone tangent `2/√dirs`, 8-corner merge; cascade 0 resolves into an SH volume |

### Surface-chart RC (yhyu13)

Probes live on the UV charts of a Cornell box, so each surface's cascades stay a 2D problem on its chart, as in [X3XfRM](2024_mathis_x3xfrm_surface_probe_rc.md).

- 8 charts (floor and ceiling 256×256 texels, walls and two interior boxes 128×256), texel scale 1/256 unit, 6 cascades in one 1024×512 RGBA32F atlas each, double buffered: 100.7 MB in all.
- Cascade `c` uses probes of `2^(c+1)` texels with one direction per texel, direction-first. Directions follow square rings: ring `i` has `4 + 8i` bins, polar angle from the ring and azimuth around it. Each direction is weighted by its solid angle times `cos θ`.
- The interval is `probeSize/32` units; the last cascade reaches 10000. Rays are traced analytically against quads, boxes, a cylinder and a mirror sphere, with one sun shadow ray at each diffuse hit.
- The merge blends 4 upper probes bilinearly. An upper sample counts only if it hit nothing or the lower probe lies inside its cone at the hit distance, a cheap visibility test. A miss uses the upper value alone.
- Bounce: a hit reads last frame's cascade 0 at its chart texel, so each frame adds a bounce.
- RTX 2080 SUPER, RenderDoc replay: 28.6 ms for all cascades on the full atlas, 5.95 ms once padding texels were skipped. The repository warns that replay timings vary 2 to 5×. Its earlier 128³ volume RC took about 37.7 ms.

### Screen probes with voxel intervals (KingTheFifth)

Rust with glow, all in fragment passes; the README calls the 3D part SPWI. The repository records no timings.

- **G-buffer:** albedo and emissive RGBA32F, a world-space octahedral normal in RG16F (a uniform comment wrongly says view space), D32 depth, and a min/max depth pyramid in RG32F whose level 0 stores `(d, d + 0.005)`. All 11 pyramid levels are rebuilt every frame.
- **Probes and directions:** one probe per 4 px at cascade 0, each taking the depth at its own pixel rather than a block minimum; sky pixels are skipped. Cascade c has spacing `4·2^c` px and `4·2^c` azimuths times `4·2^c` altitudes (`16·4^c` directions, azimuth `(i + 0.5)·2π/N`, altitude `(j + 0.5)·π/N`, y up), a latitude-longitude split stored direction-first. Each cascade texture is therefore `4·W/s` texels per axis, screen-sized at `s = 4`; six RGBA32F cascades take about 199 MB at 1080p.
- **Intervals:** `L0 = 4`, computed from the probe diagonal in pixels but used as world units. Cascade c covers `[L0·(2^c − 1), L0·(2^(c+1) − 1))`, so intervals only double: 0–4, 4–12, 12–28, 28–60, 60–124, 124–252 world units. Rays start at `probe + dir·start + normal·0.1`.
- **Tracing:** by default through a 256³ RGBA16F voxel grid (about 134 MB) over a 30 × 15 × 16 box, so voxels are anisotropic. The grid is re-voxelized each frame by dominant-axis projection and stores only `(emissive, 1)`; diffuse is computed and dropped, and the last write wins. Each interval takes exactly 400 evenly spaced samples whatever its length, a hit being alpha above 0.05; rays leaving the box miss. Alternatives are a naive screen-space march of `20·2^(c+1)` steps and a Hi-Z traversal after Beug's SSR (400 steps at most).
- **Merge:** a hit or the top cascade returns `(rgb, 1 − alpha)`; otherwise the ray adds 0.25 times the sum of its 4 upper directions, each a hardware-bilinear tap at `clamp(0.5·coord + 0.25, 0.5, count − 0.5)`. Depth-aware interpolation is a TODO.
- **Integration:** a cosine-weighted sum over cascade 0 directions divided by the total weight and again by 16, then times albedo and a diffuse intensity of 15, so a uniform field `L` returns `(15/16)·albedo·L`. Light comes from emissive voxels only, with no bounce.
- **Defects found by reading:** π typed as 3.14169265; the cascade texture is sized with unfloored `4·W/s` while the shader floors the probe count; `imageLoad` runs before the bounds test. Alpha is not bounded: each missed level adds 1, so open sky reaches 5 at cascade 0 with 6 cascades, and the ambient-occlusion term `2·mean(alpha)/16` gives 0.625 in the open and 0.125 when occluded.
- **2D part:** 2 px spacing, `ceil(log4(diagonal))` cascades, intervals starting at `L0·(4^c − 1)/3` with length `4^c·L0`, 4 rays per stored direction, gamma 1.6.

## 2D variants worth knowing

| Repository | What differs |
|---|---|
| [Sky-Meteor/RadianceCascades](https://github.com/Sky-Meteor/RadianceCascades) (Terraria mod) | visibility-aware bilinear merge: a far probe counts only if the segment from the near probe to it is unoccluded; transmittance `*= sqrt(alpha)` per sample |
| [bjorn-johansson/radiance-cascades](https://github.com/bjorn-johansson/radiance-cascades) | DDA over a bitmap instead of a distance field; Beer-Lambert absorption per cell, about 0.2 ms extra at 6 cascades |
| [routersys/YMM4-Radiance](https://github.com/routersys/YMM4-Radiance) | 9-level occupancy pyramid for empty-space skipping during the march; absorption |
| [ryandugie/BevyRadianceCascades](https://github.com/ryandugie/BevyRadianceCascades) | switchable fixes: none, interval overlap of `√2·Δp(n+1)`, or bilinear fix with 4× rays; sun and sky injected at the top cascade only; README claims 0.82 ms |
| [Qonfused/rc-linear](https://github.com/Qonfused/rc-linear) | all intermediates kept linear in RGBA32F, sRGB only at the blit; texel-by-texel march stopping below transmittance 0.001 |
| [raesga02/RadianceCascades2D](https://github.com/raesga02/RadianceCascades2D) (Vulkan) | interval length extended by `2√2·spacing` against leaks; analytic sun lobe and sky at the top cascade |
| [lixu0073/2DGI](https://github.com/lixu0073/2DGI) (Unity URP) | last frame's GI at hits as a second bounce, ping-pong accumulation, à-trous denoiser, blue-noise ray jitter |
| [ErwinTerpstra/RadianceCascades](https://github.com/ErwinTerpstra/RadianceCascades) (Unity Render Graph) | 10-bit ARGB2101010 radiance buffer; README claims 14 and 8 ms at 1080p on an RTX 3060 laptop GPU |
| [CptNemo0/RadianceCascades](https://github.com/CptNemo0/RadianceCascades) (thesis code) | cascades updated at their own frame frequencies, measured against full updates; RGBA8 targets |
| [entropylost/vlam](https://github.com/entropylost/vlam) | cascades used for path guiding: at each level one of 4 child directions is picked in proportion to its stored radiance, dividing by the product `4·w` |
| [chamchi0809/pixi-GI](https://github.com/chamchi0809/pixi-GI) (PixiJS) | holographic RC with temporal accumulation and occluders lit from a fluence mip |
| [lancimir/holographic-cascades](https://github.com/lancimir/holographic-cascades) | CPU holographic RC following the paper's equations |
| [hbattal/2D-Lights](https://github.com/hbattal/2D-Lights) | holographic trace with per-cell absorption; direction-first RC with bilinear fix |
| [GiGGioSo/radiance_cascades_2d](https://github.com/GiGGioSo/radiance_cascades_2d) | directions ×2 per level instead of ×4; a row-by-row variant with a two-row cache |
| [nema-nya/radiance-cascades](https://github.com/nema-nya/radiance-cascades) | step lengths and angle counts doubling per level, described as a multipole expansion |
| [multiversiann/Radiance-Cascades](https://github.com/multiversiann/Radiance-Cascades), [ruizemanuel/pull-cord-lamp](https://github.com/ruizemanuel/pull-cord-lamp) | intervals extended 2% past their end; GI at 0.35 to 0.5 of screen resolution |
| [akghxhs55/radiance-cascades-d3d11](https://github.com/akghxhs55/radiance-cascades-d3d11) | cascade count `ceil(log4(3·D/L + 1))` from the scene diagonal `D` |
| [bakjedev/radiance-cascades](https://github.com/bakjedev/radiance-cascades) (Slang, Vulkan) | pre-averaging before a 4-probe merge; a pull/push pass with 1-3-3-1 weights |

### YMM4-Radiance (video-editor effect)

A 2D lighting effect for the YukkuriMovieMaker4 editor, built from four Direct2D pixel shaders. The README says the load is high and gives no measurements.

- **Passes:** emission, a 9-level occupancy pyramid (max over 2×2, stored as horizontal stripes), cascades 3 down to 0, and a composite; cascade 0 is cached.
- **Geometry:** 4 levels with spacing 2, 4, 8 and 16 px and 4, 16, 64 and 256 directions per probe. Interval bounds are `[0, 1, 5, 21, 85]/85` of the range, which defaults to 300 px (0–3.5, 3.5–17.6, 17.6–74.1, 74.1–300 px). The output is padded by the range on every side, up to 4096 px.
- **Emission:** Rec.709 luma above a threshold, `e = saturate((lum − th)/(1 − th))²`; alpha carries the absorption density.
- **Ray walk:** empty-space skipping on the occupancy pyramid from the 8 px level. An empty cell jumps to its exit plus 0.05 px and moves up a level; an occupied cell moves down. At the finest level the step is `clamp(0.03·t, 1, 32)` px, the gather adds `T·emission·gain·h/(t + 2)` and `T *= exp(−0.6·alpha·h)`. The walk stops at `T ≤ 0.004` or after 128 iterations, returning a partial result without a flag.
- **Merge and output:** the 4 upper directions are averaged with hardware bilinear filtering at `(x − worldL)/(2·spacing) − 0.5`, and the result is `saturate(gather + T·upper)`, which clips HDR light. The composite lights surfaces with `light·albedo·diffuse` and adds `light·(1 − diffuse)` as glow in air; there is no bounce.
- **Parameters (code defaults and ranges):** strength 100 (0–800), range 300 px (10–2000), diffuse 60, ambient 100, threshold 70, emission gain 150 (0–1600), occlusion 80. The README lists narrower ranges, and the changelog says near levels use finer directions, the opposite of the code. A gain uniform in the emission shader is never used.

### pixi-GI (HRC for PixiJS)

The npm package `pixi-rcgi`, for PixiJS v8 on WebGL2 (with `EXT_color_buffer_float`) or WebGPU, with shaders written once in pixi-psl. It credits Yaazarai's Volumetric-HRC and the [HRC paper](2025_freeman_holographic_radiance_cascades.md).

- **Buffers:** extent `min(2048, nextPow2(max(view) + 1))` and `log2(extent)` cascades (9 at 512). Emissive RGBA16F, occlusion and normals RGBA8, rays RGBA16F at width `floor(extent/2^n)·(2^n + 1)`, cones and fluence RGBA16F at extent², fluence with mips. Memory is `extent²·(cascades + 2)` RGBA16F texels: 23 MB at 512, 96 MB at 1024 and 436 MB at 2048.
- **Frame:** albedo, emissive and occlusion renders through a GI camera whose translation snaps to `2^min(lod, log2(margin + 1))` px; per frustum a seed, extension from cascade 0 (not the paper's cascade 3) up to N − 1, merge from N − 1 down, and an additive resolve; up to 3 smoothing passes; optional temporal accumulation; fluence mips. That is `4·(2N + 1)` full-screen passes plus the mips, 76 at N = 9.
- **Seed and merge:** emission is radiance per pixel of travel, so emitters light the room without occluding; alpha is `1 − occlusion`. Rays join front to back. Cone weights are `0.5·atan(I/(I² + k(k + 1)))` with `I = 2^n`, which is half the angle between adjacent slopes `k/I` and `(k + 1)/I`; the weights sum to π, so the resolve multiplies by 1/π. Even planes average the far merge with the near cone, and interpolation happens after merging.
- **Smoothing:** four diagonal taps at offset `2^(i−1)` texels in pass i cancel the 2, 4 and 8 px lattice patterns; the checkerboard component falls from 1.5% to 0.05% of mean luma.
- **Temporal (off by default):** an exponential moving average whose keep factor (at most 0.98) is multiplied by an on-buffer test and by `1 − smoothstep(0.1, 0.4, relative luma change)`, reprojected by the camera delta. It costs 0.15 ms at 512². Keep 0.85 lowers the frame-to-frame difference by 44% and 0.95 by 55%, with mean luma unchanged within 0.1%.
- **Occluders:** a pixel inside an occluder takes the mean of free-space light dilated over mip levels (weights halving per level), shaded with half-Lambert wrap from the gradient of that field when a normal map exists. The README calls this a dilation, not a solve.
- **Measurements (author, 960×540 demo, Apple M1 Pro, Chrome on ANGLE-Metal):** resolution 0.25 gives 256² buffers, 8 cascades, 3.0 ms for HRC and an 8.3 ms frame; resolution 0.5 gives 512², 9 cascades and 8.5 to 10.4 ms for HRC. The temporal section of the same README gives 3.2 ms for the hierarchy at 512², which does not match.
- **Limitations listed:** no sky, no multi-bounce, leaks through thin walls at grazing angles, and emitter intensities quantized through 8-bit tints. The README's margins at 1080p and resolution 0.5 (483 and 63 px) are totals; per side they are 241 and 31 px.

### lancimir/holographic-cascades (CPU and GPU HRC)

Code from a lancimir studios game in progress, with no license.

- **CPU:** a 256² grid (N = 9) of transmission and radiance. Cascade n has planes every `2^n` cells and `2^n + 1` rays per probe with directions `(2^n, 2k − 2^n)`, stored at `(x/2^n)·(2^n + 1) + k`, and angular weights as `atan2` differences. A forward pass for `n = 1 … N − 1` builds rays (an even ray merges two child rays, an odd ray averages two chain orders), then a backward pass for `n = N − 2 … 0` builds fluence (even planes average two cones) from a zero top level, so there is no sky. Four quarter-turned frustums run under OpenMP and are summed with weight 0.25, then blurred with a cross of center 1/2 and neighbors 1/8.
- **CPU timings (file header, i7-14700K):** clang `-O3` without `-fopenmp` takes 210 ms at 512², 40 ms at 256² and 16 ms at 128²; MSVC `/O2` takes 280, 57 and 16 ms. Without `-fopenmp` the pragmas do nothing, so these are probably single-threaded.
- **GPU (raylib):** 1024² (N = 10), all RGBA32F. Transmittance for levels 0 to 2 uses brute-force point samples and merges above that; fluence runs from level 8 down; the same cross blur. No timings.
- **Defects found by reading:** a debug macro left in the fluence shader writes 100 whenever an even-plane fetch has positive green; out-of-range accumulation reads return clamped values instead of black; the blur counts out-of-range taps as white, brightening frame edges; circles are drawn at twice their radius.

### hbattal/2D-Lights (HRC and RC playground)

Three.js 0.184 with GLSL3 on WebGL2, with four modes: HRC, RC with the bilinear fix, plain RC, and a 64-ray brute-force reference with blue-noise offsets. No license.

- **Grid:** the lighting grid is as wide as the resolution setting (1024 on desktop), giving 10 cascades, and only every other probe row is stored ("half probes").
- **Scene:** RGB is emission and alpha absorption (1 for opaque shapes, 30 for balls); both pass through `pow(·, 2.2)`, so absorption is `alpha^2.2`, and the author's comments call the absorption scale unresolved.
- **HRC:** per frustum, cascade 0 alone is traced by a DDA over texels (`tran = exp(−absorb·step)`, `rad = emission·(1 − tran)`); levels 1 to n − 1 are built by extension (an even ray takes child `ind/2`, an odd ray averages its two neighbors, and nothing is chained when the far half falls off the buffer); cones are merged from the top with atan-difference weights, the top reading a 200-texel sky texture times the cone width. The four frustums are summed, divided by 2π and sRGB-encoded. The repository counts `4·(2·ceil(log2 W)) + 2` passes, 82 at 1024. Transmittance is one scalar, though the shader README lists per-channel transmittance as an option.
- **RC:** a jump-flood field seeded from pixels with alpha ≥ 1; `ceil(log4(3·hypot(w, h) + 1))` cascades on a half-resolution grid; direction-major blocks of `2^n × 2^n` with four sub-rays per stored direction. Intervals start at `(4^n − 1)/3` with length `4^n` plus the upper probe diagonal `|(2^(n+1), 2^(n+1))|` against leaks, and a miss takes one hardware-bilinear tap of the upper cascade. The bilinear-fix mode uses length `4^n` and casts four rays toward the four upper probes, combined with bilinear weights; the repository's note says this removes occlusion errors and leaks at a higher cost.
- **Defects:** the probe-major path and a brute-force HRC shader are unreachable; the mobile resolution shows 700 but uses 800; the rainbow sky fills only texels 0 to 50 of 200.

## Bugs that recur

- Intervals that do not meet: in lantrol's code level 1 ends at 4 units while level 2 starts at 5, leaving a gap. nff747's interval comments disagree with its code.
- Merges skipped where they matter: CptNemo0's out-of-bounds rays skip the upper merge, darkening borders; nff747's "bilinear" merge reads only the same texel.
- Probe spacing never grows (nff747), or the cascade count is computed but the last merge step is missing (Yaocenji).
- Float ray indices lose exactness above 2^24 (CptNemo0, from cascade 12 on).

## AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades: 3D world-space RC on branches

https://github.com/AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades. The default branch `main` (and `develop`, `feature/caustics`) is a Vulkan compute path tracer (`Vulkan-Engine/shaders/raytracer.comp`, 972 lines: spheres, triangles, planes, quads, cubes, a BVH, PBR, glass, fog, depth of field, SSAA, soft shadows; `feature/caustics` adds photon mapping). The RC lives on other branches, which start with commit 52e595e (2026-05-25, "Started Phase 7: The Allocation Pass"):

| Branch | Tip | State |
|---|---|---|
| `scene-swapper` | 14752f4 (2026-06-17) | most complete; the README names it the latest |
| `refactor/radiance-cascades` | 9bb9cd3 (2026-06-16) | same RC files |
| `merge-caustics-RC` | b201233 (2026-06-05) | RC merged with the caustics layer |
| `merge-caustics-RC-second-bounce` | 9b04c58 (2026-06-05) | adds a world-space SH cache for second-bounce color bleeding (`probe_shcache.comp`) |
| `testing-scaling-tex`, `testing-no-artifacts` | b2839fc, 462d305 | partial experimental shaders |

The design on `scene-swapper` (`include/gi/CascadeConfig.hpp`, `shaders/rc/*.comp`, `reference-files/technical_manual.md`):

- **Hierarchy:** a 3D world-space grid. `numCascades = 5` in the config, while the manual documents 3 levels. Level `k` has probe spacing `0.5·2^k`, an octahedral map of `4·2^k` texels per side (16, 64, 256, … directions), and a grid that halves per level from 64 × 60 × 92.
- **Intervals:** `end(k) = 0.5·4^k`, `start(k) = end(k − 1)`, so [0, 0.5], [0.5, 2], [2, 8], [8, 32], [32, 128]. Spacing doubles while interval length grows ×4, the usual 3D rule (spacing ×2, directions ×4 per level).
- **Sparse probes:** level 0 probes are allocated from G-buffer pixels and level `k > 0` from the parent slots their children need; each level has a GPU hash map (`probe_alloc.comp`, `CascadeHashMap.cpp`) filled bottom-up with atomic inserts.
- **Tracing:** `probe_trace.comp` runs one thread per (slot × octahedral texel) ray, with `tMin = start + 0.001` and `tMax = end`, testing analytic planes and quads and then a BVH. It stores FP16 radiance and transmittance; level 0 adds direct light with shadow rays.
- **Merge:** `cascade_merge.comp` runs top-down, trilinear over the 8 parent probes and 2 × 2 bilinear over the parent's octahedral map, with `L = near.L + near.T·far.L` and `T = near.T·far.T`.
- **Gather:** `final_gather.comp` interpolates the 8 surrounding level 0 probes trilinearly; `probe_sh.comp` pre-integrates level 0 into SH.
- **Recorded bugs (manual):** BUG-1, darkening at grid borders from an uninitialized transmittance accumulator for missing parents; BUG-2, probe shadows that ignored walls, fixed with analytic plane and quad shadow tests; BUG-3 and BUG-4, typos. Both fixes are present at all four branch tips: `cascade_merge.comp`, identical on all four, starts the accumulator at `parentAccum = vec4(0.0, 0.0, 0.0, 1.0)` (line 97), and `probe_trace.comp` tests analytic planes and quads before the BVH shadow call in both its hard and soft shadow paths. The repository keeps these files under `Vulkan-Engine/`.
- No timings are published.

This is the only 3D sparse-hashed world-space RC found in the survey whose code is complete enough to read end to end; the other sparse designs are in [2026_sparse_and_3d_rc.md](2026_sparse_and_3d_rc.md).

## joelmartin-dev/BeansEngine: RC removed from history

https://github.com/joelmartin-dev/BeansEngine is a Rust and `ash` Vulkan engine whose README says it exists to compare RC with ReSTIR. Its `main` branch now only rasterizes unlit glTF scenes: the RC, ReSTIR and reference shaders and about 985 lines of engine code were removed on 2026-04-18 (commits 4b3e618 and c9cf5ce, "removed global illumination capabilities, needs documentation before proceeding"). The history holds two Slang variants:

- **Software variant** (`assets/shaders/software/radiance_cascades.slang`, 302 lines, compute with inline ray queries): every screen pixel is a probe with one output image per level and `baseRayCount << level` rays (doubling per level). Level `L` covers `[s·L², s·(L + 1)²]` with `s = 1/interval`, so intervals grow quadratically, not geometrically. The probe sits along the primary camera ray at a level-dependent fraction of the first-hit distance, minus 0.001. Directions follow a golden-angle spiral over the sphere. On a miss, when a coarser level exists, the coarser level's output at the same pixel is added at half weight: a per-pixel merge with no spatial or angular interpolation. Ray results are saturated with `1 − exp(−x)` and averaged.
- **Hardware variant** (`assets/shaders/hardware/radiance_cascades.slang`, 124 lines): one dispatch per level with `(level + 1)·8` rays per pixel, over fixed slabs of length `interval/1000`, offset by `level·interval/1000` from a point 4 units in front of the camera, so intervals do not grow. There is no merge: the fragment shader sums all level textures. Each ray's sample is divided by `(ray_idx + 1)·8` rather than by the ray count, so later rays weigh less, which looks like a bug.
- Timeline: "still struggling with merging intervals" (2025-11-01), "Semi-working RC" (2025-11-03), the hardware and software split (2025-12-24), "radiance_cascades restarted" (2026-03-09), removal (2026-04-18). An earlier C++ version was moved out of the repository in 674d08a (2025-12-19) to a repository that was not found. No measurements exist.

## Checked with nothing usable

These look relevant by name but hold no working GI RC code (each checked through all branches and history, 2026-10-18):

| Repository | What it contains |
|---|---|
| Kollabiz/GoRadianceCascades | README, license and `.gitignore` only (1 commit); the README describes a 3D engine with RC diffuse GI that is not there |
| Temp-Name-Studio/Bevy-Voxel-Cascade | a one-line README ("Real Time GI Raytracing solution using Voxelization and Radiance Cascades") |
| willWallace-RIT/Radiancecascade3d | a README calling it a port of X3XfRM from "qwen base code"; the GDScript and GLSL do not run (undeclared identifiers, Godot 3 `PoolIntArray`, `gl_in` in a vertex shader, undeclared `TraceRay`); one fixed `1/256` step toward the sun, no cascades or merge |
| JavierSerranoDev/radiance-cascades-vulkan | a Visual Studio template printing "Hello World!" |
| Winstob/radiance-cascades | an AVL-balanced free list over index ranges in Rust with a test driver, a pass-through WGSL shader, and a README titled "string-art"; only the package name mentions RC |
| shirokoff/raylib-radiance-cascades | a raylib window that displays a 16 × 8 emitter-and-door cell texture (the door toggles every 3 s), the input stage of a 2D RC that was never written; committed binaries |
| j-vandy/SilkEngine | a Vulkan C++ wrapper with an ECS and a glTF duck demo; the README calls it a "Flatland Radiance Cascades rendering engine" and the `paint` branch is a 2D paint prototype meant for RC experiments, but no RC code exists |
| Heraclito-Q-Saldanha/RadianceCascades | a Bevy 0.19 plugin registering an empty `draw_system` after the opaque pass |
| vsensu/bevy_radiance_cascades | a Bevy 0.20 new-project template |
| cgorto/bevy-radiance-cascades | a Bevy 0.16 2D paint app with a naive screen-space raymarch: 16 rays per undrawn pixel, up to 128 texel steps, taking the first texel with alpha above 0.5; no cascades, intervals or merge |
| WillKirkmanM/radiance-cascade | a 2D canvas effect: 4 concentric radial-gradient discs per light, screen-blended, with shadow polygons extruded from rectangle edges; the "cascade" levels do not interact |
| tinycrops/Radiance-Cascades | a PyTorch stack of residual MLPs ("cascades") summed coarse to fine with early exit, plus a volume ray-marching demo of a learned field; it bundles Osborne and Sannikov's radiative-transfer paper but implements no light transport |
| katyhuff/uiuc-arfc-2025-02 | a LaTeX technical-report template; its description mentions an RC report that is not in the repository |
