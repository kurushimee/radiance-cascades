# Unity URP and Unreal Engine RC plugins

Two engine plugins with 3D RC. The Unreal one has the most developed screen-space variant found: RC intervals carried as visibility bitmasks, as in [bitmask SSGI](2022_therrien_visibility_bitmask_ssgi.md). Its world-space mode is another Split RC port with hardware ray tracing.

| Repository | Engine | Modes | Last commit |
|---|---|---|---|
| https://github.com/Twenmod/UERadianceCascades (no license) | Unreal 5.8.2 plugin, SM6 | screen-space bitmask RC; world-space Split RC with hardware RT | 2026-10 |
| https://github.com/alexmalyutindev/unity-urp-radiance-cascades (MIT) | Unity 6.2 URP render feature | 2D screen probes, cube-map probes, direction-first probes with SH output | 2025-08 |

## Unreal: screen-space bitmask RC

Runs after post-processing reaches "before DOF", on the pre-DOF scene color, depth and G-buffer normals.

- Parameters: `R` base rays per probe (4 or 16), tile size `T` (2 or 4 px), wall thickness 300 view units. Probe spacing at cascade `c` is `T·√R^c` px and each probe has `R^(c+1)` rays.
- Cascade count `clamp(ceil(log(diagonal)/log(R)) + 1, 1, 32)` from the probe grid diagonal.
- Intervals in pixels: `start_c = 2T·(R^c − 1)/(R − 1)`, length `2T·R^c`, so `[0, 8), [8, 40), [40, 168)` for `R = T = 4`.
- Each ray is a 2D screen slice. Up to 8 samples per interval with blue-noise jitter. Each sample becomes a front point and a back point (front pushed back by the wall thickness), whose angles in the slice mark covered sectors of a 32-bit mask.
- Sector weights `w_j = sin((j + 0.5)·π/32)`, a cosine weight across the slice; their sum `1/sin(π/64) ≈ 20.38` normalizes. A sample adds its color times the weight of the sectors it newly covers.
- The stored value is radiance plus the mask. The interval's openness is the weight of uncovered sectors.
- Merge: the upper value is scaled by the fraction of the upper interval's covered sectors that this interval leaves open, `WeightedBitSum(UpMask & ~mask)/WeightedBitSum(UpMask)`, and the masks are OR-ed. This replaces the scalar β with a per-sector one, so light hidden by near geometry in one part of the slice still passes in another.
- Upper probes are blended with depth-aware "bilinear 3D" weights (two projection iterations onto the quad of four upper probe positions).
- Apply: 4 probes per pixel with `saturate(1 − planeDistance/(0.03·depth))` weights from the pixel's normal plane, falling back to the nearest probe; result `color + rgb·π·intensity·diffuseColor`.

## Unreal: world-space Split RC

Follows [Split RC](2026_freeman_split_radiance_cascades.md) and the chandra code (a source comment names it). It plugs into Unreal's `RenderDiffuseIndirectLight` GI plugin delegate.

- Probe hash per cascade, 131072 cascade 0 slots, table 4× larger; 62-bit keys with 19 bits per axis and 4 LOD bits; probe size `BaseVoxelSize·2^level`, cascade `c` cell `>> c`.
- LOD from Chebyshev distance with `LevelBaseDist`, blended across two levels like chandra.
- 32 bins at cascade 0 on a `2D×D` cylindrical equal-area grid, Morton indexed; `kC0Len = 1.5958 = sqrt(32/4π)`.
- One ray per pixel against the TLAS plus a "far TLAS", shaded with direct light, emission and indirect light. Cascade from `ceil(max(0.5·log2(t/(kC0Len·size)), 0))`, capped at 3. Values are stored as `uint(value·10000)` for integer atomics.
- Multi-bounce (on by default): primary hits read last frame's atlas at `level + 2`; a secondary probe set at the cached hit points gets its own rays.
- Merge: parent weights `{27, 9, 3, 1}/64` by the number of mismatched coordinate bits, times deposit quality. Temporal decay multiplies weight and radiance by 0.9 when weight exceeds 3 or a bin is older than 12 frames.
- Cascade 0 is integrated into a 6×6 octahedral irradiance tile with border in a 4096² atlas; the apply reads 8 corners per LOD.

## Unity: direction-first screen probes

- Depth inputs: a min/max depth mip chain (3×3 min/max at mip 0), blurred depth moments `(d, d²)`, and a blurred color mip chain for lighting.
- Six cascades with probes every `8·2^L` px on a 2048×1024 grid. Each probe has two depth probes, at the minimum and maximum depth of its tile, stored in the left and right halves of the texture.
- Directions in view space: `4·2^L` azimuths and 4 polar angles. Interval ranges double per level (`[0, 1], [1, 2], [2, 4], …` times `RayScale`).
- Each ray traces 16 "virtual depth rays" with offsets in [−1, 1] against the variance-filtered depth `mean + σ`, reading color from the blurred mip `L + 1`; the 16 results are averaged into one value with transmittance. The author calls this variance trapezoid integration.
- Merge blends the min and max halves of the upper cascade by where the lower probe's depth falls between the upper min and max. A fixed factor `0.25/2^L` scales the upper value, which the author describes as a `1/rayCount` term, not a derived one.
- Cascade 0 is projected onto L1 spherical harmonics per probe at quarter resolution and upsampled bilaterally against the min/max depth.
- The README and issues call the mode unstable under camera motion; the min/max probe pair is what made it the most stable of the three.
