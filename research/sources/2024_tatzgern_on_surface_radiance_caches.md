# Tatzgern et al.: radiance caching with on-surface caches (2024)

| | |
|---|---|
| Title | Radiance Caching with On-Surface Caches for Real-Time Global Illumination |
| Authors | Wolfgang Tatzgern, Alexander Weinrauch, Pascal Stadlbauer, Joerg H. Mueller, Martin Winter, Markus Steinberger (Graz University of Technology, Huawei) |
| Venue | Proc. ACM Comput. Graph. Interact. Tech. 7(3), article 38, July 2024 (HPG) |
| DOI | https://doi.org/10.1145/3675382 |

Not RC. It stores hemispheres of radiance in texture space on the surfaces themselves, the same placement idea as the UV-space probes of [X3XfRM](2024_suslik_x3xfrm_surface_probe_rc.md), and shows what surface-bound caches gain and cost against screen probes and hash grids.

## Structure

- Meshes are split into texture-space islands (connected pieces limited by triangle count and normal spread). Cache entries live in blocks of 2×2 texels on these islands at several mip levels; 2×2 blocks instead of the earlier 8×8 cut memory by up to 14×.
- **Primary cache:** incoming radiance for surfaces visible from the camera, one entry per visible pixel's island texel, 8×8 hemisphere texels of RGB radiance plus hit distance in alpha. A mip bias of 1.5 to 3.5 sets the entry footprint.
- **Secondary cache:** outgoing radiance, 8×8 hemisphere texels, allocated where primary rays hit surfaces without one, at a fixed footprint of about 20 to 30 cm. Secondary entries trace into each other, so bounces build up over frames, and direct light comes from ReSTIR with a 28-byte reservoir per entry.
- A triangle ID map at its own resolution (mip bias −2) turns a jittered cache texel into a world position each update; too coarse a map gives black artifacts where many triangles share an entry.
- Entry size: two 8×8 arrays of half4 (radiance and hit distance), position and normal in full precision, plus 54 bytes of SH and four 64-bit neighbor pointers for the primary cache: 1134 bytes primary, 1076 bytes secondary.
- Entries not updated for 64 frames are freed.

## Update

- Each frame refreshes one quad in four; new entries update at once.
- Primary rays are guided by the cached radiance toward incoming light (as in GI-1.0 and Lumen). Small emitters can still be missed, which flickers.
- Each secondary update traces 32 cosine-weighted rays and applies the BRDF over all 64 directions per ray, one thread per hemisphere texel.
- Temporal filter: exponential average with weight `1/n`, `n` clamped to 4 to 8, reading last frame's value directly from the cache with no reprojection.
- Spatial filter: separable blur of radius 3 in cache space, which needs no depth or normal tests because neighbors are on the same surface; it stops at island borders, so flat surfaces split into several islands show seams. Angle-error rejection (from Lumen) and parallax-corrected neighbor directions limit bleeding.
- After a light turns off, most entries converge within 32 frames; after one turns on, within 16.

## Lookup

- Pixels interpolate trilinearly between two mip levels of the primary cache. Diffuse shading converts the hemisphere to SH; glossy shading importance-samples it by the BRDF.
- One trilinear tap is picked at random with probability equal to its weight, which turns 8 cache reads into 1 at the cost of noise that the temporal filter removes.
- Reflections with roughness below 0.2 trace rays and read the secondary cache at the hit.
- Entries sit on the surface, so thin occluders do not leak, without the heuristics probes and hash grids need.

## Numbers

RTX 3090 Ti, 1920×1080, Falcor, environment and emissive light only. In the extracted Table 1 the Effect and Display pairs sit one row low; shifted back, each row sums to its total.

| Scene | GI-1.0 | Cache | Effect | Display | Total |
|---|---|---|---|---|---|
| PicaPica | 1.78 ms | 0.27 | 0.78 | 0.40 | 1.45 ms |
| Sponza | 2.23 ms | 0.31 | 1.25 | 0.62 | 2.18 ms |
| Flying World | 1.82 ms | 0.32 | 1.01 | 0.39 | 1.72 ms |
| Bistro Exterior | 2.56 ms | 0.31 | 1.72 | 0.61 | 2.64 ms |

| Cache memory, one viewer | PicaPica | Sponza | Flying World | Bistro |
|---|---|---|---|---|
| Primary | 69 to 171 MB | 44 to 127 MB | 32 to 106 MB | 75 to 224 MB |
| Secondary | 89 to 185 MB | 93 to 134 MB | 55 to 242 MB | 116 to 456 MB |

- Error against a path-traced reference (FLIP, lower is better): 0.129 against GI-1.0's 0.256 on PicaPica, 0.063 against 0.073 on Sponza, 0.091 against 0.138 on Flying World, 0.153 against 0.226 on Bistro.
- Sampling the primary cache per pixel on Sponza: 0.54 ms at 1 sample, 0.98 ms at 8.
- Several viewers share the secondary cache, so cost grows sub-linearly with the viewer count.

## Limits

- Quality depends on the island split; seams at island borders, and neighboring pixels on different islands each allocate an entry.
- Foliage and fine geometry multiply allocations (Bistro is the one scene slower than GI-1.0).
- 8×8 hemispheres lose highlights and mirror detail.
- No transparency, translucency or volumes.
