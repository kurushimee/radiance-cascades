# Exploring a New Approach to Realistic Lighting: Radiance Cascades

| | |
|---|---|
| Author | SimonDev |
| Date | 2024-07-02 (upload date) |
| Kind | Video (15 min) |
| Link | https://www.youtube.com/watch?v=3so7xdZHKxw |

This 14:56 video explains the Radiance Cascades paper from Grinding Gear Games, the studio behind Path of Exile 2. It covers the rendering equation, the penumbra idea behind the method, interval merging, and a 2D screen-space layout. It is a gentle introduction; the paper itself is covered in [2023_sannikov_radiance_cascades_paper.md](2023_sannikov_radiance_cascades_paper.md).

## Contents

- [Global illumination and the rendering equation (00:00 to 03:00)](#global-illumination-and-the-rendering-equation-0000-to-0300)
- [Radiance and the key observation (04:00 to 05:00)](#radiance-and-the-key-observation-0400-to-0500)
- [Penumbras and sample spacing (06:00 to 08:00)](#penumbras-and-sample-spacing-0600-to-0800)
- [Merging intervals (09:00 to 10:00)](#merging-intervals-0900-to-1000)
- [Probe levels and interpolation (10:00 to 11:00)](#probe-levels-and-interpolation-1000-to-1100)
- [Pixel layout on a 2D screen (12:00 to 13:00)](#pixel-layout-on-a-2d-screen-1200-to-1300)
- [Demo, limits, and artifacts (13:00 to 14:56)](#demo-limits-and-artifacts-1300-to-1456)
- [Links found](#links-found)

## Global illumination and the rendering equation (00:00 to 03:00)

- The video compares three images: no lighting, direct lighting with a shadow, and direct plus global illumination. The third looks most realistic.
- Global illumination adds light that bounces off other surfaces before it reaches the point being shaded. The example scene has a camera, a floor, a wall, and a ceiling.
- The video names the rendering equation and restates it as pseudocode. The loop runs over directions in the hemisphere. Each step multiplies incoming light by the BRDF, then by the dot product of the normal and the direction, and sums the results.
- For a red diffuse cube, the BRDF term is the surface color. The video says a single direct light calculation is already expensive once shadows and complex BRDFs are added.

## Radiance and the key observation (04:00 to 05:00)

- The paper's core claim: to resolve radiance from an object of a given size, the method needs higher linear resolution near the object and higher angular resolution farther away from it.
- The video tests this with one point and one light. Four directions are enough to hit a nearby light.
- Farther from the light, those four directions miss it. More directions are needed to catch it again. A smaller light has the same effect.

## Penumbras and sample spacing (06:00 to 08:00)

- A light partly blocked by a wall casts a shadow with three parts: the umbra (fully shadowed), the penumbra (soft edge), and the fully lit area.
- The penumbra is sharp near the wall and blurs farther away. Its size depends on the distance from the light to the wall and on the light's size.
- Far from the light, samples can be spaced far apart. Near the light, the spacing must be smaller.
- The video says the farther out a probe sits, the farther apart its samples can be, but it needs more directions. The paper calls this relation the penumbra condition.

## Merging intervals (09:00 to 10:00)

- Two short checks along one ray combine into one longer check. Light from A to C equals light from A to B, plus light from B to C scaled by the transparency from A to B.
- Transparency from A to C equals transparency from A to B times transparency from B to C.
- Transparency is 0 when the ray hits something in the range and 1 when it does not.
- Two points on the same ray can merge their checks when those checks cover the same path. The video says the first point can treat the two checks as one interval.

## Probe levels and interpolation (10:00 to 11:00)

- The video starts with a few probes that have low angular resolution and short checks. Bilinear interpolation between nearby probes gives radiance at points in between.
- Higher-level probes have more directions, sit farther apart, and check a longer range. To use their data at a lower level, the video says to average several directions and then apply bilinear interpolation.
- Combining a higher linear-resolution level with a lower linear-resolution level covers the combined distance. Repeating this at each level gives a set of cascades.

## Pixel layout on a 2D screen (12:00 to 13:00)

- The video groups screen pixels into 2x2 blocks. Each block is one probe, and its four pixels are four directions.
- The next level doubles the block to 4x4 pixels, which gives 16 directions per probe. The probe sits at the center of the group.
- Each higher level has lower linear resolution and higher angular resolution. Cascades can stay in separate textures or be packed into one texture.
- The video gives no texel index formula beyond this block rule. Unclear in source.

## Demo, limits, and artifacts (13:00 to 14:56)

- The video shows a 2D demo on the author's website. The subtitles garble the page path, so the exact URL is unclear in source.
- The demo is a basic implementation. The video says the community is working on fixes.
- The video credits the paper's author for checking its accuracy.
- The video says the method is not a cure-all. A small light shows ringing artifacts. A large light behind a thin wall shows light leakage.
- The video says the community has mitigations for these, but it does not describe them.
- The video says the ideas extend to 3D, either as a world-space probe grid or in screen space.

## Links found

- SimonDev's RC shaders | https://github.com/simondevyoutube/Shaders_RadianceCascades | GLSL RC shaders by the same author; not linked from the video.
- Shadertoy mlSfRD | https://www.shadertoy.com/view/mlSfRD | "Radiance Cascades 2d Smooth WIP" by Sannikov, a fork of fad's mtlBzX.
