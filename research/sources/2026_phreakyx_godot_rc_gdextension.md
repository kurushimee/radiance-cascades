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
- The composite adds GI to the lit color with an albedo guessed from the color itself: `albedo = clamp((scene/lum)·clamp(lum/0.3, 0.04, 0.95), 0, 1)`, zero below luminance 0.001. Godot exposes no albedo buffer to compositor effects.

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

- Spacing doubles per cascade while directions grow ×4 only every second cascade, so `l = 2` with a mixed branching factor. Each interval is extended by 10% for overlap.
- Probes exist only near visible surfaces. Cascade 0 is seeded from a half-resolution pixel grid and higher cascades from a grid up to 1080 rows tall; each sample creates the 8 cells its gather will read. Probe ids come from a free list and live in a hash (load 0.5, 64-step linear probing); ids unseen for 60 frames are freed.
- Each (probe, direction) is traced as a **cone** through the voxel mips, aperture `2/oct_c`, with steps of half the cone diameter (one to four voxels) and distance-field skips at level 0. The trace stops below 1% transmittance.
- Radiance is packed in 32 bits: a shared 5-bit exponent, three 7-bit mantissas and a 6-bit transmittance.
- Merge `rgb = own + own.a·parent`, with the parent a trilinear mix of the 8 cascade `c+1` neighbors (missing ones dropped and weights renormalized). Where the parent has 4× the directions, its 2×2 blocks are averaged first. An option re-traces only 1 in N directions per frame.

## Gather and denoise

- Half resolution: each pixel reads the 8 cascade 0 probes with trilinear weights times `step(0, f)·(0.5 + 0.5f)`, where `f` is the normal dotted with the direction to the probe, so probes behind the surface are ignored.
- `E = Σ_d (R + T·sky(d))·max(n·d, 0)·4π/16`.
- Four à-trous passes (steps 1, 2, 4, 8, B-spline 5×5) with depth, normal (power 8) and luminance weights; then a bilateral upsample that falls back to a direct cascade 0 gather where the bilateral weights sum below 0.2 to 0.6.
