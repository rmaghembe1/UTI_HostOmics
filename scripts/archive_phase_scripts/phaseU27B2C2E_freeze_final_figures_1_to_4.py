#!/usr/bin/env python3
"""
Phase U27B2C2E
Freeze manuscript-facing Final Figures 1-4 after final visual approval.

This phase:
1. verifies the U27B2C2D PNG/SVG/PDF exports for Figures 1-4;
2. verifies panel crops and contact sheets;
3. copies all accepted assets non-destructively into a normalized frozen
   manuscript-facing directory;
4. computes SHA256 checksums;
5. writes an export audit, frozen manifest, visual-approval record and decision.

No scientific values, figure content or manuscript text are modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

try:
    from PIL import Image
except ImportError:
    Image = None


VERSION = "U27B2C2E_v1.0_2026-07-16"
TAG = "phaseU27B2C2E_final_figures_1_to_4_freeze"
SOURCE_TAG = "phaseU27B2C2D_final_label_margin_polish"

EXPECTED_FIGURES = [1, 2, 3, 4]
EXPECTED_FORMATS = ["png", "svg", "pdf"]
EXPECTED_PANEL_COUNTS = {1: 6, 2: 7, 3: 8, 4: 8}

VISUAL_AUDIT = [
    {
        "figure": "Figure_1",
        "status": "PASS",
        "assessment": (
            "All four datasets are represented; evidence hierarchy is complete; "
            "workflow and labels are readable; no blocking collisions."
        ),
    },
    {
        "figure": "Figure_2",
        "status": "PASS",
        "assessment": (
            "Independent effects, evidence classes, core networks, comparators "
            "and concordance are visually separated and readable."
        ),
    },
    {
        "figure": "Figure_3",
        "status": "PASS",
        "assessment": (
            "Full pregnancy module diversity is restored across endocrine, "
            "metabolic, inflammatory-carbon and complement branches."
        ),
    },
    {
        "figure": "Figure_4",
        "status": "PASS",
        "assessment": (
            "Embedding, marker validation, composition, targeted states and "
            "cellular localization are readable at manuscript width."
        ),
    },
]


def log(message: str) -> None:
    print(f"[U27B2C2E] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def png_dimensions(path: Path) -> Tuple[int | None, int | None]:
    if Image is None or path.suffix.lower() != ".png":
        return None, None
    with Image.open(path) as image:
        return image.size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    source_figures = project / "06_figures" / SOURCE_TAG
    source_tables = project / "06_tables" / SOURCE_TAG
    source_metadata = project / "03_metadata" / SOURCE_TAG

    frozen_figures = project / "06_figures" / TAG
    frozen_tables = project / "06_tables" / TAG
    frozen_metadata = project / "03_metadata" / TAG
    frozen_results = project / "05_results" / TAG

    for directory in (
        frozen_figures,
        frozen_tables,
        frozen_metadata,
        frozen_results,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    if not source_figures.exists():
        raise FileNotFoundError(
            f"Accepted U27B2C2D figure directory not found: {source_figures}"
        )

    manifest_rows: List[Dict[str, object]] = []
    export_audit_rows: List[Dict[str, object]] = []

    log("Verifying and freezing Figure 1-4 exports.")

    for figure_number in EXPECTED_FIGURES:
        for extension in EXPECTED_FORMATS:
            source = (
                source_figures
                / f"UTI_HostOmics_U27B2C2D_Figure_{figure_number}.{extension}"
            )
            if not source.exists():
                raise FileNotFoundError(f"Missing accepted figure export: {source}")
            if source.stat().st_size <= 0:
                raise RuntimeError(f"Empty accepted figure export: {source}")

            destination = (
                frozen_figures
                / f"UTI_HostOmics_U27B2C2E_Figure_{figure_number}.{extension}"
            )
            shutil.copy2(source, destination)

            width, height = png_dimensions(destination)
            checksum = sha256(destination)

            manifest_rows.append(
                {
                    "asset_type": "main_figure",
                    "figure_number": figure_number,
                    "panel": "",
                    "format": extension,
                    "source_path": str(source),
                    "frozen_path": str(destination),
                    "size_bytes": destination.stat().st_size,
                    "sha256": checksum,
                }
            )
            export_audit_rows.append(
                {
                    "figure_number": figure_number,
                    "format": extension,
                    "source_exists": source.exists(),
                    "frozen_exists": destination.exists(),
                    "nonempty": destination.stat().st_size > 0,
                    "png_width_px": width,
                    "png_height_px": height,
                    "sha256": checksum,
                }
            )

    frozen_crop_dir = frozen_figures / "panel_crops"
    frozen_crop_dir.mkdir(parents=True, exist_ok=True)

    observed_panel_crops = 0
    for figure_number, panel_count in EXPECTED_PANEL_COUNTS.items():
        for index in range(panel_count):
            panel = chr(ord("A") + index)
            source = (
                source_figures
                / "panel_crops"
                / f"UTI_HostOmics_U27B2C2D_Figure_{figure_number}_panel_{panel}.png"
            )
            if not source.exists():
                raise FileNotFoundError(f"Missing accepted panel crop: {source}")

            destination = (
                frozen_crop_dir
                / f"UTI_HostOmics_U27B2C2E_Figure_{figure_number}_panel_{panel}.png"
            )
            shutil.copy2(source, destination)
            observed_panel_crops += 1

            width, height = png_dimensions(destination)
            manifest_rows.append(
                {
                    "asset_type": "panel_crop",
                    "figure_number": figure_number,
                    "panel": panel,
                    "format": "png",
                    "source_path": str(source),
                    "frozen_path": str(destination),
                    "size_bytes": destination.stat().st_size,
                    "sha256": sha256(destination),
                    "png_width_px": width,
                    "png_height_px": height,
                }
            )

    contact_sheet_names = [
        "full_figure_contact_sheet",
        "panel_contact_sheet",
    ]
    for stem in contact_sheet_names:
        source = (
            source_figures
            / f"UTI_HostOmics_U27B2C2D_{stem}.png"
        )
        if not source.exists():
            raise FileNotFoundError(f"Missing accepted contact sheet: {source}")

        destination = (
            frozen_figures
            / f"UTI_HostOmics_U27B2C2E_{stem}.png"
        )
        shutil.copy2(source, destination)
        width, height = png_dimensions(destination)

        manifest_rows.append(
            {
                "asset_type": "contact_sheet",
                "figure_number": "",
                "panel": "",
                "format": "png",
                "source_path": str(source),
                "frozen_path": str(destination),
                "size_bytes": destination.stat().st_size,
                "sha256": sha256(destination),
                "png_width_px": width,
                "png_height_px": height,
            }
        )

    # Preserve the final build/source registry and build manifest.
    registry_source = (
        source_metadata
        / "UTI_HostOmics_U27B2C2D_final_build_source_registry.tsv"
    )
    build_manifest_source = (
        source_metadata
        / "UTI_HostOmics_U27B2C2D_Figures_1_to_4_build_manifest.tsv"
    )

    for source, destination_name in [
        (
            registry_source,
            "UTI_HostOmics_U27B2C2E_frozen_source_registry.tsv",
        ),
        (
            build_manifest_source,
            "UTI_HostOmics_U27B2C2E_frozen_build_manifest.tsv",
        ),
    ]:
        if not source.exists():
            raise FileNotFoundError(f"Missing final provenance file: {source}")
        shutil.copy2(source, frozen_metadata / destination_name)

    # Preserve panel source-value tables.
    source_value_files = []
    for figure_number in EXPECTED_FIGURES:
        source = (
            source_tables
            / f"UTI_HostOmics_U27B2C2D_Figure_{figure_number}_source_values.tsv"
        )
        if not source.exists():
            raise FileNotFoundError(
                f"Missing final figure source-values table: {source}"
            )
        destination = (
            frozen_tables
            / f"UTI_HostOmics_U27B2C2E_Figure_{figure_number}_source_values.tsv"
        )
        shutil.copy2(source, destination)
        source_value_files.append(destination)

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(
        frozen_metadata
        / "UTI_HostOmics_U27B2C2E_frozen_asset_manifest.tsv",
        sep="\t",
        index=False,
    )

    export_audit = pd.DataFrame(export_audit_rows)
    export_audit.to_csv(
        frozen_tables
        / "UTI_HostOmics_U27B2C2E_export_audit.tsv",
        sep="\t",
        index=False,
    )

    visual_audit = pd.DataFrame(VISUAL_AUDIT)
    visual_audit.to_csv(
        frozen_tables
        / "UTI_HostOmics_U27B2C2E_visual_approval_record.tsv",
        sep="\t",
        index=False,
    )

    expected_exports = len(EXPECTED_FIGURES) * len(EXPECTED_FORMATS)
    observed_exports = len(
        manifest[manifest["asset_type"] == "main_figure"]
    )
    expected_panel_crops = sum(EXPECTED_PANEL_COUNTS.values())
    all_visual_pass = bool((visual_audit["status"] == "PASS").all())
    all_exports_nonempty = bool(export_audit["nonempty"].all())
    frozen_paths_exist = bool(
        manifest["frozen_path"].astype(str).map(lambda value: Path(value).exists()).all()
    )

    if (
        observed_exports == expected_exports
        and observed_panel_crops == expected_panel_crops
        and all_visual_pass
        and all_exports_nonempty
        and frozen_paths_exist
        and len(source_value_files) == 4
    ):
        decision = (
            "READY_FOR_U27B2D_SCRIPTED_FINAL_FIGURES_5_TO_8_BUILD"
        )
    else:
        decision = "TARGETED_FINAL_FIGURES_1_TO_4_FREEZE_REPAIR_REQUIRED"

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B2C2E",
                "decision": decision,
                "figures_frozen": len(EXPECTED_FIGURES),
                "figure_exports_expected": expected_exports,
                "figure_exports_frozen": observed_exports,
                "panel_crops_expected": expected_panel_crops,
                "panel_crops_frozen": observed_panel_crops,
                "visual_audit_pass": all_visual_pass,
                "all_exports_nonempty": all_exports_nonempty,
                "all_frozen_paths_exist": frozen_paths_exist,
                "source_value_tables_frozen": len(source_value_files),
                "scientific_values_changed": False,
                "displayed_modules_changed": False,
                "source_locks_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B2D scripted Final Figures 5-8 build"
                    if decision.startswith("READY_FOR_U27B2D")
                    else "Repair incomplete frozen assets"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        frozen_tables
        / "UTI_HostOmics_U27B2C2E_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        frozen_results
        / "UTI_HostOmics_U27B2C2E_final_figures_1_to_4_freeze_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2C2E - Final Figures 1-4 freeze\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Figures visually approved: **4/4**.\n")
        handle.write(
            f"- PNG/SVG/PDF exports frozen: "
            f"**{observed_exports}/{expected_exports}**.\n"
        )
        handle.write(
            f"- Panel crops frozen: "
            f"**{observed_panel_crops}/{expected_panel_crops}**.\n"
        )
        handle.write(
            f"- Figure source-value tables frozen: "
            f"**{len(source_value_files)}/4**.\n\n"
        )

        handle.write("## Final visual decision\n\n")
        handle.write(
            "Figures 1-4 are accepted as manuscript-facing assets. No "
            "blocking title, label, legend, colorbar, clipping or panel-layout "
            "defects remain at the intended 180-mm figure width. Dense "
            "heatmap labels in Figures 3 and 4 remain appropriately preserved "
            "in the SVG/PDF masters.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "The freeze is non-destructive. It copies the accepted U27B2C2D "
            "outputs, source-value tables and provenance records without "
            "changing scientific values, displayed modules or source locks.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "figures_frozen": 4,
        "exports_frozen": observed_exports,
        "panel_crops_frozen": observed_panel_crops,
        "visual_audit_pass": all_visual_pass,
        "scientific_values_changed": False,
        "displayed_modules_changed": False,
        "source_locks_changed": False,
        "manuscript_modified": False,
    }
    (
        frozen_results
        / "UTI_HostOmics_U27B2C2E_run_manifest.json"
    ).write_text(
        json.dumps(run_manifest, indent=2),
        encoding="utf-8",
    )

    log("Figures 1-4 visually approved and frozen.")
    log(f"Figure exports frozen: {observed_exports}/{expected_exports}")
    log(
        f"Panel crops frozen: "
        f"{observed_panel_crops}/{expected_panel_crops}"
    )
    log(f"Decision: {decision}")
    log(f"Frozen directory: {frozen_figures}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2C2E] ERROR: {exc}", file=sys.stderr)
        raise
