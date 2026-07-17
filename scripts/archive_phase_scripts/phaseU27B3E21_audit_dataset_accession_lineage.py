#!/usr/bin/env python3
"""
Phase U27B3E2.1
Audit and resolve the GSE186800 versus GSE168600 accession-lineage conflict.

External accession identities verified against NCBI GEO:
- GSE186800: Gardnerella vaginalis activates host responses necessary for
  Escherichia coli recurrent UTI from bladder reservoirs.
- GSE168600: KLF5 governs sphingolipid metabolism and barrier function of skin.

This phase is read-only. It:
1. scans project text, scripts, SVGs, DOCX XML and PDF text for both accessions;
2. inventories source-data, design and analysis files carrying each accession;
3. inspects candidate design tables for sample counts and biological labels;
4. separates computational-source evidence from manuscript/figure-label usage;
5. identifies every file requiring accession correction;
6. releases a targeted correction phase only after local lineage is verified.

No manuscript, figure, table, script, source lock or scientific value is modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

import pandas as pd


VERSION = "U27B3E21_v1.0_2026-07-16"
TAG = "phaseU27B3E21_dataset_accession_lineage_audit"

CORRECT_ACCESSION = "GSE186800"
INCORRECT_ACCESSION = "GSE168600"

OFFICIAL_IDENTITIES = {
    "GSE186800": (
        "Gardnerella vaginalis activates host responses necessary for "
        "Escherichia coli recurrent UTI from bladder reservoirs"
    ),
    "GSE168600": (
        "KLF5 governs sphingolipid metabolism and barrier function of the skin"
    ),
}

TEXT_EXTENSIONS = {
    ".txt", ".tsv", ".csv", ".md", ".json", ".yaml", ".yml",
    ".py", ".sh", ".r", ".R", ".svg", ".xml", ".html", ".htm",
    ".tex", ".log",
}

OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
PDF_EXTENSION = ".pdf"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".cache",
    "node_modules",
    "render_qa",
}

SOURCE_EVIDENCE_HINTS = (
    "03_data",
    "03_metadata",
    "phaseU26",
    "phaseU8",
    "matrix",
    "expression",
    "design",
    "contrast",
    "effect",
    "pseudobulk",
    "counts",
)

LABEL_OR_MANUSCRIPT_HINTS = (
    "09_manuscript",
    "07_manuscript",
    "06_figures",
    "phaseU27",
    "legend",
    "figure",
    "manuscript",
    "audit",
    "report",
)


def log(message: str) -> None:
    print(f"[U27B3E2.1] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def should_skip(path: Path, project: Path) -> bool:
    try:
        relative = path.relative_to(project)
    except ValueError:
        relative = path

    return any(part in SKIP_DIRS for part in relative.parts)


def classify_path(path: Path) -> str:
    lower = str(path).lower()

    source_score = sum(
        1 for hint in SOURCE_EVIDENCE_HINTS if hint.lower() in lower
    )
    label_score = sum(
        1 for hint in LABEL_OR_MANUSCRIPT_HINTS if hint.lower() in lower
    )

    if source_score > label_score:
        return "COMPUTATIONAL_OR_SOURCE_EVIDENCE"
    if label_score > source_score:
        return "MANUSCRIPT_FIGURE_LEGEND_OR_AUDIT"
    return "UNCLASSIFIED_PROJECT_FILE"


def decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_office_text(path: Path) -> str:
    pieces: List[str] = []

    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                lower = name.lower()
                if not lower.endswith(".xml"):
                    continue
                if not (
                    lower.startswith("word/")
                    or lower.startswith("ppt/")
                    or lower.startswith("xl/")
                ):
                    continue

                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError:
                    continue

                for node in root.iter():
                    local = node.tag.rsplit("}", 1)[-1]
                    if local in {"t", "v"} and node.text:
                        pieces.append(node.text)
    except (zipfile.BadZipFile, OSError):
        return ""

    return "\n".join(pieces)


def extract_pdf_text(path: Path) -> str:
    executable = subprocess.run(
        ["sh", "-c", "command -v pdftotext"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    ).stdout.strip()

    if not executable:
        return ""

    with tempfile.TemporaryDirectory(prefix="u27b3e21_pdf_") as tmp:
        output = Path(tmp) / "out.txt"
        result = subprocess.run(
            [executable, str(path), str(output)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0 or not output.exists():
            return ""
        return output.read_text(encoding="utf-8", errors="ignore")


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()

    try:
        if suffix in TEXT_EXTENSIONS:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix in OFFICE_EXTENSIONS:
            return extract_office_text(path)
        if suffix == PDF_EXTENSION:
            return extract_pdf_text(path)
    except OSError:
        return ""

    return ""


def context_windows(
    text: str,
    term: str,
    width: int = 110,
    limit: int = 8,
) -> List[str]:
    windows = []
    for match in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
        start = max(0, match.start() - width)
        end = min(len(text), match.end() + width)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        windows.append(snippet)
        if len(windows) >= limit:
            break
    return windows


def inspect_delimited_file(path: Path) -> Dict[str, object]:
    result: Dict[str, object] = {
        "path": str(path),
        "read_success": False,
        "rows": "",
        "columns": "",
        "column_names": "",
        "pbs_hits": 0,
        "gardnerella_hits": 0,
        "upec_hits": 0,
        "skin_hits": 0,
        "klf5_hits": 0,
        "sample_like_values_preview": "",
    }

    try:
        separator = "\t" if path.suffix.lower() == ".tsv" else ","
        frame = pd.read_csv(
            path,
            sep=separator,
            low_memory=False,
            nrows=5000,
        )
    except Exception:
        return result

    result["read_success"] = True
    result["rows"] = len(frame)
    result["columns"] = len(frame.columns)
    result["column_names"] = "; ".join(str(c) for c in frame.columns)

    joined = " ".join(
        frame.astype(str)
        .fillna("")
        .head(5000)
        .to_numpy()
        .ravel()
        .tolist()
    ).lower()

    result["pbs_hits"] = joined.count("pbs")
    result["gardnerella_hits"] = (
        joined.count("gard")
        + joined.count("g. vaginalis")
        + joined.count("gardnerella")
    )
    result["upec_hits"] = joined.count("upec")
    result["skin_hits"] = joined.count("skin")
    result["klf5_hits"] = joined.count("klf5")

    preview_values: List[str] = []
    for column in frame.columns:
        lower = str(column).lower()
        if any(token in lower for token in ("sample", "title", "group", "condition")):
            preview_values.extend(
                frame[column]
                .dropna()
                .astype(str)
                .drop_duplicates()
                .head(12)
                .tolist()
            )

    result["sample_like_values_preview"] = "; ".join(preview_values[:30])
    return result


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

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG

    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    scan_rows: List[Dict[str, object]] = []
    candidate_design_paths: List[Path] = []
    files_scanned = 0

    for path in project.rglob("*"):
        if not path.is_file() or should_skip(path, project):
            continue

        suffix = path.suffix.lower()
        if (
            suffix not in TEXT_EXTENSIONS
            and suffix not in OFFICE_EXTENSIONS
            and suffix != PDF_EXTENSION
        ):
            continue

        files_scanned += 1
        text = extract_text(path)
        if not text:
            continue

        correct_count = len(
            re.findall(
                re.escape(CORRECT_ACCESSION),
                text,
                flags=re.IGNORECASE,
            )
        )
        incorrect_count = len(
            re.findall(
                re.escape(INCORRECT_ACCESSION),
                text,
                flags=re.IGNORECASE,
            )
        )

        if correct_count == 0 and incorrect_count == 0:
            continue

        classification = classify_path(path)

        scan_rows.append(
            {
                "path": str(path),
                "relative_path": str(path.relative_to(project)),
                "suffix": suffix,
                "classification": classification,
                "GSE186800_occurrences": correct_count,
                "GSE168600_occurrences": incorrect_count,
                "GSE186800_context": " || ".join(
                    context_windows(text, CORRECT_ACCESSION)
                ),
                "GSE168600_context": " || ".join(
                    context_windows(text, INCORRECT_ACCESSION)
                ),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

        lower_name = path.name.lower()
        if (
            suffix in {".tsv", ".csv"}
            and any(
                token in lower_name
                for token in (
                    "design", "metadata", "sample", "contrast", "matrix"
                )
            )
            and (
                CORRECT_ACCESSION.lower() in lower_name
                or INCORRECT_ACCESSION.lower() in lower_name
            )
        ):
            candidate_design_paths.append(path)

    scan_frame = pd.DataFrame(scan_rows)
    if scan_frame.empty:
        scan_frame = pd.DataFrame(
            columns=[
                "path",
                "relative_path",
                "suffix",
                "classification",
                "GSE186800_occurrences",
                "GSE168600_occurrences",
                "GSE186800_context",
                "GSE168600_context",
                "size_bytes",
                "sha256",
            ]
        )

    scan_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E21_accession_occurrence_inventory.tsv",
        sep="\t",
        index=False,
    )

    design_rows = [
        inspect_delimited_file(path)
        for path in sorted(set(candidate_design_paths))
    ]
    design_frame = pd.DataFrame(design_rows)
    if design_frame.empty:
        design_frame = pd.DataFrame(
            columns=[
                "path",
                "read_success",
                "rows",
                "columns",
                "column_names",
                "pbs_hits",
                "gardnerella_hits",
                "upec_hits",
                "skin_hits",
                "klf5_hits",
                "sample_like_values_preview",
            ]
        )

    design_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E21_design_and_matrix_identity_audit.tsv",
        sep="\t",
        index=False,
    )

    summary_rows: List[Dict[str, object]] = []
    for accession in (CORRECT_ACCESSION, INCORRECT_ACCESSION):
        column = f"{accession}_occurrences"
        present = scan_frame[column] > 0 if not scan_frame.empty else pd.Series(dtype=bool)

        for classification in (
            "COMPUTATIONAL_OR_SOURCE_EVIDENCE",
            "MANUSCRIPT_FIGURE_LEGEND_OR_AUDIT",
            "UNCLASSIFIED_PROJECT_FILE",
        ):
            subset = scan_frame[
                present
                & (scan_frame["classification"] == classification)
            ]
            summary_rows.append(
                {
                    "accession": accession,
                    "official_identity": OFFICIAL_IDENTITIES[accession],
                    "classification": classification,
                    "files": len(subset),
                    "occurrences": int(
                        subset[column].sum()
                    ) if not subset.empty else 0,
                }
            )

    summary_frame = pd.DataFrame(summary_rows)
    summary_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E21_accession_lineage_summary.tsv",
        sep="\t",
        index=False,
    )

    correct_source_files = int(
        (
            (scan_frame["classification"] == "COMPUTATIONAL_OR_SOURCE_EVIDENCE")
            & (scan_frame["GSE186800_occurrences"] > 0)
        ).sum()
    ) if not scan_frame.empty else 0

    incorrect_source_files = int(
        (
            (scan_frame["classification"] == "COMPUTATIONAL_OR_SOURCE_EVIDENCE")
            & (scan_frame["GSE168600_occurrences"] > 0)
        ).sum()
    ) if not scan_frame.empty else 0

    incorrect_label_files = int(
        (
            (scan_frame["classification"] == "MANUSCRIPT_FIGURE_LEGEND_OR_AUDIT")
            & (scan_frame["GSE168600_occurrences"] > 0)
        ).sum()
    ) if not scan_frame.empty else 0

    recurrent_design_support = False
    if not design_frame.empty:
        numeric = design_frame.copy()
        for column in (
            "pbs_hits",
            "gardnerella_hits",
            "upec_hits",
            "skin_hits",
            "klf5_hits",
        ):
            numeric[column] = pd.to_numeric(
                numeric[column],
                errors="coerce",
            ).fillna(0)

        recurrent_design_support = bool(
            (
                numeric["path"]
                .astype(str)
                .str.contains(CORRECT_ACCESSION, case=False, na=False)
            )
            .where(
                (numeric["pbs_hits"] > 0)
                | (numeric["gardnerella_hits"] > 0)
                | (numeric["upec_hits"] > 0),
                False,
            )
            .any()
        )

    if (
        correct_source_files > 0
        and recurrent_design_support
        and incorrect_label_files > 0
    ):
        decision = (
            "READY_FOR_U27B3E22_TARGETED_ACCESSION_CORRECTION_"
            "GSE168600_TO_GSE186800"
        )
    else:
        decision = (
            "MANUAL_DATASET_LINEAGE_RESOLUTION_REQUIRED_BEFORE_CORRECTION"
        )

    correction_targets = scan_frame[
        scan_frame["GSE168600_occurrences"] > 0
    ].copy()
    if not correction_targets.empty:
        correction_targets["recommended_action"] = correction_targets[
            "classification"
        ].map(
            {
                "MANUSCRIPT_FIGURE_LEGEND_OR_AUDIT": (
                    "Replace GSE168600 with GSE186800, then re-audit and "
                    "re-freeze affected derivative assets."
                ),
                "COMPUTATIONAL_OR_SOURCE_EVIDENCE": (
                    "Inspect manually; GSE168600 should not be part of the "
                    "UTI computational lineage."
                ),
                "UNCLASSIFIED_PROJECT_FILE": (
                    "Inspect and classify before correction."
                ),
            }
        )

    correction_targets.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E21_accession_correction_target_registry.tsv",
        sep="\t",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "phase": "U27B3E2.1",
                "decision": decision,
                "files_scanned": files_scanned,
                "files_with_accession_mentions": len(scan_frame),
                "GSE186800_computational_source_files": correct_source_files,
                "GSE168600_computational_source_files": incorrect_source_files,
                "GSE168600_manuscript_figure_legend_audit_files": (
                    incorrect_label_files
                ),
                "recurrent_UTI_design_support_for_GSE186800": (
                    recurrent_design_support
                ),
                "manuscript_modified": False,
                "figure_assets_modified": False,
                "scientific_values_recalculated": False,
                "source_locks_changed": False,
                "supplementary_materialization_allowed": False,
                "next_phase": (
                    "U27B3E2.2 correct GSE168600 labels to GSE186800 across "
                    "manuscript, figures, legends, registries and audits; "
                    "then rebuild affected frozen assets"
                    if decision.startswith("READY_FOR_U27B3E22")
                    else "Review lineage evidence manually"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B3E21_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "field": "correct_accession",
                "value": CORRECT_ACCESSION,
            },
            {
                "field": "correct_official_identity",
                "value": OFFICIAL_IDENTITIES[CORRECT_ACCESSION],
            },
            {
                "field": "incorrect_accession",
                "value": INCORRECT_ACCESSION,
            },
            {
                "field": "incorrect_official_identity",
                "value": OFFICIAL_IDENTITIES[INCORRECT_ACCESSION],
            },
            {
                "field": "audit_scope",
                "value": "read_only_project_wide_accession_lineage",
            },
        ]
    ).to_csv(
        outmetadata
        / "UTI_HostOmics_U27B3E21_accession_identity_record.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3E21_dataset_accession_lineage_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3E2.1 - Dataset accession-lineage audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Correct recurrent-UTI accession: **{CORRECT_ACCESSION}**.\n"
        )
        handle.write(
            f"- Correct identity: {OFFICIAL_IDENTITIES[CORRECT_ACCESSION]}.\n"
        )
        handle.write(
            f"- Incorrect substituted accession: **{INCORRECT_ACCESSION}**.\n"
        )
        handle.write(
            f"- Incorrect identity: {OFFICIAL_IDENTITIES[INCORRECT_ACCESSION]}.\n"
        )
        handle.write(
            f"- Project files scanned: **{files_scanned}**.\n"
        )
        handle.write(
            f"- GSE186800 computational/source files: "
            f"**{correct_source_files}**.\n"
        )
        handle.write(
            f"- GSE168600 computational/source files: "
            f"**{incorrect_source_files}**.\n"
        )
        handle.write(
            f"- GSE168600 manuscript/figure/legend/audit files: "
            f"**{incorrect_label_files}**.\n"
        )
        handle.write(
            f"- Recurrent-UTI sample-design support for GSE186800: "
            f"**{recurrent_design_support}**.\n\n"
        )

        handle.write("## Scientific interpretation\n\n")
        handle.write(
            "The accession conflict must be resolved before supplementary "
            "table materialization or submission finalization. GSE168600 is "
            "not a urinary-tract dataset. If local matrices and sample labels "
            "trace to GSE186800, the numerical analyses may remain valid while "
            "the manuscript, figures, legends and provenance records require "
            "systematic accession correction and re-freezing.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "This phase is read-only. No manuscript, figure, table, script, "
            "scientific value or source lock was modified.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "files_scanned": files_scanned,
        "files_with_mentions": len(scan_frame),
        "GSE186800_source_files": correct_source_files,
        "GSE168600_source_files": incorrect_source_files,
        "GSE168600_label_files": incorrect_label_files,
        "recurrent_design_support": recurrent_design_support,
        "manuscript_modified": False,
        "figure_assets_modified": False,
        "scientific_values_recalculated": False,
        "source_locks_changed": False,
        "supplementary_materialization_allowed": False,
    }
    (
        outresults
        / "UTI_HostOmics_U27B3E21_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Files scanned: {files_scanned}")
    log(f"GSE186800 source files: {correct_source_files}")
    log(f"GSE168600 source files: {incorrect_source_files}")
    log(f"GSE168600 label/audit files: {incorrect_label_files}")
    log(f"Recurrent design support: {recurrent_design_support}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E2.1] ERROR: {exc}", file=sys.stderr)
        raise
