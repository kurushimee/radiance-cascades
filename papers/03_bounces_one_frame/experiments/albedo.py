"""Error of the converged frozen solve against albedo in flatland, with the first bounce's, the bias, and how much of
the error the dominant mode holds (Figure 3)."""
import matplotlib.pyplot as plt
import numpy as np

from common import (ALBEDOS, MERGES, OFFSETS, SCENES, WIDTH, Flat, bias, cached, legend_below, params, perron,
                    relative_rmse, rd, save)


def errors(flat, estimate, albedo):
    K, K_hat = flat.bounce_matrix(flat.exact, albedo), flat.bounce_matrix(estimate, albedo)
    E, sky, where = flat.patches.emission, flat.sky, flat.receivers
    exact, solved = rd.converged(K, E, sky), rd.converged(K_hat, E, sky)
    first, first_hat = E + K @ np.append(E, sky), E + K_hat @ np.append(E, sky)
    one_pass = (K_hat - K) @ np.append(exact, sky)
    _, left, right = perron(K)
    error = solved - exact
    along = right * (left @ error) / (left @ right)
    return {"first": relative_rmse(first_hat, first, where), "converged": relative_rmse(solved, exact, where),
            "first_bias": bias(first_hat - E, first - E, where), "bias": bias(solved, exact, where),
            "amplification": float(np.linalg.norm(error[where]) / np.linalg.norm(one_pass[where])),
            "dominant": float(np.linalg.norm(along[where]) / np.linalg.norm(error[where]))}


def compute():
    out = {}
    for name in SCENES:
        flat = Flat(name)
        for merge in MERGES:
            estimates = [flat.estimate(params(), merge, offset)[0] for offset in OFFSETS]
            for albedo in ALBEDOS:
                rows = [errors(flat, estimate, albedo) for estimate in estimates]
                out[f"{name}/{merge}/{albedo}"] = {key: float(np.mean([r[key] for r in rows])) for key in rows[0]}
    return out


def main():
    results = cached("albedo", compute)
    fig, axes = plt.subplots(1, len(SCENES), figsize=(WIDTH, 1.9), sharey=True)
    for ax, name in zip(axes, SCENES):
        for merge, colour in zip(MERGES, ("C0", "C1")):
            label = merge.replace("_", " ")
            rows = [results[f"{name}/{merge}/{a}"] for a in ALBEDOS]
            ax.plot(ALBEDOS, [r["converged"] for r in rows], "o-", color=colour, label=f"{label}, converged")
            ax.plot(ALBEDOS, [r["first"] for r in rows], "s--", color=colour, label=f"{label}, first bounce")
        ax.set_yscale("log")
        ax.set_title(name.replace("_", " "))
        ax.set_xlabel("albedo")
    axes[0].set_ylabel("relative RMSE")
    legend_below(fig, axes[0], 4, 0.16)
    save(fig, "albedo")

    print("| Scene | Merge | Albedo | First bounce | Converged | First-bounce bias | Bias | Amplification | Dominant |")
    print("|---|---|---|---|---|---|---|---|---|")
    for key, r in results.items():
        name, merge, albedo = key.split("/")
        print(f"| {name} | {merge} | {albedo} | {r['first']:.4f} | {r['converged']:.4f} | {r['first_bias']:+.4f} | "
              f"{r['bias']:+.4f} | {r['amplification']:.2f} | {r['dominant']:.2f} |")


if __name__ == "__main__":
    main()
