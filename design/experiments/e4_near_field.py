"""E4: the near field below the texel, at four points per face a quarter texel off its centre in each tangent axis.

The radiance is the exact reflected light at albedo 0.9 (the light's emission removed), with the sky; the reference is
the Monte Carlo irradiance at each point. The estimates:

- the face's texel, or the texels of its chart bilinearly at the point, as an atlas lookup gives;
- a cascade -1 probe at the point that traces cascade 0's interval itself and merges into world cascade 1 as cascade 0
  does, bent rays included;
- a cascade -1 probe that traces cascade 0's interval, or half of it, and where its ray misses reads its face's merged
  cascade 0 in the same bin, which needs no rays beyond the near interval;
- the chart's bilinear value scaled by the point's unoccluded cosine share over cascade 0's interval, or half of it,
  over the share its face's own rays saw, capped at one: a contact term that adds shadow the texel missed.

Errors are over all points and over the points of contact faces, those with a solid voxel beside the voxel in front.
"""
import math
from types import SimpleNamespace

import cupy as cp
import numpy as np
from scipy import sparse

import common as cm
import surface as sf
from e3_cascade0 import build

SCENES = ("room", "thick room", "courtyard", "columns")
OFFSETS = [(a, b) for a in (-0.25, 0.25) for b in (-0.25, 0.25)]
BIAS, ALBEDO, BINS = 0.02, 0.9, 16
T0 = math.sqrt(2 * BINS / (4 * math.pi))


def points_of(surface):
    """Four points per probe face: positions, the face each lies on, and its frame."""
    tangent, bitangent, normal = surface.frame[:, 0], surface.frame[:, 1], surface.frame[:, 2]
    position = np.concatenate([surface.centre + a * tangent + b * bitangent + BIAS * normal for a, b in OFFSETS])
    face = np.tile(np.arange(surface.size), len(OFFSETS))
    return position, face, surface.frame[face]


def contact(surface):
    """Probe faces with a solid voxel beside the voxel in front of them."""
    solid, n = surface.volume.solid, surface.volume.n
    front = surface.cell + surface.frame[:, 2].astype(int)
    out = np.zeros(surface.size, bool)
    for row in (0, 1):
        for sign in (-1, 1):
            beside = front + sign * surface.frame[:, row].astype(int)
            inside = np.all((beside >= 0) & (beside < n), axis=1)
            out[inside] |= solid[tuple(beside[inside].T)]
    return out


def bilinear(surface, values, position, face):
    """Per-face `values` read bilinearly at each point among the faces of its chart, missing faces left out."""
    charts = sf.Charts(surface)
    grids = []
    for k in range(charts.count):
        grid = np.full(charts.size[k], -1)
        cells = np.floor(charts.xy[charts.members[k]]).astype(int)
        grid[cells[:, 0], cells[:, 1]] = charts.members[k]
        grids.append(grid)
    axis = surface.code[face] // 2
    rows = np.arange(len(face))
    offset = position - surface.centre[face]
    local = charts.xy[face] + np.stack([offset[rows, (axis + 1) % 3], offset[rows, (axis + 2) % 3]], -1)
    g = local - 0.5
    lo = np.floor(g).astype(int)
    frac = g - lo
    total, weight = np.zeros(len(face)), np.zeros(len(face))
    for du in (0, 1):
        for dv in (0, 1):
            w = np.where(du, frac[:, 0], 1 - frac[:, 0]) * np.where(dv, frac[:, 1], 1 - frac[:, 1])
            for i in rows:
                grid = grids[charts.chart[face[i]]]
                u, v = lo[i, 0] + du, lo[i, 1] + dv
                if 0 <= u < grid.shape[0] and 0 <= v < grid.shape[1] and grid[u, v] >= 0:
                    total[i] += w[i] * values[grid[u, v]]
                    weight[i] += w[i]
    return total / weight


def reference(scene, position, normal):
    path = cm.CACHE / f"{scene.name.replace(' ', '_')}_points.npz"
    if not path.exists():
        cm.CACHE.mkdir(parents=True, exist_ok=True)
        shares = [sf.reference(scene.surface, position, normal, rays=1 << 14, seed=seed) for seed in (0, 1)]
        sparse.save_npz(path, (shares[0] + shares[1]) / 2)
    return sparse.load_npz(path)


def compute():
    results = {}
    for name in SCENES:
        scene = cm.Scene(name)
        surface = scene.surface
        position, face, frame = points_of(surface)
        touching = contact(surface)[face]
        radiance = scene.converged(ALBEDO) - scene.emission
        exact = math.pi * (reference(scene, position, frame[:, 2]) @ np.append(radiance, scene.sky))

        texels = build("world", surface, BINS, T0)
        table = surface.shade_table(radiance)
        face_irradiance = texels.irradiance(radiance, scene.sky)[surface.active]
        cosines = cp.asarray(texels.hemi.cosines(), cp.float32)
        estimates = {"texel": face_irradiance[face], "texel bilinear": bilinear(surface, face_irradiance, position, face)}

        points = SimpleNamespace(volume=scene.volume, frame=frame, position=position)
        own = build("world", points, BINS, T0)
        estimates["cascade -1 to world"] = (own.merged0(table, scene.sky) @ cosines).get()

        dirs = cp.einsum("bj,pjk->pbk", cp.asarray(texels.hemi.centres(), cp.float32), cp.asarray(frame, cp.float32))
        beyond = texels.merged0(table, scene.sky)[cp.asarray(face)]
        for label, reach in (("cascade -1, then texel", T0), ("cascade -1 half, then texel", T0 / 2)):
            near = sf.Rays.trace(scene.volume, cp.asarray(position, cp.float32)[:, None], dirs, 0.0, reach)
            estimates[label] = (cp.where(near.hit, near.shade(table), beyond) @ cosines).get()
        for label, reach in (("texel times contact", T0), ("texel times contact half", T0 / 2)):
            near = sf.Rays.trace(scene.volume, cp.asarray(position, cp.float32)[:, None], dirs, 0.0, reach)
            own = (texels.own.hit & (texels.own.t < reach))[cp.asarray(face)]
            ratio = (~near.hit).astype(cp.float32) @ cosines / cp.maximum((~own).astype(cp.float32) @ cosines, 1e-6)
            estimates[label] = estimates["texel bilinear"] * cp.minimum(ratio, 1.0).get()

        results[name] = {"points": len(face), "contact": int(touching.sum())}
        for key, value in estimates.items():
            results[name][key] = {"all": cm.relative(value, exact), "contact": cm.relative(value[touching],
                                                                                             exact[touching])}
            print(name, key, results[name][key], flush=True)
    return results


def main():
    results = cm.cached("e4_near_field", compute)
    for name, rows in results.items():
        print(f"\n{name}: {rows['points']} points, {rows['contact']} on contact faces")
        for key, r in rows.items():
            if isinstance(r, dict):
                print(f"  {key:30s} all {r['all'][0]:.4f} ({r['all'][1]:+.4f})"
                      f"  contact {r['contact'][0]:.4f} ({r['contact'][1]:+.4f})")


if __name__ == "__main__":
    main()
