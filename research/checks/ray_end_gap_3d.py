"""Ray-end gap of vanilla 3D RC at the equal-error t0, the counterpart of HRC's minimum light size.

Cascade 0: 32 directions, cell width sqrt(4 pi / 32), t0 = spacing / width. K = 4 directions per parent
halve the cell width per cascade. The gap at the end of cascade n is t_end(n) * width(n); a light
resolves above one gap and about two by the Nyquist limit. Lengths are in cascade 0 spacings.
"""
import math

width0 = math.sqrt(4 * math.pi / 32)
t0 = 1 / width0
assert round(t0, 2) == 1.60


def gaps(l, cascades=6):
    return [t0 * l ** n * width0 / 2 ** n for n in range(cascades)]


# l = 2: the gap stays one cascade 0 spacing at every cascade's end.
assert all(math.isclose(g, 1) for g in gaps(2))

# l = 4: the gap is the cascade's own spacing, 2^n, which is sqrt(t / t0) at distance t = t0 * 4^n.
for n, g in enumerate(gaps(4)):
    assert math.isclose(g, 2 ** n) and math.isclose(g, math.sqrt(4 ** n))

# Two gaps reach HRC's 8 base probes at the end of cascade 2, 16 * t0 away.
first = next(n for n, g in enumerate(gaps(4)) if 2 * g >= 8)
assert first == 2 and 4 ** first == 16
