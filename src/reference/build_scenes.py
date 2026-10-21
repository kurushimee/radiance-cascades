# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""Writes the evaluation's test scenes (design/evaluation.md) as Godot scenes in assets/scenes/, with the geometry of
the built ones as glTF in assets/models/. The downloaded ones instance the models that fetch_scenes.py puts in
assets/downloaded/, with this project's lights, sky and animation. Bistro's sky is a copy of its HDR panorama
without the sun's disk, written beside it, whose light goes to a DirectionalLight3D instead.

The rooms are built on the lab's voxel grid (design/experiments/common.py and papers/03_bounces_one_frame/
experiments/) at 0.25 m per voxel, with walls of albedo 0.7 and floors of 0.45 where the lab had 0.9 throughout. The
Cornell box has the published Cornell geometry with Mitsuba 3's RGB reflectances and light, so that Mitsuba can build
the same box from the same numbers. Each scene has a camera per pose, a static lighting setup and an `animated`
animation.

    uv run src/reference/build_scenes.py

New models then need an import (`godot --headless --path . --import`) and src/editor/import_options.gd.
"""
import base64
import colorsys
import json
import math
import random
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
VOXEL = 0.25
N = 32
WALL = 0.7
FLOOR = 0.45
PANEL = 5.0  # radiance of the rooms' ceiling panels
SUN = (35.0, 30.0)  # elevation and azimuth, degrees
SPONZA_SUN = (55.9, -100.8)  # Intel Sponza's own sun, which it exports with zero intensity
SUN_DIAMETER = 0.5  # degrees, which sizes the penumbrae of the sun's shadows
# A panorama's sun disk is every pixel within SUN_CAP degrees of the brightest one that is brighter than SUN_CONTRAST
# times the cap's rim, the outer SUN_RIM degrees of the cap.
SUN_CAP = 5.0
SUN_RIM = 0.2
SUN_CONTRAST = 2.0
LUMINANCE = (0.2126, 0.7152, 0.0722)
# Godot's defaults of 0.1 and 2.0 lift the sun's shadows off the bases of thin objects.
SUN_SHADOW_BIAS = 0.03
SUN_NORMAL_BIAS = 0.5
DOWNLOADED = "res://assets/downloaded"
SHADERS = {"one_sided_shader": "shd_gi", "two_sided_shader": "shd_gi_double_sided",
           "alpha_tested_shader": "shd_gi_alpha_tested", "two_sided_alpha_tested_shader": "shd_gi_double_sided_alpha_tested"}
# Inverse-square falloff, with a range wide enough that its cutoff stays dark.
LAMP_RANGE = 20.0
SUN_PERIOD = 60.0
PANEL_PERIOD = 8.0
DEFAULT_SPECULAR = 0.5
LAMP_PERIOD = 4.0


@dataclass(frozen=True)
class Material:
    albedo: tuple
    emission: tuple = (0.0, 0.0, 0.0)  # linear radiance
    two_sided: bool = False
    specular: float = DEFAULT_SPECULAR  # Godot's metallic_specular: 0.5 is a dielectric's F0 of 0.04, 0 is matte


@dataclass(frozen=True)
class Quad:
    """Four corners counter-clockwise seen from the front."""
    corners: tuple
    material: str


@dataclass(frozen=True)
class Lamp:
    """A Godot light inside a fixture. The fixture's mesh node casts no shadow, which the path tracer reads as visible
    to camera rays alone and the GI as no part of its scene, so the fixture neither blocks its light nor adds its
    emission to it. The animation switches the fixture's material through the node's surface that uses it."""
    position: tuple
    size: float  # radius of the light, metres
    fixture: str
    mesh: str
    surface: int = 0


@dataclass
class Scene:
    name: str
    quads: list
    materials: dict
    cameras: dict  # name: (eye, target), besides the cameras a downloaded model brings
    fov: float = 70.0
    models: dict = field(default_factory=dict)  # node: path of downloaded models
    sky: bool = False
    panorama: str = ""  # an HDR panorama for the sky
    sun: tuple = ()  # elevation and azimuth, degrees
    sun_color: tuple = (1.0, 1.0, 1.0)  # linear
    sun_energy: float = 1.0
    lamps: dict = field(default_factory=dict)
    panel: str = ""  # the emissive material whose colour the animation changes
    hidden: tuple = ()  # lights inside a model that this project's lights replace
    exposure: float = 1.0  # of the displayed frame, chosen by eye
    camera_exposures: dict = field(default_factory=dict)  # path of a camera below the root: its own exposure
    shadow_distance: float = 40.0  # metres that the sun's shadow maps cover, which sets their texel size

    def __post_init__(self):
        if not self.models:
            self.models = {"Model": f"res://assets/models/mdl_{self.name}.gltf"}


def grey(value):
    return (value, value, value)


WHITE = Material(grey(WALL))
GROUND = Material(grey(FLOOR))


# Geometry.

def face(axis, sign, plane, u, v, material):
    """The rectangle `u` x `v` on the plane `axis = plane`, facing `sign` along the axis."""
    b, c = (axis + 1) % 3, (axis + 2) % 3
    corners = []
    for cu, cv in ((u[0], v[0]), (u[1], v[0]), (u[1], v[1]), (u[0], v[1])):
        point = [0.0, 0.0, 0.0]
        point[axis], point[b], point[c] = plane, cu, cv
        corners.append(tuple(point))
    return Quad(tuple(corners if sign > 0 else corners[::-1]), material)


def box(lo, hi, material, bottom=True):
    """The outward faces of an axis-aligned box."""
    return [face(axis, sign, hi[axis] if sign > 0 else lo[axis],
                 (lo[(axis + 1) % 3], hi[(axis + 1) % 3]), (lo[(axis + 2) % 3], hi[(axis + 2) % 3]), material)
            for axis in range(3) for sign in (1, -1) if bottom or (axis, sign) != (1, -1)]


def oriented(corners, material, toward, inward=True):
    """A quad whose front faces the point `toward`, or away from it."""
    a, b, c = corners[:3]
    normal = cross(sub(b, a), sub(c, a))
    facing = dot(normal, sub(toward, a)) > 0
    return Quad(tuple(corners if facing == inward else corners[::-1]), material)


class Volume:
    """A voxel volume, by default the lab's cube. A face exists where a solid voxel meets an empty one inside the
    volume."""

    def __init__(self, size=(N, N, N)):
        self.size = size
        self.solid = {}
        self.paints = []

    def fill(self, lo, hi, material="white"):
        for x in range(lo[0], hi[0]):
            for y in range(lo[1], hi[1]):
                for z in range(lo[2], hi[2]):
                    self.solid[x, y, z] = material

    def carve(self, lo, hi):
        for x in range(lo[0], hi[0]):
            for y in range(lo[1], hi[1]):
                for z in range(lo[2], hi[2]):
                    self.solid.pop((x, y, z), None)

    def shell(self):
        """Walls and ceiling of WALL's albedo around a floor of FLOOR's."""
        for axis in range(3):
            for side in (0, self.size[axis] - 1):
                lo, hi = [0, 0, 0], list(self.size)
                lo[axis], hi[axis] = side, side + 1
                self.fill(lo, hi)
        self.fill((0, 0, 0), (self.size[0], 1, self.size[2]), "floor")

    def paint_ceiling(self, x, z, material):
        """Gives the ceiling's downward faces over `x` x `z` another material, as the lab's ceiling light."""
        self.paints.append((x, z, material))

    def quads(self):
        """One quad per voxel face, in metres. Merged rectangles would leave T-junctions, which rasterize with
        cracks."""
        quads = []
        for voxel, material in sorted(self.solid.items()):
            for axis in range(3):
                for sign in (1, -1):
                    front = list(voxel)
                    front[axis] += sign
                    if 0 <= front[axis] < self.size[axis] and tuple(front) not in self.solid:
                        b, c = (axis + 1) % 3, (axis + 2) % 3
                        quads.append(face(axis, sign, (voxel[axis] + (sign > 0)) * VOXEL,
                                          (voxel[b] * VOXEL, (voxel[b] + 1) * VOXEL),
                                          (voxel[c] * VOXEL, (voxel[c] + 1) * VOXEL),
                                          self._paint(axis, sign, voxel) or material))
        return quads

    def _paint(self, axis, sign, voxel):
        if (axis, sign) != (1, -1):
            return None
        for x, z, material in self.paints:
            if x[0] <= voxel[0] < x[1] and z[0] <= voxel[2] < z[1]:
                return material
        return None


def cells(axis, position, u, v, material):
    """The plane `axis = position` over the voxel ranges `u` and `v` of its other two axes, one quad per voxel face,
    so that its edges meet a volume's faces without T-junctions."""
    return [face(axis, 1, position * VOXEL, (i * VOXEL, (i + 1) * VOXEL), (j * VOXEL, (j + 1) * VOXEL), material)
            for i in range(*u) for j in range(*v)]


# Scenes. Godot's y is up; the lab's (x, y, z) with z up maps to (x, z, y).

def cornell_box():
    """The Cornell box in metres (www.graphics.cornell.edu/online/box/data.html), the ceiling cut around the light.
    The room is one grid of quads through the light's edges, so that neighbouring quads share their corners. Its data
    are diffuse reflectances, so its surfaces are matte."""
    mm = 0.001
    centre = (278 * mm, 274.4 * mm, 279.6 * mm)
    y = 548.8
    xs, zs = (0, 213, 343), (0, 227, 332, 559.2)

    def room(material, *corners):
        return oriented(tuple(tuple(c * mm for c in p) for p in corners), material, centre)

    def right(z):
        """The floor's right edge, which leans from 552.8 to 549.6 mm; the ceiling's stays at 556 mm."""
        return 552.8 + (549.6 - 552.8) * z / 559.2

    def grid(rows, material=lambda i, j: "white"):
        return [room(material(i, j), a[j], a[j + 1], b[j + 1], b[j])
                for i, (a, b) in enumerate(zip(rows, rows[1:])) for j in range(len(a) - 1)]

    def block(top, height):
        middle = tuple(sum(p[i] for p in top) / 4 * mm for i in range(3))
        quads = [oriented(tuple(tuple(c * mm for c in p) for p in top), "white", (middle[0], 0.0, middle[2]), False)]
        for a, b in zip(top, top[1:] + top[:1]):
            side = ((a[0], 0, a[2]), (b[0], 0, b[2]), (b[0], height, b[2]), (a[0], height, a[2]))
            quads.append(oriented(tuple(tuple(c * mm for c in p) for p in side), "white", middle, False))
        return quads

    back = zs[-1]
    quads = [
        *grid([[(x, 0, z) for x in (*xs, right(z))] for z in zs]),
        *grid([[(x, y, z) for x in (*xs, 556)] for z in zs], lambda i, j: "light" if i == j == 1 else "white"),
        *grid([[(x, 0, back) for x in (*xs, right(back))], [(x, y, back) for x in (*xs, 556)]]),
        *grid([[(0, 0, z) for z in zs], [(0, y, z) for z in zs]], lambda i, j: "green"),
        *grid([[(right(z), 0, z) for z in zs], [(556, y, z) for z in zs]], lambda i, j: "red"),
        *block([(130, 165, 65), (82, 165, 225), (240, 165, 272), (290, 165, 114)], 165),
        *block([(423, 330, 247), (265, 330, 296), (314, 330, 456), (472, 330, 406)], 330),
    ]
    materials = {
        "white": Material((0.885809, 0.698859, 0.666422), specular=0.0),
        "red": Material((0.570068, 0.0430135, 0.0443706), specular=0.0),
        "green": Material((0.105421, 0.37798, 0.076425), specular=0.0),
        "light": Material(grey(0.78), (18.387, 13.9873, 6.75357), specular=0.0),
    }
    camera = (0.278, 0.273, -0.8)
    return Scene("cornell_box", quads, materials, {"Front": (camera, (0.278, 0.273, 0.0))},
                 fov=math.degrees(2 * math.atan(12.5 / 35)), panel="light", exposure=3.5)


def leak_house(lit=True):
    """Two closed rooms side by side under the sky and the sun, one with walls and roof a voxel thick and one with
    single-plane, two-sided walls and ceiling, each lit by its own ceiling lamp. Unlit, both lack their lamps and
    fixtures, so that the reference is dark inside and any light there leaked in."""
    volume = Volume((64, 16, 64))
    volume.fill((0, 0, 0), (64, 1, 64), "floor")
    volume.fill((8, 1, 16), (26, 14, 34), "plaster_warm")
    volume.fill((8, 13, 16), (26, 14, 34))
    volume.carve((9, 1, 17), (25, 13, 33))
    quads = volume.quads()
    walls, ceiling = (38, 54), (17, 33)
    quads += [quad for x in walls for quad in cells(0, x, (1, 13), ceiling, "plaster_cool")]
    quads += [quad for z in ceiling for quad in cells(2, z, walls, (1, 13), "plaster_cool")]
    quads += cells(1, 13, ceiling, walls, "white_two_sided")
    materials = {"white": WHITE, "floor": GROUND, "plaster_warm": Material((0.75, 0.55, 0.42)),
                 "plaster_cool": Material((0.45, 0.6, 0.7), two_sided=True),
                 "white_two_sided": Material(grey(WALL), two_sided=True)}
    lamps = {}
    if lit:
        for name, x in (("LampThick", 4.25), ("LampPlane", 11.5)):
            quads += box((x - 0.25, 3.0, 6.0), (x + 0.25, 3.2, 6.5), "fixture_lamp")
            lamps[name] = Lamp((x, 3.1, 6.25), 0.1, "fixture_lamp", "Model/fixture_lamp")
        materials["fixture_lamp"] = Material(grey(WALL), (10.0, 9.0, 7.5))
    cameras = {"Facade": ((8.0, 1.7, 14.0), (8.0, 1.2, 6.0)), "Back": ((13.0, 0.8, 1.5), (11.0, 0.3, 4.25)),
               "InsideThick": ((2.6, 1.8, 4.6), (5.6, 0.8, 7.9)), "InsidePlane": ((9.85, 1.8, 4.6), (12.9, 0.8, 7.9))}
    name = "leak_house" if lit else "leak_house_unlit"
    return Scene(name, quads, materials, cameras, sky=True, sun=SUN, lamps=lamps, exposure=0.9)


def two_rooms():
    """The lab's two rooms joined by a door, the panel and a red wall in one, so that the other receives coloured
    light through the door alone."""
    volume = Volume()
    volume.shell()
    volume.fill((0, 1, 1), (1, N - 1, N - 1), "red")
    volume.fill((16, 1, 1), (17, N - 1, N - 1))
    volume.carve((16, 1, 12), (17, 14, 20))
    volume.paint_ceiling((3, 13), (11, 21), "light")
    materials = {"white": WHITE, "floor": GROUND, "red": Material((0.65, 0.1, 0.08)),
                 "light": Material((0.0, 0.0, 0.0), grey(PANEL))}
    cameras = {"RoomA": ((0.8, 1.7, 7.2), (4.1, 1.5, 4.0)), "RoomB": ((7.2, 1.7, 0.8), (4.1, 1.5, 4.0))}
    return Scene("two_rooms", volume.quads(), materials, cameras, panel="light", exposure=0.45,
                 camera_exposures={"RoomB": 1.8})


def pillar_hall():
    """The lab's columns: a closed hall with a grid of pillars one voxel thick, lit by a ceiling panel at one end, so
    that the pillars cast their shadows down the hall."""
    volume = Volume()
    volume.shell()
    for x in range(6, N - 5, 5):
        for z in range(6, N - 5, 5):
            volume.fill((x, 1, z), (x + 1, N - 1, z + 1))
    volume.paint_ceiling((1, N - 1), (1, 7), "light")
    materials = {"white": WHITE, "floor": GROUND, "light": Material((0.0, 0.0, 0.0), grey(PANEL))}
    cameras = {"Corner": ((0.7, 1.7, 0.7), (5.0, 1.2, 5.0)), "Aisle": ((2.25, 1.7, 0.6), (2.25, 1.2, 7.4)),
               "End": ((5.5, 1.7, 7.4), (5.5, 1.2, 0.5))}
    return Scene("pillar_hall", volume.quads(), materials, cameras, panel="light", exposure=1.0)


def small_objects():
    """Posts, cubes and stools smaller than a texel on a 40 m floor under the sky and the sun."""
    rng = random.Random(1)
    quads = [face(1, 1, 0.0, (0.0, 40.0), (0.0, 40.0), "floor")]
    for i in range(14):
        for j in range(14):
            x, z = 15.0 + 0.75 * i + rng.uniform(-0.2, 0.2), 15.0 + 0.75 * j + rng.uniform(-0.2, 0.2)
            kind = rng.choice(("post", "cube", "stool"))
            if kind == "post":
                w, h = rng.uniform(0.03, 0.06), rng.uniform(0.3, 1.0)
                quads += box((x - w / 2, 0.0, z - w / 2), (x + w / 2, h, z + w / 2), "white", bottom=False)
            elif kind == "cube":
                w = rng.uniform(0.06, 0.2)
                quads += box((x - w / 2, 0.0, z - w / 2), (x + w / 2, w, z + w / 2), "white", bottom=False)
            else:
                quads += box((x - 0.15, 0.42, z - 0.15), (x + 0.15, 0.45, z + 0.15), "white")
                for dx in (-0.13, 0.13):
                    for dz in (-0.13, 0.13):
                        quads += box((x + dx - 0.015, 0.0, z + dz - 0.015), (x + dx + 0.015, 0.42, z + dz + 0.015),
                                     "white", bottom=False)
    cameras = {"Overview": ((14.0, 3.5, 14.0), (20.0, 0.0, 20.0)), "Low": ((13.0, 0.5, 20.0), (20.0, 0.2, 20.0))}
    return Scene("small_objects", quads, {"white": WHITE, "floor": GROUND}, cameras, sky=True, sun=SUN, exposure=1.0)


def crytek_sponza():
    """Khronos' copy of Crytek Sponza under the sky and Intel Sponza's sun."""
    cameras = {"Atrium": ((-9.0, 1.6, 0.0), (10.0, 3.0, 0.0)), "Gallery": ((-9.0, 6.2, -4.2), (10.0, 6.0, -4.2)),
               "Arcade": ((-11.0, 1.7, -4.4), (10.0, 2.0, 0.0))}
    models = {"Model": f"{DOWNLOADED}/crytek_sponza/Sponza.gltf"}
    return Scene("crytek_sponza", [], {}, cameras, models=models, sky=True, sun=SPONZA_SUN, exposure=106.0,
                 camera_exposures={"Gallery": 900.0, "Arcade": 4000.0})


def intel_sponza():
    """Intel Sponza with its ivy, seen from its own six cameras, under the sky and its own sun's direction."""
    models = {"Model": f"{DOWNLOADED}/intel_sponza/NewSponza_Main_glTF_003.gltf",
              "Ivy": f"{DOWNLOADED}/intel_sponza_ivy/NewSponza_IvyGrowth_glTF.gltf"}
    cameras = ("PhysCamera001", "PhysCamera002", "PhysCamera004", "PhysCamera005", "PhysCamera006")
    exposures = dict(zip((f"Model/{camera}" for camera in cameras), (110.0, 22.0, 440.0, 53.0, 16.0)))
    return Scene("intel_sponza", [], {}, {}, models=models, sky=True, sun=SPONZA_SUN, exposure=75.0,
                 camera_exposures=exposures)


def bistro_exterior():
    """Bistro's streets from its own camera and three of ours, under its HDR sky, whose sun becomes the scene's sun."""
    cameras = {"Corner": ((-15.7, 1.9, -4.5), (4.5, 1.5, 9.0)), "Terrace": ((-4.5, 1.9, 13.4), (10.0, 1.5, 0.0)),
               "Plaza": ((60.0, 1.9, 30.0), (100.0, 4.0, 45.0))}
    models = {"Model": f"{DOWNLOADED}/bistro/BistroExterior.fbx"}
    panorama, sun, sun_color, sun_energy = sunless_panorama("bistro/san_giuseppe_bridge_4k.hdr")
    return Scene("bistro_exterior", [], {}, cameras, models=models, panorama=panorama, sun=sun, sun_color=sun_color,
                 sun_energy=sun_energy, hidden=("BistroExterior/directionalLight1",), shadow_distance=100.0,
                 camera_exposures={"Model/BistroExterior/Camera": 4.0, "Corner": 1.9})


def bistro_interior():
    """Bistro's interior from its own camera, lit by lamps at its four point lights, each under its ceiling lamp."""
    fixtures = {(4.991, 3.031, -0.489): "03_2360", (7.989, 3.074, 1.015): "04_2362", (4.263, 3.095, -4.920): "02_2358",
                (6.107, 2.939, -8.468): "01_2356"}
    lamps = {f"Lamp{i}": Lamp(position, 0.1, "Paris_Ceiling_Lamp", f"Model/Bistro_Research_Interior_Paris_Ceiling_Light_{node}")
             for i, (position, node) in enumerate(fixtures.items(), 1)}
    models = {"Model": f"{DOWNLOADED}/bistro/BistroInterior.fbx"}
    return Scene("bistro_interior", [], {}, {}, models=models, lamps=lamps,
                 hidden=tuple(f"pointLight{i}" for i in range(1, 5)), exposure=1.4)


# Sky.

def sunless_panorama(source):
    """Writes the downloaded HDR panorama `source` beside itself without the sun's disk, and returns the copy's path
    with the sun the disk held: its elevation and azimuth in degrees and the linear colour and energy of a
    DirectionalLight3D that gives the disk's irradiance, its light above the pixels around it."""
    import cv2  # here, since mitsuba_cornell.py imports this module without OpenCV

    path = ROOT / "assets/downloaded" / source
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise SystemExit(f"{path} is missing: fetch the downloaded scenes first.")

    image = image[..., ::-1].astype(np.float64)  # OpenCV reads BGR
    height, width, _ = image.shape
    luminance = image @ LUMINANCE
    row, column = np.unravel_index(np.argmax(luminance), luminance.shape)
    cap = math.radians(SUN_CAP)
    sun_polar = (row + 0.5) / height * math.pi
    rows = np.arange(max(math.floor((sun_polar - cap) / math.pi * height), 0),
                     min(math.ceil((sun_polar + cap) / math.pi * height), height - 1) + 1)
    directions = panorama_directions(rows, width, height)
    angle = np.arccos(np.clip(directions @ directions[row - rows[0], column], -1.0, 1.0))
    band = image[rows]
    rim = band[(angle <= cap) & (angle > cap - math.radians(SUN_RIM))].mean(axis=0)
    disk = (angle <= cap - math.radians(SUN_RIM)) & (band @ LUMINANCE > SUN_CONTRAST * (rim @ LUMINANCE))

    # The pixels around the disk fill it, so that it blends into the sun's aureole.
    ring = cv2.dilate(disk.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~disk
    fill = band[ring].mean(axis=0)
    polar = (rows + 0.5) / height * math.pi
    solid_angle = np.broadcast_to((math.pi / height) * (2 * math.pi / width) * np.sin(polar)[:, None], disk.shape)
    excess = (band[disk] - fill) * solid_angle[disk][:, None]
    irradiance = excess.sum(axis=0)
    toward = normalize(tuple((directions[disk] * (excess @ LUMINANCE)[:, None]).sum(axis=0)))
    band[disk] = fill
    image[rows] = band

    target = path.with_name(path.stem + "_sunless.hdr")
    cv2.imwrite(str(target), image[..., ::-1].astype(np.float32))
    # Godot's directional light gives an irradiance of pi times its energy times its colour.
    light = irradiance / math.pi
    energy = float(light.max())
    sun = (math.degrees(math.asin(toward[1])), math.degrees(math.atan2(toward[0], toward[2])))
    return f"{DOWNLOADED}/{Path(source).with_name(target.name).as_posix()}", sun, tuple(light / energy), energy


def panorama_directions(rows, width, height):
    """The direction of each pixel of `rows` in Godot's panorama layout, which reads a direction d at
    u = atan2(d.x, -d.z) / 2 pi and v = acos(d.y) / pi."""
    polar = ((rows + 0.5) / height * math.pi)[:, None]
    azimuth = ((np.arange(width) + 0.5) / width * 2 * math.pi)[None, :]
    return np.stack(np.broadcast_arrays(np.sin(polar) * np.sin(azimuth), np.cos(polar),
                                        -np.sin(polar) * np.cos(azimuth)), axis=-1)


# glTF.

def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def normalize(a):
    length = math.sqrt(dot(a, a))
    return tuple(x / length for x in a)


def gltf(scene):
    """One node and mesh per material, with flat normals and planar UVs."""
    data = bytearray()
    document = {"asset": {"version": "2.0", "generator": "src/reference/build_scenes.py"}, "scene": 0,
                "scenes": [{"nodes": []}], "nodes": [], "meshes": [], "materials": [], "accessors": [],
                "bufferViews": []}

    def add(values, kind, component, target):
        fmt = "<f" if component == 5126 else "<I"
        flat = [x for value in values for x in (value if isinstance(value, tuple) else (value,))]
        document["bufferViews"].append({"buffer": 0, "byteOffset": len(data), "byteLength": 4 * len(flat),
                                        "target": target})
        data.extend(b"".join(struct.pack(fmt, x) for x in flat))
        accessor = {"bufferView": len(document["bufferViews"]) - 1, "componentType": component,
                    "count": len(values), "type": kind}
        if kind == "VEC3" and target == 34962:
            accessor["min"] = [min(v[i] for v in values) for i in range(3)]
            accessor["max"] = [max(v[i] for v in values) for i in range(3)]
        document["accessors"].append(accessor)
        return len(document["accessors"]) - 1

    for index, (name, material) in enumerate(scene.materials.items()):
        document["materials"].append(_gltf_material(name, material))
        # Shared vertices keep each plane one connected surface for the UV2 unwrap.
        vertices, indices = {}, []
        for quad in (q for q in scene.quads if q.material == name):
            a, b, c, _ = quad.corners
            normal = normalize(cross(sub(b, a), sub(c, a)))
            tangent = normalize(sub(b, a))
            bitangent = cross(normal, tangent)
            corners = [vertices.setdefault((p, normal, (dot(p, tangent), dot(p, bitangent))), len(vertices))
                       for p in quad.corners]
            indices += [corners[i] for i in (0, 1, 2, 0, 2, 3)]
        positions, normals, uvs = zip(*vertices)
        attributes = {"POSITION": add(positions, "VEC3", 5126, 34962), "NORMAL": add(normals, "VEC3", 5126, 34962),
                      "TEXCOORD_0": add(uvs, "VEC2", 5126, 34962)}
        primitive = {"attributes": attributes, "indices": add(indices, "SCALAR", 5125, 34963), "material": index}
        document["meshes"].append({"name": name, "primitives": [primitive]})
        document["nodes"].append({"name": name, "mesh": index})
        document["scenes"][0]["nodes"].append(index)

    document["buffers"] = [{"byteLength": len(data),
                            "uri": "data:application/octet-stream;base64," + base64.b64encode(data).decode()}]
    if any(max(m.emission) > 1.0 for m in scene.materials.values()):
        document["extensionsUsed"] = ["KHR_materials_emissive_strength"]
    return json.dumps(document, indent=1)


def _gltf_material(name, material):
    result = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": [*material.albedo, 1.0],
                                                      "metallicFactor": 0.0, "roughnessFactor": 1.0}}
    peak = max(material.emission)
    if peak > 0.0:
        strength = max(peak, 1.0)
        result["emissiveFactor"] = [e / strength for e in material.emission]
        if strength > 1.0:
            result["extensions"] = {"KHR_materials_emissive_strength": {"emissiveStrength": strength}}
    if material.two_sided:
        result["doubleSided"] = True
    if material.specular != DEFAULT_SPECULAR:
        # Godot imports no glTF specular, so gi_material_import.gd reads it from the extras.
        result["extras"] = {"specular": material.specular}
    return result


# Godot scene.

def linear_to_srgb(value):
    return 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055


def vector(values):
    return "Vector3(%s)" % ", ".join(f"{v:.6g}" for v in values)


def color(values):
    return "Color(%s, 1)" % ", ".join(f"{v:.6g}" for v in values)


def rotation_to(direction):
    """Euler rotation that points a node's -Z along `direction`."""
    dx, dy, dz = direction
    return (math.atan2(dy, math.hypot(dx, dz)), math.atan2(-dx, -dz), 0.0)


def sun_rotation(sun, azimuth_offset=0.0):
    elevation, azimuth = math.radians(sun[0]), math.radians(sun[1])
    return (-elevation, azimuth + azimuth_offset, 0.0)


def track(index, path, times, values, discrete=False):
    return "\n".join([
        f'tracks/{index}/type = "value"',
        f"tracks/{index}/imported = false",
        f"tracks/{index}/enabled = true",
        f'tracks/{index}/path = NodePath("{path}")',
        f"tracks/{index}/interp = 1",
        f"tracks/{index}/loop_wrap = true",
        f"tracks/{index}/keys = {{",
        f'"times": PackedFloat32Array({", ".join(f"{t:g}" for t in times)}),',
        f'"transitions": PackedFloat32Array({", ".join("1" for _ in times)}),',
        f'"update": {1 if discrete else 0},',
        f'"values": [{", ".join(values)}]',
        "}",
    ])


def animation(scene):
    """Sun moving across the sky, the panel changing colour, lamps switching."""
    tracks, length = [], 0.0
    if scene.sun:
        tracks.append(track(len(tracks), "Sun:rotation", (0.0, SUN_PERIOD),
                            [vector(sun_rotation(scene.sun)), vector(sun_rotation(scene.sun, 2 * math.pi))]))
        length = SUN_PERIOD
    if scene.panel:
        emission = scene.materials[scene.panel].emission
        hue, saturation, _ = colorsys.rgb_to_hsv(*(e / max(emission) for e in emission))
        times = [PANEL_PERIOD * i / 4 for i in range(5)]
        colours = [colorsys.hsv_to_rgb((hue + i / 4) % 1.0, max(saturation, 0.6) if 0 < i < 4 else saturation, 1.0)
                   for i in range(5)]
        path = f"Model/{scene.panel}:mesh:surface_0/material:shader_parameter/emission"
        tracks.append(track(len(tracks), path, times, [color(linear_to_srgb(c) for c in rgb) for rgb in colours]))
        length = max(length, PANEL_PERIOD)
    half = LAMP_PERIOD / 2
    fixtures = {}  # material: the first mesh node and surface that use it, and its emission energy
    for name, lamp in scene.lamps.items():
        tracks.append(track(len(tracks), f"{name}:visible", (0.0, half), ["true", "false"], discrete=True))
        material = scene.materials.get(lamp.fixture)
        energy = max(max(material.emission), 1.0) if material else 1.0
        fixtures.setdefault(lamp.fixture, (lamp.mesh, lamp.surface, energy))
        length = max(length, LAMP_PERIOD)
    for mesh, surface, energy in fixtures.values():
        path = f"{mesh}:mesh:surface_{surface}/material:shader_parameter/emission_energy"
        tracks.append(track(len(tracks), path, (0.0, half), [f"{energy:g}", "0.0"], discrete=True))
    return f'[sub_resource type="Animation" id="animated"]\nresource_name = "animated"\nlength = {length:g}\n' \
           f"loop_mode = 1\n" + "\n".join(tracks)


def sky(scene):
    sky = '[sub_resource type="Sky" id="sky"]\nsky_material = SubResource("sky_material")'
    if scene.panorama:
        material = '[sub_resource type="PanoramaSkyMaterial" id="sky_material"]\npanorama = ExtResource("panorama")'
        # The path tracer shows the sky through its radiance map, which at 2048² holds about a 4K panorama's detail.
        sky += "\nradiance_size = 6"
    elif scene.sky:
        # A grey ground in place of Godot's dark brown, which shows past the edges of the lab's slabs as a void.
        material = ('[sub_resource type="ProceduralSkyMaterial" id="sky_material"]\n'
                    'ground_bottom_color = Color(0.35, 0.35, 0.35, 1)')
    else:
        return []
    return [material, sky]


def environment(scene, resource_id, exposure):
    background = 'background_mode = 2\nsky = SubResource("sky")' if scene.panorama or scene.sky else "background_mode = 1"
    return (f'[sub_resource type="Environment" id="{resource_id}"]\n{background}\n'
            f"tonemap_mode = 4\ntonemap_exposure = {exposure:.6g}\nssr_enabled = true")  # AgX


def camera_environment(path):
    return "environment_" + path.rpartition("/")[2]


def tscn(scene):
    root = "".join(part.capitalize() for part in scene.name.split("_"))
    resources = [f'[ext_resource type="PackedScene" path="{path}" id="{node}"]'
                 for node, path in scene.models.items()]
    resources += ['[ext_resource type="Script" path="res://src/host/gi.gd" id="gi"]',
                  '[ext_resource type="Script" path="res://src/host/gi_effect.gd" id="gi_effect_script"]']
    resources += [f'[ext_resource type="Shader" path="res://assets/shaders/{shader}.gdshader" id="{shader}"]'
                  for shader in SHADERS.values()]
    resources.append('[ext_resource type="RDShaderFile" path="res://src/tracer/cshd_triangles.glsl" '
                     'id="triangles_shader"]')
    if scene.panorama:
        resources.append(f'[ext_resource type="Texture2D" path="{scene.panorama}" id="panorama"]')
    shaders = "".join(f'{slot} = ExtResource("{shader}")\n' for slot, shader in SHADERS.items())
    sections = ["[gd_scene format=3]", "\n".join(resources), *sky(scene), environment(scene, "environment", scene.exposure)]
    sections += [environment(scene, camera_environment(path), exposure)
                 for path, exposure in scene.camera_exposures.items()]
    sections += [
        '[sub_resource type="CompositorEffect" id="gi_effect"]\nscript = ExtResource("gi_effect_script")',
        '[sub_resource type="Compositor" id="compositor"]\n'
        'compositor_effects = Array[CompositorEffect]([SubResource("gi_effect")])',
        animation(scene),
        '[sub_resource type="AnimationLibrary" id="lighting"]\n_data = {\n&"animated": SubResource("animated")\n}',
        f'[node name="{root}" type="Node3D"]',
    ]
    sections += [f'[node name="{node}" parent="." instance=ExtResource("{node}")]' for node in scene.models]
    overrides = [(f"Model/{path}", "visible = false") for path in scene.hidden]
    overrides += [(path, "cast_shadow = 0") for path in dict.fromkeys(lamp.mesh for lamp in scene.lamps.values())]
    overrides += [(path, f'environment = SubResource("{camera_environment(path)}")')
                  for path in scene.camera_exposures if path not in scene.cameras]
    for path, value in overrides:
        parent, _, name = path.rpartition("/")
        sections.append(f'[node name="{name}" parent="{parent}"]\n{value}')
    sections += [
        '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]\n'
        'environment = SubResource("environment")\ncompositor = SubResource("compositor")',
        '[node name="GI" type="Node" parent="."]\nscript = ExtResource("gi")\n'
        f'{shaders}triangles_shader = ExtResource("triangles_shader")',
    ]
    if scene.sun:
        # Light only: a sun disk in the sky would add the sun's light a second time to every path that sees it.
        sections.append('[node name="Sun" type="DirectionalLight3D" parent="."]\n'
                        f"rotation = {vector(sun_rotation(scene.sun))}\n"
                        f"light_color = {color(linear_to_srgb(c) for c in scene.sun_color)}\n"
                        f"light_energy = {scene.sun_energy:.6g}\nlight_angular_distance = {SUN_DIAMETER}\n"
                        f"shadow_enabled = true\nshadow_bias = {SUN_SHADOW_BIAS}\nshadow_normal_bias = {SUN_NORMAL_BIAS}\n"
                        f"directional_shadow_max_distance = {scene.shadow_distance:.6g}\nsky_mode = 1")
    for name, lamp in scene.lamps.items():
        sections.append(f'[node name="{name}" type="OmniLight3D" parent="."]\nposition = {vector(lamp.position)}\n'
                        f"light_size = {lamp.size:.6g}\nshadow_enabled = true\nomni_range = {LAMP_RANGE:.6g}\n"
                        "omni_attenuation = 2.0")
    for index, (name, (eye, target)) in enumerate(scene.cameras.items()):
        current = "\ncurrent = true" if index == 0 else ""
        own_environment = (f'\nenvironment = SubResource("{camera_environment(name)}")'
                           if name in scene.camera_exposures else "")
        sections.append(f'[node name="{name}" type="Camera3D" parent="."]\nposition = {vector(eye)}\n'
                        f"rotation = {vector(rotation_to(sub(target, eye)))}{own_environment}\nfov = {scene.fov:.6g}{current}")
    sections.append('[node name="Lighting" type="AnimationPlayer" parent="."]\nlibraries/ = SubResource("lighting")')
    if overrides:
        sections.append('[editable path="Model"]')
    return "\n\n".join(sections) + "\n"


def main():
    for build in (cornell_box, leak_house, lambda: leak_house(lit=False), two_rooms, pillar_hall, small_objects,
                  crytek_sponza, intel_sponza, bistro_exterior, bistro_interior):
        scene = build()
        files = {f"assets/scenes/scn_{scene.name}.tscn": tscn(scene)}
        if scene.quads:
            files[f"assets/models/mdl_{scene.name}.gltf"] = gltf(scene)
        for path, text in files.items():
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        print(f"{scene.name}: {len(scene.quads)} quads")


if __name__ == "__main__":
    main()
