#!/usr/bin/env python3
"""
Phase U27B2E2A
Final layout and annotation repair for manuscript-facing Figures 5-8.

This phase starts from the successful U27B2E1 v1.2 pathway-specific
reconstruction. It preserves all numerical values, pathway membership,
displayed modules, source locks and biological interpretations.

Repairs
-------
- Figure 5D and Figure 7F:
  replace crowded direct point labels with numbered annotations and a compact
  inset key. All points remain visible; up to six biologically most separated
  points are numbered.
- Figures 5G, 6D and 7D:
  restrict refined-subtype displays to the six strongest support entries and
  shorten module/subtype labels.
- Shorten or wrap clipped panel titles.
- Increase local label margins for dense heatmaps and subtype panels.
- Figure 8F:
  rebuild the evidence/interpretation boundary with larger text and four
  concise limitations.

No statistical effects are recalculated.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
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
import numpy as np
import pandas as pd

try:
    from PIL import Image
except ImportError:
    Image = None


VERSION = "U27B2E2A_v1.0_2026-07-16"
TAG = "phaseU27B2E2A_final_figures_5_to_8_layout_annotation_repair"
FREEZE_TAG = "phaseU27B2C2E_final_figures_1_to_4_freeze"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"
FULL_EFFECT_MATRIX_RELATIVE = (
    "06_tables/"
    "phaseU27B2C2A_GSE280297_full_effect_source_repair/"
    "UTI_HostOmics_U27B2C2A_GSE280297_full_tissue_effect_matrix.tsv"
)
DPI = 300
EXPECTED_PANEL_COUNTS = {5: 7, 6: 8, 7: 7, 8: 6}


def log(message: str) -> None:
    print(f"[U27B2E2A] {message}", flush=True)


def load_module(path: Path, name: str):
    if not path.exists():
        raise FileNotFoundError(f"Required script not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def find_v12_script(project: Path) -> Path:
    candidates = [
        project
        / "10_scripts"
        / "phaseU27B2E1_reconstruct_figures_5_to_8_pathway_specific_v12.py",
        project
        / "10_scripts"
        / "phaseU27B2E1_reconstruct_figures_5_to_8_pathway_specific.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate the successful U27B2E1 v1.2 reconstruction script. "
        "Expected one of: " + "; ".join(str(path) for path in candidates)
    )


def compact_text(value: object, width: int = 24) -> str:
    text = str(value).replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return "\n".join(
        textwrap.wrap(
            text,
            width=width,
            break_long_words=False,
        )
    )


def concise_subtype(value: object) -> str:
    text = str(value)
    replacements = [
        (r"conventional activated T", "activated T"),
        (r"regulatory/type 2-like T", "regulatory/type-2 T"),
        (r"regulatory-like T", "regulatory T"),
        (r"inflammatory monocyte", "inflam. monocyte"),
        (r"reparative macrophage", "reparative macrophage"),
        (r"activated dendritic", "activated DC"),
        (r"cDC1-like", "cDC1-like"),
        (r"cDC2-like", "cDC2-like"),
        (r"cytotoxic NK", "cytotoxic NK"),
        (r"cycling immune", "cycling immune"),
        (r"macrophage/monocyte", "mac/mono"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def shift_axis_right(
    ax: plt.Axes,
    delta: float,
    shrink: Optional[float] = None,
) -> None:
    position = ax.get_position()
    width_reduction = delta if shrink is None else shrink
    ax.set_position(
        [
            position.x0 + delta,
            position.y0,
            max(position.width - width_reduction, 0.05),
            position.height,
        ]
    )


def shorten_title(
    ax: plt.Axes,
    text: str,
    fontsize: float = 7.0,
) -> None:
    ax.set_title(
        text,
        loc="left",
        x=0.02,
        fontsize=fontsize,
        fontweight="bold",
        pad=4,
        linespacing=0.94,
    )


def top_six_subtype_support(original_function):
    def wrapped(synthesis, feature_ids, labels):
        frame = original_function(synthesis, feature_ids, labels)
        if frame is None or frame.empty:
            return frame
        if "_score" not in frame.columns:
            return frame
        return (
            frame.sort_values("_score", ascending=False)
            .head(6)
            .sort_values("_score", ascending=True)
            .copy()
        )
    return wrapped


def convert_scatter_labels_to_numbered_key(
    ax: plt.Axes,
    max_labels: int = 6,
    key_location: Tuple[float, float] = (0.02, 0.98),
) -> None:
    """
    Replace data-coordinate annotation labels with numbers and a compact key.
    The points themselves and all numeric values remain unchanged.
    """
    candidates = []
    preserved = []

    for text in list(ax.texts):
        transform = text.get_transform()
        if transform == ax.transData:
            x, y = text.get_position()
            label = text.get_text().replace("\n", " ").strip()
            if label:
                candidates.append((text, float(x), float(y), label))
            else:
                preserved.append(text)

    if not candidates:
        return

    # Prioritize points furthest from the center of the displayed data cloud.
    xs = np.array([item[1] for item in candidates], dtype=float)
    ys = np.array([item[2] for item in candidates], dtype=float)
    x_scale = max(np.nanmax(xs) - np.nanmin(xs), 1e-9)
    y_scale = max(np.nanmax(ys) - np.nanmin(ys), 1e-9)
    x_center = float(np.nanmedian(xs))
    y_center = float(np.nanmedian(ys))
    distances = (
        ((xs - x_center) / x_scale) ** 2
        + ((ys - y_center) / y_scale) ** 2
    )

    order = np.argsort(distances)[::-1]
    selected_indices = set(order[: min(max_labels, len(order))])

    key_entries = []
    number = 1

    for index, (text, x, y, label) in enumerate(candidates):
        text.remove()
        if index in selected_indices:
            ax.annotate(
                str(number),
                (x, y),
                xytext=(3, 3),
                textcoords="offset points",
                fontsize=5.1,
                fontweight="bold",
            )
            key_entries.append(
                f"{number}. {re.sub(r'\\s+', ' ', label)}"
            )
            number += 1

    if key_entries:
        split_entries = []
        for entry in key_entries:
            split_entries.extend(
                textwrap.wrap(
                    entry,
                    width=28,
                    subsequent_indent="   ",
                    break_long_words=False,
                )
            )
        ax.text(
            key_location[0],
            key_location[1],
            "\n".join(split_entries),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=4.25,
            linespacing=0.96,
            bbox=dict(
                boxstyle="round,pad=0.25",
                facecolor="white",
                edgecolor="0.65",
                linewidth=0.5,
                alpha=0.90,
            ),
        )


def shorten_support_ticklabels(ax: plt.Axes) -> None:
    labels = []
    for tick in ax.get_yticklabels():
        text = tick.get_text().replace("\n", " ")
        if "|" in text:
            module, subtype = text.split("|", 1)
            module = compact_text(module.strip(), 16).replace("\n", " ")
            subtype = concise_subtype(subtype.strip())
            text = f"{module} | {subtype}"
        text = compact_text(text, 25)
        labels.append(text)
    if labels:
        ax.set_yticklabels(labels, fontsize=4.45)


def rebuild_figure8_panel_f(ax: plt.Axes) -> None:
    ax.clear()
    ax.set_axis_off()
    ax.text(
        -0.12,
        1.045,
        "F",
        transform=ax.transAxes,
        fontsize=9.2,
        fontweight="bold",
        ha="left",
        va="bottom",
        clip_on=False,
    )
    ax.set_title(
        "Evidence and interpretation boundary",
        loc="left",
        x=0.02,
        fontsize=7.1,
        fontweight="bold",
        pad=4,
    )

    box_specs = [
        (0.04, 0.70, "Robust core\nrecurrent concordance"),
        (0.04, 0.43, "Provisional core\nindependent support"),
        (0.04, 0.16, "Contextual biology\nhypothesis-generating"),
    ]
    for x, y, label in box_specs:
        box = plt.matplotlib.patches.FancyBboxPatch(
            (x, y),
            0.39,
            0.17,
            boxstyle="round,pad=0.018,rounding_size=0.02",
            linewidth=0.8,
            facecolor="white",
            edgecolor="black",
        )
        ax.add_patch(box)
        ax.text(
            x + 0.195,
            y + 0.085,
            label,
            ha="center",
            va="center",
            fontsize=5.0,
        )

    ax.annotate(
        "",
        xy=(0.235, 0.60),
        xytext=(0.235, 0.70),
        arrowprops=dict(arrowstyle="-|>", linewidth=0.8),
    )
    ax.annotate(
        "",
        xy=(0.235, 0.33),
        xytext=(0.235, 0.43),
        arrowprops=dict(arrowstyle="-|>", linewidth=0.8),
    )

    ax.text(
        0.52,
        0.87,
        "Interpretation limits",
        fontsize=6.0,
        fontweight="bold",
        ha="left",
    )
    limitations = [
        "Pregnancy findings lack broad FDR support.",
        "Cellular localization is descriptive at n=2 versus n=2.",
        "Metabolic modules infer transcriptional activity, not flux.",
        "Cross-species synthesis uses concordance; complement remains provisional.",
    ]
    y = 0.76
    for limitation in limitations:
        wrapped = textwrap.fill(
            limitation,
            width=42,
            subsequent_indent="  ",
            break_long_words=False,
        )
        ax.text(
            0.54,
            y,
            f"• {wrapped}",
            fontsize=4.9,
            ha="left",
            va="top",
            linespacing=1.0,
        )
        y -= 0.16

    ax.text(
        0.5,
        0.04,
        "The final model separates recurrent evidence from provisional and contextual biology.",
        ha="center",
        fontsize=4.8,
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def polish_figure_5(
    fig: plt.Figure,
    axes: Sequence[plt.Axes],
) -> None:
    a, b, c, d, e, f, g = axes

    shorten_title(b, "Preterm endocrine effects")
    shorten_title(e, "Broad-cell endocrine/lipid localization")
    shorten_title(g, "Endocrine/lipid subtype support")

    convert_scatter_labels_to_numbered_key(
        d,
        max_labels=6,
        key_location=(0.02, 0.98),
    )
    shorten_support_ticklabels(g)

    shift_axis_right(e, 0.016)
    shift_axis_right(g, 0.020)
    shift_axis_right(a, 0.010, 0.010)
    shift_axis_right(f, 0.010, 0.010)

    e.set_yticklabels(
        [tick.get_text() for tick in e.get_yticklabels()],
        fontsize=4.15,
    )
    f.set_yticklabels(
        [tick.get_text() for tick in f.get_yticklabels()],
        fontsize=4.05,
    )


def polish_figure_6(
    fig: plt.Figure,
    axes: Sequence[plt.Axes],
) -> None:
    a, b, c, d, e, f, g, h = axes

    shorten_title(d, "Immunometabolic subtype support")
    shorten_support_ticklabels(d)

    shift_axis_right(c, 0.014)
    shift_axis_right(d, 0.022)
    shift_axis_right(f, 0.012)
    shift_axis_right(g, 0.012)
    shift_axis_right(h, 0.012)

    for axis in (a, b, c, f, g, h):
        axis.set_yticklabels(
            [tick.get_text() for tick in axis.get_yticklabels()],
            fontsize=4.05,
        )


def polish_figure_7(
    fig: plt.Figure,
    axes: Sequence[plt.Axes],
) -> None:
    a, b, c, d, e, f, g = axes

    shorten_title(b, "Preterm complement branches")
    shorten_title(d, "Complement subtype support")
    shorten_title(f, "Complement infection-pregnancy comparison")

    shorten_support_ticklabels(d)
    convert_scatter_labels_to_numbered_key(
        f,
        max_labels=6,
        key_location=(0.02, 0.98),
    )

    shift_axis_right(c, 0.014)
    shift_axis_right(d, 0.022)
    shift_axis_right(g, 0.018)

    # Shorten the explanatory footer in the branch-topology panel.
    for text in e.texts:
        if "Regulatory" in text.get_text() or "coagulation" in text.get_text():
            text.set_text(
                "Regulatory and coagulation modules act across stages."
            )
            text.set_fontsize(4.5)


def polish_figure_8(
    fig: plt.Figure,
    axes: Sequence[plt.Axes],
) -> None:
    rebuild_figure8_panel_f(axes[5])


def save_figure(
    fig: plt.Figure,
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    paths: List[Path] = []
    stem = f"UTI_HostOmics_U27B2E2A_Figure_{figure_number}"
    for extension in ("png", "svg", "pdf"):
        path = outdir / f"{stem}.{extension}"
        kwargs = {"dpi": DPI} if extension == "png" else {}
        fig.savefig(path, facecolor="white", **kwargs)
        paths.append(path)
    return paths


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
        / f"UTI_HostOmics_U27B2E2A_Figure_{figure_number}_source_values.tsv"
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

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.canvas.get_width_height()
    image = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()))
    paths: List[Path] = []

    for index, axis in enumerate(axes):
        bbox = axis.get_tightbbox(renderer).expanded(1.09, 1.12)
        x0 = max(int(bbox.x0), 0)
        y0 = max(int(height - bbox.y1), 0)
        x1 = min(int(bbox.x1), width)
        y1 = min(int(height - bbox.y0), height)
        crop = image.crop((x0, y0, x1, y1))
        panel = chr(ord("A") + index)
        path = (
            outdir
            / f"UTI_HostOmics_U27B2E2A_Figure_{figure_number}"
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
        tabledir / "UTI_HostOmics_U27B2E2A_export_audit.tsv",
        sep="\t",
        index=False,
    )
    return frame


def call_builder(
    builder,
    base,
    store,
    module_library,
    full_matrix,
    outfig,
    outtables,
):
    parameters = list(inspect.signature(builder).parameters)
    if len(parameters) == 6:
        return builder(
            base,
            store,
            module_library,
            full_matrix,
            outfig,
            outtables,
        )
    if len(parameters) == 5:
        return builder(
            store,
            module_library,
            full_matrix,
            outfig,
            outtables,
        )
    raise RuntimeError(
        f"Unsupported builder signature for {builder.__name__}: "
        f"{inspect.signature(builder)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    v12_path = find_v12_script(project)
    v12 = load_module(v12_path, "u27b2e1_v12")

    # Resolve the U27B2D base module in the same way as the successful v1.2 run.
    base_script = project / "10_scripts" / "phaseU27B2D_build_final_figures_5_to_8.py"
    if hasattr(v12, "load_module"):
        base = v12.load_module(base_script, "u27b2d_base_for_polish")
    else:
        base = load_module(base_script, "u27b2d_base_for_polish")

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

    for path in (registry_path, panel_map_path, full_matrix_path):
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    registry = pd.read_csv(registry_path, sep="\t", low_memory=False)
    panel_map = pd.read_csv(panel_map_path, sep="\t", low_memory=False)
    full_matrix = pd.read_csv(
        full_matrix_path,
        sep="\t",
        low_memory=False,
    )

    store = base.SourceStore(registry)
    module_library = v12.normalize_library(
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

    # Restrict all refined-subtype panels to the six strongest entries.
    original_subtype_support = v12.subtype_support
    v12.subtype_support = top_six_subtype_support(
        original_subtype_support
    )

    # Suppress the internal v1.2 exports. This phase writes only U27B2E2A assets.
    original_save_figure = v12.save_figure
    original_save_source_rows = v12.save_source_rows
    v12.save_figure = lambda fig, outdir, figure_number: []
    v12.save_source_rows = save_source_rows

    figure_paths: List[Path] = []
    crop_paths: List[Path] = []

    builders = [
        (5, v12.build_figure_5, polish_figure_5),
        (6, v12.build_figure_6, polish_figure_6),
        (7, v12.build_figure_7, polish_figure_7),
        (8, v12.build_figure_8, polish_figure_8),
    ]

    try:
        for figure_number, builder, polisher in builders:
            log(f"Polishing Final Figure {figure_number}.")
            fig, _, axes = call_builder(
                builder,
                base,
                store,
                module_library,
                full_matrix,
                outfig,
                outtables,
            )
            polisher(fig, axes)
            figure_paths.extend(
                save_figure(fig, outfig, figure_number)
            )
            crop_paths.extend(
                panel_crops(
                    fig,
                    axes,
                    cropdir,
                    figure_number,
                )
            )
            plt.close(fig)
    finally:
        v12.subtype_support = original_subtype_support
        v12.save_figure = original_save_figure
        v12.save_source_rows = original_save_source_rows

    png_paths = [
        path
        for path in figure_paths
        if path.suffix.lower() == ".png"
    ]

    full_contact = (
        outfig
        / "UTI_HostOmics_U27B2E2A_full_figure_contact_sheet.png"
    )
    panel_contact = (
        outfig
        / "UTI_HostOmics_U27B2E2A_panel_contact_sheet.png"
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
        / "UTI_HostOmics_U27B2E2A_Figures_5_to_8_build_manifest.tsv",
        sep="\t",
        index=False,
    )

    polish_manifest = pd.DataFrame(
        [
            ("Figure_5B", "Shortened title"),
            ("Figure_5D", "Numbered six priority points with inset key"),
            ("Figure_5E", "Shortened title and increased left margin"),
            ("Figure_5G", "Top six subtype entries and shortened labels"),
            ("Figure_6D", "Top six subtype entries and shortened labels"),
            ("Figure_6F-H", "Increased label margins"),
            ("Figure_7B", "Shortened title"),
            ("Figure_7D", "Top six subtype entries and shortened labels"),
            ("Figure_7E", "Shortened explanatory footer"),
            ("Figure_7F", "Numbered six priority points with inset key"),
            ("Figure_8F", "Larger three-tier evidence layout and four concise limitations"),
        ],
        columns=["panel_key", "polish_action"],
    )
    polish_manifest.to_csv(
        outtables
        / "UTI_HostOmics_U27B2E2A_polish_manifest.tsv",
        sep="\t",
        index=False,
    )

    expected_panels = sum(EXPECTED_PANEL_COUNTS.values())
    observed_panels = build_manifest["panel_key"].nunique()
    expected_exports = 12
    observed_exports = int(audit["exists"].sum())
    exports_nonempty = bool((audit["size_bytes"] > 0).all())
    contact_sheets_present = (
        full_contact.exists()
        and panel_contact.exists()
    )
    source_paths_exist = bool(
        build_manifest["locked_path"]
        .dropna()
        .astype(str)
        .map(lambda value: Path(value).exists())
        .all()
    )

    if (
        observed_panels == expected_panels
        and len(crop_paths) == expected_panels
        and observed_exports == expected_exports
        and exports_nonempty
        and contact_sheets_present
        and source_paths_exist
    ):
        decision = (
            "READY_FOR_U27B2E2B_FINAL_FIGURES_5_TO_8_FREEZE_AUDIT"
        )
    else:
        decision = (
            "TARGETED_U27B2E2A_EXPORT_OR_LAYOUT_REPAIR_REQUIRED"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B2E2A",
                "decision": decision,
                "figures_polished": len(png_paths),
                "panels_expected": expected_panels,
                "panels_in_manifest": observed_panels,
                "panel_crops_present": len(crop_paths),
                "exports_expected": expected_exports,
                "exports_present": observed_exports,
                "nonempty_exports": exports_nonempty,
                "contact_sheets_present": contact_sheets_present,
                "locked_source_paths_exist": source_paths_exist,
                "statistical_effects_recalculated": False,
                "displayed_modules_changed": False,
                "pathway_membership_changed": False,
                "source_locks_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B2E2B final visual freeze audit"
                    if decision.startswith("READY_FOR_U27B2E2B")
                    else "Repair missing exports or residual layout defects"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B2E2A_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B2E2A_final_layout_annotation_repair_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2E2A - Final Figures 5-8 layout and annotation repair\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Figures polished: **4/4**.\n")
        handle.write(
            f"- Frozen panels represented: "
            f"**{observed_panels}/{expected_panels}**.\n"
        )
        handle.write(
            f"- PNG/SVG/PDF exports: "
            f"**{observed_exports}/{expected_exports}**.\n"
        )
        handle.write(
            f"- Panel crops: **{len(crop_paths)}/{expected_panels}**.\n\n"
        )

        handle.write("## Repair scope\n\n")
        handle.write(
            "- Crowded scatter annotations were converted to numbered keys.\n"
            "- Refined-subtype panels were reduced to the six strongest entries.\n"
            "- Dense labels and clipped titles received local margin and typography repair.\n"
            "- Figure 8F was rebuilt with larger text and four concise interpretation limits.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "No numerical values, pathway membership, displayed modules, "
            "source locks or biological interpretations were changed. "
            "Statistical effects were not recalculated.\n"
        )

    (
        outresults
        / "UTI_HostOmics_U27B2E2A_run_manifest.json"
    ).write_text(
        json.dumps(
            {
                "version": VERSION,
                "decision": decision,
                "figures_polished": len(png_paths),
                "panels": observed_panels,
                "panel_crops": len(crop_paths),
                "exports": observed_exports,
                "statistical_effects_recalculated": False,
                "displayed_modules_changed": False,
                "pathway_membership_changed": False,
                "source_locks_changed": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log(f"Figures polished: {len(png_paths)}/4")
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
        print(f"[U27B2E2A] ERROR: {exc}", file=sys.stderr)
        raise
