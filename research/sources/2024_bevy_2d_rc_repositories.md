# Bevy 2D RC repositories

Four 2D implementations in Rust and WGSL. None has temporal reuse, bounce light or published timings. They are useful for their layouts and for one sparse variant that skips empty screen areas.

| Repository | Bevy | License | Last commit | Notable for |
|---|---|---|---|---|
| https://github.com/nixonyh/bevy_radiance_cascades | 0.14 | none | 2024-08 | probe-first layout, JFA distance field, cascade count from interval sum |
| https://github.com/kornelski/bevy_flatland_radiance_cascades | 0.16 | CC0 | 2025-09 | volumetric march with transmittance, rays ×2 per cascade, interval stagger |
| https://github.com/Lommix/solis_2d | 0.15 | MIT/Apache | 2025-01 | direction-first layout with one hardware bilinear fetch per merge, normal maps |
| https://github.com/IceKontroI/sparse_rc_2d | 0.17-dev | MIT/Apache | 2025-09 | sparse cascades built as task lists in slab chains |

## nixonyh/bevy_radiance_cascades

- Pipeline: occluders drawn into an R16Uint mask, jump flood, R16Float distance field, cascades top-down in two ping-pong Rgba16Float textures at screen size, a probe-average mip, then a fullscreen add onto the HDR image.
- Probe-first: a cascade `c` probe is a `w×w` texel block with `w = 2^(c+1)`, one ray per texel, so every cascade has `W·H` rays. Intervals start at `i0·(4^c − 1)/3` with length `i0·4^c` (`i0 = 2`: `[0,2], [2,10], [10,42], …`).
- Cascade count `min(16, ceil(log4(1 + 3D/i0)))` with `D` the screen diagonal: the smallest count whose summed intervals reach `D` (6 at 1080p).
- Sphere tracing, at most 32 steps. Emitters are texels above 1.0; the hit returns `sign(c)·max(|c| − 1, 0)`, so negative "light" also works.
- Merge: rays that hit skip it. Others read 4 upper probes × 4 upper rays (16 reads), with bilinear weights 0.75/0.25 from probe parity, times 0.25. No ringing fix.
- Two bugs found by reading: the JFA's last step-1 pass never reaches the distance field (an off-by-one in ping-pong parity), and the probe-average mip divides by `2w` instead of `w²`, which is only right at the default `w = 2`.

## kornelski/bevy_flatland_radiance_cascades

- Branching factor 1 (rays per probe ×2, probe spacing ×2), 16 merged directions at cascade 0, probes 2 px apart, 6 cascades, intervals doubling (`[0,16], [16,32], [32,64], …`). The README calls the seam fix a "gear fix" without defining it.
- Direction-first storage in compute buffers, with pre-averaging of 2 raw rays per stored direction.
- A fixed-step volume march with `exp(−extinction·density·step)` per sample, so the alpha it returns is a transmittance, and the merge is `traced.rgb + traced.a·upper`. The march takes `min(L, (L + 10)/2)` samples per interval.
- Interval ends are staggered by about ±10% to hide cascade edges.
- **"Gear fix":** the README names it only once, as a workaround that reduces halos at cascade seams in place of the bilinear fix, and no code uses the word. The merge reads the four upper texels from index `(probe − 1)/2` and blends them with fixed weights: the lower neighbour gets 1/3 when the probe index is even and 2/3 when it is odd, per axis, under the comment "cascades are never perfectly aligned". Probes sit at `(i + 0.25)·s` on every level, so the geometric bilinear weights on the lower neighbour are 1/8 for even and 5/8 for odd indices (probe 2 at 2.25 s lies 7/8 of the way from upper probe 0 at 0.5 s to upper probe 1 at 2.5 s; derived, not stated in the source). The fixed weights are therefore a deliberate blur toward the lower neighbour, strongest on even probes, not an interpolation.
- A doc comment in `cascades.rs` still says "no pre-averaging yet" and "no bilinear fix", while the shader pre-averages. The README says the hardware-filtered fetch that direction-first storage allows is not implemented, which matches the manual four-texel fetch.

## Lommix/solis_2d

- Every pass is a fullscreen fragment pass: SDF, cascades in ping-pong, a probe-average mip, and a composite.
- Direction-first layout: cascade `c` is split into `2^c × 2^c` blocks, one per direction group, each the size of the probe grid. A texel holds four raw rays (`4^(c+1)` raw rays per probe), so pre-averaging is built in.
- Merge reads the upper cascade **once** with hardware bilinear filtering at `probe·0.5 + 0.25` inside the matching direction block, clamped half a texel from the block edge. This is the cheap merge that direction-first storage makes possible.
- Intervals `i0·(4^c − 1)/3` to `i0·4^c` with default `i0 = 6`, at most 16 sphere-tracing steps.
- Normal maps multiply by `N·L` at cascade 0, with the light at a configurable height.
- The composite adds `light / |sdf|` as an edge highlight with no guard against zero distance.

## IceKontroI/sparse_rc_2d

A test bed for sparse cascades meant for a later 3D version; the README calls 3D "a work in progress". Every pass is written from scratch on the author's own GPU wrapper inside Bevy's render graph. Three modes share the march and the merge: SparseFilled (the default, with cascade 0 probes at every non-solid texel and output identical to Dense), SparseEdge (cascade 0 probes only next to edges) and Dense. Slides accompany the repository.

- **Shared settings:** probes ×2 apart (`PROBE_SPACING = 2`, and the code warns that other values break it), rays ×4, the nearest-neighbour fix, pre-averaging, no interpolation and no bounce light. The cascade count is `min(32, ceil(log4(|dims|)))`, 6 at 1080p. Dense storage rounds `dims/2` up to a multiple of `2^N`, 960×576 at 1080p.
- **Layout:** level `c` has spacing `2^(c+1)` px and `4·4^c` rays. Storage is direction-first: a `2^c × 2^c` grid of direction blocks, one texel per probe and group of four raw rays. Pre-averaging is folded into the values, since a hit writes `rgb·0.25` and a merge adds `0.25·parent`. The parent texel is the same direction block at `coord/2`, with no interpolation.
- **Intervals:** start at `2·(4^c − 1)/3` (0, 2, 10, 42, 170 and 682 px) with length `2·4^c`. A code comment lists lengths one shorter (`2·4^c − 1`), which is stale.
- **March:** sphere tracing on an unsigned JFA distance field sampled at `round(pos)`, from `start + 0.5` along the ray to the parent ray's target. A hit is `d ≤ 0.5·√2`, and its color is the brightest of the 2×2 emissive texels around the sample. There is no step cap beyond the bounds checks.
- **Nearest-neighbour fix:** child rays aim at direction index 1.5 of the parent group, the center of the four parent rays they merge into (based on a GM Shaders shader). The forking fix (the Space key) uses 1.5 for all four rays of a task; the code says it "seems to introduce blind spots", so it is off by default.
- **Distance field:** a texel with nonzero alpha seeds itself, an 8-neighbour jump flood runs with jumps from 2048 down to 1 (12 passes at 1080p, the count rounded up to even), and the field is `distance(pos, seed)`. The slides put the jump flood at about 0.75 ms on an RTX 2080 Ti. It stays dense in every mode, as do the lighting texture and mouse drawing.
- **Sparse seeding:** each workgroup owns a `2^N`-texel tile (64×64 at 1080p, 30×17 workgroups) and walks its 4096 texels in Z-order, 256 at a time. A task is `texel/2`, so four consecutive Z-indices map to one probe. SparseEdge classifies 2×2 quads as empty, mixed or solid (a texel is solid when `ceil(alpha) = 1`) and places a probe when a diagonal quad is mixed or the diagonal quads include both empty and solid ones. A ray that misses adds its parent texel as a task for the next cascade. Siblings sit next to each other in Z-order, so comparing each entry with the three before it ("3-left") removes duplicates without a hash.
- **Slab chains:** tasks live in per-cascade linked lists of 256-entry slabs, with the head and length of 32 chains in workgroup memory. Slabs come two at a time from an atomic counter out of a pool of 64,000 allocated once: 8 B of task coordinates and 4 B of color per entry plus a 4 B next pointer per slab, about 197 MB. A color packs 8-bit RGB with a flag byte holding four per-direction hit bits and four "unique" bits. An exhausted pool counts the lost data and drops tasks, and a code comment says too few slabs cause flickering.
- **Merge:** runs top-down from the highest level reached (tracked with an `atomicMax` while casting) over the task lists. Each child finds its parent through a prefix-sum index and adds `0.25·parent` when its ray is unoccluded, and cascade 0 writes the lighting at half resolution.

Measurements from the slides, at 1080p on an RTX 2080 Ti, excluding the jump flood:

| Scene | Mode | Time (ms) | Rays | Merges | Memory (MB, as reported) |
|---|---|---|---|---|---|
| Star | Dense | 1.771 | 13,271,040 | 9,817,551 | 4.424 |
| Star | SparseFilled | 1.565 | 11,231,620 | 9,025,132 | 0.24 |
| Star | SparseEdge | 0.517 | 402,784 | 159,122 | 0.01 |
| Confetti | Dense | 4.889 | 13,271,040 | 6,767,372 | 4.424 |
| Confetti | SparseFilled | 2.104 | 8,280,660 | 5,579,062 | 0.18 |
| Confetti | SparseEdge | 1.214 | 1,603,804 | 614,808 | 0.07 |

- Dense's 13,271,040 rays equal 6 levels × 960×576 tasks × 4 rays. Dense has its statistics atomics disabled because contention added about 1.5 ms per frame, so the repository does not show where its counts come from.
- The sparse memory figure multiplies the slab count by 16 B, the size of one entry rather than of one 256-entry slab. Under the code's own layout a slab takes 3,076 B, 192 times more. Star SparseFilled's 0.24 MB then means about 15,000 slabs, which is about 46 MB at the real slab size, ten times the Dense figure of 4.42 MB for two RGBA8 textures of 960×576 (derived, not stated in the source). The time and ray savings stand; the reported memory saving does not.
- About 60% thread use in the confetti scene: a slab's length equals the workgroup size, so the last, partly filled slab of each chain idles threads, four times over because each direction walks the chain. A shader comment gives this as the reason 512 entries per slab were no faster than 256, and a constants comment says 256 beat both 128 and 512 in some scenes.
- 8-bit color storage limits dynamic range. Bevy's output is `Rgba8UnormSrgb`, so packing to `Rgba8Unorm` before display gives a visible color difference, listed as a TODO. Storing slabs in a texture would fix it but limit allocation sizes.
- Interpolation is "not straightforward" with this storage, and the slides say it would add parent tasks. A `select(2u, 2u, init)` in the slab allocator returns 2 in both branches.
- **Planned work:** sparse transmissive RC, with probes only on emissive voxels, rays culled below an emission threshold and no merge path, plus hash-bucketed writes against the resulting many-to-one write race; and an omnidirectional shadow map for sky light, called "highly experimental". For 3D, the slides say the cascade 0 seed order needs a precomputed chain or a sort, and that Z-order with direction-major iteration keeps the three-lookup dedupe without a hash table.
- The video linked from the repository (vHk4a7Nzw-c, 2025-11-29, 32 s, uploaded by Kael Eppcohen) is "Sparse Radiance Cascades in 3D". Its description calls it an initial showcase of a 3D sparse formulation, made sparse because 3D RC needs a lot of VRAM, and names SPWI as the alternative the author chose against. It has no captions and no further details.
