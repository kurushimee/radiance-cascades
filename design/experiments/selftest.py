"""Checks of the surface-probe simulator: bin maps, parent weights, and the furnace, where faces and sky of radiance 1
give irradiance pi at every probe for every layout and merge."""
import math

import cupy as cp
import numpy as np

import common as cm
import surface as sf

hemi = sf.Hemisphere.of(16)
assert math.isclose(hemi.cosines().sum(), math.pi)
assert sorted(hemi.children().ravel()) == list(range(hemi.finer().size))
assert (hemi.bin_of(cp.asarray(hemi.centres())).get() == np.arange(hemi.size)).all()

rng = np.random.default_rng(0)
points = cp.asarray(rng.uniform(4, 28, (1000, 3)))
for kuhn in (False, True):
    _, position, weight = sf.corners(points, np.zeros(3, int), np.full(3, 16), 2.0, kuhn)
    assert cp.allclose(weight.sum(1), 1, atol=1e-6)
    assert cp.allclose((position * weight[..., None]).sum(1), points, atol=1e-4)

for name in ("room", "courtyard", "columns"):
    volume, _, _ = cm.SCENES[name]()
    surface = sf.Surface(volume)
    ones = np.ones(surface.faces.size)
    solvers = [sf.World(surface, surface_merge=merge) for merge in sf.MERGES]
    solvers += [sf.World(surface, surface_merge=merge, front=True) for merge in sf.MERGES]
    solvers += [sf.Atlas(surface, merge=merge) for merge in sf.ATLAS_MERGES]
    for solver in solvers:
        irradiance = solver.irradiance(ones, 1.0)[surface.active]
        assert np.allclose(irradiance, math.pi, rtol=1e-4), (name, type(solver).__name__, irradiance.min())
    share = sf.reference(surface, rays=256)
    assert np.allclose(share.sum(1), 1)
    print(name, "faces", surface.size, "records", [s.cost["total"] for s in solvers])
print("selftest passed")
