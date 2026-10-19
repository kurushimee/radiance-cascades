"""Flatland test scenes on the window [0, 128]^2.

Coordinates avoid dyadic values, so no probe centre `(i + 0.5) * 2**n` falls on a segment.
"""
import numpy as np

from flatland import Scene

WINDOW = ((0.0, 0.0), (128.0, 128.0))


def lamp(length=2.0, radiance=1.0):
    """A small two-sided emitter in empty space."""
    c = np.array([64.3, 64.1])
    half = np.array([0.0, length / 2])
    return Scene.empty().wall(c - half, c + half, radiance)


def wall():
    """A long emitter and a thin occluding wall: penumbras, a shadow, and leaks behind the wall."""
    return Scene.empty().wall((20.3, 10.3), (20.3, 117.7), 1.0).wall((60.3, 34.3), (60.3, 93.7), 0.0)


def penumbra():
    """A small light and occluders at several distances from it, giving penumbras of several widths."""
    scene = Scene.empty().wall((12.3, 60.1), (12.3, 68.1), 4.0)
    for x, y0, y1 in ((24.3, 70.3, 90.3), (44.3, 36.3, 56.3), (72.3, 74.3, 100.3), (100.3, 20.3, 50.3)):
        scene.box(x, y0, x + 1.4, y1)
    return scene


def room():
    """A closed room lit by a ceiling lamp, with two blocks inside."""
    scene = Scene.empty()
    for x0, y0, x1, y1 in ((0, 0, 8.3, 128), (119.7, 0, 128, 128), (8.3, 0, 119.7, 8.3), (8.3, 119.7, 119.7, 128)):
        scene.box(x0, y0, x1, y1)
    scene.wall((48.3, 116.1), (80.3, 116.1), 2.0)
    scene.box(30.3, 8.3, 50.7, 40.7)
    scene.box(78.1, 52.3, 86.9, 90.1)
    return scene


def scatter(seed=7):
    """Small lights and occluders in separate lattice cells."""
    rng = np.random.default_rng(seed)
    scene = Scene.empty()
    for cx in range(5):
        for cy in range(5):
            x0, y0 = 6.3 + 24 * cx + rng.uniform(0, 8), 6.3 + 24 * cy + rng.uniform(0, 8)
            kind = rng.integers(3)
            if kind == 0:
                angle = rng.uniform(0, np.pi)
                length = rng.uniform(1, 3)
                scene.wall((x0, y0), (x0 + length * np.cos(angle), y0 + length * np.sin(angle)), rng.uniform(1, 3))
            elif kind == 1:
                scene.box(x0, y0, x0 + rng.uniform(1, 9), y0 + rng.uniform(1, 9))
    scene.check_no_crossings()
    return scene


def skyline():
    """An open scene under a uniform sky: ground and blocks of several heights."""
    scene = Scene.empty(sky=1.0)
    scene.box(-200.3, -40.3, 328.3, 10.3)
    for x, w, h in ((20.3, 9.4, 40.1), (40.7, 4.2, 70.3), (62.9, 12.6, 25.3), (86.1, 3.3, 55.9), (104.5, 8.8, 35.7)):
        scene.box(x, 10.3, x + w, 10.3 + h)
    return scene


SCENES = {"lamp": lamp, "wall": wall, "penumbra": penumbra, "room": room, "scatter": scatter, "skyline": skyline}


def pixels(scene, window=WINDOW, step=1.0):
    """Evaluation points at pixel centres of the window, outside every solid."""
    (x0, y0), (x1, y1) = window
    xs = np.arange(x0 + step / 2, x1, step)
    ys = np.arange(y0 + step / 2, y1, step)
    points = np.stack(np.meshgrid(xs, ys), -1).reshape(-1, 2)
    return points[~scene.inside_solid(points)]
