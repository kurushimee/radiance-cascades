# Design

This is the design of a world-space diffuse global illumination system for Godot, built from radiance cascades alone. The whole solution is rebuilt every frame from scratch, with no temporal accumulation and no denoiser. It aims to match a path-traced reference within the limits in [evaluation.md](evaluation.md) and to cost 6 ms per frame at 1080p on an RTX 2070, half of a 12 ms ceiling. Implementation and validation follow [plan 004](../plans/in_progress/004_implementation_and_validation.md).

## Contents

- [How it works](#how-it-works)
- [The frame](#the-frame)
- [Decisions](#decisions)
- [Files](#files)
- [What the engine must measure](#what-the-engine-must-measure)

## How it works

**At load**, the GPU builds a hardware acceleration structure over the static triangles. Every mesh's UV2 charts are packed into one surface atlas, about 30,000 texels 20 to 45 cm apart. Each covered texel is a cascade 0 probe with 16 hemisphere bins. World-locked sphere probes for the upper cascades are created only where the texels read them. Every ray and bent segment that static geometry decides is traced once, and its hit, a texel index, is stored: about 8 M hit records.

**Each frame**, the texels get exact direct light from Godot's lights. Five passes then re-shade the stored hits with the texels' current radiance and merge the cascades from the top down, each pass adding one bounce, without tracing a ray. A geometric tail adds the bounces not run. Materials read the result from the atlas at their UV2 and hand it to Godot as `IRRADIANCE`, and as `RADIANCE` for the indirect specular. Godot still draws direct light and specular itself.

Two results make this affordable. With static hits stored, a bounce costs memory reads instead of rays, so all bounces fit in one frame ([paper 3](../papers/03_bounces_one_frame/paper.md)). And with the hits stored, the merges that seal rooms cost reads rather than rays: they keep the furnace deficit near zero, and the deficit is what compounds over bounces.

## The frame

| Step | ms | Where |
|---|---|---|
| Moving objects: TLAS, retrace near them | 0.5 | [scene_and_tracer.md](scene_and_tracer.md#moving-objects) |
| Direct light into the texels | 0.2 | [lighting.md](lighting.md#direct-light) |
| Five bounce passes and the tail | 4.0 | [cascades.md](cascades.md#a-pass), [lighting.md](lighting.md#bounces) |
| Setup, dilation and seam stitching | 0.2 | [atlas.md](atlas.md#borders-and-seams) |
| Composite in the opaque pass | 0.1 | [near_field.md](near_field.md#the-composite) |
| Near-field reserve | 1.0 | [near_field.md](near_field.md#the-candidate-for-m5) |
| **Total** | **6.0** | [budget.md](budget.md) |

## Decisions

| Question | Choice | Evidence |
|---|---|---|
| Where the probes live | cascade 0 on atlas texels, cascades 1 and up on world grids near surfaces | atlas parents are undefined across chart borders; lattices only won on the lab's flat charts (E1) |
| Cascade 0 | 16 hemisphere bins, `t0 = 1.60` texel spacings | best interval at 16 bins (E3); equal-error rule ([paper 1](../papers/01_error_model/paper.md)) |
| Texel spacing | computed from the scene's surface area and an 8 M record budget | [budget.md](budget.md#texel-spacing) |
| Texel to cascade 1 | trilinear fix on front parents | parents behind the surface bias it 10 to 20% dark; the self test leaks (E1, E2) |
| World hand-overs | sphere fix | 21 to 37% fewer records than Kuhn-then-sphere at similar error, leak 0.0008 (E2) |
| Sub-direction reads | 4 bilinear bins | nearest reads make the second bounce 25% worse (E2) |
| Static hits | traced once at load, re-shaded every frame | frozen solves ([paper 3](../papers/03_bounces_one_frame/paper.md)) |
| Bounces | 5 passes (3 at low albedo) and a geometric tail | the tail beats GMRES up to 5 passes (E5) |
| Direct light | exact at the texels with Godot's formulas | Godot's frame order gives no lit colour or shadow maps before the opaque pass ([docs](../docs/compositor_and_shading.md)) |
| Small emitters | Godot lights with fixture meshes | hand-overs lose lights under half the parent spacing ([paper 2](../papers/02_merging_3d/paper.md)) |
| Below the texel | bilinear atlas read; a cascade −1 only if M5 needs it | contact factors darken wrongly, short traces count occluders twice (E4) |
| Tracer | hardware ray queries in compute, one BLAS with opaque and alpha-tested geometries | 0.64 to 3.96 G rays/s, 5 to 8 times the software traversal with H-PLOC's trees ([scene_and_tracer.md](scene_and_tracer.md)) |
| Composite | each material samples the atlas at UV2 and writes `IRRADIANCE = RADIANCE = E/π` | [docs](../docs/compositor_and_shading.md) |

## Files

| File | Contents |
|---|---|
| [budget.md](budget.md) | frame budget, record budget, texel spacing, memory |
| [scene_and_tracer.md](scene_and_tracer.md) | acceleration structures, ray queries, hits, moving objects, buffers |
| [atlas.md](atlas.md) | UV2 charts, packing, capture, probes, seams |
| [cascades.md](cascades.md) | layout, directions, probe creation, merges, a pass |
| [lighting.md](lighting.md) | direct light, emitters, sky, bounces |
| [near_field.md](near_field.md) | the composite and detail below the texel |
| [godot_host.md](godot_host.md) | load, frame, materials, `RenderingDevice` rules, code layout |
| [evaluation.md](evaluation.md) | scenes, reference, metrics, acceptance |
| [experiments.md](experiments.md) | the lab experiments E1 to E5 and their results |
| [checks/](checks/) | assert scripts for derived figures |
| [experiments/](experiments/) | the lab experiments' scripts |

## What the engine must measure

The lab cannot show costs on a GPU, geometry finer than a texel, or real unwraps. Plan 004 measures each of these before building on it:

- the cost per hit record, which sets the texel spacing (M3);
- records per texel in scenes that need four or more world cascades (M3);
- 16 against 36 bins at equal cost (M3);
- the sphere fix against Kuhn at the first world hand-over in thin-walled rooms (M3);
- the ray rate under `RenderingDevice` (M1): 0.64 to 3.96 G rays/s with hardware ray queries;
- the pass count at the test scenes' albedos (M4);
- whether objects smaller than a texel need a cascade −1 (M5);
- the cost of retracing near moving objects (M7).
