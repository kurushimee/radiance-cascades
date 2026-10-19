# Phreakyx/RadianceCascadeGDext: a Godot 4.7 voxel-cone 3D RC design

| | |
|---|---|
| Author | Phreakyx |
| Date | 2026-06 |
| Kind | C++ GDExtension (godot-cpp) with 28 GLSL compute shaders, run from a `CompositorEffect` |
| Link | https://github.com/Phreakyx/RadianceCascadeGDext (no license) |

The README says the code "wasn't compiled here", the submodules and binaries are missing, and many shader header comments disagree with the code. Treat it as an untested design. It is still the most complete published plan for world-space RC inside Godot's Forward+ renderer, and it shows how a `CompositorEffect` without an albedo buffer has to fake the final composite.

## Godot integration

- `RCCompositorEffect` uses `EFFECT_CALLBACK_TYPE_POST_TRANSPARENT` with `access_resolved_depth` and `needs_normal_roughness`, and reads `render_buffers/depth`, `render_buffers/color` and `forward_clustered/normal_roughness`.
- All work runs on the main device (`RenderingServer.get_rendering_device()`). An autoload adds the solver node when the `WorldEnvironment`'s compositor holds the effect.
- The first `dispatch()` scans the scene tree on the render thread (meshes, collision shapes, lights, `Texture2D.get_image()`), bakes the voxels and returns without compositing.
- Normals are decoded as `normal_roughness.xyz·2 − 1` in view space and rotated to world space; depth is linearized as `z_near / raw`. Neither is checked against the engine's encoding.
- The composite adds GI to the lit color with an albedo guessed from the color itself: `albedo = clamp((scene/lum)·clamp(lum/0.3, 0.04, 0.95), 0, 1)`, zero below luminance 0.001 (`approximate_albedo`, `shaders/rc_composite.glsl:24-31`), and the active line is `scene + irradiance·approximate_albedo(scene)·gi_intensity` (:60). The constants are hand-chosen: 0.3 is `ESTIMATED_LIGHTING`, commented as the assumed average incident level and "the scene knob", and the 0.95 cap on luminance is stricter than the comment's "a surface can't reflect >100%". `ANALYSIS.md` calls the result a "guessed albedo". Godot exposes no albedo buffer to compositor effects; the `scene_albedo` binding is declared and never read.

## Scene

- Static meshes are cut into 16 m chunks, subdivided until every edge is at most 2 m, and voxelized on the GPU. Albedo is the material color times the texture's average color.
- Five clipmap levels of 256³ voxels (0.25, 0.5, 1, 2 and 4 m), addressed toroidally (`index mod 256`). A level recenters when the player is more than 12.5% of its extent from the center; worker threads build the newly exposed shells and the render thread commits one per frame.
- Level 0 stores occupancy and lit radiance (RGBA16F, 9 mips), emission, albedo and normal, six anisotropic directional mips at 128³, and a jump-flood distance field at 128³ updated two passes per frame.
- Direct light is injected into voxels: soft shadow marches over the distance field at level 0 (up to 96 steps), occupancy marches with a "roof test" for the sun on coarse levels. After a rebake, light fades in over 10 frames.
- Moving rigid bodies are voxelized every frame into a binary grid with a decaying accumulator, `max(current, 0.95·previous)`.

## Probes and cascades

| Cascade | Directions (octahedral) | Spacing (m) | Interval (m) | Probe pool |
|---|---|---|---|---|
| 0 | 4×4 | 0.25 | 0 to 1.1 | 1,048,576 |
| 1 | 4×4 | 0.5 | 1 to 3.2 | 524,288 |
| 2 | 8×8 | 1 | 3 to 7.4 | 65,536 |
| 3 | 8×8 | 2 | 7 to 15.8 | 16,384 |
| 4 | 8×8 | 4 | 15 to 32.6 | 4,096 |

- Spacing and interval length double per cascade (`_cascade_scale = 2.0`, `src/CRadianceCascade.h:589`), while the direction table is `{4, 4, 8, 8, 8}` per side (`CRadianceCascade.cpp:1576`), so the angular branching per axis is 2 from cascade 1 to 2 and 1 elsewhere; `rc_patch_merge.glsl:73` takes the ratio as `max(oct_{c+1}/oct_c, 1)`. Each interval is extended by 10% for overlap.
- Derived: against the penumbra rule from cascade 0's 4 × 4 (directions per axis doubling as interval starts double), cascades 1 to 4 are 2×, 2×, 4× and 8× coarser per axis. The cone aperture `2/oct_c` widens to match, so the coarse cascades blur rather than alias.
- Probes exist only near visible surfaces. Cascade 0 is seeded from a half-resolution pixel grid and higher cascades from a grid up to 1080 rows tall; each sample creates the 8 cells its gather will read. Probe ids come from a free list and live in a hash (load 0.5, 64-step linear probing); ids unseen for 60 frames are freed.
- Each (probe, direction) is traced as a **cone** through the voxel mips, aperture `2/oct_c`, with steps of half the cone diameter (one to four voxels) and distance-field skips at level 0. The trace stops below 1% transmittance.
- Radiance is packed in 32 bits: a shared 5-bit exponent, three 7-bit mantissas and a 6-bit transmittance.
- Merge `rgb = own + own.a·parent`, with the parent a trilinear mix of the 8 cascade `c+1` neighbors (missing ones dropped and weights renormalized). Where the parent has 4× the directions, its 2×2 blocks are averaged first. An option re-traces only 1 in N directions per frame.

## Gather and denoise

- Half resolution: each pixel reads the 8 cascade 0 probes with trilinear weights times `step(0, f)·(0.5 + 0.5f)`, where `f` is the normal dotted with the direction to the probe, so probes behind the surface are ignored.
- `E = Σ_d (R + T·sky(d))·max(n·d, 0)·4π/16`, with the sky gated by elevation, `sky_color·smoothstep(−0.2, 0.3, d.y)` (`rc_patch_gather.glsl:126`).
- Four à-trous passes (steps 1, 2, 4, 8, B-spline 5×5) with depth, normal (power 8) and luminance weights; then a bilateral upsample with an edge fallback (`rc_irradiance_upsample.glsl:28-29, 70-76`): `edge = 1 − smoothstep(0.20, 0.60, wsum)` of the bilateral weight sum, and where `edge > 0.001` and a full-resolution cascade 0 gather finds a probe, the result is `mix(bilateral, gather, edge)`. The gather replaces the bilateral result below a weight sum of 0.2 and is unused above 0.6.

## Header comments against the code

| File | Header says | Code does |
|---|---|---|
| `rc_patch_merge.glsl:8` | direction table `{4, 4, 8, 8, 16}` | `{4, 4, 8, 8, 8}` (as `ANALYSIS.md` 2.1 says) |
| `rc_patch_trace.glsl:8-9` | walk the whole hash region and skip empty slots; indirect size `bucket_cap·dirs` | walks the compact live list with a guard on `alloc_count`; `rc_patch_indirect.glsl:30` sizes it `alloc_count·dirs` |
| `rc_patch_gather.glsl:1-12` | trilinear blend of 8 cascade 0 probes; sky weighted by residual transparency | weights also multiplied by the facing term (`:105-108`); sky also gated by elevation (`:126`) |
| `rc_composite.glsl:7, 34-36` | albedo read "dummy for now"; GI "today additive" | albedo binding never read; GI multiplied by the guessed albedo (the additive form is commented out at `:40`, and `apply_gi` is not on the active path) |
| `rc_composite.glsl:30` | cap at 100% reflectance | luminance capped at 0.95 |
| `rc_clip_inject.glsl:6-7` | no SDF march, visibility 1 | occupancy march `clip_vis` (`:77`) |
| `rc_patch_reduce.glsl:3-6` | identical to the in-merge `r²` average | the merge's `r` is 1 or 2; the reduce path was not checked |

The headers of `rc_patch_lookup.glsl`, `rc_irradiance_atrous.glsl` and `rc_irradiance_upsample.glsl`, and the spacing and interval schedule in `ANALYSIS.md`, match the code.
