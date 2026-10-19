# AMD FidelityFX Brixelizer and Brixelizer GI (2024)

| | |
|---|---|
| Talk | AMD, GDC 2024 (slides, 74 pages) |
| Pages | https://gpuopen.com/fidelityfx-brixelizer/ and https://gpuopen.com/learn/introducing-amd-fidelityfx-brixelizer/ |
| Code | https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK at tag `v1.1.4` (MIT): C++ host, HLSL and Vulkan GLSL passes, and the docs `docs/techniques/brixelizer.md` and `brixelizer-gi.md`. Later tags and `main` no longer contain it. |

Brixelizer builds a sparse distance field of the scene on the GPU and traces rays through it in compute shaders, with no hardware ray tracing. Brixelizer GI is a simplified GI-1.0 on top of it. For RC the value is the tracer: an open, compute-only structure with GLSL source that turns triangles into a traceable field every frame, plus a radiance cache that solves the missing-material problem every SDF tracer has.

## Structure

- Cascades are clipmaps of 64³ voxels around a point, usually the camera, up to 24 of them. Extent per axis is `64 · voxel_size`.
- A voxel that touches geometry gets a brick: 8³ texels of distance, stored in one shared 512³ `R8_UNORM` atlas (128 MiB, 2^18 brick slots addressed by an 18-bit brick ID). Empty voxels point to no brick.
- Each cascade has a 64³ brick map (1 MiB) and a 3-level AABB tree (17,944 bytes): one bit-packed AABB per 4³ voxels at the bottom, 64 float AABBs above them, and a root. A bottom value of `0x7fff` marks an empty node.
- Texels hold distance in voxel units, only near surfaces: anything beyond about 4/7 of a voxel is left at the cleared value 1. A brick with no texel under 1/8 is freed. Brick texels are spaced 1/7 voxel apart so the outer texels sit on the voxel faces.
- Instances are static (kept) or dynamic (resubmitted every frame), up to 2^16.

## Building

Per update, for one cascade:

1. Scroll: when the center moves, the band of voxels that wrapped around is unset.
2. Voxelize: each triangle adds a reference to every voxel its bounds touch. Triangles smaller than 0.1 voxel are stored as a centroid (12 bytes), others as a vertex and two compressed edges (24 bytes).
3. Allocate a brick from the free list for each voxel with references, up to a per-update cap.
4. Emit the SDF: each brick texel takes the minimum exact distance to its triangles.
5. Compress into the atlas, recording each brick's tight AABB.
6. Build the cascade's AABB tree; static and dynamic cascades are merged texel by texel into a combined one.
7. At the end of the frame, an Eikonal pass fills each new brick's unwritten texels: 512 threads per brick, an 8³ shared-memory copy, three sweeps with steps of 8, 4, 2 and 1 texels.

- The simple API updates one cascade per frame in the pattern 0 1 0 2 0 1 0 3, so cascade 0 refreshes every second frame and cascade 1 every fourth.
- Static cascades only build voxels that are still uninitialized, so they update incrementally. Dynamic cascades are cleared and rebuilt from scratch each time they come up.
- Running out of brick, triangle or reference budget marks the voxel failed; what happens next is not documented.
- Update cost grows with the number of triangles per cascade. Doubling the voxel size from 0.3 to 0.6 cut cost sharply; 0.6 to 0.9 helped little, since each voxel then covers more triangles.

## Tracing

`FfxBrixelizerTraverseRaw` in the shared GPU header (used by both HLSL and GLSL):

1. Loop over cascades from the finest; skip a cascade that is disabled or does not contain the ray's current point.
2. Within a cascade, walk the AABB tree in 16-voxel and then 4-voxel steps, skipping empty nodes, with a budget of 32 iterations per cascade.
3. In a non-empty 4³ block, step voxel by voxel. A voxel whose brick is uninitialized aborts the cascade.
4. For a voxel with a brick, clip the ray to the brick's AABB and sphere trace at most 8 steps inside it. A hit is a sample under twice the epsilon; leaving the brick by more than 0.001 continues the walk.
5. On running out of iterations, back up one voxel and continue in the next coarser cascade.

- The hit returns only distance, brick ID and the position inside the brick. The normal comes from three one-sided differences toward the brick center.
- The SDF surface sits slightly off the triangles, so rays need a push-off along the normal (scaled by voxel size and camera distance in the GI) and a `t_min` to avoid self-hits.
- Against DXR on an RX 7900 XTX: faster for shadows in Flying World, even in Sponza, faster for short AO rays at voxel size 3.0, and much slower for long AO rays at voxel size 0.2 (graphs only, no numbers). Long and divergent rays cost the most.

## Brixelizer GI

1. **Radiance cache:** a 256³ `R11G11B10` atlas of 4³ blocks keyed by brick. Each frame, a random pixel per 4×4 tile reprojects last frame's lit image to its world position and writes it into the brick there. The SDF stores no materials, so this is the only way hits get color, and a surface must have been on screen to bounce light.
2. **Screen probes:** one per 8×8 tile with 8×8 octahedral directions. Placement tries up to 8 Hammersley-jittered positions for a valid depth. Probes are reprojected from last frame by picking the best-matching old probe per tile; tiles that fail trace one ray per probe texel, reading the radiance cache at hits and the environment map on misses.
3. **Irradiance cache:** probes are projected to SH2 and blended into a world SH probe per brick; SH spreads to neighboring bricks one cascade per frame.
4. **Resolve:** blend screen-probe SH projected on the pixel normal with world SH, then the reprojected history; a bilateral blur whose radius grows as samples drop; split-sum composite.
5. **Specular:** a quarter-resolution pre-trace stores brick IDs, then full resolution resumes inside those bricks, starting two cascades coarser than diffuse.

Feeding the composited output back as the next frame's input adds bounces. Default internal resolution is half the output (0.75× and native optional).

## Cost

- GI: about 2 ms at 4K on an RX 7900 XTX, 2.2 ms at 4K on an RTX 4080, 1.7 ms at 1080p on an RX 7600 XT. These figures share slide 54 of the GDC 2024 deck with the statement that the default quality setting works at half resolution internally, with 0.75× and native as options, so they are most likely at 0.5× (inference); the GI page adds that the specular pre-trace runs at quarter resolution. Slide 55 lists the GI's memory as about 110, 150 and 200 MB in columns for 0.5×, 0.75× and 1× scale, with the row label lost in extraction. Neither the GI page nor the deck compares Brixelizer GI with DXR GI; the deck presents it as a fallback for hardware without ray tracing and compares it with a path tracer in images only.
- Memory: 128 MiB atlas, 1 MiB per cascade, 16 MB of internal buffers, plus scratch. The GI's fixed buffers (radiance cache 64 MiB, two SH buffers of 18 MiB, state 4 MiB) come to about 104 MiB before screen-sized data; the slides give the GI's total as roughly 110 to 500 MB depending on resolution and scale.

## Overflow

Nothing read documents what happens when bricks run out. Storage is fixed at initialization (`FFX_BRIXELIZER_MAX_BRICKS_X8 · sizeof(FfxUInt32x2) · 9` for persistent GI resources, an SDF atlas of about 128 MB, 1 MB per cascade); brick IDs range from 0 to `2^18 − 1`; per-update limits (`maxBricksPerUpdate`, `maxBricksPerBake`, `triangleSwapSize`, `maxReferences`) can be tuned; counters report attempted and successful brick allocations per frame and failed voxel allocations (`g_scratch_voxel_allocation_fail_counter`); and `FfxBrixelizerScanReferences` allocates bricks for referenced voxels with no overflow path described. The shader source was not found in the FidelityFX SDK tree on `main`.

## Problems

- Light from surfaces never seen on screen is missing until they come into view.
- The field is approximate: shadows and AO differ from triangle tracing, hard shadows soften as voxels grow, and coarse fields self-occlude without bias.
- Alpha-tested foliage cards are voxelized as solid quads, so grass over-darkens. Leaving them out removes leaf shadowing and leaves gaps in the caches that flicker. AMD calls its foliage handling naive.
- Small-scale detail is lost; AMD suggests SSAO or SSGI on top.
