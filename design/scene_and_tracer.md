# Scene and tracer

All ray tracing runs in GLSL compute shaders against a BVH that the GPU builds at load. Static hit records are traced once at load and kept, so per-frame tracing is small: shadow rays for direct light and the records that moving objects can change. Tracing speed therefore matters for load time and for those two lines of the [budget](budget.md), not for the bounce passes.

## Contents

- [Static geometry](#static-geometry)
- [Traversal](#traversal)
- [What a hit returns](#what-a-hit-returns)
- [Moving objects](#moving-objects)
- [Storage](#storage)
- [Open questions](#open-questions)

## Static geometry

- **One world-space BVH** over every static triangle, built on the GPU at load. Static means the instance never moves after load; anything else is a [moving object](#moving-objects).
- **The builder is LBVH**: Morton codes of the triangle centres, a radix sort of the 32-bit codes (four 8-bit passes), Karras's parallel hierarchy, and a bottom-up pass that fits boxes with a 32-bit atomic counter per node. Every step uses only 32-bit integer atomics, which is all Godot's Vulkan driver enables ([docs](../docs/rendering_device.md)).
- **Why not a better tree.** Higher-quality builds trace faster: on one AMD GPU an SBVH traced secondary rays 1.86 times as fast as LBVH, and H-PLOC's trees path-trace within 5 to 17% of the best builder's time while building within 15% of LBVH's ([research](../research/sources/2026_gpu_bvh_builders_and_wide_traversal.md#builders)). Here the frame traces only about 700,000 rays, so that speed is worth at most a few tenths of a millisecond. H-PLOC is the upgrade if plan 004 M1 or M7 finds the frame's rays too slow.
- **Build cost.** LBVH ran at about 2.9 ms per million triangles on an RX 6800 XT; a 10.8 M-triangle scene would take on the order of 30 to 100 ms on an RTX 2070, once (M1 measures it).

## Traversal

- **The kernel starts from tinybvh's `tiny.comp`** (MIT licence, read at commit c9be310): GLSL 4.60, one thread per ray, the 2-wide `BVH_GPU` layout with 64-byte nodes and 48-byte triangles, and a stack of 32 entries per thread in shared memory ([research](../research/sources/2026_compute_bvh_libraries.md)). It is the lowest-risk start among the tinybvh kernels for Vulkan compute.
- **Binary nodes stay.** Uncompressed 4- and 8-wide nodes traced secondary and shadow rays no faster than binary ones (0.86 to 1.04 times), and no GPU builder writes the compressed 8-wide CWBVH layout ([research](../research/sources/2026_gpu_bvh_builders_and_wide_traversal.md#wide-and-compressed-nodes)).
- **Changes to the kernel:**
  - segments with `tmin` and `tmax`, since every RC ray covers one interval;
  - an any-hit mode that stops at the first opaque hit, for shadow rays and occlusion tests;
  - an alpha test for alpha-tested triangles, reading a per-material mask through the triangle's UV0;
  - a hit result of triangle index and barycentrics;
  - a stack guard. The kernel drops the far child silently when the stack is full, which would turn into missing occluders and leaks. A debug build counts overflows, and the stack grows if any occur on the test scenes.
- **Godot has no ray queries**, so hardware ray tracing is not an option: `has_feature(SUPPORTS_RAY_QUERY)` is always false and compute shaders cannot trace ([docs](../docs/rendering_device.md)).

## What a hit returns

- **The texel it hit.** Each triangle stores its instance index and its vertices' UV2, and each instance its rectangle in the [atlas](atlas.md). The barycentrics give the hit's UV2 and with it one texel index. Because geometry and atlas are static, a static hit's texel never changes, so the record stores the texel index and never retraces.
- **Back faces.** A ray that hits the back of a single-sided triangle returns black and stops. A double-sided material gets a second atlas chart for its back side, so a thin wall lit on one side by the sun stays dark on the other ([atlas.md](atlas.md#two-sided-surfaces)).
- **Misses** return no texel; the merge decides what a miss reads ([cascades.md](cascades.md)).

## Moving objects

- **Rigid moving instances** get one BLAS per mesh, built at load like the static BVH, and a TLAS over their current transforms, rebuilt every frame. With tens of moving instances the TLAS build is a few microseconds of work.
- **Their own texels** are probes like any other, and their records are retraced every frame against the static BVH and the TLAS.
- **Static records they can change.** Each frame, for every moving object, a pass collects the probe-bins whose segments can reach its swept bounds: probes within their cascade's interval end of the box, and bins whose cone meets it. Those segments are retraced against the TLAS only, with the stored static hit distance as `tmax`. A hit on a moving object replaces the record for this frame; otherwise the static record stands. This is why records keep a hit distance ([budget.md](budget.md#memory-and-load-time)).
- **Cost** is in proportion to the moving content, not the scene: the moving-object line of the budget covers 500,000 retraced segments.
- **Skinned meshes** are left out of the first version; they need a BLAS refit per frame, which M7 adds if the budget allows.

## Storage

- **Buffer size.** Vulkan guarantees only 128 MiB per storage buffer, and no RenderingDevice limit reports more ([docs](../docs/rendering_device.md)). At 48 bytes a triangle buffer holds 2.8 M triangles and a node buffer 2.1 M nodes. Larger scenes split triangles and nodes into fixed chunks of 128 MiB, bound as separate bindings and selected by the high bits of the index.
- **One vertex copy.** The BVH build, the atlas capture and the hit lookup read the same vertex, index and UV2 buffers, uploaded once at load.

## Open questions

- Software traversal rate under RenderingDevice on the RTX 2070: no measurement exists; the budget assumes 1 G rays/s (M1).
- The stack size tinybvh's comments give, 8 KB per 8×8 group, disagrees with the declared arrays, which total 4 KB ([research](../research/sources/2026_compute_bvh_libraries.md)). M1 reads the source before sizing the stack.
- Whether chunked buffers cost measurable speed through their bindings (M1).
