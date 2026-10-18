# radiance-cascades.com (website and demo)

| | |
|---|---|
| Author | Commit author "Raikiri" (GitHub). The site credits "Alexander" with a link to github.com/Raikiri for LegitScriptEditor, together with tmpvar. The repository has no author field. |
| Date | 2025-10-11 (last commit on main, 2736fbb90) |
| Kind | website |
| Link | https://radiance-cascades.com/ (source: https://github.com/radiance-cascades/radiance-cascades.com) |

The site is a static HTML page (public/index.html) with one interactive 2D radiance cascades demo (public/js/rc.js, 2,237 lines) and link lists to papers, talks, implementations and tools. A second HTML file (public/index2.html) is a draft resources page that nothing links to. The demo runs in WebGL2: the user paints a 2D scene, a jump flood pass builds a distance field, and a set of cascade passes merges probe rays from the top cascade down to the chosen layer.

## Demo: public/js/rc.js

### Symbols used in this note

- W, H: RC resolution (the `width` and `height` of the RC object). Default 512 and 512.
- dpr: device pixel ratio used for the high-resolution copies. Set to `rcScale`. Default 2.0.
- p: `basePixelsBetweenProbes`. Equal to 2^e, where e is the slider value (0 to 4).
- E: `cascadeExtent`, the probe grid size per axis in cascade 0: floor(W/p) by floor(H/p).
- B: `baseRayCount`. Equal to 4^k, where k is the slider value (1 to 3). Default 4.
- s: `spacingBase` = sqrt(B). Equals 2, 4 or 8.
- i: `cascadeIndex`. Cascade 0 is the finest.
- N: `cascadeCount`. The number of cascades used. Top cascade = N - 1.
- L: "Layer to Render" value. Lowest cascade index computed.
- ov: `intervalOverlap`. Default 0.1.
- rI: `rayInterval` (the "Interval Length" slider). Default 1.0.
- cI: `cascadeInterval`. Set to the constant 1.0.
- M: `modifiedInterval` = modifierHack x rI x cI.

### Pipeline per update (default settings)

1. Drawing pass: the brush stroke is written into a drawing texture at RC resolution (W x H). A high-resolution copy (W*dpr x H*dpr) is updated too.
2. Seed pass: each pixel stores its own UV if its drawing alpha is above 0, otherwise (0, 0).
3. JFA pass: a jump flood over the seed texture (see Distance field).
4. DF pass: a distance texture. Each pixel stores the UV distance to its nearest seed, clamped to [0, 1].
5. Cascade passes: one full-screen pass per cascade, from the top cascade (N - 1) down to L. Each pass reads the output of the cascade above it.
6. Overlay pass: the displayed image. Drawn pixels show their own colour when "Layer to Render" is 0. Otherwise the cascade output is shown. On desktop, when the pointer is not drawing, a brush-colour disc is then drawn at the pointer on the screen only.

### Render targets and formats (default settings)

| Target | Size | Format | Filters | Count and use |
|---|---|---|---|---|
| Drawing | W x H | RGBA8 (UNSIGNED_BYTE) | NEAREST | 2, ping-pong |
| Drawing, high resolution | W*dpr x H*dpr | RGBA8 | NEAREST | 2, ping-pong |
| JFA seed and JFA passes | W x H | RG16F (HALF_FLOAT). RG32F (FLOAT) if max(W,H) > 1024 and not mobile | NEAREST | 2 for seeds (only [0] used), 2 for JFA, ping-pong |
| Distance field | W x H | R16F (HALF_FLOAT) | NEAREST | [0] used |
| Cascade output | W x H | R11F_G11F_B10F, format RGB, HALF_FLOAT | min LINEAR_MIPMAP_LINEAR, mag LINEAR | 2, ping-pong |
| Overlay | W*dpr x H*dpr | RGBA16F (default) | NEAREST | 2, ping-pong |
| Indicator | W*dpr x H*dpr | RGBA8 | NEAREST | Created, never used |

Derived from the code, with default URL parameters: the backing store of the canvas is W*dpr = 1024 px, and it is shown at W*canvasScale = 512 CSS px (canvasScale = rcScale / pixelRatio = 1).

Each sampler uniform that is bound to a non-null texture triggers `gl.generateMipmap` on that texture during `setUniform`. Mip levels are therefore regenerated on each render.

### Distance field (seed, JFA, DF)

- Seed value: s(p) = UV(p) if alpha(p) > 0, otherwise (0, 0).
- Passes P = ceil(log2(max(W, H))) + 1. For W = H = 512 this is 10 passes (derived).
- Pass i uses offset k_i = 2^(P - 1 - i) pixels, so the offsets run 512, 256, ..., 2, 1 for the default size (derived).
- In each pass, a pixel reads its own value and the 8 neighbours at distance k_i. It keeps the non-empty seed with the smallest squared distance to its own UV.
- A value counts as empty when both components are <= 0. A seed at exactly (0, 0) is therefore treated as empty.
- If no seed is found, the pixel stores (-1, -1).
- DF value: min(1, |UV(p) - seed(p)|) in UV units. A pixel with (-1, -1) gets 1.
- The source has no comment on the accuracy of this approximation.

### Cascade parameters and defaults

| Symbol | Formula in code | Default (B = 4, p = 1) |
|---|---|---|
| D (diagonal) | sqrt(W^2 + H^2) | 724.08 |
| N | ceil(ln D / ln B) + 1 | 6 (B = 16: 4; B = 64: 3). Derived. |
| E | floor(W/p), floor(H/p) | 512 x 512 |
| s | sqrt(B) | 2 |
| M | modifierHack x rI x cI, with modifierHack = p if B < 16, else s | 1.0 |
| start_i | (i = 0 ? 0 : B^(i-1)) x M | see table |
| length_i | ((1 + 3 x ov) x B^i - i^2) x M | see table |

- The source comments call the modifierHack rule "hand-wavy" and say it improved smoothing for base ray counts other than 4.
- The "Base Ray Count" slider sets B = 4^k. Displayed value is 4^k, so 4, 16 or 64.
- The "Pixels Between Base Probes" slider sets p = 2^e. Displayed value is 2^e, so 1, 2, 4, 8 or 16.
- The "Interval Overlap %" label has a % sign. The value is used directly as the fraction ov in the formula, and the slider shows the raw value (0.1 by default). The source does not say whether the % sign is meant literally.

### Index math per cascade

For cascade i, with spacing_i = s^i, grid texel c (per axis, 0 <= c < E), and texel uv = (c + 0.5) / E:

1. Block size: size_i = floor(E / spacing_i).
2. Probe index inside its block: probe = c mod size_i (per axis).
3. Block index: block = floor(c / size_i) (per axis, each in [0, spacing_i)).
4. Block id: b = block.x + spacing_i x block.y.
5. Each texel handles B rays with indices k = b x B + j, for j = 0 to B - 1. The ray count per probe is R_i = B^(i+1).
6. Ray angle: theta_k = (k + 0.5 + n) x (2pi / R_i), where n = rand(uv x (i + 1)) when noise is on, otherwise 0.
7. Ray direction: (cos theta_k, -sin theta_k).
8. Probe centre in full-resolution pixels: (probe + 0.5) x p x spacing_i.
9. Ray segment: starts at centre + dir x start_i and extends length_i along dir. The code computes rayEnd = rayStart + dir x interval.y, so `length_i` is added to the start point. The code does not subtract start_i. The source does not say whether this is the intended endpoint.
10. Texel output: the average of the B ray results (each weighted by 1/B).

Derived facts from the layout:

- Each cascade has E x E texels. Each texel stores B rays, so each cascade has E^2 x B rays in total, the same for every cascade.
- The cascade grid is stored in a W x H texture. The lookup UV is (grid coordinate) / E. A mip level log2(p) has E texels per side, so the fetch uses that level when p > 1.

### Merge from the upper cascade

- If the ray hits a surface (alpha > 0), the result is the hit colour and no merge happens.
- If the ray misses and i is not the top cascade (i < max(1, N - 1)), the code merges from cascade i + 1.
- Merge offset: o = (probe + 0.5) / s.
- Upper spacing: s^(i+1). Upper grid size: U = floor(E / s^(i+1)).
- Upper lookup coordinate: q = (k mod s^(i+1), floor(k / s^(i+1))) x U + clamp(o, 0.5, U - 0.5). The UV is q / E.
- Note that k here is the ray index, not the block index.
- The lookup is one `textureLod` on the cascade i + 1 output, with LOD log2(p) (0 when p = 1). The filter is LINEAR, so the GPU's bilinear filter does the interpolation between the four neighbouring texels.
- The result is added to the ray colour, and alpha is set to 1.
- The wiki's bilinear-fix page refers to four bilinearly sampled upper-cascade probes. This code performs one filtered texture read.

### Ray march

- Sphere tracing on the distance texture. The step is in pixels, so the distance (UV units) is multiplied by min(W, H).
- Each step: read df at the current UV. If df <= minStep (half a texel, min(1/W, 1/H) x 0.5), the ray hits. The hit colour is scene.rgb raised to srgb, and alpha is the scene alpha.
- Otherwise the ray advances by df x min(W, H) pixels. The loop stops when the travelled distance reaches the segment length, or when the position leaves [0, 1]^2. A miss returns (0, 0, 0, 0).
- The loop has no fixed iteration cap.

### Sun and sky

- The sun is on only when the sun button is on (`enableSun`). It applies only to the top cascade (i = N - 1).
- For each ray in the top cascade, the radiance is max(sky(theta), radiance) per channel, where radiance is the merged or hit value. This applies to hit rays too.
- Default sky (Naive GI Noise off): phi = mod(theta - sunAngle, 2pi). Sun term I = max(0, cos(phi))^4. Sky = mix(sunColor x I, skyColor, 0.3) = 0.7 x sunColor x I + 0.3 x skyColor, with sunColor = (0.95, 0.9, 0.8) x 3 and skyColor = (0.2, 0.24, 0.35) x 4.
- Old sky (Naive GI Noise on): I = smoothstep(1.0, 0.0, phi). Sky = (0.95, 0.95, 0.9) x I + (0.02, 0.08, 0.2). The smoothstep edges are reversed (edge0 = 1.0 > edge1 = 0.0). The source does not say whether this is intended.
- The sun angle is used in radians. The page does not state the unit. The unit is inferred from the modulo by TAU.

### sRGB handling

- The scene is decoded on a hit: rgb^srgb.
- The output of the cascade at index L (the "Layer to Render" value) is encoded: rgb^(1/srgb). Cascades above L stay linear.
- With the checkbox off, srgb = 1.0, so no conversion happens.
- The overlay shows values with no conversion.

### Derived cascade table (not stated in the source)

Computed from the formulas above with W = H = 512, p = 1, ov = 0.1, rI = 1.0.

B = 4 (default), N = 6, modifierHack = 1:

| i | Probe spacing (px) | Probes per axis | Rays per probe | start | length | far point (start + length) |
|---|---|---|---|---|---|---|
| 0 | 1 | 512 x 512 | 4 | 0 | 1.3 | 1.3 |
| 1 | 2 | 256 x 256 | 16 | 1 | 4.2 | 5.2 |
| 2 | 4 | 128 x 128 | 64 | 4 | 16.8 | 20.8 |
| 3 | 8 | 64 x 64 | 256 | 16 | 74.2 | 90.2 |
| 4 | 16 | 32 x 32 | 1024 | 64 | 316.8 | 380.8 |
| 5 | 32 | 16 x 16 | 4096 | 256 | 1306.2 | 1562.2 |

B = 16, N = 4, modifierHack = 4:

| i | Spacing | Probes per axis | Rays per probe | start | length |
|---|---|---|---|---|---|
| 0 | 1 | 512 x 512 | 16 | 0 | 5.2 |
| 1 | 4 | 128 x 128 | 256 | 4 | 79.2 |
| 2 | 16 | 32 x 32 | 4096 | 64 | 1315.2 |
| 3 | 64 | 8 x 8 | 65536 | 1024 | 21263.2 |

B = 64, N = 3, modifierHack = 8:

| i | Spacing | Probes per axis | Rays per probe | start | length |
|---|---|---|---|---|---|
| 0 | 1 | 512 x 512 | 64 | 0 | 10.4 |
| 1 | 8 | 64 x 64 | 4096 | 8 | 657.6 |
| 2 | 64 | 8 x 8 | 262144 | 512 | 42566.4 |

## Presentations and papers listed on the page

- Papers:
  - "Radiance Cascades: A Novel Approach to Calculating Global Illumination [WIP]" (github.com/Raikiri/RadianceCascadesPaper).
  - "Radiance Cascades: A Novel High-Resolution Formal Solution for Multidimensional Non-LTE Radiative Transfer" (arXiv 2408.14425).
  - "Holographic Radiance Cascades for 2D Global Illumination" (arXiv 2505.02041).
- Textual and video:
  - GM Shaders Part One by Yaazarai (mini.gmshaders.com/p/radiance-cascades).
  - GM Shaders Part Two (mini.gmshaders.com/p/radiance-cascades2). No author named on the page.
  - "Exploring a New Approach to Realistic Lighting: Radiance Cascades" by SimonDev (youtu.be/3so7xdZHKxw). SimonDev also provides an open-source implementation and demo (simondevyoutube.github.io/Shaders_RadianceCascades/).
  - "Building Real-Time Global Illumination: Radiance Cascades" by Jason McGhee (jason.today/rc).
- Demos and implementations:
  - fad's Shadertoy (shadertoy.com/view/mtlBzX). The page says it includes some temporal latency due to Shadertoy limitations.
  - "Building Intuition around Radiance Cascades" by tmpvar (tmpvar.com/poc/radiance-cascades).
  - Basic RC on LegitScript (radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/Scaling.ls).
  - HRC implementation, source and explainer by Yaazarai (github.com/Yaazarai/Volumetric-HRC, tree/main).
  - RC for Unity URP by Youssef Af (github.com/Youssef-Afella/UnityURP-RadianceCascades2DGI).
- Utilities:
  - Bilinear and forking fix by MytinoDev (shadertoy.com/view/4clcWn).
  - Kornel's calculator (kornel.ski/radiance) for optimal cascade interval lengths. Inputs: penumbra angle, minimum light size and probe spacing.
  - "Parallel fix" by mxacop (shadertoy.com/view/XcfyDj). The wiki's parallax-fix page links the same Shadertoy.
  - LegitScriptEditor, a WebGL shader editor by tmpvar and Alexander. Links to GitHub-hosted demos through the `?gh=` parameter.
  - HRC ray visualiser in Desmos by fad (desmos.com/calculator/1syt8xa8xl).

# radiance.wiki (community wiki)

| | |
|---|---|
| Author | OrionReed (Orion Reed), the repository owner and the only name in the trusted contributors list. Each page names its own authors. |
| Date | 2026-03-26 (last commit on main, f369b975a) |
| Kind | wiki |
| Link | https://radiance.wiki (source: https://github.com/OrionReed/radiance-wiki) |

A Quartz 4.5.2 wiki with 39 Markdown pages in content/: the home page, the contribution page, 3 papers, 4 talks, 9 guides, 8 implementation pages, 6 technique pages, 4 variant pages and 3 tool pages. Most pages are short notes with links to sources. The home page embeds the same interactive demo as the site, in a slightly different copy of rc.js. The technical content is mainly in the technique, variant, paper and implementation pages.

## Page: content/index.md (home page, embedded demo)

- The repository is OrionReed/radiance-wiki. The live site is radiance.wiki, built with Quartz 4.5.2.
- The page is titled "Radiance Cascades".
- The page describes RC as an approach to real-time global illumination created by Alexander Sannikov at Grinding Gear Games for Path of Exile 2, first presented at ExileCon 2023.
- It gives the penumbra hypothesis as the core idea: resolving light from an object needs high spatial resolution nearby and high angular resolution far away.
- It says each cascade level "doubles the ray count while halving the probe density". The demo code uses a base ray count of 4 by default, which gives 4 times the rays per level (B^(i+1) rays per probe). The page and the code do not match on this point.
- It says RC is geometry-agnostic (constant cost regardless of scene complexity) and noiseless in 2D. Extending RC to 3D is described as an open problem.
- The page embeds the demo with the same controls as the site (see the demo section above).
- Start Here list: SimonDev's video, jason.today, mxcop's fundamentals, and the original paper.
- It links radiance-cascades.com.

## Papers

### holographic-rc (paper: "Holographic Radiance Cascades for 2D Global Illumination")

- Authors: Rouli Freeman, Alexander Sannikov, Adrian Margel (2025). arXiv 2505.02041.
- Introduces HRC: a modified probe structure that keeps high spatial resolution perpendicular to the sampling direction.
- The page says HRC is single-shot, noiseless, and gives results close to a 2D reference solution.
- Performance (RTX 3080 Laptop, as stated): about 1.85 ms at 512 x 512, and about 7.67 ms at 1024 x 1024.
- Main limitation: memory of O(N x X^2). The page does not define N or X. It calls this the main barrier to 3D.
- Implementations: amitabha (Rust/CUDA), Volumetric-HRC, and the Desmos ray visualiser.

### osborne-sannikov-2024 ("Radiance Cascades: Multidimensional Non-LTE Radiative Transfer")

- Authors: Christopher M. J. Osborne and Alexander Sannikov (2024). arXiv 2408.14425. Published in RAS Techniques and Instruments (2025).
- Applies RC to astrophysical radiative transfer, specifically solar prominence modelling.
- Contains a formal treatment of the bilinear fix (Appendix A) and the parallax fix (Figure 8).
- Describes the DexRT implementation.

### sannikov-original ("Radiance Cascades: A Novel Approach to Calculating Global Illumination")

- Author: Alexander Sannikov. Status: WIP / preprint, licence CC BY-ND 3.0.
- Source: github.com/Raikiri/RadianceCascadesPaper. PDF on Google Drive.
- Covers the penumbra hypothesis, the cascade data structure, flatland and 3D formulations, and interval extension for 3D grids.
- States that memory for all cascades in 2D is bounded by 2 times the memory of cascade 0.
- Covers the predecessor techniques HSSVGI and hierarchical screen-space shadow cascades, presented at ExileCon 2019.

## Talks

### exilecon-2023 ("ExileCon 2023: Rendering Path of Exile 2")

- Speaker: Alexander Sannikov, November 2023. Video: youtube.com/watch?v=TrHHTQqmAaM.
- First public presentation of RC. Covers other PoE2 rendering work and the predecessor techniques.

### goobley-slides ("Radiance Cascades 3D: DexRT Presentation Slides")

- Speaker: Christopher Osborne (Goobley). Slides: goobley.github.io/RadianceCascadesSlides/.
- Topics: GPU-first design using Kokkos, atmospheric sparsity, mipmapping for upper cascades, Morton-order storage (inspired by OpenVDB), and about 40 times the performance per watt of GPU versus CPU.
- The page says the astrophysical context differs from game rendering, but the storage and mipmapping techniques transfer.

### sannikov-3d-demo ("Alexander Sannikov: 3D RC Implementation Demo")

- Short video demo of RC in 3D (youtube.com/watch?v=N6RP3r1M9g4). The page says it is light on technical detail.

### simondev

- Video: youtu.be/3so7xdZHKxw. Live demo: simondevyoutube.github.io/Shaders_RadianceCascades/ (open-source JavaScript).
- The page calls it a good starting point for newcomers.

## Guides

### 80lv-overview ("80 Level: Radiance Cascades Overview")

- News article, November 2023: 80.lv/articles/radiance-cascades-new-approach-to-calculating-global-illumination.
- Demo video by Mytino. The page reports 0.3 ms per frame on a GTX 970, with no denoising.

### bevy-overview ("This Week in Bevy: Radiance Cascades")

- Bevy and Rust perspective (thisweekinbevy.com, July 2024).
- Quotes the issue: "3d Radiance Cascades don't seem to work out as well as 2d."
- Notes JMS55's Solari post (linked URL dated 2025-09-20). Solari tried RC in 3D, found the artifacts and costs hard to manage, and moved to ReSTIR.

### gmshaders-part1 ("GM Shaders: Radiance Cascades, Part One")

- Author: Yaazarai (Alex). mini.gmshaders.com/p/radiance-cascades.
- Covers the penumbra hypothesis, cascade structure, memory layout, merging, and the skybox integral. Mentions Mytino's volumetrics work.
- Accompanied by a GameMaker implementation.

### gmshaders-part2 ("GM Shaders: Radiance Cascades 2, Part Two")

- Author: Yaazarai (Alex). mini.gmshaders.com/p/radiance-cascades2.
- Covers pre-averaging, direction-first probes, and a single-shader implementation of under 100 lines.
- The updated GameMaker implementation has bilinear-fix and nearest-fix branches.

### jason-today ("Building Real-Time Global Illumination")

- Author: Jason McGhee. Interactive walkthrough at jason.today/rc, with editable canvases.
- Builds an RC implementation step by step. Covers sRGB and linear handling, and ringing artifacts.
- Part 1 (jason.today/gi) covers raymarching, SDFs and JFA.
- A Godot branch based on this guide exists (see godot).

### mxcop-fundamentals ("Fundamentals of Radiance Cascades")

- Author: Max (mxcop). m4xc.dev/articles/fundamental-rc/. HN discussion linked.
- Covers angular and spatial resolution observations, cascade structure, interval casting, and merging. Has diagrams.

### otavio-opengl ("Radiance Cascades For 2D GI")

- Author: Otavio Peixoto. Custom OpenGL engine implementation. Shows the cascade hierarchy memory layout and merging.

### tlegoc-vulkan ("Radiance Cascade GI in Vulkan")

- Author: Théo Le Goc. Blog: tlegoc.github.io/blogs/radiance-cascade/. Repo: github.com/tlegoc/RadianceCascadesGIVulkan.
- Covers cascade resolution choices, texture sizing, and separating screen resolution from cascade resolution.
- Implementation: 2D compute shaders in Vulkan.

### tmpvar-playground ("Building Intuition around Radiance Cascades")

- Author: tmpvar. 2D playground (WebGPU, Chrome or Edge): tmpvar.com/poc/radiance-cascades/. 3D playground: tmpvar.com/poc/radiance-cascades-3d/.
- Implementation notes (October 2023): tmpvar.com/articles/implementing-radiance-cascades/.
- The 2D playground has controls for probe spacing, ray counts, branching factors, cascade levels and interval radius. It shows interval visualisations, ray distribution and probe interpolation.
- The 3D playground compares probe distributions: cube face subdivision, golden spiral and others.
- The notes describe difficulties, especially 3D memory requirements.

## Implementations

### amida

- Author: entropylost. github.com/entropylost/amida (Rust/CUDA, NVIDIA only).
- Features: bilinear fix, multiple bounces, subsurface scattering, volumetrics. Builds worlds from palette-mapped input images.
- The same author made the HRC reference implementation amitabha and the RC-guided NEE pathtracer.

### bevy

- kornelski/bevy_flatland_radiance_cascades: uses pre-averaging and an improved storage layout.
- nixonyh/bevy_radiance_cascades.
- The page also includes the Solari note (JMS55 tried RC in 3D and found artifacts and performance costs difficult, then moved to ReSTIR). The page calls this one data point, not a definitive verdict on 3D RC.

### dexrt

- Goobley/DexRT (C++20, Apache-2.0).
- RC applied to non-LTE radiative transfer for solar prominences and spectral lines.
- Uses Kokkos for GPU portability (migrated from YAKL in v0.4.0). Uses mipmapping for upper cascades, sparse VDB-like storage, and Morton order. v0.5.0 added 3D support.

### gamemaker

- Yaazarai/RadianceCascades: accompanies GM Shaders Part One.
- Yaazarai/GMShaders-Radiance-Cascades: accompanies Part Two, with bilinear-fix and nearest-fix branches.
- The page says pre-averaging and direction-first probes were first prototyped here.
- Yaazarai also made Volumetric-HRC.

### godot ("Radiance Cascades, Godot 4.3")

- Sohojoe/radiance-cascades-godot.
- Branches listed:
  - mix-Yaazarai-and-jason: based on GM Shaders Part Two and jason.today. Uses compute shaders.
  - shadertoy-port-suslik: a port of the RC Experimental Testbed Shadertoy.
  - jason-today-gi-pt1: based on jason.today.

### other (other implementations and demos)

- Web: radiance-cascades.com (2D playground with fix toggles); SimonDev's demo; LegitScript basic RC; a futureengine2 gist on making RC independent of the ray-tracing method.
- Native: tlegoc Vulkan compute shaders; Hybrid46's C# with Raylib and OpenGL 3.3+; amitabha (HRC, Rust/CUDA); Volumetric-HRC; Otavio's OpenGL.

### shadertoys

- fad's Shadertoy (September 2023, shadertoy.com/view/mtlBzX) is the first public implementation. Includes the skybox integral. Merging is temporal because of Shadertoy buffer limits.
- Fork tree: fad (Sep 2023), then Quinchilion (Nov 2023), then Suslik (Apr 2024), then RC Experimental Testbed (Suslik, Apr 2024).
- Notable Shadertoys:
  - RC V2 / bilinear fix (MytinoDev, 4clcWn).
  - Parallax fix (mxacop, XcfyDj).
  - RC / gear fix (kornelski, XffcD7).
  - Holographic RC (Suslik). Linked as a Shadertoy tag search.
  - Radiance Cascades 3D (Suslik, X3XfRM).
  - Analytic Direct Illumination (Mathis, NttSW7). Sky integral formula.
  - RC Diagram (Mytino). Linked as a tag search.
  - RC - Screen Space Probes (Mathis). Linked as a tag search.

### unity-urp

- Youssef-Afella/UnityURP-RadianceCascades2DGI. Language: HLSL.

## Techniques (fixes and optimizations)

### bilinear-fix

- Addresses interpolation artifacts during merging. The four bilinearly sampled upper-cascade probes have spatial offsets, which cause discontinuities at probe boundaries.
- Fix: cast 4 times the rays (one reprojected to each bilinear upper probe) before merging, so the merged rays are continuous.
- Cost: 4 times the ray cost.
- Formal treatment: Osborne and Sannikov 2024, Appendix A.
- Implementation: GM Shaders repo, bilinear-fix branch.
- Images compare "vanilla" with the fix (Yaazarai's repo).

### nearest-fix

- Cheaper alternative to the bilinear fix. Reprojects to only the nearest upper-cascade bilinear probe (cN+1), instead of all four.
- Tradeoff: some pixelation, because each 2 x 2 group of cN probes shares one cN+1 probe. The page says the cost is much lower than the bilinear fix.
- Implementation: GM Shaders repo, nearest-fix branch.

### parallax-fix

- Corrects energy duplication from the spatial offset between probes of different cascade levels. The duplicate energy causes ringing near light sources.
- Fix: reproject sampling rays to the positions of the bilinearly sampled probes.
- Different from the bilinear fix. The bilinear fix addresses interpolation discontinuities. The parallax fix addresses duplicate energy.
- Formal treatment: Osborne and Sannikov 2024, Figure 8. Shadertoy: XcfyDj (mxacop).

### pre-averaging

- Merging averages the four nearest upper-cascade probes' rays. These rays can be averaged before storing.
- Cast 4 rays, store one averaged result.
- Memory: 75% reduction. Texture lookups during merging: from 16 to 4.
- Combined with direction-first probes, gives an RC implementation under 100 lines of shader code (GM Shaders Part Two).

### direction-first-probes

- Alternative memory layout: rays grouped by direction, not by probe position.
- Effect: reads for the same direction across neighbouring probes become contiguous, which improves texture cache coherence during merging.
- Also allows hardware bilinear interpolation during merging.
- Described in GM Shaders Part Two.

### skybox-integral

- Merges the sky integral into the outermost cascade, which covers the farthest intervals.
- The low probe density of that cascade is acceptable because skyboxes have little spatial variation.
- Does not affect occlusion.
- Sky integral formula by Mathis (shadertoy.com/view/NttSW7). First included in fad's Shadertoy.

## Variants

### holographic-rc

- Modified probe structure that keeps high spatial resolution perpendicular to the sampling direction.
- Resolves hard shadows and volumetrics at similar cost to standard RC.
- Main limitation: O(N x X^2) memory (N and X are not defined on the page).
- "Radial HRC" was an earlier community test of whether small perpendicular probe spacing could resolve sharp shadows.
- Implementations: amitabha (Rust/CUDA), Volumetric-HRC, Suslik's Shadertoy (listed as a tag search).

### rc-guided-nee

- Uses RC to guide next-event estimation in a pathtracer. RC augments ray tracing rather than replacing it.
- Repo: entropylost/vlam (Rust).

### surfel-rc (3D)

- Experimental 3D approach with surfel probes (surfels), not screen-space or volumetric grids.
- Repo: mxcop/src-dgi.
- Two parts: surfel maintenance (spawning and recycling as the camera moves), and radiance gathering (probe rays traced, then cascades merged from top to bottom).
- Surfels avoid some volumetric memory problems, but raise questions about distribution, coverage gaps and temporal stability.
- The page calls it research-stage work.

### uv-space-3d (3D)

- Suslik's Shadertoy (November 2024, shadertoy.com/view/X3XfRM). A UV-space implementation with multi-bounce lighting and BRDF integration.
- Works in the texture coordinate space of surfaces, not in screen or world space.
- Merging is temporal because of Shadertoy limits. The page says this causes some lag and flicker, and that a proper implementation could likely avoid it.
- The page calls it a proof of concept from "the original RC author", but attributes the Shadertoy to Suslik. The two statements are not reconciled on the page.

## Tools

### hrc-ray-visualiser

- By fad. Desmos calculator 1syt8xa8xl. Interactive ray visualisation for holographic RC.

### interval-calculator ("Cascade Interval Length Calculator")

- By Kornel (kornelski). kornel.ski/radiance.
- Computes optimal cascade interval lengths from penumbra angle, minimum light size and probe spacing.
- Kornel also maintains a Bevy RC implementation.

### legitscript (LegitScriptEditor)

- By tmpvar and Alexander Sannikov. radiance-cascades.github.io/LegitScriptEditor/.
- WebGL shader editor for arbitrary multi-pass setups. No backend dependency.
- Demos can be linked from GitHub with a `?gh=` parameter, for example `?gh=Raikiri/LegitCascades/Scaling.ls`.

## Links found

- https://arxiv.org/abs/2408.14425 (Osborne and Sannikov 2024, multidimensional non-LTE radiative transfer)
- https://academic.oup.com/rasti/article/7929002 (RAS Techniques and Instruments publication of the 2024 paper)
- https://arxiv.org/abs/2505.02041 (Holographic RC paper)
- https://www.emergentmind.com/papers/2505.02041 (summary of the HRC paper)
- https://github.com/Raikiri/RadianceCascadesPaper (original paper source, WIP)
- https://drive.google.com/file/d/1L6v1_7HY2X-LV3Ofb6oyTIxgEaP4LOI6/view (original paper PDF)
- https://www.youtube.com/watch?v=TrHHTQqmAaM (ExileCon 2023 talk)
- https://www.youtube.com/watch?v=N6RP3r1M9g4 (Sannikov 3D RC demo video)
- https://youtu.be/3so7xdZHKxw (SimonDev video)
- https://www.youtube.com/@simondev758 (SimonDev channel)
- https://simondevyoutube.github.io/Shaders_RadianceCascades/ (SimonDev open-source JavaScript demo)
- https://goobley.github.io/RadianceCascadesSlides/ (DexRT presentation slides)
- https://mini.gmshaders.com/p/radiance-cascades (GM Shaders Part One)
- https://mini.gmshaders.com/p/radiance-cascades2 (GM Shaders Part Two)
- https://jason.today/rc (jason.today walkthrough)
- https://jason.today/gi (jason.today Part 1, foundations)
- https://jason.today (Jason McGhee site)
- https://m4xc.dev/articles/fundamental-rc/ (mxcop fundamentals)
- https://news.ycombinator.com/item?id=41957008 (discussion of the mxcop article)
- https://80.lv/articles/radiance-cascades-new-approach-to-calculating-global-illumination (80.lv news, November 2023)
- https://thisweekinbevy.com/issue/2024-07-22-bevy-jam-5-radiance-cascades-and-calculators-in-many-ui-kits (This Week in Bevy, July 2024)
- https://jms55.github.io/posts/2025-09-20-solari-bevy-0-17/ (JMS55, Solari and RC in 3D)
- https://otaviopeixoto1.github.io/portfolio/2DRadianceCascades/ (Otavio Peixoto, OpenGL)
- https://tlegoc.github.io/blogs/radiance-cascade/ (Théo Le Goc, Vulkan blog)
- https://tmpvar.com/poc/radiance-cascades (tmpvar 2D playground, as linked from radiance-cascades.com)
- https://tmpvar.com/poc/radiance-cascades/ (tmpvar 2D playground, as linked from the wiki)
- https://tmpvar.com/poc/radiance-cascades-3d/ (tmpvar 3D playground)
- https://tmpvar.com/articles/implementing-radiance-cascades/ (tmpvar implementation notes, October 2023)
- https://radiance-cascades.com/ (community site)
- https://radiance.wiki (community wiki)
- https://github.com/radiance-cascades (site GitHub organisation)
- https://github.com/radiance-cascades/radiance-cascades.com (site source repository)
- https://github.com/OrionReed/radiance-wiki (wiki source repository)
- https://github.com/Sohojoe/radiance-cascades-godot (Godot implementation)
- https://github.com/Yaazarai/RadianceCascades (GameMaker, accompanies GM Shaders Part One)
- https://github.com/Yaazarai/GMShaders-Radiance-Cascades (GameMaker, accompanies Part Two, bilinear and nearest branches)
- https://github.com/Yaazarai/Volumetric-HRC (volumetric HRC)
- https://github.com/Yaazarai/Volumetric-HRC/tree/main (volumetric HRC, as linked from the site)
- https://github.com/Youssef-Afella/UnityURP-RadianceCascades2DGI (Unity URP implementation)
- https://github.com/entropylost/amida (2D RC with bounces and volumetrics, Rust/CUDA)
- https://github.com/entropylost/amitabha (HRC reference implementation, Rust/CUDA)
- https://github.com/entropylost/vlam (RC-guided NEE pathtracer, Rust)
- https://github.com/kornelski/bevy_flatland_radiance_cascades (Bevy implementation with pre-averaging)
- https://github.com/nixonyh/bevy_radiance_cascades (Bevy implementation)
- https://github.com/Goobley/DexRT (DexRT, C++20)
- https://github.com/tlegoc/RadianceCascadesGIVulkan (Vulkan implementation)
- https://github.com/Hybrid46/RadianceCascade2DGlobalIllumination (C# with Raylib)
- https://github.com/mxcop/src-dgi (surfel RC)
- https://gist.github.com/futureengine2/7c8fbc6fefce1818ff1edcd4d7e7bfcf (gist on making RC independent of the ray-tracing method)
- https://www.shadertoy.com/view/mtlBzX (fad's original Shadertoy)
- https://www.shadertoy.com/view/4clcWn (RC V2, bilinear fix, MytinoDev)
- https://www.shadertoy.com/view/XcfyDj (parallax fix, mxacop)
- https://www.shadertoy.com/view/XffcD7 (RC / gear fix, kornelski)
- https://www.shadertoy.com/view/X3XfRM (UV-space RC 3D, Suslik)
- https://www.shadertoy.com/view/NttSW7 (analytic direct illumination, sky integral formula, Mathis)
- https://www.shadertoy.com/results?query=tag%3Dcascade (Shadertoy tag search, linked for Holographic RC, RC Diagram and RC Screen Space Probes)
- https://www.desmos.com/calculator/1syt8xa8xl (HRC ray visualiser, fad)
- https://kornel.ski/radiance (cascade interval length calculator)
- https://radiance-cascades.github.io/LegitScriptEditor/ (LegitScriptEditor)
- https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/Scaling.ls (basic RC on LegitScript)
