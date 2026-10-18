# Screen-space probe 3D RC repositories

Three engines that place cascade probes on the depth buffer, as PoE2 does, but run in full 3D. Two trace world-space intervals with hardware ray tracing; one marches a min/max depth pyramid in screen space and is the only one written as GLSL compute.

| Repository | API | Tracing | Last commit |
|---|---|---|---|
| https://github.com/Qirias/RC-SPWI | Metal (Apple silicon) | hardware ray tracing against one static triangle structure | 2026-09 |
| https://github.com/ClaikoCode/DX12RadianceCascades | D3D12, HLSL, DXR on MiniEngine | hardware ray tracing, TLAS updated each frame | 2026-04 |
| https://github.com/Alexander-Koutrakis/Alpha-Renderer | Vulkan, GLSL compute | screen-space march of a min/max depth pyramid | 2026-10 |

## ClaikoCode/DX12RadianceCascades

This is the code behind [Dell'Ova's thesis](2025_dellova_rc_performance_scaling_thesis.md), which has the measurements.

- Defaults: cascade 0 probes every 2 px, 16 rays per probe, `rayLength0` 5, rays ×4 and probe spacing ×2 per cascade, up to 8 cascades (`floor(log2(min probe count))`).
- Layout is direction-first: `probeIndex = pixel mod probesPerDim`, `rayIndex = floor(pixel / probesPerDim)`. Directions use an equal-area octahedral map over the full sphere.
- Intervals: start `= 5·(4^c − 1)/3`, length `5·4^c`, so `[0, 5], [5, 25], [25, 105], [105, 425]`. No leak fix.
- With pre-averaging on (the default), the ray generation shader traces 4 sub-rays per stored texel and averages them, so each texel side is `sqrt(rays/4)`.
- The closest-hit shader returns only the emissive texture, so the result is one bounce from emitters. The last cascade's misses read the skybox.
- Merge: per sub-ray, a 4-tap bilinear read of cascade `N+1`, `rgb = near.a·far.rgb`, averaged and added to the near value, in place. A depth-aware path with "bilinear 3D" weights from reconstructed world points exists but is off.
- Final lighting reads the nearest cascade 0 probe (no interpolation) with cosine weights.

## Qirias/RC-SPWI

- Six cascades, probes every 4 px, octahedral directions with `4·2^L` texels per side, 16 base rays.
- Intervals `start = 0.4·4^(L−1)·len`, `end = 0.4·4^L·len` with `len` 0.6, so `[0, 0.24], [0.24, 0.96], [0.96, 3.84]`.
- The upper merge uses Suslik's iterated "bilinear 3D" ratio (see [2023_rc_shadertoys.md](2023_rc_shadertoys.md)); the final gather uses a bilateral threshold of 0.05.
- A min/max depth mip pass and a blur pass exist but are never dispatched. The README says it is not ready for use.

## Alexander-Koutrakis/Alpha-Renderer

- Frame: shadow, G-buffer, sky, direct light, RC GI, transparency, composition (`opaque + GI`), SMAA, color grading. The RC pass reads direct light without albedo (`outIncident`) as the radiance of what rays hit.
- Depth: linearized, then a min/max pyramid (RG16F) over the full mip chain. Rays march it coarse-to-fine; steps `clamp(8 + int(1.5·sqrt(maxDist)), 8, 48)`; start offset `max(0.01, 0.0015·linear depth)` along the normal.
- Six cascades. Cascade 0 probes every 2 px with a 2×2 hemisphere tile; tile side `2 << c`, so `4^(c+1)` directions. Hemisphere directions shrink slightly toward the pole: `mix(0.90, 0.98, clamp((tile − 2)/6, 0, 1))`.
- Bands `[0, 0.32], [0.32, 1.28], … , [81.92, 327.68]` (base 0.08 times `4^c`); each dispatch extends its band by 15% of the previous band's length for overlap.
- Hit radiance `incident·albedo·kD/π`; hit transmittance is a squared smoothstep of the normalized hit distance instead of 0.
- Merge `near.rgb + near.a·far.rgb` with bilateral weights and 2×2 angular bilinear reads. Resolve takes 2×2 samples per pixel, reprojects with the previous view-projection for temporal accumulation, and multiplies by a `GI_BOOST` of 3. Sky contribution is off.
- README claims about 5.5 ms total at 1080p on an RTX 3070 and about 80 MB of memory.
