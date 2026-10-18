# Octahedral mapping of directions

| | |
|---|---|
| Authors | Zina H. Cigolle, Sam Donow, Daniel Evangelakos, Michael Mara, Morgan McGuire, Quirin Meyer |
| Date | 2014 |
| Kind | Paper, JCGT 3(2) "A Survey of Efficient Representations for Independent Unit Vectors" |
| Link | https://jcgt.org/published/0003/02/01/ |

The octahedral map stores a direction as a point in `[−1, 1]²`. 3D RC uses it for probe direction layouts (tauray, Love and Deepspace) and for irradiance tiles (Split RC, DDGI). The paper finds it the best general method: fast, close to uniform, and near the lowest error at every bit size.

## Encode and decode

```glsl
vec2 sign_not_zero(vec2 v) { return vec2(v.x >= 0.0 ? 1.0 : -1.0, v.y >= 0.0 ? 1.0 : -1.0); }

vec2 oct_encode(vec3 v) {
    vec2 p = v.xy / (abs(v.x) + abs(v.y) + abs(v.z));
    return v.z <= 0.0 ? (1.0 - abs(p.yx)) * sign_not_zero(p) : p;
}

vec3 oct_decode(vec2 e) {
    vec3 v = vec3(e, 1.0 - abs(e.x) - abs(e.y));
    if (v.z < 0.0) v.xy = (1.0 - abs(v.yx)) * sign_not_zero(v.xy);
    return normalize(v);
}
```

`sign()` returns 0 for 0, which broke the first published code at the square's edges; `sign_not_zero` fixes it. The hemisphere-only variant ("hemi-oct") maps `p = v.xy/(|x| + |y| + z)` to `(p.x + p.y, p.x − p.y)` and has lower error for the same bits.

Error: 16 bits (two 8-bit snorms) give 0.34° mean and 0.94° max; 24 bits give 0.02° mean. A "precise" encode that tries the four floor/ceil roundings and keeps the best cuts the maximum by about a third.

## Texel grids and filtering

A probe's `N×N` texel `t` has direction `oct_decode((t + 0.5)/N·2 − 1)`. The paper does not cover filtering: the square's edges wrap in a folded way, not as a simple modulo, so hardware bilinear filtering needs a border. RTXGI's scheme for a tile of `T = N + 2` texels with a 1-texel border:

- An edge texel copies the interior texel next to it on the same side, mirrored along the edge: top or bottom row texel `x` reads interior column `T − 1 − x`; left or right column texel `y` reads interior row `T − 1 − y`.
- A corner texel copies the diagonally opposite interior corner (`x = 0` reads `x = N`, `x = T − 1` reads `x = 1`, the same for `y`).
- Write the interior first, then a barrier, then the border.
