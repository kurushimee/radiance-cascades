# Split RC implementations: chandra and split-radiance-cascades-webgpu

Two open implementations of [Split Radiance Cascades](2026_freeman_split_radiance_cascades.md). chandra is by entropylost, the author behind the HRC reference code, and matches the paper's settings closely. wroughtinator's repository has a native build whose whole pipeline is one GLSL compute source with software BVH tracing and integer atomics, which is the closest existing match to what Godot's `RenderingDevice` can run.

| Repository | Language and API | Tracing | Last commit |
|---|---|---|---|
| https://github.com/entropylost/chandra (no license) | Rust GPU kernels on the `keter` and `yesod` crates of https://github.com/entropylost/sefirot, CUDA | hardware ray tracing (`keter::rtx`), one BLAS per OBJ model | 2026-10 |
| https://github.com/wroughtinator/split-radiance-cascades-webgpu | browser: JavaScript and WGSL on WebGPU; native: Rust on Sokol with one GLSL compute file (D3D11, Metal, GL 4.3, Vulkan) | software BVH (CPU-built binned SAH, 16 bins, leaves of 4, 64-entry GPU stack) | 2026-08 |

chandra's `Cargo.toml` (lines 20-21) takes `keter` and `yesod` as sibling path dependencies (`../sefirot/yesod`, `../sefirot/keter`): both are directories of the entropylost/sefirot monorepo (read at 590f48f), not repositories of their own, and the `testbed` crate was not located. So chandra builds only next to a sefirot checkout. The direction mapping and `project_line` from `yesod` are described under chandra below.

## chandra

### Frame

1. G-buffer by ray tracing one ray per pixel (depth, normal, hit).
2. Each pixel inserts its cascade 0 probe for each of its one or two LODs; each cascade then inserts the parents of the cascade below (`cell >> 1`).
3. Lifetimes: visible cascade 0 probes get lifetime 1; parents take the maximum of their children.
4. `reset_table` rebuilds every hash table from the slot keys. Each slot's lifetime drops by one, and slots at zero are freed and their data zeroed. Counts go back to the CPU to size later dispatches.
5. Ray counts: each pixel adds 1 to its base probe; counts sum up the hierarchy. Ray offsets go top-down: top probes take ranges from one global atomic counter and pass sub-ranges to their up to 8 children.
6. One ray per pixel per LOD, traced to the hit or to infinity, then split into cascades (below).
7. Merge top-down, one thread block per probe.
8. Build a 6×6 octahedral irradiance tile (8×8 with border) per cascade 0 probe, then shade.

### Probes and LOD

- One hash table per cascade; the key packs 18 bits per axis plus the LOD, and the cascade is implied by the table. Entry capacity is `4·base_probes`, so the load factor is at most 1/4. Hashing is `pcg3d` with linear probing; insertion is a compare-exchange on the key followed by a freelist pop.
- Probe spacing `base_grid_size·2^(lod + c)`. Presets use `base_grid_size` 4 to 8 scene units and `base_probes` 2^17 to 2^19.
- `lod = max(0, ceil(log2(chebyshev_distance / base_radius)))` with `base_radius` 1200. With `blending_radius` 1.1, points within the top 10% of a LOD band also deposit into the next LOD, with linear weights. The weights jump at integer LOD values, which the code does not explain.
- Directions: `2·R_c × R_c` grid with `R_c = 4·2^c`, so 32, 128, 512 and 2048 directions. Linear index is a Morton code, so the four children of a direction are consecutive. Every cascade holds the same total number of direction cells.

### Split deposit

- `L0 = sqrt(32/(4π)) ≈ 1.596`, chosen so the spacing between ray ends matches the probe spacing. Cascade 0 covers `[0, L0·s0]` and cascade `k` covers `(L0·s0·4^(k−1), L0·s0·4^k]`.
- A ray hitting in cascade `k` deposits `(0, 0, 0, 1)` (transparent) into cascades below `k` and `(L, 0)` into `k`, at the base probe shifted to each cascade. Each deposit adds to `weighted_fluence` and `weights` and bumps the probe's `probe_quality`.
- Directions come from the R2 sequence offset per frame (same offset for every pixel), flipped into the surface hemisphere. Primary rays use `project_line(fract(r2(offset_index) + pcg3df(tick, 29, 968).xy))` and then `dir·sign(dot(dir, normal))` (`src/algorithm/trace.rs:179-182`); the hash depends only on the frame, which is why every pixel shares the offset. Secondary rays (line 239) use the same call without R2.
- `SphericalEncoder` (`sefirot/yesod/src/direction.rs:41-59`) is the Lambert equal-area cylindrical map: `encode(d) = (atan2(d.y, d.x)/2π mod 1, d.z/2 + 1/2)` and `decode(u, v) = (cos h·s, sin h·s, c)` with `h = 2πu`, `c = 2v − 1`, `s = √(1 − c²)`. Azimuth is linear in `u` and height linear in `v`, so equal areas in `(u, v)` cover equal solid angles, which is why the `2·R_c × R_c` direction grid gives every cell the same solid angle. The encoder does not normalize its input. The same file holds octahedral, equirectangular (`θ = acos z`) and Clarberg encoders.
- `project_line(uv) = decode(uv.x/2, uv.y)` (lines 77-81) covers only the `y ≥ 0` hemisphere, uniformly by solid angle; its comment calls the result a line on the unit sphere, and every line through the origin has one representative with `y ≥ 0`. The hemisphere flip then takes the end of each sampled line on the normal's side. Since exactly one of `±d` has `y ≥ 0`, the result is uniform over the normal's hemisphere (density `1/2π`), the same distribution wroughtinator gets by flipping a full-sphere sample (derived from the code, not stated in it).
- Ray to cascade (`trace.rs:259-294`, `compute_deposit_ray`): a miss deposits into the last cascade, and a hit at distance `t` into `clamp(ceil(log_b(t/(L0·spacing(lod, 0)))), 0, last)`, where `b` is the length scale (the interval growth factor 4). The direction is stored through `SphericalEncoder::encode`.

### Merge and temporal reuse

- `radiance_c(j) = own.rgb + own.a · far(j)`, with `own = weighted_fluence/weights` and `far` the trilinear mix of 8 parents at cascade `c+1`, weighted by corner weight times the parent's `probe_quality`. Corner weights are `0.25^n·0.75^(3−n)`, because a parent's center is offset by a quarter of its cell from each child.
- Outputs are stored as quads (the mean of 4 consecutive directions), which is the pre-averaged cone value the next cascade down reads. Cascade 0 also keeps the full 32 directions.
- History is an exponential moving average done by decaying the sums: after each merge, `weighted_fluence` and `weights` are multiplied by 0.97 once `weights > 2`. Camera motion does not reset the cache.

### Shading and memory

- Irradiance tile texel `d_t = Σ_j max(0, d_t·d_j)·L_j` over the 32 directions, divided by the cosine weight sum.
- `shade_optimized_32` uses 8 threads per pixel, one per trilinear corner, each doing one hardware bilinear fetch in the normal direction; the 8 results are summed across the threads.
- Memory from the code formulas for `base_probes = 2^18`: `weighted_fluence` 512 MiB, `weights` 128 MiB, `base_radiance` 384 MiB, `radiance` quads 96 MiB, all fp32 and not measured.
- The TODO list names open problems: LOD blending, slow convergence, an over-darkening shadow fix, leaks near pillars without it, and a wish to convert cascade 0 to SH.
- Two CPU readbacks per frame (probe counts and ray count) are synchronization points.

## split-radiance-cascades-webgpu: native GLSL build

### Data layout

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
- Each hash slot is five `u32` words (signature, token, key low, key high, probe index), double buffered across frames. Probe metadata holds the center and flags.
- Accumulators are five `u32` per direction (fixed-point R, G, B, β, and a count), so deposits use plain integer `atomicAdd`. Composed cones are four words per direction (radiance and β).
- The irradiance atlas is RGBA16F 512×1024, one 8×8 tile per cascade 0 probe at `((probe & 63)·8, (probe >> 6)·8)`.

### Passes

1. Clear the current frame's hash, counters, ray map and accumulators.
2. Primary rays: G-buffer with position, normal, albedo and direct light (shadow rays to the sun and a point light).
3. Insert probe keys for each pixel's fine LOD, and for its coarse LOD when inside the blend band. A second stream inserts probes at `lod + 2` for last frame's hit points.
4. Insertion retries: failed inserts go to a queue that is retried up to 31 times, alternating two queues. A `canonicalize` pass turns published slots into compact probe indices and tombstones duplicates. Parents are inserted the same way for cascades 1 to 3.
5. Rank blocks of 512 slots count rays per probe; prefix passes give each probe a contiguous range of R2 indices, propagated up and assigned back down.
6. `trace_split`: one direction per ray slot, trace, shade the hit, deposit.
7. `merge` from cascade 3 down to 0, one thread per (probe, direction).
8. `irradiance`: 64 threads per cascade 0 probe build its 8×8 tile.
9. `shade` per pixel, then present.

### Tracing and deposit

- Origin `surface + 0.003·normal`; direction `r2(index, jitter)` through the equal-area map, flipped if it points into the surface. Jitter is a Cranley-Patterson shift seeded by the frame counter. `r2(i, j) = fract(0.5 + i/g, 0.5 + i/g² + j)` with `g = 1.324717957244746`, the plastic number (`native/shaders/split_rc.glsl:72-75`); `decode_equal_area` (`split_rc.glsl:77-87`, `native/src/math.rs:20-37`) is the same Lambert cylindrical map as chandra's `SphericalEncoder`, and its encoder normalizes first.
- Hit radiance is `direct + albedo/π · previous_irradiance(position, normal, lod + 2)`, where `previous_irradiance` reads last frame's coarse secondary probe at the nearest octahedral texel. That one lookup gives multi-bounce light that grows over frames.
- Deposits use the cell of the ray origin at each cascade, not the probe center: transparent `(0, 0, 0, β = 1)` below the target cascade, `(L, β = 0)` at the target, nothing above.

### Merge, history and shading

- Static scenes: exact running average per direction, `(I·n + H·h)/(n + h)` with `h = min(previous_count, 16384)`. Animated lights: `mix(current, previous, 0.92)`, or no history for frames over 50 ms. The filtered raw interval is written back, not the composed value.
- `cone = clamp(I + β·F, 0, 16)`. The top cascade uses the environment color for `F`. Otherwise `F` averages the four child directions of the parent cascade read at 8 trilinear corners, normalized over corners that exist with a nonzero count.
- Irradiance per tile texel: `E = π·Σ cone·max(0, n·d)/Σ max(0, n·d)` over directions with samples.
- Shading: 8 trilinear corners per LOD, each one hardware bilinear read from the atlas, fine and coarse LODs mixed by the blend weight; indirect is `albedo/π · E`.
- Optional screen-space cascade −1: 32 directions, 8 march steps up to `s0·2^lod` against the depth buffer, a hit returns that pixel's direct light, otherwise the cascade 0 cone shows through.
- Adaptive resolution: every 90 frames the internal scale drops by 0.9× above 1/48 s and rises by 1.05× below 1/75 s.

## split-radiance-cascades-webgpu: browser build

The WGSL build shares the structure with these differences:

- Probe keys are 32 bits: 9 bits per axis, 2 bits of LOD, 3 bits of surface class. The class is the dominant axis of the normal, so probes on different sheets of a thin wall do not share data.
- Four LODs from `18·ds0`, cross-fading from 0.75 of each boundary. Base spacing comes from scene size: `max(0.22, radius·0.077/triangles^0.12)`.
- Each pixel inserts four tangent-plane neighbor probes, and shading uses those 4 corners with Hermite weights `t²(3 − 2t)` on static receivers (8 corners on moving objects).
- Near emitters within `1.5·ds0` are cut from the ray radiance with a smoothstep and added back by an analytic `nearEmissiveIrradiance` term, which avoids fireflies from small nearby lights.
- A world-space cascade −1 for closed meshes traces 14 fixed short rays (6 axes and 8 diagonals) up to `ds0` and weights them with `smoothstep(0, ds0, t)`.
- History is a sample-count average capped at 65535, a 0.92 to 0.992 blend for moving lights, and an exact-key fallback to up to three earlier frames for missing probes. Hit radiance has direct light only.
- Albedo is sampled at mip level 2 at hit points, because mip 0 made sub-pixel detail flicker between frames.
- The screen-space temporal block in the final pass is behind a constant `false`, so it never runs.
- The documents disagree with the code in several places (base spacing formula, history weight 0.965, cascade −1 radius `15·ds0`); the code is what runs.
- Live demo: described below.

## The live demo

https://wroughtinator.github.io/ is the static production build of the browser version (repository wroughtinator/wroughtinator.github.io at 6698f7a; read from source, not run). It needs a WebGPU browser (Chrome or Edge 113+).

- **Scenes** (`rc/scenes.js:267-281`, 13): color bleed laboratory, dynamic Sponza atrium (the 262k-triangle Crytek Sponza plus 48 moving rigid meshes), concave canyon heightfield, dense lantern forest, multi-level atrium, industrial pipe maze, sun temple, orbital sculpture field, daylight door room, megacity stress grid, Cornell box, grand concave heightmap, universal visibility laboratory. The page's static text says "ten real-time validation scenes", "01 / 10" and "Run 10-scene audit", but the runtime takes the label and the audit length from the scene list (`rc/engine.js:2972`, `6694-6701`), so both cover 13; the repository description also says 13.
- **Views:** final composite, indirect only, direct only, surface normals, effective probe coverage, albedo.
- **Controls:** indirect strength and sun animation sliders (0 to 2, default 1); toggles for the camera path, moving lights, "Stable history" (temporal stability) and the pass profiler, all on by default; orbit, zoom and WASD movement. The profiler reports GI grid, frame, geometry, ray split and merge, composite, and dynamic TLAS and upload.
- `?quality=` selects a preset and `?autotest=dynamic-sponza` runs a dynamic-scene gate. Every preset traces one R2 ray per visible pixel (`raysPerSample` 1, the paper's Algorithm 3), so the pixel cap is also the ray budget per frame:

| Preset (`engine.js:55-68`) | Pixel ratio | Max pixels (rays per frame) | Shadow map |
|---|---|---|---|
| Performance | 0.72 | 90,000 | 768 |
| Balanced (default) | 0.9 | 160,000 | 1024 |
| Quality | 1.0 | 420,000 | 1536 |
| Ultra | 1.0 | 720,000 | 2048 |
