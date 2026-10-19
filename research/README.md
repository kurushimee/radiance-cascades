# Radiance cascades research

Notes on radiance cascades (RC) and the techniques around them, gathered from papers, theses, talks, articles, repositories and engine source, for a Godot implementation of 3D global illumination from RC alone, computed in a single frame. `topics/` holds the synthesis by subject, with each fact stated in the topic that owns it and the conclusions drawn across sources marked as derived or inferred; `sources/` holds one note per source or group of related sources, with links. Godot engine behavior confirmed against the engine source goes in [docs/](../docs/), not here.

## Topics

Start with the conclusions, then read the rest in this order.

**Conclusions**

1. [single_frame_3d_rc.md](topics/single_frame_3d_rc.md): what the research says about single-frame 3D RC in Godot: evidence, where designs lean on time and what replaces it, the design families judged, budgets, ranked open problems.
2. [performance.md](topics/performance.md): measured cost by domain with links to each owning topic, rays per second, time per megapixel and bytes per probe normalized across sources, and per-frame ray, time and memory budgets.

**The method**

3. [core_theory.md](topics/core_theory.md): penumbra condition, intervals, the merge operator, shift and extend, scaling laws, memory and cost, band limits, using the cascades.
4. [cascade_layout_and_merging.md](topics/cascade_layout_and_merging.md): probe placement, direction maps, intervals, cascade counts, storage layouts, merge kernels, cascade −1, final gather, formats, parameter tables.
5. [artifacts_and_fixes.md](topics/artifacts_and_fixes.md): ringing and the bilinear, straight-ray and cheaper fixes; gaps, leaks, edges, sky aliasing, banding, small lights, recurring bugs, debugging.
6. [holographic_rc.md](topics/holographic_rc.md) and [holographic_rc_implementations.md](topics/holographic_rc_implementations.md): HRC theory, tracing, extensions, variants, the cost model and every code.
7. [volumetric_and_radiative_transfer.md](topics/volumetric_and_radiative_transfer.md): radiative transfer, DexRT, volumetric merging, mip marching, thin-wall leaks, CT volumes, spectral work.

**2D**

8. [2d_implementations.md](topics/2d_implementations.md): 2D scene representations and every 2D code's design, formats and timings.
9. [2d_articles_and_demos.md](topics/2d_articles_and_demos.md): GM Shaders, jason.today, the community demo, tmpvar's playground and other explainers.
10. [2d_shadertoys.md](topics/2d_shadertoys.md): the Shadertoy lineage, fixes and frameworks.

**3D**

11. [3d_world_space.md](topics/3d_world_space.md) and [3d_world_space_implementations.md](topics/3d_world_space_implementations.md): dense grids, Split RC, sparse hashed probes, ray splitting, leak defences, every world-space code.
12. [3d_screen_space.md](topics/3d_screen_space.md), [3d_screen_space_theses.md](topics/3d_screen_space_theses.md) and [3d_screen_space_implementations.md](topics/3d_screen_space_implementations.md): PoE2, screen probes with world intervals, min/max probes, depth-aware merging, the theses and the screen-probe codes.
13. [3d_surface_probes.md](topics/3d_surface_probes.md): surfel RC, Love and Deepspace, UV-chart RC, on-surface caches.
14. [rc_for_sampling_and_guiding.md](topics/rc_for_sampling_and_guiding.md): Reservoir Cascades, RCPG and tauray, vlam, RC-guided sampling.
15. [scene_representation_and_tracing.md](topics/scene_representation_and_tracing.md): depth buffers, distance fields, voxels and HDDA, BVHs in compute, surfels, hardware RT, shading the hit.

**Godot**

16. [godot_integration.md](topics/godot_integration.md): compute scheduling, frame order and hooks, buffers, where GI enters shading, SDFGI, fog, HDDAGI.
17. [godot_projects.md](topics/godot_projects.md): gomezzz's 3D addon, Phreakyx, 2D wiring, compositor effect projects.

**Related techniques**

18. [related_probe_gi.md](topics/related_probe_gi.md): irradiance volumes, light propagation volumes, light-field probes, DDGI, Enshrouded, voxel cone tracing.
19. [related_radiance_caches.md](topics/related_radiance_caches.md): irradiance caching, path space filtering, SHaRC, GI-1.0, kajiya, Bevy Solari, GIBS.
20. [related_engine_gi.md](topics/related_engine_gi.md): Lumen, Brixelizer GI, daGI2, HSGI.
21. [related_screen_space_gi.md](topics/related_screen_space_gi.md): LSAO, horizon-based indirect lighting, PoE1's GI, visibility-bitmask SSGI.
22. [light_transport_alternatives.md](topics/light_transport_alternatives.md): line sweeping, short characteristics, cellular automata, transforms, wave optics, caustics, multi-bounce.

**Background**

23. [history_and_landscape.md](topics/history_and_landscape.md): origins, timeline, community, adoption, positions on 3D RC, who built what.
24. [supporting_techniques.md](topics/supporting_techniques.md): glossary of the sampling, mapping, resampling, structure, traversal, transport, format and metric terms used across the topics.

## Main findings for a Godot implementation

These summarize [single_frame_3d_rc.md](topics/single_frame_3d_rc.md), which gives the evidence for each.

- **RC needs no history.** It is deterministic and its cost does not depend on light count. The temporal reuse in public code comes from host limits, cost spreading, bounce feedback and hiding aliasing, each with a same-frame replacement at a known price.
- **Single-frame 3D RC is proven in two settings.** Path of Exile 2 ships screen-space RC at about 1 to 3 ms with no temporal reuse, and Split RC runs sparse world-space RC in 8.6 to 11.5 ms with hardware ray tracing. Neither setting is Godot's, where compute shaders cannot issue ray queries.
- **The tracer decides the cost.** Tracing is 87 to 96% of RC time in Dell'Ova's screen-probe runs, and the main cost in Kung's. At 1080p a 4 ms budget buys 4 to 12 M rays at 1 to 3 G rays per second, which fits screen probes at 4 to 8 px spacing or a few rays per pixel, but not a dense 128³ grid. Under `RenderingDevice` only a floor exists: 0.375 G segments per second, from gomezzz's whole-frame time.
- **The evidence favours a hybrid:** a screen-space near field over world-locked world-space cascades, sparse near surfaces or in a bounded clipmap. It reaches off-screen light, keeps the error pattern fixed under camera motion and gives screen hits a same-frame radiance source.
- **Hit lighting is the Godot-specific obstacle.** At PRE_OPAQUE this frame's lit colour does not exist, Forward+ has no albedo buffer, and shadows are drawn after the PRE_OPAQUE callbacks. A single-frame solve lights its hits from emission and its own shadow rays or per-frame light injection.
- **Lagged bounces have no cheap replacement.** One bounce plus a sky term is the single-frame baseline; each further bounce costs another solve.
- **Parameters with evidence behind them:** ×4 directions and ×4 intervals per cascade, 32 cascade 0 directions, a cascade 0 interval of 1.6 to 1.7 spacings, a nested equal-area direction map, a trilinear merge with a binary visibility test, one dispatch per cascade from the top with two live buffers, 6×6 irradiance tiles, RGBA16F.
- **The composite goes through `IRRADIANCE`,** with `E/π`, in every opaque `ShaderMaterial`; SSAO multiplies on top and should be off. Accumulation uses 32-bit integer atomics, and Vulkan guarantees only 128 MiB per storage buffer.
- **Code to learn from:** gomezzz's Godot addon for the engine plumbing; wroughtinator's native Split RC build (one GLSL compute source, software BVH, integer atomics); HDDAGI's integer hierarchical DDA over voxel bits; Brixelizer's MIT GLSL brick tracer; tinybvh's GLSL kernels and Wicked Engine's per-frame GPU BVH.

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
| [2024_peixoto_opengine_2d_rc.md](sources/2024_peixoto_opengine_2d_rc.md) | OPEngine 2D RC page and OpenGL code |

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
| [2024_mathis_x3xfrm_surface_probe_rc.md](sources/2024_mathis_x3xfrm_surface_probe_rc.md) | Surface-probe 3D Shadertoy and a 2.5D design |
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
| [2025_rulkens_rc_medical_volume_data_thesis.md](sources/2025_rulkens_rc_medical_volume_data_thesis.md) | Thesis: 3D RC for medical volume data, single scattering, mip skipping |

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
| [1996_light_field_and_lumigraph.md](sources/1996_light_field_and_lumigraph.md) | Light field rendering and the Lumigraph: two-plane line space |
| [2005_gorski_healpix.md](sources/2005_gorski_healpix.md) | HEALPix equal-area sphere pixelization |
| [2007_umenhoffer_layered_distance_maps.md](sources/2007_umenhoffer_layered_distance_maps.md) | Layered distance cube maps for reflections and refractions |
| [2008_clarberg_equal_area_sphere_mapping.md](sources/2008_clarberg_equal_area_sphere_mapping.md) | Equal-area octahedral sphere mapping |
| [2008_jarosz_radiance_caching_participating_media.md](sources/2008_jarosz_radiance_caching_participating_media.md) | Radiance caching in participating media |
| [2008_ward_krivanek_irradiance_caching.md](sources/2008_ward_krivanek_irradiance_caching.md) | Irradiance and radiance caching: split sphere, gradients, production fixes |
| [2010_kaplanyan_cascaded_light_propagation_volumes.md](sources/2010_kaplanyan_cascaded_light_propagation_volumes.md) | Cascaded light propagation volumes; irradiance volumes |
| [2011_crassin_voxel_cone_tracing.md](sources/2011_crassin_voxel_cone_tracing.md) | Voxel cone tracing |
| [2011_crassin_gigavoxels_thesis.md](sources/2011_crassin_gigavoxels_thesis.md) | GigaVoxels: sparse voxel octrees with ray-guided streaming |
| [2013_timonen_line_sweep_ambient_obscurance.md](sources/2013_timonen_line_sweep_ambient_obscurance.md) | Line-sweep ambient obscurance |
| [2015_wang_wavelet_point_based_gi.md](sources/2015_wang_wavelet_point_based_gi.md) | Wavelet point-based GI: Haar trees over directions |
| [2016_berhard_gpu_line_sweeping_thesis.md](sources/2016_berhard_gpu_line_sweeping_thesis.md) | Thesis: a GPU line sweeping framework |
| [2017_mcguire_light_field_probes.md](sources/2017_mcguire_light_field_probes.md) | Light-field probes with distance moments |
| [2018_mayaux_horizon_based_indirect_lighting.md](sources/2018_mayaux_horizon_based_indirect_lighting.md) | Horizon-based indirect lighting |
| [2018_vasiou_ray_tracing_performance.md](sources/2018_vasiou_ray_tracing_performance.md) | Where ray tracing time and energy go |
| [2021_lambru_realtime_gi_game_engines_comparison.md](sources/2021_lambru_realtime_gi_game_engines_comparison.md) | Review of real-time GI in game engines |
| [2021_majercik_ddgi_resampling.md](sources/2021_majercik_ddgi_resampling.md) | DDGI with ReSTIR-style resampling |
| [2021_pixelmager_depth_aware_upscaling.md](sources/2021_pixelmager_depth_aware_upscaling.md) | Depth-aware upscaling gist |
| [2021_seed_gibs_surfel_gi.md](sources/2021_seed_gibs_surfel_gi.md) | GIBS surfel GI and PICA PICA |
| [2021_spectral_imaging_in_production.md](sources/2021_spectral_imaging_in_production.md) | Spectral rendering in production |
| [2025_peters_jackknife_transmittance.md](sources/2025_peters_jackknife_transmittance.md) | Jackknife transmittance estimation |
| [2026_gpu_hash_tables_and_sorting.md](sources/2026_gpu_hash_tables_and_sorting.md) | GPU hash tables, spatial hashing, sorting and Morton codes |
| [2026_sweep_and_short_characteristics_solvers.md](sources/2026_sweep_and_short_characteristics_solvers.md) | Sweep and short-characteristics solvers, grid visibility |

## Sources not read

| Source | Link | Reason |
|---|---|---|
| Greger, Shirley, Hubbard and Greenberg, "The Irradiance Volume" (IEEE CG&A, 1998) | https://doi.org/10.1109/38.656788 | Cornell pages and PDF returned 403 or timed out, the IEEE and DOI routes returned empty pages, and no other copy was found; known from secondary sources |
| Tabellion and Lamorlette, irradiance caching in production (SIGGRAPH 2004) | | known through the 2008 irradiance caching course's summary |
| Kelkar et al., RC for real-time 2D GI (IEEE ICWITE 2025) | https://doi.org/10.1109/icwite64848.2025.11307155 | paywalled; only the abstract is reachable |
| Love and Deepspace talk, translated upload | https://www.bilibili.com/video/BV1gAdBBcE9B | HTTP 412; the talk is covered from its YouTube upload |
| Blackline Interactive 3D RC videos | listed in [2026_rc_conference_talks.md](sources/2026_rc_conference_talks.md) | no captions; the descriptions are covered |
| DDGI at GDC 2019 ("Ray-Traced Irradiance Fields") | https://www.gdcvault.com/play/1026182/ | video not watched; the paper is covered |
| GM Shaders voxels post | https://mini.gmshaders.com/p/voxels | paywalled; the public part is covered |
| Reddit threads | | blocked automated reads |
