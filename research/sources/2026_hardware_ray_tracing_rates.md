# Hardware ray tracing on Turing: measured rates and practice

| | |
|---|---|
| Sanzharov et al. 2019 | Sanzharov, Gorbonosov, Frolov and Voloboy, "Examination of the Nvidia RTX", CEUR-WS Vol-2485, paper 3, https://ceur-ws.org/Vol-2485/paper3.pdf |
| Meister et al. 2025 | Meister, Bokšanský, Guthe and Bittner, "On Ray Reordering Techniques for Faster GPU Ray Tracing", arXiv 2506.11273, https://arxiv.org/html/2506.11273 |
| Salmon and McIntosh-Smith 2019 | OpenMC on RT cores, PMBS19 slides, https://www.dcs.warwick.ac.uk/pmbs/pmbs19/PMBS19/pres/paper3.pdf |
| NVIDIA | [Best Practices for Using NVIDIA RTX Ray Tracing (Updated)](https://developer.nvidia.com/blog/best-practices-for-using-nvidia-rtx-ray-tracing-updated/), 2022-07-25; [Tips: Acceleration Structure Compaction](https://developer.nvidia.com/blog/tips-acceleration-structure-compaction), 2021-05-21; [developer forum on gigarays](https://forums.developer.nvidia.com/t/what-is-the-performance-of-the-rtx-4090-measured-in-gigarays/358704), 2026-01 |
| Inline against pipeline | [Microsoft, DXR 1.1](https://devblogs.microsoft.com/directx/dxr-1-1/), 2019-11-06; [Evolve, inline vs pipeline ray tracing](https://www.evolvebenchmark.com/blog-posts/inline-vs-pipeline-ray-tracing), 2025-11-06; [Vulkan guide, ray tracing](https://docs.vulkan.org/guide/latest/extensions/ray_tracing.html); [Arm, ray traversal](https://learn.arm.com/learning-paths/mobile-graphics-and-gaming/ray_tracing/rt03_ray_traversal/); [Gcores on Lumen](https://www.gcores.com/articles/187939) (Chinese) |

Measured ray rates on NVIDIA's first RT-core generation, the comparison of inline ray queries with ray tracing pipelines, and the vendor's practice notes with whatever measured effect they have. No public measurement compares inline ray queries with pipelines on a Turing GPU, and none gives ambient occlusion rays on Turing.

## Contents

- [RTX 2070: pipelines against a software BVH](#rtx-2070-pipelines-against-a-software-bvh)
- [RTX 2080 Ti: incoherent bounces and shadow rays](#rtx-2080-ti-incoherent-bounces-and-shadow-rays)
- [RTX 2080 Ti: RT cores against CUDA](#rtx-2080-ti-rt-cores-against-cuda)
- [Vendor figures](#vendor-figures)
- [Inline ray queries against pipelines](#inline-ray-queries-against-pipelines)
- [Practice and its measured effect](#practice-and-its-measured-effect)
- [Not found](#not-found)

## RTX 2070: pipelines against a software BVH

Sanzharov et al. render 1024×1024 at one sample per pixel and compute rays as width × height × samples × frames per second from the time logged in `vkCmdTraceRaysNV` or `DispatchRays`. Table 1, M rays/s, primary / secondary / tertiary:

| Scene | impl_1: Vulkan, raygen loop over `vkCmdTraceRaysNV` | impl_2: DX12, raygen spawns primary rays and closest-hit the rest | Hydra software BVH4 kernel (`BVH4TraversalInstKernel`) |
|---|---|---|---|
| Sponza, 66 K triangles | 807 / 437 / 806 | 928 / 777 / 694 | 480 / 122 / 130 |
| Crytek Sponza, 262 K | 806 / 419 / 388 | 754 / 635 / 216 | 276 / 92 / 80 |
| Hairballs, 224 M | 275 / 223 / 256 | 567 / 155 / 141 | 61 / 50 / 56 |

- **The text's figures differ from Table 1's hardware rows.** Section 3 quotes Sponza's coherent sorted primary rays at "477 vs 1140" and incoherent rays at "122 vs 561", and Hairballs' primary rays at "58 vs 283" and secondary at "50 vs 210". Read as software against hardware, that is 2.4× on coherent and 4.6× on incoherent rays in Sponza, and 4.9× and 4.2× in Hairballs.
- The authors call the hardware path "primarily aimed at accelerating random access to memory": its secondary rate in Sponza drops little from its primary rate (928 to 777 for impl_2), while the software kernel drops from 480 to 122.
- **Shader structure alone moves the rate up to 2×** on the same GPU: Hairballs' primary rays run at 275 in impl_1 and 567 in impl_2. The authors attribute this to "occupancy drop depending on code complexity and register pressure", an explanation, not a register measurement.

## RTX 2080 Ti: incoherent bounces and shadow rays

Meister et al. run a wavefront path tracer at 1920×1080 with 8 samples per pixel and 2 shadow rays per bounce, through DX12 and OptiX 7. Table 1, unsorted DX12, M rays/s, secondary (incoherent bounce) / shadow:

| Scene | Triangles | Secondary | Shadow |
|---|---|---|---|
| Crytek Sponza | 262 K | 1,755 | 3,113 |
| Pub | 281 K | 2,228 | 3,651 |
| Resort | 376 K | 1,904 | 4,119 |
| Living room | 580 K | 2,355 | 4,345 |
| Salle de Bain | 1,220 K | 2,436 | 4,123 |
| Breakfast | 1,347 K | 1,086 | 2,347 |
| Bistro | 2,833 K | 655 | 1,805 |

- Secondary rays span 0.66 to 2.44 G rays/s and shadow rays 1.81 to 4.35 G rays/s across the scenes. Figure 1 gives 2,355, 3,593 and 3,914 M rays/s for 64 consecutive third-bounce rays unsorted, partly sorted and sorted. The OptiX column of Table 1 was not read.
- **Ray reordering** speeds the trace itself by 1.4 to 2.0× (DX12) and 1.3 to 1.9× (OptiX), per the conclusion. In Table 2 (Bistro, OptiX) the sort costs 1.43 to 1.59 ms for block-local sorting and 3.66 ms device-wide, while the secondary trace saves about 0.07 ms and about 1.0 ms (derived from the table). The authors "were not able to recover the sorting overhead": a net loss in these measurements.

## RTX 2080 Ti: RT cores against CUDA

Salmon and McIntosh-Smith trace meshes of 12 to over 7 million triangles with OptiX, "each thread handles a single ray", ray type not stated but described like camera rays (slides 13 and 14). RT cores ran "4.6X" faster than CUDA traversal on the same GPU on average, 11.8× on the hairball, and reached "over 12 GigaRays/sec for the Happy Buddha and Asian Dragon models". Slide 16 names the RTX 2080 Ti as the Turing GPU.

## Vendor figures

These are ratings and forum statements, not measurements.

- NVIDIA rated the RTX 2080 Ti at 10 G rays/s against 1.1 for the GTX 1080 Ti (marketing, as quoted on the Bristol slide 13). A Tom's Hardware review reportedly calls the figures a geometric mean over several workloads rather than a peak; that review was seen only in a search summary.
- On NVIDIA's developer forum (2026-01), dhart writes that "there are no published gigarays numbers since Turing", puts the theoretical ceiling "higher than 10 gigarays/sec on Turing" while "no real applications can achieve it", and suggests measuring triangle intersection only, with no shading, depth-only output and enough rays to fill the GPU. Another NVIDIA forum reply, thread not identified, says Turing reaches about 10 G rays/s only with built-in triangles, very coherent rays, no any-hit shaders and very simple shading.
- The RTX 2070 has 36 RT cores and the RTX 2080 Ti 68 (spec-sheet counts, no source read).

## Inline ray queries against pipelines

- **Evolve** (Manon Oomen) measured both modes on an RTX 5070 Ti (Blackwell), an RX 9070 XT and an Arc B580: NVIDIA and Intel showed "no major performance differences", while on the RX 9070 XT "pipeline ray tracing performs much better than inline". The numbers are only in a chart image. The authors guess, unconfirmed, that AMD compiles all pipeline shaders into one large shader.
- **Microsoft's DXR 1.1 post:** inline tracing "might run better" with "very minimal shading complexity and/or very few shaders", and dynamic shaders suit "many complex shaders". A RayQuery object has "a relatively large state footprint". Intersection and any-hit shaders cannot call TraceRay. The advice is to "test real content". No numbers.
- **NVIDIA's best practices:** use `DispatchRays` or `vkCmdTraceRaysKHR` "when multiple different shading models are required"; with inline tracing, "complex user code may limit occupancy sooner than usually", so "monitor the register consumption of the query objects". No numbers.
- **The Vulkan guide:** ray queries restrict "the range of optimizations that a Vulkan implementation might apply to the scheduling and tracing of rays". No numbers.
- **Arm** (mobile GPUs): ray queries "usually perform better in simple examples". **Gcores**, on Lumen: inline tracing gives "an objective speedup" on unnamed consoles, no numbers, and Lumen on PC favours DXR 1.1 syntax.
- A GameDev.net claim that ray queries bypass shader execution reordering does not apply to Turing, since reordering exists only from Ada on.

## Practice and its measured effect

From NVIDIA's best practices and compaction posts unless named otherwise. Ray reordering (above) is the only practice with a measured effect on Turing.

- **Opaque geometry and any-hit:** "Flag geometries or instances as opaque whenever possible"; "the cost of any-hit shaders can have a significant effect on overall performance"; "minimize the non-opaque area when possible". No Turing cost in ms.
- **Terminate on first hit** is "a simple and efficient optimization" for shadow rays; Arm says the same. Neither gives a number.
- **Build flags:** static BLASes prefer fast trace; the TLAS prefers fast trace and is only rebuilt; dynamic BLASes choose by test, and "in extreme cases, using the PREFER_FAST_BUILD flag results in better overall ray-trace performance". Arm recommends fast build for the TLAS instead. No ms deltas.
- **Compaction** "reduces the memory footprint for a bottom-level acceleration structure (BLAS) by at least 50%" in some games, a memory figure; the post's text claims no speed-up.
- **One BLAS or many:** "Tracing performance against a BLAS doesn't depend on the number of geometries in it." Split BLASes with much empty box space and merge ones whose instance boxes overlap a lot. "Including the entire scene in the TLAS is not optimal"; cull instances with an expanded frustum and a shorter range. No numbers.
- **Thread groups for inline tracing in compute:** "Consider thread group size 8x8 or larger"; with 32-wide waves, "using thread groups with only one wave limits the thread occupancy", so "a practical choice for group size could then be 16×8 threads", and "the optimal size may be different for different hardware generations". Sorting rays inside compute thread groups is recommended but unmeasured.
- **Registers:** "Keep the ray payload small", "minimize live state across ray-trace calls", and "the full register capacity of the GPU is not available for any-hit shaders". No register counts.

## Not found

- Ambient occlusion rays measured on any Turing GPU; diffuse rays exist only as the path tracers' secondary rows above.
- Primary or coherent ray rates on the RTX 2080 or 2080 Ti beyond Bristol's mesh benchmark.
- Any measured comparison of inline and pipeline tracing on Turing.
- The cost in ms of an any-hit alpha test, the saving of terminate-on-first-hit, or build-flag timing deltas on Turing. A 2026 LiDAR paper ([arXiv 2605.10457](https://arxiv.org/pdf/2605.10457)) tabulates OptiX fast-trace against fast-build times; its values were not read.
- Chaos's article on profiling NVIDIA RTX cards, whose link redirects to the company's home page, and Evolve's per-scene numbers.
