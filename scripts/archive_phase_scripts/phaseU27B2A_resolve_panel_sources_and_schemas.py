#!/usr/bin/env python3
"""
Phase U27B2A
Resolve exact source files and schemas for all 57 frozen main-figure panels.

Why this phase is necessary
---------------------------
U27B1 froze the scientific display architecture, and U27B1.1 established that
missing legacy Working Figures 2-5 are non-blocking. Before scripted figure
construction, each frozen panel must be linked to current project tables,
metadata, scripts or canonical U27A4 visual-reference assets.

This phase:
1. inventories current source tables, metadata and relevant scripts;
2. records table schemas without loading full large matrices;
3. parses analysis scripts for literal source-file references;
4. resolves ranked source candidates for every frozen main panel;
5. distinguishes data-driven panels, conceptual source bundles and U27A4
   visual-reference panels;
6. writes an implementation-ready panel-source registry.

No figures, source data, manuscript text or scientific values are modified.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


VERSION = "U27B2A_v1.0_2026-07-15"
TAG = "phaseU27B2A_panel_source_and_schema_resolution"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"
RELEASE_TAG = "phaseU27B11_legacy_source_confirmation_resolution"

TABLE_EXTENSIONS = (
    ".tsv",
    ".csv",
    ".tsv.gz",
    ".csv.gz",
    ".txt",
)

FIGURE_EXTENSIONS = (
    ".png",
    ".svg",
    ".pdf",
)

SCRIPT_EXTENSIONS = (
    ".py",
    ".R",
    ".r",
    ".sh",
)

SCAN_ROOTS = [
    "03_metadata",
    "05_results",
    "06_tables",
    "10_scripts",
]

PHASE_DIRECTORY_HINTS = {
    "U26A": [
        "phaseU26A",
        "phaseU26A5",
    ],
    "U26B1_1": [
        "phaseU26B1_1_GSE280297_stability_refinement",
    ],
    "U26B2B": [
        "phaseU26B2B_cross_dataset_scoring_integration",
    ],
    "U26B2B1": [
        "phaseU26B2B1_independent_dataset_evidence_collapse",
    ],
    "U26C1": [
        "phaseU26C1_interpretation_threshold_and_branch_refinement",
    ],
    "U26D1A": [
        "phaseU26D1A",
    ],
    "U26D2A": [
        "phaseU26D2A_GSE252321_marker_celltype_reconstruction",
    ],
    "U26D2A1": [
        "phaseU26D2A1_GSE252321_annotation_refinement",
    ],
    "U26D2B": [
        "phaseU26D2B_GSE252321_refined_celltype_pseudobulk",
    ],
    "U26D2C": [
        "phaseU26D2C_cellular_localization_synthesis",
    ],
    "U27A4": [
        "phaseU27A4_final_visual_audit",
        "phaseU27A32_final_title_spacing_repair",
        "phaseU27A3_visual_diversity_redesign",
    ],
}

SOURCE_PREFIX_HINTS = [
    ("U26B2B1", "U26B2B1"),
    ("U26B2B_", "U26B2B"),
    ("U26C1", "U26C1"),
    ("U26B1_1", "U26B1_1"),
    ("U26D1A", "U26D1A"),
    ("U26D2A1", "U26D2A1"),
    ("U26D2A", "U26D2A"),
    ("U26D2B", "U26D2B"),
    ("U26D2C", "U26D2C"),
    ("U27A4", "U27A4"),
    ("U26A", "U26A"),
]

CONCEPTUAL_SOURCE_IDS = {
    "01_study_design_and_question_map",
    "dataset_manifest",
    "contrast_manifest",
    "phase_workflow_manifest",
    "U26C1_core_network",
    "U26C1_complement_core",
    "U26B2B1_U26C_network",
    "U26C1_pregnancy_model",
    "U26D_cellular_model",
    "U26C1_steroid_quadrant",
    "U26C1_U26D2C_metabolic_network",
    "U26C1_U26D2C_complement_topology",
    "U26C1_U26D2C_evidence_boundary",
}

STOPWORDS = {
    "and", "the", "of", "to", "in", "by", "with", "from", "versus",
    "across", "effect", "effects", "figure", "panel", "source", "results",
    "primary", "final", "working", "context", "contexts", "summary",
    "rebuild", "selected", "independent", "cell", "cellular",
}

SYNONYMS = {
    "treg": ["regulatory", "foxp3", "il2ra", "ctla4", "tnfrsf18"],
    "tnfsf9": ["cd137l", "tnfsf9"],
    "macrophage": ["macrophage", "monocyte", "mrc1", "retnla"],
    "steroid": ["steroid", "androgen", "estrogen", "cholesterol"],
    "complement": ["complement", "c3a", "c5a", "opsonophagocytosis", "mac"],
    "carbon": ["glycolysis", "glycogen", "lactate", "hif1a", "pentose"],
    "adipokine": ["leptin", "resistin", "adipokine", "irs", "pi3k"],
    "redox": ["redox", "nrf2", "nad", "purine", "oxidation"],
    "pregnancy": ["pregnancy", "preterm", "term", "uterus", "placenta"],
    "design": ["design", "sample", "metadata", "contrast"],
    "module": ["module", "submodule", "library", "dictionary"],
}


def log(message: str) -> None:
    print(f"[U27B2A] {message}", flush=True)


def normalize_token(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def tokens(text: str) -> List[str]:
    raw = re.split(r"[^A-Za-z0-9]+", str(text).lower())
    return [
        token for token in raw
        if len(token) >= 3 and token not in STOPWORDS
    ]


def expanded_tokens(text: str) -> List[str]:
    result = set(tokens(text))
    joined = " ".join(result)
    for key, values in SYNONYMS.items():
        if key in result or key in joined:
            result.update(values)
    return sorted(result)


def is_table_file(path: Path) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(extension) for extension in TABLE_EXTENSIONS)


def is_script_file(path: Path) -> bool:
    return path.suffix in SCRIPT_EXTENSIONS


def is_figure_file(path: Path) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(extension) for extension in FIGURE_EXTENSIONS)


def phase_from_path(path: Path) -> str:
    text = str(path)
    matches = re.findall(r"phaseU[0-9A-Za-z_]+", text)
    return matches[-1] if matches else ""


def open_text(path: Path):
    if path.name.lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def sniff_delimiter(path: Path) -> str:
    lower = path.name.lower()
    if ".tsv" in lower:
        return "\t"
    if ".csv" in lower:
        return ","

    try:
        with open_text(path) as handle:
            sample = handle.read(8192)
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,;")
        return dialect.delimiter
    except Exception:
        return "\t"


def inspect_table_schema(path: Path) -> Dict[str, object]:
    result: Dict[str, object] = {
        "path": str(path),
        "filename": path.name,
        "phase": phase_from_path(path),
        "size_bytes": path.stat().st_size,
        "delimiter": "",
        "n_columns": None,
        "columns": "",
        "sample_values_json": "",
        "schema_read_error": "",
    }

    try:
        delimiter = sniff_delimiter(path)
        frame = pd.read_csv(
            path,
            sep=delimiter,
            nrows=3,
            low_memory=False,
            compression="infer",
        )
        sample_values = {}
        for column in frame.columns[:12]:
            values = (
                frame[column]
                .dropna()
                .astype(str)
                .head(3)
                .tolist()
            )
            sample_values[str(column)] = values

        result.update(
            {
                "delimiter": "\\t" if delimiter == "\t" else delimiter,
                "n_columns": len(frame.columns),
                "columns": ";".join(map(str, frame.columns)),
                "sample_values_json": json.dumps(
                    sample_values,
                    ensure_ascii=True,
                ),
            }
        )
    except Exception as exc:
        result["schema_read_error"] = repr(exc)

    return result


def inventory_sources(project: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    table_rows = []
    script_rows = []

    for root_relative in SCAN_ROOTS:
        root = project / root_relative
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if is_table_file(path):
                table_rows.append(inspect_table_schema(path))
            elif is_script_file(path):
                script_rows.append(
                    {
                        "path": str(path),
                        "filename": path.name,
                        "phase": phase_from_path(path),
                        "size_bytes": path.stat().st_size,
                    }
                )

    tables = pd.DataFrame(table_rows)
    scripts = pd.DataFrame(script_rows)

    if not tables.empty:
        tables = tables.sort_values(
            ["phase", "filename", "path"]
        )
    if not scripts.empty:
        scripts = scripts.sort_values(
            ["phase", "filename", "path"]
        )

    return tables, scripts


def parse_script_references(
    project: Path,
    scripts: pd.DataFrame,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    pattern = re.compile(
        r"""["']([^"']+\.(?:tsv|csv|txt|tsv\.gz|csv\.gz|png|svg|pdf))["']""",
        flags=re.IGNORECASE,
    )

    if scripts.empty:
        return pd.DataFrame(
            columns=[
                "script_path", "script_phase", "literal_reference",
                "resolved_candidate_path", "resolved_exists",
            ]
        )

    for _, script_row in scripts.iterrows():
        script_path = Path(script_row["path"])
        try:
            content = script_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            continue

        for reference in sorted(set(pattern.findall(content))):
            reference_path = Path(reference)

            candidates = []
            if reference_path.is_absolute():
                candidates.append(reference_path)
            else:
                candidates.extend(
                    [
                        project / reference_path,
                        script_path.parent / reference_path,
                    ]
                )

            resolved = ""
            exists = False
            for candidate in candidates:
                if candidate.exists():
                    resolved = str(candidate.resolve())
                    exists = True
                    break

            rows.append(
                {
                    "script_path": str(script_path),
                    "script_phase": script_row.get("phase", ""),
                    "literal_reference": reference,
                    "resolved_candidate_path": resolved,
                    "resolved_exists": exists,
                }
            )

    return pd.DataFrame(rows)


def source_phase_hint(source_id: str) -> Optional[str]:
    for prefix, hint in SOURCE_PREFIX_HINTS:
        if str(source_id).startswith(prefix):
            return hint
    return None


def directory_hint_match(path: str, phase_hint: Optional[str]) -> bool:
    if not phase_hint:
        return False
    lower = path.lower()
    return any(
        hint.lower() in lower
        for hint in PHASE_DIRECTORY_HINTS.get(phase_hint, [])
    )


def file_relevance_score(
    row: pd.Series,
    panel_query: str,
    source_id: str,
    phase_hint: Optional[str],
) -> float:
    filename = str(row.get("filename", ""))
    path = str(row.get("path", ""))
    columns = str(row.get("columns", ""))

    searchable = " ".join(
        [
            normalize_token(filename),
            normalize_token(path),
            normalize_token(columns),
        ]
    )
    query_tokens = expanded_tokens(panel_query)
    source_tokens = expanded_tokens(source_id)

    score = 0.0

    for token in query_tokens:
        if token in normalize_token(filename):
            score += 5.0
        elif token in normalize_token(path):
            score += 2.0
        elif token in normalize_token(columns):
            score += 1.0

    for token in source_tokens:
        if token in normalize_token(filename):
            score += 7.0
        elif token in normalize_token(path):
            score += 3.0
        elif token in normalize_token(columns):
            score += 1.5

    if directory_hint_match(path, phase_hint):
        score += 25.0

    if source_id.lower() in searchable:
        score += 20.0

    if "decision" in filename.lower():
        score -= 8.0
    if "manifest" in filename.lower() and "manifest" not in panel_query.lower():
        score -= 2.0
    if row.get("schema_read_error", ""):
        score -= 5.0

    return score


def visual_reference_candidates(
    project: Path,
    source_id: str,
) -> List[str]:
    match = re.match(r"U27A4_Figure_(\d+)", str(source_id))
    if not match:
        return []

    figure_number = match.group(1)
    directory = (
        project
        / "06_figures"
        / "phaseU27A4_final_visual_audit"
    )
    candidates = []
    for extension in ("svg", "pdf", "png"):
        path = directory / (
            f"UTI_HostOmics_U27A4_Figure_{figure_number}.{extension}"
        )
        if path.exists():
            candidates.append(str(path))
    return candidates


def conceptual_bundle_candidates(
    project: Path,
    source_id: str,
    primary_source: str,
) -> List[str]:
    bundles = []

    if source_id in {
        "dataset_manifest",
        "contrast_manifest",
        "01_study_design_and_question_map",
    }:
        for relative in (
            "03_metadata",
            "06_tables/phaseU27B1_architecture_freeze_and_asset_mapping",
        ):
            path = project / relative
            if path.exists():
                bundles.append(str(path))

    if source_id == "phase_workflow_manifest":
        for relative in (
            "05_results",
            "06_tables",
            "10_scripts",
        ):
            path = project / relative
            if path.exists():
                bundles.append(str(path))

    phase_hint = source_phase_hint(source_id)
    if phase_hint:
        for root_relative in ("03_metadata", "05_results", "06_tables"):
            root = project / root_relative
            if not root.exists():
                continue
            for hint in PHASE_DIRECTORY_HINTS.get(phase_hint, []):
                for candidate in root.glob(f"*{hint}*"):
                    if candidate.exists():
                        bundles.append(str(candidate))

    return sorted(set(bundles))


def resolve_panels(
    project: Path,
    panel_mapping: pd.DataFrame,
    tables: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    resolution_rows = []
    candidate_rows = []

    for _, panel in panel_mapping.iterrows():
        source_id = str(panel["source_id"])
        panel_query = " ".join(
            [
                str(panel["panel_title"]),
                str(panel["primary_source"]),
                source_id,
            ]
        )
        phase_hint = source_phase_hint(source_id)
        construction_mode = str(panel["construction_mode"])

        visual_candidates = visual_reference_candidates(
            project,
            source_id,
        )

        conceptual = (
            source_id in CONCEPTUAL_SOURCE_IDS
            or construction_mode == "conceptual_rebuild"
        )
        bundle_candidates = (
            conceptual_bundle_candidates(
                project,
                source_id,
                str(panel["primary_source"]),
            )
            if conceptual
            else []
        )

        ranked = []
        if not tables.empty:
            working = tables.copy()
            working["candidate_score"] = working.apply(
                file_relevance_score,
                axis=1,
                panel_query=panel_query,
                source_id=source_id,
                phase_hint=phase_hint,
            )
            working = working[
                working["candidate_score"] > 0
            ].sort_values(
                ["candidate_score", "size_bytes"],
                ascending=[False, False],
            )
            ranked = working.head(8).to_dict("records")

        for rank, candidate in enumerate(ranked, start=1):
            candidate_rows.append(
                {
                    "final_figure": panel["final_figure"],
                    "panel": panel["panel"],
                    "panel_key": panel["panel_key"],
                    "source_id": source_id,
                    "rank": rank,
                    "candidate_score": candidate["candidate_score"],
                    "candidate_path": candidate["path"],
                    "candidate_filename": candidate["filename"],
                    "candidate_phase": candidate.get("phase", ""),
                    "candidate_columns": candidate.get("columns", ""),
                    "schema_read_error": candidate.get(
                        "schema_read_error", ""
                    ),
                }
            )

        if conceptual:
            resolution_type = "conceptual_source_bundle"
            resolved = bool(bundle_candidates or ranked)
        elif source_id.startswith("U27A4_Figure_"):
            resolution_type = "U27A4_visual_reference_plus_source_tables"
            resolved = bool(visual_candidates and ranked)
        else:
            resolution_type = "table_or_metadata_driven"
            resolved = bool(ranked)

        top_path = ranked[0]["path"] if ranked else ""
        top_score = (
            float(ranked[0]["candidate_score"])
            if ranked
            else None
        )
        top_columns = ranked[0].get("columns", "") if ranked else ""

        resolution_rows.append(
            {
                "final_figure": panel["final_figure"],
                "panel": panel["panel"],
                "panel_key": panel["panel_key"],
                "panel_title": panel["panel_title"],
                "construction_mode": construction_mode,
                "source_id": source_id,
                "primary_source_description": panel["primary_source"],
                "phase_hint": phase_hint or "",
                "resolution_type": resolution_type,
                "resolved_for_implementation": resolved,
                "top_table_or_metadata_candidate": top_path,
                "top_candidate_score": top_score,
                "top_candidate_columns": top_columns,
                "n_ranked_table_candidates": len(ranked),
                "visual_reference_assets": ";".join(visual_candidates),
                "source_bundle_paths": ";".join(bundle_candidates),
                "requires_manual_candidate_selection": (
                    bool(ranked)
                    and len(ranked) > 1
                    and abs(
                        float(ranked[0]["candidate_score"])
                        - float(ranked[1]["candidate_score"])
                    ) < 3.0
                ),
            }
        )

    return (
        pd.DataFrame(resolution_rows),
        pd.DataFrame(candidate_rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    panel_mapping_path = (
        project
        / "03_metadata"
        / ARCH_TAG
        / "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv"
    )
    release_decision_path = (
        project
        / "06_tables"
        / RELEASE_TAG
        / "UTI_HostOmics_U27B11_phase_decision.tsv"
    )

    if not panel_mapping_path.exists():
        raise FileNotFoundError(
            f"Frozen panel mapping not found: {panel_mapping_path}"
        )
    if not release_decision_path.exists():
        raise FileNotFoundError(
            f"U27B1.1 release decision not found: "
            f"{release_decision_path}"
        )

    release = pd.read_csv(
        release_decision_path,
        sep="\t",
        low_memory=False,
    )
    release_decision = str(release.iloc[0]["decision"])
    if release_decision != (
        "READY_FOR_U27B2_SCRIPTED_MAIN_FIGURE_CONSOLIDATION"
    ):
        raise RuntimeError(
            "U27B1.1 has not released U27B2. Current decision: "
            f"{release_decision}"
        )

    panel_mapping = pd.read_csv(
        panel_mapping_path,
        sep="\t",
        low_memory=False,
    )

    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG

    for directory in [out_tables, out_metadata, out_results]:
        directory.mkdir(parents=True, exist_ok=True)

    log("Inventorying current tables, metadata and scripts.")
    tables, scripts = inventory_sources(project)

    tables.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A_table_schema_inventory.tsv",
        sep="\t",
        index=False,
    )
    scripts.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A_script_inventory.tsv",
        sep="\t",
        index=False,
    )

    log("Parsing scripts for literal source references.")
    references = parse_script_references(project, scripts)
    references.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A_script_source_references.tsv",
        sep="\t",
        index=False,
    )

    log("Resolving candidates for 57 frozen main panels.")
    resolution, candidates = resolve_panels(
        project,
        panel_mapping,
        tables,
    )

    resolution.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B2A_panel_source_resolution.tsv",
        sep="\t",
        index=False,
    )
    candidates.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A_ranked_panel_source_candidates.tsv",
        sep="\t",
        index=False,
    )

    unresolved = resolution[
        ~resolution["resolved_for_implementation"]
    ].copy()
    unresolved.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A_unresolved_panels.tsv",
        sep="\t",
        index=False,
    )

    ambiguous = resolution[
        resolution["requires_manual_candidate_selection"]
    ].copy()
    ambiguous.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A_ambiguous_candidate_panels.tsv",
        sep="\t",
        index=False,
    )

    summary = (
        resolution.groupby(
            ["final_figure", "resolution_type"],
            as_index=False,
        )
        .agg(
            n_panels=("panel_key", "count"),
            n_resolved=(
                "resolved_for_implementation",
                "sum",
            ),
            n_ambiguous=(
                "requires_manual_candidate_selection",
                "sum",
            ),
        )
    )
    summary.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A_resolution_summary.tsv",
        sep="\t",
        index=False,
    )

    n_panels = len(resolution)
    n_resolved = int(
        resolution["resolved_for_implementation"].sum()
    )
    n_unresolved = len(unresolved)
    n_ambiguous = len(ambiguous)
    n_visual = int(
        resolution["visual_reference_assets"]
        .astype(str)
        .str.len()
        .gt(0)
        .sum()
    )
    n_conceptual = int(
        (
            resolution["resolution_type"]
            == "conceptual_source_bundle"
        ).sum()
    )

    if n_panels != 57:
        decision = "FROZEN_PANEL_COUNT_MISMATCH_REQUIRES_REVIEW"
    elif n_unresolved == 0:
        decision = (
            "READY_FOR_U27B2B_BUILD_SPEC_AND_MAIN_FIGURES_1_TO_4"
        )
    else:
        decision = (
            "TARGETED_PANEL_SOURCE_RESOLUTION_REQUIRED_BEFORE_BUILD"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B2A",
                "decision": decision,
                "frozen_main_panels_expected": 57,
                "frozen_main_panels_audited": n_panels,
                "panels_resolved_for_implementation": n_resolved,
                "panels_unresolved": n_unresolved,
                "panels_with_ambiguous_top_candidates": n_ambiguous,
                "conceptual_source_bundle_panels": n_conceptual,
                "panels_with_U27A4_visual_references": n_visual,
                "table_or_metadata_files_inventoried": len(tables),
                "scripts_inventoried": len(scripts),
                "literal_script_source_references_found": len(references),
                "architecture_frozen": True,
                "scientific_values_changed": False,
                "manuscript_modified": False,
                "figures_modified": False,
                "next_phase": (
                    "U27B2B implementation specification and scripted "
                    "construction of Final Figures 1-4"
                    if decision.startswith("READY_FOR_U27B2B")
                    else "Resolve panels listed in unresolved-panels table"
                ),
            }
        ]
    ).to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U27B2A_panel_source_resolution_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2A - Panel source and schema resolution\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Frozen main panels audited: **{n_panels}/57**.\n"
        )
        handle.write(
            f"- Panels resolved for implementation: "
            f"**{n_resolved}/{n_panels}**.\n"
        )
        handle.write(
            f"- Unresolved panels: **{n_unresolved}**.\n"
        )
        handle.write(
            f"- Panels with closely ranked candidate files: "
            f"**{n_ambiguous}**.\n"
        )
        handle.write(
            f"- Conceptual source-bundle panels: "
            f"**{n_conceptual}**.\n"
        )
        handle.write(
            f"- Panels with canonical U27A4 visual references: "
            f"**{n_visual}**.\n"
        )
        handle.write(
            f"- Table/metadata files inventoried: "
            f"**{len(tables)}**.\n"
        )
        handle.write(
            f"- Relevant scripts inventoried: "
            f"**{len(scripts)}**.\n\n"
        )

        handle.write("## Source-of-truth rule\n\n")
        handle.write(
            "Final figure construction must use the resolved current tables "
            "and metadata as the source of numerical values. U27A4 SVG/PDF "
            "files serve as visual-grammar references for Final Figures 5-8, "
            "not as substitutes for updated source tables. Legacy Working "
            "Figures 1 and 6 remain reference-only.\n\n"
        )

        handle.write("## Implementation sequence\n\n")
        handle.write(
            "The recommended next build is Final Figures 1-4 because they "
            "require full table-driven reconstruction. Final Figures 5-8 "
            "should follow in a separate scripted batch using the same "
            "resolved registry and the U27A4 visual-reference assets.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "panels_audited": n_panels,
        "panels_resolved": n_resolved,
        "panels_unresolved": n_unresolved,
        "ambiguous_candidate_panels": n_ambiguous,
        "table_files_inventoried": len(tables),
        "scripts_inventoried": len(scripts),
        "scientific_values_changed": False,
        "manuscript_modified": False,
        "figures_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U27B2A_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Frozen panels audited: {n_panels}/57")
    log(f"Panels resolved: {n_resolved}")
    log(f"Unresolved panels: {n_unresolved}")
    log(f"Ambiguous candidate panels: {n_ambiguous}")
    log(f"Table/metadata files inventoried: {len(tables)}")
    log(f"Scripts inventoried: {len(scripts)}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2A] ERROR: {exc}", file=sys.stderr)
        raise
