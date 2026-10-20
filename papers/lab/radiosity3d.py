"""Diffuse interreflection from one radiance cascades solve in a voxel volume, with a Monte Carlo reference.

The patches are the exposed faces of solid voxels, those whose neighbouring voxel is empty or outside the volume.
Each has an emission and an albedo and is shaded from the irradiance at its collocation point, the centre of the voxel
it faces: `L = E + albedo/pi * Irr`, with `Irr` the radiance seen from there weighted by `max(0, cos)` against the
face normal, pi for unit radiance all round. A ray whose interval starts inside a solid voxel sees the mean of that
voxel's exposed faces, or of the nearest voxel's that has some.

- `Faces` indexes the patches; `Frozen` runs one solve and keeps its texels' hit records;
- `Frozen.bounce` re-shades the records with any face radiance and re-merges, with no rays traced;
- `reference` casts cosine-distributed rays from every collocation point and keeps where they land, as a sparse
  matrix from face radiance and sky to collocation irradiance.

Face `f` of a voxel is `2*axis + (normal points to +axis)`, as the tracer reports it.
"""
import math

import cupy as cp
import numpy as np
from scipy import ndimage, sparse

import volume as vo

AXES = np.eye(3, dtype=int)


def bin_cosines(params, samples=64):
    """`max(0, cos)` against each of the six face normals, integrated over each cascade 0 bin: (6, N0)."""
    m = params.m0
    u = (np.arange(samples) + 0.5) / samples
    phi = ((np.arange(2 * m)[:, None] + u[None]) * math.pi / m).reshape(2 * m, 1, samples, 1)
    z = (-1 + (np.arange(m)[:, None] + u[None]) * 2 / m).reshape(1, m, 1, samples)
    s = np.sqrt(1 - z * z)
    local = np.stack(np.broadcast_arrays(s * np.cos(phi), s * np.sin(phi), z), -1)
    world = local @ np.reshape(params.rotation, (3, 3)).T
    normals = np.repeat(AXES, 2, axis=0) * np.tile([-1, 1], 3)[:, None]
    cosines = np.maximum(0, np.einsum("fk,abcdk->fabcd", normals, world)).mean((3, 4)).reshape(6, -1)
    # Each bin holds 4*pi/N0 of the sphere; the rows are scaled to their exact total, pi.
    return cosines * math.pi / cosines.sum(1, keepdims=True)


class Faces:
    """The exposed faces of a volume's solid voxels, with each face's emission and albedo (zero to start with)."""

    def __init__(self, volume):
        n = volume.n
        self.volume = volume
        cells = np.argwhere(volume.solid)
        voxel, face, neighbour = [], [], []
        for f in range(6):
            step = AXES[f // 2] * (1 if f % 2 else -1)
            beside = cells + step
            outside = np.any((beside < 0) | (beside >= n), axis=1)
            exposed = outside.copy()
            exposed[~outside] = ~volume.solid[tuple(beside[~outside].T)]
            voxel.append(np.ravel_multi_index(cells[exposed].T, (n,) * 3))
            face.append(np.full(exposed.sum(), f))
            flat = np.full(exposed.sum(), -1)
            inside = ~outside[exposed]
            flat[inside] = np.ravel_multi_index(beside[exposed][inside].T, (n,) * 3)
            neighbour.append(flat)
        self.voxel, self.face, self.neighbour = (np.concatenate(v) for v in (voxel, face, neighbour))
        self.table = np.full((n ** 3, 6), -1)
        self.table[self.voxel, self.face] = np.arange(self.size)
        self.exposed_count = np.bincount(self.voxel, minlength=n ** 3)
        _, nearest = ndimage.distance_transform_edt(self.exposed_count.reshape((n,) * 3) == 0, return_indices=True)
        self.nearest_exposed = np.ravel_multi_index(nearest.reshape(3, -1), (n,) * 3)
        self.emission = np.zeros(self.size)
        self.albedo = np.zeros(self.size)

    @property
    def size(self):
        return len(self.voxel)

    def centre(self):
        """Centre of each face's collocation voxel, where it has one, and its normal."""
        normal = np.repeat(AXES, 2, axis=0)[self.face] * np.where(self.face % 2, 1, -1)[:, None]
        cells = np.stack(np.unravel_index(self.voxel, (self.volume.n,) * 3), -1)
        return cells + normal + 0.5, normal

    def receivers(self):
        receivers = np.flatnonzero(self.albedo > 0)
        if (self.neighbour[receivers] < 0).any():
            raise ValueError("a receiver faces out of the volume")
        return receivers


class Frozen:
    """One solve's hit records, re-shaded and re-merged by `bounce`."""

    def __init__(self, faces, params, merges):
        """`merges` names the merge at each hand-over, from cascade 0 up."""
        self.faces, self.params, self.merges = faces, params, list(merges)
        self.levels, self.cost = vo.cascades(faces.volume, params, merges=self.merges)
        self.table = cp.asarray(faces.table, cp.int32)
        self.weights = cp.asarray(bin_cosines(params), cp.float32)
        self.receivers = faces.receivers()
        self.reads = 0

    def shading(self, radiance, sky):
        """What every hit sees when the faces have `radiance` and the sky is `sky`: each texel's own radiance per
        cascade, and the table of every voxel's six faces and its inside for the rays a merge traces itself."""
        faces = self.faces
        values = cp.asarray(radiance, cp.float32)
        mean = cp.bincount(cp.asarray(faces.voxel), values, minlength=faces.table.shape[0])
        mean = (mean / cp.maximum(cp.asarray(faces.exposed_count), 1))[cp.asarray(faces.nearest_exposed)]
        shade = cp.concatenate([cp.where(self.table >= 0, values[cp.maximum(self.table, 0)], 0.0), mean[:, None]], 1)
        shade = cp.ascontiguousarray(shade.astype(cp.float32).ravel())
        own = []
        for c, level in enumerate(self.levels):
            voxel, face = level["voxel"].ravel(), level["face"].ravel()
            miss = sky if math.isinf(self.params.interval(c)[1]) else 0.0
            seen = shade[7 * cp.maximum(voxel, 0) + cp.where(face >= 0, face, 6)]
            own.append(cp.where(voxel >= 0, seen, miss).astype(cp.float32))
        return own, shade

    def irradiance(self, radiance, sky):
        """Collocation irradiance of every receiver for face `radiance` and `sky` (host arrays)."""
        faces = self.faces
        own, shade = self.shading(radiance, sky)
        merged, self.reads = vo.remerge(faces.volume, self.params, self.levels, own, shade, merges=self.merges)
        r = self.receivers
        rows = merged[0][cp.asarray(faces.neighbour[r])]
        out = np.zeros(faces.size)
        out[r] = (rows * self.weights[cp.asarray(faces.face[r])]).sum(1).get()
        return out

    def bounce(self, radiance, sky):
        """`E + albedo/pi * Irr` for face `radiance` and `sky`."""
        return self.faces.emission + self.faces.albedo / math.pi * self.irradiance(radiance, sky)


def reference(faces, rays=4096, seed=0):
    """Sparse (faces, faces + 1): the share of each receiver's cosine-distributed rays that land on each face, the
    last column the sky; `pi` times it maps face radiance and sky to collocation irradiance. Rays are stratified over
    a square of `rays` cells mapped to the hemisphere by Malley's method."""
    side = math.isqrt(rays)
    assert side * side == rays
    receivers = faces.receivers()
    centre, normal = faces.centre()
    rng = np.random.default_rng(seed)
    table = cp.asarray(faces.table, cp.int32)
    cell = np.stack(np.divmod(np.arange(rays), side), -1)
    rows, cols, vals = [], [], []
    for chunk in np.array_split(receivers, max(1, len(receivers) * rays // (1 << 23))):
        u = (cell[None] + rng.random((len(chunk), rays, 2))) / side
        r, angle = np.sqrt(u[..., 0]), 2 * math.pi * u[..., 1]
        local = np.stack([r * np.cos(angle), r * np.sin(angle), np.sqrt(1 - u[..., 0])], -1)
        axis = normal[chunk]
        tangent = np.roll(np.abs(axis), 1, axis=1)
        bitangent = np.cross(axis, tangent)
        dirs = local[..., :1] * tangent[:, None] + local[..., 1:2] * bitangent[:, None] + local[..., 2:] * axis[:, None]
        origins = np.broadcast_to(centre[chunk][:, None], dirs.shape)
        _, hit, _, voxel, face = vo.trace(faces.volume, origins.reshape(-1, 3), dirs.reshape(-1, 3), 0.0, math.inf)
        landed = cp.where(hit, table[cp.maximum(voxel, 0), cp.maximum(face, 0).astype(cp.int32)], faces.size)
        code = cp.repeat(cp.arange(len(chunk)), rays) * (faces.size + 1) + landed
        unique, counts = cp.unique(code, return_counts=True)
        unique, counts = unique.get(), counts.get()
        rows.append(chunk[unique // (faces.size + 1)])
        cols.append(unique % (faces.size + 1))
        vals.append(counts / rays)
    shape = (faces.size, faces.size + 1)
    return sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=shape)
