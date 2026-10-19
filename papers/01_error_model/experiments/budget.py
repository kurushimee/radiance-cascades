"""Error budget: each term of the exact decomposition, per scene and setting (figures budget_bars, budget_maps).

Prints the table of terms and the share of each cascade in the spatial and angular terms.
"""
import math

import matplotlib.pyplot as plt
import numpy as np

from common import (SCENE_NAMES, WIDTH, budget, cached, equal_error_t0, exact_fluence, fl, jittered, params,
                    legend_below, placed, save, tonemap)

SETTINGS = {
    "A": ("$N_0=4$, $K=4$, $t_0=1.41$", params(n0=4, k=4, t0=math.sqrt(2))),
    "B": ("$N_0=32$, $K=2$, $t_0=1$", params(n0=32, t0=1.0)),
    "C": ("$N_0=32$, $K=2$, $t_0=5.09$", params(n0=32, t0=equal_error_t0(32))),
    "D": ("B with $\\Delta s_0=2$, $t_0=2$", params(ds0=2.0, n0=32, t0=2.0)),
}
TERMS = ("angular_radiance", "angular_transmittance", "correlation", "spatial", "gather", "total")
LABELS = ("angular radiance", "angular transmittance", "correlation", "spatial", "gather", "total")
MAP_SCENE, MAP_SETTING = "room", "B"


def compute():
    tasks = [(name, p) for _, p in SETTINGS.values() for name in SCENE_NAMES]
    return jittered(budget, tasks)


def bars(results):
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH, 3.6), sharey=True)
    x = np.arange(len(SCENE_NAMES))
    width = 0.8 / len(TERMS)
    for ax, (key, (label, _)), i in zip(axes.flat, SETTINGS.items(), range(len(SETTINGS))):
        rows = results[i * len(SCENE_NAMES):(i + 1) * len(SCENE_NAMES)]
        for j, (term, term_label) in enumerate(zip(TERMS, LABELS)):
            values = [max(r[term][0], 1e-5) for r in rows]
            ax.bar(x + (j - len(TERMS) / 2 + 0.5) * width, values, width, label=term_label,
                   color="k" if term == "total" else f"C{j}")
        ax.set(yscale="log", title=f"{key}: {label}", xticks=x, ylim=(1e-3, 2))
        ax.set_xticklabels(SCENE_NAMES, rotation=30)
    for ax in axes[:, 0]:
        ax.set_ylabel("relative RMS")
    legend_below(fig, axes[0, 0], len(TERMS), 0.06)
    save(fig, "budget_bars")


def image(scene, pixels, values, lo):
    """Pixel values as a 128 x 128 image, NaN inside solids."""
    out = np.full((128, 128), np.nan)
    ij = np.floor(pixels - lo).astype(int)
    out[ij[:, 1], ij[:, 0]] = values
    return out


def maps():
    scene, (lo, hi), pixels = placed(MAP_SCENE)
    p = SETTINGS[MAP_SETTING][1]
    parts = fl.decompose(scene, p, lo, hi, pixels)
    exact = exact_fluence(MAP_SCENE)
    angular = sum(parts["terms"][term].sum(0) for term in ("angular_radiance", "angular_transmittance", "correlation"))
    panels = [("exact fluence", exact), ("radiance cascades", parts["estimate"]),
              ("error", parts["estimate"] - exact), ("angular terms", angular),
              ("spatial term", parts["terms"]["spatial"].sum(0))]
    scale = np.percentile(np.abs(parts["estimate"] - exact), 99)
    fig, axes = plt.subplots(1, 5, figsize=(WIDTH, 1.35))
    for ax, (title, values) in zip(axes, panels):
        signed = title not in ("exact fluence", "radiance cascades")
        kwargs = dict(cmap="RdBu_r", vmin=-scale, vmax=scale) if signed else dict(cmap="magma", vmin=0,
                                                                                  vmax=np.percentile(exact, 99))
        ax.imshow(image(scene, pixels, values, lo), origin="lower", interpolation="nearest", **kwargs)
        ax.set(title=title, xticks=[], yticks=[])
    fig.tight_layout(pad=0.2)
    save(fig, "budget_maps")


def scenes():
    fig, axes = plt.subplots(1, 6, figsize=(WIDTH, 1.1))
    for ax, name in zip(axes, SCENE_NAMES):
        scene, (lo, _), pixels = placed(name)
        exact = exact_fluence(name)
        shown = tonemap(exact, 0.18 / exact.mean())
        ax.imshow(image(scene, pixels, shown, lo), origin="lower", interpolation="nearest", cmap="magma", vmin=0,
                  vmax=1)
        ax.set(title=name, xticks=[], yticks=[])
    fig.tight_layout(pad=0.2)
    save(fig, "scenes")


def main():
    results = cached("budget", compute)
    scenes()
    bars(results)
    maps()
    print("| setting | scene | " + " | ".join(LABELS) + " |")
    print("|---|---|" + "---|" * len(TERMS))
    for i, key in enumerate(SETTINGS):
        for name, r in zip(SCENE_NAMES, results[i * len(SCENE_NAMES):(i + 1) * len(SCENE_NAMES)]):
            print(f"| {key} | {name} | " + " | ".join(f"{r[term][0]:.3f}" for term in TERMS) + " |")
    print()
    print("Share of each cascade in the squared spatial and angular terms, mean over scenes:")
    for i, (key, (_, p)) in enumerate(SETTINGS.items()):
        rows = results[i * len(SCENE_NAMES):(i + 1) * len(SCENE_NAMES)]
        for kind in ("spatial", "angular"):
            shares = np.array([[r[f"{kind}_{m}"][0] ** 2 for m in range(p.levels)] for r in rows])
            shares = (shares / shares.sum(1, keepdims=True)).mean(0)
            print(f"{key} {kind}: " + " ".join(f"{s:.2f}" for s in shares))


if __name__ == "__main__":
    main()
