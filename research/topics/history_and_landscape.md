# History and landscape of radiance cascades

Radiance cascades (RC) grew out of Alexander Sannikov's rendering work on Path of Exile at Grinding Gear Games (GGG). The method went from 2D tests in 2022 to a shipped screen-space version in Path of Exile 2 and a public paper draft in 2023. A community of hobbyists, students and researchers then fixed its 2D artifacts within about a year and spread it into volumes, astrophysics, path guiding and several 3D designs. This topic gives the order of events, who built what, how the method spread, and where it shipped or was turned down. The technical content of each work lives in the topic that owns it and is linked from here.

Sannikov publishes as Raikiri on GitHub and as Suslik on Shadertoy: the paper repository and Godot PR #86267 name Sannikov as Raikiri, and three-rc's README and Gavras's thesis credit Sannikov with Suslik's 4XXSWS ([Shadertoys](../sources/2023_rc_shadertoys.md), [discussions](../sources/2026_rc_discussions.md#sannikov-on-world-space-rc-godot-pr-86267)).

## Contents

- [Timeline](#timeline)
- [Before RC: Sannikov's earlier work](#before-rc-sannikovs-earlier-work)
  - [Path of Exile 1: shadows and GI](#path-of-exile-1-shadows-and-gi)
  - [Other work on Sannikov's channel](#other-work-on-sannikovs-channel)
  - [Sannikov's tools](#sannikovs-tools)
- [From 2D tests to the paper (2022 to 2023)](#from-2d-tests-to-the-paper-2022-to-2023)
  - [The paper](#the-paper)
- [ExileCon 2023 and Path of Exile 2](#exilecon-2023-and-path-of-exile-2)
  - [PoE2 cost figures](#poe2-cost-figures)
  - [When ExileCon 2023 took place](#when-exilecon-2023-took-place)
- [First public implementations and the Shadertoy lineage](#first-public-implementations-and-the-shadertoy-lineage)
- [How the method spread](#how-the-method-spread)
  - [Explainers and guides](#explainers-and-guides)
    - [SimonDev's video](#simondevs-video)
    - [Non-English overviews](#non-english-overviews)
  - [Community site, wiki and tools](#community-site-wiki-and-tools)
  - [News and discussion](#news-and-discussion)
- [Research lines](#research-lines)
- [Adoption: shipped, tried and turned down](#adoption-shipped-tried-and-turned-down)
- [Positions on 3D RC](#positions-on-3d-rc)
- [Who built what](#who-built-what)
  - [Repositories that hold nothing usable](#repositories-that-hold-nothing-usable)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)

## Timeline

Shadertoy dates are creation dates. Shadertoy keeps only the current code under the original date, so a date bounds when a shader first appeared, not when its present code was written.

| Date | Event | Notes |
|---|---|---|
| 2010 to 2016 | Sannikov's channel shows GPU volume renderers, shadow techniques, imperfect shadow map GI and GLSL path tracers | [before RC](#other-work-on-sannikovs-channel) |
| 2017-06-01 | "Screen Space Global Illumination" (VOg_8ipCZLA): horizon-based GI as a pure post process, about 50 fps on a GTX 850M | [videos](../sources/2022_sannikov_youtube_rc_videos.md#earlier-screen-space-gi-20172018) |
| 2018 | Path of Exile 1 ships hierarchical screen-space variance GI; point-light shadows are added for the Delve league | [PoE1](#path-of-exile-1-shadows-and-gi) |
| 2018-07-19 | "Global illumination in screenspace: 80fps, noise-free, no reprojection" | |
| 2018-11-26 | "Realtime fur rendering based on precomputed raytracing", whose demo uses the hierarchical screen-space GI, says in its description that this GI is "now shipped with Path of Exile", the channel's only such claim | |
| 2019 (uploaded 2020-04-06) | ExileCon 2019 talk on the screen-space shadows and GI | [talk notes](../sources/2019_sannikov_poe_gi_talks.md#exilecon-dev-talk---evolving-path-of-exiles-renderer) |
| 2022-08-25, 2022-08-28 | "2d Full Global Illumination" #1 (eS0zd_8nfhk, "proof of concept, no denoising, interactive fps") and #2 (o2kgW2TBpUo, "working principle and perf tests"): the first RC demos, full 1920×1080, nothing cached between frames | [2D tests](#from-2d-tests-to-the-paper-2022-to-2023) |
| 2022-10-28 | "Hierarchal radiance cascades GI experiment" (5Ua-h1pg6yM): first 3D cascades, in world-space voxels re-voxelized each frame | |
| 2023-04-19 | "Single shot global illumination with no denoiser": cascaded image-space GI, about 5 ms | |
| 2023-07 | ExileCon 2023, "Rendering Path of Exile 2": the public debut of RC, about 1 ms in game | [ExileCon 2023](#exilecon-2023-and-path-of-exile-2) |
| 2023-08-19 | "Radiance Cascades Rendered Directly" (xkJ6i2N32Pc), one of the channel's only two RC videos with spoken explanation | |
| 2023-08-22 | The paper draft is announced with a request for reader feedback (vlF1CX8X5Bc, the other spoken video) | [paper](#the-paper) |
| 2023-09-02 | fad's Shadertoy mtlBzX, the first public implementation, and its debug variant DlSfzz | [Shadertoy lineage](#first-public-implementations-and-the-shadertoy-lineage) |
| 2023-09-04 | Suslik's mlSfRD, a fork of DlSfzz | |
| 2023-10 | tmpvar's implementation notes; Otavio Peixoto's repository is created (its RC renderer lands 2024-06) | |
| 2023-11-09 | 80.lv news post on the paper | [news](#news-and-discussion) |
| 2023-11-23 | Quinchilion's clVcD3 adds a ringing mask | |
| 2024-01-03, 2024-01-04 | Suslik's cascaded gravity simulations MfS3Wm and XcB3Ry | [light transport alternatives](light_transport_alternatives.md) |
| 2024-03-14 | Suslik's 4XXSWS, novel depth-aware upscaling | [3D screen space](3d_screen_space.md) |
| 2024-04 | GM Shaders Part One (04-13); Suslik's MctXRr (04-19) and the RC Experimental Testbed 4ctXD8 (04-24); tmpvar's 3D grid (last commit 04-28) | |
| 2024-07 | SimonDev's video (07-02); GM Shaders Part Two (07-13); Mytino's fix diagram 4clcWn (07-15); kornelski's gear fix XffcD7 (07-17); Mytino's MfXyRj and mxcop's lcfcR2 (07-18); mxcop's XcfyDj (07-21); This Week in Bevy (07-22); jason.today Part 1 (07-27) | [spread](#how-the-method-spread) |
| 2024-08 | Osborne and Sannikov's radiative transfer paper (arXiv 2408.14425); Max Coppen's first 3D RC on X (08-12, "screen probes, world intervals"); jason.today Part 2 (08-31); kornel.ski penumbra calculator; Osborne's slides | |
| 2024-10 | Coppen's "Fundamentals of Radiance Cascades" (10-22) and its Hacker News thread; Théo Le Goc's Vulkan post (10-22); Sannikov's LegitCascades scripts begin | |
| 2024-11 | X3XfRM, surface (UV-space) RC (11-02); Suslik's 4ctczl, the first holographic RC Shadertoy (11-08) | |
| 2024-12-16 | Mathis's lXByRh, screen-space probes | |
| 2025-01-22 | Coppen's surfel RC article | |
| 2025-02-08 | Mathis's M3ycWt, volumetric voxel cascades | |
| 2025-04-07 | Habr overview in Russian | |
| 2025-05 | Holographic Radiance Cascades paper (Freeman, Sannikov, Margel; arXiv 2505.02041) | [holographic RC](holographic_rc.md) |
| 2025-06 | Kung's thesis comparing RC with voxel cone tracing | |
| 2025-09-02 | "Exploring 3d holographic radiance cascades" | |
| 2025-09-20 | JMS55's Solari post for Bevy 0.17 | [adoption](#adoption-shipped-tried-and-turned-down) |
| 2025 | Theses by Gavras, Kaméus, Abou Dan and Jensen, Dell'Ova (cover dated 10 2025) and Rulkens (report dated 2025-11-07) | [research lines](#research-lines) |
| 2025-11 | Osborne's DexRT ray-acceleration paper (arXiv); "Sparse 3d Radiance Cascades" (11-02, TGLAxW0xVDU) | |
| 2025-11-30 to 2025-12-03 | youssef_afella's single-frame 2D and HRC Shadertoys; codyjbennett's 2D volumetric cascades (12-01) | |
| 2025-12-25 | "Sparse Radiance Cascades: goodbye screenspace" (rG2aok2SdbU): world-space RC work in progress with hardware ray tracing, 60 fps on a laptop RTX 4090, all from scratch each frame | |
| 2026-02-28 | "Polygonal Radiance Cascades" | |
| 2026-03 | GDC 2026 talk on Love and Deepspace, the only shipped 3D RC found; LIRIS GDL reading-group talk; polygonal block layout video (03-15, probably unlisted: it has no description and is missing from the channel's video list) | |
| 2026-04 | Gerassimov's DiGRA paper (04-18); Suslik's min/max interpolation tests (04-15) and cone sweeping tests (04-22); last LegitCascades commit (04-09) | |
| 2026-05 | kooch closes its RC issue and picks a surfel radiance cache | |
| 2026-07 | Split Radiance Cascades paper v2 (Freeman, Sannikov, Pitt-Francis); Ivan You's Reservoir Cascades (07-23) | |
| 2026-08-08 | codyjbennett's scy3Dd, SPWI in one Shadertoy | |
| 2026-09 | Suslik's extended gathering Shadertoys (09-01, 09-02); Blackline Interactive's surface-atlas 3D RC builds (09-12, 10-03), after a world-probe build (08-29); gomezzz's Godot 3D RC (last commit 09-13) | |
| 2026-10-09 | RC-based path guiding (Ikkala, Jääskeläinen, Mäkitalo) online in ACM TOG | [sampling and guiding](rc_for_sampling_and_guiding.md) |

## Before RC: Sannikov's earlier work

### Path of Exile 1: shadows and GI

Two PoE1 techniques led to RC. The ExileCon 2019 talk ("Evolving Path of Exile's Renderer", recorded at ExileCon 2019 and uploaded 2020-04-06, https://www.youtube.com/watch?v=whyJzrVEgVc) presents both, and its English captions (the track named "en", not the auto-generated one; 54 min 38 s, timestamps in caption minutes) give no ray, segment or sample counts and no probe layers; the 10 ms near 44:05 is dynamic atlas building, not GI. An ExileCon link `B-ODrtmtpzM` cited elsewhere is a private video, the devtrackers list of ExileCon 2019 talks gives this renderer talk at `whyJzrVEgVc`, and no 2019 GDC talk on PoE's screen-space GI was found ([notes](../sources/2019_sannikov_poe_gi_talks.md)).

**Point-light shadows.** Point-light shadows were added for the Delve league, where players could not turn them off. The goal was shadows that are fast, look good and work on any hardware. The talk's reasoning:

- Shadows show where objects touch surfaces; the speaker says that without them it is hard to tell whether an object touches the floor. The penumbra is the gradient at the shadow edge and has zero width at contact. Uniform-width penumbras, seen in other games, are not physically correct.
- The input is a shadow map of a player light, white where the light reaches and black where something blocks it. A sharp shadow map blurred afterwards does two separate jobs. Shadow maps suit directional lights and spotlights; an omnidirectional point light needs six cube-face shadow maps, which the speaker says no one uses because they are too expensive or do not scale.
- The method is named Screenspace Hierarchical Variance Shadow maps. The talk does not explain "variance"; "cascades" here are shadow levels of detail.
- Its stages, each shown by turning it off: a one-pixel blur (without it edges alias), depth-aware upscaling (without it areas look blocky), cascades that split the shadow into levels, each with its own detail and screen area, and MIP levels. The first level covers the small contact region, the sharpest part of the penumbra, at the highest precision; farther parts are blurred and need less. The largest part of the shadow is computed at the cheapest resolution, so load spreads evenly across levels, where in traditional methods the most blurred far end costs the most. Restoring the stages in order, depth-aware upscaling, then blur, then all MIP levels, gives the final image.
- Cost is capped. A traditional method renders the scene once per light (ten lights, ten renders of every object); this one gives each screen point a fixed number of contributions (with a hundred lights, each point is affected by about two major lights) and renders no extra geometry. The speaker values a steady frame rate over a high peak, comparing a game at 300 fps that drops to 5 with one that stays between 60 and 100.
- It depends on several properties of PoE and its in-house engine, losing any one of which would make it not good enough, and would show artifacts in general games such as 3D shooters.

This is RC's founding observation in shadow form: the penumbra near contact needs fine spatial resolution and the far penumbra does not, so work per level can be equal. The paper credits these "hierarchical screen-space shadow cascades" as RC's inspiration ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#context-from-the-related-work-section)).

**Screen-space GI.** PoE1's "hierarchical screen-space variance-based GI" (developed 2017, shipped 2018) treats every visible pixel as a point light with its own shadows, in a 3 ms budget, with no temporal reprojection, no baking and no ray-tracing hardware. Its method and its relation to Mayaux's horizon-based indirect lighting are in [related screen-space GI](related_screen_space_gi.md). Sannikov calls it the first screen-space GI in a released game (ExileCon 2023), and names its weakness as a denoiser that blurred detail. The ExileCon 2023 talk says it lacked the property the shadows had, computing each part of the result at its own resolution, and RC was built to give GI that property ([ExileCon 2023](../sources/2023_sannikov_exilecon_rendering_poe2.md)).

### Other work on Sannikov's channel

The channel (https://www.youtube.com/@Alexander_Sannikov, 159 videos) holds the work that led to RC. Descriptions carry the content, figures are the author's, and none of these videos has English narration ([notes](../sources/2022_sannikov_youtube_rc_videos.md#other-channel-videos)).

| Year | Videos | What the descriptions say |
|---|---|---|
| 2010 to 2012 | volume renderers (F0ul8XyeXtI, IX_rZSpZuOw, iMLMjpSgNZg), shadow techniques (uZxKCBtiJY8, yiVmMb_dnfc), Julia set ray tracing (C6pwhx93l00, VwonuMjin10) | a GPU volume ray tracer of a precomputed shockwave; transfer functions with isosurfaces as sharp peaks; adaptive ray-march steps with full lighting at about 5 fps on a GeForce 250; shadow maps rendered by the main ray tracer to avoid sliced shadow volumes |
| 2015 | 2d Pixel-perfect shadows (JMxm3DMY69o) | two fragment passes, shadow maps for many lights in one texture then lighting; 25 lights at about 150 fps with 800×600 shadow maps |
| 2016 | reflective shadow maps (OSEIwiYQ1jA, "FuzzLighter"); adaptive imperfect shadow maps (qSZi0cI0Vrs, 8OFJziM9pts, C-FCi_BQjos) | ISM GI with triangles tessellated adaptively into points per patch and per virtual camera, all on the GPU, real time on a GTX 850M; compute-shader point tessellation and a pull-push fill from exact 3D ray-disk intersections; uniform VPL placement flickers; cost linear in triangle count; OpenGL 4.5 and C++ |
| 2016 | path tracer in a GLSL fragment shader (iIfygSNbm0I, hKc0meeWMxM, -vQGQu6pGeI, -MhytZjBB00) | unbiased, semi-real-time, dispersion and refraction in glass under area and ambient light |
| 2017 | rasterization-based path tracing (_fm7rPsR6TA) | GI from the rasterization pipeline alone, no BVH, iterative and potentially unbiased, not real time |
| 2017 | far-field ambient occlusion (eL5RRg-BY-8), a week before the SSGI video | horizon-based AO with symbolic obscurance integration, heavy reprojection, depth mipmapping and exponential sampling |
| 2017 | "Screen Space Global Illumination" (VOg_8ipCZLA) | a pure post process with no extra passes and no stored data that integrates GI semi-analytically from horizon levels, like HBAO, and produces HBAO as a by-product; near-field GI is very accurate, and thin distant occluders can be missed; about 50 fps at full resolution on a GTX 850M laptop; it targets the second bounce and uses the HBAO term as an approximate third, and with complete screen data (no hidden occluders or off-screen lights) it converges to the path-traced result; it leans on spatial and temporal coherence, which shows as artifacts under fast motion and a static-like noise |
| 2018 | screen-space GI updates (oBUwr08AXho in June, OPFvcsQAKjc in July) | June: indirect light with occlusion and an AO term, unbiased with any number of bounces within screen space, about 75 fps at 720p on a laptop, some ghosting from moving objects and wobbly contours left; July: 80 to 100 fps on a laptop with no visible noise and no temporal reprojection |
| 2018 to 2019 | precomputed ray casting for grass, fur and noodles (NoJykuiHuSY, DBRBZ1tZv_U, 7DFHOMeHIoo), revisited in 2024 (aBPwnzUtfkA, b4jpSx5FA7c) | O(1) cost independent of blade or hair count, drawn in a fragment shader from a CPU-precomputed table; grass about 1 ms worst case at 1080p on a GTX 750 with precomputation from seconds to about 6 hours; fur at 100+ fps on a laptop |
| 2018 to 2019 | PoE water and refraction (Do9NB7l4Sx8, 3j_k4OnHeEg, b5hIzkANWF4, itZB1hriaSk) | the ocean shader shipped in 3.0.0; a Navier-Stokes river solver; O(1) subsurface refraction from a precomputed texture with mip-level diffusion, an earlier version shipped for Legion's obelisk crystals |
| 2021 | sparse voxel octree streaming (voQ0qQGagss, x4M65rI0AKc) | ray-guided streaming of nodes requested by the rasterizer: 4k³ effective resolution, 137M nodes and 5.4 GB in static storage, at most 600K nodes and 23 MB on the GPU; an SDF octree variant with 8³ bricks, 900K nodes, 2.5 GB in RAM and about 50K nodes resident |
| 2021 | cluster-based rendering (7JEHPvSGaX8) | clusters of about 128 triangles at constant screen size, after Ponchio 2008, which the author says Nanite also follows; 100× more objects on screen gives about 2 to 3× more triangles |

The 2017 SSGI, by its description, leans on spatial and temporal coherence, which shows as artifacts under fast motion and a static-like noise; the 2018 versions drop temporal reprojection, so moving objects leave no trails. Like all screen-space methods, all of them ignore what is outside the view.

### Sannikov's tools

- **LegitEngine** (https://github.com/Raikiri/LegitEngine) is Sannikov's Vulkan layer, used for the 2022 2D GI demos. It is built on a render graph that derives barriers from declared resource use, with GLSL compiled to SPIR-V. Its public code holds no radiance cascades. Its GI demos are screen-space variance GI (SSVGI, the method in [related screen-space GI](related_screen_space_gi.md#path-of-exile-1s-screen-space-gi), here horizon-based indirect light with 4 directions per pixel, a 16-sample Hammersley pattern over 4×4 tiles, step sizes growing by `2π/4 + 1` per iteration and a closed-form horizon integral; the README says no denoiser while the renderer has a denoiser pass), a point-sprite renderer with coherent raycasting over sorted buckets, a simple volumetric path tracer and a Schrödinger-style water solver with a GPU 3D FFT. Several renderers (SSCTGI, SSVCTGI, SSShiftGI, LSGI) reference shader folders missing from the repository, and the Vulkan wrapper is a submodule. The README says the engine is not multithreaded or optimized.
- **LegitProfiler** (https://github.com/Raikiri/LegitProfiler, MIT) is the on-screen profiler in those demos: an ImGui widget with CPU and GPU task graphs (frame-time ceiling 1/60 s by default) and a legend.
- **LegitScriptEditor** (https://radiance-cascades.github.io/LegitScriptEditor/, by tmpvar and Sannikov) runs LegitScript render graphs in the browser, and a script loads from GitHub by query string, for example `?gh=Raikiri/LegitCascades/PolygonalHRC45.ls&rev=master` for the aliasing-free single-pixel-light variant; it hosts LegitCascades and is described under [community tools](#community-site-wiki-and-tools).

## From 2D tests to the paper (2022 to 2023)

The first RC videos state the method's core properties before the paper did ([videos](../sources/2022_sannikov_youtube_rc_videos.md)):

- **2D GI #1 and #2 (August 2022):** distant occluders are computed at a lower resolution than nearby ones, which gives soft shadows with natural penumbras. Every pixel can occlude, emit and receive light, and the scene only looks like it has one light. Farther cascades hold more direction information and less origin information, so every cascade uses the same memory: cascade n+1 has 4× fewer probes, each with 4× more directions. Cost is constant and independent of the number of lights. GI runs at full 1920×1080, nothing is cached between frames, and each frame converges from scratch with no denoiser.
- **Hierarchal radiance cascades GI experiment (October 2022):** the first 3D version, in world-space voxels, with the fully dynamic scene re-voxelized each frame and every cascade recomputed each frame (a real application would spread updates over frames). It is noise-free by design and struggles with contact shadows, which cost more; a short-range screen-space GI could cover them ([3D world space](3d_world_space.md)).
- **Single shot GI with no denoiser (April 2023):** the first mostly working cascaded image-space GI, converging noise-free in about 5 ms from the current frame alone. Level 6, downscaled 64×64 times, holds as much GI work at its frequency as level 0 ([3D screen space](3d_screen_space.md)).
- **Radiance Cascades Rendered Directly (August 2023):** a path-traced volume stored as cascades on one plane and viewed with no tracing, under 0.5 ms, showing that one structure holds AO, soft shadows and environment light ([3D surface probes](3d_surface_probes.md)).
- **Announcement (2023-08-22):** the paper draft on Google Drive (https://drive.google.com/file/d/1L6v1_7HY2X-LV3Ofb6oyTIxgEaP4LOI6/view), with a request for feedback on what was hard to understand.

An ExileCon 2023 interview uploaded by another channel (hfok, "Interviewing GGG: @Alexander_Sannikov", bYTw3ISxgUw, 2023-08-03, 2:14, captions without speaker labels) gives Sannikov's framing at the time: the GI is a novel technique; rendering innovation is held back by leaning on RTX and AI; GI progress stalled around 2015; screen space beats RTX for this problem because it scales better; the cost approaches a constant, with fixed memory that can be allocated in advance; and at some point a cascade shrinks to 1×1 and the scheme cannot go further. Around 74 s the speakers compare RTX with screen-space GI. A thread cites this video at that time for a polygon-based hardware ray-traced RC demo, and the video shows none ([notes](../sources/2022_sannikov_youtube_rc_videos.md#interview-at-exilecon-2023)).

### The paper

"Radiance Cascades: A Novel Approach to Calculating Global Illumination" is a work-in-progress preprint in the JCGT template, licensed CC BY-ND 3.0, never formally published. Its LaTeX source is https://github.com/Raikiri/RadianceCascadesPaper (PDF at `out_latexmk2/RadianceCascades.pdf`). It defines the penumbra condition, radiance intervals, the merge, the scaling laws and the memory per domain, all in [core theory](core_theory.md), and it gives asymptotic scaling only, leaving base parameters to tuning ([notes](../sources/2023_sannikov_radiance_cascades_paper.md)).

It describes five early implementations, the record of what Sannikov built before the community started:

| Implementation | What it is | Numbers | Owning topic |
|---|---|---|---|
| Radiant 2D | first 2D proof of concept, per-pixel GI | about 30 ms on an RTX 3060 depending on fidelity; 2, 102 and 1002 lights all cost about 12 ms | [core theory](core_theory.md#shift-and-extend), [performance](performance.md) |
| Path of Exile 2 | screen-space, flatland-like hierarchy filled by screen-space raymarching | about 3 ms on a GTX 1050 | [3D screen space](3d_screen_space.md) |
| Radiance 3D | world-space 3D probe grid in a volume texture, filled from voxels or screen-space data | storage is the limit, not time | [3D world space](3d_world_space.md) |
| Direct radiance field renderer | path-traced volume baked into surface cascades on one quad, viewed directly | under 0.5 ms on an RTX 3060 | [3D surface probes](3d_surface_probes.md) |
| Screen probes with world-space intervals | probes on the depth buffer, world-space SDF raymarching | 30 to 50 ms on an RTX 3060, 0.1 to 0.5 s to converge with reprojection | [3D screen space](3d_screen_space.md) |

The related-work section places RC between ambient occlusion and environment maps, the near-field and far-field ends of one spectrum, with Lumen and GI-1.0 using four levels in between (AO, screen probes, world radiance cache, environment). It says probe GI always trades many low-resolution probes against few high-resolution ones, and finding the right point was the main motivation. Voxel cone tracing's averaging of radiance through mipmaps fed the first PoE GI.

## ExileCon 2023 and Path of Exile 2

"Rendering Path of Exile 2" (https://www.youtube.com/watch?v=TrHHTQqmAaM, 53 min, GI from 27:00 to 39:00) presented RC as one of about a dozen PoE2 rendering techniques. A re-upload by Cakez ("Most Performant Global Illumination POE2 Rendering", https://www.youtube.com/watch?v=ShiFEvlzbew, 2023-08-01, 45 min 11 s, GI from about 30:41, timestamps in caption minutes) has auto-captions with some wrong words, such as "global elimination" for global illumination, corrected only where the meaning is clear; neither recording uses the phrase "radiance cascades", only "cascades", "radiance probes" and "radiance probe hierarchy" ([ExileCon notes](../sources/2023_sannikov_exilecon_rendering_poe2.md), [re-upload notes](../sources/2019_sannikov_poe_gi_talks.md#most-performant-global-illumination-poe2-rendering)).

The talk, in order:

- GI is a many-to-many interaction: each point lights, receives from and blocks every other. Path tracing is simple to write and takes minutes per frame, and the industry methods the speaker knew did not fit the game.
- PoE1 shipped the first screen-space variance-based GI (2018; the captions give its basis as "based on variants", which is unclear), but it lacked the property of PoE's cascaded shadows, which the speaker wanted GI to share. As this talk puts it, the first shadow cascade covers a large part at low resolution, the next a part at higher resolution and the last a small part that needs the highest resolution; each part is computed at its own resolution, so the total cost is lower. The ExileCon 2023 recording says the same: blurry penumbra parts render at low resolution, and only the small sharp part near contact renders at full resolution. The ExileCon 2019 talk lists the levels the other way round, starting from the small contact region at the highest precision; both describe one split of the penumbra by distance from contact, read from opposite ends (inference).
- Probes are "tiny cameras" capturing cube maps, and objects are lit from the nearest one; and each studio picks its own point between many small probes and few large ones. RC uses all of them at once as a hierarchy.
- Development started as a 2D test, since 3D was harder to build while 2D GI is almost as hard a problem, and it worked on the first try.
- The 2D example combines a grid of 4-ray probes with a coarser cascade of probes with more rays, so each probe has eight rays after combining; as spoken, 16 probes of eight rays give 128 rays in total. Rays are built from slightly bent segments that converge to straight lines as they shorten, with 64 and 32 segments for the two cascades (the captions read "30 64" and are not fully consistent). The ray counts shown for more cascades are 64, 128 and 256: the captions read the middle one as "120", but the speaker says the counts are powers of two. The speaker calls the cost behaviour "an exploit": each cascade captures twice the rays at half the cost, so a hundred cascades cost about as much as one.
- In PoE2's screen-space version cascade 0 captures only a tiny neighbourhood of each point and looks like "bad AO", and each higher cascade holds longer-range, lower-frequency light. The first level has many tiny probes in small grids, and higher levels have larger probes and fewer of them. The first cascade costs the most memory and time.
- Emissive and directly lit surfaces cost the same, so emissive-only scenes are the standard test.
- A world-space variant on the channel uses no screen-space data and lights from sources behind the camera, which PoE does not need and other games may.
- The encoding stores light reaching each point from every direction, so the same data gives specular GI: a dungeon with narrow materials (the ExileCon 2023 recording says mirror dungeons), porcelain-like highlights, and diffuse plus specular combined in game.
- Correct GI methods converge to the same image, so the speaker shows no side-by-side comparison; the question is how fast each gets there. RC is faster than the earlier PoE GI and scales better than anything else the speaker has seen, with no numbers given.

The Q&A adds that the probe hierarchy is fixed and independent of scene content, so the cost stays at roughly 1 ms whether one or a million fireballs are on screen, so it never drops the frame rate in heavy fights; screen space is enough because of the fixed top-down camera; PoE2 has no TAA because the game is too dynamic, which is part of why RC avoids temporal reuse; and RC did not ship in the PoE1 engine update of the time because of the size of the change.

### PoE2 cost figures

| Figure | Setting | Source | Standing |
|---|---|---|---|
| about 1 ms, constant | not stated | ExileCon 2023 Q&A | speaker's figure |
| about 3 ms | GTX 1050 | paper | stated |
| 0.8 ms, same in any scene, with no temporal accumulation and so no lag | RTX 4090, 4K, High setting | Hacker News commenter Negitivefrags, 2024-10 ([discussions](../sources/2026_rc_discussions.md#path-of-exile-2-claims)) | third-party claim |
| about 3 ms, "several hundred probes" with 128×128 textures | not stated | Habr overview, 2025 ([overview](../sources/2025_non_english_rc_overviews.md)) | no source given, and the 2023 talk gives no such numbers |

The first three fit one picture: about 3 ms on a 2016 entry-level GPU, about 1 ms on the hardware of a 2023 talk, and under 1 ms at 4K on a 2022 flagship. The Habr figure matches the paper's GTX 1050 number and has no other support, so it probably repeats it with invented detail (inference). The PoE2 design itself is in [3D screen space](3d_screen_space.md). As of 2026-10 no public source beyond the talk and the paper gives its cascade count, probe spacing, interval lengths, directions per probe, the 128-bit occlusion layout, its resolution or per-pass timings; developer posts, patch notes and published frame analyses state none.

### When ExileCon 2023 took place

The ExileCon note dates the talk 2023-07, and the wiki says November 2023. The Cakez re-upload of the talk is dated 2023-08-01 and the ExileCon interview 2023-08-03, so the talk predates August 2023; the wiki's November date matches the 80.lv news post of 2023-11-09 instead (inference).

## First public implementations and the Shadertoy lineage

fad's Shadertoy mtlBzX ("Radiance Cascades", 2023-09-02) is the first public implementation, two weeks after the paper announcement. It includes the sky integral, and its merge spreads over frames because Shadertoy runs each pass once per frame; radiance-cascades.com notes this temporal latency ([wiki](../sources/2026_rc_community_site_and_wiki.md#shadertoys)). Shadertoy's fork links give the main line ([lineage](../sources/2023_rc_shadertoys.md#lineage)):

- mtlBzX (fad, 2023-09) → clVcD3 (Quinchilion, 2023-11, a ringing mask) → MctXRr (Suslik, 2024-04-19) → 4ctXD8 (Suslik, "RC Experimental Testbed", 2024-04-24).
- 4ctXD8 has three lines of descendants: MfXyRj (Mytino, circle projection) → lcfcR2 (mxcop); 4ctczl (Suslik, holographic); NfVXRc → sfVSzd (Suslik, extended gathering).
- mtlBzX → XffcD7 (kornelski, gear fix).
- DlSfzz (fad's debug variant, same day as mtlBzX, no recorded parent though its comment names mtlBzX) → mlSfRD (Suslik, smooth interval edges, whose header still names mtlBzX).
- 4clcWn (Mytino, diagram of the fixes) → XcfyDj (mxcop, reprojection diagram).
- wfyyDz → ffl3Rf → NfySzt (codyjbennett, media).
- youssef_afella's tfKyRw, 3cKczD and WfyyDm have no fork links (WfyyDm's comment calls tfKyRw a simpler version of it); Neylick's w3XSz4 credits fad's shader without a link.
- 4XXSWS → MXjcWK and NfSXRh → ffSSz1 → NfBSz1 (Suslik, upscaling and min/max interpolation); 7c2XDw → 7f2SzV (Suslik, cone sweeping); XfBGWw → MfS3Wm → XcB3Ry (Suslik, gravity).

The community wiki and Sohojoe's Godot port give the same fad → Quinchilion → Suslik → testbed order. The 4ctXD8 framework shows in all its descendants through shared names (`MERGE_FIX`, `BRANCHING_FACTOR`, `SPATIAL_SCALE_FACTOR`, `C_MINUS1_GATHERING`, the `CastMergedInterval*` family, `MergeIntervals`) and through dead code carried along (`RAYS_FORK_POW` defined and never read in MctXRr, lcfcR2 and NfVXRc; `roundSDim` unused in MctXRr, lcfcR2, 4ctczl and NfVXRc). The same `MERGE_FIX` number can mean different code in different forks. scy3Dd, outside this tree, uses the same `C_MINUS1_GATHERING` name and credits 4XXSWS. What each shader does is in [2D Shadertoys](2d_shadertoys.md), [artifacts and fixes](artifacts_and_fixes.md), [holographic RC implementations](holographic_rc_implementations.md#shadertoys) and [3D screen space](3d_screen_space.md).

**Who found the bilinear fix.** The community credits the bilinear fix to Mytino's diagram 4clcWn (2024-07-15). MctXRr (2024-04-19) already traces from each lower probe to each of its four upper probes, and 4ctXD8 (2024-04-24) makes that the default merge. Given the date caveat, this shows only that the fix was in Suslik's line no later than its current code; Sannikov's LegitCascades `Scaling.ls` also uses it as the reference merge.

## How the method spread

### Explainers and guides

| Guide | Author | Date | Form | What it adds | Content in |
|---|---|---|---|---|---|
| Implementing Radiance Cascades (notes) | tmpvar | 2023-10 | open questions | two guesses for screen-space probes (march the depth buffer, or move each probe onto the surface under its pixel for world-space rays), the opacity correction for longer steps, 3D memory worries | [volumetric](volumetric_and_radiative_transfer.md) |
| Building Intuition around RC | tmpvar | 2024 | 2D WebGPU (Chrome or Edge) and 3D (https://tmpvar.com/poc/radiance-cascades-3d/) playgrounds | controls for every parameter; a 3D comparison of probe direction sets (cube-face subdivision, golden spiral and others) | [2D articles and demos](2d_articles_and_demos.md#tmpvars-playground), [3D world space](3d_world_space.md) |
| GM Shaders Part One and Two | Yaazarai (Alex), with Xor | 2024-04-13, 2024-07-13 | articles with GameMaker code | pre-averaging and direction-first layout (first prototyped there, per the wiki), a single-shader version under 100 lines, bilinear-fix and nearest-fix branches | [cascade layout](cascade_layout_and_merging.md) |
| Exploring a New Approach to Realistic Lighting | SimonDev | 2024-07-02 | 15-min video | rendering equation, penumbra idea, interval merging, 2×2 pixel probes | [below](#simondevs-video) |
| Building Real-Time GI, parts 1 and 2 | Jason McGhee | 2024-07-27, 2024-08-31 | interactive articles | distance fields and JFA, then RC step by step with sRGB handling and ringing | [2D articles and demos](2d_articles_and_demos_jason_today.md#jasontoday-jason-mcghee) |
| [Radiance Cascades slides](https://goobley.github.io/RadianceCascadesSlides/) | Christopher Osborne (Goobley) | 2024-08 | slides | branching-factor cost comparison, a WebGL demo, slides on variance-limited mipmaps that the DexRT paper covers in full | [core theory](core_theory.md) |
| RadiCalc penumbra calculator | Kornel Lesiński (kornelski) | 2024-08 | spreadsheet | interval sizing from the exact penumbra condition | [core theory](core_theory.md) |
| Fundamentals of Radiance Cascades | Max Coppen (mxcop) | 2024-10-22 | article with 8 animations (video elements, content not transcribed) and 10 diagrams (angular and spatial observations, rings, cascade memory, interval merging, nearest and bilinear merges; the final image credits Fad's mtlBzX) | 2D fundamentals, merging, interval casting | [core theory](core_theory.md) |
| Radiance Cascade GI (Vulkan) | Théo Le Goc (tlegoc) | 2024-10-22 | blog and code | symmetric layout at any aspect, parallel tracing | [2D articles and demos](2d_articles_and_demos.md#théo-le-goc-tlegoc-vulkan) |
| Radiance Cascades For 2D GI | Otavio Peixoto | 2024-06 | portfolio page and code | cascade memory layout and merging in OpenGL | [2D articles and demos](2d_articles_and_demos.md#otavio-peixoto-opengine) |
| Radiance Cascades, a new look at GI (Russian, Habr) | heavychevy | 2025-04-07 | article | restates the paper, adds unsourced claims | [below](#non-english-overviews) |
| Irradiance Volumes – Radiance Cascades, 1996–2026 (French, LIRIS GDL talk 84) | not named | 2026-03 | 31 slides | places RC in probe-GI history | [below](#non-english-overviews) |
| GPC 2024 student showcase, RC segment | Max (likely Max Coppen) | 2024 | talk | 2D explainer, first look at 3D SPWI, branching comparison | [3D screen space](3d_screen_space.md) |

Besides ExileCon 2023, three recorded talks cover RC or a cascaded relative: the GPC 2024 student showcase, the Love and Deepspace GDC 2026 talk and Enshrouded's cascaded probe cache; only auto-captions exist for them ([talks](../sources/2026_rc_conference_talks.md)).

#### SimonDev's video

SimonDev's "Exploring a New Approach to Realistic Lighting: Radiance Cascades" (https://www.youtube.com/watch?v=3so7xdZHKxw, 14:56) is the most common entry point: the wiki's "Start Here" list opens with it, and This Week in Bevy says interest in RC grew after it ([notes](../sources/2024_simondev_exploring_radiance_cascades_video.md)). It explains:

- **GI and the rendering equation (00:00 to 03:00):** three images of a scene with a camera, a floor, a wall and a ceiling (no lighting, direct light with a shadow, direct plus GI), GI as light bounced off other surfaces, and the rendering equation as pseudocode: a loop over hemisphere directions multiplying incoming light by the BRDF and by the cosine, summed. For a red diffuse cube the BRDF is the surface color, and even one direct light gets expensive with shadows and complex BRDFs.
- **The key observation (04:00 to 05:00):** resolving an object of a given size needs higher linear resolution near it and higher angular resolution far away. Tested with one point and one light, four directions hit a nearby light; farther away they miss it, and more directions are needed; a smaller light has the same effect.
- **Penumbras (06:00 to 08:00):** umbra, penumbra and lit area; the penumbra is sharp near the wall and blurs farther away, with a size set by the light-to-wall distance and the light size; so far from the light samples can be spaced far apart but need more directions, while near it the spacing must be smaller: the penumbra condition.
- **Merging (09:00 to 10:00):** light from A to C equals light from A to B plus light from B to C times the transparency from A to B, and transparencies multiply; transparency is 0 on a hit and 1 otherwise. Two points on one ray whose checks cover the same path can merge them, the first point treating both checks as one interval.
- **Probe levels (10:00 to 11:00):** low-level probes have few directions and short checks and are bilinearly interpolated; higher levels have more directions, sit farther apart and check longer ranges; using them at a lower level averages several directions and then interpolates.
- **2D layout (12:00 to 13:00):** 2×2 pixel blocks are probes with four directions each, the next level uses 4×4 blocks with 16 directions, each probe at the centre of its block, and cascades can stay separate or pack into one texture. No index formula is given.
- **Limits (13:00 to 14:56):** a basic 2D demo on the author's site (the subtitles garble the path); the community is working on fixes; the paper's author checked the video; a small light shows ringing and a large light behind a thin wall leaks, with community mitigations not described; the ideas extend to 3D as a world-space grid or in screen space.

Its code is https://github.com/simondevyoutube/Shaders_RadianceCascades (not linked from the video), with a live demo at https://simondevyoutube.github.io/Shaders_RadianceCascades/, which the wiki calls a good starting point for newcomers; the video also points at Shadertoy mlSfRD.

#### Non-English overviews

Both are introductions without an implementation ([notes](../sources/2025_non_english_rc_overviews.md)).

- **Habr (Russian, heavychevy, 2025-04-07, https://habr.com/ru/articles/897956/)** restates the penumbra condition (Δp ∼ D, Δω ∼ 1/D) and the interval sum `L_{0,∞} = L_{0,r1} + β_{0,r1}·L_{r1,r2} + …`, and frames RC as an approximation of the rendering equation limited to one indirect bounce. It adds, with no cited source: near cascades are recomputed fully or partly each frame while far cascades update less often or through temporal filters; a point is sampled by picking the cascade by distance and interpolating the nearest probes over position and direction; cascades are stored in octahedral or cube-map textures, which the author says keep direction storage compact and even and make interpolation simpler (octahedral texels are in fact not equal in solid angle; see [supporting techniques](supporting_techniques.md)); and the PoE2 figure in the cost table above. In the comments the author says RC has no limits on camera placement, answering a question about top-down cameras. The temporal far-cascade claim describes common practice in 3D implementations, not the paper or PoE2, which recompute every frame.
- **LIRIS GDL talk (French, https://projet.liris.cnrs.fr/origami/topics/gdl/gdl_talk_84/radiance_cascades.pdf, file dated 2026-03)** places RC in the history of probe GI. Irradiance volumes (Greger, Shirley, Hubbard and Greenberg, IEEE CG&A 18(2):32-43, 1998) discretize a 5D function, 3D position plus 2D direction; in 1996 this meant static scenes, precomputation and interpolation, and since about 2010 dynamic scenes with partial real-time updates. A table compares light-field probes (1024×1024 octahedral maps), DDGI (octahedral maps, a grid of varying resolution, alpha-blended ray tracing, an 8-probe cage with variance and Chebyshev bias terms) and an unnamed newer paper (8×8 irradiance and 16×16 visibility octahedral maps, one self-shadow bias term); these are in [related probe GI](related_probe_gi.md). The talk lists what classic probe methods leave undefined (spatial and directional resolution, interpolation between probes and between hierarchy levels), describes Lumen as four levels with no rule for their precision, and presents the penumbra condition and the interval constraint as RC's answer ([core theory](core_theory.md)). Since `N` texels at level 0 give `2N` for the whole hierarchy, it argues, a level 0 that can be stored and built in real time means the whole hierarchy probably can be too. It calls PoE2 a "2D + 1D" cascade in image space and sparse 3D RC a spatial hash of probes around the camera built by hardware ray tracing.

### Community site, wiki and tools

**radiance-cascades.com** (https://radiance-cascades.com/, source https://github.com/radiance-cascades/radiance-cascades.com, last commit 2025-10-11 by the GitHub user Raikiri) is a static page (`public/index.html`) with one interactive WebGL2 2D demo (`public/js/rc.js`, 2,237 lines, described in [2D articles and demos](2d_articles_and_demos.md#radiance-cascadescom-demo-and-osbornes-slide-demo)) and link lists. A second page, `public/index2.html`, is an unlinked draft: a styled header with the logo and GitHub and Discord icons, a "Resources" heading over two identical cards for the paper ("The paper that started it all"), and a WIP banner, with no script or demo. The GitHub organisation https://github.com/radiance-cascades holds only this repository and LegitScriptEditor ([notes](../sources/2026_rc_community_site_and_wiki.md)). The page lists:

- Papers: the original paper, Osborne and Sannikov's radiative transfer paper (arXiv 2408.14425) and the HRC paper (arXiv 2505.02041).
- Guides: GM Shaders parts one and two, SimonDev's video and demo, jason.today.
- Demos and implementations: fad's Shadertoy, tmpvar's playground, basic RC on LegitScript (`Scaling.ls`, with an orange emitting circle at the centre and a black occluding circle at `center + (150, 50)`), Yaazarai's Volumetric-HRC, Youssef Afella's Unity URP version.
- Utilities: MytinoDev's bilinear and forking fix (4clcWn), Kornel's calculator, mxacop's "parallel fix" XcfyDj (a diagram that computes no radiance, which the wiki's parallax-fix page links too), LegitScriptEditor and fad's HRC ray visualiser in Desmos.

**radiance.wiki** (https://radiance.wiki, source https://github.com/OrionReed/radiance-wiki, last commit 2026-03-26, f369b975a on main) is a Quartz 4.5.2 wiki by Orion Reed (OrionReed, the only trusted contributor; each page names its authors) with 39 Markdown pages in `content/`: home, contribution, 3 papers, 4 talks, 9 guides, 8 implementation pages, 6 technique pages, 4 variant pages and 3 tool pages, mostly short notes with links. The home page embeds the site's demo with the same controls, from a slightly different copy of `rc.js`, and links radiance-cascades.com. It credits RC to Sannikov at GGG for PoE2, first shown at ExileCon 2023, calls RC geometry-agnostic and noiseless in 2D, and calls extending it to 3D an open problem. Its "Start Here" list is SimonDev's video, jason.today, mxcop's fundamentals and the paper. Points where the wiki is wrong or loose:

- The home page says each level "doubles the ray count while halving the probe density", while the embedded demo multiplies rays by 4 per level by default.
- It dates ExileCon 2023 to November (see [above](#when-exilecon-2023-took-place)).
- The HRC pages give O(N·X²) memory, which they call the main barrier to 3D, without defining N or X.
- The UV-space page attributes X3XfRM to both "the original RC author" and Suslik, which agree with each other since Suslik is Sannikov, but Shadertoy credits Mathis.
- The 3D demo page links N6RP3r1M9g4 as 3D RC and says it is light on technical detail; the video is screen-space GI of a 3D scene computed in one frame, music only, with its facts in the description.

Its Shadertoy list links three entries as tag searches rather than shaders: Holographic RC (Suslik; the shader is 4ctczl), RC Diagram (Mytino; 4clcWn) and RC - Screen Space Probes (Mathis; lXByRh). Its other pages carry facts gathered in the topics: the paper pages (HRC at about 1.85 ms at 512² and 7.67 ms at 1024² on an RTX 3080 Laptop; Osborne and Sannikov's Appendix A bilinear fix and Figure 8 parallax fix; the original paper's predecessors HSSVGI (hierarchical screen-space variance-based GI, PoE1's GI above) and hierarchical screen-space shadow cascades, from ExileCon 2019), the talk pages (Goobley's DexRT slides on Kokkos, atmospheric sparsity, mipmapped upper cascades, OpenVDB-style Morton storage and about 40× GPU performance per watt over CPU, with the page saying the astrophysical context differs from game rendering but the storage and mipmapping transfer), the technique pages (bilinear fix, with images from Yaazarai's repository comparing vanilla and the fix; nearest and parallax fixes; pre-averaging, direction-first probes, sky integral; see [artifacts and fixes](artifacts_and_fixes.md) and [cascade layout](cascade_layout_and_merging.md)) and the variant pages (HRC, with "radial HRC" as an earlier community test of small perpendicular spacing; RC-guided NEE, which is vlam ([sampling and guiding](rc_for_sampling_and_guiding.md#vlam)); surfel RC as experimental, research-stage work on surfel probes rather than screen-space or volumetric grids, avoiding some volumetric memory problems but raising questions of distribution, coverage gaps and temporal stability; UV-space 3D, whose temporal merge causes lag and flicker a proper implementation could likely avoid). Its implementation pages are in the [people table](#who-built-what) below.

**LegitScriptEditor** (repository radiance-cascades/LegitScriptEditor, Vite, TypeScript and Monaco) is the browser host for Sannikov's experiments, a WebGL shader editor for arbitrary multi-pass setups with no backend dependency; demos load from GitHub with a `?gh=` parameter, such as `?gh=Raikiri/LegitCascades/Scaling.ls` ([wiki notes](../sources/2026_rc_community_site_and_wiki.md#legitscript-legitscripteditor)):

- LegitScript compiles to WebAssembly and emits WebGL2 (`#version 300 es`) shaders only. A script has `[declaration]`, `[include]` and `[blendmode]` sections and a `[rendergraph]` function `RenderGraphMain()`. A pass is a GLSL-like fragment function whose `out` parameters become color attachments and whose `sampler2D` parameters become samplers. Images come from `GetImage(size, format)` with rgba8, rgba16f or rgba32f (rgba32f is not filterable), and sliders and context values persist across frames.
- Each frame the module runs `RenderGraphMain()` and returns the pass invocations in call order; each is a full-screen triangle drawn into a framebuffer in sequence, with no compute dispatches and no barriers. Images persist between frames, which is what lets `Scaling.ls` read the previous frame's atlas. Image 0 is copied to the canvas with a `pow(x, 1/2.2)` encode. A pass recompiles only when its source changes, and a failed compile keeps the old program and maps the GLSL error line back to the script.
- The `?gh=` loader fetches `raw.githubusercontent.com/<user>/<repo>/refs/heads/<ref>/<path>` once at startup with `ref` defaulting to `master`. It never checks the response status, so a 404 page becomes the script; tags and commit hashes fail because the path always uses `refs/heads/`, although the README says they work; and the README's example parameter `&rev=master` is not the `ref` the code reads.

Because LegitScript has no compute and runs passes in a fixed order, the scripts built on it, like Shadertoys, tend to spread merges over frames; the frame lag in `Scaling.ls` comes from the host, not from RC (inference from the host's design).

**Other tools:** fad's HRC ray visualiser in Desmos (https://www.desmos.com/calculator/1syt8xa8xl, 2025-01-11) defines a recursive `g(p, d, i)` that, up to level `n = 4`, either splits a ray into two children with doubled direction `2d ± (0, 1/2)` or, when `p.x` is not a multiple of `2^(i+1)`, draws a segment from `p + k·d` to `p + d` and recurses from its end, so it draws the binary tree of HRC ray segments, with `k = −0.97` pulling each start back along its direction. kornel.ski/radiance computes interval lengths from penumbra angle, minimum light size and probe spacing ([core theory](core_theory.md)).

### News and discussion

The discussions below span 2023 to 2026: Hacker News threads, GitHub issues, Godot pull requests, the Unreal Engine forum and Lobsters; Reddit could not be read. Forum and thread comments are opinions unless they quote a measurement.

- **80.lv** ran two short posts ([notes](../sources/2024_rc_blog_posts_and_slides.md#80lv-news)). The first (2023-11-09) covers the paper and a 2D demo by Asbjørn Lystrup at 0.3 ms on a GTX 970 with no denoising or temporal accumulation, and relays Sannikov's 12 ms for 2, 102 and 1002 particles alike, which is the paper's Radiant 2D light-count test. The second (2024-04-08) shows Lystrup's sticky-slime sandbox in a custom C++ engine on Vulkan and DX11, lit with RC. Neither gives parameters. The wiki credits the same 0.3 ms GTX 970 demo to Mytino, so Mytino (MytinoDev) is probably Lystrup's handle (inference).
- **This Week in Bevy** (2024-07-22, by Chris Biscardi and the Bevy community, https://thisweekinbevy.com/issue/2024-07-22-bevy-jam-5-radiance-cascades-and-calculators-in-many-ui-kits) says interest grew after SimonDev's video, links two Bevy implementations and bevy_ridiculous_ssgi (a cascaded screen-space GI that never names RC, in [3D screen space](3d_screen_space.md)), and quotes the view that "3d Radiance Cascades don't seem to work out as well as 2d."
- **Hacker News** on Coppen's fundamentals article (https://news.ycombinator.com/item?id=41957008, 2024-10-26, 117 points, 33 comments; the article is 2D only and says RC extends to 3D). pornel (Kornel Lesiński) describes RC as combining few points × all angles, some points × some angles and all points × few angles, cheaper than brute force and enough for shadows unless lights are small; it traces fixed ray sets on regular grids every frame with no importance sampling, full 3D RC is too expensive beyond voxel scenes, and SPWI is the screen-space 3D form; Lesiński also cites the radiative transfer paper as astrophysics use. jasonjmcghee calls it a stack of grids halving in resolution, upper levels tracing many rays (up to 4096) far and lower levels few (4) near, at a cost McGhee's post puts near 16 path-tracer rays, with fixed-step tracing and a distance field adding some scene dependence, and corrects a commenter who described an octree. For off-screen light McGhee suggests, untested, rendering a larger view and cropping, sizing the extra margin per cascade by its interval, or computing only the top cascade as an approximation; Log_out_ suggests a second depth map from a twin camera at the far plane, with its lights, to catch occluded sources such as a light behind a column. TinkersW notes the article covers only Lambertian diffuse; abetusk links Sannikov's specular GI segment (https://youtu.be/TrHHTQqmAaM?t=2275), and a PoE2 demo video is linked (p1SvodIDz6E). The thread's PoE2 claims and off-screen ideas are in [3D screen space](3d_screen_space.md) ([notes](../sources/2026_rc_discussions.md#hacker-news-on-the-fundamentals-article-2024-10)).
- **Lobsters** has two RC stories and a handful of comments, with little technical content (searched 2026-10). On the GM Shaders story (https://lobste.rs/s/6o9elb, 2024-08) Lesiński summarized the idea: soft shadows need either good spatial resolution, as for AO, or good angular resolution, as for environment maps, but not both at once, which cuts rays and storage logarithmically; every surface can emit, and cost does not depend on the light count. In another thread (2024-08) Lesiński called RC cheap in 2D and doable in screen-space 2.5D, mentioned their own Bevy implementation, and suggested that because RC knows light directions per pixel it could feed Bevy's PBR shader for normal-mapped 2D textures. On the jason.today story (https://lobste.rs/s/qpxmar, 2024-10) a commenter pointed to Thomas Diewald's 2017 real-time 2D GI (https://vimeo.com/226554155, code somewhere in https://github.com/diwi/PixelFlow), and McGhee noted its quoted 2 billion rays per second on a GTX 970 against the far smaller ray count RC needs.
- **Reddit** threads could not be read, and the Unreal Engine forum thread "Radiance Cascades in Unreal" (2024 to 2026) has no implementation and no measurements; its arguments are under [positions on 3D RC](#positions-on-3d-rc).

## Research lines

| Line | Works | Topic |
|---|---|---|
| Foundations | Sannikov's paper (2023) | [core theory](core_theory.md) |
| Radiative transfer | Osborne and Sannikov (arXiv 2408.14425, RAS Techniques and Instruments 2025); Osborne's DexRT ray acceleration (arXiv 2025-11) | [volumetric and radiative transfer](volumetric_and_radiative_transfer.md) |
| Holographic RC | Freeman, Sannikov and Margel (arXiv 2505.02041, 2025-05); Sannikov's polygonal and block variants (2025 to 2026) | [holographic RC](holographic_rc.md) |
| Split RC | Freeman, Sannikov and Pitt-Francis (arXiv v2 2026-07) | [3D world space](3d_world_space.md) |
| Sampling and guiding | You's Reservoir Cascades (2026-07-23); Ikkala et al.'s RC path guiding in Tauray (ACM TOG 46(2), 2026); entropylost's vlam | [sampling and guiding](rc_for_sampling_and_guiding.md) |
| Screen probes with world intervals | Gavras, Kaméus, Abou Dan and Jensen, Dell'Ova, Kung (2025 theses); Gerassimov (DiGRA 2026) | [3D screen space](3d_screen_space.md) |
| Surface probes | Coppen's surfel RC (2025); X3XfRM (2024); Love and Deepspace (GDC 2026) | [3D surface probes](3d_surface_probes.md) |
| Volumes and medicine | Rulkens's CT thesis (TU/e, 2025) | [volumetric and radiative transfer](volumetric_and_radiative_transfer.md) |
| 2D teaching | Peter's bachelor thesis (2026) | [2D implementations](2d_implementations.md) |

Sannikov co-authors every paper line except the theses and the sampling work. The academic work so far is 2D (HRC, Split RC's 2D results, Reservoir Cascades), Split RC's 3D world-space method, which gives one diffuse bounce in a single frame with no temporal reuse and is timed per stage on Sponza and San Miguel ([Split RC](../sources/2026_freeman_split_radiance_cascades.md)), or 3D under conditions far from a game frame: astrophysics with minutes per solve, offline path guiding with temporal reuse, CT volumes recomputed on change, or student theses on screen probes with world intervals. Split RC is an arXiv preprint (v2, 2026-07), so no peer-reviewed paper yet describes a single-frame 3D world-space RC for games (inference from the works listed).

## Adoption: shipped, tried and turned down

| Project | Outcome | Details |
|---|---|---|
| Path of Exile 2 (GGG) | shipped screen-space RC, constant about 1 ms, no TAA | [3D screen space](3d_screen_space.md) |
| Love and Deepspace (Infold Games, Unity 2019 custom pipeline, over 80 million players) | shipped 3D surfel RC on phones, about 2 ms on an iPhone 12, after irradiance volumes and a simplified ReSTIR; converges over 28 frames per bounce | [3D surface probes](3d_surface_probes.md) |
| Core Keeper (Pugstorm, Unity) | named by the Split RC paper as a 2D game shipping RC. The game's own Steam notes never name the technique: a rewritten pipeline with reworked indirect light that spreads further and takes surface colour into account (0.5.2, 2023-02-08), AO that uses directional indirect light (0.7.0, 2023-10-04), and "a new indirect lighting solution that should be more accurate, faster and nicer looking" (1.0, 2024-08-27), with no technique, resolution or timing. The attribution rests on the paper | [Split RC](../sources/2026_freeman_split_radiance_cascades.md#context-from-related-work) |
| Kyora (Pugstorm, published by Chucklefish, unreleased) | also named by the Split RC paper as shipping 2D RC; its dev blogs (2025-03 to 2026-07) mention no GI technique, so the attribution rests on the paper | [Split RC](../sources/2026_freeman_split_radiance_cascades.md#context-from-related-work) |
| Enshrouded (Keen Games) | shipped a cascaded world-space probe cache with SDF tracing; not RC | [related probe GI](related_probe_gi.md) |
| Blackline Interactive | closed-source 3D RC in its own Metal engine on a 2019 MacBook Pro's Radeon Pro 5500M, claimed single-frame with no denoiser, though whether that covers its bounces is not shown ([not shown publicly](../sources/2026_blackline_interactive_spatium_rc.md#not-shown-publicly)); video HUDs show 10 to 28 ms of GI from a Cornell box to a 10.8 M-triangle Sponza, and the evidence points to probes on a generated surface atlas grown out of X3XfRM; the code is withheld until the author joins the industry | [3D surface probes](3d_surface_probes.md#a-generated-surface-atlas-blackline-interactive) |
| Bevy Solari (JMS55) | an early RC version (2024-02) was replaced by ReSTIR; the wiki reports artifacts and costs that were hard to manage in 3D, and calls it one data point, not a verdict on 3D RC | [related radiance caches](related_radiance_caches.md) |
| BeansEngine (joelmartin-dev) | RC and ReSTIR comparison removed from history in 2026-04 | [3D screen space](3d_screen_space.md) |
| kooch (lobinuxsoft, issue #114, closed 2026-05) | chose a surfel radiance cache because 3D RC is research-grade and "no shipping engine uses 3D RC"; its RC plan estimated 3 to 6 ms in 3D | [discussions](../sources/2026_rc_discussions.md#why-some-projects-chose-other-methods) |
| praxis (gariasf, issue #65, ADR 0020) | chose a DDGI-style probe clipmap: 4 camera-centered levels, about 32 MB, a 2 ms update budget for about 2,500 to 3,000 probes at 256 rays, a target of 90% convergence within 0.5 s of a light change, which needs hysteresis at or below 0.926 at 60 Hz | [related probe GI](related_probe_gi.md) |
| An unnamed game | found 3D RC too slow and used a two-bounce method | [light transport alternatives](light_transport_alternatives.md) |
| Godot | no RC in the engine; HDDAGI is the current GI work | [Godot integration](godot_integration.md) |
| Unreal Engine | forum discussion only | [positions](#positions-on-3d-rc) |
| Trillion3D (pasquelin, #1285) | planned Split RC as a replacement for a probe bounce that missed its error and time targets | [3D world space](3d_world_space.md) |

kooch's reason was out of date when written: the Love and Deepspace talk at GDC 2026 (March) had described a shipped 3D RC two months before the issue closed (derived from the dates). The praxis hysteresis bound follows from the target: after `n` frames at hysteresis `h` the remaining error is `h^n`, and `h^30 ≤ 0.1` gives `h ≤ 0.1^(1/30) ≈ 0.926` (derived).

2D RC shows up in many hobby engines, game mods and tools, from a Terraria mod to a YukkuriMovieMaker4 video effect ([2D implementations](2d_implementations.md)).

## Positions on 3D RC

- **Sannikov** (Raikiri, Godot PR #86267, https://github.com/godotengine/godot/pull/86267, 2024-07-12) never pitched 3D RC as the ultimate GI solution, or as practical by their own standards, and calls it a direct improvement over any regular or nested grid of radiance probes such as DDGI on nearly every measure; screen-space marching sees only on-screen occluders and lights, but screen-space cascades can store world-space intervals traced with a BVH, a distance field or a voxel marcher, at the cost of radiance living only on the depth surface, so volumes cannot be lit ([notes](../sources/2026_rc_discussions.md#sannikov-on-world-space-rc-godot-pr-86267)). Sannikov's later sparse 3D RC videos (2025) show world-space intervals for on-screen probes, single frame, at 60 to 100 fps on a laptop.
- **reduz** (Godot's technical lead, PR #86007, 2023-12) planned a step toward RC where world-space GI gives low-frequency light and a screen-space system adds higher frequencies and occlusion. Comments relaying reduz's posts on X (2024-07) say world-space RC is limited to 3 or 4 cascades by memory and occlusion and is closer to SSGI than to Lumen or SDFGI. A 2024 Unreal forum post relays reduz's reasons why 3D RC is hard: the 8-probe interpolation needs an occlusion test or light passes through walls, interiors get no light when the coarse cascades' spacing is larger than the room, and open worlds need the cascades in clipmaps.
- **A 2025 Unreal forum post** compares Lumen's screen-probe hierarchy to RC and notes Epic moved to screen probes plus world probes for caching and cost.
- **This Week in Bevy** (2024) and the wiki: 3D does not work out as well as 2D and is an open problem.
- **pornel** (2024): full 3D RC is too expensive beyond voxel scenes; SPWI is the practical 3D form.
- **Max Coppen** (2024-08): screen probes with world intervals catch offscreen light without the memory of a 3D grid, and leaks were rare in Coppen's tests ([3D screen space](3d_screen_space.md)).
- **kooch** (2026): research-grade, 3 to 6 ms estimated.

These views agree on the obstacle, the memory of a dense 3D cascade 0 and the occlusion-aware interpolation it needs, and differ on the remedy: screen probes with world intervals (Coppen, pornel, Sannikov in 2024), sparse world-space probes chosen per screen pixel (Sannikov in 2025), surfels (Love and Deepspace, Coppen's surfel RC), or leaving RC for caches (Solari, kooch, praxis). The paper already names the obstacle: for full 3D, cascade 0 alone is usually the deal breaker ([core theory](core_theory.md)).

## Who built what

| Person or handle | Work |
|---|---|
| Alexander Sannikov (Raikiri, Suslik) | PoE1 shadows and GI, the paper, PoE2's RC, the testbed Shadertoy line, depth-aware upscaling, LegitCascades, sparse 3D RC, co-author of the radiative transfer, HRC and Split RC papers, LegitScriptEditor with tmpvar |
| fad | mtlBzX, DlSfzz, the HRC ray visualiser in Desmos |
| Quinchilion | clVcD3, the ringing mask |
| Mytino (MytinoDev, probably Asbjørn Lystrup) | the fix diagram 4clcWn, the circle projection fix MfXyRj, a 0.3 ms 2D demo, the slime sandbox |
| Max Coppen (mxcop, mxacop, m4xc) | the fundamentals article, lcfcR2, XcfyDj, 4cffDX, SPWI (named in 2024-08), surfel RC (src-dgi) |
| Kornel Lesiński (kornelski, pornel) | the gear fix, RadiCalc, bevy_flatland_radiance_cascades |
| Yaazarai (Alex) | GM Shaders articles, pre-averaging, direction-first layout, Volumetric-HRC, PathTraced-Volumetrics |
| Jason McGhee | jason.today parts 1 and 2 |
| SimonDev | the video and Shaders_RadianceCascades |
| tmpvar (Elijah Insua) | implementation notes, 2D and 3D playgrounds, 3D grid, LegitScriptEditor |
| Christopher Osborne (Goobley) | RC for radiative transfer, DexRT, the slides |
| Rouli Freeman | HRC and Split RC papers (Oxford) |
| Adrian Margel | HRC co-author, line-space and diffusion demos |
| entropylost | amida (2D RC with bilinear fix, bounces, subsurface scattering and volumetrics, https://github.com/entropylost/amida, Rust/CUDA and NVIDIA only per the wiki, with the code on LuisaCompute, worlds from palette-mapped images), amitabha (the HRC reference), vlam (cascades guiding a path tracer's directions, filed by the wiki as RC-guided NEE), hrcviz |
| Mathis | NttSW7 (the analytic sky integral), X3XfRM, lXByRh, M3ycWt |
| Cody Bennett (codyjbennett) | three-rc, scy3Dd, the wfyyDz media line |
| youssef_afella | the Unity URP 2D version, 3cKczD, tfKyRw, WfyyDm, 33ycDm |
| Orion Reed (OrionReed) | radiance.wiki |
| Sohojoe | the Godot port (branches mix-Yaazarai-and-jason, shadertoy-port-suslik, jason-today-gi-pt1) |
| Ivan You | Reservoir Cascades |
| Julius Ikkala, Pekka Jääskeläinen, Markku Mäkitalo | RC path guiding in Tauray |
| Tianlong Ruan (Infold Games) | the Love and Deepspace GDC 2026 talk |

The wiki's implementation pages also list kornelski's and nixonyh's Bevy versions, Goobley/DexRT (C++20, Apache-2.0, Kokkos since v0.4.0 after YAKL, mipmapped upper cascades, sparse VDB-like storage, Morton order, 3D since v0.5.0), Yaazarai's two GameMaker repositories, Youssef-Afella's Unity URP version (HLSL), and as "other" radiance-cascades.com (called a 2D playground with fix toggles, though the demo's controls include none), SimonDev's demo, LegitScript basic RC, a futureengine2 gist on making RC independent of the ray-tracing method, tlegoc's Vulkan code, Hybrid46's C# with Raylib and OpenGL 3.3+, amitabha, Volumetric-HRC and Otavio Peixoto's OpenGL version.

### Repositories that hold nothing usable

These look relevant by name but hold no working GI RC code (each checked through all branches and history, 2026-10-18; [survey](../sources/2026_rc_repository_survey.md#checked-with-nothing-usable)):

| Repository | What it contains |
|---|---|
| Kollabiz/GoRadianceCascades | README, license and `.gitignore` only (1 commit); the README describes a 3D engine with RC diffuse GI that is not there |
| Temp-Name-Studio/Bevy-Voxel-Cascade | a one-line README ("Real Time GI Raytracing solution using Voxelization and Radiance Cascades") |
| willWallace-RIT/Radiancecascade3d | a README calling it a port of X3XfRM from "qwen base code"; the GDScript and GLSL do not run (undeclared identifiers, Godot 3 `PoolIntArray`, `gl_in` in a vertex shader, undeclared `TraceRay`); one fixed `1/256` step toward the sun, no cascades or merge |
| JavierSerranoDev/radiance-cascades-vulkan | a Visual Studio template printing "Hello World!" |
| Winstob/radiance-cascades | an AVL-balanced free list over index ranges in Rust with a test driver, a pass-through WGSL shader and a README titled "string-art"; only the package name mentions RC |
| shirokoff/raylib-radiance-cascades | a raylib window showing a 16 × 8 emitter-and-door cell texture (the door toggles every 3 s), the input stage of a 2D RC never written; committed binaries |
| j-vandy/SilkEngine | a Vulkan C++ wrapper with an ECS and a glTF duck demo; the README calls it a "Flatland Radiance Cascades rendering engine" and the `paint` branch is a 2D paint prototype meant for RC experiments, with no RC code |
| Heraclito-Q-Saldanha/RadianceCascades | a Bevy 0.19 plugin registering an empty `draw_system` after the opaque pass |
| vsensu/bevy_radiance_cascades | a Bevy 0.20 new-project template |
| cgorto/bevy-radiance-cascades | a Bevy 0.16 2D paint app with a naive screen-space raymarch: 16 rays per undrawn pixel, up to 128 texel steps, taking the first texel with alpha above 0.5; no cascades, intervals or merge |
| WillKirkmanM/radiance-cascade | a 2D canvas effect: 4 concentric radial-gradient discs per light, screen-blended, with shadow polygons extruded from rectangle edges; the "cascade" levels do not interact |
| tinycrops/Radiance-Cascades | a PyTorch stack of residual MLPs ("cascades") summed coarse to fine with early exit, plus a volume ray-marching demo of a learned field; it bundles Osborne and Sannikov's paper but implements no light transport |
| katyhuff/uiuc-arfc-2025-02 | a LaTeX technical-report template whose description mentions an RC report that is not there |

## Connections

**Constant cost is the thread through all of Sannikov's work.** The PoE1 shadows cap each pixel's light contributions and spread load evenly across levels; the PoE1 GI keeps the same sample count through every refinement step; RC's cost is constant in light count and scene content; the 2018 to 2021 side projects are O(1) precomputed ray casting and streaming at constant screen size; and the 2025 sparse 3D RC picks each tile's world resolution so that it covers about the same screen area, the rule of the cluster and octree streamers. The design target is a frame time that never spikes, which the 2019 talk states outright (60 to 100 fps over 300 fps that drops to 5) (inference from the sources above).

**The community fixed 2D quickly and 3D slowly.** Within a year of fad's first Shadertoy, the testbed, the bilinear, nearest, parallax and gear fixes, pre-averaging, direction-first layouts, the sky integral and interval calculators were public, and seven of the dated works above fall in the three weeks after SimonDev's video (2024-07-02 to 07-27), which supports This Week in Bevy's remark that the video drove interest. 3D work spread into many families (world grids, sparse hashes, screen probes with world intervals, surfels, UV charts) with few complete open implementations and no shared reference (derived from the timeline; the families are compared in [single-frame 3D RC](single_frame_3d_rc.md)).

**Names drift.** The same ideas appear as "radiance probe hierarchy" (ExileCon), "cascades" (2019 talk, for shadow levels), "screen probes, world intervals" or SPWI (Coppen), "cascaded image-space GI" (2023 video) and "spatial cascaded cache" (Enshrouded, not RC). The fixes have several names each: the "parallel fix" on radiance-cascades.com is the parallax fix, and the "RC V2" bilinear fix is Mytino's diagram.

## Single-frame assessment

**Single-frame computation is Sannikov's line and is the exception elsewhere.** The 2018 SSGI drops temporal reprojection, the 2022 2D GI caches nothing between frames, the 2023 image-space GI uses only the current frame, PoE2 has no TAA, and both 2025 sparse 3D RC videos compute everything from scratch each frame. The reason given is PoE's speed of change: reprojection would blur and make AO lag moving objects (2019 talk), and the game is too dynamic for TAA (2023 Q&A). The paper's own screen-probe variant with world intervals is the one Sannikov build that reprojects (0.1 to 0.5 s to converge). Of the shipped 3D RC, Love and Deepspace converges over 28 frames per bounce and spreads tracing over frames. So the only public evidence that a single-frame 3D world-space RC runs in real time is two videos on a laptop RTX 4090 with no published code, a visible seam between cascades and blocky tiles without interpolation, plus Blackline's surface-atlas builds, whose HUDs show 10 to 28 ms of GI on a 2019 laptop GPU without RT hardware while their single-frame operation rests on the author's word (inference from the sources above; the 3D topics judge each design).

**Shadertoy and LegitScript shaped the public code.** Both hosts run fixed passes once per frame, so most public 2D code merges across frames and settles over several frames, which readers then take as a property of RC. The paper, PoE2 and the 2022 demos merge top-down within one frame. Single-frame merging is a host limitation to remove, not a design choice to copy (inference; the frame counts are in [cascade layout](cascade_layout_and_merging.md)).
