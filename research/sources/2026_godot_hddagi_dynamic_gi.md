# Godot HDDAGI and its screen-probe extension (pull requests, 2023 to 2026)

| | |
|---|---|
| HDDAGI | https://github.com/godotengine/godot/pull/86267 (reduz), open draft since 2023-12, branch head 2024-07-11; 77 files, +8145/−6151; it replaced #86007, closed unmerged |
| Rebase | https://github.com/godotengine/godot/pull/119869 (OrangeeZ), open since 2026-05 |
| Screen probes | https://github.com/godotengine/godot/pull/122999 (maidopi-usagi), draft since 2026-08 |
| Code read | `gi.cpp`, `gi.h` and the `hddagi_*.glsl` shaders at the #86267 head; the screen-probe, SVGF, irradiance-cache and Hi-Z shaders at the #122999 head |

HDDAGI (hierarchical DDA GI) is reduz's replacement for SDFGI: voxel cascades traced with an integer hierarchical DDA instead of a distance field, feeding DDGI-like world probes. None of the three pull requests is merged, and Godot 4.7.2 still ships SDFGI. They matter as working `RenderingDevice` code for a voxel tracer, probe upkeep and screen probes inside Godot's own renderer, and as a record of the artifacts a world-probe design hits there.

## Contents

- [Status](#status)
- [Voxel cascades](#voxel-cascades)
- [Hierarchical DDA](#hierarchical-dda)
- [Lighting the voxels](#lighting-the-voxels)
- [Probes](#probes)
- [Occlusion and leaks](#occlusion-and-leaks)
- [Reaching the pixels](#reaching-the-pixels)
- [Cost](#cost)
- [Screen probes in #122999](#screen-probes-in-122999)

## Status

- #86267 was reviewed in 2024. clayjohn measured a small overall gain and a large drop in probe cost, and the rendering meeting agreed to rename it `dynamic_gi`. The thread was locked in 2024-12 with the timeline depending on reduz's time. A null dereference in `process_gi` (reading `hddagi` members when only VoxelGI exists) and leaked RIDs were still in the head.
- Left for after merging: high-density probes and dynamic objects. Only static meshes are voxelized; dynamic objects receive GI but add nothing.
- #119869 rebases it onto current Godot with reviewers' changes. Open problems: wrong probe occlusion on D3D12, compute-pipeline error spam on RADV and macOS, brightness jumps at 50% and 70% cascade height, and 13 leaked "HDDAGI Voxel Disocclusion" textures.
- No maintainer has stated a merge decision for either rebase. Calinou suggested an optional screen-space GI pass as the best fix for leaks.

## Voxel cascades

- Each cascade is 128 cells across in x and z; the default "16x8x16" format halves y to 64. The other formats keep 128 in y and scale world y by 1, 1.5 or 2 before indexing. Up to 8 cascades; cell size doubles per cascade from the minimum cell size (default 0.2).
- Storage per cascade, stacked along y by cascade index in shared textures:
  - a 64-bit occupancy mask per 4³ block (`R32G32_UINT`, bit `z·16 + y·4 + x`);
  - one flag per 8³ region (`R8_UINT`) and a version counter per region (`R16_UINT`) that invalidates cached probe hits;
  - light per cell as RGBE (`R32_UINT` viewed as `E5B9G9R9`), plus a 26-bit mask of which neighbor directions can see the cell;
  - per-face albedo and emission at half resolution, and 6 axis-facing bits plus 26 normal-bin bits per cell.
- Only empty cells next to a solid face are lit. They go in a process list of 16-byte entries: position (7 bits per axis), RGB565 albedo with an 8+8 octahedral normal, RGBE emission, and 8 four-bit probe occlusion weights. Capacity is `128·64·128·solid_cell_ratio` (default 0.5); extra entries are dropped.
- Cascades follow the camera in steps of one 8-cell region and never copy data: addresses wrap with a mask, and only the newly uncovered slabs are revoxelized. A move of a whole cascade, or a dirty volume over half the cascade, rebuilds it. SDFGI regenerated its whole field on camera motion, which is where the claimed order-of-magnitude faster updates come from.
- Voxelization runs in the forward scene shader's `MODE_RENDER_SDF` block (`scene_forward_clustered.glsl:2224` at the #86267 head). It takes the geometric normal from `dFdx`/`dFdy` of the position, maps the fragment to a cell (`sdf_offset + local_pos·sdf_size`), and sets normal bits: bits 0 to 5 for the axis directions with `dot > 0.001`, bits 6 to 31 for the 26 bin directions with `dot > 0.7`. It ORs them atomically into the `r32ui` image `geom_normal_bits` (set 1, binding 27) and also writes albedo per axis sign (6 layers) and RGBE emission at half resolution (`igrid_pos >> 1`). The comments say "solid bits" and a "Compute solid bits" heading has no code under it: solidity is derived later, when `hddagi_preprocess.glsl` counts any nonzero normal word as solid and sets the region bits. The MoltenVK branch does a non-atomic load and store with `bit_ofs`, a name defined in neither the shader nor its include, so that branch would not compile.

## Hierarchical DDA

The tracer walks three levels, 8³ regions, 4³ blocks and single cells, in integer fixed point (8 fractional bits, so one cell is 256 units). It descends when the current cell at a level is occupied and climbs back up when the position leaves the parent, with no distance-based level of detail:

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

- When a ray leaves a cascade it converts to world space and continues in the next coarser cascade; it never goes finer. The loop has no iteration cap and ends after the last cascade.
- A hit returns the cell, the crossed face and the cascade. Radiance is the light texel of the empty cell on the hit face's side.
- Shadow rays for direct light use the same walk with a distance limit and 10 fractional bits.
- Cost scales with the amount of geometry in the level but not its triangle count (reduz).

## Lighting the voxels

- Static lights are injected once per region update; dynamic lights every frame or every 2, 4, 8 or 16 frames, spread over the process list. Up to 1024 static and 128 dynamic lights per cascade.
- Shadows are HDDA shadow rays from each cell toward each light, not shadow maps.
- Bounce: each lit cell adds `albedo · bounce_feedback` times the irradiance of its 8 surrounding probes from the previous update, weighted by its stored occlusion nibbles.
- The sky is never injected; probe rays that miss read the sky cubemap at mip 2 or the clear color.

## Probes

- One probe per 8 cells, so a default cascade has 17 × 9 × 17 probes. Each probe is a 5×5 octahedral tile (7×7 with a 1-texel border), one thread and one ray per texel, so 25 rays per probe update, jittered per frame.
- Rays start at the probe and are pushed forward by `probe_bias`. Each result is splatted bilinearly into up to 4 octahedral texels with 14-bit fixed-point integer atomics.
- A hit cache stores the hit cell, cascade and axis per texel and history slot, so unchanged hits are reused. An entry is dropped when its region's version changes or the cascade moved along its axis.
- History is a moving average over `frames_to_converge` slots, a project setting. In #119869 its default is 6; Calinou found 32 removes most flicker and suggested 18 to 24 as a middle ground.
- Diffuse comes from a fixed weighted sum of neighboring octahedral texels; specular reads the averaged texel directly.
- Scheduling: probes near geometry update when their region is visible to the camera; probes whose region was revoxelized update within 1, 2, 4 or 8 frames; others update every `inactive_update_frames`, staggered by the parity of their world position.
- Newly uncovered probes are seeded from the next coarser cascade with occlusion-weighted trilinear weights; the top cascade starts at zero.
- An optional filter averages each visible, near-geometry probe with its 6 axis neighbors at weight `0.7 · visibility`.

## Occlusion and leaks

- Occlusion between cells and their 8 surrounding probes is found by propagating a wavefront from each probe corner across its 8³ block (22 steps), with solid-cell bias and back-face darkening, stored as 4-bit weights.
- reduz's account of the remaining leaks: walls one voxel thick are sealed in the voxels, but a normal-based bias that moves lookups out of solid cells does not clear the outside probe's reach at corners. reduz's proposed fixes were thicker walls, denser probes, or a depth- and normal-aware blur sized to one voxel on screen.
- In #122999 the leaks at the default 0.2 cell size were gone at 0.03 with 5 cascades, or with the cascades pushed 0.3 forward of the camera; the cause given is voxels jumping to the third cascade at short range.
- Other reported problems: dark splotches that need an occlusion bias, artifacts on normal-mapped terrain and curved or overlapping geometry ("the main problem with DDGI", reduz), visible cascade shifts while moving, light popping, and blocky reflections.

## Reaching the pixels

`process_gi` runs one compute dispatch per view at internal resolution, or half resolution (the default in #119869), reading depth and normal-roughness and writing RGBE ambient and reflection images plus a blend image. These are the engine's own GI buffers, which a script cannot write ([indirect diffuse paths](2026_godot_indirect_diffuse_paths.md)). Reflections get an optional separable bilateral filter, radius 12 (6 at half resolution), weighted by depth, `pow(n·n', 4)` and roughness, skipped at roughness 0.3 and above.

## Cost

- Static camera on a GeForce GTX 1650: SDFGI 2.43 ms against HDDAGI 0.93 ms for light update and probe tracing (#86267).
- The official GI demo at 3840×2160 ran at 120 FPS on an RTX 3080 with the #122999 changes, untuned.
- No memory figures are given. The texture formulas are in `gi.cpp`.

## Screen probes in #122999

The draft adds Lumen-style screen probes that trace through Hi-Z first and then HDDA. Its author calls it a heuristic mix inspired by Kajiya and Lumen, too large to merge as one change.

- **Placement:** one probe per tile of `probe_size` GI texels, at the valid pixel nearest the tile center, optionally jittered by an 8-sample Hammersley sequence per frame. Each probe stores its screen position, depth and packed normal with a dynamic-object flag.
- **Stochastic Integrated mode:** 1 to 8 cosine-weighted rays per probe per frame, optionally guided by 8 bins (2 radial × 4 azimuthal) weighted by `sqrt(luminance)` of the nearest HDDAGI probe and mixed 50/50 with uniform. Pixels gather 3×3 probes weighted by `pow(n·n', 6)`, depth and distance. Better at detail and corners.
- **Directional Gather mode:** 64 rays per probe per frame into an 8×8 octahedral tile, one per texel with R2 jitter, radiance clamped to 10. With guiding on, a valid history and a static receiver, directions are sorted by a pdf from the BRDF and last frame's radiance and grouped as one high-pdf direction with three low-pdf ones. Where the low ones fall under 0.1 and the high one does not, the high direction splits into four 16×16 children traced with the low ones' ray slots, and the low ones reuse last frame's radiance. One frame in four skips the split so the low directions refresh. Pixels gather 2×2 probes bilinearly with a plane-distance test and read the per-normal irradiance table (the 64 directions summed with `max(n·ω, 0)` and scaled by `4/64`). It runs 20 to 40% faster than Stochastic and handles the bright small sun better.
- **Adaptive probes:** each tile has 8 jittered candidate positions; a candidate becomes a probe when the base probes cover it with weight under 0.01, and is retired once coverage rises above 0.06. Up to 8 per tile, from a pool of half the base probe count, which the author says fills up easily.
- **History:** per direction, `mix(previous, current, w)` with `w = 1/(age + 1)`, age capped at 7 (a steady 1/8), and 0.5 for dynamic receivers. Reprojection uses unjittered projections, and velocity for dynamic receivers. A spatial pass blends each probe with its 4 neighbors by distance, plane and endpoint angle.
- **SVGF:** temporal accumulation with depth, normal and plane tests, then an à-trous filter driven by luminance variance. NVIDIA NRD was removed.
- **Detail trace:** before HDDA, a Hi-Z march (2×2 max-depth pyramid, 48, 32 or 16 iterations) out to 2 units for diffuse and 50 for specular. A hit reads the lit screen color, so visible dynamic objects occlude and bounce light. It costs extra on low-end GPUs; probe jitter alone handles corners without it.
- **Irradiance cache:** first-order `[1, n]` moments per entry with a 16-sample history. It flickers and is left off.
- **Problems:** noisy and laggy screen-probe reflections, unstable light in hard-to-sample spots, and pixelated dark areas near corners and thin plates from over-occluding coarse voxels.
- Dynamic objects were prototyped in a fork with an object-level voxel cache at about 20% overhead; they flickered and leaked light from distant dynamic emitters. In maidopi-usagi's words (#122999, 2026-09-08), rigid mesh instances with an "object level cache" toggle keep their own voxel cache, traced between the screen trace and the global trace, with extra storage. Their `dynamic_gi_hw` branch (34 commits ahead of master) has the commits "Add object-local HDDAGI caches for rigid geometry" and "Improve rigid HDDAGI cache controls and lighting stability" and `hddagi_rigid*` files; that it is the measured prototype is inferred from names and dates. David-Zuloyan reports dynamic-object support on #119869 as "heavy", with no figure (fork branches `hddagi-4.7` and `pr-119869`).
