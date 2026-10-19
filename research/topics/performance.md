# Performance

The measured cost of RC and of the GI systems it competes with, gathered by domain, then normalized to rays per second, time per megapixel and bytes per probe, and turned into per-frame budgets for single-frame 3D RC. Full per-project tables stay in the topics that own them, linked from each row; this file owns the cross-domain comparisons, the 2D timing tables that have no other home, and the budgets. Figures marked "derived" were computed from the sources' data, not stated in them, by the models given in each section.

## Contents

- [What the numbers show](#what-the-numbers-show)
- [2D](#2d)
  - [Per-pass cost in one 2D solver](#per-pass-cost-in-one-2d-solver)
  - [Community 2D timings](#community-2d-timings)
- [3D screen space](#3d-screen-space)
- [3D world space and surfaces](#3d-world-space-and-surfaces)
- [Volumetric and HRC](#volumetric-and-hrc)
- [Godot](#godot)
- [Related techniques](#related-techniques)
- [GPU building blocks](#gpu-building-blocks)
- [Normalized throughput (derived)](#normalized-throughput-derived)
  - [Time per megapixel (derived)](#time-per-megapixel-derived)
  - [Memory per unit (derived)](#memory-per-unit-derived)
- [Budgets for single-frame 3D RC (derived)](#budgets-for-single-frame-3d-rc-derived)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)

## What the numbers show

- **Cascade 0 probe count sets the cost.** Halving the probe spacing quadruples the probe count and multiplied time by 3.7 to 4.0 in Dell'Ova, about 3 in Kung and 3.5 in creikey's voxel RC (derived from their tables). Dell'Ova's 16 rays at spacing 1 and 64 rays at spacing 2 cost the same (24.74 against 24.78 ms) and use nearly the same memory (335.6 against 323.4 MB), so cost follows `rays₀/spacing²` ([theses](3d_screen_space_theses.md#dellova-2025-performance-scaling-with-dxr), [creikey](3d_world_space_implementations_grids.md#creikeyvoxel-radiance-cascades)).
- **Rays per probe scale a little below linear** (16 to 64 cascade 0 rays cost 3.3 to 4.0× in Dell'Ova), and **resolution scales with pixel count** (1440p cost 1.59 to 1.79× of 1080p against a pixel ratio of 1.78 in Dell'Ova; trace grew 9.3× and merge 10.0× for 9× the pixels in Peter's 2D solver).
- **Light count does not matter when emitters are scene data.** PoE2 costs the same for one fireball or a million; Radiant 2D costs about 12 ms with 2, 102 or 1002 lights ([core theory](core_theory.md#independence-from-light-count-and-scene-content)). Light count returns as a cost only where lights are injected into a structure: EggyStudio's GI rose from 0.35 to 2.77 ms going from 1 to 64 emissive blocks ([EggyStudio](3d_world_space_implementations.md#eggystudio3dengine)).
- **Tracing is most of the cost in dense designs.** Dell'Ova's gather pass is 87 to 96% of RC time, and Kung names the ray march as the main cost. Sparse designs move the cost into bookkeeping: in Split RC, tracing is 1.3 of 8.6 ms on Sponza and 4.5 of 11.5 ms on San Miguel, and probe setup, deposit and shading take the rest ([3D world space](3d_world_space.md#measurements)). In a 2D solver with one probe per pixel and cheap SDF tracing, the merge was the largest pass ([below](#per-pass-cost-in-one-2d-solver)).
- **Long intervals cost the most.** In DexRT's 2D solver the top cascade took 63.6% of the time and cascade 0 only 0.5%; a model with time proportional to interval length and equal texels per cascade puts 75% in the top cascade of six ([core theory](core_theory.md#rays-traced-and-rays-built)). Per ray, the top of five cascades at `l = 4` takes 256× cascade 0's steps with a fixed-step march, 16× with a mip chain whose voxel follows the probe spacing, and the same with a tracer whose steps do not grow with length ([fix cost by tracer](artifacts_and_fixes.md#cost)). Kung's fixed-step depth march took 4.9 ms in a small house and 30 ms outdoors at the same settings. Letting each cascade march a coarser mip cut DexRT's time 3.5× ([volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)).
- **RC is bandwidth bound.** Moving from RGBA32F to RG16F, R11G11B10F and R16F targets took one 2D build from 81 to 240 fps at 768² ([formats](cascade_layout_and_merging.md#formats)); RGBA16F against RGBA8 cost 500 against 40 ms in one 4096² test ([volumetric](volumetric_and_radiative_transfer.md#storage-and-colour)); HRC is bandwidth bound too ([HRC](holographic_rc.md#performance)); Peter's atlas copy grew 15.4× for 9× the pixels once the atlas left the caches.
- **Hardware ray tracing is 3.5 to 4× faster than good software traversal** on the same RC rays (66 against 231 µs on a Radeon 8060S; about 4× on Apple M3), and **geometry complexity costs software tracers far more:** Gavras's Metal tracer on an M1, which runs as compute, lost 4.4× from cubes to Sponza at the same ray count, while Dell'Ova's DXR ran Sponza at 6 to 8 G rays/s ([tracing](scene_representation_and_tracing_voxels_and_bvhs.md#software-against-hardware), [throughput](#normalized-throughput-derived)).
- **Atomics and contention are a recurring cost.** Split RC's deposit (2.2 ms) costs more than its trace (1.3 ms) on Sponza; one build's atomic deposits took 16 ms against 0.3 ms without atomics; sparse_rc_2d's statistics atomics alone cost about 1.5 ms ([ray splitting](3d_world_space.md#ray-splitting), [Bevy](2d_implementations.md#bevy)).
- **Quality fixes have a price.** The bilinear fix traces 4× the rays (about 2× the time in 2D, 4.4 to 6.6× modelled for a trilinear 3D grid); the parallax fix costs about 20%; nearest merging with forking costs about a quarter of the bilinear fix; a two-tap diagonal grid cut one frame by 33% ([fixes compared](artifacts_and_fixes.md#fixes-compared), [cost](artifacts_and_fixes.md#cost)).
- **Dense 3D grids run out of memory first.** Full grids took 960 MiB for a Cornell box (jumeder), about 1.5 GB allocated at 192³ (CT volume RC) and 3.5 GiB for two atlases (tmpvar). Clipmapped and voxel-volume designs stayed under about 150 MB (EggyStudio 1.65 to 9.16 MB, creikey 12 MiB, voxel2026 148 MB), and screen-space RC at 1080p stayed under 500 MB with a spacing of 2 or more (Dell'Ova).
- **Temporal reuse in other systems hides a large ray debt.** DDGI's default hysteresis is worth about 34 M single-frame rays, about 23 ms of tracing at its own 1.5 G rays/s; a daGI2 radiance grid updated in full each frame would cost 16× its budget, and HSGI's near and far fields 9× and 121× ([DDGI](related_probe_gi.md#ddgi), [engine GI](related_engine_gi.md#connections)). A single-frame RC pays its rays in full each frame, so its cost is compared with the amortized cost of these systems, not their sampling rate.

## 2D

| Project | Hardware | Setup | Result | Owner |
|---|---|---|---|---|
| Radiant 2D (Sannikov) | RTX 3060 | per-pixel GI | about 30 ms depending on quality; about 12 ms with 2, 102 or 1002 lights | [history](history_and_landscape.md#the-paper) |
| Lystrup's demo | GTX 970 | no denoising or temporal accumulation | 0.3 ms | [history](history_and_landscape.md#news-and-discussion) |
| GM Shaders stress test | RTX 3080 | 4 probes per pixel, 4 cascade 0 rays; position-first at 1024², direction-first at 1080p | 29.91 and 25.95 ms, 28.5 against 12.5 ms per megapixel (derived) | [GM Shaders](2d_articles_and_demos_gm_shaders.md#gm-shaders-yaazarai-and-xor) |
| Peter's thesis | RX 7900 XTX, OpenGL | one probe per pixel, 9 cascades, SDF scene, 720p to 4K | RC passes 0.73 to 7.95 ms | [below](#per-pass-cost-in-one-2d-solver) |
| IceKontroI sparse_rc_2d | RTX 2080 Ti | 1080p, dense and sparse task lists, jump flood excluded | 0.5 to 4.9 ms; statistics atomics about 1.5 ms; 197 MB slab pool | [Bevy](2d_implementations.md#bevy) |
| README claims | various | ryandugie, ErwinTerpstra, bjorn-johansson | 0.82 ms; 14 and 8 ms at 1080p on a laptop RTX 3060; about 0.2 ms extra for Beer-Lambert at 6 cascades | [ports](2d_implementations.md#unity-and-other-ports) |
| mebyz adaptive cascades | WebGPU | upper cascades trace every second or fourth ray | 10 to 40% fewer rays at 36 to 68 dB; auto mode about 19% at over 50 dB | [ports](2d_implementations.md#unity-and-other-ports) |
| Reservoir Cascades | Apple-silicon laptop, WebGPU | 256², 262,144 candidate rays per frame | 120 fps | [Reservoir Cascades](rc_for_sampling_and_guiding_reservoir_cascades.md#experiments) |
| Sohojoe (Godot) | | 1280×736 at quality 0.5 | about 60 MB per RGBA32F cascade texture | [Godot 2D](2d_implementations.md#godot) |
| tmpvar playground | | sized for the slider limits | 512 MiB probe buffer allocated at startup | [playground](2d_articles_and_demos.md#tmpvars-playground) |
| jason.today final demo | | 512², 6 cascades | 6.3 M rays per frame; GPU timer disabled | [2D parameters](cascade_layout_and_merging.md#2d-parameters-across-implementations) |
| Paul Stus, "Presentation of my Radiance Cascades project" (https://www.youtube.com/watch?v=ZJ5NmYEwlKQ, 2026-02) | not stated | 2D canvas project | about 78 fps without GI, 37 fps with it ([talks](../sources/2026_rc_conference_talks.md#other-videos-checked)) | here |

McGhee's estimate for brute force, not a measurement: 512 rays per pixel at 1024² is about 500 M rays and 1 s per frame, about 100× over a 60 fps budget, so the naive method cannot reach 512 or 1024 rays in real time at large resolutions ([core theory](core_theory.md#independence-from-light-count-and-scene-content)).

### Per-pass cost in one 2D solver

Peter's bachelor thesis times a 2D solver with one probe per pixel, 4 rays per probe, spacing ×2 and directions ×2 per cascade, SDF circles and boxes sphere-traced up to 128 steps and one RGBA16F atlas of 8× the pixel count. Timings are OpenGL timestamp queries, the median of 1000 frames after 200 warm-up frames, on a Radeon RX 7900 XTX with a Ryzen 9 9950X3D under Windows 11, CornellLike scene ([Peter](../sources/2026_peter_rc_2d_bachelor_thesis.md), design in [2D implementations](2d_implementations.md#cpu-references-and-research-harnesses)).

| Resolution | Trace | Merge | Copy | RC total | Frame |
|---|---|---|---|---|---|
| 1280×720 | 0.236 ms | 0.345 ms | 0.148 ms | 0.73 ms | 0.88 ms |
| 1920×1080 | 0.511 ms | 0.789 ms | 0.535 ms | 1.84 ms | 2.11 ms |
| 2560×1440 | 0.937 ms | 1.543 ms | 0.935 ms | 3.42 ms | 3.78 ms |
| 3840×2160 | 2.206 ms | 3.459 ms | 2.285 ms | 7.95 ms | 8.66 ms |

- From 720p to 4K the pixel count grows 9×; trace grew 9.3× and merge 10.0×, which supports a cost bounded by pixel count. The atlas copy grew 15.4×, which the author puts down to memory bandwidth once tens of megapixels no longer fit any cache.
- The merge is the largest pass at 37 to 41% of the frame, trace 25 to 27% and copy 17 to 26%. The RC passes take 83% of the frame at 720p and 92% at 4K, and the merge cost varied by under 5% across six scenes.
- Per megapixel the RC passes cost 0.79, 0.89, 0.93 and 0.96 ms from 720p to 4K (derived): nearly flat, rising with the copy's bandwidth cost.

### Community 2D timings

Figures posted by implementers, with hardware and settings as reported; most builds are unoptimized research code ([merging notes](../sources/2026_merging_and_ringing.md#measured-2d-timings)).

| Setup | Time |
|---|---|
| 512² probes, laptop RTX 3080 | 1.85 ms |
| 1024² vanilla, WebGL half floats, RTX 3080 Ti | about 2.5 ms |
| 1024², 6 cascades, RTX 4070 Super (framework overhead included) | 8.8 ms |
| 3440×1440, probes every 2 px, direction-first vanilla in Godot, RTX 2070 Super | about 4.5 ms |
| 1080p, vanilla plus bilinear fix, 4 to 5 cascades | 7 ms |
| 3840×2160, 2x/3x scaling with the bilinear fix | 8 ms |
| 8K, 6x/6x scaling, 238 M mostly short rays | 3.5 ms |
| 480×272 upscaled to 1080p | 2 ms |
| 1080p on a GTX 1080, after moving ray marching to quarter resolution | 200 → 15.6 ms |
| 4K output from quarter-resolution cascades, GTX 1060 | about 12 ms |
| Steam Deck, 320p | about 7 ms |
| 640×480 on a Radeon 760M | about 16 ms |
| Jump flood at 512×256, RTX 2080 Super | about 10 µs |

A basic compute path tracer took about 10× vanilla RC's time at the same resolution, and vanilla RC at 1024² matched about 16 path-traced rays per pixel.

- The 8K row is the highest reported rate in 2D: 238 M rays in 3.5 ms is about 68 G ray segments per second, possible only because most are a few texels long (derived).
- The quarter-resolution rows (200 to 15.6 ms; 4K from quarter-resolution cascades in about 12 ms on a GTX 1060) show that tracing resolution, not output resolution, sets the cost, the same lever as screen-probe spacing in 3D.

HRC's 2D timings and cost model are in [holographic RC](holographic_rc.md#performance) and [measured results](holographic_rc.md#measured-results-and-the-cost-model); the merge-kernel test (a 3×3 kernel raised the merge from 0.41 to 0.63 ms at 1024²) is in [artifacts](artifacts_and_fixes.md#grid-and-blocky-penumbras).

## 3D screen space

| Project | Hardware | Setup | Result | Owner |
|---|---|---|---|---|
| PoE2 | GTX 1050; GTX 1650; RTX 4090 | top-down camera, depth-buffer march, no temporal reuse | about 1 ms, constant (talk); about 3 ms on a GTX 1050 (paper); 1.5 ms on a GTX 1650 and about 3 ms on a GTX 1060 (implementer threads); 0.8 ms at 4K on an RTX 4090 | [PoE2](3d_screen_space.md#path-of-exile-2) |
| Sannikov's single-shot image-space GI (2023) | not stated | current frame only, no reprojection | about 5 ms | [measurements](3d_screen_space.md#measurements) |
| Sannikov's SPWI demo | RTX 3060 | world-space analytic SDF march from screen probes | 30 to 50 ms, one to two orders of magnitude slower than PoE2's approach | [SPWI](3d_screen_space.md#screen-probes-with-world-intervals) |
| Dell'Ova | RTX 3080, DXR | Sponza, 5 to 8 cascades, 1080p and 1440p, emission only | 1.94 ms (spacing 4, 16 rays, 5 cascades) to 241.56 ms (1440p, spacing 1, 64 rays); 24 to 3610 MB | [Dell'Ova](3d_screen_space_theses.md#dellova-2025-performance-scaling-with-dxr) |
| Kung | RTX 3060, D3D11 | 1280×720, 6 cascades, depth-buffer march | probe every 4th pixel 4.9 to 30 ms; every 2nd 18 to 100 ms; every pixel 70 to 295 ms | [Kung](3d_screen_space_theses.md#kung-2025-rc-against-voxel-cone-tracing) |
| Kaméus | RTX 2070, DXR ray queries | 2048×1024, probe every 4×4, 2×2 or 1 px, one or min and max probes | 9.72 to 13.34 ms at 4×4, 21.21 to 43.02 ms at 2×2, 68.03 to 158.85 ms per pixel; min and max probes cost 2 to 17% more; 8 to 256 MB | [Kaméus](3d_screen_space_theses.md#kaméus-2025-minmax-probe-placement) |
| Gavras | M1 MacBook Air, Metal RT | 1920×1080, 6 cascades | 32.77 to 39.87 ms small scenes, 143.74 to 155.90 ms Sponza; 147 to 408.5 MiB | [Gavras](3d_screen_space_theses.md#gavras-2025-spwi-on-metal) |
| Abou Dan and Jensen | "modern hardware" | screen probes traced with visibility bitmasks, in a game, no temporal reuse | 2 ms lowest, 6 ms medium, 26 ms high; 0.03 to 3.9 GiB | [Abou Dan and Jensen](3d_screen_space_theses.md#abou-dan-and-jensen-2025-visibility-bitmask-screen-probes) |
| Gerassimov, Unity URP | RTX 4060 Laptop | whole-frame medians, three scenes | RC frames 3.75 to 4.43 ms against 2.56 to 2.92 ms without GI, so RC adds about 1.2 to 1.8 ms (derived); SSGI frames 7.14 to 9.62 ms | [Gerassimov](3d_screen_space_theses.md#gerassimov-2026-rc-against-unitys-gi) |
| Alpha-Renderer | RTX 3070 | 1080p, 6 cascades, 2 px probes, min/max depth pyramid, 12.4 M rays | about 5.5 ms, about 80 MB (README) | [Alpha-Renderer](3d_screen_space_implementations.md#alexander-koutrakisalpha-renderer) |
| three-rc | | 1080p, 8 cascades, two R11G11B10 targets | 16.6 M rays per frame; 15.8 MiB of merged cascades | [three-rc](3d_screen_space_implementations.md#three-rc) |
| KingTheFifth | | 1080p, six RGBA32F cascades, 256³ voxel grid | about 199 MB of cascades plus 134 MB of voxels | [KingTheFifth](3d_screen_space_implementations.md#kingthefifthradiance-cascades) |
| Depth-buffer optimization stack | not stated | cumulative: fp16, half resolution, sector casting, bitmasks, prefiltered mips | about 1000 ms naive, 500 ms with fp16, 20 ms with sector casting, about another 4× from prefiltered mips | [measurements](3d_screen_space.md#measurements) |
| Other forum figures | not stated | min/max SSRC with about 1 sample per cascade per frame and 1% blend; SSRC AO; Vulkan hardware-RT port with bilinear fix and cascade −1 at 2K | 2.8 ms; 2.7 ms generation and 8 ms merge; about 14 ms with no accumulation | [measurements](3d_screen_space.md#measurements) |

Scaled to 1080p by pixel count (derived, which holds for screen probes at fixed spacing): Kung's every-4th-pixel runs become 11.0 to 67.5 ms on an RTX 3060, and Kaméus's 4×4 runs 9.6 to 13.2 ms on an RTX 2070. Per megapixel, Dell'Ova's spacing 4 with 16 rays costs 1.1 ms (8 cascades), Kaméus's 4×4 runs 4.6 to 6.4 ms, Alpha-Renderer 2.7 ms, Gavras 15.8 to 75.2 ms and PoE2 at 4K 0.1 ms, a spread of almost three orders of magnitude that tracks the tracer and the scene more than the method ([time per megapixel](#time-per-megapixel-derived)).

## 3D world space and surfaces

| Project | Hardware | Setup | Result | Owner |
|---|---|---|---|---|
| Split RC (paper) | RTX 3080 Laptop, OptiX | hashed probes near visible surfaces, fp32, one diffuse bounce, single frame, not micro-optimized | Sponza 8.6 ms (setup 1.2, rays 0.4, trace 1.3, deposit 2.2, merge 1.0, shade 2.5); San Miguel 11.5 ms (1.3, 0.6, 4.5, 1.9, 0.8, 2.4); cascade −1 adds 1.4 ms | [measurements](3d_world_space.md#measurements) |
| Sannikov's sparse 3D RC | laptop; laptop RTX 4090 | hashed world-space tiles, from scratch each frame, no denoiser | 60 to 100 fps with a screen-space marcher; 60 fps with hardware RT, unoptimized; Sponza 3 to 5 ms (forum) | [sparse 3D RC](3d_world_space.md#sannikovs-sparse-3d-rc-2025) |
| Other sparse builds | laptop RTX 3080; Apple M2, M3 Max | various | 1 ray per pixel about 2 ms, about 3 rays per pixel 22 ms (3× the rays, 11× the time); software-RT prototype 512 ms (30% tracing, 50% hash insertion); one emitter took a box room from 120 to 30 fps; 2048² frame 34.7 ms | [measurements](3d_world_space.md#measurements) |
| chandra | CUDA, hardware RT | 2^18 base probes, fp32 | about 1,120 MiB of buffers (from the code's formulas) | [chandra](3d_world_space_implementations.md#chandra) |
| wroughtinator browser build | WebGPU | presets Performance to Ultra | 90,000 to 720,000 rays per frame | [browser build](3d_world_space_implementations.md#split-radiance-cascades-webgpu-browser-build) |
| owoDra/real-time-gi-lab #3, Split RC rays | Radeon 8060S | ray traversal only | 66 µs hardware RT, 231 µs software | [tracing](3d_world_space.md#tracing-for-world-space-cascades) |
| erhe | not stated, hardware RT | dense grid reduced into DDGI maps, 131,072 texels per frame | update 1.15 to 1.57× a DDGI update; 0.7 ms per million rays against about 6 for its DDGI; 288 MiB | [erhe](3d_world_space_implementations.md#measurements-against-ddgi) |
| creikey | not stated, D3D11 | 640×360, screen probes over a voxel clipmap | GI 0.76 ms (trace 0.52 ms); final build 2.1 ms average, 2.5 ms worst; halving cascade 0 spacing cost 3.5×; 12 MiB | [creikey](3d_world_space_implementations_grids.md#creikeyvoxel-radiance-cascades) |
| EggyStudio | laptop GPU | 800×450, distance-field clipmaps plus screen probes, Low to High | 0.59, 0.74, 1.00 ms; 1.65, 4.38, 9.16 MB | [EggyStudio](3d_world_space_implementations.md#eggystudio3dengine) |
| voxel2026 (jtbirdsell, issue #4) | RTX 4090 | 1080p, 256³ voxel volume, worst case | 1.98 ms (0.17 volume, 1.55 build, 0.26 query); voxel cone tracing 2.06 ms (0.17 volume, 1.88 gather); 124 MB plus 24 MB | [measurements](3d_world_space.md#measurements) |
| Trillion3D | not stated | camera-centred probe bounce, 64 full-length rays per probe | 1.1 ms against a 0.8 ms budget | [adoption](3d_world_space.md#adoption-and-plans) |
| Variance-guided retracing | RTX 2080 Ti | 4 full-length rays per probe in high-variance cascade 0 directions | +1 ms on a 4 ms scene | [measurements](3d_world_space.md#measurements) |
| jumeder | DXR | full 32³ grid, 2048 directions, 4 cascades | 960 MiB, 126 M rays per frame | [jumeder](3d_world_space_implementations_grids.md#jumederdx12-radiance-cascades) |
| tmpvar 3D grid | | 64³, 36 directions, 6 levels | 18.6 M rays per build; 1,792 MiB per atlas, 3,584 MiB for both | [tmpvar](3d_world_space_implementations_grids.md#tmpvars-radiance-cascades-3d-grid) |
| rbnelr voxel_game | | 2D slice module, 7 cascades | about 145 MB of RGBA16F, 18 M rays per frame | [voxel_game](3d_world_space_implementations_grids.md#rbnelrvoxel_game) |
| Surfel RC (Coppen) | Radeon 890M; RTX 4070 Mobile | 6 cascades, resolution not stated | surfel upkeep 2.45 ms on the 890M, 0.82 ms on the 4070 (derived sums); README profile gather 5.35 ms, merge 2.04 ms; 423 MiB; 25.2 M rays with every slot alive | [surfel RC](3d_surface_probes.md#performance) |
| Spatium (Blackline Interactive), 2026-09-12 | Radeon Pro 5500M, Metal, compute BVH | surface atlas of 1024² (inferred), 3 cascades, 2.04 M rays per frame in Sponza and 2.55 M in Sponza 4K; video HUD | Sponza passes 35.06 ms: cascades 4.55, 10.05 and 10.24, camera 3.72, irradiance filter 2.62, direct 1.65, gbuffer 0.96, gather 0.59, seams 0.37, present 0.32; Sponza 4K 56.30 ms (cascades 7.28, 13.80, 13.72; camera 9.68) | [surface atlas](3d_surface_probes.md#a-generated-surface-atlas-blackline-interactive) |
| Spatium, 2026-10-03 | same | 5 to 6 cascades, 4.11 to 6.15 M rays per frame, native resolution; ranges from several HUD frames | GI 12.6 ms pillar room, 12.1 ms Cornell box, 11.4 to 18 ms Sponza, 15.9 to 27.8 ms Intel Sponza with 10.8 M triangles; 722 MB to 3.7 GB of VRAM | [surface atlas](3d_surface_probes.md#a-generated-surface-atlas-blackline-interactive) |
| Love and Deepspace | iPhone 12 | surfels in a hash grid, gather at about 70% resolution | about 2 ms of GI; full-resolution gather alone 2.8 ms; a simplified ReSTIR version 3.2 ms | [Love and Deepspace](3d_surface_probes.md#gather-and-timing) |
| yhyu13 surface charts | RTX 2080 SUPER, OpenGL | Cornell box on 8 UV charts, 6 cascades, RenderDoc replay | 28.6 ms on the full atlases, 5.95 ms after skipping padding; replay varies 2 to 5×; 100.7 MB | [surface charts](3d_surface_probes.md#yhyu13-surface-chart-rc) |
| X3XfRM | | six 1280×256 RGBA16F chart layers | 15.7 MB | [X3XfRM](3d_surface_probes.md#x3xfrm-mathis) |
| Radiance field on a plane | not stated | stored cascades on one plane | under 0.5 ms, constant per pixel | [plane](3d_surface_probes.md#a-radiance-field-stored-on-a-plane) |
| anoptic-engine | unnamed GPU | one frame, mode unrecorded | 3.80 ms | [anoptic-engine](3d_world_space_implementations.md#anoptic-engine) |

Scaled to 1080p by pixel count (derived, valid only for the screen-probe part): creikey's 0.76 ms becomes 6.8 ms and its final build 18.9 ms; EggyStudio's Low and High become 3.4 and 5.8 ms. Both are below a single-frame budget only at Low settings, and both report GPUs they do not name.

## Volumetric and HRC

| Project | Hardware | Setup | Result | Owner |
|---|---|---|---|---|
| DexRT | RTX 4070 | 512×768 prominence model, 880 wavelengths | 95 s to 11.8 s per iteration (8×): mips 3.5×, sparsity 1.5× on a half-empty model; mips cost 1.33× the base level in 2D and 1.14× in 3D | [DexRT](volumetric_and_radiative_transfer.md#dexrt) |
| Rulkens, medical volumes | RTX 4080 Laptop (12 GB), i9-13900HX | 192³, cube and tetrahedron direction mappers, four data sets | 17.65 to 33.89 ms per recalculation; the cube mapper costs 1.38 to 1.47× the tetrahedron; Exposure Renderer needs about 2 s to settle | [Rulkens](volumetric_and_radiative_transfer.md#rc-for-medical-volumes-rulkens) |
| CT volume RC (repository) | laptop RTX 4080 | dense 192³, 5 cascades | 20 to 34 ms per full recalculation; 627.8 MiB of cascades, about 1.5 GB allocated | [CT volumes](volumetric_and_radiative_transfer.md#rc-for-ct-volumes-repository) |
| HRC paper | RTX 3080 Laptop | 256² to 2048², fp16 | 0.55, 1.85, 7.67, 33.9 ms; a 52 spp path tracer took 98.6 ms at 1024² with 10× the error | [HRC](holographic_rc.md#measured-results-and-the-cost-model) |
| Volumetric-HRC | RTX 3080; GTX 970 | 256² to 4096² | about 1, 1 to 2, 5 to 6, 9 to 11, 35 to 45 ms (README); 2.61 ms at 1024² and 0.75 ms at 512² on a GTX 970 (community); out of memory at 8192² | [Volumetric-HRC](holographic_rc_implementations.md#volumetric-hrc) |
| TypeGPU holographic runner | | 256² to 2048² | 9, 38, 160, 672 MiB logical allocation (derived) | [TypeGPU](holographic_rc_implementations.md#buffers-and-memory) |
| pixi-GI | Apple M1 Pro, ANGLE-Metal | 256² and 512² buffers | HRC 3.0 ms and 8.5 to 10.4 ms | [pixi-GI](holographic_rc_implementations.md#pixi-gi) |

## Godot

| Project | Hardware | Setup | Result | Owner |
|---|---|---|---|---|
| gomezzz, world-space 3D RC | RTX 4060 Ti, Godot 4.7 | 72,012 triangles, software BVH, 1080p with 2× MSAA | whole-frame median 6.24 ms, capped by VSync; 2,342,912 traced segments per update; CPU BVH build about 1.22 s; 8.94 MiB of directions plus 0.84 MiB of atlases; an expanded scene at QHD took a 33.77 ms median | [gomezzz](godot_projects.md#measurements) |
| HDDAGI against SDFGI | GTX 1650 | light update and probe tracing, still camera | 0.93 against 2.43 ms (2.6×); the GI demo at 4K ran at 120 FPS on an RTX 3080 with the screen-probe branch | [HDDAGI](godot_integration.md#hddagi) |
| Godot's AO passes | RTX 2070 | SSAO and related passes | 0.7 to 1.45 ms, the budget a screen-space RC layer competes with | [Godot projects](godot_projects.md#connections) |
| 2D direction-first RC in Godot | RTX 2070 Super | 3440×1440, probes every 2 px | about 4.5 ms | [above](#community-2d-timings) |
| Godot luminance-only HRC | RTX 3090 | 1080p | 7.57 ms, 5.10 ms with caching | [HRC](holographic_rc.md#performance) |

gomezzz's figure is the only measured `RenderingDevice` 3D tracer: 2.34 M segments inside a 6.24 ms frame, raster included, is a floor of 0.375 G segments per second ([derived points](godot_projects.md#derived-points)).

## Related techniques

| Technique | Hardware | Result | Owner |
|---|---|---|---|
| DDGI | RTX 2080 Ti | 32×8×32 probes, 64 rays, 8×8 maps: trace 0.8, shade 0.4, update 0.7, sample 0.5, 2.6 ms in all; above 1.5 G rays/s; sleeping probes save 30 to 50% of the update; equal-noise single-frame DDGI needs about 34 M rays, about 23 ms | [DDGI](related_probe_gi.md#ddgi) |
| DDGI resampling | not stated | at equal error, 21.81 ms over 1.33 frames on average against 17,000 ms over 804.5 frames for a path tracer with ReSTIR | [resampling](related_probe_gi.md#ddgi-resampling) |
| Light-field probes | GeForce 1080 | Living Room 4.7 ms in all; ray-cast indirect 13 ms against 0.2 ms for prefiltered visibility | [light-field probes](related_probe_gi.md#light-field-probes) |
| Enshrouded | all targets including Steam Deck | fixed budgets of 100k, 250k or 500k rays per frame; 16 rays per stable probe | [Enshrouded](related_probe_gi.md#enshrouded) |
| Light propagation volumes | GTX 285, Xbox 360, PS3 | 3.4 to 4.2 ms in all, propagation 0.7 to 1.5 ms | [LPV](related_probe_gi.md#light-propagation-volumes) |
| Voxel cone tracing | GTX 480; GTX 1070 | 22.0 ms at 1024×768 with three diffuse and one specular cone (2011); 170 to 214 fps at 720p with per-frame voxelization (GTX 1070) | [VCT](related_probe_gi.md#voxel-cone-tracing) |
| Lumen | PS5; RTX 2080 Ti | 1080p with TSR to 4K, GI and reflections: 2.77 to 4.63 ms (Land of Nanite, software), 4.29 to 8.70 ms (Lyra), 6.38 to 11.31 ms (The Matrix Awakens, hardware); 7.25 ms (Lake House, RTX 2080 Ti); final gather trace 1.04 M rays in 1.07 ms; budgets 4 ms at 60 fps, 8 ms at 30 fps | [Lumen](related_engine_gi.md#timings) |
| Brixelizer GI | RX 7900 XTX, RTX 4080, RX 7600 XT | about 2 ms at 4K on the 7900 XTX, 2.2 ms on the 4080, 1.7 ms at 1080p on the 7600 XT; 128 MiB brick atlas, 110 to 500 MB in all | [Brixelizer GI](related_engine_gi.md#brixelizer-gi) |
| daGI (Enlisted, 2019) | GTX 1070; Xbox One | 0.57 ms on the 1070; 0.7 ms with one bounce or async, about 1.6 ms synchronous multi-bounce on Xbox One; about 31 MB | [daGI v1](related_engine_gi.md#dagi-v1-in-enlisted-2019) |
| HSGI | iPhone 13 Pro; RTX 3080 | mobile 3.18 ms per frame plus 1.79 ms on clipmap shifts; PC at 4K with TSR 8.53 ms of GI against Lumen's 9.63 ms, with diffuse denoising 2.65 ms against 0.64 ms of tracing | [HSGI](related_engine_gi.md#hsgi) |
| GI-1.0 | RX 6900 XT, RTX 3080 | 1.9 to 3.1 ms at 1080p; 2.4 ms against Lumen's 2.6 ms in one UE5 scene | [GI-1.0](related_radiance_caches.md#gi-10) |
| On-surface caches | RTX 3090 Ti | 1.45 to 2.64 ms at 1080p against 1.78 to 2.56 ms for GI-1.0; 300 to 700 MB per viewer | [on-surface caches](3d_surface_probes.md#on-surface-radiance-caches-tatzgern-et-al-2024) |
| SHaRC | | 2²² hash entries, 160 MiB, of which a still camera uses 10 to 20% | [SHaRC](related_radiance_caches.md#sharc) |
| kajiya | RX 6800 XT, hardware RT | 1080p frame 8.4 ms: indirect diffuse 2.3 ms, irradiance cache 0.55 ms, reflections 2.2 ms | [kajiya](related_radiance_caches.md#kajiya) |
| Bevy Solari | RTX 3080 | 8.2 to 14.5 ms at 1600×900 including 5.8 to 6.3 ms of DLSS Ray Reconstruction | [Solari](related_radiance_caches.md#bevy-solari) |
| PICA PICA surfels | Turing | at least 0.71 G rays/s with shading | [PICA PICA](related_radiance_caches.md#pica-pica-ray-tracing-gems-chapter-25) |
| RCPG | RTX 3090 | 1080p at 1 spp: 3.04 to 6.60 ms with one bounce, of which RC trace 0.63 to 1.67 ms; 4.97 to 8.94 ms with two bounces; with ReSTIR 12.43 to 22.80 ms per frame | [RCPG](rc_for_sampling_and_guiding_rcpg.md#evaluation) |
| Visibility-bitmask SSGI | RTX 2080 | 1.23 to 4.33 ms at 1080p including a 0.33 ms denoise | [bitmask SSGI](related_screen_space_gi.md#visibility-bitmask-ssgi) |
| Screen-space ray tracing | GeForce Titan; GeForce 650M | 25 steps per pixel at 1080p: 1.2 ms and 6.4 ms, about 43 and 8 G steps per second (derived) | [McGuire and Mara](scene_representation_and_tracing.md#mcguire-and-maras-perspective-correct-dda) |
| Line sweeping | not stated | 1000 directions at 1080p in 40 ms | [line sweeping](light_transport_alternatives.md#line-sweeping) |

## GPU building blocks

Primitives a sparse or sorted single-frame RC needs, with their measured cost ([building blocks](3d_world_space.md#gpu-building-blocks), [hash maps](3d_world_space.md#hash-maps-for-probes)):

| Operation | Hardware | Result |
|---|---|---|
| Radix-sorting 1M 32-bit keys | RX 9070 XT; RTX 4080; laptop RTX 3060; GTX 1650 (WebGPU) | 0.16, 0.21, over 1 and 2.84 ms |
| Sorting 10M deduplicated texels | not stated | about 1.5 ms |
| Hash-map filling for probes | not stated; laptop RTX 3060 | 0.1 ms; 0.4 ms for a 2²¹ table |
| Hashing 1080p probes with deduplication | not stated | 0.3 ms; hashing at 2×2 downscale 4× faster |
| Initializing all cascades | not stated | 0.155 ms |
| Surfel RC hash counting, prefix sum and insertion | Radeon 890M; RTX 4070 Mobile | 0.25, 0.2 and 1.0 ms; 0.10, 0.15 and 0.19 ms |
| Simple lock-free hash table, 4M-key insert batch | not stated | 11.6 ms at load 0 to 14.7 ms at 0.5, 105.7 ms at 0.9 and 240.2 ms at 0.94 |
| cuco static map, 2²⁷ pairs at 50% load | H100 | insert 87.5 GB/s, find 134.6 GB/s |
| Random 64-bit reads (GUPS) | Xeon 8360Y; A100; H100 | 15 of 204, 141 of 2039 and 256 of 3352 GB/s peak |
| Jump flood at 512×256 | RTX 2080 Super | about 10 µs |

- Random 64-bit reads reach 6.9 to 7.6% of peak bandwidth on all three machines (derived). A hashed probe lookup is a random read, so each one costs about 13× the bandwidth of streaming the same bytes; caching each probe's 8 parent indices once (0.2 ms in one build) replaces repeated hash lookups in the merge ([hash maps](3d_world_space.md#hash-maps-for-probes)) (inference).
- Open-addressing tables stay nearly flat up to half load and degrade 7 to 9× by 0.9, so a probe table sized at twice the expected probe count costs little; a 2²¹ table is 8 to 24 MiB depending on payload (derived from the batch timings and entry sizes).

## Normalized throughput (derived)

Rays per second divide a ray or segment count by the time of the pass that traced it. The passes differ, so the "time covers" column says what each rate includes; a rate over a whole frame or a whole RC pass is a floor on the tracer's own speed.

| Tracer class | Code | Hardware | Rays | Time covers | G rays/s |
|---|---|---|---|---|---|
| Hardware RT | Dell'Ova, spacing 1, 5 cascades | RTX 3080, DXR | 165.9 M | gather pass, 23.65 ms | 7.0 |
| Hardware RT | Dell'Ova, spacing 4, 5 cascades | RTX 3080, DXR | 10.4 M | gather pass, 1.71 ms | 6.1 |
| Hardware RT | Dell'Ova, 8 cascades | RTX 3080, DXR | | gather pass | about 8.2 |
| Hardware RT | Kaméus, one probe per pixel | RTX 2070, ray queries | 33.6 M per cascade | one cascade, about 10 ms (Nsight) | 3.4; 4.5 with min and max probes |
| Hardware RT | DDGI | RTX 2080 Ti | 524,288 | probe trace, 0.8 ms; above 1.5 stated for the frame | 0.66 to 1.66 |
| Hardware RT | erhe | not stated | 1 M | trace, 0.7 ms | 1.43 |
| Compute BVH | tinybvh | RTX 5080 Laptop, no RT cores | | primary rays, Sponza | 2.8 to 3 nearest hit, 4 any hit |
| Compute BVH | tinybvh | RX 5700 XT | | primary rays | about 1.1 |
| Compute BVH | Surfel RC gather | not stated | 25.2 M at most | gather pass, 5.35 ms | at most 4.7 |
| Compute BVH | Blackline's Spatium, 2026-10-03 | Radeon Pro 5500M, Metal | 4.11 to 6.15 M | HUD GI time, 11.4 to 27.8 ms | 0.22 to 0.43 |
| Compute BVH | Blackline's Spatium, 2026-09-12 | Radeon Pro 5500M, Metal | 2.04 and 2.55 M | three cascade passes, 24.8 and 34.8 ms | 0.082 and 0.073 |
| Voxel DDA | 3D DDA over 4×4×4 bit cubes | not stated | 15 M | trace, about 5 ms | 3.0 |
| Voxel DDA | creikey clipmap | not stated, D3D11 | 1,884,160 | trace, 0.49 to 0.52 ms | 3.6 to 3.9 |
| Distance fields | Lumen final gather | PS5 | 1.04 M | trace pass, 1.07 ms | 0.97 |
| Depth march | Kung, SPS 1 | RTX 3060 | 88.5 M | whole RC, 70 to 294 ms | 0.30 to 1.26 |
| Compute (Metal RT on M1) | Gavras, small scenes | M1 | 12.4 M | whole RC, 33 to 40 ms | 0.31 to 0.38 |
| Compute (Metal RT on M1) | Gavras, Sponza | M1 | 12.4 M | whole RC, 144 to 156 ms | 0.08 to 0.09 |
| Compute BVH, Godot | gomezzz | RTX 4060 Ti | 2.34 M segments | whole frame with raster, VSync-capped | at least 0.375 |
| Hardware RT (DDGI in erhe) | erhe's DDGI | not stated | 1 M | trace, about 6 ms | about 0.17 |
| Surfels | PICA PICA | Turing | | with shading | at least 0.71 |
| 2D | 2D DDA over 8×8 bit planes | not stated | 11 M | trace, 1.2 ms | 9.2 |
| 2D | IceKontroI Star and Confetti Dense | RTX 2080 Ti | 13.3 M | whole RC, 1.77 and 4.89 ms | 7.5 and 2.7 |
| Synthetic, outlier | creikey synthetic voxel trace | not stated; WebGPU | | benchmark | 14.3; 2.8 in WebGPU |

The screen-space rows are derived in detail in [3D screen space](3d_screen_space.md#ray-throughput-across-the-measured-spwi-codes-derived).

- **Three classes.** Hardware RT on short coherent RC rays runs at 6 to 8.2 G rays/s on an RTX 3080. Compute BVHs and voxel DDA run at 2.8 to 3.9 G rays/s on current GPUs. Software traversal of a complex scene on a weak GPU (Gavras on the M1, Blackline on a 2019 Radeon Pro 5500M) falls to 0.08 to 0.43 G rays/s. The 2D and synthetic rates above 9 G rays/s come from rays a few texels long and say nothing about 3D.
- **The compute class is the one that applies to hosts without ray queries.** Godot's `RenderingDevice` compute shaders cannot issue ray queries, so a tracer there is a compute BVH, voxel DDA or distance-field march. Its shaders are SPIR-V modules dispatched with `vkCmdDispatch` like any Vulkan compute work (`drivers/vulkan/rendering_device_driver_vulkan.cpp:4418, 6700-6703, 6741` at 4.7.2-stable), so a kernel runs there at the rate the same SPIR-V reaches in any Vulkan host on that GPU, the compute class (inference from the engine source). The budgets below take this class at 1 to 3 G rays/s, at and below the measured 2.8 to 3.9 G rays/s; gomezzz's floor of 0.375 G segments/s is a frame-capped lower bound, not the tracer's speed.
- **Rates fall with ray length and scene complexity, not with the method.** Kung's same ray count ran 4.2× slower outdoors than indoors; Gavras's ran 4.4× slower in Sponza than with cubes; Dell'Ova's hardware rate held across spacing. Upper cascades, whose rays are longest, are where a compute tracer loses the most, which is what mip marching (3.5× in DexRT) and coarser scene levels per cascade address.
- **Hardware RT is not uniformly faster at RC's ray lengths.** erhe's hardware path ran 1.43 G rays/s on unstated hardware, below the compute DDA rows, and Brixelizer beat DXR on short rays; hardware RT's advantage is largest on long incoherent rays through complex geometry ([tracing](scene_representation_and_tracing_voxels_and_bvhs.md#software-against-hardware)) (inference).

### Time per megapixel (derived)

RC time divided by output megapixels, for comparing screen-anchored designs across resolutions. Rays per pixel differ by design, so the column says what was traced.

| Code | Hardware | Traced | ms per megapixel |
|---|---|---|---|
| Peter, 2D, 720p to 4K | RX 7900 XTX | one probe per pixel, 4 rays, SDF | 0.79 to 0.96 |
| IceKontroI, 2D, 1080p | RTX 2080 Ti | dense, Star and Confetti scenes | 0.85 and 2.36 |
| GM Shaders, 2D | RTX 3080 | 4 probes per pixel; position-first and direction-first | 28.5 and 12.5 |
| HRC paper, 2D | RTX 3080 Laptop | 1024² and 2048² | 7.3 and 8.1 |
| Volumetric-HRC, 2D | RTX 3080 | 1024², community figure | 2.5 |
| Godot luminance HRC, 2D | RTX 3090 | 1080p | 3.7 |
| PoE2, 3D screen space | RTX 4090 | 4K, High, depth-buffer march | 0.1 |
| Dell'Ova, 3D | RTX 3080, DXR | spacing 4, 16 rays, 8 cascades, 1080p and 1440p | 1.1 |
| Dell'Ova, 3D | RTX 3080, DXR | spacing 2, 16 rays, 8 cascades, 1080p | 4.2 |
| Alpha-Renderer, 3D | RTX 3070 | 2 px probes, 4 directions, 6 cascades | 2.7 |
| Kaméus, 3D | RTX 2070 | 4×4 tiles, one or min and max probes | 4.6 to 6.4 |
| Kung, 3D | RTX 3060 | probe every 4th pixel, depth march | 5.3 to 32.6 |
| Gavras, 3D | M1 | 6 cascades, small scenes to Sponza | 15.8 to 75.2 |
| EggyStudio, 3D | laptop GPU | Low to High | 1.6 to 2.8 |
| creikey, 3D | not stated | screen probes over a voxel clipmap | 3.3 |

- 2D with one probe per pixel and hardware RT 3D at spacing 4 land near 1 ms per megapixel; that is the cost floor a well-built pipeline reaches with a fast tracer (inference).
- The position-first GM Shaders build is 2.3× slower than its direction-first build per megapixel, the same direction-first advantage the layout topic explains through merge reads ([layout](cascade_layout_and_merging.md#position-first-and-direction-first)).

### Memory per unit (derived)

| Code | Unit | Bytes per unit |
|---|---|---|
| Dell'Ova, 1080p, spacing 4, 16 rays, 8 cascades | pixel | 16.4 |
| Dell'Ova, 1080p, spacing 1, 64 rays, 8 cascades | pixel | 974 |
| EggyStudio High, 800×450 | pixel | 25.4 |
| Alpha-Renderer, 1080p | pixel | 38.6 |
| Peixoto, 2D, 1080p cascades | pixel | 85.3 |
| creikey clipmap, 4×64³ | cell | 12 |
| gomezzz | base probe | 1,017 |
| tmpvar 3D grid, payload | base probe | 1,134 |
| Coppen surfel RC, 262,144 cascade 0 probes | base probe | 1,693 |
| erhe, 65,536 probes | base probe | 4,608 |
| tmpvar 3D grid, allocated | base probe | 7,168 |
| jumeder, 32³ | base probe | 30,720 |

A world grid that keeps ×4 directions and ⅛ probes per cascade halves its texels each cascade, so its storage per base probe is `bytes_per_texel · D₀ · Σ(½)ᶜ`, just under `2 · bytes_per_texel · D₀` ([memory by domain](core_theory.md#memory-by-domain)). Against that model:

| Code | Texel | D₀ | Cascades | Model | Measured | Ratio |
|---|---|---|---|---|---|---|
| gomezzz | vec4 fp32, 16 B | 32 | 5 | 992 B | 1,017 B | 1.03 |
| tmpvar 3D grid, payload | RGBA32F, 16 B | 36 | 6 | 1,134 B | 1,134 B | 1.00 |
| tmpvar 3D grid, allocated | RGBA32F, 16 B | 36 | 6 | 1,134 B | 7,168 B | 6.32 |
| jumeder | RGBA16F, 8 B | 2048 | 4 | 30,720 B | 30,720 B | 1.00 |
| erhe | RGBA16F, 8 B | 64 | 8 | 1,020 B | 4,608 B | 4.52 |

- Three independent codes match the model exactly or within 3%, which confirms the 3D grid law in practice.
- The gaps are layout choices, not the method: tmpvar pads every level to a 4096² array layer (6.3×), and erhe keeps raw and merged atlases (128 MiB), a 4× merged copy of cascade 0 (96 MiB) and a distance atlas (64 MiB), 4.5× the minimum ([erhe](3d_world_space_implementations.md#layout)).
- Screen designs cost bytes per pixel instead: 16 to 39 B per pixel at practical settings, so a 1080p screen layer fits in 34 to 80 MB.

## Budgets for single-frame 3D RC (derived)

Rays per frame follow from each family's layout, and time from a tracer rate. The models: screen probes keep cascade 0's ray count in every cascade (probes ÷4, directions ×4), so rays are `pixels/spacing² · rays₀ · cascades`; a splitting design traces about one ray per pixel per ray-per-pixel setting; a dense world grid halves its rays each cascade, `N³ · D₀ · Σ(½)ᶜ`. Rates span the classes above: 0.3 G rays/s (software on weak GPUs), 1 and 3 G rays/s (compute BVH or DDA), 7 G rays/s (hardware RT).

**Screen probes, 16 rays at cascade 0, 6 cascades.**

| Resolution | Spacing | Rays per frame | 0.3 G/s | 1 G/s | 3 G/s | 7 G/s |
|---|---|---|---|---|---|---|
| 1080p | 2 px | 49.8 M | 165.9 ms | 49.8 ms | 16.6 ms | 7.1 ms |
| 1080p | 4 px | 12.4 M | 41.5 ms | 12.4 ms | 4.1 ms | 1.8 ms |
| 1080p | 8 px | 3.1 M | 10.4 ms | 3.1 ms | 1.0 ms | 0.4 ms |
| 1440p | 2 px | 88.5 M | 294.9 ms | 88.5 ms | 29.5 ms | 12.6 ms |
| 1440p | 4 px | 22.1 M | 73.7 ms | 22.1 ms | 7.4 ms | 3.2 ms |
| 1440p | 8 px | 5.5 M | 18.4 ms | 5.5 ms | 1.8 ms | 0.8 ms |
| 4K | 2 px | 199.1 M | 663.6 ms | 199.1 ms | 66.4 ms | 28.4 ms |
| 4K | 4 px | 49.8 M | 165.9 ms | 49.8 ms | 16.6 ms | 7.1 ms |
| 4K | 8 px | 12.4 M | 41.5 ms | 12.4 ms | 4.1 ms | 1.8 ms |

**Ray splitting, rays per pixel.**

| Resolution | Rays per pixel | Rays per frame | 0.3 G/s | 1 G/s | 3 G/s | 7 G/s |
|---|---|---|---|---|---|---|
| 1080p | 1 | 2.07 M | 6.91 ms | 2.07 ms | 0.69 ms | 0.30 ms |
| 1080p | 2 | 4.15 M | 13.82 ms | 4.15 ms | 1.38 ms | 0.59 ms |
| 1080p | 4 | 8.29 M | 27.65 ms | 8.29 ms | 2.76 ms | 1.18 ms |
| 1440p | 1 | 3.69 M | 12.29 ms | 3.69 ms | 1.23 ms | 0.53 ms |
| 1440p | 2 | 7.37 M | 24.58 ms | 7.37 ms | 2.46 ms | 1.05 ms |
| 1440p | 4 | 14.75 M | 49.15 ms | 14.75 ms | 4.92 ms | 2.11 ms |
| 4K | 1 | 8.29 M | 27.65 ms | 8.29 ms | 2.76 ms | 1.18 ms |
| 4K | 2 | 16.59 M | 55.30 ms | 16.59 ms | 5.53 ms | 2.37 ms |
| 4K | 4 | 33.18 M | 110.59 ms | 33.18 ms | 11.06 ms | 4.74 ms |

**Dense world grid, 32 directions at cascade 0, 5 cascades.**

| Grid | Rays per frame | 0.3 G/s | 1 G/s | 3 G/s | 7 G/s |
|---|---|---|---|---|---|
| 32³ | 2.0 M | 6.8 ms | 2.0 ms | 0.7 ms | 0.3 ms |
| 64³ | 16.3 M | 54.2 ms | 16.3 ms | 5.4 ms | 2.3 ms |
| 128³ | 130.0 M | 433.4 ms | 130.0 ms | 43.3 ms | 18.6 ms |

**Rays a budget buys.**

| Rate | 4 ms | 8 ms |
|---|---|---|
| 0.3 G/s | 1.2 M | 2.4 M |
| 1 G/s | 4.0 M | 8.0 M |
| 3 G/s | 12.0 M | 24.0 M |
| 7 G/s | 28.0 M | 56.0 M |

**Memory in RGBA16F (8 bytes per texel).** Screen probes store 16 texels per probe per cascade; "two live" keeps only the cascade being merged and its parent, the peak of a fused top-down pass ([tracing and merging order](cascade_layout_and_merging.md#tracing-and-merging-order)). Pre-averaged storage keeps cascade 0 whole and stores the cascades above it at a quarter: 1080p at 4 px drops from 95 to 35.6 MiB for six cascades, the order of Dell'Ova's 34 MB.

| Layout | Per cascade | All cascades | Two live |
|---|---|---|---|
| 1080p, 2 px | 63.3 MiB | 380 MiB (6) | 127 MiB |
| 1080p, 4 px | 15.8 MiB | 95 MiB (6) | 32 MiB |
| 1080p, 8 px | 4.0 MiB | 24 MiB (6) | 8 MiB |
| 1440p, 2 px | 112.5 MiB | 675 MiB (6) | 225 MiB |
| 1440p, 4 px | 28.1 MiB | 169 MiB (6) | 56 MiB |
| 1440p, 8 px | 7.0 MiB | 42 MiB (6) | 14 MiB |
| 4K, 2 px | 253.1 MiB | 1519 MiB (6) | 506 MiB |
| 4K, 4 px | 63.3 MiB | 380 MiB (6) | 127 MiB |
| 4K, 8 px | 15.8 MiB | 95 MiB (6) | 32 MiB |
| Dense 32³ | 8 MiB at cascade 0 | 16 MiB (5) | |
| Dense 64³ | 64 MiB at cascade 0 | 124 MiB (5) | |
| Dense 128³ | 512 MiB at cascade 0 | 992 MiB (5) | |

Vulkan guarantees only 128 MiB per storage buffer, so dense 64³ cascade stacks and 1080p screen cascades at 2 px spacing already need splitting across buffers or images ([RenderingDevice notes](../../docs/rendering_device.md)).

**Reference budgets.** Lumen holds GI and reflections to 4 ms at 60 fps and 8 ms at 30 fps on PS5; HDDAGI's light update and probe trace take 0.93 ms on a GTX 1650; Godot's AO passes take 0.7 to 1.45 ms on an RTX 2070; Brixelizer GI takes about 2 ms at 4K on high-end GPUs; GI-1.0 takes 1.9 to 3.1 ms at 1080p. Enshrouded caps its probes at 100k to 500k rays per frame, which at 1 G rays/s is 0.1 to 0.5 ms.

What the tables imply at 1080p with a 4 ms budget:

- A compute tracer at 1 to 3 G rays/s buys 4 to 12 M rays. That covers screen probes at 8 px (3.1 M rays) or 4 px (12.4 M, at the top of the band), or 2 to 6 rays per pixel of splitting, plus a 32³ to 64³ world grid only at the high rate. A dense 128³ grid at 130 M rays is out of reach at any rate.
- Hardware RT at 7 G rays/s would buy 28 M rays. A compute tracer, the only kind under Godot's `RenderingDevice`, stays in the 1 to 3 G rays/s band.
- At 4K the same layouts cost 4× the rays; holding the budget there means 8 px probes or output upscaling, as PoE2's quarter-resolution and the community's quarter-resolution 2D builds do.

## Connections

- **One rule, many confirmations.** `rays₀/spacing²` holds in Dell'Ova's DXR runs, Kung's depth march and creikey's voxel trace; pixel-count scaling holds in Dell'Ova and Peter; the 3D grid storage law holds to within 3% in gomezzz, tmpvar and jumeder. The method's cost is predictable before it is built, which is what the budget tables rely on.
- **Cost moves to wherever the data is random.** Dense layouts spend their time tracing; sparse layouts spend it on hashing, deposits and interpolation (Split RC's deposit over its trace, a sparse build's trilinear gather at 27 ms of a 37.5 ms frame, a software-RT prototype at 50% hash insertion). Random reads run at about 7% of peak bandwidth, so the bookkeeping of a sparse design is bandwidth spent at a thirteenth of the rate (inference from the GUPS figures).
- **Bandwidth is the shared bottleneck.** Format size moved 2D frame rates 3×, the atlas copy outgrew pixel count, HRC is bandwidth bound, and Vasiou et al. find memory dominating ray tracing time and energy ([where tracing time goes](scene_representation_and_tracing.md#where-tracing-time-goes)). Pre-averaging, R11G11B10F and RGB9E5 storage and fused top-down merging are the same lever applied at different stages.
- **The fastest measured RC runs are the coarsest.** PoE2's 0.1 ms per megapixel comes from a top-down camera and coarse cascades, Love and Deepspace's 2 ms on a phone from a reduced-resolution gather with tracing spread over frames, and the quarter-resolution 2D builds cut 200 ms to 15.6 ms. Trace resolution is the strongest single lever in every domain.
- **Amortized systems look cheap per frame because time carries the rays.** DDGI's 2.6 ms becomes about 23 ms of tracing at equal noise without history, and HSGI and daGI2 would need 9 to 121× their budgets updated in full. RC's merge gives every pixel the rays of all cascades at once, which is why single-frame RC rows sit in the same 2 to 12 ms band as these amortized systems despite tracing everything each frame.

## Single-frame assessment

For single-frame 3D RC (inference, from the sections above):

- Single-frame 3D RC has run within real-time budgets: Split RC at 8.6 and 11.5 ms on a laptop RTX 3080 with hardware RT, Sannikov's sparse RC at 60 to 100 fps, Dell'Ova at 1.94 to 2.36 ms for spacing 4, Abou Dan and Jensen at 2 to 6 ms on their lower settings, and voxel2026 at 1.98 ms in a voxel world. Each traces with hardware RT, a voxel world or the depth buffer; none uses a compute triangle tracer.
- A compute tracer, as under Godot's `RenderingDevice`, is taken at 1 to 3 G rays/s, at and below the 2.8 to 3.9 G rays/s measured for compute BVHs and voxel DDA. At 1080p in 4 ms that is 4 to 12 M rays: screen probes at 4 to 8 px with 16 cascade 0 rays, or a splitting design at 2 to 6 rays per pixel, with a small world grid only for far field.
- Memory is not the constraint for screen-anchored or sparse designs (tens of MiB at 1080p), but dense grids above 64³ are, and Vulkan's 128 MiB storage-buffer guarantee bounds any single allocation.
- The upper cascades' long rays are where a compute tracer loses most; coarser scene levels per cascade (mips, clipmap levels) are the measured fix, and a design needs them from the start.
- Sparse designs must budget their bookkeeping at random-access bandwidth: Split RC's non-trace stages took 7.0 to 7.3 ms of its frame, more than its trace on both scenes.
