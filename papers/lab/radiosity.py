"""Diffuse interreflection from one radiance cascades solve in flatland, with an exact reference.

Walls are segments whose two sides carry an emission and an albedo, split into patches of constant radiance. A patch
is shaded from the irradiance at its collocation point, half a cascade 0 spacing off its middle on its side:
`L = E + albedo/2 * Irr`, with `Irr` the radiance seen from that point weighted by `max(0, cos)` against the patch
normal, 2 for unit radiance all round.

With the walls fixed, each ray of a solve keeps the patch it hit, so the solve is a linear map of the patch radiance
and the sky:

- `freeze` traces a solve once and keeps, per cascade, its hit records and its merge as sparse matrices;
- `remerge` runs the frozen solve on any patch radiance, without tracing, as one more bounce does;
- `operator` collapses the frozen solve into one matrix from patch radiance and sky to collocation irradiance;
- `reference` is the exact matrix of the same map, from the oracle's angular profiles.

Matrices have one row per patch (zero where the albedo is zero) and one column per patch plus a last for the sky.
"""
from dataclasses import dataclass

import numpy as np
from scipy import sparse

import flatland as fl

TAU = fl.TAU


def cosine_integral(x):
    """Integral of `max(0, cos t)` from `-pi/2` to `x`, 2 per whole turn."""
    turns = np.floor((x + np.pi / 2) / TAU)
    return 2 * turns + 1 + np.sin(np.minimum(x - TAU * turns, np.pi / 2))


def cosine_weights(edges, normal):
    """`max(0, cos)` against each normal angle integrated over the windows between consecutive `edges`: (P, W)."""
    x = np.asarray(edges)[None] - np.asarray(normal)[:, None]
    return np.diff(cosine_integral(x), axis=1)


@dataclass
class Walls:
    """Segments with each side's emission and albedo, (S, 2) with the left side first, and the sky's radiance."""

    scene: fl.Scene
    emission: np.ndarray
    albedo: np.ndarray

    @classmethod
    def empty(cls, sky=0.0):
        return cls(fl.Scene.empty(sky), np.zeros((0, 2)), np.zeros((0, 2)))

    def wall(self, p, q, emission=0.0, albedo=0.0):
        """A segment `p -> q`; `emission` and `albedo` are one value for both sides or a (left, right) pair."""
        self.scene.wall(p, q)
        self.emission = np.vstack([self.emission, np.broadcast_to(emission, 2)])
        self.albedo = np.vstack([self.albedo, np.broadcast_to(albedo, 2)])
        return self

    def shifted(self, offset):
        return Walls(self.scene.shifted(offset), self.emission, self.albedo)


@dataclass
class Patches:
    """Each segment split into `count` equal pieces, the same on both sides. Patch `first[s, side] + piece` lies on
    side 0 (left) or 1 (right) of segment `s`; `point` and `normal` (an angle) are its collocation point and normal."""

    first: np.ndarray
    count: np.ndarray
    point: np.ndarray
    normal: np.ndarray
    emission: np.ndarray
    albedo: np.ndarray

    @property
    def size(self):
        return len(self.point)

    def of_hits(self, segment, u, left):
        """Patch index of each hit, -1 where `segment` is -1."""
        s = np.maximum(segment, 0)
        piece = np.clip(np.floor(u * self.count[s]).astype(int), 0, self.count[s] - 1)
        return np.where(segment >= 0, self.first[s, np.where(left, 0, 1)] + piece, -1)


def patches(walls, size=1.0, lift=0.5):
    """Patches of about `size` along every wall, with collocation points `lift` off the wall."""
    a, b = walls.scene.a, walls.scene.b
    e = b - a
    length = np.linalg.norm(e, axis=1)
    count = np.maximum(1, np.rint(length / size).astype(int))
    start = 2 * np.concatenate([[0], np.cumsum(count)[:-1]])
    first = np.stack([start, start + count], 1)

    left_normal = np.stack([-e[:, 1], e[:, 0]], 1) / length[:, None]
    point, normal, emission, albedo = [], [], [], []
    for s in range(len(a)):
        middles = a[s] + ((np.arange(count[s]) + 0.5) / count[s])[:, None] * e[s]
        for side, sign in ((0, 1), (1, -1)):
            n = sign * left_normal[s]
            point.append(middles + lift * n)
            normal.append(np.full(count[s], np.arctan2(n[1], n[0])))
            emission.append(np.full(count[s], walls.emission[s, side]))
            albedo.append(np.full(count[s], walls.albedo[s, side]))
    return Patches(first, count, *(np.concatenate(v) for v in (point, normal, emission, albedo)))


@dataclass
class Frozen:
    """A solve's rays, frozen. Per cascade from 0 up: `hits[n]` (texels, patches + 1) holds each texel's own rays'
    weights on the patches they hit and on the sky; `merge[n]` (texels, upper texels) the weights of the upper
    texels its misses read. `gather` (patches, cascade 0 texels) gives each receiver's irradiance."""

    hits: list
    merge: list
    gather: sparse.csr_matrix
    rays: int


def _blend(params, n, idx, wts, upper_texels):
    """Bilinear blend of the upper probes, averaged over each cone's children: (texels of n, upper texels)."""
    count, k = params.directions(n), params.k
    probes = idx.shape[1]
    shape = (4, probes, count, k)
    rows = np.broadcast_to(np.arange(probes * count).reshape(1, probes, count, 1), shape)
    cols = idx[:, :, None, None] * (count * k) + np.arange(count)[None, None, :, None] * k + np.arange(k)
    vals = np.broadcast_to(wts[:, :, None, None] / k, shape)
    return sparse.csr_matrix((vals.ravel(), (rows.ravel(), cols.ravel())), shape=(probes * count, upper_texels))


def _cone_rays(params, n, points):
    """Rays of the straight cones: texel, weight, origin, direction, and the cascade's interval."""
    origins, dirs = fl.cone_rays(params, n, points)
    texel = np.repeat(np.arange(len(points) * params.directions(n)), params.s)
    start, end = params.interval(n)
    weight = np.full(len(texel), 1.0 / params.s)
    return texel, weight, origins.reshape(-1, 2), dirs.reshape(-1, 2), start, end, None


def _fix_rays(params, n, points, upper_grid):
    """Rays of the bilinear fix: one per child direction and upper probe, from the lower interval's start to the
    upper probe's interval start; each miss reads that probe's child texel."""
    idx, wts = upper_grid.bilinear(points)
    corners = upper_grid.points()[idx]
    count, k = params.directions(n), params.k
    angles = (np.arange(count * k) + 0.5) * TAU / (count * k)
    dirs = np.stack([np.cos(angles), np.sin(angles)], -1)
    start, end = params.interval(n)
    origins = np.broadcast_to(points[None, :, None] + start * dirs[None, None], (4, len(points), count * k, 2))
    delta = corners[:, :, None] + end * dirs[None, None] - origins
    length = np.linalg.norm(delta, axis=-1)
    texel = np.broadcast_to((np.arange(len(points))[:, None] * count + np.arange(count * k) // k)[None], length.shape)
    upper = idx[:, :, None] * (count * k) + np.arange(count * k)
    weight = np.broadcast_to(wts[:, :, None] / k, length.shape)
    return (texel.ravel(), weight.ravel(), origins.reshape(-1, 2), (delta / length[..., None]).reshape(-1, 2), 0.0,
            length.ravel(), upper.ravel())


def freeze(walls, pt, params, lo, hi, merge="vanilla"):
    """Traces one solve over the window [lo, hi] and keeps its rays' hits and merge weights."""
    gs = fl.grids(params, lo, hi)
    hits, merges, rays = [], [], 0
    for n in range(params.levels):
        points = gs[n].points()
        texels = len(points) * params.directions(n)
        top = n == params.levels - 1
        if merge == "bilinear_fix" and not top:
            texel, weight, origins, dirs, tmin, tmax, upper = _fix_rays(params, n, points, gs[n + 1])
        elif merge in ("vanilla", "bilinear_fix"):
            texel, weight, origins, dirs, tmin, tmax, upper = _cone_rays(params, n, points)
        else:
            raise ValueError(merge)
        segment, u, left = fl.first_hits(walls.scene, origins, dirs, tmin, tmax)
        patch = pt.of_hits(segment, u, left)
        rays += len(texel)

        seen = patch >= 0 if not top else np.ones(len(patch), bool)
        column = np.where(patch >= 0, patch, pt.size)
        hits.append(sparse.csr_matrix((weight[seen], (texel[seen], column[seen])), shape=(texels, pt.size + 1)))
        if top:
            continue
        upper_texels = len(gs[n + 1].points()) * params.directions(n + 1)
        missed = patch < 0
        if upper is None:
            beta = np.bincount(texel[missed], weight[missed], texels)
            idx, wts = gs[n + 1].bilinear(points)
            merges.append(sparse.diags(beta) @ _blend(params, n, idx, wts, upper_texels))
        else:
            merges.append(sparse.csr_matrix((weight[missed], (texel[missed], upper[missed])),
                                            shape=(texels, upper_texels)))
    return Frozen(hits, merges, _gather(pt, params, gs[0]), rays)


def _gather(pt, params, grid0):
    """Irradiance at each receiver's collocation point from cascade 0, blended bilinearly between probes."""
    receivers = np.flatnonzero(pt.albedo > 0)
    count = params.directions(0)
    idx, wts = grid0.bilinear(pt.point[receivers])
    cone = cosine_weights(np.linspace(0, TAU, count + 1), pt.normal[receivers])     # (R, N)
    shape = (4, len(receivers), count)
    rows = np.broadcast_to(receivers[None, :, None], shape)
    cols = idx[:, :, None] * count + np.arange(count)
    vals = wts[:, :, None] * cone[None]
    return sparse.csr_matrix((vals.ravel(), (rows.ravel(), cols.ravel())),
                             shape=(pt.size, len(grid0.points()) * count))


def remerge(frozen, radiance, sky):
    """Merged cascade 0 of the frozen solve for patch `radiance` and `sky`, with no rays traced."""
    shaded = np.append(radiance, sky)
    merged = frozen.hits[-1] @ shaded
    for hits, merge in zip(reversed(frozen.hits[:-1]), reversed(frozen.merge)):
        merged = hits @ shaded + merge @ merged
    return merged


def operator(frozen):
    """The frozen solve as one dense matrix from patch radiance and sky to collocation irradiance."""
    reach = frozen.gather
    total = (reach @ frozen.hits[0]).toarray()
    for n in range(1, len(frozen.hits)):
        reach = reach @ frozen.merge[n - 1]
        total += (reach @ frozen.hits[n]).toarray()
    return total


def reference(walls, pt):
    """Exact collocation irradiance as a dense matrix from patch radiance and sky."""
    # One segment per piece, carrying its two patches' indices as radiance and -1 as the sky, makes the oracle's
    # angular profile name the patch each angular cell sees.
    a, b = walls.scene.a, walls.scene.b
    ids = fl.Scene.empty(sky=-1.0)
    for s in range(len(a)):
        f = (np.arange(pt.count[s] + 1) / pt.count[s])[:, None]
        ends = a[s] + f * (b[s] - a[s])
        piece = np.arange(pt.count[s])
        ids.add(ends[:-1], ends[1:], pt.first[s, 0] + piece, pt.first[s, 1] + piece)

    receivers = np.flatnonzero(pt.albedo > 0)
    out = np.zeros((pt.size, pt.size + 1))
    for chunk in np.array_split(receivers, max(1, len(receivers) // 64)):
        theta, seen, _ = fl.profile(ids, pt.point[chunk], 0.0, np.inf)
        x = theta - pt.normal[chunk, None]
        weight = np.diff(cosine_integral(x), axis=1)
        column = np.where(seen < 0, pt.size, np.rint(seen)).astype(int)
        np.add.at(out, (np.broadcast_to(chunk[:, None], column.shape), column), weight)
    return out


def bounce_matrix(pt, irradiance):
    """`K` with `L = E + K[:, :-1] @ L + K[:, -1] * sky`."""
    return 0.5 * pt.albedo[:, None] * irradiance


def converged(K, emission, sky):
    """The fixed point of `L = E + K[:, :-1] @ L + K[:, -1] * sky`, solved directly."""
    return np.linalg.solve(np.eye(len(emission)) - K[:, :-1], emission + K[:, -1] * sky)


# Each method below starts from the emission alone and returns its estimate after each pass. A pass is one
# application of the solve: `bounce(L)` shades every hit with L and every escape with the sky and returns
# `E + K L + k sky`; `linear(v)` is the same with no emission and no sky, `K v`.

def plain(bounce, emission, passes):
    """One bounce per pass."""
    out = [bounce(emission)]
    while len(out) < passes:
        out.append(bounce(out[-1]))
    return out


def tail(bounce, emission, passes):
    """Plain bounces plus the geometric tail of the series, its ratio taken from the last two bounces."""
    steps = plain(bounce, emission, passes)
    out = [steps[0]]
    for before, last, now in zip([emission] + steps, steps, steps[1:]):
        change = (last - before).sum()
        ratio = (now - last).sum() / change if change else 0.0
        out.append(now + (now - last) * ratio / (1 - ratio) if ratio < 1 else now)
    return out


def ambient(bounce, emission, passes, albedo, surfaces):
    """Plain bounces plus an ambient term, as in progressive radiosity: the light of the last bounce, spread evenly
    over the `surfaces` of the scene (all of equal area), reflected again and again at their mean albedo."""
    mean_albedo = albedo[surfaces].mean()
    steps = plain(bounce, emission, passes)
    return [now + albedo * (now - before)[surfaces].mean() / (1 - mean_albedo)
            for before, now in zip([emission] + steps, steps)]


def gmres(bounce, linear, emission, passes):
    """GMRES on `(I - K) L = E + k sky` from `L = E`: the first pass gives the residual, each later pass one Krylov
    vector. Each estimate is the residual minimizer plus one bounce, which the known residual gives for free."""
    r0 = bounce(emission) - emission
    beta = np.linalg.norm(r0)
    basis = [r0 / beta]
    h = np.zeros((passes, max(1, passes - 1)))
    out = [emission + r0]
    for j in range(passes - 1):
        w = basis[j] - linear(basis[j])
        for _ in range(2):  # Gram-Schmidt twice keeps the basis orthogonal to rounding
            for i in range(j + 1):
                c = basis[i] @ w
                h[i, j] += c
                w = w - c * basis[i]
        h[j + 1, j] = np.linalg.norm(w)
        basis.append(w / h[j + 1, j])
        rhs = np.zeros(j + 2)
        rhs[0] = beta
        y = np.linalg.lstsq(h[:j + 2, :j + 1], rhs, rcond=None)[0]
        residual = rhs - h[:j + 2, :j + 1] @ y
        out.append(emission + np.array(basis[:j + 1]).T @ y + np.array(basis).T @ residual)
    return out
