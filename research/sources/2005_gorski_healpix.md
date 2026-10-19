# HEALPix: equal-area hierarchical pixelization of the sphere

| | |
|---|---|
| Authors | Górski et al. |
| Date | arXiv astro-ph/0409513 v1, 2004-09-21 (published in ApJ 622:759, 2005) |
| Kind | Paper, 21 pages; section 5 read in full |
| Link | https://arxiv.org/pdf/astro-ph/0409513 ; site https://healpix.sourceforge.io/ |

HEALPix divides the sphere into 12 base pixels and each of those into `N_side²` equal-area pixels whose centers lie on rings of constant latitude. RC discussions compare it with octahedral and equal-area octahedral direction maps for probes ([screen-space RC](2026_screen_space_rc.md), [sparse 3D RC](2026_sparse_and_3d_rc.md)). Equation numbers are the paper's.

## Pixelization (sec. 5)

- 12 base pixels in three rings (north cap, equator, south cap); `N_pix = 12·N_side²` pixels, each of area `Ω = π/(3·N_side²)`; `4·N_side − 1` rings of constant latitude with centers equally spaced in azimuth, `4·N_side` per equatorial ring, and polar rings gaining one pixel per quadrant per ring (p. 7). `N_side` = 1, 2, 4, 8 gives 12, 48, 192 and 768 pixels.
- Pixel centers (sec. 5.1) in `(z = cos θ, φ)`. North cap, with `p_h = (p + 1)/2`, `1 ≤ i < N_side`, `1 ≤ j ≤ 4i`: `i = ⌊√(p_h − √⌊p_h⌋)⌋ + 1`, `j = p + 1 − 2i(i − 1)`, `z = 1 − i²/(3·N_side²)`, `φ = (π/(2i))·(j − 1/2)` (eqs. 2-5). North equatorial belt, with `p' = p − 2·N_side·(N_side − 1)`, `N_side ≤ i ≤ 2·N_side`: `i = ⌊p'/(4·N_side)⌋ + N_side`, `j = (p' mod 4·N_side) + 1`, `z = 4/3 − 2i/(3·N_side)`, `φ = (π/(2·N_side))·(j − s/2)` with `s = (i − N_side + 1) mod 2` (eqs. 6-9). The south mirrors the north through `z = 0`.
- Nested indexing (sec. 5.2): for base pixel `f`, `f_row = ⌊f/4⌋`, `F1 = f_row + 2`, `F2 = 2·(f mod 4) − (f_row mod 2) + 1` (eqs. 10-12); within a base pixel the index's even and odd bits give `x` and `y` (eqs. 13-14), and `v = x + y`, `h = x − y`, ring `i = F1·N_side − v − 1`, longitude `j = (F2·N_side + h + s)/2` (eqs. 15-18). Ring order counts pixels along rings from north to south, suited to spherical harmonic transforms; nested order gives neighbour searches and a fast Haar transform.
- Pixel boundaries are not geodesics: `cos θ = a + b·φ` in the equatorial zone and `cos θ = a + b/φ²` in the caps (sec. 5.3, eqs. 19-22).
- The paper gives pixel center from index, not index from direction; the `ang2pix` function of the library is not in it, and the site's primer describes the orderings in prose only.

## For RC

- The nested scheme is a 4-to-1 tree at every level, `N_side → 2·N_side`, with equal areas throughout, which is exactly the parent-child structure RC needs for pre-averaging four directions into one (inference). Its cost is the indexing: the direction-to-pixel step needs per-zone inverses of eqs. 4-9 rather than one fold, which matches the discussion's verdict that HEALPix is accurate but costly to build into a cascade.
