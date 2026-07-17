#!/usr/bin/env python3
"""
Phase U27A.3
Rebuild Figures 7-11 with figure-specific visual grammars to reduce monotony.

Principles
----------
- All figures are generated reproducibly from the U26/U27 tabular outputs.
- Scientific values, module order, evidence layers and interpretation boundaries
  are preserved.
- Figures 7-10 no longer share one repeated heatmap/bar/heatmap/bar template.
- Figure 11 retains the integrated synthesis architecture from U27A.2.
- Figures are built directly at 180-mm journal width and exported as PNG, SVG
  and PDF.
- No manuscript text and no Figures 1-6 are modified.

Figure-specific grammars
------------------------
Figure 7: warm steroid/lipid bubble matrix + lollipop + heatmap + lollipop.
Figure 8: cool signaling heatmap + lollipop + cellular trajectory plot + bars.
Figure 9: green/amber bubble matrix + diverging bars + cellular Cleveland plot
          + ranked stems.
Figure 10: complement-stage heatmap + shaded diverging bars + cellular bubble
           matrix + ranked bars.
Figure 11: integrated cross-context heatmaps, composition shifts and network.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize, TwoSlopeNorm
except ImportError as exc:
    raise SystemExit("ERROR: matplotlib is required.") from exc


VERSION = "U27A3_v1.0_2026-07-15"
TAG = "phaseU27A3_visual_diversity_redesign"
BASE_SCRIPT_NAME = "phaseU27A2_rebuild_figures_7_to_11_journal_width.py"

JOURNAL_WIDTH_MM = 180.0
JOURNAL_WIDTH_IN = JOURNAL_WIDTH_MM / 25.4

EXPECTED_FIGURES = [
    "Figure_7",
    "Figure_8",
    "Figure_9",
    "Figure_10",
    "Figure_11",
]

FIGURE_TITLES = {
    "Figure_7": (
        "Figure 7. Steroid, cholesterol, receptor-response and "
        "lipid-remodeling architecture"
    ),
    "Figure_8": (
        "Figure 8. Adipokine, insulin/IRS, PI3K-AKT and "
        "inflammatory-carbon remodeling"
    ),
    "Figure_9": (
        "Figure 9. Amino-acid, nucleotide, nitrogen and redox remodeling"
    ),
    "Figure_10": (
        "Figure 10. Complement initiation, amplification, effector and "
        "regulatory architecture*"
    ),
}

CELL_ORDER = [
    "macrophage_monocyte",
    "dendritic",
    "neutrophil",
    "T_cell",
    "NK_cell",
    "cycling_immune",
]

CELL_LABELS = {
    "macrophage_monocyte": "Macrophage/\nmonocyte",
    "dendritic": "Dendritic",
    "neutrophil": "Neutrophil",
    "T_cell": "T cell",
    "NK_cell": "NK cell",
    "cycling_immune": "Cycling\nimmune",
}

COMPLEMENT_GROUPS = [
    ("Initiation", [
        "Classical complement",
        "Lectin complement",
        "Alternative complement",
    ]),
    ("Amplification", ["C3-convertase amplification"]),
    ("Effector", [
        "C3a/C5a signaling",
        "Complement-opsonophagocytosis",
        "Terminal complement/MAC",
        "Complement-coagulation",
    ]),
    ("Regulation", ["Complement regulators"]),
]


def log(message: str) -> None:
    print(f"[U27A.3] {message}", flush=True)


def load_base_module(project: Path):
    candidates = [
        project / "10_scripts" / BASE_SCRIPT_NAME,
        Path("/mnt/data") / BASE_SCRIPT_NAME,
    ]
    source = next((path for path in candidates if path.exists()), None)
    if source is None:
        raise FileNotFoundError(
            f"Required U27A.2 base script not found: {BASE_SCRIPT_NAME}"
        )

    spec = importlib.util.spec_from_file_location("u27a2_base", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import base script: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, source


def symmetric_norm(values: np.ndarray) -> TwoSlopeNorm:
    finite = values[np.isfinite(values)]
    limit = float(np.nanmax(np.abs(finite))) if finite.size else 1.0
    if not np.isfinite(limit) or limit == 0:
        limit = 1.0
    return TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)


def panel_letter(ax: plt.Axes, letter: str) -> None:
    ax.text(
        -0.12,
        1.055,
        letter,
        transform=ax.transAxes,
        fontsize=10.5,
        fontweight="bold",
        va="top",
        ha="left",
    )


def clean_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def bubble_matrix(
    ax: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
    cmap: str,
    colorbar_label: str,
    max_size: float = 330.0,
) -> None:
    ax.set_title(title, fontsize=8.5, pad=7)
    if matrix.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return

    values = matrix.apply(pd.to_numeric, errors="coerce").to_numpy(float)
    norm = symmetric_norm(values)
    finite = np.abs(values[np.isfinite(values)])
    scale = float(finite.max()) if finite.size else 1.0
    if scale == 0:
        scale = 1.0

    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = values[row, col]
            if not np.isfinite(value):
                continue
            size = 28.0 + max_size * math.sqrt(abs(value) / scale)
            ax.scatter(
                col,
                row,
                s=size,
                c=[value],
                cmap=cmap,
                norm=norm,
                edgecolors="white",
                linewidths=0.45,
            )

    ax.set_xlim(-0.55, len(matrix.columns) - 0.45)
    ax.set_ylim(len(matrix.index) - 0.45, -0.55)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(
        [str(value) for value in matrix.columns],
        rotation=43,
        ha="right",
        fontsize=6.5,
    )
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=6.45)
    ax.grid(True, linewidth=0.35, alpha=0.20)
    ax.set_axisbelow(True)
    clean_axis(ax)

    scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    scalar.set_array([])
    colorbar = ax.figure.colorbar(
        scalar,
        ax=ax,
        fraction=0.040,
        pad=0.025,
    )
    colorbar.set_label(colorbar_label, fontsize=6.5)
    colorbar.ax.tick_params(labelsize=5.8)

    legend_sizes = [0.25, 0.50, 1.00]
    handles = [
        ax.scatter([], [], s=28 + max_size * math.sqrt(value),
                   facecolors="none", edgecolors="0.35", linewidths=0.7)
        for value in legend_sizes
    ]
    ax.legend(
        handles,
        ["25%", "50%", "100%"],
        title="|effect|",
        loc="upper left",
        bbox_to_anchor=(1.02, 0.26),
        frameon=False,
        fontsize=5.5,
        title_fontsize=5.8,
        borderaxespad=0,
    )


def heatmap(
    ax: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
    cmap: str,
    colorbar_label: str,
) -> None:
    ax.set_title(title, fontsize=8.5, pad=7)
    if matrix.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return

    numeric = matrix.apply(pd.to_numeric, errors="coerce")
    values = numeric.to_numpy(float)
    norm = symmetric_norm(values)
    image = ax.imshow(values, aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(np.arange(len(numeric.columns)))
    ax.set_xticklabels(
        [str(value) for value in numeric.columns],
        rotation=43,
        ha="right",
        fontsize=6.5,
    )
    ax.set_yticks(np.arange(len(numeric.index)))
    ax.set_yticklabels(numeric.index, fontsize=6.45)
    clean_axis(ax)
    colorbar = ax.figure.colorbar(
        image,
        ax=ax,
        fraction=0.040,
        pad=0.025,
    )
    colorbar.set_label(colorbar_label, fontsize=6.5)
    colorbar.ax.tick_params(labelsize=5.8)


def lollipop(
    ax: plt.Axes,
    series: pd.Series,
    title: str,
    positive_color: str,
    negative_color: str,
    x_label: str,
    preserve_order: bool = True,
) -> None:
    ax.set_title(title, fontsize=8.5, pad=7)
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return
    if not preserve_order:
        values = values.sort_values()

    y = np.arange(len(values))
    colors = [positive_color if value >= 0 else negative_color for value in values]
    for yi, value, color in zip(y, values.to_numpy(), colors):
        ax.hlines(yi, 0, value, color=color, linewidth=1.35)
        ax.scatter(value, yi, color=color, s=27, zorder=3)
        span = max(float(np.max(np.abs(values))), 0.1)
        ax.text(
            value + (0.025 * span if value >= 0 else -0.025 * span),
            yi,
            f"{value:+.2f}",
            ha="left" if value >= 0 else "right",
            va="center",
            fontsize=5.7,
        )

    ax.axvline(0, color="0.35", linewidth=0.7, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(values.index, fontsize=6.35)
    ax.invert_yaxis()
    ax.set_xlabel(x_label, fontsize=7.1)
    ax.tick_params(axis="x", labelsize=6.1)
    clean_axis(ax)


def ranked_bars(
    ax: plt.Axes,
    series: pd.Series,
    title: str,
    bar_color: str,
    x_label: str,
) -> None:
    ax.set_title(title, fontsize=8.5, pad=7)
    values = pd.to_numeric(series, errors="coerce").dropna().sort_values(
        ascending=True
    )
    if values.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return

    y = np.arange(len(values))
    ax.barh(y, values.to_numpy(), color=bar_color, alpha=0.88, height=0.62)
    ax.set_yticks(y)
    ax.set_yticklabels(values.index, fontsize=6.0)
    ax.set_xlabel(x_label, fontsize=7.1)
    ax.tick_params(axis="x", labelsize=6.1)
    ax.grid(axis="x", alpha=0.18, linewidth=0.45)
    ax.set_axisbelow(True)
    clean_axis(ax)
    span = max(float(values.max()), 0.1)
    for yi, value in enumerate(values.to_numpy()):
        ax.text(
            value + 0.015 * span,
            yi,
            f"{value:.2f}",
            va="center",
            fontsize=5.7,
        )


def ranked_stems(
    ax: plt.Axes,
    series: pd.Series,
    title: str,
    stem_color: str,
    marker_color: str,
    x_label: str,
) -> None:
    ax.set_title(title, fontsize=8.5, pad=7)
    values = pd.to_numeric(series, errors="coerce").dropna().sort_values(
        ascending=True
    )
    if values.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return

    y = np.arange(len(values))
    for yi, value in zip(y, values.to_numpy()):
        ax.hlines(yi, 0, value, color=stem_color, linewidth=1.2)
        ax.scatter(value, yi, color=marker_color, s=31, zorder=3)
        ax.text(value + 0.012, yi, f"{value:.2f}", fontsize=5.7, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(values.index, fontsize=6.0)
    ax.set_xlabel(x_label, fontsize=7.1)
    ax.tick_params(axis="x", labelsize=6.1)
    ax.grid(axis="x", alpha=0.18, linewidth=0.45)
    ax.set_axisbelow(True)
    clean_axis(ax)


def trajectory_plot(
    ax: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
    cmap: str,
    n_highlight: int = 6,
) -> None:
    ax.set_title(title, fontsize=8.5, pad=7)
    if matrix.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return

    numeric = matrix.apply(pd.to_numeric, errors="coerce")
    x = np.arange(len(numeric.columns))
    amplitudes = numeric.abs().max(axis=1).sort_values(ascending=False)
    highlighted = list(amplitudes.head(n_highlight).index)
    palette = plt.get_cmap(cmap)(np.linspace(0.15, 0.90, len(highlighted)))

    for label, row in numeric.iterrows():
        values = row.to_numpy(float)
        if label in highlighted:
            color = palette[highlighted.index(label)]
            ax.plot(x, values, marker="o", linewidth=1.35, markersize=3.2,
                    color=color, label=label)
        else:
            ax.plot(x, values, linewidth=0.55, color="0.78", alpha=0.48)

    ax.axhline(0, color="0.35", linewidth=0.7, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [CELL_LABELS.get(str(value), str(value)) for value in numeric.columns],
        rotation=35,
        ha="right",
        fontsize=6.2,
    )
    ax.set_ylabel("Module-gene log2 fold change", fontsize=7.1)
    ax.tick_params(axis="y", labelsize=6.1)
    clean_axis(ax)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=5.45,
        title="Largest trajectories",
        title_fontsize=5.8,
        borderaxespad=0,
    )


def cleveland_cellular_plot(
    ax: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
    colors: Sequence[str],
) -> None:
    ax.set_title(title, fontsize=8.5, pad=7)
    if matrix.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return

    numeric = matrix.apply(pd.to_numeric, errors="coerce")
    y_base = np.arange(len(numeric.index))
    offsets = np.linspace(-0.26, 0.26, len(numeric.columns))

    for column_index, column in enumerate(numeric.columns):
        values = numeric[column].to_numpy(float)
        y = y_base + offsets[column_index]
        ax.scatter(
            values,
            y,
            s=18,
            color=colors[column_index % len(colors)],
            label=CELL_LABELS.get(str(column), str(column)),
            alpha=0.90,
        )

    row_min = numeric.min(axis=1).to_numpy(float)
    row_max = numeric.max(axis=1).to_numpy(float)
    for yi, low, high in zip(y_base, row_min, row_max):
        if np.isfinite(low) and np.isfinite(high):
            ax.hlines(yi, low, high, color="0.75", linewidth=0.7, zorder=0)

    ax.axvline(0, color="0.35", linewidth=0.7, linestyle="--")
    ax.set_yticks(y_base)
    ax.set_yticklabels(numeric.index, fontsize=6.3)
    ax.invert_yaxis()
    ax.set_xlabel("Module-gene log2 fold change", fontsize=7.1)
    ax.tick_params(axis="x", labelsize=6.1)
    clean_axis(ax)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=5.35,
        title="Broad population",
        title_fontsize=5.7,
        borderaxespad=0,
    )


def complement_stage_heatmap(
    ax: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
) -> None:
    ax.set_title(title, fontsize=8.5, pad=7)
    if matrix.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return

    numeric = matrix.apply(pd.to_numeric, errors="coerce")
    values = numeric.to_numpy(float)
    norm = symmetric_norm(values)
    image = ax.imshow(values, aspect="auto", cmap="viridis", norm=norm)
    ax.set_xticks(np.arange(len(numeric.columns)))
    ax.set_xticklabels(
        numeric.columns,
        rotation=42,
        ha="right",
        fontsize=6.4,
    )
    ax.set_yticks(np.arange(len(numeric.index)))
    ax.set_yticklabels(numeric.index, fontsize=6.3)

    row_lookup = {label: index for index, label in enumerate(numeric.index)}
    group_colors = ["#e8eef8", "#edf4ea", "#eef8f5", "#f3f1f8"]
    for group_index, (group, labels) in enumerate(COMPLEMENT_GROUPS):
        rows = [row_lookup[label] for label in labels if label in row_lookup]
        if not rows:
            continue
        start = min(rows) - 0.5
        end = max(rows) + 0.5
        ax.axhspan(start, end, color=group_colors[group_index], alpha=0.22,
                   zorder=-1)
        ax.text(
            -0.72,
            (start + end) / 2,
            group,
            rotation=90,
            va="center",
            ha="center",
            fontsize=5.5,
            fontweight="bold",
            transform=ax.transData,
        )
        if end < len(numeric.index) - 0.5:
            ax.axhline(end, color="white", linewidth=1.8)

    clean_axis(ax)
    colorbar = ax.figure.colorbar(
        image,
        ax=ax,
        fraction=0.040,
        pad=0.025,
    )
    colorbar.set_label("Effect", fontsize=6.5)
    colorbar.ax.tick_params(labelsize=5.8)


def shaded_diverging_bars(
    ax: plt.Axes,
    series: pd.Series,
    title: str,
) -> None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    ax.set_title(title, fontsize=8.5, pad=7)
    if values.empty:
        ax.text(0.5, 0.5, "No eligible data", ha="center", va="center")
        ax.set_axis_off()
        return

    span = max(float(np.max(np.abs(values))), 0.1)
    ax.axvspan(-span * 1.16, 0, color="#dcecf6", alpha=0.52, zorder=-3)
    ax.axvspan(0, span * 1.16, color="#e4f2df", alpha=0.52, zorder=-3)
    y = np.arange(len(values))
    colors = ["#2b8cbe" if value < 0 else "#31a354" for value in values]
    ax.barh(y, values.to_numpy(), color=colors, height=0.58)
    ax.axvline(0, color="0.35", linewidth=0.8, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(values.index, fontsize=6.25)
    ax.invert_yaxis()
    ax.set_xlabel("Collapsed effect", fontsize=7.1)
    ax.tick_params(axis="x", labelsize=6.1)
    clean_axis(ax)
    for yi, value in enumerate(values.to_numpy()):
        ax.text(
            value + (0.025 * span if value >= 0 else -0.025 * span),
            yi,
            f"{value:+.2f}",
            ha="left" if value >= 0 else "right",
            va="center",
            fontsize=5.7,
        )
    ax.text(0.03, 0.02, "Lower in preterm", transform=ax.transAxes,
            fontsize=5.6, color="#2b8cbe", ha="left")
    ax.text(0.97, 0.02, "Higher in preterm", transform=ax.transAxes,
            fontsize=5.6, color="#238b45", ha="right")


def make_layout(figure: str) -> Tuple[plt.Figure, Dict[str, plt.Axes]]:
    if figure == "Figure_7":
        fig = plt.figure(figsize=(JOURNAL_WIDTH_IN, 9.25))
        grid = fig.add_gridspec(
            2, 2, left=0.16, right=0.97, bottom=0.075, top=0.92,
            width_ratios=[1.16, 0.84], height_ratios=[1.0, 1.05],
            wspace=0.66, hspace=0.56,
        )
    elif figure == "Figure_8":
        fig = plt.figure(figsize=(JOURNAL_WIDTH_IN, 9.10))
        grid = fig.add_gridspec(
            2, 2, left=0.16, right=0.97, bottom=0.075, top=0.92,
            width_ratios=[1.0, 1.0], height_ratios=[0.96, 1.04],
            wspace=0.62, hspace=0.58,
        )
    elif figure == "Figure_9":
        fig = plt.figure(figsize=(JOURNAL_WIDTH_IN, 9.45))
        grid = fig.add_gridspec(
            2, 2, left=0.16, right=0.97, bottom=0.075, top=0.92,
            width_ratios=[1.12, 0.88], height_ratios=[0.94, 1.06],
            wspace=0.70, hspace=0.58,
        )
    elif figure == "Figure_10":
        fig = plt.figure(figsize=(JOURNAL_WIDTH_IN, 9.35))
        grid = fig.add_gridspec(
            2, 2, left=0.18, right=0.97, bottom=0.095, top=0.92,
            width_ratios=[1.12, 0.88], height_ratios=[1.0, 1.0],
            wspace=0.68, hspace=0.57,
        )
    else:
        raise ValueError(figure)

    axes = {
        "A": fig.add_subplot(grid[0, 0]),
        "B": fig.add_subplot(grid[0, 1]),
        "C": fig.add_subplot(grid[1, 0]),
        "D": fig.add_subplot(grid[1, 1]),
    }
    return fig, axes


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> List[Path]:
    outputs: List[Path] = []
    for extension in ["png", "svg", "pdf"]:
        path = output_dir / f"{stem}.{extension}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        outputs.append(path)
    plt.close(fig)
    return outputs


def build_figure_7(base, effects, preterm, broad, synthesis, labels, outdir):
    figure_id = "Figure_7"
    modules = base.FIGURE_MODULES[figure_id]
    fig, axes = make_layout(figure_id)

    independent = base.independent_effect_matrix(effects, modules, labels)
    pregnancy = base.preterm_series(preterm, modules, labels)
    cellular = base.cellular_matrix(
        broad, modules, labels, "module_mean_gene_log2FC"
    )
    subtype = base.subtype_top_series(synthesis, modules, labels)

    bubble_matrix(
        axes["A"], independent,
        "Independent infection-context effects",
        cmap="magma", colorbar_label="Effect",
    )
    lollipop(
        axes["B"], pregnancy,
        "Pregnancy preterm minus term",
        positive_color="#d28b00", negative_color="#7a1f5c",
        x_label="Collapsed effect",
    )
    heatmap(
        axes["C"], cellular,
        "UPEC broad-cell module-gene log2 fold change",
        cmap="PuOr_r", colorbar_label="log2FC",
    )
    ranked_stems(
        axes["D"], subtype,
        "Strongest refined-subtype cellular support",
        stem_color="#d28b00", marker_color="#7a1f5c",
        x_label="Composite support score",
    )

    for letter, axis in axes.items():
        panel_letter(axis, letter)
    fig.suptitle(FIGURE_TITLES[figure_id], fontsize=10.6, y=0.982)
    outputs = save_figure(
        fig, outdir, "UTI_HostOmics_U27A3_Figure_7"
    )
    design = {
        "A": "effect-size bubble matrix",
        "B": "warm diverging lollipop",
        "C": "diverging cellular heatmap",
        "D": "ranked support stems",
    }
    return outputs, design


def build_figure_8(base, effects, preterm, broad, synthesis, labels, outdir):
    figure_id = "Figure_8"
    modules = base.FIGURE_MODULES[figure_id]
    fig, axes = make_layout(figure_id)

    independent = base.independent_effect_matrix(effects, modules, labels)
    pregnancy = base.preterm_series(preterm, modules, labels)
    cellular = base.cellular_matrix(
        broad, modules, labels, "module_mean_gene_log2FC"
    )
    subtype = base.subtype_top_series(synthesis, modules, labels)

    heatmap(
        axes["A"], independent,
        "Independent infection-context effects",
        cmap="viridis", colorbar_label="Effect",
    )
    lollipop(
        axes["B"], pregnancy,
        "Pregnancy preterm minus term",
        positive_color="#e66b2e", negative_color="#129aa5",
        x_label="Collapsed effect",
    )
    trajectory_plot(
        axes["C"], cellular,
        "UPEC broad-cell signaling trajectories",
        cmap="winter", n_highlight=6,
    )
    ranked_bars(
        axes["D"], subtype,
        "Strongest refined-subtype cellular support",
        bar_color="#159ea8",
        x_label="Composite support score",
    )

    for letter, axis in axes.items():
        panel_letter(axis, letter)
    fig.suptitle(FIGURE_TITLES[figure_id], fontsize=10.6, y=0.982)
    outputs = save_figure(
        fig, outdir, "UTI_HostOmics_U27A3_Figure_8"
    )
    design = {
        "A": "cool independent-effect heatmap",
        "B": "teal-orange lollipop",
        "C": "broad-cell trajectory plot",
        "D": "ranked support bars",
    }
    return outputs, design


def build_figure_9(base, effects, preterm, broad, synthesis, labels, outdir):
    figure_id = "Figure_9"
    modules = base.FIGURE_MODULES[figure_id]
    fig, axes = make_layout(figure_id)

    independent = base.independent_effect_matrix(effects, modules, labels)
    pregnancy = base.preterm_series(preterm, modules, labels)
    cellular = base.cellular_matrix(
        broad, modules, labels, "module_mean_gene_log2FC"
    )
    subtype = base.subtype_top_series(synthesis, modules, labels)

    bubble_matrix(
        axes["A"], independent,
        "Independent infection-context effects",
        cmap="BrBG_r", colorbar_label="Effect",
    )
    lollipop(
        axes["B"], pregnancy,
        "Pregnancy preterm minus term",
        positive_color="#d98e00", negative_color="#2f6b2f",
        x_label="Collapsed effect",
    )
    cleveland_cellular_plot(
        axes["C"], cellular,
        "UPEC broad-cell effect distributions",
        colors=["#355f8d", "#1f9e89", "#e76f51", "#7b2cbf", "#577590", "#90be6d"],
    )
    ranked_stems(
        axes["D"], subtype,
        "Strongest refined-subtype cellular support",
        stem_color="#4d7f38", marker_color="#d98e00",
        x_label="Composite support score",
    )

    for letter, axis in axes.items():
        panel_letter(axis, letter)
    fig.suptitle(FIGURE_TITLES[figure_id], fontsize=10.6, y=0.982)
    outputs = save_figure(
        fig, outdir, "UTI_HostOmics_U27A3_Figure_9"
    )
    design = {
        "A": "green-amber effect bubble matrix",
        "B": "green-amber lollipop",
        "C": "cellular Cleveland dot-range plot",
        "D": "ranked support stems",
    }
    return outputs, design


def build_figure_10(base, effects, preterm, broad, synthesis, labels, outdir):
    figure_id = "Figure_10"
    modules = base.FIGURE_MODULES[figure_id]
    fig, axes = make_layout(figure_id)

    independent = base.independent_effect_matrix(effects, modules, labels)
    pregnancy = base.preterm_series(preterm, modules, labels)
    cellular = base.cellular_matrix(
        broad, modules, labels, "module_mean_gene_log2FC"
    )
    subtype = base.subtype_top_series(synthesis, modules, labels)

    complement_stage_heatmap(
        axes["A"], independent,
        "Independent effects organized by complement stage",
    )
    shaded_diverging_bars(
        axes["B"], pregnancy,
        "Pregnancy preterm minus term",
    )
    bubble_matrix(
        axes["C"], cellular,
        "UPEC broad-cell complement localization",
        cmap="PRGn", colorbar_label="log2FC", max_size=285.0,
    )
    ranked_bars(
        axes["D"], subtype,
        "Strongest refined-subtype cellular support",
        bar_color="#157f78",
        x_label="Composite support score",
    )

    for letter, axis in axes.items():
        panel_letter(axis, letter)
    fig.suptitle(FIGURE_TITLES[figure_id], fontsize=10.6, y=0.982)
    fig.text(
        0.18,
        0.025,
        "*Lectin and terminal-MAC modules lacked eligible GSE252321 "
        "cell-level coverage; infection and pregnancy evidence remain shown "
        "where available.",
        fontsize=5.9,
        ha="left",
    )
    outputs = save_figure(
        fig, outdir, "UTI_HostOmics_U27A3_Figure_10"
    )
    design = {
        "A": "stage-organized complement heatmap",
        "B": "direction-shaded pregnancy bars",
        "C": "cellular complement bubble matrix",
        "D": "ranked support bars",
    }
    return outputs, design


def build_figure_11(base, effects, preterm, broad, synthesis,
                    composition, targeted, labels, outdir):
    outputs, panel_rows = base.build_figure_11(
        effects,
        preterm,
        broad,
        synthesis,
        composition,
        targeted,
        labels,
        outdir,
    )
    renamed: List[Path] = []
    for path in outputs:
        target = outdir / path.name.replace("U27A2", "U27A3")
        shutil.move(str(path), str(target))
        renamed.append(target)
    design = {
        "A": "cross-context core heatmap",
        "B": "core cellular-localization heatmap",
        "C": "composition and targeted-state bars",
        "D": "integrated mechanistic network",
    }
    return renamed, design


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    base, base_source = load_base_module(project)

    plt.rcParams.update(
        {
            "font.size": 7.0,
            "axes.titlesize": 8.5,
            "axes.labelsize": 7.1,
            "xtick.labelsize": 6.2,
            "ytick.labelsize": 6.2,
            "legend.fontsize": 5.6,
            "figure.titlesize": 10.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )

    effects_path = base.require(
        project / "06_tables" / base.B2B1_TAG
        / "UTI_HostOmics_U26B2B1_primary_independent_dataset_effects.tsv"
    )
    preterm_path = base.require(
        project / "06_tables" / base.B2B1_TAG
        / "UTI_HostOmics_U26B2B1_GSE280297_preterm_term_collapsed.tsv"
    )
    broad_path = base.require(
        project / "06_tables" / base.D2C_TAG
        / "UTI_HostOmics_U26D2C_broad_effect_reliability.tsv"
    )
    synthesis_path = base.require(
        project / "06_tables" / base.D2C_TAG
        / "UTI_HostOmics_U26D2C_module_cellular_synthesis.tsv"
    )
    composition_path = base.require(
        project / "06_tables" / base.D2B_TAG
        / "UTI_HostOmics_U26D2B_celltype_composition_effects.tsv"
    )
    targeted_path = base.require(
        project / "06_tables" / base.D2B_TAG
        / "UTI_HostOmics_U26D2B_targeted_state_effects.tsv"
    )
    d2c_decision_path = base.require(
        project / "06_tables" / base.D2C_TAG
        / "UTI_HostOmics_U26D2C_phase_decision.tsv"
    )

    out_figures = project / "06_figures" / TAG
    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG
    for directory in [out_figures, out_tables, out_metadata, out_results]:
        directory.mkdir(parents=True, exist_ok=True)

    effects = base.read_tsv(effects_path)
    preterm = base.read_tsv(preterm_path)
    broad = base.read_tsv(broad_path)
    synthesis = base.read_tsv(synthesis_path)
    composition = base.read_tsv(composition_path)
    targeted = base.read_tsv(targeted_path)
    decision = base.read_tsv(d2c_decision_path)

    if not decision["decision"].astype(str).str.startswith("READY").all():
        raise RuntimeError("U26D2C is not in a READY state.")

    label_table = synthesis[["feature_id", "display_label"]].drop_duplicates(
        "feature_id"
    )
    labels = dict(
        zip(
            label_table["feature_id"].astype(str),
            label_table["display_label"].astype(str),
        )
    )

    builders = {
        "Figure_7": lambda: build_figure_7(
            base, effects, preterm, broad, synthesis, labels, out_figures
        ),
        "Figure_8": lambda: build_figure_8(
            base, effects, preterm, broad, synthesis, labels, out_figures
        ),
        "Figure_9": lambda: build_figure_9(
            base, effects, preterm, broad, synthesis, labels, out_figures
        ),
        "Figure_10": lambda: build_figure_10(
            base, effects, preterm, broad, synthesis, labels, out_figures
        ),
        "Figure_11": lambda: build_figure_11(
            base, effects, preterm, broad, synthesis,
            composition, targeted, labels, out_figures
        ),
    }

    output_rows = []
    design_rows = []
    for figure in EXPECTED_FIGURES:
        log(f"Building {figure} with its figure-specific visual grammar.")
        outputs, designs = builders[figure]()
        for path in outputs:
            output_rows.append(
                {
                    "figure": figure,
                    "path": str(path),
                    "format": path.suffix.lstrip("."),
                    "size_bytes": path.stat().st_size,
                }
            )
        for panel, grammar in designs.items():
            design_rows.append(
                {
                    "figure": figure,
                    "panel": panel,
                    "visual_grammar": grammar,
                }
            )

    output_manifest = pd.DataFrame(output_rows)
    output_manifest.to_csv(
        out_tables / "UTI_HostOmics_U27A3_figure_output_manifest.tsv",
        sep="\t",
        index=False,
    )

    design_manifest = pd.DataFrame(design_rows)
    design_manifest.to_csv(
        out_metadata / "UTI_HostOmics_U27A3_visual_grammar_manifest.tsv",
        sep="\t",
        index=False,
    )

    grammar_count = design_manifest.groupby("figure")[
        "visual_grammar"
    ].nunique()
    formats_per_figure = output_manifest.groupby("figure")["format"].nunique()
    produced = set(output_manifest["figure"].astype(str))
    expected = set(EXPECTED_FIGURES)

    ready = (
        produced == expected
        and all(formats_per_figure.get(figure, 0) == 3 for figure in expected)
        and all(grammar_count.get(figure, 0) >= 4 for figure in expected)
    )
    phase_decision = (
        "READY_FOR_U27A4_VISUAL_AUDIT_THEN_U27B_MANUSCRIPT_INTEGRATION"
        if ready
        else "TARGETED_VISUAL_DIVERSITY_REPAIR_REQUIRED"
    )

    pd.DataFrame(
        [
            {
                "phase": "U27A.3",
                "decision": phase_decision,
                "n_figures_expected": 5,
                "n_figures_produced": len(produced),
                "n_output_files": len(output_manifest),
                "png_svg_pdf_for_each_figure": bool(
                    all(
                        formats_per_figure.get(figure, 0) == 3
                        for figure in expected
                    )
                ),
                "figure_specific_visual_grammars_used": True,
                "all_figures_have_four_distinct_panel_grammars": bool(
                    all(grammar_count.get(figure, 0) >= 4 for figure in expected)
                ),
                "base_script": str(base_source),
                "manuscript_modified": False,
                "existing_figures_1_to_6_modified": False,
                "scientific_values_changed": False,
                "cells_treated_as_independent_replicates": False,
                "metabolic_flux_claims_used": False,
                "next_phase": (
                    "U27A.4 contact-sheet and journal-width visual audit"
                    if ready
                    else "Inspect and repair failed figure outputs"
                ),
            }
        ]
    ).to_csv(
        out_tables / "UTI_HostOmics_U27A3_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = out_results / "UTI_HostOmics_U27A3_visual_diversity_report.md"
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# Phase U27A.3 - Figure visual-diversity redesign\n\n")
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{phase_decision}**\n")
        handle.write(f"- Figures produced: **{len(produced)}/5**.\n")
        handle.write(f"- Output files: **{len(output_manifest)}**.\n")
        handle.write(
            "- All outputs were generated reproducibly from project tables "
            "and scripts.\n"
        )
        handle.write(
            "- Scientific values, module membership and interpretation "
            "boundaries were not changed.\n"
        )
        handle.write(
            "- Manuscript and Figures 1-6 were not modified.\n\n"
        )
        handle.write("## Monotony repair\n\n")
        for figure in EXPECTED_FIGURES:
            subset = design_manifest[design_manifest["figure"] == figure]
            handle.write(f"- **{figure.replace('_', ' ')}:** ")
            handle.write(
                "; ".join(
                    f"{row.panel}={row.visual_grammar}"
                    for row in subset.itertuples()
                )
                + ".\n"
            )
        handle.write("\n## Interpretation boundaries\n\n")
        handle.write(
            "- GSE252321 cellular comparisons retain biological samples as "
            "the inferential units.\n"
            "- Composite cellular support does not use Hedges g alone.\n"
            "- Metabolic panels show transcriptionally inferred pathway "
            "activity, not direct flux.\n"
            "- Pregnancy preterm-versus-term effects remain discovery-level.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": phase_decision,
        "n_figures_produced": int(len(produced)),
        "n_output_files": int(len(output_manifest)),
        "scientific_values_changed": False,
        "manuscript_modified": False,
        "existing_figures_1_to_6_modified": False,
    }
    (out_results / "UTI_HostOmics_U27A3_run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Figures produced: {len(produced)}/5")
    log(f"Output files: {len(output_manifest)}")
    log(f"Decision: {phase_decision}")
    log(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27A.3] ERROR: {exc}", file=sys.stderr)
        raise
