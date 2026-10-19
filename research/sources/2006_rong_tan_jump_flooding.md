# Jump flooding for distance fields

| Source | Authors | Date | Link |
|---|---|---|---|
| Jump Flooding in GPU with Applications to Voronoi Diagram and Distance Transform | Guodong Rong, Tiow-Seng Tan | 2006, ACM I3D | https://www.comp.nus.edu.sg/~tants/jfa/i3d06.pdf |
| Fast Voronoi Diagrams and Distance Field Textures on the GPU With the Jump Flooding Algorithm | Alan Wolfe (demofox) | 2016-02-29 | https://blog.demofox.org/2016/02/29/fast-voronoi-diagrams-and-distance-dield-textures-on-the-gpu-with-the-jump-flooding-algorithm/ |
| Actually Making Signed Distance Field Textures With JFA | Alan Wolfe (demofox) | 2016-03-02 | https://blog.demofox.org/2016/03/02/actually-making-signed-distance-field-textures-with-jfa/ |

Almost every 2D RC builds its scene distance field with a jump flood each frame, and the same algorithm extends to 3D voxel grids. Its cost depends on the grid size, not the number of seeds.

## Algorithm

1. Seed texels store their own coordinate; all others store an empty marker.
2. Run `log2(n)` passes with steps `n/2, n/4, …, 1`. In each pass a texel reads the 9 texels at offsets `{−k, 0, k}²` (27 in 3D) and keeps the seed closest to itself. Ping-pong two textures.
3. One more pass writes the distance to the stored seed.

Halving the step is the point: doubling it (1, 2, 4, …) gives many more errors. Errors are rare and sit mostly at single texels near Voronoi vertices.

## Variants

- **JFA+1:** one extra pass with step 1. **JFA+2:** two extra passes with steps 2 and 1. The paper recommends JFA+2: same speed in practice and close to exact. Several RC repositories skip or lose the final step-1 pass by a ping-pong parity mistake, which leaves visible errors.
- A 5-tap plus pattern worked as well as 3×3 in the blog's tests; splitting the flood into an x pass and a y pass gave many errors.
- In 3D (simulated on a CPU at 512³) the results were close to exact, and the authors expect 3D to be more accurate than 2D since more paths reach each point.

## Signed distance

A plain flood gives distance outside the shapes only. Flood again with seeds and empty space swapped to get the inside distance, then combine: `signed = outside − inside` (the blog stores `0.5 + 0.5·outside − 0.5·inside` in a normalized texture).

## Wolfe's posts

The 2016-02-29 post:

- An `N × N` texture takes `log2(N)` passes with offset `2^(log2(N) − passIndex − 1)` from pass 0, so 4, 2, 1 for 8×8. The texture need not be square or a power of two, though the formula assumes it.
- Each read is skipped if it holds no seed. Empty texels hold (0, 0, 0, 0) and seeds their own coordinate (32-bit: x in RG and y in BA; 16-bit float: x in R and y in G). A seed at pixel (0, 0) is therefore indistinguishable from an empty texel (derived, not in the post).
- Weighted seeds multiply or add a per-seed weight to the computed distance ("Weight Pts" and "Add Wt Pts" demos); the post gives no formula beyond that.
- The brute-force reference loops over every seed per pixel.
- The post says the error is very small in practice and gives no metric, timing or hardware. It notes JFA extends to volume textures with more reads per pass, and that the distances can serve as raymarch step hints.

The 2016-03-02 addendum:

- An unsigned field has a pixelated zero contour that breaks under zoom. Moving the threshold to 0.5 helps but fattens shapes.
- The fix floods the source and the inverted source and stores `0.5 + 0.5·clamp(|seed_out − p|/8, 0, 1) − 0.5·clamp(|seed_in − p|/8, 0, 1)`. The surface sits at 0.5, and distances past 8 px of the generated texture saturate. The listing writes `fFragCoord` for `fragCoord`.
- A full-resolution field still looks wrong when magnified, since a distance field only helps through interpolation. A field at 1/4 the size per axis gives clean edges and holds up to 20× zoom on top of the magnification.
- The demo is Shadertoy ldVGWc.
