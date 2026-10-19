# Screen-space RC implementations

Public code for screen-probe 3D RC: standalone repositories, two engine plugins, Shadertoys, design sketches and the depth-aware upscaling shaders the field relies on. The parameters of every code are compared in [3D screen space](3d_screen_space.md#parameters-across-projects), and the theses built on two of these repositories are in [screen-space theses](3d_screen_space_theses.md).

| Code | Family | API | Tracing | Last change |
|---|---|---|---|---|
| [three-rc](#three-rc) | SPWI | three.js, WebGL | BVH in GLSL | 2026-02-09 |
| [ClaikoCode/DX12RadianceCascades](#claikocodedx12radiancecascades) | SPWI | D3D12, HLSL, DXR on MiniEngine | hardware RT, TLAS updated each frame | 2026-04 |
| [Qirias/RC-SPWI](#qiriasrc-spwi) | SPWI | Metal (Apple silicon) | hardware RT against one static structure | 2026-09 |
| [Alpha-Renderer](#alexander-koutrakisalpha-renderer) | SSRC | Vulkan, GLSL compute | min/max depth pyramid march | 2026-10 |
| [KingTheFifth/radiance-cascades](#kingthefifthradiance-cascades) | SPWI | Rust, glow, fragment passes | voxels, depth march or Hi-Z | no timings recorded |
| [BeansEngine](#beansengine) | per-pixel probes | Rust, ash, Slang | inline ray queries | removed 2026-04-18 |
| [Unreal plugin](#unreal-screen-space-bitmask-rc) | SSRC | Unreal 5.8.2, SM6 | screen slices with 32-sector masks | 2026-10 |
| [Unity URP plugin](#unity-urp-plugin) | SSRC | Unity 6.2 URP | depth march, three modes | 2025-08 |
| [lXByRh](#lxbyrh-hit-point-reprojection), [scy3Dd](#scy3dd-spwi-in-one-shader), [33ycDm](#33ycdm-gtao-from-cascaded-horizons) | Shadertoys | GLSL | analytic, depth | 2024 to 2026 |

## three-rc

| | |
|---|---|
| Author | Cody Bennett (CodyJasonBennett) |
| Date | 2026-02-09 (last commit) |
| Link | https://github.com/CodyJasonBennett/three-rc |
| Licence | none; the README ends "All rights reserved" and says the licence was omitted because the upscaler credited to Sannikov cannot be licensed |

A three.js implementation in one module (`src/index.js`) with inline GLSL. Screen-space probes trace rays against a world-space BVH built once at startup, cascade results live in screen-sized float textures, and a composite pass shades the G-buffer from level 0. Only emitter radiance enters the cascades ([three-rc](../sources/2025_bennett_three_rc.md)).

**Setup.**

1. The Sponza glTF loads with a Draco decoder from gstatic (1.5.5); a 1×1×1 box at (0, 0.5, 0) gets a white emissive MeshStandardMaterial with `emissiveIntensity` 10.
2. Each visible mesh is cloned, given a per-vertex `id` equal to its index in the mesh list, transformed to world space and merged into one indexed geometry, never updated after startup.
3. One `MeshBVH` over the merged geometry, `maxLeafTris: 1`, SAH split, `indirect: true`; three-mesh-bvh dereferences the index texture into leaf order, so a hit triangle's first vertex index is a real vertex index.
4. An emitter table, a one-row texture with one RGB float texel per mesh (emissive colour × intensity, nearest sampling, 0 for non-emitters), and a UInt vertex texture of the merged `id`, so a hit selects the mesh and then its emitter texel.
5. Probes on a screen grid of tile centres, each reading depth and reconstructing its world position; probes are not placed in 3D.
6. `reversedDepthBuffer: true`, which in three r181 takes effect only with `EXT_clip_control`; otherwise normal depth is used, the `USE_REVERSED_DEPTH_BUFFER` define is not set, and the shaders follow the active mode.

**Passes.** `W × H` is the drawing buffer; the device pixel ratio is clamped to [1, 1.25] and the canvas is the window size times that ratio; targets resize in `onresize`, which runs at startup and on every resize.

1. G-buffer: output 0 RGBA16F (`diffuseColor.rgb` with alpha 1, or `totalEmissiveRadiance` with alpha 0 for emitters); output 1 RGBA8 (`octEncode` of the view normal in r and g, metalness in b, roughness in a; zeros for emitters); a FloatType depth texture, background cleared to 0 under reversed depth.
2. Cascades `L = N − 1` down to 0 (`N` is `NUM_CASCADES`), each a full-screen triangle from `gl_VertexID` into one of two ping-pong targets (`W × H`, R11F_G11F_B10F, with an unsampled depth attachment); `cascadeTargets.reverse()` per pass leaves level 0 in `cascadeTargets[1]`. Uniforms: `resolution`, `intervalLength` 0.005, `probeSpacing` 4, `cascadeLevel`, `numCascades`, the previous cascade, depth, the BVH struct, the `id` texture, the emitter table, `viewMatrixInverse` (from `camera.matrixWorld`) and the projection.
3. Composite to the canvas (uniforms `resolution`, `probeSpacing` 4, `cascadeTexture` at level 0, `albedoTexture` and `normalTexture` from G-buffer outputs 0 and 1, `depthTexture` and `viewMatrixInverse`), then ACES Filmic tone mapping, sRGB and dithering; background pixels are discarded.

**Math.**

- `T_L = 4·2^L` is both the tile size in pixels and the direction bins per axis; the grid is `G_L = (ceil(W/T_L), ceil(H/T_L))`; directions per probe `D_L = T_L² = 16·4^L`; each level stores about `W·H` texels and traces one ray per texel.
- Probe `q` sits at UV `(q + 0.5)/G_L`; depth is read with `textureLod` at LOD `L`, but the texture has no mips, so the sample is the nearest full-resolution texel. Linearization: in standard mode `z → 2z − 1`, then `viewZ = −P32/(P22 + z)`; for three's reversed projection (`P22 = near/(far − near)`, `P32 = far·near/(far − near)`) `z = 1` gives `−near` and `z = 0` gives `−far`. View position `x = −(1/P00)(2u.x − 1)·viewZ`, `y = −(1/P11)(2u.y − 1)·viewZ`; world position `viewMatrixInverse·(0.98·viewPos, 1)`, 2% toward the camera, for probes and the composite alike.
- Direction bin `d` has UV `(d + 0.5)/T_L` and direction `octDecode(UV)`: `f = 2·UV − 1`, `n = (f.x, f.y, 1 − |f.x| − |f.y|)`, folded by `(1 − |n.y|, 1 − |n.x|)·signNotZero` when `n.z < 0`, normalized.
- Layout: texel `p` holds probe `q = p mod G_L` and direction `d = p div G_L`, so `(q, d)` is at `d·G_L + q`.

| Level | `T_L` | Directions | Traced range | `getIntervalRange` end |
|---|---|---|---|---|
| 0 | 4 | 16 | 0 to 0.02 | 0.02 |
| 1 | 8 | 64 | 0.02 to 0.10 | 0.08 |
| 2 | 16 | 256 | 0.08 to 0.40 | 0.32 |
| 3 | 32 | 1024 | 0.32 to 1.60 | 1.28 |
| 4 | 64 | 4096 | 1.28 to 6.40 | 5.12 |
| 5 | 128 | 16384 | 5.12 to 25.60 | 20.48 |
| 6 | 256 | 65536 | 20.48 to 102.40 | 81.92 |
| 7 | 512 | 262144 | 81.92 to 409.60 | 327.68 |

- Start is `intervalLength·scale(L)` with `scale(0) = 0` and `scale(L) = 4^L`; the second value of `getIntervalRange` is `intervalLength·scale(L + 1)`. The shader moves the origin to the start and accepts hits with `t` below that second value measured from the moved origin, so the traced range is `[start, start + length]` and levels overlap: for `L ≥ 1` level `L` traces to 5× its start while level `L + 1` starts at 4×. The traversal's comment says "Min is ignored", but the start is applied by moving the origin. The triangle test accepts `t ≥ −1e−5` and both faces.
- A closest hit returns the hit mesh's emitter texel (0 for non-emitters) and does not merge, even on a non-emitter; a miss at the top level returns `getEnvColor`, which is `vec3(0)`; other misses merge from level `L + 1`.
- Merge, for a lower probe at `x` and direction `d`: upper coordinate `c = (q + 0.5)/G_L·G_{L+1} − 0.5`, base `floor(c)`, corners clamped to the grid; corner world points `P_k` from depth at the upper corner centres; ratio solve from `r = fract(c)` for four iterations, `r.x = proj(x; mix(P0, P2, r.y), mix(P1, P3, r.y))` then `r.y = proj(x; mix(P0, P1, r.x), mix(P2, P3, r.x))` with `proj(p; a, b) = saturate(dot(p − a, b − a)/dot(b − a, b − a))`; bilinear weights from `r`; direction bins `2d + o_j`, each weight 1/4, fixed because the lower direction's fraction is always 0.5; result `Σ w_k·¼·R_{L+1}(q_k, u_j)`.
- Composite: bilinear over the four nearest level-0 probes (`G0 = ceil(W/4)`, corners `q_k = clamp(b + o_k, 0, G0 − 1)`), and for each of 16 directions `octDecode((d + 0.5)/4)` reads `C0(q_k, d)` (emissive pixels use their own albedo); output `Σ w_k·f_BRDF(V, N, dir)·S` with no `1/16` or `4π/16`, `V` toward `viewMatrixInverse[3].xyz` and `N` the world-space normal.
- Cascade count `Math.ceil(Math.log(Math.max(W, H), 4))`: `Math.log` ignores its second argument, so the count is `ceil(ln max(W, H))`, 7 at 1024×768 (against `ceil(log4)` = 5), 8 at 1280×720, 1920×1080 and 2560×1440 (6), 9 at 3840×2160 (6). Each extra level adds a full-screen pass; at 1080p the top level starts at 81.92 units.

**Upscaler.** The README credits Sannikov's 4XXSWS for depth-aware interpolation; in the code the only depth-aware weighting is the ratio solve (`getBilinear3dRatioIter`) in the merge, and `projectLinePerpendicular` links the same Shadertoy. The composite uses fixed 2D bilinear weights with no depth or normal terms, evaluating the BRDF per pixel for each of the four probes and blending the four results; it has a TODO for screen-space cascade −1 and no Hi-Z or min/max.

**Issues found by reading** (not run):

- Non-divisible sizes: when `W` or `H` is not a multiple of `T_L`, `d·G + q` can pass the texture edge, and the merge reads without a bounds check; at 1080p the merge into level 4 reads level 5 (`T = 128`, `G_y = 9`) at row `127·9 + 8 = 1151`, outside 1080 rows, an out-of-range `texelFetch` that GLSL leaves undefined (not run).
- Degenerate ratio solve: if both corners of a pair clamp to one probe the projection divides by zero; with an exact 2:1 grid ratio the first column gives `c = −0.25` and corners 0 and 1 coincide, and GLSL leaves 0/0 undefined (not run).
- Only emitters carry light; bounce from non-emissive surfaces is not modelled.
- Emissive pixels use their radiance as both BRDF albedo and sampled colour, and the emission itself is not written.
- Normalization: 16 terms with weight 1 are 4/π (about 1.27) times the sphere integral for equal-solid-angle bins.
- Background probes at depth 0 linearize to `−far` (2000) and sit at `0.98·2000` along their view ray, with no special case.
- The BVH and emitter table are static; tracing uses the constant emissive colour × intensity while the G-buffer uses `totalEmissiveRadiance`, so textured emitters disagree; the emissive decision reads only the constant colour.
- The composite hard-codes level 0 with `probeSpacing` 4, which must match `PROBE_SPACING`.
- TODOs in the file: the geometry clone "won't scale well"; IOR and anisotropy, packed into the G-buffer; Hi-Z min/max; screen-space C-1 tracing; "seems broken on a complex scene like Bistro"; three should accept Float16Array.
- README notes: probe storage is a fixed cost in a screen-size texture, with no temporal accumulation; it describes a Tiny Glade screen-space raymarcher variant not in this code, which no longer models off-screen occluders or emitters. Future work: a TLAS and material lookup for complex scenes (Bistro does not look up emissive triangles in the right order), a screen-space gather for contact effects, about 16× upscaling, prefiltering and min/max probes.

**References in the README and code.** The RC paper (Google Drive), three-mesh-bvh, 4XXSWS, and Stachowiak's 2023 Tiny Glade post with its depth-buffer marcher ([scene representation and tracing](scene_representation_and_tracing.md)); Cigolle et al. for octahedral mapping; Unreal's mobile shading post for `F_AB` ([glossary](supporting_techniques.md)); and Aaltonen's depth linearization, `z_lin = 2n/(n + f − z(f − n)) = 1/(z·A + B)` with `A = −(f − n)/2n` and `B = (f + n)/2n` precomputed per frame from the projection matrix, one reciprocal and one multiply-add per pixel. three-mesh-bvh's ray functions (now in `src/webgl/glsl/`) use 32-byte nodes whose bounds take two RGBA32F texels and whose contents an RG32UI texel, defaults of centre split, depth 40 and 10 triangles per leaf, and a stack-based closest-hit traversal that visits the near child by the ray's sign on the split axis; the stack holds 60 entries, its comment calls that twice the deepest tree although a pop-one-push-two walk grows by about one entry per level, and the WebGL version has no overflow check while the WebGPU one does.

**The JSFiddle** (https://jsfiddle.net/ezsyu6dg/, "Radiance Cascades 3D - three.js", 843 lines) is a compact form of the library: Sponza from a third-party host, three-mesh-bvh with one triangle per leaf and SAH, reversed depth, FOV 95, pixel ratio capped at 1.25, `BASE_INTERVAL_LENGTH = 0.005`, `PROBE_SPACING = 4`. Cascade `c` uses `4·2^c` px tiles and `2^(c+2)` octahedral rays per axis over the full sphere with world intervals `0.005·[4^c, 4^(c+1)]` (cascade 0 `[0, 0.02]`); probes sit at the depth of mip `c`; a BVH hit returns its colour, the last cascade returns the sky, and other rays merge with four direction taps and depth-aware 3D bilinear weights over four upper probes solved in four iterations; the composite shades every direction of the four nearest probes with Burley diffuse and Schlick Fresnel. It has the same `Math.log` bug.

**Derived.** At 1080p three-rc traces 8 cascades × `W·H` = 16.6 M rays per frame and holds two R11G11B10 targets, 15.8 MiB; with its 0.02 cascade 0 interval and 4 px probes it breaks `Δp ≲ t0` beyond about 4.7 m of view depth at a 60° field of view, about 2.5 m at the fiddle's 95° ([3D screen space](3d_screen_space.md#interval-units-and-view-depth)).

## ClaikoCode/DX12RadianceCascades

The code behind [Dell'Ova's thesis](3d_screen_space_theses.md#dellova-2025-performance-scaling-with-dxr), whose note also answers the thesis's gaps from this code ([repositories](../sources/2026_screen_space_probe_repositories.md#claikocodedx12radiancecascades)).

- Defaults: cascade 0 probes every 2 px, 16 rays per probe, `rayLength0` 5, rays ×4 and spacing ×2 per cascade, up to 8 cascades (`floor(log2(min probe count))`).
- Direction-first (the thesis gives no exact linear index; see [theses](3d_screen_space_theses.md)): `probeIndex = pixel mod probesPerDim`, `rayIndex = floor(pixel/probesPerDim)`; equal-area octahedral directions over the full sphere.
- Intervals start `5·(4^c − 1)/3`, length `5·4^c`: `[0, 5], [5, 25], [25, 105], [105, 425]`. No leak fix.
- With pre-averaging on (the default) the ray generation shader traces 4 sub-rays per stored texel and averages them, so each texel side is `√(rays/4)`.
- Closest hit returns only the emissive texture: one bounce from emitters. The last cascade's misses read the skybox.
- Merge per sub-ray: a 4-tap bilinear read of cascade `N + 1`, `rgb = near.a·far.rgb`, averaged and added to the near value in place. A depth-aware path with depth-aware "bilinear 3D" weights from reconstructed world points exists but is off.
- Final lighting reads the nearest cascade 0 probe (no interpolation), sums cosine-weighted directions and divides by the ray count with no `1/π`, a quarter of Lambertian shading; the thesis's bilinear read of the coalesced buffer is a dead branch.

## Qirias/RC-SPWI

https://github.com/Qirias/RC-SPWI, Metal on Apple silicon, hardware ray tracing against one static triangle structure, last commit 2026-09 ([repositories](../sources/2026_screen_space_probe_repositories.md#qiriasrc-spwi)).

- Six cascades, probes every 4 px, octahedral directions with `4·2^L` texels per side, 16 base rays.
- Intervals `start = 0.4·4^(L−1)·len`, `end = 0.4·4^L·len` with `len` 0.6: `[0, 0.24], [0.24, 0.96], [0.96, 3.84]`.
- The upper merge uses Suslik's iterated bilinear 3D ratio ([below](#4xxsws-depth-aware-upscaling)); the final gather a bilateral threshold of 0.05.
- A min/max depth mip pass and a blur pass exist but are never dispatched. The README says it is not ready for use.

Its Metal target, 6 cascades, 4 px probes, 16 base rays, bilinear 3D merge and 0.05 final-gather threshold all match Gavras's thesis, apart from an interval constant 15× larger, which suggests a shared lineage (inference from the parameters).

## Alexander-Koutrakis/Alpha-Renderer

https://github.com/Alexander-Koutrakis/Alpha-Renderer, Vulkan with GLSL compute, the only screen-probe RC here written as compute shaders, last commit 2026-10 ([repositories](../sources/2026_screen_space_probe_repositories.md#alexander-koutrakisalpha-renderer)).

- Frame: shadow, G-buffer, sky, direct light, RC GI, transparency, composition (`opaque + GI`), SMAA, colour grading. The RC pass reads direct light without albedo (`outIncident`) as the radiance of what rays hit.
- Depth is linearized, then reduced into a min/max pyramid (RG16F) over the full mip chain. Rays march it coarse to fine with `clamp(8 + int(1.5·√maxDist), 8, 48)` steps from a start offset of `max(0.01, 0.0015·linear depth)` along the normal.
- Six cascades. Cascade 0 probes every 2 px with a 2×2 hemisphere tile; tile side `2 << c`, so `4^(c+1)` directions. Hemisphere directions shrink slightly toward the pole: `mix(0.90, 0.98, clamp((tile − 2)/6, 0, 1))`.
- Bands `[0, 0.32], [0.32, 1.28], …, [81.92, 327.68]` (base 0.08 × `4^c`), each dispatch extending its band by 15% of the previous band's length for overlap.
- Hit radiance `incident·albedo·kD/π`; hit transmittance is a squared smoothstep of the normalized hit distance instead of 0.
- Merge `near.rgb + near.a·far.rgb` with bilateral weights and 2×2 angular bilinear reads. The resolve takes 2×2 samples per pixel, reprojects with the previous view-projection for temporal accumulation and multiplies by a `GI_BOOST` of 3. The sky contribution is off.
- README claim: about 5.5 ms total at 1080p on an RTX 3070 and about 80 MB of memory.

At 2 px probes with 4 directions, each cascade is one screen-sized texture and one ray per pixel, 12.4 M rays per frame at 1080p over 6 cascades (derived). The soft transmittance and the 15% overlap blur the interval boundaries that the binary RC merge assumes (inference).

## KingTheFifth/radiance-cascades

https://github.com/KingTheFifth/radiance-cascades: Rust with glow, all in fragment passes; the README calls the 3D part SPWI. No timings are recorded ([repository survey](../sources/2026_rc_repository_survey.md#screen-probes-with-voxel-intervals-kingthefifth)).

- **G-buffer:** albedo and emissive RGBA32F, a world-space octahedral normal in RG16F (a uniform comment wrongly says view space), D32 depth, and a min/max depth pyramid in RG32F whose level 0 stores `(d, d + 0.005)`; all 11 levels rebuilt every frame.
- **Probes and directions:** one probe per 4 px at cascade 0, at the depth of its own pixel rather than a block minimum; sky pixels skipped. Cascade `c` has spacing `4·2^c` px and `4·2^c` azimuths × `4·2^c` altitudes (`16·4^c` directions, azimuth `(i + 0.5)·2π/N`, altitude `(j + 0.5)·π/N`, y up), latitude-longitude stored direction-first. Each cascade texture is `4·W/s` texels per axis, screen-sized at `s = 4`; six RGBA32F cascades take about 199 MB at 1080p.
- **Intervals:** `L0 = 4`, computed from the probe diagonal in pixels but used as world units; cascade `c` covers `[L0·(2^c − 1), L0·(2^(c+1) − 1))`, doubling: 0–4, 4–12, 12–28, 28–60, 60–124, 124–252. Rays start at `probe + dir·start + normal·0.1`.
- **Tracing:** by default a 256³ RGBA16F voxel grid (about 134 MB) over a 30 × 15 × 16 box, so voxels are anisotropic, re-voxelized each frame by dominant-axis projection, storing only `(emissive, 1)` (diffuse computed and dropped, last write wins). Each interval takes exactly 400 evenly spaced samples whatever its length, a hit being alpha above 0.05; rays leaving the box miss. Alternatives: a naive screen-space march of `20·2^(c+1)` steps and a Hi-Z traversal after Beug's SSR (at most 400 steps).
- **Merge:** a hit or the top cascade returns `(rgb, 1 − alpha)`; otherwise the ray adds 0.25 × the sum of its 4 upper directions, each a hardware-bilinear tap at `clamp(0.5·coord + 0.25, 0.5, count − 0.5)`. Depth-aware interpolation is a TODO.
- **Integration:** a cosine-weighted sum over cascade 0 divided by the total weight and again by 16, times albedo and a diffuse intensity of 15, so a uniform field `L` returns `(15/16)·albedo·L`. Light comes from emissive voxels only, with no bounce.
- **Defects found by reading:** π typed as 3.14169265; the cascade texture is sized with unfloored `4·W/s` while the shader floors the probe count; `imageLoad` runs before the bounds test; alpha is unbounded, each missed level adding 1, so open sky reaches 5 at cascade 0 with 6 cascades, and the AO term `2·mean(alpha)/16` gives 0.625 in the open and 0.125 when occluded.
- **2D part:** 2 px spacing, `ceil(log4(diagonal))` cascades, intervals from `L0·(4^c − 1)/3` with length `4^c·L0`, 4 rays per stored direction, gamma 1.6.

Its 400 samples per interval over a doubling interval make the step length double per cascade while voxels stay one size, so upper cascades skip voxels: the 124-to-252 interval at 400 samples steps 0.32 units over voxels 0.06 to 0.12 units wide, and from cascade 3 on the intervals run past the 30-unit box (derived from the box and grid).

## BeansEngine

https://github.com/joelmartin-dev/BeansEngine is a Rust and `ash` Vulkan engine whose README says it exists to compare RC with ReSTIR. Its `main` branch now only rasterizes unlit glTF scenes: the RC, ReSTIR and reference shaders and about 985 lines of engine code were removed on 2026-04-18 (commits 4b3e618 and c9cf5ce, "removed global illumination capabilities, needs documentation before proceeding"). The history holds two Slang variants ([repository survey](../sources/2026_rc_repository_survey.md#joelmartin-devbeansengine-rc-removed-from-history)):

- **Software** (`assets/shaders/software/radiance_cascades.slang`, 302 lines, compute with inline ray queries despite the name): every pixel is a probe with one output image per level and `baseRayCount << level` rays. Level `L` covers `[s·L², s·(L + 1)²]` with `s = 1/interval`, growing quadratically. The probe sits along the primary ray at a level-dependent fraction of the first-hit distance, minus 0.001. Directions follow a golden-angle spiral. On a miss the coarser level's output at the same pixel is added at half weight, a per-pixel merge with no spatial or angular interpolation. Results are saturated with `1 − exp(−x)` and averaged.
- **Hardware** (`assets/shaders/hardware/radiance_cascades.slang`, 124 lines): one dispatch per level with `(level + 1)·8` rays per pixel over fixed slabs of length `interval/1000`, offset by `level·interval/1000` from a point 4 units in front of the camera, so intervals do not grow. No merge: the fragment shader sums all level textures. Each sample is divided by `(ray_idx + 1)·8` rather than the ray count, so later rays weigh less, which looks like a bug.
- Timeline: "still struggling with merging intervals" (2025-11-01), "Semi-working RC" (2025-11-03), the hardware and software split (2025-12-24), "radiance_cascades restarted" (2026-03-09), removal (2026-04-18). An earlier C++ version moved in 674d08a (2025-12-19) to a repository not found. No measurements exist.

Neither variant keeps RC's structure: the probes do not coarsen, the directions do not nest, and the merge has no transmittance, so the code is a set of distance-sliced per-pixel gathers (inference).

## Engine plugins

| Repository | Engine | Modes | Last commit |
|---|---|---|---|
| https://github.com/Twenmod/UERadianceCascades (no licence) | Unreal 5.8.2 plugin, SM6 | screen-space bitmask RC; world-space Split RC with hardware RT | 2026-10 |
| https://github.com/alexmalyutindev/unity-urp-radiance-cascades (MIT) | Unity 6.2 URP render feature | 2D screen probes, cube-map probes, direction-first probes with SH output | 2025-08 |

The Unreal plugin's world-space Split RC mode is in [3D world space implementations](3d_world_space_implementations.md) ([plugins](../sources/2026_unity_unreal_rc_plugins.md)).

### Unreal: screen-space bitmask RC

The most developed screen-space variant found: RC intervals carried as visibility bitmasks, as in [bitmask SSGI](related_screen_space_gi.md). It runs after post-processing reaches "before DOF", on the pre-DOF scene colour, depth and G-buffer normals.

- Parameters: `R` base rays per probe (4 or 16), tile size `T` (2 or 4 px), wall thickness 300 view units. Probe spacing at cascade `c` is `T·√R^c` px with `R^(c+1)` rays per probe.
- Cascade count `clamp(ceil(log(diagonal)/log(R)) + 1, 1, 32)` from the probe grid diagonal: 4 at 1080p with `R = 16, T = 4`, 7 with `R = 4, T = 2` (derived).
- Intervals in pixels: `start_c = 2T·(R^c − 1)/(R − 1)`, length `2T·R^c`: `[0, 8), [8, 40), [40, 168)` for `R = T = 4`.
- Each ray is a 2D screen slice, up to 8 samples per interval with blue-noise jitter. Each sample becomes a front point and a back point (front pushed back by the wall thickness), whose angles in the slice mark covered sectors of a 32-bit mask.
- Sector weights `w_j = sin((j + 0.5)·π/32)`, a cosine weight across the slice; their sum `1/sin(π/64) ≈ 20.38` normalizes. A sample adds its colour times the weight of the sectors it newly covers. The stored value is radiance plus the mask, and the interval's openness is the weight of its uncovered sectors.
- Merge: the upper value is scaled by the fraction of the upper interval's covered sectors that this interval leaves open, `WeightedBitSum(UpMask & ~mask)/WeightedBitSum(UpMask)`, and the masks are OR-ed. This replaces the scalar β with a per-sector one, so light hidden by near geometry in one part of the slice still passes in another.
- Upper probes are blended with bilinear 3D weights (two projection iterations onto the quad of four upper probe positions).
- Apply: 4 probes per pixel with `saturate(1 − planeDistance/(0.03·depth))` weights from the pixel's normal plane, falling back to the nearest probe; result `color + rgb·π·intensity·diffuseColor`.

Each probe has `R^(c+1)` rays at spacing `T·√R^c`, so every cascade traces one slice per pixel for either setting (derived). The per-sector β is the merge-operator generalization that PoE2's 128-bit masks suggest, and it is the only screen-space merge found that keeps directional occlusion within an interval (inference).

## Unity URP plugin

alexmalyutindev's render feature has three modes. All three share the merge `rgb += upper.rgb·a; a *= upper.a`, where a hit writes alpha 0 and a miss alpha 1; a shared table also defines ×4 intervals `(4^L − 1)/3` to `(4^(L+1) − 1)/3`. The README says the project tries "to generalize [RC] for 3D". No mode has timings ([plugins](../sources/2026_unity_unreal_rc_plugins.md)).

### Unity: direction-first screen probes

- Depth inputs: a min/max depth mip chain (3×3 min/max at mip 0), blurred depth moments `(d, d²)`, and a blurred colour mip chain for lighting.
- Six cascades with probes every `8·2^L` px on a 2048×1024 grid. Each probe has two depth probes, at the minimum and maximum depth of its tile, stored in the left and right halves of the texture.
- Directions in view space: `4·2^L` azimuths and 4 polar angles. Interval ranges double per level (`[0, 1], [1, 2], [2, 4], …` × `RayScale`).
- Each ray traces 16 "virtual depth rays" with offsets in [−1, 1] against the variance-filtered depth `mean + σ`, reading colour from the blurred mip `L + 1`; the 16 results are averaged into one value with transmittance. The author calls this variance trapezoid integration (from [l3scz8](#l3scz8-occlusion-from-depth-variance)). In the author's issue #13, cascade `N` holds `4·2^N` view-aligned directions in rows and 4 depth rays per direction in columns, the 16 samples per direction being grouped into 4 stored rays ([discussions](../sources/2026_rc_discussions.md#implementer-notes)).
- Merge blends the min and max halves of the upper cascade by where the lower probe's depth falls between the upper min and max. A fixed factor `radianceSectorSize = 0.25/(1 << level)` scales the upper value, which the author describes as just a `1/rayCount` term, not a derived one.
- Cascade 0 is projected onto L1 spherical harmonics per probe at quarter resolution and upsampled bilaterally against the min/max depth.
- The README and issues call the mode unstable under camera motion; the min/max pair made it the most stable of the three. The author calls gathering and upscaling the most crucial unfinished part.
- From the code: probe centres at `(i + 1)/(count + 1)` in UV; min/max depth from mip `L + 2`; probes beyond linear depth 500 skipped; a ray marches `4·(end − start)` steps with a fixed 3.0 thickness (`linearDepth < rayDepth < linearDepth + 3`); the upper cascade is read bilaterally with a Chebyshev variance test on the smoothed depth (mip `L + 3`); the SH output is 1024×512; the intervals in use are `(0, 1), (1, 2), (2, 4), …, (16, 32)`, and a ×4 table is defined but unused; the README's open TODO is the depth-guided upsampling.

### Unity: 2D screen probes

Every cascade is a 512×288 texture, with directions at `(i + 0.5)·2π/P²` growing ×4 per level and ray length scaled by the buffer size. A hit is a raw depth compare. Each texel pre-averages its 4 nearest angles, and spatial weights are 0.25 and 0.75. The merge skips texels whose alpha is below 0.5 and runs top-down. The combine pass interpolates probes bilinearly and multiplies by the G-buffer albedo with additive blending.

### Unity: cube-map probes

Five cascades in one 512×384 ARGBHalf atlas, each probe a 2×3 grid of cube faces. Probes sit on the depth-buffer surface at probe centres, pushed 0.01 along the view ray. Directions are `((i + 1)/(P + 1) − 0.5)·π/2` on both face axes, rotated by a per-face basis. The only dispatched trace marches in clip space against the depth buffer. The merge averages 2×2 upper directions and interpolates bilinearly.

- A 128³ ARGB32 voxel volume over ±10 units around the camera is built every frame (albedo × `N·L` and shadow, plus emission, last write wins) and bound, but the voxel trace kernel is never dispatched and the compute voxelizer returns before its dispatch, so the mode is screen-space only.
- Found by reading: the right and top voxelization projections are gated on the device lacking geometry shaders, which the shader does not use; the combine pass picks the face from `normalWS.y` where `normalWS.z` looks intended; under the matrix convention used, three face bases appear to map to −X.

## Shadertoys

### lXByRh: hit-point reprojection

"RC - Screen Space Probes" by Mathis (2024-12-16) places hemispherical probes on a half-resolution G-buffer and merges each cascade from the next coarser one by reprojecting the coarser rays' hit points into the finer probe with a visibility test, instead of compositing intervals. Its only smoothing is temporal; the comments say there is no spatial denoising and some flicker remains ([Shadertoys](../sources/2023_rc_shadertoys.md#lxbyrh-mathis-screen-space-probes-merged-by-hit-point-reprojection)).

- Six cascades in the top and bottom halves of Buffers B, C and D (cascades 2 and 5, 1 and 4, 0 and 3). Cascade `n` tiles the half-resolution G-buffer into probes of `P × P` texels with `P = 2^(n+1)`, one texel per direction, so every cascade traces about one ray per half-resolution texel.

| Cascade | Probe tile (half-res texels) | Spacing (px) | Directions | Polar angles of texel centres |
|---|---|---|---|---|
| 0 | 2 | 4 | 4 | 45° |
| 1 | 4 | 8 | 16 | 22.5° to 67.5° |
| 2 | 8 | 16 | 64 | 11.25° to 78.75° |
| 3 | 16 | 32 | 256 | 5.63° to 84.38° |
| 4 | 32 | 64 | 1024 | 2.81° to 87.19° |
| 5 | 64 | 128 | 4096 | 1.41° to 88.59° |

- Directions cover the hemisphere around the pixel normal: texel ring `r` (Chebyshev distance from the tile centre) sits at polar angle `(r + 0.5)·π/P` with `8r + 4` evenly spread azimuths ([cascade layout](cascade_layout_and_merging.md#direction-maps-in-3d)), a map that is not octahedral, equal-area or cosine-weighted (Common:398-429); the map and its inverse round-trip exactly for `P` from 2 to 64 (checked with a port of the code).
- No intervals: every ray runs to its first hit, up to 1e6 (Buffer B:65). A hit stores sun light through a shadow ray times albedo, a miss sky radiance at distance 1e6.
- Merge (Buffer B:3-110): each texel picks the four upper probes around its own screen position with bilinear weights. For each, it projects its direction into the upper tile and scans a 5×5 window of upper texels. Each upper hit point (upper probe position plus direction times stored distance) is re-expressed from the current probe and kept if it falls in the current texel's direction bin and is not hidden by the texel's own nearer hit within a visibility window. Kept samples are averaged per probe, weighted by a normal ramp (cosine 0.8 to 1) and a plane test (0.02) floored at 0.001, and combined by the bilinear weights. If the total weight passes 0.0005 the texel's radiance is replaced by the result while its distance stays its own: a replacement, not `near + near.a·far`.
- After a merge a texel pairs upper radiance with its own hit distance, and the next cascade down rebuilds a hit point from that pair, so position and radiance come from different rays (inference). The comments say scattering would beat the 5×5 gather but may be slower.
- The visibility window is 8 times the world size of half a tile at the probe's depth `d`, about `2^(n+3)·d/H_half`: 0.015·d at cascade 0 and 0.47·d at cascade 5 for 540 half-resolution rows. The code builds it with the full-resolution reciprocal on half-resolution coordinates, which halves it (Common:391-395, inference).
- Temporal: a cube-map pass reprojects each pixel's world hit point into the camera of two frames earlier and blends `(old·count + new)/(count + 1)` with the count capped at 15, a 16-frame window matching the 16-frame period of the probe jitter. History is rejected by normal (0.5) and plane (0.05) tests, with no colour clamp. The top bands read the previous frame's G-buffer and camera, so the displayed image is a frame old and no single frame is correct by itself (Cube A:88-127, Buffer B:48-56).
- The final pass shades half-resolution pixels with the cube's irradiance from the four nearest cascade 0 probes (the mean of their four 45° texels, with no cosine weighting and no `1/π`) plus direct sun, times albedo: one bounce; then an ACES fit and a 0.45 power.
- Read from the code: the probe jitter has no tile index, so every probe in a band moves together, unlike the comment's random placement; the tilted slab's face normals are rotated back by −0.9 rad instead of −1.08 rad, about 10° off; `info.n *= −dot(info.n, d)` scales the normal instead of flipping it; the merge gate (0.0005) sits below the weight floor (0.001), so any accepted sample replaces the radiance; the emissive branches need albedo above 1 and never run; Image binds Buffers B and D without reading them. The comments add that samples are not BRDF weighted, that visibility is naive, and ask whether stochastic probes can be dropped.

### scy3Dd: SPWI in one shader

codyjbennett's Shadertoy (2026-08-08): screen-space probes with world-space intervals, six cascades over two frames ([Shadertoys](../sources/2023_rc_shadertoys.md#scy3dd-codyjbennett-spwi-in-one-shader)).

| Cascade | Probe spacing (px) | Directions per probe | Interval (world units) |
|---|---|---|---|
| 0 | 4 | 16 | 0.006 to 0.030 |
| 1 | 8 | 64 | 0.030 to 0.102 |
| 2 | 16 | 256 | 0.102 to 0.390 |
| 3 | 32 | 1,024 | 0.390 to 1.542 |
| 4 | 64 | 4,096 | 1.542 to 6.150 |
| 5 | 128 | 16,384 | 6.150 to 24.582 |

- Intervals are `[s(N), s(N+1)]·0.006` with `s(0) = 1` and `s(N) = 4^N + 1`. Directions per axis equal the probe spacing in pixels, so a direction-major atlas exactly fills one resolution-sized texture per cascade, which holds only for the 4 px base spacing. Directions use the equal-area octahedral map at cell centres.
- The scene is an emissive unit cube coloured by its face normals above a floor, traced analytically. Each probe reads one depth at its cell centre; there is no G-buffer and no min/max. A non-emissive hit counts as a miss, so the floor neither blocks nor emits.
- Merge: Bilinear3D, from 4XXSWS, iterates four times for the ratio at which the four upper probes' world positions best interpolate the probe's own position. The bilinear fix then traces from `probe + dir·lo` to each upper probe's `upper + dir·hi`, averages that probe's four child directions with weights 0.25 each, and weights by the 3D ratio.
- Gather: the 16 cascade 0 directions, each read by a hardware-bilinear fetch at the 3D ratio and weighted by `max(0, n·dir)`, divided by the sum of cosines, plus a cascade −1 contact trace over `[0, 0.006]` per pixel. Output: albedo times radiance, exposure ×2, ACES fit, sRGB.
- Buffers A to C compute cascades 5/4/3 and 2/1/0 on alternate frames, both frames of a pair using one camera time, so the image refreshes every other frame.
- Comments name what is left out: min/max depth probes (which fix bilateral flicker but need binning or temporal data), discontinuity-aware interpolation, the parallax fix, holographic cascades, and split-sum specular from the interpolated intervals.
- Defects from the code: the G-buffer trace starts at the near-plane point but adds its distance to the camera origin, so reconstructed hits sit roughly `0.1/cos θ` too close to the camera; the gather's hardware-bilinear fetch clamps only the base probe, so the last probe column of a direction tile can blend in the next tile's first probe.

scy3Dd is the only screen-probe code that combines the bilinear fix with bilinear 3D weights, so its merge handles both the depth edge and the parallax between parent and child rays (inference); the [bilinear fix](artifacts_and_fixes.md#the-bilinear-fix) itself is in artifacts and fixes.

### 33ycDm: GTAO from cascaded horizons

youssef_afella's Shadertoy computes GTAO in one frame from cascaded horizons ([Shadertoys](../sources/2023_rc_shadertoys.md#33ycdm-youssef_afella-gtao-from-cascaded-horizons)):

- Three effective levels (a fourth buffer returns −1 and is never read). Level `n` has origins every `2^n` px and `4^(n+1)` directions, 45° apart at level 0, 22.5° at level 1 and 5.625° at level 2. Radial intervals are `[4^n − 1, 4^(n+1) − 1]·0.1/63` in UV, divided by `1 + depth`, with 2, 4 and 4 samples.
- Each direction keeps the maximum cosine to the view vector over its samples, minus twice a falloff starting at 0.1 view units. The merge takes `max(own, parent − w)`, where the parent is the bilinear mean of the four child horizons of block `4b + i` and `w = 2·clamp(|Δdepth|, 0, 1)`. The author notes the depth weight should be applied per probe, not to an average.
- The image pass turns level 0's four horizons into two GTAO slices along the diagonals, clamps them to the normal's hemisphere and evaluates GTAO's per-slice integral; a camera-facing open surface gives exactly 1.
- The author calls it noiseless and full of artifacts, still needing depth-aware merging and upsampling. Taking the maximum horizon per interval and across levels is the HBAO step; the result approximates GTAO with two slices, two to four samples per ray and averaged horizons ([related screen-space GI](related_screen_space_gi.md)).

The merge replaces RC's `near + β·far` with `max(own, parent)`, the horizon form of the same operator: a horizon blocks everything below it, so the larger horizon wins (inference).

## Design sketches

### CorylusDonuts: 2.5D pseudocode

https://github.com/CorylusDonuts/2.5-d-Radiance-Cascade-Pseudocode (MIT, 2024-08) is an incomplete design whose ray tracer is a stub, with one idea worth keeping for depth discontinuities ([X3XfRM notes](../sources/2024_mathis_x3xfrm_surface_probe_rc.md#corylusdonuts-25d-screen-space-rc-pseudocode)):

- A min/max depth mip chain, each texel storing the minimum and maximum depth of its 2×2 children with their pixel positions.
- Cascade `c` has probes every `2^c` pixels with octahedral full-sphere directions, `CASCADE_0_DIM << c` per side.
- Each probe stores two intervals, one cast from the minimum-depth surface and one from the maximum-depth surface of its mip texel, packed as half floats (RGB plus distance) in an RGBA32UI texel.
- The merge weights each of the four parent probes by `exp(−16·|d − d_n|/d)` times its bilinear weight, normalized, separately for the min and max intervals.
- Directions are cast four at a time per 2×2 lane cluster and averaged with `subgroupClusteredAdd(…, 4)·0.25`, a form of pre-averaging.

### tmpvar's storage calculator

Demo 5 of tmpvar's playground, "Screenspace probes with worldspace intervals (3D)", computes a storage table and renders nothing ([playground](../sources/2024_tmpvar_rc_playground.md#demo-5-screenspace-probes-with-worldspace-intervals-3d)).

| Control | Range | Default | Meaning |
|---|---|---|---|
| probe directions (world space) | 1 to 32 | 2 | the label shows `d²`, so 4 directions by default |
| probe spacing (screen space) | 0 to 10 | 2 | spacing `2^s` px, 4 px by default |
| keep merged and unmerged cascades | checkbox | on | doubles storage; for reflections on GGX or similar rough surfaces |
| place screen-space probes on min and max depth | checkbox | on | doubles storage; for thin objects and high depth complexity |

Its `Update` runs when values change and, for 1920×1080, 2560×1440, 3840×2160 and 7680×4320, computes the grid `ceil(W/spacing) × ceil(H/spacing)`, entries per level `cells × directions` (×2 for each checkbox), levels `ceil(log2(min(gx, gy)))` and total `levels × entries`, printed by a `NiceBytes` that divides by 1024 while the value is at least 1, rounds up and adds a unit. The header says "assuming 32bit vec4f(rgb, throughput)", but the formula has no 16-byte factor, so the printed numbers count entries, not bytes. Its open items are the cascade 0 calculation, the same for other cascades, and the two doublings, which the checkboxes already cover.

At the defaults, 1080p has 480 × 270 = 129,600 cells, 2,073,600 entries per level and 9 levels, 18,662,400 entries. At the stated 16 bytes per entry the totals are 285 MiB at 1080p, 506 MiB at 1440p, 1.24 GiB at 4K (10 levels) and 5.4 GiB at 8K (11 levels) (derived). The formula charges every level the cascade 0 entry count, which is exact when directions grow ×4 as spacing doubles (derived).

### Other

- bevy_ridiculous_ssgi (DGriffin91, "very experimental", deferred rendering only, WebGL2 capable) is a cascaded screen-space GI that never names RC. It marches the prepass depth, normal and colour mips from probes every 4 px (`render_scale`), with 16 directions at cascade 0 doubling per level over 6 cascades. Cascade `n` reaches `2^n·cascade_0_dist·√(n + 1)` with an optional overlap into the previous interval ([cascade layout](cascade_layout_and_merging.md#intervals)), and its step count is the interval length over half the probe spacing, divided by `√(2^n)` or by `2^n` (faster, with more leaking). Each probe merges a 2×2 block of the coarser cascade weighted by depth and normal rejection (2.0 and 100.0 by default). Probe positions and directions are jittered with a noise period of 8 frames, and the options include rough specular, backside illumination and horizon occlusion. It sees only what is on screen and has no bounce ([blog posts](../sources/2024_rc_blog_posts_and_slides.md#this-week-in-bevy)).
- Day's "Radiance Cascades SPWI Sponza Clip" (https://youtu.be/c3cQ64qbJqk, 2025-06-06, 89 s, no captions) is described as a quick demo of screen-space probes with world-space intervals; it does not mention min/max probes ([screen-space RC](../sources/2026_screen_space_rc.md#links)).

## Depth-aware upscaling shaders

Test shaders for reading low-resolution data at full-resolution pixels; the principles are in [3D screen space](3d_screen_space.md#depth-aware-upscaling) ([Shadertoys](../sources/2023_rc_shadertoys.md#depth-aware-upscaling-and-occlusion)).

### 4XXSWS: depth-aware upscaling

Suslik's test upscales a 1/8-resolution buffer of `(colour, depth)` to full resolution in four panels: plain bilinear, reference, bilateral and "bilinear 3D". three-rc ports it for screen-space probes.

- Bilateral: weight each of the four neighbours by `bilinear_i·exp(−100·|depth_i − depth|)` and normalize.
- Bilinear 3D: rebuild the four neighbours' world points `P_i` from their depths and the target point `Q`. Starting from the plain bilinear ratio, run two iterations that alternate solving `ratio.x` and `ratio.y` by projecting `Q` onto the line between the two edge points interpolated at the other ratio (`ProjectLinePerp(A, B, p) = dot(p − A, B − A)/dot(B − A, B − A)`, saturated). The final weights at that ratio sum to 1, so no normalization is needed, and they follow the surface instead of rejecting samples. scy3Dd and three-rc run four iterations.
- There is no guard against zero-length edges or a zero total bilateral weight.

### MXjcWK: selective bilinear subsets

Quadrants show hardware linear, reference, bilateral (`exp(−100·|Δd|)` as in 4XXSWS) and a selective method on an Apollonian fractal at 1/8 resolution. The selective method keeps the 2D bilinear ratio, tries the 15 non-empty subsets of the four taps with the bilinear weights masked to the subset and renormalized, and keeps the subset whose weighted world point lands closest to the full-resolution point. It chooses among discrete subsets rather than solving a continuous 3D ratio; comments describing continuous coefficients and Newton iterations do not match the code, and a variant blending subsets by inverse squared distance is never called.

### 4cffDX: normal- and depth-weighted upsampling

Coppen's four boxes shaded at one sample per 16×16 cell and upsampled with full-resolution depth and normals. Each tap's weight is its bilinear weight times `clamp(1.5·dot(N, N_i), 0, 1)`; when the spread of the four tap depths exceeds 20% of their mean, each weight is also multiplied by `1/(|d_i − d| + 10⁻⁴)`. Weights are normalized without a guard, so four taps facing away divide by zero. Depth is ray distance, not view depth.

### ffSSz1: linear min/max interpolation

"Basic Minmax Interpolation" (Suslik, 2026-04-15) forks NfSXRh ("Perspective interpolation tests") and is NfBSz1's parent; both call themselves deliberately simple and slow demos.

- For each 8×8 cell all 64 full-resolution samples are traced, and the cell stores the minimum and maximum depth with the red radiance at each (Buffer A:11-37). The image blends the four nearest cells bilinearly in all four channels, then outputs `mix(R_min, R_max, saturate((d − d_min)/(d_max − d_min)))` with the full-resolution depth `d` (Image:12-25); everything is linear, with no `1/d` step.
- The scene is an Apollonian fractal sphere traced for 128 steps, shaded by albedo times an orbit-trap AO times 0.9 with fog `exp(−0.1·t)`; depth is ray distance (Common:68-160).
- Shared with NfBSz1, read from the code: flat cells with `d_max = d_min` divide by zero; neighbour indices are not clamped at the border; a shadow ray and a normal are computed and never used; the camera uses 3.1315 where π is likely meant (Common:168).

### NfBSz1: perspective-correct min/max interpolation

- Cells are 8×8 px (a comment says 32×32). For each cell, 256 full-resolution samples around the centre give the minimum and maximum depth, and the cell stores `(dmin, dmax, xmin, xmax)`, `x` being the world x of the centre ray at those depths. A tent weight is computed and not applied.
- The image interpolates `1/d` bilinearly: `dmin' = Σw/Σ(w/dmin_i)` and `xmin' = Σ(w·xmin_i/dmin_i)/Σ(w/dmin_i)`, likewise for max. Then `t = clamp((d − dmin')/(dmax' − dmin'), 0, 1)` and the output mixes `xmin'` and `xmax'` by `t`. Nothing guards `dmax' = dmin'`.
- The test shows `fract(10·x)` of the interpolated world x against the full-resolution x when the mouse is held, so errors show as broken stripes. There is no error metric, and a ratio-first variant is not in the code.
- Against ffSSz1 it widens the window from 8×8 aligned samples to 16×16 centred ones, reaching 4 px into neighbouring cells, stores world x instead of radiance, and blends the endpoints in `1/d` while `t` stays linear in depth. Depth is ray length rather than view z, so the blend is perspective-correct only approximately (inference). Buffer A binds its own output, read only by an uncalled `mainImage_experimental`.

### l3scz8: occlusion from depth variance

A closed-form test for moment-based depth marching. With a fixed interval `I = [a, b]`, a sample interval of half-width `s` centred at `m`, and a uniform offset on `[−h, h]` with `h = √3·σ` (variance `σ²`), the probability that a point is covered is a trapezoid: `c = |s − h|`, `l = 2·min(s, h)`, height `H = min(1, s/h)`, `T(x) = H·clamp(1 − (|x − m| − c)/l, 0, 1)`. Its antiderivative gives the mean overlap `O = (F(b) − F(a))/(b − a)` exactly, which the shader checks against a 100-step brute-force sum. The offset is uniform, so only its variance enters, and a Gaussian with the same variance would differ. The comments target SSGI and SSAO from a prefiltered buffer of depth and depth squared; the Chebyshev bound the tags suggest is not in the code.

### pixelmager's depth-aware upscaling gist

| | |
|---|---|
| Author | GitHub user pixelmager; Gavras cites it as "Gjoel, M. (2021)", but the gist names no author and no public link ties the handle to Mikkel Gjøl |
| Date | created 2021-12-08 (GitHub gists API) |
| Kind | gist, Unity HLSL fragment code with comments, 121 lines |
| Link | https://gist.github.com/pixelmager/a4364ea18305ed5ca707d89ddc5f8743 |

The gist upscales half-resolution fog to full resolution without bleeding fog over foreground edges: a rotated four-point disc, a check whether the four samples agree in depth, and inverse depth-difference weights where they do not. Gavras's thesis uses it as the bilateral filter in its merge and final gather ([pixelmager](../sources/2021_pixelmager_depth_aware_upscaling.md)). It links the INSIDE rendering talk (loopit.dk/rendering_inside.pdf, page 39; on GDC Vault as "Low Complexity, High Fidelity - INSIDE Rendering", GDC 2016, Mikkel Gjøl and Mikkel Svendsen of Playdead), whose coverage of depth-aware upsampling is not confirmed, plus ProxyPG (ppsloan.org, page 5), Frostbite's stochastic SSR, the RDR2 slides, Playdead's TAA neighbourhood clipping and MBOIT.

- **Versions** in its comments: hardware bilinear (bleeds over foreground); manual bilinear with a depth test against a stored background depth, a proxy for the range each sample covers; and a four-sample random disc blur, because plain upscaling gives TAA's neighbourhood clamp only 4 distinct values, so it rejects history and stays noisy.
- **Input:** fog at half resolution in RGBA8; R holds the square root of the attenuation, squared on read ("saving squared"); GBA hold the texel's background depth as a 24-bit float in 3 bytes (`DecodeFloatFrom3PackedBytes`).
- **Samples:** offsets in half-resolution texels, `uv = 0.5·vpos`; `rnd` is a blue-noise texel at `(vpos + (1259, 1277)·t)/texsize`, `rnd.x` uniform and `rnd.gba` triangular; `φ = 2π·rnd.x`, `rot = 3.1·(cos φ, sin φ)` (`MAX_FILTERSIZ = 3.1`); radius factors `r_k = √(0.25·rnd.y + 0.25·k)` for `k = 0..3`, stratifying the disc by area, via `fastSqrtNR0` from ShaderFastLibs; offsets `r0·(rot.x, rot.y)`, `r1·(−rot.y, rot.x)`, `r2·(−rot.x, −rot.y)`, `r3·(rot.y, −rot.x)`, each rotated 90° from the last. The largest offset is 3.1 half-resolution texels, 6.2 full-resolution pixels.
- **Edge test and weights:** `spread = (max d − min d)/mean(d)` over the four decoded depths; the flag `spread < 0.1` is named `d_edge` but is true where there is no edge. Then the four samples are averaged and the full-resolution depth read is skipped; otherwise `bg = Linear01Depth(_CameraDepthTexture)`, `w_k = 1/(|d_k − bg| + 1e−5)` and the result is `Σ w_k·a_k/Σ w_k` with `a_k` the squared attenuation. No spatial kernel and no normal term; mismatched samples still contribute, only less.
- **Output:** `atten·fogLightColour + (2v − 1)/255` for each of the three blue-noise values `v`, an 8-bit TPDF dither per channel.
- **Errors in the listing** (read, not compiled): the no-edge branch assigns `0.25·a_0` where `a_0` is a float4 written to a float, which HLSL truncates to `.x`, returning a quarter of sample 0, not the mean; the `M_TAU` declaration ends with a comma and runs into the next declaration, a syntax error; the edge branch uses `fogatten` but declares `fogAtten`, and HLSL is case-sensitive, so it does not compile. It depends on Unity's `_CameraDepthTexture`, `Linear01Depth`, `DecodeFloatFrom3PackedBytes`, `_RealTime` and `_DitherTexUni_Size`.
- **Author's notes:** the background depth is only a proxy for a half-resolution sample's depth range, and a fade over that range might be more accurate; the weighting is soft; INSIDE applied fog as a uniform additive term, and storing both irradiance and optical depth is suggested, with order-independent transparency methods possibly applicable. No timings or hardware.

| Parameter | Value |
|---|---|
| Samples | 4 |
| Disc radius | 3.1 half-resolution texels |
| Edge threshold (relative depth spread) | 0.1 |
| Weight epsilon | 1e−5 |
| Area strata | 0.25 |
| Noise time offset | (1259, 1277) |
| Dither amplitude | 1/255 |

Gavras's merge and gather keep the gist's 10% relative-spread test and `1/(|Δd| + ε)` weights (with ε 0.0001 and a 5% threshold in the gather) but drop its disc, which existed to feed TAA; for single-frame RC the disc's purpose is gone and only its weighting carries over (inference).

## Connections

- **Lineages.** 4XXSWS's bilinear 3D spread to three-rc, scy3Dd, RC-SPWI, the Unreal plugin, Gavras and ClaikoCode's disabled path; pixelmager's gist to Gavras, while Coppen's 4cffDX uses the same relative-spread test at 20% with no stated source; l3scz8 to the Unity plugin's variance trapezoid; codyjbennett's code from three-rc (2026-02) to scy3Dd (2026-08), which adds the bilinear fix and cascade −1.
- **Code drifts from intent the same way everywhere.** three-rc's cascade count, KingTheFifth's unbounded alpha, ClaikoCode's quarter-strength lighting, Alpha-Renderer's `GI_BOOST` and lXByRh's unused emissive branches all produce plausible images, so normalization bugs survive; a white furnace or uniform-sky test would catch each of them ([artifacts and fixes](artifacts_and_fixes.md#debugging-routine)) (inference).
- **Hemisphere maps go with probes that sit on one surface.** Alpha-Renderer and lXByRh in screen space, and M3ycWt, X3XfRM and yhyu13 on voxel faces and charts, use hemispheres around the normal, while the SPWI codes keep full spheres so that parent and child bins match whatever their normals ([3D surface probes](3d_surface_probes.md)).
- **Little of it is plain compute.** Among the repositories Alpha-Renderer is the only screen-probe RC in GLSL compute; Kaméus's HLSL compute and BeansEngine's software variant depend on inline ray queries, which `RenderingDevice` lacks, and the rest are fragment passes, DXR ray generation or Metal kernels.

## Single-frame assessment

- three-rc, ClaikoCode, RC-SPWI, KingTheFifth, the Unreal plugin's screen mode and scy3Dd (apart from its two-frame split) compute every frame from scratch; Alpha-Renderer and lXByRh accumulate over frames; the Unity plugin's modes are single frame but unstable.
- The Unreal plugin's per-sector masks and the Unity plugin's moment-based occlusion are the two single-frame answers to thin-object leaks in a depth march; the SPWI codes rely on world rays instead.
- None of the screen-space codes has been measured for quality, and only Alpha-Renderer gives a timing (5.5 ms at 1080p on an RTX 3070, a README claim).

## Open questions

- Does bilinear 3D with the bilinear fix (scy3Dd) remove depth-edge leaks as well as min/max probes, at lower cost?
- Can the Unreal plugin's per-sector β be carried into SPWI, where rays are world segments rather than screen slices?
- How large is the error of NfBSz1's perspective-correct min/max interpolation on real G-buffers, against bilinear 3D and selective subsets?
