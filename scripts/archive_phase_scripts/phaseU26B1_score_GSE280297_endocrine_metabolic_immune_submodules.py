#!/usr/bin/env python3
"""
Phase U26B1
Expression-level endocrine-metabolic-immune submodule scoring in GSE280297.

Inputs:
- U26A5 canonical 60-sample gene-symbol expression matrix.
- U26A5 validated 60-sample design.
- U26A expanded 78-submodule library.

Outputs:
- Global and tissue-centered sample-level submodule scores.
- Four prespecified tissue-stratified contrasts.
- Hedges' g, bootstrap confidence intervals, Welch p values, BH FDR, and AUROC.
- Composite endocrine-metabolic-immune indices.
- Ranked Figure 7-10 candidate tables and exploratory heatmaps.
- No manuscript or existing figure modification.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    from scipy import stats
except ImportError as exc:
    raise SystemExit(
        "ERROR: scipy is required. Install with: conda install scipy "
        "or pip install scipy"
    ) from exc

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit(
        "ERROR: matplotlib is required. Install with: conda install matplotlib "
        "or pip install matplotlib"
    ) from exc


VERSION = "U26B1_v1.0_2026-07-14"
PHASE_TAG = "phaseU26B1_GSE280297_endocrine_metabolic_immune_scoring"
RANDOM_SEED = 2601
N_BOOTSTRAP = 1000


def log(message: str) -> None:
    print(f"[U26B1] {message}", flush=True)


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        compression="infer",
        low_memory=False,
    )


def parse_gene_list(value: object) -> List[str]:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []

    # U26A writes lists as semicolon-delimited text.
    tokens = re.split(r"[;,| ]+", text)
    return sorted(
        {
            token.strip().upper()
            for token in tokens
            if token.strip()
            and token.strip().lower() != "nan"
        }
    )


def coverage_class(n_total: int, n_detected: int) -> str:
    if n_total <= 0:
        return "unresolved"

    fraction = n_detected / n_total

    if n_total >= 10:
        if n_detected >= 8 and fraction >= 0.65:
            return "adequate"
        if n_detected >= 5 and fraction >= 0.40:
            return "partial"
    elif n_total >= 5:
        if n_detected >= 4 and fraction >= 0.70:
            return "adequate"
        if n_detected >= 3 and fraction >= 0.45:
            return "partial"
    else:
        if n_detected >= 3 and fraction >= 0.75:
            return "adequate"
        if n_detected >= 2 and fraction >= 0.50:
            return "partial"

    return "weak"


def load_module_library(path: Path) -> pd.DataFrame:
    library = read_tsv(path)

    required = {
        "axis",
        "submodule_id",
        "display_label",
        "genes",
        "proposed_figure_family",
    }
    missing = sorted(required - set(library.columns))
    if missing:
        raise RuntimeError(
            f"Module library is missing required columns: {missing}"
        )

    library = library.copy()
    library["gene_list"] = library["genes"].map(parse_gene_list)
    library["n_library_genes"] = library["gene_list"].map(len)

    return library


def load_expression(path: Path) -> pd.DataFrame:
    expression = read_tsv(path)

    if "gene_symbol" not in expression.columns:
        raise RuntimeError(
            f"gene_symbol column not found in {path}"
        )

    expression = expression.copy()
    expression["gene_symbol"] = (
        expression["gene_symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )
    expression = expression.drop_duplicates(
        subset=["gene_symbol"],
        keep="first",
    )
    expression = expression.set_index("gene_symbol")

    for column in expression.columns:
        expression[column] = pd.to_numeric(
            expression[column],
            errors="coerce",
        )

    return expression


def load_design(
    path: Path,
    expression_samples: Sequence[str],
) -> pd.DataFrame:
    design = read_tsv(path)

    if "sample_id" not in design.columns:
        raise RuntimeError(
            f"sample_id column not found in {path}"
        )

    design = design.copy()
    design["sample_id"] = (
        design["sample_id"].astype(str).str.strip()
    )
    design = design.drop_duplicates(
        subset=["sample_id"],
        keep="first",
    )
    design = design.set_index("sample_id", drop=False)

    missing = [
        sample
        for sample in expression_samples
        if sample not in design.index
    ]
    if missing:
        raise RuntimeError(
            "Expression samples missing from design: "
            + ", ".join(missing)
        )

    return design.loc[list(expression_samples)].reset_index(drop=True)


def zscore_rows(frame: pd.DataFrame) -> pd.DataFrame:
    means = frame.mean(axis=1, skipna=True)
    standard_deviations = frame.std(
        axis=1,
        skipna=True,
        ddof=1,
    )
    standard_deviations = standard_deviations.replace(
        0,
        np.nan,
    )

    z = frame.sub(means, axis=0).div(
        standard_deviations,
        axis=0,
    )
    return z.fillna(0.0)


def build_coverage(
    expression: pd.DataFrame,
    library: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    universe = set(expression.index)
    module_genes: Dict[str, List[str]] = {}
    rows = []

    for _, module in library.iterrows():
        module_id = str(module["submodule_id"])
        genes = list(module["gene_list"])
        detected = [gene for gene in genes if gene in universe]
        module_genes[module_id] = detected

        n_total = len(genes)
        n_detected = len(detected)
        fraction = (
            n_detected / n_total
            if n_total
            else math.nan
        )
        classification = coverage_class(
            n_total,
            n_detected,
        )

        rows.append(
            {
                "axis": module["axis"],
                "submodule_id": module_id,
                "display_label": module["display_label"],
                "proposed_figure_family": module[
                    "proposed_figure_family"
                ],
                "n_library_genes": n_total,
                "n_detected_genes": n_detected,
                "coverage_fraction": (
                    round(fraction, 4)
                    if n_total
                    else ""
                ),
                "coverage_class": classification,
                "score_eligible": (
                    classification in {"adequate", "partial"}
                    and n_detected >= 3
                ),
                "detected_genes": ";".join(detected),
                "missing_genes": ";".join(
                    [gene for gene in genes if gene not in universe]
                ),
            }
        )

    return pd.DataFrame(rows), module_genes


def calculate_global_scores(
    expression: pd.DataFrame,
    design: pd.DataFrame,
    coverage: pd.DataFrame,
    module_genes: Dict[str, List[str]],
) -> pd.DataFrame:
    z = zscore_rows(expression)
    score_frame = design.copy()

    eligible = coverage[coverage["score_eligible"]].copy()

    for module_id in eligible["submodule_id"]:
        genes = module_genes[str(module_id)]
        score_frame[str(module_id)] = (
            z.loc[genes].mean(axis=0).reindex(
                score_frame["sample_id"]
            ).to_numpy()
        )

    return score_frame


def calculate_tissue_centered_scores(
    expression: pd.DataFrame,
    design: pd.DataFrame,
    coverage: pd.DataFrame,
    module_genes: Dict[str, List[str]],
) -> pd.DataFrame:
    result_parts = []
    eligible_modules = (
        coverage.loc[
            coverage["score_eligible"],
            "submodule_id",
        ]
        .astype(str)
        .tolist()
    )

    design_indexed = design.set_index(
        "sample_id",
        drop=False,
    )

    for tissue in sorted(
        design["tissue"].dropna().astype(str).unique()
    ):
        sample_ids = (
            design.loc[
                design["tissue"].astype(str) == tissue,
                "sample_id",
            ]
            .astype(str)
            .tolist()
        )
        tissue_expression = expression[sample_ids]
        tissue_z = zscore_rows(tissue_expression)

        part = design_indexed.loc[sample_ids].copy()

        for module_id in eligible_modules:
            genes = module_genes[module_id]
            part[module_id] = (
                tissue_z.loc[genes]
                .mean(axis=0)
                .reindex(sample_ids)
                .to_numpy()
            )

        result_parts.append(part.reset_index(drop=True))

    return pd.concat(
        result_parts,
        ignore_index=True,
    )


COMPOSITE_DEFINITIONS = {
    "STEROID_INFLAMMATORY_IMBALANCE_INDEX": {
        "positive": [
            "ANDROGEN_TESTOSTERONE_BIOSYNTHESIS",
            "ANDROGEN_RECEPTOR_SIGNALING",
            "GLUCOCORTICOID_RESPONSE",
            "STEROID_CATABOLISM_DEACTIVATION",
            "NFKB_MAPK_INFLAMMATION_ANCHOR",
            "PREGNANCY_INFLAMMATION_ANCHOR",
        ],
        "negative": [
            "PROGESTERONE_BIOSYNTHESIS_RESPONSE",
            "ESTROGEN_RECEPTOR_RESPONSE",
            "PLACENTAL_STEROID_METABOLISM",
        ],
    },
    "INFLAMMATORY_CARBON_USE_INDEX": {
        "positive": [
            "GLYCOLYSIS",
            "LACTATE_HIF1A_INFLAMMATORY_GLYCOLYSIS",
            "PENTOSE_PHOSPHATE_PATHWAY",
            "GLUCOSE_TRANSPORT",
            "MTOR_SIGNALING",
            "INSULIN_RECEPTOR_IRS",
            "PI3K_AKT_SIGNALING",
        ],
        "negative": [
            "TCA_OXPHOS",
            "AMPK_SIGNALING",
            "FATTY_ACID_BETA_OXIDATION",
        ],
    },
    "COMPLEMENT_INFLAMMATORY_AMPLIFICATION_INDEX": {
        "positive": [
            "COMPLEMENT_ALTERNATIVE",
            "COMPLEMENT_C3_CONVERTASE_AMPLIFICATION",
            "COMPLEMENT_C3A_C5A_SIGNALING",
            "COMPLEMENT_TERMINAL_MAC",
            "COMPLEMENT_COAGULATION_CROSSTALK",
            "NFKB_MAPK_INFLAMMATION_ANCHOR",
        ],
        "negative": [
            "COMPLEMENT_REGULATORS",
        ],
    },
}


def add_composite_indices(
    score_frame: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    score_frame = score_frame.copy()
    blueprint_rows = []

    for index_id, definition in COMPOSITE_DEFINITIONS.items():
        positive = [
            module
            for module in definition["positive"]
            if module in score_frame.columns
        ]
        negative = [
            module
            for module in definition["negative"]
            if module in score_frame.columns
        ]

        if positive:
            positive_score = score_frame[positive].mean(
                axis=1,
            )
        else:
            positive_score = pd.Series(
                np.nan,
                index=score_frame.index,
            )

        if negative:
            negative_score = score_frame[negative].mean(
                axis=1,
            )
        else:
            negative_score = pd.Series(
                0.0,
                index=score_frame.index,
            )

        score_frame[index_id] = (
            positive_score - negative_score
        )

        blueprint_rows.append(
            {
                "composite_index": index_id,
                "positive_components_requested": ";".join(
                    definition["positive"]
                ),
                "positive_components_available": ";".join(
                    positive
                ),
                "negative_components_requested": ";".join(
                    definition["negative"]
                ),
                "negative_components_available": ";".join(
                    negative
                ),
                "n_positive_available": len(positive),
                "n_negative_available": len(negative),
                "index_computable": bool(positive),
            }
        )

    pregnancy_positive = [
        "STEROID_INFLAMMATORY_IMBALANCE_INDEX",
        "INFLAMMATORY_CARBON_USE_INDEX",
        "COMPLEMENT_INFLAMMATORY_AMPLIFICATION_INDEX",
        "PREGNANCY_INFLAMMATION_ANCHOR",
        "EICOSANOID_PROSTAGLANDIN_METABOLISM",
        "FERROPTOSIS_LIPID_PEROXIDATION",
    ]
    pregnancy_negative = [
        "UROTHELIAL_BARRIER_REPAIR_ANCHOR",
        "PROGESTERONE_BIOSYNTHESIS_RESPONSE",
    ]

    positive = [
        component
        for component in pregnancy_positive
        if component in score_frame.columns
    ]
    negative = [
        component
        for component in pregnancy_negative
        if component in score_frame.columns
    ]

    score_frame[
        "PREGNANCY_RISK_ENDOCRINE_METABOLIC_INFLAMMATION_INDEX"
    ] = (
        score_frame[positive].mean(axis=1)
        - (
            score_frame[negative].mean(axis=1)
            if negative
            else 0.0
        )
    )

    blueprint_rows.append(
        {
            "composite_index": (
                "PREGNANCY_RISK_ENDOCRINE_METABOLIC_"
                "INFLAMMATION_INDEX"
            ),
            "positive_components_requested": ";".join(
                pregnancy_positive
            ),
            "positive_components_available": ";".join(
                positive
            ),
            "negative_components_requested": ";".join(
                pregnancy_negative
            ),
            "negative_components_available": ";".join(
                negative
            ),
            "n_positive_available": len(positive),
            "n_negative_available": len(negative),
            "index_computable": bool(positive),
        }
    )

    return score_frame, pd.DataFrame(blueprint_rows)


def hedges_g(
    group_a: np.ndarray,
    group_b: np.ndarray,
) -> float:
    group_a = group_a[np.isfinite(group_a)]
    group_b = group_b[np.isfinite(group_b)]

    n_a = len(group_a)
    n_b = len(group_b)

    if n_a < 2 or n_b < 2:
        return float("nan")

    variance_a = np.var(group_a, ddof=1)
    variance_b = np.var(group_b, ddof=1)

    pooled_denominator = n_a + n_b - 2
    if pooled_denominator <= 0:
        return float("nan")

    pooled_variance = (
        ((n_a - 1) * variance_a)
        + ((n_b - 1) * variance_b)
    ) / pooled_denominator

    if pooled_variance <= 0:
        return 0.0

    cohen_d = (
        np.mean(group_a) - np.mean(group_b)
    ) / math.sqrt(pooled_variance)

    correction = (
        1.0
        - 3.0
        / (4.0 * (n_a + n_b) - 9.0)
    )

    return float(correction * cohen_d)


def bootstrap_g_ci(
    group_a: np.ndarray,
    group_b: np.ndarray,
    random_state: np.random.Generator,
    iterations: int = N_BOOTSTRAP,
) -> Tuple[float, float]:
    group_a = group_a[np.isfinite(group_a)]
    group_b = group_b[np.isfinite(group_b)]

    if len(group_a) < 2 or len(group_b) < 2:
        return float("nan"), float("nan")

    estimates = []

    for _ in range(iterations):
        sample_a = random_state.choice(
            group_a,
            size=len(group_a),
            replace=True,
        )
        sample_b = random_state.choice(
            group_b,
            size=len(group_b),
            replace=True,
        )
        estimate = hedges_g(sample_a, sample_b)
        if np.isfinite(estimate):
            estimates.append(estimate)

    if not estimates:
        return float("nan"), float("nan")

    return (
        float(np.percentile(estimates, 2.5)),
        float(np.percentile(estimates, 97.5)),
    )


def auc_group_a_higher(
    group_a: np.ndarray,
    group_b: np.ndarray,
) -> float:
    group_a = group_a[np.isfinite(group_a)]
    group_b = group_b[np.isfinite(group_b)]

    if len(group_a) == 0 or len(group_b) == 0:
        return float("nan")

    combined = np.concatenate([group_a, group_b])
    ranks = stats.rankdata(combined)
    rank_sum_a = np.sum(ranks[: len(group_a)])
    u_a = (
        rank_sum_a
        - len(group_a) * (len(group_a) + 1) / 2
    )

    return float(
        u_a / (len(group_a) * len(group_b))
    )


def bh_fdr(p_values: Sequence[float]) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    result = np.full(values.shape, np.nan)

    finite_indices = np.where(np.isfinite(values))[0]
    if len(finite_indices) == 0:
        return result

    finite_values = values[finite_indices]
    order = np.argsort(finite_values)
    ranked = finite_values[order]
    n = len(ranked)

    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(
        adjusted[::-1]
    )[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)

    reordered = np.empty(n)
    reordered[order] = adjusted
    result[finite_indices] = reordered

    return result


def contrast_subsets(
    score_frame: pd.DataFrame,
) -> List[Dict[str, object]]:
    contrasts: List[Dict[str, object]] = []

    tissues = sorted(
        score_frame["tissue"]
        .dropna()
        .astype(str)
        .unique()
    )

    for tissue in tissues:
        tissue_frame = score_frame[
            score_frame["tissue"].astype(str) == tissue
        ]

        contrasts.append(
            {
                "contrast_id": "C1_PRETERM_VS_TERM",
                "tissue": tissue,
                "group_a_label": "UTI89_preterm",
                "group_b_label": "UTI89_term",
                "group_a": tissue_frame[
                    (tissue_frame["treatment"] == "UTI89")
                    & (tissue_frame["outcome"] == "preterm")
                ],
                "group_b": tissue_frame[
                    (tissue_frame["treatment"] == "UTI89")
                    & (tissue_frame["outcome"] == "term")
                ],
                "interpretation": (
                    "positive effect indicates higher activity "
                    "in UTI-associated preterm samples"
                ),
                "analysis_status": "primary",
            }
        )

        contrasts.append(
            {
                "contrast_id": "C2_UPEC_VS_PBS_PREGNANCY",
                "tissue": tissue,
                "group_a_label": "UPEC_exposed_pregnancy",
                "group_b_label": "PBS_pregnancy_control",
                "group_a": tissue_frame[
                    (
                        tissue_frame[
                            "pregnancy_status"
                        ].isin(
                            ["pregnant", "pregnant_control"]
                        )
                    )
                    & (
                        tissue_frame[
                            "primary_exposure"
                        ] == "UPEC_exposed"
                    )
                ],
                "group_b": tissue_frame[
                    (
                        tissue_frame[
                            "pregnancy_status"
                        ] == "pregnant_control"
                    )
                    & (
                        tissue_frame[
                            "primary_exposure"
                        ] == "control"
                    )
                ],
                "interpretation": (
                    "positive effect indicates higher activity "
                    "in UPEC-exposed pregnancy samples"
                ),
                "analysis_status": "primary",
            }
        )

        term_frame = tissue_frame[
            tissue_frame["outcome"] == "term"
        ]

        contrasts.append(
            {
                "contrast_id": "C4_UTI89_RFP_VS_UTI89_TERM",
                "tissue": tissue,
                "group_a_label": "UTI89_RFP_term",
                "group_b_label": "UTI89_term",
                "group_a": term_frame[
                    term_frame["treatment"] == "UTI89_RFP"
                ],
                "group_b": term_frame[
                    term_frame["treatment"] == "UTI89"
                ],
                "interpretation": (
                    "positive effect indicates higher activity "
                    "in the UTI89-RFP term subgroup"
                ),
                "analysis_status": "secondary_exploratory",
            }
        )

    bladder = score_frame[
        score_frame["tissue"] == "bladder"
    ]

    contrasts.append(
        {
            "contrast_id": "C3_INFECTED_PREGNANT_VS_NONPREGNANT",
            "tissue": "bladder",
            "group_a_label": "UTI89_pregnant",
            "group_b_label": "UTI89_nonpregnant",
            "group_a": bladder[
                (bladder["treatment"] == "UTI89")
                & (
                    bladder["pregnancy_status"]
                    == "pregnant"
                )
            ],
            "group_b": bladder[
                (bladder["treatment"] == "UTI89")
                & (
                    bladder["pregnancy_status"]
                    == "nonpregnant"
                )
            ],
            "interpretation": (
                "positive effect indicates higher activity "
                "in infected pregnant bladder"
            ),
            "analysis_status": "primary_small_group",
        }
    )

    return contrasts


def run_contrasts(
    score_frame: pd.DataFrame,
    feature_ids: Sequence[str],
    feature_metadata: pd.DataFrame,
    bootstrap_iterations: int,
) -> pd.DataFrame:
    random_state = np.random.default_rng(
        RANDOM_SEED
    )
    metadata_lookup = (
        feature_metadata
        .drop_duplicates("feature_id")
        .set_index("feature_id")
        .to_dict("index")
    )
    rows = []

    for contrast in contrast_subsets(score_frame):
        group_a = contrast["group_a"]
        group_b = contrast["group_b"]

        if len(group_a) < 2 or len(group_b) < 2:
            log(
                f"Skipping {contrast['contrast_id']} "
                f"{contrast['tissue']}: "
                f"n_a={len(group_a)}, n_b={len(group_b)}"
            )
            continue

        contrast_rows = []

        for feature_id in feature_ids:
            if feature_id not in score_frame.columns:
                continue

            a = pd.to_numeric(
                group_a[feature_id],
                errors="coerce",
            ).to_numpy(dtype=float)
            b = pd.to_numeric(
                group_b[feature_id],
                errors="coerce",
            ).to_numpy(dtype=float)

            a = a[np.isfinite(a)]
            b = b[np.isfinite(b)]

            if len(a) < 2 or len(b) < 2:
                continue

            effect = hedges_g(a, b)
            ci_low, ci_high = bootstrap_g_ci(
                a,
                b,
                random_state,
                iterations=bootstrap_iterations,
            )

            welch = stats.ttest_ind(
                a,
                b,
                equal_var=False,
                nan_policy="omit",
            )

            auc = auc_group_a_higher(a, b)
            metadata = metadata_lookup.get(
                feature_id,
                {},
            )

            contrast_rows.append(
                {
                    "contrast_id": contrast[
                        "contrast_id"
                    ],
                    "tissue": contrast["tissue"],
                    "analysis_status": contrast[
                        "analysis_status"
                    ],
                    "group_a": contrast[
                        "group_a_label"
                    ],
                    "group_b": contrast[
                        "group_b_label"
                    ],
                    "n_group_a": len(a),
                    "n_group_b": len(b),
                    "feature_type": metadata.get(
                        "feature_type",
                        "submodule",
                    ),
                    "axis": metadata.get(
                        "axis",
                        "composite_index",
                    ),
                    "feature_id": feature_id,
                    "display_label": metadata.get(
                        "display_label",
                        feature_id,
                    ),
                    "proposed_figure_family": metadata.get(
                        "proposed_figure_family",
                        "Integrated_network",
                    ),
                    "mean_group_a": float(np.mean(a)),
                    "mean_group_b": float(np.mean(b)),
                    "mean_difference_a_minus_b": float(
                        np.mean(a) - np.mean(b)
                    ),
                    "hedges_g": effect,
                    "hedges_g_ci_low": ci_low,
                    "hedges_g_ci_high": ci_high,
                    "welch_t": float(
                        welch.statistic
                    ),
                    "p_value": float(welch.pvalue),
                    "auc_group_a_higher": auc,
                    "direction": (
                        "higher_in_group_a"
                        if effect > 0
                        else "higher_in_group_b"
                        if effect < 0
                        else "no_difference"
                    ),
                    "interpretation": contrast[
                        "interpretation"
                    ],
                }
            )

        if contrast_rows:
            p_values = [
                row["p_value"]
                for row in contrast_rows
            ]
            q_values = bh_fdr(p_values)

            for row, q_value in zip(
                contrast_rows,
                q_values,
            ):
                row["q_value_within_contrast"] = float(
                    q_value
                )
                row["fdr_0_05"] = bool(
                    np.isfinite(q_value)
                    and q_value < 0.05
                )
                row["fdr_0_10"] = bool(
                    np.isfinite(q_value)
                    and q_value < 0.10
                )

            rows.extend(contrast_rows)

    return pd.DataFrame(rows)


def create_feature_metadata(
    library: pd.DataFrame,
    coverage: pd.DataFrame,
    composite_blueprints: pd.DataFrame,
) -> pd.DataFrame:
    eligible = coverage[
        coverage["score_eligible"]
    ][["submodule_id"]].copy()

    modules = library.merge(
        eligible,
        on="submodule_id",
        how="inner",
    )
    modules = modules[
        [
            "axis",
            "submodule_id",
            "display_label",
            "proposed_figure_family",
        ]
    ].copy()
    modules.rename(
        columns={"submodule_id": "feature_id"},
        inplace=True,
    )
    modules["feature_type"] = "submodule"

    composites = composite_blueprints.copy()
    composites["feature_id"] = composites[
        "composite_index"
    ]
    composites["axis"] = "composite_index"
    composites["display_label"] = composites[
        "composite_index"
    ].str.replace("_", " ", regex=False).str.title()
    composites[
        "proposed_figure_family"
    ] = "Integrated_network"
    composites["feature_type"] = "composite_index"

    composites = composites[
        [
            "axis",
            "feature_id",
            "display_label",
            "proposed_figure_family",
            "feature_type",
        ]
    ]

    return pd.concat(
        [modules, composites],
        ignore_index=True,
    )


def axis_summary(
    results: pd.DataFrame,
) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()

    summary = (
        results.groupby(
            [
                "contrast_id",
                "tissue",
                "analysis_status",
                "axis",
            ],
            dropna=False,
        )
        .agg(
            n_features=("feature_id", "count"),
            median_hedges_g=("hedges_g", "median"),
            mean_absolute_hedges_g=(
                "hedges_g",
                lambda x: float(
                    np.nanmean(np.abs(x))
                ),
            ),
            n_fdr_0_05=("fdr_0_05", "sum"),
            n_fdr_0_10=("fdr_0_10", "sum"),
        )
        .reset_index()
    )

    return summary


def rank_figure_candidates(
    results: pd.DataFrame,
) -> pd.DataFrame:
    modules = results[
        results["feature_type"] == "submodule"
    ].copy()

    if modules.empty:
        return pd.DataFrame()

    ranking = (
        modules.groupby(
            [
                "proposed_figure_family",
                "axis",
                "feature_id",
                "display_label",
            ],
            dropna=False,
        )
        .agg(
            max_absolute_hedges_g=(
                "hedges_g",
                lambda x: float(
                    np.nanmax(np.abs(x))
                ),
            ),
            median_absolute_hedges_g=(
                "hedges_g",
                lambda x: float(
                    np.nanmedian(np.abs(x))
                ),
            ),
            n_fdr_0_05=("fdr_0_05", "sum"),
            n_fdr_0_10=("fdr_0_10", "sum"),
            n_contrasts=("contrast_id", "count"),
        )
        .reset_index()
    )

    ranking["evidence_priority_score"] = (
        ranking["max_absolute_hedges_g"]
        + 0.5 * ranking["median_absolute_hedges_g"]
        + 2.0 * ranking["n_fdr_0_05"]
        + 1.0 * ranking["n_fdr_0_10"]
    )

    return ranking.sort_values(
        [
            "proposed_figure_family",
            "evidence_priority_score",
        ],
        ascending=[True, False],
    )


def result_matrix(
    results: pd.DataFrame,
    feature_ids: Sequence[str],
) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()

    data = results.copy()
    data["contrast_tissue"] = (
        data["contrast_id"].astype(str)
        + " | "
        + data["tissue"].astype(str)
    )

    matrix = data.pivot_table(
        index="feature_id",
        columns="contrast_tissue",
        values="hedges_g",
        aggfunc="first",
    )

    order = [
        feature
        for feature in feature_ids
        if feature in matrix.index
    ]

    return matrix.loc[order]


def save_heatmap(
    matrix: pd.DataFrame,
    output_stem: Path,
    title: str,
) -> None:
    if matrix.empty:
        return

    figure_width = max(
        9.0,
        1.1 * len(matrix.columns) + 4.0,
    )
    figure_height = max(
        5.0,
        0.35 * len(matrix.index) + 2.5,
    )

    figure = plt.figure(
        figsize=(figure_width, figure_height)
    )
    axis = figure.add_axes([0.30, 0.16, 0.58, 0.72])

    image = axis.imshow(
        matrix.to_numpy(dtype=float),
        aspect="auto",
    )

    axis.set_xticks(
        np.arange(len(matrix.columns))
    )
    axis.set_xticklabels(
        matrix.columns,
        rotation=55,
        ha="right",
        fontsize=8,
    )
    axis.set_yticks(
        np.arange(len(matrix.index))
    )
    axis.set_yticklabels(
        matrix.index,
        fontsize=8,
    )
    axis.set_title(title)
    axis.set_xlabel(
        "Prespecified contrast and tissue"
    )
    axis.set_ylabel("Submodule or composite index")

    colorbar = figure.colorbar(
        image,
        ax=axis,
        fraction=0.035,
        pad=0.04,
    )
    colorbar.set_label(
        "Hedges' g: group A minus group B"
    )

    output_stem.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
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
    output_path: Path,
    coverage: pd.DataFrame,
    results: pd.DataFrame,
    ranking: pd.DataFrame,
    composite_results: pd.DataFrame,
) -> None:
    eligible = coverage[
        coverage["score_eligible"]
    ]
    adequate = int(
        (coverage["coverage_class"] == "adequate").sum()
    )
    partial = int(
        (coverage["coverage_class"] == "partial").sum()
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write(
            "# Phase U26B1 - GSE280297 endocrine-metabolic-immune "
            "submodule scoring\n\n"
        )
        handle.write(
            f"- Version: `{VERSION}`\n"
        )
        handle.write(
            "- Manuscript and existing Figures 1-6 were not modified.\n"
        )
        handle.write(
            "- Dam-level pregnancy-outcome modeling remained deferred.\n\n"
        )

        handle.write("## Scoring scope\n\n")
        handle.write(
            f"- Submodules in library: **{len(coverage)}**\n"
        )
        handle.write(
            f"- Score-eligible submodules: **{len(eligible)}**\n"
        )
        handle.write(
            f"- Adequate coverage: **{adequate}**\n"
        )
        handle.write(
            f"- Partial coverage: **{partial}**\n"
        )
        handle.write(
            "- Primary scores are tissue-centered mean gene-z scores. "
            "They represent transcriptionally inferred pathway activity, "
            "not measured metabolic flux.\n\n"
        )

        handle.write("## Prespecified contrasts\n\n")
        if results.empty:
            handle.write(
                "No contrasts produced valid two-group results.\n\n"
            )
        else:
            counts = (
                results.groupby(
                    [
                        "contrast_id",
                        "tissue",
                        "analysis_status",
                    ]
                )
                .agg(
                    n_features=("feature_id", "count"),
                    n_fdr_0_05=("fdr_0_05", "sum"),
                    n_fdr_0_10=("fdr_0_10", "sum"),
                )
                .reset_index()
            )

            for _, row in counts.iterrows():
                handle.write(
                    f"- **{row['contrast_id']} | {row['tissue']}** "
                    f"({row['analysis_status']}): "
                    f"{row['n_features']} features; "
                    f"{row['n_fdr_0_05']} at FDR < 0.05; "
                    f"{row['n_fdr_0_10']} at FDR < 0.10.\n"
                )
            handle.write("\n")

        handle.write("## Highest-ranked submodule signals\n\n")
        if ranking.empty:
            handle.write("No ranked module results available.\n\n")
        else:
            for figure_family in [
                "Figure_7",
                "Figure_8",
                "Figure_9",
                "Figure_10",
            ]:
                subset = ranking[
                    ranking[
                        "proposed_figure_family"
                    ] == figure_family
                ].head(10)

                handle.write(
                    f"### {figure_family}\n\n"
                )

                if subset.empty:
                    handle.write(
                        "No eligible submodules.\n\n"
                    )
                    continue

                for _, row in subset.iterrows():
                    handle.write(
                        f"- `{row['feature_id']}`: "
                        f"maximum |Hedges' g| "
                        f"{row['max_absolute_hedges_g']:.3f}; "
                        f"{int(row['n_fdr_0_05'])} FDR<0.05 and "
                        f"{int(row['n_fdr_0_10'])} FDR<0.10 results.\n"
                    )
                handle.write("\n")

        handle.write("## Composite indices\n\n")
        if composite_results.empty:
            handle.write(
                "No composite-index results were generated.\n\n"
            )
        else:
            top = composite_results.sort_values(
                "hedges_g",
                key=lambda values: np.abs(values),
                ascending=False,
            ).head(20)

            for _, row in top.iterrows():
                handle.write(
                    f"- **{row['display_label']}**, "
                    f"{row['contrast_id']} | {row['tissue']}: "
                    f"Hedges' g={row['hedges_g']:.3f}, "
                    f"FDR={row['q_value_within_contrast']:.4g}, "
                    f"AUROC={row['auc_group_a_higher']:.3f}.\n"
                )
            handle.write("\n")

        handle.write("## Interpretation boundary\n\n")
        handle.write(
            "- Transcriptomic module scores estimate pathway-program "
            "activity and should not be described as direct metabolite "
            "concentrations or actual biochemical flux.\n"
        )
        handle.write(
            "- Tissue samples are independent GEO samples for "
            "tissue-stratified contrasts; they must not be aggregated "
            "across tissues as independent maternal replicates.\n"
        )
        handle.write(
            "- The small UTI89-RFP and infected nonpregnant groups are "
            "best interpreted through effect sizes and confidence "
            "intervals rather than isolated p values.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=N_BOOTSTRAP,
    )
    args = parser.parse_args()

    bootstrap_iterations = max(
        200,
        int(args.bootstrap_iterations),
    )

    project = Path(args.project_root).resolve()

    expression_path = (
        project
        / "03_data_processed"
        / "phaseU26A5_GSE280297_final_input_resolution"
        / "GSE280297_U26A5_canonical_60sample_gene_symbol_expression.tsv.gz"
    )
    design_path = (
        project
        / "03_metadata"
        / "phaseU26A5_GSE280297_final_input_resolution"
        / "GSE280297_U26A5_validated_60sample_design.tsv"
    )
    library_path = (
        project
        / "03_metadata"
        / "phaseU26A_expanded_endocrine_metabolic_immune_feasibility"
        / "UTI_HostOmics_U26A_expanded_submodule_library.tsv"
    )

    for required in [
        expression_path,
        design_path,
        library_path,
    ]:
        if not required.exists():
            raise FileNotFoundError(
                f"Required U26B1 input not found: {required}"
            )

    output_metadata = project / "03_metadata" / PHASE_TAG
    output_processed = (
        project / "03_data_processed" / PHASE_TAG
    )
    output_results = project / "05_results" / PHASE_TAG
    output_tables = project / "06_tables" / PHASE_TAG
    output_figures = project / "06_figures" / PHASE_TAG

    for directory in [
        output_metadata,
        output_processed,
        output_results,
        output_tables,
        output_figures,
    ]:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    log("Loading expression, design, and submodule library.")
    expression = load_expression(expression_path)
    design = load_design(
        design_path,
        expression.columns,
    )
    library = load_module_library(library_path)

    coverage, module_genes = build_coverage(
        expression,
        library,
    )
    coverage.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_GSE280297_submodule_coverage.tsv",
        sep="\t",
        index=False,
    )

    log(
        f"Score-eligible submodules: "
        f"{int(coverage['score_eligible'].sum())}/{len(coverage)}"
    )

    global_scores = calculate_global_scores(
        expression,
        design,
        coverage,
        module_genes,
    )
    global_scores, global_blueprints = add_composite_indices(
        global_scores
    )
    global_scores.to_csv(
        output_processed
        / "GSE280297_U26B1_global_submodule_scores.tsv.gz",
        sep="\t",
        index=False,
        compression="gzip",
    )

    tissue_scores = calculate_tissue_centered_scores(
        expression,
        design,
        coverage,
        module_genes,
    )
    tissue_scores, composite_blueprints = add_composite_indices(
        tissue_scores
    )
    tissue_scores.to_csv(
        output_processed
        / "GSE280297_U26B1_tissue_centered_submodule_scores.tsv.gz",
        sep="\t",
        index=False,
        compression="gzip",
    )

    composite_blueprints.to_csv(
        output_metadata
        / "UTI_HostOmics_U26B1_composite_index_blueprints.tsv",
        sep="\t",
        index=False,
    )

    feature_metadata = create_feature_metadata(
        library,
        coverage,
        composite_blueprints,
    )
    feature_metadata.to_csv(
        output_metadata
        / "UTI_HostOmics_U26B1_feature_metadata.tsv",
        sep="\t",
        index=False,
    )

    feature_ids = (
        feature_metadata["feature_id"]
        .astype(str)
        .tolist()
    )

    log("Running prespecified tissue-stratified contrasts.")
    results = run_contrasts(
        tissue_scores,
        feature_ids,
        feature_metadata,
        bootstrap_iterations,
    )

    if results.empty:
        raise RuntimeError(
            "No valid contrast results were produced."
        )

    results.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_all_contrast_results.tsv",
        sep="\t",
        index=False,
    )

    significant = results[
        results["q_value_within_contrast"] < 0.10
    ].copy()
    significant.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_FDR10_results.tsv",
        sep="\t",
        index=False,
    )

    axis_results = axis_summary(results)
    axis_results.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_axis_contrast_summary.tsv",
        sep="\t",
        index=False,
    )

    ranking = rank_figure_candidates(results)
    ranking.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_figure_candidate_ranking.tsv",
        sep="\t",
        index=False,
    )

    composite_results = results[
        results["feature_type"] == "composite_index"
    ].copy()
    composite_results.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_composite_index_contrasts.tsv",
        sep="\t",
        index=False,
    )

    # Effect-size matrices and separate exploratory figure drafts.
    all_matrix = result_matrix(
        results,
        feature_ids,
    )
    all_matrix.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_effect_size_matrix.tsv",
        sep="\t",
    )

    for figure_family in [
        "Figure_7",
        "Figure_8",
        "Figure_9",
        "Figure_10",
    ]:
        family_features = (
            feature_metadata.loc[
                feature_metadata[
                    "proposed_figure_family"
                ] == figure_family,
                "feature_id",
            ]
            .astype(str)
            .tolist()
        )
        family_matrix = result_matrix(
            results[
                results[
                    "proposed_figure_family"
                ] == figure_family
            ],
            family_features,
        )
        family_matrix.to_csv(
            output_tables
            / f"UTI_HostOmics_U26B1_{figure_family}_effect_size_matrix.tsv",
            sep="\t",
        )
        save_heatmap(
            family_matrix,
            output_figures
            / f"UTI_HostOmics_U26B1_{figure_family}_candidate_effect_heatmap",
            (
                f"{figure_family} candidate: "
                "GSE280297 tissue-stratified submodule effects"
            ),
        )

    composite_features = (
        feature_metadata.loc[
            feature_metadata["feature_type"]
            == "composite_index",
            "feature_id",
        ]
        .astype(str)
        .tolist()
    )
    composite_matrix = result_matrix(
        composite_results,
        composite_features,
    )
    composite_matrix.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_composite_effect_size_matrix.tsv",
        sep="\t",
    )
    save_heatmap(
        composite_matrix,
        output_figures
        / "UTI_HostOmics_U26B1_composite_index_effect_heatmap",
        "GSE280297 endocrine-metabolic-immune composite indices",
    )

    report_path = (
        output_results
        / "UTI_HostOmics_U26B1_GSE280297_scoring_report.md"
    )
    write_report(
        report_path,
        coverage,
        results,
        ranking,
        composite_results,
    )

    decision = "READY_FOR_U26B2_CROSS_DATASET_SCORING"
    decision_row = pd.DataFrame(
        [
            {
                "phase": "U26B1",
                "decision": decision,
                "dataset": "GSE280297",
                "n_expression_samples": len(design),
                "n_library_submodules": len(coverage),
                "n_score_eligible_submodules": int(
                    coverage["score_eligible"].sum()
                ),
                "n_contrast_results": len(results),
                "n_FDR_0_05_results": int(
                    results["fdr_0_05"].sum()
                ),
                "n_FDR_0_10_results": int(
                    results["fdr_0_10"].sum()
                ),
                "dam_level_model": "deferred",
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "score GSE186800, GSE112098, and GSE252321 "
                    "with dataset-appropriate models, then integrate "
                    "standardized module effects"
                ),
            }
        ]
    )
    decision_row.to_csv(
        output_tables
        / "UTI_HostOmics_U26B1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "expression_input": str(expression_path),
        "design_input": str(design_path),
        "module_library": str(library_path),
        "bootstrap_iterations": bootstrap_iterations,
        "decision": decision,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        output_results
        / "UTI_HostOmics_U26B1_run_manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
        )
    )

    log(f"Contrast results: {len(results)}")
    log(
        f"FDR < 0.05 results: "
        f"{int(results['fdr_0_05'].sum())}"
    )
    log(
        f"FDR < 0.10 results: "
        f"{int(results['fdr_0_10'].sum())}"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"[U26B1] ERROR: {exc}",
            file=sys.stderr,
        )
        raise
