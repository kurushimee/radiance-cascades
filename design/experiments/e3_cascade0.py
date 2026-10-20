"""E3: cascade 0 directions and interval, for world upper cascades and chart lattices.

Cascade 0 has 16, 36 or 64 hemisphere bins and an interval of 0.5, 1 or 2 times the equal-error length
sqrt(2 * bins / 4 pi); every cascade above scales from it. World solves seal the surface hand-over with the trilinear fix
on front parents and the world hand-overs with the merges E2 chose; lattices use the bilinear fix. Metrics are those of
E1."""
import math

import common as cm
import surface as sf
from e1_layout import measure

BINS = (16, 36, 64)
SCALES = (0.5, 1.0, 2.0)
WORLD = "sphere_fix"


def world_merges(levels):
    """The merge at every world hand-over."""
    return [WORLD] * (levels - 2)


def build(layout, surface, bins, t0):
    if layout == "atlas":
        return sf.Atlas(surface, bins=bins, t0=t0, merge="bilinear_fix")
    levels = sf.vo.levels_for(surface.volume.n, t0)
    return sf.World(surface, bins=bins, t0=t0, surface_merge="trilinear_fix", world_merge=world_merges(levels),
                    front=True)


def compute():
    results = {}
    for name in cm.SCENES:
        scene = cm.Scene(name)
        results[name] = {}
        for layout in ("world", "atlas"):
            for bins in BINS:
                for scale in SCALES:
                    t0 = scale * math.sqrt(2 * bins / (4 * math.pi))
                    key = f"{layout} {bins} bins t0 x{scale}"
                    results[name][key] = measure(scene, build(layout, scene.surface, bins, t0))
                    print(name, key, results[name][key], flush=True)
    return results


def main():
    cm.print_table(cm.cached("e3_cascade0", compute), 26)


if __name__ == "__main__":
    main()
