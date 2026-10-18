# Linietsky: SDFGI plan for Godot 4.1

| | |
|---|---|
| Title | SDFGI: Solving the accessible Global Illumination problem in Godot |
| Author | Juan Linietsky (reduz), Godot's technical lead |
| Form | 48-page slide deck, undated, titled "Godot SDFGI plan for 4.1" |
| Link | https://smallpdf.com/file#s=06a033fc-481b-4f1e-83cd-984dba9fe755&r=read (a viewer page; linked from a [comment on Godot PR #122999](https://github.com/godotengine/godot/pull/122999#issuecomment-5546305514)) |

The design plan behind SDFGI and the redesign that became HDDAGI. Shipped code differs in places (see [Godot GI internals](2026_godot_gi_internals.md) and [HDDAGI](2026_godot_hddagi_dynamic_gi.md)), but the deck states the requirements Godot sets for its own GI and several optimizations that apply to any probe system traced in compute, RC included.

## Requirements

- No per-scene or per-object setup: no SDFs, cards or lightmaps to author; ideally one switch.
- Real time, or at least fast updates, with light leaks kept to a minimum.
- Diffuse and reflected light, light on transparent objects, and light for volumetric fog.
- Runs on any Vulkan GPU including integrated ones, and in VR, so it cannot depend on TAA.

Accepted losses: no high-frequency GI (screen-space effects fill it in), dynamic objects receive light but add none, cascades are required, and small emitters look spotty with few samples.

## Structure

- Built on DDGI: per cascade 17³ probes over a 128³ distance field, up to 8 cascades. Irradiance probes are 5×5 octahedral tiles, one 25-thread workgroup each; occlusion probes are 16×16 octahedral depth maps used with a Chebyshev test, after biasing the point along the geometric normal.
- Geometry is rasterized into an empty framebuffer at 4× the cascade's resolution per axis (512² for 128³), writing a 4³ bitfield per cell with `imageAtomicOr`, 16 MB per cascade. Albedo and emission are reduced with subgroup operations into 64³ grids.
- The jump flood is seeded from the sub-voxel bits, which gives distances finer than one cell. Occlusion rays whose SDF distance is under the probe range walk the bitfield with a DDA for an exact hit.
- Lighting runs over a list of empty cells next to solid ones, built when the SDF is stored, with a normal, an outline bitmask and an indirect dispatch count. Each entry sums lights with sphere-traced shadows plus indirect light read from nearby probes and writes RGBE 9-9-9-5. The outline bits also write light into neighboring cells, so the short step back after a sphere-traced hit lands on lit data.

## Probe tracing

One workgroup per probe traces one jittered ray per tile texel, from the probe's cascade into coarser ones. A hit reads albedo and emission, takes a normal from the SDF, and steps back until it finds a lit cell. After a barrier the 25 results are averaged over each texel's hemisphere in shared memory and blended into history by a fixed fraction. Rays need no start bias, since the occlusion probe's depth already moves the start a little outward.

## Making it fast

- **Scrolling:** when the camera passes the nearest probe to the center, only the uncovered slab is rerendered. Keeping the jump flood's final pointers lets the old and new regions merge by comparing each cell's pointer with its neighbor's across the seam. Occlusion probes on the seam retrace only the directions toward the new region, and the light texture scrolls with its new part marked dirty. Camera motion moves one axis at a time in practice, so one side per update is enough.
- **Hit caching:** with static geometry, each ray's hit (cascade, light-texture cell, normal) can be stored. Scrolling keeps a cached hit valid if it stays in the same cascade, or if the ray leaves through the same face of an upper cascade.
- **Light on demand:** ray hits set bits in a coarse dirty volume, and only marked regions are relit next frame, at one frame of delay. Static lights go in a separate texture computed once.
- **Frustum:** probes far outside the view update every few frames, which with a centered camera slows more than half of them.

## Reflections

Sharp reflections trace from each pixel's reconstructed position; tracing two cascades together and blending by the nearer hit stops cascade switches from popping. Medium roughness reads a less blurred copy of the probes saved before the hemisphere average. Full roughness reads the irradiance probes. Each pixel blends two of the three by roughness.

## Plan for dynamic objects

- Give each moving object its own SDF from a jump flood, built on demand. Writing all objects into every cascade cell costs cells × objects, so split cascades into 8³ macro regions of 16³ SDF cells, each with a bit list of overlapping objects built by one compute thread per cell with atomic OR, and a 64-byte empty-cell mask so the DDA skips empty space.
- Light them through a card atlas: render 6 axis views per object (albedo, normal, emission, depth) at about one pixel per voxel, light it in compute with shadows from the static cascades, and plot the result where a card's depth meets a cell.
- Static hits stay cached; a dynamic ray retraces only up to the cached static hit and reads dynamic light if something intercepts it first.
- The author of HDDAGI's 2026 screen-probe draft names this plan, and Lumen's per-object surface caching, as a possible route for moving geometry instead of revoxelizing often; no work on it had started.
