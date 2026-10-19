# erhe: world-space 3D RC reduced into a DDGI probe field

| | |
|---|---|
| Author | tksuoran |
| Date | 2026-10 (last commit; the RC work is marked experimental) |
| Kind | C++ engine and editor; GLSL compute over Vulkan, OpenGL and Metal |
| Link | https://github.com/tksuoran/erhe (design notes in `doc/editor/radiance_cascades.md` and `doc/plans/radiance_cascades.md`) |

erhe traces world-space RC with hardware ray queries, merges the cascades, and then reduces cascade 0 into the same irradiance and distance octahedral atlases its DDGI renderer produces. The forward pass samples that field unchanged, so RC drops into an existing probe GI path. Its plan document measures RC against DDGI on test scenes, which makes it the best record of where world-space RC falls short in practice.

## Layout

| Setting | Default | Meaning |
|---|---|---|
| `probe_spacing_m` | 1.5 | cascade 0 target spacing `s0` |
| `volume_padding_m` | 1.0 | growth of the content bounds before fitting |
| `max_probes_cascade0` | 65536 | cascade 0 probe budget |
| `max_cascades` | 8 | upper bound (at most 12); cascades stop earlier once the top one has at most 2 probes on its longest axis |
| `cascade0_tile_texels` | 8 | octahedral tile side `q0` of cascade 0 |
| `interval_scale` | 2.0 | `r0 = interval_scale·√3·s0`, so the first interval spans two cell diagonals |
| `texels_per_frame` | 131072 | raw texels traced per frame |
| `hysteresis` | 0.9 | weight kept from history at each trace of a texel |
| `merge_mode` | `per_neighbour_trace` | see below |

- The grid fits the padded bounds of visible content, with probes on the box faces. If the count exceeds the budget, spacing grows by `cbrt(overshoot)·1.05` and the fit repeats.
- Cascade `i`: tile side `q0·2^i` (so 4× the directions), probe counts `(lower + 1)/2` per axis, spacing doubled, and interval `[r0·(2^i − 1), r0·(2^(i+1) − 1)]`, which grows only 2× per cascade. Cascades are added while the longest axis has more than 2 probes.
- Upper probes sit at the centers of lower pairs when the lower count is even, or on the even lower probes when it is odd. Per-axis upper weights are (0.25, 0.75) and (0.75, 0.25) in the even case, (1, 0) and (0.5, 0.5) in the odd case.
- Directions use the octahedral map at texel centers. Cascade `i` texel `(u, v)` has the four children `(2u..2u+1, 2v..2v+1)` in cascade `i+1`.
- Memory per cascade is two RGBA16F atlases (raw and merged). Cascade 0's merged atlas is stored at child resolution (4× raw), and cascade 0 also keeps an RGBA32F distance atlas.

## Trace

- Each frame traces the next 131072 texels in a global order (cascade 0 first) and wraps around, so a full refresh takes several frames.
- A ray runs from the probe over `[t_i, t_{i+1}]`. A front-face hit stores the shaded surface (emission plus direct lights with shadow rays) with β = 0. A backface hit stores zero with β = 0. A miss stores zero with β = 1.
- Each new value blends into history: `mix(traced, history, h)`. After a reset, the k-th trace uses `h = min(hysteresis, k/(k + 1))`, so the first trace replaces the history. Geometry changes, removed items and lighting changes reset it.
- Cascade 0 also records the mean hit distance, the mean squared distance, and the backface fraction per texel.
- Multi-bounce mode feeds the previous frame's field into the hit shading as the ambient term.

## Merge modes

The merge is `merged.rgb = raw.rgb + raw.a·upper.rgb`, `merged.a = raw.a·upper.a`. The top cascade merges with the sky. Each upper probe contributes the mean of its 2×2 child texels, except for cascade 0, which keeps each child separately in its 4× merged atlas.

| Mode | Upper value |
|---|---|
| `interpolate` | trilinear sum over the 8 upper probes |
| `visibility_masked` | drop upper probes that are inside geometry (a probe is inside when over 25% of 64 Fibonacci rays hit backfaces and the nearest backface is closer than the nearest front face) or not visible from the lower probe, then renormalize |
| `per_neighbour_trace` (default) | for each of the 8 upper probes, trace one visibility ray from `p + t_{i+1}·d` to `u_n + t_{i+1}·d`; weight is `trilinear_n·V_n`, renormalized; zero if no upper probe is visible |

`per_neighbour_trace` is a binary version of the bilinear fix: it costs one interval ray plus up to 8 short visibility rays per texel and stops light from passing through a wall between a probe and its upper neighbors.

## Reduce into the probe field

- For each cascade 0 probe, the merged child-resolution radiance is cosine-convolved into a 6×6 irradiance octahedral map (8×8 with border) and the distance statistics into a 14×14 distance map (16×16 with border), the DDGI format.
- Irradiance divides by the cosine weight of non-backface texels: `Σ W·L / Σ W·(1 − b)`. Probes with more than 25% backface solid angle are marked inactive.
- Lobe weights are precomputed on the CPU over each texel's true solid angle (the texel is split into sub-squares; a square at direction `w` with parameter area `dA` covers `dA·|w|₁³`). Only weights above 1e−4 of the maximum are kept. Tile solid angles sum to 4π, and cosine lobes sum to π.
- The reduce is the most expensive pass, about 60% of an update.

## Measurements against DDGI

The plan document compares the two on station scenes (hardware not committed):

- Cost: an RC update is 1.15–1.57× a DDGI update. RC traces about 0.7 ms per million rays against about 6 for DDGI.
- Passing: leaks between paired rooms (0.0017), Cornell box strips, back-wall noise.
- Failing: a leak at probe offset 0.25 (0.0082, gate 0.02 and not above DDGI's 0.0020); a 0.25 m emitter panel; the corridor far field; settling after a light moves (19 updates against DDGI's 29, gate half of DDGI); the worst accuracy group (0.91 against DDGI's 0.65).
- Probes are not relocated. In the Cornell box the nearest probe layer sits 0.27 m above the floor and the layer below sits inside the floor slab; DDGI relocates such probes and does better there.
- Jittering ray directions within each texel improved the near field (floor probes 0.89–1.01 of the reference at `s0` = 0.5) but leaked through thin walls (2%), added noise (0.03–0.07 relative std against DDGI's 0.004) and slowed settling (80–230 updates at hysteresis 0.97). The default is no jitter.

Planned work listed in the document: per-child connecting segments (32 rays per texel), cascade 0 probe relocation, and refitting only on change.

## Stations and gates

The test rooms are built by `scripts/creations/creation_24_gi_test_rooms.py` and measured by `scripts/gi_verify.py`; the thresholds and results are in the plan document (sections 7 and 10 and the phase 6 results).

| Station | Setup | Measures |
|---|---|---|
| `leak_pair` | two 4 × 3 × 4 m rooms sharing a 0.1 m wall, point light in room A only | room B luminance relative to room A |
| `probe_offset_sweep` | three copies of `leak_pair` with the shared wall at 0, 0.25 and 0.5 probe spacings from the nearest probe plane, plus a 0.6 m crawl space and a 0.3 m pillar centered on a probe | worst leak over the offsets |
| `cornell` | 3 m cube room with red and green walls and a spot light | color bleed ratios |
| `emissive_only` | closed room with emissive panels of 1.0, 0.25 and 0.05 m | floor luminance in front of each panel |
| `corridor` | 1.5 × 2.5 × 24 m corridor, spot light on the far end wall | far-field floor profile |
| `courtyard` | walled 8 × 8 m yard with an open top, sun and sky | |
| `dynamic` | `cornell` with a scripted light move and door opening | updates to settle |

- **Leak metric:** Rec. 709 luminance of the linear indirect irradiance (`sample_indirect_diffuse`), averaged over 8 field updates; `leak = max(floor ratio, wall ratio)` of room B over room A (`gi_verify.py:464-476`). Floors are sampled on a 5 × 5 grid inset 0.4 m from the walls, and walls with 0.3 m margins. A run counts as converged at 0.5% relative change per update, with a 180 s deadline.

| Gate | Threshold | RC at defaults | DDGI | Result |
|---|---|---|---|---|
| 1 Disabled regression | ambient and DDGI outputs unchanged | | | |
| 2 Leak | `leak_pair` ≤ 0.01; offset sweep worst ≤ 0.02 and ≤ DDGI's worst | 0.0017; offsets 0.0001, 0.0082, 0.0010 | 0.0008; 0.0020 | pass; fail |
| 3 Placement | recorded only | | | |
| 4 Bounce | red/green and green/red ≥ 1.2 in `cornell` | 2.07 and 2.07 | | pass |
| 5 Small emitters | floor brighter than the room median at the 1.0 and 0.25 m panels (0.05 m recorded only) | 1.06; 0.53 | | pass; fail |
| 6 Far field | no monotonic violations; max log second difference ≤ DDGI's | 0 violations; second difference undefined | | fail |
| 7 Convergence | updates to settle ≤ half of DDGI's | light move 19, door 16 | 29, 258 | fail; pass |
| 8 Noise | `cornell` back-wall std below DDGI's | 0 | 0.0043 | pass |
| 9 Cost | update and full refresh ≤ about 1.5× DDGI on every station | update 1.15–1.57×, full refresh 0.79–1.54× | | pass, although the update maximum is above 1.5 |
| 10 Vulkan validation | 0 errors | | | pass |
| 11 OpenGL and Metal | builds with the GI source forced to ambient | | | |
| 12 Accuracy | worst group mean relative error ≤ 0.25 (0.05 m floor excluded) and ≤ DDGI's | 0.91 at the 1.0 m emitter floor | 0.65 | fail |

- The `leak_pair` value is the worst of three runs, measured 2026-09-28. In the offset sweep only the quarter-spacing wall leaks more than DDGI; the on-plane and midway walls stay at or below DDGI's 0.0020.
- The runs used a headless Vulkan editor, back to back with DDGI on one machine. Absolute timings are kept outside the repository, and the RC documents name no GPU (other erhe documents mention an RTX 3080, a Radeon 890M and an RTX 5070 laptop, none tied to these runs).

## Other O3DE attempt

Chogan-Studios/RadianceCascade (https://github.com/Chogan-Studios/RadianceCascade, CC BY-SA 4.0) is an O3DE Gem that stores 9 SH coefficients per probe on three grids (16³, 8³ and 4³ over the same 16 m cube). Its injection writes an analytic sun-and-plane scene, its merge writes residuals in place, and its output is never composited, so it holds no usable RC method. The only idea of note is an adaptive temporal blend: α = 0.08 when L0 luminance changed less than 10%, 0.3 below 50%, and 1.0 above.
