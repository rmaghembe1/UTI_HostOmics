#!/usr/bin/env python3
"""
Phase U27B2A.2
Repair and finalize the exact panel-source lock.

This targeted repair:
1. locks the exact U26B2B1 primary independent-effects table for Figure 2A
   and all independent-effect panels;
2. defines complete source bundles for Figure 6G and Figure 6H;
3. corrects the integrated Figure 8 source semantics:
   - Figure 8A: independent effects + preterm outcome;
   - Figure 8B: broad-cell localization;
   - Figure 8C: U26D2B composition effects only;
   - Figure 8D: U26D2B targeted-state effects only;
   - Figure 8E: refined cross-dataset core + cellular synthesis;
4. preserves all correctly locked rows from U27B2A.1;
5. verifies schemas, panel coverage and prohibited-source exclusions.

No figures, scientific values, source tables or manuscript text are modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import pandas as pd


VERSION = "U27B2A2_v1.0_2026-07-15"
TAG = "phaseU27B2A2_final_panel_source_lock"
SOURCE_TAG = "phaseU27B2A1_exact_panel_source_lock"
ARCH_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"


SOURCE_SPECS: Dict[str, Dict[str, object]] = {
    "primary_independent_effects": {
        "relative_path": (
            "06_tables/"
            "phaseU26B2B1_independent_dataset_evidence_collapse/"
            "UTI_HostOmics_U26B2B1_primary_independent_dataset_effects.tsv"
        ),
        "required_columns": [
            "dataset",
            "primary_context",
            "feature_id",
            "effect_value",
            "effect_metric",
            "interpretation_role",
        ],
    },
    "preterm_collapsed": {
        "relative_path": (
            "06_tables/"
            "phaseU26B2B1_independent_dataset_evidence_collapse/"
            "UTI_HostOmics_U26B2B1_GSE280297_preterm_term_collapsed.tsv"
        ),
        "required_columns": [
            "dataset",
            "primary_context",
            "feature_id",
            "effect_value",
            "tissue_directional_coherence",
            "interpretation_role",
        ],
    },
    "broad_effect_reliability": {
        "relative_path": (
            "06_tables/"
            "phaseU26D2C_cellular_localization_synthesis/"
            "UTI_HostOmics_U26D2C_broad_effect_reliability.tsv"
        ),
        "required_columns": [
            "population",
            "feature_id",
            "module_mean_gene_log2FC",
            "cellular_localization_score",
            "cellular_evidence_class",
        ],
    },
    "module_cellular_synthesis": {
        "relative_path": (
            "06_tables/"
            "phaseU26D2C_cellular_localization_synthesis/"
            "UTI_HostOmics_U26D2C_module_cellular_synthesis.tsv"
        ),
        "required_columns": [
            "feature_id",
            "top_population_by_composite_score",
            "top_refined_subtype",
            "top_refined_subtype_composite_score",
            "cellular_localization_class",
        ],
    },
    "refined_core": {
        "relative_path": (
            "06_tables/"
            "phaseU26C1_interpretation_threshold_and_branch_refinement/"
            "UTI_HostOmics_U26C1_refined_core_and_secondary_modules.tsv"
        ),
        "required_columns": [
            "feature_id",
            "validation_class",
            "independent_evidence_priority_score",
            "manuscript_claim_priority",
            "refined_infection_outcome_relation",
        ],
    },
    "celltype_composition_effects": {
        "relative_path": (
            "06_tables/"
            "phaseU26D2B_GSE252321_refined_celltype_pseudobulk/"
            "UTI_HostOmics_U26D2B_celltype_composition_effects.tsv"
        ),
        "required_columns": [
            "refined_broad_cell_type",
            "difference_UPEC_minus_control",
        ],
    },
    "targeted_state_effects": {
        "relative_path": (
            "06_tables/"
            "phaseU26D2B_GSE252321_refined_celltype_pseudobulk/"
            "UTI_HostOmics_U26D2B_targeted_state_effects.tsv"
        ),
        "required_columns": [
            "targeted_measure",
            "difference_UPEC_minus_control",
        ],
    },
}


# Replace all existing rows for these panels with the explicit source bundles.
REPLACEMENT_BUNDLES: Dict[str, Sequence[str]] = {
    "Figure_2A": (
        "primary_independent_effects",
    ),
    "Figure_5A": (
        "primary_independent_effects",
    ),
    "Figure_6A": (
        "primary_independent_effects",
    ),
    "Figure_6G": (
        "primary_independent_effects",
        "preterm_collapsed",
        "broad_effect_reliability",
        "module_cellular_synthesis",
    ),
    "Figure_6H": (
        "primary_independent_effects",
        "preterm_collapsed",
        "broad_effect_reliability",
        "module_cellular_synthesis",
    ),
    "Figure_7A": (
        "primary_independent_effects",
    ),
    "Figure_8A": (
        "primary_independent_effects",
        "preterm_collapsed",
    ),
    "Figure_8B": (
        "broad_effect_reliability",
    ),
    "Figure_8C": (
        "celltype_composition_effects",
    ),
    "Figure_8D": (
        "targeted_state_effects",
    ),
    "Figure_8E": (
        "refined_core",
        "module_cellular_synthesis",
    ),
}


VISUAL_REFERENCE_FIGURE: Dict[str, int] = {
    "Figure_5A": 7,
    "Figure_6A": 8,
    "Figure_6G": 9,
    "Figure_6H": 9,
    "Figure_7A": 10,
    "Figure_8A": 11,
    "Figure_8B": 11,
    "Figure_8C": 11,
    "Figure_8D": 11,
    "Figure_8E": 11,
}


EXPECTED_ROLE_SEMANTICS: Dict[str, Sequence[str]] = {
    "Figure_8A": (
        "primary_independent_effects",
        "preterm_collapsed",
    ),
    "Figure_8B": (
        "broad_effect_reliability",
    ),
    "Figure_8C": (
        "celltype_composition_effects",
    ),
    "Figure_8D": (
        "targeted_state_effects",
    ),
    "Figure_8E": (
        "refined_core",
        "module_cellular_synthesis",
    ),
}


def log(message: str) -> None:
    print(f"[U27B2A.2] {message}", flush=True)


def read_schema(path: Path) -> List[str]:
    frame = pd.read_csv(
        path,
        sep="\t",
        nrows=2,
        compression="infer",
        low_memory=False,
    )
    return [str(column) for column in frame.columns]


def visual_assets(project: Path, figure_number: int) -> List[str]:
    directory = (
        project
        / "06_figures"
        / "phaseU27A4_final_visual_audit"
    )
    assets = []
    for extension in ("svg", "pdf", "png"):
        path = directory / (
            f"UTI_HostOmics_U27A4_Figure_{figure_number}.{extension}"
        )
        if not path.exists():
            raise FileNotFoundError(
                f"Required U27A4 visual reference not found: {path}"
            )
        assets.append(str(path))
    return assets


def build_exact_source_registry(
    project: Path,
) -> tuple[Dict[str, Dict[str, object]], List[Dict[str, object]]]:
    resolved: Dict[str, Dict[str, object]] = {}
    audit_rows: List[Dict[str, object]] = []

    for role, specification in SOURCE_SPECS.items():
        path = project / str(specification["relative_path"])
        if not path.exists():
            raise FileNotFoundError(
                f"Required source for role {role} not found: {path}"
            )

        columns = read_schema(path)
        missing = sorted(
            set(specification["required_columns"]) - set(columns)
        )
        schema_pass = not missing

        audit_rows.append(
            {
                "source_role": role,
                "path": str(path),
                "exists": True,
                "required_columns": ";".join(
                    specification["required_columns"]
                ),
                "observed_columns": ";".join(columns),
                "missing_required_columns": ";".join(missing),
                "schema_validation_pass": schema_pass,
            }
        )

        if not schema_pass:
            raise RuntimeError(
                f"Source schema failed for {role}: "
                f"missing columns {missing}"
            )

        resolved[role] = {
            "path": str(path),
            "columns": columns,
        }

    return resolved, audit_rows


def source_id_lookup(panel_map: pd.DataFrame) -> Dict[str, str]:
    return dict(
        zip(
            panel_map["panel_key"].astype(str),
            panel_map["source_id"].astype(str),
        )
    )


def figure_panel_lookup(
    panel_map: pd.DataFrame,
) -> Dict[str, tuple[str, str]]:
    return {
        str(row.panel_key): (
            str(row.final_figure),
            str(row.panel),
        )
        for row in panel_map.itertuples(index=False)
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    prior_registry_path = (
        project
        / "03_metadata"
        / SOURCE_TAG
        / "UTI_HostOmics_U27B2A1_locked_panel_source_registry.tsv"
    )
    panel_map_path = (
        project
        / "03_metadata"
        / ARCH_TAG
        / "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv"
    )

    if not prior_registry_path.exists():
        raise FileNotFoundError(
            f"Prior locked registry not found: {prior_registry_path}"
        )
    if not panel_map_path.exists():
        raise FileNotFoundError(
            f"Frozen panel map not found: {panel_map_path}"
        )

    prior = pd.read_csv(
        prior_registry_path,
        sep="\t",
        low_memory=False,
    )
    panel_map = pd.read_csv(
        panel_map_path,
        sep="\t",
        low_memory=False,
    )

    if len(panel_map) != 57:
        raise RuntimeError(
            f"Expected 57 frozen panels; observed {len(panel_map)}."
        )

    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG

    for directory in (out_tables, out_metadata, out_results):
        directory.mkdir(parents=True, exist_ok=True)

    log("Validating exact source files and schemas.")
    exact_sources, source_audit_rows = build_exact_source_registry(
        project
    )

    replacement_keys = set(REPLACEMENT_BUNDLES)
    retained = prior[
        ~prior["panel_key"].astype(str).isin(replacement_keys)
    ].copy()

    source_ids = source_id_lookup(panel_map)
    panel_locations = figure_panel_lookup(panel_map)

    replacement_rows: List[Dict[str, object]] = []

    for panel_key, roles in REPLACEMENT_BUNDLES.items():
        if panel_key not in source_ids:
            raise RuntimeError(
                f"Replacement panel absent from frozen map: {panel_key}"
            )

        final_figure, panel_letter = panel_locations[panel_key]
        figure_number = VISUAL_REFERENCE_FIGURE.get(panel_key)
        assets = (
            visual_assets(project, figure_number)
            if figure_number is not None
            else []
        )

        for role in roles:
            source = exact_sources[role]
            replacement_rows.append(
                {
                    "panel_key": panel_key,
                    "final_figure": final_figure,
                    "panel": panel_letter,
                    "source_id": source_ids[panel_key],
                    "source_role": role,
                    "locked_path": source["path"],
                    "selection_score": "",
                    "second_best_score": "",
                    "score_margin": "",
                    "schema_columns": ";".join(source["columns"]),
                    "visual_reference_assets": ";".join(assets),
                    "lock_status": "LOCKED_EXPLICIT_REPAIR",
                }
            )

    replacements = pd.DataFrame(replacement_rows)
    final_registry = pd.concat(
        [retained, replacements],
        ignore_index=True,
        sort=False,
    ).sort_values(
        ["final_figure", "panel", "source_role", "locked_path"]
    )

    # Confirm that every locked path exists.
    final_registry["locked_path_exists"] = (
        final_registry["locked_path"]
        .astype(str)
        .map(lambda value: Path(value).exists())
    )

    # Confirm all 57 panel keys are represented.
    observed_panels = set(
        final_registry["panel_key"].astype(str)
    )
    expected_panels = set(panel_map["panel_key"].astype(str))
    missing_panels = sorted(expected_panels - observed_panels)
    unexpected_panels = sorted(observed_panels - expected_panels)

    # Panel-level semantic role audit.
    semantic_rows: List[Dict[str, object]] = []
    for panel_key, expected_roles in EXPECTED_ROLE_SEMANTICS.items():
        observed_roles = sorted(
            final_registry.loc[
                final_registry["panel_key"].astype(str) == panel_key,
                "source_role",
            ].astype(str).unique()
        )
        expected_sorted = sorted(expected_roles)
        semantic_rows.append(
            {
                "panel_key": panel_key,
                "expected_roles": ";".join(expected_sorted),
                "observed_roles": ";".join(observed_roles),
                "semantic_role_match": (
                    observed_roles == expected_sorted
                ),
            }
        )

    semantic_audit = pd.DataFrame(semantic_rows)

    # Prohibited-source checks.
    lower_paths = final_registry["locked_path"].astype(str).str.lower()
    prohibited_rows = final_registry[
        (
            final_registry["source_role"].astype(str)
            == "primary_independent_effects"
        )
        & lower_paths.str.contains(
            "noninfection|block_interaction|fdr10_noninfection",
            regex=True,
        )
    ].copy()

    adjusted_rows = final_registry[
        final_registry["source_role"].astype(str)
        == "gse112098_adjusted"
    ].copy()
    if not adjusted_rows.empty:
        prohibited_rows = pd.concat(
            [
                prohibited_rows,
                adjusted_rows[
                    adjusted_rows["locked_path"]
                    .astype(str)
                    .str.lower()
                    .str.contains("unadjusted")
                ],
            ],
            ignore_index=True,
        )

    # U27A4 reference assets must remain references, never numerical sources.
    numerical_u27a4_rows = final_registry[
        final_registry["locked_path"]
        .astype(str)
        .str.contains(
            "/06_figures/phaseU27A4_final_visual_audit/",
            regex=False,
        )
    ].copy()

    panel_summary = (
        final_registry.groupby(
            ["panel_key", "final_figure", "panel"],
            as_index=False,
        )
        .agg(
            n_locked_source_rows=("source_role", "count"),
            n_unique_source_roles=("source_role", "nunique"),
            all_locked_paths_exist=(
                "locked_path_exists",
                "all",
            ),
        )
    )
    panel_summary["panel_lock_complete"] = (
        panel_summary["all_locked_paths_exist"]
    )

    unlocked = panel_summary[
        ~panel_summary["panel_lock_complete"]
    ].copy()

    source_audit = pd.DataFrame(source_audit_rows)

    final_registry.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B2A2_final_locked_panel_source_registry.tsv",
        sep="\t",
        index=False,
    )
    source_audit.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A2_exact_source_schema_audit.tsv",
        sep="\t",
        index=False,
    )
    semantic_audit.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A2_integrated_figure8_semantic_audit.tsv",
        sep="\t",
        index=False,
    )
    panel_summary.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A2_panel_lock_summary.tsv",
        sep="\t",
        index=False,
    )
    unlocked.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A2_unlocked_panels.tsv",
        sep="\t",
        index=False,
    )
    prohibited_rows.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A2_prohibited_source_selections.tsv",
        sep="\t",
        index=False,
    )
    numerical_u27a4_rows.to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A2_U27A4_numerical_source_violations.tsv",
        sep="\t",
        index=False,
    )

    n_panels_locked = len(panel_summary)
    semantic_pass = bool(
        semantic_audit["semantic_role_match"].all()
    )
    source_schema_pass = bool(
        source_audit["schema_validation_pass"].all()
    )
    all_paths_exist = bool(
        final_registry["locked_path_exists"].all()
    )

    if (
        n_panels_locked == 57
        and not missing_panels
        and not unexpected_panels
        and len(unlocked) == 0
        and len(prohibited_rows) == 0
        and len(numerical_u27a4_rows) == 0
        and semantic_pass
        and source_schema_pass
        and all_paths_exist
    ):
        decision = (
            "READY_FOR_U27B2B_SCRIPTED_FINAL_FIGURES_1_TO_4_BUILD"
        )
    else:
        decision = "TARGETED_FINAL_SOURCE_LOCK_REVIEW_REQUIRED"

    pd.DataFrame(
        [
            {
                "phase": "U27B2A.2",
                "decision": decision,
                "panels_expected": 57,
                "panels_with_locked_sources": n_panels_locked,
                "missing_panel_keys": ";".join(missing_panels),
                "unexpected_panel_keys": ";".join(
                    unexpected_panels
                ),
                "unlocked_panels": len(unlocked),
                "locked_source_rows": len(final_registry),
                "replacement_panels": len(REPLACEMENT_BUNDLES),
                "replacement_source_rows": len(replacements),
                "exact_source_schemas_pass": source_schema_pass,
                "integrated_figure8_semantics_pass": semantic_pass,
                "prohibited_source_selections": len(
                    prohibited_rows
                ),
                "U27A4_assets_used_as_numerical_sources": len(
                    numerical_u27a4_rows
                ),
                "all_locked_paths_exist": all_paths_exist,
                "scientific_values_changed": False,
                "manuscript_modified": False,
                "figures_modified": False,
                "next_phase": (
                    "U27B2B build Final Figures 1-4"
                    if decision.startswith("READY_FOR_U27B2B")
                    else "Review the generated audit tables"
                ),
            }
        ]
    ).to_csv(
        out_tables
        / "UTI_HostOmics_U27B2A2_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U27B2A2_final_source_lock_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2A.2 - Final panel-source lock\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Panels with locked sources: "
            f"**{n_panels_locked}/57**.\n"
        )
        handle.write(
            f"- Locked source rows: "
            f"**{len(final_registry)}**.\n"
        )
        handle.write(
            f"- Targeted replacement panels: "
            f"**{len(REPLACEMENT_BUNDLES)}**.\n"
        )
        handle.write(
            f"- Exact source-schema validation: "
            f"**{source_schema_pass}**.\n"
        )
        handle.write(
            f"- Integrated Figure 8 semantic validation: "
            f"**{semantic_pass}**.\n"
        )
        handle.write(
            f"- Prohibited source selections: "
            f"**{len(prohibited_rows)}**.\n"
        )
        handle.write(
            f"- U27A4 assets used as numerical sources: "
            f"**{len(numerical_u27a4_rows)}**.\n\n"
        )

        handle.write("## Repaired source assignments\n\n")
        handle.write(
            "- Figure 2A and independent-effect panels use "
            "`UTI_HostOmics_U26B2B1_primary_independent_dataset_effects.tsv`.\n"
            "- Figure 6G-H use independent infection, pregnancy, broad-cell "
            "and refined-subtype source layers from the full Figure 9 atlas.\n"
            "- Figure 8A uses independent infection plus pregnancy outcome.\n"
            "- Figure 8B uses broad-cell localization.\n"
            "- Figure 8C uses U26D2B cell-composition effects only.\n"
            "- Figure 8D uses U26D2B targeted-state effects only.\n"
            "- Figure 8E uses the refined cross-dataset core plus cellular "
            "synthesis.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "U27A4 SVG/PDF/PNG assets remain visual references only. "
            "All numerical rendering must use the locked U26 tables in the "
            "final registry.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "panels_with_locked_sources": n_panels_locked,
        "locked_source_rows": len(final_registry),
        "replacement_panels": len(REPLACEMENT_BUNDLES),
        "semantic_pass": semantic_pass,
        "source_schema_pass": source_schema_pass,
        "prohibited_source_selections": len(prohibited_rows),
        "scientific_values_changed": False,
        "manuscript_modified": False,
        "figures_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U27B2A2_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Panels with locked sources: {n_panels_locked}/57")
    log(f"Targeted replacement panels: {len(REPLACEMENT_BUNDLES)}")
    log(f"Locked source rows: {len(final_registry)}")
    log(f"Exact source schemas pass: {source_schema_pass}")
    log(f"Integrated Figure 8 semantics pass: {semantic_pass}")
    log(f"Prohibited selections: {len(prohibited_rows)}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2A.2] ERROR: {exc}", file=sys.stderr)
        raise
