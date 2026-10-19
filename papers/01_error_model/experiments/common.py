"""Shared setup of the paper's experiments: scenes, exact fluence, grid offsets, metrics, cost and cached results."""
import json
import math
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
matplotlib.rcParams.update({"font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7, "legend.fontsize": 6,
                            "xtick.labelsize": 6, "ytick.labelsize": 6, "lines.linewidth": 1.0,
                            "lines.markersize": 3, "savefig.pad_inches": 0.02})
WIDTH = 5.4  # inches, the text width of the paper

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
sys.path.insert(0, str(PAPER.parent / "lab"))

import flatland as fl  # noqa: E402
import scenes2d as sc  # noqa: E402

FIGURES = PAPER / "figures"
CACHE = PAPER / "build" / "cache"
LO, HI = (np.array(corner) for corner in sc.WINDOW)
DIAGONAL = math.hypot(*(HI - LO))
SCENE_NAMES = list(sc.SCENES)
# Every summary number is a mean over the scene moved by these offsets against the probe grids. Whole cascade 0
# spacings keep pixel centres on cascade 0 probes; offsets up to 32 vary the alignment of every cascade.
OFFSETS = np.random.default_rng(1).integers(0, 32, (6, 2)).astype(float)


def exact_fluence(name):
    """Exact fluence at the pixels of an unshifted scene, cached on disk. Moving the scene leaves it unchanged."""
    path = CACHE / f"{name}_fluence.npy"
    if path.exists():
        return np.load(path)
    scene = sc.SCENES[name]()
    exact = fl.fluence(scene, sc.pixels(scene))
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(path, exact)
    return exact


def placed(name, offset=(0.0, 0.0)):
    """(scene, window corners, pixels) for a scene moved by `offset`."""
    offset = np.asarray(offset, float)
    scene = sc.SCENES[name]().shifted(offset)
    lo, hi = LO + offset, HI + offset
    return scene, (lo, hi), sc.pixels(scene, (lo, hi))


def levels_for(t0, l, reach=DIAGONAL):
    """Fewest cascades for which the top one, if it ended at `t0*l**(levels-1)`, would reach `reach`.

    The top cascade runs to infinity, so it starts at the last hand-over, inside the scene.
    """
    return max(2, math.ceil(math.log(reach / t0) / math.log(l)) + 1)


def params(ds0=1.0, n0=32, k=2, l=4.0, t0=1.0, s=1, overlap=0.0):
    return fl.Params(ds0=ds0, n0=n0, k=k, l=l, t0=t0, levels=levels_for(t0, l), s=s, overlap=overlap)


def equal_error_t0(n0, ds0=1.0):
    return n0 * ds0 / (2 * math.pi)


def tonemap(fluence, exposure):
    x = fluence * exposure
    return x / (1 + x)


def metrics(estimate, exact):
    """Relative RMSE of fluence, and RMSE after a Reinhard tone map that puts the mean fluence at 0.18."""
    mean = exact.mean()
    exposure = 0.18 / mean
    return {"linear": float(np.sqrt(((estimate - exact) ** 2).mean()) / mean),
            "display": float(np.sqrt(((tonemap(estimate, exposure) - tonemap(exact, exposure)) ** 2).mean()))}


def cost(p, merge="vanilla", reach=DIAGONAL):
    """Work per unit area of the window: rays, and ray steps for two tracers.

    `steps_fixed` marches each interval at a fixed step of one cascade 0 spacing; `steps_mip` marches cascade `n` at
    its own probe spacing, as a DDA through a mip chain does. The top cascade runs to `reach`. The bilinear fix traces
    one ray per child direction and upper probe, `4*k` rays per cone, below the top cascade.
    """
    rays = steps_fixed = steps_mip = 0.0
    for n in range(p.levels):
        per_probe = p.directions(n) * (4 * p.k if merge == "bilinear_fix" and n < p.levels - 1 else p.s)
        per_area = per_probe / p.spacing(n) ** 2
        start, end = p.interval(n)
        length = min(end, reach) - start
        rays += per_area
        steps_fixed += per_area * length / p.ds0
        steps_mip += per_area * length / p.spacing(n)
    return {"rays": rays, "steps_fixed": steps_fixed, "steps_mip": steps_mip}


def run(name, p, merge="vanilla", offset=(0.0, 0.0)):
    scene, (lo, hi), pixels = placed(name, offset)
    estimate, _, _ = fl.solve(scene, p, lo, hi, pixels, merge=merge)
    return metrics(estimate, exact_fluence(name))


ANGULAR = ("angular_radiance", "angular_transmittance", "correlation")


def budget(name, p, offset=(0.0, 0.0)):
    """RMS of each error term at the pixels, relative to the mean exact fluence.

    Terms are summed over cascades; `angular` adds the three that vanish as cones narrow, and `spatial_m` and
    `angular_m` are cascade m's own share.
    """
    scene, (lo, hi), pixels = placed(name, offset)
    parts = fl.decompose(scene, p, lo, hi, pixels)
    fields = {term: values.sum(0) for term, values in parts["terms"].items()}
    fields["angular"] = sum(fields[term] for term in ANGULAR)
    fields["gather"] = parts["gather"]
    fields["total"] = parts["estimate"] - parts["exact"]
    for m in range(p.levels):
        fields[f"spatial_{m}"] = parts["terms"]["spatial"][m]
        fields[f"angular_{m}"] = sum(parts["terms"][term][m] for term in ANGULAR)
    mean = parts["exact"].mean()
    return {term: float(np.sqrt((values ** 2).mean()) / mean) for term, values in fields.items()}


def jittered(fn, tasks, offsets=OFFSETS):
    """Run each task at every offset; return the mean and standard deviation of each metric over offsets."""
    flat = [task + (tuple(offset),) for task in tasks for offset in offsets]
    results = [fn(*task) for task in flat]
    out = []
    for i in range(len(tasks)):
        chunk = results[i * len(offsets):(i + 1) * len(offsets)]
        out.append({key: (float(np.mean([r[key] for r in chunk])), float(np.std([r[key] for r in chunk])))
                    for key in chunk[0]})
    return out


def cached(stem, compute):
    """Results of `compute()`, kept in build/results/<stem>.json; delete the file to recompute."""
    path = PAPER / "build" / "results" / f"{stem}.json"
    if path.exists():
        return json.loads(path.read_text())
    results = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results))
    return results


def legend_below(fig, ax, ncol, margin):
    """Shows ax's legend under every panel, where it covers no data; margin is the figure fraction it takes."""
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=ncol, frameon=False)
    fig.tight_layout(rect=(0, margin, 1, 1))


def save(fig, stem):
    FIGURES.mkdir(exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIGURES / f"{stem}.{ext}", dpi=200, bbox_inches="tight")
