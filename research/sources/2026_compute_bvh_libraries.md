# Compute-shader BVH libraries: tinybvh, unity-tinybvh, obvhs, Wicked Engine

| | |
|---|---|
| tinybvh | https://github.com/jbikker/tinybvh (Jacco Bikker, MIT), read at commit c9be310 |
| unity-tinybvh | https://github.com/andr3wmac/unity-tinybvh (Andrew MacIntyre, MIT), read at commit 6a4f2e0 |
| obvhs | https://github.com/DGriffin91/obvhs (Rust, MIT or Apache-2.0), read at commit 2cf08de |
| Wicked Engine | https://github.com/turanszkij/WickedEngine (János Turánszki, MIT), `wiGPUBVH.cpp` and the `bvh_*CS.hlsl`, `raytracingHF.hlsli` and `ddgi_raytraceCS.hlsl` shaders, read at commit cb4a81c |

These are BVH builders with GPU node layouts that a compute shader can traverse without hardware ray tracing. tinybvh ships Vulkan GLSL compute kernels for each layout, which is the closest ready-made match for a GLSL compute tracer without hardware ray tracing, such as one under Godot's `RenderingDevice`. Coppen's surfel RC credits tinybvh for its traversal code ([surfel RC](2025_coppen_surfel_radiance_cascades.md)). Wicked Engine is the one that builds on the GPU: it rebuilds its whole BVH in compute shaders every frame, so moving meshes cost no CPU work.

## Contents

- [tinybvh layouts](#tinybvh-layouts)
- [Building and updating](#building-and-updating)
- [Traversal kernels](#traversal-kernels)
- [Measurements](#measurements)
- [unity-tinybvh](#unity-tinybvh)
- [obvhs](#obvhs)
- [Wicked Engine: a BVH built on the GPU every frame](#wicked-engine-a-bvh-built-on-the-gpu-every-frame)

## tinybvh layouts

| Layout | Node | Child bounds | Triangles | Built from |
|---|---|---|---|---|
| `BVH_GPU` (2-wide, Aila-Laine) | 64 B | float32 | 48 B: `v0`, `v1 − v0`, `v2 − v0` as float4, leaf order | the default BVH |
| `BVH4_GPU` (4-wide) | 64 B | uint8 per axis | 48 B, stored right after the leaf's node data | a 4-wide MBVH |
| `BVH8_CWBVH` (8-wide, compressed wide BVH) | 80 B | uint8 per axis with a per-node exponent | 64 B (Baldwin-Weber transform) or 48 B | an 8-wide MBVH with leaves of 1 to 3 triangles |

- `BVH_GPU` node: left bounds plus left index, right bounds plus right index, in four 16-byte fields. A child index with bit 31 set is a leaf, with the triangle count in bits 24 to 30 (at most 127) and the offset in bits 0 to 23.
- `BVH4_GPU` quantizes each child box against the node box with scale `254.999/extent`, rounding minimums down and maximums up so the boxes stay conservative. The C++ struct in the header is not the real layout; the packing in `ConvertFrom` is.
- CWBVH stores the node origin, three exponent bytes, an internal-child mask, child and triangle base indices, one meta byte per child, and six bytes of quantized bounds per child. The exponent per axis is `ceil(log2(extent/255))`. Children are put in slots by direction octant so that traversal can visit them roughly front to back with an XOR.
- The `w` lanes carry extras: the original primitive index in `v0.w` and a vertex color slot in `edge1.w`.
- The source comments that the compressed CWBVH triangle format "doesn't seem to help on GPU", with no measurement.

## Building and updating

- All layouts build on the CPU in C++. The default builder is Bonsai; binned SAH, spatial splits (SBVH) and H-PLOC are options, and an optimizer runs insertion-based tree rotations (25 iterations by default).
- Refit exists only for the CPU-side BVH, is refused for spatial-split trees and for a TLAS, and does not apply to the GPU layouts, which are rebuilt by converting again.
- A TLAS is a `BVH_GPU` built over instances, each pointing to a BLAS. Instances carry a 16-bit ray mask. The README calls rebuilding the small TLAS after moving instances cheap rigid animation, with no timing given.
- The offline optimizer cut SAH cost by about 8% on Crytek Sponza (262k triangles) in under half a minute.

## Traversal kernels

All kernels use one thread per ray and a stack array; none is stackless.

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

- The OpenCL kernels have both closest-hit and any-hit (occlusion) versions. The Vulkan GLSL kernels have closest hit only and write a depth image from primary rays, so an RC tracer would adapt them: segment `tmin` and `tmax`, an any-hit early out, and hit data for shading.
- Shared-memory stacks are indexed depth-major (`stack[depth·GROUP_SIZE + lane]`) so neighboring threads hit neighboring banks. The CWBVH kernel pushes at most one node group per level; its comment gives a measured stack peak of 6 at 450k primitives, which is why 8 entries are enough there. The comment's "8 KB per group" is wrong for the declared arrays, which total 4 KB.
- Node tests are slab tests with `fma`. Triangle tests are Möller-Trumbore, and several versions skip the near-parallel `|a|` check. The compressed CWBVH test is division-free until a candidate hit survives.
- The TLAS kernel transforms the ray into each instance's space with its inverse transform, keeps the nearest hit, and stores the instance index in the top 8 bits of the hit's primitive word. A NaN ray returns a miss.

## Measurements

- The README claims up to 5 billion rays per second in Crytek Sponza with the 2-wide layout on an RTX 5080 laptop GPU without RT hardware, and "5 rays per pixel at 4k@120Hz". The ray type is not stated.
- Its CPU-against-GPU chart (Ryzen AI 9 HX 370 against RTX 5080, no labels, read from bar heights) shows about 3 G rays/s nearest hit and about 4 G rays/s any hit on the GPU.
- CPU build of Sponza (263k triangles) with the fast builder: about 6.7 ms, against 17.5 ms for Embree (read from a chart).

## unity-tinybvh

- Builds one CWBVH BLAS per mesh at start on a worker thread, never rebuilds or refits them, and rebuilds the TLAS on the CPU every frame so instance transforms can change, then uploads it.
- One HLSL compute kernel, 64 threads per group, closest hit only. The TLAS uses the 64-byte `BVH_GPU` node and a 32-entry private stack; CWBVH BLAS traversal also uses a 32-entry stack. Neither checks for overflow.
- Its triangle test rejects `transD == 0`, unlike the tinybvh kernels.
- No timings are recorded.

## obvhs

- CPU-only Rust library. It builds a BVH2 with PLOC, optional spatial pre-splits and parallel reinsertion, then converts it to an 80-byte CWBVH node with leaves of up to 3 primitives. Build presets run from `fastest_build` to `very_slow_build`; `medium_build` aims at Embree's build time with faster traversal.
- It has no shaders; GPU traversal lives in the separate Tray Racing repository.
- Its BVH2 supports refit, insertion, removal and moving leaves. The refit docs warn that moved leaves can degrade the tree until it is rebuilt or reinserted.
- A 24-byte compressed triangle (float `v0` plus two half-float edges) is defined but not used by any traversal in the repository.
- Its CPU traversal stack saturates instead of overflowing: a push onto a full stack overwrites the top entry.

## Wicked Engine: a BVH built on the GPU every frame

Wicked Engine traces its DDGI and surfel GI through hardware ray queries when the device has them, and otherwise through a BVH it builds in compute shaders. The same shader source compiles to both variants, and the engine picks one at load time.

**Build**, a full rebuild of one BVH over all scene triangles in world space, every frame that DDGI or surfel GI is on; there is no refit:

1. Gather primitives: one 64-thread dispatch per mesh subset (and per hair system and particle emitter) writes each triangle's world-space vertices, a flag word, an identity ID and a 30-bit Morton code of its bounding-box center, normalized to the scene's bounds (10 bits per axis).
2. Sort the Morton codes with their IDs: AMD's FidelityFX parallel radix sort, 4 bits per pass over all 32 bits (8 passes), 128-thread groups, dispatched indirectly from a GPU counter.
3. Build the hierarchy with Karras 2012 ("Maximizing Parallelism in the Construction of BVHs, Octrees, and k-d Trees"): one thread per internal node finds its key range and split from common prefixes. Internal nodes are 0 to N−2 with the root at 0, leaves N−1 to 2N−2. Equal codes are told apart by index.
4. Propagate bounds bottom-up: one thread per leaf walks to the root; a bit per internal node set with `InterlockedOr` lets the first child to arrive stop, so the second merges both boxes once they are ready.

**Layout:** a 32-byte node (min, left child, max, right child; a leaf stores its primitive index) and a 48-byte primitive (packed instance, subset and triangle IDs, flags, three world-space vertices). Materials and UVs are not in the BVH; a hit looks them up through the instance and mesh buffers. Buffers grow to the scene's triangle count with no headroom.

**Traversal:** closest-hit and any-hit loops with a 32-entry stack per thread (local array by default, shared memory as an option), both children pushed with no front-to-back order, and the loop stopped on overflow with the best hit so far. Slab tests on nodes and Möller-Trumbore on triangles. A triangle flagged transparent (alpha-tested or blended material) loads its full surface, textures included, and counts as a hit when `opacity − random ≥ 0`, so foliage casts stochastic shadows in the compute path. The hardware path forces primary rays opaque.

**DDGI with it:** each probe gets 4 to 512 rays per frame in steps of 4, scaled by its measured inconsistency and cut to a tenth outside the view frustum (512 for every probe on the first frame), on a spherical Fibonacci set rotated randomly each frame. A hit loads the full surface, samples one random light with a shadow ray, adds last frame's probe irradiance for more bounces, multiplies by albedo and adds emission. Radiance is clamped to the half-float range before storing, because a bright sky turned into NaN in firefly suppression.

No timings are given anywhere in the code. It is a template for dynamic triangle scenes without hardware ray tracing: every pass is a plain compute dispatch with integer atomics, which Godot's `RenderingDevice` also supports.
