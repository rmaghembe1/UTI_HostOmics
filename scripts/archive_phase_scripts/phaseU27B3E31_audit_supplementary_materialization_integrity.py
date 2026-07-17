#!/usr/bin/env python3
"""
Phase U27B3E3.1
Audit the first supplementary-table materialization and construct a targeted
source-map repair plan.

The existing U27B3E3 package is diagnostic only until this audit passes.

Known concerns addressed
------------------------
- U27B3E3 decision/report files are absent, indicating incomplete finalization.
- S1 title requires four datasets but the current source manifest omits
  GSE280297.
- S3 is intended to contain dataset-specific effects across the atlas but the
  current sources omit GSE280297 and GSE186800 effects.
- S6 title requires QC, cluster markers, broad populations and refined
  subtypes, but the current source set is incomplete.
- S8 includes an unsupported JSON run manifest and a phase-decision row rather
  than a clean biological attribution table set.
- S9 still points to the superseded pre-accession-correction U27B3B provenance
  registry instead of the corrected U27B3E22 registry.
- All materialized tables must prohibit GSE168600 and retain GSE186800.

This phase is read-only. It does not alter the current materialized package,
source files, manuscript, figures, legends, source locks or scientific values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


VERSION = "U27B3E31_v1.0_2026-07-16"
TAG = "phaseU27B3E31_supplementary_materialization_integrity_audit"

SOURCE_TAG = "phaseU27B3E3_supplementary_table_materialization"
CORRECT_ACCESSION = "GSE186800"
WRONG_ACCESSION = "GSE168600"

TABLE_IDS = [f"S{i}" for i in range(1, 11)]

EXPECTED_TITLES = {
    "S1": (
        "Dataset architecture, sample design and inclusion roles for "
        "GSE112098, GSE280297, GSE186800 and GSE252321."
    ),
    "S2": "Expanded 78-submodule library organized across ten biological axes.",
    "S3": "Dataset-specific module effects and factorial or adjusted contrasts.",
    "S4": (
        "Cross-dataset recurrence, directional concordance and "
        "evidence-class assignments."
    ),
    "S5": "GSE280297 pregnancy, tissue and outcome-specific module effects.",
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


def log(message: str) -> None:
    print(f"[U27B3E3.1] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def read_table(path: Path) -> pd.DataFrame:
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
    return "\n".join(
        frame.astype(str).fillna("").to_numpy().ravel().tolist()
    )


def source_files(frame: pd.DataFrame) -> List[str]:
    if "_source_file" not in frame.columns:
        return []
    return sorted(
        set(
            frame["_source_file"]
            .fillna("")
            .astype(str)
            .loc[lambda s: s.str.strip() != ""]
            .tolist()
        )
    )


def count_rows_by_source_token(
    frame: pd.DataFrame,
    token: str,
) -> int:
    if "_source_file" not in frame.columns:
        return 0
    return int(
        frame["_source_file"]
        .astype(str)
        .str.contains(token, case=False, na=False)
        .sum()
    )


def has_source_token(
    frame: pd.DataFrame,
    token: str,
) -> bool:
    return count_rows_by_source_token(frame, token) > 0


def unique_nonempty(
    frame: pd.DataFrame,
    column: str,
) -> List[str]:
    if column not in frame.columns:
        return []
    return sorted(
        set(
            value
            for value in frame[column].astype(str).tolist()
            if value.strip()
        )
    )


def candidate_score(path: Path, keywords: Sequence[str]) -> int:
    lower = str(path).lower()
    score = 0
    for keyword in keywords:
        if keyword.lower() in lower:
            score += 12
    if "phaseu26" in lower:
        score += 6
    if "phaseu27" in lower:
        score += 4
    if "validated" in lower:
        score += 4
    if "design" in lower:
        score += 3
    if "effect" in lower:
        score += 3
    if "audit" in lower or "decision" in lower or "manifest.json" in lower:
        score -= 8
    if path.suffix.lower() == ".tsv":
        score += 4
    elif path.suffix.lower() == ".csv":
        score += 2
    return score


def discover_candidates(
    project: Path,
    keywords: Sequence[str],
    max_results: int = 12,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".tsv", ".csv"}:
            continue
        if SOURCE_TAG in str(path):
            continue

        score = candidate_score(path, keywords)
        if score <= 0:
            continue

        rows.append(
            {
                "path": str(path),
                "relative_path": str(path.relative_to(project)),
                "score": score,
                "size_bytes": path.stat().st_size,
                "keywords": "; ".join(keywords),
            }
        )

    rows.sort(
        key=lambda row: (
            int(row["score"]),
            int(row["size_bytes"]),
        ),
        reverse=True,
    )
    return rows[:max_results]


def audit_result(
    table_id: str,
    audit_id: str,
    passed: bool,
    observed: object,
    expected: object,
    severity: str,
    action: str,
) -> Dict[str, object]:
    return {
        "supplementary_table": table_id,
        "audit_id": audit_id,
        "pass": bool(passed),
        "observed": observed,
        "expected": expected,
        "severity": severity,
        "required_action": action,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    source_tables = project / "06_tables" / SOURCE_TAG
    source_results = project / "05_results" / SOURCE_TAG
    source_package = project / "11_supplementary" / SOURCE_TAG
    materialized_dir = source_package / "materialized_tables"

    summary_path = (
        source_tables
        / "UTI_HostOmics_U27B3E3_materialization_summary.tsv"
    )
    manifest_path = (
        source_tables
        / "UTI_HostOmics_U27B3E3_source_manifest.tsv"
    )
    schema_path = (
        source_tables
        / "UTI_HostOmics_U27B3E3_materialized_schema_registry.tsv"
    )
    decision_path = (
        source_tables
        / "UTI_HostOmics_U27B3E3_phase_decision.tsv"
    )
    report_path = (
        source_results
        / "UTI_HostOmics_U27B3E3_supplementary_materialization_report.md"
    )
    zip_path = (
        source_package
        / "UTI_HostOmics_U27B3E3_Supplementary_Tables_S1-S10.zip"
    )

    for path in (summary_path, manifest_path, schema_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Required U27B3E3 diagnostic output not found: {path}"
            )

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG

    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    summary = read_table(summary_path)
    manifest = read_table(manifest_path)

    audit_rows: List[Dict[str, object]] = []
    table_frames: Dict[str, pd.DataFrame] = {}

    for table_id in TABLE_IDS:
        path = (
            materialized_dir
            / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
        )
        exists = path.exists() and path.stat().st_size > 0
        frame = read_table(path) if exists else pd.DataFrame()
        table_frames[table_id] = frame

        audit_rows.append(
            audit_result(
                table_id,
                "materialized_file_exists",
                exists,
                str(path),
                "existing nonempty TSV",
                "BLOCKING",
                "Re-materialize the table if absent.",
            )
        )

        provenance_columns = {
            "_supplementary_table",
            "_table_title",
            "_source_order",
            "_source_file",
            "_source_relative_path",
            "_source_sha256",
            "_source_row_number",
        }
        provenance_pass = provenance_columns.issubset(set(frame.columns))
        audit_rows.append(
            audit_result(
                table_id,
                "row_level_provenance_columns",
                provenance_pass,
                "; ".join(frame.columns[:10]),
                "; ".join(sorted(provenance_columns)),
                "BLOCKING",
                "Preserve the seven required provenance columns.",
            )
        )

        text = all_text(frame)
        wrong_count = len(
            re.findall(
                re.escape(WRONG_ACCESSION),
                text,
                flags=re.IGNORECASE,
            )
        )
        audit_rows.append(
            audit_result(
                table_id,
                "wrong_accession_absent",
                wrong_count == 0,
                wrong_count,
                0,
                "BLOCKING",
                "Replace superseded provenance sources with U27B3E22 corrected derivatives.",
            )
        )

    # S1: four datasets and expected design-source row contributions.
    s1 = table_frames["S1"]
    required_s1 = {
        "GSE112098",
        "GSE280297",
        "GSE186800",
        "GSE252321",
    }
    s1_sources = "\n".join(source_files(s1))
    observed_s1 = {
        accession
        for accession in required_s1
        if accession.lower() in s1_sources.lower()
        or accession.lower() in all_text(s1).lower()
    }
    audit_rows.append(
        audit_result(
            "S1",
            "all_four_dataset_designs_present",
            observed_s1 == required_s1,
            "; ".join(sorted(observed_s1)),
            "; ".join(sorted(required_s1)),
            "BLOCKING",
            "Add the validated 60-sample GSE280297 design table.",
        )
    )

    # S2: exact 78 submodules and 10 axes.
    s2 = table_frames["S2"]
    s2_modules = unique_nonempty(s2, "submodule_id")
    s2_axes = unique_nonempty(s2, "axis")
    audit_rows.append(
        audit_result(
            "S2",
            "submodule_count",
            len(s2_modules) == 78,
            len(s2_modules),
            78,
            "BLOCKING",
            "Use the frozen U26A expanded submodule library without row loss.",
        )
    )
    audit_rows.append(
        audit_result(
            "S2",
            "axis_count",
            len(s2_axes) == 10,
            len(s2_axes),
            10,
            "BLOCKING",
            "Retain all ten biological axes.",
        )
    )

    # S3: all four dataset families should be represented.
    s3 = table_frames["S3"]
    s3_text = all_text(s3)
    observed_s3 = {
        accession
        for accession in required_s1
        if accession.lower() in s3_text.lower()
    }
    audit_rows.append(
        audit_result(
            "S3",
            "all_dataset_effect_families_present",
            observed_s3 == required_s1,
            "; ".join(sorted(observed_s3)),
            "; ".join(sorted(required_s1)),
            "BLOCKING",
            (
                "Add GSE280297 and GSE186800 effect/contrast sources and retain "
                "the GSE112098 and GSE252321 sources."
            ),
        )
    )

    # S4 recurrence fields.
    s4 = table_frames["S4"]
    s4_required_columns = {
        "feature_id",
        "validation_class",
        "n_independent_datasets",
        "weighted_directional_coherence",
        "median_effect",
        "dataset_effects",
    }
    audit_rows.append(
        audit_result(
            "S4",
            "recurrence_schema",
            s4_required_columns.issubset(set(s4.columns)),
            "; ".join(sorted(set(s4.columns) & s4_required_columns)),
            "; ".join(sorted(s4_required_columns)),
            "BLOCKING",
            "Retain the independent-dataset recurrence ranking as the core S4 source.",
        )
    )

    # S5 GSE280297 effect architecture.
    s5 = table_frames["S5"]
    s5_required = {
        "C1_PRETERM_VS_TERM | bladder",
        "C2_UPEC_VS_PBS_PREGNANCY | bladder",
        "C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder",
    }
    audit_rows.append(
        audit_result(
            "S5",
            "three_pregnancy_contrast_families",
            s5_required.issubset(set(s5.columns)),
            "; ".join(sorted(set(s5.columns) & s5_required)),
            "; ".join(sorted(s5_required)),
            "BLOCKING",
            "Retain the full GSE280297 tissue-effect matrix and collapsed summaries.",
        )
    )

    # S6 requires explicit QC/composition sources.
    s6 = table_frames["S6"]
    s6_source_text = "\n".join(source_files(s6)).lower()
    qc_present = any(token in s6_source_text for token in ("qc", "quality"))
    composition_present = "composition" in s6_source_text
    marker_present = "marker" in s6_source_text
    subtype_present = any(
        token in s6_source_text
        for token in ("subtype", "refined")
    )
    audit_rows.append(
        audit_result(
            "S6",
            "qc_marker_composition_subtype_source_coverage",
            qc_present and composition_present and marker_present and subtype_present,
            (
                f"qc={qc_present}; composition={composition_present}; "
                f"marker={marker_present}; subtype={subtype_present}"
            ),
            "all four source families present",
            "BLOCKING",
            (
                "Add explicit GSE252321 QC and broad-cell composition tables; "
                "retain marker and refined-subtype sources."
            ),
        )
    )

    # S7 broad and subtype localization.
    s7 = table_frames["S7"]
    s7_source_text = "\n".join(source_files(s7)).lower()
    audit_rows.append(
        audit_result(
            "S7",
            "broad_and_subtype_localization_sources",
            "broad" in s7_source_text and "subtype" in s7_source_text,
            s7_source_text,
            "broad and subtype localization sources",
            "BLOCKING",
            "Retain both broad-cell and refined-subtype localization tables.",
        )
    )

    # S8: no unsupported/administrative sources.
    s8_manifest = manifest[
        manifest["supplementary_table"] == "S8"
    ].copy()
    unsupported_count = int(
        (
            s8_manifest["source_read_status"]
            .astype(str)
            .str.upper()
            != "READY"
        ).sum()
    )
    administrative_sources = [
        value
        for value in s8_manifest["source_path"].astype(str).tolist()
        if any(
            token in value.lower()
            for token in (
                "run_manifest.json",
                "phase_decision.tsv",
            )
        )
    ]
    s8_source_text = "\n".join(source_files(table_frames["S8"])).lower()
    attribution_present = "cellular_attribution" in s8_source_text
    audit_rows.append(
        audit_result(
            "S8",
            "biological_tabular_sources_only",
            (
                unsupported_count == 0
                and not administrative_sources
                and attribution_present
            ),
            (
                f"unsupported={unsupported_count}; "
                f"administrative={len(administrative_sources)}; "
                f"attribution={attribution_present}"
            ),
            "zero unsupported/administrative sources and cellular-attribution source present",
            "BLOCKING",
            (
                "Remove the JSON run manifest and phase-decision table; replace "
                "them with complement-stage and endocrine-metabolic attribution TSVs."
            ),
        )
    )

    # S9 corrected provenance registry and accession cleanliness.
    s9 = table_frames["S9"]
    s9_source_text = "\n".join(source_files(s9))
    corrected_registry_used = (
        "phaseU27B3E22_targeted_accession_correction"
        in s9_source_text
    )
    s9_wrong_count = len(
        re.findall(
            re.escape(WRONG_ACCESSION),
            all_text(s9),
            flags=re.IGNORECASE,
        )
    )
    figure_numbers = unique_nonempty(s9, "figure_number")
    audit_rows.append(
        audit_result(
            "S9",
            "corrected_provenance_registry_used",
            corrected_registry_used and s9_wrong_count == 0,
            (
                f"corrected_registry={corrected_registry_used}; "
                f"wrong_accession_occurrences={s9_wrong_count}"
            ),
            "U27B3E22 corrected registry and zero GSE168600 occurrences",
            "BLOCKING",
            "Replace the U27B3B panel registry with the U27B3E22 corrected registry.",
        )
    )
    audit_rows.append(
        audit_result(
            "S9",
            "figures_1_to_8_represented",
            set(figure_numbers) >= set(str(i) for i in range(1, 9)),
            "; ".join(figure_numbers),
            "1; 2; 3; 4; 5; 6; 7; 8",
            "BLOCKING",
            "Retain all eight figure records.",
        )
    )

    # S10 caveat and traceability sources.
    s10 = table_frames["S10"]
    s10_required = {"caveat_id", "audit_type", "rationale"}
    audit_rows.append(
        audit_result(
            "S10",
            "interpretation_and_traceability_schema",
            s10_required.issubset(set(s10.columns)),
            "; ".join(sorted(set(s10.columns) & s10_required)),
            "; ".join(sorted(s10_required)),
            "BLOCKING",
            "Retain caveat, scientific-audit and false-negative rationale sources.",
        )
    )

    audit_frame = pd.DataFrame(audit_rows)
    audit_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E31_table_integrity_audit.tsv",
        sep="\t",
        index=False,
    )

    # Control-file finalization audit.
    control_frame = pd.DataFrame(
        [
            {
                "control_artifact": "U27B3E3 phase decision",
                "path": str(decision_path),
                "exists": decision_path.exists(),
            },
            {
                "control_artifact": "U27B3E3 report",
                "path": str(report_path),
                "exists": report_path.exists(),
            },
            {
                "control_artifact": "U27B3E3 package ZIP",
                "path": str(zip_path),
                "exists": zip_path.exists(),
            },
        ]
    )
    control_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E31_control_artifact_audit.tsv",
        sep="\t",
        index=False,
    )

    # Discovery requests for targeted repair.
    discovery_specs = {
        "S1_ADD_GSE280297_DESIGN": [
            "GSE280297",
            "design",
            "60sample",
            "validated",
        ],
        "S3_ADD_GSE280297_EFFECTS": [
            "GSE280297",
            "effect",
            "contrast",
        ],
        "S3_ADD_GSE186800_EFFECTS": [
            "GSE186800",
            "effect",
            "contrast",
        ],
        "S6_ADD_GSE252321_QC": [
            "GSE252321",
            "qc",
        ],
        "S6_ADD_GSE252321_COMPOSITION": [
            "GSE252321",
            "composition",
        ],
        "S8_COMPLEMENT_ATTRIBUTION": [
            "complement",
            "cellular",
            "attribution",
        ],
        "S8_ENDOCRINE_METABOLIC_ATTRIBUTION": [
            "endocrine",
            "metabolic",
            "cellular",
            "attribution",
        ],
        "S9_CORRECTED_PANEL_REGISTRY": [
            "U27B3E22",
            "panel",
            "legend",
            "provenance",
            "registry",
        ],
    }

    candidate_rows: List[Dict[str, object]] = []
    for repair_id, keywords in discovery_specs.items():
        for rank, row in enumerate(
            discover_candidates(project, keywords),
            start=1,
        ):
            candidate_rows.append(
                {
                    "repair_id": repair_id,
                    "rank": rank,
                    **row,
                }
            )

    candidate_frame = pd.DataFrame(candidate_rows)
    candidate_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B3E31_repair_candidate_registry.tsv",
        sep="\t",
        index=False,
    )

    # Deterministic action plan.
    action_rows = [
        {
            "supplementary_table": "S1",
            "action": "ADD",
            "target_role": "GSE280297 validated 60-sample design",
            "reason": "Current S1 has only 97 rows from GSE252321, GSE112098 and GSE186800.",
        },
        {
            "supplementary_table": "S3",
            "action": "ADD",
            "target_role": "GSE280297 dataset-specific effects",
            "reason": "Current S3 omits the pregnancy-model effect family.",
        },
        {
            "supplementary_table": "S3",
            "action": "ADD",
            "target_role": "GSE186800 recurrent-UTI effects",
            "reason": "Current S3 omits the recurrent-UTI effect family.",
        },
        {
            "supplementary_table": "S6",
            "action": "ADD",
            "target_role": "GSE252321 sample/cell QC summary",
            "reason": "The title promises QC but no QC source is locked.",
        },
        {
            "supplementary_table": "S6",
            "action": "ADD",
            "target_role": "GSE252321 broad-cell composition",
            "reason": "The title promises broad populations but no composition source is locked.",
        },
        {
            "supplementary_table": "S8",
            "action": "REMOVE",
            "target_role": "U26B1 run_manifest.json",
            "reason": "Unsupported non-tabular administrative artifact.",
        },
        {
            "supplementary_table": "S8",
            "action": "REMOVE",
            "target_role": "U26B1 phase_decision.tsv",
            "reason": "Administrative control row is not a biological attribution table.",
        },
        {
            "supplementary_table": "S8",
            "action": "ADD",
            "target_role": "Complement-stage cellular attribution TSV",
            "reason": "Required by the table title and manuscript claims.",
        },
        {
            "supplementary_table": "S8",
            "action": "ADD",
            "target_role": "Endocrine-metabolic cellular attribution TSV",
            "reason": "Required by the table title and manuscript claims.",
        },
        {
            "supplementary_table": "S9",
            "action": "REPLACE",
            "target_role": "U27B3B panel provenance registry",
            "reason": "Use the accession-corrected U27B3E22 panel provenance registry.",
        },
    ]
    pd.DataFrame(action_rows).to_csv(
        outmetadata
        / "UTI_HostOmics_U27B3E31_targeted_source_map_repair_plan.tsv",
        sep="\t",
        index=False,
    )

    failed_audits = audit_frame[~audit_frame["pass"]].copy()
    blocking_failures = len(
        failed_audits[
            failed_audits["severity"] == "BLOCKING"
        ]
    )
    control_complete = bool(control_frame["exists"].all())

    if blocking_failures > 0:
        decision = (
            "READY_FOR_U27B3E32_TARGETED_SUPPLEMENTARY_SOURCE_MAP_REPAIR_"
            "AND_REMATERIALIZATION"
        )
    elif not control_complete:
        decision = (
            "U27B3E3_CONTENT_PASS_CONTROL_ARTIFACT_FINALIZATION_REQUIRED"
        )
    else:
        decision = (
            "READY_FOR_U27B3E4_SUPPLEMENTARY_TABLE_SCHEMA_AND_CONTENT_AUDIT"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B3E3.1",
                "decision": decision,
                "supplementary_tables_observed": len(table_frames),
                "table_level_audits": len(audit_frame),
                "table_level_audits_passed": int(audit_frame["pass"].sum()),
                "blocking_failures": blocking_failures,
                "current_phase_decision_exists": decision_path.exists(),
                "current_phase_report_exists": report_path.exists(),
                "current_package_zip_exists": zip_path.exists(),
                "current_package_submission_approved": False,
                "scientific_values_recalculated": False,
                "source_files_modified": False,
                "current_materialized_tables_modified": False,
                "next_phase": (
                    "U27B3E3.2 repair the source map, rebuild S1/S3/S6/S8/S9, "
                    "rematerialize all ten tables and regenerate decision/report/ZIP"
                    if decision.startswith("READY_FOR_U27B3E32")
                    else "Complete control artifacts or proceed to U27B3E4"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B3E31_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report = (
        outresults
        / "UTI_HostOmics_U27B3E31_supplementary_integrity_audit_report.md"
    )
    with report.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3E3.1 - Supplementary materialization integrity audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Table-level audits passed: "
            f"**{int(audit_frame['pass'].sum())}/{len(audit_frame)}**.\n"
        )
        handle.write(
            f"- Blocking failures: **{blocking_failures}**.\n"
        )
        handle.write(
            f"- Original U27B3E3 decision exists: **{decision_path.exists()}**.\n"
        )
        handle.write(
            f"- Original U27B3E3 report exists: **{report_path.exists()}**.\n"
        )
        handle.write(
            f"- Diagnostic package ZIP exists: **{zip_path.exists()}**.\n\n"
        )

        handle.write("## Scientific disposition\n\n")
        handle.write(
            "The first ZIP is diagnostic only and must not be submitted. "
            "Materialization succeeded mechanically, but S1, S3, S6, S8 and "
            "S9 require source-map repair before the package can represent the "
            "frozen manuscript architecture faithfully.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "This phase is read-only. No source table, materialized TSV, "
            "manuscript, figure, legend, source lock or scientific value was "
            "modified.\n"
        )

    manifest_out = {
        "version": VERSION,
        "decision": decision,
        "table_audits": len(audit_frame),
        "table_audits_passed": int(audit_frame["pass"].sum()),
        "blocking_failures": blocking_failures,
        "control_complete": control_complete,
        "diagnostic_zip": str(zip_path),
        "diagnostic_zip_sha256": sha256(zip_path) if zip_path.exists() else "",
        "current_package_submission_approved": False,
        "scientific_values_recalculated": False,
        "source_files_modified": False,
        "current_materialized_tables_modified": False,
    }
    (
        outresults
        / "UTI_HostOmics_U27B3E31_run_manifest.json"
    ).write_text(
        json.dumps(manifest_out, indent=2),
        encoding="utf-8",
    )

    log(
        "Table audits passed: "
        f"{int(audit_frame['pass'].sum())}/{len(audit_frame)}"
    )
    log(f"Blocking failures: {blocking_failures}")
    log(f"Original decision exists: {decision_path.exists()}")
    log(f"Original report exists: {report_path.exists()}")
    log(f"Decision: {decision}")
    log(f"Report: {report}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E3.1] ERROR: {exc}", file=sys.stderr)
        raise
