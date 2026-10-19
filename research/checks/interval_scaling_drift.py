"""Per-cascade drift of the penumbra ratios for spacing x2, K directions per parent and interval scale l.

m is the number of direction dimensions (1 in flatland, 2 in 3D and for screen or surface probes).
"""
import itertools
import math


def angular(k, l, m):
    return l / k ** (1 / m)


def gap_over_spacing(k, l, m):
    return l / (2 * k ** (1 / m))


# The "Two criteria for interval scaling" table in core_theory.md: (m, K, l, spatial, angular, gap/spacing).
table = [
    (1, 2, 2, 1, 1, 0.5),
    (1, 4, 4, 0.5, 1, 0.5),
    (1, 2, 4, 0.5, 2, 1),
    (2, 4, 2, 1, 1, 0.5),
    (2, 4, 4, 0.5, 2, 1),
    (2, 8, 4, 0.5, 1.41, 0.71),
    (2, 4, 2, 1, 1, 0.5),
    (2, 4, 4, 0.5, 2, 1),
]
for m, k, l, spatial, ang, gap in table:
    assert math.isclose(2 / l, spatial)
    assert round(angular(k, l, m), 2) == ang
    assert round(gap_over_spacing(k, l, m), 2) == gap

# The two multipliers differ by the spacing factor alone, so no l holds both at 1.
for m, k, l in itertools.product((1, 2), (2, 4, 8), (2, 3, 4, 6, 8)):
    assert math.isclose(gap_over_spacing(k, l, m) / angular(k, l, m), 0.5)

# Per-cascade l_n: after n cascades gap/spacing is prod(l_i) / (2 K^(1/m))^n, bounded only when the
# running product of l_i tracks (2 K^(1/m))^n; then the angular ratio is that times 2^n and grows.
k, m = 4, 2
target = 2 * k ** (1 / m)
alternating = [target * 1.5, target / 1.5] * 5
gap = angle = 1.0
for n, l in enumerate(alternating, 1):
    gap *= gap_over_spacing(k, l, m)
    angle *= angular(k, l, m)
    assert 1 / 1.5 - 1e-9 <= gap <= 1.5 + 1e-9
    assert math.isclose(angle, gap * 2 ** n)
