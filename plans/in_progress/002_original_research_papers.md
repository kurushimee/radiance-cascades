---
id: 002
title: Original research papers on radiance cascades
status: in_progress
created: 2026-10-20
updated: 2026-10-20
---

# Original research papers on radiance cascades

Three papers in `papers/` address the gaps where the published record of radiance cascades ends: an error model with an exact flatland reference, merging in 3D probe grids measured against a reference, and several bounces within one frame. Each paper has derivations backed by assert scripts, seeded experiments that regenerate its figures and tables, a Pandoc Markdown source and a built `paper.pdf` in a conventional `acmart` layout. The papers are written about radiance cascades in general, with no mention of this project. Once a paper is committed, `research/` takes it in like any other source: a concise source note, its facts in the topics that own them, and entries in the indexes and the README that point at both.

## Phases

### 1. Scaffold

Done when a one-page stub with a citation, an equation, a figure and a cross-reference builds to PDF with no warnings, and `papers/README.md` and the `CLAUDE.md` pointer exist.

- [x] `papers/` skeleton, `.gdignore`, uv project with numpy, scipy, matplotlib
- [x] Pandoc, pandoc-crossref and MiKTeX installed
- [x] LaTeX template and `build.py` proven on a stub
- [x] `papers/README.md` and the `CLAUDE.md` "Papers" section

### 2. Paper 1: where the error of radiance cascades comes from

Done when `selftest.py`, every check and every experiment pass, and the PDF is built, read page by page and committed.

- [x] Novelty check
- [x] Exact flatland oracle and the RC simulator with switchable stages
- [x] Derivations and checks
- [x] Experiments and figures
- [x] Prose, bibliography, PDF
- [x] Review, rerun, commit
- [x] Source note, topics, indexes and README in `research/`

### 3. Paper 2: merging in 3D probe grids

Done as for paper 1. Proposals: a depth-reprojected merge, which reads each parent toward the hit point estimated from the parents' stored merged depth, and a self test, which drops a parent when the lower probe's own ray toward the start of that parent's ray stops short of it (the gate form of DexRT's inner parallax fix, which substitutes the lower sample instead). The parent-side hit-distance test is kept as a measured row; it cannot fire where the parent's interval starts beyond the lower probe. Merges are also chosen per hand-over, selected on training offsets and reported on held-out offsets and scenes. References are exact where the scene allows: solid angles for a lamp in empty space, zero inside a sealed box and the sky less the box's solid angle outside it, and `4πc` in a uniform furnace.

- [x] Novelty check
- [x] Voxel scenes, DDA tracer, dense-grid RC and reference
- [x] Derivations and checks
- [x] Experiments and figures
- [x] Prose, bibliography, PDF
- [x] Review, rerun, commit
- [x] Source note, topics, indexes and README in `research/`

### 4. Paper 3: several bounces in one frame

Done as for paper 1. Diffuse opaque scenes, discretized into patches (segment sides in flatland, voxel faces in 3D), each with emission and albedo. With geometry fixed, every ray's hit record (the patch it hit) is fixed, so an RC solve is a linear map from patch radiance to irradiance at the patches' collocation points; one more bounce is a re-shade of the hit records and a re-merge, with no rays. The exact reference solves the same collocation system: in flatland with exact point-to-patch form factors from the oracle, in 3D with frozen cosine-weighted Monte Carlo rays from the same points. Questions: the furnace (uniform radiance) is exact under the vanilla merge, so in a closed scene RC's operator has the exact one's dominant eigenpair; how the error of the converged solution relates to the one-bounce error (the second eigenvalue, i.e. how weakly a scene's parts couple, against albedo); how many re-merges plain iteration, tail (ambient) extrapolation, Anderson mixing and GMRES need, since the iteration state is only the patch vector; one bounce plus an ambient term as the baseline; a coarse re-merge that stops at cascade 1 for later bounces; cost per bounce in texel reads and memory per hit record.

- [x] Novelty check
- [x] Exact radiosity reference and the frozen-ray bounce solver
- [x] Derivations and checks
- [x] Experiments and figures
- [x] Prose, bibliography, PDF
- [x] Review, rerun, commit
- [ ] Source note, topics, indexes and README in `research/`

### 5. Close

- [ ] Plan moved to `finished/`, memory updated, scratch files deleted

## Facts / research

- Gaps the papers address: `research/topics/single_frame_3d_rc.md#where-the-evidence-stops` items 4, 5 and 8; "there is no measured optimum" for interval scaling in `research/topics/core_theory.md#two-criteria-for-interval-scaling-derived`; the "not reported" cells of the fixes table in `research/topics/artifacts_and_fixes.md#fixes-compared`; lag-free multi-bounce "exists in principle" in `research/topics/light_transport_alternatives.md#single-frame-assessment`.
- Prior art to credit: the 2D parallax fix reprojects at the lower ray's end; Reservoir Cascades reprojects through one depth `t_c`; lXByRh reprojects hit points into finer probes and replaces radiance; directional-opacity mips (VCT, GIVoxels, DexRT) rule out a paper on mip marching.
- Web searches on 2026-10-20 for error analysis, single-frame multi-bounce and 3D merge comparisons found nothing beyond the sources already in `research/`.
- Paper 3's furnace hypothesis failed: every merge whose weights sum to one passes the furnace, yet inside a closed region it reads light from behind walls, so the frozen operator's dominant eigenvalue is not the exact one. That leak deficit, its eigenvalue shift and its compounding over bounces became the paper's center. Enlighten (precomputed form factors, bounces fed back per frame) and Arvo, Torrance and Smits 1994 (operator-perturbation error analysis) are the prior art closest to the frozen solve; a web search on 2026-10-20 found no measured single-frame multi-bounce RC.
- Python 3.14 has numpy 2.5 and scipy 1.18 but not matplotlib; uv 0.12 is installed. The GPU is an RTX 2070 with 8 GB.
- CuPy 14.2 (`cupy-cuda13x[ctk]`) runs the lab's tracer and reference on the GPU and matches the CPU to 1e-15. The RTX 2070's fp64 is slow but still far faster than the CPU; several GPU processes at once ran slower than one and exhausted memory, so the experiments run sequentially and the tracer moves rays to the device in chunks.
