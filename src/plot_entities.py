"""Heatmaps of the Hetionet entities found in each book (output of src/book_entities.py).

- `overview.png`: books x Hetionet categories, coloured by mentions, with the number of
  distinct entities and of mentions in each cell.
- `<book>.png`: the entities with at least MIN_MENTIONS mentions (at most MAX_PER_KIND per
  category), grouped by category (rows),
  against its position in the book (columns: equal slices of the text), coloured by the number
  of mentions in each slice; the total is written at the end of each row.

    uv run python src/plot_entities.py configs/books.yaml
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

MIN_MENTIONS = 10  # entities shown in the per-book heatmaps…
MAX_PER_KIND = 15  # …at most this many per category, the most mentioned
SLICES = 40  # slices of the book text (2.5% each)

# Book titles for the plots, by file-name prefix.
TITLES = {
    "1": "Genetics of Colorectal Cancer",
    "2": "Medical Genetics Summaries: CYP2D6 group",
    "3": "The EBMT Handbook, 8th ed.",
    "4": "Microbiology, Pharmacology, and Immunology for Pre-Clinical Students",
    "5": "Nursing: Mental Health and Community Concepts",
    "6": "The EBMT/EHA CAR-T Cell Handbook",
    "7": "Diseases of the Chest, Breast, Heart and Vessels 2019–2022",
    "8": "Diseases of the Abdomen and Pelvis 2023–2026",
    "9": "Diseases of the Brain, Head and Neck, Spine 2024–2027",
    "10": "The EBMT Textbook for Nurses, 2nd ed.",
}
KINDS = [
    "Gene",
    "Compound",
    "Disease",
    "Side Effect",
    "Symptom",
    "Anatomy",
    "Pharmacologic Class",
    "Biological Process",
    "Molecular Function",
    "Cellular Component",
    "Pathway",
]

# Sequential blue ramp, steps 100 -> 700 (dataviz reference palette); empty cells = surface.
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("blues", BLUES)
CMAP.set_bad("#f2f2ef")
INK, MUTED = "#1f1f1d", "#6b6b66"
PLAIN = FuncFormatter(lambda v, _: f"{v:g}")  # 1, 10, 100 instead of 10^0, 10^1, 10^2

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 9,
        "text.color": INK,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": INK,
        "figure.facecolor": "white",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.spines.bottom": False,
    }
)


def title(book: str) -> str:
    prefix = book.split("-", 1)[0]
    return f"{prefix}. {TITLES.get(prefix, book)}"


def colorbar(fig, image, label: str, ax=None, cax=None) -> None:
    """Horizontal colour bar, either stolen from `ax` or drawn in its own axes `cax`."""
    if cax is not None:
        bar = fig.colorbar(image, cax=cax, orientation="horizontal")
    else:
        bar = fig.colorbar(
            image,
            ax=ax,
            orientation="horizontal",
            fraction=0.04,
            pad=0.1,
            aspect=40,
            shrink=0.5,
            anchor=(0, 1),
        )
    bar.set_label(label, color=MUTED)
    bar.ax.xaxis.set_major_formatter(PLAIN)
    bar.ax.tick_params(colors=MUTED, length=2)
    bar.outline.set_visible(False)


def overview(results: list[dict], out: Path) -> None:
    mentions = np.array(
        [[sum(e["mentions"] for e in r["entities"].get(k, [])) for k in KINDS] for r in results],
        dtype=float,
    )
    distinct = np.array([[len(r["entities"].get(k, [])) for k in KINDS] for r in results])
    fig, ax = plt.subplots(figsize=(13, 0.75 * len(results) + 2.6))
    norm = LogNorm(1, mentions.max())
    image = ax.imshow(np.ma.masked_equal(mentions, 0), cmap=CMAP, norm=norm, aspect="auto")
    for i in range(len(results)):
        for j in range(len(KINDS)):
            if distinct[i, j]:
                dark = norm(mentions[i, j]) > 0.6
                ax.text(
                    j,
                    i,
                    f"{distinct[i, j]}\n{int(mentions[i, j])}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if dark else INK,
                    linespacing=1.4,
                )
    ax.set_xticks(range(len(KINDS)), KINDS, rotation=30, ha="right")
    ax.set_yticks(range(len(results)), [title(r["book"]) for r in results])
    ax.set_xticks(np.arange(-0.5, len(KINDS)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(results)), minor=True)
    ax.grid(which="minor", color="white", linewidth=3)
    ax.tick_params(which="both", length=0)
    for text, offset, style in [
        (
            "Hetionet entities per book and category",
            30,
            {"fontsize": 12, "fontweight": "bold", "color": INK},
        ),
        (
            "each cell: distinct entities (top) and total mentions (bottom)",
            12,
            {"fontsize": 9, "color": MUTED},
        ),
    ]:
        ax.annotate(
            text,
            xy=(0.01, 1),
            xycoords=("figure fraction", "axes fraction"),
            xytext=(0, offset),
            textcoords="offset points",
            ha="left",
            va="bottom",
            **style,
        )
    colorbar(fig, image, "total mentions (log scale)", cax=ax.inset_axes([0, -0.3, 0.4, 0.05]))
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)


def book_heatmap(result: dict, out: Path) -> None:
    rows, names, totals, groups = [], [], [], []  # groups: (kind, first row, last row)
    for kind in KINDS:
        entities = [e for e in result["entities"].get(kind, []) if e["mentions"] >= MIN_MENTIONS]
        entities = entities[:MAX_PER_KIND]  # already sorted by mentions
        if not entities:
            continue
        if rows:  # blank row between categories
            rows.append(np.full(SLICES, np.nan))
            names.append("")
            totals.append(0)
        groups.append((kind, len(rows), len(rows) + len(entities) - 1))
        for e in entities:
            counts, _ = np.histogram(e["positions"], bins=SLICES, range=(0, result["chars"]))
            rows.append(counts.astype(float))
            names.append(e["name"] if len(e["name"]) <= 32 else e["name"][:31] + "…")
            totals.append(e["mentions"])
    grid = np.array(rows)
    n = len(rows)

    # One row for the plot (category labels | heatmap | totals), one for the colour bar, so the
    # three plot columns keep exactly the same height and their rows line up.
    fig = plt.figure(figsize=(12, 0.27 * n + 2.6))
    grid_spec = fig.add_gridspec(
        2, 3, width_ratios=[2.6, 6, 0.5], height_ratios=[0.27 * n, 1.1], wspace=0.03, hspace=0.0
    )
    label_ax = fig.add_subplot(grid_spec[0, 0])
    ax = fig.add_subplot(grid_spec[0, 1], sharey=label_ax)
    bar_ax = fig.add_subplot(grid_spec[0, 2], sharey=label_ax)
    legend_ax = fig.add_subplot(grid_spec[1, 1])
    legend_ax.axis("off")

    norm = LogNorm(1, max(np.nanmax(grid), 2))
    cells = np.ma.masked_invalid(np.where(grid == 0, np.nan, grid))
    image = ax.imshow(cells, cmap=CMAP, norm=norm, aspect="auto", interpolation="nearest")
    for i, name in enumerate(names):
        if not name:  # separator row: white, not the grey of an empty cell
            ax.axhspan(i - 0.5, i + 0.5, color="white", zorder=2)
    for x in (SLICES * 0.25, SLICES * 0.5, SLICES * 0.75):
        ax.axvline(x - 0.5, color="white", linewidth=1, zorder=3)
    ax.set_xticks(np.linspace(-0.5, SLICES - 0.5, 5), ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("position in the text")
    ax.set_yticks([])
    ax.tick_params(length=0)
    ax.set_xlim(-0.5, SLICES - 0.5)
    ax.set_ylim(n - 0.5, -0.5)

    label_ax.set_xlim(0, 1)
    label_ax.axis("off")
    for i, name in enumerate(names):  # entity names, right-aligned against the heatmap
        label_ax.text(0.98, i, name, ha="right", va="center", fontsize=8, color=INK)
    for kind, first, last in groups:  # category names, in their own column on the left
        label = kind.replace(" ", "\n") if len(kind) > 12 else kind
        label_ax.text(
            0,
            (first + last) / 2,
            label,
            ha="left",
            va="center",
            fontsize=9,
            fontweight="bold",
            color=INK,
        )

    for i, total in enumerate(totals):  # total mentions, as a number at the end of each row
        if total:
            bar_ax.text(0.04, i, str(total), va="center", ha="left", fontsize=8, color=MUTED)
    bar_ax.set_xlim(0, 1)
    bar_ax.set_xticks([])
    bar_ax.tick_params(left=False, labelleft=False)
    bar_ax.text(0.04, -1.2, "total", va="bottom", ha="left", fontsize=8, color=MUTED)

    subtitle = (
        f"Hetionet entities mentioned at least {MIN_MENTIONS} times (top {MAX_PER_KIND} per "
        f"category) · colour: mentions per "
        f"{100 / SLICES:g}% of the text"
    )
    for text, offset, style in [
        (title(result["book"]), 30, {"fontsize": 12, "fontweight": "bold", "color": INK}),
        (subtitle, 12, {"fontsize": 9, "color": MUTED}),
    ]:
        label_ax.annotate(
            text,
            xy=(0, 1),
            xycoords="axes fraction",
            xytext=(0, offset),
            textcoords="offset points",
            ha="left",
            va="bottom",
            **style,
        )
    colorbar(
        fig, image, "mentions per slice (log scale)", cax=legend_ax.inset_axes([0, 0.2, 0.4, 0.12])
    )
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", help="YAML config, e.g. configs/books.yaml")
    config = yaml.safe_load(Path(parser.parse_args().config).read_text(encoding="utf-8"))
    entities_dir, out_dir = Path(config["entities_dir"]), Path(config["plots_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(entities_dir.glob("*.json"), key=lambda p: int(p.stem.split("-", 1)[0]))
    results = [json.loads(p.read_text()) for p in paths]
    overview(results, out_dir / "overview.png")
    for result in results:
        book_heatmap(result, out_dir / f"{result['book']}.png")
    print(f"wrote {len(results) + 1} plots to {out_dir}")
