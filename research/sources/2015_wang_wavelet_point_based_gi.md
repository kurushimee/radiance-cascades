# Wavelet Point-Based Global Illumination (WPBGI)

| | |
|---|---|
| Authors | Wang, Meng, Boubekeur |
| Date | EGSR 2015, Computer Graphics Forum 34(4) |
| Kind | Paper |
| Link | https://perso.telecom-paristech.fr/boubek/papers/WPBGI/WPBGI_lowres.pdf |

Point-based GI stores outgoing radiance on a hierarchy of surface points and gathers it through a per-receiver microbuffer; WPBGI replaces its spherical harmonics with Haar wavelets of cube maps so glossy interreflection and caustics survive. RC discussions link it as a wavelet radiance encoding ([sparse 3D RC](2026_sparse_and_3d_rc.md)). Equations and Table 2 were read from rendered page images.

## Method (sec. 3)

- Outgoing radiance per point (`L_o = ∫ L_i·ρ·V·(ω_i·n) dω_i`, eq. 1) is sampled into a cube map, typically 32×32 per face, and Haar-transformed; coefficients go into a binary bounding-sphere tree.
- A parent averages its children, `C_j = (C_{j−} + C_{j+})/2`, `G_j = (G_{j−} + G_{j+})/2`, and keeps the detail `H_j = (G_{j−} − G_{j+})/2`. Only the root average and the detail vectors are stored; a detail vector whose L2 norm falls below 0.002 is dropped, and averages are kept down to level `m = 20`. A node is rebuilt as `C_j = G_root + Σ_{k on the path} s_k·H_k` with `s_k = ±1` for left and right children.
- Each receiver starts with a 16×16 quadtree microbuffer refined first by the BRDF and then by incoming light: importance `F(q) = F_l(q)·F_ρ(q)` with `F_l(q) = 1` when `L_i(q)/2^{Δ_q} > γ` (`γ = 1` typically) and `Δ_q` the refinement level.
- Multiple bounces split sender and receiver node pairs until the solid-angle ratio falls below `ε = 0.05` (Alg. 1). Shading multiplies wavelet coefficients: `D = U·W` with `U` the 4D coefficients of the BRDF and `W` the 2D coefficients of incoming radiance, then `L_o = T₂^{−1}(D)`.

## Results (sec. 4)

Mitsuba on an 8-core 2.67 GHz i7 with 9 GB; 1024×768, or 1024² for Ring, Cornell box and Sphere; 32×32 tiles; reference by bidirectional path tracing (BPT).

| Scene | Max path | BPT samples | BPT (h) | Points (M) | Face res | Memory (GB) | Pre (min) | Render (h) | Total (h) | MSE |
|---|---|---|---|---|---|---|---|---|---|---|
| Ring | 3 | 16384 | 5.49 | 5 | 128² | 5.98 | 3.22 | 1.14 | 1.20 | 4.589e-5 |
| Corner | 3 | 16384 | 6.63 | 8 | 32² | 6.62 | 3.05 | 1.57 | 1.63 | 1.570e-4 |
| Bunny | 3 | 16384 | 10.53 | 4 | 32² | 5.68 | 12.28 | 0.84 | 1.04 | 6.527e-5 |
| Kitchen | 3 | 16384 | 11.20 | 5 | 32² | 5.26 | 6.57 | 3.66 | 3.77 | 7.948e-5 |
| Sibenik | 3 | 16384 | 10.33 | 10 | 32² | 5.85 | 11.07 | 1.75 | 1.94 | 2.099e-4 |
| Sphere | 5 | 16384 | 22.80 | 2 | 32² | 5.05 | 78.56 | 0.98 | 2.29 | 1.370e-4 |
| Torus | 5 | 65536 | 40.01 | 1 | 32² | 6.53 | 201.61 | 1.01 | 4.37 | 3.116e-4 |

- Total speedup over BPT is 2.9× to 10.1× (2.97× Kitchen to 10.1× Bunny by the table). Against plain PBGI, adaptive microbuffers are up to about 10× faster at similar quality with about twice the memory; SH-based PBGI with 3 × 256 coefficients uses 50 % more memory, takes about 10× longer and still misses glossy detail (Fig. 5). Without adaptive microbuffers the Corner scene took over 24 h instead of 1.63 h (Fig. 13). A larger bootstrap level `m` is faster but memory grows quickly past 16 (Fig. 14). No compression ratio is given.
- Limits: fixed cube-map resolution, over-refinement from intensity alone, importance that ignores occlusion, an intermediate cube map for the Haar transform, and perfectly specular BRDFs as the method's limit (sec. 5).

## For RC

- Haar averages up a binary tree are RC's pre-averaging written as a wavelet transform: the average at each level is the coarse cascade's bin, and the detail coefficient is what a coarser bin loses. Thresholding details at 0.002 is a lossy direction compression that RC does not attempt (inference).
