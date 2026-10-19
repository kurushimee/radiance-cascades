"""Reading a parent toward an estimated hit point, and estimating that point from the parents' stored depths.

The lower ray from p in direction w misses its interval. Reading parent q toward p + D*w, rather than along w,
removes the parallax of a hit at depth D: vanilla is D = infinity, the parallax fix D = t_end, the fixed-depth
reprojection one depth per hand-over, and the depth merge the depth the parents report. Parent q sees a hit at
depth d_q along w; for a plane every parent sees, the trilinear mean of d_q is the lower ray's own depth.
"""
import itertools
import math

import numpy as np

rng = np.random.default_rng(5)


def corners(frac):
    """Positions (upper spacings, relative to the cell's base corner) and trilinear weights of the eight parents."""
    out = []
    for c in itertools.product((0, 1), repeat=3):
        out.append((np.array(c, float), np.prod([f if ci else 1 - f for f, ci in zip(frac, c)])))
    return out


def plane_depth(origin, w, point, normal):
    return (point - origin) @ normal / (w @ normal)


# Each parent's depth along w to any plane, averaged with trilinear weights, is the lower ray's depth: the depth is
# linear in the origin and the weights reproduce linear functions.
for _ in range(200):
    frac = rng.choice((0.25, 0.75), 3)
    w = rng.normal(size=3)
    w /= np.linalg.norm(w)
    normal = rng.normal(size=3)
    normal /= np.linalg.norm(normal)
    point = frac + 6 * w + rng.normal(size=3)
    if abs(w @ normal) < 0.2:
        continue
    exact = plane_depth(frac, w, point, normal)
    mean = sum(weight * plane_depth(q, w, point, normal) for q, weight in corners(frac))
    assert math.isclose(mean, exact, rel_tol=1e-9, abs_tol=1e-9)
    # Adding (q - p) . w to each parent's depth makes each one exact on its own for a plane facing w, and leaves
    # the full mean unchanged, since the weighted offsets cancel.
    corrected = sum(weight * (plane_depth(q, w, point, normal) + (q - frac) @ w) for q, weight in corners(frac))
    assert math.isclose(corrected, exact, rel_tol=1e-9, abs_tol=1e-9)

frac, w = np.array([0.25, 0.75, 0.25]), np.array([0.0, 0.0, 1.0])
facing = [plane_depth(q, w, frac + 5 * w, w) + (q - frac) @ w for q, _ in corners(frac)]
assert np.allclose(facing, 5.0)
# The mean of inverse depths, which lets a parent that sees the sky count as infinitely far, is exact only for a
# plane facing the ray: tilted 60 degrees, six upper spacings away, it falls 2.4% short.
tilted = np.array([math.sin(math.radians(60)), 0.0, math.cos(math.radians(60))])
depths = [plane_depth(q, w, frac + 6 * w, tilted) for q, _ in corners(frac)]
weights = [weight for _, weight in corners(frac)]
inverse_mean = 1 / sum(weight / d for weight, d in zip(weights, depths))
assert 0.0240 < 1 - inverse_mean / 6 < 0.0250

# With a parent offset delta from p, reading toward p + D*w a hit that lies at depth d is off by the angle between
# q -> p + d*w and q -> p + D*w, close to |delta_perp| * |1/d - 1/D| when delta is small against both depths.
for _ in range(100):
    delta = rng.normal(size=3) * 0.05
    w = rng.normal(size=3)
    w /= np.linalg.norm(w)
    d, reach = rng.uniform(4, 40, 2)
    a, b = d * w - delta, reach * w - delta
    angle = math.acos(np.clip(a @ b / np.linalg.norm(a) / np.linalg.norm(b), -1, 1))
    perpendicular = np.linalg.norm(delta - (delta @ w) * w)
    assert math.isclose(angle, perpendicular * abs(1 / d - 1 / reach), rel_tol=0.05)
# So a fixed depth D is exact at one depth, and vanilla's error at depth d, |delta_perp|/d, falls to
# |delta_perp| * |1/d - 1/D|: the parallax fix (D = t_end) is worse than vanilla for every hit beyond 2*t_end.
d = np.linspace(1.0, 50.0, 5000)
worse = d[np.abs(1 / d - 1 / 1.6) > 1 / d]
assert math.isclose(worse.min(), 3.2, abs_tol=0.01)
print("depth_estimate: ok")
