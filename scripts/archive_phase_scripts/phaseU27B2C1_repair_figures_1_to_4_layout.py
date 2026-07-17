#!/usr/bin/env python3
"""
Phase U27B2C1
Targeted layout and content repair for manuscript-facing Final Figures 1-4.

The repair is based on manual inspection of the U27B2B full-figure and panel
contact sheets. It preserves the U27B2A.2 locked numerical sources and changes
only panel selection, labeling, spacing and visual composition.

Major repairs
-------------
Figure 1
- Expand dataset architecture from two bulk comparators to all four datasets.
- Replace cramped workflow with a readable six-stage process.
- Shorten evidence hierarchy labels.

Figure 2
- Separate Panel A from evidence-class labels.
- Replace long evidence labels with concise manuscript-facing classes.
- Rebuild complement core as a paired-effect display.
- Reduce adjusted/factorial panels to readable top effects.
- Number, rather than fully label, crowded concordance points.

Figure 3
- Select pregnancy modules using U26C1 biological labels, not anonymous
  feature identifiers.
- Prevent complement modules from monopolizing broad pregnancy panels.
- Shorten contrast/tissue labels.
- Rebuild the pregnancy-outcome model with nonoverlapping nodes.

Figure 4
- Restrict the marker heatmap to the two strongest markers per cluster.
- Shorten biological-sample labels.
- Shorten targeted-state and population labels.
- Rebuild the TNFSF9-macrophage-Treg model.

No scientific values, source tables or manuscript text are modified.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

try:
    from PIL import Image
except ImportError:
    Image = None


VERSION = "U27B2C1_v1.0_2026-07-15"
TAG = "phaseU27B2C1_figures_1_to_4_layout_content_repair"
BASE_SCRIPT = "phaseU27B2B_build_final_figures_1_to_4.py"
DPI = 300
FIGURE_WIDTH_IN = 180 / 25.4


ISSUES = [
    ("Figure_1", "B", "Dataset panel omitted GSE280297 and GSE252321.",
     "Build a four-dataset biological-sample summary."),
    ("Figure_1", "E", "Workflow boxes and text were too small and crowded.",
     "Use a six-stage snake workflow with shorter labels."),
    ("Figure_1", "F", "Long evidence-class labels collided.",
     "Collapse to concise manuscript-facing evidence classes."),
    ("Figure_2", "A-B", "Panel B labels overlapped Panel A and its colorbar.",
     "Use a vertical evidence-class chart and a horizontal Panel A colorbar."),
    ("Figure_2", "C-E", "Titles, labels and annotations collided.",
     "Increase gutters and simplify each panel."),
    ("Figure_2", "G", "Concordance annotations were unreadably crowded.",
     "Number six priority points and provide an inset key."),
    ("Figure_3", "B/E/G", "Automatic ranking produced complement-dominated panels.",
     "Use U26C1 biological labels for curated branch-balanced selection."),
    ("Figure_3", "F", "Title was truncated.",
     "Shorten the panel title."),
    ("Figure_3", "H", "Working-model boxes and text overlapped.",
     "Rebuild as a six-node nonoverlapping model."),
    ("Figure_4", "B", "Marker labels were too dense.",
     "Use at most two markers per cluster."),
    ("Figure_4", "C-F", "Sample and targeted-state labels were too long.",
     "Use compact biological-sample and state labels."),
    ("Figure_4", "H", "Model nodes overlapped.",
     "Rebuild as a five-node cellular model."),
]


def load_base(project: Path):
    path = project / "10_scripts" / BASE_SCRIPT
    if not path.exists():
        raise FileNotFoundError(
            f"Required U27B2B base script not found: {path}"
        )
    spec = importlib.util.spec_from_file_location("u27b2b_base", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def log(message: str) -> None:
    print(f"[U27B2C1] {message}", flush=True)


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def wrap(value: object, width: int = 24) -> str:
    return "\n".join(
        textwrap.wrap(
            str(value),
            width=width,
            break_long_words=False,
        )
    )


def clean_label(value: object, width: int = 25) -> str:
    text = str(value).replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return wrap(text, width)


def panel_label(ax: plt.Axes, letter: str) -> None:
    ax.text(
        -0.12,
        1.045,
        letter,
        transform=ax.transAxes,
        fontsize=9.4,
        fontweight="bold",
        ha="left",
        va="bottom",
        clip_on=False,
    )


def panel_title(ax: plt.Axes, title: str) -> None:
    ax.set_title(
        title,
        loc="left",
        x=0.02,
        fontsize=7.7,
        fontweight="bold",
        pad=5,
    )


def finish_axis(ax: plt.Axes) -> None:
    ax.tick_params(labelsize=5.7, length=2.2, width=0.55)
    for spine in ax.spines.values():
        spine.set_linewidth(0.55)


def axis_off(ax: plt.Axes) -> None:
    ax.set_axis_off()


def add_zero(ax: plt.Axes, vertical: bool = True) -> None:
    if vertical:
        ax.axvline(0, linewidth=0.65, alpha=0.55)
    else:
        ax.axhline(0, linewidth=0.65, alpha=0.55)


def draw_box(
    ax: plt.Axes,
    xy: Tuple[float, float],
    width: float,
    height: float,
    text: str,
    fontsize: float = 5.8,
) -> None:
    box = patches.FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.02",
        linewidth=0.8,
        facecolor="white",
        edgecolor="black",
    )
    ax.add_patch(box)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
    )


def arrow(
    ax: plt.Axes,
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(
            arrowstyle="-|>",
            linewidth=0.8,
            shrinkA=2,
            shrinkB=2,
        ),
    )


def safe_heatmap(
    ax: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
    xlabel: str = "",
    ylabel: str = "",
    colorbar_orientation: str = "vertical",
    annotate: bool = False,
    annotation_size: float = 4.5,
) -> None:
    if matrix.empty:
        axis_off(ax)
        panel_title(ax, title)
        ax.text(0.5, 0.5, "No eligible values", ha="center", va="center")
        return

    values = matrix.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        finite = np.array([0.0])
    limit = max(float(np.nanmax(np.abs(finite))), 1e-6)

    image = ax.imshow(
        values,
        aspect="auto",
        cmap="coolwarm",
        norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
    )
    ax.set_xticks(np.arange(matrix.shape[1]))
    ax.set_xticklabels(
        [clean_label(value, 14) for value in matrix.columns],
        rotation=40,
        ha="right",
        fontsize=5.0,
    )
    ax.set_yticks(np.arange(matrix.shape[0]))
    ax.set_yticklabels(
        [clean_label(value, 23) for value in matrix.index],
        fontsize=5.0,
    )
    ax.set_xlabel(xlabel, fontsize=6.0)
    ax.set_ylabel(ylabel, fontsize=6.0)
    panel_title(ax, title)

    if annotate and matrix.size <= 80:
        for row in range(matrix.shape[0]):
            for column in range(matrix.shape[1]):
                value = values[row, column]
                if np.isfinite(value):
                    ax.text(
                        column,
                        row,
                        f"{value:.0f}",
                        ha="center",
                        va="center",
                        fontsize=annotation_size,
                    )

    if colorbar_orientation == "horizontal":
        colorbar = ax.figure.colorbar(
            image,
            ax=ax,
            orientation="horizontal",
            fraction=0.075,
            pad=0.20,
            aspect=28,
        )
    else:
        colorbar = ax.figure.colorbar(
            image,
            ax=ax,
            fraction=0.042,
            pad=0.025,
        )
    colorbar.ax.tick_params(labelsize=4.8, length=2)
    finish_axis(ax)


def horizontal_lollipop(
    ax: plt.Axes,
    labels: Sequence[str],
    values: Sequence[float],
    title: str,
    xlabel: str,
    label_width: int = 24,
) -> None:
    labels = list(labels)
    values = np.asarray(values, dtype=float)
    keep = np.isfinite(values)
    labels = [label for label, valid in zip(labels, keep) if valid]
    values = values[keep]
    order = np.argsort(values)
    labels = [labels[index] for index in order]
    values = values[order]
    y = np.arange(len(values))
    ax.hlines(y, 0, values, linewidth=0.9)
    ax.scatter(values, y, s=18, zorder=3)
    add_zero(ax, True)
    ax.set_yticks(y)
    ax.set_yticklabels(
        [clean_label(value, label_width) for value in labels],
        fontsize=5.1,
    )
    ax.set_xlabel(xlabel, fontsize=6.0)
    panel_title(ax, title)
    finish_axis(ax)


def evidence_class(value: object) -> str:
    text = str(value).lower()
    if "two dataset concordant" in text or "robust" in text:
        return "Robust core"
    if "one fdr dataset plus independent" in text or "provisional" in text:
        return "Provisional core"
    if "limited independent" in text or "secondary" in text:
        return "Secondary support"
    if "context divergent" in text or "divergent" in text:
        return "Context divergent"
    return clean_label(str(value).title(), 16)


def feature_text(frame: pd.DataFrame) -> pd.Series:
    columns = [
        column
        for column in ("feature_id", "display_label", "axis")
        if column in frame.columns
    ]
    if not columns:
        return pd.Series("", index=frame.index)
    text = frame[columns[0]].fillna("").astype(str)
    for column in columns[1:]:
        text = text + " " + frame[column].fillna("").astype(str)
    return text.str.lower()


def choose_features(
    annotated: pd.DataFrame,
    keywords: Sequence[str],
    n: int,
    score_column: Optional[str] = None,
) -> List[str]:
    working = annotated.drop_duplicates("feature_id").copy()
    working["_text"] = feature_text(working)
    if score_column and score_column in working.columns:
        working["_score"] = numeric(working[score_column]).abs()
    else:
        working["_score"] = 0.0

    selected: List[str] = []
    for keyword in keywords:
        matches = working[
            working["_text"].str.contains(
                keyword,
                case=False,
                na=False,
                regex=False,
            )
            & ~working["feature_id"].astype(str).isin(selected)
        ]
        if not matches.empty:
            index = matches["_score"].fillna(-np.inf).idxmax()
            selected.append(str(working.loc[index, "feature_id"]))
        if len(selected) >= n:
            return selected

    remaining = working[
        ~working["feature_id"].astype(str).isin(selected)
    ].sort_values("_score", ascending=False)
    for value in remaining["feature_id"].astype(str):
        selected.append(value)
        if len(selected) >= n:
            break
    return selected


def label_lookup(frame: pd.DataFrame) -> Dict[str, str]:
    if "feature_id" not in frame.columns:
        return {}
    labels = (
        frame["display_label"]
        if "display_label" in frame.columns
        else frame["feature_id"]
    )
    return dict(
        zip(
            frame["feature_id"].astype(str),
            labels.fillna(frame["feature_id"]).astype(str),
        )
    )


def matrix_subset(
    matrix: pd.DataFrame,
    feature_ids: Sequence[str],
    prefix: str,
    labels: Dict[str, str],
) -> pd.DataFrame:
    columns = [
        column
        for column in matrix.columns
        if str(column).startswith(prefix)
    ]
    if not columns:
        return pd.DataFrame()

    subset = (
        matrix[matrix["feature_id"].astype(str).isin(feature_ids)]
        .set_index("feature_id")[columns]
        .apply(pd.to_numeric, errors="coerce")
    )
    subset = subset.reindex(
        [value for value in feature_ids if value in subset.index]
    )
    subset.index = [labels.get(value, value) for value in subset.index]
    subset.columns = [
        str(column).split("|")[-1].strip()
        if "|" in str(column)
        else str(column)
        for column in subset.columns
    ]
    return subset


def short_sample_map(
    frame: pd.DataFrame,
    sample_column: str = "sample_id",
    condition_column: str = "condition",
) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for condition, subset in frame[[sample_column, condition_column]].drop_duplicates().groupby(condition_column):
        condition_text = "UPEC" if "upec" in str(condition).lower() else "Control"
        for index, sample in enumerate(sorted(subset[sample_column].astype(str)), start=1):
            mapping[sample] = f"{condition_text} {index}"
    return mapping


def export_rows(
    base,
    collector: List[pd.DataFrame],
    frame: pd.DataFrame,
    figure: str,
    panel: str,
    source_role: str,
    note: str = "",
) -> None:
    base.export_rows(
        collector,
        frame,
        figure,
        panel,
        source_role,
        note,
    )


def save_source_rows(
    rows: List[pd.DataFrame],
    tabledir: Path,
    figure_number: int,
) -> Path:
    if rows:
        frame = pd.concat(rows, ignore_index=True, sort=False)
    else:
        frame = pd.DataFrame(
            columns=["figure", "panel", "source_role", "source_note"]
        )
    path = (
        tabledir
        / f"UTI_HostOmics_U27B2C1_Figure_{figure_number}_source_values.tsv"
    )
    frame.to_csv(path, sep="\t", index=False)
    return path


def save_figure(
    fig: plt.Figure,
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    paths: List[Path] = []
    stem = f"UTI_HostOmics_U27B2C1_Figure_{figure_number}"
    for extension in ("png", "svg", "pdf"):
        path = outdir / f"{stem}.{extension}"
        kwargs = {"dpi": DPI} if extension == "png" else {}
        fig.savefig(path, facecolor="white", **kwargs)
        paths.append(path)
    return paths


def build_figure_1(
    base,
    store,
    outdir: Path,
    tabledir: Path,
):
    source_rows: List[pd.DataFrame] = []
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 8.9))
    grid = fig.add_gridspec(
        3,
        2,
        left=0.10,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.62,
        wspace=0.62,
        height_ratios=[1.05, 1.05, 0.92],
    )
    axes = [fig.add_subplot(grid[row, column]) for row in range(3) for column in range(2)]
    a, b, c, d, e, f = axes

    # A
    axis_off(a)
    panel_label(a, "A")
    panel_title(a, "Central biological questions")
    draw_box(a, (0.36, 0.39), 0.28, 0.16, "UPEC exposure\nand host response", 6.4)
    draw_box(a, (0.03, 0.69), 0.27, 0.15, "Cross-dataset\ninfection core")
    draw_box(a, (0.70, 0.69), 0.27, 0.15, "Pregnancy,\ntissue and outcome")
    draw_box(a, (0.03, 0.10), 0.27, 0.15, "Endocrine and\nmetabolic branches")
    draw_box(a, (0.70, 0.10), 0.27, 0.15, "Cell-resolved\nimmune localization")
    for start, end in [
        ((0.43, 0.55), (0.25, 0.69)),
        ((0.57, 0.55), (0.75, 0.69)),
        ((0.43, 0.39), (0.25, 0.25)),
        ((0.57, 0.39), (0.75, 0.25)),
    ]:
        arrow(a, start, end)
    a.text(
        0.5,
        0.92,
        "Mechanistic integration under an explicit evidence hierarchy",
        ha="center",
        va="center",
        fontsize=6.0,
        fontweight="bold",
    )
    a.set_xlim(0, 1)
    a.set_ylim(0, 1)

    # B: all four datasets
    panel_label(b, "B")
    readiness = store.table("Figure_1B", "bulk_readiness")
    design = store.table("Figure_1C", "gse280297_design")
    annotations = store.table("Figure_4A", "balanced_annotations")

    rows = []
    for row in readiness.itertuples():
        rows.append(
            {
                "dataset": str(row.dataset),
                "species": str(row.species),
                "role": str(row.biological_role),
                "biological_samples": float(row.observed_samples),
                "detail": "",
            }
        )
    existing = {row["dataset"] for row in rows}
    if "GSE280297" not in existing:
        rows.append(
            {
                "dataset": "GSE280297",
                "species": "Mus musculus",
                "role": "pregnancy, tissue and outcome",
                "biological_samples": float(design["sample_id"].nunique()),
                "detail": "bladder, uterus and placenta",
            }
        )
    if "GSE252321" not in existing:
        qc = annotations.copy()
        if "adaptive_qc_pass" in qc.columns:
            pass_values = qc["adaptive_qc_pass"].astype(str).str.lower().isin(
                ["true", "1", "yes"]
            )
            n_cells = int(pass_values.sum()) if pass_values.any() else len(qc)
        else:
            n_cells = len(qc)
        rows.append(
            {
                "dataset": "GSE252321",
                "species": "Mus musculus",
                "role": "single-cell bladder UPEC",
                "biological_samples": float(qc["sample_id"].nunique()),
                "detail": f"{n_cells:,} QC-passing cells",
            }
        )

    dataset_summary = (
        pd.DataFrame(rows)
        .drop_duplicates("dataset", keep="last")
        .sort_values("biological_samples")
    )
    y = np.arange(len(dataset_summary))
    b.barh(y, dataset_summary["biological_samples"])
    b.set_yticks(y)
    b.set_yticklabels(
        [
            f"{row.dataset}\n{clean_label(row.role, 23)}"
            for row in dataset_summary.itertuples()
        ],
        fontsize=5.0,
    )
    for position, row in enumerate(dataset_summary.itertuples()):
        label = f"n={int(row.biological_samples)}"
        if row.detail:
            label += f" | {row.detail}"
        b.text(
            row.biological_samples + max(dataset_summary["biological_samples"]) * 0.02,
            position,
            label,
            va="center",
            fontsize=4.8,
        )
    b.set_xlabel("Biological samples", fontsize=6.0)
    b.set_xlim(
        0,
        max(dataset_summary["biological_samples"]) * 1.34,
    )
    panel_title(b, "Dataset architecture")
    finish_axis(b)
    export_rows(base, source_rows, dataset_summary, "Figure_1", "B", "combined_dataset_manifest")

    # C
    panel_label(c, "C")
    group_col = "inferred_group" if "inferred_group" in design.columns else "treatment"
    counts = pd.crosstab(design[group_col], design["tissue"])
    rename_rows = {}
    for value in counts.index:
        text = str(value).lower()
        if "preterm" in text:
            rename_rows[value] = "UPEC preterm"
        elif "term" in text:
            rename_rows[value] = "UPEC term"
        elif "nonpreg" in text:
            rename_rows[value] = "UPEC nonpregnant"
        elif "pbs" in text or "mock" in text:
            rename_rows[value] = "Mock/PBS"
        else:
            rename_rows[value] = clean_label(value, 18)
    counts = counts.rename(index=rename_rows)
    safe_heatmap(
        c,
        counts.astype(float),
        "Sample and contrast structure",
        xlabel="Tissue",
        ylabel="GSE280297 group",
        annotate=True,
    )
    export_rows(base, source_rows, counts.reset_index(), "Figure_1", "C", "gse280297_design")

    # D
    panel_label(d, "D")
    modules = store.table("Figure_1D", "module_library")
    module_summary = (
        modules.groupby("axis", as_index=False)
        .agg(n_submodules=("submodule_id", "nunique"))
        .sort_values("n_submodules")
    )
    y = np.arange(len(module_summary))
    d.barh(y, module_summary["n_submodules"])
    d.set_yticks(y)
    d.set_yticklabels(
        [clean_label(value, 23) for value in module_summary["axis"]],
        fontsize=4.9,
    )
    for position, value in enumerate(module_summary["n_submodules"]):
        d.text(value + 0.12, position, str(int(value)), va="center", fontsize=4.8)
    d.set_xlabel("Submodules per biological axis", fontsize=6.0)
    panel_title(d, "Ten biological axes and 78 submodules")
    finish_axis(d)
    export_rows(base, source_rows, module_summary, "Figure_1", "D", "module_library")

    # E
    axis_off(e)
    panel_label(e, "E")
    panel_title(e, "Analytical workflow")
    stages = [
        ("U26A", "Input and\nmodule resolution"),
        ("U26B", "Within-dataset\nscoring"),
        ("U26B/C", "Independent-evidence\ncollapse"),
        ("U26D", "Single-cell\nlocalization"),
        ("U27A", "Mechanistic\nfigure library"),
        ("U27B", "Architecture and\nsource lock"),
    ]
    positions = [
        (0.03, 0.61),
        (0.36, 0.61),
        (0.69, 0.61),
        (0.69, 0.20),
        (0.36, 0.20),
        (0.03, 0.20),
    ]
    for (phase, label), (x, y0) in zip(stages, positions):
        draw_box(e, (x, y0), 0.27, 0.20, f"{phase}\n{label}", 5.3)
    for start, end in [
        ((0.30, 0.71), (0.36, 0.71)),
        ((0.63, 0.71), (0.69, 0.71)),
        ((0.825, 0.61), (0.825, 0.40)),
        ((0.69, 0.30), (0.63, 0.30)),
        ((0.36, 0.30), (0.30, 0.30)),
    ]:
        arrow(e, start, end)
    e.text(
        0.5,
        0.89,
        "Expression repair → scoring → evidence synthesis → cellular attribution",
        ha="center",
        fontsize=5.7,
        fontweight="bold",
    )
    e.text(
        0.5,
        0.06,
        "Species-native analyses; biological samples remain the inferential units.",
        ha="center",
        fontsize=5.0,
    )
    e.set_xlim(0, 1)
    e.set_ylim(0, 1)

    # F
    panel_label(f, "F")
    core = store.table("Figure_1F", "refined_core")
    evidence = (
        core["validation_class"]
        .fillna("unclassified")
        .map(evidence_class)
        .value_counts()
        .rename_axis("evidence_class")
        .reset_index(name="n_modules")
        .sort_values("n_modules")
    )
    horizontal_lollipop(
        f,
        evidence["evidence_class"],
        evidence["n_modules"],
        "Evidence hierarchy",
        "Modules",
        label_width=19,
    )
    export_rows(base, source_rows, evidence, "Figure_1", "F", "refined_core")

    paths = save_figure(fig, outdir, 1)
    save_source_rows(source_rows, tabledir, 1)
    return fig, paths, axes


def build_figure_2(base, store, outdir: Path, tabledir: Path):
    source_rows: List[pd.DataFrame] = []
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 9.6))
    grid = fig.add_gridspec(
        3,
        3,
        left=0.10,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.72,
        wspace=0.74,
        width_ratios=[1.05, 1.05, 0.98],
        height_ratios=[1.16, 1.05, 1.02],
    )
    a = fig.add_subplot(grid[0, 0:2])
    b = fig.add_subplot(grid[0, 2])
    c = fig.add_subplot(grid[1, 0])
    d = fig.add_subplot(grid[1, 1])
    e = fig.add_subplot(grid[1, 2])
    f = fig.add_subplot(grid[2, 0])
    g = fig.add_subplot(grid[2, 1:3])
    axes = [a, b, c, d, e, f, g]

    primary = store.table("Figure_2A", "primary_independent_effects")
    recurrence = store.table("Figure_2B", "recurrence_ranking")
    core = store.table("Figure_2C", "refined_core")
    labels = label_lookup(core)

    selected = choose_features(
        core.assign(
            _priority=numeric(core["independent_evidence_priority_score"])
        ),
        [
            "tlr4",
            "leptin",
            "pi3k",
            "insulin receptor",
            "irs",
            "glycogen",
            "c3a",
            "c5a",
            "opsonophag",
            "androgen receptor",
            "amino acid transport",
            "fatty acid synthesis",
        ],
        10,
        "_priority",
    )

    # A
    panel_label(a, "A")
    subset = primary[primary["feature_id"].astype(str).isin(selected)].copy()
    matrix = subset.pivot_table(
        index="feature_id",
        columns="dataset",
        values="effect_value",
        aggfunc="mean",
    )
    matrix = matrix.reindex([value for value in selected if value in matrix.index])
    matrix.index = [labels.get(value, value) for value in matrix.index]
    safe_heatmap(
        a,
        matrix,
        "Independent infection effects",
        xlabel="Independent dataset",
        ylabel="Module",
        colorbar_orientation="horizontal",
    )
    export_rows(base, source_rows, subset, "Figure_2", "A", "primary_independent_effects")

    # B
    panel_label(b, "B")
    evidence = (
        recurrence["validation_class"]
        .fillna("unclassified")
        .map(evidence_class)
        .value_counts()
        .rename_axis("evidence_class")
        .reset_index(name="n_modules")
    )
    order = ["Robust core", "Provisional core", "Secondary support", "Context divergent"]
    evidence["_order"] = evidence["evidence_class"].map(
        {value: index for index, value in enumerate(order)}
    ).fillna(len(order))
    evidence = evidence.sort_values("_order")
    x = np.arange(len(evidence))
    b.bar(x, evidence["n_modules"])
    b.set_xticks(x)
    b.set_xticklabels(
        [clean_label(value, 12) for value in evidence["evidence_class"]],
        rotation=28,
        ha="right",
        fontsize=5.0,
    )
    b.set_ylabel("Modules", fontsize=6.0)
    panel_title(b, "Evidence-class distribution")
    finish_axis(b)
    export_rows(base, source_rows, evidence, "Figure_2", "B", "recurrence_ranking")

    # C
    axis_off(c)
    panel_label(c, "C")
    panel_title(c, "TLR4–leptin–PI3K/AKT core")
    nodes = [
        ("TLR4–LPS", 0.04, 0.52),
        ("Leptin", 0.37, 0.72),
        ("IRS", 0.37, 0.34),
        ("PI3K–AKT", 0.70, 0.53),
        ("Inflammatory\nresponse", 0.70, 0.78),
        ("Glycogen/\ncarbon use", 0.70, 0.20),
    ]
    for label, x0, y0 in nodes:
        draw_box(c, (x0, y0), 0.25, 0.14, label, 5.7)
    for start, end in [
        ((0.29, 0.59), (0.37, 0.79)),
        ((0.29, 0.59), (0.37, 0.41)),
        ((0.62, 0.79), (0.70, 0.60)),
        ((0.62, 0.41), (0.70, 0.56)),
        ((0.825, 0.67), (0.825, 0.78)),
        ((0.825, 0.53), (0.825, 0.34)),
    ]:
        arrow(c, start, end)
    c.text(
        0.5,
        0.04,
        "Evidence-weighted topology; not a direct causal model.",
        ha="center",
        fontsize=4.8,
    )
    c.set_xlim(0, 1)
    c.set_ylim(0, 1)
    export_rows(
        base,
        source_rows,
        core[core["feature_id"].astype(str).isin(selected)],
        "Figure_2",
        "C",
        "refined_core",
    )

    # D
    panel_label(d, "D")
    complement = core[
        feature_text(core).str.contains(
            "complement|c3a|c5a|opsonophag",
            regex=True,
            na=False,
        )
    ].copy()
    complement["_priority"] = numeric(
        complement["independent_evidence_priority_score"]
    )
    complement = complement.nlargest(min(5, len(complement)), "_priority")
    y = np.arange(len(complement))
    infection = numeric(complement["median_effect"]).to_numpy()
    preterm = numeric(complement["preterm_vs_term_effect"]).to_numpy()
    for position, left, right in zip(y, infection, preterm):
        if np.isfinite(left) and np.isfinite(right):
            d.plot([left, right], [position, position], linewidth=0.75)
    d.scatter(infection, y + 0.07, s=18, label="infection")
    d.scatter(preterm, y - 0.07, s=18, marker="s", label="preterm vs term")
    add_zero(d, True)
    d.set_yticks(y)
    d.set_yticklabels(
        [clean_label(value, 21) for value in complement["display_label"]],
        fontsize=4.9,
    )
    d.set_xlabel("Standardized module effect", fontsize=6.0)
    d.legend(fontsize=4.6, frameon=False, loc="lower right")
    panel_title(d, "Complement core")
    finish_axis(d)
    export_rows(base, source_rows, complement, "Figure_2", "D", "refined_core")

    # E
    panel_label(e, "E")
    adjusted = store.table("Figure_2E", "gse112098_adjusted").copy()
    adjusted["_value"] = numeric(adjusted["model_estimate"])
    adjusted = adjusted.reindex(
        adjusted["_value"].abs().sort_values(ascending=False).head(7).index
    )
    horizontal_lollipop(
        e,
        adjusted["display_label"],
        adjusted["_value"],
        "Adjusted systemic comparator",
        "Age/sex-adjusted estimate",
        label_width=20,
    )
    export_rows(base, source_rows, adjusted, "Figure_2", "E", "gse112098_adjusted")

    # F
    panel_label(f, "F")
    factorial = store.table("Figure_2F", "gse186800_factorial").copy()
    contrast = factorial["contrast_id"].astype(str).str.lower()
    preferred = factorial[
        contrast.str.contains("gard|treat|infect|upec", regex=True)
        & ~contrast.str.contains("block|batch|interaction", regex=True)
    ].copy()
    if preferred.empty:
        preferred = factorial.copy()
    preferred["_value"] = numeric(preferred["model_estimate"])
    preferred = preferred.reindex(
        preferred["_value"].abs().sort_values(ascending=False).head(7).index
    )
    horizontal_lollipop(
        f,
        preferred["display_label"],
        preferred["_value"],
        "Contextual factorial effects",
        "Factorial estimate",
        label_width=19,
    )
    export_rows(base, source_rows, preferred, "Figure_2", "F", "gse186800_factorial")

    # G
    panel_label(g, "G")
    scatter = recurrence.copy()
    scatter["_x"] = numeric(scatter["weighted_directional_coherence"])
    scatter["_y"] = numeric(scatter["median_effect"])
    scatter["_priority"] = numeric(
        scatter["independent_evidence_priority_score"]
    ).fillna(0)
    scatter = scatter.dropna(subset=["_x", "_y"])
    sizes = 15 + 55 * (
        scatter["_priority"] - scatter["_priority"].min()
    ) / max(scatter["_priority"].max() - scatter["_priority"].min(), 1e-9)
    g.scatter(scatter["_x"], scatter["_y"], s=sizes, alpha=0.78)
    add_zero(g, False)
    g.set_xlabel("Weighted directional coherence", fontsize=6.0)
    g.set_ylabel("Median independent effect", fontsize=6.0)
    panel_title(g, "Evidence-weighted concordance")
    finish_axis(g)

    top = scatter.nlargest(min(6, len(scatter)), "_priority").copy()
    top = top.reset_index(drop=True)
    for index, row in top.iterrows():
        g.annotate(
            str(index + 1),
            (row["_x"], row["_y"]),
            xytext=(3, 3),
            textcoords="offset points",
            fontsize=5.0,
            fontweight="bold",
        )
    key_lines = [
        f"{index + 1}. {clean_label(row.display_label, 26).replace(chr(10), ' ')}"
        for index, row in top.iterrows()
    ]
    g.text(
        0.02,
        0.98,
        "\n".join(key_lines),
        transform=g.transAxes,
        ha="left",
        va="top",
        fontsize=4.5,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.85),
    )
    export_rows(base, source_rows, top, "Figure_2", "G", "recurrence_ranking")

    paths = save_figure(fig, outdir, 2)
    save_source_rows(source_rows, tabledir, 2)
    return fig, paths, axes


def build_figure_3(base, store, outdir: Path, tabledir: Path):
    source_rows: List[pd.DataFrame] = []
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 11.1))
    grid = fig.add_gridspec(
        4,
        2,
        left=0.11,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.66,
        wspace=0.68,
    )
    axes = [fig.add_subplot(grid[row, column]) for row in range(4) for column in range(2)]
    a, b, c, d, e, f, g, h = axes

    design = store.table("Figure_3A", "gse280297_design")
    matrix = store.table("Figure_3B", "gse280297_primary_matrix")
    coherence = store.table("Figure_3C", "cross_tissue_coherence")
    domains = store.table("Figure_3D", "decoupling_domains")
    core = store.table("Figure_3H", "refined_core")
    labels = label_lookup(core)
    annotated = core.copy()
    annotated["_priority"] = numeric(
        annotated["independent_evidence_priority_score"]
    )

    # A
    panel_label(a, "A")
    group_col = "inferred_group" if "inferred_group" in design.columns else "treatment"
    counts = pd.crosstab(design[group_col], design["tissue"])
    rename_rows = {}
    for value in counts.index:
        text = str(value).lower()
        if "preterm" in text:
            rename_rows[value] = "UPEC preterm"
        elif "term" in text:
            rename_rows[value] = "UPEC term"
        elif "nonpreg" in text:
            rename_rows[value] = "UPEC nonpregnant"
        elif "pbs" in text or "mock" in text:
            rename_rows[value] = "Mock/PBS"
        else:
            rename_rows[value] = clean_label(value, 18)
    counts = counts.rename(index=rename_rows)
    safe_heatmap(
        a,
        counts.astype(float),
        "Pregnancy and tissue design",
        xlabel="Tissue",
        ylabel="Experimental group",
        annotate=True,
    )
    export_rows(base, source_rows, counts.reset_index(), "Figure_3", "A", "gse280297_design")

    # B
    panel_label(b, "B")
    c1_ids = choose_features(
        annotated,
        [
            "core steroidogenesis",
            "androgen and testosterone biosynthesis",
            "estrogen biosynthesis",
            "cholesterol biosynthesis",
            "androgen receptor",
            "estrogen receptor",
            "pi3k-akt",
            "insulin receptor",
            "leptin",
            "glycogen",
            "c3a and c5a",
            "opsonophagocytosis",
        ],
        12,
        "_priority",
    )
    c1 = matrix_subset(matrix, c1_ids, "C1_PRETERM_VS_TERM", labels)
    safe_heatmap(
        b,
        c1,
        "Preterm versus term by tissue",
        xlabel="Tissue",
        ylabel="Branch-balanced module",
    )
    export_rows(base, source_rows, c1.reset_index(), "Figure_3", "B", "gse280297_primary_matrix")

    # C
    panel_label(c, "C")
    c1_coh = coherence[
        coherence["contrast_id"].astype(str).str.contains("C1_PRETERM_VS_TERM")
    ].copy()
    c1_coh["_score"] = numeric(c1_coh["mean_absolute_hedges_g"])
    c1_coh = c1_coh.nlargest(min(10, len(c1_coh)), "_score")
    y = np.arange(len(c1_coh))
    values = numeric(c1_coh["median_hedges_g"]).to_numpy()
    coherence_values = numeric(
        c1_coh["directional_coherence_fraction"]
    ).fillna(0).to_numpy()
    c.hlines(y, 0, values, linewidth=0.85)
    c.scatter(values, y, s=15 + 45 * coherence_values)
    add_zero(c, True)
    c.set_yticks(y)
    c.set_yticklabels(
        [clean_label(value, 22) for value in c1_coh["display_label"]],
        fontsize=4.9,
    )
    c.set_xlabel("Median Hedges g across tissues", fontsize=6.0)
    panel_title(c, "Cross-tissue coherence")
    c.text(
        0.98,
        0.03,
        "Marker size = directional coherence",
        transform=c.transAxes,
        ha="right",
        fontsize=4.6,
    )
    finish_axis(c)
    export_rows(base, source_rows, c1_coh, "Figure_3", "C", "cross_tissue_coherence")

    # D
    panel_label(d, "D")
    domains = domains.copy()
    domains["_value"] = numeric(domains["median_effect"])
    horizontal_lollipop(
        d,
        domains["domain"],
        domains["_value"],
        "Steroid synthesis–response decoupling",
        "Median preterm-versus-term effect",
        label_width=22,
    )
    export_rows(base, source_rows, domains, "Figure_3", "D", "decoupling_domains")

    # E
    panel_label(e, "E")
    c2_ids = choose_features(
        annotated,
        [
            "tlr4",
            "leptin",
            "pi3k-akt",
            "insulin receptor",
            "glycogen",
            "glycolysis",
            "lactate and hif1a",
            "c3a and c5a",
            "opsonophagocytosis",
            "core steroidogenesis",
            "amino-acid transport",
            "nrf2",
        ],
        12,
        "_priority",
    )
    c2 = matrix_subset(matrix, c2_ids, "C2_UPEC_VS_PBS_PREGNANCY", labels)
    safe_heatmap(
        e,
        c2,
        "UPEC versus PBS pregnancy",
        xlabel="Tissue",
        ylabel="Branch-balanced module",
    )
    export_rows(base, source_rows, c2.reset_index(), "Figure_3", "E", "gse280297_primary_matrix")

    # F
    panel_label(f, "F")
    c3_ids = choose_features(
        annotated,
        [
            "c3a and c5a",
            "opsonophagocytosis",
            "tlr4",
            "leptin",
            "pi3k-akt",
            "insulin receptor",
            "glycogen",
            "core steroidogenesis",
            "androgen receptor",
            "amino-acid transport",
        ],
        10,
        "_priority",
    )
    c3 = matrix_subset(
        matrix,
        c3_ids,
        "C3_INFECTED_PREGNANT_VS_NONPREGNANT",
        labels,
    )
    if not c3.empty:
        values = c3.iloc[:, 0]
        horizontal_lollipop(
            f,
            c3.index,
            values,
            "Pregnant versus nonpregnant bladder",
            "Hedges g",
            label_width=22,
        )
        export_rows(base, source_rows, c3.reset_index(), "Figure_3", "F", "gse280297_primary_matrix")
    else:
        axis_off(f)
        panel_title(f, "Pregnant versus nonpregnant bladder")
        f.text(0.5, 0.5, "No eligible C3 values", ha="center")

    # G
    panel_label(g, "G")
    g_ids = choose_features(
        annotated,
        [
            "c3 convertase",
            "c3a and c5a",
            "opsonophagocytosis",
            "complement regulators",
            "glycolysis",
            "lactate and hif1a",
            "glycogen",
            "pentose phosphate",
            "nrf2",
        ],
        9,
        "_priority",
    )
    value_columns = [
        column
        for column in matrix.columns
        if column != "feature_id"
        and (
            str(column).startswith("C1_")
            or str(column).startswith("C2_")
            or str(column).startswith("C3_")
        )
    ]
    g_matrix = (
        matrix[matrix["feature_id"].astype(str).isin(g_ids)]
        .set_index("feature_id")[value_columns]
        .apply(pd.to_numeric, errors="coerce")
        .reindex([value for value in g_ids if value in set(matrix["feature_id"].astype(str))])
    )
    g_matrix.index = [labels.get(value, value) for value in g_matrix.index]
    renamed = []
    for column in g_matrix.columns:
        text = str(column)
        prefix = text.split("_")[0]
        tissue = text.split("|")[-1].strip() if "|" in text else ""
        renamed.append(f"{prefix} {tissue}".strip())
    g_matrix.columns = renamed
    safe_heatmap(
        g,
        g_matrix,
        "Complement and inflammatory-carbon branches",
        xlabel="Contrast and tissue",
        ylabel="Module",
    )
    export_rows(base, source_rows, g_matrix.reset_index(), "Figure_3", "G", "gse280297_primary_matrix")

    # H
    axis_off(h)
    panel_label(h, "H")
    panel_title(h, "Pregnancy-outcome model")
    draw_box(h, (0.04, 0.67), 0.22, 0.15, "UPEC exposure\nin pregnancy")
    draw_box(h, (0.37, 0.75), 0.24, 0.14, "TLR4/complement\nand carbon response")
    draw_box(h, (0.37, 0.47), 0.24, 0.14, "Steroid synthesis\nand androgen branch")
    draw_box(h, (0.70, 0.62), 0.25, 0.17, "Tissue-specific\nhost state")
    draw_box(h, (0.37, 0.17), 0.24, 0.14, "Attenuated receptor\nand metabolic response")
    draw_box(h, (0.70, 0.19), 0.25, 0.17, "Preterm-associated\noutcome architecture")
    for start, end in [
        ((0.26, 0.745), (0.37, 0.82)),
        ((0.26, 0.745), (0.37, 0.54)),
        ((0.61, 0.82), (0.70, 0.70)),
        ((0.61, 0.54), (0.70, 0.67)),
        ((0.49, 0.47), (0.49, 0.31)),
        ((0.61, 0.24), (0.70, 0.27)),
        ((0.825, 0.62), (0.825, 0.36)),
    ]:
        arrow(h, start, end)
    h.text(
        0.5,
        0.04,
        "Branch-selective association; not proof of causal miscarriage biology.",
        ha="center",
        fontsize=4.8,
    )
    h.set_xlim(0, 1)
    h.set_ylim(0, 1)
    export_rows(base, source_rows, domains, "Figure_3", "H", "decoupling_domains")

    paths = save_figure(fig, outdir, 3)
    save_source_rows(source_rows, tabledir, 3)
    return fig, paths, axes


def build_figure_4(base, store, outdir: Path, tabledir: Path):
    source_rows: List[pd.DataFrame] = []
    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 11.0))
    grid = fig.add_gridspec(
        4,
        2,
        left=0.10,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.69,
        wspace=0.62,
    )
    axes = [fig.add_subplot(grid[row, column]) for row in range(4) for column in range(2)]
    a, b, c, d, e, f, g, h = axes

    annotations = store.table("Figure_4A", "balanced_annotations")
    markers = store.table("Figure_4B", "cluster_markers")
    refinement = store.table("Figure_4B", "refinement_map")
    broad = store.table("Figure_4C", "broad_composition")
    subtype = store.table("Figure_4D", "subtype_composition")
    targeted = store.table("Figure_4E", "targeted_states")
    core_attr = store.table("Figure_4G", "core_cellular_attribution")
    broad_effects = store.table("Figure_4G", "broad_effect_reliability")

    # A
    panel_label(a, "A")
    merged = base.merge_refined_labels(annotations, refinement)
    plot_data = (
        merged.sample(12000, random_state=17)
        if len(merged) > 12000
        else merged.copy()
    )
    categories = pd.Categorical(plot_data["plot_label"])
    a.scatter(
        numeric(plot_data["corrected_component_1"]),
        numeric(plot_data["corrected_component_2"]),
        c=categories.codes,
        cmap="tab20",
        s=1.6,
        alpha=0.70,
        linewidths=0,
    )
    a.set_xlabel("Corrected component 1", fontsize=6.0)
    a.set_ylabel("Corrected component 2", fontsize=6.0)
    panel_title(a, "Balanced cellular embedding")
    finish_axis(a)
    legend_labels = list(categories.categories)
    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markersize=3,
            label=clean_label(label, 15),
        )
        for label in legend_labels[:10]
    ]
    if handles:
        a.legend(
            handles=handles,
            loc="lower left",
            fontsize=4.2,
            frameon=False,
            ncol=2,
        )
    export_rows(
        base,
        source_rows,
        plot_data[
            [
                "cell_id",
                "sample_id",
                "condition",
                "cluster",
                "plot_label",
                "corrected_component_1",
                "corrected_component_2",
            ]
        ],
        "Figure_4",
        "A",
        "balanced_annotations",
        "subsampled for plotting when >12,000 cells",
    )

    # B
    panel_label(b, "B")
    top_markers = markers.copy()
    if "rank" in top_markers.columns:
        top_markers = top_markers[numeric(top_markers["rank"]) <= 2]
    value_column = (
        "specificity_difference"
        if "specificity_difference" in top_markers.columns
        else "cluster_mean_log_expression"
    )
    marker_matrix = top_markers.pivot_table(
        index="gene_symbol",
        columns="cluster",
        values=value_column,
        aggfunc="max",
    ).fillna(0)
    if marker_matrix.shape[0] > 28:
        marker_matrix["_max"] = marker_matrix.abs().max(axis=1)
        marker_matrix = (
            marker_matrix.sort_values("_max", ascending=False)
            .head(28)
            .drop(columns="_max")
        )
    safe_heatmap(
        b,
        marker_matrix,
        "Cluster-marker validation",
        xlabel="Cluster",
        ylabel="Top marker",
    )
    export_rows(base, source_rows, top_markers, "Figure_4", "B", "cluster_markers")
    export_rows(base, source_rows, refinement, "Figure_4", "B", "refinement_map")

    sample_labels = short_sample_map(broad)

    # C
    panel_label(c, "C")
    composition = broad.pivot_table(
        index="sample_id",
        columns="refined_broad_cell_type",
        values="fraction_of_QC_cells",
        aggfunc="sum",
        fill_value=0,
    )
    bottom = np.zeros(len(composition))
    x = np.arange(len(composition))
    for column in composition.columns:
        values = numeric(composition[column]).fillna(0).to_numpy()
        c.bar(x, values, bottom=bottom, label=clean_label(column, 14))
        bottom += values
    c.set_xticks(x)
    c.set_xticklabels(
        [sample_labels.get(value, value) for value in composition.index],
        rotation=25,
        ha="right",
        fontsize=5.1,
    )
    c.set_ylabel("Fraction of QC-passing cells", fontsize=6.0)
    panel_title(c, "Broad-cell composition")
    c.legend(
        fontsize=4.1,
        frameon=False,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.99),
    )
    finish_axis(c)
    export_rows(base, source_rows, broad, "Figure_4", "C", "broad_composition")

    # D
    panel_label(d, "D")
    subtype = subtype.copy()
    subtype["fraction_of_QC_cells"] = numeric(subtype["fraction_of_QC_cells"])
    top_subtypes = (
        subtype.groupby("refined_cell_subtype")["fraction_of_QC_cells"]
        .mean()
        .sort_values(ascending=False)
        .head(11)
        .index
    )
    subtype_matrix = (
        subtype[subtype["refined_cell_subtype"].isin(top_subtypes)]
        .pivot_table(
            index="refined_cell_subtype",
            columns="sample_id",
            values="fraction_of_QC_cells",
            aggfunc="sum",
            fill_value=0,
        )
    )
    subtype_matrix.columns = [
        sample_labels.get(value, value) for value in subtype_matrix.columns
    ]
    safe_heatmap(
        d,
        subtype_matrix,
        "Refined immune subtypes",
        xlabel="Biological sample",
        ylabel="Refined subtype",
    )
    export_rows(
        base,
        source_rows,
        subtype[subtype["refined_cell_subtype"].isin(top_subtypes)],
        "Figure_4",
        "D",
        "subtype_composition",
    )

    targeted = targeted.copy()
    targeted["value"] = numeric(targeted["value"])
    targeted_text = targeted["targeted_measure"].astype(str).str.lower()

    # E
    panel_label(e, "E")
    tnfsf9 = targeted[
        targeted_text.str.contains("tnfsf9|cd137l", regex=True)
    ].copy()
    measure_map = {}
    for value in tnfsf9["targeted_measure"].drop_duplicates():
        text = str(value).lower()
        measure_map[value] = "TNFSF9-high" if "high" in text else "TNFSF9+"
    measures = list(measure_map)
    conditions = tnfsf9["condition"].drop_duplicates().tolist()
    x = np.arange(len(measures))
    width = 0.34
    for index, condition in enumerate(conditions):
        values = [
            tnfsf9[
                (tnfsf9["condition"] == condition)
                & (tnfsf9["targeted_measure"] == measure)
            ]["value"].mean()
            for measure in measures
        ]
        e.bar(
            x + (index - (len(conditions) - 1) / 2) * width,
            values,
            width=width,
            label="UPEC" if "upec" in str(condition).lower() else "Control",
        )
    e.set_xticks(x)
    e.set_xticklabels([measure_map[value] for value in measures], fontsize=5.2)
    e.set_ylabel("Fraction within parent population", fontsize=6.0)
    e.legend(fontsize=4.7, frameon=False)
    panel_title(e, "TNFSF9-positive macrophage states")
    finish_axis(e)
    export_rows(base, source_rows, tnfsf9, "Figure_4", "E", "targeted_states")

    # F
    panel_label(f, "F")
    treg = targeted[
        targeted_text.str.contains("treg|foxp3|regulatory", regex=True)
    ].copy()
    measure_map = {}
    for value in treg["targeted_measure"].drop_duplicates():
        text = str(value).lower()
        measure_map[value] = "Expanded Treg-like" if "expanded" in text else "Strict Treg-like"
    measures = list(measure_map)
    conditions = treg["condition"].drop_duplicates().tolist()
    x = np.arange(len(measures))
    for index, condition in enumerate(conditions):
        values = [
            treg[
                (treg["condition"] == condition)
                & (treg["targeted_measure"] == measure)
            ]["value"].mean()
            for measure in measures
        ]
        f.bar(
            x + (index - (len(conditions) - 1) / 2) * width,
            values,
            width=width,
            label="UPEC" if "upec" in str(condition).lower() else "Control",
        )
    f.set_xticks(x)
    f.set_xticklabels(
        [clean_label(measure_map[value], 12) for value in measures],
        fontsize=5.0,
    )
    f.set_ylabel("Fraction within parent population", fontsize=6.0)
    f.legend(fontsize=4.7, frameon=False)
    panel_title(f, "Strict and expanded Treg-like states")
    finish_axis(f)
    export_rows(base, source_rows, treg, "Figure_4", "F", "targeted_states")

    # G
    panel_label(g, "G")
    core_features = choose_features(
        core_attr.assign(
            _priority=numeric(core_attr["top_population_composite_score"])
        ),
        [
            "tlr4",
            "leptin",
            "pi3k",
            "insulin receptor",
            "glycogen",
            "c3a",
            "c5a",
            "opsonophag",
            "androgen receptor",
            "amino-acid transport",
        ],
        10,
        "_priority",
    )
    localization = broad_effects[
        broad_effects["feature_id"].astype(str).isin(core_features)
    ].copy()
    localization_matrix = localization.pivot_table(
        index="feature_id",
        columns="population",
        values="module_mean_gene_log2FC",
        aggfunc="mean",
    )
    lookup = label_lookup(core_attr)
    localization_matrix.index = [
        lookup.get(value, value) for value in localization_matrix.index
    ]
    population_map = {
        "NK cell": "NK",
        "T cell": "T",
        "cycling immune": "Cycling",
        "dendritic": "Dendritic",
        "macrophage-monocyte": "Mac/mono",
        "macrophage/monocyte": "Mac/mono",
        "neutrophil": "Neutrophil",
    }
    localization_matrix.columns = [
        population_map.get(str(value), clean_label(value, 12))
        for value in localization_matrix.columns
    ]
    safe_heatmap(
        g,
        localization_matrix,
        "Core-module cellular localization",
        xlabel="Broad immune population",
        ylabel="Core module",
    )
    export_rows(base, source_rows, localization, "Figure_4", "G", "broad_effect_reliability")

    # H
    axis_off(h)
    panel_label(h, "H")
    panel_title(h, "TNFSF9–macrophage–Treg model")
    draw_box(h, (0.05, 0.66), 0.20, 0.15, "UPEC")
    draw_box(h, (0.38, 0.73), 0.25, 0.15, "Myeloid expansion\nand activation")
    draw_box(h, (0.38, 0.43), 0.25, 0.15, "TNFSF9-positive/\nhigh macrophages")
    draw_box(h, (0.70, 0.62), 0.25, 0.17, "T-cell and dendritic\nmodule localization")
    draw_box(h, (0.38, 0.14), 0.25, 0.15, "Strict/expanded\nTreg-like states")
    draw_box(h, (0.70, 0.17), 0.25, 0.17, "Regulatory–inflammatory\nbalance")
    for start, end in [
        ((0.25, 0.735), (0.38, 0.80)),
        ((0.25, 0.735), (0.38, 0.50)),
        ((0.63, 0.80), (0.70, 0.70)),
        ((0.63, 0.50), (0.70, 0.67)),
        ((0.50, 0.43), (0.50, 0.29)),
        ((0.63, 0.21), (0.70, 0.25)),
        ((0.825, 0.62), (0.825, 0.34)),
    ]:
        arrow(h, start, end)
    h.text(
        0.5,
        0.04,
        "Descriptive cellular attribution: n=2 control and n=2 UPEC samples.",
        ha="center",
        fontsize=4.8,
    )
    h.set_xlim(0, 1)
    h.set_ylim(0, 1)
    export_rows(base, source_rows, targeted, "Figure_4", "H", "targeted_states")
    export_rows(base, source_rows, core_attr, "Figure_4", "H", "core_cellular_attribution")

    paths = save_figure(fig, outdir, 4)
    save_source_rows(source_rows, tabledir, 4)
    return fig, paths, axes


def panel_crops(
    fig: plt.Figure,
    axes: Sequence[plt.Axes],
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    if Image is None:
        return []

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.canvas.get_width_height()
    buffer = np.asarray(fig.canvas.buffer_rgba())
    image = Image.fromarray(buffer)
    paths: List[Path] = []

    for index, axis in enumerate(axes):
        bbox = axis.get_tightbbox(renderer).expanded(1.06, 1.10)
        x0 = max(int(bbox.x0), 0)
        y0 = max(int(height - bbox.y1), 0)
        x1 = min(int(bbox.x1), width)
        y1 = min(int(height - bbox.y0), height)
        crop = image.crop((x0, y0, x1, y1))
        letter = chr(ord("A") + index)
        path = (
            outdir
            / f"UTI_HostOmics_U27B2C1_Figure_{figure_number}_panel_{letter}.png"
        )
        crop.save(path)
        paths.append(path)
    return paths


def export_audit(
    figure_paths: Sequence[Path],
    tabledir: Path,
) -> pd.DataFrame:
    rows = []
    for path in figure_paths:
        row = {
            "path": str(path),
            "filename": path.name,
            "format": path.suffix.lower().lstrip("."),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "png_width_px": "",
            "png_height_px": "",
        }
        if path.suffix.lower() == ".png" and Image is not None:
            with Image.open(path) as image:
                row["png_width_px"], row["png_height_px"] = image.size
        rows.append(row)
    audit = pd.DataFrame(rows)
    audit.to_csv(
        tabledir / "UTI_HostOmics_U27B2C1_export_audit.tsv",
        sep="\t",
        index=False,
    )
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    base = load_base(project)
    registry, panel_map = base.get_registry(project)
    store = base.SourceStore(registry)

    outfig = project / "06_figures" / TAG
    outtables = project / "06_tables" / TAG
    outresults = project / "05_results" / TAG
    outmetadata = project / "03_metadata" / TAG
    cropdir = outfig / "panel_crops"

    for directory in (outfig, outtables, outresults, outmetadata, cropdir):
        directory.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        ISSUES,
        columns=[
            "figure",
            "panel",
            "observed_issue",
            "implemented_repair",
        ],
    ).to_csv(
        outtables / "UTI_HostOmics_U27B2C1_visual_issue_repair_manifest.tsv",
        sep="\t",
        index=False,
    )

    figure_paths: List[Path] = []
    crop_paths: List[Path] = []

    builders = [
        (1, build_figure_1),
        (2, build_figure_2),
        (3, build_figure_3),
        (4, build_figure_4),
    ]

    for number, builder in builders:
        log(f"Repairing Final Figure {number}.")
        fig, paths, axes = builder(
            base,
            store,
            outfig,
            outtables,
        )
        figure_paths.extend(paths)
        crop_paths.extend(
            panel_crops(fig, axes, cropdir, number)
        )
        plt.close(fig)

    png_paths = [
        path for path in figure_paths
        if path.suffix.lower() == ".png"
    ]
    base.make_contact_sheet(
        png_paths,
        outfig / "UTI_HostOmics_U27B2C1_full_figure_contact_sheet.png",
        columns=2,
        cell_width=1100,
    )
    base.make_contact_sheet(
        crop_paths,
        outfig / "UTI_HostOmics_U27B2C1_panel_contact_sheet.png",
        columns=4,
        cell_width=700,
    )

    audit = export_audit(figure_paths, outtables)

    build_manifest = panel_map[
        panel_map["final_figure"].isin(
            ["Figure_1", "Figure_2", "Figure_3", "Figure_4"]
        )
    ].copy()
    build_manifest = build_manifest.merge(
        registry[
            [
                "panel_key",
                "source_role",
                "locked_path",
                "lock_status",
            ]
        ],
        on="panel_key",
        how="left",
    )
    build_manifest.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B2C1_Figures_1_to_4_build_manifest.tsv",
        sep="\t",
        index=False,
    )

    expected_panels = 29
    panel_count = build_manifest["panel_key"].nunique()
    expected_exports = 12
    export_count = int(audit["exists"].sum())
    nonempty = bool((audit["size_bytes"] > 0).all())
    contact_sheets = all(
        path.exists()
        for path in [
            outfig / "UTI_HostOmics_U27B2C1_full_figure_contact_sheet.png",
            outfig / "UTI_HostOmics_U27B2C1_panel_contact_sheet.png",
        ]
    )

    if (
        panel_count == expected_panels
        and export_count == expected_exports
        and nonempty
        and contact_sheets
        and len(crop_paths) == expected_panels
    ):
        decision = "READY_FOR_U27B2C2_FINAL_FIGURES_1_TO_4_VISUAL_AUDIT"
    else:
        decision = "TARGETED_U27B2C1_EXPORT_REPAIR_REQUIRED"

    pd.DataFrame(
        [
            {
                "phase": "U27B2C1",
                "decision": decision,
                "figures_repaired": len(png_paths),
                "panels_expected": expected_panels,
                "panels_in_manifest": panel_count,
                "panel_crops_present": len(crop_paths),
                "exports_expected": expected_exports,
                "exports_present": export_count,
                "nonempty_exports": nonempty,
                "contact_sheets_present": contact_sheets,
                "locked_numerical_sources_preserved": True,
                "scientific_values_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B2C2 manual final visual audit"
                    if decision.startswith("READY_FOR_U27B2C2")
                    else "Repair missing exports or panel crops"
                ),
            }
        ]
    ).to_csv(
        outtables / "UTI_HostOmics_U27B2C1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B2C1_figures_1_to_4_repair_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2C1 - Figures 1-4 layout and content repair\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Figures repaired: **4/4**.\n")
        handle.write(
            f"- Frozen panels represented: **{panel_count}/29**.\n"
        )
        handle.write(
            f"- PNG/SVG/PDF exports present: "
            f"**{export_count}/{expected_exports}**.\n"
        )
        handle.write(
            f"- Panel crops present: **{len(crop_paths)}/29**.\n\n"
        )

        handle.write("## Principal repairs\n\n")
        handle.write(
            "- Figure 1 now represents all four datasets and uses compact "
            "workflow and evidence-hierarchy panels.\n"
            "- Figure 2 separates evidence labels from the independent-effect "
            "heatmap and removes crowded concordance labels.\n"
            "- Figure 3 uses branch-balanced biological selection from U26C1 "
            "labels instead of anonymous effect ranking.\n"
            "- Figure 4 reduces marker density, shortens sample/state labels "
            "and rebuilds the cellular model.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "All numerical rendering continues to derive from the U27B2A.2 "
            "locked registry. The repair changes only module selection for "
            "display, labeling, panel geometry and annotation density.\n"
        )

    (
        outresults / "UTI_HostOmics_U27B2C1_run_manifest.json"
    ).write_text(
        json.dumps(
            {
                "version": VERSION,
                "decision": decision,
                "figures_repaired": len(png_paths),
                "panels": panel_count,
                "exports": export_count,
                "panel_crops": len(crop_paths),
                "locked_sources_preserved": True,
                "scientific_values_changed": False,
                "manuscript_modified": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log(f"Figures repaired: {len(png_paths)}/4")
    log(f"Panels represented: {panel_count}/29")
    log(f"Exports present: {export_count}/{expected_exports}")
    log(f"Panel crops: {len(crop_paths)}/29")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2C1] ERROR: {exc}", file=sys.stderr)
        raise
