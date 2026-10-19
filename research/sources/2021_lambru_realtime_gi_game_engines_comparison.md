# Comparative analysis of real-time global illumination techniques in current game engines

| | |
|---|---|
| Authors | Cristian Lambru, Anca Morar, Florica Moldoveanu, Victor Asavei, Alin Moldoveanu |
| Date | IEEE Access 9 (2021), 125158-125183, published 2021-09-01 |
| Kind | Survey with the authors' own implementations, open access (CC BY) |
| Link | https://ieeexplore.ieee.org/document/9527241 (DOI 10.1109/ACCESS.2021.3109663) |

The paper sorts rasterization-based real-time GI into four classes, implements one representative of each in one OpenGL 4.6 framework, and compares them on the same Sponza scene. Hardware ray-traced GI is described but not implemented. [Gerassimov](2026_gerassimov_rc_vs_unity_gi.md) cites it for engine GI limits.

## Classes and implementations (sec. III-IV)

| Class | Implemented technique | Notes from the implementation |
|---|---|---|
| Reflective shadow map (RSM) | Dachsbacher and Stamminger's stochastic RSM sampling, gathered at low resolution and reused per pixel where normals and positions match (their screen-space interpolation) | One bounce only; a fixed quasi-random sample set reused every frame avoids brightness jumps between sample sets; banding along light directions, because pixels on one light ray project to the same RSM texel and pick the same samples |
| Discrete ordinate method (DOM) | Light propagation volumes with Kaplanyan and Dachsbacher's cascades and geometry occlusion volume, the occlusion built only from the RSM and the G-buffer | OpenGL 4.6 has no float atomics, so injection could not write RGBA32F cells; packing into one R32F left 8 bits per SH coefficient, too few, so four R32F volumes hold one coefficient each. Leaks through walls at low resolution; more resolution needs more propagation iterations |
| Voxels | Voxel cone tracing (Crassin et al.) with anisotropic mips, 6 colours per voxel from the second mip level up, one shadow cone and 5 short AO cones | One colour per voxel at the finest level bleeds light through thin walls lit from one side, more so at low resolution |
| Screen space | Screen-space directional occlusion with SSR, screen-space shadows, Mittring's SSAO (4×4 rotated patterns, 5×5 Gaussian blur) and screen-space refraction | Needs a direct-lighting pass first; small lit areas give noise at any sample count; lighting changes as the camera moves |

All four need a light intensity scale factor to reach the intended brightness, and translucent objects are left out of the RSM so it keeps the opaque surfaces that reflect light.

## Effects (sec. V, Table 1)

| Class | Indirect diffuse | Glossy | Shadows | AO | Subsurface and translucency | Volumetric | Area lights |
|---|---|---|---|---|---|---|---|
| RSM | yes | partly (1, 3) | yes | partly (1) | partly (1, 4) | yes | no |
| DOM | yes | partly (3) | no | no | partly (3, 4) | no (4) | yes |
| Voxels | yes | yes | yes | yes | yes | no (4) | yes |
| Screen space | partly (1, 2) | partly (1) | partly (1; a second mark is unreadable) | yes | partly (1, 4) | partly (5) | partly (1, 2) |

Footnotes: (1) the class partly lacks the information the effect needs; (2) temporal coherence problems in dynamic scenes; (3) no high-frequency information; (4) possible only with significant changes to the class; (5) inflexible approximations for particular cases.

- Voxel AO needs long cones because voxels cannot resolve short-range occlusion, so it comes out much darker than the short-range screen-space and RSM versions.
- Volumetric light needs a second LPV or voxel volume holding direct light rather than reflected light, doubling the expensive passes.
- Screen-space area lights miss emitters that face away or sit off screen.

## Performance (sec. VI, Table 2)

GTX 1070, Sponza (262k triangles), frame rates for indirect diffuse, shadows and AO only, read from the table image:

| Class | Setting | 1280×720 fps | 1920×1080 fps |
|---|---|---|---|
| RSM, 512² | 100 / 200 / 300 / 400 samples | 226 / 187 / 157 / 136 | 122 / 99 / 84 / 73 |
| RSM, 1024² | 100 / 200 / 300 / 400 samples | 190 / 144 / 116 / 96 | 109 / 84 / 68 / 58 |
| LPV | 32³ / 64³ | 196 / 94 | 111 / 68 |
| VCT, voxelized once | 64³ / 128³ / 256³ / 512³ | 283 / 250 / 216 / 178 | 145 / 128 / 109 / 89 |
| VCT, voxelized every frame | 64³ / 128³ / 256³ / 512³ | 214 / 214 / 170 / 74 | 138 / 121 / 96 / 52 |
| SSDO | 100 / 200 / 300 / 400 samples | 85 / 50 / 35 / 27 | 36 / 21.4 / 15.0 / 11.6 |

- Higher RSM resolution costs more than its rendering time because texture-cache misses grow with the sampled texture, worse with more samples. LPV cost sits in injection and propagation; shading costs about the same at both resolutions. Per-frame voxelization costs more than the cone-traced shading at 512³. SSDO must gather from far away to match the others and thrashes the texture cache, so it suits only fine detail.

## Conclusions (sec. VII)

Screen-space methods give the sharpest glossy reflections and acceptable AO but fail for long-range diffuse light and flicker under motion; the RSM is flexible but one bounce, and best as the photon source for other methods; LPVs give plausible, overly bright low-frequency diffuse light cheaply; voxels cover the most effects with the most plausible results at the price of voxelization.

## For RC

- The frame rates are whole-frame figures with shadows and AO, so per-technique cost is not separable; at 1080p they span about 7 to 19 ms for voxel cone tracing with per-frame voxelization (64³ to 512³), 9.0 and 14.7 ms for LPVs, 8.2 to 17.2 ms for RSM sampling and 28 to 86 ms for SSDO on a 2016 GPU (derived as 1000/fps).
- Godot's `RenderingDevice` meets the same constraint as the LPV workaround: its GLSL has no float atomics either, so any scatter or splat step in RC there (injecting emitters into a grid, accumulating hits) needs integer-encoded values or a gather formulation (inference).
- The two failure modes it documents for grid methods, leaking through walls thinner than a cell and over-bright results at low resolution, are the same ones reported for world-space RC grids, and they have the same cause: one value per cell standing for both sides of a surface (inference).
