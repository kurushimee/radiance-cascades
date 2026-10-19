"""Interval scaling and the error-cost trade-off over all parameters (figures l_sweep and pareto).

Prints the best t0 per scaling, the Pareto-optimal settings, and where the published rules sit against the front.
"""
import math

import matplotlib.pyplot as plt
import numpy as np

from common import (OFFSETS, SCENE_NAMES, WIDTH, cached, cost, equal_error_t0, jittered, legend_below, params, run,
                    save)

FAR = 0.75 * math.sqrt(2)
L_VALUES = {2: (2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0), 4: (3.0, 3.5, 4.0, 5.0, 6.0, 8.0)}
L_T0 = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
# (K, N0). K = 4 starts at l = 3: below it the top cascades, which hold 4x more directions per level on grids no
# smaller than a few probes, trace hundreds of millions of rays.
L_SCHEMES = ((2, 32), (4, 4))
RULES = {
    "2x/4x, diagonal t0": dict(n0=4, k=4, l=4.0, t0=math.sqrt(2)),
    "K=2, l=4, t0=1": dict(n0=32, k=2, l=4.0, t0=1.0),
    "equal error": dict(n0=32, k=2, l=4.0, t0=equal_error_t0(32)),
    "equal error, N0=8": dict(n0=8, k=2, l=4.0, t0=equal_error_t0(8)),
}
RANDOM = 48


def random_configs(seed=3):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(RANDOM):
        k = int(rng.choice((2, 4)))
        out.append((dict(n0=int(rng.choice((4, 8, 16, 32, 64) if k == 2 else (4, 8, 16))), k=k,
                         l=float(rng.choice((2.0, 3.0, 4.0, 6.0, 8.0) if k == 2 else (3.0, 4.0, 6.0, 8.0))),
                         t0=float(rng.choice(0.5 * np.sqrt(2) ** np.arange(9))), s=int(rng.choice((1, 2, 4))),
                         overlap=float(rng.choice((0.0, 0.5, FAR), p=(0.7, 0.15, 0.15)))),
                    "bilinear_fix" if rng.random() < 0.2 else "vanilla"))
    return out


def configs():
    """Every setting measured: the l sweep, the rules and random settings, as (kwargs, merge)."""
    out = [(dict(n0=n0, k=k, l=l, t0=t0), "vanilla") for k, n0 in L_SCHEMES for l in L_VALUES[k] for t0 in L_T0]
    out += [(kwargs, "vanilla") for kwargs in RULES.values()]
    return out + random_configs()


def compute():
    tasks = [(name, params(**kwargs), merge) for kwargs, merge in configs() for name in SCENE_NAMES]
    return jittered(run, tasks, OFFSETS[:3])


def per_config(results, key):
    return np.array([r[key][0] for r in results]).reshape(len(configs()), len(SCENE_NAMES))


def describe(kwargs, merge):
    text = f"K={kwargs['k']}, l={kwargs['l']:g}, N0={kwargs['n0']}, t0={kwargs['t0']:.2f}"
    if kwargs.get("s", 1) > 1:
        text += f", s={kwargs['s']}"
    if kwargs.get("overlap", 0):
        text += f", overlap={kwargs['overlap']:.2f}"
    return text + (", bilinear fix" if merge == "bilinear_fix" else "")


def front(costs, errors):
    """Indices of settings no other setting beats on both cost and error."""
    order = np.lexsort((errors, costs))
    best, out = np.inf, []
    for i in order:
        if errors[i] < best:
            best = errors[i]
            out.append(i)
    return np.array(out)


def l_blocks(linear):
    """Errors of the l sweep per scheme, as arrays (l, t0, scene)."""
    blocks, start = [], 0
    for k, _ in L_SCHEMES:
        count = len(L_VALUES[k]) * len(L_T0)
        blocks.append(linear[start:start + count].reshape(len(L_VALUES[k]), len(L_T0), len(SCENE_NAMES)))
        start += count
    return blocks


def l_figure(blocks):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.4), sharey=True)
    for ax, (k, n0), block in zip(axes, L_SCHEMES, blocks):
        best = block.min(1)
        for i, name in enumerate(SCENE_NAMES):
            ax.plot(L_VALUES[k], best[:, i], "-", color=f"C{i}", lw=0.7, label=name)
        ax.plot(L_VALUES[k], best.mean(1), "k-o", lw=1.4, label="mean")
        ax.axvline(2 * k, color="0.6", ls="--", lw=0.6)
        ax.set(xscale="log", yscale="log", title=f"$K={k}$, $N_0={n0}$, best $t_0$ per scene",
               xlabel="interval scale $l$")
        ax.set_xticks(L_VALUES[k])
        ax.set_xticklabels([f"{v:g}" for v in L_VALUES[k]])
        ax.minorticks_off()
    axes[0].set_ylabel("relative RMSE")
    legend_below(fig, axes[1], 7, 0.1)
    save(fig, "l_sweep")


def pareto_figure(all_configs, mean_error):
    costs = {key: np.array([cost(params(**kwargs), merge)[key] for kwargs, merge in all_configs])
             for key in ("rays", "steps_mip")}
    rule_index = {label: all_configs.index((kwargs, "vanilla")) for label, kwargs in RULES.items()}
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.8), sharey=True)
    fronts = {}
    for ax, (key, label) in zip(axes, (("rays", "rays per unit area"), ("steps_mip", "mip steps per unit area"))):
        fixed = np.array([merge == "bilinear_fix" for _, merge in all_configs])
        ax.scatter(costs[key][~fixed], mean_error[~fixed], s=4, color="0.6", label="vanilla or overlap")
        ax.scatter(costs[key][fixed], mean_error[fixed], s=6, marker="^", color="C2", label="bilinear fix")
        fronts[key] = front(costs[key], mean_error)
        ax.plot(costs[key][fronts[key]], mean_error[fronts[key]], "k-", lw=0.8, label="Pareto front")
        for i, (rule, index) in enumerate(rule_index.items()):
            ax.scatter(costs[key][index], mean_error[index], s=18, marker="*", color=f"C{i + 3}",
                       label=rule.replace("t0", "$t_0$").replace("N0", "$N_0$"))
        ax.set(xscale="log", yscale="log", xlabel=label)
    axes[0].set_ylabel("relative RMSE, mean over scenes")
    legend_below(fig, axes[1], 4, 0.14)
    save(fig, "pareto")
    return costs, fronts, rule_index


def main():
    results = cached("parameters", compute)
    all_configs = configs()
    linear, display = per_config(results, "linear"), per_config(results, "display")
    blocks = l_blocks(linear)
    l_figure(blocks)
    print("Best l per scheme (mean over scenes of the error at each scene's best t0):")
    for (k, n0), block in zip(L_SCHEMES, blocks):
        best = block.min(1).mean(1)
        print(f"K={k}, N0={n0}: " + " ".join(f"l={l:g}:{e:.3f}" for l, e in zip(L_VALUES[k], best)))
        for i, name in enumerate(SCENE_NAMES):
            j, t = np.unravel_index(np.argmin(block[:, :, i]), block[:, :, i].shape)
            print(f"  {name}: best l={L_VALUES[k][j]:g} at t0={L_T0[t]:g}, error {block[j, t, i]:.3f}")

    mean_error = linear.mean(1)
    costs, fronts, rule_index = pareto_figure(all_configs, mean_error)
    for key in ("rays", "steps_mip"):
        print(f"\nPareto front against {key}:")
        print("| setting | cost | relative RMSE | display RMSE |")
        print("|---|---|---|---|")
        for i in fronts[key]:
            print(f"| {describe(*all_configs[i])} | {costs[key][i]:.0f} | {mean_error[i]:.3f} | "
                  f"{display[i].mean():.4f} |")
        print("Rules: error over the best front error at no more cost:")
        for rule, i in rule_index.items():
            on_front = fronts[key][costs[key][fronts[key]] <= costs[key][i]]
            best = mean_error[on_front].min() if len(on_front) else np.nan
            print(f"  {rule}: cost {costs[key][i]:.0f}, error {mean_error[i]:.3f}, ratio {mean_error[i] / best:.2f}")


if __name__ == "__main__":
    main()
