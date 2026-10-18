# Screen-space 3D radiance cascades

Screen-space RC puts the probes on the depth buffer: a 2D grid of probes in screen space, each at the world position of its pixel, with full 3D directions. This is the "surface" row of the memory table in [core_theory.md](core_theory.md). With directions ×4 and probe spacing ×2 per cascade, every cascade holds about the same number of texels, so memory and cost grow linearly with the cascade count. Path of Exile 2 shipped this way. World-space designs are in [3d_world_space.md](3d_world_space.md).

## Two families

- **Screen-space tracing** (PoE2): rays march the depth buffer. Cheap and constant in cost, but blind to anything off screen or hidden behind the front surface.
- **Screen probes, world intervals** (SPWI): probes stay on the depth buffer, but rays are traced through a world-space scene (hardware ray tracing, a BVH, an SDF, or voxels), so off-screen and hidden geometry and lights count. Sannikov notes the remaining limit: radiance exists only on the depth-buffer surface, so it cannot light volumes ([discussions](../sources/2026_rc_discussions.md)). Light through transparent objects needs extra work in both families.

The paper's interval-extension trick (doubling an interval by reading the cascade at a shifted position) needs a regular grid and does not work for screen probes, which each sit at their own depth ([paper](../sources/2023_sannikov_radiance_cascades_paper.md)).

## Path of Exile 2

- Probes and data are screen-space. Each thread marches 4 rays at once and stores occlusion as a 128-bit mask per cascade texel, the equivalent of 128 binary occlusion rays; this works well with normal maps and also feeds specular ([paper](../sources/2023_sannikov_radiance_cascades_paper.md)).
- Cost is fixed by the probe hierarchy, not by scene content: about 1 ms whatever the number of lights, about 3 ms on a GTX 1050 in the paper, and a reported 0.8 ms on an RTX 4090 at 4K ([ExileCon 2023](../sources/2023_sannikov_exilecon_rendering_poe2.md), [discussions](../sources/2026_rc_discussions.md)).
- No temporal accumulation and no TAA, because the game changes too fast; every frame is solved from scratch.
- Screen space is enough because the camera is a fixed top-down view with no relevant lights behind it.
- The diffuse result and specular cone queries both come from the same cascades.

## Parameters in the projects found

| Project | Tracing | Cascade 0 spacing | Cascade 0 directions | Per cascade | Intervals | Cascades |
|---|---|---|---|---|---|---|
| Sannikov SPWI demo | analytic SDF | `2^i` px at cascade `i` | `2^i×2^i` octahedral at cascade `i` | dirs ×4, spacing ×2 | world | not given |
| [Gavras](../sources/2025_gavras_screen_probes_world_intervals_thesis.md) | hardware RT (Metal) | 4 px | 16 octahedral | dirs ×4, spacing ×2 | world, ends at `0.016·4^L` | 6 |
| [Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md) (ClaikoCode) | DXR | 1 to 4 px | 16, 36, 64 equal-area octahedral | dirs ×4, spacing ×2 | world, start `5·(4^c−1)/3`, length `5·4^c` | 5 to 8 |
| [three-rc](../sources/2025_bennett_three_rc.md) | BVH in GLSL | 4 px | 16 octahedral | dirs ×4, spacing ×2 | world, start `0.005·4^L` (0 at level 0), length `0.005·4^(L+1)`, so levels overlap | ceil(ln max(W, H)) by a bug |
| [RC-SPWI](../sources/2026_screen_space_probe_repositories.md) | hardware RT (Metal) | 4 px | 16 octahedral | dirs ×4, spacing ×2 | world, `0.24·4^(L−1)` to `0.24·4^L` | 6 |
| [Kung](../sources/2025_kung_rc_vs_voxel_cone_tracing_thesis.md) | depth march, fixed thickness | 1, 2, 4 px | 4×4 azimuth × polar | dirs ×4, spacing ×2 | march steps `20·1.2^i` | 6 |
| [Alpha-Renderer](../sources/2026_screen_space_probe_repositories.md) | min/max depth pyramid march | 2 px | 2×2 hemisphere | dirs ×4, spacing ×2 | world, ends at `0.08·4^(c+1)`, +15% overlap | 6 |
| [Unreal bitmask RC](../sources/2026_unity_unreal_rc_plugins.md) | screen slices, 32-sector mask | 2 or 4 px | 4 or 16 | dirs ×R, spacing ×√R | pixels, start `2T·(R^c−1)/(R−1)`, length `2T·R^c` | up to 32 |
| [Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md) | DXR ray queries | 1, 2, 4 px | 4 pre-averaged | dirs ×4, spacing ×2 | world, `4^i·scale` to `4^(i+1)·scale` | not given |
| [Unity URP](../sources/2026_unity_unreal_rc_plugins.md) | 16 virtual rays against variance depth | 8 px, min and max probe | 4 azimuth × 4 polar | azimuth ×2, spacing ×2 | doubling | 6 |

Points that hold across them:

- **Directions:** equal-area octahedral mapping removes the axis bias of plain octahedral; cascade 0 needs at least 8 directions; and since SPWI directions double per axis per cascade, its intervals should grow 2×, not 4×, to keep world ray density constant (same source).
- **Direction-first layout and pre-averaging** are standard (see [core_theory.md](core_theory.md)). With pre-averaging, every cascade texture is the same size, `pc0·sqrt(rc0)/2` per axis (Dell'Ova).
- **Valid base direction counts** for a square pre-averaged layout are `4k²`: 4, 16, 36, 64. Dell'Ova excludes 4 in 3D because four symmetric sphere directions lie in one plane.
- **Equal cost for equal rays:** configurations with the same `rc0/spacing²` cost about the same (16 rays at 1 px and 64 rays at 2 px both took about 24.7 ms in Dell'Ova's tests), so spatial and angular density trade freely at fixed cost.
- **Interval units:** world-unit intervals must be tuned to the scene's scale (Gavras, Dell'Ova). Screen probes are a fixed number of pixels apart, so their world spacing grows with view depth while a world-unit interval does not. Far from the camera the spacing then outgrows `t0` and breaks the penumbra condition `Δp ≲ t0`. Intervals in pixels (Unreal) or scaled with view depth keep the ratio fixed; Split RC solves the same problem with distance LODs for world probes.

## Probe placement

- Each probe reads the depth at its tile center and reconstructs the world position. Gavras and three-rc then pull it to 98% of its depth toward the camera to stop self-hits; Kung and Alpha-Renderer push it along the normal (`max(0.01, 0.0015·linear depth)` in Alpha-Renderer).
- Rays that start under the surface, or probes on a thin edge, return black and darken the result; see the "rays starting inside geometry" section of [artifacts_and_fixes.md](artifacts_and_fixes.md).
- A probe at the tile center can land on the background while most of the tile is foreground. **Min/max probes** fix this: build a min/max depth mip chain, place two probes per tile, one at the minimum and one at the maximum depth, and blend the upper cascade's pair by where the child's depth falls between them. Unity's plugin found this the most stable of its three modes; CorylusDonuts' design stores both intervals in one RGBA32UI texel; Gavras proposes it as future work, with odd rays on the near probe and even rays on the far one to keep the ray count. Kaméus measured it against one bilaterally merged probe per tile: 2 to 17% more time, twice the rays and memory, and only 0.5 to 5.8% lower error, but it removed the splotchy leaks at depth edges and the worst flicker under motion ([Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md)).
- **Filling gaps:** a uniform grid leaves pixels on fine geometry with no matching probe. Lumen subdivides the grid where geometry is detailed; Godot's screen-probe draft adds a probe at one of 8 jittered candidates per tile when the base probes cover it with weight under 0.01, from a pool of half the base count. Brixelizer GI instead tries up to 8 jittered positions per tile until one has valid depth. daGI2 runs up to log2(tile size) passes, each adding a probe at the tile pixel least covered by the planes of nearby probes, from a pool of 0.75 times the base count at 16-pixel tiles ([Lumen](../sources/2022_wright_lumen_siggraph_advances.md), [HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md), [Brixelizer](../sources/2024_amd_brixelizer_gi.md), [daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).
- **Keeping anchors:** daGI2 leaves a probe at last frame's pixel when that pixel reprojects inside the tile with a matching depth, and moves it to the tile center otherwise. Re-placing probes every frame under TAA jitter stopped temporal reuse and made probes blink ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).
- Full-sphere directions waste the half that points into the surface (Dell'Ova notes those rays carry nothing after the merge's occlusion test), but parents and children share direction bins whatever their normals. A hemisphere around each probe's normal (Alpha-Renderer) halves storage at the cost of matching bins between probes with different normals.

## Tracing

- **Depth-buffer march:** fast and the only option that needs no scene representation. Abou Dan and Jensen traced screen probes with visibility-bitmask GI for the game As We Descend and ran at 2 to 26 ms depending on settings with no temporal reuse, but the screen-space tracing over-brightened the background and flickered under small camera moves ([thesis](../sources/2025_abou_dan_jensen_rc_vbgi_thesis.md)). A single depth layer has unknown thickness; Kung's fixed thickness leaked through thin objects, Alpha-Renderer marches a min/max pyramid coarse to fine, and the Unreal plugin treats each depth sample as a slab of fixed thickness, as in [visibility-bitmask SSGI](../sources/2022_therrien_visibility_bitmask_ssgi.md).
- **Sector casting and prefiltering** made depth-buffer RC real time in one account: naive vanilla RC at about 1000 ms fell to 10 ms through fp16, half resolution with depth-aware upscaling, sector casting (each depth sample updates every cone that projects onto its screen line) and occlusion bitmasks. Depth moments allow prefiltering that bitmasks and horizons cannot ([screen-space notes](../sources/2026_screen_space_rc.md)).
- **World rays:** the ray from the probe position is traced in a world structure. Tracing dominates: the RC gather was 87 to 96% of all RC time in Dell'Ova's DXR measurements, and Kung's naive depth march was the main cost there too. Godot's `RenderingDevice` has no ray queries in compute shaders (see [docs/rendering_device.md](../../docs/rendering_device.md)), so world rays in Godot need a software structure; the options are in [scene_representation_and_tracing.md](scene_representation_and_tracing.md).
- **What a hit returns** decides the number of bounces. three-rc, Gavras and Dell'Ova return only emission, so lit non-emissive surfaces bounce nothing. Alpha-Renderer reads its direct-light buffer (light without albedo) and multiplies by the hit surface's albedo. Reading the previous frame's lit color or GI at the hit adds bounces over frames.

## Merging across depth edges

Upper probes can sit on different surfaces than the lower probe, so plain bilinear interpolation leaks light and shadow across depth edges. In order of quality:

- **Bilateral weights:** Gavras multiplies each bilinear weight by `1/(|d_i − d| + 0.0001)` only where the four depths differ by more than 10% of their mean; 4XXSWS uses `exp(−100·|d_i − d|)`; CorylusDonuts uses `exp(−16·|d_i − d|/d)`. Bilateral merges show striations at steep angles (Gavras).
- **"Bilinear 3D"** ([4XXSWS](../sources/2023_rc_shadertoys.md)): reconstruct the four upper probes' world points and solve for the bilinear ratio at which they interpolate to the lower probe's point, alternating projections onto the two edge pairs for 2 to 4 iterations. Weights follow the surface instead of rejecting samples and need no normalization. three-rc, RC-SPWI, the Unreal plugin and Gavras use it. Guard the projection against zero-length edges: three-rc divides by zero when two corners clamp to the same probe at the screen edge.
- **Per-sector occlusion** (Unreal plugin): each interval stores a 32-sector mask of the screen slice it covers, and the upper value is scaled by the share of its covered sectors that the lower interval leaves open, `WeightedBitSum(UpMask & ~mask)/WeightedBitSum(UpMask)`. Light hidden in one part of a slice still passes in another.
- **Min/max probes**, above, address the same problem at its source.

Later min/max probe builds ([screen-space notes](../sources/2026_screen_space_rc.md)) adds the construction details: widen the 2×2 min/max chain by half a texel so max does not creep into min, start intervals outside the tile (at least its diagonal) or a black band appears, use a 3×3 upscaling window, and store min and max in a `W×H×2` texture so one trilinear tap does the depth-aware lookup. A continuous min/max that blurs foreground and background classes separately was stable under camera motion. Path of Exile 2 skips the pair in tiles without a depth discontinuity.

## Final gather

- Cascade 0 is reduced per probe to irradiance and then interpolated per pixel. Options: a cosine-weighted average per probe (Gavras), a 6×6 octahedral irradiance tile or L1 spherical harmonics per probe (Split RC, Unity URP), or reading all directions per pixel.
- **Normalization:** for `N` equal-solid-angle bins, irradiance is `E = Σ L(ω)·max(n·ω, 0)·4π/N`, and Lambertian outgoing light is `albedo·E/π`. Because `Σ max(n·ω, 0)·4π/N ≈ π`, a cosine-weighted average `Σ L·cos/Σ cos` is already `E/π` and only needs albedo (Gavras, gomezzz). three-rc sums 16 terms with weight 1, which is 4/π too bright for equal-area bins; Dell'Ova sets the cosine to 1.
- **Per-pixel weights:** bilateral depth weights (Gavras, threshold 0.05), or the distance from each probe to the pixel's tangent plane, `saturate(1 − planeDistance/(0.03·depth))`, falling back to the nearest probe when all four fail (Unreal plugin).
- **Cascade −1:** cascade 0's spacing blurs contact shadows and small detail. A per-pixel short trace over `[0, t0]` merged in front of interpolated cascade 0 fixes it (the `C_MINUS1_GATHERING` path in 4ctXD8); Split RC uses visibility-bitmask SSGI for this at 1.4 ms.

## Temporal behavior

- Screen probes move with the camera and jump in depth between frames, so the GI flickers under motion. Gavras, Kung, the Unity plugin and the Gerassimov comparison (RC rated "medium" for temporal stability) all report it.
- Fixes found: min/max probes; temporal accumulation with reprojection (Alpha-Renderer with the previous view-projection; Sannikov's SPWI demo converged in 0.1 to 0.5 s); blending with the previous frame only where the surface is the same, clamped to the current neighborhood's spread (EggyStudio's screen probes); world-space probes instead (Kung's suggestion).
- Small lights flicker and streak when too few cascade 0 directions hit them; rotating directions per frame and accumulating helps (Kung).
- Non-RC screen-probe systems settle on the same recipe. Lumen jitters probe positions, rejects history by depth and normal with no neighborhood clamp, and speeds up accumulation where rays hit moving objects. Godot's draft blends each direction with `w = 1/(age + 1)`, age capped at 7, and 0.5 for dynamic receivers, reprojecting with unjittered matrices and with velocity for moving objects. daGI2 gives a new probe weights of 1, 1/2 and 1/3, then 0.025 per frame, and 0.125 on moving objects, and re-traces only a set fraction of probes each frame ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).

## Hybrids

Screen probes handle the near field well and world probes the far field, so several designs split the work:

- EggyStudio traces screen probes through the depth buffer out to twice the world probe spacing and takes world probes' light beyond it; the whole system cost 0.6 to 1.0 ms at 800×450 on a laptop GPU ([design documents](../sources/2026_engine_rc_design_documents.md)).
- genos-engine walks outward from near world-fixed probes to a screen cascade to a coarse world volume.
- Godot's lead developer planned world-space GI for low-frequency light plus a screen-space layer for detail and occlusion ([discussions](../sources/2026_rc_discussions.md)). The 2026 draft that adds screen probes to HDDAGI does this: a Hi-Z trace up to 2 units, then the voxel cascades.
- Lumen shortens the screen-probe ray and reads its 32×32-direction world cache when the ray misses, with a 16-pixel contact AO in front; Brixelizer GI blends screen-probe SH with a world SH probe per brick ([related techniques](related_techniques.md)).
- HSGI's phone path places one 4×4 hemisphere probe per 64×64-pixel tile and lets pixels on dynamic objects, marked by a G-buffer bit since there is no velocity buffer, read the world probe volume directly, which avoided smearing ([HSGI](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md)).
- daGI2 cuts each screen-probe ray at 3 to 6 world-grid probe sizes (3 for new probes) and reads its world radiance clipmap there, pulled back half a grid probe so the filtered read does not cross a wall. Before that, a 16-sample screen march reads last frame's lit pixel at a hit, and an SDF march reads its voxel lit scene ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).
- KingTheFifth's 3D RC lifts screen probes by depth and traces their world intervals through voxels or Hi-Z ([repository survey](../sources/2026_rc_repository_survey.md)).

## Cost

Measured numbers for all designs are collected in [performance.md](performance.md). For screen-space RC the takeaways are that cost and memory follow the cascade 0 probe count, which grows with the inverse square of the spacing; each added cascade adds a fixed amount; cost scales roughly with pixel count; and the ray tracing step is nearly all of it.
