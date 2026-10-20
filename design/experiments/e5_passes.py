"""E5: bounce passes on surface probes, GMRES against plain bounces with a geometric tail.

For the world and lattice solves of E3 at its default parameters, at albedos 0.5 and 0.9: the relative error of the
face radiance after 1 to 8 passes, against the exact solution and against the solve's own fixed point (GMRES after 40
passes). The light's direct irradiance is exact; the solves gather reflected light and the sky."""
import math

import numpy as np

import common as cm
from e3_cascade0 import build

ALBEDOS = (0.5, 0.9)
PASSES = 8
SCENES = ("room", "thick room", "two rooms", "courtyard", "columns")


def compute():
    results = {}
    for name in SCENES:
        scene = cm.Scene(name)
        faces = scene.surface.active[scene.receivers]
        results[name] = {}
        for layout in ("world", "atlas"):
            solver = build(layout, scene.surface, 16, math.sqrt(32 / (4 * math.pi)))
            for albedo in ALBEDOS:
                exact = scene.converged(albedo)[faces]
                own = scene.passes(solver, albedo, 40, exact_direct=True)[-1][faces]
                rho = albedo * scene.reflects / math.pi
                direct = scene.as_faces(math.pi * (scene.share @ np.append(scene.emission, 0.0)))
                bounce = lambda reflected: rho * (direct + solver.irradiance(reflected, scene.sky))  # noqa: E731
                tail = cm.rd.tail(bounce, np.zeros(scene.size), PASSES)
                runs = {"gmres": scene.passes(solver, albedo, PASSES, exact_direct=True),
                        "tail": [scene.emission + r for r in tail]}
                for method, steps in runs.items():
                    key = f"{layout} {albedo} {method}"
                    results[name][key] = {"exact": [cm.relative(s[faces], exact)[0] for s in steps],
                                          "own": [cm.relative(s[faces], own)[0] for s in steps]}
                    print(name, key, results[name][key], flush=True)
    return results


def main():
    results = cm.cached("e5_passes", compute)
    for name, rows in results.items():
        print(f"\n{name}")
        for key, r in rows.items():
            print(f"  {key:20s} own " + " ".join(f"{e:.4f}" for e in r["own"]))
            print(f"  {'':20s} exact " + " ".join(f"{e:.4f}" for e in r["exact"]))


if __name__ == "__main__":
    main()
