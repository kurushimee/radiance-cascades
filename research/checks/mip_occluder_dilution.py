"""Opacity a thin occluder keeps under box-filtered mips, against the Switch game's pow(2, i^2) weights."""
import numpy as np


def mip(image, level):
    for _ in range(level):
        image = 0.25 * (image[0::2, 0::2] + image[1::2, 0::2] + image[0::2, 1::2] + image[1::2, 1::2])
    return image


size = 64
line = np.zeros((size, size))
line[:, 8] = 1.0
dot = np.zeros((size, size))
dot[8, 8] = 1.0

for i in range(4):
    assert np.isclose(mip(line, i).max(), 1 / 2 ** i)
    assert np.isclose(mip(dot, i).max(), 1 / 4 ** i)

weights = [2 ** (i * i) for i in range(4)]
assert weights == [1, 2, 16, 512]

# Cascade 1 matches the line's factor 2^1, cascade 2 the dot's 4^2; cascade 3 overshoots both 2^3 and 4^3.
assert weights[1] == 2 ** 1 and weights[2] == 4 ** 2
assert weights[3] > 4 ** 3 > 2 ** 3
