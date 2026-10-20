"""Radiance cascades on surface probes in a voxel volume, with a Monte Carlo reference at the probe points.

The surface is the set of exposed faces of solid voxels whose front voxel lies inside the volume. Cascade 0 holds one
probe per face, at its centre lifted `bias` along the normal, with equal-area bins over the hemisphere around the
normal and the interval [0, t0]. The cascades above it live in one of two places:

- `World`: sphere probes on volume.py's grids (spacing 2**c, 2 * bins * 4**c directions, interval
  [t0 4**(c-1), t0 4**c]), merged among themselves by volume.py and read by cascade 0 through the corners of the grid
  cell around each probe;
- `Atlas`: hemisphere probes on a lattice of spacing 2**c laid over each chart, a connected planar patch of faces
  with one normal; each lattice point sits on the chart face nearest to it and is read through the four corners of
  its lattice cell, clamped to the chart.

Every ray keeps its hit record, so `irradiance` re-shades the records for any face radiance and re-merges with no
rays, as radiosity3d.Frozen does. `cost["records"]` counts, per cascade, the rays a static solve keeps: those some
merge reads, found by following which parents each texel reads from cascade 0 up.
"""
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import cupy as cp
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "papers" / "lab"))

import radiosity3d as rd3  # noqa: E402
import volume as vo  # noqa: E402

MERGES = ("vanilla", "self_test", "trilinear_fix", "kuhn_fix")
ATLAS_MERGES = ("vanilla", "self_test", "bilinear_fix")
BENT = ("trilinear_fix", "kuhn_fix", "bilinear_fix")

# Face f = 2*axis + (normal points to +axis): rows tangent, bitangent, normal.
FRAMES = np.zeros((6, 3, 3))
for _f in range(6):
    FRAMES[_f, 2, _f // 2] = 1.0 if _f % 2 else -1.0
    FRAMES[_f, 0, (_f // 2 + 1) % 3] = 1.0
    FRAMES[_f, 1] = np.cross(FRAMES[_f, 2], FRAMES[_f, 0])


@dataclass(frozen=True)
class Hemisphere:
    """Equal-area bins over the hemisphere around a normal: `cols` azimuth sectors by `rows` bands of equal height in
    `cos θ`, bin (j, k) at index j * rows + k, the sectors turned by `phi0`. `finer()` splits every bin in four."""

    cols: int
    rows: int
    phi0: float = 0.3

    @classmethod
    def of(cls, bins, phi0=0.3):
        a = math.isqrt(bins // 4)
        assert 4 * a * a == bins, "hemisphere bins must be 4 a^2"
        return cls(4 * a, a, phi0)

    @property
    def size(self):
        return self.cols * self.rows

    def finer(self):
        return Hemisphere(2 * self.cols, 2 * self.rows, self.phi0)

    def centres(self):
        """Bin centre directions in local coordinates, z along the normal: (size, 3)."""
        j, k = np.divmod(np.arange(self.size), self.rows)
        phi = (j + 0.5) * 2 * math.pi / self.cols + self.phi0
        z = (k + 0.5) / self.rows
        r = np.sqrt(1 - z * z)
        return np.stack([r * np.cos(phi), r * np.sin(phi), z], -1)

    def children(self):
        """The four bins of `finer()` inside each bin: (size, 4)."""
        j, k = np.divmod(np.arange(self.size), self.rows)
        return np.stack([(2 * j + dj) * (2 * self.rows) + 2 * k + dk for dj in (0, 1) for dk in (0, 1)], -1)

    def cosines(self):
        """`cos θ` integrated over each bin; they sum to pi."""
        k = np.arange(self.size) % self.rows
        return math.pi / self.cols * (((k + 1) / self.rows) ** 2 - (k / self.rows) ** 2)

    def bin_of(self, local):
        """Bin of each local direction (device array, last axis xyz), or -1 at or below the horizon."""
        phi = (cp.arctan2(local[..., 1], local[..., 0]) - self.phi0) % (2 * math.pi)
        j = cp.minimum((phi * self.cols / (2 * math.pi)).astype(cp.int32), self.cols - 1)
        k = cp.clip((local[..., 2] * self.rows).astype(cp.int32), 0, self.rows - 1)
        return cp.where(local[..., 2] > 0, j * self.rows + k, -1)


class Surface:
    """The probe-carrying faces of a volume: radiosity3d.Faces plus each face's frame and probe position."""

    def __init__(self, volume, bias=0.05):
        self.volume, self.bias = volume, bias
        self.faces = rd3.Faces(volume)
        self.active = np.flatnonzero(self.faces.neighbour >= 0)
        self.cell = np.stack(np.unravel_index(self.faces.voxel[self.active], (volume.n,) * 3), -1)
        self.code = self.faces.face[self.active]
        self.frame = FRAMES[self.code]
        normal = self.frame[:, 2]
        self.centre = self.cell + 0.5 + 0.5 * normal
        self.position = self.centre + bias * normal
        self._exposed = cp.asarray(np.maximum(self.faces.exposed_count, 1))
        self._nearest = cp.asarray(self.faces.nearest_exposed)
        self._table = cp.asarray(self.faces.table, cp.int32)

    @property
    def size(self):
        return len(self.active)

    def shade_table(self, radiance):
        """7 values per voxel for face `radiance` (one per face of the volume): its six faces, then what a ray that
        starts inside it sees, the mean of the nearest exposed voxel's faces."""
        values = cp.asarray(radiance, cp.float32)
        mean = cp.bincount(cp.asarray(self.faces.voxel), values, minlength=self._table.shape[0]) / self._exposed
        table = cp.where(self._table >= 0, values[cp.maximum(self._table, 0)], 0.0)
        return cp.ascontiguousarray(cp.concatenate([table, mean[self._nearest][:, None]], 1).astype(cp.float32).ravel())


@dataclass
class Rays:
    """Hit records of a batch of rays, any shape: the voxel and face each hit (-1 when none) and the distance."""

    voxel: cp.ndarray
    face: cp.ndarray
    t: cp.ndarray

    @classmethod
    def trace(cls, volume, origins, dirs, tmin, tmax):
        shape = dirs.shape[:-1]
        origins = cp.ascontiguousarray(cp.broadcast_to(cp.asarray(origins, cp.float32), dirs.shape)).reshape(-1, 3)
        tmin = cp.broadcast_to(cp.asarray(tmin, cp.float32), shape).ravel()
        tmax = cp.broadcast_to(cp.asarray(tmax, cp.float32), shape).ravel()
        _, _, t, voxel, face = vo.trace(volume, origins, cp.asarray(dirs, cp.float32).reshape(-1, 3), tmin, tmax)
        return cls(voxel.reshape(shape), face.reshape(shape), t.reshape(shape))

    @classmethod
    def segments(cls, volume, start, end):
        """Rays from each start point to its end point, distances measured from the start."""
        gap = end - start
        length = cp.linalg.norm(gap, axis=-1)
        return cls.trace(volume, start, gap / length[..., None], 0.0, length)

    @property
    def hit(self):
        return self.voxel >= 0

    def shade(self, table, miss=0.0):
        seen = table[7 * cp.maximum(self.voxel, 0) + cp.where(self.face >= 0, self.face, 6).astype(cp.int32)]
        return cp.where(self.hit, seen, miss).astype(cp.float32)


def corners(points, start, count, h, kuhn=False):
    """Probes of the grid of spacing h (first probe at (start + 0.5) h, `count` per axis) around each point (device
    (k, 3)): the 8 trilinear corners or the 4 of the Kuhn tetrahedron, as index (k, V), position (k, V, 3), weight."""
    f = cp.asarray(points, cp.float64) / h - 0.5
    base = cp.floor(f)
    frac = f - base
    k = len(f)
    if kuhn:
        order = cp.argsort(-frac, axis=1)
        steps = cp.zeros((k, 4, 3))
        rows = cp.arange(k)
        for v in range(1, 4):
            steps[:, v] = steps[:, v - 1]
            steps[rows, v, order[:, v - 1]] = 1.0
        bounds = cp.concatenate([cp.ones((k, 1)), cp.take_along_axis(frac, order, 1), cp.zeros((k, 1))], 1)
        weight = bounds[:, :4] - bounds[:, 1:]
    else:
        steps = cp.broadcast_to(cp.asarray([[v >> 2, (v >> 1) & 1, v & 1] for v in range(8)], cp.float64), (k, 8, 3))
        weight = cp.prod(cp.where(steps > 0, frac[:, None], 1 - frac[:, None]), axis=2)
    cell = base[:, None] + steps
    local = cp.clip(cell.astype(cp.int64) - cp.asarray(start), 0, cp.asarray(count) - 1)
    index = (local[..., 0] * int(count[1]) + local[..., 1]) * int(count[2]) + local[..., 2]
    return index, ((cell + 0.5) * h).astype(cp.float32), weight.astype(cp.float32)


def world_around(params, c, dirs):
    """The four bins of volume.py's cascade c map around each direction (device (..., 3)), with bilinear weights."""
    m = params.m0 * 2 ** c
    u = dirs @ cp.asarray(np.reshape(params.rotation, (3, 3)), cp.float32)
    phi = cp.arctan2(u[..., 1], u[..., 0]) % (2 * math.pi)
    x, y = phi * m / math.pi - 0.5, (u[..., 2] + 1) * 0.5 * m - 0.5
    j, k = cp.floor(x).astype(cp.int32), cp.floor(y).astype(cp.int32)
    fx, fy = x - j, y - k
    j0, j1 = (j + 2 * m) % (2 * m), (j + 1) % (2 * m)
    k0, k1 = cp.maximum(k, 0), cp.minimum(k + 1, m - 1)
    bins = cp.stack([j0 * m + k0, j1 * m + k0, j0 * m + k1, j1 * m + k1], -1)
    weights = cp.stack([(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy], -1)
    return bins, weights.astype(cp.float32)


def combine(mode, own_rad, own_hit, value, weight, bent=None, test=None):
    """Merged radiance of lower texels (P, B) from parent values (P, B, S, V) toward S sub-directions at parent
    weights (P, V).

    `test` is the self test's (keep, seen, blocked) for each sub-direction and parent: whether the parent is kept, the
    radiance the lower probe's own ray saw toward it, and whether that ray stopped short of it. `bent` is the bent
    rays' (hit, radiance), (P, B, V)."""
    w = weight[:, None, None, :]
    if mode in BENT:
        hit, radiance = bent
        return (cp.where(hit, radiance, value.mean(2)) * weight[:, None, :]).sum(-1)
    if mode == "self_test":
        keep, seen, blocked = test
        kept_w = (keep * w).sum(-1)
        kept = (value * keep * w).sum(-1) / cp.maximum(kept_w, 1e-12)
        blocked_w = (blocked * w).sum(-1)
        fallback = cp.where(blocked_w > 0, (seen * blocked * w).sum(-1) / cp.maximum(blocked_w, 1e-12),
                            (value * w).sum(-1))
        merged = cp.where(kept_w > 0, kept, fallback).mean(-1)
    else:
        merged = (value * w).sum(-1).mean(-1)
    return cp.where(own_hit, own_rad, merged)


def self_test(own, frame, hemi, origin, parent_pos, sub, t_join, tau, own_rad):
    """The self test for lower probes at `origin` (P, 3) in `frame` (P, 3, 3): a parent at `parent_pos` (P, V, 3)
    is dropped toward sub-direction `sub` (P, B, S, 3) when the start of its ray lies at or below the lower probe's
    horizon, or when the lower probe's own ray toward that start stopped more than `tau` short of it."""
    start = parent_pos[:, None, None] + t_join * sub[:, :, :, None]  # (P, B, S, V, 3)
    gap = start - origin[:, None, None, None]
    distance = cp.linalg.norm(gap, axis=-1)
    bins = hemi.bin_of(cp.einsum("pbsvk,pjk->pbsvj", gap, frame))
    rows = cp.arange(len(origin))[:, None, None, None]
    safe = cp.maximum(bins, 0)
    reached = cp.where(own.hit[rows, safe], own.t[rows, safe], cp.inf)
    above = bins >= 0
    blocked = above & (reached < distance - tau)
    return above & ~blocked, own_rad[rows, safe], blocked


class World:
    """Cascade 0 on the faces, cascades 1 and up on volume.py's sphere grids.

    `surface_merge` is the merge at the hand-over from the faces to cascade 1 (one of MERGES); `world_merge` names
    volume.py's merge at every hand-over above, or lists one per hand-over from cascade 1 up. With `front`, cascade 0
    drops the parents on or behind its tangent plane and renormalizes the weights of the rest. With `nearest`, each
    sub-direction reads one bin of a cascade 1 probe, the nearest, instead of four bilinearly."""

    def __init__(self, surface, bins=16, t0=None, surface_merge="self_test", world_merge="self_test",
                 rotation=None, tau=0.5, front=False, nearest=False):
        volume = surface.volume
        self.surface, self.hemi, self.tau, self.surface_merge = surface, Hemisphere.of(bins), tau, surface_merge
        n0 = 2 * bins
        self.t0 = t0 if t0 is not None else math.sqrt(n0 / (4 * math.pi))
        levels = vo.levels_for(volume.n, self.t0)
        self.params = vo.Params(n0=n0, t0=self.t0, levels=levels, rotation=rotation or vo.generic_rotation())
        above = [world_merge] * (levels - 2) if isinstance(world_merge, str) else list(world_merge)
        self.world_merges = ["vanilla"] + above
        self.levels, _ = vo.cascades(volume, self.params, merges=self.world_merges)

        self.frame = cp.asarray(surface.frame, cp.float32)
        self.origin = cp.asarray(surface.position, cp.float32)
        self.dirs = cp.einsum("bj,pjk->pbk", cp.asarray(self.hemi.centres(), cp.float32), self.frame)
        self.own = Rays.trace(volume, self.origin[:, None], self.dirs, 0.0, self.t0)
        start, count = vo.grids(self.params, volume.n)[1]
        self.index, self.parent_pos, self.weight = corners(self.origin, start, count, 2.0, surface_merge == "kuhn_fix")
        if front:
            ahead = cp.einsum("pvk,pk->pv", self.parent_pos - self.origin[:, None], self.frame[:, 2]) > 0
            kept = self.weight * ahead
            total = kept.sum(1, keepdims=True)
            self.weight = cp.where(total > 0, kept / cp.maximum(total, 1e-12), self.weight)
        sub = cp.asarray(self.hemi.finer().centres()[self.hemi.children()], cp.float32)
        self.sub = cp.einsum("bsj,pjk->pbsk", sub, self.frame)
        self.sub_bins, self.sub_weights = world_around(self.params, 1, self.sub)
        if nearest:
            self.sub_bins = cp.take_along_axis(self.sub_bins, self.sub_weights.argmax(-1)[..., None], -1)
            self.sub_weights = cp.ones(self.sub_bins.shape, cp.float32)
        if surface_merge in BENT:
            end = self.parent_pos[:, None] + self.t0 * self.dirs[:, :, None]
            self.bent = Rays.segments(volume, cp.broadcast_to(self.origin[:, None, None], end.shape), end)
        self.cost = {"records": self._records()}
        self.cost["total"] = sum(self.cost["records"])

    def _parent_values(self, radiance1):
        """Each parent's radiance toward each sub-direction, read bilinearly between its bins: (P, B, S, V)."""
        rows = radiance1[self.index]  # (P, V, M)
        picked = rows[cp.arange(len(rows))[:, None, None, None, None], cp.arange(rows.shape[1])[None, None, None, :,
                                                                                               None],
                      self.sub_bins[:, :, :, None, :]]
        return (picked * self.sub_weights[:, :, :, None, :]).sum(-1)

    def merged0(self, table, sky):
        """Cascade 0's merged radiance (P, B) for the shading `table` and `sky`."""
        own = []
        for c, level in enumerate(self.levels):
            rays = Rays(level["voxel"].ravel(), level["face"].ravel(), None)
            own.append(rays.shade(table, sky if math.isinf(self.params.interval(c)[1]) else 0.0))
        merged, _ = vo.remerge(self.surface.volume, self.params, self.levels, own, table,
                                             merges=self.world_merges)
        value = self._parent_values(merged[1])
        own_rad = self.own.shade(table)
        bent = test = None
        if self.surface_merge in BENT:
            bent = (self.bent.hit, self.bent.shade(table))
        if self.surface_merge == "self_test":
            test = self_test(self.own, self.frame, self.hemi, self.origin, self.parent_pos, self.sub, self.t0,
                             self.tau, own_rad)
        return combine(self.surface_merge, own_rad, self.own.hit, value, self.weight, bent, test)

    def irradiance(self, radiance, sky):
        """Irradiance at every face of the volume (host array, zero where no probe) for face `radiance` and `sky`."""
        merged = self.merged0(self.surface.shade_table(radiance), sky)
        out = np.zeros(self.surface.faces.size)
        out[self.surface.active] = (merged @ cp.asarray(self.hemi.cosines(), cp.float32)).get()
        return out

    def _records(self):
        P, B = self.own.voxel.shape
        bent = self.surface_merge in BENT
        records = [B * int((self.weight > 0).sum()) if bent else P * B]
        reads = cp.ones((P, B), bool) if bent else ~self.own.hit
        shape = (P, B, self.sub_bins.shape[2], self.weight.shape[1], self.sub_bins.shape[-1])
        mask = cp.broadcast_to(reads[:, :, None, None, None] & (self.weight[:, None, None, :, None] > 0), shape)
        rows = cp.broadcast_to(self.index[:, None, None, :, None], mask.shape)
        cols = cp.broadcast_to(self.sub_bins[:, :, :, None, :], mask.shape)
        need = cp.zeros(self.levels[1]["hit"].shape, bool)
        need[rows[mask], cols[mask]] = True
        grids = vo.grids(self.params, self.surface.volume.n)
        for c in range(1, self.params.levels):
            merge = self.world_merges[c] if c < self.params.levels - 1 else "vanilla"
            bent, kuhn = merge in BENT, merge == "kuhn_fix"
            records.append(int(need.sum()) * ((4 if kuhn else 8) if bent else 1))
            if c == self.params.levels - 1:
                break
            probes, bins = cp.nonzero(need if bent else need & ~cp.isfinite(self.levels[c]["hit"]))
            start, count = grids[c]
            cell = cp.stack(cp.unravel_index(probes, tuple(int(x) for x in count)), -1) + cp.asarray(start)
            index, _, weight = corners((cell + 0.5) * 2.0 ** c, *grids[c + 1], 2.0 ** (c + 1), kuhn)
            m = self.params.m0 * 2 ** c
            child = cp.stack([(2 * (bins // m) + k // 2) * (2 * m) + 2 * (bins % m) + k % 2 for k in range(4)], -1)
            keep = cp.broadcast_to((weight > 0)[:, :, None], (*index.shape, 4))
            need = cp.zeros(self.levels[c + 1]["hit"].shape, bool)
            need[cp.broadcast_to(index[:, :, None], keep.shape)[keep], cp.broadcast_to(child[:, None], keep.shape)[keep]] \
                = True
        return records


class Charts:
    """Connected planar patches of the surface's faces with one normal, and lattices of spacing 2**c over each."""

    def __init__(self, surface):
        self.surface = surface
        n = surface.volume.n
        axis = surface.code // 2
        plane = surface.cell[np.arange(surface.size), axis] + surface.code % 2
        u = surface.cell[np.arange(surface.size), (axis + 1) % 3]
        v = surface.cell[np.arange(surface.size), (axis + 2) % 3]
        self.chart = np.full(surface.size, -1)
        count = 0
        for key in np.unique(surface.code * (n + 1) + plane):
            members = np.flatnonzero(surface.code * (n + 1) + plane == key)
            grid = np.zeros((n, n), bool)
            grid[u[members], v[members]] = True
            labels, found = ndimage.label(grid)
            self.chart[members] = labels[u[members], v[members]] - 1 + count
            count += found
        self.count = count
        self.lo = np.stack([[u[self.chart == k].min(), v[self.chart == k].min()] for k in range(count)])
        self.size = np.stack([[u[self.chart == k].max(), v[self.chart == k].max()] for k in range(count)]) + 1 - self.lo
        self.xy = np.stack([u, v], -1) - self.lo[self.chart] + 0.5  # chart coordinates of each face centre
        self.trees = [cKDTree(self.xy[self.chart == k]) for k in range(count)]
        self.members = [np.flatnonzero(self.chart == k) for k in range(count)]

    def lattice(self, c):
        """Lattice of spacing 2**c over every chart: per node its chart, ideal chart coordinates, and the face it
        sits on; and per chart the first node index and the node counts per axis."""
        h = 2.0 ** c
        counts = np.maximum(1, np.ceil(self.size / h).astype(int))
        first = np.concatenate([[0], np.cumsum(counts.prod(1))[:-1]])
        chart, xy, face = [], [], []
        for k in range(self.count):
            i, j = np.meshgrid(np.arange(counts[k, 0]), np.arange(counts[k, 1]), indexing="ij")
            ideal = (np.stack([i.ravel(), j.ravel()], -1) + 0.5) * h
            snapped = np.minimum(ideal, self.size[k] - 0.5)
            chart.append(np.full(len(ideal), k))
            xy.append(ideal)
            face.append(self.members[k][self.trees[k].query(snapped)[1]])
        return np.concatenate(chart), np.concatenate(xy), np.concatenate(face), first, counts

    def parents(self, chart, xy, first, counts, h):
        """The four lattice nodes of spacing h around chart points, clamped to the chart: index (k, 4), weight."""
        n = counts[chart]
        g = np.clip(xy / h - 0.5, 0, n - 1)
        lo = np.floor(g).astype(int)
        hi = np.minimum(lo + 1, n - 1)
        f = g - lo
        index, weight = [], []
        for a, fa in ((lo[:, 0], 1 - f[:, 0]), (hi[:, 0], f[:, 0])):
            for b, fb in ((lo[:, 1], 1 - f[:, 1]), (hi[:, 1], f[:, 1])):
                index.append(first[chart] + a * n[:, 1] + b)
                weight.append(fa * fb)
        return np.stack(index, -1), np.stack(weight, -1)


class Atlas:
    """Every cascade on chart lattices: cascade 0 on the faces, cascade c on each chart's lattice of spacing 2**c,
    with hemisphere probes in the chart's frame. `merge` is one of ATLAS_MERGES, used at every hand-over."""

    def __init__(self, surface, bins=16, t0=None, merge="self_test", tau=0.5):
        volume = surface.volume
        self.surface, self.merge, self.tau = surface, merge, tau
        self.t0 = t0 if t0 is not None else math.sqrt(2 * bins / (4 * math.pi))
        self.count = vo.levels_for(volume.n, self.t0)
        charts = Charts(surface)
        self.charts = charts
        hemi = Hemisphere.of(bins)
        self.levels = []
        for c in range(self.count):
            if c == 0:
                chart, xy, face = charts.chart, charts.xy, np.arange(surface.size)
                first = counts = None
            else:
                chart, xy, face, first, counts = charts.lattice(c)
            frame = cp.asarray(surface.frame[face], cp.float32)
            origin = cp.asarray(surface.position[face], cp.float32)
            dirs = cp.einsum("bj,pjk->pbk", cp.asarray(hemi.centres(), cp.float32), frame)
            start = 0.0 if c == 0 else self.t0 * 4.0 ** (c - 1)
            end = math.inf if c == self.count - 1 else self.t0 * 4.0 ** c
            self.levels.append({"hemi": hemi, "chart": chart, "xy": xy, "first": first, "counts": counts,
                                "frame": frame, "origin": origin, "dirs": dirs, "start": start, "end": end,
                                "own": Rays.trace(volume, origin[:, None], dirs, start, end)})
            hemi = hemi.finer()
        for c in range(self.count - 1):
            level, up = self.levels[c], self.levels[c + 1]
            index, weight = charts.parents(level["chart"], level["xy"], up["first"], up["counts"], 2.0 ** (c + 1))
            level["index"], level["weight"] = cp.asarray(index), cp.asarray(weight, cp.float32)
            level["parent_pos"] = up["origin"][level["index"]]
            level["children"] = cp.asarray(level["hemi"].children())
            sub = cp.asarray(up["hemi"].centres()[level["hemi"].children()], cp.float32)
            level["sub"] = cp.einsum("bsj,pjk->pbsk", sub, level["frame"])
            if merge in BENT:
                o = level["origin"][:, None, None] + level["start"] * level["dirs"][:, :, None]
                end = level["parent_pos"][:, None] + up["start"] * level["dirs"][:, :, None]
                level["bent"] = Rays.segments(volume, cp.broadcast_to(o, end.shape), end)
        self.cost = {"records": self._records()}
        self.cost["total"] = sum(self.cost["records"])

    def merged0(self, table, sky):
        """Cascade 0's merged radiance (P, B) for the shading `table` and `sky`."""
        top = self.levels[-1]
        merged = top["own"].shade(table, sky)
        for c in reversed(range(self.count - 1)):
            level, up = self.levels[c], self.levels[c + 1]
            own_rad = level["own"].shade(table)
            P = len(own_rad)
            value = merged[level["index"][:, None, None, :], level["children"][None, :, :, None]]
            bent = test = None
            if self.merge in BENT:
                bent = (level["bent"].hit, level["bent"].shade(table))
            if self.merge == "self_test":
                test = self_test(level["own"], level["frame"], level["hemi"], level["origin"], level["parent_pos"],
                                 level["sub"], up["start"], self.tau * 2.0 ** c, own_rad)
            merged = combine(self.merge, own_rad, level["own"].hit, value, level["weight"], bent, test)
            assert merged.shape == (P, level["hemi"].size)
        return merged

    def irradiance(self, radiance, sky):
        merged = self.merged0(self.surface.shade_table(radiance), sky)
        out = np.zeros(self.surface.faces.size)
        out[self.surface.active] = (merged @ cp.asarray(self.levels[0]["hemi"].cosines(), cp.float32)).get()
        return out

    def _records(self):
        bent = self.merge in BENT
        need = None
        records = []
        for c, level in enumerate(self.levels):
            own = level["own"]
            if need is None:
                need = cp.ones(own.voxel.shape, bool)
            records.append(int(need.sum()) * (4 if bent and c < self.count - 1 else 1))
            if c == self.count - 1:
                break
            probes, bins = cp.nonzero(need if bent else need & ~own.hit)
            index, weight = level["index"][probes], level["weight"][probes]
            child = level["children"][bins]
            keep = cp.broadcast_to((weight > 0)[:, :, None], (len(probes), 4, 4))
            up_need = cp.zeros(self.levels[c + 1]["own"].voxel.shape, bool)
            up_need[cp.broadcast_to(index[:, :, None], keep.shape)[keep],
                    cp.broadcast_to(child[:, None], keep.shape)[keep]] = True
            need = up_need
        return records


def reference(surface, points=None, normals=None, rays=4096, seed=0):
    """Sparse (points, faces + 1): the share of cosine-distributed rays from each point (by default every probe) that
    lands on each face of the volume, the last column the sky; pi times it maps face radiance and sky to irradiance.
    Rays are stratified over a square of `rays` cells mapped to the hemisphere by Malley's method."""
    from scipy import sparse

    points = surface.position if points is None else points
    normals = surface.frame[:, 2] if normals is None else normals
    faces = surface.faces
    side = math.isqrt(rays)
    assert side * side == rays
    rng = np.random.default_rng(seed)
    table = cp.asarray(faces.table, cp.int32)
    cell = np.stack(np.divmod(np.arange(rays), side), -1)
    rows, cols, vals = [], [], []
    for chunk in np.array_split(np.arange(len(points)), max(1, len(points) * rays // (1 << 23))):
        u = (cell[None] + rng.random((len(chunk), rays, 2))) / side
        r, angle = np.sqrt(u[..., 0]), 2 * math.pi * u[..., 1]
        local = np.stack([r * np.cos(angle), r * np.sin(angle), np.sqrt(1 - u[..., 0])], -1)
        axis = normals[chunk]
        tangent = np.roll(np.abs(axis), 1, axis=1)
        bitangent = np.cross(axis, tangent)
        dirs = local[..., :1] * tangent[:, None] + local[..., 1:2] * bitangent[:, None] + local[..., 2:] * axis[:, None]
        origins = np.broadcast_to(points[chunk][:, None], dirs.shape)
        _, hit, _, voxel, face = vo.trace(surface.volume, origins.reshape(-1, 3), dirs.reshape(-1, 3), 0.0, math.inf)
        landed = cp.where(hit, table[cp.maximum(voxel, 0), cp.maximum(face, 0).astype(cp.int32)], faces.size)
        code = cp.repeat(cp.arange(len(chunk)), rays) * (faces.size + 1) + landed
        unique, counts = cp.unique(code, return_counts=True)
        unique, counts = unique.get(), counts.get()
        rows.append(chunk[unique // (faces.size + 1)])
        cols.append(unique % (faces.size + 1))
        vals.append(counts / rays)
    shape = (len(points), faces.size + 1)
    return sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=shape)
