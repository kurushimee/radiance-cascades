"""Where the bilinear fix's chain of rays is broken, in flatland with 32 directions branching by 2 and intervals by 4.

A miss of a fixed ray reads the upper probe's child texel at the upper interval's start, in the child's centre
direction; that texel's own rays leave from the same distance in its children's centre directions, a quarter of the
child bin away. The chain from a probe outward is therefore continuous except for an arc of
`t_end(c) * pi / (2 * N(c+1))` at each hand-over into a cascade that is itself fixed: every cascade but the top.
"""
import math

N0 = 32


def gaps(t0, levels):
    return [t0 * 4 ** c * math.pi / (2 * N0 * 2 ** (c + 1)) for c in range(levels - 2)]


t_eq = N0 / (2 * math.pi)
# At the equal-error interval, four cascades: arcs of 1/8 and 1/4 of a cascade 0 spacing, 5.1 and 20.4 out.
assert [round(g, 3) for g in gaps(t_eq, 4)] == [0.125, 0.25]
assert [round(t_eq * 4 ** c, 1) for c in range(2)] == [5.1, 20.4]
# At a fifth of it, five cascades: three arcs of 1/40 to 1/10 of a spacing, 1.0 to 16.3 out.
assert [round(g, 3) for g in gaps(t_eq / 5, 5)] == [0.025, 0.05, 0.1]
# Each arc is t0 * pi * 2**c / (4 * N0): it doubles per cascade while its distance quadruples.
assert all(math.isclose(g, t_eq * math.pi * 2 ** c / (4 * N0)) for c, g in enumerate(gaps(t_eq, 6)))
print("ok")
