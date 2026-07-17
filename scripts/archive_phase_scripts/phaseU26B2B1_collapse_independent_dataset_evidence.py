#!/usr/bin/env python3
"""
Phase U26B2B.1
Independent-dataset evidence collapse and biologically disciplined recurrence.

This phase corrects correlated-evidence inflation in U26B2B by using one
primary infection-context effect per dataset and module:

- GSE112098: age/sex-adjusted sepsis vs vascular-surgery effect only.
- GSE186800: average Gardnerella vs PBS treatment effect only.
- GSE252321: UPEC vs control sample-pseudobulk effect only.
- GSE280297: median UPEC vs PBS pregnancy effect across bladder, uterus,
  and placenta, with tissue-direction coherence retained separately.

It also separates:
- GSE186800 block/exposure-stage effects from pathogen-treatment effects.
- GSE280297 preterm-vs-term pregnancy-outcome architecture from infection
  recurrence.
- GSE252321 tiny-group exploratory effects from inferential validation.

No manuscript or existing Figures 1-6 are modified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit(
        "ERROR: matplotlib is required. Install with conda or pip."
    ) from exc


VERSION = "U26B2B1_v1.0_2026-07-14"
PHASE_TAG = "phaseU26B2B1_independent_dataset_evidence_collapse"

DATASET_WEIGHTS = {
    "GSE112098": 1.0,
    "GSE186800": 1.0,
    "GSE280297": 1.0,
    "GSE252321": 0.25,
}

PRIMARY_CONTEXTS = {
    "GSE112098": "GSE112098_SEPSIS_VS_VASCULAR_SURGERY_ADJUSTED",
    "GSE186800": "GSE186800_AVERAGE_TREATMENT",
    "GSE252321": "GSE252321_UPEC_VS_CONTROL",
}


def log(message: str) -> None:
    print(f"[U26B2B.1] {message}", flush=True)


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        compression="infer",
        low_memory=False,
    )


def bool_series(series: pd.Series) -> pd.Series:
    return (
        series.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def sign_label(value: float) -> str:
    if not np.isfinite(value):
        return "unresolved"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def collapse_gse280297(
    evidence: pd.DataFrame,
    contrast_prefix: str,
    context_label: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    subset = evidence[
        (evidence["dataset"] == "GSE280297")
        & evidence["contrast_id"].astype(str).str.startswith(
            contrast_prefix
        )
    ].copy()

    subset["effect_value"] = numeric(subset["effect_value"])
    subset["q_value"] = numeric(subset["q_value"])
    subset["fdr_bool"] = bool_series(subset["fdr_0_10"])

    tissue_rows = []
    collapsed_rows = []

    grouping = [
        "feature_type",
        "axis",
        "feature_id",
        "display_label",
        "proposed_figure_family",
    ]

    for keys, group in subset.groupby(grouping, dropna=False):
        group = group.copy()
        effects = group["effect_value"].dropna().to_numpy(dtype=float)

        if len(effects) == 0:
            continue

        positive = int(np.sum(effects > 0))
        negative = int(np.sum(effects < 0))
        nonzero = positive + negative
        coherence = (
            max(positive, negative) / nonzero
            if nonzero
            else 0.0
        )
        median_effect = float(np.median(effects))
        mean_effect = float(np.mean(effects))

        for _, row in group.iterrows():
            tissue = str(row["contrast_id"]).split("__")[-1]
            tissue_rows.append(
                {
                    "dataset": "GSE280297",
                    "analysis_family": context_label,
                    "tissue": tissue,
                    "feature_type": keys[0],
                    "axis": keys[1],
                    "feature_id": keys[2],
                    "display_label": keys[3],
                    "proposed_figure_family": keys[4],
                    "effect_value": float(row["effect_value"]),
                    "q_value": (
                        float(row["q_value"])
                        if np.isfinite(row["q_value"])
                        else np.nan
                    ),
                    "fdr_0_10": bool(row["fdr_bool"]),
                    "direction": sign_label(float(row["effect_value"])),
                }
            )

        collapsed_rows.append(
            {
                "dataset": "GSE280297",
                "primary_context": context_label,
                "feature_type": keys[0],
                "axis": keys[1],
                "feature_id": keys[2],
                "display_label": keys[3],
                "proposed_figure_family": keys[4],
                "effect_value": median_effect,
                "mean_tissue_effect": mean_effect,
                "effect_metric": "median_tissue_hedges_g",
                "n_tissues": len(effects),
                "n_positive_tissues": positive,
                "n_negative_tissues": negative,
                "tissue_directional_coherence": coherence,
                "direction": sign_label(median_effect),
                "fdr_0_10": bool(group["fdr_bool"].any()),
                "best_tissue_q_value": (
                    float(group["q_value"].min(skipna=True))
                    if group["q_value"].notna().any()
                    else np.nan
                ),
                "evidence_weight": DATASET_WEIGHTS["GSE280297"],
                "interpretation_role": (
                    "pregnancy_tissue_discovery_collapsed_across_tissues"
                ),
            }
        )

    return pd.DataFrame(collapsed_rows), pd.DataFrame(tissue_rows)


def select_primary_dataset_effects(
    evidence: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for dataset, contrast_id in PRIMARY_CONTEXTS.items():
        subset = evidence[
            (evidence["dataset"] == dataset)
            & (evidence["contrast_id"] == contrast_id)
        ].copy()

        subset["effect_value"] = numeric(subset["effect_value"])
        subset["q_value"] = numeric(subset["q_value"])
        subset["fdr_bool"] = bool_series(subset["fdr_0_10"])

        for _, row in subset.iterrows():
            rows.append(
                {
                    "dataset": dataset,
                    "primary_context": contrast_id,
                    "feature_type": row["feature_type"],
                    "axis": row["axis"],
                    "feature_id": row["feature_id"],
                    "display_label": row["display_label"],
                    "proposed_figure_family": row[
                        "proposed_figure_family"
                    ],
                    "effect_value": (
                        float(row["effect_value"])
                        if np.isfinite(row["effect_value"])
                        else np.nan
                    ),
                    "effect_metric": row["effect_metric"],
                    "direction": sign_label(
                        float(row["effect_value"])
                        if np.isfinite(row["effect_value"])
                        else np.nan
                    ),
                    "fdr_0_10": bool(row["fdr_bool"]),
                    "q_value": (
                        float(row["q_value"])
                        if np.isfinite(row["q_value"])
                        else np.nan
                    ),
                    "evidence_weight": DATASET_WEIGHTS[dataset],
                    "interpretation_role": (
                        "human_systemic_urinary_inflammation_comparator"
                        if dataset == "GSE112098"
                        else "mouse_bladder_average_pathogen_exposure_effect"
                        if dataset == "GSE186800"
                        else "exploratory_mouse_whole_object_UPEC_pseudobulk"
                    ),
                }
            )

    return pd.DataFrame(rows)


def build_independent_recurrence(
    primary_effects: pd.DataFrame,
) -> pd.DataFrame:
    modules = primary_effects[
        primary_effects["feature_type"] == "submodule"
    ].copy()
    modules["effect_value"] = numeric(modules["effect_value"])
    modules["absolute_effect"] = np.abs(modules["effect_value"])
    modules["moderate_effect"] = modules["absolute_effect"] >= 0.50
    modules["large_effect"] = modules["absolute_effect"] >= 0.80
    modules["fdr_bool"] = bool_series(modules["fdr_0_10"])

    rows = []
    grouping = [
        "feature_id",
        "axis",
        "display_label",
        "proposed_figure_family",
    ]

    for keys, group in modules.groupby(grouping, dropna=False):
        group = group.dropna(subset=["effect_value"]).copy()
        if group.empty:
            continue

        effects = group["effect_value"].to_numpy(dtype=float)
        positive_mask = effects > 0
        negative_mask = effects < 0

        positive_weight = float(
            group.loc[positive_mask, "evidence_weight"].sum()
        )
        negative_weight = float(
            group.loc[negative_mask, "evidence_weight"].sum()
        )
        total_weight = positive_weight + negative_weight

        dominant_direction = (
            "positive"
            if positive_weight > negative_weight
            else "negative"
            if negative_weight > positive_weight
            else "mixed"
        )
        weighted_coherence = (
            max(positive_weight, negative_weight) / total_weight
            if total_weight > 0
            else 0.0
        )

        n_fdr = int(group["fdr_bool"].sum())
        n_moderate = int(group["moderate_effect"].sum())
        n_large = int(group["large_effect"].sum())
        n_datasets = int(group["dataset"].nunique())

        if n_fdr >= 2:
            validation_class = "replicated_FDR_across_independent_datasets"
        elif (
            n_fdr >= 1
            and n_moderate >= 2
            and weighted_coherence >= 0.67
        ):
            validation_class = (
                "one_FDR_dataset_plus_independent_concordant_effect"
            )
        elif (
            n_large >= 2
            and weighted_coherence >= 0.67
        ):
            validation_class = "multi_dataset_large_concordant_effect"
        elif (
            n_moderate >= 3
            and weighted_coherence >= 0.67
        ):
            validation_class = "broad_multi_dataset_concordant_effect"
        elif (
            n_moderate >= 2
            and weighted_coherence >= 0.67
        ):
            validation_class = "two_dataset_concordant_effect"
        elif weighted_coherence < 0.67:
            validation_class = "context_divergent_or_tissue_specific"
        else:
            validation_class = "limited_independent_support"

        dataset_effects = []
        for _, row in group.sort_values("dataset").iterrows():
            dataset_effects.append(
                f"{row['dataset']}:{row['effect_value']:.4f}"
            )

        priority_score = (
            5.0 * n_fdr
            + 2.5 * n_large
            + 1.5 * n_moderate
            + 1.0 * weighted_coherence
            + float(np.median(np.abs(effects)))
            + 0.25 * n_datasets
        )

        rows.append(
            {
                "feature_id": keys[0],
                "axis": keys[1],
                "display_label": keys[2],
                "proposed_figure_family": keys[3],
                "n_independent_datasets": n_datasets,
                "datasets": ";".join(
                    sorted(group["dataset"].astype(str).unique())
                ),
                "dataset_effects": ";".join(dataset_effects),
                "n_positive_datasets": int(np.sum(positive_mask)),
                "n_negative_datasets": int(np.sum(negative_mask)),
                "dominant_direction": dominant_direction,
                "weighted_directional_coherence": weighted_coherence,
                "median_effect": float(np.median(effects)),
                "median_absolute_effect": float(
                    np.median(np.abs(effects))
                ),
                "max_absolute_effect": float(
                    np.max(np.abs(effects))
                ),
                "n_FDR10_datasets": n_fdr,
                "n_moderate_effect_datasets": n_moderate,
                "n_large_effect_datasets": n_large,
                "validation_class": validation_class,
                "independent_evidence_priority_score": priority_score,
            }
        )

    return pd.DataFrame(rows).sort_values(
        [
            "independent_evidence_priority_score",
            "n_independent_datasets",
        ],
        ascending=False,
    )


def extract_gse186800_noninfection_effects(
    evidence: pd.DataFrame,
) -> pd.DataFrame:
    subset = evidence[
        (evidence["dataset"] == "GSE186800")
        & evidence["contrast_id"].isin(
            [
                "GSE186800_BLOCK_MAIN_PBS",
                "GSE186800_INTERACTION_RECURRENCE",
            ]
        )
    ].copy()

    subset["effect_value"] = numeric(subset["effect_value"])
    subset["q_value"] = numeric(subset["q_value"])
    subset["fdr_bool"] = bool_series(subset["fdr_0_10"])

    subset["interpretation_boundary"] = np.where(
        subset["contrast_id"] == "GSE186800_BLOCK_MAIN_PBS",
        (
            "Exposure-stage or experimental-block difference among PBS "
            "controls; not a Gardnerella treatment effect."
        ),
        (
            "Treatment-by-block interaction; recurrence/adaptation hypothesis "
            "only, not a simple pathogen main effect."
        ),
    )

    return subset.sort_values(
        ["fdr_bool", "q_value"],
        ascending=[False, True],
    )


def family_rankings(
    recurrence: pd.DataFrame,
) -> pd.DataFrame:
    if recurrence.empty:
        return recurrence

    return recurrence.sort_values(
        [
            "proposed_figure_family",
            "independent_evidence_priority_score",
        ],
        ascending=[True, False],
    )


def figure_panel_plan(
    rankings: pd.DataFrame,
    pregnancy_outcome: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    family_titles = {
        "Figure_7": (
            "Steroid, cholesterol, lipid-peroxidation and receptor-response "
            "remodeling"
        ),
        "Figure_8": (
            "Inflammatory carbon use, insulin/IRS, adipokine and energy-sensing "
            "architecture"
        ),
        "Figure_9": (
            "Amino-acid, nucleotide, nitrogen, nitric-oxide and catecholamine "
            "metabolism"
        ),
        "Figure_10": (
            "Complement initiation, amplification, effector and regulatory "
            "architecture"
        ),
    }

    for family, title in family_titles.items():
        subset = rankings[
            rankings["proposed_figure_family"] == family
        ].head(10)

        selected = subset["feature_id"].astype(str).tolist()

        panels = [
            (
                "A",
                "Independent-dataset effect heatmap",
                "One primary effect per dataset; no repeated contrasts.",
            ),
            (
                "B",
                "Human comparator adjusted effects",
                "Age/sex-adjusted GSE112098 estimates with FDR.",
            ),
            (
                "C",
                "Mouse bladder exposure effects",
                "GSE186800 average Gardnerella effect, not PBS block effect.",
            ),
            (
                "D",
                "Pregnancy-tissue UPEC architecture",
                "Median effect plus bladder/uterus/placenta heterogeneity.",
            ),
            (
                "E",
                "Exploratory UPEC pseudobulk",
                "GSE252321 n=2 per group; direction and magnitude only.",
            ),
            (
                "F",
                "Mechanistic pathway schematic",
                "Link prioritized submodules into immune-metabolic biology.",
            ),
        ]

        for panel, panel_title, purpose in panels:
            rows.append(
                {
                    "figure_family": family,
                    "figure_title": title,
                    "panel": panel,
                    "panel_title": panel_title,
                    "purpose": purpose,
                    "priority_modules": ";".join(selected),
                }
            )

    pregnancy_priority = (
        pregnancy_outcome.sort_values(
            "absolute_effect",
            ascending=False,
        )["feature_id"]
        .head(15)
        .astype(str)
        .tolist()
        if not pregnancy_outcome.empty
        else []
    )

    for panel, panel_title, purpose in [
        (
            "A",
            "Cross-dataset convergence network",
            "Connect recurrent immune, endocrine and metabolic modules.",
        ),
        (
            "B",
            "Pregnancy outcome architecture",
            "Preterm-vs-term tissue-collapsed effects and tissue heterogeneity.",
        ),
        (
            "C",
            "Synthesis-response decoupling",
            "Contrast steroid biosynthesis with receptor-response programmes.",
        ),
        (
            "D",
            "Carbon-complement-inflammatory integration",
            "Integrate glycolysis, xanthine oxidase, complement and NETosis.",
        ),
        (
            "E",
            "Evidence hierarchy",
            "Separate human FDR evidence, mouse effects and exploratory signals.",
        ),
        (
            "F",
            "Working mechanistic model",
            "Generate manuscript-facing synthesis after final review.",
        ),
    ]:
        rows.append(
            {
                "figure_family": "Figure_11",
                "figure_title": (
                    "Integrated endocrine-metabolic-immune model of urinary "
                    "inflammation and pregnancy-associated UTI biology"
                ),
                "panel": panel,
                "panel_title": panel_title,
                "purpose": purpose,
                "priority_modules": ";".join(pregnancy_priority),
            }
        )

    return pd.DataFrame(rows)


def effect_matrix(
    primary_effects: pd.DataFrame,
) -> pd.DataFrame:
    modules = primary_effects[
        primary_effects["feature_type"] == "submodule"
    ].copy()

    if modules.empty:
        return pd.DataFrame()

    modules["effect_value"] = numeric(modules["effect_value"])

    return modules.pivot_table(
        index="feature_id",
        columns="dataset",
        values="effect_value",
        aggfunc="first",
    )


def save_heatmap(
    matrix: pd.DataFrame,
    rankings: pd.DataFrame,
    output_stem: Path,
    title: str,
    family: Optional[str] = None,
    top_n: int = 30,
) -> None:
    if matrix.empty:
        return

    ranking_subset = rankings.copy()
    if family is not None:
        ranking_subset = ranking_subset[
            ranking_subset["proposed_figure_family"] == family
        ]

    selected = (
        ranking_subset["feature_id"]
        .head(top_n)
        .astype(str)
        .tolist()
    )
    selected = [
        feature
        for feature in selected
        if feature in matrix.index
    ]

    if not selected:
        return

    plot_matrix = matrix.loc[selected]

    width = max(8.5, 1.2 * len(plot_matrix.columns) + 4.5)
    height = max(5.0, 0.38 * len(plot_matrix.index) + 2.5)

    figure = plt.figure(figsize=(width, height))
    axis = figure.add_axes([0.34, 0.16, 0.50, 0.72])

    image = axis.imshow(
        plot_matrix.to_numpy(dtype=float),
        aspect="auto",
    )
    axis.set_xticks(np.arange(len(plot_matrix.columns)))
    axis.set_xticklabels(
        plot_matrix.columns,
        rotation=35,
        ha="right",
        fontsize=9,
    )
    axis.set_yticks(np.arange(len(plot_matrix.index)))
    axis.set_yticklabels(plot_matrix.index, fontsize=8)
    axis.set_title(title)
    axis.set_xlabel("Independent dataset primary effect")
    axis.set_ylabel("Submodule")

    colorbar = figure.colorbar(
        image,
        ax=axis,
        fraction=0.045,
        pad=0.04,
    )
    colorbar.set_label(
        "Standardized effect\n"
        "(adjusted beta, treatment beta, or Hedges' g)"
    )

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output_stem.with_suffix(".png"),
        dpi=300,
        bbox_inches="tight",
    )
    figure.savefig(
        output_stem.with_suffix(".svg"),
        bbox_inches="tight",
    )
    plt.close(figure)


def write_report(
    path: Path,
    recurrence: pd.DataFrame,
    block_effects: pd.DataFrame,
    pregnancy_outcome: pd.DataFrame,
    primary_effects: pd.DataFrame,
) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26B2B.1 - Independent-dataset evidence collapse\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(
            "- Manuscript and existing Figures 1-6 were not modified.\n"
        )
        handle.write(
            "- One primary infection-context effect per dataset and module "
            "was used for cross-dataset recurrence.\n\n"
        )

        handle.write("## Evidence-collapse rules\n\n")
        handle.write(
            "- GSE112098: age/sex-adjusted sepsis-versus-vascular-surgery "
            "effect only; unadjusted results are sensitivity evidence.\n"
        )
        handle.write(
            "- GSE186800: average Gardnerella-versus-PBS effect only; block "
            "and interaction effects are reported separately.\n"
        )
        handle.write(
            "- GSE280297: median UPEC-versus-PBS pregnancy effect across "
            "bladder, uterus and placenta, retaining tissue coherence.\n"
        )
        handle.write(
            "- GSE252321: one UPEC-versus-control sample-pseudobulk effect, "
            "down-weighted because n=2 per group.\n\n"
        )

        handle.write("## Independent-dataset recurrence\n\n")
        if recurrence.empty:
            handle.write("No recurrence table was generated.\n\n")
        else:
            class_counts = (
                recurrence["validation_class"]
                .value_counts()
                .to_dict()
            )
            for label, count in class_counts.items():
                handle.write(
                    f"- **{label}**: {int(count)} modules.\n"
                )
            handle.write("\n")

            for _, row in recurrence.head(30).iterrows():
                handle.write(
                    f"- `{row['feature_id']}`: "
                    f"{row['validation_class']}; "
                    f"{int(row['n_FDR10_datasets'])} independent FDR<0.10 "
                    f"datasets; {int(row['n_moderate_effect_datasets'])} "
                    f"datasets with |effect|>=0.5; dominant direction "
                    f"{row['dominant_direction']} "
                    f"(weighted coherence="
                    f"{row['weighted_directional_coherence']:.2f}).\n"
                )
            handle.write("\n")

        handle.write("## GSE186800 interpretation boundary\n\n")
        significant_block = block_effects[
            block_effects["fdr_bool"]
        ]
        handle.write(
            f"- FDR<0.10 block or interaction effects: "
            f"**{len(significant_block)}**.\n"
        )
        handle.write(
            "- PBS block effects are exposure-stage or experimental-block "
            "differences and must not be described as Gardnerella-induced "
            "pathway changes.\n\n"
        )

        handle.write("## GSE280297 pregnancy outcome architecture\n\n")
        if pregnancy_outcome.empty:
            handle.write(
                "No preterm-versus-term collapsed table was generated.\n\n"
            )
        else:
            for _, row in pregnancy_outcome.sort_values(
                "absolute_effect",
                ascending=False,
            ).head(20).iterrows():
                handle.write(
                    f"- `{row['feature_id']}`: median tissue effect "
                    f"{row['effect_value']:.3f}; tissue coherence "
                    f"{row['tissue_directional_coherence']:.2f}; direction "
                    f"{row['direction']}.\n"
                )
            handle.write("\n")

        handle.write("## Evidence hierarchy\n\n")
        handle.write(
            "- Human adjusted FDR evidence is the strongest inferential layer, "
            "but it represents systemic urinary inflammation rather than UTI.\n"
        )
        handle.write(
            "- GSE186800 treatment effects provide independent mouse-bladder "
            "support; its significant PBS block effects are not infection "
            "validation.\n"
        )
        handle.write(
            "- GSE280297 provides pregnancy and tissue architecture, with "
            "limited contrast-wide FDR support.\n"
        )
        handle.write(
            "- GSE252321 provides exploratory whole-study UPEC direction only "
            "until cell-type pseudobulk reconstruction is available.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    source_tag = "phaseU26B2B_cross_dataset_scoring_integration"
    source_tables = project / "06_tables" / source_tag

    evidence_path = (
        source_tables
        / "UTI_HostOmics_U26B2B_harmonized_effect_evidence.tsv"
    )

    if not evidence_path.exists():
        raise FileNotFoundError(
            f"Required U26B2B evidence table not found: {evidence_path}"
        )

    output_results = project / "05_results" / PHASE_TAG
    output_tables = project / "06_tables" / PHASE_TAG
    output_figures = project / "06_figures" / PHASE_TAG
    output_metadata = project / "03_metadata" / PHASE_TAG

    for directory in [
        output_results,
        output_tables,
        output_figures,
        output_metadata,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    log("Loading harmonized U26B2B evidence.")
    evidence = read_tsv(evidence_path)

    primary_nonpregnancy = select_primary_dataset_effects(evidence)

    pregnancy_infection, pregnancy_infection_tissues = collapse_gse280297(
        evidence,
        "C2_UPEC_VS_PBS_PREGNANCY__",
        "GSE280297_UPEC_VS_PBS_PREGNANCY_COLLAPSED",
    )

    pregnancy_outcome, pregnancy_outcome_tissues = collapse_gse280297(
        evidence,
        "C1_PRETERM_VS_TERM__",
        "GSE280297_PRETERM_VS_TERM_COLLAPSED",
    )

    primary_effects = pd.concat(
        [primary_nonpregnancy, pregnancy_infection],
        ignore_index=True,
        sort=False,
    )

    primary_effects.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_primary_independent_dataset_effects.tsv",
        sep="\t",
        index=False,
    )

    pregnancy_infection_tissues.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_GSE280297_UPEC_tissue_heterogeneity.tsv",
        sep="\t",
        index=False,
    )

    pregnancy_outcome["absolute_effect"] = np.abs(
        numeric(pregnancy_outcome["effect_value"])
    )
    pregnancy_outcome.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_GSE280297_preterm_term_collapsed.tsv",
        sep="\t",
        index=False,
    )

    pregnancy_outcome_tissues.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_GSE280297_preterm_term_tissue_effects.tsv",
        sep="\t",
        index=False,
    )

    recurrence = build_independent_recurrence(primary_effects)
    recurrence.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_independent_dataset_recurrence_ranking.tsv",
        sep="\t",
        index=False,
    )

    block_effects = extract_gse186800_noninfection_effects(evidence)
    block_effects.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_GSE186800_block_interaction_effects.tsv",
        sep="\t",
        index=False,
    )

    significant_block = block_effects[
        block_effects["fdr_bool"]
    ].copy()
    significant_block.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_GSE186800_FDR10_noninfection_effects.tsv",
        sep="\t",
        index=False,
    )

    rankings = family_rankings(recurrence)
    rankings.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_figure_family_rankings.tsv",
        sep="\t",
        index=False,
    )

    panel_plan = figure_panel_plan(
        rankings,
        pregnancy_outcome,
    )
    panel_plan.to_csv(
        output_metadata
        / "UTI_HostOmics_U26B2B1_Figures_7_to_11_panel_plan.tsv",
        sep="\t",
        index=False,
    )

    matrix = effect_matrix(primary_effects)
    matrix.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_independent_dataset_effect_matrix.tsv",
        sep="\t",
    )

    save_heatmap(
        matrix,
        rankings,
        output_figures
        / "UTI_HostOmics_U26B2B1_independent_dataset_effect_heatmap",
        "Independent-dataset endocrine-metabolic-immune effects",
        top_n=35,
    )

    for family in [
        "Figure_7",
        "Figure_8",
        "Figure_9",
        "Figure_10",
    ]:
        save_heatmap(
            matrix,
            rankings,
            output_figures
            / f"UTI_HostOmics_U26B2B1_{family}_independent_effect_heatmap",
            f"{family}: one primary effect per independent dataset",
            family=family,
            top_n=15,
        )

    class_summary = (
        recurrence["validation_class"]
        .value_counts()
        .rename_axis("validation_class")
        .reset_index(name="n_modules")
    )
    class_summary.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_validation_class_summary.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        output_results
        / "UTI_HostOmics_U26B2B1_independent_evidence_report.md"
    )
    write_report(
        report_path,
        recurrence,
        block_effects,
        pregnancy_outcome,
        primary_effects,
    )

    replicated_fdr = int(
        (
            recurrence["validation_class"]
            == "replicated_FDR_across_independent_datasets"
        ).sum()
    )
    one_fdr_plus = int(
        (
            recurrence["validation_class"]
            == "one_FDR_dataset_plus_independent_concordant_effect"
        ).sum()
    )
    multi_large = int(
        (
            recurrence["validation_class"]
            == "multi_dataset_large_concordant_effect"
        ).sum()
    )

    decision = (
        "READY_FOR_U26C_BIOLOGICAL_SYNTHESIS_AND_FIGURE_ARCHITECTURE_"
        "CELLTYPE_RECONSTRUCTION_DEFERRED"
    )

    decision_table = pd.DataFrame(
        [
            {
                "phase": "U26B2B.1",
                "decision": decision,
                "n_primary_dataset_effect_rows": len(primary_effects),
                "n_ranked_submodules": len(recurrence),
                "n_replicated_FDR_modules": replicated_fdr,
                "n_one_FDR_plus_independent_modules": one_fdr_plus,
                "n_multi_dataset_large_concordant_modules": multi_large,
                "n_GSE186800_FDR10_block_or_interaction_effects": len(
                    significant_block
                ),
                "GSE186800_FDR10_treatment_effects": 0,
                "GSE252321_cell_type_pseudobulk": "deferred",
                "critical_rule": (
                    "Do not call PBS block effects Gardnerella effects; do not "
                    "count adjusted and unadjusted human models as independent "
                    "datasets."
                ),
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U26C biological synthesis, Figure 7-11 panel selection, "
                    "and cell-type reconstruction decision"
                ),
            }
        ]
    )
    decision_table.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "decision": decision,
        "primary_effect_rows": int(len(primary_effects)),
        "ranked_submodules": int(len(recurrence)),
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        output_results
        / "UTI_HostOmics_U26B2B1_run_manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
        )
    )

    log(f"Primary independent dataset effect rows: {len(primary_effects)}")
    log(f"Ranked submodules: {len(recurrence)}")
    log(f"Replicated FDR modules: {replicated_fdr}")
    log(f"One-FDR-plus-independent modules: {one_fdr_plus}")
    log(f"Multi-dataset large concordant modules: {multi_large}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26B2B.1] ERROR: {exc}", file=sys.stderr)
        raise
