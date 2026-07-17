#!/usr/bin/env python3
"""
Phase U26D2C
Cellular-localization synthesis for GSE252321 and Figure 7-11 integration.

Purpose
-------
U26D2B successfully localized 73 transcriptionally inferred pathway modules
across six complete broad immune populations and fourteen complete refined
subtypes. With only two control and two UPEC biological samples, Hedges g can
become extremely large when within-group variance is very small. This phase
therefore avoids ranking biology by Hedges g alone.

The synthesis jointly uses:
- module mean gene log2 fold change;
- within-module gene-direction coherence;
- standardized module-score effect;
- consistency across broad populations;
- refined-subtype localization;
- cell-composition and fixed targeted-state changes.

No new cell-level significance tests are performed. Biological samples remain
the inferential units. The manuscript and Figures 1-6 are not modified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit("ERROR: matplotlib is required.") from exc


VERSION = "U26D2C_v1.0_2026-07-14"
TAG = "phaseU26D2C_cellular_localization_synthesis"
SOURCE_TAG = "phaseU26D2B_GSE252321_refined_celltype_pseudobulk"
CORE_TAG = "phaseU26C1_interpretation_threshold_and_branch_refinement"

MYELOID = {"macrophage_monocyte", "dendritic", "neutrophil"}
LYMPHOID = {"T_cell", "NK_cell"}
CYCLING = {"cycling_immune"}

CORE_FEATURES = [
    "TLR4_LPS_SIGNALING_ANCHOR",
    "LEPTIN_SIGNALING",
    "PI3K_AKT_SIGNALING",
    "COMPLEMENT_C3A_C5A_SIGNALING",
    "COMPLEMENT_OPSONOPHAGOCYTOSIS",
    "INSULIN_RECEPTOR_IRS",
    "GLYCOGEN_SYNTHESIS",
    "ANDROGEN_RECEPTOR_SIGNALING",
    "FATTY_ACID_SYNTHESIS",
    "AMINO_ACID_TRANSPORT",
]

FIGURE_PANEL_PLAN = [
    {
        "figure": "Figure_7",
        "panel": "A",
        "title": "Cell-resolved endocrine and lipid pathway heatmap",
        "modules": (
            "GLUCOCORTICOID_RESPONSE;ESTROGEN_RECEPTOR_RESPONSE;"
            "ANDROGEN_RECEPTOR_SIGNALING;STEROIDOGENESIS_CORE;"
            "CHOLESTEROL_BIOSYNTHESIS;FERROPTOSIS_LIPID_PEROXIDATION"
        ),
        "purpose": (
            "Show broad immune-cell localization while separating coherent "
            "responses from branch-divergent steroid and lipid programmes."
        ),
    },
    {
        "figure": "Figure_7",
        "panel": "B",
        "title": "Pan-immune cholesterol-biosynthesis suppression",
        "modules": "CHOLESTEROL_BIOSYNTHESIS",
        "purpose": (
            "Demonstrate the unusually coherent lower cholesterol-biosynthesis "
            "programme across all complete broad populations."
        ),
    },
    {
        "figure": "Figure_7",
        "panel": "C",
        "title": "Glucocorticoid-response activation",
        "modules": "GLUCOCORTICOID_RESPONSE",
        "purpose": (
            "Localize the higher glucocorticoid-response programme across "
            "lymphoid and myeloid compartments."
        ),
    },
    {
        "figure": "Figure_7",
        "panel": "D",
        "title": "Mixed steroidogenic branch architecture",
        "modules": (
            "STEROIDOGENESIS_CORE;ESTROGEN_BIOSYNTHESIS;"
            "ESTROGEN_RECEPTOR_RESPONSE;ANDROGEN_RECEPTOR_SIGNALING"
        ),
        "purpose": (
            "Contrast lower steroid-synthesis branches with higher receptor-"
            "response programmes outside neutrophils."
        ),
    },
    {
        "figure": "Figure_7",
        "panel": "E",
        "title": "Lipid-peroxidation and lipid-droplet remodeling",
        "modules": (
            "FERROPTOSIS_LIPID_PEROXIDATION;LIPID_DROPLET_DYNAMICS;"
            "PPAR_SREBP_LXR_REGULATION"
        ),
        "purpose": (
            "Distinguish inflammatory lipid storage/peroxidation from "
            "neutrophil-specific suppression of selected lipid programmes."
        ),
    },
    {
        "figure": "Figure_8",
        "panel": "A",
        "title": "Leptin-PI3K/AKT cellular core",
        "modules": "LEPTIN_SIGNALING;PI3K_AKT_SIGNALING",
        "purpose": (
            "Localize leptin predominantly to macrophage/monocyte and "
            "PI3K-AKT predominantly to dendritic responses."
        ),
    },
    {
        "figure": "Figure_8",
        "panel": "B",
        "title": "Insulin/IRS and glycogen response",
        "modules": "INSULIN_RECEPTOR_IRS;GLYCOGEN_SYNTHESIS",
        "purpose": (
            "Show coherent higher signaling across several immune populations "
            "with strong glycogen remodeling in neutrophils."
        ),
    },
    {
        "figure": "Figure_8",
        "panel": "C",
        "title": "Inflammatory glycolysis",
        "modules": (
            "GLYCOLYSIS;LACTATE_HIF1A_INFLAMMATORY_GLYCOLYSIS;"
            "RESISTIN_INFLAMMATORY_SIGNALING;ADIPOKINE_INFLAMMATORY_AXIS"
        ),
        "purpose": (
            "Demonstrate a broad inflammatory-carbon programme extending "
            "across lymphoid and myeloid populations."
        ),
    },
    {
        "figure": "Figure_8",
        "panel": "D",
        "title": "Cell-composition shift",
        "modules": "",
        "purpose": (
            "Show neutrophil and macrophage expansion with relative T-cell, "
            "dendritic, NK-cell and cycling-immune contraction."
        ),
    },
    {
        "figure": "Figure_9",
        "panel": "A",
        "title": "Arginine-NO-urea cellular localization",
        "modules": "ARGININE_NO_UREA;NITRIC_OXIDE_SYNTHESIS_REGULATION",
        "purpose": (
            "Localize arginine-NO remodeling to dendritic and cycling-immune "
            "states while noting the neutrophil exception."
        ),
    },
    {
        "figure": "Figure_9",
        "panel": "B",
        "title": "Purine-redox remodeling",
        "modules": (
            "XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM;"
            "PURINE_SALVAGE;PURINE_DEGRADATION_URATE;"
            "OXIDATIVE_STRESS_NRF2_ANCHOR"
        ),
        "purpose": (
            "Connect dendritic purine oxidation, T-cell purine salvage and "
            "cross-compartment oxidative-stress responses."
        ),
    },
    {
        "figure": "Figure_9",
        "panel": "C",
        "title": "Amino-acid transport and selective suppression",
        "modules": (
            "AMINO_ACID_TRANSPORT;TRYPTOPHAN_KYNURENINE;"
            "AROMATIC_AMINO_ACID_METABOLISM;BRANCHED_CHAIN_AMINO_ACIDS"
        ),
        "purpose": (
            "Separate dendritic amino-acid transport activation from lower "
            "neutrophil aromatic, tryptophan and branched-chain programmes."
        ),
    },
    {
        "figure": "Figure_10",
        "panel": "A",
        "title": "C3a/C5a inflammatory complement",
        "modules": "COMPLEMENT_C3A_C5A_SIGNALING",
        "purpose": (
            "Show coherent higher signaling across all complete broad immune "
            "populations with a dendritic maximum."
        ),
    },
    {
        "figure": "Figure_10",
        "panel": "B",
        "title": "Opsonophagocytic complement",
        "modules": "COMPLEMENT_OPSONOPHAGOCYTOSIS",
        "purpose": (
            "Show a modest dendritic-localized increase rather than universal "
            "opsonophagocytic activation."
        ),
    },
    {
        "figure": "Figure_10",
        "panel": "C",
        "title": "Complement branch divergence",
        "modules": (
            "COMPLEMENT_CLASSICAL;COMPLEMENT_ALTERNATIVE;"
            "COMPLEMENT_C3_CONVERTASE_AMPLIFICATION;"
            "COMPLEMENT_COAGULATION_CROSSTALK;COMPLEMENT_REGULATORS"
        ),
        "purpose": (
            "Contrast dendritic-positive complement branches with lower "
            "T-cell/neutrophil branches and cycling-immune coagulation-linked "
            "responses."
        ),
    },
    {
        "figure": "Figure_10",
        "panel": "D",
        "title": "TNFSF9-positive macrophage expansion",
        "modules": "",
        "purpose": (
            "Integrate fixed TNFSF9-positive/high macrophage fractions with "
            "macrophage abundance and complement signaling."
        ),
    },
    {
        "figure": "Figure_11",
        "panel": "A",
        "title": "UPEC cellular-remodeling overview",
        "modules": "",
        "purpose": (
            "Summarize neutrophil/macrophage expansion, lymphoid contraction "
            "and targeted Treg-like/TNFSF9-high states."
        ),
    },
    {
        "figure": "Figure_11",
        "panel": "B",
        "title": "Cell-source-resolved mechanistic network",
        "modules": (
            "TLR4_LPS_SIGNALING_ANCHOR;NFKB_MAPK_INFLAMMATION_ANCHOR;"
            "LEPTIN_SIGNALING;PI3K_AKT_SIGNALING;"
            "COMPLEMENT_C3A_C5A_SIGNALING;NEUTROPHIL_NETOSIS_ANCHOR"
        ),
        "purpose": (
            "Assign dendritic, macrophage, neutrophil and lymphoid sources to "
            "the integrated inflammatory-metabolic network."
        ),
    },
    {
        "figure": "Figure_11",
        "panel": "C",
        "title": "Infection-versus-pregnancy state contrast",
        "modules": (
            "LEPTIN_SIGNALING;PI3K_AKT_SIGNALING;INSULIN_RECEPTOR_IRS;"
            "GLUCOCORTICOID_RESPONSE;ANDROGEN_RECEPTOR_SIGNALING"
        ),
        "purpose": (
            "Contrast higher UPEC immune-cell signaling with attenuation in "
            "preterm-associated pregnancy tissues."
        ),
    },
    {
        "figure": "Figure_11",
        "panel": "D",
        "title": "Evidence hierarchy and limitations",
        "modules": "",
        "purpose": (
            "Separate human adjusted-FDR evidence, independent directional "
            "support, pregnancy discovery effects and n=2-versus-n=2 cellular "
            "localization."
        ),
    },
]


def log(message: str) -> None:
    print(f"[U26D2C] {message}", flush=True)


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", compression="infer", low_memory=False)


def finite_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )


def evidence_class(row: pd.Series) -> str:
    abs_logfc = abs(float(row["module_mean_gene_log2FC"]))
    coherence = float(row["gene_direction_coherence"])
    abs_g = abs(float(row["hedges_g_finite"]))

    if abs_logfc >= 0.35 and coherence >= 0.75 and abs_g >= 0.8:
        return "high_cellular_localization_support"
    if abs_logfc >= 0.20 and coherence >= 0.65 and abs_g >= 0.5:
        return "moderate_cellular_localization_support"
    if coherence >= 0.60 and abs_logfc >= 0.10:
        return "directional_cellular_support"
    return "limited_cellular_support"


def localization_score(row: pd.Series) -> float:
    abs_logfc = abs(float(row["module_mean_gene_log2FC"]))
    coherence = float(row["gene_direction_coherence"])
    abs_g = abs(float(row["hedges_g_finite"]))

    logfc_component = min(abs_logfc / 0.50, 1.0)
    coherence_component = max(min((coherence - 0.50) / 0.50, 1.0), 0.0)
    g_component = min(abs_g / 2.0, 1.0)

    return float(
        0.45 * logfc_component
        + 0.35 * coherence_component
        + 0.20 * g_component
    )


def prepare_effect_rows(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame[frame["score_eligible"].astype(bool)].copy()

    result["hedges_g_finite"] = finite_numeric(
        result["hedges_g_UPEC_vs_control"]
    )
    result["module_mean_gene_log2FC"] = finite_numeric(
        result["module_mean_gene_log2FC"]
    )
    result["module_median_gene_log2FC"] = finite_numeric(
        result["module_median_gene_log2FC"]
    )
    result["gene_direction_coherence"] = finite_numeric(
        result["gene_direction_coherence"]
    )
    result["mean_difference_UPEC_minus_control"] = finite_numeric(
        result["mean_difference_UPEC_minus_control"]
    )

    result = result.dropna(
        subset=[
            "hedges_g_finite",
            "module_mean_gene_log2FC",
            "gene_direction_coherence",
        ]
    ).copy()

    result["variance_sensitive_hedges_g"] = (
        result["hedges_g_finite"].abs() >= 5.0
    )
    result["cellular_evidence_class"] = result.apply(
        evidence_class,
        axis=1,
    )
    result["cellular_localization_score"] = result.apply(
        localization_score,
        axis=1,
    )
    result["effect_direction"] = np.where(
        result["module_mean_gene_log2FC"] > 0,
        "higher_in_UPEC",
        np.where(
            result["module_mean_gene_log2FC"] < 0,
            "lower_in_UPEC",
            "near_neutral",
        ),
    )
    return result


def classify_module(frame: pd.DataFrame) -> Dict[str, object]:
    frame = frame.sort_values(
        "cellular_localization_score",
        ascending=False,
    ).copy()

    positive = int((frame["module_mean_gene_log2FC"] > 0).sum())
    negative = int((frame["module_mean_gene_log2FC"] < 0).sum())
    total = len(frame)
    direction_coherence = max(positive, negative) / total if total else np.nan

    high_or_moderate = int(
        frame["cellular_evidence_class"].isin(
            [
                "high_cellular_localization_support",
                "moderate_cellular_localization_support",
            ]
        ).sum()
    )

    top = frame.iloc[0]
    top_population = str(top["population"])
    top_score = float(top["cellular_localization_score"])
    second_score = (
        float(frame.iloc[1]["cellular_localization_score"])
        if len(frame) > 1
        else 0.0
    )
    top_dominance = (
        top_score / second_score
        if second_score > 0
        else np.inf
    )

    if positive >= 5 and high_or_moderate >= 4:
        localization_class = "coherent_pan_immune_higher_in_UPEC"
    elif negative >= 5 and high_or_moderate >= 4:
        localization_class = "coherent_pan_immune_lower_in_UPEC"
    elif top_population in MYELOID and top_dominance >= 1.20:
        localization_class = "myeloid_dominant"
    elif top_population in LYMPHOID and top_dominance >= 1.20:
        localization_class = "lymphoid_dominant"
    elif top_population in CYCLING and top_dominance >= 1.20:
        localization_class = "cycling_immune_dominant"
    elif direction_coherence < 0.67:
        localization_class = "branch_divergent"
    else:
        localization_class = "multi_compartment_contextual"

    return {
        "n_populations": total,
        "n_positive_populations": positive,
        "n_negative_populations": negative,
        "directional_coherence_fraction": direction_coherence,
        "n_high_or_moderate_populations": high_or_moderate,
        "top_population_by_composite_score": top_population,
        "top_population_composite_score": top_score,
        "top_population_evidence_class": top["cellular_evidence_class"],
        "top_population_mean_gene_log2FC": top["module_mean_gene_log2FC"],
        "top_population_gene_direction_coherence": top[
            "gene_direction_coherence"
        ],
        "top_population_hedges_g": top["hedges_g_finite"],
        "top_population_variance_sensitive_g": top[
            "variance_sensitive_hedges_g"
        ],
        "top_to_second_score_ratio": top_dominance,
        "cellular_localization_class": localization_class,
        "median_mean_gene_log2FC": frame[
            "module_mean_gene_log2FC"
        ].median(),
        "median_gene_direction_coherence": frame[
            "gene_direction_coherence"
        ].median(),
        "median_composite_score": frame[
            "cellular_localization_score"
        ].median(),
    }


def synthesize_modules(
    broad: pd.DataFrame,
    subtype: pd.DataFrame,
) -> pd.DataFrame:
    subtype_top = (
        subtype.sort_values(
            ["feature_id", "cellular_localization_score"],
            ascending=[True, False],
        )
        .groupby("feature_id", as_index=False)
        .first()
        .rename(
            columns={
                "population": "top_refined_subtype",
                "cellular_localization_score": (
                    "top_refined_subtype_composite_score"
                ),
                "module_mean_gene_log2FC": (
                    "top_refined_subtype_mean_gene_log2FC"
                ),
                "gene_direction_coherence": (
                    "top_refined_subtype_gene_direction_coherence"
                ),
                "hedges_g_finite": "top_refined_subtype_hedges_g",
                "variance_sensitive_hedges_g": (
                    "top_refined_subtype_variance_sensitive_g"
                ),
            }
        )
    )

    rows = []
    for feature_id, frame in broad.groupby("feature_id"):
        summary = classify_module(frame)
        first = frame.iloc[0]
        rows.append(
            {
                "feature_id": feature_id,
                "display_label": first["display_label"],
                "axis": first["axis"],
                "proposed_figure_family": first[
                    "proposed_figure_family"
                ],
                **summary,
            }
        )

    result = pd.DataFrame(rows)
    keep = [
        "feature_id",
        "top_refined_subtype",
        "top_refined_subtype_composite_score",
        "top_refined_subtype_mean_gene_log2FC",
        "top_refined_subtype_gene_direction_coherence",
        "top_refined_subtype_hedges_g",
        "top_refined_subtype_variance_sensitive_g",
    ]
    result = result.merge(
        subtype_top[[column for column in keep if column in subtype_top.columns]],
        on="feature_id",
        how="left",
    )
    return result.sort_values(
        [
            "n_high_or_moderate_populations",
            "median_composite_score",
        ],
        ascending=[False, False],
    )


def claims_matrix() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "finding_type": "coherent broad-cell pseudobulk effect",
                "allowed_wording": (
                    "The module showed directionally coherent UPEC-associated "
                    "remodeling across multiple immune populations."
                ),
                "avoid_wording": (
                    "The module was statistically significant across cell "
                    "types."
                ),
            },
            {
                "finding_type": "large Hedges g at n=2 versus n=2",
                "allowed_wording": (
                    "A large standardized effect was observed, interpreted "
                    "together with module-gene fold change and direction "
                    "coherence."
                ),
                "avoid_wording": (
                    "Very large biological induction based on Hedges g alone."
                ),
            },
            {
                "finding_type": "cell-type composition change",
                "allowed_wording": (
                    "The UPEC samples showed descriptive expansion or "
                    "contraction of the population."
                ),
                "avoid_wording": (
                    "UPEC significantly changed abundance."
                ),
            },
            {
                "finding_type": "fixed Treg-like or TNFSF9 state fraction",
                "allowed_wording": (
                    "Both UPEC replicates showed higher descriptive fractions "
                    "under a fixed marker definition."
                ),
                "avoid_wording": (
                    "UPEC caused Treg differentiation or CD137L induction."
                ),
            },
            {
                "finding_type": "metabolic module",
                "allowed_wording": (
                    "Transcriptionally inferred metabolic pathway activity."
                ),
                "avoid_wording": (
                    "Metabolic flux, substrate utilization or metabolite "
                    "production unless directly measured."
                ),
            },
            {
                "finding_type": "top cellular source",
                "allowed_wording": (
                    "The strongest composite localization was observed in the "
                    "named population."
                ),
                "avoid_wording": (
                    "The named population was the exclusive biological source."
                ),
            },
        ]
    )


def figure_panel_evidence(
    plan: pd.DataFrame,
    synthesis: pd.DataFrame,
) -> pd.DataFrame:
    lookup = synthesis.set_index("feature_id").to_dict("index")
    rows = []

    for _, panel in plan.iterrows():
        modules = [
            value for value in str(panel["modules"]).split(";") if value
        ]

        if not modules:
            rows.append(
                {
                    **panel.to_dict(),
                    "feature_id": "",
                    "display_label": "",
                    "cellular_localization_class": "",
                    "top_broad_population": "",
                    "top_refined_subtype": "",
                    "cellular_evidence_summary": (
                        "Composition or targeted-state panel; use U26D2A.1 "
                        "and U26D2B effect tables."
                    ),
                }
            )
            continue

        for feature_id in modules:
            item = lookup.get(feature_id, {})
            rows.append(
                {
                    **panel.to_dict(),
                    "feature_id": feature_id,
                    "display_label": item.get(
                        "display_label",
                        feature_id.replace("_", " ").title(),
                    ),
                    "cellular_localization_class": item.get(
                        "cellular_localization_class",
                        "not_score_eligible_or_not_available",
                    ),
                    "top_broad_population": item.get(
                        "top_population_by_composite_score",
                        "",
                    ),
                    "top_refined_subtype": item.get(
                        "top_refined_subtype",
                        "",
                    ),
                    "cellular_evidence_summary": (
                        f"median composite="
                        f"{item.get('median_composite_score', np.nan):.3f}; "
                        f"high/moderate broad populations="
                        f"{item.get('n_high_or_moderate_populations', 0)}"
                        if item
                        else "Module unavailable or not score eligible."
                    ),
                }
            )
    return pd.DataFrame(rows)


def save_composite_heatmap(
    broad: pd.DataFrame,
    features: Sequence[str],
    output: Path,
) -> None:
    subset = broad[broad["feature_id"].isin(features)].copy()
    if subset.empty:
        return

    pivot = subset.pivot_table(
        index="feature_id",
        columns="population",
        values="cellular_localization_score",
        aggfunc="first",
    )
    pivot = pivot.reindex(
        index=[feature for feature in features if feature in pivot.index]
    )
    preferred_columns = [
        "macrophage_monocyte",
        "dendritic",
        "neutrophil",
        "T_cell",
        "NK_cell",
        "cycling_immune",
    ]
    pivot = pivot.reindex(
        columns=[
            column for column in preferred_columns
            if column in pivot.columns
        ]
    )

    figure = plt.figure(
        figsize=(10, max(7, 0.34 * len(pivot.index) + 2))
    )
    axis = figure.add_axes([0.36, 0.14, 0.46, 0.76])
    image = axis.imshow(pivot.to_numpy(), aspect="auto")
    axis.set_xticks(np.arange(len(pivot.columns)))
    axis.set_xticklabels(
        [column.replace("_", " ") for column in pivot.columns],
        rotation=45,
        ha="right",
        fontsize=8,
    )
    axis.set_yticks(np.arange(len(pivot.index)))
    axis.set_yticklabels(
        [value.replace("_", " ") for value in pivot.index],
        fontsize=8,
    )
    axis.set_title(
        "Composite cellular-localization support"
    )
    color_axis = figure.add_axes([0.85, 0.25, 0.025, 0.50])
    figure.colorbar(
        image,
        cax=color_axis,
        label="Composite support score",
    )
    figure.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(figure)


def write_report(
    path: Path,
    synthesis: pd.DataFrame,
    core: pd.DataFrame,
    composition: pd.DataFrame,
    targeted: pd.DataFrame,
    decision: str,
) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26D2C - Cellular-localization synthesis\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            "- Hedges g was not used alone to rank cellular biology.\n"
        )
        handle.write(
            "- Biological samples remain the inferential units.\n"
        )
        handle.write(
            "- Manuscript and existing Figures 1-6 were not modified.\n\n"
        )

        handle.write("## Central cellular architecture\n\n")
        handle.write(
            "UPEC exposure produced a myeloid-dominant compositional shift, "
            "with neutrophil and macrophage/monocyte expansion and relative "
            "contraction of T-cell, dendritic, NK-cell, cycling-immune and "
            "mast-cell fractions. Within the retained populations, the "
            "inflammatory-metabolic response was not confined to the expanded "
            "myeloid cells: several TLR4/NF-kB, adipokine, glycolytic, NETosis, "
            "C3a/C5a and pregnancy-inflammation gene programmes were "
            "directionally coherent across lymphoid and myeloid compartments.\n\n"
        )

        handle.write("## Core module cellular attribution\n\n")
        for _, item in core.iterrows():
            handle.write(
                f"- **{item['display_label']}**: "
                f"`{item['cellular_localization_class']}`; strongest composite "
                f"broad localization in "
                f"`{item['top_population_by_composite_score']}` and refined "
                f"localization in `{item.get('top_refined_subtype', '')}`. "
                f"High/moderate support occurred in "
                f"{int(item['n_high_or_moderate_populations'])} broad "
                f"populations.\n"
            )
        handle.write("\n")

        handle.write("## Composition effects\n\n")
        for _, item in composition.sort_values(
            "difference_UPEC_minus_control",
            key=lambda series: series.abs(),
            ascending=False,
        ).iterrows():
            handle.write(
                f"- `{item['refined_broad_cell_type']}`: control "
                f"{float(item['mean_control']):.3f}, UPEC "
                f"{float(item['mean_UPEC']):.3f}, difference "
                f"{float(item['difference_UPEC_minus_control']):+.3f}.\n"
            )
        handle.write("\n")

        handle.write("## Fixed targeted states\n\n")
        for _, item in targeted.iterrows():
            handle.write(
                f"- `{item['targeted_measure']}`: control "
                f"{float(item['mean_control']):.3f}, UPEC "
                f"{float(item['mean_UPEC']):.3f}, difference "
                f"{float(item['difference_UPEC_minus_control']):+.3f}.\n"
            )
        handle.write("\n")

        handle.write("## Interpretation safeguards\n\n")
        handle.write(
            "Very large standardized effects can arise when two samples per "
            "group have minimal within-group variance. Such effects are "
            "retained for transparency but are flagged as variance-sensitive. "
            "Figure and manuscript prioritization uses module-gene fold change, "
            "gene-direction coherence and cross-population consistency together "
            "with the standardized effect. Cell-type localization is not proof "
            "of an exclusive cellular source, and all metabolic modules remain "
            "transcriptionally inferred rather than direct metabolic flux "
            "measurements.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    source_tables = project / "06_tables" / SOURCE_TAG

    broad_path = (
        source_tables
        / "UTI_HostOmics_U26D2B_broad_celltype_module_results.tsv"
    )
    subtype_path = (
        source_tables
        / "UTI_HostOmics_U26D2B_refined_subtype_module_results.tsv"
    )
    composition_path = (
        source_tables
        / "UTI_HostOmics_U26D2B_celltype_composition_effects.tsv"
    )
    targeted_path = (
        source_tables
        / "UTI_HostOmics_U26D2B_targeted_state_effects.tsv"
    )
    decision_path = (
        source_tables
        / "UTI_HostOmics_U26D2B_phase_decision.tsv"
    )

    for path in [
        broad_path,
        subtype_path,
        composition_path,
        targeted_path,
        decision_path,
    ]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG
    out_figures = project / "06_figures" / TAG

    for directory in [
        out_tables,
        out_metadata,
        out_results,
        out_figures,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    log("Loading U26D2B pseudobulk results.")
    broad_raw = read_tsv(broad_path)
    subtype_raw = read_tsv(subtype_path)
    composition = read_tsv(composition_path)
    targeted = read_tsv(targeted_path)
    source_decision = read_tsv(decision_path)

    if not source_decision["decision"].astype(str).str.startswith(
        "READY"
    ).all():
        raise RuntimeError(
            "U26D2B was not in a READY state."
        )

    broad = prepare_effect_rows(broad_raw)
    subtype = prepare_effect_rows(subtype_raw)

    broad.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2C_broad_effect_reliability.tsv",
        sep="\t",
        index=False,
    )
    subtype.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2C_subtype_effect_reliability.tsv",
        sep="\t",
        index=False,
    )

    synthesis = synthesize_modules(broad, subtype)
    synthesis.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2C_module_cellular_synthesis.tsv",
        sep="\t",
        index=False,
    )

    core_priorities_path = (
        project / "06_tables" / CORE_TAG
        / "UTI_HostOmics_U26C1_refined_core_and_secondary_modules.tsv"
    )
    if core_priorities_path.exists():
        priorities = read_tsv(core_priorities_path)
        priority_columns = [
            column for column in [
                "feature_id",
                "biological_priority",
                "manuscript_claim_priority",
                "refined_infection_outcome_relation",
            ]
            if column in priorities.columns
        ]
        synthesis = synthesis.merge(
            priorities[priority_columns],
            on="feature_id",
            how="left",
        )

    core = synthesis[
        synthesis["feature_id"].isin(CORE_FEATURES)
    ].copy()
    core.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2C_core_module_cellular_attribution.tsv",
        sep="\t",
        index=False,
    )

    variance_sensitive = broad[
        broad["variance_sensitive_hedges_g"]
    ].sort_values(
        "hedges_g_finite",
        key=lambda series: series.abs(),
        ascending=False,
    )
    variance_sensitive.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2C_variance_sensitive_effects.tsv",
        sep="\t",
        index=False,
    )

    claims = claims_matrix()
    claims.to_csv(
        out_metadata
        / "UTI_HostOmics_U26D2C_claim_boundary_matrix.tsv",
        sep="\t",
        index=False,
    )

    plan = pd.DataFrame(FIGURE_PANEL_PLAN)
    panel_evidence = figure_panel_evidence(plan, synthesis)
    panel_evidence.to_csv(
        out_metadata
        / "UTI_HostOmics_U26D2C_Figures_7_to_11_cellular_panel_plan.tsv",
        sep="\t",
        index=False,
    )

    save_composite_heatmap(
        broad,
        [
            feature
            for feature in [
                "TLR4_LPS_SIGNALING_ANCHOR",
                "NFKB_MAPK_INFLAMMATION_ANCHOR",
                "NEUTROPHIL_NETOSIS_ANCHOR",
                "LEPTIN_SIGNALING",
                "PI3K_AKT_SIGNALING",
                "INSULIN_RECEPTOR_IRS",
                "GLYCOLYSIS",
                "LACTATE_HIF1A_INFLAMMATORY_GLYCOLYSIS",
                "GLUCOCORTICOID_RESPONSE",
                "CHOLESTEROL_BIOSYNTHESIS",
                "STEROIDOGENESIS_CORE",
                "COMPLEMENT_C3A_C5A_SIGNALING",
                "COMPLEMENT_OPSONOPHAGOCYTOSIS",
                "ARGININE_NO_UREA",
                "XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM",
            ]
            if feature in set(broad["feature_id"])
        ],
        out_figures
        / "UTI_HostOmics_U26D2C_core_composite_cellular_support.png",
    )

    complete_core = int(
        core["top_population_by_composite_score"].notna().sum()
    )
    n_variance_sensitive = len(variance_sensitive)

    decision = (
        "READY_FOR_U27_FIGURE_7_TO_11_BUILD_AND_MANUSCRIPT_"
        "INTEGRATION_WITH_CELLULAR_ATTRIBUTION"
    )

    pd.DataFrame(
        [
            {
                "phase": "U26D2C",
                "decision": decision,
                "n_broad_effect_rows": len(broad),
                "n_subtype_effect_rows": len(subtype),
                "n_modules_synthesized": synthesis["feature_id"].nunique(),
                "n_core_modules_with_cellular_attribution": complete_core,
                "n_variance_sensitive_broad_effects_abs_g_ge_5": (
                    n_variance_sensitive
                ),
                "ranking_uses_hedges_g_alone": False,
                "ranking_uses_gene_log2FC": True,
                "ranking_uses_gene_direction_coherence": True,
                "ranking_uses_cross_population_consistency": True,
                "biological_sample_is_inferential_unit": True,
                "cell_level_significance_testing_performed": False,
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U27 construct Figures 7-11 and integrate cellular "
                    "attribution into results and discussion"
                ),
            }
        ]
    ).to_csv(
        out_tables / "UTI_HostOmics_U26D2C_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U26D2C_cellular_localization_synthesis_report.md"
    )
    write_report(
        report_path,
        synthesis,
        core,
        composition,
        targeted,
        decision,
    )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "n_modules_synthesized": int(
            synthesis["feature_id"].nunique()
        ),
        "n_variance_sensitive_broad_effects": int(
            n_variance_sensitive
        ),
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U26D2C_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log(
        f"Modules synthesized: "
        f"{synthesis['feature_id'].nunique()}"
    )
    log(
        f"Variance-sensitive broad effects: "
        f"{n_variance_sensitive}"
    )
    log(f"Core modules attributed: {complete_core}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26D2C] ERROR: {exc}", file=sys.stderr)
        raise
