# Fundamentals of Radiance Cascades

| | |
|---|---|
| Author | Max Coppen (mxcop) |
| Date | 2024-10-22 |
| Kind | Article (explainer with animations, figures, and code) |
| Link | https://m4xc.dev/articles/fundamental-rc/ |

A 2D ("flatland") explainer of RC. It covers the angular and spatial observations behind the penumbra condition, how they become cascades of probes and intervals, how a cascade is stored in a texture, and how cascades merge into diffuse lighting. Code fragments show interval directions, interval ranges, interval merging, and bilinear merging. It is a good first read; the merge loop below is the most reusable part.

## Contents

- [Introduction](#introduction)
  - [Terms](#terms)
- [Observations](#observations)
  - [Angular observation](#angular-observation)
  - [Spatial observation](#spatial-observation)
  - [Penumbra condition](#penumbra-condition)
  - [Recap](#recap)
- [Exploiting the observations](#exploiting-the-observations)
  - [Angular](#angular)
  - [Spatial](#spatial)
- [Cascades](#cascades)
  - [Cascade hierarchy](#cascade-hierarchy)
  - [Cascade memory](#cascade-memory)
  - [Cascade gathering](#cascade-gathering)
- [Merging](#merging)
  - [Merging intervals](#merging-intervals)
  - [Merging cones](#merging-cones)
  - [Merging spatially](#merging-spatially)
  - [Merging algorithm](#merging-algorithm)
  - [Final pass](#final-pass)
- [Artifacts and fixes](#artifacts-and-fixes)
- [Parameters and values](#parameters-and-values)
- [Limitations and author statements](#limitations-and-author-statements)
- [Unclear in source](#unclear-in-source)
- [Figures and animations](#figures-and-animations)
- [Links found](#links-found)

## Introduction

- RC efficiently represents a radiance field: at any point in an area (usually the screen in 2D), it gives the incoming light.
- The article covers 2D only.

### Terms

- Radiance: light from one direction at one point. The author compares it to a ray.
- Irradiance: light from a subset of directions at one point. The author describes it as light from all directions.
- Irradiance is built from many radiance values.

## Observations

The article rests on two observations: an angular one and a spatial one.

### Angular observation

- A radiance probe has an angular resolution, which is the angle between its evenly spaced rays (Figure A).
- As the probe moves away from a light source, its angular resolution can become insufficient.
- The angle that is enough depends on two quantities:
  - D: distance to the furthest object.
  - w: size of the smallest object.
- The paper (Sannikov) formalizes this as: Δω < w/D
  - Δω: angle between evenly spaced rays.

### Spatial observation

- A penumbra made by a line light and a line occluder can be resolved by interpolating between only 2 probes (Figure B).
- The probe spacing depends on two quantities:
  - D: distance to the closest object.
  - w: size of the smallest object.
- The spacing can grow the further the probe is from all objects.
- The author says the distance term is the inverse of the angular observation.
- Figure C moves the line occluder. The penumbra still grows with distance, whatever the distance between light and occluder. Its sharpness changes.
- The author states RC is notoriously bad at representing very sharp shadows.
- The nearest or furthest object matters, not the light source. A wall is a light source that emits no light, and a light source is a wall that emits light.

### Penumbra condition

- Δp: distance between probes (spatial spacing).
- Δω: angle between rays (angular spacing).
- The required Δω decreases as the required Δp increases, and the reverse. The author calls them inversely proportional.
- The paper's penumbra condition, as the article gives it:

```
Δp <~ D
Δω <~ 1/D
```

- A <~ B means A is less than the output of some function that scales linearly with B.
- w is not in the condition, because it is the same at all points in the scene.
- A smaller w raises both the required angular and the required spatial resolution, because both are needed to resolve the smallest object.

### Recap

- The further from the closest object, the less spatial resolution is needed. Probe spacing can be larger.
- The further from the closest object, the more angular resolution is needed. A probe needs more rays.

## Exploiting the observations

### Angular

- Problem: the rays of a classic probe can hit objects at almost any distance. The penumbra condition needs a narrower distance window.
- Proposed split: divide a circular probe into rings (Figure D). Each ring then hits objects within a narrow distance window.
- The angular resolution can differ from ring to ring.
- The rays of a ring with a limited range are called intervals.
- Rings for more distant objects get more intervals, meaning a smaller angle between rays. Figure E doubles the interval count per ring.
- Doubling the interval count also doubles the length of each ring's distance window. The source says this keeps the gap between intervals roughly equal between rings.
- A whole scene needs many rings.

### Spatial

- Splitting by angle alone does not reduce the ray count. Each probe still casts many rays.
- Each ring is treated as its own probe, which can be moved. From here on, "probe" means ring.
- Rings further out get larger spacing (Figure F). Fewer probes are needed to cover an area.
- The interval lengths in Figure F are wrong on purpose, to make the figure easier to read.
- Probes in different cascades do not connect cleanly. The source says this causes artifacts, mainly ringing.
- Fixes named in the source are a bilinear fix and a parallax fix. Both are out of the article's scope.

## Cascades

- A cascade is a grid of probes where every probe has the same properties: interval count, interval length, and probe spacing.
- Cascades grow outward, with increasing interval count and length.
- Figure G1 shows cascade 0 with a 4x4 probe grid. Figure G2 shows cascade 1 with a 2x2 probe grid.

### Cascade hierarchy

- One cascade covers only a small part of the scene. Several cascades are combined into a hierarchy.
- The usual choice is to halve the probe count along each axis from one cascade to the next, which is 4x fewer probes in 2D.
- By the penumbra condition, spacing and angle are inversely proportional. Doubling the spacing requires halving the angle between intervals.
- Many implementations reduce the angle between intervals by 4x per cascade instead, while keeping the 2x spacing. The author says this is more costly and may give better quality in some cases.

### Cascade memory

- The most common storage is a 2D texture.
- A probe with 16 intervals is a 4x4 block of texels. Each texel holds one direction (Figure H).
- The source derives the direction from the direction index with this code:

```glsl
const int dir_count = 16; /* 4x4 */
const int dir_index = ...;

/* Compute interval direction from direction index */
float angle = 2.0 * PI * ((float(dir_index) + 0.5) / float(dir_count));
vec2 dir    = vec2(cos(angle), sin(angle));
```

- Instead of one texture per probe, a whole cascade is stored in one texture, with its probes packed together (Figure I).
- The author also describes a "direction first" layout. All intervals with the same direction are stored together in blocks. The author says this improves data locality during merging. No index math is given.
- With a 2x angle reduction per cascade, the probe count drops 4x and the intervals per probe rise 2x. Each cascade then has half the total intervals of the one before it. The total approaches 2x the interval count of cascade 0 as cascades are added.
- With a 4x angle reduction per cascade, every cascade has the same total interval count. The total grows linearly with the number of cascades.
- The author recommends the 4x method, because the interval count stays equal and it is simpler to work with in practice.

### Cascade gathering

- Gathering loops over every texel of a cascade's texture. For each texel, it computes the texel's direction and casts its interval into the scene.
- Steps from the source, in order:
  1. Local texel coordinate inside its probe: `dir_coord = texel_coord % probe_size`.
  2. Direction index, row by row: `dir_index = dir_coord.x + dir_coord.y * probe_size.x`.
  3. Direction count `dir_count = probe_size.x * probe_size.y`, then the direction formula from Cascade memory.
  4. Interval endpoints: `interval_start = probe_pos + dir * start_time` and `interval_end = probe_pos + dir * end_time`.
  5. `radiance = cast_interval(interval_start, interval_end)`.
- The source does not say how `probe_pos` is found from the texel coordinate.
- `cast_interval` may use any ray casting method. It must return the radiance from start to end.
- The visibility term is stored in the alpha channel. The article says it is set during gathering: 1.0 if the interval hit nothing, 0.0 if it hit something. The gathering code shown returns only a vec3 radiance.
- Start and end times depend on the cascade and the branching. For 4x branching, which the author recommends, the source uses:

```glsl
float interval_scale(int cascade_index) {
    if (cascade_index <= 0) return 0.0;
    return float(1 << (2 * cascade_index));
}

vec2 interval_range(int cascade_index, float base_length) {
    return base_length * vec2(interval_scale(cascade_index), interval_scale(cascade_index + 1));
}
```

- `base_length` is the value the prose gives as the length for cascade 0 intervals.
- Derived from the code above (not stated in the source):
  - Cascade 0 covers [0, 4 × base_length], so its length is 4 × base_length.
  - Cascade 1 covers [4 × base_length, 16 × base_length].
  - Cascade i ≥ 1 covers [4^i × base_length, 4^(i+1) × base_length], so its length is 3 × 4^i × base_length.
  - Each cascade starts where the previous one ends.
- The prose and the code disagree on cascade 0's length (base_length in the prose, 4 × base_length from the code). The source does not say which is intended.

## Merging

The goal is the diffuse irradiance of the scene, also called fluence in 2D. This is the sum of the radiance from all directions at a point.

### Merging intervals

- Intervals earlier in a chain can occlude intervals further down the chain (Figure J).
- Merge code from the source:

```glsl
vec4 merge_intervals(vec4 near, vec4 far) {
    const vec3 radiance = near.rgb + (far.rgb * near.a);
    return vec4(radiance, near.a * far.a);
}
```

- Far radiance is blocked by the near interval's visibility.
- Visibility terms are multiplied, so a hit carries down the chain (1.0 × 0.0 = 0.0).

### Merging cones

- Merging each direction through every cascade would be too costly.
- Instead, each cascade is merged into the one below it, from the top down.
- Diffuse lighting needs little directional detail, so all scene radiance is merged into cascade 0. Cascade 0 has the lowest angular resolution.
- With a branch factor such as 4x, each cascade merges 4 intervals of the cascade above into 1 interval. Repeating this over all cascades captures the radiance of a cone (Figure K).

### Merging spatially

- The next cascade, N+1, is the one above the current cascade N. It has lower spatial resolution and higher angular resolution.
- Merging with only the nearest probe of N+1 gives a visible grid pattern, which shows the probes themselves (Figure L). The penumbrae are blocky.
- Bilinear merging uses the nearest 4 probes of N+1. Probes closer to the destination get higher weights. The author describes this as blurring the blocky probes with their neighbours.
- Terms: the green probes are "bilinear probes", and the blue probe is the "destination probe" (Figures M and N).
- The author notes that the weights shown in Figure M are wrong. They should always add up to 1.0.
- With bilinear merging the penumbrae are smooth (Figure N).

### Merging algorithm

- Merge top down, from the lowest spatial resolution to the highest.
- The top cascade has nothing above it. The source says it can be skipped or merged with a skybox, with no further detail.
- Each other cascade N merges with the cascade above it, N+1. The source writes this as N_{i+1} → N_i.

Step 1: find the 4 bilinear probes of N+1 and their weights.

```glsl
vec4 bilinear_weights(vec2 ratio) {
    return vec4(
        (1.0 - ratio.x) * (1.0 - ratio.y),
        ratio.x * (1.0 - ratio.y),
        (1.0 - ratio.x) * ratio.y,
        ratio.x * ratio.y
    );
}
```

```glsl
void bilinear_samples(vec2 dest_center, vec2 bilinear_size, out vec4 weights, out ivec2 base_index) {
    const vec2 base_coord = (dest_center / bilinear_size) - vec2(0.5, 0.5);
    const vec2 ratio = fract(base_coord);
    weights = bilinear_weights(ratio);
    base_index = ivec2(floor(base_coord));
}
```

- Inputs as the source describes them: `dest_center` is the center of the destination probe in pixels, and `bilinear_size` is the size of a bilinear probe in pixels. See Unclear in source.
- `base_index` is the top-left bilinear probe. The other three are `base_index + bilinear_offset(b)`, where offset 0 is (0,0), 1 is (1,0), 2 is (0,1), and 3 is (1,1). The weights use the same order.

Step 2: nested loops.

- Outer loop `d` = 0..3: the 4 directions of N+1 that go with one direction of N.
- Inner loop `b` = 0..3: the 4 bilinear probes.
- Index math from the source (comments removed):

```glsl
const ivec2 base_offset = bilinear_offset(b);
const ivec2 bilinear_index = base_index + base_offset;
const int base_dir_index = dir_index * 4;
const int bilinear_dir_index = base_dir_index + d;
const ivec2 bilinear_dir_coord = ivec2(
    bilinear_dir_index % bilinear_size.x,
    bilinear_dir_index / bilinear_size.x
);
const ivec2 bilinear_texel = bilinear_index * bilinear_size + bilinear_dir_coord;
```

- In the inner loop, the N+1 interval at `bilinear_texel` is merged with the destination interval, then weighted: `radiance += merge_intervals(destination_interval, bilinear_interval) * weights[b]`.
- After the inner loop, the result is added as `merged += radiance / 4.0`.
- The text says each of the 4 bilinear probes contributes 4 intervals. With 4x branching, that is 16 interval fetches per destination interval.
- The source does not explain the division by 4.0. The text only says "for each extra N+1 interval".
- The index math implies that each N+1 probe is a block of `bilinear_size` texels, with probes laid out in 2D.
- Figure O is drawn with 2x branching instead of 4x, to keep it readable. Its green intervals are colored by their bilinear weight.
- After every cascade has been merged, cascade 0 holds the result.

### Final pass

- For each pixel, bilinearly interpolate between the 4 nearest cascade 0 probes.
- Sum the radiance from the intervals (cones) of those probes. The source gives no code for this step.
- Figure P is the final result. Its credit is Fad's Shadertoy.

## Artifacts and fixes

| Artifact | Cause as stated | Fix as stated |
|---|---|---|
| Ringing | Visible disconnect between probes of different cascades | A "bilinear fix" and a "parallax fix" are named but not described. Out of scope. |
| Grid pattern (blocky penumbrae) | Merging with only the nearest probe of N+1 (Figure L) | Bilinear merging over the 4 nearest probes of N+1 (Figure N) |
| Poor sharp shadows | Not explained beyond the penumbra condition | None stated |

## Parameters and values

| Item | Value in source | Notes |
|---|---|---|
| Interval count per ring, angular split | 2x per ring | Example in Figure E |
| Probe count between cascades | Halved along each axis | "Most of the time" |
| Angle between intervals between cascades | Halved (2x spacing case) or quartered (4x case) | 4x recommended |
| Branch factor | 4 (recommended). 2 in Figure O only. | |
| Bilinear probes per merge | 4 | |
| Directions of N+1 per direction of N | 4 | `dir_index * 4` |
| Intervals per destination interval | 16 with 4x branching | 4 probes × 4 directions |
| Example direction count | 16 (4x4 texels) | Figure H |
| Cascade 0 probe grid example | 4x4 | Figure G1 |
| Cascade 1 probe grid example | 2x2 | Figure G2 |
| Number of cascades | Not given | |
| `base_length` | Symbol only, no value | |
| Probe spacing (pixels or units) | Not given | |
| Texture format and size | Not given beyond "2D texture" | |
| Performance, hardware, resolution | Not given | Author states real-time only |
| Ray casting method | Free choice | `cast_interval` |

## Limitations and author statements

- RC is notoriously bad at representing very sharp shadows (Figure C).
- Ringing comes from the disconnect between cascades. Fixes are out of scope.
- The merge is for diffuse lighting. The author says directional resolution is not important for diffuse.
- The weights in Figure M are wrong, according to the author's own note.
- The interval lengths in Figure F are not to scale.
- 4x branching costs more but may give higher quality in some cases.
- The author says the method extends to 3D. No details are given.
- The author says the method is fully deterministic.

## Unclear in source

- `probe_pos`: how it is derived from the texel coordinate.
- `destination_interval` and `textureFetch` are not defined. The code does not show where `merged` is written.
- `bilinear_size` is described as the size of a bilinear probe in pixels. The index math uses the same name as the direction-texel width (`% bilinear_size.x`, `/ bilinear_size.x`, and `* bilinear_size` for the texel origin). The two meanings are not reconciled.
- `dest_center`: the coordinate space is not defined (world, screen, or texel).
- The division by 4.0 in the merge loop is not explained.
- `merge_intervals(...) * weights[b]` also multiplies the alpha (visibility) by the weight. The source does not discuss this.
- Cascade 0's interval length: prose and code disagree (see Cascade gathering).
- The symbol D means the furthest object in the angular observation and the closest object in the spatial observation. The penumbra condition uses one D for both and does not separate them.
- The gathering code writes only radiance. The alpha (visibility) write is described in prose but not shown.
- The "direction first" layout has no index math and no exact block layout.
- The final pass has no code. It is unclear whether it uses the same bilinear sampling.
- It is unclear whether the bilinear merging described here is the same as the "bilinear fix" named for ringing.
- The top cascade's skybox option has no detail.

## Figures and animations

The 8 animations are HTML video elements. Their content was not transcribed. Only the captions are recorded.

Base URLs: videos at https://m4xc.dev/anim/articles/fundamental-rc/ and images at https://m4xc.dev/img/articles/fundamental-rc/

| Figure | File | Caption |
|---|---|---|
| Intro (no number) | showcase.mp4 | Diffuse global illumination in flatland |
| A | angular-anim.mp4 | Circular object with a radiance probe |
| B | spatial-anim.mp4 | Penumbra created by line light and line occluder |
| C | penumbra-anim.mp4 | Moving the line occluder around |
| D | splitting-anim.mp4 | Probe being split into "rings" |
| E | inc-angular-split.png | Increasing angular resolution for more distant rings |
| F | spatial-exploit-anim.mp4 | Increasing probe/ring spacing |
| G1 | cascade0.png | Cascade 0, with 4x4 probes |
| G2 | cascade1.png | Cascade 1, with 2x2 probes |
| H | probe-memory-anim.mp4 | 4x4 probe in texture memory |
| I | cascade-memory.png | Cascade in texture memory |
| J | interval-merge-anim.mp4 | Green interval should occlude red interval |
| K | interval-cone.png | Cone made out of intervals |
| L | nearest-interp.png | Merging with nearest probe only |
| M | bilinear-probes.png | Merging with 4 bilinear probes |
| N | bilinear-interp.png | Smooth penumbrae using bilinear interpolation |
| O | full-merge.png | Merging for 1 interval (in blue) |
| P | final-result.png | Final result (credit: Fad's Shadertoy) |

## Links found

- Alexander Sannikov, Radiance Cascades paper and repository | https://github.com/Raikiri/RadianceCascadesPaper | Source of the angular condition Δω < w/D and the penumbra condition the article cites.
- XorDev and Yaazarai, Radiance Cascades part 1 | https://mini.gmshaders.com/p/radiance-cascades | Article giving another explanation, per the author.
- XorDev and Yaazarai, Radiance Cascades part 2 | https://mini.gmshaders.com/p/radiance-cascades2 | Part 2 of the same series.
- SimonDev, video | https://youtu.be/3so7xdZHKxw | Video explanation of RC.
- Christopher M. J. Osborne, arXiv 2408.14425 | https://arxiv.org/abs/2408.14425 | Paper on the bilinear fix for RC.
- Jason, blog post | https://jason.today/rc | Blog post on RC.
- Fad, Shadertoy mtlBzX | https://www.shadertoy.com/view/mtlBzX | RC implementation. Source of the final result image (Figure P).
- Surfel Maintenance for Global Illumination (2025-01-22) | https://m4xc.dev/articles/surfel-maintenance/ | The author's article on surfel probe maintenance, used by Surfel RC.
