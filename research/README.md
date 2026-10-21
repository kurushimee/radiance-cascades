# Radiance cascades research

Notes on radiance cascades (RC) and the techniques around them, gathered from papers, theses, talks, articles, repositories and engine source. `topics/` holds the synthesis by subject, with each fact stated in the topic that owns it and the conclusions drawn across sources marked as derived or inferred; `sources/` holds one note per source or group of related sources, with links; `index/` holds the lookup lists that point into both. Original research written here, with exact references and experiments, lives in [papers/](../papers/README.md); each paper has a source note like any other source, and its results are stated in the topics that own them, marked as such. Godot engine behavior confirmed against the engine source goes in [docs/](../docs/), not here.

## Finding things

| Looking for | Go to |
|---|---|
| What the research concludes about single-frame 3D RC | [single_frame_3d_rc.md](topics/single_frame_3d_rc.md) and the [main findings](#main-findings) below |
| A way to fix a problem or reach a goal, when the technique's name is unknown | The goal files: [artifacts](index/goals_artifacts.md) (ringing, leaks, self-hits, depth edges, seams, aliasing, banding) · [one frame, stability, noise and detail](index/goals_single_frame.md) · [what the lighting reaches](index/goals_lighting.md) (bounces, off-screen light, specular, media, sky) · [shading, sampling and other uses](index/goals_shading_and_sampling.md) (many lights, guiding, diffuse shading, non-lighting uses) · [speed and tracing](index/goals_speed_and_tracing.md) · [memory, data structures and scale](index/goals_memory_and_scale.md) (memory, GPU structures, parameters, large worlds) · [building it](index/goals_engine.md) (Godot shading, hit lighting, moving geometry, passes, probes, porting, debugging) |
| A named technique, algorithm, data structure, format, artifact or term | The techniques index: [0–9 to F](index/techniques_0_to_f.md) · [G to O](index/techniques_g_to_o.md) · [P to R](index/techniques_p_to_r.md) · [S to Y](index/techniques_s_to_y.md). The explanations of cross-cutting terms are in [supporting_techniques.md](topics/supporting_techniques.md) and its two parts. |
| A project, repository, Shadertoy ID, paper, thesis, talk, video, game, engine or author | The projects index: [0–9 to E](index/projects_0_to_e.md) · [F to K](index/projects_f_to_k.md) · [L to Q](index/projects_l_to_q.md) · [R to U](index/projects_r_to_u.md) · [V to Z](index/projects_v_to_z.md) |
| The note on one source, or what could not be read | [Radiance cascades sources](index/sources_rc.md) · [related sources and sources not read](index/sources_related.md) |
| Where the measured record of single-frame 3D RC ends | [Where the evidence stops](topics/single_frame_3d_rc.md#where-the-evidence-stops) |
| A subject | The [topics](#topics) below, in reading order |
| Original research: derivations and measurements against exact references | [papers/](../papers/README.md) for the papers, and their source notes under [original research](index/sources_rc.md#original-research) |
| The computation behind a derived figure | [checks/](checks/): one assert-based Python script per derivation (standard library and NumPy), linked from the claim it checks |

Every index entry is one line, so a text search for a term, ID or author over `index/` finds its entry and the links to every section that covers it. Every topic and source note with more than a few sections starts with a contents list. Every topic except the conclusions and the glossary ends with its connections to other topics and a single-frame assessment. A topic too long to read at once continues in part files named `<topic>_<part>.md`; the main file links its parts and keeps the connections and assessment for all of them.

## Topics

Start with the conclusions, then read the rest in this order.

**Conclusions**

1. [single_frame_3d_rc.md](topics/single_frame_3d_rc.md): what the research says about 3D RC computed in a single frame: evidence, where designs lean on time and what replaces it, the design families judged, with Godot as a host, budgets, and where the evidence stops.
2. [performance.md](topics/performance.md): measured cost by domain with links to each owning topic, rays per second, time per megapixel and bytes per probe normalized across sources, and per-frame ray, time and memory budgets.

**The method**

3. [core_theory.md](topics/core_theory.md): penumbra condition, intervals, the merge operator, shift and extend, scaling laws, memory and cost, band limits, using the cascades.
4. [cascade_layout_and_merging.md](topics/cascade_layout_and_merging.md): probe placement, direction maps, intervals, cascade counts, storage layouts, merge kernels, cascade −1, final gather, formats, parameter tables.
5. [artifacts_and_fixes.md](topics/artifacts_and_fixes.md): ringing and the bilinear, straight-ray and cheaper fixes; gaps, leaks, edges, sky aliasing, banding, small lights, recurring bugs, debugging.
6. [holographic_rc.md](topics/holographic_rc.md) and [holographic_rc_implementations.md](topics/holographic_rc_implementations.md): HRC theory, tracing, extensions, variants, the cost model and every code.
7. [volumetric_and_radiative_transfer.md](topics/volumetric_and_radiative_transfer.md): radiative transfer, DexRT, volumetric merging, mip marching, thin-wall leaks, CT volumes, spectral work.

**2D**

8. [2d_implementations.md](topics/2d_implementations.md): 2D scene representations and every 2D code's design, formats and timings.
9. [2d_articles_and_demos.md](topics/2d_articles_and_demos.md): the community demo, tmpvar's playground, Coppen's fundamentals, OPEngine, tlegoc, SimonDev and Kelkar et al.; parts [2d_articles_and_demos_gm_shaders.md](topics/2d_articles_and_demos_gm_shaders.md) (GM Shaders) and [2d_articles_and_demos_jason_today.md](topics/2d_articles_and_demos_jason_today.md) (jason.today).
10. [2d_shadertoys.md](topics/2d_shadertoys.md): the Shadertoy lineage, fixes and frameworks.

**3D**

11. [3d_world_space.md](topics/3d_world_space.md): dense grids, Split RC, sparse hashed probes, ray splitting, leak defences, GPU building blocks.
12. [3d_world_space_implementations.md](topics/3d_world_space_implementations.md): the Split RC codes, erhe and RC design documents; part [3d_world_space_implementations_grids.md](topics/3d_world_space_implementations_grids.md): dense-grid codes and creikey's voxel clipmap.
13. [3d_screen_space.md](topics/3d_screen_space.md), [3d_screen_space_theses.md](topics/3d_screen_space_theses.md) and [3d_screen_space_implementations.md](topics/3d_screen_space_implementations.md): PoE2, screen probes with world intervals, min/max probes, depth-aware merging, the theses and the screen-probe codes.
14. [3d_surface_probes.md](topics/3d_surface_probes.md): surfel RC, Love and Deepspace, UV-chart RC, on-surface caches.
15. [rc_for_sampling_and_guiding.md](topics/rc_for_sampling_and_guiding.md): vlam, RC-guided light sampling and the methods compared; parts [rc_for_sampling_and_guiding_reservoir_cascades.md](topics/rc_for_sampling_and_guiding_reservoir_cascades.md) (Reservoir Cascades) and [rc_for_sampling_and_guiding_rcpg.md](topics/rc_for_sampling_and_guiding_rcpg.md) (RCPG and tauray).
16. [scene_representation_and_tracing.md](topics/scene_representation_and_tracing.md): depth buffers, distance fields, hardware RT, surfels, shading the hit, robustness; part [scene_representation_and_tracing_voxels_and_bvhs.md](topics/scene_representation_and_tracing_voxels_and_bvhs.md): voxels and hierarchical DDA, triangle BVHs in compute, software against hardware.

**Godot**

17. [godot_integration.md](topics/godot_integration.md): compute scheduling, frame order and hooks, buffers, where GI enters shading, SDFGI, fog, HDDAGI.
18. [godot_projects.md](topics/godot_projects.md): gomezzz's 3D addon, Phreakyx, 2D wiring, compositor effect projects.

**Related techniques**

19. [related_probe_gi.md](topics/related_probe_gi.md): irradiance volumes, light propagation volumes, light-field probes, DDGI, Enshrouded, voxel cone tracing.
20. [related_radiance_caches.md](topics/related_radiance_caches.md): irradiance caching, path space filtering, SHaRC, GI-1.0, kajiya, Bevy Solari, GIBS.
21. [related_engine_gi.md](topics/related_engine_gi.md): Lumen, Brixelizer GI, daGI2, HSGI.
22. [related_screen_space_gi.md](topics/related_screen_space_gi.md): LSAO, horizon-based indirect lighting, PoE1's GI, visibility-bitmask SSGI.
23. [light_transport_alternatives.md](topics/light_transport_alternatives.md): line sweeping, short characteristics, cellular automata, transforms, wave optics, caustics, multi-bounce.

**Background**

24. [history_and_landscape.md](topics/history_and_landscape.md): origins, timeline, community, adoption, positions on 3D RC, who built what.
25. [supporting_techniques.md](topics/supporting_techniques.md): glossary of sampling and noise, direction parameterizations, resampling, and denoising and temporal reuse; parts [supporting_techniques_structures_and_tracing.md](topics/supporting_techniques_structures_and_tracing.md) (GPU data structures, ray traversal, distance fields, visibility and screen-space terms) and [supporting_techniques_transport_and_math.md](topics/supporting_techniques_transport_and_math.md) (transport and solver math, interpolation, statistics, image metrics, formats and colour, shading, GPU APIs).

## Main findings

These summarize [single_frame_3d_rc.md](topics/single_frame_3d_rc.md), which gives the evidence for each.

- **RC needs no history.** It is deterministic and its cost does not depend on light count. The temporal reuse in public code comes from host limits, cost spreading, bounce feedback and hiding aliasing, each with a same-frame replacement at a known price.
- **Single-frame 3D RC is proven in two settings.** Path of Exile 2 ships screen-space RC at about 1 to 3 ms with no temporal reuse, and Split RC runs sparse world-space RC in 8.6 to 11.5 ms with hardware ray tracing. Neither runs on a host whose compute shaders cannot issue ray queries, such as Godot 4.7.2 as released; Godot 4.8 adds ray queries on Vulkan ([Godot ray tracing](sources/2026_godot_ray_tracing_status.md#upstream-pull-requests)). A third, closed-source instance, Blackline Interactive's Spatium, shows 11 to 18 ms of GI in Sponza on a 2019 laptop GPU without RT hardware through what appears to be a generated surface atlas, observed on video HUDs only.
- **The tracer decides the cost.** Tracing is 87 to 96% of RC time in Dell'Ova's screen-probe runs, and the main cost in Kung's. At 1080p a 4 ms budget buys 4 to 12 M rays at 1 to 3 G rays per second, which fits screen probes at 4 to 8 px spacing or a few rays per pixel, but not a dense 128³ grid. Under Godot's `RenderingDevice` the one measured figure is a floor, 0.375 G segments per second from gomezzz's whole-frame time; its compute shaders are ordinary Vulkan compute dispatches, so the compute-class rates apply there ([performance](topics/performance.md#normalized-throughput-derived)).
- **The evidence favours a hybrid:** a screen-space near field over world-locked world-space cascades, sparse near surfaces, in a bounded clipmap or on a generated surface atlas. It reaches off-screen light, keeps the error pattern fixed under camera motion and gives screen hits a same-frame radiance source. Measured in a voxel lab, cascade 0 on surface texels under world-locked upper cascades, with stored hits, seals one-voxel walls to 0.0008 of the sky; what a near field must add there is the radiance of occluders smaller than a texel, merged like a cascade, since a visibility factor darkens contact points.
- **In Godot, hit lighting is the main obstacle.** At PRE_OPAQUE this frame's lit colour does not exist, Forward+ has no albedo buffer, and shadows are drawn after the PRE_OPAQUE callbacks. A single-frame solve lights its hits from emission and its own shadow rays or per-frame light injection.
- **Lagged bounces need stored hits to replace.** Without them, one bounce plus a sky term is the single-frame baseline, and each further bounce costs another solve. In opaque scenes, re-merging stored hits gives all bounces without new rays: measured in flatland and a 3D voxel lab, 2 to 8 GMRES passes converge at albedo 0.9, each 0.42 to 0.97 of a solve's reads and voxel steps, and the merge's leak deficit sets the accuracy.
- **Parameters with evidence behind them:** ×4 directions and ×4 intervals per cascade, 32 cascade 0 directions, a cascade 0 interval of 1.6 to 1.7 spacings, a nested equal-area direction map, a trilinear merge with a binary visibility test, one dispatch per cascade from the top with two live buffers, 6×6 irradiance tiles, RGBA16F. Measured in flatland against an exact reference, the equal-error cascade 0 interval is the robust choice, within 1.42 times every scene's optimal error, while the optimum moves eightfold with the size of the lights; the interval scale matters little once the interval is tuned, and at short intervals most error is merge parallax at the first hand-over.
- **In Godot the composite goes through `IRRADIANCE`,** with `E/π`, in every opaque `ShaderMaterial`; SSAO multiplies on top, darkening contact regions that RC already occludes. Accumulation uses 32-bit integer atomics, and Vulkan guarantees only 128 MiB per storage buffer.
- **The most reusable code:** gomezzz's Godot addon for RC plumbing in Godot; wroughtinator's native Split RC build (one GLSL compute source, software BVH, integer atomics); HDDAGI's integer hierarchical DDA over voxel bits; Brixelizer's MIT GLSL brick tracer; tinybvh's GLSL kernels and Wicked Engine's per-frame GPU BVH.

## Sources

The source notes are listed with what each holds and the topics that carry its facts in [radiance cascades sources](index/sources_rc.md) (foundations, explainers and 2D, 3D, Godot) and [related sources](index/sources_related.md) (related GI methods, data structures and background papers, and the sources that could not be read, with the routes tried).
