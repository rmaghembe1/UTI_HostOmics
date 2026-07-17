#!/usr/bin/env python3
"""
Phase U26B2A
Prepare and validate cross-dataset inputs for endocrine-metabolic-immune
integration across:

- GSE186800: recurrent/exposure bladder model, mouse bulk RNA-seq
- GSE112098: human urinary early-sepsis comparator
- GSE252321: UPEC-responsive mouse bladder single-cell study

The phase performs source discovery, matrix and annotation audits, bulk
canonicalization, single-cell object inspection, and an explicit readiness
decision. It does not modify the manuscript or existing figures.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

VERSION = "U26B2A_v1.0_2026-07-14"
PHASE_TAG = "phaseU26B2A_cross_dataset_input_preparation"

ACCESSIONS = {
    "GSE186800": {
        "species": "Mus musculus",
        "modality": "bulk_RNAseq",
        "expected_samples": 20,
        "expected_groups": "PBS_1;Gardnerella_1;PBS_2;Gardnerella_2",
        "biological_role": "recurrent_or_prior_exposure_bladder_model",
    },
    "GSE112098": {
        "species": "Homo sapiens",
        "modality": "urinary_expression_array",
        "expected_samples": 73,
        "expected_groups": "sepsis;vascular_surgery",
        "biological_role": "human_urinary_systemic_inflammation_comparator",
    },
    "GSE252321": {
        "species": "Mus musculus",
        "modality": "single_cell_RNAseq",
        "expected_samples": None,
        "expected_groups": "control;UPEC",
        "biological_role": "UPEC_responsive_cell_type_validation",
    },
}

SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,79}$")
ENSEMBL_RE = re.compile(
    r"^(?:ENSG|ENSMUSG|ENST|ENSMUST)\d+(?:\.\d+)?$",
    re.I,
)


def log(message: str) -> None:
    print(f"[U26B2A] {message}", flush=True)


def normalize_token(value: object) -> str:
    return re.sub(
        r"[^A-Za-z0-9]+",
        "",
        str(value).strip(),
    ).lower()


def normalize_symbol(value: object) -> str:
    return str(value).strip().strip('"').strip("'")


def symbol_like(value: object) -> bool:
    text = normalize_symbol(value)
    return (
        bool(SYMBOL_RE.fullmatch(text))
        and not text.isdigit()
        and not bool(ENSEMBL_RE.fullmatch(text))
        and text.lower() not in {"", "na", "nan", "none", "null"}
    )


def open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(
            path,
            "rt",
            encoding="utf-8",
            errors="replace",
        )
    return open(
        path,
        "rt",
        encoding="utf-8",
        errors="replace",
    )


def sniff_separator(path: Path) -> str:
    with open_text(path) as handle:
        line = handle.readline()

    return "\t" if line.count("\t") >= line.count(",") else ","


def read_delimited(
    path: Path,
    nrows: Optional[int] = None,
    dtype=None,
) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep=sniff_separator(path),
        compression="infer",
        nrows=nrows,
        dtype=dtype,
        low_memory=False,
    )


def excluded_candidate(path: Path) -> bool:
    text = str(path).lower()

    excluded_terms = [
        "module_scores",
        "module_score",
        "coverage",
        "contrast",
        "figure",
        "heatmap",
        "report",
        "summary",
        "decision",
        "gene_universe",
        "detected_gene",
        "phaseu26",
        "rank",
        "manifest",
    ]
    return any(term in text for term in excluded_terms)


def candidate_priority(path: Path) -> int:
    text = str(path).lower()
    score = 0

    if "repaired_gene_symbol_matrix" in text:
        score += 1000
    elif "clean_gene_symbol_matrix" in text:
        score += 850
    elif "gene_symbol" in text:
        score += 600

    if "normalized" in text:
        score += 120
    if "raw_genecpm" in text or "genecpm" in text:
        score += 140
    if "independentvalidationsetmatrix" in text:
        score += 160
    if "03_data_processed" in text:
        score += 80
    if "04_data_processed" in text:
        score += 60
    if "02_data_raw" in text:
        score += 20

    if "gene_count" in text:
        score += 30

    return score


def discover_bulk_matrices(
    project: Path,
    accession: str,
) -> List[Path]:
    roots = [
        project / "02_data_raw",
        project / "03_data_processed",
        project / "04_data_processed",
    ]

    extensions = {
        ".tsv",
        ".csv",
        ".txt",
        ".gz",
    }

    candidates: List[Path] = []
    seen = set()

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob(f"*{accession}*"):
            if not path.is_file() or path in seen:
                continue

            name = path.name.lower()
            if path.suffix.lower() not in extensions:
                continue

            if not any(
                term in name
                for term in [
                    "matrix",
                    "count",
                    "expression",
                    "genecpm",
                    "normalized",
                    "validation",
                ]
            ):
                continue

            if excluded_candidate(path):
                continue

            seen.add(path)
            candidates.append(path)

    return candidates


def audit_bulk_matrix(
    path: Path,
    expected_samples: int,
) -> Dict[str, object]:
    row: Dict[str, object] = {
        "path": str(path),
        "status": "unreadable",
        "priority": candidate_priority(path),
        "delimiter": "",
        "n_columns": 0,
        "n_rows_inspected": 0,
        "gene_column": "",
        "symbol_like_fraction": 0.0,
        "n_numeric_columns": 0,
        "sample_count_distance": "",
        "selection_score": -9999.0,
        "error": "",
    }

    try:
        preview = read_delimited(
            path,
            nrows=600,
            dtype=str,
        )
        row["status"] = "ok"
        row["delimiter"] = sniff_separator(path)
        row["n_columns"] = int(preview.shape[1])
        row["n_rows_inspected"] = int(preview.shape[0])

        best_column = None
        best_fraction = -1.0

        for column in list(preview.columns[:8]):
            values = preview[column].astype(str)
            fraction = float(values.map(symbol_like).mean())

            if fraction > best_fraction:
                best_column = str(column)
                best_fraction = fraction

        numeric_columns = []
        for column in preview.columns:
            if str(column) == str(best_column):
                continue

            numeric = pd.to_numeric(
                preview[column],
                errors="coerce",
            )

            if numeric.notna().mean() >= 0.85:
                numeric_columns.append(str(column))

        distance = abs(len(numeric_columns) - expected_samples)

        row["gene_column"] = (
            best_column if best_column is not None else ""
        )
        row["symbol_like_fraction"] = round(
            max(best_fraction, 0.0),
            6,
        )
        row["n_numeric_columns"] = len(numeric_columns)
        row["sample_count_distance"] = distance

        symbol_bonus = (
            400
            if best_fraction >= 0.80
            else 200
            if best_fraction >= 0.50
            else 0
        )
        sample_bonus = max(
            0,
            250 - 20 * distance,
        )

        row["selection_score"] = (
            row["priority"]
            + symbol_bonus
            + sample_bonus
            + min(len(numeric_columns), 100)
        )

    except Exception as exc:
        row["error"] = repr(exc)

    return row


def choose_bulk_matrix(
    audit: pd.DataFrame,
    expected_samples: int,
) -> pd.Series:
    readable = audit[audit["status"] == "ok"].copy()

    if readable.empty:
        raise RuntimeError(
            "No readable bulk-expression matrix candidate was found."
        )

    plausible = readable[
        (readable["symbol_like_fraction"] >= 0.50)
        & (
            np.abs(
                readable["n_numeric_columns"]
                - expected_samples
            )
            <= 5
        )
    ].copy()

    if not plausible.empty:
        return plausible.sort_values(
            ["selection_score", "priority"],
            ascending=False,
        ).iloc[0]

    return readable.sort_values(
        ["selection_score", "priority"],
        ascending=False,
    ).iloc[0]


def canonicalize_bulk_matrix(
    path: Path,
    gene_column: str,
    expected_samples: int,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    frame = read_delimited(path)

    if gene_column not in frame.columns:
        raise RuntimeError(
            f"Selected gene column {gene_column!r} not found in {path}"
        )

    symbols = frame[gene_column].map(normalize_symbol)
    keep = symbols.map(symbol_like)

    numeric_columns: List[str] = []
    for column in frame.columns:
        if str(column) == str(gene_column):
            continue

        numeric = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        if numeric.notna().mean() >= 0.85:
            frame[column] = numeric
            numeric_columns.append(str(column))

    if not numeric_columns:
        raise RuntimeError(
            f"No numeric sample columns found in {path}"
        )

    matrix = frame.loc[
        keep,
        [gene_column] + numeric_columns,
    ].copy()
    matrix.insert(
        0,
        "gene_symbol",
        symbols.loc[keep].values,
    )

    if gene_column != "gene_symbol":
        matrix.drop(
            columns=[gene_column],
            inplace=True,
        )

    duplicate_rows = int(
        matrix["gene_symbol"].duplicated().sum()
    )

    matrix = (
        matrix.groupby(
            "gene_symbol",
            as_index=False,
        )[numeric_columns]
        .mean(numeric_only=True)
        .sort_values("gene_symbol")
        .reset_index(drop=True)
    )

    values = matrix[numeric_columns].to_numpy(dtype=float)
    finite = values[np.isfinite(values)]

    non_integer_fraction = (
        float(
            np.mean(
                np.abs(finite - np.round(finite))
                > 1e-8
            )
        )
        if len(finite)
        else 1.0
    )

    qc = {
        "selected_source": str(path),
        "gene_column": gene_column,
        "n_input_rows": int(frame.shape[0]),
        "n_valid_symbol_rows": int(keep.sum()),
        "n_invalid_symbol_rows": int((~keep).sum()),
        "n_duplicate_symbol_rows_before_collapse": duplicate_rows,
        "n_canonical_gene_symbols": int(
            matrix["gene_symbol"].nunique()
        ),
        "n_expression_samples": len(numeric_columns),
        "expected_samples": expected_samples,
        "sample_count_difference": (
            len(numeric_columns) - expected_samples
        ),
        "non_integer_fraction": round(
            non_integer_fraction,
            6,
        ),
        "expression_scale_class": (
            "continuous_transformed_expression"
            if non_integer_fraction > 0.05
            else "integer_like_counts"
        ),
        "sample_columns": ";".join(numeric_columns),
        "gene_universe_plausible": bool(
            matrix["gene_symbol"].nunique() >= 8000
        ),
        "sample_count_plausible": bool(
            abs(len(numeric_columns) - expected_samples) <= 5
        ),
    }

    return matrix, qc


def discover_annotations(
    project: Path,
    accession: str,
) -> List[Path]:
    roots = [
        project / "03_metadata",
        project / "07_tables",
        project / "06_tables",
        project / "02_data_raw",
    ]

    candidates: List[Path] = []
    seen = set()

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob(f"*{accession}*"):
            if not path.is_file() or path in seen:
                continue

            name = path.name.lower()

            if not any(
                term in name
                for term in [
                    "annotation",
                    "metadata",
                    "design",
                    "phenotype",
                    "series_matrix",
                ]
            ):
                continue

            if any(
                term in name
                for term in [
                    "coverage",
                    "contrast",
                    "report",
                    "decision",
                    "summary",
                ]
            ):
                continue

            seen.add(path)
            candidates.append(path)

    return candidates


def parse_series_matrix(path: Path) -> pd.DataFrame:
    records: Dict[str, Dict[str, object]] = {}
    accessions: List[str] = []

    with open_text(path) as handle:
        for line in handle:
            if not line.startswith("!Sample_"):
                continue

            fields = next(
                csv.reader(
                    [line.rstrip("\n")],
                    delimiter="\t",
                    quotechar='"',
                )
            )
            key = fields[0].replace(
                "!Sample_",
                "",
                1,
            )
            values = fields[1:]

            if key == "geo_accession":
                accessions = [
                    value.strip()
                    for value in values
                ]

                for accession in accessions:
                    records.setdefault(
                        accession,
                        {"sample_geo_accession": accession},
                    )
                continue

            if (
                not accessions
                or len(values) != len(accessions)
            ):
                continue

            for accession, value in zip(
                accessions,
                values,
            ):
                value = value.strip()
                records.setdefault(
                    accession,
                    {"sample_geo_accession": accession},
                )

                if key == "characteristics_ch1":
                    existing = records[accession].get(
                        key,
                        [],
                    )
                    if not isinstance(existing, list):
                        existing = [str(existing)]
                    existing.append(value)
                    records[accession][key] = existing
                else:
                    existing = records[accession].get(
                        key,
                        "",
                    )
                    records[accession][key] = (
                        value
                        if not existing
                        else f"{existing} | {value}"
                    )

    rows = []
    for record in records.values():
        record = dict(record)
        characteristics = record.get(
            "characteristics_ch1",
            [],
        )

        if isinstance(characteristics, list):
            record["characteristics_ch1"] = " | ".join(
                characteristics
            )

        rows.append(record)

    return pd.DataFrame(rows)


def read_annotation_candidate(path: Path) -> pd.DataFrame:
    if "series_matrix" in path.name.lower():
        return parse_series_matrix(path)

    return read_delimited(
        path,
        dtype=str,
    )


def best_sample_id_column(
    annotation: pd.DataFrame,
    sample_columns: Sequence[str],
) -> Tuple[str, float]:
    sample_tokens = {
        normalize_token(sample)
        for sample in sample_columns
    }

    preferred = [
        "sample_id",
        "sample",
        "sample_name",
        "sample_geo_accession",
        "geo_accession",
        "gsm_accession",
        "title",
    ]

    lower = {
        str(column).lower(): column
        for column in annotation.columns
    }

    ordered_candidates = [
        lower[name]
        for name in preferred
        if name in lower
    ]
    ordered_candidates += [
        column
        for column in annotation.columns
        if column not in ordered_candidates
    ]

    best_column = ""
    best_overlap = 0.0

    for column in ordered_candidates:
        values = {
            normalize_token(value)
            for value in annotation[column]
            .dropna()
            .astype(str)
        }

        overlap = (
            len(sample_tokens & values)
            / len(sample_tokens)
            if sample_tokens
            else 0.0
        )

        if overlap > best_overlap:
            best_column = str(column)
            best_overlap = float(overlap)

    return best_column, best_overlap


def audit_annotation(
    path: Path,
    sample_columns: Sequence[str],
) -> Dict[str, object]:
    row: Dict[str, object] = {
        "path": str(path),
        "status": "unreadable",
        "n_rows": 0,
        "n_columns": 0,
        "sample_id_column": "",
        "sample_overlap_fraction": 0.0,
        "columns": "",
        "selection_score": -9999.0,
        "error": "",
    }

    try:
        annotation = read_annotation_candidate(path)
        sample_column, overlap = best_sample_id_column(
            annotation,
            sample_columns,
        )

        name = path.name.lower()
        priority = 0
        if "sample_annotation" in name:
            priority += 500
        if "design" in name:
            priority += 400
        if "metadata" in name:
            priority += 300
        if "series_matrix" in name:
            priority += 150
        if "repaired" in name:
            priority += 100

        row["status"] = "ok"
        row["n_rows"] = int(annotation.shape[0])
        row["n_columns"] = int(annotation.shape[1])
        row["sample_id_column"] = sample_column
        row["sample_overlap_fraction"] = round(
            overlap,
            6,
        )
        row["columns"] = ";".join(
            map(str, annotation.columns)
        )
        row["selection_score"] = (
            priority
            + 1000 * overlap
            - abs(annotation.shape[0] - len(sample_columns))
        )

    except Exception as exc:
        row["error"] = repr(exc)

    return row


def choose_annotation(
    audit: pd.DataFrame,
) -> pd.Series:
    readable = audit[audit["status"] == "ok"].copy()

    if readable.empty:
        raise RuntimeError(
            "No readable annotation candidate was found."
        )

    return readable.sort_values(
        ["selection_score", "sample_overlap_fraction"],
        ascending=False,
    ).iloc[0]


def canonicalize_annotation(
    path: Path,
    sample_id_column: str,
    sample_columns: Sequence[str],
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    annotation = read_annotation_candidate(path)

    if sample_id_column not in annotation.columns:
        raise RuntimeError(
            f"Sample ID column {sample_id_column!r} not found in {path}"
        )

    annotation = annotation.copy()
    annotation["_sample_token"] = annotation[
        sample_id_column
    ].map(normalize_token)
    annotation = annotation.drop_duplicates(
        subset=["_sample_token"],
        keep="first",
    )
    lookup = annotation.set_index("_sample_token")

    rows = []
    for sample in sample_columns:
        token = normalize_token(sample)

        if token in lookup.index:
            source = lookup.loc[token]
            matched = True
        else:
            source = pd.Series(dtype=object)
            matched = False

        row = {
            "sample_id": str(sample),
            "annotation_row_matched": matched,
        }

        for column in annotation.columns:
            if column == "_sample_token":
                continue
            row[str(column)] = source.get(
                column,
                "",
            )

        rows.append(row)

    design = pd.DataFrame(rows)

    qc = {
        "selected_annotation": str(path),
        "sample_id_column": sample_id_column,
        "n_expression_samples": len(sample_columns),
        "n_annotation_rows": int(annotation.shape[0]),
        "annotation_match_fraction": round(
            float(
                design["annotation_row_matched"]
                .astype(bool)
                .mean()
            ),
            6,
        ),
        "annotation_columns": ";".join(
            map(str, annotation.columns)
        ),
    }

    return design, qc


def summarize_design_text(
    design: pd.DataFrame,
) -> pd.DataFrame:
    likely_columns = [
        column
        for column in design.columns
        if any(
            term in str(column).lower()
            for term in [
                "group",
                "condition",
                "treatment",
                "outcome",
                "source",
                "title",
                "characteristic",
                "status",
                "exposure",
            ]
        )
    ]

    rows = []
    for column in likely_columns:
        counts = (
            design[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .value_counts(dropna=False)
        )

        for value, count in counts.head(25).items():
            if not value:
                continue

            rows.append(
                {
                    "column": str(column),
                    "value": value,
                    "n_samples": int(count),
                }
            )

    return pd.DataFrame(rows)


def find_h5ad_candidates(
    project: Path,
    accession: str,
) -> List[Path]:
    roots = [
        project / "02_data_raw",
        project / "03_data_processed",
        project / "04_data_processed",
    ]

    candidates: List[Path] = []
    seen = set()

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob("*.h5ad"):
            if path in seen:
                continue

            text = str(path).lower()

            if (
                accession.lower() in text
                or "upec" in text
                or "bladder" in text
            ):
                seen.add(path)
                candidates.append(path)

    return candidates


def find_single_cell_other_candidates(
    project: Path,
    accession: str,
) -> List[Path]:
    roots = [
        project / "02_data_raw",
        project / "03_data_processed",
        project / "04_data_processed",
    ]
    allowed_suffixes = {
        ".rds",
        ".rda",
        ".h5",
        ".hdf5",
        ".loom",
        ".mtx",
        ".gz",
    }

    candidates: List[Path] = []
    seen = set()

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob(f"*{accession}*"):
            if not path.is_file() or path in seen:
                continue

            if path.suffix.lower() not in allowed_suffixes:
                continue

            if path.suffix.lower() == ".h5ad":
                continue

            seen.add(path)
            candidates.append(path)

    return candidates


def detect_obs_column(
    columns: Sequence[str],
    preferred: Sequence[str],
) -> str:
    lower = {
        str(column).lower(): str(column)
        for column in columns
    }

    for candidate in preferred:
        if candidate.lower() in lower:
            return lower[candidate.lower()]

    for column in columns:
        lower_column = str(column).lower()

        if any(
            candidate.lower() in lower_column
            for candidate in preferred
        ):
            return str(column)

    return ""


def audit_h5ad(path: Path) -> Dict[str, object]:
    row: Dict[str, object] = {
        "path": str(path),
        "status": "unreadable",
        "n_cells": 0,
        "n_genes": 0,
        "sample_column": "",
        "condition_column": "",
        "cell_type_column": "",
        "n_biological_samples": 0,
        "n_conditions": 0,
        "n_cell_types": 0,
        "sample_counts": "",
        "condition_counts": "",
        "cell_type_counts": "",
        "selection_score": -9999.0,
        "error": "",
    }

    try:
        import anndata as ad

        object_ = ad.read_h5ad(
            path,
            backed="r",
        )

        obs_columns = list(
            map(str, object_.obs.columns)
        )

        sample_column = detect_obs_column(
            obs_columns,
            [
                "sample_id",
                "sample",
                "orig.ident",
                "donor",
                "replicate",
                "library",
                "mouse",
                "animal",
            ],
        )
        condition_column = detect_obs_column(
            obs_columns,
            [
                "condition",
                "treatment",
                "infection",
                "group",
                "status",
            ],
        )
        cell_type_column = detect_obs_column(
            obs_columns,
            [
                "cell_type",
                "celltype",
                "annotation",
                "cell_annotation",
                "broad_class",
                "cluster",
            ],
        )

        n_samples = (
            int(object_.obs[sample_column].nunique())
            if sample_column
            else 0
        )
        n_conditions = (
            int(object_.obs[condition_column].nunique())
            if condition_column
            else 0
        )
        n_cell_types = (
            int(object_.obs[cell_type_column].nunique())
            if cell_type_column
            else 0
        )

        row.update(
            {
                "status": "ok",
                "n_cells": int(object_.n_obs),
                "n_genes": int(object_.n_vars),
                "sample_column": sample_column,
                "condition_column": condition_column,
                "cell_type_column": cell_type_column,
                "n_biological_samples": n_samples,
                "n_conditions": n_conditions,
                "n_cell_types": n_cell_types,
                "sample_counts": (
                    object_.obs[sample_column]
                    .astype(str)
                    .value_counts()
                    .to_json()
                    if sample_column
                    else ""
                ),
                "condition_counts": (
                    object_.obs[condition_column]
                    .astype(str)
                    .value_counts()
                    .to_json()
                    if condition_column
                    else ""
                ),
                "cell_type_counts": (
                    object_.obs[cell_type_column]
                    .astype(str)
                    .value_counts()
                    .head(50)
                    .to_json()
                    if cell_type_column
                    else ""
                ),
            }
        )

        row["selection_score"] = (
            min(int(object_.n_obs), 100000) / 1000
            + 200 * bool(sample_column)
            + 200 * bool(condition_column)
            + 200 * bool(cell_type_column)
            + 50 * min(n_samples, 10)
        )

        if getattr(object_, "file", None) is not None:
            object_.file.close()

    except Exception as exc:
        row["error"] = repr(exc)

    return row


def r_package_status() -> Dict[str, object]:
    packages = [
        "Seurat",
        "SingleCellExperiment",
        "SummarizedExperiment",
    ]

    expression = "; ".join(
        [
            (
                f'cat("{package}=", '
                f'requireNamespace("{package}", quietly=TRUE), "\\n", sep="")'
            )
            for package in packages
        ]
    )

    try:
        completed = subprocess.run(
            ["Rscript", "-e", expression],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

        return {
            "Rscript_available": completed.returncode == 0,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }

    except Exception as exc:
        return {
            "Rscript_available": False,
            "stdout": "",
            "stderr": repr(exc),
        }


def extract_u26b1_family_hits(
    project: Path,
) -> pd.DataFrame:
    path = (
        project
        / "06_tables"
        / "phaseU26B1_1_GSE280297_stability_refinement"
        / "UTI_HostOmics_U26B1_1_primary_results.tsv"
    )

    if not path.exists():
        return pd.DataFrame()

    results = read_delimited(path)

    if "family_fdr_0_10" not in results.columns:
        return pd.DataFrame()

    hits = results[
        results["family_fdr_0_10"]
        .astype(str)
        .str.lower()
        .isin(["true", "1"])
    ].copy()

    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    output_metadata = project / "03_metadata" / PHASE_TAG
    output_processed = (
        project / "03_data_processed" / PHASE_TAG
    )
    output_results = project / "05_results" / PHASE_TAG
    output_tables = project / "06_tables" / PHASE_TAG

    for directory in [
        output_metadata,
        output_processed,
        output_results,
        output_tables,
    ]:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    bulk_status_rows = []
    selected_source_rows = []

    for accession in ["GSE186800", "GSE112098"]:
        expected_samples = int(
            ACCESSIONS[accession]["expected_samples"]
        )

        log(f"Auditing bulk inputs for {accession}.")

        candidates = discover_bulk_matrices(
            project,
            accession,
        )
        matrix_audit = pd.DataFrame(
            [
                audit_bulk_matrix(
                    path,
                    expected_samples,
                )
                for path in candidates
            ]
        )

        if matrix_audit.empty:
            matrix_audit = pd.DataFrame(
                columns=[
                    "path",
                    "status",
                    "priority",
                    "delimiter",
                    "n_columns",
                    "n_rows_inspected",
                    "gene_column",
                    "symbol_like_fraction",
                    "n_numeric_columns",
                    "sample_count_distance",
                    "selection_score",
                    "error",
                ]
            )

        matrix_audit.to_csv(
            output_tables
            / f"UTI_HostOmics_U26B2A_{accession}_matrix_candidate_audit.tsv",
            sep="\t",
            index=False,
        )

        try:
            selected = choose_bulk_matrix(
                matrix_audit,
                expected_samples,
            )
            selected_matrix = Path(
                str(selected["path"])
            )

            canonical, matrix_qc = canonicalize_bulk_matrix(
                selected_matrix,
                str(selected["gene_column"]),
                expected_samples,
            )

            canonical_path = (
                output_processed
                / f"{accession}_U26B2A_canonical_gene_symbol_expression.tsv.gz"
            )
            canonical.to_csv(
                canonical_path,
                sep="\t",
                index=False,
                compression="gzip",
            )

            pd.DataFrame([matrix_qc]).to_csv(
                output_tables
                / f"UTI_HostOmics_U26B2A_{accession}_matrix_qc.tsv",
                sep="\t",
                index=False,
            )

            sample_columns = [
                column
                for column in canonical.columns
                if column != "gene_symbol"
            ]

            annotation_candidates = discover_annotations(
                project,
                accession,
            )
            annotation_audit = pd.DataFrame(
                [
                    audit_annotation(
                        path,
                        sample_columns,
                    )
                    for path in annotation_candidates
                ]
            )

            if annotation_audit.empty:
                annotation_audit = pd.DataFrame(
                    columns=[
                        "path",
                        "status",
                        "n_rows",
                        "n_columns",
                        "sample_id_column",
                        "sample_overlap_fraction",
                        "columns",
                        "selection_score",
                        "error",
                    ]
                )

            annotation_audit.to_csv(
                output_tables
                / f"UTI_HostOmics_U26B2A_{accession}_annotation_candidate_audit.tsv",
                sep="\t",
                index=False,
            )

            selected_annotation = choose_annotation(
                annotation_audit
            )
            annotation_path = Path(
                str(selected_annotation["path"])
            )

            design, annotation_qc = canonicalize_annotation(
                annotation_path,
                str(
                    selected_annotation[
                        "sample_id_column"
                    ]
                ),
                sample_columns,
            )

            design_path = (
                output_metadata
                / f"{accession}_U26B2A_validated_sample_design.tsv"
            )
            design.to_csv(
                design_path,
                sep="\t",
                index=False,
            )

            pd.DataFrame([annotation_qc]).to_csv(
                output_tables
                / f"UTI_HostOmics_U26B2A_{accession}_annotation_qc.tsv",
                sep="\t",
                index=False,
            )

            design_summary = summarize_design_text(
                design
            )
            design_summary.to_csv(
                output_tables
                / f"UTI_HostOmics_U26B2A_{accession}_design_value_summary.tsv",
                sep="\t",
                index=False,
            )

            matrix_ready = bool(
                matrix_qc["gene_universe_plausible"]
                and matrix_qc["sample_count_plausible"]
            )
            annotation_ready = (
                annotation_qc[
                    "annotation_match_fraction"
                ]
                >= 0.90
            )

            dataset_ready = (
                matrix_ready and annotation_ready
            )

            bulk_status_rows.append(
                {
                    "dataset": accession,
                    "species": ACCESSIONS[
                        accession
                    ]["species"],
                    "modality": ACCESSIONS[
                        accession
                    ]["modality"],
                    "expected_samples": expected_samples,
                    "observed_samples": matrix_qc[
                        "n_expression_samples"
                    ],
                    "canonical_genes": matrix_qc[
                        "n_canonical_gene_symbols"
                    ],
                    "annotation_match_fraction": annotation_qc[
                        "annotation_match_fraction"
                    ],
                    "expression_scale_class": matrix_qc[
                        "expression_scale_class"
                    ],
                    "ready_for_scoring": dataset_ready,
                    "critical_note": (
                        "Use sample-level bulk contrasts; "
                        "do not pool raw expression across species."
                    ),
                }
            )

            selected_source_rows.append(
                {
                    "dataset": accession,
                    "selected_matrix": str(
                        selected_matrix
                    ),
                    "canonical_matrix": str(
                        canonical_path
                    ),
                    "selected_annotation": str(
                        annotation_path
                    ),
                    "validated_design": str(
                        design_path
                    ),
                }
            )

        except Exception as exc:
            bulk_status_rows.append(
                {
                    "dataset": accession,
                    "species": ACCESSIONS[
                        accession
                    ]["species"],
                    "modality": ACCESSIONS[
                        accession
                    ]["modality"],
                    "expected_samples": expected_samples,
                    "observed_samples": "",
                    "canonical_genes": "",
                    "annotation_match_fraction": "",
                    "expression_scale_class": "",
                    "ready_for_scoring": False,
                    "critical_note": repr(exc),
                }
            )

    bulk_status = pd.DataFrame(bulk_status_rows)
    bulk_status.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A_bulk_dataset_readiness.tsv",
        sep="\t",
        index=False,
    )

    pd.DataFrame(selected_source_rows).to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A_selected_bulk_sources.tsv",
        sep="\t",
        index=False,
    )

    log("Auditing GSE252321 single-cell assets.")

    h5ad_candidates = find_h5ad_candidates(
        project,
        "GSE252321",
    )
    h5ad_audit = pd.DataFrame(
        [
            audit_h5ad(path)
            for path in h5ad_candidates
        ]
    )

    if h5ad_audit.empty:
        h5ad_audit = pd.DataFrame(
            columns=[
                "path",
                "status",
                "n_cells",
                "n_genes",
                "sample_column",
                "condition_column",
                "cell_type_column",
                "n_biological_samples",
                "n_conditions",
                "n_cell_types",
                "sample_counts",
                "condition_counts",
                "cell_type_counts",
                "selection_score",
                "error",
            ]
        )

    h5ad_audit.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A_GSE252321_h5ad_candidate_audit.tsv",
        sep="\t",
        index=False,
    )

    other_sc_candidates = (
        find_single_cell_other_candidates(
            project,
            "GSE252321",
        )
    )
    pd.DataFrame(
        [
            {
                "path": str(path),
                "suffix": path.suffix,
                "size_bytes": path.stat().st_size,
            }
            for path in other_sc_candidates
        ]
    ).to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A_GSE252321_other_object_inventory.tsv",
        sep="\t",
        index=False,
    )

    r_status = r_package_status()
    (
        output_results
        / "UTI_HostOmics_U26B2A_R_single_cell_package_status.json"
    ).write_text(
        json.dumps(
            r_status,
            indent=2,
        )
    )

    single_cell_ready = False
    selected_h5ad = ""
    single_cell_note = ""

    readable_h5ad = h5ad_audit[
        h5ad_audit["status"] == "ok"
    ].copy()

    if not readable_h5ad.empty:
        selected = readable_h5ad.sort_values(
            "selection_score",
            ascending=False,
        ).iloc[0]

        selected_h5ad = str(selected["path"])

        single_cell_ready = bool(
            selected["sample_column"]
            and selected["condition_column"]
            and selected["cell_type_column"]
            and int(
                selected["n_biological_samples"]
            )
            >= 4
            and int(selected["n_conditions"]) >= 2
        )

        single_cell_note = (
            "Ready for sample_id x cell_type pseudobulk scoring."
            if single_cell_ready
            else (
                "Readable h5ad found, but sample, condition, "
                "cell-type, or biological-replicate metadata "
                "remain incomplete."
            )
        )
    elif other_sc_candidates:
        single_cell_note = (
            "No readable h5ad was found. RDS/H5/MTX assets exist; "
            "targeted object conversion or R inspection is required."
        )
    else:
        single_cell_note = (
            "No accession-linked single-cell object was found."
        )

    single_cell_status = pd.DataFrame(
        [
            {
                "dataset": "GSE252321",
                "species": ACCESSIONS[
                    "GSE252321"
                ]["species"],
                "modality": ACCESSIONS[
                    "GSE252321"
                ]["modality"],
                "selected_h5ad": selected_h5ad,
                "n_h5ad_candidates": len(
                    h5ad_candidates
                ),
                "n_other_object_candidates": len(
                    other_sc_candidates
                ),
                "ready_for_pseudobulk_scoring": single_cell_ready,
                "critical_note": single_cell_note,
            }
        ]
    )
    single_cell_status.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A_single_cell_readiness.tsv",
        sep="\t",
        index=False,
    )

    family_hits = extract_u26b1_family_hits(
        project
    )
    family_hits.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A_GSE280297_family_FDR10_hits.tsv",
        sep="\t",
        index=False,
    )

    bulk_ready_count = int(
        bulk_status["ready_for_scoring"]
        .astype(str)
        .str.lower()
        .isin(["true", "1"])
        .sum()
    )

    if bulk_ready_count == 2 and single_cell_ready:
        decision = "READY_FOR_U26B2B_ALL_DATASET_SCORING"
    elif bulk_ready_count == 2:
        decision = (
            "READY_FOR_U26B2B_BULK_SCORING_"
            "SINGLE_CELL_TARGETED_REPAIR"
        )
    elif bulk_ready_count >= 1:
        decision = (
            "PARTIAL_BULK_READINESS_TARGETED_INPUT_REVIEW"
        )
    else:
        decision = "TARGETED_INPUT_REVIEW_REQUIRED"

    decision_table = pd.DataFrame(
        [
            {
                "phase": "U26B2A",
                "decision": decision,
                "n_bulk_datasets_ready": bulk_ready_count,
                "single_cell_ready": single_cell_ready,
                "n_GSE280297_family_FDR10_hits": len(
                    family_hits
                ),
                "cross_species_rule": (
                    "Score each dataset in its native species and "
                    "integrate standardized effects or ortholog-aware "
                    "module identities; never pool raw expression."
                ),
                "single_cell_analysis_unit": (
                    "sample_id x cell_type pseudobulk; cell-level "
                    "distributions are descriptive only."
                ),
                "human_comparator_rule": (
                    "GSE112098 is a urinary systemic-inflammation "
                    "comparator, not direct UTI evidence."
                ),
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U26B2B dataset-appropriate scoring and "
                    "standardized-effect integration"
                ),
            }
        ]
    )
    decision_table.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_lines = [
        "# Phase U26B2A - Cross-dataset input preparation",
        "",
        f"- Version: `{VERSION}`",
        f"- Decision: **{decision}**",
        "- Manuscript and existing Figures 1-6 were not modified.",
        "",
        "## Bulk datasets",
        "",
    ]

    for _, row in bulk_status.iterrows():
        report_lines.extend(
            [
                f"### {row['dataset']}",
                "",
                f"- Ready for scoring: **{row['ready_for_scoring']}**",
                f"- Observed samples: **{row['observed_samples']}**",
                f"- Canonical genes: **{row['canonical_genes']}**",
                (
                    "- Annotation match fraction: "
                    f"**{row['annotation_match_fraction']}**"
                ),
                (
                    "- Expression scale: "
                    f"**{row['expression_scale_class']}**"
                ),
                f"- Note: {row['critical_note']}",
                "",
            ]
        )

    report_lines.extend(
        [
            "## Single-cell dataset",
            "",
            (
                "- Ready for sample-by-cell-type pseudobulk scoring: "
                f"**{single_cell_ready}**"
            ),
            f"- Selected h5ad: `{selected_h5ad}`",
            f"- Note: {single_cell_note}",
            "",
            "## GSE280297 refinement carry-forward",
            "",
            (
                "- Family-specific permutation FDR < 0.10 hits: "
                f"**{len(family_hits)}**"
            ),
            (
                "- GSE280297 remains a tissue-resolved "
                "effect-direction and pathway-architecture layer."
            ),
            "",
            "## Integration rules",
            "",
            (
                "- Score each dataset in its native species and "
                "technology context."
            ),
            (
                "- Integrate standardized submodule effects and "
                "directional recurrence; do not pool raw expression."
            ),
            (
                "- Treat GSE112098 as a human urinary systemic-"
                "inflammation comparator rather than UTI-specific evidence."
            ),
            (
                "- Use sample-level pseudobulk for GSE252321; "
                "do not treat cells as independent biological replicates."
            ),
        ]
    )

    report_path = (
        output_results
        / "UTI_HostOmics_U26B2A_cross_dataset_input_report.md"
    )
    report_path.write_text(
        "\n".join(report_lines) + "\n"
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "decision": decision,
        "bulk_ready_count": bulk_ready_count,
        "single_cell_ready": single_cell_ready,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        output_results
        / "UTI_HostOmics_U26B2A_run_manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
        )
    )

    log(f"Bulk datasets ready: {bulk_ready_count}/2")
    log(f"Single-cell ready: {single_cell_ready}")
    log(
        f"GSE280297 family FDR10 hits carried forward: "
        f"{len(family_hits)}"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"[U26B2A] ERROR: {exc}",
            file=sys.stderr,
        )
        raise
