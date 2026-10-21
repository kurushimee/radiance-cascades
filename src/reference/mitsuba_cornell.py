# /// script
# requires-python = ">=3.11"
# dependencies = ["mitsuba", "numpy"]
# ///
"""The Cornell box of build_scenes.py rendered by Mitsuba 3, written as a reference camera folder like an accumulated
one (scene_capture.gd --accumulate) for `metrics.py agree`: irradiance.exr holds E/π over all passes and
irradiance_half.exr over the even passes, and albedo.exr and position.exr the surfaces' albedo and world position,
which `agree` reads from its first folder. E/π is the rendered radiance over the albedo, which holds where a surface
does not emit, so alpha is 0 on the light.

    uv run src/reference/mitsuba_cornell.py <camera folder> <samples per pixel, a multiple of 32>
"""
import sys
import tempfile
from pathlib import Path

import mitsuba as mi
import numpy as np

from build_scenes import cornell_box

SIZE = (1280, 720)
SAMPLES_PER_PASS = 16  # keeps a pass's wavefront within the GPU's memory


def obj(quads):
    """The quads as two triangles each in the glTF's order, so both renderers see the same surfaces."""
    vertices, faces = [], []
    for quad in quads:
        first = len(vertices) + 1
        vertices += [f"v {x} {y} {z}" for x, y, z in quad.corners]
        faces += [f"f {first} {first + 1} {first + 2}", f"f {first} {first + 2} {first + 3}"]
    return "\n".join(vertices + faces) + "\n"


def load(folder):
    scene = cornell_box()
    shapes = {}
    for name, material in scene.materials.items():
        path = folder / f"{name}.obj"
        path.write_text(obj(quad for quad in scene.quads if quad.material == name))
        shapes[name] = {"type": "obj", "filename": str(path), "face_normals": True,
                        "bsdf": {"type": "diffuse", "reflectance": {"type": "rgb", "value": material.albedo}}}
        if any(material.emission):
            shapes[name]["emitter"] = {"type": "area", "radiance": {"type": "rgb", "value": material.emission}}

    eye, target = scene.cameras["Front"]
    sensor = {"type": "perspective", "fov": scene.fov, "fov_axis": "y",
              "to_world": mi.ScalarTransform4f().look_at(origin=eye, target=target, up=(0.0, 1.0, 0.0)),
              "film": {"type": "hdrfilm", "width": SIZE[0], "height": SIZE[1], "rfilter": {"type": "box"}}}
    integrator = {"type": "aov", "aovs": "albedo:albedo,position:position", "radiance": {"type": "path"}}
    emitting = [material.albedo for material in scene.materials.values() if any(material.emission)]
    return mi.load_dict({"type": "scene", "integrator": integrator, "sensor": sensor, **shapes}), emitting


def render(scene, samples):
    """Every channel's mean over the even passes and over the odd ones, by channel name."""
    film = scene.sensors()[0].film()
    sums = [0.0, 0.0]
    passes = samples // SAMPLES_PER_PASS
    for index in range(passes):
        mi.render(scene, spp=SAMPLES_PER_PASS, seed=index)
        sums[index % 2] = sums[index % 2] + np.array(film.bitmap(), dtype=np.float64)
    names = [field.name for field in film.bitmap().struct_()]
    return [{name: total[..., index] / (passes // 2) for index, name in enumerate(names)} for total in sums]


def channels(image, prefix, suffixes):
    return np.stack([image[prefix + suffix] for suffix in suffixes], axis=-1)


def write(folder, even, odd, emitting):
    mean = {name: (even[name] + odd[name]) / 2 for name in even}
    albedo = channels(mean, "albedo.", "RGB")
    surface = mean["radiance.A"] > 0.999
    for emitter in emitting:
        surface &= np.abs(albedo - emitter).max(axis=-1) > 1e-3
    divisor = np.where(albedo > 0.0, albedo, 1.0)
    images = {"irradiance": channels(mean, "radiance.", "RGB") / divisor,
              "irradiance_half": channels(even, "radiance.", "RGB") / divisor,
              "albedo": albedo, "position": channels(mean, "position.", "XYZ")}
    folder.mkdir(parents=True, exist_ok=True)
    for name, colour in images.items():
        pixels = np.concatenate([colour, surface[..., None]], axis=-1).astype(np.float32)
        mi.Bitmap(pixels, mi.Bitmap.PixelFormat.RGBA).write(str(folder / f"{name}.exr"))


def main():
    if len(sys.argv) != 3 or int(sys.argv[2]) % (2 * SAMPLES_PER_PASS):
        sys.exit(__doc__)
    mi.set_variant("cuda_ad_rgb")
    with tempfile.TemporaryDirectory() as meshes:
        scene, emitting = load(Path(meshes))
        write(Path(sys.argv[1]), *render(scene, int(sys.argv[2])), emitting)


if __name__ == "__main__":
    main()
