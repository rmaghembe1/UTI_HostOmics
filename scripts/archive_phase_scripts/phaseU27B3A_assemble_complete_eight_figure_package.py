#!/usr/bin/env python3
"""
Phase U27B3A
Assemble the complete frozen eight-figure manuscript package.

Inputs
------
Figures 1-4:
    phaseU27B2C2E_final_figures_1_to_4_freeze

Figures 5-8:
    phaseU27B2E2E_final_figures_5_to_8_freeze

This phase:
1. verifies and copies all 24 PNG/SVG/PDF figure exports;
2. verifies and copies all 57 frozen panel crops;
3. verifies and copies all eight panel-level source-value tables;
4. combines the two visual-approval records;
5. preserves frozen source registries, asset manifests and build manifests;
6. builds a normalized figure-title and panel-title registry;
7. builds a legend-input registry linked to figure masters and source tables;
8. creates complete main-figure and panel contact sheets;
9. computes SHA256 checksums and verifies source/destination identity;
10. creates a portable ZIP package containing figures, tables and manifests.

No scientific values, figure content, panel architecture, source locks or
manuscript text are modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

try:
    from PIL import Image
except ImportError as exc:
    raise RuntimeError(
        "Pillow is required for contact-sheet assembly."
    ) from exc


VERSION = "U27B3A_v1.0_2026-07-16"
TAG = "phaseU27B3A_complete_eight_figure_package_assembly"

FREEZE_1_TO_4 = "phaseU27B2C2E_final_figures_1_to_4_freeze"
FREEZE_5_TO_8 = "phaseU27B2E2E_final_figures_5_to_8_freeze"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"

EXPECTED_FORMATS = ("png", "svg", "pdf")
EXPECTED_PANEL_COUNTS = {
    1: 6,
    2: 7,
    3: 8,
    4: 8,
    5: 7,
    6: 8,
    7: 7,
    8: 6,
}

FIGURE_TITLES = {
    1: (
        "Study architecture, datasets, contrasts and evidence hierarchy"
    ),
    2: (
        "Cross-dataset infection effects, recurrent cores and contextual "
        "comparators"
    ),
    3: (
        "Pregnancy, tissue and outcome-associated endocrine-metabolic-"
        "complement remodeling"
    ),
    4: (
        "Single-cell composition, immune states and cellular localization"
    ),
    5: (
        "Steroid, cholesterol and lipid-remodeling architecture"
    ),
    6: (
        "Adipokine, insulin and integrated immunometabolic remodeling"
    ),
    7: (
        "Complement branch and cellular architecture"
    ),
    8: (
        "Integrated endocrine-metabolic-immune model and evidence boundaries"
    ),
}


def log(message: str) -> None:
    print(f"[U27B3A] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def png_dimensions(path: Path) -> Tuple[Optional[int], Optional[int]]:
    if path.suffix.lower() != ".png":
        return None, None
    with Image.open(path) as image:
        return image.size


def source_identity(figure_number: int) -> Tuple[str, str]:
    if 1 <= figure_number <= 4:
        return FREEZE_1_TO_4, "U27B2C2E"
    if 5 <= figure_number <= 8:
        return FREEZE_5_TO_8, "U27B2E2E"
    raise ValueError(f"Unsupported figure number: {figure_number}")


def copy_verified(
    source: Path,
    destination: Path,
) -> Dict[str, object]:
    if not source.exists():
        raise FileNotFoundError(f"Required frozen asset not found: {source}")
    if source.stat().st_size <= 0:
        raise RuntimeError(f"Frozen asset is empty: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(source)
    shutil.copy2(source, destination)
    destination_hash = sha256(destination)

    if source_hash != destination_hash:
        raise RuntimeError(
            "Checksum mismatch after copy: "
            f"{source} -> {destination}"
        )

    width, height = png_dimensions(destination)

    return {
        "source_path": str(source),
        "package_path": str(destination),
        "format": destination.suffix.lower().lstrip("."),
        "size_bytes": destination.stat().st_size,
        "source_sha256": source_hash,
        "package_sha256": destination_hash,
        "checksum_match": True,
        "png_width_px": width,
        "png_height_px": height,
    }


def make_contact_sheet(
    paths: Sequence[Path],
    output: Path,
    columns: int,
    cell_width: int,
    padding: int = 28,
) -> None:
    if not paths:
        raise RuntimeError(
            f"Cannot build contact sheet without images: {output}"
        )

    images: List[Image.Image] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(
                f"Contact-sheet input not found: {path}"
            )
        image = Image.open(path).convert("RGB")
        ratio = cell_width / image.width
        resized = image.resize(
            (cell_width, max(1, int(image.height * ratio)))
        )
        images.append(resized)

    rows = math.ceil(len(images) / columns)
    row_heights: List[int] = []

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

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def first_existing_column(
    frame: pd.DataFrame,
    candidates: Sequence[str],
) -> Optional[str]:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None


def normalize_final_figure(value: object) -> str:
    text = str(value)
    if text.startswith("Figure_"):
        return text
    if text.isdigit():
        return f"Figure_{text}"
    return text


def infer_panel_title(
    row: pd.Series,
    source_column: Optional[str],
) -> str:
    if source_column is not None:
        value = row.get(source_column, "")
        if pd.notna(value) and str(value).strip():
            return str(value).strip()

    for candidate in (
        "scientific_message",
        "panel_content",
        "panel_description",
        "primary_message",
        "source_id",
    ):
        value = row.get(candidate, "")
        if pd.notna(value) and str(value).strip():
            return str(value).strip()

    return str(row.get("panel_key", "panel"))


def create_zip(
    package_roots: Dict[str, Path],
    output_zip: Path,
) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(
        output_zip,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for archive_root, package_root in package_roots.items():
            for path in sorted(package_root.rglob("*")):
                if not path.is_file():
                    continue
                if path.resolve() == output_zip.resolve():
                    continue
                archive.write(
                    path,
                    arcname=str(
                        Path(archive_root)
                        / path.relative_to(package_root)
                    ),
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    outfig = project / "06_figures" / TAG
    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG

    panel_crop_dir = outfig / "panel_crops"
    provenance_dir = outmetadata / "frozen_provenance"

    for directory in (
        outfig,
        outtables,
        outmetadata,
        outresults,
        panel_crop_dir,
        provenance_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    asset_rows: List[Dict[str, object]] = []
    main_pngs: List[Path] = []
    panel_pngs: List[Path] = []

    log("Assembling normalized Figures 1-8.")

    for figure_number in range(1, 9):
        freeze_tag, source_prefix = source_identity(figure_number)
        source_figure_dir = project / "06_figures" / freeze_tag

        for extension in EXPECTED_FORMATS:
            source = (
                source_figure_dir
                / f"UTI_HostOmics_{source_prefix}_Figure_"
                f"{figure_number}.{extension}"
            )
            destination = (
                outfig
                / f"UTI_HostOmics_U27B3A_Figure_"
                f"{figure_number}.{extension}"
            )

            record = copy_verified(source, destination)
            record.update(
                {
                    "asset_type": "main_figure",
                    "figure_number": figure_number,
                    "panel": "",
                    "source_freeze_phase": freeze_tag,
                }
            )
            asset_rows.append(record)

            if extension == "png":
                main_pngs.append(destination)

        for index in range(EXPECTED_PANEL_COUNTS[figure_number]):
            panel = chr(ord("A") + index)
            source = (
                source_figure_dir
                / "panel_crops"
                / f"UTI_HostOmics_{source_prefix}_Figure_"
                f"{figure_number}_panel_{panel}.png"
            )
            destination = (
                panel_crop_dir
                / f"UTI_HostOmics_U27B3A_Figure_"
                f"{figure_number}_panel_{panel}.png"
            )

            record = copy_verified(source, destination)
            record.update(
                {
                    "asset_type": "panel_crop",
                    "figure_number": figure_number,
                    "panel": panel,
                    "source_freeze_phase": freeze_tag,
                }
            )
            asset_rows.append(record)
            panel_pngs.append(destination)

    # Copy all eight source-value tables.
    source_value_rows: List[Dict[str, object]] = []
    source_value_paths: Dict[int, Path] = {}

    for figure_number in range(1, 9):
        freeze_tag, source_prefix = source_identity(figure_number)
        source = (
            project
            / "06_tables"
            / freeze_tag
            / f"UTI_HostOmics_{source_prefix}_Figure_"
            f"{figure_number}_source_values.tsv"
        )
        destination = (
            outtables
            / f"UTI_HostOmics_U27B3A_Figure_"
            f"{figure_number}_source_values.tsv"
        )

        record = copy_verified(source, destination)
        record.update(
            {
                "figure_number": figure_number,
                "source_freeze_phase": freeze_tag,
            }
        )
        source_value_rows.append(record)
        source_value_paths[figure_number] = destination

    source_value_manifest = pd.DataFrame(source_value_rows)
    source_value_manifest.to_csv(
        outtables
        / "UTI_HostOmics_U27B3A_source_value_table_manifest.tsv",
        sep="\t",
        index=False,
    )

    # Combine visual-approval records.
    approval_frames: List[pd.DataFrame] = []

    for freeze_tag, source_prefix in (
        (FREEZE_1_TO_4, "U27B2C2E"),
        (FREEZE_5_TO_8, "U27B2E2E"),
    ):
        path = (
            project
            / "06_tables"
            / freeze_tag
            / f"UTI_HostOmics_{source_prefix}_visual_approval_record.tsv"
        )
        if not path.exists():
            raise FileNotFoundError(
                f"Visual approval record not found: {path}"
            )
        frame = pd.read_csv(path, sep="\t", low_memory=False)
        frame["source_freeze_phase"] = freeze_tag
        approval_frames.append(frame)

    combined_approval = pd.concat(
        approval_frames,
        ignore_index=True,
        sort=False,
    )
    combined_approval.to_csv(
        outtables
        / "UTI_HostOmics_U27B3A_combined_visual_approval_record.tsv",
        sep="\t",
        index=False,
    )

    # Preserve key frozen provenance files.
    provenance_specs = [
        (
            project
            / "03_metadata"
            / FREEZE_1_TO_4
            / "UTI_HostOmics_U27B2C2E_frozen_asset_manifest.tsv",
            "Figures_1_to_4_frozen_asset_manifest.tsv",
        ),
        (
            project
            / "03_metadata"
            / FREEZE_5_TO_8
            / "UTI_HostOmics_U27B2E2E_frozen_asset_manifest.tsv",
            "Figures_5_to_8_frozen_asset_manifest.tsv",
        ),
        (
            project
            / "03_metadata"
            / FREEZE_1_TO_4
            / "UTI_HostOmics_U27B2C2E_frozen_build_manifest.tsv",
            "Figures_1_to_4_frozen_build_manifest.tsv",
        ),
        (
            project
            / "03_metadata"
            / FREEZE_5_TO_8
            / "UTI_HostOmics_U27B2E2E_frozen_build_manifest.tsv",
            "Figures_5_to_8_frozen_build_manifest.tsv",
        ),
    ]

    preserved_provenance = 0
    for source, destination_name in provenance_specs:
        destination = provenance_dir / destination_name
        copy_verified(source, destination)
        preserved_provenance += 1

    # Preserve and validate the canonical frozen source registry.
    registry_candidates = [
        (
            project
            / "03_metadata"
            / FREEZE_5_TO_8
            / "UTI_HostOmics_U27B2E2E_frozen_source_registry.tsv"
        ),
        (
            project
            / "03_metadata"
            / FREEZE_1_TO_4
            / "UTI_HostOmics_U27B2C2E_frozen_source_registry.tsv"
        ),
    ]
    registry_sources = [
        path for path in registry_candidates if path.exists()
    ]
    if not registry_sources:
        raise FileNotFoundError(
            "No frozen source registry was found."
        )

    registry_hashes = {
        str(path): sha256(path)
        for path in registry_sources
    }
    registries_identical = (
        len(set(registry_hashes.values())) == 1
    )

    canonical_registry_source = registry_sources[0]
    canonical_registry_destination = (
        outmetadata
        / "UTI_HostOmics_U27B3A_frozen_source_registry.tsv"
    )
    copy_verified(
        canonical_registry_source,
        canonical_registry_destination,
    )

    pd.DataFrame(
        [
            {
                "registry_path": path,
                "sha256": digest,
                "all_available_registries_identical": registries_identical,
            }
            for path, digest in registry_hashes.items()
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B3A_source_registry_identity_audit.tsv",
        sep="\t",
        index=False,
    )

    # Build the complete title and panel registry.
    panel_map_path = (
        project
        / "03_metadata"
        / ARCH_TAG
        / "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv"
    )
    if not panel_map_path.exists():
        raise FileNotFoundError(
            f"Frozen panel map not found: {panel_map_path}"
        )

    panel_map = pd.read_csv(
        panel_map_path,
        sep="\t",
        low_memory=False,
    )
    panel_map["final_figure"] = panel_map["final_figure"].map(
        normalize_final_figure
    )
    panel_map = panel_map[
        panel_map["final_figure"].isin(
            [f"Figure_{number}" for number in range(1, 9)]
        )
    ].copy()

    panel_title_source_column = first_existing_column(
        panel_map,
        (
            "panel_title",
            "panel_heading",
            "panel_name",
            "panel_description",
            "panel_content",
            "scientific_message",
            "primary_message",
        ),
    )

    panel_map["figure_number"] = (
        panel_map["final_figure"]
        .astype(str)
        .str.extract(r"(\d+)", expand=False)
        .astype(int)
    )
    panel_map["figure_title"] = panel_map["figure_number"].map(
        FIGURE_TITLES
    )
    panel_map["panel_title"] = panel_map.apply(
        lambda row: infer_panel_title(
            row,
            panel_title_source_column,
        ),
        axis=1,
    )
    panel_map["panel_title_source_column"] = (
        panel_title_source_column
        if panel_title_source_column is not None
        else "fallback"
    )
    panel_map["figure_png"] = panel_map["figure_number"].map(
        lambda number: str(
            outfig
            / f"UTI_HostOmics_U27B3A_Figure_{number}.png"
        )
    )
    panel_map["figure_svg"] = panel_map["figure_number"].map(
        lambda number: str(
            outfig
            / f"UTI_HostOmics_U27B3A_Figure_{number}.svg"
        )
    )
    panel_map["figure_pdf"] = panel_map["figure_number"].map(
        lambda number: str(
            outfig
            / f"UTI_HostOmics_U27B3A_Figure_{number}.pdf"
        )
    )
    panel_map["source_value_table"] = panel_map["figure_number"].map(
        lambda number: str(source_value_paths[number])
    )
    panel_map["panel_crop"] = panel_map.apply(
        lambda row: str(
            panel_crop_dir
            / f"UTI_HostOmics_U27B3A_Figure_"
            f"{row['figure_number']}_panel_{row['panel']}.png"
        ),
        axis=1,
    )

    title_registry_columns = [
        column
        for column in (
            "figure_number",
            "final_figure",
            "figure_title",
            "panel",
            "panel_key",
            "panel_title",
            "panel_title_source_column",
            "source_id",
            "construction_mode",
            "primary_source",
            "figure_png",
            "figure_svg",
            "figure_pdf",
            "panel_crop",
            "source_value_table",
        )
        if column in panel_map.columns
    ]
    title_registry = panel_map[
        title_registry_columns
    ].sort_values(
        ["figure_number", "panel"]
    )
    title_registry.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B3A_figure_and_panel_title_registry.tsv",
        sep="\t",
        index=False,
    )

    # Legend-input registry preserves all panel-map fields plus package paths.
    legend_input_registry = panel_map.sort_values(
        ["figure_number", "panel"]
    )
    legend_input_registry.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B3A_legend_input_registry.tsv",
        sep="\t",
        index=False,
    )

    # Build contact sheets.
    full_contact_sheet = (
        outfig
        / "UTI_HostOmics_U27B3A_Figures_1_to_8_contact_sheet.png"
    )
    panel_contact_sheet = (
        outfig
        / "UTI_HostOmics_U27B3A_all_57_panels_contact_sheet.png"
    )

    make_contact_sheet(
        main_pngs,
        full_contact_sheet,
        columns=2,
        cell_width=1120,
    )
    make_contact_sheet(
        panel_pngs,
        panel_contact_sheet,
        columns=4,
        cell_width=690,
    )

    # Add generated contact sheets to the package manifest.
    for asset_type, path in (
        ("main_contact_sheet", full_contact_sheet),
        ("panel_contact_sheet", panel_contact_sheet),
    ):
        width, height = png_dimensions(path)
        digest = sha256(path)
        asset_rows.append(
            {
                "asset_type": asset_type,
                "figure_number": "",
                "panel": "",
                "source_freeze_phase": "U27B3A_generated",
                "source_path": "",
                "package_path": str(path),
                "format": "png",
                "size_bytes": path.stat().st_size,
                "source_sha256": "",
                "package_sha256": digest,
                "checksum_match": True,
                "png_width_px": width,
                "png_height_px": height,
            }
        )

    asset_manifest = pd.DataFrame(asset_rows)
    asset_manifest.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B3A_complete_asset_manifest.tsv",
        sep="\t",
        index=False,
    )

    # Main export audit.
    main_assets = asset_manifest[
        asset_manifest["asset_type"] == "main_figure"
    ].copy()
    export_audit = (
        main_assets.groupby(
            ["figure_number", "format"],
            as_index=False,
        )
        .agg(
            assets_present=("package_path", "count"),
            all_nonempty=("size_bytes", lambda values: bool((values > 0).all())),
            all_checksum_match=(
                "checksum_match",
                lambda values: bool(pd.Series(values).all()),
            ),
        )
    )
    export_audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B3A_main_figure_export_audit.tsv",
        sep="\t",
        index=False,
    )

    panel_count_audit_rows = []
    for figure_number, expected in EXPECTED_PANEL_COUNTS.items():
        observed = int(
            (
                (asset_manifest["asset_type"] == "panel_crop")
                & (
                    asset_manifest["figure_number"].astype(str)
                    == str(figure_number)
                )
            ).sum()
        )
        mapped = int(
            (
                title_registry["figure_number"] == figure_number
            ).sum()
        )
        panel_count_audit_rows.append(
            {
                "figure_number": figure_number,
                "expected_panel_crops": expected,
                "observed_panel_crops": observed,
                "panels_in_title_registry": mapped,
                "panel_count_pass": (
                    observed == expected
                    and mapped == expected
                ),
            }
        )

    panel_count_audit = pd.DataFrame(
        panel_count_audit_rows
    )
    panel_count_audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B3A_panel_count_audit.tsv",
        sep="\t",
        index=False,
    )

    # Build the portable ZIP after all package files exist.
    zip_path = (
        outfig
        / "UTI_HostOmics_U27B3A_complete_eight_figure_package.zip"
    )
    create_zip(
        package_roots={
            "figures": outfig,
            "tables": outtables,
            "metadata": outmetadata,
        },
        output_zip=zip_path,
    )
    zip_hash = sha256(zip_path)

    pd.DataFrame(
        [
            {
                "zip_path": str(zip_path),
                "size_bytes": zip_path.stat().st_size,
                "sha256": zip_hash,
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B3A_zip_package_audit.tsv",
        sep="\t",
        index=False,
    )

    expected_main_exports = 8 * 3
    observed_main_exports = int(
        (
            asset_manifest["asset_type"] == "main_figure"
        ).sum()
    )
    expected_panel_crops = sum(EXPECTED_PANEL_COUNTS.values())
    observed_panel_crops = int(
        (
            asset_manifest["asset_type"] == "panel_crop"
        ).sum()
    )
    source_value_tables = len(source_value_manifest)
    title_registry_panels = len(title_registry)

    visual_approval_pass = bool(
        len(combined_approval) == 8
        and (
            combined_approval["status"].astype(str) == "PASS"
        ).all()
    )
    checksums_pass = bool(
        asset_manifest["checksum_match"].astype(bool).all()
    )
    exports_pass = bool(
        observed_main_exports == expected_main_exports
        and len(export_audit) == expected_main_exports
        and export_audit["all_nonempty"].all()
        and export_audit["all_checksum_match"].all()
    )
    panel_counts_pass = bool(
        observed_panel_crops == expected_panel_crops
        and panel_count_audit["panel_count_pass"].all()
        and title_registry_panels == expected_panel_crops
    )
    source_tables_pass = source_value_tables == 8
    contact_sheets_pass = (
        full_contact_sheet.exists()
        and panel_contact_sheet.exists()
    )
    zip_pass = zip_path.exists() and zip_path.stat().st_size > 0
    source_registry_pass = (
        canonical_registry_destination.exists()
    )

    if (
        exports_pass
        and panel_counts_pass
        and source_tables_pass
        and visual_approval_pass
        and checksums_pass
        and contact_sheets_pass
        and zip_pass
        and source_registry_pass
        and preserved_provenance == 4
    ):
        decision = (
            "READY_FOR_U27B3B_DEFINITIVE_FIGURE_LEGEND_CONSTRUCTION"
        )
    else:
        decision = (
            "TARGETED_U27B3A_COMPLETE_PACKAGE_REPAIR_REQUIRED"
        )

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B3A",
                "decision": decision,
                "figures_expected": 8,
                "figures_packaged": 8,
                "main_exports_expected": expected_main_exports,
                "main_exports_packaged": observed_main_exports,
                "panel_crops_expected": expected_panel_crops,
                "panel_crops_packaged": observed_panel_crops,
                "panels_in_title_registry": title_registry_panels,
                "source_value_tables_expected": 8,
                "source_value_tables_packaged": source_value_tables,
                "visual_approval_records": len(combined_approval),
                "visual_approval_pass": visual_approval_pass,
                "all_checksums_match": checksums_pass,
                "source_registries_identical_when_both_present": (
                    registries_identical
                ),
                "complete_contact_sheet_present": (
                    full_contact_sheet.exists()
                ),
                "panel_contact_sheet_present": (
                    panel_contact_sheet.exists()
                ),
                "zip_package_present": zip_pass,
                "zip_package_sha256": zip_hash,
                "scientific_values_changed": False,
                "figure_content_changed": False,
                "panel_architecture_changed": False,
                "source_locks_changed": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B3B construct definitive legends for Figures 1-8 "
                    "from the frozen legend-input registry and source tables"
                    if decision.startswith("READY_FOR_U27B3B")
                    else "Repair incomplete package assets or metadata"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3A_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3A_complete_eight_figure_package_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3A - Complete eight-figure package assembly\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write("- Frozen figures packaged: **8/8**.\n")
        handle.write(
            f"- PNG/SVG/PDF exports packaged: "
            f"**{observed_main_exports}/{expected_main_exports}**.\n"
        )
        handle.write(
            f"- Panel crops packaged: "
            f"**{observed_panel_crops}/{expected_panel_crops}**.\n"
        )
        handle.write(
            f"- Source-value tables packaged: "
            f"**{source_value_tables}/8**.\n"
        )
        handle.write(
            f"- Visual approvals combined: "
            f"**{len(combined_approval)}/8**.\n"
        )
        handle.write(
            f"- Panel-title registry: "
            f"**{title_registry_panels}/{expected_panel_crops} panels**.\n"
        )
        handle.write(
            f"- Source/destination checksums: "
            f"**{'PASS' if checksums_pass else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Portable ZIP package: `{zip_path}`.\n"
        )
        handle.write(
            f"- ZIP SHA256: `{zip_hash}`.\n\n"
        )

        handle.write("## Package contents\n\n")
        handle.write(
            "- Eight normalized main figures in PNG, SVG and PDF.\n"
            "- Fifty-seven normalized panel crops.\n"
            "- Eight panel-level source-value tables.\n"
            "- Complete figure-title and panel-title registry.\n"
            "- Legend-input registry linked to masters and source tables.\n"
            "- Combined visual-approval record.\n"
            "- Frozen source registry and freeze provenance.\n"
            "- Complete eight-figure and 57-panel contact sheets.\n"
            "- Portable ZIP archive containing assembled figures, tables and metadata manifests.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "The assembly is non-destructive. It renames and copies the "
            "already frozen assets without changing scientific values, "
            "figure content, panel architecture, source locks or manuscript "
            "text. The assembled package is the sole input for U27B3B "
            "definitive figure-legend construction.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "figures_packaged": 8,
        "main_exports_packaged": observed_main_exports,
        "panel_crops_packaged": observed_panel_crops,
        "source_value_tables_packaged": source_value_tables,
        "visual_approval_records": len(combined_approval),
        "title_registry_panels": title_registry_panels,
        "all_checksums_match": checksums_pass,
        "zip_path": str(zip_path),
        "zip_sha256": zip_hash,
        "scientific_values_changed": False,
        "figure_content_changed": False,
        "panel_architecture_changed": False,
        "source_locks_changed": False,
        "manuscript_modified": False,
    }
    (
        outresults
        / "UTI_HostOmics_U27B3A_run_manifest.json"
    ).write_text(
        json.dumps(run_manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Figures packaged: 8/8")
    log(
        f"Main exports: "
        f"{observed_main_exports}/{expected_main_exports}"
    )
    log(
        f"Panel crops: "
        f"{observed_panel_crops}/{expected_panel_crops}"
    )
    log(f"Source-value tables: {source_value_tables}/8")
    log(f"Legend-registry panels: {title_registry_panels}/57")
    log(f"Checksums pass: {checksums_pass}")
    log(f"ZIP package: {zip_path}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3A] ERROR: {exc}", file=sys.stderr)
        raise
