#!/usr/bin/env python3
"""
Phase U26D2B
Refined sample-by-cell-type pseudobulk module scoring for GSE252321.

Scientific unit
---------------
The four biological samples are the independent units. Cells are aggregated
within each biological sample and refined cell population before pathway
scoring. No cell-level significance test is performed.

Outputs
-------
1. Broad-cell-type and refined-subtype pseudobulk manifests.
2. Module coverage against the common mouse gene universe.
3. UPEC-versus-control module effects within each cell population.
4. Gene-direction coherence and module-level mean/median log2 fold changes.
5. Cellular-localization summaries for the U26C core and Figure 7-10 modules.
6. Descriptive composition and fixed targeted-state effect summaries.
7. Heatmaps for broad-cell and subtype localization.
8. A phase decision for cellular synthesis and Figure 7-11 integration.

Statistical boundary
--------------------
With n=2 control and n=2 UPEC samples, the smallest possible exact two-sided
permutation p value is not conventionally significant. Effect sizes and
directional coherence are therefore primary; p and FDR values are retained
only as descriptive completeness checks.
"""

from __future__ import annotations

import argparse
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
    from scipy import sparse
except ImportError as exc:
    raise SystemExit("ERROR: scipy is required.") from exc

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit("ERROR: matplotlib is required.") from exc


VERSION = "U26D2B_v1.0_2026-07-14"
TAG = "phaseU26D2B_GSE252321_refined_celltype_pseudobulk"
ANNOTATION_TAG = "phaseU26D2A1_GSE252321_annotation_refinement"
MATRIX_TAG = "phaseU26D1A_GSE252321_flat_matrix_validation"
CORE_TAG = "phaseU26C1_interpretation_threshold_and_branch_refinement"

MIN_CELLS = 30
MIN_MODULE_GENES = 5
MIN_MODULE_COVERAGE = 0.35

FOCUS_MODULES = [
    "TLR4_LPS_SIGNALING_ANCHOR",
    "NFKB_MAPK_INFLAMMATION_ANCHOR",
    "NEUTROPHIL_NETOSIS_ANCHOR",
    "PREGNANCY_INFLAMMATION_ANCHOR",
    "LEPTIN_SIGNALING",
    "RESISTIN_INFLAMMATORY_SIGNALING",
    "INSULIN_RECEPTOR_IRS",
    "PI3K_AKT_SIGNALING",
    "GLYCOLYSIS",
    "LACTATE_HIF1A_INFLAMMATORY_GLYCOLYSIS",
    "GLYCOGEN_SYNTHESIS",
    "GLUCOCORTICOID_RESPONSE",
    "ESTROGEN_RECEPTOR_RESPONSE",
    "ANDROGEN_RECEPTOR_SIGNALING",
    "STEROIDOGENESIS_CORE",
    "ANDROGEN_TESTOSTERONE_BIOSYNTHESIS",
    "TESTOSTERONE_CONVERSION_AROMATIZATION",
    "FERROPTOSIS_LIPID_PEROXIDATION",
    "COMPLEMENT_CLASSICAL",
    "COMPLEMENT_ALTERNATIVE",
    "COMPLEMENT_TERMINAL_MAC",
    "COMPLEMENT_OPSONOPHAGOCYTOSIS",
    "COMPLEMENT_C3A_C5A_SIGNALING",
    "XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM",
    "ARGININE_NO_UREA",
    "NITRIC_OXIDE_SYNTHESIS_REGULATION",
]

COLUMN_ALIASES = {
    "feature_id": [
        "feature_id", "submodule_id", "module_id", "gene_set_id",
        "geneset_id", "set_id", "pathway_id",
    ],
    "gene_symbol": [
        "gene_symbol", "gene", "symbol", "member_gene", "gene_name",
    ],
    "gene_list": [
        "genes", "gene_symbols", "member_genes", "members",
        "gene_set", "geneset",
    ],
    "display_label": [
        "display_label", "feature_label", "submodule_label",
        "module_label", "pathway_label", "name",
    ],
    "axis": [
        "axis", "module_axis", "biological_axis", "domain",
    ],
    "figure": [
        "proposed_figure_family", "figure_family", "figure",
    ],
}


def log(message: str) -> None:
    print(f"[U26D2B] {message}", flush=True)


def read_table(path: Path) -> pd.DataFrame:
    suffixes = "".join(path.suffixes).lower()
    if ".csv" in suffixes:
        return pd.read_csv(path, compression="infer", low_memory=False)
    return pd.read_csv(
        path,
        sep="\t",
        compression="infer",
        low_memory=False,
    )


def normalize_column(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def normalize_gene(value: object) -> str:
    return str(value).strip().upper()


def find_column(columns: Sequence[str], aliases: Sequence[str]) -> Optional[str]:
    normalized = {normalize_column(column): str(column) for column in columns}
    for alias in aliases:
        token = normalize_column(alias)
        if token in normalized:
            return normalized[token]
    return None


def split_genes(value: object) -> List[str]:
    if pd.isna(value):
        return []
    text = str(value)
    parts = re.split(r"[;,|/\s]+", text)
    return [
        normalize_gene(part)
        for part in parts
        if normalize_gene(part)
        and normalize_gene(part) not in {"NA", "NAN", "NONE"}
    ]


def candidate_module_files(project: Path) -> List[Path]:
    roots = [
        project / "03_metadata",
        project / "06_tables",
        project / "07_tables",
        project / "05_results",
    ]
    paths: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in ("*.tsv", "*.tsv.gz", "*.csv", "*.csv.gz"):
            for path in root.rglob(pattern):
                text = str(path).lower()
                if TAG.lower() in text:
                    continue
                if path.stat().st_size > 150_000_000:
                    continue
                paths.append(path)
    return sorted(set(paths))


def inspect_module_candidate(path: Path) -> Optional[Dict[str, object]]:
    try:
        frame = read_table(path)
    except Exception:
        return None

    if frame.empty or frame.shape[1] < 2:
        return None

    feature_col = find_column(frame.columns, COLUMN_ALIASES["feature_id"])
    gene_col = find_column(frame.columns, COLUMN_ALIASES["gene_symbol"])
    gene_list_col = find_column(frame.columns, COLUMN_ALIASES["gene_list"])

    if feature_col is None or (gene_col is None and gene_list_col is None):
        return None

    unique_features = int(frame[feature_col].astype(str).nunique())
    if unique_features < 10:
        return None

    if gene_col is not None:
        gene_rows = int(frame[gene_col].notna().sum())
    else:
        gene_rows = int(
            frame[gene_list_col].fillna("").astype(str).map(
                lambda value: len(split_genes(value))
            ).sum()
        )

    if gene_rows < 50:
        return None

    path_text = str(path).lower()
    phase_bonus = 0
    if "u26a" in path_text:
        phase_bonus += 1000
    if "submodule" in path_text or "dictionary" in path_text:
        phase_bonus += 400
    if "geneset" in path_text or "gene_set" in path_text:
        phase_bonus += 250
    if "coverage" in path_text or "result" in path_text:
        phase_bonus -= 100

    score = phase_bonus + unique_features * 10 + min(gene_rows, 100000) / 100

    return {
        "path": path,
        "frame": frame,
        "feature_col": feature_col,
        "gene_col": gene_col,
        "gene_list_col": gene_list_col,
        "unique_features": unique_features,
        "gene_rows": gene_rows,
        "score": score,
    }


def canonicalize_modules(candidate: Dict[str, object]) -> pd.DataFrame:
    frame = candidate["frame"].copy()
    feature_col = str(candidate["feature_col"])
    gene_col = candidate["gene_col"]
    gene_list_col = candidate["gene_list_col"]

    display_col = find_column(frame.columns, COLUMN_ALIASES["display_label"])
    axis_col = find_column(frame.columns, COLUMN_ALIASES["axis"])
    figure_col = find_column(frame.columns, COLUMN_ALIASES["figure"])

    rows: List[Dict[str, str]] = []

    for _, item in frame.iterrows():
        feature_id = str(item[feature_col]).strip()
        if not feature_id or feature_id.lower() in {"nan", "none"}:
            continue

        if gene_col is not None:
            genes = [normalize_gene(item[gene_col])]
        else:
            genes = split_genes(item[gene_list_col])

        for gene in genes:
            if not gene or gene in {"NA", "NAN", "NONE"}:
                continue
            rows.append(
                {
                    "feature_id": feature_id,
                    "gene_symbol": gene,
                    "display_label": (
                        str(item[display_col]).strip()
                        if display_col is not None
                        else feature_id.replace("_", " ").title()
                    ),
                    "axis": (
                        str(item[axis_col]).strip()
                        if axis_col is not None
                        else "unresolved"
                    ),
                    "proposed_figure_family": (
                        str(item[figure_col]).strip()
                        if figure_col is not None
                        else "unresolved"
                    ),
                }
            )

    modules = pd.DataFrame(rows).drop_duplicates(
        ["feature_id", "gene_symbol"]
    )
    if modules["feature_id"].nunique() < 10:
        raise RuntimeError("Canonical module dictionary has too few modules.")
    return modules


def discover_modules(project: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    audits = []
    candidates = []

    for path in candidate_module_files(project):
        result = inspect_module_candidate(path)
        if result is None:
            continue
        audits.append(
            {
                "path": str(path),
                "unique_features": result["unique_features"],
                "gene_rows": result["gene_rows"],
                "selection_score": result["score"],
                "feature_column": result["feature_col"],
                "gene_column": result["gene_col"] or "",
                "gene_list_column": result["gene_list_col"] or "",
            }
        )
        candidates.append(result)

    if not candidates:
        raise RuntimeError(
            "No module dictionary containing feature IDs and gene symbols "
            "could be discovered."
        )

    candidates.sort(key=lambda item: float(item["score"]), reverse=True)

    last_error = ""
    for candidate in candidates:
        try:
            modules = canonicalize_modules(candidate)
            audit = pd.DataFrame(audits).sort_values(
                "selection_score", ascending=False
            )
            audit["selected"] = audit["path"].eq(str(candidate["path"]))
            modules.attrs["source_path"] = str(candidate["path"])
            return modules, audit
        except Exception as exc:
            last_error = str(exc)

    raise RuntimeError(f"Module dictionaries were found but unusable: {last_error}")


def load_manifest(project: Path) -> pd.DataFrame:
    path = (
        project / "03_metadata" / MATRIX_TAG
        / "UTI_HostOmics_U26D1A_sparse_matrix_manifest.tsv"
    )
    manifest = read_table(path)
    if len(manifest) != 4:
        raise RuntimeError(f"Expected four manifest rows, found {len(manifest)}")
    return manifest


def load_annotations(project: Path) -> pd.DataFrame:
    path = (
        project / "03_metadata" / ANNOTATION_TAG
        / "UTI_HostOmics_U26D2A1_refined_all_QC_cell_annotations.tsv.gz"
    )
    annotations = read_table(path)
    required = {
        "cell_id", "sample_id", "condition",
        "refined_broad_cell_type", "refined_cell_subtype",
    }
    missing = sorted(required - set(annotations.columns))
    if missing:
        raise RuntimeError(f"Annotation table missing columns: {missing}")
    return annotations


def common_gene_universe(
    manifest: pd.DataFrame,
) -> Tuple[List[str], Dict[str, Dict[str, int]]]:
    maps: Dict[str, Dict[str, int]] = {}
    intersection: Optional[set[str]] = None

    for _, row in manifest.iterrows():
        genes = read_table(Path(str(row["genes_path"])))
        mapping: Dict[str, int] = {}
        for index, gene in enumerate(genes["gene_symbol"].map(normalize_gene)):
            if gene and gene not in mapping:
                mapping[gene] = index
        sample_id = str(row["sample_id"])
        maps[sample_id] = mapping
        gene_set = set(mapping)
        intersection = gene_set if intersection is None else intersection & gene_set

    common = sorted(intersection or set())
    if len(common) < 8000:
        raise RuntimeError(f"Only {len(common)} common genes were found.")
    return common, maps


def align_qc_matrix_and_annotations(
    row: pd.Series,
    sample_annotations: pd.DataFrame,
    common_genes: Sequence[str],
    gene_map: Dict[str, int],
) -> Tuple[sparse.csr_matrix, pd.DataFrame]:
    matrix = sparse.load_npz(Path(str(row["sparse_matrix_path"]))).tocsr()
    cells = read_table(Path(str(row["cell_metadata_path"])))

    qc_mask = (
        cells["adaptive_qc_pass"].astype(str).str.lower().isin(["true", "1"])
    ).to_numpy()
    matrix = matrix[qc_mask].tocsr()
    cells = cells.loc[qc_mask].reset_index(drop=True)

    common_indices = np.asarray([gene_map[gene] for gene in common_genes])
    matrix = matrix[:, common_indices].tocsr()

    position = pd.Series(
        np.arange(len(cells)),
        index=cells["cell_id"].astype(str),
    )
    requested = sample_annotations["cell_id"].astype(str)

    if not requested.isin(position.index).all():
        raise RuntimeError(
            f"Annotations cannot be aligned for {row['sample_id']}"
        )

    reorder = position.loc[requested].to_numpy(dtype=int)
    return matrix[reorder].tocsr(), sample_annotations.reset_index(drop=True)


def aggregate_populations(
    manifest: pd.DataFrame,
    annotations: pd.DataFrame,
    common_genes: Sequence[str],
    gene_maps: Dict[str, Dict[str, int]],
) -> Tuple[Dict[Tuple[str, str], Dict[str, np.ndarray]], pd.DataFrame]:
    aggregates: Dict[Tuple[str, str], Dict[str, np.ndarray]] = {}
    manifest_rows = []

    levels = {
        "broad_cell_type": "refined_broad_cell_type",
        "refined_subtype": "refined_cell_subtype",
    }

    for _, row in manifest.iterrows():
        sample_id = str(row["sample_id"])
        condition = str(row["condition"])
        sample_annotations = (
            annotations[annotations["sample_id"].astype(str) == sample_id]
            .copy()
            .reset_index(drop=True)
        )
        matrix, sample_annotations = align_qc_matrix_and_annotations(
            row,
            sample_annotations,
            common_genes,
            gene_maps[sample_id],
        )

        for level, column in levels.items():
            for population, indices in sample_annotations.groupby(column).indices.items():
                indices_array = np.asarray(indices, dtype=int)
                n_cells = len(indices_array)
                if n_cells < MIN_CELLS:
                    continue
                summed = np.asarray(
                    matrix[indices_array].sum(axis=0)
                ).ravel().astype(np.float64)

                key = (level, str(population))
                aggregates.setdefault(key, {})[sample_id] = summed

                manifest_rows.append(
                    {
                        "population_level": level,
                        "population": str(population),
                        "sample_id": sample_id,
                        "condition": condition,
                        "n_cells": n_cells,
                        "library_size": float(summed.sum()),
                        "detected_genes": int(np.count_nonzero(summed)),
                    }
                )

    return aggregates, pd.DataFrame(manifest_rows)


def complete_populations(
    aggregates: Dict[Tuple[str, str], Dict[str, np.ndarray]],
    sample_ids: Sequence[str],
) -> Dict[Tuple[str, str], Dict[str, np.ndarray]]:
    required = set(map(str, sample_ids))
    return {
        key: value
        for key, value in aggregates.items()
        if set(value) == required
    }


def log_cpm(counts: np.ndarray) -> np.ndarray:
    library = counts.sum(axis=1, keepdims=True)
    return np.log2(
        ((counts + 0.5) / (library + 1.0)) * 1_000_000.0
    )


def hedges_g(group_a: np.ndarray, group_b: np.ndarray) -> float:
    group_a = np.asarray(group_a, dtype=float)
    group_b = np.asarray(group_b, dtype=float)
    n_a = len(group_a)
    n_b = len(group_b)

    if n_a < 2 or n_b < 2:
        return np.nan

    var_a = np.var(group_a, ddof=1)
    var_b = np.var(group_b, ddof=1)
    denominator = n_a + n_b - 2
    if denominator <= 0:
        return np.nan

    pooled = math.sqrt(
        max(((n_a - 1) * var_a + (n_b - 1) * var_b) / denominator, 0.0)
    )
    if pooled == 0:
        difference = float(np.mean(group_a) - np.mean(group_b))
        if difference == 0:
            return 0.0
        return float(np.sign(difference) * np.inf)

    d = (np.mean(group_a) - np.mean(group_b)) / pooled
    correction_denominator = 4 * (n_a + n_b) - 9
    correction = (
        1.0 - 3.0 / correction_denominator
        if correction_denominator > 0
        else 1.0
    )
    return float(correction * d)


def exact_permutation_p(
    values: np.ndarray,
    upec_mask: np.ndarray,
) -> float:
    values = np.asarray(values, dtype=float)
    observed = abs(
        values[upec_mask].mean() - values[~upec_mask].mean()
    )

    indices = np.arange(len(values))
    differences = []
    for selected in itertools.combinations(indices, int(upec_mask.sum())):
        mask = np.zeros(len(values), dtype=bool)
        mask[list(selected)] = True
        differences.append(
            abs(values[mask].mean() - values[~mask].mean())
        )

    differences = np.asarray(differences)
    return float(np.mean(differences >= observed - 1e-12))


def bh_adjust(p_values: Sequence[float]) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    output = np.full(len(values), np.nan)
    finite = np.isfinite(values)
    if not finite.any():
        return output

    finite_values = values[finite]
    order = np.argsort(finite_values)
    ranked = finite_values[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.minimum(adjusted, 1.0)

    restored = np.empty_like(adjusted)
    restored[order] = adjusted
    output[np.where(finite)[0]] = restored
    return output


def module_dictionary(
    modules: pd.DataFrame,
) -> Tuple[Dict[str, List[str]], pd.DataFrame]:
    dictionary = (
        modules.groupby("feature_id")["gene_symbol"]
        .apply(lambda series: sorted(set(series.map(normalize_gene))))
        .to_dict()
    )
    metadata = (
        modules.groupby("feature_id", as_index=False)
        .agg(
            display_label=("display_label", "first"),
            axis=("axis", "first"),
            proposed_figure_family=("proposed_figure_family", "first"),
            requested_genes=("gene_symbol", "nunique"),
        )
    )
    return dictionary, metadata


def score_population(
    population_level: str,
    population: str,
    sample_counts: Dict[str, np.ndarray],
    sample_order: Sequence[str],
    conditions: Dict[str, str],
    common_genes: Sequence[str],
    module_genes: Dict[str, List[str]],
    module_metadata: pd.DataFrame,
) -> pd.DataFrame:
    counts = np.vstack([sample_counts[sample_id] for sample_id in sample_order])
    expression = log_cpm(counts)

    means = expression.mean(axis=0)
    standard = expression.std(axis=0, ddof=1)
    standard[standard == 0] = 1.0
    gene_z = (expression - means) / standard

    gene_lookup = {gene: index for index, gene in enumerate(common_genes)}
    upec_mask = np.asarray(
        [str(conditions[sample_id]).lower() == "upec" for sample_id in sample_order]
    )

    metadata_lookup = module_metadata.set_index("feature_id")
    rows = []

    for feature_id, requested in module_genes.items():
        detected = [gene for gene in requested if gene in gene_lookup]
        coverage = len(detected) / len(requested) if requested else 0.0
        eligible = (
            len(detected) >= MIN_MODULE_GENES
            and coverage >= MIN_MODULE_COVERAGE
        )

        meta = metadata_lookup.loc[feature_id]
        base = {
            "population_level": population_level,
            "population": population,
            "feature_id": feature_id,
            "display_label": meta["display_label"],
            "axis": meta["axis"],
            "proposed_figure_family": meta["proposed_figure_family"],
            "requested_genes": len(requested),
            "detected_genes": len(detected),
            "coverage_fraction": coverage,
            "score_eligible": eligible,
        }

        if not eligible:
            rows.append(
                {
                    **base,
                    "mean_control_score": np.nan,
                    "mean_UPEC_score": np.nan,
                    "mean_difference_UPEC_minus_control": np.nan,
                    "hedges_g_UPEC_vs_control": np.nan,
                    "exact_permutation_p": np.nan,
                    "module_mean_gene_log2FC": np.nan,
                    "module_median_gene_log2FC": np.nan,
                    "fraction_genes_positive_log2FC": np.nan,
                    "fraction_genes_negative_log2FC": np.nan,
                    "gene_direction_coherence": np.nan,
                    "direction": "not_scored",
                }
            )
            continue

        indices = np.asarray([gene_lookup[gene] for gene in detected], dtype=int)
        scores = gene_z[:, indices].mean(axis=1)

        control = scores[~upec_mask]
        upec = scores[upec_mask]
        difference = float(upec.mean() - control.mean())
        effect = hedges_g(upec, control)
        p_value = exact_permutation_p(scores, upec_mask)

        gene_logfc = (
            expression[upec_mask][:, indices].mean(axis=0)
            - expression[~upec_mask][:, indices].mean(axis=0)
        )
        positive_fraction = float(np.mean(gene_logfc > 0))
        negative_fraction = float(np.mean(gene_logfc < 0))
        coherence = max(positive_fraction, negative_fraction)

        rows.append(
            {
                **base,
                "mean_control_score": float(control.mean()),
                "mean_UPEC_score": float(upec.mean()),
                "mean_difference_UPEC_minus_control": difference,
                "hedges_g_UPEC_vs_control": effect,
                "exact_permutation_p": p_value,
                "module_mean_gene_log2FC": float(np.mean(gene_logfc)),
                "module_median_gene_log2FC": float(np.median(gene_logfc)),
                "fraction_genes_positive_log2FC": positive_fraction,
                "fraction_genes_negative_log2FC": negative_fraction,
                "gene_direction_coherence": coherence,
                "direction": (
                    "higher_in_UPEC"
                    if difference > 0
                    else "lower_in_UPEC"
                    if difference < 0
                    else "neutral"
                ),
            }
        )

    result = pd.DataFrame(rows)
    eligible_mask = result["score_eligible"].astype(bool)
    result["exact_permutation_q_within_population"] = np.nan
    result.loc[
        eligible_mask,
        "exact_permutation_q_within_population",
    ] = bh_adjust(
        result.loc[eligible_mask, "exact_permutation_p"].to_numpy()
    )
    return result


def cellular_localization(results: pd.DataFrame) -> pd.DataFrame:
    eligible = results[
        results["score_eligible"].astype(bool)
        & np.isfinite(pd.to_numeric(
            results["hedges_g_UPEC_vs_control"], errors="coerce"
        ))
    ].copy()

    rows = []
    for feature_id, frame in eligible.groupby("feature_id"):
        frame = frame.copy()
        frame["abs_effect"] = frame["hedges_g_UPEC_vs_control"].abs()
        frame = frame.sort_values("abs_effect", ascending=False)

        positive = int((frame["hedges_g_UPEC_vs_control"] > 0).sum())
        negative = int((frame["hedges_g_UPEC_vs_control"] < 0).sum())
        total = len(frame)
        dominant_count = max(positive, negative)

        top = frame.iloc[0]
        positive_frame = frame[frame["hedges_g_UPEC_vs_control"] > 0]
        negative_frame = frame[frame["hedges_g_UPEC_vs_control"] < 0]

        rows.append(
            {
                "feature_id": feature_id,
                "display_label": top["display_label"],
                "axis": top["axis"],
                "proposed_figure_family": top["proposed_figure_family"],
                "n_complete_populations": total,
                "n_positive_populations": positive,
                "n_negative_populations": negative,
                "directional_coherence_fraction": (
                    dominant_count / total if total else np.nan
                ),
                "dominant_direction": (
                    "higher_in_UPEC"
                    if positive > negative
                    else "lower_in_UPEC"
                    if negative > positive
                    else "mixed"
                ),
                "top_absolute_effect_population": top["population"],
                "top_absolute_effect_hedges_g": top[
                    "hedges_g_UPEC_vs_control"
                ],
                "top_positive_population": (
                    positive_frame.iloc[
                        positive_frame["hedges_g_UPEC_vs_control"].argmax()
                    ]["population"]
                    if not positive_frame.empty
                    else ""
                ),
                "top_positive_hedges_g": (
                    positive_frame["hedges_g_UPEC_vs_control"].max()
                    if not positive_frame.empty
                    else np.nan
                ),
                "top_negative_population": (
                    negative_frame.iloc[
                        negative_frame["hedges_g_UPEC_vs_control"].argmin()
                    ]["population"]
                    if not negative_frame.empty
                    else ""
                ),
                "top_negative_hedges_g": (
                    negative_frame["hedges_g_UPEC_vs_control"].min()
                    if not negative_frame.empty
                    else np.nan
                ),
                "median_effect": frame["hedges_g_UPEC_vs_control"].median(),
                "median_absolute_effect": frame["abs_effect"].median(),
                "n_populations_abs_g_ge_0_5": int(
                    (frame["abs_effect"] >= 0.5).sum()
                ),
                "n_populations_abs_g_ge_0_8": int(
                    (frame["abs_effect"] >= 0.8).sum()
                ),
                "median_gene_direction_coherence": frame[
                    "gene_direction_coherence"
                ].median(),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["n_populations_abs_g_ge_0_8", "median_absolute_effect"],
        ascending=[False, False],
    )


def effect_summary_from_fraction_table(
    frame: pd.DataFrame,
    id_columns: Sequence[str],
    value_column: str,
) -> pd.DataFrame:
    rows = []
    for keys, group in frame.groupby(list(id_columns)):
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_values = dict(zip(id_columns, keys))

        control = pd.to_numeric(
            group.loc[
                group["condition"].astype(str).str.lower() == "control",
                value_column,
            ],
            errors="coerce",
        ).dropna().to_numpy()
        upec = pd.to_numeric(
            group.loc[
                group["condition"].astype(str).str.lower() == "upec",
                value_column,
            ],
            errors="coerce",
        ).dropna().to_numpy()

        if len(control) != 2 or len(upec) != 2:
            continue

        values = np.concatenate([control, upec])
        upec_mask = np.asarray([False, False, True, True])

        rows.append(
            {
                **key_values,
                "mean_control": float(control.mean()),
                "mean_UPEC": float(upec.mean()),
                "difference_UPEC_minus_control": float(
                    upec.mean() - control.mean()
                ),
                "hedges_g_UPEC_vs_control": hedges_g(upec, control),
                "exact_permutation_p": exact_permutation_p(values, upec_mask),
            }
        )
    return pd.DataFrame(rows)


def save_heatmap(
    results: pd.DataFrame,
    populations: Sequence[str],
    features: Sequence[str],
    output: Path,
    title: str,
) -> None:
    subset = results[
        results["population"].isin(populations)
        & results["feature_id"].isin(features)
        & results["score_eligible"].astype(bool)
    ].copy()

    if subset.empty:
        return

    pivot = subset.pivot_table(
        index="feature_id",
        columns="population",
        values="hedges_g_UPEC_vs_control",
        aggfunc="first",
    ).reindex(index=[feature for feature in features if feature in subset["feature_id"].unique()])
    pivot = pivot.reindex(columns=[population for population in populations if population in pivot.columns])

    if pivot.empty:
        return

    figure_height = max(7, 0.32 * len(pivot.index) + 2)
    figure_width = max(9, 0.8 * len(pivot.columns) + 5)

    figure = plt.figure(figsize=(figure_width, figure_height))
    axis = figure.add_axes([0.30, 0.15, 0.52, 0.76])
    image = axis.imshow(pivot.to_numpy(), aspect="auto")

    axis.set_xticks(np.arange(len(pivot.columns)))
    axis.set_xticklabels(
        [str(value).replace("_", " ") for value in pivot.columns],
        rotation=45,
        ha="right",
        fontsize=8,
    )
    axis.set_yticks(np.arange(len(pivot.index)))
    axis.set_yticklabels(
        [str(value).replace("_", " ") for value in pivot.index],
        fontsize=8,
    )
    axis.set_title(title)
    color_axis = figure.add_axes([0.85, 0.25, 0.025, 0.50])
    figure.colorbar(image, cax=color_axis, label="Hedges g: UPEC vs control")
    figure.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(figure)


def load_core_priorities(project: Path) -> pd.DataFrame:
    path = (
        project / "06_tables" / CORE_TAG
        / "UTI_HostOmics_U26C1_refined_core_and_secondary_modules.tsv"
    )
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "feature_id", "biological_priority",
                "manuscript_claim_priority",
            ]
        )
    return read_table(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    out_processed = project / "03_data_processed" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_tables = project / "06_tables" / TAG
    out_results = project / "05_results" / TAG
    out_figures = project / "06_figures" / TAG

    for directory in [
        out_processed, out_metadata, out_tables, out_results, out_figures
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    log("Loading refined annotations and sparse-count manifest.")
    annotations = load_annotations(project)
    manifest = load_manifest(project)
    sample_order = manifest["sample_id"].astype(str).tolist()
    conditions = dict(
        zip(
            manifest["sample_id"].astype(str),
            manifest["condition"].astype(str),
        )
    )

    log("Discovering the U26 module dictionary.")
    modules, module_audit = discover_modules(project)
    module_audit.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_module_dictionary_audit.tsv",
        sep="\t",
        index=False,
    )
    modules.to_csv(
        out_metadata / "UTI_HostOmics_U26D2B_canonical_module_dictionary.tsv",
        sep="\t",
        index=False,
    )
    module_source = str(modules.attrs.get("source_path", ""))
    log(
        f"Selected module dictionary: {module_source}; "
        f"{modules['feature_id'].nunique()} modules."
    )

    module_genes, module_metadata = module_dictionary(modules)

    common_genes, gene_maps = common_gene_universe(manifest)
    pd.DataFrame({"gene_symbol": common_genes}).to_csv(
        out_metadata / "UTI_HostOmics_U26D2B_common_gene_universe.tsv.gz",
        sep="\t",
        index=False,
        compression="gzip",
    )

    log("Aggregating raw counts by sample and refined population.")
    aggregates, pseudobulk_manifest = aggregate_populations(
        manifest,
        annotations,
        common_genes,
        gene_maps,
    )
    complete = complete_populations(aggregates, sample_order)

    pseudobulk_manifest["complete_four_sample_population"] = [
        (row.population_level, row.population) in complete
        for row in pseudobulk_manifest.itertuples()
    ]
    pseudobulk_manifest.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_pseudobulk_manifest.tsv",
        sep="\t",
        index=False,
    )

    results = []
    for index, ((level, population), sample_counts) in enumerate(
        sorted(complete.items()),
        start=1,
    ):
        log(
            f"Scoring {level}: {population} "
            f"({index}/{len(complete)})."
        )
        results.append(
            score_population(
                population_level=level,
                population=population,
                sample_counts=sample_counts,
                sample_order=sample_order,
                conditions=conditions,
                common_genes=common_genes,
                module_genes=module_genes,
                module_metadata=module_metadata,
            )
        )

    all_results = pd.concat(results, ignore_index=True)
    broad_results = all_results[
        all_results["population_level"] == "broad_cell_type"
    ].copy()
    subtype_results = all_results[
        all_results["population_level"] == "refined_subtype"
    ].copy()

    broad_results.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_broad_celltype_module_results.tsv",
        sep="\t",
        index=False,
    )
    subtype_results.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_refined_subtype_module_results.tsv",
        sep="\t",
        index=False,
    )

    coverage = (
        all_results[
            [
                "feature_id", "display_label", "axis",
                "proposed_figure_family", "requested_genes",
                "detected_genes", "coverage_fraction", "score_eligible",
            ]
        ]
        .drop_duplicates("feature_id")
        .sort_values(["score_eligible", "coverage_fraction"], ascending=[False, False])
    )
    coverage.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_module_coverage.tsv",
        sep="\t",
        index=False,
    )

    broad_localization = cellular_localization(broad_results)
    subtype_localization = cellular_localization(subtype_results)
    broad_localization.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_broad_cellular_localization.tsv",
        sep="\t",
        index=False,
    )
    subtype_localization.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_subtype_cellular_localization.tsv",
        sep="\t",
        index=False,
    )

    core = load_core_priorities(project)
    core_localization = broad_localization.merge(
        core[
            [
                column for column in [
                    "feature_id", "biological_priority",
                    "manuscript_claim_priority",
                    "refined_infection_outcome_relation",
                ]
                if column in core.columns
            ]
        ],
        on="feature_id",
        how="left",
    )
    core_localization["is_predefined_focus_module"] = (
        core_localization["feature_id"].isin(FOCUS_MODULES)
    )
    core_localization = core_localization.sort_values(
        [
            "is_predefined_focus_module",
            "n_populations_abs_g_ge_0_8",
            "median_absolute_effect",
        ],
        ascending=[False, False, False],
    )
    core_localization.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_core_module_cellular_localization.tsv",
        sep="\t",
        index=False,
    )

    composition_path = (
        project / "06_tables" / ANNOTATION_TAG
        / "UTI_HostOmics_U26D2A1_refined_sample_celltype_composition.tsv"
    )
    targeted_path = (
        project / "06_tables" / ANNOTATION_TAG
        / "UTI_HostOmics_U26D2A1_fixed_targeted_population_summary.tsv"
    )

    composition = read_table(composition_path)
    composition_effects = effect_summary_from_fraction_table(
        composition,
        ["refined_broad_cell_type"],
        "fraction_of_QC_cells",
    )
    composition_effects.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_celltype_composition_effects.tsv",
        sep="\t",
        index=False,
    )

    targeted = read_table(targeted_path)
    targeted_effects = effect_summary_from_fraction_table(
        targeted,
        ["targeted_measure"],
        "value",
    )
    targeted_effects.to_csv(
        out_tables / "UTI_HostOmics_U26D2B_targeted_state_effects.tsv",
        sep="\t",
        index=False,
    )

    broad_populations = sorted(
        broad_results["population"].unique().tolist()
    )
    subtype_counts = (
        pseudobulk_manifest[
            (pseudobulk_manifest["population_level"] == "refined_subtype")
            & pseudobulk_manifest["complete_four_sample_population"]
        ]
        .groupby("population")["n_cells"]
        .min()
        .sort_values(ascending=False)
    )
    subtype_populations = subtype_counts.head(14).index.tolist()

    available_focus = [
        feature for feature in FOCUS_MODULES
        if feature in set(all_results["feature_id"])
    ]

    save_heatmap(
        broad_results,
        broad_populations,
        available_focus,
        out_figures
        / "UTI_HostOmics_U26D2B_focus_modules_broad_celltypes.png",
        "GSE252321 UPEC effects by refined broad cell type",
    )
    save_heatmap(
        subtype_results,
        subtype_populations,
        available_focus,
        out_figures
        / "UTI_HostOmics_U26D2B_focus_modules_refined_subtypes.png",
        "GSE252321 UPEC effects by refined cell subtype",
    )

    for figure_family in ["Figure_7", "Figure_8", "Figure_9", "Figure_10"]:
        features = (
            module_metadata[
                module_metadata["proposed_figure_family"].astype(str)
                == figure_family
            ]["feature_id"]
            .astype(str)
            .tolist()
        )
        if not features:
            continue
        save_heatmap(
            broad_results,
            broad_populations,
            features,
            out_figures
            / f"UTI_HostOmics_U26D2B_{figure_family}_broad_celltypes.png",
            f"{figure_family.replace('_', ' ')} cellular localization",
        )

    key_covered = {
        feature: bool(
            feature in set(coverage.loc[coverage["score_eligible"], "feature_id"])
        )
        for feature in [
            "TLR4_LPS_SIGNALING_ANCHOR",
            "LEPTIN_SIGNALING",
            "PI3K_AKT_SIGNALING",
            "COMPLEMENT_OPSONOPHAGOCYTOSIS",
            "COMPLEMENT_C3A_C5A_SIGNALING",
        ]
    }

    n_complete_broad = int(
        broad_results["population"].nunique()
    )
    n_complete_subtypes = int(
        subtype_results["population"].nunique()
    )
    n_eligible_modules = int(
        coverage["score_eligible"].astype(bool).sum()
    )
    min_exact_p = float(
        pd.to_numeric(
            broad_results["exact_permutation_p"],
            errors="coerce",
        ).min()
    )

    if (
        n_complete_broad >= 5
        and n_complete_subtypes >= 8
        and n_eligible_modules >= 60
        and all(key_covered.values())
    ):
        decision = (
            "READY_FOR_U26D2C_CELLULAR_LOCALIZATION_SYNTHESIS_"
            "AND_U27_FIGURE_INTEGRATION"
        )
    else:
        decision = "TARGETED_PSEUDOBULK_REVIEW_REQUIRED"

    pd.DataFrame(
        [
            {
                "phase": "U26D2B",
                "decision": decision,
                "module_dictionary_source": module_source,
                "n_modules_in_dictionary": modules["feature_id"].nunique(),
                "n_score_eligible_modules": n_eligible_modules,
                "n_common_genes": len(common_genes),
                "n_complete_broad_cell_types": n_complete_broad,
                "n_complete_refined_subtypes": n_complete_subtypes,
                "n_broad_module_results": len(broad_results),
                "n_subtype_module_results": len(subtype_results),
                "minimum_exact_two_sided_permutation_p": min_exact_p,
                "FDR_supported_results_expected_with_n2_vs_n2": False,
                "TLR4_covered": key_covered[
                    "TLR4_LPS_SIGNALING_ANCHOR"
                ],
                "leptin_covered": key_covered["LEPTIN_SIGNALING"],
                "PI3K_AKT_covered": key_covered["PI3K_AKT_SIGNALING"],
                "complement_opsonophagocytosis_covered": key_covered[
                    "COMPLEMENT_OPSONOPHAGOCYTOSIS"
                ],
                "complement_C3A_C5A_covered": key_covered[
                    "COMPLEMENT_C3A_C5A_SIGNALING"
                ],
                "biological_sample_is_inferential_unit": True,
                "cell_level_significance_testing_performed": False,
                "raw_expression_pooled_across_datasets_or_species": False,
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U26D2C cellular localization synthesis and U27 "
                    "Figure 7-11 integration"
                    if decision.startswith("READY")
                    else "Review module dictionary, coverage, and population "
                    "completeness"
                ),
            }
        ]
    ).to_csv(
        out_tables / "UTI_HostOmics_U26D2B_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U26D2B_celltype_pseudobulk_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26D2B - Refined cell-type pseudobulk scoring\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Module dictionary: `{module_source}`.\n"
        )
        handle.write(
            f"- Modules in dictionary: **{modules['feature_id'].nunique()}**.\n"
        )
        handle.write(
            f"- Score-eligible modules: **{n_eligible_modules}**.\n"
        )
        handle.write(
            f"- Common mouse genes: **{len(common_genes):,}**.\n"
        )
        handle.write(
            f"- Complete broad cell populations: **{n_complete_broad}**.\n"
        )
        handle.write(
            f"- Complete refined subtypes: **{n_complete_subtypes}**.\n\n"
        )

        handle.write("## Statistical boundary\n\n")
        handle.write(
            "Every pathway comparison uses two control and two UPEC "
            "biological samples. Cells were aggregated before scoring. The "
            "exact permutation p values therefore have very low resolution "
            f"(minimum observed {min_exact_p:.3f}) and cannot establish "
            "conventional statistical significance. Cellular localization is "
            "based primarily on Hedges g, module gene log2 fold change and "
            "within-module gene-direction coherence.\n\n"
        )

        handle.write("## Broad cellular localization priorities\n\n")
        focus_localization = core_localization[
            core_localization["is_predefined_focus_module"]
        ].head(30)
        for _, item in focus_localization.iterrows():
            handle.write(
                f"- **{item['display_label']}**: strongest absolute effect in "
                f"`{item['top_absolute_effect_population']}` "
                f"(g={float(item['top_absolute_effect_hedges_g']):.3f}); "
                f"dominant direction `{item['dominant_direction']}`; "
                f"{int(item['n_populations_abs_g_ge_0_5'])} broad populations "
                f"with |g|>=0.5.\n"
            )

        handle.write("\n## Composition and targeted states\n\n")
        for _, item in composition_effects.sort_values(
            "difference_UPEC_minus_control",
            key=lambda series: series.abs(),
            ascending=False,
        ).iterrows():
            handle.write(
                f"- `{item['refined_broad_cell_type']}` fraction: "
                f"control={float(item['mean_control']):.3f}, "
                f"UPEC={float(item['mean_UPEC']):.3f}, "
                f"difference={float(item['difference_UPEC_minus_control']):.3f}.\n"
            )

        for _, item in targeted_effects.iterrows():
            handle.write(
                f"- `{item['targeted_measure']}`: "
                f"control={float(item['mean_control']):.3f}, "
                f"UPEC={float(item['mean_UPEC']):.3f}, "
                f"difference={float(item['difference_UPEC_minus_control']):.3f}.\n"
            )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "module_dictionary_source": module_source,
        "n_score_eligible_modules": n_eligible_modules,
        "n_complete_broad_cell_types": n_complete_broad,
        "n_complete_refined_subtypes": n_complete_subtypes,
        "minimum_exact_permutation_p": min_exact_p,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results / "UTI_HostOmics_U26D2B_run_manifest.json"
    ).write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    log(f"Score-eligible modules: {n_eligible_modules}")
    log(f"Complete broad cell types: {n_complete_broad}")
    log(f"Complete refined subtypes: {n_complete_subtypes}")
    log(f"Minimum exact permutation p: {min_exact_p:.3f}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26D2B] ERROR: {exc}", file=sys.stderr)
        raise
