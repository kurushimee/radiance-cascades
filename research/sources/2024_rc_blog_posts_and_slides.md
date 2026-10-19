# Short RC blog posts and slides

Seven smaller sources. Each adds only a few facts, so they share one file.

| Source | Author | Date | Link |
|---|---|---|---|
| Implementing Radiance Cascades (notes) | tmpvar | 2023-10 (from page source) | https://tmpvar.com/articles/implementing-radiance-cascades/ |
| Radiance Cascades slides | Christopher Osborne (Goobley) | repository created 2024-08 | https://goobley.github.io/RadianceCascadesSlides/, source https://github.com/Goobley/RadianceCascadesSlides |
| Radiance Cascade Global Illumination | Théo Le Goc (tlegoc) | 2024-10-22 | https://tlegoc.github.io/blogs/radiance-cascade/, code https://github.com/tlegoc/RadianceCascadesGIVulkan |
| Radiance Cascade Penumbra Condition mini spreadsheet (RadiCalc) | Kornel Lesiński (kornelski) | 2024-08 | https://kornel.ski/radiance |
| Radiance Cascades: New Approach to Calculating Global Illumination; Asbjorn Lystrup's Sticky Slime Simulation Gets Better Lighting | 80.lv news | 2023-11-09, 2024-04-08 | https://80.lv/articles/radiance-cascades-new-approach-to-calculating-global-illumination, https://80.lv/articles/asbjorn-lystrup-s-sticky-slime-simulation-gets-better-lighting |
| This Week in Bevy, 2024-07-22 | Chris Biscardi and the Bevy community | 2024-07-22 | https://thisweekinbevy.com/issue/2024-07-22-bevy-jam-5-radiance-cascades-and-calculators-in-many-ui-kits |

## Contents

- [tmpvar implementation notes](#tmpvar-implementation-notes)
- [Osborne slides](#osborne-slides)
- [tlegoc Vulkan blog post](#tlegoc-vulkan-blog-post)
- [This Week in Bevy](#this-week-in-bevy)
- [kornel.ski penumbra calculator](#kornelski-penumbra-calculator)
- [80.lv news](#80lv-news)

## tmpvar implementation notes

A short list of open questions from an early implementer. For screen-space probes the author guessed at marching the depth buffer, or moving each probe onto the surface under its pixel for world-space rays. For participating media it gives the opacity correction for a changed step length, `A = 1 − (1 − A0)^(s0/s)` (GPU Gems, chapter 39), which applies when a cascade marches a coarser volume with longer steps. It notes that world-space 3D needs a lot of memory.

## Osborne slides

The slides present RC for solar radiative transfer; see [2024_osborne_radiance_cascades_radiative_transfer.md](2024_osborne_radiance_cascades_radiative_transfer.md) and [2025_osborne_dexrt_ray_acceleration.md](2025_osborne_dexrt_ray_acceleration.md) for the method. Two points add to those notes.

- **Cost of the two branching choices.** With rays halving per cascade (probes ×¼, rays per probe ×2 in 2D), the rays traced sum to under `2·N0`, while the rays the merge builds grow as `2^I·N0`. With a branching factor of 2 (rays per probe ×4), each cascade traces the same `N0` rays, so cost is `I·N0`, and the merge builds `4^I·N0` rays. The slides say the second choice looks somewhat better.
- **Animation scripts.** The manim scripts use 2D cascades with probe spacing `2^L`, `4·2^L` rays per probe, interval ends `0.25·2^L` (each starting where the last ended), ray `k` of `N` at angle `2π(k + 0.5)/N`, and parent ray `floor(i/2)` at the next level.

The rendered page also has slides on variance-limited mipmaps that the DexRT paper covers in full.

The deck embeds `rc-demo.html`, a WebGL port of the jason.today 2D demo. Its settings: base rays 4, 16 or 64; cascade count `ceil(log(diagonal)/log(base)) + 1`; R11G11B10 float targets; interval start `base^(i−1)·len` and end `((1 + 3·overlap)·base^i − i²)·len` with a default overlap of 0.1. The interval length is scaled by a factor the code calls a "hand-wavy rule" that smooths other base ray counts. A ray that hits, or any ray in the top cascade, skips the merge.

## tlegoc Vulkan blog post

A 2D Vulkan compute version on a screen-space SDF (RGBA32F: color plus distance). The author first tried 3D with screen-space marching in Unity and moved to 2D to learn the method.

- The cascade count and the top cascade's vertical probe count are fixed; the texture width stretches to fit the screen. This keeps the layout symmetric at any aspect ratio, with extra probes on the sides.
- All cascades are traced in parallel, then merged top-down with one dispatch each, waiting on the one before.
- The merge reads the 4 nearest rays of each nearby upper probe, averages them, and interpolates bilinearly across probes.
- It crashes when rays are too long or the march step too small, and shows artifacts at low resolution.

## This Week in Bevy

The 2024-07-22 issue says interest in RC grew after the SimonDev video, links two Bevy implementations (see [2024_bevy_2d_rc_repositories.md](2024_bevy_2d_rc_repositories.md)) and bevy_ridiculous_ssgi, and repeats the view at the time that 3D RC works less well than 2D.

bevy_ridiculous_ssgi (DGriffin91, "very experimental", deferred rendering only, WebGL2 capable) is a cascaded screen-space GI that never names radiance cascades. It marches the prepass depth, normal and color mips from probes every 4 px (`render_scale`), with 16 directions at cascade 0 doubling per level over 6 cascades. Cascade `n` reaches `2^n·cascade_0_dist·√(n + 1)` with an optional overlap into the previous interval, and its step count is the interval length over half the probe spacing, divided by `√(2^n)` or by `2^n` (faster, with more leaking). Each probe merges a 2×2 block of the coarser cascade weighted by depth and normal rejection (2.0 and 100.0 by default). Probe positions and directions are jittered with a noise period of 8 frames, and the options include rough specular, backside illumination and horizon occlusion. It sees only what is on screen and has no bounce.

## kornel.ski penumbra calculator

An interactive table that sizes 2D cascades from the penumbra condition instead of fixed powers of 4. With `s` the base probe spacing, `P(c) = s·2^c`, light size `L`, and penumbra angle `a`:

- The light-to-wall distance where the penumbra starts is `d = (L/2)/tan(a/2)`; the distance where spacing `P` fits inside the penumbra is `w(P) = (P/2)/tan(a/2)`.
- Cascade `c` covers `[(w(P(c)) + d)^p, (w(P(c+1)) + d)^p]`, with exponent `p = 1` by default; cascade 0 starts at 0.
- Rays per probe: `ceil(2π·end/L)` so the smallest light is still hit at the interval end, or `ceil(2π·(end + P)/L)` to cover the probe farthest from the light. A diagonal mode uses `√2·P`, since the largest gap between probes is the diagonal.
- Steps per interval assume volumetric marching at the light size: `ceil(length/L)`. An optional per-cascade mip divider scales lengths, light size, and rays down.

With the defaults (spacing 1, light size 1, 90°, 1920×1080) intervals only double, rays roughly double per cascade (16, 29, 54, 104 …), 12 cascades fit, and the total is 37 M probe-rays and 144 M probe-ray-steps; cascade 0 alone has 56% of the probe-rays. The page notes that this exact condition gives intervals shorter than the probe spacing, unlike the usual ×4 intervals.

## 80.lv news

Two short news posts. The first (2023) covers the paper's release and a 2D demo by Asbjorn Lystrup that runs at 0.3 ms on a GTX 970 with no denoising or temporal accumulation; Sannikov reports about 12 ms for 2, 102, and 1002 particles alike, showing cost independent of light count. The second (2024) shows the same developer's slime sandbox, a custom C++ engine on Vulkan and DX11, lit with RC. Neither gives parameters.
