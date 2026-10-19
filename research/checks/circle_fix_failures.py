"""Where the circle-intersection fix has no forward exit point, and why the failures form a period-2 pattern.

A lower probe P at the centre of its cell sits at offsets of 1/4 and 3/4 of an upper spacing from its
four upper probes C. For direction d the ray starts at S = P + d * t_start and the fix ends it at the far
intersection with the circle |X - C| = t_end. The fix fails when that circle is missed (D < 0) or lies
behind the start (far root t+ <= 0). Lengths are in units of the cascade 0 spacing.
"""
import math


def far_root(p, c, d, t_start, t_end):
    a, b = p[0] + d[0] * t_start - c[0], p[1] + d[1] * t_start - c[1]
    disc = t_end ** 2 - (a * d[1] - b * d[0]) ** 2
    if disc < 0:
        return None
    return -(a * d[0] + b * d[1]) + math.sqrt(disc)


def failures(parity, cascade, directions, t_start, t_end):
    """Set of (direction index, upper probe) pairs with no forward exit, for one parity class."""
    spacing = 2.0 ** cascade
    p = ((parity[0] + 0.5) * spacing, (parity[1] + 0.5) * spacing)
    xs = [spacing, (3 if parity[0] else -1) * spacing]
    ys = [spacing, (3 if parity[1] else -1) * spacing]
    uppers = [(x, y) for x in xs for y in ys]
    found, outside = set(), set()
    for k in range(directions):
        angle = (k + 0.5) * 2 * math.pi / directions
        d = (math.cos(angle), math.sin(angle))
        for c in uppers:
            # The upper probe's offset, reflected into class (0, 0), names it across classes.
            rank = ((c[0] - p[0]) * (-1 if parity[0] else 1), (c[1] - p[1]) * (-1 if parity[1] else 1))
            start = (p[0] + d[0] * t_start - c[0], p[1] + d[1] * t_start - c[1])
            if math.hypot(*start) > t_end:
                outside.add((k, rank))
            root = far_root(p, c, d, t_start, t_end)
            if root is None or root <= 0:
                found.add((k, rank))
    return found, outside


PARITIES = [(0, 0), (1, 0), (0, 1), (1, 1)]


def mirrored(fails, parity, directions):
    """Map class (0, 0)'s failures to another class by reflecting x and/or y."""
    out = set()
    for k, rank in fails:
        angle = (k + 0.5) * 2 * math.pi / directions
        if parity[0]:
            angle = math.pi - angle
        if parity[1]:
            angle = -angle
        out.add((round((angle % (2 * math.pi)) / (2 * math.pi) * directions - 0.5) % directions, rank))
    return out


def run(setup):
    """Cascades with failures, checking the period-2 structure on each."""
    failing = []
    for cascade, (t_start, t_end, directions) in enumerate(setup):
        sets = {q: failures(q, cascade, directions, t_start, t_end) for q in PARITIES}
        fails = {q: s[0] for q, s in sets.items()}
        if any(fails.values()):
            failing.append(cascade)
            assert all(fails[q] == mirrored(fails[(0, 0)], q, directions) for q in PARITIES)
            assert len({frozenset(f) for f in fails.values()}) > 1
        for q, (f, outside) in sets.items():
            assert f <= outside
    return failing


def fails_by_length(intervals, dims):
    """Cascades whose interval is shorter than the farthest upper probe, 0.75 * sqrt(dims) upper spacings."""
    return [c for c, (t0, t1) in enumerate(intervals) if t1 - t0 < 0.75 * math.sqrt(dims) * 2 ** (c + 1)]


# LegitCascades ChroniclFix defaults: 15 px spacing, t_end 9, 45, 189 px; 4 * 4^c directions.
legit = [(0 / 15, 9 / 15, 4), (9 / 15, 45 / 15, 16), (45 / 15, 189 / 15, 64)]
assert run(legit) == [0, 1] == fails_by_length([r[:2] for r in legit], 2)

# Contiguous x4 intervals from 0 with t0 = 1 spacing. Cascade 1 clears D >= 0 (t_end 5 against 4.24),
# yet a ray that starts outside the circle and points away from it finds the circle behind its start.
contiguous = [(0, 1, 4), (1, 5, 16), (5, 21, 64)]
assert run(contiguous) == [0, 1] == fails_by_length([r[:2] for r in contiguous], 2)
assert 5 > 0.75 * math.sqrt(2) * 4
assert fails_by_length([r[:2] for r in contiguous], 3) == [0, 1]

# Split RC-style ends t_n = 1.6 * 4^n: cascade 0 fails in 2D, cascades 0 and 1 in 3D (4.8 against 5.20).
split = [(0, 1.6), (1.6, 6.4), (6.4, 25.6)]
assert fails_by_length(split, 2) == [0] and fails_by_length(split, 3) == [0, 1]

# With l = 4 and intervals 4^c * t0 long, the t0 needed halves per cascade.
assert [round(0.75 * math.sqrt(2) * 2 ** (c + 1) / 4 ** c, 2) for c in range(3)] == [2.12, 1.06, 0.53]
assert [round(0.75 * math.sqrt(3) * 2 ** (c + 1) / 4 ** c, 2) for c in range(3)] == [2.6, 1.3, 0.65]

# XcfyDj: cascade 0 over [0, 0.5] spacings, 4 directions, nearest upper probe only, 0.707 spacings away.
u = (0.5, 0.5)
outcomes = []
for k in range(4):
    angle = (k + 0.5) * math.pi / 2
    d = (math.cos(angle), math.sin(angle))
    root = far_root((0, 0), u, d, 0, 0.5)
    outcomes.append("miss" if root is None else "behind" if root <= 0 else "ahead")
assert sorted(outcomes) == ["ahead", "behind", "miss", "miss"]
