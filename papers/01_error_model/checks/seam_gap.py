"""Seam gap of the vanilla merge on cell-centred grids with spacing x2 per cascade (2D).

A lower probe sits at fractions 1/4 or 3/4 of its upper cell on each axis. Upper probe i, offset delta_i from the
lower probe, starts its interval at the hand-over distance measured from itself, which along a lower ray of
direction w lies at the hand-over plus delta_i . w. Surfaces in between are seen by neither cascade. With overlap o
(in upper spacings) the lower interval runs o further, and the gap is max(delta_i . w - o, 0).
"""
import itertools
import math

import numpy as np


def corners():
    """Offsets (upper spacings) and bilinear weights of the four upper probes around a lower probe at (1/4, 1/4)."""
    out = []
    for cx, cy in itertools.product((0, 1), repeat=2):
        offset = np.array([cx - 0.25, cy - 0.25])
        weight = (0.25 if cx else 0.75) * (0.25 if cy else 0.75)
        out.append((offset, weight))
    return out


def mean_gap(overlap=0.0, samples=200_000, sign=1):
    """Mean length, over directions and corners, seen by neither cascade (sign 1) or by both (sign -1)."""
    phi = (np.arange(samples) + 0.5) * 2 * math.pi / samples
    w = np.stack([np.cos(phi), np.sin(phi)], -1)
    return sum(weight * np.maximum(sign * (w @ offset - overlap), 0).mean() for offset, weight in corners())


weighted_distance = sum(weight * np.linalg.norm(offset) for offset, weight in corners())
assert round(weighted_distance, 3) == 0.562
# Over uniform directions the mean of max(cos, 0) is 1/pi.
assert abs(mean_gap() - weighted_distance / math.pi) < 1e-6
assert round(mean_gap(), 4) == 0.1788

# Every gap closes once the overlap reaches the farthest corner, 0.75*sqrt(2) upper spacings.
farthest = max(np.linalg.norm(offset) for offset, _ in corners())
assert abs(farthest - 0.75 * math.sqrt(2)) < 1e-12 and round(farthest, 4) == 1.0607
assert mean_gap(farthest) == 0.0
assert round(mean_gap(0.5) / mean_gap(), 3) == 0.157

# Corners behind the lower probe start early, so the same mean length is seen twice; overlap adds to it one for one,
# since the along-ray offset averages to zero over directions.
for overlap in (0.0, 0.5, farthest):
    assert abs(mean_gap(overlap, sign=-1) - (mean_gap(overlap) + overlap)) < 1e-6
assert abs(mean_gap(sign=-1) - mean_gap()) < 1e-6

# The four parity classes are mirror images, so they share every number above.
for fx, fy in itertools.product((0.25, 0.75), repeat=2):
    offsets = sorted(round(math.hypot(cx - fx, cy - fy), 6) for cx, cy in itertools.product((0, 1), repeat=2))
    assert offsets == sorted(round(np.linalg.norm(o), 6) for o, _ in corners())
# 3D, trilinear: a lower probe sits at a quarter of its upper cell on each of three axes. Over uniform directions on
# the sphere the mean of max(cos, 0) is 1/4, so the mean unseen length is sum(w*|delta|)/4.
corners_3d = [(np.array([cx - 0.25, cy - 0.25, cz - 0.25]),
               (0.25 if cx else 0.75) * (0.25 if cy else 0.75) * (0.25 if cz else 0.75))
              for cx, cy, cz in itertools.product((0, 1), repeat=3)]
weighted_3d = sum(weight * np.linalg.norm(offset) for offset, weight in corners_3d)
rng = np.random.default_rng(0)
w3 = rng.normal(size=(400_000, 3))
w3 /= np.linalg.norm(w3, axis=1, keepdims=True)
sampled = sum(weight * np.maximum(w3 @ offset, 0).mean() for offset, weight in corners_3d)
assert abs(sampled - weighted_3d / 4) < 2e-3
assert round(weighted_3d, 3) == 0.706 and round(weighted_3d / 4, 3) == 0.177
farthest_3d = max(np.linalg.norm(offset) for offset, _ in corners_3d)
assert abs(farthest_3d - 0.75 * math.sqrt(3)) < 1e-12 and round(farthest_3d, 2) == 1.30
print("seam_gap: ok")
