#!/usr/bin/env python3
"""
Phase U27B2E2D
Final scatter-annotation and title micro-repair for Figures 5-8.

The U27B2E2A contact-sheet audit showed that the intended numbered-key
conversion did not remove the original scatter labels in Figure 5D and
Figure 7F. The labels are Matplotlib Annotation objects rather than ordinary
Text objects, so the earlier transform-based detector did not select them.

This phase:
- rebuilds Figures 5-8 from the successful pathway-specific v1.2 sources;
- retains the U27B2E2A top-six subtype and margin repairs;
- removes non-empty Annotation objects from Figure 5D and Figure 7F;
- numbers six priority points and adds compact in-panel keys;
- shortens the remaining clipped titles;
- exports normalized PNG, SVG and PDF masters and contact sheets.

No numerical values, pathway membership, displayed modules, source locks,
biological interpretations or statistical results are changed.
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
from typing import List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.text import Annotation
import numpy as np
import pandas as pd

try:
    from PIL import Image
except ImportError:
    Image = None


VERSION = "U27B2E2D_v1.0_2026-07-16"
TAG = "phaseU27B2E2D_final_visibility_title_microrepair"
FREEZE_TAG = "phaseU27B2C2E_final_figures_1_to_4_freeze"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"
FULL_EFFECT_MATRIX_RELATIVE = (
    "06_tables/"
    "phaseU27B2C2A_GSE280297_full_effect_source_repair/"
    "UTI_HostOmics_U27B2C2A_GSE280297_full_tissue_effect_matrix.tsv"
)
EXPECTED_PANEL_COUNTS = {5: 7, 6: 8, 7: 7, 8: 6}
DPI = 300


def log(message: str) -> None:
    print(f"[U27B2E2D] {message}", flush=True)


def load_module(path: Path, name: str):
    if not path.exists():
        raise FileNotFoundError(f"Required script not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def find_script(project: Path, candidates: Sequence[str]) -> Path:
    for filename in candidates:
        path = project / "10_scripts" / filename
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not locate required script. Tried: "
        + "; ".join(str(project / "10_scripts" / value) for value in candidates)
    )


def compact(value: object, width: int = 22) -> str:
    text = re.sub(r"\s+", " ", str(value).replace("_", " ")).strip()
    return "\n".join(
        textwrap.wrap(
            text,
            width=width,
            break_long_words=False,
        )
    )


def save_figure(
    fig: plt.Figure,
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    paths: List[Path] = []
    stem = f"UTI_HostOmics_U27B2E2D_Figure_{figure_number}"
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
    frame = (
        pd.concat(collector, ignore_index=True, sort=False)
        if collector
        else pd.DataFrame(
            columns=["figure", "panel", "source_role", "source_note"]
        )
    )
    path = (
        tabledir
        / f"UTI_HostOmics_U27B2E2D_Figure_{figure_number}_source_values.tsv"
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
            / f"UTI_HostOmics_U27B2E2D_Figure_{figure_number}"
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
        tabledir / "UTI_HostOmics_U27B2E2D_export_audit.tsv",
        sep="\t",
        index=False,
    )
    return frame


def top_six_subtype_support(original_function):
    def wrapped(synthesis, feature_ids, labels):
        frame = original_function(synthesis, feature_ids, labels)
        if frame is None or frame.empty or "_score" not in frame.columns:
            return frame
        return (
            frame.sort_values("_score", ascending=False)
            .head(6)
            .sort_values("_score", ascending=True)
            .copy()
        )
    return wrapped


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


def annotation_candidates(ax: plt.Axes):
    candidates = []
    for artist in list(ax.texts):
        if not isinstance(artist, Annotation):
            continue
        label = re.sub(r"\s+", " ", artist.get_text()).strip()
        if not label:
            continue
        xy = getattr(artist, "xy", None)
        if xy is None or len(xy) != 2:
            continue
        try:
            x = float(xy[0])
            y = float(xy[1])
        except (TypeError, ValueError):
            continue
        if not np.isfinite(x) or not np.isfinite(y):
            continue
        candidates.append((artist, x, y, label))
    return candidates


def numbered_scatter_key(
    ax: plt.Axes,
    max_labels: int,
    key_anchor: Tuple[float, float],
    key_width: int = 27,
) -> int:
    """
    Remove all direct non-empty Annotation labels from the scatter panel,
    number the most separated points and add a compact key.
    """
    candidates = annotation_candidates(ax)
    if not candidates:
        return 0

    xs = np.array([item[1] for item in candidates], dtype=float)
    ys = np.array([item[2] for item in candidates], dtype=float)
    x_span = max(float(np.nanmax(xs) - np.nanmin(xs)), 1e-9)
    y_span = max(float(np.nanmax(ys) - np.nanmin(ys)), 1e-9)
    x_center = float(np.nanmedian(xs))
    y_center = float(np.nanmedian(ys))

    separation = (
        ((xs - x_center) / x_span) ** 2
        + ((ys - y_center) / y_span) ** 2
    )
    selected = list(
        np.argsort(separation)[::-1][: min(max_labels, len(candidates))]
    )
    selected_set = set(selected)

    entries = []
    number = 1

    for index, (artist, x, y, label) in enumerate(candidates):
        artist.remove()
        if index not in selected_set:
            continue

        ax.annotate(
            str(number),
            xy=(x, y),
            xytext=(3, 3),
            textcoords="offset points",
            fontsize=5.2,
            fontweight="bold",
            ha="left",
            va="bottom",
            bbox=dict(
                boxstyle="circle,pad=0.10",
                facecolor="white",
                edgecolor="none",
                alpha=0.95,
            ),
            zorder=20,
        )
        entries.append(f"{number}. {label}")
        number += 1

    key_lines = []
    for entry in entries:
        key_lines.extend(
            textwrap.wrap(
                entry,
                width=key_width,
                subsequent_indent="   ",
                break_long_words=False,
            )
        )

    ax.text(
        key_anchor[0],
        key_anchor[1],
        "\n".join(key_lines),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=4.15,
        linespacing=0.95,
        bbox=dict(
            boxstyle="round,pad=0.24",
            facecolor="white",
            edgecolor="0.60",
            linewidth=0.5,
            alpha=0.90,
        ),
        zorder=10,
    )
    return len(entries)


def polish_titles(figure_number: int, axes: Sequence[plt.Axes]) -> None:
    if figure_number == 5:
        axes[6].set_title(
            "Endocrine/lipid\nsubtype support",
            loc="left",
            x=0.02,
            fontsize=6.7,
            fontweight="bold",
            pad=4,
            linespacing=0.94,
        )
    elif figure_number == 7:
        axes[1].set_title(
            "Preterm complement effects",
            loc="left",
            fontsize=6.9,
            fontweight="bold",
            pad=4,
        )
        axes[4].set_title(
            "Complement topology",
            loc="left",
            fontsize=7.0,
            fontweight="bold",
            pad=4,
        )
        axes[5].set_title(
            "Complement infection-pregnancy comparison",
            loc="left",
            fontsize=6.7,
            fontweight="bold",
            pad=4,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    v12_path = find_script(
        project,
        [
            "phaseU27B2E1_reconstruct_figures_5_to_8_pathway_specific_v12.py",
            "phaseU27B2E1_reconstruct_figures_5_to_8_pathway_specific.py",
        ],
    )
    previous_path = find_script(
        project,
        [
            "phaseU27B2E2A_final_figures_5_to_8_layout_annotation_repair.py",
        ],
    )
    base_path = find_script(
        project,
        [
            "phaseU27B2D_build_final_figures_5_to_8.py",
        ],
    )

    v12 = load_module(v12_path, "u27b2e1_v12_for_e2c")
    previous = load_module(previous_path, "u27b2e2a_previous")
    base = load_module(base_path, "u27b2d_base_for_e2c")

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

    original_subtype_support = v12.subtype_support
    original_save_figure = v12.save_figure
    original_save_source_rows = v12.save_source_rows

    v12.subtype_support = top_six_subtype_support(
        original_subtype_support
    )
    v12.save_figure = lambda fig, outdir, figure_number: []
    v12.save_source_rows = save_source_rows

    builders = [
        (5, v12.build_figure_5, previous.polish_figure_5),
        (6, v12.build_figure_6, previous.polish_figure_6),
        (7, v12.build_figure_7, previous.polish_figure_7),
        (8, v12.build_figure_8, previous.polish_figure_8),
    ]

    figure_paths: List[Path] = []
    crop_paths: List[Path] = []
    annotation_audit = []

    try:
        for figure_number, builder, previous_polisher in builders:
            log(f"Rebuilding and micro-polishing Final Figure {figure_number}.")
            fig, _, axes = call_builder(
                builder,
                base,
                store,
                module_library,
                full_matrix,
                outfig,
                outtables,
            )

            previous_polisher(fig, axes)

            if figure_number == 5:
                numbered = numbered_scatter_key(
                    axes[3],
                    max_labels=6,
                    key_anchor=(0.51, 0.97),
                    key_width=23,
                )
                annotation_audit.append(
                    {
                        "panel_key": "Figure_5D",
                        "numbered_annotations": numbered,
                        "direct_nonempty_annotations_remaining": len(
                            annotation_candidates(axes[3])
                        ),
                    }
                )
            elif figure_number == 7:
                numbered = numbered_scatter_key(
                    axes[5],
                    max_labels=6,
                    key_anchor=(0.02, 0.97),
                    key_width=28,
                )
                annotation_audit.append(
                    {
                        "panel_key": "Figure_7F",
                        "numbered_annotations": numbered,
                        "direct_nonempty_annotations_remaining": len(
                            annotation_candidates(axes[5])
                        ),
                    }
                )

            polish_titles(figure_number, axes)

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
        / "UTI_HostOmics_U27B2E2D_full_figure_contact_sheet.png"
    )
    panel_contact = (
        outfig
        / "UTI_HostOmics_U27B2E2D_panel_contact_sheet.png"
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
        / "UTI_HostOmics_U27B2E2D_Figures_5_to_8_build_manifest.tsv",
        sep="\t",
        index=False,
    )

    annotation_audit_frame = pd.DataFrame(annotation_audit)
    annotation_audit_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B2E2D_scatter_annotation_audit.tsv",
        sep="\t",
        index=False,
    )

    polish_manifest = pd.DataFrame(
        [
            (
                "Figure_5D",
                "Removed direct Annotation labels; numbered six priority points and added compact key",
            ),
            (
                "Figure_5G",
                "Completed concise subtype-support title",
            ),
            (
                "Figure_7B",
                "Shortened title to Preterm complement effects",
            ),
            (
                "Figure_7E",
                "Shortened title to Complement topology",
            ),
            (
                "Figure_7F",
                "Removed direct Annotation labels; numbered six priority points and added compact key",
            ),
        ],
        columns=["panel_key", "repair_action"],
    )
    polish_manifest.to_csv(
        outtables
        / "UTI_HostOmics_U27B2E2D_polish_manifest.tsv",
        sep="\t",
        index=False,
    )

    expected_panels = sum(EXPECTED_PANEL_COUNTS.values())
    observed_panels = build_manifest["panel_key"].nunique()
    observed_exports = int(audit["exists"].sum())
    exports_nonempty = bool((audit["size_bytes"] > 0).all())
    contacts_present = full_contact.exists() and panel_contact.exists()
    source_paths_exist = bool(
        build_manifest["locked_path"]
        .dropna()
        .astype(str)
        .map(lambda value: Path(value).exists())
        .all()
    )
    annotation_pass = bool(
        len(annotation_audit_frame) == 2
        and (
            annotation_audit_frame["numbered_annotations"] == 6
        ).all()
        and (
            annotation_audit_frame[
                "direct_nonempty_annotations_remaining"
            ] == 6
        ).all()
    )

    # After replacement, the only remaining non-empty Annotation objects are
    # the six newly added numeric labels in each audited scatter panel.
    if (
        observed_panels == expected_panels
        and len(crop_paths) == expected_panels
        and observed_exports == 12
        and exports_nonempty
        and contacts_present
        and source_paths_exist
        and annotation_pass
    ):
        decision = (
            "READY_FOR_U27B2E2E_FINAL_FIGURES_5_TO_8_FREEZE"
        )
    else:
        decision = (
            "TARGETED_U27B2E2D_SCATTER_OR_EXPORT_REPAIR_REQUIRED"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B2E2D",
                "decision": decision,
                "figures_rebuilt": len(png_paths),
                "panels_expected": expected_panels,
                "panels_in_manifest": observed_panels,
                "panel_crops_present": len(crop_paths),
                "exports_present": observed_exports,
                "contact_sheets_present": contacts_present,
                "locked_source_paths_exist": source_paths_exist,
                "scatter_annotation_audit_pass": annotation_pass,
                "statistical_effects_recalculated": False,
                "displayed_modules_changed": False,
                "pathway_membership_changed": False,
                "source_locks_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B2E2E final freeze of Figures 5-8"
                    if decision.startswith("READY_FOR_U27B2E2E")
                    else "Inspect scatter annotation audit and exports"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B2E2D_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B2E2D_scatter_annotation_title_repair_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2E2D - Final visibility and title micro-repair\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Figures rebuilt: **4/4**.\n")
        handle.write(
            f"- Frozen panels represented: "
            f"**{observed_panels}/{expected_panels}**.\n"
        )
        handle.write(
            f"- PNG/SVG/PDF exports: **{observed_exports}/12**.\n"
        )
        handle.write(
            f"- Panel crops: **{len(crop_paths)}/{expected_panels}**.\n"
        )
        handle.write(
            f"- Scatter annotation audit: **{annotation_pass}**.\n\n"
        )

        handle.write("## Corrected defect\n\n")
        handle.write(
            "The U27B2E2A conversion searched for ordinary Text objects, "
            "whereas the scatter labels were Matplotlib Annotation objects. "
            "This phase explicitly removes the Annotation labels, preserves "
            "all points, and replaces six priority labels with numeric markers "
            "and compact keys.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "No numerical values, displayed modules, pathway assignments, "
            "source locks, statistical effects or biological interpretations "
            "were changed.\n"
        )

    (
        outresults
        / "UTI_HostOmics_U27B2E2D_run_manifest.json"
    ).write_text(
        json.dumps(
            {
                "version": VERSION,
                "decision": decision,
                "figures_rebuilt": len(png_paths),
                "panels": observed_panels,
                "panel_crops": len(crop_paths),
                "exports": observed_exports,
                "scatter_annotation_audit_pass": annotation_pass,
                "statistical_effects_recalculated": False,
                "displayed_modules_changed": False,
                "pathway_membership_changed": False,
                "source_locks_changed": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log(f"Figures rebuilt: {len(png_paths)}/4")
    log(f"Panels represented: {observed_panels}/{expected_panels}")
    log(f"Panel crops: {len(crop_paths)}/{expected_panels}")
    log(f"Exports present: {observed_exports}/12")
    log(f"Scatter annotation audit pass: {annotation_pass}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2E2D] ERROR: {exc}", file=sys.stderr)
        raise
