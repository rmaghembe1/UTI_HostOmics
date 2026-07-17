#!/usr/bin/env python3
"""
Phase U26A.5
Finalize GSE280297 input resolution using the structurally valid repaired
gene-symbol matrix with all 60 samples and its matching sample annotation.

The malformed repaired normalized matrix is explicitly excluded.
The selected matrix is treated as continuous transformed expression, not raw
integer counts, unless its numeric audit proves otherwise.

This phase does not modify the manuscript or existing figures.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

VERSION = "U26A5_v1.0_2026-07-14"
PHASE_TAG = "phaseU26A5_GSE280297_final_input_resolution"

# Mouse symbols can begin with digits, for example 0610007P14Rik.
SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,79}$")
MOUSE_ENSEMBL_RE = re.compile(r"^ENSMUSG\d+(?:\.\d+)?$", re.I)


def log(message: str) -> None:
    print(f"[U26A.5] {message}", flush=True)


def normalize_symbol(value: object) -> str:
    return str(value).strip().strip('"').strip("'")


def valid_symbol(value: object) -> bool:
    symbol = normalize_symbol(value)
    return (
        bool(SYMBOL_RE.fullmatch(symbol))
        and not symbol.isdigit()
        and not bool(MOUSE_ENSEMBL_RE.fullmatch(symbol))
        and symbol.lower() not in {"", "na", "nan", "none", "null"}
    )


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        compression="infer",
        low_memory=False,
    )


def expected_samples() -> List[str]:
    samples = [f"B{i}" for i in range(1, 19)]
    samples += [f"U{i}" for i in range(1, 15)]
    samples += [f"P{i}" for i in range(1, 29)]
    return samples


def matrix_audit(
    matrix_path: Path,
) -> Tuple[pd.DataFrame, dict]:
    df = read_tsv(matrix_path)

    if "gene_symbol" not in df.columns:
        raise RuntimeError(
            f"Expected gene_symbol column not found in {matrix_path}"
        )

    expected = expected_samples()
    present = [sample for sample in expected if sample in df.columns]
    absent = [sample for sample in expected if sample not in df.columns]

    symbols = df["gene_symbol"].map(normalize_symbol)
    keep = symbols.map(valid_symbol)

    matrix = df.loc[keep, ["gene_symbol"] + present].copy()
    matrix["gene_symbol"] = symbols.loc[keep].values

    for sample in present:
        matrix[sample] = pd.to_numeric(
            matrix[sample],
            errors="coerce",
        )

    numeric_completion = float(
        matrix[present].notna().mean().mean()
    ) if present else 0.0

    duplicate_rows = int(
        matrix["gene_symbol"].duplicated().sum()
    )

    matrix = (
        matrix.groupby("gene_symbol", as_index=False)[present]
        .mean(numeric_only=True)
        .sort_values("gene_symbol")
        .reset_index(drop=True)
    )

    # Characterize whether this is raw count data or transformed expression.
    preview = matrix[present].iloc[: min(2000, len(matrix))]
    values = preview.to_numpy(dtype=float).ravel()
    values = values[np.isfinite(values)]

    if len(values):
        non_integer_fraction = float(
            np.mean(np.abs(values - np.round(values)) > 1e-8)
        )
        negative_fraction = float(np.mean(values < 0))
        zero_fraction = float(np.mean(values == 0))
    else:
        non_integer_fraction = 1.0
        negative_fraction = 0.0
        zero_fraction = 0.0

    expression_scale = (
        "continuous_transformed_expression"
        if non_integer_fraction > 0.05
        else "integer_like_counts"
    )

    qc = {
        "matrix_path": str(matrix_path),
        "n_input_rows": int(df.shape[0]),
        "n_valid_symbol_rows": int(keep.sum()),
        "n_invalid_symbol_rows": int((~keep).sum()),
        "n_duplicate_symbol_rows_before_collapse": duplicate_rows,
        "n_canonical_gene_symbols": int(
            matrix["gene_symbol"].nunique()
        ),
        "n_expected_samples": len(expected),
        "n_expression_samples_present": len(present),
        "missing_expected_samples": ";".join(absent),
        "numeric_completion_fraction": round(
            numeric_completion, 6
        ),
        "non_integer_fraction_preview": round(
            non_integer_fraction, 6
        ),
        "negative_fraction_preview": round(
            negative_fraction, 6
        ),
        "zero_fraction_preview": round(
            zero_fraction, 6
        ),
        "expression_scale_class": expression_scale,
        "gene_universe_plausible": bool(
            matrix["gene_symbol"].nunique() >= 10000
        ),
        "sample_architecture_complete": bool(
            len(present) == 60 and not absent
        ),
    }

    return matrix, qc


def normalize_tissue(value: object, sample_id: str) -> str:
    text = str(value).strip().lower()

    if "bladder" in text:
        return "bladder"
    if "uterus" in text or "uterine" in text:
        return "uterus"
    if "placenta" in text or "placental" in text:
        return "placenta"

    match = re.fullmatch(r"([BUP])\d+", sample_id, flags=re.I)
    if not match:
        return ""

    return {
        "B": "bladder",
        "U": "uterus",
        "P": "placenta",
    }.get(match.group(1).upper(), "")


def normalize_treatment(value: object) -> str:
    text = str(value).strip().lower()

    if "pbs" in text or "mock" in text:
        return "PBS_control"
    if "uti89" in text and "rfp" in text:
        return "UTI89_RFP"
    if "uti89" in text or "upec" in text:
        return "UTI89"

    return ""


def normalize_outcome(value: object) -> str:
    text = str(value).strip().lower()

    if "nonpregnant" in text or "non-pregnant" in text:
        return "nonpregnant"
    if "preterm" in text:
        return "preterm"
    if text == "term" or "term" in text:
        return "term"
    if "mock" in text:
        return "mock_control"

    return ""


def pregnancy_status(
    outcome: str,
    tissue: str,
    treatment: str,
) -> str:
    if outcome == "nonpregnant":
        return "nonpregnant"

    if outcome in {"preterm", "term"}:
        return "pregnant"

    if outcome == "mock_control":
        # The mock/PBS samples belong to the pregnancy-control arm.
        return "pregnant_control"

    # Placenta and uterus samples necessarily derive from pregnancy.
    if tissue in {"placenta", "uterus"}:
        return "pregnant"

    if treatment == "PBS_control":
        return "pregnant_control"

    return ""


def build_design(
    annotation_path: Path,
    expression_samples: Sequence[str],
) -> Tuple[pd.DataFrame, dict]:
    annotation = read_tsv(annotation_path)

    if "sample_id" not in annotation.columns:
        raise RuntimeError(
            f"sample_id column not found in {annotation_path}"
        )

    annotation = annotation.copy()
    annotation["sample_id"] = (
        annotation["sample_id"].astype(str).str.strip()
    )
    annotation = annotation.drop_duplicates(
        subset=["sample_id"],
        keep="first",
    )
    lookup = annotation.set_index("sample_id", drop=False)

    rows = []

    for sample_id in expression_samples:
        if sample_id in lookup.index:
            row = lookup.loc[sample_id]
            matched = True
        else:
            row = pd.Series(dtype=object)
            matched = False

        tissue = normalize_tissue(
            row.get("tissue", ""),
            sample_id,
        )
        treatment = normalize_treatment(
            row.get("treatment", "")
        )
        outcome = normalize_outcome(
            row.get("outcome", "")
        )
        pregnancy = pregnancy_status(
            outcome,
            tissue,
            treatment,
        )

        primary_exposure = (
            "UPEC_exposed"
            if treatment in {"UTI89", "UTI89_RFP"}
            else "control"
            if treatment == "PBS_control"
            else ""
        )

        unresolved = []
        for field, value in [
            ("tissue", tissue),
            ("treatment", treatment),
            ("outcome", outcome),
            ("pregnancy_status", pregnancy),
        ]:
            if not value:
                unresolved.append(field)

        rows.append(
            {
                "sample_id": sample_id,
                "annotation_row_matched": matched,
                "sample_geo_accession": row.get(
                    "sample_geo_accession",
                    "",
                ),
                "tissue": tissue,
                "treatment": treatment,
                "primary_exposure": primary_exposure,
                "outcome": outcome,
                "pregnancy_status": pregnancy,
                "sex": row.get("sex", ""),
                "inferred_group": row.get(
                    "inferred_group",
                    "",
                ),
                "dam_id": row.get("dam_id", ""),
                "unresolved_required_fields": ";".join(
                    unresolved
                ),
                "source_annotation_text": row.get(
                    "sample_characteristics_ch1_joined",
                    "",
                ),
            }
        )

    design = pd.DataFrame(rows)

    metadata_qc = {
        "annotation_path": str(annotation_path),
        "n_annotation_rows": int(annotation.shape[0]),
        "n_expression_samples": int(len(expression_samples)),
        "annotation_match_fraction": round(
            float(
                design["annotation_row_matched"]
                .astype(bool)
                .mean()
            ),
            6,
        ),
        "tissue_completion": round(
            completion(design["tissue"]),
            6,
        ),
        "treatment_completion": round(
            completion(design["treatment"]),
            6,
        ),
        "outcome_completion": round(
            completion(design["outcome"]),
            6,
        ),
        "pregnancy_completion": round(
            completion(design["pregnancy_status"]),
            6,
        ),
        "dam_id_completion_all": round(
            completion(design["dam_id"]),
            6,
        ),
        "n_unresolved_rows": int(
            design["unresolved_required_fields"]
            .fillna("")
            .ne("")
            .sum()
        ),
    }

    pregnant = design[
        design["pregnancy_status"].isin(
            ["pregnant", "pregnant_control"]
        )
    ]

    metadata_qc["dam_id_completion_pregnancy_samples"] = round(
        completion(pregnant["dam_id"])
        if len(pregnant)
        else 0.0,
        6,
    )

    return design, metadata_qc


def completion(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0

    return float(
        series.fillna("")
        .astype(str)
        .str.strip()
        .ne("")
        .mean()
    )


def load_submodule_library(
    project: Path,
) -> Optional[pd.DataFrame]:
    path = (
        project
        / "03_metadata"
        / "phaseU26A_expanded_endocrine_metabolic_immune_feasibility"
        / "UTI_HostOmics_U26A_expanded_submodule_library.tsv"
    )

    if not path.exists():
        return None

    return pd.read_csv(path, sep="\t", dtype=str)


def gene_list_column(library: pd.DataFrame) -> str:
    preferred = [
        "genes",
        "gene_symbols",
        "members",
        "gene_list",
        "symbols",
    ]

    for column in preferred:
        if column in library.columns:
            return column

    for column in library.columns:
        if "gene" in str(column).lower():
            return str(column)

    raise RuntimeError(
        "Could not identify the gene-list column."
    )


def calculate_coverage(
    library: Optional[pd.DataFrame],
    symbols: Iterable[str],
) -> pd.DataFrame:
    if library is None:
        return pd.DataFrame()

    genes_column = gene_list_column(library)
    universe = {
        normalize_symbol(symbol).upper()
        for symbol in symbols
    }

    rows = []

    for _, row in library.iterrows():
        raw = str(row[genes_column])
        genes = [
            token.strip()
            for token in re.split(r"[;,| ]+", raw)
            if token.strip()
            and token.strip().lower() != "nan"
        ]
        detected = [
            gene
            for gene in genes
            if gene.upper() in universe
        ]
        fraction = (
            len(detected) / len(genes)
            if genes
            else math.nan
        )

        if genes and len(detected) >= 5 and fraction >= 0.50:
            coverage_class = "adequate"
        elif genes and len(detected) >= 3 and fraction >= 0.25:
            coverage_class = "partial"
        else:
            coverage_class = "weak"

        rows.append(
            {
                "axis": row.get("axis", ""),
                "submodule_id": row.get(
                    "submodule_id",
                    row.get("module_id", ""),
                ),
                "display_label": row.get(
                    "display_label",
                    row.get("label", ""),
                ),
                "n_library_genes": len(genes),
                "n_detected_genes": len(detected),
                "coverage_fraction": (
                    round(fraction, 4)
                    if genes
                    else ""
                ),
                "coverage_class": coverage_class,
                "detected_genes": ";".join(detected),
            }
        )

    return pd.DataFrame(rows)


def contrast_blueprint() -> pd.DataFrame:
    rows = [
        {
            "contrast_id": "GSE280297_C1",
            "analysis_scope": "within_tissue",
            "comparison": "UTI89_preterm_vs_UTI89_term",
            "eligible_tissues": "bladder;uterus;placenta",
            "primary_statistics": (
                "continuous module-score effect size; "
                "Welch/limma-style contrast; FDR"
            ),
            "status": "ready",
        },
        {
            "contrast_id": "GSE280297_C2",
            "analysis_scope": "within_tissue",
            "comparison": "UPEC_exposed_pregnancy_vs_PBS_pregnancy_control",
            "eligible_tissues": "bladder;uterus;placenta",
            "primary_statistics": (
                "continuous module-score effect size; "
                "Welch/limma-style contrast; FDR"
            ),
            "status": "ready",
        },
        {
            "contrast_id": "GSE280297_C3",
            "analysis_scope": "bladder_only",
            "comparison": "UTI89_nonpregnant_vs_UTI89_pregnant",
            "eligible_tissues": "bladder",
            "primary_statistics": (
                "effect size and exploratory FDR-controlled "
                "contrast"
            ),
            "status": "ready_with_small_group_caution",
        },
        {
            "contrast_id": "GSE280297_C4",
            "analysis_scope": "tissue_stratified",
            "comparison": "UTI89_RFP_vs_UTI89",
            "eligible_tissues": "where both groups occur",
            "primary_statistics": (
                "descriptive/exploratory effect sizes"
            ),
            "status": "secondary",
        },
        {
            "contrast_id": "GSE280297_C5",
            "analysis_scope": "dam_level",
            "comparison": (
                "pregnancy_risk_index_vs_preterm_outcome"
            ),
            "eligible_tissues": (
                "dam-aggregated bladder;uterus;placenta"
            ),
            "primary_statistics": (
                "AUROC/permutation; logistic model only if "
                "dam identifiers and effective n are adequate"
            ),
            "status": "deferred_missing_dam_id",
        },
    ]

    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    selected_matrix = (
        project
        / "03_data_processed"
        / "phaseU4b_repaired_matrices"
        / "GSE280297_gene_count_repaired_gene_symbol_matrix.tsv.gz"
    )
    selected_annotation = (
        project
        / "07_tables"
        / "phaseU4b_repaired_module_scores"
        / "GSE280297_gene_count_repaired_sample_annotation_v1.tsv"
    )
    excluded_matrix = (
        project
        / "03_data_processed"
        / "phaseU4b_repaired_matrices"
        / "GSE280297_normalized_repaired_gene_symbol_matrix.tsv.gz"
    )

    out_meta = project / "03_metadata" / PHASE_TAG
    out_processed = project / "03_data_processed" / PHASE_TAG
    out_results = project / "05_results" / PHASE_TAG
    out_tables = project / "06_tables" / PHASE_TAG

    for directory in [
        out_meta,
        out_processed,
        out_results,
        out_tables,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    for required in [selected_matrix, selected_annotation]:
        if not required.exists():
            raise FileNotFoundError(
                f"Required established asset not found: {required}"
            )

    log(f"Selected matrix: {selected_matrix}")
    log(f"Selected annotation: {selected_annotation}")

    matrix, matrix_qc = matrix_audit(selected_matrix)

    canonical_matrix = (
        out_processed
        / "GSE280297_U26A5_canonical_60sample_gene_symbol_expression.tsv.gz"
    )
    matrix.to_csv(
        canonical_matrix,
        sep="\t",
        index=False,
        compression="gzip",
    )
    matrix_qc["canonical_matrix"] = str(canonical_matrix)

    pd.DataFrame([matrix_qc]).to_csv(
        out_tables
        / "UTI_HostOmics_U26A5_GSE280297_matrix_qc.tsv",
        sep="\t",
        index=False,
    )

    samples = [
        column
        for column in matrix.columns
        if column != "gene_symbol"
    ]

    design, metadata_qc = build_design(
        selected_annotation,
        samples,
    )

    design_path = (
        out_meta
        / "GSE280297_U26A5_validated_60sample_design.tsv"
    )
    design.to_csv(
        design_path,
        sep="\t",
        index=False,
    )

    pd.DataFrame([metadata_qc]).to_csv(
        out_tables
        / "UTI_HostOmics_U26A5_GSE280297_metadata_qc.tsv",
        sep="\t",
        index=False,
    )

    group_summary = (
        design.groupby(
            [
                "tissue",
                "treatment",
                "primary_exposure",
                "outcome",
                "pregnancy_status",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="n_samples")
    )
    group_summary.to_csv(
        out_tables
        / "UTI_HostOmics_U26A5_GSE280297_group_summary.tsv",
        sep="\t",
        index=False,
    )

    unresolved = design[
        design["unresolved_required_fields"]
        .fillna("")
        .ne("")
    ]
    unresolved.to_csv(
        out_tables
        / "UTI_HostOmics_U26A5_unresolved_sample_design_rows.tsv",
        sep="\t",
        index=False,
    )

    coverage = calculate_coverage(
        load_submodule_library(project),
        matrix["gene_symbol"],
    )
    if not coverage.empty:
        coverage.to_csv(
            out_tables
            / "UTI_HostOmics_U26A5_GSE280297_submodule_coverage.tsv",
            sep="\t",
            index=False,
        )

    contrasts = contrast_blueprint()
    contrasts.to_csv(
        out_tables
        / "UTI_HostOmics_U26A5_GSE280297_contrast_blueprint.tsv",
        sep="\t",
        index=False,
    )

    asset_disposition = pd.DataFrame(
        [
            {
                "asset": str(selected_matrix),
                "disposition": "selected_primary",
                "reason": (
                    "valid gene symbols; all 60 B/U/P samples; "
                    "continuous transformed expression suitable "
                    "for module scoring"
                ),
            },
            {
                "asset": str(selected_annotation),
                "disposition": "selected_matching_annotation",
                "reason": (
                    "matching 60-sample annotation architecture"
                ),
            },
            {
                "asset": str(excluded_matrix),
                "disposition": "excluded",
                "reason": (
                    "gene_symbol column contains numeric values "
                    "and B1-B3 are absent"
                ),
            },
        ]
    )
    asset_disposition.to_csv(
        out_tables
        / "UTI_HostOmics_U26A5_asset_disposition.tsv",
        sep="\t",
        index=False,
    )

    matrix_ready = bool(
        matrix_qc["gene_universe_plausible"]
        and matrix_qc["sample_architecture_complete"]
        and matrix_qc["numeric_completion_fraction"] >= 0.99
    )

    metadata_ready = bool(
        metadata_qc["annotation_match_fraction"] >= 0.99
        and metadata_qc["tissue_completion"] >= 0.99
        and metadata_qc["treatment_completion"] >= 0.99
        and metadata_qc["outcome_completion"] >= 0.99
        and metadata_qc["pregnancy_completion"] >= 0.99
    )

    dam_ready = (
        metadata_qc["dam_id_completion_pregnancy_samples"]
        >= 0.90
    )

    if matrix_ready and metadata_ready and dam_ready:
        decision = "READY_FOR_U26B"
        core_status = "ready"
        dam_status = "ready"
    elif matrix_ready and metadata_ready:
        decision = (
            "READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED"
        )
        core_status = "ready"
        dam_status = "deferred"
    elif matrix_ready:
        decision = "TARGETED_METADATA_REVIEW_REQUIRED"
        core_status = "not_ready"
        dam_status = "deferred"
    else:
        decision = "TARGETED_MATRIX_REVIEW_REQUIRED"
        core_status = "not_ready"
        dam_status = "deferred"

    analysis_method = (
        "continuous module scoring and limma/Welch-style "
        "sample-level contrasts; do not use DESeq2 on this "
        "transformed matrix"
        if matrix_qc["expression_scale_class"]
        == "continuous_transformed_expression"
        else "count-aware modeling may be considered after "
        "confirming integer raw counts"
    )

    decision_row = {
        "phase": "U26A.5",
        "overall_decision": decision,
        "selected_matrix": str(selected_matrix),
        "selected_annotation": str(selected_annotation),
        "canonical_matrix": str(canonical_matrix),
        "n_canonical_gene_symbols": matrix_qc[
            "n_canonical_gene_symbols"
        ],
        "n_expression_samples": matrix_qc[
            "n_expression_samples_present"
        ],
        "expression_scale_class": matrix_qc[
            "expression_scale_class"
        ],
        "annotation_match_fraction": metadata_qc[
            "annotation_match_fraction"
        ],
        "tissue_completion": metadata_qc[
            "tissue_completion"
        ],
        "treatment_completion": metadata_qc[
            "treatment_completion"
        ],
        "outcome_completion": metadata_qc[
            "outcome_completion"
        ],
        "pregnancy_completion": metadata_qc[
            "pregnancy_completion"
        ],
        "dam_id_completion_pregnancy_samples": metadata_qc[
            "dam_id_completion_pregnancy_samples"
        ],
        "core_tissue_stratified_scoring": core_status,
        "dam_level_pregnancy_outcome_model": dam_status,
        "recommended_U26B_statistics": analysis_method,
        "critical_rule": (
            "Use biological tissue samples as analysis units; "
            "do not combine tissues as independent dam-level "
            "replicates; retain dam-level pregnancy-risk "
            "modeling as deferred until dam identifiers exist."
        ),
    }

    pd.DataFrame([decision_row]).to_csv(
        out_tables
        / "UTI_HostOmics_U26A5_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "selected_matrix": str(selected_matrix),
        "selected_annotation": str(selected_annotation),
        "canonical_matrix": str(canonical_matrix),
        "decision": decision,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U26A5_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2))

    report = f"""# Phase U26A.5 - Final GSE280297 input resolution

- Version: `{VERSION}`
- Decision: **{decision}**
- Manuscript and existing figures were not modified.

## Asset resolution

The malformed repaired normalized matrix was excluded because its
`gene_symbol` column contains numeric expression values and samples B1-B3
are absent.

The selected primary matrix is:

`{selected_matrix}`

Its matching annotation is:

`{selected_annotation}`

## Matrix validation

- Canonical gene symbols: **{matrix_qc['n_canonical_gene_symbols']}**
- Expression samples: **{matrix_qc['n_expression_samples_present']}**
- Missing expected samples:
  **{matrix_qc['missing_expected_samples'] or 'none'}**
- Numeric completion:
  **{matrix_qc['numeric_completion_fraction']:.3f}**
- Expression-scale class:
  **{matrix_qc['expression_scale_class']}**

## Metadata validation

- Annotation match fraction:
  **{metadata_qc['annotation_match_fraction']:.3f}**
- Tissue completion:
  **{metadata_qc['tissue_completion']:.3f}**
- Treatment completion:
  **{metadata_qc['treatment_completion']:.3f}**
- Outcome completion:
  **{metadata_qc['outcome_completion']:.3f}**
- Pregnancy-status completion:
  **{metadata_qc['pregnancy_completion']:.3f}**
- Dam-ID completion among pregnancy samples:
  **{metadata_qc['dam_id_completion_pregnancy_samples']:.3f}**

Mock/PBS samples are represented as pregnancy controls.
Preterm, term, nonpregnant and mock-control outcomes remain separate.

## Statistical implication

{analysis_method.capitalize()}.

## U26B entry interpretation

- `READY_FOR_U26B`: tissue-stratified scoring and dam-aware outcome
  modeling can begin.
- `READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED`: tissue-stratified
  endocrine-metabolic-immune scoring can begin now, while maternal/dam-level
  AUROC or logistic models remain deferred.
- `TARGETED_METADATA_REVIEW_REQUIRED`: core metadata remain incomplete.
- `TARGETED_MATRIX_REVIEW_REQUIRED`: matrix structure remains unsuitable.
"""

    (
        out_results
        / "UTI_HostOmics_U26A5_final_input_resolution_report.md"
    ).write_text(report)

    log(
        f"Canonical genes: "
        f"{matrix_qc['n_canonical_gene_symbols']}"
    )
    log(
        f"Expression samples: "
        f"{matrix_qc['n_expression_samples_present']}"
    )
    log(
        f"Expression scale: "
        f"{matrix_qc['expression_scale_class']}"
    )
    log(f"Decision: {decision}")
    log(
        "Decision table: "
        + str(
            out_tables
            / "UTI_HostOmics_U26A5_phase_decision.tsv"
        )
    )
    log(
        "Report: "
        + str(
            out_results
            / "UTI_HostOmics_U26A5_final_input_resolution_report.md"
        )
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26A.5] ERROR: {exc}", file=sys.stderr)
        raise
