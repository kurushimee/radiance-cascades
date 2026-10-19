"""Memory of a 3D HRC frustum stack, the N^4 count of lines, and HRC stopped at segment length d.

A frustum has, at level L, N/2^L planes of N^2 probes with (2^L + 1)^2 directions. Six frusta at 8 B
per interval (RGBA16F). Lines joining cell centres of two opposite faces are N^2 * N^2 per axis family,
and any two of them differ by at least one cell at a face, so a store that resolves each holds N^4 values.
"""
import math


def level(n, l):
    return n / 2 ** l * n * n * (2 ** l + 1) ** 2


def stack(n, levels):
    return sum(level(n, l) for l in range(levels))


def gigabytes(n, levels):
    return 6 * 8 * stack(n, levels) / 1e9


# The memory model in holographic_rc.md: 1.20 N^4 below the top level at N = 64, 2.23 N^4 with it.
assert round(stack(64, 6) / 64 ** 4, 2) == 1.20
assert round(stack(64, 7) / 64 ** 4, 2) == 2.23
assert math.isclose(gigabytes(128, 7), 14.39, abs_tol=0.01)

# The line count grows 16x per doubling of N, as the frustum stack does asymptotically.
assert all((2 * n) ** 4 / n ** 4 == 16 for n in (16, 32, 64))
assert 15 < stack(256, 8) / stack(128, 7) < 16

# HRC up to segment length d = 2^L (levels 0..L), vanilla RC beyond: intervals per frustum in units of N^3.
assert level(1, 0) == 4
assert [round(stack(1, l + 1), 1) for l in (3, 4)] == [24.9, 42.9]
assert [round(gigabytes(64, l + 1), 2) for l in (3, 4)] == [0.31, 0.54]
assert [round(gigabytes(128, l + 1), 1) for l in (3, 4)] == [2.5, 4.3]
assert round(6 * 8 * level(128, 0) / 1e9, 2) == 0.40
