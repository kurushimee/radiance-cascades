"""Shared setup of the design's lab experiments: scenes, the Monte Carlo reference at the probes, solves and metrics.

Scenes are voxel volumes of 32^3 with a ceiling light of radiance 1 or a sky of radiance 1. Every exposed face whose
front voxel lies inside the volume carries a cascade 0 probe; receivers are those faces less the light.
"""
import functools
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
DESIGN = HERE.parent
PAPERS = DESIGN.parent / "papers"
sys.path.insert(0, str(PAPERS / "lab"))
sys.path.insert(0, str(HERE))

import radiosity as rd  # noqa: E402
import radiosity3d as rd3  # noqa: E402
import surface as sf  # noqa: E402
import volume as vo  # noqa: E402
from report import Outputs  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bounces = _load(PAPERS / "03_bounces_one_frame" / "experiments" / "common.py", "bounces")
cached = Outputs(DESIGN).cached
CACHE = DESIGN / "build" / "cache"
N = bounces.N


def sealed_box():
    """A closed box with walls one voxel thick on a floor under the sky: any light inside it leaked in."""
    volume = vo.Volume.empty(N, sky=1.0)
    volume.box((0, 0, 0), (N, N, 1))
    volume.box((8, 8, 1), (24, 24, 17))
    volume.solid[9:23, 9:23, 1:16] = False
    faces = rd3.Faces(volume)
    return volume, faces, np.zeros(faces.size, bool)


def columns():
    """A closed hall lit from the ceiling, with a grid of pillars one voxel thick."""
    volume = vo.Volume.empty(N)
    bounces._shell(volume, 1)
    for x in range(6, N - 5, 5):
        for y in range(6, N - 5, 5):
            volume.box((x, y, 1), (x + 1, y + 1, N - 1))
    faces = rd3.Faces(volume)
    return volume, faces, bounces._ceiling_light(faces, 11, 21, 11, 21, N - 1)


SCENES = {**bounces.SCENES3D, "sealed box": sealed_box, "columns": columns}


class Scene:
    """A scene's surface with its emission, receivers, and Monte Carlo shares at the probes for two seeds."""

    RAYS = 1 << 14

    def __init__(self, name):
        self.name = name
        self.volume, faces, light = SCENES[name]()
        self.surface = sf.Surface(self.volume)
        assert self.surface.faces.size == faces.size
        self.size = faces.size
        self.sky = self.volume.sky
        self.emission = light.astype(float)
        self.reflects = np.zeros(self.size)
        self.reflects[self.surface.active] = 1.0
        self.reflects[light] = 0.0
        self.receivers = self.reflects[self.surface.active] > 0  # over probes
        self.shares = [self._reference(seed) for seed in (0, 1)]
        self.share = (self.shares[0] + self.shares[1]) / 2

    def _reference(self, seed):
        path = CACHE / f"{self.name.replace(' ', '_')}_surface_{seed}.npz"
        if not path.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            sparse.save_npz(path, sf.reference(self.surface, rays=self.RAYS, seed=seed))
        return sparse.load_npz(path)

    def interior(self):
        """Probes inside the sealed box, by their position."""
        p = self.surface.position
        return np.all((p > (9, 9, 1)) & (p < (23, 23, 16)), axis=1)

    def first_bounce(self, share=None):
        """Exact irradiance at every probe from the emission and sky alone."""
        share = self.share if share is None else share
        return math.pi * (share @ np.append(self.emission, self.sky))

    @functools.cache
    def converged(self, albedo):
        """Exact face radiance of the receivers at uniform `albedo`, with all bounces."""
        share = self.share
        faces = self.surface.active[self.receivers]
        rest = np.setdiff1d(np.arange(self.size), faces)
        rows = share[np.flatnonzero(self.receivers)]
        system = np.eye(len(faces)) - albedo * rows[:, faces].toarray()
        rhs = self.emission[faces] + albedo * (rows[:, rest] @ self.emission[rest]
                                               + rows[:, -1].toarray().ravel() * self.sky)
        out = self.emission.copy()
        out[faces] = np.linalg.solve(system, rhs)
        return out

    def as_faces(self, values):
        """Per-probe values spread over all faces, zero where no probe."""
        out = np.zeros(self.size)
        out[self.surface.active] = values
        return out

    def passes(self, solver, albedo, count, exact_direct=False):
        """Face radiance after each of `count` GMRES passes of `solver` at uniform `albedo`. With `exact_direct`, the
        light's direct irradiance is exact and the solver gathers only reflected light and the sky."""
        rho = albedo * self.reflects / math.pi
        linear = lambda radiance: rho * solver.irradiance(radiance, 0.0)  # noqa: E731
        if not exact_direct:
            bounce = lambda radiance: self.emission + rho * solver.irradiance(radiance, self.sky)  # noqa: E731
            return rd.gmres(bounce, linear, self.emission, count)
        direct = self.as_faces(math.pi * (self.share @ np.append(self.emission, 0.0)))
        bounce = lambda reflected: rho * (direct + solver.irradiance(reflected, self.sky))  # noqa: E731
        return [self.emission + r for r in rd.gmres(bounce, linear, np.zeros(self.size), count)]


def relative(estimate, exact):
    """Relative RMSE and relative bias of `estimate` against `exact`, both normalized by the mean of `exact`."""
    scale = np.mean(exact)
    return float(np.sqrt(np.mean((estimate - exact) ** 2)) / scale), float(np.mean(estimate - exact) / scale)



def print_table(results, width):
    """Prints each scene's rows of an E1-style result: errors as relative RMSE, records in millions."""
    for name, rows in results.items():
        print(f"\n{name}")
        for key, r in rows.items():
            if not isinstance(r, dict):
                continue
            cells = [f"{k} {r[k][0]:.4f}" + (f" ({r[k][1]:+.4f})" if k == "first" else "")
                     for k in ("first", "second", "converged", "split") if k in r]
            cells += [f"{k} {r[k]:.4f}" for k in ("leak", "deficit") if k in r]
            print(f"  {key:{width}s} " + " ".join(cells) + f" records {sum(r['records']) / 1e6:.2f}M")
