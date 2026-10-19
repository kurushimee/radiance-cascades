"""Bin shift of a reprojected parent lookup at Split RC's 3D scaling (K = 4, l = 4) and the equal-error t0.

A parent probe at offset o from a child sees the child's ray end, at the child's interval end t, up to
|o| / t radians from the child's direction, counted here in parent cell widths. Children sit at 1/4 and
3/4 of a parent cell on each axis, so the eight parents are 0.43 to 1.30 parent spacings away.
"""
import itertools
import math

width0 = math.sqrt(4 * math.pi / 32)
t0 = 1 / width0  # equal error: t0 * width0 is one cascade 0 spacing


def shifts(n):
    spacing = 2 ** n
    t_end = t0 * 4 ** n
    parent_width = width0 / 2 ** (n + 1)
    offsets = [math.sqrt(sum((f * 2 * spacing) ** 2 for f in c)) for c in itertools.product((0.25, 0.75), repeat=3)]
    return sorted(o / t_end / parent_width for o in offsets)


first = shifts(0)
for n in range(1, 6):
    assert all(math.isclose(a, b) for a, b in zip(shifts(n), first))
assert round(first[0], 2) == 1.73 and round(first[-1], 2) == 5.20
