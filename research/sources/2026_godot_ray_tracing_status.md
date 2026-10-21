# Ray tracing in Godot: upstream status and NVIDIA's fork

| | |
|---|---|
| Upstream pull requests | [#99119](https://github.com/godotengine/godot/pull/99119), [#116227](https://github.com/godotengine/godot/pull/116227), [#118668](https://github.com/godotengine/godot/pull/118668), [#122051](https://github.com/godotengine/godot/pull/122051), [#123093](https://github.com/godotengine/godot/pull/123093), [#123095](https://github.com/godotengine/godot/pull/123095) |
| NVIDIA-RTX/godot | https://github.com/NVIDIA-RTX/godot (MIT), branch `nvidia-pt-dlss` read at commit [135dff3887](https://github.com/NVIDIA-RTX/godot/commit/135dff3887) |
| Press and forum | [CG Channel](https://www.cgchannel.com/2026/03/get-nvidias-new-path-tracing-fork-of-the-godot-game-engine/), [Godot forum](https://forum.godotengine.org/t/godot-rtx-nvidia-fork-path-tracing/135657), [GameFromScratch](https://gamefromscratch.com/nvidia-release-rtx-powered-godot-fork/), [ziva.sh](https://ziva.sh/blogs/godot-ray-tracing) |

Godot's `RenderingDevice` gained a ray tracing API in January 2026, but compute shaders could not use ray queries on stock builds until a fix merged in August 2026 for 4.8. NVIDIA's fork, a path tracer, requested ray queries before upstream did. The engine behaviour itself, checked against the source, is in the [RenderingDevice notes](../../docs/rendering_device.md#ray-tracing).

## Contents

- [Upstream pull requests](#upstream-pull-requests)
- [NVIDIA's fork](#nvidias-fork)
  - [The build](#the-build)
  - [Implementation](#implementation)
  - [Backends, denoising and performance](#backends-denoising-and-performance)

## Upstream pull requests

The feature enums and the wiring that makes them true landed in different pull requests.

- **#99119 "Vulkan raytracing plumbing"** (Fahien, profile name Antonio Caggiano), opened 2024-11-12, merged 2026-01-27. It adds the `RenderingDevice` ray tracing API, the `SUPPORTS_RAYTRACING_PIPELINE` and `SUPPORTS_RAY_QUERY` feature enums and a `ray_query_support` flag, plus D3D12 stubs. `SUPPORTS_RAY_QUERY` returns `acceleration_structure_support && ray_query_support`, which could not be true, because nothing requested the extension.
- **#116227 "Fix acceleration structure barriers in Vulkan pipelines"** (Fahien), opened 2026-02-12, merged 2026-04-17. It gates the ray query barrier logic on `ray_query_support`.
- **#118668 "Fix asymmetric bitmask update in Vulkan acceleration-structure barrier"** (shaun0927), opened and closed 2026-04-17, not merged.
- **#122051 "Fix various raytracing issues."** (blueskythlikesclouds, not NVIDIA), opened 2026-08-03, merged 2026-08-04, milestone 4.8. It registers `VK_KHR_RAY_QUERY_EXTENSION_NAME` as an optional extension and chains `VkPhysicalDeviceRayQueryFeaturesKHR`, the first upstream change that makes `SUPPORTS_RAY_QUERY` true on Vulkan. The same pull request fixes indexed BLAS creation in release builds and push constants in ray tracing stages ([RenderingDevice notes](../../docs/rendering_device.md#ray-tracing)).
- **#123093 "RenderingDevice: only require an instance hit-SBT range where raytracing pipelines exist"** and **#123095 "Only require a hit SBT range where raytracing pipelines exist"** (iamGeoWat, the same change), both opened and closed 2026-09-02, not merged. Their description says devices with ray queries but no ray tracing pipelines fail every TLAS build.

No open upstream pull request is about ray queries, and none comes from NVIDIA's fork; a search for "ray query" returns only CPU physics BVH pull requests such as #100475.

## NVIDIA's fork

### The build

- NVIDIA-RTX/godot is a GitHub fork of godotengine/godot, described as "NVIDIA fork of Godot Engine", created 2026-03-09, last pushed 2026-07-28. GitHub lists its licence as MIT, and the forum post says it is "under the MIT license (the same as Godot)". The owner's only other Godot repository is `nvigi_godot_extension`, a binding of the NVIGI inference SDK unrelated to ray tracing; the NVIDIAGameWorks and NVIDIA owners have none.
- The default branch, `nvidia-pt-dlss`, ends at 135dff3887 (2026-07-24, "NVIDIA: Pathtracer + DLSS", 191 files, +19,452 −721, by L Sikkes at an NVIDIA address), with same-day commits 5e232ffd61 (dependencies) and 6d1005697f (miscellaneous). Other branches: `master` (2026-06-16), `nvidia-pt-dlss-dev` (2026-07-04, "DLSS RR Diffuse Albedo Stabilization"), `backport/nvidia-pt-dlss-4.6.3` (2026-07-28) and `worktree-dlss-fg-reflex` (2026-07-28, a DLSS Frame Generation fix).
- **Base version.** The default branch's `version.py` says 4.8.0 "dev", and its merge base with upstream master, c3e6b2c09354 (2026-06-23), is 4.8.0 "dev" too. The backport branch says 4.6.3 "stable". The press says 4.7, which the repository does not bear out.
- CG Channel (secondhand) describes Leroy Sikkes as an NVIDIA developer technology engineer who presented at GDC 2026. The forum post's author lists no affiliation on GitHub.
- Issues: #11 (open) transmissive materials render opaque under path tracing; #12 (closed) the build cannot run without shader execution reordering support; #13 (closed) a PhysX branch request.

### Implementation

Paths are in `nvidia-pt-dlss`. The path tracer is a ray tracing pipeline, and inline ray queries serve shadows and one probe. Its sampling, materials and lights, checked against the source and measured, are in the [path tracer notes](../../docs/path_tracer.md).

- **Dispatch:** `servers/rendering/renderer_rd/forward_clustered/render_forward_clustered_pt.cpp:353` calls `raytracing_list_trace_rays`. `scene_shader_raytracing.cpp` in the same folder creates the pipelines (lines 874 and 1225) and hit shader binding tables (lines 887 and 1285).
- **Acceleration structures:** `render_raytracing.cpp` (3,353 lines) creates a BLAS per surface (line 1039), procedural ones (1361) and one per merged MultiMesh (2161), whose vertices a compute shader (`mm_merge_shader`, line 61) merges into one source; the TLAS (line 1778) prefers fast traces.
- **Shaders** in `servers/rendering/renderer_rd/shaders/raytracing/`: `scene_raytracing_raygen.glsl` holds raygen (line 1), miss (104), closest-hit (253), any-hit (461) and intersection (572) stages. The path bounce is `traceRayEXT` at line 83, with `hitObjectEXT` and `reorderThreadEXT` under `USE_SER` (lines 69 to 84). `raytracing_lights_inc.glsl` casts shadow rays with `rayQueryEXT` (line 194) under `USE_RAY_QUERY_SHADOWS` and with `traceRayEXT` (line 237) otherwise; `raytracing_closest_hit_common_inc.glsl:502-503` casts a specular probe ray query with `gl_RayFlagsTerminateOnFirstHitEXT`. Every ray query sits in the closest-hit stage, which includes both files (raygen lines 306 and 345); none is in compute or fragment shaders.
- **Light selection:** `raytracing_lights_inc.glsl:256-270` picks the light for next-event estimation by mini-batch reservoir sampling, which is RIS with no temporal or spatial reuse.
- **Switches:** in `scene_shader_raytracing.cpp`, `rendering/pathtracing/use_simple_shadows` (line 664) sets `USE_RAY_QUERY_SHADOWS`, `rendering/pathtracing/use_shader_execution_reordering` (line 679) sets `USE_SER`, and the DLSS Ray Reconstruction define is set at line 671 for the `PT_DENOISER_DLSS_RAY_RECONSTRUCTION` denoiser.
- **Engine changes:** the fork adds `raytracing_list_add_buffer_dependency` to `servers/rendering/rendering_device.h` (line 1658), absent at the merge base. `drivers/vulkan/rendering_device_driver_vulkan.cpp:592-593` requests `VK_KHR_ray_tracing_pipeline` and `VK_KHR_ray_query`, with their feature structures at lines 932 to 1031; the merge base requests no ray query extension. The fork thus requested ray queries on 2026-07-24, before #122051 merged the same request upstream on 2026-08-04.

### Backends, denoising and performance

- **Backends.** Only Vulkan traces. `drivers/d3d12/rendering_device_driver_d3d12.cpp:5569-5570` returns "Ray tracing is not currently supported by the D3D12 driver." and `has_feature` (line 5915) falls through to false, the same 31 lines as upstream. The Metal driver has no ray tracing symbols, and `rendering_device_driver_vulkan.cpp:57` disables ray tracing on macOS and iOS because of MoltenVK.
- **Denoising** is DLSS Ray Reconstruction only (`servers/rendering/renderer_rd/effects/dlss.cpp:518` calls `slEvaluateFeature(sl::kFeatureDLSS_RR, ...)`, with Streamline in `drivers/streamline/` and `thirdparty/streamline/`), so it needs NVIDIA hardware. The press reports a second denoiser for other vendors in development (secondhand).
- **Performance.** No figures are published: the README is upstream's and the issues hold no benchmarks. CG Channel, quoting Reddit, says frame rates "aren't great"; the forum post says DLSS Ray Reconstruction removes much of the flicker. Volumetrics and decals are reported unsupported (secondhand, ziva.sh and CG Channel).
- GitHub code search does not index the fork (no hits for strings it contains, such as `rayQueryEXT`), so these paths come from the git tree API and raw file reads.
