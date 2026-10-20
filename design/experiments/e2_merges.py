"""E2: merges per hand-over with world upper cascades and front parents.

The surface hand-over (cascade 0 to 1) and the world hand-overs above it are varied independently, and cascade 0
reads each sub-direction from one bin of a cascade 1 probe or from four bilinearly. Metrics are those of E1."""
import common as cm
import surface as sf
from e1_layout import measure

SURFACE = ("self_test", "trilinear_fix")
WORLD = {"self test": ("self_test", "self_test"), "depth self test": ("depth_self_test", "depth_self_test"),
         "few steps": ("depth_self_test", "sphere_fix"), "kuhn fix": ("kuhn_fix", "kuhn_fix"),
         "trilinear fix": ("trilinear_fix", "trilinear_fix"), "kuhn then sphere": ("kuhn_fix", "sphere_fix"),
         "sphere fix": ("sphere_fix", "sphere_fix")}


def compute():
    results = {}
    for name in cm.SCENES:
        scene = cm.Scene(name)
        results[name] = {}
        for surface_merge in SURFACE:
            for world, merges in WORLD.items():
                for nearest in (False, True):
                    solver = sf.World(scene.surface, surface_merge=surface_merge, world_merge=merges, front=True,
                                      nearest=nearest)
                    key = f"{surface_merge} | {world} | {'nearest' if nearest else 'bilinear'}"
                    results[name][key] = measure(scene, solver)
                    print(name, key, results[name][key], flush=True)
    return results


def main():
    cm.print_table(cm.cached("e2_merges", compute), 48)


if __name__ == "__main__":
    main()
