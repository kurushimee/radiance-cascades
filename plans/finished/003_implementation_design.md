---
id: 003
title: Implementation design for single-frame 3D radiance cascades GI
status: finished
created: 2026-10-20
updated: 2026-10-20
finished: 2026-10-20
---

# Implementation design for single-frame 3D radiance cascades GI

A complete written design of the GI system to build in Godot 4.7.2 (GDScript and GLSL compute through `RenderingDevice`): world-space 3D global illumination from radiance cascades alone, recomputed every frame with no temporal accumulation and no denoiser, at quality on par with path tracing and a budget that leaves a 60 FPS game most of its frame. The design lives in `design/`; the Godot implementation and its validation follow as plan 004. The work writes no Godot code.

## Decisions

| Question | Decision |
|---|---|
| Probe domain | Cascade 0 on hemisphere probes at surface-atlas texels; cascades 1 and up on world-locked sphere probes in a hash grid near surfaces, placed from the atlas texels. E1 kept this: atlas lattices only won on the lab's large flat charts, and they stay the fallback for such charts. |
| Hit cache | Ray hit records against static geometry are kept across frames and re-shaded with each frame's lighting, which gives the same result as retracing; rays whose segment crosses a moving object's bounds are retraced each frame. |
| Lab experiments | Run wherever they settle a design choice faster than a Godot prototype would; the rest go to plan 004 milestones with a measurement and a fallback. |
| Budget | 12 ms of GI at 1080p on an RTX 2070 (Sponza, all bounces, sun animating) is the ceiling; the design aims at 6 ms. |
| Scope | Diffuse indirect light with all bounces, sky, emitters and Godot's lights. Godot keeps direct light and specular; glossy from RC radiance is a later extension; mirrors and glass are out. |

## Phases

### 1. Research the gaps

Done when each finding is recorded in `research/` (universal facts), `docs/` (engine behavior confirmed against 4.7.2) or `design/` (decisions).

- [x] GPU BVH build and wide-BVH compute traversal without RT cores
- [x] Atlas generation through Godot's import, packing, seam stitching, UV2-space capture
- [x] Visibility-bitmask details for the screen-space cascade −1
- [x] Godot 4.7.2 APIs: raster draw lists at PRE_OPAQUE, `texture_get_rd_texture`, camera matrices, light formulas, sky access, storage buffer limits
- [x] Reference renderer, FLIP, scene assets and licences

### 2. Lab experiments

Done when every experiment reruns from its seeded script in `design/experiments/` and the design quotes its results.

- [x] Surface-probe simulator over the voxel lab, with a Monte Carlo reference at the probe points
- [x] E1: world sphere probes against chart-clamped atlas lattices for the upper cascades
- [x] E2: merges per hand-over, by leak deficit, first-bounce and converged error
- [x] E3: cascade 0 directions and interval
- [x] E4: the cascade −1 hand-over and contact error
- [x] E5: bounce passes, GMRES against the geometric tail

### 3. Write the design

Done when every subsystem file exists, each decision links its evidence, and every derived number has a passing check in `design/checks/`.

- [x] Budgets and checks
- [x] Scene ingestion and tracer
- [x] Surface atlas
- [x] Cascades and merge
- [x] Lighting and bounces
- [x] Near field and composite
- [x] Godot host
- [x] Evaluation and acceptance
- [x] `design/README.md`

### 4. Plan 004 and documentation

Done when plan 004 is in `plans/backlog/` with a measurement and a fallback per milestone, every repository document reflects the design phase, and the work is committed.

- [x] Plan 004
- [x] Root `README.md`, `CLAUDE.md`, `plans/README.md`, `papers/README.md`, `research/README.md`, `docs/`
- [x] Review against the open points of `research/topics/single_frame_3d_rc.md#where-the-evidence-stops`
- [x] Commit

## Facts / research

- The design's decisions and their evidence are in `design/README.md`; the lab results are in `design/experiments.md`.
- **E1:** world grids keep parents defined across chart borders; chart lattices kept 2 to 4 times fewer records only on large, planar, axis-aligned charts.
- **E2:** trilinear parents behind the surface bias bent merges 9.5 to 20% dark, and dropping them fixes it. The sphere fix at every world hand-over leaks 0.0008 of the sky for 21 to 37% fewer records than Kuhn.
- **E3:** at 16 bins, `t0 = 1.60` texel spacings has the lowest error; 36 bins cut single-room error by a third to a half for 2.1 to 2.2 times the records.
- **E4:** contact factors darken contact points 13 to 15%, and short traces with the texel behind count near occluders twice. Only a cascade −1 merged into world cascade 1 gains, so the default is the bilinear atlas read.
- **E5:** the geometric tail beats GMRES up to 5 passes.
- Engine behavior read in the 4.7.2-stable source is in `docs/compositor_and_shading.md` (frame order, light units and attenuation, `texture_get_rd_texture`, camera matrices) and `docs/lightmap_uv2.md` (UV2 unwrap at import, texel size, xatlas options).
- The universal results are in `research/sources/2026_kurushimee_surface_probe_lab.md`, with the GPU BVH, lightmap atlas and evaluation research in the other 2026 source notes.
- The voxel lab (`papers/lab/volume.py`, `papers/lab/radiosity3d.py`) traces DDA rays in CUDA through CuPy, runs dense-grid cascades with thirteen merges, and keeps hit records for frozen re-merges; paper 3's experiments hold GMRES and the geometric tail (`papers/lab/radiosity.py`).
