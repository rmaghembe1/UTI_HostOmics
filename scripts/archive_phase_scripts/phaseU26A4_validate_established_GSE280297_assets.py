#!/usr/bin/env python3
"""
Phase U26A.4
Validate the established repaired GSE280297 matrix and its matching sample
annotation, then issue the U26B entry decision.

This phase does not modify the manuscript or existing figures.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

VERSION = "U26A4_v1.0_2026-07-14"
PHASE_TAG = "phaseU26A4_GSE280297_established_asset_validation"

SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{1,39}$")
MOUSE_ENSEMBL_RE = re.compile(r"^ENSMUSG\d+(?:\.\d+)?$", re.I)


def log(message: str) -> None:
    print(f"[U26A.4] {message}", flush=True)


def normalize_token(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value).strip()).lower()


def normalize_symbol(value: object) -> str:
    return str(value).strip().strip('"').strip("'")


def read_table(path: Path, nrows: Optional[int] = None) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        compression="infer",
        low_memory=False,
        nrows=nrows,
    )


def detect_gene_column(df: pd.DataFrame) -> str:
    preferred = [
        "gene_symbol",
        "symbol",
        "gene",
        "gene_name",
        "external_gene_name",
    ]
    lower = {str(c).lower(): c for c in df.columns}
    for name in preferred:
        if name in lower:
            return lower[name]

    best_col = None
    best_fraction = -1.0
    for col in list(df.columns[:6]):
        values = df[col].astype(str).head(1000)
        valid = values.map(
            lambda x: bool(SYMBOL_RE.match(normalize_symbol(x)))
            and not bool(MOUSE_ENSEMBL_RE.match(normalize_symbol(x)))
            and not normalize_symbol(x).isdigit()
        )
        fraction = float(valid.mean())
        if fraction > best_fraction:
            best_col = col
            best_fraction = fraction

    if best_col is None or best_fraction < 0.50:
        raise RuntimeError(
            "Could not identify a plausible gene-symbol column."
        )
    return str(best_col)


def detect_expression_columns(
    df: pd.DataFrame,
    gene_column: str,
) -> List[str]:
    expression_columns: List[str] = []

    for col in df.columns:
        if col == gene_column:
            continue

        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().mean() >= 0.90:
            expression_columns.append(str(col))

    # Prefer the known B/U/P naming architecture when present.
    bup = [
        col
        for col in expression_columns
        if re.fullmatch(r"[BUP]\d+", col, flags=re.I)
    ]
    if len(bup) >= 50:
        return bup

    return expression_columns


def matrix_qc(path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    df = read_table(path)
    gene_col = detect_gene_column(df)
    sample_cols = detect_expression_columns(df, gene_col)

    symbols = df[gene_col].map(normalize_symbol)
    keep = symbols.map(
        lambda x: bool(SYMBOL_RE.match(x))
        and not bool(MOUSE_ENSEMBL_RE.match(x))
        and not x.isdigit()
    )

    mat = df.loc[keep, [gene_col] + sample_cols].copy()
    mat.rename(columns={gene_col: "gene_symbol"}, inplace=True)

    for col in sample_cols:
        mat[col] = pd.to_numeric(mat[col], errors="coerce")

    duplicate_rows = int(mat["gene_symbol"].duplicated().sum())
    mat = (
        mat.groupby("gene_symbol", as_index=False)[sample_cols]
        .mean(numeric_only=True)
        .sort_values("gene_symbol")
        .reset_index(drop=True)
    )

    qc = {
        "matrix_path": str(path),
        "gene_column": str(gene_col),
        "n_input_rows": int(df.shape[0]),
        "n_valid_symbol_rows": int(keep.sum()),
        "n_duplicate_symbol_rows": duplicate_rows,
        "n_canonical_gene_symbols": int(mat["gene_symbol"].nunique()),
        "n_expression_samples": int(len(sample_cols)),
        "sample_columns": ";".join(sample_cols),
        "gene_universe_plausible": bool(
            mat["gene_symbol"].nunique() >= 10000
        ),
        "sample_count_plausible": bool(55 <= len(sample_cols) <= 65),
    }
    return mat, qc


def choose_sample_id_column(
    annotation: pd.DataFrame,
    expression_samples: Sequence[str],
) -> Tuple[str, float]:
    expression_norm = {normalize_token(x) for x in expression_samples}

    preferred = [
        "sample_id",
        "sample",
        "sample_name",
        "sampleid",
        "gsm_accession",
        "gsm",
        "title",
    ]
    lower = {str(c).lower(): c for c in annotation.columns}

    candidate_columns = []
    for name in preferred:
        if name in lower:
            candidate_columns.append(lower[name])
    candidate_columns.extend(
        [c for c in annotation.columns if c not in candidate_columns]
    )

    best_col = None
    best_overlap = -1.0
    for col in candidate_columns:
        values = {
            normalize_token(x)
            for x in annotation[col].dropna().astype(str)
        }
        overlap = (
            len(expression_norm & values) / len(expression_norm)
            if expression_norm
            else 0.0
        )
        if overlap > best_overlap:
            best_col = col
            best_overlap = overlap

    if best_col is None:
        raise RuntimeError(
            "Could not identify a sample identifier column."
        )

    return str(best_col), float(best_overlap)


def row_text(row: pd.Series) -> str:
    return " | ".join(
        str(value)
        for value in row.values
        if str(value).lower() != "nan"
    )


def infer_tissue(sample_id: str, text: str) -> str:
    lower = text.lower()

    if "bladder" in lower:
        return "bladder"
    if "placenta" in lower or "placental" in lower:
        return "placenta"
    if "uterus" in lower or "uterine" in lower:
        return "uterus"

    match = re.fullmatch(r"([BUP])\d+", sample_id, flags=re.I)
    if match:
        return {
            "B": "bladder",
            "U": "uterus",
            "P": "placenta",
        }[match.group(1).upper()]

    return ""


def infer_treatment(text: str) -> str:
    lower = text.lower()

    if re.search(
        r"\buti[-_ ]?89\b|\buropathogenic\b|\bupec\b",
        lower,
    ):
        return "UTI89"

    if re.search(
        r"\bpbs\b|\bmock\b|\bvehicle\b|\bcontrol\b",
        lower,
    ):
        return "PBS_or_control"

    return ""


def infer_outcome(text: str) -> str:
    lower = text.lower()

    if re.search(r"\bnon[-_ ]?pregnant\b", lower):
        return "nonpregnant"

    if re.search(r"\bpreterm\b|\bpremature\b", lower):
        return "preterm"

    if re.search(
        r"\bterm\b|\bnon[-_ ]?labor|\bnonlabor",
        lower,
    ):
        return "term_or_nonlaboring"

    return ""


def infer_pregnancy(outcome: str, text: str) -> str:
    lower = text.lower()

    if outcome == "nonpregnant":
        return "nonpregnant"

    if outcome in {"preterm", "term_or_nonlaboring"}:
        return "pregnant"

    if re.search(r"\bpregnan", lower):
        return "pregnant"

    return ""


def infer_dam_id(text: str) -> str:
    patterns = [
        r"\b(?:dam[_ ]?id|mouse[_ ]?id|animal[_ ]?id)"
        r"[:= _-]*([A-Za-z0-9.-]+)\b",
        r"\b(?:dam|mouse|animal|mother)"
        r"[:= _#-]+([A-Za-z0-9.-]+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            candidate = match.group(1)
            if candidate.lower() not in {
                "bladder",
                "uterus",
                "placenta",
                "pregnant",
                "preterm",
                "term",
                "uti89",
                "pbs",
            }:
                return candidate

    return ""


def build_design(
    annotation: pd.DataFrame,
    annotation_sample_column: str,
    expression_samples: Sequence[str],
) -> pd.DataFrame:
    lookup: Dict[str, pd.Series] = {}

    for _, row in annotation.iterrows():
        key = normalize_token(row.get(annotation_sample_column, ""))
        if key and key not in lookup:
            lookup[key] = row

    rows = []
    for sample in expression_samples:
        key = normalize_token(sample)
        source = lookup.get(key)

        if source is None:
            text = sample
            matched = False
        else:
            text = row_text(source)
            matched = True

        tissue = infer_tissue(str(sample), text)
        treatment = infer_treatment(text)
        outcome = infer_outcome(text)
        pregnancy = infer_pregnancy(outcome, text)
        dam_id = infer_dam_id(text)

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
                "sample_id": str(sample),
                "annotation_row_matched": matched,
                "tissue": tissue,
                "treatment": treatment,
                "outcome": outcome,
                "pregnancy_status": pregnancy,
                "dam_id": dam_id,
                "unresolved_required_fields": ";".join(unresolved),
                "annotation_evidence": text,
            }
        )

    return pd.DataFrame(rows)


def completion(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0

    return float(
        series.fillna("").astype(str).str.strip().ne("").mean()
    )


def load_submodule_library(project: Path) -> Optional[pd.DataFrame]:
    path = (
        project
        / "03_metadata"
        / "phaseU26A_expanded_endocrine_metabolic_immune_feasibility"
        / "UTI_HostOmics_U26A_expanded_submodule_library.tsv"
    )

    if not path.exists():
        return None

    return pd.read_csv(path, sep="\t", dtype=str)


def find_gene_list_column(library: pd.DataFrame) -> str:
    preferred = [
        "genes",
        "gene_symbols",
        "members",
        "gene_list",
        "symbols",
    ]

    for col in preferred:
        if col in library.columns:
            return col

    for col in library.columns:
        if "gene" in str(col).lower():
            return str(col)

    raise RuntimeError(
        "Could not identify the gene-list column in the U26A library."
    )


def recalculate_coverage(
    library: Optional[pd.DataFrame],
    gene_symbols: Iterable[str],
) -> pd.DataFrame:
    if library is None:
        return pd.DataFrame()

    gene_column = find_gene_list_column(library)
    universe = {str(gene).upper() for gene in gene_symbols}

    rows = []
    for _, row in library.iterrows():
        raw_genes = str(row[gene_column])
        members = [
            value.strip()
            for value in re.split(r"[;,| ]+", raw_genes)
            if value.strip()
            and value.strip().lower() != "nan"
        ]
        detected = [
            gene for gene in members if gene.upper() in universe
        ]
        fraction = (
            len(detected) / len(members) if members else math.nan
        )

        if members and len(detected) >= 5 and fraction >= 0.50:
            coverage_class = "adequate"
        elif members and len(detected) >= 3 and fraction >= 0.25:
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
                "n_library_genes": len(members),
                "n_detected_genes": len(detected),
                "coverage_fraction": (
                    round(fraction, 4) if members else ""
                ),
                "coverage_class": coverage_class,
                "detected_genes": ";".join(detected),
            }
        )

    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    normalized_matrix = (
        project
        / "03_data_processed"
        / "phaseU4b_repaired_matrices"
        / "GSE280297_normalized_repaired_gene_symbol_matrix.tsv.gz"
    )
    normalized_annotation = (
        project
        / "07_tables"
        / "phaseU4b_repaired_module_scores"
        / "GSE280297_normalized_repaired_sample_annotation_v1.tsv"
    )

    gene_count_matrix = (
        project
        / "03_data_processed"
        / "phaseU4b_repaired_matrices"
        / "GSE280297_gene_count_repaired_gene_symbol_matrix.tsv.gz"
    )
    gene_count_annotation = (
        project
        / "07_tables"
        / "phaseU4b_repaired_module_scores"
        / "GSE280297_gene_count_repaired_sample_annotation_v1.tsv"
    )

    out_meta = project / "03_metadata" / PHASE_TAG
    out_results = project / "05_results" / PHASE_TAG
    out_tables = project / "06_tables" / PHASE_TAG

    for directory in [out_meta, out_results, out_tables]:
        directory.mkdir(parents=True, exist_ok=True)

    input_rows = []
    for matrix, annotation, role in [
        (
            normalized_matrix,
            normalized_annotation,
            "primary_normalized_repaired",
        ),
        (
            gene_count_matrix,
            gene_count_annotation,
            "secondary_raw_count_repaired",
        ),
    ]:
        input_rows.append(
            {
                "role": role,
                "matrix": str(matrix),
                "matrix_exists": matrix.exists(),
                "matrix_size_bytes": (
                    matrix.stat().st_size if matrix.exists() else 0
                ),
                "annotation": str(annotation),
                "annotation_exists": annotation.exists(),
                "annotation_size_bytes": (
                    annotation.stat().st_size
                    if annotation.exists()
                    else 0
                ),
            }
        )

    pd.DataFrame(input_rows).to_csv(
        out_tables
        / "UTI_HostOmics_U26A4_established_input_inventory.tsv",
        sep="\t",
        index=False,
    )

    if not normalized_matrix.exists():
        raise FileNotFoundError(
            f"Primary repaired normalized matrix is missing: "
            f"{normalized_matrix}"
        )

    if not normalized_annotation.exists():
        raise FileNotFoundError(
            f"Matching repaired normalized annotation is missing: "
            f"{normalized_annotation}"
        )

    log(f"Primary matrix: {normalized_matrix}")
    log(f"Primary annotation: {normalized_annotation}")

    matrix, qc = matrix_qc(normalized_matrix)
    pd.DataFrame([qc]).to_csv(
        out_tables
        / "UTI_HostOmics_U26A4_GSE280297_matrix_qc.tsv",
        sep="\t",
        index=False,
    )

    annotation = read_table(normalized_annotation)
    sample_columns = [
        col for col in matrix.columns if col != "gene_symbol"
    ]

    sample_id_column, direct_overlap = choose_sample_id_column(
        annotation,
        sample_columns,
    )

    design = build_design(
        annotation,
        sample_id_column,
        sample_columns,
    )
    design_path = (
        out_meta
        / "GSE280297_U26A4_validated_sample_design.tsv"
    )
    design.to_csv(design_path, sep="\t", index=False)

    matched_fraction = float(
        design["annotation_row_matched"].mean()
    )
    tissue_completion = completion(design["tissue"])
    treatment_completion = completion(design["treatment"])
    outcome_completion = completion(design["outcome"])
    pregnancy_completion = completion(
        design["pregnancy_status"]
    )
    dam_all_completion = completion(design["dam_id"])

    pregnant = design[
        design["pregnancy_status"] == "pregnant"
    ]
    dam_pregnant_completion = (
        completion(pregnant["dam_id"])
        if len(pregnant)
        else 0.0
    )

    coverage = recalculate_coverage(
        load_submodule_library(project),
        matrix["gene_symbol"],
    )
    if not coverage.empty:
        coverage.to_csv(
            out_tables
            / "UTI_HostOmics_U26A4_GSE280297_submodule_coverage.tsv",
            sep="\t",
            index=False,
        )

    matrix_ready = bool(
        qc["gene_universe_plausible"]
        and qc["sample_count_plausible"]
    )
    core_design_ready = bool(
        matched_fraction >= 0.95
        and tissue_completion >= 0.95
        and treatment_completion >= 0.85
        and outcome_completion >= 0.85
    )
    dam_ready = dam_pregnant_completion >= 0.90

    if matrix_ready and core_design_ready and dam_ready:
        decision = "READY_FOR_U26B"
        core_status = "ready"
        dam_status = "ready"
    elif matrix_ready and core_design_ready:
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

    decision_row = {
        "phase": "U26A.4",
        "overall_decision": decision,
        "primary_matrix": str(normalized_matrix),
        "primary_annotation": str(normalized_annotation),
        "annotation_sample_id_column": sample_id_column,
        "direct_sample_overlap_fraction": round(
            direct_overlap, 4
        ),
        "annotation_match_fraction": round(
            matched_fraction, 4
        ),
        "n_canonical_gene_symbols": qc[
            "n_canonical_gene_symbols"
        ],
        "n_expression_samples": qc[
            "n_expression_samples"
        ],
        "tissue_completion": round(
            tissue_completion, 4
        ),
        "treatment_completion": round(
            treatment_completion, 4
        ),
        "outcome_completion": round(
            outcome_completion, 4
        ),
        "pregnancy_completion": round(
            pregnancy_completion, 4
        ),
        "dam_id_completion_all": round(
            dam_all_completion, 4
        ),
        "dam_id_completion_pregnant": round(
            dam_pregnant_completion, 4
        ),
        "core_tissue_stratified_scoring": core_status,
        "dam_level_pregnancy_outcome_model": dam_status,
        "critical_rule": (
            "Use the established repaired normalized matrix and matching "
            "sample annotation. Use B/U/P only as tissue labels. Do not "
            "treat multiple tissues from the same dam as independent."
        ),
    }

    pd.DataFrame([decision_row]).to_csv(
        out_tables
        / "UTI_HostOmics_U26A4_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    group_summary = (
        design.groupby(
            [
                "tissue",
                "treatment",
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
        / "UTI_HostOmics_U26A4_GSE280297_group_summary.tsv",
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
        / "UTI_HostOmics_U26A4_unresolved_sample_design_rows.tsv",
        sep="\t",
        index=False,
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "primary_matrix": str(normalized_matrix),
        "primary_annotation": str(normalized_annotation),
        "decision": decision,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U26A4_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2))

    report = f"""# Phase U26A.4 - Established GSE280297 asset validation

- Version: `{VERSION}`
- Decision: **{decision}**
- Manuscript and existing figures were not modified.

## Established primary assets

- Repaired normalized matrix:
  `{normalized_matrix}`
- Matching sample annotation:
  `{normalized_annotation}`

## Matrix validation

- Canonical gene symbols: **{qc['n_canonical_gene_symbols']}**
- Expression samples: **{qc['n_expression_samples']}**
- Gene universe plausible: **{qc['gene_universe_plausible']}**
- Sample count plausible: **{qc['sample_count_plausible']}**

## Sample-design validation

- Annotation sample-ID column: `{sample_id_column}`
- Direct sample overlap: **{direct_overlap:.3f}**
- Annotation match fraction: **{matched_fraction:.3f}**
- Tissue completion: **{tissue_completion:.3f}**
- Treatment completion: **{treatment_completion:.3f}**
- Outcome completion: **{outcome_completion:.3f}**
- Pregnancy completion: **{pregnancy_completion:.3f}**
- Dam-ID completion among pregnant samples:
  **{dam_pregnant_completion:.3f}**

## U26B interpretation

- `READY_FOR_U26B`: tissue-stratified scoring and dam-aware outcome
  modeling can begin.
- `READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED`: tissue-stratified
  scoring can begin, while maternal/dam-level AUROC and logistic models
  remain deferred.
- `TARGETED_METADATA_REVIEW_REQUIRED`: the matrix is valid, but core
  treatment or outcome metadata require focused reconstruction.
- `TARGETED_MATRIX_REVIEW_REQUIRED`: the selected repaired matrix did
  not pass gene-universe or sample-count checks.
"""

    (
        out_results
        / "UTI_HostOmics_U26A4_established_asset_validation_report.md"
    ).write_text(report)

    log(
        f"Canonical genes: "
        f"{qc['n_canonical_gene_symbols']}"
    )
    log(
        f"Expression samples: "
        f"{qc['n_expression_samples']}"
    )
    log(f"Decision: {decision}")
    log(
        "Decision table: "
        + str(
            out_tables
            / "UTI_HostOmics_U26A4_phase_decision.tsv"
        )
    )
    log(
        "Report: "
        + str(
            out_results
            / "UTI_HostOmics_U26A4_established_asset_validation_report.md"
        )
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26A.4] ERROR: {exc}", file=sys.stderr)
        raise
