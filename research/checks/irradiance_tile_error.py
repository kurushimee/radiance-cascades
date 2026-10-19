"""Irradiance from one directional light: bilinear octahedral tiles of N x N against bands 0 to 2 of SH.

E(n) = max(0, n.l), the worst case for band-limited storage. Tiles store E at texel centres with a
1-texel border copied by the folded octahedral rule, and are read with bilinear filtering.
"""
import numpy as np


def sign_not_zero(v):
    return np.where(v >= 0, 1.0, -1.0)


def oct_encode(v):
    p = v[..., :2] / np.abs(v).sum(-1, keepdims=True)
    folded = (1 - np.abs(p[..., ::-1])) * sign_not_zero(p)
    return np.where(v[..., 2:3] <= 0, folded, p)


def oct_decode(e):
    v = np.concatenate([e, 1 - np.abs(e).sum(-1, keepdims=True)], -1)
    folded = (1 - np.abs(v[..., 1::-1])) * sign_not_zero(v[..., :2])
    v[..., :2] = np.where(v[..., 2:3] < 0, folded, v[..., :2])
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def tile(n, light):
    centres = (np.arange(n) + 0.5) / n * 2 - 1
    e = np.stack(np.meshgrid(centres, centres, indexing="ij"), -1)
    inner = np.maximum(oct_decode(e) @ light, 0)
    t = n + 2
    padded = np.zeros((t, t))
    padded[1:-1, 1:-1] = inner
    padded[1:-1, 0] = inner[::-1, 0]
    padded[1:-1, -1] = inner[::-1, -1]
    padded[0, 1:-1] = inner[0, ::-1]
    padded[-1, 1:-1] = inner[-1, ::-1]
    padded[0, 0], padded[0, -1] = inner[-1, -1], inner[-1, 0]
    padded[-1, 0], padded[-1, -1] = inner[0, -1], inner[0, 0]
    return padded


def bilinear(padded, n, directions):
    x = (oct_encode(directions) + 1) / 2 * n + 0.5
    i = np.clip(np.floor(x).astype(int), 0, n)
    f = x - i
    a = padded[i[:, 0], i[:, 1]] * (1 - f[:, 1]) + padded[i[:, 0], i[:, 1] + 1] * f[:, 1]
    b = padded[i[:, 0] + 1, i[:, 1]] * (1 - f[:, 1]) + padded[i[:, 0] + 1, i[:, 1] + 1] * f[:, 1]
    return a * (1 - f[:, 0]) + b * f[:, 0]


def sh9(cosine):
    """Bands 0 to 2 of max(0, x): 1/4 + x/2 + (5/16)*P2(x)."""
    return 0.25 + 0.5 * cosine + (5 / 16) * (3 * cosine ** 2 - 1) / 2


rng = np.random.default_rng(1)
directions = rng.normal(size=(200000, 3))
directions /= np.linalg.norm(directions, axis=1, keepdims=True)
lights = rng.normal(size=(64, 3))
lights /= np.linalg.norm(lights, axis=1, keepdims=True)


def mean_and_max(estimate):
    errors = [np.abs(estimate(l) - np.maximum(directions @ l, 0)) for l in lights]
    return float(np.mean(errors)), float(np.max(errors))


sh_mean, sh_max = mean_and_max(lambda l: sh9(directions @ l))
assert round(sh_mean, 3) == 0.031 and round(sh_max, 3) == 0.094

tiles = {n: mean_and_max(lambda l, n=n: bilinear(tile(n, l), n, directions)) for n in (4, 6, 8, 12)}
assert [round(tiles[n][0], 3) for n in (4, 6, 8, 12)] == [0.063, 0.034, 0.021, 0.010], tiles

# A 6x6 tile's 36 texels match the 9 SH coefficients' mean error; its maximum, at the large texels, is far worse.
assert abs(tiles[6][0] - sh_mean) < 0.004
assert tiles[6][1] > 2.5 * sh_max
# Beating SH9's mean error takes 8x8, and no tile size tried reaches its maximum error.
assert tiles[8][0] < sh_mean and all(tiles[n][1] > sh_max for n in tiles)
