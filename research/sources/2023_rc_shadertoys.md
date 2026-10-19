# Radiance cascades Shadertoys

Shadertoy holds the reference 2D implementations of radiance cascades and most public experiments with merge fixes, holographic cascades, 3D variants and depth-aware upscaling. The code here was read from the shader data on shadertoy.com and from the Shadertoy API dump in https://github.com/GabeRundlett/shadertoy-api-shaders (`shaders/<id>.json`). The shaders carry no license unless noted. Suslik is Alexander Sannikov's account: three-rc's README and Gavras's thesis credit Sannikov with 4XXSWS, and GM Shaders calls XcB3Ry Sannikov's gravity simulation, while Shadertoy lists both under Suslik. Code references are `Pass:line` in each pass's source.

Shadertoy runs each pass once per frame and allows four buffers and one cube map, while the cascade merge is a chain of dependent steps. So most shaders here spread the merge over frames. Either every cascade reads the previous frame's cascade above it, and a change takes one frame per level to reach cascade 0, or a fixed ring of buffers computes a few levels per frame and refreshes the whole chain every two or three frames. Several authors note that outside Shadertoy the merge runs top-down within one frame and the lag disappears. Among the RC shaders here, 3cKczD and 33ycDm compute their whole result from the current frame, as do DlSfzz and NfVXRc, which have a single cascade; tf2XRc gathers every cascade in one pass but shows its indirect light a frame late. Frame lags are worked out on the assumption that Shadertoy runs passes in tab order (Buffer A to D, then Image).

A creation date bounds when a shader first appeared, not when its present code was written: Shadertoy keeps one current version under the original date.

## Index

| ID | Title | Author | Created | Forked from | Section |
|---|---|---|---|---|---|
| mtlBzX | Radiance Cascades | fad | 2023-09-02 | | [2D lineage](#mtlbzx-fad-the-original-2d-implementation) |
| DlSfzz | Radiance Cascades Debug | fad | 2023-09-02 | none recorded (its Image comment names mtlBzX) | [2D lineage](#dlsfzz-fad-one-cascade-and-one-ray) |
| mlSfRD | Radiance Cascades 2d Smooth WIP | Suslik | 2023-09-04 | DlSfzz (fad, "Radiance Cascades Debug", 2023-09-02) | [2D lineage](#mlsfrd-suslik-smooth-interval-edges) |
| clVcD3 | Fork Radiance C Quinchilio 468 | Quinchilion | 2023-11-23 | mtlBzX | [2D lineage](#clvcd3-quinchilion-a-ringing-mask) |
| MctXRr | Fork Fork Radia Suslik 677 | Suslik | 2024-04-19 | clVcD3 | [2D lineage](#mctxrr-suslik-a-fixed-grid-and-one-trace-per-upper-probe) |
| 4ctXD8 | RC Experimental Testbed | Suslik | 2024-04-24 | MctXRr | [2D lineage](#4ctxd8-suslik-testbed-of-merge-fixes) |
| MfXyRj | Fork RC Testbed - circle proj | Mytino | 2024-07-18 | 4ctXD8 | [2D lineage](#mfxyrj-mytino-the-circle-projection-fix) |
| lcfcR2 | Fork RC MAX | mxcop | 2024-07-18 | MfXyRj (Mytino, "Fork RC Testbed - circle proj", 2024-07-18, forked from 4ctXD8) | [2D lineage](#lcfcr2-mxcop-four-merges-in-one-playground) |
| 3cKczD | Radiance Cascades 2D GI | youssef_afella | 2025-11-30 | | [2D](#3ckczd-youssef_afella-five-levels-in-one-frame) |
| tf2XRc | Radiance Cascades - sjarod | SJarod | 2025-03-19 | | [2D](#tf2xrc-sjarod-every-cascade-merged-per-pixel) |
| w3XSz4 | VanillaRC - neylick (WIP) | Neylick | 2025-04-26 | | [2D](#w3xsz4-neylick-branching-factor-2-in-a-cube-map) |
| 4clcWn | Radiance Cascades Diagram | Mytino | 2024-07-15 | | [Fixes](#4clcwn-mytino-diagram-of-the-fixes) |
| XcfyDj | RC Reproject Fix Diagram | mxcop | 2024-07-21 | 4clcWn | [Fixes](#xcfydj-mxcop-reprojection-diagram) |
| XffcD7 | Radiance Cascades/gear fix | kornelski | 2024-07-17 | mtlBzX | [Fixes](#xffcd7-kornelski-gear-shaped-intervals) |
| cslSW4 | Local Interpolation | FatalSleep | 2022-11-19 | | [Fixes](#cslsw4-fatalsleep-local-bilinear-interpolation) |
| NttSW7 | Analytic Direct Illumination | Mathis | 2021-12-16 | | [Sky](#nttsw7-mathis-analytic-direct-illumination-and-the-sky-integral) |
| 4ctczl | Holographic Radiance Cascades | Suslik | 2024-11-08 | 4ctXD8 | [HRC](#4ctczl-suslik-two-families-of-probe-lines) |
| tfKyRw | Holographic Radiance Cascades 2D | youssef_afella | 2025-12-01 | | [HRC](#tfkyrw-youssef_afella-one-frustum-with-paper-geometry) |
| WfyyDm | HRC 2D GI | youssef_afella | 2025-12-03 | | [HRC](#wfyydm-youssef_afella-four-frustums-in-one-buffer) |
| NfVXRc | RC Extended gathering | Suslik | 2026-09-01 | 4ctXD8 | [Extended gathering](#nfvxrc-and-sfvszd-suslik-extended-gathering) |
| sfVSzd | Extended gathering pt2 | Suslik | 2026-09-02 | NfVXRc | [Extended gathering](#nfvxrc-and-sfvszd-suslik-extended-gathering) |
| wfyyDz | 2D Volumetric Radiance Cascades | codyjbennett | 2025-12-01 | | [Media](#wfyydz-codyjbennett-2d-volumetric-cascades-with-the-bilinear-fix) |
| ffl3Rf | 2D RC with Hardware Bilinear | codyjbennett | 2026-03-10 | wfyyDz | [Media](#ffl3rf-codyjbennett-hardware-bilinear-without-the-fix) |
| NfySzt | Fork 2D RC HW bilinear | codyjbennett | 2026-09-01 | ffl3Rf (codyjbennett, "2D RC with Hardware Bilinear", 2026-03-10, forked from wfyyDz) | [Media](#nfyszt-codyjbennett-hardware-bilinear-upper-fetches) |
| X3XfRM | Radiance Cascades 3D | Mathis | 2024-11-02 | | [2024_mathis_x3xfrm_surface_probe_rc.md](2024_mathis_x3xfrm_surface_probe_rc.md) |
| M3ycWt | Volumetric Radiance Cascades | Mathis | 2025-02-08 | | [3D](#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes) |
| lXByRh | RC - Screen Space Probes | Mathis | 2024-12-16 | | [3D](#lxbyrh-mathis-screen-space-probes-merged-by-hit-point-reprojection) |
| scy3Dd | 3D Radiance Cascades GI (SPWI) | codyjbennett | 2026-08-08 | | [3D](#scy3dd-codyjbennett-spwi-in-one-shader) |
| 33ycDm | Radiance Cascades GTAO | youssef_afella | 2026-01-24 | | [3D](#33ycdm-youssef_afella-gtao-from-cascaded-horizons) |
| 4XXSWS | Novel depth aware upscaling | Suslik | 2024-03-14 | lXlSzs ("Fractal basic raytracer") | [Upscaling](#4xxsws-suslik-depth-aware-upscaling) |
| MXjcWK | Selective Depth Aware Upscaler | Suslik | 2024-10-01 | 4XXSWS | [Upscaling](#mxjcwk-suslik-selective-bilinear-subsets) |
| 4cffDX | Depth-aware upsampled cube | mxcop | 2024-08-23 | | [Upscaling](#4cffdx-mxcop-normal--and-depth-weighted-upsampling) |
| ffSSz1 | Basic Minmax Interpolation | Suslik | 2026-04-15 | NfSXRh ("Perspective interpolation tests") | [Upscaling](#ffssz1-suslik-linear-minmax-interpolation) |
| NfBSz1 | Minmax tests | Suslik | 2026-04-15 | ffSSz1 (Suslik, "Basic Minmax Interpolation") | [Upscaling](#nfbsz1-suslik-perspective-correct-minmax-interpolation) |
| l3scz8 | Integrating variance opacity | Suslik | 2024-09-10 | | [Upscaling](#l3scz8-suslik-occlusion-from-depth-variance) |
| XcB3Ry | Continuous gravity simulation 2 | Suslik | 2024-01-04 | MfS3Wm | [Gravity](#xcb3ry-and-mfs3wm-suslik-cascades-for-gravity) |
| MfS3Wm | CFD Gravity simulation | Suslik | 2024-01-03 | XfBGWw ("Viscous soft body physics test") | [Gravity](#xcb3ry-and-mfs3wm-suslik-cascades-for-gravity) |
| McSyWm | sRGB vs Linear averaging | Suslik | 2024-07-31 | | [Not RC](#mcsywm-suslik-srgb-against-linear-averaging) |
| 3tdSDj | Segment - distance 2D | iq | 2020-02-15 | | [Not RC](#3tdsdj-iq-distance-to-a-segment) |
| fld3R4 | 2D Light Propagation Volume | paniq | 2021-11-01 | | [Not RC](#fld3r4-paniq-2d-light-propagation-volume) |
| 7c2XDw | Cone sweeping test | Suslik | 2026-04-22 | | [Not RC](#7c2xdw-and-7f2szv-suslik-sweeping-and-diffusion-tests) |
| 7f2SzV | Cone diffusion test | Suslik | 2026-04-24 | 7c2XDw | [Not RC](#7c2xdw-and-7f2szv-suslik-sweeping-and-diffusion-tests) |
| sXcGRB | Two-Way Horizon Map Shadows | SpinningCube | 2026-09-16 | | [Not RC](#sxcgrb-spinningcube-two-way-horizon-map-shadows) |
| XXVfW3 | clunky cascade fb01 | fb01 | 2025-02-04 | | [Not RC](#xxvfw3-fb01-a-per-pixel-gather-without-cascades) |
| MsV3zR | pyramid op | FabriceNeyret2 | 2016-01-18 | | [Not RC](#msv3zr-fabriceneyret2-a-max-pyramid) |

https://www.shadertoy.com/view/XXXyWM, linked as a line-sweep demo, returns Shadertoy's not-found page (checked 2026-10-19): the shader was deleted or made private, or the ID is wrong.

## Lineage

Shadertoy's fork links give this tree:

- mtlBzX (fad) → clVcD3 (Quinchilion) → MctXRr (Suslik) → 4ctXD8 (Suslik). 4ctXD8 then has three lines of descendants: MfXyRj (Mytino) → lcfcR2 (mxcop); 4ctczl (Suslik, holographic); NfVXRc → sfVSzd (Suslik, extended gathering). The community wiki and Sohojoe's Godot port give the same fad → Quinchilion → Suslik → testbed order.
- mtlBzX → XffcD7 (kornelski).
- DlSfzz (fad's "Radiance Cascades Debug", created the same day as mtlBzX) → mlSfRD (Suslik). mlSfRD's own header still names mtlBzX as its source. Shadertoy records no parent for DlSfzz, whose Image comment calls it a fork of mtlBzX.
- 4clcWn (Mytino) → XcfyDj (mxcop).
- wfyyDz → ffl3Rf → NfySzt (codyjbennett).
- youssef_afella's tfKyRw, 3cKczD and WfyyDm have no fork links; WfyyDm's comment calls tfKyRw a simpler version of it. Neylick's w3XSz4 credits fad's shader without a fork link.
- 4XXSWS → MXjcWK and NfSXRh → ffSSz1 → NfBSz1 (Suslik); 7c2XDw → 7f2SzV (Suslik); XfBGWw → MfS3Wm → XcB3Ry (Suslik).

The 4ctXD8 framework shows in all its descendants through shared names (`MERGE_FIX`, `BRANCHING_FACTOR`, `SPATIAL_SCALE_FACTOR`, `C_MINUS1_GATHERING`, the `CastMergedInterval*` family, `MergeIntervals`) and through dead code it carries along: `RAYS_FORK_POW` is defined and never read in MctXRr, lcfcR2 and NfVXRc, and `roundSDim` is unused in MctXRr, lcfcR2, 4ctczl and NfVXRc. The same `MERGE_FIX` number can mean different code in different forks, so a number is only meaningful with the shader it comes from. scy3Dd, outside this tree, uses the same `C_MINUS1_GATHERING` name and credits 4XXSWS for its depth-aware interpolation.

MctXRr (2024-04-19) already traces from each lower probe to each of the four upper probes, the bilinear fix, and its child 4ctXD8 (2024-04-24) makes that the default merge. The community credits the bilinear fix to Mytino's diagram 4clcWn (2024-07-15). Given the caveat on dates above, this shows only that the fix was in Suslik's line no later than its current code.

## Parameters across the 2D implementations

All values are read from the code; "frames to settle" counts how many frames a change takes to reach the displayed result.

| Shader | Cascades | Cascade 0 probes | Cascade 0 directions | Interval rule | Merge | Gather | Frames to settle |
|---|---|---|---|---|---|---|---|
| mtlBzX | 5 | from cube-map capacity | 16, pre-averaged to 1 | `[4^(n−1), 4^n]·L0`, `L0 = 4·diag/(4^5 − 1)` | vanilla bilinear | ×2π | 5 |
| DlSfzz | 1 | 320×180, fixed | 1 | `[0, 100]` px | none (sky only) | ×2π | 1 |
| mlSfRD | 4 | 320×180, fixed | 16, pre-averaged to 1 | `[4^(n−1), 4^n]·7` px, cross-faded ends | vanilla bilinear | ×2π | 4 |
| clVcD3 | 5 | from capacity, multiple of 32 | 16, pre-averaged to 1 | as mtlBzX, plus an overrun of `2^(n+1)` px | vanilla plus ringing mask | ×2π | 5 |
| XffcD7 | 5 | from capacity | 16, pre-averaged to 1 | as mtlBzX, with gear factors | vanilla bilinear | ×2π | 5 |
| MctXRr | 6 | 512×512 | 4 | `[4^n, 4^(n+1)]·10^−3·W` (cascade 0 from 0) | bilinear fix | mean | 6 |
| 4ctXD8 | 6 | 512 across | 4 | starts `(4^k + 1)·L0`, `L0 = 1.5·10^−3·W` | switchable, bilinear fix by default | mean | 6 |
| MfXyRj | 6 | 512×512 | 4 | `[4^n, 4^(n+1)]·1.5·10^−3·W` (cascade 0 from 0) | bilinear fix ending on circles around the upper probes | mean | 6 |
| lcfcR2 | 5 | 512×256 | 4 | `[4^c, 4^(c+1)]·1.5·10^−3·W` (cascade 0 from 0) | one random upper probe | mean of the nearest probe | 5 |
| wfyyDz | 6 | 1 px spacing | 1 | `0.2·[4^c, 4^(c+1)]` px | bilinear fix with absorption | exposure ×2 | 2-frame ring |
| ffl3Rf | 6 | 1 px spacing | 1 | `0.2·[4^c, 4^(c+1)]` px | vanilla, one hardware-bilinear read per upper direction | exposure ×2 | 2-frame ring |
| NfVXRc | 1 | 512 across | 8 | `[0.12, 0.18]·W` | none | extended gather | 1 |
| 3cKczD | 5 | 1 px spacing | 4, pre-averaged to 1 | `[4^n − 1, 4^(n+1) − 1]·⅔` px | vanilla, one hardware-bilinear read | mean | 1 |
| tf2XRc | 3 | 16×16 in UV | 8, doubling per level | `[0, 1], [1, 3], [2, 6]·20/256` UV, overlapping | all cascades composited per pixel | mean | 2 |
| w3XSz4 | 11 | 886×886 | 4, doubling per level | `[2^n, 2^(n+1)]·√2` px (cascade 0 from 0) | two child directions over four probes, divided by 4 | mean | about 10 |

The fad line multiplies the gathered mean by 2π to get fluence, while the testbed line (MctXRr, 4ctXD8, MfXyRj, lcfcR2, NfVXRc, 4ctczl) outputs the mean radiance, as do 3cKczD, tf2XRc and w3XSz4. Both apply the same tone map `1 − (1 + F)^−2.5`, so the same scene displays about 2π darker in the testbed line (derived).

## mtlBzX (fad): the original 2D implementation

- Passes: mouse smoothing, an SDF paint buffer (`.r` signed distance, `.gba` emission), a cube-map buffer holding all cascades, and the image pass. Every cascade reads the previous frame's cube map, so a full update takes `n` frames for `n` cascades.
- Five cascades. Cascade 0 has 16 directions and about `6·W·H/17` texels' worth of probes; each cascade halves the probes per axis and has 4× the directions.
- Pre-averaging: cascade 0 stores one value per probe (the mean of 16 rays), and each texel of cascade `n ≥ 1` stores the mean of 4 rays, so cascade `n` stores `16·4^(n−1)` texels per probe.
- Intervals: with `L0 = 4·|res|/(4^5 − 1)`, cascade `n` covers `[4^(n−1)·L0, 4^n·L0]` (cascade 0 starts at 0), so `[0, L0], [L0, 4L0], …, [64L0, 256L0]`. The top interval ends just past the screen diagonal.
- Trace: sphere tracing with at most 100 steps; a hit needs `t > 0.2` and `d < 1` px. A ray starting inside a shape returns that shape's emission at once.
- Merge: for rays that did not hit, read cascade `n+1` at the same direction index from four probes, with `pf = (p + 0.5)/2`, `q = round(pf) − 1`, `w = pf − q − 0.5`, then `rgb += a·S.rgb`, `a *= S.a`.
- Sky: the top cascade adds the analytic sky integral over each ray's angular bin, divided by the bin width. For a bin `(a0, a1)`: sky `(a1 − a0 − 0.5(cos a1 − cos a0))·SkyColor` plus sun `(atan(8(SunA − a0)) − atan(8(SunA − a1)))/8·SunColor`, all divided by 6; bins that cross 2π are split. Integrating the sky over the bin, instead of sampling one direction, avoids aliasing from the coarse top-cascade bins. The integral is Mathis's ([NttSW7](#nttsw7-mathis-analytic-direct-illumination-and-the-sky-integral)), which divides the full-circle integral by 2π instead of 6.
- Gather: bilinear over four cascade 0 probes, times 2π for fluence, tone map `1 − 1/(1 + F)^2.5`. Emission colors are linearized with `pow(c, 2.2)`.
- The header notes that small point lights show ringing and that the author found no fix. Most forks keep this comment.

## DlSfzz (fad): one cascade and one ray

fad's "Radiance Cascades Debug", created the same day as mtlBzX, is mlSfRD's parent. Shadertoy records no parent for it, while its Image comment calls it a fork of mtlBzX. Despite the title, the code has no debug view or mode switch.

- The shipped constants make it a single cascade: a fixed 320×180 grid, `c_dRes = 1` direction, `nCascades = 1` and a 100 px interval (Common:2-8). Every probe is in the top cascade and traces one ray at angle π, pointing left, over [0, 100] px; a miss adds the sky average over the whole circle, and the merge branch never runs (Cube A:159-186).
- The general code is fad's: cascade `n` uses the grid shifted right by `n` and traces `c_dRes·4^n` rays; it stores 1 entry per probe at cascade 0 and `c_dRes·4^(n−1)` above, each the mean of its rays; intervals are `[4^(n−1), 4^n]·c_intervalLength` with cascade 0 from 0; the merge reads upper entry `j` bilinearly from four upper probes with `pf = (p + 0.5)/2` and corner `floor(pf − 0.5)`, then `rgb += a·S.rgb`, `a *= S.a` (Common:44-50, Cube A:140-192). The diagonal-based interval length is computed and unused (Cube A:151-152).
- Sky: Mathis's sector integral divided by 6, split at 2π, added only for misses and divided by the sector width (Cube A:76-104, 166-171), with sky (0.2, 0.5, 1.0) and a sun of 10·(1, 0.7, 0.1) at 2.0 rad, `S = 64`.
- Trace: up to 100 sphere-tracing steps, a hit at `t > 0.2` with the SDF below 1 px (Cube A:43-51). Gather: bilinear cascade 0 times 2π, plus the painted emission times 2π blended in by `clamp(3 − sd, 0, 1)` within 3 px of shapes, and the tone map `1 − (1 + F)^−2.5` (Image:40-53).
- Space toggles emissive brushes and key 1 a temporary light; an idle Lissajous cursor paints strokes gated by `cos(time)` (Buffer A:28-36, Buffer B:148-152). Buffer B credits its Bézier SDF solver as the only correct one of many the author tried.
- Read from the code: after clipping a ray to the screen, the exit test compares with a distance measured from the unclipped origin, so a march can overshoot the screen edge by the clip offset (Cube A:31-38; the same lines are in mlSfRD, MfXyRj and lcfcR2); texels past the used range return without writing (Cube A:127-128); the temporary light reads a global `screenRes` before `intersect()` sets it, so its radius may be zero on the first sample (Common:101, Cube A:22, 61); cube reads use `texture()` on a direction, so results depend on the sampler settings (Common:38).

## mlSfRD (Suslik): smooth interval edges

The description reads "Original implementation by fad. I just fixed haloes." The halo fix is a cross-fade between neighboring intervals. Against its parent [DlSfzz](#dlsfzz-fad-one-cascade-and-one-ray), mlSfRD changes the constants (16 directions, 4 cascades, a 7 px interval, a 0.02 brush), adds the fade and a hit distance to the trace result, and multiplies the sky by 0; the merge and the Image, Buffer A and Buffer B passes are unchanged.

- Parameters (Common:2-10): a fixed cascade 0 grid of 320×180 probes, 16 directions, 4 cascades, a cascade 0 interval of 7 px, and a fade scale of 10 px. The intervals are `[0, 7], [7, 28], [28, 112], [112, 448]` px. The diagonal-based interval length of fad's version is still computed (Cube A:163-164) and never used.
- Fade (Cube A:175-186): with `s_n = 10·2^n` px, cascade `n` traces from `max(0, start − s_n/2)` to `end + s_(n+1)/2`. A hit's color and alpha are blended toward empty `(0, 0, 0, 1)`, with a weight that rises linearly from 0 at `start − s_n/2` to 1 at `start + s_n/2` and falls back to 0 between `end − s_(n+1)/2` and `end + s_(n+1)/2`.
- Cascade `n`'s end ramp and cascade `n+1`'s start ramp share the boundary as their center and `s_(n+1)` as their width, so their weights sum to one: a hit near a boundary is split between the two cascades instead of belonging wholly to one (derived). Blending alpha with color makes a partly faded hit partly transparent, so the merge lets the upper cascade through by the same share.
- The ramps around the boundaries at 7, 28 and 112 px span `[−3, 17]`, `[8, 48]` and `[72, 152]` px (derived). The first is wider than cascade 0's whole interval.
- Cascade 0 has no cascade below it, yet its start ramp of 10 px around 0 still applies: a hit at the probe keeps weight 0.5 and reaches full weight only at 5 px (derived from Cube A:178-185). Contact hits next to a probe stay half transparent.
- The sky term is multiplied by 0 (Cube A:194), so there is no sky.
- The comment on the fade scale calls it the transition between cascades 0 and 1 (Common:9), but the fade applies at every boundary.
- Storage, merge, gather and tone map are fad's: pre-averaged cascades, four-probe bilinear merge, `×2π` fluence, an SDF overlay within 3 px of shapes. All cascades take `320·180·(1 + 4·3) = 748,800` texels, which needs cube-map faces of at least 354 px (derived).
- The probe grid stays 320×180 at every resolution while the intervals are in pixels, so the probe spacing is 2.5 px at 800×450 and 6 px at 1920×1080, and the ratio of interval to spacing changes with the window (derived).

## clVcD3 (Quinchilion): a ringing mask

- Same design as mtlBzX: five cascades in one cube map used as a flat array, a cascade 0 grid derived from the cube map's capacity with each axis rounded down to a multiple of 32 (Common:46-48), 16 pre-averaged rays at cascade 0, `16·4^n` rays and `4^(n+1)` stored texels per probe at cascade `n`, and `t1 = 4·diag/(4^N − 1)`. Direction varies fastest in memory, then probe x, then probe y.
- The scene is fixed (Buffer B:118-127): a 10 px emissive disc orbiting on the emissive right half of the screen (`x ≥ 0.52·W` emits `(2, 2, 2)`) and a bar occluder in the middle. The mouse only draws a temporary light; the header still describes permanent drawing, which this Buffer B does not implement.
- A hit needs the SDF below 0.5 px.
- `RINGING_FIX` (Cube A:165-217): each ray marches past its interval end to `tMax + 2^(n+1)` px. For a hit beyond `tMax − 2^(n+1)`, the hit is projected along the ray from each of the four upper probes; an upper probe covers the hit when that projected distance reaches `tMax`, where the upper interval begins. The four coverage bits are mixed bilinearly, and when the mix is below 1 the color is scaled by it and alpha set to 1. This removes the part of a hit that the upper cascade will also see, the idea behind the Dolkar mask fix.
- The mask's bilinear bracket uses `floor(pf)` and `pf − q` and omits the probe-center offset, while the merge uses `round(pf) − 1` and `w − 0.5` (Cube A:186-193, 231-232). Mask and merge therefore disagree on probes and weights, probably by accident.
- The sky integral (divided by 6) is defined and its call is commented out (Cube A:226), so there is no sky.
- Gather: four-probe bilinear, `×2π`, and an overlay of the exact emission within about 3 px of shapes (Image:50-53). A change takes about five frames to reach cascade 0.

## MctXRr (Suslik): a fixed grid and one trace per upper probe

- Six cascades on a fixed 512×512 cascade 0 grid with 4 directions (`BRANCHING_FACTOR 2`); the inactive factor-1 branch has 256 probes, 16 directions and a `10^−2·W` base. With `L0 = 10^−3·W`, cascade 0 covers `[0, 4]·L0` and cascade `n` covers `[4^n, 4^(n+1)]·L0`, so the top cascade reaches `4.096·W`.
- Cascade `n` stores `4^(n+1)` texels per probe, each from 4 child rays: the same ray counts as clVcD3. Each cascade holds `1024²` texels, one cube-map face (inference). Probe cells are `W/512 × H/512`, so they are not square on a non-square window.
- Merge (Cube A:155-200): for each child ray and each of the four upper probes, trace from `probe + dir·s_n·L0` to `upper_probe + dir·s_(n+1)·L0` and merge with that probe's texel, weighted bilinearly: 16 traces per texel. This is the bilinear fix. A plain trace per child is still computed and discarded.
- Gather: the mean of 4 directions over 4 bilinear probes, with no `2π`. Emitters use HSV value 1.5, a linear peak of about 2.4 against clVcD3's 0.6.
- Strokes persist: Buffer A keeps a smoothed three-point mouse history, Buffer B draws quadratic Bézier strokes into the SDF, and nothing erases them. With no input, a Lissajous path draws blinking strokes.
- `RINGING_FIX` is defined with no reader, and the ringing comment is stale. `cubemapUsage`, `c_dRes`, `roundSDim` and `RAYS_FORK_POW` are unused. A change takes about six frames to reach cascade 0.

## 4ctXD8 (Suslik): testbed of merge fixes

Six cascades, cascade 0 with 4 directions and 512 probes across, `L0 = 0.0015·W`, interval starts `(4^k + 1)·L0` for `k ≥ 1`. Every cascade holds the same number of texels. The `MERGE_FIX` switch picks the merge:

| Value | Function | What it does |
|---|---|---|
| 0 | `CastMergedInterval` | one ray per direction; four upper probes blended bilinearly for that direction |
| 1 (default) | `CastMergedIntervalBilinearFix` | four rays from the probe, each ending at one upper probe's interval start, each merged with that probe and weighted bilinearly |
| 2 | `CastMergedIntervalMidpointBilinearFix` | splits each ray at a midpoint |
| 3 | `CastMergedIntervalMaskFix` | masks upper probes by hit distance; the "Dolkar fix" |
| 4 | `CastMergedIntervalParallaxFix` | per-upper-probe direction interpolation, intervals stretched by 1.1 for overlap |
| 5 | `CastMergedIntervalInnerParallaxFix` | inner variant of the parallax fix |

The bilinear fix core is short: start at `probe + dir·t_start`, end at `upper_probe + dir·t_end`, march along the normalized difference, merge with the upper probe's value, weight. Each cascade texel also averages its 4 upper directions.

`C_MINUS1_GATHERING`: the image pass traces `[0, L0]` from every pixel for each cascade 0 direction and merges it in front of the interpolated cascade 0 value. This "cascade −1" removes the blur from interpolating cascade 0 near contact. The result is the mean over directions, with no 2π factor.

## MfXyRj (Mytino): the circle projection fix

Mytino's "Fork RC Testbed - circle proj" forks 4ctXD8 and is lcfcR2's parent. Its comments say its goal is to show design patterns for RC: interpolation, packing and abstractions (Image:3-5).

- 4ctXD8's layout: six cascades, a 512×512 cascade 0 grid with 4 directions, `L0 = 1.5·10^−3·W`, cascade 0 over `[0, 4]·L0` and cascade `n` over `[4^n, 4^(n+1)]·L0`, so the top cascade ends at `6.144·W` (Common:4-81). Every cascade holds `2^20` texels, so six need cube faces of at least 1024² (derived).
- Each stored bin traces the 4 sub-directions of the cascade above and stores their mean (Cube A:359-376). The top cascade merges with `(0, 0, 0, 1)`; the sky functions are defined and never called. The gather is bilinear over 4 bins and 4 probes, with no `2π` (Image:58-72).

| `MERGE_FIX` | Function | Traces per ray | What it does |
|---|---|---|---|
| 0 | `CastMergedInterval` | 1 | vanilla: one ray, four upper probes blended, merged once |
| 1 (default) | `CastMergedIntervalBilinearFix` | 4 | one ray per upper probe, merged with that probe and then weighted bilinearly; the active `#if 1` block ends each ray on the circle of radius `t_end` around its upper probe (Cube A:170-213) |
| 2 | `CastMergedIntervalMidpointBilinearFix` | 1 + 4 | a shared leg to a midpoint at `t_end` minus 1.5 upper spacings, then one leg to each upper probe's point at `t_end` (Cube A:215-261) |
| 3 | `CastMergedIntervalMaskFix` | 1 | the Dolkar mask: one ray to `t_end` plus three upper spacings, four masks from the hit distance against each upper probe's interval start projected on the ray, blended bilinearly with a formula from a cited Desmos graph (Cube A:263-316) |

- Circle projection (Cube A:200-207): with `S = P + dir·t_start` and upper probe `C`, the ray ends at the far root `t₊ = (−(a·u + b·v) + √D)/(u² + v²)` of `|S + t·dir − C| = t_end`, where `(a, b) = S − C`, `(u, v) = dir` and `D = t_end²·(u² + v²) − (a·v − b·u)²`. The circle is where the upper probe's interval begins, so each ray stops where its upper probe starts seeing (inference). The result is clamped to `max(t₊, t_start + 10^−6)`, which compares a distance from `S` with one from `P`; at the default constants the clamp never acts (derived).
- Nothing guards `D < 0`. The four bracketing upper probes lie within one upper-cell diagonal of the lower probe, about `0.0039·√(W² + H²)` at cascade 0, against a radius of `0.006·W`, so `D ≥ 0` holds for height-to-width ratios up to about 1.17, and taller views can take the square root of a negative number (derived).
- `MERGE_FIX 3` has its own trace body, in which a ray starting inside a shape returns `(0, 0, 0, 0)` at distance 0 while the other modes return the shape's emission; the comment says the Dolkar variant works better when misses terminate (Cube A:66-99).
- Read from the code: `intersect()` clips the ray to the screen but returns `t` instead of `tOffset + t`, so for rays starting off screen the hit point and distance are short by the clip offset, which also corrupts the mask fix's distances; DlSfzz returns the sum (Cube A:33-50). The hit test has no minimum `t`, so a probe within 0.01 px of an edge hits at once (Cube A:49-50). The midpoint and mask modes use only the x spacing, which is anisotropic on non-square views (Cube A:224, 273).

## lcfcR2 (mxcop): four merges in one playground

mxcop is Max Coppen, the author of surfel RC ([2025_coppen_surfel_radiance_cascades.md](2025_coppen_surfel_radiance_cascades.md)). "MAX" in the title and the "by MAX" comments (Common:56, 96) most likely mark the author's own changes (inference). The shader forks Mytino's circle-projection fork of 4ctXD8 ([MfXyRj](#mfxyrj-mytino-the-circle-projection-fix)), which explains the 4ctXD8 names, and credits fad.

- Defaults: `MERGE_FIX 3`, `SKY_INTEGRAL 0`, `PIXEL_PERFECT 1`, `MODIFIED_INTERVAL_SCALING 0`, 5 cascades, `BRANCHING_FACTOR 2`, `SPATIAL_SCALE_FACTOR 1`, a cascade 0 grid of 512×256 probes with 4 directions, and `L0 = 1.5·10^−3·W` (Common:1-62). Cascade 0 covers `[0, 4]·L0` and cascade `c ≥ 1` covers `[4^c, 4^(c+1)]·L0`, so the top cascade ends at `1.536·W`. A comment says the base length comes from the probe spacing; the code uses the fixed fraction of the width.
- Each cascade takes `2^19` texels, so five need cube-map faces of at least 661 px (derived).
- Each lower texel averages four upper sub-directions `4k + s`, each from the selected cast, divided by 4 (Cube A:331-348).

| `MERGE_FIX` | Function | What it does | Traces per sub-direction |
|---|---|---|---|
| 0 (marked work in progress) | `CastMergedInterval` | circle fix: the straight ray ends where it meets the circle of radius `t_end` around each upper probe (far root; a negative discriminant returns −1, which leaves a zero-length segment that `normalize` cannot handle); bilinear weights | 4 |
| 1 | `CastMergedIntervalBilinearFix` | segment from `P + dir·t_start` to `U + dir·t_end` for each upper probe; bilinear weights | 4 |
| 2 | `CastMergedIntervalMidpointBilinearFix` | the same segment to the nearest upper probe only, unweighted: a nearest fix | 1 |
| 3 (active) | `CastMergedIntervalMaskFix` | a hash of the lower probe index picks one of the four upper probes with equal odds; one segment to it, unweighted | 1 |

- Variant 0 ends on the lower ray itself; variant 1 ends on the same circle but at the angle of `dir` (inference).
- The hash in variant 3 takes neither time nor direction, so the choice is a fixed white-noise pattern: every direction of a probe, and every cascade's probe with the same index, picks the same upper probe (derived). Despite the shared name, this is not 4ctXD8's hit-distance mask.
- Tracing uses the signed distance (not its absolute value) and hits below 0.01 px; the returned hit distance is never read.
- With `SKY_INTEGRAL 1`, the top cascade sums four bin averages without dividing by 4, four times too bright (derived). The sky constants and the division by 6 match XffcD7.
- Gather: `PIXEL_PERFECT 1` takes the nearest cascade 0 probe and averages its 4 directions, with no `2π`; the bilinear path is inactive.
- Unused: `RAYS_FORK_POW`, `roundSDim`, `c0_pixels_count`, the hit distance, and the keyboard and Buffer B channels of Image.
- Against MfXyRj: variant 0 moves the circle into `circle_intersect`, which takes the probe as its origin, so its clamp `max(t, t_start)` compares distances in one frame; variant 1 drops the circle; variant 2 loses its midpoint and weights; variant 3 replaces the Dolkar mask with the hashed pick; and the top-cascade guard that wrote black past the used texels is gone (Cube A:115-279).
- `MODIFIED_INTERVAL_SCALING 1`, off by default, gives cascade 0 a zero-length interval and leaves a gap between cascades 1 and 2, at `[0.5, 3.5]` and `[4.5, 16.5]` scaled base lengths (Common:56-63, 95-107, derived).
- It inherits MfXyRj's `intersect()` without the clip offset and its hit test without a minimum `t` (Cube A:21-58).

## 3cKczD (youssef_afella): five levels in one frame

"Radiance Cascades 2D GI" (2025-11-30) computes a direction-major 2D cascade with one level per pass, and the whole chain from the top level to the image runs in one frame, assuming Shadertoy runs passes in tab order.

- Buffer A computes level 4, B level 3, C level 2, D level 1 and Image level 0. Each reads only the level above it, from the same frame, and no pass reads its own previous frame.
- The work area is the resolution rounded down to multiples of 16. Level `n` splits it into `2^n × 2^n` blocks, one per stored direction bin; the position inside a block is the probe index, and probes sit at `(i + 0.5)·2^n` px (Common:121-131). Each probe traces 4 rays at angles `(4b + i + 0.5)·2π/4^(n+1)` and stores their mean, so level `n` has `4^(n+1)` rays and `4^n` bins per probe, and every level traces four rays per work-area pixel (Common:136-163).

| Level | Pass | Spacing (px) | Rays per probe | Bins | Interval (px) |
|---|---|---|---|---|---|
| 0 | Image | 1 | 4 | 1 | [0, 2.0] |
| 1 | Buffer D | 2 | 16 | 4 | [2.0, 10.0] |
| 2 | Buffer C | 4 | 64 | 16 | [10.0, 42.0] |
| 3 | Buffer B | 8 | 256 | 64 | [42.0, 170.0] |
| 4 | Buffer A | 16 | 1024 | 256 | [170.0, 681.9] |

- Intervals run from `(4^n − 1)·⅔` to `(4^(n+1) − 1)·⅔` px, with 0.3333 standing in for 1/3 (Common:106-113), so they are contiguous, start at the probe and grow 4× per level.
- Merge, for missed rays only: the child position maps to the parent lattice as `0.5·x + 0.25`, clamped inside the parent block, and one hardware-bilinear `texture()` read of the parent bin with the child's index blends the four nearest parent probes; then `rgb += a·parent.rgb` and `a *= parent.a` (Common:144-158). In a direction-major layout, one filtered read is the whole bilinear merge.
- Scene: ten concentric ring arcs with time-varying apertures and rotations, the even rings coloured emitters and the odd rings black occluders, plus two black arcs. Sphere tracing runs 32 steps with a 0.001 px threshold; misses return `(0, 0, 0, 1)`, and running out of steps counts as a miss. There is no sky, tone map or colour conversion; the image is level 0's mean of four rays.
- Read from the code: pixels outside the work area return alpha 0, which reads as an opaque black object, so a 1920×1080 frame has 8 black rows at the bottom; the clamp shifts samples at parent block edges by up to a quarter texel.

## tf2XRc (SJarod): every cascade merged per pixel

"Radiance Cascades - sjarod" (2025-03-19) is a small 2D build "for research" in flatland that cites a paper and two web pages (Image:4-6).

- Three cascades on UV grids of 16×16, 8×8 and 4×4 probes with 8, 16 and 32 directions at angles `(k + 0.5)·2π/q`: probes fall 4× and directions double per level (Common:21-25, Buffer D:39-40). Buffer C stores the cascade descriptors and probe positions; Buffer D traces every interval of every cascade in one pass, row `n` for cascade `n` and column `probe·q + direction` (Buffer D:51-89).
- Interval `n` has length `2^n·L0` with `L0 = 20/256` in UV and starts at 0 for cascade 0 and at `2^(n−1)·L0` above: [0, 1], [1, 3] and [2, 6]·L0. Cascades 1 and 2 overlap on [2, 3]·L0, where contiguous intervals would put cascade 2 at [3, 7]·L0 (Buffer C:49, Buffer D:76-82).
- A ray takes 17 texel reads `len/16` apart from a slightly offset start and stops at the first sample with alpha ≥ 0.5; there is no distance field (Buffer D:9-45). Each light disc emits and blocks; a black mouse disc only blocks.
- Merge (Buffer B:49-102): per pixel and for each of the 32 finest directions, cascades 0 to 2 are read at interval index `i/2^(2−j)`, each blended bilinearly over its four nearest probes and composited front to back (`sum += T·rgb`, `T *= a`), which unrolls the merge operator over the cascades; the sum is divided by 32. That is 960 texel fetches per pixel. There is no pre-averaging, ringing fix, sky, `2π` or tone map.
- Buffer B runs before C and D in tab order and reads them from the previous frame, so the indirect light lags the direct light by one frame (inference). Nothing accumulates over frames.
- Read from the code: Buffer D needs 2048 columns for cascade 0, so on a canvas narrower than 2048 px the last probes are never stored (probes 240 to 255 at 1920 px); probe indices are never clamped, so border cells extrapolate with negative weights and read zero alpha, which darkens them; probes, steps and directions live in UV, so the directions are uneven in pixels on a non-square canvas; and the composite adds direct light twice on the lights and the occluder (Image:12-14). A comment says storing the interval count in alpha failed because Shadertoy forces alpha to 1 (Buffer C:101).

## w3XSz4 (Neylick): branching factor 2 in a cube map

"VanillaRC - neylick (WIP)" (2025-04-26) is a learning build based on fad's shader, crediting fad, Xor, Maxdev and jason.today; the header warns of bugs and high cost. It merges with branching factor 2, and its defects break occlusion.

- Eleven cascades in a 1024² cube map, all computed each frame in one pass that reads the previous frame's cascade above, so a change needs about 10 frames to reach cascade 0 (Cube A:27-123, inference). Cascade 0 gets half the cube's `6·1024²` texels and cascade `n` gets `c0 >> n`; probes per side are `floor(1773/2^(n+1))` (886, 443, …, 1, 0) and directions `4·2^n` (Common:124-183).
- Intervals: with `b = √2` px (BASE_LENGTH 1/1024 times the cube's diagonal, not the viewport's), cascade 0 covers `[0, 2b]` and cascade `n` covers `[2^n·b, 2^(n+1)·b]`, doubling per level up to [1448, 2896] px (Cube A:91).
- Trace: up to 16 sphere-tracing steps, each at most a sixteenth of the interval; a hit within 0.1 px returns the surface colour decoded with a 2.2 power (Cube A:7-24). Five analytic shapes, all emitters, and no direct lighting. The top cascade integrates fad's sky (divided by 6, scaled by 20 before decoding).
- Merge: for each of two child directions, a bilinear blend of four upper probes; the two are summed and divided by 4, then `near + near.a·far` (Cube A:107-123, Common:310-314). Gather: bilinear over four cascade 0 probes, the mean of 4 directions, no `2π`, a 1/2.2 encode and no tone map.
- Read from the code: a hit returns alpha 1 like a miss, so surfaces never block the far term; dividing two child terms by 4 halves the far term at branching factor 2; cascade 10 has 0 probes per side, so its pass divides by zero, and cascade 9's directions from 1536 up read the magenta fill of the unused tail; the bilinear weights for even fine probes are −0.25 and 1.25 on the wrong pair of parents, while a correct `bilinear_samples` helper is never called; the gather places probe `k` at `k/side`, half a cell off; scaling the sky by 20 before the 2.2 power multiplies its linear value by about 728; and the header's example of 16 cascade 0 directions does not match the code's 4.

## 4clcWn (Mytino): diagram of the fixes

Draws the rays of two cascades. The bilinear fix ends each ray at `upper_probe + dir·t_end` (one ray per upper probe). The forking fix starts each ray at `probe + dir_lower·t_start`, where `dir_lower` is the center of the coarser direction bin that contains it, so the four child rays fork from the end of their parent ray. With both off, the diagram shows plain RC.

## XcfyDj (mxcop): reprojection diagram

The radiance-cascades.com site lists this as "Parallel fix" and the wiki as "Parallax fix"; the shader is titled "RC Reproject Fix Diagram", forks 4clcWn, and computes no radiance. The author says the diagram may be wrong and asks how to draw the fix.

- Two cascades: cascade 0 has 8×8 probes spaced `C = 0.1·H` apart with 4 directions over `[0, 0.5C]`; cascade 1 has 4×4 probes with 16 directions over `[0.5C, 2C]`.
- For each cascade 0 ray ending at `E = P + dir·t_end`, the upper probe `U` is the coarse cell containing `P`, its nearest upper probe, and the reprojected direction is `normalize(E − U)` (Image:100-116): the direction in which the upper probe sees the point where the lower ray stops. That direction picks which of the upper probe's rays continues the lower one, the per-upper-probe direction lookup of 4ctXD8's parallax fix.
- `FORKING_FIX_ENABLED` moves the ray start to `P + dir_lower·t_start`. `BILINEAR_FIX_ENABLED` and `REPROJ_FIX_ENABLED` are copied into variables that nothing reads, so the reprojection arrow is always drawn and the bilinear fix never is.
- `CIRCLE_PROJECTION_FIX_ENABLED` ends the ray at the far root of its intersection with the circle of radius `t_end` around `U`, without checking the discriminant. For cascade 0 the nearest upper probe is `0.707·C` from `P` while the radius is `0.5·C`, so two of the four directions of every probe give a negative discriminant and an undefined square root (derived).
- The ringing testbed's radiance array is set to 100 and never written, so its fluence is a constant.

## XffcD7 (kornelski): gear-shaped intervals

Forked from mtlBzX with the same five cascades, 16 pre-averaged base directions, capacity-derived grid, `t1 = 4·diag/(4^N − 1)` and sky divided by 6. Only the interval ends change (Cube A:166-171):

- `tMin` is multiplied by `1 + teeth` when `(j >> 2) & 1` is 0 and by `1 − teeth·overlap` otherwise; `tMax` by `1 + teeth·overlap` when `j` is even and by `1 − teeth` otherwise. With `teeth = 0.1` and `overlap = 1.15`, the start factors are 1.1 and 0.885 and the end factors 1.115 and 0.9.
- A parent ray `d` ends with 1.115 when `d` is even and 0.9 when odd. Its four children share `j >> 2 = d` and start with 1.1 or 0.885 for the same parity, so every boundary overlaps by `0.015·4^(n−1)·t1`, which is `teeth·(overlap − 1)` of the base, while it steps out and in from one direction to the next: the gear (derived).
- The comment says 1.1 works well, but the value is 0.1; at 1.1 the factor `1 − teeth` would be negative.
- Gather: four-probe bilinear, `×2π`, a 3 px emission overlay, the fad tone map. One level merges per frame.

## cslSW4 (FatalSleep): local bilinear interpolation

FatalSleep is the Shadertoy account that the GM Shaders article links as its author's bilinear example. The shader is from 2022-11-19, ten months before fad's, and is a general interpolation demo.

- Samples sit on cell corners every 50 px (`floor(coord/50)·50`) and come from a four-color gradient. Left of the mouse, each pixel blends its cell's four corners by its position inside the cell. Right of the mouse, the same four samples are weighted by the screen-wide UV with two corners swapped, which steps at every cell edge. With no mouse input, the right branch fills the screen.
- RC probes sit at cell centers, so the RC merge uses the same 2×2 blend with a half-cell offset: `q = round(pf) − 1`, `w = pf − q − 0.5`.

## NttSW7 (Mathis): analytic direct illumination and the sky integral

Every fad-lineage shader carries this shader's sky integral. NttSW7 itself solves direct light in 2D exactly, with nothing sampled.

- The scene is six draggable segments: a floor, a wall, two ceilings, a wall that rotates 2 rad/s about its midpoint, and an emitter. Buffer A stores the endpoints; R resets and A pauses.
- Per pixel, each segment starts as one visible part and is clipped against every other segment, giving exact 2D visibility. Each visible part becomes an angular span with `atan2`. The result is `L(P) = max(0, [Sky(0, 2π) − Σ_visible Sky(span) + Σ_emissive E·width] / 2π)`.
- `Sky(a0, a1) = SkyColor·[(a1 − a0) − 0.5·(cos a1 − cos a0)]` integrates `SkyColor·(1 + 0.5·sin a)`, a sky brighter overhead. `Sun(a0, a1) = SunColor/√S·[atan(√S·(A − a0)) − atan(√S·(A − a1))]` integrates `SunColor/(1 + S·(a − A)²)`, a Lorentzian sun at `A = 2` rad with half-width at half maximum `1/√S = 0.125` rad (`S = 64`). Constants: SkyColor `(0.2, 0.5, 1.0)`, SunColor `10·(1, 0.7, 0.1)`, EmissiveColor `4·(1, 0.9, 0.9)`.
- Over the full circle the sky gives `2π·SkyColor` and the sun about `0.381·SunColor`, slightly below the untruncated `π/√S = 0.393` because the tail is cut at 0 and 2π. An unoccluded pixel shows about `(0.807, 0.925, 1.061)` before tone mapping (derived).
- Walls reflect nothing, so the image is direct light only, although the header calls it a single-bounce solution. Segments have no thickness and must not intersect. A scatter version in a block comment was dropped because it compiled too slowly. Tone map `1 − exp(−1.2·C)`, then a power of 0.45.
- The RC shaders divide each bin's integral by its width, which gives the mean radiance over the bin, and then by an unexplained 6.

## Holographic cascades

### 4ctczl (Suslik): two families of probe lines

Forked from 4ctXD8. It uses HRC's line structure but not its extension step.

- Four levels. Level `n` has lines spaced `2^n` times the base spacing (512 lines across at level 0), a constant probe spacing along each line, and `D_n = 8·2^n` directions uniform over 360°, offset by −45° (Common:30-32, 88-90, 231-236). Directions double per level instead of quadrupling.
- Two families: directions within 45° of horizontal live on vertical lines and the rest on horizontal lines (Common:111-115). For `D = 8`, family 0 is −22.5°, 22.5°, 157.5° and 202.5°. Each (line, probe) holds `D/2` intervals per family, `2^21` per level on a square view (derived).
- Merge (Cube A:54-112): each interval takes 16 sub-steps. Each sub-step slides the origin across the probe's cell and picks a fractional direction, then finds where its ray meets the next level's line and interpolates linearly between two neighboring level `n+1` directions and along that line. The near segment runs from the origin to the crossing; the top level uses 1000 px rays with no far term. The 16 results are averaged with equal weights, with no angular weights. The comment above the origin slide says nobody knows why it works.
- Every interval marches to the next level's line, which is top-down RC on HRC-like geometry with no extension.
- Gather: for each of 8 level-0 directions, interpolate the nearest line's interval; output `1.5 ×` the mean, tone mapped.
- One level per frame through the cube map's previous frame, so about three frames of lag. Inactive: three other merge variants (`CastMergedInterval`, `CastMergedIntervalExtended`, `CastMergedIntervalNumericalFast`), a slower gather, the sky integral, and a Dolkar miss-handling variant.

### tfKyRw (youssef_afella): one frustum with paper geometry

- Eleven levels (0 to 10) for one 90° frustum facing +x. Level `n` has planes `2^n` px apart with one probe per pixel row, and rays `(2^n, 2k − 2^n)` for `k = 0…2^n`: the paper's `2^n + 1` rays spanning slopes −1 to 1 (Common:62-63, 103-107). Each texel is one cone between neighboring rays, so every level is a full-viewport texture.
- Cone weights come from angles: with `mid` the average of the two rays, `w1 = angle(ray1, mid)/angle(ray1, ray2)` and `w2 = 1 − w1` (Common:82-94). Level 0 gives 0.5 and 0.5; level 1 cone 0 gives about 0.41 and 0.59. Each ray is weighted by the angular width of its half of the cone.
- Merge (Common:97-159): each ray marches its full length and, unless it hit, composites level `n+1` at its far end. Odd planes read one sample on the next level's plane. Even planes march twice the length and average two samples, which the code calls a fix for discontinuous rays on even planes. No ray is built from two shorter rays, so the extension step is absent, and the cross-level merge has no angular weights.
- Buffers A to C compute three levels each over a three-frame ring (10/9/8, 7/6/5, 4/3/2), Buffer D level 1, and Image level 0 every frame, so levels refresh every three frames and the image lags about two frames while mixing times across levels. The author accepts losing about two thirds of the frame rate and states the ideal as one pass from the top level to level 0.
- The scene is a pulsing white light behind a black occluder, sphere traced for 32 steps; misses are black. There is no sky, no frustum rotation and no division by the frustum count. Output is linear radiance with an sRGB encode.

### WfyyDm (youssef_afella): four frustums in one buffer

"HRC 2D GI" (2025-12-03) recreates the HRC paper's figure, and its comment calls tfKyRw a simpler version of it. It shares tfKyRw's cone weights, doubled even-plane rays, two-sample even-plane average, buffer ring and sRGB encode, and like it has no extension step.

- Four 90° frustums (toward −x, +x, −y and +y) at half resolution, stored as the four quadrants of each buffer; the author says full resolution would need about 40 dispatches (Common:8, 229-233).
- Ten levels. Level `n` has planes `2^n` px apart with one probe per lateral pixel row and `2^n` cones per probe, each cone between rays `(L, 2k − L)` and `(L, 2k + 2 − L)` with `L = 2^n`, spanning ±45° (Common:112-158). Odd-plane rays reach the next parent plane (length `L` to `√2·L`) and read one nearest parent texel; even-plane rays are twice as long and average two parent samples (Common:169-211). Ray `i` of cone `c` reads parent cone `2c + i`.
- Cone weights are each ray's angle to the cone's chord midpoint over the angle between the rays: 0.5 and 0.5 at level 0, 0.41 and 0.59 for level 1 cone 0 (Common:127-143). The first and last rays of a frustum have their direct hits scaled by `0.5/L + 0.5` before the merge, so light merged onto them is not scaled (Common:174-178).
- Schedule: Buffers A to C compute levels 9/8/7, 6/5/4 and 3/2/1 over a three-frame ring, and Buffer D computes level 0 on the third frame and holds it otherwise; levels 6 and 3 read the level above from the previous frame. Level 0 is 0 to 2 frames old on screen and level 9's light 2 to 4 frames old, while the ball overlay updates every frame (inference from the schedule). The author accepts losing two thirds of the frame rate.
- Image averages the four quadrants with weight 0.25, which at level 0 averages four diagonal rays (inference). The scene is 80 emissive balls on a spiral (angle step 2.3067 rad, not the golden angle), sphere traced for 32 steps, with no sky or tone map and an sRGB encode.
- Read from the code: planes at multiples of `2^n` own `2^n` cones, so when the quadrant width is not a multiple of `2^n` the last plane is partial and its high cones are never stored, which matches the author's note about problems at non-power-of-two resolutions; the spiral takes the square root of a negative number for inner balls when its time term is large; and an odd-width buffer puts its last column in the wrong frustum.

## NfVXRc and sfVSzd (Suslik): extended gathering

Both fork the 4ctXD8 framework with one live cascade: 512 probes across, spaced `W/512`, each with 8 directions at `(k + 0.5)·45°` (Common:4, 33-35). Nothing merges: `MergeIntervals` is never called and three of the six listed `MERGE_FIX` modes change no code.

- **NfVXRc** traces every probe direction over `[0.12·W, 0.18·W]` (scale `(80, 120)` times `0.0015·W`) each frame. The image pass gathers `N = 200` directions per pixel (8 while the mouse is held): each gather direction's sample point lies 120 px from the pixel, and for the two stored directions that bracket it, the source probe sits at the sample point minus that direction times 120 px; four probes around it are read bilinearly and the two directions weighted linearly (Image:70-112). The gather radius is a fixed 120 px while the trace ends at `0.18·W`, which match only at a width of about 667 px.
- **sfVSzd** moves the angular smoothing into the cube pass: even frames trace over `[0.075·W, 0.18·W]`, odd frames replace each texel by 200 samples over one direction spacing on each side of its own direction, with source probes on circles of radius `R = 0.18·W` around the sample points (Cube A:96-136). A final pass sums the 8 stored directions over four bilinear probes. The ring gather declares a second `probe_location` that shadows the outer one, leaving its cascade index uninitialized (Cube A:122-127). The mouse state chooses whether the trace-only or the gathered frames are shown.
- `MERGE_FIX 3` (Dolkar) returns zero instead of the origin's emission when a ray starts inside a shape; the outer and inner parallax modes only stretch the trace end by 1.1. `intersect()` clips rays to the screen without adding the clip offset back, so rays that start off screen sample short of the hit. The sky integral is defined and never called.

## Media and transmittance

### wfyyDz (codyjbennett): 2D volumetric cascades with the bilinear fix

- Six levels with probe spacing `2^c` px, `4^c` directions and intervals `0.2·[4^c, 4^(c+1)]` px, so level 0 has a single direction pointing left (Common:106-120). Each probe owns a `2^c × 2^c` block of texels.
- Casts sample `16·2^c` evenly spaced points; each adds `rgb·T·a` and multiplies `T` by `1 − a` (Common:63-79). The opacity applies per sample, not per length, so the same absorber attenuates differently on each level and in each of the four bilinear-fix casts, whose step lengths differ (derived).
- The bilinear fix casts from `probe + dir·start` to `upper_b + dir·end` for each of four upper probes, reads that probe's four child directions, merges, weights bilinearly and averages (Common:141-174).
- Three emitters and absorbers move with time and are drawn at twice their radius; there is no sky. The radiance accumulator starts with alpha 1, so stored alpha is not a transmittance at levels below the top, though the displayed color does not depend on it.
- Buffers A to C alternate between levels 5/4/3 and 2/1/0, so the chain refreshes every two frames. Output: exposure ×2, ACES fit, sRGB. The author calls the bilinear fix a nonphysical trick that hides ringing, and suggests HRC to keep shadow edges sharp.

### ffl3Rf (codyjbennett): hardware bilinear without the fix

"2D RC with Hardware Bilinear" (2026-03-10) forks wfyyDz and is NfySzt's parent. Its description still advertises volumetrics and a four-ray bilinear fix; the code has no bilinear fix.

- The pass graph, the two-frame schedule (levels 5/4/3 on even frames and 2/1/0 on odd frames), the intervals `0.2·[4^c, 4^(c+1)]` px with `16 << c` steps, the scene and the Image pass are wfyyDz's.
- The layout becomes direction-major: each direction is a tile holding that direction for every probe (Common:85-94). The merge reads each of the four upper directions `4·dir + i` with one `texture()` call, which the comment calls a bilinear sampler, clamped to the upper grid, and averages the four (Common:112-127). One filtered read per direction replaces wfyyDz's manual four-probe blend, which that shader's author wrote because float linear filtering is unreliable on some targets (wfyyDz Common:145-146).
- `texture()` takes its mip level from screen-space derivatives, which jump at tile boundaries; NfySzt pins level 0 with `textureLod` (inference; the channel's mip setting is not in the code).
- Shared with wfyyDz, read from the code: the disc test `distance − r < r` draws discs at twice their radius (Common:34); the absorber removes 1 % per sample whatever the step length, an optical depth of about 0.20 per pixel at level 0 and 0.008 at level 5, a factor of about 24 (derived); samples sit at step starts, so interval ends are never sampled; and on resolutions that are not multiples of the spacing the coarse levels misplace probes, by up to about 24 px at level 4 of 1280×720.

### NfySzt (codyjbennett): hardware bilinear upper fetches

Labeled elsewhere as a refraction fix, this shader has no refraction and no angle correction. It keeps wfyyDz's pass graph, two-frame schedule and intervals, and changes the rest:

- The scene is an opaque blocker of radius 50 and one pulsing emitter, intersected analytically per ray and clipped to the interval; a blocker hit stores 0 and skips the merge (Common:52-132).
- The layout is direction-major: each direction is one tile of the probe grid (Common:109-119).
- A miss adds a quarter of the sum of four upper directions, each one hardware-bilinear fetch at the upper position, clamped so the filter stays inside its tile (Common:138-153). There is no bilinear fix and no sky.
- Compared with ffl3Rf, its parent, it keeps the passes, schedule, constants, intervals, direction-major tiles and four-direction hardware fetch (now `textureLod` at level 0), and replaces the marched scene with analytic circles at their nominal radius, half the drawn size of the parent's discs.
- With binary hits its three-way branch equals the parent's merge: an emitter hit returns 1, a blocker hit 0 and a miss the mean of four upper samples (derived). The level-5 sky branch is empty and the stored alpha is fixed at 1.
- Probe positions go through `probeUV·resolution`, which keeps the levels aligned with each other on resolutions that are not multiples of the spacing but stretches them in pixels (Common:60, 122, 142).

## 3D and screen space

### M3ycWt (Mathis): voxel cascades with hemisphere probes

"Volumetric" here means a voxel volume; there are no participating media.

- A procedural 32×32×48 voxel room (columns, arches, cloth, a fountain lamp, a partial roof, a moving floor emitter and a moving sphere), rebuilt each frame, traced by voxel DDA for up to 128 steps. A sun shadow map stores the distance to the first solid voxel along the sun.
- Five levels with probe grids from 32×32×48 (spacing 1) to 2×2×3 (spacing 16). Each probe has six hemispheres, one per face normal. Level `L` uses an `s×s` grid per hemisphere with `s = 3·2^L`: level 0 has the normal plus 8 directions at 45°, and higher levels use concentric square rings with polar angle `(ring/s)·π` and `4 + 8k` azimuth bins per ring (Common:96-121). Each texel stores radiance times solid angle over `2π` times `cos θ`; `w` holds the hit distance (1e7 for sky, −1 for an invalid probe).
- Level 0 traces from every empty voxel, 0.25 voxels off each face; coarser levels move the probe toward an empty fine voxel by ±0.05 per axis.
- There are no intervals: every ray runs to its first hit. A hit distance `t` keeps the probe's own value below `2^L` voxels, hands over to the parent beyond `3·2^L`, and blends linearly between (Cube A:258-259).
- The parent value blends eight parent probes trilinearly. For each, the parent hemisphere facing the child is read in the one direction pointing at the child; if that stored distance is shorter than the offset minus 0.5, the parent counts as occluded and its weight drops to `10^−5` (Cube A:44-103). This is the same visibility test as X3XfRM's.
- Hits add the shadowed sun and last frame's level-0 irradiance in front of the hit, times albedo, so each frame adds a bounce and level 4 reaches level 0 in about four frames. The camera pass sums nine level-0 texels in front of the hit, adds the sun, multiplies by albedo, and applies an ACES fit and a 0.45 power.
- Findings from the code: level 0's direction weights use uncentered grid coordinates, so the zenith texel gets a ring weight of 0.088 and a corner texel the center weight of 0.293; stored values weighted by solid angle over `2π` make the indirect term half of Lambert's `E/π` while the sun term has no `1/π` at all; the visibility test uses the parent's nominal position rather than its nudged one; `BRDF_GGX` is defined and never called.

### lXByRh (Mathis): screen-space probes merged by hit-point reprojection

"RC - Screen Space Probes" (2024-12-16) places hemispherical probes on a half-resolution G-buffer and merges each cascade from the next coarser one by reprojecting the coarser rays' hit points into the finer probe with a visibility test, instead of compositing intervals. Its only smoothing is temporal; the comments say there is no spatial denoising and some flicker remains (Image:2-25).

- Six cascades in the top and bottom halves of Buffers B, C and D (cascades 2 and 5, 1 and 4, 0 and 3). Cascade `n` tiles the half-resolution G-buffer into probes of `P × P` texels with `P = 2^(n+1)`, one texel per direction, so every cascade traces about one ray per half-resolution texel.

| Cascade | Probe tile (half-res texels) | Spacing (px) | Directions | Polar angles of texel centers |
|---|---|---|---|---|
| 0 | 2 | 4 | 4 | 45° |
| 1 | 4 | 8 | 16 | 22.5° to 67.5° |
| 2 | 8 | 16 | 64 | 11.25° to 78.75° |
| 3 | 16 | 32 | 256 | 5.63° to 84.38° |
| 4 | 32 | 64 | 1024 | 2.81° to 87.19° |
| 5 | 64 | 128 | 4096 | 1.41° to 88.59° |

- Directions cover the hemisphere around the pixel normal: texel ring `r` (Chebyshev distance from the tile center) sits at polar angle `(r + 0.5)·π/P` with `8r + 4` evenly spread azimuths. The map is not octahedral, equal-area or cosine-weighted (Common:398-429); it and its inverse round-trip exactly for `P` from 2 to 64 (checked with a port of the code).
- There are no intervals: every ray runs to its first hit, up to 1e6 (Buffer B:65). A hit stores sun light through a shadow ray times albedo, and a miss stores sky radiance at distance 1e6.
- Merge (Buffer B:3-110): each texel picks the four upper probes around its own screen position with bilinear weights. For each, it projects its direction into the upper tile and scans a 5×5 window of upper texels. Each upper hit point (upper probe position plus direction times stored distance) is re-expressed from the current probe and kept if it falls in the current texel's direction bin and is not hidden by the texel's own nearer hit within a visibility window. Kept samples are averaged per probe, weighted by a normal ramp (cosine 0.8 to 1) and a plane test (0.02) floored at 0.001, and combined by the bilinear weights. If the total weight passes 0.0005, the texel's radiance is replaced by the result while its distance stays its own: the merge is a replacement, not `near + near.a·far`.
- After a merge a texel pairs upper radiance with its own hit distance, and the next cascade down rebuilds a hit point from that pair, so the position and the radiance come from different rays (inference). The comments say scattering would beat the 5×5 gather but may be slower.
- The visibility window is 8 times the world size of half a tile at the probe's depth `d`, about `2^(n+3)·d/H_half`: 0.015·d at cascade 0 and 0.47·d at cascade 5 for 540 half-resolution rows. The code builds it with the full-resolution reciprocal on half-resolution coordinates, which halves it (Common:391-395, inference).
- Temporal: a cube-map pass reprojects each pixel's world hit point into the camera of two frames earlier and blends `(old·count + new)/(count + 1)` with the count capped at 15, a 16-frame window that matches the 16-frame period of the probe jitter. History is rejected by normal (0.5) and plane (0.05) tests, with no colour clamp. The top bands read the previous frame's G-buffer and camera, so the displayed image is a frame old and no single frame is correct by itself (Cube A:88-127, Buffer B:48-56).
- The final pass shades half-resolution pixels with the cube's irradiance from the four nearest cascade 0 probes (the mean of their four 45° texels, with no cosine weighting and no `1/π`) plus direct sun, times albedo: one bounce. Output is an ACES fit, then a 0.45 power.
- Read from the code: the probe jitter has no tile index, so every probe in a band moves together, unlike the comment's random placement; the tilted slab's face normals are rotated back by −0.9 rad instead of −1.08 rad, about 10° off; `info.n *= −dot(info.n, d)` scales the normal instead of flipping it; the merge gate (0.0005) sits below the weight floor (0.001), so any accepted sample replaces the radiance; the emissive branches need albedo above 1 and never run; and Image binds Buffers B and D without reading them. The comments add that samples are not BRDF weighted, that visibility is naive, and ask whether stochastic probes can be dropped.

### scy3Dd (codyjbennett): SPWI in one shader

Screen-space probes with world-space intervals (SPWI), six cascades over two frames.

| Cascade | Probe spacing (px) | Directions per probe | Interval (world units) |
|---|---|---|---|
| 0 | 4 | 16 | 0.006 to 0.030 |
| 1 | 8 | 64 | 0.030 to 0.102 |
| 2 | 16 | 256 | 0.102 to 0.390 |
| 3 | 32 | 1,024 | 0.390 to 1.542 |
| 4 | 64 | 4,096 | 1.542 to 6.150 |
| 5 | 128 | 16,384 | 6.150 to 24.582 |

- Intervals are `[s(N), s(N+1)]·0.006` with `s(0) = 1` and `s(N) = 4^N + 1`. Directions per axis equal the probe spacing in pixels, so a direction-major atlas exactly fills one resolution-sized texture per cascade, which holds only for the 4 px base spacing. Directions use the equal-area octahedral map at cell centers.
- The scene is an emissive unit cube colored by its face normals above a floor, traced analytically. Each probe reads one depth at its cell center; there is no G-buffer and no min/max. A non-emissive hit counts as a miss, so the floor neither blocks nor emits.
- Merge: Bilinear3D, from 4XXSWS, iterates four times to find the ratio at which the four upper probes' world positions best interpolate the probe's own position. The bilinear fix then traces from `probe + dir·lo` to each upper probe's `upper + dir·hi`, averages that probe's four child directions with weights 0.25 each, and weights by the 3D ratio.
- Gather: the 16 cascade 0 directions, each read by a hardware-bilinear fetch at the 3D ratio and weighted by `max(0, n·dir)`, divided by the sum of cosines, plus a cascade −1 contact trace over `[0, 0.006]` per pixel. Output: albedo times radiance, exposure ×2, ACES fit, sRGB.
- Buffers A to C compute cascades 5/4/3 and 2/1/0 on alternate frames, and both frames of a pair use one camera time, so the image refreshes every other frame.
- Comments name what is left out: min/max depth probes (which fix bilateral flicker but need binning or temporal data), discontinuity-aware interpolation, the parallax fix, holographic cascades, and split-sum specular from the interpolated intervals.
- Defects from the code: the G-buffer trace starts at the near-plane point but adds its distance to the camera origin, so reconstructed hits sit roughly `0.1/cos θ` too close to the camera; the gather's hardware-bilinear fetch clamps only the base probe, so the last probe column of a direction tile can blend in the next tile's first probe.

### 33ycDm (youssef_afella): GTAO from cascaded horizons

- Three effective levels (a fourth buffer returns −1 and is never read), all from the current frame. Level `n` has origins every `2^n` px and `4^(n+1)` directions, 45° apart at level 0, 22.5° at level 1 and 5.625° at level 2. The radial intervals are `[4^n − 1, 4^(n+1) − 1]·0.1/63` in UV, divided by `1 + depth`, with 2, 4 and 4 samples.
- Each direction keeps the maximum cosine to the view vector over its samples, minus twice a falloff that starts at 0.1 view units. The merge takes `max(own, parent − w)`, where the parent is the bilinear mean of the four child horizons of block `4b + i` and `w = 2·clamp(|Δdepth|, 0, 1)`. The author notes the depth weight should be applied per probe, not to an average.
- The image pass converts level 0's four horizons into two GTAO slices along the diagonals, clamps them to the normal's hemisphere and evaluates GTAO's per-slice integral. A camera-facing open surface gives exactly 1.
- The author calls it noiseless and full of artifacts, and still needing depth-aware merging and upsampling. Taking the maximum horizon per interval and across levels is the HBAO step; the result approximates GTAO with two slices, two to four samples per ray and averaged horizons.

## Depth-aware upscaling and occlusion

### 4XXSWS (Suslik): depth-aware upscaling

A test of upscaling a 1/8-resolution buffer of `(color, depth)` to full resolution, with four panels: plain bilinear, reference, bilateral, and "bilinear 3D". three-rc ports it for screen-space probes.

- Bilateral: weight each of the four neighbors by `bilinear_i·exp(−100·|depth_i − depth|)` and normalize.
- Bilinear 3D: rebuild the four neighbors' world points `P_i` from their depths and the target point `Q`. Starting from the plain bilinear ratio, run two iterations that alternate solving `ratio.x` and `ratio.y` by projecting `Q` onto the line between the two edge points interpolated at the other ratio (`ProjectLinePerp(A, B, p) = dot(p − A, B − A)/dot(B − A, B − A)`, saturated). The final bilinear weights at that ratio sum to 1, so no normalization is needed, and they follow the actual surface instead of rejecting samples. scy3Dd runs four iterations.
- There is no guard against zero-length edges or a zero total bilateral weight.

### MXjcWK (Suslik): selective bilinear subsets

Quadrants show hardware linear, reference, bilateral (`exp(−100·|Δd|)` as in 4XXSWS), and a selective method on an Apollonian fractal at 1/8 resolution. The selective method keeps the 2D bilinear ratio, tries the 15 non-empty subsets of the four taps with the bilinear weights masked to the subset and renormalized, and keeps the subset whose weighted world point lands closest to the full-resolution point. It chooses among discrete subsets rather than solving a continuous 3D ratio; comments describing continuous coefficients and Newton iterations do not match the code, and a variant blending subsets by inverse squared distance is never called.

### 4cffDX (mxcop): normal- and depth-weighted upsampling

Four boxes shaded at one sample per 16×16 cell and upsampled with full-resolution depth and normals. Each tap's weight is its bilinear weight times `clamp(1.5·dot(N, N_i), 0, 1)`; when the spread of the four tap depths exceeds 20% of their mean, each weight is also multiplied by `1/(|d_i − d| + 10^−4)`. Weights are normalized without a guard, so four taps facing away divide by zero. Depth is ray distance, not view depth.

### ffSSz1 (Suslik): linear min/max interpolation

"Basic Minmax Interpolation" (2026-04-15) forks NfSXRh ("Perspective interpolation tests") and is NfBSz1's parent; both describe themselves as deliberately simple and slow demos.

- For each 8×8 cell, all 64 full-resolution samples are traced, and the cell stores the minimum and maximum depth with the red radiance at each (Buffer A:11-37). The image blends the four nearest cells bilinearly in all four channels, then outputs `mix(R_min, R_max, saturate((d − d_min)/(d_max − d_min)))` with the full-resolution depth `d` (Image:12-25). Everything is linear; there is no `1/d` step.
- The scene is an Apollonian fractal sphere traced for 128 steps, shaded by albedo times an orbit-trap AO times 0.9 with fog `exp(−0.1·t)`; depth is ray distance (Common:68-160).
- Shared with NfBSz1, read from the code: flat cells with `d_max = d_min` divide by zero; neighbour indices are not clamped at the border; a shadow ray and a normal are computed and never used; and the camera uses 3.1315 where π is likely meant (Common:168).

### NfBSz1 (Suslik): perspective-correct min/max interpolation

- Cells are 8×8 px (a comment says 32×32). For each cell, 256 full-resolution samples around the center give the minimum and maximum depth, and the cell stores `(dmin, dmax, xmin, xmax)`, where `x` is the world x of the center ray at those depths. A tent weight is computed and not applied.
- The image interpolates `1/d` bilinearly: `dmin' = Σw/Σ(w/dmin_i)`, and `xmin' = Σ(w·xmin_i/dmin_i)/Σ(w/dmin_i)`, likewise for max. Then `t = clamp((d − dmin')/(dmax' − dmin'), 0, 1)` and the output mixes `xmin'` and `xmax'` by `t`. Nothing guards `dmax' = dmin'`.
- The test shows `fract(10·x)` of the interpolated world x against the full-resolution x when the mouse is held, so errors show as broken stripes. There is no error metric, and a ratio-first variant is not in the code.
- Compared with ffSSz1, it widens the window from 8×8 aligned samples to 16×16 centered ones, which reach 4 px into neighbouring cells, stores world x instead of radiance, and blends the endpoints in `1/d` while `t` stays linear in depth. Depth is ray length rather than view z, so the blend is perspective-correct only approximately (inference). Buffer A binds its own output, which only an uncalled `mainImage_experimental` reads.

### l3scz8 (Suslik): occlusion from depth variance

A closed-form test for moment-based depth marching. With a fixed interval `I = [a, b]`, a sample interval of half-width `s` centered at `m`, and a uniform offset on `[−h, h]` with `h = √3·σ` (variance `σ²`), the probability that a point is covered is a trapezoid: `c = |s − h|`, `l = 2·min(s, h)`, height `min(1, s/h)`, `T(x) = H·clamp(1 − (|x − m| − c)/l, 0, 1)`. Its antiderivative gives the mean overlap `O = (F(b) − F(a))/(b − a)` exactly, which the shader checks against a 100-step brute-force sum. The offset is uniform, so only its variance enters, and a Gaussian with the same variance would differ. The comments target SSGI and SSAO from a prefiltered buffer of depth and depth squared; the Chebyshev bound that the tags suggest is not in the code.

## XcB3Ry and MfS3Wm (Suslik): cascades for gravity

A gravitational fluid simulation that uses the cascade hierarchy for an N-body field; XcB3Ry's header names mlSfRD as its RC reference. Both store everything in one viewport-sized texture: the left half holds matter (impulse, density, color) and the right half acceleration, each split into cascades stacked vertically with `(W/2 >> k) × (H/2 >> k)` cells.

- **XcB3Ry** (six cascades, scaling factor 4): level `k` of the matter field is the 2×2 average of level `k − 1`. Level `k` of the gravity field sums `density·4^k·Δ/|Δ|³` (Newton with `G = 1`, no softening) over sources whose distance lies in `((4^(k−1) or 0) + 1, 4^k + 1)·5.1` base pixels, with linear fades of width `2·(2^k, 2^(k+1))` at both band edges, and then adds the bilinear sample of level `k + 1` from the previous frame. So each level holds its own band plus everything coarser, the RC merge, and far fields arrive over frames. Matter advects by scattering each source within radius 10 to its moved position with tent weights. Mass and momentum are conserved, energy is not. The mouse adds mass and impulse; space or the first ten frames reseed about 250 orbiting blobs.
- **MfS3Wm**, the earlier version (seven cascades, factor 2, base distance 15): hard bands `[2^(k−1), 2^k)·15` and the coarser-level accumulation commented out, so each level holds only its own band.
- The scheme carries over to any long-range field whose needed resolution falls with distance.

## Related shaders that are not RC

### McSyWm (Suslik): sRGB against linear averaging

Two cosine-driven colors alternate in rows on the left (a checkerboard with `USE_CHECKERBOARD 1`). The top right shows their average taken on sRGB-encoded values, the bottom right the average taken after a 2.2 power and re-encoded. With black and white (mouse held), the encoded average is 0.5 (128 of 255) and the linear one encodes to 0.730 (186 of 255). The author asks why the checkerboard looks worse than lines. RC merges average many values, so the same rule applies to them: average linear radiance.

### 3tdSDj (iq): distance to a segment

MIT-licensed. The function is `udSegment`: `h = clamp(dot(pa, ba)/dot(ba, ba), 0, 1)` and the distance `|pa − h·ba|`. The demo subtracts a breathing radius to make a capsule and draws a ring of the distance around the mouse. Copies in RC shaders call it `sdSegment`, though it is unsigned.

### fld3R4 (paniq): 2D light propagation volume

Labeled elsewhere as a frustum sweep with angular falloff and Gaussian penumbras; the code is a 2D light propagation volume with none of those.

- Each pixel is a cell holding order-1 circular harmonics (two directional terms and a constant, basis `√((2, 2, 1)/2π)`), one buffer per color channel.
- Each frame, a cell gathers from its four neighbors through three lobes per neighbor: one along the face normal with solid angle `acos(3/5) ≈ 53.13°` and two tilted ones of `acos(3/√10) ≈ 18.43°`, which sum to 90° per neighbor, 12 terms in all. For each lobe, the arriving light `L` and the neighbor's occupancy `E` (from an SDF-derived opacity, 0.5 on the surface) give transmitted light `L·(1 − min(E, 1))` plus a reflection `min(E, 1)·L·albedo`, or `albedo·E` for emitters at a surface.
- Light moves one cell per frame through each buffer's previous frame, so it needs many frames to cross the screen. The inputs are declared as 8-bit, which would clip negative harmonics and the emitters' 20× radiance if that is the storage format. A strip on the right ray-marches a rotated 1D view of the scene. Output: ACES fit, exact sRGB.

### 7c2XDw and 7f2SzV (Suslik): sweeping and diffusion tests

Linked elsewhere for angular falloff and Gaussian penumbras; neither shader has them.

- **7c2XDw:** a scan column moves one pixel per frame. Two carrier columns move one row up and one row down per frame from each single-pixel source, so they cross the scan at 45°, and an accumulator writes the column into the image: a 90° wedge from each source. There are no cascades and no per-level occluder counts. Negative values paint red as a check.
- **7f2SzV:** each frame, every non-source pixel takes the mean of three taps one column to the left at offsets `−δ, 0, +δ` rows, with `δ = 2·mouse.y/H` (0 until the mouse moves). Light spreads to the right in a cone of half-angle `atan δ` through a gap in a wall. The kernel is a box; repeated over many columns it approaches a Gaussian, but the code has no Gaussian term.

### XXVfW3 (fb01): a per-pixel gather without cascades

"clunky cascade fb01" (2025-02-04) carries the radiancecascade tag but has no cascades, probes, intervals or merge. One pass simulates 27 shapes (balls, blocks, triangles and ovals) moving on triangle-wave paths with three collision passes, recomputed in every pixel, and each pixel averages 50 rays sphere-traced for at most six steps up to `t = 4`, with misses black and an ACES fit. It keeps no state, so it has no lag.

### MsV3zR (FabriceNeyret2): a max pyramid

"pyramid op" (2016-01-18) builds a pyramid of 2×2 maxima of the webcam image in one buffer, one level per frame, and divides the image by the top value to normalize brightness. It shares only the stack of resolution levels with RC.

### sXcGRB (SpinningCube): two-way horizon map shadows

Linked elsewhere for isometric terrain; the shader has no isometric view. For each heightmap pixel, a row scan stores the steepest slope toward +x and toward −x (`O(W)` per pixel, cached until the resolution changes). The sun moves overhead along x with a 0.2 rad disc, and visibility is the visible fraction of that disc above each horizon, from the area of a circular segment, combined as east plus west minus one. Ambient occlusion is `0.5 + 0.5·cos(atan(east) + atan(west))`, blended in at 1%. There is no horizon along y.
