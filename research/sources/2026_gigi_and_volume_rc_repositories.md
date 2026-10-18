# Gigi 2D RC and RC for CT volumes

| Repository | Author | License | Last commit | What it is |
|---|---|---|---|---|
| https://github.com/Kosmokleaner/GigiRadianceCascades | Kosmokleaner (Technique.json names Martin Mittring) | BSD-3-Clause | 2026-10 | 2D RC with the bilinear fix as an EA Gigi graph in HLSL |
| https://github.com/ReneeR33/radiance-cascades-volume-rendering | Renée Rulkens | none | 2026-01 | 3D world-grid RC lighting CT volumes, OpenGL 4.4 compute |

The second repository is the code behind Rulkens' TU/e thesis "Radiance Cascades for Medical Volume Data" (2025), whose PDF is behind a bot check. Neither repository has timings.

## Gigi 2D RC

A compact reference for single-frame 2D RC with the bilinear fix and volumetric marching, in nine passes: paint, occupancy, then one propagate pass per cascade from 5 down to 0, then the final image.

- **Scene:** an RGBA16F texture where RGB is emission and alpha is opacity. No distance field: an 8×8-pixel occupancy grid (a cell is set if any pixel in the 24×24 block around it is non-empty) lets the 1 px march skip 7 px through empty cells.
- **Layout:** 6 cascades at 512², spacing `2^c` px, `4^(c+1)` rays per probe, direction-first with 4 rays pre-averaged per texel, ray `j` at angle `(j + 0.5)·2π/count`. Each cascade is its own RGBA16F texture.
- **Intervals:** `[0, s)`, then `[s·4^(c−1), s·4^c)` px with scale `s = 1`; the top cascade marches `[256, 1024)`. No overlap.
- **March:** front to back with bilinear scene reads, `L += T·rgb·a; T *= 1 − a`, stopping at `T < 0.01` or the texture edge.
- **Merge (bilinear fix):** for lower ray `j` at probe origin `o`, the four upper probes `q` around `o/(2T) − 0.5` (clamped) each get their own march from `o + d·t_start` to `q + d·t_end`, then `r_j = Σ w_q·(seg.rgb + seg.a·U_q(j))`, where `U_q(j)` is the upper texel for direction slot `j`. The stored texel averages its four rays. A source comment says the four marches avoid both double counting (bright rings) and gaps (leaks).
- The final pass multiplies fluence by a fixed albedo of 0.5. An ambient term is commented out because it "hides leaks" while debugging.

## RC for CT volumes

A full-resolution world-space 3D grid over a unit cube: 192³ probes in cascade 0, 5 cascades, probes halving per axis (192, 96, 48, 24, 12).

- **Scene:** a 192³ combined volume of color and transmittance (RGBA8 each). Emitter voxels and CT values at or above a cutoff are opaque; lower CT values attenuate as `exp(−(absorption + scatter)/190)` per voxel.
- **Directions:** cube-face subdivision, `6·4^c` per probe (6, 24, 96, 384, 1536). Each direction is the normalized cell center; its weight is the cell's solid angle (two spherical triangles by Girard's theorem) divided by `4π/n`. A tetrahedral mapper with `4·4^c` directions also exists.
- **Intervals:** doubling, not quadrupling: `[0, 1/r]`, then `[2^(c−1)/r, 2^c/r]` with `r = 100` (about 1.9, 3.8, 7.7, 15.4 voxels), the top cascade running to the cube edge. This is the paper's 3D grid law: spacing ×2, directions ×4, intervals ×2.
- **March:** 1-voxel steps with nearest reads; transmittance multiplies by `T^(190·step)`; an opaque voxel adds its color times 20 and ends the ray.
- **Merge:** trilinear over the 8 upper probes, each the mean of the 4 child directions `4a … 4a+3`: `color = c + t·Σ w_q·mean_q`, `trans = t·Σ w_q·meanT_q`. Out-of-range upper probes return the background with transmittance 1. No bilinear fix.
- **Storage:** RG32UI texels holding color and transmittance as hand-packed 11-11-10 floats.
- **Shading:** a separate ray march through the CT finds surfaces, offsets the lookup 1.7 probe spacings along the normal, interpolates cascade 0 trilinearly, and sums `L_i·max(d_i·n, 0)` over the 6 directions. Translucent samples use a per-probe irradiance texture (the mean of the 6 directions) for single scattering.

### Lessons from its problems

- **Child ordering:** with row-major cells per cube face, children `4a … 4a+3` are four cells in a row of the finer grid, not the 2×2 block under the parent, from cascade 1 upward. Direction indices must be laid out as a quadtree (Morton order per face, or equal-area layouts ordered the same way) for the `4a + l` child rule to hold.
- **Normalization:** stored values are pre-weighted by solid angle, and the shading sum uses `2π/n` on top, which for uniform light gives half the correct irradiance. Pick one convention and check a uniform-sky case.
- **Memory:** about 1.5 GB of allocations at 192³ (raw cascades 628 MB, merged copies 608 MB, half of the latter never used). A dense full-resolution 3D grid is the method's worst case, as the paper warns.
- **Precision:** 8-bit transmittance rounds very small values to exactly 0, which the march treats as opaque.
