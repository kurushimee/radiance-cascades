# Near field and composite

Each pixel reads its irradiance from the atlas at its own UV2, bilinearly, inside its material's shader. The default frame has no screen-space pass. Light that changes faster than the texel spacing is below what the solve resolves. The lab found no cheap way to add it, so plan 004 M5 measures whether the test scenes need one, with 1 ms of the [budget](budget.md#the-frame) held for it.

## Contents

- [The composite](#the-composite)
- [Below the texel](#below-the-texel)
- [The candidate for M5](#the-candidate-for-m5)

## The composite

- **The material reads the atlas.** The irradiance atlas, stored as `E/π`, is a `Texture2DRD` set as a global `sampler2D` shader parameter. Godot accepts it if it is 2D, single-layer, created with sampling usage and in an image-mappable format ([research](../research/topics/godot_integration.md)). Every GI material samples it at UV2 and writes `IRRADIANCE = vec4(value, 1.0)`.
- **`E/π`, not `E`.** Godot mixes `IRRADIANCE.rgb` into the ambient light and multiplies it by AO, albedo and `1 − metallic`, with no division by π ([docs](../docs/compositor_and_shading.md)).
- **Alpha 1** replaces Godot's ambient light entirely, so the solve's sky term is the only sky light ([lighting.md](lighting.md#sky)).
- **SSAO and SSIL are off.** SSAO would multiply the solve's light by a contact factor, which E4 showed darkens wrongly; SSIL would add bounced light a second time.
- **Borders and seams** are handled in the atlas: padding texels hold dilated values, and seam texels are stitched after the last pass ([atlas.md](atlas.md#borders-and-seams)).
- **Cost.** One filtered texture read per pixel inside the opaque pass, which the budget counts at 0.1 ms.
- **Moving objects** read their own charts the same way; transparent materials are out of scope.

## Below the texel

What the texel spacing misses is indirect light that changes within 20 to 45 cm: the darkening and colour under objects smaller than a texel, such as a chair leg or a vase, and the edges of indirect shadows. Godot draws direct light and its shadows per pixel, so they are unaffected.

E4 measured four ways to add detail below the texel, at points a quarter texel from each texel's centre ([experiments.md](experiments.md#e4-the-near-field-below-the-texel)). The lab's geometry is aligned to its texels, so it shows the near field only around one-voxel pillars and at corners:

- **The bilinear atlas read** was within 1 to 6% of the reference at contact points.
- **A probe at the point, merged into world cascade 1 like a texel**, was the only estimate that gained: around the pillars, contact error fell from 0.053 to 0.033. It needs a texel's 64 bent segments per point.
- **A short trace with the texel behind it** gained nothing over cascade 0's full interval and half the pillars' gain over half of it, while doing slightly worse elsewhere. A texel's merged radiance already comes from rays that start at the texel, so a miss at the point reads near occluders twice.
- **A contact factor** (scaling the texel by how much more the point is blocked nearby, as ambient occlusion does) biased contact points 13 to 15% dark over half the interval. Near occluders are lit, and the factor treats them as black.

So any near field must hand over like a cascade: it adds the radiance of what it hits and merges its misses into world cascade 1. A visibility factor of any kind is ruled out.

## The candidate for M5

M5 compares the default composite against a path-traced reference on scenes with objects smaller than a texel. If the error under small objects decides acceptance, it tests a cascade −1 in this form:

- **Probes on a half-resolution pixel grid**, each a hemisphere of 16 bins over `[0, t0]`, traced in screen space against the depth buffer with 32-sector visibility bitmasks ([research](../research/sources/2022_therrien_visibility_bitmask_ssgi.md)). At PRE_OPAQUE this frame's depth and normals exist ([research](../research/topics/godot_integration.md)).
- **Hits read the atlas** at the occluder's UV2, which needs a visibility buffer: a raster pass at PRE_OPAQUE that writes UV2 per pixel.
- **Misses merge into world cascade 1** along the bin's direction, as the texel's own sub-direction reads do, without bent segments; the near interval is short, which bounds what can leak.
- **Off-screen and hidden geometry** cannot be traced in screen space, so pixels whose near interval leaves the screen or crosses a depth discontinuity fall back to the bilinear atlas read.
- **No temporal filter.** The published bitmask GI timing at 1080p is 1.07 ms at half resolution with 16 samples, including a 0.1 ms denoise whose design the source does not give, on a GPU it does not name. Without temporal accumulation, one frame's noise must be low enough with spatial filtering alone.

If the candidate does not beat the default within its 1 ms, the reserve goes to the passes instead, for texels about 11% closer ([budget.md](budget.md#what-buys-finer-texels)).
