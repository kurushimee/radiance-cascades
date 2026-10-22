# /// script
# requires-python = ">=3.11"
# dependencies = ["flip-evaluator", "numpy", "openexr"]
# ///
"""The evaluation's image metrics (design/evaluation.md#metrics) on camera folders written by scene_capture.gd. A
capture of the GI holds final.exr, Godot's final image, and irradiance.exr, the E/π it hands Godot. A path-traced
reference holds the path tracer's E/π in irradiance.exr, Godot's final image with that E/π in final.exr, Godot's final
image at an irradiance of 0 and of 1, from which flip-limit composes the final image for other irradiances, and the
surfaces' world positions in position.exr. A denoised reference adds the path-traced final image, path_traced.exr; an
accumulated one adds E/π over its even frames, irradiance_half.exr. Pixels without a surface, alpha 0 in
irradiance.exr, are left out. A GI capture's direct.exr holds its light code's E/π at the pixels, and a direct
reference's direct.exr and direct_half.exr the path tracer's direct E/π over all frames and the even ones.

    uv run src/reference/metrics.py compare <test camera folder> <reference camera folder>
    uv run src/reference/metrics.py leak <inside camera folder> <outside camera folder>
    uv run src/reference/metrics.py agree <reference camera folder with albedo.exr> <other reference's camera folder>
    uv run src/reference/metrics.py flip-limit <reference camera folder> <texel spacing> <RMSE limit> <bias limit>
    uv run src/reference/metrics.py flip-floor <denoised reference camera folder>
    uv run src/reference/metrics.py direct <GI camera folder> <direct reference camera folder>
    uv run src/reference/metrics.py texels <atlas EXR> <atlas EXR of the same atlas>

All print JSON. A relative figure is null when the reference's mean is zero, and HDR-FLIP when the reference's final
image has no light.
"""
import inspect
import itertools
import json
import sys
from pathlib import Path

import flip_evaluator
import numpy as np
import OpenEXR

FINAL = "final.exr"
PATH_TRACED = "path_traced.exr"
IRRADIANCE = "irradiance.exr"
IRRADIANCE_HALF = "irradiance_half.exr"
ALBEDO = "albedo.exr"
POSITION = "position.exr"
NO_INDIRECT = "no_indirect.exr"
UNIT_INDIRECT = "unit_indirect.exr"
DIRECT = "direct.exr"
DIRECT_HALF = "direct_half.exr"
LUMINANCE = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
CREASE = 0.1  # a bend in the positions this large against their step marks a crease or a jump
ALBEDO_STEP = 1e-3
FLIP_SHARE = 0.05  # a pixel this dark beside the other side's value sees the light blocked on that side alone
FLIP_LEVEL = 0.2  # of the mean, so that a flip is a lit pixel, not a dim one
LATTICE_PRIMES = np.array([73856093, 19349663, 83492791], dtype=np.uint64)  # Teschner et al. 2003


def read(path):
    """An RGB or RGBA EXR as float32 pixels, height x width x channels."""
    channels = OpenEXR.File(str(path)).channels()
    return np.asarray(channels["RGBA" if "RGBA" in channels else "RGB"].pixels, dtype=np.float32)


def masked(path):
    """An RGBA EXR's colour, and the mask of its pixels with alpha."""
    pixels = read(path)
    return pixels[..., :3], pixels[..., 3] > 0.5


def irradiance(folder):
    """E/π, and the mask of the pixels with a surface."""
    return masked(Path(folder) / IRRADIANCE)


def half_difference(folder):
    """A reference's mean over all samples less its mean over the even ones. It varies as much as the full mean does,
    so its square estimates the full mean's variance at each pixel, and so does that of any average of its channels."""
    return irradiance(folder)[0] - read(Path(folder) / IRRADIANCE_HALF)[..., :3]


def interior(folder):
    """The pixels whose 3x3 neighbourhood sees one smooth surface: one albedo, and positions without a crease or a
    jump. A renderer that filters over each pixel blends the pixels at those edges."""
    albedo = read(Path(folder) / ALBEDO)
    position = read(Path(folder) / POSITION)[..., :3]
    smooth = albedo[..., 3] > 0.5
    for axis in (0, 1):
        previous, following = np.roll(position, 1, axis), np.roll(position, -1, axis)
        bend = np.linalg.norm(previous - 2 * position + following, axis=-1)
        smooth &= bend <= CREASE * np.linalg.norm(following - previous, axis=-1) / 2
        smooth &= np.abs(np.roll(albedo, -1, axis) - albedo).max(axis=-1) <= ALBEDO_STEP
    smooth[[0, -1], :] = False
    smooth[:, [0, -1]] = False
    return np.logical_and.reduce([np.roll(smooth, shift, (0, 1)) for shift in itertools.product((-1, 0, 1), repeat=2)])


def compose(folder, values):
    """A reference's final image for the irradiance `values`. With Godot's specular occlusion off, as in the GI
    materials, Godot's final image is affine in each pixel's irradiance, apart from its screen-space reflections, which
    show other pixels'."""
    none = read(Path(folder) / NO_INDIRECT)[..., :3]
    unit = read(Path(folder) / UNIT_INDIRECT)[..., :3]
    return np.ascontiguousarray(none + (unit - none) * values)


def final(folder, name=FINAL):
    return np.ascontiguousarray(read(Path(folder) / name)[..., :3])


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
    return {"relative_rmse": rmse, "relative_bias": bias, "hdr_flip": hdr_flip(final(reference), final(test)),
            "pixels": int(mask.sum())}


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


def flip_floor(reference):
    """The HDR-FLIP of Godot's final image with the reference's E/π against the path-traced one: what Godot's own
    direct light, shadows and reflections leave between an exact GI and path tracing."""
    return {"hdr_flip": hdr_flip(final(reference, PATH_TRACED), final(reference))}


def agree(first, second):
    """Two references of one view, compared over the pixels both see, away from the edges in the first, whose albedo
    and positions come from the pixels' centres. They agree when the relative bias is within three standard deviations
    of the mean and the squared difference's excess over their noise within three of its standard errors of zero."""
    first_values, first_mask = irradiance(first)
    second_values, second_mask = irradiance(second)
    mask = first_mask & second_mask & interior(first)
    halves = [half_difference(folder)[mask] for folder in (first, second)]
    return agreement((first_values - second_values)[mask], halves, float(np.mean(second_values[mask])))


def direct(test, reference):
    """The GI's light code at the pixels against the path tracer's direct view, over the pixels both see. Both read
    the pixels' centres, so no edge is left out. The GI's side has no noise, so the reference's half difference alone
    feeds the deviations. A scene without lights gives the GI's largest value, which must be zero.

    A few pixels are lit on one side and dark on the other. A ray toward the light that grazes the surface it leaves,
    or leaves it below its face where the interpolated normal turns far from the face, clears its own mesh or meets it
    as rounding decides, and a leaf that the reference's depth view cannot tell from a parallel one behind it passes
    for the same surface. They are counted, and the agreement is given again without them."""
    test_values, test_mask = masked(Path(test) / DIRECT)
    reference_values, reference_mask = masked(Path(reference) / DIRECT)
    mask = test_mask & reference_mask
    test_values, reference_values = test_values[mask], reference_values[mask]
    scale = float(np.mean(reference_values))
    if scale == 0.0:
        return {"largest": float(test_values.max()), "pixels": int(mask.sum())}

    half = reference_values - read(Path(reference) / DIRECT_HALF)[..., :3][mask]
    result = agreement(test_values - reference_values, [half], scale)
    test_level, reference_level = test_values.mean(axis=-1), reference_values.mean(axis=-1)
    brighter = np.maximum(test_level, reference_level)
    flips = (np.minimum(test_level, reference_level) < FLIP_SHARE * brighter) & (brighter > FLIP_LEVEL * scale)
    kept = ~flips
    result["flips"] = int(flips.sum())
    result["without_flips"] = agreement((test_values - reference_values)[kept], [half[kept]],
                                        float(np.mean(reference_values[kept])))
    return result


def agreement(difference, halves, scale):
    """The relative bias of the pixels' `difference`, with its count of standard deviations of the noise that the
    `halves` estimate, the relative RMSE, the relative RMSE that the noise alone accounts for, all normalized by
    `scale`, and the squared difference's excess over the noise's, as a share of the noise's, with its standard
    error."""
    pixel_variance = sum(np.mean(half, axis=-1) ** 2 for half in halves)
    noise_squares = sum(np.sum(half ** 2, axis=-1) for half in halves)
    # Without a difference of their own, a pixel's squared difference less its noise's averages zero, and the
    # pixels' noise is independent.
    excess = np.sum(difference ** 2, axis=-1) - noise_squares
    return {
        "relative_bias": float(np.mean(difference)) / scale,
        "bias_deviations": float(np.mean(difference) / (np.sqrt(np.sum(pixel_variance)) / len(difference))),
        "relative_rmse": float(np.sqrt(np.mean(difference ** 2))) / scale,
        "noise_rmse": float(np.sqrt(np.mean(noise_squares) / difference.shape[-1])) / scale,
        "excess": float(np.sum(excess) / np.sum(noise_squares)),
        "excess_error": float(np.sqrt(np.sum(excess ** 2)) / np.sum(noise_squares)),
        "pixels": len(difference),
    }


def texels(first, second):
    """Two views of one atlas, compared over the texels both cover: the relative RMSE and bias of the second against
    the first."""
    first_values, first_mask = masked(first)
    second_values, second_mask = masked(second)
    mask = first_mask & second_mask
    rmse, bias = relative(second_values[mask], first_values[mask])
    return {"relative_rmse": rmse, "relative_bias": bias, "texels": int(mask.sum())}


def lattice_noise(points, spacing):
    """Value noise: a random value at each corner of a world lattice, interpolated trilinearly."""
    scaled = points / spacing
    cells = np.floor(scaled).astype(np.int64)
    fractions = scaled - cells
    total = np.zeros(len(points))
    for corner in itertools.product((0, 1), repeat=3):
        weights = np.prod(np.where(corner, fractions, 1.0 - fractions), axis=-1)
        keys = np.bitwise_xor.reduce((cells + corner).astype(np.uint64) * LATTICE_PRIMES, axis=-1)
        total += weights * (splitmix64(keys) >> np.uint64(11)) / 2.0 ** 53
    return total


def splitmix64(keys):
    keys = keys + np.uint64(0x9E3779B97F4A7C15)
    keys = (keys ^ (keys >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    keys = (keys ^ (keys >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return keys ^ (keys >> np.uint64(31))


def flip_limit(reference, spacing, rmse_limit, bias_limit):
    """The HDR-FLIP that the indirect-error limits allow: the reference's E/π scaled by 1 ± bias + s·n(x), with n
    zero-mean unit-RMS value noise on a world lattice at the texel spacing and s set for the RMSE limit, composed into a
    final image. The limit is the smaller FLIP of the two signs of the bias."""
    values, mask = irradiance(reference)
    pattern = lattice_noise(read(Path(reference) / POSITION)[mask][:, :3].astype(np.float64), float(spacing))
    noise_map = np.zeros(mask.shape)
    noise_map[mask] = (pattern - pattern.mean()) / pattern.std()
    exact = compose(reference, values)
    results = []
    for bias in (float(bias_limit), -float(bias_limit)):
        perturbed = values * (1.0 + bias + noise_scale(values[mask], noise_map[mask], bias, float(rmse_limit))
                              * noise_map[..., None])
        rmse, achieved_bias = relative(perturbed[mask], values[mask])
        results.append({"hdr_flip": hdr_flip(exact, compose(reference, perturbed)), "relative_rmse": rmse,
                        "relative_bias": achieved_bias})
    flips = [result["hdr_flip"] for result in results]
    return {"hdr_flip": None if None in flips else min(flips), "perturbations": results}


def noise_scale(values, pattern, bias, rmse_limit):
    """The s at which the relative RMSE, sqrt(mean(E²(bias + s·n)²)) / mean(E), equals the limit: the positive root
    of a quadratic in s."""
    squares, pattern = values ** 2, pattern[:, None]
    quadratic = [np.mean(squares * pattern ** 2), 2 * bias * np.mean(squares * pattern),
                 bias ** 2 * np.mean(squares) - (rmse_limit * np.mean(values)) ** 2]
    return float(np.max(np.roots(quadratic)))


COMMANDS = {"compare": compare, "leak": leak, "agree": agree, "flip-limit": flip_limit,
            "flip-floor": flip_floor, "direct": direct, "texels": texels}

if __name__ == "__main__":
    command = COMMANDS.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if command is None or len(sys.argv) - 2 != len(inspect.signature(command).parameters):
        sys.exit(__doc__)
    print(json.dumps(command(*sys.argv[2:]), indent=1))
