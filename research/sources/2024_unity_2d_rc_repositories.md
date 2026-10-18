# Unity 2D RC repositories

Four Unity projects and one Game Boy Advance port, all plain 2D RC except one HRC port. None has temporal reuse, bounce light or timings. Two details are worth keeping: an analytic sky integral for top-cascade misses, and a five-tap angular merge filter.

| Repository | Unity | License | Last commit | Notable for |
|---|---|---|---|---|
| https://github.com/Youssef-Afella/UnityURP-RadianceCascades2DGI | 2022.3 URP | MIT | 2025-03 | direction-first, one bilinear merge fetch, analytic sky |
| https://github.com/Youssef-Afella/UnityURP-HolographicRadianceCascades2DGI | 6000.0 URP render graph | MIT | 2025-06 | HRC port, unfinished |
| https://github.com/ZY4N/Unity-2D-Radiance-Cascade-Demo | 2022.3 | MIT | 2024-07 | volumetric march, five-tap merge, 3D-texture layout |
| https://github.com/agrdino/RadianceCascadesUnity | 2020.3 | MIT | 2024-08 | hand-painted SDF, minimal |
| https://github.com/Youssef-Afella/GBA-RadianceCascades | GBA, C | MIT | 2026-06 | fixed-point RC on an 80×80 screen, about 3 s per frame |

## Youssef-Afella plain RC

- Layer objects draw into a float texture; pixels with alpha above 0.5 occlude, and a jump flood gives the distance field.
- Cascade size is the screen times a render scale, rounded up to a multiple of `2^C`; the README says render scale matters most for speed.
- Direction-first: level `L` has `4^L` blocks, each holding one group of 4 rays (pre-averaged), `4^(L+1)` directions per probe, probes `2^L` texels apart.
- Intervals share one range scaled to the screen: start `(4^L − 1)/(4^C − 1)·R`, end `(4^(L+1) − 1)/(4^C − 1)·R`, so the top interval reaches the screen diagonal at `R = 1`.
- Merge: one bilinear fetch in block `4b + i` at `p/2 + 0.25`, clamped half a texel inside the block; `rgb += upper.rgb·a`, `a *= upper.a`.
- **Sky:** a top-level ray that misses adds the sky integrated analytically over its angle interval `[a0, a1]`: `0.16·(sky·(a1 − a0 − 0.5(cos a1 − cos a0)) + sun·(atan(8(S − a0)) − atan(8(S − a1)))/8)`, divided by the interval width and doubled. Integrating over the bin instead of point-sampling it avoids aliasing a small sun.
- Bug: the march adds a UV-space distance to a parameter measured in screen-short-side units.

## Youssef-Afella HRC port

Two texture-array slices hold vertical and horizontal plane stacks. Ray vectors are integer pixel steps `(2^L, 2^L − 4g)`, so rays end on upper probes. Each stripe mixes its two rays by angle. Even probes average two upper samples (at the probe and at the end of the doubled ray), odd probes take one. The top level does nothing and the sky is never called. The stripe index can exceed the stripe count when the width is not divisible by `2^L`.

## ZY4N

- The camera image is the scene: RGB is emission and alpha is opacity. Rays march fixed steps with `rgb += T·c; T *= 1 − a`, no distance field.
- Layers have `4^(i+1)` directions, rays start at `0.5 + 2(4^i − 1)/3` with length `2·4^i`, and up to 256 samples per ray.
- **Five-tap merge:** near direction `k` reads far directions `4k−2 … 4k+2` with weights `0.5, 1, 1, 1, 0.5` (÷4). The half-weight taps overlap the neighbor bins, a light angular blur that softens ringing at the cost of a little sharpness.
- Two layouts: a 2D texture with probe cells per layer, or a 3D texture per layer with direction in z. The 3D one drops layers that exceed the maximum 3D texture size.
- A source comment notes that integer `−1/2` rounds to 0, which makes the first column extrapolate with weight −0.25.

## agrdino

Probes `2^(L+1)` texels wide with one direction per texel, intervals `[(4^L − 1)/3, (4^(L+1) − 1)/3]` cascade pixels, bilinear 0.25/0.75 upper weights, 4 upper directions averaged per probe. The README lists ringing and dark screen edges as unsolved. The dispatch uses `width/8` without rounding up, so the last columns are never computed.

## GBA port

80×80 pixels, three levels with 4, 16 and 64 directions, intervals `[4^L − 1, 4^(L+1) − 1]` px, 16-bit texels of 8-bit light and 8-bit visibility, ray-box tests in 8.8 fixed point. It shows the method's structure with the bare minimum of state.

Other 2D repositories found but not read: Hybrid46 (C# with Raylib, a port of the Youssef-Afella code), GiGGioSo, qJay44, tsukinousagi18, ReneeR33.
