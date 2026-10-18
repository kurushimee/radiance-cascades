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

## Earlier screen-space GI (2017–2018)

These videos show the screen-space GI that came before RC. A later video says a hierarchical version of it shipped in Path of Exile.

- 2017: a pure post process with no extra passes and no stored data. It integrates GI semi-analytically from horizon levels, like HBAO, and produces HBAO as a by-product. Near-field GI is very accurate; thin distant occluders can be missed. About 50 fps at full resolution on a GTX 850M laptop.
- 2018: the latest version runs at 80–100 fps on a laptop, with no visible noise and no temporal reprojection, so moving objects leave no trails.
- Like all screen-space methods, it ignores everything outside the view.

## 2D GI #1 and #2 (2022)

- The goal is to compute light from distant occluders at a lower resolution than light from nearby ones. This gives soft shadows with natural penumbras.
- Every pixel can occlude, emit and receive light. The scene only looks like it has one light.
- Farther cascades hold more information about ray directions and less about ray origins, so every cascade uses the same memory.
- Cascade n+1 has 4× fewer probes than cascade n, and each probe has 4× more directions.
- Cost is constant and does not depend on the number of lights, because each pixel has its own emission and opacity.
- GI runs at full 1920×1080. Nothing is cached between frames; each frame converges from scratch with no denoiser.
- The engine is LegitEngine, Sannikov's Vulkan framegraph engine (https://github.com/Raikiri/LegitEngine). The on-screen profiler is LegitProfiler (https://github.com/Raikiri/LegitProfiler).

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
- Rendering takes under 0.5 ms on the GPU, at constant cost: each pixel reads only the data stored for it.
- There are four cascades, each covering one depth range. Cascade 0 has the highest spatial and lowest angular resolution. Cascade 3 has the opposite and is in effect an environment map of infinitely distant light.
- Each next cascade has twice the angular resolution and half the spatial resolution.
- All cascades are stored in one 2D texture of about 8K. Each cascade is an atlas of small cube maps in a parabolic projection, one per probe. The size is more than GI needs and was chosen for direct viewing.
- Penumbras need fine spatial resolution near their origin and less farther away; angular resolution follows the opposite pattern. RC is built to hold both, so the same structure holds ambient occlusion, soft shadows and environment light.

## Announcement for graphics programming enthusiasts! (2023)

This announces the RC paper draft and asks readers for feedback on what was hard to understand. The description links a Google Drive draft: https://drive.google.com/file/d/1L6v1_7HY2X-LV3Ofb6oyTIxgEaP4LOI6/view

## Exploring 3d holographic radiance cascades (2025)

Sponza is stored in holographic radiance cascades (HRC) and rendered directly.

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
- A visible seam between cascades remains, and the code is not optimized. The CPU does little work.

## Polygonal Radiance Cascades (2026)

A new variant that produces aliasing-free light from a single-pixel light source. Source, runnable in the browser: https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/PolygonalHRC45.ls&rev=master
