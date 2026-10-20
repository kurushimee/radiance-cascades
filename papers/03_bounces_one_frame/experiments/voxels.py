"""Bounces of the frozen 3D solve against a Monte Carlo reference: cost, leak deficit, dominant eigenvalues,
first-bounce and converged errors for four merges, passes to converge, and 128 directions (Figure 5, Tables 4 and 5)."""
import math

import matplotlib.pyplot as plt
import numpy as np
from scipy.sparse.linalg import LinearOperator, eigs

from common import CHOICES, SCENES3D, WIDTH, Vox, bias, cached, legend_below, rd, relative_rmse, save

ALBEDOS = (0.3, 0.6, 0.9)
PASSES = 30
FINE = (("room", "vanilla"), ("room", "trilinear fix"), ("thick room", "vanilla"), ("thick room", "trilinear fix"))


def dominant(matrix):
    values, vectors = eigs(matrix, k=1, which="LR")
    return float(values[0].real), np.abs(vectors[:, 0].real)


def eigenvalues(vox, frozen, deficit):
    """Dominant eigenvalues of the exact and the frozen bounce at the top albedo, the frozen one as the exact one
    lowered by the Perron-weighted leak deficit, and the converged bias predicted from the first bounce and the two."""
    albedo = ALBEDOS[-1]
    r = np.flatnonzero(vox.receivers)
    K = albedo * vox.exact[0][r][:, r]
    mu, right = dominant(K)
    left = dominant(K.T)[1]
    bounce, linear = vox.passes(frozen, albedo)
    E = vox.faces.emission
    first = vox.first_bounce(vox.exact[0], albedo)[r] - E[r]
    first_hat = bounce(E)[r] - E[r]

    def apply(x):
        full = np.zeros(vox.faces.size)
        full[r] = x.ravel()
        return linear(full)[r]

    out = {"mu": mu, "mu_hat": dominant(LinearOperator((len(r), len(r)), matvec=apply))[0]}
    out["bias_predicted"] = float((left @ first_hat) / (left @ first) * (1 - mu) / (1 - out["mu_hat"]) - 1)
    if deficit is not None:
        weight = left * right
        out["mu_predicted"] = mu * (1 - float((weight * deficit).sum() / weight.sum()))
    return out


def measure(vox, choice, n0=32):
    frozen = vox.frozen(choice, n0)
    where, faces = vox.receivers, vox.faces
    out = {"rays": frozen.cost["rays"], "steps": frozen.cost["steps"], "solve_reads": frozen.cost["reads"]}
    deficit = None
    if vox.sky == 0:
        deficit = 1 - frozen.irradiance(np.where(vox.inside, 1.0, 0.0), 0.0)[where] / math.pi
        out["deficit"] = float(deficit.mean())
    for albedo in ALBEDOS:
        bounce, linear = vox.passes(frozen, albedo)
        exact = [vox.converged(share, albedo) for share in vox.exact]
        first, first_hat = vox.first_bounce(vox.exact[0], albedo), bounce(faces.emission)
        estimates = rd.gmres(bounce, linear, faces.emission, PASSES)
        solved = estimates[-1]
        floor = relative_rmse(solved, exact[0], where)
        row = {"noise": relative_rmse(exact[1], exact[0], where), "first": relative_rmse(first_hat, first, where),
               "first_bias": bias(first_hat - faces.emission, first - faces.emission, where),
               "converged": floor, "bias": bias(solved, exact[0], where)}
        if albedo == ALBEDOS[-1]:
            runs = {"plain": rd.plain(bounce, faces.emission, PASSES), "tail": rd.tail(bounce, faces.emission, PASSES),
                    "gmres": estimates}
            for method, xs in runs.items():
                own = [relative_rmse(x, solved, where) for x in xs]
                row[f"{method}_needed"] = next((i + 1 for i, e in enumerate(own) if e <= floor), PASSES + 1)
        out[str(albedo)] = row
    out["pass_reads"] = frozen.reads + frozen.cost["rays"]
    out.update(eigenvalues(vox, frozen, deficit))
    return out


def compute():
    out = {}
    for name in SCENES3D:
        vox = Vox(name)
        for choice in CHOICES:
            out[f"{name}/{choice}/32"] = measure(vox, choice)
        for fine_name, choice in FINE:
            if fine_name == name:
                out[f"{name}/{choice}/128"] = measure(vox, choice, 128)
    return out


def passes_needed(count):
    return f">{PASSES}" if count > PASSES else str(count)


def main():
    results = cached("voxels", compute)
    fig, axes = plt.subplots(1, len(SCENES3D), figsize=(WIDTH, 2.0), sharey=True)
    for ax, name in zip(axes, SCENES3D):
        for i, choice in enumerate(CHOICES):
            r = results[f"{name}/{choice}/32"]
            ax.plot(ALBEDOS, [r[str(a)]["converged"] for a in ALBEDOS], "o-", color=f"C{i}", label=choice)
            ax.axhline(r[str(ALBEDOS[0])]["first"], color=f"C{i}", ls="--", lw=0.8)
        ax.set_title(name)
        ax.set_xlabel("albedo")
    axes[0].set_ylabel("relative RMSE")
    legend_below(fig, axes[0], 4, 0.14)
    save(fig, "voxels")

    print("| Scene | Merge | N0 | Rays | Steps | Reads, solve / pass | Deficit | mu | mu hat | Predicted | "
          "Bias at 0.9 | predicted | Passes at 0.9: plain / tail / GMRES |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for key, r in results.items():
        name, choice, n0 = key.split("/")
        last = r[str(ALBEDOS[-1])]
        deficit = f"{r['deficit']:.4f}" if "deficit" in r else "-"
        predicted = f"{r['mu_predicted']:.3f}" if "mu_predicted" in r else "-"
        passes = " / ".join(passes_needed(last[f"{m}_needed"]) for m in ("plain", "tail", "gmres"))
        print(f"| {name} | {choice} | {n0} | {r['rays'] / 1e6:.1f}M | {r['steps'] / 1e6:.1f}M | "
              f"{r['solve_reads'] / 1e6:.0f}M / {r['pass_reads'] / 1e6:.0f}M | {deficit} | {r['mu']:.3f} | "
              f"{r['mu_hat']:.3f} | {predicted} | {last['bias']:+.3f} | {r['bias_predicted']:+.3f} | {passes} |")

    print("\n| Scene | Merge | N0 | First bounce | " + " | ".join(f"Converged {a}" for a in ALBEDOS) + " | Noise |")
    print("|---|---|---|---|" + "---|" * len(ALBEDOS) + "---|")
    for key, r in results.items():
        name, choice, n0 = key.split("/")
        first = r[str(ALBEDOS[0])]
        converged = " | ".join(f"{r[str(a)]['converged']:.3f} ({r[str(a)]['bias']:+.3f})" for a in ALBEDOS)
        print(f"| {name} | {choice} | {n0} | {first['first']:.3f} ({first['first_bias']:+.3f}) | {converged} | "
              f"{r[str(ALBEDOS[-1])]['noise']:.4f} |")


if __name__ == "__main__":
    main()
