# kajiya: global illumination overview (Stachowiak)

| | |
|---|---|
| Author | Tomasz Stachowiak (h3r2tic), later a developer of Tiny Glade |
| Form | Design document in the kajiya renderer repository, 2022 |
| Link | https://github.com/h3r2tic/kajiya/blob/main/docs/gi-overview.md |
| Code | https://github.com/h3r2tic/kajiya (Apache-2.0, Rust and HLSL, needs hardware ray tracing) |

A research renderer's real-time GI: half-resolution ReSTIR GI for the first bounce and a sparse world irradiance cache for the rest. It needs hardware ray tracing, so none of it runs as-is in Godot's compute shaders. The draft that adds screen probes to Godot's HDDAGI names kajiya as one of its two models, and its irradiance cache answers a question world-space RC also faces: where to put sparse probes so that thin walls do not leak.

## Cost

1920×1080 on a Radeon RX 6800 XT, 8.4 ms in all: G-buffer 1.15 ms, indirect diffuse about 2.3 ms, irradiance cache about 0.55 ms, reflections about 2.2 ms, sun shadows 0.52 ms, SSAO 0.17 ms, sky 0.1 ms. The cache usually holds fewer than 16k entries, which trace 128k G-buffer rays and 384k shadow rays per frame.

## Irradiance cache

- 12 camera-aligned clipmaps of 32³ cells, allocated sparsely: a dense 32×32×32×12 indirection array points into payload buffers of up to 65,536 entries. Entries are allocated on first use and freed a few frames after their last.
- The cache is queried only by rays, never by screen pixels: a diffuse or reflection ray asks it for the remaining bounces at its hit point. Hits that are visible on screen reproject last frame's result instead and never touch the cache.
- **Output-sensitive trace origins:** a cell has no fixed probe point. Each query location is a candidate, and every frame one candidate per cell is picked at random to trace from. When the camera is inside a building, the queries come from inside, so the cell lights the inside; this is what keeps thin sunlit walls from leaking, a case where any cache with a fixed point runs out of resolution.
- **Ranking:** queries from the cache's own rays would let outside cells vote for outside positions. Each entry stores the lowest bounce index that reached it (1 for rays from the screen, 2 for rays from a rank-1 entry, and so on), and a new vote counts only if its rank is lower or equal. This removed leaks into a torch-lit room inside repeated Sun Temple scenes.
- **Normal bias:** the lookup point moves along the surface normal, so the underside of a table lit from above stays dark more often.
- Each entry keeps temporal reservoirs stratified over a 4×4 octahedral map; 4 texels make new candidates per frame, lit by the sun and by the cache itself (single-buffered, races accepted), plus 4 validation rays and 16 short accessibility rays. A compute pass turns them into L1 SH irradiance.
- Known problems: the cache is blocky and not temporally stable, which shows wherever reflections read it directly; stochastic interpolation between entries reduced this.

## Indirect diffuse

- One pixel per 2×2 tile traces a ray each frame from its G-buffer position, with a hemispherical (not cosine) distribution. A hit that is visible on screen reprojects last frame's irradiance; other hits are lit from the ray payload.
- Results feed ReSTIR reservoirs at half resolution: temporal reuse with `M` clamped to 10, permutation sampling, then two spatial passes (radius 12 to 32 pixels with 8 samples, then 6 to 16 with 5), shrinking as reservoirs fill and in corners by SSAO. The last pass marches up to 6 half-resolution depth taps toward each neighbor's hit for a rough contact shadow.
- **Near and far split:** spatial reuse erodes small-scale bounce in corners, which are not a large source of variance anyway. The resolve takes near hits from the raw rays traced that frame and far hits from the reservoirs, blended by a threshold that grows with distance from the camera. This recovered the corner detail.
- **Validation:** every third frame retraces all reservoir samples instead of generating new ones; a sample whose radiance changed has its `M` cut, and one that hits the same point has its radiance updated, allowed to grow at most 10× to avoid fireflies. Validation frames also trace short rays so the near field stays filled.
- A 4-sample resolve to full resolution, a temporal filter with color box clamping, and TAA follow.

## Lessons for RC

- Small bright emitters defeat ReSTIR's reuse, and the document suggests treating them as explicit lights, the same advice RC sources give for emitters smaller than cascade 0's spacing.
- Newly disoccluded areas are noisy until reservoirs refill.
- SSAO is used only as a guide for filter radii and bilateral weights, never to darken lighting.
