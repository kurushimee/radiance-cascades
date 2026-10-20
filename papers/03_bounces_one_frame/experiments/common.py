"""Shared setup of the paper's experiments: scenes, parameters, frozen solves, exact solutions and metrics."""
import math
import sys
from pathlib import Path

import numpy as np
from scipy import linalg, sparse

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
sys.path.insert(0, str(PAPER.parent / "lab"))

import flatland as fl  # noqa: E402
import radiosity as rd  # noqa: E402
import radiosity3d as rd3  # noqa: E402
import volume as vo  # noqa: E402
from report import WIDTH, Outputs, legend_below  # noqa: E402,F401

cached, save = Outputs(PAPER).cached, Outputs(PAPER).save
CACHE = PAPER / "build" / "cache"
ALBEDOS = (0.3, 0.5, 0.7, 0.9)
MERGES = ("vanilla", "bilinear_fix")


# Flatland: walls on a 4-unit lattice inside the window [0, 128]^2. Collocation points then sit on cascade 0 probes,
# and no probe of a solve whose cascade 0 spacing is 1, 2 or 4 lies on a wall it could start a ray on. Each builder
# gives receiving sides albedo 1, scaled by the experiment.

LO, HI = np.zeros(2), np.full(2, 128.0)
DIAGONAL = math.hypot(128, 128)
# Moving a scene by multiples of 4 keeps it on the lattice and varies the alignment of every cascade above 1.
OFFSETS = 4.0 * np.random.default_rng(1).integers(0, 8, (6, 2))


def _box(walls, x0, y0, x1, y1):
    """A closed outline whose inner sides receive: counter-clockwise, so the left side faces in."""
    for p, q in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        walls.wall(p, q, albedo=(1.0, 0.0))
    return walls


def room():
    """A closed room lit by a hanging lamp, with a free-standing wall and a shelf."""
    walls = _box(rd.Walls.empty(), 0, 0, 128, 128)
    walls.wall((52, 112), (76, 112), emission=1.0)
    walls.wall((36, 0), (36, 44), albedo=1.0)
    return walls.wall((84, 64), (112, 64), albedo=1.0)


def two_rooms():
    """Two rooms joined by an opening above a partition, the lamp in one of them."""
    walls = _box(rd.Walls.empty(), 0, 0, 128, 128)
    walls.wall((64, 0), (64, 96), albedo=1.0)
    return walls.wall((20, 104), (44, 104), emission=1.0)


def canyon():
    """A courtyard open to a uniform sky, half roofed, with a free-standing wall."""
    walls = rd.Walls.empty(sky=1.0)
    walls.wall((0, 0), (128, 0), albedo=(1.0, 0.0))
    walls.wall((128, 0), (128, 96), albedo=(1.0, 0.0))
    walls.wall((0, 96), (0, 0), albedo=(1.0, 0.0))
    walls.wall((0, 96), (48, 96), albedo=1.0)
    return walls.wall((84, 40), (84, 72), albedo=1.0)


SCENES = {"room": room, "two_rooms": two_rooms, "canyon": canyon}
CLOSED = ("room", "two_rooms")


def params(ds0=1.0, t0_factor=1.0, overlap=0.0, n0=32):
    """32 directions branching by 2, intervals by 4, cascade 0 at `t0_factor` times the equal-error interval."""
    t0 = n0 * ds0 / (2 * math.pi) * t0_factor
    levels = max(2, math.ceil(math.log(DIAGONAL / t0) / math.log(4)) + 1)
    return fl.Params(ds0=ds0, n0=n0, t0=t0, levels=levels, overlap=overlap)


class Flat:
    """A flatland scene with its patches, receivers and exact irradiance matrix, which no offset changes."""

    def __init__(self, name):
        self.name = name
        self.walls = SCENES[name]()
        self.patches = rd.patches(self.walls)
        self.reflects = self.patches.albedo.copy()
        self.receivers = self.reflects > 0
        self.inside = self.receivers | (self.patches.emission > 0)
        self.sky = self.walls.scene.sky
        self.exact = self._reference()

    def _reference(self):
        path = CACHE / f"{self.name}_reference.npy"
        if not path.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            np.save(path, rd.reference(self.walls, self.patches))
        return np.load(path)

    def estimate(self, p, merge, offset=(0.0, 0.0), lift=None):
        """The frozen solve's irradiance matrix with the scene moved by `offset`; collocation points `lift` off
        the walls (half a cascade 0 spacing by default)."""
        offset = np.asarray(offset, float)
        lift = p.ds0 / 2 if lift is None else lift
        walls = self.walls.shifted(offset)
        frozen = rd.freeze(walls, rd.patches(walls, lift=lift), p, LO + offset, HI + offset, merge)
        return rd.operator(frozen), frozen.rays

    def bounce_matrix(self, irradiance, albedo):
        self.patches.albedo = albedo * self.reflects
        return rd.bounce_matrix(self.patches, irradiance)

    def deficit(self, irradiance):
        """Each receiver's share of irradiance drawn from outside the closed region, under unit radiance inside."""
        return 1 - irradiance[self.receivers][:, :-1][:, self.inside].sum(1) / 2


def relative_rmse(estimate, exact, where):
    return float(np.sqrt(((estimate[where] - exact[where]) ** 2).mean()) / exact[where].mean())


def bias(estimate, exact, where):
    return float(estimate[where].mean() / exact[where].mean() - 1)


def perron(K):
    """Spectral radius of the bounce matrix's linear part, with its left and right Perron vectors."""
    values, left, right = linalg.eig(K[:, :-1], left=True, right=True)
    top = np.argmax(np.abs(values))
    return float(values[top].real), np.abs(left[:, top].real), np.abs(right[:, top].real)


# 3D: a 32^3 volume, one solve on the paper's 3D grid: 32 directions on an equal-area map turned against the axes,
# directions and intervals by 4, cascade 0 at the equal-error interval.

N = 32
T_EQ = math.sqrt(32 / (4 * math.pi))
ROTATION = vo.generic_rotation()
CHOICES = {
    "vanilla": ("vanilla",) * 3,
    "self test": ("self_test",) * 3,
    "few steps": ("depth_self_test", "depth_self_test", "sphere_fix"),
    "trilinear fix": ("trilinear_fix",) * 3,
}


def params3d(n0=32):
    t0 = math.sqrt(n0 / (4 * math.pi))
    return vo.Params(n0=n0, t0=t0, levels=vo.levels_for(N, t0), rotation=ROTATION)


def _shell(volume, thickness):
    for axis in range(3):
        for side in (0, N - thickness):
            lo, hi = np.zeros(3, int), np.full(3, N)
            lo[axis], hi[axis] = side, side + thickness
            volume.box(lo, hi)


def _ceiling_light(faces, x0, x1, y0, y1, z):
    """The downward faces of the ceiling voxels at height `z` over [x0, x1) x [y0, y1)."""
    centre, _ = faces.centre()
    x, y = centre[:, 0], centre[:, 1]
    return (faces.face == 4) & (centre[:, 2] == z - 0.5) & (x > x0) & (x < x1) & (y > y0) & (y < y1)


def room3d(thickness=1):
    """A closed room with walls `thickness` voxels thick, a ceiling light, a free-standing panel and a pillar."""
    volume = vo.Volume.empty(N)
    _shell(volume, thickness)
    t = thickness
    volume.box((10, t, t), (10 + t, 14, 12))
    volume.box((20, 20, t), (22, 22, 20))
    faces = rd3.Faces(volume)
    return volume, faces, _ceiling_light(faces, 11, 21, 11, 21, N - t)


def two_rooms3d():
    """Two rooms joined by a door in a one-voxel partition, the light in one of them."""
    volume = vo.Volume.empty(N)
    _shell(volume, 1)
    volume.box((16, 1, 1), (17, N - 1, N - 1))
    volume.solid[16, 12:20, 1:14] = False
    faces = rd3.Faces(volume)
    return volume, faces, _ceiling_light(faces, 3, 13, 11, 21, N - 1)


def courtyard3d():
    """A floor between two walls, open to a uniform sky above and at both ends, with a free-standing panel."""
    volume = vo.Volume.empty(N, sky=1.0)
    volume.box((0, 0, 0), (N, N, 1))
    volume.box((0, 0, 1), (1, N, 24))
    volume.box((N - 1, 0, 1), (N, N, 24))
    volume.box((12, 6, 1), (20, 7, 14))
    faces = rd3.Faces(volume)
    return volume, faces, np.zeros(faces.size, bool)


SCENES3D = {"room": room3d, "thick room": lambda: room3d(2), "two rooms": two_rooms3d, "courtyard": courtyard3d}


class Vox:
    """A 3D scene with its faces, receivers and Monte Carlo collocation matrices for two seeds."""

    RAYS = 1 << 14

    def __init__(self, name):
        self.name = name
        self.volume, self.faces, light = SCENES3D[name]()
        self.faces.emission[light] = 1.0
        self.reflects = ((self.faces.neighbour >= 0) & ~light).astype(float)
        self.faces.albedo = self.reflects.copy()
        self.receivers = self.reflects > 0
        self.inside = self.receivers | light
        self.sky = self.volume.sky
        self.exact = [self._reference(seed) for seed in (0, 1)]

    def _reference(self, seed):
        path = CACHE / f"{self.name.replace(' ', '_')}_3d_reference_{seed}.npz"
        if not path.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            sparse.save_npz(path, rd3.reference(self.faces, self.RAYS, seed))
        return sparse.load_npz(path)

    def converged(self, share, albedo):
        """Exact solution for the collocation shares `share` at uniform `albedo`, solved over the receivers."""
        faces = self.faces
        r = np.flatnonzero(self.receivers)
        rest = np.flatnonzero(~self.receivers)
        rows = share[r].toarray()
        system = np.eye(len(r)) - albedo * rows[:, r]
        rhs = faces.emission[r] + albedo * (rows[:, rest] @ faces.emission[rest] + rows[:, -1] * self.sky)
        out = faces.emission.copy()
        out[r] = np.linalg.solve(system, rhs)
        return out

    def first_bounce(self, share, albedo):
        return self.faces.emission + albedo * self.reflects * (share @ np.append(self.faces.emission, self.sky))

    def frozen(self, choice, n0=32):
        return rd3.Frozen(self.faces, params3d(n0), CHOICES[choice])

    def passes(self, frozen, albedo):
        """The bounce and linear maps of the frozen solve at uniform `albedo`."""
        self.faces.albedo = albedo * self.reflects
        bounce = lambda radiance: frozen.bounce(radiance, self.sky)  # noqa: E731
        linear = lambda radiance: self.faces.albedo / math.pi * frozen.irradiance(radiance, 0.0)  # noqa: E731
        return bounce, linear
