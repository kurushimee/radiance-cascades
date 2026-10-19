# Scene representation and tracing: voxels and BVHs

Two families of world-space tracers that run as plain compute: voxel grids stepped by hierarchical DDA, from HDDAGI's bit-mask cascades to sparse voxel octrees, and triangle BVHs traversed in compute, from tinybvh's GLSL kernels to Wicked Engine's per-frame GPU build. What RC asks of a tracer, the comparison of all options, depth-buffer and distance-field tracing, shading the hit, robustness, and the connections, single-frame assessment and open questions for tracing are in [scene representation and tracing](scene_representation_and_tracing.md).

## Contents

- [Voxels](#voxels)
  - [The hierarchical DDA family](#the-hierarchical-dda-family)
  - [HDDAGI's voxel cascades](#hddagis-voxel-cascades)
  - [HSGI's sparse voxel cache](#hsgis-sparse-voxel-cache)
  - [GigaVoxels: sparse voxel octrees with ray-guided streaming](#gigavoxels-sparse-voxel-octrees-with-ray-guided-streaming)
  - [Voxelization in Godot](#voxelization-in-godot)
  - [Voxel tracing measured for RC](#voxel-tracing-measured-for-rc)
- [Triangle BVHs](#triangle-bvhs)
  - [tinybvh](#tinybvh)
  - [Wicked Engine: a BVH built on the GPU every frame](#wicked-engine-a-bvh-built-on-the-gpu-every-frame)
  - [BVH width and ray coherence](#bvh-width-and-ray-coherence)
  - [Other software BVHs in RC projects](#other-software-bvhs-in-rc-projects)
  - [Software against hardware](#software-against-hardware)

## Voxels

### The hierarchical DDA family

Three tracers in the sources step a DDA through cells of a level's size and skip empty blocks whole:

- **Museth's HDDA** (the OpenVDB traversal; [glossary](supporting_techniques_structures_and_tracing.md#ray-traversal-and-intersection)), which DexRT adopts with exact path lengths per segment and per-cascade mip caps ([volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)). DexRT's robustness rules: push `t` forward by 0.01 cell when entering an empty region, require the next-plane `t` to exceed the current one, and use an arithmetic shift, not division, for negative coordinates.
- **The two-level bitmask DDA** of Shadertoy lfyGRW (16×16 block flags, or an 8×8 bitmask per block as a u64), which skips uniform blocks with no error and no leaks ([volumetric](volumetric_and_radiative_transfer.md)).
- **HDDAGI's integer DDA** over 8³ regions, 4³ blocks and cells (below), and HSGI's GVDB-style occupancy bits.

All three descend where a block is occupied and climb back where it is empty, and none needs a distance field. Against sphere tracing they give exact first-hit cells with no thin-wall miss, at the cost of storing occupancy at every level (inference). Measured bit-level tracers for RC: a 2D DDA over 8×8 bit planes traced 11M rays in 1.2 ms, and a 3D DDA over 4×4×4 bit cubes traced 15M rays in about 5 ms; 4×4×4 brick bitmasks with a lookup table are another option (AMD's subspace culling, https://gpuopen.com/download/I3D2023_SubspaceCulling.pdf) ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#tracing-without-hardware-rt)).

### HDDAGI's voxel cascades

reduz's HDDAGI, the unmerged replacement for SDFGI ([Godot integration](godot_integration.md#hddagi) has its status), traces voxel cascades with an integer hierarchical DDA ([notes](../sources/2026_godot_hddagi_dynamic_gi.md#voxel-cascades)).

**Cascades.**

- Each cascade is 128 cells across in x and z; the default "16x8x16" format halves y to 64, and the other formats keep 128 in y and scale world y by 1, 1.5 or 2 before indexing. Up to 8 cascades, with cell size doubling per cascade from the minimum cell size (default 0.2).
- Storage per cascade, stacked along y by cascade index in shared textures: a 64-bit occupancy mask per 4³ block (`R32G32_UINT`, bit `z·16 + y·4 + x`); one flag per 8³ region (`R8_UINT`) and a version counter per region (`R16_UINT`) that invalidates cached probe hits; light per cell as RGBE (`R32_UINT` viewed as `E5B9G9R9`) plus a 26-bit mask of which neighbour directions can see the cell; per-face albedo and emission at half resolution; and 6 axis-facing bits plus 26 normal-bin bits per cell. For the default 128×64×128 cascade that is at least 128 KiB of occupancy, 4 MiB of light and 4 MiB of normal bits, about 8.1 MiB before the half-resolution albedo and emission (derived; the pull request gives no memory figures).
- Only empty cells next to a solid face are lit. They go in a process list of 16-byte entries: position (7 bits per axis), RGB565 albedo with an 8+8 octahedral normal, RGBE emission, and 8 four-bit probe occlusion weights. Capacity is `128·64·128·solid_cell_ratio` (default 0.5); extra entries are dropped.
- Cascades follow the camera in steps of one 8-cell region and never copy data: addresses wrap with a mask, and only the newly uncovered slabs are revoxelized. A move of a whole cascade, or a dirty volume over half the cascade, rebuilds it. SDFGI regenerated its whole field on camera motion, which is where the claimed order-of-magnitude faster updates come from.
- Voxelization runs in the forward scene shader's `MODE_RENDER_SDF` block (`scene_forward_clustered.glsl:2224` at the #86267 head). It takes the geometric normal from `dFdx`/`dFdy` of the position, maps the fragment to a cell (`sdf_offset + local_pos·sdf_size`), and sets normal bits: bits 0 to 5 for the axis directions with `dot > 0.001`, bits 6 to 31 for the 26 bin directions with `dot > 0.7`. It ORs them atomically into the `r32ui` image `geom_normal_bits` (set 1, binding 27) and writes albedo per axis sign (6 layers) and RGBE emission at half resolution (`igrid_pos >> 1`). The comments say "solid bits" and a "Compute solid bits" heading has no code under it: solidity is derived later, when `hddagi_preprocess.glsl` counts any nonzero normal word as solid and sets the region bits. The MoltenVK branch does a non-atomic load and store with `bit_ofs`, a name defined in neither the shader nor its include, so that branch would not compile.

**The walk** ([notes](../sources/2026_godot_hddagi_dynamic_gi.md#hierarchical-dda)) covers three levels, 8³ regions, 4³ blocks and single cells, in integer fixed point with 8 fractional bits (one cell is 256 units). It descends when the current cell at a level is occupied and climbs back up when the position leaves the parent, with no distance-based level of detail:

```glsl
ivec3 mask = level_masks[level];
ivec3 box = mask * step;
ivec3 pos_diff = box - (pos & mask);
ivec3 tv = mix(pos_diff * inv_ray_dir_fp, ivec3(0x7FFFFFFF), ray_zero) >> fp_bits;
int t = min(tv.x, min(tv.y, tv.z));
ivec3 adv_box = pos_diff + ray_sign;
ivec3 adv_t = (ray_dir_fp * t) >> fp_bits;
pos += mix(adv_t, adv_box, equal(ivec3(t), tv));
```

- A ray that leaves a cascade converts to world space and continues in the next coarser cascade; it never goes finer. The loop has no iteration cap and ends after the last cascade.
- A hit returns the cell, the crossed face and the cascade; radiance is the light texel of the empty cell on the hit face's side.
- Shadow rays for direct light use the same walk with a distance limit and 10 fractional bits.
- Cost scales with the amount of geometry in the level but not its triangle count (reduz). The walk needs only 32-bit integer operations and the 64-bit mask is read as two 32-bit words, so it fits Godot's driver, which has no 64-bit atomics ([RenderingDevice notes](../../docs/rendering_device.md#atomics)) (inference).

### HSGI's sparse voxel cache

HSGI (LIGHTSPEED STUDIOS, GDC 2023) is not RC; its "surfels" are voxels with a normal in a sparse brick clipmap traced with a hierarchical DDA, the same structure as HDDAGI ([notes](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md#voxel-radiance-cache)). Its GI paths are in [related engine GI](related_engine_gi.md).

- Bricks of 4³ voxels in a sparse clipmap are addressed like a virtual texture: a dense "hierarchy link" grid holds a brick ID per allocated brick (zero otherwise), a pool indexed by brick ID holds the voxel data, and an allocator tracks free IDs.
- Per voxel: diffuse colour, direct and indirect outgoing radiance, normal, alpha, an age weight and masks, 128 bits in 4 textures on PC and 64 bits in 2 textures on mobile. Range: 100+ m on mobile and 500+ m on PC.
- Camera motion uses toroidal addressing; only the wrapped band is cleared, by a flag per voxel or brick.
- Tracing follows GVDB: 1 bit of occupancy per voxel, read 64 bits per fetch, with the sparse mip 0 trading trace speed for memory.

How it is filled is under [shading the hit](scene_representation_and_tracing.md#radiance-at-the-hit-from-the-lit-frame).

### GigaVoxels: sparse voxel octrees with ray-guided streaming

Cyril Crassin's PhD thesis (supervisor Fabrice Neyret, Université de Grenoble, defended 2011-07-12, 207 pages, https://maverick.inria.fr/Publications/2011/Cra11/CCrassinThesis_EN_Web.pdf) is the structure behind voxel cone tracing ([related probe GI](related_probe_gi.md)): a sparse voxel octree with bricks in a 3D texture, rendered by pre-integrated cone tracing and streamed on demand by the rays themselves ([notes](../sources/2011_crassin_gigavoxels_thesis.md)). The RC discussions link it for its storage and streaming design. Chapters 4 to 7 and 9 were read, in part for 4, 6 and 7; appendix A was not. Page numbers are the printed ones, equal to the PDF's.

**Octree and bricks (ch. 5).**

- One child pointer per node, with siblings stored together in blocks of `N³` nodes (`N = 2`), grouped as 2×2×2 node tiles in linear memory (pp. 100-101). A node is two 32-bit words: flags (terminal, and whether the second word is a constant or a brick pointer) with a 30-bit child pointer, and a constant colour or a 30-bit brick pointer (p. 102).
- Bricks live in a 3D texture, so trilinear filtering is hardware; data are split into structure-of-arrays layers. Brick addresses are three 10-bit coordinates. Addressing limits: `2^30` tiles × 64 B = 64 GB of nodes and `2^30` bricks of 8³ RGBA8 voxels = 2 TB (p. 103).
- Node-centred bricks need at least 8³ voxels without a border (p. 98); for Sponza and Coral the storage optimum was 4³ corner-centred bricks (p. 104).
- Sponza takes 68.48 MB of bricks and 1.93 MB of octree, 70.41 MB, 6.88% of a dense mip pyramid; Coral 4.9%. A dense 512³ pyramid is given as 1023 MB, which matches 8 bytes per voxel (derived from p. 142's 8 B per voxel).

**Rendering (ch. 4, 6).** Rendering splits into top-down octree traversal and brick sampling, which communicate through video memory (p. 108). The level of detail follows the node's projected size (p. 109). A constant node is crossed in one step; a brick is ray-marched with trilinear samples. Each pixel footprint is an orthographic beam, and a cone is one ray sampled at the mip level matching its footprint, with linear interpolation between levels (pp. 79-86). Pre-integrated transport (eq. 4.9, p. 83) is

```
I(D, P) ≈ Σ_i [∫_P Q(s_i, s_{i+1}, r) dr] · Π_{j>i} [∫_P exp(−τ(s_j, s_{j+1}, r)) dr]
```

with the mean in-scattered energy `Q` and mean transparency precomputed per voxel and level. Per voxel `T = exp(−κ·dx)` with `κ = κ'·ρ` and `dx` the voxel size, and colour is premultiplied by `α = 1 − T` (p. 91). Cone footprints have no closed form; measured footprints are plotted for 11.25° and 22.5° apertures (p. 86).

**Streaming (ch. 7).** Each ray reports the nodes and bricks it needs at the resolution it needs; misses become requests, and rays may stop early (p. 74). Node tiles and bricks have separate caches with fine-grained LRU replacement on the GPU (pp. 121-122). Requests are batched during rendering and served in an update phase (p. 125) by producers that load from system memory, compute procedurally or read from disk; a 256 GB dataset streams on demand (pp. 122, 150). A real-time mode loads bricks first with one render-and-update pass per frame; a quality-first mode runs as many refining passes as the frame budget allows (pp. 125-127). Example pools (p. 142): 262,144 node tiles (2,097,152 nodes × 8 B = 16 MB) and 110,592 bricks of 8³ (56,623,104 voxels × 8 B = 432 MB), with 13.84 MB of management buffers, 3.08% overhead. Miss rates at 4× exploration speed: 2.6% with a 512 MB brick cache and 5.9% with 128 MB (p. 152).

| Scene | Size | GPU | Frame rate |
|---|---|---|---|
| Lion | 2048³, 64 GB on disk, 512² output | GTX 480 | 60 to 80 FPS (pp. 95, 148) |
| CT scan | 2048³, 32 GB | GTX 280 | 20 FPS (p. 105) |
| Teaser scene | 8192³ | GTX 280 | 20 to 40 FPS (p. 148) |
| Procedural fractal | | GTX 480 | 70 to 90 FPS (p. 150) |
| Visible Male | 4096³, 256 GB | GTX 280 | 15 to 20 FPS (p. 150) |
| Power Plant, 13M triangles, GPU triangle cache | | GTX 280 | 15 to 30 FPS (p. 155) |
| Dragon | 1024³ | not stated | about 80 FPS (p. 95) |

**Indirect light (ch. 9).**

- Two bounces, diffuse and glossy, at 25 to 70 FPS on a GTX 480 (p. 165). Light is injected by rasterizing from each light and splatting into the leaves, filtered up the octree with incoming directions stored as Gaussian lobes, and gathered with about five wide diffuse cones and one specular cone whose aperture follows the specular exponent (p. 167).
- Weighting each voxel by the inverse of its multiplicity gives a 3×3×3 Gaussian kernel (p. 170). Bricks are 3×3×3 and corner-centred, and nodes gain neighbour pointers (pp. 168-169). The octree is built on the GPU by rasterization without a full intermediate grid; semi-static geometry is voxelized once and dynamic objects every frame, separated by time stamps (p. 169).
- Table 9.1 (p. 175), Sponza (280K triangles, 9-level octree, 512³ virtual), 512² image, 3 diffuse cones and a 10° specular cone: rasterization 1.0, direct 2.0, indirect diffuse 7.8, direct plus diffuse 14.2, indirect specular 8.0, total 33.0 ms. The paper's version of the table prints 22.0 ms as the total, so the two disagree, and neither total is a sum of the listed parts (derived).
- A 16K-triangle hand updates in about 5.5 ms and the static octree takes about 280 ms; Sponza runs at 30 FPS without and 20 FPS with the specular cone (GTX 480, Core 2 Duo E6850). Against Kaplanyan and Dachsbacher's LPV: 31 against 27 FPS (Fig. 9.10). AO runs at 70 to 150 FPS, and at 153 FPS against 0.1 FPS for an OptiX reference (Figs. 9.11-9.12). About 512 MB of GPU memory are allocated (p. 176), where the paper says about 1024 MB.

Two points carry to RC (inference). Ray-guided streaming, in which rays request data at the resolution they need, maps onto the interval structure: upper cascades' long intervals need only coarse levels, so a sparse RC scene can be streamed per cascade by the same request scheme. Pre-integrated transparency per voxel and level is the volumetric mip that mip-marched RC uses, with the same nonlinearity: averaging `T` over a footprint is not `exp` of the averaged density ([volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)).

### Voxelization in Godot

- Godot's `RenderingDevice` has no geometry shader stage, so tauray's single-pass dominant-axis voxelization ([sampling and guiding](rc_for_sampling_and_guiding_rcpg.md#tauray-code)) does not port directly.
- SDFGI's own route is three orthographic raster passes, one per axis, writing 3D images; HSGI does the same per object with depth testing off and each object's own material shader. HDDAGI voxelizes inside the forward scene shader's SDF mode (above). A compute pass over the triangles is the other route, as daGI2 uses above a voxel-size threshold and Brixelizer for its references (inference for Godot).
- Mesh data reaches GDScript through `mesh_surface_get_arrays()`; the engine's own mesh buffers are not exposed as RIDs ([RenderingDevice notes](../../docs/rendering_device.md#ray-tracing)). Skinned meshes need their own path; gomezzz rejects them ([Godot projects](godot_projects.md#scene)).

### Voxel tracing measured for RC

From the sparse 3D builds ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#tracing-without-hardware-rt); the pairing with world-space cascades is in [3D world space](3d_world_space.md#tracing-for-world-space-cascades)):

- A two-level grid (16³ cells over 4³ bricks) traced 2× faster than an H-PLOC BVH, though more slowly on AMD than on NVIDIA.
- Sparse voxel cone tracing came within about 1.8× of hardware RT.
- Each cascade needs the scene filtered to its probe spacing, and averaged 2×2×2 mips make thin walls half transparent at every level, so averaged mips need six-direction opacity.
- creikey's clipmap of four 64³ levels (1, 4, 16 and 64 m cells, 12 MiB) stores albedo, density and injected light per cell and puts dynamic objects in a separate small clipmap rebuilt per frame with `atomicMax` to resolve overlaps; geometry thinner than a voxel leaks ([implementations](3d_world_space_implementations_grids.md#creikeyvoxel-radiance-cascades)).

## Triangle BVHs

### tinybvh

https://github.com/jbikker/tinybvh (Jacco Bikker, MIT, read at c9be310) ships Vulkan GLSL compute kernels for each of its GPU layouts, the closest ready-made match for a GLSL compute tracer without hardware ray tracing, such as one under Godot's `RenderingDevice`; Coppen's surfel RC credits it for its traversal ([notes](../sources/2026_compute_bvh_libraries.md#tinybvh-layouts), [surface probes](3d_surface_probes.md)).

| Layout | Node | Child bounds | Triangles | Built from |
|---|---|---|---|---|
| `BVH_GPU` (2-wide, Aila-Laine) | 64 B | float32 | 48 B: `v0`, `v1 − v0`, `v2 − v0` as float4, leaf order | the default BVH |
| `BVH4_GPU` (4-wide) | 64 B | uint8 per axis | 48 B, stored right after the leaf's node data | a 4-wide MBVH |
| `BVH8_CWBVH` (8-wide, compressed wide BVH) | 80 B | uint8 per axis with a per-node exponent | 64 B (Baldwin-Weber transform) or 48 B | an 8-wide MBVH with leaves of 1 to 3 triangles |

- `BVH_GPU` node: left bounds plus left index, right bounds plus right index, in four 16-byte fields. A child index with bit 31 set is a leaf, with the triangle count in bits 24 to 30 (at most 127) and the offset in bits 0 to 23.
- `BVH4_GPU` quantizes each child box against the node box with scale `254.999/extent`, rounding minimums down and maximums up so boxes stay conservative. The C++ struct in the header is not the real layout; the packing in `ConvertFrom` is.
- CWBVH stores the node origin, three exponent bytes, an internal-child mask, child and triangle base indices, one meta byte per child, and six bytes of quantized bounds per child; the exponent per axis is `ceil(log2(extent/255))`. Children sit in slots by direction octant so traversal can visit them roughly front to back with an XOR.
- The `w` lanes carry extras: the original primitive index in `v0.w` and a vertex colour slot in `edge1.w`. A source comment says the compressed CWBVH triangle format "doesn't seem to help on GPU", with no measurement.

**Building and updating** ([notes](../sources/2026_compute_bvh_libraries.md#building-and-updating)). All layouts build on the CPU in C++. The default builder is Bonsai; binned SAH, spatial splits (SBVH) and H-PLOC are options, and an optimizer runs insertion-based tree rotations (25 iterations by default), which cut SAH cost by about 8% on Crytek Sponza (262k triangles) in under half a minute. Refit exists only for the CPU-side BVH, is refused for spatial-split trees and for a TLAS, and does not apply to the GPU layouts, which are rebuilt by converting again. A TLAS is a `BVH_GPU` built over instances, each pointing to a BLAS, with a 16-bit ray mask per instance; the README calls rebuilding the small TLAS after moving instances cheap rigid animation, with no timing.

**Traversal kernels** ([notes](../sources/2026_compute_bvh_libraries.md#traversal-kernels)), all one thread per ray with a stack array, none stackless:

| Kernel | Language | Layout | Stack | Overflow |
|---|---|---|---|---|
| `kernels/traverse_bvh2.cl` | OpenCL | `BVH_GPU` | 32 entries, private | not checked |
| `kernels/traverse_bvh4.cl` | OpenCL | `BVH4_GPU` | 32, private | not checked |
| `kernels/traverse_cwbvh.cl` | OpenCL | CWBVH | 24 `uint2`, private | not checked |
| `kernels/traverse_tlas.cl` | OpenCL | TLAS over `BVH_GPU` or CWBVH BLASes | 32, private | not checked |
| `external/vulkanrt/shaders/tiny.comp` | GLSL 460 compute | `BVH_GPU` | 32 per thread in shared memory, 8 KB per 8×8 group | the far child is dropped |
| `external/vulkanrt/shaders/tiny4.comp` | GLSL 460 compute | `BVH4_GPU` | 64, private | the far children are dropped |
| `external/vulkanrt/shaders/tiny8.comp` | GLSL 460 compute | CWBVH | 8 per thread in two shared arrays | remaining siblings are dropped |
| `tmpl8_compute/shaders/traverse.comp` | GLSL 430 compute | `BVH_GPU` | 64, private | not checked |

- The OpenCL kernels have closest-hit and any-hit (occlusion) versions. The Vulkan GLSL kernels have closest hit only and write a depth image from primary rays, so an RC tracer adapts them: segment `tmin` and `tmax`, an any-hit early out, and hit data for shading.
- Shared-memory stacks are indexed depth-major (`stack[depth·GROUP_SIZE + lane]`) so neighbouring threads hit neighbouring banks. The CWBVH kernel pushes at most one node group per level; its comment gives a measured stack peak of 6 at 450k primitives, which is why 8 entries suffice there. The comment's "8 KB per group" is wrong for the declared arrays, which total 4 KB. A full stack silently drops nodes.
- Node tests are slab tests with `fma`; triangle tests are Möller-Trumbore, and several versions skip the near-parallel `|a|` check. The compressed CWBVH test is division-free until a candidate hit survives.
- The TLAS kernel transforms the ray into each instance's space with its inverse transform, keeps the nearest hit, and stores the instance index in the top 8 bits of the hit's primitive word. A NaN ray returns a miss.

**Measurements** ([notes](../sources/2026_compute_bvh_libraries.md#measurements)). The README claims up to 5 billion rays per second in Crytek Sponza with the 2-wide layout on an RTX 5080 laptop GPU without RT hardware, and "5 rays per pixel at 4k@120Hz", ray type not stated. Its CPU-against-GPU chart (Ryzen AI 9 HX 370 against RTX 5080, unlabelled, read from bar heights) shows about 3 G rays/s nearest hit and about 4 G rays/s any hit on the GPU. A CPU build of Sponza (263k triangles) with the fast builder took about 6.7 ms against 17.5 ms for Embree (read from a chart).

**unity-tinybvh** (https://github.com/andr3wmac/unity-tinybvh, Andrew MacIntyre, MIT, read at 6a4f2e0) builds one CWBVH BLAS per mesh at start on a worker thread, never rebuilds or refits them, and rebuilds the TLAS on the CPU every frame so instance transforms can change, then uploads it. One HLSL compute kernel, 64 threads per group, closest hit only; the TLAS uses the 64-byte `BVH_GPU` node with a 32-entry private stack, and CWBVH BLAS traversal also uses 32 entries, neither checking for overflow. Its triangle test rejects `transD == 0`, unlike the tinybvh kernels. No timings are recorded.

**obvhs** (https://github.com/DGriffin91/obvhs, Rust, MIT or Apache-2.0, read at 2cf08de) is CPU-only. It builds a BVH2 with PLOC, optional spatial pre-splits and parallel reinsertion, then converts it to an 80-byte CWBVH node with leaves of up to 3 primitives; presets run from `fastest_build` to `very_slow_build`, and `medium_build` aims at Embree's build time with faster traversal. It has no shaders (GPU traversal lives in the separate Tray Racing repository). Its BVH2 supports refit, insertion, removal and moving leaves, and the refit docs warn that moved leaves can degrade the tree until it is rebuilt or reinserted. A 24-byte compressed triangle (float `v0` plus two half-float edges) is defined but unused by any traversal in the repository, and its CPU traversal stack saturates instead of overflowing: a push onto a full stack overwrites the top entry.

### Wicked Engine: a BVH built on the GPU every frame

Wicked Engine (János Turánszki, MIT; `wiGPUBVH.cpp`, the `bvh_*CS.hlsl`, `raytracingHF.hlsli` and `ddgi_raytraceCS.hlsl` shaders, read at cb4a81c) traces its DDGI and surfel GI through hardware ray queries when the device has them and otherwise through a BVH it builds in compute shaders; the same shader source compiles to both, and the engine picks one at load time ([notes](../sources/2026_compute_bvh_libraries.md#wicked-engine-a-bvh-built-on-the-gpu-every-frame)).

**Build**, a full rebuild of one BVH over all scene triangles in world space every frame that DDGI or surfel GI is on, with no refit:

1. Gather primitives: one 64-thread dispatch per mesh subset (and per hair system and particle emitter) writes each triangle's world-space vertices, a flag word, an identity ID and a 30-bit Morton code of its bounding-box centre, normalized to the scene's bounds (10 bits per axis, so 1024 cells per axis).
2. Sort the Morton codes with their IDs: AMD's FidelityFX parallel radix sort, 4 bits per pass over all 32 bits (8 passes), 128-thread groups, dispatched indirectly from a GPU counter.
3. Build the hierarchy with Karras 2012 ("Maximizing Parallelism in the Construction of BVHs, Octrees, and k-d Trees"): one thread per internal node finds its key range and split from common prefixes. Internal nodes are 0 to N−2 with the root at 0, leaves N−1 to 2N−2, and equal codes are told apart by index.
4. Propagate bounds bottom-up: one thread per leaf walks to the root; a bit per internal node set with `InterlockedOr` lets the first child to arrive stop, so the second merges both boxes once they are ready.

**Layout:** a 32-byte node (min, left child, max, right child; a leaf stores its primitive index) and a 48-byte primitive (packed instance, subset and triangle IDs, flags, three world-space vertices). Materials and UVs are not in the BVH; a hit looks them up through the instance and mesh buffers. Buffers grow to the scene's triangle count with no headroom. With `2N − 1` nodes that is about 112 bytes per triangle, 107 MiB for a million triangles; Vulkan guarantees only 128 MiB per storage buffer, which caps the node buffer near 2.1 million triangles unless it is split (derived, [RenderingDevice notes](../../docs/rendering_device.md#limits)).

**Traversal:** closest-hit and any-hit loops with a 32-entry stack per thread (local array by default, shared memory as an option), both children pushed with no front-to-back order, and the loop stopped on overflow with the best hit so far. Slab tests on nodes and Möller-Trumbore on triangles. A triangle flagged transparent (alpha-tested or blended material) loads its full surface, textures included, and counts as a hit when `opacity − random ≥ 0`, so foliage casts stochastic shadows in the compute path; the hardware path forces primary rays opaque.

**DDGI with it:** each probe gets 4 to 512 rays per frame in steps of 4, scaled by its measured inconsistency and cut to a tenth outside the view frustum (512 for every probe on the first frame), on a spherical Fibonacci set rotated randomly each frame. A hit loads the full surface, samples one random light with a shadow ray, adds last frame's probe irradiance for more bounces, multiplies by albedo and adds emission. Radiance is clamped to the half-float range before storing, because a bright sky turned into NaN in firefly suppression. No timings are given anywhere in the code.

Every pass is a plain compute dispatch with integer atomics, which Godot's `RenderingDevice` supports, so it is a template for dynamic triangle scenes without hardware ray tracing, and it removes the CPU rebuild that makes gomezzz reset its history when meshes move (inference).

### BVH width and ray coherence

The claim that a binary BVH beat an 8-wide compressed BVH by 2× for SPWI because RC rays are coherent cites tinybvh issue 238 (https://github.com/jbikker/tinybvh/issues/238), which measures tinybvh's primary-ray speedtest, not SPWI ([screen-space notes](../sources/2026_screen_space_rc.md#measurements)):

| Device and path | `BVH_GPU` (2-wide) | `BVH4_GPU` | CWBVH |
|---|---|---|---|
| Radeon iGPU, rusticl OpenCL | 6.32 MRays/s | | 121.06 MRays/s |
| RX 5700 XT (after a May 2026 NVIDIA driver update the GPU formats came out close) | 1093 MRays/s | 1072 | 858 |
| RTX 5080 laptop | 2.8 G rays/s | 1.9 G | 1.4 G |

The maintainer puts CWBVH's deficit down to its OpenCL traversal code, which lost the CUDA original's shared-memory stack, says OpenCL needs separate paths per vendor and that BVH2 is the clear winner on Apple, and keeps CWBVH mostly for history; incoherent rays were not tested. The issue therefore supports BVH2 for coherent rays in tinybvh's OpenCL code, with the cause given as traversal code, not ray coherence alone. Smaller BVH stacks saved a few ms on an M2. A binary BVH beat wide BVHs for coherent RC rays in the sparse builds too ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#tracing-without-hardware-rt)). For GLSL compute, as under Godot, tinybvh's 2-wide `tiny.comp` is the lowest-risk starting point (inference).

### Other software BVHs in RC projects

- gomezzz builds a binned-SAH BVH on the CPU in GDScript (8 bins per axis, leaves of up to 4 triangles), flattened in preorder with an escape index for stackless traversal, with 48-byte nodes (`lower.xyz`, `upper.xyz`, and `links` = first triangle, triangle count, escape index) and 80-byte triangles (`a`, `b`, `c`, albedo, emission); the build took about 1.2 s for 72,012 triangles, so moving meshes need a rebuild and reset the history ([Godot projects](godot_projects.md#scene)).
- wroughtinator's native Split RC build uses a CPU-built binned SAH BVH (16 bins, leaves of 4) and a 64-entry GPU stack, all in one GLSL compute source ([implementations](3d_world_space_implementations.md)).
- three-rc uses three-mesh-bvh with one triangle per leaf; its node layout and GLSL ray functions are in [three-rc](3d_screen_space_implementations.md#three-rc).
- Coppen's surfel RC traverses a binary BVH with a 32-entry stack and Möller-Trumbore triangles, credited to tinybvh ([surface probes](3d_surface_probes.md)).
- Blackline Interactive's engine lists tinybvh among its libraries (2026-10). An earlier build's HUD showed a binary BVH over 2.83 M triangles in Bistro: 1,723,357 nodes, 861,679 leaves (about 3.3 triangles each), depth 32 and 95.8 MB. The later builds trace in compute on a GPU without RT hardware at 0.22 to 0.43 G rays per second of GI time ([Blackline](../sources/2026_blackline_interactive_spatium_rc.md#derived-numbers)).

### Software against hardware

- Software traversal measured 231 µs against 66 µs for hardware ray tracing on the same Split RC workload, about 3.5×, and one optimized software ray tracer ran about 4× slower than hardware RT on Apple M3 ([3D world space](3d_world_space.md#tracing-for-world-space-cascades)).
- Lumen rejected software BVHs and grids as too slow for long incoherent rays, while the RC builds found a two-level grid 2× faster than an H-PLOC BVH and Brixelizer beat DXR on short rays but lost badly on long ones. The common factor is ray length: grids and distance fields win on short segments and lose on long divergent rays, where BVHs and hardware RT keep their cost (inference). RC's low cascades are short segments; its upper cascades are the long rays, which coarse mips shorten in steps ([connections](scene_representation_and_tracing.md#connections)).
