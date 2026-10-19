"""Precision of an 8-bit narrow band of +-4 voxels, and scene volumes against a dense cascade stack."""
MIB = 2 ** 20

# daGI2's decode (2a - 1) * 4 voxels over 255 steps of a: a step of 8/255 voxel, rounding error half that.
step = 8 / 255
assert round(step, 4) == 0.0314
assert round(step / 2, 4) == 0.0157 and step / 2 < 1 / 63

sizes = {(n, b): n ** 3 * b / MIB for n in (128, 256) for b in (1, 2, 4)}
assert [sizes[(128, b)] for b in (1, 2, 4)] == [2, 4, 8]
assert [sizes[(256, b)] for b in (1, 2, 4)] == [16, 32, 64]
assert all(v <= 128 for v in sizes.values())

# Vulkan guarantees 128 MiB per storage buffer. A dense 128^3 stack with 32 cascade 0 directions in fp16
# holds about 2 * N^3 * D0 texels of 8 B, 1,008 MiB as tabulated in 3d_world_space.md.
stack = 2 * 128 ** 3 * 32 * 8 / MIB * 63 / 64
assert round(stack) == 1008
assert 7 < stack / 128 < 8
