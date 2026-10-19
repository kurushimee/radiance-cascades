# RCPG: radiance cascades for path guiding (tauray code)

| | |
|---|---|
| Authors | Julius Ikkala, Pekka Jääskeläinen, Markku Mäkitalo (Tampere University) |
| Date | 2026-10 (ACM Transactions on Graphics 46(2), 1-25, online 2026-10-09, DOI 10.1145/3840291; the Tampere group page lists it as 2027, the issue year) |
| Kind | Paper (open access, 25 pages) and its renderer code |
| Link | https://doi.org/10.1145/3840291, code https://github.com/vga-group/tauray (LGPL-2.1, `--renderer=rc` and `--renderer=rc-restir`) |

"RCPG: Real-Time Product Path Guiding Using Radiance Cascades" uses a world-space 3D RC volume as a guiding distribution for a path tracer, not as the final lighting. The code sections come from tauray's default branch; the README says the paper's exact version lives in a separate `rcpg` branch and that tauray is no longer developed. The branch's differences are at the end of this note. The volume, culling and temporal parts apply to RC for GI too.

The paper is open access on the ACM Digital Library (read from the full-text page; section, table and figure numbers are the paper's). Its claims: bounds on radiance intervals so the hierarchy does not misplace incoming directions; one sampler for the product of incoming radiance and the BSDF; a PDF that can be evaluated for any direction, so it combines with MIS and unbiased ReSTIR; and a world-space structure that serves off-screen path vertices, which multi-bounce guiding needs. Against earlier real-time guiding with multi-sample MIS it traces about twice the paths per pixel in a real-time frame.

## Contents

- [The paper](#the-paper)
  - [Cascades (sec. 3.1)](#cascades-sec-31)
  - [Parallax-based interval bounds (sec. 3.2)](#parallax-based-interval-bounds-sec-32)
  - [Probe mapping and culling (sec. 3.3-3.4)](#probe-mapping-and-culling-sec-33-34)
  - [Ray casting and gathering (sec. 3.5-3.6)](#ray-casting-and-gathering-sec-35-36)
  - [Sampling (sec. 4)](#sampling-sec-4)
  - [Implementation (sec. 5)](#implementation-sec-5)
  - [Evaluation (sec. 6-8)](#evaluation-sec-6-8)
  - [Limits and future work (sec. 9-10)](#limits-and-future-work-sec-9-10)
  - [For RC](#for-rc)
- [Code: volume and layout](#code-volume-and-layout)
- [Live probe culling](#live-probe-culling)
- [Trace](#trace)
- [Merge and temporal reuse](#merge-and-temporal-reuse)
- [Guiding](#guiding)
- [vlam (entropylost)](#vlam-entropylost)
- [The rcpg branch](#the-rcpg-branch)

## The paper

### Cascades (sec. 3.1)

- Every cascade is a power-of-two cube grid over the whole scene; each texel holds radiance and transparency. A step up halves probe density, doubles angular resolution per axis and moves the interval out, with each interval longer than the last.
- A cascade holds `M³N²` texels and the next `(M/2)³·(2N)² = M³N²/2`, so storage is `O(M_0³·N_0²)`, the same as one probe grid at cascade 0's resolution, and most texels belong to short intervals, which trace faster. At most `log₂ M_0` cascades exist; one whose `t_min > L·√3` (`L` the largest extent of the scene bounds) starts outside all geometry and is skipped.
- Spatial lookups are nearest-neighbour, so each probe has one parent. Each texel is integrated over its solid angle and its cell's volume by jittering ray origins in the cell and directions in the texel, averaged with an exponential moving average of `α = 1/30`. One deterministic ray per texel, as in the original paper, cannot represent detail below a minimum size.
- Unlike SD-trees, the structure never splits adaptively, which keeps GPU traversal free of divergence, and space and direction are coupled: short-range light at high spatial and low angular resolution, long-range light the reverse.

### Parallax-based interval bounds (sec. 3.2)

- Jittering origins over the cell low-pass filters the probe image: a point at distance `t` is smeared over the parallax angle under which the cell sees it. The bound uses the cell's inscribed circle (edge `l`), which is smaller than the cell from every direction and carries over to 3D as a sphere's equator: `θ_min = 2·arcsin(l/(2·t_max))`.
- Taking `θ_min` as the window width, the passband tops out at `f_max = 1/θ_min`, and Nyquist requires `f_max < f_s/2` for the probe's angular sampling rate `f_s`, precomputed by brute force from the longest angle across the largest texel. Then `t_max = l/(2·sin(1/f_s))`.
- With `l` and `f_s` doubling per cascade and `sin` nearly linear near zero, `t_max ∝ 4^i`. The penumbra condition of the original paper gives `t ∝ 2^i`; Osborne and Sannikov and the HRC paper use `4^i`. Power-of-two lengths let adjacent probes see parallax larger than a texel's angular radius, giving double images under linear interpolation or wasted resolution under jitter; diffuse lighting hides this, but the direction of incoming light is misrepresented, which rules them out for guiding.
- The conservative bound wastes probe resolution over most of the interval, so the measured configuration doubles it, `t'_max = l/sin(1/f_s)`, with `f_s` taken across the shortest edge of the smallest texel, switching from wasted resolution to lost detail near the middle of the interval. Using the conservative bound as `t_min` instead also works but samples slightly worse.

### Probe mapping and culling (sec. 3.3-3.4)

- Equal-area maps (Clarberg; Mortari et al. 2011) give uniform resolution per solid angle and a constant Jacobian, but sampling projects every corner of every texel it visits, so the octahedral map, with no transcendental functions, wins. Its Jacobian is `|J| = (1 + 2·min(1 − |x| − |y|, 0) − 2|x| − 2|y| + 2|xy| + 2x² + 2y²)^(−3/2)` for `x, y ∈ [−1, 1]`, computed once per sample.
- A 128³ cascade 0 with 16 texels per probe, two rays per texel (primary and shadow) and 5 cascades would need about 130 million rays. Probes whose cell overlaps no geometry are never used under nearest-neighbour lookup, so the scene is voxelized conservatively by rasterization at cascade 0's resolution, coarser levels mark a voxel occupied if any of its 2×2×2 children is, and empty cells are culled. A per-cell count of occupied frames lets returning geometry reuse old probe data. The culling is not core to the method.

### Ray casting and gathering (sec. 3.5-3.6)

- One ray per texel per frame, with origin and direction jittered by the `R_5` sequence (3 dimensions of position, 2 of direction), averaged over frames, which delays updates. Back faces are ignored so that jittered origins inside geometry still pass through and contribute.
- A hit is shaded with one light sample per frame from a light BVH; any light type works as long as the probe-update light sampler supports it (area lights, environment maps and spotlights are shown).
- Multiple bounces shade hits from the previous frame's gathered cascade 0, treating each texel as an area light evaluated with LTC; shading a 1280×720 image this way took about 0.5 ms, with colour lost and nearest-neighbour blocks obvious (Fig. 7). Errors there only add noise to guiding.
- Explicit point and directional lights are left out of the probes and to NEE, since texels are too coarse for small lights; RCPG is meant for indirect light and emissive meshes. With the sun inside the cascades, 8 spp leave shaded areas near sunlit edges slow to converge, worse than 4 spp with NEE at about equal ray counts (Fig. 8).
- Gathering runs from the highest cascade down: each texel takes the light of its 4 child texels in the next cascade, alpha-blended behind it by its coverage, so a texel holds all light from its direction, not only its interval's. A floor `L_avg·γ` with `γ = 0.05` (probe-wide average luminance at cascade 0, 2×2 neighbourhood above) keeps stochastic zeros from biasing sampling; larger `γ` means more noise but fewer outliers.

### Sampling (sec. 4)

- Texels are weighted as polygonal area lights through LTC, with irradiance `E = (1/2π)·Σ arccos(p_i·p_j)·((p_i × p_j)/|p_i × p_j|)·n` over vertices clipped to the upper hemisphere. The inverse matrix uses a 3-parameter fit, rows `(a, 0, b)`, `(0, 1, 0)`, `(0, 0, c)` with `a, b, c ∈ [0, 1]`: the lobe stays non-zero over the whole hemisphere, which keeps sampling unbiased, and points above the horizon stay above, so clipping can precede the transform and the diffuse and specular lobes share it. At grazing angles with low roughness the fit turns bimodal with a weak retro-reflective lobe.
- A sample descends the hierarchy: every texel of the cascade 0 probe containing the point is weighed and one is chosen by weighted random sampling, then one of the 4 texels it covers in the next cascade, and so on to the finest cascade. Weights use the separability approximation `∫L·ρ·cos dω ≈ ∫L dω · ∫ρ·cos dω`, with the stored luminance as the first factor and LTC with clamped vertices as an approximate horizon clip for the second, which underestimates grazing texels but cannot bias because the PDF uses the same weights.
- Inside the final texel the direction is uniform over its solid angle (used in all measurements; faster, but it can go below the horizon), or drawn by LTC polygon-light sampling (Peters 2021) with exact clipping, which never goes below the horizon and helps large texels with narrow lobes; in the ablation it was 25 % slower in path tracing for SSIM 0.0842 against 0.0837 (Fig. 22).

### Implementation (sec. 5)

- A baseline with 16 texels at cascade 0, four floats per texel, 5 cascades and linear spatial interpolation reads 4096 bytes per sample, about 475 GB/s at 1920×1080 and 60 Hz. RCPG stores luminance in R32F and visibility in R8 in separate textures, so one gather reads a 2×2 luminance footprint and visibility is read only for the chosen texel; half floats caused artifacts in the moving average. Nearest-neighbour lookups in space and direction cut bandwidth by 8× more, leaving visible edges in noise level that denoisers or ReSTIR hide. The total is about 15.4 GB/s.
- The arccos term is rewritten for a tangent-space normal as `Σ arccos(p_i·p_j)/(2π·|sin(arccos(p_i·p_j))|)·(p_ix·p_jy − p_iy·p_jx)`, and `arccos(d)/(2π·|sin(arccos d)|)` is approximated by `(−0.709693·d³ + 3.787823·d² + 20.448902·d + 15.951386)^(−1/2)`. Most sampling math runs in 16-bit floats for double-rate FMA.
- Bounces use RCPG samples alone, not MIS with BSDF samples: single-sample MIS raised noise at equal sample counts and frame time by 40 to 80 % through divergence. MIS with NEE or a light tree is recommended.

### Evaluation (sec. 6-8)

RTX 3090, 1920×1080, 1000 warm-up frames, GPU timings averaged over 250 frames, references at 262,144 spp; MAE in linear colour, PSNR, SSIM and FLIP after Reinhard tone mapping. Equal-time runs target 33.33 ms. RCPG uses 4×4 texels at cascade 0, a 128³ grid, uniform in-texel sampling and 5 cascades, 2,396,672 probes and 310 MB allocated in every scene. Scenes keep roughness above 0.05 and lose normal maps and transparency; explicit lights replace emissive surfaces because VXPG did not sample them, and NEE picks lights uniformly. ReSTIR GI is unbiased, one bounce, one temporal and one spatial neighbour, a 32-pixel radius and a history cap of 8. VXPG runs at 128³ (its default is 64³) with multi-sample MIS.

| Scene (Table 1) | Bounds size | Active probes | Active memory | `t_0` | `t_1` | `t_2` | `t_3` | `t_4` |
|---|---|---|---|---|---|---|---|---|
| Ajar | 11.30 × 4.80 × 9.20 | 127,067 | 31.7 MB | 0.126 | 0.564 | 2.521 | 10.72 | 44.24 |
| Breakfast | 11.62 × 9.32 × 14.43 | 99,447 | 27.4 MB | 0.161 | 0.720 | 3.221 | 13.69 | 56.51 |
| Classroom | 10.17 × 3.11 × 8.51 | 113,740 | 26.9 MB | 0.113 | 0.508 | 2.270 | 9.652 | 39.83 |
| Rungholt | 655 × 69 × 550 | 70,936 | 13.9 MB | 7.309 | 32.69 | 146.2 | 621.6 | 2565 |
| Staircase | 7.02 × 7.84 × 10.59 | 175,886 | 40.0 MB | 0.118 | 0.528 | 2.363 | 10.05 | 41.47 |
| Kitchen | 6.92 × 3.38 × 8.65 | 117,288 | 30.1 MB | 0.097 | 0.432 | 1.931 | 8.213 | 33.89 |

FLIP against the reference (lower is better), with spp for the equal-time runs and ms for the ReSTIR runs at 1 spp (Tables 2-7):

| Scene | 1 bounce: PT / SSPG / VXPG / RCPG | 2 bounces: PT / VXPG / RCPG | ReSTIR: PT / VXPG / RCPG |
|---|---|---|---|
| Ajar | 0.235 (37) / 0.186 (14) / 0.039 (13) / 0.094 (23) | 0.336 (22) / 0.127 (4) / 0.164 (11) | 0.155 (5.55) / 0.105 (15.16) / 0.083 (12.43) |
| Breakfast | 0.174 (28) / 0.158 (8) / 0.156 (7) / 0.112 (19) | 0.197 (16) / 0.277 (2) / 0.183 (9) | 0.156 (7.03) / 0.147 (32.32) / 0.116 (14.38) |
| Classroom | 0.215 (21) / 0.175 (7) / 0.226 (6) / 0.151 (16) | 0.261 (12) / 0.347 (2) / 0.223 (6) | 0.181 (8.55) / 0.183 (32.48) / 0.137 (17.92) |
| Rungholt | 0.144 (20) / 0.113 (5) / 0.212 (5) / 0.106 (13) | 0.169 (12) / 0.273 (2) / 0.133 (7) | 0.180 (11.73) / 0.213 (27.75) / 0.120 (22.80) |
| Staircase | 0.232 (29) / 0.171 (9) / 0.217 (8) / 0.132 (19) | 0.289 (17) / 0.343 (3) / 0.212 (8) | 0.173 (6.68) / 0.214 (23.66) / 0.116 (14.67) |
| Kitchen | 0.245 (27) / 0.261 (9) / 0.282 (7) / 0.216 (18) | 0.365 (15) / 0.414 (3) / 0.344 (8) | 0.299 (8.57) / 0.350 (18.11) / 0.282 (15.37) |

- VXPG wins Ajar, whose single rectangular slit fits voxels; RCPG leads Classroom, Rungholt and Staircase in every metric with 2 to 3 times the samples, and samples Breakfast's caustic best. In Kitchen, with metallic surfaces and occluded lights, unguided PT beats RCPG in PSNR and SSIM. With ReSTIR, RCPG is best by most metrics, but VXPG wins MAE in Ajar, Breakfast and Rungholt, plausibly from temporal flicker of its stochastic light injection.
- After one bounce, intersection points diverge between neighbouring pixels, and the scattered reads into the guiding structure slow both VXPG and RCPG: in Breakfast unguided PT manages twice RCPG's sample count at two bounces.
- Over the first 64 frames PT and VXPG are flat, RCPG stabilizes more slowly because of its moving average, and SSPG takes hundreds of frames, settling at MAE 0.158 in Staircase. RCPG's PDFs sit between SSPG and VXPG in detail and match the ground-truth magnitudes better than either (Fig. 15). Fireflies from small high-contribution regions make RCPG's MSE worse than PT's in Breakfast and Staircase; a single-sample MIS configuration with a plain average (9 to 12 spp) improves only MSE.

Per-pass cost at 1 spp, ms (Table 8):

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

4×4 is the smallest resolution supported, because 2×2 texels are so large that the LTC integration hits corner cases. With `α = 1/30`, a worst case where Sponza's spotlights jump from one curtain to the other makes guiding briefly worse than plain path tracing until the probes adapt over tens of frames (Figs. 25-26).

### Limits and future work (sec. 9-10)

- The cascades hold only visible surfaces, and with jitter and detail thinner than a cell, light leaks across cascade transitions. Caustics and other very local, directional light show the grid as edges in noise level; LTC weighting fits very low roughness poorly. Moving geometry entering cells without history shows noisier patches, softened by seeding new probes from visited neighbours and by coarser cascades more often having history.
- Only about 10 % of the allocated memory is touched, so a sparse voxel octree or spatial hash grid would scale to larger worlds. Proposed: sharing traced rays across cascades, RGB storage as an FP32 copy for the moving average plus an RGBE copy for sampling, culling by distance queries on hardware ray-tracing structures, and computing each texel by cone or beam tracing in one sample, which would remove the temporal reuse but has no hardware support (sparse voxel octrees might serve).

### For RC

- Table 1 equals `t_n = l_n/sin θ_{n+1}` within 0.5 %, with `l_n = 2^n·1.01·E/128` the cascade-`n` cell edge and `θ` from the code's angle table (derived by script). In cell edges of its own cascade the intervals end at 1.4, 3.2, 7.1, 15.0 and 31.1, and in cascade-0 cells at 1.4, 6.3, 28.3, 120 and 497: cascade 0 reaches only about one and a half cells, and the ratio between successive bounds falls from 4.48 toward 4.13, approaching the `4^n` of the derivation (derived).
- The bound is a direction-fidelity criterion, the angular counterpart of the penumbra condition: it asks when a texel can stand for its direction from anywhere in its cell, which is the question a 3D merge with spatial interpolation faces too. Standard RC's `2^n` intervals violate it and rely on diffuse integration to hide the error; any use that reads directions from the cascades (specular, guiding, directional shading) inherits the error (inference).
- The method leans on temporal reuse in exactly one place, the moving average that turns one jittered ray per texel into a cell- and texel-integrated value, and the paper's own replacement is a cone or beam integral per texel in one sample. A single-frame 3D RC faces the same requirement and has to get the cell-and-cone integral from rays traced in that frame, through pre-averaging several rays per texel or a cone-traced representation (inference).
- Cost reference for a world-space 3D RC with hardware ray queries: building 128³ with 4×4 texels and 5 cascades, one ray per live texel, costs 1.0 to 1.9 ms on an RTX 3090 for 71k to 176k live probes, 2.9 to 4.0 ms with voxelization, and 1.4 to 2.2 ms for recursive two-bounce cascades. Build time grows about 2.9× and 3.9× for each 4× more texels at cascade 0 and 4.4× from 128³ to 256³ (derived). The allocation, 65,011,712 texels at 5 bytes, is 325 MB or 310 MiB, so the 310 MB of the paper and the 325 MB of the code are the same figure (derived).

## Code: volume and layout

- One cube around the scene bounds (1.01× the largest extent). Cascade `c` has `2^(L−c)` probes per axis, with `L = 7` by default (128³ probes at cascade 0).
- Octahedral directions, `(c0 << c)²` per probe with `c0 = 4`: 16, 64, 256, 1024, 4096. Each cascade is a 2D array texture of `c0·2^L` squared (512²) with one layer per probe slice; a probe's directions sit in one block.
- Storage is luminance only (R32F) plus an R8 visibility, about 325 MB at the defaults (the paper's 310 MB in MiB), more with ping-pong copies.
- Intervals derive from the probe spacing and an angle table: `t0(c) = l/sin(θ_c)` with `l = 2^(c−1)·E/2^L` and `θ = 1.5708, 0.7854, 0.3218, 0.1419, 0.0666, …`. Cascade 0 starts at zero so a surface inside a probe's cell can see its own cell. The code doubles the computed length on purpose: too long makes probe resolution the limit, too short makes parallax the limit, and longer was faster and looked better. Cascades are added while `t0` is within the volume diagonal.

## Live probe culling

- The scene is voxelized every frame at `2^L` by conservative rasterization (dominant-axis projection in a geometry shader). Each mip takes the maximum of its 8 children.
- A probe is live when the occupancy mip matching its cascade is occupied. Starting from every top-cascade probe, the children of live probes are tested cascade by cascade, and live probes are appended to one list, which feeds indirect dispatches (`ceil(live·dirs/64)` groups per cascade). Only live probes are traced and merged.
- A per-voxel history counter (occupied frames, capped at 65536) tells whether a probe has valid history.

## Trace

- One invocation per texel of a live probe. A hardware ray query traces the segment `[t0(c), t0(c+1)]` with back-face culling; the last cascade ends at 10⁹ and alone receives environment light.
- A hit returns emission plus optional direct light (shadow maps, or light-tree samples with shadow rays) plus, when enabled, a recursive term that reads the cascades again at the hit point for multi-bounce. Back-face hits return black and opaque.
- Texel directions and probe origins are jittered per frame with R2 and R3 sequences, the same offset for all probes in a frame; the paper describes this as one `R_5` sequence.

## Merge and temporal reuse

- The parent probe is simply `child/2`, with no spatial interpolation. Each texel takes the mean of its 4 child directions, gated by its own visibility: `dst += mean(r0..r3)·(1 − vis)`.
- Blend with the previous frame: `blend = max(1/(history + 1), 0.033)`. Probes with almost no history are filled from the average of their 6 face neighbors' previous values.
- An optional bias exponent blends in a power domain to lean toward the larger value, reducing underestimation and fireflies at the cost of noise.
- The value read by the path tracer is `dst + 0.05·local_mean`, floored at 0.01, so no direction gets zero guiding probability.

## Guiding

To sample a bounce, the path tracer starts at cascade 0, picks one 2×2 texel block by weighted reservoir sampling over radiance times the BSDF (diffuse and an LTC-fitted GGX lobe integrated over each quad), then descends into the chosen block's children at the next cascade, adjusting the weights by the accumulated transmittance. The final direction is uniform inside the chosen finest texel. The same structure gives the PDF for multiple importance sampling with next-event estimation.

## vlam (entropylost)

https://github.com/entropylost/vlam (2025-04, no license) is a 2D experiment in the same direction: a path tracer through refracting circles that picks its direction by descending six cascades of stored luminance (4 to 4096 angle bins), choosing one of 4 children at each level in proportion to the stored values, and depositing each path segment's radiance back into the matching cascade. There is no merge pass and, despite the repository description, no light sampling.

## The rcpg branch

- The branch shares the trace, merge and sampling code and adds texel sampling modes (uniform, BRDF and hybrid), a BRDF texel sampler, a visualizer, a path-guiding stub and a replication note listing the implementation files.
- Its `rcpg.cfg` sets grid size 7, `c0` 4, no recursion, uniform texel sampling, ray depth 3 and 19 samples, and leaves the temporal ratio at the stage default. Defaults disagree between layers: the command line has temporal ratio 0.033, recursion on and hybrid sampling, while the stage itself has 0.005, recursion off and uniform sampling.
- The interval code uses angle index `i = c + msb(c0) − 2`, `l = 2^(c−1)·E/2^L` and `t_max = l/(2·sin θ_i)`, then doubles `t_max`. The memory estimate counts 5 bytes per texel (R32F luminance plus R8 visibility).
- Guided sampling is the only active sampler: next-event estimation is combined by MIS with the RC PDF, and a single-sample MIS alternative is compiled out. Without the bias exponent the merge takes `max(prev, dst)`.
