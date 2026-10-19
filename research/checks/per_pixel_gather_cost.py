"""Reads per pixel: gathering every cascade per pixel against a top-down merge and a cascade 0 gather.

n cascades, branching K, D0 cascade 0 directions, 4 bilinear probes per read, no pre-averaging.
Cascade i holds probes_i * D0 * K^i values, and the merge into cascade i reads 4 * K values per value.
"""


def unrolled(n, k, d0):
    return 4 * n * d0 * k ** (n - 1)


def top_down(n, k, d0, probes0, pixels, spatial=4):
    merge = sum((probes0 / spatial ** i) * d0 * k ** i * 4 * k for i in range(n - 1))
    return 4 * d0 + merge / pixels


for k in (2, 4):
    for d0 in (4, 8):
        # One cascade: both read 4 probes per direction.
        assert top_down(1, k, d0, 1, 1) == unrolled(1, k, d0)
        for n in range(2, 7):
            dense = top_down(n, k, d0, probes0=1, pixels=1)
            assert unrolled(n, k, d0) / dense >= 2 * k / (1 + k) - 1e-12
            sparse = top_down(n, k, d0, probes0=1, pixels=1e6)
            assert abs(unrolled(n, k, d0) / sparse - n * k ** (n - 1)) < 1e-3 * n * k ** (n - 1)
