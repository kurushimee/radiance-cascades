"""Seams at the hand-overs against interval overlap (figure seams), and the error and cost of the fixes (table).

Overlap is in upper probe spacings. The law: the mean length seen by neither cascade falls as mean_gap(o), and the
length seen by both grows as mean_gap(o) + o.
"""
import math

import matplotlib.pyplot as plt
import numpy as np

from common import (OFFSETS, SCENE_NAMES, WIDTH, cached, cost, equal_error_t0, exact_fluence, fl, jittered,
                    legend_below, params, placed, run, save)

FAR = 0.75 * math.sqrt(2)
OVERLAPS = (0.0, 0.25, 0.5, 0.75, FAR, 1.5)
SEAM_SCENES = ("wall", "penumbra", "room", "scatter")
T0S = (1.0, equal_error_t0(32))
FIXES = (("vanilla", 0.0, "vanilla"), ("overlap 0.5", 0.5, "vanilla"), ("overlap 1.06", FAR, "vanilla"),
         ("bilinear fix", 0.0, "bilinear_fix"))


def mean_gap(overlap, sign=1, samples=20_000):
    """Mean seam length in upper spacings, unseen (sign 1) or double-seen (sign -1), for cell-centred grids."""
    phi = (np.arange(samples) + 0.5) * 2 * math.pi / samples
    w = np.stack([np.cos(phi), np.sin(phi)], -1)
    total = 0.0
    for cx in (0, 1):
        for cy in (0, 1):
            weight = (0.25 if cx else 0.75) * (0.25 if cy else 0.75)
            total += weight * np.maximum(sign * (w @ np.array([cx - 0.25, cy - 0.25]) - overlap), 0).mean()
    return total


def seam_parts(name, t0, overlap, n, offset):
    """Mean magnitude of the unseen, double-seen and parallax parts at cascade n, over mean exact radiance."""
    scene, (lo, hi), _ = placed(name, offset)
    unseen, double, parallax = fl.split_spatial(scene, params(n0=32, t0=t0, overlap=overlap), lo, hi, n,
                                                samples=300, rays=16, seed=0)
    radiance = exact_fluence(name).mean() / fl.TAU
    return [float(np.abs(v).mean() / radiance) for v in (unseen, double, parallax)]


def compute():
    seam_tasks = [(name, t0, o, n, tuple(offset)) for name in SEAM_SCENES for t0 in T0S for o in OVERLAPS
                  for n in (0, 1) for offset in OFFSETS[:2]]
    seams = np.array([seam_parts(*task) for task in seam_tasks]).reshape(len(SEAM_SCENES), len(T0S), len(OVERLAPS), 2, 2, 3)
    fix_tasks = [(name, params(n0=32, t0=t0, overlap=o), merge) for t0 in T0S for _, o, merge in FIXES
                 for name in SCENE_NAMES]
    return {"seams": seams.mean(4).tolist(), "fixes": jittered(run, fix_tasks)}


def figure(seams):
    seams = np.array(seams)                                   # (scene, t0, overlap, cascade, part)
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.6), sharey=True)
    grid = np.linspace(0, 1.5, 61)
    for ax, (j, t0) in zip(axes, enumerate(T0S)):
        for i, name in enumerate(SEAM_SCENES):
            base = seams[i, j, 0, 0]
            ax.plot(OVERLAPS, seams[i, j, :, 0, 0] / base[0], "o-", color=f"C{i}", label=f"{name} unseen")
            ax.plot(OVERLAPS, seams[i, j, :, 0, 1] / base[1], "s:", color=f"C{i}", label=f"{name} double")
        ax.plot(grid, [mean_gap(o) / mean_gap(0) for o in grid], "k-", lw=1.4, alpha=0.5, label="law, unseen")
        ax.plot(grid, [mean_gap(o, -1) / mean_gap(0, -1) for o in grid], "k--", lw=1.4, alpha=0.5,
                label="law, double")
        ax.axvline(FAR, color="0.6", lw=0.6)
        ax.set(title=f"cascade 0, $t_0={t0:.2f}$", xlabel="overlap (upper spacings)", ylim=(0, 6))
    axes[0].set_ylabel("seam magnitude / value at no overlap")
    legend_below(fig, axes[0], 5, 0.16)
    save(fig, "seams")


def main():
    results = cached("seams", compute)
    figure(results["seams"])
    seams = np.array(results["seams"])
    print("Mean magnitudes at no overlap (unseen, double, parallax), cascades 0 and 1:")
    for i, name in enumerate(SEAM_SCENES):
        for j, t0 in enumerate(T0S):
            print(f"{name} t0={t0:.2f}: " + "; ".join(
                " ".join(f"{v:.4f}" for v in seams[i, j, 0, n]) for n in (0, 1)))
    print()
    print("| t0 | scene | " + " | ".join(label for label, _, _ in FIXES) + " |")
    print("|---|---|" + "---|" * len(FIXES))
    fixes = results["fixes"]
    for j, t0 in enumerate(T0S):
        for s, name in enumerate(SCENE_NAMES):
            row = [fixes[(j * len(FIXES) + f) * len(SCENE_NAMES) + s] for f in range(len(FIXES))]
            print(f"| {t0:.2f} | {name} | " + " | ".join(f"{r['linear'][0]:.3f} / {r['display'][0]:.4f}"
                                                        for r in row) + " |")
    print()
    print("Cost of each fix relative to vanilla (rays, fixed-step steps, mip steps):")
    for t0 in T0S:
        base = cost(params(n0=32, t0=t0))
        for label, o, merge in FIXES:
            c = cost(params(n0=32, t0=t0, overlap=o), merge)
            print(f"t0={t0:.2f} {label}: " + " ".join(f"{c[key] / base[key]:.2f}" for key in base))


if __name__ == "__main__":
    main()
