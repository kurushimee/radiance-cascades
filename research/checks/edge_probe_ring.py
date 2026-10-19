"""Memory of a one-probe ring around each upper cascade, and the share of a level that edge clamping affects."""


def ring_share(n, d):
    return ((n + 2) ** d - n ** d) / n ** d


def stack_overhead(n0, levels, d, children):
    """Ring memory over stack memory when spacing doubles per level and each parent has `children` directions per child direction."""
    counts = [n0 >> k for k in range(levels)]
    memory = [n ** d * children ** k for k, n in enumerate(counts)]
    ring = sum(m * ring_share(n, d) for k, (m, n) in enumerate(zip(memory, counts)) if k > 0)
    return ring / sum(memory)


def clamped_share(n, d):
    """Clamping makes the bilinear merge nearest within half an upper spacing of each face."""
    return 1 - (1 - 1 / n) ** d


assert round(100 * ring_share(64, 3), 1) == 9.7
assert round(100 * ring_share(4, 3), 1) == 237.5

# 64^3 cascade 0 with five levels above it: 4 directions per parent halve memory per level, 8 keep it constant.
assert round(100 * stack_overhead(64, 6, 3, 4), 1) == 35.2
assert round(100 * stack_overhead(64, 6, 3, 8), 1) == 182.5

# A 512^2 2D stack down to 8^2 with 4 directions per parent, constant memory per level.
assert round(100 * stack_overhead(512, 7, 2, 4), 1) == 15.3

assert round(100 * clamped_share(4, 3), 1) == 57.8
assert round(100 * clamped_share(4, 2), 1) == 43.8
