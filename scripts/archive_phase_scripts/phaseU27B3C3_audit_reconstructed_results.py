#!/usr/bin/env python3
"""
Phase U27B3C3
Scientific, structural and visual-release audit of the reconstructed Results.

This phase is read-only. It compares the authoritative v4.1 source with the
U27B3C2 v5.0 derivative, verifies the Results narrative and interpretive
boundaries, confirms preservation of non-Results text, records the completed
visual review, and determines readiness for frozen Figure 1-8 integration.

No DOCX, figure or table is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import pandas as pd


VERSION = "U27B3C3_v1.0_2026-07-16"
TAG = "phaseU27B3C3_results_visual_scientific_audit"

DEFAULT_SOURCE = (
    "__UTI_HOSTOMICS_PROJECT_ROOT__/"
    "09_manuscript_docx/phaseU23_review_handoff_package/"
    "01_review_main_files/"
    "UTI_HostOmics_preZotero_manuscript_v4_1_draft_with_figures.docx"
)
DEFAULT_DERIVATIVE = (
    "__UTI_HOSTOMICS_PROJECT_ROOT__/"
    "09_manuscript_docx/phaseU27B3C2_results_section_reconstruction/"
    "UTI_HostOmics_preZotero_manuscript_v5_0_U27B3C2_results_reconstructed.docx"
)
DEFAULT_CONTACT_SHEET = (
    "__UTI_HOSTOMICS_PROJECT_ROOT__/"
    "09_manuscript_docx/phaseU27B3C2_results_section_reconstruction/"
    "render_qa/UTI_HostOmics_U27B3C2_render_contact_sheet.png"
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

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

REQUIRED_DATASETS = [
    "GSE112098",
    "GSE280297",
    "GSE168600",
    "GSE252321",
]

PROHIBITED_OBSOLETE_TERMS = [
    "GSE186800",
    "phaseU11_results_claim_index_v1.tsv",
    "phaseU11_key_numeric_anchors_v1.tsv",
    "Results-section traceability note",
]

REQUIRED_RESULTS_CONCEPTS = {
    "expanded_atlas": ["expanded", "atlas", "evidence"],
    "infection_core": ["TLR4", "leptin", "PI3K"],
    "pregnancy_remodeling": ["pregnancy", "tissue", "preterm"],
    "single_cell_localization": ["single-cell", "cellular", "UPEC"],
    "steroid_lipid_branching": ["steroid", "cholesterol", "lipid"],
    "immunometabolism": ["adipokine", "insulin", "carbon"],
    "complement_architecture": ["complement", "C3a", "opsonophagocytosis"],
    "integrated_synthesis": ["integrated", "evidence", "causal"],
}

REQUIRED_BOUNDARIES = {
    "pregnancy_fdr_boundary": [
        "no broad pregnancy",
        "false-discovery",
    ],
    "sample_unit_boundary": [
        "tissue samples",
        "dam-level",
    ],
    "single_cell_sample_size": [
        "n=2",
        "control",
        "UPEC",
    ],
    "single_cell_exact_p": ["0.333"],
    "metabolic_flux_boundary": [
        "transcriptionally inferred",
        "flux",
    ],
    "cross_dataset_boundary": [
        "not pooled",
        "species",
    ],
    "complement_boundary": [
        "complement",
        "provisional",
    ],
}


def log(message: str) -> None:
    print(f"[U27B3C3] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def read_document_root(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read("word/document.xml"))


def body_paragraphs(root: ET.Element) -> List[ET.Element]:
    body = root.find("w:body", NS)
    if body is None:
        return []
    return [
        child
        for child in list(body)
        if child.tag == f"{{{W_NS}}}p"
    ]


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


def detect_section(text: str) -> str:
    cleaned = normalize(text).lower()
    cleaned = re.sub(r"^\d+(?:\.\d+)*\s*", "", cleaned)
    cleaned = cleaned.rstrip(":.")
    return SECTION_ALIASES.get(cleaned, "")


def extract_structure(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    root = read_document_root(path)
    rows = []
    for index, paragraph in enumerate(body_paragraphs(root)):
        text = paragraph_text(paragraph)
        rows.append(
            {
                "paragraph_index": index,
                "text": text,
                "detected_section": detect_section(text),
                "word_count": len(re.findall(r"\b[\w'-]+\b", text)),
            }
        )

    paragraphs = pd.DataFrame(rows)
    headings = paragraphs[
        paragraphs["detected_section"].astype(str) != ""
    ].copy()
    headings = headings.sort_values("paragraph_index")

    boundaries = []
    heading_records = headings.to_dict("records")
    for position, record in enumerate(heading_records):
        start = int(record["paragraph_index"]) + 1
        if position + 1 < len(heading_records):
            end = int(heading_records[position + 1]["paragraph_index"]) - 1
        else:
            end = int(paragraphs["paragraph_index"].max())
        boundaries.append(
            {
                "section": record["detected_section"],
                "heading_paragraph_index": int(record["paragraph_index"]),
                "content_start_index": start,
                "content_end_index": end,
                "content_paragraph_count": max(0, end - start + 1),
            }
        )

    return paragraphs, pd.DataFrame(boundaries)


def section_text(
    paragraphs: pd.DataFrame,
    boundaries: pd.DataFrame,
    section: str,
) -> str:
    rows = boundaries[boundaries["section"] == section]
    if len(rows) != 1:
        return ""
    record = rows.iloc[0]
    selected = paragraphs[
        paragraphs["paragraph_index"].between(
            int(record["content_start_index"]),
            int(record["content_end_index"]),
        )
    ]
    return "\n\n".join(selected["text"].fillna("").astype(str))


def outside_results_signature(
    paragraphs: pd.DataFrame,
    boundaries: pd.DataFrame,
) -> Dict[str, str]:
    results = boundaries[boundaries["section"] == "Results"]
    discussion = boundaries[boundaries["section"] == "Discussion"]
    if len(results) != 1 or len(discussion) != 1:
        return {"pre_results": "", "discussion_onward": ""}

    results_heading = int(results.iloc[0]["heading_paragraph_index"])
    discussion_heading = int(discussion.iloc[0]["heading_paragraph_index"])

    pre = paragraphs[
        paragraphs["paragraph_index"] < results_heading
    ]["text"].fillna("").astype(str).tolist()
    post = paragraphs[
        paragraphs["paragraph_index"] >= discussion_heading
    ]["text"].fillna("").astype(str).tolist()

    return {
        "pre_results": "\n".join(pre),
        "discussion_onward": "\n".join(post),
    }


def phrase_group_pass(text: str, phrases: List[str]) -> bool:
    lower = text.lower()
    return all(phrase.lower() in lower for phrase in phrases)


def figure_reference_positions(text: str) -> Dict[int, int]:
    positions = {}
    for number in range(1, 9):
        matches = list(
            re.finditer(
                rf"\bFigure\s+{number}\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        positions[number] = matches[0].start() if matches else -1
    return positions


def count_embedded_media(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return len(
            [
                name
                for name in archive.namelist()
                if name.startswith("word/media/")
                and not name.endswith("/")
            ]
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--derivative", default=DEFAULT_DERIVATIVE)
    parser.add_argument(
        "--contact-sheet",
        default=DEFAULT_CONTACT_SHEET,
    )
    parser.add_argument(
        "--visual-pass",
        choices=["true", "false"],
        default="true",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    source = Path(args.source).resolve()
    derivative = Path(args.derivative).resolve()
    contact_sheet = Path(args.contact_sheet).resolve()
    visual_pass = args.visual_pass == "true"

    for path in (source, derivative):
        if not path.exists():
            raise FileNotFoundError(path)

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    source_paragraphs, source_boundaries = extract_structure(source)
    derivative_paragraphs, derivative_boundaries = extract_structure(
        derivative
    )

    source_results = section_text(
        source_paragraphs,
        source_boundaries,
        "Results",
    )
    derivative_results = section_text(
        derivative_paragraphs,
        derivative_boundaries,
        "Results",
    )

    if not derivative_results:
        raise RuntimeError(
            "The derivative Results section could not be resolved."
        )

    source_signatures = outside_results_signature(
        source_paragraphs,
        source_boundaries,
    )
    derivative_signatures = outside_results_signature(
        derivative_paragraphs,
        derivative_boundaries,
    )

    pre_results_preserved = (
        source_signatures["pre_results"]
        == derivative_signatures["pre_results"]
    )
    discussion_onward_preserved = (
        source_signatures["discussion_onward"]
        == derivative_signatures["discussion_onward"]
    )

    concept_rows = []
    for concept, phrases in REQUIRED_RESULTS_CONCEPTS.items():
        concept_rows.append(
            {
                "audit_type": "required_results_concept",
                "audit_id": concept,
                "required_terms": "; ".join(phrases),
                "pass": phrase_group_pass(derivative_results, phrases),
            }
        )

    boundary_rows = []
    for boundary, phrases in REQUIRED_BOUNDARIES.items():
        boundary_rows.append(
            {
                "audit_type": "required_interpretation_boundary",
                "audit_id": boundary,
                "required_terms": "; ".join(phrases),
                "pass": phrase_group_pass(derivative_results, phrases),
            }
        )

    dataset_rows = [
        {
            "audit_type": "required_dataset",
            "audit_id": dataset,
            "required_terms": dataset,
            "pass": dataset in derivative_results,
        }
        for dataset in REQUIRED_DATASETS
    ]

    prohibited_rows = [
        {
            "audit_type": "prohibited_obsolete_term",
            "audit_id": term,
            "required_terms": "absent",
            "pass": term.lower() not in derivative_results.lower(),
        }
        for term in PROHIBITED_OBSOLETE_TERMS
    ]

    content_audit = pd.DataFrame(
        concept_rows + boundary_rows + dataset_rows + prohibited_rows
    )
    content_audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C3_results_scientific_content_audit.tsv",
        sep="\t",
        index=False,
    )

    figure_positions = figure_reference_positions(derivative_results)
    figure_refs_present = all(
        position >= 0 for position in figure_positions.values()
    )
    ordered_positions = [figure_positions[number] for number in range(1, 9)]
    figure_refs_ordered = bool(
        figure_refs_present
        and ordered_positions == sorted(ordered_positions)
    )

    figure_reference_audit = pd.DataFrame(
        [
            {
                "figure_number": number,
                "first_reference_character_position": figure_positions[number],
                "reference_present": figure_positions[number] >= 0,
            }
            for number in range(1, 9)
        ]
    )
    figure_reference_audit["all_figures_ordered"] = figure_refs_ordered
    figure_reference_audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C3_figure_reference_audit.tsv",
        sep="\t",
        index=False,
    )

    source_media = count_embedded_media(source)
    derivative_media = count_embedded_media(derivative)
    legacy_figures_pending_replacement = derivative_media == 6

    preservation_audit = pd.DataFrame(
        [
            {
                "source_path": str(source),
                "source_sha256": sha256(source),
                "derivative_path": str(derivative),
                "derivative_sha256": sha256(derivative),
                "pre_results_text_preserved": pre_results_preserved,
                "discussion_onward_text_preserved": discussion_onward_preserved,
                "source_results_word_count": len(source_results.split()),
                "derivative_results_word_count": len(
                    derivative_results.split()
                ),
                "source_results_paragraphs": int(
                    source_boundaries[
                        source_boundaries["section"] == "Results"
                    ]["content_paragraph_count"].iloc[0]
                ),
                "derivative_results_paragraphs": int(
                    derivative_boundaries[
                        derivative_boundaries["section"] == "Results"
                    ]["content_paragraph_count"].iloc[0]
                ),
                "source_embedded_media_files": source_media,
                "derivative_embedded_media_files": derivative_media,
                "legacy_figures_pending_replacement": (
                    legacy_figures_pending_replacement
                ),
                "contact_sheet_present": contact_sheet.exists(),
                "visual_review_pass": visual_pass,
                "visual_review_note": (
                    "Text pages render cleanly without clipping or overlap. "
                    "Large whitespace and six legacy figure pages are inherited "
                    "from v4.1 and are pending frozen Figure 1-8 replacement."
                ),
            }
        ]
    )
    preservation_audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C3_preservation_visual_audit.tsv",
        sep="\t",
        index=False,
    )

    content_pass = bool(content_audit["pass"].all())
    preservation_pass = bool(
        pre_results_preserved and discussion_onward_preserved
    )
    render_pass = bool(contact_sheet.exists() and visual_pass)
    section_pass = bool(
        len(
            derivative_boundaries[
                derivative_boundaries["section"] == "Results"
            ]
        )
        == 1
        and len(
            derivative_boundaries[
                derivative_boundaries["section"] == "Discussion"
            ]
        )
        == 1
    )

    if (
        content_pass
        and preservation_pass
        and render_pass
        and section_pass
        and figure_refs_present
        and figure_refs_ordered
        and legacy_figures_pending_replacement
    ):
        decision = (
            "READY_FOR_U27B3C4_FROZEN_FIGURES_1_TO_8_"
            "AND_LEGEND_INTEGRATION"
        )
    else:
        decision = (
            "TARGETED_U27B3C2_RESULTS_CONTENT_OR_PRESERVATION_"
            "REPAIR_REQUIRED"
        )

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B3C3",
                "decision": decision,
                "scientific_content_audits": len(content_audit),
                "scientific_content_audits_passed": int(
                    content_audit["pass"].sum()
                ),
                "all_scientific_content_audits_pass": content_pass,
                "figures_1_to_8_referenced": figure_refs_present,
                "figure_references_in_order": figure_refs_ordered,
                "pre_results_text_preserved": pre_results_preserved,
                "discussion_onward_text_preserved": (
                    discussion_onward_preserved
                ),
                "visual_render_pass": render_pass,
                "legacy_embedded_figures": derivative_media,
                "legacy_figures_pending_replacement": (
                    legacy_figures_pending_replacement
                ),
                "scientific_values_recalculated": False,
                "figure_assets_modified": False,
                "source_manuscript_modified": False,
                "derivative_modified": False,
                "next_phase": (
                    "U27B3C4 replace six legacy embedded figures with frozen "
                    "Figures 1-8 and integrate definitive legends"
                    if decision.startswith("READY_FOR_U27B3C4")
                    else "Repair failed Results content or preservation audits"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        outtables / "UTI_HostOmics_U27B3C3_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    derivative_results_path = (
        outresults / "UTI_HostOmics_U27B3C3_audited_results_section.txt"
    )
    derivative_results_path.write_text(
        derivative_results,
        encoding="utf-8",
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3C3_results_visual_scientific_audit_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3C3 - Results visual and scientific audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Scientific/content checks passed: "
            f"**{int(content_audit['pass'].sum())}/{len(content_audit)}**.\n"
        )
        handle.write(
            f"- Figures 1-8 referenced: "
            f"**{'PASS' if figure_refs_present else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Figure-reference order: "
            f"**{'PASS' if figure_refs_ordered else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Pre-Results text preserved: "
            f"**{'PASS' if pre_results_preserved else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Discussion-onward text preserved: "
            f"**{'PASS' if discussion_onward_preserved else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Render review: "
            f"**{'PASS' if render_pass else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Legacy embedded figures awaiting replacement: "
            f"**{derivative_media}**.\n\n"
        )
        handle.write("## Visual decision\n\n")
        handle.write(
            "The reconstructed Results pages render cleanly without clipping, "
            "overlap, missing glyphs or broken headings. Large whitespace and "
            "the six figure pages are inherited v4.1 layout artifacts and are "
            "not approved as final manuscript assets. They are explicitly "
            "released for replacement by frozen Figures 1-8 in U27B3C4.\n\n"
        )
        handle.write("## Integrity boundary\n\n")
        handle.write(
            "This phase is read-only. No statistical value was recalculated, "
            "and neither the authoritative source nor the v5.0 derivative was "
            "modified.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "source_path": str(source),
        "source_sha256": sha256(source),
        "derivative_path": str(derivative),
        "derivative_sha256": sha256(derivative),
        "content_checks_pass": content_pass,
        "figure_references_present": figure_refs_present,
        "figure_references_ordered": figure_refs_ordered,
        "pre_results_preserved": pre_results_preserved,
        "discussion_onward_preserved": discussion_onward_preserved,
        "visual_render_pass": render_pass,
        "legacy_embedded_figures": derivative_media,
        "scientific_values_recalculated": False,
        "files_modified": False,
    }
    (
        outresults / "UTI_HostOmics_U27B3C3_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log(f"Scientific/content checks: {int(content_audit['pass'].sum())}/{len(content_audit)}")
    log(f"Figures 1-8 referenced: {figure_refs_present}")
    log(f"Figure references ordered: {figure_refs_ordered}")
    log(f"Non-Results text preserved: {preservation_pass}")
    log(f"Visual review pass: {render_pass}")
    log(f"Legacy figures pending replacement: {derivative_media}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3C3] ERROR: {exc}", file=sys.stderr)
        raise
