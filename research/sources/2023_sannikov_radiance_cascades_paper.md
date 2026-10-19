# Radiance Cascades: A Novel Approach to Calculating Global Illumination

| | |
|---|---|
| Author | Alexander Sannikov (Grinding Gear Games) |
| Date | 2023, work-in-progress preprint in the JCGT template, never formally published |
| Kind | Paper |
| Link | https://github.com/Raikiri/RadianceCascadesPaper (`RadianceCascades.tex`, PDF in `out_latexmk2/RadianceCascades.pdf`) |

The founding paper. It defines the penumbra condition, radiance intervals, the merge rule, the cascade scaling laws, and the memory math for flatland, 3D grids, and surfaces. It also describes five early implementations, including the one shipped in Path of Exile 2. The math is loose on purpose: the paper gives asymptotic scaling only and leaves all base parameters to tuning.

## Contents

- [Penumbra condition](#penumbra-condition)
- [Radiance intervals](#radiance-intervals)
  - [Merge](#merge)
  - [Shift and extend](#shift-and-extend)
- [Cascade scaling](#cascade-scaling)
  - [Memory by dimensionality](#memory-by-dimensionality)
- [Using the cascades](#using-the-cascades)
- [Cost analysis (flatland)](#cost-analysis-flatland)
- [Failure modes and tuning](#failure-modes-and-tuning)
- [Early implementations](#early-implementations)
- [Limitations stated by the author](#limitations-stated-by-the-author)
- [Context from the related-work section](#context-from-the-related-work-section)

## Penumbra condition

Take the smallest light in the scene, of size `w`, at distance `d` from an occluder edge. The penumbra opens at angle `α = 2·atan(w / 2d) ≈ w/d`. At distance `D` from the light (assuming `D ≫ d`), the penumbra is `α·D` wide, and the light covers an angle of `w/D`. To resolve both:

- spatial step `Δp < α·D`, so `Δp` may grow linearly with `D`;
- angular step `Δω < w/D`, so `Δω` must shrink as `1/D`.

Near an object, light needs dense positions and few directions; far away, it needs sparse positions and many directions. The **penumbra hypothesis** assumes that a discretization meeting this condition represents any radiance field well, because a field is a superposition of penumbras. It fails only for vanishingly small lights very close to occluders. The two extremes already used in games fit it: ambient occlusion (`Δp → 0`, no directions) and environment maps (no positions, `Δω → 0`).

## Radiance intervals

`L[a,b](p, ω)` is the radiance arriving at `p` from direction `ω` that comes only from points at distance `t ∈ [a, b]` along the ray `p + t·ω`. With a ray-cast function `R(p, ω)` returning the nearest opaque hit:

- `L[a,b](p, ω) = L_out(R(p + a·ω, ω), −ω)` if that hit is closer than `b`, otherwise `0`.
- Volumetric form: `L[a,b](p, ω) = ∫ₐᵇ exp(−∫ₐˣ σ(p + y·ω) dy) · L_emi(p + x·ω, −ω) dx`.

The matching transparency interval `β[a,b](p, ω)` is `0` if something opaque lies in `[a, b]`, else `1` (volumetric: the transmittance over the segment). A probe stores RGB radiance plus `β` in alpha.

### Merge

Adjacent intervals combine like front-to-back alpha blending:

```
L[a,c] = L[a,b] + β[a,b] · L[b,c]
β[a,c] = β[a,b] · β[b,c]
```

Full radiance is the interval `[0, ∞)`, so radiance is rebuilt by merging intervals `[t₀=0, t₁], [t₁, t₂], …`. Merging back-to-front or front-to-back gives the same result.

### Shift and extend

Shifting: `L[a+x, b+x](p, ω) = L[a,b](p + x·ω, ω)`, the same segment described from a different start point.

Extending: with `L[a, a+x]` known everywhere, `L[a, a+2x](p) = L[a, a+x](p) + β[a, a+x](p) · L[a, a+x](p + x·ω)`. So a cascade can raymarch a short piece of its interval and double it repeatedly by reading itself at shifted positions, each doubling costing O(1). This works only on regular grids (flatland, world-space 3D) and not for screen-space probes, which each sit at their own depth.

## Cascade scaling

A cascade is a uniform grid of probes that stores one interval `[a, b]`, with `Δp ≲ a` and `Δω ≲ 1/b`. Cascade `i` stores `[tᵢ, tᵢ₊₁]` with `t₀ = 0` and `tᵢ → ∞`. Doubling the probe spacing per cascade, like mipmaps, forces the rest:

```
Δp ∝ 2^i      Δω ∝ 1/2^i      tᵢ ∝ 2^i
```

Each cascade has twice the probe spacing, half the angular step, and an interval twice as long as the one before. Probe storage can be cubemaps, octahedral maps, or spherical harmonics; only the asymptotic texel count matters.

### Memory by dimensionality

| Domain | Probes in cascade `i` | Directions per probe | Memory of cascade `i` | Total for N cascades |
|---|---|---|---|---|
| Flatland (2D position, 1D angle) | `∝ 1/4^i` | `∝ 2^i` | `M₀ / 2^i` | `< 2·M₀` |
| 3D grid (3D position, 2D angle) | `∝ 1/8^i` | `∝ 4^i` | `M₀ / 2^i` | `< 2·M₀` |
| Surface (2D position, 2D angle) | `∝ 1/4^i` | `∝ 4^i` | `M₀` | `N·M₀` |

Example flatland atlas: cascade 0 has 32×32 probes with 8×8 angular texels each, cascade 1 has 16×16 probes with 8×16 texels each, and the whole atlas is twice the width of cascade 0. Example surface atlas: cascade 0 has 16×16 probes of 8×8 texels, cascade 1 has 8×8 probes of 16×16 texels; the atlas grows linearly with the cascade count. For full 3D, cascade 0 alone is usually the deal breaker, while for surfaces cascade 0 is cheap.

## Using the cascades

**Diffuse.** Merge cascades from `N−1` down to 0. Projecting cascade `i+1` onto cascade `i` averages 2 (flatland) or 4 (3D directions) texels of `i+1` and merges the result into one texel of `i`. Cascade 0 then holds full radiance averaged over each of its few direction cones, which is enough because the cosine-weighted diffuse BRDF has low angular frequency.

**Specular.** A glossy lobe is a cone around the reflected view vector, and RC answers cone queries in O(N). The narrowest cone comes from querying each cascade separately in that direction and merging the results, which gives the angular step of the top cascade. The widest cone is one lookup in the fully merged cascade 0. Cones in between query cascades `0..K` individually and merge them with one lookup into the merged cascade `K+1`.

## Cost analysis (flatland)

Cascade 0 has `P₀` probes and `Q₀` directions. Cascade 1 has `P₀/4` probes and `2Q₀` directions, so half the intervals. Interpolating cascade 1 to every cascade 0 probe and merging builds `2·P₀·Q₀` full-length rays from `1.5·P₀·Q₀` stored intervals. Each added cascade costs half the previous one and doubles the number of effective rays:

```
rays(N) = 2^N · rays(0)
cost(N) = (1 + 1/2 + … + 1/2^N) · cost(0) < 2 · cost(0)
```

The cascade count is capped near `log(P₀)`, and the constructed rays are only accurate while the penumbra hypothesis holds. Probe data in a cascade that meets the penumbra condition is band-limited, so plain linear interpolation in space and direction reconstructs it without bilateral filtering or disocclusion handling. Classic probes need those fixes because they store full radiance rather than intervals.

## Failure modes and tuning

- Point lights that are too small and penumbras that are too sharp break the hypothesis.
- The base parameters (cascade 0 probe spacing, angular step, and interval length `t₀`) decide quality and speed and need hand tuning; the paper gives no rule for them. The LaTeX source (`rcpaper/RadianceCascades.tex`, commit 9d1fd29) says so directly: the work "only provides an asymptotic scaling analysis, completely omitting considerations behind choosing any actual initial values", which "dramatically affect both accuracy and performance" and take "some amount of fiddling" (line 673). Anything satisfying the scaling condition makes a valid cascade sequence, and storage falls directly as the spatial and angular steps grow (line 379); cascade 0's interval is an arbitrary parameter the others scale from (line 539). Radiant 2D raised angular resolution 4× per cascade instead of 2× (line 551).
- For 3D the source gives scaling only: `P_i ~ (1/2^i)³` probes, `Q_i ~ (2^i)²` texels and `M_i ~ M_0/2^i`, so `Σ M_i = 2·M_0` (lines 431-435), and the hierarchy takes as much memory as its cascade 0 while that storage scales with the scene size cubed (line 614). It gives no MB figures or timings for 3D.
- A cascade 0 interval that is too long leaves visible gaps between the interval segments of different cascades; shortening it until the segments connect gives a continuous result.
- Quality degrades gracefully: missing resolution blurs shadows as if they came from area lights.

## Early implementations

| Implementation | What it is | Numbers |
|---|---|---|
| Radiant 2D | First 2D proof of concept, per-pixel GI | ~30 ms on an RTX 3060 depending on fidelity; 2, 102, and 1002 lights all cost ~12 ms |
| Path of Exile 2 | Screen-space, flatland-like hierarchy filled by screen-space raymarching | ~3 ms on a GTX 1050 |
| Radiance 3D | World-space 3D probe grid in a volume texture, filled from voxels or from screen-space data | Storage is the limit, not time |
| Direct radiance field renderer | Path-traced volume baked into surface cascades on one quad and viewed directly | < 0.5 ms on an RTX 3060 |
| Screen probes with world-space intervals | Probes on the depth buffer, world-space SDF raymarching | 30–50 ms on an RTX 3060, 0.1–0.5 s to converge with reprojection |

Details worth keeping:

- Radiant 2D raymarches only `[512, 544]` of a `[512, 1024]` interval and reaches the full range by repeated interval extension.
- Radiant 2D scales angular resolution by 4× per cascade, not 2×, so every cascade uses the same memory, like surface cascades. The author found a better quality-to-cost ratio this way without knowing why at the time; later papers confirm it (see [2026_freeman_split_radiance_cascades.md](2026_freeman_split_radiance_cascades.md)).
- PoE2 marches 4 rays at once in screen space and stores occlusion as a 128-bit bitmask per cascade texel, the equivalent of 128 binary occlusion rays. It works well with normal maps and can feed specular.
- The world-space interval variant places octahedral probes of `2^i × 2^i` texels every `2^i` pixels on the depth buffer. Spatial interpolation is bilateral (only neighbors with similar depth count), directional interpolation is bilinear. Any ray-segment query works for filling intervals; the demo used analytic SDFs. Each cascade reprojects from the last frame for temporal accumulation. It sees off-screen and depth-occluded light but runs one to two orders of magnitude slower than PoE2's approach.
- World-space cascades can be sampled anywhere in space, which participating media and atmospheric scattering need; screen-space cascades can be sampled only on the G-buffer surface.

## Limitations stated by the author

- The constant cost is high: a 3D cascade 0 grid costs about as much as voxelizing the scene, and a detailed screen-space cascade 0 alone can take milliseconds.
- Screen-space artifacts (no off-screen lights, no hidden occluders, nothing behind the depth buffer) come from tracing screen-space data, not from storing cascades in screen space.
- Hardware ray tracing could fill world-space intervals with the same asymptotic scaling but an order of magnitude higher constant cost.

## Context from the related-work section

- Probe-based GI always picks some trade-off between many low-resolution probes and few high-resolution ones; finding the right point was the main motivation.
- Ambient occlusion and environment maps are the near-field and far-field ends of one spectrum, and RC fills the levels in between. Lumen and GI-1.0 use four such levels (AO, screen probes, world radiance cache, environment).
- The author's earlier PoE1 GI (2017, shipped 2018), "hierarchical screen-space variance-based GI", used horizon-based screen-space sectors, screen-space mipmaps, and a Chebyshev occlusion test on two depth moments. It resembles "Horizon-Based Indirect Lighting" by Benoît Mayaux (2018; [notes](2018_mayaux_horizon_based_indirect_lighting.md)), which was written for a different studio's game. PoE1 also used hierarchical screen-space shadow cascades that compute blurry penumbra parts at low resolution, which inspired RC.
- Voxel cone tracing's idea of averaging radiance through mipmaps fed the first PoE GI.
