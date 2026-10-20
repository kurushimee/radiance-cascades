"""Error of n bounces of the frozen solve against n exact bounces, in the closed flatland rooms (Figure 1)."""
import matplotlib.pyplot as plt
import numpy as np

from common import CLOSED, MERGES, OFFSETS, WIDTH, Flat, cached, legend_below, params, rd, relative_rmse, save

BOUNCES = 16
ALBEDOS = (0.5, 0.9)


def compute():
    out = {}
    for name in CLOSED:
        flat = Flat(name)
        E, sky, where = flat.patches.emission, flat.sky, flat.receivers
        for merge in MERGES:
            estimates = [flat.estimate(params(), merge, offset)[0] for offset in OFFSETS]
            for albedo in ALBEDOS:
                K = flat.bounce_matrix(flat.exact, albedo)
                exact = rd.plain(lambda L: E + K @ np.append(L, sky), E, BOUNCES)
                curves = []
                for estimate in estimates:
                    K_hat = flat.bounce_matrix(estimate, albedo)
                    steps = rd.plain(lambda L: E + K_hat @ np.append(L, sky), E, BOUNCES)
                    curves.append([relative_rmse(a, b, where) for a, b in zip(steps, exact)])
                out[f"{name}/{merge}/{albedo}"] = np.mean(curves, axis=0).tolist()
    return out


def main():
    results = cached("teaser", compute)
    fig, axes = plt.subplots(1, len(CLOSED), figsize=(WIDTH, 1.9), sharey=True)
    bounces = np.arange(1, BOUNCES + 1)
    for ax, name in zip(axes, CLOSED):
        for merge, colour in zip(MERGES, ("C0", "C1")):
            for albedo, style in zip(ALBEDOS, ("--", "-")):
                ax.plot(bounces, results[f"{name}/{merge}/{albedo}"], style, color=colour,
                        label=f"{merge.replace('_', ' ')}, albedo {albedo}")
        ax.set_yscale("log")
        ax.set_title(name.replace("_", " "))
        ax.set_xlabel("bounces")
    axes[0].set_ylabel("relative RMSE")
    legend_below(fig, axes[0], 4, 0.16)
    save(fig, "teaser")
    for key, curve in results.items():
        print(key, " ".join(f"{e:.4f}" for e in curve[::3]), f"... {curve[-1]:.4f}")


if __name__ == "__main__":
    main()
