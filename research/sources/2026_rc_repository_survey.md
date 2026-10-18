# RC repositories surveyed in 2026

About 55 public repositories found by searching GitHub for radiance cascades, read at their October 2026 heads without building or running them. Most are 2D implementations of the standard scheme, so this note lists only what departs from it or carries a measurement. The standard scheme here means probe spacing ×2 and directions ×4 per cascade, geometric intervals, a top-down merge, and a jump-flood distance field.

## 3D

| Repository | Design | Notes |
|---|---|---|
| [yhyu13/radiance-cascades-demo](https://github.com/yhyu13/radiance-cascades-demo) (`3d/`, MIT) | probes on surface charts | see below |
| [SultanAladin/RadianceCascades](https://github.com/SultanAladin/RadianceCascades) | world probe grids, Vulkan GLSL compute | octahedral direction tiles per probe; 8-probe trilinear merge that samples each upper probe along the direction toward the lower interval's end (a 3D bilinear fix); octahedral tiles filtered by hand so they do not bleed; sparse SDF bricks with brick skipping, 64 steps; shades the nearest hit across SDF instances with per-instance albedo |
| [KingTheFifth/radiance-cascades](https://github.com/KingTheFifth/radiance-cascades) | screen probes lifted by depth | world-space intervals traced through voxels or Hi-Z; direction-first layout |
| [mpalenque/sim](https://github.com/mpalenque/sim) | world probe grid in three.js | spacing ×2 and octahedral directions ×4 per level, intervals `base·(4^i − 1)/3` to `base·(4^(i+1) − 1)/3`, cone tangent `2/√dirs`, 8-corner merge; cascade 0 resolves into an SH volume |

### Surface-chart RC (yhyu13)

Probes live on the UV charts of a Cornell box, so each surface's cascades stay a 2D problem on its chart, as in [X3XfRM](2024_suslik_x3xfrm_surface_probe_rc.md).

- 8 charts (floor and ceiling 256×256 texels, walls and two interior boxes 128×256), texel scale 1/256 unit, 6 cascades in one 1024×512 RGBA32F atlas each, double buffered: 100.7 MB in all.
- Cascade `c` uses probes of `2^(c+1)` texels with one direction per texel, direction-first. Directions follow square rings: ring `i` has `4 + 8i` bins, polar angle from the ring and azimuth around it. Each direction is weighted by its solid angle times `cos θ`.
- The interval is `probeSize/32` units; the last cascade reaches 10000. Rays are traced analytically against quads, boxes, a cylinder and a mirror sphere, with one sun shadow ray at each diffuse hit.
- The merge blends 4 upper probes bilinearly. An upper sample counts only if it hit nothing or the lower probe lies inside its cone at the hit distance, a cheap visibility test. A miss uses the upper value alone.
- Bounce: a hit reads last frame's cascade 0 at its chart texel, so each frame adds a bounce.
- RTX 2080 SUPER, RenderDoc replay: 28.6 ms for all cascades on the full atlas, 5.95 ms once padding texels were skipped. The repository warns that replay timings vary 2 to 5×. Its earlier 128³ volume RC took about 37.7 ms.

## 2D variants worth knowing

| Repository | What differs |
|---|---|
| [Sky-Meteor/RadianceCascades](https://github.com/Sky-Meteor/RadianceCascades) (Terraria mod) | visibility-aware bilinear merge: a far probe counts only if the segment from the near probe to it is unoccluded; transmittance `*= sqrt(alpha)` per sample |
| [bjorn-johansson/radiance-cascades](https://github.com/bjorn-johansson/radiance-cascades) | DDA over a bitmap instead of a distance field; Beer-Lambert absorption per cell, about 0.2 ms extra at 6 cascades |
| [routersys/YMM4-Radiance](https://github.com/routersys/YMM4-Radiance) | 9-level occupancy pyramid for empty-space skipping during the march; absorption |
| [ryandugie/BevyRadianceCascades](https://github.com/ryandugie/BevyRadianceCascades) | switchable fixes: none, interval overlap of `√2·Δp(n+1)`, or bilinear fix with 4× rays; sun and sky injected at the top cascade only; README claims 0.82 ms |
| [Qonfused/rc-linear](https://github.com/Qonfused/rc-linear) | all intermediates kept linear in RGBA32F, sRGB only at the blit; texel-by-texel march stopping below transmittance 0.001 |
| [raesga02/RadianceCascades2D](https://github.com/raesga02/RadianceCascades2D) (Vulkan) | interval length extended by `2√2·spacing` against leaks; analytic sun lobe and sky at the top cascade |
| [lixu0073/2DGI](https://github.com/lixu0073/2DGI) (Unity URP) | last frame's GI at hits as a second bounce, ping-pong accumulation, à-trous denoiser, blue-noise ray jitter |
| [ErwinTerpstra/RadianceCascades](https://github.com/ErwinTerpstra/RadianceCascades) (Unity Render Graph) | 10-bit ARGB2101010 radiance buffer; README claims 14 and 8 ms at 1080p on an RTX 3060 laptop GPU |
| [CptNemo0/RadianceCascades](https://github.com/CptNemo0/RadianceCascades) (thesis code) | cascades updated at their own frame frequencies, measured against full updates; RGBA8 targets |
| [entropylost/vlam](https://github.com/entropylost/vlam) | cascades used for path guiding: at each level one of 4 child directions is picked in proportion to its stored radiance, dividing by the product `4·w` |
| [chamchi0809/pixi-GI](https://github.com/chamchi0809/pixi-GI) (PixiJS) | holographic RC with temporal accumulation and occluders lit from a fluence mip |
| [lancimir/holographic-cascades](https://github.com/lancimir/holographic-cascades) | CPU holographic RC following the paper's equations |
| [hbattal/2D-Lights](https://github.com/hbattal/2D-Lights) | holographic trace with per-cell absorption; direction-first RC with bilinear fix |
| [GiGGioSo/radiance_cascades_2d](https://github.com/GiGGioSo/radiance_cascades_2d) | directions ×2 per level instead of ×4; a row-by-row variant with a two-row cache |
| [nema-nya/radiance-cascades](https://github.com/nema-nya/radiance-cascades) | step lengths and angle counts doubling per level, described as a multipole expansion |
| [multiversiann/Radiance-Cascades](https://github.com/multiversiann/Radiance-Cascades), [ruizemanuel/pull-cord-lamp](https://github.com/ruizemanuel/pull-cord-lamp) | intervals extended 2% past their end; GI at 0.35 to 0.5 of screen resolution |
| [akghxhs55/radiance-cascades-d3d11](https://github.com/akghxhs55/radiance-cascades-d3d11) | cascade count `ceil(log4(3·D/L + 1))` from the scene diagonal `D` |
| [bakjedev/radiance-cascades](https://github.com/bakjedev/radiance-cascades) (Slang, Vulkan) | pre-averaging before a 4-probe merge; a pull/push pass with 1-3-3-1 weights |

## Bugs that recur

- Intervals that do not meet: in lantrol's code level 1 ends at 4 units while level 2 starts at 5, leaving a gap. nff747's interval comments disagree with its code.
- Merges skipped where they matter: CptNemo0's out-of-bounds rays skip the upper merge, darkening borders; nff747's "bilinear" merge reads only the same texel.
- Probe spacing never grows (nff747), or the cascade count is computed but the last merge step is missing (Yaocenji).
- Float ray indices lose exactness above 2^24 (CptNemo0, from cascade 12 on).

## Checked with nothing usable

These look relevant by name but hold no working RC code: Kollabiz/GoRadianceCascades and Temp-Name-Studio/Bevy-Voxel-Cascade (README only), joelmartin-dev/BeansEngine (RC removed; its history holds a partial version with no measurements), AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades (a path tracer), willWallace-RIT/Radiancecascade3d (incomplete), JavierSerranoDev/radiance-cascades-vulkan, Winstob/radiance-cascades, shirokoff/raylib-radiance-cascades, j-vandy/SilkEngine, Heraclito-Q-Saldanha/RadianceCascades and vsensu/bevy_radiance_cascades (empty or unrelated), cgorto/bevy-radiance-cascades and WillKirkmanM/radiance-cascade (per-pixel marching or gradients, not cascades), tinycrops/Radiance-Cascades (a neural residual cascade), katyhuff/uiuc-arfc-2025-02 (a LaTeX template).
