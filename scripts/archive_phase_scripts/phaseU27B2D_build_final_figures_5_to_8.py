#!/usr/bin/env python3
"""
Phase U27B2D
Build manuscript-facing Final Figures 5-8 from the frozen source registry.

Final figures
-------------
Figure 5 (7 panels)
    Steroid, cholesterol and lipid-remodeling architecture.

Figure 6 (8 panels)
    Adipokine, insulin and integrated immunometabolic remodeling.

Figure 7 (7 panels)
    Complement branch and cellular architecture.

Figure 8 (6 panels)
    Integrated endocrine-metabolic-immune model.

Source integrity
----------------
- Numerical values are read only from the frozen U27B2C2E source registry.
- U27A4 Figures 7-11 are checked and recorded as visual-grammar references.
- U27A4 graphics are not used as numerical sources.
- No statistical effects are recalculated.

Outputs
-------
- Figures 5-8 in PNG, SVG and PDF.
- 28 panel crops.
- Full-figure and panel contact sheets.
- Panel-level source-value tables.
- Build manifest, export audit, visual-reference audit and phase decision.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.colors import CenteredNorm
import numpy as np
import pandas as pd

try:
    from PIL import Image
except ImportError:
    Image = None


VERSION = "U27B2D_v1.0_2026-07-16"
TAG = "phaseU27B2D_final_figures_5_to_8_build"
FREEZE_TAG = "phaseU27B2C2E_final_figures_1_to_4_freeze"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"
U27A4_TAG = "phaseU27A4_final_visual_audit"

FIGURE_WIDTH_IN = 180 / 25.4
DPI = 300

EXPECTED_PANEL_COUNTS = {
    5: 7,
    6: 8,
    7: 7,
    8: 6,
}


def log(message: str) -> None:
    print(f"[U27B2D] {message}", flush=True)


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def compact(value: object, width: int = 23) -> str:
    text = str(value).replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return "\n".join(
        textwrap.wrap(
            text,
            width=width,
            break_long_words=False,
        )
    )


def panel_label(ax: plt.Axes, letter: str) -> None:
    ax.text(
        -0.12,
        1.045,
        letter,
        transform=ax.transAxes,
        fontsize=9.3,
        fontweight="bold",
        ha="left",
        va="bottom",
        clip_on=False,
    )


def panel_title(ax: plt.Axes, title: str) -> None:
    wrapped = (
        "\n".join(
            textwrap.wrap(
                str(title),
                width=31,
                break_long_words=False,
            )
        )
        if len(str(title)) > 32
        else str(title)
    )
    ax.set_title(
        wrapped,
        loc="left",
        x=0.02,
        fontsize=7.2,
        fontweight="bold",
        pad=4,
        linespacing=0.95,
    )


def finish_axis(ax: plt.Axes) -> None:
    ax.tick_params(labelsize=4.9, length=2.0, width=0.5)
    for spine in ax.spines.values():
        spine.set_linewidth(0.5)


def add_zero(ax: plt.Axes, vertical: bool = True) -> None:
    if vertical:
        ax.axvline(0, linewidth=0.65, alpha=0.55)
    else:
        ax.axhline(0, linewidth=0.65, alpha=0.55)


def axis_off(ax: plt.Axes) -> None:
    ax.set_axis_off()


def draw_box(
    ax: plt.Axes,
    xy: Tuple[float, float],
    width: float,
    height: float,
    text: str,
    fontsize: float = 5.5,
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
    linestyle: str = "-",
) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(
            arrowstyle="-|>",
            linewidth=0.8,
            linestyle=linestyle,
            shrinkA=2,
            shrinkB=2,
        ),
    )


class SourceStore:
    def __init__(self, registry: pd.DataFrame):
        self.registry = registry.copy()
        self.cache: Dict[str, pd.DataFrame] = {}

    def paths(
        self,
        panel_key: str,
        role: Optional[str] = None,
    ) -> List[str]:
        subset = self.registry[
            self.registry["panel_key"].astype(str) == str(panel_key)
        ].copy()
        if role is not None:
            subset = subset[
                subset["source_role"].astype(str) == str(role)
            ]
        return (
            subset["locked_path"]
            .astype(str)
            .drop_duplicates()
            .tolist()
        )

    def table(self, panel_key: str, role: str) -> pd.DataFrame:
        paths = self.paths(panel_key, role)
        if len(paths) != 1:
            raise RuntimeError(
                f"Expected one source for {panel_key}/{role}; "
                f"observed {len(paths)}: {paths}"
            )
        path = paths[0]
        if path not in self.cache:
            self.cache[path] = pd.read_csv(
                path,
                sep="\t",
                compression="infer",
                low_memory=False,
            )
        return self.cache[path].copy()


def label_column(frame: pd.DataFrame) -> str:
    for column in (
        "display_label",
        "module_label",
        "feature_label",
        "feature_id",
    ):
        if column in frame.columns:
            return column
    raise RuntimeError("No label-compatible column found.")


def feature_text(frame: pd.DataFrame) -> pd.Series:
    columns = [
        column
        for column in (
            "feature_id",
            "display_label",
            "axis",
            "refined_infection_outcome_relation",
        )
        if column in frame.columns
    ]
    if not columns:
        return pd.Series("", index=frame.index)

    text = frame[columns[0]].fillna("").astype(str)
    for column in columns[1:]:
        text = text + " " + frame[column].fillna("").astype(str)
    return text.str.lower()


def label_lookup(frame: pd.DataFrame) -> Dict[str, str]:
    if "feature_id" not in frame.columns:
        return {}
    label = label_column(frame)
    return dict(
        zip(
            frame["feature_id"].astype(str),
            frame[label].fillna(frame["feature_id"]).astype(str),
        )
    )


def select_features(
    frame: pd.DataFrame,
    keywords: Sequence[str],
    n: int,
    score_column: Optional[str] = None,
) -> List[str]:
    if "feature_id" not in frame.columns:
        return []

    working = frame.drop_duplicates("feature_id").copy()
    working["_text"] = feature_text(working)

    if score_column and score_column in working.columns:
        working["_score"] = numeric(working[score_column]).abs()
    else:
        working["_score"] = 0.0

    selected: List[str] = []

    for keyword in keywords:
        matches = working[
            working["_text"].str.contains(
                str(keyword).lower(),
                regex=False,
                na=False,
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


def filter_features(
    frame: pd.DataFrame,
    feature_ids: Sequence[str],
) -> pd.DataFrame:
    if "feature_id" not in frame.columns:
        return frame.head(0).copy()
    return frame[
        frame["feature_id"].astype(str).isin(
            [str(value) for value in feature_ids]
        )
    ].copy()


def independent_matrix(
    frame: pd.DataFrame,
    feature_ids: Sequence[str],
    labels: Dict[str, str],
) -> pd.DataFrame:
    subset = filter_features(frame, feature_ids)
    if subset.empty:
        return pd.DataFrame()

    dataset_column = (
        "dataset"
        if "dataset" in subset.columns
        else "primary_context"
    )
    matrix = subset.pivot_table(
        index="feature_id",
        columns=dataset_column,
        values="effect_value",
        aggfunc="mean",
    )
    order = [value for value in feature_ids if value in matrix.index]
    matrix = matrix.reindex(order)
    matrix.index = [labels.get(value, value) for value in matrix.index]
    return matrix


def broad_matrix(
    frame: pd.DataFrame,
    feature_ids: Sequence[str],
    labels: Dict[str, str],
) -> pd.DataFrame:
    subset = filter_features(frame, feature_ids)
    if subset.empty:
        return pd.DataFrame()

    population_column = (
        "population"
        if "population" in subset.columns
        else "refined_broad_cell_type"
    )
    value_column = (
        "module_mean_gene_log2FC"
        if "module_mean_gene_log2FC" in subset.columns
        else "cellular_localization_score"
    )

    matrix = subset.pivot_table(
        index="feature_id",
        columns=population_column,
        values=value_column,
        aggfunc="mean",
    )
    order = [value for value in feature_ids if value in matrix.index]
    matrix = matrix.reindex(order)
    matrix.index = [labels.get(value, value) for value in matrix.index]
    return matrix


def preterm_series(
    frame: pd.DataFrame,
    feature_ids: Sequence[str],
    labels: Dict[str, str],
) -> pd.Series:
    subset = filter_features(frame, feature_ids)
    if subset.empty:
        return pd.Series(dtype=float)

    subset["_effect"] = numeric(subset["effect_value"])
    series = (
        subset.groupby("feature_id")["_effect"]
        .mean()
        .reindex([value for value in feature_ids if value in set(subset["feature_id"].astype(str))])
    )
    series.index = [labels.get(value, value) for value in series.index]
    return series


def safe_heatmap(
    ax: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
    xlabel: str,
    ylabel: str,
    horizontal_colorbar: bool = False,
) -> None:
    panel_title(ax, title)

    if matrix.empty:
        axis_off(ax)
        ax.text(
            0.5,
            0.5,
            "No eligible values",
            ha="center",
            va="center",
            fontsize=6,
        )
        return

    values = matrix.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        finite = np.array([0.0])

    image = ax.imshow(
        values,
        aspect="auto",
        norm=CenteredNorm(vcenter=0),
    )

    ax.set_xticks(np.arange(matrix.shape[1]))
    ax.set_xticklabels(
        [compact(value, 12) for value in matrix.columns],
        rotation=38,
        ha="right",
        fontsize=4.5,
    )
    ax.set_yticks(np.arange(matrix.shape[0]))
    ax.set_yticklabels(
        [compact(value, 21) for value in matrix.index],
        fontsize=4.45,
    )
    ax.set_xlabel(xlabel, fontsize=5.7)
    ax.set_ylabel(ylabel, fontsize=5.7)

    if horizontal_colorbar:
        colorbar = ax.figure.colorbar(
            image,
            ax=ax,
            orientation="horizontal",
            fraction=0.07,
            pad=0.18,
            aspect=30,
        )
    else:
        colorbar = ax.figure.colorbar(
            image,
            ax=ax,
            fraction=0.040,
            pad=0.024,
        )
    colorbar.ax.tick_params(labelsize=4.3, length=1.8)
    finish_axis(ax)


def horizontal_lollipop(
    ax: plt.Axes,
    labels: Sequence[str],
    values: Sequence[float],
    title: str,
    xlabel: str,
    label_width: int = 22,
) -> None:
    panel_title(ax, title)

    labels = list(labels)
    values = np.asarray(values, dtype=float)
    keep = np.isfinite(values)
    labels = [label for label, valid in zip(labels, keep) if valid]
    values = values[keep]

    if len(values) == 0:
        axis_off(ax)
        ax.text(0.5, 0.5, "No eligible values", ha="center", va="center")
        return

    order = np.argsort(values)
    labels = [labels[index] for index in order]
    values = values[order]
    y = np.arange(len(values))

    ax.hlines(y, 0, values, linewidth=0.9)
    ax.scatter(values, y, s=18, zorder=3)
    add_zero(ax, True)

    ax.set_yticks(y)
    ax.set_yticklabels(
        [compact(value, label_width) for value in labels],
        fontsize=4.7,
    )
    ax.set_xlabel(xlabel, fontsize=5.8)
    finish_axis(ax)


def subtype_support(
    synthesis: pd.DataFrame,
    feature_ids: Sequence[str],
    labels: Dict[str, str],
) -> pd.DataFrame:
    subset = filter_features(synthesis, feature_ids)
    if subset.empty:
        return subset

    subtype_column = (
        "top_refined_subtype"
        if "top_refined_subtype" in subset.columns
        else "top_population_by_composite_score"
    )
    score_column = (
        "top_refined_subtype_composite_score"
        if "top_refined_subtype_composite_score" in subset.columns
        else "top_population_composite_score"
    )

    subset["_label"] = (
        subset["feature_id"].astype(str).map(labels).fillna(
            subset["feature_id"].astype(str)
        )
    )
    subset["_subtype"] = subset[subtype_column].fillna("unresolved").astype(str)
    subset["_score"] = numeric(subset[score_column])
    return subset


def export_rows(
    collector: List[pd.DataFrame],
    frame: pd.DataFrame,
    figure: int,
    panel: str,
    role: str,
    note: str = "",
) -> None:
    copy = frame.copy()
    copy.insert(0, "source_note", note)
    copy.insert(0, "source_role", role)
    copy.insert(0, "panel", panel)
    copy.insert(0, "figure", f"Figure_{figure}")
    collector.append(copy)


def save_source_rows(
    collector: List[pd.DataFrame],
    tabledir: Path,
    figure_number: int,
) -> Path:
    if collector:
        frame = pd.concat(collector, ignore_index=True, sort=False)
    else:
        frame = pd.DataFrame(
            columns=["figure", "panel", "source_role", "source_note"]
        )
    path = (
        tabledir
        / f"UTI_HostOmics_U27B2D_Figure_{figure_number}_source_values.tsv"
    )
    frame.to_csv(path, sep="\t", index=False)
    return path


def save_figure(
    fig: plt.Figure,
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    paths: List[Path] = []
    stem = f"UTI_HostOmics_U27B2D_Figure_{figure_number}"
    for extension in ("png", "svg", "pdf"):
        path = outdir / f"{stem}.{extension}"
        kwargs = {"dpi": DPI} if extension == "png" else {}
        fig.savefig(path, facecolor="white", **kwargs)
        paths.append(path)
    return paths


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
    image = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()))
    paths: List[Path] = []

    for index, axis in enumerate(axes):
        bbox = axis.get_tightbbox(renderer).expanded(1.08, 1.12)
        x0 = max(int(bbox.x0), 0)
        y0 = max(int(height - bbox.y1), 0)
        x1 = min(int(bbox.x1), width)
        y1 = min(int(height - bbox.y0), height)
        crop = image.crop((x0, y0, x1, y1))
        panel = chr(ord("A") + index)
        path = (
            outdir
            / f"UTI_HostOmics_U27B2D_Figure_{figure_number}"
            f"_panel_{panel}.png"
        )
        crop.save(path)
        paths.append(path)

    return paths


def make_contact_sheet(
    paths: Sequence[Path],
    output: Path,
    columns: int,
    cell_width: int,
    padding: int = 28,
) -> None:
    if Image is None or not paths:
        return

    images = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        ratio = cell_width / image.width
        image = image.resize(
            (cell_width, max(1, int(image.height * ratio)))
        )
        images.append(image)

    rows = math.ceil(len(images) / columns)
    row_heights = []
    for row_index in range(rows):
        subset = images[
            row_index * columns:(row_index + 1) * columns
        ]
        row_heights.append(max(image.height for image in subset))

    canvas_width = columns * cell_width + (columns + 1) * padding
    canvas_height = sum(row_heights) + (rows + 1) * padding
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")

    y = padding
    for row_index in range(rows):
        x = padding
        subset = images[
            row_index * columns:(row_index + 1) * columns
        ]
        for image in subset:
            canvas.paste(image, (x, y))
            x += cell_width + padding
        y += row_heights[row_index] + padding

    canvas.save(output)


def endocrine_keywords() -> List[str]:
    return [
        "core steroidogenesis",
        "androgen and testosterone biosynthesis",
        "estrogen biosynthesis",
        "cholesterol biosynthesis",
        "androgen receptor",
        "estrogen receptor",
        "glucocorticoid receptor",
        "lipid droplet",
        "ppar",
        "srebp",
        "lxr",
        "ferroptosis",
        "lipid peroxidation",
        "fatty acid synthesis",
    ]


def metabolic_keywords() -> List[str]:
    return [
        "leptin",
        "resistin",
        "insulin receptor",
        "irs",
        "pi3k-akt",
        "glycolysis",
        "lactate and hif1a",
        "glycogen",
        "pentose phosphate",
        "amino-acid transport",
        "arginine",
        "urea",
        "purine",
        "nad",
        "nrf2",
    ]


def complement_keywords() -> List[str]:
    return [
        "complement classical",
        "complement lectin",
        "complement alternative",
        "c3 convertase",
        "c3a and c5a",
        "opsonophagocytosis",
        "complement terminal mac",
        "complement regulators",
        "coagulation crosstalk",
    ]


def core_keywords() -> List[str]:
    return [
        "tlr4",
        "leptin",
        "pi3k-akt",
        "insulin receptor",
        "irs",
        "glycogen",
        "c3a and c5a",
        "opsonophagocytosis",
        "androgen receptor",
        "amino-acid transport",
    ]


def build_figure_5(
    store: SourceStore,
    outdir: Path,
    tabledir: Path,
) -> Tuple[plt.Figure, List[Path], List[plt.Axes]]:
    source_rows: List[pd.DataFrame] = []

    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 10.1))
    grid = fig.add_gridspec(
        3,
        3,
        left=0.11,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.73,
        wspace=0.72,
        height_ratios=[1.12, 1.02, 1.02],
    )
    a = fig.add_subplot(grid[0, 0:2])
    b = fig.add_subplot(grid[0, 2])
    c = fig.add_subplot(grid[1, 0])
    d = fig.add_subplot(grid[1, 1])
    e = fig.add_subplot(grid[1, 2])
    f = fig.add_subplot(grid[2, 0:2])
    g = fig.add_subplot(grid[2, 2])
    axes = [a, b, c, d, e, f, g]

    primary = store.table("Figure_5A", "primary_independent_effects")
    preterm = store.table("Figure_5B", "preterm_collapsed")
    broad = store.table("Figure_5C", "broad_effect_reliability")
    core = store.table("Figure_5D", "refined_core")
    synthesis = store.table("Figure_5D", "module_cellular_synthesis")

    labels = label_lookup(core)
    core["_priority"] = numeric(
        core.get(
            "independent_evidence_priority_score",
            pd.Series(index=core.index, dtype=float),
        )
    )

    features = select_features(
        core,
        endocrine_keywords(),
        12,
        "_priority",
    )

    # A
    panel_label(a, "A")
    matrix = independent_matrix(primary, features, labels)
    safe_heatmap(
        a,
        matrix,
        "Independent endocrine and lipid effects",
        "Independent dataset",
        "Endocrine/lipid module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        filter_features(primary, features),
        5,
        "A",
        "primary_independent_effects",
    )

    # B
    panel_label(b, "B")
    pregnancy = preterm_series(preterm, features, labels)
    horizontal_lollipop(
        b,
        pregnancy.index,
        pregnancy.values,
        "Pregnancy outcome effects",
        "Collapsed preterm-versus-term effect",
        20,
    )
    export_rows(
        source_rows,
        filter_features(preterm, features),
        5,
        "B",
        "preterm_collapsed",
    )

    # C
    panel_label(c, "C")
    broad_features = features[:8]
    cell_matrix = broad_matrix(broad, broad_features, labels)
    safe_heatmap(
        c,
        cell_matrix,
        "Broad-cell localization",
        "Broad immune population",
        "Endocrine/lipid module",
    )
    export_rows(
        source_rows,
        filter_features(broad, broad_features),
        5,
        "C",
        "broad_effect_reliability",
    )

    # D
    panel_label(d, "D")
    quadrant = filter_features(core, features).copy()
    x_column = (
        "median_effect"
        if "median_effect" in quadrant.columns
        else "independent_evidence_priority_score"
    )
    y_column = (
        "preterm_vs_term_effect"
        if "preterm_vs_term_effect" in quadrant.columns
        else "independent_evidence_priority_score"
    )
    quadrant["_x"] = numeric(quadrant[x_column])
    quadrant["_y"] = numeric(quadrant[y_column])
    d.scatter(quadrant["_x"], quadrant["_y"], s=22)
    add_zero(d, True)
    add_zero(d, False)
    for _, row in quadrant.dropna(subset=["_x", "_y"]).iterrows():
        d.annotate(
            compact(labels.get(str(row["feature_id"]), row["feature_id"]), 13),
            (row["_x"], row["_y"]),
            xytext=(2, 2),
            textcoords="offset points",
            fontsize=4.2,
        )
    d.set_xlabel("Median infection effect", fontsize=5.7)
    d.set_ylabel("Preterm-versus-term effect", fontsize=5.7)
    panel_title(d, "Steroid synthesis-response branching")
    finish_axis(d)
    export_rows(source_rows, quadrant, 5, "D", "refined_core")

    # E
    panel_label(e, "E")
    cholesterol = [
        feature
        for feature in features
        if re.search(
            r"cholesterol",
            labels.get(feature, feature),
            flags=re.IGNORECASE,
        )
    ]
    cholesterol_subset = filter_features(broad, cholesterol)
    if not cholesterol_subset.empty:
        value_column = (
            "module_mean_gene_log2FC"
            if "module_mean_gene_log2FC" in cholesterol_subset.columns
            else "cellular_localization_score"
        )
        population_column = (
            "population"
            if "population" in cholesterol_subset.columns
            else "refined_broad_cell_type"
        )
        summary = (
            cholesterol_subset.groupby(population_column)[value_column]
            .mean()
            .sort_values()
        )
    else:
        summary = pd.Series(dtype=float)
    horizontal_lollipop(
        e,
        summary.index,
        summary.values,
        "Pan-immune cholesterol pattern",
        "Mean module-gene log2 fold change",
        18,
    )
    export_rows(
        source_rows,
        cholesterol_subset,
        5,
        "E",
        "broad_effect_reliability",
    )

    # F
    panel_label(f, "F")
    lipid_features = [
        feature
        for feature in features
        if re.search(
            r"lipid|ppar|srebp|lxr|ferropt|fatty",
            labels.get(feature, feature),
            flags=re.IGNORECASE,
        )
    ][:7]
    lipid_matrix = broad_matrix(broad, lipid_features, labels)
    safe_heatmap(
        f,
        lipid_matrix,
        "Lipid-droplet, regulatory and lipid-stress programs",
        "Broad immune population",
        "Lipid module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        filter_features(broad, lipid_features),
        5,
        "F",
        "broad_effect_reliability",
    )

    # G
    panel_label(g, "G")
    support = subtype_support(synthesis, features, labels)
    support = support.sort_values("_score").tail(8)
    horizontal_lollipop(
        g,
        [
            f"{compact(row['_label'], 13)} | "
            f"{compact(row['_subtype'], 13)}"
            for _, row in support.iterrows()
        ],
        support["_score"],
        "Refined-subtype support",
        "Composite support score",
        24,
    )
    export_rows(
        source_rows,
        support,
        5,
        "G",
        "module_cellular_synthesis",
    )

    paths = save_figure(fig, outdir, 5)
    save_source_rows(source_rows, tabledir, 5)
    return fig, paths, axes


def build_figure_6(
    store: SourceStore,
    outdir: Path,
    tabledir: Path,
) -> Tuple[plt.Figure, List[Path], List[plt.Axes]]:
    source_rows: List[pd.DataFrame] = []

    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 11.3))
    grid = fig.add_gridspec(
        4,
        2,
        left=0.11,
        right=0.97,
        bottom=0.06,
        top=0.96,
        hspace=0.70,
        wspace=0.68,
    )
    axes = [
        fig.add_subplot(grid[row, column])
        for row in range(4)
        for column in range(2)
    ]
    a, b, c, d, e, f, g, h = axes

    primary = store.table("Figure_6A", "primary_independent_effects")
    preterm = store.table("Figure_6B", "preterm_collapsed")
    broad = store.table("Figure_6C", "broad_effect_reliability")
    synthesis = store.table("Figure_6D", "module_cellular_synthesis")
    core = store.table("Figure_6E", "refined_core")

    labels = label_lookup(core)
    core["_priority"] = numeric(
        core.get(
            "independent_evidence_priority_score",
            pd.Series(index=core.index, dtype=float),
        )
    )
    features = select_features(
        core,
        metabolic_keywords(),
        14,
        "_priority",
    )

    # A
    panel_label(a, "A")
    matrix = independent_matrix(primary, features[:11], labels)
    safe_heatmap(
        a,
        matrix,
        "Independent adipokine, insulin and carbon effects",
        "Independent dataset",
        "Immunometabolic module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        filter_features(primary, features[:11]),
        6,
        "A",
        "primary_independent_effects",
    )

    # B
    panel_label(b, "B")
    pregnancy_features = [
        feature
        for feature in features
        if re.search(
            r"leptin|insulin|irs|pi3k|glycogen|glycol",
            labels.get(feature, feature),
            flags=re.IGNORECASE,
        )
    ][:8]
    pregnancy = preterm_series(
        preterm,
        pregnancy_features,
        labels,
    )
    horizontal_lollipop(
        b,
        pregnancy.index,
        pregnancy.values,
        "Pregnancy-associated signaling attenuation",
        "Collapsed preterm-versus-term effect",
        22,
    )
    export_rows(
        source_rows,
        filter_features(preterm, pregnancy_features),
        6,
        "B",
        "preterm_collapsed",
    )

    # C
    panel_label(c, "C")
    trajectory_features = features[:8]
    cell_matrix = broad_matrix(
        broad,
        trajectory_features,
        labels,
    )
    safe_heatmap(
        c,
        cell_matrix,
        "Broad-cell signaling trajectories",
        "Broad immune population",
        "Signaling/carbon module",
    )
    export_rows(
        source_rows,
        filter_features(broad, trajectory_features),
        6,
        "C",
        "broad_effect_reliability",
    )

    # D
    panel_label(d, "D")
    support = subtype_support(
        synthesis,
        features[:10],
        labels,
    ).sort_values("_score").tail(9)
    horizontal_lollipop(
        d,
        [
            f"{compact(row['_label'], 13)} | "
            f"{compact(row['_subtype'], 13)}"
            for _, row in support.iterrows()
        ],
        support["_score"],
        "Refined-subtype support",
        "Composite support score",
        24,
    )
    export_rows(
        source_rows,
        support,
        6,
        "D",
        "module_cellular_synthesis",
    )

    # E
    axis_off(e)
    panel_label(e, "E")
    panel_title(e, "Leptin-IRS-PI3K/AKT coupling")
    draw_box(e, (0.05, 0.61), 0.23, 0.15, "Leptin")
    draw_box(e, (0.38, 0.72), 0.23, 0.15, "Leptin receptor")
    draw_box(e, (0.38, 0.42), 0.23, 0.15, "Insulin receptor\nand IRS")
    draw_box(e, (0.70, 0.58), 0.24, 0.17, "PI3K-AKT")
    draw_box(e, (0.70, 0.22), 0.24, 0.17, "Inflammatory carbon\nand glycogen use")
    draw_box(e, (0.05, 0.20), 0.23, 0.15, "TLR4-LPS")
    for start, end in [
        ((0.28, 0.685), (0.38, 0.795)),
        ((0.61, 0.795), (0.70, 0.665)),
        ((0.61, 0.495), (0.70, 0.635)),
        ((0.28, 0.275), (0.70, 0.63)),
        ((0.82, 0.58), (0.82, 0.39)),
    ]:
        arrow(e, start, end)
    e.text(
        0.5,
        0.05,
        "Evidence-weighted coupling; not a claim of direct causal sequence.",
        ha="center",
        fontsize=4.8,
    )
    e.set_xlim(0, 1)
    e.set_ylim(0, 1)
    export_rows(
        source_rows,
        filter_features(core, pregnancy_features),
        6,
        "E",
        "refined_core",
    )

    # F
    panel_label(f, "F")
    carbon_features = [
        feature
        for feature in features
        if re.search(
            r"glycol|lactate|hif|glycogen|pentose",
            labels.get(feature, feature),
            flags=re.IGNORECASE,
        )
    ][:7]
    carbon_matrix = broad_matrix(
        broad,
        carbon_features,
        labels,
    )
    safe_heatmap(
        f,
        carbon_matrix,
        "Inflammatory carbon-use programs",
        "Broad immune population",
        "Carbon-metabolism module",
    )
    export_rows(
        source_rows,
        filter_features(broad, carbon_features),
        6,
        "F",
        "broad_effect_reliability",
    )

    # G
    panel_label(g, "G")
    amino_features = [
        feature
        for feature in features
        if re.search(
            r"amino|arginine|urea|nitric|nitrogen",
            labels.get(feature, feature),
            flags=re.IGNORECASE,
        )
    ][:6]
    amino_matrix = broad_matrix(
        broad,
        amino_features,
        labels,
    )
    safe_heatmap(
        g,
        amino_matrix,
        "Amino-acid transport and arginine-NO-urea",
        "Broad immune population",
        "Nitrogen-metabolism module",
    )
    export_rows(
        source_rows,
        filter_features(broad, amino_features),
        6,
        "G",
        "broad_effect_reliability",
    )

    # H
    panel_label(h, "H")
    redox_features = [
        feature
        for feature in features
        if re.search(
            r"purine|nad|nrf2|redox|oxid",
            labels.get(feature, feature),
            flags=re.IGNORECASE,
        )
    ][:6]
    redox_matrix = broad_matrix(
        broad,
        redox_features,
        labels,
    )
    safe_heatmap(
        h,
        redox_matrix,
        "Purine, NAD and NRF2-redox remodeling",
        "Broad immune population",
        "Purine/redox module",
    )
    export_rows(
        source_rows,
        filter_features(broad, redox_features),
        6,
        "H",
        "broad_effect_reliability",
    )

    paths = save_figure(fig, outdir, 6)
    save_source_rows(source_rows, tabledir, 6)
    return fig, paths, axes


def build_figure_7(
    store: SourceStore,
    outdir: Path,
    tabledir: Path,
) -> Tuple[plt.Figure, List[Path], List[plt.Axes]]:
    source_rows: List[pd.DataFrame] = []

    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 10.2))
    grid = fig.add_gridspec(
        3,
        3,
        left=0.11,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.73,
        wspace=0.72,
        height_ratios=[1.08, 1.02, 1.02],
    )
    a = fig.add_subplot(grid[0, 0:2])
    b = fig.add_subplot(grid[0, 2])
    c = fig.add_subplot(grid[1, 0])
    d = fig.add_subplot(grid[1, 1])
    e = fig.add_subplot(grid[1, 2])
    f = fig.add_subplot(grid[2, 0:2])
    g = fig.add_subplot(grid[2, 2])
    axes = [a, b, c, d, e, f, g]

    primary = store.table("Figure_7A", "primary_independent_effects")
    preterm = store.table("Figure_7B", "preterm_collapsed")
    broad = store.table("Figure_7C", "broad_effect_reliability")
    synthesis = store.table("Figure_7D", "module_cellular_synthesis")
    core = store.table("Figure_7E", "refined_core")

    labels = label_lookup(core)
    core["_priority"] = numeric(
        core.get(
            "independent_evidence_priority_score",
            pd.Series(index=core.index, dtype=float),
        )
    )
    features = select_features(
        core,
        complement_keywords(),
        9,
        "_priority",
    )

    # A
    panel_label(a, "A")
    matrix = independent_matrix(primary, features, labels)
    safe_heatmap(
        a,
        matrix,
        "Independent complement effects by branch",
        "Independent dataset",
        "Complement module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        filter_features(primary, features),
        7,
        "A",
        "primary_independent_effects",
    )

    # B
    panel_label(b, "B")
    pregnancy = preterm_series(preterm, features, labels)
    horizontal_lollipop(
        b,
        pregnancy.index,
        pregnancy.values,
        "Pregnancy complement effects",
        "Collapsed preterm-versus-term effect",
        20,
    )
    export_rows(
        source_rows,
        filter_features(preterm, features),
        7,
        "B",
        "preterm_collapsed",
    )

    # C
    panel_label(c, "C")
    cell_matrix = broad_matrix(
        broad,
        features,
        labels,
    )
    safe_heatmap(
        c,
        cell_matrix,
        "Broad-cell complement localization",
        "Broad immune population",
        "Complement module",
    )
    export_rows(
        source_rows,
        filter_features(broad, features),
        7,
        "C",
        "broad_effect_reliability",
    )

    # D
    panel_label(d, "D")
    support = subtype_support(
        synthesis,
        features,
        labels,
    ).sort_values("_score").tail(8)
    horizontal_lollipop(
        d,
        [
            f"{compact(row['_label'], 12)} | "
            f"{compact(row['_subtype'], 12)}"
            for _, row in support.iterrows()
        ],
        support["_score"],
        "Refined-subtype support",
        "Composite support score",
        23,
    )
    export_rows(
        source_rows,
        support,
        7,
        "D",
        "module_cellular_synthesis",
    )

    # E
    axis_off(e)
    panel_label(e, "E")
    panel_title(e, "Complement branch topology")
    draw_box(e, (0.05, 0.73), 0.23, 0.14, "Classical")
    draw_box(e, (0.05, 0.49), 0.23, 0.14, "Lectin")
    draw_box(e, (0.05, 0.25), 0.23, 0.14, "Alternative")
    draw_box(e, (0.38, 0.59), 0.24, 0.17, "C3 convertase\nand amplification")
    draw_box(e, (0.70, 0.69), 0.24, 0.15, "C3a/C5a\nsignaling")
    draw_box(e, (0.70, 0.42), 0.24, 0.15, "Opsonophagocytosis")
    draw_box(e, (0.70, 0.15), 0.24, 0.15, "Terminal MAC")
    for start, end in [
        ((0.28, 0.80), (0.38, 0.69)),
        ((0.28, 0.56), (0.38, 0.67)),
        ((0.28, 0.32), (0.38, 0.64)),
        ((0.62, 0.68), (0.70, 0.76)),
        ((0.62, 0.66), (0.70, 0.49)),
        ((0.62, 0.63), (0.70, 0.22)),
    ]:
        arrow(e, start, end)
    e.text(
        0.5,
        0.04,
        "Regulatory and coagulation-crosstalk modules modulate multiple stages.",
        ha="center",
        fontsize=4.6,
    )
    e.set_xlim(0, 1)
    e.set_ylim(0, 1)
    export_rows(
        source_rows,
        filter_features(core, features),
        7,
        "E",
        "refined_core",
    )

    # F
    panel_label(f, "F")
    comparison = filter_features(core, features).copy()
    comparison["_infection"] = numeric(
        comparison.get(
            "median_effect",
            comparison.get(
                "independent_evidence_priority_score",
                pd.Series(index=comparison.index, dtype=float),
            ),
        )
    )
    comparison["_preterm"] = numeric(
        comparison.get(
            "preterm_vs_term_effect",
            pd.Series(index=comparison.index, dtype=float),
        )
    )
    f.scatter(
        comparison["_infection"],
        comparison["_preterm"],
        s=24,
    )
    add_zero(f, True)
    add_zero(f, False)
    for _, row in comparison.dropna(
        subset=["_infection", "_preterm"]
    ).iterrows():
        f.annotate(
            compact(labels.get(str(row["feature_id"]), row["feature_id"]), 15),
            (row["_infection"], row["_preterm"]),
            xytext=(2, 2),
            textcoords="offset points",
            fontsize=4.3,
        )
    f.set_xlabel("Median infection effect", fontsize=5.8)
    f.set_ylabel("Preterm-versus-term effect", fontsize=5.8)
    panel_title(f, "C3a/C5a versus opsonophagocytic architecture")
    finish_axis(f)
    export_rows(
        source_rows,
        comparison,
        7,
        "F",
        "refined_core",
    )

    # G
    panel_label(g, "G")
    coverage_rows = []
    for feature in features:
        cell_rows = broad[
            broad["feature_id"].astype(str) == str(feature)
        ]
        coverage_rows.append(
            {
                "feature_id": feature,
                "display_label": labels.get(feature, feature),
                "broad_populations_with_values": int(
                    cell_rows["population"].nunique()
                )
                if "population" in cell_rows.columns
                else 0,
                "maximum_absolute_cell_effect": float(
                    numeric(
                        cell_rows.get(
                            "module_mean_gene_log2FC",
                            pd.Series(dtype=float),
                        )
                    ).abs().max()
                )
                if len(cell_rows)
                else 0.0,
            }
        )
    coverage = pd.DataFrame(coverage_rows).sort_values(
        "broad_populations_with_values"
    )
    horizontal_lollipop(
        g,
        coverage["display_label"],
        coverage["broad_populations_with_values"],
        "Cellular coverage by complement stage",
        "Broad populations with eligible values",
        20,
    )
    export_rows(
        source_rows,
        coverage,
        7,
        "G",
        "derived_cellular_coverage",
        "Derived only from locked broad-effect rows.",
    )

    paths = save_figure(fig, outdir, 7)
    save_source_rows(source_rows, tabledir, 7)
    return fig, paths, axes


def build_figure_8(
    store: SourceStore,
    outdir: Path,
    tabledir: Path,
) -> Tuple[plt.Figure, List[Path], List[plt.Axes]]:
    source_rows: List[pd.DataFrame] = []

    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 9.2))
    grid = fig.add_gridspec(
        3,
        2,
        left=0.11,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.70,
        wspace=0.68,
    )
    axes = [
        fig.add_subplot(grid[row, column])
        for row in range(3)
        for column in range(2)
    ]
    a, b, c, d, e, f = axes

    primary = store.table("Figure_8A", "primary_independent_effects")
    preterm = store.table("Figure_8A", "preterm_collapsed")
    broad = store.table("Figure_8B", "broad_effect_reliability")
    composition = store.table(
        "Figure_8C",
        "celltype_composition_effects",
    )
    targeted = store.table(
        "Figure_8D",
        "targeted_state_effects",
    )
    core = store.table("Figure_8E", "refined_core")
    synthesis = store.table(
        "Figure_8E",
        "module_cellular_synthesis",
    )

    labels = label_lookup(core)
    core["_priority"] = numeric(
        core.get(
            "independent_evidence_priority_score",
            pd.Series(index=core.index, dtype=float),
        )
    )
    features = select_features(
        core,
        core_keywords(),
        10,
        "_priority",
    )

    # A
    panel_label(a, "A")
    independent = independent_matrix(
        primary,
        features,
        labels,
    )
    pregnancy = preterm_series(
        preterm,
        features,
        labels,
    )
    combined = independent.copy()
    if not pregnancy.empty:
        combined["Preterm vs term"] = pregnancy.reindex(combined.index)
    safe_heatmap(
        a,
        combined,
        "Core modules across infection and pregnancy",
        "Evidence context",
        "Core module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        filter_features(primary, features),
        8,
        "A",
        "primary_independent_effects",
    )
    export_rows(
        source_rows,
        filter_features(preterm, features),
        8,
        "A",
        "preterm_collapsed",
    )

    # B
    panel_label(b, "B")
    cell_matrix = broad_matrix(
        broad,
        features,
        labels,
    )
    safe_heatmap(
        b,
        cell_matrix,
        "Cell-source-resolved core localization",
        "Broad immune population",
        "Core module",
    )
    export_rows(
        source_rows,
        filter_features(broad, features),
        8,
        "B",
        "broad_effect_reliability",
    )

    # C
    panel_label(c, "C")
    composition = composition.copy()
    label_col = (
        "refined_broad_cell_type"
        if "refined_broad_cell_type" in composition.columns
        else label_column(composition)
    )
    value_col = (
        "difference_UPEC_minus_control"
        if "difference_UPEC_minus_control" in composition.columns
        else composition.select_dtypes(include=[np.number]).columns[0]
    )
    composition["_value"] = numeric(composition[value_col])
    composition = composition.sort_values("_value")
    horizontal_lollipop(
        c,
        composition[label_col],
        composition["_value"],
        "UPEC-associated cell-composition shifts",
        "Difference: UPEC minus control",
        20,
    )
    export_rows(
        source_rows,
        composition,
        8,
        "C",
        "celltype_composition_effects",
    )

    # D
    panel_label(d, "D")
    targeted = targeted.copy()
    measure_col = (
        "targeted_measure"
        if "targeted_measure" in targeted.columns
        else label_column(targeted)
    )
    value_col = (
        "difference_UPEC_minus_control"
        if "difference_UPEC_minus_control" in targeted.columns
        else targeted.select_dtypes(include=[np.number]).columns[0]
    )
    targeted["_value"] = numeric(targeted[value_col])
    targeted = targeted.sort_values("_value")
    horizontal_lollipop(
        d,
        targeted[measure_col],
        targeted["_value"],
        "Treg-like and TNFSF9 macrophage states",
        "Difference: UPEC minus control",
        22,
    )
    export_rows(
        source_rows,
        targeted,
        8,
        "D",
        "targeted_state_effects",
    )

    # E
    axis_off(e)
    panel_label(e, "E")
    panel_title(e, "Integrated mechanistic network")
    draw_box(e, (0.03, 0.69), 0.21, 0.14, "UPEC / TLR4")
    draw_box(e, (0.31, 0.76), 0.23, 0.14, "Leptin-IRS-\nPI3K/AKT")
    draw_box(e, (0.31, 0.49), 0.23, 0.14, "Complement and\nopsonophagocytosis")
    draw_box(e, (0.31, 0.22), 0.23, 0.14, "Steroid and lipid\nbranching")
    draw_box(e, (0.65, 0.76), 0.27, 0.14, "Carbon, nitrogen\nand redox remodeling")
    draw_box(e, (0.65, 0.49), 0.27, 0.14, "Myeloid, dendritic\nand lymphoid localization")
    draw_box(e, (0.65, 0.22), 0.27, 0.14, "Pregnancy- and\ntissue-specific outcome")
    for start, end in [
        ((0.24, 0.76), (0.31, 0.83)),
        ((0.24, 0.76), (0.31, 0.56)),
        ((0.24, 0.76), (0.31, 0.29)),
        ((0.54, 0.83), (0.65, 0.83)),
        ((0.54, 0.56), (0.65, 0.56)),
        ((0.54, 0.29), (0.65, 0.29)),
        ((0.785, 0.76), (0.785, 0.63)),
        ((0.785, 0.49), (0.785, 0.36)),
    ]:
        arrow(e, start, end)
    e.text(
        0.5,
        0.05,
        "Integrated hypothesis model; branch associations remain context-dependent.",
        ha="center",
        fontsize=4.7,
    )
    e.set_xlim(0, 1)
    e.set_ylim(0, 1)
    export_rows(
        source_rows,
        filter_features(core, features),
        8,
        "E",
        "refined_core",
    )
    export_rows(
        source_rows,
        filter_features(synthesis, features),
        8,
        "E",
        "module_cellular_synthesis",
    )

    # F
    axis_off(f)
    panel_label(f, "F")
    panel_title(f, "Evidence hierarchy and interpretation boundary")

    evidence_counts = (
        core["validation_class"]
        .fillna("unclassified")
        .astype(str)
        .value_counts()
        .head(5)
    )

    y = 0.86
    f.text(
        0.04,
        y,
        "Evidence tiers",
        fontsize=6.0,
        fontweight="bold",
        ha="left",
    )
    y -= 0.10
    for label, count in evidence_counts.items():
        f.text(
            0.06,
            y,
            f"• {compact(label, 30).replace(chr(10), ' ')}: n={count}",
            fontsize=4.9,
            ha="left",
        )
        y -= 0.075

    f.text(
        0.54,
        0.86,
        "Interpretation boundary",
        fontsize=6.0,
        fontweight="bold",
        ha="left",
    )
    boundary_lines = [
        "No broad pregnancy FDR support.",
        "Cellular attribution is descriptive at n=2 vs n=2.",
        "Metabolic modules infer transcriptional activity, not flux.",
        "Cross-species synthesis uses concordance, not pooled expression.",
        "Complement core remains provisional where sample support is limited.",
    ]
    y = 0.76
    for line in boundary_lines:
        f.text(
            0.56,
            y,
            f"• {line}",
            fontsize=4.8,
            ha="left",
        )
        y -= 0.105

    f.text(
        0.5,
        0.05,
        "The final model separates robust recurrence from provisional and contextual biology.",
        ha="center",
        fontsize=4.8,
    )
    f.set_xlim(0, 1)
    f.set_ylim(0, 1)
    export_rows(
        source_rows,
        core,
        8,
        "F",
        "refined_core",
    )

    paths = save_figure(fig, outdir, 8)
    save_source_rows(source_rows, tabledir, 8)
    return fig, paths, axes


def visual_reference_audit(project: Path) -> pd.DataFrame:
    directory = project / "06_figures" / U27A4_TAG
    rows = []
    for figure_number in range(7, 12):
        for extension in ("png", "svg", "pdf"):
            path = (
                directory
                / f"UTI_HostOmics_U27A4_Figure_{figure_number}.{extension}"
            )
            rows.append(
                {
                    "working_figure": figure_number,
                    "format": extension,
                    "path": str(path),
                    "exists": path.exists(),
                    "size_bytes": path.stat().st_size if path.exists() else 0,
                    "use": "visual_grammar_reference_only",
                }
            )
    return pd.DataFrame(rows)


def export_audit(
    paths: Sequence[Path],
    tabledir: Path,
) -> pd.DataFrame:
    rows = []
    for path in paths:
        row = {
            "path": str(path),
            "filename": path.name,
            "format": path.suffix.lower().lstrip("."),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "png_width_px": "",
            "png_height_px": "",
        }
        if (
            path.suffix.lower() == ".png"
            and Image is not None
            and path.exists()
        ):
            with Image.open(path) as image:
                row["png_width_px"], row["png_height_px"] = image.size
        rows.append(row)

    frame = pd.DataFrame(rows)
    frame.to_csv(
        tabledir / "UTI_HostOmics_U27B2D_export_audit.tsv",
        sep="\t",
        index=False,
    )
    return frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    registry_path = (
        project
        / "03_metadata"
        / FREEZE_TAG
        / "UTI_HostOmics_U27B2C2E_frozen_source_registry.tsv"
    )
    panel_map_path = (
        project
        / "03_metadata"
        / ARCH_TAG
        / "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv"
    )

    if not registry_path.exists():
        raise FileNotFoundError(
            f"Frozen source registry not found: {registry_path}"
        )
    if not panel_map_path.exists():
        raise FileNotFoundError(
            f"Frozen panel map not found: {panel_map_path}"
        )

    registry = pd.read_csv(
        registry_path,
        sep="\t",
        low_memory=False,
    )
    panel_map = pd.read_csv(
        panel_map_path,
        sep="\t",
        low_memory=False,
    )

    outfig = project / "06_figures" / TAG
    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    cropdir = outfig / "panel_crops"

    for directory in (
        outfig,
        outtables,
        outmetadata,
        outresults,
        cropdir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    references = visual_reference_audit(project)
    references.to_csv(
        outtables
        / "UTI_HostOmics_U27B2D_U27A4_visual_reference_audit.tsv",
        sep="\t",
        index=False,
    )

    if not bool(references["exists"].all()):
        missing = references[~references["exists"]]["path"].tolist()
        raise FileNotFoundError(
            "Missing required U27A4 visual-reference assets: "
            + "; ".join(missing)
        )

    store = SourceStore(registry)

    figure_paths: List[Path] = []
    crop_paths: List[Path] = []

    builders = [
        (5, build_figure_5),
        (6, build_figure_6),
        (7, build_figure_7),
        (8, build_figure_8),
    ]

    for figure_number, builder in builders:
        log(f"Building Final Figure {figure_number}.")
        fig, paths, axes = builder(
            store,
            outfig,
            outtables,
        )
        figure_paths.extend(paths)
        crop_paths.extend(
            panel_crops(
                fig,
                axes,
                cropdir,
                figure_number,
            )
        )
        plt.close(fig)

    png_paths = [
        path
        for path in figure_paths
        if path.suffix.lower() == ".png"
    ]

    full_contact = (
        outfig
        / "UTI_HostOmics_U27B2D_full_figure_contact_sheet.png"
    )
    panel_contact = (
        outfig
        / "UTI_HostOmics_U27B2D_panel_contact_sheet.png"
    )

    make_contact_sheet(
        png_paths,
        full_contact,
        columns=2,
        cell_width=1120,
    )
    make_contact_sheet(
        crop_paths,
        panel_contact,
        columns=4,
        cell_width=710,
    )

    audit = export_audit(
        figure_paths,
        outtables,
    )

    build_manifest = panel_map[
        panel_map["final_figure"].isin(
            ["Figure_5", "Figure_6", "Figure_7", "Figure_8"]
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
        / "UTI_HostOmics_U27B2D_Figures_5_to_8_build_manifest.tsv",
        sep="\t",
        index=False,
    )

    registry_paths_exist = bool(
        build_manifest["locked_path"]
        .dropna()
        .astype(str)
        .map(lambda value: Path(value).exists())
        .all()
    )

    expected_panels = sum(EXPECTED_PANEL_COUNTS.values())
    observed_panels = build_manifest["panel_key"].nunique()
    expected_exports = 4 * 3
    observed_exports = int(audit["exists"].sum())
    exports_nonempty = bool((audit["size_bytes"] > 0).all())
    contact_sheets_present = (
        full_contact.exists()
        and panel_contact.exists()
    )

    if (
        observed_panels == expected_panels
        and len(crop_paths) == expected_panels
        and observed_exports == expected_exports
        and exports_nonempty
        and contact_sheets_present
        and registry_paths_exist
        and bool(references["exists"].all())
    ):
        decision = (
            "READY_FOR_U27B2E_FINAL_FIGURES_5_TO_8_VISUAL_AUDIT"
        )
    else:
        decision = "TARGETED_U27B2D_FIGURE_BUILD_REPAIR_REQUIRED"

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B2D",
                "decision": decision,
                "figures_expected": 4,
                "figures_built": len(png_paths),
                "panels_expected": expected_panels,
                "panels_in_manifest": observed_panels,
                "panel_crops_present": len(crop_paths),
                "exports_expected": expected_exports,
                "exports_present": observed_exports,
                "nonempty_exports": exports_nonempty,
                "contact_sheets_present": contact_sheets_present,
                "locked_source_paths_exist": registry_paths_exist,
                "U27A4_visual_references_complete": bool(
                    references["exists"].all()
                ),
                "U27A4_used_as_numerical_source": False,
                "scientific_values_recalculated": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B2E final visual audit of Figures 5-8"
                    if decision.startswith("READY_FOR_U27B2E")
                    else "Repair missing sources, exports or panel crops"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B2D_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B2D_final_figures_5_to_8_build_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2D - Final Figures 5-8 build\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Figures built: **4/4**.\n")
        handle.write(
            f"- Frozen panels represented: "
            f"**{observed_panels}/{expected_panels}**.\n"
        )
        handle.write(
            f"- PNG/SVG/PDF exports: "
            f"**{observed_exports}/{expected_exports}**.\n"
        )
        handle.write(
            f"- Panel crops: **{len(crop_paths)}/{expected_panels}**.\n"
        )
        handle.write(
            f"- U27A4 visual-reference assets verified: "
            f"**{int(references['exists'].sum())}/{len(references)}**.\n\n"
        )

        handle.write("## Figure identities\n\n")
        handle.write(
            "- Figure 5: steroid, cholesterol and lipid-remodeling architecture.\n"
            "- Figure 6: adipokine, insulin and integrated immunometabolism.\n"
            "- Figure 7: complement branch and cellular architecture.\n"
            "- Figure 8: integrated endocrine-metabolic-immune model.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "All numerical panels use the frozen source registry. U27A4 "
            "Figures 7-11 were verified and used only to preserve visual "
            "grammar; they were not treated as numerical data sources. "
            "No statistical effects were recalculated.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "figures_built": len(png_paths),
        "panels": observed_panels,
        "panel_crops": len(crop_paths),
        "exports": observed_exports,
        "U27A4_visual_references_complete": bool(
            references["exists"].all()
        ),
        "U27A4_used_as_numerical_source": False,
        "scientific_values_recalculated": False,
        "manuscript_modified": False,
    }
    (
        outresults
        / "UTI_HostOmics_U27B2D_run_manifest.json"
    ).write_text(
        json.dumps(run_manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Figures built: {len(png_paths)}/4")
    log(f"Panels represented: {observed_panels}/{expected_panels}")
    log(f"Panel crops: {len(crop_paths)}/{expected_panels}")
    log(f"Exports present: {observed_exports}/{expected_exports}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2D] ERROR: {exc}", file=sys.stderr)
        raise
