#!/usr/bin/env python3
"""
Phase U27B3E3.2.1
Correct the semantic accession audit for the repaired supplementary package.

Scientific resolution
---------------------
The single GSE168600 occurrence in Supplementary Table S10 is not residual
contamination. It is an intentional validation-rule row documenting that
GSE168600 is the prohibited unrelated KLF5 skin/sphingolipid accession.

This phase:
1. preserves every U27B3E32 materialized table byte-for-byte;
2. distinguishes unauthorized accession use from an intentional prohibition
   rule in S10;
3. requires exactly one documented prohibited-accession row and zero
   unauthorized GSE168600 occurrences;
4. corrects the two false-negative audit rows;
5. creates a new controlled package, README, decision, report and ZIP;
6. verifies table checksums, ZIP integrity and package completeness.

No scientific value, source table, manuscript, figure, legend or historical
artifact is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


VERSION = "U27B3E321_v1.0_2026-07-16"
TAG = "phaseU27B3E321_semantic_accession_audit_correction"
SOURCE_TAG = "phaseU27B3E32_repaired_supplementary_rematerialization"

CORRECT_ACCESSION = "GSE186800"
PROHIBITED_ACCESSION = "GSE168600"

PROVENANCE_COLUMNS = {
    "_supplementary_table",
    "_table_title",
    "_source_order",
    "_source_role",
    "_source_file",
    "_source_relative_path",
    "_source_sha256",
    "_source_row_number",
}


def log(message: str) -> None:
    print(f"[U27B3E3.2.1] {message}", flush=True)


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


def all_text(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    return "\n".join(frame.astype(str).to_numpy().ravel().tolist())


def classify_prohibited_accession_rows(
    table_id: str,
    frame: pd.DataFrame,
) -> Tuple[List[Dict[str, object]], int, int]:
    records: List[Dict[str, object]] = []
    authorized = 0
    unauthorized = 0

    for row_index, row in frame.iterrows():
        matching_columns = [
            column
            for column in frame.columns
            if PROHIBITED_ACCESSION.lower()
            in str(row.get(column, "")).lower()
        ]
        if not matching_columns:
            continue

        source_role = str(row.get("_source_role", ""))
        rule_id = str(row.get("rule_id", ""))
        term = str(row.get("term", ""))
        rule = str(row.get("rule", ""))
        identity = str(row.get("scientific_identity", ""))

        is_authorized = bool(
            table_id == "S10"
            and source_role == "Future accession validation rules"
            and rule_id == "prohibited_unrelated_skin_accession"
            and term == PROHIBITED_ACCESSION
            and rule.lower() == "prohibited"
            and "klf5" in identity.lower()
            and "skin" in identity.lower()
        )

        if is_authorized:
            authorized += 1
            classification = "DOCUMENTED_PROHIBITION_RULE"
        else:
            unauthorized += 1
            classification = "UNAUTHORIZED_ACCESSION_USE"

        records.append(
            {
                "supplementary_table": table_id,
                "materialized_row_number": row_index + 1,
                "matching_columns": "; ".join(matching_columns),
                "source_role": source_role,
                "rule_id": rule_id,
                "term": term,
                "rule": rule,
                "scientific_identity": identity,
                "classification": classification,
                "authorized": is_authorized,
            }
        )

    return records, authorized, unauthorized


def make_zip(package_root: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(package_root.rglob("*")):
            if not path.is_file():
                continue
            if path.resolve() == zip_path.resolve():
                continue
            archive.write(
                path,
                arcname=str(path.relative_to(package_root)),
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    source_tables_dir = project / "06_tables" / SOURCE_TAG
    source_metadata_dir = project / "03_metadata" / SOURCE_TAG
    source_results_dir = project / "05_results" / SOURCE_TAG
    source_package_root = project / "11_supplementary" / SOURCE_TAG
    source_materialized_dir = source_package_root / "materialized_tables"

    required_source_files = [
        source_tables_dir / "UTI_HostOmics_U27B3E32_materialization_summary.tsv",
        source_tables_dir / "UTI_HostOmics_U27B3E32_source_manifest.tsv",
        source_tables_dir / "UTI_HostOmics_U27B3E32_materialized_schema_registry.tsv",
        source_tables_dir / "UTI_HostOmics_U27B3E32_schema_content_accession_audit.tsv",
        source_tables_dir / "UTI_HostOmics_U27B3E32_unclassified_source_map_rows.tsv",
        source_metadata_dir / "UTI_HostOmics_U27B3E32_corrected_source_lock_map.tsv",
        source_results_dir / "UTI_HostOmics_U27B3E32_repaired_materialization_report.md",
        source_package_root / "UTI_HostOmics_U27B3E32_supplementary_package_README.md",
    ]

    for path in required_source_files:
        if not path.exists():
            raise FileNotFoundError(f"Required U27B3E32 artifact missing: {path}")

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    package_root = project / "11_supplementary" / TAG
    materialized_dir = package_root / "materialized_tables"
    manifest_dir = package_root / "manifests"

    for directory in (
        outtables,
        outmetadata,
        outresults,
        materialized_dir,
        manifest_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    table_frames: Dict[str, pd.DataFrame] = {}
    preservation_rows: List[Dict[str, object]] = []
    accession_records: List[Dict[str, object]] = []
    authorized_total = 0
    unauthorized_total = 0

    for table_number in range(1, 11):
        table_id = f"S{table_number}"
        source_path = (
            source_materialized_dir
            / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
        )
        output_path = materialized_dir / source_path.name

        if not source_path.exists() or source_path.stat().st_size == 0:
            raise FileNotFoundError(f"Materialized source table missing: {source_path}")

        shutil.copy2(source_path, output_path)
        source_hash = sha256(source_path)
        output_hash = sha256(output_path)
        frame = read_tsv(output_path)
        table_frames[table_id] = frame

        records, authorized, unauthorized = classify_prohibited_accession_rows(
            table_id,
            frame,
        )
        accession_records.extend(records)
        authorized_total += authorized
        unauthorized_total += unauthorized

        preservation_rows.append(
            {
                "supplementary_table": table_id,
                "source_path": str(source_path),
                "source_sha256": source_hash,
                "corrected_package_path": str(output_path),
                "corrected_package_sha256": output_hash,
                "byte_identical": source_hash == output_hash,
                "rows": len(frame),
                "columns": len(frame.columns),
                "provenance_columns_complete": (
                    PROVENANCE_COLUMNS.issubset(set(frame.columns))
                ),
            }
        )

    preservation = pd.DataFrame(preservation_rows)
    accession_inventory = pd.DataFrame(accession_records)
    if accession_inventory.empty:
        accession_inventory = pd.DataFrame(
            columns=[
                "supplementary_table",
                "materialized_row_number",
                "matching_columns",
                "source_role",
                "rule_id",
                "term",
                "rule",
                "scientific_identity",
                "classification",
                "authorized",
            ]
        )

    preservation_path = (
        outtables
        / "UTI_HostOmics_U27B3E321_table_preservation_audit.tsv"
    )
    accession_inventory_path = (
        outtables
        / "UTI_HostOmics_U27B3E321_semantic_accession_inventory.tsv"
    )
    preservation.to_csv(preservation_path, sep="\t", index=False)
    accession_inventory.to_csv(
        accession_inventory_path,
        sep="\t",
        index=False,
    )

    source_audit = read_tsv(
        source_tables_dir
        / "UTI_HostOmics_U27B3E32_schema_content_accession_audit.tsv"
    )
    corrected_audit = source_audit.copy()

    mask_wrong = (
        (corrected_audit["supplementary_table"] == "S10")
        & (corrected_audit["audit_id"] == "wrong_accession_absent")
    )
    corrected_audit.loc[mask_wrong, "audit_id"] = (
        "unauthorized_wrong_accession_absent"
    )
    corrected_audit.loc[mask_wrong, "pass"] = str(unauthorized_total == 0)
    corrected_audit.loc[mask_wrong, "observed"] = str(unauthorized_total)
    corrected_audit.loc[mask_wrong, "expected"] = "0"

    mask_trace = (
        (corrected_audit["supplementary_table"] == "S10")
        & (
            corrected_audit["audit_id"]
            == "corrected_interpretation_traceability_sources"
        )
    )
    corrected_audit.loc[mask_trace, "pass"] = str(
        unauthorized_total == 0 and authorized_total == 1
    )
    corrected_audit.loc[mask_trace, "observed"] = (
        "corrected caveats; claim boundary; accession rules; "
        "preservation traceability; documented prohibited-accession rule=1"
    )
    corrected_audit.loc[mask_trace, "expected"] = (
        "corrected caveats; claim boundary; accession rules; preservation "
        "traceability; exactly one documented GSE168600 prohibition rule"
    )

    semantic_row = pd.DataFrame(
        [
            {
                "supplementary_table": "S10",
                "audit_id": "documented_prohibited_accession_rule",
                "pass": str(authorized_total == 1),
                "observed": str(authorized_total),
                "expected": "1",
            }
        ]
    )
    corrected_audit = pd.concat(
        [corrected_audit, semantic_row],
        ignore_index=True,
        sort=False,
    )

    corrected_audit["pass_bool"] = (
        corrected_audit["pass"].astype(str).str.lower() == "true"
    )
    all_audits_pass = bool(corrected_audit["pass_bool"].all())
    corrected_audit = corrected_audit.drop(columns=["pass_bool"])

    corrected_audit_path = (
        outtables
        / "UTI_HostOmics_U27B3E321_semantic_schema_content_accession_audit.tsv"
    )
    corrected_audit.to_csv(
        corrected_audit_path,
        sep="\t",
        index=False,
    )

    copied_manifest_files = [
        source_tables_dir / "UTI_HostOmics_U27B3E32_materialization_summary.tsv",
        source_tables_dir / "UTI_HostOmics_U27B3E32_source_manifest.tsv",
        source_tables_dir / "UTI_HostOmics_U27B3E32_materialized_schema_registry.tsv",
        source_tables_dir / "UTI_HostOmics_U27B3E32_unclassified_source_map_rows.tsv",
        source_metadata_dir / "UTI_HostOmics_U27B3E32_corrected_source_lock_map.tsv",
    ]

    for path in copied_manifest_files:
        destination = manifest_dir / path.name
        shutil.copy2(path, destination)

    shutil.copy2(preservation_path, manifest_dir / preservation_path.name)
    shutil.copy2(
        accession_inventory_path,
        manifest_dir / accession_inventory_path.name,
    )
    shutil.copy2(
        corrected_audit_path,
        manifest_dir / corrected_audit_path.name,
    )

    table_hashes_preserved = bool(preservation["byte_identical"].all())
    provenance_complete = bool(
        preservation["provenance_columns_complete"].all()
    )
    correct_accession_present = any(
        CORRECT_ACCESSION.lower() in all_text(frame).lower()
        for frame in table_frames.values()
    )

    decision = (
        "READY_FOR_U27B3E4_SUPPLEMENTARY_TABLE_SCHEMA_AND_CONTENT_AUDIT"
        if (
            table_hashes_preserved
            and provenance_complete
            and all_audits_pass
            and unauthorized_total == 0
            and authorized_total == 1
            and correct_accession_present
        )
        else "TARGETED_U27B3E321_SEMANTIC_ACCESSION_AUDIT_REPAIR_REQUIRED"
    )

    readme_path = (
        package_root
        / "UTI_HostOmics_U27B3E321_supplementary_package_README.md"
    )
    with readme_path.open("w", encoding="utf-8") as handle:
        handle.write("# UTI HostOmics Supplementary Tables S1-S10\n\n")
        handle.write(f"- Phase: `{VERSION}`\n")
        handle.write(
            f"- Correct recurrent-UTI accession: **{CORRECT_ACCESSION}**\n"
        )
        handle.write(
            f"- Unauthorized {PROHIBITED_ACCESSION} occurrences: "
            f"**{unauthorized_total}**\n"
        )
        handle.write(
            f"- Documented {PROHIBITED_ACCESSION} prohibition-rule rows: "
            f"**{authorized_total}**\n"
        )
        handle.write("- Scientific values recalculated: **No**\n")
        handle.write("- Materialized table bytes changed: **No**\n")
        handle.write("- Historical artifacts overwritten: **No**\n\n")
        handle.write("## Accession interpretation\n\n")
        handle.write(
            f"The sole `{PROHIBITED_ACCESSION}` string is intentionally retained "
            "in Supplementary Table S10 as a future validation rule identifying "
            "the unrelated KLF5 skin/sphingolipid dataset that must not be used "
            "in the UTI analysis. It is not a dataset assignment, effect row, "
            "figure label or manuscript claim.\n\n"
        )
        handle.write("## Provenance and biological-replicate boundary\n\n")
        handle.write(
            "All ten tables are byte-identical to U27B3E32 and retain row-level "
            "source paths, SHA256 checksums and source-row numbers. GSE252321 "
            "dataset-level effects use the four biological samples; cells are "
            "not treated as independent biological replicates.\n"
        )

    decision_path = (
        outtables / "UTI_HostOmics_U27B3E321_phase_decision.tsv"
    )
    report_path = (
        outresults
        / "UTI_HostOmics_U27B3E321_semantic_accession_audit_report.md"
    )

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B3E3.2.1",
                "decision": decision,
                "supplementary_tables_preserved": len(preservation),
                "table_sha256_matches": int(
                    preservation["byte_identical"].sum()
                ),
                "semantic_audits": len(corrected_audit),
                "semantic_audits_passed": int(
                    (
                        corrected_audit["pass"]
                        .astype(str)
                        .str.lower()
                        == "true"
                    ).sum()
                ),
                "unauthorized_GSE168600_occurrences": unauthorized_total,
                "documented_prohibition_rule_occurrences": authorized_total,
                "GSE186800_present": correct_accession_present,
                "package_zip_created": False,
                "scientific_values_recalculated": False,
                "materialized_table_bytes_modified": False,
                "source_files_modified": False,
                "historical_artifacts_overwritten": False,
                "next_phase": (
                    "U27B3E4 perform table-by-table schema, missingness, "
                    "content and manuscript-consistency audit"
                    if decision.startswith("READY_FOR_U27B3E4")
                    else "Inspect semantic accession classification"
                ),
            }
        ]
    )
    decision_frame.to_csv(decision_path, sep="\t", index=False)

    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3E3.2.1 - Semantic accession audit correction\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Tables preserved byte-for-byte: "
            f"**{int(preservation['byte_identical'].sum())}/10**.\n"
        )
        handle.write(
            f"- Corrected semantic audits passed: "
            f"**{int((corrected_audit['pass'].astype(str).str.lower() == 'true').sum())}/"
            f"{len(corrected_audit)}**.\n"
        )
        handle.write(
            f"- Unauthorized `{PROHIBITED_ACCESSION}` occurrences: "
            f"**{unauthorized_total}**.\n"
        )
        handle.write(
            f"- Authorized prohibition-rule occurrences: "
            f"**{authorized_total}**.\n\n"
        )
        handle.write("## Correction rationale\n\n")
        handle.write(
            "U27B3E32 used a literal global-string absence test. That rule "
            "incorrectly rejected the S10 validation row whose purpose is to "
            "document that GSE168600 is prohibited because it is an unrelated "
            "KLF5 skin/sphingolipid dataset. The corrected audit evaluates "
            "semantic context: dataset use remains prohibited, while the "
            "explicit prevention rule is retained.\n\n"
        )
        handle.write("## Integrity boundary\n\n")
        handle.write(
            "No materialized table, statistical result, source file, manuscript, "
            "figure or legend was changed. This phase corrects only the audit "
            "logic and controlled package metadata.\n"
        )

    shutil.copy2(decision_path, manifest_dir / decision_path.name)
    shutil.copy2(report_path, manifest_dir / report_path.name)

    zip_path = (
        package_root
        / "UTI_HostOmics_U27B3E321_Supplementary_Tables_S1-S10.zip"
    )
    make_zip(package_root, zip_path)

    zip_exists = zip_path.exists() and zip_path.stat().st_size > 0
    zip_test_error = ""
    if zip_exists:
        with zipfile.ZipFile(zip_path) as archive:
            failed_member = archive.testzip()
            if failed_member is not None:
                zip_test_error = failed_member

    zip_pass = zip_exists and not zip_test_error
    decision_frame.loc[0, "package_zip_created"] = zip_pass
    if not zip_pass:
        decision_frame.loc[0, "decision"] = (
            "TARGETED_U27B3E321_ZIP_CONSTRUCTION_REPAIR_REQUIRED"
        )
        decision_frame.loc[0, "next_phase"] = (
            "Inspect corrected package ZIP construction"
        )
    decision_frame.to_csv(decision_path, sep="\t", index=False)
    shutil.copy2(decision_path, manifest_dir / decision_path.name)

    # Rebuild so the ZIP contains the final decision state.
    make_zip(package_root, zip_path)
    zip_exists = zip_path.exists() and zip_path.stat().st_size > 0
    with zipfile.ZipFile(zip_path) as archive:
        failed_member = archive.testzip()
    zip_pass = zip_exists and failed_member is None

    zip_audit_path = (
        outtables / "UTI_HostOmics_U27B3E321_package_zip_audit.tsv"
    )
    pd.DataFrame(
        [
            {
                "zip_path": str(zip_path),
                "zip_exists": zip_exists,
                "zip_test_pass": zip_pass,
                "zip_size_bytes": zip_path.stat().st_size if zip_exists else 0,
                "zip_sha256": sha256(zip_path) if zip_exists else "",
                "materialized_tables": len(list(materialized_dir.glob("*.tsv"))),
                "manifest_files": len(list(manifest_dir.glob("*"))),
                "failed_zip_member": failed_member or "",
            }
        ]
    ).to_csv(zip_audit_path, sep="\t", index=False)

    manifest = {
        "version": VERSION,
        "decision": decision_frame.loc[0, "decision"],
        "table_hashes_preserved": table_hashes_preserved,
        "provenance_complete": provenance_complete,
        "semantic_audits": len(corrected_audit),
        "semantic_audits_passed": int(
            (corrected_audit["pass"].astype(str).str.lower() == "true").sum()
        ),
        "unauthorized_GSE168600_occurrences": unauthorized_total,
        "documented_prohibition_rule_occurrences": authorized_total,
        "GSE186800_present": correct_accession_present,
        "zip_path": str(zip_path),
        "zip_pass": zip_pass,
        "scientific_values_recalculated": False,
        "materialized_table_bytes_modified": False,
        "source_files_modified": False,
        "historical_artifacts_overwritten": False,
    }
    (
        outresults / "UTI_HostOmics_U27B3E321_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log(f"Tables preserved: {int(preservation['byte_identical'].sum())}/10")
    log(f"Authorized prohibition rows: {authorized_total}")
    log(f"Unauthorized GSE168600 rows: {unauthorized_total}")
    log(
        "Semantic audits passed: "
        f"{int((corrected_audit['pass'].astype(str).str.lower() == 'true').sum())}/"
        f"{len(corrected_audit)}"
    )
    log(f"ZIP pass: {zip_pass}")
    log(f"Decision: {decision_frame.loc[0, 'decision']}")
    log(f"ZIP: {zip_path}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E3.2.1] ERROR: {exc}", file=sys.stderr)
        raise
