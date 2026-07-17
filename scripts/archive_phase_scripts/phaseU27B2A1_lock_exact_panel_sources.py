#!/usr/bin/env python3
"""
Phase U27B2A.1
Deterministically adjudicate and lock exact source files for all 57 main panels.

U27B2A resolved all panels but left 37 closely ranked candidate sets. This
phase prevents incorrect source selection by applying explicit filename,
phase, schema and exclusion rules.

Outputs
-------
- one locked primary source per panel;
- additional supporting sources where a panel requires more than one table;
- explicit visual-reference assets for U27A4-derived panels;
- prohibited-source audit;
- unresolved/ambiguous source-lock tables;
- final build-readiness decision.

No figures, source data or manuscript text are modified.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


VERSION = "U27B2A1_v1.0_2026-07-15"
TAG = "phaseU27B2A1_exact_panel_source_lock"
SOURCE_TAG = "phaseU27B2A_panel_source_and_schema_resolution"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"


@dataclass(frozen=True)
class SourceRule:
    role: str
    phase_tokens: Tuple[str, ...] = ()
    filename_all: Tuple[str, ...] = ()
    filename_any: Tuple[str, ...] = ()
    filename_exclude: Tuple[str, ...] = ()
    required_columns: Tuple[str, ...] = ()
    preferred_columns: Tuple[str, ...] = ()
    allow_directory: bool = False


def log(message: str) -> None:
    print(f"[U27B2A.1] {message}", flush=True)


def lower(value: object) -> str:
    return str(value).lower()


def parse_columns(value: object) -> set[str]:
    return {
        item.strip()
        for item in str(value).split(";")
        if item.strip()
    }


def rule_score(row: pd.Series, rule: SourceRule) -> Optional[float]:
    filename = lower(row.get("filename", ""))
    path = lower(row.get("path", ""))
    columns = parse_columns(row.get("columns", ""))

    if rule.phase_tokens and not all(
        token.lower() in path for token in rule.phase_tokens
    ):
        return None

    if rule.filename_all and not all(
        token.lower() in filename for token in rule.filename_all
    ):
        return None

    if rule.filename_any and not any(
        token.lower() in filename for token in rule.filename_any
    ):
        return None

    if any(token.lower() in filename for token in rule.filename_exclude):
        return None

    if rule.required_columns and not set(rule.required_columns).issubset(columns):
        return None

    score = 0.0
    score += 50.0 * len(rule.phase_tokens)
    score += 35.0 * len(rule.filename_all)
    score += 15.0 * sum(
        token.lower() in filename for token in rule.filename_any
    )
    score += 12.0 * len(rule.required_columns)
    score += 4.0 * sum(
        column in columns for column in rule.preferred_columns
    )

    # Prefer smaller final result tables over huge raw matrices where schemas tie.
    size_bytes = float(row.get("size_bytes", 0) or 0)
    if size_bytes > 0:
        score -= min(size_bytes / 1e9, 2.0)

    return score


COMMON_RULES: Dict[str, SourceRule] = {
    "module_library": SourceRule(
        role="module_library",
        phase_tokens=("phaseu26a_expanded_endocrine_metabolic_immune_feasibility",),
        filename_all=("expanded_submodule_library",),
        required_columns=("axis", "submodule_id", "display_label", "n_genes", "genes"),
    ),
    "bulk_readiness": SourceRule(
        role="bulk_readiness",
        phase_tokens=("phaseu26b2a1_cross_dataset_input_repair",),
        filename_all=("bulk_dataset_readiness",),
        required_columns=("dataset", "species", "observed_samples", "canonical_genes"),
    ),
    "gse280297_design": SourceRule(
        role="gse280297_design",
        filename_any=(
            "u26a5_validated_60sample_design",
            "validated_60sample_design",
            "final_validated_sample_design",
        ),
        filename_exclude=("u26a4_",),
        required_columns=("sample_id", "tissue", "treatment", "outcome", "pregnancy_status"),
    ),
    "refined_core": SourceRule(
        role="refined_core",
        phase_tokens=("phaseu26c1_interpretation_threshold_and_branch_refinement",),
        filename_all=("refined_core_and_secondary_modules",),
        required_columns=(
            "feature_id",
            "axis",
            "display_label",
            "validation_class",
            "manuscript_claim_priority",
        ),
    ),
    "decoupling_domains": SourceRule(
        role="decoupling_domains",
        phase_tokens=("phaseu26c1_interpretation_threshold_and_branch_refinement",),
        filename_all=("refined_decoupling_domains",),
        required_columns=("domain", "median_effect", "dominant_direction", "refined_interpretation"),
    ),
    "primary_independent_effects": SourceRule(
        role="primary_independent_effects",
        phase_tokens=("phaseu26b2b1_independent_dataset_evidence_collapse",),
        filename_all=("primary_independent_dataset_effects",),
        filename_exclude=("noninfection", "block", "interaction", "fdr10"),
        required_columns=("dataset", "contrast_id", "feature_id", "effect_value", "effect_metric"),
    ),
    "recurrence_ranking": SourceRule(
        role="recurrence_ranking",
        phase_tokens=("phaseu26b2b1_independent_dataset_evidence_collapse",),
        filename_all=("independent_dataset_recurrence_ranking",),
        required_columns=(
            "feature_id",
            "validation_class",
            "independent_evidence_priority_score",
            "dominant_direction",
        ),
    ),
    "preterm_collapsed": SourceRule(
        role="preterm_collapsed",
        phase_tokens=("phaseu26b2b1_independent_dataset_evidence_collapse",),
        filename_all=("gse280297", "preterm", "term", "collapsed"),
        required_columns=("feature_id",),
        preferred_columns=("effect_value", "preterm_vs_term_effect", "median_effect"),
    ),
    "gse112098_adjusted": SourceRule(
        role="gse112098_adjusted",
        phase_tokens=("phaseu26b2b_cross_dataset_scoring_integration",),
        filename_all=("gse112098", "adjusted"),
        filename_exclude=("unadjusted",),
        required_columns=("dataset", "contrast_id", "feature_id", "model_estimate"),
    ),
    "gse186800_factorial": SourceRule(
        role="gse186800_factorial",
        phase_tokens=("phaseu26b2b_cross_dataset_scoring_integration",),
        filename_all=("gse186800", "factorial_results"),
        required_columns=("dataset", "contrast_id", "feature_id", "model_estimate", "model_q_within_contrast"),
    ),
    "gse280297_primary_matrix": SourceRule(
        role="gse280297_primary_matrix",
        phase_tokens=("phaseu26b1_1_gse280297_stability_refinement",),
        filename_all=("primary_effect_matrix",),
        required_columns=("feature_id",),
    ),
    "cross_tissue_coherence": SourceRule(
        role="cross_tissue_coherence",
        phase_tokens=("phaseu26b1_1_gse280297_stability_refinement",),
        filename_all=("cross_tissue_directional_coherence",),
        required_columns=(
            "contrast_id",
            "feature_id",
            "directional_coherence_fraction",
            "median_hedges_g",
        ),
    ),
    "balanced_annotations": SourceRule(
        role="balanced_annotations",
        phase_tokens=("phaseu26d2a_gse252321_marker_celltype_reconstruction",),
        filename_all=("balanced_cell_annotations",),
        required_columns=(
            "cell_id",
            "sample_id",
            "condition",
            "cluster",
            "broad_cell_type",
            "corrected_component_1",
            "corrected_component_2",
        ),
    ),
    "cluster_markers": SourceRule(
        role="cluster_markers",
        phase_tokens=("phaseu26d2a_gse252321_marker_celltype_reconstruction",),
        filename_any=("top_markers", "cluster_markers", "marker_summary"),
        filename_exclude=("decision", "manifest"),
        required_columns=("cluster",),
        preferred_columns=("gene", "gene_symbol", "log2fc", "marker_score"),
    ),
    "refinement_map": SourceRule(
        role="refinement_map",
        phase_tokens=("phaseu26d2a1_gse252321_annotation_refinement",),
        filename_any=("cluster_refinement", "annotation_refinement", "refined_cluster"),
        filename_exclude=("decision", "report"),
        required_columns=("cluster",),
        preferred_columns=("refined_broad_cell_type", "refined_subtype", "refined_label"),
    ),
    "broad_composition": SourceRule(
        role="broad_composition",
        phase_tokens=("phaseu26d2a1_gse252321_annotation_refinement",),
        filename_any=("broad_composition", "refined_broad", "composition"),
        filename_exclude=("subtype", "targeted", "decision"),
        preferred_columns=("sample_id", "condition", "refined_broad_cell_type", "fraction"),
    ),
    "subtype_composition": SourceRule(
        role="subtype_composition",
        phase_tokens=("phaseu26d2a1_gse252321_annotation_refinement",),
        filename_any=("subtype_composition", "refined_subtype"),
        filename_exclude=("decision",),
        preferred_columns=("sample_id", "condition", "refined_subtype", "fraction"),
    ),
    "targeted_states": SourceRule(
        role="targeted_states",
        phase_tokens=("phaseu26d2a1_gse252321_annotation_refinement",),
        filename_any=("targeted", "treg", "tnfsf9"),
        filename_exclude=("decision", "report"),
        preferred_columns=("sample_id", "condition", "targeted_measure", "fraction"),
    ),
    "core_cellular_attribution": SourceRule(
        role="core_cellular_attribution",
        phase_tokens=("phaseu26d2c_cellular_localization_synthesis",),
        filename_all=("core_module_cellular_attribution",),
        required_columns=("feature_id",),
    ),
    "broad_effect_reliability": SourceRule(
        role="broad_effect_reliability",
        phase_tokens=("phaseu26d2c_cellular_localization_synthesis",),
        filename_all=("broad_effect_reliability",),
        required_columns=("feature_id",),
        preferred_columns=("population", "module_mean_gene_log2FC", "cellular_localization_score"),
    ),
    "module_cellular_synthesis": SourceRule(
        role="module_cellular_synthesis",
        phase_tokens=("phaseu26d2c_cellular_localization_synthesis",),
        filename_all=("module_cellular_synthesis",),
        required_columns=("feature_id",),
        preferred_columns=("top_refined_subtype", "top_refined_subtype_composite_score"),
    ),
    "claim_boundaries": SourceRule(
        role="claim_boundaries",
        phase_tokens=("phaseu26d2c_cellular_localization_synthesis",),
        filename_all=("claim_boundary_matrix",),
        required_columns=("feature_id",),
    ),
}


def rules_for_panel(row: pd.Series) -> List[SourceRule]:
    figure = str(row["final_figure"])
    panel = str(row["panel"])
    source_id = str(row["source_id"])

    # Figure 1
    if source_id == "01_study_design_and_question_map":
        return [
            COMMON_RULES["module_library"],
            COMMON_RULES["bulk_readiness"],
            COMMON_RULES["gse280297_design"],
            COMMON_RULES["refined_core"],
        ]
    if source_id == "dataset_manifest":
        return [COMMON_RULES["bulk_readiness"]]
    if source_id == "contrast_manifest":
        return [
            COMMON_RULES["gse280297_design"],
            COMMON_RULES["gse186800_factorial"],
            COMMON_RULES["gse112098_adjusted"],
        ]
    if source_id == "U26A_module_dictionary":
        return [COMMON_RULES["module_library"]]
    if source_id == "phase_workflow_manifest":
        return []
    if source_id == "U26C1_evidence_tiers":
        return [COMMON_RULES["refined_core"]]

    # Figure 2
    if source_id == "U26B2B1_primary_effects":
        return [COMMON_RULES["primary_independent_effects"]]
    if source_id == "U26B2B1_classification":
        return [COMMON_RULES["recurrence_ranking"]]
    if source_id in {"U26C1_core_network", "U26C1_complement_core"}:
        return [COMMON_RULES["refined_core"]]
    if source_id == "U26B2B_GSE112098":
        return [COMMON_RULES["gse112098_adjusted"]]
    if source_id == "U26B2B_GSE186800":
        return [COMMON_RULES["gse186800_factorial"]]
    if source_id == "U26B2B1_U26C_network":
        return [COMMON_RULES["recurrence_ranking"], COMMON_RULES["refined_core"]]

    # Figure 3
    if source_id == "GSE280297_design":
        return [COMMON_RULES["gse280297_design"]]
    if source_id in {"U26B1_1_C1", "U26B1_1_C2", "U26B1_1_C3"}:
        return [COMMON_RULES["gse280297_primary_matrix"]]
    if source_id == "U26B1_1_C1_concordance":
        return [COMMON_RULES["cross_tissue_coherence"]]
    if source_id == "U26C1_steroid_branching":
        return [COMMON_RULES["decoupling_domains"]]
    if source_id == "U26B1_1_tissue_modules":
        return [
            COMMON_RULES["gse280297_primary_matrix"],
            COMMON_RULES["cross_tissue_coherence"],
        ]
    if source_id == "U26C1_pregnancy_model":
        return [
            COMMON_RULES["refined_core"],
            COMMON_RULES["decoupling_domains"],
            COMMON_RULES["cross_tissue_coherence"],
        ]

    # Figure 4
    if source_id == "U26D2A_embedding":
        return [COMMON_RULES["balanced_annotations"]]
    if source_id == "U26D2A_D2A1_markers":
        return [COMMON_RULES["cluster_markers"], COMMON_RULES["refinement_map"]]
    if source_id == "U26D2A1_composition":
        return [COMMON_RULES["broad_composition"]]
    if source_id == "U26D2A1_subtypes":
        return [COMMON_RULES["subtype_composition"]]
    if source_id in {"U26D2A1_TNFSF9", "U26D2A1_Treg"}:
        return [COMMON_RULES["targeted_states"]]
    if source_id == "U26D2C_core_localization":
        return [
            COMMON_RULES["core_cellular_attribution"],
            COMMON_RULES["broad_effect_reliability"],
        ]
    if source_id == "U26D_cellular_model":
        return [
            COMMON_RULES["targeted_states"],
            COMMON_RULES["core_cellular_attribution"],
            COMMON_RULES["module_cellular_synthesis"],
        ]

    # U27A4-derived panels
    if source_id.startswith("U27A4_Figure_"):
        if source_id.endswith("A"):
            return [COMMON_RULES["primary_independent_effects"]]
        if source_id.endswith("B"):
            return [COMMON_RULES["preterm_collapsed"]]
        if source_id.endswith("C"):
            return [COMMON_RULES["broad_effect_reliability"]]
        if source_id.endswith("D"):
            return [COMMON_RULES["module_cellular_synthesis"]]
        if "Figure_11A" in source_id:
            return [
                COMMON_RULES["primary_independent_effects"],
                COMMON_RULES["preterm_collapsed"],
            ]
        if "Figure_11B" in source_id:
            return [COMMON_RULES["broad_effect_reliability"]]
        if "Figure_11C" in source_id:
            return [
                COMMON_RULES["broad_composition"],
                COMMON_RULES["targeted_states"],
            ]
        if "Figure_11D" in source_id:
            return [
                COMMON_RULES["refined_core"],
                COMMON_RULES["module_cellular_synthesis"],
            ]

    # Remaining synthesis panels
    if source_id in {
        "U26C1_steroid_quadrant",
        "U26C1_U26D2C_metabolic_network",
        "U26C1_U26D2C_complement_topology",
        "U26C1_U26D2C_evidence_boundary",
    }:
        return [
            COMMON_RULES["refined_core"],
            COMMON_RULES["module_cellular_synthesis"],
        ]
    if source_id in {
        "U26D2C_cholesterol",
        "U26D2C_lipid_stress",
        "U26D2C_carbon",
        "U26D2C_complement_comparison",
    }:
        return [
            COMMON_RULES["broad_effect_reliability"],
            COMMON_RULES["module_cellular_synthesis"],
        ]
    if source_id == "U26D2B_complement_coverage":
        return [SourceRule(
            role="module_coverage",
            phase_tokens=("phaseu26d2b_gse252321_refined_celltype_pseudobulk",),
            filename_any=("coverage", "module_manifest", "module_eligibility"),
            filename_exclude=("decision", "report"),
            preferred_columns=("feature_id", "population", "n_genes"),
        )]

    return []


def visual_assets(project: Path, source_id: str) -> List[str]:
    match = re.search(r"U27A4_Figure_(\d+)", source_id)
    if not match:
        return []

    number = match.group(1)
    directory = project / "06_figures" / "phaseU27A4_final_visual_audit"
    assets = []
    for extension in ("svg", "pdf", "png"):
        path = directory / f"UTI_HostOmics_U27A4_Figure_{number}.{extension}"
        if path.exists():
            assets.append(str(path))
    return assets


def select_candidate(inventory: pd.DataFrame, rule: SourceRule) -> Tuple[Optional[pd.Series], float, float]:
    scored = []
    for index, row in inventory.iterrows():
        score = rule_score(row, rule)
        if score is not None:
            scored.append((index, score))

    if not scored:
        return None, float("-inf"), float("-inf")

    scored.sort(key=lambda item: item[1], reverse=True)
    top_index, top_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else float("-inf")
    return inventory.loc[top_index], top_score, second_score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    inventory_path = (
        project / "06_tables" / SOURCE_TAG
        / "UTI_HostOmics_U27B2A_table_schema_inventory.tsv"
    )
    panel_path = (
        project / "03_metadata" / ARCH_TAG
        / "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv"
    )

    if not inventory_path.exists():
        raise FileNotFoundError(f"Missing inventory: {inventory_path}")
    if not panel_path.exists():
        raise FileNotFoundError(f"Missing panel map: {panel_path}")

    inventory = pd.read_csv(inventory_path, sep="\t", low_memory=False)
    panels = pd.read_csv(panel_path, sep="\t", low_memory=False)

    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG

    for directory in (out_tables, out_metadata, out_results):
        directory.mkdir(parents=True, exist_ok=True)

    lock_rows = []
    exception_rows = []
    panel_summary_rows = []

    log("Applying deterministic source-lock rules to 57 panels.")

    for _, panel in panels.iterrows():
        panel_key = str(panel["panel_key"])
        source_id = str(panel["source_id"])
        rules = rules_for_panel(panel)
        assets = visual_assets(project, source_id)

        if source_id == "phase_workflow_manifest":
            phase_decisions = sorted(
                str(path)
                for path in (project / "06_tables").rglob("*phase_decision.tsv")
            )
            for path in phase_decisions:
                lock_rows.append({
                    "panel_key": panel_key,
                    "final_figure": panel["final_figure"],
                    "panel": panel["panel"],
                    "source_id": source_id,
                    "source_role": "phase_decision_bundle",
                    "locked_path": path,
                    "selection_score": "",
                    "second_best_score": "",
                    "score_margin": "",
                    "schema_columns": "",
                    "visual_reference_assets": ";".join(assets),
                    "lock_status": "LOCKED_BUNDLE",
                })
            panel_summary_rows.append({
                "panel_key": panel_key,
                "n_required_roles": 1,
                "n_roles_locked": 1 if phase_decisions else 0,
                "visual_assets_complete": True,
                "panel_lock_complete": bool(phase_decisions),
            })
            continue

        roles_locked = 0
        for rule in rules:
            candidate, top_score, second_score = select_candidate(inventory, rule)
            if candidate is None:
                exception_rows.append({
                    "panel_key": panel_key,
                    "source_id": source_id,
                    "source_role": rule.role,
                    "issue": "NO_CANDIDATE_MATCHED_EXACT_RULE",
                })
                continue

            margin = (
                top_score - second_score
                if second_score != float("-inf")
                else float("inf")
            )
            roles_locked += 1

            lock_rows.append({
                "panel_key": panel_key,
                "final_figure": panel["final_figure"],
                "panel": panel["panel"],
                "source_id": source_id,
                "source_role": rule.role,
                "locked_path": candidate["path"],
                "selection_score": top_score,
                "second_best_score": (
                    second_score if second_score != float("-inf") else ""
                ),
                "score_margin": margin if margin != float("inf") else "",
                "schema_columns": candidate.get("columns", ""),
                "visual_reference_assets": ";".join(assets),
                "lock_status": "LOCKED_EXACT_RULE",
            })

            filename = lower(candidate["filename"])
            if rule.role == "gse112098_adjusted" and "unadjusted" in filename:
                exception_rows.append({
                    "panel_key": panel_key,
                    "source_id": source_id,
                    "source_role": rule.role,
                    "issue": "PROHIBITED_UNADJUSTED_SOURCE_SELECTED",
                })
            if rule.role == "primary_independent_effects" and any(
                token in filename
                for token in ("noninfection", "block", "interaction", "fdr10")
            ):
                exception_rows.append({
                    "panel_key": panel_key,
                    "source_id": source_id,
                    "source_role": rule.role,
                    "issue": "PROHIBITED_NONPRIMARY_SOURCE_SELECTED",
                })

        visual_required = source_id.startswith("U27A4_Figure_")
        visual_complete = (len(assets) == 3) if visual_required else True
        complete = roles_locked == len(rules) and visual_complete

        panel_summary_rows.append({
            "panel_key": panel_key,
            "n_required_roles": len(rules),
            "n_roles_locked": roles_locked,
            "visual_assets_complete": visual_complete,
            "panel_lock_complete": complete,
        })

        if not rules and source_id != "phase_workflow_manifest":
            exception_rows.append({
                "panel_key": panel_key,
                "source_id": source_id,
                "source_role": "",
                "issue": "NO_DETERMINISTIC_RULE_DEFINED",
            })

    locks = pd.DataFrame(lock_rows)
    exceptions = pd.DataFrame(exception_rows)
    summary = pd.DataFrame(panel_summary_rows)

    locks.to_csv(
        out_metadata / "UTI_HostOmics_U27B2A1_locked_panel_source_registry.tsv",
        sep="\t",
        index=False,
    )
    exceptions.to_csv(
        out_tables / "UTI_HostOmics_U27B2A1_source_lock_exceptions.tsv",
        sep="\t",
        index=False,
    )
    summary.to_csv(
        out_tables / "UTI_HostOmics_U27B2A1_panel_lock_summary.tsv",
        sep="\t",
        index=False,
    )

    unresolved = summary[~summary["panel_lock_complete"]].copy()
    unresolved.to_csv(
        out_tables / "UTI_HostOmics_U27B2A1_unlocked_panels.tsv",
        sep="\t",
        index=False,
    )

    prohibited = (
        exceptions[
            exceptions["issue"].str.startswith("PROHIBITED", na=False)
        ]
        if not exceptions.empty
        else pd.DataFrame()
    )

    n_complete = int(summary["panel_lock_complete"].sum())
    n_unlocked = len(unresolved)
    n_prohibited = len(prohibited)
    n_locked_rows = len(locks)
    n_visual_panels = int(
        panels["source_id"].astype(str).str.startswith("U27A4_Figure_").sum()
    )

    if len(summary) != 57:
        decision = "PANEL_COUNT_MISMATCH_REQUIRES_REVIEW"
    elif n_unlocked == 0 and n_prohibited == 0:
        decision = "READY_FOR_U27B2B_SCRIPTED_FINAL_FIGURES_1_TO_4_BUILD"
    else:
        decision = "TARGETED_SOURCE_LOCK_REVIEW_REQUIRED"

    pd.DataFrame([{
        "phase": "U27B2A.1",
        "decision": decision,
        "panels_expected": 57,
        "panels_audited": len(summary),
        "panels_fully_locked": n_complete,
        "panels_unlocked": n_unlocked,
        "locked_source_rows": n_locked_rows,
        "prohibited_source_selections": n_prohibited,
        "U27A4_visual_reference_panels": n_visual_panels,
        "scientific_values_changed": False,
        "manuscript_modified": False,
        "figures_modified": False,
        "next_phase": (
            "U27B2B build Final Figures 1-4"
            if decision.startswith("READY_FOR_U27B2B")
            else "Resolve source-lock exceptions"
        ),
    }]).to_csv(
        out_tables / "UTI_HostOmics_U27B2A1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U27B2A1_exact_source_lock_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# Phase U27B2A.1 - Exact panel source lock\n\n")
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(f"- Panels audited: **{len(summary)}/57**.\n")
        handle.write(f"- Panels fully locked: **{n_complete}/57**.\n")
        handle.write(f"- Unlocked panels: **{n_unlocked}**.\n")
        handle.write(f"- Locked source rows: **{n_locked_rows}**.\n")
        handle.write(
            f"- Prohibited source selections: **{n_prohibited}**.\n"
        )
        handle.write(
            f"- U27A4 visual-reference panels: **{n_visual_panels}**.\n\n"
        )

        handle.write("## Source integrity rules\n\n")
        handle.write(
            "- Figure 2A cannot use noninfection, block, interaction or "
            "FDR-only extracts.\n"
            "- Figure 2E must use age/sex-adjusted GSE112098 results and "
            "cannot use the unadjusted table.\n"
            "- Figure 3B, E and F use the tissue-resolved primary-effect "
            "matrix; Figure 3C uses the cross-tissue coherence table.\n"
            "- Figures 5-8 retain U27A4 as visual references but obtain "
            "numerical values from locked U26 tables.\n"
            "- Working Figures 1 and 6 remain reference-only.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "panels_locked": n_complete,
        "panels_unlocked": n_unlocked,
        "locked_source_rows": n_locked_rows,
        "prohibited_source_selections": n_prohibited,
        "scientific_values_changed": False,
        "manuscript_modified": False,
        "figures_modified": False,
    }
    (
        out_results / "UTI_HostOmics_U27B2A1_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log(f"Panels fully locked: {n_complete}/57")
    log(f"Unlocked panels: {n_unlocked}")
    log(f"Locked source rows: {n_locked_rows}")
    log(f"Prohibited selections: {n_prohibited}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2A.1] ERROR: {exc}", file=sys.stderr)
        raise
