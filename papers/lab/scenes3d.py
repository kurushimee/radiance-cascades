"""Voxel test scenes in a cube of N^3 voxels, each with the points where it is evaluated and their reference fluence.

Every scene takes an integer offset that moves its contents against the probe grids; offsets below 8 voxels vary the
alignment of every cascade up to spacing 8.
"""
import math

import numpy as np

from volume import Volume, box_solid_angle, reference_fluence

N = 48


def _shell(volume, lo, hi, thickness, radiance=0.0):
    """A closed hollow box of the given wall thickness; returns the mask of its interior."""
    volume.box(lo, hi, radiance)
    inner = tuple(slice(a + thickness, b - thickness) for a, b in zip(lo, hi))
    volume.solid[inner] = False
    volume.emission[inner] = 0.0
    interior = np.zeros_like(volume.solid)
    interior[inner] = True
    return interior


def sealed(thickness, offset=(0, 0, 0)):
    """A closed dark box under a uniform sky. Inside, the exact fluence is zero; outside, it is the sky's 4*pi less
    the box's solid angle."""
    volume = Volume.empty(N, sky=1.0)
    lo, hi = np.array([14, 14, 14]) + offset, np.array([34, 34, 34]) + offset
    interior = _shell(volume, lo, hi, thickness)
    outside = np.argwhere(~volume.solid & ~interior) + 0.5
    return volume, {"inside": np.argwhere(interior) + 0.5, "outside": outside,
                    "outside_exact": 4 * math.pi - box_solid_angle(outside, lo, hi)}


def lamp(width, offset=(0, 0, 0)):
    """An emissive cube of radiance 1 in empty space, with its exact fluence at every empty voxel centre."""
    volume = Volume.empty(N)
    lo = np.array([N // 2 - width // 2] * 3) + offset
    hi = lo + width
    volume.box(lo, hi, 1.0)
    points = np.argwhere(~volume.solid) + 0.5
    return volume, {"points": points, "exact": box_solid_angle(points, lo, hi), "centre": (lo + hi) / 2}


def lamp_by_wall(offset=(0, 0, 0)):
    """A small bright lamp two voxels outside one wall of a closed dark box of wall thickness 1; the exact fluence
    inside the box is zero. `scale` is the lamp's exact fluence at the wall's outer face, for normalising leaks."""
    volume = Volume.empty(N)
    lo, hi = np.array([16, 14, 14]) + offset, np.array([36, 34, 34]) + offset
    interior = _shell(volume, lo, hi, 1)
    lamp_lo = np.array([lo[0] - 4, 23, 23]) + np.array([0, offset[1], offset[2]])
    volume.box(lamp_lo, lamp_lo + 2, 50.0)
    face = np.array([[lo[0] - 0.5, y + 0.5, z + 0.5] for y in range(lo[1], hi[1]) for z in range(lo[2], hi[2])])
    scale = 50.0 * box_solid_angle(face, lamp_lo, lamp_lo + 2).mean()
    return volume, {"inside": np.argwhere(interior) + 0.5, "scale": scale}


def room(offset=(0, 0, 0), samples=4096, r=96, seed=0):
    """A closed room with an emissive ceiling patch and two dark blocks; reference fluence by stratified rays at a
    random subset of empty voxel centres."""
    volume = Volume.empty(N)
    lo = np.array(offset)
    _shell(volume, lo, lo + 40, 2)
    volume.box(lo + [14, 14, 37], lo + [26, 26, 38], 4.0)
    volume.box(lo + [7, 8, 2], lo + [17, 18, 14], 0.0)
    volume.box(lo + [22, 20, 2], lo + [31, 29, 26], 0.0)
    interior = np.zeros_like(volume.solid)
    interior[tuple(slice(a + 2, a + 38) for a in lo)] = True
    candidates = np.argwhere(interior & ~volume.solid)
    rng = np.random.default_rng(seed)
    points = candidates[rng.choice(len(candidates), samples, replace=False)] + 0.5
    return volume, {"points": points, "reference": reference_fluence(volume, points, r=r, seed=seed)}


def partition(offset=(0, 0, 0), samples=4096, r=96, seed=1):
    """A closed room split by a one-voxel wall with a doorway; a ceiling lamp on one side lights the other side only
    through the door. Reference fluence by stratified rays at a random subset of empty voxel centres."""
    volume = Volume.empty(N)
    lo = np.array(offset)
    _shell(volume, lo, lo + 40, 2)
    volume.box(lo + [20, 2, 2], lo + [21, 38, 38], 0.0)
    volume.solid[tuple(slice(a, b) for a, b in zip(lo + [20, 16, 2], lo + [21, 24, 20]))] = False
    volume.box(lo + [6, 12, 37], lo + [16, 28, 38], 4.0)
    volume.box(lo + [27, 10, 2], lo + [34, 30, 12], 0.0)
    interior = np.zeros_like(volume.solid)
    interior[tuple(slice(a + 2, a + 38) for a in lo)] = True
    candidates = np.argwhere(interior & ~volume.solid)
    rng = np.random.default_rng(seed)
    points = candidates[rng.choice(len(candidates), samples, replace=False)] + 0.5
    return volume, {"points": points, "reference": reference_fluence(volume, points, r=r, seed=seed)}


def values_at(fluence, points):
    """The solver's fluence at voxel-centre points."""
    return fluence[tuple(np.floor(points).astype(int).T)]
