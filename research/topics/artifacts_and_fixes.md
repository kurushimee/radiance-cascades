# Artifacts and fixes

Most RC artifacts come from one fact: a lower probe merges with upper probes that sit somewhere else, so the upper intervals start at different points and look at the scene from different angles. This note lists each artifact, its cause, and the fixes that implementations use, with their costs. Theory is in [core_theory.md](core_theory.md).

## Ringing

Bright rings around small, bright sources in open space, at the distances where one cascade hands off to the next. They show most clearly after colors are converted to linear space.

**Cause: parallax.** A lower probe blends four upper probes. Each upper probe's interval starts at its own position, so it sees the source at a slightly different angle. The lower probe's own occlusion does not line up with what an offset upper probe sees, so an upper probe can add an unoccluded copy of the source (double counting) or miss part of it (a gap that leaks). Energy is not conserved where a cascade boundary crosses a source. Osborne and Sannikov measured just over 10% error in the worst case (a tiny, very opaque source in vacuum) and a few percent in practice.

### Fixes

| Fix | What it does | Cost | Sources |
|---|---|---|---|
| **Bilinear fix** | For each of the four upper probes, trace the lower interval from its own start to that upper probe's interval start (`probe + d·t_start` → `upper + d·t_end`), merge with that probe, then blend the four results bilinearly. Rays bend slightly toward each upper probe. | 4× the traced rays on every cascade except the top | Osborne and Sannikov 2024 (appendix A), LegitCascades `Scaling.ls`, Suslik testbed (default), GM Shaders `BilinearFix` branch, Gigi |
| **Forking fix** | Start each ray at `probe + d_parent·t_start`, where `d_parent` is the center of the coarser bin that contains it, so four child rays fork from the end of their parent. Usually paired with the bilinear fix. | Free | Mytino diagram 4clcWn, GM Shaders |
| **Nearest fix** | Reproject only to the nearest upper probe (`floor(p/2)`). | 1× rays, but 2×2 blocks of lower probes share an upper probe, so results look pixelated | GM Shaders `NearestFix` |
| **Interlaced fix** | Pick one of the four upper probes per lower probe by `(2·px + py) mod 4`. | 1× rays, dithered look | GM Shaders `InterlacedFix` |
| **Parallax fix** | Keep the ray at the lower probe but, per upper probe, interpolate the direction that upper probe would need to see the same point, with intervals stretched by 1.1 for overlap. | Extra direction lookups | mxcop Shadertoy XcfyDj, Osborne figure 8, Suslik testbed |
| **Chronicl fix** | Keep rays straight: intersect the lower ray with a circle of radius `t_end` around each upper probe, march to that exit point, and interpolate the upper probe's two nearest directions toward it. Shows a checkerboard on cascades 0 and 1, so those keep the bilinear fix. | Like the bilinear fix, with straight rays | LegitCascades `ChroniclFix.ls` |
| **Dolkar (mask) fix** | Mask upper probes by hit distance before blending. | Small | Suslik testbed `MERGE_FIX = 3` |
| **Midpoint fix** | Split each bilinear-fix ray at a midpoint. | As bilinear fix | Suslik testbed |

The bilinear fix is the standard. It also removes light leaking through occluders thinner than the probe spacing. jason.today notes known fixes roughly double frame time; DexRT did not need the fix for its data. Unverified 2D tests put the parallax fix at about 20% over vanilla and nearest merging with forking at about a quarter of the bilinear fix's cost; forking alone showed no measurable gain in one test and lowers angular resolution. The cheaper variants and their costs, including two-tap diagonal merging, stochastic and temporal bilinear fixes, gear-tooth intervals and an interior mask, are listed in the [merging notes](../sources/2026_merging_and_ringing.md).

In 3D, an exact bilinear fix needs 8 rays per lower ray. Split RC sidesteps it by splitting rays at their hit distance, and screen-space designs mostly rely on depth-aware weights instead (see [3d_screen_space.md](3d_screen_space.md)).

## Gaps and seams between cascades

- **Interval gaps:** if cascade 0's interval is too long relative to its spacing, segments of neighboring cascades do not meet and thin occluders fall between them. Shorten `i0` until they connect.
- **Overlap:** extend each interval past the next cascade's start. GM Shaders adds the upper probe spacing diagonal, `√2·s0·2^(c+1)`, to each range ("light-leak term"); the community demo scales lengths by `1 + 3·overlap` with overlap 0.1; jason.today uses 0.04. The forking fix replaces the overlap term in GM Shaders.
- **Cross-fade:** Suslik's mlSfRD extends each interval by half a fade length at both ends and fades hits near the ends toward empty, so neighboring cascades blend instead of meeting at a hard edge.
- **Cascade −1:** a per-pixel trace of `[0, i0]` in front of interpolated cascade 0 recovers contact shadows and detail finer than the cascade 0 grid. It behaves like a bilinear fix with one cascade 0 ray and adds no ringing, so cascade 0 probes every 2 px gave the quality of one per pixel in 2D tests ([merging notes](../sources/2026_merging_and_ringing.md)).

## Grid and blocky penumbras

Merging with only the nearest upper probe shows the probe grid. Bilinear blending of four upper probes (or the direction-first hardware fetch) fixes it. In jason.today the grid appeared until the render targets used linear filtering. A wider 3×3 distance-weighted merge kernel removes the remaining blocks at shadow edges, but it averages across walls and leaks more light, and cost 54% more merge time in a 2D test ([Peter](../sources/2026_peter_rc_2d_bachelor_thesis.md)).

## Light leaks

- **Merge reads across tiles:** a hardware-filtered fetch near the edge of a direction tile blends in a neighboring direction. Clamp the coordinate at least half a texel inside the tile (jason.today used 1 texel in its final code).
- **Spacing too coarse for the occluders:** walls thinner than cascade 0's probe spacing let light through, because the penumbra condition is violated. The bilinear fix helps; otherwise make the base grid finer.
- **Thin walls in the traced structure:** a distance field sampled on either side of a wall thinner than a voxel may never cross zero. Lumen expands surfaces by half a voxel at trace time, starting from zero at the ray origin so contact shadows survive ([Lumen](../sources/2022_wright_lumen_siggraph_advances.md)).
- **Coarse cascades of the scene structure:** Godot's HDDAGI leaked at the default 0.2 cell size because rays reached the third voxel cascade within a short distance; 0.03 cells with 5 cascades removed it ([HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md)).
- **Filtered reads at a ray's far end:** a ray that stops short of a wall and reads a probe grid at its end point filters in probes behind the wall. daGI2 pulls that read back along the ray, by half a grid probe for screen probes and √3 coarser probes for its grid. Its todo list also records that large lit-scene voxels leak more than the SDF plus albedo, so it caps the number of lit clips, and that sparse foliage under-sampled into its media volume lets forests leak skylight ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).
- **Sparse trilinear interpolation:** interpolating with an upper probe behind a 2 to 3 voxel wall leaks. Interpolating with a parent neighbor only when the nearest child rays in that direction were unoccluded, using one hit/miss bit per ray, removed it at about 50% more merge time ([sparse 3D notes](../sources/2026_sparse_and_3d_rc.md)).
- **Averaged volume mips:** 2×2×2 averaging halves a thin wall's opacity at each level, so cone-traced or mip-marched cascades leak; six-direction opacity per voxel fixes it ([volumetric notes](../sources/2026_volumetric_rc.md)).
- **3D grids and surfels:** probes inside or behind walls interpolate light from the other side. World-space designs add visibility weights (DDGI-style moments), probe relocation, normal offsets, or hit-distance masks. See [3d_world_space.md](3d_world_space.md) and [related_techniques.md](related_techniques.md).

## Domain edges

Lookups past the outermost probe row clamp, which flattens falloff near the border (Osborne). Screens get dark edges when the top interval does not reach the diagonal; add a cascade or extend the top interval to the domain edge. jason.today added one extra cascade for this.

## Sky aliasing

Point-sampling a small sun in the top cascade's coarse bins gives banding and stepped shadows. Integrate the sky over each bin instead (fad's formula in [core_theory.md](core_theory.md); Youssef-Afella uses the same).

## Dark-scene banding

Very dark scenes band visibly in 8-bit output. Valve-style animated dithering fixed it in one 2D game ([discussions](../sources/2026_rc_discussions.md)). Store cascades in at least RGBA16F (R11G11B10F works for radiance without alpha). Jump-flood and distance textures also need 16 bits: 8-bit ones cannot hold positions beyond 256 and report false hits 1 to 2 px from surfaces ([merging notes](../sources/2026_merging_and_ringing.md)).

## Sharp shadows

RC blurs shadows from small, distant lights because the cascade that sees the occluder has coarse spacing. More cascade 0 resolution helps only near the occluder. HRC fixes this in 2D by keeping full probe resolution across the travel direction ([HRC](../sources/2025_freeman_holographic_radiance_cascades.md)), at `O(N⁴)` memory in 3D. Lights smaller than about 8 base probes still alias in HRC. HRC's own artifacts, a checkerboard, crosses around small emitters and striations from even-plane merging, and their fixes are in the [HRC notes](../sources/2026_holographic_rc.md).

## Rays starting inside geometry

A ray whose interval starts inside a solid returns that solid's emission at once (fad) or nothing (GM Shaders, for cascades above 0, since 2D lights emit from their surface). Pick one rule; returning the emission double counts thick emitters.

## Base ray counts other than 4

jason.today saw much worse artifacts at base 16 and added an unexplained interval multiplier (`√base`). The community demo carries the same "hand-wavy" rule. Stay with 4 directions per step in 2D unless the intervals are retuned.

## Color drift in packed formats

GPUs truncate when writing R11G11B10F (and RGB9E5), and over many temporal blends the bias tints the image yellow (blue for RGB9E5). daGI2 rounds each channel before the write and stores its screen GI as squared color in half floats for the same reason ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).

## Temporal latency and flicker

Merging against last frame's upper cascade (Shadertoy, LegitScript, temporal surface RC) delays changes by one frame per cascade and can flicker. Updating each cascade at its own frame rate (CptNemo0's cached variant, Brixelizer's 0 1 0 2 0 1 0 3 order) trades latency in the far cascades for cost. Separate passes per cascade avoid it in 2D. In 3D, nearly every design accumulates over frames, so history rejection and hysteresis matter; see [3d_world_space.md](3d_world_space.md) and [3d_screen_space.md](3d_screen_space.md).
