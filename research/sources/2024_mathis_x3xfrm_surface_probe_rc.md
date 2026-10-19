# Surface-probe 3D RC (Shadertoy X3XfRM) and a 2.5D screen-space attempt

The Shadertoy "Radiance Cascades 3D" (X3XfRM, by Mathis, 2024-11-02; the community wiki credits Suslik, but the Shadertoy page names Mathis) places probes on the scene's surfaces in UV space, so each surface is a 2D probe grid with hemisphere directions, and the problem keeps the surface memory scaling (`N·M0`). Shadertoy is behind a bot check, so these notes come from a Rust and wgpu port that keeps the original GLSL in `reference/shadertoy/`.

| | |
|---|---|
| Original | https://www.shadertoy.com/view/X3XfRM |
| Port | https://github.com/uziiDevelopment/providentia-cascades (Rust, wgpu 26, 2026-07) |

## Contents

- [Scene and atlas](#scene-and-atlas)
- [Hemisphere directions](#hemisphere-directions)
- [Trace](#trace)
- [Merge](#merge)
- [Final gather](#final-gather)
- [CorylusDonuts: 2.5D screen-space RC pseudocode](#corylusdonuts-25d-screen-space-rc-pseudocode)

## Scene and atlas

- The scene is an analytic box room (1 × 0.5 × 1) with an interior wall with two round holes, a mirror sphere and a mirror box, a moving sun and a sky. Rays are intersected analytically.
- Each cascade is one 1280×256 RGBA16F layer: the floor and ceiling take 256×256 texels each and six walls take 128×256 each, packed side by side without padding. The original uses a cube-map layout. There are six cascades.
- Cascade `c` probes are `P = 2^(c+1)` texels wide, so cascade 0 has 4 directions per probe and a probe every 1/128 units; each cascade has 4× the directions and ¼ the probes.
- The layout is direction-first: the probe index is `texel mod grid` and the direction index is `floor(texel / grid)`, with `grid = res / P`.

## Hemisphere directions

Directions per probe are a `P×P` square of texels mapped onto the hemisphere around the surface normal with concentric square rings:

- Offset `r = (k + 0.5) − P/2`, ring `m = max(|r.x|, |r.y|)`.
- Polar angle `θ = m/P·π` (the source has a typo, π written as 3.14192653, which the port keeps).
- Ring `m` has `4 + 8·floor(m)` azimuth bins around its four sides.
- Each sample's weight is its ring band's solid angle split across the ring, `(cos(θ − π/P) − cos(θ + π/P)) / (4 + 8·floor(m))`, times `cos θ` for the diffuse integral.

## Trace

- Rays start at the probe plus 0.001 along the normal. Cascades 0 to 4 trace up to `(1/64)·P·2` (0.0625 to 1.0 units); cascade 5 traces to infinity.
- The stored alpha is the hit distance (−1 on a miss), not a transmittance.
- A hit on lit geometry stores `(previous-frame irradiance at the hit + shadowed sun) × albedo`. So the bounce comes from the previous frame's cascade 0 and builds up over frames. Emitters store their emission; mirrors store zero; misses store the sky.

## Merge

Each ray is cross-faded into its parent by hit distance instead of being composited with transparency:

- `l = 1 − clamp((t_hit − minDist) / maxInterval, 0, 1)` and `result = radiance·l + parent·(1 − l)`, with `minDist = maxInterval = 1.5·P/256` (cascade 0 starts at 0 with double the length). Rays that hit within the cascade's range keep their own value; rays that miss hand over smoothly to the parent.
- The parent value blends four parent probes bilinearly. For each, the parent direction pointing at the child is chosen and its stored hit distance is read. The parent counts only if it missed or if the child lies closer than that hit distance plus 0.01 (scaled by `cos(π/2 − θ)`). Hidden parents get zero weight, and the sum is divided by `max(0.01, weight)`.
- The original merges from the previous frame's parent cascade, because Shadertoy runs each buffer once per frame. Its header lists the resulting flicker and light lag, light leaking from naive bilinear fetches at the smallest probes, static probe positions and no complex BRDFs. For the last two it suggests moving probes with the scene, as DDGI does, and importance-sampling both ray directions and probe positions from screen-space BRDF changes so that high-frequency detail is not blurred away. The port merges top-down within one frame, which removes the lag.

## Final gather

Per pixel, a primary ray finds the surface, and the irradiance is the sum of the probe's four cascade 0 direction texels (already weighted by solid angle and cosine), each read bilinearly between probes, times albedo, plus the shadowed sun. Mirrors get one reflection bounce. The output goes through an ACES curve.

## CorylusDonuts: 2.5D screen-space RC pseudocode

https://github.com/CorylusDonuts/2.5-d-Radiance-Cascade-Pseudocode (MIT, 2024-08) is an incomplete design (its ray tracer is a stub) with one idea worth keeping for screen-space probes on depth discontinuities:

- Build a min/max depth mip chain, each texel storing the minimum and maximum depth of its 2×2 children with their pixel positions.
- Cascade `c` has probes every `2^c` pixels with octahedral full-sphere directions, `CASCADE_0_DIM << c` per side.
- Each probe stores two intervals, one cast from the minimum-depth surface and one from the maximum-depth surface of its mip texel, packed as half floats (RGB plus distance) in an RGBA32UI texel.
- The merge weights each of the four parent probes by `exp(−16·|d − d_n|/d)` times its bilinear weight, normalized, separately for the min and max intervals.
- Directions are cast four at a time per 2×2 lane cluster and averaged with `subgroupClusteredAdd(…, 4)·0.25`, a form of pre-averaging.
