# Supporting techniques: structures and tracing

Glossary entries for GPU data structures, ray traversal and intersection, distance fields and voxelization, and visibility, shadows and screen-space methods. The entry format and the other categories are in [supporting techniques](supporting_techniques.md).

## Contents

- [GPU data structures](#gpu-data-structures)
  - [Hi-Z and min/max depth pyramids](#hi-z-and-minmax-depth-pyramids)
  - [Morton order](#morton-order)
  - [Clipmaps and toroidal addressing](#clipmaps-and-toroidal-addressing)
  - [Froxels](#froxels)
  - [VDB and GVDB](#vdb-and-gvdb)
  - [Sparse voxel octrees](#sparse-voxel-octrees)
  - [GPU hash tables](#gpu-hash-tables)
  - [Prefix sums and decoupled look-back](#prefix-sums-and-decoupled-look-back)
  - [Radix sort and Onesweep](#radix-sort-and-onesweep)
  - [Nanite](#nanite)
  - [Surface cache cards](#surface-cache-cards)
- [Ray traversal and intersection](#ray-traversal-and-intersection)
  - [BVH](#bvh)
  - [BLAS and TLAS](#blas-and-tlas)
  - [Ray queries](#ray-queries)
  - [Aila and Laine traversal](#aila-and-laine-traversal)
  - [Slab test](#slab-test)
  - [Möller-Trumbore](#möller-trumbore)
  - [DDA grid traversal](#dda-grid-traversal)
  - [Hierarchical DDA](#hierarchical-dda)
  - [Sphere tracing](#sphere-tracing)
  - [Bresenham's line algorithm](#bresenhams-line-algorithm)
- [Distance fields and voxelization](#distance-fields-and-voxelization)
  - [Jump flooding](#jump-flooding)
  - [Eikonal equation and fast sweeping](#eikonal-equation-and-fast-sweeping)
  - [GPU distance fields from meshes](#gpu-distance-fields-from-meshes)
  - [Conservative rasterization](#conservative-rasterization)
  - [Draco](#draco)
- [Visibility, shadows and screen space](#visibility-shadows-and-screen-space)
  - [Shadow maps, acne and bias](#shadow-maps-acne-and-bias)
  - [Variance shadow maps and the Chebyshev bound](#variance-shadow-maps-and-the-chebyshev-bound)
  - [Summed-area variance shadow maps](#summed-area-variance-shadow-maps)
  - [Moment shadow maps and power moments](#moment-shadow-maps-and-power-moments)
  - [Chebyshev distance](#chebyshev-distance)
  - [Bent normals and bent cones](#bent-normals-and-bent-cones)
  - [SSAO](#ssao)
  - [HBAO](#hbao)
  - [GTAO](#gtao)
  - [SAO](#sao)
  - [Screen-space reflections](#screen-space-reflections)
  - [Screen-space indirect light (SSDO, SSIL, SSGI)](#screen-space-indirect-light-ssdo-ssil-ssgi)
  - [Depth thickness](#depth-thickness)
  - [G-buffer and deferred shading](#g-buffer-and-deferred-shading)
  - [Premultiplied alpha and "over"](#premultiplied-alpha-and-over)

## GPU data structures

### Hi-Z and min/max depth pyramids

A mip chain of the depth buffer where each texel keeps the min (or max, or both) of the 2×2 block below, so a ray or query can skip a whole region at once and descend only where a hit is possible. The Z pyramid comes from Greene, Kass and Miller, "Hierarchical Z-Buffer Visibility", SIGGRAPH 1993; Uludag's "Hi-Z Screen-Space Cone-Traced Reflections" (GPU Pro 5, 2014) made it the standard screen-space ray structure, and AMD's single-pass downsampler builds up to about 12 levels in one dispatch. Screen-space RC uses min/max pyramids both for tracing and to place probe pairs at the min and max depth of a tile ([3D screen space](3d_screen_space.md), [scene representation](scene_representation_and_tracing.md)).

### Morton order

Interleave the bits of integer coordinates so points close in space get close keys: in 2D, spread 16-bit `x` with `x &= 0x0000ffff; x = (x ^ (x << 8)) & 0x00ff00ff; x = (x ^ (x << 4)) & 0x0f0f0f0f; x = (x ^ (x << 2)) & 0x33333333; x = (x ^ (x << 1)) & 0x55555555` and combine `(spread(y) << 1) | spread(x)`; in 3D first mask `x &= 0x000003ff`, then use shifts 16, 8, 4, 2 with masks 0xff0000ff, 0x0300f00f, 0x030c30c3, 0x09249249. Reference: Morton, IBM Ottawa technical report, 1966 (secondary); Giesen's "Decoding Morton codes", 2009. Used for sparse storage in [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md), probe ordering in [tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md), BVH builds in [compute BVH libraries](../sources/2026_compute_bvh_libraries.md), hash keys in [GPU hash tables](../sources/2026_gpu_hash_tables_and_sorting.md) and layouts in kornelski's Bevy RC ([Bevy repositories](../sources/2024_bevy_2d_rc_repositories.md)).

### Clipmaps and toroidal addressing

Nested fixed-size windows, one per level, centred on the viewer with doubling extent; logical texel `(u, v)` lives at `(u mod N, v mod N)`, so a moving window rewrites only the newly exposed strip. Reference: Tanner, Migdal and Jones, "The Clipmap: A Virtual Mipmap", SIGGRAPH 1998; Asirvatham and Hoppe, GPU Gems 2, ch. 2, 2005. The usual container for camera-following world-space probes and voxels: [Lumen](../sources/2022_wright_lumen_siggraph_advances.md), [HSGI](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md), [daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md), [kajiya](../sources/2022_stachowiak_kajiya_gi.md), Love and Deepspace, the [voxel repositories](../sources/2026_voxel_3d_rc_repositories.md) and reduz's view that open-world RC needs clipmaps.

### Froxels

Cells of a 3D grid aligned with the view frustum (frustum voxels), small near the camera and large far away, used to inject, light and integrate participating media front to back. References: Wronski, "Volumetric Fog", SIGGRAPH 2014 Advances course; Hillaire, "Physically Based and Unified Volumetric Rendering in Frostbite", SIGGRAPH 2015 Advances course (8×8-pixel tiles, 64 depth slices by default). Used in [Lumen](../sources/2022_wright_lumen_siggraph_advances.md), [daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md) and Godot's volumetric fog ([Godot GI internals](../sources/2026_godot_gi_internals.md)).

### VDB and GVDB

A sparse grid as a shallow, wide tree of fixed-size blocks (by default 8³ leaves under 16³ and 32³ internal nodes), with average constant-time random access; GVDB puts the layout on the GPU with a memory pool and hierarchical ray traversal. References: Museth, "VDB: High-Resolution Sparse Volumes with Dynamic Topology", ACM TOG 32(3), 2013; Hoetzlein, "GVDB", HPG 2016. DexRT's sparse storage is VDB-like ([wiki](../sources/2026_rc_community_site_and_wiki.md#dexrt)).

### Sparse voxel octrees

Octrees that store only occupied octants and are ray cast directly. Reference: Laine and Karras, "Efficient Sparse Voxel Octrees", I3D 2010. Sannikov's 2021 SVO streaming and Crassin's GigaVoxels ([notes](../sources/2011_crassin_gigavoxels_thesis.md)) build on them.

### GPU hash tables

Open addressing with linear probing (`slot = (h(key) + i) mod N`) places a colliding key in the next free slot; cuckoo hashing gives each key `k` candidate slots and evicts on insert, so lookups probe at most `k` slots. Bucketed cuckoo with three functions reaches load factors near 0.98. References: Alcantara et al., "Real-time parallel hashing on the GPU", SIGGRAPH Asia 2009; Awad et al., "Better GPU Hash Tables", arXiv 2108.07232, 2021. The storage of sparse 3D RC, SHaRC and GI-1.0 ([GPU hash tables](../sources/2026_gpu_hash_tables_and_sorting.md), [scene representation](scene_representation_and_tracing.md)).

### Prefix sums and decoupled look-back

An exclusive scan gives each element the sum of those before it; Blelloch's tree form does O(n) work in O(log n) steps, and Merrill and Garland's single-pass scan has each tile publish its aggregate and look back over predecessors' status, about `2n` memory traffic. References: Blelloch, CMU-CS-90-190, 1990; Merrill and Garland, NVR-2016-002, 2016. Used for compaction and allocation in [Coppen's surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md), [Solari](../sources/2025_jms55_bevy_solari.md) and [GPU hash tables](../sources/2026_gpu_hash_tables_and_sorting.md).

### Radix sort and Onesweep

LSD radix sort orders keys digit by digit with a histogram, a scan and a scatter per pass; Onesweep folds the scan into one pass with decoupled look-back, about `2n` traffic per digit (29.4 GKeys/s for 256M 32-bit keys on an A100). Reference: Adinets and Merrill, arXiv 2206.01784, 2022. Used to sort rays, probes and BVH primitives ([GPU hash tables](../sources/2026_gpu_hash_tables_and_sorting.md), [compute BVH libraries](../sources/2026_compute_bvh_libraries.md)).

### Nanite

Unreal Engine 5's virtualized geometry: clustered meshes in a hierarchy with per-cluster level of detail, streamed in pages, culled, rasterized and shaded through a visibility buffer. Reference: Karis, Stubbe and Wihlidal, "A Deep Dive into Nanite Virtualized Geometry", SIGGRAPH 2021 Advances course. Sannikov's cluster renderer follows the same rule ([history](history_and_landscape.md#other-work-on-sannikovs-channel)).

### Surface cache cards

Lumen's surface parameterization: offline capture viewpoints per mesh (12 by default for static meshes, six around pre-skinned bounds for skeletal meshes) from which material properties are recorded and lighting is cached for ray hits. Reference: Wright, Narkowicz and Kelly, "Lumen", SIGGRAPH 2022 Advances course ([notes](../sources/2022_wright_lumen_siggraph_advances.md)); SDFGI's plan ([notes](../sources/2023_linietsky_godot_sdfgi_plan.md)) and [Brixelizer](../sources/2024_amd_brixelizer_gi.md) use similar ideas.

## Ray traversal and intersection

### BVH

A tree of bounding volumes (usually axis-aligned boxes) over primitives; a ray skips any subtree whose box it misses. References: Rubin and Whitted, SIGGRAPH 1980; Kay and Kajiya, SIGGRAPH 1986 (both secondary). **SAH:** a split costs `K_T + K_I·(SA(L)/SA(V)·N_L + SA(R)/SA(V)·N_R)`, and builders pick the cheapest (Goldsmith and Salmon, IEEE CG&A 7(5), 1987; MacDonald and Booth, *The Visual Computer* 6(3), 1990). **Binned SAH** scores only the `K − 1` boundaries of `K` equal centroid bins along an axis, with `K = 16` near optimal and 4 already reasonable (Wald, IEEE Symposium on Interactive Ray Tracing 2007). **Wide BVHs** (BVH4, BVH8, MBVH) give nodes 4 or 8 children for SIMD and GPU lanes (Wald, Benthin and Boulos 2008). **CWBVH** quantizes the 8 child boxes to 8 bits per plane against a shared origin and exponent, with octant-aware child order, for 1.9 to 2.1× faster incoherent traversal at 35 to 60% of the memory (Ylitie, Karras and Laine, HPG 2017). **PLOC** builds bottom-up by sorting primitives in Morton order and merging mutually nearest clusters within a window of radius `r` (10 to 100) (Meister and Bittner, IEEE TVCG, 2018), and **H-PLOC** does the binary build in one kernel by combining LBVH's Morton ranges with PLOC merges, then collapses to a wide tree in one more (Benthin et al., HPG 2024). BVHs traced in compute are covered in [compute BVH libraries](../sources/2026_compute_bvh_libraries.md) and [scene representation](scene_representation_and_tracing.md).

### BLAS and TLAS

In hardware ray tracing APIs a bottom-level acceleration structure holds one geometry's triangles or boxes, and a top-level structure holds instances (BLAS reference, transform, mask, hit-group offset); rays start at the TLAS and are transformed into each instance. Reference: Microsoft, DirectX Raytracing functional spec.

### Ray queries

`VK_KHR_ray_query` (and DXR 1.1 inline ray tracing) lets any shader stage, compute included, traverse an acceleration structure with a loop of query steps and read the committed hit. Reference: Khronos, VK_KHR_ray_query, 2020. Godot 4.7.2's `RenderingDevice`, as released, does not expose it, which is why software traversal matters there ([Godot integration](godot_integration.md)); upstream PR #122051, merged on 2026-08-04 for 4.8, requests the extension on Vulkan ([Godot ray tracing](../sources/2026_godot_ray_tracing_status.md#upstream-pull-requests), [RenderingDevice notes](../../docs/rendering_device.md#ray-tracing)). Inline queries suit one simple shading model and pipelines several: Microsoft's DXR 1.1 post and NVIDIA's best practices say so without numbers, NVIDIA warns that query objects cost registers and occupancy, and Evolve found no major difference on an RTX 5070 Ti and an Arc B580 but pipelines much faster on an RX 9070 XT; no measurement compares the two on Turing ([hardware ray tracing](../sources/2026_hardware_ray_tracing_rates.md#inline-ray-queries-against-pipelines)).

### Aila and Laine traversal

Persistent threads that fill the GPU once and pull rays from a global pool with an atomic counter, with "while-while" loops (traverse internal nodes until a leaf, then test its primitives), closing most of the gap to a simulated upper bound. Reference: Aila and Laine, "Understanding the Efficiency of Ray Traversal on GPUs", HPG 2009.

### Slab test

A ray hits an axis-aligned box when the largest per-axis entry `t` is at most the smallest exit `t`; with `t1,2 = (min_i or max_i − O_i)·(1/D_i)` swapped so `t1 ≤ t2`, IEEE infinities from `1/0` make zero components work without branches. Reference: Williams, Barrus, Morley and Shirley, "An Efficient and Robust Ray-Box Intersection Algorithm", JGT 10(1), 2005.

### Möller-Trumbore

Solve `O + tD = V0 + u·e1 + v·e2` by Cramer's rule: `det = e1·(D × e2)`, `u = s·(D × e2)/det`, `v = D·(s × e1)/det`, `t = e2·(s × e1)/det` with `s = O − V0`; hit if `u, v ≥ 0`, `u + v ≤ 1`, `t > 0`. Reference: Möller and Trumbore, JGT 2(1), 21-28, 1997. **Baldwin-Weber** stores a per-triangle transform to barycentric space, trading memory for a faster test (1 to 6% faster frames in PBRT): JCGT 5(3), 2016. **Watertight** (Woop, Benthin and Wald, JCGT 2(1), 2013) shears the triangle so the ray runs along +z and uses 2D edge functions, so rays never slip through shared edges.

### DDA grid traversal

Step a ray through a uniform grid one cell at a time, always crossing the nearest boundary: per axis keep `step = ±1`, `tMax` (the `t` of the next boundary) and `tDelta` (the `t` per cell), and advance the axis with the smallest `tMax`. Reference: Amanatides and Woo, "A Fast Voxel Traversal Algorithm for Ray Tracing", Eurographics 1987. 2D RC on bitmaps ([2D implementations](2d_implementations.md)) and voxel 3D RC use it.

### Hierarchical DDA

A DDA at each level of a VDB tree, stepping by that level's node size, so empty nodes are skipped whole. Reference: Museth, "Hierarchical Digital Differential Analyzer for Efficient Ray-Marching in OpenVDB", SIGGRAPH 2014 talk. Godot's HDDAGI is named after it ([HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md)).

### Sphere tracing

March along the ray by the distance-field value, a step that cannot cross the surface: `t += f(o + t·d)` until `f < ε` or `t` passes a limit. It needs only a Lipschitz bound on `f`. Reference: Hart, "Sphere Tracing", *The Visual Computer* 12(10), 527-545, 1996. The tracer of most 2D RC (JFA fields) and SDF-based 3D RC.

### Bresenham's line algorithm

Step the major axis once per pixel and the minor axis when an integer error term crosses zero (`V0 = 2Δb − Δa`; `V += 2Δb − 2Δa` on a diagonal step, `V += 2Δb` otherwise), with no multiplication or division. Reference: Bresenham, IBM Systems Journal 4(1), 25-30, 1965. Exact integer line tests in Sannikov's IntegerBlockHRC and line-space tilings in [HRC](holographic_rc.md#block-cascades) rest on the same lattice-line idea.

## Distance fields and voxelization

### Jump flooding

Approximates a Voronoi diagram and distance transform in about `log2 n` passes: each pixel keeps the nearest of the seeds held by its 8 neighbours at step `k`, with `k` halving from `n/2` to 1. JFA+1 adds a final step-1 pass, JFA+2 adds steps 2 and 1, JFA² adds `log n` passes, and 1+JFA runs one step-1 pass first, with far fewer errors than JFA+1. References: Rong and Tan, I3D 2006 ([notes](../sources/2006_rong_tan_jump_flooding.md)); Rong and Tan, ISVD 2007. The scene representation of most 2D RC ([2D implementations](2d_implementations.md)).

### Eikonal equation and fast sweeping

`|∇u| = f` describes distance (`f = 1`) or arrival time. Fast sweeping solves its Godunov upwind discretization `[(u − u_xmin)⁺]² + [(u − u_ymin)⁺]² = f²h²` with Gauss-Seidel sweeps in alternating orderings (4 in 2D, `2^n` in `n` dimensions), O(N) with a sweep count independent of grid size. Reference: Zhao, *Mathematics of Computation* 74(250), 603-627, 2005. **Fast marching** finalizes nodes in order of increasing arrival time from a heap: Sethian, PNAS 93(4), 1591-1595, 1996.

### GPU distance fields from meshes

DiFi rasterizes each primitive's distance function into grid slices, culled and clamped by bounds on its Voronoi region. Reference: Sud, Otaduy and Manocha, CGF 23(3), 2004.

### Conservative rasterization

Rasterize every pixel a triangle touches (overestimation) or only those it fully covers (underestimation); D3D12 tier 1 allows a 1/2-pixel uncertainty, tiers 2 and 3 1/256 pixel, and tier 3 adds inner coverage. Reference: Hasselgren, Akenine-Möller and Ohlsson, GPU Gems 2, ch. 42, 2005. **GPU voxelization:** project each triangle along its dominant axis, rasterize it conservatively and write fragments to a 3D image, averaging with atomics (Crassin and Green, "Octree-Based Sparse Voxelization Using the GPU Hardware Rasterizer", *OpenGL Insights*, 2012). How [voxel 3D RC](../sources/2026_voxel_3d_rc_repositories.md), [KingTheFifth](../sources/2026_rc_repository_survey.md#screen-probes-with-voxel-intervals-kingthefifth) and [HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md) build their grids.

### Draco

Google's mesh and point-cloud compression library: position quantization bits (`-qp`, default 11), compression level (`-cl`, default 7), Edgebreaker or sequential connectivity. Used for assets in [three-rc](../sources/2025_bennett_three_rc.md).

## Visibility, shadows and screen space

How these methods relate to RC, and the RC-specific variants (visibility-bitmask SSGI, PoE1's GI, line-sweep AO, horizon-based indirect light), are in [related screen-space GI](related_screen_space_gi.md). Godot implementations of SSAO, HBAO, SAO and GTAO in compute, with their parameters, costs and bugs, are in the [compositor examples](../sources/2026_godot_compositor_effect_examples.md).

### Shadow maps, acne and bias

A shadow map stores the depth of the nearest surface seen from the light; a point is lit if its own light-space depth is not greater. Many receiver points share one texel, and at grazing angles the stored depth sits above part of the surface, so the surface shadows itself in stripes (shadow acne). Depth bias subtracts a constant or slope-scaled offset before comparing (for example `max(0.05·(1 − n·l), 0.005)`); normal offset moves the lookup point along the normal by a multiple of the world-space texel size. Too much bias detaches shadows from their casters ("peter-panning"). Reference: Williams, "Casting curved shadows on curved surfaces", SIGGRAPH 1978 (secondary); no dated origin of the terms acne and normal offset was found. RC rays have the same problem at their start: a ray leaving a surface or a depth-buffer sample hits the surface it starts on, and the fixes are the same offsets ([three-rc](../sources/2025_bennett_three_rc.md), [Gavras](../sources/2025_gavras_screen_probes_world_intervals_thesis.md), [Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md), [screen-space RC](../sources/2026_screen_space_rc.md), [artifacts and fixes](artifacts_and_fixes.md)).

### Variance shadow maps and the Chebyshev bound

Store the first two moments of depth per texel, `M1 = E[z]` and `M2 = E[z²]`, which can be filtered and mipmapped linearly. For a receiver at depth `t > μ`, the one-sided Chebyshev (Cantelli) inequality bounds the fraction of the footprint that does not occlude it: `p_max = σ²/(σ² + (t − μ)²)` with `σ² = max(M2 − M1², σ²_min)`, and visibility is 1 for `t ≤ μ`. When two occluders at different depths overlap a footprint the variance is large and the bound stays high behind the nearer one, which shows as light bleeding. References: Donnelly and Lauritzen, "Variance Shadow Maps", I3D 2006 (formula secondary, from GPU Gems 3 ch. 8). The same test on stored mean and squared ray distance per probe direction is how [DDGI](../sources/2019_majercik_ddgi.md), [light-field probes](../sources/2017_mcguire_light_field_probes.md), [HSGI](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md), Enshrouded ([talks](../sources/2026_rc_conference_talks.md#enshrouded-a-cascaded-probe-cache)), [GIBS](../sources/2021_seed_gibs_surfel_gi.md) and the [SDFGI plan](../sources/2023_linietsky_godot_sdfgi_plan.md) keep probes from leaking through walls, and Sannikov's PoE1 GI applied it to two screen-space depth moments ([paper](../sources/2023_sannikov_radiance_cascades_paper.md)). RC intervals need no such test inside the cascade, because each interval carries its own transmittance; the question comes back only where a probe is interpolated across a wall (inference, [artifacts and fixes](artifacts_and_fixes.md)).

### Summed-area variance shadow maps

Summed-area tables of `z` and `z²` give the mean and variance over any axis-aligned rectangle from four lookups, so each receiver can use its own filter size for soft shadows. Light bleeding is reduced by mapping `p_max` below a threshold to 0 and rescaling the rest. Reference: Lauritzen, "Summed-Area Variance Shadow Maps", GPU Gems 3, ch. 8, 2007. Sannikov's trapezoid coverage test for depth marching against moments ([Shadertoys](../sources/2023_rc_shadertoys.md)) is a related closed form.

### Moment shadow maps and power moments

Store four power moments `(E[z], E[z²], E[z³], E[z⁴])` per texel (64 bits, 16-bit quantization works) and bound shadowing from the moment problem, much tighter than the two-moment bound. Reference: Peters and Klein, "Moment Shadow Mapping", I3D 2015; a solver-tolerance flaw in the original comparison was later rerun with the same conclusions. Peters's later transmittance work is in [Peters](../sources/2025_peters_jackknife_transmittance.md); Love and Deepspace blends overlapping surfel hits with four power moments of the hit points ([talks](../sources/2026_rc_conference_talks.md)).

### Chebyshev distance

Unrelated to the bound above: `max(|Δx|, |Δy|, |Δz|)`, the L∞ distance. Split RC sets probe LOD from the binary log of the Chebyshev distance to the camera, which gives fewer artifacts with grid-aligned probes than Euclidean distance ([Split RC](../sources/2026_freeman_split_radiance_cascades.md), [plugins](../sources/2026_unity_unreal_rc_plugins.md)); Sannikov's hemisphere map indexes texel rings by it ([Shadertoys](../sources/2023_rc_shadertoys.md)).

### Bent normals and bent cones

A bent normal is the mean unoccluded direction over the hemisphere, used in place of the normal to look up ambient light; a bent cone adds a half-angle so the visible region is a cone around it. Klehm et al. compute both in screen space alongside SSAO; GTAO derives the cone from its horizon angles assuming visibility is the same around the bent normal. References: Landis, "Production-Ready Global Illumination", SIGGRAPH 2002 course (secondary); Klehm, Ritschel, Eisemann and Seidel, "Bent Normals and Cones in Screen-space", VMV 2011. Used in [Mayaux](../sources/2018_mayaux_horizon_based_indirect_lighting.md), [Therrien](../sources/2022_therrien_visibility_bitmask_ssgi.md) and [Lumen](../sources/2022_wright_lumen_siggraph_advances.md).

### SSAO

Ambient occlusion from the depth buffer alone: sample depths around the pixel, count those in front of the surface and average, `AO ≈ 1 − (1/N)Σ occ_i`, with 8 to 16 samples rotated per pixel by a small noise texture and a depth-aware blur to remove the pattern. Reference: Mittring, "Finding Next Gen: CryEngine 2", SIGGRAPH 2007 course (the method credited to Kajalin at Crytek). Godot's AO multiplies indirect light only, as `min(material AO, SSAO)` ([indirect diffuse paths](../sources/2026_godot_indirect_diffuse_paths.md)).

### HBAO

Treats the depth buffer as a heightfield: for each of several screen directions, march to find the horizon angle above the tangent plane and integrate the occluded part of the hemisphere between them, with a falloff inside radius `R`. Reference: Bavoil, Sainz and Dimitrov, "Image-space horizon-based ambient occlusion", SIGGRAPH 2008 talks (algorithm from NVIDIA's GDC 2008 deck; the talk's equations were not read).

### GTAO

Splits the hemisphere into screen-space slices and integrates cosine-weighted visibility in closed form between the two horizon angles `h1`, `h2` of each slice: with `γ` the angle of the normal projected into the slice, `a = ¼(−cos(2h1 − γ) + cos γ + 2h1·sin γ) + ¼(−cos(2h2 − γ) + cos γ + 2h2·sin γ)` (the memo's Eq. 7, read from https://www.iryoku.com/downloads/Practical-Realtime-Strategies-for-Accurate-Indirect-Occlusion.pdf; the sum equals the slice integral of `cos(θ − γ)·|sin θ|` only with `h1 ≤ 0 ≤ h2`, the horizon on the far side of the view vector signed negative, which the memo's arccos horizons leave implicit, and it drops the memo's clamp of `cos(θ − γ)` to non-negative values, so it holds when both horizons lie in the hemisphere around the normal (derived)). Spatial and temporal filtering spread the slices over pixels and frames, and a thickness heuristic handles thin occluders; 0.5 ms on PS4 at 1080p. Reference: Jimenez, Wu, Pesce and Jarabo, "Practical Realtime Strategies for Accurate Indirect Occlusion", Activision ATVI-TR-16-01, 2016. Intel's XeGTAO uses 3 slices with 3 steps per side at its High preset. GTAO's horizons are what visibility-bitmask SSGI replaces with a bitmask of sectors ([Therrien](../sources/2022_therrien_visibility_bitmask_ssgi.md)).

### SAO

Scalable ambient obscurance keeps the math of McGuire's Alchemy AO but reads a mip pyramid of camera-space depth, so its cost no longer grows with radius or scene. Reference: McGuire, Mara and Luebke, HPG 2012 (abstract only). LSAO, which sweeps lines to get exact horizons, compares against it ([line-sweep AO](../sources/2013_timonen_line_sweep_ambient_obscurance.md)).

### Screen-space reflections

Trace reflection rays through the depth buffer and reuse the colour at the hit, so only what is on screen can be reflected. Stochastic SSR samples GGX with Halton points, traces at reduced resolution, shares rays among neighbours weighted by BRDF over PDF, picks a prefiltered colour mip from roughness and hit distance, and accumulates over frames. Reference: Stachowiak and Uludag, "Stochastic Screen-Space Reflections", SIGGRAPH 2015 Advances course; Stachowiak later wrote [kajiya](../sources/2022_stachowiak_kajiya_gi.md). Lumen traces screen space first and falls back to its own structures ([Lumen](../sources/2022_wright_lumen_siggraph_advances.md)).

### Screen-space indirect light (SSDO, SSIL, SSGI)

SSAO extended to directional occlusion and one diffuse bounce: samples of the lit frame buffer add colour, weighted by visibility. Reference: Ritschel, Grosch and Seidel, "Approximating Dynamic Global Illumination in Image Space", I3D 2009. The modern form is visibility-bitmask SSGI ([Therrien](../sources/2022_therrien_visibility_bitmask_ssgi.md)). Godot's SSIL reads the previous frame's lit colour and is applied as `ambient·(1 − ssil.a) + ssil.rgb·albedo` ([indirect diffuse paths](../sources/2026_godot_indirect_diffuse_paths.md)); [Gerassimov](../sources/2026_gerassimov_rc_vs_unity_gi.md) compares RC against Unity's SSGI.

### Depth thickness

A depth buffer holds one surface per pixel and no thickness, so screen-space tracers assume each pixel is a slab of thickness `z_t` behind the stored depth and count a hit when the ray's depth interval overlaps it. Too thin and rays pass through objects; too thick and rays hit phantom walls behind silhouettes. Reference: McGuire and Mara, JCGT 3(4), 2014 ([notes](../sources/2014_mcguire_mara_screen_space_ray_tracing.md)). Every screen-space RC chooses one ([screen-space RC](../sources/2026_screen_space_rc.md), [plugins](../sources/2026_unity_unreal_rc_plugins.md) with a fixed 3.0, [3D screen space](3d_screen_space.md)).

### G-buffer and deferred shading

Per-pixel images of the visible surface's attributes (depth, normal, albedo, material) written in one geometry pass, so later passes shade or trace without rasterizing again. Reference: Saito and Takahashi, "Comprehensible Rendering of 3-D Shapes", SIGGRAPH 1990. Screen-space RC reads its probe positions and normals from it.

### Premultiplied alpha and "over"

With colour stored premultiplied by alpha, compositing A over B is `C = C_A + (1 − α_A)·C_B`, `α = α_A + (1 − α_A)·α_B`, and filtering stays linear. Reference: Porter and Duff, "Compositing Digital Images", SIGGRAPH 1984. RC's merge `(L1, β1) ∘ (L2, β2) = (L1 + β1·L2, β1·β2)` is exactly this operator with `β = 1 − α` and emitted radiance as premultiplied colour ([core theory](core_theory.md), [HRC](../sources/2025_freeman_holographic_radiance_cascades.md), [merging and ringing](../sources/2026_merging_and_ringing.md)), which is why it is associative and why scene textures store emission times opacity ([tmpvar playground](../sources/2024_tmpvar_rc_playground.md)).
