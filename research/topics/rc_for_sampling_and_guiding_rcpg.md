# RC for sampling and guiding: RCPG

RCPG (Ikkala, Jääskeläinen and Mäkitalo, ACM TOG 2026) builds a world-space 3D cascade volume and samples path-tracing directions from it, with tauray as the renderer: cascades, interval bounds, mapping and culling, gathering, sampling, implementation, evaluation and code. Its comparison with Reservoir Cascades and vlam, and the connections, single-frame assessment and open questions for both are in [RC for sampling and guiding](rc_for_sampling_and_guiding.md).

## Contents

- [RCPG: product path guiding with radiance cascades](#rcpg-product-path-guiding-with-radiance-cascades)
  - [Cascades](#cascades)
  - [Parallax-based interval bounds](#parallax-based-interval-bounds)
  - [Mapping and culling](#mapping-and-culling)
  - [Ray casting and gathering](#ray-casting-and-gathering)
  - [Sampling](#sampling)
  - [Implementation and bandwidth](#implementation-and-bandwidth)
  - [Evaluation](#evaluation)
  - [Limits and future work](#limits-and-future-work)
  - [Tauray code](#tauray-code)
  - [Derived points](#derived-points)

## RCPG: product path guiding with radiance cascades

"RCPG: Real-Time Product Path Guiding Using Radiance Cascades" by Julius Ikkala, Pekka Jääskeläinen and Markku Mäkitalo (Tampere University) appeared in ACM Transactions on Graphics 46(2), 1-25, online 2026-10-09, DOI 10.1145/3840291; the Tampere group page lists it under 2027, the issue year. It is open access (25 pages), and the renderer is tauray (https://github.com/vga-group/tauray, LGPL-2.1, `--renderer=rc` and `--renderer=rc-restir`). The README says the paper's exact version lives in a separate `rcpg` branch and that tauray is no longer developed; the code described here is the default branch, and its volume, culling and temporal parts apply to RC for GI too ([notes](../sources/2026_tauray_rcpg_path_guiding.md)).

The world-space 3D cascade volume serves as a guiding distribution for a path tracer, not as the final lighting. The paper claims bounds on radiance intervals so the hierarchy does not misplace incoming directions; one sampler for the product of incoming radiance and the BSDF; a PDF that can be evaluated for any direction, so it combines with MIS and unbiased ReSTIR; and a world-space structure that serves off-screen path vertices, which multi-bounce guiding needs. Against earlier real-time guiding with multi-sample MIS it traces about twice the paths per pixel in a real-time frame.

### Cascades

- Every cascade is a power-of-two cube grid over the whole scene, each texel holding radiance and transparency. A step up halves probe density, doubles angular resolution per axis and moves the interval out, each interval longer than the last ([notes](../sources/2026_tauray_rcpg_path_guiding.md#cascades-sec-31)).
- A cascade holds `M³N²` texels and the next `(M/2)³·(2N)² = M³N²/2`, so storage is `O(M0³·N0²)`, the same as one probe grid at cascade 0's resolution, and most texels belong to short intervals, which trace faster. At most `log₂ M0` cascades exist, and one whose `t_min > L·√3` (`L` the largest extent of the scene bounds) starts outside all geometry and is skipped.
- Spatial lookups are nearest-neighbour, so each probe has one parent. Each texel is integrated over its solid angle and its cell's volume by jittering ray origins in the cell and directions in the texel, averaged with an exponential moving average of `α = 1/30`. One deterministic ray per texel, as in the original paper, cannot represent detail below a minimum size.
- Unlike SD-trees, the structure never splits adaptively, which keeps GPU traversal free of divergence, and space and direction are coupled: short-range light at high spatial and low angular resolution, long-range light the reverse.

### Parallax-based interval bounds

- Jittering origins over the cell low-pass filters the probe image: a point at distance `t` is smeared over the parallax angle under which the cell sees it. The bound uses the cell's inscribed circle (edge `l`), smaller than the cell from every direction, which carries to 3D as a sphere's equator: `θ_min = 2·arcsin(l/(2·t_max))` ([notes](../sources/2026_tauray_rcpg_path_guiding.md#parallax-based-interval-bounds-sec-32)).
- Taking `θ_min` as the window width, the passband tops out at `f_max = 1/θ_min`, and Nyquist requires `f_max < f_s/2` for the probe's angular sampling rate `f_s`, precomputed by brute force from the longest angle across the largest texel. Then `t_max = l/(2·sin(1/f_s))`.
- With `l` and `f_s` doubling per cascade and `sin` nearly linear near zero, `t_max ∝ 4^i`. The original paper's penumbra condition gives `t ∝ 2^i` (its 3D `l = 2`), while Osborne and Sannikov use `4^i`. Power-of-two lengths let adjacent probes see parallax larger than a texel's angular radius, giving double images under linear interpolation or wasted resolution under jitter; diffuse lighting hides this, but the direction of incoming light is misrepresented, which rules them out for guiding. The source note also credits `4^i` to the HRC paper, whose own rays double per level; the [HRC topic](holographic_rc.md#connections) resolves that attribution.
- The conservative bound wastes probe resolution over most of the interval, so the measured configuration doubles it, `t'_max = l/sin(1/f_s)`, with `f_s` taken across the shortest edge of the smallest texel, which switches from wasted resolution to lost detail near the middle of the interval. Using the conservative bound as `t_min` instead also works but samples slightly worse.

### Mapping and culling

- Equal-area maps (Clarberg; Mortari et al. 2011) give uniform resolution per solid angle and a constant Jacobian, but sampling projects every corner of every texel it visits, so the octahedral map, with no transcendental functions, wins ([direction maps](supporting_techniques.md#direction-parameterizations)). Its Jacobian is `|J| = (1 + 2·min(1 − |x| − |y|, 0) − 2|x| − 2|y| + 2|xy| + 2x² + 2y²)^(−3/2)` for `x, y ∈ [−1, 1]`, computed once per sample ([notes](../sources/2026_tauray_rcpg_path_guiding.md#probe-mapping-and-culling-sec-33-34)).
- A 128³ cascade 0 with 16 texels per probe, two rays per texel (primary and shadow) and 5 cascades would need about 130 million rays. Probes whose cell overlaps no geometry are never used under nearest-neighbour lookup, so the scene is voxelized conservatively by rasterization at cascade 0's resolution, coarser levels mark a voxel occupied if any of its 2×2×2 children is, and empty cells are culled. A per-cell count of occupied frames lets returning geometry reuse old probe data. The paper calls the culling not core to the method.

### Ray casting and gathering

- One ray per texel per frame, with origin and direction jittered by an `R_5` sequence (3 dimensions of position, 2 of direction), averaged over frames, which delays updates. Back faces are ignored so that jittered origins inside geometry still pass through and contribute ([notes](../sources/2026_tauray_rcpg_path_guiding.md#ray-casting-and-gathering-sec-35-36)).
- A hit is shaded with one light sample per frame from a light BVH; any light type works if the probe-update light sampler supports it (area lights, environment maps and spotlights are shown).
- Multiple bounces shade hits from the previous frame's gathered cascade 0, treating each texel as an area light evaluated with LTC; shading a 1280×720 image this way took about 0.5 ms, with colour lost and nearest-neighbour blocks obvious (Fig. 7). Errors there only add noise to guiding.
- Explicit point and directional lights stay out of the probes and go to next-event estimation, since texels are too coarse for small lights; RCPG targets indirect light and emissive meshes. With the sun inside the cascades, 8 spp leave shaded areas near sunlit edges slow to converge, worse than 4 spp with NEE at about equal ray counts (Fig. 8).
- Gathering runs from the highest cascade down: each texel takes the light of its 4 child texels in the next cascade, alpha-blended behind it by its coverage, so a texel holds all light from its direction, not only its interval's. A floor `L_avg·γ` with `γ = 0.05` (probe-wide average luminance at cascade 0, a 2×2 neighbourhood above) keeps stochastic zeros from biasing sampling; a larger `γ` means more noise but fewer outliers.

### Sampling

- Texels are weighted as polygonal area lights through LTC, with irradiance `E = (1/2π)·Σ arccos(p_i·p_j)·((p_i × p_j)/|p_i × p_j|)·n` over vertices clipped to the upper hemisphere ([LTC](supporting_techniques_transport_and_math.md#linearly-transformed-cosines)). The inverse matrix uses a 3-parameter fit with rows `(a, 0, b)`, `(0, 1, 0)` and `(0, 0, c)`, `a, b, c ∈ [0, 1]`: the lobe stays non-zero over the whole hemisphere, which keeps sampling unbiased, and points above the horizon stay above, so clipping can precede the transform and the diffuse and specular lobes share it. At grazing angles with low roughness the fit turns bimodal with a weak retro-reflective lobe ([notes](../sources/2026_tauray_rcpg_path_guiding.md#sampling-sec-4)).
- A sample descends the hierarchy: every texel of the cascade 0 probe containing the point is weighed and one is chosen by weighted random sampling, then one of the 4 texels it covers in the next cascade, and so on to the finest cascade. Weights use the separability approximation `∫L·ρ·cos dω ≈ ∫L dω · ∫ρ·cos dω`, with the stored luminance as the first factor and LTC with clamped vertices as an approximate horizon clip for the second; that underestimates grazing texels but cannot bias, because the PDF uses the same weights.
- Inside the final texel the direction is uniform over its solid angle (used in all measurements; faster, but it can go below the horizon) or drawn by LTC polygon-light sampling (Peters 2021) with exact clipping, which never goes below the horizon and helps large texels with narrow lobes. In the ablation the latter was 25% slower in path tracing for SSIM 0.0842 against 0.0837 (Fig. 22).

### Implementation and bandwidth

- A baseline with 16 texels at cascade 0, four floats per texel, 5 cascades and linear spatial interpolation reads 4096 bytes per sample, about 475 GB/s at 1920×1080 and 60 Hz ([notes](../sources/2026_tauray_rcpg_path_guiding.md#implementation-sec-5)). RCPG stores luminance in R32F and visibility in R8 in separate textures, so one gather reads a 2×2 luminance footprint and visibility only for the chosen texel; half floats caused artifacts in the moving average. Nearest-neighbour lookups in space and direction cut bandwidth by 8× more, leaving visible edges in noise level that denoisers or ReSTIR hide. The total is about 15.4 GB/s.
- The 4096 bytes are all 16 cascade 0 texels plus 4 child texels in each of 4 more cascades, at 16 bytes and 8 trilinear corners each: `(16 + 4·4)·16·8`. RCPG's footprint is the 16 cascade 0 luminances plus one visibility byte, then 4 luminances and one visibility byte per further cascade: `64 + 1 + 4·17 = 133` bytes. At 124.4 million samples per second these give 474.6 and 15.4 GiB/s, so the paper's GB are GiB (derived).
- The arccos term is rewritten for a tangent-space normal as `Σ arccos(p_i·p_j)/(2π·|sin(arccos(p_i·p_j))|)·(p_ix·p_jy − p_iy·p_jx)`, and `arccos(d)/(2π·|sin(arccos d)|)` is approximated by `(−0.709693·d³ + 3.787823·d² + 20.448902·d + 15.951386)^(−1/2)`. Most sampling math runs in 16-bit floats for double-rate FMA.
- Bounces use RCPG samples alone, not MIS with BSDF samples: single-sample MIS raised noise at equal sample counts and frame time by 40 to 80% through divergence. MIS with NEE or a light tree is recommended.

### Evaluation

The setup: RTX 3090, 1920×1080, 1000 warm-up frames, GPU timings averaged over 250 frames, references at 262,144 spp, and MAE in linear colour plus PSNR, SSIM and FLIP after Reinhard tone mapping ([metrics](supporting_techniques_transport_and_math.md#image-metrics)); equal-time runs target 33.33 ms ([notes](../sources/2026_tauray_rcpg_path_guiding.md#evaluation-sec-6-8)). RCPG uses 4×4 texels at cascade 0, a 128³ grid, uniform in-texel sampling and 5 cascades: 2,396,672 probes and 310 MB allocated in every scene. Scenes keep roughness above 0.05 and lose normal maps and transparency; explicit lights replace emissive surfaces because VXPG did not sample them, and NEE picks lights uniformly. ReSTIR GI runs unbiased, one bounce, with one temporal and one spatial neighbour, a 32-pixel radius and a history cap of 8. VXPG runs at 128³ (its default is 64³) with multi-sample MIS.

| Scene (Table 1) | Bounds | Active probes | Active memory | `t_0` | `t_1` | `t_2` | `t_3` | `t_4` |
|---|---|---|---|---|---|---|---|---|
| Ajar | 11.30 × 4.80 × 9.20 | 127,067 | 31.7 MB | 0.126 | 0.564 | 2.521 | 10.72 | 44.24 |
| Breakfast | 11.62 × 9.32 × 14.43 | 99,447 | 27.4 MB | 0.161 | 0.720 | 3.221 | 13.69 | 56.51 |
| Classroom | 10.17 × 3.11 × 8.51 | 113,740 | 26.9 MB | 0.113 | 0.508 | 2.270 | 9.652 | 39.83 |
| Rungholt | 655 × 69 × 550 | 70,936 | 13.9 MB | 7.309 | 32.69 | 146.2 | 621.6 | 2565 |
| Staircase | 7.02 × 7.84 × 10.59 | 175,886 | 40.0 MB | 0.118 | 0.528 | 2.363 | 10.05 | 41.47 |
| Kitchen | 6.92 × 3.38 × 8.65 | 117,288 | 30.1 MB | 0.097 | 0.432 | 1.931 | 8.213 | 33.89 |

FLIP against the reference (lower is better), with spp for the equal-time runs and ms for the ReSTIR runs at 1 spp (Tables 2 to 7):

| Scene | 1 bounce: PT / SSPG / VXPG / RCPG | 2 bounces: PT / VXPG / RCPG | ReSTIR: PT / VXPG / RCPG |
|---|---|---|---|
| Ajar | 0.235 (37) / 0.186 (14) / 0.039 (13) / 0.094 (23) | 0.336 (22) / 0.127 (4) / 0.164 (11) | 0.155 (5.55) / 0.105 (15.16) / 0.083 (12.43) |
| Breakfast | 0.174 (28) / 0.158 (8) / 0.156 (7) / 0.112 (19) | 0.197 (16) / 0.277 (2) / 0.183 (9) | 0.156 (7.03) / 0.147 (32.32) / 0.116 (14.38) |
| Classroom | 0.215 (21) / 0.175 (7) / 0.226 (6) / 0.151 (16) | 0.261 (12) / 0.347 (2) / 0.223 (6) | 0.181 (8.55) / 0.183 (32.48) / 0.137 (17.92) |
| Rungholt | 0.144 (20) / 0.113 (5) / 0.212 (5) / 0.106 (13) | 0.169 (12) / 0.273 (2) / 0.133 (7) | 0.180 (11.73) / 0.213 (27.75) / 0.120 (22.80) |
| Staircase | 0.232 (29) / 0.171 (9) / 0.217 (8) / 0.132 (19) | 0.289 (17) / 0.343 (3) / 0.212 (8) | 0.173 (6.68) / 0.214 (23.66) / 0.116 (14.67) |
| Kitchen | 0.245 (27) / 0.261 (9) / 0.282 (7) / 0.216 (18) | 0.365 (15) / 0.414 (3) / 0.344 (8) | 0.299 (8.57) / 0.350 (18.11) / 0.282 (15.37) |

- VXPG wins Ajar, whose single rectangular slit fits voxels. RCPG leads Classroom, Rungholt and Staircase in every metric with 2 to 3 times the samples, and samples Breakfast's caustic best. In Kitchen, with metallic surfaces and occluded lights, unguided PT beats RCPG in PSNR and SSIM. With ReSTIR, RCPG is best by most metrics, but VXPG wins MAE in Ajar, Breakfast and Rungholt, plausibly from temporal flicker of its stochastic light injection.
- After one bounce, intersection points diverge between neighbouring pixels, and the scattered reads into the guiding structure slow both VXPG and RCPG: in Breakfast unguided PT manages twice RCPG's sample count at two bounces.
- Over the first 64 frames PT and VXPG are flat, RCPG stabilizes more slowly because of its moving average, and SSPG takes hundreds of frames, settling at MAE 0.158 in Staircase. RCPG's PDFs sit between SSPG's and VXPG's in detail and match the ground-truth magnitudes better than either (Fig. 15). Fireflies from small high-contribution regions make RCPG's MSE worse than PT's in Breakfast and Staircase; a single-sample MIS configuration with a plain average (9 to 12 spp) improves only MSE.
- At the 33.33 ms budget one sample per pixel costs 0.90 to 1.67 ms for PT and 1.45 to 2.56 ms for one-bounce RCPG (derived from the spp).

Per-pass cost at 1 spp in ms (Table 8):

| Scene | Voxelization | Probe culling | RC trace | RC gather | Path tracing | Tone mapping | Total |
|---|---|---|---|---|---|---|---|
| Ajar, 1 bounce | 0.29 | 0.06 | 0.70 | 0.27 | 1.66 | 0.09 | 3.04 |
| Breakfast, 1 bounce | 0.24 | 0.06 | 0.63 | 0.22 | 1.99 | 0.08 | 3.22 |
| Classroom, 1 bounce | 0.35 | 0.06 | 0.83 | 0.23 | 2.47 | 0.09 | 4.03 |
| Rungholt, 1 bounce | 2.27 | 0.05 | 1.67 | 0.12 | 2.41 | 0.08 | 6.60 |
| Staircase, 1 bounce | 0.27 | 0.06 | 0.99 | 0.33 | 1.92 | 0.09 | 3.66 |
| Kitchen, 1 bounce | 0.38 | 0.06 | 0.78 | 0.23 | 1.95 | 0.08 | 3.48 |
| Ajar, 2 bounces | 0.29 | 0.06 | 1.10 | 0.26 | 3.18 | 0.08 | 4.97 |
| Breakfast, 2 bounces | 0.25 | 0.06 | 1.07 | 0.22 | 4.18 | 0.08 | 5.86 |
| Classroom, 2 bounces | 0.36 | 0.06 | 1.35 | 0.24 | 5.55 | 0.08 | 7.64 |
| Rungholt, 2 bounces | 2.31 | 0.06 | 1.77 | 0.12 | 4.59 | 0.09 | 8.94 |
| Staircase, 2 bounces | 0.28 | 0.06 | 1.75 | 0.34 | 4.12 | 0.09 | 6.64 |
| Kitchen, 2 bounces | 0.39 | 0.06 | 1.32 | 0.25 | 4.00 | 0.08 | 6.10 |

The cascade passes (voxelization, culling, trace and gather) take 1.15 to 1.65 ms, 36 to 45% of the one-bounce frame, in the indoor scenes and 4.11 ms (62%) in Rungholt, where voxelization alone is 2.27 ms; the recursive second bounce multiplies the trace by 1.57 to 1.77 indoors and 1.06 in Rungholt (derived).

Ablations at 1 spp (Tables 9 and 10):

| Cascade 0 grid (Staircase) | RC build (ms) | Sampling (ms) | FLIP |
|---|---|---|---|
| 16³ | 0.09 | 1.56 | 0.462 |
| 32³ | 0.15 | 1.70 | 0.436 |
| 64³ | 0.36 | 1.69 | 0.412 |
| 128³ | 1.38 | 1.92 | 0.383 |
| 256³ | 6.06 | 1.82 | 0.360 |

| Cascade 0 texels (Classroom) | RC build (ms) | Sampling (ms) | FLIP |
|---|---|---|---|
| 4×4 | 1.12 | 2.47 | 0.364 |
| 8×8 | 3.20 | 2.74 | 0.341 |
| 16×16 | 12.57 | 7.12 | 0.324 |

4×4 is the smallest supported resolution, because 2×2 texels are so large that the LTC integration hits corner cases. With `α = 1/30`, a worst case in which Sponza's spotlights jump from one curtain to the other makes guiding briefly worse than plain path tracing until the probes adapt over tens of frames (Figs. 25-26).

### Limits and future work

- The cascades hold only visible surfaces, and with jitter and detail thinner than a cell, light leaks across cascade transitions. Caustics and other very local, directional light show the grid as edges in noise level, and LTC weighting fits very low roughness poorly. Moving geometry entering cells without history shows noisier patches, softened by seeding new probes from visited neighbours and by coarser cascades more often having history ([notes](../sources/2026_tauray_rcpg_path_guiding.md#limits-and-future-work-sec-9-10)).
- Only about 10% of the allocated memory is touched, so a sparse voxel octree or spatial hash grid would scale to larger worlds.
- Proposed: sharing traced rays across cascades; RGB storage as an FP32 copy for the moving average plus an RGBE copy for sampling; culling by distance queries on hardware ray-tracing structures; and computing each texel by cone or beam tracing in one sample, which would remove the temporal reuse but has no hardware support (sparse voxel octrees might serve).

### Tauray code

**Volume and layout** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#code-volume-and-layout)):

- One cube around the scene bounds at 1.01× the largest extent. Cascade `c` has `2^(L−c)` probes per axis, with `L = 7` by default (128³ probes at cascade 0).
- Octahedral directions, `(c0 << c)²` per probe with `c0 = 4`: 16, 64, 256, 1024 and 4096. Each cascade is a 2D array texture of `c0·2^L` squared (512²) with one layer per probe slice, and a probe's directions sit in one block. Each cascade holds half the texels of the one below: 33.6, 16.8, 8.4, 4.2 and 2.1 million, 65,011,712 in all (derived).
- Storage is luminance only (R32F) plus an R8 visibility: 65,011,712 texels at 5 bytes are 325 MB, or 310 MiB, so the paper's 310 MB and the code's 325 MB are the same figure, more with ping-pong copies (derived).
- Intervals derive from the probe spacing and an angle table: `t0(c) = l/sin(θ_c)` with `l = 2^(c−1)·E/2^L` and `θ = 1.5708, 0.7854, 0.3218, 0.1419, 0.0666, …`. Cascade 0 starts at zero so that a surface inside a probe's cell can see its own cell. The code doubles the computed length on purpose: too long makes probe resolution the limit, too short makes parallax the limit, and longer was faster and looked better. Cascades are added while `t0` is within the volume diagonal.

**Live probe culling** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#live-probe-culling)):

- The scene is voxelized every frame at `2^L` by conservative rasterization (dominant-axis projection in a geometry shader); each mip takes the maximum of its 8 children.
- A probe is live when the occupancy mip matching its cascade is occupied. Starting from every top-cascade probe, the children of live probes are tested cascade by cascade, and live probes are appended to one list, which feeds indirect dispatches of `ceil(live·dirs/64)` groups per cascade. Only live probes are traced and merged.
- A per-voxel history counter (occupied frames, capped at 65536) tells whether a probe has valid history.

**Trace** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#trace)):

- One invocation per texel of a live probe. A hardware ray query traces the segment `[t0(c), t0(c+1)]` with back-face culling; the last cascade ends at 10⁹ and alone receives environment light.
- A hit returns emission plus optional direct light (shadow maps, or light-tree samples with shadow rays) plus, when enabled, a recursive term that reads the cascades again at the hit point for multi-bounce. Back-face hits return black and opaque.
- Texel directions and probe origins are jittered per frame with R2 and R3 sequences ([R2](supporting_techniques.md#r2)), the same offset for all probes in a frame; the paper describes this as one `R_5` sequence.

**Merge and temporal reuse** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#merge-and-temporal-reuse)):

- The parent probe is simply `child/2`, with no spatial interpolation. Each texel takes the mean of its 4 child directions, gated by its own visibility: `dst += mean(r0..r3)·(1 − vis)`.
- The blend with the previous frame is `blend = max(1/(history + 1), 0.033)`. Probes with almost no history are filled from the average of their 6 face neighbours' previous values.
- An optional bias exponent blends in a power domain to lean toward the larger value, reducing underestimation and fireflies at the cost of noise.
- The path tracer reads `dst + 0.05·local_mean`, floored at 0.01, so no direction gets zero guiding probability.

**Guiding** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#guiding)). To sample a bounce, the path tracer starts at cascade 0, picks one 2×2 texel block by weighted reservoir sampling over radiance times the BSDF (diffuse and an LTC-fitted GGX lobe integrated over each quad), then descends into the chosen block's children at the next cascade, adjusting the weights by the accumulated transmittance. The final direction is uniform inside the chosen finest texel. The same structure gives the PDF for multiple importance sampling with next-event estimation.

**The `rcpg` branch** ([notes](../sources/2026_tauray_rcpg_path_guiding.md#the-rcpg-branch)):

- It shares the trace, merge and sampling code and adds texel sampling modes (uniform, BRDF and hybrid), a BRDF texel sampler, a visualizer, a path-guiding stub and a replication note listing the implementation files.
- Its `rcpg.cfg` sets grid size 7, `c0` 4, no recursion, uniform texel sampling, ray depth 3 and 19 samples, and leaves the temporal ratio at the stage default. Defaults disagree between layers: the command line has temporal ratio 0.033, recursion on and hybrid sampling, while the stage itself has 0.005, recursion off and uniform sampling.
- The interval code uses angle index `i = c + msb(c0) − 2`, `l = 2^(c−1)·E/2^L` and `t_max = l/(2·sin θ_i)`, then doubles `t_max`. The memory estimate counts 5 bytes per texel.
- Guided sampling is the only active sampler: next-event estimation is combined by MIS with the RC PDF, and a single-sample MIS alternative is compiled out. Without the bias exponent the merge takes `max(prev, dst)`.

### Derived points

- **Table 1 is the code's formula.** The intervals equal `t_n = l_n/sin θ_{n+1}` within 0.5%, with `l_n = 2^n·1.01·E/128` the cascade-`n` cell edge and `θ` from the angle table. In cell edges of their own cascade the intervals end at 1.41, 3.16, 7.07, 15.0 and 31.1; in cascade 0 cells at 1.4, 6.3, 28.3, 120 and 497. Cascade 0 reaches only about one and a half cells, and the ratio between successive bounds falls from 4.48 toward 4.13, approaching the `4^n` of the derivation ([notes](../sources/2026_tauray_rcpg_path_guiding.md#for-rc)).
- **Cascade 0's interval against the other rules.** Its end at 1.41 cells sits between the equal-error rule's 1.13 spacings for 16 directions and the diagonal rule's 1.73 ([choosing cascade 0](core_theory.md#choosing-cascade-0-derived-and-reported)); the undoubled conservative bound would be 0.71 cells, well below the diagonal. The diagonal rule protects interpolation between ray ends, which RCPG does not do, since its parent lookup is nearest-neighbour (inference).
- **Live probes and memory.** Live probes are 3.0 to 7.3% of all probes, but active memory is 4.5 to 12.9% of the allocation, about 200 to 280 bytes per live probe. Coarse probes hold more texels and are live more often, so memory concentrates in the upper cascades (inference, reading the active memory as live texels at 5 bytes).
- **Trace throughput.** Read that way, the live texels number 5.4 to 8.0 million indoors and 2.8 million in Rungholt, and the one-bounce trace handles 6.5 to 9.1 billion texels per second indoors and 1.7 billion in Rungholt, each texel one ray plus an optional light-tree shadow ray, on an RTX 3090 with ray queries (inference). That sits near Dell'Ova's 6.1 to 7.0 billion rays per second for screen-probe DXR on an RTX 3080 ([theses](3d_screen_space_theses.md)).
- **Build cost follows surface area.** Each doubling of the cascade 0 grid multiplies build time by 1.67, 2.4, 3.83 and 4.39, rising toward the 4× that surface area grows and far below the 8× of the volume; with culling, a dense address space costs what a sparse surface set costs (inference). Each 4× more cascade 0 texels multiplies it by 2.86 and 3.93, approaching linear.
- **The bound is a direction-fidelity criterion,** the angular counterpart of the penumbra condition: it asks when a texel can stand for its direction from anywhere in its cell, which is the question a 3D merge with spatial interpolation faces too. Standard RC's `2^n` intervals violate it and rely on diffuse integration to hide the error; any use that reads directions from the cascades (specular, guiding, directional shading) inherits that error (inference).
- **The one temporal dependency.** The method leans on temporal reuse in exactly one place, the moving average that turns one jittered ray per texel into a cell- and texel-integrated value, and the paper's own replacement is a cone or beam integral per texel in one sample (inference). At stationarity an exponential moving average with `α = 1/30` has the variance of `(2 − α)/α = 59` samples, so reaching the same noise in one frame by brute force means about 59 rays per texel, 37 to 58 ms of trace indoors on the RTX 3090 (derived). A single-frame 3D RC faces the same requirement and has to get the cell-and-cone integral from rays traced in that frame, through pre-averaging several rays per texel or a cone-traced representation ([cascade layout](cascade_layout_and_merging.md)) (inference).
- **Cost reference for world-space 3D RC with hardware ray queries.** Building 128³ with 4×4 texels and 5 cascades, one ray per live texel, costs 1.0 to 1.9 ms on an RTX 3090 for 71k to 176k live probes, 2.9 to 4.0 ms with voxelization, and 1.4 to 2.2 ms for recursive two-bounce cascades. Build time grows about 2.9× and 3.9× for each 4× more texels at cascade 0, and 4.4× from 128³ to 256³ (derived). RGB radiance for lighting instead of luminance would hold 41 to 61 MiB of live RGBA16F texels indoors, or half that in R11G11B10 (derived).
