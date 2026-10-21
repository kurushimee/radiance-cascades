"""Frame budget of the GI at 1080p on an RTX 2070, and the atlas texel spacing it buys.

A bounce pass re-shades and re-merges every stored hit record, so the passes cost passes * records * c_r; every
other pass gets a fixed allowance. Records per texel come from the lab (design/experiments.md, E2 and E3): cascade 0
keeps 4 * bins bent segments (about four front parents per bin), and each world cascade adds records in proportion to
the bins. The lab's scenes stop at three world cascades; above those the model adds a constant per cascade.

`python budget.py <area> <diameter>` prints the texel spacing at the planning point for a scene of that surface area
(m²) and diameter (m), after the checks pass.
"""
import math
import sys

CEILING_MS = 12.0
AIM_MS = 6.0
FIXED_MS = {"direct light": 0.2, "moving objects": 0.5, "near field": 1.0, "composite": 0.1, "setup": 0.2}
PASSES = 5
C_R_NS = 0.1

# Lab records per texel at 16 bins, sphere fix at every world hand-over (E2): world cascades 1, 2 and 3.
LAB_WORLD = {"room": (21, 49, 64), "thick room": (25, 47, 58), "two rooms": (20, 45, 52),
             "courtyard": (26, 66, 109), "sealed box": (24, 46, 63), "columns": (35, 42, 44)}
FIRST, REST = 25, 60  # central model: world cascade 1, and each cascade above it
FIRST_MAX, REST_MAX = 35, 110  # bound: the largest the lab measured at each

# RTX 2070: 448 GB/s peak.
BANDWIDTH = 448e9 * 0.7
BYTES_PER_RECORD = (8, 16)  # the record itself, its share of a merged write, a parent read on a miss

# Measured with hardware ray queries on Intel Sponza and Crytek Sponza (plan 004 M1): lowest and highest rate.
SHADOW_RAYS_PER_S = (1.47e9, 2.40e9)
SHORT_SEGMENTS_PER_S = (1.88e9, 2.61e9)  # cascades 0 and 1
SEGMENTS_PER_S = (0.64e9, 3.96e9)  # every cascade
TRACER_BYTES_PER_TRIANGLE = 48 + 56 + 128  # corners, attributes, acceleration structures with their scratch


def t0(bins):
    """Cascade 0's equal-error interval in texel spacings."""
    return math.sqrt(2 * bins / (4 * math.pi))


def world_cascades(diameter, spacing, bins):
    """World cascades that put the top cascade's start inside the scene's diameter."""
    return max(1, math.ceil(math.log(diameter / (t0(bins) * spacing), 4)))


def records_per_texel(bins, world, first=FIRST, rest=REST):
    return 4 * bins + bins / 16 * (first + rest * (world - 1))


def record_budget(passes_ms, passes=PASSES, c_r_ns=C_R_NS):
    return passes_ms * 1e-3 / (passes * c_r_ns * 1e-9)


def spacing(area, records, bins=16, diameter=45.0):
    """Texel spacing (m), world cascades and records per texel for a scene of surface `area` (m²)."""
    s = 1.0
    for _ in range(20):
        world = world_cascades(diameter, s, bins)
        s = math.sqrt(area * records_per_texel(bins, world) / records)
    return s, world, records_per_texel(bins, world)


# The model brackets the lab: its central value is within 10% of the lab's mean, its bound above every scene.
lab = [64 + sum(levels) for levels in LAB_WORLD.values()]
assert lab == [198, 194, 181, 265, 197, 185]
assert abs(records_per_texel(16, 3) / (sum(lab) / len(lab)) - 1) < 0.1
assert records_per_texel(16, 3, FIRST_MAX, REST_MAX) >= max(lab)

# The aim leaves the passes 4 ms, which buys 8 M records at the planning cost.
passes_ms = AIM_MS - sum(FIXED_MS.values())
assert math.isclose(passes_ms, 4.0)
assert math.isclose(record_budget(passes_ms), 8e6)
assert AIM_MS <= CEILING_MS / 2

# The planning cost is about 2 to 4 times what bandwidth alone allows.
floor = [b / BANDWIDTH * 1e9 for b in BYTES_PER_RECORD]
assert [round(f, 3) for f in floor] == [0.026, 0.051]
assert [round(C_R_NS / f, 1) for f in floor] == [3.9, 2.0]

# Texel spacing at the planning point (16 bins, 5 passes, 0.1 ns): about 0.18, 0.32 and 0.45 m for 1,000, 3,000 and
# 6,000 m² of surface, with four world cascades in a scene 45 m across and about 270 records per texel.
plan = [spacing(a, 8e6) for a in (1000, 3000, 6000)]
assert [round(s, 2) for s, _, _ in plan] == [0.18, 0.32, 0.45]
assert all(world == 4 and records == 269 for _, world, records in plan)
assert round(8e6 / 269) == 29740

# The downloaded test scenes as measured (area in m², diameter in m), and the spacing they get at the planning point.
MEASURED = {"Bistro interior": (1445.2, 26.0, 0.22), "Crytek Sponza": (8144.5, 37.1, 0.46),
            "Intel Sponza with ivy": (10782.7, 47.7, 0.53), "Bistro exterior": (137297.0, 258.5, 2.15)}
assert all(round(spacing(a, 8e6, diameter=d)[0], 2) == s for a, d, s in MEASURED.values())

# The cost per record moves the spacing with its square root: 0.03 ns gives 0.17 m at 3,000 m², 0.3 ns 0.48 m.
assert round(spacing(3000, record_budget(passes_ms, c_r_ns=0.03))[0], 2) == 0.17
assert round(spacing(3000, record_budget(passes_ms, c_r_ns=0.3))[0], 2) == 0.48

# Three passes, enough at albedo 0.5 (E5), buy 5/3 the records: 0.25 m at 3,000 m².
assert round(spacing(3000, record_budget(passes_ms, passes=3))[0], 2) == 0.25

# 36 bins need 2.2 to 2.25 times the records per texel, so 1.5 times the spacing at a fixed budget (0.42 m).
assert 2.2 <= records_per_texel(36, 4) / records_per_texel(16, 4) <= 2.25
assert round(spacing(3000, 8e6, bins=36)[0], 2) == 0.42

# A record keeps a 4-byte hit texel, a byte of parent flags and a 2-byte distance: 56 MB at the planning budget.
assert 8e6 * (4 + 1 + 2) / 1e6 == 56

# At the measured rates, the direct-light line covers 294,000 to 480,000 shadow rays, one per texel for the sun and for
# 9 to 15 moving lights over 30,000 texels, and the moving-object line 940,000 to 1,305,000 short segments; at load,
# 8 M segments take 2.0 to 12.5 ms.
shadow_rays = [round(FIXED_MS["direct light"] * 1e-3 * r) for r in SHADOW_RAYS_PER_S]
assert shadow_rays == [294_000, 480_000]
assert [round(rays / 30_000 - 1) for rays in shadow_rays] == [9, 15]
assert [round(FIXED_MS["moving objects"] * 1e-3 * r) for r in SHORT_SEGMENTS_PER_S] == [940_000, 1_305_000]
assert [round(8e6 / r * 1e3, 1) for r in reversed(SEGMENTS_PER_S)] == [2.0, 12.5]

# Without a near-field pass the passes get 5 ms: 10 M records, texels about 11% closer at 3,000 m².
assert math.isclose(record_budget(passes_ms + FIXED_MS["near field"]), 10e6)
assert round(1 - spacing(3000, 10e6)[0] / spacing(3000, 8e6)[0], 2) == 0.11

# Merged world radiance: one value per world record, the records past cascade 0's 64 per texel.
assert round((8e6 - 64 * 8e6 / 269) / 1e6, 1) == 6.1

# Geometry: 232 bytes per triangle, 61 MB for Crytek Sponza and 2.5 GB for a 10.8 M-triangle scene.
assert round(262_267 * TRACER_BYTES_PER_TRIANGLE / 1e6) == 61
assert round(10.8e6 * TRACER_BYTES_PER_TRIANGLE / 1e9, 1) == 2.5

if len(sys.argv) == 3:
    print(spacing(float(sys.argv[1]), record_budget(passes_ms), diameter=float(sys.argv[2]))[0])
