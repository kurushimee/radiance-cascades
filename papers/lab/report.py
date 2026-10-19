"""Figure style and result caching shared by the papers' experiments."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams.update({"font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7, "legend.fontsize": 6,
                            "xtick.labelsize": 6, "ytick.labelsize": 6, "lines.linewidth": 1.0,
                            "lines.markersize": 3, "savefig.pad_inches": 0.02})
WIDTH = 5.4  # inches, the text width of the papers


class Outputs:
    """A paper's cached results in build/results/ and its figures in figures/."""

    def __init__(self, paper):
        self.paper = Path(paper)

    def cached(self, stem, compute):
        """Results of `compute()`, kept in build/results/<stem>.json; delete the file to recompute."""
        path = self.paper / "build" / "results" / f"{stem}.json"
        if path.exists():
            return json.loads(path.read_text())
        results = compute()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results))
        return results

    def save(self, fig, stem):
        figures = self.paper / "figures"
        figures.mkdir(exist_ok=True)
        for ext in ("png", "pdf"):
            fig.savefig(figures / f"{stem}.{ext}", dpi=200, bbox_inches="tight")


def legend_below(fig, ax, ncol, margin):
    """Shows ax's legend under every panel, where it covers no data; margin is the figure fraction it takes."""
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=ncol, frameon=False)
    fig.tight_layout(rect=(0, margin, 1, 1))
