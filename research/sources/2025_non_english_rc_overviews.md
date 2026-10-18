# Non-English radiance cascades overviews

Two overviews in other languages add a few points to the English sources. Both are introductions; neither describes an implementation.

## Habr: Radiance Cascades, a new look at global illumination

| | |
|---|---|
| Author | heavychevy |
| Language | Russian |
| Date | 2025-04-07 |
| Link | https://habr.com/ru/articles/897956/ |

The article restates the paper's core ideas: the penumbra condition (Δp ∼ D, Δω ∼ 1/D) and the interval sum L_{0,∞} = L_{0,r1} + β_{0,r1}·L_{r1,r2} + …, where β is the transparency of an interval. It frames RC as an approximation of the rendering equation limited to one indirect bounce.

Points it adds, none backed by a cited source:

- Near cascades are recomputed fully or partly each frame. Far cascades update less often or through temporal filters such as reprojection.
- To sample a point, pick the cascade by distance, read the nearest probes in it, and interpolate over both position and direction.
- Cascades are stored in octahedral or cube-map textures, which keep direction storage compact and even and make interpolation simpler.
- Path of Exile 2 is said to use cascades of several hundred probes with 128×128 textures at about 3 ms per frame. No source is given, and the 2023 talk gives no such numbers.

In the comments, the author says the method has no limits on camera placement, in reply to a question about top-down cameras.

## LIRIS GDL talk: Irradiance Volumes – Radiance Cascades, 1996–2026

| | |
|---|---|
| Author | not named; a talk in the GDL reading group of the LIRIS Origami team |
| Language | French |
| Date | 2026-03 (file creation date) |
| Link | https://projet.liris.cnrs.fr/origami/topics/gdl/gdl_talk_84/radiance_cascades.pdf |

The 31 slides place RC in the history of probe-based GI.

- Irradiance volumes (Greger, Shirley, Hubbard and Greenberg, 1998) discretize a 5D function: 3D position plus 2D direction. In 1996 this meant a static scene, precomputation and interpolation. Since about 2010 it means a dynamic scene with partial real-time probe updates.
- A table compares probe GI methods. Light-field probes (McGuire et al. 2017) used 1024×1024 octahedral maps. DDGI (Majercik et al. 2019) uses octahedral maps, a 3D grid of varying resolution, ray tracing with alpha blending, and an 8-probe cage query with variance and Chebyshev bias terms. The newest column, from an unnamed paper, uses 8×8 irradiance and 16×16 visibility octahedral maps with a single self-shadow bias term.
- The slides list what classic probe methods leave undefined: the spatial and directional resolution, the interpolation between probes, and the interpolation between hierarchy levels. Lumen is described as four levels (per-pixel AO, per-pixel probes, sparser world probes and an environment map) with no rule for choosing their precision.
- RC answers these with the penumbra condition. If probes are spaced farther apart, direction resolution must rise, and the reverse.
- The talk adds the interval constraint: each level also covers its own distance interval. With Δp ∼ 2^i, Δω ∼ 1/2^i and Δt ∼ 2^i, each level doubles its interval length and its direction count. N texels at level 0 give 2N texels for the whole hierarchy.
- So if level 0 can be stored and built in real time, the whole hierarchy probably can too.
- The interval constraint is what makes the sampled function possible to reconstruct and interpolate.
- Path of Exile 2 (2023) is described as a "2D + 1D" cascade in image space. Sparse 3D RC is described as a spatial hash storing probes around the camera, with probes built by hardware ray tracing.
