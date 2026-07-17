#!/usr/bin/env python3
"""
Phase U27B2E1
Pathway-specific reconstruction of manuscript-facing Final Figures 5-8.

Why this repair is required
---------------------------
The U27B2D build completed technically, but several pathway-specific panels
used unrelated high-priority fallback modules when keyword matching returned
too few requested modules. This produced:
- endocrine/lipid panels containing TLR4, complement and insulin modules;
- carbon, amino-acid and redox panels with one or zero eligible modules;
- complement panels containing non-complement modules;
- an overly compressed evidence-boundary panel.

This phase:
1. uses the full U26A 78-submodule dictionary to define pathway membership;
2. uses the corrected 81-module GSE280297 C1-C3 matrix for pathway-complete
   pregnancy and context panels;
3. intersects pathway-defined modules with each locked source table;
4. never fills a pathway panel with unrelated fallback modules;
5. reconstructs Figures 5-8 and exports 28 panel crops and source tables.

No statistical effects are recalculated.
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


VERSION = "U27B2E1_v1.0_2026-07-16"
TAG = "phaseU27B2E1_pathway_specific_figures_5_to_8_reconstruction"
BASE_SCRIPT = "phaseU27B2D_build_final_figures_5_to_8.py"
FREEZE_TAG = "phaseU27B2C2E_final_figures_1_to_4_freeze"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"

FULL_EFFECT_MATRIX_RELATIVE = (
    "06_tables/"
    "phaseU27B2C2A_GSE280297_full_effect_source_repair/"
    "UTI_HostOmics_U27B2C2A_GSE280297_full_tissue_effect_matrix.tsv"
)

FIGURE_WIDTH_IN = 180 / 25.4
DPI = 300
EXPECTED_PANEL_COUNTS = {5: 7, 6: 8, 7: 7, 8: 6}


def log(message: str) -> None:
    print(f"[U27B2E1] {message}", flush=True)


def load_module(path: Path, name: str):
    if not path.exists():
        raise FileNotFoundError(f"Required script not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def compact(value: object, width: int = 22) -> str:
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
        fontsize=9.2,
        fontweight="bold",
        ha="left",
        va="bottom",
        clip_on=False,
    )


def panel_title(ax: plt.Axes, title: str) -> None:
    title = str(title)
    if len(title) > 31:
        title = "\n".join(
            textwrap.wrap(title, width=30, break_long_words=False)
        )
    ax.set_title(
        title,
        loc="left",
        x=0.02,
        fontsize=7.1,
        fontweight="bold",
        pad=4,
        linespacing=0.94,
    )


def finish_axis(ax: plt.Axes) -> None:
    ax.tick_params(labelsize=4.8, length=2.0, width=0.5)
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
    fontsize: float = 5.4,
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


def normalize_library(frame: pd.DataFrame) -> pd.DataFrame:
    library = frame.copy()

    if "feature_id" not in library.columns:
        for candidate in ("submodule_id", "module_id"):
            if candidate in library.columns:
                library = library.rename(
                    columns={candidate: "feature_id"}
                )
                break

    if "display_label" not in library.columns:
        for candidate in ("module_label", "feature_label"):
            if candidate in library.columns:
                library = library.rename(
                    columns={candidate: "display_label"}
                )
                break

    required = {"feature_id", "display_label", "axis"}
    missing = sorted(required - set(library.columns))
    if missing:
        raise RuntimeError(
            "Module library missing required columns: "
            + ", ".join(missing)
        )

    library["feature_id"] = library["feature_id"].astype(str)
    library["display_label"] = library["display_label"].astype(str)
    library["axis"] = library["axis"].astype(str)
    library["_text"] = (
        library["feature_id"]
        + " "
        + library["display_label"]
        + " "
        + library["axis"]
    ).str.lower()

    return library.drop_duplicates("feature_id")


def feature_ids_for_axis(
    library: pd.DataFrame,
    axis_terms: Sequence[str],
    available_ids: Optional[Iterable[str]] = None,
) -> List[str]:
    mask = pd.Series(False, index=library.index)
    axis_text = library["axis"].str.lower()

    for term in axis_terms:
        mask = mask | axis_text.str.contains(
            str(term).lower(),
            regex=False,
            na=False,
        )

    subset = library[mask].copy()

    if available_ids is not None:
        available = {str(value) for value in available_ids}
        subset = subset[
            subset["feature_id"].astype(str).isin(available)
        ]

    return subset["feature_id"].astype(str).tolist()


def prioritized_features(
    library: pd.DataFrame,
    candidate_ids: Sequence[str],
    priority_terms: Sequence[str],
    maximum: int,
) -> List[str]:
    candidates = library[
        library["feature_id"].astype(str).isin(
            [str(value) for value in candidate_ids]
        )
    ].copy()

    selected: List[str] = []
    for term in priority_terms:
        matches = candidates[
            candidates["_text"].str.contains(
                str(term).lower(),
                regex=False,
                na=False,
            )
            & ~candidates["feature_id"].astype(str).isin(selected)
        ]
        for feature in matches["feature_id"].astype(str):
            selected.append(feature)
            if len(selected) >= maximum:
                return selected

    # Complete only with modules from the same pre-defined biological axis.
    for feature in candidates["feature_id"].astype(str):
        if feature not in selected:
            selected.append(feature)
        if len(selected) >= maximum:
            break

    return selected


def label_lookup(library: pd.DataFrame) -> Dict[str, str]:
    return dict(
        zip(
            library["feature_id"].astype(str),
            library["display_label"].astype(str),
        )
    )


def available_ids(frame: pd.DataFrame) -> set[str]:
    if "feature_id" not in frame.columns:
        return set()
    return set(frame["feature_id"].astype(str))


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


def full_context_matrix(
    full_matrix: pd.DataFrame,
    feature_ids: Sequence[str],
    labels: Dict[str, str],
    prefixes: Sequence[str] = ("C1_", "C2_", "C3_"),
) -> pd.DataFrame:
    columns = [
        column
        for column in full_matrix.columns
        if any(str(column).startswith(prefix) for prefix in prefixes)
    ]

    subset = (
        full_matrix[
            full_matrix["feature_id"].astype(str).isin(
                [str(value) for value in feature_ids]
            )
        ]
        .set_index("feature_id")[columns]
        .apply(pd.to_numeric, errors="coerce")
    )

    order = [value for value in feature_ids if value in subset.index]
    subset = subset.reindex(order)
    subset.index = [labels.get(value, value) for value in subset.index]

    renamed = []
    for column in subset.columns:
        text = str(column)
        contrast = text.split("_")[0]
        tissue = text.split("|")[-1].strip() if "|" in text else ""
        renamed.append(f"{contrast} {tissue}".strip())
    subset.columns = renamed

    return subset


def full_prefix_matrix(
    full_matrix: pd.DataFrame,
    feature_ids: Sequence[str],
    labels: Dict[str, str],
    prefix: str,
) -> pd.DataFrame:
    return full_context_matrix(
        full_matrix,
        feature_ids,
        labels,
        prefixes=(prefix,),
    )


def preterm_series(
    frame: pd.DataFrame,
    feature_ids: Sequence[str],
    labels: Dict[str, str],
) -> pd.Series:
    subset = filter_features(frame, feature_ids)
    if subset.empty:
        return pd.Series(dtype=float)

    subset["_effect"] = numeric(subset["effect_value"])
    series = subset.groupby("feature_id")["_effect"].mean()
    order = [value for value in feature_ids if value in series.index]
    series = series.reindex(order)
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
            "No eligible pathway-specific values",
            ha="center",
            va="center",
            fontsize=5.7,
        )
        return

    values = matrix.to_numpy(dtype=float)
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
        fontsize=4.4,
    )
    ax.set_yticks(np.arange(matrix.shape[0]))
    ax.set_yticklabels(
        [compact(value, 20) for value in matrix.index],
        fontsize=4.35,
    )
    ax.set_xlabel(xlabel, fontsize=5.6)
    ax.set_ylabel(ylabel, fontsize=5.6)

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
    colorbar.ax.tick_params(labelsize=4.2, length=1.8)
    finish_axis(ax)


def horizontal_lollipop(
    ax: plt.Axes,
    labels: Sequence[str],
    values: Sequence[float],
    title: str,
    xlabel: str,
    label_width: int = 21,
) -> None:
    panel_title(ax, title)

    labels = list(labels)
    values = np.asarray(values, dtype=float)
    keep = np.isfinite(values)
    labels = [label for label, valid in zip(labels, keep) if valid]
    values = values[keep]

    if len(values) == 0:
        axis_off(ax)
        ax.text(
            0.5,
            0.5,
            "No eligible pathway-specific values",
            ha="center",
            va="center",
            fontsize=5.7,
        )
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
        fontsize=4.6,
    )
    ax.set_xlabel(xlabel, fontsize=5.7)
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
        subset["feature_id"].astype(str)
        .map(labels)
        .fillna(subset["feature_id"].astype(str))
    )
    subset["_subtype"] = (
        subset[subtype_column].fillna("unresolved").astype(str)
    )
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
    frame = (
        pd.concat(collector, ignore_index=True, sort=False)
        if collector
        else pd.DataFrame(
            columns=["figure", "panel", "source_role", "source_note"]
        )
    )
    path = (
        tabledir
        / f"UTI_HostOmics_U27B2E1_Figure_{figure_number}_source_values.tsv"
    )
    frame.to_csv(path, sep="\t", index=False)
    return path


def save_figure(
    fig: plt.Figure,
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    paths: List[Path] = []
    stem = f"UTI_HostOmics_U27B2E1_Figure_{figure_number}"
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
            / f"UTI_HostOmics_U27B2E1_Figure_{figure_number}"
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

    width = columns * cell_width + (columns + 1) * padding
    height = sum(row_heights) + (rows + 1) * padding
    canvas = Image.new("RGB", (width, height), "white")

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


def axis_feature_sets(
    library: pd.DataFrame,
) -> Dict[str, List[str]]:
    return {
        "endocrine": feature_ids_for_axis(
            library,
            ["steroid cholesterol endocrine"],
        ),
        "lipid": feature_ids_for_axis(
            library,
            ["lipid metabolism"],
        ),
        "adipokine_insulin": feature_ids_for_axis(
            library,
            ["adipokine signaling", "insulin irs signaling"],
        ),
        "carbon": feature_ids_for_axis(
            library,
            ["carbohydrate inflammatory carbon"],
        ),
        "amino": feature_ids_for_axis(
            library,
            ["amino acid metabolism"],
        ),
        "nucleotide_nitrogen": feature_ids_for_axis(
            library,
            ["nucleotide and nitrogen"],
        ),
        "complement": feature_ids_for_axis(
            library,
            ["complement architecture"],
        ),
    }


def build_figure_5(
    base,
    store,
    library: pd.DataFrame,
    full_matrix: pd.DataFrame,
    outdir: Path,
    tabledir: Path,
):
    source_rows: List[pd.DataFrame] = []
    labels = label_lookup(library)
    sets = axis_feature_sets(library)

    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 10.2))
    grid = fig.add_gridspec(
        3,
        3,
        left=0.12,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.72,
        wspace=0.72,
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
    broad = store.table("Figure_5C", "broad_effect_reliability")
    synthesis = store.table("Figure_5D", "module_cellular_synthesis")
    domains = store.table("Figure_3D", "decoupling_domains")
    core = store.table("Figure_5D", "refined_core")
    preterm = store.table("Figure_5B", "preterm_collapsed")

    endocrine_lipid = sets["endocrine"] + sets["lipid"]

    independent_ids = prioritized_features(
        library,
        [value for value in endocrine_lipid if value in available_ids(primary)],
        [
            "core steroidogenesis",
            "androgen and testosterone",
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
            "fatty acid synthesis",
        ],
        12,
    )

    # A
    panel_label(a, "A")
    a_matrix = independent_matrix(primary, independent_ids, labels)
    safe_heatmap(
        a,
        a_matrix,
        "Independent steroid, cholesterol and lipid effects",
        "Independent dataset",
        "Endocrine/lipid module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        filter_features(primary, independent_ids),
        5,
        "A",
        "primary_independent_effects",
    )

    # B
    panel_label(b, "B")
    c1_ids = prioritized_features(
        library,
        [value for value in endocrine_lipid if value in available_ids(full_matrix)],
        [
            "core steroidogenesis",
            "androgen and testosterone",
            "estrogen biosynthesis",
            "cholesterol biosynthesis",
            "androgen receptor",
            "estrogen receptor",
            "glucocorticoid receptor",
            "lipid droplet",
        ],
        9,
    )
    b_matrix = full_prefix_matrix(
        full_matrix,
        c1_ids,
        labels,
        "C1_",
    )
    safe_heatmap(
        b,
        b_matrix,
        "Preterm-versus-term endocrine effects",
        "Tissue",
        "Endocrine/lipid module",
    )
    export_rows(
        source_rows,
        b_matrix.reset_index(),
        5,
        "B",
        "full_GSE280297_C1_matrix",
    )

    # C
    panel_label(c, "C")
    domain_values = domains.copy()
    domain_values["_value"] = numeric(domain_values["median_effect"])
    horizontal_lollipop(
        c,
        domain_values["domain"],
        domain_values["_value"],
        "Steroid synthesis-response decoupling",
        "Median preterm-versus-term effect",
        21,
    )
    export_rows(
        source_rows,
        domain_values,
        5,
        "C",
        "decoupling_domains",
    )

    # D
    panel_label(d, "D")
    common_ids = [
        value
        for value in endocrine_lipid
        if value in available_ids(primary)
        and value in available_ids(preterm)
    ]
    common_ids = prioritized_features(
        library,
        common_ids,
        [
            "core steroidogenesis",
            "androgen and testosterone",
            "estrogen biosynthesis",
            "cholesterol biosynthesis",
            "androgen receptor",
            "estrogen receptor",
            "lipid droplet",
            "fatty acid synthesis",
        ],
        10,
    )
    infection = (
        filter_features(primary, common_ids)
        .groupby("feature_id")["effect_value"]
        .mean()
    )
    pregnancy = (
        filter_features(preterm, common_ids)
        .groupby("feature_id")["effect_value"]
        .mean()
    )
    scatter = pd.DataFrame(
        {
            "infection": infection,
            "preterm": pregnancy,
        }
    ).dropna()
    d.scatter(scatter["infection"], scatter["preterm"], s=22)
    add_zero(d, True)
    add_zero(d, False)
    for feature, row in scatter.iterrows():
        d.annotate(
            compact(labels.get(str(feature), feature), 13),
            (row["infection"], row["preterm"]),
            xytext=(2, 2),
            textcoords="offset points",
            fontsize=4.1,
        )
    d.set_xlabel("Median independent infection effect", fontsize=5.6)
    d.set_ylabel("Collapsed preterm-versus-term effect", fontsize=5.6)
    panel_title(d, "Infection-pregnancy endocrine branching")
    finish_axis(d)
    export_rows(
        source_rows,
        scatter.reset_index(),
        5,
        "D",
        "derived_locked_effect_comparison",
        "Derived from locked primary and preterm effect tables.",
    )

    # E
    panel_label(e, "E")
    broad_ids = prioritized_features(
        library,
        [value for value in endocrine_lipid if value in available_ids(broad)],
        [
            "androgen receptor",
            "estrogen receptor",
            "glucocorticoid receptor",
            "cholesterol",
            "lipid droplet",
            "fatty acid synthesis",
            "ferroptosis",
        ],
        8,
    )
    e_matrix = broad_matrix(broad, broad_ids, labels)
    safe_heatmap(
        e,
        e_matrix,
        "Broad-cell endocrine and lipid localization",
        "Broad immune population",
        "Endocrine/lipid module",
    )
    export_rows(
        source_rows,
        filter_features(broad, broad_ids),
        5,
        "E",
        "broad_effect_reliability",
    )

    # F
    panel_label(f, "F")
    lipid_ids = prioritized_features(
        library,
        [value for value in sets["lipid"] if value in available_ids(full_matrix)],
        [
            "lipid droplet",
            "ppar",
            "srebp",
            "lxr",
            "ferroptosis",
            "lipid peroxidation",
            "fatty acid synthesis",
            "beta oxidation",
        ],
        8,
    )
    f_matrix = full_context_matrix(
        full_matrix,
        lipid_ids,
        labels,
    )
    safe_heatmap(
        f,
        f_matrix,
        "Lipid-regulatory and lipid-stress programs across contexts",
        "Contrast and tissue",
        "Lipid module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        f_matrix.reset_index(),
        5,
        "F",
        "full_GSE280297_C1_C3_matrix",
    )

    # G
    panel_label(g, "G")
    support_ids = [
        value
        for value in endocrine_lipid
        if value in available_ids(synthesis)
    ]
    support = subtype_support(
        synthesis,
        support_ids,
        labels,
    ).sort_values("_score").tail(8)
    horizontal_lollipop(
        g,
        [
            f"{compact(row['_label'], 12)} | "
            f"{compact(row['_subtype'], 12)}"
            for _, row in support.iterrows()
        ],
        support["_score"],
        "Endocrine/lipid subtype support",
        "Composite support score",
        23,
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
    base,
    store,
    library: pd.DataFrame,
    full_matrix: pd.DataFrame,
    outdir: Path,
    tabledir: Path,
):
    source_rows: List[pd.DataFrame] = []
    labels = label_lookup(library)
    sets = axis_feature_sets(library)

    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 11.3))
    grid = fig.add_gridspec(
        4,
        2,
        left=0.12,
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

    signaling = sets["adipokine_insulin"] + sets["carbon"]

    # A
    panel_label(a, "A")
    a_ids = prioritized_features(
        library,
        [value for value in signaling if value in available_ids(primary)],
        [
            "leptin",
            "resistin",
            "insulin receptor",
            "irs",
            "pi3k",
            "glycolysis",
            "lactate",
            "glycogen",
            "pentose phosphate",
        ],
        11,
    )
    a_matrix = independent_matrix(primary, a_ids, labels)
    safe_heatmap(
        a,
        a_matrix,
        "Independent adipokine, insulin and carbon effects",
        "Independent dataset",
        "Immunometabolic module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        filter_features(primary, a_ids),
        6,
        "A",
        "primary_independent_effects",
    )

    # B
    panel_label(b, "B")
    b_ids = prioritized_features(
        library,
        [
            value
            for value in sets["adipokine_insulin"]
            if value in available_ids(full_matrix)
        ],
        ["leptin", "resistin", "insulin receptor", "irs", "pi3k"],
        7,
    )
    b_matrix = full_prefix_matrix(
        full_matrix,
        b_ids,
        labels,
        "C1_",
    )
    safe_heatmap(
        b,
        b_matrix,
        "Pregnancy adipokine and insulin effects",
        "Tissue",
        "Signaling module",
    )
    export_rows(
        source_rows,
        b_matrix.reset_index(),
        6,
        "B",
        "full_GSE280297_C1_matrix",
    )

    # C
    panel_label(c, "C")
    c_ids = prioritized_features(
        library,
        [value for value in signaling if value in available_ids(broad)],
        [
            "leptin",
            "resistin",
            "insulin receptor",
            "irs",
            "pi3k",
            "glycolysis",
            "glycogen",
            "lactate",
        ],
        9,
    )
    c_matrix = broad_matrix(broad, c_ids, labels)
    safe_heatmap(
        c,
        c_matrix,
        "Broad-cell immunometabolic localization",
        "Broad immune population",
        "Signaling/carbon module",
    )
    export_rows(
        source_rows,
        filter_features(broad, c_ids),
        6,
        "C",
        "broad_effect_reliability",
    )

    # D
    panel_label(d, "D")
    d_ids = [
        value
        for value in signaling
        if value in available_ids(synthesis)
    ]
    support = subtype_support(
        synthesis,
        d_ids,
        labels,
    ).sort_values("_score").tail(9)
    horizontal_lollipop(
        d,
        [
            f"{compact(row['_label'], 12)} | "
            f"{compact(row['_subtype'], 12)}"
            for _, row in support.iterrows()
        ],
        support["_score"],
        "Immunometabolic subtype support",
        "Composite support score",
        23,
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
        "Evidence-weighted coupling; not a direct causal sequence.",
        ha="center",
        fontsize=4.7,
    )
    e.set_xlim(0, 1)
    e.set_ylim(0, 1)

    # F
    panel_label(f, "F")
    f_ids = prioritized_features(
        library,
        [value for value in sets["carbon"] if value in available_ids(full_matrix)],
        [
            "glycolysis",
            "lactate",
            "hif1a",
            "glycogen",
            "pentose phosphate",
            "pyruvate",
        ],
        7,
    )
    f_matrix = full_context_matrix(full_matrix, f_ids, labels)
    safe_heatmap(
        f,
        f_matrix,
        "Inflammatory carbon-use programs across contexts",
        "Contrast and tissue",
        "Carbon-metabolism module",
    )
    export_rows(
        source_rows,
        f_matrix.reset_index(),
        6,
        "F",
        "full_GSE280297_C1_C3_matrix",
    )

    # G
    panel_label(g, "G")
    amino_nitrogen = sets["amino"] + sets["nucleotide_nitrogen"]
    g_ids = prioritized_features(
        library,
        [
            value
            for value in amino_nitrogen
            if value in available_ids(full_matrix)
        ],
        [
            "amino-acid transport",
            "arginine",
            "nitric oxide",
            "urea",
            "glutamine",
            "tryptophan",
        ],
        7,
    )
    g_matrix = full_context_matrix(full_matrix, g_ids, labels)
    safe_heatmap(
        g,
        g_matrix,
        "Amino-acid transport and arginine-NO-urea",
        "Contrast and tissue",
        "Amino-acid/nitrogen module",
    )
    export_rows(
        source_rows,
        g_matrix.reset_index(),
        6,
        "G",
        "full_GSE280297_C1_C3_matrix",
    )

    # H
    panel_label(h, "H")
    h_ids = prioritized_features(
        library,
        [
            value
            for value in sets["nucleotide_nitrogen"]
            if value in available_ids(full_matrix)
        ],
        [
            "purine",
            "pyrimidine",
            "nad",
            "nrf2",
            "redox",
            "oxidative",
        ],
        7,
    )
    h_matrix = full_context_matrix(full_matrix, h_ids, labels)
    safe_heatmap(
        h,
        h_matrix,
        "Purine, NAD and NRF2-redox remodeling",
        "Contrast and tissue",
        "Nucleotide/redox module",
    )
    export_rows(
        source_rows,
        h_matrix.reset_index(),
        6,
        "H",
        "full_GSE280297_C1_C3_matrix",
    )

    paths = save_figure(fig, outdir, 6)
    save_source_rows(source_rows, tabledir, 6)
    return fig, paths, axes


def build_figure_7(
    base,
    store,
    library: pd.DataFrame,
    full_matrix: pd.DataFrame,
    outdir: Path,
    tabledir: Path,
):
    source_rows: List[pd.DataFrame] = []
    labels = label_lookup(library)
    complement_ids = axis_feature_sets(library)["complement"]

    fig = plt.figure(figsize=(FIGURE_WIDTH_IN, 10.2))
    grid = fig.add_gridspec(
        3,
        3,
        left=0.12,
        right=0.97,
        bottom=0.07,
        top=0.96,
        hspace=0.73,
        wspace=0.72,
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

    # A
    panel_label(a, "A")
    a_ids = prioritized_features(
        library,
        [value for value in complement_ids if value in available_ids(primary)],
        [
            "classical",
            "lectin",
            "alternative",
            "c3 convertase",
            "c3a and c5a",
            "opsonophagocytosis",
            "terminal mac",
            "regulators",
            "coagulation",
        ],
        9,
    )
    a_matrix = independent_matrix(primary, a_ids, labels)
    safe_heatmap(
        a,
        a_matrix,
        "Independent complement effects with eligible evidence",
        "Independent dataset",
        "Complement module",
        horizontal_colorbar=True,
    )
    export_rows(
        source_rows,
        filter_features(primary, a_ids),
        7,
        "A",
        "primary_independent_effects",
    )

    # B
    panel_label(b, "B")
    b_ids = prioritized_features(
        library,
        [value for value in complement_ids if value in available_ids(full_matrix)],
        [
            "classical",
            "lectin",
            "alternative",
            "c3 convertase",
            "c3a and c5a",
            "opsonophagocytosis",
            "terminal mac",
            "regulators",
            "coagulation",
        ],
        9,
    )
    b_matrix = full_prefix_matrix(full_matrix, b_ids, labels, "C1_")
    safe_heatmap(
        b,
        b_matrix,
        "Preterm-versus-term complement branches",
        "Tissue",
        "Complement module",
    )
    export_rows(
        source_rows,
        b_matrix.reset_index(),
        7,
        "B",
        "full_GSE280297_C1_matrix",
    )

    # C
    panel_label(c, "C")
    c_ids = prioritized_features(
        library,
        [value for value in complement_ids if value in available_ids(broad)],
        [
            "classical",
            "alternative",
            "c3 convertase",
            "c3a and c5a",
            "opsonophagocytosis",
            "regulators",
            "coagulation",
        ],
        8,
    )
    c_matrix = broad_matrix(broad, c_ids, labels)
    safe_heatmap(
        c,
        c_matrix,
        "Broad-cell complement localization",
        "Broad immune population",
        "Complement module",
    )
    export_rows(
        source_rows,
        filter_features(broad, c_ids),
        7,
        "C",
        "broad_effect_reliability",
    )

    # D
    panel_label(d, "D")
    d_ids = [
        value
        for value in complement_ids
        if value in available_ids(synthesis)
    ]
    support = subtype_support(
        synthesis,
        d_ids,
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
        "Complement subtype support",
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
        "Regulatory and coagulation-crosstalk modules act across stages.",
        ha="center",
        fontsize=4.6,
    )
    e.set_xlim(0, 1)
    e.set_ylim(0, 1)

    # F
    panel_label(f, "F")
    common_ids = [
        value
        for value in complement_ids
        if value in available_ids(primary)
        and value in available_ids(preterm)
    ]
    infection = (
        filter_features(primary, common_ids)
        .groupby("feature_id")["effect_value"]
        .mean()
    )
    pregnancy = (
        filter_features(preterm, common_ids)
        .groupby("feature_id")["effect_value"]
        .mean()
    )
    comparison = pd.DataFrame(
        {
            "infection": infection,
            "preterm": pregnancy,
        }
    ).dropna()
    f.scatter(comparison["infection"], comparison["preterm"], s=24)
    add_zero(f, True)
    add_zero(f, False)
    for feature, row in comparison.iterrows():
        f.annotate(
            compact(labels.get(str(feature), feature), 14),
            (row["infection"], row["preterm"]),
            xytext=(2, 2),
            textcoords="offset points",
            fontsize=4.2,
        )
    f.set_xlabel("Median independent infection effect", fontsize=5.7)
    f.set_ylabel("Collapsed preterm-versus-term effect", fontsize=5.7)
    panel_title(f, "Complement-stage infection-pregnancy comparison")
    finish_axis(f)
    export_rows(
        source_rows,
        comparison.reset_index(),
        7,
        "F",
        "derived_locked_effect_comparison",
    )

    # G
    panel_label(g, "G")
    coverage_rows = []
    for feature in complement_ids:
        rows = broad[
            broad["feature_id"].astype(str) == str(feature)
        ]
        coverage_rows.append(
            {
                "feature_id": feature,
                "display_label": labels.get(feature, feature),
                "broad_populations_with_values": (
                    int(rows["population"].nunique())
                    if "population" in rows.columns
                    else 0
                ),
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    coverage = coverage[
        coverage["broad_populations_with_values"] > 0
    ].sort_values("broad_populations_with_values")
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
    )

    paths = save_figure(fig, outdir, 7)
    save_source_rows(source_rows, tabledir, 7)
    return fig, paths, axes


def build_figure_8(
    base,
    store,
    library: pd.DataFrame,
    full_matrix: pd.DataFrame,
    outdir: Path,
    tabledir: Path,
):
    # Retain the validated U27B2D scientific content for A-E, but rebuild F.
    # Temporarily replace the base exporters so this phase writes only the
    # U27B2E1 source-value table and does not leave duplicate U27B2D figure
    # exports inside the reconstruction directory.
    original_save_figure = base.save_figure
    original_save_source_rows = base.save_source_rows
    base.save_figure = lambda fig, outdir, figure_number: []
    base.save_source_rows = save_source_rows
    try:
        fig, _, axes = base.build_figure_8(
            store,
            outdir,
            tabledir,
        )
    finally:
        base.save_figure = original_save_figure
        base.save_source_rows = original_save_source_rows

    a, b, c, d, e, f = axes

    # Clear and rebuild Panel F for readability.
    f.clear()
    axis_off(f)
    panel_label(f, "F")
    panel_title(f, "Evidence hierarchy and interpretation boundary")

    left_x = 0.04
    right_x = 0.53

    draw_box(
        f,
        (left_x, 0.69),
        0.39,
        0.18,
        "Robust recurrent core\nTwo-dataset concordance",
        fontsize=5.1,
    )
    draw_box(
        f,
        (left_x, 0.43),
        0.39,
        0.18,
        "Provisional core\nOne FDR dataset plus support",
        fontsize=5.1,
    )
    draw_box(
        f,
        (left_x, 0.17),
        0.39,
        0.18,
        "Contextual or divergent\nHypothesis-generating biology",
        fontsize=5.1,
    )
    arrow(f, (0.235, 0.69), (0.235, 0.61))
    arrow(f, (0.235, 0.43), (0.235, 0.35))

    boundary_lines = [
        "No broad pregnancy FDR support",
        "Cellular localization is descriptive at n=2 vs n=2",
        "Metabolic modules infer transcriptional activity, not flux",
        "Cross-species synthesis uses concordance, not pooled expression",
        "Complement claims remain provisional where sample support is limited",
    ]
    f.text(
        right_x,
        0.88,
        "Interpretation boundary",
        fontsize=6.0,
        fontweight="bold",
        ha="left",
    )
    y = 0.77
    for line in boundary_lines:
        f.text(
            right_x,
            y,
            f"• {line}",
            fontsize=4.8,
            ha="left",
            va="top",
            wrap=True,
        )
        y -= 0.13

    f.text(
        0.5,
        0.04,
        "Final synthesis separates recurrent evidence from provisional and contextual biology.",
        ha="center",
        fontsize=4.8,
    )
    f.set_xlim(0, 1)
    f.set_ylim(0, 1)

    # Replace exports generated internally by the base builder.
    paths = save_figure(fig, outdir, 8)
    return fig, paths, axes


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
        tabledir / "UTI_HostOmics_U27B2E1_export_audit.tsv",
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
    base = load_module(
        project / "10_scripts" / BASE_SCRIPT,
        "u27b2d_base",
    )

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
    full_matrix_path = project / FULL_EFFECT_MATRIX_RELATIVE

    if not registry_path.exists():
        raise FileNotFoundError(
            f"Frozen source registry not found: {registry_path}"
        )
    if not panel_map_path.exists():
        raise FileNotFoundError(
            f"Frozen panel map not found: {panel_map_path}"
        )
    if not full_matrix_path.exists():
        raise FileNotFoundError(
            f"Corrected full effect matrix not found: {full_matrix_path}"
        )

    registry = pd.read_csv(registry_path, sep="\t", low_memory=False)
    panel_map = pd.read_csv(panel_map_path, sep="\t", low_memory=False)
    full_matrix = pd.read_csv(
        full_matrix_path,
        sep="\t",
        low_memory=False,
    )

    store = base.SourceStore(registry)
    module_library = normalize_library(
        store.table("Figure_1D", "module_library")
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

    figure_paths: List[Path] = []
    crop_paths: List[Path] = []

    builders = [
        (5, build_figure_5),
        (6, build_figure_6),
        (7, build_figure_7),
        (8, build_figure_8),
    ]

    for figure_number, builder in builders:
        log(f"Reconstructing Final Figure {figure_number}.")
        fig, paths, axes = builder(
            base,
            store,
            module_library,
            full_matrix,
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
        / "UTI_HostOmics_U27B2E1_full_figure_contact_sheet.png"
    )
    panel_contact = (
        outfig
        / "UTI_HostOmics_U27B2E1_panel_contact_sheet.png"
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

    audit = export_audit(figure_paths, outtables)

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
        / "UTI_HostOmics_U27B2E1_Figures_5_to_8_build_manifest.tsv",
        sep="\t",
        index=False,
    )

    pathway_manifest = module_library[
        [
            "feature_id",
            "display_label",
            "axis",
        ]
    ].copy()
    pathway_manifest.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B2E1_full_module_dictionary_used.tsv",
        sep="\t",
        index=False,
    )

    no_blank_panel_markers = True
    source_value_files = []
    for figure_number in (5, 6, 7, 8):
        path = (
            outtables
            / f"UTI_HostOmics_U27B2E1_Figure_{figure_number}_source_values.tsv"
        )
        if path.exists():
            source_value_files.append(path)

    expected_panels = sum(EXPECTED_PANEL_COUNTS.values())
    panels_present = build_manifest["panel_key"].nunique()
    exports_present = int(audit["exists"].sum())
    exports_nonempty = bool((audit["size_bytes"] > 0).all())
    contact_sheets_present = (
        full_contact.exists()
        and panel_contact.exists()
    )
    all_paths_exist = bool(
        build_manifest["locked_path"]
        .dropna()
        .astype(str)
        .map(lambda value: Path(value).exists())
        .all()
    )

    if (
        panels_present == expected_panels
        and len(crop_paths) == expected_panels
        and exports_present == 12
        and exports_nonempty
        and contact_sheets_present
        and all_paths_exist
        and len(source_value_files) == 4
        and module_library["feature_id"].nunique() >= 78
        and full_matrix["feature_id"].nunique() >= 81
    ):
        decision = (
            "READY_FOR_U27B2E2_FINAL_FIGURES_5_TO_8_VISUAL_AUDIT"
        )
    else:
        decision = (
            "TARGETED_U27B2E1_PATHWAY_RECONSTRUCTION_REPAIR_REQUIRED"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B2E1",
                "decision": decision,
                "figures_reconstructed": len(png_paths),
                "panels_expected": expected_panels,
                "panels_in_manifest": panels_present,
                "panel_crops_present": len(crop_paths),
                "exports_present": exports_present,
                "full_module_dictionary_features": int(
                    module_library["feature_id"].nunique()
                ),
                "full_GSE280297_effect_features": int(
                    full_matrix["feature_id"].nunique()
                ),
                "unrelated_fallback_modules_permitted": False,
                "statistical_effects_recalculated": False,
                "source_locks_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B2E2 manual visual and pathway-content audit"
                    if decision.startswith("READY_FOR_U27B2E2")
                    else "Repair incomplete exports or missing source coverage"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B2E1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B2E1_pathway_reconstruction_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2E1 - Pathway-specific Figures 5-8 reconstruction\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Figures reconstructed: **4/4**.\n")
        handle.write(
            f"- Frozen panels represented: "
            f"**{panels_present}/{expected_panels}**.\n"
        )
        handle.write(
            f"- Panel crops: **{len(crop_paths)}/{expected_panels}**.\n"
        )
        handle.write(
            f"- PNG/SVG/PDF exports: **{exports_present}/12**.\n"
        )
        handle.write(
            f"- Full module dictionary: "
            f"**{module_library['feature_id'].nunique()} modules**.\n"
        )
        handle.write(
            f"- Full GSE280297 matrix: "
            f"**{full_matrix['feature_id'].nunique()} modules**.\n\n"
        )

        handle.write("## Scientific corrections\n\n")
        handle.write(
            "- Figure 5 uses only steroid/cholesterol/endocrine and lipid-axis "
            "modules.\n"
            "- Figure 6 uses explicit adipokine, insulin/IRS, carbon, "
            "amino-acid, nucleotide and redox axes.\n"
            "- Figure 7 uses only complement-architecture modules.\n"
            "- Figure 8 retains the integrated core and uses a readable "
            "evidence-boundary panel.\n"
            "- No pathway panel is completed with unrelated fallback modules.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "Previously calculated effects were reformatted and subset by the "
            "full pathway dictionary. Statistical effects were not "
            "recalculated, and frozen source locks were not modified.\n"
        )

    (
        outresults
        / "UTI_HostOmics_U27B2E1_run_manifest.json"
    ).write_text(
        json.dumps(
            {
                "version": VERSION,
                "decision": decision,
                "figures_reconstructed": len(png_paths),
                "panels": panels_present,
                "panel_crops": len(crop_paths),
                "exports": exports_present,
                "module_dictionary_features": int(
                    module_library["feature_id"].nunique()
                ),
                "full_effect_features": int(
                    full_matrix["feature_id"].nunique()
                ),
                "unrelated_fallback_modules_permitted": False,
                "statistical_effects_recalculated": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log(f"Figures reconstructed: {len(png_paths)}/4")
    log(f"Panels represented: {panels_present}/{expected_panels}")
    log(f"Panel crops: {len(crop_paths)}/{expected_panels}")
    log(f"Exports present: {exports_present}/12")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2E1] ERROR: {exc}", file=sys.stderr)
        raise
