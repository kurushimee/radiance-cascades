# 3D world-space implementations

The code bases behind [3D world space](3d_world_space.md): the open Split RC codes, erhe's world-space RC reduced into DDGI maps, dense probe grids, a voxel clipmap tracer, and the design documents of small engines. Each section records the design as the code runs it, the numbers it publishes, and the defects found by reading it. Design comparisons, cost models and the single-frame assessment are in the main topic.

| Code | Language and API | Probes | Tracing | Single frame |
|---|---|---|---|---|
| chandra (entropylost) | Rust GPU kernels on `keter` and `yesod`, CUDA | sparse hash, Split RC | hardware RT | no: decayed sums |
| split-radiance-cascades-webgpu, native (wroughtinator) | Rust on Sokol, one GLSL compute file | sparse hash, Split RC | software BVH | no: running average |
| split-radiance-cascades-webgpu, browser | JavaScript and WGSL on WebGPU | sparse hash, Split RC | software BVH | no |
| UERadianceCascades, world mode (Twenmod) | Unreal 5.8.2 plugin, SM6 | sparse hash, Split RC | hardware RT | no: decay with age |
| erhe (tksuoran) | C++, GLSL compute over Vulkan, OpenGL, Metal | dense grid fitted to content | hardware ray queries | no: texel budget and hysteresis |
| tmpvar radiance-cascades-3d-grid | C++, OpenGL compute | dense 64³ | sphere tracing an analytic SDF | built once |
| jumeder/dx12-radiance-cascades | C++, D3D12 DXR | dense 32³ | hardware RT | yes, no temporal reuse |
| rbnelr/voxel_game | C++, OpenGL 4.6 | one 25³ cascade | distance field and DDA | debug view |
| AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades | C++, Vulkan compute | sparse hash per level | analytic primitives and a BVH | not stated |
| SultanAladin/RadianceCascades | Vulkan GLSL compute | world probe grids | sparse SDF bricks | not stated |
| mpalenque/sim | three.js | world probe grid | | not stated |
| M3ycWt (Mathis) | Shadertoy | 5-level voxel grid, hemispheres | voxel DDA | no: bounce over frames |
| creikey/voxel-radiance-cascades | Rust, Sokol, GLSL on D3D11 and WebGPU | screen probes | world voxel clipmap | yes |
| EggyStudio/3DEngine | engine | world probes per distance-field clipmap level plus screen probes | distance-field clipmaps | bounce over frames |

Dense-grid codes and creikey's voxel clipmap are in [dense grids and voxel clipmaps](3d_world_space_implementations_grids.md).

## Contents

- [Split RC codes](#split-rc-codes)
  - [chandra](#chandra)
    - [Frame](#frame)
    - [Probes and LOD](#probes-and-lod)
    - [Split deposit](#split-deposit)
    - [Merge and temporal reuse](#merge-and-temporal-reuse)
    - [Shading and memory](#shading-and-memory)
  - [split-radiance-cascades-webgpu: native GLSL build](#split-radiance-cascades-webgpu-native-glsl-build)
    - [Data layout](#data-layout)
    - [Passes](#passes)
    - [Tracing and deposit](#tracing-and-deposit)
    - [Merge, history and shading](#merge-history-and-shading)
  - [split-radiance-cascades-webgpu: browser build](#split-radiance-cascades-webgpu-browser-build)
  - [The live demo](#the-live-demo)
  - [Unreal world-space Split RC port](#unreal-world-space-split-rc-port)
  - [How the Split RC codes differ](#how-the-split-rc-codes-differ)
- [erhe](#erhe)
  - [Layout](#layout)
  - [Trace](#trace)
  - [Merge modes](#merge-modes)
  - [Reduce into the probe field](#reduce-into-the-probe-field)
  - [Measurements against DDGI](#measurements-against-ddgi)
  - [Stations and gates](#stations-and-gates)
  - [Other O3DE attempt](#other-o3de-attempt)
- [RC design documents](#rc-design-documents)
  - [EggyStudio/3DEngine](#eggystudio3dengine)
  - [genos-engine](#genos-engine)
  - [anoptic-engine](#anoptic-engine)
  - [XRENGINE](#xrengine)
- [Connections](#connections)
- [Single-frame assessment](#single-frame-assessment)
- [Open questions](#open-questions)

## Split RC codes

Two open implementations follow [Split Radiance Cascades](../sources/2026_freeman_split_radiance_cascades.md), and an Unreal plugin ports them. chandra is by entropylost, the author behind the HRC reference code, and matches the paper's settings closely. wroughtinator's repository has a native build whose whole pipeline is one GLSL compute source with software BVH tracing and integer atomics, the closest existing match to what Godot's `RenderingDevice` can run.

| Repository | Language and API | Tracing | Last commit |
|---|---|---|---|
| https://github.com/entropylost/chandra (no license) | Rust GPU kernels on the `keter` and `yesod` crates of https://github.com/entropylost/sefirot, CUDA | hardware ray tracing (`keter::rtx`), one BLAS per OBJ model | 2026-10 |
| https://github.com/wroughtinator/split-radiance-cascades-webgpu | browser: JavaScript and WGSL on WebGPU; native: Rust on Sokol with one GLSL compute file (D3D11, Metal, GL 4.3, Vulkan) | software BVH (CPU-built binned SAH, 16 bins, leaves of 4, 64-entry GPU stack) | 2026-08 |

chandra's `Cargo.toml` (lines 20-21) takes `keter` and `yesod` as sibling path dependencies (`../sefirot/yesod`, `../sefirot/keter`). Both are directories of the entropylost/sefirot monorepo (read at 590f48f), not repositories of their own, and the `testbed` crate was not located, so chandra builds only next to a sefirot checkout.

Sources: [Split RC implementations](../sources/2026_split_rc_implementations.md).

### chandra

#### Frame

1. G-buffer by ray tracing one ray per pixel (depth, normal, hit).
2. Each pixel inserts its cascade 0 probe for each of its one or two LODs; each cascade then inserts the parents of the cascade below (`cell >> 1`).
3. Lifetimes: visible cascade 0 probes get lifetime 1; parents take the maximum of their children.
4. `reset_table` rebuilds every hash table from the slot keys. Each slot's lifetime drops by one, and slots at zero are freed and their data zeroed. Counts go back to the CPU to size later dispatches.
5. Ray counts: each pixel adds 1 to its base probe, and counts sum up the hierarchy. Ray offsets go top-down: top probes take ranges from one global atomic counter and pass sub-ranges to their up to 8 children.
6. One ray per pixel per LOD, traced to the hit or to infinity, then split into cascades (below).
7. Merge top-down, one thread block per probe sharing upper-probe lookups in shared memory; the four Morton-adjacent children of a direction are averaged with warp shuffles, and higher cascades store the pre-averaged cone values (the Split RC paper's implementation notes, in Rust with LuisaCompute over CUDA and OptiX).
8. Build a 6×6 octahedral irradiance tile (8×8 with border) per cascade 0 probe, then shade.

#### Probes and LOD

- One hash table per cascade; the key packs 18 bits per axis plus the LOD, and the cascade is implied by the table. Entry capacity is `4·base_probes`, so the load factor is at most 1/4. Hashing is `pcg3d` with linear probing; insertion is a compare-exchange on the key followed by a freelist pop.
- Probe spacing `base_grid_size·2^(lod + c)`. Presets use `base_grid_size` 4 to 8 scene units and `base_probes` 2^17 to 2^19.
- `lod = max(0, ceil(log2(chebyshev_distance/base_radius)))` with `base_radius` 1200. With `blending_radius` 1.1, points within the top 10% of a LOD band also deposit into the next LOD, with linear weights. The weights jump at integer LOD values, which the code does not explain.
- Directions: a `2·R_c × R_c` grid with `R_c = 4·2^c`, so 32, 128, 512 and 2048 directions. The linear index is a Morton code, so the four children of a direction are consecutive. Every cascade holds the same total number of direction cells.

#### Split deposit

- `L0 = sqrt(32/(4π)) ≈ 1.596`, chosen so the spacing between ray ends matches the probe spacing. Cascade 0 covers `[0, L0·s0]` and cascade `k` covers `(L0·s0·4^(k−1), L0·s0·4^k]`.
- A ray hitting in cascade `k` deposits `(0, 0, 0, 1)` (transparent) into the cascades below `k` and `(L, 0)` into `k`, at the base probe shifted to each cascade. Each deposit adds to `weighted_fluence` and `weights` and bumps the probe's `probe_quality`.
- Directions come from the R2 sequence offset per frame (the same offset for every pixel), flipped into the surface hemisphere. Primary rays use `project_line(fract(r2(offset_index) + pcg3df(tick, 29, 968).xy))` and then `dir·sign(dot(dir, normal))` (`src/algorithm/trace.rs:179-182`); the hash depends only on the frame, which is why every pixel shares the offset. Secondary rays (line 239) use the same call without R2.
- `SphericalEncoder` (`sefirot/yesod/src/direction.rs:41-59`) is the Lambert equal-area cylindrical map: `encode(d) = (atan2(d.y, d.x)/2π mod 1, d.z/2 + 1/2)` and `decode(u, v) = (cos h·s, sin h·s, c)` with `h = 2πu`, `c = 2v − 1`, `s = √(1 − c²)`. Azimuth is linear in `u` and height linear in `v`, so equal areas in `(u, v)` cover equal solid angles, which is why the `2·R_c × R_c` grid gives every cell the same solid angle. The encoder does not normalize its input. The same file holds octahedral, equirectangular (`θ = acos z`) and Clarberg encoders.
- `project_line(uv) = decode(uv.x/2, uv.y)` (lines 77-81) covers only the `y ≥ 0` hemisphere, uniformly by solid angle; its comment calls the result a line on the unit sphere, and every line through the origin has one representative with `y ≥ 0`. The hemisphere flip then takes the end of each sampled line on the normal's side. Since exactly one of `±d` has `y ≥ 0`, the result is uniform over the normal's hemisphere (density `1/2π`), the same distribution wroughtinator gets by flipping a full-sphere sample (derived from the code, not stated in it).
- Ray to cascade (`trace.rs:259-294`, `compute_deposit_ray`): a miss deposits into the last cascade, and a hit at distance `t` into `clamp(ceil(log_b(t/(L0·spacing(lod, 0)))), 0, last)`, where `b` is the length scale (the interval growth factor 4). The direction is stored through `SphericalEncoder::encode`.

#### Merge and temporal reuse

- `radiance_c(j) = own.rgb + own.a·far(j)`, with `own = weighted_fluence/weights` and `far` the trilinear mix of 8 parents at cascade `c + 1`, weighted by corner weight times the parent's `probe_quality`. Corner weights are `0.25^n·0.75^(3−n)`, because a parent's centre is offset by a quarter of its cell from each child.
- Outputs are stored as quads (the mean of 4 consecutive directions), which is the pre-averaged cone value the next cascade down reads. Cascade 0 also keeps the full 32 directions.
- History is an exponential moving average done by decaying the sums: after each merge, `weighted_fluence` and `weights` are multiplied by 0.97 once `weights > 2`. Camera motion does not reset the cache.

#### Shading and memory

- Irradiance tile texel `d_t = Σ_j max(0, d_t·d_j)·L_j` over the 32 directions, divided by the cosine weight sum.
- `shade_optimized_32` uses 8 threads per pixel, one per trilinear corner, each doing one hardware bilinear fetch in the normal direction; the 8 results are summed across the threads.
- Memory from the code formulas for `base_probes = 2^18`: `weighted_fluence` 512 MiB, `weights` 128 MiB, `base_radiance` 384 MiB, `radiance` quads 96 MiB, all fp32 and not measured. These match 4 cascades of `2^18 × 32 = 2^23` cells at 16, 4 and 12 bytes, and a quarter of the cells at 12 bytes, 1,120 MiB in all (derived).
- The TODO list names open problems: LOD blending, slow convergence, an over-darkening shadow fix, leaks near pillars without it, and a wish to convert cascade 0 to SH.
- Two CPU readbacks per frame (probe counts and ray count) are synchronization points.

### split-radiance-cascades-webgpu: native GLSL build

#### Data layout

| Constant | Value |
|---|---|
| Cascades | 4 (32, 128, 512, 2048 directions) |
| Probe capacity per cascade | 4096, 1536, 512, 256 |
| Hash slots per cascade | 8192, 4096, 2048, 1024 |
| LODs | 0 to 7, cross-fade from 0.9 of each boundary |
| Interval cutoff | `T(c, lod) = 1.6·s0·2^lod·4^c` |
| Fixed-point scale | 4096, radiance clamped to 16 before storing |
| Internal resolution | at most 960×540 |

- `IMPLEMENTATION.md` ("Cascade configuration") states the rule behind the table: spacing `ds(n, d) = ds0·2^(n+d)` for cascade `n` and LOD `d`, `32·4^n` directions on a `2Θ × Θ` equal-area grid with `Θ = 4·2^n`, and cutoff `1.6·ds0·2^d·4^n`, with `ds0` chosen per asset from its scale and detail. The 1.6 is chandra's `L0 = √(32/4π) ≈ 1.596` rounded.
- Each hash slot is five `u32` words (signature, token, key low, key high, probe index), double buffered across frames. Probe metadata holds the centre and flags.
- Accumulators are five `u32` per direction (fixed-point R, G, B, β and a count), so deposits use plain integer `atomicAdd`. Composed cones are four words per direction (radiance and β).
- The irradiance atlas is RGBA16F 512×1024, one 8×8 tile per cascade 0 probe at `((probe & 63)·8, (probe >> 6)·8)`.
- Sizes at these capacities (derived): 131,072, 196,608, 262,144 and 524,288 direction cells, 1.11 M in all; 22.3 MB of accumulators and 17.8 MB of composed cones; 600 KiB of double-buffered hash slots. The 4 MiB atlas has 8192 tiles, of which the 4096 cascade 0 probes use the first half.

#### Passes

1. Clear the current frame's hash, counters, ray map and accumulators.
2. Primary rays: G-buffer with position, normal, albedo and direct light (shadow rays to the sun and a point light).
3. Insert probe keys for each pixel's fine LOD, and for its coarse LOD when inside the blend band. A second stream inserts probes at `lod + 2` for last frame's hit points.
4. Insertion retries: failed inserts go to a queue that is retried up to 31 times, alternating two queues. A `canonicalize` pass turns published slots into compact probe indices and tombstones duplicates. Parents are inserted the same way for cascades 1 to 3.
5. Rank blocks of 512 slots count rays per probe; prefix passes give each probe a contiguous range of R2 indices, propagated up and assigned back down.
6. `trace_split`: one direction per ray slot, trace, shade the hit, deposit.
7. `merge` from cascade 3 down to 0, one thread per (probe, direction).
8. `irradiance`: 64 threads per cascade 0 probe build its 8×8 tile.
9. `shade` per pixel, then present.

#### Tracing and deposit

- Origin `surface + 0.003·normal`; direction `r2(index, jitter)` through the equal-area map, flipped if it points into the surface. Jitter is a Cranley-Patterson shift seeded by the frame counter. `r2(i, j) = fract(0.5 + i/g, 0.5 + i/g² + j)` with `g = 1.324717957244746`, the plastic number (`native/shaders/split_rc.glsl:72-75`); `decode_equal_area` (`split_rc.glsl:77-87`, `native/src/math.rs:20-37`) is the same Lambert cylindrical map as chandra's `SphericalEncoder`, and its encoder normalizes first.
- Hit radiance is `direct + albedo/π·previous_irradiance(position, normal, lod + 2)`, where `previous_irradiance` reads last frame's coarse secondary probe at the nearest octahedral texel. That one lookup gives multi-bounce light that grows over frames.
- Deposits use the cell of the ray origin at each cascade, not the probe centre: transparent `(0, 0, 0, β = 1)` below the target cascade, `(L, β = 0)` at the target, nothing above.

#### Merge, history and shading

- Static scenes: exact running average per direction, `(I·n + H·h)/(n + h)` with `h = min(previous_count, 16384)`. Animated lights: `mix(current, previous, 0.92)`, or no history for frames over 50 ms. The filtered raw interval is written back, not the composed value.
- `cone = clamp(I + β·F, 0, 16)`. The top cascade uses the environment colour for `F`. Otherwise `F` averages the four child directions of the parent cascade read at 8 trilinear corners, normalized over corners that exist with a nonzero count.
- Irradiance per tile texel: `E = π·Σ cone·max(0, n·d)/Σ max(0, n·d)` over directions with samples.
- Shading: 8 trilinear corners per LOD, each one hardware bilinear read from the atlas, fine and coarse LODs mixed by the blend weight; indirect is `albedo/π·E`.
- Optional screen-space cascade −1: 32 directions, 8 march steps up to `s0·2^lod` against the depth buffer; a hit returns that pixel's direct light, otherwise the cascade 0 cone shows through.
- Adaptive resolution: every 90 frames the internal scale drops by 0.9× above 1/48 s and rises by 1.05× below 1/75 s.

### split-radiance-cascades-webgpu: browser build

The WGSL build shares the structure with these differences:

- Probe keys are 32 bits: 9 bits per axis, 2 bits of LOD, 3 bits of surface class. The class is the dominant axis of the normal, so probes on different sheets of a thin wall do not share data.
- Four LODs from `18·ds0`, cross-fading from 0.75 of each boundary. Base spacing comes from scene size: `max(0.22, radius·0.077/triangles^0.12)`.
- Each pixel inserts four tangent-plane neighbour probes, and shading uses those 4 corners with Hermite weights `t²(3 − 2t)` on static receivers (8 corners on moving objects).
- Near emitters within `1.5·ds0` are cut from the ray radiance with a smoothstep and added back by an analytic `nearEmissiveIrradiance` term, which avoids fireflies from small nearby lights.
- A world-space cascade −1 for closed meshes traces 14 fixed short rays (6 axes and 8 diagonals) up to `ds0` and weights them with `smoothstep(0, ds0, t)`.
- History is a sample-count average capped at 65535, a 0.92 to 0.992 blend for moving lights, and an exact-key fallback to up to three earlier frames for missing probes. Hit radiance has direct light only.
- Albedo is sampled at mip level 2 at hit points, because mip 0 made sub-pixel detail flicker between frames.
- The screen-space temporal block in the final pass is behind a constant `false`, so it never runs.
- The documents disagree with the code in several places (base spacing formula, history weight 0.965, cascade −1 radius `15·ds0`); the code is what runs.

### The live demo

https://wroughtinator.github.io/ is the static production build of the browser version (repository wroughtinator/wroughtinator.github.io at 6698f7a; read from source, not run). It needs a WebGPU browser (Chrome or Edge 113+).

- **Scenes** (`rc/scenes.js:267-281`, 13): colour bleed laboratory, dynamic Sponza atrium (the 262k-triangle Crytek Sponza plus 48 moving rigid meshes), concave canyon heightfield, dense lantern forest, multi-level atrium, industrial pipe maze, sun temple, orbital sculpture field, daylight door room, megacity stress grid, Cornell box, grand concave heightmap, universal visibility laboratory. The page's static text says "ten real-time validation scenes", "01 / 10" and "Run 10-scene audit", but the runtime takes the label and the audit length from the scene list (`rc/engine.js:2972`, `6694-6701`), so both cover 13; the repository description also says 13.
- **Views:** final composite, indirect only, direct only, surface normals, effective probe coverage, albedo.
- **Controls:** indirect strength and sun animation sliders (0 to 2, default 1); toggles for the camera path, moving lights, "Stable history" (temporal stability) and the pass profiler, all on by default; orbit, zoom and WASD movement. The profiler reports GI grid, frame, geometry, ray split and merge, composite, and dynamic TLAS and upload.
- `?quality=` selects a preset and `?autotest=dynamic-sponza` runs a dynamic-scene gate. Every preset traces one R2 ray per visible pixel (`raysPerSample` 1, the paper's Algorithm 3), so the pixel cap is also the ray budget per frame:

| Preset (`engine.js:55-68`) | Pixel ratio | Max pixels (rays per frame) | Shadow map |
|---|---|---|---|
| Performance | 0.72 | 90,000 | 768 |
| Balanced (default) | 0.9 | 160,000 | 1024 |
| Quality | 1.0 | 420,000 | 1536 |
| Ultra | 1.0 | 720,000 | 2048 |

### Unreal world-space Split RC port

https://github.com/Twenmod/UERadianceCascades (no license, Unreal 5.8.2 plugin, SM6, last commit 2026-10) has a world-space mode that follows Split RC and the chandra code; its screen-space bitmask mode is in [3D screen space](3d_screen_space.md). A comment in the plugin's hash table calls chandra "the paper's implementation" and says its hashing stays stable with multiple bounces, while the plugin's simpler hash is "fine for now". It plugs into Unreal's `RenderDiffuseIndirectLight` GI plugin delegate.

- Probe hash per cascade, 131,072 cascade 0 slots, table 4× larger; 62-bit keys with 19 bits per axis and 4 LOD bits; probe size `BaseVoxelSize·2^level`, cascade `c` cell `>> c`.
- LOD from the Chebyshev distance with `LevelBaseDist`, blended across two levels like chandra.
- 32 bins at cascade 0 on a `2D×D` cylindrical equal-area grid, Morton indexed; `kC0Len = 1.5958 = sqrt(32/4π)`.
- One ray per pixel against the TLAS plus a "far TLAS", shaded with direct light, emission and indirect light. Cascade from `ceil(max(0.5·log2(t/(kC0Len·size)), 0))`, capped at 3. Values are stored as `uint(value·10000)` for integer atomics.
- Multi-bounce (on by default): primary hits read last frame's atlas at `level + 2`; a secondary probe set at the cached hit points gets its own rays.
- Merge: parent weights `{27, 9, 3, 1}/64` by the number of mismatched coordinate bits, times deposit quality. Temporal decay multiplies weight and radiance by 0.9 when the weight exceeds 3 or a bin is older than 12 frames.
- Cascade 0 is integrated into a 6×6 octahedral irradiance tile with border in a 4096² atlas; the apply reads 8 corners per LOD.

Sources: [plugins](../sources/2026_unity_unreal_rc_plugins.md#unreal-world-space-split-rc).

The cascade rule `ceil(0.5·log2(t/(kC0Len·size)))` is `ceil(log4(t/(L0·size)))`, chandra's rule with `b = 4` written in base 2 (derived).

### How the Split RC codes differ

| | Paper | chandra | wroughtinator native | wroughtinator browser | Unreal port |
|---|---|---|---|---|---|
| Key | 64-bit, 18 per axis, 10 LOD | 18 per axis plus LOD | five 32-bit words | 32-bit: 9 per axis, 2 LOD, 3 class | 62-bit: 19 per axis, 4 LOD |
| LODs | binary log of Chebyshev distance, overlap from 0.9 | `base_radius` 1200, blend 1.1 | 0 to 7, fade from 0.9 | 4 from `18·ds0`, fade from 0.75 | `LevelBaseDist`, two-level blend |
| Probes per pixel | nearest | one or two LODs | fine plus coarse in the band | four tangent-plane neighbours | like chandra |
| Accumulators | atomic adds with a counter | fp32 sums with quality | fixed point ×4096, clamp 16 | fixed point | `uint(value·10000)` |
| Multi-bounce | secondary cache 2 LODs coarser | secondary rays | `lod + 2` lookup | direct light only | `level + 2` lookup plus secondary rays |
| History | optional | ×0.97 decay | running average, 16384 cap | count average, 65535 cap | ×0.9 decay with age |
| Cascade −1 | screen-space march | | screen-space, 8 steps | world-space, 14 fixed rays | |

The codes agree on the paper's core (4 cascades of 32 to 2048 equal-area cylindrical directions, `t0 ≈ 1.6·s0`, Morton-ordered children, 6×6 octahedral tiles read at 8 corners) and differ in everything a port has to decide: key width, accumulator format, LOD blending, and history. Only wroughtinator's two builds run without hardware RT, and only its native build avoids 64-bit atomics entirely (derived from the table).

## erhe

| | |
|---|---|
| Author | tksuoran |
| Date | 2026-10 (last commit; the RC work is marked experimental) |
| Kind | C++ engine and editor; GLSL compute over Vulkan, OpenGL and Metal |
| Link | https://github.com/tksuoran/erhe (design notes in `doc/editor/radiance_cascades.md` and `doc/plans/radiance_cascades.md`) |

erhe traces world-space RC with hardware ray queries, merges the cascades, and then reduces cascade 0 into the same irradiance and distance octahedral atlases its DDGI renderer produces. The forward pass samples that field unchanged, so RC drops into an existing probe GI path. Its plan document measures RC against DDGI on test scenes, which makes it the best record of where world-space RC falls short in practice ([erhe](../sources/2026_erhe_world_space_rc.md)).

### Layout

| Setting | Default | Meaning |
|---|---|---|
| `probe_spacing_m` | 1.5 | cascade 0 target spacing `s0` |
| `volume_padding_m` | 1.0 | growth of the content bounds before fitting |
| `max_probes_cascade0` | 65536 | cascade 0 probe budget |
| `max_cascades` | 8 | upper bound (at most 12); cascades stop earlier once the top one has at most 2 probes on its longest axis |
| `cascade0_tile_texels` | 8 | octahedral tile side `q0` of cascade 0 |
| `interval_scale` | 2.0 | `r0 = interval_scale·√3·s0`, so the first interval spans two cell diagonals |
| `texels_per_frame` | 131072 | raw texels traced per frame |
| `hysteresis` | 0.9 | weight kept from history at each trace of a texel |
| `merge_mode` | `per_neighbour_trace` | see below |

- The grid fits the padded bounds of visible content, with probes on the box faces. If the count exceeds the budget, spacing grows by `cbrt(overshoot)·1.05` and the fit repeats.
- Cascade `i`: tile side `q0·2^i` (so 4× the directions), probe counts `(lower + 1)/2` per axis, spacing doubled, and interval `[r0·(2^i − 1), r0·(2^(i+1) − 1)]`, which grows only 2× per cascade. Cascades are added while the longest axis has more than 2 probes.
- Upper probes sit at the centres of lower pairs when the lower count is even, or on the even lower probes when it is odd. Per-axis upper weights are (0.25, 0.75) and (0.75, 0.25) in the even case, (1, 0) and (0.5, 0.5) in the odd case.
- Directions use the octahedral map at texel centres. Cascade `i` texel `(u, v)` has the four children `(2u..2u+1, 2v..2v+1)` in cascade `i + 1`.
- Memory per cascade is two RGBA16F atlases (raw and merged). Cascade 0's merged atlas is stored at child resolution (4× raw), and cascade 0 also keeps an RGBA32F distance atlas.

At the defaults (derived): cascade 0 holds 65,536 × 64 = 4.19 M texels and the 8 cascades 8.36 M; raw and merged atlases take 128 MiB, cascade 0's 4× merged atlas 96 MiB more, and the distance atlas 64 MiB, 288 MiB in all. At 131,072 texels per frame a full refresh takes 64 frames. `r0 = 3.46·s0 = 5.2 m`, and 8 cascades reach `255·r0 ≈ 1,325 m`. The equal-error `t0` for 64 directions would be `2.26·s0` ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)).

### Trace

- Each frame traces the next 131,072 texels in a global order (cascade 0 first) and wraps around, so a full refresh takes several frames.
- A ray runs from the probe over `[t_i, t_{i+1}]`. A front-face hit stores the shaded surface (emission plus direct lights with shadow rays) with β = 0. A backface hit stores zero with β = 0. A miss stores zero with β = 1.
- Each new value blends into history: `mix(traced, history, h)`. After a reset, the `k`-th trace uses `h = min(hysteresis, k/(k + 1))`, so the first trace replaces the history. Geometry changes, removed items and lighting changes reset it.
- Cascade 0 also records the mean hit distance, the mean squared distance and the backface fraction per texel.
- Multi-bounce mode feeds the previous frame's field into the hit shading as the ambient term.

### Merge modes

The merge is `merged.rgb = raw.rgb + raw.a·upper.rgb`, `merged.a = raw.a·upper.a`. The top cascade merges with the sky. Each upper probe contributes the mean of its 2×2 child texels, except for cascade 0, which keeps each child separately in its 4× merged atlas.

| Mode | Upper value |
|---|---|
| `interpolate` | trilinear sum over the 8 upper probes |
| `visibility_masked` | drop upper probes that are inside geometry (a probe is inside when over 25% of 64 Fibonacci rays hit backfaces and the nearest backface is closer than the nearest front face) or not visible from the lower probe, then renormalize |
| `per_neighbour_trace` (default) | for each of the 8 upper probes, trace one visibility ray from `p + t_{i+1}·d` to `u_n + t_{i+1}·d`; the weight is `trilinear_n·V_n`, renormalized; zero if no upper probe is visible |

`per_neighbour_trace` is a binary version of the bilinear fix: it costs one interval ray plus up to 8 short visibility rays per texel and stops light from passing through a wall between a probe and its upper neighbours.

### Reduce into the probe field

- For each cascade 0 probe, the merged child-resolution radiance is cosine-convolved into a 6×6 irradiance octahedral map (8×8 with border) and the distance statistics into a 14×14 distance map (16×16 with border), the DDGI format.
- Irradiance divides by the cosine weight of non-backface texels: `Σ W·L / Σ W·(1 − b)`. Probes with more than 25% backface solid angle are marked inactive.
- Lobe weights are precomputed on the CPU over each texel's true solid angle (the texel is split into sub-squares; a square at direction `w` with parameter area `dA` covers `dA·|w|₁³`). Only weights above 1e−4 of the maximum are kept. Tile solid angles sum to 4π, and cosine lobes sum to π.
- The reduce is the most expensive pass, about 60% of an update.

### Measurements against DDGI

The plan document compares the two on station scenes (hardware not committed):

- Cost: an RC update is 1.15 to 1.57× a DDGI update. RC traces about 0.7 ms per million rays against about 6 for DDGI.
- Passing: leaks between paired rooms (0.0017), Cornell box strips, back-wall noise.
- Failing: a leak at probe offset 0.25 (0.0082, gate 0.02 and not above DDGI's 0.0020); a 0.25 m emitter panel; the corridor far field; settling after a light moves (19 updates against DDGI's 29, gate half of DDGI); the worst accuracy group (0.91 against DDGI's 0.65).
- Probes are not relocated. In the Cornell box the nearest probe layer sits 0.27 m above the floor and the layer below sits inside the floor slab; DDGI relocates such probes and does better there.
- Jittering ray directions within each texel improved the near field (floor probes 0.89 to 1.01 of the reference at `s0` = 0.5) but leaked through thin walls (2%), added noise (0.03 to 0.07 relative std against DDGI's 0.004) and slowed settling (80 to 230 updates at hysteresis 0.97). The default is no jitter.

Planned work listed in the document: per-child connecting segments (32 rays per texel), cascade 0 probe relocation, and refitting only on change.

### Stations and gates

The test rooms are built by `scripts/creations/creation_24_gi_test_rooms.py` and measured by `scripts/gi_verify.py`; the thresholds and results are in the plan document (sections 7 and 10 and the phase 6 results).

| Station | Setup | Measures |
|---|---|---|
| `leak_pair` | two 4 × 3 × 4 m rooms sharing a 0.1 m wall, point light in room A only | room B luminance relative to room A |
| `probe_offset_sweep` | three copies of `leak_pair` with the shared wall at 0, 0.25 and 0.5 probe spacings from the nearest probe plane, plus a 0.6 m crawl space and a 0.3 m pillar centred on a probe | worst leak over the offsets |
| `cornell` | 3 m cube room with red and green walls and a spot light | colour bleed ratios |
| `emissive_only` | closed room with emissive panels of 1.0, 0.25 and 0.05 m | floor luminance in front of each panel |
| `corridor` | 1.5 × 2.5 × 24 m corridor, spot light on the far end wall | far-field floor profile |
| `courtyard` | walled 8 × 8 m yard with an open top, sun and sky | |
| `dynamic` | `cornell` with a scripted light move and door opening | updates to settle |

**Leak metric:** Rec. 709 luminance of the linear indirect irradiance (`sample_indirect_diffuse`), averaged over 8 field updates; `leak = max(floor ratio, wall ratio)` of room B over room A (`gi_verify.py:464-476`). Floors are sampled on a 5 × 5 grid inset 0.4 m from the walls, and walls with 0.3 m margins. A run counts as converged at 0.5% relative change per update, with a 180 s deadline.

| Gate | Threshold | RC at defaults | DDGI | Result |
|---|---|---|---|---|
| 1 Disabled regression | ambient and DDGI outputs unchanged | | | |
| 2 Leak | `leak_pair` ≤ 0.01; offset sweep worst ≤ 0.02 and ≤ DDGI's worst | 0.0017; offsets 0.0001, 0.0082, 0.0010 | 0.0008; 0.0020 | pass; fail |
| 3 Placement | recorded only | | | |
| 4 Bounce | red/green and green/red ≥ 1.2 in `cornell` | 2.07 and 2.07 | | pass |
| 5 Small emitters | floor brighter than the room median at the 1.0 and 0.25 m panels (0.05 m recorded only) | 1.06; 0.53 | | pass; fail |
| 6 Far field | no monotonic violations; max log second difference ≤ DDGI's | 0 violations; second difference undefined | | fail |
| 7 Convergence | updates to settle ≤ half of DDGI's | light move 19, door 16 | 29, 258 | fail; pass |
| 8 Noise | `cornell` back-wall std below DDGI's | 0 | 0.0043 | pass |
| 9 Cost | update and full refresh ≤ about 1.5× DDGI on every station | update 1.15 to 1.57×, full refresh 0.79 to 1.54× | | pass, although the update maximum is above 1.5 |
| 10 Vulkan validation | 0 errors | | | pass |
| 11 OpenGL and Metal | builds with the GI source forced to ambient | | | |
| 12 Accuracy | worst group mean relative error ≤ 0.25 (0.05 m floor excluded) and ≤ DDGI's | 0.91 at the 1.0 m emitter floor | 0.65 | fail |

- The `leak_pair` value is the worst of three runs, measured 2026-09-28. In the offset sweep only the quarter-spacing wall leaks more than DDGI; the on-plane and midway walls stay at or below DDGI's 0.0020.
- The runs used a headless Vulkan editor, back to back with DDGI on one machine. Absolute timings are kept outside the repository, and the RC documents name no GPU (other erhe documents mention an RTX 3080, a Radeon 890M and an RTX 5070 laptop, none tied to these runs).

**What the gates show** (inference): RC's zero back-wall noise against DDGI's 0.0043 is the deterministic structure of RC; its failures are spatial, not statistical. The quarter-spacing wall leak, the floor-embedded probes, the 0.25 m emitter and the corridor far field each trace to probe placement or interval scaling (probes not relocated, emitters below the 1.5 m spacing, intervals growing 2×), none to sample count. A single-frame design therefore inherits erhe's failures unless it changes placement and scaling, and gains nothing on them from history.

### Other O3DE attempt

Chogan-Studios/RadianceCascade (https://github.com/Chogan-Studios/RadianceCascade, CC BY-SA 4.0) is an O3DE Gem that stores 9 SH coefficients per probe on three grids (16³, 8³ and 4³ over the same 16 m cube). Its injection writes an analytic sun-and-plane scene, its merge writes residuals in place, and its output is never composited, so it holds no usable RC method. The only idea of note is an adaptive temporal blend: α = 0.08 when L0 luminance changed less than 10%, 0.3 below 50%, and 1.0 above ([erhe](../sources/2026_erhe_world_space_rc.md#other-o3de-attempt)).

## RC design documents

Design documents found in five small engine repositories ([design documents](../sources/2026_engine_rc_design_documents.md)). Only EggyStudio's describes a working 3D hybrid with measurements. Where a document and its code disagree, the code values are given. The 2D canvas tutorial among them is in [2D implementations](2d_implementations.md).

| Repository | Document | What it is |
|---|---|---|
| https://github.com/EggyStudio/3DEngine (MPL-2.0) | `docs/global-illumination.md` | 3D world probes traced through distance-field clipmaps, plus screen probes for near light |
| https://github.com/AnthonyPoschen/genos-engine (MIT) | `docs/lighting.md` | 3D hybrid of world-fixed near probes on faces, a screen cascade and a coarse world volume; document and code disagree on most values |
| https://github.com/anghel4d/anoptic-engine (LGPL-3.0) | `docs/references/radiance-cascades.md` | theory summary of the radiative transfer paper, no implementation |
| https://github.com/BlackJaxDev/XRENGINE | `docs/developer-guides/gi/radiance-cascades.md` | pre-baked 3D textures sampled by distance; no cascade merge or tracing exists, and the runtime rejects the provider |

### EggyStudio/3DEngine

**Scene field:**

- A distance field of shadow-casting meshes in camera-following clipmap cascades of 64³ cells, each twice as coarse and wide as the last (4 cascades of 0.25 units reach 16 to 128 units across). The field is shared with AO, sun contact shadows and particle collision.
- Each cascade's centre sits 0.35 of its width ahead of the eye and moves in 8-cell snaps. A cascade is rebuilt when the camera passes its snap or a mesh appears or disappears; a budget (default 2 per frame, finest first) bounds rebuilds.
- A mesh that stays in place for 8 frames is built into the field from its triangles. Moving meshes are approximated as coloured boxes.
- Small emitters (a box no larger than twice the cascade 0 probe spacing) are treated as analytic lights instead: the 64 nearest light the scene, each out to where its light falls to 1/50, with soft shadows from the field.

**Probes:**

- World probes stand 8 cells apart in each field cascade (2 units at 0.25-unit cells). Each traces an interval from its spacing to four times its spacing; cascade 0 starts at the probe.
- Quality presets: Low 2 cascades (64, 64 directions), Medium 3 (64, 64, 256), High 4 (64, 256, 256, 256).
- A ray that hits returns the surface's albedo times sun and shadowed lamp light, plus emission, plus last frame's bounce at that surface, so multi-bounce builds up over frames. Misses return environment, ambient or reflection-probe light.
- Probes deep inside walls are excluded, so surfaces near them read only the valid neighbours and a sealed room stays dark next to a lit one.
- Screen probes on tiles (16, 12 or 8 px) trace the near field through the depth buffer out to twice the world probe spacing and take the world probes' light beyond it. Screen probe results blend with the previous frame where the surface is the same, clamped to the spread of the current frame's neighbourhood.

**Measurements** (laptop GPU, 800×450, bounce-room test scene):

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

Each field cascade carries its own probe level, so the probe hierarchy is the clipmap hierarchy: spacing doubles with the field cell, and an interval of one to four spacings is marched on the field level of that spacing, the filtered-proxy pairing again. Its directions do not grow 4× per level (64, 256, 256, 256 at High), so above the second level `K = 1` and the far levels lose angular resolution against RC's rule (inference).

### genos-engine

- The two finest levels store hits in world-fixed cells on floor and wall faces (created within 8 and 12 m of the camera, dropped beyond 14 m, faded out over 6 to 12 m and 10 to 14 m), so they do not shift when the camera moves. A farther screen-anchored level and a coarse world volume (2.5 m grid, 16 directions, one bounce) cover distance.
- The merge walks outward: a near hit wins, a near miss reads the farther level, and a far miss reads the world volume.
- Two fixes recorded from bugs: a probe inside a wall stores no light and is skipped by shading, and a ray that starts inside a solid must not exit through its far side, which had painted lit faces onto back faces.
- An accepted design record (2026-10-10) plans a second version with 1, 2, 4 and 8 m world levels and screen probe radii of 6 to 16 m; the code still implements the 2.5 m world volume.
- Probe density near the player is `1 + 3·exp(−d/3)` (`d` in metres), which the documents do not mention.

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

### anoptic-engine

The document summarizes the RC paper in the language of non-LTE radiative transfer: the penumbra condition `Δs < H(h)` with `γ = 2·arctan(w/2d)`, intervals as `[I, τ]` pairs merged as `[I_cb + e^(−τ_cb)·I_ba, τ_cb + τ_ba]`, scaling `Δs ∝ 2^i` and `Δω ∝ 2^(−αi)`, ray counts (`α = 1` halves rays per cascade, `α = 2` keeps them constant), the bilinear fix at 4× cost, and a DDA formal solution with a diagonal approximate lambda operator (`Λ* = e^(−τ)`), charge conservation and pressure conservation steps. It also stores a pasted copy of a third-party cube-map Shadertoy whose header lists 5 cascades, rays of different lengths, `4 + 8·θ_bin` azimuth bins, flicker from temporal merging and leaks from naive bilinear merging.

The engine has a lighting-mode switch (shadow maps, hybrid, RC) that the L key cycles, but RC mode only turns shadow maps off: the fragment shader samples no RC data and keeps the shadow factor at 1, and no RC code exists in the repository. One profiler capture of a frame (3.80 ms on an unnamed GPU, with the mode unrecorded) gives no RC timing.

### XRENGINE

"Baked" means 3D textures authored offline and supplied per level. The documents describe a voxelize, light, propagate and store baker, but say elsewhere that there is no in-engine baking, and none exists in code. The runtime samples up to 4 nested volumes per pixel at quarter or full resolution:

- A level covers `±HalfExtents` (5 by default) around its transform. A pixel takes the volume whose box contains it, with a blend weight `1 − smoothstep(0.9, 1, maxAxis)` and a priority bias of `0.15·(count − index)/count` toward finer levels, falling back to the last level. The sample is offset along the normal by `normalOffsetScale·texel·halfExtents·0.5` (1.5 by default).
- GI is `radiance·tint·intensity·max(0, 0.35·N.y + 0.65)·albedo·(1 − metallic)/π`, blended with history clamped to `gi ± 0.5` with a factor of 0.85 (at most 0.95). A 5-tap depth- and normal-aware upscale (`exp(−420·|Δdepth|)`, `max(N·N', 0)^4`) composites it additively.
- The provider registry marks RC as experimental and unsupported until live injection, propagation, lifetime handling and validation of authored volumes exist, so selecting it allocates no GI work. That is deliberate, per the engine's to-do list.
- Per-level and component-wide intensities multiply separately, though the documents describe one. The documented voxel size, origin and extents do not exist in code.

## Connections

- **Lineage.** chandra is the reference for both the wroughtinator builds (which take its `L0 = 1.596` as 1.6 and its Lambert map) and the Unreal port (which names chandra "the paper's implementation"); entropylost also wrote the HRC reference code ([HRC implementations](holographic_rc_implementations.md#amitabha)). AliMoghimii, SultanAladin, mpalenque, erhe and tmpvar are independent grid designs that follow the paper's 3D law (inference from the code notes).
- **Hybrids agree on the near field.** EggyStudio and genos both trace the near field from screen or face-anchored probes and the far field from world probes, the same split as Split RC's screen-space cascade −1 below its world cascades and creikey's screen probes over a world clipmap. Every hybrid puts the world representation where the screen fails, off-screen and far (inference).
- **The probe-inside-wall fix recurs.** genos skips probes that store no light, EggyStudio excludes probes deep in walls, erhe deactivates probes over 25% backface, and M3ycWt moves probes toward empty voxels: four codes, one validity rule, and none relocates probes the way DDGI does ([3D world space](3d_world_space.md#leak-defences-in-world-space)) (inference).
- **Code and documents drift.** genos, the wroughtinator browser build, XRENGINE and tmpvar's printout all state values their code does not use; the code values are recorded here (inference from the notes).

## Single-frame assessment

- **Among these codes, jumeder and creikey alone recompute everything per frame with no history**, and they bracket the space: jumeder's dense 32³ grid needs 960 MiB and 126 M rays for a Cornell box, while creikey traces 1.9 M rays over a 12 MiB clipmap in 0.5 ms at 640×360 with screen probes (inference from the measurements).
- **Every Split RC code keeps history.** chandra decays its sums by 0.97, wroughtinator averages up to 16,384 or 65,535 frames, the Unreal port decays by 0.9 with age. A single-frame port changes these, and the paper's table is the only single-frame measurement.
- **wroughtinator's native build is the template for `RenderingDevice`:** one GLSL compute source, software BVH, 32-bit integer atomics with fixed-point accumulators, five-word hash slots, retry queues and prefix passes, no CPU readback. Its gaps for single-frame use are its history and its multi-bounce, both read from last frame (inference).
- **erhe's gates are the failure list a single-frame design inherits:** they come from placement and interval scaling, not sample count ([erhe](#stations-and-gates)).
- **EggyStudio shows the cheap end:** clipmap world probes plus screen probes at 0.59 to 1.00 ms and under 10 MB at 800×450, with 5 frames to settle after motion, so its single-frame quality is unmeasured.

## Open questions

- How does wroughtinator's native build perform with history off, and how much of its look comes from the running average?
- Would erhe's gate failures (quarter-spacing leak, floor-embedded probes, 0.25 m emitter, corridor far field) pass with `l = 4`, equal-error `t0`, probe relocation and an analytic small-emitter term?
- Does the hit-distance hand-over of M3ycWt (rays to the first hit, blended between two levels) beat interval splitting for seams, and at what cost?
- Is a clipmap of world probes over a distance field (EggyStudio) a usable far field under a single-frame screen-probe near field, with directions growing 4× per level?
