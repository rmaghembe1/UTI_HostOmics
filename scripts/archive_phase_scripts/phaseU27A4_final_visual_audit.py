#!/usr/bin/env python3
"""
Phase U27A.4
Final visual audit and normalized export of Figures 7-11.

This phase:
1. verifies PNG/SVG/PDF availability for all five figures;
2. normalizes all output filenames to a single U27A4 prefix;
3. audits PNG dimensions, aspect ratios, border density and content margins;
4. audits SVG dimensions/viewBox metadata;
5. creates full-figure, two-column, one-column and quadrant contact sheets;
6. verifies the visual-grammar manifest;
7. produces a final pre-manuscript decision.

The U27A.3.2 source figures are preserved. Scientific values are not changed.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    from PIL import Image, ImageChops, ImageDraw
except ImportError as exc:
    raise SystemExit(
        "ERROR: Pillow is required. Install with: "
        "python3 -m pip install pillow"
    ) from exc


VERSION = "U27A4_v1.0_2026-07-15"
TAG = "phaseU27A4_final_visual_audit"
SOURCE_TAG = "phaseU27A32_final_title_spacing_repair"

EXPECTED_FIGURES = [
    "Figure_7",
    "Figure_8",
    "Figure_9",
    "Figure_10",
    "Figure_11",
]
EXPECTED_FORMATS = ["png", "svg", "pdf"]

PREVIEW_DPI = 300
TWO_COLUMN_MM = 180.0
ONE_COLUMN_MM = 85.0


def log(message: str) -> None:
    print(f"[U27A4] {message}", flush=True)


def mm_to_pixels(mm: float, dpi: int = PREVIEW_DPI) -> int:
    return int(round(mm / 25.4 * dpi))


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", low_memory=False)


def locate_source_file(
    source_dir: Path,
    figure: str,
    extension: str,
) -> Path:
    matches = sorted(source_dir.glob(f"*{figure}.{extension}"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one {extension.upper()} for {figure}; "
            f"found {len(matches)}."
        )
    return matches[0]


def normalize_outputs(
    source_dir: Path,
    output_dir: Path,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []

    for figure in EXPECTED_FIGURES:
        for extension in EXPECTED_FORMATS:
            source = locate_source_file(source_dir, figure, extension)
            destination = (
                output_dir
                / f"UTI_HostOmics_U27A4_{figure}.{extension}"
            )
            shutil.copy2(source, destination)

            rows.append(
                {
                    "figure": figure,
                    "format": extension,
                    "source_path": str(source),
                    "normalized_path": str(destination),
                    "source_filename": source.name,
                    "normalized_filename": destination.name,
                    "source_prefix_mismatch": (
                        f"U27A32_{figure}" not in source.stem
                    ),
                    "size_bytes": destination.stat().st_size,
                }
            )

    return pd.DataFrame(rows)


def border_density(
    image: Image.Image,
    border_fraction: float = 0.012,
) -> Dict[str, float]:
    rgb = image.convert("RGB")
    array = np.asarray(rgb)
    gray_distance = 255.0 - array.mean(axis=2)

    height, width = gray_distance.shape
    border_x = max(1, int(round(width * border_fraction)))
    border_y = max(1, int(round(height * border_fraction)))

    border_arrays = {
        "left": gray_distance[:, :border_x],
        "right": gray_distance[:, width - border_x :],
        "top": gray_distance[:border_y, :],
        "bottom": gray_distance[height - border_y :, :],
    }

    return {
        f"{side}_border_nonwhite_fraction": float(
            (values > 18).mean()
        )
        for side, values in border_arrays.items()
    }


def content_margins(
    image: Image.Image,
) -> Tuple[float, float, float, float]:
    rgb = image.convert("RGB")
    white = Image.new("RGB", rgb.size, (255, 255, 255))
    difference = ImageChops.difference(rgb, white).convert("L")
    thresholded = difference.point(
        lambda value: 255 if value > 12 else 0
    )
    box = thresholded.getbbox()

    if box is None:
        return (0.0, 0.0, 0.0, 0.0)

    left, top, right, bottom = box
    width, height = rgb.size
    return (
        left / width,
        top / height,
        (width - right) / width,
        (height - bottom) / height,
    )


def parse_svg(path: Path) -> Dict[str, str]:
    result = {
        "svg_width": "",
        "svg_height": "",
        "svg_viewbox": "",
        "svg_parse_error": "",
    }

    try:
        root = ET.parse(path).getroot()
        result["svg_width"] = root.attrib.get("width", "")
        result["svg_height"] = root.attrib.get("height", "")
        result["svg_viewbox"] = root.attrib.get("viewBox", "")
    except Exception as exc:
        result["svg_parse_error"] = repr(exc)

    return result


def resize_to_width(
    image: Image.Image,
    width: int,
) -> Image.Image:
    image = image.convert("RGB")
    height = max(
        1,
        int(round(image.height * width / image.width)),
    )
    return image.resize(
        (width, height),
        Image.Resampling.LANCZOS,
    )


def labeled_canvas(
    image: Image.Image,
    label: str,
    header_height: int = 70,
) -> Image.Image:
    image = image.convert("RGB")
    canvas = Image.new(
        "RGB",
        (image.width, image.height + header_height),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    draw.text((15, 18), label, fill="black")
    canvas.paste(image, (0, header_height))
    return canvas


def contact_sheet(
    items: Sequence[Tuple[str, Image.Image]],
    output: Path,
    columns: int,
    cell_width: int,
) -> None:
    prepared = []
    for label, image in items:
        resized = resize_to_width(image, cell_width)
        prepared.append(labeled_canvas(resized, label))

    rows = int(math.ceil(len(prepared) / columns))
    cell_height = max(item.height for item in prepared)

    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * cell_height),
        "white",
    )

    for index, item in enumerate(prepared):
        row = index // columns
        column = index % columns
        sheet.paste(
            item,
            (column * cell_width, row * cell_height),
        )

    sheet.save(
        output,
        dpi=(PREVIEW_DPI, PREVIEW_DPI),
    )


def quadrant_crops(
    image: Image.Image,
) -> Dict[str, Image.Image]:
    """
    Create overlapping panel-review crops. The overlap retains titles,
    color bars and inter-panel gutters where collisions are most likely.
    """
    image = image.convert("RGB")
    width, height = image.size

    left_x0 = int(width * 0.00)
    left_x1 = int(width * 0.59)
    right_x0 = int(width * 0.43)
    right_x1 = width

    top_y0 = int(height * 0.04)
    top_y1 = int(height * 0.57)
    bottom_y0 = int(height * 0.43)
    bottom_y1 = int(height * 0.98)

    return {
        "A": image.crop((left_x0, top_y0, left_x1, top_y1)),
        "B": image.crop((right_x0, top_y0, right_x1, top_y1)),
        "C": image.crop((left_x0, bottom_y0, left_x1, bottom_y1)),
        "D": image.crop((right_x0, bottom_y0, right_x1, bottom_y1)),
    }


def audit_png(
    figure: str,
    png_path: Path,
    svg_path: Path,
    pdf_path: Path,
) -> Dict[str, object]:
    image = Image.open(png_path).convert("RGB")
    width, height = image.size
    margins = content_margins(image)
    density = border_density(image)

    border_flag = any(
        value >= 0.08 for value in density.values()
    )
    margin_flag = any(
        value <= 0.0035 for value in margins
    )

    return {
        "figure": figure,
        "png_path": str(png_path),
        "png_size_bytes": png_path.stat().st_size,
        "png_width_px": width,
        "png_height_px": height,
        "aspect_ratio": width / height,
        "left_content_margin_fraction": margins[0],
        "top_content_margin_fraction": margins[1],
        "right_content_margin_fraction": margins[2],
        "bottom_content_margin_fraction": margins[3],
        **density,
        "border_or_clipping_risk_flag": border_flag or margin_flag,
        "svg_path": str(svg_path),
        "svg_size_bytes": svg_path.stat().st_size,
        **parse_svg(svg_path),
        "pdf_path": str(pdf_path),
        "pdf_size_bytes": pdf_path.stat().st_size,
    }


def validate_visual_grammar(
    metadata_dir: Path,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    source = (
        metadata_dir
        / "UTI_HostOmics_U27A32_visual_grammar_manifest.tsv"
    )
    if not source.exists():
        raise FileNotFoundError(
            f"Visual-grammar manifest not found: {source}"
        )

    grammar = read_tsv(source)
    required = {"figure", "panel", "visual_grammar"}
    missing = sorted(required - set(grammar.columns))
    if missing:
        raise RuntimeError(
            f"Visual-grammar manifest missing columns: {missing}"
        )

    counts = grammar.groupby("figure")["panel"].nunique()
    all_four = all(
        counts.get(figure, 0) == 4
        for figure in EXPECTED_FIGURES
    )
    total_grammars = grammar["visual_grammar"].nunique()

    return grammar, {
        "all_figures_have_four_panels": all_four,
        "n_unique_visual_grammars": int(total_grammars),
        "visual_grammar_diversity_pass": (
            all_four and total_grammars >= 10
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    source_figures = project / "06_figures" / SOURCE_TAG
    source_metadata = project / "03_metadata" / SOURCE_TAG

    out_figures = project / "06_figures" / TAG
    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG

    for directory in [
        out_figures,
        out_tables,
        out_metadata,
        out_results,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    if not source_figures.exists():
        raise FileNotFoundError(
            f"Source figure directory not found: {source_figures}"
        )

    log("Normalizing final figure filenames.")
    normalized = normalize_outputs(
        source_figures,
        out_figures,
    )
    normalized.to_csv(
        out_tables
        / "UTI_HostOmics_U27A4_normalized_output_manifest.tsv",
        sep="\t",
        index=False,
    )

    grammar, grammar_summary = validate_visual_grammar(
        source_metadata
    )
    grammar.to_csv(
        out_metadata
        / "UTI_HostOmics_U27A4_visual_grammar_manifest.tsv",
        sep="\t",
        index=False,
    )

    audit_rows = []
    full_items: List[Tuple[str, Image.Image]] = []
    two_column_items: List[Tuple[str, Image.Image]] = []
    one_column_items: List[Tuple[str, Image.Image]] = []
    panel_items: List[Tuple[str, Image.Image]] = []

    two_width = mm_to_pixels(TWO_COLUMN_MM)
    one_width = mm_to_pixels(ONE_COLUMN_MM)

    for figure in EXPECTED_FIGURES:
        log(f"Auditing {figure}.")
        png_path = (
            out_figures
            / f"UTI_HostOmics_U27A4_{figure}.png"
        )
        svg_path = (
            out_figures
            / f"UTI_HostOmics_U27A4_{figure}.svg"
        )
        pdf_path = (
            out_figures
            / f"UTI_HostOmics_U27A4_{figure}.pdf"
        )

        audit_rows.append(
            audit_png(
                figure,
                png_path,
                svg_path,
                pdf_path,
            )
        )

        image = Image.open(png_path).convert("RGB")
        full_items.append((figure, image))
        two_column_items.append(
            (
                f"{figure}: 180-mm preview",
                resize_to_width(image, two_width),
            )
        )
        one_column_items.append(
            (
                f"{figure}: 85-mm preview",
                resize_to_width(image, one_width),
            )
        )

        for panel, crop in quadrant_crops(image).items():
            panel_items.append(
                (f"{figure} panel {panel}", crop)
            )

    audit = pd.DataFrame(audit_rows)
    audit.to_csv(
        out_tables
        / "UTI_HostOmics_U27A4_visual_audit.tsv",
        sep="\t",
        index=False,
    )

    log("Creating final contact sheets.")
    contact_sheet(
        full_items,
        out_figures
        / "UTI_HostOmics_U27A4_full_figure_contact_sheet.png",
        columns=2,
        cell_width=1450,
    )
    contact_sheet(
        two_column_items,
        out_figures
        / "UTI_HostOmics_U27A4_two_column_contact_sheet.png",
        columns=2,
        cell_width=two_width,
    )
    contact_sheet(
        one_column_items,
        out_figures
        / "UTI_HostOmics_U27A4_one_column_contact_sheet.png",
        columns=2,
        cell_width=one_width,
    )
    contact_sheet(
        panel_items,
        out_figures
        / "UTI_HostOmics_U27A4_panel_collision_contact_sheet.png",
        columns=2,
        cell_width=1250,
    )

    n_clipping_flags = int(
        audit["border_or_clipping_risk_flag"].sum()
    )
    all_formats = (
        normalized.groupby("figure")["format"].nunique()
        .reindex(EXPECTED_FIGURES)
        .fillna(0)
        .eq(3)
        .all()
    )
    naming_normalized = bool(
        normalized["normalized_filename"]
        .str.startswith("UTI_HostOmics_U27A4_")
        .all()
    )

    technical_ready = bool(
        len(audit) == 5
        and all_formats
        and naming_normalized
        and n_clipping_flags == 0
        and grammar_summary["visual_grammar_diversity_pass"]
    )

    decision = (
        "READY_FOR_U27B_PENDING_MANUAL_FINAL_CONTACT_SHEET_CONFIRMATION"
        if technical_ready
        else "TARGETED_FINAL_FIGURE_REVIEW_REQUIRED"
    )

    pd.DataFrame(
        [
            {
                "phase": "U27A.4",
                "decision": decision,
                "n_figures_audited": len(audit),
                "n_output_files": len(normalized),
                "all_figures_have_png_svg_pdf": all_formats,
                "all_filenames_normalized_to_U27A4": naming_normalized,
                "n_source_prefix_mismatches_corrected": int(
                    normalized["source_prefix_mismatch"].sum()
                ),
                "n_border_or_clipping_flags": n_clipping_flags,
                **grammar_summary,
                "scientific_values_changed": False,
                "manuscript_modified": False,
                "existing_figures_1_to_6_modified": False,
                "manual_contact_sheet_confirmation_required": True,
                "next_phase": (
                    "Open full and panel contact sheets; if visually clean, "
                    "proceed to U27B manuscript and legend integration"
                ),
            }
        ]
    ).to_csv(
        out_tables
        / "UTI_HostOmics_U27A4_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U27A4_final_visual_audit_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27A.4 - Final visual audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Figures audited: **{len(audit)}/5**.\n"
        )
        handle.write(
            f"- Normalized output files: **{len(normalized)}**.\n"
        )
        handle.write(
            f"- Border/clipping flags: **{n_clipping_flags}**.\n"
        )
        handle.write(
            f"- Source-prefix mismatches normalized: "
            f"**{int(normalized['source_prefix_mismatch'].sum())}**.\n"
        )
        handle.write(
            f"- Unique visual grammars: "
            f"**{grammar_summary['n_unique_visual_grammars']}**.\n\n"
        )

        handle.write("## Final review assets\n\n")
        handle.write(
            "- Full-figure contact sheet.\n"
            "- 180-mm two-column contact sheet.\n"
            "- 85-mm one-column contact sheet.\n"
            "- Twenty-panel collision contact sheet containing A-D crops "
            "from Figures 7-11.\n\n"
        )

        handle.write("## Required manual confirmation\n\n")
        handle.write(
            "The technical audit verifies file completeness, dimensions, "
            "border safety, normalized naming and visual-grammar diversity. "
            "Before manuscript integration, inspect the full-figure and "
            "panel-collision contact sheets at 100% zoom for residual title, "
            "legend, label or color-bar collisions. If clean, the normalized "
            "U27A4 SVG/PDF files should become the manuscript-facing figures.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "n_figures_audited": int(len(audit)),
        "n_output_files": int(len(normalized)),
        "n_clipping_flags": n_clipping_flags,
        "n_source_prefix_mismatches_corrected": int(
            normalized["source_prefix_mismatch"].sum()
        ),
        "scientific_values_changed": False,
        "manuscript_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U27A4_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Figures audited: {len(audit)}")
    log(f"Output files normalized: {len(normalized)}")
    log(f"Border/clipping flags: {n_clipping_flags}")
    log(
        "Source filename-prefix mismatches corrected: "
        f"{int(normalized['source_prefix_mismatch'].sum())}"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27A4] ERROR: {exc}", file=sys.stderr)
        raise
