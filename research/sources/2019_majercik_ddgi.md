# DDGI: ray-traced irradiance probe volumes

| Source | Authors | Date | Link |
|---|---|---|---|
| Dynamic Diffuse Global Illumination with Ray-Traced Irradiance Fields | Zander Majercik, Jean-Philippe Guertin, Derek Nowrouzezahrai, Morgan McGuire | 2019, JCGT 8(2) | https://jcgt.org/published/0008/02/01/ |
| Scaling Probe-Based Real-Time Dynamic Global Illumination for Production | Zander Majercik, Adam Marrs, Josef Spjut, Morgan McGuire | 2021, JCGT 10(2) | https://jcgt.org/published/0010/02/01/ |
| RTXGI-DDGI SDK | NVIDIA | 2019 to 2024 | https://github.com/NVIDIAGameWorks/RTXGI-DDGI |

DDGI makes the visibility-weighted probes of [light field probes](2017_mcguire_light_field_probes.md) dynamic; [DDGI resampling](2021_majercik_ddgi_resampling.md) queries it at secondary vertices inside ReSTIR.

DDGI is the probe-grid method world-space RC is most often compared with: one cascade of probes, each tracing a full sphere every frame and blending into octahedral irradiance and depth maps. Its leak prevention, probe relocation and probe states apply directly to the probe grid of a world-space RC, and its blend and query code is mature. See [2014_cigolle_octahedral_unit_vectors.md](2014_cigolle_octahedral_unit_vectors.md) for the octahedral mapping and border copy.

## Probes and storage

- Probes sit on a uniform grid with power-of-two counts, one cage of 8 per cell; 1 to 2 m spacing suits human-scale scenes (the SDK docs say 2 to 3 m). At least one full cage should fit in each room.
- Per probe: 8×8 octahedral irradiance (R11G11B10F, or RGB10A2 in the timed setup) and 16×16 mean and mean-squared distance (RG16F), packed into an atlas with a 1-texel border. 8-bit formats show artifacts; R11G11B10F tints grays green.
- Rays per probe: 32 to 256 in a spherical Fibonacci pattern, rotated randomly each frame (Arvo's method in the SDK). Probe count matters more than angular resolution.

## Update

1. Trace all probe rays in one batch.
2. Shade the hits with the normal shading path, reading last frame's probes for indirect light, which adds one bounce per frame.
3. Blend into each texel: irradiance `Σ max(0, n·ω)·L / (2·Σ w)`, distance with a cosine power of 50 and distances clamped to `1.5·|spacing|`.

Hysteresis 0.85 to 0.98 (SDK default 0.97). The 2021 paper adds:

- **Perceptual encoding:** store `pow(irradiance, 1/5)`, blend in that space, and at query raise each sample to `5/2`, interpolate, and square. Gamma 5 converged fastest and damps fireflies.
- **Convergence heuristics:** per texel, a change above 25% lowers hysteresis by 0.15 and above 80% sets it to 0. Scene events lower it for a few frames (15% for 4 frames after a small light change, 50% for 10 frames after a large one).
- The SDK instead lowers hysteresis by 0.75 past the threshold, scales large brightness jumps by 0.25, and bounds each update so dark-going texels still move at least 1/1024 per frame.

## Query

For each of the 8 probes around the point:

- Bias the sample point: `(0.2·n + 0.8·v)·0.75·minSpacing·0.3` in the 2021 paper (`v` toward the camera), or `0.1·n + 0.1·v` in the SDK. Too much bias leaks through walls.
- Wrap backface weight `((dot(dirToProbe, n) + 1)/2)² + 0.2`.
- Chebyshev visibility from the stored moments at the direction toward the point: if `d > μ`, `p = σ²/(σ² + (d − μ)²)`, cubed; weight × `max(0.05, p)`.
- Crush tiny weights (`w < 0.2` becomes `w³/0.04`), then multiply by the trilinear weight.

Normalize the sum, square (undoing the encoding), and multiply by 2π. Rays that hit backfaces store depth shortened by 80% and are skipped in irradiance blending, so probes inside walls fall out through the visibility test.

## Probe relocation and states

- **Relocation:** 32 fixed (unrotated) rays per probe decide moves. If more than 25% hit backfaces, the probe is inside geometry and moves through the closest backface; if a front face is closer than a minimum distance, it moves away along the farthest free direction. Offsets stay within 45% of a cell. Only static geometry moves probes; dynamic objects made them unstable.
- **Classification:** a probe is inactive when it is inside geometry or when none of its rays hits a surface within one cell; inactive probes trace only their fixed rays. The 2021 paper adds sleeping probes that wake when a dynamic object's bounds (grown by one cell) reach them. Sleeping saved 30 to 50% of update time.

## Volumes

- A camera-following volume is a circular buffer that spawns a new plane of probes when the camera moves a cell, as in a clipmap.
- Several volumes cascade outward at falling density; each fades out linearly over its last cell, and the shader accumulates densest first and stops once the weights reach 1.
- The 2021 update moved to compute with ray results in shared memory, 3× faster than the pixel-shader version.

## Timings

RTX 2080 Ti, 32×8×32 probes, 64 rays, 8×8 maps: trace 0.8 ms, shade hits 0.4 ms, update 0.7 ms, sample at pixels 0.5 ms, 2.6 ms in all (the text also says 7 ms). Throughput stayed above 1.5 Grays/s. Known limits: ghosting behind small bright moving lights, and no fixed ray budget.

## GDC and GTC 2019 talk

McGuire presented DDGI at GDC 2019 as "Ray-Traced Irradiance Fields (Presented by NVIDIA)" (https://www.gdcvault.com/play/1026182/, session 400013301; the video was not read). The page pitches glossy ray tracing plus ray-traced irradiance-field probes that scale across DXR GPUs, cut leaks without per-probe or lightmap work, update without denoising or convolving radiance probes, and stop leaks through walls with moment-based depth. The matching 90-page deck, "Dynamic Diffuse Global Illumination with Ray-Traced Irradiance Fields" (April 2019, GTC session S9900, https://developer.download.nvidia.com/video/gputechconf/gtc/2019/presentation/s9900-irradiance-fields-rtx-diffuse-global-illumination-for-local-and-cloud-graphics.pdf), adds numbers the paper lacks; page numbers are PDF pages, two below the printed footers.

- Diffuse GI 1.0 ms and glossy GI 1.1 ms per frame at 1080p on an RTX 2080 Ti, 1.5 Grays/s (pp. 7-8); mip generation about 0.1 ms; glossy down to about 0.5 ms as in Battlefield V (p. 33). Summary: 1 ms per frame and 4.5 MB per cascade, scaling down to Xbox One by updating less often and up to 4k, 240 Hz and VR (p. 86).
- Cascades of 32×4×32 = 4k probes around the camera, updated often, with coarser cascades in space and time for large scenes; placement can be optimized around static geometry and overridden by artists (p. 42).
- Texels: irradiance 6×6 R11G11B10F and distance 16×16 RG16F, "5 MB GPU RAM for 8k probes" (p. 43); 1024 + 144 = 1168 bytes per probe with bilinear borders (p. 74). The paper uses 8×8 irradiance, so the two disagree; which came later is not stated.
- Three passes: trace (packed with the glossy rays), blend with duplicated borders, sample; shading reads the previous iteration, which gives infinite bounces, at a cost independent of frame rate and resolution (p. 44). Irradiance is blurred over a cosine hemisphere and depth over a power cosine to keep some sharpness (p. 66).
- Hysteresis is the lever for scaling down, with no value, and bright scenes can use fewer diffuse rays (p. 84); no ray count per probe is given.
- Query code (pp. 69-74, as extracted): the Chebyshev weight `variance/(variance + (r − mean)²)` with `variance = |mean² − mean2|` applies only when `r > mean`; the backface weight is `((dot(dir, n) + 1)·0.5)² + 0.2`, times `trilinear + 0.001`, crushed by `weight³/threshold²` below a perceptual threshold of about 0.2; the shading point moves by `bias·(n − view)`; irradiance accumulates as `sqrt(texel)·weight` and returns `(rgb/a)²`, so the blend runs in a square-root domain (inference from the pairing).
- The paper (JCGT 2019) gives what the deck leaves out: power-of-two grids with per-axis spacing (sec. 4.1); every probe updated every frame with the same rays (sec. 4.2); 32 to 256 rays on 16×8×16, 32×8×32 and 32×16×32 grids at 1.48 to 1.66 Grays/s on the 876,127-primitive Greek Temple (Table 1); the Table 2 caption lists colour as RGB10A2 while the text says R11G11B10F; irradiance under 5 % of the range is down-weighted (p. 14). The Table 2 rows sum to 2.6 ms and adding the 2.4 ms brute-force glossy pass gives 5.0 ms, neither of which is the 7 ms in the prose (derived); Fig. 1 gives 6 ms per frame.

## SDK code

- Defaults: 256 rays per probe, hysteresis 0.97, distance exponent 50, irradiance encoding gamma 5, view and normal biases 0.1, minimum front-face distance 1.0. A texel whose stored mean is zero gets hysteresis 0, so new probes fill at once.
- The update lowers hysteresis by 0.75 when a texel's change passes a threshold and scales large brightness jumps by 0.25, with a minimum change of 1/1024 per update. The query's Chebyshev term is `σ²/(σ² + (d − μ)²)` with `σ² = |μ² − E[d²]|`, cubed, and the weight is multiplied by `max(0.05, p)`.
- Found by reading: the distance texture's byte size is set to 8 only when the irradiance format (not the distance format) is two 32-bit floats, so other combinations undercount it; and the sample's default build traces probe rays through NVAPI with back faces culled, while relocation and classification count back-face hits, which that build may then never see (not confirmed by running). The SDK publishes no costs.
