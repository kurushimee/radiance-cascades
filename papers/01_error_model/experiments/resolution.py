"""Small lights: the aliasing law at the probes, and image error against the resolvable distance (figure resolution).

Prints, per case, how far the measured probe error departs from the law.
"""
import math

import matplotlib.pyplot as plt
import numpy as np

from common import HI, LO, OFFSETS, WIDTH, cached, equal_error_t0, fl, params, save, sc

CENTRE = np.array([64.3, 64.1])
PROBE_CASES = ((0.5, 1.0, 1), (2.0, 1.0, 1), (8.0, 1.0, 1), (2.0, equal_error_t0(32), 1), (2.0, 1.0, 4))
IMAGE_CASES = [(w, n0, t0) for w in (1.0, 2.0, 4.0) for n0 in (16, 32) for t0 in (1.0, equal_error_t0(32))]
X_EDGES = np.geomspace(0.1, 200, 25)
D_EDGES = np.geomspace(2, 90, 12)
FAR = 0.3  # beyond this fraction of the resolvable distance, aliasing rather than ringing sets the image error


def distance_to_segment(points, a, b):
    e = b - a
    u = np.clip(((points - a) @ e) / (e @ e), 0, 1)
    return np.linalg.norm(points - (a + u[:, None] * e), axis=1)


def probe_errors(w, t0, s, n0=32):
    """Spanned ray count x and relative error of the interval fluence at every probe whose interval holds the lamp,
    over all grid offsets."""
    p = params(n0=n0, t0=t0, s=s)
    xs, errors = [], []
    for offset in OFFSETS:
        scene = sc.lamp(w).shifted(offset)
        a, b = scene.a[0], scene.b[0]
        for n, grid in enumerate(fl.grids(p, LO + offset, HI + offset)):
            points = grid.points()
            start, end = p.interval(n)
            far = np.maximum(np.linalg.norm(points - a, axis=1), np.linalg.norm(points - b, axis=1))
            points = points[(distance_to_segment(points, a, b) >= start) & (far <= end)]
            if not len(points):
                continue
            j_hat, _ = fl.sample(scene, p, n, points)
            j_bar, _ = fl.cone_means(scene, points, start, end, p.directions(n))
            truth = j_bar.sum(1)
            xs.append(truth * s)
            errors.append((j_hat.sum(1) - truth) / truth)
    return np.concatenate(xs), np.concatenate(errors)


def resolvable(w, n0, t0, s=1):
    return (w * s * n0 / (2 * math.pi)) ** 2 / t0


def bands(w, n0, t0, offset):
    """Relative RMSE of the image in distance bands around the lamp."""
    offset = np.asarray(offset)
    scene = sc.lamp(w).shifted(offset)
    lo, hi = LO + offset, HI + offset
    pixels = sc.pixels(scene, (lo, hi))
    exact = fl.fluence(scene, pixels)
    estimate, _, _ = fl.solve(scene, params(n0=n0, t0=t0), lo, hi, pixels)
    d = np.linalg.norm(pixels - CENTRE - offset, axis=1)
    out = []
    for d0, d1 in zip(D_EDGES[:-1], D_EDGES[1:]):
        sel = (d >= d0) & (d < d1)
        out.append(float(np.sqrt(((estimate[sel] - exact[sel]) ** 2).mean()) / exact[sel].mean()))
    return out


def compute():
    probes = {}
    for w, t0, s in PROBE_CASES:
        x, err = probe_errors(w, t0, s)
        probes[f"{w},{t0},{s}"] = [x.tolist(), err.tolist()]
    tasks = [(w, n0, t0, tuple(offset)) for w, n0, t0 in IMAGE_CASES for offset in OFFSETS]
    image = np.array([bands(*task) for task in tasks]).reshape(len(IMAGE_CASES), len(OFFSETS), -1)
    return {"probes": probes, "image": np.sqrt((image ** 2).mean(1)).tolist()}


def law(x):
    f = x - np.floor(x)
    return f * (1 - f) / x ** 2


def main():
    results = cached("resolution", compute)
    fig, (left, right) = plt.subplots(1, 2, figsize=(WIDTH, 2.3))
    centres = np.sqrt(X_EDGES[:-1] * X_EDGES[1:])
    print("| w | t0 | s | probes | worst measured/law over bins with >= 30 probes |")
    print("|---|---|---|---|---|")
    for i, (w, t0, s) in enumerate(PROBE_CASES):
        x, err = (np.array(v) for v in results["probes"][f"{w},{t0},{s}"])
        which = np.digitize(x, X_EDGES) - 1
        measured, predicted, keep = [], [], []
        for j in range(len(centres)):
            sel = which == j
            keep.append(sel.sum() >= 30)
            measured.append(np.sqrt((err[sel] ** 2).mean()) if sel.any() else np.nan)
            predicted.append(np.sqrt(law(x[sel]).mean()) if sel.any() else np.nan)
        keep, measured, predicted = np.array(keep), np.array(measured), np.array(predicted)
        label = f"$w={w:g}$, $t_0={t0:.2f}$, $s={s}$"
        left.plot(centres[keep], measured[keep], "o", color=f"C{i}", label=label)
        left.plot(centres[keep], predicted[keep], "-", color=f"C{i}", lw=0.7)
        ratio = measured[keep] / predicted[keep]
        print(f"| {w:g} | {t0:.2f} | {s} | {len(x)} | {ratio.min():.2f} to {ratio.max():.2f} |")
    grid = np.geomspace(1, 200, 100)
    left.plot(grid, 1 / (2 * grid), "k--", lw=0.7, label="$1/(2x)$")
    left.set(xscale="log", yscale="log", xlabel="rays spanned by the light, $x$", ylabel="relative RMS at probes",
             ylim=(1e-3, 3))
    left.legend(frameon=False, fontsize=5)

    d_centres = np.sqrt(D_EDGES[:-1] * D_EDGES[1:])
    xs, ys = [], []
    for (w, n0, t0), errors in zip(IMAGE_CASES, results["image"]):
        x = d_centres / resolvable(w, n0, t0)
        right.plot(x, errors, "-o" if t0 == 1.0 else "-s", color=f"C{[1.0, 2.0, 4.0].index(w)}",
                   alpha=0.5 if n0 == 16 else 1.0, ms=2)
        xs.append(x)
        ys.append(errors)
    xs, ys = np.concatenate(xs), np.concatenate(ys)
    far = xs >= FAR
    slope, intercept = np.polyfit(np.log(xs[far]), np.log(ys[far]), 1)
    spread = np.exp(np.std(np.log(ys[far]) - slope * np.log(xs[far]) - intercept))
    print(f"\nImage error beyond D/Dmax = {FAR}: {np.exp(intercept):.2f} * (D/Dmax)^{slope:.2f}, "
          f"geometric spread x{spread:.2f}, {far.sum()} bands")
    ratio = np.geomspace(1e-3, 10, 100)
    right.plot(ratio, 0.5 * np.sqrt(ratio), "k--", lw=0.7, label="$0.5\\sqrt{D/D_{\\max}}$")
    fitted = np.geomspace(FAR, xs.max(), 50)
    right.plot(fitted, np.exp(intercept) * fitted ** slope, "k-", lw=1.0,
               label=f"${np.exp(intercept):.2f}\\,(D/D_{{\\max}})^{{{slope:.2f}}}$")
    for i, w in enumerate((1.0, 2.0, 4.0)):
        right.plot([], [], "-", color=f"C{i}", label=f"$w={w:g}$")
    right.plot([], [], "ko", ms=2, label="$t_0=1$")
    right.plot([], [], "ks", ms=2, label="$t_0=5.09$")
    right.legend(frameon=False, fontsize=5)
    right.set(xscale="log", yscale="log", xlabel="$D/D_{\\max}$", ylabel="relative RMSE in distance band")
    fig.tight_layout()
    save(fig, "resolution")


if __name__ == "__main__":
    main()
