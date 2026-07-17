#!/usr/bin/env python3
"""
Phase U27B3E3
Materialize Supplementary Tables S1-S10 from the accession-corrected source map.

This phase reads the corrected U27B3E22 supplementary source lock map and
creates a traceable supplementary-table package without altering any source
file. Each table is exported as a standalone TSV with row-level provenance,
accompanied by schema, source-lock, checksum, and package manifests.

The phase deliberately avoids recalculating scientific values. It copies and
harmonizes existing frozen source tables only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


VERSION = "U27B3E3_v1.0_2026-07-16"
TAG = "phaseU27B3E3_supplementary_table_materialization"

DEFAULT_MAP = (
    "06_tables/phaseU27B3E22_targeted_accession_correction/"
    "UTI_HostOmics_U27B3E22_supplementary_source_lock_map.tsv"
)

DEFAULT_SUMMARY = (
    "06_tables/phaseU27B3E22_targeted_accession_correction/"
    "UTI_HostOmics_U27B3E22_supplementary_source_confirmation_summary.tsv"
)

TABLE_IDS = [f"S{i}" for i in range(1, 11)]
SUPPORTED_SUFFIXES = {".tsv", ".csv", ".txt"}

TABLE_FIELD_CANDIDATES = (
    "supplementary_table",
    "supplementary_table_id",
    "table_id",
    "table_number",
    "supplement",
    "table",
)
SOURCE_FIELD_CANDIDATES = (
    "locked_source_path",
    "source_path",
    "source_file",
    "source_paths",
    "candidate_path",
    "file_path",
    "path",
)
STATUS_FIELD_CANDIDATES = (
    "source_status",
    "lock_status",
    "confirmation_status",
    "status",
)
TITLE_FIELD_CANDIDATES = (
    "supplementary_table_title",
    "table_title",
    "title",
    "description",
)
ORDER_FIELD_CANDIDATES = (
    "source_order",
    "priority",
    "rank",
    "order",
)


def log(message: str) -> None:
    print(f"[U27B3E3] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def normalize_table_id(value: str) -> str:
    text = str(value).strip().upper()
    match = re.search(r"(?:TABLE\s*)?S\s*(10|[1-9])\b", text)
    if match:
        return f"S{match.group(1)}"
    match = re.fullmatch(r"10|[1-9]", text)
    if match:
        return f"S{text}"
    return ""


def find_field(fieldnames: Sequence[str], candidates: Sequence[str]) -> str:
    normalized = {normalize_key(name): name for name in fieldnames}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return ""


def read_tsv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {key: (value if value is not None else "") for key, value in row.items()}
            for row in reader
        ]
    return fieldnames, rows


def split_paths(value: str) -> List[str]:
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"\s*(?:\|\||;|\n)\s*", text)
    return [part.strip().strip('"').strip("'") for part in parts if part.strip()]


def resolve_source_path(project: Path, value: str) -> Path:
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (project / raw).resolve()


def detect_delimiter(path: Path) -> str:
    if path.suffix.lower() == ".tsv":
        return "\t"
    if path.suffix.lower() == ".csv":
        return ","
    sample = path.read_text(encoding="utf-8-sig", errors="ignore")[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,;").delimiter
    except csv.Error:
        return "\t"


def read_header(path: Path) -> Tuple[str, List[str]]:
    delimiter = detect_delimiter(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            return delimiter, []
    return delimiter, [str(value).strip() for value in header]


def iter_rows(path: Path, delimiter: str) -> Iterable[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            yield {
                key: (value if value is not None else "")
                for key, value in row.items()
            }


def safe_relative(path: Path, project: Path) -> str:
    try:
        return str(path.relative_to(project))
    except ValueError:
        return str(path)


def write_tsv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames),
            delimiter="\t",
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    parser.add_argument("--source-map", default=DEFAULT_MAP)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    source_map = resolve_source_path(project, args.source_map)
    summary_path = resolve_source_path(project, args.summary)

    if not source_map.exists():
        raise FileNotFoundError(f"Corrected supplementary source map not found: {source_map}")

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    outpackage = project / "11_supplementary" / TAG
    materialized_dir = outpackage / "materialized_tables"

    for directory in (outtables, outmetadata, outresults, outpackage, materialized_dir):
        directory.mkdir(parents=True, exist_ok=True)

    map_fields, map_rows = read_tsv(source_map)
    if not map_fields:
        raise RuntimeError("Corrected source map has no header.")

    table_field = find_field(map_fields, TABLE_FIELD_CANDIDATES)
    source_field = find_field(map_fields, SOURCE_FIELD_CANDIDATES)
    status_field = find_field(map_fields, STATUS_FIELD_CANDIDATES)
    title_field = find_field(map_fields, TITLE_FIELD_CANDIDATES)
    order_field = find_field(map_fields, ORDER_FIELD_CANDIDATES)

    if not table_field:
        raise RuntimeError(
            "Could not identify the supplementary-table ID column. "
            f"Observed columns: {map_fields}"
        )
    if not source_field:
        raise RuntimeError(
            "Could not identify the source-path column. "
            f"Observed columns: {map_fields}"
        )

    summary_by_table: Dict[str, Dict[str, str]] = {}
    if summary_path.exists():
        summary_fields, summary_rows = read_tsv(summary_path)
        summary_table_field = find_field(summary_fields, TABLE_FIELD_CANDIDATES)
        for row in summary_rows:
            table_id = normalize_table_id(row.get(summary_table_field, "")) if summary_table_field else ""
            if table_id:
                summary_by_table[table_id] = row

    grouped: Dict[str, List[Dict[str, str]]] = {table_id: [] for table_id in TABLE_IDS}
    unclassified_rows: List[Dict[str, str]] = []

    for row in map_rows:
        table_id = normalize_table_id(row.get(table_field, ""))
        if table_id in grouped:
            grouped[table_id].append(row)
        else:
            unclassified_rows.append(row)

    source_manifest_rows: List[Dict[str, object]] = []
    schema_rows: List[Dict[str, object]] = []
    table_summary_rows: List[Dict[str, object]] = []
    package_files: List[Path] = []
    failures: List[str] = []

    for table_id in TABLE_IDS:
        rows = grouped[table_id]
        title = ""
        if rows and title_field:
            title = next((row.get(title_field, "").strip() for row in rows if row.get(title_field, "").strip()), "")
        if not title and table_id in summary_by_table:
            summary_fields = list(summary_by_table[table_id].keys())
            summary_title_field = find_field(summary_fields, TITLE_FIELD_CANDIDATES)
            if summary_title_field:
                title = summary_by_table[table_id].get(summary_title_field, "").strip()
        if not title:
            title = f"Supplementary Table {table_id}"

        source_records: List[Tuple[int, Dict[str, str], Path]] = []
        for index, row in enumerate(rows, start=1):
            raw_paths = split_paths(row.get(source_field, ""))
            if not raw_paths:
                failures.append(f"{table_id}: source path missing in source-map row {index}")
                continue

            order_value = index
            if order_field:
                try:
                    order_value = int(float(row.get(order_field, "") or index))
                except ValueError:
                    order_value = index

            for raw_path in raw_paths:
                path = resolve_source_path(project, raw_path)
                source_records.append((order_value, row, path))

        source_records.sort(key=lambda item: (item[0], str(item[2])))

        unique_records: List[Tuple[int, Dict[str, str], Path]] = []
        seen = set()
        for record in source_records:
            key = str(record[2])
            if key not in seen:
                seen.add(key)
                unique_records.append(record)

        union_headers: List[str] = []
        source_headers: Dict[str, List[str]] = {}
        source_delimiters: Dict[str, str] = {}

        for source_order, row, path in unique_records:
            exists = path.exists()
            supported = path.suffix.lower() in SUPPORTED_SUFFIXES
            source_hash = sha256(path) if exists and path.is_file() else ""
            status = row.get(status_field, "") if status_field else ""

            manifest_row: Dict[str, object] = {
                "supplementary_table": table_id,
                "table_title": title,
                "source_order": source_order,
                "source_status": status,
                "source_path": str(path),
                "source_relative_path": safe_relative(path, project),
                "source_exists": exists,
                "source_supported_tabular_format": supported,
                "source_sha256": source_hash,
                "source_size_bytes": path.stat().st_size if exists else 0,
            }

            if not exists:
                manifest_row["source_read_status"] = "MISSING"
                failures.append(f"{table_id}: source file missing: {path}")
                source_manifest_rows.append(manifest_row)
                continue

            if not supported:
                manifest_row["source_read_status"] = "UNSUPPORTED_FORMAT"
                failures.append(f"{table_id}: unsupported source format: {path}")
                source_manifest_rows.append(manifest_row)
                continue

            delimiter, header = read_header(path)
            source_delimiters[str(path)] = delimiter
            source_headers[str(path)] = header
            manifest_row["source_read_status"] = "READY" if header else "EMPTY_OR_HEADERLESS"
            manifest_row["source_column_count"] = len(header)
            manifest_row["source_columns"] = "; ".join(header)
            source_manifest_rows.append(manifest_row)

            if not header:
                failures.append(f"{table_id}: empty or headerless source: {path}")
                continue

            for column in header:
                if column not in union_headers:
                    union_headers.append(column)

        output_path = materialized_dir / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
        provenance_columns = [
            "_supplementary_table",
            "_table_title",
            "_source_order",
            "_source_file",
            "_source_relative_path",
            "_source_sha256",
            "_source_row_number",
        ]
        output_fields = provenance_columns + union_headers

        rows_written = 0
        source_rows_written = 0
        if union_headers:
            with output_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=output_fields,
                    delimiter="\t",
                    extrasaction="ignore",
                    lineterminator="\n",
                )
                writer.writeheader()

                for source_order, row, path in unique_records:
                    if str(path) not in source_headers:
                        continue
                    if not source_headers[str(path)]:
                        continue
                    source_hash = sha256(path)
                    delimiter = source_delimiters[str(path)]
                    for source_row_number, source_row in enumerate(iter_rows(path, delimiter), start=1):
                        record: Dict[str, object] = {
                            "_supplementary_table": table_id,
                            "_table_title": title,
                            "_source_order": source_order,
                            "_source_file": path.name,
                            "_source_relative_path": safe_relative(path, project),
                            "_source_sha256": source_hash,
                            "_source_row_number": source_row_number,
                        }
                        record.update(source_row)
                        writer.writerow({key: record.get(key, "") for key in output_fields})
                        rows_written += 1
                        source_rows_written += 1

            package_files.append(output_path)

        table_summary_rows.append(
            {
                "supplementary_table": table_id,
                "table_title": title,
                "source_map_rows": len(rows),
                "unique_source_files": len(unique_records),
                "materialized_output": str(output_path),
                "output_exists": output_path.exists(),
                "output_sha256": sha256(output_path) if output_path.exists() else "",
                "materialized_rows": rows_written,
                "materialized_columns": len(output_fields) if union_headers else 0,
                "materialization_status": (
                    "MATERIALIZED" if output_path.exists() and rows_written > 0 else "FAILED_OR_EMPTY"
                ),
            }
        )

        for position, column in enumerate(output_fields, start=1):
            schema_rows.append(
                {
                    "supplementary_table": table_id,
                    "column_position": position,
                    "column_name": column,
                    "column_origin": (
                        "provenance" if column in provenance_columns else "source_union"
                    ),
                }
            )

    source_manifest_path = outtables / "UTI_HostOmics_U27B3E3_source_manifest.tsv"
    write_tsv(
        source_manifest_path,
        [
            "supplementary_table",
            "table_title",
            "source_order",
            "source_status",
            "source_path",
            "source_relative_path",
            "source_exists",
            "source_supported_tabular_format",
            "source_sha256",
            "source_size_bytes",
            "source_read_status",
            "source_column_count",
            "source_columns",
        ],
        source_manifest_rows,
    )

    schema_path = outtables / "UTI_HostOmics_U27B3E3_materialized_schema_registry.tsv"
    write_tsv(
        schema_path,
        [
            "supplementary_table",
            "column_position",
            "column_name",
            "column_origin",
        ],
        schema_rows,
    )

    summary_path_out = outtables / "UTI_HostOmics_U27B3E3_materialization_summary.tsv"
    write_tsv(
        summary_path_out,
        [
            "supplementary_table",
            "table_title",
            "source_map_rows",
            "unique_source_files",
            "materialized_output",
            "output_exists",
            "output_sha256",
            "materialized_rows",
            "materialized_columns",
            "materialization_status",
        ],
        table_summary_rows,
    )

    unclassified_path = outtables / "UTI_HostOmics_U27B3E3_unclassified_source_map_rows.tsv"
    write_tsv(unclassified_path, map_fields, unclassified_rows)

    successful_tables = sum(
        1 for row in table_summary_rows if row["materialization_status"] == "MATERIALIZED"
    )
    failed_tables = len(TABLE_IDS) - successful_tables
    all_sources_exist = all(bool(row.get("source_exists")) for row in source_manifest_rows) if source_manifest_rows else False
    no_unsupported_sources = all(bool(row.get("source_supported_tabular_format")) for row in source_manifest_rows) if source_manifest_rows else False

    package_readme = outpackage / "UTI_HostOmics_U27B3E3_supplementary_package_README.md"
    with package_readme.open("w", encoding="utf-8") as handle:
        handle.write("# UTI HostOmics Supplementary Tables S1-S10\n\n")
        handle.write(f"- Phase: `{VERSION}`\n")
        handle.write("- Correct recurrent-UTI accession: **GSE186800**\n")
        handle.write("- Scientific values recalculated: **No**\n")
        handle.write("- Historical sources overwritten: **No**\n")
        handle.write(f"- Successfully materialized tables: **{successful_tables}/10**\n\n")
        handle.write("## Provenance model\n\n")
        handle.write(
            "Every materialized row carries the supplementary-table ID, source file, "
            "source-relative path, SHA256 checksum and source-row number. Composite tables "
            "use a union schema and preserve values exactly as stored in the locked source files.\n\n"
        )
        handle.write("## Materialized tables\n\n")
        for row in table_summary_rows:
            handle.write(
                f"- **{row['supplementary_table']}**: {row['table_title']} "
                f"({row['materialization_status']}; rows={row['materialized_rows']}; "
                f"sources={row['unique_source_files']}).\n"
            )
        if failures:
            handle.write("\n## Materialization warnings\n\n")
            for failure in failures:
                handle.write(f"- {failure}\n")

    package_files.extend([package_readme, source_manifest_path, schema_path, summary_path_out])

    zip_path = outpackage / "UTI_HostOmics_U27B3E3_Supplementary_Tables_S1-S10.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in package_files:
            if path.exists():
                archive.write(path, arcname=str(path.relative_to(outpackage.parent)))

    if successful_tables == 10 and not failures and all_sources_exist and no_unsupported_sources:
        decision = "READY_FOR_U27B3E4_SUPPLEMENTARY_TABLE_SCHEMA_AND_CONTENT_AUDIT"
    elif successful_tables > 0:
        decision = "TARGETED_U27B3E3_SUPPLEMENTARY_SOURCE_OR_SCHEMA_REPAIR_REQUIRED"
    else:
        decision = "U27B3E3_SUPPLEMENTARY_MATERIALIZATION_FAILED"

    decision_path = outtables / "UTI_HostOmics_U27B3E3_phase_decision.tsv"
    write_tsv(
        decision_path,
        [
            "phase",
            "decision",
            "supplementary_tables_expected",
            "supplementary_tables_materialized",
            "supplementary_tables_failed_or_empty",
            "all_sources_exist",
            "all_sources_supported_tabular_format",
            "unclassified_source_map_rows",
            "package_zip_created",
            "package_zip_path",
            "scientific_values_recalculated",
            "source_files_modified",
            "historical_artifacts_overwritten",
            "front_matter_user_input_still_required",
            "next_phase",
        ],
        [
            {
                "phase": "U27B3E3",
                "decision": decision,
                "supplementary_tables_expected": 10,
                "supplementary_tables_materialized": successful_tables,
                "supplementary_tables_failed_or_empty": failed_tables,
                "all_sources_exist": all_sources_exist,
                "all_sources_supported_tabular_format": no_unsupported_sources,
                "unclassified_source_map_rows": len(unclassified_rows),
                "package_zip_created": zip_path.exists(),
                "package_zip_path": str(zip_path),
                "scientific_values_recalculated": False,
                "source_files_modified": False,
                "historical_artifacts_overwritten": False,
                "front_matter_user_input_still_required": True,
                "next_phase": (
                    "U27B3E4 audit materialized schemas, row counts, biological scope, "
                    "duplicate rows and submission-facing table descriptions"
                    if decision.startswith("READY_FOR_U27B3E4")
                    else "Resolve missing, unsupported, empty or ambiguously mapped sources"
                ),
            }
        ],
    )

    report_path = outresults / "UTI_HostOmics_U27B3E3_supplementary_materialization_report.md"
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# Phase U27B3E3 - Supplementary table materialization\n\n")
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(f"- Correct source map: `{source_map}`\n")
        handle.write(f"- Tables materialized: **{successful_tables}/10**\n")
        handle.write(f"- Tables failed or empty: **{failed_tables}**\n")
        handle.write(f"- Package ZIP: `{zip_path}`\n")
        handle.write("- Scientific values recalculated: **False**\n")
        handle.write("- Source files modified: **False**\n")
        handle.write("- Historical artifacts overwritten: **False**\n\n")
        handle.write("## Integrity boundary\n\n")
        handle.write(
            "This phase materializes existing locked tables only. It does not recompute "
            "module scores, effect estimates, FDR values, cell counts or source matrices.\n"
        )
        if failures:
            handle.write("\n## Failures or warnings\n\n")
            for failure in failures:
                handle.write(f"- {failure}\n")

    manifest = {
        "version": VERSION,
        "decision": decision,
        "source_map": str(source_map),
        "source_map_sha256": sha256(source_map),
        "summary_path": str(summary_path) if summary_path.exists() else "",
        "tables_expected": 10,
        "tables_materialized": successful_tables,
        "tables_failed_or_empty": failed_tables,
        "failures": failures,
        "package_zip": str(zip_path),
        "package_zip_sha256": sha256(zip_path) if zip_path.exists() else "",
        "scientific_values_recalculated": False,
        "source_files_modified": False,
        "historical_artifacts_overwritten": False,
    }
    (outresults / "UTI_HostOmics_U27B3E3_run_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Tables materialized: {successful_tables}/10")
    log(f"Failures or warnings: {len(failures)}")
    log(f"Package ZIP: {zip_path}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E3] ERROR: {exc}", file=sys.stderr)
        raise
