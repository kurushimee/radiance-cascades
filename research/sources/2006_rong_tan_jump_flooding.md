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
