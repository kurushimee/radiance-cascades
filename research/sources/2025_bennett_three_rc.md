# three-rc: screen-space probe radiance cascades in three.js

| | |
|---|---|
| Author | Cody Bennett (GitHub: CodyJasonBennett) |
| Date | 2026-02-09 (last commit) |
| Kind | repository |
| Link | https://github.com/CodyJasonBennett/three-rc |

Three.js implementation of radiance cascades global illumination for 3D scenes, written as one module (src/index.js) with inline GLSL. Screen-space probes trace rays against a world-space BVH built once at startup, the cascade results are stored in screen-sized float textures, and a composite pass shades the G-buffer from the level-0 result. In this code only emitter radiance enters the cascades, and the repository has no license because the README says the upscaler credited to Sannikov cannot be licensed.

## Architecture

1. Scene load. The Sponza glTF is loaded with a Draco decoder from gstatic (version 1.5.5). A 1x1x1 box at (0, 0.5, 0) is added with a MeshStandardMaterial whose emissive color is white and whose emissiveIntensity is 10.
2. Static geometry. Each visible mesh is cloned, given a per-vertex `id` attribute equal to its index in the mesh list, transformed to world space, and merged into one indexed geometry. Geometry is not updated after startup.
3. BVH. One `MeshBVH` is built over the merged geometry with `maxLeafTris: 1`, SAH split, and `indirect: true`. three-mesh-bvh dereferences the index texture into BVH leaf order, so a hit triangle's first vertex index is a real vertex index.
4. Emitter table. One RGB float texel per mesh holds the material emissive color times emissiveIntensity. The table is a one-row texture with nearest sampling. Non-emissive meshes store (0, 0, 0).
5. Mesh id lookup. A UInt vertex texture holds the merged `id` attribute. A hit's first vertex index selects the mesh id, which then selects the emitter texel.
6. Probes. Probes are placed on a screen-space grid of tile centers. Each probe reads depth from the G-buffer and reconstructs its world position. Probes are not placed in 3D.
7. Depth mode. The renderer is created with `reversedDepthBuffer: true`. In three r181 this takes effect only when the `EXT_clip_control` extension is available. Otherwise the renderer uses normal depth and the `USE_REVERSED_DEPTH_BUFFER` define is not set, so the shaders follow the active mode.

## Passes

W x H is the drawing buffer size. The device pixel ratio is clamped to [1, 1.25], and the canvas size is the window size times that ratio. Cascade and G-buffer targets are resized in `onresize`, which runs at startup and on every resize.

Per frame, in this order:

### 1. G-buffer (scene render)

Target: `gBufferTarget`, W x H, two color outputs and one depth texture.

- Output 0: RGBA16F (HalfFloat). Non-emissive pixels store `diffuseColor.rgb` with alpha 1. Emissive pixels store `totalEmissiveRadiance` with alpha 0.
- Output 1: RGBA8. Non-emissive pixels store octEncode of the view-space normal in r and g, metalness in b, roughness in a. Emissive pixels store zeros.
- Depth: `DepthTexture` with FloatType, W x H. Background pixels keep the cleared depth, which is 0 under reversed depth.

### 2. Cascade passes, level L = N-1 down to 0

N is `NUM_CASCADES` (see the cascade count section below). Each pass draws a full-screen triangle generated from `gl_VertexID`, with no vertex buffer. The output goes to one of two ping-pong targets, `cascadeTargets[0]` or `[1]`. Each target is W x H, with an RGB texture of FloatType and internal format R11F_G11F_B10F. The targets also have the default depth attachment, which is never sampled.

Uniforms for every cascade pass:

| Uniform | Value |
|---|---|
| `resolution` | W, H |
| `intervalLength` | 0.005 |
| `probeSpacing` | 4 |
| `cascadeLevel` | L |
| `numCascades` | N |
| `cascadeTexture` | Output of the previous pass (unused by the top pass) |
| `depthTexture` | G-buffer depth |
| `bvh` | BVH uniform struct |
| `idAttribute` | Merged `id` attribute as a UInt texture |
| `emissiveTexture` | Emitter table |
| `viewMatrixInverse` | `camera.matrixWorld` |
| `projectionMatrix` | Set automatically by three |

Each pass writes one radiance value per texel. Texels map to probe-direction pairs as described in the math section.

The ping-pong works as follows. Each iteration calls `cascadeTargets.reverse()`, so the read target is the last written texture and the write target is the other one. After the loop, `cascadeTargets[1]` holds level 0.

### 3. Composite (canvas)

Target: the canvas (`setRenderTarget(null)`).

Uniforms: `resolution`, `probeSpacing` (4), `cascadeTexture` (level 0), `albedoTexture` (G-buffer output 0), `normalTexture` (G-buffer output 1), `depthTexture`, and `viewMatrixInverse`.

The composite writes the shaded color, then three's tone mapping (ACES Filmic, set on the renderer), sRGB conversion, and dithering. Background pixels are discarded.

## RC parameters and math

### Notation

- T_L is the probe spacing at level L, equal to 4 * 2^L. It is both the tile size in pixels and the number of direction bins per axis.
- G_L is the probe grid, equal to (ceil(W / T_L), ceil(H / T_L)).
- D_L is the number of directions per probe, equal to T_L^2 = 16 * 4^L.
- Each level stores about W * H texels, so the storage is fixed per level.

### Cascade table

Ranges are in world units of the glTF scene. "Range end per getIntervalRange" is the second value that `getIntervalRange` returns. The traced end is the start plus that value, as explained under Tracing.

| Level L | T_L | Directions per probe | Traced range (start to end) | Range end per getIntervalRange |
|---|---|---|---|---|
| 0 | 4 | 16 | 0 to 0.02 | 0.02 |
| 1 | 8 | 64 | 0.02 to 0.10 | 0.08 |
| 2 | 16 | 256 | 0.08 to 0.40 | 0.32 |
| 3 | 32 | 1024 | 0.32 to 1.60 | 1.28 |
| 4 | 64 | 4096 | 1.28 to 6.40 | 5.12 |
| 5 | 128 | 16384 | 5.12 to 25.60 | 20.48 |
| 6 | 256 | 65536 | 20.48 to 102.40 | 81.92 |
| 7 | 512 | 262144 | 81.92 to 409.60 | 327.68 |

Interval start is `intervalLength * scale(L)`, where `scale(0) = 0` and `scale(L) = 4^L` for L >= 1. The second value of `getIntervalRange` is `intervalLength * scale(L+1)`. Level 0 therefore starts at 0, not at the base length.

### Probe placement

- Probe q at level L sits at UV `(q + 0.5) / G_L`, the center of its T_L x T_L screen tile.
- Depth is read with `textureLod` at LOD L. The depth texture has NearestFilter and no mip chain, so the LOD does not change the sample. The sample is the nearest full-resolution texel.
- Linearization: if the depth mode is standard, the raw depth z is first mapped to z * 2 - 1. Then `viewZ = -P32 / (P22 + z)`.
- For the reversed projection that three r181 builds (P22 = near / (far - near), P32 = far * near / (far - near)), z = 1 gives viewZ = -near and z = 0 gives viewZ = -far.
- View position: x = -(1 / P00) * (2u.x - 1) * viewZ, y = -(1 / P11) * (2u.y - 1) * viewZ, z = viewZ.
- World position: `(viewMatrixInverse * vec4(0.98 * viewPos, 1)).xyz`. The factor 0.98 moves the point 2% toward the camera. Probes and the composite's surface point use the same function.

### Directions and octahedral mapping

- Direction bin d = (d.x, d.y), with 0 <= d < T_L. Its UV is `(d + 0.5) / T_L`.
- The direction vector is `octDecode(UV)` in world space.
- octDecode: f = 2 * UV - 1, n = (f.x, f.y, 1 - |f.x| - |f.y|). If n.z < 0, then n.xy = (1 - |n.y|, 1 - |n.x|) * signNotZero(n.xy). The result is normalized.
- The composite uses the same mapping with T = 4 for the level-0 directions.

### Texel layout

- A texel at pixel p holds probe q = p mod G_L and direction d = p div G_L (component-wise integer division).
- Equivalently, the texel for (q, d) is at `d * G_L + q`.
- Each pass traces one ray per texel, so each cascade traces about W * H rays per frame.

### Tracing

- Ray origin is the probe's world position. Direction is `octDecode` of the bin UV. The interval is [start, start + length] from `getIntervalRange`.
- The shader moves the ray origin to `start`, then accepts triangle hits with distance `t` below `length`, measured from the moved origin. The traced range is therefore [start, start + length].
- The triangle test from three-mesh-bvh accepts `t >= -1e-5` and counts both faces. Hits up to 1e-5 behind the moved origin are accepted.
- Closest hit: radiance is the hit mesh's emitter texel. Non-emitting meshes give 0. No merge happens after a hit, even on a non-emitter.
- Miss at the top level: radiance is `getEnvColor`, which returns vec3(0).
- Miss at other levels: radiance is the merge from level L+1.

### Merge (level L+1 to level L, on a miss)

For a lower probe at world position x, direction index d:

1. Upper coordinate c = (q + 0.5) / G_L * G_{L+1} - 0.5, applied per component. Base b = floor(c). Fraction f = fract(c).
2. Upper corners q_k = clamp(b + o_k, 0, G_{L+1} - 1), with offsets o_0..o_3 = (0,0), (1,0), (0,1), (1,1).
3. Corner world positions P_k come from depth at the upper corner centers (level L+1), reconstructed as for probes.
4. Ratio solve, with r initialized to f and four iterations:
   - r.x = proj(x; A, B), where A = mix(P_0, P_2, r.y) and B = mix(P_1, P_3, r.y).
   - r.y = proj(x; C, D), where C = mix(P_0, P_1, r.x) and D = mix(P_2, P_3, r.x).
   - proj(p; a, b) = saturate(dot(p - a, b - a) / dot(b - a, b - a)).
5. Corner weights from r: w_0 = (1 - r.x)(1 - r.y), w_1 = r.x (1 - r.y), w_2 = (1 - r.x) r.y, w_3 = r.x r.y.
6. Direction bins: u_j = 2d + o_j for j = 0..3, each with weight 1/4. The fraction of the lower direction coordinate is always 0.5, so these weights are fixed.
7. Result: R_L(x, d) = sum over k and j of w_k * 1/4 * R_{L+1}(q_k, u_j), where R_{L+1}(q, u) is the texel at `u * G_{L+1} + q`.

### Final gather (composite)

- Pixel UV v. Level-0 grid G_0 = ceil(W / 4). Coordinate c = v * G_0 - 0.5, base b = floor(c), fraction f = fract(c), weights w_k from the 2D bilinear formula on f.
- For each corner k, q_k = clamp(b + o_k, 0, G_0 - 1).
- For each of the 16 directions d, the direction is `octDecode((d + 0.5) / 4)`, with bin coordinates dx = d mod 4 and dy = d div 4. The sample S is C_0(q_k, d), the texel at `d * G_0 + q_k`. For emissive pixels S is the pixel's own albedo.
- Output: sum over k and d of w_k * f_BRDF(V, N, dir) * S. There is no 1/16 or 4*pi/16 weight.
- V is the unit vector from the surface point to the camera position `viewMatrixInverse[3].xyz`. N is the world-space normal.

### Cascade count

The code is `NUM_CASCADES = Math.ceil(Math.log(Math.max(W, H), 4))`. JavaScript's `Math.log` takes one argument, so the base 4 is ignored and the value is ceil(ln(max(W, H))).

| Size | Code result | ceil(log4(max)) |
|---|---|---|
| 1024 x 768 | 7 | 5 |
| 1280 x 720 | 8 | 6 |
| 1920 x 1080 | 8 | 6 |
| 2560 x 1440 | 8 | 6 |
| 3840 x 2160 | 9 | 6 |

## Upscaler

- The README credits the upscaler to Alexander Sannikov (Shadertoy 4XXSWS) and calls it depth-aware interpolation.
- The only depth-aware weighting in the code is the 3D ratio solve (`getBilinear3dRatioIter`). It is used in the merge from level L+1 to L.
- The `projectLinePerpendicular` helper has a comment that links to the same Shadertoy ID.
- The final gather in the composite uses fixed 2D bilinear weights over the four nearest level-0 probes. It has no depth or normal weights.
- In the composite, the BRDF is evaluated per pixel for each of the four probes, and the four results are blended with the bilinear weights.
- The composite has a TODO for screen-space C-1 tracing. There is no Hi-Z or min/max depth.

## Issues and notes

- Cascade count. The `Math.log` call ignores its base argument, so the count is ceil(ln(max(W, H))). The table above lists the values. Each extra level adds one full-screen pass. At 1920 x 1080 the top level starts at 81.92 world units.
- Interval overlap. The traced range is [start, start + length]. `getIntervalRange` describes contiguous intervals, so the traced ranges overlap. For L >= 1, level L traces up to 5 times its start, and level L+1 starts at 4 times that start. The comment on the traversal function says "Min is ignored", but the code does apply the start by moving the origin.
- Non-divisible sizes. When W or H is not a multiple of T_L, the texel index `d * G + q` can reach W or H or beyond. The merge reads those texels without a bounds check. Example: at 1920 x 1080, the merge into level 4 reads level 5 (T = 128, G_y = 9). Row 127 * 9 + 8 = 1151 is outside the 1080-row texture. GLSL leaves an out-of-range `texelFetch` undefined. This was not run.
- Degenerate ratio solve. If the two corners of a pair are clamped to the same probe, the projection divides by zero, because the segment length is 0. The outermost lower probes can hit this case. For example, with an exact 2:1 grid ratio, the first probe column gives c = -0.25 and corner clamping makes corners 0 and 1 equal. The GLSL result of 0/0 is undefined. This was not run.
- Only emitters carry light. A hit on a non-emitter stores 0 and stops the ray. Light bounced off non-emissive surfaces is not stored in any cascade, so the code does not model bounce from those surfaces.
- Emissive pixels. The composite uses the emitted radiance as the BRDF albedo and also as the sampled color. The emitted radiance is not written to the output.
- Normalization. The composite sums 16 directional terms with weight 1. For equal-solid-angle bins (4*pi/16 each), the sum is 4/pi (about 1.27) times the sphere integral.
- Background probes. A probe on the background has depth 0, which linearizes to viewZ = -far (2000). Its world position is at 0.98 * 2000 from the camera along its view ray. No special case exists.
- Static scene. The BVH and the emitter table are built once. There is no update path for moved meshes.
- Emissive maps. Tracing uses the constant emissive color times intensity. The G-buffer uses `totalEmissiveRadiance`, which can include an emissive map. The two can disagree for textured emitters. The emissive decision uses the constant color only.
- Probe spacing. The composite hard-codes level 0 with `probeSpacing` 4. It must match `PROBE_SPACING`.
- Code TODOs. The file contains these TODOs: geometry clone "won't scale well"; add IOR and anisotropy; pack IOR/anisotropy into the G-buffer; use Hi-Z min/max; screen-space C-1 tracing; "seems broken on a complex scene like Bistro"; three should accept Float16Array.
- README notes. Probe storage is fixed cost in a screen-size texture, with no temporal accumulation. The README describes a Tiny Glade screen-space raymarcher variant that is not in this code. That variant no longer models off-screen occluders or emitters.
- README future work. A TLAS and material lookup for complex scenes. The README says Bistro does not look up emissive triangles in the correct order. A screen-space gather for contact effects, and upscaling of about 16x. Prefiltering and min/max probes.
- License. GitHub reports no license. The README ends with "All rights reserved." and says the license was omitted because the upscaler cannot be licensed.

## Links found

- README reference 1, Radiance Cascades paper: https://drive.google.com/file/d/1L6v1_7HY2X-LV3Ofb6oyTIxgEaP4LOI6/view
- README reference 2, three-mesh-bvh: https://github.com/gkjohnson/three-mesh-bvh
- README reference 3, Shadertoy upscaler: https://shadertoy.com/view/4XXSWS
- README reference 4, Tiny Glade raymarcher: https://twitter.com/h3r2tic/status/1652056116908490760. Tomasz Stachowiak's 2023 post shares a depth-buffer ray marcher for contact shadows and GI experiments (https://gist.github.com/h3r2tic/9c8356bdaefbe80b1a22ae0aaee192db), which also does SSR. Stachowiak tried DDA first but needed so much bias against acne and false hits that contact shadows were lost, and larger steps made it worse; the marcher was faster at similar quality. A later fix to its secant refinement stopped SSR leaking when rays approached overhangs from below. The experiments did not ship in Tiny Glade.
- JSFiddle demo: https://jsfiddle.net/ezsyu6dg/ (show page: https://jsfiddle.net/ezsyu6dg/show). The fiddle ("Radiance Cascades 3D - three.js", 843 lines of JS) is a compact form of the library: Sponza from a third-party host, three-mesh-bvh with one triangle per leaf and SAH, reversed depth, FOV 95, pixel ratio capped at 1.25, `BASE_INTERVAL_LENGTH = 0.005` and `PROBE_SPACING = 4`. Cascade `c` uses `4·2^c` px tiles, `2^(c+2)` octahedral rays per axis (`16·4^c` per probe) over the full sphere and world intervals `0.005·[4^c, 4^(c+1)]` (cascade 0 [0, 0.02]); probes sit at the depth of mip `c`; a BVH hit returns its colour, the last cascade returns the sky, and other rays merge with four direction taps and depth-aware 3D bilinear weights over four upper probes, solved in four iterations; the composite shades every direction of the four nearest probes with Burley diffuse and Schlick Fresnel. It has the same `Math.log` cascade-count bug as the library.
- Code comments: https://github.com/gkjohnson/three-mesh-bvh/blob/master/src/gpu/glsl/bvh_ray_functions.glsl.js (ray functions; the file now lives in `src/webgl/glsl/`, with 32-byte nodes whose bounds take two RGBA32F texels and contents an RG32UI texel, defaults of center split, depth 40 and 10 triangles per leaf, and a stack-based closest-hit traversal that visits the near child by the ray's sign on the split axis; the stack holds 60 entries, its comment calls that twice the deepest tree although a pop-one-push-two walk grows by about one entry per level, and the WebGL version has no overflow check while the WebGPU one does), https://jcgt.org/published/0003/02/01/paper.pdf (octahedral mapping), https://twitter.com/SebAaltonen/status/1772577195338113454 (depth linearization: with near `n`, far `f` and NDC depth `z`, `z_lin = 2n / (n + f − z(f − n)) = 1 / (z·A + B)` with `A = −(f − n)/2n` and `B = (f + n)/2n` precomputed per frame, one reciprocal and one multiply-add per pixel; A and B are entries of the projection matrix), https://unrealengine.com/en-US/blog/physically-based-shading-on-mobile (F_AB)
- Repository: https://github.com/CodyJasonBennett/three-rc
