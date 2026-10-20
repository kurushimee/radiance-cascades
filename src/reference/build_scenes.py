"""Writes the evaluation's built test scenes (design/evaluation.md): glTF geometry to assets/models/ and Godot scenes
to assets/scenes/.

The rooms are the lab's 32-voxel scenes (design/experiments/common.py and papers/03_bounces_one_frame/experiments/)
at 0.25 m per voxel and the lab's albedo of 0.9, so that their results compare with E1 to E5. The Cornell box has the
published Cornell geometry with Mitsuba 3's RGB reflectances and light, so that Mitsuba can build the same box from
the same numbers. Each scene has a camera per pose, a static lighting setup and an `animated` animation.

    python src/reference/build_scenes.py

New models then need an import (`godot --headless --path . --import`) and src/editor/texel_size.gd.
"""
import base64
import colorsys
import json
import math
import random
import struct
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VOXEL = 0.25
N = 32
ALBEDO = 0.9
PANEL = 5.0  # radiance of the rooms' ceiling panels
SUN = (35.0, 30.0)  # elevation and azimuth, degrees
SUN_PERIOD = 60.0
PANEL_PERIOD = 8.0
LAMP_PERIOD = 4.0


@dataclass(frozen=True)
class Material:
    albedo: tuple
    emission: tuple = (0.0, 0.0, 0.0)  # linear radiance
    two_sided: bool = False


@dataclass(frozen=True)
class Quad:
    """Four corners counter-clockwise seen from the front."""
    corners: tuple
    material: str


@dataclass(frozen=True)
class Lamp:
    """A Godot light under a fixture: the fixture's emission stays out of the solve."""
    position: tuple
    fixture: str


@dataclass
class Scene:
    name: str
    quads: list
    materials: dict
    cameras: dict  # name: (eye, target)
    fov: float = 70.0
    sky: bool = False
    sun: bool = False
    lamps: dict = field(default_factory=dict)
    panel: str = ""  # the emissive material whose colour the animation changes


def grey(value):
    return (value, value, value)


WHITE = Material(grey(ALBEDO))


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
    """A lab voxel volume. A face exists where a solid voxel meets an empty one inside the volume."""

    def __init__(self):
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
        for axis in range(3):
            for side in (0, N - 1):
                lo, hi = [0, 0, 0], [N, N, N]
                lo[axis], hi[axis] = side, side + 1
                self.fill(lo, hi)

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
                    if 0 <= front[axis] < N and tuple(front) not in self.solid:
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


# Scenes. Godot's y is up; the lab's (x, y, z) with z up maps to (x, z, y).

def cornell_box():
    """The Cornell box in metres (www.graphics.cornell.edu/online/box/data.html), the ceiling cut around the light.
    The room is one grid of quads through the light's edges, so that neighbouring quads share their corners."""
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
        "white": Material((0.885809, 0.698859, 0.666422)),
        "red": Material((0.570068, 0.0430135, 0.0443706)),
        "green": Material((0.105421, 0.37798, 0.076425)),
        "light": Material(grey(0.78), (18.387, 13.9873, 6.75357)),
    }
    camera = (0.278, 0.273, -0.8)
    return Scene("cornell_box", quads, materials, {"Front": (camera, (0.278, 0.273, 0.0))},
                 fov=math.degrees(2 * math.atan(12.5 / 35)), panel="light")


def sealed_room_thick():
    """The lab's sealed box: a closed room with walls one voxel thick on a slab under the sky and the sun."""
    volume = Volume()
    volume.fill((0, 0, 0), (N, 1, N))
    volume.fill((8, 1, 8), (24, 17, 24))
    volume.carve((9, 1, 9), (23, 16, 23))
    cameras = {"Outside": ((10.5, 4.0, 10.5), (4.0, 1.5, 4.0)), "Inside": ((2.6, 1.7, 2.6), (5.6, 1.0, 5.6))}
    return Scene("sealed_room_thick", volume.quads(), {"white": WHITE}, cameras, sky=True, sun=True)


def sealed_room_plane():
    """The sealed room with single-plane, two-sided walls and ceiling on a ground split into a grid at the walls."""
    lo, hi, top, edge = 2.0, 6.0, 4.0, 8.0
    breaks = (0.0, lo, hi, edge)
    quads = [face(1, 1, 0.0, (z0, z1), (x0, x1), "white")
             for x0, x1 in zip(breaks, breaks[1:]) for z0, z1 in zip(breaks, breaks[1:])]
    quads += [face(0, sign, x, (0.0, top), (lo, hi), "white_two_sided") for sign, x in ((1, hi), (-1, lo))]
    quads += [face(2, sign, z, (lo, hi), (0.0, top), "white_two_sided") for sign, z in ((1, hi), (-1, lo))]
    quads.append(face(1, 1, top, (lo, hi), (lo, hi), "white_two_sided"))
    materials = {"white": WHITE, "white_two_sided": Material(grey(ALBEDO), two_sided=True)}
    cameras = {"Outside": ((10.5, 4.0, 10.5), (4.0, 1.5, 4.0)), "Inside": ((2.4, 1.7, 2.4), (5.6, 0.8, 5.6))}
    return Scene("sealed_room_plane", quads, materials, cameras, sky=True, sun=True)


def two_rooms():
    """The lab's two rooms joined by a door, the panel in one and a lamp in the other."""
    volume = Volume()
    volume.shell()
    volume.fill((16, 1, 1), (17, N - 1, N - 1))
    volume.carve((16, 1, 12), (17, 14, 20))
    volume.paint_ceiling((3, 13), (11, 21), "light")
    volume.fill((24, 28, 16), (25, 29, 17), "fixture_lamp")
    materials = {"white": WHITE, "light": Material((0.0, 0.0, 0.0), grey(PANEL)),
                 "fixture_lamp": Material((0.0, 0.0, 0.0), (10.0, 9.0, 7.5))}
    cameras = {"RoomA": ((0.8, 1.7, 7.2), (4.1, 1.5, 4.0)), "RoomB": ((7.2, 1.7, 0.8), (4.1, 1.5, 4.0))}
    lamps = {"Lamp": Lamp((6.125, 6.8, 4.125), "fixture_lamp")}
    return Scene("two_rooms", volume.quads(), materials, cameras, lamps=lamps)


def pillar_hall():
    """The lab's columns: a closed hall lit by a ceiling panel, with a grid of pillars one voxel thick."""
    volume = Volume()
    volume.shell()
    for x in range(6, N - 5, 5):
        for z in range(6, N - 5, 5):
            volume.fill((x, 1, z), (x + 1, N - 1, z + 1))
    volume.paint_ceiling((11, 21), (11, 21), "light")
    materials = {"white": WHITE, "light": Material((0.0, 0.0, 0.0), grey(PANEL))}
    cameras = {"Corner": ((0.7, 1.7, 0.7), (5.0, 1.2, 5.0)), "Aisle": ((2.25, 1.7, 0.6), (2.25, 1.2, 7.4))}
    return Scene("pillar_hall", volume.quads(), materials, cameras, panel="light")


def small_objects():
    """Posts, cubes and stools smaller than a texel on a 40 m floor under the sky and the sun."""
    rng = random.Random(1)
    quads = [face(1, 1, 0.0, (0.0, 40.0), (0.0, 40.0), "white")]
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
    return Scene("small_objects", quads, {"white": WHITE}, cameras, sky=True, sun=True)


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


def sun_rotation(azimuth_offset=0.0):
    elevation, azimuth = math.radians(SUN[0]), math.radians(SUN[1])
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
                            [vector(sun_rotation()), vector(sun_rotation(2 * math.pi))]))
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
    for name, lamp in scene.lamps.items():
        half = LAMP_PERIOD / 2
        tracks.append(track(len(tracks), f"{name}:visible", (0.0, half), ["true", "false"], discrete=True))
        energy = max(max(scene.materials[lamp.fixture].emission), 1.0)
        path = f"Model/{lamp.fixture}:mesh:surface_0/material:shader_parameter/emission_energy"
        tracks.append(track(len(tracks), path, (0.0, half), [f"{energy:g}", "0.0"], discrete=True))
        length = max(length, LAMP_PERIOD)
    return f'[sub_resource type="Animation" id="animated"]\nresource_name = "animated"\nlength = {length:g}\n' \
           f"loop_mode = 1\n" + "\n".join(tracks)


def tscn(scene):
    root = "".join(part.capitalize() for part in scene.name.split("_"))
    background = ('[sub_resource type="ProceduralSkyMaterial" id="sky_material"]\n\n'
                  '[sub_resource type="Sky" id="sky"]\nsky_material = SubResource("sky_material")\n\n'
                  '[sub_resource type="Environment" id="environment"]\nbackground_mode = 2\nsky = SubResource("sky")'
                  if scene.sky else '[sub_resource type="Environment" id="environment"]\nbackground_mode = 1')
    sections = [
        "[gd_scene format=3]",
        f'[ext_resource type="PackedScene" path="res://assets/models/mdl_{scene.name}.gltf" id="model"]\n'
        '[ext_resource type="Script" path="res://src/host/gi.gd" id="gi"]\n'
        '[ext_resource type="Script" path="res://src/host/gi_effect.gd" id="gi_effect_script"]\n'
        '[ext_resource type="Shader" path="res://assets/shaders/shd_gi.gdshader" id="shd_gi"]\n'
        '[ext_resource type="Shader" path="res://assets/shaders/shd_gi_double_sided.gdshader" '
        'id="shd_gi_double_sided"]',
        background,
        '[sub_resource type="CompositorEffect" id="gi_effect"]\nscript = ExtResource("gi_effect_script")',
        '[sub_resource type="Compositor" id="compositor"]\n'
        'compositor_effects = Array[CompositorEffect]([SubResource("gi_effect")])',
        animation(scene),
        '[sub_resource type="AnimationLibrary" id="lighting"]\n_data = {\n&"animated": SubResource("animated")\n}',
        f'[node name="{root}" type="Node3D"]',
        '[node name="Model" parent="." instance=ExtResource("model")]',
        '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]\n'
        'environment = SubResource("environment")\ncompositor = SubResource("compositor")',
        '[node name="GI" type="Node" parent="."]\nscript = ExtResource("gi")\n'
        'shaders = Array[Shader]([ExtResource("shd_gi"), ExtResource("shd_gi_double_sided")])',
    ]
    if scene.sun:
        sections.append('[node name="Sun" type="DirectionalLight3D" parent="."]\n'
                        f"rotation = {vector(sun_rotation())}\nshadow_enabled = true")
    for name, lamp in scene.lamps.items():
        sections.append(f'[node name="{name}" type="OmniLight3D" parent="."]\nposition = {vector(lamp.position)}\n'
                        "shadow_enabled = true\nomni_range = 10.0")
    for index, (name, (eye, target)) in enumerate(scene.cameras.items()):
        current = "\ncurrent = true" if index == 0 else ""
        sections.append(f'[node name="{name}" type="Camera3D" parent="."]\nposition = {vector(eye)}\n'
                        f"rotation = {vector(rotation_to(sub(target, eye)))}\nfov = {scene.fov:.6g}{current}")
    sections.append('[node name="Lighting" type="AnimationPlayer" parent="."]\nlibraries/ = SubResource("lighting")')
    return "\n\n".join(sections) + "\n"


def main():
    for build in (cornell_box, sealed_room_thick, sealed_room_plane, two_rooms, pillar_hall, small_objects):
        scene = build()
        for path, text in ((f"assets/models/mdl_{scene.name}.gltf", gltf(scene)),
                           (f"assets/scenes/scn_{scene.name}.tscn", tscn(scene))):
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        print(f"{scene.name}: {len(scene.quads)} quads")


if __name__ == "__main__":
    main()
