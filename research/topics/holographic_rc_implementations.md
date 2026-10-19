# Holographic RC implementations

Every public code of [holographic RC](holographic_rc.md) (HRC): what each one stores, traces, extends and merges, its formats and pass counts, its bugs and its numbers. The method, its merge rules, its artifacts and the cross-code comparisons of traced levels, cone weights and checkerboard fixes are in [holographic RC](holographic_rc.md); this file holds the per-code detail those comparisons draw on.

Statements marked "derived" were computed with a script from the codes' own formulas; "inference" marks conclusions drawn here; "read from the code" marks behaviour found by reading, not by running.

| Code | Author | Platform | Licence | Last commit | Kind |
|---|---|---|---|---|---|
| [amitabha](#amitabha) | entropylost | Rust on LuisaCompute (CUDA) | | 2025-11 | reference for the paper |
| [Volumetric-HRC](#volumetric-hrc) | Yaazarai | GameMaker | | 2026-07 | HRC with volumetrics, with a write-up |
| [TypeGPU holographic runner](#typegpu-holographic-runner) | Software Mansion | TypeScript, WGSL on WebGPU | | | library |
| [pixi-GI](#pixi-gi) | chamchi0809 | PixiJS v8, WebGL2 or WebGPU | | | npm package `pixi-rcgi` |
| [lancimir](#lancimir) | lancimir studios | C++ CPU, raylib GPU | none | | code from a game in progress |
| [hbattal](#hbattal) | hbattal | Three.js 0.184, GLSL3 on WebGL2 | none | | playground with four modes |
| [cute_framework, folkjs](#cute_framework-and-folkjs) | RandyGaul; folk-js | C; TypeScript and WGSL | zlib; MIT | 2026-10; 2026-05 | samples |
| [Unity URP port](#youssef-afellas-unity-port) | Youssef-Afella | Unity 6000.0 URP render graph | MIT | 2025-06 | unfinished port |
| [Shadertoys](#shadertoys) | Suslik; youssef_afella | Shadertoy | | 2024-11 to 2025-12 | 4ctczl, tfKyRw, WfyyDm |
| [jason.today/hrc](#jasontodayhrc) | Jason McGhee | WebGL page | | | demo with a luminance and colour split |
| [nihil](#nihil) | entropylost | Rust, CPU | | | continuous line functions |
| [hrcviz, hrcviz2](#hrcviz-and-hrcviz2) | entropylost | web; Rust to WebAssembly | | | visualizers |
| [Half HRC](#half-hrc) | brucelevis copy | GameMaker shader | | | half the probe rows |

Margel's line-space and diffusion demos, deadlyredcube's extension and sheared-probe-line pages and fad's Desmos graph draw HRC geometry without solving lighting; they are described with the ideas they illustrate in [holographic RC](holographic_rc.md#variants).

## amitabha

The reference HRC (Rust on LuisaCompute over CUDA), by entropylost, who also wrote nihil, hrcviz and the Split RC code chandra ([reference codes](../sources/2025_hrc_and_2d_reference_implementations.md#amitabha-reference-hrc)).

- **Frames.** Four rotated frames, each covering ±45°. Each frame has two interleaved probe grids offset by one pixel across the travel axis, so there is one probe per pixel across the rays.
- **Levels.** Level `i` has cells `2^(i+1)` px long along the travel axis and 2 px across, with `2^(i+1)` direction bins between `2^(i+1) + 1` boundary rays of slope `(k − D/2)/2^i`. Every level spans the same ±45°.
- **Tracing.** The two lowest levels are traced directly; higher levels build their rays by joining two rays of the level below (merge-up), and odd directions average two joined pairs because the midpoint falls between cells.
- **Merge-down.** Even probes, which share a position with a level `i + 1` probe, and odd probes, between them, are treated differently, as in the paper. A 5-tap cross filter that mixes only pixels of equal opacity removes the checkerboard.
- **Segments.** Fluence from a cell over length `L` has `T = exp(−σL)` and radiance `emission·(1 − T)`.
- No timings are published.

amitabha's level `i` is the paper's level `i + 1`, with the same `2^(i+1)` cones and plane spacing, and each of its two grids holds one lattice of the checkerboard, 2 px across. Its two traced levels are then the paper's levels 1 and 2, and the paper's level 0, 1 px long, is not stored (inference).

## Volumetric-HRC

Yaazarai's GameMaker HRC with volumetrics and a write-up, credited by pixi-GI ([reference codes](../sources/2025_hrc_and_2d_reference_implementations.md#volumetric-hrc-yaazarai)).

- **Layout.** Plane spacing `2^i`, `2^i + 1` rays per plane and `2^i` cones between them. Cascade 0 is seeded per pixel with `T = 2^(−A)` and `R = (1 − T)·E`, with `E` and `A` linearized with exponent 2.2.
- **Extensions from cascade 0.** Rays are built by extension from cascade 0 upward, not from cascade 3 as in the paper; the README says this reduces aliasing and gives more stable results through angular diffusion.
- **Merging.** The README says the even-plane interpolation cannot be replaced by interpolating before merging. Emitters must be drawn into both the emission and the absorption textures.
- **Half probes.** The README describes an option to cast only half as many probes along each plane and let rays interpolate between them when extending and merging, to "double performance where needed".
- **Timings (README, RTX 3080).** 256² about 1 ms, 512² 1 to 2 ms, 1024² 5 to 6 ms, 2048² 9 to 11 ms, 4096² 35 to 45 ms; 8192² runs out of memory. The README's header gives a "simple" 2048² volumetric scene at 11 to 12 ms. The community notes give 2.61 ms at 1024² on an RTX 3080 and 0.75 ms at 512² on a GTX 970 ([holographic RC](holographic_rc.md#performance)).
- **Earlier plain RC.** The same author's port of fad's Shadertoy (Yaazarai/RadianceCascades) stores radiance in RGBA8 gamma space, which bands visibly; the GM Shaders version later moved to RGBA16F ([2D articles and demos](2d_articles_and_demos.md#gm-shaders-yaazarai-and-xor)).

The README rows do not scale together. From 1024² to 2048² the midpoints grow ×1.82 where `X·Y·log X` predicts ×4.40, while from 2048² to 4096² they grow ×4.00 against ×4.36 predicted (derived). The 1024² row is about twice what the scaling from the larger sizes implies, and 2.61 ms at 1024² on the same GPU fits that scaling, so the 5 to 6 ms row most likely comes from an older build or a heavier scene (inference).

## TypeGPU holographic runner

Software Mansion's `@typegpu/radiance-cascades` package has an SDF runner, described in [2D implementations](2d_implementations.md#typegpu-software-mansion), and a holographic runner, "Four-sector HRC, using the interval and fluence recurrences of Freeman et al. (2025)" ([TypeGPU](../sources/2026_software_mansion_typegpu_radiance_cascades.md#holographic-runner)).

### Options and outputs

`create(options)` returns an `Executor`.

| Option | Required | Default | Meaning |
|---|---|---|---|
| `root` | yes | | `TgpuRoot` |
| `size` | yes | | `{ width, height }`, not validated |
| `medium(pixel: v2u)` | yes | | returns `{ emission: v3f, extinction }`, with `extinction` a `number` for scalar transmission and a `v3f` for rgb |
| `transmission` | no | `'scalar'` | `'scalar'` or `'rgb'` |
| `source(pixel: v2u, incident: v3f)` | no | none | extra emission (`v3f`) per pixel |
| `tracedLevels` | no | 3 | positive integer, otherwise it throws `tracedLevels must be a positive integer.` |

`medium` is wrapped with `tgpu.fn` and bound to a slot on the root, so captured TypeGPU resources are bound automatically.

- `output`: `rgba16float`, `[W, H]`, storage and sampled; angular mean radiance normalized by 2π.
- `sectors`: `rgba16float`, `[W, H, 4]` (a 2D array), storage and sampled. Layer `q` holds the light arriving from one side: 0 is +X, 1 is +Y, 2 is −X, 3 is −Y (the guide's order and the drawing example's display order).

**Units and use (guide).** `medium` receives integer pixel coordinates and returns emitted linear RGB radiance added per pixel of travel and a nonnegative extinction in inverse pixels, so `e^(−extinction·s)` of the light survives `s` pixels. An opaque emitter shows as `emission/extinction` (emission `[16, 8, 4]` with extinction 16 displays as `[1, 0.5, 0.25]`), extinction 16 passes about 10⁻⁷ of the light crossing one pixel, and values must be finite because infinity is not treated as fully opaque. Coloured transmission `T` over `s` pixels takes extinction `−log(T)/s` per channel (`[0.9, 0.1, 0.01]` over 10 px gives about `[0.0105, 0.2303, 0.4605]`). Light travels in straight lines with no refraction or dispersion, and expensive materials are best rasterized into a texture that `medium` reads with `textureLoad`. `source(pixel, incident)` adds emission from `incident`, the direction-averaged light arriving in the previous pass: `run({ iterations })` repeats the solve with zero `incident` on the first pass and one more bounce per pass, and every `run()` starts from darkness, so bounces do not carry over between runs. Isotropic scattering adds the scattering coefficient to extinction and returns `scattering·incident` (the guide's example keeps absorption in `.rgb` and scattering in `.a` of a medium texture and runs 3 iterations); the direction average is not enough for forward or backward scattering, and the runner does not check energy conservation, so a `source` that returns more light than the medium removes brightens the scene every iteration. Neither callback may read `output` or `sectors`; they use `incident`. Apps sample `output` with the scene's `uv` and composite `scene.rgb + light·(1 − scene.a)` with `scene.a = 1` on solid pixels; light is linear and can exceed 1 near bright emitters, so it is scaled or tone mapped. The guide says `+Y` points down, the four sector layers add up to `output` before its smoothing, and it uses them to light surfaces by their normals. Both textures are owned by the runner and destroyed by `destroy()`.

### Data and transport

- **Interval:** `radiance: vec3f` and `transmission: f32` (scalar) or `vec3f` (rgb).
- **Packing in storage buffers.** Scalar: `array<u32, 2>` (8 bytes), word 0 `pack2x16float(radiance.rg)`, word 1 `pack2x16float(radiance.b, transmission)`. RGB: `array<u32, 3>` (12 bytes), word 2 `pack2x16float(transmission.gb)`. `empty()` is radiance 0 and transmission 1 (`vec3(1)` for rgb). Fluence values are packed as `vec2u` with `pack2x16float` of `(rgb, 0)`.
- **`over(near, far)`:** `radiance = near.radiance + near.transmission·far.radiance`, `transmission = near.transmission·far.transmission`.
- **`average(a, b)`:** the component-wise mean of radiance and transmission.
- **`integrate(emission, extinction, length)`:** `T = exp(−σ·length)`; `integral = (1 − T)/σ` when `σ > 1e−5`, else `length`; radiance `emission·integral`, transmission `T`. Scalar uses `σ.r` for the transmission; rgb uses per-channel values.

### Buffers and memory

For `size = (W, H)`:

- `levels = ceil(log2(max(W, H)))`.
- `planeCount(L)` is the maximum over axes `a` of `ceil(size_a/2^L)·size_other` where `L ≤ ceil(log2(size_a))`, else 0.
- The interval pyramid has `intervalCounts[L] = planeCount(L)·(2^L + 1)` for `L` in `0..levels`, inclusive, with one storage buffer of packed intervals per level.
- `fluenceCount` is the maximum over `L` of `planeCount(L)·2^L`; two radiance buffers of `fluenceCount` `vec2u` alternate by level parity.
- The sectors texture and the output texture; with `source`, a mutable `vec2u` feedback buffer of `W·H` elements.
- `bytes = Σ intervalCounts·8 + fluenceCount·16 + W·H·40`, the 40 bytes per pixel being 32 for four `rgba16float` sector layers and 8 for `output`; `byteSize = bytes + (rgb ? Σ intervalCounts·4 : 0) + (source ? W·H·8 : 0)`.

| Size | Intervals | Fluence values | Memory |
|---|---|---|---|
| 256² | 720,640 | 65,536 | 9.0 MiB |
| 512² | 3,145,216 | 262,144 | 38.0 MiB |
| 1024² | 13,630,464 | 1,048,576 | 160.0 MiB |
| 2048² | 58,718,208 | 4,194,304 | 672.0 MiB |

The guide checks 9.0, 38.0 and 160.0 MiB by hand; the 2048² row and the counts were computed from the same formula (derived). The code's docstring calls `byteSize` the "Logical size of the allocations owned by the executor" (`src/holographic/index.ts:82`), so the guide's "exact allocation" says more than the code does.

The four quadrant sweeps run one after another and share one pyramid, so TypeGPU stores about 13 intervals per pixel at 1024² (all 11 levels, with the extra boundary ray per probe) at 8 bytes, where the paper's formula keeps four quadrants of 10 levels at 12 bytes, 40 intervals per pixel: 104 MiB of interval storage against 480 MiB (derived). Sequential quadrants do the same work as concurrent ones, so storing all four pyramids buys only parallelism across quadrants (inference).

### Quadrant sweeps

- Each sweep applies the same 1D algorithm to a rotated grid: width `W_q = size[q mod 2]` (local `x`, along the sweep), height `H_q = size[1 − (q mod 2)]` (local `y`, rows), `levels_q = ceil(log2(W_q))`.
- Local to world, with `(size0, size1) = (W, H)`: q0 `(x, y)`; q1 `(size0 − 1 − y, x)`; q2 `(size0 − 1 − x, size1 − 1 − y)`; q3 `(y, size1 − 1 − x)`.
- The value computed for local column `x` is stored in the sector texture at local pixel `x − 1`, layer `q`; for `x = 0` the stored value is zero, at local pixel `W_q − 1`, so the edge pixel facing the exterior is zero. This is the paper's `+1` gather offset.
- Per sweep, the up-sweep runs levels `L = 0..levels_q` inclusive, then the down-sweep `L = levels_q − 1..0`; after all four sweeps, one integrate pass. That is `Σ_q (2·levels_q + 1) + 1` passes per iteration, 77 at 512² (`4·19 + 1`), with one more source pass per iteration when `source` is set.
- All holographic passes use `@workgroup_size(64)` with a 1D dispatch: `getDispatchSize(count)` returns `[ceil(count/(64·rows)), rows]` with `rows = ceil(count/(65535·64))`, and the thread id is `gid.x + gid.y·(dispatch[0]·64)`. Up- and down-sweep pipelines are cached by key, `up_WxH_lL` (plus `_qQ` for traced levels) and `down_WxH_lL` (plus `_qQ` at level 0); the integrate and source pipelines are created once each. Paired-level pipelines do not depend on the quadrant, so quadrants with the same sweep size share them.

### Up-sweep: intervals

For level `L`, `s = 2^L` and `C = ceil(W_q/s)` columns; `D = s + 1` directions on traced levels (`L < tracedLevels`) or `D = s/2 + 1` on paired levels. The thread count is `C·H_q·D`, with `y = id mod H_q`, `d = floor(id/H_q) mod D`, `x = floor(id/(H_q·D))`, and the storage index is `(x·(s + 1) + dirActual)·H_q + y` with `dirActual = d` (traced) or `2d` (paired).

- **Traced levels.** The segment starts at pixel `(x·s, y)` and ends at offset `(s, 2·dirActual − s)`, slope `(2·dirActual − s)/s` in [−1, 1]. The walk visits cells with pixel centres at integers and boundaries at half-integers, stepping one pixel in `x` per crossing and one in `y` per crossing, `+1` for a non-negative slope and `−1` otherwise. Per cell, `value = over(value, integrate(emission(world) + feedback(world), extinction(world), cellLength))`, with `feedback` zero unless `source` is set. It starts at `empty()` and stops when the walk leaves the sweep (`x ≥ W_q`, `y < 0`, `y ≥ H_q`) or reaches the segment length, after at most `2s + 1` cells.
- **Paired levels**, for even `dirActual` with `dh = dirActual/2` and `off = 2·dh − s/2`: `near = I[L−1](2x, y, dh)`, `far = I[L−1](2x + 1, y + off, dh)`, `value = over(near, far)`, stored for every even entry. When `dirActual < s` the odd entry is written at index `+ H_q` (the next direction slot) as `average(lowerPath, upperPath)`, with `lowerPath = over(near, I[L−1](2x + 1, y + off, dh + 1))` and `upperPath = over(I[L−1](2x, y, dh + 1), I[L−1](2x + 1, y + off + 2, dh))`.
- Out-of-range reads of the previous level return `empty()`.
- `tracedLevels` larger than `ceil(log2(W_q))` traces every level directly; no upper bound is checked.

### Down-sweep: fluence

For level `L`, `s = 2^L`, `C = ceil(W_q/s)` columns and `Cu = ceil(W_q/(2s))` upper columns; `C·H_q·s` threads with `y = id mod H_q`, `d = floor(id/H_q) mod s`, `x = floor(id/(H_q·s))`, writing radiance index `(x·s + d)·H_q + y`. For each half `h` in {0, 1}:

- `b = d + h` is the boundary index within level `L`, and `ud = 2d + h` the upper fluence direction (0 to `2s − 1`).
- The wedge fraction is `α = (atan(slope1) − atan(slope0))/(2π)` with `slope0 = (2·ud − 2s)/(2s)` and `slope1 = (2(ud + 1) − 2s)/(2s)`.
- The segment is `far = I[L+1]((x/2)·(2s + 1) + 2b)` at row `y` for even `x`, and `near = I[L](x·(s + 1) + b)` at row `y` for odd `x`.
- The distant term reads `R[L+1](floor(x/2) + 1, ty, ud)` with `ty = y + (2b − s)·(2 for even x, 1 for odd x)`, zero at the top down level (`L = levels_q − 1`) or out of range.
- `contribution = segment.radiance·α + segment.transmission·distant`; for even `x`, `contribution = (contribution + R[L+1](floor(x/2), y, ud))·0.5`; the result sums both halves.
- For `L > 0` it stores `R[L][(x·s + d)·H_q + y] = pack(vec4(result, 0))`. For `L = 0` it writes the sector texture at the world pixel of local `(x − 1, y)` (or `(W_q − 1, y)` for `x = 0`), layer `q`, as `unpack(pack(result))` for `x > 0` and zero for `x = 0`; the round trip reproduces half-precision rounding before the texture store ("Preserve half precision rounding before the texture conversion").
- `R[L]` is written to `radiance[L mod 2]` and read from `radiance[1 − (L mod 2)]`.

### Integrate and source passes

- **Integrate**, per pixel `p` (`id = p.y·W + p.x`): `opacity(q) = exp(−extinction(q))`, per channel for rgb; `S(p)` is the sum of the four sector layers. Neighbours +X, +Y, −X, −Y are used when inside the grid and `|opacity(p) − opacity(n)| < 0.1` in every channel; `value = 4·S(p) + Σ S(n)` over used neighbours, `weight = 4 + count`, and `output(p) = (value/weight, 1)`. With `source`, `feedback[id] = pack(value/weight, 0)`. The medium's extinction is read through `hrcMedium` both for traced cells and for this test.
- **Source** runs once per iteration before the sweeps: on iteration 0 with `incident = 0`, later with `incident = unpack(feedback[id])`, the previous integrate output. It writes `feedback[id] = pack(source(pixel, incident), 0)`, which traced cells read as extra emission at `feedback[world.y·W + world.x]` ("evaluated once per pixel before each solve"). The integrate pass then overwrites the same buffer with the lighting output for the next iteration.
- Each sector layer holds the angle-weighted contributions of its quarter-circle divided by 2π, so their sum is the angular mean, which is then averaged with neighbours of similar opacity.

### Behaviour read from the code

- `run({ iterations: 0 })` records no solve passes, and `output` keeps the previous run's values.
- `size` is not validated: `create` throws only for `tracedLevels` (`src/holographic/index.ts:101-106`), although the guide requires both dimensions to be at least 2 px. The guide's other limits: the domain is finite with a black exterior, emission is isotropic, surface reflection and refraction are not built in, long paths and reconstruction are approximate, and half-precision storage limits accuracy in very dim and high-dynamic-range scenes.
- The guide says "Use finite values, since infinity is not treated as fully opaque." With infinite extinction, `exp(−σ·length)` is 0 and `(1 − T)/σ` is 0, so light is blocked and emission adds nothing, but a zero-length cell evaluates `exp(−∞·0)`, which is NaN.
- `Executor.run`'s docstring: a supplied encoder is not submitted and a supplied pass is not ended.

### Examples

- **global-illumination** ("Holographic Global Illumination: Explore color bleeding and successive diffuse bounces through a connected gallery. Drag to move the light."). The scene is 512 units: an enclosing wall `12 − sdBox2d(p − 256, (216, 216))` and twelve boxes and disks with grey, blue, green, red and orange albedo, combined by minimum distance with the albedo of the nearest shape; `normalAt(p, radius)` takes central differences of the SDF. The grid is 256×256 (`cellSize` 2 units), with three `rgba16float` textures: `base` (lamp emission, surface coverage), `emission` (the medium's emission) and `medium` (extinction). The rasterize pass sets coverage `saturate(0.5 − sceneDistance/cellSize)` and lamp coverage from a box SDF at `lampPosition` (half size `(2, 15)`, minus 3), writes `base = (lamp·64·cellSize, surface)` and extinction `max(surface, lamp)·16·cellSize`, and the runner reads `emission.rgb` and `medium.r` with scalar transmission. The bounce pass, for pixels with `distance > −1.5·cellSize` and `base.a > 0`, writes `base.rgb + reflected(p, surface, normal)·extinction` to `emission` and re-solves. `reflected` pushes the boundary point out along the normal in three iterations, samples the four sector layers at `boundary + normal·1.5` cells, weights each sector by the sine difference of its lobe clipped to ±π/2 around the normal angle, and multiplies by `2·albedo`. `updateLighting` runs rasterize, `lighting.run({ pass })`, then `bounces` times bounce and run, all in one compute pass and only when the lamp moves or the bounce count changes. Display shows walls as `reflected(...)/π`, adds `lamp·4`, tone maps `colour/(0.5 + max(rgb))`, converts to sRGB and masks a rounded gallery frame `sdBox2d(p − 256, 220) − 12`.
- **radiance-cascades-drawing** ("Holographic Radiance Cascades (with drawing): Draw emitters and occluders in a pixel scene lit by holographic radiance cascades"): emission `rgb·16`, extinction `alpha·16`, so painted pixels are opaque (extinction 16) and show radiance equal to their colour, emission over extinction.

The gallery example computes its bounces within one frame by re-solving, and only when the light moves; it is the one HRC code that gets multi-bounce without frame latency, at one full solve per bounce (inference).

## pixi-GI

The npm package `pixi-rcgi` for PixiJS v8 on WebGL2 (with `EXT_color_buffer_float`) or WebGPU, with shaders written once in pixi-psl; it credits Volumetric-HRC and the paper ([survey](../sources/2026_rc_repository_survey.md#pixi-gi-hrc-for-pixijs)).

- **Buffers.** Extent `min(2048, nextPow2(max(view) + 1))` and `log2(extent)` cascades (9 at 512). Emissive RGBA16F, occlusion and normals RGBA8, rays RGBA16F at width `floor(extent/2^n)·(2^n + 1)`, cones and fluence RGBA16F at extent², fluence with mips. Memory is `extent²·(cascades + 2)` RGBA16F texels, given in the README as 23 MB at 512, 96 MB at 1024 and 436 MB at 2048. The formula gives 23.1 MB (22.0 MiB), 100.7 MB (96.0 MiB) and 436.2 MB (416.0 MiB), so the README's middle figure is in MiB and the other two in MB (derived).
- **Frame.** Albedo, emissive and occlusion renders through a GI camera whose translation snaps to `2^min(lod, log2(margin + 1))` px; per frustum a seed, extension from cascade 0 (not the paper's cascade 3) up to `N − 1`, merge from `N − 1` down and an additive resolve; up to 3 smoothing passes; optional temporal accumulation; fluence mips. That is `4·(2N + 1)` full-screen passes plus the mips, 76 at `N = 9`.
- **Seed and merge.** Emission is radiance per pixel of travel, so emitters light the room without occluding; alpha is `1 − occlusion`. Rays join front to back. Cone weights are `0.5·atan(I/(I² + k(k + 1)))` with `I = 2^n`, half the angle between slopes `k/I` and `(k + 1)/I`; the weights sum to π, so the resolve multiplies by 1/π. Even planes average the far merge with the near cone, and interpolation happens after merging.
- **Smoothing.** Four diagonal taps at offset `2^(i−1)` texels in pass `i` cancel the 2, 4 and 8 px lattice patterns; the checkerboard falls from 1.5% to 0.05% of mean luma.
- **Temporal (off by default).** An exponential moving average whose keep factor (at most 0.98) is multiplied by an on-buffer test and by `1 − smoothstep(0.1, 0.4, relative luma change)`, reprojected by the camera delta, at 0.15 ms at 512². Keep 0.85 lowers the frame-to-frame difference by 44% and 0.95 by 55%, with mean luma unchanged within 0.1%.
- **Occluders.** A pixel inside an occluder takes the mean of free-space light dilated over mip levels (weights halving per level), shaded with half-Lambert wrap from the gradient of that field when a normal map exists. The README calls this a dilation, not a solve.
- **Measurements (author, 960×540 demo, Apple M1 Pro, Chrome on ANGLE-Metal).** Resolution 0.25 gives 256² buffers, 8 cascades, 3.0 ms for HRC and an 8.3 ms frame; resolution 0.5 gives 512², 9 cascades and 8.5 to 10.4 ms for HRC. The temporal section of the same README gives 3.2 ms for the hierarchy at 512², which does not match.
- **Limitations listed.** No sky, no multi-bounce, leaks through thin walls at grazing angles, and emitter intensities quantized through 8-bit tints. The README's margins at 1080p and resolution 0.5 (483 and 63 px) are totals; per side they are 241 and 31 px.

The temporal filter reduces frame-to-frame change by under half at keep 0.85, so most of what it removes is flicker from the snapped camera and moving sources rather than noise, since HRC has none (inference).

## lancimir

lancimir/holographic-cascades, code from a lancimir studios game in progress, with no licence ([survey](../sources/2026_rc_repository_survey.md#lancimirholographic-cascades-cpu-and-gpu-hrc)).

- **CPU.** A 256² grid (`N = 9`) of transmission and radiance. Cascade `n` has planes every `2^n` cells and `2^n + 1` rays per probe with directions `(2^n, 2k − 2^n)`, stored at `(x/2^n)·(2^n + 1) + k`, with angular weights as `atan2` differences. A forward pass for `n = 1..N − 1` builds rays (an even ray merges two child rays, an odd ray averages two chain orders), then a backward pass for `n = N − 2..0` builds fluence (even planes average two cones) from a zero top level, so there is no sky. Four quarter-turned frustums run under OpenMP and are summed with weight 0.25, then blurred with a cross of centre 1/2 and neighbours 1/8.
- **CPU timings (file header, i7-14700K).** clang `-O3` without `-fopenmp` takes 210 ms at 512², 40 ms at 256² and 16 ms at 128²; MSVC `/O2` takes 280, 57 and 16 ms. Without `-fopenmp` the pragmas do nothing, so these are probably single-threaded.
- **GPU (raylib).** 1024² (`N = 10`), all RGBA32F. Transmittance for levels 0 to 2 uses brute-force point samples and merges above that; fluence runs from level 8 down; the same cross blur. No timings.
- **Defects read from the code.** A debug macro left in the fluence shader writes 100 whenever an even-plane fetch has positive green; out-of-range accumulation reads return clamped values instead of black; the blur counts out-of-range taps as white, brightening frame edges; circles are drawn at twice their radius.

The CPU timings grow ×2.5 from 128² to 256² and ×5.3 from 256² to 512² (clang), against about ×4.5 predicted by `X·Y·log X`; the small first step suggests fixed overhead at 128², and the large second one a working set leaving cache (inference).

## hbattal

hbattal/2D-Lights, Three.js 0.184 with GLSL3 on WebGL2, with four modes: HRC, RC with the bilinear fix, plain RC, and a 64-ray brute-force reference with blue-noise offsets; no licence. The RC modes are in [2D implementations](2d_implementations.md#unity-and-other-ports) ([survey](../sources/2026_rc_repository_survey.md#hbattal2d-lights-hrc-and-rc-playground)).

- **Grid.** The lighting grid is as wide as the resolution setting (1024 on desktop), giving 10 cascades, and only every other probe row is stored ("half probes").
- **Scene.** RGB is emission and alpha absorption (1 for opaque shapes, 30 for balls); both pass through `pow(·, 2.2)`, so absorption is `alpha^2.2`, and the author's comments call the absorption scale unresolved.
- **HRC.** Per frustum, cascade 0 alone is traced by a DDA over texels (`tran = exp(−absorb·step)`, `rad = emission·(1 − tran)`); levels 1 to `n − 1` are built by extension (an even ray takes child `ind/2`, an odd ray averages its two neighbours, and nothing is chained when the far half falls off the buffer); cones are merged from the top with `atan`-difference weights, the top reading a 200-texel sky texture times the cone width. The four frustums are summed, divided by 2π and sRGB-encoded. The repository counts `4·(2·ceil(log2 W)) + 2` passes, 82 at 1024. Transmittance is one scalar, though the shader README lists per-channel transmittance as an option.
- **Defects.** The probe-major path and a brute-force HRC shader are unreachable; the mobile resolution shows 700 but uses 800; the rainbow sky fills only texels 0 to 50 of 200.

## cute_framework and folkjs

Two independent ports of the paper: RandyGaul's cute_framework sample `samples/hrc.c` (C, zlib, 2026-10, dense directions and bounce feedback) and folkjs's `folk-holographic-rc.ts` (TypeScript and WGSL, a WebGPU custom element, MIT, 2026-05, with a sky prefix table and RGB9E5 storage) ([assorted experiments](../sources/2026_assorted_2d_rc_experiments.md#hrc-samples-cute_framework-folkjs)).

Shared findings:

- **Checkerboard.** The paper's ray offsets `(2^i, 2k − 2^i)` are always even, so odd and even rows never meet. cute_framework uses dense offsets `(2^i, k − 2^i)` with `2^(i+1) + 1` directions, which couples every row and doubles angular resolution; folkjs keeps the paper's form and cancels the pattern with an opacity-gated `[0 1 0; 1 4 1; 0 1 0]` blur.
- **Low levels.** Building levels 0 to 2 by merging short rays gave Manhattan-shaped artifacts, so they are traced directly through raw scene texels. Mip-prefiltered scene input thinned 2 px walls enough to leak about 13% per crossing and made moving emitters flicker.
- **Bounces.** Last frame's fluence times albedo/2π is added back as emission. Wall probes have zero fluence inside solids, so folkjs takes the bounce from neighbouring probes outside the wall, weighted by their transparency.
- **Sky.** folkjs integrates a 256-entry sky table into a prefix-sum table per direction row, so any merge bin's sky light is one subtraction.
- **Storage.** Emission is encoded as `(e/16)^(1/2.2)` in 8-bit canvases (a plain `/16` lands 28× too dark after the curve); merged fluence is stored as RGB9E5.

folkjs in detail:

- **Grid.** `probeCount` 1024 sets the probes along the longer side, so 1920×1080 gets 1024×576 probes 1.875 px apart and `ceil(log2(1024)) = 10` cascades. Level `L` has `ceil(pc/2^L)` probes per row with `2^L + 1` rays each. Each frame runs seed, extend and merge for the four directions and accumulates level 0 into an RGB9E5 fluence buffer.
- **Seed.** Transmittance `(1 − a)^spacing` per probe and radiance `(rgb + bounce)·(1 − T)`, packed as f16.
- **Extension.** Ray `r` at level `L` joins `lower = floor(r/2)` and `upper = floor((r + 1)/2)` from probes `2p` and `2p + 1` and averages the two crossings; for even `r` the two coincide, so the result is the exact composition. A comment describes a parity branch the code does not need.
- **Merge.** Cone weights are exact arc widths `atan2(2s − N + 2, N) − atan2(2s − N, N)` with `N = 2^(L+1)`. Odd probes add `ray·w + far·T`; even probes average that two-step chain with the coarse level's merged value, which a comment calls a Richardson average though it is a plain 50/50 mean. The top level and out-of-bounds probes fall back to the sky, whose prefix table is built from samples at cone midpoints, so it integrates a piecewise-constant sky.
- **Bounce and output.** Bounce is `fluence·albedo/2π` from the exterior cardinal neighbours where a probe is opaque, read by the next frame's seed (one frame of latency). The blit adds `fluence/2π·(1 − opacity)` to the scene colour, then applies a fitted ACES curve, a 1/2.2 power and ±1/255 triangular dither. A debug mode shows a path-traced reference and its difference from HRC; per-pass GPU timestamps are shown in the element, and the repository records no numbers.

The `(e/16)^(1/2.2)` encoding stores up to 16× overbright emission in 8 bits at the cost of precision near 16, the same trade as the RGBA8 gamma storage that banded in Yaazarai's plain RC port (inference).

## Youssef-Afella's Unity port

Youssef-Afella/UnityURP-HolographicRadianceCascades2DGI, an unfinished HRC port for the Unity 6000.0 URP render graph, MIT, 2025-06 ([Unity repositories](../sources/2024_unity_2d_rc_repositories.md#youssef-afella-hrc-port)). The same author's plain RC port is in [2D implementations](2d_implementations.md#unity-and-other-ports).

- Two texture-array slices hold vertical and horizontal plane stacks. Ray vectors are integer pixel steps `(2^L, 2^L − 4g)`, so rays end on upper probes. Each stripe mixes its two rays by angle. Even probes average two upper samples (at the probe and at the end of the doubled ray), odd probes take one. The top level does nothing and the sky is never called. The stripe index can exceed the stripe count when the width is not divisible by `2^L`.
- Targets are screen-sized, not powers of two, and the volume defaults to 9 cascades. Each level dispatches both plane orientations; a level has `2^L` blocks with planes `2^L` px apart, two rays per block, and rays on even plane coordinates are twice as long. The march takes at most 32 steps on the distance field and hits below 1 px.
- The jump flood runs `ceil(ln(max(W, H)))` passes, a natural logarithm: 8 passes at 1920 px, ending at a step of about 7.5 px instead of 1 px, so distances near seeds are approximate (a base-2 count would give 11).
- Cone weights are `angle(r1, mid)/angle(r1, r2)` with `mid` normalized from unnormalized integer vectors, so both come out near 0.5 instead of following each cone's angular span. The final pass averages the vertical and horizontal results equally; the sky function and its uploaded colour are never used.

## Shadertoys

The three HRC Shadertoys march every level its full length; none builds rays by extension ([Shadertoy notes](../sources/2023_rc_shadertoys.md#holographic-cascades)). Their place in the Shadertoy lineage is in [2D Shadertoys](2d_shadertoys.md).

### 4ctczl (Suslik)

"Holographic Radiance Cascades" (2024-11-08), forked from 4ctXD8, the first HRC Shadertoy. It uses HRC's line structure but not its extension step.

- Four levels. Level `n` has lines spaced `2^n` times the base spacing (512 lines across at level 0), a constant probe spacing along each line, and `D_n = 8·2^n` directions uniform over 360°, offset by −45° (Common:30-32, 88-90, 231-236). Directions double per level instead of quadrupling.
- Two families: directions within 45° of horizontal live on vertical lines and the rest on horizontal lines (Common:111-115). For `D = 8`, family 0 is −22.5°, 22.5°, 157.5° and 202.5°. Each (line, probe) holds `D/2` intervals per family, `2^21` per level on a square view (derived).
- Merge (Cube A:54-112): each interval takes 16 sub-steps. Each sub-step slides the origin across the probe's cell and picks a fractional direction, then finds where its ray meets the next level's line and interpolates linearly between two neighbouring level `n + 1` directions and along that line. The near segment runs from the origin to the crossing; the top level uses 1000 px rays with no far term. The 16 results are averaged with equal weights, with no angular weights. The comment above the origin slide says nobody knows why it works.
- Every interval marches to the next level's line, which is top-down RC on HRC-like geometry with no extension.
- Gather: for each of 8 level-0 directions, interpolate the nearest line's interval; output `1.5×` the mean, tone mapped.
- One level per frame through the cube map's previous frame, so about three frames of lag. Inactive: three other merge variants (`CastMergedInterval`, `CastMergedIntervalExtended`, `CastMergedIntervalNumericalFast`), a slower gather, the sky integral, and a Dolkar miss-handling variant.

The origin slide over the cell with 16 sub-steps integrates each interval over its footprint across the line, a box prefilter in line space, which is plausibly why it works (inference).

### tfKyRw (youssef_afella)

"Holographic Radiance Cascades 2D" (2025-12-01), one frustum with the paper's geometry.

- Eleven levels (0 to 10) for one 90° frustum facing +x. Level `n` has planes `2^n` px apart with one probe per pixel row, and rays `(2^n, 2k − 2^n)` for `k = 0..2^n`: the paper's `2^n + 1` rays spanning slopes −1 to 1 (Common:62-63, 103-107). Each texel is one cone between neighbouring rays, so every level is a full-viewport texture.
- Cone weights come from angles: with `mid` the average of the two rays, `w1 = angle(ray1, mid)/angle(ray1, ray2)` and `w2 = 1 − w1` (Common:82-94). Level 0 gives 0.5 and 0.5; level 1 cone 0 gives about 0.41 and 0.59. Each ray is weighted by the angular width of its half of the cone.
- Merge (Common:97-159): each ray marches its full length and, unless it hit, composites level `n + 1` at its far end. Odd planes read one sample on the next level's plane. Even planes march twice the length and average two samples, which the code calls a fix for discontinuous rays on even planes. No ray is built from two shorter rays, and the cross-level merge has no angular weights.
- Buffers A to C compute three levels each over a three-frame ring (10/9/8, 7/6/5, 4/3/2), Buffer D level 1, and Image level 0 every frame, so levels refresh every three frames and the image lags about two frames while mixing times across levels. The author accepts losing about two thirds of the frame rate and states the ideal as one pass from the top level to level 0.
- The scene is a pulsing white light behind a black occluder, sphere traced for 32 steps; misses are black. There is no sky, no frustum rotation and no division by the frustum count. Output is linear radiance with an sRGB encode.

### WfyyDm (youssef_afella)

"HRC 2D GI" (2025-12-03) recreates the paper's figure, and its comment calls tfKyRw a simpler version of it. It shares tfKyRw's cone weights, doubled even-plane rays, two-sample even-plane average, buffer ring and sRGB encode, and like it has no extension step.

- Four 90° frustums (toward −x, +x, −y and +y) at half resolution, stored as the four quadrants of each buffer; the author says full resolution would need about 40 dispatches (Common:8, 229-233).
- Ten levels. Level `n` has planes `2^n` px apart with one probe per lateral pixel row and `2^n` cones per probe, each cone between rays `(L, 2k − L)` and `(L, 2k + 2 − L)` with `L = 2^n`, spanning ±45° (Common:112-158). Odd-plane rays reach the next parent plane (length `L` to `√2·L`) and read one nearest parent texel; even-plane rays are twice as long and average two parent samples (Common:169-211). Ray `i` of cone `c` reads parent cone `2c + i`.
- Cone weights are each ray's angle to the cone's chord midpoint over the angle between the rays: 0.5 and 0.5 at level 0, 0.41 and 0.59 for level 1 cone 0 (Common:127-143). The first and last rays of a frustum have their direct hits scaled by `0.5/L + 0.5` before the merge, so light merged onto them is not scaled (Common:174-178).
- Schedule: Buffers A to C compute levels 9/8/7, 6/5/4 and 3/2/1 over a three-frame ring, and Buffer D computes level 0 on the third frame and holds it otherwise; levels 6 and 3 read the level above from the previous frame. Level 0 is 0 to 2 frames old on screen and level 9's light 2 to 4 frames old, while the ball overlay updates every frame (inference from the schedule). The author accepts losing two thirds of the frame rate.
- Image averages the four quadrants with weight 0.25, which at level 0 averages four diagonal rays (inference). The scene is 80 emissive balls on a spiral (angle step 2.3067 rad, not the golden angle), sphere traced for 32 steps, with no sky or tone map and an sRGB encode.
- Read from the code: planes at multiples of `2^n` own `2^n` cones, so when the quadrant width is not a multiple of `2^n` the last plane is partial and its high cones are never stored, which matches the author's note about problems at non-power-of-two resolutions; the spiral takes the square root of a negative number for inner balls when its time term is large; and an odd-width buffer puts its last column in the wrong frustum.

The community timing table's "512², 4×4 px light, 10 cascades, 0.88 ms" row is a build of the same kind ([holographic RC](holographic_rc.md#performance)).

## jason.today/hrc

The page serves no article text; the HRC code is in its inline scripts ([HRC notes](../sources/2026_holographic_rc.md#jasontodayhrc)). The author's earlier RC articles are in [2D articles and demos](2d_articles_and_demos.md#jasontoday-jason-mcghee).

- **Defaults.** Probes at 1 px spacing (`hrcExtentScales` [0.25, 0.5, 1, 2], index 2), linear upscale, density scale 0.25, footprint seeding on, exposure 1, sRGB exponent 2.2, sun off. Four direction fields come from axis swaps and flips of the probe grid.
- **Seeding.** Transmittance `t = exp(−densityScale·spacing·(−ln max(1 − α, 10^−4)))`, that is `(1 − α)^(spacing/4)` by default, and 0 for `α ≥ 0.999`. Emission is the part of the scene colour above 1, `max(rgb − 1, 0)`, and the seeded radiance is `(1 − t)·source^2.2`. When the spacing exceeds 1.01 px, the seed averages 2×2, 4×4 or 8×8 sub-samples. Each axis pair has one atlas holding a direction and its opposite.
- **Merging.** `(near.r + far.r·near.t, near.t·far.t)`; an extended ray averages two such merges of lower-level rays in radiance and transmittance. Cone weights are slope-bin widths `atan2(2s − 2n + 2, 2n) − atan2(2s − 2n, 2n)` with `n = 2^level`, π/4 at level 0. Even probes average two phases and odd probes use one; the comments say the phases alternate along the probe axis at level 0, which a 0.25/0.5/0.25 filter removes. The output sums the four direction fields with a 4×2 kernel and clamps at 0.
- **Sky**, only with the sun on: `max(0, cos(ray − sun))^(4/sunDistance)` in sun colour (0.95, 0.9, 0.8) and sky colour (0.2, 0.24, 0.35), scaled by 3 and mixed 0.7/0.3.
- **Luminance and colour split**, the default ("Luminance + 0.5x Scale Color"). HRC runs at full resolution on Rec. 709 luminance and separately on colour averaged over `k × k` blocks with `k` = 2 (or 4). A block's averaged radiance `j` and transmittance `t` become `J = j·Σ_{i<k} t^i` and `T = t^k`, so a coarse texel stands for `k` fine steps. The result is `y·c/luma(c)`, with `y` the full-resolution luminance and `c` the bilinearly upsampled colour, `y` alone where `luma(c) ≤ 10^−8`, and a clamp at 64512. Colour HRC then costs `1/k²` of the probes, while shadow edges keep full resolution in luminance and colour bleeds at `k`-pixel resolution (inference).
- **Storage.** Radiance R11G11B10F and transmittance R16F; packed luminance RGBA16F by default, or RGBA8, which the UI says halves the packed storage but can lose faint light.

`J = j·Σ t^i` is the closed form of merging `k` identical cells front to back, so the coarse colour pass is exactly a fine pass over a medium that is uniform within each block (derived from the merge operator). The luminance pass carries one radiance channel instead of three, the same kind of saving as the community's single transmittance channel (inference).

## nihil

entropylost/nihil, a CPU test (Rust, 512², 10 cascades) that treats each line of probes as a continuous function of position and angle, discretized and interpolated bilinearly. Its README says it "functions significantly worse than normal HRC" ([reference codes](../sources/2025_hrc_and_2d_reference_implementations.md#nihil-hrc-with-continuous-line-functions)).

- Only the +x frame exists. Cascade `i` has vertical lines `2^i` px apart, 512 probes 1 px apart on each, and `2^i` angles across ±45° at `((a + 0.5)/N − 0.5)·π/2`.
- Each texel traces its own segment to the next cascade's line once, then merges with the next cascade sampled on a 100 × 100 grid of offsets over ±1 probe and ±1 angle with tent weights, each sample projected to the next line and read bilinearly. The per-sample trace is commented out, so all samples reuse the centre ray.
- Segments use `T = exp(−σL)` and radiance `emission·(1 − T)` through a 2D DDA. The output image is the single +x ray of cascade 0, not a full fluence.
- Every other line of a cascade lies exactly on a line of the next, so its projected segment has length zero (derived). The cost is about 2.6 M texels times 10,000 samples (derived, not measured).

nihil's angles are equal-angle (`π/2` split evenly), not equal-tangent like the paper's, and its tent-weighted resampling is the footprint integration that the resampling view of RC favours ([light transport alternatives](light_transport_alternatives.md#resampling-view-of-rc)); with the per-sample trace disabled, the occlusion it resamples is the centre ray's, which may explain why it does worse (inference).

## hrcviz and hrcviz2

entropylost's visualizers ([reference codes](../sources/2025_hrc_and_2d_reference_implementations.md#entropylosts-visualizers-hrcviz-and-hrcviz2)):

- **Indexing (hrcviz).** A 32 × 32 grid of index cells over 512 px shows which index lines pass through a hovered cell, with the stroke alpha set by the chord length. Seven schemes: left and right edge points, left point and slope, left and bottom points, radius and angle, height and angle, ring and angle, and two ring points.
- **Basis (hrcviz `basis.html`).** Four clicks define a basis element as the lines between two segments, plotted in slope–intercept space, where each element is a quadrilateral tile.
- **Weights.** Compares bilinear interpolation of the transmission weight `1/|probe − emitter|` over an 8 px grid with the exact value.
- **hrcviz2 (Rust, WebAssembly).** A frustum has a focus, a size `2^level` and an index in `[−size, size)`, covering slopes `[index/size, (index + 1)/size)`. Odd merges keep the focus and take children `2i` and `2i + 1` with weight 1; even merges step the focus by the lower and upper ray and weight children ½. A generator precomputes, for 6 levels, sparse per-pixel weights as transmission-weighted polygon areas, with error masks for each merge kind. The tiling is by clipped polygon areas, not Bresenham lines; the community notes link it as the indexing code of polygonal HRC ([holographic RC](holographic_rc.md#polygonal-cascades)).

The seven indexing schemes are the line parameterizations of the light-field literature in 2D: two edge points is the two-plane slab, point and slope is the slab with one plane at infinity, radius and angle is the `(r, θ)` form Levoy and Hanrahan measure density in ([holographic RC](holographic_rc.md#background-light-fields-and-line-space)) (inference).

## Half HRC

The half-HRC shader linked in the community notes under Yaazarai's name lives in brucelevis/Holographic-Radiance-Cascades ("Extremely naive implementation using 1/2 HRC model", `Half-HRC/shaders/Shd_HolographicRC/Shd_HolographicRC.fsh`); the Yaazarai repository of that name does not exist ([reference codes](../sources/2025_hrc_and_2d_reference_implementations.md#half-hrc-brucelevis-copy)).

- Probes are 1 px apart, but ray ends are 2 px apart, so each ray merges with two next-level rays at ±1 px across, and each lookup averages two texels: 8 taps at 1/8 each. A comment says ray ends are 1 px apart, which contradicts the 2 px step.
- Each frustum's cascades run top-down at 1920×1080 in 11 cascades of 2048² RGBA16F (`ceil(log2(1920))`). A hit returns the sRGB-decoded scene colour with alpha 0, and a miss merges. Rays are weighted by `1 − 0.5·|index − I/2|/(I/2)`, 1 at the centre ray and 0.5 at the edges.
- The four frustums are averaged with weights 0.25, each shifted one texel outward, and gamma-encoded. No timings.

Eleven 2048² RGBA16F cascades are 352 MiB for one frustum's set and four times that if each frustum keeps its own, while a 1920×1080 frame fills under half of each 2048² texture (derived).

## Connections

- **Two schools of extension.** The paper, amitabha, TypeGPU, lancimir, cute_framework and folkjs trace the lowest 2 or 3 levels; Volumetric-HRC, pixi-GI and hbattal extend from cascade 0. The sources conflict on which is better: the community reports crosses around small emitters when extensions start at cascade 0, and cute_framework and folkjs found Manhattan-shaped artifacts when they tried it, while Volumetric-HRC's README says starting at cascade 0 reduces aliasing and is more stable ([holographic RC](holographic_rc.md#building-rays-the-acceleration-structure)).
- **Two kinds of weight.** The codes that weight cones by angular width (paper, amitabha, lancimir, TypeGPU, folkjs, jason.today, pixi-GI, hbattal) agree up to a constant; the Shadertoys and the Unity port split each cone between its rays, and Half HRC and 4ctczl use no angular measure ([holographic RC](holographic_rc.md#merging-down)).
- **Multi-frame schedules.** 4ctczl, tfKyRw and WfyyDm spread levels over frames because Shadertoy limits passes, not because the method needs it; their latency is a host artifact, as with the plain RC Shadertoys ([2D Shadertoys](2d_shadertoys.md)).
- **Storage reuse.** TypeGPU's sequential quadrants with one shared pyramid are the memory-lean pattern; pixi-GI keeps `extent²·(cascades + 2)` texels and the paper's formula counts all four quadrants (derived above).
- **Lineage.** entropylost wrote amitabha, nihil, hrcviz and hrcviz2; Yaazarai wrote Volumetric-HRC, whose README describes a half-probe option, and is credited with a Half HRC repository that does not exist, so that shader's authorship is unresolved (it survives in brucelevis's copy); youssef_afella wrote the Unity port and both later Shadertoys; Suslik's 4ctczl descends from 4ctXD8 ([history and landscape](history_and_landscape.md)).

## Single-frame assessment

- The library codes (TypeGPU, pixi-GI with temporal off, folkjs, cute_framework, hbattal, lancimir, amitabha, Volumetric-HRC) recompute the whole solve every frame; only bounce light carries over, with one frame of latency in folkjs and cute_framework. TypeGPU's gallery example shows single-frame bounces by re-solving per bounce.
- The Shadertoy multi-frame rings are not a property of HRC and would collapse to one pass per level in a compute pipeline.
- Pass counts of 76 to 82 per frame at 512² to 1024² are the figure to plan dispatch overhead around; TypeGPU's 64-thread 1D dispatches with a row split above 65535 workgroups are a pattern that maps directly onto `RenderingDevice` compute lists (inference).

## Open questions

- How large is the accuracy gap between extending from cascade 0 and tracing the lowest three levels, measured on the same code against a reference?
- Does TypeGPU's 0.1 opacity gate in the integrate pass blur across thin occluders whose opacity differs by less than that?
- What are TypeGPU's, folkjs's and cute_framework's timings on one GPU at one size, so the codes can be compared without the cross-hardware normalization used in [holographic RC](holographic_rc.md#measured-results-and-the-cost-model)?
