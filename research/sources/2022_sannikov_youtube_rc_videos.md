# Alexander Sannikov's radiance cascades videos

| | |
|---|---|
| Author | Alexander Sannikov |
| Kind | short videos; most have music only, so the descriptions carry the content |
| Link | https://www.youtube.com/@Alexander_Sannikov |

The channel shows radiance cascades (RC) from the first 2D tests in 2022 to sparse 3D versions in 2025 and 2026. Only two videos have spoken explanations: "Radiance Cascades Rendered Directly" and the paper announcement.

| Title | Uploaded | ID |
|---|---|---|
| Screen Space Global Illumination | 2017-06-01 | VOg_8ipCZLA |
| Global illumination in screenspace: 80fps, noise-free, no reprojection | 2018-07-19 | OPFvcsQAKjc |
| 2d Full Global Illumination #1 (proof of concept, no denoising, interactive fps) | 2022-08-25 | eS0zd_8nfhk |
| 2d Full Global Illumination #2 (working principle and perf tests) | 2022-08-28 | o2kgW2TBpUo |
| Hierarchal radiance cascades GI experiment | 2022-10-28 | 5Ua-h1pg6yM |
| Single shot global illumination with no denoiser | 2023-04-19 | N6RP3r1M9g4 |
| Radiance Cascades Rendered Directly | 2023-08-19 | xkJ6i2N32Pc |
| Announcement for graphics programming enthusiasts! | 2023-08-22 | vlF1CX8X5Bc |
| Exploring 3d holographic radiance cascades | 2025-09-02 | xT_7JtYXdNc |
| Sparse 3d Radiance Cascades | 2025-11-02 | TGLAxW0xVDU |
| Sparse Radiance Cascades: goodbye screenspace | 2025-12-25 | rG2aok2SdbU |
| Polygonal Radiance Cascades | 2026-02-28 | AhbnwZFp5iE |
| Testing polygonal block RC layout (no description, not in the channel's video list) | 2026-03-15 | JcWFXYnYC5M |

## Contents

- [Earlier screen-space GI (2017–2018)](#earlier-screen-space-gi-20172018)
- [2D GI #1 and #2 (2022)](#2d-gi-1-and-2-2022)
- [Hierarchal radiance cascades GI experiment (2022)](#hierarchal-radiance-cascades-gi-experiment-2022)
- [Single shot global illumination with no denoiser (2023)](#single-shot-global-illumination-with-no-denoiser-2023)
- [Radiance Cascades Rendered Directly (2023)](#radiance-cascades-rendered-directly-2023)
- [Announcement for graphics programming enthusiasts! (2023)](#announcement-for-graphics-programming-enthusiasts-2023)
- [Exploring 3d holographic radiance cascades (2025)](#exploring-3d-holographic-radiance-cascades-2025)
- [Sparse 3d Radiance Cascades (2025)](#sparse-3d-radiance-cascades-2025)
- [Sparse Radiance Cascades: goodbye screenspace (2025)](#sparse-radiance-cascades-goodbye-screenspace-2025)
- [Polygonal Radiance Cascades (2026)](#polygonal-radiance-cascades-2026)
- [Testing polygonal block RC layout (2026)](#testing-polygonal-block-rc-layout-2026)
- [Interview at ExileCon 2023](#interview-at-exilecon-2023)
- [Other channel videos](#other-channel-videos)

## Earlier screen-space GI (2017–2018)

These videos show the screen-space GI that came before RC. A later video says a hierarchical version of it shipped in Path of Exile.

- 2017: a pure post process with no extra passes and no stored data. It integrates GI semi-analytically from horizon levels, like HBAO, and produces HBAO as a by-product. Near-field GI is very accurate; thin distant occluders can be missed. About 50 fps at full resolution on a GTX 850M laptop. It targets the second bounce and uses the HBAO term as an approximate third; with complete screen data (no hidden occluders or off-screen lights) it converges to the path-traced result, and it leans on spatial and temporal coherence, which shows as artifacts under fast motion and a static-like noise. A week earlier, "Far field ambient occlusion calculation" (eL5RRg-BY-8) showed horizon-based AO with symbolic obscurance integration, heavy reprojection, depth mipmapping and exponential sampling.
- 2018-06 (oBUwr08AXho): indirect light with occlusion and an AO term, unbiased and with any number of bounces within screen space, about 75 fps at 720p on a laptop, with some ghosting from moving objects and wobbly contours left.
- 2018: the latest version runs at 80–100 fps on a laptop, with no visible noise and no temporal reprojection, so moving objects leave no trails.
- Like all screen-space methods, it ignores everything outside the view.
- The shipping claim is in the description of "Realtime fur rendering based on precomputed raytracing" (DBRBZ1tZv_U, 2018-11-26), whose demo uses the author's hierarchical screen-space GI, "now shipped with Path of Exile"; it is the only such claim in the channel.

## 2D GI #1 and #2 (2022)

- The goal is to compute light from distant occluders at a lower resolution than light from nearby ones. This gives soft shadows with natural penumbras.
- Every pixel can occlude, emit and receive light. The scene only looks like it has one light.
- Farther cascades hold more information about ray directions and less about ray origins, so every cascade uses the same memory.
- Cascade n+1 has 4× fewer probes than cascade n, and each probe has 4× more directions.
- Cost is constant and does not depend on the number of lights, because each pixel has its own emission and opacity.
- GI runs at full 1920×1080. Nothing is cached between frames; each frame converges from scratch with no denoiser.
- The engine is LegitEngine, Sannikov's Vulkan framegraph engine (https://github.com/Raikiri/LegitEngine). The on-screen profiler is LegitProfiler (https://github.com/Raikiri/LegitProfiler).
  - LegitEngine is a Vulkan layer built on a render graph that derives barriers from declared resource use, with GLSL shaders compiled to SPIR-V. Its public code holds no radiance cascades: its GI demos are screen-space variance GI (SSVGI: horizon-based indirect light with 4 directions per pixel, a 16-sample Hammersley pattern over 4×4 tiles, step sizes growing by `2π/4 + 1` per iteration, and a closed-form horizon integral; the README says no denoiser while the renderer has a denoiser pass), a point-sprite renderer with coherent raycasting over sorted buckets, a simple volumetric path tracer and a Schrödinger-style water solver with a GPU 3D FFT. Several renderers (SSCTGI, SSVCTGI, SSShiftGI, LSGI) reference shader folders missing from the repository, and the Vulkan wrapper is a submodule. The README says it is not multithreaded or optimized.
  - LegitProfiler is an ImGui widget with CPU and GPU task graphs (frame-time ceiling 1/60 s by default) and a legend; MIT licensed.

## Hierarchal radiance cascades GI experiment (2022)

- This is the first 3D extension. It works in world-space voxels, and the fully dynamic scene is re-voxelized from scratch each frame.
- The demo recomputes every cascade every frame. A real application would spread cascade updates over several frames.
- Lighting is noise-free by design.
- Higher-frequency lighting costs more, so the method struggles with contact shadows. A short-range screen-space GI could cover them.

## Single shot global illumination with no denoiser (2023)

- First mostly working prototype of cascaded image-space GI. It converges to a noise-free result in about 5 ms with no denoiser.
- It uses only the current frame: no temporal reprojection and no reuse of earlier frames. It has the usual screen-space drawbacks.
- Low spatial resolution cascades have high angular resolution and capture far-field GI. High spatial resolution cascades have low angular resolution and capture near-field GI.
- Work is spread evenly: level 6 is downscaled 64×64 times, yet holds as much GI work at its frequency as level 0.

## Radiance Cascades Rendered Directly (2023)

This video renders the stored cascades directly, to show what data they hold.

- A volume was path traced once, and its radiance field was stored as a cross-section on one plane. The volume is then unloaded; the demo does no tracing or ray marching.
- Rendering takes under 0.5 ms on the GPU, at constant cost: each pixel reads only the data stored for it. The CPU side in the recording is slower because validation layers are on (01:13).
- There are four cascades, each covering one depth range. Cascade 0 has the highest spatial and lowest angular resolution. Cascade 3 has the opposite and is in effect an environment map of infinitely distant light.
- Each next cascade has twice the angular resolution and half the spatial resolution.
- All cascades are stored in one 2D texture of about 8K. Each cascade is an atlas of small cube maps in a parabolic projection, one per probe. The size is more than GI needs and was chosen for direct viewing.
- Penumbras need fine spatial resolution near their origin and less farther away; angular resolution follows the opposite pattern. RC is built to hold both, so the same structure holds ambient occlusion, soft shadows and environment light.

## Announcement for graphics programming enthusiasts! (2023)

This announces the RC paper draft and asks readers for feedback on what was hard to understand. The description links a Google Drive draft: https://drive.google.com/file/d/1L6v1_7HY2X-LV3Ofb6oyTIxgEaP4LOI6/view

## Exploring 3d holographic radiance cascades (2025)

Sponza is stored in holographic radiance cascades (HRC) and rendered directly. The 37-second video gives no grid sizes, memory, frame rate or GPU.

## Sparse 3d Radiance Cascades (2025)

- Classic full 3D world-space RC, with sparse storage. Only probes directly visible on screen are added.
- Storage is a large GPU hash map, cascaded, like a radiance cache, but it stores radiance intervals instead of radiance.
- Each pixel picks the world-space resolution of its interval tiles so that a tile covers nearly the same screen area. So the number of tiles in memory stays nearly constant, and the method scales almost like a screen-space one while staying in world space, with no upscaling.
- Tiles are cached by world position and by desired resolution. A missing tile of the needed size renders as missing; with streaming frozen, tiles vanish when the camera moves too close or too far.
- The demo traces with a basic screen-space ray marcher. The method does not depend on it and could use hardware ray tracing or SDF marching.
- There is no interpolation between tiles, which gives a blocky look.
- 60–100 fps on a laptop, with no denoising, no temporal accumulation and no upscaling.

## Sparse Radiance Cascades: goodbye screenspace (2025)

- The screen-space ray marcher is replaced with hardware ray tracing. This allows off-screen lights and is faster.
- 60 fps on a laptop RTX 4090, stable under small camera moves, all GI computed from scratch each frame with no denoiser.
- A visible seam between cascades remains, and the code is not optimized. The CPU does little work; the slow CPU frame in the video comes from validation layers and a debug build.
- The description does not say world space, but off-screen lights imply data not tied to the screen; it gives no resolution, cascade count or per-stage timings.

## Polygonal Radiance Cascades (2026)

A new variant that produces aliasing-free light from a single-pixel light source. Source, runnable in the browser: https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/PolygonalHRC45.ls&rev=master

## Testing polygonal block RC layout (2026)

The video has no description and is missing from the channel's video list, so it is probably unlisted; the layout is the one in the polygonal block demo of [HRC](2026_holographic_rc.md).

## Interview at ExileCon 2023

"Interviewing GGG: @Alexander_Sannikov" (bYTw3ISxgUw, 2023-08-03, 2:14) is an interview uploaded by another channel (hfok), not a demo; its captions have no speaker labels. Sannikov calls the GI a novel technique and says rendering innovation is held back by leaning on RTX and AI; GI progress stalled around 2015; screen space beats RTX for this problem because it scales better; the cost approaches a constant, paired with fixed memory that can be allocated in advance; and at some point a cascade shrinks to 1×1 and the scheme cannot go further. Around 74 s the speakers compare RTX with screen-space GI; nothing in the video shows a polygon-based or hardware ray-traced RC demo.

## Other channel videos

The channel (159 videos) holds the work that led to RC. Descriptions carry the content; none of these has English narration. Figures are the author's.

| Year | Video | What the description says |
|---|---|---|
| 2010 to 2012 | volume renderers (F0ul8XyeXtI, IX_rZSpZuOw, iMLMjpSgNZg), shadow techniques (uZxKCBtiJY8, yiVmMb_dnfc), Julia set ray tracing (C6pwhx93l00, VwonuMjin10) | a GPU volume ray tracer of a precomputed shockwave; transfer functions with isosurfaces as sharp peaks; adaptive ray-march steps with full lighting at about 5 fps on a GeForce 250; shadow maps rendered by the main ray tracer to avoid sliced shadow volumes |
| 2015 | 2d Pixel-perfect shadows (JMxm3DMY69o) | two fragment passes, shadow maps for many lights in one texture then lighting; 25 lights at about 150 fps with 800×600 shadow maps |
| 2016 | Reflective shadow maps (OSEIwiYQ1jA, "FuzzLighter"); adaptive imperfect shadow maps (qSZi0cI0Vrs, 8OFJziM9pts, C-FCi_BQjos) | ISM GI with triangles tessellated adaptively into points per patch and per virtual camera, all on the GPU, real time on a GTX 850M; compute-shader point tessellation and a pull-push fill from exact 3D ray-disk intersections; uniform VPL placement flickers; cost linear in triangle count; OpenGL 4.5 and C++ |
| 2016 | path tracer in a GLSL fragment shader (iIfygSNbm0I, hKc0meeWMxM, -vQGQu6pGeI, -MhytZjBB00) | unbiased, semi-real-time, dispersion and refraction in glass under area and ambient light |
| 2017 | Rasterization-based path tracing (_fm7rPsR6TA) | GI from the rasterization pipeline alone, no BVH, iterative and potentially unbiased, not real time |
| 2018 to 2019 | precomputed ray casting for grass, fur and noodles (NoJykuiHuSY, DBRBZ1tZv_U, 7DFHOMeHIoo), revisited in 2024 (aBPwnzUtfkA, b4jpSx5FA7c) | O(1) cost independent of blade or hair count, drawn in a fragment shader from a CPU-precomputed table; grass about 1 ms worst case at 1080p on a GTX 750 with precomputation from seconds to about 6 hours; fur at 100+ fps on a laptop |
| 2018 to 2019 | PoE water and refraction (Do9NB7l4Sx8, 3j_k4OnHeEg, b5hIzkANWF4, itZB1hriaSk) | the ocean shader shipped in 3.0.0; a Navier-Stokes river solver; O(1) subsurface refraction from a precomputed texture with mip-level diffusion, an earlier version shipped for Legion's obelisk crystals |
| 2021 | sparse voxel octree streaming (voQ0qQGagss, x4M65rI0AKc) | ray-guided streaming of nodes requested by the rasterizer: 4k³ effective resolution, 137M nodes and 5.4 GB in static storage, at most 600K nodes and 23 MB on the GPU; an SDF octree variant with 8³ bricks, 900K nodes, 2.5 GB in RAM and about 50K nodes resident |
| 2021 | cluster-based rendering (7JEHPvSGaX8) | clusters of about 128 triangles at constant screen size, after Ponchio 2008, which the author says Nanite also follows; 100× more objects on screen gives about 2 to 3× more triangles |

The constant-cost precomputed tables, ray-guided streaming at constant screen size and constant per-level work recur in RC: the sparse 3D RC demo picks tile resolution per pixel for a near-constant tile count, the same rule as the cluster and octree streamers (inference).
