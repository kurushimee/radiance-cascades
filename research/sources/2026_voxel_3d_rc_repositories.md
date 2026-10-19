# 3D radiance cascades over voxels and hardware ray tracing

Three small 3D projects, each with a different scene representation. Together they show what a voxel clipmap trace costs, what a naive full 3D grid costs in memory, and a few practical fixes.

| Repository | API | Probes | Scene |
|---|---|---|---|
| https://github.com/creikey/voxel-radiance-cascades (MIT) | Rust, Sokol, GLSL compute on D3D11 and WebGPU | screen-space, on G-buffer pixels | camera-centered voxel clipmap, density only |
| https://github.com/rbnelr/voxel_game | C++, OpenGL 4.6 compute | fixed world box | 512³ toroidal block window with a distance field |
| https://github.com/jumeder/dx12-radiance-cascades | C++, D3D12 DXR and HLSL compute | fixed world box, full 3D grid | hardware ray tracing (BLAS per model, TLAS rebuilt each frame) |

## Contents

- [creikey/voxel-radiance-cascades](#creikeyvoxel-radiance-cascades)
  - [Scene](#scene)
  - [Cascades](#cascades)
  - [Numbers (D3D11, 640×360, GPU not named)](#numbers-d3d11-640360-gpu-not-named)
  - [Lessons recorded](#lessons-recorded)
- [rbnelr/voxel_game](#rbnelrvoxel_game)
- [jumeder/dx12-radiance-cascades](#jumederdx12-radiance-cascades)

## creikey/voxel-radiance-cascades

Screen-space RC at 640×360, tracing a world voxel clipmap. Its report has the most detailed timings of any small 3D RC project.

### Scene

- Static clipmap: four levels of 64³ cells, cell edge 1, 4, 16 and 64 m. One u32 per cell (albedo and density, unorm8) and two u32 of half-float radiance. 12 MiB in total.
- The clipmap recenters only when the camera moves more than 12 m from its center, snapped to 2 m. A recenter rebuilds all four levels; there is no toroidal scrolling.
- Static radiance is albedo times direct light (sun, moon, ambient) with no shadow test, re-injected every frame. So probes see one bounce of unshadowed direct light.
- Dynamic objects go into a separate two-level clipmap (1 m and 4 m) rebuilt every frame as 8³ bricks per object. Overlaps resolve with `atomicMax` on the packed word, which fixed flicker from overlapping objects.

### Cascades

| Cascade | Probes | Directions | Interval (m) | Step (m) |
|---|---|---|---|---|
| 0 | 160×90 (every 4 px) | 32 | 0–1.6 | 0.1 |
| 1 | 80×45 | 128 | 1.6–6.4 | 0.3 |
| 2 | 40×23 | 512 | 6.4–25.6 | 1.2 |
| 3 | 20×12 | 2048 | 25.6–102.4 | 4.8 |

- Probes take the depth and normal of one G-buffer pixel. The ray origin is snapped to `max(0.125, 0.25·4^c)` m and pushed out along the normal by `0.82·4^c` m.
- Directions are a Fibonacci sphere with `N` points, full sphere. The merge groups child indices `4k..4k+3`, which on a Fibonacci lattice share a height but spread around in azimuth.
- Each ray takes 16 samples. The clipmap level is chosen per sample from the distance along the ray: `LOD = clamp(0.5·log2(max(t/2, 1)), 0, 3)`, blending two levels. So the voxel size grows with distance, like cone tracing.
- Extinction per sample is `clamp(0.36·density, 0, 0.9)`. Samples outside the cascade's own clipmap level add a faint sky term. Cascade 3 adds the sky after the loop.
- Merge: bilinear over 2×2 upper probes, four child directions each. The far transmittance is averaged, not multiplied.
- Cascade 0 is turned into a 4×4 octahedral irradiance map per probe (32 directions, cosine weighted, weight 4π/32). Shading reads 2×2 probes bilinearly and the octahedral map bilinearly, with no border wrap.
- No temporal accumulation.

### Numbers (D3D11, 640×360, GPU not named)

- Baseline GI compute 0.76 ms: trace 0.52 ms, merge and octahedral build 0.08 ms. Rays per frame: 1,884,160 with 16 samples each.
- Final build: 2.1 ms average, 2.5 ms worst, most of it G-buffer and shadow maps; trace 0.49 ms.
- Halving the cascade 0 spacing to 2 px (7.4 M rays) cost 3.5× the GPU time.
- Synthetic trace benchmark: 14.3 G rays/s on D3D11, 2.8 G rays/s on WebGPU in a browser.

### Lessons recorded

- Geometry thinner than one voxel leaks. Indirect detail is limited by the 4 px probe spacing and the 4×4 octahedral maps.
- A small emitter seen by only one or two cascade 0 directions becomes a bright firefly probe. The fix was to cap the emitter's injected radiance and add an analytic term for its nearby falloff.
- Screen-space contact AO multiplied onto the indirect light caused rings on terrain until same-material taps were skipped.

## rbnelr/voxel_game

A Minecraft-style engine with two experimental RC modules that are drawn only as debug views.

- Scene: a 512³ window of R16UI block ids (256 MiB) addressed with `coord & 511`, so moving one chunk rewrites only the new slab. A matching R8I distance field (128 MiB) is built per chunk: mark solid cells and their neighbors, then sweep lines along x, y and z with `min(previous + 1)`, giving an L1-style distance within each chunk.
- Tracing steps by the distance field when it is above 1 (step `n·(1 − ε)/(|dx| + |dy| + |dz|)`, which cannot skip a solid cell) and falls back to a voxel DDA near surfaces.
- 2D module: a horizontal slice of the world, 7 cascades, base spacing 0.125 m, 4 rays at cascade 0, intervals `[√2·0.125·4^(k−1), √2·0.125·4^k]` m, about 145 MB of RGBA16F, 18 M rays per frame, with the bilinear fix.
- 3D module: a single cascade, 25³ probes 4 m apart, 2×2 octahedral directions, no merging.

## jumeder/dx12-radiance-cascades

Full 3D RC with hardware ray tracing in a Cornell box. It shows why a naive full 3D grid is impractical.

- Four cascades with 32³, 16³, 8³ and 4³ probes over a 2×2×2 box. Directions are a lat-long grid of (64 << i)×(32 << i) texels: 2048 directions at cascade 0, 4× more per cascade.
- Memory: 512, 256, 128 and 64 MiB of RGBA16F, 960 MiB in total; 126 M rays per frame.
- Intervals grow 8× per cascade: ends at 0.031, 0.28, 2.28 and 18.3 units. The cascade 0 interval is shorter than the probe spacing.
- The hit shader returns only the instance's emission, so the result is one bounce from emitters.
- Merge: trilinear over 8 upper probes. Looking up the same direction UV in the 2× finer upper tile lands on a 2×2 texel corner, so the hardware linear filter averages the four child directions.
- Shading integrates 2048 directions × 8 trilinear taps per pixel (16,384 samples), with no solid-angle weight for the lat-long grid and no temporal reuse.
