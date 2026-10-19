# Scene representation and tracing

Every RC design asks one query of the scene: what is the first thing along the segment `[t_c, t_{c+1}]`, and what light leaves it toward the probe. That query is nearly all of the cost (87 to 96% of RC time in [Dell'Ova](3d_screen_space_theses.md)), so the scene representation sets both speed and which artifacts appear. Every option here except hardware ray tracing runs as plain compute. That matters on hosts such as Godot 4.7.2, where compute shaders cannot use hardware ray queries and the ray tracing pipeline is experimental and Vulkan-only with hard limits ([RenderingDevice notes](../../docs/rendering_device.md#ray-tracing)). Definitions of the traversal primitives (DDA, hierarchical DDA, sphere tracing, slab test, Möller-Trumbore, BVH, SAH, BLAS and TLAS) are in the [glossary](supporting_techniques_structures_and_tracing.md#ray-traversal-and-intersection).

Voxel and triangle-BVH tracers are in [voxels and BVHs](scene_representation_and_tracing_voxels_and_bvhs.md).

## Contents

- [What RC asks of a tracer](#what-rc-asks-of-a-tracer)
- [Options](#options)
- [Depth buffer](#depth-buffer)
  - [McGuire and Mara's perspective-correct DDA](#mcguire-and-maras-perspective-correct-dda)
  - [Stachowiak's depth marcher](#stachowiaks-depth-marcher)
  - [Pyramids and atlases](#pyramids-and-atlases)
  - [Layered distance maps](#layered-distance-maps)
- [Distance fields](#distance-fields)
  - [Jump flooding](#jump-flooding)
  - [Sphere tracing and cheaper fields](#sphere-tracing-and-cheaper-fields)
  - [Lumen: mesh and global distance fields](#lumen-mesh-and-global-distance-fields)
  - [Brixelizer](#brixelizer)
  - [daGI2: narrow-band clips without bricks](#dagi2-narrow-band-clips-without-bricks)
- [Hardware ray tracing](#hardware-ray-tracing)
- [Surfels](#surfels)
- [Shading the hit](#shading-the-hit)
  - [Lumen's surface cache](#lumens-surface-cache)
  - [Radiance at the hit from the lit frame](#radiance-at-the-hit-from-the-lit-frame)
- [Robustness](#robustness)
- [Where tracing time goes](#where-tracing-time-goes)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)
- [Open questions](#open-questions)

## What RC asks of a tracer

- **Segments, not rays.** Each cascade traces only its own interval. Near cascades trace short segments and need full precision; far cascades trace long segments but have wide angular cells.
- **Far cascades accept coarse data.** A cascade's direction cell is wide enough that it averages a large footprint at the far end, so far intervals can read prefiltered geometry. DexRT caps cascade `n` at mip `[0, 0, 1, 2, 3, 4][n]` and gets most of its 8× speedup from that ([volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)); creikey's voxel RC picks the clipmap level per sample from the distance along the ray ([implementations](3d_world_space_implementations_grids.md#creikeyvoxel-radiance-cascades)); Phreakyx's design cone-traces voxel mips with an aperture of `2/oct_c` ([Godot integration](godot_integration.md)). Within one interval the needed level spans about two mips, so a single mip per cascade is too coarse at its start or too fine at its end ([which mip](3d_world_space.md#marching-cost)).
- **Coarse data leaks if it thins walls.** Prefiltered scene input thinned 2 px walls enough to leak about 13% per crossing in the HRC samples ([2D experiments](../sources/2026_assorted_2d_rc_experiments.md)). DexRT's variance-limited mipmapping only coarsens a block whose children agree, which keeps sharp structure at full resolution, and averaged voxel mips need directional opacity ([voxel tracing for RC](scene_representation_and_tracing_voxels_and_bvhs.md#voxel-tracing-measured-for-rc)).
- **Closest hit or any hit.** An interval needs the first hit inside `[t_c, t_{c+1}]` for its radiance and only a yes or no for its transmittance. Shadow rays and validation segments ([sampling and guiding](rc_for_sampling_and_guiding.md)) need any-hit with an early exit, which many compute kernels lack ([BVH kernels](scene_representation_and_tracing_voxels_and_bvhs.md#tinybvh)).
- **A hit returns radiance and transmittance.** Radiance is emission plus direct light times albedo, plus GI at the hit for more bounces ([shading the hit](#shading-the-hit)). Transmittance is 0 for an opaque hit and fractional for media.
- **Coherence falls with the cascade.** Low cascades trace short, spatially coherent segments and high cascades long, incoherent ones. Path-tracing measurements put the cost of incoherent rays in memory stalls ([cost of tracing](#where-tracing-time-goes)), so upper cascades cost more per ray than their step count suggests (inference).

## Options

| Representation | Projects | Off screen | Dynamic objects | Cost found |
|---|---|---|---|---|
| Depth buffer | PoE2, Kung, Alpha-Renderer, Unreal bitmask RC ([3D screen space](3d_screen_space.md)) | no | free | PoE2 about 1 ms in total |
| Distance field (jump flood, sweeps, relaxation or sparse bricks) | nearly all 2D RC; EggyStudio clipmaps; rbnelr; Enshrouded; Godot's SDFGI; Lumen; Brixelizer; daGI2 | yes | rebuild, approximate, or mark from depth | EggyStudio full GI 0.6 to 1.0 ms at 800×450; Brixelizer GI about 2 ms at 4K |
| Voxels with DDA or mips | creikey, Phreakyx, DexRT, CT volume RC, tauray (occupancy only), Godot HDDAGI, HSGI | yes | revoxelize, or inject from the screen | creikey trace 0.5 ms at 640×360 and 14.3 G rays/s in a synthetic test (GPU not named); HDDAGI probe update 0.93 ms on a GTX 1650; HSGI full GI 3.18 ms on an iPhone 13 Pro |
| Sparse voxel octree | GigaVoxels, voxel cone tracing | yes | revoxelize dynamic parts per frame | GigaVoxels Sponza GI 33 ms on a GTX 480 |
| Software triangle BVH | gomezzz, wroughtinator, three-rc, Surfel RC (tinybvh), Wicked Engine (GPU build) | yes | rebuild or refit | about 3.5× slower than hardware RT; tinybvh claims 3 to 5 G rays/s on an RTX 5080 Laptop |
| Analytic primitives | gomezzz (64 boxes and spheres), X3XfRM | yes | per frame | cheap |
| Surfels in a hash grid | Love and Deepspace ([surface probes](3d_surface_probes.md#love-and-deepspace)) | yes | local-space surfels per mesh | about 2 ms total GI on an iPhone 12 |
| Layered distance cube maps | Umenhoffer et al. (reflections, not RC) | what the reference point sees | rebuild per frame | 50 FPS at 800×600 on a GeForce 8800 GTX |
| Hardware ray tracing | chandra, erhe, Dell'Ova, Gavras, Kaméus, tauray, Unreal Split RC | yes | TLAS update | erhe 0.7 ms per million rays |

## Depth buffer

Only the front surface exists, so thickness is a guess: too small leaks behind objects, too large over-occludes. Lights and occluders off screen or hidden are missing. Screen-space RC's own use of the depth buffer, min/max probes and depth-moment prefiltering is in [3D screen space](3d_screen_space.md#tracing), and the bitmask and horizon methods in [related screen-space GI](related_screen_space_gi.md).

### McGuire and Mara's perspective-correct DDA

"Efficient GPU Screen-Space Ray Tracing" (Morgan McGuire and Michael Mara, JCGT 3(4), 2014-12, CC BY-ND 3.0, https://jcgt.org/published/0003/04/04/) is the standard method for tracing against a depth buffer ([notes](../sources/2014_mcguire_mara_screen_space_ray_tracing.md)). Marching a 3D ray in fixed steps and projecting each sample skips some pixels and samples others twice; walking the ray's 2D projection with a perspective-correct DDA visits each pixel along the line once.

Setup:

1. If the ray's far end would pass the near plane, shorten it to end there.
2. Project both ends, keeping `k = 1/w` and `Q = point·k` at each; both interpolate linearly in screen space, so the 3D point at any step is `Q/k`.
3. If the ends are closer than 0.01 px, nudge the far end.
4. If the line is steeper than 45°, swap x and y so the loop always steps along x.
5. Per-step deltas `dP = (sign, dy/dx)`, `dQ` and `dk` are scaled by the stride, and the start is offset by a jitter fraction of one step.

Loop:

- Each step covers ray depths from the last step's maximum to `(Q.z + dQ.z/2)/(k + dk/2)`, the depth half a step ahead.
- Each depth sample is a slab from the stored depth to that depth plus `zThickness` away from the camera, and the ray hits when its depth range overlaps the slab. Up to 4 depth layers can be tested.
- An out-of-bounds fetch returns 0, which ends the loop, so viewport clipping is free. The walk stops after `maxSteps` or at the ray's end.

Parameters: `zThickness` should match typical object thickness (too small lets rays pass behind thin objects; a near-infinite value is reasonable with one depth layer); `stride` above 1 spaces samples for speed but bands, which a per-pixel jitter of the start hides, and the paper suggests it only for rough surfaces; `maxDistance` and `maxSteps` bound the worst case, and cost is linear in the steps taken. Misses can fall back to another structure such as voxels or an environment map, and a guard band around the viewport helps.

25 steps per pixel at 1080p took 1.2 ms on a GeForce Titan and 6.4 ms on a GeForce 650M laptop, about 43 and 8 billion steps per second (derived); 25 rays per pixel for AO cost about 30 ms, which the paper calls too slow for real time. Ideas it leaves open: testing every pixel the ray crosses with conservative rasterization, refining strided hits by binary search, and refining hits to subpixel precision.

### Stachowiak's depth marcher

Tomasz Stachowiak's 2023 HLSL gist (https://gist.github.com/h3r2tic/9c8356bdaefbe80b1a22ae0aaee192db, Apache-2.0 or MIT) marches the depth buffer for contact shadows, SSGI and SSR; three-rc's README credits Stachowiak's Tiny Glade post for it ([screen-space notes](../sources/2026_screen_space_rc.md#links), [three-rc](3d_screen_space_implementations.md#three-rc)).

- It marches in UV with `max(2, min(linear_steps, ⌊len_px⌋))` steps, at most one per pixel, at `t_i = lerp(t_min, t_max, ((i + jitter)/N)^exponent)`, and refines the first crossing with optional bisection and a secant step that is accepted only if it shrinks the distance below 0.9 of the bracket's.
- Depth is reverse Z with an infinite far plane, so surface depth is `1/sample`.
- Each point is tested against both the bilinear and the nearest-texel surface: `distance = max(lin, near)·(1 + 2·10⁻⁶) − ray_depth` and `penetration = ray_depth − min(lin, near)`. Point samples form steps near the ray origin that cause false occlusion, while the smooth surface causes false shadows at object edges, so occlusion is claimed only below both.
- A hit needs penetration and distance below a constant thickness (default 1 in linear z, scaled by the reciprocal near-plane distance), since the depth buffer has no thickness.
- Defaults: 4 linear steps, exponent 1, no bisection or secant (useful for colour, as in SSR or SSGI, pointless for contact shadows), no jitter, no marching behind surfaces (contact shadows only, since it leaks colour bounces; then the thickness should be at least the world ray length over the step count), and no nearest-only sloppy mode. A miss returns the farthest point reached. The included `frame_constants`, `uv` and `samplers` headers are not in the gist.
- The Tiny Glade post (https://twitter.com/h3r2tic/status/1652056116908490760): DDA came first but needed so much bias against acne and false hits that contact shadows were lost, and larger steps made it worse; the marcher was faster at similar quality. A later fix to its secant refinement stopped SSR leaking when rays approached overhangs from below. The experiments did not ship in Tiny Glade ([three-rc notes](../sources/2025_bennett_three_rc.md#links-found)).

### Pyramids and atlases

- A min/max depth pyramid lets a ray skip empty space coarse to fine (Alpha-Renderer), and a visibility bitmask per sample handles thin objects better than one horizon ([Therrien](related_screen_space_gi.md)). Lumen's screen traces walk the closest HZB mips without a stack, because linear steps skipped thin tables, doors and walkways ([Lumen's tracing](#lumen-mesh-and-global-distance-fields)).
- **Mip chains in one atlas.** Aaltonen's 2020 post atlases a whole mip chain into one 2D texture 1.5 times as wide as mip 0: mip 0 on the left, mip 1 in the top half of the right column, each further mip below the previous one at half size. That costs 1.5 times mip 0 against 1.333 times for a hardware chain, 12.5% more memory. Mip 0 must be a power of two, or each axis divisible by `2^mips` for a partial chain, or texel coordinates turn fractional. The author uses it because D3D12 and Vulkan lack gather and compare sampling at an explicit mip level, here for single-sample occlusion-pyramid culling with gathers; tmpvar's 3D grid cites it for its cascade-chain debug view ([tmpvar notes](../sources/2024_tmpvar_rc_3d_grid.md#links-found)).

### Layered distance maps

"Robust Multiple Specular Reflections and Refractions" (Umenhoffer, Patow and Szirmay-Kalos, GPU Gems 3, ch. 17, 2007) ray-traces against cube maps that store distance from a reference point, searching each ray in the map's texture space ([notes](../sources/2007_umenhoffer_layered_distance_maps.md)). RC discussions link it as "distance impostors for a spherical radiance field"; the chapter itself says layered distance maps, and "distance impostors" appears only in its reference to Szirmay-Kalos et al. 2005. Section numbers are the chapter's.

- **Representation (sec. 17.2).** Each layer is a cube map rendered from the reference point. A texel holds the material (reflected radiance for diffuse surfaces, or the Fresnel factor at normal incidence for specular ones), a refractive index whose sign gives the type (negative reflector, zero diffuse, positive refractor), the normal, and the distance. Layers come from depth peeling with a capped count, far objects collapsing into one layer; a single reflective object puts its front and back faces in two layers, with empty texels cleared to a negative distance. Per-map minimum and maximum distances bound the search ("Acceleration with Min-Max Distance Values").
- **Tracing (sec. 17.2.2).** For the ray `x + R·d`, the point `l` is compared with the stored distance `|l'|` in its direction: `|l|/|l'| < 1` is in front of the surface, `> 1` behind it. The linear search is uniform on the segment between the projections of the start and the direction onto the unit sphere, `r'(t) = s·(1 − t) + e·t` with `s = x/|x|` and `e = R/|R|`, so steps are even in texels; the ray parameter is `d = a·t/(1 − t)` with `a = |x|/|R|` (Listing 17-1). The step `dt` scales with the segment length and the map resolution, and a step longer than a texel can miss thin objects. Every layer is searched, and the one with the smallest overshoot holds the first hit.
- **Secant refinement (Listing 17-2):** `d_new = d_l + (d_p − d_l)·(1 − llp)/(ppp − llp)` from the last undershoot and overshoot and their ratios, exact for planes. Fig. 17-6 compares linear/secant step limits of 15/1, 15/10, 80/1 and 80/10.
- **Shading:** Schlick Fresnel `F = F_p + (1 − F_p)·(1 − N·R)^5` with `F_p` from the refractive index and extinction coefficient computed on the CPU; a loop up to `MAXDEPTH` reflects or refracts by the index's sign, falls back to reflection on total internal reflection, multiplies by the Fresnel factor at each specular hit and by the diffuse radiance at the end (Listing 17-5).
- **Results:** DirectX 9 HLSL on a GeForce 8800 GTX at 800×600, six 512² cube maps rebuilt every frame and three layers (two for the reflective object, one for diffuse surfaces); depth peeling was not implemented. The video runs at 25 FPS without and 50 FPS with min/max acceleration, with at most two reflections, and the frame rate barely falls with reflection depth (Figs. 17-7, 17-8).
- **Limits:** thin objects are missed when steps exceed texels; abrupt distance changes need fine steps; few layers leave reflected regions empty (shown under a table in Fig. 17-6); one diffuse layer blurs where occlusion depends on the view; maps must be rebuilt when objects move.

A distance cube map is one probe's hit-distance texels, so the chapter's search traces rays near a probe through that probe's stored distances instead of the scene, as light field probes later did with octahedral maps ([related probe GI](related_probe_gi.md)). It works only for rays near the reference point and for what that point sees, the same limit as tracing through screen-space depth (inference).

## Distance fields

### Jump flooding

Jump flooding (Rong and Tan, "Jump Flooding in GPU with Applications to Voronoi Diagram and Distance Transform", ACM I3D 2006, https://www.comp.nus.edu.sg/~tants/jfa/i3d06.pdf) builds the scene distance field of almost every 2D RC each frame and extends to 3D voxel grids. Its cost depends on the grid size, not the number of seeds ([notes](../sources/2006_rong_tan_jump_flooding.md)).

1. Seed texels store their own coordinate; all others store an empty marker.
2. Run `log2(n)` passes with steps `n/2, n/4, …, 1`. In each pass a texel reads the 9 texels at offsets `{−k, 0, k}²` (27 in 3D) and keeps the seed closest to itself, ping-ponging two textures.
3. One more pass writes the distance to the stored seed.

- Halving the step is the point: doubling it (1, 2, 4, …) gives many more errors. Errors are rare and sit mostly at single texels near Voronoi vertices.
- **JFA+1** adds one pass with step 1 and **JFA+2** two passes with steps 2 and 1. The paper recommends JFA+2: the same speed in practice and close to exact. Several RC repositories skip or lose the final step-1 pass through a ping-pong parity mistake, which leaves visible errors.
- A 5-tap plus pattern worked as well as 3×3 in Wolfe's tests; splitting the flood into an x pass and a y pass gave many errors. In 3D (simulated on a CPU at 512³) the results were close to exact, and the authors expect 3D to be more accurate than 2D since more paths reach each point.
- **Signed distance.** A plain flood gives distance outside the shapes only. Flooding again with seeds and empty space swapped gives the inside distance, combined as `signed = outside − inside`; the 2016-02-29 post stores `0.5 + 0.5·outside − 0.5·inside` in a normalized texture.

Alan Wolfe's posts (https://blog.demofox.org/2016/02/29/fast-voronoi-diagrams-and-distance-dield-textures-on-the-gpu-with-the-jump-flooding-algorithm/ and https://blog.demofox.org/2016/03/02/actually-making-signed-distance-field-textures-with-jfa/):

- An `N × N` texture takes `log2(N)` passes with offset `2^(log2(N) − passIndex − 1)` from pass 0, so 4, 2, 1 for 8×8. The texture need not be square or a power of two, though the formula assumes it.
- A read is skipped if it holds no seed. Empty texels hold (0, 0, 0, 0) and seeds their own coordinate (32-bit: x in RG and y in BA; 16-bit float: x in R and y in G), so a seed at pixel (0, 0) is indistinguishable from an empty texel (derived in the notes).
- Weighted seeds multiply or add a per-seed weight to the computed distance ("Weight Pts" and "Add Wt Pts" demos), with no formula beyond that. The brute-force reference loops over every seed per pixel. The error is called very small in practice, with no metric, timing or hardware. JFA extends to volume textures with more reads per pass, and the distances can serve as raymarch step hints.
- An unsigned field has a pixelated zero contour that breaks under zoom; moving the threshold to 0.5 helps but fattens shapes. The fix floods the source and the inverted source and stores `0.5 + 0.5·clamp(|seed_out − p|/8, 0, 1) − 0.5·clamp(|seed_in − p|/8, 0, 1)`, so the surface sits at 0.5 and distances past 8 px saturate (the listing writes `fFragCoord` for `fragCoord`). A full-resolution field still looks wrong when magnified, since a distance field helps only through interpolation; a field at 1/4 the size per axis gives clean edges and holds up to 20× zoom on top of the magnification. The demo is Shadertoy ldVGWc.

**Cost in 3D (derived).** With JFA+2 a 128³ grid takes 9 passes of 27 reads, 243 reads per voxel and about 510 million reads per rebuild; 256³ takes 4.5 billion; a 1024² 2D field takes 108 reads per texel. That is why 3D engines build narrow bands, bricks or incremental updates instead of flooding whole volumes each frame (inference).

### Sphere tracing and cheaper fields

- Sphere tracing steps by the stored distance and needs a minimum step and a hit tolerance; TypeGPU's defaults are `eps` 0.25 and minimum step 0.125 probe spacings, with obstacles eroded by one spacing ([TypeGPU](2d_implementations.md#typegpu-software-mansion)).
- rbnelr builds an L1-style distance per chunk by sweeping lines along x, y and z and steps `n·(1 − ε)/(|dx| + |dy| + |dz|)`, which cannot skip a solid cell, falling back to a voxel DDA near surfaces ([implementations](3d_world_space_implementations.md)).
- **Clipmaps** follow the camera. EggyStudio keeps four 64³ cascades, snaps them in 8-cell steps, rebuilds at most two per frame, adds a mesh to the field only after it has stayed still for 8 frames, and approximates moving meshes as coloured boxes ([design documents](3d_world_space_implementations.md#eggystudio3dengine)). Enshrouded traces an SDF of its voxel world on all hardware ([related probe GI](related_probe_gi.md)).
- Godot's SDFGI builds 128³ SDF cascades with a jump flood but holds them as private engine data that no script or compositor effect can reach, so an RC implementation has to build its own field ([Godot integration](godot_integration.md)).

### Lumen: mesh and global distance fields

Lumen (Wright, Narkowicz and Kelly, SIGGRAPH 2022 Advances; [notes](../sources/2022_wright_lumen_siggraph_advances.md)) traces each ray through methods in order, screen trace, then software or hardware tracing, then the skylight on a miss; each method writes its trace distance and hit flag, and the next resumes from there (pp. 9, 22). Its GI pipeline is in [related engine GI](related_engine_gi.md); the tracing parts are these ([notes](../sources/2022_wright_lumen_siggraph_advances.md#tracing)):

- **Screen traces** walk the closest HZB mips without a stack. On going behind a surface or off screen, the ray steps back to its last unoccluded position before handing off, which avoids leaks at the hand-off. Diffuse rays trace at half resolution (pp. 25 to 27).
- **Compaction** after screen tracing removes finished lanes, order-preserving with a Z-order within 128×128 tiles, a wave prefix sum and global atomics, for up to 50% faster tracing (pp. 29 to 30).
- **Mesh SDFs** are traced for the first 2 m of a ray, at most 64 steps, where step 64 counts as a hit. Instances are found through a froxel grid of culled object lists rather than a BVH (pp. 36, 44).
- **The global SDF** covers the rest: loop over clipmaps from the smallest, sample a continuous coarse mip, and switch to sparse bricks near surfaces (p. 43).
- Directional shadow rays cull objects to a 2D grid in light space and stop at any hit (p. 45).

The fields ([notes](../sources/2022_wright_lumen_siggraph_advances.md#distance-fields)):

- **Mesh SDFs** are built at import with Embree point queries; the sign comes from counting back-face hits among 64 rays per voxel. Storage is sparse 8³ bricks with a half-texel border, a narrow band of ±4 voxels in one byte, and one virtual volume texture per mip. A 1.5M-triangle mesh builds in about 0.6 ms, and mips stream by camera distance from a fixed 320 MB pool (pp. 34 to 35).
- **The global SDF** merges instances at runtime into 4 camera-centred clipmaps of 256³ in the same sparse brick format. Static and dynamic bricks are cached separately and modified bricks are tracked on the GPU; distant clipmaps update less often and drop small objects. Non-uniformly scaled objects use the distance to their oriented bounding box. A quarter-resolution coarse mip is rebuilt with 5 iterations of Eikonal propagation (pp. 40 to 42). A dense 256³ clipmap at one byte would be 16 MiB, so the bricks pay where most of it is empty (derived).
- **Thin walls** may never cross zero between samples, which gives no hit and no gradient and leaks badly. The fix expands surfaces by half a voxel's diagonal at trace time and pulls back to fix the gradient. Expansion over-occludes and adds surface bias, so GI rays start with no expansion and grow it linearly with distance, fading it at the end of shadow rays; reflections use `min(MaxExpand, DistanceToSurface)` per step (pp. 48 to 51).
- **One-sided meshes** get a virtual closing surface that wraps after 4 voxels (p. 47).
- **Foliage:** expansion can block all light between leaves, so each instance has a coverage value (and the global SDF a coverage channel) that reduces expansion, raises the minimum step and drives stochastic transparency at hits (pp. 53 to 54). SDFs do not animate.
- **Rejected tracers** ([notes](../sources/2022_wright_lumen_siggraph_advances.md#rejected-designs)): hardware ray tracing alone (no scaling down for PCs without DXR and 60 fps consoles, and slow with overlapping instances; pp. 4, 32); software BVHs or grids (too slow for long incoherent rays; p. 38); voxel cone tracing and prefiltered cone tracing (leaks or over-occlusion that cannot be avoided, especially in coarse mips, and no hardware RT path; pp. 39, 139 to 141); ray marching voxel bit bricks (surprisingly slow, replaced by the global SDF; p. 39); irradiance fields (irradiance computed at the probe instead of the pixel, leaks and over-occlusion, hard placement, slow updates and a flat look; p. 143); per-pixel tracing with a screen-space denoiser (slow decorrelated rays and poor disocclusions; p. 144). Its documentation asks for walls at least 10 cm thick with software tracing ([related engine GI](related_engine_gi.md)).

### Brixelizer

AMD FidelityFX Brixelizer (GDC 2024; code in the FidelityFX SDK at tag `v1.1.4`, MIT, with C++ host, HLSL and Vulkan GLSL passes; later tags and `main` no longer contain it) builds a sparse distance field of the scene on the GPU and traces it in compute shaders with no hardware ray tracing ([notes](../sources/2024_amd_brixelizer_gi.md)). Its GI layer, a simplified GI-1.0, is in [related engine GI](related_engine_gi.md).

**Structure.**

- Cascades are clipmaps of 64³ voxels around a point, usually the camera, up to 24 of them; extent per axis is `64·voxel_size`.
- A voxel that touches geometry gets a brick of 8³ distance texels, stored in one shared 512³ `R8_UNORM` atlas (128 MiB, 2^18 brick slots addressed by an 18-bit brick ID). Empty voxels point to no brick.
- Each cascade has a 64³ brick map (1 MiB) and a 3-level AABB tree of 17,944 bytes: one bit-packed AABB per 4³ voxels at the bottom, 64 float AABBs above them, and a root. A bottom value of `0x7fff` marks an empty node. The size is 4096 bottom entries of 4 bytes, 64 float boxes of 24 bytes and a root of 24, `16,384 + 1,536 + 24` (derived).
- Texels hold distance in voxel units only near surfaces: anything beyond about 4/7 of a voxel stays at the cleared value 1, and a brick with no texel under 1/8 is freed. Brick texels are spaced 1/7 voxel apart so the outer texels sit on the voxel faces.
- Instances are static (kept) or dynamic (resubmitted every frame), up to 2^16.

**Building**, per update of one cascade:

1. Scroll: when the centre moves, the band of voxels that wrapped around is unset.
2. Voxelize: each triangle adds a reference to every voxel its bounds touch. Triangles smaller than 0.1 voxel are stored as a centroid (12 bytes), others as a vertex and two compressed edges (24 bytes).
3. Allocate a brick from the free list for each voxel with references, up to a per-update cap.
4. Emit the SDF: each brick texel takes the minimum exact distance to its triangles.
5. Compress into the atlas, recording each brick's tight AABB.
6. Build the cascade's AABB tree; static and dynamic cascades are merged texel by texel into a combined one.
7. At the end of the frame an Eikonal pass fills each new brick's unwritten texels: 512 threads per brick, an 8³ shared-memory copy, three sweeps with steps of 8, 4, 2 and 1 texels.

- The simple API updates one cascade per frame in the pattern 0 1 0 2 0 1 0 3, so cascade 0 refreshes every second frame and cascade 1 every fourth.
- Static cascades build only voxels that are still uninitialized, so they update incrementally; dynamic cascades are cleared and rebuilt from scratch each time they come up.
- Running out of brick, triangle or reference budget marks the voxel failed; what happens next is not documented. Storage is fixed at initialization (`FFX_BRIXELIZER_MAX_BRICKS_X8·sizeof(FfxUInt32x2)·9` for persistent GI resources, an SDF atlas of about 128 MB, 1 MB per cascade); brick IDs range from 0 to `2^18 − 1`; per-update limits (`maxBricksPerUpdate`, `maxBricksPerBake`, `triangleSwapSize`, `maxReferences`) can be tuned; counters report attempted and successful brick allocations per frame and failed voxel allocations (`g_scratch_voxel_allocation_fail_counter`); `FfxBrixelizerScanReferences` allocates bricks for referenced voxels with no overflow path described ([notes](../sources/2024_amd_brixelizer_gi.md#overflow)).
- Update cost grows with the number of triangles per cascade. Doubling the voxel size from 0.3 to 0.6 cut cost sharply; 0.6 to 0.9 helped little, since each voxel then covers more triangles.

**Tracing** (`FfxBrixelizerTraverseRaw` in the shared GPU header, used by both HLSL and GLSL):

1. Loop over cascades from the finest, skipping one that is disabled or does not contain the ray's current point.
2. Within a cascade, walk the AABB tree in 16-voxel and then 4-voxel steps, skipping empty nodes, with a budget of 32 iterations per cascade.
3. In a non-empty 4³ block, step voxel by voxel; a voxel whose brick is uninitialized aborts the cascade.
4. For a voxel with a brick, clip the ray to the brick's AABB and sphere trace at most 8 steps inside it. A hit is a sample under twice the epsilon; leaving the brick by more than 0.001 continues the walk.
5. On running out of iterations, back up one voxel and continue in the next coarser cascade.

- The hit returns only distance, brick ID and the position inside the brick; the normal comes from three one-sided differences toward the brick centre. The SDF surface sits slightly off the triangles, so rays need a push-off along the normal (scaled by voxel size and camera distance in the GI) and a `t_min` against self-hits.
- Against DXR on an RX 7900 XTX: faster for shadows in Flying World, even in Sponza, faster for short AO rays at voxel size 3.0, and much slower for long AO rays at voxel size 0.2 (graphs only, no numbers). Long and divergent rays cost the most.
- Problems of the field itself: it is approximate, so shadows and AO differ from triangle tracing, hard shadows soften as voxels grow, and coarse fields self-occlude without bias; alpha-tested foliage cards voxelize as solid quads, so grass over-darkens, and leaving them out removes leaf shadowing and leaves flickering gaps in the caches (AMD calls its foliage handling naive); small-scale detail is lost, and AMD suggests SSAO or SSGI on top.

### daGI2: narrow-band clips without bricks

Gaijin's daGI2 (Dagor Engine, BSD-3-Clause, `prog/gameLibs/daSDF/`) marches a signed distance clipmap with no hardware ray tracing ([notes](../sources/2026_gaijin_dagi2_dynamic_gi.md#world-sdf)); its probes and caches are in [related engine GI](related_engine_gi.md).

- **Layout.** Clip `i` has voxel size `0.15·2^i` m, 128 voxels wide and 64 tall, so clip 0 is 19.2 m wide and clip 4 is 307 m. One R8 3D texture holds every clip, each with a copy of its top and bottom slice so filtering wraps, addressed toroidally. Only a band of ±4 voxels is stored: value `a` decodes to `(2a − 1)·4` voxels, and empty space reads as +4 voxels. A clip is `128·128·64` bytes plus two border slices, 1.08 MB (derived, matching the stated "about 1.1 MB").
- **Build** for a scrolled region, with no jump flood: clear a 32-bit scratch buffer over the region plus one voxel; write candidate distances from geometry with `InterlockedMin`, the sign in bit 0 so that an unsigned minimum orders by magnitude; relax once over the 26 neighbours (each voxel takes the minimum of neighbour distance plus offset length; the code notes that more passes give a better field); write the result into the R8 clip and copy the border slices.
- **Geometry sources** are collision meshes, rasterized with a pixel shader below a voxel-size threshold and voxelized in compute above it. Each rasterized pixel writes its voxel and the six face neighbours with the exact distance to its triangle.
- **Updates from the depth buffer** keep moving objects and opened doors current without re-rasterizing. Marking: random depth pixels each write a 4×4×4 block of distances to the pixel's point, only lowering values, 12.5% of them into a coarser clip. Removal: random points along random view rays up to 128 m; if a voxel's band box lies wholly in front of the HZB on screen, its distance is raised.
- **Scrolling.** Clips snap to 2 voxels and rebuild only after moving 4. Only the newly exposed slab is rebuilt, coarsest clip first and at most one clip per frame.
- **Tracing** steps `max(d − 0.5·voxel, 0.25·voxel)`. A hit is `d` below a surface bias that grows from 0 to half a voxel over the first voxel of travel, so rays leaving a surface do not hit it. There is no step limit. A ray that leaves a clip starts in the next coarser clip one finer voxel back, because the coarse clip likely hits earlier. Normals come from 6 taps at ±0.5 voxel, and a soft-shadow variant uses `k = 8`.
- **Object SDFs.** daSDF also has an offline mesh-SDF baker and a sparse object atlas merged into the clipmap, but `HAS_OBJECT_SDF` is 0, so that path is compiled out.

## Hardware ray tracing

chandra, erhe, Dell'Ova, Gavras, Kaméus, tauray and the Unreal Split RC plugin trace with hardware ray queries or pipelines; their per-ray numbers are in [performance](performance.md) and the world-space and screen-space topics. In Godot 4.7.2 the ray tracing pipeline exists but is experimental: only Vulkan implements it, `SUPPORTS_RAY_QUERY` is always false so compute shaders cannot trace, `blas_create` fails for indexed geometry in release builds, the engine's mesh buffers cannot feed a BLAS, and push constants arrive as zeros in ray tracing stages ([RenderingDevice notes](../../docs/rendering_device.md#ray-tracing)). An RC trace there would be a raygen shader per texel writing to storage images, with the merge in compute (inference).

## Surfels

Love and Deepspace generates surfels per mesh asset from its lightmap UVs (about 10 cm, four LODs), stores them in local space, keeps them in a multi-level hash grid, and tests rays against disks in each grid cell they cross; on phones this beat software triangle BVHs. Gaps between surfels leak unless each surfel has a transparent outer ring that counts only when hit several times ([surface probes](3d_surface_probes.md#scene-representation)).

## Shading the hit

- **Emission only** (three-rc, Gavras, Dell'Ova, jumeder) gives a single bounce from emitters; lit surfaces bounce nothing.
- **Direct light at the hit:** shadow rays through the same structure (gomezzz for one point source, wroughtinator for the sun and a point light, erhe, HDDAGI's HDDA shadow rays), light injected into voxels ahead of time (Phreakyx, SDFGI's direct-light pass, HDDAGI's process list, HSGI and daGI2 below), or shadow maps (tauray).
- **Bounces:** read last frame's GI at the hit (gomezzz with `bounce_feedback` 0.65, wroughtinator two LODs coarser, X3XfRM from last frame's cascade 0, HDDAGI's lit cells adding `albedo·bounce_feedback` times their probes' irradiance). Each frame adds a bounce.
- **Materials:** gomezzz uses one constant albedo and emission per surface; Phreakyx multiplies the material colour by the texture's average; wroughtinator samples albedo at mip 2 because mip 0 made sub-pixel detail flicker.

### Lumen's surface cache

A distance-field hit has no UVs or material, so Lumen's hits read a cache of material and lighting stored on cards (p. 57; [notes](../sources/2022_wright_lumen_siggraph_advances.md#surface-cache), [cards](supporting_techniques_structures_and_tracing.md#surface-cache-cards)):

- Cards are axis-aligned projections picked at import by clustering surfels, 12 per mesh by default (docs), six around the bounds as a fallback and for skinned meshes. They live in a virtual 4096×4096 atlas of 128×128 pages, with low-resolution pages always resident and high-resolution pages requested by GPU feedback (pp. 60 to 67).
- Captures re-render mesh materials with Nanite at a budget of 512×512 texels per frame (p. 68). Direct light updates 1024×1024 texels per frame and indirect 512×512, ordered by `LastUsed − LastUpdated` with a radix sort (p. 74).
- Direct light: lights culled to 8×8 tiles, the first 8 per tile, a 1-bit shadow mask from shadow maps, and shadow rays only where maps cannot answer (p. 75).
- Indirect light: a 4×4 hemisphere probe per 4×4 texel tile, jittered over 4 frames, gathered from 4 probes with plane and hit-distance weights, and accumulated over at most 4 frames. Last frame's indirect feeds back, so bounces build up; it costs under one sixteenth of Lumen's budget (pp. 76 to 78).
- Rays that hit back faces return zero, so texels inside geometry stay black and filtering does not leak through walls (p. 73).
- The global SDF cannot tell which instance was hit, so it reads a coarse voxel lighting volume: 4 clipmaps of 64³ with radiance in 6 directions per voxel, 3 interpolated by normal (pp. 80 to 82), which the slides call too coarse.
- Weak points: missing card coverage (shown pink), no animation, a limited number of surface layers (p. 83).
- The 2022 notes add that the cache picks capture directions per mesh so every surface is covered, recaptures nearby meshes into its atlas as the player moves (Nanite speeds this up but is not required), and lights the cached surfaces with multi-bounce GI and shadowed skylight.

### Radiance at the hit from the lit frame

Two engines copy the lit screen into voxels so that off-screen hits have light without shading them ([daGI2 notes](../sources/2026_gaijin_dagi2_dynamic_gi.md#voxel-lit-scene), [HSGI notes](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md#filling-it)):

- **daGI2's voxel lit scene** stores the light leaving surfaces in 6 slots per voxel (± each axis, picked by the signs of the surface normal), at half the SDF resolution from SDF clip 1 up, so its finest voxel is 4 times the SDF clip 0 voxel, 0.6 m by default. Each frame takes `128 + 8192·speed` random pixels spread over screen tiles; each goes to the finest clip that holds it, or a coarser clip 12.5% of the time because coarse clips are seen less, and reads the pixel's final lit colour plus emission, which already includes GI, so bounces build up over frames. It blends into the three slots facing the normal with weight `0.05·` the normal's component, or replaces an empty slot. A stable mode averages 64 jittered taps on a disk half a voxel wide, keeping only taps in the same voxel, facing the same way and not on dynamic objects. Off screen, rasterized collision geometry is lit by a project callback (default `0.1·albedo`) and written with alpha 32/255, so screen updates soon outweigh it. At a ray hit the clips are read finest first, filtered radiance divided by filtered alpha, the three normal-facing slots weighted by the squared normal and their alpha; with no clip holding data, the albedo scene times the project's hit lighting is used. A shader gate stops lit-scene writes where the irradiance grid is not yet valid after a teleport, so a brief low-detail ambient does not get baked into voxels that outlast it, and the sample waits up to 24 frames for its scene data around the camera before updating radiance.
- **daGI2's albedo scene** is sparse: each clip is a toroidal window of 8×8×8-texel blocks, a uint per window cell points into a 256×256×N atlas, and free blocks sit on a LIFO stack with an atomic counter. A thread claims a cell by swapping in a token with compare-and-swap; other threads spin 32 times, then recover a stranded token. The atlas is sized for half the window by default. G-buffer samples blend in 5% at a time, and a background pass fills empty texels from their neighbours over 32 frames ([notes](../sources/2026_gaijin_dagi2_dynamic_gi.md#albedo-and-media-scenes)).
- **daGI2's media scene** is a dense RGBA16F volume per clip, in-scatter times density in rgb and density in alpha. 256 taps around a voxel measure how much translucent surface covers it, and `density = −log2(1 − coverage)/voxel_size`. Rays march it with exact in-scatter per step. The comments warn that 16×16 taps miss sparse leaves, so forests can leak skylight, and that canopies lit from below converge dark unless updates ignore small changes ([volumetric](volumetric_and_radiative_transfer.md)).
- **HSGI's screen injection:** one thread per voxel compares a point in the voxel with the depth buffer; in front of the depth it clears the voxel, behind it skips, and at the depth it writes the lit scene colour. To limit threads, tiles of 8×8×8 bricks are culled against the frustum with an update rate that drops with distance, then bricks are tested by their 8 corners. Moving and destroyed objects need no revoxelization while on screen.
- **HSGI's per-object voxelization** for off-screen geometry draws each object instanced along 3 axes with an orthographic projection, depth test off, using its material shader, optionally with forward lighting so the first bounce is present; a fake ambient sky initializes new voxels.
- **HSGI's light propagation (PC):** voxels store direct light (from analytic lights with culling) and indirect light (a hemisphere gather with RIS, accumulated over time), so the cache supports several bounces. Non-empty bricks in the near field (300 × 300 × 150 m) update over 9 frames and the far field over 121, with 16 threads per brick sampling its valid voxels, since a plane crossing a 4³ brick fills at least 16 of them.
- **HSGI's ray origins inside a voxel** are offset by the voxel radius along its normal, then a short hardware ray, one voxel long, is traced into the back hemisphere to find the actual surface; without a hit the surface is reconstructed from the voxel.

## Robustness

- **Rays starting inside solids:** gomezzz returns opaque black, which darkens probes near walls; genos-engine found that such a ray must not exit through the solid's far side, which painted lit faces onto back faces; Enshrouded pushes probes out along the SDF and kills probes whose summed ray distance is under 1 mm; erhe marks a probe as inside when more than 25% of 64 rays hit back faces. RCPG ignores back faces so that jittered origins inside geometry still pass through ([artifacts](artifacts_and_fixes.md#rays-starting-inside-geometry)).
- **Back faces:** erhe stores zero with β = 0 for a back-face hit; tauray culls back faces and returns black and opaque; Lumen's surface cache returns zero for back-face hits; gomezzz treats triangles as two-sided.
- **Small emitters** seen by one or two cascade 0 directions turn into fireflies; the analytic near-field terms that every builder adds are in [3D world space](3d_world_space.md#connections) and [sampling and guiding](rc_for_sampling_and_guiding.md#cascades-and-light-sampling).
- **Thin walls** thinner than one cell of whatever structure is traced will leak (creikey, SDFGI, EggyStudio). SDFGI is "mostly leak free" only for walls thicker than one voxel of the cascade that renders them, and HDDAGI seals one-voxel walls in the voxels but leaks at corners through its probes ([Godot integration](godot_integration.md)).
- **Hand-offs between tracers:** each tracer should resume from the distance the previous one reached. Lumen's screen trace steps back to its last unoccluded point when it goes behind a surface or off screen, and daGI2 restarts a ray one finer voxel back when it changes clip.
- **Surface offsets:** approximate fields sit off the triangles, so every SDF tracer needs a push-off and a minimum `t` (Brixelizer), or a bias that grows over the first voxel of travel (daGI2), or an expansion that grows with distance (Lumen).

## Where tracing time goes

Vasiou, Shkurko, Mallett, Brunvand and Yuksel ("A Detailed Study of Ray Tracing Performance: Render Time and Energy Cost", The Visual Computer, CGI 2018, DOI 10.1007/s00371-018-1532-8; author copy https://hwrt.cs.utah.edu/papers/rt_performance_CGI18.pdf) break down where path tracing spends time and energy ([notes](../sources/2018_vasiou_ray_tracing_performance.md)). Dell'Ova cites it for the hypothesis that dense RC probes hit memory-bandwidth limits; the paper's own claim is narrower: time and energy follow data movement, memory stalls and DRAM accesses dominate, and bandwidth is plotted (Fig. 6) but not used as the explanation. The results come from a cycle-accurate simulator of the TRaX architecture with USIMM for DRAM, not a commercial GPU, and the CPU comparison agrees only qualitatively (sec. 4.9).

- **Setup (sec. 3):** 32 multiprocessors of 32 thread processors (1024 threads) at 1 GHz on 65 nm; four shared 512 KB L2 caches of 16 banks; 8-channel GDDR5 at 8 GHz effective, 512 GB/s peak; area and latency from Cacti 6.5 and Synopsys DesignWare. CPU reference: Core i7-5960X (8 cores, 20 MB L3) at 500 spp, final render times only. Scenes at 1024×1024 with 0 to 9 bounces, 50 simulations: Crytek Sponza (262K triangles), Dragon Box (870K), Hairball (2.9M), San Miguel (10.5M); BVH with first-child traversal, Lambertian shading, one point light.
- **Time (Fig. 3):** Sponza is mostly compute once it fits in L2, with memory stalls mostly from L1 misses; in San Miguel, from one bounce on, memory data stalls take about 65% of the time. L1 hit rate drops from about 80% for primary rays to about 60% from two bounces on.
- **Kernels (Fig. 4):** generation and shading are negligible; trace dominates; shadow traces are about 20% faster. Trace stalls (Fig. 5) are substantial from the first bounces and nearly constant past the second, put down to incoherent rays thrashing the caches. Because the simulated memory system is already generous, more banks or capacity alone would gain little.
- **DRAM bandwidth (Fig. 6):** small, fast scenes use more, large scenes spread requests out, and all converge toward similar use; no numbers in the text.
- **Energy (Fig. 7):** Sponza at 9 bounces spends 80% on memory (60% DRAM) and 1 to 2% on compute; San Miguel 95% on memory (80% DRAM). A floating-point operation is about three orders of magnitude cheaper in energy than fetching its operand from DRAM. Shadow rays use about 15% less energy than other rays, and generation at most 2% (sec. 4.6). Energy per ray rises for incoherent secondary rays and levels off after about three bounces, with memory at 60 to 95% of traversal energy (sec. 4.7).
- **Contribution:** most of the image comes from the first few bounces; past the fourth or fifth, cost is large next to the contribution (sec. 4.8).
- **Conclusions (sec. 5-6):** memory dominates energy and latency even for scenes that fit in cache; compression reduces the bottleneck without removing it; adding memory resources alone does not help, so the authors point to memory-system redesign and streaming (dual streaming). Shading is Lambertian without textures, and hardware sensitivity is future work.

RC's coherent low cascades and incoherent high cascades map onto the paper's primary and secondary rays, which predicts that upper cascades cost more per ray than their step count suggests; Dell'Ova's dense-probe slowdown fits that reading but was not measured with counters (inference).

## Connections

- **Ray length picks the tracer.** Lumen's rejection of grids, the RC builds' grid beating H-PLOC, and Brixelizer's win on short rays and loss on long ones all fit one rule: empty-space-skipping fields and grids are fastest for short segments and BVHs or hardware RT for long, divergent rays. RC splits every ray into segments whose length grows ×2 to ×4 per cascade, so the natural pairing is a fine exact structure for the low cascades and coarse mips or a BVH for the long upper intervals (inference).
- **Mips are cones.** Per-cascade mips (DexRT, creikey), GigaVoxels' cone sampling at the footprint's level and Phreakyx's cone tracing are one operation, and they share the thin-wall failure that averaged occupancy causes and directional opacity or variance-limited mips fix ([volumetric](volumetric_and_radiative_transfer.md#marching-on-mips)) (inference).
- **One HDDA family.** Museth's HDDA in DexRT, lfyGRW's bitmask DDA, HDDAGI's integer walk and HSGI's GVDB bits all skip empty blocks by occupancy at several levels. They are exact where sphere tracing is approximate: no surface offset, no thin-wall miss, an exact cell (inference).
- **Narrow bands everywhere.** Lumen (±4 voxels in a byte), daGI2 (±4 voxels in R8) and Brixelizer (distances beyond about 4/7 voxel cleared) all store distance only near surfaces and let a coarser structure (coarse mip, AABB tree, coarser clip) skip the rest. A narrow band plus a skip structure is a hierarchical DDA with sphere tracing at the leaves (inference).
- **Screen data keeps the world current.** daGI2's depth marking and removal, its lit-scene sampling, HSGI's screen injection and Lumen's screen traces all use the frame's depth and colour to update a world structure, so moving and destroyed objects need no revoxelization while visible. RC's screen-space cascade −1 or SSRC near field is the same split between a current screen layer and a world layer ([3D screen space](3d_screen_space.md#hybrids)) (inference).
- **Distance cube maps are probe-local tracing.** Umenhoffer's layered distance maps, DDGI's and light field probes' octahedral distance maps, and RC's stored hit distances all let a ray be resolved near a probe from that probe's own data ([related probe GI](related_probe_gi.md)) (inference).
- **Streaming follows intervals.** GigaVoxels' rays request data at the resolution they need, and RC's interval structure states that resolution per cascade in advance (inference).

## Single-frame assessment

- **Scene caches are compatible, lighting caches are not.** A single-frame GI may keep a scene structure across frames, since static geometry's distance field or BVH is a function of the scene, not of past lighting. Lighting stored at hits over frames is temporal accumulation: Lumen's surface cache (indirect over 4 frames, last frame's indirect fed back), daGI2's lit scene (5% blends of frames that already contain GI), HSGI's indirect voxels (RIS accumulated over time, 9 and 121 frame update cycles) and HDDAGI's bounce feedback all carry history. A single-frame design shades each hit in the frame it is traced, from emission, direct light by shadow ray or shadow map, and, for a second bounce, a second solve (inference).
- **Dynamic geometry must enter the same frame.** Incremental updates lag: Brixelizer refreshes cascade 0 every second frame and cascade 1 every fourth, daGI2 marks moving objects from random depth pixels and rebuilds one clip per frame, EggyStudio waits 8 still frames before adding a mesh. A single-frame design needs a per-frame structure for moving objects: Wicked Engine's full GPU BVH rebuild, a small dynamic-only TLAS capped by the static hit distance (the sparse-build proposal), creikey's per-frame dynamic clipmap, or screen-space marking of the visible part in the same frame (inference).
- **Compute-only routes exist for every family.** Under Godot's `RenderingDevice`, distance fields build with JFA (510 million reads per 128³ rebuild with JFA+2, derived) or from triangles with 32-bit `InterlockedMin`; HDDA bitmasks need only 32-bit words; Wicked's GPU LBVH needs integer atomics and indirect dispatch, both supported; tinybvh's GLSL kernels run as written once segment limits and any-hit exits are added. Only hardware tracing is restricted, to the experimental Vulkan pipeline ([RenderingDevice notes](../../docs/rendering_device.md)) (inference).
- **Exact visibility near, coarse far.** Cascade 0 decides contact shadows and leaks, so it needs an exact or near-exact structure (triangles, an HDDA over fine bits, or the depth buffer for a screen near field). Upper cascades can read coarse mips with directional opacity at a fraction of the cost, which is DexRT's 8× (inference, from the measured mip speedups and the thin-wall leaks of averaged data).
- **Software tracing cost is rays per second in compute.** The available figures for software tracing are tinybvh's 2.8 G primary rays per second (BVH2, RTX 5080 laptop), creikey's 14.3 G rays per second for a synthetic voxel trace (GPU not named) and the 3.5 to 4× software penalty against hardware RT. None was measured in GLSL under Godot's `RenderingDevice`, so no tracer there has a direct throughput figure (inference).

## Open questions

- Which pairing gives the best single-frame quality per millisecond: a triangle BVH for cascades 0 and 1 with voxel mips above, an HDDA over bitmasks for all cascades, or a narrow-band SDF with a skip structure?
- Can a per-frame GPU LBVH (Wicked Engine's four passes) build and trace a typical Godot scene within 1 to 2 ms on mid-range hardware, and how does BVH2 traversal in GLSL compare with an HDDA at RC's segment lengths?
- How thin can walls be before each structure leaks at cascade 0, and do six-direction opacity mips keep upper cascades leak-free in one frame?
- What is the cheapest same-frame hit shading that does not carry history: shadow maps sampled at hits, one shadow ray per hit, or a light injected into voxels each frame from the current shadow maps?
- Can screen-space marking and removal of the visible depth (daGI2's scheme) run every frame over the whole screen, so that visible moving objects enter the world structure without lag?
- Does a narrow band of ±4 voxels in 8 bits keep enough precision for RC's short cascade 0 segments, or does cascade 0 need a finer field near the camera?
- How much of a dense 128³ to 256³ occupancy or distance volume fits Godot's storage-buffer and texture limits once cascades, probes and the scene share the GPU?
