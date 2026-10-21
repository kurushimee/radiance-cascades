# Supporting techniques

Methods that RC work uses without owning: sampling patterns, direction maps, resamplers and denoisers, GPU data structures, ray traversal, transport math, formats, shading models, metrics and the frameworks implementations are written in. Each entry gives the definition, the formula or algorithm with its usual parameters, the primary reference, and the notes that use it. Methods that are central to RC are summarized here and covered in full in the topic that owns them: direction maps for cascades in [cascade layout and merging](cascade_layout_and_merging.md), jump flooding and screen-space tracing in [scene representation and tracing](scene_representation_and_tracing.md), visibility bitmasks in [related screen-space GI](related_screen_space_gi.md). Background GI methods (irradiance volumes, light propagation volumes, light-field probes, voxel cone tracing, PoE1's screen-space GI) are in [related probe GI](related_probe_gi.md) and [related screen-space GI](related_screen_space_gi.md).

A reference marked "secondary" was read only through a textbook, survey, specification or encyclopedia page, not in the original.

The entries span three files: sampling, direction maps, resampling and denoising here; GPU data structures, traversal, distance fields and visibility in [structures and tracing](supporting_techniques_structures_and_tracing.md); and transport, numerics, metrics, formats, shading and APIs in [transport, math, formats and APIs](supporting_techniques_transport_and_math.md).

## Contents

- [Sampling and noise](#sampling-and-noise)
  - [Low-discrepancy sequences](#low-discrepancy-sequences)
  - [R2](#r2)
  - [Halton sequence](#halton-sequence)
  - [Hammersley set](#hammersley-set)
  - [Sobol sequence and Owen scrambling](#sobol-sequence-and-owen-scrambling)
  - [Cranley-Patterson rotation](#cranley-patterson-rotation)
  - [Vogel spiral](#vogel-spiral)
  - [Spherical Fibonacci points](#spherical-fibonacci-points)
  - [Blue noise and void-and-cluster](#blue-noise-and-void-and-cluster)
  - [PCG and GPU hashes](#pcg-and-gpu-hashes)
  - [xxHash32](#xxhash32)
  - [Jenkins hashes](#jenkins-hashes)
  - [Interleaved gradient noise](#interleaved-gradient-noise)
  - [Valve's animated dither](#valves-animated-dither)
  - [Arvo's random rotations](#arvos-random-rotations)
- [Direction parameterizations](#direction-parameterizations)
  - [Octahedral map](#octahedral-map)
  - [Equal-area octahedral map (Clarberg)](#equal-area-octahedral-map-clarberg)
  - [HEALPix](#healpix)
  - [Latitude-longitude map](#latitude-longitude-map)
  - [Cube maps and face subdivision](#cube-maps-and-face-subdivision)
  - [Parabolic maps](#parabolic-maps)
  - [Spherical harmonics](#spherical-harmonics)
  - [Ambient cube](#ambient-cube)
  - [Spherical Gaussians](#spherical-gaussians)
  - [Lebedev quadrature](#lebedev-quadrature)
  - [Girard's theorem](#girards-theorem)
  - [Geodesic and tetrahedral subdivision](#geodesic-and-tetrahedral-subdivision)
  - [Lambert cylindrical equal-area projection](#lambert-cylindrical-equal-area-projection)
- [Resampling and sampling theory](#resampling-and-sampling-theory)
  - [Importance sampling](#importance-sampling)
  - [Multiple importance sampling](#multiple-importance-sampling)
  - [Resampled importance sampling (RIS)](#resampled-importance-sampling-ris)
  - [Weighted reservoir sampling](#weighted-reservoir-sampling)
  - [ReSTIR](#restir)
  - [Permutation sampling](#permutation-sampling)
  - [Next-event estimation](#next-event-estimation)
  - [Path guiding](#path-guiding)
  - [Light trees and stochastic lightcuts](#light-trees-and-stochastic-lightcuts)
  - [Stochastic texture filtering and stochastic interpolation](#stochastic-texture-filtering-and-stochastic-interpolation)
- [Denoising, upscaling and temporal reuse](#denoising-upscaling-and-temporal-reuse)
  - [Bilateral filter](#bilateral-filter)
  - [Depth-aware upscaling](#depth-aware-upscaling)
  - [Edge-avoiding à-trous wavelet filter](#edge-avoiding-à-trous-wavelet-filter)
  - [SVGF](#svgf)
  - [BMFR](#bmfr)
  - [OIDN](#oidn)
  - [DLSS Ray Reconstruction](#dlss-ray-reconstruction)
  - [Pull-push](#pull-push)
  - [Temporal anti-aliasing and reprojection](#temporal-anti-aliasing-and-reprojection)
  - [YCoCg](#ycocg)
  - [Hysteresis](#hysteresis)
  - [Temporal Super Resolution](#temporal-super-resolution)
  - [SMAA and FXAA](#smaa-and-fxaa)
  - [Mip bias under upscaling](#mip-bias-under-upscaling)

## Sampling and noise

### Low-discrepancy sequences

Deterministic point sets in `[0,1)^s` that fill the cube more evenly than random points, so averages converge faster than plain Monte Carlo (quasi-Monte Carlo). The star discrepancy `D*_N = sup_B |A(B)/N − vol(B)|` over boxes anchored at the origin measures the worst mismatch between the share of points in a box and its volume, and the Koksma-Hlawka inequality bounds the integration error by `V(f)·D*_N`, with `V` the Hardy-Krause variation of `f`. Reference: Niederreiter, *Random Number Generation and Quasi-Monte Carlo Methods*, SIAM 1992 (secondary). RC traces fixed ray sets, so these matter wherever a renderer jitters probe positions or directions between frames or across probes.

### R2

Roberts's additive recurrence `x_n = fract(0.5 + n·(1/g, 1/g²))` with `g ≈ 1.3247`, the plastic number (the real root of `g³ = g + 1`), the 2D analogue of the golden-ratio sequence. Every prefix is well spread and it costs one multiply-add. Used for probe or ray jitter in [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md), the [Split RC implementations](../sources/2026_split_rc_implementations.md), [HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md), [RCPG](../sources/2026_tauray_rcpg_path_guiding.md) (EMA jitter) and the [line-sweep solvers](../sources/2026_sweep_and_short_characteristics_solvers.md).

### Halton sequence

Coordinate `i` of point `n` is the radical inverse of `n` in the `i`-th prime base: `φ_b(n) = Σ d_k·b^(−k−1)` for `n = Σ d_k·b^k`, the base-`b` digits mirrored across the radix point. Reference: Halton, *Numerische Mathematik* 2, 84-90, 1960. Used in [GIBS](../sources/2021_seed_gibs_surfel_gi.md), [GI-1.0](../sources/2023_boisse_gi10_two_level_radiance_cache.md) and [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md).

### Hammersley set

A fixed `N`-point set whose first coordinate is `k/N` and whose others are Halton radical inverses in the first primes: `x_k = (k/N, φ_2(k), φ_3(k), …)`. Not extensible, since `N` is fixed. Reference: Hammersley, "Monte Carlo methods for solving multivariable problems", *Annals of the New York Academy of Sciences* 86(3), 844-874, 1960. Used in Sannikov's LegitEngine SSVGI (16 samples over 4×4 tiles, [videos](../sources/2022_sannikov_youtube_rc_videos.md)), [Brixelizer GI](../sources/2024_amd_brixelizer_gi.md) and [HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md).

### Sobol sequence and Owen scrambling

Sobol is a base-2 digital sequence: `x_{n,i} = x_{n−1,i} XOR v_{k,i}`, with `k` the position of the lowest zero bit of `n − 1` and direction numbers `v` from published tables (Joe and Kuo for many dimensions). Owen scrambling permutes each digit by a permutation that depends on the higher digits, which keeps the stratification and removes the structured artifacts. Burley's hash-based form reverses the bits, applies a seeded Laine-Karras permutation (add the seed, then four xor-multiply rounds with 0x6c50b47c, 0xb82f1e52, 0xc7afe638, 0x8d22f6e6) and reverses them back. References: Sobol, *USSR Comput. Math. Math. Phys.* 7, 86-112, 1967 (secondary); Owen, "Randomly permuted (t,m,s)-nets and (t,s)-sequences", Springer LNS 106, 1995 (secondary); Burley, "Practical Hash-based Owen Scrambling", JCGT 9(4), 2020. Used in [light transport alternatives](../sources/2026_light_transport_alternatives.md) and [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md).

### Cranley-Patterson rotation

Adds one uniform random vector `c` to every point of a deterministic rule modulo 1: `Q_c f = (1/N) Σ f({x_j + c})`. Averaging `q` independent shifts gives an unbiased estimate, and their spread estimates the error. Reference: Cranley and Patterson, "Randomization of number theoretic methods for multiple integration", *SIAM J. Numer. Anal.* 13, 904-914, 1976 (secondary). A per-frame or per-probe rotation of a fixed RC direction set is this shift. Used in the [Split RC implementations](../sources/2026_split_rc_implementations.md).

### Vogel spiral

Point `n` of a disk at radius `c·√n` and angle `n·α` with the golden angle `α = π(3 − √5) ≈ 2.39996` rad (137.508°), which spreads points without radial bands. Reference: Vogel, "A better way to construct the sunflower head", *Mathematical Biosciences* 44(3-4), 179-189, 1979 (secondary).

### Spherical Fibonacci points

`N` points on the sphere with heights `z_k = 1 − (2k + 1)/N` and azimuths `φ_k = 2πk/Φ`, `Φ = (1 + √5)/2`, which gives near-uniform coverage for any `N`. Keinert et al. add an inverse map that finds the nearest point in constant time without a table. Reference: Keinert, Innmann, Sänger and Stamminger, "Spherical Fibonacci Mapping", ACM TOG 34(6), article 193, 2015 (formula secondary, from Goebl et al., arXiv 1811.01534). These sets do not nest: the directions of `N` points are not a subset of those of `4N`, so a cascade cannot average child directions into a parent, which is why [Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md) rejected them. Used for ray directions in [DDGI](../sources/2019_majercik_ddgi.md), [erhe](../sources/2026_erhe_world_space_rc.md), [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md) and the [voxel 3D repositories](../sources/2026_voxel_3d_rc_repositories.md); golden-angle spirals over the sphere appear in [BeansEngine](../sources/2026_rc_repository_survey.md#joelmartin-devbeansengine-rc-removed-from-history) and tmpvar's 3D direction comparison.

### Blue noise and void-and-cluster

A blue-noise pattern has little low-frequency energy, so its error looks like fine, even grain. Void-and-cluster builds a blue-noise threshold array: start from a random binary pattern, score cells with a Gaussian-weighted neighbour sum on a toroidal grid, move minority pixels from the tightest cluster into the largest void until balanced, then rank every pixel. Reference: Ulichney, "The void-and-cluster method for dither array generation", Proc. SPIE 1913, 332-343, 1993 (secondary). Used for ray jitter in the [2D repositories](../sources/2026_rc_repository_survey.md#2d-variants-worth-knowing), [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md), [volumetric RC](../sources/2026_volumetric_rc.md), [GIBS](../sources/2021_seed_gibs_surfel_gi.md), [daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md) and the [Unity and Unreal plugins](../sources/2026_unity_unreal_rc_plugins.md).

### PCG and GPU hashes

PCG pairs a 64-bit LCG (`state·6364136223846793005 + inc`, `inc` odd) with an output permutation that hides its weak low bits; PCG32's XSH-RR output is `rotr32(((state >> 18) ^ state) >> 27, state >> 59)`. Jarzynski and Olano's survey of GPU hashes found the PCG-based hash a good default; its 32-bit form is `s = x·747796405 + 2891336453; w = ((s >> ((s >> 28) + 4)) ^ s)·277803737; return (w >> 22) ^ w`. References: O'Neill, HMC-CS-2014-0905, 2014; Jarzynski and Olano, "Hash Functions for GPU Rendering", JCGT 9(3), 21-38, 2020. Used in [Coppen's surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md), [Solari](../sources/2025_jms55_bevy_solari.md), [Peters](../sources/2025_peters_jackknife_transmittance.md), the [GPU hash tables note](../sources/2026_gpu_hash_tables_and_sorting.md), [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md), [Split RC implementations](../sources/2026_split_rc_implementations.md) and [Reservoir Cascades](../sources/2026_you_reservoir_cascades.md).

### xxHash32

A fast non-cryptographic 32-bit hash: four accumulators consume 16-byte stripes (`acc = rotl(acc + lane·P2, 13)·P1`), merge as `rotl1 + rotl7 + rotl12 + rotl18`, add the length, fold the tail, and avalanche with `xor >> 15, ·P2, xor >> 13, ·P3, xor >> 16`, with primes P1 to P5 = 0x9E3779B1, 0x85EBCA77, 0xC2B2AE3D, 0x27D4EB2F, 0x165667B1. Reference: Collet, xxHash specification. Used for surfel and probe hashing in [Coppen's surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md) and [GPU hash tables](../sources/2026_gpu_hash_tables_and_sorting.md).

### Jenkins hashes

One-at-a-time: for each byte `h += b; h += h << 10; h ^= h >> 6`, then `h += h << 3; h ^= h >> 11; h += h << 15`. lookup3 mixes three words with rotation rounds (mix: 4, 6, 8, 16, 19, 4; final: 14, 11, 25, 16, 4, 14, 24). References: Jenkins, "A Hash Function for Hash Table Lookup", *Dr. Dobb's Journal*, 1997; lookup3.c, 2006. Used in [SHaRC](../sources/2019_binder_path_space_filtering_and_sharc.md) and [Osborne's radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md).

### Interleaved gradient noise

`IGN(x, y) = fract(52.9829189·fract(0.06711056·x + 0.00583715·y))` from pixel coordinates, no texture fetch. Designed for TAA, where its pattern behaves well across frames. Reference: Jimenez, "Next Generation Post Processing in Call of Duty: Advanced Warfare", SIGGRAPH 2014 Advances course (formula secondary). Used in [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md).

### Valve's animated dither

A per-pixel RGB offset added before 8-bit output to hide banding: `s = dot((171, 231), p + t)`, `v = fract(s/(103, 71, 97)) − 0.5`, output `v/255·0.375`, with `p` the pixel and `t` the time. Reference: Vlachos, "Advanced VR Rendering", GDC 2015. It fixed RC banding on very dark 2D backgrounds with the least change in perceived brightness ([discussions](../sources/2026_rc_discussions.md#implementer-notes)).

### Arvo's random rotations

A uniform random rotation from three uniforms: `θ = 2πu1`, `φ = 2πu2`, `z = 2u3`, `v = (√z·sin φ, √z·cos φ, √(2 − z))`, and `M = (v·vᵀ − I)·R_z(−θ)`, a Householder reflection composed with a rotation about z. Reference: Arvo, "Fast Random Rotation Matrices", *Graphics Gems III*, 117-120, 1992 (algorithm secondary). [DDGI](../sources/2019_majercik_ddgi.md) rotates its Fibonacci ray set this way each frame.

## Direction parameterizations

### Octahedral map

A unit vector is divided by its L1 norm, which puts it on an octahedron; the upper half projects straight down onto the square, and the lower half folds outward over the diagonals: `p = n/(|x| + |y| + |z|)`, and if `z < 0`, `p.xy = (1 − |p.y|, 1 − |p.x|)·sign(p.xy)`. Decoding sets `z = 1 − |x| − |y|`, shifts `x, y` by `saturate(−z)` toward the center and normalizes. The map is continuous across its edges with a mirrored wrap, so a border of copied texels makes hardware bilinear filtering work. Its solid angle per unit square area is `|J| = |p|^(−3)` with `|p|² = 1 + 2·min(1 − |x| − |y|, 0) − 2|x| − 2|y| + 2|xy| + 2x² + 2y²` on `[−1, 1]²` ([RCPG](../sources/2026_tauray_rcpg_path_guiding.md)); it integrates to 4π, equals 1 at the six octahedron vertices and `3√3 ≈ 5.2` at the eight face centers, so texels near face centers cover about 5.2 times the solid angle of texels at the vertices (verified numerically). An unweighted mean of octahedral texels is therefore not the mean over the sphere. References: Engelhardt and Dachsbacher, "Octahedron Environment Maps", VMV 2008; Meyer et al., "On Floating-Point Normal Vectors", CGF 29(4), 2010; Cigolle et al., JCGT 3(2), 2014 ([notes](../sources/2014_cigolle_octahedral_unit_vectors.md)); Narkowicz's encoding post, 2014. The most common direction layout in 3D RC: [tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md), [Gavras](../sources/2025_gavras_screen_probes_world_intervals_thesis.md), [Coppen's surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md), [erhe](../sources/2026_erhe_world_space_rc.md), the [voxel repositories](../sources/2026_voxel_3d_rc_repositories.md), [DDGI](../sources/2019_majercik_ddgi.md), [light-field probes](../sources/2017_mcguire_light_field_probes.md) and many more.

### Equal-area octahedral map (Clarberg)

A map of the square to the sphere with constant Jacobian, so every texel covers the same solid angle and a 2×2 child block is exactly a quarter of its parent at every level ([notes](../sources/2008_clarberg_equal_area_sphere_mapping.md)). Used in [Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md), [Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md), [Split RC](../sources/2026_freeman_split_radiance_cascades.md), [Coppen's surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md) and the [screen-space RC](../sources/2026_screen_space_rc.md) and [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md) findings. RCPG weighs it against the plain octahedral map in [sampling and guiding](rc_for_sampling_and_guiding.md).

### HEALPix

Equal-area, iso-latitude pixels in a hierarchy of 12·4^k cells ([notes](../sources/2005_gorski_healpix.md)); its nesting matches RC's ×4 directions per 3D cascade. Mentioned in [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md), [screen-space RC](../sources/2026_screen_space_rc.md) and [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md).

### Latitude-longitude map

Texel `(u, v)` holds `θ = π(v + 0.5)/H`, `φ = 2π(u + 0.5)/W`, covering `(2π²/(W·H))·sin θ` steradians, so rows near the poles must be weighted by `sin θ` when averaging or importance sampling. References: Blinn and Newell, "Texture and reflection in computer generated images", CACM 19(10), 542-547, 1976 (secondary); PBRT 3rd ed., section 12.6. Used by [KingTheFifth's screen probes](../sources/2026_rc_repository_survey.md#screen-probes-with-voxel-intervals-kingthefifth), [Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md) and the [voxel repositories](../sources/2026_voxel_3d_rc_repositories.md).

### Cube maps and face subdivision

Six square faces, each a 90° perspective view; a direction picks the face of its largest component and projects the other two by dividing by it. Texels near face corners cover less solid angle than those at face centers. Splitting each face into `2^c × 2^c` cells gives `6·4^c` directions that nest across levels. Reference: Greene, "Environment mapping and other applications of world projections", IEEE CG&A 6(11), 21-29, 1986 (secondary). Used in fad's original Shadertoy (cube-map storage), [Rulkens's cube mapper](../sources/2025_rulkens_rc_medical_volume_data_thesis.md), [layered distance maps](../sources/2007_umenhoffer_layered_distance_maps.md) and others. Wan and Wong's isocube is a six-face layout with near-equal solid angle per texel (GDC 2007).

### Parabolic maps

Two maps, one per hemisphere, with front coordinates `(x/(1 + z), y/(1 + z))` and back `(x/(1 − z), y/(1 − z))`, remapped to `[0, 1]`; view-independent, no singularity, two textures. Reference: Heidrich and Seidel, "View-independent Environment Maps", Graphics Hardware 1998. Sannikov's "Radiance Cascades Rendered Directly" stores each probe as a small cube map in a parabolic projection ([videos](../sources/2022_sannikov_youtube_rc_videos.md)).

### Spherical harmonics

Orthonormal functions on the sphere by band `l` (`2l + 1` per band). Projecting distant light onto bands 0 to 2 (9 coefficients) and convolving with the clamped cosine (band factors `π`, `2π/3`, `π/4`) gives irradiance with about 1% average error, written as `E(n) = nᵀMn` for `n = (x, y, z, 1)` with constants `c1 = 0.429043`, `c2 = 0.511664`, `c3 = 0.743125`, `c4 = 0.886227`, `c5 = 0.247708`. L1 (4 coefficients) keeps only bands 0 and 1, enough for irradiance with a dominant direction. Reference: Ramamoorthi and Hanrahan, "An Efficient Representation for Irradiance Environment Maps", SIGGRAPH 2001. RC implementations use SH to compress cascade 0 for the final gather ([mpalenque/sim](../sources/2026_rc_repository_survey.md#3d), [AliMoghimii](../sources/2026_rc_repository_survey.md#alimoghimiivulkan-ray-tracing-with-radiance-cascades-3d-world-space-rc-on-branches)) and Love and Deepspace stores luma SH plus two chroma scalars ([talks](../sources/2026_rc_conference_talks.md)); the paper lists SH as one storage option.

### Ambient cube

Six scalars or colours, one per axis direction, read with weights `n²` per axis toward the normal's sign. Reference: McTaggart, "Half-Life 2 / Valve Source Shading", GDC 2004 (secondary, through Valve's patent US 7,227,548). Used in [HSGI](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md) and [daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md).

### Spherical Gaussians

Lobes `G(v) = a·exp(λ(μ·v − 1))` with closed-form integral `2π(a/λ)(1 − e^(−2λ))` and closed-form products, a compact basis for lighting. Reference: Wang et al., "All-Frequency Rendering of Dynamic, Spatially-Varying Reflectance", ACM TOG 28(5), 2009 (secondary); Pettineo and Hill's SG series, 2016.

### Lebedev quadrature

Sphere quadrature with points in orbits of the octahedral group and weights chosen to integrate polynomials up to a given degree exactly; the weights sum to 4π and the smallest rule is the six axis points. Reference: Lebedev, "Quadratures on a sphere", *Zh. Vychisl. Mat. Mat. Fiz.* 16(2), 293-306, 1976 (secondary). Mentioned as a direction-set option in [screen-space RC](../sources/2026_screen_space_rc.md).

### Girard's theorem

A spherical triangle with angles `α, β, γ` on the unit sphere has area `α + β + γ − π`. Reference: Girard, *Invention nouvelle en l'algèbre*, 1629 (secondary). [Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md) uses it for per-direction solid-angle weights of the tetrahedral mapper.

### Geodesic and tetrahedral subdivision

Split each face of a Platonic solid into triangles and project the vertices onto the sphere; frequency `ν = b + c` and triangulation number `T = b² + bc + c²` classify the result. Splitting every triangle into four per level gives `4·4^c` directions from a tetrahedron or `20·4^c` from an icosahedron, both nesting across levels. Reference: Fuller, US patent 2,682,235, 1954 (icosahedral); Wenninger, *Spherical Models*, 1979 (secondary). [Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md) uses the tetrahedral form.

### Lambert cylindrical equal-area projection

`x = λ − λ0`, `y = sin φ`; area is preserved because `dy = cos φ·dφ`. Reference: Lambert, 1772 (secondary). The building block of equal-area sphere maps.

## Resampling and sampling theory

### Importance sampling

Estimate `∫f` as `(1/n) Σ f(X_i)/p(X_i)` with `X_i ~ p`; unbiased if `p > 0` wherever `f ≠ 0`, low variance when `p` resembles `f`. Reference: PBRT 4th ed., section 2.2.2. RC traces fixed uniform ray sets and so does not importance sample ([discussions](../sources/2026_rc_discussions.md)); the guiding work uses cascades as the `p` ([sampling and guiding](rc_for_sampling_and_guiding.md)).

### Multiple importance sampling

Combine techniques `i` with `n_i` samples each by weighting each sample with the balance heuristic `w_i = n_i·p_i/Σ_j n_j·p_j` or the power heuristic `w_i = (n_i·p_i)^β/Σ_j (n_j·p_j)^β`, usually `β = 2`. Reference: Veach and Guibas, "Optimally Combining Sampling Techniques for Monte Carlo Rendering", SIGGRAPH 1995. Used in [RCPG](../sources/2026_tauray_rcpg_path_guiding.md), [Reservoir Cascades](../sources/2026_you_reservoir_cascades.md) and [Peters](../sources/2025_peters_jackknife_transmittance.md).

### Resampled importance sampling (RIS)

Draw `M` candidates from an easy `p`, weight each by `w_j = p̂(x_j)/p(x_j)` against a target `p̂`, keep one with probability `w_z/Σw_j`, and estimate `f(x_z)/p̂(x_z)·(1/M)·Σw_j`. Reference: Talbot, Cline and Egbert, "Importance Resampling for Global Illumination", EGSR 2005 (formula secondary). Used in [Reservoir Cascades](../sources/2026_you_reservoir_cascades.md), [Solari](../sources/2025_jms55_bevy_solari.md) and [HSGI](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md).

### Weighted reservoir sampling

A one-item reservoir over a stream keeps item `i` with probability `w_i/Σ_{j≤i} w_j`, storing only the current pick and the running weight sum. References: Chao, *Biometrika* 69(3), 653-656, 1982; Vitter, ACM TOMS 11(1), 37-57, 1985 (both secondary). The reservoir in every ReSTIR variant.

### ReSTIR

Each pixel streams candidate light samples through a reservoir, then merges reservoirs from neighbours (spatial reuse) and from the previous frame (temporal reuse), so the effective candidate count far exceeds the rays traced; the shading weight is `W = w_sum/(M·p̂(y))`, and the history length `M` is capped. ReSTIR GI applies it to the first indirect bounce's path; generalized RIS (ReSTIR PT) moves samples between pixels through shift mappings with their Jacobians and handles correlated samples and unknown densities. References: Bitterli et al., ACM TOG 39(4), 2020; Ouyang et al., CGF (HPG 2021); Lin et al., "Generalized Resampled Importance Sampling: Foundations of ReSTIR", ACM TOG 41(4), 2022. Its temporal reuse is what single-frame RC gives up; [Reservoir Cascades](../sources/2026_you_reservoir_cascades.md) puts reservoirs inside cascades, and [kajiya](../sources/2022_stachowiak_kajiya_gi.md), [Solari](../sources/2025_jms55_bevy_solari.md) and Love and Deepspace's second version used it ([related radiance caches](related_radiance_caches.md)).

### Permutation sampling

kajiya's variant of temporal reservoir reuse that reads the history at a permuted pixel offset to break correlation between neighbours ([kajiya](../sources/2022_stachowiak_kajiya_gi.md)).

### Next-event estimation

Estimate direct light by sampling a point on a light, tracing a shadow ray and converting the area density to solid angle, `(1/N) Σ f·L_d·|cos θ|/p(ω)`, and combine it with BSDF sampling by MIS so no light is counted twice. Reference: PBRT 3rd ed., section 14.3. The community wiki files vlam as RC-guided NEE, but vlam guides path directions and samples no lights; RCPG guides indirect directions with cascades and combines them with NEE by MIS ([sampling and guiding](rc_for_sampling_and_guiding.md#cascades-and-light-sampling)).

### Path guiding

Learn an approximation of incident radiance while rendering and sample directions from it; Müller et al. store it in an SD-tree (a spatial binary tree whose leaves hold directional quadtrees), refined with unbiased samples. References: Müller, Gross and Novák, "Practical Path Guiding for Efficient Light-Transport Simulation", CGF 36(4), 2017; Vorba et al., "Path Guiding in Production", SIGGRAPH 2019 course. [Sampling and guiding](rc_for_sampling_and_guiding.md) covers RC used this way.

### Light trees and stochastic lightcuts

A BVH over emitters whose nodes aggregate energy, bounds and orientation; one random number walks it, choosing children by estimated importance, and Yuksel's stochastic lightcuts sample the cut instead of fixing it, turning correlated error into noise. References: Conty Estevez and Kulla, "Importance Sampling of Many Lights with Adaptive Tree Splitting", HPG 2018; Yuksel, "Stochastic Lightcuts", HPG 2019. Used in [GIBS](../sources/2021_seed_gibs_surfel_gi.md) and named in [RCPG](../sources/2026_tauray_rcpg_path_guiding.md).

### Stochastic texture filtering and stochastic interpolation

Pick one texel from the filter kernel per lookup, with probability equal to its weight, instead of blending before shading; temporal accumulation or a denoiser removes the noise. Reference: Pharr, Wronski, Salvi and Fajardo, "Filtering After Shading With Stochastic Texture Filtering", PACMCGIT 7(1), 2024. kajiya used stochastic interpolation between cache entries to hide blockiness ([kajiya](../sources/2022_stachowiak_kajiya_gi.md)), Enshrouded blends overlapping cascades stochastically ([talks](../sources/2026_rc_conference_talks.md#enshrouded-a-cascaded-probe-cache)), and 2D RC demos add noise to cascade interpolation for a painted look. A single-frame RC without a denoiser cannot use it (inference).

## Denoising, upscaling and temporal reuse

### Bilateral filter

A weighted average whose weights fall off with both distance and value difference, `BF[I]_p = (1/W_p) Σ_q G_s(|p − q|)·G_r(|I_p − I_q|)·I_q`, so edges survive. Reference: Tomasi and Manduchi, "Bilateral Filtering for Gray and Color Images", ICCV 1998, 839-846. Joint (cross) bilateral upsampling computes the range weight on a full-resolution guide such as depth: Kopf, Cohen, Lischinski and Uyttendaele, "Joint Bilateral Upsampling", ACM TOG 26(3), 2007. Depth- and normal-weighted versions are how screen-space RC upsamples and interpolates probes ([Gavras](../sources/2025_gavras_screen_probes_world_intervals_thesis.md), [Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md), the paper's SPWI variant); the paper argues that band-limited interval data needs only plain linear interpolation ([core theory](core_theory.md)).

### Depth-aware upscaling

Joint bilateral upsampling with depth (and often normals) as the guide; edge-aware upscaling is the general form, with any edge signal (depth, normals, colour) as the guide. Variants: Sannikov's 4XXSWS and MXjcWK choose subsets of the bilinear footprint by depth ([Shadertoys](../sources/2023_rc_shadertoys_hrc_3d_and_other.md#depth-aware-upscaling-and-occlusion)), pixelmager's gist weights by depth ([notes](../sources/2021_pixelmager_depth_aware_upscaling.md)); details in [3D screen space](3d_screen_space.md).

### Edge-avoiding à-trous wavelet filter

Repeated passes of a B3-spline kernel whose tap spacing doubles each pass, multiplied by edge-stopping weights on colour, normal and depth, which approximates a large bilateral filter cheaply. Reference: Dammertz, Sewtz, Hanika and Lensch, HPG 2010 (secondary). Used in [HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md), [Phreakyx](../sources/2026_phreakyx_godot_rc_gdextension.md) and lixu0073/2DGI.

### SVGF

Temporal accumulation with motion vectors, a luminance variance estimate from the history, and an à-trous filter steered by that variance, for 1 sample per pixel path tracing. Reference: Schied et al., "Spatiotemporal Variance-Guided Filtering", HPG 2017. Named in [GIBS](../sources/2021_seed_gibs_surfel_gi.md), [HDDAGI](../sources/2026_godot_hddagi_dynamic_gi.md) and Love and Deepspace's talk.

### BMFR

Regresses noisy colour on noise-free feature buffers (albedo, normal, position) per image block with polynomial features, solved by a fast augmented QR factorization with stochastic regularization. Each pixel reads only its own features, which is why Love and Deepspace chose it over SVGF for its ReSTIR version ([talks](../sources/2026_rc_conference_talks.md)). Reference: Koskela et al., "Blockwise Multi-Order Feature Regression for Real-Time Path Tracing Reconstruction", ACM TOG 38(5), 2019.

### OIDN

Intel Open Image Denoise, an Apache-2.0 library of pretrained neural denoisers taking colour plus optional albedo and normal buffers. Used offline for references in [Split RC](../sources/2026_freeman_split_radiance_cascades.md) and [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md) findings.

### DLSS Ray Reconstruction

NVIDIA's neural denoiser in DLSS 3.5 (2023), which replaces hand-tuned ray-tracing denoisers using temporal and spatial data; no algorithm is published. Used by [Solari](../sources/2025_jms55_bevy_solari.md). Version 4.5 (DLSS SDK 310.9.1, 2026-09-08) is a second-generation transformer, Preset F, that runs on every RTX generation; on Turing and Ampere it costs up to 25 to 29% of the frame rate for lack of FP8. NVIDIA documents nothing on its bias or convergence against a converged image ([DLSS Ray Reconstruction 4.5](../sources/2026_dlss_ray_reconstruction_4_5.md)).

### Pull-push

Fill holes in a sparse image through a pyramid: the pull pass averages known texels into coarser levels weighted by coverage, and the push pass fills unknown fine texels from the level above. References: Gortler et al., "The Lumigraph", SIGGRAPH 1996 ([notes](../sources/1996_light_field_and_lumigraph.md)); Grossman and Dally, "Point Sample Rendering", 1998 (secondary). Used in Sannikov's imperfect shadow maps, bakjedev's 2D RC (1-3-3-1 weights) and [light transport alternatives](../sources/2026_light_transport_alternatives.md).

### Temporal anti-aliasing and reprojection

Jitter each frame by a sub-pixel offset and blend into a history reprojected with motion vectors, `h_t = a·c + (1 − a)·reproject(h_{t−1})`, rejecting or clamping stale history. Reference: Karis, "High-Quality Temporal Supersampling", SIGGRAPH 2014 Advances course. Neighbourhood clamping (colour box clamping) limits the history to the min/max (or mean ± γσ, variance clipping) of the current 3×3 neighbourhood, tighter in YCoCg: Salvi, "An Excursion in Temporal Supersampling", GDC 2016 (secondary). PoE2 ships without TAA ([history](history_and_landscape.md#exilecon-2023-and-path-of-exile-2)).

### YCoCg

`Y = R/4 + G/2 + B/4`, `Co = R/2 − B/2`, `Cg = −R/4 + G/2 − B/4`; the lifting form YCoCg-R (`Co = R − B; t = B + Co/2; Cg = G − t; Y = t + Cg/2`) is exactly invertible on integers. Reference: Malvar and Sullivan, JVT-I014r3, 2003. Used for history clamping and compression in [SHaRC](../sources/2019_binder_path_space_filtering_and_sharc.md) and [volumetric RC](../sources/2026_volumetric_rc.md).

### Hysteresis

The weight `h` on the old value in an exponential moving average, `x_t = h·x_{t−1} + (1 − h)·s_t`. After `n` frames a change has decayed to `h^n`, so reaching 90% of a change in `n` frames needs `h ≤ 0.1^(1/n)` (derived). Reference: Majercik et al., DDGI, JCGT 8(2), 2019 ([notes](../sources/2019_majercik_ddgi.md)). Used in [light-field probes](../sources/2017_mcguire_light_field_probes.md), [GI-1.0](../sources/2023_boisse_gi10_two_level_radiance_cache.md), [erhe](../sources/2026_erhe_world_space_rc.md) and praxis's target ([history](history_and_landscape.md#adoption-shipped-tried-and-turned-down)).

### Temporal Super Resolution

Unreal's temporal upscaler: jittered rendering at a lower resolution, motion-vector reprojection, parallax-based disocclusion detection, shading rejection, flicker analysis and history resurrection; convergence takes about `1000/(ScreenPercentage²·fps)` ms, with `r.TSR.History.SampleCount` 16 by default. Reference: Epic, "Temporal Super Resolution in Unreal Engine" documentation. Lumen leans on it ([Lumen](../sources/2022_wright_lumen_siggraph_advances.md)).

### SMAA and FXAA

Post-process anti-aliasing from the final image: SMAA detects edges, measures their pattern with search and area lookup textures and blends neighbours (Jimenez, Echevarria, Sousa and Gutierrez, CGF 31(2), 2012); FXAA is a cheaper single-pass luma-edge filter (Lottes, NVIDIA, 2009). Single-frame GI pairs with these instead of TAA: Blackline's demos use FXAA 3 ([Blackline](../sources/2026_blackline_interactive_spatium_rc.md#hardware-and-engine)); Godot ships SMAA ([Godot GI internals](../sources/2026_godot_gi_internals.md)).

### Mip bias under upscaling

An upscaler renders at lower resolution, so textures are sampled with a negative bias, `mipBias = log2(render/display) − 1` in AMD's FSR guidance. Reference: AMD FidelityFX Super Resolution 3.1.4 documentation. Named in [on-surface caches](../sources/2024_tatzgern_on_surface_radiance_caches.md) and [screen-space RC](../sources/2026_screen_space_rc.md).
