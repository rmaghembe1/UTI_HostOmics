#!/usr/bin/env python3
"""
Phase U26C.1
Refine biological interpretation classes before manuscript integration.

Repairs:
1. Near-zero pregnancy effects are not called direction reversals.
2. Steroid synthesis is represented as branch-selective/mixed rather than
   globally preserved or increased.
3. Complement pregnancy architecture is represented as branch-selective.
4. Produces manuscript-facing synthesis statements and a refined Figure 11
   architecture without modifying the manuscript or Figures 1-6.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


VERSION = "U26C1_v1.0_2026-07-14"
TAG = "phaseU26C1_interpretation_threshold_and_branch_refinement"
SOURCE_TAG = "phaseU26C_biological_synthesis_figure_architecture"

NEAR_NEUTRAL_THRESHOLD = 0.20
MODERATE_THRESHOLD = 0.50


def log(message: str) -> None:
    print(f"[U26C.1] {message}", flush=True)


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", low_memory=False)


def classify_effect(value: float) -> str:
    if pd.isna(value):
        return "unresolved"
    value = float(value)
    if abs(value) < NEAR_NEUTRAL_THRESHOLD:
        return "near_neutral"
    return "positive" if value > 0 else "negative"


def classify_relation(infection_direction: str, preterm_effect: float) -> str:
    pregnancy_direction = classify_effect(preterm_effect)
    infection_direction = str(infection_direction).strip().lower()

    if pregnancy_direction in {"unresolved", "near_neutral"}:
        return f"pregnancy_{pregnancy_direction}"
    if infection_direction not in {"positive", "negative"}:
        return "infection_direction_unresolved"
    if infection_direction == pregnancy_direction:
        return "direction_preserved"
    return "direction_reversal"


def domain_interpretation(row: pd.Series) -> str:
    domain = str(row["domain"])
    positive = int(row["n_positive"])
    negative = int(row["n_negative"])
    coherence = float(row["directional_coherence"])

    if domain == "steroid_synthesis":
        return (
            "branch_selective_steroid_synthesis: core steroidogenesis and "
            "androgen/testosterone biosynthesis are positive, whereas estrogen "
            "and cholesterol biosynthesis are negative; do not describe the "
            "entire synthesis domain as globally increased"
        )
    if domain == "steroid_receptor_response":
        return (
            "uniform_receptor_response_attenuation: all five receptor-response "
            "programmes are negative across the tissue-collapsed comparison"
        )
    if domain == "metabolic_effector_response":
        return (
            "uniform_metabolic_effector_attenuation: insulin/IRS, PI3K-AKT, "
            "leptin, transport and carbon-use programmes are negative"
        )
    if domain == "complement_effector_response":
        return (
            "branch_selective_complement_remodeling: classical, terminal-MAC "
            "and opsonophagocytosis are positive while C3a/C5a signaling is "
            "negative"
        )
    if coherence >= 0.75:
        return f"predominantly_{row['dominant_direction']}"
    return "mixed_or_branch_selective"


def build_claim_priority(row: pd.Series) -> str:
    priority = str(row["biological_priority"])
    relation = str(row["refined_infection_outcome_relation"])

    if priority == "robust_core":
        base = "primary_mechanistic_result"
    elif priority == "provisional_core_exploratory_dependent":
        base = "secondary_result_pending_celltype_reconstruction"
    else:
        base = "supporting_mechanistic_result"

    if relation == "direction_reversal":
        return f"{base}_with_state_dependent_reversal"
    if relation == "pregnancy_near_neutral":
        return f"{base}_without_material_pregnancy_outcome_shift"
    return base


def build_figure11_rows(core: pd.DataFrame, domain: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, item in core.iterrows():
        priority = str(item["biological_priority"])
        if priority == "robust_core":
            panel = "A"
            panel_title = "Robust cross-model inflammatory-metabolic core"
        elif priority == "provisional_core_exploratory_dependent":
            panel = "B"
            panel_title = "Provisional complement core requiring cellular resolution"
        else:
            panel = "C"
            panel_title = "Secondary concordant metabolic and endocrine programmes"

        rows.append(
            {
                "panel": panel,
                "panel_title": panel_title,
                "feature_id": item["feature_id"],
                "display_label": item["display_label"],
                "biological_priority": priority,
                "infection_direction": item["dominant_direction"],
                "infection_coherence": item["weighted_directional_coherence"],
                "preterm_effect": item["preterm_vs_term_effect"],
                "preterm_effect_class": item["refined_preterm_effect_class"],
                "infection_outcome_relation": item[
                    "refined_infection_outcome_relation"
                ],
                "figure_role": item["manuscript_claim_priority"],
            }
        )

    for _, item in domain.iterrows():
        rows.append(
            {
                "panel": "D",
                "panel_title": "Pregnancy branch-selective synthesis-response architecture",
                "feature_id": item["domain"],
                "display_label": item["domain"].replace("_", " ").title(),
                "biological_priority": "pregnancy_domain_synthesis",
                "infection_direction": "not_applicable",
                "infection_coherence": np.nan,
                "preterm_effect": item["median_effect"],
                "preterm_effect_class": classify_effect(item["median_effect"]),
                "infection_outcome_relation": "not_applicable",
                "figure_role": item["refined_interpretation"],
            }
        )

    return pd.DataFrame(rows)


def write_report(
    path: Path,
    core: pd.DataFrame,
    domain: pd.DataFrame,
) -> None:
    robust = core[core["biological_priority"] == "robust_core"]
    provisional = core[
        core["biological_priority"]
        == "provisional_core_exploratory_dependent"
    ]
    secondary = core[core["biological_priority"] == "secondary"]

    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26C.1 - Interpretation threshold and branch refinement\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(
            f"- Near-neutral threshold: `|effect| < {NEAR_NEUTRAL_THRESHOLD}`.\n"
        )
        handle.write(
            "- Manuscript and existing Figures 1-6 were not modified.\n\n"
        )

        handle.write("## Corrected cross-state classifications\n\n")
        for _, row in robust.iterrows():
            handle.write(
                f"- **{row['display_label']}**: infection direction "
                f"{row['dominant_direction']}; preterm effect "
                f"{row['preterm_vs_term_effect']:.3f}; refined relation "
                f"`{row['refined_infection_outcome_relation']}`.\n"
            )
        handle.write("\n")

        handle.write("## Branch-selective pregnancy architecture\n\n")
        for _, row in domain.iterrows():
            handle.write(
                f"- **{row['domain']}**: median effect "
                f"{row['median_effect']:.3f}; {row['refined_interpretation']}.\n"
            )
        handle.write("\n")

        handle.write("## Manuscript-facing biological synthesis\n\n")
        handle.write(
            "The cross-model urinary inflammatory response is centered on a "
            "TLR4-linked leptin/PI3K-AKT axis. Leptin and PI3K-AKT show "
            "positive effects across all four infection-context datasets and "
            "marked attenuation in preterm-associated pregnancy tissues. "
            "TLR4-LPS signaling remains a robust infection anchor, but its "
            "preterm-versus-term effect is near neutral and must not be called "
            "a pregnancy direction reversal.\n\n"
        )
        handle.write(
            "Pregnancy-associated endocrine remodeling is branch-selective. "
            "Core steroidogenesis and androgen/testosterone biosynthesis are "
            "positive, whereas estrogen and cholesterol biosynthesis are "
            "negative. In contrast, all evaluated steroid receptor-response "
            "programmes and all evaluated metabolic-effector programmes are "
            "negative. The appropriate working model is therefore selective "
            "steroidogenic branch remodeling coupled to broad receptor and "
            "metabolic-response attenuation, not globally increased steroid "
            "synthesis.\n\n"
        )
        handle.write(
            "Complement remodeling is also branch-selective: classical, "
            "terminal-MAC and opsonophagocytic programmes are positive, "
            "whereas C3a/C5a inflammatory signaling is negative. The "
            "C3a/C5a and opsonophagocytosis cross-dataset signals remain "
            "provisional because their independent moderate support depends "
            "mainly on the n=2-versus-n=2 GSE252321 pseudobulk layer.\n\n"
        )

        handle.write("## Evidence counts\n\n")
        handle.write(f"- Robust core modules: **{len(robust)}**.\n")
        handle.write(f"- Provisional core modules: **{len(provisional)}**.\n")
        handle.write(f"- Secondary concordant modules: **{len(secondary)}**.\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    source_tables = project / "06_tables" / SOURCE_TAG

    core_path = (
        source_tables
        / "UTI_HostOmics_U26C_core_and_secondary_modules.tsv"
    )
    domain_path = (
        source_tables
        / "UTI_HostOmics_U26C_decoupling_domain_summary.tsv"
    )

    for path in [core_path, domain_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    out_tables = project / "06_tables" / TAG
    out_results = project / "05_results" / TAG
    out_metadata = project / "03_metadata" / TAG
    for directory in [out_tables, out_results, out_metadata]:
        directory.mkdir(parents=True, exist_ok=True)

    log("Loading U26C synthesis outputs.")
    core = read_tsv(core_path)
    domain = read_tsv(domain_path)

    core["preterm_vs_term_effect"] = pd.to_numeric(
        core["preterm_vs_term_effect"],
        errors="coerce",
    )
    core["refined_preterm_effect_class"] = core[
        "preterm_vs_term_effect"
    ].map(classify_effect)
    core["refined_infection_outcome_relation"] = core.apply(
        lambda row: classify_relation(
            row["dominant_direction"],
            row["preterm_vs_term_effect"],
        ),
        axis=1,
    )
    core["manuscript_claim_priority"] = core.apply(
        build_claim_priority,
        axis=1,
    )

    domain["median_effect"] = pd.to_numeric(
        domain["median_effect"],
        errors="coerce",
    )
    domain["refined_effect_class"] = domain["median_effect"].map(
        classify_effect
    )
    domain["refined_interpretation"] = domain.apply(
        domain_interpretation,
        axis=1,
    )

    core.to_csv(
        out_tables
        / "UTI_HostOmics_U26C1_refined_core_and_secondary_modules.tsv",
        sep="\t",
        index=False,
    )
    domain.to_csv(
        out_tables
        / "UTI_HostOmics_U26C1_refined_decoupling_domains.tsv",
        sep="\t",
        index=False,
    )

    figure11 = build_figure11_rows(core, domain)
    figure11.to_csv(
        out_tables
        / "UTI_HostOmics_U26C1_refined_Figure_11_architecture.tsv",
        sep="\t",
        index=False,
    )

    correction_log = pd.DataFrame(
        [
            {
                "issue": "TLR4 preterm effect classification",
                "original": "direction_reversal",
                "revised": "pregnancy_near_neutral",
                "basis": (
                    f"|effect| < {NEAR_NEUTRAL_THRESHOLD}; observed effect "
                    "-0.058"
                ),
            },
            {
                "issue": "Steroid synthesis domain wording",
                "original": "preserved_or_increased_steroid_synthesis",
                "revised": "branch_selective_mixed_steroid_synthesis",
                "basis": (
                    "Core steroidogenesis and androgen biosynthesis positive; "
                    "estrogen and cholesterol biosynthesis negative"
                ),
            },
            {
                "issue": "Complement outcome wording",
                "original": "complement_activation",
                "revised": "branch_selective_complement_remodeling",
                "basis": (
                    "Classical/MAC/opsonophagocytosis positive; C3a/C5a "
                    "signaling negative"
                ),
            },
        ]
    )
    correction_log.to_csv(
        out_metadata
        / "UTI_HostOmics_U26C1_interpretation_correction_log.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U26C1_refined_biological_synthesis_report.md"
    )
    write_report(report_path, core, domain)

    decision = (
        "READY_FOR_U26D_CELLTYPE_RECONSTRUCTION_AND_"
        "U27_FIGURE_BUILD_WITH_REFINED_INTERPRETATION"
    )

    pd.DataFrame(
        [
            {
                "phase": "U26C.1",
                "decision": decision,
                "near_neutral_absolute_effect_threshold": (
                    NEAR_NEUTRAL_THRESHOLD
                ),
                "n_robust_core_modules": int(
                    (core["biological_priority"] == "robust_core").sum()
                ),
                "n_provisional_core_modules": int(
                    (
                        core["biological_priority"]
                        == "provisional_core_exploratory_dependent"
                    ).sum()
                ),
                "n_secondary_modules": int(
                    (core["biological_priority"] == "secondary").sum()
                ),
                "n_true_direction_reversals": int(
                    (
                        core["refined_infection_outcome_relation"]
                        == "direction_reversal"
                    ).sum()
                ),
                "TLR4_pregnancy_class": core.loc[
                    core["feature_id"] == "TLR4_LPS_SIGNALING_ANCHOR",
                    "refined_infection_outcome_relation",
                ].iloc[0],
                "steroid_synthesis_domain": (
                    "branch_selective_mixed"
                ),
                "complement_domain": (
                    "branch_selective"
                ),
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U26D targeted GSE252321 cell-type reconstruction; "
                    "U27 refined Figure 7-11 construction"
                ),
            }
        ]
    ).to_csv(
        out_tables / "UTI_HostOmics_U26C1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "near_neutral_threshold": NEAR_NEUTRAL_THRESHOLD,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results / "UTI_HostOmics_U26C1_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log(
        "TLR4 pregnancy relation: "
        + str(
            core.loc[
                core["feature_id"] == "TLR4_LPS_SIGNALING_ANCHOR",
                "refined_infection_outcome_relation",
            ].iloc[0]
        )
    )
    log("Steroid synthesis: branch-selective mixed architecture.")
    log("Complement: branch-selective architecture.")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26C.1] ERROR: {exc}", file=sys.stderr)
        raise
