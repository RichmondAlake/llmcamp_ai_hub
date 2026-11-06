"""One chart style for every notebook: a dark surface, thin marks and one axis per chart.

The palette is the dark step of a validated categorical order; slots are assigned in fixed order so
a method keeps its colour across charts.
"""

from __future__ import annotations

from typing import Sequence

import matplotlib.pyplot as plt

SURFACE = "#1a1a19"
INK = "#f0efec"
MUTED = "#c3c2b7"
GRID = "#3a3a38"
SERIES = {"blue": "#3987e5", "orange": "#d95926", "aqua": "#199e70", "yellow": "#c98500", "magenta": "#d55181"}


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "text.color": INK, "axes.labelcolor": MUTED, "axes.edgecolor": GRID,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "font.size": 11, "axes.titlesize": 13,
        "axes.titlelocation": "left", "legend.frameon": False, "figure.dpi": 110,
    })


def signal_along_text(values: Sequence[float], gold: Sequence[int], threshold: float, *,
                      title: str, ylabel: str, line_label: str, threshold_label: str,
                      colour: str = "blue", size: tuple[float, float] = (11, 3.4)):
    """One value per gap between sentences, gold cuts as vertical lines, the cut rule as a horizontal."""
    fig, ax = plt.subplots(figsize=size)
    for position, index in enumerate(gold):
        ax.axvline(index, color=SERIES["yellow"], linewidth=1.2, linestyle=":",
                   label="gold topic boundary" if position == 0 else None)
    ax.plot(range(len(values)), values, color=SERIES[colour], linewidth=2, label=line_label)
    ax.axhline(threshold, color=INK, linewidth=1, linestyle="--", label=threshold_label)
    ax.set(title=title, xlabel="sentence index", ylabel=ylabel, xlim=(0, len(values) - 1))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncols=3)
    fig.tight_layout()
    return fig, ax


def chunk_map(length: int, topics: Sequence[tuple[int, str]], rows: Sequence[dict], *, title: str,
              size: tuple[float, float] = (11, 3.6)):
    """The text drawn as one bar per row, left to right.

    The top bar is the real topics, one labelled block each. Every other bar is one chunker: a block
    per chunk, with a gap wherever it cut. Dashed lines mark the real topic changes through every
    bar, so a cut on a line is right, a cut between lines is extra, and a line with no cut is missed.
    `rows` holds {"name", "cuts" (character offsets), "colour", "note"}.
    """
    import numpy as np

    fig, ax = plt.subplots(figsize=size)
    names = ["real topics"] + [row["name"] for row in rows]
    y = {name: len(names) - 1 - i for i, name in enumerate(names)}
    edges = [start for start, _ in topics] + [length]
    for i, (start, label) in enumerate(topics):
        shade = "#4a4a46" if i % 2 else "#5f5f5a"
        ax.barh(y["real topics"], edges[i + 1] - start, left=start, height=0.72, color=shade,
                edgecolor=SURFACE, linewidth=2)
        ax.text((start + edges[i + 1]) / 2, y["real topics"], label.replace(" ", "\n"), ha="center",
                va="center", fontsize=7.5, color=INK, linespacing=0.95)
    for row in rows:
        cut_edges = [0] + sorted(row["cuts"]) + [length]
        for i, (a, b) in enumerate(zip(cut_edges, cut_edges[1:])):
            ax.barh(y[row["name"]], b - a, left=a, height=0.62, color=SERIES[row["colour"]],
                    alpha=0.9 if i % 2 == 0 else 0.6, edgecolor=SURFACE, linewidth=2.5)
        if row.get("note"):
            ax.text(length * 1.01, y[row["name"]], row["note"], va="center", fontsize=9, color=MUTED)
    for position, (start, _) in enumerate(topics[1:]):
        ax.axvline(start, color=SERIES["yellow"], linewidth=1.2, linestyle="--", zorder=3,
                   label="real topic change" if position == 0 else None)
    ax.set_yticks([y[name] for name in names], names)
    ax.set_xticks(np.linspace(0, length, 5).round(), [f"{int(v):,}" for v in np.linspace(0, length, 5)])
    ax.set(title=title, xlabel="position in the text (characters)", xlim=(0, length))
    ax.grid(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncols=1)
    fig.tight_layout()
    return fig, ax


def threshold_tradeoff(thresholds: Sequence[float], lines: dict[str, tuple[Sequence[float], str]], *,
                       title: str, xlabel: str, ylabel: str, markers: dict[str, tuple[float, str]] | None = None,
                       mark_x: float | None = None, mark_label: str | None = None,
                       size: tuple[float, float] = (8, 3.6)):
    """Rates that move with one threshold, plus fixed reference values drawn as dashed lines."""
    fig, ax = plt.subplots(figsize=size)
    for name, (values, colour) in lines.items():
        ax.plot(thresholds, values, color=SERIES[colour], linewidth=2, marker="o", markersize=4, label=name)
    for name, (value, colour) in (markers or {}).items():
        ax.axhline(value, color=SERIES[colour], linewidth=1.5, linestyle="--", label=name)
    if mark_x is not None:
        ax.axvline(mark_x, color=INK, linewidth=1, linestyle=":", label=mark_label)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel, ylim=(-0.03, 1.03))
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    return fig, ax


def dots_by_group(groups: dict[str, Sequence[float]], *, title: str, xlabel: str, line: float | None = None,
                  line_label: str | None = None, colour: str = "blue", size: tuple[float, float] = (8, 3.4)):
    """One row of dots per group on one shared axis, so overlapping groups are easy to see."""
    import numpy as np

    fig, ax = plt.subplots(figsize=size)
    names = list(groups)
    for i, name in enumerate(names):
        values = np.asarray(groups[name])
        jitter = (np.arange(len(values)) % 3 - 1) * 0.12
        ax.scatter(values, np.full(len(values), len(names) - 1 - i) + jitter, s=46, color=SERIES[colour],
                   edgecolor=SURFACE, linewidth=1.5, zorder=3)
    if line is not None:
        ax.axvline(line, color=INK, linewidth=1, linestyle="--", label=line_label)
        ax.legend(loc="lower right")
    ax.set_yticks(range(len(names)), names[::-1])
    ax.set(title=title, xlabel=xlabel)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return fig, ax


def paired_bars(rows: Sequence[dict], *, title: str, xlabel: str, left: str, right: str,
                size: tuple[float, float] = (8, 3.8)):
    """Two bars per row, today and with a decision model, labelled with their values."""
    import numpy as np

    fig, ax = plt.subplots(figsize=size)
    y = np.arange(len(rows))[::-1]
    for offset, key, colour, label in ((0.2, "today", "blue", left), (-0.2, "model", "aqua", right)):
        values = [row[key] for row in rows]
        ax.barh(y + offset, values, height=0.36, color=SERIES[colour], label=label)
        for yy, value in zip(y + offset, values):
            ax.text(value + 0.01, yy, f"{value:.2f}", va="center", fontsize=9, color=MUTED)
    ax.set_yticks(y, [row["name"] for row in rows])
    ax.set(title=title, xlabel=xlabel, xlim=(0, 1.12))
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncols=2)
    fig.tight_layout()
    return fig, ax


def gap_view(sentences: Sequence[str], *, real: Sequence[int] = (), values: dict | None = None,
             cuts: dict | None = None, title: str, width: int = 78, size_x: float = 11.5):
    """A text's sentences stacked top to bottom, with the gap between each pair drawn and numbered.

    Gap i sits between sentence i and sentence i + 1. Real boundaries are drawn as solid yellow
    lines. `values` adds one column per method, {label: (per-gap values, colour)}, and `cuts`
    marks with ✂ the gaps each method cuts at, {label: set of gap indices}.
    """
    values, cuts, real = values or {}, cuts or {}, set(real)
    n = len(sentences)
    fig, ax = plt.subplots(figsize=(size_x, 0.52 * n + 1.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, 2 * n - 0.4)
    ax.axis("off")
    text_right = 0.58 if values else 0.86
    y = lambda row: 2 * (n - 1 - row) + 0.6          # sentence rows, top to bottom; gaps sit between them
    for i, sentence in enumerate(sentences):
        line = " ".join(sentence.split())
        line = line if len(line) <= width else line[: width - 1] + "…"
        ax.text(0.0, y(i), f"{i:>2}  {line}", fontsize=9.5, color=INK, va="center", family="monospace")
    columns = list(values)
    for k, label in enumerate(columns):
        ax.text(text_right + 0.18 + k * 0.14, 2 * n - 0.55, label, fontsize=9, color=SERIES[values[label][1]],
                ha="center", va="center", fontweight="bold")
    for g in range(n - 1):
        gy = (y(g) + y(g + 1)) / 2
        is_real = g in real
        ax.plot([0.0, text_right], [gy, gy], color=SERIES["yellow"] if is_real else GRID,
                linewidth=2.2 if is_real else 1, linestyle="-" if is_real else (0, (4, 3)))
        ax.text(text_right + 0.01, gy, f"gap {g}" + ("  real change" if is_real else ""), fontsize=8.5,
                color=SERIES["yellow"] if is_real else MUTED, va="center")
        for k, label in enumerate(columns):
            series, colour = values[label]
            mark = "✂ " if g in cuts.get(label, set()) else ""
            ax.text(text_right + 0.18 + k * 0.14, gy, f"{mark}{series[g]:.2f}", fontsize=9.5, ha="center", va="center",
                    color=SERIES[colour], fontweight="bold" if mark else "normal")
    ax.set_title(title, loc="left")
    notes = ["solid yellow line: a real section change"] + (["✂: where that method cuts"] if cuts else [])
    ax.text(0.0, -0.45, "   ·   ".join(notes), fontsize=8.5, color=MUTED, va="center")
    fig.tight_layout()
    return fig, ax
