# Irradiance and radiance caching: Ward, Křivánek, Gautron and Tabellion

| | |
|---|---|
| Course | Křivánek, Gautron, Ward, Jensen, Tabellion and Christensen, "Practical Global Illumination with Irradiance Caching", SIGGRAPH 2008 class 16 |
| Course page | https://cgg.mff.cuni.cz/~jaroslav/papers/2008-irradiance_caching_class/ (per-talk slides and the full notes, `2008-siggraph-irradiance_caching_class_notes-no_reprints.pdf`, 405 pages) |
| Papers covered | Ward, Rubinstein and Clear, "A Ray Tracing Solution for Diffuse Interreflection", SIGGRAPH 1988 (doi 10.1145/54852.378490); Ward and Heckbert, "Irradiance Gradients", Eurographics Rendering Workshop 1992; Tabellion and Lamorlette, "An Approximate Global Illumination System for Computer Generated Films", SIGGRAPH 2004; Křivánek, Gautron, Pattanaik and Bouatouch, "Radiance Caching for Efficient Global Illumination Computation", IEEE TVCG 2005; Křivánek, Bouatouch, Pattanaik and Žára, "Making Radiance and Irradiance Caching Practical: Adaptive Caching and Neighbor Clamping", EGSR 2006; Gautron, Křivánek, Bouatouch and Pattanaik, "Radiance Cache Splatting", Graphics Hardware 2005; Gautron, Bouatouch and Pattanaik, "Temporal Radiance Caching", IEEE TVCG 2007 |
| Code | Radiance, `src/rt/ambient.c` and `ambcomp.c` (https://github.com/NREL/Radiance, read at `master`, `ambcomp.c` revision 2.88 of 2021-12-15) |

Irradiance caching computes indirect diffuse light at sparse points, stores each as a record, and interpolates between records elsewhere. It is the ancestor of every radiance cache in this collection, and its record spacing rule is an early form of the spatial half of the penumbra condition. The 1988 and 1992 papers sit behind the ACM paywall and Radiance's site holds only scanned figures, so the formulas below come from Ward's own slides in the 2008 course. Slide formulas were read from rendered pages, since the PDF text layer drops them.

## Contents

- [The 1988 algorithm (Ward's course slides)](#the-1988-algorithm-wards-course-slides)
- [Gradients (Ward and Heckbert 1992)](#gradients-ward-and-heckbert-1992)
- [Radiance's implementation (Ward's second talk)](#radiances-implementation-wards-second-talk)
- [Problems and fixes (Křivánek)](#problems-and-fixes-křivánek)
- [Radiance caching for glossy surfaces (Křivánek et al. 2005, 2006)](#radiance-caching-for-glossy-surfaces-křivánek-et-al-2005-2006)
- [Irradiance splatting on the GPU (Gautron et al. 2005)](#irradiance-splatting-on-the-gpu-gautron-et-al-2005)
- [Temporal radiance caching (Gautron et al. 2007)](#temporal-radiance-caching-gautron-et-al-2007)
- [Tabellion and Lamorlette at PDI/DreamWorks (2004)](#tabellion-and-lamorlette-at-pdidreamworks-2004)

## The 1988 algorithm (Ward's course slides)

- **Lazy evaluation.** A query point near enough records interpolates (or extrapolates) from them; otherwise it computes a new record by sampling its hemisphere. Ward called it "lazy evaluation"; the name "irradiance caching" came from someone else.
- **Hemisphere sampling.** Stratified Monte Carlo over altitude and azimuth, with divisions keeping projected areas constant on the unit circle (the Nusselt analog). Samples that hit a light source count as zero, since direct light is computed separately. Deeper bounce levels use fewer samples. Radiance's controls: `-ab` bounces, `-ad` and `-as` samples per hemisphere, `-aa` accuracy, `-ar` spatial resolution.
- **Cache growth.** In a multi-bounce run the deepest level fills first; the average of the upper levels can estimate the constant "ambient" term.
- **Split sphere.** The assumed "pretty bad case" (not a strict worst case) is a point at the centre of a sphere that is half light and half dark, looking at the break. Bounding its partial derivatives gives `ε ≤ |∂E/∂x·(x − x₀) + ∂E/∂ξ·(ξ − ξ₀)|`, then `ε ≤ (4E/(πR))·|x − x₀| + E·|ξ − ξ₀|`, and for a record at `P₀` with normal `N(P₀)`: `ε(P) ≤ (4/π)·E·|P − P₀|/R₀ + E·sqrt(2 − 2·N(P)·N(P₀))`.
- **R₀** is the harmonic mean of the hemisphere rays' lengths, preferred because the radius appears in a denominator; zero lengths are forbidden. The slide itself labels it "average distance to surfaces".
- **Weight and selection.** Dropping the constants gives `w_i(P) = 1/(|P − P_i|/R_i + sqrt(1 − N(P)·N(P_i)))`, and the interpolated value is `E(P) = Σ w_i·E_i/Σ w_i` over `S = {i : w_i(P) > 1/a}`, where `a` is the user's error tolerance. Weights correlate with 1/error, so the weighted average spreads error evenly. With equal normals a record reaches `|P − P_i| < a·R_i`.
- **Behind test.** A record may think it is valid where nearby geometry occludes it. Treating the surface locally as a sphere, a query is rejected as "behind" when `(P − P_i)·(N(P) + N(P_i))/2 < 0`.
- **Storage.** An octree independent of the surfaces, each node listing records whose valid radius is less than the node width; lookup descends until all records in range are found. It even works for volume data, "sort of".
- **Record.** `pos[3]`, `dir[3]` (normal), `lvl` (recursion level of the parent ray), `weight` (of the parent ray), `rad` (valid radius), `val` (colour), `gpos[3]` (gradient with respect to position) and `gdir[3]` (with respect to direction). Level and weight decide when to truncate the ray tree.
- **Placement in practice.** Records space out on flat surfaces far from other geometry and bunch up on outside curves and especially inside corners.

## Gradients (Ward and Heckbert 1992)

- Rotational and translational gradients come almost free from the same hemisphere samples. Ward and Heckbert first meant them to guide spacing; a year later they saw it was better to use them in interpolation, which reduces discontinuities and avoids bias.
- **Rotational:** as the normal turns, the surface sees more or less of a bright object; it is zero at the zenith because the cosine's derivative is zero there. What lies over the horizon cannot be known.
- **Translational:** moving the point exposes or hides occluded objects and shifts boundaries. Disocclusions are assumed to look like the visible part of the background, so a boundary moves with the nearer edge; the formula takes the closer of two neighbouring samples with `min`.
- **Interpolation:** `E(P) = Σ w_i·[E_i + (n̂_i × n̂)·∇_r E_i + (P − P_i)·∇_t E_i]/Σ w_i`, with the same weights. The gradient also caps the valid radius.

## Radiance's implementation (Ward's second talk)

- The ambient "constant" approximates the rest of the infinite series; an average of top-level indirect values is a good estimate, kept as a moving average as the cache fills (`-aw`). Over-estimating it is worse than under-estimating; in practice it is little used.
- Adaptive super-sampling (`-as`) samples high-variance regions of the hemisphere until error is uniform or a limit is reached; it is especially effective in bright daylit interiors.
- Without a minimum record spacing, inside corners resolve to pixel level. A maximum spacing of 64 times the minimum "seems about right". Pixel size could also set spacing, at the cost of view independence.
- The gradient caps spacing only when `‖∇‖·R > 1`, reducing the radius to `1/‖∇‖` to avoid negative values; at the minimum spacing the gradient is reduced instead. The gradient should not set spacing in general, because it is unknown before sampling; a conservative geometric rule is safer.
- Bump maps apply the rotation gradient with the perturbed normal at the final interpolation, so bumps do not reduce sharing and do not leak samples.
- Materials can be excluded from or included in interreflection (`-ae`, `-aE`, `-ai`, `-aI`), which saves hours in fields of grass.
- Processes share records through cache files with lock, read, write and unlock, with a buffer of about 13 records up to about 10 processors; the NFS lock manager is not always reliable. Records are sorted from most to least recently used at growing intervals for memory coherence, which is turned off when more than a third of records are shared.
- Limits: values cached over very different scales leak light if spacing is not limited, and "hairy" geometry (forests, grass) is best left to noisy path tracing. Sources of bias: naive adaptive super-sampling, truncation from limited bounces (caching overrides Russian roulette), spacing limits, and an assumed average reflectance. Scaling sample counts by reflectance and spacing by reflectance^−0.5 distributes errors.
- History: implemented in Radiance around 1986; the first SIGGRAPH submission was rejected and the paper rewritten twice; the code is about 1,500 of Radiance's 30,000 lines.
- **Current code** (not in the course): `ambcomp.c` computes anisotropic valid radii from a radiometric Hessian after Schwarzhaupt, Jensen and Jarosz, "Practical Hessian-Based Error Control for Irradiance Caching" (SIGGRAPH Asia 2012), `ra = sqrt(sqrt(4/eigenvalue))` per axis, clamped between the minimum and maximum radius, falling back to a geometric Hessian. `sumambient` in `ambient.c` rejects records whose normal differs by more than 10° plus `ambacc` radians (relaxed for low-weight rays), applies a modified behind test, tests an elliptical distance with the two radii and the offset along the normal against `ambacc`, runs a leak test (`plugaleak`) for records with a "corral", and weights each record by a hat function, the product of two linear ramps in angle and distance. The 1988 `1/(d/R + sqrt(1 − N·N_i))` form is no longer in the code.

## Problems and fixes (Křivánek)

- **Missed small geometry and leaking rays.** `R_i` should be the mean distance to nearby geometry but is computed from ray lengths, so rays that miss small features, or leak through cracks between polygons, overestimate it and spread a wrong value over a large area. **Neighbour clamping** (EGSR 2006) enforces the triangle inequality: on adding record `j`, for every record `k` with `‖p_j − p_k‖ < R_j + R_k`, set `R_j = min(R_j, R_k + ‖p_j − p_k‖)`, then `R_k = min(R_k, R_j + ‖p_j − p_k‖)`. It equalizes record spacing so it falls off smoothly away from features (examples: 7,761 records at `a = 0.15` without it against 7,752 at `a = 0.35` with it; Sponza 9,638 against 9,416). It cannot fix a leaked record's own wrong value.
- **Too many records in corners:** impose a minimum `R_min`. In world space (Radiance gives it as a fraction of scene size) records are too sparse near the camera and too dense far away; Tabellion and Lamorlette use 1.5 to 3 times the projected pixel size, and 10 times for `R_max` (Radiance: 64 times the minimum).
- **Mean or minimum distance:** the harmonic mean (Ward) misses small features; the minimum ray length (Tabellion and Lamorlette) avoids that. Without neighbour clamping or a gradient limit, the minimum looks much better (mean at `a = 0.07` against minimum at `a = 0.5`, both 14k records); with neighbour clamping, use the mean.
- **Record insertion, in order:** sample the hemisphere (irradiance, gradients, mean or minimum distance `R`); `R = min(R, 1/‖∇_t‖)`; `R' = max(min(R, R_max), R_min)`; if `R < R'`, scale the gradient by `R/R'`; neighbour-clamp using the unclamped `R`, redoing it whenever `R` shrinks (so each record stores `R`, `R'`, `R_min` and `R_max`); insert. Translational gradients explode in corners and are clamped.
- **Uneven interpolation:** filling the cache in scanline order leaves discontinuities, since a new record never reaches pixels already shaded. Two passes fix it: fill the cache first (best-candidate pixel order is best: 6,043 records against 6,167 hierarchical and 7,395 scanline), then render. Raising `a` in the second pass (for example 0.25 to 0.45, 1.8 times) smooths results from few rays (400 per hemisphere) at the cost of some detail.
- **Bounded weights.** Ward's weight is infinite at the record and discontinuous at the border; Radiance hides seams by randomizing acceptance. Two alternatives fall to zero at the border: Tabellion and Lamorlette's `w = 1 − 2a·max(‖p − p_i‖/R_i, 4·sqrt(1 − n·n_i))`, bounded at the record, and Gautron's `w = 1/(‖p − p_i‖/R_i + sqrt(1 − n·n_i)) − 1/a`.
- **Speed:** an octree that references each record from every node it may overlap (as in PBRT) turns lookup into one root-to-leaf walk, at more memory and slower insertion. Reusing the last query's result within a supersampled pixel (same pixel and shader, distance under a projected pixel, normals' dot over 0.95) costs almost nothing; production images make tens of millions of queries.
- Glossy surfaces corrupt translational gradients, so hemisphere sampling ignores the glossy term. With motion blur in a ray tracer, hits are reprojected to `t = 0` before the query.

## Radiance caching for glossy surfaces (Křivánek et al. 2005, 2006)

- A record stores incoming radiance as a vector of (hemi)spherical harmonic coefficients in its local frame, with one translational gradient per coefficient, kept as derivatives along the tangent axes `x` and `y` only (motion along the normal is small in interpolation).
- Interpolation adjusts each record's coefficients by its gradient, then rotates them into the query's frame with an SH rotation, which is the bottleneck and needs an optimized routine.
- Outgoing radiance is the dot product of the interpolated coefficients with the BRDF-times-cosine coefficients, precomputed per discretized outgoing direction in a parabolic parameterization (about a minute per BRDF) and looked up from a texture. Surfaces are chosen by BRDF roughness: sharp reflections and complex geometry are left to importance-sampled Monte Carlo, which radiance caching complements; at equal time it gives smooth results where Monte Carlo is noisy.
- **Adaptive radiance caching:** glossy indirect light depends on lighting, BRDF sharpness and view, so a geometric spacing rule fails more often than for irradiance. Each record gets its own `a_i`; when two contributing records differ by more than a Weber-law threshold (2 to 3% of luminance) the radius of one shrinks, so record density rises where lighting changes fast and with sharper BRDFs.

## Irradiance splatting on the GPU (Gautron et al. 2005)

- Splatting reverses the lookup: each record is drawn as a screen quad covering the projection of its sphere of influence (radius `a·R_k`), and a fragment shader evaluates the weight at each covered pixel's G-buffer position and normal, adding `w·ρ_d·E_k(p)` and `w` to a floating-point splat buffer by blending. A final pass divides by the summed weight and adds direct light.
- The fragment shader rejects early on `‖p − p_k‖²/R_k² + 0.2·(1 − n·n_k) > a²`, then computes `1/w = sqrt(e1) + sqrt(e2)` clamped from below, and adds the gradient terms per colour channel.
- Because every record reaches every pixel it covers, one pass in any order gives the result the octree method needs two passes for. Subtracting `1/a` from Ward's weight removes the circular seams that appear with few records.
- Cache misses are found on the CPU by walking the splat buffer. New records sample their hemisphere by rasterizing the scene from the record with a single camera of about 126° aperture, with border pixels stretched to cover grazing angles (RMS error 5.8% against 10.4% for plain plane sampling and 18.1% for Larsen and Christensen's coverage scaling, over 10,000 values in Sibenik), shaded with view-independent uniform shadow maps (1024², 16-sample PCF) that the final image reuses. A record holds about 22 floats: irradiance, rotational and translational gradients per channel, and the harmonic mean distance; reading back and summing on the CPU beat GPU mipmap summation.
- Results (Quadro FX 3400, Pentium 4 3.6 GHz, 1000×1000, 64×64 hemisphere rasterization): Sibenik (80K triangles, `a = 0.15`, 4,076 records, splatting 188 ms) 14.3 s against Radiance's 425 s, about 30 times faster; Sponza (66K triangles, `a = 0.1`, 4,123 records, splatting 242.5 ms) 13.71 s against 645 s, about 47 times. Records are view-independent, so static scenes fill the cache progressively during interactive walkthroughs.

## Temporal radiance caching (Gautron et al. 2007)

- Recomputing the cache from scratch each frame flickers: record positions change between frames, and since gradient extrapolation is most accurate at a record and worse away from it, the pattern of accuracy changes with them. It also wastes work.
- The fix keeps record positions fixed over time. A temporal weight `w_t(t) = 1/((τ − 1)(t − t₀))`, with `τ = E₁/E₀` the irradiance change rate between consecutive frames (for radiance, the maximum ratio over projection coefficients), gives a record a lifespan: it contributes while `w_t ≥ 1/a_t` and `t − t₀ < t_max`, with `t_max` an ad hoc 5 to 10 frames, because a static neighbourhood gives `τ = 1` and an infinite lifespan. A record that expires is replaced at the same position.
- Temporal gradients, the change of irradiance and of its spatial gradients over time, extrapolate (one pass) or interpolate (two passes) between a record's estimates and suppress the remaining flicker. The method assumes the animation is known in advance.
- Results: flicker removed, with speedups up to 9 times over per-frame computation; with a moving light, flicker is removed but the speedup is only 1.25 times.

## Tabellion and Lamorlette at PDI/DreamWorks (2004)

As cited in the course: record spacing from the minimum ray length instead of the harmonic mean, `R_min` of 1.5 to 3 projected pixels and `R_max` of 10, and a weight bounded at the record. The production details in their own course talk were not read.
