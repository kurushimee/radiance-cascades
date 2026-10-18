# Radiance cascades: core theory

Radiance cascades (RC) store a radiance field as a stack of probe grids. Each grid ("cascade") covers one distance band: near bands use dense probes with few directions, far bands use sparse probes with many directions. Merging the bands from the farthest down gives every probe of the densest grid the light from all distances, at a cost close to that of the densest grid alone. This note covers the shared theory; [artifacts_and_fixes.md](artifacts_and_fixes.md) covers what goes wrong, and [3d_world_space.md](3d_world_space.md) and [3d_screen_space.md](3d_screen_space.md) cover the 3D designs.

Main sources: [the paper](../sources/2023_sannikov_radiance_cascades_paper.md), [Osborne and Sannikov 2024](../sources/2024_osborne_radiance_cascades_radiative_transfer.md), [Coppen's fundamentals](../sources/2024_coppen_fundamentals_of_radiance_cascades.md), [GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md), [jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md), [the community site and wiki](../sources/2026_rc_community_site_and_wiki.md), [LegitCascades](../sources/2024_sannikov_legitcascades.md), [Shadertoys](../sources/2023_rc_shadertoys.md).

## Penumbra condition

Take the smallest light, of size `w`, at distance `d` from an occluder edge. The penumbra opens at angle `γ = 2·atan(w/2d)`. At distance `D` from the light it is `γ·D` wide, and the light covers an angle of about `w/D`. To resolve both:

```
Δp ≲ D        (probe spacing may grow linearly with distance)
Δω ≲ 1/D      (angle between rays must shrink with distance)
```

Near a surface, radiance changes fast in space and slowly in angle; far away, the reverse. The condition is about distance to the nearest object, not to lights: an occluder is a light that emits nothing. It breaks only for tiny lights very close to occluders, where `d ≈ D` and `Δω` must shrink faster than `1/D`. When resolution runs short, shadows blur as if the lights were larger, so quality degrades gracefully. RC cannot produce very sharp shadows; [HRC](../sources/2025_freeman_holographic_radiance_cascades.md) addresses that in 2D.

## Radiance intervals

`L[a,b](p, ω)` is the light reaching `p` from direction `ω` that comes only from distances `t ∈ [a, b]` along the ray. `β[a,b]` is the transmittance over that segment: 1 if nothing blocks it, 0 if something opaque does, or `exp(−τ)` in a volume. A probe texel stores RGB radiance plus `β` in alpha.

Adjacent intervals merge like front-to-back premultiplied alpha:

```glsl
vec4 merge_intervals(vec4 near, vec4 far) {
    return vec4(near.rgb + near.a * far.rgb, near.a * far.a);
}
```

In optical-depth form: `I = I_near + exp(−τ_near)·I_far`, `τ = τ_near + τ_far`. The order of merging does not matter, and front to back allows early exit once `β` reaches 0. Many 2D implementations skip the merge when a ray hit something, which is the same as `β = 0`.

Two identities matter for 3D grids:

- **Shift:** `L[a+x, b+x](p, ω) = L[a,b](p + x·ω, ω)`.
- **Extend:** `L[a, a+2x](p) = L[a, a+x](p) + β[a, a+x](p)·L[a, a+x](p + x·ω)`. A cascade can trace a short piece and double it by reading itself at shifted positions, each doubling costing O(1). This needs a regular grid, so it does not work for screen-space probes.

## Scaling laws

Probe spacing doubles per cascade. With a branching factor `α`:

```
Δp ∝ 2^i      Δω ∝ 1/2^(α·i)      interval start and length ∝ 2^(α·i)
```

The paper's minimum is `α = 1` (angle halves, intervals double). Almost every implementation uses `α = 2` in 2D: four times the directions and intervals four times as long per cascade, so every cascade holds the same number of texels and is simpler to lay out. Sannikov found this gave better quality per cost before knowing why; the Split RC paper later justified it for 3D (see [3d_world_space.md](3d_world_space.md)).

Memory per cascade by domain, for `α = 1`:

| Domain | Probes in cascade `i` | Directions per probe | Memory of cascade `i` | Total |
|---|---|---|---|---|
| 2D (flatland) | `∝ 1/4^i` | `∝ 2^i` | `M0/2^i` | `< 2·M0` |
| 3D grid | `∝ 1/8^i` | `∝ 4^i` | `M0/2^i` | `< 2·M0` |
| Surface (screen or surfels) | `∝ 1/4^i` | `∝ 4^i` | `M0` | `N·M0` |

For a full 3D grid, cascade 0 alone is usually too large; for surfaces, cascade 0 is cheap and each added cascade costs the same.

Cost of the two 2D choices (Osborne): with `α = 1`, the rays traced sum to under `2·N0` and the merge builds `2^I·N0` rays; with `α = 2`, every cascade traces `N0` rays, the total is `I·N0`, and the merge builds `4^I·N0` rays. Run time is not just ray count: upper cascades march longer intervals, and in DexRT the top two cascades took 85% of the time.

The [kornel.ski calculator](../sources/2024_rc_blog_posts_and_slides.md) sizes intervals from the exact condition instead of powers of 4. For a 1 px base spacing, 1 px lights, and a 90° penumbra, intervals only double and rays roughly double per cascade, at 37 M probe-rays for 1080p.

2D tests ([merging notes](../sources/2026_merging_and_ringing.md)) add practical rules. Write scaling as `spatial/angular`: `2x/4x` keeps cascades the same size, `2x/2x` halves them. `2x/3x` gave similar quality to 2x/4x with the bilinear fix at a fraction of the cost, and a third of its rays line up with the cascade below. 2× angular branching needs about 32 cascade 0 directions and 16 to 32 px first intervals. About `log4` of the screen diagonal cascades suffice with 4× scaling. Probe counts should drop at most by half per axis per cascade. In 3D, 4× interval scaling gave uniform error at the same cost with one fewer cascade than 2× ([sparse 3D notes](../sources/2026_sparse_and_3d_rc.md)). Holographic RC trades this structure for one-axis probe reduction; its rules are in the [HRC notes](../sources/2026_holographic_rc.md).

## Layout and index math (2D, `α = 2`)

Symbols: cascade `c`, base spacing `s0`, base interval `i0`, `B` stored directions in cascade 0 (often 4).

- Probe `k` of cascade `c` sits at `(k + 0.5)·s0·2^c`.
- Cascade `c` has `B·4^c` directions; direction `j` points at angle `2π(j + 0.5)/count`, the bin center. Upper directions `4j … 4j+3` subdivide lower direction `j`.
- Contiguous intervals: start `i0·(4^c − 1)/3`, length `i0·4^c`. Variants start cascade 0 at 0 and the rest at `i0·4^(c−1)`, or add an overlap (below).
- Cascade count: enough that the top interval passes the screen diagonal, `ceil(log4(diagonal))` with a 1 px base interval, or `ceil(log4(1 + 3·diagonal/i0))` in general. jason.today adds one more cascade so a corner light reaches the far corner.
- Choose `i0` near half to one times the cascade 0 probe diagonal. A longer `i0` leaves gaps between cascade segments; shorter costs more cascades.

### Storage

- **Position-first:** each probe is a tile of direction texels. Simple, but a merge needs 16 fetches per ray (4 directions × 4 probes).
- **Direction-first:** each direction is a tile holding that direction for every probe. Neighbor probes of one direction sit side by side, so one hardware bilinear fetch blends four upper probes. It is also easier to debug.
- **Pre-averaging:** each stored texel is the mean of the 4 rays it will be merged into below. Cast 4 rays per texel, store one value. Memory and merge fetches drop by 75%. Combined with direction-first, a full 2D RC fits in one shader of under 100 lines (GM Shaders part two).

With direction-first and pre-averaging, the merge for lower ray `k` at probe `p` is one fetch in upper direction tile `k` at `p/2 + 0.25` (in upper texel units), clamped at least half a texel inside the tile so the filter never reads a neighboring direction. The `+0.25` gives the 0.25/0.75 bilinear weights of a probe that sits between upper probes.

## Merge and gather

1. Trace every cascade's intervals; all cascades can trace in parallel.
2. Merge from the top cascade down. For each lower texel and each of its rays: blend the four nearest upper probes bilinearly (eight trilinearly in a 3D grid), average the upper directions that subdivide the ray, and merge behind the lower interval. Each step needs the cascade above finished, so this is `N` dependent passes.
3. Cascade 0 now holds full radiance averaged over each of its direction cones. For each pixel, blend the nearest cascade 0 probes and sum over directions. In 2D this gives fluence (`2π × mean radiance`); on surfaces in 3D, weight directions by the cosine to the normal.

**Cascade −1.** Trace `[0, i0]` per pixel for each cascade 0 direction and merge it in front of the interpolated cascade 0 value. This restores contact detail finer than the cascade 0 grid (Suslik's testbed and LegitCascades).

**Single frame or temporal.** Shadertoy and LegitScript versions merge each cascade with last frame's upper cascade in one pass, so changes take `N` frames to reach cascade 0. A separate pass per cascade gives a single-frame, noise-free result.

**Bounces.** Feed last frame's result back as emission at hit points (one bounce per frame). Without that, RC gives one bounce.

**Sky.** At the top cascade, a ray that misses adds the sky integrated over its angle bin, not sampled at the bin center, which avoids aliasing a small sun. fad's 2D formula for bin `(a0, a1)`: sky `(a1 − a0 − 0.5(cos a1 − cos a0))·skyColor` plus sun `(atan(8(S − a0)) − atan(8(S − a1)))/8·sunColor`, divided by the bin width. Sky light needs no spatial detail, so the coarse top cascade suffices, and occlusion is unchanged.

**Specular.** A glossy lobe is a cone query: query cascades `0..K` separately in the reflected direction, merge them, and read the merged cascade `K+1` for the rest. The narrowest cone uses every cascade's own angular step.

**Color.** Accumulate in linear space. Decode sRGB scene colors before tracing; jason.today notes that doing so made ringing more visible.

## Interpolation and band-limiting

Because each cascade meets the penumbra condition for its distance band, its data is band-limited. Plain bilinear interpolation in space and direction reconstructs it, with no bilateral weights or disocclusion handling. Classic probes need those because they store full radiance. This holds only in a regular grid; screen-space probes at different depths still need depth-aware interpolation (see [3d_screen_space.md](3d_screen_space.md)).

## Worked 2D defaults

| Source | Base spacing | Cascade 0 rays | Ratio | Base interval | Cascades at 512² |
|---|---|---|---|---|---|
| radiance-cascades.com demo | 1 px | 4 | ×4 rays, ×2 spacing | 1, overlap 0.1 | 6 |
| jason.today | 1 px | 4 | ×4 | 2 px, overlap 0.04 | 6 |
| GM Shaders (optimized) | 1 px | 4 (1 stored) | ×4 | 2 px | 6 at 1080p |
| fad Shadertoy | about 2.4 px | 16 | ×4 | `4·|res|/1023` | 5 |
| LegitCascades | 256-wide grid | 4 | ×4 | 10 px | 3 |

The jason.today table at 512²: intervals `[0.25, 2]`, `[2, 9]`, `[8, 36]`, `[32, 143]`, `[128, 570]`, `[512, 2280]` px, each cascade casting about 1 M rays, 6.3 M per frame.
