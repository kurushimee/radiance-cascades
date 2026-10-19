# Cascaded light propagation volumes and irradiance volumes

| | |
|---|---|
| Paper | Anton Kaplanyan (Crytek) and Carsten Dachsbacher (VISUS, University of Stuttgart), "Cascaded Light Propagation Volumes for Real-Time Indirect Illumination", I3D 2010, pp. 99-107 (doi 10.1145/1730804.1730821) |
| Copy read | https://cg.ivd.kit.edu/publications/p2010/CLPVFRII_Kaplanyan_2010/CLPVFRII_Kaplanyan_2010.pdf (author copy, 9 pages; equations and Table 1 read from rendered pages) |
| Background | Greger, Shirley, Hubbard and Greenberg, "The Irradiance Volume", IEEE CG&A 18(2):32-43, 1998 (doi 10.1109/38.656788) |

Light propagation volumes (LPVs) inject reflective-shadow-map lights into a coarse grid of low-order spherical harmonics and spread the light cell to cell, all in one frame. They are the propagation member of the probe family and shipped in CryENGINE 3. Section numbers are the paper's; page numbers were not printed in the copy.

## Injection (sec. 3.1, 6)

- Each light renders a reflective shadow map (RSM) of depth (32-bit float) plus normals and flux (RGBA8 each), 256² on PC and 128² on consoles, so each texel is one virtual point light (VPL), 2^16 or 2^14 per light. Environment maps inject VPLs into the outer grids.
- A VPL is a clamped-cosine lobe around its normal, projected into SH and scaled by its flux (which already accounts for the surface area it stands for). It is moved half a cell along its normal before its cell is chosen, which avoids self-lighting. RGB uses three coefficient vectors.
- The implementation uses 2 SH bands (4 coefficients) per colour channel, stored in three RGBA16F 32³ textures per grid (QUVW8, 8-bit signed per component, on consoles). VPLs are injected by point rendering, with vertex texture fetch (DirectX 9 and 10, Xbox 360) or render-to-vertex-buffer (faster on PS3).

## Geometry volume (sec. 3.2, 3.3)

- Blocking comes from a second grid, the geometry volume (GV): surfels from the camera's depth and normal buffers (down-sampled) and from the RSMs, each with blocking potential `B(ω) = A_s/s²·⟨n_s, ω⟩₊` for area `A_s`, normal `n_s` and cell size `s`, projected into SH. Per-buffer GVs merge by a maximum over SH vectors; static surfels from earlier frames can be reused, with care not to accumulate their blocking twice.
- The GV is offset by half a cell so its centres sit on LPV cell corners, and propagation reads it bilinearly at the face it crosses. The first propagation step skips occlusion to avoid self-shadowing.
- A cell assumes its surfaces do not occlude each other, and surfaces smaller than a cell (foliage) cast no resolved shadows.

## Propagation (sec. 3.3, 6)

- A cell gathers from its 6 axial neighbours (4 in 2D), against 26 (8 in 2D) for an 8-direction discrete ordinates method (DOM8). For each face of the destination cell, the solid angle `Δω_f = ∫_Ω V(ω) dω` and central direction `ω_c` of the visibility cone give the flux `Φ_f = Δω_f/(4π)·I(ω_c)`, taking the intensity in `ω_c` as the average over the solid angle. Projected transfer vectors were rejected as too inaccurate at low SH order.
- **Reprojection:** the flux on each face becomes a new clamped-cosine point light at the destination centre emitting the same total flux, `Φ_f = ∫_Ω Φ_l⟨n_l, ω⟩₊ dω`, so `Φ_l = Φ_f/π`; its scaled lobe is accumulated into the destination's SH for the next iteration. Each iteration's output accumulates into a separate grid, and propagation conserves energy in vacuum, though propagation and reprojection add spatial and directional discretization, as in all lattice methods.
- Ping-pong rendering: every cell in every cascade looks up its 6 neighbours, computes face fluxes, reprojects and accumulates. Most scenes used 8 iterations, which limits how far light travels and can show artifacts in large sparse scenes; iterating twice the LPV's longest side would be correct but too slow.
- In flatland the scheme preserves main directions better than DOM4 and produces no ray effects at higher SH orders, where DOM4 does; DOM8 keeps the distribution much better. The scheme suits 2 to 4 SH bands and lights larger than a cell.
- **Multiple bounces:** an extra GV lookup one cell ahead along the propagation direction gives a blocker approximation `B(ω)`; its diffuse illumination `B(−ω_c)` scaled by the propagated intensity and reflectivity is injected back, for about 0.3 ms more on a GTX 285 (32³, 8 iterations). The examples use monochrome reflectivity for later bounces, since spectral reflectivity would triple GV memory.

## Lookup (sec. 3.4)

- The accumulated iterations are read with a trilinear SH lookup, evaluated for the negative surface orientation "similar to irradiance volumes [Greger et al. 1998; Oat 2006]", and intensity is converted to incident radiance assuming the surface lies half a cell from the cell centre.
- Coarse volumes self-illuminate and bleed; a damping factor reduces this: when the directional derivative of the SH coefficients along the normal (by differencing) is large and disagrees with the coefficients, the coefficients are damped before lighting.
- **Glossy reflections** march the LPV along the reflection direction, averaging `I(−r)` divided by the squared distance over the cells passed, which reads light before it is smeared further; 4 cells sufficed. Participating media are single-scattered by ray marching the LPV.

## Cascades (sec. 4)

- Three nested 32³ grids move with the viewer, displaced along the view direction so more of each grid lies in front of the camera, and snapped to multiples of their cell size ("one-cell grid snapping") so VPL and geometry injection stay consistent as they move. VPLs and geometry go into all grids at once, and propagation runs per grid; a lookup uses the finest grid that holds the point and blends into the next at its border.
- The teaser gives "50, 25 and 12.5 meters grid spacing" for a Sponza of about 37 × 15 × 22 m; for a 37 m scene these read as grid extents, which makes cells 1.56, 0.78 and 0.39 m and an 8-iteration reach of 12.5, 6.25 and 3.1 m (derived, inference on the meaning).
- Objects smaller than a grid's cell inject no VPLs into it, and small moving objects make light unsteady, so their contribution is faded out.

## Results (sec. 6, 7)

| Stage (ms, one 32³ grid, 8 iterations, 1280×720) | GTX 285 | Xbox 360 | PS3 |
|---|---|---|---|
| RSM rendering | 0.16 | 0.5 | 0.8 |
| VPL injection | 0.05 | 0.2 | 0.4 |
| GV injection | 0.02 | 0.15 | 0.15 |
| Propagation (no occlusion / fuzzy occlusion / fuzzy occlusion and bounces) | 0.8 / 1.1 / 1.4 | 0.8 / 1.1 / 1.5 | 0.7 / 1.1 / 1.5 |
| LPV lookup | 2.4 | 2.0 | 1.5 |
| Total | 3.4 / 3.7 / 4.0 | 3.5 / 3.8 / 4.2 | 3.4 / 3.8 / 4.2 |

- RSM 256² (VPLs) on the GTX 285 and 128² on consoles; only RSM rendering depends on scene complexity.
- Crytek Sponza (262k triangles) with 3 cascades: 58 fps on a GTX 285 at 1280×720, about 10 ms for indirect light; ray-marched single scattering adds about 18 ms (34 fps). With 3 cascades at 60 fps against a PBRT photon-mapping reference (single bounce, 200,000 photons, 1024 final-gather samples, about 45 minutes) and Imperfect Shadow Maps at 15.6 fps. One 32³ LPV: 130 fps without occlusion, 90 with fuzzy occlusion, 85 with multiple bounces.
- Memory with ping-pong targets: `32³·(2·4)·3·(cascades + 2)` = 3.75 MB for the LPV and `32³·(2·4)·cascades` = 0.75 MB for the GV, halved on consoles.

## Limitations (sec. 1, 3, 7)

- Low-frequency, diffuse indirect light only, primarily one bounce; surface detail comes from bump mapping and SSAO.
- Spatial discretization bleeds light through thin geometry (a shelf in Fig. 11), and small blockers' shadows go missing; cascades reduce this.
- SH and propagation diffuse light, so glossy surfaces cannot be handled by propagation.
- Low RSM resolution flickers; cost is linear in iterations and cells.

## Irradiance volumes (Greger et al. 1998)

The full text of "The Irradiance Volume" could not be read: the Cornell pages and PDF returned 403 or timed out, the IEEE and DOI routes returned empty shells or reset connections, and no other copy turned up (2026-10). What is known from secondary sources: it extends irradiance to all points and directions in space for scenes that overwhelm conventional GI (abstract excerpt), and it discretizes a 5D function of position and direction, which at the time meant static scenes, precomputation and interpolation (LIRIS GDL talk, [non-English overviews](2025_non_english_rc_overviews.md)). The LPV lookup above is described as similar to it.
