"""A small light in 3D (figure lamp, tables aliasing and lamp).

The angular term alone: one ray per bin of a cascade's direction map estimates the solid angle of a unit cube seen
from random points; its relative error is binned by x, the number of bins the cube covers, and fitted against the
conjectured x^(-3/4). The full solve: the error at every empty voxel around a cube light, binned by distance. Then
the share of the light that depth reprojection at one hand-over keeps, against the share derived in
checks/depth_light_loss.py.
"""
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullFormatter

from common import HAND_OVERS, PARAMS, TEST, WIDTH, cached, save, sc, vo

MAPS = range(6)
SAMPLES = 16000
WIDTHS = (2, 4, 8)
BINS = np.geomspace(0.25, 512, 34)
DISTANCES = np.geomspace(1, 40, 25)
TICKS = (1, 2, 5, 10, 20, 40)
WINDOWS = ((4, 16), (16, 64), (64, 256), (4, 256))


def hits(points, dirs, lo, hi):
    """Whether each ray from each point along each direction hits the box [lo, hi]."""
    inverse = 1 / dirs
    out = np.empty((len(points), len(dirs)), bool)
    step = max(1, 4_000_000 // len(dirs))
    for i in range(0, len(points), step):
        p = points[i:i + step, None]
        a, b = (lo - p) * inverse, (hi - p) * inverse
        near, far = np.minimum(a, b).max(-1), np.maximum(a, b).min(-1)
        out[i:i + step] = far >= np.maximum(near, 0)
    return out


def angular(c, rng):
    """Bins covered and relative error of the one-ray-per-bin solid angle of a unit cube, from random points."""
    dirs = vo.bin_directions(PARAMS, c)
    u = rng.normal(size=(SAMPLES, 3))
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    reach = math.sqrt(len(dirs) / (4 * math.pi * BINS[0]))
    points = u * np.exp(rng.uniform(math.log(1.5), math.log(reach), SAMPLES))[:, None]
    exact = vo.box_solid_angle(points, -0.5 * np.ones(3), 0.5 * np.ones(3))
    estimate = hits(points, dirs, -0.5, 0.5).sum(1) * 4 * math.pi / len(dirs)
    return exact * len(dirs) / (4 * math.pi), estimate / exact - 1


def binned(value, error, edges):
    """RMS error in each bin of value, where the bin holds at least 20 samples."""
    which = np.digitize(value, edges) - 1
    return [math.sqrt(np.mean(error[which == k] ** 2)) if np.sum(which == k) >= 20 else math.nan
            for k in range(len(edges) - 1)]


def centres(edges):
    return np.sqrt(edges[1:] * edges[:-1])


def slope(rms, window):
    x = centres(BINS)
    keep = (x >= window[0]) & (x <= window[1]) & np.isfinite(rms)
    if keep.sum() < 3:
        return math.nan
    return float(np.polyfit(np.log(x[keep]), np.log(rms[keep]), 1)[0])


def solved(width):
    """RMS relative error at every empty voxel around a cube light, binned by distance, over the test offsets."""
    distances, errors = [], []
    for offset in TEST:
        volume, data = sc.lamp(width, offset)
        fluence, _ = vo.solve(volume, PARAMS)
        distances.append(np.linalg.norm(data["points"] - data["centre"], axis=1))
        errors.append(sc.values_at(fluence, data["points"]) / data["exact"] - 1)
    return binned(np.concatenate(distances), np.concatenate(errors), DISTANCES)


def kept(width, hand_over):
    """Mean ratio of the fluence with depth reprojection at one hand-over to vanilla's, over the probes that the light
    reaches only through that hand-over: beyond its boundary by the light's half-diagonal and the reach of the
    hand-over's lower probes."""
    merges = ["vanilla"] * HAND_OVERS
    merges[hand_over] = "depth_surface"
    ratios = []
    for offset in TEST:
        volume, data = sc.lamp(width, offset)
        distance = np.linalg.norm(data["points"] - data["centre"], axis=1)
        far = data["points"][distance > PARAMS.boundary(hand_over) + math.sqrt(3) * (2 ** hand_over + width / 2)]
        base = sc.values_at(vo.solve(volume, PARAMS)[0], far)
        ratios.append(sc.values_at(vo.solve(volume, PARAMS, merges=merges)[0], far) / base)
    return float(np.concatenate(ratios).mean())


def compute():
    rng = np.random.default_rng(7)
    maps = [angular(c, rng) for c in MAPS]
    x, error = (np.concatenate(a) for a in zip(*maps))
    out = {"angular": binned(x, error, BINS), "maps": {str(c): binned(*maps[c], BINS) for c in MAPS},
           "solved": {str(w): solved(w) for w in WIDTHS}}
    out["kept"] = {f"{w} {h}": kept(w, h) for w in WIDTHS for h in range(HAND_OVERS)}
    return out


def main():
    results = cached("lamp", compute)
    angular_rms = np.array(results["angular"], float)
    print("Exponent of the angular term's RMS error against x, fitted over windows of x:\n")
    print("| maps | " + " | ".join(f"{a}-{b}" for a, b in WINDOWS) + " |")
    print("|---|" + "---|" * len(WINDOWS))
    print("| all, pooled | " + " | ".join(f"{slope(angular_rms, w):.2f}" for w in WINDOWS) + " |")
    for c in MAPS[2:]:
        rms = np.array(results["maps"][str(c)], float)
        print(f"| {PARAMS.directions(c)} bins | " + " | ".join(f"{slope(rms, w):.2f}" for w in WINDOWS) + " |")
    print("\nFull solve, RMS relative error by distance from the light's centre:\n")
    print("| width | " + " | ".join(f"{d:.1f}" for d in centres(DISTANCES)) + " |")
    print("|---|" + "---|" * (len(DISTANCES) - 1))
    for w in WIDTHS:
        print(f"| {w} | " + " | ".join("" if math.isnan(e) else f"{100 * e:.0f}" for e in results["solved"][str(w)])
              + " |")
    print("\nMean fluence ratio of depth reprojection at one hand-over to vanilla, where the light arrives only through "
          "that hand-over:\n")
    print("| light width a | hand-over | parent spacing h | a/h | ratio |")
    print("|---|---|---|---|---|")
    for key, ratio in results["kept"].items():
        w, h = (int(v) for v in key.split())
        print(f"| {w} | {h} | {2 ** (h + 1)} | {w / 2 ** (h + 1):g} | {ratio:.2f} |")

    fig, (left, right) = plt.subplots(1, 2, figsize=(WIDTH, 2.5))
    x = centres(BINS)
    left.plot(x, angular_rms, "ko", ms=3, label="one ray per bin")
    for power, style in ((-0.5, ":"), (-0.75, "--"), (-1.0, "-.")):
        left.plot(x, 0.6 * x ** power, style, color="0.5", lw=0.8, label=f"$x^{{{power:g}}}$")
    left.set(xscale="log", yscale="log", xlabel="bins the light covers, $x$", ylabel="RMS relative error")
    left.legend(frameon=False)
    for i, w in enumerate(WIDTHS):
        right.plot(centres(DISTANCES), results["solved"][str(w)], "-o", ms=2, color=f"C{i}", label=f"width {w}")
    for c in range(PARAMS.levels - 1):
        right.axvline(PARAMS.boundary(c), color="k", lw=0.5)
    right.set(xscale="log", xlabel="distance from the light, voxels", ylabel="RMS relative error, full solve")
    right.set_xticks(TICKS, [str(t) for t in TICKS])
    right.xaxis.set_minor_formatter(NullFormatter())
    right.legend(frameon=False)
    fig.tight_layout()
    save(fig, "lamp")


if __name__ == "__main__":
    main()
