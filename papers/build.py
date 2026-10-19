"""Builds each paper's paper.pdf from its paper.md.

Pandoc with pandoc-crossref writes LaTeX on the acmart template, then pdfLaTeX and BibTeX typeset it in the paper's
build/ directory. Exits non-zero when LaTeX reports an undefined or duplicated citation or reference.

Usage: uv run python build.py [paper_dir ...]    (default: every NN_* directory beside this script)
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template" / "acmart.latex"
FILTERS = ROOT / "template" / "filters.lua"
CROSSREF = [
    "-M", "figPrefix=Figure",
    "-M", "eqnPrefix=Equation",
    "-M", "tblPrefix=Table",
    "-M", "secPrefix=Section",
    "-M", "linkReferences=true",
]
PROBLEM = re.compile(r"undefined|multiply defined", re.IGNORECASE)


def tool(name):
    path = shutil.which(name)
    if not path:
        sys.exit(f"{name} is not on PATH")
    return path


def run(args, cwd):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, errors="replace")
    if result.returncode:
        print(result.stdout[-4000:], result.stderr[-4000:], sep="\n")
        sys.exit(f"{Path(args[0]).name} failed in {cwd}")


def build(paper):
    (paper / "build").mkdir(exist_ok=True)
    run([tool("pandoc"), "paper.md", "--filter", tool("pandoc-crossref"), "--lua-filter", str(FILTERS), "--natbib",
         "--template", str(TEMPLATE), *CROSSREF, "-o", "build/paper.tex"], paper)

    latex = [tool("pdflatex"), "-interaction=nonstopmode", "-halt-on-error", "-output-directory=build", "build/paper.tex"]
    run(latex, paper)
    run([tool("bibtex"), "build/paper"], paper)
    run(latex, paper)
    run(latex, paper)

    shutil.copy(paper / "build" / "paper.pdf", paper / "paper.pdf")
    log = (paper / "build" / "paper.log").read_text(errors="replace")
    return [line for line in log.splitlines() if PROBLEM.search(line)]


def main():
    papers = [Path(arg).resolve() for arg in sys.argv[1:]] or sorted(p.parent for p in ROOT.glob("[0-9][0-9]_*/paper.md"))
    failed = False
    for paper in papers:
        problems = build(paper)
        print(f"{paper.name}: {'ok' if not problems else 'problems'}")
        for line in problems:
            print("  " + line)
        failed |= bool(problems)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
