# Global Illumination based on Surfels (GIBS) and its PICA PICA predecessor

| | |
|---|---|
| Author | EA SEED: Henrik Halén, Andreas Brinck, Kyle Hayward, Xiangshun Bei (GIBS); Colin Barré-Brisebois et al. (Ray Tracing Gems chapter) |
| Date | SIGGRAPH 2021 (GIBS); Ray Tracing Gems, 2019 (chapter 25) |
| Kind | Talk slides (211 pages) and book chapter |
| Link | https://www.ea.com/seed/news/siggraph21-global-illumination-surfels ; slides https://media.contentapi.ea.com/content/dam/ea/seed/presentations/seed-siggraph21-surfel-gi.pdf ; talk video https://youtu.be/h1ocYFrtsM4 ; chapter https://media.contentapi.ea.com/content/dam/ea/seed/presentations/2019-ray-tracing-gems-chapter-25-barre-brisebois-et-al.pdf |

GIBS computes indirect diffuse light with hardware ray tracing on surfels, small oriented discs spawned from the G-buffer, with no precomputation, no special meshes and no UVs. It began as the surfel GI of the PICA PICA demo (2018, described in Ray Tracing Gems chapter 25) and ships in Frostbite. Surfel RC ([src-dgi](2025_coppen_surfel_radiance_cascades.md)) takes its spawning, stack allocation and transform-ID plan from it.

Page numbers below are PDF pages of the slides and printed pages of the chapter.

## Contents

- [GIBS (SIGGRAPH 2021)](#gibs-siggraph-2021)
  - [Surfels and spawning](#surfels-and-spawning)
  - [Pool and recycling](#pool-and-recycling)
  - [Acceleration structure](#acceleration-structure)
  - [Gather and leaks](#gather-and-leaks)
  - [Rays, integration and guiding](#rays-integration-and-guiding)
  - [Many lights and transparency](#many-lights-and-transparency)
  - [Performance](#performance)
  - [Talk video](#talk-video)
  - [Known problems](#known-problems)
- [Ray Tracing Gems chapter 25: Hybrid Rendering for Real-Time Ray Tracing (2019)](#ray-tracing-gems-chapter-25-hybrid-rendering-for-real-time-ray-tracing-2019)
  - [GI with surfels (p. 22-27)](#gi-with-surfels-p-22-27)
  - [Other passes](#other-passes)
  - [Timings (Figure 31, p. 28)](#timings-figure-31-p-28)

## GIBS (SIGGRAPH 2021)

### Surfels and spawning

- A surfel has a position, radius and normal (p. 13).
- The screen is split into 16×16 texel tiles. Each tile finds its least-covered texel and spawns a surfel from the G-buffer position and normal if the coverage passes a randomized threshold. A tile stops spawning once it reaches its coverage target (p. 14-17).
- Surfels are scaled so their projected size on screen stays about constant, so count and radius follow distance (p. 23).
- The G-buffer writes a per-geometry transform ID. A surfel stores its position in that transform's local space and is moved each frame from a global transform buffer that includes skinned bones. Skinned meshes write only the highest-weight bone, so surfels slip in some cases, which the lighting tolerates (p. 18-20).

### Pool and recycling

- All surfel memory is allocated up front. A GPU stack of free indices with an atomic counter serves allocation: spawning pops, recycling pushes (p. 26-29).
- The recycle decision combines the live count, the frames since the surfel last contributed, and its distance. The result is compared with a uniform random number, so less relevant surfels are more likely to go.

### Acceleration structure

- PICA PICA used a uniform grid. Each surfel is inserted into its own cell and every neighbour its radius overlaps, with radius at most one cell side (p. 30-33).
- The shipped structure is a uniform grid at the center plus a trapezoidal grid along each principal axis, whose slices thicken with distance from the center (p. 36-38). Lookups and inserts stay as cheap as in a regular grid, and the number of surfels per screen area stays about constant.

### Gather and leaks

- A pixel reconstructs its world position, finds its cell, reads the first N surfels and accumulates irradiance weighted by normal and distance. If the total weight is below 1, it adds the cell's weighted average irradiance (p. 40). N is not given.
- Each surfel keeps a radial depth function of 4×4 texels per hemisphere, initialized to the surfel's diameter. Rays that hit within the diameter update a moving average of depth and squared depth, and a Chebyshev bound gives a smooth visibility test, as in variance shadow maps and DDGI (p. 41-58).

### Rays, integration and guiding

- Content sets a total ray budget. Each surfel requests rays from its frames since last contributing (more when active), its variance (more when high) and a bonus when new; dormant surfels send just enough rays to notice change. A count pass sums the requests into a global counter and the binning pass gives each surfel a proportional share (p. 60, 75-79).
- Irradiance integrates with a modified moving average whose blend factor follows short-term mean and variance estimates, so it reacts fast to change and converges in static scenes. High variance also triggers irradiance sharing between neighbouring surfels (p. 53, 75-76, 117-122).
- Ray guiding: each surfel maps its hemisphere to a 6×6 radiance map at 8 bits per component plus one 16-bit scale per surfel, normalized after each update, and samples it by inverse CDF over all 36 texels. A quadtree in the style of Müller inspired it but was not built. Guiding helps when much light enters through large openings (p. 83-110).
- Rays are sorted by a bin built from the surfel's cell coordinate flattened to 1D, used as a spatial hash, plus the ray direction, with two counting passes and a reorder pass in the Battlefield V style (p. 123).

### Many lights and transparency

- The stress scene has 1400 lights in view. Stochastic lightcuts (Yuksel, HPG 2019) sort lights by the Morton code of their view-space position, build a tree bottom-up, choose a cut of 2 to 8 nodes and walk it stochastically. Reservoir sampling in the ReSTIR style takes 4 to 8 candidates and one shadow ray. Spatiotemporal reservoir reuse needs per-surfel or per-cell storage and was not finished (p. 127-150).
- Transparent G-buffers spawn no surfels, so transparent surfaces read ray-traced probes in a volume clipmap of 3 or 4 nested levels instead. Probes project radiance to SH (order not given) and use the same adaptive integrator with Sloan's de-ringing. A level shifts its probes when the camera leaves its center cell, newly exposed probes start from the coarser level, and level borders blend with two samples per shade or one blue-noise dithered sample (p. 155-175).

### Performance

PS5, 4K output, screen-space passes at 1080p, no spawn distance limit, no ray cutoff, 8-sample reservoirs unless noted. The worst case is an empty, converged scene.

| Scene | Result |
|---|---|
| PvZ town center, sun only | About 7 ms total on average, from the large draw distance (p. 184-186) |
| 1400-light stress scene | The default budget "about never" converges; a 1M-ray budget is still noisy after 10 s and costs about 11 ms once converging (p. 187-191) |
| Same view, 4-sample lightcuts | Near the reference within 15 frames, at higher cost (p. 141-154) |
| 140-light internal demo | Fast convergence, cheaper than the PvZ street view |
| Roaming PvZ, 1800p checkerboard | "Quite a bit faster" than the 4K test (p. 200-202) |

- Filtering averages about 0.2 ms, and applying the surfels is dominated by the lighting pass (p. 179-181).
- The 3-level probe clipmap solve is "very reasonable", and sampling it in a full-resolution 900p pass costs about 0.2 ms (p. 203-206).

### Talk video

The recorded talk (https://youtu.be/h1ocYFrtsM4, 47:39, read from English auto-captions) is given by Henrik Halén, with Kyle Hayward (Frostbite) from 26:27, and adds numbers and remarks the slides leave out.

- The algorithm began in 2018 in the PICA PICA showcase and is now in Frostbite; the talk calls it still in development (00:44-01:47).
- Converged surfels drop to about one ray per frame or fewer (16:32-17:44).
- Irradiance sharing between surfels of the same cell turns a blotchy result after 64 samples into a reasonable one (25:14-26:17).
- Ray guiding does not help where light is uniform and matches the cosine lobe, and fails for very small lights, which the 6×6 map is too coarse to find (24:33-25:04).
- Many-light comparison with about 700 lights in view and 700 outside the frustum, against a reference that converges in about 5 s: after 15 frames, 2-sample random sampling is very noisy, 8-sample reservoirs are closer but leave fireflies, and 4-sample lightcuts are closest but cost more on console (32:18-33:09).
- The probe clipmap demo shows four levels and the cost test three; blue-noise dithered level selection is said to work well with their TAA (36:23, 37:57-38:08, 44:08).

| Scene | Lights | Convergence | Average cost |
|---|---|---|---|
| PvZ town center, sun only | none local | about 3.5 s | about 7 ms |
| Stress test, view 1 | about 1400 in view | never at the default budget; about 10 s with a 1M-ray budget | about 11 ms after converging, with a spike at spawn |
| Stress test, view 2 | about 1400 | about 7 s with reservoirs, about 5 s with 4-sample lightcuts | about 11.3 ms with lightcuts |
| Internal demo, constrained view | about 140 | about 2 s | about 5.5 ms |
| PvZ roaming path | not stated | already converged | about 5.4 ms |
| PvZ roaming path, 1800p checkerboard | not stated | already converged | about 3.4 ms |

The costs are GIBS's whole per-frame cost while it accumulates over seconds, so they bound what a temporal surfel cache spends per frame, not what a converged single-frame result costs (inference).

### Known problems

- Procedural geometry keeps spawning and recycling surfels, and high-detail geometry over-spawns (p. 204).
- Planned: combining with SSGI, sharing guiding data between surfels, ReSTIR-style guiding, light visibility per cell, and reservoirs per cell or surfel.
- Not given: pool size, bytes per surfel, grid dimensions, the surfel irradiance format, the probe SH order, and N in the gather.

## Ray Tracing Gems chapter 25: Hybrid Rendering for Real-Time Ray Tracing (2019)

The chapter describes the PICA PICA renderer, in which only GI, transparency and translucency require ray tracing, while shadows, reflections and AO can be rasterized or traced (p. 2-3).

### GI with surfels (p. 22-27)

- 250,000 rays per frame for diffuse interreflection and up to 250,000 surfels, so one ray per surfel per frame. GI costs 0.35 ms on Turing for 250,000 surfels.
- A surfel holds position, normal, radius and irradiance in a pre-allocated array. Spawning uses an atomic counter fed by the least-covered pixel of each 16×16 tile, with probability proportional to the pixel's projected world area so a wall coming into view does not spawn a burst. The counter resets only on scene reload, and there is no recycling.
- Surfels remember their object and follow animated objects each frame.
- Irradiance per surfel comes from a one-segment path: one ray whose hit reads the previous frame's surfel result, which gives multiple bounces over time. New surfels get more paths, falling to one per frame.
- Surfels are splatted with smoothstep distance attenuation, a Mahalanobis metric that squashes the falloff along the normal (Lehtinen et al.), and an angular falloff. A world-space grid of surfel lists culls and looks them up. Coloured multi-bounce SSAO is multiplied in.
- Disoccluded areas start dark (the "first frame" problem). Recycling was not needed for the demo, and LOD for open worlds is left as research.
- The multiscale mean estimator updates `x_{n+1} = lerp(x_n, x_{n+1}, k)` with adaptive `k`. Listing constants: short-window blend 0.08; variance blend 0.5 × 0.08 = 0.04; firefly clamp `0.1 + shortMean + 8·dev`; inconsistency blend 0.08; variance-based reduction clamped to [1/32, 1]; catch-up blend clamped to [1/256, 1]; `vbbr` blend 0.1; luma weights (0.299, 0.587, 0.114).

### Other passes

- Shadows (p. 3-7): rays start from depth-reconstructed positions, penumbrae come from cone sampling with Halton points rotated per pixel, `TMin = max(1, |pos|)·1e-3`, and the filter is a single-scalar SVGF variant with a Karis bounding-box clamp, a Salvi variance box and a 5×5 footprint.
- Reflections (p. 8-14): half resolution, a quarter ray per pixel, sampled from the microfacet distribution only, with rays below the horizon regenerated. Reconstruction sums `colour(hit)·localBrdf(hit)/hitPdf` over a neighbourhood normalized by the weights, then a bilateral pass. Reprojection uses motion vectors or hit points with `w = exp2(−10·luma((rgb − mean)/dev))`.
- AO (p. 14-16): one or two cosine-weighted rays per pixel with a per-scene maximum length, filtered like shadows; the reference used 1000 spp.
- Transparency (p. 16-19): texture-space parameterization per object, Snell refraction or a microfacet BTDF, Beer's law absorption, and a recursion limit set by the performance target. Translucency (p. 20-21) traces one scattering ray per texel per frame and accumulates with an adaptive moving average.
- Halton indexing (p. 29-30): `((h2inv(x % 256, 8)·76545 + h3inv(y % 256, 6)·110080) % m_increment) + i·186624`, with bit reversal for base 2, digit reversal for base 3 and primes up to 131 for 32 dimensions. The chapter calls the listing pseudocode; `m_increment` is never defined and `sampleIndex` is undeclared.

### Timings (Figure 31, p. 28)

Volta is a Titan V and Turing ran pre-release drivers.

| Pass | Volta (ms) | Turing (ms) | Speedup |
|---|---|---|---|
| Shadows 1 / 2 / 4 / 8 / 16 spp | 1.48 / 2.98 / 5.89 / 11.53 / 23.54 | 0.44 / 0.77 / 1.31 / 2.33 / 4.65 | 3.3 / 3.9 / 4.5 / 4.9 / 5.0× |
| AO 1 spp, max distance 0.5 / 2 / 20 m | 1.67 / 2.18 / 2.50 | 0.54 / 0.62 / 0.62 | 3.0 to 3.6× |
| AO 2 spp | 3.41 / 4.48 / 5.08 | 0.88 / 1.01 / 1.01 | 3.8 to 4.4× |
| AO 4 spp | 6.71 / 8.81 / 10.03 | 1.48 / 1.64 / 1.64 | 4.5 to 5.3× |
| AO 8 spp | 13.27 / 17.44 / 19.85 | 2.55 / 3.02 / 3.02 | 5.2 to 5.7× |
| AO 16 spp | 26.56 / 34.90 / 39.96 | 4.90 / 5.82 / 5.82 | 5.4 to 6.0× |
| Reflections | 2.97 | 1.45 | 2.0× |
| Transparency and translucency | 0.47 | 0.25 | 1.9× |
| GI (250,000 surfels) | 1.70 | 0.35 | 4.8× |

The table was rebuilt from the PDF's text order, and its speedups match the printed ratios.
