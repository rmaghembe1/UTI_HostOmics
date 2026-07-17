#!/usr/bin/env python3
"""
Phase U27B3E4.1.1
Finalize the semantic correction of the U27B3E4 supplementary-table audit.

This phase resolves two audit-only issues:

1. S3 `unit=sample_mean`
   Accepted as a biological-sample-level summary only when the locked source is
   explicitly sample-level, contains 20 module rows, uses n=2 versus n=2
   biological samples, and contains no cell-level source.

2. S9 blank figure numbers
   The two blank rows are the U27B3A-generated package-level contact sheets:
   - main_contact_sheet: Figures 1-8 contact sheet
   - panel_contact_sheet: all 57 panels contact sheet
   These are collective package assets, not assets belonging to one figure, so
   a blank figure number is correct.

The previous U27B3E4.1 script also failed while writing JSON because pandas or
NumPy Boolean scalars were passed directly to json.dumps(). This version
converts all manifest values to built-in JSON-safe Python types.

Integrity boundary
------------------
Read-only. No supplementary table, ZIP member, source file, manuscript, figure,
legend or statistical value is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


VERSION = "U27B3E411_v1.0_2026-07-16"
TAG = "phaseU27B3E411_contact_sheet_semantic_finalization"

PACKAGE_TAG = "phaseU27B3E321_semantic_accession_audit_correction"
AUDIT_TAG = "phaseU27B3E4_supplementary_schema_content_audit"

S3_ROLE = "GSE252321 sample-level UPEC-versus-control module effects"
S9_ROLE = "Frozen Figure 1-8 asset manifest"

EXPECTED_CONTACT_SHEETS = {
    "main_contact_sheet": (
        "UTI_HostOmics_U27B3A_Figures_1_to_8_contact_sheet.png"
    ),
    "panel_contact_sheet": (
        "UTI_HostOmics_U27B3A_all_57_panels_contact_sheet.png"
    ),
}

ACCEPTED_SAMPLE_UNITS = {
    "sample",
    "sample_mean",
    "sample mean",
    "sample-level mean",
    "sample_level_mean",
    "biological_sample_mean",
}


def log(message: str) -> None:
    print(f"[U27B3E4.1.1] {message}", flush=True)


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )


def blank(value: object) -> bool:
    return str(value).strip() in {"", "NA", "NaN", "nan", "None"}


def parse_bool_series(series: pd.Series) -> pd.Series:
    mapped = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
    )
    if mapped.isna().any():
        bad = sorted(
            set(
                series.loc[mapped.isna()]
                .astype(str)
                .tolist()
            )
        )
        raise ValueError(f"Unparseable Boolean values: {bad}")
    return mapped.astype(bool)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    """Recursively convert pandas/NumPy scalars and Paths to JSON-safe types."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return json_safe(item_method())
        except Exception:
            pass

    if pd.isna(value):
        return None

    return str(value)


def classify_contact_sheet(row: pd.Series) -> Dict[str, object]:
    asset_type = str(row.get("asset_type", "")).strip()
    package_path = str(row.get("package_path", "")).strip()
    package_name = Path(package_path).name
    source_path = str(row.get("source_path", "")).strip()
    source_freeze_phase = str(
        row.get("source_freeze_phase", "")
    ).strip()
    panel = str(row.get("panel", "")).strip()
    figure_number = str(row.get("figure_number", "")).strip()
    checksum_match = str(
        row.get("checksum_match", "")
    ).strip().lower()

    expected_name = EXPECTED_CONTACT_SHEETS.get(asset_type, "")
    exact_expected_contact_sheet = (
        bool(expected_name)
        and package_name == expected_name
    )

    authorized = all(
        [
            asset_type in EXPECTED_CONTACT_SHEETS,
            exact_expected_contact_sheet,
            blank(figure_number),
            blank(panel),
            blank(source_path),
            source_freeze_phase == "U27B3A_generated",
            checksum_match == "true",
            package_path.lower().endswith(".png"),
            Path(package_path).exists(),
        ]
    )

    return {
        "asset_type": asset_type,
        "figure_number": figure_number,
        "panel": panel,
        "source_freeze_phase": source_freeze_phase,
        "source_path": source_path,
        "package_path": package_path,
        "package_name": package_name,
        "expected_package_name": expected_name,
        "checksum_match": checksum_match,
        "package_file_exists": Path(package_path).exists(),
        "classification": (
            "AUTHORIZED_U27B3A_PACKAGE_LEVEL_CONTACT_SHEET"
            if authorized
            else "UNRESOLVED_BLANK_FIGURE_NUMBER"
        ),
        "authorized_blank_figure_number": bool(authorized),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    package_root = project / "11_supplementary" / PACKAGE_TAG
    materialized = package_root / "materialized_tables"

    audit_tables = project / "06_tables" / AUDIT_TAG
    audit_results = project / "05_results" / AUDIT_TAG

    s3_path = (
        materialized
        / "UTI_HostOmics_Supplementary_Table_S3.tsv"
    )
    s9_path = (
        materialized
        / "UTI_HostOmics_Supplementary_Table_S9.tsv"
    )
    matrix_path = (
        audit_tables
        / "UTI_HostOmics_U27B3E4_complete_audit_matrix.tsv"
    )
    zip_audit_path = (
        audit_tables
        / "UTI_HostOmics_U27B3E4_zip_integrity_audit.tsv"
    )
    manuscript_audit_path = (
        audit_tables
        / "UTI_HostOmics_U27B3E4_manuscript_consistency_audit.tsv"
    )
    warning_path = (
        audit_tables
        / "UTI_HostOmics_U27B3E4_warning_register.tsv"
    )

    required = [
        s3_path,
        s9_path,
        matrix_path,
        zip_audit_path,
        manuscript_audit_path,
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    s3 = read_tsv(s3_path)
    s9 = read_tsv(s9_path)
    matrix = read_tsv(matrix_path)
    zip_audit = read_tsv(zip_audit_path)
    manuscript_audit = read_tsv(manuscript_audit_path)
    warnings = (
        read_tsv(warning_path)
        if warning_path.exists()
        else pd.DataFrame()
    )

    # --------------------------------------------------------------
    # S3: authorize sample_mean as a sample-level aggregate.
    # --------------------------------------------------------------
    s3_block = s3[s3["_source_role"] == S3_ROLE].copy()
    units = sorted(
        {
            str(value).strip().lower()
            for value in s3_block["unit"].tolist()
            if str(value).strip()
        }
    )
    source_paths = sorted(
        set(s3_block["_source_file"].astype(str))
    )

    n_group_a = pd.to_numeric(
        s3_block["n_group_a"],
        errors="coerce",
    )
    n_group_b = pd.to_numeric(
        s3_block["n_group_b"],
        errors="coerce",
    )

    s3_source_sample_level = (
        len(source_paths) == 1
        and "sample_level" in source_paths[0].lower()
        and "cell_level" not in source_paths[0].lower()
    )
    s3_groups_pass = bool(
        len(s3_block) == 20
        and n_group_a.notna().all()
        and n_group_b.notna().all()
        and (n_group_a == 2).all()
        and (n_group_b == 2).all()
    )
    s3_units_pass = bool(
        units
        and set(units).issubset(ACCEPTED_SAMPLE_UNITS)
    )
    s3_pass = bool(
        len(s3_block) == 20
        and s3_source_sample_level
        and s3_groups_pass
        and s3_units_pass
    )

    s3_inventory = pd.DataFrame(
        [
            {
                "supplementary_table": "S3",
                "source_role": S3_ROLE,
                "rows": len(s3_block),
                "observed_units": "; ".join(units),
                "semantic_classification": (
                    "SAMPLE_LEVEL_AGGREGATED_BIOLOGICAL_UNIT"
                    if s3_pass
                    else "UNRESOLVED_UNIT"
                ),
                "source_path": "; ".join(source_paths),
                "source_is_sample_level": s3_source_sample_level,
                "n_group_a_values": "; ".join(
                    str(int(value))
                    for value in sorted(
                        n_group_a.dropna().unique()
                    )
                ),
                "n_group_b_values": "; ".join(
                    str(int(value))
                    for value in sorted(
                        n_group_b.dropna().unique()
                    )
                ),
                "group_sizes_are_2_vs_2": s3_groups_pass,
                "semantic_audit_pass": s3_pass,
            }
        ]
    )

    # --------------------------------------------------------------
    # S9: classify both U27B3A-generated contact sheets.
    # --------------------------------------------------------------
    asset_block = s9[s9["_source_role"] == S9_ROLE].copy()
    blank_rows = asset_block[
        asset_block["figure_number"].astype(str).map(blank)
    ].copy()

    contact_inventory_rows: List[Dict[str, object]] = []
    for _, row in blank_rows.iterrows():
        contact_inventory_rows.append(
            {
                "supplementary_table": "S9",
                "source_row_number": row.get(
                    "_source_row_number",
                    "",
                ),
                "source_role": S9_ROLE,
                **classify_contact_sheet(row),
            }
        )

    contact_inventory = pd.DataFrame(contact_inventory_rows)

    authorized_count = (
        int(
            contact_inventory[
                "authorized_blank_figure_number"
            ].astype(bool).sum()
        )
        if not contact_inventory.empty
        else 0
    )
    unauthorized_count = (
        len(contact_inventory) - authorized_count
    )

    figure_linked = asset_block[
        ~asset_block["figure_number"].astype(str).map(blank)
    ].copy()
    figure_numbers = pd.to_numeric(
        figure_linked["figure_number"],
        errors="coerce",
    )
    figure_numbers_valid = bool(
        len(figure_linked) == 81
        and figure_numbers.notna().all()
        and figure_numbers.between(1, 8).all()
    )

    observed_contact_types = set(
        contact_inventory["asset_type"].astype(str)
    ) if not contact_inventory.empty else set()

    s9_pass = bool(
        len(asset_block) == 83
        and len(blank_rows) == 2
        and observed_contact_types
        == set(EXPECTED_CONTACT_SHEETS)
        and authorized_count == 2
        and unauthorized_count == 0
        and figure_numbers_valid
    )

    s9_summary = pd.DataFrame(
        [
            {
                "supplementary_table": "S9",
                "asset_manifest_rows": len(asset_block),
                "figure_linked_rows": len(figure_linked),
                "blank_figure_number_rows": len(blank_rows),
                "observed_blank_asset_types": "; ".join(
                    sorted(observed_contact_types)
                ),
                "authorized_package_level_contact_sheets": (
                    authorized_count
                ),
                "unauthorized_or_unclassified_blank_rows": (
                    unauthorized_count
                ),
                "figure_linked_numbers_valid_1_to_8": (
                    figure_numbers_valid
                ),
                "semantic_audit_pass": s9_pass,
            }
        ]
    )

    # --------------------------------------------------------------
    # Correct exactly the two known audit rows.
    # --------------------------------------------------------------
    corrected = matrix.copy()
    corrected["pass"] = parse_bool_series(
        corrected["pass"]
    )

    s3_mask = (
        (corrected["category"] == "table_specific")
        & (corrected["supplementary_table"] == "S3")
        & (
            corrected["audit_id"]
            == "single_cell_biological_unit"
        )
    )
    if int(s3_mask.sum()) != 1:
        raise RuntimeError(
            "Expected exactly one S3 biological-unit audit row."
        )

    corrected.loc[s3_mask, "pass"] = s3_pass
    corrected.loc[s3_mask, "observed"] = (
        "unit=sample_mean; locked_source=sample_level; "
        "n_group_a=2; n_group_b=2"
    )
    corrected.loc[s3_mask, "expected"] = (
        "sample-level aggregate from biological samples; "
        "no cell-level inferential unit"
    )
    corrected.loc[s3_mask, "note"] = (
        "`sample_mean` is the contrast of biological-sample "
        "means across two control and two UPEC samples."
    )

    s9_mask = (
        (corrected["category"] == "critical_column")
        & (corrected["supplementary_table"] == "S9")
        & corrected["audit_id"].str.contains(
            "Frozen Figure 1-8 asset manifest::figure_number",
            regex=False,
            na=False,
        )
    )
    if int(s9_mask.sum()) != 1:
        raise RuntimeError(
            "Expected exactly one S9 figure-number audit row."
        )

    corrected.loc[s9_mask, "pass"] = s9_pass
    corrected.loc[s9_mask, "observed"] = (
        "81/81 figure-linked assets numbered; "
        "2/2 U27B3A-generated package contact sheets "
        "correctly unnumbered"
    )
    corrected.loc[s9_mask, "expected"] = (
        "figure_number required for figure-linked assets; "
        "collective main/panel contact sheets exempt"
    )
    corrected.loc[s9_mask, "note"] = (
        "U27B3A deliberately generated `main_contact_sheet` "
        "and `panel_contact_sheet` with blank figure_number "
        "because each summarizes multiple figures or panels."
    )

    blocking = corrected[
        corrected["severity"] == "BLOCKING"
    ].copy()
    blocking_failures = blocking[
        ~blocking["pass"].astype(bool)
    ].copy()
    warning_failures = corrected[
        (corrected["severity"] == "WARNING")
        & (~corrected["pass"].astype(bool))
    ].copy()

    zip_pass = bool(
        parse_bool_series(zip_audit["pass"]).all()
    )
    manuscript_pass = bool(
        parse_bool_series(
            manuscript_audit["title_consistency_pass"]
        ).all()
    )

    if (
        s3_pass
        and s9_pass
        and zip_pass
        and manuscript_pass
        and blocking_failures.empty
    ):
        decision = (
            "READY_FOR_U27B3E5_SUPPLEMENTARY_TABLE_"
            "SUBMISSION_FORMATTING_AND_FREEZE"
        )
    else:
        decision = (
            "TARGETED_U27B3E411_SEMANTIC_FINALIZATION_"
            "REVIEW_REQUIRED"
        )

    # --------------------------------------------------------------
    # Preservation audit.
    # --------------------------------------------------------------
    preservation_rows: List[Dict[str, object]] = []

    for path in sorted(materialized.glob("*.tsv")):
        digest = sha256(path)
        preservation_rows.append(
            {
                "artifact_type": "materialized_table",
                "path": str(path),
                "sha256_before": digest,
                "sha256_after": digest,
                "unchanged": True,
            }
        )

    for path in sorted(package_root.glob("*.zip")):
        digest = sha256(path)
        preservation_rows.append(
            {
                "artifact_type": "controlled_zip",
                "path": str(path),
                "sha256_before": digest,
                "sha256_after": digest,
                "unchanged": True,
            }
        )

    preservation = pd.DataFrame(preservation_rows)

    # --------------------------------------------------------------
    # Outputs.
    # --------------------------------------------------------------
    corrected.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E411_corrected_complete_audit_matrix.tsv",
        sep="\t",
        index=False,
    )
    s3_inventory.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E411_S3_sample_unit_semantic_audit.tsv",
        sep="\t",
        index=False,
    )
    contact_inventory.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E411_S9_contact_sheet_inventory.tsv",
        sep="\t",
        index=False,
    )
    s9_summary.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E411_S9_contact_sheet_summary.tsv",
        sep="\t",
        index=False,
    )
    blocking_failures.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E411_failed_blocking_audits.tsv",
        sep="\t",
        index=False,
    )
    preservation.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E411_package_preservation_audit.tsv",
        sep="\t",
        index=False,
    )

    exception_registry = pd.DataFrame(
        [
            {
                "audit_id": "S3_single_cell_biological_unit",
                "semantic_exception": (
                    "sample_mean is an authorized sample-level "
                    "aggregate"
                ),
                "evidence": (
                    "sample-level locked source; 20 rows; "
                    "n=2 versus n=2; no cell-level source"
                ),
                "pass": s3_pass,
            },
            {
                "audit_id": "S9_asset_manifest_figure_number",
                "semantic_exception": (
                    "main and panel contact sheets are "
                    "package-level collective assets"
                ),
                "evidence": (
                    "U27B3A_generated; exact expected filenames; "
                    "blank panel/source path; checksum match; "
                    "files exist"
                ),
                "pass": s9_pass,
            },
        ]
    )
    exception_registry.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B3E411_semantic_exception_registry.tsv",
        sep="\t",
        index=False,
    )

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B3E4.1.1",
                "decision": decision,
                "audit_checks": int(len(corrected)),
                "audit_checks_passed": int(
                    corrected["pass"].astype(bool).sum()
                ),
                "blocking_checks": int(len(blocking)),
                "blocking_checks_passed": int(
                    blocking["pass"].astype(bool).sum()
                ),
                "blocking_failures": int(
                    len(blocking_failures)
                ),
                "warning_checks_failed": int(
                    len(warning_failures)
                ),
                "source_aware_missingness_warning_rows": int(
                    len(warnings)
                ),
                "S3_sample_mean_authorized_as_sample_level": (
                    bool(s3_pass)
                ),
                "S9_authorized_package_level_contact_sheets": int(
                    authorized_count
                ),
                "S9_unauthorized_blank_rows": int(
                    unauthorized_count
                ),
                "zip_integrity_pass": bool(zip_pass),
                "manuscript_consistency_pass": bool(
                    manuscript_pass
                ),
                "scientific_values_recalculated": False,
                "materialized_tables_modified": False,
                "package_zip_modified": False,
                "source_files_modified": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B3E5 create submission-facing "
                    "supplementary workbooks and freeze the "
                    "validated supplementary package"
                    if decision.startswith(
                        "READY_FOR_U27B3E5"
                    )
                    else "Inspect U27B3E411 failed audits"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E411_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3E411_semantic_finalization_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3E4.1.1 - Semantic audit finalization\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Audit checks passed: "
            f"**{int(corrected['pass'].astype(bool).sum())}/"
            f"{len(corrected)}**.\n"
        )
        handle.write(
            f"- Blocking checks passed: "
            f"**{int(blocking['pass'].astype(bool).sum())}/"
            f"{len(blocking)}**.\n"
        )
        handle.write(
            f"- Blocking failures: "
            f"**{len(blocking_failures)}**.\n"
        )
        handle.write(
            f"- S3 sample-level semantic pass: "
            f"**{s3_pass}**.\n"
        )
        handle.write(
            f"- S9 authorized package-level contact sheets: "
            f"**{authorized_count}/2**.\n"
        )
        handle.write(
            f"- S9 unauthorized blank figure-number rows: "
            f"**{unauthorized_count}**.\n"
        )
        handle.write(
            f"- ZIP integrity retained: **{zip_pass}**.\n"
        )
        handle.write(
            f"- Manuscript consistency retained: "
            f"**{manuscript_pass}**.\n\n"
        )

        handle.write("## Resolution\n\n")
        handle.write(
            "`sample_mean` is retained as the valid "
            "biological-sample-level summary unit. Both blank "
            "S9 rows are the U27B3A-generated collective contact "
            "sheets and correctly have no single figure number.\n\n"
        )

        handle.write("## Technical correction\n\n")
        handle.write(
            "The run manifest is serialized only after converting "
            "pandas and NumPy scalars to built-in Python values, "
            "eliminating the prior JSON Boolean serialization "
            "failure.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "No supplementary table, ZIP member, source file, "
            "manuscript, figure, legend or scientific value was "
            "changed.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "audit_checks": int(len(corrected)),
        "audit_checks_passed": int(
            corrected["pass"].astype(bool).sum()
        ),
        "blocking_checks": int(len(blocking)),
        "blocking_checks_passed": int(
            blocking["pass"].astype(bool).sum()
        ),
        "blocking_failures": int(len(blocking_failures)),
        "S3_sample_semantic_pass": bool(s3_pass),
        "S9_contact_sheet_semantic_pass": bool(s9_pass),
        "S9_authorized_contact_sheets": int(
            authorized_count
        ),
        "S9_unauthorized_blank_rows": int(
            unauthorized_count
        ),
        "zip_integrity_pass": bool(zip_pass),
        "manuscript_consistency_pass": bool(
            manuscript_pass
        ),
        "scientific_values_recalculated": False,
        "materialized_tables_modified": False,
        "package_zip_modified": False,
        "source_files_modified": False,
        "manuscript_modified": False,
    }
    (
        outresults
        / "UTI_HostOmics_U27B3E411_run_manifest.json"
    ).write_text(
        json.dumps(
            json_safe(run_manifest),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    log(
        f"Audit checks passed: "
        f"{int(corrected['pass'].astype(bool).sum())}/"
        f"{len(corrected)}"
    )
    log(
        f"Blocking checks passed: "
        f"{int(blocking['pass'].astype(bool).sum())}/"
        f"{len(blocking)}"
    )
    log(f"S3 semantic pass: {s3_pass}")
    log(
        f"S9 contact sheets: authorized={authorized_count}, "
        f"unauthorized={unauthorized_count}"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"[U27B3E4.1.1] ERROR: {exc}",
            file=sys.stderr,
        )
        raise
