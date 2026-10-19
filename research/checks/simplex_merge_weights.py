"""Merge weights on a cubic upper grid split into six tetrahedra per cell (Kuhn), against trilinear.

The enclosing tetrahedron comes from sorting the three fractional coordinates; its corners are 0, e_a,
e_a + e_b and (1, 1, 1), with weights 1 - f_a, f_a - f_b, f_b - f_c and f_c for f_a >= f_b >= f_c.
Cell-centred lower probes sit at fractions 1/4 or 3/4 of an upper cell on each axis.
"""
import itertools

import numpy as np


def kuhn(f):
    order = np.argsort(-f)
    s = f[order]
    weights = [1 - s[0], s[0] - s[1], s[1] - s[2], s[2]]
    corner = np.zeros(3)
    corners = [corner.copy()]
    for axis in order:
        corner[axis] = 1
        corners.append(corner.copy())
    return weights, corners


def trilinear_count(f):
    return sum(1 for c in itertools.product((0, 1), repeat=3) if np.prod([fi if ci else 1 - fi for fi, ci in zip(f, c)]) > 0)


def fix_factor(k, shares):
    top = shares[-1] / sum(shares)
    return k * (1 - top) + top


rng = np.random.default_rng(3)
for f in rng.random((1000, 3)):
    weights, corners = kuhn(f)
    assert min(weights) >= -1e-12 and abs(sum(weights) - 1) < 1e-12
    # Linear functions are reproduced exactly.
    a, b = rng.normal(size=3), rng.normal()
    assert abs(sum(w * (a @ c + b) for w, c in zip(weights, corners)) - (a @ f + b)) < 1e-9

counts = []
for f in itertools.product((0.25, 0.75), repeat=3):
    weights, _ = kuhn(np.array(f))
    counts.append(sum(1 for w in weights if w > 1e-12))
    assert trilinear_count(f) == 8

# Probes on the shared diagonal take 2 upper probes, the other six classes 3; never 4.
assert sorted(counts) == [2, 2, 3, 3, 3, 3, 3, 3]
mean = sum(counts) / len(counts)
assert mean == 2.75

# Fix cost on a 3D grid with rays halving per cascade, five cascades, the top cascade unfixed.
rays = [0.5 ** n for n in range(5)]
time_l4 = [2.0 ** n for n in range(5)]
assert round(fix_factor(mean, rays), 2) == 2.69
assert round(fix_factor(mean, [0.5 ** n for n in range(7)]), 2) == 2.74
assert round(fix_factor(mean, time_l4), 2) == 1.85
