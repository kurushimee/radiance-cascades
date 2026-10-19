# Fast Equal-Area Mapping of the (Hemi)Sphere using SIMD

| | |
|---|---|
| Author | Petrik Clarberg |
| Date | Journal of Graphics Tools, 2008 |
| Kind | Paper (preprint); the paper gives its code at http://jgt.akpeters.com/Clarberg08/ |
| Link | https://fileadmin.cs.lth.se/graphics/research/papers/2008/simdmapping/clarberg_simdmapping08_preprint.pdf ; plot https://simulationcorner.net/clarberg/main.html |

The paper keeps the folded-square layout of the octahedral map and replaces its projection with an equal-area one built from Shirley and Chiu's concentric map, so every texel covers the same solid angle. RC implementations use it for probe directions: Dell'Ova's ClaikoCode build has it as `OctToFloat3EqualArea` ([2025_dellova_rc_performance_scaling_thesis.md](2025_dellova_rc_performance_scaling_thesis.md)), and the RC discussions prefer it over the plain octahedral map at low resolution ([screen-space RC](2026_screen_space_rc.md), [sparse 3D RC](2026_sparse_and_3d_rc.md)). Page numbers are the printed journal pages.

## Mapping

- Hemisphere base (eq. 1, p. 54), Shirley and Chiu's concentric map in its first sector: `u = 2s − 1`, `v = 2t − 1`, `r = u`, `φ = (π/4)·(v/u)`, then `x = cos φ·r·√(2 − r²)`, `y = sin φ·r·√(2 − r²)`, `z = 1 − r²`.
- Sphere from the square (eqs. 2-5, pp. 56-58): `u = 2s − 1`, `v = 2t − 1`, `d = 1 − (|u| + |v|)`, `r = 1 − |d|`, `φ' = (π/4)·((|v| − |u|)/r + 1)` in [0, π/2] (set to 0 when `r = 0`), `sin φ = sign(v)·sin φ'`, `cos φ = sign(u)·cos φ'`, and `x = cos φ·r·√(2 − r²)`, `y = sin φ·r·√(2 − r²)`, `z = sign(d)·(1 − r²)`. The inner diamond `|u| + |v| < 1` is the upper hemisphere and the four outer triangles the lower one.
- Square from the sphere (sec. 3.2): `r = 1 − |z|`, `φ' = atan2(|y|, |x|)` (a polynomial arctangent of min over max in the paper), `v_i = r·2φ'/π`, `u_i = r − v_i`; for `z < 0`, reflect to `(1 − v_i, 1 − u_i)`; restore the signs of `x` and `y` and map [−1, 1]² to [0, 1]².
- The area distortion is constant (sec. 6, pp. 67-68): [−1, 1]² of area 4 maps to 4π, a factor of π everywhere. The paper calls the plain octahedral map's projection an arbitrary parameterization (Fig. 2) and does not measure its distortion; it notes that cube maps are not area-preserving either, with smaller solid angles near the corners.
- Each octahedral edge folds about its midpoint, so the map tiles by mirrored repeat and lookups outside [0, 1)² need no special case (sec. 4.1, p. 64). Bilinear weights and wrapped texel addresses take 27 SSE instructions; 16-bit indices limit maps to 64k × 64k texels (sec. 4.2).

## Accuracy and cost

- Forward error on the unit sphere: max 7.49·10^−6, mean 3.37·10^−6; inverse: max 2.43·10^−4, mean 3.19·10^−6, a few inverse cases reaching about a third of a texel on a 4k map (Table 1, p. 63).
- Cycles per point on one core of a 3.2 GHz Penryn (gcc 4.0.1), for `N` = 256 / 4k / 64k / 1M / 16M points (Tables 3-4):

| Direction | Version | 256 | 4k | 64k | 1M | 16M |
|---|---|---|---|---|---|---|
| square → sphere | scalar standard | 121.9 | 156.2 | 160.7 | 162.4 | 162.5 |
| square → sphere | scalar optimized | 77.9 | 77.9 | 78.0 | 80.4 | 80.5 |
| square → sphere | SSE | 18.8 | 18.7 | 18.7 | 22.8 | 22.8 |
| sphere → square | scalar standard | 114.7 | 145.1 | 147.8 | 149.1 | 149.0 |
| sphere → square | scalar optimized | 106.9 | 115.8 | 115.7 | 117.7 | 117.5 |
| sphere → square | SSE | 23.0 | 23.2 | 23.2 | 25.6 | 25.6 |

SSE is 3.5 to 4.2× faster than optimized scalar code and 6.5 to 8.6× faster than the standard version; the abstract says up to 9×.

## The plot page

The simulationcorner page has no text: a Plotly figure whose script draws 16 blue arrows from the origin to radius 1, 64 red arrows from radius 1 to 2 and 256 green arrows from radius 2 to 3 (28 more calls are commented out). The counts 16, 64 and 256 are three cascades of directions growing 4× per level, drawn on nested shells (inference).

## For RC

- An equal-area map gives every direction bin the same solid angle, so a probe's mean over its texels is the mean radiance over the sphere without per-texel weights, and the 2×2 parent-child grouping of a square map stays a 4-to-1 split in solid angle at every level (inference from constant distortion). The plain octahedral map needs a Jacobian weight for both.
- The map is not uniform in shape: texels near the octahedron's edges and the poles of the outer triangles are stretched, so equal area does not mean equal angular spread, which matters for interval-end footprints (inference).
