#!/usr/bin/env python3
"""
Phase U26B2B
Dataset-specific endocrine-metabolic-immune submodule scoring and
cross-dataset standardized-effect integration.

Datasets:
- GSE186800: mouse bladder Gardnerella/PBS exposure design.
- GSE112098: human urine sepsis vs vascular-surgery comparator.
- GSE252321: mouse bladder whole-object sample pseudobulk, UPEC vs control.
- GSE280297: previously refined pregnancy-tissue evidence imported from U26B1.1.

Rules:
- Score each dataset separately in its native species/technology context.
- Never pool raw expression across species or tissues.
- Use biological samples as inferential units.
- Treat GSE112098 as a urinary systemic-inflammation comparator.
- Treat GSE252321 whole-object pseudobulk as exploratory because n=2 per group.
- Keep cell-type pseudobulk deferred.
- Do not modify the manuscript or existing Figures 1-6.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import itertools
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
        "ERROR: scipy is required. Install with conda or pip."
    ) from exc

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit(
        "ERROR: matplotlib is required. Install with conda or pip."
    ) from exc


VERSION = "U26B2B_v1.0_2026-07-14"
PHASE_TAG = "phaseU26B2B_cross_dataset_scoring_integration"
RANDOM_SEED = 2622


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
    "PREGNANCY_RISK_ENDOCRINE_METABOLIC_INFLAMMATION_INDEX": {
        "positive": [
            "STEROID_INFLAMMATORY_IMBALANCE_INDEX",
            "INFLAMMATORY_CARBON_USE_INDEX",
            "COMPLEMENT_INFLAMMATORY_AMPLIFICATION_INDEX",
            "PREGNANCY_INFLAMMATION_ANCHOR",
            "EICOSANOID_PROSTAGLANDIN_METABOLISM",
            "FERROPTOSIS_LIPID_PEROXIDATION",
        ],
        "negative": [
            "UROTHELIAL_BARRIER_REPAIR_ANCHOR",
            "PROGESTERONE_BIOSYNTHESIS_RESPONSE",
        ],
    },
}


def log(message: str) -> None:
    print(f"[U26B2B] {message}", flush=True)


def read_tsv(path: Path, dtype=None) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        compression="infer",
        dtype=dtype,
        low_memory=False,
    )


def normalize_token(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value).strip()).lower()


def parse_gene_list(value: object) -> List[str]:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return sorted(
        {
            token.strip().upper()
            for token in re.split(r"[;,| ]+", text)
            if token.strip()
            and token.strip().lower() != "nan"
        }
    )


def load_library(path: Path) -> pd.DataFrame:
    library = read_tsv(path, dtype=str)
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
            f"Module library missing required columns: {missing}"
        )
    library = library.copy()
    library["gene_list"] = library["genes"].map(parse_gene_list)
    library["n_library_genes"] = library["gene_list"].map(len)
    return library


def load_expression(path: Path) -> pd.DataFrame:
    frame = read_tsv(path)
    if "gene_symbol" not in frame.columns:
        raise RuntimeError(f"gene_symbol column not found in {path}")
    frame = frame.copy()
    frame["gene_symbol"] = (
        frame["gene_symbol"].astype(str).str.strip().str.upper()
    )
    frame = frame.drop_duplicates("gene_symbol", keep="first")
    frame = frame.set_index("gene_symbol")
    for column in frame.columns:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )
    return frame


def zscore_rows(frame: pd.DataFrame) -> pd.DataFrame:
    means = frame.mean(axis=1, skipna=True)
    standard_deviations = frame.std(axis=1, skipna=True, ddof=1)
    standard_deviations = standard_deviations.replace(0, np.nan)
    return (
        frame.sub(means, axis=0)
        .div(standard_deviations, axis=0)
        .fillna(0.0)
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


def score_modules(
    expression: pd.DataFrame,
    library: pd.DataFrame,
    sample_metadata: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    universe = set(expression.index)
    z = zscore_rows(expression)

    coverage_rows = []
    scores = sample_metadata.copy()

    if "sample_id" not in scores.columns:
        raise RuntimeError("sample_metadata requires sample_id")

    score_sample_order = scores["sample_id"].astype(str).tolist()

    for _, module in library.iterrows():
        module_id = str(module["submodule_id"])
        genes = list(module["gene_list"])
        detected = [gene for gene in genes if gene in universe]
        classification = coverage_class(len(genes), len(detected))
        eligible = (
            classification in {"adequate", "partial"}
            and len(detected) >= 3
        )

        coverage_rows.append(
            {
                "axis": module["axis"],
                "submodule_id": module_id,
                "display_label": module["display_label"],
                "proposed_figure_family": module[
                    "proposed_figure_family"
                ],
                "n_library_genes": len(genes),
                "n_detected_genes": len(detected),
                "coverage_fraction": (
                    round(len(detected) / len(genes), 4)
                    if genes
                    else ""
                ),
                "coverage_class": classification,
                "score_eligible": eligible,
                "detected_genes": ";".join(detected),
            }
        )

        if eligible:
            scores[module_id] = (
                z.loc[detected]
                .mean(axis=0)
                .reindex(score_sample_order)
                .to_numpy()
            )

    return scores, pd.DataFrame(coverage_rows)


def add_composites(scores: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    scores = scores.copy()
    rows = []

    for composite_id, definition in COMPOSITE_DEFINITIONS.items():
        positive = [
            feature
            for feature in definition["positive"]
            if feature in scores.columns
        ]
        negative = [
            feature
            for feature in definition["negative"]
            if feature in scores.columns
        ]

        if positive:
            positive_score = scores[positive].mean(axis=1)
        else:
            positive_score = pd.Series(np.nan, index=scores.index)

        if negative:
            negative_score = scores[negative].mean(axis=1)
        else:
            negative_score = pd.Series(0.0, index=scores.index)

        scores[composite_id] = positive_score - negative_score

        rows.append(
            {
                "composite_index": composite_id,
                "positive_components_available": ";".join(positive),
                "negative_components_available": ";".join(negative),
                "n_positive_available": len(positive),
                "n_negative_available": len(negative),
                "computable": bool(positive),
            }
        )

    return scores, pd.DataFrame(rows)


def feature_metadata(
    library: pd.DataFrame,
    coverage_tables: Sequence[pd.DataFrame],
) -> pd.DataFrame:
    eligible_ids = set()
    for coverage in coverage_tables:
        eligible_ids.update(
            coverage.loc[
                coverage["score_eligible"],
                "submodule_id",
            ].astype(str)
        )

    modules = library[
        library["submodule_id"].astype(str).isin(eligible_ids)
    ][
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

    composites = pd.DataFrame(
        [
            {
                "axis": "composite_index",
                "feature_id": composite_id,
                "display_label": composite_id.replace("_", " ").title(),
                "proposed_figure_family": "Integrated_network",
                "feature_type": "composite_index",
            }
            for composite_id in COMPOSITE_DEFINITIONS
        ]
    )

    return pd.concat([modules, composites], ignore_index=True)


def bh_fdr(values: Sequence[float]) -> np.ndarray:
    p_values = np.asarray(values, dtype=float)
    output = np.full(p_values.shape, np.nan)

    finite_indices = np.where(np.isfinite(p_values))[0]
    if len(finite_indices) == 0:
        return output

    observed = p_values[finite_indices]
    order = np.argsort(observed)
    ranked = observed[order]
    n = len(ranked)

    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)

    restored = np.empty(n)
    restored[order] = adjusted
    output[finite_indices] = restored
    return output


def hedges_g(group_a: np.ndarray, group_b: np.ndarray) -> float:
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]

    if len(a) < 2 or len(b) < 2:
        return float("nan")

    pooled_variance = (
        (len(a) - 1) * np.var(a, ddof=1)
        + (len(b) - 1) * np.var(b, ddof=1)
    ) / (len(a) + len(b) - 2)

    if pooled_variance <= 0:
        return 0.0

    d = (np.mean(a) - np.mean(b)) / math.sqrt(pooled_variance)
    correction = 1 - 3 / (4 * (len(a) + len(b)) - 9)
    return float(correction * d)


def auc_group_a_higher(group_a: np.ndarray, group_b: np.ndarray) -> float:
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]

    if len(a) == 0 or len(b) == 0:
        return float("nan")

    combined = np.concatenate([a, b])
    ranks = stats.rankdata(combined)
    rank_sum_a = np.sum(ranks[: len(a)])
    u_a = rank_sum_a - len(a) * (len(a) + 1) / 2
    return float(u_a / (len(a) * len(b)))


def permutation_p(
    group_a: np.ndarray,
    group_b: np.ndarray,
    rng: np.random.Generator,
    max_exact: int = 5000,
    monte_carlo_iterations: int = 10000,
) -> Tuple[float, str, int]:
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]

    if len(a) < 2 or len(b) < 2:
        return float("nan"), "unavailable", 0

    pooled = np.concatenate([a, b])
    observed = abs(float(np.mean(a) - np.mean(b)))
    total_n = len(pooled)
    combinations_count = math.comb(total_n, len(a))

    if combinations_count <= max_exact:
        extreme = 0
        total = 0
        all_indices = np.arange(total_n)
        for selected_tuple in itertools.combinations(
            range(total_n),
            len(a),
        ):
            selected = np.fromiter(
                selected_tuple,
                dtype=int,
                count=len(a),
            )
            mask = np.ones(total_n, dtype=bool)
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
        return float(extreme / total), "exact", total

    extreme = 0
    for _ in range(monte_carlo_iterations):
        permutation = rng.permutation(total_n)
        selected = permutation[: len(a)]
        complement = permutation[len(a) :]
        statistic = abs(
            float(
                np.mean(pooled[selected])
                - np.mean(pooled[complement])
            )
        )
        extreme += int(statistic >= observed - 1e-12)

    return (
        float((extreme + 1) / (monte_carlo_iterations + 1)),
        "monte_carlo",
        monte_carlo_iterations,
    )


def two_group_results(
    scores: pd.DataFrame,
    group_column: str,
    group_a_label: str,
    group_b_label: str,
    feature_info: pd.DataFrame,
    dataset: str,
    contrast_id: str,
    biological_context: str,
    evidence_tier: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    lookup = (
        feature_info.drop_duplicates("feature_id")
        .set_index("feature_id")
        .to_dict("index")
    )
    features = [
        feature
        for feature in feature_info["feature_id"].astype(str)
        if feature in scores.columns
    ]

    group_a = scores[scores[group_column] == group_a_label]
    group_b = scores[scores[group_column] == group_b_label]

    if len(group_a) < 2 or len(group_b) < 2:
        return pd.DataFrame()

    rows = []
    for feature in features:
        a = pd.to_numeric(group_a[feature], errors="coerce").to_numpy(dtype=float)
        b = pd.to_numeric(group_b[feature], errors="coerce").to_numpy(dtype=float)
        a = a[np.isfinite(a)]
        b = b[np.isfinite(b)]

        if len(a) < 2 or len(b) < 2:
            continue

        welch = stats.ttest_ind(
            a,
            b,
            equal_var=False,
            nan_policy="omit",
        )
        perm_p, perm_method, n_perm = permutation_p(a, b, rng)
        metadata = lookup.get(feature, {})

        rows.append(
            {
                "dataset": dataset,
                "contrast_id": contrast_id,
                "biological_context": biological_context,
                "evidence_tier": evidence_tier,
                "group_a": group_a_label,
                "group_b": group_b_label,
                "n_group_a": len(a),
                "n_group_b": len(b),
                "feature_type": metadata.get("feature_type", "submodule"),
                "axis": metadata.get("axis", ""),
                "feature_id": feature,
                "display_label": metadata.get("display_label", feature),
                "proposed_figure_family": metadata.get(
                    "proposed_figure_family",
                    "Integrated_network",
                ),
                "mean_group_a": float(np.mean(a)),
                "mean_group_b": float(np.mean(b)),
                "mean_difference_a_minus_b": float(np.mean(a) - np.mean(b)),
                "hedges_g": hedges_g(a, b),
                "welch_p_value": float(welch.pvalue),
                "permutation_p_value": perm_p,
                "permutation_method": perm_method,
                "n_permutations": n_perm,
                "auc_group_a_higher": auc_group_a_higher(a, b),
                "direction": (
                    "higher_in_group_a"
                    if np.mean(a) > np.mean(b)
                    else "higher_in_group_b"
                    if np.mean(a) < np.mean(b)
                    else "no_difference"
                ),
            }
        )

    results = pd.DataFrame(rows)
    if results.empty:
        return results

    results["permutation_q_within_contrast"] = bh_fdr(
        results["permutation_p_value"].to_numpy(dtype=float)
    )
    results["welch_q_within_contrast"] = bh_fdr(
        results["welch_p_value"].to_numpy(dtype=float)
    )
    results["permutation_fdr_0_05"] = (
        results["permutation_q_within_contrast"] < 0.05
    )
    results["permutation_fdr_0_10"] = (
        results["permutation_q_within_contrast"] < 0.10
    )
    return results


def infer_gse186800_design(design: pd.DataFrame) -> pd.DataFrame:
    design = design.copy()

    if "inferred_group" not in design.columns:
        raise RuntimeError("GSE186800 design lacks inferred_group")

    if "inferred_block" not in design.columns:
        if "source" in design.columns:
            design["inferred_block"] = (
                design["source"]
                .astype(str)
                .str.extract(r"_(1|2)\.", expand=False)
            )
        else:
            raise RuntimeError("GSE186800 design lacks inferred_block")

    design["treatment"] = np.where(
        design["inferred_group"]
        .astype(str)
        .str.contains("Gard", case=False, na=False),
        "Gardnerella",
        "PBS",
    )
    design["block"] = (
        design["inferred_block"]
        .astype(str)
        .str.extract(r"([12])", expand=False)
    )
    design["group4"] = (
        design["treatment"].astype(str)
        + "_"
        + design["block"].astype(str)
    )
    return design


def ols_fit(
    y: np.ndarray,
    X: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, float, int]:
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    finite = np.isfinite(y) & np.isfinite(X).all(axis=1)
    y = y[finite]
    X = X[finite]

    n, p = X.shape
    if n <= p:
        raise RuntimeError("Insufficient degrees of freedom for OLS")

    xtx_inverse = np.linalg.pinv(X.T @ X)
    beta = xtx_inverse @ X.T @ y
    residuals = y - X @ beta
    degrees_freedom = n - p
    sigma2 = float((residuals @ residuals) / degrees_freedom)
    covariance = xtx_inverse * sigma2
    return beta, covariance, sigma2, degrees_freedom


def ols_contrast(
    beta: np.ndarray,
    covariance: np.ndarray,
    contrast: np.ndarray,
    degrees_freedom: int,
) -> Tuple[float, float, float, float]:
    contrast = np.asarray(contrast, dtype=float)
    estimate = float(contrast @ beta)
    variance = float(contrast @ covariance @ contrast)
    standard_error = math.sqrt(max(variance, 0.0))
    if standard_error > 0:
        t_value = estimate / standard_error
        p_value = float(
            2
            * stats.t.sf(
                abs(t_value),
                degrees_freedom,
            )
        )
    else:
        t_value = 0.0
        p_value = 1.0
    return estimate, standard_error, float(t_value), p_value


def gse186800_factorial_results(
    scores: pd.DataFrame,
    feature_info: pd.DataFrame,
) -> pd.DataFrame:
    lookup = (
        feature_info.drop_duplicates("feature_id")
        .set_index("feature_id")
        .to_dict("index")
    )
    features = [
        feature
        for feature in feature_info["feature_id"].astype(str)
        if feature in scores.columns
    ]

    treatment = (scores["treatment"] == "Gardnerella").astype(float).to_numpy()
    block2 = (scores["block"] == "2").astype(float).to_numpy()
    interaction = treatment * block2
    X = np.column_stack(
        [
            np.ones(len(scores)),
            treatment,
            block2,
            interaction,
        ]
    )

    contrasts = {
        "GSE186800_TREATMENT_BLOCK1": (
            np.array([0, 1, 0, 0], dtype=float),
            "Gardnerella_vs_PBS_block1",
        ),
        "GSE186800_TREATMENT_BLOCK2": (
            np.array([0, 1, 0, 1], dtype=float),
            "Gardnerella_vs_PBS_block2",
        ),
        "GSE186800_BLOCK_MAIN_PBS": (
            np.array([0, 0, 1, 0], dtype=float),
            "PBS_block2_vs_block1",
        ),
        "GSE186800_INTERACTION_RECURRENCE": (
            np.array([0, 0, 0, 1], dtype=float),
            "difference_in_differences_block2_minus_block1",
        ),
        "GSE186800_AVERAGE_TREATMENT": (
            np.array([0, 1, 0, 0.5], dtype=float),
            "average_Gardnerella_vs_PBS",
        ),
    }

    rows = []
    for feature in features:
        y = pd.to_numeric(scores[feature], errors="coerce").to_numpy(dtype=float)
        try:
            beta, covariance, _, degrees_freedom = ols_fit(y, X)
        except Exception:
            continue

        metadata = lookup.get(feature, {})

        for contrast_id, (contrast_vector, label) in contrasts.items():
            estimate, standard_error, t_value, p_value = ols_contrast(
                beta,
                covariance,
                contrast_vector,
                degrees_freedom,
            )

            rows.append(
                {
                    "dataset": "GSE186800",
                    "contrast_id": contrast_id,
                    "biological_context": "bladder_exposure_recurrence_model",
                    "evidence_tier": "independent_mouse_bulk",
                    "group_a": label,
                    "group_b": "reference",
                    "n_group_a": len(scores),
                    "n_group_b": "",
                    "feature_type": metadata.get("feature_type", "submodule"),
                    "axis": metadata.get("axis", ""),
                    "feature_id": feature,
                    "display_label": metadata.get("display_label", feature),
                    "proposed_figure_family": metadata.get(
                        "proposed_figure_family",
                        "Integrated_network",
                    ),
                    "mean_group_a": "",
                    "mean_group_b": "",
                    "mean_difference_a_minus_b": estimate,
                    "hedges_g": "",
                    "model_estimate": estimate,
                    "model_standard_error": standard_error,
                    "model_t_value": t_value,
                    "model_p_value": p_value,
                    "degrees_freedom": degrees_freedom,
                    "direction": (
                        "positive"
                        if estimate > 0
                        else "negative"
                        if estimate < 0
                        else "no_difference"
                    ),
                }
            )

    results = pd.DataFrame(rows)
    if results.empty:
        return results

    results["model_q_within_contrast"] = np.nan
    for contrast_id, indices in results.groupby("contrast_id").groups.items():
        index_list = list(indices)
        results.loc[
            index_list,
            "model_q_within_contrast",
        ] = bh_fdr(
            results.loc[index_list, "model_p_value"].to_numpy(dtype=float)
        )

    results["model_fdr_0_05"] = results["model_q_within_contrast"] < 0.05
    results["model_fdr_0_10"] = results["model_q_within_contrast"] < 0.10
    return results


def discover_group_mapping(
    project: Path,
    accession: str,
    sample_ids: Sequence[str],
) -> Tuple[Dict[str, str], pd.DataFrame]:
    roots = [
        project / "03_metadata",
        project / "06_tables",
        project / "07_tables",
        project / "05_results",
    ]
    candidate_rows = []
    best_mapping: Dict[str, str] = {}
    best_score = -1.0

    sample_tokens = {
        normalize_token(sample): str(sample)
        for sample in sample_ids
    }

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob(f"*{accession}*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".tsv", ".csv", ".txt", ".gz"}:
                continue

            lower_name = path.name.lower()
            if any(
                token in lower_name
                for token in [
                    "contrast",
                    "coverage",
                    "decision",
                    "report",
                    "summary",
                    "score",
                    "figure",
                ]
            ):
                continue

            try:
                separator = "\t"
                if path.suffix.lower() == ".gz":
                    opener = gzip.open
                else:
                    opener = open

                with opener(
                    path,
                    "rt",
                    encoding="utf-8",
                    errors="replace",
                ) as handle:
                    first_line = handle.readline()
                    separator = (
                        "\t"
                        if first_line.count("\t") >= first_line.count(",")
                        else ","
                    )

                frame = pd.read_csv(
                    path,
                    sep=separator,
                    compression="infer",
                    dtype=str,
                    nrows=1000,
                    low_memory=False,
                )
            except Exception:
                continue

            if frame.empty:
                continue

            sample_column = ""
            sample_overlap = 0.0
            for column in frame.columns:
                values = {
                    normalize_token(value)
                    for value in frame[column].dropna().astype(str)
                }
                overlap = (
                    len(set(sample_tokens) & values)
                    / len(sample_tokens)
                    if sample_tokens
                    else 0.0
                )
                if overlap > sample_overlap:
                    sample_overlap = overlap
                    sample_column = str(column)

            if sample_overlap < 0.50 or not sample_column:
                continue

            for group_column in frame.columns:
                if str(group_column) == sample_column:
                    continue

                mapping = {}
                for _, row in frame.iterrows():
                    token = normalize_token(row.get(sample_column, ""))
                    if token not in sample_tokens:
                        continue
                    text = str(row.get(group_column, "")).lower()
                    if "sepsis" in text:
                        mapping[sample_tokens[token]] = "sepsis"
                    elif "vascular" in text or "surgery" in text:
                        mapping[sample_tokens[token]] = "vascular_surgery"

                n_sepsis = sum(value == "sepsis" for value in mapping.values())
                n_surgery = sum(
                    value == "vascular_surgery"
                    for value in mapping.values()
                )
                completeness = len(mapping) / len(sample_ids)
                score = (
                    1000 * completeness
                    + 5 * min(n_sepsis, 41)
                    + 5 * min(n_surgery, 32)
                )

                if mapping:
                    candidate_rows.append(
                        {
                            "path": str(path),
                            "sample_column": sample_column,
                            "group_column": str(group_column),
                            "sample_overlap_fraction": sample_overlap,
                            "n_mapped": len(mapping),
                            "n_sepsis": n_sepsis,
                            "n_vascular_surgery": n_surgery,
                            "completeness": completeness,
                            "selection_score": score,
                        }
                    )

                if score > best_score:
                    best_score = score
                    best_mapping = mapping

    return best_mapping, pd.DataFrame(candidate_rows)


def infer_group_from_design_text(design: pd.DataFrame) -> Dict[str, str]:
    mapping = {}
    for _, row in design.iterrows():
        sample_id = str(row["sample_id"])
        text = " | ".join(
            str(value)
            for value in row.values
            if str(value).lower() != "nan"
        ).lower()
        if "sepsis" in text:
            mapping[sample_id] = "sepsis"
        elif "vascular" in text or "surgery" in text:
            mapping[sample_id] = "vascular_surgery"
    return mapping


def parse_age_sex(design: pd.DataFrame) -> pd.DataFrame:
    design = design.copy()

    row_text = design.astype(str).agg(" | ".join, axis=1)

    design["age"] = pd.to_numeric(
        row_text.str.extract(
            r"age\s*:\s*([0-9]+(?:\.[0-9]+)?)",
            flags=re.I,
            expand=False,
        ),
        errors="coerce",
    )
    sex_text = row_text.str.extract(
        r"(?:gender|sex)\s*:\s*(male|female)",
        flags=re.I,
        expand=False,
    )
    design["sex"] = sex_text.str.lower()
    return design


def adjusted_human_results(
    scores: pd.DataFrame,
    feature_info: pd.DataFrame,
) -> pd.DataFrame:
    lookup = (
        feature_info.drop_duplicates("feature_id")
        .set_index("feature_id")
        .to_dict("index")
    )
    features = [
        feature
        for feature in feature_info["feature_id"].astype(str)
        if feature in scores.columns
    ]

    group_indicator = (scores["comparison_group"] == "sepsis").astype(float)
    age = pd.to_numeric(scores["age"], errors="coerce")
    age_centered = age - age.mean(skipna=True)
    sex_male = (scores["sex"] == "male").astype(float)

    X = np.column_stack(
        [
            np.ones(len(scores)),
            group_indicator.to_numpy(dtype=float),
            age_centered.fillna(0.0).to_numpy(dtype=float),
            sex_male.to_numpy(dtype=float),
        ]
    )

    rows = []
    for feature in features:
        y = pd.to_numeric(scores[feature], errors="coerce").to_numpy(dtype=float)
        try:
            beta, covariance, _, degrees_freedom = ols_fit(y, X)
            estimate, standard_error, t_value, p_value = ols_contrast(
                beta,
                covariance,
                np.array([0, 1, 0, 0], dtype=float),
                degrees_freedom,
            )
        except Exception:
            continue

        metadata = lookup.get(feature, {})
        rows.append(
            {
                "dataset": "GSE112098",
                "contrast_id": "GSE112098_SEPSIS_VS_VASCULAR_SURGERY_ADJUSTED",
                "biological_context": (
                    "human_urinary_systemic_inflammation_comparator"
                ),
                "evidence_tier": "human_comparator_adjusted",
                "group_a": "sepsis",
                "group_b": "vascular_surgery",
                "n_group_a": int((scores["comparison_group"] == "sepsis").sum()),
                "n_group_b": int(
                    (scores["comparison_group"] == "vascular_surgery").sum()
                ),
                "feature_type": metadata.get("feature_type", "submodule"),
                "axis": metadata.get("axis", ""),
                "feature_id": feature,
                "display_label": metadata.get("display_label", feature),
                "proposed_figure_family": metadata.get(
                    "proposed_figure_family",
                    "Integrated_network",
                ),
                "model_estimate": estimate,
                "model_standard_error": standard_error,
                "model_t_value": t_value,
                "model_p_value": p_value,
                "degrees_freedom": degrees_freedom,
                "direction": (
                    "positive"
                    if estimate > 0
                    else "negative"
                    if estimate < 0
                    else "no_difference"
                ),
            }
        )

    results = pd.DataFrame(rows)
    if results.empty:
        return results

    results["model_q_within_contrast"] = bh_fdr(
        results["model_p_value"].to_numpy(dtype=float)
    )
    results["model_fdr_0_05"] = results["model_q_within_contrast"] < 0.05
    results["model_fdr_0_10"] = results["model_q_within_contrast"] < 0.10
    return results


def import_gse280297_results(project: Path) -> pd.DataFrame:
    path = (
        project
        / "06_tables"
        / "phaseU26B1_1_GSE280297_stability_refinement"
        / "UTI_HostOmics_U26B1_1_primary_results.tsv"
    )
    if not path.exists():
        return pd.DataFrame()

    source = read_tsv(path)
    rows = []

    for _, row in source.iterrows():
        rows.append(
            {
                "dataset": "GSE280297",
                "contrast_id": str(row["contrast_id"])
                + "__"
                + str(row["tissue"]),
                "biological_context": (
                    "pregnancy_tissue_UPEC_or_preterm_architecture"
                ),
                "evidence_tier": "pregnancy_tissue_discovery",
                "group_a": row["group_a"],
                "group_b": row["group_b"],
                "n_group_a": row["n_group_a"],
                "n_group_b": row["n_group_b"],
                "feature_type": row["feature_type"],
                "axis": row["axis"],
                "feature_id": row["feature_id"],
                "display_label": row["display_label"],
                "proposed_figure_family": row[
                    "proposed_figure_family"
                ],
                "effect_value": row["hedges_g"],
                "effect_metric": "hedges_g",
                "p_value": row["permutation_p_value"],
                "q_value": row[
                    "permutation_q_within_contrast"
                ],
                "fdr_0_10": row["permutation_fdr_0_10"],
                "direction": (
                    "positive"
                    if float(row["hedges_g"]) > 0
                    else "negative"
                    if float(row["hedges_g"]) < 0
                    else "no_difference"
                ),
            }
        )

    return pd.DataFrame(rows)


def harmonize_effects(
    gse186800_factorial: pd.DataFrame,
    gse186800_pairwise: pd.DataFrame,
    gse112098_unadjusted: pd.DataFrame,
    gse112098_adjusted: pd.DataFrame,
    gse252321: pd.DataFrame,
    gse280297: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    def add_pairwise(frame: pd.DataFrame):
        if frame.empty:
            return
        for _, row in frame.iterrows():
            rows.append(
                {
                    "dataset": row["dataset"],
                    "contrast_id": row["contrast_id"],
                    "biological_context": row["biological_context"],
                    "evidence_tier": row["evidence_tier"],
                    "group_a": row["group_a"],
                    "group_b": row["group_b"],
                    "feature_type": row["feature_type"],
                    "axis": row["axis"],
                    "feature_id": row["feature_id"],
                    "display_label": row["display_label"],
                    "proposed_figure_family": row[
                        "proposed_figure_family"
                    ],
                    "effect_value": row["hedges_g"],
                    "effect_metric": "hedges_g",
                    "p_value": row["permutation_p_value"],
                    "q_value": row[
                        "permutation_q_within_contrast"
                    ],
                    "fdr_0_10": row["permutation_fdr_0_10"],
                    "direction": (
                        "positive"
                        if float(row["hedges_g"]) > 0
                        else "negative"
                        if float(row["hedges_g"]) < 0
                        else "no_difference"
                    ),
                }
            )

    def add_model(frame: pd.DataFrame):
        if frame.empty:
            return
        for _, row in frame.iterrows():
            rows.append(
                {
                    "dataset": row["dataset"],
                    "contrast_id": row["contrast_id"],
                    "biological_context": row["biological_context"],
                    "evidence_tier": row["evidence_tier"],
                    "group_a": row["group_a"],
                    "group_b": row["group_b"],
                    "feature_type": row["feature_type"],
                    "axis": row["axis"],
                    "feature_id": row["feature_id"],
                    "display_label": row["display_label"],
                    "proposed_figure_family": row[
                        "proposed_figure_family"
                    ],
                    "effect_value": row["model_estimate"],
                    "effect_metric": "standardized_module_score_beta",
                    "p_value": row["model_p_value"],
                    "q_value": row["model_q_within_contrast"],
                    "fdr_0_10": row["model_fdr_0_10"],
                    "direction": row["direction"],
                }
            )

    add_model(gse186800_factorial)
    add_pairwise(gse186800_pairwise)
    add_pairwise(gse112098_unadjusted)
    add_model(gse112098_adjusted)
    add_pairwise(gse252321)

    if not gse280297.empty:
        rows.extend(gse280297.to_dict("records"))

    return pd.DataFrame(rows)


def infection_context_filter(evidence: pd.DataFrame) -> pd.DataFrame:
    permitted = {
        "C2_UPEC_VS_PBS_PREGNANCY__bladder",
        "C2_UPEC_VS_PBS_PREGNANCY__uterus",
        "C2_UPEC_VS_PBS_PREGNANCY__placenta",
        "GSE186800_TREATMENT_BLOCK1",
        "GSE186800_TREATMENT_BLOCK2",
        "GSE186800_AVERAGE_TREATMENT",
        "GSE112098_SEPSIS_VS_VASCULAR_SURGERY",
        "GSE112098_SEPSIS_VS_VASCULAR_SURGERY_ADJUSTED",
        "GSE252321_UPEC_VS_CONTROL",
    }
    return evidence[evidence["contrast_id"].isin(permitted)].copy()


def cross_dataset_recurrence(evidence: pd.DataFrame) -> pd.DataFrame:
    infection = infection_context_filter(evidence)
    infection = infection[infection["feature_type"] == "submodule"].copy()

    if infection.empty:
        return pd.DataFrame()

    infection["effect_value"] = pd.to_numeric(
        infection["effect_value"],
        errors="coerce",
    )
    infection["large_effect"] = (
        np.abs(infection["effect_value"]) >= 0.80
    )
    infection["moderate_effect"] = (
        np.abs(infection["effect_value"]) >= 0.50
    )
    infection["positive_effect"] = infection["effect_value"] > 0
    infection["negative_effect"] = infection["effect_value"] < 0
    infection["fdr10_bool"] = (
        infection["fdr_0_10"]
        .astype(str)
        .str.lower()
        .isin(["true", "1"])
    )

    rows = []
    grouping = [
        "feature_id",
        "axis",
        "display_label",
        "proposed_figure_family",
    ]

    for keys, group in infection.groupby(grouping):
        datasets = sorted(group["dataset"].astype(str).unique())
        positive = int(group["positive_effect"].sum())
        negative = int(group["negative_effect"].sum())
        nonzero = positive + negative
        coherence = (
            max(positive, negative) / nonzero
            if nonzero
            else 0.0
        )

        dataset_large_support = 0
        dataset_moderate_support = 0
        for dataset, dataset_group in group.groupby("dataset"):
            maximum = float(
                np.nanmax(
                    np.abs(
                        pd.to_numeric(
                            dataset_group["effect_value"],
                            errors="coerce",
                        )
                    )
                )
            )
            dataset_large_support += int(maximum >= 0.80)
            dataset_moderate_support += int(maximum >= 0.50)

        rows.append(
            {
                "feature_id": keys[0],
                "axis": keys[1],
                "display_label": keys[2],
                "proposed_figure_family": keys[3],
                "n_effect_contexts": len(group),
                "n_datasets": len(datasets),
                "datasets": ";".join(datasets),
                "n_positive_contexts": positive,
                "n_negative_contexts": negative,
                "directional_coherence_fraction": coherence,
                "dominant_direction": (
                    "positive"
                    if positive > negative
                    else "negative"
                    if negative > positive
                    else "mixed"
                ),
                "median_effect": float(
                    np.nanmedian(group["effect_value"])
                ),
                "median_absolute_effect": float(
                    np.nanmedian(np.abs(group["effect_value"]))
                ),
                "max_absolute_effect": float(
                    np.nanmax(np.abs(group["effect_value"]))
                ),
                "n_large_effect_contexts": int(
                    group["large_effect"].sum()
                ),
                "n_moderate_effect_contexts": int(
                    group["moderate_effect"].sum()
                ),
                "n_datasets_large_effect": dataset_large_support,
                "n_datasets_moderate_effect": dataset_moderate_support,
                "n_FDR10_contexts": int(group["fdr10_bool"].sum()),
            }
        )

    recurrence = pd.DataFrame(rows)

    recurrence["cross_dataset_priority_score"] = (
        1.5 * recurrence["n_datasets_moderate_effect"]
        + 2.5 * recurrence["n_datasets_large_effect"]
        + 1.0 * recurrence["n_moderate_effect_contexts"]
        + 1.5 * recurrence["n_large_effect_contexts"]
        + 3.0 * recurrence["n_FDR10_contexts"]
        + recurrence["median_absolute_effect"]
        + 0.5 * recurrence["directional_coherence_fraction"]
    )

    recurrence["validation_class"] = np.select(
        [
            recurrence["n_FDR10_contexts"] >= 2,
            (
                (recurrence["n_FDR10_contexts"] >= 1)
                & (recurrence["n_datasets_moderate_effect"] >= 2)
            ),
            recurrence["n_datasets_large_effect"] >= 2,
            recurrence["n_datasets_moderate_effect"] >= 3,
            recurrence["n_datasets_moderate_effect"] >= 2,
        ],
        [
            "multi_context_FDR_supported",
            "FDR_plus_independent_effect_support",
            "multi_dataset_large_effect",
            "broad_multi_dataset_moderate_effect",
            "two_dataset_moderate_effect",
        ],
        default="single_dataset_or_context_specific",
    )

    return recurrence.sort_values(
        [
            "cross_dataset_priority_score",
            "n_datasets",
        ],
        ascending=False,
    )


def evidence_matrix(evidence: pd.DataFrame) -> pd.DataFrame:
    modules = evidence[evidence["feature_type"] == "submodule"].copy()
    if modules.empty:
        return pd.DataFrame()

    modules["context"] = (
        modules["dataset"].astype(str)
        + " | "
        + modules["contrast_id"].astype(str)
    )
    modules["effect_value"] = pd.to_numeric(
        modules["effect_value"],
        errors="coerce",
    )

    return modules.pivot_table(
        index="feature_id",
        columns="context",
        values="effect_value",
        aggfunc="first",
    )


def save_heatmap(
    matrix: pd.DataFrame,
    output_stem: Path,
    title: str,
    top_features: Optional[Sequence[str]] = None,
) -> None:
    if matrix.empty:
        return

    plot_matrix = matrix.copy()
    if top_features:
        selected = [
            feature
            for feature in top_features
            if feature in plot_matrix.index
        ]
        if selected:
            plot_matrix = plot_matrix.loc[selected]

    width = max(11.0, 0.65 * len(plot_matrix.columns) + 5.0)
    height = max(6.0, 0.34 * len(plot_matrix.index) + 2.5)

    figure = plt.figure(figsize=(width, height))
    axis = figure.add_axes([0.28, 0.19, 0.60, 0.68])

    image = axis.imshow(
        plot_matrix.to_numpy(dtype=float),
        aspect="auto",
    )
    axis.set_xticks(np.arange(len(plot_matrix.columns)))
    axis.set_xticklabels(
        plot_matrix.columns,
        rotation=60,
        ha="right",
        fontsize=7,
    )
    axis.set_yticks(np.arange(len(plot_matrix.index)))
    axis.set_yticklabels(plot_matrix.index, fontsize=8)
    axis.set_title(title)
    axis.set_xlabel("Dataset-specific biological context")
    axis.set_ylabel("Submodule")

    colorbar = figure.colorbar(
        image,
        ax=axis,
        fraction=0.035,
        pad=0.04,
    )
    colorbar.set_label(
        "Standardized module effect\n"
        "(Hedges' g or standardized-score beta)"
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
    gse186800_factorial: pd.DataFrame,
    gse112098_unadjusted: pd.DataFrame,
    gse112098_adjusted: pd.DataFrame,
    gse252321: pd.DataFrame,
    recurrence: pd.DataFrame,
    human_status: str,
) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26B2B - Cross-dataset endocrine-metabolic-immune scoring\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(
            "- Manuscript and existing Figures 1-6 were not modified.\n"
        )
        handle.write(
            "- Raw expression was never pooled across datasets or species.\n"
        )
        handle.write(
            "- GSE252321 cell-type pseudobulk remains deferred.\n\n"
        )

        handle.write("## GSE186800\n\n")
        if gse186800_factorial.empty:
            handle.write("No factorial results were generated.\n\n")
        else:
            handle.write(
                f"- Factorial feature-level results: "
                f"**{len(gse186800_factorial)}**\n"
            )
            handle.write(
                f"- Results at model FDR < 0.05: "
                f"**{int(gse186800_factorial['model_fdr_0_05'].sum())}**\n"
            )
            handle.write(
                f"- Results at model FDR < 0.10: "
                f"**{int(gse186800_factorial['model_fdr_0_10'].sum())}**\n\n"
            )

            top = gse186800_factorial.sort_values(
                "model_q_within_contrast"
            ).head(20)
            for _, row in top.iterrows():
                handle.write(
                    f"- `{row['feature_id']}`, {row['contrast_id']}: "
                    f"beta={row['model_estimate']:.3f}, "
                    f"FDR={row['model_q_within_contrast']:.4g}.\n"
                )
            handle.write("\n")

        handle.write("## GSE112098\n\n")
        handle.write(f"- Group-resolution status: **{human_status}**\n")
        if gse112098_unadjusted.empty:
            handle.write(
                "- Human comparator scoring was not completed because "
                "sample-group labels were not resolved without assuming order.\n\n"
            )
        else:
            handle.write(
                f"- Unadjusted feature-level results: "
                f"**{len(gse112098_unadjusted)}**\n"
            )
            handle.write(
                f"- Unadjusted permutation FDR < 0.10: "
                f"**{int(gse112098_unadjusted['permutation_fdr_0_10'].sum())}**\n"
            )
            handle.write(
                f"- Age/sex-adjusted results: "
                f"**{len(gse112098_adjusted)}**\n"
            )
            handle.write(
                f"- Adjusted model FDR < 0.10: "
                f"**{int(gse112098_adjusted['model_fdr_0_10'].sum())}**\n\n"
            )

        handle.write("## GSE252321\n\n")
        if gse252321.empty:
            handle.write("No pseudobulk comparison was generated.\n\n")
        else:
            handle.write(
                f"- Whole-object pseudobulk results: "
                f"**{len(gse252321)}**\n"
            )
            handle.write(
                "- Group size was two control and two UPEC biological samples. "
                "Effects are exploratory; exact two-sided permutation p values "
                "cannot provide strong significance at this sample size.\n\n"
            )

        handle.write("## Cross-dataset recurrence\n\n")
        if recurrence.empty:
            handle.write("No integrated recurrence table was generated.\n\n")
        else:
            for _, row in recurrence.head(30).iterrows():
                handle.write(
                    f"- `{row['feature_id']}`: "
                    f"{row['validation_class']}; "
                    f"{int(row['n_datasets_moderate_effect'])} datasets with "
                    f"|effect|>=0.5; "
                    f"{int(row['n_datasets_large_effect'])} datasets with "
                    f"|effect|>=0.8; dominant direction "
                    f"{row['dominant_direction']} "
                    f"(coherence={row['directional_coherence_fraction']:.2f}).\n"
                )
            handle.write("\n")

        handle.write("## Interpretation rules\n\n")
        handle.write(
            "- GSE186800 represents a bladder exposure/recurrence model and "
            "does not reproduce the pregnancy design of GSE280297.\n"
        )
        handle.write(
            "- GSE112098 is a human urinary systemic-inflammation comparator, "
            "not a direct UTI cohort.\n"
        )
        handle.write(
            "- GSE252321 validates whole-study UPEC-responsive direction only; "
            "cell-type attribution awaits reconstructed annotations.\n"
        )
        handle.write(
            "- Cross-dataset recurrence supports pathway prioritization, but "
            "opposite directions can be biologically meaningful because tissue, "
            "host state and exposure differ.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    rng = np.random.default_rng(RANDOM_SEED)

    input_tag = "phaseU26B2A1_cross_dataset_input_repair"
    input_processed = project / "03_data_processed" / input_tag
    input_metadata = project / "03_metadata" / input_tag

    paths = {
        "GSE186800_expression": (
            input_processed
            / "GSE186800_U26B2A1_canonical_gene_symbol_expression.tsv.gz"
        ),
        "GSE186800_design": (
            input_metadata
            / "GSE186800_U26B2A1_validated_sample_design.tsv"
        ),
        "GSE112098_expression": (
            input_processed
            / "GSE112098_U26B2A1_canonical_gene_symbol_expression.tsv.gz"
        ),
        "GSE112098_design": (
            input_metadata
            / "GSE112098_U26B2A1_validated_sample_design.tsv"
        ),
        "GSE252321_expression": (
            input_processed
            / "GSE252321_U26B2A1_sample_level_pseudobulk_expression.tsv.gz"
        ),
        "GSE252321_design": (
            input_metadata
            / "GSE252321_U26B2A1_sample_level_pseudobulk_design.tsv"
        ),
        "library": (
            project
            / "03_metadata"
            / "phaseU26A_expanded_endocrine_metabolic_immune_feasibility"
            / "UTI_HostOmics_U26A_expanded_submodule_library.tsv"
        ),
    }

    for required in [
        paths["GSE186800_expression"],
        paths["GSE186800_design"],
        paths["GSE252321_expression"],
        paths["GSE252321_design"],
        paths["library"],
    ]:
        if not required.exists():
            raise FileNotFoundError(f"Required input not found: {required}")

    output_metadata = project / "03_metadata" / PHASE_TAG
    output_processed = project / "03_data_processed" / PHASE_TAG
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
        directory.mkdir(parents=True, exist_ok=True)

    library = load_library(paths["library"])

    # GSE186800
    log("Scoring GSE186800.")
    expression_186800 = load_expression(paths["GSE186800_expression"])
    design_186800 = read_tsv(paths["GSE186800_design"], dtype=str)
    design_186800 = infer_gse186800_design(design_186800)
    scores_186800, coverage_186800 = score_modules(
        expression_186800,
        library,
        design_186800,
    )
    scores_186800, composites_186800 = add_composites(scores_186800)

    # GSE252321
    log("Scoring GSE252321 sample pseudobulk.")
    expression_252321 = load_expression(paths["GSE252321_expression"])
    design_252321 = read_tsv(paths["GSE252321_design"], dtype=str)
    scores_252321, coverage_252321 = score_modules(
        expression_252321,
        library,
        design_252321,
    )
    scores_252321, composites_252321 = add_composites(scores_252321)

    # GSE112098
    human_available = (
        paths["GSE112098_expression"].exists()
        and paths["GSE112098_design"].exists()
    )
    scores_112098 = pd.DataFrame()
    coverage_112098 = pd.DataFrame()
    composites_112098 = pd.DataFrame()
    human_mapping_audit = pd.DataFrame()
    human_status = "inputs_missing"

    if human_available:
        log("Resolving and scoring GSE112098.")
        expression_112098 = load_expression(paths["GSE112098_expression"])
        design_112098 = read_tsv(paths["GSE112098_design"], dtype=str)
        design_112098 = parse_age_sex(design_112098)

        mapping = infer_group_from_design_text(design_112098)
        if len(mapping) < len(design_112098):
            discovered_mapping, human_mapping_audit = discover_group_mapping(
                project,
                "GSE112098",
                design_112098["sample_id"].astype(str).tolist(),
            )
            mapping.update(discovered_mapping)

        design_112098["comparison_group"] = (
            design_112098["sample_id"].astype(str).map(mapping)
        )

        n_sepsis = int(
            (design_112098["comparison_group"] == "sepsis").sum()
        )
        n_surgery = int(
            (
                design_112098["comparison_group"]
                == "vascular_surgery"
            ).sum()
        )

        if (
            n_sepsis >= 30
            and n_surgery >= 20
            and n_sepsis + n_surgery >= 65
        ):
            human_status = (
                f"resolved_{n_sepsis}_sepsis_"
                f"{n_surgery}_vascular_surgery"
            )
            scores_112098, coverage_112098 = score_modules(
                expression_112098,
                library,
                design_112098,
            )
            scores_112098, composites_112098 = add_composites(
                scores_112098
            )
        else:
            human_status = (
                f"unresolved_{n_sepsis}_sepsis_"
                f"{n_surgery}_vascular_surgery"
            )

        design_112098.to_csv(
            output_metadata
            / "GSE112098_U26B2B_resolved_scoring_design.tsv",
            sep="\t",
            index=False,
        )
        human_mapping_audit.to_csv(
            output_tables
            / "UTI_HostOmics_U26B2B_GSE112098_group_mapping_audit.tsv",
            sep="\t",
            index=False,
        )

    coverage_tables = [
        coverage_186800,
        coverage_252321,
    ]
    if not coverage_112098.empty:
        coverage_tables.append(coverage_112098)

    feature_info = feature_metadata(
        library,
        coverage_tables,
    )

    # Save scores and coverage.
    scores_186800.to_csv(
        output_processed
        / "GSE186800_U26B2B_submodule_scores.tsv.gz",
        sep="\t",
        index=False,
        compression="gzip",
    )
    coverage_186800.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_GSE186800_coverage.tsv",
        sep="\t",
        index=False,
    )

    scores_252321.to_csv(
        output_processed
        / "GSE252321_U26B2B_sample_pseudobulk_scores.tsv.gz",
        sep="\t",
        index=False,
        compression="gzip",
    )
    coverage_252321.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_GSE252321_coverage.tsv",
        sep="\t",
        index=False,
    )

    if not scores_112098.empty:
        scores_112098.to_csv(
            output_processed
            / "GSE112098_U26B2B_submodule_scores.tsv.gz",
            sep="\t",
            index=False,
            compression="gzip",
        )
        coverage_112098.to_csv(
            output_tables
            / "UTI_HostOmics_U26B2B_GSE112098_coverage.tsv",
            sep="\t",
            index=False,
        )

    pd.concat(
        [
            composites_186800.assign(dataset="GSE186800"),
            composites_252321.assign(dataset="GSE252321"),
            (
                composites_112098.assign(dataset="GSE112098")
                if not composites_112098.empty
                else pd.DataFrame()
            ),
        ],
        ignore_index=True,
    ).to_csv(
        output_metadata
        / "UTI_HostOmics_U26B2B_composite_index_blueprints.tsv",
        sep="\t",
        index=False,
    )

    feature_info.to_csv(
        output_metadata
        / "UTI_HostOmics_U26B2B_feature_metadata.tsv",
        sep="\t",
        index=False,
    )

    # GSE186800 factorial and planned pairwise contrasts.
    factorial_186800 = gse186800_factorial_results(
        scores_186800,
        feature_info,
    )
    factorial_186800.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_GSE186800_factorial_results.tsv",
        sep="\t",
        index=False,
    )

    pairwise_186800_parts = []
    for contrast_id, group_a, group_b, context in [
        (
            "GSE186800_GARDNERELLA1_VS_PBS1",
            "Gardnerella_1",
            "PBS_1",
            "first_exposure_bladder",
        ),
        (
            "GSE186800_GARDNERELLA2_VS_PBS2",
            "Gardnerella_2",
            "PBS_2",
            "second_exposure_bladder",
        ),
    ]:
        part = two_group_results(
            scores_186800,
            "group4",
            group_a,
            group_b,
            feature_info,
            "GSE186800",
            contrast_id,
            context,
            "independent_mouse_bulk",
            rng,
        )
        if not part.empty:
            pairwise_186800_parts.append(part)

    pairwise_186800 = (
        pd.concat(pairwise_186800_parts, ignore_index=True)
        if pairwise_186800_parts
        else pd.DataFrame()
    )
    pairwise_186800.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_GSE186800_pairwise_results.tsv",
        sep="\t",
        index=False,
    )

    # Human comparator.
    unadjusted_112098 = pd.DataFrame()
    adjusted_112098 = pd.DataFrame()

    if not scores_112098.empty:
        unadjusted_112098 = two_group_results(
            scores_112098,
            "comparison_group",
            "sepsis",
            "vascular_surgery",
            feature_info,
            "GSE112098",
            "GSE112098_SEPSIS_VS_VASCULAR_SURGERY",
            "human_urinary_systemic_inflammation_comparator",
            "human_comparator_unadjusted",
            rng,
        )
        adjusted_112098 = adjusted_human_results(
            scores_112098,
            feature_info,
        )

    unadjusted_112098.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_GSE112098_unadjusted_results.tsv",
        sep="\t",
        index=False,
    )
    adjusted_112098.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_GSE112098_age_sex_adjusted_results.tsv",
        sep="\t",
        index=False,
    )

    # GSE252321 exploratory comparison.
    results_252321 = two_group_results(
        scores_252321,
        "condition",
        "UPEC",
        "control",
        feature_info,
        "GSE252321",
        "GSE252321_UPEC_VS_CONTROL",
        "whole_object_sample_pseudobulk_UPEC_response",
        "exploratory_mouse_sample_pseudobulk",
        rng,
    )
    results_252321.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_GSE252321_sample_pseudobulk_results.tsv",
        sep="\t",
        index=False,
    )

    # Import GSE280297 and harmonize.
    imported_280297 = import_gse280297_results(project)
    evidence = harmonize_effects(
        factorial_186800,
        pairwise_186800,
        unadjusted_112098,
        adjusted_112098,
        results_252321,
        imported_280297,
    )
    evidence.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_harmonized_effect_evidence.tsv",
        sep="\t",
        index=False,
    )

    recurrence = cross_dataset_recurrence(evidence)
    recurrence.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_cross_dataset_recurrence_ranking.tsv",
        sep="\t",
        index=False,
    )

    matrix = evidence_matrix(evidence)
    matrix.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_effect_matrix.tsv",
        sep="\t",
    )

    top_features = (
        recurrence["feature_id"].head(40).astype(str).tolist()
        if not recurrence.empty
        else None
    )
    save_heatmap(
        matrix,
        output_figures
        / "UTI_HostOmics_U26B2B_cross_dataset_effect_heatmap",
        "Cross-dataset endocrine-metabolic-immune submodule effects",
        top_features=top_features,
    )

    for family in [
        "Figure_7",
        "Figure_8",
        "Figure_9",
        "Figure_10",
    ]:
        family_features = (
            recurrence.loc[
                recurrence["proposed_figure_family"] == family,
                "feature_id",
            ]
            .head(20)
            .astype(str)
            .tolist()
            if not recurrence.empty
            else []
        )
        save_heatmap(
            matrix,
            output_figures
            / f"UTI_HostOmics_U26B2B_{family}_cross_dataset_effect_heatmap",
            f"{family}: cross-dataset effect recurrence",
            top_features=family_features,
        )

    human_ready = not scores_112098.empty
    if human_ready:
        decision = (
            "READY_FOR_U26C_CROSS_DATASET_BIOLOGICAL_SYNTHESIS_"
            "CELLTYPE_RECONSTRUCTION_DEFERRED"
        )
    else:
        decision = (
            "READY_FOR_U26C_MOUSE_INTEGRATION_"
            "HUMAN_GROUP_LABEL_REVIEW_REQUIRED"
        )

    decision_table = pd.DataFrame(
        [
            {
                "phase": "U26B2B",
                "decision": decision,
                "GSE186800_factorial_results": len(factorial_186800),
                "GSE186800_model_FDR10": int(
                    factorial_186800["model_fdr_0_10"].sum()
                )
                if not factorial_186800.empty
                else 0,
                "GSE112098_group_status": human_status,
                "GSE112098_unadjusted_results": len(
                    unadjusted_112098
                ),
                "GSE112098_adjusted_model_FDR10": int(
                    adjusted_112098["model_fdr_0_10"].sum()
                )
                if not adjusted_112098.empty
                else 0,
                "GSE252321_sample_pseudobulk_results": len(
                    results_252321
                ),
                "GSE252321_cell_type_pseudobulk": "deferred",
                "integrated_module_rows": len(recurrence),
                "cross_species_rule": (
                    "Native-species scoring; integrate standardized "
                    "module effects and directions only."
                ),
                "human_comparator_rule": (
                    "Systemic urinary inflammation comparator, not UTI-specific."
                ),
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U26C biological synthesis, module convergence review, "
                    "and Figure 7-11 architecture planning"
                ),
            }
        ]
    )
    decision_table.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2B_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        output_results
        / "UTI_HostOmics_U26B2B_cross_dataset_scoring_report.md"
    )
    write_report(
        report_path,
        factorial_186800,
        unadjusted_112098,
        adjusted_112098,
        results_252321,
        recurrence,
        human_status,
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "decision": decision,
        "human_group_status": human_status,
        "human_scoring_completed": bool(human_ready),
        "GSE252321_cell_type_pseudobulk": "deferred",
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        output_results
        / "UTI_HostOmics_U26B2B_run_manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
        )
    )

    log(
        f"GSE186800 factorial FDR < 0.10: "
        f"{int(factorial_186800['model_fdr_0_10'].sum()) if not factorial_186800.empty else 0}"
    )
    log(f"GSE112098 status: {human_status}")
    log(
        f"GSE252321 sample-pseudobulk results: "
        f"{len(results_252321)}"
    )
    log(
        f"Integrated recurrence modules: "
        f"{len(recurrence)}"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26B2B] ERROR: {exc}", file=sys.stderr)
        raise
