# Light transport and alternatives to RC

| | |
|---|---|
| Date | 2024-09 to 2026-10 |
| Kind | Collected implementation findings; claims are unverified unless a public link backs them |
| Related | [2026_tauray_rcpg_path_guiding.md](2026_tauray_rcpg_path_guiding.md), [2026_holographic_rc.md](2026_holographic_rc.md), [2026_sparse_and_3d_rc.md](2026_sparse_and_3d_rc.md), [../topics/related_techniques.md](../topics/related_techniques.md) |

This note covers methods that compete with RC or extend it beyond diffuse light: line sweeping, short characteristics, cellular automata and cone sweeping, transform-based solutions without occlusion, wave optics, extended gathering, caustics and refraction, multi-bounce, and RC used for path guiding. Most of it is 2D research; the parts with direct use in a 3D renderer are extended gathering, multi-bounce feedback and the guiding ideas.

## Line sweeping

- A sweep marches all parallel rays of one direction across the grid at once, so one march serves every pixel it passes and costs O(1) per pixel per direction. It needs only two columns of `N` directions in flight. Sweeps suit a uniform screen grid better than a BVH.
- **Measured:** 1000 directions at 1080p in 40 ms after removing modulo operations, which had used about 60 of 150 ALU instructions; on an M2 Pro, 1024 sweeps at 1080p took about 200 ms with modulo, 50 ms without and 27 ms at the highest GPU clock. A 13 ms budget allows about 325 directions. Dispatching one thread per row ran at 105 fps against 70 for columns.
- **With RC:** RC line sweeping was competitive with but slightly slower than a multi-level DDA. It was faster on higher cascades, while cascades 0 to 2 were better traced normally. Sweeps cannot use the nearest or bilinear fix because rays are not per probe; the parallax fix works. Skewed probe grids per direction avoid the parallax error of misaligned probes.
- **Volumetrics:** a sweep cannot stop at one interval length, so finite intervals need a stack of samples (about 600 MB estimated for 2× RC) or prefix sums of additive optical depth. Volumetric sweeps handle opaque geometry poorly.
- **In 3D:** bucket fragments by world-space line and sort along it, which gives the ray-march result with no extra memory; only the first hit matters. Sparse sweeps visit only non-empty voxels.
- **Sunlight:** a single sweep is faster than a second RC pass for a directional light.
- **Grid visibility recurrence** for a point source without volumetrics: `T·(x·r[x−1] + y·r[y−1])/(x + y)`, an O(N²) wave from the source with partial transmittance allowed and `1/r` applied separately ([article](https://towardsdatascience.com/a-quick-and-clear-look-at-grid-based-visibility-bf63769fbc78)). From O(N) boundary points this gives full GI in O(N³).
- Line-sweep ambient occlusion on height maps is O(1) per ray with infinite thickness ([LSAO](http://wili.cc/research/lsao/lsao.pdf)), and rasterizing slices into height maps was faster than a DDA.

## Short characteristics

Radiative-transfer codes solve the same problem with 45° diamond-shaped sweep fronts, one global write per pixel ([Kripke report](https://www.osti.gov/servlets/purl/1559411), [MURaM solver](https://github.com/NCAR/MURaM_main/blob/main/src/rt/rt.cc), [lecture](https://www.astro.uu.se/~piskunov/TEACHING/NUM_RT/nrt_lecture05.pdf)). Atomics are nearly free in a sweep when lines do enough other work. An uncascaded sweep wastes far-field work, and wide cones keep the direction count low.

## Cellular automata and cone sweeping

- **Cone sweeping:** the endpoints of a 45° cone move one pixel per step, which makes it an O(1) per pixel cellular automaton. Cascade 0 tracks one occluder per pixel, cascade 1 two, cascade 2 four ([angular falloff](https://www.shadertoy.com/view/7c2XDw), [Gaussian penumbras](https://www.shadertoy.com/view/7f2SzV), [frustum sweep](https://www.shadertoy.com/view/fld3R4)). A swept-light demo took 481 ms on Iris Xe and 78 ms on an RTX A2000 ([demo](https://swept-radiance.pages.dev/)).
- **Diffusion automaton:** `p[x+1, y] = 0.8·p[x, y] + 0.1·p[x, y−1] + 0.1·p[x, y+1]` gives penumbras; repeated convolution converges to a Gaussian.
- Cellular-automaton GI implementations checked stored only 4 to 6 angles, which is not conservative and leaks where steep cone borders skip tiles. Voxel versions with 2-bit directions give 90° shadows ([video](https://youtu.be/wVkhP67P2sk?si=lU0rayMB7kyutOd8)).

## Solutions without occlusion

- Without occlusion, 2D GI is one convolution of the emission with a `1/r` kernel, exact with an FFT in O(n log n); RC is also O(n log n) but not exact. Accurate AO is therefore most of the GI problem.
- The same result is `DualRadon(Radon(sources))` by the projection-slice theorem ([prototype](https://www.shadertoy.com/view/fXfXRS)). A naive O(N³) transform ran in real time on Shadertoy; the inverse dual Radon took about 5 s in Mathematica against a 5 ms target. FFT periodicity causes lens-flare artifacts, so pad with zeros. Sinograms can hold off-screen sources.
- An FFT Poisson solve cannot take internal barriers, and occlusion is nonlinear, so no transform encodes it exactly. Analytic conformal maps give exact unoccluded fluence (a line light is `ln((z − p)/(z − q))`), but continuing it from a boundary is ill-conditioned ([demo](https://www.shadertoy.com/view/7cBGDK)).
- A line light contributes `cos θ/r`, not a sum of point lights, and a finite source falls off as `atan(d/r)/π`.

## Wave optics

- Wave-based GI scales as N² log N in 2D with an FFT, and N³ log N is not enough in 3D, where cost should follow surface area. Sharp shadows need tiny wavelengths. A 2D point source is a Hankel function; the infinite-wavelength limit is the Poisson problem.
- **Wave Cascades**, a wave-optics extension of RC for Lorenz–Mie scattering and diffraction, computed a fully spectral Mie lookup table in real time and sampled it with a 64³ equal-angle HRC.

## Extended gathering

- Hits in one direction are spread to neighboring probe cones with a constant-width ramp, since all hits fall in a known distance interval: `L(P, d) = lerp(L(A, d_i), L(B, d_{i+1}), α)` with `A = P + d·r − d_i·r`. Each gathered direction uses its own interpolated source position, and with 4× scaling the probe count per cascade stays the same. It needs spatial resolution above angular resolution and smears only across the propagation direction, so occlusion along the cone survives ([plane and ring variants](https://www.shadertoy.com/view/NfVXRc), [ring probe selection](https://www.shadertoy.com/view/sfVSzd)).
- Longer intervals cut spatial error at a fixed ray count while the gather compensates angular error; pick interval scaling so the two errors match.
- With analytic ray splitting, 2×2 extended gathering and 2×2 dithered jitter, it acts as a ray multiplier, and a 2×2 radius keeps contact shadows. World-space probes suited it better than screen probes; in screen space, interval length should make probes project to the same radius.

## Resampling view of RC

- Extensions (N probes and M directions to N/2 probes and 2M directions) and merges (to 2N probes and M/2 directions) are both reinterpolations of a radiance field. Resampling by integrating over each target's footprint, a trapezoid in line space, beat point sampling; stripe artifacts were fixed by oversampling a cascade. Lossless reinterpolation needs probe spacing to double per cascade.
- Primal and dual RC both capture radiance on a plane and rebuild it elsewhere; they alias only when the source or the receiver lies on the capture line.

## Caustics and refraction

- **Refractive cascades** in vanilla RC refract each interval at the boundary and continue tracing for the rest of its length, with a bilinear fix before and after refraction. Starting intervals at probe centers made bent merge lookups more sensible. Residual artifacts remained, and changing cascade 0 settings made earlier good results unphysical, which suggests luck in convergence. Merging rotates the upper probes by the lower probe's deflection ([Shadertoy port](https://www.shadertoy.com/view/f3d3R8)); 4 to 8 refraction bounces looked identical.
- **Equal-angle HRC** gives each frustum equal width in radians instead of equal slope spacing, which removes HRC crosses; one 2D build ran in 1.05 ms on an RTX 5090. Refraction across quadrant boundaries remained the error source, and ring HRC was judged better suited because bent rays break frustums.
- **3D:** dense equal-angle HRC with dispersion and Fresnel reflection, compared against 4k spp spectral path tracing, was called the first 3D RC caustics. Memory is the limit: 128³ took about 9 GiB through Vulkan, since WebGPU cannot allocate that much, and 32³ ran in 40 ms without accumulation on an RTX 4070 Ti Super. An adaptive topology that splits rays per cell by an error estimate, bounded to 1 to 2× splits, cleaned up a refractive sphere, but its memory was too high.
- Off-screen radiance for refraction needs adaptive, bounded allocation, and no conservative metric for lensing is known, so it does not look scalable in 3D.
- **Limits:** scattering doubles rays at every split, so cascades lose their constant size; caustics also break the angular-spatial trade-off that lets cascade 0 manage with 4 directions. HRC caustics in 2D were poor.
- **2D forward light tracing:** a uniform grid cut the ray-tracing pass from 165 ms to 3.5 ms. Uniform hemisphere sampling did better than cosine-weighted sampling for forward tracing in 2D, though metrics disagreed (FLIP mean 0.112 against 0.100). Most variance comes from rasterizing random lines, so stratifying lines matters more than better paths; Owen-scrambled Sobol cost about 8% more per path than white noise.

## Multi-bounce

- **Feedback:** feed last frame's radiance times albedo back as emission. Without a transmittance bound it explodes: one 256² test went from 65 to 5700 at albedo 0.9. Closed reflective boxes need decay or a reset of the temporal input. Emission should count only on the first bounce, and splitting floors and walls into two layers stabilized one build. Albedo 0.5 sums to twice the direct light after infinite bounces.
- **Without temporal lag:** stored ray hit distances allow `N` bounces in one frame without recasting rays, for opaque scenes. Bounces can also run as separate RC iterations, with Jacobi iteration or Anderson acceleration to converge faster.
- Path of Exile 2 shipped one extra indirect bounce for directly lit objects. One game found 3D RC too slow and used a two-bounce method instead.

## Guiding and next-event estimation

- **RC-guided NEE:** at each level, pick one of the four next-cascade cones by brightness, then trace inside the chosen cone, with a small uniform term. This resembles the published RC path guiding (see [2026_tauray_rcpg_path_guiding.md](2026_tauray_rcpg_path_guiding.md)).
- A light tree over emissive triangles built in under 0.5 ms for 10k to 100k triangles on an RTX 3090 with O(log N) sampling ([PBRT light BVH](https://pbr-book.org/4ed/Light_Sources/Light_Sampling#BVHLightSampling)). About 70% of Path of Exile 2 shaders are emissive effects, so screen-space emissive pixels are the simplest light source there.
- RC wants many rays, while resampling methods want a few good ones, which is a tension in combining them.

## Other uses

- **Diffusion and Laplace solving** with HRC (see [2026_holographic_rc.md](2026_holographic_rc.md)), and cascades for pathfinding connectivity: an N³ build and log N queries against N⁴ for A*.
- **Radiative heat transfer** follows the same transport equation; thermal infrared suits RC because everything emits.
- **Audio attenuation**, **fog of war** (one channel per faction) and **spectral rendering** with one wavelength or a batch of four per frame were prototyped.

## Links

- Line-sweeping thesis: https://www.pdf.inf.usi.ch/papers/master_thesis/ConstantinBerhard.pdf
- Line-sweep demos: https://www.shadertoy.com/view/XXXyWM and https://compute.toys/view/1418
- Cellular-automaton light reference video: https://www.youtube.com/watch?v=nNJG2GAHsQk
- Projection-slice theorem: https://en.wikipedia.org/wiki/Projection-slice_theorem
- Limited-angle tomographic reconstruction: https://arxiv.org/abs/2502.12293v1
- Hologram propagation demo: https://radiance-cascades.github.io/LegitScriptEditor/?gh=Raikiri/LegitCascades/HologramPropagation.ls
- Lumigraph and light field papers behind HRC's discretization: https://cseweb.ucsd.edu/~ravir/6160/papers/p43-gortler.pdf and https://graphics.stanford.edu/papers/light/
- Refraction ANGLE fix: https://www.shadertoy.com/view/NfySzt
- Temporal multi-bounce transport paper: https://www.sciencedirect.com/science/article/pii/S0022407326000142
- Radiance caching for participating media: https://cs.dartmouth.edu/~wjarosz/publications/jarosz08radiance.pdf
- Spectral sky with a SIMD trick: https://fgarlin.com/blog/spectral-sky/
- Texture-space quad patches for surface probes: https://arxiv.org/abs/1905.09097
- Horizon maps for isometric terrain: https://www.shadertoy.com/view/sXcGRB
