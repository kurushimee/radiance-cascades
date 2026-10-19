# Cascade layout and merging

How cascades are laid out in memory and merged: where probes sit, how directions are numbered in 2D and mapped in 3D, the interval formulas and cascade counts each implementation uses, position-first and direction-first storage, pre-averaging, the merge kernels, the order in which cascades are traced and merged within or across frames, cascade −1, the final gather, and storage formats. The theory behind the parameters (penumbra condition, scaling criteria, the choice of the cascade 0 interval) is in [core theory](core_theory.md); merge fixes for ringing and leaks are in [artifacts and fixes](artifacts_and_fixes.md); each 2D code's full design is in [2D implementations](2d_implementations.md), [2D articles and demos](2d_articles_and_demos.md) and [2D Shadertoys](2d_shadertoys.md) and each 3D design in the 3D topics.

Statements marked "derived" were computed from the sources' formulas; "inference" marks conclusions drawn here.

## Probe placement

Most codes put probes at cell centers: probe `k` of cascade `c` sits at `(k + 0.5)·s0·2^c`, with `s0` the cascade 0 spacing ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#direction-first-index-math), [radiance-cascades.com demo](../sources/2026_rc_community_site_and_wiki.md#index-math-per-cascade), [LegitCascades](../sources/2024_sannikov_legitcascades.md#layout)). Each upper probe then sits at the center of a 2×2 (2D) or 2×2×2 (3D) block of lower probes, so a lower probe is a quarter of an upper cell from its nearest upper probe on each axis and its bilinear weights are 0.75 and 0.25 (derived).

Variants:

- **Vertex-centered** probes look aliased ([merging notes](../sources/2026_merging_and_ringing.md#debugging-routine)).
- **Offset against stacked.** imnethen's configurable 2D build puts probes at `0.5 + s_c·i`; its Offset layout moves them back by `0.5·(S^c − 1)/(S − 1)` cascade 0 spacings, which puts each coarse probe midway between finer ones, while Stacked puts it on top of a fine probe ([merging notes](../sources/2026_merging_and_ringing.md#links)).
- **Half-cell offsets in 3D.** Split RC places probes at `Δs_n·(v + ½)` so cascades do not align and interpolation error spreads evenly, and gives directions the same half offset ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#parameters-and-why)). Rulkens places higher cascades between the probes below ([Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md#method)).
- **HRC** grows spacing only along the travel axis, `p = (x·2ⁿ, y)` ([holographic RC](holographic_rc.md#geometry)).
- **Screen-fit grids.** LegitCascades spaces cascade `k` probes at `screen_size/N_k`; tlegoc fixes the cascade count and the top cascade's vertical probe count and stretches the texture width to the screen, which keeps the layout symmetric at any aspect ratio with extra probes at the sides ([LegitCascades](../sources/2024_sannikov_legitcascades.md#layout), [blog posts](../sources/2024_rc_blog_posts_and_slides.md#tlegoc-vulkan-blog-post)).

Formulas for the four upper probes around a lower probe, all equivalent for cell-centered 2D grids:

| Source | Top-left upper probe | Weights |
|---|---|---|
| [Merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix) | `floor((probe − 1)/2)` | `fract(probe·0.5 + 0.25)` |
| GM Shaders bilinear fix | `floor((probe − 1)/2)`, then `+(0,0), (1,0), (0,1), (1,1)` | `0.25 + (probe − (2·probeN1 + 1))·0.5` per axis |
| fad's mtlBzX | `q = round(pf) − 1` with `pf = (p + 0.5)/2` | `w = pf − q − 0.5` |
| Coppen | `floor(dest_center/bilinear_size − 0.5)` | `fract` of the same, bilinear in the usual order |

The upper probes must be found from the lower probe's position, not from where its ray ends ([merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix)). Probe placement and the bilinear fix's ray offsets must use the same convention: sampling at the origin should give 0.25 to each of the four upper probes in every cascade ([merging notes](../sources/2026_merging_and_ringing.md#debugging-routine)). Coppen's own figure of the weights is wrong by the author's note, since they must sum to 1 ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#merging-spatially)).

**Domain edges.** Past the outermost probe row lookups clamp, which flattens falloff near the border ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#other-implementation-notes)). Reads outside the texture must return zero, or light wraps around to the opposite edge ([merging notes](../sources/2026_merging_and_ringing.md#debugging-routine)).

## Directions

### Flatland

Direction `j` of `n` points at the bin center `2π(j + 0.5)/n`, with vector `(cos θ, −sin θ)` in GM Shaders and the community demo ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#direction-first-index-math), [demo](../sources/2026_rc_community_site_and_wiki.md#index-math-per-cascade)). GM Shaders' Part One writes `ray_index/ray_count·2π`, the left edge of the bin ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#raymarching-from-probes-index-math)).

With `K` directions per parent, upper directions `K·j … K·j + K − 1` subdivide lower direction `j`: upper ray `b·idx + i` has angle `(idx + (i + 0.5)/b)·2π/N_k`, so the `b` upper rays averaged into one texel cover exactly the angular bin of the lower ray (derived, [jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#45-rc-fragment-algorithm)). The Desmos ray-layout graph centers cascade `c`'s `4^(c+1)` bins at `360°·n/4^(c+1) − 360°/(8·4^c)`, each with four children in cascade `c + 1` ([merging notes](../sources/2026_merging_and_ringing.md#links)).

**Forked** layouts start every group of child rays at one shared point and draw them from the parent's center angle: GM Shaders' bilinear-fix shader starts each ray on its coarser parent direction (`thetaNm1 = (floor(preavg/4) + 0.5)·TAU/4^c`), and mxcop's animation helper draws forked child rays the same way ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#bilinear-fix-in-detail-shd_radiancecascades_bilinearfixfsh), [merging notes](../sources/2026_merging_and_ringing.md#links)). Forking trades angular resolution for continuous paths ([artifacts and fixes](artifacts_and_fixes.md)).

**Odd branching:** with ×3 directions per cascade a third of the upper rays line up with lower rays and can be extended without interpolation; it made little visible difference ([merging notes](../sources/2026_merging_and_ringing.md#other-fixes)).

### Direction maps in 3D

A 3D cascade needs a map of the sphere (or hemisphere) to texels with four properties (inference, from the sources below): children that nest 4 to 1 across cascades, so a parent texel is exactly the union of its children; known solid angle per texel, so means and cosine sums are unbiased; a cheap inverse, since merging and gathering look directions up; and edges that hardware filtering can cross, if filtered reads are used.

| Map | Directions per level | Nests 4 to 1 | Equal area | Used by |
|---|---|---|---|---|
| Octahedral | `N²`, `N` doubling | yes, 2×2 texel blocks | no, up to 5.2× | tmpvar's 3D grid, erhe, three-rc, Gavras, X3XfRM, tauray (RCPG), Love and Deepspace, SultanAladin, mpalenque/sim, KingTheFifth's DX12 build, DDGI-style irradiance tiles |
| Equal-area octahedral (Clarberg) | `N²` | yes | yes | Dell'Ova and ClaikoCode (`OctToFloat3EqualArea`), Coppen's surfel RC, ClaikoCode's screen probes |
| Equal-area cylindrical (Lambert) | `2n × n` | yes, `(⌊j/2⌋, ⌊k/2⌋)` | yes | Split RC and its Unity and Unreal ports |
| HEALPix | `12·N_side²` | yes, nested indexing | yes | DexRT's 3D solver |
| Cube faces | `6·4^c` | yes | no (smaller solid angles near the corners) | Rulkens's cube mapper; tonsa1's near-equal-area cube warp |
| Tetrahedral faces | `4·4^c` | yes | no | Rulkens's tetrahedral mapper |
| Latitude-longitude | `(64 << i)·(32 << i)` and others | yes on the grid | no, `sin θ` | a voxel 3D repository, KingTheFifth's screen probes |
| Spherical Fibonacci | any `N` | no | nearly | a voxel 3D repository (merging `4k … 4k + 3`) |

**Octahedral.** The map stores a direction as a point in `[−1, 1]²`. Cigolle et al. find it the best general unit-vector encoding: fast, close to uniform, and near the lowest error at every bit size. Divide by the L1 norm, project the upper half onto the square and fold the lower half outward ([Cigolle](../sources/2014_cigolle_octahedral_unit_vectors.md#encode-and-decode), [glossary](supporting_techniques.md#direction-parameterizations)):

```glsl
vec2 sign_not_zero(vec2 v) { return vec2(v.x >= 0.0 ? 1.0 : -1.0, v.y >= 0.0 ? 1.0 : -1.0); }

vec2 oct_encode(vec3 v) {
    vec2 p = v.xy / (abs(v.x) + abs(v.y) + abs(v.z));
    return v.z <= 0.0 ? (1.0 - abs(p.yx)) * sign_not_zero(p) : p;
}

vec3 oct_decode(vec2 e) {
    vec3 v = vec3(e, 1.0 - abs(e.x) - abs(e.y));
    if (v.z < 0.0) v.xy = (1.0 - abs(v.yx)) * sign_not_zero(v.xy);
    return normalize(v);
}
```

- `sign()` returns 0 for 0, which broke the first published code at the square's edges; `sign_not_zero` fixes it. Narkowicz's 2014 form folds with `OctWrap(v) = (1 − |v.yx|)·sign(v.xy)` taking the sign of 0 as +1, pyalot's 2015 gist is the same map with `y` as the pole axis, and Stubbe's 2017 decode drops the outer conditional: `n = (f.x, f.y, 1 − |f.x| − |f.y|); t = max(−n.z, 0); n.xy += (n.xy >= 0) ? −t : t` ([tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md)).
- The details behind those three forms: the wrap that swaps components and signs, after Meyer et al. 2010, came from a reader of Narkowicz's post (Tobias Zirr) and removes the seam where `z` changes sign, so no epsilon is needed. Narkowicz compares only visually, on reflective spheres with world normals in R8G8B8A8, against XYZ and spherical coordinates (bad distribution and speed); Crytek's best-fit normals are more precise but need three channels and a 512² lookup. In the comments Narkowicz finds artifacts hard to spot at 10 bits per component, uses 10:10 for view-space normals with stable specular, calls 12:12 overkill, and notes that octahedral at equal bit depth looks worse than XYZ, its point being two channels instead of three. pyalot's gist also has `normalToUvSphOct`, which maps azimuth `atan(|x|, |z|)/(π/2)` and polar angle `atan(|xz|, y)/(π/2)` onto the folded square (`uv = (s.x·orient, s.z·(1 − orient))·pitch`, refolded for `y < 0`): an octahedral layout whose diamond rings are equal steps in polar angle, with an `acos` path when `highdef` is 0. A static cost estimate in Stubbe's post gives 139 cycles per wavefront for the shorter decode against 175 for the standard form; inigo quilez saw no difference in WebGL, and Stubbe a 17 to 21 fps gain in a stress loop ([tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md#links-found)).
- The hemisphere variant ("hemi-oct") maps `p = v.xy/(|x| + |y| + z)` to `(p.x + p.y, p.x − p.y)` with lower error for the same bits. As a storage encoding, 16 bits (two 8-bit snorms) give 0.34° mean and 0.94° max error and 24 bits 0.02° mean; a precise encode that tries the four roundings cuts the maximum by about a third ([Cigolle](../sources/2014_cigolle_octahedral_unit_vectors.md#encode-and-decode)).
- Texel `t` of an `N×N` probe tile has direction `oct_decode((t + 0.5)/N·2 − 1)`; cascade `i` texel `(u, v)` has children `(2u … 2u + 1, 2v … 2v + 1)` in cascade `i + 1` ([erhe](../sources/2026_erhe_world_space_rc.md)).
- The paper does not cover filtering. The square's edges wrap folded, not as a modulo, so hardware bilinear filtering needs a border. RTXGI's scheme for a tile of `T = N + 2` texels: a top or bottom row texel `x` copies interior column `T − 1 − x` on its side, a left or right column texel `y` copies interior row `T − 1 − y`, and a corner copies the diagonally opposite interior corner; write the interior, then a barrier, then the border ([Cigolle](../sources/2014_cigolle_octahedral_unit_vectors.md#texel-grids-and-filtering)). tmpvar's atlas copies each border edge from the adjacent interior row or column in reverse order, index `i` to `d + 1 − i` ([tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md)).
- Weaknesses at RC resolutions: the map biases rays toward the axes and puts 8 of 16 directions on the equator ([screen-space RC](../sources/2026_screen_space_rc.md)); it is poor at low resolution ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)); its texels near the eight face centers cover about 5.2 times the solid angle of those at the six vertices, so equal-weight child averages and texel means are biased unless weighted by the Jacobian ([glossary](supporting_techniques.md#direction-parameterizations)). RCPG still prefers it for sampling, because equal-area maps need transcendental functions at every texel corner ([sampling and guiding](rc_for_sampling_and_guiding.md)).

**Equal-area octahedral.** Clarberg (page numbers are the printed journal pages) keeps the folded-square layout and replaces the projection with one built from Shirley and Chiu's concentric map ([Clarberg](../sources/2008_clarberg_equal_area_sphere_mapping.md#mapping)):

- Square to sphere (eqs. 2-5, pp. 56-58): `u = 2s − 1`, `v = 2t − 1`, `d = 1 − (|u| + |v|)`, `r = 1 − |d|`, `φ' = (π/4)·((|v| − |u|)/r + 1)` in [0, π/2] (0 when `r = 0`), `sin φ = sign(v)·sin φ'`, `cos φ = sign(u)·cos φ'`, then `x = cos φ·r·√(2 − r²)`, `y = sin φ·r·√(2 − r²)`, `z = sign(d)·(1 − r²)`. The inner diamond is the upper hemisphere and the four outer triangles the lower one. Dell'Ova's ClaikoCode code has exactly this as `OctToFloat3EqualArea` ([Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md)), and Coppen's surfel RC uses PBRT's equal-area decode ([surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md)).
- Sphere to square (sec. 3.2): `r = 1 − |z|`, `φ' = atan2(|y|, |x|)` (a polynomial arctangent of min over max in the paper), `v_i = r·2φ'/π`, `u_i = r − v_i`, reflected to `(1 − v_i, 1 − u_i)` for `z < 0`, then signs restored and `[−1, 1]²` mapped to `[0, 1]²`. The hemisphere base (eq. 1, p. 54) is Shirley and Chiu's concentric map in its first sector: `u = 2s − 1`, `v = 2t − 1`, `r = u`, `φ = (π/4)·(v/u)`, then `x = cos φ·r·√(2 − r²)`, `y = sin φ·r·√(2 − r²)`, `z = 1 − r²`.
- The area distortion is a constant π (sec. 6, pp. 67-68: `[−1, 1]²` of area 4 maps to 4π); the paper calls the plain octahedral projection an arbitrary parameterization (Fig. 2) without measuring its distortion. So a 2×2 child block is exactly a quarter of its parent in solid angle and a texel mean is the sphere mean, with no per-texel weights; the plain octahedral map needs a Jacobian weight for both (inference from constant distortion). Each edge folds about its midpoint, so the map tiles by mirrored repeat and lookups outside [0, 1)² need no special case (sec. 4.1, p. 64); bilinear weights and wrapped texel addresses take 27 SSE instructions, and 16-bit indices limit maps to 64k × 64k texels (sec. 4.2). Texels near the octahedron's edges and the poles of the outer triangles are stretched, so equal area is not equal angular spread, which matters for interval-end footprints (inference; [Clarberg](../sources/2008_clarberg_equal_area_sphere_mapping.md#for-rc)).
- Accuracy is far below a texel (forward error at most 7.49·10⁻⁶, mean 3.37·10⁻⁶; inverse at most 2.43·10⁻⁴, mean 3.19·10⁻⁶, a third of a texel on a 4k map in a few cases; Table 1, p. 63). SSE code over 256, 4k, 64k, 1M and 16M points takes 18.8, 18.7, 18.7, 22.8 and 22.8 cycles square to sphere and 23.0, 23.2, 23.2, 25.6 and 25.6 sphere to square, 3.5 to 4.2× faster than optimized scalar code and 6.5 to 8.6× faster than the standard version (the abstract says up to 9×). On one core of a 3.2 GHz Penryn (gcc 4.0.1; Tables 3-4), scalar code over 256, 4k, 64k, 1M and 16M points costs 121.9, 156.2, 160.7, 162.4 and 162.5 cycles square to sphere (77.9, 77.9, 78.0, 80.4 and 80.5 optimized), and 114.7, 145.1, 147.8, 149.1 and 149.0 sphere to square (106.9, 115.8, 115.7, 117.7 and 117.5 optimized) ([Clarberg](../sources/2008_clarberg_equal_area_sphere_mapping.md#accuracy-and-cost)).
- At 32² it comes close to a 768-direction HEALPix grid, fixes the octahedral axis bias at trivial cost, and looks better at low resolution ([screen-space RC](../sources/2026_screen_space_rc.md), [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)). The "Clarberg visualiser" ([simulationcorner.net/clarberg](https://simulationcorner.net/clarberg/main.html)) shared in those discussions is a text-free Plotly page drawing 16 blue arrows from the origin to radius 1, 64 red ones from 1 to 2 and 256 green ones from 2 to 3 (28 more calls commented out), three cascades of directions growing 4× per level on nested shells ([Clarberg](../sources/2008_clarberg_equal_area_sphere_mapping.md#the-plot-page)).

**Equal-area cylindrical.** Split RC's `encode(ω) = (frac(atan2(y, x)/2π), (z + 1)/2)` and `decode(u, v)`: `φ = 2πu`, `z = 2v − 1`, `r = √(1 − z²)`, `ω = (r·cos φ, r·sin φ, z)`. A cascade with resolution `n` has `2n × n` directions at cell centers, and the parent of `(j, k)` is `(⌊j/2⌋, ⌊k/2⌋)`, exactly 4 to 1. The paper reports that octahedral and Clarberg ([preprint](https://fileadmin.cs.lth.se/graphics/research/papers/2008/simdmapping/clarberg_simdmapping08_preprint.pdf)) mappings gave worse quality despite more uniform spacing ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#sparse-probes)); its code's `SphericalEncoder` is the same Lambert map, and its configuration uses `32·4^n` directions on a `2Θ × Θ` grid with `Θ = 4·2^n` ([Split RC implementations](../sources/2026_split_rc_implementations.md)). A Unity port uses 32 bins on a `2D × D` grid in Morton order ([plugins](../sources/2026_unity_unreal_rc_plugins.md)). Cylindrical maps need a 2:1 or π:1 aspect ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)).

**HEALPix** ([healpix.sourceforge.io](https://healpix.sourceforge.io/)). 12 base pixels in three rings (north cap, equator, south cap), each split into `N_side²` equal-area pixels on rings of constant latitude: `12·N_side²` pixels of area `π/(3·N_side²)` on `4·N_side − 1` rings with centers equally spaced in azimuth, `4·N_side` per equatorial ring and polar rings gaining one pixel per quadrant per ring (p. 7); `N_side` = 1, 2, 4, 8 gives 12, 48, 192 and 768 pixels. Nested indexing is a 4-to-1 tree at every level with equal areas throughout, exactly RC's parent-child structure; its cost is indexing, since the direction-to-pixel step needs per-zone inverses of the center formulas instead of one fold ([HEALPix](../sources/2005_gorski_healpix.md)). Equation numbers below are the paper's. The paper gives the pixel center from the index in `(z = cos θ, φ)` (sec. 5.1): in the north cap, with `p_h = (p + 1)/2`, `1 ≤ i < N_side` and `1 ≤ j ≤ 4i`, ring `i = ⌊√(p_h − √⌊p_h⌋)⌋ + 1`, `j = p + 1 − 2i(i − 1)`, `z = 1 − i²/(3·N_side²)` and `φ = (π/(2i))·(j − 1/2)` (eqs. 2-5); in the north equatorial belt, with `p' = p − 2·N_side·(N_side − 1)` and `N_side ≤ i ≤ 2·N_side`, `i = ⌊p'/(4·N_side)⌋ + N_side`, `j = (p' mod 4·N_side) + 1`, `z = 4/3 − 2i/(3·N_side)` and `φ = (π/(2·N_side))·(j − s/2)` for `s = (i − N_side + 1) mod 2` (eqs. 6-9); the south mirrors the north through `z = 0`. Nested indexing (sec. 5.2) takes `f_row = ⌊f/4⌋`, `F1 = f_row + 2` and `F2 = 2·(f mod 4) − (f_row mod 2) + 1` for base pixel `f` (eqs. 10-12), splits the index's even and odd bits into `x` and `y` (eqs. 13-14), and gives ring `F1·N_side − (x + y) − 1` and longitude `(F2·N_side + (x − y) + s)/2` (eqs. 15-18). Ring order counts pixels along rings from north to south, suited to spherical harmonic transforms; nested order gives neighbour searches and a fast Haar transform. Pixel boundaries are not geodesics (`cos θ = a + b·φ` at the equator, `a + b/φ²` in the caps; sec. 5.3, eqs. 19-22). Direction to index (`ang2pix`) is in the library, not the paper, and the site's primer describes the orderings in prose only. It had lower error than equal-area octahedral in analytic tests but is costly to build ([screen-space RC](../sources/2026_screen_space_rc.md)); DexRT's 3D solver uses 12 base directions from a HEALPix sphere with ×4 per cascade ([DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md)).

**Polyhedral subdivisions.** Rulkens rejects Fibonacci lattices because they do not nest cones across cascades and regular point sets exist only for special counts up to 20, so Rulkens subdivides a regular polyhedron (p. 13, [Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md#direction-mappers-sec-5)):

- **Cube:** 6 base directions, each face split into a `2^c × 2^c` grid per cascade, `6·4^c` directions (6, 24, 96, 384, 1536), each the normalized cell center `P = S + (½ + i)·du + (½ + j)·dv` with `du = v/2^c`, `dv = u/2^c`; a probe's block is `2^(c+1)` by `3·2^c` texels of six face sub-blocks (p. 14-17).
- **Tetrahedron:** 4 base directions, each face split into four triangles per cascade, `4·4^c` directions (4, 16, 64, 256, 1024), each the normalized barycenter `(A + B + C)/3`; one base face's directions share a contiguous index range, numbered from the bottom left (p. 17-19).
- Non-uniform cells bias a probe toward the side with more directions, so each value is weighted by `r_w = r·N·A/(4π)` with the cell's solid angle `A` from Girard's theorem (p. 20, [glossary](supporting_techniques.md#direction-parameterizations)).
- The cube mapper cost 1.38 to 1.47 times the tetrahedron and looked better, mostly for small lights, with the gap narrowing as cascades were added.

tonsa1's shader warps each cube face by `s = u·(0.7456 + 0.1239u² + 0.1305u⁴)` and `t = v·√max((1 + s²)/(2 + s² − v²), 0)` before normalizing `(s, 1, t)`; its solid-angle density stays within about ±1.3% of the mean, an almost equal-area cube map ([screen-space RC](../sources/2026_screen_space_rc.md)).

**Latitude-longitude** grids need `sin θ` weights; one voxel repository uses `(64 << i)×(32 << i)` texels (2048 directions at cascade 0) and integrates them with no solid-angle weight, which biases toward the poles (derived, [voxel 3D repositories](../sources/2026_voxel_3d_rc_repositories.md), [glossary](supporting_techniques.md#direction-parameterizations)). KingTheFifth's screen probes use `4·2^c` azimuths times `4·2^c` altitudes ([repository survey](../sources/2026_rc_repository_survey.md#screen-probes-with-voxel-intervals-kingthefifth)).

**Sets that do not nest.** A Fibonacci sphere groups child indices `4k … 4k + 3`, which share a height but spread around in azimuth, so a parent's "cone" is not a cone ([voxel 3D repositories](../sources/2026_voxel_3d_rc_repositories.md)). Lebedev and spiral sets have no merge scheme ([screen-space RC](../sources/2026_screen_space_rc.md)).

Other choices: hemisphere-only maps around a surface normal (Mathis's M3ycWt hemisphere probes; Sannikov's lXByRh, whose texel ring `r` at Chebyshev distance from the tile center sits at polar angle `(r + 0.5)·π/P` with `8r + 4` azimuths, neither octahedral nor equal-area; [Shadertoys](../sources/2023_rc_shadertoys.md#3d-and-screen-space)); spherical harmonics for cascade 0 only, since higher cascades need more angular resolution than SH1 holds ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)); and a fixed world orientation for the map rather than one aligned to each surface ([screen-space RC](../sources/2026_screen_space_rc.md)). Cross-shaped artifacts from small lights on walls tracked the cascade 0 direction count, not the octahedral Jacobian ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)).

## Intervals

Cascade intervals must tile each ray: starts form one geometric series with no gaps or overlaps, `[0, 1), [1, 4), [4, 16), …`. A common bug computes the start from one series and the length from another ([merging notes](../sources/2026_merging_and_ringing.md#parameters-that-look-like-merge-bugs)). The families in use, with `I0` or `L0` the base length:

| Family | Cascade `c` | Used by |
|---|---|---|
| Contiguous geometric, ×4 | start `I0·(4^c − 1)/3`, length `I0·4^c` | GM Shaders (with `sign(c)` so cascade 0 starts at 0), the old jason.today article |
| Contiguous geometric, any `A` | start `L0·(A^c − 1)/(A − 1)`, length `L0·A^c` | imnethen (contiguous for any angular factor) |
| Cascade 0 from 0, then powers | `[4^(c−1), 4^c]·L0`, cascade 0 `[0, L0]` | fad's mtlBzX and forks (`L0 = 4·|res|/(4^5 − 1)`, top interval just past the diagonal), Desmos graph (`[4^(c−1)·i, 4^c·i]`, `i = 2√2`), jason.today's article (`start = base^(k−1)/side`, `len = base^k/side`) |
| Powers from `L` | `[4^c, 4^(c+1)]·L`, cascade 0 from 0 | MctXRr (`10⁻³·W`), MfXyRj and lcfcR2 (`1.5·10⁻³·W`), Coppen's `interval_range` |
| Testbed | starts `(4^k + 1)·L0`, `L0 = 1.5·10⁻³·W` | 4ctXD8 |
| With cascade −1 offset | `[c0·(D^k − 1) + cm1, c0·(D^(k+1) − 1) + cm1]`, `cm1` one cascade 0 spacing | LegitCascades `Scaling.ls` (chronicl's patch drops `cm1`; past the top cascade the far value is zero radiance with zero transmittance) |
| Overlapped | start `B^(i−1)·M`, length `((1 + 3·ov)·B^i − i²)·M` | the community demo (`ov = 0.1`) and Osborne's slide demo; jason.today's final code (below) |
| Small fixed scale | `0.2·[4^c, 4^(c+1)]` px, cascade 0 `[0, 0.8]` | codyjbennett's wfyyDz, ffl3Rf and the cbenn fiddle |
| Offset by one | `[4^n − 1, 4^(n+1) − 1]·⅔` px | youssef_afella's 3cKczD |
| ×2 per cascade | `[2^n, 2^(n+1)]·√2` px, cascade 0 from 0 | Neylick's w3XSz4 (directions ×2) |
| Overlapping by design | `[0, 1], [1, 3], [2, 6]·20/256` UV | SJarod's tf2XRc |
| Cross-faded ends | `[4^(n−1), 4^n]·7` px with smooth edges | Suslik's mlSfRD |
| Split RC | `[t_{n−1}, t_n]`, `t_n = t0·l^n`, `t_{−1} = 0`, `t0 ≈ 1.6·Δs0` | Split RC; code cutoff `1.6·ds0·2^d·4^n` for LOD `d` |
| DexRT 2D | `[0, 1.5], [1.5, 6], [6, 24], …`, top extended out of the domain | DexRT v0.2 and the 2025 paper |
| DexRT 3D | ends `6·2^n` cells | DexRT's 3D solver |
| Rulkens | `[0, 1/100)`, then `[2^(c−1)/100, 2^c/100)` | Rulkens (unit cube, 192³ grid) |
| Kaméus | `[4^i·scale, 4^(i+1)·scale]`, top to infinity | Kaméus's SPWI |
| Exact condition | from penumbra geometry | kornel's RadiCalc ([core theory](core_theory.md#sizing-from-the-exact-condition)) |

Sources for the rows: [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#probe-and-ray-index-math-post-version-cascadetexelinfo), [merging notes](../sources/2026_merging_and_ringing.md#links), [Shadertoys](../sources/2023_rc_shadertoys.md#parameters-across-the-2d-implementations), [Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#cascade-gathering), [LegitCascades](../sources/2024_sannikov_legitcascades.md#intervals), [demo](../sources/2026_rc_community_site_and_wiki.md#cascade-parameters-and-defaults), [slides](../sources/2024_rc_blog_posts_and_slides.md#osborne-slides), [jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#32-generalizing-to-n-cascades-article), [Split RC](../sources/2026_freeman_split_radiance_cascades.md#parameters-and-why), [Split RC implementations](../sources/2026_split_rc_implementations.md), [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md), [Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md#parameters), [Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md).

Notes on the families:

- Coppen's code gives cascade 0 the range `[0, 4·base_length]` and cascade `i ≥ 1` `[4^i, 4^(i+1)]·base_length` (length `3·4^i·base_length`), while the prose calls `base_length` the cascade 0 length; the source does not say which is intended (derived, [Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#cascade-gathering)).
- The community demo adds `length_i` to the start point (`rayEnd = rayStart + dir·interval.y`), and its cascade 0 to 5 intervals at 512² (probes 512², 256², 128², 64², 32² and 16²; lengths 1.3, 4.2, 16.8, 74.2, 316.8 and 1306.2 px) run 0 to 1.3, 1 to 5.2, 4 to 20.8, 16 to 90.2, 64 to 380.8 and 256 to 1562.2 px; at base 16 the `modifierHack` is 4 and the intervals reach 21,263 px, at base 64 it is 8 and they reach 42,566 px (derived, [demo](../sources/2026_rc_community_site_and_wiki.md#derived-cascade-table-not-stated-in-the-source)). Its source calls the `modifierHack = p if B < 16, else √B` rule "hand-wavy", added because it smoothed base ray counts other than 4; jason.today's article says artifacts were much worse at base 16 and suspects "a bug somewhere" ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#32-generalizing-to-n-cascades-article)).
- jason.today's final code starts cascade 0 at `1·base^−1` (0.25 px for base 4) and computes `L = modInt·((b^k − prev) + overlap·b^(k+1)/1.41)` with `SQRT_2 = 1.41`, giving intervals 0.25 to 1.977, 2 to 8.908, 8 to 35.63, 32 to 142.5, 128 to 570.1 and 512 to 2280 px at its 512² defaults (rays interval 2.0, overlap 0.04) ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#11-derived-values-default-settings)). Its early two-pass demo split one ray at `partial = 0.125` UV, `[0, partial]` for the base pass and `[partial, √2]` for the high-ray pass, and found about 0.02 UV (about 8 px), half a 16 px probe, a reasonable split ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#31-two-levels-ping-pong-interval-split)).
- Several shaders measure the ray length from the start point and others from the probe center; a tracer that marches a fixed length from the start gets the bilinear fix wrong, since the fix's rays run between two points rather than for one interval length ([merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix)).

### Overlap

An interval can be extended past the next cascade's start:

- GM Shaders adds `length(vec2(L0·2^(c+1)))`, the diagonal of the upper cascade's spacing, which the post calls a minimal overlap ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#probe-and-ray-index-math-post-version-cascadetexelinfo)); the original repository adds it only for `c > 0`, the optimized base shader for every cascade, and the bilinear, nearest and interlaced variants replace it with forked starts.
- clVcD3 adds an overrun of `2^(n+1)` px; jason.today and the community demo scale the length by an overlap fraction (0.04 and 0.1; the community slider labelled "%" feeds its raw value in as the fraction); bevy_ridiculous_ssgi's cascade `n` reaches `2^n·cascade_0_dist·√(n + 1)` with an optional overlap into the previous interval ([Shadertoys](../sources/2023_rc_shadertoys.md#parameters-across-the-2d-implementations), [blog posts](../sources/2024_rc_blog_posts_and_slides.md#this-week-in-bevy)).
- Overlap of about `√2` upper spacings fixes leaks but not ringing; large overlaps give halos and count partial absorbers twice ([merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs)). With a watertight tracer the bilinear fix needs no overlap, while parallax fixes depend on it ([merging notes](../sources/2026_merging_and_ringing.md#why-it-works)).
- Staggering the boundary instead of overlapping it, by direction parity (kornelski's gear teeth) or with smooth edges (mlSfRD), is covered in [artifacts and fixes](artifacts_and_fixes.md).

## Cascade count

Enough cascades that the top interval passes the farthest distance a ray must reach, or a top cascade whose rays run to infinity. Formulas in use:

| Source | Count |
|---|---|
| GM Shaders Part One | `factor = ceil(log4(diagonal/interval0))`, `intervalstart = interval0·(1 − 4^factor)/(1 − 4)`, `count = ceil(log4(intervalstart)) − 1`; its 1920×1080 example (diagonal about 2203 px) gives no `interval0`, so its count is not stated |
| GM Shaders original repository | `min(floor(log4(4·diag)) − 1, max)` = `floor(log4(diag))`, capped by `ceil(log2(E/√angular))` (9 at its defaults; 5 used) |
| GM Shaders optimized repository | `ceil(log4(diag))` (6 at 1920×1080) |
| GM Shaders visual demo | `floor(log2(size/√angular)) − 1` |
| jason.today and the community demo | `ceil(log(diagonal)/log(base)) + 1` (6 at 512² with base 4; 4 at base 16, 3 at base 64); the `+1` is "the most naive way" to let a corner light reach the far corner |
| fad | 5, with `L0` chosen so the top interval ends just past the diagonal |
| Merging notes | about `log4` of the screen diagonal, about 5 at 512², rarely more than 6 |
| Osborne | the top cascade's rays run until they leave the domain; add cascades if its angular resolution is too coarse for the boundary |
| Split RC | 4, with environment-map lookups on top-cascade misses |

Sources: [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#cascade-count), [GM inconsistencies](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#inconsistencies-in-the-repository), [jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#32-generalizing-to-n-cascades-article), [demo](../sources/2026_rc_community_site_and_wiki.md#cascade-parameters-and-defaults), [merging notes](../sources/2026_merging_and_ringing.md#scaling-and-setups), [radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#method-restated-more-precisely), [Split RC](../sources/2026_freeman_split_radiance_cascades.md#parameters-and-why).

For contiguous ×4 intervals starting at 0 with base `i0`, the top interval ends at `i0·(4^N − 1)/3`, so covering a diagonal `D` needs `N = ceil(log4(1 + 3·D/i0))` (derived). With `i0 = 1` px this is 6 at 512², 7 at 1080p, 1440p and 4K; with `i0 = 2` it is 6 at 512² and 1080p and 7 at 1440p and 4K; with `i0 = 4` it is 5 at 512² and 6 above (derived). The count grows by one per 4× in diagonal, so resolution barely moves it.

## Storage layouts

### Position-first and direction-first

| Item | Position-first | Direction-first |
|---|---|---|
| Block in the texture | one probe, a tile of its direction texels | one direction, holding that direction for every probe |
| Neighbouring texels | the directions of one probe | the same direction at neighbouring probes |
| Merge reads for one lower ray, 2D 2x/4x | 16 (4 upper probes × 4 child directions), blended in the shader | 1 hardware-filtered read with pre-averaging, the four upper probes blended by the sampler |
| Debugging | per-probe tiles | per-direction images, easier to read |

GM Shaders built both; its post first claimed the direction-first version doubled performance at twice the screen area, then said in an update that it is not actually faster, because of a GameMaker issue at the time, and keeps it for debugging ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#optimization-2-direction-first-layout-and-hardware-interpolation)). Direction-first makes reads of one direction across neighbouring probes contiguous, which improves cache coherence during merging ([wiki](../sources/2026_rc_community_site_and_wiki.md#direction-first-probes)), and Coppen notes the same locality benefit without giving index math ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#cascade-memory)).

Index math, position-first (GM Shaders original; `A` cascade 0 rays, here 4):

- `count_c = A·4^c` rays per probe, tile side `size_c = √count_c = 2^(c+1)`, probe cell `floor(texel/size_c)`, ray index `r = (texel.y mod size_c)·size_c + (texel.x mod size_c)` row-major, `θ = 2π(r + 0.5)/count_c`, probe center `(cell + 0.5)·L_c·texel_size` with `L_c = spacing·2^c`; every cascade holds `E²` rays ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#position-first-index-math-original-shaders)).
- Coppen's version: `dir_coord = texel_coord % probe_size`, `dir_index = dir_coord.x + dir_coord.y·probe_size.x`, `dir_count = probe_size.x·probe_size.y`; a probe with 16 intervals is a 4×4 texel block ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#cascade-gathering)). The article does not say how `probe_pos` comes from the texel coordinate, and its gathering code writes only radiance; the alpha (visibility) write is described but not shown.

Index math, direction-first (GM Shaders optimized, `S = 2^i` direction grid side, `E` texture side):

- Direction group side `E/2^i` (the code's `E_x` by `E_y`, 1920 × 1088 in the optimized build); direction block `(bx, by) = floor(uv·2^i)`, index `d = bx + 2^i·by`; probe position `p = (x mod E/2^i, y mod E/2^i)`; `E²/4^i` probes with `4^i` stored directions each; actual rays `k = 4d + j`, `θ = (k + 0.5)·2π/4^(i+1)` (the shader's `TAU/(pinfo.angular·4.0)`, with `pinfo` the `probe_info` derived from the texel's position (the post's struct holds `angular`, `linear`, `size`, `probe`, `index`, `offset`, `range` and `scale`), whose struct field `angular` holds `4^i` while the local `angular` is `2^i`); probe origin `(p + 0.5)·L0·2^i`. Every cascade stores `E²` texels and casts `4·E²` rays ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#direction-first-index-math)).
- jason.today's and the community demo's tile layout is the same: `s × s` tiles of `floor(E/s)` texels, tile `T = tile.x + s·tile.y` numbered from the bottom left, each texel the mean of the `b` rays `b·T + i` ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#45-rc-fragment-algorithm), [demo](../sources/2026_rc_community_site_and_wiki.md#index-math-per-cascade)). LegitCascades uses `texel = C·(dir mod B.x, dir div B.x) + probe` ([LegitCascades](../sources/2024_sannikov_legitcascades.md#layout)), three-rc `texel = d·G_L + q` in 3D ([three-rc](../sources/2025_bennett_three_rc.md)), and ClaikoCode `probeIndex = pixel mod probesPerDim`, `rayIndex = floor(pixel/probesPerDim)` ([screen-probe repositories](../sources/2026_screen_space_probe_repositories.md)). DexRT's `DIR_BY_DIR` flag is the same choice ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#dexrt-v020-and-the-data-archive)).

GM Shaders keeps row-major order and calls a Z-order curve not worth the complexity ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#probe-and-ray-index-math-post-version-cascadetexelinfo)); Split RC stores directions in Morton order so the 4 children of a parent are contiguous, which makes merging coherent and lets warp shuffles average them ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details)). Index math should be integer: float rounding caused wrong merges ([merging notes](../sources/2026_merging_and_ringing.md#debugging-routine)).

### Pre-averaging

Each stored texel holds the mean of the rays it will be merged into below: cast 4 rays, store one value. Memory and merge lookups both drop by 75% (16 to 4 lookups), and with direction-first storage the remaining 4 become one filtered fetch, which put a full 2D RC in under 100 lines of shader code ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#optimization-1-pre-averaging), [wiki](../sources/2026_rc_community_site_and_wiki.md#pre-averaging)). In GM Shaders' optimized code pre-averaging cannot be disabled, and cascade 0 always holds the displayable result with 4 rays per pixel. fad pre-averaged from the start: cascade 0 stores one value per probe, the mean of 16 rays, and each texel of cascade `n ≥ 1` the mean of 4, so cascade `n` stores `16·4^(n−1)` texels per probe ([Shadertoys](../sources/2023_rc_shadertoys.md#mtlbzx-fad-the-original-2d-implementation)). Split RC's higher cascades store pre-averaged cone values directly ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details)).

Pre-averaging interacts with the fixes: averaged upper texels no longer hold separate directions, which weakens the parallax fix noticeably; the rays of an upper group start at slightly different points, so the four bilinear-fix rays do not land exactly on them (tracing 16 rays, one to each upper ray start, is very slightly better and not worth 4× the rays); and it should be skipped on cascade 0 when cascade −1 gathering is used ([merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix)).

### Containers

| Container | Used by |
|---|---|
| One texture per cascade | GM Shaders original, Rulkens |
| Two ping-pong textures reused for every cascade | GM Shaders optimized, the community demo, jason.today, imnethen (two buffers of `u32` pairs) |
| One atlas with cascade regions stacked vertically (regions may halve or double instead) | LegitCascades |
| A cube map holding all cascades | fad's mtlBzX |
| 3D textures with the angle on Z, repeat wrap and hardware filtering | the shipped 2D Switch game |
| 2D array texture, one layer per cascade or per probe slice | tmpvar's 3D grid (4096² × 7 layers, RGBA32F), tauray |
| Hash map plus an indirection buffer of each probe's directions | Split RC, sparse 3D RC |

Sources: [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#optimized-version-radiancecascades-optimized), [demo](../sources/2026_rc_community_site_and_wiki.md#render-targets-and-formats-default-settings), [merging notes](../sources/2026_merging_and_ringing.md#scaling-and-setups), [LegitCascades](../sources/2024_sannikov_legitcascades.md#layout), [tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md), [RCPG](../sources/2026_tauray_rcpg_path_guiding.md), [Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details).

**Non-square screens.** GM Shaders' optimized build pads the render size to a multiple of `error_rate = 2^(count − 1)` (32 with 6 cascades, so 1920 stays and 1080 becomes 1088), and its cascade textures are `floor(render/linear)`, 1920 × 1088 at spacing 1, and measures distances in pixels scaled by the render diagonal; the original assumed square sizes throughout ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#optimized-version-radiancecascades-optimized)). jason.today scales rays by the shortest side so they stay on a unit circle ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#32-generalizing-to-n-cascades-article)).

## Merge kernels

The merge combines each lower interval with the interpolated upper value behind it ([core theory](core_theory.md#the-merge-operator)). In 2D vanilla RC the lower ray reads the four nearest upper probes and, in each, the `K` child directions of its own direction.

- **In the shader, position-first.** Coppen's loop: for each of the 4 child directions `d`, for each of the 4 bilinear probes `b`, fetch `bilinear_texel = bilinear_index·bilinear_size + (dir_index·4 + d)` laid out row-major, merge with the destination interval, weight by `weights[b]`, then add `radiance/4.0` per child direction; 16 fetches per lower interval ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#merging-algorithm)). The article leaves `cast_interval` to any ray caster that returns the radiance from start to end, leaves `destination_interval`, `textureFetch` and the space of `dest_center` undefined, does not show where `merged` is written, and uses `bilinear_size` both for the bilinear probe's size in pixels and for the direction-texel width in the index math. It never calls its merge the bilinear fix, but merging the lower interval with each upper probe before weighting is that fix ([bilinear fix](artifacts_and_fixes.md#the-bilinear-fix), derived). The division by 4 is the cone average over the 4 children, and weighting alpha is correct because the weights sum to 1 ([core theory](core_theory.md#the-merge-operator)).
- **One hardware fetch.** With direction-first storage and pre-averaging, lower ray `k` at probe `p` reads upper direction tile `k` at `p/2 + 0.25` in upper texel units: an even probe index lands on an upper probe and an odd one halfway, and adding 0.25 gives the 0.25/0.75 weights. The lookup is clamped inside the tile so the filter never reads a neighbouring direction: GM Shaders' post clamps to `[1, size − 1]` before adding 0.25 while its base shader adds first; its Final variant clamps to `[0.5, size − 0.5]`; the community demo clamps `(probe + 0.5)/s` to `[0.5, U − 0.5]`, with `U = floor(E/s^(i+1))` the upper grid size; jason.today's article clamps to `[0.5, upperSize − 0.5]` and its final code to `[1, upperSize − 1]`, a clamp that also fixes a light leak along edges when the interval split is 0 ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#merge-post-version-merge), [demo](../sources/2026_rc_community_site_and_wiki.md#merge-from-the-upper-cascade), [jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#34-light-leak-clamp-article)). The post's "2,2 becomes 2.25" contradicts its own steps, which give 1.25. When cascade 0 probes are spaced `P` pixels apart the fetch reads mip `log2(P)` of the upper texture ([demo](../sources/2026_rc_community_site_and_wiki.md#merge-from-the-upper-cascade), [jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#45-rc-fragment-algorithm)).
- **Two samples instead of four.** Two neighbouring upper samples with weights `a` and `b` can be read with one filtered fetch, `a·s0 + b·s1 = lerp(s0, s1, b/max(a + b, 1e−7))·(a + b)`; rays cost the same, so this only trims merge reads ([merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix)). Youssef-Afella's Unity port reads with one bilinear fetch ([Unity 2D repositories](../sources/2024_unity_2d_rc_repositories.md)).
- **Weights.** The specified bilinear weights are 0.25 and 0.75; GM Shaders' original shader uses `0.33 + (probe − (2·probeN1 + 1))·0.33`, labelled "smoother", with the specification version commented out. That shader merges only rays that did not hit, skips the top cascade (index ≥ count − 1), averages the 4 rays `4·index + i` fetched from each of the 4 upper probes at `floor((probe − 1)/2)` and its neighbours, and forces alpha 1; its upper fetch uses fractional offsets inside the tile, which select the right texel only under nearest filtering, and the original never calls `gpu_set_tex_filter`, so the filter is whatever the engine default is at that point ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#position-first-index-math-original-shaders)).
- **Fewer probes.** The nearest kernel reads only `floor(probe/2)` and pixelates in 2×2 blocks; the interlaced kernel picks one of four upper probes by `mod(2·px + py, 4)` with a dithered look; lcfcR2 reads one random upper probe ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#shader-variants-optimized-folder), [Shadertoys](../sources/2023_rc_shadertoys.md#parameters-across-the-2d-implementations)). Their effect on ringing is in [artifacts and fixes](artifacts_and_fixes.md).
- **Other grids.** Simplex grids cut interpolation lookups from 4 to 3 in 2D and from 8 to 4 in 3D, and a hexagonal 2D grid interpolates 3 neighbours slightly better than bilinear at the same cost ([Dddfz7](https://www.shadertoy.com/view/Dddfz7)); bicubic merging from four hardware taps ([GPU Gems 2, ch. 20](https://developer.nvidia.com/gpugems/gpugems2/part-iii-high-quality-rendering/chapter-20-fast-third-order-texture-filtering)) helps vanilla a little, and whether it helps with the bilinear fix is disputed ([merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs)).
- **Hardware filtering is wrong for fixes.** Any kernel that blends per-probe results after per-probe tracing must interpolate by hand from direct texel reads; leaving hardware filtering on is the most common reason a bilinear fix shows banding or still leaks ([merging notes](../sources/2026_merging_and_ringing.md#building-the-bilinear-fix)). GM Shaders' original fetch with fractional offsets works only under nearest filtering, which its code never sets ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#position-first-index-math-original-shaders)).
- **Adaptive skipping.** Skipping angular rays in upper cascades where about 8 nearby lower probes agree saved about 19% of rays at above 50 dB PSNR over 50 scenes, and an aggressive 40% mode was visible ([mebyz's adaptive-radiance-cascades demo](https://mebyz.github.io/adaptive-radiance-cascades/), [merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs)).

**3D grids** blend 8 upper probes trilinearly and 4 child directions ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#other-implementation-notes)). Variants: SultanAladin's 8-probe merge samples each upper probe along the direction toward the lower interval's end, a 3D bilinear fix ([repository survey](../sources/2026_rc_repository_survey.md)); erhe's `visibility_masked` mode drops upper probes inside geometry or invisible from the lower probe and renormalizes ([erhe](../sources/2026_erhe_world_space_rc.md)); Split RC's sparse trilinear sums the neighbours that exist and divides by their total weight ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#sparse-probes)); Rulkens merges the upper directions forming a cone with the lower one, trilinearly interpolated from the upper probes (p. 20-21, with `|D|` and the merge order not stated), `T_m = T_c·(1/|D|)·ΣT_{c+1}` and `L_m = L_c + T_c·(1/|D|)·ΣT_{c+1}·L_{c+1}` (the printed formula drops the `T_c` that the code applies) ([Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md#collection-and-merge-sec-55)). Split RC averages the 4 contiguous Morton children with warp shuffles and shares upper-probe lookups across a thread block ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details)).

A 3D direction-first layout, one probe grid per direction stored as a region of a 3D texture, would let one hardware trilinear fetch blend all 8 upper probes, the 3D analogue of GM Shaders' one-fetch merge, at the cost of a one-texel clamp margin per region (inference, from GM Shaders' layout and the Switch game's 3D textures).

## Tracing and merging order

Merging runs top-down: cascade `N − 1` first, then each cascade reads the merged one above it. Tracing has no such order, so codes split into three schedules:

- **Trace all, then merge.** tlegoc traces every cascade in parallel, then merges top-down with one dispatch each, each waiting on the one before ([blog posts](../sources/2024_rc_blog_posts_and_slides.md#tlegoc-vulkan-blog-post)). GM Shaders' original runs an intervals pass over all cascades, then a merging pass from `count − 1` down through a temporary surface ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#original-version-radiancecascades)).
- **Trace and merge in one pass per cascade, top-down.** GM Shaders' optimized build and the community demo draw one full-screen pass per cascade from the top down, each reading the cascade above; only two textures exist ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#optimized-version-radiancecascades-optimized), [demo](../sources/2026_rc_community_site_and_wiki.md#pipeline-per-update-default-settings)).
- **One pass per frame across frames.** Shadertoy and LegitScript run fixed passes once per frame, so each cascade merges with last frame's upper cascade and a change takes `N` frames to reach cascade 0: 5 for fad's line, 6 for the testbed line, about 10 for w3XSz4's 11 cascades, while youssef_afella's 3cKczD fits five levels into one frame and codyjbennett's shaders settle in a 2-frame ring ([Shadertoys](../sources/2023_rc_shadertoys.md#parameters-across-the-2d-implementations), [LegitCascades](../sources/2024_sannikov_legitcascades.md#frame-structure), [history](history_and_landscape.md#first-public-implementations-and-the-shadertoy-lineage)). tf2XRc composites all cascades per pixel instead.

The fused top-down schedule needs memory for only two cascades at a time, the merged one above and the one being built, so peak cascade memory is `M_i + M_{i+1}` instead of `Σ M_i` (derived). For constant-size cascades (2D 2x/4x, screen and surface probes) that is `2·M0` against `N·M0`; for a 3D grid with ×4 directions it is `1.5·M0` against about `2·M0`. The price is that tracing cannot overlap merging, and each cascade is one dependent dispatch.

jason.today's "Reduce Demand" mode splits the work over two frames, but its code never reads the first frame's partial cascades on the second. In full mode (the default) `frame` stays 0 and every frame runs every pass. With the mode on, `rcPass` stops at `stop = (frame == 0 and not fullPass) ? halfway + 1 : lastLayer`, so frame 0 runs the seed, flood and distance field and the cascades from the top down to `halfway + 1`, with `halfway = floor((firstLayer − lastLayer)/2)`, while the overlay takes its own previous output (`OT[0]`) as the RC input and writes `OT[1]`, so the partial result is never shown; frame 1 reuses that distance field, runs every cascade from the top, reading only cascades computed in that frame, and overlays the fresh output ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#46-cascade-loop-frame-modes-and-overlay)). The Habr overview's claim that far cascades update less often or through reprojection cites no source ([non-English overviews](../sources/2025_non_english_rc_overviews.md)).

## Cascade −1 and contact detail

When cascade 0 has fewer probes than pixels, each pixel can trace its own short interval from 0 to the cascade 0 start during the final gather and merge it in front of the four nearest cascade 0 probes ([merging notes](../sources/2026_merging_and_ringing.md#cheaper-fixes-and-their-costs)):

- It adds no ringing and works like a bilinear fix with one cascade 0 ray. With probes every 2 px it matches one probe per pixel in quality, and with fp16 storage it makes the bilinear fix cost about what vanilla did. `C_MINUS1_GATHERING` in [4ctXD8](https://www.shadertoy.com/view/4ctXD8) is the reference, and scy3Dd uses the same name.
- In 3D it removes the need to store cascade 0, the largest memory saving found.
- LegitCascades' final gather runs the bilinear-fixed merge with the interval `[0, cm1]` per pixel for each cascade 0 direction, `cm1 = 1.0` cascade 0 spacings by default ([LegitCascades](../sources/2024_sannikov_legitcascades.md#final-gather)).
- Split RC starts cascade 0 rays at a small distance and fills the gap with per-pixel screen-space raymarching, as in visibility-bitmask SSGI, merged as cascade −1; it recovers contact detail smaller than the cascade 0 spacing for 1.4 ms, where the unoptimized directional gather cost 23 ms ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#extensions-shown)).
- A sparse 3D build instead inserts a new cascade before cascade 0 with a quarter of the distance, half the probe size and a quarter of the directions ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)).

## Final gather

**Flatland.** Each pixel blends the 4 nearest cascade 0 probes bilinearly and sums or averages their direction cones ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#final-pass); Coppen's final pass has no code, so whether it samples bilinearly is not shown). The normalizations differ:

| Output | Codes |
|---|---|
| Mean radiance × 2π = fluence | fad's line |
| Mean radiance | the testbed line (MctXRr, 4ctXD8, MfXyRj, lcfcR2, NfVXRc, 4ctczl), 3cKczD, tf2XRc, w3XSz4, LegitCascades (fluence divided by 2π) |
| Sum over rays divided by the ray count, upscaled by hardware interpolation | GM Shaders (the original draws its mip additively at 1.0 and again at 0.5) |
| Exposure ×2 | codyjbennett's line |
| Fluence read from `R0([x + 1, y], 0)` | HRC (the +1 offset stops adjacent quadrants' diagonal rays from overlapping into bright crosses) |

Both main Shadertoy lines apply the tone map `1 − (1 + F)^−2.5`, so the same scene displays about 2π darker in the testbed line ([Shadertoys](../sources/2023_rc_shadertoys.md#parameters-across-the-2d-implementations)). Sources for the other rows: [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#original-version-radiancecascades), [LegitCascades](../sources/2024_sannikov_legitcascades.md#final-gather), [HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#final-gather-and-cleanup). jason.today shows painted pixels' own colour at cascade 0 and RC output elsewhere ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#45-rc-fragment-algorithm)).

**Surfaces in 3D.** Cascade 0's cones must become irradiance at each normal, and per-pixel sums over every direction of every interpolated probe are expensive (Split RC: 32 directions × 8 probes, up to 256 samples). Codes precompute instead:

| Code | Gather |
|---|---|
| Split RC | each probe converts its cones to a 6×6 Lambertian octahedral irradiance map with a 1-texel border; pixels take at most 8 filtered samples in the normal direction |
| Split RC's Unity port | the same 6×6 tiles in a 4096² atlas, 8 corners per LOD |
| erhe | cascade 0 cosine-convolved into the DDGI formats: a 6×6 irradiance map (8×8 with border) and a 14×14 distance map (16×16), read by the existing DDGI shading |
| A voxel 3D repository | a 4×4 octahedral irradiance map per probe (32 directions, cosine weighted, weight 4π/32), read 2×2 probes and the map bilinearly with no border wrap |
| mpalenque/sim | an SH volume |
| Love and Deepspace | luma SH plus two chroma scalars |

Sources: [Split RC](../sources/2026_freeman_split_radiance_cascades.md#implementation-details), [plugins](../sources/2026_unity_unreal_rc_plugins.md), [erhe](../sources/2026_erhe_world_space_rc.md), [voxel 3D repositories](../sources/2026_voxel_3d_rc_repositories.md), [repository survey](../sources/2026_rc_repository_survey.md), [talks](../sources/2026_rc_conference_talks.md).

Sparse 3D builds found per-direction sums of `max(0, dot(dir, n))` had fewer failure modes than SH1, an SH clamp once hid negative radiance from wrong mesh normals, and 4×4 cosine samples per cone cost about 0.3 ms, the same as 8×8 ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)). One cosine per cone is wrong, and the error grows with cone size ([core theory](core_theory.md#diffuse), [Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md#for-rc)). A gather that divides `Σ L·cos θ` by `Σ cos θ`, as Gavras's does, returns the cosine-weighted mean radiance, which is irradiance divided by π (derived, [Gavras](../sources/2025_gavras_screen_probes_world_intervals_thesis.md)). Where the sample point sits relative to the surface matters: Rulkens samples at `p + o·n` (1.7 probe spacings in the thesis code) to keep probes behind the surface out ([Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md#shading-sec-6)); the other offsets and leak guards are in the 3D topics.

## Formats

| Data | Format that worked | Notes |
|---|---|---|
| Jump-flood coordinates | RG16F (RG32F above 1024 px in the community demo) | 8-bit fails: no positions beyond 256 and false hits 1 to 2 px from surfaces; full-precision JFA fixed shimmer in one build |
| Distance field | R16F | RGB10A2 is too small |
| Radiance without transmittance | R11G11B10F | the community demo's cascades; no alpha, so visibility is only the hit flag and merging must early-return (derived) |
| Radiance with continuous transmittance | RGBA16F | needed for volumetric alpha; GM Shaders' optimized cascades; the only portable filterable float render target on the web |
| Surfaces | RGBA8 | |
| Cascades in research codes | fp16 RGB radiance and transmittance (HRC), fp32 (Split RC), RGBA32F (tmpvar's 3D grid), RG32UI 8-byte texels (Rulkens) | |

Moving one 2D build from RGBA32F everywhere to the formats above took it from 81 to 240 fps at 768² on an RTX 3050 laptop: RC is memory bound and speed tracks format size ([merging notes](../sources/2026_merging_and_ringing.md#formats-and-color)). On WebGL2, RGBA16F samples and filters everywhere and with `EXT_color_buffer_float` or `EXT_color_buffer_half_float` also renders, blends and multisamples; R11G11B10F renders and multisamples but never blends and filters only with `OES_texture_float_linear`; RGBA32F filters only with `OES_texture_float_linear`; RGB9E5 can only be sampled. On WebGPU, RGBA16F supports all uses, R11G11B10F only sampling and filtering, and RGBA32F filters and blends only behind features ([merging notes](../sources/2026_merging_and_ringing.md#links), sokol's format table). jason.today's targets default to half float ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#8-performance-notes)).

Memory at these formats (derived): GM Shaders' optimized two RGBA16F textures at 1920×1088 take 33.4 MB; imnethen's two ping-pong buffers hold 2.1 to 2.3 M texels per cascade at 1080p and take 36.6 MB; GM Shaders' original keeps 5 cascades of 1024² 4-byte texels, about 20 MiB; Rulkens's dense 192³ cube-mapper cascades take 658 MB ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#original-version-radiancecascades), [merging notes](../sources/2026_merging_and_ringing.md#links), [Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md#parameters)).

Shared-exponent and packed formats lose precision when merged values are re-stored, which drifts ([artifacts and fixes](artifacts_and_fixes.md), [glossary](supporting_techniques.md#formats-and-colour)).

## 2D parameters across implementations

| Implementation | Cascades | Cascade 0 spacing | Cascade 0 directions | Base interval | Branching | Merge |
|---|---|---|---|---|---|---|
| fad, mtlBzX | 5 | from cube-map capacity, about `6·W·H/17` texels of probes | 16, pre-averaged to 1 | `4·|res|/1023` | 2x/4x | vanilla bilinear |
| Suslik, mlSfRD | 4 | 320×180 fixed | 16, pre-averaged | 7 px | 2x/4x | vanilla, cross-faded ends |
| Quinchilion, clVcD3 | 5 | from capacity, multiple of 32 | 16, pre-averaged | as fad, plus `2^(n+1)` px overrun | 2x/4x | vanilla plus ringing mask |
| kornelski, XffcD7 | 5 | from capacity | 16, pre-averaged | as fad, gear factors | 2x/4x | vanilla |
| Suslik, MctXRr | 6 | 512×512 | 4 | `10⁻³·W` | 2x/4x | bilinear fix |
| Suslik, 4ctXD8 | 6 | 512 across | 4 | `1.5·10⁻³·W` | 2x/4x | switchable, bilinear fix by default |
| Mytino, MfXyRj | 6 | 512×512 | 4 | `1.5·10⁻³·W` | 2x/4x | bilinear fix ending on circles |
| mxcop, lcfcR2 | 5 | 512×256 | 4 | `1.5·10⁻³·W` | 2x/4x | one random upper probe |
| codyjbennett, wfyyDz and cbenn fiddle | 6 (8 in the fiddle) | 1 px | 1 | 0.2 px scale (cascade 0 0.8 px) | 2x/4x | bilinear fix with absorption |
| youssef_afella, 3cKczD | 5 | 1 px | 4, pre-averaged | ⅔ px scale | 2x/4x | vanilla, one hardware read |
| SJarod, tf2XRc | 3 | 16×16 in UV | 8, doubling | 20/256 UV, overlapping | 2x/2x | all cascades per pixel |
| Neylick, w3XSz4 | 11 | 886×886 | 4, doubling | `√2` px, ×2 | 2x/2x | two child directions over four probes |
| GM Shaders original | 5 | 2 px | 4 | 4 px, plus leak term | 2x/4x | 16 fetches, 0.33 weights |
| GM Shaders optimized | 6 | 1 px | 4 (1 stored) | 2 px | 2x/4x | bilinear fix active |
| jason.today | 6 | 1 px | 4 | 2 px, overlap 0.04 | 2x/4x | one filtered read |
| radiance-cascades.com demo | 6 | 1 px | 4 | 1 px, overlap 0.1 | 2x/4x | one filtered read |
| LegitCascades `Scaling.ls` | 3 (4 in ChroniclFix) | 256-wide grid, height from the screen aspect | 4 (2×2) | 10 px (3 px in ChroniclFix) | 2x/4x | bilinear fix (chronicl fix above cascade 1) |
| imnethen | 7 | 1 px | 4 | 1 px | 2x/4x (S and A configurable) | vanilla or bilinear fix |
| mxcop's animation helper | | | `N0` | `L` | `tmin = L·2^(s·i)`, `s = B/2` | |
| DexRT 2D | 6 | 1 cell | 4 azimuth × 8 inclinations | 1.5 cells | 2x/4x | vanilla (fix not needed) |
| Shipped 2D Switch game | 3 | 384×256 | 4 | | 2x/2x | single fetch on a downsampled scene |
| nixonyh, Bevy | 6 at 1080p | 2 px (2×2 texel blocks) | 4 | 2 px | 2x/4x | 16 texels with parity weights, skipped on hits |
| kornelski, Bevy | 6 | 2 px | 16 merged | 16 px, doubling | 2x/2x | four texels with fixed blur weights, ends staggered ±10% |
| Lommix, solis_2d | | 1 px | 4 per texel | 6 px | 2x/4x | one filtered read |
| IceKontroI, sparse_rc_2d | 6 at 1080p | 2 px | 4 | 2 px | 2x/4x | nearest upper probe, child rays aimed at the parent group's centre |
| Sohojoe, mix-Yaazarai-and-jason | 6 at 1280×736 | 0.25 to 4 px by quality | 4, pre-averaged | `I0`, plus `√2·L0·2^(i+1)` | 2x/4x | one `imageLoad`, so nearest |
| knowdawg, ProcPixelTexturing | 5 at 1024² | | 16 merged at the output | `[0, 1]` px, then `[4^(c−1), 4^c]` | 2x/4x | four bilinear probes, four child directions, in place |
| Youssef-Afella, Unity | `C` | 1 texel at the render scale | 4, pre-averaged | `R/(4^C − 1)` | 2x/4x | one filtered read |
| ZY4N, Unity | | 1 px | 4 | 2 px starting at 0.5 px | 2x/4x | five-tap angular merge |
| agrdino, Unity | | 2 px (2×2 texel blocks) | 4 | 1 cascade pixel | 2x/4x | 0.25/0.75 weights |
| Youssef-Afella, GBA | 3 at 80×80 | | 4 | 3 px | 2x/4x | |
| Hybrid46, Raylib | 6 at any size | 1 px | 4 | about 1.3 px at 1200×900 (`R/(4^N − 1)` of two screen heights) | 2x/4x | one filtered read |
| qJay44, OpenGL | 7 at 1200×720 | 1 px | `base` (4 to 16) | 1 px | 2x/`base`× | one clamped filtered read |
| tsukinousagi18, OpenGL | 6 at 704² | 1 px | 4 | `[0.25, 1.25]` px | 2x/4x | one filtered read |
| futureengine2 gist | 7 | 1 px | 4, doubling | `[0, 0.5]` px | 2x/2x | parity weights on misses |
| kiss3d `gi2d` | | 2 px | 16 (4×4 tile) | `base` | 2x/4x | |
| SimonDev demo | 7 | | 4 | | 2x/4x | four upper directions, half a bin off |
| CoreCascade | 7 traced at 800² | 1 px (`2/W` over `[−1, 1]`) | 4 | 0.5 px | 2x/4x (`ceil(N/2) + 1` probes per axis) | vanilla or bilinear fix |
| Peixoto, OPEngine | 5 at 1080p | 2 px | 4 | 4 px, overlap re-tracing below | 2x/4x | 16 texels on misses |
| tlegoc, Vulkan | fixed | from a fixed top-cascade probe count | | | | bilinear with wrong corner weights |
| Peter's thesis | 8 (9 in the text) | 1 px | 4 | one pixel diagonal | 2x/2x | bilinear |
| TypeGPU SDF runner | 6 at 512² (at least 5) | 1 px (512 probes across) | 4 (16 or 64 with `baseStoredRayDim`) | one probe spacing | 2x/4x | one filtered read or bilinear fix |
| tmpvar playground Flatland | 5 | 2 px | 4 | 6 px (6.76 truncated) | 2x/4x | bilinear over upper probe means |
| Gigi graph | 6 at 512² | 1 px | 4, pre-averaged | 1 px | 2x/4x | bilinear fix |
| amida | 6 at 512² | 1 px | 4, pre-averaged | 1 px | 2x/4x | four variants, all tracing to the upper interval end |
| YMM4-Radiance | 4 | 2 px | 4 | 3.5 px (of a 300 px range) | 2x/4x | hardware filter over 4 upper directions, saturated |

Sources: [Shadertoys](../sources/2023_rc_shadertoys.md#parameters-across-the-2d-implementations), [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#default-configuration-derived-values), [jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#11-derived-values-default-settings), [demo](../sources/2026_rc_community_site_and_wiki.md#derived-cascade-table-not-stated-in-the-source), [LegitCascades](../sources/2024_sannikov_legitcascades.md#defaults), [merging notes](../sources/2026_merging_and_ringing.md#links), [radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#dexrt-v020-and-the-data-archive); the rows from nixonyh down are read from the codes in [2D implementations](2d_implementations.md) and [2D articles and demos](2d_articles_and_demos.md). Each code's full design, scene representation and bugs are in [2D implementations](2d_implementations.md).

Derived cascade tables at the defaults:

| Code | Cascade: spacing (px), probes per axis, rays per probe, tile side (texels), interval (px) |
|---|---|
| GM Shaders original (1024², angular 4, interval 4, spacing 2) | 0: 2, 512, 4, 2, `[0, 4]`; 1: 4, 256, 16, 4, `[4, 31.31]`; 2: 8, 128, 64, 8, `[20, 106.6]`; 3: 16, 64, 256, 16, `[84, 385.3]`; 4: 32, 32, 1024, 32, `[340, 1454.5]` (ranges 4, 27.31, 86.63, 301.25 and 1114.51 include the `√2·2^(c+1)·spacing` leak term, none at cascade 0) |
| GM Shaders optimized (1920×1088, linear 1, interval 2) | 0 to 5: spacing 1 to 32; probes 1920 × 1088, 960 × 544, 480 × 272, 240 × 136, 120 × 68 and 60 × 34; direction grids 1 × 1 to 32 × 32 (stored directions 1 to 1024); 4 to 4096 actual rays; starts 0, 2, 10, 42, 170, 682; ranges 2, 8, 32, 128, 512, 2048 in the active bilinear-fix shader (the base shader adds `√2·2^(i+1)`, giving 4.83, 13.66, 43.31, 150.63, 557.25 and 2138.51); the top range against a 2203.13 px diagonal, whose `log4` of about 5.55 gives 6 cascades |
| jason.today (512²) | 6 cascades, 1 M rays each, 6.3 M per frame |

The GM Shaders original's interval end is `off_c + range` (derived from its start and range columns). Its stored texture is `E = floor(1024/2)·√4 = 1024` per side for every cascade.

## Connections

- **Direction-first is ray sorting.** Enshrouded sorts rays by position and direction bin and GIBS bins them by cell and direction to make tracing coherent; a direction-first layout stores all rays of one direction together, so it gets that coherence without a sort ([probe GI](related_probe_gi.md#connections), [radiance caches](related_radiance_caches.md#connections)) (inference).
- **Pre-averaging is a Haar step.** Averaging four children into one parent texel is the average half of WPBGI's average-and-detail tree; RC keeps the averages and drops the details ([alternatives](light_transport_alternatives.md#connections)) (inference).
- **Irradiance tiles are DDGI's maps.** The 6×6 octahedral tiles Split RC and erhe build per probe for the final gather are DDGI's irradiance texels, and erhe reduces its cascades into DDGI maps outright ([probe GI](related_probe_gi.md#ddgi), [3D world space](3d_world_space.md#measurements)).
- **Interval overlap has a stochastic twin.** Enshrouded picks a cascade by a probability ramp across the overlap zone, where RC blends by weight ([probe GI](related_probe_gi.md#connections)).
- **Cascade −1 is the near-field split every cache makes.** kajiya's raw near hits, GI-1.0's horizon AO under its probes and Split RC's screen-space cascade −1 all treat contact light apart from the cached far field ([radiance caches](related_radiance_caches.md#connections)).
- **Merging across depth edges is an upscaling problem.** Parent-to-child merges, cascade 0 to pixel upscaling and history reprojection are one depth-aware interpolation, answered by bilinear 3D, selective subsets and min/max probes ([3D screen space](3d_screen_space.md#connections)).
- **Frame-lagged schedules come from the hosts.** Shadertoy and LegitScript run fixed passes per frame, which is why so much public code merges across frames ([history](history_and_landscape.md#single-frame-assessment)).

## Single-frame assessment

For a single-frame 3D implementation (inference, from the sections above):

- **Schedule:** one dispatch per cascade from the top down, fusing trace and merge, gives a complete result each frame with `N` dependent dispatches and two cascade buffers; each dispatch boundary needs a storage barrier ([Godot integration](godot_integration.md)). Frame-lagged schedules are host artifacts, not needed.
- **Directions:** an equal-area nested map (cylindrical as in Split RC, or Clarberg's octahedral) avoids per-texel weights in the merge and gather; the plain octahedral map needs Jacobian weights and is poor at 4×4 to 8×8 tiles. HEALPix is the most accurate and the costliest to index.
- **Intervals:** the contiguous geometric family with `l = 4` and `t0` near 1.6 spacings at 32 directions ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)); overlap only if the tracer is not watertight.
- **Merge:** trilinear over 8 probes and 4 child directions. A direction-first layout in 3D textures could let the sampler do the trilinear blend; any fix that traces per upper probe must interpolate by hand.
- **Memory:** cascade −1 per pixel removes the stored cascade 0 and adds contact detail; pre-averaging cuts storage 4×; fused scheduling caps live cascades at two.
- **Gather:** precompute per-probe irradiance tiles (6×6 octahedral, as Split RC and erhe do) rather than summing every cone per pixel.

## Open questions

- Is the 3D direction-first layout with hardware trilinear merging faster than a shader trilinear blend on current GPUs, given that GM Shaders' 2D speedup did not survive measurement?
- Which nested equal-area map gives the best quality at 16 to 32 cascade 0 directions? Split RC found cylindrical better than Clarberg and octahedral, while screen-space builds preferred Clarberg; neither comparison was published with metrics.
- Does pre-averaging cost quality in 3D, where a parent's 4 children are farther apart in angle at low direction counts?
- What is the best irradiance tile size per probe for single-frame shading, and should tiles be built per probe or per pixel group?
- Can cascade −1 in 3D be traced against the same scene representation as the cascades, or does it need screen-space marching as in Split RC, and how does that choice affect leaks at contact?
