# Radiance cascades in public discussions

Technical claims and measurements from Hacker News threads, GitHub issues, Godot pull requests and the Unreal Engine forum, 2023 to 2026. Comments are opinions unless they quote a measurement. Lobsters threads are summarized at the end; Reddit could not be read.

## Contents

- [Sannikov on world-space RC (Godot PR #86267)](#sannikov-on-world-space-rc-godot-pr-86267)
- [Unreal Engine forum](#unreal-engine-forum)
- [Path of Exile 2 claims](#path-of-exile-2-claims)
- [Implementer notes](#implementer-notes)
- [Why some projects chose other methods](#why-some-projects-chose-other-methods)
- [Coppen's first 3D RC on X (2024-08)](#coppens-first-3d-rc-on-x-2024-08)
- [Other implementations found in threads](#other-implementations-found-in-threads)
- [Hacker News on the fundamentals article (2024-10)](#hacker-news-on-the-fundamentals-article-2024-10)
- [Lobsters](#lobsters)

## Sannikov on world-space RC (Godot PR #86267)

The GitHub account Raikiri belongs to Sannikov (its paper repository names Sannikov, and it says so in the thread). In the HDDAGI pull request (https://github.com/godotengine/godot/pull/86267, comment of 2024-07-12) it says:

- Sannikov never pitched 3D RC as the ultimate GI solution, or as practical by their own standards.
- 3D RC is a direct improvement over any method that uses a regular or nested grid of radiance probes, such as DDGI, on nearly every measure.
- Screen-space RC with screen-space marching only sees on-screen occluders and lights. Screen-space cascades can still store world-space intervals, including offscreen geometry, if the rays are cast in world space with a BVH, a distance field or a voxel marcher.
- The limit of that approach is that radiance lives only on the depth-buffer surface, so it cannot light volumes.

Godot's view in the same threads: reduz (PR #86007, 2023-12) planned a step toward RC where the world-space GI gives low-frequency environment light and a screen-space system adds higher-frequency light and occlusion. Comments relaying reduz's posts on X (July 2024) say world-space RC is limited to 3 or 4 cascades by memory and occlusion, and is closer to SSGI than to Lumen or SDFGI. No RC work entered the engine.

## Unreal Engine forum

The thread "Radiance Cascades in Unreal" (https://forums.unrealengine.com/t/radiance-cascades-in-unreal/1939802, 2024 to 2026) has no Unreal implementation and no measurements. A 2024 post relays reduz's reasons why 3D RC is hard: the 8-probe interpolation needs an occlusion test or light passes through walls, interiors can get no light when the coarse cascades' spacing is larger than the room, and open worlds need the cascades in clipmaps. A 2025 post compares Lumen's screen probe hierarchy to RC and notes Epic moved to screen probes plus world probes for caching and cost.

## Path of Exile 2 claims

- An HN commenter (Negitivefrags, 2024-10) says PoE2's GI costs 0.8 ms on an RTX 4090 at 4K on the High setting, the same for any scene, with no temporal accumulation and so no lag. Particles light nearby surfaces through the GI with no extra authoring.
- The same commenter says the input is screen-space but a 3D structure is built by marching the depth buffer, and data behind the camera is not needed because lights rarely sit there.
- Offscreen geometry is the usual objection: a light behind a column or in another room casts nothing. Suggested fixes in the thread are rendering a larger view and cropping, or giving each cascade only the range its interval needs.

## Implementer notes

- **Direction-first screen-space layout** (alexmalyutindev, unity-urp-radiance-cascades #13): each block of the texture holds one direction for all probes. Cascade `N` holds `4·2^N` view-aligned directions in rows and 4 depth rays per direction in columns. The buffer stores two probe sets side by side, one at the minimum and one at the maximum depth of each probe's tile, which steadies the merge under camera motion. The 16 depth samples per direction are integrated with "variance trapezoid integration" (from Shadertoy l3scz8) and grouped into 4 stored rays. `radianceSectorSize = 0.25/(1 << level)` is, in the author's words, just a `1/rayCount` factor. The author calls gathering and upscaling the most crucial unfinished part, and the mode is still unstable under camera motion.
- **RC against voxel cone tracing at the same scale** (jtbirdsell/voxel2026 #4, RTX 4090, 1080p, 256³ voxel volume, worst case): RC with scale 4 cost 0.17 ms volume, 1.55 ms build and 0.26 ms query, 1.98 ms in total; VCT cost 0.17 ms volume and 1.88 ms gather, 2.06 ms in total. RC cost follows probe count, not pixels, so the 0.26 ms query is the per-frame cost when cascades are not rebuilt. RC memory was 124 MB of cascades plus 24 MB of cubes. The largest RC pass was merging into cascade 0 (0.43 ms). Scale 2 cost 1.88 ms with 504 units of reach against 1.55 ms and 1364 at scale 4. Quality was not compared.
- **Software against hardware traversal for Split RC rays** (owoDra/real-time-gi-lab #3): the best software path (segment DDA over a hash plus a quantized 8-wide BVH) averaged 231 µs against 66 µs for hardware ray tracing, about 3.5×, on an AMD Radeon 8060S.
- **Split RC as a bounce replacement** (pasquelin/Trillion3D #1285): the existing camera-centered probe bounce (64 full-length rays per probe, SH2) had 18.6% mean error against a path-traced reference, target 10%, at 1.1 ms against a 0.8 ms budget. Split RC was planned as the alternative. A related issue (#1284) points out that a global epoch that resets all probes on any light change is wasteful; only probes within the light's old and new reach need a re-sweep, except for the sun and sky.
- **Portability bugs** (Far-Beyond-Pulsar/Helio): binding one texture as both storage output and sampled input (cascade output and parent, history read and write) is invalid in wgpu and needs ping-pong pairs. Some drivers reject `textureLoad` on depth textures or `textureLod` on shadow samplers, so depth was read from an R32F Hi-Z mip instead. Rebuilding bind groups every frame was a measurable cost.
- **Dark-scene banding** (an HN comment from a 2D game, 2025-10): RC lighting banded on very dark backgrounds; Valve's animated dithering fixed it with the least change in perceived brightness.
- **Transparency** (vpinball #1843): screen-space RC cannot pass light through transparent objects without hacks. The same comment calls RC an approximation limited to one bounce unless bounces are added.

## Why some projects chose other methods

- lobinuxsoft/kooch (#114, closed 2026-05): picked a surfel radiance cache because 3D RC is research-grade and no shipping engine uses 3D RC. Its RC plan estimated 3 to 6 ms in 3D.
- gariasf/praxis (#65, ADR 0020): chose a DDGI-style probe clipmap (4 camera-centered levels, about 32 MB) over RC, with a 2 ms update budget for about 2,500 to 3,000 probes at 256 rays, and a target of 90% convergence within 0.5 s of a light change, which needs hysteresis at or below 0.926 at 60 Hz.
- Bevy (jms55, 2024-02): an early RC-based version of Solari was replaced by a ReSTIR-based one.

## Coppen's first 3D RC on X (2024-08)

Max Coppen (mxacop) showed a first 3D RC on 12 August 2024 (https://x.com/mxacop/status/1822851233708732579), a scene of voxel cubes with one emissive cube. Coppen's replies in the thread describe the design:

- Probes sit on the depth buffer and are stored in 2D textures, but their intervals are traced in world space, so offscreen light is still caught without the memory of a 3D grid. Coppen named this SPWI, "screen probes, world intervals". Coppen knew of two or three other screen-space 3D implementations besides Sannikov's and Coppen's own.
- Each cascade casts one ray per pixel and five cascades were used, so the images cost the equivalent of 5 samples per pixel. Coppen expected to reach under 2, with more than half of the rays very short, and to improve data locality.
- Leaks were rare in Coppen's tests because probe rays connect well across cascades. A bilateral depth filter avoids edge artifacts; Coppen planned to replace it with min/max depth interpolation.
- It ran in real time but unoptimized, with a high base cost, and gave only single-bounce diffuse light with no tone mapping. Coppen had no 3D version of the 2D analytic sky integral.

## Other implementations found in threads

| Link | What it is |
|---|---|
| https://github.com/Kosmokleaner/GigiRadianceCascades | HLSL RC in the Gigi rendering prototyping tool |
| https://github.com/ReneeR33/radiance-cascades-volume-rendering | RC adapted to 3D volume data |
| https://x.com/mxacop/status/1822851233708732579 | 3D RC showcase by Max Coppen (2024-08) |
| https://noamzeise.com/drafts/2025-05-10-dissertation.html | A short write-up titled "3D Radiance Cascades" of an honours project, not a dissertation draft despite the URL, in the author's own Common Lisp and OpenGL framework, estimating ambient light: a fixed 3D probe grid was too slow for real time, probes in projection space that move with the camera had interpolation problems, so the final version keeps probes in view space, where world-space distances between probes are easy; it credits RC to Sannikov as GI without ray-tracing hardware, and its RC-against-SSAO section has screenshots only, with no algorithm details, parameters or numbers |
| https://github.com/Raikiri/RadianceCascadesPaper | LaTeX source of the RC paper, with the PDF at `out_latexmk2/RadianceCascades.pdf` |
| https://www.youtube.com/watch?v=rG2aok2SdbU | Sannikov's world-space RC work in progress with hardware ray tracing |
| https://www.youtube.com/watch?v=bYTw3ISxgUw | Sannikov video cited at t=74 for polygon-based hardware RT RC; the video is a 2023 ExileCon interview uploaded by another channel, and around 74 s it compares RTX with screen-space GI, with no such demo ([notes](2022_sannikov_youtube_rc_videos.md#interview-at-exilecon-2023)) |

## Hacker News on the fundamentals article (2024-10)

The thread on mxcop's "Fundamentals of Radiance Cascades" (https://news.ycombinator.com/item?id=41957008, 117 points, 33 comments) holds the PoE2 claims above and these points. The article itself is 2D only and says RC can be extended to 3D.

- pornel describes RC as combining few points × all angles, some points × some angles and all points × few angles, cheaper than brute force and enough for shadows unless lights are small; it traces fixed ray sets on regular grids every frame with no importance sampling; full 3D RC is too expensive beyond voxel scenes, and SPWI (world-space intervals from screen-visible probes) is the screen-space 3D form. Lesiński also cites arXiv 2408.14425 (Osborne's radiative transfer paper) as astrophysics use.
- jasonjmcghee calls it a stack of grids that halve in resolution, upper levels tracing many rays (up to 4096) far and lower levels few (4) near, at a cost McGhee's post puts near 16 path-tracer rays, with fixed-step tracing and a distance field adding some scene dependence, and corrects a commenter who described an octree. For off-screen light McGhee suggests, untested, rendering a larger view and cropping, sizing the extra margin per cascade by its interval, or computing only the top cascade as an approximation.
- Log_out_ suggests a second depth map from a twin camera at the far plane, with its lights, to catch occluded sources such as a light behind a column. TinkersW notes the article covers only Lambertian diffuse. abetusk links Sannikov's talk on specular GI (https://youtu.be/TrHHTQqmAaM?t=2275), and a PoE2 demo video is linked (p1SvodIDz6E).

## Lobsters

Lobsters has two RC stories and a handful of comments, with little technical content (searched 2026-10):

- On the GM Shaders story (https://lobste.rs/s/6o9elb, 2024-08), Kornel Lesiński summarized the idea: soft shadows need either good spatial resolution, as for ambient occlusion, or good angular resolution, as for environment maps, but not both at once, which cuts rays and storage logarithmically. Every surface can emit, and the cost does not depend on the number of lights.
- In another thread (2024-08) Lesiński called RC cheap in 2D and doable in screen-space 2.5D, mentioned their own Bevy implementation, and suggested that because RC knows light directions per pixel, it could feed Bevy's PBR shader for normal-mapped 2D textures.
- On the jason.today story (https://lobste.rs/s/qpxmar, 2024-10), a commenter pointed to Thomas Diewald's 2017 real-time 2D GI (video https://vimeo.com/226554155, code somewhere in https://github.com/diwi/PixelFlow). McGhee noted its quoted 2 billion rays per second on a GTX 970, against the far smaller ray count RC needs.
