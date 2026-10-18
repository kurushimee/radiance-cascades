# Related techniques

Other real-time GI methods solve problems an RC implementation meets too: probe placement and reuse, leaks, hashing, temporal blending, and near-field detail. This note lists what each one contributes to RC. Details and numbers are in the linked source notes.

| Technique | What carries over to RC |
|---|---|
| [DDGI](../sources/2019_majercik_ddgi.md) | world probe grid upkeep: visibility, relocation, probe states, blending, irradiance tiles |
| [GI-1.0](../sources/2023_boisse_gi10_two_level_radiance_cache.md) | screen-probe reuse, hole filling at a fixed budget, firefly-safe blending, a leak bit for hashed caches |
| [Path space filtering, SHaRC](../sources/2019_binder_path_space_filtering_and_sharc.md) | hashed caches: keys, LOD from distance, fixed-point atomics, eviction |
| [Bevy Solari](../sources/2025_jms55_bevy_solari.md) | a hashed world cache in practice; RC tried and dropped |
| [kajiya](../sources/2022_stachowiak_kajiya_gi.md) | a sparse irradiance cache that places ray origins where it is queried, ranked by bounce, against thin-wall leaks; a near and far split that keeps contact detail |
| [Visibility-bitmask SSGI](../sources/2022_therrien_visibility_bitmask_ssgi.md) | cascade −1 near-field detail; per-sector occlusion |
| [Screen-space ray tracing](../sources/2014_mcguire_mara_screen_space_ray_tracing.md) | depth-buffer intervals |
| [Enshrouded's probe cache](../sources/2026_rc_conference_talks.md) | ray budgets, probe push-out, stochastic cascade blending |
| [Godot SDFGI](../sources/2026_godot_gi_internals.md) | the engine's own GI, its limits and costs |
| [Godot HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md) | an integer hierarchical DDA voxel tracer, probe upkeep and screen probes written for Godot's renderer |
| [Lumen](../sources/2022_wright_lumen_siggraph_advances.md) | layered caches split by range, screen-probe filtering, thin-wall and foliage fixes, fixed update budgets |
| [Brixelizer GI](../sources/2024_amd_brixelizer_gi.md) | a compute-only sparse SDF with an open GLSL tracer, feeding screen probes and world caches |
| [HSGI](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md) | an HDDA voxel radiance cache filled from the lit screen, shipped on phones with a measured budget |
| [daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md) | screen probes that hand off to a world radiance clipmap after a few probe sizes, a narrow-band SDF built with atomics, voxels lit from the frame; all source open |
| [On-surface caches](../sources/2024_tatzgern_on_surface_radiance_caches.md) | radiance stored on the surfaces themselves: no leaks through thin occluders, filtering without depth tests |
| Voxel cone tracing | the closest comparison for a voxel-traced RC |
| [Line sweeping, short characteristics, cone sweeping, transforms](../sources/2026_light_transport_alternatives.md) | other ways to propagate light on a grid, extended gathering, caustics, multi-bounce feedback and RC-guided sampling |

## DDGI

DDGI is one cascade of world probes that trace a full sphere every frame and blend into 8×8 octahedral irradiance and 16×16 distance maps. Everything that keeps a DDGI grid usable applies to the probe grid of world-space RC:

- **Visibility:** each probe stores mean and squared hit distance; a query weights each of 8 probes by a Chebyshev test toward the point, a wrapped backface term and the trilinear weight, after biasing the point by `0.1·n + 0.1·v` (SDK) toward the normal and the viewer.
- **Relocation and states:** 32 fixed rays per probe; more than 25% backface hits means the probe is inside geometry and moves out, within 45% of a cell. Probes with no nearby surface go inactive; sleeping probes saved 30 to 50% of update time.
- **Blending:** hysteresis 0.85 to 0.98, lowered sharply where a texel changes by more than 25%; storing `irradiance^(1/5)` converged fastest and damped fireflies.
- **Tiles:** octahedral tiles need a 1-texel border for hardware filtering ([octahedral mapping](../sources/2014_cigolle_octahedral_unit_vectors.md)).
- **Against RC:** erhe reduces RC cascade 0 into DDGI's maps and measured an RC update at 1.15 to 1.57× a DDGI update; RC passed room-pair leak tests but failed on probes inside floors (no relocation), small emitters, corridor far fields and settling speed ([erhe](../sources/2026_erhe_world_space_rc.md)). Sannikov considers 3D RC a direct improvement over any regular or nested probe grid such as DDGI ([discussions](../sources/2026_rc_discussions.md)).

## GI-1.0

AMD's two-level cache: screen probes on visible surfaces plus a hashed world cache, hardware ray traced at a quarter sample per pixel, 1.9 to 3.1 ms at 1080p. Its screen cache faces the same problems as screen-space RC:

- **Reprojection rule:** a pixel reuses last frame's probe if `|dot(probe − pixel, n)| < cell_size` and the normals agree within `dot > 0.95`. `cell_size` grows with distance from the camera.
- **Fixed budget:** tiles that failed to reproject take rays from tiles that did, instead of adding rays.
- **Shadow-preserving blend:** keep the older value when the new one is brighter in the way fireflies are (formula in the source), which keeps shadows and filters sub-cell fireflies.
- **Thin geometry:** probes that fail reuse go to a persistent LRU side cache found again by splatting into screen tiles, which stops lighting on thin features from wobbling.
- **World cache leak fix:** add the bit `ray_length < cell_size` to the hash key, so a short ray in an enclosed space and a long ray from outside never share a cell.
- **Temporal radiance feedback:** a hit that was visible last frame reads last frame's lit color, giving bounces for free over frames.

## Hashed caches: path space filtering and SHaRC

Split RC stores probes in per-cascade hash maps, as do the GI-1.0 and Solari world caches. These sources give the tested details:

- Key: quantized position plus a LOD from camera distance (`level = clamp(0.5·log2(dist²) + bias, 1, 511)` in SHaRC), plus normal sign bits so surfaces at an edge do not share a cell. Jittering positions in the tangent plane before quantizing trades block artifacts for noise.
- Slots: a hash for the bucket and a second hash or the key itself for checking, with short linear probing (SHaRC: 16-slot buckets).
- Accumulation: `uint(radiance·weight·scale)` added with integer atomics, `scale` about 1000 and lowered for bright scenes; the same approach works in Godot, which has no float atomics.
- Resolve: blend by sample counts, cap the history length, evict entries unused for 8 or more frames, and borrow history from the same cell one LOD coarser or finer when a new entry appears after camera motion.

## Bevy Solari

Solari moved from Lumen-style screen probes to RC and then to ReSTIR, saying RC "brought their own artifacts and performance costs" without details. Its world cache is a working hashed irradiance cache: cells claimed on first query, freed after a lifetime without queries, compacted into a live list for indirect dispatch, each tracing a light sample and a cosine ray per frame. Known problems: a cell's position and normal are fixed by its first sample, the cache seemed to lose energy, and bright cells flicker and trail behind moving lights.

## kajiya

A research renderer by Tomasz Stachowiak with ReSTIR GI at half resolution for the first bounce and a sparse world irradiance cache for the rest, 8.4 ms per 1080p frame on an RX 6800 XT with hardware ray tracing. HDDAGI's screen-probe draft names it as a model. Two ideas carry over to RC:

- **Probes placed by use:** each cache cell traces from a random one of the points that queried it this frame, so its light matches the side of the wall the camera is on. A rank per cell (1 for queries from screen rays, 2 for queries from rank-1 cells, and so on) stops deeper bounces from moving the origin, which removed leaks into closed rooms.
- **Near and far split:** spatial reuse erased small-scale bounce in corners, so the resolve takes near hits from the raw rays of that frame and far hits from the filtered reservoirs, with the threshold growing with camera distance. RC's cascade 0 serves the same near field, and the split argues for filtering it less than the far cascades.

## Visibility-bitmask SSGI

A screen-space GI that replaces GTAO's two horizon angles with a 32-sector bitmask per slice and treats each depth sample as a slab of constant thickness, so light passes behind thin objects. Split RC uses it as cascade −1 for detail below cascade 0's spacing (1.4 ms), and the Unreal RC plugin carries its masks through the cascade merge (see [3d_screen_space.md](3d_screen_space.md)). Half resolution was about 2.7× cheaper by the paper's own table, but flickered more.

## Enshrouded's cascaded probe cache

A shipped world-space probe cache with 12 cascades of 32³ cells, traced through an SDF of the voxel world on all hardware including the Steam Deck. Not RC, but its practical rules carry over:

- A fixed ray budget per platform (100k, 250k or 500k rays per frame); new probes start with 512 rays and drop to 16 per frame once stable.
- Rays importance-sampled from the probe's own radiance, with uniform sampling every 5 frames so no direction starves; uniform sampling alone flickered at 16 to 32 rays.
- Rays sorted by position and direction bins before shading, because mixed rays diverged badly.
- Probes inside walls pushed out along the SDF; probes whose summed ray distance is under 1 mm are dead.
- Overlapping cascades blended stochastically, picking the coarser one with a probability that rises across the overlap.

## Godot SDFGI

Godot's built-in dynamic GI: up to 8 camera-following cascades of 128³ voxels (cell size 0.2 m doubling per cascade by default), a jump-flooded SDF, and 17³ probes per cascade traced through the SDF, 16 rays each by default, converging over about 30 frames. Only static meshes contribute; it is "mostly leak free" for walls thicker than one voxel of the cascade that renders them. Its volumes are private engine data, so an RC implementation cannot reuse them. Comments relaying posts by Godot's lead developer, reduz, say world-space RC is limited to 3 or 4 cascades by memory and occlusion and sits closer to SSGI than to SDFGI or Lumen. reduz's design deck adds the parts the code does not explain: sub-voxel bit masks seeding the jump flood, merging the flood across a scroll seam, cached hits, relighting only where rays hit, and a card-atlas plan for moving objects ([SDFGI plan](../sources/2023_linietsky_godot_sdfgi_plan.md)).

## Voxel cone tracing

Kung compared screen-space RC with voxel cone tracing on Sponza; VCT showed only leaks, stronger than RC's through thin objects, while RC showed leaks, flicker and dim small lights ([Kung](../sources/2025_kung_rc_vs_voxel_cone_tracing_thesis.md)). A world-space RC over a 256³ voxel volume cost 1.98 ms against 2.06 ms for VCT on an RTX 4090 at 1080p, with quality not compared ([discussions](../sources/2026_rc_discussions.md)).

## Godot HDDAGI

reduz's unmerged replacement for SDFGI, rebased in 2026 and extended with Lumen-style screen probes in a draft; Godot 4.7.2 still ships SDFGI. It is the closest existing code to a voxel tracer written for `RenderingDevice`:

- **Tracer:** cells grouped into 4³ blocks with a 64-bit occupancy mask and 8³ regions with a flag, walked by an integer DDA with 8 fractional bits that descends into occupied cells and climbs out of empty ones. Rays that leave a cascade continue in the next coarser one. The authors call cost dependent on the amount of geometry, not its triangle count.
- **Upkeep:** cascades follow the camera by wrapping their addresses and revoxelizing only the uncovered slabs; a per-region version number invalidates cached probe hits when geometry changes.
- **Probes:** one per 8 cells with 5×5 octahedral tiles, results splatted with fixed-point integer atomics, history as a moving average over 6 to 32 frames. New probes are seeded from the coarser cascade.
- **Leaks:** occlusion weights from a wavefront propagated across each probe block still leak at corners, where the normal bias does not clear the outside probe. Smaller cells (0.03 with 5 cascades) or pushing the cascades ahead of the camera removed the leaks in tests.
- **Screen probes (draft):** a Hi-Z trace up to 2 units before HDDA lets visible dynamic objects occlude and bounce light. The directional mode traces 64 rays into an 8×8 tile per probe, splits the brightest directions into finer children and reuses history for the dimmest, and adds probes where the base grid covers a pixel poorly.

## Lumen

Unreal's GI stacks four levels by range, each given the precision its range needs: contact AO for 16 pixels, screen probes (one per 16 pixels, 8×8 directions) for the first meters, a world radiance cache (32×32 directions, much sparser) out to 200 m, and the skylight beyond. That is the trade RC makes with its penumbra rule, except that Lumen picks the levels and their hand-offs by hand: the screen-probe ray is shortened and the world probe is interpolated on a miss. GI-1.0 measured 2.4 ms against Lumen's 2.6 ms on one UE5 scene. What carries over:

- **Fixed budgets:** the world cache keeps last frame's probes, traces newly revealed ones, and retraces a fixed number picked from a GPU priority queue, so cost is fixed and latency varies. The surface cache relights a fixed texel count per frame ordered by `LastUsed − LastUpdated`.
- **Screen-probe filtering:** interpolate only from probes on the pixel's plane; filter spatially in probe space (3×3 probes cover 48×48 pixels without per-pixel tests); temporal filtering with depth and normal rejection, sped up where rays hit moving objects.
- **Importance sampling:** product sampling of BRDF and incoming light from last frame's reprojected screen cache, falling back to the world cache, was worth about four times the rays.
- **Tracing hand-offs:** each tracer resumes from the previous one's distance; a screen trace that goes behind a surface steps back to its last unoccluded point before handing off.
- **Thin walls and foliage:** surfaces are expanded by half a voxel at trace time, growing with distance from the ray origin so contact shadows survive; foliage carries a coverage value that reduces the expansion and drives stochastic transparency.
- **Rejected:** voxel cone tracing (leaks in coarse mips), software BVHs (slow for long incoherent rays), voxel bit bricks (slow to march, though HDDAGI shows a hierarchical walk over them), and irradiance fields (leaks, hard placement, a flat look).

## Brixelizer GI

AMD's compute-only GI on a sparse distance field: cascades of 64³ voxels where each voxel touching geometry gets an 8³ brick of one-byte distances in a shared atlas, found through a small AABB tree per cascade. A GI-1.0 style pipeline puts one probe per 8×8 tile, traces it through the bricks, and reads lighting at hits from a radiance cache filled from the previous frame's lit screen, so surfaces must have been on screen to bounce their color. An SH irradiance cache per brick backs the screen probes. Its MIT-licensed SDK release includes the Vulkan GLSL builder and tracer, which makes it a ready reference for an RC tracer that needs no triangles at trace time. It costs about 2 ms at 4K on an RX 7900 XTX.

## HSGI

Lightspeed Studios' dynamic GI for large open worlds with destructible geometry, running on PC, consoles and phones without needing hardware ray tracing. It traces the same kind of structure as HDDAGI, 4³-voxel bricks in a sparse clipmap walked by a hierarchical DDA, but its voxels also hold lit radiance, which is what an RC tracer has to return at a hit:

- **Screen injection:** one thread per voxel near the depth buffer writes the lit scene color into voxels at the depth and clears voxels in front of it, so moved and destroyed geometry updates without revoxelizing. Tiles of bricks are culled to the frustum and updated less often with distance.
- **Off-screen geometry:** each object is drawn with its own material shader along 3 axes with an orthographic camera, the same three-pass approach as SDFGI's voxelization.
- **Bounces:** each voxel gathers a hemisphere of indirect light, amortized over 9 frames near the camera and 121 far away with 16 threads per brick, so the cache carries several bounces.
- **Mobile:** tracing per pixel was too slow, so phones gather deferred screen probes (one 4×4 hemisphere probe per 64×64-pixel tile, at half resolution) backed by a DDGI-style volume. The whole GI costs 3.18 ms per frame on an iPhone 13 Pro.
- **Against Lumen:** on an RTX 3080 at 4K with TSR, its GI passes took 8.53 ms against Lumen's 9.63 ms with lower error against a path tracer. Denoising the half-resolution ReSTIR GI cost four times as much as tracing it.

## daGI2

Gaijin's dynamic GI in the open-source Dagor Engine, with no hardware ray tracing. Rays march an R8 narrow-band SDF clipmap, and hits read a voxel copy of the lit frame. It is worth reading in full before building world-space RC, because its rays already work in intervals:

- **Hand-off:** screen-probe rays stop after 3 to 6 world-probe sizes and read the world radiance clipmap, pulled back half a probe so filtering does not cross walls. World probes that scroll into a clip stop at 4 coarser-clip probe sizes and read the coarser clip's texel for the same direction.
- **Scene:** the SDF is built with `InterlockedMin` and one 26-neighbor relaxation pass, then kept current by marking distances from random depth pixels and raising them where the HZB shows empty space. The lit voxels take the final color of random G-buffer pixels each frame, so bounces build up without relighting voxels.
- **Upkeep:** every budget is a count. World probes are picked by a probability from age, frustum, HZB occlusion and surface proximity, with a feedback multiplier that holds the count steady.
- **Pitfalls on record:** R11G11B10F writes drift yellow unless rounded, large lit voxels leak more than SDF plus albedo, and the lit scene needs typed storage loads.

Its predecessor in Enlisted cost 0.57 ms on a GTX 1070 and 0.7 to 1.6 ms on Xbox One.

## On-surface caches

Tatzgern et al. store 8×8 hemispheres of radiance in texture space on mesh islands instead of in probes. Entries sit on the surfaces, so thin occluders cannot leak and a blur in cache space needs no depth or normal tests; it costs 1.45 to 2.64 ms at 1080p, close to GI-1.0. Its problems are those any surface-bound RC layout (X3XfRM, the surface-chart RC in the [repository survey](../sources/2026_rc_repository_survey.md)) would meet: seams at island borders, extra entries where neighboring pixels fall on different islands, and allocation blowing up on foliage.
