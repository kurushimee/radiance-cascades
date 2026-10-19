# HSGI: cross-platform hierarchical surfel GI (GDC 2023)

| | |
|---|---|
| Title | HSGI: Cross-Platform Hierarchical Surfel Global Illumination |
| Authors | LIGHTSPEED STUDIOS (Tencent): Minmin Gong, Junfeng Li, Wei Lan, Yucong Pan, Kai Dai, Jiaqi Guo, Mali Liu, Lihua Li and others; slides filed under Jiaxuan Zhang |
| Venue | GDC 2023 |
| Slides | https://media.gdcvault.com/gdc2023/Slides/HSGI+Cross-Platform_Jiaxuan_Zhang.pdf (90 pages) |

Not RC. HSGI is a dynamic GI for huge open worlds with moving geometry, running on PC, consoles and phones. Its "surfels" are voxels with a normal, held in a sparse brick clipmap and traced with a hierarchical DDA, the same structure as Godot's HDDAGI. It matters here for three things an RC build in Godot also needs: a voxel radiance cache filled from the lit screen, a cheap per-object voxelization by rasterization, and a measured mobile budget.

## Voxel radiance cache

- Bricks of 4³ voxels in a sparse clipmap, addressed like a virtual texture: a dense "hierarchy link" grid holds a brick ID per allocated brick (zero otherwise), a pool indexed by brick ID holds the voxel data, and an allocator tracks free IDs.
- Per voxel: diffuse color, direct and indirect outgoing radiance, normal, alpha, an age weight and masks. 128 bits in 4 textures on PC, 64 bits in 2 textures on mobile.
- Range: 100+ m on mobile, 500+ m on PC.
- Camera motion uses toroidal addressing: only the wrapped band is cleared, by a flag per voxel or brick.
- Tracing follows GVDB: 1 bit of occupancy per voxel, read 64 bits per fetch, with the sparse mip 0 trading trace speed for memory.

## Filling it

- **Screen injection:** one thread per voxel compares a point in the voxel with the depth buffer. In front of the depth it clears the voxel, behind it skips, and at the depth it writes the lit scene color. To limit threads, tiles of 8×8×8 bricks are culled against the frustum with an update rate that drops with distance, then bricks are tested by their 8 corners.
- **Per-object voxelization** for geometry off screen: draw each object instanced along 3 axes with an orthographic projection, depth test off, using its material shader, optionally with forward lighting so the first bounce is present. A fake ambient sky initializes new voxels.
- **Light propagation (PC):** the voxels store direct light (from analytic lights with culling) and indirect light (a hemisphere gather with RIS, accumulated over time), so the cache supports several bounces. Work is amortized: non-empty bricks in the near field (300 × 300 × 150 m) update over 9 frames and the far field over 121, with 16 threads per brick sampling its valid voxels, since a plane crossing a 4³ brick fills at least 16 of them.
- **Ray origins inside a voxel:** offset by the voxel radius along its normal, then trace a short hardware ray, one voxel long, into the back hemisphere to find the actual surface; without a hit, reconstruct the surface from the voxel.

## Mobile path

1 spp tracing per pixel was too slow on phones, so mobile uses probes:

- A DDGI-style probe volume: ambient cube irradiance, VSM visibility and relocation per probe, 2 clipmap LODs (4 on PC). Only probes near surfaces, found through the voxel hierarchy, update; each frame one random face of each traces one ray.
- Gathering 8 probes per pixel in the forward pass was too costly, so indirect light moved to deferred **screen probes**: the screen is split into 64×64-pixel tiles with one jittered probe each, storing a 4×4 hemisphere octahedral tile, with visibility rays in place of VSM.
- Probes are gathered at half resolution with depth and normal tests, accumulated over time, and upsampled with a bilateral filter. A tile where all four probes fail gets an extra probe the next frame.
- One extra G-buffer target (RGB8 diffuse plus an 8-bit hemisphere normal in view space, dithered before encoding) makes this work in a lite deferred pass.
- Without a velocity buffer, one bit of the diffuse color masks dynamic objects: they read the 3D probes directly, screen probes are generated before they are drawn, and history marked dynamic is discarded.
- iPhone 13 Pro (A15): 3.18 ms per frame in all. Gathering screen probes takes 1.07 ms, indirect lighting 1.00, injection 0.33, and generating screen probes 0.08; structure and volume updates take the rest. The base pass dropped from 2.20 to 1.88 ms. On frames when the clipmap shifts or objects are voxelized, another 1.79 ms is added, mostly shifting the hierarchy (1.51).

## PC and console path

- Rays use screen traces (Hi-Z), then HDDA voxels or hardware RT, and read radiance from the scene color, the voxels or a probe.
- Diffuse GI runs ReSTIR GI at half resolution. One visibility ray after spatial reuse restores indirect shadows that visibility-free reuse washes out, and neighbors are reused only when their shadow state matches. Shading samples 3×3 to 7×7 neighbor reservoirs to cut color noise.
- **Trace-probe mode:** for scenes with 4 or more important bounces or small bright lights, rays go only as far as one probe size and then read a 6×6 octahedral probe, trading detail for stability, switchable per area.
- Reflections below roughness 0.4 trace; rougher ones reuse the diffuse result, and above 0.8 they blend to diffuse GI.
- RTX 3080, 4K output via TSR from 1932×1084, GI traced at 966×542: HSGI's GI passes took 8.53 ms (73.48 fps) against 9.63 ms for UE5 Lumen (59.62 fps), with RMSE against a path tracer of 29.36 against 32.12. No source states the RMSE's units, value range or tone mapping: the GDC Vault page ("HSGI: Cross-Platform Hierarchical Surfel Global Illumination", Jiancong Huang and Jiaxuan Zhang) has only an abstract, no paper or preprint exists, and the Chalmers thesis sometimes linked with it is Ekberg's 2022 reimplementation of GIBS. Of HSGI's 8.53 ms, diffuse denoising was the largest pass at 2.65 ms against 0.64 ms for diffuse tracing; a pass labeled "Ray Tracing Scene" took 2.14 ms (4.90 in UE5), light propagation 0.33 and screen injection 0.15.
- Hardware RT is optional on every path.
