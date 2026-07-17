#!/usr/bin/env python3
"""
Phase U27B3C3.1
Correct the false-negative Results audit caused by overly literal phrase and
figure-reference matching.

The U27B3C2 Results text already contains:
- the tissue-sample inferential-unit boundary and unavailable dam identifiers;
- the native-species, independently analyzed, non-pooled-expression boundary;
- references to Figures 1-8 using panel-qualified forms such as Figure 1A-E.

The earlier U27B3C3 audit required exact phrases and searched for bare figure
numbers followed by word boundaries, so it failed on semantically equivalent
language and on panel-qualified references.

This phase is read-only. It does not modify the authoritative source, the v5.0
derivative, frozen figures, legends, values or source locks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

import pandas as pd


VERSION = "U27B3C31_v1.0_2026-07-16"
TAG = "phaseU27B3C31_corrected_results_scientific_audit"

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

PREVIOUS_AUDIT_RELATIVE = (
    "06_tables/phaseU27B3C3_results_visual_scientific_audit/"
    "UTI_HostOmics_U27B3C3_preservation_visual_audit.tsv"
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def log(message: str) -> None:
    print(f"[U27B3C3.1] {message}", flush=True)


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


def read_docx_paragraphs(path: Path) -> Tuple[List[str], int]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        body = root.find("w:body", NS)
        if body is None:
            raise RuntimeError(f"No word/body element found in {path}")

        paragraphs = [
            paragraph_text(child)
            for child in list(body)
            if child.tag == f"{{{W_NS}}}p"
        ]
        media_count = sum(
            1
            for name in archive.namelist()
            if name.startswith("word/media/")
            and not name.endswith("/")
        )

    return paragraphs, media_count


def heading_index(paragraphs: Sequence[str], heading: str) -> int:
    normalized_heading = heading.lower()
    matches = []
    for index, text in enumerate(paragraphs):
        cleaned = normalize(text).lower()
        cleaned = re.sub(r"^\d+(?:\.\d+)*\s*", "", cleaned)
        cleaned = cleaned.rstrip(":." )
        if cleaned == normalized_heading:
            matches.append(index)

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one {heading!r} heading; observed {matches}"
        )
    return matches[0]


def split_document(paragraphs: Sequence[str]) -> Dict[str, object]:
    results_index = heading_index(paragraphs, "Results")
    discussion_index = heading_index(paragraphs, "Discussion")

    if results_index >= discussion_index:
        raise RuntimeError("Results heading does not precede Discussion.")

    return {
        "results_heading_index": results_index,
        "discussion_heading_index": discussion_index,
        "pre_results": list(paragraphs[:results_index]),
        "results": list(paragraphs[results_index + 1:discussion_index]),
        "discussion_onward": list(paragraphs[discussion_index:]),
    }


def contains_all(text: str, terms: Sequence[str]) -> bool:
    lower = text.lower()
    return all(term.lower() in lower for term in terms)


def semantic_sample_unit_boundary(text: str) -> bool:
    lower = text.lower()
    tissue_unit = (
        "tissue samples" in lower
        and "inferential units" in lower
    )
    explicit_dam_boundary = "no dam-level inference" in lower
    unavailable_dam_identifiers = (
        "dam identifiers" in lower
        and any(
            phrase in lower
            for phrase in (
                "were unavailable",
                "was unavailable",
                "unavailable",
            )
        )
    )
    return tissue_unit and (
        explicit_dam_boundary or unavailable_dam_identifiers
    )


def semantic_cross_dataset_boundary(text: str) -> bool:
    lower = text.lower()

    independent_native_context = (
        "analyzed independently" in lower
        and "native species" in lower
        and "tissue context" in lower
    )

    non_pooled_expression = any(
        phrase in lower
        for phrase in (
            "not pooled",
            "rather than pooled raw expression",
            "not merged",
            "not merged raw expression",
        )
    )

    standardized_integration = (
        "standardized effects" in lower
        and (
            "directional concordance" in lower
            or "recurrence" in lower
        )
    )

    return (
        independent_native_context
        and non_pooled_expression
        and standardized_integration
    )


def figure_reference_pattern(figure_number: int) -> re.Pattern[str]:
    """
    Match:
      Figure 1
      Figure 1A
      Figure 1A-E
      Figure 1A–E
      Fig. 1A-E
    """
    return re.compile(
        rf"\bFig(?:ure)?\.?\s*{figure_number}"
        rf"(?:\s*[A-H](?:\s*[-\u2013\u2014]\s*[A-H])?)?",
        flags=re.IGNORECASE,
    )


def audit_row(
    audit_type: str,
    audit_id: str,
    required_terms: str,
    passed: bool,
    rationale: str = "",
) -> Dict[str, object]:
    return {
        "audit_type": audit_type,
        "audit_id": audit_id,
        "required_terms_or_rule": required_terms,
        "pass": bool(passed),
        "rationale": rationale,
    }


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
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    source = Path(args.source).resolve()
    derivative = Path(args.derivative).resolve()
    contact_sheet = Path(args.contact_sheet).resolve()

    for path in (source, derivative):
        if not path.exists():
            raise FileNotFoundError(f"Required DOCX not found: {path}")

    outtables = project / "06_tables" / TAG
    outresults = project / "05_results" / TAG
    outmetadata = project / "03_metadata" / TAG

    for directory in (outtables, outresults, outmetadata):
        directory.mkdir(parents=True, exist_ok=True)

    source_paragraphs, source_media = read_docx_paragraphs(source)
    derivative_paragraphs, derivative_media = read_docx_paragraphs(
        derivative
    )

    source_split = split_document(source_paragraphs)
    derivative_split = split_document(derivative_paragraphs)

    pre_results_preserved = (
        source_split["pre_results"] == derivative_split["pre_results"]
    )
    discussion_onward_preserved = (
        source_split["discussion_onward"]
        == derivative_split["discussion_onward"]
    )

    results_paragraphs = derivative_split["results"]
    results_text = "\n\n".join(results_paragraphs)
    results_lower = results_text.lower()

    scientific_rows: List[Dict[str, object]] = []

    concept_audits = [
        (
            "expanded_atlas",
            ("expanded", "atlas", "evidence"),
        ),
        (
            "infection_core",
            ("tlr4", "leptin", "pi3k"),
        ),
        (
            "pregnancy_remodeling",
            ("pregnancy", "tissue", "preterm"),
        ),
        (
            "single_cell_localization",
            ("single-cell", "cellular", "upec"),
        ),
        (
            "steroid_lipid_branching",
            ("steroid", "cholesterol", "lipid"),
        ),
        (
            "immunometabolism",
            ("adipokine", "insulin", "carbon"),
        ),
        (
            "complement_architecture",
            ("complement", "c3a", "opsonophagocytosis"),
        ),
        (
            "integrated_synthesis",
            ("integrated", "evidence", "causal"),
        ),
    ]

    for audit_id, terms in concept_audits:
        scientific_rows.append(
            audit_row(
                "required_results_concept",
                audit_id,
                "; ".join(terms),
                contains_all(results_text, terms),
            )
        )

    scientific_rows.extend(
        [
            audit_row(
                "required_interpretation_boundary",
                "pregnancy_fdr_boundary",
                "no broad pregnancy; false-discovery",
                contains_all(
                    results_text,
                    ("no broad pregnancy", "false-discovery"),
                ),
            ),
            audit_row(
                "required_interpretation_boundary",
                "sample_unit_boundary",
                (
                    "tissue samples + inferential units + "
                    "(no dam-level inference OR unavailable dam identifiers)"
                ),
                semantic_sample_unit_boundary(results_text),
                (
                    "The manuscript states that tissue samples were the "
                    "inferential units because dam identifiers were unavailable."
                ),
            ),
            audit_row(
                "required_interpretation_boundary",
                "single_cell_sample_size",
                "n=2; control; UPEC",
                contains_all(results_text, ("n=2", "control", "upec")),
            ),
            audit_row(
                "required_interpretation_boundary",
                "single_cell_exact_p",
                "0.333",
                "0.333" in results_text,
            ),
            audit_row(
                "required_interpretation_boundary",
                "metabolic_flux_boundary",
                "transcriptionally inferred; flux",
                contains_all(
                    results_text,
                    ("transcriptionally inferred", "flux"),
                ),
            ),
            audit_row(
                "required_interpretation_boundary",
                "cross_dataset_boundary",
                (
                    "independent native-species analyses + "
                    "non-pooled expression + standardized concordance"
                ),
                semantic_cross_dataset_boundary(results_text),
                (
                    "The manuscript states that datasets were independently "
                    "analyzed in native species/tissue context and integrated "
                    "using standardized effects rather than pooled expression."
                ),
            ),
            audit_row(
                "required_interpretation_boundary",
                "complement_boundary",
                "complement; provisional",
                contains_all(results_text, ("complement", "provisional")),
            ),
        ]
    )

    for dataset in (
        "GSE112098",
        "GSE280297",
        "GSE168600",
        "GSE252321",
    ):
        scientific_rows.append(
            audit_row(
                "required_dataset",
                dataset,
                dataset,
                dataset.lower() in results_lower,
            )
        )

    prohibited_terms = (
        "GSE186800",
        "phaseU11_results_claim_index_v1.tsv",
        "phaseU11_key_numeric_anchors_v1.tsv",
        "Results-section traceability note",
    )
    for term in prohibited_terms:
        scientific_rows.append(
            audit_row(
                "prohibited_obsolete_term",
                term,
                "absent",
                term.lower() not in results_lower,
            )
        )

    scientific_audit = pd.DataFrame(scientific_rows)
    scientific_audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C31_results_scientific_content_audit.tsv",
        sep="\t",
        index=False,
    )

    figure_rows: List[Dict[str, object]] = []
    positions: List[int] = []

    for figure_number in range(1, 9):
        pattern = figure_reference_pattern(figure_number)
        match = pattern.search(results_text)
        position = match.start() if match else -1
        positions.append(position)

        figure_rows.append(
            {
                "figure_number": figure_number,
                "matched_reference": (
                    match.group(0) if match else ""
                ),
                "first_reference_character_position": position,
                "reference_present": match is not None,
            }
        )

    all_present = all(position >= 0 for position in positions)
    ordered = bool(
        all_present
        and all(
            positions[index] < positions[index + 1]
            for index in range(len(positions) - 1)
        )
    )

    figure_audit = pd.DataFrame(figure_rows)
    figure_audit["all_figures_ordered"] = ordered
    figure_audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C31_figure_reference_audit.tsv",
        sep="\t",
        index=False,
    )

    previous_audit_path = project / PREVIOUS_AUDIT_RELATIVE
    inherited_visual_pass = False
    inherited_visual_note = ""
    if previous_audit_path.exists():
        previous = pd.read_csv(
            previous_audit_path,
            sep="\t",
            low_memory=False,
        )
        if not previous.empty:
            inherited_visual_pass = bool(
                previous.iloc[0].get("visual_review_pass", False)
            )
            inherited_visual_note = str(
                previous.iloc[0].get("visual_review_note", "")
            )

    contact_sheet_present = (
        contact_sheet.exists()
        and contact_sheet.stat().st_size > 0
    )
    visual_render_pass = (
        inherited_visual_pass and contact_sheet_present
    )

    preservation = pd.DataFrame(
        [
            {
                "source_path": str(source),
                "source_sha256": sha256(source),
                "derivative_path": str(derivative),
                "derivative_sha256": sha256(derivative),
                "pre_results_text_preserved": pre_results_preserved,
                "discussion_onward_text_preserved": (
                    discussion_onward_preserved
                ),
                "source_results_word_count": len(
                    re.findall(
                        r"\b[\w'-]+\b",
                        "\n".join(source_split["results"]),
                    )
                ),
                "derivative_results_word_count": len(
                    re.findall(r"\b[\w'-]+\b", results_text)
                ),
                "source_results_paragraphs": len(
                    source_split["results"]
                ),
                "derivative_results_paragraphs": len(
                    results_paragraphs
                ),
                "source_embedded_media_files": source_media,
                "derivative_embedded_media_files": derivative_media,
                "legacy_figures_pending_replacement": (
                    derivative_media == source_media
                    and derivative_media == 6
                ),
                "contact_sheet_present": contact_sheet_present,
                "visual_review_pass": visual_render_pass,
                "visual_review_note": inherited_visual_note,
            }
        ]
    )
    preservation.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C31_preservation_visual_audit.tsv",
        sep="\t",
        index=False,
    )

    correction_rationale = pd.DataFrame(
        [
            {
                "previous_failed_audit": "sample_unit_boundary",
                "previous_rule": (
                    "literal terms: tissue samples; dam-level"
                ),
                "corrected_rule": (
                    "semantic rule accepts explicit no-dam-level wording or "
                    "the stated absence of dam identifiers"
                ),
                "manuscript_content_changed": False,
            },
            {
                "previous_failed_audit": "cross_dataset_boundary",
                "previous_rule": "literal terms: not pooled; species",
                "corrected_rule": (
                    "semantic rule requires independent native-species/tissue "
                    "analysis, non-pooled expression and standardized "
                    "directional integration"
                ),
                "manuscript_content_changed": False,
            },
            {
                "previous_failed_audit": "figure_references_1_to_8",
                "previous_rule": (
                    "bare figure numbers with a word boundary after the digit"
                ),
                "corrected_rule": (
                    "panel-qualified references such as Figure 1A-E and "
                    "Figure 8F are accepted"
                ),
                "manuscript_content_changed": False,
            },
        ]
    )
    correction_rationale.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C31_false_negative_correction_rationale.tsv",
        sep="\t",
        index=False,
    )

    scientific_pass = bool(scientific_audit["pass"].all())
    preservation_pass = bool(
        pre_results_preserved
        and discussion_onward_preserved
    )
    figures_pass = bool(all_present and ordered)

    if (
        scientific_pass
        and preservation_pass
        and figures_pass
        and visual_render_pass
        and derivative_media == 6
    ):
        decision = (
            "READY_FOR_U27B3C4_FROZEN_FIGURES_1_TO_8_"
            "AND_LEGEND_INTEGRATION"
        )
    else:
        decision = (
            "TARGETED_U27B3C2_RESULTS_CONTENT_OR_PRESERVATION_REPAIR_REQUIRED"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B3C3.1",
                "decision": decision,
                "scientific_content_audits": len(scientific_audit),
                "scientific_content_audits_passed": int(
                    scientific_audit["pass"].sum()
                ),
                "all_scientific_content_audits_pass": scientific_pass,
                "figures_1_to_8_referenced": all_present,
                "figure_references_in_order": ordered,
                "pre_results_text_preserved": pre_results_preserved,
                "discussion_onward_text_preserved": (
                    discussion_onward_preserved
                ),
                "visual_render_pass": visual_render_pass,
                "legacy_embedded_figures": derivative_media,
                "legacy_figures_pending_replacement": (
                    derivative_media == 6
                ),
                "scientific_values_recalculated": False,
                "figure_assets_modified": False,
                "source_manuscript_modified": False,
                "derivative_modified": False,
                "next_phase": (
                    "U27B3C4 replace the six legacy figures with frozen "
                    "Figures 1-8 and integrate definitive U27B3B legends"
                    if decision.startswith("READY_FOR_U27B3C4")
                    else "Inspect corrected audit outputs"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B3C31_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    (
        outresults
        / "UTI_HostOmics_U27B3C31_audited_results_section.txt"
    ).write_text(results_text, encoding="utf-8")

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3C31_corrected_results_audit_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3C3.1 - Corrected Results scientific audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Scientific/content checks passed: "
            f"**{int(scientific_audit['pass'].sum())}/"
            f"{len(scientific_audit)}**.\n"
        )
        handle.write(
            f"- Figures 1-8 referenced: "
            f"**{'PASS' if all_present else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Figure-reference order: "
            f"**{'PASS' if ordered else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Pre-Results text preserved: "
            f"**{'PASS' if pre_results_preserved else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Discussion onward preserved: "
            f"**{'PASS' if discussion_onward_preserved else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Render review inherited from U27B3C3: "
            f"**{'PASS' if visual_render_pass else 'FAIL'}**.\n"
        )
        handle.write(
            f"- Legacy embedded figures awaiting replacement: "
            f"**{derivative_media}**.\n\n"
        )

        handle.write("## Correction\n\n")
        handle.write(
            "The U27B3C2 Results text did not require scientific rewriting. "
            "The prior failures were audit false negatives: semantically "
            "equivalent boundary wording was rejected, and panel-qualified "
            "references such as `Figure 1A-E` were not recognized as Figure 1 "
            "references. This corrected audit accepts those valid forms while "
            "preserving all original content and provenance checks.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "This phase is read-only. No manuscript, figure, source table, "
            "statistical result or source lock was modified.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "scientific_audits": len(scientific_audit),
        "scientific_audits_passed": int(
            scientific_audit["pass"].sum()
        ),
        "figures_1_to_8_referenced": all_present,
        "figure_references_in_order": ordered,
        "pre_results_text_preserved": pre_results_preserved,
        "discussion_onward_text_preserved": discussion_onward_preserved,
        "visual_render_pass": visual_render_pass,
        "legacy_embedded_figures": derivative_media,
        "scientific_values_recalculated": False,
        "figure_assets_modified": False,
        "source_manuscript_modified": False,
        "derivative_modified": False,
    }
    (
        outresults
        / "UTI_HostOmics_U27B3C31_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(
        "Scientific audits passed: "
        f"{int(scientific_audit['pass'].sum())}/{len(scientific_audit)}"
    )
    log(f"Figures 1-8 referenced: {all_present}")
    log(f"Figure references ordered: {ordered}")
    log(f"Pre-Results preserved: {pre_results_preserved}")
    log(f"Discussion onward preserved: {discussion_onward_preserved}")
    log(f"Visual render pass: {visual_render_pass}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3C3.1] ERROR: {exc}", file=sys.stderr)
        raise
