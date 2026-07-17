#!/usr/bin/env python3
"""
Phase U26B1.1
Stability-aware refinement of GSE280297 endocrine-metabolic-immune results.

This phase:
- keeps C1, C2, and C3 as primary biological contrasts;
- keeps C4 (UTI89-RFP vs UTI89 term) as secondary exploratory only;
- recalculates adaptive exact/Monte-Carlo permutation p values;
- controls FDR within each primary contrast and within each figure family;
- builds axis-level aggregate scores and permutation tests;
- creates primary-only, stability-aware Figure 7-10 rankings;
- suppresses unreliable effect-size confidence intervals for groups with n < 4;
- does not alter the manuscript or existing Figures 1-6.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit(
        "ERROR: matplotlib is required. Install with conda or pip."
    ) from exc

VERSION = "U26B1.1_v1.0_2026-07-14"
PHASE_TAG = "phaseU26B1_1_GSE280297_stability_refinement"
RANDOM_SEED = 2611

PRIMARY_CONTRASTS = {
    "C1_PRETERM_VS_TERM",
    "C2_UPEC_VS_PBS_PREGNANCY",
    "C3_INFECTED_PREGNANT_VS_NONPREGNANT",
}
EXPLORATORY_CONTRASTS = {
    "C4_UTI89_RFP_VS_UTI89_TERM",
}


def log(message: str) -> None:
    print(f"[U26B1.1] {message}", flush=True)


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        compression="infer",
        low_memory=False,
    )


def bh_fdr(values: Sequence[float]) -> np.ndarray:
    p_values = np.asarray(values, dtype=float)
    output = np.full(p_values.shape, np.nan)

    finite = np.where(np.isfinite(p_values))[0]
    if len(finite) == 0:
        return output

    observed = p_values[finite]
    order = np.argsort(observed)
    ranked = observed[order]
    n = len(ranked)

    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)

    restored = np.empty(n)
    restored[order] = adjusted
    output[finite] = restored
    return output


def adaptive_permutation_p(
    group_a: np.ndarray,
    group_b: np.ndarray,
    rng: np.random.Generator,
    max_exact: int,
    monte_carlo_iterations: int,
) -> Tuple[float, str, int]:
    group_a = np.asarray(group_a, dtype=float)
    group_b = np.asarray(group_b, dtype=float)
    group_a = group_a[np.isfinite(group_a)]
    group_b = group_b[np.isfinite(group_b)]

    n_a = len(group_a)
    n_b = len(group_b)
    if n_a < 2 or n_b < 2:
        return float("nan"), "unavailable", 0

    pooled = np.concatenate([group_a, group_b])
    observed = abs(float(np.mean(group_a) - np.mean(group_b)))
    n_total = len(pooled)
    n_combinations = math.comb(n_total, n_a)

    if n_combinations <= max_exact:
        extreme = 0
        total = 0
        all_indices = np.arange(n_total)

        for selected_tuple in itertools.combinations(range(n_total), n_a):
            selected = np.fromiter(
                selected_tuple,
                dtype=int,
                count=n_a,
            )
            mask = np.ones(n_total, dtype=bool)
            mask[selected] = False
            complement = all_indices[mask]

            statistic = abs(
                float(
                    np.mean(pooled[selected])
                    - np.mean(pooled[complement])
                )
            )
            extreme += int(statistic >= observed - 1e-12)
            total += 1

        return (
            float(extreme / total),
            "exact",
            total,
        )

    extreme = 0
    for _ in range(monte_carlo_iterations):
        permutation = rng.permutation(n_total)
        selected = permutation[:n_a]
        complement = permutation[n_a:]
        statistic = abs(
            float(
                np.mean(pooled[selected])
                - np.mean(pooled[complement])
            )
        )
        extreme += int(statistic >= observed - 1e-12)

    p_value = (
        extreme + 1
    ) / (
        monte_carlo_iterations + 1
    )

    return (
        float(p_value),
        "monte_carlo",
        monte_carlo_iterations,
    )


def contrast_masks(
    scores: pd.DataFrame,
    contrast_id: str,
    tissue: str,
) -> Tuple[pd.Series, pd.Series, str, str]:
    tissue_mask = scores["tissue"].astype(str) == str(tissue)

    if contrast_id == "C1_PRETERM_VS_TERM":
        group_a = (
            tissue_mask
            & (scores["treatment"] == "UTI89")
            & (scores["outcome"] == "preterm")
        )
        group_b = (
            tissue_mask
            & (scores["treatment"] == "UTI89")
            & (scores["outcome"] == "term")
        )
        return group_a, group_b, "UTI89_preterm", "UTI89_term"

    if contrast_id == "C2_UPEC_VS_PBS_PREGNANCY":
        group_a = (
            tissue_mask
            & scores["pregnancy_status"].isin(
                ["pregnant", "pregnant_control"]
            )
            & (scores["primary_exposure"] == "UPEC_exposed")
        )
        group_b = (
            tissue_mask
            & (scores["pregnancy_status"] == "pregnant_control")
            & (scores["primary_exposure"] == "control")
        )
        return (
            group_a,
            group_b,
            "UPEC_exposed_pregnancy",
            "PBS_pregnancy_control",
        )

    if contrast_id == "C3_INFECTED_PREGNANT_VS_NONPREGNANT":
        group_a = (
            tissue_mask
            & (scores["treatment"] == "UTI89")
            & (scores["pregnancy_status"] == "pregnant")
        )
        group_b = (
            tissue_mask
            & (scores["treatment"] == "UTI89")
            & (scores["pregnancy_status"] == "nonpregnant")
        )
        return (
            group_a,
            group_b,
            "UTI89_pregnant",
            "UTI89_nonpregnant",
        )

    if contrast_id == "C4_UTI89_RFP_VS_UTI89_TERM":
        term_mask = tissue_mask & (scores["outcome"] == "term")
        group_a = term_mask & (scores["treatment"] == "UTI89_RFP")
        group_b = term_mask & (scores["treatment"] == "UTI89")
        return (
            group_a,
            group_b,
            "UTI89_RFP_term",
            "UTI89_term",
        )

    raise ValueError(f"Unknown contrast: {contrast_id}")


def stability_class(
    n_group_a: int,
    n_group_b: int,
    analysis_status: str,
) -> str:
    minimum = min(n_group_a, n_group_b)

    if analysis_status == "secondary_exploratory":
        return "exploratory_tiny_group"

    if minimum >= 6:
        return "moderate_stability"
    if minimum >= 4:
        return "limited_stability"
    if minimum >= 3:
        return "small_group"
    return "exploratory_tiny_group"


def add_permutation_statistics(
    results: pd.DataFrame,
    scores: pd.DataFrame,
    max_exact: int,
    monte_carlo_iterations: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    refined_rows = []

    for _, row in results.iterrows():
        contrast_id = str(row["contrast_id"])
        tissue = str(row["tissue"])
        feature_id = str(row["feature_id"])

        group_a_mask, group_b_mask, _, _ = contrast_masks(
            scores,
            contrast_id,
            tissue,
        )

        if feature_id not in scores.columns:
            permutation_p = float("nan")
            method = "feature_missing"
            n_permutations = 0
        else:
            group_a = pd.to_numeric(
                scores.loc[group_a_mask, feature_id],
                errors="coerce",
            ).to_numpy(dtype=float)
            group_b = pd.to_numeric(
                scores.loc[group_b_mask, feature_id],
                errors="coerce",
            ).to_numpy(dtype=float)

            permutation_p, method, n_permutations = (
                adaptive_permutation_p(
                    group_a,
                    group_b,
                    rng,
                    max_exact=max_exact,
                    monte_carlo_iterations=monte_carlo_iterations,
                )
            )

        output = row.to_dict()
        output["evidence_tier"] = (
            "primary"
            if contrast_id in PRIMARY_CONTRASTS
            else "secondary_exploratory"
        )
        output["stability_class"] = stability_class(
            int(row["n_group_a"]),
            int(row["n_group_b"]),
            str(row["analysis_status"]),
        )
        output["permutation_p_value"] = permutation_p
        output["permutation_method"] = method
        output["n_permutations"] = n_permutations

        if min(
            int(row["n_group_a"]),
            int(row["n_group_b"]),
        ) < 4:
            output["stable_hedges_g_ci_low"] = np.nan
            output["stable_hedges_g_ci_high"] = np.nan
            output["effect_ci_status"] = (
                "suppressed_min_group_below_4"
            )
        else:
            output["stable_hedges_g_ci_low"] = row[
                "hedges_g_ci_low"
            ]
            output["stable_hedges_g_ci_high"] = row[
                "hedges_g_ci_high"
            ]
            output["effect_ci_status"] = "retained"

        refined_rows.append(output)

    refined = pd.DataFrame(refined_rows)

    refined["permutation_q_within_contrast"] = np.nan
    refined["permutation_q_within_family"] = np.nan

    for (_, _), indices in refined.groupby(
        ["contrast_id", "tissue"]
    ).groups.items():
        index_list = list(indices)
        refined.loc[
            index_list,
            "permutation_q_within_contrast",
        ] = bh_fdr(
            refined.loc[
                index_list,
                "permutation_p_value",
            ].to_numpy(dtype=float)
        )

    for (_, _, _), indices in refined.groupby(
        [
            "contrast_id",
            "tissue",
            "proposed_figure_family",
        ]
    ).groups.items():
        index_list = list(indices)
        refined.loc[
            index_list,
            "permutation_q_within_family",
        ] = bh_fdr(
            refined.loc[
                index_list,
                "permutation_p_value",
            ].to_numpy(dtype=float)
        )

    refined["permutation_fdr_0_05"] = (
        refined["permutation_q_within_contrast"] < 0.05
    )
    refined["permutation_fdr_0_10"] = (
        refined["permutation_q_within_contrast"] < 0.10
    )
    refined["family_fdr_0_10"] = (
        refined["permutation_q_within_family"] < 0.10
    )

    return refined


def build_axis_scores(
    scores: pd.DataFrame,
    feature_metadata: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    modules = feature_metadata[
        feature_metadata["feature_type"] == "submodule"
    ].copy()

    axis_map = (
        modules.groupby("axis")["feature_id"]
        .apply(list)
        .to_dict()
    )

    axis_scores = scores[
        [
            "sample_id",
            "tissue",
            "treatment",
            "primary_exposure",
            "outcome",
            "pregnancy_status",
            "sex",
            "inferred_group",
        ]
    ].copy()

    definition_rows = []

    for axis, features in sorted(axis_map.items()):
        available = [
            feature
            for feature in features
            if feature in scores.columns
        ]

        if not available:
            continue

        axis_id = f"AXIS__{axis}"
        axis_scores[axis_id] = scores[available].mean(axis=1)

        definition_rows.append(
            {
                "axis_score_id": axis_id,
                "axis": axis,
                "n_requested_submodules": len(features),
                "n_available_submodules": len(available),
                "available_submodules": ";".join(available),
            }
        )

    return axis_scores, pd.DataFrame(definition_rows)


def axis_permutation_tests(
    axis_scores: pd.DataFrame,
    axis_definitions: pd.DataFrame,
    primary_contrast_pairs: pd.DataFrame,
    max_exact: int,
    monte_carlo_iterations: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED + 1)
    rows = []

    for _, contrast in primary_contrast_pairs.iterrows():
        contrast_id = str(contrast["contrast_id"])
        tissue = str(contrast["tissue"])

        group_a_mask, group_b_mask, group_a_label, group_b_label = (
            contrast_masks(
                axis_scores,
                contrast_id,
                tissue,
            )
        )

        for _, definition in axis_definitions.iterrows():
            axis_id = str(definition["axis_score_id"])
            a = pd.to_numeric(
                axis_scores.loc[group_a_mask, axis_id],
                errors="coerce",
            ).to_numpy(dtype=float)
            b = pd.to_numeric(
                axis_scores.loc[group_b_mask, axis_id],
                errors="coerce",
            ).to_numpy(dtype=float)
            a = a[np.isfinite(a)]
            b = b[np.isfinite(b)]

            if len(a) < 2 or len(b) < 2:
                continue

            p_value, method, n_permutations = adaptive_permutation_p(
                a,
                b,
                rng,
                max_exact=max_exact,
                monte_carlo_iterations=monte_carlo_iterations,
            )

            pooled_sd = np.sqrt(
                (
                    (len(a) - 1) * np.var(a, ddof=1)
                    + (len(b) - 1) * np.var(b, ddof=1)
                )
                / (len(a) + len(b) - 2)
            )
            if pooled_sd > 0:
                d = (np.mean(a) - np.mean(b)) / pooled_sd
                correction = (
                    1
                    - 3
                    / (4 * (len(a) + len(b)) - 9)
                )
                effect = float(correction * d)
            else:
                effect = 0.0

            rows.append(
                {
                    "contrast_id": contrast_id,
                    "tissue": tissue,
                    "group_a": group_a_label,
                    "group_b": group_b_label,
                    "axis": definition["axis"],
                    "axis_score_id": axis_id,
                    "n_group_a": len(a),
                    "n_group_b": len(b),
                    "mean_group_a": float(np.mean(a)),
                    "mean_group_b": float(np.mean(b)),
                    "mean_difference_a_minus_b": float(
                        np.mean(a) - np.mean(b)
                    ),
                    "hedges_g": effect,
                    "permutation_p_value": p_value,
                    "permutation_method": method,
                    "n_permutations": n_permutations,
                    "stability_class": stability_class(
                        len(a),
                        len(b),
                        "primary",
                    ),
                }
            )

    axis_results = pd.DataFrame(rows)
    axis_results["permutation_q_within_contrast"] = np.nan

    for (_, _), indices in axis_results.groupby(
        ["contrast_id", "tissue"]
    ).groups.items():
        index_list = list(indices)
        axis_results.loc[
            index_list,
            "permutation_q_within_contrast",
        ] = bh_fdr(
            axis_results.loc[
                index_list,
                "permutation_p_value",
            ].to_numpy(dtype=float)
        )

    axis_results["fdr_0_05"] = (
        axis_results["permutation_q_within_contrast"] < 0.05
    )
    axis_results["fdr_0_10"] = (
        axis_results["permutation_q_within_contrast"] < 0.10
    )

    return axis_results


def primary_ranking(
    refined: pd.DataFrame,
) -> pd.DataFrame:
    primary = refined[
        (refined["evidence_tier"] == "primary")
        & (refined["feature_type"] == "submodule")
    ].copy()

    primary["large_effect"] = (
        np.abs(primary["hedges_g"]) >= 0.80
    )
    primary["moderate_effect"] = (
        np.abs(primary["hedges_g"]) >= 0.50
    )
    primary["stable_result"] = (
        primary["stability_class"]
        != "exploratory_tiny_group"
    )

    stable = primary[primary["stable_result"]].copy()

    ranking = (
        stable.groupby(
            [
                "proposed_figure_family",
                "axis",
                "feature_id",
                "display_label",
            ],
            dropna=False,
        )
        .agg(
            max_absolute_hedges_g_primary=(
                "hedges_g",
                lambda x: float(np.nanmax(np.abs(x))),
            ),
            median_absolute_hedges_g_primary=(
                "hedges_g",
                lambda x: float(np.nanmedian(np.abs(x))),
            ),
            n_primary_results=("feature_id", "count"),
            n_large_primary_effects=("large_effect", "sum"),
            n_moderate_primary_effects=("moderate_effect", "sum"),
            n_permutation_FDR_0_05=(
                "permutation_fdr_0_05",
                "sum",
            ),
            n_permutation_FDR_0_10=(
                "permutation_fdr_0_10",
                "sum",
            ),
            n_family_FDR_0_10=("family_fdr_0_10", "sum"),
        )
        .reset_index()
    )

    ranking["primary_evidence_score"] = (
        ranking["max_absolute_hedges_g_primary"]
        + 0.5 * ranking["median_absolute_hedges_g_primary"]
        + 0.5 * ranking["n_large_primary_effects"]
        + 0.2 * ranking["n_moderate_primary_effects"]
        + 3.0 * ranking["n_permutation_FDR_0_05"]
        + 1.5 * ranking["n_permutation_FDR_0_10"]
        + 0.5 * ranking["n_family_FDR_0_10"]
    )

    ranking["evidence_class"] = np.select(
        [
            ranking["n_permutation_FDR_0_05"] > 0,
            ranking["n_permutation_FDR_0_10"] > 0,
            ranking["n_large_primary_effects"] >= 2,
            ranking["n_large_primary_effects"] == 1,
            ranking["n_moderate_primary_effects"] >= 2,
        ],
        [
            "primary_FDR_supported",
            "primary_FDR10_supported",
            "recurrent_large_effect",
            "single_large_effect",
            "recurrent_moderate_effect",
        ],
        default="weak_or_context_specific",
    )

    return ranking.sort_values(
        [
            "proposed_figure_family",
            "primary_evidence_score",
        ],
        ascending=[True, False],
    )


def cross_tissue_coherence(
    refined: pd.DataFrame,
) -> pd.DataFrame:
    primary = refined[
        (refined["evidence_tier"] == "primary")
        & (refined["feature_type"] == "submodule")
        & refined["contrast_id"].isin(
            [
                "C1_PRETERM_VS_TERM",
                "C2_UPEC_VS_PBS_PREGNANCY",
            ]
        )
    ].copy()

    rows = []

    for (
        contrast_id,
        feature_id,
        axis,
        label,
        figure_family,
    ), group in primary.groupby(
        [
            "contrast_id",
            "feature_id",
            "axis",
            "display_label",
            "proposed_figure_family",
        ]
    ):
        effects = group["hedges_g"].dropna().to_numpy(dtype=float)
        if len(effects) == 0:
            continue

        positive = int(np.sum(effects > 0))
        negative = int(np.sum(effects < 0))
        dominant = max(positive, negative)
        coherence = dominant / len(effects)

        rows.append(
            {
                "contrast_id": contrast_id,
                "feature_id": feature_id,
                "axis": axis,
                "display_label": label,
                "proposed_figure_family": figure_family,
                "n_tissues": len(effects),
                "n_positive_tissues": positive,
                "n_negative_tissues": negative,
                "directional_coherence_fraction": coherence,
                "dominant_direction": (
                    "positive"
                    if positive > negative
                    else "negative"
                    if negative > positive
                    else "mixed"
                ),
                "median_hedges_g": float(np.median(effects)),
                "mean_absolute_hedges_g": float(
                    np.mean(np.abs(effects))
                ),
            }
        )

    return pd.DataFrame(rows)


def primary_effect_matrix(
    refined: pd.DataFrame,
    family: str,
) -> pd.DataFrame:
    subset = refined[
        (refined["evidence_tier"] == "primary")
        & (refined["feature_type"] == "submodule")
        & (refined["proposed_figure_family"] == family)
    ].copy()

    if subset.empty:
        return pd.DataFrame()

    subset["contrast_tissue"] = (
        subset["contrast_id"].astype(str)
        + " | "
        + subset["tissue"].astype(str)
    )

    return subset.pivot_table(
        index="feature_id",
        columns="contrast_tissue",
        values="hedges_g",
        aggfunc="first",
    )


def save_heatmap(
    matrix: pd.DataFrame,
    output_stem: Path,
    title: str,
) -> None:
    if matrix.empty:
        return

    width = max(9.0, 1.1 * len(matrix.columns) + 4.0)
    height = max(5.0, 0.35 * len(matrix.index) + 2.5)

    figure = plt.figure(figsize=(width, height))
    axis = figure.add_axes([0.30, 0.18, 0.58, 0.68])

    image = axis.imshow(
        matrix.to_numpy(dtype=float),
        aspect="auto",
    )
    axis.set_xticks(np.arange(len(matrix.columns)))
    axis.set_xticklabels(
        matrix.columns,
        rotation=55,
        ha="right",
        fontsize=8,
    )
    axis.set_yticks(np.arange(len(matrix.index)))
    axis.set_yticklabels(matrix.index, fontsize=8)
    axis.set_title(title)
    axis.set_xlabel("Primary contrast and tissue")
    axis.set_ylabel("Submodule")

    colorbar = figure.colorbar(
        image,
        ax=axis,
        fraction=0.035,
        pad=0.04,
    )
    colorbar.set_label("Hedges' g: group A minus group B")

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
    refined: pd.DataFrame,
    axis_results: pd.DataFrame,
    ranking: pd.DataFrame,
    coherence: pd.DataFrame,
) -> None:
    primary = refined[refined["evidence_tier"] == "primary"]
    exploratory = refined[
        refined["evidence_tier"] == "secondary_exploratory"
    ]

    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26B1.1 - Stability-aware GSE280297 refinement\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(
            "- Manuscript and existing Figures 1-6 were not modified.\n"
        )
        handle.write(
            "- C1, C2, and C3 are primary; C4 is secondary exploratory.\n\n"
        )

        handle.write("## Why refinement was required\n\n")
        handle.write(
            "The first U26B1 ranking used the maximum absolute effect across "
            "all contrasts. The UTI89-RFP comparison often involved n=2 versus "
            "n=3 and generated unstable bootstrap intervals, so it was not "
            "appropriate for primary figure prioritization.\n\n"
        )

        handle.write("## Primary permutation evidence\n\n")
        handle.write(
            f"- Primary feature-level results: **{len(primary)}**\n"
        )
        handle.write(
            f"- Primary results at permutation FDR < 0.05: "
            f"**{int(primary['permutation_fdr_0_05'].sum())}**\n"
        )
        handle.write(
            f"- Primary results at permutation FDR < 0.10: "
            f"**{int(primary['permutation_fdr_0_10'].sum())}**\n"
        )
        handle.write(
            f"- Primary results at family-specific FDR < 0.10: "
            f"**{int(primary['family_fdr_0_10'].sum())}**\n\n"
        )

        handle.write("## Axis-level evidence\n\n")
        if axis_results.empty:
            handle.write("No axis-level tests were available.\n\n")
        else:
            for _, row in axis_results.sort_values(
                [
                    "permutation_q_within_contrast",
                    "hedges_g",
                ],
                key=lambda series: (
                    np.abs(series)
                    if series.name == "hedges_g"
                    else series
                ),
            ).head(25).iterrows():
                handle.write(
                    f"- **{row['contrast_id']} | {row['tissue']} | "
                    f"{row['axis']}**: Hedges' g={row['hedges_g']:.3f}, "
                    f"permutation FDR="
                    f"{row['permutation_q_within_contrast']:.4g}.\n"
                )
            handle.write("\n")

        handle.write("## Primary-only Figure 7-10 priorities\n\n")
        for family in [
            "Figure_7",
            "Figure_8",
            "Figure_9",
            "Figure_10",
        ]:
            handle.write(f"### {family}\n\n")
            subset = ranking[
                ranking["proposed_figure_family"] == family
            ].head(10)

            if subset.empty:
                handle.write("No eligible submodules.\n\n")
                continue

            for _, row in subset.iterrows():
                handle.write(
                    f"- `{row['feature_id']}`: "
                    f"{row['evidence_class']}; "
                    f"max primary |g|="
                    f"{row['max_absolute_hedges_g_primary']:.3f}; "
                    f"large primary effects="
                    f"{int(row['n_large_primary_effects'])}; "
                    f"permutation FDR<0.10 results="
                    f"{int(row['n_permutation_FDR_0_10'])}.\n"
                )
            handle.write("\n")

        handle.write("## Cross-tissue directional coherence\n\n")
        if coherence.empty:
            handle.write("No coherence summary was available.\n\n")
        else:
            coherent = coherence[
                (coherence["directional_coherence_fraction"] >= 1.0)
                & (coherence["mean_absolute_hedges_g"] >= 0.50)
            ].sort_values(
                "mean_absolute_hedges_g",
                ascending=False,
            )

            for _, row in coherent.head(30).iterrows():
                handle.write(
                    f"- `{row['feature_id']}` in "
                    f"{row['contrast_id']}: "
                    f"{row['dominant_direction']} across "
                    f"{int(row['n_tissues'])} tissues; "
                    f"mean |g|={row['mean_absolute_hedges_g']:.3f}.\n"
                )
            handle.write("\n")

        handle.write("## Secondary exploratory contrast\n\n")
        handle.write(
            f"- C4 feature-level results retained: **{len(exploratory)}**.\n"
        )
        handle.write(
            "- C4 is excluded from primary Figure 7-10 ranking and from "
            "standalone mechanistic conclusions because its smallest groups "
            "contain only two samples.\n"
        )
        handle.write(
            "- Hedges' g may still be displayed as descriptive exploratory "
            "evidence, but effect-size confidence intervals are suppressed "
            "when either group has fewer than four samples.\n\n"
        )

        handle.write("## Biological interpretation\n\n")
        handle.write(
            "GSE280297 should be used as a tissue-resolved effect-direction "
            "and pathway-architecture layer. Strong but non-FDR-supported "
            "effects are hypothesis-generating until reinforced by the "
            "recurrence model, urinary inflammatory comparator, and "
            "UPEC-responsive single-cell layer.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    parser.add_argument(
        "--max-exact",
        type=int,
        default=5000,
    )
    parser.add_argument(
        "--monte-carlo-iterations",
        type=int,
        default=10000,
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    source_tag = (
        "phaseU26B1_GSE280297_endocrine_metabolic_immune_scoring"
    )
    source_tables = project / "06_tables" / source_tag
    source_processed = project / "03_data_processed" / source_tag
    source_metadata = project / "03_metadata" / source_tag

    results_path = (
        source_tables
        / "UTI_HostOmics_U26B1_all_contrast_results.tsv"
    )
    scores_path = (
        source_processed
        / "GSE280297_U26B1_tissue_centered_submodule_scores.tsv.gz"
    )
    feature_metadata_path = (
        source_metadata
        / "UTI_HostOmics_U26B1_feature_metadata.tsv"
    )

    for required in [
        results_path,
        scores_path,
        feature_metadata_path,
    ]:
        if not required.exists():
            raise FileNotFoundError(
                f"Required U26B1 input not found: {required}"
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

    log("Loading U26B1 results and sample-level scores.")
    results = read_tsv(results_path)
    scores = read_tsv(scores_path)
    feature_metadata = read_tsv(feature_metadata_path)

    refined = add_permutation_statistics(
        results,
        scores,
        max_exact=max(100, args.max_exact),
        monte_carlo_iterations=max(
            1000,
            args.monte_carlo_iterations,
        ),
    )
    refined.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_1_refined_all_results.tsv",
        sep="\t",
        index=False,
    )

    primary = refined[
        refined["evidence_tier"] == "primary"
    ].copy()
    primary.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_1_primary_results.tsv",
        sep="\t",
        index=False,
    )

    exploratory = refined[
        refined["evidence_tier"] == "secondary_exploratory"
    ].copy()
    exploratory.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_1_secondary_exploratory_results.tsv",
        sep="\t",
        index=False,
    )

    axis_scores, axis_definitions = build_axis_scores(
        scores,
        feature_metadata,
    )
    axis_scores.to_csv(
        output_metadata
        / "GSE280297_U26B1_1_axis_scores.tsv.gz",
        sep="\t",
        index=False,
        compression="gzip",
    )
    axis_definitions.to_csv(
        output_metadata
        / "UTI_HostOmics_U26B1_1_axis_score_definitions.tsv",
        sep="\t",
        index=False,
    )

    primary_pairs = (
        primary[
            ["contrast_id", "tissue"]
        ]
        .drop_duplicates()
        .sort_values(
            ["contrast_id", "tissue"]
        )
    )

    axis_results = axis_permutation_tests(
        axis_scores,
        axis_definitions,
        primary_pairs,
        max_exact=max(100, args.max_exact),
        monte_carlo_iterations=max(
            1000,
            args.monte_carlo_iterations,
        ),
    )
    axis_results.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_1_axis_permutation_results.tsv",
        sep="\t",
        index=False,
    )

    ranking = primary_ranking(refined)
    ranking.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_1_primary_figure_candidate_ranking.tsv",
        sep="\t",
        index=False,
    )

    coherence = cross_tissue_coherence(refined)
    coherence.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_1_cross_tissue_directional_coherence.tsv",
        sep="\t",
        index=False,
    )

    large_primary = primary[
        (primary["feature_type"] == "submodule")
        & (np.abs(primary["hedges_g"]) >= 0.80)
        & (
            primary["stability_class"]
            != "exploratory_tiny_group"
        )
    ].copy()
    large_primary.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_1_large_primary_effects.tsv",
        sep="\t",
        index=False,
    )

    for family in [
        "Figure_7",
        "Figure_8",
        "Figure_9",
        "Figure_10",
    ]:
        matrix = primary_effect_matrix(
            refined,
            family,
        )
        matrix.to_csv(
            output_tables
            / f"UTI_HostOmics_U26B1_1_{family}_primary_effect_matrix.tsv",
            sep="\t",
        )
        save_heatmap(
            matrix,
            output_figures
            / f"UTI_HostOmics_U26B1_1_{family}_primary_effect_heatmap",
            f"{family}: primary GSE280297 submodule effects",
        )

    report_path = (
        output_results
        / "UTI_HostOmics_U26B1_1_stability_refinement_report.md"
    )
    write_report(
        report_path,
        refined,
        axis_results,
        ranking,
        coherence,
    )

    decision = "READY_FOR_U26B2_CROSS_DATASET_SCORING"
    decision_table = pd.DataFrame(
        [
            {
                "phase": "U26B1.1",
                "decision": decision,
                "n_primary_feature_results": len(primary),
                "n_secondary_exploratory_results": len(exploratory),
                "n_primary_permutation_FDR_0_05": int(
                    primary["permutation_fdr_0_05"].sum()
                ),
                "n_primary_permutation_FDR_0_10": int(
                    primary["permutation_fdr_0_10"].sum()
                ),
                "n_primary_family_FDR_0_10": int(
                    primary["family_fdr_0_10"].sum()
                ),
                "n_axis_FDR_0_05": int(
                    axis_results["fdr_0_05"].sum()
                ),
                "n_axis_FDR_0_10": int(
                    axis_results["fdr_0_10"].sum()
                ),
                "n_large_primary_effects": len(
                    large_primary
                ),
                "c4_primary_ranking_status": (
                    "excluded_secondary_exploratory"
                ),
                "dam_level_model": "deferred",
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "dataset-appropriate scoring of GSE186800, "
                    "GSE112098, and GSE252321 followed by "
                    "cross-dataset standardized-effect integration"
                ),
            }
        ]
    )
    decision_table.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "source_results": str(results_path),
        "source_scores": str(scores_path),
        "max_exact": int(args.max_exact),
        "monte_carlo_iterations": int(
            args.monte_carlo_iterations
        ),
        "decision": decision,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        output_results
        / "UTI_HostOmics_U26B1_1_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2))

    log(
        f"Primary permutation FDR < 0.05: "
        f"{int(primary['permutation_fdr_0_05'].sum())}"
    )
    log(
        f"Primary permutation FDR < 0.10: "
        f"{int(primary['permutation_fdr_0_10'].sum())}"
    )
    log(
        f"Axis permutation FDR < 0.10: "
        f"{int(axis_results['fdr_0_10'].sum())}"
    )
    log(f"Large primary effects: {len(large_primary)}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26B1.1] ERROR: {exc}", file=sys.stderr)
        raise
