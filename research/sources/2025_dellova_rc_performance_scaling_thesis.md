# Analyzing the Performance Scaling of Radiance Cascades: Exploring a Novel Solution for Dynamic Diffuse Real-Time Global Illumination

| | |
|---|---|
| Author | Jonathan Dell'Ova |
| Date | 2025 (Blekinge Institute of Technology; the cover reads "10 2025") |
| Kind | thesis |
| Link | https://bth.diva-portal.org/smash/get/diva2:2007296/FULLTEXT01 |
| Code | https://github.com/ClaikoCode/DX12RadianceCascades (its README links this thesis); see [2026_screen_space_probe_repositories.md](2026_screen_space_probe_repositories.md) |

Master's thesis (MSc in Engineering, Game and Software Engineering) at Blekinge Institute of Technology, 84 PDF pages. It describes a from-scratch 3D radiance cascades (RC) implementation in DirectX 12 that uses hardware ray tracing, and measures frame time and VRAM for 48 parameter sets at 1920x1080 and 2560x1440 in the Sponza scene. It covers the RC algorithm as implemented, the automated test setup, the scaling results, and the study's limits.

The PDF text layer is partly garbled in math and figure labels. Equations 4.4 and 4.5 lost their superscripts in extraction; they are rebuilt here from the surrounding text and from the thesis's own numbers (Table 5.4). Items marked "Derived" are arithmetic on the thesis's equations or tables, not statements in the thesis.

## Contents

- [Abstract (p. i)](#abstract-p-i)
- [1 Introduction (pp. 1-4)](#1-introduction-pp-1-4)
  - [1.1 Gaps in existing work](#11-gaps-in-existing-work)
  - [1.2 Aim and objectives](#12-aim-and-objectives)
  - [1.3 Delimitations](#13-delimitations)
  - [1.4 Research question](#14-research-question)
  - [2.4 Radiance cascades](#24-radiance-cascades)
  - [3.3 Radiance cascade research](#33-radiance-cascade-research)
    - [3.3.1 Radiance cascades for radiative transfer](#331-radiance-cascades-for-radiative-transfer)
    - [3.3.2 Radiance cascades in 2D](#332-radiance-cascades-in-2d)
    - [3.3.3 Radiance cascades in 3D](#333-radiance-cascades-in-3d)
- [4 Method (pp. 15-31)](#4-method-pp-15-31)
  - [4.1 Implementation](#41-implementation)
    - [4.1.1 Radiance cascade implementation](#411-radiance-cascade-implementation)
    - [4.1.2 Probe count (eq 4.1)](#412-probe-count-eq-41)
    - [4.1.3 Cascade count (eq 4.2)](#413-cascade-count-eq-42)
    - [4.1.4 Cascade texture size and layout (eqs 4.3 to 4.6)](#414-cascade-texture-size-and-layout-eqs-43-to-46)
    - [4.1.5 Valid ray counts (eq 4.7)](#415-valid-ray-counts-eq-47)
    - [4.1.6 Coalesced result](#416-coalesced-result)
  - [4.2 Execution pipeline (pp. 19-24)](#42-execution-pipeline-pp-19-24)
    - [4.2.1 G-buffer and depth pass](#421-g-buffer-and-depth-pass)
    - [4.2.2 RC gather pass](#422-rc-gather-pass)
    - [4.2.3 RC merge pass](#423-rc-merge-pass)
    - [4.2.4 RC coalesce pass](#424-rc-coalesce-pass)
    - [4.2.5 Deferred lighting pass](#425-deferred-lighting-pass)
  - [4.3 Testing setup (pp. 24-29)](#43-testing-setup-pp-24-29)
  - [4.4 Tools and apparatus (pp. 29-31)](#44-tools-and-apparatus-pp-29-31)
- [5 Results and analysis (pp. 33-44)](#5-results-and-analysis-pp-33-44)
  - [5.1 Frame time measurement consistency](#51-frame-time-measurement-consistency)
  - [5.2 Full parameter space](#52-full-parameter-space)
  - [5.3 Resolution dependent scaling](#53-resolution-dependent-scaling)
  - [5.4 Ray count dependent scaling](#54-ray-count-dependent-scaling)
  - [5.5 Real-time feasibility of probe density](#55-real-time-feasibility-of-probe-density)
- [6 Discussion (pp. 45-50)](#6-discussion-pp-45-50)
  - [6.1 Parameter specific scaling characteristics](#61-parameter-specific-scaling-characteristics)
    - [6.1.1 Probe spacing impact](#611-probe-spacing-impact)
    - [6.1.2 Ray count impact](#612-ray-count-impact)
    - [6.1.3 Resolution impact](#613-resolution-impact)
    - [6.1.4 Cascade level impact](#614-cascade-level-impact)
  - [6.2 Configuration equivalencies](#62-configuration-equivalencies)
    - [6.2.1 Real-time feasibility](#621-real-time-feasibility)
  - [6.3 Validity threats](#63-validity-threats)
- [7 Conclusions and future work (pp. 51-52)](#7-conclusions-and-future-work-pp-51-52)
  - [7.1 Conclusions](#71-conclusions)
  - [7.2 Future work](#72-future-work)
- [Data tables](#data-tables)
- [Source inconsistencies and gaps](#source-inconsistencies-and-gaps)
- [Answers from the code](#answers-from-the-code)
- [Links found](#links-found)

## Abstract (p. i)

- RC is a deterministic technique for dynamic diffuse global illumination, created by Alexander Sannikov.
- The thesis asks how 3D RC frame time and VRAM scale with render resolution, probe spacing, cascade count, and initial rays per probe.
- Setup: DirectX 12, MSI RTX 3080 10GB, Sponza scene with about 262k triangles, 48 configurations per resolution, each measured 30 times.
- Pre-averaging is stated to cut RC VRAM by a factor of 4.
- 95% confidence intervals are within +/-0.04 ms of the mean for all configurations.
- Probe spacing has the strongest effect and scales super-linearly.
- Resolution scaling matches the pixel ratio. Ray count scales sub-linearly.
- The RC gather pass takes 87 to 96% of the measured time.
- At 1080p, 79.2% of configurations are below 33.33 ms and 62.5% below 16.67 ms (RC passes only).
- The abstract says probe spacing of 2 or greater looks promising for real-time use.
- Left for future work: visual evaluation, hardware counters, and deeper statistics.

## 1 Introduction (pp. 1-4)

### 1.1 Gaps in existing work

- Three academic texts on RC were found (Google Scholar, DiVA, Scopus): [7], [10], [28].
- Only Kung [10] covers 3D RC for real-time dynamic GI. That study varies one parameter and uses no hardware ray tracing.

### 1.2 Aim and objectives

- Aim: measure how RC performance scales across several key parameters with hardware ray tracing.
- O1: implement 3D RC with hardware ray tracing.
- O2: measure common performance metrics that depend on the key RC parameters, reliably.
- O3: analyze how the implementation scales across configurations.

### 1.3 Delimitations

- Diffuse GI only. Specular reflections are mentioned as possible in Sannikov's pre-print [32] but are not evaluated.
- No evaluation of the output image quality. The output was checked only for clear bugs.
- One scene only (Sponza).

### 1.4 Research question

- How does the real-time performance of a 3D RC implementation with hardware ray tracing scale in VRAM and frame time with respect to render resolution, probe spacing, cascade count, and initial ray count per probe?
- Frame time: total GPU time for specific work in the current frame, excluding CPU time.
- VRAM usage: GPU memory allocated for a specific resource or group of resources.

### 2.4 Radiance cascades

- RC is a probe-based dynamic GI technique first shown by Sannikov [31, 32]. It is the main GI solution in Path of Exile 2 [5].
- It is deterministic. It does not use stochastic sampling.
- It rests on the penumbra condition: to resolve emission from a distant object of a given size, a probe needs higher angular resolution but can accept lower spatial resolution. Nearby objects need higher spatial resolution and can accept lower angular resolution [32] (Figure 2.3).
- Angular resolution: density of sampling directions (smaller angle between neighbors means higher resolution).
- Spatial resolution: density of probes in world space.
- Probe spacing: uniform distance between probes. It is inversely proportional to spatial resolution.
- Cascade (also cascade interval or level): a grid of probes with a given spatial resolution, angular resolution, and distance interval.
- Each cascade has lower spatial resolution and higher angular resolution than the previous one.
- Each cascade's distance interval starts where the previous one ended (Figures 2.4 and 2.5).
- Probe scaling factor: how much the probe count drops per cascade, and how much probe spacing grows per cascade.
- Ray scaling factor: how much the ray count per probe grows per cascade. Section 2.4 also says it sets how much the ray length grows.
- Cascade scaling factor: the pair of the two above.
- Merge: radiance is combined across cascades by interpolation based on ray direction. Occlusion is accounted for at each step. The result keeps near-field spatial detail and far-field directional detail (Figure 2.6).
- Notation caveat: Section 2.4 gives "2x/4x" as an example meaning twice the rays and a quarter of the probes. The implementation (Section 4.1) uses 4x rays and a quarter of the probes per cascade. See the inconsistencies section.

### 3.3 Radiance cascade research

#### 3.3.1 Radiance cascades for radiative transfer

- Osborne and Sannikov [28] used RC for 2D solar radiative transfer, not rendering.
- Their computation times are several orders of magnitude above real-time rendering costs.
- They state the logic generalizes to 3D.
- They note some inconsistencies and optimizations left for later work.

#### 3.3.2 Radiance cascades in 2D

- Freeman et al. [7] (Sannikov is a co-author) introduced Holographic Radiance Cascades (HRC) for 2D grid-based GI.
- Render times on an RTX 3080 laptop GPU: 1.85 ms at 512x512 and 7.67 ms at 1024x1024.
- They claim the output is visually indistinguishable from a 2D reference, and that the method handles hard shadows.
- They also tried a 3D HRC. It has steep N^4 memory growth for an N x N x N scene, so it is feasible only for small volumes.

#### 3.3.3 Radiance cascades in 3D

- Kung [10] implemented 3D RC for the game Romestead and is the closest prior work.
- Kung uses screen-space ray marching with the deferred position and emission buffers. It does not use hardware ray tracing.
- Median render times (DirectX 11 timestamp queries) for three increasing scenes, sampling every 4th pixel (SPS 4): about 5, 20, and 30 ms.
- Sampling every pixel (SPS 1): 70, 196, and 294 ms.
- Kung used 6 cascades with branching factor 2 in both spatial and polar directions, which the thesis maps to a 4x/4x scaling factor.
- Render time falls by about 3x when sample spacing doubles.
- Kung does not measure VRAM. Kung varies only sample point spacing.
- Kung's work was published after this thesis's plan was set.

## 4 Method (pp. 15-31)

### 4.1 Implementation

- The RC code was written from scratch. There was no reference 3D implementation.
- 2D references: Max's blog [15] and the GM Shaders post by Xor and Alex [37] (co-authored by Sannikov).
- The thesis states that 2D intuition was essential to the 3D version.

#### 4.1.1 Radiance cascade implementation

- Probe spacing in cascade 0, in pixels (ps0).
- Rays per probe in cascade 0 (rc0).
- Render target width and height (w, h).
- Maximum allowed cascade count.
- Ray length per probe in cascade 0.
- Probe scaling factor (sp), applied per dimension. Set to 2.
- Ray scaling factor (sr). Set to 4.
- Resulting cascade scaling factor: 4x/4x. Each cascade has 4 times the rays per probe and a quarter of the total probes.

#### 4.1.2 Probe count (eq 4.1)

- pc0 = floor((w, h) / ps0), applied to each of width and height.
- pc0 = (pc0x, pc0y) is the cascade 0 probe count per axis. (w, h) is the target size in pixels. ps0 is the cascade 0 spacing.
- Figure 4.1 example: spacing 1 gives a probe count of 16, spacing 2 gives 4. The figure does not say whether these counts are per axis or total.

#### 4.1.3 Cascade count (eq 4.2)

- N = floor( log_sp( min(pc0x, pc0y) ) ), where sp is the probe scaling factor.
- N is the cascade count limit. The thesis caps it at the user's maximum allowed cascade count.
- The shortest axis limits N, because probes cannot be divided into whole counts past that point.
- Figure 4.2 (1D illustration, probe scaling 2): spacing 1 gives 3 levels, spacing 2 gives 2 levels. The figure gives no sizes, so eq 4.2 cannot be applied to it.
- Derived: at 1080p with sp = 2, spacing 4 gives min probe count 270 and N = 8. Spacing 5 gives 216 and N = 7. This matches the thesis's statement that spacing above 4 does not reach cascade 8 at 1080p.

#### 4.1.4 Cascade texture size and layout (eqs 4.3 to 4.6)

- Equation 4.3 (before pre-averaging): (wi, hi) = pci * sqrt(rci), with the cascade texture size in pixels.
- Equation 4.4: rci = rc0 * sr^i (ray count per probe at cascade i).
- Equation 4.5: pci = pc0 / sp^i (probe count per axis at cascade i). The thesis states this per dimension.
- Layout without pre-averaging: each cascade texture is a sqrt(rci) x sqrt(rci) grid of elements. Each element is pci_x by pci_y pixels.
- Each element holds the radiance of one ray direction for all probes at that cascade. Each pixel in an element is one probe (Figure 4.3, 4 rays).
- Pre-averaging, equation 4.6 (used by the implementation): (wi, hi) = pci * sqrt(rci / sr), with sr = 4.
- With pre-averaging, the element grid is sqrt(rci / 4) per side. Element size is still pci_x by pci_y pixels.
- Pre-averaging gathers 4 rays in one thread and stores their average. The merge step then needs 1 sample instead of 4, and VRAM is reduced by a factor of 4. The thesis reports no measured comparison without pre-averaging.

Derived from equations 4.4 to 4.6 (not stated in the thesis; Table 5.4 agrees):

- Every cascade texture has the same width and height: width = pc0x * sqrt(rc0) / 2, height = pc0y * sqrt(rc0) / 2.
- Probe counts are whole numbers. With integer division at each level (Table 5.4 uses floor), the high cascades come out slightly smaller in height.
- One reading of the layout index math: texel (X, Y) in cascade i is probe (X mod pci_x, Y mod pci_y) in direction block (floor(X / pci_x), floor(Y / pci_y)). The thesis does not give the exact linear index; the code uses this direction-first index (see [2026_screen_space_probe_repositories.md](2026_screen_space_probe_repositories.md)).

#### 4.1.5 Valid ray counts (eq 4.7)

- Requirement: sqrt(rci / sr) must be a whole number for all i.
- Result: rc0 must be 4k^2 for a whole number k (4, 16, 36, 64, 100, ...).
- Tested values: 16, 36, 64.
- 4 is excluded: with symmetric sphere directions, all four directions fall on one plane, so 3D coverage fails.
- 100 is excluded: frame time above 33 ms for most configurations.

#### 4.1.6 Coalesced result

- Final RC texture. Dimensions equal the cascade 0 probe counts (pc0x by pc0y).
- Each texel holds the merged radiance for one cascade 0 probe.

### 4.2 Execution pipeline (pp. 19-24)

The pipeline runs the passes below per frame, in order (Figure 4.4 shows example outputs).

| Pass | Dispatch granularity | Reads | Writes | Timed |
|---|---|---|---|---|
| G-buffer and depth | MiniEngine raster pass | Scene | Albedo G-buffer, depth buffer | No (4.2.1) |
| RC gather | One thread per cascade texel (4 rays), one dispatch per cascade | Depth buffer, camera matrices, scene (ray tracing), emissive textures | Cascade i texture (RGB radiance plus alpha) | Yes |
| RC merge | One thread per texel of cascade i-1, for i from top down | Cascade i and cascade i-1 alpha | Cascade i-1, in place (from the code) | Yes |
| RC coalesce | One thread per cascade 0 probe | All direction texels of cascade 0 | Coalesce buffer (pc0 size) | Yes |
| Deferred lighting | One thread per output pixel | Albedo G-buffer, coalesce buffer | Lit output | Yes (4.3.1) |

#### 4.2.1 G-buffer and depth pass

- Uses MiniEngine's rasterization API. Only the albedo buffer is used later.
- The depth buffer is used for probe positions.
- This pass is not in the performance results.

#### 4.2.2 RC gather pass

- One ray tracing dispatch per cascade. One thread per texel of the cascade buffer. Each texel covers 4 probe-direction pairs (pre-averaging).
- Per-thread steps:
  1. Compute the probe index, the base ray index, the probe spacing, and the distance interval from the 2D dispatch index.
  2. Ray directions: the four ray indices of a 2x2 block of the direction grid (from [0, sqrt(rci)] squared) are mapped to [-1, 1] squared. An equal-area mapping then gives the unit vector. The source uses the equal-area sphere mapping in Pharr et al. [30] and does not give its formula; the code's formula is in "Answers from the code" below.
  3. Probe placement: probe positions are laid out over the depth buffer using the cascade's spacing, offset by half the spacing in each dimension. World position is rebuilt from the depth value with the inverse projection and inverse view matrices. That position is the ray origin.
  4. Radiance sampling: the thread traces 4 rays. Each ray covers the cascade's distance interval.
     - On a hit, the emissive texture of the hit surface gives RGB radiance.
     - On a miss, radiance is black, except in the last cascade, which returns an analytic sky color for the ray direction. The thesis says this made no measurable performance difference. The code's latest commit samples an HDR skybox there instead (below).
     - Alpha: 1.0 for a miss, 0.0 for a hit.
  5. Average the 4 rays (RGB and alpha) together, whether they hit or missed. Write the result to the texel.
- The thesis does not give the distance interval formula per cascade; the code's is below.

#### 4.2.3 RC merge pass

- Merges all cascades into cascade 0, from the highest cascade down. This follows Sannikov's method for diffuse (irradiance) lighting [31].
- Each merge pair is cascade i and cascade i-1. One thread per texel of cascade i-1.
- Per-thread steps:
  1. Occlusion test: fetch the alpha of the lower cascade texel. If alpha is 0, all 4 pre-averaged rays hit a surface, and merging is skipped so no upper radiance passes through solid geometry.
  2. Directional averaging: each lower texel covers 4 rays, so 16 upper rays are merged into 4 lower rays. Four sets of neighboring upper directions are sampled and averaged. Pre-averaging means one sample per set instead of four.
  3. Spatial interpolation: bilinear sampling across the four nearest upper-cascade probes, so closer probes contribute more.
- Not given in the thesis: the blending weights, and what is kept when the merge is skipped. The code uses plain bilinear weights and keeps the lower value (below).

#### 4.2.4 RC coalesce pass

- One thread per cascade 0 probe.
- Each thread sums the radiance from all directions of that probe into one irradiance value, and writes it to the coalesce buffer.
- The thesis says "summing". The normalization is not stated; the code divides by the direction count, a plain average.

#### 4.2.5 Deferred lighting pass

- For each output pixel, the irradiance is a bilinear sample of the coalesce buffer at the pixel's screen position.
- Cascade 0 probes sit on surfaces. Rays into surfaces carry no radiance because of the merge occlusion test. The result approximates light from the outward hemisphere.
- Simplified diffuse term used: fr = 1.0 * albedo, and the cosine term (wi . n) is set to 1.0.
- Result: outgoing diffuse = albedo * (coalesced irradiance). The thesis writes "albedo * integral of Li dwi", and approximates it with the coalesce value.
- No 1/pi factor appears anywhere in the derivation, and none appears in the code.

### 4.3 Testing setup (pp. 24-29)

**Scene**

- Sponza model from the MiniEngine demo, about 262k triangles.
- Chosen for common use in GI research [10, 12, 14, 16, 36].
- A floating sphere of about 31k triangles acts as the dynamic emitter. It oscillates between the far sides of Sponza.
- Sponza is scaled by 100 so MiniEngine's default camera speed is usable. The bounding sphere radius becomes 2590 units.
- Ray length: 5.0 for all tests, chosen by hand for a cohesive diffuse look. The ray length does not affect RC resource creation. Output is the same if the scene and ray length are scaled together.
- Figure 4.6 example: 1440p, 64 rays, ray length 5.0, 8 cascades, spacing 1.

**Test parameters**

- Target resolutions: 1920x1080 and 2560x1440. Both use the same parameter ranges.
- Probe spacing: 1, 2, 3, 4.
- Max allowed cascades: 5, 6, 7, 8.
- Rays per probe in cascade 0: 16, 36, 64.
- Frames averaged per test: 64. Frame count is used instead of time so each test gets the same sample count.
- Configurations per resolution: 4 x 4 x 3 = 48.
- Repetitions: 30 full runs per resolution, based on a rule of thumb from the central limit theorem [11]. The analysis treats each stored value (a 64-frame mean) as one sample.
- Why spacing stops at 4: at 1080p, spacing above 4 does not reach cascade 8 (see 4.1.3).
- Why cascades start at 5: the thesis calls 5 to 6 the minimum for full radiance capture. For the tested camera angle, cascade levels had no meaningful visual effect (Section 5 introduction).
- Why rays stop at 64: 4 is excluded (see 4.1.5). The next valid value, 100, costs more than 33 ms for most configurations.
- Total frame time = sum of the RC pass times (the thesis calls it "summed frame time of RC passes").
- The G-buffer pass is excluded.

### 4.4 Tools and apparatus (pp. 29-31)

- GPU: MSI GeForce RTX 3080 SUPRIM X 10GB, driver 580.88 (Jul 31, 2025).

## 5 Results and analysis (pp. 33-44)

- Figures 5.1 and 5.2 show Sponza at 2048x2048 with probe spacing 1 to 4 (rays 36), and rays 16, 36, 64 (spacing 2). Image quality is not evaluated.
- Full data are in the "Data tables" section at the end of these notes.

### 5.1 Frame time measurement consistency

- Standard deviation of the mean over 30 runs: 1080p 0.005 to 0.056 ms; 1440p 0.006 to 0.104 ms.
- 95% CI half-width: within +/-0.0210 ms at 1080p; within +/-0.0385 ms at 1440p (see gaps on the 1440p figure).
- Mean frame times range from under 2 ms (R16-S4-C5 at 1080p) to over 240 ms (R64-S1-C8 at 1440p).
- Table 5.1 (1080p) and Table 5.2 (1440p) in the thesis are the same numbers at 3 decimals. The full 5-decimal data are in Data table D1.

### 5.2 Full parameter space

- Probe spacing has the biggest effect on both VRAM and frame time. Spacing 1 dominates the plot.
- VRAM and frame time both rise linearly with the cascade count. The step between cascade levels grows with ray count.
- Spacing 1 costs the most VRAM at every ray count, at both resolutions (Table 5.3).
- The RC gather share of frame time rises with ray count (Table 5.3).
- Cascade levels 5 to 7 show the same two patterns (Appendix tables A.3 to A.5; data table D2).

Table 5.3 (max cascades 8). Frame time is the total RC time. RC Gather % is gather's share of it.

| Resolution | Spacing | Rays | VRAM MB | Total frame time (ms) | RC Gather % |
|---|---|---|---|---|---|
| 1080p | 4 | 16 | 34 | 2.36 | 87.0 |
| 1080p | 4 | 36 | 72 | 4.97 | 91.3 |
| 1080p | 4 | 64 | 125 | 8.59 | 93.1 |
| 1080p | 3 | 16 | 58 | 3.95 | 90.3 |
| 1080p | 3 | 36 | 129 | 8.55 | 93.0 |
| 1080p | 3 | 64 | 222 | 14.96 | 94.2 |
| 1080p | 2 | 16 | 133 | 8.66 | 93.2 |
| 1080p | 2 | 36 | 286 | 19.16 | 94.5 |
| 1080p | 2 | 64 | 499 | 33.81 | 95.0 |
| 1080p | 1 | 16 | 519 | 34.04 | 95.1 |
| 1080p | 1 | 36 | 1159 | 76.19 | 95.5 |
| 1080p | 1 | 64 | 2019 | 134.82 | 95.7 |
| 1440p | 4 | 16 | 58 | 4.04 | 89.8 |
| 1440p | 4 | 36 | 129 | 8.66 | 92.8 |
| 1440p | 4 | 64 | 222 | 15.16 | 94.0 |
| 1440p | 3 | 16 | 103 | 6.86 | 92.1 |
| 1440p | 3 | 36 | 229 | 15.01 | 93.9 |
| 1440p | 3 | 64 | 383 | 26.45 | 94.7 |
| 1440p | 2 | 16 | 238 | 15.36 | 94.1 |
| 1440p | 2 | 36 | 510 | 34.19 | 94.9 |
| 1440p | 2 | 64 | 902 | 60.37 | 95.3 |
| 1440p | 1 | 16 | 940 | 60.77 | 95.3 |
| 1440p | 1 | 36 | 2055 | 136.19 | 95.6 |
| 1440p | 1 | 64 | 3610 | 241.56 | 95.8 |

- The thesis gives a 87 to 96% gather share range across all configurations.

### 5.3 Resolution dependent scaling

- Pixel ratio 2560x1440 / 1920x1080 = 1.78 (1.7778).
- Frame time scale factor (1440p / 1080p): 1.59 to 1.79. Minimum at R16-S4-C5.
- VRAM scale factor: 1.67 to 1.81 (as stated; the VRAM values are integer MB, so the exact ratios cannot be recomputed).
- Most configurations cluster near 1.78. Both minima (frame time and VRAM) belong to R16-S4-C5. The thesis does not name the maxima.
- R64-S3 and R36-S1 show a linear pattern with cascade count. The thesis says other sets do not.
- Derived check: the frame-time ratios computed from the 5-decimal data give 1.588 (minimum) to 1.792 (maximum) across all 48 configurations.

Table 5.4 (max cascades 5, 1080p): two configurations with the same cost but different layouts.

| Cascade | Buffer (R16-S1) | Buffer (R64-S2) | Probe count (R16-S1) | Probe count (R64-S2) | Rays (R16-S1) | Rays (R64-S2) |
|---|---|---|---|---|---|---|
| 0 | 3840x2160 | 3840x2160 | 1920x1080 | 960x540 | 16 | 64 |
| 1 | 3840x2160 | 3840x2160 | 960x540 | 480x270 | 64 | 256 |
| 2 | 3840x2160 | 3840x2160 | 480x270 | 240x135 | 256 | 1024 |
| 3 | 3840x2160 | 3840x2144 | 240x135 | 120x67 | 1024 | 4096 |
| 4 | 3840x2144 | 3840x2112 | 120x67 | 60x33 | 4096 | 16384 |

- VRAM usage: 335.6 MB (R16-S1) vs 323.4 MB (R64-S2).
- Total frame time: 24.74 ms vs 24.78 ms (mean over 30 runs).
- The buffer sizes match equations 4.5 and 4.6 with integer probe counts (derived check).

### 5.4 Ray count dependent scaling

- Reference scale factors for a ray increase: 36/16 = 2.25 and 64/16 = 4.0.
- Figure 5.5 bar values are not in the text. The table below is computed from the 5-decimal data (Tables A.1 and A.2). Derived.

| Spacing | Cascades | 1080p 16 to 36 | 1080p 16 to 64 | 1440p 16 to 36 | 1440p 16 to 64 |
|---|---|---|---|---|---|
| 4 | 5 | 1.94 | 3.33 | 2.12 | 3.70 |
| 4 | 6 | 2.06 | 3.54 | 2.14 | 3.72 |
| 4 | 7 | 2.09 | 3.61 | 2.14 | 3.75 |
| 4 | 8 | 2.10 | 3.64 | 2.15 | 3.76 |
| 3 | 5 | 2.15 | 3.74 | 2.18 | 3.82 |
| 3 | 6 | 2.15 | 3.76 | 2.18 | 3.83 |
| 3 | 7 | 2.16 | 3.78 | 2.18 | 3.85 |
| 3 | 8 | 2.16 | 3.79 | 2.19 | 3.85 |
| 2 | 5 | 2.20 | 3.88 | 2.22 | 3.91 |
| 2 | 6 | 2.21 | 3.89 | 2.22 | 3.92 |
| 2 | 7 | 2.21 | 3.90 | 2.22 | 3.93 |
| 2 | 8 | 2.21 | 3.90 | 2.23 | 3.93 |
| 1 | 5 | 2.24 | 3.95 | 2.24 | 3.97 |
| 1 | 6 | 2.24 | 3.96 | 2.24 | 3.97 |
| 1 | 7 | 2.24 | 3.96 | 2.24 | 3.97 |
| 1 | 8 | 2.24 | 3.96 | 2.24 | 3.97 |

- The thesis says the scale factors sit below the theoretical 2.25 and 4.0 in most sets.
- Spacing 1 is closest to the reference values. Spacing 4 is furthest below.
- Sub-linear scaling is attributed to cache effects, not to pre-averaging (see 6.1.2).

### 5.5 Real-time feasibility of probe density

- Figure 5.6 plots frame time on a log scale against probe spacing, for 30, 60, and 120 FPS lines.
- The three ray-count groups form three bands, each with a predictable scaling. The thesis suggests this could drive a quality preset.
- At 1080p, spacing 1 with 36 or 64 rays lands above 30 FPS.
- At 1080p, R64-S2-C8 (33.81 ms) and R16-S1-C8 (34.04 ms) are just above 33.33 ms. The thesis calls them "at the 30 FPS line".
- At 1080p, all configurations except R64-S4-C8 reach 120 FPS (8.33 ms).
- At 1440p, no spacing 1 configuration is below 33 ms. The lowest is 43.86 ms (R16-S1-C5).

Table 5.5 (share of the 48 configurations below each threshold):

| Resolution | 30 FPS (< 33.33 ms) | 60 FPS (< 16.67 ms) | 120 FPS (< 8.33 ms) |
|---|---|---|---|
| 1080p | 79.2% | 62.5% | 43.8% |
| 1440p | 64.6% | 50.0% | 22.9% |

- Derived check: counting rows of Table 5.2 gives 31 of 48 below 33.33 ms at 1440p (64.6%). Section 6.2.1 gives 64.4%, which is a typo.
- Derived check: 1080p counts are 38, 30, and 21 of 48, which match the table.

## 6 Discussion (pp. 45-50)

### 6.1 Parameter specific scaling characteristics

#### 6.1.1 Probe spacing impact

- Probe spacing has the largest effect on frame time and VRAM.
- Probe count should scale with the inverse square of spacing (the thesis cites equation 4.5). Spacing changes both width and height.
- Kung [10] also found spacing dominant. Kung calls the parameter sample point spacing (SPS).
- Dense probes are closer to the theory. One explanation offered: memory bandwidth limits at high load, with more memory stalls (citing Vasiou et al. [35]). This is a hypothesis; hardware counters were not measured. Vasiou et al. find, in a simulator, that memory stalls and DRAM traffic follow ray incoherence rather than raw bandwidth ([notes](2018_vasiou_ray_tracing_performance.md)).

#### 6.1.2 Ray count impact

- Scale factors for 16 to 36 and 16 to 64 are consistently below the theoretical 2.25 and 4.0.
- The thesis reads this as a predictable upper bound: scaling is at least as efficient as the theory.
- Likely cause, per the thesis: cache use. Cheaper configurations benefit more from cache speed-ups. Spacing 4 scales best with ray count.
- Pre-averaging is ruled out as the cause. It cuts VRAM by 4, but ray tracing stays close to or above 90% of RC pipeline time.

#### 6.1.3 Resolution impact

- Frame time scales near-linearly with pixel count for most configurations, from 1.59 to 1.79 (pixel ratio 1.78).
- Cause, per the thesis: a larger target size means a larger cascade 0 probe count by the same factor, so every level's probe count scales with it.
- The R16-S4 set is the lowest (1.59), which the thesis links to the same low-cost pattern.
- Some configurations show irregular scaling. The thesis gives no firm cause.

#### 6.1.4 Cascade level impact

- Each cascade adds a fixed amount of work and VRAM, so the growth is linear.
- With ray length 5.0 and this scene's size, cascades 7 and 8 start outside the scene radius of 2590 units. Their rays only miss.
- A miss still counts as a valid result (black), and the later passes do not treat it differently.
- The thesis suggests the hardware may skip rays that start outside the scene, but this was not tested. Including cascades 7 and 8 did not change the observed scaling.
- A shorter ray or a larger scene could change this, which the thesis flags as a risk.

### 6.2 Configuration equivalencies

- R16-S1 and R64-S2 have nearly the same frame time (24.74 ms and 24.78 ms; CIs do not overlap, the gap is about 0.04 ms).
- Reason: the spacing-1 set has 4 times the spatial resolution (2x per axis) and a quarter of the angular resolution of the spacing-2 set. The total rays per cascade match.
- VRAM differs because of integer rounding in probe counts, and the coalesce buffer size (1920x1080 vs 960x540 probes at 1080p).
- Other sets with similar cost: R64-S4, R36-S3, R16-S2. The thesis states that configurations with the same value of rc0 / sp^2 produce similar cost (sp = probe spacing, rc0 = rays per probe).
- The thesis suggests developers can choose between spatial and angular density with similar cost.

#### 6.2.1 Real-time feasibility

- 79.2% of 1080p configurations are below 33.33 ms, and 64.4% at 1440p (the text; Table 5.5 says 64.6%).
- Figures are for RC passes only. Shadows, post-processing, and other passes need the remaining budget.
- Spacing 1 gives no 1440p configuration under 33 ms. At 1080p, spacing 1 with 36 or more rays is above 30 FPS.

### 6.3 Validity threats

- The results are averaged over 30 runs. Parameter interactions were not analyzed; each parameter was analyzed on its own.
- One GPU (RTX 3080). Other architectures, especially other ray tracing hardware, may scale differently.
- Stable clock speeds were forced. Real GPUs change clocks with heat and power, so real measurements would be less consistent.
- One scene (Sponza). Its geometry and surface types may not generalize.
- No hardware counters were used (cache hit rate, memory bandwidth, RT core occupancy). The memory-bandwidth and cache explanations are speculation.

## 7 Conclusions and future work (pp. 51-52)

### 7.1 Conclusions

- Probe spacing has the largest effect on frame time and VRAM, with super-linear scaling. Some tested configurations exceed real-time limits.
- Resolution scaling is near the pixel ratio for heavy configurations, and deviates for light ones.
- Ray count scaling is sub-linear. Extra factors (not identified) affect efficiency.
- Cascade count scales VRAM and frame time linearly.
- 79.2% of tested 1080p configurations meet 33.33 ms for RC passes only. Standard deviations are below 0.06 ms at 1080p.
- The gather pass is 87 to 96% of frame time, so ray tracing dominates.
- The thesis claims this is the first systematic multi-parameter scaling analysis of 3D RC with hardware ray tracing.
- The conclusion says configurations with probe spacing 2 or greater "consistently achieved over 60+ FPS at 1080p". This conflicts with the data (see the inconsistencies section).

### 7.2 Future work

- Hardware-level counters: cache behavior, memory bandwidth, RT core occupancy. These would turn correlation into cause.
- Visual quality across parameter sets, and quality/performance trade-offs.
- Comparison with other real-time GI techniques.
- More scenes: outdoor scenes where far-field probes matter, interiors with small objects where near probes matter.
- Specular lighting with RC, using scenes other than Sponza.

## Data tables

Table D2: VRAM and frame time per cascade count (Tables A.3 to A.5, and Table 5.3 for 8 cascades). RC Gather % is gather's share of total RC time.

| Res | Spacing | Rays | Cascades | VRAM (MB) | Total frame time (ms) | RC Gather % |
|---|---|---|---|---|---|---|
| 1080p | 4 | 16 | 8 | 34 | 2.36 | 87.0 |
| 1080p | 4 | 36 | 8 | 72 | 4.97 | 91.3 |
| 1080p | 4 | 64 | 8 | 125 | 8.59 | 93.1 |
| 1080p | 3 | 16 | 8 | 58 | 3.95 | 90.3 |
| 1080p | 3 | 36 | 8 | 129 | 8.55 | 93.0 |
| 1080p | 3 | 64 | 8 | 222 | 14.96 | 94.2 |
| 1080p | 2 | 16 | 8 | 133 | 8.66 | 93.2 |
| 1080p | 2 | 36 | 8 | 286 | 19.16 | 94.5 |
| 1080p | 2 | 64 | 8 | 499 | 33.81 | 95.0 |
| 1080p | 1 | 16 | 8 | 519 | 34.04 | 95.1 |
| 1080p | 1 | 36 | 8 | 1159 | 76.19 | 95.5 |
| 1080p | 1 | 64 | 8 | 2019 | 134.82 | 95.7 |
| 1440p | 4 | 16 | 8 | 58 | 4.04 | 89.8 |
| 1440p | 4 | 36 | 8 | 129 | 8.66 | 92.8 |
| 1440p | 4 | 64 | 8 | 222 | 15.16 | 94.0 |
| 1440p | 3 | 16 | 8 | 103 | 6.86 | 92.1 |
| 1440p | 3 | 36 | 8 | 229 | 15.01 | 93.9 |
| 1440p | 3 | 64 | 8 | 383 | 26.45 | 94.7 |
| 1440p | 2 | 16 | 8 | 238 | 15.36 | 94.1 |
| 1440p | 2 | 36 | 8 | 510 | 34.19 | 94.9 |
| 1440p | 2 | 64 | 8 | 902 | 60.37 | 95.3 |
| 1440p | 1 | 16 | 8 | 940 | 60.77 | 95.3 |
| 1440p | 1 | 36 | 8 | 2055 | 136.19 | 95.6 |
| 1440p | 1 | 64 | 8 | 3610 | 241.56 | 95.8 |
| 1080p | 4 | 16 | 5 | 24 | 1.94 | 88.2 |
| 1080p | 4 | 36 | 5 | 49 | 3.76 | 91.8 |
| 1080p | 4 | 64 | 5 | 84 | 6.45 | 93.8 |
| 1080p | 3 | 16 | 5 | 39 | 3.00 | 90.8 |
| 1080p | 3 | 36 | 5 | 86 | 6.43 | 93.6 |
| 1080p | 3 | 64 | 5 | 149 | 11.21 | 94.8 |
| 1080p | 2 | 16 | 5 | 89 | 6.39 | 93.7 |
| 1080p | 2 | 36 | 5 | 188 | 14.08 | 95.1 |
| 1080p | 2 | 64 | 5 | 323 | 24.78 | 95.7 |
| 1080p | 1 | 16 | 5 | 336 | 24.74 | 95.6 |
| 1080p | 1 | 36 | 5 | 748 | 55.31 | 96.1 |
| 1080p | 1 | 64 | 5 | 1292 | 97.77 | 96.4 |
| 1440p | 4 | 16 | 5 | 39 | 3.08 | 90.1 |
| 1440p | 4 | 36 | 5 | 86 | 6.55 | 93.3 |
| 1440p | 4 | 64 | 5 | 149 | 11.40 | 94.7 |
| 1440p | 3 | 16 | 5 | 70 | 5.15 | 92.6 |
| 1440p | 3 | 36 | 5 | 153 | 11.23 | 94.6 |
| 1440p | 3 | 64 | 5 | 253 | 19.69 | 95.4 |
| 1440p | 2 | 16 | 5 | 158 | 11.26 | 94.6 |
| 1440p | 2 | 36 | 5 | 326 | 24.96 | 95.5 |
| 1440p | 2 | 64 | 5 | 582 | 44.03 | 96.0 |
| 1440p | 1 | 16 | 5 | 605 | 43.86 | 95.9 |
| 1440p | 1 | 36 | 5 | 1305 | 98.16 | 96.3 |
| 1440p | 1 | 64 | 5 | 2280 | 173.97 | 96.5 |
| 1080p | 4 | 16 | 6 | 27 | 2.04 | 87.6 |
| 1080p | 4 | 36 | 6 | 57 | 4.21 | 91.8 |
| 1080p | 4 | 64 | 6 | 99 | 7.25 | 93.7 |
| 1080p | 3 | 16 | 6 | 47 | 3.36 | 90.8 |
| 1080p | 3 | 36 | 6 | 103 | 7.24 | 93.6 |
| 1080p | 3 | 64 | 6 | 177 | 12.64 | 94.8 |
| 1080p | 2 | 16 | 6 | 104 | 7.18 | 93.6 |
| 1080p | 2 | 36 | 6 | 221 | 15.83 | 95.0 |
| 1080p | 2 | 64 | 6 | 383 | 27.89 | 95.6 |
| 1080p | 1 | 16 | 6 | 399 | 27.94 | 95.6 |
| 1080p | 1 | 36 | 6 | 889 | 62.52 | 96.0 |
| 1080p | 1 | 64 | 6 | 1539 | 110.53 | 96.3 |
| 1440p | 4 | 16 | 6 | 47 | 3.45 | 90.2 |
| 1440p | 4 | 36 | 6 | 103 | 7.36 | 93.3 |
| 1440p | 4 | 64 | 6 | 177 | 12.83 | 94.6 |
| 1440p | 3 | 16 | 6 | 83 | 5.80 | 92.6 |
| 1440p | 3 | 36 | 6 | 182 | 12.66 | 94.5 |
| 1440p | 3 | 64 | 6 | 301 | 22.24 | 95.3 |
| 1440p | 2 | 16 | 6 | 185 | 12.68 | 94.6 |
| 1440p | 2 | 36 | 6 | 390 | 28.18 | 95.5 |
| 1440p | 2 | 64 | 6 | 692 | 49.71 | 95.9 |
| 1440p | 1 | 16 | 6 | 720 | 49.64 | 95.9 |
| 1440p | 1 | 36 | 6 | 1560 | 111.21 | 96.2 |
| 1440p | 1 | 64 | 6 | 2730 | 197.18 | 96.4 |
| 1080p | 4 | 16 | 7 | 31 | 2.21 | 87.3 |
| 1080p | 4 | 36 | 7 | 65 | 4.61 | 91.6 |
| 1080p | 4 | 64 | 7 | 113 | 7.97 | 93.4 |
| 1080p | 3 | 16 | 7 | 53 | 3.68 | 90.6 |
| 1080p | 3 | 36 | 7 | 118 | 7.96 | 93.3 |
| 1080p | 3 | 64 | 7 | 202 | 13.92 | 94.5 |
| 1080p | 2 | 16 | 7 | 119 | 7.94 | 93.4 |
| 1080p | 2 | 36 | 7 | 255 | 17.54 | 94.7 |
| 1080p | 2 | 64 | 7 | 443 | 30.95 | 95.3 |
| 1080p | 1 | 16 | 7 | 459 | 30.99 | 95.3 |
| 1080p | 1 | 36 | 7 | 1024 | 69.35 | 95.7 |
| 1080p | 1 | 64 | 7 | 1779 | 122.67 | 96.0 |
| 1440p | 4 | 16 | 7 | 53 | 3.77 | 90.0 |
| 1440p | 4 | 36 | 7 | 118 | 8.08 | 93.1 |
| 1440p | 4 | 64 | 7 | 202 | 14.11 | 94.3 |
| 1440p | 3 | 16 | 7 | 94 | 6.39 | 92.4 |
| 1440p | 3 | 36 | 7 | 209 | 13.96 | 94.2 |
| 1440p | 3 | 64 | 7 | 347 | 24.57 | 95.0 |
| 1440p | 2 | 16 | 7 | 212 | 14.08 | 94.3 |
| 1440p | 2 | 36 | 7 | 454 | 31.31 | 95.2 |
| 1440p | 2 | 64 | 7 | 802 | 55.27 | 95.6 |
| 1440p | 1 | 16 | 7 | 830 | 55.20 | 95.6 |
| 1440p | 1 | 36 | 7 | 1808 | 123.68 | 95.9 |
| 1440p | 1 | 64 | 7 | 3170 | 219.36 | 96.1 |

## Source inconsistencies and gaps

Inconsistencies found in the thesis:

1. Section 6.2.1 gives 64.4% of 1440p configurations below 33.33 ms. Table 5.5 gives 64.6%, and counting Table 5.2 gives 31 of 48 (64.6%).
2. Section 7.1 says spacing 2 or greater "consistently achieved over 60+ FPS at 1080p". Table 5.1 contradicts this. For example, R64-S2 is 24.78 to 33.81 ms (30 to 40 FPS), and R36-S2 at 7 and 8 cascades is 17.54 and 19.16 ms (not 60 FPS). Section 5.5 gives 62.5% at 1080p below 16.67 ms, so the blanket claim does not hold.
3. Section 5.1 gives the 1440p CI as within +/-0.0385 ms. The maximum half-width in Table A.2 is 0.0388 ms (R64-S1-C6, [197.14082, 197.21834]).
4. Section 5.5 calls R64-S2-C8 (33.81 ms) and R16-S1-C8 (34.04 ms) "at the 30 FPS line". Both are just above 33.33 ms.
5. Section 2.4 example "2x/4x" (2x rays) and Section 4.1 "4x/4x" (4x rays) use the same label for different ray scalings. The implementation uses 4x rays and 2x probe scaling per axis.
6. The time measurement section lists diffuse lighting among the timed passes. The results call the total "summed RC passes". Whether the lighting pass is in the totals is unclear.

Gaps (not stated in the thesis; the code answers all of them except the figure values and the measured comparison, in the next section):

- Texture formats and bit depths of the cascade, coalesce, and G-buffer textures.
- Thread group sizes for each dispatch.
- Exact distance interval formula per cascade, and the ray length formula per cascade.
- The equal-area mapping formula (the thesis cites Pharr et al. [30], section 3.8).
- Merge blending weights, and whether the merge writes in place.
- Sky color formula.
- Coalesce normalization, and any 1/pi factor.
- Floor rules for probe counts (Table 5.4 implies floor division at each level, but eq 4.5 does not show it).
- Figure 5.5 and Figure 5.6 values (only shown as images).
- How the sphere sampling directions are rotated or distributed per probe.
- The emissive texture format and sampling method.
- Any measured comparison with pre-averaging turned off.

## Answers from the code

From ClaikoCode/DX12RadianceCascades at commit 21024b5 (paths under `DX12RadianceCascades/`). The code is newer than the thesis, and two passes differ from the thesis text, as noted.

| Gap | Code |
|---|---|
| Formats | cascades and coalesce buffer `R16G16B16A16_FLOAT`, cleared to (0, 0, 0, 0) (`src/RadianceCascadeManager3d.cpp:11, 74-100`); gather-filter masks `R8_UNORM` per cascade with a `uint32` reduction buffer (:16, 84, 103); depth copy `R32_FLOAT` and Hi-Z `R32G32_FLOAT` (`src/RadianceCascades.cpp:249-252`); albedo in MiniEngine's HDR color format `R11G11B10_FLOAT`, normals `R16G16B16A16_FLOAT` with alpha as the emissive flag (`MiniEngine/Core/BufferManager.cpp:85, 113-114`) |
| Thread groups | merge and coalesce `[numthreads(8, 8, 1)]` over the texture with ceil division; ray generation is one DXR invocation per (probe, direction) texel (`RadianceCascades.cpp:1367-1372, 1425, 1563`) |
| Intervals | start `|rayLength0·(1 − r^c)/(1 − r)|` and length `rayLength0·r^c`, with `r = rayScalingFactor = 4` (commented "needs to be a perfect square") and `rayLength0 = 5`, so `[0, 5], [5, 25], [25, 105], …`; `TMin = start`, `TMax = start + length` (`Assets/shaders/RCCommon3D.hlsli:86-89, 143-144`, `RCRaytraceRT.hlsl:109-110`) |
| Equal-area map | `OctToFloat3EqualArea` (`RCCommon3D.hlsli:112-126`): `d = 1 − (|x| + |y|)`, `r = 1 − |d|`, `φ = ((|y| − |x|)/r + 1)·π/4`, `z = sign(d)·(1 − r²)`, and the horizontal part `sign·(cos φ, sin φ)·r·√(2 − r²)`: the Clarberg equal-area octahedral map ([notes](2008_clarberg_equal_area_sphere_mapping.md)). Directions are texel centers remapped to [−1, 1]² (`GetRCRayDir`, :149-159) |
| Direction rotation | none: directions depend only on the ray index, with no jitter or per-probe rotation |
| Merge | each pre-averaged texel reads its 4 upper sub-rays at the 4 bilinear upper probes with standard `frac` weights, carries each as `near.a·far` and averages over the sub-rays; `near + far` is written back into the same UAV, so the merge runs in place, top-down (`RCMerge3DCS.hlsl:40, 115-159`, `RadianceCascades.cpp:1408-1425`). A texel with alpha 0 returns early and keeps its own value, as do rays the gather filter dropped (never written, so still cleared). Alpha is not clamped and can exceed 1 after a merge; only the near alpha, which stays in [0, 1], scales radiance, so rgb is unaffected |
| Coalesce | `rgb = Σ/rayCount` over all directions (the count divided by 4 first with pre-averaging), alpha 1: a plain average with no 1/π and no cosine (`RCCoalesce3DCS.hlsl:23-45`) |
| Final lighting | differs from the thesis. The active path (`DeferredLightingPassPS.hlsl`, inside an `if (true)`) skips the coalesce buffer: it reads the cascade 0 probe at `int2(uv·probeCounts)` (nearest, no interpolation), sums each direction's radiance times `clamp(n·d, 0, 1)`, divides by the ray count and multiplies by albedo. The thesis's bilinear read of the coalesce buffer survives only in the dead `else` branch. Emissive pixels show their albedo directly, and a depth-aware branch is commented "Completely broken for now" |
| Sky | differs from the thesis. Only top-cascade misses with the skybox enabled read an equirectangular HDR skybox (`u = atan2(z, x)/2π + 0.5`, `v = acos(y)/π`); other misses return black, and the procedural `SimpleSunsetSky` call is commented out (`RCRaytraceRT.hlsl:262-278`, `Common.hlsli:83-109, 187-194`) |
| Emissive | glTF emissive textures load as sRGB block formats (BC7, BC3 or BC1 `_UNORM_SRGB`); the closest-hit shader samples mip 0 at the interpolated UV and returns `(emission, 0)`; the material's `emissiveFactor` is never read (`RCRaytraceRT.hlsl:241-258`, `MiniEngine/Model/TextureConvert.cpp:171-175`) |
| Probe counts | `floor(width/spacing0)` per axis (a comment says rounding up would place probes off screen), cascade count `floor(log_2(min count))` capped at 8, and integer division by `2^c` per cascade (`RadianceCascadeManager3d.cpp:48-56, 180-188`); directions per side `(uint)sqrt(rays/4)`, which truncates non-square counts |
| Pre-averaging off | implemented and switchable at run time ("Use Pre Average Intervals", on by default), but the ray payload array holds 4 entries, so a ray scaling factor above 4 would overflow (`RCRaytraceRT.hlsl:165, 187-195`) |

Derived from the code: the active lighting returns `albedo·(1/N)·Σ L·max(0, n·d)`. Lambertian shading is `(albedo/π)·E` with `E ≈ (4π/N)·Σ L·max(0, n·d)`, so the code's value is a quarter of it: under a uniform sky of radiance `L` it gives `albedo·L/4` instead of `albedo·L`. The thesis's coalesce path, a plain direction average, gives `albedo·L` under the same sky only if no direction is blocked; with probes on surfaces, the directions into the surface hit it and return black, which halves the value.

## Links found

- Freeman, Sannikov, Margel, "Holographic Radiance Cascades for 2D Global Illumination" (2025) | https://arxiv.org/abs/2505.02041 | HRC, 2D RC with reported render times on an RTX 3080 laptop GPU.
- Osborne and Sannikov, "Radiance cascades: a novel high-resolution formal solution for multidimensional non-LTE radiative transfer" (RASTI, 2025) | https://academic.oup.com/rasti/article/doi/10.1093/rasti/rzae062/7929002 | RC for solar radiative transfer.
- Sannikov, "2d Full Global Illumination #1 (proof of concept, no denoising, interactive fps)" (2022 video) | https://www.youtube.com/watch?v=eS0zd_8nfhk | First public RC demo ([notes](2022_sannikov_youtube_rc_videos.md#2d-gi-1-and-2-2022)).
- ExileCon 2023, "Rendering Path of Exile 2" (Path of Exile talk) | https://www.youtube.com/watch?v=TrHHTQqmAaM | Sannikov's talk on RC in Path of Exile 2.
- Sannikov, "Radiance Cascades: A Novel Approach to Calculating Global Illumination [WIP]" (2024) | https://github.com/Raikiri/RadianceCascadesPaper/blob/main/out_latexmk2/RadianceCascades.pdf | Pre-print cited for the penumbra condition and for specular reflections.
- Max (M ΛX), "Fundamentals of Radiance Cascades" (2024) | https://m4xc.dev/articles/fundamental-rc/ | 2D RC explanation used for the thesis's intuition.
- Xor and Alex, "GM Shaders Guest: Radiance Cascades" (2024) | https://mini.gmshaders.com/p/radiance-cascades | 2D RC blog post, co-authored by Sannikov.
- Xor and Alex, "Guest: Radiance Cascades 2" (2024) | https://mini.gmshaders.com/p/radiance-cascades2 | Follow-up 2D RC post.
- Kung, "Comparing Radiance Cascades to Voxel Cone Tracing for Interactive Global Illumination in Dynamic Scenes" (Linkoping University, 2025) | https://www.diva-portal.org/smash/record.jsf?pid=diva2%3A1967544&dswid=-7797 | Closest prior 3D RC performance study (screen-space, DX11).

- McGuire et al., "Real-time global illumination using precomputed light field probes" (I3D 2017) | https://dl.acm.org/doi/10.1145/3023368.3023378 | Light field probes ([notes](2017_mcguire_light_field_probes.md)).
- Crassin et al., "Interactive Indirect Illumination Using Voxel Cone Tracing" (2011) | https://onlinelibrary.wiley.com/doi/10.1111/j.1467-8659.2011.02063.x | Voxel cone tracing GI ([notes](2011_crassin_voxel_cone_tracing.md)).
- Pharr, Jakob, Humphreys, "Physically Based Rendering" 4th ed., section 3.8 "Spherical Geometry" (MIT Press, 2023) | https://www.pbr-book.org | Equal-area sphere mapping.
