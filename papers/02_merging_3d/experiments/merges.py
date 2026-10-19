"""Every merge, the same at each hand-over, on every scene (table merges).

Prints the table: leaked energy, errors and cost relative to vanilla, all on the held-out offsets; vanilla's absolute
cost; and the noise of the room references, from a second reference with other rays.
"""
import numpy as np

from common import HEADER, NAMES, SCENES, TEST, cached, cells, evaluate, scene, sphere_where_defined, vo

ROWS = [(name, None) for name in vo.MERGES] + [("sphere where defined", sphere_where_defined())]
ROOMS = ("room", "partition")


def compute():
    return {name: evaluate(SCENES, TEST, merge=name if merges is None else "vanilla", merges=merges)
            for name, merges in ROWS}


def reference_noise():
    """Relative RMS noise of one reference, from the difference of two with independent rays."""
    out = {}
    for name in ROOMS:
        noise = []
        for offset in TEST:
            volume, data = scene(name, offset)
            other = vo.reference_fluence(volume, data["points"], r=96, seed=99)
            noise.append(np.sqrt(((data["reference"] - other) ** 2).mean() / 2) / data["reference"].mean())
        out[name] = float(np.mean(noise))
    return out


def main():
    results = cached("merges", compute)
    base = results["vanilla"]["cost"]
    print(f"| merge | {HEADER} | rays | steps | reads |")
    print("|---|" + "---|" * 11)
    for name, _ in ROWS:
        r = results[name]
        cost = " | ".join(f"{r['cost'][key] / base[key]:.2f}" for key in ("rays", "steps", "reads"))
        print(f"| {NAMES.get(name, name)} | {cells(r)} | {cost} |")
    print("\nVanilla, one solve of the room: " + ", ".join(f"{base[key]:.3g} {key}" for key in ("rays", "steps", "reads")))
    noise = cached("reference_noise", reference_noise)
    print("Reference noise, relative RMS: " + ", ".join(f"{name} {100 * value:.2f}%" for name, value in noise.items()))


if __name__ == "__main__":
    main()
