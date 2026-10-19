"""Share of the infinite-bounce indirect light that n bounces capture, and the size of a solve two LODs up.

Closed scene of uniform albedo rho: bounce k carries rho^k of the emitted light, so n bounces hold
1 - rho^n of the indirect light. Open scenes lose light to the sky at every bounce, so the closed scene
bounds what the missing bounces carry.
"""


def share(rho, n):
    return 1 - rho ** n


table = {rho: [round(share(rho, n), 3) for n in (1, 2, 3)] for rho in (0.3, 0.5, 0.8)}
assert table == {0.3: [0.7, 0.91, 0.973], 0.5: [0.5, 0.75, 0.875], 0.8: [0.2, 0.36, 0.488]}

# The second bounce's part of two bounces is rho / (1 + rho): a third at albedo 0.5.
assert round(0.5 ** 2 / (0.5 + 0.5 ** 2), 3) == round(0.5 / 1.5, 3) == 0.333

# Two LODs up the spacing is 4x: probes on surfaces fall 16x, probes filling a volume 64x.
assert (1 / 4) ** 2 == 1 / 16 and (1 / 4) ** 3 == 1 / 64
