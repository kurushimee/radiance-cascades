"""Flatland radiance cascades with an exact reference.

A scene is a set of non-crossing line segments. Each side of a segment has its own constant outgoing radiance, so
the radiance seen from any point is piecewise constant in angle, and every quantity radiance cascades estimate has an
exact value:

- `profile` sweeps the angles around each point and returns the radiance of the interval `[a, b]` exactly, as
  breakpoints and values;
- `trace` intersects arbitrary rays with the segments, the tracer the cascades themselves use;
- `solve` runs radiance cascades (vanilla merge or bilinear fix) and returns the merged cascades and the fluence at
  evaluation points;
- `decompose` splits the error of `solve` exactly into per-cascade terms (angular sampling of radiance and of
  transmittance, spatial reconstruction, cone-merge correlation) and the final gather.

Angles run over [0, 2*pi). Fluence is radiance integrated over all directions without a cosine.
"""
from dataclasses import dataclass, field

import numpy as np

try:
    import cupy as xp
except ImportError:  # without CuPy the tracer and the reference run on the CPU
    xp = np

TAU = 2 * np.pi
CHUNK = 1 << 23


def cross(u, v):
    return u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]


@dataclass
class Scene:
    """Segments `a -> b`; `left` and `right` are the outgoing radiance on each side, `sky` lights escaping rays."""

    a: np.ndarray
    b: np.ndarray
    left: np.ndarray
    right: np.ndarray
    sky: float = 0.0
    solids: list = field(default_factory=list)

    @classmethod
    def empty(cls, sky=0.0):
        return cls(np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0), np.zeros(0), sky)

    def add(self, a, b, left, right):
        a, b = np.atleast_2d(a).astype(float), np.atleast_2d(b).astype(float)
        self.a = np.vstack([self.a, a])
        self.b = np.vstack([self.b, b])
        self.left = np.concatenate([self.left, np.broadcast_to(left, len(a)).astype(float)])
        self.right = np.concatenate([self.right, np.broadcast_to(right, len(a)).astype(float)])
        return self

    def wall(self, p, q, radiance=0.0):
        """A segment with zero thickness, the same radiance on both sides."""
        return self.add(p, q, radiance, radiance)

    def polygon(self, points, radiance=0.0, inside=0.0):
        """A solid polygon with counter-clockwise points: `radiance` outside, `inside` on its inner faces."""
        points = np.asarray(points, float)
        self.solids.append(points)
        return self.add(points, np.roll(points, -1, axis=0), inside, radiance)

    def box(self, x0, y0, x1, y1, radiance=0.0, inside=0.0):
        return self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], radiance, inside)

    def shifted(self, offset):
        """The same scene moved by `offset`."""
        offset = np.asarray(offset, float)
        return Scene(self.a + offset, self.b + offset, self.left, self.right, self.sky,
                     [solid + offset for solid in self.solids])

    def inside_solid(self, points):
        """Even-odd test of each point against every solid polygon."""
        result = np.zeros(len(points), bool)
        x, y = points[:, 0], points[:, 1]
        for poly in self.solids:
            crossings = np.zeros(len(points), bool)
            for (x0, y0), (x1, y1) in zip(poly, np.roll(poly, -1, axis=0)):
                straddles = (y0 > y) != (y1 > y)
                with np.errstate(divide="ignore", invalid="ignore"):
                    xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                crossings ^= straddles & (x < xc)
            result |= crossings
        return result

    def check_no_crossings(self):
        """Exactness needs segments that meet only at shared endpoints."""
        e = self.b - self.a
        for i in range(len(self.a)):
            d = self.a - self.a[i]
            denom = cross(e[i], e)
            with np.errstate(divide="ignore", invalid="ignore"):
                u = cross(d, e) / denom
                v = cross(d, e[i]) / denom
            interior = (u > 1e-9) & (u < 1 - 1e-9) & (v > 1e-9) & (v < 1 - 1e-9)
            interior[i] = False
            if interior.any():
                raise ValueError(f"segment {i} crosses segments {np.nonzero(interior)[0]}")


def host(array):
    return xp.asnumpy(array) if xp is not np else array


def _device(scene):
    """Segment starts, edge vectors and side radiances on the compute device."""
    return tuple(xp.asarray(v) for v in (scene.a, scene.b - scene.a, scene.left, scene.right))


def _side_radiance(device, index, origins):
    """Radiance of segment `index` as seen from `origins`."""
    a, e, left, right = device
    facing_left = cross(e[index], origins - a[index]) > 0
    return xp.where(facing_left, left[index], right[index])


def _nearest(scene, origins, dirs, tmin, tmax):
    """Yields the rays a chunk at a time on the device, with the nearest segment each meets in `[tmin, tmax]`:
    (chunk, origins, tmax, segment, t, u), the hit at `a + u*(b - a)`, `t` infinite on a miss."""
    device = a, e, _, _ = _device(scene)
    origins, dirs = np.asarray(origins, float), np.asarray(dirs, float)
    count = len(origins)
    tmin = np.broadcast_to(np.asarray(tmin, float), (count,))
    tmax = np.broadcast_to(np.asarray(tmax, float), (count,))
    step = max(1, CHUNK // max(1, len(e)))
    # Rays move to the device a chunk at a time, so device memory stays bounded whatever the ray count.
    for lo in range(0, count, step):
        chunk = slice(lo, lo + step)
        o, d = xp.asarray(origins[chunk]), xp.asarray(dirs[chunk])
        near, far = xp.asarray(tmin[chunk])[:, None], xp.asarray(tmax[chunk])[:, None]
        ao = a[None] - o[:, None]
        denom = cross(d[:, None], e[None])
        with np.errstate(divide="ignore", invalid="ignore"):
            t = cross(ao, e[None]) / denom
            u = cross(ao, d[:, None]) / denom
        t = xp.where((u >= 0) & (u <= 1) & (t >= near) & (t <= far), t, np.inf)
        best = xp.argmin(t, axis=1)[:, None]
        yield (chunk, o, far[:, 0], best[:, 0], xp.take_along_axis(t, best, 1)[:, 0],
               xp.take_along_axis(u, best, 1)[:, 0])


def trace(scene, origins, dirs, tmin, tmax):
    """First hit of each ray `origin + t*dir`, `tmin <= t <= tmax`.

    Returns (radiance, hit, t). A ray that hits nothing returns radiance 0, or the sky if `tmax` is infinite.
    """
    device = _device(scene)
    count = len(origins)
    radiance, hit, best_t = np.empty(count), np.empty(count, bool), np.empty(count)
    for chunk, o, far, best, t, _ in _nearest(scene, origins, dirs, tmin, tmax):
        found = xp.isfinite(t)
        rad = xp.where(xp.isinf(far), scene.sky, 0.0)
        rad[found] = _side_radiance(device, best[found], o[found])
        radiance[chunk], hit[chunk], best_t[chunk] = host(rad), host(found), host(t)
    return radiance, hit, best_t


def first_hits(scene, origins, dirs, tmin, tmax):
    """Segment each ray hits first (-1 on a miss), where along it (`u` from 0 at `a` to 1 at `b`), and whether the
    ray arrives on its left side."""
    count = len(origins)
    segment, u, left = np.empty(count, int), np.empty(count), np.empty(count, bool)
    for chunk, o, _, best, t, along in _nearest(scene, origins, dirs, tmin, tmax):
        found = xp.isfinite(t)
        a, e = xp.asarray(scene.a)[best], xp.asarray(scene.b - scene.a)[best]
        segment[chunk] = host(xp.where(found, best, -1))
        u[chunk], left[chunk] = host(along), host(cross(e, o - a) > 0)
    return segment, u, left


def _clip_to_annulus(ra, e, a, b):
    """Parameter ranges u in [0, 1] where |ra + u*e| lies in [a, b]; up to two pieces per segment."""
    ee = (e * e).sum(-1)
    re = (ra * e).sum(-1)
    rr = (ra * ra).sum(-1)

    def roots(r):
        disc = re * re - ee * (rr - r * r)
        sq = xp.sqrt(xp.maximum(disc, 0))
        return (-re - sq) / ee, (-re + sq) / ee, disc > 0

    if np.isinf(b):
        lo, hi = xp.zeros_like(rr), xp.ones_like(rr)
    else:
        b0, b1, cuts = roots(b)
        lo, hi = xp.where(cuts, xp.maximum(b0, 0), 1), xp.where(cuts, xp.minimum(b1, 1), 0)
    if a > 0:
        a0, a1, cuts = roots(a)
        a0, a1 = xp.where(cuts, a0, 2), xp.where(cuts, a1, 2)
    else:
        a0 = a1 = xp.full_like(rr, 2)
    pieces_lo = xp.stack([lo, xp.maximum(a1, lo)], -1)
    pieces_hi = xp.stack([xp.minimum(a0, hi), hi], -1)
    single = a0 >= 2
    pieces_hi[..., 1] = xp.where(single, -1, pieces_hi[..., 1])
    return pieces_lo, pieces_hi


def profile(scene, points, a, b):
    """Exact angular profile of the interval `[a, b]` around each point.

    Returns (theta, radiance, hit): `theta` has shape (P, M + 1), sorted from 0 to 2*pi, and `radiance` and `hit`
    have shape (P, M), constant on each angular cell. Misses carry the sky when `b` is infinite and 0 otherwise.
    """
    return tuple(host(v) for v in _profile(scene, points, a, b))


def _profile(scene, points, a, b):
    """`profile` with its results left on the compute device."""
    device = scene_a, e, _, _ = _device(scene)
    points = xp.atleast_2d(xp.asarray(points, float))
    n = len(e)
    count = len(points)
    cells = 4 * n + 1
    thetas = xp.empty((count, cells + 1))
    radiance = xp.empty((count, cells))
    hits = xp.empty((count, cells), bool)
    miss = scene.sky if np.isinf(b) else 0.0
    step = max(1, CHUNK // max(1, cells * 2 * n))
    for lo in range(0, count, step):
        p = points[lo:lo + step]
        ra = scene_a[None] - p[:, None]
        ulo, uhi = _clip_to_annulus(ra, e[None], a, b)
        valid = uhi > ulo
        ends = xp.concatenate([ulo, uhi], -1)
        xy = ra[:, :, None, :] + ends[..., None] * e[None, :, None, :]
        angle = xp.mod(xp.arctan2(xy[..., 1], xy[..., 0]), TAU)
        angle = xp.where(xp.concatenate([valid, valid], -1), angle, 0.0).reshape(len(p), -1)
        theta = xp.sort(xp.concatenate([xp.zeros((len(p), 1)), angle, xp.full((len(p), 1), TAU)], 1), axis=1)
        mid = 0.5 * (theta[:, 1:] + theta[:, :-1])
        d = xp.stack([xp.cos(mid), xp.sin(mid)], -1)
        # Ray from the point along each cell's mid-angle against each segment's line.
        denom = cross(d[:, :, None, :], e[None, None])
        with np.errstate(divide="ignore", invalid="ignore"):
            t = cross(ra[:, None], e[None, None]) / denom
            u = cross(ra[:, None], d[:, :, None, :]) / denom
        inside = ((u[..., None] >= ulo[:, None]) & (u[..., None] <= uhi[:, None]) & valid[:, None]).any(-1)
        t = xp.where(inside & (t > 0), t, np.inf)
        nearest = xp.argmin(t, axis=-1)
        found = xp.isfinite(xp.take_along_axis(t, nearest[..., None], -1)[..., 0])
        rad = xp.full(found.shape, miss)
        rows = xp.nonzero(found)
        rad[rows] = _side_radiance(device, nearest[rows], p[rows[0]])
        thetas[lo:lo + step] = theta
        radiance[lo:lo + step] = rad
        hits[lo:lo + step] = found
    return thetas, radiance, hits


def window_means(theta, values, edges):
    """Mean of each piecewise-constant row over the windows between consecutive `edges` (shared by all rows)."""
    theta, values, edges = xp.asarray(theta), xp.asarray(values), xp.asarray(edges)
    rows, cells = values.shape
    widths = xp.diff(theta, axis=1)
    cumulative = xp.concatenate([xp.zeros((rows, 1)), xp.cumsum(values * widths, axis=1)], 1)
    # Rows lie in [0, 2*pi]; shifting row r by 2*TAU*r makes one sorted array, searched once for all rows.
    shift = 2 * TAU * xp.arange(rows)[:, None]
    found = xp.searchsorted((theta + shift).ravel(), (edges[None] + shift).ravel(), side="right")
    row = xp.arange(rows)[:, None]
    idx = xp.clip(found.reshape(rows, -1) - 1 - (cells + 1) * row, 0, cells - 1)
    at = cumulative[row, idx] + values[row, idx] * (edges[None] - theta[row, idx])
    return host(xp.diff(at, axis=1) / xp.diff(edges)[None])


def cone_means(scene, points, a, b, cones):
    """Exact mean radiance and transmittance over `cones` equal cones, for the interval `[a, b]` at each point."""
    theta, rad, hit = _profile(scene, points, a, b)
    edges = np.linspace(0, TAU, cones + 1)
    return window_means(theta, rad, edges), window_means(theta, (~hit).astype(float), edges)


def fluence(scene, points):
    theta, rad, _ = _profile(scene, points, 0.0, np.inf)
    return host((rad * xp.diff(theta, axis=1)).sum(1))


@dataclass(frozen=True)
class Params:
    """Cascade `n` has probe spacing `ds0*2**n`, `n0*k**n` directions and the interval
    `[t0*l**(n-1), t0*l**n]` (cascade 0 starts at 0, the top cascade runs to infinity); `s` rays per cone."""

    ds0: float = 1.0
    n0: int = 32
    k: int = 2
    l: float = 4.0
    t0: float = 1.0
    levels: int = 5
    s: int = 1
    overlap: float = 0.0

    def spacing(self, n):
        return self.ds0 * 2.0 ** n

    def directions(self, n):
        return self.n0 * self.k ** n

    def boundary(self, n):
        """Where cascade `n` hands over to cascade `n + 1`."""
        return self.t0 * self.l ** n

    def interval(self, n):
        """Traced range of cascade `n`; `overlap` extends each end by that many upper probe spacings."""
        start = 0.0 if n == 0 else self.boundary(n - 1)
        end = np.inf if n == self.levels - 1 else self.boundary(n) + self.overlap * self.spacing(n + 1)
        return start, end


class Grid:
    """Probe centres `(i + 0.5) * spacing` covering a window."""

    def __init__(self, spacing, lo, hi):
        self.spacing = spacing
        self.i0 = np.floor(np.asarray(lo) / spacing - 0.5).astype(int)
        self.i1 = np.ceil(np.asarray(hi) / spacing - 0.5).astype(int) + 1
        self.shape = (self.i1[1] - self.i0[1], self.i1[0] - self.i0[0])

    def points(self):
        ix = (np.arange(self.i0[0], self.i1[0]) + 0.5) * self.spacing
        iy = (np.arange(self.i0[1], self.i1[1]) + 0.5) * self.spacing
        x, y = np.meshgrid(ix, iy)
        return np.stack([x.ravel(), y.ravel()], -1)

    def bilinear(self, points):
        """Corner indices (4, P) into the flattened grid and weights (4, P)."""
        f = points / self.spacing - 0.5 - self.i0
        base = np.floor(f).astype(int)
        w = f - base
        if (base.min(0) < 0).any() or (base[:, 0].max() + 1 >= self.shape[1]) or (base[:, 1].max() + 1 >= self.shape[0]):
            raise ValueError("bilinear lookup outside the grid")
        idx, wts = [], []
        for dy in (0, 1):
            for dx in (0, 1):
                idx.append((base[:, 1] + dy) * self.shape[1] + base[:, 0] + dx)
                wts.append(np.where(dx, w[:, 0], 1 - w[:, 0]) * np.where(dy, w[:, 1], 1 - w[:, 1]))
        return np.array(idx), np.array(wts)


def grids(params, lo, hi):
    """Probe grids, each covering the bilinear lookups of the cascade below it."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    out = [Grid(params.spacing(0), lo, hi)]
    for n in range(1, params.levels):
        below = out[-1].points()
        out.append(Grid(params.spacing(n), below.min(0) - params.spacing(n), below.max(0) + params.spacing(n)))
    return out


def cone_rays(params, n, points):
    """Origins and directions of the `s` stratified rays of every cone: shape (P, N, s, 2)."""
    count = params.directions(n)
    angles = (np.arange(count)[:, None] + (np.arange(params.s)[None] + 0.5) / params.s) * TAU / count
    dirs = np.stack([np.cos(angles), np.sin(angles)], -1)
    return np.broadcast_to(points[:, None, None], (len(points), count, params.s, 2)), \
        np.broadcast_to(dirs[None], (len(points), count, params.s, 2))


def sample(scene, params, n, points):
    """Ray-sampled mean radiance and transmittance of each cone of cascade `n` at `points`: shape (P, N)."""
    origins, dirs = cone_rays(params, n, points)
    start, end = params.interval(n)
    rad, hit, _ = trace(scene, origins.reshape(-1, 2), dirs.reshape(-1, 2), start, end)
    shape = origins.shape[:3]
    return rad.reshape(shape).mean(-1), (~hit).reshape(shape).mean(-1)


def upper_mean(upper, params, n, idx, wts):
    """Bilinear blend of the upper cascade, averaged over the `k` children of each lower cone: shape (P, N_n)."""
    children = upper.reshape(upper.shape[0], params.directions(n), params.k).mean(-1)
    return np.einsum("cp,cpn->pn", wts, children[idx])


def bilinear_fix(scene, params, n, points, upper, upper_grid):
    """Lower cone value with one bent ray per child direction and upper probe, merged before blending."""
    idx, wts = upper_grid.bilinear(points)
    corners = upper_grid.points()[idx]                      # (4, P, 2)
    count, k = params.directions(n), params.k
    child = np.arange(count * k)
    angles = (child + 0.5) * TAU / (count * k)
    dirs = np.stack([np.cos(angles), np.sin(angles)], -1)   # (N*k, 2)
    start, end = params.interval(n)
    origins = points[None, :, None] + start * dirs[None, None]
    targets = corners[:, :, None] + end * dirs[None, None]
    delta = targets - origins
    length = np.linalg.norm(delta, axis=-1)
    rad, hit, _ = trace(scene, np.broadcast_to(origins, delta.shape).reshape(-1, 2),
                        (delta / length[..., None]).reshape(-1, 2), 0.0, length.ravel())
    shape = delta.shape[:3]
    far = upper[idx]                                        # (4, P, N*k)
    merged = rad.reshape(shape) + (~hit).reshape(shape) * far
    blended = np.einsum("cp,cpm->pm", wts, merged)
    return blended.reshape(len(points), count, k).mean(-1)


def solve(scene, params, lo, hi, eval_points, merge="vanilla"):
    """Radiance cascades over the window [lo, hi]; returns (fluence at eval_points, merged cascades, grids)."""
    gs = grids(params, lo, hi)
    merged = [None] * params.levels
    for n in reversed(range(params.levels)):
        points = gs[n].points()
        if n == params.levels - 1:
            merged[n], _ = sample(scene, params, n, points)
            continue
        if merge == "vanilla":
            j, beta = sample(scene, params, n, points)
            idx, wts = gs[n + 1].bilinear(points)
            merged[n] = j + beta * upper_mean(merged[n + 1], params, n, idx, wts)
        elif merge == "bilinear_fix":
            merged[n] = bilinear_fix(scene, params, n, points, merged[n + 1], gs[n + 1])
        else:
            raise ValueError(merge)
    return gather(merged[0], params, gs[0], eval_points), merged, gs


def gather(cascade0, params, grid0, eval_points):
    """Fluence at each evaluation point from the bilinear blend of cascade 0's cones."""
    idx, wts = grid0.bilinear(eval_points)
    probe_fluence = cascade0.sum(1) * TAU / params.directions(0)
    return (wts * probe_fluence[idx]).sum(0)


TERMS = ("angular_radiance", "angular_transmittance", "spatial", "correlation")


def decompose(scene, params, lo, hi, eval_points):
    """Exact split of the vanilla error `solve(...) - fluence(...)` at `eval_points`.

    Returns a dict: `terms[name]` is an array (levels, E) of each cascade's local error of that kind, carried to the
    evaluation points through the cascades below it; `gather` is the error of interpolating exact probe fluence;
    `estimate` and `exact` are the two fluences. The parts sum to `estimate - exact` to rounding.
    """
    gs = grids(params, lo, hi)
    levels = params.levels
    terms = {name: [None] * levels for name in TERMS}
    beta_hat = [None] * levels
    exact_upper = None
    for n in reversed(range(levels)):
        points = gs[n].points()
        count = params.directions(n)
        start, end = params.interval(n)
        j_hat, beta_hat[n] = sample(scene, params, n, points)
        j_bar, beta_bar = cone_means(scene, points, start, end, count)
        r_n, _ = cone_means(scene, points, start, np.inf, count)
        if n == levels - 1:
            local = {"angular_radiance": j_hat - j_bar, "angular_transmittance": np.zeros_like(j_hat),
                     "spatial": np.zeros_like(j_hat), "correlation": np.zeros_like(j_hat)}
        else:
            idx, wts = gs[n + 1].bilinear(points)
            x_hat = upper_mean(exact_upper, params, n, idx, wts)
            far_here, _ = cone_means(scene, points, end, np.inf, params.directions(n + 1))
            x_bar = far_here.reshape(len(points), count, params.k).mean(-1)
            local = {"angular_radiance": j_hat - j_bar,
                     "angular_transmittance": (beta_hat[n] - beta_bar) * x_hat,
                     "spatial": beta_bar * (x_hat - x_bar),
                     "correlation": beta_bar * x_bar - (r_n - j_bar)}
        for name in TERMS:
            terms[name][n] = local[name]
        exact_upper = r_n

    exact_probe = exact_upper.sum(1) * TAU / params.directions(0)
    idx0, wts0 = gs[0].bilinear(eval_points)
    exact = fluence(scene, eval_points)
    out = {"terms": {}, "gather": (wts0 * exact_probe[idx0]).sum(0) - exact, "exact": exact}
    for name in TERMS:
        out["terms"][name] = np.array([carry(terms[name][m], m, params, gs, beta_hat, eval_points)
                                       for m in range(levels)])
    out["estimate"], _, _ = solve(scene, params, lo, hi, eval_points)
    return out


def split_spatial(scene, params, lo, hi, n, samples=800, rays=16, seed=0):
    """Split cascade `n`'s local spatial term into seam parts and a parallax part, at sampled probes.

    An upper probe's offset from the lower probe has a component along each ray and one across it. The seam parts are
    what the along-ray component does: where the upper interval starts after the lower one ends, a surface between
    them is seen by neither (unseen); where it starts before, a surface there is seen by both (double). The parallax
    part is what remains with the start matched, the across-ray offset alone. All are cone means from `rays`
    stratified rays per upper cone. Returns (unseen, double, parallax), each of shape (samples, N_n).
    """
    gs = grids(params, lo, hi)
    rng = np.random.default_rng(seed)
    all_points = gs[n].points()
    points = all_points[rng.choice(len(all_points), min(samples, len(all_points)), replace=False)]
    count, k = params.directions(n), params.k
    _, end = params.interval(n)
    _, beta_bar = cone_means(scene, points, params.interval(n)[0], end, count)

    idx, wts = gs[n + 1].bilinear(points)
    corners = gs[n + 1].points()[idx]                                     # (4, P, 2)
    upper_count = count * k
    angles = (np.arange(upper_count)[:, None] + (np.arange(rays)[None] + 0.5) / rays) * TAU / upper_count
    dirs = np.stack([np.cos(angles), np.sin(angles)], -1)                 # (Nu, m, 2)

    def far(origins, tmin):
        shape = (origins.shape[0], len(points), upper_count, rays)
        o = np.broadcast_to(origins, shape + (2,)).reshape(-1, 2)
        d = np.broadcast_to(dirs, shape + (2,)).reshape(-1, 2)
        rad, _, _ = trace(scene, o, d, np.broadcast_to(tmin, shape).ravel(), np.inf)
        return rad.reshape(shape)

    def cone_mean(per_ray):
        return per_ray.mean(-1).reshape(per_ray.shape[0], len(points), count, k).mean(-1)

    def blend(per_ray):
        return beta_bar * np.einsum("cp,cpn->pn", wts, cone_mean(per_ray))

    far_p = cone_mean(far(points[None, :, None, None], end))[0]
    far_q = far(corners[:, :, None, None], params.boundary(n))
    offset = corners - points[None]                                       # (4, P, 2)
    along = (offset[:, :, None, None] * dirs[None, None]).sum(-1)         # (4, P, Nu, m)
    far_matched = far(corners[:, :, None, None] + (end - along)[..., None] * dirs[None, None], 0.0)
    seam = far_q - far_matched
    unseen = along > end - params.boundary(n)
    return blend(np.where(unseen, seam, 0.0)), blend(np.where(unseen, 0.0, seam)), \
        blend(far_matched) - beta_bar * far_p


def carry(field_m, m, params, gs, beta_hat, eval_points):
    """Carry an error field of cascade `m` down to the evaluation points through the vanilla merges below it."""
    current = field_m
    for n in reversed(range(m)):
        idx, wts = gs[n + 1].bilinear(gs[n].points())
        current = beta_hat[n] * upper_mean(current, params, n, idx, wts)
    return gather(current, params, gs[0], eval_points)
