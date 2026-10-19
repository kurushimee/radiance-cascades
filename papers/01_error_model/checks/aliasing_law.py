"""Aliasing of a light narrower than a few rays.

A light spanning x ray spacings, at a uniformly random phase against the rays, is hit by floor(x) or ceil(x) of them,
the second with probability f = frac(x). The estimate is (hits/x) times the truth, so its relative RMS error is
sqrt(f*(1-f))/x, at most 1/(2x).
"""
import math

import numpy as np


def relative_rms(x, phases=200_000):
    phase = (np.arange(phases) + 0.5) / phases
    hits = np.floor(x + phase) - np.floor(phase)
    return math.sqrt(((hits - x) ** 2).mean()) / x


for x in (0.3, 0.9, 1.0, 1.5, 2.25, 3.7, 8.5, 12.0):
    f = x - math.floor(x)
    assert abs(relative_rms(x) - math.sqrt(f * (1 - f)) / x) < 1e-4
    assert relative_rms(x) <= 1 / (2 * x) + 1e-9 or x < 1

# Over a spread of x, f is uniform and the mean of f*(1-f) is 1/6: the typical error is 1/(sqrt(6)*x) = 0.41/x.
f = (np.arange(1_000_000) + 0.5) / 1_000_000
assert abs((f * (1 - f)).mean() - 1 / 6) < 1e-9 and round(1 / math.sqrt(6), 2) == 0.41

# Below one ray spacing the light is missed with probability 1 - x: the error is sqrt((1 - x)/x).
assert abs(relative_rms(0.3) - math.sqrt(0.7 / 0.3)) < 1e-4
# Width at which the worst-phase error bound drops to a target: a light one ray gap wide errs by up to 50%,
# two gaps (the Nyquist width) by up to 25%, and 10% needs five gaps.
assert [1 / (2 * x) for x in (1, 2, 5)] == [0.5, 0.25, 0.1]
print("aliasing_law: ok")
