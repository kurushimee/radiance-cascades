# @typegpu/radiance-cascades

| | |
|---|---|
| Author | Software Mansion |
| Date | 2026-10-12 (last commit touching the package: a21e2ca8e) |
| Kind | library (WebGPU) |
| Link | https://github.com/software-mansion/TypeGPU/tree/main/packages/typegpu-radiance-cascades |

@typegpu/radiance-cascades (version 0.12.1; 0.12.2 at commit 7af6a9e) computes 2D lighting for TypeGPU through two runners: an SDF runner that ray-marches a user signed distance function through a stack of cascade layers, and a holographic runner that solves light transport over a pixel grid with per-pixel emission and extinction. Both runners are created with `create`, recomputed with `run()`, and expose a texture (`output`) that the app samples in its own shader. All GPU code is TGSL (functions marked `'use gpu'`, compiled through unplugin-typegpu); the package contains no hand-written WGSL.

## Guide

Holographic scene inputs (guide table):

| Input | Meaning |
|---|---|
| `size` | Material grid and lighting texture dimensions in pixels |
| `medium(pixel)` | Emitted light and extinction of one pixel |
| `transmission` | `'scalar'` (default) for one extinction value, or `'rgb'` for one per channel |
| `source(pixel, incident)` | Optional extra emission |
| `tracedLevels` | Cascade levels traced directly before merging |

Holographic units and conventions (guide):

- `medium(pixel)` receives integer pixel coordinates. It returns emitted light in linear RGB and extinction in inverse pixels.
- Emission is linear radiance added per pixel of travel. Extinction is a nonnegative value in inverse pixels. After `s` pixels, a fraction `e^(-extinction * s)` of light remains.
- An opaque emitter appears with radiance `emission / extinction`. Example: emission `[16, 8, 4]` with extinction 16 shows as `[1, 0.5, 0.25]`.
- Extinction 16 passes about 1e-7 of the light crossing one pixel.
- Guide text: "Use finite values, since infinity is not treated as fully opaque."
- Colored transmission: for transmission `T` through `s` pixels, use extinction `-log(T) / s` per channel. Guide example: `[0.9, 0.1, 0.01]` over 10 pixels gives roughly `[0.0105, 0.2303, 0.4605]`.
- Light travels in straight lines. The guide states there is no refraction or dispersion.
- For expensive materials, the guide suggests rasterizing the scene into a texture and reading it in `medium` with `textureLoad`.

Scattering (guide, "Sources and scattering"):

- `source(pixel, incident)` returns extra emission for a pixel. `incident` is the light arriving at that pixel from the previous pass.
- `run({ iterations })` runs the solve several times. On the first pass, `incident` is zero. Each later pass gives `source` the previous pass's lighting (the same values as `runner.output`). Each pass adds one bounce.
- Every `run()` starts from darkness, so bounces do not carry over between runs.
- For isotropic scattering, add the scattering coefficient to extinction and return `scattering * incident` from `source`. The guide example stores absorption in `.rgb` and scattering in `.a` of a medium texture and uses `runner.run({ iterations: 3 })`.
- `incident` is averaged over all directions. The guide says this is not enough for forward or backward scattering.
- Neither callback may read `runner.output` or `runner.sectors`. Use `incident` instead.
- Guide caution: the runner does not check energy conservation. If `source` returns more light than the medium removes, the scene grows brighter with each iteration.

Using holographic output (guide):

- `runner.output` holds the light reaching each pixel. Sample it with the same `uv` as the scene.
- Guide composite: `scene.rgb + light * (1 - scene.a)`, where `scene.a` is 1 on solid pixels.
- Light values are linear and can exceed 1 near bright emitters. The guide suggests scaling or tone mapping.
- `runner.sectors` is a texture array with four layers, one per side. The guide says `+Y` points down. The four layers add up to `output` before its smoothing. The guide uses them to light surfaces by their normals.
- `output` and `sectors` are `rgba16float`, owned by the runner, and destroyed by `destroy()`.

Holographic quality and cost (guide):

- `size` sets both the material grid and the lighting resolution. Memory grows as `O(N^2 log N)`.
- Guide memory table, scalar transmission, no source: 256x256 = 9 MiB, 512x512 = 38 MiB, 1024x1024 = 160 MiB, 2048x2048 = 672 MiB. These match the `getLayout` byte formula (checked by hand for 256, 512 and 1024).
- RGB transmission stores 12 bytes per interval instead of 8.
- A source adds 8 bytes per pixel and one dispatch per iteration.
- The guide says `runner.byteSize` reports "the exact allocation for the current configuration" (see Issues).
- `tracedLevels`: short intervals read the medium directly. The default 3 traces spans of 1, 2 and 4 pixels. Each extra traced level doubles the longest traced span. This means more medium reads and fewer approximate joins for the same memory.
- Guide diagrams: "traced-levels" (short intervals read the medium, longer ones are joined from two shorter ones) and "merge" (where the straight path misses an interval end, two bent paths stand in for it).
- Guide limitations: domain is finite with a black exterior; emission is isotropic; surface reflection and refraction are not built in; long paths and reconstruction are approximate; half-precision storage limits accuracy in very dim and high-dynamic-range scenes; both dimensions must be at least 2 pixels.

SDF runner guidance (guide):

- Scene callbacks receive `uv` from 0 to 1 on each axis.
- `sdf(uv)` returns signed distance: positive outside, zero on the surface, negative inside. Distances use the shorter side of the scene as 1. Example: in a 1024 x 512 scene, 10 pixels is `10 / 512`.
- `emission(uv)` returns linear RGB emitted light, not material color. Return zero for a non-emitting obstacle. Values above 1 are allowed.
- `sdfResolution` is the distance-texture size, or the desired surface-detail resolution for an analytic SDF. It does not allocate a distance texture.
- `size` is the lighting texture size. It can be smaller than the canvas.
- For rectangular scenes, the scene aspect defaults to the output width divided by height. Set `renderAspect` when the lighting texture aspect differs. Guide example: a square lighting texture covering a 1024 x 512 scene needs `renderAspect: 2`.
- The built-in tracer treats surfaces as opaque. Surface reflection and extra bounces are up to the app.

Image-based SDF scenes (guide): the guide uses `@typegpu/sdf` `createJumpFlood`. Source texture is `rgba8unorm`, 2048 x 2048, alpha marks solid pixels. `classify` reads alpha greater than 0.5. `getSdf` returns `signedDist / min(size)`. `getColor` returns the source RGB with alpha 1. The lighting runner uses `sdfResolution` equal to the flood size and preview size 512 x 512. `updateLighting()` runs the flood and then the lighting runner, and must be called again after editing the source image.

SDF quality and cost (guide):

- `size` sets lighting resolution. Smaller costs less and resolves less detail.
- `baseStoredRayDim` sets how many directions each lighting sample traces, independent of `size`. The option comment gives 1 (default) = 4 rays, 2 = 16 rays, 4 = 64 rays at the finest resolution.
- Each doubling of `baseStoredRayDim` doubles the internal textures on each axis. At 4, a lighting texture with a diagonal of 4096 pixels or more exceeds the default 8192-pixel texture size limit (the guide's claim; consistent with the cascade size formula below).
- `mergeMode`: `'hardware'` (default) uses the faster interpolation path. `'bilinear-fix'` does extra visibility checks to reduce light leaking at a higher cost.

SDF tracing controls (guide table, defaults from code):

| Option | Default | Effect (guide) |
|---|---|---|
| `maxRaySteps` | 64 | Maximum steps per ray; must be a positive integer |
| `stepSafety` | 1 | Step multiplier in (0, 1]; smaller values step shorter |
| `erodeBiasProbes` | 1 | Shrinks every obstacle by this distance before tracing |
| `epsProbes` | 0.25 | Surface hit tolerance |
| `minStepProbes` | 0.125 | Minimum step length |

- The three `...Probes` distances use the finest lighting-sample spacing as their unit. `1` equals `1 / min(baseProbes)` in scene units.
- The hit tolerance and minimum step are also limited by `sdfResolution` (see Issues).

SDF custom tracing (guide): the `rayMarch` callback replaces the built-in tracer in both merge modes. It receives `(origin, direction, startT, endT, eps, minStep, bias)` and returns `RayMarchResult({ color, transmittance })`. `color` is accumulated linear RGB over the segment. `transmittance` is 1 for transparent, 0 for opaque, or between. Positions are `origin + direction * t`, with `t` in scene units. `maxRaySteps` and `stepSafety` only affect the built-in tracer.

## Source files

Line counts and locations at commit 7af6a9e (`packages/typegpu-radiance-cascades/`):

| File | Lines | Contents |
|---|---|---|
| `src/index.ts` | 12 | exports `create`, the deprecated `createRadianceCascades`, the slots `sdfSlot`, `emissionSlot` and `rayMarchSlot`, `defaultRayMarch`, `RayMarchResult`, `maxRayStepsAccess`, `rayMarchStepSafetyAccess`, and the types `BaseStoredRayDim` and `MergeMode` |
| `src/runner.ts` | 311 | SDF `create()`: option defaults (lines 118-124), the tracing constants (lines 139-142), the two ping-pong cascade textures, top-down cascade passes and the build pass; exposes `run`, `with`, `initSync`, `initAsync` and `destroy` |
| `src/cascades.ts` | 434 | `getCascadeInfo` (43-107), `defaultRayMarch` (138-162; hit test at 152, step at 156, step cap at 145), segment trace (164-183), layer parameters (185-196), bind group (198-203), `traceHardwareMergeRay` (225-256), `bilinearWeight` (258-263), `traceBilinearFixMergeRay` (293-313), `rayDirection` (315-321), `cascadePassCompute` with the 2 × 2 pre-average (326-379), `buildRadianceFieldCompute` (394 on) |
| `src/holographic/index.ts` | 448 | holographic `create()`, passes and pipelines |
| `src/holographic/layout.ts` | 26 | level count, interval counts `planeCount·(2^l + 1)`, fluence count, byte size |
| `src/holographic/transport.ts` | 73 | `Interval`, f16 packing, `over`, `average`, `integrate` |
| `README.md` | 78 | quick start for both APIs; `sdfResolution` at lines 46 and 63-64 |

`tests/cascades.test.ts` and `tests/holographic.test.ts` were not read.

## SDF runner

### Signature and options

Overloads of `create(options)`:

- With `size` and no `output`: returns `RadianceCascadesExecutor` (output type `RadianceTexture & SampledFlag`).
- With `output`: returns `RadianceCascadesExecutor<TOutput>`.

| Option | Required | Default | Meaning |
|---|---|---|---|
| `root` | yes | | `TgpuRoot` |
| `sdf` | yes | | `(uv: v2f) => f32`; scene distance in shorter-side units |
| `emission` | yes | | `(uv: v2f) => v3f`; linear RGB emitted light |
| `sdfResolution` | yes | | `{ width, height }`, both must be > 0 |
| `size` | yes, unless `output` reports its size | | Lighting texture size |
| `output` | no | internal texture | `TgpuTexture` (rgba16float, storage and sampled) or a write-only storage view |
| `renderAspect` | no | output width / height | Scene aspect; must be > 0 |
| `erodeBiasProbes` | no | 1 | Must be >= 0 |
| `epsProbes` | no | 0.25 | Must be >= 0 |
| `minStepProbes` | no | 0.125 | Must be >= 0 |
| `maxRaySteps` | no | 64 | Positive integer |
| `stepSafety` | no | 1 | In (0, 1] |
| `baseStoredRayDim` | no | 1 | `1`, `2` or `4` |
| `mergeMode` | no | `'hardware'` | `'hardware'` or `'bilinear-fix'` |
| `rayMarch` | no | `defaultRayMarch` | Custom tracer, same signature as `defaultRayMarch` |

### Derived constants

Inputs: output width `W` and height `H` (from `output` or `size`), sdf resolution `Sw x Sh`, `renderAspect` `a` (default `W/H`). Let `aspect = W/H` and `diag = hypot(W, H)`.

1. `P = max(16, 2^floor(log2(diag)))`.
2. Base probes `B`: if `aspect >= 1`, `B = [P, max(16, round(P / aspect))]`. Otherwise `B = [max(16, round(P * aspect)), P]`.
3. `interval0 = 1 / min(B)`.
4. `maxRange = hypot(a, 1) / min(a, 1)`.
5. Cascade count `N = max(5, ceil(log2(3 * maxRange / interval0 + 1) / 2))`.
6. `cascadeDim = [max(B_x * base, base * 2^(N-1)), max(B_y * base, base * 2^(N-1))]`, where `base = baseStoredRayDim`. Each cascade texture is a 2D `rgba16float` texture of this size.
7. For layer `L` from 0 to N-1 (0 is finest):
   - `probes_L = max(1, floor(B / 2^L))` per axis.
   - `probesU_L = max(1, floor(B / 2^(L+1)))` per axis (probes of the layer above).
   - `R_L = raysDimStored = base * 2^L` per axis.
   - `validDim_L = probes_L * R_L` per axis. Always `<= cascadeDim`.
   - `startT_L = interval0 * (4^L - 1) / 3`.
   - `endT_L = startT_L + interval0 * 4^L`.
   - Actual rays per probe: `(2 * R_L)^2`.
8. Per-layer tracing constants (shared by all layers):
   - `cascadeProbesMin = min(B)`.
   - `sdfTexelMin = 1 / min(Sw, Sh)`.
   - `eps = max(sdfTexelMin, epsProbes / cascadeProbesMin)`.
   - `minStep = max(0.5 * sdfTexelMin, minStepProbes / cascadeProbesMin)`.
   - `hitBias = erodeBiasProbes / cascadeProbesMin`.
   - `aspect` in layer params is the render aspect `a`.

Worked example, output 512 x 512, default options: `B = [512, 512]`, `interval0 = 1/512`, `maxRange = sqrt(2)`, `N = 6`, `cascadeDim = [512, 512]`.

| Layer | probes per axis | R (stored dirs per axis) | actual rays per probe | startT | endT (scene units) |
|---|---|---|---|---|---|
| 0 | 512 | 1 | 4 | 0 | 1/512 |
| 1 | 256 | 2 | 16 | 1/512 | 5/512 |
| 2 | 128 | 4 | 64 | 5/512 | 21/512 |
| 3 | 64 | 8 | 256 | 21/512 | 85/512 |
| 4 | 32 | 16 | 1024 | 85/512 | 341/512 |
| 5 | 16 | 32 | 4096 | 341/512 | 1365/512 |

Every layer has `validDim = [512, 512]`, so each pass dispatches 64 x 64 workgroups.

### Passes per `run()`

The runner records `N + 1` compute dispatches in one compute pass (top to bottom):

1. Cascade pass for layer `N-1`, then `N-2`, ..., then `0`. The pipelines array is reversed after construction (`prebuiltCascadePasses.reverse()`), so this order holds.
2. Build pass for the output.

Pipelines: top layer (`hasUpperCascade = false`) and all other layers (`hasUpperCascade = true`) use the same `cascadePassCompute` with different slot values. The build pass is a separate pipeline.

Ping-pong: two textures `A` and `B`. Layer `L` writes to `A` when `(N - 1 - L)` is even, otherwise to `B`. It reads the upper layer from the other texture. Layer 0 therefore lives in `A` when `(N - 1)` is even. The build pass reads layer 0 from that texture.

Bindings:

- Layer pass: uniform `CascadeLayerParams` (fields: `probes`, `probesU`, `validDim` as `vec2u`; `raysDimStored` as `u32`; `startT`, `endT`, `aspect`, `eps`, `minStep`, `hitBias` as `f32`); `upper` as `texture2d<f32>`; `upperSampler` (filtering); `dst` as write-only `rgba16float` storage texture.
- Build pass: uniform `BuildRadianceFieldParams` (`probes: vec2f`, set to `B`); `src` texture; `srcSampler`; `dst` storage texture (the output).
- Sampler: linear magnification and minification, default address modes.

Workgroups: layer and build passes both use `@workgroup_size(8, 8)`. Layer dispatch is `ceil(validDim / 8)` per axis. Build dispatch is `ceil(W / 8)` by `ceil(H / 8)`.

### Cascade pass (per thread)

Thread index `g = (gx, gy)`, guarded by `g < validDim`.

- Direction index `d = g mod R` (per axis) and probe index `p = floor(g / R)` (per axis). Threads are arranged so that nearby threads share a probe. Storage is direction-major.
- Probe position: `probePos = (p + 0.5) / probes_L` in unit-square uv.
- Output texel: `d * probes_L + p`. The used region of the texture is `validDim`.
- The four actual rays of stored direction `d` are `dirActual = 2 * d + (i & 1, i >> 1)` for `i` in 0..3.
- Ray index: `k = morton2D(dirActual.x, dirActual.y)`. The angle is `theta = (k + 0.5) / (4 * R^2) * 2 * pi - pi`, using the actual ray count `(2R)^2`.
- Direction: `(cos theta, -sin theta)`. If `aspect >= 1`, the x component is divided by `aspect`. If `aspect < 1`, the y component is multiplied by `aspect`. This makes the direction unit length in shorter-side units.
- `exitT` is the distance from `probePos` to the unit-square boundary along the direction (`rayBoxExitT`).
- If `exitT <= startT`, the ray contributes `(0, 0, 0, 1)`: no light, full transmission.
- Else if an upper layer exists, the merge runs (below). Else the top layer marches from `startT` to `min(endT, exitT)`.
- The stored value is the average of the four actual rays: rgb is the mean color, alpha is the mean transmittance.

Built-in ray march (`defaultRayMarch`), arguments `(probePos, rayDir, startT, endT, eps, minStep, bias)`:

- Start at `t = startT`. Loop for up to `maxRaySteps` iterations.
- Stop when `t > endT` (no hit).
- `hitDist = sdf(pos) + bias` where `pos = probePos + rayDir * t`.
- If `hitDist <= eps`: return color `emission(pos)` and transmittance 0.
- Else `t += max(hitDist * stepSafety, minStep)`.
- Return color 0 and transmittance 1 when no hit.
- `bias` is positive by default, so obstacles are effectively shrunk by `erodeBiasProbes` probe spacings.

Hardware merge (default, `mergeMode = 'hardware'`):

- `near = rayMarch(probePos, dir, startT, min(endT, exitT), eps, minStep, hitBias)`.
- If `near.transmittance > 0.01` and `exitT > endT`, sample the upper layer:
  - `tileOrigin = dirActual * probesU`
  - `probePixel = clamp(probePos * probesU, 0.5, probesU - 0.5)`
  - `uv = (tileOrigin + probePixel) / upperTextureSize`
  - Sample with linear filtering at level 0.
  - Result: color `near.color + up.rgb * near.transmittance`; transmittance `near.transmittance * up.a`.
- Else the result is `near`.
- The upper stored directions are indexed by `dirActual` because the upper layer has `2R` stored directions per axis, which equals the actual count per axis of this layer.

Bilinear-fix merge (`mergeMode = 'bilinear-fix'`):

- `samplePos = clamp(probePos * probesU - 0.5, 0, probesU - 1)`. `base = floor(samplePos)`, `f = samplePos - base`.
- For each corner `c = (cx, cy)` in {0,1}^2 with offset `(cx, cy)`:
  - `upperProbe = min(base + c, probesU - 1)`.
  - `weight = (cx == 0 ? 1 - f.x : f.x) * (cy == 0 ? 1 - f.y : f.y)`.
  - If `weight > 0`: `upperProbePos = (upperProbe + 0.5) / probesU`, `upperExitT = rayBoxExitT(upperProbePos, dir)`.
  - `near = traceSegment(probePos + dir * startT, upperProbePos + dir * endT, aspect, eps, minStep, bias)`. `traceSegment` converts the uv delta to a unit-metric direction and calls `rayMarch` with start 0.
  - If `near.transmittance > 0.01` and `upperExitT > endT`: fetch the upper texel `tileOrigin + upperProbe` with `textureLoad` (no filtering) and combine as in the hardware path.
  - Accumulate `result * weight`.
- The four bilinear weights sum to 1. Corners beyond the last probe are clamped to it.

Build pass (per output pixel `g`):

- `uv = (g + 0.5) / (W, H)`.
- `probePixel = clamp(uv * B, 0.5, B - 0.5)`.
- `uvStride = B / textureSize` (per axis).
- Sum over `x, y` in `[0, base)`: sample the layer-0 texture at `probePixel / textureSize + (x, y) * uvStride`, linear filtering, and add rgb.
- Output: `(sum / base^2, 1)`. Alpha is always 1, so transmittance is not exposed in `output`.

## Holographic runner

### Signature and options

`create(options)` returns `Executor`.

| Option | Required | Default | Meaning |
|---|---|---|---|
| `root` | yes | | `TgpuRoot` |
| `size` | yes | | `{ width, height }`. Not validated (see Issues) |
| `medium(pixel: v2u)` | yes | | Returns `{ emission: v3f, extinction }`. `extinction` is `number` for scalar transmission and `v3f` for rgb |
| `transmission` | no | `'scalar'` | `'scalar'` or `'rgb'` |
| `source(pixel: v2u, incident: v3f)` | no | none | Returns extra emission (`v3f`) per pixel |
| `tracedLevels` | no | 3 | Positive integer; otherwise throws `tracedLevels must be a positive integer.` |

`medium` is wrapped with `tgpu.fn` and bound to a slot on the root, so captured TypeGPU resources are bound automatically.

Outputs:
- `output`: `rgba16float`, size `[W, H]`, storage and sampled. Angular mean radiance normalized by 2 pi.
- `sectors`: `rgba16float`, size `[W, H, 4]` (2D array), storage and sampled. Layer `q` holds the light arriving from one side. Layer 0 is `+X`, 1 is `+Y`, 2 is `-X`, 3 is `-Y` (guide, and display order in the drawing example).

### Data types and packing

Interval (`Interval` struct in transport): `radiance: vec3f`, `transmission: f32` (scalar) or `vec3f` (rgb).

Packed interval (stored in storage buffers):

- Scalar: `array<u32, 2>` (8 bytes). Word 0 = `pack2x16float(radiance.rg)`. Word 1 = `pack2x16float(radiance.b, transmission)`.
- RGB: `array<u32, 3>` (12 bytes). Word 2 = `pack2x16float(transmission.gb)`.
- `empty()` is radiance 0 and transmission 1 (rgb: `vec3(1)`).

Transport operations (`transport.ts`):

- `over(near, far)`: `radiance = near.radiance + near.transmission * far.radiance`; `transmission = near.transmission * far.transmission`.
- `average(a, b)`: component-wise mean of radiance and transmission.
- `integrate(emission, extinction, length)`: `T = exp(-sigma * length)`. `integral = (1 - T) / sigma` when `sigma > 1e-5`, else `length`. Radiance = `emission * integral`, transmission = `T`. Scalar uses `sigma.r` for the transmission. RGB uses per-channel values.

Fluence (radiance) values are packed as `vec2u` with `pack2x16float` of `(rgb, 0)`.

### Buffers and layout (`layout.ts`)

Given `size = (W, H)`:

- `levels = ceil(log2(max(W, H)))`.
- `planeCount(L) = max over axes a of (L <= ceil(log2(size_a)) ? ceil(size_a / 2^L) * size_other : 0)`.
- Interval pyramid: `intervalCounts[L] = planeCount(L) * (2^L + 1)` for `L` in `0..levels`. One storage buffer of `Packed` per level.
- Fluence count: `fluenceCount = max over L of planeCount(L) * 2^L`.
- Two radiance buffers, each of `fluenceCount` elements of `vec2u`. They alternate by level parity.
- Sectors texture (above) and output texture.
- Feedback buffer (only with `source`): mutable `vec2u` array of `W * H` elements.
- `bytes = sum(intervalCounts) * 8 + fluenceCount * 16 + W * H * 40`. The 40 bytes per pixel are 32 for four `rgba16float` sector layers plus 8 for `output`.
- `byteSize = bytes + (rgb ? sum(intervalCounts) * 4 : 0) + (source ? W * H * 8 : 0)`.
- Checked by hand: 256 x 256 gives 9.0 MiB, 512 x 512 gives 38.0 MiB, 1024 x 1024 gives 160.0 MiB.

### Quadrant sweeps

The solve runs four sweeps, one per quadrant `q` in 0..3. Each sweep is the same 1D algorithm applied to a rotated grid.

- Sweep width `W_q = size[q mod 2]` (the length along the sweep, local `x`). Sweep height `H_q = size[1 - (q mod 2)]` (local `y`, rows).
- `levels_q = ceil(log2(W_q))`.
- Local to world pixel mapping, with `(size0, size1) = (W, H)`:
  - q0: `(x, y)`
  - q1: `(size0 - 1 - y, x)`
  - q2: `(size0 - 1 - x, size1 - 1 - y)`
  - q3: `(y, size1 - 1 - x)`
- Sector output: the value computed for local column `x` is stored in the sector texture at local pixel `x - 1`, layer `q`. For `x = 0` the stored value is zero, stored at local pixel `W_q - 1`. The edge pixel facing the exterior is therefore zero.

Per sweep, passes run in this order:

1. Up-sweep levels `L = 0 .. levels_q` (inclusive).
2. Down-sweep levels `L = levels_q - 1 .. 0`.

After all four sweeps: one integrate pass.

Passes per iteration: `sum over q of (2 * levels_q + 1) + 1`. For 512 x 512: `4 * 19 + 1 = 77`. With `source`, one extra source pass per iteration.

Workgroups: all holographic passes use `@workgroup_size(64)` with 1D dispatch. `getDispatchSize(count)` returns `[ceil(count / (64 * rows)), rows]` with `rows = ceil(count / (65535 * 64))`. Thread id is `gid.x + gid.y * (dispatch[0] * 64)`. Up- and down-sweep pipelines are cached by key: `up_WxH_lL` (plus `_qQ` for traced levels) and `down_WxH_lL` (plus `_qQ` at level 0). The integrate and source pipelines are created once each.

### Up-sweep (intervals)

For level `L`, let `s = 2^L`, `C = ceil(W_q / s)` columns, `D = s + 1` directions for traced levels (`L < tracedLevels`), or `D = s/2 + 1` directions for paired levels (`L >= tracedLevels`). Thread count is `C * H_q * D`.

Thread decomposition: `y = id mod H_q`, `d = floor(id / H_q) mod D`, `x = floor(id / (H_q * D))`. Storage index: `(x * (s + 1) + dirActual) * H_q + y`, where `dirActual = d` (traced) or `2d` (paired).

Traced levels:

- The segment starts at pixel `(x * s, y)` and ends at offset `(s, 2 * dirActual - s)`. Slope is `(2 dirActual - s) / s`, in [-1, 1].
- The walk visits grid cells with pixel centers at integers and cell boundaries at half-integers. It advances in `x` by one pixel per crossing and in `y` by one pixel per crossing with sign `+1` when the slope is non-negative, else `-1`.
- Per cell: `value = over(value, integrate(emission(world) + feedback(world), extinction(world), cellLength))`. `feedback` is zero unless `source` is set.
- Start with `value = empty()`. Stop when the walk leaves the sweep (`x >= W_q`, `y < 0`, `y >= H_q`) or when the distance reaches the segment length. The loop runs at most `2s + 1` cells.

Paired levels (`L >= tracedLevels`), for even `dirActual` with `dh = dirActual / 2` and `off = 2 * dh - s/2`:

- `near = I[L-1](2x, y, dh)`, `far = I[L-1](2x+1, y + off, dh)`, `value = over(near, far)`.
- Odd entries (`dirActual + 1`) are written at index `+ H_q` (the next direction slot) when `dirActual < s`:
  - `lowerPath = over(near, I[L-1](2x+1, y + off, dh + 1))`
  - `upperPath = over(I[L-1](2x, y, dh + 1), I[L-1](2x+1, y + off + 2, dh))`
  - stored value = `average(lowerPath, upperPath)`.
- Every even entry is stored as `value`.

Out-of-range reads in the previous level return `empty()`.

### Down-sweep (fluence)

For level `L`, let `s = 2^L`, `C = ceil(W_q / s)` columns, `Cu = ceil(W_q / (2s))` upper columns. Thread count is `C * H_q * s`. Thread decomposition: `y = id mod H_q`, `d = floor(id / H_q) mod s`, `x = floor(id / (H_q * s))`. The radiance output index is `(x * s + d) * H_q + y`.

For each half `h` in {0, 1}:

- `b = d + h` (boundary index within level `L`).
- `ud = 2d + h` (upper fluence direction, 0..2s-1).
- Wedge angle fraction: `alpha = (atan(slope1) - atan(slope0)) / (2 pi)`, where `slope0 = (2 ud - 2s) / (2s)` and `slope1 = (2 (ud + 1) - 2s) / (2s)`.
- Segment:
  - If `x` is even: `far = I[L+1]((x/2) * (2s + 1) + 2b, at row y)`.
  - If `x` is odd: `near = I[L]((x * (s + 1) + b), at row y)`.
- Target row for the distant term: `ty = y + (2b - s) * (x even ? 2 : 1)`.
- `distant = R[L+1](floor(x/2) + 1, ty, ud)`, zero when `L` is the top down level (`L == levels_q - 1`) or out of range.
- `contribution = segment.radiance * alpha + segment.transmission * distant`.
- If `x` is even: `contribution = (contribution + R[L+1](floor(x/2), y, ud)) * 0.5`.
- `result = sum over h of contribution`.

Storage:

- `L > 0`: `R[L][(x * s + d) * H_q + y] = pack(vec4(result, 0))`.
- `L = 0`: sector texture at world pixel of local `(x - 1, y)` (or `(W_q - 1, y)` for `x = 0`), layer `q`. Value is `unpack(pack(result))` for `x > 0`, zero for `x = 0`. The unpack-pack round trip reproduces half-precision rounding before the texture store.

Radiance buffers alternate: `R[L]` is written at `radiance[L mod 2]`, and reads come from `radiance[1 - (L mod 2)]`.

### Integrate pass

Per pixel `p` (linear index `id = p.y * W + p.x`):

- `opacity(q) = exp(-extinction(q))` (per channel for rgb).
- `S(p) = sum over the four sector layers of sector(p)` (rgb).
- Neighbors in order: `+X`, `+Y`, `-X`, `-Y`. A neighbor is used when it is inside the grid and `|opacity(p) - opacity(n)| < 0.1` in every channel.
- `value = 4 * S(p) + sum of S(n) over used neighbors`. `weight = 4 + count of used neighbors`.
- `output(p) = (value / weight, 1)`.
- With `source`: `feedback[id] = pack(value / weight, 0)`.

### Source pass

Runs once per iteration before the sweeps. Two pipelines:

- First pipeline (iteration 0): `incident = 0`.
- Second pipeline (iterations 1 and later): `incident = unpack(feedback[id])`, which is the previous integrate output.

It writes `feedback[id] = pack(source(pixel, incident), 0)`. The traced cells read this value as extra emission at their world pixel (`feedback[world.y * W + world.x]`). Doc note from `source` docstring: "evaluated once per pixel before each solve."

### Holographic: notes on the model

- Intervals are straight segments of `2^L` columns. Each has a slope from a fixed set. The up-sweep builds them at doubling lengths.
- The down-sweep builds the radiance arriving at each interval end from larger intervals.
- Each sector layer holds the angle-weighted contributions from its quarter-circle, divided by 2 pi. The sum of the four layers is the angular mean, which is then averaged with neighbors of similar opacity.
- The guide cites "Freeman et al. (2025)" as the source of the interval and fluence recurrences (code comment on `create`).

## Examples

All three examples are in `apps/typegpu-docs/src/examples/rendering/`. Each has `meta.json` (title, description, category `rendering`, tags, coolFactor 8).

### radiance-cascades (from scratch, no package use)

- Title: "Radiance Cascades". Description: "Demonstrates real-time 2D global illumination by tracing and merging progressively larger radiance cascades."
- The file header says it is a from-scratch implementation and points to the package guide and the drawing example.
- Scene (`scene.ts`): `sceneSDF` returns distance and color. Three emissive disks (red, green, blue, radius 0.05), two emissive-free boxes, one grey disk (radius 0.1). Element data is stored in a `SceneData` struct uniform. The scene is in uv units (0 to 1).
- Parameters: `LIGHTING_RESOLUTION = 0.35`, `maxOutputResolution = 1024`. Output probes = `min(canvas.width, 1024)`. Cascade probes = `2^round(log2(diag * 0.35))`, with `diag = outputProbes * sqrt(2)`. Cascade texture size `cascadeDim = 2 * cascadeProbes` (square).
- Cascade count: `ceil(log2((1.5 * 3) / interval0 + 1) / 2)`. There is no minimum of 5 and the max range is fixed at 1.5 (the package uses `maxRange` and a minimum of 5).
- Radiance field texture: square, `outputProbes` by `outputProbes`.
- Two ping-pong texture arrays with one array layer per cascade (kept for all layers), instead of two 2D textures.
- Direction layout: layer `L` uses `raysDimStored = 2 << L` and `raysDimActual = 2 * raysDimStored`. Texel layout is `dirStored * probes + probe` as in the package.
- Ray march: `for step < 64`, `hit.dist <= eps` ends the ray, `t += max(dist, minStep)`. `eps = 0.5 / baseProbeCount`, `minStep = 0.25 / baseProbeCount`. No `erodeBias`, no `stepSafety`.
- Merge: samples the upper layer (linear filter) whenever `T > 0.01` and `layer + 1 < cascadeAmount`. No `exitT > endT` check.
- Final gather: 2 x 2 texel samples of layer 0 (`probes` units), averaged (`sum * 0.25`).
- Display: `ACESFilm` on the field and surface colors; surface alpha from SDF smoothstep; `overlay` debug view.

### global-illumination ("Holographic Global Illumination")

- Description: "Explore color bleeding and successive diffuse bounces through a connected gallery. Drag to move the light."
- Scene (`scene.ts`): `sceneSize = 512`. An enclosing wall (`12 - sdBox2d(p - 256, (216, 216))`), twelve shapes (boxes and disks with albedo colors grey, blue, green, red, orange), combined by minimum distance with the albedo of the nearest shape. `normalAt(p, radius)` uses central differences of the scene SDF.
- Grid: 256 x 256, `cellSize = 512 / 256 = 2` scene units.
- Textures (all 256 x 256 `rgba16float`, storage and sampled): `base` (rgb = lamp emission, a = surface coverage), `emission` (the holographic medium emission), `medium` (rgb = extinction).
- Rasterize pass (`rasterize`): surface coverage `saturate(0.5 - sceneDistance / cellSize)`. Lamp coverage from a box SDF at `lampPosition` (half size `(2, 15)`, minus 3). `base = (lamp * 64 * cellSize, surface)`, written to `base` and `emission`. Medium extinction `max(surface, lamp) * 16 * cellSize` written to `medium`.
- Holographic runner: `hrc.create({ root, size: 256 x 256, medium })`. `medium` reads `emission.rgb` and `medium.r` (scalar transmission).
- Bounce pass (`bounce`): for pixels with `distance > -1.5 * cellSize` and `base.a > 0`, `source = base.rgb + reflected(p, surface, normal) * extinction`. Written to `emission` with alpha `base.a`. Then the lighting runner re-solves.
- `reflected(p, surface, normal)`: pushes the boundary point out along the normal (three iterations), samples the four sector layers at `boundary + normal * 1.5 cells` (uv), weights each sector by the sine difference of the lobe clipped to +-pi/2 around the normal angle, and multiplies by `2 * albedo`.
- Updates: `updateLighting` runs rasterize, then `lighting.run({ pass })`, then `bounces` times `(bounce, lighting.run({ pass }))`. Everything is in one compute pass. Runs only when `lightingDirty` is set (on lamp move or bounce count change).
- Display (`displayFragment`): a wall pixel shows `reflected(...) / pi`. Non-wall pixels show the lighting texture. Lamp adds `lamp * 4`. Tone map `color / (0.5 + max(rgb))`, then `linearToSrgb`. The gallery frame is a rounded box mask (`sdBox2d(p - 256, 220) - 12`).

### radiance-cascades-drawing ("Holographic Radiance Cascades (with drawing)")

- Description: "Draw emitters and occluders in a pixel scene lit by holographic radiance cascades."
- Medium: `emission = rgb * 16`, `extinction = alpha * 16`. Painted pixels are opaque (extinction 16) and show radiance equal to their color (emission divided by extinction).

## Issues and notes

- Guide: "Use finite values, since infinity is not treated as fully opaque." From reading the code (not run): with infinite extinction, `exp(-sigma * length)` is 0 (blocks light) and `(1 - T) / sigma` is 0 (so emission adds nothing). A zero-length cell with infinite extinction would evaluate `exp(-inf * 0)`, which is NaN.

### Behavior notes (from code)

- Holographic `run({ iterations: 0 })` records no solve passes. `output` keeps values from the previous run.
- Holographic `tracedLevels` larger than the number of levels (`ceil(log2(W_q))`) traces every level directly. No upper bound is checked.
- Holographic `byteSize` and the memory table use the same formula. The formula counts intervals as 8 bytes (scalar) or 12 bytes (rgb). The code's docstring calls it the "Logical size of the allocations owned by the executor" (`src/holographic/index.ts:82`), so it counts logical bytes; the guide's "exact allocation" says more than the code does.
- Holographic `size` is not validated: `create` throws only for `tracedLevels` (`src/holographic/index.ts:101-106`), although the guide requires both dimensions to be at least 2 pixels.
- SDF `output` alpha is always 1 (the build pass writes alpha 1). The per-pixel transmittance is not exposed.
- `sdfResolution` puts a floor under the hit tolerance and the minimum step (`runner.ts:140-142`): `eps` cannot drop below one SDF texel (`1/min(Sw, Sh)`) and `minStep` below half a texel, while `cascadeProbesMin` comes from the output size (`runner.ts:139`). With `P = min(B)` and `S = min(Sw, Sh)`, both floors win when `S < 4P` and both probe terms win when `S > 4P`. A 512² output over a 512² SDF gets `eps = 1/512`, four times the probe term; over a 4096² SDF it gets `eps = 0.25/512`. Steps never shrink below half a texel, so features thinner than that can be stepped over.
- SDF hardware merge samples the upper layer only when `exitT > endT`. The from-scratch example does not check this.
- SDF default ray marcher uses `hitDist = sdf + bias`, so the bias shrinks obstacles (positive bias). With `erodeBiasProbes = 0`, obstacles are not shrunk.
- A square lighting texture covering a non-square scene needs `renderAspect` set to the scene aspect (guide example: 2 for a 1024 x 512 scene).
- Holographic medium extinction is read through `hrcMedium` for both traced cells and the integrate pass (for the opacity similarity test).
- Holographic `source` writes its result into the feedback buffer during `updateSource`. The integrate pass overwrites the same buffer with the lighting output. The next iteration's source pass reads that output as `incident`.
- Holographic paired-level pipelines do not depend on the quadrant, so they are shared between quadrants with the same sweep size.

### Code comments of note

- SDF `cascadePassCompute`: "Group nearby directions for tracing locality; keep texture storage direction-major."
- Holographic down-sweep: "Preserve half precision rounding before the texture conversion."
- Holographic `create` doc: "Four-sector HRC, using the interval and fluence recurrences of Freeman et al. (2025)."
- Holographic `Executor.run` doc: a supplied encoder is not submitted and a supplied pass is not ended.
- The example `radiance-cascades` comment: "Ray intervals are distances in normalized scene space, not texture UV coordinates."

## Links found

| Link | Where | Notes |
|---|---|---|
| https://github.com/software-mansion/TypeGPU/tree/main/packages/typegpu-radiance-cascades | Header table of this file (task-provided) | Package directory; not present in any repo file |
| https://github.com/software-mansion/TypeGPU/tree/main/packages/typegpu-radiance-cascades/src | Guide | Source link |
| https://docs.swmansion.com/TypeGPU/ecosystem/typegpu-radiance-cascades/ | README, SDF example header | Guide page |
| https://docs.swmansion.com/TypeGPU/examples#example=rendering--radiance-cascades | Guide, SDF example header | Radiance Cascades example |
| https://docs.swmansion.com/TypeGPU/examples#example=rendering--radiance-cascades-drawing | Guide, SDF example header | Drawing example |
| https://docs.swmansion.com/TypeGPU/examples#example=rendering--global-illumination | Guide | Global Illumination example |
| http://arxiv.org/abs/2505.02041v1 | Found by arXiv search, not linked in repo | "Holographic Radiance Cascades for 2D Global Illumination", Rouli Freeman, Alexander Sannikov, Adrian Margel, 2025-05-04. The code comment cites "Freeman et al. (2025)". |
| http://arxiv.org/abs/2607.20384v2 | Found by arXiv search, not referenced by the package | "Split Radiance Cascades: Real-Time Global Illumination via Sparse Radiance Probes", Freeman, Sannikov, Pitt-Francis, 2026-07-22 |

- The original 2023 Sannikov radiance cascades work is not referenced anywhere in the package, guide, or examples.
