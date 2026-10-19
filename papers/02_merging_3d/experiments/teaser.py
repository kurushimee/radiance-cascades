"""Fluence in a slice through the partition's doorway (figure teaser): the reference, vanilla, the self test and the
lowest-error choice of merges per hand-over."""
import matplotlib.pyplot as plt
import numpy as np

import handover
from common import PARAMS, TEST, WIDTH, cached, save, scene, vo

OFFSET = TEST[0]
SLICE = 20  # the doorway's centre, in voxels from the room's corner


def panels():
    volume, _ = scene("partition", OFFSET)
    lo = np.asarray(OFFSET)
    y = lo[1] + SLICE
    cells = np.array([(x, y, z) for x in range(lo[0] + 2, lo[0] + 38) for z in range(lo[2] + 2, lo[2] + 38)])
    empty = ~volume.solid[tuple(cells.T)]
    points = cells[empty] + 0.5
    chosen = cached("handover", handover.compute)["chosen"]["lowest error"].split()
    out = {"reference": vo.reference_fluence(volume, points, r=128, seed=3)}
    for title, merge, merges in (("vanilla", "vanilla", None), ("self test", "self_test", None),
                                 ("per hand-over", "vanilla", chosen)):
        fluence, _ = vo.solve(volume, PARAMS, merge, merges=merges)
        out[title] = fluence[tuple(np.floor(points).astype(int).T)]
    return {"empty": empty.tolist(), **{k: v.tolist() for k, v in out.items()}}


def main():
    results = cached("teaser", panels)
    empty = np.array(results.pop("empty"))
    fig, axes = plt.subplots(1, len(results), figsize=(WIDTH, 1.6), layout="constrained")
    images = {}
    for title, values in results.items():
        image = np.full(empty.shape, np.nan)
        image[empty] = np.log10(np.maximum(values, 1e-4))
        images[title] = image.reshape(36, 36).T
    for ax, (title, image) in zip(axes, images.items()):
        shown = ax.imshow(image, origin="lower", vmin=-2.5, vmax=1.5, cmap="inferno")
        ax.set_title(title, fontsize=7)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.colorbar(shown, ax=axes, shrink=0.9, label=r"$\log_{10}$ fluence")
    save(fig, "teaser")


if __name__ == "__main__":
    main()
