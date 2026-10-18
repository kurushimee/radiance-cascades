# Abou Dan and Jensen: screen-space RC with visibility-bitmask GI (thesis, 2025)

| | |
|---|---|
| Title | Screen Space Global Illumination Using Radiance Cascades in 3D Video Games |
| Authors | Ghaith Abou Dan, Mati Jensen; supervisor Erik Sintorn, examiner Ulf Assarsson |
| Institution | Chalmers University of Technology, master's thesis, 2025 |
| Link | https://odr.chalmers.se/items/9e42007a-bb60-440f-ba28-04410822758f |

The repository record holds only the abstract and a license file; the full text is not public, so these notes come from the abstract alone.

## Design

- Built for the game As We Descend (Box Dragon): a camera with limited movement, all relevant geometry on screen, many short-lived emissive effects, and a budget of a few milliseconds per frame.
- Screen-space probes in a radiance cascade hierarchy, traced with visibility-bitmask GI (see [Therrien](2022_therrien_visibility_bitmask_ssgi.md)) instead of plain depth marching.
- One bounce of screen-space GI plus emissive light, with a radius covering the whole screen.
- No temporal accumulation or reuse and no separate denoiser, and no high-frequency noise.

## Cost

| Setting | Time | Memory |
|---|---|---|
| Lowest | 2 ms | from 0.03 GiB |
| Medium | 6 ms | |
| High | 26 ms | up to 3.9 GiB |

Hardware is described only as "modern"; the GPU and resolution are not in the abstract.

## Problems the authors report

- Anything off screen neither lights nor occludes.
- The screen-space tracing over-brightens the background.
- Upscaling the radiance data causes artifacts, worst at low settings.
- Flicker during small movements, worst at low settings, which makes every other artifact flicker too.
