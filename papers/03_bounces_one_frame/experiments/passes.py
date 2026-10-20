"""Error against the number of passes of the frozen solve for plain bounces, the ambient term, the geometric tail and
GMRES in flatland (Figure 4, Table 2)."""
import matplotlib.pyplot as plt
import numpy as np

from common import MERGES, OFFSETS, SCENES, WIDTH, Flat, cached, legend_below, params, rd, relative_rmse, save

PASSES = 40
ALBEDOS = (0.5, 0.9)
METHODS = ("plain", "ambient", "tail", "gmres")


def runs(flat, estimate, albedo):
    E, sky, where = flat.patches.emission, flat.sky, flat.receivers
    exact = rd.converged(flat.bounce_matrix(flat.exact, albedo), E, sky)
    K = flat.bounce_matrix(estimate, albedo)
    solved = rd.converged(K, E, sky)
    bounce = lambda L: E + K @ np.append(L, sky)  # noqa: E731
    linear = lambda v: K[:, :-1] @ v  # noqa: E731
    estimates = {"plain": rd.plain(bounce, E, PASSES),
                 "ambient": rd.ambient(bounce, E, PASSES, flat.patches.albedo, flat.inside),
                 "tail": rd.tail(bounce, E, PASSES), "gmres": rd.gmres(bounce, linear, E, PASSES)}
    floor = relative_rmse(solved, exact, where)
    out = {"floor": floor}
    for method, xs in estimates.items():
        out[method] = [relative_rmse(x, exact, where) for x in xs]
        own = [relative_rmse(x, solved, where) for x in xs]
        out[f"{method}_needed"] = next((i + 1 for i, e in enumerate(own) if e <= floor), PASSES + 1)
    return out


def compute():
    out = {}
    for name in SCENES:
        flat = Flat(name)
        for merge in MERGES:
            estimates = [flat.estimate(params(), merge, offset)[0] for offset in OFFSETS]
            for albedo in ALBEDOS:
                rows = [runs(flat, estimate, albedo) for estimate in estimates]
                out[f"{name}/{merge}/{albedo}"] = {
                    key: (np.mean([r[key] for r in rows], axis=0).tolist()) for key in rows[0]}
    return out


def main():
    results = cached("passes", compute)
    fig, axes = plt.subplots(len(MERGES), len(SCENES), figsize=(WIDTH, 3.3), sharex=True, sharey="row")
    passes = np.arange(1, PASSES + 1)
    for row, merge in zip(axes, MERGES):
        for ax, name in zip(row, SCENES):
            r = results[f"{name}/{merge}/0.9"]
            for method in METHODS:
                ax.plot(passes, r[method], label="GMRES" if method == "gmres" else method)
            ax.axhline(r["floor"], color="0.4", ls=":", lw=0.8, label="converged frozen solve")
            ax.set_yscale("log")
            ax.set_title(f"{name.replace('_', ' ')}, {merge.replace('_', ' ')}")
        row[0].set_ylabel("relative RMSE")
    for ax in axes[-1]:
        ax.set_xlabel("passes")
    legend_below(fig, axes[0, 0], 5, 0.1)
    save(fig, "passes")

    print("| Scene | Merge | Albedo | Floor | " + " | ".join(METHODS) + " |")
    print("|---|---|---|---|" + "---|" * len(METHODS))
    for key, r in results.items():
        name, merge, albedo = key.split("/")
        needed = " | ".join(f"{r[f'{m}_needed']:.1f}" for m in METHODS)
        print(f"| {name} | {merge} | {albedo} | {r['floor']:.4f} | {needed} |")


if __name__ == "__main__":
    main()
