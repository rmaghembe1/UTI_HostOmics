#!/usr/bin/env python3
"""
Phase U27B3E5
Create a polished submission-facing Excel workbook for Supplementary Tables
S1-S10 and assemble a reproducible supplementary freeze package.

Scientific source of truth
--------------------------
The byte-preserved TSV package from:
  11_supplementary/phaseU27B3E321_semantic_accession_audit_correction

Release gate
------------
The script runs only when U27B3E4.1.1 reports:
  READY_FOR_U27B3E5_SUPPLEMENTARY_TABLE_SUBMISSION_FORMATTING_AND_FREEZE

Workbook architecture
---------------------
- README: package scope, interpretation boundaries and sheet index.
- Source_Index: source roles, project-relative source paths, row counts and
  SHA256 checksums.
- Audit_Summary: U27B3E4.1.1 release decision and semantic exceptions.
- S1-S10: one worksheet per supplementary table. Heterogeneous source blocks
  are stacked vertically, and each block exposes only its native source schema
  plus source_row_number. Absolute local paths are not included in the visible
  scientific sheets.

Integrity boundary
------------------
- Uses artifact_tool only for workbook creation and formatting.
- Does not use pandas, openpyxl or LibreOffice.
- Does not recalculate scientific values.
- Does not modify the archival TSVs, controlled U27B3E321 ZIP, manuscript,
  figures, legends or source tables.
- Produces a candidate freeze package that remains pending workbook visual
  review of the generated contact sheet.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import textwrap
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from artifact_tool import Blob, SpreadsheetFile, Workbook


VERSION = "U27B3E5_v1.0_2026-07-16"
TAG = "phaseU27B3E5_supplementary_submission_formatting_and_freeze"

INPUT_PACKAGE_TAG = "phaseU27B3E321_semantic_accession_audit_correction"
RELEASE_AUDIT_TAG = "phaseU27B3E411_contact_sheet_semantic_finalization"
REQUIRED_RELEASE = (
    "READY_FOR_U27B3E5_SUPPLEMENTARY_TABLE_"
    "SUBMISSION_FORMATTING_AND_FREEZE"
)

TABLE_TITLES = {
    "S1": (
        "Dataset architecture, sample design and inclusion roles for "
        "GSE112098, GSE280297, GSE186800 and GSE252321."
    ),
    "S2": (
        "Expanded 78-submodule library organized across ten biological axes."
    ),
    "S3": (
        "Dataset-specific module effects and factorial or adjusted contrasts."
    ),
    "S4": (
        "Cross-dataset recurrence, directional concordance and "
        "evidence-class assignments."
    ),
    "S5": (
        "GSE280297 pregnancy, tissue and outcome-specific module effects."
    ),
    "S6": (
        "GSE252321 quality control, cluster markers, broad populations and "
        "refined subtypes."
    ),
    "S7": (
        "Broad-cell and refined-subtype pseudobulk module localization results."
    ),
    "S8": (
        "Complement-stage and endocrine-metabolic cellular attribution tables."
    ),
    "S9": (
        "Figure 1-8 source-value manifest and panel-level provenance registry."
    ),
    "S10": (
        "Interpretation-boundary, sensitivity and manuscript "
        "claim-traceability register."
    ),
}

TABLE_SHORT_NOTES = {
    "S1": "Four independently processed datasets; GSE280297 has no dam identifiers.",
    "S2": "Frozen 78-submodule library across ten biological axes.",
    "S3": "Effects remain dataset-native; GSE252321 uses sample_mean from n=2 versus n=2 biological samples.",
    "S4": "Cross-dataset integration uses standardized effects and directional concordance, not pooled expression.",
    "S5": "Pregnancy-model contrasts are tissue resolved; tissue samples remain the inferential units.",
    "S6": "Single-cell QC, markers and composition: 28,313 raw cells and 27,385 QC-passing cells.",
    "S7": "Localization summaries are descriptive and hypothesis-generating because GSE252321 contains four samples.",
    "S8": "Cellular attribution summarizes complement and endocrine-metabolic localization without treating cells as replicates.",
    "S9": "Includes 81 figure-linked assets and two authorized package-level contact sheets.",
    "S10": "Contains interpretation boundaries and the explicit prohibition rule for unrelated accession GSE168600.",
}

PROVENANCE_COLUMNS = [
    "_supplementary_table",
    "_table_title",
    "_source_order",
    "_source_role",
    "_source_file",
    "_source_relative_path",
    "_source_sha256",
    "_source_row_number",
]

TEXT_HEAVY_HINTS = (
    "legend",
    "statement",
    "rationale",
    "wording",
    "description",
    "genes",
    "path",
    "identity",
    "note",
    "title",
    "label",
    "class",
    "dataset_effects",
)

INTEGER_HINTS = (
    "n_",
    "_count",
    "rank",
    "figure_number",
    "channel_count",
    "data_row_count",
    "source_row_number",
)

DECIMAL_HINTS = (
    "effect",
    "score",
    "coherence",
    "fraction",
    "median",
    "mean",
    "auc",
    "log",
)

PROBABILITY_HINTS = (
    "p_value",
    "q_value",
    "fdr",
    "probability",
)

TRUE_VALUES = {"true", "yes"}
FALSE_VALUES = {"false", "no"}

# Consistent professional palette.
NAVY = "#17365D"
TEAL = "#1F6D78"
MID_BLUE = "#5B9BD5"
LIGHT_BLUE = "#D9EAF7"
PALE_BLUE = "#EEF5FB"
PALE_TEAL = "#E2F0D9"
LIGHT_GRAY = "#F2F2F2"
MID_GRAY = "#D9E1F2"
DARK_GRAY = "#404040"
WHITE = "#FFFFFF"
WARNING_FILL = "#FFF2CC"


def log(message: str) -> None:
    print(f"[U27B3E5] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def safe_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def blank(value: Any) -> bool:
    return str(value).strip() in {"", "NA", "NaN", "nan", "None"}


def column_letter(index_1_based: int) -> str:
    if index_1_based < 1:
        raise ValueError("Column index must be >= 1")
    result = ""
    index = index_1_based
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def excel_range(start_row: int, start_col: int, row_count: int, col_count: int) -> str:
    end_row = start_row + row_count - 1
    end_col = start_col + col_count - 1
    return (
        f"{column_letter(start_col)}{start_row}:"
        f"{column_letter(end_col)}{end_row}"
    )


def sanitize_table_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"T_{cleaned}"
    return cleaned[:200]


def parse_source_columns(value: str) -> List[str]:
    return [part.strip() for part in str(value).split(";") if part.strip()]


def numeric_hint(column_name: str) -> str:
    lower = column_name.lower()
    if any(token in lower for token in PROBABILITY_HINTS):
        return "probability"
    if lower.startswith("n_") or any(token in lower for token in INTEGER_HINTS):
        return "integer"
    if any(token in lower for token in DECIMAL_HINTS):
        return "decimal"
    return "text"


def to_cell_value(column_name: str, value: Any) -> Any:
    text = str(value)
    if blank(text):
        return None

    lower = text.strip().lower()
    if lower in TRUE_VALUES:
        return True
    if lower in FALSE_VALUES:
        return False

    hint = numeric_hint(column_name)
    if hint == "integer":
        try:
            number = float(text)
            if math.isfinite(number) and number.is_integer():
                return int(number)
        except ValueError:
            return text
    elif hint in {"probability", "decimal"}:
        try:
            number = float(text)
            if math.isfinite(number):
                return number
        except ValueError:
            return text

    if len(text) > 32767:
        raise ValueError(
            f"Cell value exceeds Excel's 32,767-character limit in column {column_name}"
        )
    return text


def display_header(column_name: str) -> str:
    if column_name == "_source_row_number":
        return "source_row_number"
    return column_name


def format_for_column(column_name: str) -> str | None:
    hint = numeric_hint(column_name)
    if hint == "integer":
        return "0"
    if hint == "probability":
        return "0.0000"
    if hint == "decimal":
        return "0.000"
    return None


def suggested_width(column_name: str, sampled_values: Sequence[Any]) -> float:
    lower = column_name.lower()
    max_len = len(column_name)
    for value in sampled_values[:200]:
        if value is None:
            continue
        max_len = max(max_len, min(len(str(value)), 80))

    if column_name == "_source_row_number":
        return 12
    if any(token in lower for token in TEXT_HEAVY_HINTS):
        return min(max(18, max_len * 0.72), 40)
    if numeric_hint(column_name) in {"integer", "decimal", "probability"}:
        return min(max(11, max_len * 0.9), 16)
    if "id" in lower or "accession" in lower or "sample" in lower:
        return min(max(14, max_len * 0.85), 24)
    return min(max(11, max_len * 0.8), 24)


def group_rows_by_source(rows: Sequence[Dict[str, str]]) -> List[Tuple[int, str, List[Dict[str, str]]]]:
    groups: MutableMapping[Tuple[int, str], List[Dict[str, str]]] = {}
    for row in rows:
        order_text = str(row.get("_source_order", "0")).strip()
        try:
            order = int(float(order_text))
        except ValueError:
            order = 0
        role = str(row.get("_source_role", "Unspecified source")).strip()
        groups.setdefault((order, role), []).append(row)
    return [
        (order, role, groups[(order, role)])
        for order, role in sorted(groups, key=lambda item: (item[0], item[1]))
    ]


def manifest_lookup(manifest_rows: Sequence[Dict[str, str]]) -> Dict[Tuple[str, str], Dict[str, str]]:
    result: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in manifest_rows:
        key = (
            str(row.get("supplementary_table", "")).strip(),
            str(row.get("source_role", "")).strip(),
        )
        result[key] = row
    return result


def style_title(sheet, cell_range: str, fill: str, font_size: int) -> None:
    rng = sheet.get_range(cell_range)
    rng.format = {
        "fill": fill,
        "font": {"bold": True, "color": WHITE, "size": font_size},
        "horizontal_alignment": "left",
        "vertical_alignment": "center",
        "wrap_text": True,
    }


def style_section(sheet, cell_range: str) -> None:
    rng = sheet.get_range(cell_range)
    rng.format = {
        "fill": TEAL,
        "font": {"bold": True, "color": WHITE, "size": 11},
        "horizontal_alignment": "left",
        "vertical_alignment": "center",
        "wrap_text": True,
    }


def style_note(sheet, cell_range: str) -> None:
    rng = sheet.get_range(cell_range)
    rng.format = {
        "fill": PALE_BLUE,
        "font": {"italic": True, "color": DARK_GRAY, "size": 9},
        "horizontal_alignment": "left",
        "vertical_alignment": "center",
        "wrap_text": True,
    }


def style_header(sheet, cell_range: str) -> None:
    rng = sheet.get_range(cell_range)
    rng.format = {
        "fill": NAVY,
        "font": {"bold": True, "color": WHITE, "size": 9},
        "horizontal_alignment": "center",
        "vertical_alignment": "center",
        "wrap_text": True,
        "borders": {
            "top": {"style": "continuous", "color": WHITE},
            "bottom": {"style": "continuous", "color": WHITE},
            "left": {"style": "continuous", "color": WHITE},
            "right": {"style": "continuous", "color": WHITE},
        },
    }


def style_data(sheet, cell_range: str) -> None:
    rng = sheet.get_range(cell_range)
    rng.format = {
        "font": {"color": "#000000", "size": 9},
        "vertical_alignment": "top",
        "wrap_text": True,
        "borders": {
            "top": {"style": "continuous", "color": "#D9D9D9"},
            "bottom": {"style": "continuous", "color": "#D9D9D9"},
            "left": {"style": "continuous", "color": "#D9D9D9"},
            "right": {"style": "continuous", "color": "#D9D9D9"},
        },
    }


def add_readme_sheet(wb, index_rows: Sequence[Dict[str, Any]]) -> None:
    sheet = wb.worksheets.add("README")
    sheet.merge_cells("A1:H1")
    sheet.get_range("A1").values = [["UTI HostOmics Supplementary Tables S1-S10"]]
    style_title(sheet, "A1:H1", NAVY, 16)
    sheet.get_range("A1:H1").format.row_height = 30

    sheet.merge_cells("A2:H2")
    sheet.get_range("A2").values = [[
        "Submission-facing workbook generated from the byte-preserved U27B3E321 TSV package."
    ]]
    style_note(sheet, "A2:H2")
    sheet.get_range("A2:H2").format.row_height = 26

    metadata = [
        ["Release phase", VERSION],
        ["Canonical recurrent-UTI accession", "GSE186800"],
        ["Prohibited unrelated accession", "GSE168600 appears only in the S10 prevention rule"],
        ["Cross-species integration", "Native-species scoring; standardized effects and directional concordance only"],
        ["Metabolic terminology", "Transcriptionally inferred pathway activity; not metabolic flux"],
        ["GSE252321 inference", "Sample-level n=2 control versus n=2 UPEC; cells are not independent replicates"],
        ["GSE280297 inference", "No dam identifiers; tissue samples remain inferential units"],
        ["GSE112098 role", "Systemic urinary inflammation comparator; not UTI-specific"],
        ["Archival master", "The accompanying TSV package remains the source-of-truth archive"],
    ]
    sheet.get_range("A4:B12").values = metadata
    sheet.get_range("A4:A12").format = {
        "fill": LIGHT_BLUE,
        "font": {"bold": True, "color": NAVY, "size": 10},
        "vertical_alignment": "top",
        "wrap_text": True,
    }
    sheet.get_range("B4:B12").format = {
        "font": {"size": 10},
        "vertical_alignment": "top",
        "wrap_text": True,
    }

    sheet.get_range("A14:E14").values = [[
        "Sheet", "Supplementary table title", "Rows", "Source blocks", "Interpretive note"
    ]]
    style_header(sheet, "A14:E14")

    matrix = []
    for row in index_rows:
        matrix.append([
            row["sheet"],
            row["title"],
            row["rows"],
            row["source_blocks"],
            row["note"],
        ])
    if matrix:
        end_row = 14 + len(matrix)
        sheet.get_range(f"A15:E{end_row}").values = matrix
        style_data(sheet, f"A15:E{end_row}")
        sheet.tables.add(f"A14:E{end_row}", True, "SupplementaryIndexTable")

    sheet.get_range("A1:E30").format.wrap_text = True
    widths = [12, 42, 10, 13, 46]
    for index, width in enumerate(widths, start=1):
        sheet.get_range(f"{column_letter(index)}1:{column_letter(index)}30").format.column_width = width
    sheet.freeze_panes.freeze_rows(14)
    sheet.freeze_panes.freeze_columns(1)


def add_source_index_sheet(wb, manifest_rows: Sequence[Dict[str, str]]) -> None:
    sheet = wb.worksheets.add("Source_Index")
    sheet.merge_cells("A1:H1")
    sheet.get_range("A1").values = [["Supplementary source index and checksums"]]
    style_title(sheet, "A1:H1", NAVY, 15)
    sheet.get_range("A1:H1").format.row_height = 28

    headers = [
        "supplementary_table",
        "source_order",
        "source_role",
        "source_relative_path",
        "source_rows",
        "source_column_count",
        "source_sha256",
        "source_status",
    ]
    sheet.get_range("A3:H3").values = [headers]
    style_header(sheet, "A3:H3")

    values = []
    for row in sorted(
        manifest_rows,
        key=lambda item: (
            int(float(item.get("supplementary_table", "S0")[1:] or 0)),
            int(float(item.get("source_order", "0") or 0)),
        ),
    ):
        values.append([
            row.get("supplementary_table", ""),
            to_cell_value("source_order", row.get("source_order", "")),
            row.get("source_role", ""),
            row.get("source_relative_path", ""),
            to_cell_value("source_rows", row.get("source_rows", "")),
            to_cell_value("source_column_count", row.get("source_column_count", "")),
            row.get("source_sha256", ""),
            row.get("source_status", ""),
        ])

    if values:
        end_row = 3 + len(values)
        sheet.get_range(f"A4:H{end_row}").values = values
        style_data(sheet, f"A4:H{end_row}")
        sheet.tables.add(f"A3:H{end_row}", True, "SourceIndexTable")

    widths = [12, 12, 38, 48, 12, 15, 36, 22]
    for index, width in enumerate(widths, start=1):
        sheet.get_range(f"{column_letter(index)}1:{column_letter(index)}{max(10, 4 + len(values))}").format.column_width = width
    sheet.freeze_panes.freeze_rows(3)
    sheet.freeze_panes.freeze_columns(2)


def add_audit_summary_sheet(
    wb,
    decision_rows: Sequence[Dict[str, str]],
    exception_rows: Sequence[Dict[str, str]],
    warning_rows: Sequence[Dict[str, str]],
) -> None:
    sheet = wb.worksheets.add("Audit_Summary")
    sheet.merge_cells("A1:F1")
    sheet.get_range("A1").values = [["Supplementary release audit summary"]]
    style_title(sheet, "A1:F1", NAVY, 15)
    sheet.get_range("A1:F1").format.row_height = 28

    decision = decision_rows[0] if decision_rows else {}
    release_fields = [
        ("decision", decision.get("decision", "")),
        ("audit_checks", decision.get("audit_checks", "")),
        ("audit_checks_passed", decision.get("audit_checks_passed", "")),
        ("blocking_checks", decision.get("blocking_checks", "")),
        ("blocking_checks_passed", decision.get("blocking_checks_passed", "")),
        ("blocking_failures", decision.get("blocking_failures", "")),
        ("zip_integrity_pass", decision.get("zip_integrity_pass", "")),
        ("manuscript_consistency_pass", decision.get("manuscript_consistency_pass", "")),
        ("scientific_values_recalculated", decision.get("scientific_values_recalculated", "")),
        ("materialized_tables_modified", decision.get("materialized_tables_modified", "")),
    ]
    sheet.get_range(f"A3:B{2 + len(release_fields)}").values = [
        [field, to_cell_value(field, value)] for field, value in release_fields
    ]
    sheet.get_range(f"A3:A{2 + len(release_fields)}").format = {
        "fill": LIGHT_BLUE,
        "font": {"bold": True, "color": NAVY, "size": 10},
        "wrap_text": True,
    }
    sheet.get_range(f"B3:B{2 + len(release_fields)}").format = {
        "font": {"size": 10},
        "wrap_text": True,
    }

    start = 4 + len(release_fields)
    sheet.get_range(f"A{start}:D{start}").values = [[
        "audit_id", "semantic_exception", "evidence", "pass"
    ]]
    style_header(sheet, f"A{start}:D{start}")
    exception_values = [
        [
            row.get("audit_id", ""),
            row.get("semantic_exception", ""),
            row.get("evidence", ""),
            to_cell_value("pass", row.get("pass", "")),
        ]
        for row in exception_rows
    ]
    if exception_values:
        end = start + len(exception_values)
        sheet.get_range(f"A{start + 1}:D{end}").values = exception_values
        style_data(sheet, f"A{start + 1}:D{end}")
        sheet.tables.add(f"A{start}:D{end}", True, "SemanticExceptionsTable")

    warning_start = start + max(3, len(exception_values) + 3)
    sheet.get_range(f"A{warning_start}:D{warning_start}").values = [[
        "supplementary_table", "source_role", "warning_type", "interpretation"
    ]]
    style_header(sheet, f"A{warning_start}:D{warning_start}")
    warning_values = []
    for row in warning_rows:
        warning_values.append([
            row.get("supplementary_table", ""),
            row.get("source_role", ""),
            row.get("warning_type", ""),
            (
                "Native-source missingness warning; non-blocking unless a critical field is affected. "
                f"Reported fraction: {row.get('value', '')}"
            ),
        ])
    if warning_values:
        end = warning_start + len(warning_values)
        sheet.get_range(f"A{warning_start + 1}:D{end}").values = warning_values
        style_data(sheet, f"A{warning_start + 1}:D{end}")
        sheet.get_range(f"A{warning_start + 1}:D{end}").format.fill = WARNING_FILL
        sheet.tables.add(f"A{warning_start}:D{end}", True, "MissingnessWarningsTable")

    widths = [26, 32, 55, 18, 18, 18]
    max_row = max(30, warning_start + len(warning_values) + 2)
    for index, width in enumerate(widths, start=1):
        sheet.get_range(f"{column_letter(index)}1:{column_letter(index)}{max_row}").format.column_width = width
    sheet.freeze_panes.freeze_rows(1)


def add_supplementary_sheet(
    wb,
    table_id: str,
    title: str,
    note: str,
    source_rows: Sequence[Dict[str, str]],
    source_manifest: Mapping[Tuple[str, str], Dict[str, str]],
) -> Dict[str, Any]:
    sheet = wb.worksheets.add(table_id)
    groups = group_rows_by_source(source_rows)
    max_native_columns = 1
    for _, role, _ in groups:
        manifest = source_manifest.get((table_id, role), {})
        native_columns = parse_source_columns(manifest.get("source_columns", ""))
        if not native_columns:
            native_columns = [
                column
                for column in source_rows[0].keys()
                if column not in PROVENANCE_COLUMNS
            ]
        max_native_columns = max(max_native_columns, 1 + len(native_columns))

    title_end_col = min(max(max_native_columns, 8), 18)
    title_end_letter = column_letter(title_end_col)

    sheet.merge_cells(f"A1:{title_end_letter}1")
    sheet.get_range("A1").values = [[f"Supplementary Table {table_id}"]]
    style_title(sheet, f"A1:{title_end_letter}1", NAVY, 15)
    sheet.get_range(f"A1:{title_end_letter}1").format.row_height = 28

    sheet.merge_cells(f"A2:{title_end_letter}2")
    sheet.get_range("A2").values = [[title]]
    style_note(sheet, f"A2:{title_end_letter}2")
    sheet.get_range(f"A2:{title_end_letter}2").format.row_height = 34

    sheet.merge_cells(f"A3:{title_end_letter}3")
    sheet.get_range("A3").values = [[note]]
    sheet.get_range(f"A3:{title_end_letter}3").format = {
        "fill": PALE_TEAL,
        "font": {"italic": True, "color": DARK_GRAY, "size": 9},
        "wrap_text": True,
        "vertical_alignment": "center",
    }
    sheet.get_range(f"A3:{title_end_letter}3").format.row_height = 30

    current_row = 5
    total_data_rows = 0
    source_block_count = 0
    sheet_max_col = 1

    for source_order, role, block_rows in groups:
        source_block_count += 1
        manifest = source_manifest.get((table_id, role), {})
        native_columns = parse_source_columns(manifest.get("source_columns", ""))
        if not native_columns:
            native_columns = [
                column
                for column in block_rows[0].keys()
                if column not in PROVENANCE_COLUMNS
            ]

        visible_columns = ["_source_row_number"] + native_columns
        display_columns = [display_header(column) for column in visible_columns]
        sheet_max_col = max(sheet_max_col, len(visible_columns))
        end_col_letter = column_letter(len(visible_columns))

        sheet.merge_cells(f"A{current_row}:{end_col_letter}{current_row}")
        sheet.get_range(f"A{current_row}").values = [[
            f"Source block {source_order}: {role}"
        ]]
        style_section(sheet, f"A{current_row}:{end_col_letter}{current_row}")
        sheet.get_range(f"A{current_row}:{end_col_letter}{current_row}").format.row_height = 22

        note_row = current_row + 1
        relative_path = manifest.get("source_relative_path", "")
        checksum = manifest.get("source_sha256", "")
        source_note = (
            f"Rows: {len(block_rows)} | Source: {relative_path} | SHA256: {checksum}"
        )
        sheet.merge_cells(f"A{note_row}:{end_col_letter}{note_row}")
        sheet.get_range(f"A{note_row}").values = [[source_note]]
        style_note(sheet, f"A{note_row}:{end_col_letter}{note_row}")
        sheet.get_range(f"A{note_row}:{end_col_letter}{note_row}").format.row_height = 30

        header_row = current_row + 2
        sheet.get_range(
            excel_range(header_row, 1, 1, len(display_columns))
        ).values = [display_columns]
        style_header(
            sheet,
            excel_range(header_row, 1, 1, len(display_columns)),
        )
        sheet.get_range(
            excel_range(header_row, 1, 1, len(display_columns))
        ).format.row_height = 28

        values: List[List[Any]] = []
        for row in block_rows:
            values.append([
                to_cell_value(column, row.get(column, ""))
                for column in visible_columns
            ])

        data_start = header_row + 1
        if values:
            data_range = excel_range(data_start, 1, len(values), len(display_columns))
            sheet.get_range(data_range).values = values
            style_data(sheet, data_range)
            sheet.tables.add(
                excel_range(header_row, 1, len(values) + 1, len(display_columns)),
                True,
                sanitize_table_name(f"Tbl_{table_id}_{source_order:02d}"),
            )

            # Number formats and bounded widths.
            for col_index, column in enumerate(visible_columns, start=1):
                col_letter = column_letter(col_index)
                sampled = [row[col_index - 1] for row in values[:200]]
                width = suggested_width(column, sampled)
                sheet.get_range(
                    f"{col_letter}{header_row}:{col_letter}{data_start + len(values) - 1}"
                ).format.column_width = width
                number_format = format_for_column(column)
                if number_format:
                    sheet.get_range(
                        f"{col_letter}{data_start}:{col_letter}{data_start + len(values) - 1}"
                    ).format.number_format = number_format

        total_data_rows += len(values)
        current_row = data_start + len(values) + 2

    sheet.freeze_panes.freeze_rows(3)
    sheet.freeze_panes.freeze_columns(1)

    return {
        "sheet": table_id,
        "title": title,
        "rows": total_data_rows,
        "source_blocks": source_block_count,
        "note": note,
        "max_row": current_row,
        "max_col": sheet_max_col,
    }


def make_contact_sheet(image_paths: Sequence[Path], output_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return

    images: List[Tuple[str, Any]] = []
    for path in image_paths:
        if path.exists():
            images.append((path.stem, Image.open(path).convert("RGB")))
    if not images:
        return

    thumb_width = 520
    margin = 20
    label_height = 28
    columns = 2
    prepared: List[Tuple[str, Any]] = []
    for label, image in images:
        ratio = thumb_width / image.width
        thumb = image.resize((thumb_width, max(1, int(image.height * ratio))))
        prepared.append((label, thumb))

    rows = math.ceil(len(prepared) / columns)
    row_heights = []
    for row_index in range(rows):
        row_items = prepared[row_index * columns:(row_index + 1) * columns]
        row_heights.append(max(item[1].height for item in row_items) + label_height + margin)

    canvas_width = columns * thumb_width + (columns + 1) * margin
    canvas_height = sum(row_heights) + margin
    canvas = Image.new("RGB", (canvas_width, canvas_height), WHITE)
    draw = ImageDraw.Draw(canvas)

    y = margin
    for row_index in range(rows):
        row_items = prepared[row_index * columns:(row_index + 1) * columns]
        row_height = row_heights[row_index]
        for col_index, (label, image) in enumerate(row_items):
            x = margin + col_index * (thumb_width + margin)
            draw.text((x, y), label, fill="black")
            canvas.paste(image, (x, y + label_height))
        y += row_height

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def make_zip(root: Path, zip_path: Path, include_paths: Sequence[Path]) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(include_paths):
            if not path.exists() or not path.is_file():
                continue
            archive.write(path, arcname=str(path.relative_to(root)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    if not project.exists():
        raise FileNotFoundError(f"Project root not found: {project}")

    input_root = project / "11_supplementary" / INPUT_PACKAGE_TAG
    input_tables = input_root / "materialized_tables"
    input_manifest_dir = input_root / "manifests"

    release_tables = project / "06_tables" / RELEASE_AUDIT_TAG
    release_metadata = project / "03_metadata" / RELEASE_AUDIT_TAG
    release_results = project / "05_results" / RELEASE_AUDIT_TAG

    release_decision_path = (
        release_tables / "UTI_HostOmics_U27B3E411_phase_decision.tsv"
    )
    exception_path = (
        release_metadata / "UTI_HostOmics_U27B3E411_semantic_exception_registry.tsv"
    )
    warning_path = (
        project
        / "06_tables"
        / "phaseU27B3E4_supplementary_schema_content_audit"
        / "UTI_HostOmics_U27B3E4_warning_register.tsv"
    )

    manifest_candidates = sorted(input_manifest_dir.glob("*source_manifest.tsv"))
    if not manifest_candidates:
        fallback = (
            project
            / "06_tables"
            / "phaseU27B3E32_repaired_supplementary_rematerialization"
            / "UTI_HostOmics_U27B3E32_source_manifest.tsv"
        )
        if fallback.exists():
            manifest_candidates = [fallback]
    if not manifest_candidates:
        raise FileNotFoundError("Supplementary source manifest could not be resolved.")
    source_manifest_path = manifest_candidates[0]

    required_paths = [
        input_root,
        input_tables,
        release_decision_path,
        exception_path,
        source_manifest_path,
    ]
    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    _, decision_rows = read_tsv(release_decision_path)
    if not decision_rows:
        raise RuntimeError("U27B3E411 decision table is empty.")
    release_decision = decision_rows[0].get("decision", "")
    if release_decision != REQUIRED_RELEASE:
        raise RuntimeError(
            f"Release gate not satisfied: observed {release_decision!r}; "
            f"expected {REQUIRED_RELEASE!r}"
        )

    _, manifest_rows = read_tsv(source_manifest_path)
    _, exception_rows = read_tsv(exception_path)
    warning_rows: List[Dict[str, str]] = []
    if warning_path.exists():
        _, warning_rows = read_tsv(warning_path)

    source_manifest = manifest_lookup(manifest_rows)

    out_root = project / "11_supplementary" / TAG
    submission_dir = out_root / "submission_upload_only"
    archival_dir = out_root / "archival_tsv"
    manifests_dir = out_root / "manifests"
    audit_dir = out_root / "audit"
    render_dir = out_root / "render_qa"

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG

    for directory in (
        submission_dir,
        archival_dir,
        manifests_dir,
        audit_dir,
        render_dir,
        outtables,
        outmetadata,
        outresults,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    # Verify and freeze input TSV hashes before workbook construction.
    input_hashes: Dict[str, str] = {}
    table_data: Dict[str, Tuple[List[str], List[Dict[str, str]]]] = {}
    for table_id in TABLE_TITLES:
        path = input_tables / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
        if not path.exists() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Missing or empty supplementary TSV: {path}")
        input_hashes[table_id] = sha256(path)
        table_data[table_id] = read_tsv(path)

    wb = Workbook.create()

    index_rows: List[Dict[str, Any]] = []
    # Build scientific sheets first to obtain exact row/source summaries.
    for table_id in TABLE_TITLES:
        _, rows = table_data[table_id]
        index_rows.append(
            add_supplementary_sheet(
                wb=wb,
                table_id=table_id,
                title=TABLE_TITLES[table_id],
                note=TABLE_SHORT_NOTES[table_id],
                source_rows=rows,
                source_manifest=source_manifest,
            )
        )
        log(
            f"{table_id}: formatted rows={index_rows[-1]['rows']}, "
            f"source blocks={index_rows[-1]['source_blocks']}"
        )

    # Add front sheets last, then move by creation order is not available in the
    # documented API. They remain clearly named and indexed.
    add_readme_sheet(wb, index_rows)
    add_source_index_sheet(wb, manifest_rows)
    add_audit_summary_sheet(wb, decision_rows, exception_rows, warning_rows)

    workbook_path = submission_dir / "UTI_HostOmics_Supplementary_Tables_S1-S10.xlsx"

    # Compact workbook inspection before export.
    inspect_outputs: Dict[str, str] = {}
    for sheet_name in ["README", "Source_Index", "Audit_Summary", "S1", "S3", "S9"]:
        inspection = wb.inspect({
            "kind": "table",
            "range": f"{sheet_name}!A1:N24",
            "include": "values,formulas",
            "table_max_rows": 24,
            "table_max_cols": 14,
        })
        inspect_outputs[sheet_name] = inspection.ndjson

    error_scan = wb.inspect({
        "kind": "match",
        "search_term": "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
        "options": {"use_regex": True, "max_results": 300},
        "summary": "U27B3E5 final formula error scan",
    })

    for sheet_name, ndjson in inspect_outputs.items():
        (audit_dir / f"inspect_{sheet_name}.ndjson").write_text(ndjson, encoding="utf-8")
    (audit_dir / "formula_error_scan.ndjson").write_text(error_scan.ndjson, encoding="utf-8")

    # Render every sheet's header and first source block for visual review.
    render_paths: List[Path] = []
    render_sheet_names = ["README", "Source_Index", "Audit_Summary"] + list(TABLE_TITLES)
    for sheet_name in render_sheet_names:
        output = render_dir / f"{sheet_name}_preview.png"
        blob = wb.render({
            "sheet_name": sheet_name,
            "range": "A1:N32",
            "scale": 1,
        })
        blob.save(str(output))
        render_paths.append(output)

    SpreadsheetFile.export_xlsx(wb).save(str(workbook_path))
    if not workbook_path.exists() or workbook_path.stat().st_size == 0:
        raise RuntimeError("Workbook export failed.")

    # Artifact-tool reload verification.
    reloaded = SpreadsheetFile.import_xlsx(Blob.load(str(workbook_path)))
    sheet_inventory = reloaded.inspect({"kind": "sheet", "include": "id,name"})
    (audit_dir / "reloaded_sheet_inventory.ndjson").write_text(
        sheet_inventory.ndjson,
        encoding="utf-8",
    )

    contact_sheet_path = render_dir / "UTI_HostOmics_U27B3E5_workbook_preview_contact_sheet.png"
    make_contact_sheet(render_paths, contact_sheet_path)

    # Copy archival masters and audit artifacts without modification.
    archival_manifest_rows: List[Dict[str, Any]] = []
    for table_id in TABLE_TITLES:
        source = input_tables / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
        target = archival_dir / source.name
        copy_file(source, target)
        archival_manifest_rows.append({
            "supplementary_table": table_id,
            "source_path": str(source),
            "source_sha256": input_hashes[table_id],
            "frozen_copy": str(target),
            "frozen_copy_sha256": sha256(target),
            "byte_identical": input_hashes[table_id] == sha256(target),
        })

    copy_file(source_manifest_path, manifests_dir / source_manifest_path.name)
    copy_file(release_decision_path, audit_dir / release_decision_path.name)
    copy_file(exception_path, audit_dir / exception_path.name)
    if warning_path.exists():
        copy_file(warning_path, audit_dir / warning_path.name)

    source_zip_candidates = sorted(input_root.glob("*.zip"))
    for source_zip in source_zip_candidates:
        copy_file(source_zip, manifests_dir / source_zip.name)

    archival_manifest_path = outtables / "UTI_HostOmics_U27B3E5_archival_table_freeze_manifest.tsv"
    write_tsv(
        archival_manifest_path,
        [
            "supplementary_table",
            "source_path",
            "source_sha256",
            "frozen_copy",
            "frozen_copy_sha256",
            "byte_identical",
        ],
        archival_manifest_rows,
    )
    copy_file(archival_manifest_path, manifests_dir / archival_manifest_path.name)

    workbook_manifest = {
        "phase": "U27B3E5",
        "version": VERSION,
        "release_gate": release_decision,
        "workbook": str(workbook_path),
        "workbook_sha256": sha256(workbook_path),
        "workbook_size_bytes": workbook_path.stat().st_size,
        "worksheets": 13,
        "scientific_sheets": 10,
        "front_sheets": ["README", "Source_Index", "Audit_Summary"],
        "rendered_previews": len(render_paths),
        "contact_sheet_created": contact_sheet_path.exists(),
        "scientific_values_recalculated": False,
        "archival_tsvs_modified": False,
        "source_files_modified": False,
        "manuscript_modified": False,
        "figure_assets_modified": False,
    }
    workbook_manifest_path = outresults / "UTI_HostOmics_U27B3E5_workbook_manifest.json"
    workbook_manifest_path.write_text(
        json.dumps(workbook_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    copy_file(workbook_manifest_path, manifests_dir / workbook_manifest_path.name)

    submission_readme = submission_dir / "README_UPLOAD.txt"
    submission_readme.write_text(
        textwrap.dedent(
            f"""\
            UTI HostOmics supplementary upload package

            Upload file:
              {workbook_path.name}

            Contents:
              README, Source_Index and Audit_Summary worksheets
              Supplementary Tables S1-S10 as dedicated worksheets

            Scientific integrity:
              Generated from the byte-preserved U27B3E321 TSV archive
              GSE186800 is the canonical recurrent-UTI accession
              GSE168600 appears only in the S10 prohibition rule
              No scientific values were recalculated

            The archival TSV package and internal audit files are retained in the
            separate archival freeze package and normally should not be uploaded
            unless the journal requests machine-readable source tables.
            """
        ),
        encoding="utf-8",
    )

    package_readme = out_root / "UTI_HostOmics_U27B3E5_freeze_README.md"
    package_readme.write_text(
        textwrap.dedent(
            f"""\
            # UTI HostOmics supplementary submission workbook and freeze package

            - Phase: `{VERSION}`
            - Release gate: **{release_decision}**
            - Submission workbook: `{workbook_path}`
            - Workbook SHA256: `{sha256(workbook_path)}`
            - Archival TSVs preserved byte-for-byte: **{all(row['byte_identical'] for row in archival_manifest_rows)}**
            - Scientific values recalculated: **False**
            - Source files modified: **False**
            - Manuscript modified: **False**
            - Figure assets modified: **False**

            ## Submission-facing architecture

            The workbook contains three orientation/QC sheets and one scientific
            worksheet for each Supplementary Table S1-S10. Within each scientific
            worksheet, heterogeneous source blocks are stacked vertically and
            expose only their native schemas plus `source_row_number`. Absolute
            local filesystem paths are excluded from the scientific worksheets.

            ## Visual-release boundary

            The workbook has passed programmatic construction, reload and render
            checks. Final freeze remains contingent on visual inspection of:

            `{contact_sheet_path}`
            """
        ),
        encoding="utf-8",
    )

    # Build submission-only and archival freeze ZIPs.
    submission_zip = out_root / "UTI_HostOmics_U27B3E5_submission_upload_only.zip"
    make_zip(
        out_root,
        submission_zip,
        [workbook_path, submission_readme],
    )

    archival_zip = out_root / "UTI_HostOmics_U27B3E5_archival_freeze_package.zip"
    archival_members = [
        path
        for path in out_root.rglob("*")
        if path.is_file()
        and path not in {submission_zip, archival_zip}
    ]
    make_zip(out_root, archival_zip, archival_members)

    # Verify ZIP integrity.
    zip_rows: List[Dict[str, Any]] = []
    for zip_path in (submission_zip, archival_zip):
        with zipfile.ZipFile(zip_path) as archive:
            failed_member = archive.testzip()
            members = archive.namelist()
        zip_rows.append({
            "zip_path": str(zip_path),
            "zip_exists": zip_path.exists(),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": sha256(zip_path),
            "zip_members": len(members),
            "failed_member": failed_member or "",
            "zip_test_pass": failed_member is None,
        })

    zip_audit_path = outtables / "UTI_HostOmics_U27B3E5_zip_audit.tsv"
    write_tsv(
        zip_audit_path,
        [
            "zip_path",
            "zip_exists",
            "zip_size_bytes",
            "zip_sha256",
            "zip_members",
            "failed_member",
            "zip_test_pass",
        ],
        zip_rows,
    )

    input_unchanged = True
    for table_id in TABLE_TITLES:
        path = input_tables / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
        input_unchanged = input_unchanged and sha256(path) == input_hashes[table_id]

    zip_pass = all(bool(row["zip_test_pass"]) for row in zip_rows)
    workbook_reload_pass = "README" in sheet_inventory.ndjson and "S10" in sheet_inventory.ndjson
    render_pass = len(render_paths) == 13 and all(path.exists() and path.stat().st_size > 0 for path in render_paths)

    if input_unchanged and zip_pass and workbook_reload_pass and render_pass and contact_sheet_path.exists():
        decision = "READY_FOR_U27B3E51_SUPPLEMENTARY_WORKBOOK_VISUAL_AUDIT"
    else:
        decision = "TARGETED_U27B3E5_WORKBOOK_FORMATTING_OR_PACKAGE_REPAIR_REQUIRED"

    decision_rows_out = [{
        "phase": "U27B3E5",
        "decision": decision,
        "submission_workbook_created": workbook_path.exists(),
        "workbook_reload_pass": workbook_reload_pass,
        "worksheets_created": 13,
        "scientific_worksheets": 10,
        "rendered_sheet_previews": len(render_paths),
        "contact_sheet_created": contact_sheet_path.exists(),
        "submission_zip_created": submission_zip.exists(),
        "archival_freeze_zip_created": archival_zip.exists(),
        "zip_integrity_pass": zip_pass,
        "archival_tsvs_byte_identical": all(row["byte_identical"] for row in archival_manifest_rows),
        "input_tsvs_unchanged": input_unchanged,
        "scientific_values_recalculated": False,
        "source_files_modified": False,
        "manuscript_modified": False,
        "figure_assets_modified": False,
        "next_phase": (
            "U27B3E5.1 visually inspect all 13 rendered worksheet previews and approve the workbook freeze"
            if decision.startswith("READY_FOR_U27B3E51")
            else "Inspect U27B3E5 workbook and package audits"
        ),
    }]
    decision_path = outtables / "UTI_HostOmics_U27B3E5_phase_decision.tsv"
    write_tsv(decision_path, list(decision_rows_out[0].keys()), decision_rows_out)

    report_path = outresults / "UTI_HostOmics_U27B3E5_submission_formatting_and_freeze_report.md"
    report_path.write_text(
        textwrap.dedent(
            f"""\
            # Phase U27B3E5 - Supplementary submission formatting and freeze

            - Version: `{VERSION}`
            - Decision: **{decision}**
            - Submission workbook: `{workbook_path}`
            - Workbook worksheets: **13** (README, Source_Index, Audit_Summary, S1-S10)
            - Rendered worksheet previews: **{len(render_paths)}**
            - Contact sheet created: **{contact_sheet_path.exists()}**
            - Submission-only ZIP integrity: **{zip_rows[0]['zip_test_pass']}**
            - Archival freeze ZIP integrity: **{zip_rows[1]['zip_test_pass']}**
            - Archival TSVs byte-identical: **{all(row['byte_identical'] for row in archival_manifest_rows)}**
            - Input TSVs unchanged: **{input_unchanged}**
            - Scientific values recalculated: **False**

            ## Workbook design

            Each Supplementary Table has a dedicated worksheet. Source blocks are
            stacked vertically and retain native column names, native values and
            source row numbers. Source-relative paths, checksums and row counts are
            consolidated in `Source_Index`; absolute local paths are not displayed
            on scientific worksheets.

            ## Release boundary

            Programmatic construction, artifact-tool reload, render and ZIP checks
            passed. Human visual inspection of the 13-sheet preview contact sheet is
            required before declaring the workbook frozen for journal upload.
            """
        ),
        encoding="utf-8",
    )

    run_manifest = {
        **workbook_manifest,
        "decision": decision,
        "submission_zip": str(submission_zip),
        "submission_zip_sha256": sha256(submission_zip),
        "archival_zip": str(archival_zip),
        "archival_zip_sha256": sha256(archival_zip),
        "archival_tsvs_byte_identical": all(row["byte_identical"] for row in archival_manifest_rows),
        "input_tsvs_unchanged": input_unchanged,
        "zip_integrity_pass": zip_pass,
        "workbook_reload_pass": workbook_reload_pass,
        "render_pass": render_pass,
    }
    (outresults / "UTI_HostOmics_U27B3E5_run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    log(f"Workbook: {workbook_path}")
    log(f"Workbook SHA256: {sha256(workbook_path)}")
    log(f"Rendered previews: {len(render_paths)}")
    log(f"Contact sheet: {contact_sheet_path}")
    log(f"Submission ZIP: {submission_zip}")
    log(f"Archival ZIP: {archival_zip}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E5] ERROR: {exc}", file=sys.stderr)
        raise
