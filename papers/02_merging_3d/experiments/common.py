"""Shared setup of the paper's experiments: parameters, scenes at grid offsets, metrics and cached results."""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
sys.path.insert(0, str(PAPER.parent / "lab"))

import scenes3d as sc  # noqa: E402
import volume as vo  # noqa: E402
from report import WIDTH, Outputs, legend_below  # noqa: E402,F401

cached, save = Outputs(PAPER).cached, Outputs(PAPER).save
T_EQ = math.sqrt(32 / (4 * math.pi))

ROTATION = vo.generic_rotation()
PARAMS = vo.Params(t0=T_EQ, levels=vo.levels_for(sc.N, T_EQ), rotation=ROTATION)  # equal-error interval, 32 directions
HAND_OVERS = PARAMS.levels - 1
# Scenes move by whole voxels against the grids; below 8 voxels every cascade's alignment varies. Choices of merge
# are made on TRAIN and every reported number comes from TEST.
TRAIN, TEST = np.random.default_rng(2).integers(0, 8, (2, 4, 3))
SCENES = {
    "sealed_1": lambda o: sc.sealed(1, o),
    "sealed_2": lambda o: sc.sealed(2, o),
    "sealed_3": lambda o: sc.sealed(3, o),
    "lamp_by_wall": sc.lamp_by_wall,
    "lamp": lambda o: sc.lamp(2, o),
    "room": sc.room,
    "partition": sc.partition,
}
_BUILT = {}


def scene(name, offset):
    key = (name, tuple(int(x) for x in offset))
    if key not in _BUILT:
        _BUILT[key] = SCENES[name](np.asarray(offset))
    return _BUILT[key]


def relative_rmse(estimate, exact):
    return float(np.sqrt(((estimate - exact) ** 2).mean()) / exact.mean())


def measure(name, fluence, data):
    """The scene's metrics: leaked energy where the exact fluence is zero, and relative errors elsewhere. The lamp's
    fluence spans orders of magnitude, so its error is the RMS of each probe's relative error."""
    at = lambda points: sc.values_at(fluence, points)  # noqa: E731
    if name.startswith("sealed"):
        return {"leak": float(at(data["inside"]).mean() / (4 * math.pi)),
                "outside": relative_rmse(at(data["outside"]), data["outside_exact"])}
    if name == "lamp_by_wall":
        return {"leak": float(at(data["inside"]).mean() / data["scale"])}
    if name == "lamp":
        return {"error": float(np.sqrt((((at(data["points"]) - data["exact"]) / data["exact"]) ** 2).mean()))}
    return {"error": relative_rmse(at(data["points"]), data["reference"])}


def evaluate(names, offsets, params=PARAMS, merge="vanilla", merges=None, tau=0.5):
    """Metrics of each scene averaged over offsets, and the cost of one solve of the room at the first offset."""
    out = {}
    for name in names:
        rows = []
        for i, offset in enumerate(offsets):
            volume, data = scene(name, offset)
            fluence, cost = vo.solve(volume, params, merge, tau=tau, merges=merges)
            rows.append(measure(name, fluence, data))
            if name == "room" and i == 0:
                out["cost"] = cost
        out[name] = {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}
    return out


def label(merges):
    return " / ".join(m.replace("_", " ") for m in merges)


NAMES = {
    "vanilla": "vanilla",
    "parallax": "parallax fix",
    "fixed_depth": "fixed-depth reprojection",
    "depth": "depth reprojection, inverse mean",
    "depth_surface": "depth reprojection",
    "hit_distance": "hit-distance test",
    "visibility_rays": "visibility rays",
    "inner_fix": "inner parallax fix",
    "self_test": "self test",
    "depth_self_test": "depth reprojection + self test",
    "trilinear_fix": "trilinear fix",
    "kuhn_fix": "Kuhn fix",
    "sphere_fix": "sphere fix",
}


def sphere_defined(c, params=PARAMS):
    """Whether every ray of cascade c leaves the sphere around each parent ahead of its start."""
    start, end = params.interval(c)
    return end - start >= 0.75 * math.sqrt(3) * 2 ** (c + 1)


def sphere_where_defined(params=PARAMS):
    """The sphere fix where it is defined and the Kuhn fix elsewhere."""
    return ["sphere_fix" if sphere_defined(c, params) else "kuhn_fix" for c in range(params.levels - 1)]


# Table columns: scene, metric and decimals, all in percent.
COLUMNS = (("sealed_1", "leak", 2), ("sealed_2", "leak", 2), ("sealed_3", "leak", 3), ("lamp_by_wall", "leak", 2),
           ("sealed_1", "outside", 2), ("lamp", "error", 1), ("room", "error", 1), ("partition", "error", 1))
HEADER = "leak, 1-voxel walls | 2 | 3 | lamp by wall | outside | lamp | room | partition"


def cells(result):
    return " | ".join(f"{100 * result[scene][key]:.{decimals}f}" for scene, key, decimals in COLUMNS)


def params(n0=32, t0=T_EQ, overlap=0.0, rotation=ROTATION):
    return vo.Params(n0=n0, t0=t0, levels=vo.levels_for(sc.N, t0), overlap=overlap, rotation=rotation)
