# Performance

Measured times and memory from every source that gave them. Hardware, resolution and what each number covers differ from source to source, so rows are rarely comparable to each other; the patterns in the first section hold across them. Figures marked "derived" were computed from the source's data, not stated in it.

## What the numbers show

- **Cascade 0 probe count sets the cost.** Halving the probe spacing quadruples the probe count and multiplied time by 3.7 to 4.0 in Dell'Ova, about 3 to 4 in Kung, and 3.5 in creikey's voxel RC (derived from their tables). Dell'Ova's 16 rays at spacing 1 and 64 rays at spacing 2 cost the same (24.74 against 24.78 ms) and use nearly the same memory (335.6 against 323.4 MB), which gives the rule that cost follows `rays₀/spacing²`.
- **Rays per probe scale a little below linear.** Going from 16 to 64 cascade 0 rays cost 3.3 to 4.0× in Dell'Ova.
- **Resolution scales with pixel count.** 1440p cost 1.59 to 1.79× of 1080p, against a pixel ratio of 1.78 (Dell'Ova).
- **Light count does not matter when emitters are scene data.** PoE2 costs the same for one fireball or a million; Radiant 2D costs about 12 ms with 2, 102 or 1002 lights.
- **Tracing is most of the cost in dense designs.** Dell'Ova's gather pass is 87 to 96% of RC time, and Kung names the ray march as the main cost. Sparse designs shift the cost to bookkeeping: in Split RC, tracing is 1.3 of 8.6 ms on Sponza and 4.5 of 11.5 ms on San Miguel, and probe setup, deposit and shading take the rest. In a 2D solver with one probe per pixel and cheap SDF tracing, the merge was the largest pass (37 to 41% of the frame against 25 to 27% for tracing) and the atlas copy grew faster than the pixel count ([Peter](../sources/2026_peter_rc_2d_bachelor_thesis.md)).
- **Long intervals cost the most when rays march fixed steps.** Kung's depth-buffer march took 4.9 ms in a small house and 30 ms in large outdoor scenes at the same settings, because long rays keep stepping until they hit. In DexRT's 2D solver the top cascade took 63.6% of the time and cascade 0 only 0.5%; letting each cascade march a coarser mip cut the time 3.5× ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md), [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md)).
- **Quality fixes have a price.** The bilinear fix traces 4× the rays and ran 4× slower in amida; some ringing fixes double the frame time (McGhee). Going the other way, tracing only every second or fourth ray of each group in the upper cascades cut 10 to 40% of rays at 36 to 68 dB PSNR against the full result ([2D experiments](../sources/2026_assorted_2d_rc_experiments.md)).
- **Hardware ray tracing is about 3.5× faster than a good software traversal** on the same Split RC workload (66 against 231 µs). Godot compute shaders cannot issue ray queries and its ray tracing pipeline is experimental (see [docs/rendering_device.md](../../docs/rendering_device.md)), so the hardware ray tracing rows below (DXR, OptiX, Metal) trace faster than a compute-only Godot build can.
- **Dense 3D grids run out of memory first.** Full grids took 960 MiB for a Cornell box (jumeder), about 1.5 GB at 192³ (volume RC), and 3.5 GiB for two atlases (tmpvar). Clipmapped and voxel-volume designs stayed under about 150 MB (EggyStudio 1.65 to 9.16 MB, creikey 12 MiB, jtbirdsell 148 MB), and screen-space RC at 1080p stayed under 500 MB with a spacing of 2 or more (Dell'Ova).

## 2D

| Project | Hardware | Setup | Time | Memory |
|---|---|---|---|---|
| [Radiant 2D, Sannikov](../sources/2023_sannikov_radiance_cascades_paper.md) | RTX 3060 | per-pixel GI | about 30 ms depending on quality; about 12 ms with 2, 102 or 1002 lights | |
| [Lystrup's demo](../sources/2024_rc_blog_posts_and_slides.md) | GTX 970 | no denoising or temporal accumulation | 0.3 ms | |
| [Sannikov's image-space prototype](../sources/2022_sannikov_youtube_rc_videos.md) | not stated | no denoiser | about 5 ms | |
| [Yaazarai, GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md) | RTX 3080 | 4 probes per pixel, 4 rays at cascade 0; position-first at 1024², direction-first at 1920×1080 | 29.91 and 25.95 ms, read as measured frame times from the on-screen timer; the post's own wording is ambiguous | |
| [Volumetric HRC, Yaazarai](../sources/2025_hrc_and_2d_reference_implementations.md) | RTX 3080 | 256², 512², 1024², 2048², 4096² | about 1, 1 to 2, 5 to 6, 9 to 11, 35 to 45 ms | out of memory at 8192² |
| [HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md) | RTX 3080 Laptop | 256², 512², 1024², 2048², fp16 | 0.55, 1.85, 7.67, 33.9 ms; a 52 spp path tracer took 98.6 ms at 1024² with 10× the error | dominated by the `T` structure, about `log₂X·4·X·Y·(r + t)` bytes |
| [Reservoir Cascades](../sources/2026_you_reservoir_cascades.md) | Apple-silicon laptop | 256², WebGPU | 120 fps | about 3× plain RC, one reservoir per bin |
| [sparse_rc_2d](../sources/2024_bevy_2d_rc_repositories.md) | | sparse task lists | statistics atomics alone cost about 1.5 ms from contention | 197 MB slab pool |
| [typegpu](../sources/2026_software_mansion_typegpu_radiance_cascades.md) | | 256², 512², 1024², 2048², scalar transmission | | 9, 38, 160, 672 MiB |
| [Sohojoe, Godot](../sources/2024_godot_2d_rc_repositories.md) | | 1280×736 at quality 0.5 | | about 60 MB per RGBA32F cascade texture |
| [tmpvar playground](../sources/2024_tmpvar_rc_playground.md) | | sized for the slider limits | | 512 MiB probe buffer allocated at startup |
| [Paul Stus](../sources/2026_rc_conference_talks.md) | not stated | 2D canvas | 78 fps without GI, 37 fps with it | |
| [Peter](../sources/2026_peter_rc_2d_bachelor_thesis.md) | RX 7900 XTX, OpenGL | one probe per pixel, 9 cascades, SDF scene; 720p, 1080p, 1440p, 4K | RC passes 0.73, 1.84, 3.42, 7.95 ms; a 3×3 merge kernel cost 54% more merge time than bilinear | atlas of 8× the pixel count, RGBA16F |

McGhee's estimate for brute force, not a measurement: 512 rays per pixel at 1024² is about 1 s per frame, about 100× over a 60 fps budget ([part 2](../sources/2024_mcghee_building_realtime_gi_part2_rc.md)).

The [merging](../sources/2026_merging_and_ringing.md) and [HRC](../sources/2026_holographic_rc.md) notes add unverified 2D figures. Against vanilla RC, the bilinear fix costs about 4× the rays, the parallax fix about 20% more time, nearest merging with forking about a quarter of the bilinear fix, and a two-tap diagonal merge cut one frame by 33%. Moving from RGBA32F to RG16F, R11G11B10F and R16F targets took one build from 81 to 240 fps at 768², because RC is memory bound. HRC with a 4×4 px light took 0.88 ms at 512²; HRC is also bandwidth bound, and keeping one transmittance channel or fewer probes along each plane saved 25 to 70%.

## 3D screen-space

| Project | Hardware | Setup | Time | Memory |
|---|---|---|---|---|
| [PoE2](../sources/2023_sannikov_exilecon_rendering_poe2.md) | not stated | top-down camera, depth-buffer march, no temporal reuse | about 1 ms, constant | |
| PoE2, [paper](../sources/2023_sannikov_radiance_cascades_paper.md) | GTX 1050 | | about 3 ms | |
| PoE2, [HN commenter](../sources/2026_rc_discussions.md) | RTX 4090 | 4K, High | 0.8 ms | |
| [Sannikov SPWI](../sources/2023_sannikov_radiance_cascades_paper.md) | RTX 3060 | world-space SDF march from screen probes | 30 to 50 ms, one to two orders of magnitude slower than PoE2's approach; 0.1 to 0.5 s to converge with reprojection | |
| [Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md) | RTX 3080, DXR | Sponza (262k triangles), 5 to 8 cascades, emission only | 1.94 ms to 241.56 ms; table below | 24 to 3610 MB |
| [Kung](../sources/2025_kung_rc_vs_voxel_cone_tracing_thesis.md) | RTX 3060, D3D11 | 1280×720, 6 cascades, depth-buffer march | probe every 4th pixel: 4.9 to 30 ms; every 2nd: 18 to 100 ms; every pixel: 70 to 295 ms | |
| [Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md) | RTX 2070, DXR ray queries | 2048×1024, probe every 4×4, 2×2 or 1 px; one probe or a min and max probe per tile | 9.72 to 13.34 ms at 4×4, 21.21 to 43.02 ms at 2×2, 68.03 to 158.85 ms per pixel; min and max probes cost 2 to 17% more | 8 to 256 MB |
| [Gavras](../sources/2025_gavras_screen_probes_world_intervals_thesis.md) | M1 MacBook Air, Metal RT | 1920×1080, 6 cascades | 32.77 to 39.87 ms for small scenes, 143.74 to 155.90 ms for Sponza | 147 to 408.5 MiB |
| [Abou Dan and Jensen](../sources/2025_abou_dan_jensen_rc_vbgi_thesis.md) | "modern hardware" | screen probes traced with visibility bitmasks, no temporal reuse | 2 ms lowest, 6 ms medium, 26 ms high | 0.03 to 3.9 GiB |
| [Alpha-Renderer](../sources/2026_screen_space_probe_repositories.md) | RTX 3070 | 1080p, 6 cascades, min/max depth pyramid | about 5.5 ms (README) | about 80 MB |
| [Unity URP RC](../sources/2026_gerassimov_rc_vs_unity_gi.md) | RTX 4060 Laptop | resolution not stated; whole-frame medians | 3.75 to 4.43 ms against 2.56 to 2.92 ms without GI, so RC adds about 1.2 to 1.8 ms (derived); Unity's SSGI frames took 6.94 to 9.62 ms | |

Dell'Ova at 8 cascades, RC passes only:

| Resolution | Spacing | Rays at cascade 0 | Time | VRAM | Gather share |
|---|---|---|---|---|---|
| 1080p | 4 | 16 | 2.36 ms | 34 MB | 87.0% |
| 1080p | 4 | 64 | 8.59 ms | 125 MB | 93.1% |
| 1080p | 2 | 16 | 8.66 ms | 133 MB | 93.2% |
| 1080p | 2 | 64 | 33.81 ms | 499 MB | 95.0% |
| 1080p | 1 | 16 | 34.04 ms | 519 MB | 95.1% |
| 1080p | 1 | 64 | 134.82 ms | 2019 MB | 95.7% |
| 1440p | 4 | 16 | 4.04 ms | 58 MB | 89.8% |
| 1440p | 2 | 16 | 15.36 ms | 238 MB | 94.1% |
| 1440p | 1 | 64 | 241.56 ms | 3610 MB | 95.8% |

Time and memory rise linearly with the cascade count: at 1080p with spacing 4 and 16 rays, 5 cascades took 1.94 ms and 24 MB. At 1080p, 62.5% of the 48 configurations ran under 16.67 ms; at 1440p, none with spacing 1 ran under 33 ms.

## 3D world-space

| Project | Hardware | Setup | Time | Memory |
|---|---|---|---|---|
| [Split RC](../sources/2026_freeman_split_radiance_cascades.md) | RTX 3080 Laptop, OptiX | hashed probes near visible surfaces, fp32, not micro-optimized | 8.6 ms Sponza, 11.5 ms San Miguel; cascade −1 adds 1.4 ms | |
| [Sannikov's sparse 3D RC](../sources/2022_sannikov_youtube_rc_videos.md) | laptop; laptop RTX 4090 | hashed world-space tiles for visible probes, no denoising or temporal accumulation | 60 to 100 fps with a screen-space marcher; 60 fps with hardware RT, unoptimized | |
| [chandra](../sources/2026_split_rc_implementations.md) | CUDA, hardware RT | 2^18 base probes | | about 1.1 GiB of fp32 buffers (from the code's formulas, not measured) |
| [owoDra Split RC test](../sources/2026_rc_discussions.md) | Radeon 8060S | ray traversal only | 66 µs hardware RT, 231 µs software (hash DDA plus 8-wide BVH) | |
| [Surfel RC, Coppen](../sources/2025_coppen_surfel_radiance_cascades.md) | Radeon 890M iGPU; RTX 4070 Mobile | 6 cascades, resolution not stated | surfel upkeep (spawn, hash, recycle) 2.45 ms on the 890M, 0.82 ms on the 4070 (derived sums); a README profile shows gather 5.35 ms and merge 2.04 ms on unstated hardware | |
| [Love and Deepspace](../sources/2026_rc_conference_talks.md) | iPhone 12 | surfels in a hash grid, gather at about 70% resolution | about 2 ms total GI; the full-resolution gather alone took 2.8 ms | |
| [erhe](../sources/2026_erhe_world_space_rc.md) | not stated | dense grid reduced into DDGI maps | an update costs 1.15 to 1.57× a DDGI update; 0.7 ms per million rays | |
| [gomezzz, Godot](../sources/2026_gomezzz_godot_3d_radiance_cascades.md) | RTX 4060 Ti | 72,012 triangles, software BVH, 1080p with 2× MSAA | whole frame median 6.24 ms, capped by VSync; 2,342,912 traced segments per update; BVH build on the CPU 1.22 s | 8.94 MiB of directions plus 0.84 MiB of atlases |
| [creikey](../sources/2026_voxel_3d_rc_repositories.md) | not stated, D3D11 | 640×360, voxel clipmap | GI 0.76 ms, of which tracing 0.52 ms; halving the cascade 0 spacing cost 3.5× | 12 MiB clipmap |
| [EggyStudio](../sources/2026_engine_rc_design_documents.md) | laptop GPU | 800×450, distance-field clipmaps plus screen probes, Low, Medium, High | 0.59, 0.74, 1.00 ms | 1.65, 4.38, 9.16 MB |
| [jtbirdsell voxel2026](../sources/2026_rc_discussions.md) | RTX 4090 | 1080p, 256³ voxel volume, worst case | 1.98 ms total, 0.26 ms of it the per-frame query; voxel cone tracing took 2.06 ms | 124 MB cascades plus 24 MB |
| [jumeder](../sources/2026_voxel_3d_rc_repositories.md) | DXR | full grid, 4 cascades, Cornell box | | 960 MiB, 126 M rays per frame |
| [Volume RC](../sources/2026_gigi_and_volume_rc_repositories.md) | | full grid, 192³ CT volume | | about 1.5 GB allocated |
| [tmpvar 3D grid](../sources/2024_tmpvar_rc_3d_grid.md) | | 7 layers of 4096² | | 1,792 MiB per atlas, 3,584 MiB for both |
| [tauray RCPG](../sources/2026_tauray_rcpg_path_guiding.md) | | luminance-only probes for path guiding | | about 325 MB at defaults |
| [Surface-chart RC](../sources/2026_rc_repository_survey.md) | RTX 2080 SUPER, OpenGL | Cornell box on 8 UV charts, 6 cascades, analytic tracing, RenderDoc replay | 28.6 ms on the full atlases, 5.95 ms after skipping padding; replay varies 2 to 5× | 100.7 MB of RGBA32F atlases |
| [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md) | RTX 4070 | 512×768 astrophysics model, 880 wavelengths | 95 s to 11.8 s per iteration (8×): mips 3.5×, sparsity 1.5× | mips cost 1.33× the base level in 2D, 1.14× in 3D |

Unverified 3D figures: sparse RC with hardware RT took 3 to 5 ms on Sponza on a laptop RTX 4090; an optimized software ray tracer ran about 4× slower than hardware RT on Apple M3; radix-sorting 1M keys took 0.16 ms on an RX 9070 XT; a screen-space optimization stack went from about 1000 ms naive to 10 ms with fp16, half resolution, sector casting and bitmasks; min/max SSRC with accumulation took 2.8 ms ([sparse and 3D](../sources/2026_sparse_and_3d_rc.md), [screen space](../sources/2026_screen_space_rc.md)). Line sweeping ran 1000 directions at 1080p in 40 ms ([alternatives](../sources/2026_light_transport_alternatives.md)).

## Related techniques

| Technique | Hardware | Time |
|---|---|---|
| [DDGI](../sources/2019_majercik_ddgi.md) | RTX 2080 Ti | 32×8×32 probes, 64 rays: 2.6 ms in all; sleeping probes saved 30 to 50% of update time |
| [GI-1.0](../sources/2023_boisse_gi10_two_level_radiance_cache.md) | RX 6900 XT, RTX 3080 | 1.9 to 3.1 ms at 1080p; 2.4 ms against Lumen's 2.6 ms in one UE5 scene |
| [On-surface caches](../sources/2024_tatzgern_on_surface_radiance_caches.md) | RTX 3090 Ti | 1.45 to 2.64 ms at 1080p against 1.78 to 2.56 ms for GI-1.0; 32 to 224 MB primary and 55 to 456 MB secondary cache |
| [Lumen](../sources/2022_wright_lumen_siggraph_advances.md) | PS5 | 1080p internal, GI and reflections: 2.77 to 4.63 ms with global SDF tracing, 6.38 to 11.31 ms with hardware RT in The Matrix Awakens; budgets 4 ms at 60 fps, 8 ms at 30 fps |
| [Godot HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md) | GeForce GTX 1650 | light update and probe tracing with a still camera: 0.93 ms against 2.43 ms for SDFGI |
| [HSGI](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md) | iPhone 13 Pro; RTX 3080 | mobile screen probes and voxel upkeep 3.18 ms per frame, plus 1.79 ms on clipmap shifts; PC at 4K with TSR: 8.53 ms of GI passes against Lumen's 9.63 ms, with diffuse denoising 2.65 ms against 0.64 ms of tracing |
| [daGI (Enlisted, 2019)](../sources/2026_gaijin_dagi2_dynamic_gi.md) | GTX 1070; Xbox One | 0.57 ms in all on the 1070; Xbox One 0.7 ms with one bounce or async, about 1.6 ms synchronous multi-bounce; voxel updates from 100k pixels under 0.2 ms; about 31 MB. Its open successor daGI2 records no timings |
| [Brixelizer GI](../sources/2024_amd_brixelizer_gi.md) | RX 7900 XTX, RTX 4080, RX 7600 XT | about 2 ms at 4K on the 7900 XTX, 2.2 ms on the 4080, 1.7 ms at 1080p on the 7600 XT; 128 MiB brick atlas |
| [tinybvh](../sources/2026_compute_bvh_libraries.md) | RTX 5080 Laptop, compute only | README claims up to 5 G rays/s in Sponza; its chart shows about 3 G rays/s nearest hit and 4 G any hit |
| [SHaRC](../sources/2019_binder_path_space_filtering_and_sharc.md) | | memory only: 2²² hash entries, 160 MiB, of which a still camera uses 10 to 20% |
| [Bevy Solari](../sources/2025_jms55_bevy_solari.md) | RTX 3080 | 8.2 to 14.5 ms at 1600×900 including 5.8 to 6.3 ms of DLSS-RR; world cache under 0.2 ms except 2.1 ms lighting in Bistro |
| [kajiya](../sources/2022_stachowiak_kajiya_gi.md) | RX 6800 XT, hardware RT | 1080p frame 8.4 ms: indirect diffuse 2.3 ms, irradiance cache 0.55 ms (under 16k entries), reflections 2.2 ms |
| [Visibility-bitmask SSGI](../sources/2022_therrien_visibility_bitmask_ssgi.md) | | 1.23 to 4.33 ms at 1080p depending on samples and radius, including a 0.33 ms denoise; half resolution about 2.7× cheaper (derived) |
| [Screen-space ray tracing](../sources/2014_mcguire_mara_screen_space_ray_tracing.md) | GeForce Titan; GeForce 650M | 25 steps per pixel at 1080p: 1.2 ms; 6.4 ms on the laptop GPU |
| [Enshrouded](../sources/2026_rc_conference_talks.md) | all targets including Steam Deck | fixed budgets of 100k, 250k or 500k rays per frame |
