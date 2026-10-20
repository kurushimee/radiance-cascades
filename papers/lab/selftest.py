"""Assert-based checks of the lab. Run from papers/: uv run python lab/selftest.py"""
import itertools
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flatland as fl  # noqa: E402
import radiosity as rd  # noqa: E402
import radiosity3d as rd3  # noqa: E402
import scenes3d as sc3  # noqa: E402
import volume as vo  # noqa: E402


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


def walled_room(sky=0.0, emission=None):
    """A closed 32 x 32 room on a 4-unit lattice with a partition and a free-standing lamp. `emission`, (S, 2), gives
    every side its own radiance instead."""
    walls = rd.Walls.empty(sky)
    for p, q in (((0, 0), (32, 0)), ((32, 0), (32, 32)), ((32, 32), (0, 32)), ((0, 32), (0, 0))):
        walls.wall(p, q, albedo=(0.7, 0.0))  # counter-clockwise, so the left side faces in
    walls.wall((16, 0), (16, 20), albedo=0.5)
    walls.wall((4, 24), (12, 24), emission=1.0)
    if emission is not None:
        walls.emission = emission
    return walls


ROOM_PARAMS = (fl.Params(n0=16, t0=2.5, levels=4), fl.Params(n0=8, t0=1.0, levels=4, s=2, overlap=0.5))


def check_cosine_weights():
    normal = np.random.default_rng(13).uniform(-10, 10, 50)
    for count in (4, 16, 32):
        edges = np.linspace(0, fl.TAU, count + 1)
        weights = rd.cosine_weights(edges, normal)
        assert np.allclose(weights.sum(1), 2.0, atol=1e-12)
        fine = (np.arange(count * 4000) + 0.5) * fl.TAU / (count * 4000)
        dense = np.maximum(0, np.cos(fine[None] - normal[:, None])).reshape(len(normal), count, -1).mean(-1)
        assert np.allclose(weights, dense * fl.TAU / count, atol=1e-7)


def check_frozen_matches_solve():
    """Re-merging the frozen solve with each side's radiance gives the solve's merged cascade 0 itself."""
    radiance = np.random.default_rng(14).uniform(0, 2, (7, 2))
    walls = walled_room(sky=0.4, emission=radiance)
    scene = fl.Scene(walls.scene.a, walls.scene.b, radiance[:, 0], radiance[:, 1], 0.4)
    pt = rd.patches(walls)
    for params, merge in itertools.product(ROOM_PARAMS, ("vanilla", "bilinear_fix")):
        frozen = rd.freeze(walls, pt, params, (0, 0), (32, 32), merge)
        merged = rd.remerge(frozen, pt.emission, 0.4)
        _, solved, _ = fl.solve(scene, params, (0, 0), (32, 32), np.array([[3.5, 3.5]]), merge)
        assert np.allclose(merged, solved[0].ravel(), atol=1e-12), merge
        irradiance = rd.operator(frozen) @ np.append(pt.emission, 0.4)
        assert np.allclose(frozen.gather @ merged, irradiance, atol=1e-12)


def check_radiosity_furnace():
    """With every patch and the sky at radiance 1, every receiver's irradiance is 2, from the solve and exactly."""
    walls = walled_room()
    pt = rd.patches(walls)
    receivers = pt.albedo > 0
    ones = np.ones(pt.size + 1)
    for params, merge in itertools.product(ROOM_PARAMS, ("vanilla", "bilinear_fix")):
        estimate = rd.operator(rd.freeze(walls, pt, params, (0, 0), (32, 32), merge)) @ ones
        assert np.allclose(estimate[receivers], 2.0, atol=1e-12) and not estimate[~receivers].any(), merge
    exact = rd.reference(walls, pt)
    assert np.allclose(exact[receivers] @ ones, 2.0, atol=1e-12)
    # Inside the closed room, no receiver sees an outer side or the sky.
    inside = receivers | (pt.emission > 0)
    assert np.allclose(exact[receivers][:, :-1][:, inside].sum(1), 2.0, atol=1e-12)


def check_reference_lone_wall():
    """A receiver under a lit wall sees it over [theta1, theta2], where the irradiance is cos(theta1) - cos(theta2)."""
    walls = rd.Walls.empty().wall((0, 0), (4, 0), albedo=(0.5, 0.0)).wall((-2, 10), (6, 10), emission=1.0)
    pt = rd.patches(walls)
    exact = rd.reference(walls, pt) @ np.append(pt.emission, 0.0)
    x = pt.point[:4, 0]
    expected = np.cos(np.arctan2(9.5, 6 - x)) - np.cos(np.arctan2(9.5, -2 - x))
    assert np.allclose(exact[:4], expected, atol=1e-12)


def check_iterations():
    """GMRES is exact once its Krylov space fills the space; the tail is exact for a rank-one bounce."""
    rng = np.random.default_rng(15)
    K = rng.uniform(0, 1, (6, 7))
    K *= 0.9 / K[:, :-1].sum(1, keepdims=True)
    emission, sky = rng.uniform(0, 1, 6), 0.5
    exact = rd.converged(K, emission, sky)
    bounce = lambda L: emission + K[:, :-1] @ L + K[:, -1] * sky  # noqa: E731
    linear = lambda v: K[:, :-1] @ v  # noqa: E731
    assert np.allclose(rd.gmres(bounce, linear, emission, 7)[-1], exact, atol=1e-10)
    plain = rd.plain(bounce, emission, 400)[-1]
    assert np.allclose(plain, exact, atol=1e-10)
    K = np.outer(rng.uniform(0.1, 0.5, 6), rng.uniform(0, 0.3, 7))
    exact = rd.converged(K, emission, sky)
    bounce = lambda L: emission + K[:, :-1] @ L + K[:, -1] * sky  # noqa: E731
    assert np.allclose(rd.tail(bounce, emission, 2)[-1], exact, atol=1e-12)


def random_volume(seed, n=16, radiance=None, sky=0.0):
    rng = np.random.default_rng(seed)
    volume = vo.Volume.empty(n, sky=sky)
    for _ in range(10):
        lo = rng.integers(0, n - 3, 3)
        volume.box(lo, lo + rng.integers(1, 4, 3), rng.uniform(0, 3) if radiance is None else radiance)
    return volume


def check_dda_against_slabs():
    """The DDA's first hit matches an exact slab test over every solid voxel, on rays clear of voxel edges."""
    volume = random_volume(10)
    rng = np.random.default_rng(11)
    origins = rng.uniform(-4, 20, (3000, 3))
    dirs = rng.normal(size=(3000, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    tmin, tmax = rng.uniform(0, 2, 3000), rng.uniform(4, 30, 3000)
    _, hit, t, _, _ = (a.get() for a in vo.trace(volume, origins, dirs, tmin, tmax))
    cells = np.argwhere(volume.solid)
    with np.errstate(divide="ignore", invalid="ignore"):
        near = (cells[None] - origins[:, None]) / dirs[:, None]
        far = (cells[None] + 1 - origins[:, None]) / dirs[:, None]
    enter = np.maximum(np.minimum(near, far).max(-1), tmin[:, None])
    chord = np.minimum(np.maximum(near, far).min(-1), tmax[:, None]) - enter
    first = np.where(chord > 0, enter, np.inf).min(1)
    clear = ~np.any((np.abs(chord) < 1e-3) & (enter <= first[:, None] + 1e-3), axis=1)
    assert clear.mean() > 0.9
    assert np.array_equal(hit[clear], np.isfinite(first[clear]))
    assert np.allclose(t[clear & hit], first[clear & hit], atol=1e-4)


def check_box_solid_angle():
    lo, hi = np.array([20, 22, 21]), np.array([26, 27, 29])
    volume = vo.Volume.empty(48).box(lo, hi, 1.0)
    points = np.array([[10.5, 24.5, 25.5], [23.5, 30.5, 24.5], [40.5, 6.5, 40.5], [26.5, 27.5, 29.5]])
    exact = vo.box_solid_angle(points, lo, hi)
    assert np.allclose(vo.reference_fluence(volume, points, r=256), exact, rtol=5e-3)


ROTATIONS = (vo.Params().rotation, vo.generic_rotation())


def check_furnace_3d():
    """Where every surface and the sky have radiance 1, every merge returns 4*pi at every empty voxel, except that
    visibility rays, which return nothing where every parent is hidden, can only fall short."""
    volume = random_volume(12, n=24, radiance=1.0, sky=1.0)
    for rotation, merge in itertools.product(ROTATIONS, vo.MERGES):
        params = vo.Params(levels=vo.levels_for(24, 1.6), rotation=rotation)
        fluence = vo.solve(volume, params, merge)[0][~volume.solid]
        if merge == "visibility_rays":
            assert fluence.max() <= 4 * math.pi * (1 + 1e-5) and fluence.min() < 4 * math.pi * (1 - 1e-4)
        else:
            assert np.allclose(fluence, 4 * math.pi, rtol=1e-5), merge


def check_bent_rays_seal():
    """Merges whose rays join each lower interval to its parents' let almost no sky into a closed box. The joining
    ray follows the lower bin's centre while each parent is read in its four child directions, whose rays start up to
    t_end times half a lower bin away, so a little leaks."""
    for rotation, offset in itertools.product(ROTATIONS, ((0, 0, 0), (3, 5, 6))):
        params = vo.Params(levels=vo.levels_for(sc3.N, 1.6), rotation=rotation)
        volume, data = sc3.sealed(1, offset)
        for merge in ("visibility_rays", "trilinear_fix", "kuhn_fix"):
            inside = sc3.values_at(vo.solve(volume, params, merge)[0], data["inside"]) / (4 * math.pi)
            assert inside.mean() < 1e-4 and inside.max() < 1e-3, merge


def walled_volume(n=16, sky=0.0):
    """A closed box with one-voxel walls, a free-standing panel and a pillar; every solid voxel has an exposed face."""
    volume = vo.Volume.empty(n, sky=sky)
    for axis in range(3):
        for side in (0, n - 1):
            lo, hi = np.zeros(3, int), np.full(3, n)
            lo[axis], hi[axis] = side, side + 1
            volume.box(lo, hi)
    volume.box((5, 1, 1), (6, 9, 8))
    volume.box((10, 9, 1), (12, 11, 12))
    return volume


def receiving_faces(volume, albedo=0.5):
    faces = rd3.Faces(volume)
    faces.albedo[faces.neighbour >= 0] = albedo
    return faces


def check_bin_cosines():
    """Against +z, unrotated bins are bands of height: each gets (pi/m) * (z1^2 - z0^2) / 2 of the upper half."""
    params = vo.Params()
    m = params.m0
    weights = rd3.bin_cosines(params)
    assert np.allclose(weights.sum(1), math.pi)
    z = -1 + np.arange(m + 1) * 2 / m
    band = np.where(z[:-1] >= 0, (math.pi / m) * (z[1:] ** 2 - z[:-1] ** 2) / 2, 0.0)
    assert np.allclose(weights[5].reshape(2 * m, m), band[None], atol=1e-4)
    assert np.allclose(weights[4].reshape(2 * m, m), band[::-1][None], atol=1e-4)


def check_voxel_remerge():
    """Faces shaded with their voxel's radiance re-merge into the solve's own cascades, under every merge; any radiance
    re-merges linearly; with every face and the sky at 1 every receiver's irradiance is pi, from the cascades (but
    visibility rays, which can only fall short) and from the reference's rays."""
    volume = walled_volume(sky=0.0)
    rng = np.random.default_rng(16)
    volume.emission = np.where(volume.solid, rng.uniform(0, 2, volume.solid.shape), 0.0)
    faces = receiving_faces(volume)
    radiance = volume.emission.ravel()[faces.voxel]
    a, b = rng.uniform(0, 1, faces.size), rng.uniform(0, 1, faces.size)
    for rotation, merge in itertools.product(ROTATIONS, vo.MERGES):
        params = vo.Params(levels=vo.levels_for(16, 1.6), rotation=rotation)
        frozen = rd3.Frozen(faces, params, [merge] * (params.levels - 1))
        own, shade = frozen.shading(radiance, 0.0)
        merged, _ = vo.remerge(volume, params, frozen.levels, own, shade, merge)
        assert np.allclose(merged[0].get(), frozen.levels[0]["radiance"].get(), atol=1e-5), merge
        both = frozen.irradiance(a + 2 * b, 0.3)
        assert np.allclose(both, frozen.irradiance(a, 0.1) + 2 * frozen.irradiance(b, 0.1), rtol=1e-5, atol=1e-5)
        if merge != "visibility_rays":
            furnace = frozen.irradiance(np.ones(faces.size), 1.0)[frozen.receivers]
            assert np.allclose(furnace, math.pi, rtol=1e-5), merge
    exact = rd3.reference(faces, rays=256) @ np.ones(faces.size + 1)
    assert np.allclose(exact[faces.receivers()], 1.0)


def check_reference_rectangle():
    """Under a lit square ceiling, a floor face's irradiance is pi times the point-to-rectangle form factor."""
    n, h = 24, 9
    volume = vo.Volume.empty(n)
    volume.box((0, 0, 0), (n, n, 1))
    volume.box((8, 8, h + 1), (16, 16, h + 2))
    faces = rd3.Faces(volume)
    centre, normal = faces.centre()
    receiver = np.flatnonzero((faces.face == 5) & np.all(centre == (12.5, 12.5, 1.5), axis=1))
    faces.albedo[receiver] = 0.5
    faces.emission[(faces.face == 4) & (centre[:, 2] == h + 0.5)] = 1.0
    irradiance = math.pi * (rd3.reference(faces, rays=1 << 16) @ np.append(faces.emission, 0.0))[receiver][0]
    def corner(a, b, d):
        x, y = a / d, b / d
        return (x / math.sqrt(1 + x * x) * math.atan(y / math.sqrt(1 + x * x))
                + y / math.sqrt(1 + y * y) * math.atan(x / math.sqrt(1 + y * y))) / (2 * math.pi)
    d = h + 1 - 1.5
    exact = math.pi * (corner(4.5, 4.5, d) + corner(3.5, 4.5, d) * 2 + corner(3.5, 3.5, d))
    assert abs(irradiance / exact - 1) < 0.01, (irradiance, exact)


for check in (check_lone_segment, check_hollow_emitter, check_oracle_against_tracer, check_cone_means_against_dense_rays,
              check_window_means,
              check_merge_monoid, check_decomposition, check_spatial_split, check_bilinear_fix_runs,
              check_cosine_weights, check_frozen_matches_solve, check_radiosity_furnace,
              check_reference_lone_wall, check_iterations,
              check_dda_against_slabs, check_box_solid_angle, check_furnace_3d, check_bent_rays_seal,
              check_bin_cosines, check_voxel_remerge, check_reference_rectangle):
    check()
    print(f"{check.__name__}: ok")
