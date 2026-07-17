#!/usr/bin/env python3
"""
Phase U27B2E2E
Freeze manuscript-facing Final Figures 5-8 after final visual approval.

This phase:
1. verifies the accepted U27B2E2D PNG/SVG/PDF exports for Figures 5-8;
2. verifies all 28 panel crops and both contact sheets;
3. copies accepted assets non-destructively into a normalized frozen directory;
4. preserves source-value tables, build provenance and annotation audits;
5. computes SHA256 checksums;
6. writes the final visual-approval record and phase decision.

No scientific values, figure content, displayed modules, pathway membership,
source locks or manuscript text are modified.
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


VERSION = "U27B2E2E_v1.0_2026-07-16"
TAG = "phaseU27B2E2E_final_figures_5_to_8_freeze"
SOURCE_TAG = "phaseU27B2E2D_final_visibility_title_microrepair"

EXPECTED_FIGURES = [5, 6, 7, 8]
EXPECTED_FORMATS = ["png", "svg", "pdf"]
EXPECTED_PANEL_COUNTS = {
    5: 7,
    6: 8,
    7: 7,
    8: 6,
}

VISUAL_APPROVAL = [
    {
        "figure": "Figure_5",
        "status": "PASS",
        "assessment": (
            "Steroid, cholesterol and lipid-remodeling architecture is "
            "pathway-specific and complete. The infection-pregnancy scatter "
            "uses a readable numbered key, point 4 is visible, and the "
            "subtype-support title and labels are complete."
        ),
    },
    {
        "figure": "Figure_6",
        "status": "PASS",
        "assessment": (
            "Adipokine, insulin, inflammatory-carbon, amino-acid, nucleotide, "
            "NAD and redox programs are complete and readable. No blank or "
            "pathway-contaminated panels remain."
        ),
    },
    {
        "figure": "Figure_7",
        "status": "PASS",
        "assessment": (
            "Complement panels are restricted to complement architecture. "
            "The infection-pregnancy comparison uses a compact numbered key, "
            "and branch, subtype and cellular-coverage panels are readable."
        ),
    },
    {
        "figure": "Figure_8",
        "status": "PASS",
        "assessment": (
            "Integrated infection, pregnancy, cellular-state and mechanistic "
            "synthesis is balanced. The evidence and interpretation boundary "
            "is readable and preserves all required caveats."
        ),
    },
]


def log(message: str) -> None:
    print(f"[U27B2E2E] {message}", flush=True)


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


def copy_required(
    source: Path,
    destination: Path,
) -> Dict[str, object]:
    if not source.exists():
        raise FileNotFoundError(f"Required accepted asset not found: {source}")
    if source.stat().st_size <= 0:
        raise RuntimeError(f"Accepted asset is empty: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

    width, height = png_dimensions(destination)
    return {
        "source_path": str(source),
        "frozen_path": str(destination),
        "format": destination.suffix.lower().lstrip("."),
        "size_bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "png_width_px": width,
        "png_height_px": height,
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
    source_tables = project / "06_tables" / SOURCE_TAG
    source_metadata = project / "03_metadata" / SOURCE_TAG
    source_results = project / "05_results" / SOURCE_TAG

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
            f"Accepted U27B2E2D figure directory not found: {source_figures}"
        )

    manifest_rows: List[Dict[str, object]] = []
    export_rows: List[Dict[str, object]] = []

    log("Freezing accepted Figure 5-8 exports.")

    for figure_number in EXPECTED_FIGURES:
        for extension in EXPECTED_FORMATS:
            source = (
                source_figures
                / f"UTI_HostOmics_U27B2E2D_Figure_{figure_number}.{extension}"
            )
            destination = (
                frozen_figures
                / f"UTI_HostOmics_U27B2E2E_Figure_{figure_number}.{extension}"
            )

            record = copy_required(source, destination)
            record.update(
                {
                    "asset_type": "main_figure",
                    "figure_number": figure_number,
                    "panel": "",
                }
            )
            manifest_rows.append(record)

            export_rows.append(
                {
                    "figure_number": figure_number,
                    "format": extension,
                    "source_exists": source.exists(),
                    "frozen_exists": destination.exists(),
                    "nonempty": destination.stat().st_size > 0,
                    "png_width_px": record["png_width_px"],
                    "png_height_px": record["png_height_px"],
                    "sha256": record["sha256"],
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
                / f"UTI_HostOmics_U27B2E2D_Figure_{figure_number}"
                f"_panel_{panel}.png"
            )
            destination = (
                frozen_crop_dir
                / f"UTI_HostOmics_U27B2E2E_Figure_{figure_number}"
                f"_panel_{panel}.png"
            )

            record = copy_required(source, destination)
            record.update(
                {
                    "asset_type": "panel_crop",
                    "figure_number": figure_number,
                    "panel": panel,
                }
            )
            manifest_rows.append(record)
            observed_panel_crops += 1

    for contact_name in (
        "full_figure_contact_sheet",
        "panel_contact_sheet",
    ):
        source = (
            source_figures
            / f"UTI_HostOmics_U27B2E2D_{contact_name}.png"
        )
        destination = (
            frozen_figures
            / f"UTI_HostOmics_U27B2E2E_{contact_name}.png"
        )

        record = copy_required(source, destination)
        record.update(
            {
                "asset_type": "contact_sheet",
                "figure_number": "",
                "panel": "",
            }
        )
        manifest_rows.append(record)

    # Preserve the four panel-level source-value tables.
    source_value_files = []
    for figure_number in EXPECTED_FIGURES:
        source = (
            source_tables
            / f"UTI_HostOmics_U27B2E2D_Figure_{figure_number}_source_values.tsv"
        )
        destination = (
            frozen_tables
            / f"UTI_HostOmics_U27B2E2E_Figure_{figure_number}_source_values.tsv"
        )
        copy_required(source, destination)
        source_value_files.append(destination)

    provenance_files = [
        (
            source_metadata
            / "UTI_HostOmics_U27B2E2D_Figures_5_to_8_build_manifest.tsv",
            frozen_metadata
            / "UTI_HostOmics_U27B2E2E_frozen_build_manifest.tsv",
        ),
        (
            source_tables
            / "UTI_HostOmics_U27B2E2D_scatter_annotation_audit.tsv",
            frozen_tables
            / "UTI_HostOmics_U27B2E2E_scatter_annotation_audit.tsv",
        ),
        (
            source_tables
            / "UTI_HostOmics_U27B2E2D_polish_manifest.tsv",
            frozen_tables
            / "UTI_HostOmics_U27B2E2E_polish_manifest.tsv",
        ),
        (
            source_tables
            / "UTI_HostOmics_U27B2E2D_export_audit.tsv",
            frozen_tables
            / "UTI_HostOmics_U27B2E2E_source_export_audit.tsv",
        ),
    ]

    preserved_provenance = 0
    for source, destination in provenance_files:
        copy_required(source, destination)
        preserved_provenance += 1

    # Preserve the final source registry used across the full figure package.
    registry_source = (
        project
        / "03_metadata"
        / "phaseU27B2C2E_final_figures_1_to_4_freeze"
        / "UTI_HostOmics_U27B2C2E_frozen_source_registry.tsv"
    )
    registry_destination = (
        frozen_metadata
        / "UTI_HostOmics_U27B2E2E_frozen_source_registry.tsv"
    )
    copy_required(registry_source, registry_destination)

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(
        frozen_metadata
        / "UTI_HostOmics_U27B2E2E_frozen_asset_manifest.tsv",
        sep="\t",
        index=False,
    )

    export_audit = pd.DataFrame(export_rows)
    export_audit.to_csv(
        frozen_tables
        / "UTI_HostOmics_U27B2E2E_export_audit.tsv",
        sep="\t",
        index=False,
    )

    visual_approval = pd.DataFrame(VISUAL_APPROVAL)
    visual_approval.to_csv(
        frozen_tables
        / "UTI_HostOmics_U27B2E2E_visual_approval_record.tsv",
        sep="\t",
        index=False,
    )

    expected_exports = (
        len(EXPECTED_FIGURES) * len(EXPECTED_FORMATS)
    )
    observed_exports = len(
        manifest[manifest["asset_type"] == "main_figure"]
    )
    expected_panel_crops = sum(EXPECTED_PANEL_COUNTS.values())

    all_visual_pass = bool(
        (visual_approval["status"] == "PASS").all()
    )
    all_exports_nonempty = bool(
        export_audit["nonempty"].all()
    )
    all_frozen_paths_exist = bool(
        manifest["frozen_path"]
        .astype(str)
        .map(lambda value: Path(value).exists())
        .all()
    )
    contact_sheets_frozen = (
        len(manifest[manifest["asset_type"] == "contact_sheet"]) == 2
    )

    if (
        observed_exports == expected_exports
        and observed_panel_crops == expected_panel_crops
        and all_visual_pass
        and all_exports_nonempty
        and all_frozen_paths_exist
        and contact_sheets_frozen
        and len(source_value_files) == 4
        and preserved_provenance == len(provenance_files)
        and registry_destination.exists()
    ):
        decision = (
            "READY_FOR_U27B3_COMPLETE_EIGHT_FIGURE_PACKAGE_"
            "AND_LEGEND_INTEGRATION"
        )
    else:
        decision = (
            "TARGETED_FINAL_FIGURES_5_TO_8_FREEZE_REPAIR_REQUIRED"
        )

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B2E2E",
                "decision": decision,
                "figures_frozen": len(EXPECTED_FIGURES),
                "figure_exports_expected": expected_exports,
                "figure_exports_frozen": observed_exports,
                "panel_crops_expected": expected_panel_crops,
                "panel_crops_frozen": observed_panel_crops,
                "contact_sheets_frozen": contact_sheets_frozen,
                "visual_audit_pass": all_visual_pass,
                "all_exports_nonempty": all_exports_nonempty,
                "all_frozen_paths_exist": all_frozen_paths_exist,
                "source_value_tables_frozen": len(source_value_files),
                "provenance_files_preserved": preserved_provenance,
                "source_registry_preserved": registry_destination.exists(),
                "scientific_values_changed": False,
                "displayed_modules_changed": False,
                "pathway_membership_changed": False,
                "source_locks_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B3 assemble complete Figures 1-8 package and "
                    "integrate figure legends"
                    if decision.startswith("READY_FOR_U27B3")
                    else "Repair incomplete frozen assets"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        frozen_tables
        / "UTI_HostOmics_U27B2E2E_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        frozen_results
        / "UTI_HostOmics_U27B2E2E_final_figures_5_to_8_freeze_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2E2E - Final Figures 5-8 freeze\n\n"
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
            f"- Contact sheets frozen: "
            f"**{int(contact_sheets_frozen)}/1 required pair**.\n"
        )
        handle.write(
            f"- Figure source-value tables frozen: "
            f"**{len(source_value_files)}/4**.\n\n"
        )

        handle.write("## Final visual decision\n\n")
        handle.write(
            "Figures 5-8 are accepted as manuscript-facing assets. The final "
            "visibility repair makes every selected scatter-point number "
            "identifiable and completes the Figure 5 subtype-support title. "
            "No blocking annotation, title, label, legend, colorbar, clipping "
            "or panel-layout defects remain at the intended 180-mm width.\n\n"
        )

        handle.write("## Scientific integrity\n\n")
        handle.write(
            "Figure 5 remains restricted to steroid, cholesterol and lipid "
            "biology; Figure 6 retains adipokine, insulin, carbon, amino-acid, "
            "nucleotide, NAD and redox modules; Figure 7 remains "
            "complement-specific; and Figure 8 preserves the integrated "
            "endocrine-metabolic-immune synthesis and evidence boundaries.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "The freeze is non-destructive. It copies accepted U27B2E2D "
            "outputs and provenance records without changing scientific "
            "values, displayed modules, pathway membership, source locks or "
            "manuscript text.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "figures_frozen": 4,
        "exports_frozen": observed_exports,
        "panel_crops_frozen": observed_panel_crops,
        "contact_sheets_frozen": contact_sheets_frozen,
        "visual_audit_pass": all_visual_pass,
        "scientific_values_changed": False,
        "displayed_modules_changed": False,
        "pathway_membership_changed": False,
        "source_locks_changed": False,
        "manuscript_modified": False,
    }
    (
        frozen_results
        / "UTI_HostOmics_U27B2E2E_run_manifest.json"
    ).write_text(
        json.dumps(run_manifest, indent=2),
        encoding="utf-8",
    )

    log("Figures 5-8 visually approved and frozen.")
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
        print(f"[U27B2E2E] ERROR: {exc}", file=sys.stderr)
        raise
