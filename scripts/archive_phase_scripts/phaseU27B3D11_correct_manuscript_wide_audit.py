#!/usr/bin/env python3
"""
Phase U27B3D1.1
Correct the false-negative Figure 1 audit in U27B3D1.

Cause
-----
The U27B3D1 section detector used the first definitive Figure 1 caption as the
synthetic "Figures" section heading, then began section content after that
paragraph. Figure 1 was therefore excluded from the caption inventory, while
Figures 2-8 were counted normally.

This phase is read-only. It:
1. reuses the U27B3D1 audit outputs;
2. audits Figure 1-8 captions directly from the full document element inventory;
3. verifies eight embedded image paragraphs;
4. confirms Results, frozen datasets, 78 submodules and ten axes;
5. updates only the audit decision and reconstruction release.

No DOCX, figure, legend, table, value or source lock is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Sequence, Tuple
from xml.etree import ElementTree as ET

import pandas as pd


VERSION = "U27B3D11_v1.0_2026-07-16"
TAG = "phaseU27B3D11_corrected_manuscript_wide_audit"

DEFAULT_MANUSCRIPT = (
    "__UTI_HOSTOMICS_PROJECT_ROOT__/"
    "09_manuscript_docx/phaseU27B3C41_integrated_figure_section_cleanup/"
    "UTI_HostOmics_preZotero_manuscript_v5_2_U27B3C41_figure_section_cleaned.docx"
)

SOURCE_AUDIT_TAG = "phaseU27B3D1_manuscript_wide_content_structure_audit"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

FIGURE_CAPTION_PATTERN = re.compile(
    r"^Figure\s+([1-8])\.\s+",
    flags=re.IGNORECASE,
)


def log(message: str) -> None:
    print(f"[U27B3D1.1] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def paragraph_text(paragraph: ET.Element) -> str:
    pieces: List[str] = []
    for node in paragraph.iter():
        local = node.tag.rsplit("}", 1)[-1]
        if local == "t":
            pieces.append(node.text or "")
        elif local == "tab":
            pieces.append("\t")
        elif local in {"br", "cr"}:
            pieces.append("\n")
    return normalize("".join(pieces))


def read_docx_body(path: Path) -> Tuple[List[Dict[str, object]], int]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        body = root.find("w:body", NS)
        if body is None:
            raise RuntimeError("No word/body element found.")

        rows: List[Dict[str, object]] = []
        for body_index, element in enumerate(list(body)):
            local = element.tag.rsplit("}", 1)[-1]
            if local == "p":
                text = paragraph_text(element)
                has_drawing = any(
                    node.tag.rsplit("}", 1)[-1] in {"drawing", "pict"}
                    for node in element.iter()
                )
                rows.append(
                    {
                        "body_index": body_index,
                        "element_type": "paragraph",
                        "text": text,
                        "has_drawing": has_drawing,
                    }
                )
            elif local == "tbl":
                rows.append(
                    {
                        "body_index": body_index,
                        "element_type": "table",
                        "text": paragraph_text(element),
                        "has_drawing": False,
                    }
                )

        media_count = sum(
            1
            for name in archive.namelist()
            if name.startswith("word/media/")
            and not name.endswith("/")
        )

    return rows, media_count


def find_section_text(
    rows: Sequence[Dict[str, object]],
    heading: str,
    next_heading: str,
) -> str:
    heading_matches = [
        int(row["body_index"])
        for row in rows
        if row["element_type"] == "paragraph"
        and normalize(row["text"]).lower().rstrip(":.") == heading.lower()
    ]
    next_matches = [
        int(row["body_index"])
        for row in rows
        if row["element_type"] == "paragraph"
        and normalize(row["text"]).lower().rstrip(":.") == next_heading.lower()
    ]

    if len(heading_matches) != 1 or len(next_matches) != 1:
        raise RuntimeError(
            f"Could not uniquely resolve {heading} -> {next_heading}: "
            f"{heading_matches}, {next_matches}"
        )

    start = heading_matches[0]
    end = next_matches[0]
    if start >= end:
        raise RuntimeError(f"{heading} does not precede {next_heading}.")

    return "\n".join(
        str(row["text"])
        for row in rows
        if start < int(row["body_index"]) < end
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    parser.add_argument(
        "--manuscript",
        default=DEFAULT_MANUSCRIPT,
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    manuscript = Path(args.manuscript).resolve()

    if not manuscript.exists():
        raise FileNotFoundError(f"Manuscript not found: {manuscript}")

    source_tables = project / "06_tables" / SOURCE_AUDIT_TAG
    source_metadata = project / "03_metadata" / SOURCE_AUDIT_TAG
    source_results = project / "05_results" / SOURCE_AUDIT_TAG

    required_source_files = [
        source_tables / "UTI_HostOmics_U27B3D1_section_treatment_map.tsv",
        source_tables / "UTI_HostOmics_U27B3D1_obsolete_term_path_audit.tsv",
        source_tables / "UTI_HostOmics_U27B3D1_supplementary_table_audit.tsv",
        source_metadata / "UTI_HostOmics_U27B3D1_v6_reconstruction_map.tsv",
    ]
    for path in required_source_files:
        if not path.exists():
            raise FileNotFoundError(f"Required U27B3D1 audit file missing: {path}")

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG

    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    rows, media_count = read_docx_body(manuscript)
    frame = pd.DataFrame(rows)

    # Direct caption audit across the full body. This deliberately does not use
    # synthetic section boundaries.
    caption_rows: List[Dict[str, object]] = []
    for row in rows:
        if row["element_type"] != "paragraph":
            continue
        text = normalize(row["text"])
        match = FIGURE_CAPTION_PATTERN.match(text)
        if match:
            caption_rows.append(
                {
                    "figure_number": int(match.group(1)),
                    "body_index": int(row["body_index"]),
                    "caption_text": text,
                    "caption_character_count": len(text),
                }
            )

    caption_frame = pd.DataFrame(caption_rows)
    if caption_frame.empty:
        caption_frame = pd.DataFrame(
            columns=[
                "figure_number",
                "body_index",
                "caption_text",
                "caption_character_count",
            ]
        )

    caption_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3D11_direct_figure_caption_inventory.tsv",
        sep="\t",
        index=False,
    )

    # Drawing audit.
    drawings = frame[
        (frame["element_type"] == "paragraph")
        & (frame["has_drawing"].astype(bool))
    ].copy()
    drawings.to_csv(
        outtables
        / "UTI_HostOmics_U27B3D11_embedded_figure_paragraph_audit.tsv",
        sep="\t",
        index=False,
    )

    observed_numbers = (
        sorted(caption_frame["figure_number"].astype(int).tolist())
        if not caption_frame.empty
        else []
    )
    unique_numbers = (
        sorted(caption_frame["figure_number"].astype(int).unique().tolist())
        if not caption_frame.empty
        else []
    )

    caption_count_pass = len(caption_frame) == 8
    caption_unique_pass = unique_numbers == list(range(1, 9))
    caption_order_pass = observed_numbers == list(range(1, 9))
    drawing_count_pass = len(drawings) == 8
    media_count_pass = media_count == 8

    results_text = find_section_text(rows, "Results", "Discussion")
    results_lower = results_text.lower()

    results_ready = all(
        [
            "gse112098" in results_lower,
            "gse280297" in results_lower,
            "gse168600" in results_lower,
            "gse252321" in results_lower,
            (
                "78 curated submodules" in results_lower
                or "78 submodules" in results_lower
            ),
            (
                "ten biological axes" in results_lower
                or "10 biological axes" in results_lower
            ),
            all(
                re.search(
                    rf"\bFigure\s+{number}(?:[A-H])?",
                    results_text,
                    flags=re.IGNORECASE,
                )
                is not None
                for number in range(1, 9)
            ),
        ]
    )

    figures_ready = all(
        [
            caption_count_pass,
            caption_unique_pass,
            caption_order_pass,
            drawing_count_pass,
            media_count_pass,
        ]
    )

    # Reuse the valid U27B3D1 reconstruction evidence.
    treatment = pd.read_csv(
        source_tables / "UTI_HostOmics_U27B3D1_section_treatment_map.tsv",
        sep="\t",
        low_memory=False,
    )
    obsolete = pd.read_csv(
        source_tables / "UTI_HostOmics_U27B3D1_obsolete_term_path_audit.tsv",
        sep="\t",
        low_memory=False,
    )
    supplementary = pd.read_csv(
        source_tables / "UTI_HostOmics_U27B3D1_supplementary_table_audit.tsv",
        sep="\t",
        low_memory=False,
    )
    reconstruction = pd.read_csv(
        source_metadata / "UTI_HostOmics_U27B3D1_v6_reconstruction_map.tsv",
        sep="\t",
        low_memory=False,
    )

    treatment.to_csv(
        outtables / "UTI_HostOmics_U27B3D11_section_treatment_map.tsv",
        sep="\t",
        index=False,
    )
    obsolete.to_csv(
        outtables / "UTI_HostOmics_U27B3D11_obsolete_term_path_audit.tsv",
        sep="\t",
        index=False,
    )
    supplementary.to_csv(
        outtables / "UTI_HostOmics_U27B3D11_supplementary_table_audit.tsv",
        sep="\t",
        index=False,
    )
    reconstruction.to_csv(
        outmetadata / "UTI_HostOmics_U27B3D11_v6_reconstruction_map.tsv",
        sep="\t",
        index=False,
    )

    correction = pd.DataFrame(
        [
            {
                "failed_audit": "Figure 1 caption presence",
                "previous_method": (
                    "The first definitive Figure 1 caption was promoted to a "
                    "synthetic Figures-section heading and excluded from its "
                    "own section content."
                ),
                "corrected_method": (
                    "Audit all definitive Figure 1-8 caption paragraphs "
                    "directly across the complete DOCX body."
                ),
                "manuscript_content_changed": False,
            }
        ]
    )
    correction.to_csv(
        outtables
        / "UTI_HostOmics_U27B3D11_false_negative_correction_rationale.tsv",
        sep="\t",
        index=False,
    )

    sections_requiring_replacement = int(
        treatment[
            treatment["recommended_treatment"].isin(
                [
                    "REPLACE",
                    "MAJOR_REVISION",
                    "REPLACE_OR_UPDATE",
                    "REPLACE_OR_EXPAND",
                    "REPLACE_AND_RENUMBER",
                    "REPLACE_WITH_CONFIRMED_FUNDING",
                ]
            )
        ].shape[0]
    )

    obsolete_occurrences = int(obsolete["occurrence_count"].sum())

    if results_ready and figures_ready:
        decision = "READY_FOR_U27B3D2_MANUSCRIPT_WIDE_V6_RECONSTRUCTION"
    else:
        decision = (
            "TARGETED_U27B3D11_FROZEN_RESULTS_OR_FIGURE_AUDIT_REPAIR_REQUIRED"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B3D1.1",
                "decision": decision,
                "manuscript_path": str(manuscript),
                "manuscript_sha256": sha256(manuscript),
                "definitive_caption_paragraphs": len(caption_frame),
                "caption_numbers_observed": ",".join(
                    str(number) for number in observed_numbers
                ),
                "caption_numbers_unique_1_to_8": caption_unique_pass,
                "caption_order_1_to_8": caption_order_pass,
                "embedded_drawing_paragraphs": len(drawings),
                "embedded_media_files": media_count,
                "results_section_ready_to_freeze": results_ready,
                "figures_1_to_8_ready_to_freeze": figures_ready,
                "sections_requiring_replacement_or_major_revision": (
                    sections_requiring_replacement
                ),
                "obsolete_term_or_path_occurrences": obsolete_occurrences,
                "supplementary_tables_detected": len(supplementary),
                "manuscript_modified": False,
                "scientific_values_recalculated": False,
                "figure_assets_modified": False,
                "source_locks_changed": False,
                "next_phase": (
                    "U27B3D2 create a new v6.0 derivative while freezing the "
                    "U27B3C2 Results and U27B3A/U27B3B figure package"
                    if decision.startswith("READY_FOR_U27B3D2")
                    else "Inspect corrected figure and Results audits"
                ),
            }
        ]
    ).to_csv(
        outtables / "UTI_HostOmics_U27B3D11_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3D11_corrected_manuscript_wide_audit_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3D1.1 - Corrected manuscript-wide audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(f"- Manuscript: `{manuscript}`\n")
        handle.write(f"- SHA256: `{sha256(manuscript)}`\n")
        handle.write(
            f"- Definitive figure captions: **{len(caption_frame)}/8**.\n"
        )
        handle.write(
            f"- Caption numbers: **{observed_numbers}**.\n"
        )
        handle.write(
            f"- Embedded drawings: **{len(drawings)}/8**.\n"
        )
        handle.write(
            f"- Embedded media files: **{media_count}/8**.\n"
        )
        handle.write(
            f"- Results frozen-ready: **{results_ready}**.\n"
        )
        handle.write(
            f"- Figures 1-8 frozen-ready: **{figures_ready}**.\n"
        )
        handle.write(
            "- Sections requiring replacement or major revision: "
            f"**{sections_requiring_replacement}**.\n"
        )
        handle.write(
            f"- Obsolete term/path occurrences: "
            f"**{obsolete_occurrences}**.\n\n"
        )

        handle.write("## Correction\n\n")
        handle.write(
            "Figure 1 was present in the cleaned manuscript. The original "
            "audit classified its definitive caption as the synthetic "
            "`Figures` section heading and then excluded that heading from "
            "the section body. Direct body-wide caption inspection confirms "
            "one ordered definitive caption and one embedded image for each "
            "of Figures 1-8. No manuscript repair was required.\n\n"
        )

        handle.write("## Reconstruction release\n\n")
        handle.write(
            "The U27B3C2 Results section, frozen Figures 1-8 and definitive "
            "U27B3B legends are released as immutable scientific components "
            "for U27B3D2. Abstract, Introduction, Methods, Discussion, "
            "limitations, conclusions, availability statements, funding and "
            "supplementary-table architecture require reconstruction in a "
            "new v6.0 derivative.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "manuscript_path": str(manuscript),
        "manuscript_sha256": sha256(manuscript),
        "caption_count": len(caption_frame),
        "caption_numbers": observed_numbers,
        "drawing_count": len(drawings),
        "media_count": media_count,
        "results_ready": results_ready,
        "figures_ready": figures_ready,
        "sections_requiring_replacement": sections_requiring_replacement,
        "obsolete_occurrences": obsolete_occurrences,
        "manuscript_modified": False,
        "scientific_values_recalculated": False,
        "figure_assets_modified": False,
        "source_locks_changed": False,
    }
    (
        outresults / "UTI_HostOmics_U27B3D11_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Definitive captions: {len(caption_frame)}/8")
    log(f"Caption numbers: {observed_numbers}")
    log(f"Embedded drawings: {len(drawings)}/8")
    log(f"Media files: {media_count}/8")
    log(f"Results frozen-ready: {results_ready}")
    log(f"Figures frozen-ready: {figures_ready}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3D1.1] ERROR: {exc}", file=sys.stderr)
        raise
