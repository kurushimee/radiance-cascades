# Godot 2D radiance cascades repositories

Seven public Godot projects implement or attempt 2D RC. They matter for how they connect compute shaders to Godot and for a few techniques: Suslik's merge variants and interval fades, and a scene mip pyramid that makes long intervals cheap.

| Repository | Godot | Last commit | State |
|---|---|---|---|
| https://github.com/Sohojoe/radiance-cascades-godot | 4.3 | 2024-08-04 | Working 2D RC, four project folders plus a branch (Apache 2.0) |
| https://github.com/thmasn/Godot-RadianceCascades | 4.2 | 2024-07-30 | Working port of Suslik's Shadertoy with canvas shaders |
| https://github.com/knowdawg/ProcPixelTexturing | 4.7 | 2026-08-29 | Working RC inside a pixel-art sandbox addon |
| https://github.com/TheCubeOfFire/radiance-cascades-godot | 4.3 | 2025-03-04 | 3D SDF box ray marcher; no RC code yet |
| https://github.com/TheSandwichCoder/radiance-cascades | 4.4 | 2025-08-09 | Rough prototype: fixed 3 px march steps, the top cascade never merged |
| https://github.com/Izendi/radiance_cascades_V2 | 4.5 (Compatibility) | 2026-01-23 | SubViewport chain sphere-tracing a list of up to 500 segments |
| https://github.com/knowdawg/BareBonesRadianceCascades | 4.6 | 2026-03-12 | Skeleton with an empty ray march; does not run |

## Godot integration patterns

| Pattern | Used by | Effect |
|---|---|---|
| `RenderingServer.create_local_rendering_device()`, then `submit()`, `sync()` and `texture_get_data()` each frame, with the bytes copied into an `ImageTexture` | Sohojoe | Every frame stalls and round-trips the image through the CPU. Works, but slow. |
| SubViewports chained with canvas_item shaders; the cascade viewport reads a copy of itself from the previous frame | thmasn | No scripts. Each frame merges once, so cascade `n` uses cascade `n+1` from the last frame. |
| Main device (`RenderingServer.get_rendering_device()`), results wrapped in `Texture2DRD` and `Texture2DArrayRD` and exposed as global shader parameters | knowdawg | No readback. Material shaders sample the GI directly. |
| Main device with setup through `RenderingServer.call_on_render_thread`, output in a `Texture2DRD` | TheCubeOfFire | No readback. |

Pitfalls found in these projects:

- Sohojoe's distance pass reads the output of the second-to-last jump flood pass, because of the ping-pong swap order.
- Sohojoe's Suslik port updates the six cascade images in place with no ping-pong. Dispatches for different cascades read and write the same images, and one cascade can span two images, so a read may see either the old or the new value.
- knowdawg dispatches 2048×2048 threads over 1024×1024 images with no bounds check. Two shaders declare `rgba32f` storage images bound to RGBA16F textures, which Vulkan leaves undefined.
- Recreating textures on a quality change without `free_rid` leaks GPU memory.
- TheSandwichCoder passes `width / 32` as a float to `compute_list_dispatch`; at 1080 rows that is 33.75 groups, so the last partial group of rows is dropped. Group counts need a ceiling division.
- The same project merges one cascade into the next in a texture array through two image bindings to one RID (one read-only, one write-only), relying on each thread touching only its own texel, and calls one `barrier` after all cascade dispatches instead of between them.

## Sohojoe: mix-Yaazarai-and-jason

A port of Yaazarai's direction-first, pre-averaged layout (see [2024_yaazarai_gmshaders_radiance_cascades.md](2024_yaazarai_gmshaders_radiance_cascades.md)) fed by jason.today's jump flood SDF.

- Scene: paint into an RGBA32F texture, seed, run the jump flood for `ceil(log2(max(W, H)))` passes, then store the distance divided by the render diagonal.
- Cascade count `ceil(log4(diagonal))`: 6 for 1280×736. The render size is rounded up to a multiple of `2^(N−1)`.
- Base probe spacing `radiance_linear` from a quality setting (0.25 to 4 px). Interval start `I0·(4^i − 1)/3`, length `I0·4^i + √2·L0·2^(i+1)`; the second term pads each interval past the start of the next to reduce leaks.
- One dispatch per cascade from top to bottom, two ping-pong cascade textures. The merge reads one texel of cascade `i+1` at `clamp(probe·0.5 + 0.25, 1, size − 1)` with `imageLoad`, so it is nearest-neighbor, even though a comment says hardware interpolation.
- Colors are linearized with `pow(c, 2.2)` on hit and re-encoded on cascade 0.
- Memory at quality 0.5 and 1280×736: each RGBA32F cascade texture is 2560×1472, about 60 MB.

The README calls this variant the most performant and cleanest. The repository's `main` branch holds three more Godot 4.3 project folders, and a second branch holds a fifth:

- `jason-today-gi-pt1` is jason.today's part 1, a prequel to RC with no cascades: a jump flood distance field, then sphere tracing with a sun and noise (32 rays and 32 steps for the field march, 8 rays and 256 steps for the plain march, sun angle 4.2).
- `shadertoy-port-suslik` is the port described below.
- `try-mix-jason-and-shadertoy` (not listed in the README) feeds jason.today's distance field into fad's cascade and image passes, six cascades at 1024×1024 with `MERGE_FIX 4`. Its README says it "kinda works but performance is not great".
- The `shadertoy-fad` branch ports fad's mtlBzX (`c_dRes` 16, 5 cascades); its last commit is a work in progress, "almost working with square view space".

## Ports of Suslik's Shadertoys

Sohojoe's `shadertoy-port-suslik` ports the testbed 4ctXD8, and thmasn ports "Radiance Cascades 2d Smooth WIP" (mlSfRD); both shaders are described in [2023_rc_shadertoys.md](2023_rc_shadertoys.md).

- 4ctXD8's `merge_fix` switch picks plain merge (0), bilinear fix (1), midpoint bilinear fix (2), mask or "Dolkar" fix (3), parallax fix (4) and inner parallax fix (5). Sohojoe's default is 4: march along the probe's own direction, then for each of the four upper neighbors compute the direction from that neighbor to the ray end and linearly interpolate the neighbor's two nearest directions, with interval ends stretched by 1.1 so intervals overlap.
- In 4ctXD8, cascade 0 has 4 directions per probe and 512 probes across the width; each cascade has 4× the directions and ¼ the probes. Sohojoe spreads all cascades over one linear index space in six images. Intervals in units of `W·1.5e−3` are `[0, 4], [4, 16], [16, 64], …`.
- The scene stores a signed distance in `.r` and emission in `.gba`. Rays starting inside a shape return its emission at once.
- Final gather: bilinear over four cascade 0 probes, sum their directions, tone map with `1 − 1/(1 + fluence)^2.5`.
- thmasn's mlSfRD port has 16 directions on cascade 0 (one texel each) and 4 rays per texel above it, 4 cascades, a 7 px cascade 0 interval, and smooth fades at both interval ends. Fluence is the bilinear average times 2π. The sky term is multiplied by zero.

## knowdawg: scene mip pyramid per cascade

This addon runs RC in a 2D sandbox at 1024×1024 with five cascades and needs only a handful of samples per ray.

- Build a 10-level mip pyramid of the light image (RGB emission, alpha density) with a 4×4 binomial kernel. Alpha is scaled by 2 at each level (`occlusionGain`), so a uniform field doubles its density per mip.
- Cascade `c` samples mip `c` only. Intervals are `[4^(c−1), 4^c]` px (`[0, 1]` for cascade 0), with `max(2, ceil(length / 2^c))` samples at sub-interval centers, so the step grows with the mip footprint: 2, 2, 3, 6 and 12 samples for cascades 0 to 4.
- Transmittance uses `T *= exp(−a)` per sample and stops below 0.001. The step length does not scale the density, so the result depends on the sample count.
- The merge uses four bilinear upper probes and four child directions with the standard premultiplied-alpha merge, in place from cascade 4 down to 1.
- The final pass builds 16 merged ray directions per cascade 0 probe and a fluence texture. A cosine convolution turns the 16 rays into 16 directional diffuse layers, which material shaders pick by the normal's angle for normal-mapped 2D lighting.
