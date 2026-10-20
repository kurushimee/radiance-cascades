# /// script
# requires-python = ">=3.11"
# dependencies = ["flip-evaluator", "numpy", "openexr"]
# ///
"""The evaluation's image metrics (design/evaluation.md#metrics) on camera folders written by scene_capture.gd, each
holding a final.exr and an irradiance.exr. Pixels without a surface, alpha 0 in irradiance.exr, are left out.

    uv run src/reference/metrics.py compare <test camera folder> <reference camera folder>
    uv run src/reference/metrics.py leak <inside camera folder> <outside camera folder>

Both print JSON. A relative figure is null when the reference's mean is zero, and HDR-FLIP when the reference's final
image has no light.
"""
import json
import sys
from pathlib import Path

import flip_evaluator
import numpy as np
import OpenEXR

FINAL = "final.exr"
IRRADIANCE = "irradiance.exr"
LUMINANCE = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def read(path):
    """An RGB or RGBA EXR as float32 pixels, height x width x channels."""
    channels = OpenEXR.File(str(path)).channels()
    return np.asarray(channels["RGBA" if "RGBA" in channels else "RGB"].pixels, dtype=np.float32)


def irradiance(folder):
    """E/π, and the mask of the pixels with a surface."""
    pixels = read(Path(folder) / IRRADIANCE)
    return pixels[..., :3], pixels[..., 3] > 0.5


def relative(estimate, exact):
    """Relative RMSE and relative bias, both normalized by the mean of `exact`, as in the lab."""
    scale = float(np.mean(exact))
    if scale == 0.0:
        return None, None
    return float(np.sqrt(np.mean((estimate - exact) ** 2)) / scale), float(np.mean(estimate - exact) / scale)


def compare(test, reference):
    """Indirect error over the pixels where both captures see a surface, and the image error of the final images."""
    test_irradiance, test_mask = irradiance(test)
    reference_irradiance, reference_mask = irradiance(reference)
    mask = test_mask & reference_mask
    rmse, bias = relative(test_irradiance[mask], reference_irradiance[mask])
    finals = [np.ascontiguousarray(read(Path(folder) / FINAL)[..., :3]) for folder in (reference, test)]
    return {"relative_rmse": rmse, "relative_bias": bias, "hdr_flip": hdr_flip(*finals), "pixels": int(mask.sum())}


def hdr_flip(reference, test):
    """Mean HDR-FLIP. FLIP takes its exposure range from the reference's peak luminance, and exits the process when
    that peak is below float32 epsilon."""
    if float((reference @ LUMINANCE).max()) < np.finfo(np.float32).eps:
        return None
    return flip_evaluator.evaluate(reference, test, "HDR", applyMagma=False)[1]


def leak(inside, outside):
    """The mean irradiance inside as a share of the outside."""
    means = []
    for folder in (inside, outside):
        values, mask = irradiance(folder)
        means.append(float(np.mean(values[mask])))
    return {"inside": means[0], "outside": means[1], "leak": means[0] / means[1] if means[1] else None}


COMMANDS = {"compare": compare, "leak": leak}

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    print(json.dumps(COMMANDS[sys.argv[1]](*sys.argv[2:]), indent=1))
