# Horizon-Based Indirect Lighting (HBIL)

| | |
|---|---|
| Author | Benoît Mayaux (Patapom) |
| Date | March 2018 |
| Kind | 40-page write-up with source code, for an Eko Software ARPG on the Warhammer Fantasy Battles licence |
| Link | https://github.com/Patapom/GodComplex/blob/master/Tests/TestHBIL/2018%20Mayaux%20-%20Horizon-Based%20Indirect%20Lighting%20(HBIL).pdf ; code https://github.com/Patapom/GodComplex/tree/master/Tests/TestHBIL ; 80.lv item "Source Code for HBIL Technique", 2018-09-21 |

HBIL extends HBAO into screen-space near-field indirect light: the horizon found in each azimuthal slice gives AO, a bent normal and cone for far-field probe lighting, and the radiance of the surfaces below the horizon for near-field bounce light. Sannikov's paper calls PoE1's GI similar to it ([2023_sannikov_radiance_cascades_paper.md](2023_sannikov_radiance_cascades_paper.md)); the write-up itself does not mention Path of Exile. Visibility-bitmask SSGI replaces its horizon angles with sector bits ([2022_therrien_visibility_bitmask_ssgi.md](2022_therrien_visibility_bitmask_ssgi.md)). Several formulas are garbled in text extraction; those are marked.

## Contents

- [Horizons, AO and bent cones (sec. 1-2)](#horizons-ao-and-bent-cones-sec-1-2)
- [Indirect light (sec. 2.3)](#indirect-light-sec-23)
- [Pipeline (sec. 3)](#pipeline-sec-3)
- [Performance (sec. 3.5)](#performance-sec-35)
- [Limitations (sec. 4)](#limitations-sec-4)
- [For RC](#for-rc)

## Horizons, AO and bent cones (sec. 1-2)

- AO becomes an integral over azimuthal slices with horizon angle `θ(φ)`; per slice the inner integral is `1 − cos θ(φ)`, and AO is one minus a normalized average of `cos θ(φ)` (normalization garbled, p. 4).
- A local view vector from each sample toward the camera defines the slice frame, and screen-space horizon angles are converted to that frame with a trigonometric correction (sec. 1.3, garbled). Front and back horizons start from the slice direction projected on the normal plane, which adds much detail (sec. 2.1, Fig. 8).
- The bent normal is the mean unoccluded direction, with per-slice closed forms built from `½[1 − θ₀ + sin θ₀ cos θ₀ − sin θ₁ cos θ₁]` and `½[2 − cos²θ₀ − cos²θ₁]` (sec. 2.2.1). The cone of solid angle `2π(1 − cos α)` equal to the unoccluded fraction gives `α = cos⁻¹(1 − AO)`; `cos α` is kept for dot-product terms (sec. 2.2.2). The AO uses GTAO's cosine-weighted form (Jimenez et al. 2016).
- Far field from the bent cone: a pre-convolved cube map scaled by a factor, or order-2 SH (9 coefficients) with a reduced aperture, which the paper finds more accurate (sec. 2.2.3-2.2.4).

## Indirect light (sec. 2.3)

- Irradiance splits into `E = E_direct + E_far + E_near`: far from the bent cone, near from the occluded part, `E_near(x, n) = ∫(1 − V)·cos θ·L dω` (garbled). The paper notes that the near field is usually ignored, simplified or baked.
- Near-field radiance from a neighbour is that neighbour's diffuse radiance from the previous frame, `L_N(x, ω) ≈ B_{N−1}`, reprojected, which the paper says gives unlimited bounces; independence between bounces is assumed (sec. 2.3.1). Diffuse radiance is `ρ(x)·(E_direct + E_far + E_near)`.
- Within a slice, when the horizon rises from `θ₀` to `θ₁`, the neighbour's radiance is weighted by the corresponding sine and cosine integral; the only extra buffer beyond HBAO's depth sampling is one radiance buffer (sec. 2.3.2).
- Diffuse is weighted by `1 − F₀` with Schlick Fresnel, dropping a cross term worth at most 0.03 % of irradiance, so metals get almost no indirect diffuse (sec. 2.3.3).

## Pipeline (sec. 3)

- Steps: reproject last frame's diffuse radiance by scatter in compute with a z-test, fill holes with push-pull (Kraus 2009), compute HBIL at quarter resolution, recompose with lighting and post-processing (Fig. 21). Gathering with TAA motion vectors is noted as an alternative.
- Buffers: full-resolution HDR diffuse lighting with mips (RGB10A2 or R11G11B10 tried), full-resolution push-pull buffer with mips, and quarter-resolution 4×4-split radiance (texture array), normal (R8G8_SNORM), depth (R16F), irradiance (HDR) and bent cone (R8G8B8A8_SNORM).
- Two slices per pixel, 90° apart, interleaved over 4×4 tiles at quarter resolution, so `4·4·2 = 32` slices per pixel over the tile; temporal filtering smooths the noise, and a bilateral spatial filter is future work (sec. 3.3).
- Neighbour radiance samples whose normal faces away from the shading point are rejected, with tolerances; depth still counts for AO (sec. 3.4, Figs. 24-25).

## Performance (sec. 3.5)

GTX 680 (2 GB), driver 388.13, 1280×720, 2 slices per pixel, 16 samples per direction, averaged over many scenes: reprojection 0.16 ms (optional), push-pull 0.32 ms (optional), buffer split 0.78 ms, HBIL 1.97 ms; 3.23 ms with the optional passes and 2.75 ms for the core.

## Limitations (sec. 4)

- Off-screen lights and geometry are lost; an off-screen paraboloid buffer is suggested.
- About two directions per pixel need TAA and more denoising. Merging specular with SSR is future work.

## For RC

- The near-field bounce comes from last frame's reprojected radiance, so every bounce past the first is temporal; the same holds for multi-bounce feedback in RC (inference).
- Horizon-based slices are one probe direction set per pixel with no hierarchy. Screen-space RC replaces the per-pixel slices with cascades of probes whose sector count grows with interval length (inference).
