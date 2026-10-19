# Blackline Interactive: Spatium radiance cascades GI

| | |
|---|---|
| Author | Blackline Interactive (X: @demonv559) |
| Date | 2025-05 to 2026-10 |
| Kind | Videos, posts and screenshots of a closed-source engine; no code, paper or talk |
| Links | https://www.youtube.com/@BlacklineInteractive, https://x.com/demonv559, https://t.me/s/blacklineinteractive, https://www.patreon.com/BlacklineInteractive, https://github.com/BlackLineInteractive |

One developer's engine, Black Engine (earlier Lucida Engine), with a 3D radiance cascades GI codenamed Spatium. It runs on a 2019 16-inch MacBook Pro whose AMD Radeon Pro 5500M (8 GB, 50 W) has no ray-tracing hardware. The author claims real-time 3D GI from RC with no TAA, temporal accumulation, denoiser, screen-space GI, DDGI, voxels or lightmaps, no light leaks, and quality near path tracing. The code and design stay closed until the author joins the games or graphics industry; the author says the code will be published then, and credits Sannikov as the inventor of RC.

No source states the design. This note records what the videos, their on-screen HUDs and panels, and the author's posts and replies show, as read from 2026-10-17 to 2026-10-19. A *claim* is the author's statement. *Observed* means read from a video frame or image. *(derived)* marks arithmetic on those numbers, and *(inference)* marks reconstruction. HUD times vary from frame to frame, so ranges are given where several frames were read.

## Sources read

Videos on the YouTube channel, with descriptions and comments (none has captions):

| Video | Date | Length | Title | Content |
|---|---|---|---|---|
| 9lSJju9MUVA, rvJh6Ct45z4, 2OfsVZuRs4k | 2025-05-26 to 05-31 | 1:03 to 7:01 | "Ray Tracing on Android with C++ — No RTX Needed!", "Real-Time Ray Tracing on Android" (twice) | ray tracing on an Android phone (Mali-G76) in Termux with Debian, C++, SDL2 and OpenGL ES ("NebelEngine") |
| eiLo8mW5gMA | 2025-08-20 | 9:39 | "Ray Tracing Beyond RTX (ARM64)" | VRT Engine pre-alpha 0.4: a hybrid path tracer (CRT), a rasterizer (GRT), a BVH and the author's own denoiser; C++17/20, OpenGL 4.3, SDL2, GLEW, ImGui, GLM, tiny_obj_loader, stb_image |
| kVhJs96bJ2I | 2025-11-17 | 0:53 | "Ray Tracing for Android/Linux" | the same tracer |
| ID_g-zTmKRw | 2026-06-10 | 3:35 | "I Made Real-Time Ray Tracing Work on Old AMD Hardware" | Whitted ray tracing on the 5500M at 1080×720 and 1280×720, 60 FPS; C++ with Metal, OpenGL or Vulkan and SDL2; "No TAA. No denoisers." |
| Q_sU9PjbypY | 2026-08-13 | 0:41 | "Did I write no-noise Ray Tracing on my MacBook?" | the same tracer |
| hTzKP-FQ8ng | 2026-08-17 | 1:38 | "Shadertoy RC GI demo" | a 2024 RC Shadertoy run natively in Lucida Engine ([below](#the-shadertoy-port-2026-08-17)) |
| O3C3aoVbTIk | 2026-08-29 | 3:33 | "Real-time Global Illumination on Radiance Cascades" | the world-probe build: Bistro and Sponza |
| s6C3pcUO8h0 | 2026-08-31 | 2:37 | "Radiance Cascades Global Illumination (not SSGI!)" | the same build: Bistro (about 2 M triangles), Sponza HD (about 230k) and Sponza 4K (5.7 M) |
| fWnQvWBIZTs, MoIYpK3ObSo | 2026-09-05 | 5:07, 1:30 | "Radiance Cascades 3D GI glass demo", "Radiance Cascades 3D GI Demo" | glass, dispersion and caustics |
| -fBe0ZIu39Q | 2026-09-12 | 20:00 | "Radiance Cascades Global Illumination - without TAA, SSGI, DDGI..." | the first atlas build: Sponza, Sponza 4K, Bistro, Cornell box; HUD and per-pass timings |
| KzzSkymLz0s | 2026-09-14 | 0:38 | "RCGI on Potato GPU 2019 MacBook" | a forest rally scene |
| IVga0oVt2EU | 2026-09-22 | 1:22 | "Radiance Cascades Dynamic Global Illumination" | Cornell box with the engine's inspector |
| GeKb8zDIUqs | 2026-09-25 | 0:34 | "Radiance Cascades real-time Global Illumination" | Cornell box against a path-traced still |
| WK_dEXWLrq8 | 2026-09-25 | 1:27 | "Radiance Cascades Global Illumination 3D" | a pillar hall with coloured walls, a skylight and windows, and a car |
| TTI1QoHlCHE | 2026-10-03 | 17:32 | "New fast Global Illumination"; the description is headed "Real-Time Radiance Cascades Global Illumination 3D" | pillar room, Cornell box, Sponza, Intel Sponza with ivy, Bistro; HUD |

Titles are as retrieved on 2026-10-17. On 2026-10-05 the author marked O3C3aoVbTIk "no longer a relevant idea" and s6C3pcUO8h0, -fBe0ZIu39Q and KzzSkymLz0s old versions.

Posts read: the Telegram channel (posts 392 to 551, 2026-08-11 to 10-17), the X account (posts of 2026-10-06 to 10-17 with their images), the Patreon page (its bio; no posts rendered) and the technical lines of the author's LinkedIn posts. The GitHub organisation holds 9 to 10 repositories, none about RC. The Lucida repository named in hTzKP-FQ8ng and the Whitted ray tracing repository named in ID_g-zTmKRw have been deleted.

## Timeline

| Date | Engine | Step |
|---|---|---|
| 2025-05 | NebelEngine | ray tracing on an Android phone |
| 2025-08 | VRT Engine 0.4 | path tracer with its own denoiser, rasterizer and BVH on OpenGL 4.3 |
| 2026-06 | Whitted tracer | Whitted ray tracing on the 5500M at 60 FPS and 720p, with no TAA or denoiser |
| 2026-08-17 | Lucida Engine pre-alpha | Whitted tracing on compute with analytic soft shadows and hemisphere AO, Metal with MetalFX; demo 0.3 (primitives, trochoidal water, volumetric fog) at 1971×1065 runs at about 60 to 100 FPS, Sponza 4K (about 5.7 M triangles) at 1080×720 at 15 to 30 FPS; a 2024 RC Shadertoy, most likely X3XfRM, runs natively |
| 2026-08-19, 08-20 | Lucida | the "first version" of the author's own RC GI: Sponza 4K at 1280×720 at 20 to 30 FPS, then 45 FPS (Telegram 426, 428) |
| 2026-08-29 | | the world-probe build (Telegram 435, O3C3aoVbTIk) |
| 2026-09-05 | | the glass and caustics demo |
| 2026-09-12 | | the atlas build with a HUD (-fBe0ZIu39Q) |
| 2026-09-18 | | Bistro at 1080p and 2K from 4 to 7 FPS up to 12 to 14 FPS (Telegram 468; frame title "RC-GI \| 12.7 FPS \| CPU 8.5 ms \| GPU 78.7 ms \| 2829207 tris") |
| 2026-09-22 | | the engine inspector (IVga0oVt2EU) |
| 2026-09-26 | | FXAA; mirrors now reflect light into the GI, shown as path tracing, RCGI now and RCGI before (Telegram 490, 491) |
| 2026-09-27 | | Intel Sponza with ivy (Telegram 497) |
| 2026-10-03 | | a faster build with 5 to 6 cascades (TTI1QoHlCHE) |
| 2026-10-09 | Black Engine 0.1.0 | "Black Engine with Spatium Radiance Cascades Global Illumination": C++, SDL3 and Metal, with OpenGL and Vulkan planned (Telegram 522, X) |
| 2026-10-11, 10-16 | | light-leak tests against path tracing (Telegram 525, 548, 549; X) |
| 2026-10-16 | | assets for a vertical slice to show the engine and Spatium (Telegram 547) |

A LinkedIn post from late September 2026 reports fixes to several shadow bugs and a 60 to 150% FPS gain.

## The Shadertoy port (2026-08-17)

hTzKP-FQ8ng runs a 2024 Shadertoy natively. Asked whether it is another author's shader, the author replies that it shows the shader running natively rather than in the browser, and that Lucida is now Black Engine with Spatium RC GI.

*Observed:* the window title is "Radiance Cascades 3D | 103 FPS | Time: 6.134s". The scene is a box room with red and green walls, an interior wall with round holes, a mirror sphere and a patterned window lit by the sun. The title and the scene match X3XfRM, "Radiance Cascades 3D" by Mathis (2024-11-02), the surface-chart RC with probes on the UV texels of the room's surfaces, whose notes record the box room, the interior wall with two round holes and the mirror sphere but not the wall colours or the window (inference; [X3XfRM](2024_mathis_x3xfrm_surface_probe_rc.md), [3D surface probes](../topics/3d_surface_probes.md#x3xfrm-mathis)). The author's own RC GI appears two days later, and the world-probe build's window title keeps the same format: "Radiance Cascades 3D | 1280x720 | 7 cascades | ~60 fps (gpu 3.7–16.6 ms)".

## Hardware and engine

- **Machine:** a 2019 16-inch MacBook Pro with an Intel Core i9-9880H and an AMD Radeon Pro 5500M with 8 GB ("8.0 GB, dedicated" in the engine's About dialog) at 50 W. The GPU has no ray-tracing hardware; the author notes that RT cores would make BVH traversal much faster. On this machine Mafia: Definitive Edition runs at 2 to 7 FPS at minimum settings, and Lumen does not launch (LinkedIn).
- **Black Engine 0.1.0** (About dialog in the X post of 2026-10-09; commit 3ce5c64, built Oct 9 2026, Debug): renderer "RC GI, Metal"; ImGui 1.93.0 WIP. Its libraries are Dear ImGui (docking), ImGuizmo, ImAnim, SDL 3, EnTT, Jolt Physics, GLM, nlohmann/json, cgltf, fast_obj, stb_image, meshoptimizer, bc7enc_rdo and tinybvh, plus one MIT-licensed entry whose name is not visible. The editor has a hierarchy, an inspector with physics settings, assets, a console and statistics.
- **Backends:** the glass demo names Metal, Vulkan 1.2+ and OpenGL 4.3+ Core sharing one scene definition and mesh loader; Black Engine runs on Metal, with OpenGL and Vulkan planned.
- **Rendering:** asked whether it is a raster engine with lighting and volumetrics through RC, the author answers yes, with deterministic Whitted ray tracing for glass and mirrors (also for the reflections on the cars). Materials use a standard BRDF; rough metals and subsurface scattering are not done. Anti-aliasing is FXAA 3, not MSAA, at native resolution without upscaling.

## The world-probe build (2026-08-29)

*Claims* (O3C3aoVbTIk description): world-probe GI, not screen-space; an alternative to DDGI without stochastic noise, boiling or temporal lag; 7 active cascades with 4 to 5 diffuse bounces computed in real time. Bistro (about 2 M triangles) runs at a stable 60 FPS at 720p to 1080p with the GPU at about 7.4 to 9.9 ms, and Sponza 4K (5.7 M triangles) at 50 to 60 FPS at 720p. Under s6C3pcUO8h0 a viewer asked why one point light and the sun took about 20 ms.

*Observed:*

- Panel "Diagnostics & Controls": resolution 1280×720, 7 active cascades, GPU 5.67 ms in one frame and 9.47 ms in another, 60.2 FPS, peak 10.0 ms, "Tracing Enabled", exposure.
- Section "World Probes (WIP)": Cell Size 1.00, Bounces 4 and a "Rebuild World Probes" button. Debug views: View (Shaded or Albedo) and "Show Cascade Level −1". Collapsed sections: "Sun Shadows" and "Cascade Schedule".
- GPU passes, measured per pass: gbuffer 3.873 ms (70%) and composite 1.632 ms (30%), 5.505 ms in all. Another frame: gbuffer 7.368, composite 1.885 and sun shadow cascades 0 to 3 at 4.040, 3.716, 2.664 and 1.930 ms, 21.603 ms in all.
- Scene: 2,829,226 triangles and 2,896,660 vertices in 1591 draws, 132 materials, 274 images, bounds 174×51×184 (diagonal 258.5). BVH: 1,723,357 nodes, 861,679 leaves, depth 32, 95.8 MB. Unified memory no; maximum buffer 3.5 GB; shader library `rc.metallib`.

The per-frame pass list has no GI pass, and the panel has a rebuild button and a cascade schedule, so this build's probes were most likely built on demand or over several frames and only sampled each frame (inference). Its numbers do not bear on the single-frame claims. The BVH is binary (nodes = 2·leaves − 1) with about 3.28 triangles per leaf, and 32 bytes per node plus 16 per triangle gives 95.76 MiB, matching the 95.8 shown (derived; a consistency check, not the layout).

## The glass demo (2026-09-05)

*Claims:* refraction with Fresnel, RGB dispersion with a Cauchy IOR, Beer–Lambert absorption, forward-splatted photon caustics, "cascaded irradiance caching" for indirect diffuse, and BVH ray tracing. The passes are cascaded irradiance gathering, filtering, photon caustic splatting, caustic filtering and final ray-traced shading. It runs at about 50 to 60 FPS at about 2K.

*Observed:* the overlay at 2560×1440 shows GPU 11.4 to 14.7 ms and 155 MB of 8176 MB VRAM allocated; the modes are "Clear Glass + Caustics" and "Frosted Rough Glass".

## The atlas build (2026-09-12 onward)

### Claims

- **-fBe0ZIu39Q:** based on Sannikov's RC "but with my own custom 3D architecture"; aimed at zero light leaks and stable performance on older GPUs; no TAA, SSGI, DDGI or denoising; "0ms temporal latency (no temporal accumulation / ghosting)"; near path-tracing quality. The opening card calls it an early build with minor visual bugs or seams in large scenes but no light leaks, and says hardware ray tracing with TAA would add 100 to 200 ms per frame in the same scenes.
- **KzzSkymLz0s:** avoids the light-leak and thin-mesh problems of Split RC, SSGI and DDGI; needs no TAA, denoiser or RT hardware. With no camera-originated rays, resolution barely matters: 720p and native 2K differ by about 7 FPS. It uses an "almost maximally optimized BVH", and its difference from path tracing is about 3 to 20%.
- **GeKb8zDIUqs, TTI1QoHlCHE:** "These aren't lightmaps... Lightmaps require a UV map to be created in advance."
- **TTI1QoHlCHE:** no TAA, SSGI, DDGI, voxels or lightmaps; not a game-ready solution; FXAA 3; native resolution; tested at Full HD and 2K on the 5500M; the code has never been released.
- **Patreon bio:** fast and scalable real-time RC GI without TAA, screen-space or DDGI-like methods or voxels, designed for budget GPUs and built for games; the goal is to finish the RCGI codenamed Spatium.
- **X (2026-10-06):** tested at 4K with FXAA, natively. **LinkedIn:** GI with no noticeable latency and without hardware RT.

### HUD and passes, 2026-09-12

*Observed* (-fBe0ZIu39Q). Sponza (262,266 triangles): "GI: 3 cascades, 2.04 M rays/f", VRAM 735 MB, "Atlas: 1024x1024 (19.9 cm/tex)", frame 35.82 ms (CPU 8.6, GPU 35.9). Sponza 4K (5,744,346 triangles): 3 cascades, 2.55 M rays per frame, VRAM 1721 to 1811 MB, RAM about 4890 MB, atlas 1024×1024 at 24.7 cm per texel. The HUD's GI time is 34.7 ms at GPU 39.7 ms in Sponza and 41.2 to 47.2 ms at GPU 57.2 to 64 ms in Sponza 4K.

GPU passes in ms, as listed by the pass panel (sorted by cost, not in execution order):

| Pass | Sponza, frame A | Sponza, frame B | Sponza 4K |
|---|---|---|---|
| cascade 0 | 4.55 | 4.92 | 7.28 |
| cascade 1 | 10.05 | 12.36 | 13.80 |
| cascade 2 | 10.24 | 11.29 | 13.72 |
| camera | 3.72 | 4.96 | 9.68 |
| irradiance filter | 2.62 | 3.15 | 2.85 |
| direct | 1.65 | 1.87 | 2.30 |
| gbuffer | 0.96 | 1.04 | 5.19 |
| gather | 0.59 | 0.74 | 0.52 |
| seams | 0.37 | 0.39 | 0.64 |
| present | 0.32 | 0.29 | 0.31 |
| total measured | 35.06 | 41.01 | 56.30 |

Two more Sponza 4K frames measured 63.55 and 59.66 ms with similar splits, the camera pass reaching 15.15 ms and cascade 1 15.98 ms.

### Inspector, 2026-09-22

*Observed* (IVga0oVt2EU, engine inspector):

| Group | Settings |
|---|---|
| Lighting | "Global Illumination: ENABLED"; scale buttons 0.5x, 1.0x, 1.5x, 2.0x; Intensity 1.00x; Skip Near Range 0.00; "Interval (texels)" 2.0; Normal Bias 0.50 (0.54 in another frame); Merge Cutoff 0.35; Filter Radius 0 taps; Filter Normal 0.90 |
| Sun and sky | Animate; elevation 0.90 rad (1.05 in another frame), azimuth 2.40 rad, intensity 2.5; sun colour; sky intensity 1.00; sky colour; exposure; emissive scale |
| Viewport | "ACCELERATION STRUCTURE — run with --bvh-debug to collect the boxes" |
| Diagnostic modes | Lit GI (key 1), Albedo (2), Normals (3), Irradiance (4), Atlas UV (5), Irrad ×0.1, Material Albedo, Material UV |
| Primary visibility | Raster G-Buffer or Ray Traced; checkboxes "Directional GI" and "Normal Mapping" |
| Resolution | window 2560×1440 rendered at 1920×1080; 50, 75, 100 and 150%; scale factor 0.75x |
| Object inspector | transform, material, metallic, roughness, specular, transmission, IOR 1.5, emissive |

The description calls it dynamic RC GI without TAA, SSGI or voxels at Full HD and 2K on the 50 W GPU.

### HUD, 2026-10-03

*Observed* (TTI1QoHlCHE). The HUD has three lines, "FPS | ms (CPU ? GPU ? GI)", "GI: N cascades, X M rays/f | VRAM | RAM" and "Scene: tris | Atlas: 128x128 (cm/tex, 0.0% lit) | Bounds", and a key bar "[F1: HUD | F2: Settings | F3: Inspector | F4: Passes | Tab: Memory | G: GI | 1-5: Modes]". Every scene shows "Atlas: 128x128" and "0.0% lit".

| Scene | Triangles | Bounds (m) | Texel | Cascades | Rays per frame | VRAM | RAM | FPS | GPU ms | GI ms |
|---|---|---|---|---|---|---|---|---|---|---|
| Pillar room | 278 | 40.80 × 9.40 × 25.80 | 9.7 cm | 6 | 5.10 M | 780 MB | 214 MB | 59.3 | 16.6 | 12.6 |
| Cornell box | 760 | 5.50 cube | 1.7 cm | 6 | 4.11 M | 722 MB | 292 MB | 59.9 | 15.4 | 12.1 |
| Sponza | 262,267 | 29.77 × 12.45 × 18.31 | 11.4 cm | 5 | 4.89 M | 1101 to 1202 MB | 630 MB | 38.6 to 50.3 | 18.4 to 25.8 | 11.4 to 18 |
| Intel Sponza with ivy | 10,809,928 | 36.25 × 19.89 × 23.77 | 13.3 cm | 5 | 6.15 M | 3717 MB | 5870 MB | 22.7 to 24.3 | 29.2 to 50 | 15.9 to 27.8 |

FPS values come from the frames where FPS was read, and the GPU and GI ranges include other frames. Across the frames read, the pillar room and Cornell box show GI times of 10.1 to 13.0 ms and CPU times of 10 to 15 ms. The HUD is hidden in the Bistro section. The irradiance debug views show smooth, blotchy, low-frequency surface irradiance, and indirect contact shadows are weak in every scene. Bistro shows black and white cuts, and light reaches the floor under one column.

### Comparisons with path tracing

- Telegram 475 and 489 (2026-09-24, 09-25) set offline path tracing beside the RC GI: a checker floor with coloured light under a pillar. GeKb8zDIUqs compares the Cornell box with a path-traced still, since this GPU cannot path trace in real time.
- Telegram 491 (2026-09-26) shows path tracing, RCGI now and RCGI before, after mirrors began reflecting light into the GI.
- Telegram 525 and the X post of 2026-10-11 show a light-leak test: white rooms of single walls in sunlight, Spatium smooth above and the path tracer grainy below. *Observed:* no light passes through the walls in either; Spatium's shadowed inner corners are darker and the sunlit wedge between two walls is softer. The author calls it "Not ideal". Telegram 548 and 549 (2026-10-16) repeat the comparison and the leak test.

### The author's technical replies

From the comments under TTI1QoHlCHE (2026-10-05) unless noted:

- **Leaks:** there are no light leaks. The enclosed Cornell box's walls are single planes and its corners stay dark; an earlier version did leak at the corners. The Bistro's black and white cuts are a bug in "the visibility check", and the light under a column comes from the column floating above the floor.
- **Known problems:** contact shadows from indirect light are "the only real problem", which a more powerful GPU could solve in theory; black or white geometric artifacts remain, and a further reply adds "black holes". A viewer suggested ambient occlusion where geometry meets, because the cascades' resolution is too coarse for contact.
- **Scaling:** an optimization for huge scenes, not enabled in the video, would weaken GI with distance and outside the view while keeping mirrors, and raise FPS. The author reports 30 to 40 FPS at native Full HD.
- **World space:** computing lighting in world space "is vastly more expensive than screen-space tricks, especially without temporal caching"; the author agrees it is full-scene GI.
- **Novelty:** most approaches need TAA or temporal accumulation against shadow flicker; the author has not found the same approach anywhere online. -fBe0ZIu39Q's comments add that this version "by its very design, it inherently has no light leaks".
- **Engine:** proprietary, and not ported to Godot.

## Derived numbers

Computed with a script from the HUD values above.

- **Rays per cascade**, assuming each frame's rays split equally over the cascades: 0.68 M (64.8% of 1024²) in Sponza and 0.85 M (81.1%) in Sponza 4K on 2026-09-12; 0.85 M (pillar room), 0.685 M (Cornell box), 0.978 M (Sponza) and 1.23 M (Intel Sponza) on 2026-10-03.
- **Where the time goes on 2026-09-12:** the three cascade passes take 70.8% of the measured pass time in Sponza and 61.8% in Sponza 4K.
- **Throughput on 2026-09-12**, rays per millisecond of each cascade pass (tracing and merging): cascade 0 at 149 and 117 M rays/s, cascades 1 and 2 at 62 to 68 M rays/s, all three at 82 and 73 M rays/s. Cascade 0 runs about twice as fast per ray as the upper cascades, as shorter rays would (inference).
- **Throughput on 2026-10-03**, rays per millisecond of the HUD's GI time, which also holds filtering, seams and gathering, so it bounds tracing from below: 405 M rays/s (pillar room), 340 (Cornell box), 272 to 429 (Sponza) and 221 to 387 (Intel Sponza).
- **Between the builds:** Sponza went from about 82 to 272–429 M rays per GI second, while the cascades went from 3 to 5, the texel density rose (19.9/11.4)² = 3.05×, and the HUD's atlas string changed. It is a trend, not a measured speed-up.
- **GI share of GPU time on 2026-10-03:** 55 to 79%.
- **Atlas coverage:** if each cascade traces one ray per occupied texel and the cm/tex figure is a texel's edge, the rays per cascade cover 198 m² in the Cornell box (its six 5.5 m walls are 181.5 m², plus the inner boxes), 8,000 m² in the pillar room (3,357 m² of box interior), 12,700 m² in Sponza on 2026-10-03 and 26,900 m² in Sponza on 2026-09-12. The Cornell box fits one ray per texel per cascade; the two Sponza builds disagree by 2.1×, so the relation is not established.
- **Interval reach:** with the inspector's 2-texel interval for cascade 0 and an assumed ×4 growth per cascade, cascade ends fall at 2, 10, 42, 170, 682 and 2730 texels. The scene diagonals on 2026-10-03 are 507 (pillar room), 560 (Cornell box), 325 (Sponza) and 359 (Intel Sponza) texels, so five cascades cross every scene and the 6-cascade scenes carry one more than this rule needs. The 2026-09-12 build's three cascades reach 42 texels against a 186-texel Sponza diagonal, so that build used another rule or a far-field fallback. The growth factor is not shown.
- **Memory:** 722 to 780 MB of VRAM in scenes of 278 and 760 triangles points to a fixed allocation of several hundred MB independent of geometry (inference).

## Reconstruction (inference)

The evidence points to RC on a surface atlas: X3XfRM's surface-chart design, generalized from an analytic room to arbitrary meshes. In this reading, probes live on the texels of an automatically generated atlas of chart UVs, separate from the material UVs. Each cascade traces one ray per atlas texel over the hemisphere of its probe, and the cascades scale over the atlas's 2D parameterization. Rays are traced in world space through a compute BVH, built with tinybvh at least from the 2026-10-09 build. Interval lengths are set in texels, and the merge includes a visibility test. Irradiance per texel is then filtered in atlas space with normal weights, seams are fixed across chart borders, and a per-pixel gather reads the atlas as a lightmap would be read. Direct light is a separate pass with shadow maps, and mirrors and glass use Whitted rays from the camera. The likely pass order is direct, cascades, irradiance filter, seams, gather, camera and present.

| Evidence | What it indicates |
|---|---|
| a native run of what appears to be X3XfRM two days before the first own version, with the same window title format | the starting point was surface-chart RC |
| "Atlas: 1024x1024 (19.9 cm/tex)", with the texel growing with the scene from 1.7 cm (Cornell box) to 24.7 cm (Sponza 4K) | a 2D atlas over surfaces with a fixed texel budget spread over the surface area |
| "Interval (texels)", "Normal Bias", separate "Atlas UV" and "Material UV" modes, an "Irradiance" mode, "Filter Radius (taps)" and "Filter Normal" | intervals measured on the atlas, probes offset from their surface, an atlas apart from material UVs, irradiance stored per texel and filtered with normal weights |
| passes named per cascade, "irradiance filter", "seams" and a 0.5 to 0.7 ms "gather" | lightmap-style storage with seam fixing and a cheap per-pixel lookup |
| "These aren't lightmaps... Lightmaps require a UV map to be created in advance" | the atlas is generated by the engine, and its content is computed live |
| no camera-originated rays; 720p and 2K about 7 FPS apart | cost set by the atlas, not by the screen |
| rays per cascade below 1024² on 2026-09-12, and the Cornell box's coverage match | one ray per texel per cascade, as in X3XfRM's layers |
| no leaks through single-plane walls; a "visibility check" causing cuts | probes cannot sit behind a wall, rays hit true geometry, and the merge tests visibility, perhaps with X3XfRM's parent hit-distance test |
| weak indirect contact shadows that a stronger GPU would fix | the texel (10 to 25 cm) is cascade 0's probe spacing, so occlusion below it is lost and a denser atlas would recover it |
| "cascaded irradiance caching" in the glass demo | irradiance cached on surfaces per cascade |
| smooth, blotchy irradiance debug views | a coarse atlas filtered in texel space |

Other families fit worse. Screen probes contradict the resolution independence and the "not SSGI" claim. A dense world grid contradicts the cm-per-texel atlas and the leak claim. Sparse world probes like Split RC contradict the atlas, and the author sets the work apart from Split RC. World probes with a cell size were the 2026-08-29 build, which the author dropped.

## Open questions

- How is the atlas generated and packed? None of the visible libraries is a chart generator; xatlas is the common MIT-licensed one, one MIT entry is unreadable, and meshoptimizer could simplify meshes for it.
- What do "Atlas: 128x128" and "0.0% lit" mean on the 2026-10-03 HUD, when the 2026-09-12 HUD showed "1024x1024" and the rays per cascade exceed 128² by 40 to 75 times?
- What are the direction layout per probe, the probe size per cascade and the growth factors, and what do "Merge Cutoff" (0.35) and "Skip Near Range" control?
- How do bounces work without history? The world-probe build had 4 bounces and a rebuild button; X3XfRM reads last frame's cascade 0 at each hit, one bounce per frame. Whether "0ms temporal latency" covers the bounces is not shown.
- What does "Directional GI" store per texel for normal mapping: a dominant direction, SH or something else?
- How do moving and skinned meshes enter the atlas and the BVH? IVga0oVt2EU is titled dynamic GI and its inspector edits transforms and materials, but the frames read do not show the atlas being rebuilt.
- How does the 2026-09-12 build's three cascades reach the far field, and what is the unused optimization for huge scenes?
