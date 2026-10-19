# Depth-aware upscaling gist

| | |
|---|---|
| Author | GitHub user pixelmager. Gavras's thesis cites it as "Gjoel, M. (2021)"; the gist names no author, and no public link ties the handle to Mikkel Gjøl. |
| Date | Created 2021-12-08 (GitHub gists API) |
| Kind | Gist: Unity HLSL fragment code with comments, 121 lines |
| Link | https://gist.github.com/pixelmager/a4364ea18305ed5ca707d89ddc5f8743 |

The gist upscales half-resolution fog to full resolution without bleeding fog over foreground edges. It samples a rotated four-point disc, checks whether the four samples agree in depth, and falls back to inverse depth-difference weights where they do not. Gavras's thesis uses it as the bilateral filter in its cascade merge and final gather ([Algorithms 7 and 11](2025_gavras_screen_probes_world_intervals_thesis.md)).

The gist links the INSIDE rendering talk (loopit.dk/rendering_inside.pdf, page 39), listed on GDC Vault as "Low Complexity, High Fidelity - INSIDE Rendering" (GDC 2016, Mikkel Gjøl and Mikkel Svendsen of Playdead). Whether that talk covers depth-aware upsampling is not confirmed. The gist also links ProxyPG (ppsloan.org, page 5), Frostbite's stochastic SSR, the RDR2 slides, Playdead's TAA neighbourhood clipping and MBOIT.

## Contents

- [Versions](#versions)
- [Input](#input)
- [Sample pattern](#sample-pattern)
- [Edge test and weights](#edge-test-and-weights)
- [Errors in the listing](#errors-in-the-listing)
- [Author's notes on limits](#authors-notes-on-limits)

## Versions

The gist's own comments describe three versions:

1. Hardware bilinear upscaling, which bleeds fog over foreground geometry.
2. Manual bilinear with a depth test against a stored background depth, used as a proxy for the depth range each sample covers.
3. A four-sample random disc blur. Plain upscaling gives TAA's neighbourhood clamp only 4 distinct values, so it rejects history and the result stays noisy; the disc gives the clamp more distinct values.

## Input

- Fog is computed at half resolution into an RGBA8 target.
- R holds the square root of the fog attenuation, and the read side squares it (`fogAtten *= fogAtten`); the comments call this "saving squared".
- GBA hold the background depth of the texel as a 24-bit float packed in 3 bytes (`DecodeFloatFrom3PackedBytes`).

## Sample pattern

All offsets are in half-resolution texels, with `uv = 0.5·vpos`.

- `rnd` is a blue-noise texel at `(vpos + (1259, 1277)·t) / texsize`. `rnd.x` is uniform and `rnd.gba` is triangular (TPDF) noise.
- `φ = 2π·rnd.x` and `rot = 3.1·(cos φ, sin φ)` (`MAX_FILTERSIZ = 3.1`).
- Radius factors `r_k = sqrt(0.25·rnd.y + 0.25·k)` for `k = 0..3`, which stratifies the disc by area. The square root uses `fastSqrtNR0` from ShaderFastLibs.
- Offsets: `o0 = r0·(rot.x, rot.y)`, `o1 = r1·(−rot.y, rot.x)`, `o2 = r2·(−rot.x, −rot.y)`, `o3 = r3·(rot.y, −rot.x)`. Each sample is rotated 90° from the previous one.
- The largest offset is 3.1 half-resolution texels, 6.2 full-resolution pixels.

## Edge test and weights

- `d_k` is the decoded background depth of sample `k`, and `spread = (max d − min d) / mean(d)`.
- The flag is `spread < 0.1`. It is named `d_edge` but is true where there is no edge.
- Where the flag is true, the four samples are averaged and the full-resolution depth read is skipped.
- Where it is false, `bg = Linear01Depth(_CameraDepthTexture)` at the full-resolution pixel, each sample gets `w_k = 1 / (|d_k − bg| + 1e-5)`, and the result is `Σ w_k·a_k / Σ w_k` with `a_k` the squared stored attenuation.
- There is no spatial kernel and no normal term. The comments note that mismatched samples still contribute, only less.
- Output: `atten·fogLightColour + (2v − 1)/255` for each of the three blue-noise values `v` in GBA, an 8-bit TPDF dither per channel.

| Parameter | Value |
|---|---|
| Samples | 4 |
| Disc radius | 3.1 half-resolution texels |
| Edge threshold (relative depth spread) | 0.1 |
| Weight epsilon | 1e-5 |
| Area strata | 0.25 |
| Noise time offset | (1259, 1277) |
| Dither amplitude | 1/255 |

## Errors in the listing

The code was read, not compiled.

- The no-edge branch assigns `0.25·a_0` where `a_0` is a float4 written to a float, which HLSL truncates to `.x`. As written it returns a quarter of sample 0, not the mean `0.25·(a_0 + a_1 + a_2 + a_3)`.
- The `M_TAU` declaration ends with a comma and runs into the next static declaration, a syntax error.
- The edge branch uses `fogatten` but declares `fogAtten`; HLSL is case-sensitive, so it does not compile.
- The code depends on Unity's `_CameraDepthTexture`, `Linear01Depth`, `DecodeFloatFrom3PackedBytes`, `_RealTime` and `_DitherTexUni_Size`.

## Author's notes on limits

- The background depth is only a proxy for the depth range of a half-resolution sample; a fade over that range might be more accurate.
- The weighting is soft.
- INSIDE applied fog as a uniform additive term. The author suggests storing both irradiance and optical depth, and says order-independent transparency methods may apply.
- No timings or hardware are given.
