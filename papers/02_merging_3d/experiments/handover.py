"""Merges hand-over by hand-over (figure handover, tables handover and chosen).

Each merge replaces vanilla at one hand-over; leaks are attributed by leaving one hand-over to a merge and sealing
the others with the trilinear fix. Merges are then chosen per hand-over on the training offsets and reported on the
held-out ones.
"""
import itertools

import matplotlib.pyplot as plt
import numpy as np

from common import (HAND_OVERS, HEADER, NAMES, SCENES, TEST, TRAIN, WIDTH, cached, cells, evaluate, label, legend_below,
                    save, vo)

ROOMS = ("room", "partition")
LEAK_MERGES = ("vanilla", "parallax", "depth_surface", "self_test", "depth_self_test", "sphere_fix")
SEALING = ("kuhn_fix", "trilinear_fix")
FREE_STEPS = 1.05


def error(result):
    return float(np.mean([result[name]["error"] for name in ROOMS]))


def at(hand_over, merge, rest="vanilla"):
    merges = [rest] * HAND_OVERS
    merges[hand_over] = merge
    return merges


def compute():
    base = evaluate(ROOMS + ("sealed_1",), TRAIN)
    marginal = {f"{h} {m}": evaluate(ROOMS + ("sealed_1",), TRAIN, merges=at(h, m))
                for h in range(HAND_OVERS) for m in vo.MERGES}
    attribution = {f"{h} {m}": evaluate(("sealed_1",), TRAIN, merges=at(h, m, "trilinear_fix"))["sealed_1"]["leak"]
                   for h in range(HAND_OVERS) for m in LEAK_MERGES}
    candidates = []
    for h in range(HAND_OVERS):
        ranked = sorted(vo.MERGES, key=lambda m: error(marginal[f"{h} {m}"]))
        candidates.append(sorted(set(ranked[:4]) | set(SEALING)))
    combos = {}
    for merges in itertools.product(*candidates):
        r = evaluate(ROOMS + ("sealed_1",), TRAIN, merges=list(merges))
        combos[" ".join(merges)] = {"error": error(r), "leak": r["sealed_1"]["leak"],
                                    "steps": r["cost"]["steps"] / base["cost"]["steps"]}
    chosen = {
        "free": min((k for k, v in combos.items() if v["steps"] <= FREE_STEPS), key=lambda k: combos[k]["error"]),
        "sealed": min((k for k, v in combos.items() if v["leak"] < 5e-4), key=lambda k: combos[k]["error"]),
        "lowest error": min(combos, key=lambda k: combos[k]["error"]),
    }
    test = {key: evaluate(SCENES, TEST, merges=merges.split()) for key, merges in chosen.items()}
    test["vanilla"] = evaluate(SCENES, TEST)
    return {"base": base, "marginal": marginal, "attribution": attribution, "candidates": candidates,
            "combos": combos, "chosen": chosen, "test": test}


def main():
    results = cached("handover", compute)
    base, marginal = results["base"], results["marginal"]
    print("Training offsets; change of the room and partition error, and the sealed box's leak, with each merge at one"
          " hand-over and vanilla at the others:\n")
    print("| merge | " + " | ".join(f"hand-over {h}: error, leak" for h in range(HAND_OVERS)) + " |")
    print("|---|" + "---|" * HAND_OVERS)
    for m in vo.MERGES:
        parts = []
        for h in range(HAND_OVERS):
            r = marginal[f"{h} {m}"]
            parts.append(f"{100 * (error(r) / error(base) - 1):+.0f}%, {100 * r['sealed_1']['leak']:.2f}%")
        print(f"| {NAMES[m]} | " + " | ".join(parts) + " |")
    print(f"\nVanilla everywhere: error {100 * error(base):.1f}%, leak {100 * base['sealed_1']['leak']:.2f}%")
    print("\nLeak (% of the sky) with one hand-over left to a merge and the others sealed by the trilinear fix:\n")
    print("| merge | " + " | ".join(f"hand-over {h}" for h in range(HAND_OVERS)) + " |")
    print("|---|" + "---|" * HAND_OVERS)
    for m in LEAK_MERGES:
        print(f"| {NAMES[m]} | " + " | ".join(f"{100 * results['attribution'][f'{h} {m}']:.2f}"
                                             for h in range(HAND_OVERS)) + " |")
    print("\nCandidates per hand-over:", [[NAMES[m] for m in c] for c in results["candidates"]])
    print(f"{len(results['combos'])} combinations tried on the training offsets.\n")
    test = results["test"]
    base_cost = test["vanilla"]["cost"]
    print(f"| choice | merges by hand-over | training error | {HEADER} | steps | reads |")
    print("|---|---|---|" + "---|" * 10)
    for key in ("vanilla", "free", "sealed", "lowest error"):
        r = test[key]
        merges = "vanilla" if key == "vanilla" else label(NAMES[m] for m in results["chosen"][key].split())
        train = error(base) if key == "vanilla" else results["combos"][results["chosen"][key]]["error"]
        cost = " | ".join(f"{r['cost'][k] / base_cost[k]:.2f}" for k in ("steps", "reads"))
        print(f"| {key} | {merges} | {100 * train:.1f} | {cells(r)} | {cost} |")

    fig, (left, right) = plt.subplots(1, 2, figsize=(WIDTH, 2.9), sharey=True)
    ys = np.arange(len(vo.MERGES))
    for h in range(HAND_OVERS):
        change = [100 * (error(marginal[f"{h} {m}"]) / error(base) - 1) for m in vo.MERGES]
        leak = [100 * marginal[f"{h} {m}"]["sealed_1"]["leak"] for m in vo.MERGES]
        left.plot(change, ys + 0.2 * (h - 1), "o", color=f"C{h}", label=f"hand-over {h}")
        right.plot(leak, ys + 0.2 * (h - 1), "o", color=f"C{h}")
    left.axvline(0, color="k", lw=0.5)
    right.axvline(100 * base["sealed_1"]["leak"], color="k", lw=0.5)
    left.set(yticks=ys, yticklabels=[NAMES[m] for m in vo.MERGES], xlabel="change of error, %")
    left.set_xscale("symlog", linthresh=10)
    right.set(xlabel="sky leaked into the box, %")
    left.invert_yaxis()
    legend_below(fig, left, 3, 0.1)
    save(fig, "handover")


if __name__ == "__main__":
    main()
