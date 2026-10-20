# Lighting and bounces

Each frame starts from nothing. Direct light from Godot's lights is computed exactly at every texel, emission and the sky are added, and a fixed number of passes gathers bounced light through the cascades. A geometric tail then adds the light of the bounces not run. No value carries over from the previous frame, so a frame is a pure function of the scene and its lights.

## Contents

- [Texel radiance](#texel-radiance)
- [Direct light](#direct-light)
- [Emitters](#emitters)
- [Sky](#sky)
- [Bounces](#bounces)
- [Open questions](#open-questions)

## Texel radiance

A texel reflects `L = Le + (ρ/π) · (E_direct + E_indirect)`, with `ρ` and `Le` from the [capture](atlas.md#capture). `E_direct` comes from the lights below; `E_indirect` is what the cascades gather from other texels and the sky.

## Direct light

- **The solver computes direct light itself.** Godot's frame order gives a pass that must finish before the opaque pass neither this frame's lit colour nor its shadow maps ([research](../research/topics/single_frame_3d_rc.md#where-the-evidence-stops)).
- **Godot's own formulas**, so the texels see the same light the screen shows ([docs](../docs/compositor_and_shading.md)):
  - In non-physical units Godot multiplies each light's energy by π, so the irradiance a texel gets is `E = π · color · energy · max(N·L, 0) · attenuation · visibility`, and its reflected radiance `ρ · color · energy · N·L · attenuation` matches the screen's diffuse term.
  - Omni and spot attenuation is `max(1 − (d/r)⁴, 0)² · max(d, 0.0001)^(−decay)`; spots multiply by their cone term; physical units scale energy as the docs list.
  - A light with shadows off has visibility 1.
- **Visibility:**
  - The sun gets one any-hit shadow ray per texel per frame toward its centre. A hard shadow at texel resolution is enough, because the screen's sharp shadows come from Godot's shadow maps.
  - A static omni or spot light against static geometry gets its visibility once at load, one bit per texel in range.
  - A moving light gets shadow rays every frame for the texels in its range.
  - Shadow rays whose segment crosses a moving object's bounds are retraced against the moving objects ([scene_and_tracer.md](scene_and_tracer.md#moving-objects)).
- **Cost.** The direct-light line of the [budget](budget.md#the-frame) covers 200,000 rays: 30,000 texels for the sun plus about five moving lights.

## Emitters

- **Large emitters stay in the solve.** A window, a glowing panel or a lit sign adds its captured emission to `Le`, and the cascades gather it like any other radiance.
- **Small emitters become Godot lights.** A hand-over loses most of a light narrower than half its parent spacing: the kept share falls as `3.70 (a/h)²` ([paper 2, depth reprojection and small lights](../papers/02_merging_3d/paper.md)), and in the lab's closed scenes RC's first bounce from a ceiling light carried errors of 0.25 to 0.58, against 0.04 to 0.16 for the second bounce (E2). So a lamp is a Godot light plus a fixture mesh whose material is marked as a fixture: the light gives direct light on screen and in the texels, and the fixture's emission stays out of `Le`, so nothing is counted twice. Emitters smaller than about twice the texel spacing should be fixtures; M6 tests that threshold.

## Sky

- **Only the top cascade's misses read the sky.** A lower ray that misses reads its parents.
- **Scripts get the sky only as a CPU image**, through `environment_bake_panorama` or `sky_bake_panorama`, linear and untonemapped ([docs](../docs/compositor_and_shading.md)). At load and whenever the environment changes, the panorama is baked, uploaded and integrated over each top-cascade bin into a table of one radiance per bin.
- **The sun's disk** is part of the panorama, and the sun's light is already injected as direct light. The table replaces the disk with the sky around it before integrating.
- **The composite writes `IRRADIANCE` with alpha 1**, which removes Godot's own ambient light, so the solve supplies all sky light ([research](../research/topics/godot_integration.md)).

## Bounces

- **Passes.** Pass 1 gathers from `L = Le + (ρ/π) · E_direct`. Pass `n` gathers `E_indirect` from the radiance of pass `n − 1` and sets `L = Le + (ρ/π) · (E_direct + E_indirect)`. Each pass re-shades the stored records and merges the cascades ([cascades.md](cascades.md#a-pass)); none traces a ray ([paper 3, frozen solves](../papers/03_bounces_one_frame/paper.md)).
- **Five passes**, or three for scenes whose mean albedo is 0.5 or less. The count is a per-scene setting and never changes at run time. In the lab, five tail passes at albedo 0.9 came within 0.015 to 0.047 of the solve's own fixed point in single rooms and the pillar hall, and three passes at albedo 0.5 within 0.023 (E5).
- **The geometric tail.** With `d_n` the last pass's change in irradiance and `r_n = Σ d_n / Σ d_(n−1)` over all texels, per colour channel, the output is `E_n + d_n · r_n / (1 − r_n)` ([paper 3, iterations](../papers/03_bounces_one_frame/paper.md)). Irradiance is linear in radiance, so applying the tail to irradiance gives what a further gather of tail-corrected radiance would, without the pass. `r_n` is kept below 0.95 so that a near-zero denominator cannot blow up the result.
- **Why not GMRES.** Up to five passes the tail was as good or better in every lab scene except two rooms at pass 5, and it needs two global sums per pass instead of a growing set of stored vectors and inner products (E5).
- **The limit: rooms joined by small openings.** In the lab's two rooms at albedo 0.9, the tail stays 0.14 from its fixed point after five passes and 0.08 after eight, while GMRES reaches 0.02 at eight. Scenes like that converge slowly whatever the method. M4 measures them, and the fallback is more passes for that scene.

## Open questions

- Whether one shadow ray per texel toward the sun's centre is enough, or soft sun shadows need a few rays at texel scale (M2).
- The cost of baking the sky panorama when it changes (M6).
- The pass count on the test scenes at their real albedos (M4).
