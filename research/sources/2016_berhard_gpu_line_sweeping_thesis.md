# A GPU Line Sweeping Framework

| | |
|---|---|
| Author | Constantin Berhard |
| Date | 2016-12-01 |
| Kind | Master's thesis, Saarland University (hosted at pdf.inf.usi.ch), 67 pages; OpenCL and C++ |
| Link | https://www.pdf.inf.usi.ch/papers/master_thesis/ConstantinBerhard.pdf |

The thesis generalizes the line sweep of [LSAO](2013_timonen_line_sweep_ambient_obscurance.md) into a framework: for each direction, parallel rays cross the domain, a small per-ray state machine (the "information condenser") digests the samples it passes, and an accumulator combines the per-direction results at each output position. It applies the framework to LSAO, diffusion inpainting, inside-outside voxelization and signed distance fields, and sketches line-sweep photon mapping. Page numbers are the printed ones.

## Framework (ch. 4, 5)

- Algorithm 1 (p. 16): for each direction `d`, for each sampled ray entering the domain, a new condenser walks `a += stepSize·d` while `a` is inside, calls `digest(a, d, f(a))` at each step and writes `getInterestingData()` to `output[a, d]`. Work is parallel over directions and rays, and a condenser cannot allocate memory on the GPU.
- Direct accumulation uses atomics, which OpenCL offers only on integers, so HDR output is impossible this way (Alg. 2, p. 17).
- Two-pass accumulation writes every (position, direction) sample to private memory without synchronization, then runs one thread per output position over all directions (Alg. 3 and 4). It costs memory proportional to directions × samples; splitting directions into batches cuts memory and adds time (sec. 5.8). It needs coherent parallel ray bundles per direction so the accumulator can find a position's samples, and each ray knows its base address and offset (sec. 5.4, 5.7.2).
- Directions are spread on the sphere by a repulsion simulation and jittered by at most half the neighbour spacing; purely random directions bias the results (sec. 5.4.1-5.4.2).

## LSAO in the framework (sec. 3.3)

- `L(p) = ∫∫ L_i(p, ω)·(ω·n)` (eq. 3.2) becomes `L(p) = ∫ f(p, θ, n, o(p, θ)) dθ` with `o` the occluder information in direction θ (eq. 3.3), `f = V·W(|p − o_p|)` (eq. 3.4), `V = sin h(o) − sin t(θ, n)` from the largest occluder's elevation and the tangent angle (eq. 3.5), and `W(d) = R/(R + d²)` (eq. 3.6), which the thesis calls a slight modification of Timonen's falloff.
- The sweep starts at the border of the depth map and steps inward, updating the occluder information per step, with the amortized-constant structure of Timonen and Westerholm 2010.

## Applications

- **Diffusion inpainting (ch. 6):** the smoothness energy `∫(f_x² + f_y²)` is usually minimized by relaxation over four neighbours. The ray form is `I(p) = ∫ L(r(p, θ))·w(|p − r(p, θ)|) dθ`, where `r(p, θ)` is the nearest known pixel along the ray, so known pixels act as light sources that emit and block. The condenser keeps the last non-empty value seen; the accumulator adds `brightness·w(distance)` with two-pass accumulation. Light sources must already sit on a regular grid.
- **Inside-outside testing (ch. 7):** rays start on the bounding box, so outside, and flip an inside flag at each crossing found by brute-force Möller-Trumbore against all triangles. Each voxel packs two 16-bit counters (total and inside votes) in one 32-bit word through integer atomic adds of `2^16 + inside`, and is inside if more than half its votes say so.
- Signed distance fields (sec. 8.5) and line-sweep photon mapping (sec. 8.4.3) are sketched; in the photon sketch each direction is one parallel light, and scattering works only with direct accumulation.

## Timings

Core 2 Q9550, Radeon HD 7850 (2 GB), AMD APP SDK 3.0; medians of three runs of the kernels only (sec. 3.3.4).

| Task | Setting | Time |
|---|---|---|
| Line-sweep directional occlusion, depth 1024×436, hemisphere map 1024×256 | 16 directions, 2 px grid | 94 ms median (fastest 62 ms) |
| Same | 8 directions, 1.8 px grid | 47 ms |
| Same | four batches of two directions | 78 ms |
| Inpainting, 1155×866 | 128 directions, 1 px grid | 3,969 ms |
| Inpainting | 32 directions, 2 px grid | 188 ms |
| Inside-outside, 256³ voxels, no BVH | octahedron (8 triangles), 2,348,486 rays | 1,078 ms |
| Inside-outside | box with a hole (25 triangles), same rays | 2,109 ms |
| Inside-outside | octahedron, 12,543,424 rays | 7,375 ms |

Generating the rays on one CPU thread took 2,250 ms for 2.37 M rays and 25.5 s for 12.5 M; under 1 s in 2D but several seconds in 3D.

## Limitations and future work

- Sweep rays are not aligned with voxel centers, which leaves jagged edges (Fig. 7.7); snapping samples to the grid as in LSAO is the proposed fix.
- Noise rises sharply on open meshes, and two crossings close together at shared edges can count as one (Fig. 7.5, 7.6).
- Two-pass memory grows with directions × samples, and integer-only atomics rule out HDR in direct mode.
- Proposed: sequential writes in blocks of about 32 threads (after Timonen and Westerholm), an overhead analysis, and incremental rendering by pairing opposite directions.
