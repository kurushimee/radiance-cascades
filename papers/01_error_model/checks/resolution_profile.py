"""Angular and spatial resolution of radiance cascades as functions of distance (2D).

Cascade n holds distances up to t0*l**n with bin width 2*pi/(N0*K**n) and probe spacing ds0*2**n. At the end of its
interval the gap between neighbouring ray ends is g = D*dw and the spatial footprint is the spacing.
"""
import math

import numpy as np


def ends(n0, k, l, t0, ds0, levels=8):
    n = np.arange(levels)
    d = t0 * l ** n
    return d, d * 2 * math.pi / (n0 * k ** n), ds0 * 2.0 ** n


def equal_error_t0(n0, ds0=1.0):
    return n0 * ds0 / (2 * math.pi)


# The ratio of ray-end gap to spacing is (t0/t_eq)*(l/(2K))**n: constant over cascades only when l = 2K.
for n0, k, l, t0 in ((32, 2, 4, 1.0), (8, 2, 4, 3.0), (4, 4, 8, 1.41), (32, 2, 2, 1.0), (4, 4, 4, 1.41)):
    d, gap, spacing = ends(n0, k, l, t0, 1.0)
    expected = t0 / equal_error_t0(n0) * (l / (2 * k)) ** np.arange(len(d))
    assert np.allclose(gap / spacing, expected)
    assert np.allclose(gap / spacing, gap[0] / spacing[0]) == (l == 2 * k)

# Under K = 2, l = 4 both blurs grow as sqrt(D): g = (2*pi/N0)*sqrt(D*t0) and ds = ds0*sqrt(D/t0).
d, gap, spacing = ends(32, 2, 4, 1.7, 1.0)
assert np.allclose(gap, 2 * math.pi / 32 * np.sqrt(d * 1.7)) and np.allclose(spacing, np.sqrt(d / 1.7))

# Cascade counts as the experiments choose them: the top cascade starts at the last hand-over inside the scene. A
# scene 181 spacings across takes five cascades at t0 = 1, the top one with 512 directions, and three at t0 = 16,
# the top one with 128.
def levels_for(t0, l, reach=128 * math.sqrt(2)):
    return max(2, math.ceil(math.log(reach / t0) / math.log(l)) + 1)


assert (levels_for(1.0, 4), 32 * 2 ** (levels_for(1.0, 4) - 1)) == (5, 512)
assert (levels_for(16.0, 4), 32 * 2 ** (levels_for(16.0, 4) - 1)) == (3, 128)


def resolvable(w, n0, t0, s=1):
    """Distance up to which a light of width w spans at least one ray gap, under K = 2, l = 4."""
    return (w * s * n0 / (2 * math.pi)) ** 2 / t0


assert round(resolvable(2, 32, 1.0), 1) == 103.8
assert round(resolvable(2, 32, equal_error_t0(32)), 1) == 20.4
# Quadratic in N0 and in rays per cone, inverse in t0.
assert math.isclose(resolvable(1, 64, 2.0) / resolvable(1, 32, 2.0), 4)
assert math.isclose(resolvable(1, 8, 1.0, s=4), resolvable(1, 32, 1.0))
assert math.isclose(resolvable(1, 32, 4.0) / resolvable(1, 32, 1.0), 0.25)

# Model error e^2 = A*g^2 + B*ds^2 summed over distance: g^2/ds^2 = (t0/t_eq)^2 at every D, so
# e^2 = c*(A*t0/t_eq + B*t_eq/t0) and the optimum t0* = t_eq*sqrt(B/A) is where the two parts are equal.
rng = np.random.default_rng(0)
for _ in range(5):
    a, b, n0 = rng.uniform(0.1, 10), rng.uniform(0.1, 10), int(rng.choice((8, 16, 32)))
    teq = equal_error_t0(n0)
    t = np.exp(np.linspace(np.log(0.01), np.log(100), 200_001))
    e2 = a * t / teq + b * teq / t
    best = t[np.argmin(e2)]
    assert math.isclose(best, teq * math.sqrt(b / a), rel_tol=1e-3)
    assert math.isclose(a * best / teq, b * teq / best, rel_tol=2e-3)
# With other exponents, e^2 = A*t0**alpha + B*t0**-beta, the optimum sits at (beta/alpha)**(1/(alpha+beta)) times
# the crossing: aliasing (alpha = 1) against a blurred step edge (beta = 1/2) puts it at 0.63 times the crossing.
alpha, beta = 1.0, 0.5
t = np.exp(np.linspace(np.log(0.01), np.log(100), 400_001))
e2 = 3.0 * t ** alpha + 2.0 * t ** -beta
cross = (2.0 / 3.0) ** (1 / (alpha + beta))
assert math.isclose(t[np.argmin(e2)] / cross, (beta / alpha) ** (1 / (alpha + beta)), rel_tol=1e-3)
assert round((beta / alpha) ** (1 / (alpha + beta)), 2) == 0.63
# In 3D, with K = 4 and l = 4, a bin's angular width sqrt(4*pi/M) halves per cascade while the spacing doubles, so
# the same sqrt(D) laws hold, and the equal-error interval is ds0*sqrt(N0/(4*pi)): 1.60 spacings at 32 directions.
width0 = math.sqrt(4 * math.pi / 32)
n = np.arange(6)
assert np.allclose(np.sqrt(4 * math.pi / (32 * 4.0 ** n)), width0 / 2.0 ** n)
assert round(1 / width0, 2) == 1.60

# In 3D, s rays spread over a cell leave gaps of t*width/sqrt(s), so at the interval ends the gap is
# width0*sqrt(D*t0/s), and a light of width w spans one gap out to D_max = w^2*s*N0/(4*pi*t0): linear in N0.
def resolvable_3d(w, s, n0, t0):
    return w ** 2 * s * n0 / (4 * math.pi * t0)


for w, s, n0, t0 in ((2.0, 1, 32, 1.0), (1.0, 4, 32, 1.6), (3.0, 1, 128, 2.0)):
    width = math.sqrt(4 * math.pi / n0)
    reach = resolvable_3d(w, s, n0, t0)
    assert math.isclose(width * math.sqrt(reach * t0 / s), w)
assert math.isclose(resolvable_3d(2, 1, 64, 1) / resolvable_3d(2, 1, 32, 1), 2)
assert round(resolvable_3d(2, 1, 32, 1 / width0), 2) == 6.38
print("resolution_profile: ok")
