# Radiance Cascades for Medical Volume Data

| | |
|---|---|
| Author | Renée E. S. Rulkens; supervisors Maxime Chamberland and Bram Kraaijeveld |
| Date | 2025 (report dated 2025-11-07) |
| Kind | Master's thesis, Eindhoven University of Technology, 35 PDF pages |
| Link | https://research.tue.nl/en/studentTheses/001b99c6-3cf9-4c84-a3f8-7bf98c94a2ab |
| Code | https://github.com/ReneeR33/radiance-cascades-volume-rendering; see [2026_gigi_and_volume_rc_repositories.md](2026_gigi_and_volume_rc_repositories.md#rc-for-ct-volumes) |

The thesis applies a dense 3D world-grid RC to CT volume rendering, combining it with surface shading and a volumetric illumination model to show single-bounce GI on CT data in real time. It claims no convergence time and no limit on the number or shape of lights. Page numbers are PDF pages; printed numbers are 4 lower.

## Goal and background

- The one stated goal is physically based single-bounce GI for CT scans in real time, with no light limit and no convergence (p. 5). The abstract says adding lights does not change performance (p. 3); the results say it changes little (p. 26), and no light-count sweep is measured.
- Earlier real-time volume lighting is limited: deep shadow maps and shadow volume propagation take one light; extinction-based shading and SH lighting slow down per light (p. 8). Monte Carlo renderers (Kroes et al.'s Exposure Renderer, Rezk-Salama) converge over time; Jönsson et al.'s historygrams and photon mapping allow editable transfer functions at high memory cost; Yang et al.'s screen-space occlusion handles only lights in front of the image plane (p. 6). Game irradiance volumes are cited for light leaks and a probe-count trade-off (p. 5).
- RC is explained from Sannikov's paper alone (p. 9-10).

## Method

The light field is computed once per scene change and read every frame (Fig. 4.2, p. 12).

| Stage | Runs |
|---|---|
| Combine the CT volume with an RGB light volume into one transmittance volume and one emitted-colour volume | on scene change |
| Ray-march the combined volume for every probe and cascade | on scene change |
| Merge the cascades into a radiance volume | on scene change |
| Ray-march the CT and light volumes from the camera, reading the radiance volume | every frame |
| Gamma correction and display | every frame |

- The field is independent of the camera and is recomputed only when the transfer function, the volume or the lights change (p. 11-12, 32). Nothing is accumulated over frames, and whether one recomputation fits in one frame is not stated.
- Transparent voxels emit nothing, so colour is read only where transmittance is near 0; the combined volume exists to cut texture fetches, the largest cost (p. 12).
- Cascade 0 probes are spread evenly over the volume, and higher cascades sit between the probes below (p. 11). Probe and light volumes span a unit cube that the CT is scaled into (p. 25).

### Direction mappers (sec. 5)

- Regular point sets on the sphere exist only for special counts up to 20, and Fibonacci lattices do not nest cones across cascades, so directions come from subdividing a regular polyhedron's faces (p. 13).
- **Cube:** 6 base directions; each cascade splits every face into a `2^c × 2^c` grid, `6·4^c` directions (6, 24, 96, 384, 1536), each the normalized cell center (p. 14-17). A probe's block is `2^(c+1)` by `3·2^c` texels with six face sub-blocks; a cell point is `P = S + (1/2 + i)·du + (1/2 + j)·dv` with `du = v/2^c`, `dv = u/2^c`.
- **Tetrahedron:** 4 base directions, each face split into four triangles per cascade, `4·4^c` directions (4, 16, 64, 256, 1024), each the normalized barycenter `(A + B + C)/3`; directions of one base face share a contiguous index range, numbered from the bottom left (p. 17-19).
- Non-uniform cells bias a probe toward whichever side holds more directions, so each value is weighted by `r_w = r·N·A/(4π)` with `A` the cell's solid angle by Girard's theorem (p. 20).

### Collection and merge (sec. 5.5)

- An interval `[a, b]` integrates `T(s)·L_e(x_s)` with no in-scatter term, so the field holds only light seen directly from the light volume (p. 20).
- Merging cascade `c+1` into `c` takes the upper directions `D` forming a cone with the lower direction, trilinearly interpolated from the upper probes (p. 20-21): `T_m = T_c·(1/|D|)·Σ T_{c+1}` and `L_m = L_c + (1/|D|)·Σ T_{c+1}·L_{c+1}`. `|D|` and the merge order are not stated. The printed `L_m` lacks the factor `T_c`; the code applies it (`color = c + t·Σ w_q·mean_q`).
- The final radiance volume keeps cascade 0's directions: 6 or 4 per probe.

### Shading (sec. 6)

- Surfaces sample the field at `s = p + o·n` to keep probes behind the surface out of the sum, with the normal from finite differences (p. 22). The thesis gives no value for `o`; the code uses 1.7 probe spacings.
- Lambertian shading: `L_r ≈ (π·ρ/N)·Σ_j V_{s,j}·max(f_d(j)·n, 0)`, normalized so a cone fully on a unit light sums to the hemisphere area (p. 22-23).
- Volumes march front to back with `T(0) = 1`, multiplying `T` by `exp(−σ_t·Δs)` and adding `T·(σ_a·L_e + σ_s·L_s)·Δs`; in-scatter is `L_s ≈ (4π/N)·Σ_j f_p·V_{x,j}`, which for the isotropic phase `1/(4π)` used throughout is the mean of the `N` directions (p. 23-24).
- The transfer function maps density to `σ_s` and `σ_a` by linear interpolation between control points; voxels above a threshold render as surfaces with zero `σ` (p. 24).

## Parameters

- Cascade 0 grid and light volume both 192³; RC step 1/192; camera step 1/1000; output 1000×1000 (p. 25).
- Intervals: cascade 0 `[0, 1/100)`, cascade `c > 0` `[2^(c−1)/100, 2^c/100)`, so lengths 0.01, 0.01, 0.02, 0.04, 0.08 (about 1.9, 1.9, 3.8, 7.7 and 15.4 steps) and a top reach of 0.16, about 31 cascade-0 spacings (derived).
- Tested with 2 to 5 cascades; the ground-truth tests use 5. Neither the 192 grid nor the 1/100 base is justified.
- C++ and OpenGL on an Intel i9-13900HX with a 12 GB RTX 4080 Laptop GPU. NIfTI sources up to 535³ are downsampled to 192³ (p. 25).
- No memory figures. At `(192/2^c)³` probes per cascade and one texel per direction, the cube mapper needs 82,280,448 texels, 658 MB (628 MiB) at the code's 8-byte RG32UI texel, which matches the 628 MB of raw cascades measured in the code; the tetrahedron mapper needs two thirds of that, 439 MB (derived).

## Results

Table 7.1, recalculation time of the radiance field in ms, cube ("square") and tetrahedron mappers (p. 27):

| Scene | 2 cube | 2 tetra | 3 cube | 3 tetra | 4 cube | 4 tetra | 5 cube | 5 tetra |
|---|---|---|---|---|---|---|---|---|
| CT Philips, large white light | 25.88 | 17.65 | 28.28 | 19.68 | 29.16 | 20.40 | 28.70 | 19.95 |
| Bonsai, four small coloured lights | 29.64 | 20.99 | 32.21 | 22.66 | 31.90 | 22.73 | 30.43 | 21.49 |
| Iguana, white background light | 28.05 | 19.18 | 29.96 | 20.95 | 30.45 | 21.48 | 29.55 | 20.91 |
| AVM | 30.82 | 22.05 | 33.89 | 23.95 | 33.39 | 24.17 | 31.45 | 22.70 |

- The cube mapper costs 1.38 to 1.47 times the tetrahedron in every cell, and 2 to 5 cascades adds only 2 to 13 % (derived). Times fall from 4 to 5 cascades, which the thesis guesses, untested, comes from top-cascade probes sitting farther from the volume edge.
- Quality rises with cascade count mainly for small lights, which distant probes miss with few cascades; large lights change little. The cube mapper looks better, mostly for small lights, and the gap narrows with more cascades (p. 25-26).
- Against a single-bounce Monte Carlo reference (sample count and time not given): surfaces come out slightly darker because cones partly below the surface are dropped whole, some lights are missed, and light bleeds through thin structures such as eye sockets (p. 28). Volumes look nearly identical, with brighter spots from bleeding and darker ones from limited angular resolution, worst for the tetrahedron (p. 30). At very high extinction (`σ_a = 152`, `σ_s = 8`) probes inside the volume collect little light and dark rings appear, so surface rendering is advised there (p. 30-31). One-voxel lights leave dark spots because few directions hit them (p. 31).
- Exposure Renderer needs about 2 s to settle after a change, against at most 20 to 30 ms for RC (p. 32); hardware and method for the comparison are not given, and Table 7.1 reaches 33.89 ms.
- No numeric image metric, memory figure, per-pass timing or run statistics are reported.

## Limits and future work

Specular reflection is poor, though the nearest direction approximates it; only one bounce is covered; the probe grid is coarser than the surfaces, which causes bleeding; small lights need more directions; mip-based empty-space skipping made the method slower, and acceleration structures may not help (p. 33). Future work: Cook-Torrance and other BRDFs, acceleration structures, and MRI data.

## Inconsistencies

- Fig. 5.4 gives cube blocks of `2·3^c` by `2·2^c` where the formulas and base case give `2^(c+1)` by `3·2^c`; the text says the cube direction count rises "by 4" per cascade and the tetrahedron block "by 2", where the formulas multiply.
- The tetrahedron point modulus is printed `2^c`, while four triangles per face at cascade 1 need `4^c`; the flattened index `i_d = i_d_y·2^c + i_d_y` repeats the y component; the cube point index uses the side index where a local index is meant.
- p. 10 says merging yields the last cascade's angular resolution; p. 20-24 keep cascade 0's.
- The reference is called closed-form tracking on p. 29 and regular tracking on p. 30; reference [32] is cited as Yang et al. but lists other authors; Fig. 5.11 has a placeholder caption.

## For RC

- **Cone weights:** shading by the cosine at each cone's center discards how much of the cone lies above the surface. With the 6 cube directions and normal `+z`, the exact projected solid angles are 1.741 sr for the top face (55.4 % of π) and 0.350 sr for each side face (11.1 %), while the center cosine gives the top face everything and the sides nothing. Under uniform unit radiance the center-cosine sum with cone solid angle `4π/6` gives 2/3 of the exact irradiance for an axis-aligned normal and 1.155 times it for a `(1,1,1)` normal, so shading varies by `√3` with normal orientation alone; the thesis's `π/N` prefactor scales both cases down further, to 0.52 and 0.91 of the exact value (derived by numeric integration). This fits the darker surfaces in the ground-truth comparison and the code's half-irradiance bug; precomputed per-cone projected solid angles against a normal fix it at the cost of a small table (inference).
- **Cascade 0 with 4 or 6 directions** is the least angular resolution any 3D RC uses, and every quality problem reported here (missed small lights, dark one-voxel lights, mapper quality gap shrinking with more cascades) is an angular-resolution limit of cascade 0 rather than of the hierarchy (inference).
- **Doubling intervals in 3D** keep the paper's 3D scaling (spacing ×2, directions ×4, intervals ×2) but reach only 31 probe spacings after 5 cascades, so the hierarchy never covers the whole unit cube's 192 spacings; the top cascade runs to the edge instead (inference from the code note).
- **Cost:** 20 to 34 ms per full recalculation of a dense 192³ grid on a laptop RTX 4080, with the field reused while the camera moves; a per-frame dense world grid at this size would exceed a real-time budget, which is the cost the sparse and screen-space families avoid (inference).
