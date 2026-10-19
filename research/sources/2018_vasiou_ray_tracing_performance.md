# A Detailed Study of Ray Tracing Performance: Render Time and Energy Cost

| | |
|---|---|
| Authors | Elena Vasiou, Konstantin Shkurko, Agatha Mallett, Erik Brunvand, Cem Yuksel (as printed on the author copy) |
| Date | The Visual Computer (CGI 2018); DOI 10.1007/s00371-018-1532-8 |
| Kind | Paper (pre-copyedit author copy) and a figures-only supplement |
| Link | https://hwrt.cs.utah.edu/papers/rt_performance_CGI18.pdf ; supplement https://hwrt.cs.utah.edu/papers/rt_performance_CGI18_sup.pdf |

The paper breaks down where path tracing spends time and energy, by kernel, by hardware unit and by bounce. Dell'Ova cites it for the hypothesis that dense RC probes hit memory-bandwidth limits ([2025_dellova_rc_performance_scaling_thesis.md](2025_dellova_rc_performance_scaling_thesis.md)). Its claim is narrower: time and energy follow data movement, memory stalls and DRAM accesses dominate, and bandwidth is plotted (Fig. 6) but not used as the explanation. The results come from a cycle-accurate simulator of the TRaX architecture with USIMM for DRAM, not from a commercial GPU; the CPU comparison agrees only qualitatively (sec. 4.9).

## Setup (sec. 3)

- Simulated: 32 multiprocessors of 32 thread processors (1024 threads) at 1 GHz on 65 nm; four shared 512 KB L2 caches of 16 banks; 8-channel GDDR5 at 8 GHz effective, 512 GB/s peak; area and latency from Cacti 6.5 and Synopsys DesignWare.
- CPU reference: Core i7-5960X (8 cores, 20 MB L3), path tracing at 500 spp, final render times only.
- Scenes at 1024×1024 with 0 to 9 bounces, 50 simulations: Crytek Sponza (262K triangles), Dragon Box (870K), Hairball (2.9M), San Miguel (10.5M). BVH with first-child traversal, Lambertian shading, one point light.

## Findings (sec. 4)

- Time (Fig. 3): Sponza is mostly compute once it fits in L2, with memory stalls mostly from L1 misses; in San Miguel, from one bounce on, memory data stalls take about 65 % of the time. L1 hit rate drops from about 80 % for primary rays to about 60 % from two bounces on.
- Kernels (Fig. 4): generation and shading are negligible; trace dominates; shadow traces are about 20 % faster.
- Trace stalls (Fig. 5) are substantial from the first bounces and nearly constant past the second, which the authors put down to incoherent rays thrashing the caches. Because the simulated memory system is already generous, more banks or capacity alone would gain little.
- DRAM bandwidth (Fig. 6): small, fast scenes use more, large scenes spread requests out, and all converge toward similar use; no numbers in the text.
- Energy (Fig. 7): Sponza at 9 bounces spends 80 % on memory (60 % DRAM) and 1 to 2 % on compute; San Miguel 95 % on memory (80 % DRAM). A floating-point operation is about three orders of magnitude cheaper in energy than fetching its operand from DRAM.
- Shadow rays use about 15 % less energy than other rays; generation is at most 2 % (sec. 4.6). Energy per ray rises for incoherent secondary rays and levels off after about three bounces, with memory at 60 to 95 % of traversal energy (sec. 4.7).
- Most of the image comes from the first few bounces; past the fourth or fifth, cost is large next to the contribution (sec. 4.8).

## Conclusions and limits (sec. 5-6)

- Memory dominates energy and latency even for scenes that fit in cache; compression reduces the bottleneck without removing it; adding memory resources alone does not help, so the authors point to memory-system redesign and streaming (dual streaming).
- Shading is Lambertian without textures, and hardware sensitivity is future work.

## For RC

- RC's cascade traces are short and spatially coherent at low levels and long and incoherent at high levels, so the paper's coherence result predicts that upper cascades cost more per ray than their step count suggests (inference). Dell'Ova's dense-probe slowdown fits that reading but was not measured with counters.
