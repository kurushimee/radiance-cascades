# Atlas

Every surface that takes part in the GI has texels in one 2D atlas, laid out by the meshes' UV2 charts, and the composite reads irradiance at the texels. The cascade 0 probes hold the radiance the surfaces reflect: a texel that covers enough surface is a probe of its own, and the texels of smaller charts share probes. The texel spacing comes from the [budget](budget.md#texel-spacing), which plans for about 30,000 probes, 20 to 45 cm apart on typical game scenes. The test scenes get 25,000 to 84,000, the most where small charts are many: on Bistro's exterior, 70,406 of its 84,196 probes are groups of small charts (plan 004 M2).

## Contents

- [Charts from the import](#charts-from-the-import)
- [Packing](#packing)
- [Capture](#capture)
- [Probes](#probes)
- [Borders and seams](#borders-and-seams)
- [Two-sided surfaces](#two-sided-surfaces)
- [Moving objects](#moving-objects)

## Charts from the import

- **UV2 comes from Godot's import.** Unwrapping is editor-only, so an exported game cannot make UV2; the scene import option `meshes/light_baking` set to Static Lightmaps unwraps every mesh with xatlas, at `meshes/lightmap_texel_size` in scene units at the node's scale ([docs](../docs/lightmap_uv2.md)). Godot pads charts by one texel with bilinear padding.
- **The import texel size is the runtime spacing.** If the atlas used a coarser spacing than the import, the one-texel padding would shrink below a texel and bilinear reads would mix charts. An editor script therefore measures the scene's surface area, computes the spacing from the budget, sets it as the import texel size and reimports.
- **Each instance's rectangle** is its mesh's UV2 extent at that density. An instance scaled after import keeps its mesh's texel count, so its texels are larger or smaller in the world; the scenes in the [evaluation](evaluation.md) import with their scales applied.

## Packing

- **Rectangles.** An instance's rectangle is its mesh's lightmap size: xatlas's atlas in texels, with UV2 the texel position over that size ([docs](../docs/lightmap_uv2.md)). xatlas strips the atlas's outer padding, so charts touch the rectangle's edge. Each rectangle gets one texel of padding on every side, which matches the two empty texels xatlas keeps between charts. An instance with a two-sided surface gets a second rectangle for the backs.
- **Packer.** At load, `Geometry2D.make_atlas` packs the rectangles into one atlas. It is the packer Godot exposes to scripts, and it tries power-of-two widths up to 4096, so a wider rectangle is an error.
- Small charts cost more than their area: a chart of `w × h` texels takes `(w + 2p)(h + 2p)`, so a 2×2 chart with one texel of padding takes 16 ([research](../research/sources/2026_lightmap_atlases_seams_and_packing.md#packing)).
- **On the test scenes** the atlas runs from 220×160 texels on the Cornell box to 2048×3160 on Bistro's exterior. The built scenes' few large charts cover 48 to 78% of it; the downloaded scenes' many small charts, each with its gap, cover 19 to 21% (plan 004 M2).

## Capture

At load the capture finds each texel's surface at 4×4 sample points. For each point a raster pass at atlas resolution draws every triangle into its instance's rectangle at its UV2, shifted so that each pixel centre falls on that point, and keeps the covering triangle. A compute pass then adds the triangle's surface at the point to the texel's sums, along with the world area the point stands for. The passes run in a fixed order, so the sums come out the same on every load. A resolve turns the sums into one value per texel:

| Value | Resolve |
|---|---|
| world position | mean of covered samples |
| normal | normalized mean of the interpolated vertex normals |
| albedo | mean of the material's albedo texture and colour |
| emission | mean emitted radiance |
| coverage | share of samples covered |
| world area | sum of the covered samples' areas |

- **Normals.** The interpolated vertex normal is the one the path tracer and Godot's lightmapper shade with; a face normal would make curved surfaces faceted. Where the vertex normals turn to the face's back, the face normal stands in.
- **Materials.** Every GI mesh uses the project's `ShaderMaterial`, so its albedo and emission parameters are known. The capture reads them through the tracer's material table, which binds the same textures through `texture_get_rd_texture` ([docs](../docs/compositor_and_shading.md)). An alpha-tested surface counts only where its alpha reaches the material's scissor.
- **Textures are read at their full-resolution level**, as the path tracer reads them. Godot averages mipmaps in sRGB terms ([docs](../docs/scene_import.md#textures-used-in-3d)), so reading at the footprint of a sample made the textured scenes' albedo 1.3 to 3.1% darker. At 4×4 points, the albedo is within 0.2% of a 16×16 capture's on average, and 4.5 to 10.5% apart texel by texel where a texture's detail is finer than a texel. A gather reads many probes, so that spread averages out, while a bias would not (plan 004 M2).
- **Raster passes in RenderingDevice** need their own framebuffer and draw list; the capture runs once at load, outside any frame callback.

## Probes

- **A texel covered by at least half a texel of world surface is a probe of its own.** xatlas gives every small part of a mesh, such as a leaf or a bolt, a chart of its own, and such a chart's texels cover a fraction of a texel of surface. A probe for each would cost a full probe's records for almost no light.
- **A texel with less surface joins a neighbour.** It reads the probe of its own that covers the most world area among its eight neighbours. Charts lie at least two texels apart, so that probe is on the same chart.
- **The rest group.** Texels with no such neighbour belong to charts smaller than a texel. They group per instance by world cell, one texel across, and by normal class, the normal's largest component and its sign. Each group is one probe at the area-weighted mean of its texels. The groups' sums are in fixed point and their keys are sorted on the CPU, so the probes come out the same on every load.
- **Position.** A probe sits at its surface's mean position, moved off the surface along the normal by a twentieth of a texel, as in the lab ([experiments.md](experiments.md#the-model)). The mean of a curved surface lies behind it, inside a column or a prop, where the probe's rays would meet back faces and return black. So a probe whose ray along its normal meets the back of a one-sided surface within half a texel first moves out to it.
- **Its frame** has the normal as its axis. The hemisphere's direction map turns with the frame ([cascades.md](cascades.md#directions)).
- **The map** sends every texel to the probe whose light it reads, and a hit reads the probe of the texel it lands in.

## Borders and seams

- **Dilation.** At load, every texel that no sample covered takes the probe of the nearest covered texel within two texels, ties going to the lower index, as Godot's lightmapper copies the first covered texel it finds ([docs](../docs/lightmap_uv2.md)). Charts lie at least two texels apart, so the nearest covered texel belongs to the chart whose bilinear reads reach the padding. The map carries the dilation, so it costs nothing per frame, and a hit inside an uncovered texel reads its neighbour's probe.
- **Seam pairs.** At load, every triangle edge is keyed by its two vertex positions and normals; an edge that appears again with a different UV2 pair is a seam, as in Godot's lightmapper. Points sampled along each seam give pairs of texels, one on each side, with weights by length.
- **Stitching.** After the last pass, each pair of seam texels is set to their weighted mean, so the bilinear reads on both sides of a cut agree. The probes on both sides already see the same light; only the reads differ, so stitching the output is enough. The list of pairs is static and small, and the pass costs a few microseconds.
- **Why not stitch with least squares.** No real-time lightmapper solves seams that way, and the averaged output is what the composite reads anyway ([research](../research/sources/2026_lightmap_atlases_seams_and_packing.md#seams)).

## Two-sided surfaces

An instance with a double-sided surface gets a second rectangle with the same layout and flipped normals. Rays that hit the back of its triangles read the second rectangle. A one-sided wall lit by the sun on one side therefore stays dark on the other, which the sealed sunlit rooms of the [evaluation](evaluation.md#scenes) test. Rays that hit the back of a one-sided triangle return black ([scene_and_tracer.md](scene_and_tracer.md#what-a-hit-returns)).

## Moving objects

Moving rigid objects have charts packed in the same atlas. Their capture is stored in object space, and their probe positions and frames are transformed each frame. Their records are retraced every frame ([scene_and_tracer.md](scene_and_tracer.md#moving-objects)).
