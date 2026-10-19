"""Error against the cascade 0 interval t0 at K = 2, l = 4 (figures t0_sweep, t0_display and t0_balance).

Prints, per scene and sampling, the error-optimal t0 by each metric and where the angular and spatial terms cross.
"""
import matplotlib.pyplot as plt
import numpy as np

from common import (OFFSETS, SCENE_NAMES, WIDTH, budget, cached, equal_error_t0, jittered, legend_below, params, run,
                    save)

T0 = 0.5 * np.sqrt(2) ** np.arange(11)
SAMPLING = ((8, 1), (8, 4), (32, 1))  # (cascade 0 directions, rays per cone)
BALANCE = ((8, 1), (32, 1))
TERM_KEYS = ("total", "angular", "spatial", "gather")


def compute():
    sweep = [(name, params(n0=n0, t0=t0, s=s), "vanilla") for name in SCENE_NAMES for n0, s in SAMPLING for t0 in T0]
    terms = [(name, params(n0=n0, t0=t0, s=s)) for name in SCENE_NAMES for n0, s in BALANCE for t0 in T0]
    return {"sweep": jittered(run, sweep), "terms": jittered(budget, terms, OFFSETS[:2])}


def table(results, sampling, key):
    """results[...] as an array (scene, sampling, t0) of (mean, sd) pairs for metric `key`."""
    return np.array([r[key] for r in results]).reshape(len(SCENE_NAMES), len(sampling), len(T0), 2)


def optimum(values):
    """t0 at the minimum of a parabola in log t0 through the best grid point and its neighbours, as text.

    A minimum at either end of the sweep is reported as a bound.
    """
    best = int(np.argmin(values))
    if best == 0:
        return f"<= {T0[0]:.2f}"
    if best == len(values) - 1:
        return f">= {T0[-1]:.2f}"
    i = best
    x, y = np.log(T0[i - 1:i + 2]), values[i - 1:i + 2]
    a, b, _ = np.polyfit(x, y, 2)
    return f"{np.exp(-b / (2 * a)):.2f}"


def crossing(angular, spatial):
    """t0 where the angular and spatial curves cross, interpolated in log-log; None if they do not."""
    diff = np.log(angular) - np.log(spatial)
    for i in range(len(diff) - 1):
        if diff[i] <= 0 < diff[i + 1] or diff[i] >= 0 > diff[i + 1]:
            f = diff[i] / (diff[i] - diff[i + 1])
            return float(np.exp(np.log(T0[i]) + f * (np.log(T0[i + 1]) - np.log(T0[i]))))
    return None


def mark_rules(ax):
    for n0 in (8, 32):
        ax.axvline(equal_error_t0(n0), color="0.6", ls="--", lw=0.6)
    ax.axvline(np.sqrt(2), color="0.6", ls=":", lw=0.6)


def sweep_figure(sweep, key, stem):
    fig, axes = plt.subplots(2, 3, figsize=(WIDTH, 3.5), sharex=True)
    for ax, name, rows in zip(axes.flat, SCENE_NAMES, sweep):
        for (n0, s), row in zip(SAMPLING, rows):
            ax.errorbar(T0, row[:, 0], yerr=row[:, 1], marker="o", capsize=1.5, label=f"$N_0={n0}$, $s={s}$")
        mark_rules(ax)
        ax.set(xscale="log", yscale="log", title=name)
    for ax in axes[1]:
        ax.set_xlabel("$t_0/\\Delta s_0$")
    for ax in axes[:, 0]:
        ax.set_ylabel("relative RMSE" if key == "linear" else "display RMSE")
    legend_below(fig, axes[0, 0], 3, 0.05)
    save(fig, stem)


def balance_figure(terms):
    fig, axes = plt.subplots(2, 3, figsize=(WIDTH, 3.5), sharex=True)
    j = BALANCE.index((32, 1))
    for ax, name, scene_terms in zip(axes.flat, SCENE_NAMES, terms):
        for key, style in (("total", "k-"), ("angular", "C0--"), ("spatial", "C3-.")):
            ax.plot(T0, scene_terms[key][j], style, marker="o", label=key)
        mark_rules(ax)
        ax.set(xscale="log", yscale="log", title=name)
    for ax in axes[1]:
        ax.set_xlabel("$t_0/\\Delta s_0$")
    for ax in axes[:, 0]:
        ax.set_ylabel("relative RMS")
    legend_below(fig, axes[0, 0], 3, 0.05)
    save(fig, "t0_balance")


def main():
    results = cached("t0_sweep", compute)
    linear, display = (table(results["sweep"], SAMPLING, key) for key in ("linear", "display"))
    sweep_figure(linear, "linear", "t0_sweep")
    sweep_figure(display, "display", "t0_display")

    terms = []
    for i in range(len(SCENE_NAMES)):
        chunk = results["terms"][i * len(BALANCE) * len(T0):(i + 1) * len(BALANCE) * len(T0)]
        terms.append({key: np.array([r[key][0] for r in chunk]).reshape(len(BALANCE), len(T0)) for key in TERM_KEYS})
    balance_figure(terms)

    print("| scene | sampling | t0* linear | t0* display | crossing | equal error |")
    print("|---|---|---|---|---|---|")
    for i, name in enumerate(SCENE_NAMES):
        for j, (n0, s) in enumerate(SAMPLING):
            cross = None
            if (n0, s) in BALANCE:
                b = BALANCE.index((n0, s))
                cross = crossing(terms[i]["angular"][b], terms[i]["spatial"][b])
            cross_text = "none" if cross is None else f"{cross:.2f}"
            print(f"| {name} | N0={n0}, s={s} | {optimum(linear[i, j, :, 0])} | "
                  f"{optimum(display[i, j, :, 0])} | {cross_text} | {equal_error_t0(n0):.2f} |")

    print()
    print("Worst ratio over scenes of the error at each t0 to that scene's best error:")
    for key, values in (("linear", linear), ("display", display)):
        for j, (n0, s) in enumerate(SAMPLING):
            ratio = (values[:, j, :, 0] / values[:, j, :, 0].min(1, keepdims=True)).max(0)
            print(f"{key} N0={n0}, s={s}: best t0 {T0[np.argmin(ratio)]:.2f} with ratio {ratio.min():.2f}; "
                  + " ".join(f"{t:.2f}:{r:.2f}" for t, r in zip(T0, ratio)))

    print()
    print("Log-log slopes of the angular and spatial terms against t0 (N0 = 32):")
    j = BALANCE.index((32, 1))
    for name, scene_terms in zip(SCENE_NAMES, terms):
        slopes = [np.polyfit(np.log(T0), np.log(scene_terms[key][j]), 1)[0] for key in ("angular", "spatial")]
        print(f"{name}: angular {slopes[0]:+.2f}, spatial {slopes[1]:+.2f}")


if __name__ == "__main__":
    main()
