# Assorted 2D RC experiments

Small 2D projects that each add one idea or one warning. None reports timings except where noted. The Gigi graph is covered in [2026_gigi_and_volume_rc_repositories.md](2026_gigi_and_volume_rc_repositories.md).

| Repository | Language | License | Last commit | Notable for |
|---|---|---|---|---|
| https://github.com/s-macke/CoreCascade | Go, CPU | MIT | 2025-10 | CPU reference with a path tracer, volumetric SDF scenes, bilinear fix |
| https://github.com/mebyz/adaptive-radiance-cascades | JS, WGSL | CC BY 4.0 | 2026-01 | skipping rays in upper cascades |
| https://github.com/dimforge/kiss3d (`gi2d`) | Rust, WGSL | BSD-3 | 2026-10 | probe spacing and direction count set separately |
| https://github.com/RandyGaul/cute_framework (`samples/hrc.c`) | C | zlib | 2026-10 | HRC with dense directions and bounce feedback |
| https://github.com/folk-js/folkjs (`folk-holographic-rc.ts`) | TS, WGSL | MIT | 2026-05 | HRC with a sky prefix table and RGB9E5 storage |
| https://github.com/simondevyoutube/Shaders_RadianceCascades | JS, GLSL | MIT | 2024-07 | the SimonDev video's demo |
| https://github.com/tlegoc/RadianceCascadesGIVulkan | C++, Slang | none | 2024-11 | Vulkan compute; known merge bugs |
| https://github.com/Hybrid46/RadianceCascade2DGlobalIllumination | C#, Raylib | MIT | 2026-07 | port of Youssef-Afella with sky and reflectivity |
| https://gist.github.com/futureengine2/7c8fbc6fefce1818ff1edcd4d7e7bfcf | C, GLSL | none | 2023-10 | rays ×2 per cascade, DDA on a bitmap |
| https://github.com/qJay44/radiance-cascades-2d | C++20, OpenGL 4.6 | none | 2026-06 | HDR cascades, hardware-bilinear merge |
| https://github.com/tsukinousagi18/radiance-cascades-2D | C, OpenGL | MIT | 2025-12 | overlapping intervals, analytic sun and sky |

## CoreCascade

A CPU program in Go that renders one image per run with plain RC, RC with the bilinear fix, light propagation volumes, or a path tracer, which makes it a ready comparison harness. The main branch has 2D and an experimental 3D renderer, light propagation volumes, directional emitters and float32 storage. The `absorption` branch is 2D only and float64; it carries unused OKLab conversions and a README line about light propagation with no code behind it. The absorption model, cascade geometry and merge are the same in both. The README says the method would run in real time on a GPU, without a measurement.

- **Media:** a material has an emission `E` per unit path length, one scalar absorption σ, and a diffuse tint used only for re-emission. Each step of length `s` adds `vis·(E/σ)(1 − e^(−σs))` and multiplies `vis` by `e^(−σs)`; with σ ≤ 10⁻⁴ it adds `vis·E·s`. The march stops when `vis < 10⁻⁴`. There are no surfaces: walls are strong absorbers, and emitters are volumes whose brightness grows with the path length inside them.
- **Scenes:** SDF shapes are sphere-traced with `step = max(|d|, 0.01)`, integrating only inside shapes, for at most 128 steps. Grid scenes take fixed steps of `2/W` with nearest samples. On the absorption branch the SDF march adds its last step whole even when it overruns `tmax`, and the grid march does not clip to the scene bounds; main clips both. Both branches stop silently after 128 steps.
- **Geometry:** the scene spans [−1, 1]², cascade 0 spacing is `2/W` and its interval is half of that, `L0 = 1/W`. The count is `ceil(log4(2√2/L0)) + 1`; directions grow ×4 from 4 and spacing ×2. Grids have `N_i = ceil(N_(i−1)/2) + 1` probes per axis, with the first probe moved back a quarter of the upper spacing each level, so upper probes cover the image edges. Intervals are contiguous, `[L0·4^(i−1), L0·4^i]`. The README says most implementations zero the probes that fall outside the image, which is usually enough.
- **Merge:** each interval stores color and transmittance; merging is `color += far.color·near.vis` and `vis *= far.vis`, so absorption carries through every level. Four far directions are averaged with bilinear weights `0.25 + 0.5·(x & 1)`. The bilinear fix traces from `probe + dir·TStart` to each far probe's `far + dir·TEnd_near`.
- **Second pass:** the first pass's fluence times diffuse color becomes emission for a second render, giving one more bounce. Nothing keeps diffuse at or below 1, and the absorption scene's absorber has diffuse 3 on the branch (black on main).
- **Default size (derived from the code):** at 800×800 there are 7 traced cascades plus an eighth that is never traced. Grids are 800, 401, 202, 102, 52, 27, 15 and 9 probes wide, and intervals run from [0, 0.00125] to [1.28, 5.12] scene units. The traced cascades hold 19.8 M probe directions, so plain RC traces 19.8 M rays and the bilinear fix 79.4 M. At 32 B per entry (float64) all cascades take 805 MB, or 403 MB in float32, of which the untraced last level is 170 MB.
- **Bugs found by reading:** the bilinear fix checks only whether the near cascade is the last, so cascade 6 traces toward cascade 7 probes and merges their never-computed values (black, visibility 1), adding rays and no light. Merged visibility starts at 1 and then sums four directions before dividing by 4, giving `(1 + Σv)/4`, which is 1.25 in empty space; stored visibility never reaches color in the current code, so images are unaffected. The path tracer runs 101 samples and divides by 100. Output is Reinhard with a 1/2.2 power, not the sRGB curve. A comment calling visibility a hit flag is stale.

## Adaptive ray skipping (mebyz)

Upper cascades trace only every second or fourth ray of each pre-averaged group and average the traced ones. Fixed modes cut 10 to 40% of rays at 36 to 68 dB PSNR against the full version; an auto mode picks a level from the mean plus standard deviation of cascade 1 luminance at 8 probes, averaging about 19% fewer rays at over 50 dB across 50 test scenes. The far cascades carry low-frequency light, so they tolerate skipping.

The work is a WebGPU page with a paper-style README (Emmanuel Botros Youssef, 2026, CC BY 4.0; repository mebyz/adaptive-radiance-cascades). The demo runs 5 cascades at 512² with 256² probes at cascade 0 and ×4 directions per level; the code gives cascade 0 16 directions, while the README says 4.

- **Skipping:** from a start level up, the merge steps over direction indices by `1 << min(level − start + 1, maxSkipBits)` and copies each traced result into the skipped directions. The README's pseudocode caps the factor (`min(2^bits, max_skip)`) while the shader caps the bits; the published numbers match the shader.
- **Modes:** L5 (start 4, at most 2 skip bits, about 10% fewer rays), L4 (start 3, 1 bit, about 17%), L3 (start 3, 2 bits, about 25%) and L2 (about 40%). The auto mode computes `score = mean + stddev` of the angular radiance at level 1 and picks L5 below 0.45, L4 below 1.00 and L3 otherwise. L2 is never chosen because no signal predicted when it is safe. The page labels L3 conservative and L5 ultra-safe, while the README calls L5 conservative and L3 aggressive.

| Fixed mode | Fewer rays | PSNR range (dB) | Mean PSNR (dB) | All 50 scenes above 50 dB |
|---|---|---|---|---|
| L5 | about 10% | 56.7 to 67.6 | 61.8 | yes |
| L4 | about 17% | 49.9 to 60.6 | 55.2 | no |
| L3 | about 25% | 47.3 to 59.5 | 53.7 | no |
| L2 | about 40% | 35.9 to 52.0 | 43.6 | no |

- **Predictors of L2 PSNR** (correlation, 95% interval): light count 0.81 [0.69, 0.89], mean 0.77, mean plus standard deviation 0.73 (the chosen signal), standard deviation 0.69, nonzero ratio 0.20 (not significant), peak over average −0.60, and the angular bandwidth holding 90% of the energy −0.68, which the README calls a "bandwidth paradox".
- The scenes are synthetic (1 to 50 lights, 1 to 8 occluders), and the thresholds were fitted on the same 50 scenes that then show the ">50 dB" result, so the guarantee is in-sample. The 19% is a ray count, with no GPU or timing given; the author lists 2D only and possible recalibration elsewhere as limits.

## kiss3d decoupled cascades

Each cascade texel is one (probe, direction) pair, and the tile edge per probe (`4·2^c`) and probe spacing (`2·2^c` field pixels) are chosen independently while every level stays the size of the screen. Intervals are `base·(4^c − 1)/3` to `base·(4^(c+1) − 1)/3`. The jump-flood field is unsigned, so the SDF is biased outward by two field pixels to stop grazing rays tunneling through thin occluders. The engine ships a brute-force march with 8 rays per pixel and temporal blending as the default, and RC as an option.

## HRC samples (cute_framework, folkjs)

Two independent ports of [HRC](2025_freeman_holographic_radiance_cascades.md):

- **Checkerboard:** the paper's ray offsets `(2^i, 2k − 2^i)` are always even, so odd and even rows never meet. cute_framework uses dense offsets `(2^i, k − 2^i)` with `2^(i+1) + 1` directions, which couples every row and doubles angular resolution; folkjs keeps the paper's form and cancels the pattern with an opacity-gated `[0 1 0; 1 4 1; 0 1 0]` blur.
- **Low levels:** building levels 0 to 2 by merging short rays gave Manhattan-shaped artifacts, so they are traced directly through raw scene texels. Mip-prefiltered scene input thinned 2 px walls enough to leak about 13% per crossing and made moving emitters flicker.
- **Bounces:** last frame's fluence times albedo/2π is added back as emission. Wall probes have zero fluence inside solids, so folkjs takes the bounce from neighboring probes outside the wall, weighted by their transparency.
- **Sky:** folkjs integrates a 256-entry sky table into a prefix-sum table per direction row, so any merge bin's sky light is one subtraction.
- **Storage:** emission is encoded as `(e/16)^(1/2.2)` in 8-bit canvases (a plain `/16` lands 28× too dark after the curve); merged fluence is stored as RGB9E5.

folkjs in more detail (`folk-holographic-rc.ts`, a WebGPU custom element):

- **Grid:** `probeCount` 1024 sets the probes along the longer side, so 1920×1080 gets 1024×576 probes 1.875 px apart and `ceil(log2(1024))` = 10 cascades. Level `L` has `ceil(pc/2^L)` probes per row with `2^L + 1` rays each. Each frame runs seed, extend and merge for the four directions and accumulates level 0 into an RGB9E5 fluence buffer.
- **Seed:** transmittance `(1 − a)^spacing` per probe and radiance `(rgb + bounce)·(1 − T)`, packed as f16.
- **Extension:** ray `r` at level `L` joins `lower = floor(r/2)` and `upper = floor((r + 1)/2)` from probes `2p` and `2p + 1` and averages the two crossings; for even `r` the two coincide, so the result is the exact composition. A comment describes a parity branch the code does not need.
- **Merge:** cone weights are exact arc widths `atan2(2s − N + 2, N) − atan2(2s − N, N)` with `N = 2^(L+1)`. Odd probes add `ray·w + far·T`; even probes average that two-step chain with the coarse level's merged value, which a comment calls a Richardson average though it is a plain 50/50 mean. The top level and out-of-bounds probes fall back to the sky, whose prefix table is built from samples at cone midpoints, so it integrates a piecewise-constant sky.
- **Bounce and output:** bounce is `fluence·albedo/2π` from the exterior cardinal neighbours where a probe is opaque, read by the next frame's seed (one frame of latency). The blit adds `fluence/2π·(1 − opacity)` to the scene color, then applies a fitted ACES curve, a 1/2.2 power and ±1/255 triangular dither. A debug mode shows a path-traced reference and its difference from HRC; per-pass GPU timestamps are shown in the element, and the repository records no numbers.

## SimonDev demo

Plain RC, 7 levels, 4 directions per cascade 0 probe and ×4 per level, intervals `(4^L − 1)/3` to `(4^(L+1) − 1)/3` scene pixels, every level the same texture size (1820×1024). The upper lookup averages four angular taps at `index − 1 … index + 2`, which is centered half a bin off the child range `4k … 4k+3`; several helpers are marked "fixme". Probes outside the texture return `(0, 0, 0, 0)`, which reads as opaque and stops the merge.

- The scene is painted with a lazy-brush pen into a 1920×1080 distance field whose texels hold color and distance; the march sphere-traces up to 64 steps and hits below 0.1 px, returning alpha 0 for a hit and 1 for an escape. The cascade texture is `1024·16/9` = 1820.44 texels wide, a non-integer size.
- The level count comes from a loop that stops at the first level whose interval end passes the screen diagonal (5461 > 2203 px gives 7 levels), overriding an earlier formula. Every level renders into the same target, so the rays per level are constant.
- Probe `P`, angle `a` sits at texel `(dims·Px + a mod dims, dims·Py + floor(a/dims))` with `dims = 2^(n+1)`, and the angle is `a·2π/dims² − π/dims²`, a half step back. The bilinear probe set is chosen from `pixel − dims/2` while its weights are measured from the centers `dims·k + (dims − 1)/2`, a half-texel mismatch that wraps the fraction in a narrow band at probe boundaries (found by reading). A 13-tap merge option calls a function that does not exist.
- The radiance field averages cascade 0's 4 directions per probe with no cosine term; the composite multiplies a background mixed in Oklab by the radiance and applies ACES with a 1/2.2 power.

## Bugs worth recognizing

- **Weights:** tlegoc's merge assigns three of four bilinear corners the wrong weights, and its `output += final·output.a` also changes alpha. Skipped edge taps still count toward the divisor of 4, darkening edges.
- **Negative indices:** `index − 1` at index 0 wraps to the previous probe block when `%` keeps the sign (tlegoc, SimonDev).
- **Emitter rays:** Hybrid46 keeps transmittance 1 on emitter hits, so the upper cascade is added on top of the emitter.
- **8-bit cascades:** the futureengine2 gist and Hybrid46 store cascades in RGBA8, which clips the sun and bright emitters.
- **Shifted sky bins:** Hybrid46 and futureengine2 integrate the sky from the ray's center angle one bin forward, so each bin sits half a bin off the ray it belongs to.

## futureengine2 gist

Two files: `gi.c` dispatches through the author's unreleased GPU framework, so the gist does not run on its own, and `gi.glsl` holds the algorithm, unchanged since the first revision (2023-10-01). The scene is a bitmap where black occludes, white is air and any other color emits, following Sannikov's 2D demo.

- **Parameters:** 7 cascades; cascade 0 has 1 px spacing and 4 rays; the probe lattice covers twice the window (`2w` probes per axis); cascades are RGBA8 with nearest filtering, in two ping-pong textures.
- **Cascade `ci`:** spacing `2^ci`, `4·2^ci` rays (rays only double per level), interval `[0.5·4^(ci−1), 0.5·4^ci]` px with cascade 0 at `[0, 0.5]`, ray angle `(r + 0.5)·2π/rn`. Texels per level halve, so the whole stack is twice cascade 0; the code comment notes that a ray branching factor above 2 gives that up.
- **Merge:** on a miss, the upper probe is `(xi + 1)/2` with explicit four-probe weights of 0.75 and 0.25 by parity, and the two upper rays `2r` and `2r + 1` are averaged.
- **Tracer:** an Amanatides–Woo walk over bitmap texels where the first non-white texel is the hit, returned with alpha 1 (transparency is a TODO). The walk initializes `tMax = (x0 − floor(x0))/dx`, which measures to the near cell boundary for positive steps and has the wrong sign for negative ones. For `x0 = 0.25` moving in +x, the first crossing comes at 0.25 instead of 0.75, so diagonal rays visit cells out of order and can step past a one-texel occluder (found by reading, not by running).
- **Sky and output:** the top cascade adds the sky integrated over `[α, α + 2π/rn]` with sky color (0.2, 0.5, 1.0), a sun of (1, 0.7, 0.1)·10 at 2.0 rad with sharpness 64, all divided by 6. The final pass averages the 4 rays of the nearest cascade 0 probe and applies an ACES-style curve.
- **Tracer independence:** in the gist's comments (March 2024) the author argues that RC does not depend on how rays are traced. Voxel cone tracing, SDF sphere tracing or any other tracer fits, and cost stops depending on geometry count when the tracer does, as with G-buffer tracing or precomputed cones. RC is a way to lay out and combine probe results, not a ray-tracing method.

## Hybrid46 (Raylib port)

A C# port of Youssef-Afella's Unity project, with GLSL passes for jump flood, distance field, cascades, blur and merge. Each frame draws a color and an emissive target, seeds the jump flood from any non-zero texel, builds the distance field, runs six cascade passes top-down through two ping-pong targets, blurs the result 3×3 (radius 1.5) and adds it to the scene, clamped to 1.

- **Fixed parameters:** 6 cascades at any resolution; ray range 2.0 in units of screen height (1800 px at 1200×900); cascade textures padded to multiples of 64 (1216×960). Every target is 8-bit RGBA, with the float formats commented out; screen targets use point filtering and cascades bilinear.
- **Layout:** level L has 4^L blocks of 2^L × 2^L texels, and each texel casts 4 rays, so a probe has `4^(L+1)` directions at `(i + 0.5)·2π/4^(L+1)` and every level casts `4·W·H` rays. The README says ray counts fall quadratically per level, which the code does not do.
- **Intervals:** level L spans `[(4^L − 1), (4^(L+1) − 1)]/(4^N − 1)` of the ray range, contiguous with ratio 4. At 1200×900, level 0 covers about 0 to 1.3 px and level 5 about 450 to 1800 px.
- **March:** 32 sphere-tracing steps, hit below 0.001 UV. The distance field is a UV-space distance clamped to 1 and packed into two 8-bit channels; the marcher scales directions by the aspect ratio, so steps on wide windows are safe but short.
- **Jump flood:** 11 steps that start at half the screen height (450 px) instead of half the larger side, so the reach (about 900 px) falls short of the 1200 px width. Texels with no seed store (0, 0) and later read a finite distance to the UV origin instead of "far" (from reading).
- **Merge:** a ray with non-zero alpha (a miss, an emitter, or a reflective surface) adds one bilinear tap from the level above at `coordsInBlock·0.5 + 0.25`, clamped half a texel inside the block, times its alpha. A surface hit returns its albedo with alpha equal to the reflectivity, which defaults to 0, so every wall adds its own albedo as if it glowed.
- **Sky:** top-level misses add an analytic integral taken from the Analytic Direct Illumination Shadertoy: sky `∫(1 + 0.5 sin t)` plus a Lorentzian sun `∫1/(1 + 64(S − t)²)`, times 0.16, then an unexplained factor 2.
- **Defects:** the loader opens `shaders/Merge.fs` while the file is `merge.fs`, which fails on the case-sensitive file systems the README claims to support; `packing.glsl` is never included, since each shader carries its own copy; the README promises 8 debug views (7 are drawn) and random or cycling paint colors (absent).
- **Timing:** the README's 60 fps at 1200×900 on a GTX 1660 equals the app's frame cap, so it is not a measurement.

## qJay44 (OpenGL 4.6)

C++20 with GLFW and ImGui. A painted pixel is both occluder and emitter, its color being its radiance; there is no separate emissive map and no sky. The seed and jump-flood targets are RG16F, the distance field R16F, and the cascades RGBA16F.

- **Jump flood:** offsets `2^(P−1−i)` px with `P = ceil(log2(max(W, H)))`, the standard schedule, which reaches the whole window. The distance is measured in UV, so it is anisotropic on non-square windows.
- **Cascades:** count `ceil(log(diagonal)/log(base)) + 1`, 7 at 1200×720, computed at startup and not recomputed when the GUI changes the base ray count. Level i has spacing `2^i` px, probes at `(p + 0.5)·spacing`, `base^(i+1)` directions with 4 rays per texel at `(index + 0.5)·2π/count` (a comment calls the offset "0.5 radians"), and intervals `[0, 1]` px at level 0 and `[4^(i−1), 4^i]` above, scaled by the shorter side.
- **March and merge:** distance-field steps until the ray leaves the screen, hit within half a texel; hits return `scene.rgb^2.2`, and level 0 re-encodes with `1/2.2`. Misses below the top take one tap at the clamped upper probe position, blended by the texture's default `GL_LINEAR` filter rather than explicit weights.
- **Base ray counts:** the layout uses `sqrt(base)` texels per side, so of the GUI's range 4 to 16 only 4, 9 and 16 tile a whole-number grid (from reading).
- Per-pass GPU timers are shown in ImGui as 90-frame averages, with the frame rate capped at 144; no timings are recorded in the repository.

## tsukinousagi18 (C, OpenGL)

Built on the PixelRifts C codebase, in a fixed 704×704 window, so UV and pixel distances agree. It uses 6 cascades (`ceil(log4(diagonal)) + 1`), 4 base rays and 10 jump-flood passes starting at 0.5 UV.

- **Intervals:** level 0 covers `[0.25, 1.25]` px; level `k ≥ 1` starts at `4^(k−1)` px with length `4^k`, so it ends at `1.25·4^k`, past the next level's start at `4^k`. The merge runs only on misses, so the overlap costs tracing but does not count light twice.
- **Merge:** one tap at `clamp((pos + 0.5)/2, 0.5, size − 0.5)` inside the upper block, blended by the hardware (`GL_LINEAR`, clamp to edge), with rays averaged at 1/4 each. Pass i writes framebuffer i for cascade `count − 1 − i`, so cascade 0 ends up in the last framebuffer.
- **Sky (off by default):** top-level rays take `max(sunAndSky, rgb)`, even when they hit geometry. The sun is `sunColor·max(cos(θ − S), 0)^(4/d)` and the result is `mix(sun, sky, 0.3)`.
- **Composite:** `radiance + mix(world, 0.6·radiance, 1 − dist^4)`, with `dist` the distance-field value, so surfaces near occluders show 0.6× GI.
- The sRGB branch never runs (`first_cascade_index` equals the cascade count), and build artifacts (executables, PDBs, object files) are committed.

## Kelkar et al. (IEEE ICWITE 2025)

"Radiance Cascades for Real-Time 2D Global Illumination" by Nikhil Kelkar, Ganesh Bhutkar, Shriya Nagarkar and Nandini Naik (Vishwakarma Institute of Technology, Pune), 2025 IEEE International Conference for Women in Innovation, Technology & Entrepreneurship, pp. 1-6, published 2025-09-26, DOI 10.1109/ICWITE64848.2025.11307155. Only the abstract was reachable: a 2D GI engine with soft shadows for fully dynamic scenes that ray-marches a signed distance field and a lightmap, uses a 4× angular branching factor with screen-resolution textures per cascade for O(n) memory, merges cascades by hardware bilinear interpolation, and is tested on a cave scene with several emitters and occluders, running in real time while relighting every frame. The abstract gives no timings, GPU, resolution or scene size, and no open copy was found.
