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

## CoreCascade

A CPU program that renders one image per run with plain RC, RC with the bilinear fix, light propagation volumes, or a path tracer, which makes it a ready comparison harness. Scenes are SDF shapes with emission, absorption and diffuse color, marched with `step = max(|d|, 0.01)`; inside a shape, emission accumulates per step and visibility falls as `exp(−absorption·step)`. Cascade grids have `ceil(N/2) + 1` probes per axis with the origin moved back a quarter of the upper spacing each level, so upper probes cover the image edges. The README says most implementations zero the probes that fall outside the image, which is usually enough. A second pass can reuse the first pass's result times diffuse color as emission, giving one more bounce.

## Adaptive ray skipping (mebyz)

Upper cascades trace only every second or fourth ray of each pre-averaged group and average the traced ones. Fixed modes cut 10 to 40% of rays at 36 to 68 dB PSNR against the full version; an auto mode picks a level from the mean plus standard deviation of cascade 1 luminance at 8 probes, averaging about 19% fewer rays at over 50 dB across 50 test scenes. The far cascades carry low-frequency light, so they tolerate skipping.

## kiss3d decoupled cascades

Each cascade texel is one (probe, direction) pair, and the tile edge per probe (`4·2^c`) and probe spacing (`2·2^c` field pixels) are chosen independently while every level stays the size of the screen. Intervals are `base·(4^c − 1)/3` to `base·(4^(c+1) − 1)/3`. The jump-flood field is unsigned, so the SDF is biased outward by two field pixels to stop grazing rays tunneling through thin occluders. The engine ships a brute-force march with 8 rays per pixel and temporal blending as the default, and RC as an option.

## HRC samples (cute_framework, folkjs)

Two independent ports of [HRC](2025_freeman_holographic_radiance_cascades.md):

- **Checkerboard:** the paper's ray offsets `(2^i, 2k − 2^i)` are always even, so odd and even rows never meet. cute_framework uses dense offsets `(2^i, k − 2^i)` with `2^(i+1) + 1` directions, which couples every row and doubles angular resolution; folkjs keeps the paper's form and cancels the pattern with an opacity-gated `[0 1 0; 1 4 1; 0 1 0]` blur.
- **Low levels:** building levels 0 to 2 by merging short rays gave Manhattan-shaped artifacts, so they are traced directly through raw scene texels. Mip-prefiltered scene input thinned 2 px walls enough to leak about 13% per crossing and made moving emitters flicker.
- **Bounces:** last frame's fluence times albedo/2π is added back as emission. Wall probes have zero fluence inside solids, so folkjs takes the bounce from neighboring probes outside the wall, weighted by their transparency.
- **Sky:** folkjs integrates a 256-entry sky table into a prefix-sum table per direction row, so any merge bin's sky light is one subtraction.
- **Storage:** emission is encoded as `(e/16)^(1/2.2)` in 8-bit canvases (a plain `/16` lands 28× too dark after the curve); merged fluence is stored as RGB9E5.

## SimonDev demo

Plain RC, 7 levels, 4 directions per cascade 0 probe and ×4 per level, intervals `(4^L − 1)/3` to `(4^(L+1) − 1)/3` scene pixels, every level the same texture size (1820×1024). The upper lookup averages four angular taps at `index − 1 … index + 2`, which is centered half a bin off the child range `4k … 4k+3`; several helpers are marked "fixme". Probes outside the texture return `(0, 0, 0, 0)`, which reads as opaque and stops the merge.

## Bugs worth recognizing

- **Weights:** tlegoc's merge assigns three of four bilinear corners the wrong weights, and its `output += final·output.a` also changes alpha. Skipped edge taps still count toward the divisor of 4, darkening edges.
- **Negative indices:** `index − 1` at index 0 wraps to the previous probe block when `%` keeps the sign (tlegoc, SimonDev).
- **Emitter rays:** Hybrid46 keeps transmittance 1 on emitter hits, so the upper cascade is added on top of the emitter.
- **8-bit cascades:** the futureengine2 gist stores cascades in RGBA8, which clips the sun and bright emitters.

## Ray-count branching (futureengine2)

The gist doubles rays per cascade (`r0 = 4`, ×2) while intervals grow ×4 and spacing ×2, so a missed ray reads 2 upper rays at 4 probes. Its comment notes that raising the ray branching factor gives up the property that all cascades together take twice the memory of cascade 0. Rays march with an Amanatides–Woo walk over the bitmap, the first non-white texel being the hit.
