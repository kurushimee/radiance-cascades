# Radiance Caching for Participating Media

| | |
|---|---|
| Authors | Wojciech Jarosz, Craig Donner, Matthias Zwicker, Henrik Wann Jensen |
| Date | ACM Transactions on Graphics 27(1), article 7, March 2008 |
| Kind | Paper; DOI 10.1145/1330511.1330518 |
| Link | https://cs.dartmouth.edu/~wjarosz/publications/jarosz08radiance.pdf |

The paper caches inscattered radiance at sparse points in a participating medium, each record holding radiance and its spatial gradient, and reuses each record within a radius set by its gradient. It is linked from RC discussions of volumetric transport ([light transport alternatives](2026_light_transport_alternatives.md)) and is the volumetric member of the Ward-style irradiance caching family. Equation numbers are the paper's; eqs. 34 and 35 are partly garbled in text extraction and follow the surrounding prose.

## Transport and estimators

- Extinction `σ_t = σ_a + σ_s`; transmittance `T_r(x ↔ x')` is the exponential of minus the integrated extinction (eq. 3); inscattered radiance is `L_i(x, ω) = ∫ p(x, ω, ω')·L(x, ω') dω'` over the sphere; radiance is constant along empty segments (sec. 2).
- Single scattering as an area integral over surfaces (eqs. 7-9): `L_s(x, ω) = ∫_A p(x, ω, ω̂)·L_r(x' → x)·V(x, x')·H(x, x') dx'`, with reduced radiance `L_r = T_r·L`, visibility `V` and the geometry term `H` with its cosine clamped at 0. The estimator (eq. 11) samples lights and surfaces with `pdf(x_j)`; its gradient (eq. 10) applies the product rule over `p`, `L_r`, `V` and `H`, and the implementation ignores the visibility gradient.
- Multiple scattering (sec. 4, eqs. 28-30): random walks with `N` samples at the first event and one at each later event, distance pdf `σ_t·exp(−σ_t·r_j)` (eq. 29). The gradient translates the whole path, so the phase-function term vanishes because the path's angles do not change. The example scenes use 2K to 8K paths per cache point (sec. 6).
- Directions (sec. 3.4, 4.2, 5.1): isotropic media sample uniformly with pdf `1/(4π)`; anisotropic media store spherical harmonics with `M = 9` coefficients, which the paper says suffice for Henyey-Greenstein with `|g| < 0.6`. A record holds 16 floats (48 bytes) for isotropic media and 28 floats (27 SH coefficients and a radius, 112 bytes by the paper's count) for anisotropic ones.

## Cache

- Three independent caches, each with its own tolerance: single scattering from lights, surface scattering, and multiple scattering, stored in octrees after Ward et al. 1988 (sec. 5).
- Valid radius (sec. 5.2): ideally the largest `r` for which the relative extrapolation error over the ball stays below `ε` (eq. 31), relative because vision responds to contrast. With the log-space gradient `∇ln L = ∇L/L` (eq. 32), the practical radius is `R(x) = ε·Σ_j L_j(x) / Σ_j |∇L_j(x)|` over the record's samples (eq. 34), summing gradient magnitudes so saddle points do not get infinite radii. Colour radii are computed per channel and the minimum kept; anisotropic records use the zero-order SH coefficient. `ε = 0` never reuses, and `ε = 1` reuses until values differ by about 2×. Radii are clamped in world and screen space, gradients are clamped after Křivánek et al. 2006, and the smaller of the shadowed and unshadowed radii is used.
- Extrapolation (eq. 35) is linear in log space: `L(x) = exp(Σ_k w(d_k)·[ln L_k + (∇L_k/L_k)·(x − x_k)] / Σ_k w(d_k))`, with `w(d) = 3d² − 2d³` and `d_k = 1 − |x_k − x|/r_k`, so a record weighs 1 at its center and 0 at its radius.
- Queries take a third to a half of render time; there are millions of queries and thousands of records, and a new record costs 100 to 1000 queries (sec. 6).

## Results

1K×1K, up to 16 spp, one core of a 2.4 GHz Core 2 Duo (sec. 6, captions):

| Scene | Time | Records | Queries | Notes |
|---|---|---|---|---|
| Cornell smoke (Fig. 6) | 1.42, 2.45, 3.65, 7.50 min | | | equal-time path tracing is noisy |
| Sponza atrium (Fig. 8) | 19 min | about 46K | 79M | 512 walks per multiple-scattering record; 40 min of photon tracing left under 1K usable photons |
| Animated smoke (Fig. 9) | 5.8 min per frame | 9K | 8.2M | cache rebuilt per frame, no flicker |
| Two cars in fog (Fig. 10) | 20.35 min | 175K | 27M | 4K paths per record, 60 lights; 8M photons still showed artifacts |

The abstract claims speedups of several orders of magnitude over path tracing and higher quality than volumetric photon mapping.

## Limitations

- Without the visibility gradient the error metric cannot adapt at volumetric shadow edges, so a lower global tolerance is needed.
- Spherical harmonics suit highly directional scattering poorly; a 5D cache with separate spatial and angular error terms is suggested (sec. 7).

## For RC

- The valid radius is an adaptive form of RC's fixed spatial spacing: a record covers a region inversely proportional to its log-gradient, where cascades space probes by interval length alone (inference). The paper also shows the cost of adaptivity: an octree lookup per query and a record set rebuilt per frame for dynamic media.
- Rebuilding the cache every frame of the animated smoke without flicker is a single-frame result: when every record is recomputed from scratch with enough samples, interpolation between records does not flicker (inference from Fig. 9).
- Exponential, log-space extrapolation suits radiance that falls off exponentially in a medium, which is a candidate for interpolating volumetric probes where bilinear blending of linear values smears transmittance (inference).
