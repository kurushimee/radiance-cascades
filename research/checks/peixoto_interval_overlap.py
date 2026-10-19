"""Peixoto's adjusted intervals and their overlap with the cascade below, in upper probe spacings."""
import math


def sign(x):
    return (x > 0) - (x < 0)


def intervals(cascades=5):
    out = []
    for i in range(cascades):
        minimum = 4 * (4 ** i - 1) // 3
        length = 4 * 4 ** i
        start = minimum - (length // 4) * sign(i - 1)
        out.append((start, minimum + length))
    return out


rows = intervals()
assert rows == [(1, 4), (4, 20), (4, 84), (20, 340), (84, 1364)]

# From cascade 2 up each cascade starts at the unadjusted start of the one below, re-tracing its whole interval.
for i in range(2, 5):
    assert rows[i][0] == 4 * (4 ** (i - 1) - 1) // 3

# Overlap with the lower interval, in this cascade's probe spacing 2^(i+1): 2^(i-1), against the sqrt(2) rule.
overlap = [(rows[i - 1][1] - rows[i][0]) / 2 ** (i + 1) for i in range(1, 5)]
assert overlap == [0.0, 2.0, 4.0, 8.0]
assert [round(o / math.sqrt(2), 1) for o in overlap[1:]] == [1.4, 2.8, 5.7]

# Cascade 0 starts 1 px out from probes 2 px apart, and no cascade traces [0, 1).
assert min(start for start, _ in rows) == 1
