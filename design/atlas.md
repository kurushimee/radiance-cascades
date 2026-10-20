# Atlas

Every surface that takes part in the GI has texels in one 2D atlas, laid out by the meshes' UV2 charts. Each covered texel is a cascade 0 probe, holds the radiance its surface reflects, and is where the composite reads irradiance. The texel spacing comes from the [budget](budget.md#texel-spacing): about 30,000 texels, 20 to 45 cm apart on typical game scenes.

## Contents

- [Charts from the import](#charts-from-the-import)
- [Packing](#packing)
- [Capture](#capture)
- [Probes](#probes)
- [Borders and seams](#borders-and-seams)
- [Two-sided surfaces](#two-sided-surfaces)
- [Moving objects](#moving-objects)
- [Open questions](#open-questions)

## Charts from the import

- **UV2 comes from Godot's import.** Unwrapping is editor-only, so an exported game cannot make UV2; the scene import option `meshes/light_baking` set to Static Lightmaps unwraps every mesh with xatlas, at `meshes/lightmap_texel_size` in scene units at the node's scale ([docs](../docs/lightmap_uv2.md)). Godot pads charts by one texel with bilinear padding.
- **The import texel size is the runtime spacing.** If the atlas used a coarser spacing than the import, the one-texel padding would shrink below a texel and bilinear reads would mix charts. An editor script therefore measures the scene's surface area, computes the spacing from the budget, sets it as the import texel size and reimports.
- **Each instance's rectangle** is its mesh's UV2 extent at that density. An instance scaled after import keeps its mesh's texel count, so its texels are larger or smaller in the world; the scenes in the [evaluation](evaluation.md) import with their scales applied.

## Packing

- At load, every instance's rectangle is packed into one atlas with a skyline bottom-left packer, the method Godot's lightmapper uses through stb_rect_pack ([docs](../docs/lightmap_uv2.md)).
- Small charts cost more than their area: a chart of `w × h` texels takes `(w + 2p)(h + 2p)`, so a 2×2 chart with one texel of padding takes 16 ([research](../research/sources/2026_lightmap_atlases_seams_and_packing.md#packing)). A mesh too small for a chart of its own gets a 2×2 rectangle.
- 30,000 covered texels at 50 to 70% use fit in a 256×256 atlas.

## Capture

A raster pass draws each instance into its rectangle at load, with the vertex shader placing each vertex at its UV2. It renders at 4×4 samples per texel and resolves to one value per texel:

| Value | Resolve |
|---|---|
| world position | mean of covered samples |
| geometric normal | normalized mean |
| albedo | mean of the material's albedo texture and colour |
| emission | mean emitted radiance |
| coverage | share of samples covered |

- **Materials.** Every GI mesh uses the project's `ShaderMaterial`, which writes `IRRADIANCE` in the composite anyway ([near_field.md](near_field.md#the-composite)). Its albedo and emission parameters are therefore known, and the capture binds the same textures through `texture_get_rd_texture` ([docs](../docs/compositor_and_shading.md)).
- **Raster passes in RenderingDevice** need their own framebuffer and draw list; the capture runs once at load, outside any frame callback.

## Probes

- **A texel with any covered sample is a probe.** Its position is the covered samples' mean, moved off the surface along the normal by a twentieth of a texel, as in the lab ([experiments.md](experiments.md#the-model)).
- **Its frame** has the geometric normal as its axis. The hemisphere's direction map turns with the frame ([cascades.md](cascades.md#directions)).
- **Uncovered texels are padding, not probes.** Bilinear filtering reads them, so they hold copies of a covered neighbour's value.

## Borders and seams

- **Dilation.** At load, every padding texel stores the index of the nearest covered texel of its own chart. After the last pass of each frame, padding texels copy that texel's irradiance, as Godot's lightmapper copies the first covered texel it finds ([docs](../docs/lightmap_uv2.md)).
- **Seam pairs.** At load, every triangle edge is keyed by its two vertex positions and normals; an edge that appears again with a different UV2 pair is a seam, as in Godot's lightmapper. Points sampled along each seam give pairs of texels, one on each side, with weights by length.
- **Stitching.** After the last pass, each pair of seam texels is set to their weighted mean, so the bilinear reads on both sides of a cut agree. The probes on both sides already see the same light; only the reads differ, so stitching the output is enough. The list of pairs is static and small, and the pass costs a few microseconds.
- **Why not stitch with least squares.** No real-time lightmapper solves seams that way, and the averaged output is what the composite reads anyway ([research](../research/sources/2026_lightmap_atlases_seams_and_packing.md#seams)).

## Two-sided surfaces

A double-sided material gets a second rectangle with the same layout and flipped normals. Rays that hit the back of its triangles read the second rectangle. A one-sided wall lit by the sun on one side therefore stays dark on the other, which the sealed sunlit rooms of the [evaluation](evaluation.md#scenes) test. Rays that hit the back of a one-sided triangle return black ([scene_and_tracer.md](scene_and_tracer.md#what-a-hit-returns)).

## Moving objects

Moving rigid objects have charts packed in the same atlas. Their capture is stored in object space, and their probe positions and frames are transformed each frame. Their records are retraced every frame ([scene_and_tracer.md](scene_and_tracer.md#moving-objects)).

## Open questions

- The scripting API for packing: whether Godot exposes a rectangle packer to GDScript, or the project packs with its own skyline packer (M2).
- Chart counts and atlas use on the test scenes, at their computed spacings (M2).
- Whether 4×4 samples per texel are enough for albedo on textured materials, measured against a 16×16 capture (M2).
