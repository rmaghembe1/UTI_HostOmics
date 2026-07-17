#!/usr/bin/env python3
"""
Phase U27B2C2D
Final label, title and margin polish for manuscript-facing Figures 1-4.

This phase starts from the validated U27B2C2B builders and repaired source
registry. It changes only artist text, axis position and export identity.

Repairs
-------
- Figure 1B: shorten right-edge dataset annotations.
- Figure 1F and Figure 2B: use concise evidence-class labels.
- Figure 2D: shorten complement labels.
- Figure 2E/F: shorten panel titles.
- Figure 2F, Figure 3C/G and Figure 4D/G: add left-label space.
- Preserve all numerical values, displayed modules and source locks.

No statistical values are recalculated.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
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


VERSION = "U27B2C2D_v1.0_2026-07-16"
TAG = "phaseU27B2C2D_final_label_margin_polish"
FINAL_BUILDER = "phaseU27B2C2B_rebuild_final_figures_1_to_4.py"
REPAIR_BUILDER = "phaseU27B2C1_repair_figures_1_to_4_layout.py"
REPAIRED_REGISTRY_RELATIVE = (
    "03_metadata/"
    "phaseU27B2C2A_GSE280297_full_effect_source_repair/"
    "UTI_HostOmics_U27B2C2A_repaired_locked_panel_source_registry.tsv"
)
PANEL_MAP_RELATIVE = (
    "03_metadata/"
    "phaseU27B1_architecture_freeze_and_asset_mapping/"
    "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv"
)
DPI = 300


def log(message: str) -> None:
    print(f"[U27B2C2D] {message}", flush=True)


def load_module(path: Path, name: str):
    if not path.exists():
        raise FileNotFoundError(f"Required script not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def concise_evidence_label(value: object) -> str:
    text = str(value).lower()
    if "limited" in text or "secondary" in text:
        return "Secondary"
    if "context" in text or "divergent" in text:
        return "Divergent"
    if "one fdr" in text or "provisional" in text:
        return "Provisional"
    if "two dataset" in text or "robust" in text:
        return "Robust"
    return str(value)


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


def polish_figure_1(fig: plt.Figure, axes: Sequence[plt.Axes]) -> None:
    b = axes[1]
    for text in b.texts:
        value = text.get_text()
        if value.startswith("n=60"):
            text.set_text("n=60 | 3 tissues")
            text.set_fontsize(4.6)
        elif value.startswith("n=4"):
            text.set_text("n=4 | ~10,000 QC cells")
            text.set_fontsize(4.6)
        elif value.startswith("n=73") or value.startswith("n=20"):
            text.set_fontsize(4.6)

    f = axes[5]
    f.set_yticklabels(
        [
            concise_evidence_label(label.get_text())
            for label in f.get_yticklabels()
        ],
        fontsize=5.0,
    )
    f.set_title("Evidence hierarchy", loc="left", fontsize=7.1, fontweight="bold", pad=4)


def polish_figure_2(fig: plt.Figure, axes: Sequence[plt.Axes]) -> None:
    a, b, c, d, e, f, g = axes

    b.set_xticklabels(
        [
            concise_evidence_label(label.get_text())
            for label in b.get_xticklabels()
        ],
        rotation=18,
        ha="right",
        fontsize=5.0,
    )
    b.set_title(
        "Evidence classes",
        loc="left",
        fontsize=7.1,
        fontweight="bold",
        pad=4,
    )

    d_labels = []
    for label in d.get_yticklabels():
        text = label.get_text().lower()
        if "opson" in text:
            d_labels.append("Opsonophagocytosis")
        elif "c3a" in text or "c5a" in text:
            d_labels.append("C3a/C5a")
        else:
            d_labels.append(label.get_text())
    d.set_yticklabels(d_labels, fontsize=5.0)

    e.set_title(
        "Adjusted systemic model",
        loc="left",
        fontsize=7.1,
        fontweight="bold",
        pad=4,
    )
    f.set_title(
        "Factorial comparator",
        loc="left",
        fontsize=7.1,
        fontweight="bold",
        pad=4,
    )

    shift_axis_right(f, 0.022)
    shift_axis_right(e, 0.010, 0.010)


def polish_figure_3(fig: plt.Figure, axes: Sequence[plt.Axes]) -> None:
    a, b, c, d, e, f, g, h = axes
    shift_axis_right(c, 0.030)
    shift_axis_right(e, 0.012)
    shift_axis_right(g, 0.016)

    c.set_yticklabels(
        [label.get_text() for label in c.get_yticklabels()],
        fontsize=4.75,
    )
    g.set_yticklabels(
        [label.get_text() for label in g.get_yticklabels()],
        fontsize=4.55,
    )


def polish_figure_4(fig: plt.Figure, axes: Sequence[plt.Axes]) -> None:
    a, b, c, d, e, f, g, h = axes
    shift_axis_right(d, 0.020)
    shift_axis_right(g, 0.026)

    d.set_yticklabels(
        [label.get_text() for label in d.get_yticklabels()],
        fontsize=4.35,
    )
    g.set_yticklabels(
        [label.get_text() for label in g.get_yticklabels()],
        fontsize=4.55,
    )


def save_figure(
    fig: plt.Figure,
    outdir: Path,
    figure_number: int,
) -> List[Path]:
    paths: List[Path] = []
    stem = f"UTI_HostOmics_U27B2C2D_Figure_{figure_number}"
    for extension in ("png", "svg", "pdf"):
        path = outdir / f"{stem}.{extension}"
        kwargs = {"dpi": DPI} if extension == "png" else {}
        fig.savefig(path, facecolor="white", **kwargs)
        paths.append(path)
    return paths


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
        / f"UTI_HostOmics_U27B2C2D_Figure_{figure_number}_source_values.tsv"
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
        bbox = axis.get_tightbbox(renderer).expanded(1.08, 1.12)
        x0 = max(int(bbox.x0), 0)
        y0 = max(int(height - bbox.y1), 0)
        x1 = min(int(bbox.x1), width)
        y1 = min(int(height - bbox.y0), height)
        crop = image.crop((x0, y0, x1, y1))

        letter = chr(ord("A") + index)
        path = (
            outdir
            / f"UTI_HostOmics_U27B2C2D_Figure_{figure_number}"
            f"_panel_{letter}.png"
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
    canvas = Image.new(
        "RGB",
        (canvas_width, canvas_height),
        "white",
    )

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
        tabledir / "UTI_HostOmics_U27B2C2D_export_audit.tsv",
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

    final_module = load_module(
        project / "10_scripts" / FINAL_BUILDER,
        "u27b2c2b_final",
    )
    repair_module = final_module.load_module(
        project / "10_scripts" / REPAIR_BUILDER,
        "u27b2c1_repair",
    )
    base_module = repair_module.load_base(project)

    registry_path = project / REPAIRED_REGISTRY_RELATIVE
    panel_map_path = project / PANEL_MAP_RELATIVE

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

    final_registry = final_module.build_final_registry(
        project,
        registry,
    )

    outfig = project / "06_figures" / TAG
    outtables = project / "06_tables" / TAG
    outresults = project / "05_results" / TAG
    outmetadata = project / "03_metadata" / TAG
    cropdir = outfig / "panel_crops"

    for directory in (
        outfig,
        outtables,
        outresults,
        outmetadata,
        cropdir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    final_registry.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B2C2D_final_build_source_registry.tsv",
        sep="\t",
        index=False,
    )

    # Use the validated U27B2C2B rendering helpers, but suppress its internal
    # export so the polished figures are saved only after artist adjustment.
    repair_module.panel_title = final_module.wrapped_panel_title
    repair_module.safe_heatmap = final_module.compact_heatmap
    repair_module.save_figure = lambda fig, outdir, number: []
    repair_module.save_source_rows = save_source_rows

    store = final_module.FinalSourceStore(
        base_module,
        final_registry,
    )

    builders = [
        (1, repair_module.build_figure_1, polish_figure_1),
        (2, repair_module.build_figure_2, polish_figure_2),
        (3, repair_module.build_figure_3, polish_figure_3),
        (4, repair_module.build_figure_4, polish_figure_4),
    ]

    figure_paths: List[Path] = []
    crop_paths: List[Path] = []

    for figure_number, builder, polisher in builders:
        log(f"Polishing Final Figure {figure_number}.")
        fig, _, axes = builder(
            base_module,
            store,
            outfig,
            outtables,
        )
        polisher(fig, axes)
        figure_paths.extend(
            save_figure(
                fig,
                outfig,
                figure_number,
            )
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

    png_paths = [
        path
        for path in figure_paths
        if path.suffix.lower() == ".png"
    ]

    full_contact = (
        outfig
        / "UTI_HostOmics_U27B2C2D_full_figure_contact_sheet.png"
    )
    panel_contact = (
        outfig
        / "UTI_HostOmics_U27B2C2D_panel_contact_sheet.png"
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
            ["Figure_1", "Figure_2", "Figure_3", "Figure_4"]
        )
    ].copy()
    build_manifest = build_manifest.merge(
        final_registry[
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
        / "UTI_HostOmics_U27B2C2D_Figures_1_to_4_build_manifest.tsv",
        sep="\t",
        index=False,
    )

    polish_manifest = pd.DataFrame(
        [
            ("Figure_1B", "Shortened dataset annotations"),
            ("Figure_1F", "Concise four-class hierarchy labels"),
            ("Figure_2B", "Concise evidence-class labels"),
            ("Figure_2D", "Shortened complement labels"),
            ("Figure_2E", "Shortened title"),
            ("Figure_2F", "Shortened title and increased left margin"),
            ("Figure_3C", "Increased left-label margin"),
            ("Figure_3G", "Increased left-label margin"),
            ("Figure_4D", "Increased left-label margin"),
            ("Figure_4G", "Increased left-label margin"),
        ],
        columns=["panel_key", "polish_action"],
    )
    polish_manifest.to_csv(
        outtables
        / "UTI_HostOmics_U27B2C2D_polish_manifest.tsv",
        sep="\t",
        index=False,
    )

    expected_panels = 29
    expected_exports = 12
    panels_present = build_manifest["panel_key"].nunique()
    exports_present = int(audit["exists"].sum())
    exports_nonempty = bool((audit["size_bytes"] > 0).all())
    contacts_present = full_contact.exists() and panel_contact.exists()
    all_paths_exist = bool(
        final_registry["locked_path"]
        .astype(str)
        .map(lambda value: Path(value).exists())
        .all()
    )

    if (
        panels_present == expected_panels
        and len(crop_paths) == expected_panels
        and exports_present == expected_exports
        and exports_nonempty
        and contacts_present
        and all_paths_exist
    ):
        decision = (
            "READY_FOR_U27B2C2E_FINAL_FIGURES_1_TO_4_FREEZE_AUDIT"
        )
    else:
        decision = "TARGETED_U27B2C2D_EXPORT_REPAIR_REQUIRED"

    pd.DataFrame(
        [
            {
                "phase": "U27B2C2D",
                "decision": decision,
                "figures_polished": len(png_paths),
                "panels_expected": expected_panels,
                "panels_in_manifest": panels_present,
                "panel_crops_present": len(crop_paths),
                "exports_expected": expected_exports,
                "exports_present": exports_present,
                "nonempty_exports": exports_nonempty,
                "contact_sheets_present": contacts_present,
                "all_locked_paths_exist": all_paths_exist,
                "scientific_values_recalculated": False,
                "displayed_modules_changed": False,
                "source_locks_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B2C2E final visual freeze audit"
                    if decision.startswith("READY_FOR_U27B2C2E")
                    else "Repair missing export or contact sheet"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B2C2D_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B2C2D_final_polish_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2C2D - Final label and margin polish\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Figures polished: **4/4**.\n")
        handle.write(
            f"- Panels represented: **{panels_present}/29**.\n"
        )
        handle.write(
            f"- PNG/SVG/PDF exports: "
            f"**{exports_present}/12**.\n"
        )
        handle.write(
            f"- Panel crops: **{len(crop_paths)}/29**.\n\n"
        )
        handle.write("## Scope\n\n")
        handle.write(
            "This phase changed only concise labels, panel titles and axis "
            "positions. Numerical values, displayed modules, source locks and "
            "statistical interpretations were preserved.\n"
        )

    (
        outresults
        / "UTI_HostOmics_U27B2C2D_run_manifest.json"
    ).write_text(
        json.dumps(
            {
                "version": VERSION,
                "decision": decision,
                "figures_polished": len(png_paths),
                "panels": panels_present,
                "exports": exports_present,
                "panel_crops": len(crop_paths),
                "scientific_values_recalculated": False,
                "displayed_modules_changed": False,
                "source_locks_changed": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log(f"Figures polished: {len(png_paths)}/4")
    log(f"Panels represented: {panels_present}/29")
    log(f"Exports present: {exports_present}/12")
    log(f"Panel crops: {len(crop_paths)}/29")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2C2D] ERROR: {exc}", file=sys.stderr)
        raise
