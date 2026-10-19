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
7. Merge top-down, one thread block per probe.
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

## Dense grids

### tmpvar's radiance-cascades-3d-grid

| | |
|---|---|
| Author | Elijah Insua (GitHub: tmpvar) |
| Date | 2024-04-28 (last commit, 00:18:05 UTC) |
| Kind | Repository (C++, OpenGL compute) |
| Link | https://github.com/tmpvar/radiance-cascades-3d-grid |

A rough, unoptimized C++ and GLSL implementation of RC on a world-space dense 3D probe grid. The scene is an analytic signed distance function with one emitter sphere. The cascades are built once by sphere tracing rays from every probe into a 2D-array octahedral atlas, merged from the top level down, and read per pixel by a trilinear lookup of level 0 probes. The code includes headers from HotCart, an unreleased engine wrapper that is not in the repository, and the README states the project cannot run as published ([3D grid](../sources/2024_tmpvar_rc_3d_grid.md)).

#### Files

| File | Contents |
|---|---|
| README.md | Project description and media links; states the project is unrunnable without HotCart. |
| NOTES.md | Two short notes on reflection skew and merge interpolation. |
| DEVLOG.md | Dated log from 2024-01-30 to 2024-02-08, with Next and Pending lists. |
| radiance-cascades-3d-grid.cpp | App entry (CartSetup, CartLoop): sets up the camera, ticks the cascades, draws the final pass and debug UI, presents. |
| radiance-cascades/radiance-cascades.h | Host class RadianceCascades: init, level and memory math, Tick (build, copy, stitch, merge), debug UI and debug draws. |
| radiance-cascades/shared.h | RadianceCascadesConfig struct and OCTAPROBE macros, included by both C++ and GLSL. |
| shaders/shared.glsl | MapResult struct, pack and unpack, Lerp wrappers, scene `map()`, SDF primitives, boolean operations, normals. |
| shaders/octahedral.glsl | Octahedral encode and decode. |
| shaders/lerp.glsl | Lerp2D and Lerp3D for vec3 and vec4. |
| shaders/probes.glsl | World-to-probe-grid mapping, probe SDF (debug only), upper-grid index helpers. |
| shaders/radiance-cascades-build.comp | Ray march per atlas texel; writes one level. |
| shaders/radiance-cascades-merge.comp | Merges level `l+1` into level `l`. |
| shaders/radiance-cascades-octaprobe-stitch.comp | Copies interior edges and corners into the 1-texel border of each probe slot. |
| shaders/fractal.frag | Final pass: sphere traces the scene and shades hits from level 0 probes. |
| shaders/debug-probe-merge.frag | Debug view of one probe, its 8 upper probes and the merge results. |
| shaders/radiance-cascade-atlas-debug.frag | Debug view of atlas layers. |

Git history: five commits by the author, from 2024-04-27 to 2024-04-28. Referenced but not in the repository: `engine/dust.h`, `hotcart/hotcart.h`, `hotcart/types.h`, `hotcart/debug.h`, `engine/linalg.h`, `engine/gpu/morton.h` (MortonEncode, MortonDecode, MortonDecode2D), `engine/gpu/colormap-turbo.glsl`, and `engine/renderer/shaders/debug-fullscreen.vert` (the final pass uses it for its full-screen triangle).

#### Scene

- No voxels and no stored SDF. The scene is the function `map(p)` in `shaders/shared.glsl`, evaluated on demand. It returns a MapResult (distance `d`, colour, emission, throughput, level).
- Active scene (the `#if 1` branch): a solid red box of half-size 12; an inner box of half-size 11.8 subtracted, so the walls are 0.2 thick; a slab of half-size (18, 18, 0.3) centred at (0, 0, 12) subtracted, which removes the +Z wall so that side is open; and an emitter sphere of radius 1.4 at the origin, colour (1, 1, 1), emission (100, 100, 100), combined by union.
- Inactive scene (the `#else` branch): a white floor box of half-size (3.5, 0.25, 3.5) at (0, −3, 0) and a pink box of half-size (0.5, 2, 0.5) at (0, −1.25, 2.5), with no emitter.
- Union takes the minimum of the two distances; cut takes `max(a.d, −b.d)`; the material comes from whichever operand has the smaller `|d|`. After boolean operations the distance is a bound, not an exact distance.
- Normals use a four-tap tetrahedron difference with `h = 0.0001` (CalcNormal).
- The scene is static: `map()` reads no time or uniforms.
- At default settings the level 0 grid spans [−8, 8] on each axis, so the room walls at `|x|, |y|, |z| = 12` lie outside it; the emitter lies inside.

#### Passes

Tick returns early unless `debug.dirty` is set. Dirty is set at init, when any ImGui config value changes (ray length, scale, max level, branching factor), when the gather radius or ratio sliders change, and on keys 0 to 4 (max level). Passes marked [dirty] run only then; passes marked [frame] run every frame.

- **Init (once):** `octahedralProbeAtlas`, a GL_TEXTURE_2D_ARRAY of RGBA32F, 4096 × 4096 × 7 layers, linear filter, clamp to edge; `octahedralProbeAtlasOriginal`, the same with nearest filtering; `configUBO`, a 48-byte copy of RadianceCascadesConfig. Debug defaults: atlas scale 1, render probe level −1, gather radius 1.0, gather ratio 0.75, sample-original off.
- **P1 [dirty]:** clear the atlas to zero (`glClearTexImage`).
- **P2 [dirty] Build** (`radiance-cascades-build.comp`): one dispatch per level, from `maxLevel` down to 0 (default 5, so levels 5 to 0). Uniform 0 is the level (`uint`), uniform 1 the ray range (vec2), the UBO is on binding 0 and the atlas on image binding 1, write-only. Local size 128; thread count = texels per probe × probes at that level, with no bounds check. A thread decodes `probe = id / rays`, `ray = id % rays`, texel `(ray % d, ray / d)` with `d = atlasProbeDiameter·2^level`, and direction `OctahedralDecode((texel + 0.5)/d)`. From the probe centre it marches `t` from `rayRange.x` to `rayRange.y`: if `map(origin + dir·t).d ≤ 0.001` it stores the hit (colour, emission, throughput 0) and stops, otherwise `t += max(1e−6, r.d)`, with no iteration cap. A miss stores colour 0, emission 0, throughput 1. The write goes to layer = level at slot origin + (1, 1) + texel, with slot origin `MortonDecode2D(probe)·(d + 2)`.
- **P3 [dirty]:** copy the atlas into the original atlas (`glCopyImageSubData`, all layers), which keeps build-only values.
- **P4 [dirty] Stitch** the original atlas for levels `maxLevel` down to 0 (`radiance-cascades-octaprobe-stitch.comp`): local size 16, uniform 0 the level, uniform 1 the probe count `N/8^level`; thread count = probe count, with an early return at or above it.
- **P5 [dirty] Merge and stitch loop** from level `maxLevel + 1` down to 0 (6 down to 0 by default). Each level: a memory barrier; the merge (`radiance-cascades-merge.comp`), one thread per texel of level `l` (`d_l²·probes_l`), local size 16, sampler unit 0 the atlas read with `texelFetch` from layer `l + 1`, image unit 1 the atlas read-write on layer `l`, uniform 0 the lower level; a memory barrier; the stitch for the same level with the P4 shader (see the uniform mismatch below).
- **P6 [frame] Final pass** (`fractal.frag`, a three-vertex triangle with `debug-fullscreen.vert`): uniforms 0 `worldToScreen`, 1 `screenToWorld`, 2 `eye`, 3 `fov`, 4 `screenDims`, 5 the sampler (merged atlas, or the original if sample-original is on), 6 `debugRenderProbeLevel` (default −1), 7 and 8 the gather offset and ratio (declared, unused here). One primary ray per pixel, up to 128 sphere-trace steps, a hit threshold of 2 × the cone radius at distance `t`, and a miss colour of (0.1, 0.1, 0.1).
- **P7 [frame, optional] Debug views:** `debug-probe-merge.frag` when "debug merge" is on; `radiance-cascade-atlas-debug.frag` draws one strip per level, left to right, when the render-atlas box is on.

#### Parameters and math

| Field | Default | Meaning |
|---|---|---|
| gridDiameter | 64 | level 0 probes per axis, 64³ = 262,144 |
| scale | 0.25 | level 0 probe spacing in world units |
| rayLength | 0.05 | length of the level 0 interval, the base unit for all intervals |
| atlasProbeDiameter | 6 | level 0 octahedral texels per side, interior only |
| OCTAPROBE_PADDING | 1 | border texels on each side of each probe slot |
| maxLevel | −1 | −1 builds levels 0 to `totalLevels − 2`, otherwise 0 to `maxLevel` |
| branchingFactor | 1 | shown in the UI only; no shader or build path reads it |

| Level | Probes per axis | Probes | Spacing | Texels per probe | Slot (`d + 2`) | Interval | Rays |
|---|---|---|---|---|---|---|---|
| 0 | 64 | 262,144 | 0.25 | 6×6 = 36 | 8 | [0, 0.05) | 9,437,184 |
| 1 | 32 | 32,768 | 0.5 | 12×12 = 144 | 14 | [0.05, 0.2) | 4,718,592 |
| 2 | 16 | 4,096 | 1 | 24×24 = 576 | 26 | [0.2, 0.8) | 2,359,296 |
| 3 | 8 | 512 | 2 | 48×48 = 2,304 | 50 | [0.8, 3.2) | 1,179,648 |
| 4 | 4 | 64 | 4 | 96×96 = 9,216 | 98 | [3.2, 12.8) | 589,824 |
| 5 | 2 | 8 | 8 | 192×192 = 36,864 | 194 | [12.8, 51.2) | 294,912 |
| 6 | 1 | 1 | 16 | 384×384 = 147,456 | 386 | [51.2, 204.8) | not built |

- **Placement:** level `l` has `D_l = 64 >> l` probes per axis at spacing `s_l = 0.25·2^l`; probe `i` sits at `(i + 0.5 − D_l/2)·s_l`, so the grid is centred on the origin and spans 16 units at every level. The probe index is the 3D Morton index of the cell.
- **Directions:** octahedral, with +Y at the map centre (0.5, 0.5), −Y at the four corners and the edge midpoints at ±X and ±Z. Encode divides by the L1 norm and folds the lower hemisphere; encode and decode are inverses. Directions per probe are `36·4^l`, probes `262,144/8^l`, so rays per level halve.
- **Intervals:** `rayRange(l) = [start, end)` with `end = rayLength·4^l` and `start = 0` at level 0, else `rayLength·4^(l−1)`. They are contiguous, from the probe centre.
- **Atlas:** one array layer per level. A probe slot is `(d + 2)` texels square at `MortonDecode2D(probe)·(d + 2)`. `atlasGridDiameter = NextPowerOfTwo(√262,144) = 512` slots per side at level 0, and `baseDiameter = NextPowerOfTwo(512·8) = 4096`, assuming NextPowerOfTwo returns a power of two unchanged (the header is missing). Level 0 fills its layer exactly (262,144 × 64 = 4096² texels). The share of each layer used by slots is 38.3% at level 1, 16.5% at 2, 7.6% at 3, 3.7% at 4, 1.8% at 5 and 0.9% at 6.
- **Memory** (RGBA32F, 16 bytes per texel): one layer 256 MiB, one 7-layer atlas 1,792 MiB, the original copy 1,792 MiB, both 3,584 MiB. The Init printout says 1,792 MB; the value is in MiB. Interior texels hold 283.5 MiB, 15.8% of one atlas (derived, [3D world space](3d_world_space.md#memory-and-rays)).
- **Packing** (four 32-bit words per texel): x colour rgb as `packUnorm4x8` (8 bits per channel, clamped to [0, 1]); y `emission.xy` as half2; z half2(`emission.z`, `throughput.x`); w half2(`throughput.yz`). `d` and `level` are not packed.
- **Merge** per lower texel, from the top level down. The upper index per axis is `idx = (p + 0.5)·(d_l/d_(l+1)) − 0.5`, which is `p/2 − 0.25` since `d_(l+1) = 2·d_l`:

```
vec3 index = (lowerProbeGridPos + 0.5) * lowerAtlasProbeDiameter / upperAtlasProbeDiameter - 0.5;
vec3 upperProbeGridPos = clamp(floor(index), vec3(0.0), vec3(config.gridDiameter >> upperLevel));
vec3 hi = vec3((config.gridDiameter >> (lowerLevel + 1)));
t = fract(index);
```

  Eight upper probes at `base + {0,1}³`, each clamped to `hi`, get trilinear weights from `t`. For each, lower texel `t` maps to upper texels `2t` and `2t + 1` per axis, averaged with weights 0.25. The eight values combine trilinearly, then `color = lower.color + upper.color·lower.throughput`, `emission = lower.emission + upper.emission·lower.throughput`, `throughput = lower.throughput·upper.throughput`. Lower values are the build values read from the texel before it is written; upper values come from layer `l + 1`, already merged. A lower hit (throughput 0) blocks upper contributions, a lower miss passes them. Layer `l + 1` for the top merge (level 6) does not exist and reads zero; layer 6 is never built with default settings, so the merged throughput is zero at every level. Colour and emission do not depend on merged throughput, because the merge reads only the lower texel's build throughput.
- **Stitch**, one thread per probe (`d = atlasProbeDiameter·2^level`): interior texels are 1 to `d` per axis and border texels 0 and `d + 1`. Each border edge copies the adjacent interior row or column in reverse order (index `i` maps to `d + 1 − i`), the octahedral edge wrap, and each corner copies the diagonally opposite interior corner.
- **Final gather** per hit pixel: surface point `pos`, normal `n = CalcNormal(pos)`, level 0 grid coordinate `g = pos/scale + D/2` (WorldToProbeGrid), `base = floor(g)`, `t = fract(g)`. The eight probes at `base + {0,1}³` are read at level 0 in direction `n`: `ReadProbeLinear` takes `uv = OctahedralEncode(n)`, `src = slot origin + uv·d + 0.5`, and blends the four texels at `floor(src) + {0,1}²` bilinearly with `fract(src)`, edge reads using the border texels. The eight values blend trilinearly with `t`. The output is the rgb of emission only: albedo is not multiplied in, and the hit surface's own emission is not added.
- **Cost** (no timings recorded): one full build traces 18,579,456 rays for levels 0 to 5, each step evaluating `map()` once (four primitives, three boolean operations). Merge threads for levels 0 to 6 total 18,726,912, each reading 32 texels. Each hit pixel calls `map()` four times for the normal and reads 32 texels for the probe lookup.

#### Issues and notes

Author notes (NOTES.md): skewed-looking reflections suggest a problem in the merge, and the merge is not a plain 0.25/0.75 blend because a lower probe can sit in a negative cell relative to the upper cascade. DEVLOG pending items: a computed probe view, and pentalinear interpolation for the merged view so it can be compared with the expected value. DEVLOG next items: lit fog by sampling probes along a DDA, possibly pre-cooked into a small voxel grid; a grid layout with deinterleaved directions; a second test scene for reflections; non-cubic cascade diameters (the atlas packing would have to change); ray data in octahedral maps (the atlas already uses them).

Code TODOs and comments: "TODO: memory barrier for image reading" before the final pass (`radiance-cascades-3d-grid.cpp`); "TODO: make this multiplier a slider" for the cone radius factor (`fractal.frag`); "replace by an appropriate value" on the finite-difference step `h` (`shared.glsl`, `fractal.frag`); a commented line samples along `reflect(rayDir, normal)` while the active line samples along the normal; commented lines multiply the probe value by `result.color`, inactive.

Found by reading (not executed):

1. The merge's upper-index clamp is one too high: both the clamp on `floor(index)` and `hi` use `D_(l+1)`, while valid indices are 0 to `D_(l+1) − 1`, so for the last lower probe one of the eight upper neighbours lies outside the grid.
2. Merge edge weights are wrong for lower probe 0: its `idx` is −0.25, the base clamps to 0, but `t = fract(−0.25) = 0.75` is not clamped, so 75% of the weight goes to upper probe 1 instead of 0. Interior probes are not affected.
3. The final gather is shifted by half a probe cell: WorldToProbeGrid puts probe centres at integer + 0.5, while SampleProbesWorldSpace uses floor and fract as if centres were at integers. The merge subtracts 0.5 and the gather does not; at level 0 with the default scale the shift is 0.125 world units.
4. The gather reads outside the grid for scene surfaces: the level 0 grid covers [−8, 8], the walls are at 12, so `x = 12` maps to 80 and `x = −12` to −16. Indices of 64 and above and negative coordinates fall outside the level, and negative values passed through `uvec3()` are undefined in GLSL.
5. The stitch probe-count uniform is set at the wrong location: the merge loop calls `glUniform1ui(2, levelProbeCount)`, but the stitch shader declares only locations 0 and 1. Location 1 keeps the value from the last P4 call (level 0, 262,144), so every P5 stitch covers 262,144 probe indices instead of `N/8^l`. Writes beyond a level's real count land in slots that level does not use, so output is unaffected, but each level launches 262,144 threads.
6. Build and merge have no bounds check on the thread index. The default dispatch sizes are multiples of their local sizes (128 and 16), so the defaults do not overrun; GLDispatch is HotCart code and its rounding is not visible.
7. Merge uniform locations 2 (gather offset), 3 (gather ratio) and 4 (`maxLevel`) are declared but unused. The gather sliders still set the dirty flag, so changing them triggers a full rebuild that does not read them; the values are used only in `debug-probe-merge.frag`.
8. `d` and `level` are not packed, and UnpackMapResult leaves them unset. The merge reads `d` from unpacked values and discards it; ProcessMaterial reads `level`, unset for scene primitives but unused on the scene-hit path.
9. The host builds `screenDims` from the width for both components (`radiance-cascades-3d-grid.cpp` line 136). The final pass takes its cone radius from `screenDims.y`, so the hit threshold is wrong when the window is not square.
10. Level 6 is never built: with the default `maxLevel` of −1, levels 0 to 5 are built and layer 6 stays zero, so rays longer than 51.2 world units are never cast.
11. Only emitter light is shaded: the build stores albedo, but the final pass never reads colour, and surfaces other than the emitter contribute no emission, so no light bounces off the walls.
12. The gather samples one direction, the surface normal, with no hemisphere integral, no cosine weight and no albedo.

#### References in the devlog and code

The DEVLOG cites tmpvar's 2D playground (https://tmpvar.com/poc/radiance-cascades/, [2D articles and demos](2d_articles_and_demos.md#tmpvars-playground)), Chen's 2020 Monter post on irradiance-probe interpolation seams ([related probe GI](related_probe_gi.md)) and Aaltonen's 2020 cascade-chain debug view, a mip chain packed into one atlas ([scene representation](scene_representation_and_tracing.md)). `octahedral.glsl` cites Narkowicz's 2014 octahedral encoding ([cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d)), pyalot's 2015 gist and Stubbe's 2017 decode ([cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d)), and McGuire's GDC 2019 DDGI talk (https://www.gdcvault.com/play/1026182/, [related probe GI](related_probe_gi.md)).

### jumeder/dx12-radiance-cascades

https://github.com/jumeder/dx12-radiance-cascades (C++, D3D12 DXR and HLSL compute) is full 3D RC with hardware ray tracing in a Cornell box, with a BLAS per model and the TLAS rebuilt each frame. It shows why a naive full 3D grid is impractical ([voxel and RT repositories](../sources/2026_voxel_3d_rc_repositories.md#jumederdx12-radiance-cascades)).

- Four cascades with 32³, 16³, 8³ and 4³ probes over a 2×2×2 box. Directions are a lat-long grid of `(64 << i)×(32 << i)` texels: 2048 directions at cascade 0, 4× more per cascade.
- Memory: 512, 256, 128 and 64 MiB of RGBA16F, 960 MiB in total; 126 M rays per frame.
- Intervals grow 8× per cascade: ends at 0.031, 0.28, 2.28 and 18.3 units. The cascade 0 interval is shorter than the probe spacing.
- The hit shader returns only the instance's emission, so the result is one bounce from emitters.
- Merge: trilinear over 8 upper probes. Looking up the same direction UV in the 2× finer upper tile lands on a 2×2 texel corner, so the hardware linear filter averages the four child directions.
- Shading integrates 2048 directions × 8 trilinear taps per pixel (16,384 samples), with no solid-angle weight for the lat-long grid and no temporal reuse.

The 2×2×2 box at 32³ gives a spacing of 0.0625, so cascade 0's interval (0.031) is half a spacing (derived). The 8× interval growth with 4× directions is the `l = 8, K = 4` point, which by Split RC's error rule makes the angular error at each ray's end grow 4× per cascade against a 2× spacing growth ([core theory](core_theory.md#two-criteria-for-interval-scaling-derived)) (derived).

### rbnelr/voxel_game

https://github.com/rbnelr/voxel_game (C++, OpenGL 4.6 compute) is a Minecraft-style engine with two experimental RC modules drawn only as debug views ([voxel and RT repositories](../sources/2026_voxel_3d_rc_repositories.md#rbnelrvoxel_game)).

- Scene: a 512³ window of R16UI block ids (256 MiB) addressed with `coord & 511`, so moving one chunk rewrites only the new slab. A matching R8I distance field (128 MiB) is built per chunk: mark solid cells and their neighbours, then sweep lines along x, y and z with `min(previous + 1)`, giving an L1-style distance within each chunk.
- Tracing steps by the distance field when it is above 1 (step `n·(1 − ε)/(|dx| + |dy| + |dz|)`, which cannot skip a solid cell) and falls back to a voxel DDA near surfaces.
- 2D module: a horizontal slice of the world, 7 cascades, base spacing 0.125 m, 4 rays at cascade 0, intervals `[√2·0.125·4^(k−1), √2·0.125·4^k]` m, about 145 MB of RGBA16F, 18 M rays per frame, with the bilinear fix.
- 3D module: a single cascade, 25³ probes 4 m apart, 2×2 octahedral directions, no merging.

### Other world probe grids

**SultanAladin/RadianceCascades** (https://github.com/SultanAladin/RadianceCascades, Vulkan GLSL compute): world probe grids with octahedral direction tiles per probe; an 8-probe trilinear merge that samples each upper probe along the direction toward the lower interval's end, a 3D bilinear fix; octahedral tiles filtered by hand so they do not bleed; sparse SDF bricks with brick skipping and 64 steps; and the nearest hit across SDF instances shaded with per-instance albedo ([survey](../sources/2026_rc_repository_survey.md#3d)).

**mpalenque/sim** (https://github.com/mpalenque/sim, three.js): a world probe grid with spacing ×2 and octahedral directions ×4 per level, intervals `base·(4^i − 1)/3` to `base·(4^(i+1) − 1)/3`, cone tangent `2/√dirs`, an 8-corner merge, and cascade 0 resolved into an SH volume ([survey](../sources/2026_rc_repository_survey.md#3d)).

**AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades** (https://github.com/AliMoghimii/Vulkan-Ray-Tracing-with-Radiance-Cascades). The default branch `main` (and `develop`, `feature/caustics`) is a Vulkan compute path tracer (`Vulkan-Engine/shaders/raytracer.comp`, 972 lines: spheres, triangles, planes, quads, cubes, a BVH, PBR, glass, fog, depth of field, SSAA, soft shadows; `feature/caustics` adds photon mapping). The RC lives on other branches, which start with commit 52e595e (2026-05-25, "Started Phase 7: The Allocation Pass"):

| Branch | Tip | State |
|---|---|---|
| `scene-swapper` | 14752f4 (2026-06-17) | most complete; the README names it the latest |
| `refactor/radiance-cascades` | 9bb9cd3 (2026-06-16) | same RC files |
| `merge-caustics-RC` | b201233 (2026-06-05) | RC merged with the caustics layer |
| `merge-caustics-RC-second-bounce` | 9b04c58 (2026-06-05) | adds a world-space SH cache for second-bounce colour bleeding (`probe_shcache.comp`) |
| `testing-scaling-tex`, `testing-no-artifacts` | b2839fc, 462d305 | partial experimental shaders |

The design on `scene-swapper` (`include/gi/CascadeConfig.hpp`, `shaders/rc/*.comp`, `reference-files/technical_manual.md`):

- **Hierarchy:** a 3D world-space grid. `numCascades = 5` in the config, while the manual documents 3 levels. Level `k` has probe spacing `0.5·2^k`, an octahedral map of `4·2^k` texels per side (16, 64, 256, … directions), and a grid that halves per level from 64 × 60 × 92.
- **Intervals:** `end(k) = 0.5·4^k`, `start(k) = end(k − 1)`, so [0, 0.5], [0.5, 2], [2, 8], [8, 32], [32, 128]. Spacing doubles while interval length grows ×4.
- **Sparse probes:** level 0 probes are allocated from G-buffer pixels and level `k > 0` from the parent slots their children need; each level has a GPU hash map (`probe_alloc.comp`, `CascadeHashMap.cpp`) filled bottom-up with atomic inserts.
- **Tracing:** `probe_trace.comp` runs one thread per (slot × octahedral texel) ray, with `tMin = start + 0.001` and `tMax = end`, testing analytic planes and quads and then a BVH. It stores FP16 radiance and transmittance; level 0 adds direct light with shadow rays.
- **Merge:** `cascade_merge.comp` runs top-down, trilinear over the 8 parent probes and 2 × 2 bilinear over the parent's octahedral map, with `L = near.L + near.T·far.L` and `T = near.T·far.T`.
- **Gather:** `final_gather.comp` interpolates the 8 surrounding level 0 probes trilinearly; `probe_sh.comp` pre-integrates level 0 into SH.
- **Recorded bugs (manual):** BUG-1, darkening at grid borders from an uninitialized transmittance accumulator for missing parents; BUG-2, probe shadows that ignored walls, fixed with analytic plane and quad shadow tests; BUG-3 and BUG-4, typos. Whether the fixes are present at the branch tips was not checked.
- No timings are published.

It is the only sparse hashed world-space RC with per-probe tracing (no ray splitting) whose code is complete enough to read end to end ([survey](../sources/2026_rc_repository_survey.md#alimoghimiivulkan-ray-tracing-with-radiance-cascades-3d-world-space-rc-on-branches)). With `K = l = 4` and 16 cascade 0 directions, its `t0 = 0.5` against a spacing of 0.5 is one spacing, below the equal-error 1.13 for 16 directions ([core theory](core_theory.md#choosing-cascade-0-derived-and-reported)) (derived). BUG-1 is the 3D form of the missing-parent case that sparse trilinear renormalization exists to handle ([3D world space](3d_world_space.md#placement-and-levels-of-detail)) (inference).

### M3ycWt (Mathis): voxel cascades with hemisphere probes

"Volumetric" in the Shadertoy's title ("Volumetric Radiance Cascades", 2025-02-08) means a voxel volume; there are no participating media ([Shadertoys](../sources/2023_rc_shadertoys.md#m3ycwt-mathis-voxel-cascades-with-hemisphere-probes)).

- A procedural 32×32×48 voxel room (columns, arches, cloth, a fountain lamp, a partial roof, a moving floor emitter and a moving sphere), rebuilt each frame and traced by voxel DDA for up to 128 steps. A sun shadow map stores the distance to the first solid voxel along the sun.
- Five levels with probe grids from 32×32×48 (spacing 1) to 2×2×3 (spacing 16). Each probe has six hemispheres, one per face normal. Level `L` uses an `s×s` grid per hemisphere with `s = 3·2^L`: level 0 has the normal plus 8 directions at 45°, and higher levels use concentric square rings with polar angle `(ring/s)·π` and `4 + 8k` azimuth bins per ring (Common:96-121). Each texel stores radiance times solid angle over `2π` times `cos θ`; `w` holds the hit distance (1e7 for sky, −1 for an invalid probe).
- Level 0 traces from every empty voxel, 0.25 voxels off each face; coarser levels move the probe toward an empty fine voxel by ±0.05 per axis.
- There are no intervals: every ray runs to its first hit. A hit distance `t` keeps the probe's own value below `2^L` voxels, hands over to the parent beyond `3·2^L`, and blends linearly between (Cube A:258-259).
- The parent value blends eight parent probes trilinearly. For each, the parent hemisphere facing the child is read in the one direction pointing at the child; if that stored distance is shorter than the offset minus 0.5, the parent counts as occluded and its weight drops to `10^−5` (Cube A:44-103). This is the same visibility test as X3XfRM's ([3D surface probes](3d_surface_probes.md)).
- Hits add the shadowed sun and last frame's level 0 irradiance in front of the hit, times albedo, so each frame adds a bounce and level 4 reaches level 0 in about four frames. The camera pass sums nine level 0 texels in front of the hit, adds the sun, multiplies by albedo, and applies an ACES fit and a 0.45 power.
- Found in the code: level 0's direction weights use uncentred grid coordinates, so the zenith texel gets a ring weight of 0.088 and a corner texel the centre weight of 0.293; stored values weighted by solid angle over `2π` make the indirect term half of Lambert's `E/π`, while the sun term has no `1/π` at all; the visibility test uses the parent's nominal position rather than its nudged one; `BRDF_GGX` is defined and never called.

Hit-distance hand-over in place of intervals is a soft split: each ray to its first hit feeds its own level near and its parent far, which is ray splitting with a linear blend between two cascades, the variant one sparse build found removed seams at twice the cost ([3D world space](3d_world_space.md#ray-splitting)) (inference).

## creikey/voxel-radiance-cascades

https://github.com/creikey/voxel-radiance-cascades (MIT; Rust, Sokol, GLSL compute on D3D11 and WebGPU) is screen-space RC at 640×360 whose probes sit on G-buffer pixels and whose intervals trace a world voxel clipmap, so it belongs to the screen-probes-with-world-intervals family ([3D screen space](3d_screen_space.md)). Its report has the most detailed timings of any small 3D RC project, and its tracer is the world-space part ([voxel and RT repositories](../sources/2026_voxel_3d_rc_repositories.md#creikeyvoxel-radiance-cascades)).

**Scene:**

- Static clipmap: four levels of 64³ cells, cell edge 1, 4, 16 and 64 m. One u32 per cell (albedo and density, unorm8) and two u32 of half-float radiance, 12 MiB in total.
- The clipmap recentres only when the camera moves more than 12 m from its centre, snapped to 2 m. A recentre rebuilds all four levels; there is no toroidal scrolling.
- Static radiance is albedo times direct light (sun, moon, ambient) with no shadow test, re-injected every frame, so probes see one bounce of unshadowed direct light.
- Dynamic objects go into a separate two-level clipmap (1 m and 4 m) rebuilt every frame as 8³ bricks per object. Overlaps resolve with `atomicMax` on the packed word, which fixed flicker from overlapping objects.

**Cascades:**

| Cascade | Probes | Directions | Interval (m) | Step (m) |
|---|---|---|---|---|
| 0 | 160×90 (every 4 px) | 32 | 0 to 1.6 | 0.1 |
| 1 | 80×45 | 128 | 1.6 to 6.4 | 0.3 |
| 2 | 40×23 | 512 | 6.4 to 25.6 | 1.2 |
| 3 | 20×12 | 2048 | 25.6 to 102.4 | 4.8 |

- Probes take the depth and normal of one G-buffer pixel. The ray origin is snapped to `max(0.125, 0.25·4^c)` m and pushed out along the normal by `0.82·4^c` m.
- Directions are a Fibonacci sphere with `N` points over the full sphere. The merge groups child indices `4k..4k+3`, which on a Fibonacci lattice share a height but spread around in azimuth.
- Each ray takes 16 samples. The clipmap level is chosen per sample from the distance along the ray, `LOD = clamp(0.5·log2(max(t/2, 1)), 0, 3)`, blending two levels, so the voxel size grows with distance like cone tracing.
- Extinction per sample is `clamp(0.36·density, 0, 0.9)`. Samples outside the cascade's own clipmap level add a faint sky term, and cascade 3 adds the sky after the loop.
- Merge: bilinear over 2×2 upper probes, four child directions each. The far transmittance is averaged, not multiplied.
- Cascade 0 becomes a 4×4 octahedral irradiance map per probe (32 directions, cosine weighted, weight 4π/32). Shading reads 2×2 probes bilinearly and the octahedral map bilinearly, with no border wrap.
- No temporal accumulation.

**Numbers** (D3D11, 640×360, GPU not named):

- Baseline GI compute 0.76 ms: trace 0.52 ms, merge and octahedral build 0.08 ms. Rays per frame: 1,884,160 with 16 samples each.
- Final build: 2.1 ms average, 2.5 ms worst, most of it G-buffer and shadow maps; trace 0.49 ms.
- Halving the cascade 0 spacing to 2 px (7.4 M rays) cost 3.5× the GPU time.
- Synthetic trace benchmark: 14.3 G rays/s on D3D11, 2.8 G rays/s on WebGPU in a browser.

**Lessons recorded:**

- Geometry thinner than one voxel leaks. Indirect detail is limited by the 4 px probe spacing and the 4×4 octahedral maps.
- A small emitter seen by only one or two cascade 0 directions becomes a bright firefly probe. The fix was to cap the emitter's injected radiance and add an analytic term for its nearby falloff.
- Screen-space contact AO multiplied onto the indirect light caused rings on terrain until same-material taps were skipped.

**Read against the cost model** (derived unless marked): the rays per cascade are 460,800, 460,800, 471,040 and 491,520, constant as on a flat surface, and they sum to the stated 1,884,160. Step lengths grow 3 to 4× per cascade with the ×4 intervals, so every ray takes 16 samples whatever its length; that is the filtered-proxy pairing that keeps `l = 4` affordable for a marcher ([3D world space](3d_world_space.md#marching-cost)). The per-sample LOD follows the gap between ray ends inside an interval. Averaging the far transmittance instead of multiplying it is an error unless each child holds one whole sample of the parent's transmittance (inference).

## RC design documents

Design documents found in small engine repositories ([design documents](../sources/2026_engine_rc_design_documents.md)). Only EggyStudio's describes a working 3D hybrid with measurements. Where a document and its code disagree, the code values are given. The 2D canvas tutorial among them is in [2D implementations](2d_implementations.md).

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
