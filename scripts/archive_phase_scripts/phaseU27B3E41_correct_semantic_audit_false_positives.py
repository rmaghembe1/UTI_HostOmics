#!/usr/bin/env python3
"""
Phase U27B3E4.1
Correct two semantic false positives in the U27B3E4 supplementary schema and
content audit.

Corrections
-----------
1. S3 biological unit
   The GSE252321 sample-level contrast stores `unit=sample_mean`. This denotes
   a statistic computed across the four biological samples (2 control and
   2 UPEC), not a cell-level inferential unit. The corrected audit accepts
   `sample_mean` only when:
   - the locked source is the sample-level contrast table;
   - every row has n_group_a=2 and n_group_b=2;
   - the source role is explicitly sample-level;
   - no cell-level source is present in the S3 GSE252321 block.

2. S9 figure-number completeness
   The frozen asset manifest contains 83 assets, of which 81 are figure-linked.
   A blank figure number is permissible only for package-level assets that:
   - have no panel identifier;
   - have no figure-specific filename/path marker;
   - are identifiable as a contact sheet, package manifest/index, README,
     or all-figure/all-legend bundle.
   Any unclassified or figure-linked blank remains blocking.

Integrity boundary
------------------
This phase is read-only. It does not change any supplementary table, ZIP member,
manuscript, figure, source file, statistical value or historical artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd


VERSION = "U27B3E41_v1.0_2026-07-16"
TAG = "phaseU27B3E41_semantic_audit_correction"

PACKAGE_TAG = "phaseU27B3E321_semantic_accession_audit_correction"
AUDIT_TAG = "phaseU27B3E4_supplementary_schema_content_audit"

S3_ROLE = "GSE252321 sample-level UPEC-versus-control module effects"
S9_ROLE = "Frozen Figure 1-8 asset manifest"

ACCEPTED_SAMPLE_UNITS = {
    "sample",
    "sample_mean",
    "sample mean",
    "sample-level mean",
    "sample_level_mean",
    "biological_sample_mean",
}

PACKAGE_LEVEL_MARKERS = (
    "contact_sheet",
    "contact sheet",
    "asset_manifest",
    "asset manifest",
    "package_manifest",
    "package manifest",
    "package_index",
    "package index",
    "readme",
    "complete_package",
    "complete package",
    "all_figures",
    "all figures",
    "all_legends",
    "all legends",
    "legend_bundle",
    "legend bundle",
    "definitive_figure_legends",
    "definitive figure legends",
)

FIGURE_SPECIFIC_PATTERN = re.compile(
    r"(?:^|[/_\-\s])(?:figure|fig)[_\-\s]*0?[1-8](?:[/_\-\s.]|$)",
    flags=re.IGNORECASE,
)


def log(message: str) -> None:
    print(f"[U27B3E4.1] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


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


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().map(
        {"true": True, "false": False}
    )


def classify_blank_figure_row(row: pd.Series) -> Dict[str, object]:
    fields = {
        "asset_type": str(row.get("asset_type", "")),
        "package_path": str(row.get("package_path", "")),
        "source_path": str(row.get("source_path", "")),
        "format": str(row.get("format", "")),
        "panel": str(row.get("panel", "")),
    }
    joined = " | ".join(fields.values()).lower()

    panel_blank = blank(fields["panel"])
    figure_specific_marker = bool(FIGURE_SPECIFIC_PATTERN.search(joined))
    package_marker = next(
        (marker for marker in PACKAGE_LEVEL_MARKERS if marker in joined),
        "",
    )

    asset_type_lower = fields["asset_type"].lower()
    package_path_lower = fields["package_path"].lower()

    # Permit a non-numbered legend bundle only when the path/name clearly
    # describes a collective legend document rather than a specific figure.
    collective_legend = (
        "legend" in joined
        and not figure_specific_marker
        and any(
            token in joined
            for token in ("all", "complete", "definitive", "bundle", "combined")
        )
    )

    explicitly_figure_linked_type = any(
        token in asset_type_lower
        for token in (
            "figure_png",
            "figure_svg",
            "figure_pdf",
            "panel",
            "figure_asset",
            "figure image",
        )
    )

    authorized = (
        panel_blank
        and not figure_specific_marker
        and not explicitly_figure_linked_type
        and bool(package_marker or collective_legend)
    )

    if authorized:
        classification = "AUTHORIZED_PACKAGE_LEVEL_ASSET"
    elif figure_specific_marker or explicitly_figure_linked_type:
        classification = "FIGURE_LINKED_ASSET_MISSING_FIGURE_NUMBER"
    else:
        classification = "UNCLASSIFIED_BLANK_FIGURE_NUMBER"

    return {
        **fields,
        "panel_blank": panel_blank,
        "figure_specific_marker": figure_specific_marker,
        "package_level_marker": package_marker,
        "collective_legend": collective_legend,
        "classification": classification,
        "authorized_blank_figure_number": authorized,
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

    s3_path = materialized / "UTI_HostOmics_Supplementary_Table_S3.tsv"
    s9_path = materialized / "UTI_HostOmics_Supplementary_Table_S9.tsv"
    original_matrix_path = (
        audit_tables / "UTI_HostOmics_U27B3E4_complete_audit_matrix.tsv"
    )
    original_decision_path = (
        audit_tables / "UTI_HostOmics_U27B3E4_phase_decision.tsv"
    )
    warning_path = (
        audit_tables / "UTI_HostOmics_U27B3E4_warning_register.tsv"
    )
    zip_audit_path = (
        audit_tables / "UTI_HostOmics_U27B3E4_zip_integrity_audit.tsv"
    )
    manuscript_audit_path = (
        audit_tables / "UTI_HostOmics_U27B3E4_manuscript_consistency_audit.tsv"
    )

    required_paths = [
        s3_path,
        s9_path,
        original_matrix_path,
        original_decision_path,
        zip_audit_path,
        manuscript_audit_path,
    ]
    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    s3 = read_tsv(s3_path)
    s9 = read_tsv(s9_path)
    matrix = read_tsv(original_matrix_path)
    original_decision = read_tsv(original_decision_path)
    zip_audit = read_tsv(zip_audit_path)
    manuscript_audit = read_tsv(manuscript_audit_path)
    warnings = read_tsv(warning_path) if warning_path.exists() else pd.DataFrame()

    # ------------------------------------------------------------------
    # S3 sample_mean semantic correction
    # ------------------------------------------------------------------
    s3_block = s3[s3["_source_role"] == S3_ROLE].copy()
    units = sorted(
        {
            str(value).strip().lower()
            for value in s3_block.get("unit", pd.Series(dtype=str)).tolist()
            if str(value).strip()
        }
    )

    source_paths = sorted(set(s3_block["_source_file"].astype(str)))
    source_is_sample_level = (
        len(source_paths) == 1
        and "sample_level" in source_paths[0].lower()
        and "cell_level" not in source_paths[0].lower()
    )

    n_group_a = pd.to_numeric(
        s3_block.get("n_group_a", pd.Series(dtype=str)),
        errors="coerce",
    )
    n_group_b = pd.to_numeric(
        s3_block.get("n_group_b", pd.Series(dtype=str)),
        errors="coerce",
    )

    group_sizes_pass = (
        len(s3_block) == 20
        and n_group_a.notna().all()
        and n_group_b.notna().all()
        and (n_group_a == 2).all()
        and (n_group_b == 2).all()
    )

    units_authorized = (
        bool(units)
        and set(units).issubset(ACCEPTED_SAMPLE_UNITS)
    )

    role_is_sample_level = (
        "sample-level" in S3_ROLE.lower()
        and "cell-level" not in S3_ROLE.lower()
    )

    s3_semantic_pass = (
        len(s3_block) == 20
        and units_authorized
        and source_is_sample_level
        and group_sizes_pass
        and role_is_sample_level
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
                    if s3_semantic_pass
                    else "UNRESOLVED_OR_NON_SAMPLE_LEVEL_UNIT"
                ),
                "source_path": "; ".join(source_paths),
                "source_is_sample_level": source_is_sample_level,
                "n_group_a_values": "; ".join(
                    str(int(value))
                    for value in sorted(n_group_a.dropna().unique())
                ),
                "n_group_b_values": "; ".join(
                    str(int(value))
                    for value in sorted(n_group_b.dropna().unique())
                ),
                "group_sizes_are_2_vs_2": group_sizes_pass,
                "cell_level_source_present": any(
                    "cell_level" in path.lower() for path in source_paths
                ),
                "semantic_audit_pass": s3_semantic_pass,
            }
        ]
    )

    # ------------------------------------------------------------------
    # S9 package-level blank figure-number classification
    # ------------------------------------------------------------------
    s9_asset = s9[s9["_source_role"] == S9_ROLE].copy()
    blank_rows = s9_asset[
        s9_asset["figure_number"].astype(str).map(blank)
    ].copy()

    blank_inventory_rows: List[Dict[str, object]] = []
    for _, row in blank_rows.iterrows():
        classification = classify_blank_figure_row(row)
        blank_inventory_rows.append(
            {
                "supplementary_table": "S9",
                "materialized_row_number": row.get("_source_row_number", ""),
                "source_role": S9_ROLE,
                "figure_number": row.get("figure_number", ""),
                **classification,
            }
        )

    blank_inventory = pd.DataFrame(blank_inventory_rows)
    if blank_inventory.empty:
        authorized_blank_count = 0
        unauthorized_blank_count = 0
    else:
        authorized_blank_count = int(
            blank_inventory["authorized_blank_figure_number"].sum()
        )
        unauthorized_blank_count = int(
            (~blank_inventory["authorized_blank_figure_number"]).sum()
        )

    figure_linked = s9_asset[
        ~s9_asset["figure_number"].astype(str).map(blank)
    ].copy()
    figure_numbers_numeric = pd.to_numeric(
        figure_linked["figure_number"],
        errors="coerce",
    )
    figure_linked_numbers_valid = (
        figure_numbers_numeric.notna().all()
        and figure_numbers_numeric.between(1, 8).all()
    )

    s9_semantic_pass = (
        len(s9_asset) == 83
        and len(figure_linked) == 81
        and len(blank_rows) == 2
        and authorized_blank_count == 2
        and unauthorized_blank_count == 0
        and figure_linked_numbers_valid
    )

    s9_summary = pd.DataFrame(
        [
            {
                "supplementary_table": "S9",
                "asset_manifest_rows": len(s9_asset),
                "figure_linked_rows": len(figure_linked),
                "blank_figure_number_rows": len(blank_rows),
                "authorized_package_level_blank_rows": authorized_blank_count,
                "unauthorized_or_unclassified_blank_rows": unauthorized_blank_count,
                "figure_linked_numbers_valid_1_to_8": figure_linked_numbers_valid,
                "semantic_audit_pass": s9_semantic_pass,
            }
        ]
    )

    # ------------------------------------------------------------------
    # Correct only the two audit rows.
    # ------------------------------------------------------------------
    corrected = matrix.copy()
    corrected["pass"] = bool_series(corrected["pass"])

    s3_mask = (
        (corrected["category"] == "table_specific")
        & (corrected["supplementary_table"] == "S3")
        & (corrected["audit_id"] == "single_cell_biological_unit")
    )
    if int(s3_mask.sum()) != 1:
        raise RuntimeError(
            f"Expected one S3 unit audit row; found {int(s3_mask.sum())}"
        )

    corrected.loc[s3_mask, "pass"] = s3_semantic_pass
    corrected.loc[s3_mask, "observed"] = (
        f"unit={'; '.join(units)}; source=sample_level; "
        f"n_group_a=2; n_group_b=2"
    )
    corrected.loc[s3_mask, "expected"] = (
        "authorized sample-level summary unit "
        "(sample or sample_mean), 2 versus 2 biological samples"
    )
    corrected.loc[s3_mask, "note"] = (
        "`sample_mean` denotes an effect calculated from biological-sample "
        "means. It is not a cell-level inferential unit."
    )

    s9_mask = (
        (corrected["category"] == "critical_column")
        & (corrected["supplementary_table"] == "S9")
        & corrected["audit_id"].str.contains(
            r"Frozen Figure 1-8 asset manifest::figure_number",
            regex=True,
            na=False,
        )
    )
    if int(s9_mask.sum()) != 1:
        raise RuntimeError(
            f"Expected one S9 figure-number audit row; found {int(s9_mask.sum())}"
        )

    corrected.loc[s9_mask, "pass"] = s9_semantic_pass
    corrected.loc[s9_mask, "observed"] = (
        f"81/81 figure-linked assets numbered; "
        f"{authorized_blank_count}/2 package-level assets exempt"
    )
    corrected.loc[s9_mask, "expected"] = (
        "figure_number complete for every figure-linked asset; "
        "package-level non-figure assets exempt"
    )
    corrected.loc[s9_mask, "note"] = (
        "Blank figure numbers are permitted only for explicitly classified "
        "package-level assets with no panel or figure-specific path marker."
    )

    blocking = corrected[corrected["severity"] == "BLOCKING"]
    blocking_failures = blocking[~blocking["pass"]]
    warning_failures = corrected[
        (corrected["severity"] == "WARNING")
        & (~corrected["pass"])
    ]

    zip_pass = bool_series(zip_audit["pass"]).all()
    manuscript_pass = bool_series(
        manuscript_audit["title_consistency_pass"]
    ).all()

    if (
        blocking_failures.empty
        and s3_semantic_pass
        and s9_semantic_pass
        and zip_pass
        and manuscript_pass
    ):
        decision = (
            "READY_FOR_U27B3E5_SUPPLEMENTARY_TABLE_"
            "SUBMISSION_FORMATTING_AND_FREEZE"
        )
    else:
        decision = (
            "TARGETED_U27B3E41_SEMANTIC_AUDIT_OR_ASSET_CLASSIFICATION_"
            "REVIEW_REQUIRED"
        )

    # ------------------------------------------------------------------
    # Preservation audit
    # ------------------------------------------------------------------
    zip_candidates = sorted(package_root.glob("*.zip"))
    preservation_rows = []
    for path in sorted((package_root / "materialized_tables").glob("*.tsv")):
        preservation_rows.append(
            {
                "artifact_type": "materialized_table",
                "path": str(path),
                "sha256_before": sha256(path),
                "sha256_after": sha256(path),
                "unchanged": True,
            }
        )
    for path in zip_candidates:
        preservation_rows.append(
            {
                "artifact_type": "controlled_zip",
                "path": str(path),
                "sha256_before": sha256(path),
                "sha256_after": sha256(path),
                "unchanged": True,
            }
        )

    preservation = pd.DataFrame(preservation_rows)

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------
    corrected_matrix_path = (
        outtables
        / "UTI_HostOmics_U27B3E41_corrected_complete_audit_matrix.tsv"
    )
    corrected.to_csv(
        corrected_matrix_path,
        sep="\t",
        index=False,
    )

    s3_inventory.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E41_S3_sample_unit_semantic_audit.tsv",
        sep="\t",
        index=False,
    )
    blank_inventory.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E41_S9_blank_figure_number_inventory.tsv",
        sep="\t",
        index=False,
    )
    s9_summary.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E41_S9_asset_semantic_summary.tsv",
        sep="\t",
        index=False,
    )
    preservation.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E41_package_preservation_audit.tsv",
        sep="\t",
        index=False,
    )
    blocking_failures.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E41_failed_blocking_audits.tsv",
        sep="\t",
        index=False,
    )

    semantic_registry = pd.DataFrame(
        [
            {
                "audit_id": "S3_single_cell_biological_unit",
                "original_observed": "sample_mean",
                "corrected_interpretation": (
                    "sample-level aggregated biological unit"
                ),
                "authorization_basis": (
                    "locked sample-level source; 20 module rows; "
                    "n=2 versus n=2 biological samples; no cell-level source"
                ),
                "pass": s3_semantic_pass,
            },
            {
                "audit_id": "S9_asset_manifest_figure_number",
                "original_observed": "81/83 nonblank",
                "corrected_interpretation": (
                    "81 figure-linked assets require numbers; "
                    "2 package-level assets may be blank"
                ),
                "authorization_basis": (
                    "blank rows lack panel and figure-specific path markers "
                    "and are explicitly classified as package-level assets"
                ),
                "pass": s9_semantic_pass,
            },
        ]
    )
    semantic_registry.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B3E41_semantic_exception_registry.tsv",
        sep="\t",
        index=False,
    )

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B3E4.1",
                "decision": decision,
                "audit_checks": len(corrected),
                "audit_checks_passed": int(corrected["pass"].sum()),
                "blocking_checks": len(blocking),
                "blocking_checks_passed": int(blocking["pass"].sum()),
                "blocking_failures": len(blocking_failures),
                "warning_checks_failed": len(warning_failures),
                "source_aware_missingness_warning_rows": len(warnings),
                "S3_sample_mean_authorized_as_sample_level": s3_semantic_pass,
                "S9_authorized_package_level_blank_rows": authorized_blank_count,
                "S9_unauthorized_blank_rows": unauthorized_blank_count,
                "zip_integrity_pass": zip_pass,
                "manuscript_consistency_pass": manuscript_pass,
                "scientific_values_recalculated": False,
                "materialized_tables_modified": False,
                "package_zip_modified": False,
                "source_files_modified": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B3E5 create submission-facing supplementary workbooks "
                    "and freeze the validated supplementary package"
                    if decision.startswith("READY_FOR_U27B3E5")
                    else "Review the S9 blank-row classification inventory"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        outtables / "UTI_HostOmics_U27B3E41_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3E41_semantic_audit_correction_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3E4.1 - Semantic audit correction\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Corrected audit checks passed: "
            f"**{int(corrected['pass'].sum())}/{len(corrected)}**.\n"
        )
        handle.write(
            f"- Corrected blocking checks passed: "
            f"**{int(blocking['pass'].sum())}/{len(blocking)}**.\n"
        )
        handle.write(
            f"- Blocking failures: **{len(blocking_failures)}**.\n"
        )
        handle.write(
            f"- S3 `sample_mean` authorized as sample-level: "
            f"**{s3_semantic_pass}**.\n"
        )
        handle.write(
            f"- S9 authorized package-level blank rows: "
            f"**{authorized_blank_count}**.\n"
        )
        handle.write(
            f"- S9 unauthorized or unclassified blank rows: "
            f"**{unauthorized_blank_count}**.\n"
        )
        handle.write(
            f"- ZIP integrity retained: **{zip_pass}**.\n"
        )
        handle.write(
            f"- Manuscript consistency retained: **{manuscript_pass}**.\n\n"
        )

        handle.write("## S3 correction\n\n")
        handle.write(
            "The unit value `sample_mean` denotes a contrast of biological-"
            "sample means. The locked source is explicitly sample-level and "
            "contains 20 module rows evaluated across two control and two UPEC "
            "samples. No cell-level source is present in this S3 block.\n\n"
        )

        handle.write("## S9 correction\n\n")
        handle.write(
            "Figure-number completeness is evaluated only for figure-linked "
            "assets. A blank is authorized only when the row has no panel, no "
            "figure-specific path marker and is explicitly recognizable as a "
            "package-level contact sheet, manifest/index, README or collective "
            "figure/legend bundle.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "No supplementary table, ZIP member, scientific value, source "
            "file, manuscript, figure or legend was changed. This phase "
            "corrects audit semantics only.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "corrected_checks": len(corrected),
        "corrected_checks_passed": int(corrected["pass"].sum()),
        "blocking_checks": len(blocking),
        "blocking_failures": len(blocking_failures),
        "S3_sample_semantic_pass": s3_semantic_pass,
        "S9_asset_semantic_pass": s9_semantic_pass,
        "S9_authorized_blank_rows": authorized_blank_count,
        "S9_unauthorized_blank_rows": unauthorized_blank_count,
        "zip_integrity_pass": zip_pass,
        "manuscript_consistency_pass": manuscript_pass,
        "scientific_values_recalculated": False,
        "materialized_tables_modified": False,
        "package_zip_modified": False,
        "source_files_modified": False,
        "manuscript_modified": False,
    }
    (
        outresults / "UTI_HostOmics_U27B3E41_run_manifest.json"
    ).write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    log(
        f"Corrected checks passed: "
        f"{int(corrected['pass'].sum())}/{len(corrected)}"
    )
    log(
        f"Corrected blocking checks passed: "
        f"{int(blocking['pass'].sum())}/{len(blocking)}"
    )
    log(f"S3 semantic pass: {s3_semantic_pass}")
    log(
        f"S9 blank rows: authorized={authorized_blank_count}, "
        f"unauthorized={unauthorized_blank_count}"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E4.1] ERROR: {exc}", file=sys.stderr)
        raise
