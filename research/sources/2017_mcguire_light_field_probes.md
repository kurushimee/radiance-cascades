# Real-Time Global Illumination using Precomputed Light Field Probes

| | |
|---|---|
| Authors | Morgan McGuire, Mike Mara, Derek Nowrouzezahrai, David Luebke |
| Date | I3D 2017; DOI 10.1145/3023368.3023378 |
| Kind | Paper (author PDF) |
| Link | https://casual-effects.com/research/McGuire2017LightField/McGuire2017LightField.pdf |

A regular grid of probes stores, per octahedral texel, radiance, the normal of the nearest surface and its radial distance, so the probe set is a ray-traceable approximation of the scene. Rays are traced through the probes' depth maps, and diffuse light is gathered from prefiltered irradiance weighted by a Chebyshev visibility test on distance moments. The prefiltered visibility test is the one DDGI later made dynamic ([2019_majercik_ddgi.md](2019_majercik_ddgi.md)), and the probes use Cigolle's octahedral map ([2014_cigolle_octahedral_unit_vectors.md](2014_cigolle_octahedral_unit_vectors.md)). Section numbers are the paper's.

## Probes and storage (sec. 3)

- Probes sit on a regular grid inside the scene bounds, not jittered in the results. Each probe stores a spherical slice of the light field `L(x, ω)`, the normal of the nearest surface in each direction and its radial distance `r`.
- Octahedral maps (Cigolle et al. 2014) replace cube maps, which the paper says cuts space and bandwidth by about 4× at equal quality. Each probe is one layer of a 2D texture array.
- Radiance R11G11B10F (32 bits), normal RG8 (16 bits), radial distance R16F (16 bits): 8 bytes per texel. A compressed alternative (BC6H radiance, two BC4 for normals, R16F distance) gives 4 bytes per texel; the results use uncompressed textures to shorten generation.
- Radiance probes are 1024² texels in all results, sized so a texel's solid angle does not exceed a pixel's at the probe center, which avoids aliasing in mirror reflections; Fig. 18 compares 64², 256² and 1024².
- Irradiance probes are 128² octahedral texels at 8 bytes, with squared distance (16-bit float) in place of the normal channel for the Chebyshev test; the paper says 32² is often enough.
- Generation rasterizes six cube faces per probe and resamples to octahedral; direct light is the first bounce, and further bounces come from re-shading and re-rendering the probes. It takes 1 to 2 minutes per scene (sec. 6).

## Tracing (sec. 4)

- A ray is traced in the probe whose center is closest to the ray's line. In the octahedral map it projects to at most four 2D polyline segments, one per octahedral face crossed. A probe answers HIT, MISS or UNKNOWN, the last when the ray passes behind a surface the probe cannot see.
- On UNKNOWN the ray origin advances to the exit point and the next of the eight surrounding probes is tried, chosen by `i' = (i + 3) mod 8` with offsets `(i mod 2, ⌊i/2⌋ mod 2, ⌊i/4⌋ mod 2)`, which moves to the farthest probe (Fig. 3). If all eight fail, the ray is taken to hit at the last seen location.
- A two-level min-mip hierarchy of radial depth, the second level at 1/16² resolution, speeds the depth tests; more levels would need a stack, which shaders cannot hold without spilling to memory (sec. 4.2).
- Back faces are rejected with the stored normal.

## Shading (sec. 5)

- Each pixel traces two indirect rays, one Lambertian and one glossy, with cosine-weighted BRDF sampling (sec. 5.1).
- Denoising: Lambertian uses a 12-pixel cross-bilateral filter at stride 2 and an exponential moving average with 98 % hysteresis; glossy a 3-pixel filter and 75 % hysteresis.
- Visibility-aware irradiance (sec. 5.2): probes prefilter cosine-weighted irradiance and the first two moments of radial distance, `E[r]` and `E[r²]`. A query blends 8 probes with trilinear weights times a clamped dot product between the normal and the direction to the probe, times a Chebyshev test with `σ² = |E[r]² − E[r²]|`, normalized to sum to one: eight texture fetches per shading point. This removes light and dark leaks around occluders (Figs. 10-12), while probe-indexing noise remains where visibility is complex.

## Results (sec. 6)

GeForce 1080, 1920×1080, full-resolution shading (Table 1, ms):

| Scene | Probes | Radiance texels | Lambertian | Glossy |
|---|---|---|---|---|
| Cornell Box | 2×2×2 | 2048² | 0.358 | 0.000 |
| Cornell Box | 2×2×2 | 256² | 0.302 | 0.000 |
| Sponza (statue) | 8×2×4 | 512² | 0.332 | 0.151 |
| Living Room | 4×4×4 | 1024² | 0.293 | 4.401 |
| Luxury Kitchen | 4×4×4 | 1024² | 0.358 | 9.334 |
| San Miguel | 8×2×8 | 1024² | 0.520 | 47.170 |

- The squares on the texel counts are lost in text extraction and restored here. The Living Room total of 4.7 ms matches Fig. 1.
- Fig. 11: ray-cast indirect 13 ms against 0.2 ms for prefiltered visibility (about 65×) in a 3×2×3 grid.
- San Miguel's 128 probes take about 500 MB compressed, against about 2 GB for its compressed geometry and textures (sec. 7).

## Limitations

- Probes are precomputed for static geometry; dynamic receivers are lit, but dynamic objects cast no indirect light (Fig. 16), and real-time probe updates are future work.
- Glossy cost follows glossy coverage; San Miguel is slow because every surface has a broad glossy lobe. Primary rays alias (Fig. 20). Too few probes leave diffuse interreflection artifacts.
- Spherical harmonics were rejected because they ring and need 2 to 3× the bandwidth (sec. 7).

## For RC

- A 1024² octahedral radiance probe is a single dense RC-style direction set with no cascade: angular resolution fixed by the mirror criterion at every distance. RC gets the same far-field resolution from its top cascade at a cost spread over many coarse probes (inference).
- Storing per-texel hit distance and normal turns probes into a traceable scene proxy; RC implementations that store hit distances for bounces or depth-aware merges use the same data (inference).
- The Chebyshev test on distance moments is the visibility weighting that probe-based RC upsampling and world-space RC borrow from this line of work.
