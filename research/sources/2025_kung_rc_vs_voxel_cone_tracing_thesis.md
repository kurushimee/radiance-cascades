# Comparing Radiance Cascades to Voxel Cone Tracing for Interactive Global Illumination in Dynamic Scenes

| | |
|---|---|
| Author | Johannes Kung |
| Date | 2025-06 |
| Kind | MSc thesis, Linköping University (LiTH-ISY-EX--25/5758--SE), with Beartwigs AB (the game Romestead) |
| Link | https://www.diva-portal.org/smash/get/diva2:1967544/FULLTEXT01.pdf |
| Comparison VCT | https://github.com/compix/VoxelConeTracingGI (MIT) |

Screen-space 3D RC in a shipping game engine, compared with voxel cone tracing on Sponza. The implementation is naive and its timings are poor, so the value lies in its catalog of artifacts and their causes, not in its numbers. The author found a probe placement bug late, so results at sparse probe spacing are less reliable.

## Implementation

- Probes on a 2D screen grid every SPS pixels (1, 2 or 4), each placed at the depth of its pixel and pushed out along the normal.
- Directions: `n` azimuth × `m` polar angles on the full sphere, `φ_j = (j + 0.5)·2π/n`, `θ_k = (k + 0.5)·π/m`; 4×4 at cascade 0. Equal polar steps oversample the poles, which the author flags as a possible bias.
- Branching factor 2 per axis: probes halve per screen axis and directions double per angle axis per cascade, so each cascade texture has the same size. Layout is direction-first: an `n×m` grid of tiles, one tile per direction holding all probes.
- Rays march the depth buffer with a fixed thickness and return the G-buffer emission at a hit; there are no bounces. A voxel marcher (256³ texture) exists in the prototype.
- Merge: for each direction, average the 4 nearest upper directions, each read bilinearly from 4 upper probes. β is interpolated like radiance. Only two textures are needed, alternating read and write.
- Shading: `E ≈ (1/N)·Σ L0(ω)·(ω·n)` from bilinearly interpolated cascade 0, then `albedo·E + emission`.

## Performance (RTX 3060, 1280×720, 6 cascades, D3D11 timestamps)

| Scene | SPS 1 | SPS 2 | SPS 4 |
|---|---|---|---|
| House (small indoor) | 70 ms | 18 ms | 4.9 ms |
| Dungeon | 196 ms | 66 ms | 21 ms |
| Plains (large outdoor) | 294 ms | 100 ms | 30 ms |
| Vulcano (large outdoor) | 295 ms | 99 ms | 30 ms |

- Medians shown. Doubling SPS cuts time by about 3×, not the expected 4×.
- Time grows with scene size because rays march fixed steps (`20·1.2^i` per cascade) until they hit, so open scenes produce long rays. Moving objects did not change the cost.
- The author concludes SPS 1 is not real-time and SPS 2 might be after optimizing the ray march, which was the main cost.

## Artifacts found against VCT

| Artifact | Cause given | Remedy given |
|---|---|---|
| Light leaks through thin objects | depth buffer lacks hidden surfaces; coarse voxels merge emitter and occluder; large steps; a ray missing an edge then merging with an upper ray beyond it | better tracing |
| Light and dark leaks at depth edges | merge and shading interpolation ignore depth | depth-aware (bilateral) weights |
| Flicker under camera or object motion | screen-space probes jump in depth between frames | world-space probes with reprojection, low-pass filtered depth, or temporal accumulation |
| Small lights too dim, with visible ray streaks | too few cascade 0 directions to hit them | more directions, or per-frame direction offsets accumulated over frames |
| Light drifting toward the lower left at large SPS | probably a probe placement bug | fix placement |

Every artifact but the small-light one grows with SPS. VCT only showed leaks, and those were stronger than RC's through thin objects.
