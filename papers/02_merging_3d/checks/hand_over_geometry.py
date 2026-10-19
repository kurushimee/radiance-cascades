"""Geometry of one hand-over in a 3D dense grid: K = 4, l = 4, cell-centred probes, spacing 2**c, cascade c's interval
ending at t0*4**c, where the parent's interval starts.

A lower probe sits at 1/4 or 3/4 of its upper cell on each axis, so its eight trilinear parents lie at offsets of
0.25 or 0.75 upper spacings per axis, with weights 0.75 and 0.25; every parity class shares these numbers.
"""
import itertools
import math

import numpy as np

T0 = math.sqrt(32 / (4 * math.pi))


def corners():
    """Offsets q - p of the eight parents in upper spacings, and their trilinear weights."""
    return [(np.array(c) - 0.25, np.prod([0.25 if ci else 0.75 for ci in c]))
            for c in itertools.product((0, 1), repeat=3)]


def interval(c, t0=T0):
    return (0.0 if c == 0 else t0 * 4.0 ** (c - 1)), t0 * 4.0 ** c


def directions(count=200_000):
    """Evenly spread unit vectors (Fibonacci lattice)."""
    i = np.arange(count) + 0.5
    z = 1 - 2 * i / count
    phi = math.pi * (3 - math.sqrt(5)) * i
    s = np.sqrt(1 - z * z)
    return np.stack([s * np.cos(phi), s * np.sin(phi), z], -1)


assert math.isclose(sum(w for _, w in corners()), 1.0)
# Trilinear weights reproduce linear functions, so the weighted parent offsets cancel.
assert np.allclose(sum(w * offset for offset, w in corners()), 0.0)
distances = sorted({round(float(np.linalg.norm(offset)), 3) for offset, _ in corners()})
assert distances == [0.433, 0.829, 1.09, 1.299]

# Parent-side hit-distance test: a parent's stored hit lies at least t_end from it, and the test drops the parent
# only when that hit falls short of the lower probe's distance less 0.5. It can fire only for parents farther than
# t_end + 0.5 from the lower probe: at t0 = 1.60 a 10/64 share of the weight on cascade 0, none above.
def fireable(c, t0=T0, tolerance=0.5):
    h = 2.0 ** (c + 1)
    return sum(w for offset, w in corners() if np.linalg.norm(offset) * h > interval(c, t0)[1] + tolerance)


assert fireable(0) == 10 / 64 and fireable(1) == 0 and fireable(2) == 0
# Cascade c can fire at all only while t0 < (0.75*sqrt(3)*2**(c+1) - 0.5) / 4**c.
thresholds = [(0.75 * math.sqrt(3) * 2 ** (c + 1) - 0.5) / 4 ** c for c in range(3)]
assert [round(t, 2) for t in thresholds] == [2.1, 1.17, 0.62]
for c, threshold in enumerate(thresholds):
    assert fireable(c, threshold * 0.99) > 0 and fireable(c, threshold * 1.01) == 0

# Sphere fix: the lower ray ends where it leaves the sphere of radius t_end around the parent, and the parent is read
# toward that exit. Every ray from t_start has a forward exit only when t_end - t_start >= 0.75*sqrt(3) upper spacings
# (2.60 * 2**c); at t0 = 1.60 that fails on cascades 0 and 1. The share of weight and directions with an exit, and the
# mean angle between the read direction and the ray, in parent bins of width sqrt(4*pi/M_{c+1}):
w_all = directions()


def sphere(c, t0=T0):
    t_start, t_end = interval(c, t0)
    h = 2.0 ** (c + 1)
    width = math.sqrt(4 * math.pi / (32 * 4 ** (c + 1)))
    defined = bend = 0.0
    for offset, weight in corners():
        away = -offset * h
        b = w_all @ away
        disc = b * b - away @ away + t_end ** 2
        exit_ = np.where(disc >= 0, -b + np.sqrt(np.maximum(disc, 0)), -np.inf)
        ok = exit_ >= t_start
        read = w_all[ok] * exit_[ok, None] + away
        cos = np.sum(read * w_all[ok], 1) / t_end
        defined += weight * ok.mean()
        bend += weight * np.arccos(np.clip(cos, -1, 1)).sum() / len(w_all)
    return defined, bend / defined / width


needed = [0.75 * math.sqrt(3) * 2 ** (c + 1) for c in range(3)]
lengths = [interval(c)[1] - interval(c)[0] for c in range(3)]
assert [round(x, 2) for x in needed] == [2.6, 5.2, 10.39] and [round(x, 2) for x in lengths] == [1.6, 4.79, 19.15]
shares, bends = zip(*(sphere(c) for c in range(3)))
assert [round(x, 3) for x in shares] == [0.6, 0.997, 1.0]
assert [round(x, 1) for x in bends] == [1.8, 2.3, 2.2]
# The nearest parent alone bends the read by up to asin(0.433 * 2 / t_end) on cascade 0.
assert round(math.degrees(math.asin(0.25 * math.sqrt(3) * 2 / T0)), 1) == 32.9

# Self test: the parent's ray starts at S = q + t_end*u. The lower probe's own ray toward S covers [t_start, t_end],
# so it sees any wall that separates S from the lower ray's end inside that range; S itself lies beyond t_end for
# most parents and directions, and almost never inside t_start at t0 = 1.60. Shares of weight and directions:
def start_distances(c, t0=T0):
    t_start, t_end = interval(c, t0)
    h = 2.0 ** (c + 1)
    beyond = below = covered = 0.0
    for offset, weight in corners():
        r = np.linalg.norm(offset * h + t_end * w_all, axis=1)
        beyond += weight * (r > t_end).mean()
        below += weight * (r < t_start).mean()
        covered += weight * (np.clip(np.minimum(r, t_end) - t_start, 0, None) / r).mean()
    return beyond, below, covered


beyond, below, covered = zip(*(start_distances(c) for c in range(3)))
assert [round(x, 2) for x in beyond] == [0.72, 0.61, 0.56]
assert max(below) < 2e-4
# The share of the segment from the lower probe to S that its own ray covers, on average.
assert [round(x, 2) for x in covered] == [0.78, 0.64, 0.69]

# A light of width a facing a probe at distance D covers x = a^2/D^2 * N_c/(4*pi) bins of cascade c, N_c = 32*4**c.
# At t0 = sqrt(32/(4*pi)) that is (a/2**c)**2 at the end of cascade c's interval and 16 times more at its start, and
# x grows fourfold across each hand-over at a fixed distance.
for a in (1.0, 2.0, 8.0):
    for c in range(4):
        bins = lambda d, k: a ** 2 / d ** 2 * 32 * 4 ** k / (4 * math.pi)  # noqa: E731
        start, end = interval(c)
        assert math.isclose(bins(end, c), (a / 2 ** c) ** 2)
        assert c == 0 or math.isclose(bins(start, c), 16 * bins(end, c))
        assert math.isclose(bins(end, c + 1), 4 * bins(end, c))
# From 23.4 to 31.8 voxels, across hand-over 2, x grows 2.2-fold; at the measured angular exponent -0.68 the error
# falls by 41% over that span, and by 61% for a fourfold x at a fixed distance.
growth = 4 * (23.4 / 31.8) ** 2
assert round(growth, 1) == 2.2 and round(1 - growth ** -0.68, 2) == 0.41 and round(1 - 4 ** -0.68, 2) == 0.61

# At the parent's interval start t_c, a parent offset across the ray by delta upper spacings sees a point in a
# direction off by delta * 2**(c+1) / t_c, which in mean parent bins sqrt(4*pi/N_{c+1}) is 4 * delta * t_eq/t0 at
# every hand-over: 1.73 to 5.20 bins for the nearest and farthest parents at t0 = t_eq.
for c in range(3):
    shift = [delta * 2 ** (c + 1) / interval(c)[1] / math.sqrt(4 * math.pi / (32 * 4 ** (c + 1)))
             for delta in (0.433, 1.299)]
    assert [round(s, 2) for s in shift] == [1.73, 5.2]
print("hand_over_geometry: ok")
