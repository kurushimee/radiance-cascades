"""Assert-based checks of the lab. Run from papers/: uv run python lab/selftest.py"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flatland as fl  # noqa: E402


def lattice_scene(seed):
    """Boxes and walls in separate lattice cells, so no two segments cross."""
    rng = np.random.default_rng(seed)
    scene = fl.Scene.empty(sky=0.3)
    for cx in range(4):
        for cy in range(4):
            x0, y0 = 4.3 + 16 * cx + rng.uniform(0, 4), 4.3 + 16 * cy + rng.uniform(0, 4)
            w, h = rng.uniform(1, 8), rng.uniform(1, 8)
            kind = rng.integers(3)
            if kind == 0:
                scene.box(x0, y0, x0 + w, y0 + h, radiance=rng.uniform(0, 4) * (rng.random() < 0.4))
            elif kind == 1:
                scene.wall((x0, y0), (x0 + w, y0 + h), radiance=rng.uniform(0, 2) * (rng.random() < 0.3))
    scene.check_no_crossings()
    return scene


def check_lone_segment():
    scene = fl.Scene.empty().wall((10.0, -5.0), (10.0, 7.0), radiance=2.0)
    p = np.array([[1.0, 0.5], [-3.0, 4.0]])
    angle = np.abs(np.arctan2(7 - p[:, 1], 10 - p[:, 0]) - np.arctan2(-5 - p[:, 1], 10 - p[:, 0]))
    assert np.allclose(fl.fluence(scene, p), 2.0 * angle)


def check_hollow_emitter():
    c = 1.5
    ring = [(math.cos(a) * 20, math.sin(a) * 20) for a in np.linspace(0, fl.TAU, 41)[:-1]]
    scene = fl.Scene.empty().polygon(ring, radiance=c, inside=c)
    assert np.allclose(fl.fluence(scene, np.array([[0.0, 0.0], [5.0, -7.0]])), fl.TAU * c)
    # Just outside a flat side, half the directions see the emitter.
    edge_mid = 0.5 * (np.array(ring[0]) + np.array(ring[1]))
    outside = edge_mid * (1 + 1e-4)
    assert abs(fl.fluence(scene, outside[None])[0] - math.pi * c) < 1e-2


def check_oracle_against_tracer():
    scene = lattice_scene(1)
    rng = np.random.default_rng(2)
    points = rng.uniform(0, 64, (40, 2))
    points = points[~scene.inside_solid(points)]
    for a, b in ((0.0, np.inf), (1.3, 6.0), (4.0, np.inf), (0.7, 2.1)):
        theta, rad, hit = fl.profile(scene, points, a, b)
        angles = rng.uniform(0, fl.TAU, (len(points), 50))
        cell = np.array([np.searchsorted(theta[i], angles[i], side="right") - 1 for i in range(len(points))])
        dirs = np.stack([np.cos(angles), np.sin(angles)], -1).reshape(-1, 2)
        origins = np.repeat(points, 50, axis=0)
        t_rad, t_hit, _ = fl.trace(scene, origins, dirs, a, b)
        rows = np.arange(len(points))[:, None]
        assert np.array_equal(hit[rows, cell].ravel(), t_hit)
        assert np.allclose(rad[rows, cell].ravel(), t_rad)


def check_cone_means_against_dense_rays():
    scene = lattice_scene(6)
    points = np.array([[21.7, 33.1], [40.2, 9.9], [12.0, 50.3]])
    points = points[~scene.inside_solid(points)]
    cones, rays = 16, 4096
    for a, b in ((0.0, np.inf), (2.0, 9.0)):
        rad, beta = fl.cone_means(scene, points, a, b, cones)
        angles = (np.arange(cones * rays) + 0.5) * fl.TAU / (cones * rays)
        dirs = np.stack([np.cos(angles), np.sin(angles)], -1)
        for i, p in enumerate(points):
            t_rad, t_hit, _ = fl.trace(scene, np.broadcast_to(p, dirs.shape), dirs, a, b)
            assert np.allclose(rad[i], t_rad.reshape(cones, rays).mean(1), atol=4 * 4.0 / rays)
            assert np.allclose(beta[i], (~t_hit).reshape(cones, rays).mean(1), atol=4.0 / rays)


def check_window_means():
    theta = np.array([[0.0, 1.0, 3.0, fl.TAU]])
    values = np.array([[2.0, 0.0, 1.0]])
    edges = np.array([0.0, 2.0, fl.TAU])
    means = fl.window_means(theta, values, edges)
    assert np.allclose(means, [[1.0, (1.0 * (fl.TAU - 3.0)) / (fl.TAU - 2.0)]])


def check_merge_monoid():
    rng = np.random.default_rng(4)
    a, b, c = (rng.random(2) for _ in range(3))

    def merge(near, far):
        return np.array([near[0] + near[1] * far[0], near[1] * far[1]])

    assert np.allclose(merge(merge(a, b), c), merge(a, merge(b, c)))
    assert np.allclose(merge(a, np.array([0.0, 1.0])), a)


def check_decomposition():
    scene = lattice_scene(3)
    lo, hi = (8.0, 8.0), (56.0, 56.0)
    xs = np.arange(8.5, 56, 3.0)
    eval_points = np.stack(np.meshgrid(xs, xs), -1).reshape(-1, 2)
    eval_points = eval_points[~scene.inside_solid(eval_points)]
    for params in (fl.Params(ds0=2, n0=8, k=2, l=4, t0=2, levels=4, s=1),
                   fl.Params(ds0=1, n0=4, k=4, l=4, t0=1, levels=4, s=2)):
        parts = fl.decompose(scene, params, lo, hi, eval_points)
        total = sum(t.sum(0) for t in parts["terms"].values()) + parts["gather"]
        assert np.allclose(total, parts["estimate"] - parts["exact"], atol=1e-9 * parts["exact"].max())
        estimate, merged, _ = fl.solve(scene, params, lo, hi, eval_points)
        assert np.all(estimate >= 0) and np.all(estimate <= fl.TAU * 4.0)


def check_spatial_split():
    """Seam parts plus parallax, from dense rays, match the exact local spatial term."""
    scene = lattice_scene(8)
    params = fl.Params(ds0=2, n0=8, k=2, l=4, t0=2, levels=4, overlap=0.4)
    lo, hi = (8.0, 8.0), (56.0, 56.0)
    n, rays = 1, 256
    unseen, double, parallax = fl.split_spatial(scene, params, lo, hi, n, samples=60, rays=rays, seed=1)
    gs = fl.grids(params, lo, hi)
    rng = np.random.default_rng(1)
    all_points = gs[n].points()
    points = all_points[rng.choice(len(all_points), 60, replace=False)]
    start, end = params.interval(n)
    _, beta_bar = fl.cone_means(scene, points, start, end, params.directions(n))
    idx, wts = gs[n + 1].bilinear(points)
    upper = fl.cone_means(scene, gs[n + 1].points(), params.boundary(n), np.inf, params.directions(n + 1))[0]
    x_hat = fl.upper_mean(upper, params, n, idx, wts)
    x_bar = fl.cone_means(scene, points, end, np.inf, params.directions(n + 1))[0]
    x_bar = x_bar.reshape(len(points), params.directions(n), params.k).mean(-1)
    assert np.allclose(unseen + double + parallax, beta_bar * (x_hat - x_bar), atol=8 * 4.0 / rays)


def check_bilinear_fix_runs():
    scene = lattice_scene(5)
    params = fl.Params(ds0=2, n0=8, k=2, l=4, t0=2, levels=4)
    points = np.array([[20.5, 30.5], [40.5, 12.5]])
    fixed, _, _ = fl.solve(scene, params, (8.0, 8.0), (56.0, 56.0), points, merge="bilinear_fix")
    assert np.all(np.isfinite(fixed)) and np.all(fixed >= 0)


for check in (check_lone_segment, check_hollow_emitter, check_oracle_against_tracer, check_cone_means_against_dense_rays,
              check_window_means,
              check_merge_monoid, check_decomposition, check_spatial_split, check_bilinear_fix_runs):
    check()
    print(f"{check.__name__}: ok")
