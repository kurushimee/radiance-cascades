# Radiance cascades research

Notes on radiance cascades (RC) and the techniques around them, gathered from papers, theses, talks, articles, repositories and engine source, for reference while implementing RC in this project. `topics/` holds the synthesis by subject; `sources/` holds one note per source or group of related sources, with links. Godot engine behavior confirmed against the engine source goes in [docs/](../docs/), not here.

## Topics

Read in this order:

1. [core_theory.md](topics/core_theory.md): penumbra condition, intervals and merging, scaling laws, layouts and index math, gather.
2. [artifacts_and_fixes.md](topics/artifacts_and_fixes.md): ringing, gaps, leaks, edges, sky aliasing, banding, latency, and the fixes for each.
3. [3d_world_space.md](topics/3d_world_space.md): probes in the scene: dense grids, Split RC, surfels, erhe, leaks, temporal blending.
4. [3d_screen_space.md](topics/3d_screen_space.md): probes on the depth buffer: PoE2, screen probes with world intervals, depth-aware merging, flicker.
5. [scene_representation_and_tracing.md](topics/scene_representation_and_tracing.md): depth buffers, distance fields, voxels, BVHs, surfels and hardware ray tracing as interval tracers.
6. [godot_integration.md](topics/godot_integration.md): running compute in Godot 4.7.2, reading its buffers, and getting GI into shading.
7. [performance.md](topics/performance.md): measured times and memory across all implementations found.
8. [related_techniques.md](topics/related_techniques.md): DDGI, GI-1.0, hashed caches, Solari, bitmask SSGI, Enshrouded, SDFGI, HDDAGI, Lumen, Brixelizer GI, HSGI, daGI2, on-surface caches, voxel cone tracing.

## Main findings for a Godot implementation

- Two 3D RC designs have shipped: Path of Exile 2 (screen-space probes and tracing, about 1 ms, no temporal reuse) and Love and Deepspace (surfel scene, world-space probe clipmap, about 2 ms on an iPhone 12). Everything else found is research code.
- The most complete world-space design is Split RC (sparse hashed probes near visible surfaces, rays split by hit distance). wroughtinator's native build runs it as one GLSL compute source with a software BVH and integer atomics, which is the closest existing match to Godot's `RenderingDevice`.
- Godot 4.7.2 compute shaders have no ray queries and no float atomics, and the engine exposes neither its mesh buffers nor its SDFGI volumes, so an implementation brings its own scene structure and accumulates with fixed-point integers.
- The GI result composes correctly only through the material `IRRADIANCE` output, fed from a `Texture2DRD` global shader parameter; the engine's own GI and SSIL buffers cannot carry custom data into the opaque pass.
- In dense designs tracing is about 90% of RC cost. Cascade 0 spacing sets cost and memory, and halving it multiplies both by about 4; directions ×4 with probe spacing ×2 per cascade keeps every screen-space cascade the same size.
- gomezzz's world-space Godot addon is a working reference for the engine plumbing: render-thread scheduling, one compute list with barriers between cascades, and `Texture2DRD` outputs read by generated materials.
- Two open compute-only tracers fit `RenderingDevice` without ray queries: Godot's unmerged HDDAGI walks voxel bit masks with an integer hierarchical DDA, and AMD's Brixelizer traces sparse 8³ SDF bricks through a small AABB tree, with GLSL source under MIT. HSGI shipped the same kind of hierarchical voxel walk on phones and fills its voxels with radiance copied from the lit screen. Gaijin's open daGI2 does the same over an R8 narrow-band SDF clipmap built with integer atomics, and its screen probes trace a few world-probe sizes before reading a world probe clipmap, an RC-style interval hand-off. tinybvh's GLSL kernels cover the triangle BVH route, and Wicked Engine shows that BVH rebuilt on the GPU every frame. Lumen's account of thin-wall expansion, foliage coverage and tracer hand-offs applies to whichever is chosen.

## Sources

### Foundations

| Note | Content |
|---|---|
| [2023_sannikov_radiance_cascades_paper.md](sources/2023_sannikov_radiance_cascades_paper.md) | The founding paper: penumbra condition, intervals, scaling, early implementations |
| [2023_sannikov_exilecon_rendering_poe2.md](sources/2023_sannikov_exilecon_rendering_poe2.md) | ExileCon 2023 talk; PoE2's shipped RC and its cost |
| [2019_sannikov_poe_gi_talks.md](sources/2019_sannikov_poe_gi_talks.md) | Earlier PoE shadow and GI methods that led to RC |
| [2022_sannikov_youtube_rc_videos.md](sources/2022_sannikov_youtube_rc_videos.md) | Sannikov's RC videos, 2022 to 2026 |
| [2024_sannikov_legitcascades.md](sources/2024_sannikov_legitcascades.md) | Sannikov's 2D experiment scripts: bilinear and chronicl fixes |
| [2024_osborne_radiance_cascades_radiative_transfer.md](sources/2024_osborne_radiance_cascades_radiative_transfer.md) | RC for radiative transfer; ringing and the bilinear fix |
| [2025_osborne_dexrt_ray_acceleration.md](sources/2025_osborne_dexrt_ray_acceleration.md) | DexRT's sparse mipmapped tracing and merge variants |
| [2025_freeman_holographic_radiance_cascades.md](sources/2025_freeman_holographic_radiance_cascades.md) | Holographic RC (2D only) |
| [2026_freeman_split_radiance_cascades.md](sources/2026_freeman_split_radiance_cascades.md) | Split RC: sparse world-space 3D RC with evaluation |
| [2026_you_reservoir_cascades.md](sources/2026_you_reservoir_cascades.md) | Reservoir Cascades: resampled merges, leak reduction |

### Explainers and 2D implementations

| Note | Content |
|---|---|
| [2024_coppen_fundamentals_of_radiance_cascades.md](sources/2024_coppen_fundamentals_of_radiance_cascades.md) | 2D explainer with code fragments |
| [2024_mcghee_building_realtime_gi_part1.md](sources/2024_mcghee_building_realtime_gi_part1.md) | Naive 2D GI with jump flood distance fields |
| [2024_mcghee_building_realtime_gi_part2_rc.md](sources/2024_mcghee_building_realtime_gi_part2_rc.md) | 2D RC step by step |
| [2024_yaazarai_gmshaders_radiance_cascades.md](sources/2024_yaazarai_gmshaders_radiance_cascades.md) | GM Shaders series: pre-averaging, direction-first layout, timings |
| [2024_simondev_exploring_radiance_cascades_video.md](sources/2024_simondev_exploring_radiance_cascades_video.md) | Introductory video |
| [2024_tmpvar_rc_playground.md](sources/2024_tmpvar_rc_playground.md) | Interactive 2D and 3D demos |
| [2024_rc_blog_posts_and_slides.md](sources/2024_rc_blog_posts_and_slides.md) | Short posts, slides, the RadiCalc calculator, news articles |
| [2025_non_english_rc_overviews.md](sources/2025_non_english_rc_overviews.md) | Russian and Chinese overviews |
| [2023_rc_shadertoys.md](sources/2023_rc_shadertoys.md) | Reference Shadertoys: merge fixes, depth-aware upscaling |
| [2025_hrc_and_2d_reference_implementations.md](sources/2025_hrc_and_2d_reference_implementations.md) | HRC and 2D reference code |
| [2026_holographic_rc.md](sources/2026_holographic_rc.md) | HRC tracing, extensions, artifacts, variants and timings |
| [2026_merging_and_ringing.md](sources/2026_merging_and_ringing.md) | Merge fixes and their costs, scaling setups, formats, 2D timings |
| [2026_volumetric_rc.md](sources/2026_volumetric_rc.md) | Volumetric integration and merging, mip marching, thin-wall leaks |
| [2024_bevy_2d_rc_repositories.md](sources/2024_bevy_2d_rc_repositories.md) | Bevy 2D implementations |
| [2024_unity_2d_rc_repositories.md](sources/2024_unity_2d_rc_repositories.md) | Unity 2D implementations, analytic sky |
| [2024_godot_2d_rc_repositories.md](sources/2024_godot_2d_rc_repositories.md) | Godot 2D implementations and their pitfalls |
| [2026_software_mansion_typegpu_radiance_cascades.md](sources/2026_software_mansion_typegpu_radiance_cascades.md) | TypeGPU library: SDF and holographic runners |
| [2026_assorted_2d_rc_experiments.md](sources/2026_assorted_2d_rc_experiments.md) | CPU reference, adaptive ray skipping, HRC ports, bugs |
| [2026_peter_rc_2d_bachelor_thesis.md](sources/2026_peter_rc_2d_bachelor_thesis.md) | Bachelor thesis: per-pass 2D RC timings on an RX 7900 XTX, wider merge kernel |
| [2026_gigi_and_volume_rc_repositories.md](sources/2026_gigi_and_volume_rc_repositories.md) | Gigi 2D RC and RC for CT volumes |
| [2026_rc_community_site_and_wiki.md](sources/2026_rc_community_site_and_wiki.md) | radiance-cascades.com demo and link lists |

### 3D designs and implementations

| Note | Content |
|---|---|
| [2026_split_rc_implementations.md](sources/2026_split_rc_implementations.md) | chandra and wroughtinator's Split RC builds |
| [2026_erhe_world_space_rc.md](sources/2026_erhe_world_space_rc.md) | World-space RC reduced into DDGI maps, measured against DDGI |
| [2025_coppen_surfel_radiance_cascades.md](sources/2025_coppen_surfel_radiance_cascades.md) | Surfel RC |
| [2026_rc_conference_talks.md](sources/2026_rc_conference_talks.md) | Love and Deepspace (shipped surfel RC), GPC 2024, Enshrouded |
| [2024_tmpvar_rc_3d_grid.md](sources/2024_tmpvar_rc_3d_grid.md) | Dense world-space 3D grid |
| [2026_voxel_3d_rc_repositories.md](sources/2026_voxel_3d_rc_repositories.md) | Voxel clipmap and hardware RT 3D projects |
| [2026_tauray_rcpg_path_guiding.md](sources/2026_tauray_rcpg_path_guiding.md) | RC volume for path guiding; live probe culling |
| [2024_suslik_x3xfrm_surface_probe_rc.md](sources/2024_suslik_x3xfrm_surface_probe_rc.md) | Surface-probe 3D Shadertoy and a 2.5D design |
| [2025_gavras_screen_probes_world_intervals_thesis.md](sources/2025_gavras_screen_probes_world_intervals_thesis.md) | Thesis: screen probes with world intervals |
| [2025_kameus_spwi_probe_placement_thesis.md](sources/2025_kameus_spwi_probe_placement_thesis.md) | Thesis: one bilateral probe against min and max probes per tile |
| [2025_abou_dan_jensen_rc_vbgi_thesis.md](sources/2025_abou_dan_jensen_rc_vbgi_thesis.md) | Thesis abstract: screen probes traced with visibility bitmasks in a game |
| [2025_dellova_rc_performance_scaling_thesis.md](sources/2025_dellova_rc_performance_scaling_thesis.md) | Thesis: parameter scaling of 3D RC with hardware RT |
| [2025_kung_rc_vs_voxel_cone_tracing_thesis.md](sources/2025_kung_rc_vs_voxel_cone_tracing_thesis.md) | Thesis: screen-space RC against voxel cone tracing |
| [2025_bennett_three_rc.md](sources/2025_bennett_three_rc.md) | three.js screen probes with a BVH |
| [2026_screen_space_probe_repositories.md](sources/2026_screen_space_probe_repositories.md) | Metal, DX12 and Vulkan screen-probe engines |
| [2026_unity_unreal_rc_plugins.md](sources/2026_unity_unreal_rc_plugins.md) | Unreal bitmask RC and Split RC; Unity screen probes |
| [2026_engine_rc_design_documents.md](sources/2026_engine_rc_design_documents.md) | Hybrid designs in small engines, with measurements |
| [2026_gerassimov_rc_vs_unity_gi.md](sources/2026_gerassimov_rc_vs_unity_gi.md) | RC against Unity's SSGI and realtime lightmaps |
| [2026_rc_discussions.md](sources/2026_rc_discussions.md) | Claims and measurements from public threads |
| [2026_rc_repository_survey.md](sources/2026_rc_repository_survey.md) | About 55 repositories: surface-chart and SDF-brick 3D builds, 2D variants, dead ends |
| [2026_sparse_and_3d_rc.md](sources/2026_sparse_and_3d_rc.md) | Sparse 3D probes, GPU hash maps, ray splitting, tracing without hardware RT |
| [2026_screen_space_rc.md](sources/2026_screen_space_rc.md) | Screen-space RC optimizations, min/max probes, temporal stability |

### Godot

| Note | Content |
|---|---|
| [2026_godot_gi_internals.md](sources/2026_godot_gi_internals.md) | SDFGI internals, compositor hooks, buffer names |
| [2026_godot_indirect_diffuse_paths.md](sources/2026_godot_indirect_diffuse_paths.md) | Where custom diffuse GI can enter opaque shading |
| [2026_godot_compositor_effect_examples.md](sources/2026_godot_compositor_effect_examples.md) | CompositorEffect projects, normal and depth decoding |
| [2026_gomezzz_godot_3d_radiance_cascades.md](sources/2026_gomezzz_godot_3d_radiance_cascades.md) | World-space 3D RC addon for Godot 4.7 |
| [2026_phreakyx_godot_rc_gdextension.md](sources/2026_phreakyx_godot_rc_gdextension.md) | Untested GDExtension design with voxel cone tracing |
| [2026_godot_hddagi_dynamic_gi.md](sources/2026_godot_hddagi_dynamic_gi.md) | Unmerged HDDAGI: voxel bit masks, hierarchical DDA, probes, screen-probe draft |
| [2023_linietsky_godot_sdfgi_plan.md](sources/2023_linietsky_godot_sdfgi_plan.md) | reduz's SDFGI design deck: requirements, scrolling, hit caching, on-demand lighting, dynamic-object plan |

### Related techniques

| Note | Content |
|---|---|
| [2019_majercik_ddgi.md](sources/2019_majercik_ddgi.md) | DDGI probe grids |
| [2023_boisse_gi10_two_level_radiance_cache.md](sources/2023_boisse_gi10_two_level_radiance_cache.md) | GI-1.0 screen and world caches |
| [2019_binder_path_space_filtering_and_sharc.md](sources/2019_binder_path_space_filtering_and_sharc.md) | Hashed radiance caches |
| [2025_jms55_bevy_solari.md](sources/2025_jms55_bevy_solari.md) | Bevy Solari world cache |
| [2022_stachowiak_kajiya_gi.md](sources/2022_stachowiak_kajiya_gi.md) | kajiya: ReSTIR GI with a sparse irradiance cache placed and ranked by use |
| [2022_therrien_visibility_bitmask_ssgi.md](sources/2022_therrien_visibility_bitmask_ssgi.md) | Visibility-bitmask SSGI |
| [2014_mcguire_mara_screen_space_ray_tracing.md](sources/2014_mcguire_mara_screen_space_ray_tracing.md) | Depth-buffer ray marching |
| [2014_cigolle_octahedral_unit_vectors.md](sources/2014_cigolle_octahedral_unit_vectors.md) | Octahedral direction mapping and borders |
| [2006_rong_tan_jump_flooding.md](sources/2006_rong_tan_jump_flooding.md) | Jump flooding for distance fields |
| [2022_wright_lumen_siggraph_advances.md](sources/2022_wright_lumen_siggraph_advances.md) | Lumen: layered caches, distance fields, surface cache, timings |
| [2024_amd_brixelizer_gi.md](sources/2024_amd_brixelizer_gi.md) | Compute-only sparse SDF bricks and the GI built on them |
| [2023_lightspeed_hsgi_hierarchical_surfel_gi.md](sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md) | HSGI: sparse voxel bricks traced by HDDA, screen injection, mobile screen probes, PC ReSTIR GI |
| [2026_gaijin_dagi2_dynamic_gi.md](sources/2026_gaijin_dagi2_dynamic_gi.md) | daGI2 (Dagor Engine source): narrow-band SDF clipmap, voxels lit from the frame, screen probes handing off to a world radiance grid; daGI v1 timings |
| [2024_tatzgern_on_surface_radiance_caches.md](sources/2024_tatzgern_on_surface_radiance_caches.md) | Radiance caches stored on surfaces in texture space |
| [2026_compute_bvh_libraries.md](sources/2026_compute_bvh_libraries.md) | tinybvh GPU layouts and compute traversal kernels; Wicked Engine's per-frame GPU BVH build |
| [2026_light_transport_alternatives.md](sources/2026_light_transport_alternatives.md) | Line sweeping, short characteristics, cone sweeping, extended gathering, multi-bounce |

## Sources not read

| Source | Link | Reason |
|---|---|---|
| Rulkens, RC for medical volume data (TU/e thesis, 2025) | https://research.tue.nl/en/studentTheses/001b99c6-3cf9-4c84-a3f8-7bf98c94a2ab | PDF behind a bot check; its code is covered |
| Kelkar et al., RC for real-time 2D GI (IEEE ICWITE 2025) | https://doi.org/10.1109/icwite64848.2025.11307155 | paywalled, no abstract |
| Ikkala et al., RCPG (ACM TOG 2026) | https://doi.org/10.1145/3840291 | paywalled; its code is covered |
| Unreal Engine 5 Lumen tech blog | https://www.unrealengine.com/en-US/tech-blog/unreal-engine-5-goes-all-in-on-dynamic-global-illumination-with-lumen | HTTP 403; the SIGGRAPH slides are covered |
| Love and Deepspace talk, translated upload | https://www.bilibili.com/video/BV1gAdBBcE9B | HTTP 412; the talk itself is covered |
| Blackline Interactive 3D RC videos | listed in [2026_rc_conference_talks.md](sources/2026_rc_conference_talks.md) | no captions or details |
| Reddit and Lobsters threads | | blocked automated reads |

Shadertoy pages sit behind a bot check; their code was read from GitHub mirrors instead.
