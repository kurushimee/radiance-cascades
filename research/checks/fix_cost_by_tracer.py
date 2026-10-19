"""Time factor of a merge fix that traces k rays per lower ray on every cascade but the top.

Trace time of cascade n is rays_n * steps_n. The fix multiplies every cascade but the top by k, so its
time factor is k * (1 - s_top) + s_top, with s_top the top cascade's share of trace time.
Steps per ray by tracer class, with interval scale l and probe spacing x2 per cascade:
  length:   fixed-step march or voxel DDA at one resolution, steps grow with interval length (l^n)
  mip:      DDA through a mip chain whose voxel follows the probe spacing, steps grow as (l/2)^n
  constant: steps do not grow with interval length, which is the ray-count model
"""
import math


def fix_factor(k, shares):
    top = shares[-1] / sum(shares)
    return k * (1 - top) + top


def shares(cascades, ray_ratio, step_ratio):
    return [(ray_ratio * step_ratio) ** n for n in range(cascades)]


STEPS = {"length": lambda l: l, "mip": lambda l: l / 2, "constant": lambda l: 1}

# 2D 2x/4x, screen and surface probes: rays constant per cascade, k = 4, l = 4.
flat = {name: fix_factor(4, shares(6, 1, step(4))) for name, step in STEPS.items()}
assert round(flat["length"], 2) == 1.75
assert round(flat["mip"], 2) == 2.48
assert round(fix_factor(4, shares(5, 1, 1)), 2) == 3.40
assert round(fix_factor(4, shares(7, 1, 1)), 2) == 3.57

# DexRT's measured top share in its six-cascade 2D run.
assert round(4 * (1 - 0.636) + 0.636, 2) == 2.09

# 3D grid with x4 directions and 1/8 probes: rays halve per cascade; five cascades.
trilinear_l4 = fix_factor(8, shares(5, 0.5, STEPS["length"](4)))
trilinear_l2 = fix_factor(8, shares(5, 0.5, STEPS["length"](2)))
simplex_l4 = fix_factor(4, shares(5, 0.5, STEPS["length"](4)))
assert round(trilinear_l4, 2) == 4.39
assert round(trilinear_l2, 2) == 6.60
assert round(simplex_l4, 2) == 2.45

# Every tracer class lands between the length model and the ray-count model.
assert flat["length"] < flat["mip"] < flat["constant"]

# Per-ray time from cascade 0 to the top of five cascades at l = 4: 256x, 16x, 1x by class.
assert [STEPS[name](4) ** 4 for name in ("length", "mip", "constant")] == [256, 16, 1]
assert math.isclose(STEPS["mip"](2), 1)
