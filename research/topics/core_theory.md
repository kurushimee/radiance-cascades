# Core theory

Radiance cascades (RC) store a radiance field as a stack of probe grids. Each grid, a cascade, holds one band of distances along every ray: near bands use dense probes with few directions, far bands use sparse probes with many. Merging the bands from the farthest down gives each probe of the densest grid the light from all distances, at a cost close to that of the densest grid alone. This topic covers the theory shared by every variant: the penumbra condition, radiance intervals, the merge operator, the scaling laws and what they cost, interpolation, how cascades answer diffuse, specular and sky queries, and where the method is exact and where it approximates.

The index math, interval formulas of each implementation, storage layouts, merge kernels, cascade −1 and the final gather are in [cascade layout and merging](cascade_layout_and_merging.md); the observed artifacts and every fix are in [artifacts and fixes](artifacts_and_fixes.md); measured timings are in [performance](performance.md); the 2D-specific line-space variant is in [holographic RC](holographic_rc.md).

Statements marked "derived" were computed from the sources' own formulas and are not stated in them; statements marked "inference" are conclusions drawn here.

## The penumbra condition

Take the smallest light in the scene, of size `w`, at distance `d` behind an occluder edge. The penumbra opens at angle `α = 2·atan(w/2d) ≈ w/d`. At distance `D` from the light (with `D ≫ d`) the penumbra is `α·D` wide, and the light covers an angle of about `w/D`. A discretization resolves both when ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#penumbra-condition)):

```
Δp ≲ α·D      spatial step may grow linearly with distance
Δω ≲ w/D      angular step must shrink as 1/D
```

`A ≲ B` means `A` stays below some function that scales linearly with `B` ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#penumbra-condition)). Since `w` and `α` are fixed for a scene, the condition is usually written `Δp ≲ D`, `Δω ≲ 1/D`. Near an object, light needs dense positions and few directions; far away, sparse positions and many directions. The two requirements are inversely proportional, so a method can trade one for the other ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#penumbra-hypothesis)).

Osborne and Sannikov restate it precisely ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#method-restated-more-precisely)): a light of length `w` at distance `d` from a blocker casts a penumbra of angle `γ = 2·atan(w/2d)`, which is `γ·h` wide at distance `h` from the blocker, so `Δs < γ·h`; the light subtends `ε(D) = 2·atan(w/2D)` at distance `D`, so `Δω < ε(D)`. For `d ≪ D` this gives `Δs ≲ γ·D` and `Δω ≲ w/D`. When `d ≈ D` and the penumbra angle is not small, `Δω` must shrink faster than `1/D`.

Other statements of the same idea:

- Coppen splits it into an angular observation (a probe moving away from a light runs out of angular resolution; the needed angle depends on the distance to the furthest object and the size of the smallest) and a spatial one (a penumbra from a line light and a line occluder is resolved by interpolating between only two probes; the needed spacing grows with the distance to the closest object). Splitting a probe's rays by angle alone leaves each probe casting as many rays, so the spatial observation makes each ring its own probe, which can then move. A wall is a light that emits nothing and a light is a wall that emits, so the condition concerns objects, not lights ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#observations)).
- McGhee: the linear resolution needed to capture an area is inversely proportional to its distance and the angular resolution proportional to it, "the farther the light, the more rays per pixel are needed and the fewer pixels need to be looked at". With 4 rays a black dot far from a light is lost and more rays recover it ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#2-penumbra-hypothesis-article)).
- The LIRIS talk frames classic probe GI as leaving three things undefined (spatial and directional resolution, interpolation between probes, interpolation between hierarchy levels) and the penumbra condition as the rule that fixes them ([non-English overviews](../sources/2025_non_english_rc_overviews.md#liris-gdl-talk-irradiance-volumes--radiance-cascades-19962026)).

The condition is a sampling-rate rule in the sense of Nyquist ([supporting techniques](supporting_techniques.md#light-transport-and-solver-math)): it states the spatial and angular frequencies a penumbra can contain at each distance, and spaces samples to match.

### The penumbra hypothesis

The paper assumes that a discretization meeting the condition represents any radiance field well, because a field is a superposition of penumbras. The two extremes already used in games fit it: ambient occlusion (`Δp → 0`, no directions) and environment maps (no positions, `Δω → 0`). RC fills the levels between them, where Lumen and GI-1.0 use four hand-chosen levels (AO, screen probes, world radiance cache, environment) ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#context-from-the-related-work-section)). When resolution runs short, shadows blur as if lights were larger, so quality degrades gracefully.

### Which distance: occluder and light separated

The symbol `D` does double duty: Coppen's angular observation uses the distance to the furthest object and the spatial one the distance to the closest, and the condition uses one `D` for both ([Coppen, unclear items](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#unclear-in-source)). Separating them (derived): let a receiver sit at distance `h` in front of an occluder edge, with a light of size `w` a further `d` behind it.

- The penumbra at the receiver is `w·h/d` wide, so the spatial step must satisfy `Δp < (w/d)·h`. RC assigns the occluder to the cascade whose interval contains `h`, where `Δp = k·h` with a fixed ratio `k = Δp_i/t_i`, so the requirement is `k < w/d`: the spacing-to-distance ratio of the cascades must stay below the smallest penumbra angle in the scene, `w_min/d_max`.
- The angular step must satisfy `Δω < w/(h + d)`: the gap between neighbouring rays where they reach the light must be smaller than the light.

So the spatial requirement depends on the largest light-to-occluder distance in the scene, and it is the harder one. A small light far behind its occluder makes a narrow penumbra that no fixed `k` resolves; the cascade that sees the occluder smears it. This is the case Osborne flags (`d ≈ D`) and the error HRC was built to remove: with an occluder halfway to a distant small light of size `l`, the penumbra near the probe is about `l` wide, the occluder is seen by cascade `log4(D/r)` with spacing `s·D/r`, and once that exceeds `l` the penumbra smears; in HRC's test, standard RC tuned to equal time had twice HRC's RMSE, all of it in penumbras ([HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#what-it-fixes-in-plain-rc)).

The sun is the limit of this case (derived). Its disc is 0.53° wide (0.0093 rad), and with `d → ∞` the penumbra angle is the disc angle, so a sun shadow at distance `h` behind its caster is resolved only where `Δp < 0.0093·h`. With Split RC's settings (`t0 = 1.6·Δs0`, `l = 4`) the ratio `Δp_i/t` is 0.625 at the end of cascade 0 and halves per cascade, so cascade 3, the top one there, still smears sun penumbras by 8× (at its interval end) to 34× (at its start); the requirement is met only from cascade 7 to 9 on. RC with 4 or 5 cascades never resolves sun shadows.

Two consequences (inference):

- RC suits indirect light, whose sources are lit surfaces: large, close to the occluders that shape their shadows, and with wide penumbras. Direct light from the sun and from small lights needs its own shadowing. The shipped 2D Switch game in the [merging notes](../sources/2026_merging_and_ringing.md#scaling-and-setups) does this, with RC carrying indirect light and point lights shadowed separately, and the blurred hard shadows of foliage in Split RC's comparison are the same limit ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#quality-versus-ddgi-and-reference)).
- The cascade structure has a minimum penumbra angle by design: soft, splotchy shadows behind small sharp sources are expected behaviour, not a bug ([merging notes](../sources/2026_merging_and_ringing.md#why-it-works)), and RC is "notoriously bad" at very sharp shadows ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#limitations-and-author-statements)). The paper names the same failure for vanishingly small lights very close to occluders and too-sharp penumbras ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#failure-modes-and-tuning)).

### Rays cast against directions stored

The penumbra condition concerns rays cast, not directions stored: 4×2 stored cones with 8×8 rays each use the same memory as 4×2 cones with one ray, so averaging many rays per stored cone meets the angular requirement without more storage ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)). Pre-averaging, where each stored texel is the mean of the rays it will be merged into, is the same idea applied to merging ([cascade layout](cascade_layout_and_merging.md)).

## Radiance intervals

`L[a,b](p, ω)` is the radiance arriving at `p` from direction `ω` that comes only from points at distance `t ∈ [a, b]` along `p + t·ω`. With a ray cast `R(p, ω)` returning the nearest opaque hit, `L[a,b](p, ω) = L_out(R(p + a·ω, ω), −ω)` if that hit is closer than `b`, else 0. In a medium:

```
L[a,b](p, ω) = ∫ₐᵇ exp(−∫ₐˣ σ(p + y·ω) dy) · L_emi(p + x·ω, −ω) dx
```

The matching transparency `β[a,b](p, ω)` is 0 if something opaque lies in `[a, b]` and 1 otherwise; in a medium it is the transmittance of the segment, the Beer-Lambert `exp(−∫σ)` ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#radiance-intervals), [Beer-Lambert](supporting_techniques.md#light-transport-and-solver-math)). A probe texel stores RGB radiance with `β` in alpha. Osborne writes the interval as `R[a,b](p, ω) = [I(b→a), τ(b→a)]`, intensity and optical depth accumulated over the segment, which any 1D solver can integrate ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#method-restated-more-precisely)). Volumetric marching and its pitfalls are in [volumetric and radiative transfer](volumetric_and_radiative_transfer.md).

Conventions differ between codes. GM Shaders' text and original code store 1.0 for a hit while its optimized code stores 0 for a hit, and several codes drop alpha and stop merging after any hit ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#inconsistencies-in-part-one), [2D articles and demos](2d_articles_and_demos.md#gm-shaders-yaazarai-and-xor)). A hit-stops-merging shortcut is the binary case `β = 0`; fades, pre-averaging, mips and the inner parallax fix need a continuous `β`, so binary shortcuts break them ([merging notes](../sources/2026_merging_and_ringing.md#parameters-that-look-like-merge-bugs)).

An interval ignores everything before its start. A small occluder sitting on a probe therefore does not shadow that probe's upper-cascade rays, which Split RC uses deliberately ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#merge-with-cones)). The flip side is that what an interval sees at its start depends on where the start lands: inside a solid, codes return the solid's emission at once (fad), black on every cascade but 0 (the interior mask), or zero (Dolkar's mask), and the choice changes ringing and darkening ([artifacts and fixes](artifacts_and_fixes.md)).

## The merge operator

Adjacent intervals combine like front-to-back alpha blending ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#merge)):

```
L[a,c] = L[a,b] + β[a,b] · L[b,c]
β[a,c] = β[a,b] · β[b,c]
```

In optical-depth form, `I = I(b→a) + exp(−τ(b→a))·I(c→b)` and `τ = τ(b→a) + τ(c→b)` ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#method-restated-more-precisely)). Coppen's GLSL:

```glsl
vec4 merge_intervals(vec4 near, vec4 far) {
    const vec3 radiance = near.rgb + (far.rgb * near.a);
    return vec4(radiance, near.a * far.a);
}
```

Full radiance is the interval `[0, ∞)`, rebuilt by merging `[0, t1], [t1, t2], …`; visibility terms multiply, so one hit carries down the chain ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#merging-intervals)).

Properties:

- **It is Porter and Duff's "over" with premultiplied colour.** Emitted radiance plays premultiplied colour and `β = 1 − α` ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#merge-with-cones), [HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#formulation), [glossary](supporting_techniques.md#visibility-shadows-and-screen-space)). Scene textures accordingly store emission times opacity ([tmpvar playground](../sources/2024_tmpvar_rc_playground.md)).
- **It is associative with identity `(0, 1)`**, so intervals form a monoid (derived). Back-to-front and front-to-back give the same result ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#merge)); front to back allows early exit once a long interval is opaque ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#other-implementation-notes)). Associativity is what lets HRC build long rays by merging short ones and lets a parallel scan combine segments in any grouping (derived).
- **It is linear in the far interval for a fixed near one.** For weights summing to 1, `Σ w_k·merge(n, f_k) = merge(n, Σ w_k·f_k)` (derived). So in vanilla RC, where all upper samples sit behind one shared lower interval, interpolating the upper cascade before merging equals merging each sample and interpolating after. The bilinear fix is different because each upper probe gets its own lower interval ([artifacts and fixes](artifacts_and_fixes.md)). This also settles two items Coppen leaves unexplained (derived): multiplying the merged alpha by the bilinear weight is correct when the weights sum to 1, since the sum is then the interpolated transmittance behind the shared lower interval; and the final division by 4.0 is the average over the 4 child directions that make up the parent's cone ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#merging-algorithm)).
- **It needs no attenuation term.** Merging produces the `1/r` falloff of 2D light by itself ([merging notes](../sources/2026_merging_and_ringing.md#formats-and-color)).

## Shift and extend

Two identities follow from the definition ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#shift-and-extend)):

- **Shift:** `L[a+x, b+x](p, ω) = L[a,b](p + x·ω, ω)`, the same segment described from another start point.
- **Extend:** with `L[a, a+x]` known everywhere, `L[a, a+2x](p) = L[a, a+x](p) + β[a, a+x](p)·L[a, a+x](p + x·ω)`.

A cascade can therefore raymarch a short piece of its interval and double it repeatedly by reading itself at shifted positions, each doubling costing O(1). Radiant 2D marches only `[512, 544]` of the interval `[512, 1024]` and reaches the rest by repeated extension ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#early-implementations)). Osborne's rule: trace an initial piece at least one probe spacing long, then extend recursively by merging with the interpolated value at the endpoint ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#other-implementation-notes)).

Extension works only on regular grids (flatland, world-space 3D), where `p + x·ω` can be read from neighbouring probes. Screen-space probes each sit at their own depth, so there is nothing to read at the shifted point ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#shift-and-extend)).

### Where the merge is exact (derived)

The two identities show exactly what vanilla merging approximates. A lower probe at `p` needs `L[t1, t2](p, ω)`. The upper cascade stores `L[t1, t2](q, ω)` only at its own probes `q`, which sit up to half an upper cell away from `p`. Interpolating those values treats parallel segments that start at different points as if they were the segment from `p`, which is right only if nothing in the scene changes over the offset `p − q`. The four RC variants differ in how they handle this offset:

| Scheme | What the lower ray is joined to | Exactness |
|---|---|---|
| Vanilla | the bilinear (2D) or trilinear (3D) blend of the upper probes' parallel segments | approximate in space; occlusion seen from `q` is applied to light reaching `p` |
| Bilinear fix | for each upper probe `q_k`, a ray traced from `p + t1·ω` to `q_k + t1'·ω`, merged with `q_k`'s own segment, then blended | each path is continuous but bent; exact paths, approximate blend |
| Forking | every group of child rays starts at one shared point | paths continuous; angular resolution lower |
| HRC | directions chosen so that `p + v_n(k)` is exactly a probe of the next level | the extend identity holds exactly along cone edges; only the angular split is averaged |

Vanilla merging is thus an extend whose shift is replaced by spatial interpolation; the fixes in [artifacts and fixes](artifacts_and_fixes.md) are ways to restore the shift, and HRC is a lattice designed so that the shift needs no interpolation ([HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#merging-down-r_n-from-r_n1), [holographic RC](holographic_rc.md)). The paper's own description of Radiant 2D's extension uses "the interpolated value at the endpoint", so it carries the same approximation.

## Cascade scaling

A cascade is a uniform grid of probes storing one interval `[a, b]` with `Δp ≲ a` and `Δω ≲ 1/b`. Cascade `i` stores `[t_i, t_{i+1}]` with `t0 = 0` and `t_i → ∞`. Doubling the probe spacing per cascade, as in a mip chain, forces the rest ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#cascade-scaling)):

```
Δp ∝ 2^i      Δω ∝ 1/2^i      t_i ∝ 2^i
```

Each cascade has twice the probe spacing, half the angular step and an interval twice as long. Storage can be cube maps, octahedral maps or spherical harmonics; only the asymptotic texel count matters. Any sequence satisfying the scaling makes a valid cascade set, storage falls directly as the steps grow, and cascade 0's interval is an arbitrary parameter the others scale from ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#failure-modes-and-tuning)).

The general form has a branching factor ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#method-restated-more-precisely), [Split RC](../sources/2026_freeman_split_radiance_cascades.md#parameters-and-why)):

| Source | Spacing | Directions | Interval length |
|---|---|---|---|
| Osborne and Sannikov | `Δs ∝ 2^i` | `Δω ∝ 1/2^(α·i)` | `t_i ∝ 2^(α·i)` |
| Split RC | `Δs_n = Δs0·2^n` | `|Ω_n| = |Ω0|·K^n` | `t_n = t0·l^n` |

In Osborne's form the branching factor scales angle and interval length together; in 2D `α = 1` halves the ray count per cascade and `α = 2` keeps it constant, and all of Osborne's examples use `α = 2`. Split RC separates the two: `K` multiplies the direction count and `l` the interval length. In the notation of the [merging notes](../sources/2026_merging_and_ringing.md#scaling-and-setups) a scheme is written spatial/angular: `2x/4x` doubles probe spacing per axis and quadruples directions, `2x/2x` halves each cascade, and some people write the spatial factor in area, so 2x/4x becomes 4x/4x.

Almost every 2D implementation uses 2x/4x: 4 times the directions and intervals 4 times as long per cascade. The choice is attributed to Sannikov as best for 2D, not a hard rule ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#cascade-layout)); Radiant 2D used it and found a better quality-to-cost ratio before knowing why ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#early-implementations)); Coppen recommends it because cascades stay the same size and it is simpler to work with, while noting it costs more and may look better in some cases ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#cascade-memory)); Osborne's slides say it looks somewhat better ([slides](../sources/2024_rc_blog_posts_and_slides.md#osborne-slides)).

### Two criteria for interval scaling (derived)

With spacing ×2 per cascade, `K` directions per parent and interval scale `l`, three ratios change per cascade. Here `m` is the number of direction dimensions (1 in flatland, 2 in 3D and for screen or surface probes), and the ray-end gap is the distance between neighbouring rays at the end of an interval, `t·Δω`:

| Domain | `K` | `l` | spatial ratio `Δp/t` | angular ratio `Δω·t_end` | gap / spacing | Used by |
|---|---|---|---|---|---|---|
| 2D | 2 | 2 | ×1 | ×1 | ×0.5 | the paper's minimum (`α = 1`) |
| 2D | 4 | 4 | ×0.5 | ×1 | ×0.5 | nearly every 2D code (2x/4x) |
| 2D | 2 | 4 | ×0.5 | ×2 | ×1 | Split RC's 2D choice |
| 3D | 4 | 2 | ×1 | ×1 | ×0.5 | the paper; DexRT's 3D solver |
| 3D | 4 | 4 | ×0.5 | ×2 | ×1 | Split RC |
| 3D | 8 | 4 | ×0.5 | ×1.41 | ×0.71 | none found |
| screen | 4 | 2 | ×1 | ×1 | ×0.5 | PoE2 |
| screen | 4 | 4 | ×0.5 | ×2 | ×1 | most SPWI codes ([3D screen space](3d_screen_space.md#directions-in-3d)) |

The angular ratio is `l/K^(1/m)` and the spatial ratio `2/l`. Two criteria pick different rows:

- **Constant penumbra ratios.** The paper's scaling holds both `Δp/t` and `Δω·t` constant (`l = 2`, `K = 2^m`). If the penumbra condition holds at cascade 0 it then holds at every cascade, for the same smallest light and penumbra angle. The 2D 2x/4x scheme keeps the angular ratio constant and improves the spatial one.
- **Equal absolute error.** Split RC asks that the angular error at a ray's end equal the probe spacing in every cascade, `Δω_n·t_n = Δs_n`, with `Δω_n = t_n·√(4π/|Ω_n|) = (l/√K)^n·Δω0` in 3D. That needs `l/K^(1/m) = 2`: `K = 4, l = 4` in 3D and `K = 2, l = 4` in 2D ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#parameters-and-why)). The price is that the angular ratio doubles per cascade, so the smallest resolvable light grows ×2 per cascade.

Most earlier implementations used `l = 2`, the constant angular error per cascade. The evidence favours equal error for perceived quality. In Split RC's 2D appendix (32 cascade 0 directions, one probe per pixel), `l = 4` spread aliasing and blur evenly over the image, while `l = 2` drifted from aliasing near the light to blur far away whatever `t0` was. The table explains the drift: with `l = 2` the gap-to-spacing ratio halves per cascade, so near cascades are dominated by angular error and far ones by spatial error. Sparse 3D builds report the same: 4× interval scaling was called the only correct value in 3D, giving uniform error at the same compute and memory with one fewer cascade, while 2× error is "dominated by angular error near and spatial error far" ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)). Split RC also notes that PoE2's `l = 2` works only because it traces the depth buffer with a top-down camera, where the scene's vertical extent does not grow with distance ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#parameters-and-why)).

The "interval scaling should match angular scaling" rule of the 2D community ([merging notes](../sources/2026_merging_and_ringing.md#scaling-and-setups)) is the 2D constant-angular-ratio row, `l = K`.

With `l = 4` far fewer cascades span a scene: covering 500 cascade 0 intervals takes about 9 cascades at `l = 2` and about 5 at `l = 4` (derived, `log2 500` against `log4 500`). Split RC spans whole scenes with 4 or 5 and lets the top cascade's misses sample the environment map.

A 2D sweep of the scaling factor (×2, ×3, ×3.5, ×4, ×6, ×8) found ×3 and ×3.5 best by eye and the rest clearly worse. All parameters depend on each other and there is no measured optimum: longer intervals alias, shorter ones soften ([merging notes](../sources/2026_merging_and_ringing.md#parameters-that-look-like-merge-bugs)).

### Parallax in bin units (derived)

A parent probe sees a child's ray end from a direction that differs from the child's by about the parallax angle `Δp/t`, which changes by `2/l` per cascade, while the bin width along each direction axis changes by `1/K^(1/m)`. The misalignment counted in parent bins therefore changes by `2·K^(1/m)/l` per cascade, the reciprocal of the gap-to-spacing column in the table above:

| Scaling | Shift in bins per cascade | After 4 cascades |
|---|---|---|
| 2D `K = 2, l = 4`; 3D `K = 4, l = 4` | ×1 | ×1 |
| 3D `K = 8, l = 4` | ×1.41 | ×4 |
| 2D 2x/4x; 2D `K = 2, l = 2`; 3D `K = 4, l = 2`; screen `K = 4, l = 2` | ×2 | ×16 |

The shift stays constant only on the equal-error rows, `l = 2·K^(1/m)`. Two other arguments land on the same rows. Reservoir Cascades proves the 2D case as its Lemma 2: under ×4 branching the shift is `Θ(2^n)` bins, and the claim that it stays within `O(1)` bins holds only for ×2 branching. RCPG asks that a texel stand for its direction from anywhere in its cell and gets interval ends `t_max ∝ 4^i` for 3D `K = 4`. Equal error, alignment and direction fidelity are therefore one condition ([sampling and guiding](rc_for_sampling_and_guiding.md#connections)). The scalings off it need a parallax correction that grows with depth: the bilinear and parallax fixes in 2D ([artifacts](artifacts_and_fixes.md#the-bilinear-fix)), Reservoir Cascades' reprojected lookup, or its windowed lookup beyond 3 to 4 levels.

### Choosing cascade 0 (derived and reported)

The paper gives asymptotic scaling only and leaves cascade 0's probe spacing, angular step and interval to tuning; the LaTeX source says the omitted initial values "dramatically affect both accuracy and performance" and take "some amount of fiddling" ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#failure-modes-and-tuning)). Three rules from the sources constrain `t0`, the cascade 0 interval, against the spacing `Δs0` and the direction count `N0`:

- **Equal error:** `t0 = Δs0/Δω0`, with `Δω0 = 2π/N0` in 2D and `√(4π/N0)` in 3D (derived from Split RC's criterion). For 32 directions this gives `5.09·Δs0` in 2D and `1.60·Δs0` in 3D, which are exactly Split RC's predicted `t0 ≈ 5·Δs0` for its 2D test and its final 3D setting `t0 ≈ 1.6·Δs0`. A Unity port of Split RC writes the constant out as `kC0Len = 1.5958 = √(32/4π)` ([plugins](../sources/2026_unity_unreal_rc_plugins.md)). In 2D they used `t0 = 1·Δs0`, because aliasing looks worse than blur, so shorter is better unless several rays per direction average it out.
- **Diagonal rule:** `t0` should be at least the diagonal of the cascade 0 cell, `√2·Δs0` in 2D (and so `√3·Δs0 ≈ 1.73·Δs0` in 3D, derived). Shorter intervals bring the ray ends of cascades `N` and `N + 1` so close that interpolation squeezes into a small space, which shows as bent rays, small leaks and flicker under motion; this was the most common parameter mistake in 2D ([merging notes](../sources/2026_merging_and_ringing.md#parameters-that-look-like-merge-bugs)).
- **Gaps:** a cascade 0 interval that is too long leaves visible gaps between the interval segments of different cascades, and shortening it until they connect gives a continuous result ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#failure-modes-and-tuning)).

The equal-error rule gives 0.64, 1.27, 2.55, 5.09 and 10.2 spacings in 2D for 4, 8, 16, 32 and 64 directions, and 0.56, 0.80, 1.13, 1.60 and 2.26 in 3D (derived). At the 4 directions most 2D codes use, it asks for less than the diagonal rule's 1.41, and the diagonal rule binds: below it the merge geometry breaks before the error balance matters. At 32 or more directions in 2D the equal-error value is far above the diagonal and the observed preference for shorter intervals (aliasing reads worse than blur) binds instead. In 3D at 32 directions the two rules nearly coincide (1.60 against 1.73), which may be why Split RC's setting works well (inference).

The cascade 0 interval also sets the smallest light that resolves: a light resolves only if its size exceeds the ray-end gap `2π·t0/N0`, and about twice that by the Nyquist limit ([merging notes](../sources/2026_merging_and_ringing.md#parameters-that-look-like-merge-bugs)). The reported failure confirms the rule: a 5 px light flickered with 16 directions and a 10 px interval, where the rule gives 3.9 px and the Nyquist bound 7.9 px (derived). Under 2x/4x the gap is the same at every cascade's end, so the rule holds for every distance; under `l = 4, K = 2` (2D) or `K = 4` (3D) the gap doubles per cascade (derived, from the table above).

Sparse 3D builds add: cutting cascade 0 spatial resolution before angular resolution smooths GI, while cutting angular resolution aliases; 8 cascade 0 directions showed obvious artifacts against 32; a typical cascade 0 interval in Sponza was about 0.015 scene units, with 0.005 too short; and shorter cascade 0 intervals sharpen contact shadows and worsen peter-panning ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)).

### Sizing from the exact condition

Kornel Lesiński's RadiCalc sizes 2D cascades from the penumbra condition instead of fixed powers of 4 ([kornel.ski](../sources/2024_rc_blog_posts_and_slides.md#kornelski-penumbra-calculator)). With base spacing `s`, `P(c) = s·2^c`, light size `L` and penumbra angle `a`:

- The light-to-wall distance where the penumbra starts is `d = (L/2)/tan(a/2)`, and the distance where spacing `P` fits inside the penumbra is `w(P) = (P/2)/tan(a/2)`.
- Cascade `c` covers `[(w(P(c)) + d)^p, (w(P(c+1)) + d)^p]` with exponent `p = 1` by default; cascade 0 starts at 0.
- Rays per probe are `ceil(2π·end/L)`, so the smallest light is still hit at the interval end, or `ceil(2π·(end + P)/L)` to cover the probe farthest from the light; a diagonal mode uses `√2·P`. Steps per interval assume volumetric marching at the light size, `ceil(length/L)`, and an optional per-cascade mip divider scales lengths, light size and rays down.

With the defaults (spacing 1, light 1, 90°, 1920×1080) intervals only double and rays roughly double per cascade (16, 29, 54, 104, …); 12 cascades fit, the total is 37 M probe-rays and 144 M probe-ray-steps, and cascade 0 alone holds 56% of the probe-rays. The exact condition gives intervals shorter than the probe spacing, unlike the usual ×4 intervals. Its doubling intervals and roughly doubling rays are the 2D `l = 2, K = 2` row: the exact condition lands on the paper's constant-ratio scaling, not on 2x/4x (derived).

## Memory and cost

### Memory by domain

The texel count of cascade `i` relative to cascade 0 is `r^i`, where `r` is the direction factor over the probe-count factor ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#memory-by-dimensionality)):

| Domain | Probes in cascade `i` | Directions per probe | Memory of cascade `i` | Total for `N` cascades |
|---|---|---|---|---|
| Flatland (2D position, 1D angle) | `∝ 1/4^i` | `∝ 2^i` | `M0/2^i` | `< 2·M0` |
| 3D grid (3D position, 2D angle) | `∝ 1/8^i` | `∝ 4^i` | `M0/2^i` | `< 2·M0` |
| Surface (2D position, 2D angle) | `∝ 1/4^i` | `∝ 4^i` | `M0` | `N·M0` |

Totals for other branching factors (derived, `Σ r^i`):

| Domain and scheme | `r` | 4 cascades | 5 | 6 | 8 |
|---|---|---|---|---|---|
| 2D, ×2 directions | 0.5 | 1.88 | 1.94 | 1.97 | 1.99 |
| 2D, ×3 directions | 0.75 | 2.73 | 3.05 | 3.29 | 3.60 |
| 2D, ×4 directions | 1 | 4 | 5 | 6 | 8 |
| 2D, ×8 directions | 2 | 15 | 31 | 63 | 255 |
| 3D grid, ×4 directions | 0.5 | 1.88 | 1.94 | 1.97 | 1.99 |
| 3D grid, ×8 directions | 1 | 4 | 5 | 6 | 8 |
| Surface or screen, ×4 directions | 1 | 4 | 5 | 6 | 8 |

The paper's flatland atlas example has cascade 0 at 32×32 probes of 8×8 angular texels and cascade 1 at 16×16 probes of 8×16, the whole atlas twice the width of cascade 0; its surface example has cascade 0 at 16×16 probes of 8×8 texels and cascade 1 at 8×8 probes of 16×16, growing linearly with the cascade count. The [merging notes](../sources/2026_merging_and_ringing.md#scaling-and-setups) give 2.75×M0 for 2x/3x against 1.0× per cascade for constant-size cascades. For a full 3D grid, cascade 0 alone is usually the deal breaker, and the hierarchy as a whole takes about as much memory as cascade 0, which scales with scene size cubed; for surfaces cascade 0 is cheap ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#memory-by-dimensionality)). Removing the stored cascade 0 entirely, by tracing it per pixel during the final gather (cascade −1 gathering), was the largest 3D memory saving found ([cascade layout](cascade_layout_and_merging.md)).

### Rays traced and rays built

In flatland with `α = 1`, cascade 1 has `P0/4` probes and `2·Q0` directions, half the intervals of cascade 0. Interpolating cascade 1 to every cascade 0 probe and merging builds `2·P0·Q0` full-length rays from `1.5·P0·Q0` stored intervals, and each added cascade costs half the previous one while doubling the effective rays ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#cost-analysis-flatland)):

```
rays(N) = 2^N · rays(0)
cost(N) = (1 + 1/2 + … + 1/2^N) · cost(0) < 2 · cost(0)
```

With `α = 2` every cascade traces the same `N0` rays, so the cost is `I·N0` and the merge builds `4^I·N0` rays; Osborne's slides set this against rays halving per cascade (under `2·N0` traced, `2^I·N0` built) and say the second choice looks somewhat better ([Osborne's slides](../sources/2024_rc_blog_posts_and_slides.md#osborne-slides)). In general the traced count follows the memory table above, one ray per stored texel, and the built count grows as `K^N` (derived). The cascade count is capped near `log(P0)`, and the built rays are accurate only while the penumbra hypothesis holds ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#cost-analysis-flatland)).

Time does not follow ray count alone, because upper intervals are longer ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#method-restated-more-precisely)). In DexRT's 2D run (cascade 0 interval 1.5 voxels, ×4 per cascade, 6 cascades, constant texels per cascade) cascade 5 took 63.6% of the run time, cascade 4 21.4% and cascade 0 only 0.5% ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#numbers-from-the-dexrt-run)). If time is proportional to interval length with equal texels per cascade, the shares are 0.1%, 0.3%, 1.2%, 4.7%, 18.8% and 75% (derived from lengths 1.5, 4.5, 18, 72, 288 and 1152 voxels). The model gets the ordering and the lower cascades right; the measured top share falls short of 75% because the top cascade runs its rays only until they leave the domain, with sparse calculation and early exit on opaque intervals also cutting long rays short (inference). The consequence for any grid RC that marches at full resolution is that the top one or two cascades dominate the cost, which is what per-cascade mip marching ([volumetric](volumetric_and_radiative_transfer.md), [DexRT](../sources/2025_osborne_dexrt_ray_acceleration.md)) and interval extension attack.

### Independence from light count and scene content

RC traces the same rays whatever emits light, so its cost does not depend on the number of lights: Radiant 2D cost about 12 ms with 2, 102 and 1002 lights alike ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#early-implementations), [80.lv](../sources/2024_rc_blog_posts_and_slides.md#80lv-news)). It does depend on how far rays march before hitting, except in HRC, whose upper levels are built by merging and cost the same for empty and dense scenes ([HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#ray-acceleration-structure-t_n)).

For scale, McGhee's estimate for brute-force 2D GI: 1024² pixels at 512 rays is about 500 M rays per frame, about 1 B texture lookups at 10 steps and 2 lookups per ray, about 1 s at 1 ns per lookup, so a 16 ms target needs roughly 100× less work ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#1-why-the-naive-method-is-slow-article)). Measured comparisons with path tracing are in [performance](performance.md).

### Constant cost

The paper names RC's high constant cost as its main limitation: a 3D cascade 0 grid costs about as much as voxelizing the scene, and a detailed screen-space cascade 0 alone can take milliseconds. Hardware ray tracing could fill world-space intervals with the same asymptotic scaling but an order of magnitude higher constant ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#limitations-stated-by-the-author)). Screen-space artifacts (no off-screen lights, no hidden occluders, nothing behind the depth buffer) come from tracing screen-space data, not from storing cascades in screen space.

## Interpolation and band limits

The paper argues that probe data in a cascade meeting the penumbra condition is band-limited, so plain linear interpolation in space and direction reconstructs it without bilateral filtering or disocclusion handling; classic probes need those fixes because they store full radiance rather than intervals ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#cost-analysis-flatland)). The LIRIS talk puts it the same way: the interval constraint is what makes the sampled function possible to reconstruct and interpolate ([non-English overviews](../sources/2025_non_english_rc_overviews.md#liris-gdl-talk-irradiance-volumes--radiance-cascades-19962026)). The contrast is with probe methods such as DDGI, which store full-length radiance and need a Chebyshev visibility test to interpolate across walls ([glossary](supporting_techniques.md#visibility-shadows-and-screen-space), [related probe GI](related_probe_gi.md)).

The same paper's screen-probe variant with world-space intervals interpolates spatially with bilateral weights, counting only neighbours of similar depth ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#early-implementations)). The two statements are compatible once the condition behind the claim is explicit (inference): band-limiting holds for probes that sample one continuous field in free space, as on a regular grid; probes placed on a depth buffer sit on different surfaces at different depths, so neighbours are samples of different fields and need depth-aware weights. Every screen-space design confirms this ([3D screen space](3d_screen_space.md)).

Linear interpolation is also not free of error on a grid:

- Light falls off as `1/r` in 2D while interpolation between probes falls off linearly, and the mismatch shows as rings ([merging notes](../sources/2026_merging_and_ringing.md#why-it-works)).
- Blocky interpolation patches in dark areas come from probe resolution and survive every merge fix; they show most on OLED screens, and cubic interpolation was suggested but not tested ([merging notes](../sources/2026_merging_and_ringing.md#why-it-works)).
- Cascade 0 probes inherit occlusion from cascade 1, so a shadow darkens uniformly below the level that saw the occluder, and interpolation cannot add resolution there ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)).
- Past the outermost probe row, lookups clamp, which flattens falloff near a domain border ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#other-implementation-notes)).

Higher-order storage has been tried only as an experiment: Sannikov's GradientRC stores each interval's value and its slope along the wedge center line, tested on `1/r` from a point source, a first-order reconstruction along the ray with none across it ([LegitCascades](../sources/2024_sannikov_legitcascades.md#gradientrcls)).

### Angle: cones, not rays

Merging all `2^α` child directions of a parent approximates the parent's cone; interpolating in angle before merging would give a single thin ray instead ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#method-restated-more-precisely)). Split RC writes the cone merge explicitly ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#merge-with-cones)):

```
C_n(x, ω) = J_n(x, ω) + β_n(x, ω) · (1/|π_n⁻¹(ω)|) · Σ over ω' in π_n⁻¹(ω) of C_{n+1}(x, ω')
```

where `π_n⁻¹(ω)` is the set of higher-cascade directions whose nearest direction is `ω`. `C0` then holds full radiance per cone, and shading integrates over `Ω0` with the cosine weight. Coppen draws the same structure as a cone built from intervals ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#merging-cones)).

Each merged direction thus has an implicit cone footprint: its angular width is the cascade's `Δω`, and its spatial width at distance `t` is about `t·Δω` (derived, [cone footprint](supporting_techniques.md#interpolation-and-footprints)). The penumbra condition is the statement that this footprint stays below the features it must resolve.

## Using the cascades

### Diffuse

Merge cascades from `N − 1` down to 0. Projecting cascade `i + 1` onto cascade `i` averages 2 (flatland, `α = 1`) or 4 (3D) child texels and merges the result into one parent texel. Cascade 0 then holds full radiance averaged over each of its few direction cones, which is enough because the cosine-weighted diffuse BRDF has low angular frequency ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#using-the-cascades)). Diffuse needs little directional detail, so everything is merged into cascade 0, the cascade with the lowest angular resolution ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#merging-cones)).

Turning cascade 0 into irradiance needs care in 3D: one cosine per cone is wrong (a cube-face cone pointing along a floor gets zero weight), and 4×4 cosine samples per cone cost about the same as 8×8 ([sparse 3D RC](../sources/2026_sparse_and_3d_rc.md#parameters-and-directions)); Rulkens measures the error of weighting each cone by its center cosine ([Rulkens](../sources/2025_rulkens_rc_medical_volume_data_thesis.md)). The gather of each implementation, and the 2D question of fluence against mean radiance, are in [cascade layout and merging](cascade_layout_and_merging.md).

### Radiometry in flatland

2D GI has its own radiometry. Fluence is radiance integrated over all directions without a cosine, the natural output when 2D points need not lie on surfaces; HRC works in fluence and treats every surface as a dense medium ([HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#formulation), [glossary](supporting_techniques.md#light-transport-and-solver-math)). Tantalum, the 2D spectral path tracer used for reference images, works in intrinsic 2D radiometry (Jarosz et al. 2012): radiance is per metre, a 2D Lambertian BRDF is 1/2 instead of `1/π`, and normalized Phong and microfacet lobes are rederived for one angle ([merging notes](../sources/2026_merging_and_ringing.md#links)). A 2D RC compared against a 3D-calibrated reference, or a 3D BRDF used in a 2D RC, is off by these factors (inference).

Under a uniform field the expected 2D values are simple: a closed hollow emitter of colour `c` gives `c` everywhere inside, and just outside its surface half the directions see it, so mean radiance approaches `c/2` there, which is the white furnace test of the [merging notes](../sources/2026_merging_and_ringing.md#debugging-routine) (derived; [white furnace](supporting_techniques.md#numerics-and-statistics)).

### Specular

A glossy lobe is a cone around the reflected view vector, and RC answers cone queries in O(N), like a prefiltered environment map indexed by roughness ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#using-the-cascades), [split sum](supporting_techniques.md#shading)):

- The narrowest cone queries each cascade separately in that direction and merges the results, giving the angular step of the top cascade.
- The widest cone is one lookup into the fully merged cascade 0.
- Cones in between query cascades `0..K` individually and merge them with one lookup into the merged cascade `K + 1`.

Split RC picks the cascade whose cone matches the lobe and merges it with the intervals of the lower cascades; sharp reflections need another method ([Split RC](../sources/2026_freeman_split_radiance_cascades.md#extensions-shown)). With 32 cascade 0 directions and ×4 per cascade, a cascade's direction cell is about 36°, 18°, 9°, 4.5° and 2.2° wide for cascades 0 to 4 (derived, `√(4π/|Ω|)`), so four or five cascades cover rough to moderately glossy lobes and nothing near a mirror. HRC has only 20 truly traced directions per point, which blurs specular BRDFs ([HRC paper](../sources/2025_freeman_holographic_radiance_cascades.md#final-gather-and-cleanup)), and PoE2's bitmask occlusion can feed specular ([paper](../sources/2023_sannikov_radiance_cascades_paper.md#early-implementations)).

### Sky and environment

The top cascade has nothing above it; it can be skipped or merged with a skybox ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#merging-algorithm)). The usual choice merges the sky integral into the top cascade, the one with the highest angular resolution and the farthest intervals. This leaves occlusion unchanged, and the cascade's low probe density is acceptable because sky light has little spatial variation ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#extensions-mentioned), [wiki](../sources/2026_rc_community_site_and_wiki.md#skybox-integral)). Osborne's top cascade runs its rays out of the domain and adds cascades if its angular resolution is too coarse for the boundary ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md#method-restated-more-precisely)).

The sky must be integrated over each top-cascade direction bin, not sampled at the bin center: coarse top bins would otherwise alias a small sun. Every fad-lineage shader uses Mathis's 2D integrals ([Shadertoys](../sources/2023_rc_shadertoys.md#nttsw7-mathis-analytic-direct-illumination-and-the-sky-integral)):

- `Sky(a0, a1) = SkyColor·[(a1 − a0) − 0.5·(cos a1 − cos a0)]` integrates `SkyColor·(1 + 0.5·sin a)`, a sky brighter overhead.
- `Sun(a0, a1) = SunColor/√S·[atan(√S·(A − a0)) − atan(√S·(A − a1))]` integrates a Lorentzian sun `SunColor/(1 + S·(a − A)²)` at `A = 2` rad with half-width `1/√S = 0.125` rad (`S = 64`).
- The RC shaders divide each bin's integral by its width, which gives the mean radiance over the bin, then by an unexplained 6; bins that cross 2π are split ([fad's mtlBzX](../sources/2023_rc_shadertoys.md#mtlbzx-fad-the-original-2d-implementation)).

No 3D form of the analytic sky integral was published; Coppen said in 2024 that Coppen's first 3D RC had none ([discussions](../sources/2026_rc_discussions.md#coppens-first-3d-rc-on-x-2024-08)). The 3D equivalent is the mean of the environment over each top-cascade direction cell, which a prefiltered environment map read at the mip whose texel matches the cell's solid angle approximates; on an octahedral map the cells differ in solid angle by up to 5.2×, so the mip must follow the cell, not the cascade (inference, [octahedral Jacobian](supporting_techniques.md#direction-parameterizations)). Volumetric clouds can be baked into the sky integral merged at the top cascade more cheaply than marched ([volumetric RC](../sources/2026_volumetric_rc.md)).

### Bounces

RC computes incoming radiance from given outgoing radiance, so one solve gives one bounce of whatever the scene emits; the Habr overview frames it as an approximation of the rendering equation limited to one indirect bounce, and a vpinball comment makes the same point ([non-English overviews](../sources/2025_non_english_rc_overviews.md#habr-radiance-cascades-a-new-look-at-global-illumination), [discussions](../sources/2026_rc_discussions.md)). Multi-bounce GI is the fixed point `L_out = E + ρ·K(L_out)`, with `K` the RC solve and `ρ` the albedo. Feeding last frame's result back as emission applies `K` once per frame, a Jacobi iteration of that fixed point spread over frames (derived, [Jacobi iteration](supporting_techniques.md#light-transport-and-solver-math)). Bounce methods, including ones that need no temporal lag, are in [light transport alternatives](light_transport_alternatives.md).

## Colour space and range

All RC math runs in linear space. sRGB inputs must be converted before any interpolation, since converting after a hardware bilinear fetch is not equivalent, and the result encoded once at output; a plain power curve in place of the piecewise sRGB curve gave blocky shadows that cut to black, and gamma applied only when sampling gave green ringing ([merging notes](../sources/2026_merging_and_ringing.md#formats-and-color), [sRGB](supporting_techniques.md#formats-and-colour)). McGhee's linearization with gamma 2.2 produced "a much brighter (accurate) result" and made vanilla RC's ringing clearly visible ([jason.today](../sources/2024_mcghee_building_realtime_gi_part2_rc.md#33-srgb-correction-article)); fad linearizes emission with `pow(c, 2.2)`.

RC values exceed 1, so 8-bit cascades clamp and band. White emitters at 1.0 look muted and emission around 5 to 10 looked right, and tone mapping belongs on the result, not on each ray ([merging notes](../sources/2026_merging_and_ringing.md#formats-and-color)). Storage formats are in [cascade layout and merging](cascade_layout_and_merging.md).

## Connections

- **Discrete ordinates.** RC is a discrete-ordinates scheme for the transfer equation whose ordinate count grows with distance, built by merging intervals that any 1D solver can integrate; this is why it transferred directly to solar radiative transfer ([radiative transfer](../sources/2024_osborne_radiance_cascades_radiative_transfer.md), [RTE](supporting_techniques.md#light-transport-and-solver-math), [volumetric and radiative transfer](volumetric_and_radiative_transfer.md)).
- **Structured sampling.** GM Shaders presents RC as a structured alternative to random ray sampling ([GM Shaders](../sources/2024_yaazarai_gmshaders_radiance_cascades.md#part-one-introduction-to-radiance-cascades)). Coppen calls it fully deterministic ([Coppen](../sources/2024_coppen_fundamentals_of_radiance_cascades.md#limitations-and-author-statements)): the same scene gives the same image, and its errors are structured (blur, ringing, aliasing, leaks) rather than noise.
- **Far-field compression.** Distance-dependent resolution is the idea behind multipole expansions: far sources are represented coarsely in position and finely in direction ([glossary](supporting_techniques.md#light-transport-and-solver-math)).
- **The probe-GI lineage.** Irradiance volumes discretized the same 5D function (3D position, 2D direction) with static scenes in 1998; RC is the first scheme in that line with a rule for its resolutions ([non-English overviews](../sources/2025_non_english_rc_overviews.md#liris-gdl-talk-irradiance-volumes--radiance-cascades-19962026), [related probe GI](related_probe_gi.md)).
- **Three derivations, one scaling.** Split RC's equal-error criterion, Reservoir Cascades' alignment lemma and RCPG's Nyquist parallax bound all select `l = 2·K^(1/m)`, which is `K = 4, l = 4` in 3D ([sampling and guiding](rc_for_sampling_and_guiding.md#connections)).
- **Ward's split sphere is the spatial half of the penumbra condition.** Irradiance caching spaces records in proportion to the distance of the nearest surface; RC applies the same rule per distance band ([radiance caches](related_radiance_caches.md#connections)).
- **Probe grids and LPVs are cascades without the angular trade.** DDGI, SDFGI and HDDAGI keep one angular resolution at every level, and LPVs keep the same SH order in every nested grid ([probe GI](related_probe_gi.md#connections), [Godot integration](godot_integration.md#connections)).
- **Engine GI hand-offs are two-level RC merges.** Lumen, daGI2, HSGI and Godot's screen-probe draft all stop a near ray after a few probe sizes and read a coarser level, with the length chosen by hand ([engine GI](related_engine_gi.md#connections)).
- **Sweeps share occluders along lines, RC across footprints.** Both make cost independent of range, and screen-space AO's exponential sample patterns are interval scaling without the rule ([alternatives](light_transport_alternatives.md#connections), [screen-space GI](related_screen_space_gi.md#connections)).
- **HRC makes the extend identity exact in 2D** by giving every ray a partner of the same direction one level up ([holographic RC](holographic_rc.md#connections)).

## Single-frame assessment

Nothing in the theory needs temporal reuse (inference, from the sections above):

- The method is deterministic and noise-free, so a single frame has nothing to denoise. Radiant 2D, PoE2 (which has no TAA because the game is too dynamic, [ExileCon](../sources/2023_sannikov_exilecon_rendering_poe2.md)), Split RC's results and the 2D references with a pass per cascade compute each frame from scratch ([history](history_and_landscape.md)).
- Temporal reuse appears in implementations for other reasons: host limits that merge one cascade per frame (Shadertoy, LegitScript; [history](history_and_landscape.md#first-public-implementations-and-the-shadertoy-lineage)), spreading cost (jason.today's "reduce demand" mode spreads work over two frames), bounce feedback, jitter that hides aliasing behind accumulation, and convergence of screen probes with world intervals (0.1 to 0.5 s with reprojection in the paper's variant). Each is a cost or quality trade, not a requirement of the representation.
- The errors a single frame must live with are the deterministic ones: the minimum penumbra angle, merge parallax (ringing and leaks), aliasing of small lights at upper cascades and blocky interpolation. None of them averages away over frames without jitter, so temporal reuse would not fix them either, only blur them.

What the theory implies for single-frame 3D RC (inference):

- **Scaling:** `K = 4` directions per cascade with `l = 4` intervals (equal error, about 5 cascades per scene) is better supported than `l = 2` (constant penumbra ratios, about 9), by Split RC's tests and the sparse 3D builds; the price is that distant small lights alias more.
- **Cascade 0:** `t0` between the equal-error value and the cell diagonal (about 1.6 to 1.7 spacings at 32 directions), with 32 cascade 0 directions as the smallest count that tested well.
- **Memory:** a dense 3D grid totals under 2× its cascade 0 with ×4 directions, but cascade 0 scales with scene volume; surface and screen probes cost `N·M0`. Removing the stored cascade 0 is the largest saving.
- **Time:** at full-resolution marching the top cascades dominate; mip marching or interval extension is needed to keep them affordable.
- **Lights:** RC alone will not resolve sun and small-light shadows at practical spacings. A single-frame design needs direct light with its own shadows (shadow maps, or rays to lights) and RC for the indirect part, or a variant such as HRC that keeps transverse resolution.
- **Bounces:** a single frame gives one bounce unless the hierarchy is iterated within the frame.

## Open questions

- Which interval scaling minimizes perceived error in 3D? Only Split RC tested `l = 4` against `l = 2` with a published method, and its 2D appendix is the only controlled comparison. Is there a scaling between them, or a per-cascade `l`, that keeps the angular ratio bounded without the drift of `l = 2`?
- Can a 3D lattice make the extend identity exact, as HRC does in 2D, without HRC's `O(N⁴)` memory for an `N³` volume?
- How large is vanilla merging's error in 3D? Osborne's worst case (just over 10% for a tiny opaque source in vacuum) is a 2D figure, and the 3D bilinear fix costs 8× on a rectilinear grid.
- Can interpolation order be raised cheaply (GradientRC's slopes, cubic kernels) to remove blocky patches, and does that interact with the band-limit argument?
- What is the right 3D sky integral for non-equal-area direction maps, and can a prefiltered environment lookup per direction cell replace it exactly?
- How should direct light be split from RC without double counting light that RC also reaches through its intervals? Must emitters that are shadowed separately be removed from the RC scene, or only their direct contribution?
- Can several bounces be computed within one frame from stored hit distances or repeated RC passes at acceptable cost?
- Does supersampling each stored direction (many rays per cone) change the equal-error `t0`, since it removes the aliasing that made shorter intervals preferable?
