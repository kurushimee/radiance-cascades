"""Which share of a small light depth reprojection keeps.

All probes of a cascade share their bin directions, so the parents' rays in a child direction w are parallel to the
lower probe's. The merged depth along w exists only where some parent's ray along w hits a surface. Where the lower
probe p would see a cube light along w but no parent's parallel ray hits it, the depth is unknown, the read stays
along w, and every parent misses the light there; where a parent hits it but p would not, the read moves to the empty
point p + D*w. So p keeps the light only in the directions where at least one of the eight parents also hits it.
For p uniform in the parent cell (spacing h), w uniform, and p's hit point uniform over the light's cross-section,
that share K depends on a/h alone, for a light of side a.
"""
import itertools
import math

import numpy as np

rng = np.random.default_rng(11)
CORNERS = np.array(list(itertools.product((0.0, 1.0), repeat=3)))
SAMPLES = 400_000


def unit(n):
    v = rng.normal(size=(n, 3))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def hits(origin, w, lo, hi):
    a, b = (lo - origin) / w, (hi - origin) / w
    near, far = np.minimum(a, b).max(-1), np.maximum(a, b).min(-1)
    return far >= np.maximum(near, 0)


def kept(ratio):
    """K(a/h), with h = 1: of the directions in which p hits the light, the share in which a parent also does."""
    p, w = rng.uniform(0, 1, (SAMPLES, 3)), unit(SAMPLES)
    lateral = unit(SAMPLES)
    lateral -= (lateral * w).sum(1, keepdims=True) * w
    lateral /= np.linalg.norm(lateral, axis=1, keepdims=True)
    radius = ratio * math.sqrt(3) / 2  # covers the cube's cross-section
    centre = p + 20 * w + lateral * (radius * np.sqrt(rng.uniform(0, 1, SAMPLES)))[:, None]
    lo, hi = centre - ratio / 2, centre + ratio / 2
    seen = hits(p, w, lo, hi)
    by_parent = np.zeros(SAMPLES, bool)
    for q in CORNERS:
        by_parent |= hits(np.broadcast_to(q, p.shape), w, lo, hi)
    # A light placed at random is seen in proportion to its cross-section; weighting by its inverse makes w uniform.
    weight = 1 / np.abs(w[seen]).sum(1)
    return float((by_parent[seen] * weight).sum() / weight.sum())


shares = {ratio: kept(ratio) for ratio in (0.125, 0.25, 0.5, 1.0)}
assert abs(shares[0.125] - 0.057) < 0.003
assert abs(shares[0.25] - 0.216) < 0.006
assert abs(shares[0.5] - 0.678) < 0.008
assert shares[1.0] > 0.999

# For a light much smaller than the cell, K is the density of the parents' lateral offsets at zero times the
# light's cross-section. The offsets q - p of the eight parents fill the doubled cell [-h, h]^3 uniformly at 1/h^3,
# whose chord through 0 along w is 2h/max|w_i|; the cross-section is a^2 * sum|w_i|. So K ~ C*(a/h)^2 with
# C = 2*E[sum|w_i| / max|w_i|].
w = np.abs(unit(1_000_000))
C = 2 * float((w.sum(1) / w.max(1)).mean())
assert 3.65 < C < 3.75
assert math.isclose(shares[0.125], C * 0.125 ** 2, rel_tol=0.05)
print(f"depth_light_loss: ok; K = {shares}, C = {C:.2f}")
