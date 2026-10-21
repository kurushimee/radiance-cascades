# Lightmap UV2

Read in the 4.7.2-stable source and checked again in NVIDIA's fork at `135dff3887`; paths are relative to the engine repository.

## Unwrapping happens at import

`ArrayMesh.lightmap_unwrap` is bound as an editor method, and the `xatlas_unwrap` module that implements it builds only into editor builds (`modules/xatlas_unwrap/config.py`); without it the call returns `ERR_UNCONFIGURED`. An exported game cannot generate UV2, so meshes get it at import: the scene import option `meshes/light_baking` set to Static Lightmaps unwraps every mesh, and `meshes/lightmap_texel_size` (default 0.2, range 0.001 to 100) appears only in that mode. The result is cached beside the source file as `<source>.unwrap_cache`.

## Texel size

The texel size is in scene units at the mesh node's scale: xatlas gets `texelsPerUnit = 1 / texel_size`, and the unwrap transforms the vertices by the scale of the node's transform only, dropping its rotation and translation (`ImporterMesh::lightmap_unwrap_cached` in `scene/resources/3d/importer_mesh.cpp`, which the import runs). A surface of area `A` therefore covers about `A / texel_size²` texels before padding.

## xatlas options

Godot sets `fixWinding`, `padding = 1`, `blockAlign` and `maxChartSize = 4094`, and leaves every other chart and pack option at its xatlas default, which includes `bilinear` padding (`modules/xatlas_unwrap/register_types.cpp`).

## How the lightmapper handles seams, coverage and packing

`modules/lightmapper_rd/lightmapper_rd.cpp` and its shaders:

- **Seams.** Every triangle edge is keyed by its two vertex positions and normals. When the same 3D edge appears again with a different UV2 pair, the pair is recorded as a seam; the same UV2 pair means the edge is shared in the atlas and needs nothing. A third occurrence of an edge is skipped as bad geometry.
- **Blending.** Each seam is drawn as a line from one side's UV2 into the other's, blended into the lightmap. The triangles are then drawn into the depth buffer only, as a mask, and the seam lines are drawn again at eight one-texel offsets around their position. A table gives the centre pass weight 0.5, the four edge offsets 0.2 and the four corner offsets 0.1, but every pass uses the centre's 0.5.
- **Dilation.** Uncovered texels take the color of the first covered texel (alpha above 0.5) found on eight rays out to `4 × supersampling` texels; nothing is averaged.
- **Packing.** Each mesh's rectangle grows by `max(2, denoiser range) × supersampling` texels of padding, and `Geometry2D.partial_pack_rects` places the rectangles with stb_rect_pack's Skyline Bottom-Left packer, opening a new atlas layer whenever some do not fit.
