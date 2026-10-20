# Lightmap atlases: chart generation, seams, coverage and packing

| | |
|---|---|
| xatlas | https://github.com/jpcy/xatlas, `source/xatlas/xatlas.h` lines 173 to 232, read at master |
| The Witness | Ignacio Castaño, "Lightmap Parameterization", http://www.ludicon.com/castano/blog/articles/lightmap-parameterization/ |
| Unity | Seam stitching, https://docs.unity.cn/2019.2/Documentation/Manual/Lightmapping-SeamStitching.html; generating lightmap UVs, https://docs.unity3d.com/2019.2/Documentation/Manual/LightingGiUvs-GeneratingLightmappingUVs.html |
| The Last of Us | Iwanicki, "Lighting technology of The Last of Us", SIGGRAPH 2013, abstract at https://history.siggraph.org/?p=139809; the talk itself was not reachable |
| Seamless | Liu, Ferguson, Jacobson and Gingold, "Seamless: Seam erasure and seam-aware decoupling of shape from mesh resolution", ACM TOG 36(6), SIGGRAPH Asia 2017, https://cragl.cs.gmu.edu/seamless/ (abstract and project page; the PDF was not read) |
| Conservative rasterization | Microsoft, https://learn.microsoft.com/en-us/windows/win32/direct3d11/conservative-rasterization |
| Lumen | Epic, "Lumen Technical Details", https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine (page for UE 5.8) |
| Packing | Jylänki, "A Thousand Ways to Pack the Bin", 2010, https://github.com/juj/RectangleBinPack (PDF in the repository); stb_rect_pack, which states it uses Skyline Bottom-Left |
| Read | 2026-10-20. Quotes from documentation pages came through a page extractor. |

How lightmap atlases are generated, padded, stitched at seams and packed, collected for storing radiance or probes on surface charts. One engine's lightmapper, read in its source, is in the engine notes of the repository ([docs](../../docs/lightmap_uv2.md)).

## Contents

- [xatlas options](#xatlas-options)
- [Chart generation and padding in production](#chart-generation-and-padding-in-production)
- [Seams](#seams)
- [Coverage: conservative rasterization and dilation](#coverage-conservative-rasterization-and-dilation)
- [Lumen's surface cache cards](#lumens-surface-cache-cards)
- [Packing](#packing)
- [Not found](#not-found)

## xatlas options

**Chart options.**

- `maxChartArea` and `maxBoundaryLength` stop a chart from growing past a size; 0 means no limit.
- Growth is scored by weighted metrics: normal deviation 2.0, roundness 0.01, straightness 6.0, normal seams 4.0 (above 1000, normal seams are always respected) and texture seams 0.5.
- `maxCost` 2.0: a chart stops growing once the weighted sum exceeds it, so lower values give more charts.
- `maxIterations` 1; higher values give better charts.
- `fixWinding` enforces consistent winding of the texture coordinates.

**Pack options.**

- `padding`: pixels of padding around each chart.
- `texelsPerUnit`: a 1×1 quad at 32 texels per unit covers about 32×32 texels; 0 estimates it from `resolution`.
- `resolution`: 0 gives one atlas; a resolution with `texelsPerUnit` set gives as many atlases of exactly that size as needed.
- `bilinear` (default on): leaves room around charts for the texels bilinear filtering reads.
- `blockAlign` (default off): aligns charts to 4×4 blocks.
- `bruteForce`: slower, best placement; otherwise placement is random.
- `rotateCharts` and `rotateChartsToAxis` (default on), and `maxChartSize`.
- The result reports `utilization` (0.8 means 20% empty space), the chart count and the texels per unit.

The header and readme give no typical chart counts for complex meshes.

## Chart generation and padding in production

**The Witness** (Castaño):

- The team chose not to invest in parameterizations guaranteed to be seamless.
- Charts follow normal seams more strictly and in proportion to their angle.
- Packing marks every texel a chart touches plus one texel of padding, places charts in order of parametric area, and minimizes a metric of extent and perimeter that gives mostly square atlases.
- The article does not describe least-squares seam stitching.

**Unity** (2019.2 manual):

- Pack Margin is the margin between charts in pixels, assuming the mesh fills a 1024×1024 lightmap: default 4, range 1 to 64. Charts need to be at least two full texels apart to avoid bleeding.
- Hard Angle (default 88°) splits charts at sharper edges; Angle Error defaults to 8%.
- The manual mentions dilating chart texels to avoid black edges.

## Seams

- **Why they appear.** Unity's manual explains that the GPU cannot blend texel values between charts that sit apart in the lightmap. Seamless's authors write that seams are unavoidable when parameterizing most surfaces.
- **Unity's seam stitching** is off by default because it lengthens the bake; its algorithm is not described.
- **The Last of Us.** The SIGGRAPH 2013 abstract names seams caused by UV layout among the problems solved. A search summary, not verified, describes stitch points spaced evenly along each UV-split edge and solved by least squares. The talk was unreachable.
- **Seamless** characterizes seam-free textures as the null space of a linear operator and uses it for seam-aware decimation and for showing signals without seams. It is not a texel-blending method for lightmaps.
- **Finding seam pairs.** One engine keys each triangle edge by its endpoint positions and normals and records a seam when the same edge appears with different UVs ([docs](../../docs/lightmap_uv2.md#how-the-lightmapper-handles-seams-coverage-and-packing)). Unity creates seams by splitting at its hard angle.

## Coverage: conservative rasterization and dilation

- Conservative rasterization runs the pixel shader for every pixel a primitive touches even partly. Microsoft lists texture atlases and light map generation among Tier 1's uses.
- Without it, lightmappers rely on dilation: uncovered texels near a chart copy a covered neighbour, so bilinear reads at chart borders do not pull in empty texels.

## Lumen's surface cache cards

- Lumen generates an automatic parameterization of the nearby scene's surfaces, the Surface Cache, from capture positions called Cards, generated offline per mesh.
- By default a mesh gets at most 12 Cards; the limit is set per mesh. Skeletal meshes get six cards around their pre-skinned bounds.
- Uncovered areas show pink in the Surface Cache view.
- Card resolution and the stored attributes are not on Epic's page. Community posts name console variables for card resolution, atlas size and per-frame capture counts, unverified.

## Packing

- **Jylänki's survey** (Section 5) finds MAXRECTS best overall; Skyline best when packing online into one bin at a time; Guillotine asymptotically faster than MAXRECTS but slightly worse; Shelf, the simplest family, worth choosing only for simplicity.
- **stb_rect_pack** implements Skyline Bottom-Left.

**Derived.** At a texel size `s` in scene units, a surface of world area `A` needs about `A / s²` texels before padding, and padding adds a ring of `p` texels around every chart. Many small charts therefore cost far more than their area: a chart of `w × h` texels takes `(w + 2p)(h + 2p)`, so a 2×2 chart with one texel of padding takes 16 texels for 4 of surface.

## Not found

- Typical xatlas chart counts for complex meshes.
- Castaño's least-squares seam stitching, and a verified account of Iwanicki's.
- Real-time seam fixing in Enlighten, Frostbite or Lumen's surface cache.
- Lumen's card resolution and attribute layout from engine source.
