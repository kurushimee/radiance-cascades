# Sweep solvers for radiative transfer and grid visibility

| Source | Author | Date | Link |
|---|---|---|---|
| Porting 3D Discrete Ordinates Sweep Algorithm in Ardra to CUDA (LLNL-CONF-773204) | A. Kunen et al. | 2019, M&C | https://www.osti.gov/servlets/purl/1559411 (archived copy used) |
| Kripke mini-app paper (LLNL-CONF-675389) | A. J. Kunen, T. S. Bailey, P. N. Brown | 2015, ANS M&C | https://www.osti.gov/servlets/purl/1229802 (archived copy used) |
| MURaM radiative transfer solver, `src/rt/rt.cc` | NCAR | read on `main` in 2026-10 | https://github.com/NCAR/MURaM_main/blob/main/src/rt/rt.cc |
| Numerical radiative transfer, lecture 5 (short characteristics) | N. Piskunov | course slides | https://www.astro.uu.se/~piskunov/TEACHING/NUM_RT/nrt_lecture05.pdf |
| A Quick and Clear Look at Grid-Based Visibility | R. Goldstein | 2023-05-12 | https://towardsdatascience.com/a-quick-and-clear-look-at-grid-based-visibility-bf63769fbc78 |
| Line Sweeping Example (compute.toys 1418) | fadaaszhi | unlisted demo | https://compute.toys/view/1418 |

These sources are linked from RC discussions of line sweeping as a way to trace many parallel rays at once ([light transport alternatives](2026_light_transport_alternatives.md)). They show three ways to parallelize a sweep: hyperplane wavefronts that start at a corner (Ardra, Kripke, and the anti-diagonals of the grid-visibility recurrence); planes swept in order with parallel work inside each plane (MURaM); and one independent thread per ray with atomic accumulation (compute.toys 1418, [LSAO](2013_timonen_line_sweep_ambient_obscurance.md), [Berhard](2016_berhard_gpu_line_sweeping_thesis.md)). None of them describes a 45° sweep by name or compares with RC.

## Contents

- [Ardra on CUDA (OSTI 1559411)](#ardra-on-cuda-osti-1559411)
- [Kripke (2015)](#kripke-2015)
- [MURaM short characteristics (`rt.cc`)](#muram-short-characteristics-rtcc)
- [Short characteristics lecture (Piskunov)](#short-characteristics-lecture-piskunov)
- [Grid-based visibility (Goldstein)](#grid-based-visibility-goldstein)
- [compute.toys 1418](#computetoys-1418)

## Ardra on CUDA (OSTI 1559411)

The link labelled "Kripke report" in the RC discussions resolves to this paper.

- Diamond-difference zone equations (eqs. 3-7): `C = σ_t/2 + μ_d/Δx + η_d/Δy + ξ_d/Δz`, `Ψ = (1/C)·[(μ_d/Δx)·Ψ_x,in + (η_d/Δy)·Ψ_y,in + (ξ_d/Δz)·Ψ_z,in + ½Q]`, and outflow `Ψ_x,out = 2Ψ − Ψ_x,in`, likewise in y and z.
- A zone-by-zone sweep has no parallelism. Zones on one hyperplane depend only on the previous hyperplane, so wavefronts start at the upwind corner, with at most N² parallel zones on an N³ grid. Across MPI ranks, wavefronts from different directions can collide at a node and are handled in message-arrival order.
- Performance model: `T_iter = T_rhs + T_sweep`, `T_rhs = A + B·log P`, `S = P_x + P_y + P_z − 3 + M` stages, `T_bw = G·(Z/P)^(2/3)/BW`, `T_sweep = S·(T_comp + 3(T_bw + T_lat))`, refined with the fraction `C` of rank faces that communicate (eqs. 8-12).
- GPU sweep on a V100: register pressure limits the kernel to about 400 threads per block. Tiling x and y into 20×20 zones gives 20×20×N "pencils" with parallelism 400 at any N and 20 stages of ramp-up and ramp-down. Each thread owns one (x, y) column and sweeps z in order, keeping z-face fluxes in registers and exchanging x and y faces through shared memory ("Flux Registers Sweep", after Rennich's CUDA Kripke). Each energy group is a CUDA block.
- The same RAJA source runs on CPU with 1×1×N pencils and on GPU with 20×20×N.
- Benchmark: Jezebel k-eigenvalue problem, 48 groups, S8, P4 scattering, 50³ zones per rank, up to 4096 Sierra nodes (2 POWER9 + 4 V100) and 64 CTS-1 nodes (2× 18-core Broadwell). Measured latency and bandwidth: CTS-1 2.1 µs and 5.1 GB/s, Sierra 61 µs and 9.5 GB/s. Fitted: CTS-1 A = 1.065 s, B = 0.237 s, T_comp = 0.00251 s; Sierra A = 0.102 s, B = 0.00194 s, T_comp = 0.00178 s. CTS-1 matched only with bandwidth divided by 36, blamed on network contention. Single-node throughput: 2.75e8 (CTS-1) and 7.32e9 (Sierra) unknowns per second per iteration, 26.1×.
- Diamond difference is memory-bandwidth bound, and Sierra's latency blocks the gain from 4-way spatial overloading.

## Kripke (2015)

- Steady-state 3D Boltzmann transport with diamond-difference space discretization, `Hψ = L⁺Σ_s Lψ + Q` (eq. 2). A sweep inverts `H`, which is block-diagonal in groups and directions, with one wavefront per direction from each of the 8 corners.
- Group sets are swept in sequence and direction sets are pipelined through the MPI sweep. Six data nestings (DGZ, DZG, GDZ, GZD, ZDG, ZGD) give 18 kernels.
- On a 16-core Sandy Bridge node (64 groups, 96 directions, P4, 12³ zones per core, 10 iterations), 252 layout variants ran from 2 to 51 s, and the best took about 60 % of Ardra's layout time. GZD was usually best, but the ranking changed with architecture and scattering order.
- Weak scaling reached 32,768 BG/Q cores.

## MURaM short characteristics (`rt.cc`)

The solar MHD code solves radiative transfer with short characteristics per cell in 3D, and long characteristics only along vertical columns for optical depth and the top-boundary intensity. Line numbers refer to `rt.cc`; the opacity tables and transposes were not read line by line.

- Directions: Carlson sets with 3, 6 or 10 directions per octant from `carlson{NMU}.dat`, swept over all 8 octants (lines 278-296, 1145-1151).
- Each direction picks a base face: with `aM_i = Δ_i/μ_i`, the axis with the smallest `aM` (lines 417-431). The step is `Δ_base/μ_base`.
- The upwind point lies on the base face, interpolated bilinearly from 4 neighbours with weights `(1 − r1)(1 − r2)`, `r2(1 − r1)`, `r1(1 − r2)`, `r1·r2`, where `r1` and `r2` are ratios of the `aM` values (lines 433-438). Density, opacity and source are interpolated with the same weights.
- Optical depth from the upwind point: `dt = (ds/3)·(κ_u ρ_u + κ_0 ρ_0) + (ds/6)·(κ_0 ρ_u + κ_u ρ_0)`, the exact integral of two linear profiles (lines 2135, 2172).
- Source term: `e = exp(−dt)`, `w0 = 1 − e`, `w1 = w0 − dt·e`, `η = S_0·(w0 − w1/dt) + S_u·(w1/dt)`, the exact integral for a source linear between the two points. Small `dt` uses series (`w0 = dt − dt²/2 + dt³/6`, `w1 = dt²/2 − dt³/3`), and very small `dt` passes the upwind intensity through unchanged. Update: `I = I_upw·e + η`.
- Sweep order: planes along the base axis run in sequence (`acc loop seq`), with gangs and vectors over the two transverse indices; z sweeps use transposed copies so z is the outer loop (lines 1893-2024).
- Each (octant, direction) repeats read boundary, integrate, write boundary, exchange halos until the relative boundary change is below a threshold, reduced across ranks with MPI max. Within a rank the sweep is exact for its inflow, and coupling across ranks behaves like block Jacobi.
- Accumulation: `J += (w/8)·I` and `F_z += (π/2)·sign·w·μ_z·I`. The heating term mixes the mean-intensity form and the flux-divergence form with weight `exp(−10·τ)`, so the first dominates where thin and the second where thick.
- OpenACC throughout, MPI for domains; no timings or accuracy figures in the file.

## Short characteristics lecture (Piskunov)

- Long characteristics run boundary to boundary and give both directions, which is expensive in 2D and 3D when rays do not follow the grid. Short characteristics cross one cell at a time on the grid, are fast, need two-direction integration for the mean intensity, and suffer numerical "light defocusing" (slides 9-12).
- Formal solution over a cell: `I(τ_{i+1}) = I(τ_i)·e^(−Δ) + ∫ S(t)·e^(−(τ_{i+1} − t)) dt`. With a linear source, `η = S_i·[1 − (1 + Δ)e^(−Δ)]/Δ + S_{i+1}·[Δ − 1 + e^(−Δ)]/Δ`, which matches MURaM's form (derived; the slide does not write it). Quadratic sources are more accurate but can go negative; Bézier sources (de la Cruz Rodríguez and Piskunov 2013) are more robust (slide 24).
- The Hermitian scheme (Bellot Rubio et al. 1998) uses `I_{i+1} = I_i + (δ/2)(I'_i + I'_{i+1}) + (δ²/12)(I''_i − I''_{i+1})` with `I' = α(I − S)` (slide 22).
- Errors against a Runge-Kutta reference (slide 26): Feautrier 0.45 %, DELO linear 0.26 %, DELO parabolic 0.16 %, Hermitian 1.46 %.
- A formal solver must iterate when source and opacity depend on the radiation field.

## Grid-based visibility (Goldstein)

- With the viewpoint in a corner, `V(x, y) ← V(x, y)·[x·V(x − 1, y) + y·V(x, y − 1)]/(x + y)` over a grid of 1 (free) and 0 (blocked), visiting cells in raster order; scores above 0.5 count as visible. An arbitrary viewpoint runs the recurrence once per quadrant on the four flipped sub-grids.
- The result is approximate, with blurred shadow edges and misclassified cells near them. Refinement sharpens shadows, and the scores converge to the exact answer as spacing goes to zero (Kao and Tsai 2008). Obstacles must span several cells to cast reasonable shadows.
- Larger neighbourhoods apply the update within cones between integer vectors: 8 neighbours use [1,1] with [1,0] and [0,1]; 16 neighbours add [2,1] and [1,2].
- The score equals the number of unblocked shortest grid paths from the viewpoint divided by the unblocked count, a binomial coefficient (Goldstein et al. 2022, JAIR 74).
- Each cell reads its already-updated left and upper neighbours, so cells on one anti-diagonal are independent: the same hyperplane parallelism as Ardra's sweep (derived).

## compute.toys 1418

- A WGSL demo with a 256×256 storage buffer of `atomic<u32>`. One dispatch of 256 threads each launches one line from an upwind boundary cell; the direction is normalized so the major axis advances exactly 1 per step (`d = (cos a, sin a)/max(|cos a|, |sin a|)`), and the edge used depends on which of four 90° sectors the angle falls in.
- Each line adds 1 at `o + round(d·i)` for 256 steps, wrapping on a torus, so the buffer ends with the number of lines crossing each cell. The image pass shows 0 as black, 1 as white and 2 or more as red, and resets each cell with `atomicExchange`.
- It is a discrete parallel-line projection with integer atomics, the one-thread-per-ray scheme with direct accumulation, not a light-transport solver.
