# Scene and tracer

All ray tracing runs in GLSL compute shaders as hardware ray queries against an acceleration structure that the GPU builds at load. Static hit records are traced once at load and kept, so per-frame tracing is small: shadow rays for direct light and the records that moving objects can change. Tracing speed therefore matters for load time and for those two lines of the [budget](budget.md), not for the bounce passes. On the RTX 2070, ray queries run at 0.64 to 3.96 G rays/s, 5 to 8 times the software traversal they replaced (plan 004 M1).

## Contents

- [Static geometry](#static-geometry)
- [Traversal](#traversal)
- [What a hit returns](#what-a-hit-returns)
- [Moving objects](#moving-objects)
- [Storage](#storage)

## Static geometry

- **One BLAS** holds every static triangle in world space, and a TLAS holds it as its only instance. Static means the instance never moves after load; anything else is a [moving object](#moving-objects).
- **A compute pass gathers the triangles** at load: it transforms each one to world space, writes its three corners as the BLAS's vertices, and writes its attributes. The driver then builds the BLAS, preferring fast traces. Godot can neither compact nor update an acceleration structure ([docs](../docs/rendering_device.md#ray-tracing)).
- **Two geometries.** The opaque triangles form the BLAS's first geometry, flagged opaque, so the hardware never hands them to the shader. The alpha-tested ones form the second. The gather puts the opaque surfaces first, so each kind is one range of triangles, and the instance's custom index, the first alpha-tested triangle, turns the second geometry's primitive indices back into triangle indices.
- **Build cost.** The gather and the build take 2.7 to 3.3 ms for Crytek Sponza's 262,267 triangles and 54 to 86 ms for Intel Sponza's 8.8 M, once at load.
- **The engine.** Stock Godot 4.7.2 cannot trace from compute shaders. The project runs on NVIDIA's Godot fork, which carries upstream PR #122051's fixes that enable ray queries ([README](../README.md#engine)).

## Traversal

- **`trace()` is one ray query** with these options:
  - segments with `tmin` and `tmax`, since every RC ray covers one interval;
  - an any-hit mode that stops at the first accepted hit, for shadow rays and occlusion tests;
  - an alpha test: a candidate on an alpha-tested triangle is accepted where the material's alpha at its UV0 reaches the scissor, as the raster's discard does;
  - culling of the back of single-sided triangles, for primary rays, as the raster does: these rays treat every triangle as a candidate, and the shader rejects the back of single-sided ones;
  - a hit of distance, barycentrics, triangle and side, the side from the hardware's facing.
- **Checked against brute force.** Closest-hit and any-hit queries, side included, agree with a test of every triangle on all 11,134 checked rays of the Cornell box and all 21,261 of Crytek Sponza (plan 004 M1).
- **Measured rates**, G rays/s, at 1280×720 from the camera's surfaces with the scene's texel spacing (plan 004 M1):

  | Rays | Crytek Sponza, 262 K triangles | Intel Sponza, 8.8 M triangles |
  |---|---|---|
  | Primary | 1.49 to 1.50 | 1.21 to 1.22 |
  | Cascade 0 and 1 segments | 2.47 to 2.61 | 1.88 to 2.52 |
  | Cascade 2 segments | 1.41 to 1.43 | 0.64 to 0.78 |
  | Top cascade, no end | 3.93 to 3.96 | 1.75 to 1.76 |
  | Sun shadows | 2.38 to 2.40 | 1.47 |
- **Software traversal**, H-PLOC trees and tinybvh's `tiny.comp` in compute, traced 0.11 to 0.50 G rays/s on the same rays (plan 004 M1).

## What a hit returns

- **The texel it hit.** Each triangle stores its instance index and its vertices' UV2, and each instance its rectangle in the [atlas](atlas.md). The barycentrics give the hit's UV2 and with it one texel index. Because geometry and atlas are static, a static hit's texel never changes, so the record stores the texel index and never retraces.
- **Back faces.** A ray that hits the back of a single-sided triangle returns black and stops. A double-sided material gets a second atlas chart for its back side, so a thin wall lit on one side by the sun stays dark on the other ([atlas.md](atlas.md#two-sided-surfaces)).
- **Misses** return no texel; the merge decides what a miss reads ([cascades.md](cascades.md)).

## Moving objects

- **Rigid moving instances** get one BLAS per mesh, built at load like the static one, and join the static BLAS as instances of the TLAS at their current transforms. The TLAS is rebuilt every frame, since Godot has no update; with tens of instances that is a few microseconds of work.
- **Their own texels** are probes like any other, and their records are retraced every frame against the whole TLAS.
- **Static records they can change.** Each frame, for every moving object, a pass collects the probe-bins whose segments can reach its swept bounds: probes within their cascade's interval end of the box, and bins whose cone meets it. Those segments are retraced against the moving instances only, through the instance mask, with the stored static hit distance as `tmax`. A hit on a moving object replaces the record for this frame; otherwise the static record stands. This is why records keep a hit distance ([budget.md](budget.md#memory-and-load-time)).
- **Cost** is in proportion to the moving content, not the scene: the moving-object line of the budget covers 940,000 to 1,305,000 short segments at the rates measured against the static BLAS. Segments masked to the moving instances cross a much smaller structure, and M7 measures them.
- **Skinned meshes** are left out of the first version; they need a BLAS rebuild per frame, which M7 adds if the budget allows.

## Storage

- **Bytes per triangle.** The tracer keeps 232 bytes per triangle: 48 of corners, which the shaders read for normals and materials and which must live as long as the BLAS built from them, 56 of attributes (UV0 and UV2 at each corner, material and instance), and 128 of acceleration structures with the build scratch that Godot keeps beside them. Crytek Sponza takes 61 MB and Intel Sponza 2.04 GB. Nothing more is held during the build.
- **One buffer each** for corners and attributes. Godot checks no storage buffer's size and cannot bind an array of storage buffers ([docs](../docs/rendering_device.md#limits)). The RTX 2070 binds up to 4 GiB per storage buffer, 76 M triangles of attributes, while Vulkan guarantees only 128 MiB, so other GPUs may need smaller scenes.
- **The materials** are one table and one array of 512 textures with a 1×1 white stand-in in the unused slots. Godot enables no non-uniform descriptor indexing, so each subgroup samples one texture at a time ([docs](../docs/rendering_device.md#texture-arrays)).
