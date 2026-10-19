"""The cascade 0 interval and the interval overlap in 3D (figure parameters).

Prints the error at each t0 around the equal-error interval sqrt(N0/(4*pi)) for three direction counts, and the leak
and errors against the overlap, whose derived closing value is 0.75*sqrt(3) = 1.30 upper spacings.
"""
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullFormatter

from common import TEST, WIDTH, cached, evaluate, legend_below, params, save, vo

N0S = (8, 32, 128)
FACTORS = tuple(2 ** (k / 4) for k in range(-4, 5))
MERGES = ("vanilla", "self_test", "trilinear_fix")
OVERLAPS = (0.0, 0.33, 0.65, 1.0, 1.3, 1.6, 2.0)
ROOMS = ("room", "partition")
ALONG_AXES = vo.Params().rotation


def equal_error(n0):
    return math.sqrt(n0 / (4 * math.pi))


def compute():
    sweep = {f"{n0} {f} {m}": evaluate(ROOMS + ("sealed_1",), TEST, params(n0, f * equal_error(n0)), m)
             for n0 in N0S for f in FACTORS for m in MERGES}
    overlap = {f"{o} {m}": evaluate(("room", "sealed_1"), TEST, params(overlap=o), m)
               for o in OVERLAPS for m in ("vanilla", "self_test")}
    return {"sweep": sweep, "overlap": overlap}


def along_axes():
    """Vanilla at 32 directions with the map's poles and seams along the voxel axes."""
    return {str(f): evaluate(ROOMS, TEST, params(32, f * equal_error(32), rotation=ALONG_AXES)) for f in FACTORS}


def room_error(r):
    return float(np.mean([r[name]["error"] for name in ROOMS]))


def main():
    results = cached("parameters", compute)
    sweep, overlap = results["sweep"], results["overlap"]
    aligned = [room_error(r) for r in cached("parameters_along_axes", along_axes).values()]
    print("Room and partition error against t0 / sqrt(N0/(4 pi)):\n")
    print("| N0 | merge | " + " | ".join(f"{f:.2f}" for f in FACTORS) + " | best |")
    print("|---|---|" + "---|" * (len(FACTORS) + 1))
    for n0 in N0S:
        for m in MERGES:
            errors = [room_error(sweep[f"{n0} {f} {m}"]) for f in FACTORS]
            print(f"| {n0} | {m} | " + " | ".join(f"{100 * e:.1f}" for e in errors)
                  + f" | {FACTORS[int(np.argmin(errors))]:.2f} |")
    print("| 32 | vanilla, map along the axes | " + " | ".join(f"{100 * e:.1f}" for e in aligned)
          + f" | {FACTORS[int(np.argmin(aligned))]:.2f} |")
    print("\nOutside the sealed box, error against t0 / sqrt(N0/(4 pi)):\n")
    print("| N0 | merge | " + " | ".join(f"{f:.2f}" for f in FACTORS) + " | best |")
    print("|---|---|" + "---|" * (len(FACTORS) + 1))
    for n0 in N0S:
        for m in MERGES:
            errors = [sweep[f"{n0} {f} {m}"]["sealed_1"]["outside"] for f in FACTORS]
            print(f"| {n0} | {m} | " + " | ".join(f"{100 * e:.2f}" for e in errors)
                  + f" | {FACTORS[int(np.argmin(errors))]:.2f} |")
    print("\n| overlap | merge | leak | outside | room |")
    print("|---|---|---|---|---|")
    for o in OVERLAPS:
        for m in ("vanilla", "self_test"):
            r = overlap[f"{o} {m}"]
            print(f"| {o} | {m} | {100 * r['sealed_1']['leak']:.2f} | {100 * r['sealed_1']['outside']:.2f} "
                  f"| {100 * r['room']['error']:.1f} |")

    fig, (left, right) = plt.subplots(1, 2, figsize=(WIDTH, 3.0))
    styles = {"vanilla": "-", "self_test": ":", "trilinear_fix": "--"}
    for i, n0 in enumerate(N0S):
        for m in MERGES:
            left.plot(FACTORS, [room_error(sweep[f"{n0} {f} {m}"]) for f in FACTORS], styles[m], marker="o",
                      color=f"C{i}", label=f"$N_0={n0}$, {m.replace('_', ' ')}")
    left.plot(FACTORS, aligned, "-", marker="s", ms=3, color="0.5", label="$N_0=32$, vanilla, map along the axes")
    left.set(xscale="log", xlabel=r"$t_0/\sqrt{N_0/4\pi}$", ylabel="relative RMSE, room and partition")
    left.set_xticks(FACTORS, [f"{f:.2f}" for f in FACTORS], rotation=90)
    left.xaxis.set_minor_formatter(NullFormatter())
    for m, color in (("vanilla", "C0"), ("self_test", "C1")):
        right.plot(OVERLAPS, [100 * overlap[f"{o} {m}"]["sealed_1"]["leak"] for o in OVERLAPS], "-o", color=color,
                   label=f"{m.replace('_', ' ')}: leak")
    right.axvline(0.75 * math.sqrt(3), color="k", lw=0.5)
    right.set(xlabel="overlap, upper probe spacings", ylabel="sky leaked into a box, %")
    right.legend(frameon=False)
    legend_below(fig, left, 3, 0.2)
    save(fig, "parameters")


if __name__ == "__main__":
    main()
