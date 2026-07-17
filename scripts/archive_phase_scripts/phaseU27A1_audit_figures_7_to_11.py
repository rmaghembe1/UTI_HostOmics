#!/usr/bin/env python3
"""
Phase U27A.1
Visual-quality audit for Figures 7-11.

This phase does not alter the scientific source figures. It:
1. inventories PNG/SVG/PDF outputs;
2. checks raster dimensions, aspect ratios and border-content density;
3. inspects SVG width, height and viewBox metadata;
4. creates full-resolution and journal-width contact sheets;
5. creates one-column and two-column readability previews;
6. flags likely typography and clipping risks;
7. decides whether figures can proceed to manuscript integration or require
   targeted redesign.

The original U27A figures are preserved.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps
except ImportError as exc:
    raise SystemExit(
        "ERROR: Pillow is required. Install with: python3 -m pip install pillow"
    ) from exc


VERSION = "U27A1_v1.0_2026-07-14"
TAG = "phaseU27A1_figure_visual_quality_audit"
SOURCE_TAG = "phaseU27A_build_figures_7_to_11"

TWO_COLUMN_MM = 180.0
ONE_COLUMN_MM = 85.0
PREVIEW_DPI = 300
EXPECTED_FIGURES = [
    "Figure_7",
    "Figure_8",
    "Figure_9",
    "Figure_10",
    "Figure_11",
]


def log(message: str) -> None:
    print(f"[U27A.1] {message}", flush=True)


def mm_to_pixels(mm: float, dpi: int) -> int:
    return int(round(mm / 25.4 * dpi))


def find_png(source_dir: Path, figure: str) -> Path:
    matches = sorted(source_dir.glob(f"*{figure}.png"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one PNG for {figure}, found {len(matches)}"
        )
    return matches[0]


def find_format(source_dir: Path, figure: str, extension: str) -> Optional[Path]:
    matches = sorted(source_dir.glob(f"*{figure}.{extension}"))
    return matches[0] if len(matches) == 1 else None


def border_density(image: Image.Image, border_fraction: float = 0.012) -> Dict[str, float]:
    """
    Estimate non-white content touching the outer border.

    This is only a clipping-risk heuristic. A high border density means text,
    marks or axes may be too close to the image boundary.
    """
    rgb = image.convert("RGB")
    array = np.asarray(rgb)
    gray_distance = 255.0 - array.mean(axis=2)

    h, w = gray_distance.shape
    bx = max(1, int(round(w * border_fraction)))
    by = max(1, int(round(h * border_fraction)))

    masks = {
        "left": gray_distance[:, :bx],
        "right": gray_distance[:, w - bx :],
        "top": gray_distance[:by, :],
        "bottom": gray_distance[h - by :, :],
    }

    return {
        f"{side}_border_nonwhite_fraction": float((values > 18).mean())
        for side, values in masks.items()
    }


def content_bbox_fraction(image: Image.Image) -> Tuple[float, float, float, float]:
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, (255, 255, 255))
    difference = ImageChops.difference(rgb, background).convert("L")
    thresholded = difference.point(lambda value: 255 if value > 12 else 0)
    bbox = thresholded.getbbox()

    if bbox is None:
        return (0.0, 0.0, 0.0, 0.0)

    left, top, right, bottom = bbox
    width, height = rgb.size
    return (
        left / width,
        top / height,
        (width - right) / width,
        (height - bottom) / height,
    )


def parse_svg(path: Path) -> Dict[str, object]:
    output = {
        "svg_width": "",
        "svg_height": "",
        "svg_viewbox": "",
        "svg_parse_error": "",
    }
    if path is None or not path.exists():
        output["svg_parse_error"] = "missing"
        return output

    try:
        root = ET.parse(path).getroot()
        output["svg_width"] = root.attrib.get("width", "")
        output["svg_height"] = root.attrib.get("height", "")
        output["svg_viewbox"] = root.attrib.get("viewBox", "")
    except Exception as exc:
        output["svg_parse_error"] = repr(exc)
    return output


def make_readability_preview(
    source: Image.Image,
    target_width_px: int,
    label: str,
) -> Image.Image:
    source = source.convert("RGB")
    target_height = max(
        1,
        int(round(source.height * target_width_px / source.width)),
    )
    resized = source.resize(
        (target_width_px, target_height),
        Image.Resampling.LANCZOS,
    )

    header_height = 80
    canvas = Image.new(
        "RGB",
        (target_width_px, target_height + header_height),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (18, 16),
        label,
        fill="black",
    )
    draw.text(
        (18, 43),
        f"{target_width_px} px wide at {PREVIEW_DPI} dpi",
        fill="black",
    )
    canvas.paste(resized, (0, header_height))
    return canvas


def make_contact_sheet(
    items: List[Tuple[str, Image.Image]],
    output: Path,
    columns: int = 2,
    thumb_width: int = 1500,
) -> None:
    prepared = []
    for label, image in items:
        rgb = image.convert("RGB")
        height = int(round(rgb.height * thumb_width / rgb.width))
        resized = rgb.resize(
            (thumb_width, height),
            Image.Resampling.LANCZOS,
        )
        header = 70
        canvas = Image.new(
            "RGB",
            (thumb_width, height + header),
            "white",
        )
        draw = ImageDraw.Draw(canvas)
        draw.text((15, 18), label, fill="black")
        canvas.paste(resized, (0, header))
        prepared.append(canvas)

    rows = int(math.ceil(len(prepared) / columns))
    cell_height = max(image.height for image in prepared)
    sheet = Image.new(
        "RGB",
        (columns * thumb_width, rows * cell_height),
        "white",
    )

    for index, image in enumerate(prepared):
        row = index // columns
        column = index % columns
        sheet.paste(
            image,
            (column * thumb_width, row * cell_height),
        )

    sheet.save(output, dpi=(PREVIEW_DPI, PREVIEW_DPI))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    source_dir = project / "06_figures" / SOURCE_TAG

    out_figures = project / "06_figures" / TAG
    out_tables = project / "06_tables" / TAG
    out_results = project / "05_results" / TAG

    for directory in [out_figures, out_tables, out_results]:
        directory.mkdir(parents=True, exist_ok=True)

    if not source_dir.exists():
        raise FileNotFoundError(f"U27A figure directory not found: {source_dir}")

    two_column_px = mm_to_pixels(TWO_COLUMN_MM, PREVIEW_DPI)
    one_column_px = mm_to_pixels(ONE_COLUMN_MM, PREVIEW_DPI)

    audit_rows = []
    full_items = []
    two_column_items = []
    one_column_items = []

    for figure in EXPECTED_FIGURES:
        png_path = find_png(source_dir, figure)
        svg_path = find_format(source_dir, figure, "svg")
        pdf_path = find_format(source_dir, figure, "pdf")

        log(f"Auditing {figure}.")
        image = Image.open(png_path).convert("RGB")
        width, height = image.size
        aspect = width / height

        density = border_density(image)
        margins = content_bbox_fraction(image)
        svg = parse_svg(svg_path)

        high_border = any(
            value >= 0.08
            for value in density.values()
        )
        narrow_margin = any(
            margin <= 0.004
            for margin in margins
        )

        two_preview = make_readability_preview(
            image,
            two_column_px,
            f"{figure}: two-column preview ({TWO_COLUMN_MM:.0f} mm)",
        )
        one_preview = make_readability_preview(
            image,
            one_column_px,
            f"{figure}: one-column preview ({ONE_COLUMN_MM:.0f} mm)",
        )

        two_path = out_figures / f"UTI_HostOmics_U27A1_{figure}_two_column_preview.png"
        one_path = out_figures / f"UTI_HostOmics_U27A1_{figure}_one_column_preview.png"
        two_preview.save(two_path, dpi=(PREVIEW_DPI, PREVIEW_DPI))
        one_preview.save(one_path, dpi=(PREVIEW_DPI, PREVIEW_DPI))

        full_items.append((f"{figure}: original PNG", image))
        two_column_items.append(
            (f"{figure}: {TWO_COLUMN_MM:.0f}-mm preview", two_preview)
        )
        one_column_items.append(
            (f"{figure}: {ONE_COLUMN_MM:.0f}-mm preview", one_preview)
        )

        audit_rows.append(
            {
                "figure": figure,
                "png_path": str(png_path),
                "png_size_bytes": png_path.stat().st_size,
                "png_width_px": width,
                "png_height_px": height,
                "aspect_ratio": aspect,
                "two_column_target_width_px": two_column_px,
                "one_column_target_width_px": one_column_px,
                "downscale_factor_two_column": two_column_px / width,
                "downscale_factor_one_column": one_column_px / width,
                "left_content_margin_fraction": margins[0],
                "top_content_margin_fraction": margins[1],
                "right_content_margin_fraction": margins[2],
                "bottom_content_margin_fraction": margins[3],
                **density,
                "border_clipping_risk_flag": high_border or narrow_margin,
                "svg_path": str(svg_path) if svg_path else "",
                "svg_size_bytes": (
                    svg_path.stat().st_size if svg_path else np.nan
                ),
                **svg,
                "pdf_path": str(pdf_path) if pdf_path else "",
                "pdf_size_bytes": (
                    pdf_path.stat().st_size if pdf_path else np.nan
                ),
                "two_column_preview_path": str(two_path),
                "one_column_preview_path": str(one_path),
            }
        )

    audit = pd.DataFrame(audit_rows)
    audit.to_csv(
        out_tables / "UTI_HostOmics_U27A1_figure_visual_audit.tsv",
        sep="\t",
        index=False,
    )

    make_contact_sheet(
        full_items,
        out_figures / "UTI_HostOmics_U27A1_original_figures_contact_sheet.png",
        columns=2,
        thumb_width=1500,
    )
    make_contact_sheet(
        two_column_items,
        out_figures / "UTI_HostOmics_U27A1_two_column_contact_sheet.png",
        columns=2,
        thumb_width=two_column_px,
    )
    make_contact_sheet(
        one_column_items,
        out_figures / "UTI_HostOmics_U27A1_one_column_contact_sheet.png",
        columns=2,
        thumb_width=one_column_px,
    )

    # U27A used an 18-inch-wide canvas. At 180 mm publication width, the
    # linear reduction is approximately 0.394. Fonts originally set at
    # 5.5-10 pt consequently appear around 2.2-3.9 pt.
    publication_scale = (TWO_COLUMN_MM / 25.4) / 18.0
    estimated_smallest_font_pt = 5.5 * publication_scale
    estimated_typical_font_pt = 7.0 * publication_scale
    estimated_panel_title_pt = 10.0 * publication_scale

    typography_risk = estimated_typical_font_pt < 6.0
    clipping_flags = int(audit["border_clipping_risk_flag"].sum())

    # Technical production is complete, but the inferred typography scaling
    # makes journal-size readability doubtful until previews are inspected.
    if typography_risk or clipping_flags > 0:
        decision = "TARGETED_FIGURE_READABILITY_REDESIGN_REQUIRED_BEFORE_U27B"
    else:
        decision = "READY_FOR_U27B_RESULTS_DISCUSSION_AND_LEGEND_INTEGRATION"

    pd.DataFrame(
        [
            {
                "phase": "U27A.1",
                "decision": decision,
                "n_figures_audited": len(audit),
                "n_figures_with_border_clipping_risk": clipping_flags,
                "source_canvas_width_inferred_inches": 18.0,
                "two_column_publication_width_mm": TWO_COLUMN_MM,
                "publication_linear_scale_from_source": publication_scale,
                "estimated_smallest_font_at_two_column_pt": (
                    estimated_smallest_font_pt
                ),
                "estimated_typical_font_at_two_column_pt": (
                    estimated_typical_font_pt
                ),
                "estimated_panel_title_at_two_column_pt": (
                    estimated_panel_title_pt
                ),
                "typography_readability_risk": typography_risk,
                "original_figures_modified": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27A.2 targeted typography/layout repair"
                    if decision.startswith("TARGETED")
                    else "U27B manuscript and legend integration"
                ),
            }
        ]
    ).to_csv(
        out_tables / "UTI_HostOmics_U27A1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results / "UTI_HostOmics_U27A1_visual_quality_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# Phase U27A.1 - Figure visual-quality audit\n\n")
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(f"- Figures audited: **{len(audit)}**.\n")
        handle.write(
            f"- Border/clipping heuristic flags: **{clipping_flags}**.\n"
        )
        handle.write(
            "- Original figures and manuscript were not modified.\n\n"
        )

        handle.write("## Typography scaling risk\n\n")
        handle.write(
            "The U27A figures were created on an approximately 18-inch-wide "
            "canvas. Reduction to a 180-mm two-column journal width gives a "
            f"linear scale of approximately **{publication_scale:.3f}**. "
            "Thus, source fonts of 5.5, 7 and 10 pt would appear at "
            f"approximately **{estimated_smallest_font_pt:.1f}**, "
            f"**{estimated_typical_font_pt:.1f}** and "
            f"**{estimated_panel_title_pt:.1f} pt**, respectively. "
            "This is below normal publication readability and should be "
            "verified in the generated journal-width previews.\n\n"
        )

        handle.write("## Generated review assets\n\n")
        handle.write(
            "- Original-resolution contact sheet.\n"
            "- Two-column 180-mm contact sheet.\n"
            "- One-column 85-mm contact sheet.\n"
            "- Individual two-column and one-column previews for Figures 7-11.\n\n"
        )

        handle.write("## Review checklist\n\n")
        handle.write(
            "1. Open the two-column contact sheet at 100% zoom.\n"
            "2. Confirm every module label is readable without zooming.\n"
            "3. Check panel letters, color bars and numeric annotations.\n"
            "4. Inspect Figure 11 network labels and arrows for collisions.\n"
            "5. Confirm Figure 10 clearly indicates that lectin and terminal "
            "MAC lack GSE252321 cell-level attribution.\n"
            "6. Use SVG/PDF outputs for final journal upload after any "
            "layout repair.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "n_figures_audited": int(len(audit)),
        "typography_readability_risk": bool(typography_risk),
        "n_border_clipping_flags": clipping_flags,
        "original_figures_modified": False,
        "manuscript_modified": False,
    }
    (
        out_results / "UTI_HostOmics_U27A1_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log(f"Figures audited: {len(audit)}")
    log(f"Border/clipping flags: {clipping_flags}")
    log(
        f"Estimated typical two-column font size: "
        f"{estimated_typical_font_pt:.2f} pt"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27A.1] ERROR: {exc}", file=sys.stderr)
        raise
