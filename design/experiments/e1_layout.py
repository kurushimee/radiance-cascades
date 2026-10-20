"""E1: upper cascades on world sphere grids, with all of a probe's parents or only those in front of it, against
chart lattices, with the same merge at every hand-over (the bilinear fix on the lattices).

Per scene, layout and merge, over the receivers: the error of the first bounce, the irradiance from the light and sky;
of the second, the irradiance from faces lit by the exact first bounce at albedo 1; the leak into the sealed box; the
deficit of a closed scene's furnace (faces of radiance 1, no sky); the error of the face radiance after 5 GMRES passes
at albedo 0.9 with every bounce gathered ("converged"), and with the light's direct irradiance exact ("split"); and the
hit records a static solve keeps."""
import math

import numpy as np

import common as cm
import surface as sf

CLOSED = ("room", "thick room", "two rooms", "columns")
ALBEDO, PASSES = 0.9, 5


LAYOUTS = {"world": sf.MERGES, "world front": sf.MERGES, "atlas": sf.ATLAS_MERGES}


def build(layout, surface, merge):
    if layout == "atlas":
        return sf.Atlas(surface, merge=merge)
    return sf.World(surface, surface_merge=merge, world_merge=merge, front=layout == "world front")


def measure(scene, solver):
    rows = scene.receivers
    active = scene.surface.active
    out = {"records": solver.cost["records"]}
    exact_first = scene.first_bounce()
    first = solver.irradiance(scene.emission, scene.sky)[active]
    out["first"] = cm.relative(first[rows], exact_first[rows])
    lit = scene.reflects * scene.as_faces(exact_first / math.pi)
    second = solver.irradiance(lit, 0.0)[active]
    exact_second = math.pi * (scene.share @ np.append(lit, 0.0))
    out["second"] = cm.relative(second[rows], exact_second[rows])
    if scene.name == "sealed box":
        inside = scene.interior()
        out["leak"] = float(solver.irradiance(np.zeros(scene.size), 1.0)[active][inside].mean() / math.pi)
        return out
    if scene.name in CLOSED:
        out["deficit"] = float(1 - solver.irradiance(np.ones(scene.size), 0.0)[active][rows].mean() / math.pi)
    faces = active[rows]
    exact = scene.converged(ALBEDO)[faces]
    out["converged"] = cm.relative(scene.passes(solver, ALBEDO, PASSES)[-1][faces], exact)
    out["split"] = cm.relative(scene.passes(solver, ALBEDO, PASSES, exact_direct=True)[-1][faces], exact)
    return out


def compute():
    results = {}
    for name in cm.SCENES:
        scene = cm.Scene(name)
        rows = scene.receivers
        noise = cm.relative(scene.first_bounce(scene.shares[0])[rows], scene.first_bounce(scene.shares[1])[rows])
        results[name] = {"probes": int(scene.surface.size), "noise": noise[0] / 2}
        for layout, merges in LAYOUTS.items():
            for merge in merges:
                results[name][f"{layout} {merge}"] = measure(scene, build(layout, scene.surface, merge))
                print(name, layout, merge, results[name][f"{layout} {merge}"], flush=True)
    return results


def main():
    cm.print_table(cm.cached("e1_layout", compute), 26)


if __name__ == "__main__":
    main()
