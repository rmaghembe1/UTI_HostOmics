#!/usr/bin/env python3
"""
Phase U27B3C1.1
Confirm the authoritative manuscript target and audit its DOCX structure.

Authoritative input
-------------------
The U21, U22 and U23 manuscript copies were verified as byte-identical.
The U23 review-handoff copy is selected as the authoritative read-only source.

This phase:
1. verifies all three duplicate hashes and the expected SHA256;
2. records the authoritative target;
3. inventories paragraph order, styles and section headings;
4. resolves the Results and Discussion boundaries;
5. extracts the current Results section non-destructively;
6. audits embedded figures, relationships, fields, comments, tracked changes,
   protection and bookmarks;
7. writes a decision for U27B3C2.

No DOCX is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET

import pandas as pd


VERSION = "U27B3C11_v1.0_2026-07-16"
TAG = "phaseU27B3C11_authoritative_target_and_structure_audit"

EXPECTED_SHA256 = (
    "148b4f7b6cb0c60e620913229e0f490fb"
    "621778b5a3ae8d6b8ddab2145d15e90"
)

DEFAULT_TARGET = (
    "__UTI_HOSTOMICS_PROJECT_ROOT__/"
    "09_manuscript_docx/phaseU23_review_handoff_package/"
    "01_review_main_files/"
    "UTI_HostOmics_preZotero_manuscript_v4_1_draft_with_figures.docx"
)

DUPLICATE_RELATIVE_PATHS = [
    (
        "09_manuscript_docx/phaseU21_draft_docx/"
        "UTI_HostOmics_preZotero_manuscript_v4_1_draft_with_figures.docx"
    ),
    (
        "09_manuscript_docx/phaseU22_docx_visual_qa/"
        "UTI_HostOmics_preZotero_manuscript_v4_1_draft_with_figures.docx"
    ),
    (
        "09_manuscript_docx/phaseU23_review_handoff_package/"
        "01_review_main_files/"
        "UTI_HostOmics_preZotero_manuscript_v4_1_draft_with_figures.docx"
    ),
]

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"

NS = {
    "w": W_NS,
    "r": R_NS,
    "a": A_NS,
    "wp": WP_NS,
    "pic": PIC_NS,
}

SECTION_ALIASES = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "methods": "Methods",
    "materials and methods": "Methods",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "conclusions": "Conclusion",
    "references": "References",
}


def log(message: str) -> None:
    print(f"[U27B3C1.1] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def read_xml(archive: zipfile.ZipFile, name: str) -> Optional[ET.Element]:
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None
    except ET.ParseError:
        return None


def paragraph_text(paragraph: ET.Element) -> str:
    pieces = []
    for node in paragraph.iter():
        local = node.tag.rsplit("}", 1)[-1]
        if local == "t":
            pieces.append(node.text or "")
        elif local == "tab":
            pieces.append("\t")
        elif local in {"br", "cr"}:
            pieces.append("\n")
    return normalize_text("".join(pieces))


def paragraph_style(paragraph: ET.Element) -> str:
    ppr = paragraph.find("w:pPr", NS)
    if ppr is None:
        return ""
    style = ppr.find("w:pStyle", NS)
    if style is None:
        return ""
    return style.attrib.get(f"{{{W_NS}}}val", "")


def paragraph_outline_level(paragraph: ET.Element) -> str:
    ppr = paragraph.find("w:pPr", NS)
    if ppr is None:
        return ""
    outline = ppr.find("w:outlineLvl", NS)
    if outline is None:
        return ""
    return outline.attrib.get(f"{{{W_NS}}}val", "")


def detect_section(text: str) -> str:
    cleaned = normalize_text(text).lower()
    cleaned = re.sub(r"^\d+(?:\.\d+)*\s*", "", cleaned)
    cleaned = cleaned.rstrip(":.")

    if cleaned in SECTION_ALIASES:
        return SECTION_ALIASES[cleaned]

    return ""


def body_paragraphs(document_root: ET.Element) -> List[ET.Element]:
    body = document_root.find("w:body", NS)
    if body is None:
        return []
    return [
        child
        for child in list(body)
        if child.tag == f"{{{W_NS}}}p"
    ]


def count_nodes(root: Optional[ET.Element], local_name: str) -> int:
    if root is None:
        return 0
    return sum(
        1
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == local_name
    )


def relationship_inventory(
    archive: zipfile.ZipFile,
) -> pd.DataFrame:
    rel_root = read_xml(
        archive,
        "word/_rels/document.xml.rels",
    )
    if rel_root is None:
        return pd.DataFrame(
            columns=["relationship_id", "type", "target", "target_mode"]
        )

    rows = []
    for rel in list(rel_root):
        rows.append(
            {
                "relationship_id": rel.attrib.get("Id", ""),
                "type": rel.attrib.get("Type", ""),
                "target": rel.attrib.get("Target", ""),
                "target_mode": rel.attrib.get("TargetMode", ""),
            }
        )
    return pd.DataFrame(rows)


def heading_boundaries(
    paragraph_frame: pd.DataFrame,
) -> pd.DataFrame:
    heading_rows = paragraph_frame[
        paragraph_frame["detected_section"].astype(str) != ""
    ].copy()

    if heading_rows.empty:
        return pd.DataFrame(
            columns=[
                "section",
                "heading_paragraph_index",
                "content_start_index",
                "content_end_index",
                "content_paragraph_count",
            ]
        )

    heading_rows = heading_rows.sort_values("paragraph_index")
    records = []
    heading_list = heading_rows.to_dict("records")

    for position, record in enumerate(heading_list):
        start = int(record["paragraph_index"]) + 1
        if position + 1 < len(heading_list):
            end = int(heading_list[position + 1]["paragraph_index"]) - 1
        else:
            end = int(paragraph_frame["paragraph_index"].max())

        records.append(
            {
                "section": record["detected_section"],
                "heading_paragraph_index": int(record["paragraph_index"]),
                "content_start_index": start,
                "content_end_index": end,
                "content_paragraph_count": max(0, end - start + 1),
            }
        )

    return pd.DataFrame(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    target = Path(args.target).resolve()

    if not project.exists():
        raise FileNotFoundError(f"Project root not found: {project}")
    if not target.exists():
        raise FileNotFoundError(
            f"Authoritative manuscript target not found: {target}"
        )

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    outmanuscript = project / "07_manuscript" / TAG

    for directory in (
        outtables,
        outmetadata,
        outresults,
        outmanuscript,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    # Duplicate identity audit.
    duplicate_rows = []
    for relative in DUPLICATE_RELATIVE_PATHS:
        path = project / relative
        digest = sha256(path) if path.exists() else ""
        duplicate_rows.append(
            {
                "path": str(path),
                "relative_path": relative,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "sha256": digest,
                "matches_expected_sha256": digest == EXPECTED_SHA256,
            }
        )

    duplicate_audit = pd.DataFrame(duplicate_rows)
    duplicate_audit["matches_target_sha256"] = (
        duplicate_audit["sha256"] == sha256(target)
    )
    duplicate_audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C11_duplicate_identity_audit.tsv",
        sep="\t",
        index=False,
    )

    duplicates_complete = bool(
        duplicate_audit["exists"].all()
        and duplicate_audit["matches_expected_sha256"].all()
        and duplicate_audit["matches_target_sha256"].all()
    )

    target_hash = sha256(target)
    target_hash_pass = target_hash == EXPECTED_SHA256

    with zipfile.ZipFile(target) as archive:
        document_root = read_xml(archive, "word/document.xml")
        if document_root is None:
            raise RuntimeError(
                "word/document.xml could not be read from the DOCX."
            )

        paragraphs = body_paragraphs(document_root)
        paragraph_rows = []

        for index, paragraph in enumerate(paragraphs):
            text = paragraph_text(paragraph)
            style = paragraph_style(paragraph)
            outline = paragraph_outline_level(paragraph)
            section = detect_section(text)

            paragraph_rows.append(
                {
                    "paragraph_index": index,
                    "text": text,
                    "style_id": style,
                    "outline_level": outline,
                    "detected_section": section,
                    "character_count": len(text),
                    "word_count": len(
                        re.findall(r"\b[\w'-]+\b", text)
                    ),
                    "contains_figure_reference": bool(
                        re.search(
                            r"\bFig(?:ure)?\.?\s*\d+",
                            text,
                            flags=re.IGNORECASE,
                        )
                    ),
                    "contains_table_reference": bool(
                        re.search(
                            r"\bTable\s+\d+",
                            text,
                            flags=re.IGNORECASE,
                        )
                    ),
                }
            )

        paragraph_frame = pd.DataFrame(paragraph_rows)
        paragraph_frame.to_csv(
            outtables
            / "UTI_HostOmics_U27B3C11_paragraph_inventory.tsv",
            sep="\t",
            index=False,
        )

        boundaries = heading_boundaries(paragraph_frame)
        boundaries.to_csv(
            outtables
            / "UTI_HostOmics_U27B3C11_section_boundary_audit.tsv",
            sep="\t",
            index=False,
        )

        results_rows = boundaries[
            boundaries["section"] == "Results"
        ]
        discussion_rows = boundaries[
            boundaries["section"] == "Discussion"
        ]

        results_heading_count = len(results_rows)
        discussion_heading_count = len(discussion_rows)

        results_text_rows = pd.DataFrame()
        results_text = ""

        if results_heading_count == 1:
            result_record = results_rows.iloc[0]
            start = int(result_record["content_start_index"])
            end = int(result_record["content_end_index"])
            results_text_rows = paragraph_frame[
                paragraph_frame["paragraph_index"].between(start, end)
            ].copy()
            results_text = "\n\n".join(
                results_text_rows["text"]
                .fillna("")
                .astype(str)
                .tolist()
            )

        results_text_rows.to_csv(
            outtables
            / "UTI_HostOmics_U27B3C11_current_results_paragraphs.tsv",
            sep="\t",
            index=False,
        )
        (
            outmanuscript
            / "UTI_HostOmics_U27B3C11_current_results_section.txt"
        ).write_text(results_text, encoding="utf-8")

        relationships = relationship_inventory(archive)
        relationships.to_csv(
            outtables
            / "UTI_HostOmics_U27B3C11_relationship_inventory.tsv",
            sep="\t",
            index=False,
        )

        media_files = [
            name
            for name in archive.namelist()
            if name.startswith("word/media/")
            and not name.endswith("/")
        ]

        comments_root = read_xml(archive, "word/comments.xml")
        settings_root = read_xml(archive, "word/settings.xml")
        footnotes_root = read_xml(archive, "word/footnotes.xml")
        endnotes_root = read_xml(archive, "word/endnotes.xml")

        tracked_insertions = count_nodes(document_root, "ins")
        tracked_deletions = count_nodes(document_root, "del")
        comment_count = count_nodes(comments_root, "comment")
        field_instruction_count = count_nodes(
            document_root,
            "instrText",
        )
        simple_field_count = count_nodes(
            document_root,
            "fldSimple",
        )
        bookmark_start_count = count_nodes(
            document_root,
            "bookmarkStart",
        )
        drawing_count = count_nodes(document_root, "drawing")
        inline_count = count_nodes(document_root, "inline")
        anchor_count = count_nodes(document_root, "anchor")
        hyperlink_count = count_nodes(document_root, "hyperlink")
        footnote_count = max(
            0,
            count_nodes(footnotes_root, "footnote") - 2,
        )
        endnote_count = max(
            0,
            count_nodes(endnotes_root, "endnote") - 2,
        )

        protection_count = (
            count_nodes(settings_root, "documentProtection")
            if settings_root is not None
            else 0
        )

        ooxml_audit = pd.DataFrame(
            [
                {
                    "target_path": str(target),
                    "target_sha256": target_hash,
                    "expected_sha256": EXPECTED_SHA256,
                    "hash_pass": target_hash_pass,
                    "paragraphs_in_document_body": len(paragraphs),
                    "embedded_media_files": len(media_files),
                    "drawing_elements": drawing_count,
                    "inline_drawing_elements": inline_count,
                    "anchored_drawing_elements": anchor_count,
                    "relationships": len(relationships),
                    "hyperlinks": hyperlink_count,
                    "field_instruction_runs": field_instruction_count,
                    "simple_fields": simple_field_count,
                    "bookmarks": bookmark_start_count,
                    "comments": comment_count,
                    "tracked_insertions": tracked_insertions,
                    "tracked_deletions": tracked_deletions,
                    "footnotes": footnote_count,
                    "endnotes": endnote_count,
                    "document_protection_elements": protection_count,
                }
            ]
        )
        ooxml_audit.to_csv(
            outtables
            / "UTI_HostOmics_U27B3C11_ooxml_preservation_audit.tsv",
            sep="\t",
            index=False,
        )

        media_inventory = pd.DataFrame(
            [
                {
                    "archive_path": name,
                    "filename": Path(name).name,
                    "size_bytes": len(archive.read(name)),
                }
                for name in media_files
            ]
        )
        media_inventory.to_csv(
            outtables
            / "UTI_HostOmics_U27B3C11_embedded_media_inventory.tsv",
            sep="\t",
            index=False,
        )

    sections_found = set(
        boundaries["section"].astype(str)
    ) if not boundaries.empty else set()

    result_before_discussion = False
    if results_heading_count == 1 and discussion_heading_count == 1:
        result_before_discussion = bool(
            int(results_rows.iloc[0]["heading_paragraph_index"])
            < int(
                discussion_rows.iloc[0]["heading_paragraph_index"]
            )
        )

    structure_pass = bool(
        results_heading_count == 1
        and discussion_heading_count == 1
        and result_before_discussion
    )

    preservation_strategy = (
        "OOXML_SECTION_REPLACEMENT_AND_RENDER_VERIFY"
        if (
            tracked_insertions > 0
            or tracked_deletions > 0
            or comment_count > 0
            or field_instruction_count > 0
            or simple_field_count > 0
        )
        else "PYTHON_DOCX_DERIVATIVE_AND_RENDER_VERIFY"
    )

    if (
        duplicates_complete
        and target_hash_pass
        and structure_pass
        and protection_count == 0
    ):
        decision = (
            "READY_FOR_U27B3C2_RESULTS_SECTION_RECONSTRUCTION"
        )
    elif protection_count > 0:
        decision = (
            "MANUSCRIPT_TARGET_CONFIRMED_BUT_EDITING_PROTECTION_REQUIRES_REVIEW"
        )
    else:
        decision = (
            "TARGET_CONFIRMED_BUT_RESULTS_STRUCTURE_REPAIR_OR_MANUAL_BOUNDARY_"
            "CONFIRMATION_REQUIRED"
        )

    authoritative_record = pd.DataFrame(
        [
            {
                "field": "authoritative_input_path",
                "value": str(target),
            },
            {
                "field": "input_sha256",
                "value": target_hash,
            },
            {
                "field": "selection_basis",
                "value": (
                    "Latest downstream review-handoff copy; U21, U22 and U23 "
                    "verified as byte-identical"
                ),
            },
            {
                "field": "input_role",
                "value": "read_only_authoritative_source",
            },
            {
                "field": "overwrite_permitted",
                "value": "False",
            },
            {
                "field": "preservation_strategy",
                "value": preservation_strategy,
            },
            {
                "field": "next_derivative_phase",
                "value": "U27B3C2",
            },
        ]
    )
    authoritative_record.to_csv(
        outmetadata
        / "UTI_HostOmics_U27B3C11_authoritative_manuscript_target.tsv",
        sep="\t",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "phase": "U27B3C1.1",
                "decision": decision,
                "duplicate_candidates_verified": duplicates_complete,
                "authoritative_target_confirmed": target_hash_pass,
                "results_heading_count": results_heading_count,
                "discussion_heading_count": discussion_heading_count,
                "results_precede_discussion": result_before_discussion,
                "current_results_paragraphs": len(results_text_rows),
                "embedded_media_files": len(media_files),
                "comments": comment_count,
                "tracked_insertions": tracked_insertions,
                "tracked_deletions": tracked_deletions,
                "field_instruction_runs": field_instruction_count,
                "document_protection_elements": protection_count,
                "preservation_strategy": preservation_strategy,
                "input_read_only": True,
                "files_modified": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B3C2 create a new v5.0 manuscript derivative with "
                    "Results reconstructed in frozen Figure 1-8 order"
                    if decision.startswith("READY_FOR_U27B3C2")
                    else "Resolve heading boundaries or document protection"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B3C11_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3C11_authoritative_target_structure_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3C1.1 - Authoritative manuscript target and "
            "structure audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(f"- Authoritative input: `{target}`\n")
        handle.write(f"- SHA256: `{target_hash}`\n")
        handle.write(
            f"- Duplicate identity audit: "
            f"**{'PASS' if duplicates_complete else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Results headings: **{results_heading_count}**.\n"
        )
        handle.write(
            f"- Discussion headings: **{discussion_heading_count}**.\n"
        )
        handle.write(
            f"- Current Results paragraphs: "
            f"**{len(results_text_rows)}**.\n"
        )
        handle.write(
            f"- Embedded media files: **{len(media_files)}**.\n"
        )
        handle.write(
            f"- Tracked insertions/deletions: "
            f"**{tracked_insertions}/{tracked_deletions}**.\n"
        )
        handle.write(f"- Comments: **{comment_count}**.\n")
        handle.write(
            f"- Field instruction runs: "
            f"**{field_instruction_count}**.\n"
        )
        handle.write(
            f"- Preservation strategy: "
            f"**{preservation_strategy}**.\n\n"
        )

        handle.write("## Boundary decision\n\n")
        handle.write(
            "The U23 review-handoff document is designated as the "
            "authoritative read-only input. U27B3C2 must create a new "
            "derivative and must not overwrite any v4.1 manuscript copy.\n\n"
        )

        handle.write("## Results reconstruction boundary\n\n")
        if structure_pass:
            handle.write(
                "Exactly one Results heading and one downstream Discussion "
                "heading were identified. The paragraph interval between them "
                "is the replaceable Results section for the new derivative.\n"
            )
        else:
            handle.write(
                "The Results/Discussion boundary is ambiguous and requires "
                "manual review before reconstruction.\n"
            )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "authoritative_input_path": str(target),
        "input_sha256": target_hash,
        "duplicates_complete": duplicates_complete,
        "results_heading_count": results_heading_count,
        "discussion_heading_count": discussion_heading_count,
        "current_results_paragraphs": len(results_text_rows),
        "embedded_media_files": len(media_files),
        "tracked_insertions": tracked_insertions,
        "tracked_deletions": tracked_deletions,
        "comments": comment_count,
        "field_instruction_runs": field_instruction_count,
        "preservation_strategy": preservation_strategy,
        "input_read_only": True,
        "files_modified": False,
        "manuscript_modified": False,
    }
    (
        outresults
        / "UTI_HostOmics_U27B3C11_run_manifest.json"
    ).write_text(
        json.dumps(run_manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Duplicate identity pass: {duplicates_complete}")
    log(f"Authoritative target: {target}")
    log(f"Results headings: {results_heading_count}")
    log(f"Discussion headings: {discussion_heading_count}")
    log(f"Current Results paragraphs: {len(results_text_rows)}")
    log(f"Preservation strategy: {preservation_strategy}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3C1.1] ERROR: {exc}", file=sys.stderr)
        raise
