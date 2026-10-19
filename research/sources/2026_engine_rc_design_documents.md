# RC design documents in small engine repositories

Design documents found in five engine repositories. Only EggyStudio's describes a working 3D hybrid with measurements, so it gets the detail here. Where a document and its code disagree, the code values are given.

| Repository | Document | What it is |
|---|---|---|
| https://github.com/EggyStudio/3DEngine (MPL-2.0) | `docs/global-illumination.md` | 3D world probes traced through distance-field clipmaps, plus screen probes for near light |
| https://github.com/AnthonyPoschen/genos-engine (MIT) | `docs/lighting.md` | 3D hybrid of world-fixed near probes on faces, a screen cascade and a coarse world volume; document and code disagree on most values |
| https://github.com/xiaoiver/infinite-canvas-tutorial (MIT) | `docs/rc-gi-implementation.md` (Chinese) | Plain 2D canvas RC modeled on bevy_radiance_cascades |
| https://github.com/anghel4d/anoptic-engine (LGPL-3.0) | `docs/references/radiance-cascades.md` | Theory summary of the radiative transfer paper, no implementation |
| https://github.com/BlackJaxDev/XRENGINE | `docs/developer-guides/gi/radiance-cascades.md` | Pre-baked 3D textures sampled by distance; no cascade merge or tracing exists, and the runtime rejects the provider |

The last two are described at the end of this note.

## EggyStudio/3DEngine

### Scene field

- A distance field of shadow-casting meshes in camera-following clipmap cascades of 64³ cells, each twice as coarse and wide as the last (4 cascades of 0.25 units reach 16 to 128 units across). The field is shared with AO, sun contact shadows and particle collision.
- Each cascade's center sits 0.35 of its width ahead of the eye, and moves in 8-cell snaps. A cascade is rebuilt when the camera passes its snap or a mesh appears or disappears; a budget (default 2 per frame, finest first) bounds rebuilds.
- A mesh that stays in place for 8 frames is built into the field from its triangles. Moving meshes are approximated as colored boxes.
- Small emitters (a box no larger than twice the cascade 0 probe spacing) are treated as analytic lights instead: the 64 nearest light the scene, each out to where its light falls to 1/50, with soft shadows from the field.

### Probes

- World probes stand 8 cells apart in each field cascade (2 units at 0.25-unit cells). Each traces an interval from its spacing to four times its spacing; cascade 0 starts at the probe.
- Quality presets: Low 2 cascades (64, 64 directions), Medium 3 (64, 64, 256), High 4 (64, 256, 256, 256).
- A ray that hits returns the surface's albedo times sun and shadowed lamp light, plus emission, plus last frame's bounce at that surface, so multi-bounce builds up over frames. Misses return environment, ambient or reflection-probe light.
- Probes deep inside walls are excluded, so surfaces near them read only the valid neighbors and a sealed room stays dark next to a lit one.
- Screen probes on tiles (16, 12 or 8 px) trace the near field through the depth buffer out to twice the world probe spacing and take the world probes' light beyond it. Screen probe results blend with the previous frame where the surface is the same, clamped to the spread of the current frame's neighborhood.

### Measurements (laptop GPU, 800×450, bounce-room test scene)

| Preset | Memory | GPU time |
|---|---|---|
| Low | 1.65 MB | 0.59 ms |
| Medium | 4.38 MB | 0.74 ms |
| High | 9.16 MB | 1.00 ms |

- The field adds about 4 to 5 MB per cascade.
- Against path-traced references of nine views, per-view error was 0.02 to 0.29 of the reference; the three presets agree within a few hundredths.
- Emissive blocks at 1280×720 on High: 1 block 0.35 ms, 16 blocks 1.08 ms, 64 blocks 2.77 ms. Each block is within 5% of a path-traced reference from one to four blocks away.
- Light follows a changed light at once; after a walk or turn it settles within 5 frames.
- Known leaks: light enters caves through the field side behind the eye (1.7/255 in a test cave at High), and caves wider than the last cascade get sky light (27/255 at Low). Gaps thinner than a cell block light; walls thinner than a cell still block it.

## genos-engine

- The two finest levels store hits in world-fixed cells on floor and wall faces (created within 8 and 12 m of the camera, dropped beyond 14 m, faded out over 6 to 12 m and 10 to 14 m), so they do not shift when the camera moves. A farther screen-anchored level and a coarse world volume (2.5 m grid, 16 directions, one bounce) cover distance.
- The merge walks outward: a near hit wins, a near miss reads the farther level, and a far miss reads the world volume.
- Two fixes recorded from bugs: a probe inside a wall stores no light and is skipped by shading, and a ray that starts inside a solid must not exit through its far side, which had painted lit faces onto back faces.
- An accepted design record (2026-10-10) plans a second version with 1, 2, 4 and 8 m world levels and screen probe radii of 6 to 16 m; the code still implements the 2.5 m world volume.
- Probe density near the player is `1 + 3·exp(−d/3)` (`d` in meters), which the documents do not mention.

| Value | Document | Code |
|---|---|---|
| Screen probe spacing | 0.5 m, 1 m, far 32 px | target 0.28, grown ×1.25 until it fits or passes 2.0, then doubled per level |
| Screen directions | 64 | 16 at the finest level, doubling: 16, 32, 64 |
| Screen grid cap | 96 × 54 | 96 × 54 |
| World volume | 2.5 m, 16 directions, three heights, two-cell margin | same (heights 1.5 m apart from 0.45 m) |
| World blend-out | to 1.5 m | `max(1.0·tier spacing, 8.0)`; no 1.5 m blend |
| Spacing levels | 1, 2, 4 and 8 m | none; the same document later says the lattice does not exist yet |
| Unit lamp | 97 m | 72 (its 17 m reach at peak 0.2 matches 72, not 97) |
| Occluder and lamp cells, sun shadow reach, tier ray, world probe ray | 2 m, 4 m, 80 m, 64 m, 8 m | same |
| Diffuse shading | albedo over π | albedo times `0.8/π` |

A reference document comparing the design with the RC paper cites functions and line numbers that no longer exist.

## infinite-canvas-tutorial

2D RC at full resolution with interval `2·4^c` px starting at `2·(4^c − 1)/3`, cascade count `ceil(log4(1 + 1.5·diagonal))` (6 at 1080p), sphere tracing an analytic SDF of canvas shapes, ping-pong merge with 0.75/0.25 parent weights, and a cascade 0 average upsampled linearly. The composite adds GI with a hidden gain of 14 and a weight that favors dark base colors.

- **The gain:** GI is the GI texture minus the plain render, clamped at zero, multiplied by `14·gi_strength` and by `w = 0.22 + 0.78·(1 − base)`, then added and clamped to [0, 1]. A comment explains the weight: bright areas suppress GI so they do not blow out, dark areas let the bleed show, and the result is "not a physical penumbra" but indirect light laid over an LDR image. No commit, issue or document explains the 14; the design document's formula omits both the gain and the weight.
- **Code against the document:** the march takes at most 32 steps and hits at distance below 4.88·10⁻⁴, not on an "abs(sd) thin band"; the probe-average mip divides `pw²` samples by `2·pw`; the cascade count and its cap of 16 match. The tutorial lesson built on bevy_radiance_cascades has neither the gain nor the weight.

## anoptic-engine

The document summarizes the RC paper in the language of non-LTE radiative transfer: the penumbra condition `Δs < H(h)` with `γ = 2·arctan(w/2d)`, intervals as `[I, τ]` pairs merged as `[I_cb + e^(−τ_cb)·I_ba, τ_cb + τ_ba]`, scaling `Δs ∝ 2^i` and `Δω ∝ 2^(−αi)`, ray counts (`α = 1` halves rays per cascade, `α = 2` keeps them constant), the bilinear fix at 4× cost, and a DDA formal solution with a diagonal approximate lambda operator (`Λ* = e^(−τ)`), charge conservation and pressure conservation steps. It also stores a pasted copy of a third-party cube-map Shadertoy whose header lists 5 cascades, rays of different lengths, `4 + 8·θ_bin` azimuth bins, flicker from temporal merging and leaks from naive bilinear merging.

The engine has a lighting-mode switch (shadow maps, hybrid, RC) that the L key cycles, but RC mode only turns shadow maps off: the fragment shader samples no RC data and keeps the shadow factor at 1, and no RC code exists in the repository. One profiler capture of a frame (3.80 ms on an unnamed GPU, with the mode unrecorded) gives no RC timing.

## XRENGINE

"Baked" means 3D textures authored offline and supplied per level; the documents describe a voxelize, light, propagate and store baker, but say elsewhere that there is no in-engine baking, and none exists in code. The runtime samples up to 4 nested volumes per pixel at quarter or full resolution:

- A level covers `±HalfExtents` (5 by default) around its transform. A pixel takes the volume whose box contains it, with a blend weight `1 − smoothstep(0.9, 1, maxAxis)` and a priority bias of `0.15·(count − index)/count` toward finer levels, falling back to the last level. The sample is offset along the normal by `normalOffsetScale·texel·halfExtents·0.5` (1.5 by default).
- GI is `radiance·tint·intensity·max(0, 0.35·N.y + 0.65)·albedo·(1 − metallic)/π`, blended with history clamped to `gi ± 0.5` with a factor of 0.85 (at most 0.95). A 5-tap depth- and normal-aware upscale (`exp(−420·|Δdepth|)`, `max(N·N', 0)^4`) composites it additively.
- The provider registry marks RC as experimental and unsupported until live injection, propagation, lifetime handling and validation of authored volumes exist, so selecting it allocates no GI work. That is deliberate, per the engine's to-do list.
- Per-level and component-wide intensities multiply separately, though the documents describe one. The documented voxel size, origin and extents do not exist in code.
