#!/usr/bin/env python3
"""
Phase U27B3E2
Confirm reference, front-matter and Supplementary Tables S1-S10 source
architecture after the cleaned v6.2 submission-architecture manuscript.

This phase is read-only. It does not modify the manuscript.

Inputs
------
- U27B3E1 cleaned v6.2 manuscript
- U27B3E1 reference-gap register
- U27B3E1 Zotero working table
- U27B3E1 supplementary-table manifest
- U27B3E1 supplementary source-candidate registry
- U27B3E1 submission-finalization checklist

Outputs
-------
- Source-lock map for Supplementary Tables S1-S10
- Reference-gap candidate map
- Front-matter/finalization response worksheet
- Copy-paste user response template
- Phase decision and report

No manuscript, figure, source table, result, citation field or source lock is
modified by this phase.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import pandas as pd

try:
    from docx import Document
except ImportError as exc:
    raise RuntimeError("python-docx is required for U27B3E2.") from exc


VERSION = "U27B3E2_v1.0_2026-07-16"
TAG = "phaseU27B3E2_reference_frontmatter_supplement_source_confirmation"
E1_TAG = "phaseU27B3E1_reference_supplement_submission_architecture"

DEFAULT_MANUSCRIPT = (
    "__UTI_HOSTOMICS_PROJECT_ROOT__/"
    "09_manuscript_docx/phaseU27B3E1_reference_supplement_submission_architecture/"
    "UTI_HostOmics_preZotero_manuscript_v6_2_"
    "U27B3E1_submission_architecture_cleaned.docx"
)

SUPPLEMENT_EXPECTED = {
    1: "Dataset architecture, sample design and inclusion roles for GSE112098, GSE280297, GSE168600 and GSE252321.",
    2: "Expanded 78-submodule library organized across ten biological axes.",
    3: "Dataset-specific module effects and factorial or adjusted contrasts.",
    4: "Cross-dataset recurrence, directional concordance and evidence-class assignments.",
    5: "GSE280297 pregnancy, tissue and outcome-specific module effects.",
    6: "GSE252321 quality control, cluster markers, broad populations and refined subtypes.",
    7: "Broad-cell and refined-subtype pseudobulk module localization results.",
    8: "Complement-stage and endocrine-metabolic cellular attribution tables.",
    9: "Figure 1-8 source-value manifest and panel-level provenance registry.",
    10: "Interpretation-boundary, sensitivity and manuscript claim-traceability register.",
}

DIRECT_SOURCE_OVERRIDES: Dict[int, List[str]] = {
    2: [
        "03_metadata/phaseU26A_expanded_endocrine_metabolic_immune_feasibility/UTI_HostOmics_U26A_expanded_submodule_library.tsv",
    ],
    9: [
        "03_metadata/phaseU27B3A_complete_eight_figure_package_assembly/UTI_HostOmics_U27B3A_complete_asset_manifest.tsv",
        "03_metadata/phaseU27B3A_complete_eight_figure_package_assembly/UTI_HostOmics_U27B3A_figure_and_panel_title_registry.tsv",
        "03_metadata/phaseU27B3B_definitive_figure_legend_construction/UTI_HostOmics_U27B3B_panel_legend_provenance_registry.tsv",
    ],
    10: [
        "03_metadata/phaseU27B3B_definitive_figure_legend_construction/UTI_HostOmics_U27B3B_caveat_terminology_registry.tsv",
        "06_tables/phaseU27B3C31_corrected_results_scientific_audit/UTI_HostOmics_U27B3C31_results_scientific_content_audit.tsv",
        "06_tables/phaseU27B3C31_corrected_results_scientific_audit/UTI_HostOmics_U27B3C31_false_negative_correction_rationale.tsv",
    ],
}

FRONT_MATTER_ITEMS = [
    (
        "author_order",
        "Final author list and order",
        "Provide the exact author names in publication order, including initials and diacritics.",
        "USER_INPUT_REQUIRED",
    ),
    (
        "affiliation_mapping",
        "Affiliations and author-affiliation mapping",
        "Provide the numbered affiliation list and map each author to the correct affiliation numbers.",
        "USER_INPUT_REQUIRED",
    ),
    (
        "corresponding_author",
        "Corresponding-author details",
        "Provide corresponding-author name, institutional postal address, email and ORCID if used.",
        "USER_INPUT_REQUIRED",
    ),
    (
        "repository",
        "Code/data repository statement",
        "Provide the final public repository URL and DOI/archival identifier, or confirm that this remains pending.",
        "USER_INPUT_REQUIRED",
    ),
    (
        "credit_contributions",
        "CRediT author contributions",
        "Provide or confirm the contribution roles for every author.",
        "USER_INPUT_REQUIRED",
    ),
    (
        "competing_interests",
        "Competing-interest declaration",
        "Provide the final declaration exactly as it should appear in the manuscript.",
        "USER_INPUT_REQUIRED",
    ),
    (
        "acknowledgements",
        "Acknowledgements",
        "Provide the final acknowledgement text, including non-author assistance and infrastructure support.",
        "USER_INPUT_REQUIRED",
    ),
    (
        "funding_confirmation",
        "Funding statement confirmation",
        "Confirm the current funding statement and grant wording before final insertion.",
        "CONFIRMATION_REQUIRED",
    ),
]


def log(message: str) -> None:
    print(f"[U27B3E2] {message}", flush=True)


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def read_tsv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required U27B3E1 input not found: {path}")
    return pd.read_csv(path, sep="\t", low_memory=False)


def existing_paths(project: Path, relative_paths: Sequence[str]) -> List[Path]:
    result = []
    for relative in relative_paths:
        path = project / relative
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            result.append(path)
    return result


def candidates_for_table(
    registry: pd.DataFrame,
    table_label: str,
) -> pd.DataFrame:
    subset = registry[
        registry["supplementary_table"].astype(str) == table_label
    ].copy()
    if subset.empty:
        return subset

    subset["candidate_rank_numeric"] = pd.to_numeric(
        subset["candidate_rank"],
        errors="coerce",
    )
    subset["candidate_score_numeric"] = pd.to_numeric(
        subset["candidate_score"],
        errors="coerce",
    ).fillna(0)
    subset["path_exists"] = subset["candidate_path"].astype(str).map(
        lambda value: bool(value) and Path(value).exists()
    )
    subset = subset[subset["path_exists"]].copy()
    return subset.sort_values(
        ["candidate_rank_numeric", "candidate_score_numeric"],
        ascending=[True, False],
    )


def source_lock_rows(
    project: Path,
    manifest: pd.DataFrame,
    registry: pd.DataFrame,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []

    for number in range(1, 11):
        label = f"Table S{number}"
        manifest_rows = manifest[
            manifest["table_number"].astype(int) == number
        ] if "table_number" in manifest.columns else pd.DataFrame()

        description = SUPPLEMENT_EXPECTED[number]
        if not manifest_rows.empty and "description" in manifest_rows.columns:
            candidate_description = normalize(manifest_rows.iloc[0]["description"])
            if candidate_description:
                description = candidate_description

        direct = existing_paths(
            project,
            DIRECT_SOURCE_OVERRIDES.get(number, []),
        )

        ranked = candidates_for_table(registry, label)
        ranked_paths = [
            Path(value)
            for value in ranked.get("candidate_path", pd.Series(dtype=str)).astype(str).tolist()
            if value and Path(value).exists()
        ]

        selected: List[Path] = []
        status = ""
        assembly_mode = ""
        rationale = ""

        if direct:
            selected.extend(direct)
            status = "LOCKED_HIGH_CONFIDENCE"
            assembly_mode = "DIRECT_OR_COMPOSITE_FROM_EXACT_FROZEN_SOURCES"
            rationale = "Exact frozen source paths were available."
        elif ranked_paths:
            # Keep up to three distinct high-ranked sources. Supplementary tables
            # often require a composite rather than a blind copy of one file.
            for path in ranked_paths:
                if path not in selected:
                    selected.append(path)
                if len(selected) == 3:
                    break

            top_score = float(ranked.iloc[0]["candidate_score_numeric"])
            second_score = (
                float(ranked.iloc[1]["candidate_score_numeric"])
                if len(ranked) > 1
                else 0.0
            )
            score_margin = top_score - second_score

            if top_score >= 8 and score_margin >= 2:
                status = "PROVISIONAL_HIGH_CONFIDENCE"
            else:
                status = "PROVISIONAL_COMPOSITE_REVIEW"
            assembly_mode = "ASSEMBLE_FROM_RANKED_EXISTING_SOURCES"
            rationale = (
                f"Selected the top {len(selected)} existing ranked source(s); "
                f"top score={top_score:.1f}, margin={score_margin:.1f}."
            )
        else:
            status = "UNRESOLVED_NO_EXISTING_SOURCE"
            assembly_mode = "MANUAL_SOURCE_IDENTIFICATION_REQUIRED"
            rationale = "No existing candidate source file was available."

        for source_index, path in enumerate(selected, start=1):
            rows.append(
                {
                    "supplementary_table": label,
                    "table_number": number,
                    "description": description,
                    "source_sequence": source_index,
                    "source_path": str(path),
                    "source_exists": path.exists(),
                    "source_size_bytes": path.stat().st_size if path.exists() else 0,
                    "source_status": status,
                    "assembly_mode": assembly_mode,
                    "selection_rationale": rationale,
                    "final_user_confirmation_required": status != "LOCKED_HIGH_CONFIDENCE",
                }
            )

        if not selected:
            rows.append(
                {
                    "supplementary_table": label,
                    "table_number": number,
                    "description": description,
                    "source_sequence": "",
                    "source_path": "",
                    "source_exists": False,
                    "source_size_bytes": 0,
                    "source_status": status,
                    "assembly_mode": assembly_mode,
                    "selection_rationale": rationale,
                    "final_user_confirmation_required": True,
                }
            )

    return pd.DataFrame(rows)


def reference_candidate_map(
    gaps: pd.DataFrame,
    references: pd.DataFrame,
) -> pd.DataFrame:
    if gaps.empty or references.empty:
        return pd.DataFrame(
            columns=[
                "gap_id",
                "gap_text",
                "candidate_rank",
                "candidate_reference",
                "keyword_overlap",
                "status",
            ]
        )

    reference_records = []
    for index, row in references.iterrows():
        blob = normalize(" | ".join(str(value) for value in row.tolist()))
        reference_records.append((index, blob))

    rows: List[Dict[str, object]] = []
    for gap_index, gap_row in gaps.iterrows():
        gap_id = normalize(gap_row.get("gap_id", f"GAP_{gap_index + 1}"))
        gap_text = normalize(
            gap_row.get("gap_text", gap_row.get("description", ""))
        )
        gap_words = {
            word
            for word in re.findall(r"[A-Za-z0-9-]+", gap_text.lower())
            if len(word) >= 4
        }

        scored: List[Tuple[int, int, str, List[str]]] = []
        for reference_index, blob in reference_records:
            reference_words = set(
                word
                for word in re.findall(r"[A-Za-z0-9-]+", blob.lower())
                if len(word) >= 4
            )
            overlap = sorted(gap_words & reference_words)
            scored.append((len(overlap), reference_index, blob, overlap))

        scored.sort(key=lambda item: item[0], reverse=True)
        top = [item for item in scored[:5] if item[0] > 0]

        if not top:
            rows.append(
                {
                    "gap_id": gap_id,
                    "gap_text": gap_text,
                    "candidate_rank": "",
                    "candidate_reference": "",
                    "keyword_overlap": "",
                    "status": "LITERATURE_CONFIRMATION_REQUIRED",
                }
            )
            continue

        for rank, (score, _, blob, overlap) in enumerate(top, start=1):
            rows.append(
                {
                    "gap_id": gap_id,
                    "gap_text": gap_text,
                    "candidate_rank": rank,
                    "candidate_reference": blob,
                    "keyword_overlap": "; ".join(overlap),
                    "status": "CANDIDATE_ONLY_NOT_FINALIZED",
                }
            )

    return pd.DataFrame(rows)


def paragraph_after_heading(document: Document, heading: str) -> str:
    paragraphs = document.paragraphs
    indices = [
        index
        for index, paragraph in enumerate(paragraphs)
        if normalize(paragraph.text).lower().rstrip(".") == heading.lower().rstrip(".")
    ]
    if len(indices) != 1:
        return ""
    index = indices[0] + 1
    values = []
    while index < len(paragraphs):
        text = normalize(paragraphs[index].text)
        if text and paragraphs[index].style.name.lower().startswith("heading"):
            break
        if text:
            values.append(text)
        index += 1
    return " ".join(values)


def build_front_matter_worksheet(manuscript: Path) -> pd.DataFrame:
    document = Document(manuscript)
    current_sections = {
        "credit_contributions": paragraph_after_heading(document, "Author contributions"),
        "competing_interests": paragraph_after_heading(document, "Competing interests"),
        "acknowledgements": paragraph_after_heading(document, "Acknowledgements"),
        "funding_confirmation": paragraph_after_heading(document, "Funding"),
        "repository": paragraph_after_heading(document, "Code availability"),
    }

    rows = []
    for item_id, label, request, status in FRONT_MATTER_ITEMS:
        rows.append(
            {
                "item_id": item_id,
                "item_label": label,
                "current_or_provisional_text": current_sections.get(item_id, ""),
                "requested_user_input": request,
                "status": status,
                "user_response": "",
            }
        )
    return pd.DataFrame(rows)


def write_user_template(path: Path, worksheet: pd.DataFrame) -> None:
    labels = {row["item_id"]: row for _, row in worksheet.iterrows()}
    text = f"""# UTI HostOmics front-matter completion template

Copy this block into ChatGPT after completing the fields.

## Final author order
{labels['author_order']['user_response'] or '[ENTER EXACT AUTHOR ORDER]'}

## Affiliations and author-affiliation mapping
{labels['affiliation_mapping']['user_response'] or '[ENTER NUMBERED AFFILIATIONS AND AUTHOR MAPPING]'}

## Corresponding author
{labels['corresponding_author']['user_response'] or '[ENTER NAME, POSTAL ADDRESS, EMAIL AND ORCID IF USED]'}

## Public repository
{labels['repository']['user_response'] or '[ENTER FINAL URL AND DOI/ARCHIVE IDENTIFIER, OR STATE PENDING]'}

## CRediT contributions
{labels['credit_contributions']['user_response'] or '[ENTER CONTRIBUTION STATEMENT FOR EACH AUTHOR]'}

## Competing interests
{labels['competing_interests']['user_response'] or '[ENTER FINAL DECLARATION]'}

## Acknowledgements
{labels['acknowledgements']['user_response'] or '[ENTER FINAL ACKNOWLEDGEMENT TEXT]'}

## Funding confirmation
Current/provisional text:
{labels['funding_confirmation']['current_or_provisional_text'] or '[NO CURRENT TEXT EXTRACTED]'}

Final confirmed text:
[ENTER OR CONFIRM FINAL FUNDING STATEMENT]
"""
    path.write_text(text, encoding="utf-8")


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
        raise FileNotFoundError(f"Cleaned v6.2 manuscript not found: {manuscript}")

    e1_tables = project / "06_tables" / E1_TAG
    e1_results = project / "05_results" / E1_TAG

    manifest = read_tsv(
        e1_tables / "UTI_HostOmics_U27B3E1_supplementary_table_manifest.tsv"
    )
    registry = read_tsv(
        e1_tables / "UTI_HostOmics_U27B3E1_supplementary_source_candidate_registry.tsv"
    )
    gaps = read_tsv(
        e1_tables / "UTI_HostOmics_U27B3E1_reference_gap_register.tsv"
    )
    references = read_tsv(
        e1_tables / "UTI_HostOmics_U27B3E1_Zotero_reference_table.tsv"
    )
    checklist = read_tsv(
        e1_tables / "UTI_HostOmics_U27B3E1_submission_finalization_checklist.tsv"
    )

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    outmanuscript = project / "07_manuscript" / TAG
    for directory in (outtables, outmetadata, outresults, outmanuscript):
        directory.mkdir(parents=True, exist_ok=True)

    source_map = source_lock_rows(project, manifest, registry)
    source_map.to_csv(
        outtables / "UTI_HostOmics_U27B3E2_supplementary_source_lock_map.tsv",
        sep="\t",
        index=False,
    )

    source_summary = (
        source_map.groupby(
            ["supplementary_table", "table_number", "description"],
            as_index=False,
        )
        .agg(
            selected_source_count=("source_path", lambda values: sum(bool(normalize(value)) for value in values)),
            all_sources_exist=("source_exists", "all"),
            source_status=("source_status", "first"),
            assembly_mode=("assembly_mode", "first"),
            final_user_confirmation_required=("final_user_confirmation_required", "max"),
        )
        .sort_values("table_number")
    )
    source_summary.to_csv(
        outtables / "UTI_HostOmics_U27B3E2_supplementary_source_confirmation_summary.tsv",
        sep="\t",
        index=False,
    )

    reference_map = reference_candidate_map(gaps, references)
    reference_map.to_csv(
        outtables / "UTI_HostOmics_U27B3E2_reference_gap_candidate_map.tsv",
        sep="\t",
        index=False,
    )

    worksheet = build_front_matter_worksheet(manuscript)
    worksheet.to_csv(
        outtables / "UTI_HostOmics_U27B3E2_front_matter_user_input_worksheet.tsv",
        sep="\t",
        index=False,
    )

    user_template = (
        outmanuscript / "UTI_HostOmics_U27B3E2_front_matter_copy_paste_template.md"
    )
    write_user_template(user_template, worksheet)

    checklist.to_csv(
        outtables / "UTI_HostOmics_U27B3E2_carried_submission_finalization_checklist.tsv",
        sep="\t",
        index=False,
    )

    unresolved_supplements = int(
        source_summary["source_status"].astype(str).str.startswith("UNRESOLVED").sum()
    )
    supplements_with_sources = int((source_summary["selected_source_count"] > 0).sum())
    exact_locked = int((source_summary["source_status"] == "LOCKED_HIGH_CONFIDENCE").sum())
    provisional = int(source_summary["source_status"].astype(str).str.startswith("PROVISIONAL").sum())
    open_front_matter_items = int(worksheet["status"].isin(["USER_INPUT_REQUIRED", "CONFIRMATION_REQUIRED"]).sum())
    reference_gaps = int(gaps.shape[0])

    if supplements_with_sources == 10 and unresolved_supplements == 0:
        decision = (
            "READY_FOR_U27B3E3_SUPPLEMENTARY_TABLE_MATERIALIZATION_"
            "WITH_FRONT_MATTER_USER_INPUT_REQUIRED"
        )
    else:
        decision = "TARGETED_U27B3E2_SUPPLEMENT_SOURCE_CONFIRMATION_REQUIRED"

    pd.DataFrame(
        [
            {
                "phase": "U27B3E2",
                "decision": decision,
                "manuscript_path": str(manuscript),
                "supplementary_tables_expected": 10,
                "supplementary_tables_with_selected_sources": supplements_with_sources,
                "supplementary_tables_high_confidence_locked": exact_locked,
                "supplementary_tables_provisional": provisional,
                "supplementary_tables_unresolved": unresolved_supplements,
                "reference_gaps": reference_gaps,
                "reference_candidate_rows": len(reference_map),
                "front_matter_items_requiring_user_input_or_confirmation": open_front_matter_items,
                "manuscript_modified": False,
                "scientific_values_recalculated": False,
                "figure_assets_modified": False,
                "source_locks_changed": False,
                "next_phase": (
                    "U27B3E3 materialize Supplementary Tables S1-S10 from the confirmed source map; "
                    "front-matter insertion remains pending user responses"
                    if decision.startswith("READY_FOR_U27B3E3")
                    else "Review unresolved supplementary source mappings"
                ),
            }
        ]
    ).to_csv(
        outtables / "UTI_HostOmics_U27B3E2_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults / "UTI_HostOmics_U27B3E2_reference_frontmatter_supplement_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# Phase U27B3E2 - Reference, front matter and supplementary source confirmation\n\n")
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(f"- Cleaned manuscript: `{manuscript}`\n")
        handle.write(f"- Supplementary tables with selected sources: **{supplements_with_sources}/10**.\n")
        handle.write(f"- High-confidence locked supplementary tables: **{exact_locked}**.\n")
        handle.write(f"- Provisional supplementary source mappings: **{provisional}**.\n")
        handle.write(f"- Unresolved supplementary tables: **{unresolved_supplements}**.\n")
        handle.write(f"- Reference gaps: **{reference_gaps}**.\n")
        handle.write(f"- Front-matter items requiring user input/confirmation: **{open_front_matter_items}**.\n\n")

        handle.write("## Supplementary source boundary\n\n")
        handle.write(
            "Exact frozen sources are locked where available. Other tables are mapped to the top existing "
            "ranked sources and remain provisional until materialization validates schema, row counts and biological scope.\n\n"
        )

        handle.write("## Reference boundary\n\n")
        handle.write(
            "Keyword-ranked reference candidates are navigation aids only. Final citations require literature and Zotero confirmation; "
            "this phase does not fabricate or insert references.\n\n"
        )

        handle.write("## Front-matter boundary\n\n")
        handle.write(
            "Author order, affiliations, corresponding-author details, repository identifier, CRediT roles, competing interests, "
            "acknowledgements and funding wording remain explicit user-confirmation tasks. The copy-paste response template is available at "
            f"`{user_template}`.\n"
        )

    manifest_json = {
        "version": VERSION,
        "decision": decision,
        "manuscript_path": str(manuscript),
        "supplementary_tables_with_sources": supplements_with_sources,
        "high_confidence_locked": exact_locked,
        "provisional_mappings": provisional,
        "unresolved_supplements": unresolved_supplements,
        "reference_gaps": reference_gaps,
        "front_matter_items_open": open_front_matter_items,
        "manuscript_modified": False,
        "scientific_values_recalculated": False,
        "figure_assets_modified": False,
        "source_locks_changed": False,
    }
    (
        outresults / "UTI_HostOmics_U27B3E2_run_manifest.json"
    ).write_text(json.dumps(manifest_json, indent=2), encoding="utf-8")

    log(f"Supplementary tables with selected sources: {supplements_with_sources}/10")
    log(f"High-confidence locked: {exact_locked}")
    log(f"Provisional mappings: {provisional}")
    log(f"Unresolved supplementary tables: {unresolved_supplements}")
    log(f"Reference gaps: {reference_gaps}")
    log(f"Front-matter items open: {open_front_matter_items}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E2] ERROR: {exc}", file=sys.stderr)
        raise
