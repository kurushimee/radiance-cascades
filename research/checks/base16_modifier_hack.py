"""Per-cascade penumbra ratios of jason.today's 2D layout with and without modifierHack.

Cascade k at base B and p pixels between base probes: B^(k+1) rays, spacing p*sqrt(B)^k,
interval start M*B^(k-1) (0 for k = 0) and length M*B^k, counted from the start.
"""
import math


def ratios(base, p, m, cascades=4):
    """Return (gap/spacing, spacing/start) per cascade; start ratio is None for cascade 0."""
    rows = []
    for k in range(cascades):
        start = 0.0 if k == 0 else m * base ** (k - 1)
        end = start + m * base ** k
        gap = end * 2 * math.pi / base ** (k + 1)
        spacing = p * math.sqrt(base) ** k
        rows.append((gap / spacing, None if k == 0 else spacing / start))
    return rows


def jason_hack(base, p):
    return 1.0 if base < 16 else math.sqrt(base)


def community_hack(base, p):
    return p if base < 16 else math.sqrt(base)


# A constant multiplier scales every cascade's ratios alike, so it moves the balance, not the trend.
for base in (4, 16, 64):
    plain, scaled = ratios(base, 1, 1.0), ratios(base, 1, 4.0)
    for (g1, _), (g4, _) in zip(plain, scaled):
        assert math.isclose(g4 / g1, 4.0)

# From cascade 1 up, gap/spacing falls by sqrt(B) per cascade: x0.5 at base 4, x0.25 at base 16.
for base in (4, 16, 64):
    rows = ratios(base, 1, 1.0, 5)
    for k in range(1, 4):
        assert math.isclose(rows[k + 1][0] / rows[k][0], 1 / math.sqrt(base))

# jason.today's 1 : sqrt(B) gives base 16's cascade 0 base 4's gap/spacing, pi/(2p), at every p.
for p in (1, 2, 4):
    base4 = ratios(4, p, jason_hack(4, p))[0][0]
    base16 = ratios(16, p, jason_hack(16, p))[0][0]
    assert math.isclose(base4, math.pi / (2 * p)) and math.isclose(base16, base4)

# The community demo's p : sqrt(B) keeps base 4 at pi/2 for every p but matches it at base 16 only at p = 1.
for p in (1, 2, 4):
    base4 = ratios(4, p, community_hack(4, p))[0][0]
    base16 = ratios(16, p, community_hack(16, p))[0][0]
    assert math.isclose(base4, math.pi / 2)
    assert math.isclose(base16, math.pi / (2 * p))

# sqrt(B) equals the matching multiplier B/4 only at base 16; at base 64 cascade 0 gets half of base 4's ratio.
assert math.isclose(ratios(64, 1, jason_hack(64, 1))[0][0], math.pi / 4)

# Without the multiplier base 16 is spatially dominated from cascade 0 up; with it the balance lies between cascades 0 and 1.
untuned = [g for g, _ in ratios(16, 1, 1.0)]
tuned = [g for g, _ in ratios(16, 1, 4.0)]
assert all(g < 0.4 for g in untuned)
assert tuned[0] > 1 > tuned[1]
assert [round(g, 3) for g in tuned[:3]] == [1.571, 0.417, 0.104]
assert [round(g, 3) for g, _ in ratios(4, 1, 1.0)[:3]] == [1.571, 0.982, 0.491]

# Spacing over interval start at cascade 1: p*sqrt(B)/M, so 2 at base 4, 4 untuned and 1 tuned at base 16.
assert math.isclose(ratios(4, 1, 1.0)[1][1], 2.0)
assert math.isclose(ratios(16, 1, 1.0)[1][1], 4.0)
assert math.isclose(ratios(16, 1, 4.0)[1][1], 1.0)
