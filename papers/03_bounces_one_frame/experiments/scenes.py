"""The flatland scenes, each side of each wall drawn by its exact converged radiance at albedo 0.7 (Figure 2)."""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm

from common import SCENES, WIDTH, Flat, rd, save

ALBEDO = 0.7
SIDE = 1.2  # how far each side's line is drawn off its wall, so both sides of a thin wall show


def pieces(flat):
    """The two ends of every patch, moved off the wall toward its side."""
    pt, scene = flat.patches, flat.walls.scene
    ends = np.empty((pt.size, 2, 2))
    for s in range(len(scene.a)):
        e = scene.b[s] - scene.a[s]
        left = np.array([-e[1], e[0]]) / np.linalg.norm(e)
        f = np.arange(pt.count[s] + 1)[:, None] / pt.count[s]
        points = scene.a[s] + f * e
        for side, sign in ((0, 1), (1, -1)):
            first = pt.first[s, side]
            ends[first:first + pt.count[s], 0] = points[:-1] + sign * SIDE * left
            ends[first:first + pt.count[s], 1] = points[1:] + sign * SIDE * left
    return ends


def main():
    fig, axes = plt.subplots(1, len(SCENES), figsize=(WIDTH, 2.0))
    norm = LogNorm(1e-2, 1.0)
    for ax, name in zip(axes, SCENES):
        flat = Flat(name)
        radiance = rd.converged(flat.bounce_matrix(flat.exact, ALBEDO), flat.patches.emission, flat.sky)
        shown = flat.receivers | (flat.patches.emission > 0)
        lines = LineCollection(pieces(flat)[shown], array=np.maximum(radiance[shown], 1e-2), cmap="inferno",
                               norm=norm, linewidths=1.6)
        ax.add_collection(lines)
        ax.set_xlim(-4, 132)
        ax.set_ylim(-4, 132)
        ax.set_aspect("equal")
        ax.set_facecolor("0.85")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(name.replace("_", " "))
    fig.colorbar(lines, ax=axes, shrink=0.8, label="radiance")
    save(fig, "scenes")


if __name__ == "__main__":
    main()
