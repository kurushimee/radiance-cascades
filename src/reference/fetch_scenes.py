"""Downloads the evaluation's downloaded test scenes (design/evaluation.md) into assets/downloaded/, which git ignores.
Archives go to the system's temporary folder and are deleted once the files Godot imports are extracted; an archive
already there at its pinned size is not fetched again.

    python src/reference/fetch_scenes.py

The models then need an import (`godot --headless --path . --import`) and src/editor/import_options.gd.
"""
import fnmatch
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "assets" / "downloaded"
ARCHIVES = Path(tempfile.gettempdir()) / "rc_scenes"
CRYTEK_SPONZA = "https://api.github.com/repos/KhronosGroup/glTF-Sample-Assets/contents/Models/Sponza"
CRYTEK_SPONZA_BYTES = 52_686_624
INTEL_KEEP = ("*.gltf", "*.bin", "*/textures/*", "*/credits_license.txt")
# name: archive file, URL, pinned size in bytes, the members kept
SOURCES = {
    "intel_sponza": ("main_sponza.zip", "https://cdrdv2.intel.com/v1/dl/getContent/830833", 3_987_608_266,
                     INTEL_KEEP),
    "intel_sponza_ivy": ("pkg_b_ivy1.zip", "https://cdrdv2.intel.com/v1/dl/getContent/726656", 1_383_921_436,
                         INTEL_KEEP),
    "bistro": ("Bistro_v5_2.zip", "https://developer.nvidia.com/downloads/bistro", 894_377_473,
               ("*/BistroExterior.fbx", "*/BistroInterior.fbx", "*/Textures/*", "*.hdr", "*/LICENSE.txt",
                "*/README.txt")),
}


def fetch(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response, open(path, "wb") as file:
        shutil.copyfileobj(response, file, 1 << 20)


def crytek_sponza():
    """The glTF folder of Khronos' glTF-Sample-Assets copy, with its licence."""
    target = TARGET / "crytek_sponza"
    files = json.load(urllib.request.urlopen(CRYTEK_SPONZA + "/glTF"))
    licence = [f for f in json.load(urllib.request.urlopen(CRYTEK_SPONZA)) if f["name"] == "LICENSE.md"]
    if sum(f["size"] for f in files) != CRYTEK_SPONZA_BYTES:
        raise RuntimeError("Crytek Sponza changed upstream: its glTF files no longer add up to the pinned size.")
    for f in files + licence:
        fetch(f["download_url"], target / f["name"])


def extract(name, file_name, url, size, keep):
    archive = ARCHIVES / name / file_name
    if not archive.exists() or archive.stat().st_size != size:
        fetch(url, archive)
    if archive.stat().st_size != size:
        raise RuntimeError(f"{file_name} is {archive.stat().st_size} bytes, not the pinned {size}.")

    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            if member.is_dir() or not any(fnmatch.fnmatch(member.filename, pattern) for pattern in keep):
                continue
            # The archive's top folder is dropped.
            target = TARGET / name / member.filename.split("/", 1)[1]
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(member) as source, open(target, "wb") as file:
                shutil.copyfileobj(source, file, 1 << 20)
    shutil.rmtree(archive.parent)


def main():
    crytek_sponza()
    print("crytek_sponza")
    for name, source in SOURCES.items():
        extract(name, *source)
        print(name)
    if not any(ARCHIVES.iterdir()):
        ARCHIVES.rmdir()


if __name__ == "__main__":
    main()
