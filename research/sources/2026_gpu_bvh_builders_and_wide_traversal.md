# GPU BVH builders and wide-BVH traversal, measured

| | |
|---|---|
| H-PLOC | Benthin, Meister et al., "H-PLOC: Hierarchical Parallel Locally-Ordered Clustering for Bounding Volume Hierarchy Construction", ACM PACMCGIT 7(3), July 2024, DOI 10.1145/3675377, https://gpuopen.com/download/publications/HPLOC.pdf |
| CWBVH | Ylitie, Karras and Laine, "Efficient Incoherent Ray Traversal on GPUs Through Compressed Wide BVHs", HPG 2017, https://users.aalto.fi/~laines9/publications/ylitie2017hpg_paper.pdf |
| Wide against binary | Meister and Bittner, "Performance Comparison of Bounding Volume Hierarchies for GPU Ray Tracing", JCGT 11(4), 2022, https://jcgt.org/published/0011/04/01/paper.pdf |
| Aila and Laine | "Understanding the Efficiency of Ray Traversal on GPUs", HPG 2009, https://users.aalto.fi/~laines9/publications/aila2009hpg_paper.pdf |
| LBVH | Karras, "Maximizing Parallelism in the Construction of BVHs, Octrees, and k-d Trees", HPG 2012 (abstract only: https://diglib.eg.org/items/71edb707-2be1-4d84-8e25-9162cd9a59e9) |
| PLOC, PLOC++ | Meister and Bittner, IEEE TVCG 2018 (https://dcgi.felk.cvut.cz/projects/ploc/); Benthin et al., PACMCGIT 5(3), 2022 (search summary of https://diglib.eg.org/items/cf7c86c3-0fd6-4f26-a2da-a8b20808199c/full) |
| Treelet refinement | Karras and Aila, HPG 2013 (search summary of https://diglib.eg.org/handle/10.2312/14935) |
| RT cores on and off | University of Bristol, PMBS 2019 slides, https://www.dcs.warwick.ac.uk/pmbs/pmbs19/PMBS19/pres/paper3.pdf |
| Code | PLOC (CUDA driver API): https://github.com/meistdan/ploc; PLOC++ reference cited by H-PLOC: https://github.com/embree/embree/tree/ploc (repository licence Apache 2.0; whether the builder lies under it was not confirmed); HIP-BVH-Construction (MIT): https://github.com/Niravaana/HIP-BVH-Construction |
| Read | 2026-10-20. No source measures an RTX 2070 (TU106); the only Turing figures are for an RTX 2080 Ti. |

Published measurements of GPU BVH builds, of wide and compressed node layouts, and of software traversal against RT cores. Each number names its GPU, because they span five GPU generations and two vendors.

## Contents

- [Builders](#builders)
- [Build memory](#build-memory)
- [Wide and compressed nodes](#wide-and-compressed-nodes)
- [Memory per triangle](#memory-per-triangle)
- [Short rays](#short-rays)
- [Software traversal against RT cores](#software-traversal-against-rt-cores)
- [Code](#code)
- [Not found](#not-found)

## Builders

**H-PLOC**, measured on a Radeon RX 7900 XT with HIP on ROCm 5.7.3 (Table 1, total build time and throughput):

| Scene | Triangles | H-PLOC | PLOC++ | ATRBVH | LBVH | PRBVH |
|---|---|---|---|---|---|---|
| Powerplant | 12.7 M | 12.71 ms (1004 MTris/s) | 14.31 ms (892) | 35.23 ms (362) | 11.46 ms (1112) | 38,017 ms |
| San Miguel | 10 M | 11.45 ms (871) | 13.78 ms (724) | | 9.88 ms (1009) | |

- The abstract claims similar BVH quality "in just a single kernel launch" and 1.1 to 3.6 times lower build times than prior builders; Section 4.1 puts H-PLOC within 15% of LBVH's build time, 2.7 to 3.6 times faster than ATRBVH and 1.1 to 1.8 times faster than PLOC++.
- The paper's LBVH column is Apetrei's 2014 single-kernel variant. H-PLOC describes Karras 2012 as building the topology in one kernel but needing a second bottom-up pass to fit the boxes.
- Quality is measured against PRBVH (parallel reinsertion), not against a plain SAH build: BVH4 SAH cost relative to PRBVH is 1.09 on Sponza and 1.12 on Powerplant, and path-tracing time 1.11 (Sponza), 1.13 (Powerplant), 1.05 (Buddha) and 1.17 (San Miguel). ATRBVH, PLOC++ and H-PLOC all come within 1.04 to 1.12 of PRBVH.
- SAH is not the quality ceiling either: the 2022 JCGT comparison finds that SAH builds have higher costs on average than PLOC and ATRBVH.

**Other builders.**

- PLOC cut build times up to twofold against earlier GPU builders while tracing up to 17% faster (project page). PLOC++ is 1.9 to 2.3 times faster than PLOC (search summary).
- On a Radeon RX 6800 XT with HIP (JCGT 2022, Table 2), a binary build of Powerplant (12.76 M triangles) took 36.7 ms with LBVH, 129 ms with PLOC, 292 ms with ATRBVH and 5752 ms with PRBVH.
- Karras and Aila's treelet refinement improves an existing BVH at about 40 M triangles per second on a GTX Titan and reaches over 90% of SBVH's trace speed on average over 20 scenes (search summary).

**Derived.** H-PLOC builds at about 1.0 to 1.15 ms per million triangles on the RX 7900 XT, which extrapolates to about 11 to 12 ms for 10.8 M triangles on that GPU. On the RX 6800 XT, LBVH ran at about 2.9 ms and PLOC at about 10 ms per million triangles, with a different PLOC version from the H-PLOC table.

## Build memory

H-PLOC needs, for N primitives, 64-bit Morton codes (8 N bytes), parent IDs (4 N), cluster indices (4 N) and the binary BVH (64 N), and a cluster is 32 bytes (Section 3.3). N counts primitives after pairing triangles into quads, which cuts it by 20 to 50%, and most of these arrays can reuse the leaf data's memory.

**Derived.** About 80 bytes per paired primitive, so 430 to 690 MB of transient memory on top of the input for 10.8 M triangles paired into 5.4 to 8.6 M primitives.

## Wide and compressed nodes

**CWBVH**, measured in CUDA on GTX Titan X Pascal and Maxwell:

- An 80-byte node holds 8 children: a 15-byte quantization frame, 17 bytes of indexing, and 6 bytes per child (Figure 4).
- Against the binary Aila 2012 kernel, the geometric mean over scenes is 1.36× faster on Pascal for primary rays (bounce 0), 2.36× at bounce 1 and 2.70× at bounce 4; on Maxwell 1.33×, 2.24× and 2.51× (Tables 4 and 5). The abstract states 1.9 to 2.1 times for incoherent rays.
- The 15-scene baseline mean (Table 7) goes from 35.63 ray-node tests and 7.58 ray-triangle tests at bounce 0 to 38.48 and 11.93 at bounce 4.
- The traversal stack has 64-bit entries. Twelve entries (96 B per thread) fit in shared memory, and eight (64 B) give "virtually all of the benefits" (Section 4.1, Appendix A.3).
- The wide BVH was built on the CPU: about 6 minutes for a 10 M-triangle scene, about 80% of it in the binary build (Section 3.4).

**Wide nodes without compression** (Meister and Bittner, RX 6800 XT, HIP), trace speed relative to binary LBVH (Table 1):

| Rays | BF2 | BF4 | BF8 |
|---|---|---|---|
| Secondary, LBVH | 1.00 | 1.04 | 0.98 |
| Shadow, LBVH | 1.00 | 0.92 | 0.86 |
| Secondary, SBVH | 1.86 | 1.73 | 1.54 |

- Their k-ary nodes are uncompressed, 32 k bytes per node. The paper finds that trace speed "drops significantly" with the branching factor for secondary and shadow rays, and that node compression as in CWBVH would be needed, which the comparison leaves out.
- The drop is largest for primary rays, the most coherent; the paper leaves primary rays out as a small share of rendering time.
- Binary LBVH on Powerplant (12.76 M) traced secondary rays at about 53 MRays/s (Table 3).

**Aila and Laine 2009** (GTX 285, CUDA), on Sibenik (80 K triangles) with the persistent while-while kernel: 117.5 MRays/s primary, 113.4 ambient occlusion and 48.1 diffuse (Table 1). Its ambient occlusion rays are long, as its table caption notes.

## Memory per triangle

| Item | Bytes | Source |
|---|---|---|
| Uncompressed k-ary node | 32 k: 64 (BVH2), 128 (BVH4), 256 (BVH8) | JCGT 2022, Section 3 |
| CWBVH internal node | 80 for 8 children | Ylitie, Figure 4 |
| CWBVH structure without triangles | 8.63 B per triangle (Powerplant, 12.8 M), 8.10 (San Miguel, 10.5 M); 0.43 of the binary layout over all scenes | Ylitie, Table 6 |
| Binary Aila 2012 layout without triangles | 24.14 B per triangle (Powerplant) | Ylitie, Table 6 |
| Triangle | 48 B padded (three float3 and 12 spare bytes) | Ylitie, Section 3.3 |
| CWBVH traversal stack in tinybvh's OpenCL kernel | 24 entries of 8 B | `kernels/traverse_cwbvh.cl` |

**Derived, for 10.8 M triangles.** Triangles at 48 B take 518 MB, and a 12-byte index adds 130 MB. A CWBVH adds 88 to 93 MB, about 610 MB in all; a binary layout at 18.6 to 24.1 B per triangle adds 200 to 260 MB.

## Short rays

No source measures distance-limited rays in compute BVH traversal. The nearest evidence:

- CWBVH's gain over binary grows with incoherence, from bounce 0 to bounce 4, and its triangle tests grow faster than its node tests.
- The JCGT comparison finds wide uncompressed nodes hurt most for the most coherent rays.
- CWBVH leaves a shadow-ray traversal order out of scope, noting that one often pays off. Cycles stops shadow traversal at the first opaque hit (search summary of https://developer.blender.org/docs/features/cycles/bvh/).

## Software traversal against RT cores

The Bristol PMBS 2019 slides compare an RTX 2080 Ti with RT cores on and off against a GTX 1080 Ti, through OptiX at 15360×8640, one ray per thread, ray types not stated:

- With RT cores off the 2080 Ti traced about 2.5 to 3 G rays/s on Cube, Sphere, Happy Buddha and Dragon, and about 0.5 G on Hairball (read from bars).
- With them on, about 12.4 G rays/s on Buddha and Dragon and 6.4 G on Hairball.
- The slides state a 4.6× average speedup on Turing, 11.8× on Hairball, and "10 GigaRays/s on RT cores vs 1-2 GigaRays/s in CUDA on the same GPU". The Sphere is 89 K triangles on one slide and 82 K on the chart.

NVIDIA's own figures give about 10 G rays/s for the RTX 2080 Ti against 1.1 G for the GTX 1080 Ti (https://bit-tech.net/features/nvidias-turing-architecture-explained/5/).

**Derived.** The RTX 2070 has 36 SMs against the 2080 Ti's 68. Scaled by SM count, which ignores clocks and memory bandwidth, software traversal of simple scenes would reach about 1.3 to 1.6 G rays/s on it. The scaling is unmeasured.

## Code

- HIP-BVH-Construction implements H-PLOC, PLOC++, LBVH variants and an n-wide collapse in HIP. Its README gives H-PLOC builds of 0.5147 ms for the 150 K-triangle Bunny and 0.6133 ms for Sponza; its header names an RX 6800 and its footer a 6800W Pro.
- tinybvh's README cites "NexusBVH's CUDA code" for its H-PLOC builder; that repository was not found.
- No official H-PLOC code was found. PLOC's licence file starts by saying parts of the code fall under different licences, without the terms being checked.

## Not found

- A GPU builder that writes 80-byte CWBVH nodes; H-PLOC's single-kernel wide collapse writes uncompressed nodes.
- Measurements of GLSL CWBVH traversal, of software traversal on an RTX 2070, and of distance-limited rays.
