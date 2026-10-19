# Interactive Indirect Illumination Using Voxel Cone Tracing

| | |
|---|---|
| Author | Cyril Crassin, Fabrice Neyret, Miguel Sainz, Simon Green, Elmar Eisemann |
| Date | 2011, Pacific Graphics (Computer Graphics Forum 30(7)) |
| Kind | Paper (accepted author version) |
| Link | https://research.nvidia.com/sites/default/files/publications/GIVoxels-pg2011-authors.pdf ; DOI https://onlinelibrary.wiley.com/doi/10.1111/j.1467-8659.2011.02063.x |

Voxel cone tracing (VCT) voxelizes the scene into a sparse octree, prefilters light and occlusion up the mip levels, and gathers indirect light along a few wide cones per pixel by sampling the level whose voxel size matches the cone's radius. RC shares its core idea, that far light needs less spatial detail, but VCT applies it inside each cone by blurring the scene, while RC keeps exact rays and coarsens probe spacing instead. Its thin-wall leak and the six-direction anisotropic voxels it introduced are the precedent cited for directional opacity in mipmapped RC volumes ([sparse 3D RC](2026_sparse_and_3d_rc.md), [volumetric RC](2026_volumetric_rc.md)). Kung's thesis compares RC with VCT directly ([2025_kung_rc_vs_voxel_cone_tracing_thesis.md](2025_kung_rc_vs_voxel_cone_tracing_thesis.md)).

Section numbers refer to the PDF. Some formulas lost symbols in text extraction; those are marked.

## Structure (sec. 4)

- A sparse voxel octree with pointer-based nodes grouped in 2×2×2 tiles, so one pointer addresses 8 children (sec. 4.1).
- Each node has a 3×3×3 brick with voxel centers at node corners. This vertex-centered layout needs less than half the memory of bricks with a one-voxel border for the same sampling precision. Neighbour pointers are stored.
- Construction (sec. 4.2.1): the mesh is rasterized three times along the main axes at 512² with depth testing off, one fragment thread per potential leaf. Subdivision uses atomic counters and per-node mutexes; threads that lose a race are deferred to a later pass. It needs `NV_shader_buffer_load` and `NV_shader_buffer_store`.
- Dynamic objects (sec. 4.2.2) are rasterized each frame into a separate part of the buffer, leaving static data untouched.
- Mipmapping (sec. 4.2.3) takes `n − 1` passes for `n` levels with a 3³ Gaussian kernel (weights 1/16, 1/8, 1/4). Each brick voxel is weighted by the inverse of its multiplicity, since brick borders are shared. Filtering runs in three passes over octants, and an add-and-copy pass per axis fixes the duplicated border voxels (Fig. 9, sec. 8.2).
- A mip pyramid of leaf indices lets threads that share an ancestor stop early, more than a 2× speedup (sec. 8.2).

## Voxel contents (sec. 4.3, 9)

- Directional distributions are stored as isotropic Gaussian lobes, with the lobe width encoded in the length of the mean direction in a Toksvig-style relation; sec. 6 gives `σ² = (1 − |N|)/|N|` for the normal lobe.
- Occlusion is stored as one average visibility value, not as density. Colour and normal are premultiplied by opacity.
- Anisotropic voxels (sec. 9) keep six values, one per major axis direction, each from a depth integration averaged over four directional values. A lookup interpolates the three of the six directions closest to the view direction. This fixes the leak where two walls of different colours blend into one voxel. Memory rises 1.5×, since directional values are stored only above the finest level.

## Cone tracing (sec. 5, 6, 8)

- A cone steps along its axis and samples the mip level matching its radius with quadrilinear interpolation.
- Accumulation is front-to-back emission-absorption (Max 1995): `c := c + (1 − α)·α₂·c₂` and `α := α + (1 − α)·α₂`.
- A step `d` that differs from the voxel size gets an opacity correction with exponent `d/d_voxel` (formula partly garbled in extraction).
- Ambient occlusion: `A(p) = (1/N)·Σ V_c(p, ω_i)` over `N` cones, with falloff `f(r) = 1/(1 + r)` on occlusion.
- Indirect diffuse uses about five wide cones, and indirect specular one narrow cone whose aperture follows the specular exponent (sec. 8.1).
- Light injection renders a light-view map with one photon per pixel and splats it into the octree. Splatting needs 16-bit normalized textures because atomic add works only on integer types, and the duplicated brick voxels need three axis passes to resolve collisions (sec. 8.2).

## Results (sec. 10)

GTX 480 with a Core 2 Duo E6850; Sponza (280K triangles), 9-level octree (512³ virtual resolution), 512² screen unless stated.

- 30 FPS with no specular cone and 20 FPS with one; 11.4 FPS at 1024×768 with three diffuse cones and one specular cone.
- About 1024 MB of video memory, which the paper counts among its limitations and says is usually less than [KD10] needs for comparable quality, mostly spent on indirect specular; out-of-core caching is future work.
- Other limitations: light leaks from the discrete geometry and irradiance resolution, and wide AO cones overestimate far occlusion (sec. 10-11).
- A dynamic hand of 16K triangles updates in about 5.5 ms per frame. The static octree takes about 280 ms to build, and light injection and filtering about 16 ms, run only when the light moves.
- Table 1 (three diffuse cones and one 10° specular cone) extracts as 1.0, 2.0, 7.8, 14.2, 8.0 and 22.0 ms for rasterization, direct, indirect diffuse, direct plus diffuse, indirect specular and total. The combined direct-plus-diffuse pass and the specular pass give 22.2 ms, close to the printed total, while the three separate figures sum to 10.8 ms, so the separate columns appear to be measured apart from the combined pass (derived; the column mapping stays uncertain).
- The Fig. 1 caption gives 25 to 70 FPS on a GTX 480 with two bounces.
- Table 2 (AO with three cones at 512²) by cone aperture: 10° 16.6 ms, 20° 9.0 ms, 30° 6.5 ms, 60° 3.9 ms.
- Against light propagation volumes (Fig. 12): 32 ms against 37 ms, closer to the Mental Ray reference (14 min 12 s) and with less leaking.
