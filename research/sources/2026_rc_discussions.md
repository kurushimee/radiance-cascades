# Radiance cascades in public discussions

Technical claims and measurements from Hacker News threads, GitHub issues, Godot pull requests and the Unreal Engine forum, 2023 to 2026. Comments are opinions unless they quote a measurement. Reddit and Lobsters blocked automated reads, so they are missing.

## Sannikov on world-space RC (Godot PR #86267)

The GitHub account Raikiri belongs to Sannikov (its paper repository names him, and it says so in the thread). In the HDDAGI pull request (https://github.com/godotengine/godot/pull/86267, comment of 2024-07-12) it says:

- He never pitched 3D RC as the ultimate GI solution, or as practical by his own standards.
- 3D RC is a direct improvement over any method that uses a regular or nested grid of radiance probes, such as DDGI, on nearly every measure.
- Screen-space RC with screen-space marching only sees on-screen occluders and lights. Screen-space cascades can still store world-space intervals, including offscreen geometry, if the rays are cast in world space with a BVH, a distance field or a voxel marcher.
- The limit of that approach is that radiance lives only on the depth-buffer surface, so it cannot light volumes.

Godot's view in the same threads: reduz (PR #86007, 2023-12) planned a step toward RC where the world-space GI gives low-frequency environment light and a screen-space system adds higher-frequency light and occlusion. Comments relaying his posts on X (July 2024) say world-space RC is limited to 3 or 4 cascades by memory and occlusion, and is closer to SSGI than to Lumen or SDFGI. No RC work entered the engine.

## Unreal Engine forum

The thread "Radiance Cascades in Unreal" (https://forums.unrealengine.com/t/radiance-cascades-in-unreal/1939802, 2024 to 2026) has no Unreal implementation and no measurements. A 2024 post relays reduz's reasons why 3D RC is hard: the 8-probe interpolation needs an occlusion test or light passes through walls, interiors can get no light when the coarse cascades' spacing is larger than the room, and open worlds need the cascades in clipmaps. A 2025 post compares Lumen's screen probe hierarchy to RC and notes Epic moved to screen probes plus world probes for caching and cost.

## Path of Exile 2 claims

- An HN commenter (Negitivefrags, 2024-10) says PoE2's GI costs 0.8 ms on an RTX 4090 at 4K on the High setting, the same for any scene, with no temporal accumulation and so no lag. Particles light nearby surfaces through the GI with no extra authoring.
- The same commenter says the input is screen-space but a 3D structure is built by marching the depth buffer, and data behind the camera is not needed because lights rarely sit there.
- Offscreen geometry is the usual objection: a light behind a column or in another room casts nothing. Suggested fixes in the thread are rendering a larger view and cropping, or giving each cascade only the range its interval needs.

## Implementer notes

- **Direction-first screen-space layout** (alexmalyutindev, unity-urp-radiance-cascades #13): each block of the texture holds one direction for all probes. Cascade `N` holds `4·2^N` view-aligned directions in rows and 4 depth rays per direction in columns. The buffer stores two probe sets side by side, one at the minimum and one at the maximum depth of each probe's tile, which steadies the merge under camera motion. The 16 depth samples per direction are integrated with "variance trapezoid integration" (from Shadertoy l3scz8) and grouped into 4 stored rays. `radianceSectorSize = 0.25/(1 << level)` is, in the author's words, just a `1/rayCount` factor. He calls gathering and upscaling the most crucial unfinished part, and the mode is still unstable under camera motion.
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

## Other implementations found in threads

| Link | What it is |
|---|---|
| https://github.com/Kosmokleaner/GigiRadianceCascades | HLSL RC in the Gigi rendering prototyping tool |
| https://github.com/ReneeR33/radiance-cascades-volume-rendering | RC adapted to 3D volume data |
| https://x.com/mxacop/status/1822851233708732579 | 3D RC showcase by Max Coppen (2024-08) |
| https://noamzeise.com/drafts/2025-05-10-dissertation.html | Honours project in Common Lisp and OpenGL: a fixed 3D probe grid was too slow, camera-projected probes interpolated badly, so the final version keeps probes in view space; no numbers |
| https://github.com/Raikiri/RadianceCascadesPaper | LaTeX source of the RC paper, with the PDF at `out_latexmk2/RadianceCascades.pdf` |
| https://www.youtube.com/watch?v=rG2aok2SdbU | Sannikov's world-space RC work in progress with hardware ray tracing |
| https://www.youtube.com/watch?v=bYTw3ISxgUw | Sannikov video cited at t=74 for polygon-based hardware RT RC |
