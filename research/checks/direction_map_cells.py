"""Cell compactness of the equal-area cylindrical (Split RC) and Clarberg maps at low direction counts.

Metric: RMS angle between points of a cell and the cell's centre direction, divided by the square root
of the cell's solid angle. Both maps are equal-area, so uniform samples of the square are uniform on the sphere.
A disc would give 1/sqrt(2*pi) = 0.399.
"""
import numpy as np


def cylindrical(u, v):
    phi = 2 * np.pi * u
    z = 2 * v - 1
    r = np.sqrt(np.clip(1 - z * z, 0, 1))
    return np.stack([r * np.cos(phi), r * np.sin(phi), z], -1)


def clarberg(s, t):
    u, v = 2 * s - 1, 2 * t - 1
    d = 1 - (np.abs(u) + np.abs(v))
    r = 1 - np.abs(d)
    safe = np.where(r == 0, 1, r)
    phi = np.where(r == 0, 0, (np.pi / 4) * ((np.abs(v) - np.abs(u)) / safe + 1))
    k = r * np.sqrt(2 - r * r)
    return np.stack([np.sign(u) * np.cos(phi) * k, np.sign(v) * np.sin(phi) * k, np.sign(d) * (1 - r * r)], -1)


def compactness(mapping, columns, rows, samples=800):
    g = (np.arange(samples) + 0.5) / samples
    u, v = np.meshgrid(g, g, indexing="ij")
    iu = np.minimum((u * columns).astype(int), columns - 1)
    iv = np.minimum((v * rows).astype(int), rows - 1)
    points = mapping(u, v)
    centres = mapping((iu + 0.5) / columns, (iv + 0.5) / rows)
    angle = np.arccos(np.clip((points * centres).sum(-1), -1, 1))
    return np.sqrt((angle ** 2).mean()) / np.sqrt(4 * np.pi / (columns * rows))


expected = [
    (clarberg, 4, 4, 0.455),
    (cylindrical, 6, 3, 0.436),
    (cylindrical, 8, 4, 0.444),
    (clarberg, 16, 16, 0.460),
    (cylindrical, 24, 12, 0.475),
]
for mapping, columns, rows, value in expected:
    assert abs(compactness(mapping, columns, rows) - value) < 0.003, (columns * rows, value)

# Within 5% of each other at 16 to 32 directions, with the cylindrical map ahead; the order flips at high counts.
assert compactness(cylindrical, 8, 4) < compactness(clarberg, 4, 4) < 1.05 * compactness(cylindrical, 8, 4)
assert compactness(cylindrical, 24, 12) > compactness(clarberg, 16, 16)
