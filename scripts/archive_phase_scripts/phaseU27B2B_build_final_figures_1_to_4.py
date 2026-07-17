#!/usr/bin/env python3
"""
Phase U27B2B
Build manuscript-facing Final Figures 1-4 from the exact locked source registry.

Outputs
-------
- Final Figures 1-4 in PNG, SVG and PDF.
- Panel-level source-data exports.
- Figure/panel build manifests.
- Full-figure and panel contact sheets.
- Technical export audit and phase decision.

The script uses only source tables locked in U27B2A.2. Legacy composite
figures are not used as numerical sources.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

try:
    from PIL import Image, ImageOps, ImageDraw
except ImportError:
    Image = None
    ImageOps = None
    ImageDraw = None


VERSION = "U27B2B_v1.0_2026-07-15"
TAG = "phaseU27B2B_final_figures_1_to_4_build"
LOCK_TAG = "phaseU27B2A2_final_panel_source_lock"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"

FIGURE_WIDTH_IN = 180 / 25.4
DPI = 300

PANEL_TITLES = {
    "Figure_1": {
        "A": "Central biological questions",
        "B": "Dataset architecture",
        "C": "Sample and contrast structure",
        "D": "Ten axes and 78 submodules",
        "E": "Analytical workflow",
        "F": "Evidence hierarchy",
    },
    "Figure_2": {
        "A": "Independent infection effects",
        "B": "Evidence-class distribution",
        "C": "TLR4-leptin-PI3K/AKT core",
        "D": "Complement core",
        "E": "Adjusted systemic comparator",
        "F": "Contextual factorial comparator",
        "G": "Evidence-weighted concordance",
    },
    "Figure_3": {
        "A": "Pregnancy and tissue design",
        "B": "Preterm versus term by tissue",
        "C": "Cross-tissue coherence",
        "D": "Steroid synthesis-response decoupling",
        "E": "UPEC versus PBS pregnancy",
        "F": "Pregnant versus nonpregnant infected bladder",
        "G": "Complement and inflammatory-carbon architecture",
        "H": "Pregnancy-outcome working model",
    },
    "Figure_4": {
        "A": "Balanced cellular embedding",
        "B": "Cluster-marker validation",
        "C": "Broad-cell composition",
        "D": "Refined immune subtypes",
        "E": "TNFSF9-positive macrophage states",
        "F": "Strict and expanded Treg-like states",
        "G": "Core-module cellular localization",
        "H": "TNFSF9-macrophage-Treg model",
    },
}


def log(message: str) -> None:
    print(f"[U27B2B] {message}", flush=True)


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def read_table(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        compression="infer",
        low_memory=False,
    )


def wrap(value: object, width: int = 24) -> str:
    return "\n".join(
        textwrap.wrap(str(value), width=width, break_long_words=False)
    )


def clean_label(value: object, width: int = 28) -> str:
    text = str(value)
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return wrap(text, width=width)


def panel_label(ax: plt.Axes, letter: str) -> None:
    ax.text(
        -0.11,
        1.055,
        letter,
        transform=ax.transAxes,
        fontsize=10,
        fontweight="bold",
        ha="left",
        va="top",
    )


def panel_title(ax: plt.Axes, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=8.2, fontweight="bold", pad=7)


def finish_axis(ax: plt.Axes) -> None:
    ax.tick_params(labelsize=6.2, length=2.5, width=0.6)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)


def add_zero_line(ax: plt.Axes, vertical: bool = True) -> None:
    if vertical:
        ax.axvline(0, linewidth=0.7, alpha=0.55)
    else:
        ax.axhline(0, linewidth=0.7, alpha=0.55)


def axis_off(ax: plt.Axes) -> None:
    ax.set_axis_off()


def get_registry(
    project: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    registry_path = (
        project
        / "03_metadata"
        / LOCK_TAG
        / "UTI_HostOmics_U27B2A2_final_locked_panel_source_registry.tsv"
    )
    panel_map_path = (
        project
        / "03_metadata"
        / ARCH_TAG
        / "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv"
    )
    if not registry_path.exists():
        raise FileNotFoundError(f"Missing source registry: {registry_path}")
    if not panel_map_path.exists():
        raise FileNotFoundError(f"Missing panel map: {panel_map_path}")

    registry = pd.read_csv(registry_path, sep="\t", low_memory=False)
    panel_map = pd.read_csv(panel_map_path, sep="\t", low_memory=False)
    return registry, panel_map


class SourceStore:
    def __init__(self, registry: pd.DataFrame):
        self.registry = registry.copy()
        self.cache: Dict[str, pd.DataFrame] = {}

    def paths(self, panel_key: str, role: Optional[str] = None) -> List[str]:
        subset = self.registry[
            self.registry["panel_key"].astype(str) == panel_key
        ].copy()
        if role is not None:
            subset = subset[
                subset["source_role"].astype(str) == role
            ]
        paths = subset["locked_path"].astype(str).drop_duplicates().tolist()
        return paths

    def path(self, panel_key: str, role: str) -> str:
        paths = self.paths(panel_key, role)
        if len(paths) != 1:
            raise RuntimeError(
                f"Expected exactly one path for {panel_key}/{role}; "
                f"observed {len(paths)}."
            )
        return paths[0]

    def table(self, panel_key: str, role: str) -> pd.DataFrame:
        path = self.path(panel_key, role)
        if path not in self.cache:
            self.cache[path] = read_table(path)
        return self.cache[path].copy()


def feature_text(frame: pd.DataFrame) -> pd.Series:
    columns = [
        column
        for column in ("feature_id", "display_label", "axis")
        if column in frame.columns
    ]
    if not columns:
        return pd.Series("", index=frame.index)
    result = frame[columns[0]].fillna("").astype(str)
    for column in columns[1:]:
        result = result + " " + frame[column].fillna("").astype(str)
    return result.str.lower()


def select_features(
    frame: pd.DataFrame,
    keywords: Sequence[str],
    n: int,
    score_column: Optional[str] = None,
    absolute_score: bool = True,
) -> List[str]:
    if "feature_id" not in frame.columns:
        return []

    working = frame.drop_duplicates("feature_id").copy()
    working["_text"] = feature_text(working)
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
        ].copy()
        if matches.empty:
            continue

        if score_column and score_column in matches.columns:
            score = numeric(matches[score_column])
            if absolute_score:
                score = score.abs()
            index = score.fillna(-np.inf).idxmax()
        else:
            index = matches.index[0]
        selected.append(str(matches.loc[index, "feature_id"]))
        if len(selected) >= n:
            return selected

    remaining = working[
        ~working["feature_id"].astype(str).isin(selected)
    ].copy()
    if score_column and score_column in remaining.columns:
        score = numeric(remaining[score_column])
        if absolute_score:
            score = score.abs()
        remaining = remaining.assign(_score=score).sort_values(
            "_score", ascending=False
        )

    for value in remaining["feature_id"].astype(str):
        selected.append(value)
        if len(selected) >= n:
            break

    return selected


def label_lookup(frame: pd.DataFrame) -> Dict[str, str]:
    if "feature_id" not in frame.columns:
        return {}
    label_column = (
        "display_label" if "display_label" in frame.columns else "feature_id"
    )
    return dict(
        zip(
            frame["feature_id"].astype(str),
            frame[label_column].fillna(frame["feature_id"]).astype(str),
        )
    )


def safe_heatmap(
    ax: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
    xlabel: str = "",
    ylabel: str = "",
    annotate: bool = False,
    max_annotations: int = 60,
) -> None:
    if matrix.empty:
        axis_off(ax)
        ax.text(0.5, 0.5, "No eligible values", ha="center", va="center")
        panel_title(ax, title)
        return

    values = matrix.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        finite = np.array([0.0])

    maximum = max(float(np.nanmax(np.abs(finite))), 1e-6)
    image = ax.imshow(
        values,
        aspect="auto",
        cmap="coolwarm",
        norm=TwoSlopeNorm(vmin=-maximum, vcenter=0, vmax=maximum),
    )
    ax.set_xticks(np.arange(matrix.shape[1]))
    ax.set_xticklabels(
        [clean_label(value, 16) for value in matrix.columns],
        rotation=45,
        ha="right",
        fontsize=5.5,
    )
    ax.set_yticks(np.arange(matrix.shape[0]))
    ax.set_yticklabels(
        [clean_label(value, 24) for value in matrix.index],
        fontsize=5.4,
    )
    ax.set_xlabel(xlabel, fontsize=6.5)
    ax.set_ylabel(ylabel, fontsize=6.5)
    panel_title(ax, title)

    if annotate and matrix.size <= max_annotations:
        for row in range(matrix.shape[0]):
            for column in range(matrix.shape[1]):
                value = values[row, column]
                if np.isfinite(value):
                    ax.text(
                        column,
                        row,
                        f"{value:.2f}",
                        ha="center",
                        va="center",
                        fontsize=4.7,
                    )

    colorbar = ax.figure.colorbar(image, ax=ax, fraction=0.045, pad=0.02)
    colorbar.ax.tick_params(labelsize=5.3, length=2)


def horizontal_lollipop(
    ax: plt.Axes,
    labels: Sequence[str],
    values: Sequence[float],
    title: str,
    xlabel: str,
) -> None:
    labels = list(labels)
    values = np.asarray(values, dtype=float)
    order = np.argsort(values)
    labels = [labels[index] for index in order]
    values = values[order]
    positions = np.arange(len(values))

    ax.hlines(positions, 0, values, linewidth=1.0)
    ax.scatter(values, positions, s=22, zorder=3)
    add_zero_line(ax, vertical=True)
    ax.set_yticks(positions)
    ax.set_yticklabels(
        [clean_label(value, 28) for value in labels],
        fontsize=5.5,
    )
    ax.set_xlabel(xlabel, fontsize=6.5)
    panel_title(ax, title)
    finish_axis(ax)


def export_rows(
    collector: List[pd.DataFrame],
    frame: pd.DataFrame,
    figure: str,
    panel: str,
    source_role: str,
    note: str = "",
) -> None:
    if frame is None:
        return
    copy = frame.copy()
    copy.insert(0, "source_note", note)
    copy.insert(0, "source_role", source_role)
    copy.insert(0, "panel", panel)
    copy.insert(0, "figure", figure)
    collector.append(copy)


def draw_box(
    ax: plt.Axes,
    xy: Tuple[float, float],
    width: float,
    height: float,
    text: str,
    linewidth: float = 0.9,
    fontsize: float = 6.4,
) -> patches.FancyBboxPatch:
    box = patches.FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.025",
        linewidth=linewidth,
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
    return box


def arrow(
    ax: plt.Axes,
    start: Tuple[float, float],
    end: Tuple[float, float],
    linestyle: str = "-",
) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(
            arrowstyle="-|>",
            linewidth=0.9,
            linestyle=linestyle,
            shrinkA=2,
            shrinkB=2,
        ),
    )


def build_figure_1(
    store: SourceStore,
    registry: pd.DataFrame,
    outdir: Path,
    tabledir: Path,
) -> Tuple[plt.Figure, List[Path]]:
    source_rows: List[pd.DataFrame] = []
    fig, axes = plt.subplots(
        3,
        2,
        figsize=(FIGURE_WIDTH_IN, 9.3),
        layout="constrained",
    )
    ax = axes.ravel()

    # A
    a = ax[0]
    axis_off(a)
    panel_label(a, "A")
    panel_title(a, PANEL_TITLES["Figure_1"]["A"])
    draw_box(a, (0.35, 0.39), 0.30, 0.18, "UPEC exposure\nand host response", fontsize=7)
    draw_box(a, (0.03, 0.70), 0.28, 0.16, "Cross-dataset\ninfection core")
    draw_box(a, (0.69, 0.70), 0.28, 0.16, "Pregnancy,\ntissue and outcome")
    draw_box(a, (0.03, 0.08), 0.28, 0.16, "Endocrine and\nmetabolic branches")
    draw_box(a, (0.69, 0.08), 0.28, 0.16, "Cell-resolved\nimmune localization")
    for start, end in [
        ((0.43, 0.57), (0.27, 0.70)),
        ((0.57, 0.57), (0.73, 0.70)),
        ((0.43, 0.39), (0.27, 0.24)),
        ((0.57, 0.39), (0.73, 0.24)),
    ]:
        arrow(a, start, end)
    a.text(
        0.5,
        0.92,
        "Mechanistic integration under an explicit evidence hierarchy",
        ha="center",
        va="center",
        fontsize=6.5,
        fontweight="bold",
    )
    a.set_xlim(0, 1)
    a.set_ylim(0, 1)

    # B
    b = ax[1]
    panel_label(b, "B")
    readiness = store.table("Figure_1B", "bulk_readiness")
    readiness = readiness.copy()
    readiness["observed_samples"] = numeric(readiness["observed_samples"])
    readiness["canonical_genes"] = numeric(readiness["canonical_genes"])
    readiness = readiness.sort_values("observed_samples", ascending=True)
    y = np.arange(len(readiness))
    b.barh(y, readiness["observed_samples"].fillna(0))
    b.set_yticks(y)
    b.set_yticklabels(
        [
            f"{row.dataset}\n{row.species} | {clean_label(row.biological_role, 22)}"
            for row in readiness.itertuples()
        ],
        fontsize=5.2,
    )
    b.set_xlabel("Biological samples", fontsize=6.5)
    panel_title(b, PANEL_TITLES["Figure_1"]["B"])
    finish_axis(b)
    export_rows(source_rows, readiness, "Figure_1", "B", "bulk_readiness")

    # C
    c = ax[2]
    panel_label(c, "C")
    design = store.table("Figure_1C", "gse280297_design")
    group_col = "inferred_group" if "inferred_group" in design.columns else "treatment"
    counts = pd.crosstab(design[group_col], design["tissue"])
    counts = counts.loc[counts.sum(axis=1).sort_values(ascending=False).index]
    safe_heatmap(
        c,
        counts.astype(float),
        PANEL_TITLES["Figure_1"]["C"],
        xlabel="Tissue",
        ylabel="GSE280297 analysis group",
        annotate=True,
        max_annotations=80,
    )
    export_rows(source_rows, counts.reset_index(), "Figure_1", "C", "gse280297_design")

    # D
    d = ax[3]
    panel_label(d, "D")
    modules = store.table("Figure_1D", "module_library")
    module_summary = (
        modules.groupby("axis", as_index=False)
        .agg(
            n_submodules=("submodule_id", "nunique"),
            median_genes=("n_genes", lambda values: numeric(values).median()),
        )
        .sort_values("n_submodules")
    )
    positions = np.arange(len(module_summary))
    d.barh(positions, module_summary["n_submodules"])
    d.set_yticks(positions)
    d.set_yticklabels(
        [clean_label(value, 28) for value in module_summary["axis"]],
        fontsize=5.1,
    )
    d.set_xlabel("Submodules per biological axis", fontsize=6.5)
    panel_title(d, PANEL_TITLES["Figure_1"]["D"])
    for position, count in zip(positions, module_summary["n_submodules"]):
        d.text(count + 0.15, position, str(int(count)), va="center", fontsize=5)
    finish_axis(d)
    export_rows(source_rows, module_summary, "Figure_1", "D", "module_library")

    # E
    e = ax[4]
    panel_label(e, "E")
    axis_off(e)
    panel_title(e, PANEL_TITLES["Figure_1"]["E"])
    stage_labels = [
        ("U26A", "Input and\nmodule resolution"),
        ("U26B", "Within-dataset\nand cross-dataset scoring"),
        ("U26C", "Biological synthesis\nand evidence tiers"),
        ("U26D", "Single-cell\nlocalization"),
        ("U27A", "Mechanistic\nfigure development"),
        ("U27B", "Architecture and\nsource locking"),
    ]
    x_positions = np.linspace(0.06, 0.86, len(stage_labels))
    for index, ((phase, label), x) in enumerate(zip(stage_labels, x_positions)):
        draw_box(e, (x, 0.35), 0.12, 0.25, f"{phase}\n{label}", fontsize=5.5)
        if index < len(stage_labels) - 1:
            arrow(e, (x + 0.12, 0.475), (x_positions[index + 1], 0.475))
    e.text(
        0.5,
        0.76,
        "Expression repair → module scoring → evidence collapse → cellular attribution",
        ha="center",
        fontsize=6.2,
        fontweight="bold",
    )
    e.text(
        0.5,
        0.16,
        "Species-native analyses; tissue samples and biological samples remain the inferential units",
        ha="center",
        fontsize=5.5,
    )
    e.set_xlim(0, 1)
    e.set_ylim(0, 1)

    # F
    f = ax[5]
    panel_label(f, "F")
    core = store.table("Figure_1F", "refined_core")
    class_counts = (
        core["validation_class"]
        .fillna("unclassified")
        .astype(str)
        .value_counts()
        .rename_axis("validation_class")
        .reset_index(name="n_modules")
    )
    class_counts = class_counts.sort_values("n_modules")
    horizontal_lollipop(
        f,
        class_counts["validation_class"].tolist(),
        class_counts["n_modules"].tolist(),
        PANEL_TITLES["Figure_1"]["F"],
        "Modules",
    )
    f.text(
        0.98,
        0.04,
        "Robust core → provisional core → secondary/contextual → divergent",
        transform=f.transAxes,
        ha="right",
        va="bottom",
        fontsize=5.2,
    )
    export_rows(source_rows, class_counts, "Figure_1", "F", "refined_core")

    figure_paths = save_figure(fig, outdir, 1)
    save_source_rows(source_rows, tabledir, 1)
    return fig, figure_paths


def choose_core_features(
    core: pd.DataFrame,
    n: int = 10,
) -> List[str]:
    working = core.copy()
    if "independent_evidence_priority_score" in working.columns:
        working["_priority"] = numeric(
            working["independent_evidence_priority_score"]
        )
    else:
        working["_priority"] = 0

    keywords = [
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
    ]
    return select_features(
        working,
        keywords=keywords,
        n=n,
        score_column="_priority",
        absolute_score=False,
    )


def build_figure_2(
    store: SourceStore,
    outdir: Path,
    tabledir: Path,
) -> Tuple[plt.Figure, List[Path]]:
    source_rows: List[pd.DataFrame] = []
    mosaic = [
        ["A", "A", "B"],
        ["C", "D", "E"],
        ["F", "G", "G"],
    ]
    fig, axes = plt.subplot_mosaic(
        mosaic,
        figsize=(FIGURE_WIDTH_IN, 10.3),
        layout="constrained",
    )

    primary = store.table("Figure_2A", "primary_independent_effects")
    recurrence = store.table("Figure_2B", "recurrence_ranking")
    core = store.table("Figure_2C", "refined_core")
    labels = label_lookup(core)
    selected = choose_core_features(core, n=11)

    # A
    a = axes["A"]
    panel_label(a, "A")
    subset = primary[primary["feature_id"].astype(str).isin(selected)].copy()
    matrix = subset.pivot_table(
        index="feature_id",
        columns="dataset",
        values="effect_value",
        aggfunc="mean",
    )
    order = [value for value in selected if value in matrix.index]
    matrix = matrix.reindex(order)
    matrix.index = [labels.get(value, value) for value in matrix.index]
    safe_heatmap(
        a,
        matrix,
        PANEL_TITLES["Figure_2"]["A"],
        xlabel="Independent dataset",
        ylabel="Module",
    )
    export_rows(source_rows, subset, "Figure_2", "A", "primary_independent_effects")

    # B
    b = axes["B"]
    panel_label(b, "B")
    evidence = (
        recurrence["validation_class"]
        .fillna("unclassified")
        .astype(str)
        .value_counts()
        .rename_axis("validation_class")
        .reset_index(name="n_modules")
    )
    evidence = evidence.sort_values("n_modules")
    horizontal_lollipop(
        b,
        evidence["validation_class"].tolist(),
        evidence["n_modules"].tolist(),
        PANEL_TITLES["Figure_2"]["B"],
        "Modules",
    )
    export_rows(source_rows, evidence, "Figure_2", "B", "recurrence_ranking")

    # C
    c = axes["C"]
    axis_off(c)
    panel_label(c, "C")
    panel_title(c, PANEL_TITLES["Figure_2"]["C"])
    nodes = [
        ("TLR4-LPS", 0.08, 0.58),
        ("Leptin", 0.36, 0.76),
        ("IRS", 0.36, 0.39),
        ("PI3K-AKT", 0.66, 0.58),
        ("Glycogen/\ncarbon use", 0.66, 0.20),
        ("Inflammatory\nhost response", 0.66, 0.85),
    ]
    for label, x, y in nodes:
        draw_box(c, (x, y), 0.23, 0.14, label, fontsize=6.1)
    for start, end in [
        ((0.31, 0.65), (0.36, 0.81)),
        ((0.31, 0.65), (0.36, 0.46)),
        ((0.59, 0.83), (0.66, 0.65)),
        ((0.59, 0.46), (0.66, 0.61)),
        ((0.78, 0.58), (0.78, 0.34)),
        ((0.78, 0.72), (0.78, 0.85)),
    ]:
        arrow(c, start, end)
    c.text(
        0.5,
        0.05,
        "Core topology is evidence-weighted, not a claim of direct causal coupling.",
        ha="center",
        fontsize=5.2,
    )
    c.set_xlim(0, 1)
    c.set_ylim(0, 1)
    export_rows(
        source_rows,
        core[core["feature_id"].astype(str).isin(selected)],
        "Figure_2",
        "C",
        "refined_core",
    )

    # D
    d = axes["D"]
    panel_label(d, "D")
    complement = core[
        feature_text(core).str.contains(
            "complement|c3a|c5a|opsonophag",
            regex=True,
            na=False,
        )
    ].copy()
    if complement.empty:
        complement = core.nlargest(
            min(6, len(core)),
            "independent_evidence_priority_score",
        )
    complement["_x"] = numeric(complement["median_effect"])
    complement["_y"] = numeric(complement["preterm_vs_term_effect"])
    d.scatter(complement["_x"], complement["_y"], s=30)
    add_zero_line(d, vertical=True)
    add_zero_line(d, vertical=False)
    for _, row in complement.iterrows():
        if np.isfinite(row["_x"]) and np.isfinite(row["_y"]):
            d.text(
                row["_x"],
                row["_y"],
                clean_label(row["display_label"], 18),
                fontsize=4.9,
            )
    d.set_xlabel("Median infection effect", fontsize=6.3)
    d.set_ylabel("Preterm-versus-term effect", fontsize=6.3)
    panel_title(d, PANEL_TITLES["Figure_2"]["D"])
    finish_axis(d)
    export_rows(source_rows, complement, "Figure_2", "D", "refined_core")

    # E
    e = axes["E"]
    panel_label(e, "E")
    adjusted = store.table("Figure_2E", "gse112098_adjusted")
    adjusted["_value"] = numeric(adjusted["model_estimate"])
    adjusted = adjusted.reindex(
        adjusted["_value"].abs().sort_values(ascending=False).head(9).index
    )
    horizontal_lollipop(
        e,
        adjusted["display_label"].tolist(),
        adjusted["_value"].tolist(),
        PANEL_TITLES["Figure_2"]["E"],
        "Age/sex-adjusted estimate",
    )
    export_rows(source_rows, adjusted, "Figure_2", "E", "gse112098_adjusted")

    # F
    f = axes["F"]
    panel_label(f, "F")
    factorial = store.table("Figure_2F", "gse186800_factorial")
    contrast_text = factorial["contrast_id"].astype(str).str.lower()
    preferred = factorial[
        contrast_text.str.contains("gard|treat|infect|upec", regex=True)
        & ~contrast_text.str.contains("block|batch|interaction", regex=True)
    ].copy()
    if preferred.empty:
        contrast_scores = (
            factorial.assign(_abs=numeric(factorial["model_estimate"]).abs())
            .groupby("contrast_id")["_abs"]
            .mean()
            .sort_values(ascending=False)
        )
        if len(contrast_scores):
            preferred = factorial[
                factorial["contrast_id"] == contrast_scores.index[0]
            ].copy()
        else:
            preferred = factorial.copy()
    preferred["_value"] = numeric(preferred["model_estimate"])
    preferred = preferred.reindex(
        preferred["_value"].abs().sort_values(ascending=False).head(8).index
    )
    horizontal_lollipop(
        f,
        preferred["display_label"].tolist(),
        preferred["_value"].tolist(),
        PANEL_TITLES["Figure_2"]["F"],
        "Factorial model estimate",
    )
    if "contrast_id" in preferred.columns and not preferred.empty:
        f.text(
            0.98,
            0.03,
            clean_label(preferred["contrast_id"].iloc[0], 35),
            transform=f.transAxes,
            ha="right",
            va="bottom",
            fontsize=5,
        )
    export_rows(source_rows, preferred, "Figure_2", "F", "gse186800_factorial")

    # G
    g = axes["G"]
    panel_label(g, "G")
    recurrence = recurrence.copy()
    recurrence["_x"] = numeric(recurrence["weighted_directional_coherence"])
    recurrence["_y"] = numeric(recurrence["median_effect"])
    recurrence["_size"] = numeric(
        recurrence["independent_evidence_priority_score"]
    ).fillna(0)
    plot_data = recurrence.dropna(subset=["_x", "_y"]).copy()
    sizes = 18 + 55 * (
        plot_data["_size"] - plot_data["_size"].min()
    ) / max(plot_data["_size"].max() - plot_data["_size"].min(), 1e-9)
    g.scatter(plot_data["_x"], plot_data["_y"], s=sizes, alpha=0.75)
    add_zero_line(g, vertical=False)
    g.set_xlabel("Weighted directional coherence", fontsize=6.5)
    g.set_ylabel("Median independent effect", fontsize=6.5)
    panel_title(g, PANEL_TITLES["Figure_2"]["G"])
    top = plot_data.nlargest(min(9, len(plot_data)), "_size")
    for _, row in top.iterrows():
        if np.isfinite(row["_x"]) and np.isfinite(row["_y"]):
            g.text(
                row["_x"],
                row["_y"],
                clean_label(row["display_label"], 20),
                fontsize=4.9,
            )
    finish_axis(g)
    export_rows(source_rows, top, "Figure_2", "G", "recurrence_ranking")

    figure_paths = save_figure(fig, outdir, 2)
    save_source_rows(source_rows, tabledir, 2)
    return fig, figure_paths


def primary_matrix_subset(
    matrix: pd.DataFrame,
    prefix: str,
    keywords: Sequence[str],
    n: int,
) -> pd.DataFrame:
    columns = [
        column for column in matrix.columns
        if str(column).startswith(prefix)
    ]
    if not columns:
        return pd.DataFrame()

    working = matrix.copy()
    values = working[columns].apply(pd.to_numeric, errors="coerce")
    working["_score"] = values.abs().max(axis=1)
    working["_text"] = working["feature_id"].astype(str).str.lower()
    selected: List[str] = []

    for keyword in keywords:
        matches = working[
            working["_text"].str.contains(
                keyword,
                regex=False,
                na=False,
            )
            & ~working["feature_id"].astype(str).isin(selected)
        ]
        if not matches.empty:
            index = matches["_score"].idxmax()
            selected.append(str(working.loc[index, "feature_id"]))
        if len(selected) >= n:
            break

    remaining = working[
        ~working["feature_id"].astype(str).isin(selected)
    ].sort_values("_score", ascending=False)
    for value in remaining["feature_id"].astype(str):
        selected.append(value)
        if len(selected) >= n:
            break

    subset = (
        matrix[matrix["feature_id"].astype(str).isin(selected)]
        .set_index("feature_id")[columns]
        .apply(pd.to_numeric, errors="coerce")
    )
    subset = subset.reindex([value for value in selected if value in subset.index])
    return subset


def build_figure_3(
    store: SourceStore,
    outdir: Path,
    tabledir: Path,
) -> Tuple[plt.Figure, List[Path]]:
    source_rows: List[pd.DataFrame] = []
    fig, axes = plt.subplots(
        4,
        2,
        figsize=(FIGURE_WIDTH_IN, 11.6),
        layout="constrained",
    )
    ax = axes.ravel()

    design = store.table("Figure_3A", "gse280297_design")
    matrix = store.table("Figure_3B", "gse280297_primary_matrix")
    coherence = store.table("Figure_3C", "cross_tissue_coherence")
    domains = store.table("Figure_3D", "decoupling_domains")

    # A
    a = ax[0]
    panel_label(a, "A")
    group_col = "inferred_group" if "inferred_group" in design.columns else "treatment"
    design_counts = pd.crosstab(design[group_col], design["tissue"])
    safe_heatmap(
        a,
        design_counts.astype(float),
        PANEL_TITLES["Figure_3"]["A"],
        xlabel="Tissue",
        ylabel="Experimental group",
        annotate=True,
        max_annotations=80,
    )
    export_rows(source_rows, design_counts.reset_index(), "Figure_3", "A", "gse280297_design")

    # B
    b = ax[1]
    panel_label(b, "B")
    steroid_keywords = [
        "steroid",
        "androgen",
        "estrogen",
        "cholesterol",
        "receptor",
        "lipid",
        "pi3k",
        "leptin",
        "complement",
        "glycogen",
    ]
    c1 = primary_matrix_subset(matrix, "C1_PRETERM_VS_TERM", steroid_keywords, 12)
    safe_heatmap(
        b,
        c1,
        PANEL_TITLES["Figure_3"]["B"],
        xlabel="Tissue",
        ylabel="Selected module",
    )
    export_rows(source_rows, c1.reset_index(), "Figure_3", "B", "gse280297_primary_matrix")

    # C
    c = ax[2]
    panel_label(c, "C")
    c1_coherence = coherence[
        coherence["contrast_id"].astype(str).str.contains("C1_PRETERM_VS_TERM")
    ].copy()
    c1_coherence["_score"] = numeric(
        c1_coherence["mean_absolute_hedges_g"]
    )
    c1_coherence = c1_coherence.nlargest(
        min(10, len(c1_coherence)), "_score"
    )
    horizontal_lollipop(
        c,
        c1_coherence["display_label"].tolist(),
        numeric(c1_coherence["median_hedges_g"]).tolist(),
        PANEL_TITLES["Figure_3"]["C"],
        "Median Hedges g across tissues",
    )
    for position, value in enumerate(
        numeric(c1_coherence["directional_coherence_fraction"])
    ):
        if np.isfinite(value):
            c.text(
                0.98,
                position / max(len(c1_coherence), 1),
                f"coh={value:.2f}",
                transform=c.transAxes,
                ha="right",
                fontsize=4.8,
            )
    export_rows(source_rows, c1_coherence, "Figure_3", "C", "cross_tissue_coherence")

    # D
    d = ax[3]
    panel_label(d, "D")
    domains = domains.copy()
    domains["_value"] = numeric(domains["median_effect"])
    horizontal_lollipop(
        d,
        domains["domain"].tolist(),
        domains["_value"].tolist(),
        PANEL_TITLES["Figure_3"]["D"],
        "Median preterm-versus-term effect",
    )
    export_rows(source_rows, domains, "Figure_3", "D", "decoupling_domains")

    # E
    e = ax[4]
    panel_label(e, "E")
    c2 = primary_matrix_subset(
        matrix,
        "C2_UPEC_VS_PBS_PREGNANCY",
        [
            "tlr4", "leptin", "pi3k", "complement", "glycogen",
            "glycolysis", "steroid", "cholesterol", "redox", "amino",
        ],
        12,
    )
    safe_heatmap(
        e,
        c2,
        PANEL_TITLES["Figure_3"]["E"],
        xlabel="Tissue",
        ylabel="Selected module",
    )
    export_rows(source_rows, c2.reset_index(), "Figure_3", "E", "gse280297_primary_matrix")

    # F
    f = ax[5]
    panel_label(f, "F")
    c3_columns = [
        column for column in matrix.columns
        if str(column).startswith("C3_INFECTED_PREGNANT_VS_NONPREGNANT")
    ]
    if c3_columns:
        c3 = matrix[["feature_id", c3_columns[0]]].copy()
        c3["_value"] = numeric(c3[c3_columns[0]])
        c3 = c3.reindex(
            c3["_value"].abs().sort_values(ascending=False).head(12).index
        )
        horizontal_lollipop(
            f,
            c3["feature_id"].tolist(),
            c3["_value"].tolist(),
            PANEL_TITLES["Figure_3"]["F"],
            "Hedges g",
        )
        export_rows(source_rows, c3, "Figure_3", "F", "gse280297_primary_matrix")
    else:
        axis_off(f)
        panel_title(f, PANEL_TITLES["Figure_3"]["F"])
        f.text(0.5, 0.5, "C3 column unavailable", ha="center")

    # G
    g = ax[6]
    panel_label(g, "G")
    text = matrix["feature_id"].astype(str).str.lower()
    selected_rows = matrix[
        text.str.contains(
            "complement|c3a|c5a|opson|glycol|lactate|glycogen|pentose|hif",
            regex=True,
        )
    ].copy()
    value_columns = [
        column for column in matrix.columns
        if column != "feature_id"
        and (
            str(column).startswith("C1_")
            or str(column).startswith("C2_")
            or str(column).startswith("C3_")
        )
    ]
    if not selected_rows.empty and value_columns:
        selected_rows["_score"] = (
            selected_rows[value_columns]
            .apply(pd.to_numeric, errors="coerce")
            .abs()
            .max(axis=1)
        )
        selected_rows = selected_rows.nlargest(
            min(10, len(selected_rows)), "_score"
        )
        g_matrix = (
            selected_rows.set_index("feature_id")[value_columns]
            .apply(pd.to_numeric, errors="coerce")
        )
    else:
        g_matrix = pd.DataFrame()
    safe_heatmap(
        g,
        g_matrix,
        PANEL_TITLES["Figure_3"]["G"],
        xlabel="Contrast and tissue",
        ylabel="Complement/carbon module",
    )
    export_rows(source_rows, selected_rows, "Figure_3", "G", "gse280297_primary_matrix")

    # H
    h = ax[7]
    axis_off(h)
    panel_label(h, "H")
    panel_title(h, PANEL_TITLES["Figure_3"]["H"])
    draw_box(h, (0.05, 0.65), 0.25, 0.16, "UPEC exposure\nin pregnancy")
    draw_box(h, (0.38, 0.76), 0.25, 0.14, "TLR4/complement\nand inflammatory carbon")
    draw_box(h, (0.38, 0.45), 0.25, 0.14, "Steroid synthesis\nand androgen branch")
    draw_box(h, (0.70, 0.62), 0.25, 0.18, "Tissue-specific\nhost state")
    draw_box(h, (0.38, 0.13), 0.25, 0.14, "Attenuated receptor\nand metabolic response")
    draw_box(h, (0.70, 0.16), 0.25, 0.16, "Preterm-associated\noutcome architecture")
    for start, end in [
        ((0.30, 0.73), (0.38, 0.83)),
        ((0.30, 0.73), (0.38, 0.52)),
        ((0.63, 0.83), (0.70, 0.72)),
        ((0.63, 0.52), (0.70, 0.68)),
        ((0.50, 0.45), (0.50, 0.27)),
        ((0.63, 0.20), (0.70, 0.24)),
        ((0.82, 0.62), (0.82, 0.32)),
    ]:
        arrow(h, start, end)
    h.text(
        0.5,
        0.03,
        "Working model: branch-selective association, not proof of causal miscarriage biology.",
        ha="center",
        fontsize=5.1,
    )
    h.set_xlim(0, 1)
    h.set_ylim(0, 1)
    export_rows(source_rows, domains, "Figure_3", "H", "decoupling_domains")

    figure_paths = save_figure(fig, outdir, 3)
    save_source_rows(source_rows, tabledir, 3)
    return fig, figure_paths


def merge_refined_labels(
    annotations: pd.DataFrame,
    refinement: pd.DataFrame,
) -> pd.DataFrame:
    refinement = refinement.copy()
    refinement["cluster"] = refinement["cluster"].astype(str)
    annotations = annotations.copy()
    annotations["cluster"] = annotations["cluster"].astype(str)
    merged = annotations.merge(
        refinement[
            [
                column
                for column in (
                    "cluster",
                    "refined_broad_cell_type",
                    "refined_cell_subtype",
                )
                if column in refinement.columns
            ]
        ],
        on="cluster",
        how="left",
    )
    merged["plot_label"] = (
        merged.get("refined_broad_cell_type", pd.Series(index=merged.index))
        .fillna(merged.get("broad_cell_type", "Unresolved"))
        .astype(str)
    )
    return merged


def build_figure_4(
    store: SourceStore,
    outdir: Path,
    tabledir: Path,
) -> Tuple[plt.Figure, List[Path]]:
    source_rows: List[pd.DataFrame] = []
    fig, axes = plt.subplots(
        4,
        2,
        figsize=(FIGURE_WIDTH_IN, 11.8),
        layout="constrained",
    )
    ax = axes.ravel()

    annotations = store.table("Figure_4A", "balanced_annotations")
    markers = store.table("Figure_4B", "cluster_markers")
    refinement = store.table("Figure_4B", "refinement_map")
    broad = store.table("Figure_4C", "broad_composition")
    subtype = store.table("Figure_4D", "subtype_composition")
    targeted = store.table("Figure_4E", "targeted_states")
    core_attr = store.table("Figure_4G", "core_cellular_attribution")
    broad_effects = store.table("Figure_4G", "broad_effect_reliability")

    # A
    a = ax[0]
    panel_label(a, "A")
    merged = merge_refined_labels(annotations, refinement)
    if len(merged) > 12000:
        plot_data = merged.sample(12000, random_state=17)
    else:
        plot_data = merged.copy()
    categories = pd.Categorical(plot_data["plot_label"])
    a.scatter(
        numeric(plot_data["corrected_component_1"]),
        numeric(plot_data["corrected_component_2"]),
        c=categories.codes,
        cmap="tab20",
        s=1.8,
        alpha=0.7,
        linewidths=0,
    )
    a.set_xlabel("Corrected component 1", fontsize=6.5)
    a.set_ylabel("Corrected component 2", fontsize=6.5)
    panel_title(a, PANEL_TITLES["Figure_4"]["A"])
    finish_axis(a)
    legend_labels = list(categories.categories)
    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markersize=3,
            label=clean_label(label, 18),
        )
        for label in legend_labels[:10]
    ]
    if handles:
        a.legend(
            handles=handles,
            loc="best",
            fontsize=4.5,
            frameon=False,
            ncol=2,
        )
    export_rows(
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
        note="subsampled for plotting when >12,000 cells",
    )

    # B
    b = ax[1]
    panel_label(b, "B")
    top_markers = markers.copy()
    if "rank" in top_markers.columns:
        top_markers = top_markers[numeric(top_markers["rank"]) <= 3]
    value_col = (
        "specificity_difference"
        if "specificity_difference" in top_markers.columns
        else "cluster_mean_log_expression"
    )
    marker_matrix = top_markers.pivot_table(
        index="gene_symbol",
        columns="cluster",
        values=value_col,
        aggfunc="max",
    ).fillna(0)
    if marker_matrix.shape[0] > 36:
        marker_matrix = marker_matrix.iloc[:36]
    safe_heatmap(
        b,
        marker_matrix,
        PANEL_TITLES["Figure_4"]["B"],
        xlabel="Cluster",
        ylabel="Top marker",
    )
    export_rows(source_rows, top_markers, "Figure_4", "B", "cluster_markers")
    export_rows(source_rows, refinement, "Figure_4", "B", "refinement_map")

    # C
    c = ax[2]
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
        c.bar(x, values, bottom=bottom, label=clean_label(column, 18))
        bottom += values
    c.set_xticks(x)
    c.set_xticklabels(composition.index, rotation=45, ha="right", fontsize=5.5)
    c.set_ylabel("Fraction of QC-passing cells", fontsize=6.5)
    panel_title(c, PANEL_TITLES["Figure_4"]["C"])
    c.legend(fontsize=4.5, frameon=False, ncol=2, loc="upper right")
    finish_axis(c)
    export_rows(source_rows, broad, "Figure_4", "C", "broad_composition")

    # D
    d = ax[3]
    panel_label(d, "D")
    subtype = subtype.copy()
    subtype["fraction_of_QC_cells"] = numeric(subtype["fraction_of_QC_cells"])
    top_subtypes = (
        subtype.groupby("refined_cell_subtype")["fraction_of_QC_cells"]
        .mean()
        .sort_values(ascending=False)
        .head(12)
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
    safe_heatmap(
        d,
        subtype_matrix,
        PANEL_TITLES["Figure_4"]["D"],
        xlabel="Sample",
        ylabel="Refined subtype",
    )
    export_rows(
        source_rows,
        subtype[subtype["refined_cell_subtype"].isin(top_subtypes)],
        "Figure_4",
        "D",
        "subtype_composition",
    )

    # E
    e = ax[4]
    panel_label(e, "E")
    targeted_text = targeted["targeted_measure"].astype(str).str.lower()
    tnfsf9 = targeted[
        targeted_text.str.contains("tnfsf9|cd137l", regex=True)
    ].copy()
    if tnfsf9.empty:
        tnfsf9 = targeted.head(0).copy()
    if not tnfsf9.empty:
        tnfsf9["value"] = numeric(tnfsf9["value"])
        measures = tnfsf9["targeted_measure"].drop_duplicates().tolist()
        x = np.arange(len(measures))
        width = 0.34
        conditions = tnfsf9["condition"].drop_duplicates().tolist()
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
                label=condition,
            )
        e.set_xticks(x)
        e.set_xticklabels(
            [clean_label(value, 18) for value in measures],
            rotation=35,
            ha="right",
            fontsize=5.2,
        )
        e.set_ylabel("Fraction within parent population", fontsize=6.3)
        e.legend(fontsize=5, frameon=False)
        finish_axis(e)
    else:
        axis_off(e)
        e.text(0.5, 0.5, "No TNFSF9-targeted rows", ha="center")
    panel_title(e, PANEL_TITLES["Figure_4"]["E"])
    export_rows(source_rows, tnfsf9, "Figure_4", "E", "targeted_states")

    # F
    f = ax[5]
    panel_label(f, "F")
    treg = targeted[
        targeted_text.str.contains("treg|foxp3|regulatory", regex=True)
    ].copy()
    if not treg.empty:
        treg["value"] = numeric(treg["value"])
        measures = treg["targeted_measure"].drop_duplicates().tolist()
        x = np.arange(len(measures))
        width = 0.34
        conditions = treg["condition"].drop_duplicates().tolist()
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
                label=condition,
            )
        f.set_xticks(x)
        f.set_xticklabels(
            [clean_label(value, 18) for value in measures],
            rotation=35,
            ha="right",
            fontsize=5.2,
        )
        f.set_ylabel("Fraction within parent population", fontsize=6.3)
        f.legend(fontsize=5, frameon=False)
        finish_axis(f)
    else:
        axis_off(f)
        f.text(0.5, 0.5, "No Treg-targeted rows", ha="center")
    panel_title(f, PANEL_TITLES["Figure_4"]["F"])
    export_rows(source_rows, treg, "Figure_4", "F", "targeted_states")

    # G
    g = ax[6]
    panel_label(g, "G")
    core_features = choose_core_features(
        core_attr.rename(
            columns={
                "top_population_composite_score":
                "independent_evidence_priority_score"
            }
        ),
        n=10,
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
    safe_heatmap(
        g,
        localization_matrix,
        PANEL_TITLES["Figure_4"]["G"],
        xlabel="Broad immune population",
        ylabel="Core module",
    )
    export_rows(source_rows, localization, "Figure_4", "G", "broad_effect_reliability")

    # H
    h = ax[7]
    axis_off(h)
    panel_label(h, "H")
    panel_title(h, PANEL_TITLES["Figure_4"]["H"])
    draw_box(h, (0.05, 0.68), 0.25, 0.15, "UPEC")
    draw_box(h, (0.38, 0.76), 0.25, 0.14, "Myeloid expansion\nand activation")
    draw_box(h, (0.38, 0.45), 0.25, 0.14, "TNFSF9-positive/\nhigh macrophages")
    draw_box(h, (0.70, 0.66), 0.25, 0.15, "T-cell and dendritic\nmodule localization")
    draw_box(h, (0.38, 0.15), 0.25, 0.14, "Strict/expanded\nTreg-like states")
    draw_box(h, (0.70, 0.18), 0.25, 0.15, "Regulatory-inflammatory\nbalance")
    for start, end in [
        ((0.30, 0.75), (0.38, 0.83)),
        ((0.30, 0.75), (0.38, 0.52)),
        ((0.63, 0.83), (0.70, 0.73)),
        ((0.63, 0.52), (0.70, 0.68)),
        ((0.50, 0.45), (0.50, 0.29)),
        ((0.63, 0.22), (0.70, 0.25)),
        ((0.82, 0.66), (0.82, 0.33)),
    ]:
        arrow(h, start, end)
    h.text(
        0.5,
        0.04,
        "Cellular attribution is descriptive at n=2 control and n=2 UPEC samples.",
        ha="center",
        fontsize=5.1,
    )
    h.set_xlim(0, 1)
    h.set_ylim(0, 1)
    export_rows(source_rows, targeted, "Figure_4", "H", "targeted_states")
    export_rows(source_rows, core_attr, "Figure_4", "H", "core_cellular_attribution")

    figure_paths = save_figure(fig, outdir, 4)
    save_source_rows(source_rows, tabledir, 4)
    return fig, figure_paths


def save_figure(
    fig: plt.Figure,
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    stem = f"UTI_HostOmics_U27B2B_Figure_{figure_number}"
    for extension in ("png", "svg", "pdf"):
        path = outdir / f"{stem}.{extension}"
        kwargs = {}
        if extension == "png":
            kwargs["dpi"] = DPI
        fig.savefig(
            path,
            facecolor="white",
            bbox_inches=None,
            **kwargs,
        )
        paths.append(path)
    return paths


def save_source_rows(
    rows: List[pd.DataFrame],
    tabledir: Path,
    figure_number: int,
) -> Path:
    tabledir.mkdir(parents=True, exist_ok=True)
    if rows:
        frame = pd.concat(rows, ignore_index=True, sort=False)
    else:
        frame = pd.DataFrame(
            columns=["figure", "panel", "source_role", "source_note"]
        )
    path = (
        tabledir
        / f"UTI_HostOmics_U27B2B_Figure_{figure_number}_source_values.tsv"
    )
    frame.to_csv(path, sep="\t", index=False)
    return path


def panel_crops(
    fig: plt.Figure,
    axes: Sequence[plt.Axes],
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    if Image is None:
        return []

    outdir.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.canvas.get_width_height()
    buffer = np.asarray(fig.canvas.buffer_rgba())
    image = Image.fromarray(buffer)

    paths = []
    for index, axis in enumerate(axes):
        bbox = axis.get_tightbbox(renderer).expanded(1.05, 1.08)
        x0 = max(int(bbox.x0), 0)
        y0 = max(int(height - bbox.y1), 0)
        x1 = min(int(bbox.x1), width)
        y1 = min(int(height - bbox.y0), height)
        crop = image.crop((x0, y0, x1, y1))
        letter = chr(ord("A") + index)
        path = (
            outdir
            / f"UTI_HostOmics_U27B2B_Figure_{figure_number}_panel_{letter}.png"
        )
        crop.save(path)
        paths.append(path)
    return paths


def make_contact_sheet(
    paths: Sequence[Path],
    output: Path,
    columns: int,
    cell_width: int = 1200,
    padding: int = 30,
) -> None:
    if Image is None or not paths:
        return

    images = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        ratio = cell_width / image.width
        height = max(int(image.height * ratio), 1)
        image = image.resize((cell_width, height))
        images.append(image)

    rows = math.ceil(len(images) / columns)
    row_heights = []
    for row in range(rows):
        subset = images[row * columns:(row + 1) * columns]
        row_heights.append(max(image.height for image in subset))

    canvas_width = columns * cell_width + (columns + 1) * padding
    canvas_height = sum(row_heights) + (rows + 1) * padding
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")

    y = padding
    for row in range(rows):
        x = padding
        subset = images[row * columns:(row + 1) * columns]
        for image in subset:
            canvas.paste(image, (x, y))
            x += cell_width + padding
        y += row_heights[row] + padding

    canvas.save(output)


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
        tabledir / "UTI_HostOmics_U27B2B_export_audit.tsv",
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
    registry, panel_map = get_registry(project)

    outfig = project / "06_figures" / TAG
    outtables = project / "06_tables" / TAG
    outresults = project / "05_results" / TAG
    outmetadata = project / "03_metadata" / TAG
    cropdir = outfig / "panel_crops"

    for directory in (outfig, outtables, outresults, outmetadata, cropdir):
        directory.mkdir(parents=True, exist_ok=True)

    source_store = SourceStore(registry)
    figure_paths: List[Path] = []
    panel_crop_paths: List[Path] = []

    log("Building Final Figure 1.")
    fig1, paths1 = build_figure_1(source_store, registry, outfig, outtables)
    figure_paths.extend(paths1)
    panel_crop_paths.extend(panel_crops(fig1, fig1.axes[:6], cropdir, 1))
    plt.close(fig1)

    log("Building Final Figure 2.")
    fig2, paths2 = build_figure_2(source_store, outfig, outtables)
    figure_paths.extend(paths2)
    panel_crop_paths.extend(panel_crops(fig2, fig2.axes[:7], cropdir, 2))
    plt.close(fig2)

    log("Building Final Figure 3.")
    fig3, paths3 = build_figure_3(source_store, outfig, outtables)
    figure_paths.extend(paths3)
    panel_crop_paths.extend(panel_crops(fig3, fig3.axes[:8], cropdir, 3))
    plt.close(fig3)

    log("Building Final Figure 4.")
    fig4, paths4 = build_figure_4(source_store, outfig, outtables)
    figure_paths.extend(paths4)
    panel_crop_paths.extend(panel_crops(fig4, fig4.axes[:8], cropdir, 4))
    plt.close(fig4)

    png_paths = [
        path for path in figure_paths if path.suffix.lower() == ".png"
    ]
    make_contact_sheet(
        png_paths,
        outfig / "UTI_HostOmics_U27B2B_full_figure_contact_sheet.png",
        columns=2,
        cell_width=1100,
    )
    make_contact_sheet(
        panel_crop_paths,
        outfig / "UTI_HostOmics_U27B2B_panel_contact_sheet.png",
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
        / "UTI_HostOmics_U27B2B_Figures_1_to_4_build_manifest.tsv",
        sep="\t",
        index=False,
    )

    expected_panels = 6 + 7 + 8 + 8
    observed_panels = build_manifest["panel_key"].nunique()
    expected_exports = 4 * 3
    observed_exports = int(audit["exists"].sum())
    nonempty_exports = bool((audit["size_bytes"] > 0).all())

    if (
        observed_panels == expected_panels
        and observed_exports == expected_exports
        and nonempty_exports
        and (
            outfig
            / "UTI_HostOmics_U27B2B_full_figure_contact_sheet.png"
        ).exists()
        and (
            outfig
            / "UTI_HostOmics_U27B2B_panel_contact_sheet.png"
        ).exists()
    ):
        decision = (
            "READY_FOR_U27B2C_FINAL_FIGURES_1_TO_4_VISUAL_AUDIT"
        )
    else:
        decision = "TARGETED_FIGURE_BUILD_REPAIR_REQUIRED"

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B2B",
                "decision": decision,
                "figures_expected": 4,
                "figures_built": len(png_paths),
                "panels_expected": expected_panels,
                "panels_in_build_manifest": observed_panels,
                "exports_expected": expected_exports,
                "exports_present": observed_exports,
                "nonempty_exports": nonempty_exports,
                "full_figure_contact_sheet_present": (
                    outfig
                    / "UTI_HostOmics_U27B2B_full_figure_contact_sheet.png"
                ).exists(),
                "panel_contact_sheet_present": (
                    outfig
                    / "UTI_HostOmics_U27B2B_panel_contact_sheet.png"
                ).exists(),
                "scientific_values_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B2C visual audit of Final Figures 1-4"
                    if decision.startswith("READY_FOR_U27B2C")
                    else "Repair figure build or missing exports"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        outtables / "UTI_HostOmics_U27B2B_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B2B_final_figures_1_to_4_build_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2B - Final Figures 1-4 build\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Figures built: **4/4**.\n")
        handle.write(
            f"- Frozen panels represented: "
            f"**{observed_panels}/{expected_panels}**.\n"
        )
        handle.write(
            f"- PNG/SVG/PDF exports present: "
            f"**{observed_exports}/{expected_exports}**.\n"
        )
        handle.write(
            f"- Panel crops generated: "
            f"**{len(panel_crop_paths)}**.\n\n"
        )
        handle.write("## Figure identities\n\n")
        handle.write(
            "- Figure 1: study architecture, datasets and evidence framework.\n"
            "- Figure 2: cross-dataset infection-response core.\n"
            "- Figure 3: pregnancy-, tissue- and outcome-resolved remodeling.\n"
            "- Figure 4: single-cell immune ecosystem and TNFSF9-Treg axis.\n\n"
        )
        handle.write("## Integrity boundary\n\n")
        handle.write(
            "All rendered values derive from the U27B2A.2 locked source "
            "registry. Legacy composite figures and U27A4 visual assets were "
            "not used as numerical sources for Figures 1-4.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "figures_built": 4,
        "panels": observed_panels,
        "exports": observed_exports,
        "panel_crops": len(panel_crop_paths),
        "scientific_values_changed": False,
        "manuscript_modified": False,
    }
    (
        outresults / "UTI_HostOmics_U27B2B_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Figures built: 4/4")
    log(f"Panels represented: {observed_panels}/{expected_panels}")
    log(f"Exports present: {observed_exports}/{expected_exports}")
    log(f"Panel crops: {len(panel_crop_paths)}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2B] ERROR: {exc}", file=sys.stderr)
        raise
