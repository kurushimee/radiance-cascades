# Papers

Original research on radiance cascades: derivations, assert-checked numbers and experiments against exact or brute-force references. Published work on the subject is collected separately in [research/](../research/README.md).

| Paper | Subject | Status |
|---|---|---|
| [01_error_model](01_error_model/) | Where the error of radiance cascades comes from, measured against an exact flatland reference, and the parameters that minimize it | [done](01_error_model/paper.pdf) |
| [02_merging_3d](02_merging_3d/) | Merging in 3D probe grids: leaks, parallax and cost of thirteen merges against a voxel reference, and a self test that halves the leak at no rays | [done](02_merging_3d/paper.pdf) |
| 03_bounces_one_frame | Several bounces within one frame by re-merging frozen rays | planned |

## Layout

Each paper directory holds `paper.md` (the source), `paper.pdf` (the built paper), `checks/` (one assert script per derived number), `experiments/` (seeded scripts that regenerate every figure and table) and `figures/`. [lab/](lab/) holds the simulators and reference solvers the experiments share.

## Running

The Python environment is a uv project; run every script from this directory:

```bash
uv run python lab/selftest.py
```

The flatland lab traces rays and computes its reference on the GPU through CuPy, and falls back to NumPy on the CPU when CuPy is missing. The voxel lab, `lab/volume.py`, compiles CUDA kernels through CuPy and needs an NVIDIA GPU. Experiments keep their results in the paper's `build/results/` and only redraw figures while those files exist; deleting them recomputes everything.

Building the PDFs needs Pandoc, pandoc-crossref built for the same Pandoc version, and a LaTeX distribution with `acmart`, `pdflatex` and `bibtex` on `PATH`:

```bash
uv run python build.py
```

`build.py` takes paper directories as arguments and builds every paper without them. Sources are Pandoc Markdown: `[@key]` cites [references.bib](references.bib), `{#fig:…}` and `@fig:…` label and reference figures, equations and tables, and a heading with the class `.appendix` starts the appendices.
