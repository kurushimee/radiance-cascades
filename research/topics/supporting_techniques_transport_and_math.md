# Supporting techniques: transport, math, formats and APIs

Glossary entries for light transport and solver math, interpolation and footprints, numerics and statistics, image metrics, formats and colour, shading, and frameworks and GPU APIs. The entry format and the other categories are in [supporting techniques](supporting_techniques.md).

## Contents

- [Light transport and solver math](#light-transport-and-solver-math)
  - [Radiometric quantities](#radiometric-quantities)
  - [Lambertian BRDF](#lambertian-brdf)
  - [Beer-Lambert law](#beer-lambert-law)
  - [Opacity correction](#opacity-correction)
  - [Phase functions](#phase-functions)
  - [Delta tracking](#delta-tracking)
  - [Radiative transfer equation and discrete ordinates](#radiative-transfer-equation-and-discrete-ordinates)
  - [Non-LTE radiative transfer](#non-lte-radiative-transfer)
  - [Short characteristics](#short-characteristics)
  - [Radon and Hough transforms, projection-slice theorem](#radon-and-hough-transforms-projection-slice-theorem)
  - [Jacobi iteration](#jacobi-iteration)
  - [Anderson acceleration](#anderson-acceleration)
  - [Fast multipole method](#fast-multipole-method)
  - [Hankel functions](#hankel-functions)
  - [Nyquist-Shannon sampling](#nyquist-shannon-sampling)
  - [FFT convolution](#fft-convolution)
  - [Laplace diffusion](#laplace-diffusion)
- [Interpolation and footprints](#interpolation-and-footprints)
  - [Multilinear interpolation](#multilinear-interpolation)
  - [Cone footprint](#cone-footprint)
  - [Convex offset filtering](#convex-offset-filtering)
- [Numerics and statistics](#numerics-and-statistics)
  - [Gauss-Radau quadrature](#gauss-radau-quadrature)
  - [expm1](#expm1)
  - [Index of dispersion](#index-of-dispersion)
  - [Coefficient of variation](#coefficient-of-variation)
  - [AR(1)](#ar1)
  - [Beurling-Selberg functions](#beurling-selberg-functions)
  - [IRLS](#irls)
  - [2-means clustering](#2-means-clustering)
  - [White furnace test](#white-furnace-test)
- [Image metrics](#image-metrics)
  - [FLIP](#flip)
  - [SSIM](#ssim)
  - [MSE, RMSE, MAE, PSNR, MAPE](#mse-rmse-mae-psnr-mape)
- [Formats and colour](#formats-and-colour)
  - [R11G11B10F](#r11g11b10f)
  - [RGB9E5](#rgb9e5)
  - [RGB10A2](#rgb10a2)
  - [sRGB](#srgb)
  - [Tone mapping](#tone-mapping)
  - [Reversed Z](#reversed-z)
- [Shading](#shading)
  - [GGX](#ggx)
  - [Split-sum approximation](#split-sum-approximation)
  - [Multiple-scattering energy compensation](#multiple-scattering-energy-compensation)
  - [Linearly transformed cosines](#linearly-transformed-cosines)
- [Frameworks and GPU APIs](#frameworks-and-gpu-apis)
  - [Subgroup operations](#subgroup-operations)
  - [UAV barriers and typed UAV loads](#uav-barriers-and-typed-uav-loads)
  - [Shader execution reordering](#shader-execution-reordering)
  - [Float atomics](#float-atomics)

## Light transport and solver math

### Radiometric quantities

Radiance `L = d²Φ/(dω·dA⊥)` is constant along a ray in vacuum; irradiance `E = ∫ L cos θ dω` is power per area on a surface; fluence (in RC usage, after biomedical optics' fluence rate) is `∫_{4π} L dω`, the radiance integrated over all directions without a cosine. A uniform field `L` gives `E = πL` on a surface and fluence `4πL` in 3D or `2πL` in 2D. Reference: PBRT 4th ed., ch. 4. 2D RC codes disagree on whether they output fluence or mean radiance, a factor 2π in brightness ([cascade layout](cascade_layout_and_merging.md)).

### Lambertian BRDF

`f = ρ/π`, so outgoing radiance is `ρ·E/π`, and under uniform `L` it is `ρL`. Reference: Lambert, *Photometria*, 1760; PBRT 3rd ed., section 8.3. The cosine-weighted integral of cascade 0 against the normal is the diffuse gather of every RC renderer; [Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md) shows the error of weighting each cone by its center cosine.

### Beer-Lambert law

Transmittance through a medium is `T = exp(−∫σ_t ds)`. References: Bouguer 1729, Lambert 1760, Beer 1852 (secondary). The volumetric form of RC's interval transmittance `β` ([core theory](core_theory.md)).

### Opacity correction

A sample of opacity `α` taken over step `Δx` has transmittance `1 − α`; at step `Δx'` the equivalent opacity is `α' = 1 − (1 − α)^(Δx'/Δx)`, so total absorption is unchanged. Reference: Engel et al., *Real-Time Volume Graphics*, 2006 (secondary); GPU Gems ch. 39. Needed when coarse cascades march with longer steps ([volumetric](volumetric_and_radiative_transfer.md)).

### Phase functions

The angular distribution of scattering in a medium; Henyey-Greenstein `p(cos θ) = (1 − g²)/(4π(1 + g² − 2g·cos θ)^(3/2))` with `g` the mean cosine, isotropic at `g = 0`. Reference: Henyey and Greenstein, "Diffuse radiation in the Galaxy", ApJ 93, 70-83, 1941. Used in [Jarosz](../sources/2008_jarosz_radiance_caching_participating_media.md), [volumetric RC](../sources/2026_volumetric_rc.md) and Godot's fog ([compositor examples](../sources/2026_godot_compositor_effect_examples.md)).

### Delta tracking

Sample collisions in a heterogeneous medium against a majorant `σ_maj ≥ σ_t`: fly `s = −ln ξ/σ_maj`, accept a real collision with probability `σ_t(x)/σ_maj`, else continue unchanged. Reference: Woodcock et al., ANL-7050, 1965 (secondary). Named in [volumetric RC](../sources/2026_volumetric_rc.md).

### Radiative transfer equation and discrete ordinates

`Ω·∇I = j − (k_a + k_s)ρI + (k_sρ/4π)∫I dΩ`; without scattering the formal solution is `I(s) = I(s0)e^(−τ) + ∫ j·e^(−τ) dx`. Discrete ordinates replace the angular integral with `Σ_j w_j I(s_j)` over fixed directions. Reference: Chandrasekhar, *Radiative Transfer*, 1950 (secondary). RC is a hierarchical discrete-ordinates scheme in which the ordinate count grows with distance ([core theory](core_theory.md), [volumetric](volumetric_and_radiative_transfer.md)).

### Non-LTE radiative transfer

Solves the radiation field together with atomic level populations when they depart from local thermodynamic equilibrium, iterating formal solutions of the transfer equation with statistical equilibrium, accelerated by an approximate Λ operator. References: Rybicki and Hummer, A&A 245, 1991; Osborne and Milić, "The Lightweaver Framework", arXiv 2107.00475. Osborne's RC work solves this problem ([notes](../sources/2024_osborne_radiance_cascades_radiative_transfer.md)).

### Short characteristics

Solve the formal transfer equation at each grid point along a short segment to the nearest upstream cell boundary, interpolating the upstream intensity: `I = I_up·e^(−Δτ) + ∫_0^{Δτ} S(t)e^(−t) dt`. Reference: Kunasz and Auer, JQSRT 39, 67, 1988 (secondary). Compared with RC in [sweep solvers](../sources/2026_sweep_and_short_characteristics_solvers.md).

### Radon and Hough transforms, projection-slice theorem

The Radon transform integrates a function along every line; the projection-slice theorem says the 1D Fourier transform of a projection is a central slice of the 2D transform; the Hough transform is its discrete voting form, `ρ = x·cos θ + y·sin θ`. References: Radon, 1917; Bracewell, *Aust. J. Phys.* 9(2), 1956; Hough, US patent 3,069,654, 1962; Duda and Hart, CACM 15(1), 1972 (all secondary). HRC's line-space structure is a discrete Radon transform ([holographic RC](holographic_rc.md#building-rays-the-acceleration-structure)).

### Jacobi iteration

Solve `Ax = b` by `x_i^(k+1) = (b_i − Σ_{j≠i} a_ij x_j^(k))/a_ii`, every update independent and parallel; converges when the spectral radius of `D⁻¹R` is below 1. Reference: Jacobi, *Astronomische Nachrichten* 22, 1845. Bounce iteration over frames in a radiance cache is a Jacobi iteration of the rendering equation ([light transport alternatives](../sources/2026_light_transport_alternatives.md)).

### Anderson acceleration

Speeds up a fixed-point iteration `x = f(x)` by combining the last `m` iterates with weights that minimize the combined residual, `x_{k+1} = (1 − β)Σα_i x_i + βΣα_i f(x_i)`. References: Anderson, J. ACM 12(4), 1965; Walker and Ni, SIAM J. Numer. Anal. 49(4), 2011 (secondary). Proposed for multi-bounce convergence in [light transport alternatives](../sources/2026_light_transport_alternatives.md).

### Fast multipole method

Evaluates all pairwise `1/r` interactions in O(N) for a tolerance by representing far clusters with multipole expansions translated to local expansions. Reference: Greengard and Rokhlin, J. Comput. Phys. 73, 325-348, 1987. nema-nya describes its doubling cascades as a multipole expansion ([survey](../sources/2026_rc_repository_survey.md#2d-variants-worth-knowing)); RC's distance-dependent resolution is the same far-field idea (inference).

### Hankel functions

The outgoing 2D Helmholtz Green's function is `G = (i/4)·H0⁽¹⁾(k|x − y|)`, behaving like `−ln r/(2π)` near the source. Reference: standard (secondary). Used in Sannikov's wave-optics tests ([LegitCascades](../sources/2024_sannikov_legitcascades.md#wave-optics-tests)).

### Nyquist-Shannon sampling

A signal with no frequencies above `B` is determined by samples at a rate above `2B` and rebuilt by sinc interpolation; below that it aliases. Reference: Shannon, "Communication in the presence of noise", Proc. IRE 37(1), 1949. The penumbra condition is a sampling-rate rule of this kind ([core theory](core_theory.md)); [merging and ringing](../sources/2026_merging_and_ringing.md) and the [lumigraph](../sources/1996_light_field_and_lumigraph.md) use it.

### FFT convolution

Convolution is pointwise multiplication of spectra; zero-pad to length `N ≥ L + M − 1` to avoid wrap-around, O(N log N). Used in [light transport alternatives](../sources/2026_light_transport_alternatives.md) and LegitEngine's water solver.

### Laplace diffusion

Solving `∇²u = 0` (or a diffusion step) by relaxation; an HRC-based hierarchical solver ran a 129² grid in 3 to 4 ms ([HRC](../sources/2026_holographic_rc.md)).

## Interpolation and footprints

### Multilinear interpolation

Linear interpolation along each dimension in turn: bilinear (4 taps), trilinear (8), quadrilinear (16, trilinear in space plus linear between two mip levels, as voxel cone tracing samples a cone's radius: [VCT](../sources/2011_crassin_voxel_cone_tracing.md)) and pentalinear (32, trilinear over the 8 surrounding probes times bilinear over 4 direction texels). Pentalinear is the full continuous reading of a 3D cascade in position and direction, which [tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md) planned for its debug view. A merge that averages a parent's fixed child directions needs only the trilinear part per direction (derived, [cascade layout](cascade_layout_and_merging.md)).

### Cone footprint

A cone of half-angle `θ` from a point has radius `r(t) = t·tan θ` at distance `t`, and sampling it from a prefiltered structure uses the level whose cell size matches `2r(t)`. A pixel cone (`θ` from the pixel's angular size) sets the sphere-trace hit threshold in [tmpvar's 3D grid](../sources/2024_tmpvar_rc_3d_grid.md) (2 × cone radius at `t`). In RC, a cascade's angular spacing and interval distance define an implicit cone footprint per ray, which is the quantity the penumbra condition keeps bounded ([core theory](core_theory.md)). Cone footprints through voxel mips have no closed form ([GigaVoxels](../sources/2011_crassin_gigavoxels_thesis.md)).

### Convex offset filtering

daGI2's fix for leaks when probes or samples sit on the border of the convex volume they interpolate in: samples are pushed off the border into the volume before filtering ([daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md)).

## Numerics and statistics

### Gauss-Radau quadrature

A Gauss rule with one endpoint fixed as a node, exact for polynomials up to degree `2n − 2` with `n` nodes. Reference: Radau, 1880 (secondary, IMSL documentation). Osborne integrates intervals this way ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md), [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md)).

### expm1

`expm1(x) = e^x − 1` without cancellation near zero, so `1 − e^(−x) = −expm1(−x)` keeps precision for thin segments. Reference: C99/C++11 `expm1`. Used in [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md).

### Index of dispersion

`D = σ²/μ`, 1 for a Poisson process, above 1 for clustering. Used in [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md).

### Coefficient of variation

`CV = σ/μ`, a unitless relative spread for ratio-scale data.

### AR(1)

`X_t = φX_{t−1} + ε_t`, stationary for `|φ| < 1`, with autocorrelation `φ^k` at lag `k`; models frame-to-frame correlation of a temporally reused estimate. Used in [Reservoir Cascades](../sources/2026_you_reservoir_cascades.md).

### Beurling-Selberg functions

Band-limited functions that majorize or minorize `sgn(x)` or an interval indicator with minimal integral error. Reference: Vaaler, Bull. AMS 12, 1985 (secondary). Proposed for band-limited interval weights in [screen-space RC](../sources/2026_screen_space_rc.md).

### IRLS

Minimize `Σ|r_i|^p` by repeated weighted least squares with weights `|r_i|^(p−2)` from the last iteration, regularized near zero (`1/max(δ, |r_i|)` at `p = 1`). Used in [screen-space RC](../sources/2026_screen_space_rc.md).

### 2-means clustering

Lloyd's algorithm with two centroids: assign points to the nearer, move centroids to their means, repeat; in 1D it is a threshold at the midpoint of the two means. Reference: Lloyd, IEEE Trans. Inf. Theory 28(2), 1982. Used to split a tile's depths into two layers in [screen-space RC](../sources/2026_screen_space_rc.md) and [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md).

### White furnace test

Under uniform unit illumination a white, energy-conserving material or renderer must reproduce the environment exactly; darker means lost energy, brighter means gained. Used to check RC normalization in [Coppen's surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md), [HRC](../sources/2026_holographic_rc.md), [merging and ringing](../sources/2026_merging_and_ringing.md) and [volumetric RC](../sources/2026_volumetric_rc.md). For single-frame RC it is the cheapest end-to-end check of interval coverage, merge weights and gather normalization together (inference).

## Image metrics

### FLIP

A full-reference metric that maps the difference a viewer perceives when flipping between two images, given viewing distance and pixel size; HDR-FLIP evaluates several exposures. References: Andersson et al., "FLIP: A Difference Evaluator for Alternating Images", HPG 2020; Andersson, Nilsson, Shirley and Akenine-Möller, "Visualizing Errors in Rendered High Dynamic Range Images", Eurographics 2021 short papers. "LIP" in some notes is FLIP with its mirrored F lost. Used in [RCPG](../sources/2026_tauray_rcpg_path_guiding.md), [Gavras](../sources/2025_gavras_screen_probes_world_intervals_thesis.md), [Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md), [on-surface caches](../sources/2024_tatzgern_on_surface_radiance_caches.md) and [Split RC implementations](../sources/2026_split_rc_implementations.md).

### SSIM

`SSIM = (2μxμy + c1)(2σxy + c2)/((μx² + μy² + c1)(σx² + σy² + c2))` over local windows, `c1 = (0.01L)²`, `c2 = (0.03L)²`. Reference: Wang, Bovik, Sheikh and Simoncelli, IEEE TIP 13(4), 600-612, 2004. Used in [Kaméus](../sources/2025_kameus_spwi_probe_placement_thesis.md), [Gerassimov](../sources/2026_gerassimov_rc_vs_unity_gi.md), [Lambru](../sources/2021_lambru_realtime_gi_game_engines_comparison.md) and [RCPG](../sources/2026_tauray_rcpg_path_guiding.md).

### MSE, RMSE, MAE, PSNR, MAPE

`MSE = mean((I − K)²)`, `RMSE = √MSE`, `MAE = mean|I − K|`, `PSNR = 10·log10(MAX²/MSE)`, `MAPE = 100·mean|(A − F)/A|`. For HDR renders `MAX` has no natural value and must be stated, and MAPE is undefined at black pixels, so relative metrics on images need a floor. Used in [HRC](../sources/2025_freeman_holographic_radiance_cascades.md), [HSGI](../sources/2023_lightspeed_hsgi_hierarchical_surfel_gi.md), [RCPG](../sources/2026_tauray_rcpg_path_guiding.md), [DDGI resampling](../sources/2021_majercik_ddgi_resampling.md) and [Reservoir Cascades](../sources/2026_you_reservoir_cascades.md).

## Formats and colour

### R11G11B10F

Three unsigned floats in 32 bits: R and G with 5-bit exponent and 6-bit mantissa, B with 5 and 5, bias 15, maximum 65024 (R, G) and 64512 (B), no sign and no alpha. Relative precision is about 1.6% (R, G) and 3.1% (B) per step (derived from the mantissas). Reference: Microsoft, "Floating-point rules (Direct3D 10)". Common for cascades and probes ([DDGI](../sources/2019_majercik_ddgi.md), [daGI2](../sources/2026_gaijin_dagi2_dynamic_gi.md), the Osborne slides' demo, [merging and ringing](../sources/2026_merging_and_ringing.md)), but it has no room for transmittance, which must live elsewhere.

### RGB9E5

Three 9-bit mantissas sharing one 5-bit exponent (bias 15), maximum `(511/512)·2^16 = 65408`, non-negative only, no alpha. Reference: GL_EXT_texture_shared_exponent. Godot stores GI in it ([Godot GI internals](../sources/2026_godot_gi_internals.md)); Enshrouded's E5B9G9R9 probes are the same format ([talks](../sources/2026_rc_conference_talks.md#enshrouded-a-cascaded-probe-cache)). Small channels lose precision against a bright one sharing the exponent, a source of drift when merged values are re-stored ([artifacts and fixes](artifacts_and_fixes.md)).

### RGB10A2

Three 10-bit unorm channels and a 2-bit alpha; Microsoft DXGI format 24. Used in [Mayaux](../sources/2018_mayaux_horizon_based_indirect_lighting.md), [DDGI](../sources/2019_majercik_ddgi.md) and ErwinTerpstra's Unity RC (10-bit ARGB2101010).

### sRGB

Decode `c_l = c_s/12.92` for `c_s ≤ 0.04045`, else `((c_s + 0.055)/1.055)^2.4`; encode with the inverse, threshold 0.0031308. An sRGB texture decodes to linear before filtering, and its alpha stays linear. References: Stokes, Anderson, Chandrasekar and Motta, "A Standard Default Color Space for the Internet – sRGB", 1996; IEC 61966-2-1; EXT_texture_sRGB. Averaging encoded values darkens results, which several 2D RC codes did by mistake ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md), Suslik's McSyWm, [rc-linear](../sources/2026_rc_repository_survey.md#2d-variants-worth-knowing)).

### Tone mapping

Reinhard's global operator `L/(1 + L)` after scaling by the key over the log-average luminance (Reinhard, Stark, Shirley and Ferwerda, SIGGRAPH 2002); Narkowicz's ACES fit `saturate(x(2.51x + 0.03)/(x(2.43x + 0.59) + 0.14))` (2016 blog post); AgX, Sobotka's log-encoded, matrix-wrapped S-curve transform from Blender. The fad and testbed Shadertoy lines use `1 − (1 + F)^−2.5` ([Shadertoys](../sources/2023_rc_shadertoys.md#parameters-across-the-2d-implementations)).

### Reversed Z

Map the near plane to depth 1 and far to 0 in a float depth buffer, so float precision, densest near 0, balances perspective's `1/z`; in OpenGL this needs `glClipControl(…, GL_ZERO_TO_ONE)` (EXT/ARB_clip_control). Reference: Reed, "Depth Precision Visualized", 2015. Godot uses reversed Z, which matters when reading its depth in compute ([compositor examples](../sources/2026_godot_compositor_effect_examples.md)); also [three-rc](../sources/2025_bennett_three_rc.md) and [screen-space RC](../sources/2026_screen_space_rc.md).

## Shading

### GGX

`D(h) = α²/(π((n·h)²(α² − 1) + 1)²)`, a microfacet distribution with a long tail, usually with `α = roughness²`. Reference: Walter, Marschner, Li and Torrance, "Microfacet Models for Refraction through Rough Surfaces", EGSR 2007 (after Trowbridge and Reitz, 1975). Used in [gomezzz](../sources/2026_gomezzz_godot_3d_radiance_cascades.md) and [RCPG](../sources/2026_tauray_rcpg_path_guiding.md).

### Split-sum approximation

Specular image lighting as the product of a prefiltered environment map (one mip per roughness) and a BRDF table of scale and bias indexed by `n·v` and roughness: `L ≈ prefiltered(r)·(F0·A + B)`. Reference: Karis, "Real Shading in Unreal Engine 4", SIGGRAPH 2013 course. Lazarov's and Karis's 2014 analytic fit of `(A, B)` (`EnvBRDFApprox`, the `F_AB` term of Unreal's mobile shading) replaces the table on mobile; three-rc uses it ([three-rc](../sources/2025_bennett_three_rc.md)). The paper's specular cones query RC like a prefiltered map ([core theory](core_theory.md)).

### Multiple-scattering energy compensation

Single-scattering microfacet BRDFs lose energy at high roughness; Kulla and Conty add a lobe built from the directional albedo `E(μ)` and its average, and Filament scales specular by `1 + F0(1/r − 1)` from the DFG table. References: Kulla and Conty, "Revisiting Physically Based Shading at Imageworks", SIGGRAPH 2017 course; Fdez-Agüera, JCGT 8(1), 2019. Godot's shading applies it ([indirect diffuse paths](../sources/2026_godot_indirect_diffuse_paths.md)).

### Linearly transformed cosines

A BRDF lobe approximated by a clamped cosine under a fitted 3×3 matrix stored per view angle and roughness, which keeps a closed-form integral over polygons. Reference: Heitz, Dupuy, Hill and Neubelt, SIGGRAPH 2016. RCPG fits LTC lobes to guide sampling ([RCPG](../sources/2026_tauray_rcpg_path_guiding.md)).

## Frameworks and GPU APIs

| Name | What it is | Where used |
|---|---|---|
| MiniEngine | Microsoft's DirectX 12 starter kit in DirectX-Graphics-Samples (C++, MIT) | [Dell'Ova](../sources/2025_dellova_rc_performance_scaling_thesis.md), ClaikoCode's DX12 RC ([screen-probe repositories](../sources/2026_screen_space_probe_repositories.md)) |
| LuisaCompute | C++ GPU framework with an embedded kernel DSL and CUDA, DirectX, Metal, Vulkan and CPU backends (Apache-2.0; Zheng et al., "LuisaRender", ACM TOG 41(6), 2022) | the HRC and Split RC reference code ([HRC references](../sources/2025_hrc_and_2d_reference_implementations.md)) |
| OptiX | NVIDIA's ray tracing framework with ray-generation, intersection and shading programs on RT cores | [Split RC](../sources/2026_freeman_split_radiance_cascades.md), [DDGI resampling](../sources/2021_majercik_ddgi_resampling.md) |
| Kokkos | C++ performance-portability library with CUDA, HIP, SYCL, OpenMP and threads backends (Apache-2.0 with LLVM exception) | DexRT since v0.4.0 |
| wgpu | pure-Rust WebGPU over Vulkan, Metal, D3D12, OpenGL and the web (Apache-2.0 or MIT) | [X3XfRM ports](../sources/2024_mathis_x3xfrm_surface_probe_rc.md), Helio ([discussions](../sources/2026_rc_discussions.md#implementer-notes)), [HRC](../sources/2026_holographic_rc.md) |
| Slang | shading language and compiler targeting HLSL, SPIR-V, GLSL, Metal, WGSL, CUDA and CPU, hosted by Khronos since 2024 (Apache-2.0 with LLVM exception) | [Coppen's surfel RC](../sources/2025_coppen_surfel_radiance_cascades.md), bakjedev's RC, BeansEngine |
| TypeGPU, unplugin-typegpu | Software Mansion's typed WebGPU toolkit (MIT) and its bundler plugin that compiles TypeScript functions marked `'use gpu'` to WGSL | [TypeGPU RC](../sources/2026_software_mansion_typegpu_radiance_cascades.md) |
| Gigi | EA SEED's node-graph prototyping tool that generates DX12, WebGPU or Unreal code (Windows, DX12) | [Gigi RC](../sources/2026_gigi_and_volume_rc_repositories.md) |

### Subgroup operations

`GL_KHR_shader_subgroup` (Vulkan 1.1) lets invocations of a subgroup share values without shared memory: basic, vote, arithmetic, ballot, shuffle, shuffle-relative, clustered and quad operations. Quad shuffles (`quadSwapX/Y` in WGSL) averaging four ray threads gained about 10% on a screen-space RC ray pass ([screen-space RC](../sources/2026_screen_space_rc.md)); reductions and ballots serve compaction in [sparse 3D RC](../sources/2026_sparse_and_3d_rc.md).

### UAV barriers and typed UAV loads

In D3D12 a UAV barrier makes all earlier UAV accesses to a resource finish before later ones start; typed UAV loads read a UAV in a given format, with R32 float, uint and sint always allowed and more behind a capability. In Vulkan the equivalents are pipeline barriers between dispatches and storage-image formats. Each top-down merge step needs one such barrier ([cascade layout](cascade_layout_and_merging.md), [Godot integration](godot_integration.md)).

### Shader execution reordering

NVIDIA's 2022 feature that regroups ray-tracing work across threads for coherence. Not available through Godot.

### Float atomics

`VK_EXT_shader_atomic_float` and `GL_EXT_shader_atomic_float` (2020) add atomic float add and exchange on buffers, shared memory and r32f images; without them, sums are scaled to fixed point and accumulated with integer `atomicAdd`, which is also order-independent and so reproducible (Defour and Collange, FedCSIS 2015). Godot's `RenderingDevice` shaders cannot rely on float atomics, as Lambru et al. found in OpenGL ([Lambru](../sources/2021_lambru_realtime_gi_game_engines_comparison.md)); any splat step needs integer encoding or a gather.
