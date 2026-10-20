# Cascades

Cascade 0 is a hemisphere probe on every atlas texel. Cascades 1 and up are sphere probes on world-locked grids, created only near the texels that read them. Every hit record against static geometry is traced once at load. A frame only re-shades the records and merges the cascades from the top down. Each choice below was measured in the lab ([experiments.md](experiments.md)), with the papers' theory behind it.

## Contents

- [Layout](#layout)
- [Directions](#directions)
- [Which probes and bins exist](#which-probes-and-bins-exist)
- [Merges](#merges)
- [A pass](#a-pass)
- [Checks in the engine](#checks-in-the-engine)
- [Open questions](#open-questions)

## Layout

| Cascade | Probes | Spacing | Directions | Interval |
|---|---|---|---|---|
| 0 | atlas texels | `s` | 16 hemisphere bins | `[0, t0]` |
| `k ≥ 1` | world grid, near surfaces | `2^k · s` | `32 · 4^k` sphere bins | `[t0 · 4^(k−1), t0 · 4^k]` |
| top | world grid | `2^K · s` | `32 · 4^K` | `[t0 · 4^(K−1), ∞)` |

- **`t0 = sqrt(2 · bins / 4π) · s = 1.60 s`** at 16 bins: the equal-error interval, at which the angular footprint at a ray's end matches the probe spacing ([paper 1, parameter rules](../papers/01_error_model/paper.md); in 3D, `sqrt(N0 / 4π)` spacings for `N0` sphere directions, [paper 2](../papers/02_merging_3d/paper.md)). In 3D it was the best interval at 16 bins: halving it raised every error and opened leaks, doubling it raised the error too (E3).
- **`K`**, the number of world cascades, is the smallest that puts the top cascade's start inside the scene's diameter: `ceil(log4(D / t0))`, 4 for a scene 45 m across at 0.3 m texels ([budget.md](budget.md#texel-spacing)).
- **Why world probes above cascade 0.** On an atlas, an upper probe's parents are undefined across chart borders, on curved charts and on charts narrower than the spacing, and tiny charts stop the probe count from falling per cascade. World parents are always defined. In the lab, where every chart is large, flat and axis-aligned, chart lattices kept fewer records at a similar error (E1); real unwraps break exactly those conditions, so world probes stay. Chart lattices remain the fallback for large planar charts if M3 finds world probes too costly.
- **16 bins, not 36.** At 36 bins the error in single rooms falls by a third to a half, for 2.1 to 2.2 times the records per texel (E3), which at a fixed budget means texels 1.5 times as far apart. The lab cannot weigh finer directions against finer texels, because its texels are fixed to the voxels; plan 004 M3 compares both at equal cost on the test scenes.

## Directions

- **Cascade 0** splits the hemisphere around the texel's normal into 8 azimuth sectors by 2 bands of equal height in `cos θ`, so every bin has the same solid angle; the sectors are turned by 0.3 rad. The tangent axis comes from the normal alone, by a fixed orthonormal-basis formula, so neighbouring texels and both sides of a seam get the same frame.
- **World cascades** use an equal-area cylindrical map of `2m × m` bins, `m = 4 · 2^k`, turned by a fixed generic rotation so that no bin lines up with the scene's axes. Lined up with the axes, vanilla's error at 32 directions and 1.19 times the equal-error interval rose from 16.5% to 25.0% in the voxel lab ([paper 2, the cascade 0 interval and overlap](../papers/02_merging_3d/paper.md)). Each bin splits into its 2×2 children in the next cascade.
- **A cascade 0 bin reads its four sub-directions** (its children in a hemisphere twice as fine), each bilinearly from four bins of a cascade 1 probe. Reading only the nearest bin saves 20% of records but makes the second bounce about 25% worse (E2).

## Which probes and bins exist

- **Insertion at load, bottom-up.** Every texel inserts its front parents in cascade 1: the trilinear corners around its probe that lie in front of its tangent plane. Every cascade 1 bin that a texel reads inserts the parents and bins its own merge reads in cascade 2, and so on to the top.
- **Only needed bins are traced and stored.** A sphere probe near a wall is read only from the wall's side, so most of its bins are never needed. In the lab, world cascade 1 needed 20 to 35 bin records per texel and the top 44 to 109 (E2).
- **Hash grids.** Each cascade keeps an open-addressing table from cell coordinate to probe slot, with 32-bit keys of 10 bits per axis and linear probing at a load of at most one half ([research](../research/sources/2026_gpu_hash_tables_and_sorting.md)). Hashing happens only at load: every probe stores the slots of its parents, and a prefix sum over the needed-bin masks gives each probe-bin its index. A frame does no lookups.
- **Determinism.** Insertion order cannot change the result, because the set of probes and bins depends only on the texels, and each value is computed by one thread in a fixed order.

## Merges

Each hand-over has its own merge, chosen in E2 by the error after five bounces with exact direct light, the leak into a sealed box and the furnace deficit. The deficit matters most: it compounds over bounces like a loss of albedo, while the merges' other errors do not ([paper 3, furnace exactness and the leak deficit](../papers/03_bounces_one_frame/paper.md)).

- **Texel to cascade 1: the trilinear fix on front parents.** For each bin and each front parent, a bent segment runs from the probe to the parent's interval start along the bin's direction ([paper 2, bent rays](../papers/02_merging_3d/paper.md)). A hit returns the hit's radiance; a miss reads the parent. The weights of the parents behind the tangent plane are dropped and the rest renormalized: with all eight, the first bounce came out 10 to 20% dark, because a parent behind the wall sees the wall's back (E1). The hand-over must be bent to seal: with the self test here, the sealed box leaked 0.006 even with every world hand-over sealed (E2). The Kuhn fix fails here with front parents, at first-bounce errors of 0.87 to 1.04 (E1).
- **World hand-overs: the sphere fix.** The lower probe's straight ray continues until it leaves the sphere of radius `t_c` around each parent, where that parent's interval starts, and reads the parent toward the exit point ([paper 2, bent rays](../papers/02_merging_3d/paper.md)). One record per probe-bin holds the hit and a flag per parent for whether the hit comes before that parent's exit; both are static. Where the exit lies behind the ray's start, the parent is read along the ray, which happens for 0.3% of the weight at the first world hand-over and never above it. In the lab this kept 21 to 37% fewer records than Kuhn-then-sphere at split errors within 0.015 and a sealed-box leak of 0.0008 (E2).
- **The sealed alternative** is the Kuhn fix at the first world hand-over and the sphere fix above, which leaked 0.0001 for a third more records. M3 measures both on the thin-walled sunlit rooms of the [evaluation](evaluation.md#scenes).
- **The top cascade's misses** read the sky ([lighting.md](lighting.md#sky)).

## A pass

A pass turns texel radiance into texel irradiance through the stored records, from the top cascade down. Each step is one dispatch with one thread per output value, so nothing needs atomics ([docs](../docs/rendering_device.md)).

1. **Top cascade:** each probe-bin's value is the radiance of its hit texel, or the sky for a miss.
2. **Each world cascade below, down to 1:** each probe-bin's value is its hit's radiance where the hit comes before a parent's exit, and that parent's value toward the exit otherwise, blended by the parents' trilinear weights.
3. **Cascade 0:** for each texel and bin, the bent segments to the front parents return their hits' radiance or the parents' values in the bin's sub-directions, blended by the renormalized weights.
4. **Irradiance:** each texel sums its 16 merged bins weighted by their integrated cosines, which add up to π.

Steps 1 and 2 read 4 to 5 bytes per record and, on misses, parent values that neighbouring probes share. Step 3 reads up to 16 parent values per missed segment (four sub-directions times four bilinear bins). If M3 finds step 3 limited by those reads, cascade 1 can store each bin's pre-averaged children at cascade 0's resolution, so a missed segment reads 4 values instead of 16; the lab did not test that read, so it is measured against the exact one before use.

## Checks in the engine

- **Furnace.** In a closed scene with every texel at radiance 1 and no sky, every texel's irradiance is π less the merge's deficit; the lab's deficits for this layout were 0.0010 to 0.0052 (E2).
- **Sealed box.** Sky light inside a closed box with one-texel walls stays at the lab's 0.0008 of the outside or below.
- **Determinism.** The same frame rendered after two different histories is bit-identical.

## Open questions

- Records per texel for scenes that need four or more world cascades: the lab stops at three, and the [budget](budget.md#texel-spacing) charges 60 per texel for each cascade above the first (M3).
- 16 against 36 bins at equal cost (M3).
- The sphere fix against Kuhn at the first world hand-over in thin-walled interiors (M3).
- Pre-averaged cascade 1 reads (M3).
