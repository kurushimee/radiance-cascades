# Efficient GPU screen-space ray tracing

| | |
|---|---|
| Authors | Morgan McGuire, Michael Mara |
| Date | 2014-12 |
| Kind | Paper, Journal of Computer Graphics Techniques 3(4), CC BY-ND 3.0 |
| Link | https://jcgt.org/published/0003/04/04/ |

The standard method for tracing rays against a depth buffer, which screen-space RC intervals need. Marching a 3D ray in fixed steps and projecting each sample skips some pixels and samples others twice. This paper instead walks the ray's 2D projection with a perspective-correct DDA, so each pixel along the line is visited once.

## Setup

1. If the ray's far end would pass the near plane, shorten it to end there.
2. Project both ends. Keep `k = 1/w` and `Q = point·k` at each end; both interpolate linearly in screen space, so the 3D point at any step is `Q/k`.
3. If the ends are closer than 0.01 px, nudge the far end.
4. If the line is steeper than 45°, swap x and y so the loop always steps along x.
5. Per-step deltas `dP = (sign, dy/dx)`, `dQ`, `dk`, all scaled by the stride and offset at the start by a jitter fraction of one step.

## Loop

- Each step covers ray depths from the last step's maximum to `(Q.z + dQ.z/2)/(k + dk/2)`, the depth half a step ahead.
- Each depth sample is treated as a slab from the stored depth to that depth plus `zThickness` away from the camera. The ray hits when its depth range overlaps the slab. Up to 4 depth layers can be tested.
- An out-of-bounds fetch returns 0, which ends the loop, so viewport clipping is free.
- The walk stops after `maxSteps` or at the ray's end.

## Parameters

- `zThickness` should match typical object thickness. Too small lets rays pass behind thin objects; a near-infinite value is reasonable with a single depth layer.
- `stride` above 1 spaces samples for speed and causes banding; jittering the start by a per-pixel pattern hides it. The paper suggests stride above 1 only for rough surfaces.
- `maxDistance` and `maxSteps` bound the worst case. Cost is linear in the steps taken.
- Misses can fall back to another structure (such as voxels) or an environment map. A guard band around the viewport helps.

## Cost

25 steps per pixel at 1080p took 1.2 ms on a GeForce Titan and 6.4 ms on a GeForce 650M laptop. 25 rays per pixel for AO cost about 30 ms, which the paper calls too slow for real time.

Open ideas listed: test every pixel the ray crosses with conservative rasterization, refine strided hits with a binary search, and refine hits to subpixel precision.
