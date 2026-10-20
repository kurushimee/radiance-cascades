# Projects and works: V to Z

Implementations, repositories, Shadertoys by ID, engines, games, papers, theses, talks, articles, videos and authors, in alphabetical order. Each entry says what it is, links the sections that describe it, and lists the other topics that cite it. Source notes are listed in [radiance cascades sources](sources_rc.md) and [related sources](sources_related.md).

Letters in all files: [0–9 to E](projects_0_to_e.md) · [F to K](projects_f_to_k.md) · [L to Q](projects_l_to_q.md) · [R to U](projects_r_to_u.md) · [V to Z](projects_v_to_z.md).

## Contents

- [V](#v)
- [W](#w)
- [X](#x)
- [Y](#y)
- [Z](#z)

## V

- **Vahteristo, Liu and Rupp 2025**: arXiv paper reconstructing binary disks from 30 to 100° sinograms. [light_transport_alternatives: Solutions without occlusion](../topics/light_transport_alternatives.md#solutions-without-occlusion).
- **Vasiou et al. 2018 ray tracing performance study**: CGI 2018 study: memory dominates ray tracing time and energy, using a cycle-accurate simulator. [scene_representation_and_tracing: Where tracing time goes](../topics/scene_representation_and_tracing.md#where-tracing-time-goes). Also in [3d_screen_space_theses](../topics/3d_screen_space_theses.md#dellova-2025-performance-scaling-with-dxr), [performance](../topics/performance.md#connections).
- **Viertel, Osting and Staten 2019**: Coarse quad layouts from separatrix simplification; no texturing or lighting. [light_transport_alternatives: Other uses](../topics/light_transport_alternatives.md#other-uses).
- **vlam**: 2D path tracer by entropylost, 2025, guiding directions with six cascades. [rc_for_sampling_and_guiding: vlam](../topics/rc_for_sampling_and_guiding.md#vlam). Also in [2d_implementations](../topics/2d_implementations.md#where-each-2d-code-is-covered), [history_and_landscape](../topics/history_and_landscape.md#community-site-wiki-and-tools), [supporting_techniques](../topics/supporting_techniques.md#next-event-estimation).
- **Volumetric-HRC**: Yaazarai's GameMaker HRC with volumetrics, extended from cascade 0 with a write-up. [holographic_rc_implementations: Volumetric-HRC](../topics/holographic_rc_implementations.md#volumetric-hrc). Also in [2d_implementations](../topics/2d_implementations.md#where-each-2d-code-is-covered), [performance](../topics/performance.md#volumetric-and-hrc), [history_and_landscape](../topics/history_and_landscape.md#community-site-wiki-and-tools), [holographic_rc](../topics/holographic_rc.md#building-rays-the-acceleration-structure), [volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#integration-and-merging).
- **voQ0qQGagss**: 2021 sparse voxel octree streaming video. [history_and_landscape: Other work on Sannikov's channel](../topics/history_and_landscape.md#other-work-on-sannikovs-channel).
- **VoxelGI**: Godot's built-in voxel GI, which script can feed through RenderingServer allocation. [godot_integration: World-space inputs](../topics/godot_integration.md#world-space-inputs).
- **-vQGQu6pGeI**: 2016 GLSL fragment-shader path tracer video, same description. [history_and_landscape: Other work on Sannikov's channel](../topics/history_and_landscape.md#other-work-on-sannikovs-channel).
- **vsensu/bevy_radiance_cascades**: Bevy 0.20 new-project template. [history_and_landscape: Repositories that hold nothing usable](../topics/history_and_landscape.md#repositories-that-hold-nothing-usable).
- **VXPG**: Lu et al. SIGGRAPH 2024 real-time path guiding with bounding voxel sampling; RCPG main baseline. [rc_for_sampling_and_guiding: Methods compared and cited](../topics/rc_for_sampling_and_guiding.md#methods-compared-and-cited). Also in [rc_for_sampling_and_guiding_rcpg](../topics/rc_for_sampling_and_guiding_rcpg.md#evaluation).

## W

- **w3XSz4**: Neylick's learning build: eleven cascades, 1024² cube map, about ten frames to settle. [2d_shadertoys: Independent codes](../topics/2d_shadertoys.md#independent-codes). Also in [2d_implementations](../topics/2d_implementations.md#scene-representations), [artifacts_and_fixes](../topics/artifacts_and_fixes.md#recurring-implementation-bugs), [cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#intervals), [history_and_landscape](../topics/history_and_landscape.md#first-public-implementations-and-the-shadertoy-lineage).
- **Ward**: Author of irradiance caching; the rule and weight this section describes. [related_radiance_caches: Ward's rule](../topics/related_radiance_caches.md#wards-rule).
- **Weta's Manuka**: Spectral renderer with Fourier-moment reflectance and four wavelengths per path. [volumetric_and_radiative_transfer: Spectral transport](../topics/volumetric_and_radiative_transfer.md#spectral-transport).
- **WfyyDm (youssef_afella)**: HRC 2D GI Shadertoy recreating the paper's figure, with four frustums in one buffer. [holographic_rc_implementations: WfyyDm (youssef_afella)](../topics/holographic_rc_implementations.md#wfyydm-youssef_afella). Also in [2d_shadertoys](../topics/2d_shadertoys.md#index), [history_and_landscape](../topics/history_and_landscape.md#first-public-implementations-and-the-shadertoy-lineage), [holographic_rc](../topics/holographic_rc.md#merging-down).
- **wfyyDz**: Shadertoy fixed-step march with 1% opacity per sample. [2d_implementations: Scene representations](../topics/2d_implementations.md#scene-representations), [2d_shadertoys: Media](../topics/2d_shadertoys.md#media). Also in [cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#intervals), [history_and_landscape](../topics/history_and_landscape.md#first-public-implementations-and-the-shadertoy-lineage), [volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#integration-and-merging).
- **wgpu**: Pure-Rust WebGPU over Vulkan, Metal, D3D12, OpenGL and the web. [supporting_techniques_transport_and_math: Frameworks and GPU APIs](../topics/supporting_techniques_transport_and_math.md#frameworks-and-gpu-apis). Also in [holographic_rc](../topics/holographic_rc.md#debugging).
- **Wicked Engine**: János Turánszki's MIT engine; builds a GPU BVH each frame for DDGI and surfel GI. [scene_representation_and_tracing_voxels_and_bvhs: Wicked Engine: a BVH built on the GPU every frame](../topics/scene_representation_and_tracing_voxels_and_bvhs.md#wicked-engine-a-bvh-built-on-the-gpu-every-frame). Also in [single_frame_3d_rc](../topics/single_frame_3d_rc.md#where-the-evidence-stops), [godot_projects](../topics/godot_projects.md#single-frame-assessment), [scene_representation_and_tracing](../topics/scene_representation_and_tracing.md#options).
- **WillKirkmanM/radiance-cascade**: Canvas effect with 4 radial-gradient discs per light; the levels do not interact. [history_and_landscape: Repositories that hold nothing usable](../topics/history_and_landscape.md#repositories-that-hold-nothing-usable).
- **willWallace-RIT/Radiancecascade3d**: GDScript and GLSL that do not run; one fixed step toward the sun, no cascades. [history_and_landscape: Repositories that hold nothing usable](../topics/history_and_landscape.md#repositories-that-hold-nothing-usable).
- **Winstob/radiance-cascades**: Rust free-list and pass-through WGSL shader with a test driver; no RC. [history_and_landscape: Repositories that hold nothing usable](../topics/history_and_landscape.md#repositories-that-hold-nothing-usable).
- **World-space ReSTIR**: Boisse 2021 GI reservoir cache in hash grid cells; model for Reservoir Cascades control. [rc_for_sampling_and_guiding: Methods compared and cited](../topics/rc_for_sampling_and_guiding.md#methods-compared-and-cited).
- **WPBGI**: Wang, Meng and Boubekeur's EGSR 2015 Haar cube-map point GI. [light_transport_alternatives: Wavelet point-based GI](../topics/light_transport_alternatives.md#wavelet-point-based-gi). Also in [cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#connections).
- **WWDC 2021 session 10148**: Apple talk on texture usage flags and compression; gives mechanism, no comparison. [holographic_rc: Performance](../topics/holographic_rc.md#performance).

## X

- **X3XfRM (Mathis)**: Shadertoy Radiance Cascades 3D by Mathis, 2024; RC on UV charts of an analytic room. [3d_surface_probes: X3XfRM (Mathis)](../topics/3d_surface_probes.md#x3xfrm-mathis). Also in [2d_shadertoys](../topics/2d_shadertoys.md#index), [3d_screen_space_implementations](../topics/3d_screen_space_implementations.md#connections), [single_frame_3d_rc](../topics/single_frame_3d_rc.md#where-existing-designs-lean-on-time), [3d_world_space](../topics/3d_world_space.md#leak-defences-in-world-space), [3d_world_space_implementations_grids](../topics/3d_world_space_implementations_grids.md#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes), [cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#direction-maps-in-3d), [performance](../topics/performance.md#3d-world-space-and-surfaces), [history_and_landscape](../topics/history_and_landscape.md#timeline).
- **x4M65rI0AKc**: 2021 sparse voxel octree streaming video, including an SDF octree variant. [history_and_landscape: Other work on Sannikov's channel](../topics/history_and_landscape.md#other-work-on-sannikovs-channel).
- **xatlas**: Chart generator and packer behind common lightmap UV2; weighted growth metrics, padding and bilinear room. [3d_surface_probes: Building a surface atlas](../topics/3d_surface_probes.md#building-a-surface-atlas).
- **XcB3Ry**: Suslik's 2024 gravity fluid simulation: six cascades, factor 4, N-body field. [2d_shadertoys: Cascades for gravity](../topics/2d_shadertoys.md#cascades-for-gravity). Also in [history_and_landscape](../topics/history_and_landscape.md#timeline).
- **XcfyDj**: mxcop's diagram of the reprojection (parallax) fix with two cascades. [2d_shadertoys: Diagrams and helpers](../topics/2d_shadertoys.md#diagrams-and-helpers). Also in [artifacts_and_fixes](../topics/artifacts_and_fixes.md#straight-ray-fixes), [history_and_landscape](../topics/history_and_landscape.md#timeline).
- **XffcD7**: kornelski's Shadertoy with gear-shaped interval offsets and a teeth parameter. [artifacts_and_fixes: Cheaper fixes](../topics/artifacts_and_fixes.md#cheaper-fixes), [2d_shadertoys: fad's line](../topics/2d_shadertoys.md#fads-line). Also in [cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#2d-parameters-across-implementations), [history_and_landscape](../topics/history_and_landscape.md#timeline).
- **xiaoiver/infinite-canvas-tutorial**: Chinese canvas RC tutorial modelled on bevy_radiance_cascades. [2d_implementations: Unity and other ports](../topics/2d_implementations.md#unity-and-other-ports).
- **Xor**: Co-author of the GM Shaders posts; wrote the 2023 random-rays post with Yaazarai. [2d_articles_and_demos_gm_shaders: GM Shaders (Yaazarai and Xor)](../topics/2d_articles_and_demos_gm_shaders.md#gm-shaders-yaazarai-and-xor).
- **XRENGINE**: Engine with pre-baked 3D GI volumes sampled per pixel; RC provider unsupported until live injection. [3d_world_space_implementations: XRENGINE](../topics/3d_world_space_implementations.md#xrengine).
- **XXVfW3**: fb01's ray-traced shape scene tagged as RC but with no cascades. [2d_shadertoys: Shaders that are not RC](../topics/2d_shadertoys.md#shaders-that-are-not-rc).
- **XXXyWM**: Linked line-sweep demo that returns Shadertoy's not-found page. [2d_shadertoys: Shaders that are not RC](../topics/2d_shadertoys.md#shaders-that-are-not-rc). Also in [light_transport_alternatives](../topics/light_transport_alternatives.md#three-ways-to-parallelize-a-sweep).

## Y

- **Yaazarai**: Co-author of the GM Shaders posts and GameMaker repository. [2d_articles_and_demos_gm_shaders: GM Shaders (Yaazarai and Xor)](../topics/2d_articles_and_demos_gm_shaders.md#gm-shaders-yaazarai-and-xor). Also in [history_and_landscape](../topics/history_and_landscape.md#who-built-what), [holographic_rc_implementations](../topics/holographic_rc_implementations.md#volumetric-hrc).
- **yhyu13**: Hemisphere probes on voxel faces and charts. [3d_screen_space_implementations: Connections](../topics/3d_screen_space_implementations.md#connections). Also in [single_frame_3d_rc](../topics/single_frame_3d_rc.md#where-the-evidence-stops).
- **yhyu13's surface charts**: Surface-chart RC probes using a parent hit-distance test. [3d_world_space: Leak defences in world space](../topics/3d_world_space.md#leak-defences-in-world-space). Also in [performance](../topics/performance.md#3d-world-space-and-surfaces).
- **yiVmMb_dnfc**: 2010-2012 shadow-technique video, same method as uZxKCBtiJY8. [history_and_landscape: Other work on Sannikov's channel](../topics/history_and_landscape.md#other-work-on-sannikovs-channel).
- **YMM4-Radiance**: Direct2D 2D lighting effect with a 9-level occupancy pyramid. [2d_implementations: Unity and other ports](../topics/2d_implementations.md#unity-and-other-ports). Also in [cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#2d-parameters-across-implementations).
- **youssef_afella**: Unfinished HRC port for Unity 6000 URP render graph; MIT, 2025. [holographic_rc_implementations: Youssef-Afella's Unity port](../topics/holographic_rc_implementations.md#youssef-afellas-unity-port), [2d_implementations: Scene representations](../topics/2d_implementations.md#scene-representations), [2d_shadertoys: Independent codes](../topics/2d_shadertoys.md#independent-codes). Also in [history_and_landscape](../topics/history_and_landscape.md#who-built-what), [cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#merge-kernels), [holographic_rc](../topics/holographic_rc.md#merging-down).

## Z

- **ZY4N**: Unity 2D RC with no distance field, camera image as scene. [2d_implementations: Unity and other ports](../topics/2d_implementations.md#unity-and-other-ports).
