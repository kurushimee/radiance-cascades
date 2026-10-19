# Spectral Imaging in Production

| | |
|---|---|
| Author | Chapter authors Weidlich; Forsythe and Dyer; Mansencal; Hanika; Wilkie; Emrose; Langlands |
| Date | 2021, SIGGRAPH course notes |
| Kind | Course notes, about 90 pages |
| Link | https://jo.dreggn.org/home/2021_spectral_imaging.pdf |

The course covers how film renderers handle colour spectrally: how many wavelengths they carry, how RGB inputs become spectra, and what breaks in single precision. For RC it bounds what a spectral cascade would cost and which uplifting method keeps spectra filterable; DexRT carries 880 wavelengths through its cascades ([2025_osborne_dexrt_ray_acceleration.md](2025_osborne_dexrt_ray_acceleration.md)).

Chapters: 1 Weidlich, material system (pp. 3-8); 2 Forsythe and Dyer, camera characterization (pp. 9-19); 3 Mansencal, LED walls (pp. 21-42); 4 Hanika, spectral upsampling (pp. 43-53); 5 Wilkie, fluorescence, the ART workflow and Spectral OpenEXR (pp. 54-62); 6 Emrose, hero wavelengths at Animal Logic (pp. 63-70); 7 Langlands, Weta's Manuka (pp. 72-79).

## Spectral sample counts

| Use | Samples |
|---|---|
| Smits 1999 basis | 7 basis spectra of 10 samples each (sec. 4.2.2) |
| Hanika's constrained optimization | for example 39 wavelength bins (sec. 4.2.3) |
| Manuka per-vertex spectral inputs | 10 equally spaced bins; heavy on memory and hidden from artists (sec. 1.3.2.2) |
| ART path tracing | 1 nm buckets from a precomputed spectrum; output bands chosen by the user, 16 in Fig. 5.3 |
| Animal Logic Glimpse | hero wavelength chosen stochastically among fixed R, G and B wavelengths (sec. 6.2.2) |
| Manuka paths | 4 randomly offset, uniformly spaced wavelengths per path; colour noise mostly gone by 8 to 16 spp (sec. 7.1) |
| Camera measurement | monochromator sweep 350 to 800 nm in 5 nm steps, 91 samples (sec. 2.2.1.1) |

- Sampling at 10 nm stores about ten times more per colour than RGB, which is why Manuka uplifts RGB to spectra at shading time (sec. 7.1.1).
- Each extra output channel adds image size, splatting hero samples aliases unless the kernel spans more than the nearest bucket, and only lossless compression is considered safe (sec. 5.3).

## RGB to spectrum (ch. 4)

- A spectrum must reproduce its XYZ, the integral of the colour matching functions times `f(λ)` (eq. 4.1). Reflectances are bounded to [0, 1]; emission is unbounded, and scaling keeps its chromaticity, so emission can use a 2D table over xy (Meng) while reflectance needs a 3D table because the spectral shape changes with brightness (sec. 4.1).
- Glassner: convex combinations of three basis wavelengths, with staircase spectra and negative coefficients outside the primaries' gamut.
- Sigmoid polynomial (Jakob and Hanika 2019): `f(λ) = s(p(λ))` with `p(λ) = Σ_i c_i·λ^(d−i−1)` and `s(x) = ½ + x / (2·sqrt(1 + x²))` (eqs. 4.5-4.6). With `d = 3` coefficients it covers all colours. The RGB-to-coefficient map needs Gauss-Newton or a table, and the coefficients need 32-bit floats in a 3D table and do not interpolate linearly (sec. 4.2.4).
- Fourier moments (Peters et al. 2019): the arctangent of a truncated Fourier series with Lagrange multipliers (eq. 4.7), bounded to [0, 1] by construction. Moments interpolate linearly, so ordinary texture filtering works, and they quantize to 10 bits without trouble; 8 bits needs care.
- Clustered PCA (Otsu 2018) recovers shapes from training data per kd-tree cell over xy, with discontinuities at cell borders and possible negative values.
- The AVX sigmoid variant is fastest on CPUs; the table size dominates cost, and GPUs are more memory-bound (sec. 4.2.5).
- Table 4.1 compares methods by compute, table memory, texture format, filterability, gamut, reflectance or emission, and shape. Its texture and filter cells for Jakob-Hanika (3× ui8, filterable) and Peters (3× f32, not filterable) contradict the chapter text, which says the opposite, so those cells were probably shifted in extraction.
- Manuka replaced its Smits solver with Fourier moments for reflectance: three coefficients round-trip the full wide gamut, and although slower in micro-benchmarks than Smits and the sigmoid, the difference is not measurable in a render (sec. 7.2).
- Manuka solves emission curves at startup from `C = M_sRGB·∫ f(λ)·I(λ)·W_cam(λ) dλ` (eq. 7.1) with D65 and the camera response, relaxing the bound to positivity only. It clips to [0, 1] after uplifting rather than before, which keeps more saturation. sRGB covers most of Pointer's gamut of about 4000 real surface colours; the saturated colours outside it are accepted as lost (sec. 7.2.1).

## Precision and transport (ch. 5, 6)

- Hero wavelength sampling weights all wavelengths on a path with the balance heuristic (Wilkie et al. 2014, eq. 6.1); one wavelength per path gives rainbow noise.
- In single precision the product of throughput `f` and pdf `p` underflows: with a 1 mm mean free path and albedo 1 it reaches `FLT_MIN` after 8.73 cm (eq. 6.6). Multiplying both by `1/max(f_r, f_g, f_b, p_r, p_g, p_b)` at each bounce makes single precision match double (eq. 6.5, Fig. 6.5).
- Nested dielectrics count crossings (+1 entering, −1 leaving), which ignores internal surfaces in overlapping or holed geometry (sec. 6.3.2).
- Fluorescence is a 2D re-radiation matrix over input and output wavelength, with ordinary reflectance on the diagonal. Dense storage grows with the square of the sampling; Gaussian mixtures (2021) cut it by orders of magnitude and allow importance sampling. Hero sampling handles it in a path tracer (Mojzik et al. 2018). Spectral OpenEXR (Fichet et al. 2021) stores layered and bi-spectral data with an RGB preview layer.

## Cameras and LED walls (ch. 2, 3)

- Real sensors do not meet the Luther condition, so the 3×3 camera matrix is optimized against spectral measurements.
- CRI uses 8 samples and is poorly uniform; CFI uses 99; TM-30-18 is the reporting standard. Adding an amber primary to an LED wall cut mean ΔE00 by 2.6 and raised Rf from 60 to 80; stacked LEE gels 642 and 738 gave SSI 45 and cut mean ΔE00 by 3.1.
