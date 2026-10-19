# Screen Space Indirect Lighting with Visibility Bitmask

| | |
|---|---|
| Author | Olivier Therrien (CDRIN, Quebec), Yannick Levesque (Cegep de Matane, Quebec), Guillaume Gilet (University of Sherbrooke) |
| Date | arXiv v1 submitted 2023-01-26; v2 revised 2023-01-31. arXiv comment: "Vis Comput (2022)". |
| Kind | Paper (related technique: screen-space GI) |
| Link | https://arxiv.org/abs/2301.11376 |

Visibility-bitmask GI (VBGI). Split RC uses it as "cascade −1" for contact detail below the cascade 0 spacing, and a Chalmers thesis combines it with screen-space RC. The paper replaces the two horizon angles used by GTAO and HBIL with a bit field of N sectors per hemisphere slice. Each depth sample is treated as a thin slab of constant world-space thickness t, so light can pass behind it. The same bitmask drives ambient occlusion, directionally weighted ambient light, and one-bounce indirect diffuse light.

## Introduction

Indirect diffuse light is hard to compute in real time. Screen-space methods keep the cost independent of scene complexity.

Screen-space GI that ray-marches screen pixels, like SSR, is noisy. It integrates irradiance over the whole hemisphere.

HBIL, built on HBAO and GTAO, integrates over a set of directions around the view vector. For each direction it integrates analytically the difference between horizon angles.

These methods read a single-layer depth buffer and assume infinite thickness. The depth buffer is treated as a height field. This causes halos and over-darkening around thin surfaces. Falloff heuristics reduce the artifacts but fail at large radii.

Multi-layer methods (Deep G-Buffer, multi-layer SSRT) store extra depth layers. They are expensive, so the paper keeps one layer.

With one layer, a constant thickness t per depth sample plus a bitmask reduces artifacts around thin surfaces compared with horizon methods.

The main contributions are the bitmask inside SSGI methods, shown on AO, directional AO, and indirect diffuse light.

## Proposed algorithm

### Core idea

The depth buffer is treated as a set of unconnected samples. Each sample has its own thickness.

The hemisphere slice is split into N_b equal sectors. Each sector is binary: occluded or not occluded.

Each depth sample marks a range of sectors as occluded. Occlusion is then counted by counting set bits.

The bitmask replaces the two GTAO horizon angles, theta1 and theta2.

Samples are still taken on both sides of the view vector v. The bit field is centred on the projected normal n.

The paper says the bitmask approximates tracing N_b rays at the cost of one horizon search.

### Sample geometry

- The front sample sits at the depth sample. Its angle theta_f equals the GTAO angle theta.
- The back sample is the front sample shifted by thickness t along the normalised view-space position p (Algorithm 1, line 15).
- The text says each sample acts as thin geometry between theta_f and theta_b. The source formula subtracts t times p/|p|, and the source does not state whether that moves the sample toward or away from the camera.
- theta_b is the angle of the back sample. The occluded range runs from min(theta_f, theta_b) to max(theta_f, theta_b).
- Angles are converted from cosine space to angle space so that samples spread evenly over the hemisphere.

### Hit criterion

- The paper uses a "round" criterion. A sector becomes occluded when the sample covers at least half of it.
- The Algorithm 1 index formulas use floor for the start index and ceil for the width. The text does not reconcile this rounding with the half-coverage rule.

### Bit assignment (restated from Algorithm 1)

The following is a restatement of the paper's logic, not a copy of its listing. The source writes the width term with an extra pi/2 term, as shown.

```
slice_mask = 0
for each step j:
    lo = min(theta_f, theta_b)
    hi = max(theta_f, theta_b)
    start = floor((lo + PI/2) / PI * N_b)
    width = ceil((hi - lo + PI/2) / PI * N_b)     # extra PI/2 as written in source
    step_mask = ((1 << width) - 1) << start
    new_bits = popcount(step_mask AND NOT slice_mask)
    gi += new_bits / N_b * light_j * cos_receiver * cos_emitter
    slice_mask = slice_mask OR step_mask
ao_slice = 1 - popcount(slice_mask) / N_b
```

- The index formula implies that theta runs over a range of pi, centred on zero. The text does not state this range directly.
- All sectors of one sample are set at once. The paper says this makes the work O(1) for any sector count.
- Lighting is taken only from newly occluded sectors (`step_mask AND NOT slice_mask`).

### Algorithm 1 structure

Inputs: constant thickness t, bitmask size N_b, view-space position p, view-space normal n_p, projected radius r.

Step size is r / (N_s + 1). Direction offsets are randomised.

For each slice direction d_i (i = 0 to N_d - 1):
- The pseudo-code computes a slice tangent t_p and its angle t_theta. Neither value is used by the later lines.
- The slice mask starts at zero.
- For each step j (0 to N_s): compute the front and back samples, the occluded range, the step mask, the GI term, and update the slice mask.
- After the steps, add the slice's AO term: 1 - popcount(slice mask) / N_b.

Return AO / N_d and GI / N_d.

The text says samples are taken on both sides of v. Algorithm 1 has one front and one back sample per step. The source does not explain how the two sides map onto the direction loop.

### Sector count and word size

- 32 sectors were chosen. This fits one unsigned 32-bit integer.
- Too few sectors produce banding, especially around thin objects. 32 is just past the point where the banding is almost invisible.
- 128 sectors need four integers and vector instructions. The paper reports 5 to 10 percent overhead compared with 32.

### Thickness

- Thickness t is a constant in world space. The paper calls it a small value.
- Values named in the source: 0.2 for the GI table, and 1, 0.5, 0.25 and 0.1 for the AO thickness figure (radius 2).
- GTAO without falloff is equivalent to an infinite t.
- The paper chooses a small t because over-occlusion around thin objects is more visible than light leaks behind thick objects.
- With a fixed t, depth discontinuities can leak light. The paper shows this against GTAO with and without falloff.
- Option: t can increase linearly with distance from the camera. This counters over-attenuation of distant objects. The paper says the change is barely noticeable.
- A per-pixel thickness heuristic is left for future work.

### Ambient occlusion

- AO is defined as one minus a cosine-weighted visibility integral over the hemisphere, divided by pi.
- The integral splits into an outer integral over the slice angle phi and an inner integral over theta.
- HBAO and GTAO solve the inner integral analytically from two horizons.
- The paper replaces the inner integral with a discrete average over N_b sectors. Each sector contributes 1/N_b.
- The discrete form drops the cos(theta) sin(theta) weight of the inner integral. The text does not discuss this.
- In practice the outer integral uses Monte Carlo over a few slices.
- The radius is the hemisphere radius in world units, aligned to the screen.
- The sample count N_s is the number of depth fetches per horizon side. A slice therefore takes 2 x N_s samples.
- A wider radius spreads samples further apart on screen. The paper says the sample count should rise with the radius to keep the density.
- The AO extension is a modification of Unity's GTAO implementation. The two horizons are replaced by one bitmask.
- Benchmarks use one slice per pixel, jittered over several frames.

### Directionally occluded ambient lighting

- The hemisphere is divided into as many subregions as there are ambient samples (K).
- Each subregion gets one sampling direction, at its centre.
- Ambient light is sampled in that direction. The result is multiplied by the fraction of unoccluded sectors in that subregion.
- A bent normal gives one direction per pixel. It cannot handle several light directions and misrepresents ambient light near thin objects (text).
- Visibility bitmasks give smooth lighting from several directions. Each direction is weighted by its own occlusion.
- Averaging colour first and then multiplying by AO loses colour variation. The paper says per-direction weighting avoids this loss.

### Indirect diffuse

- At each sample, the algorithm reads the light buffer and the normal buffer.
- The light buffer holds direct light with shadows. Ambient light is excluded, because the method computes it.
- A sample contributes only when it covers at least one unoccluded sector.
- The contribution is the newly occluded fraction, times the light, times the cosine at the receiver, times the cosine at the emitter.
- After a sample, its sectors are marked occluded. Later samples behind it therefore contribute less.
- Multi-bounce: indirect light is written back into the light buffer and used in the next frame. Intensity must be balanced, or it accumulates through feedback.
- Too few samples cause banding. Jittering the samples along the sampling direction hides the banding.
- Samples are distributed exponentially, with more density near the pixel. This keeps detail around small nearby objects. The paper does not give the distribution formula.
- The method is bandwidth-heavy. Light and normal reads are not coherent, so the cache is used poorly.
- Half-resolution rendering with a bilateral upsample is about 4x faster according to the text. It flickers more and looks blurrier.
- Compared with SSR-like tracing at the same maximum sample count, the bitmask method is much less noisy. SSR accumulates at most one hit per ray. The bitmask accumulates every sample visible from the pixel.

## Results and evaluation

### Test setup stated in the source

- AO work uses the Lumberyard Bistro scene. The paper chose it for its many thin and shallow surfaces.
- The AO table was measured at 1920x1080 on an Nvidia RTX 2080, with 32 sectors per slice.
- The GI table was measured at 1920x1080. The source does not name the GPU for it.
- The AO denoise pass costs a constant 0.3 ms at 1080p. The GI denoise pass costs 0.33 ms at full resolution and 0.1 ms at half resolution.
- No numeric image-error metric appears in the text. Comparisons with ray-traced references are visual.

### AO sampling pass (source Table 1)

| Radius | Sample count | GTAO (ms) | Visibility bitmask (ms) |
|---|---|---|---|
| 0.8 | 8 | 0.49 | 0.51 |
| 1 | 12 | 0.75 | 0.77 |
| 1 | 16 | 0.95 | 0.97 |
| 2 | 16 | 1.12 | 1.13 |
| 3 | 16 | 1.12 | 1.13 |

- The paper reports an overhead of 0.01 to 0.02 ms.
- The fixed ALU cost is about 15 GPU instructions per sample.
- At larger radii the overhead is hidden, because the pass becomes bandwidth-limited.
- Time scales roughly linearly with sample count.
- A wider radius raises the cache-miss rate and can lower performance.

### Indirect diffuse (source Table 2, constant thickness 0.2)

| Configuration | Sampling (ms) | Denoising (ms) | Total (ms) |
|---|---|---|---|
| a) 8 samples, radius 1, constant steps, full res | 0.9 | 0.33 | 1.23 |
| b) 8 samples, radius 4, constant steps, full res | 1.7 | 0.33 | 2.03 |
| c) 16 samples, radius 4, constant steps, full res | 2.3 | 0.33 | 2.63 |
| d) 16 samples, radius 4, exponential steps, full res | 2.6 | 0.33 | 2.93 |
| e) 32 samples, radius 4, exponential steps, full res | 4.0 | 0.33 | 4.33 |
| f) 16 samples, radius 4, exponential steps, half res | 0.97 | 0.1 | 1.07 |

- The text says half resolution is about 4x more efficient. Computed from the table, configuration d against f gives about 2.7x for the sampling pass and 2.7x for the total.

### Qualitative findings the paper reports

- Fence scene: GTAO over-occludes behind the bars. The bitmask lets light pass between them.
- Poles: GTAO produces halos around the poles. The bitmask does not.
- Wide radius: GTAO produces a blurry occlusion blob. The bitmask keeps small details.
- Ambient: the bitmask gives smoother, multi-directional ambient light than surface normals or bent normals.
- Multi-bounce: compared with a path-traced reference, the result is close but not exact, because the method only sees screen pixels.
- Noise: the bitmask is much less noisy than SSR-like tracing at the same maximum sample count.

## Differences from horizon-based methods (as the source states them)

| Aspect | GTAO / HBIL | Visibility bitmask (this paper) |
|---|---|---|
| Per-slice state | Two horizon angles | Bit field of N_b sectors |
| Depth model | Height field, infinite thickness | Constant thickness t, back sample behind each front sample |
| Integration | Analytic between two horizons | Discrete count of sectors |
| Visibility per slice | One cone | Any number of occluded and unoccluded ranges |
| Thin surfaces | Over-darkening, halos | Light passes behind surfaces of thickness t |
| Ambient light | Bent normal gives one direction | Several directions, each weighted by its own visibility |
| GI weight (HBIL) | Angle difference between samples | Newly occluded sectors times cosines |
| Cost | Reference | About 0.01 to 0.02 ms more in the AO benchmark |

## Code post (2023)

Therrien's post https://cdrinmatane.github.io/posts/ssaovb-code/ (2023-05-11) gives the shader code for the AO case and settles several points the paper leaves open.

- Sectors: `SECTOR_COUNT 32`, one `uint` per slice. The AO integral is `1 − countbits(mask)/32` per direction, averaged over directions, and the post says it ignores the cosine weight.
- Slices are aligned with the view vector `V` and rotated randomly in screen space, so they turn about `V`, not the normal, and the projected normal differs from slice to slice.
- Front and back samples: `dpos = samplePosVS − positionVS`, `dback = dpos − V·thickness`, `θ_f = acos(dot(normalize(dpos), V))` and `θ_b = acos(dot(normalize(dback), V))`. `V` points from the pixel to the camera, so the back sample lies farther from the camera than the front one (inference from that definition), which answers the direction left open in [sample geometry](#sample-geometry).
- Each angle is normalized as `saturate((sgn·(−θ) − N + π/2)/π)`, with `N` the angle from `V` to the projected normal and `sgn` the side of the slice: the `π/2` centers the slice's hemisphere on the projected normal and the division by `π` maps `[N − π/2, N + π/2]` to [0, 1] (inference from the formula). The width is then `ceil((max_f − min_f)·32)` with no `π/2`, so the extra `π/2` in the paper's width term ([bit assignment](#bit-assignment-restated-from-algorithm-1)) belongs to the start offset only (inference).
- Sector update: `start = floor(min_f·32)`, `count = ceil((max_f − min_f)·32)`, `bits = count > 0 ? (0xFFFFFFFF >> (32 − count)) << start : 0`, `mask |= bits`. With `ceil`, a sample occludes every sector it touches; the post names `round` (half covered) and `floor` (fully covered) as alternatives, and the paper uses the half-coverage rule, which is the source of the floor and ceil mismatch noted under [hit criterion](#hit-criterion).
- The post's loop steps at a fixed `rayStep`, the paper's Algorithm 1 at `r/(N_s + 1)`, and the paper spreads indirect-diffuse samples exponentially without giving the exponent (sec. 4.3).
- The post gives no timings; the paper's tables above are on an RTX 2080.

## Limitations (from the source)

- Single depth layer. Hidden surfaces are unknown, so background geometry can be estimated wrongly.
- Thickness is unknown. The method uses a constant or distance-scaled value.
- A small t causes light leaks at depth discontinuities.
- A large t causes over-occlusion around thin objects.
- Too few sectors cause banding, especially near thin objects.
- Too few samples cause banding and lost detail. Jitter and exponential spacing help but do not remove the trade-off.
- Indirect light disappears when the direct light source is off screen.
- The method cannot match a full path tracer, because it only uses screen pixels.
- Multi-bounce needs intensity balancing, or it accumulates.
- GI is bandwidth-heavy and cache-unfriendly.
- Half resolution flickers more and is blurrier.
- Ambient light sources are static or costly to update. The paper does not solve dynamic low-frequency ambient irradiance.

## Conclusion and future work

- The paper argues that horizon-based efficiency can be kept while thickness is handled.
- The method can be added to any horizon-based technique with a small cost.
- It can also improve ambient light by weighting it with directional occlusion.
- Future work: a per-pixel thickness heuristic.
- Future work: caching similar to LSAO, to reduce bandwidth ([LSAO notes](2013_timonen_line_sweep_ambient_obscurance.md)).
- Future work: approximating low-frequency ambient irradiance at runtime.

## Links found

- arXiv | https://arxiv.org/abs/2301.11376 | Paper.
- Code post | https://cdrinmatane.github.io/posts/ssaovb-code/ | AO shader code ([notes](#code-post-2023)).
- The Visual Computer | https://doi.org/10.1007/s00371-022-02703-y | Journal version.
