#!/usr/bin/env python3
"""
Phase U26B2A.1
Repair cross-dataset input preparation after U26B2A.

Repairs:
1. Handles matrices whose selected gene column is already named gene_symbol.
2. Uses established repaired matrices directly:
   - GSE186800: 20-sample repaired mouse bladder matrix.
   - GSE112098: 73-sample repaired human urinary comparator matrix.
3. Searches project-wide for matching sample annotations.
4. Inventories every file under GSE252321, including GSM-named matrices.
5. Builds light sample-level single-cell pseudobulk when four or more
   gene-by-cell matrices are available.
6. Keeps cell-type pseudobulk deferred unless cell-level annotations exist.

No manuscript or existing figures are modified.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

VERSION = "U26B2A1_v1.0_2026-07-14"
PHASE_TAG = "phaseU26B2A1_cross_dataset_input_repair"

SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,79}$")
ENSEMBL_RE = re.compile(r"^(?:ENSG|ENSMUSG)\d+(?:\.\d+)?$", re.I)


def log(message: str) -> None:
    print(f"[U26B2A.1] {message}", flush=True)


def open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "rt", encoding="utf-8", errors="replace")


def sniff_separator(path: Path) -> str:
    with open_text(path) as handle:
        line = handle.readline()
    return "\t" if line.count("\t") >= line.count(",") else ","


def read_table(path: Path, nrows: Optional[int] = None, dtype=None) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep=sniff_separator(path),
        compression="infer",
        nrows=nrows,
        dtype=dtype,
        low_memory=False,
    )


def normalize_symbol(value: object) -> str:
    return str(value).strip().strip('"').strip("'")


def valid_symbol(value: object) -> bool:
    text = normalize_symbol(value)
    return (
        bool(SYMBOL_RE.fullmatch(text))
        and not text.isdigit()
        and not bool(ENSEMBL_RE.fullmatch(text))
        and text.lower() not in {"", "na", "nan", "none", "null"}
    )


def normalize_token(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value).strip()).lower()


def canonicalize_matrix(
    path: Path,
    expected_samples: int,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    frame = read_table(path)

    if "gene_symbol" in frame.columns:
        gene_column = "gene_symbol"
    else:
        best_column = None
        best_fraction = -1.0
        for column in list(frame.columns[:8]):
            fraction = float(
                frame[column].astype(str).head(1000).map(valid_symbol).mean()
            )
            if fraction > best_fraction:
                best_column = str(column)
                best_fraction = fraction
        if best_column is None or best_fraction < 0.50:
            raise RuntimeError(f"No plausible gene-symbol column found in {path}")
        gene_column = best_column

    symbols = frame[gene_column].map(normalize_symbol)
    keep = symbols.map(valid_symbol)

    numeric_columns: List[str] = []
    for column in frame.columns:
        if str(column) == gene_column:
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.notna().mean() >= 0.85:
            frame[column] = numeric
            numeric_columns.append(str(column))

    if not numeric_columns:
        raise RuntimeError(f"No numeric expression columns found in {path}")

    matrix = frame.loc[keep, numeric_columns].copy()
    matrix.insert(0, "gene_symbol", symbols.loc[keep].values)

    duplicate_rows = int(matrix["gene_symbol"].duplicated().sum())
    matrix = (
        matrix.groupby("gene_symbol", as_index=False)[numeric_columns]
        .mean(numeric_only=True)
        .sort_values("gene_symbol")
        .reset_index(drop=True)
    )

    values = matrix[numeric_columns].iloc[: min(2000, len(matrix))].to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    non_integer_fraction = (
        float(np.mean(np.abs(finite - np.round(finite)) > 1e-8))
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
        "n_canonical_gene_symbols": int(matrix["gene_symbol"].nunique()),
        "n_expression_samples": len(numeric_columns),
        "expected_samples": expected_samples,
        "sample_count_difference": len(numeric_columns) - expected_samples,
        "sample_columns": ";".join(numeric_columns),
        "non_integer_fraction_preview": round(non_integer_fraction, 6),
        "expression_scale_class": (
            "continuous_transformed_expression"
            if non_integer_fraction > 0.05
            else "integer_like_counts"
        ),
        "gene_universe_plausible": bool(matrix["gene_symbol"].nunique() >= 8000),
        "sample_count_plausible": bool(
            abs(len(numeric_columns) - expected_samples) <= 2
        ),
    }
    return matrix, qc


def parse_series_matrix(path: Path) -> pd.DataFrame:
    records: Dict[str, Dict[str, object]] = {}
    accessions: List[str] = []

    with open_text(path) as handle:
        for line in handle:
            if not line.startswith("!Sample_"):
                continue
            fields = next(
                csv.reader([line.rstrip("\n")], delimiter="\t", quotechar='"')
            )
            key = fields[0].replace("!Sample_", "", 1)
            values = fields[1:]

            if key == "geo_accession":
                accessions = [value.strip() for value in values]
                for accession in accessions:
                    records.setdefault(
                        accession,
                        {"sample_geo_accession": accession},
                    )
                continue

            if not accessions or len(values) != len(accessions):
                continue

            for accession, value in zip(accessions, values):
                value = value.strip()
                records.setdefault(
                    accession,
                    {"sample_geo_accession": accession},
                )
                if key == "characteristics_ch1":
                    prior = records[accession].get(key, [])
                    if not isinstance(prior, list):
                        prior = [str(prior)]
                    prior.append(value)
                    records[accession][key] = prior
                else:
                    prior = records[accession].get(key, "")
                    records[accession][key] = (
                        value if not prior else f"{prior} | {value}"
                    )

    rows = []
    for record in records.values():
        row = dict(record)
        characteristics = row.get("characteristics_ch1", [])
        if isinstance(characteristics, list):
            row["characteristics_ch1"] = " | ".join(characteristics)
        rows.append(row)
    return pd.DataFrame(rows)


def annotation_candidates(project: Path, accession: str) -> List[Path]:
    roots = [
        project / "03_metadata",
        project / "06_tables",
        project / "07_tables",
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
            lower = path.name.lower()
            if any(
                token in lower
                for token in [
                    "sample_annotation",
                    "annotation",
                    "sample_design",
                    "design",
                    "metadata",
                    "series_matrix",
                ]
            ):
                if not any(
                    token in lower
                    for token in [
                        "coverage",
                        "contrast",
                        "decision",
                        "report",
                        "summary",
                    ]
                ):
                    seen.add(path)
                    candidates.append(path)
    return candidates


def load_annotation(path: Path) -> pd.DataFrame:
    if "series_matrix" in path.name.lower():
        return parse_series_matrix(path)
    return read_table(path, dtype=str)


def best_sample_column(
    annotation: pd.DataFrame,
    expression_samples: Sequence[str],
) -> Tuple[str, float]:
    expected = {normalize_token(sample) for sample in expression_samples}
    preferred = [
        "sample_id",
        "sample",
        "sample_name",
        "sample_geo_accession",
        "geo_accession",
        "gsm_accession",
        "title",
    ]
    lower_map = {str(column).lower(): str(column) for column in annotation.columns}

    ordered = [lower_map[name] for name in preferred if name in lower_map]
    ordered += [str(column) for column in annotation.columns if str(column) not in ordered]

    best_column = ""
    best_overlap = -1.0

    for column in ordered:
        values = {
            normalize_token(value)
            for value in annotation[column].dropna().astype(str)
        }
        overlap = len(expected & values) / len(expected) if expected else 0.0
        if overlap > best_overlap:
            best_column = column
            best_overlap = overlap

    return best_column, float(max(best_overlap, 0.0))


def select_annotation(
    project: Path,
    accession: str,
    expression_samples: Sequence[str],
) -> Tuple[Path, pd.DataFrame, str, float, pd.DataFrame]:
    audit_rows = []

    for path in annotation_candidates(project, accession):
        row = {
            "path": str(path),
            "status": "unreadable",
            "n_rows": 0,
            "n_columns": 0,
            "sample_id_column": "",
            "sample_overlap_fraction": 0.0,
            "selection_score": -9999.0,
            "columns": "",
            "error": "",
        }
        try:
            annotation = load_annotation(path)
            sample_column, overlap = best_sample_column(
                annotation,
                expression_samples,
            )
            priority = 0
            lower = path.name.lower()
            if "sample_annotation" in lower:
                priority += 500
            if "repaired" in lower:
                priority += 150
            if "design" in lower:
                priority += 300
            if "series_matrix" in lower:
                priority += 100

            row.update(
                {
                    "status": "ok",
                    "n_rows": int(annotation.shape[0]),
                    "n_columns": int(annotation.shape[1]),
                    "sample_id_column": sample_column,
                    "sample_overlap_fraction": round(overlap, 6),
                    "selection_score": priority + 1000 * overlap,
                    "columns": ";".join(map(str, annotation.columns)),
                }
            )
        except Exception as exc:
            row["error"] = repr(exc)
        audit_rows.append(row)

    audit = pd.DataFrame(audit_rows)
    readable = audit[audit["status"] == "ok"].copy()

    if readable.empty:
        raise RuntimeError(f"No readable annotation candidate found for {accession}")

    selected = readable.sort_values(
        ["selection_score", "sample_overlap_fraction"],
        ascending=False,
    ).iloc[0]

    selected_path = Path(str(selected["path"]))
    annotation = load_annotation(selected_path)
    sample_column = str(selected["sample_id_column"])
    overlap = float(selected["sample_overlap_fraction"])

    return selected_path, annotation, sample_column, overlap, audit


def canonicalize_design(
    annotation: pd.DataFrame,
    sample_column: str,
    expression_samples: Sequence[str],
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    annotation = annotation.copy()
    annotation["_sample_token"] = annotation[sample_column].map(normalize_token)
    annotation = annotation.drop_duplicates("_sample_token", keep="first")
    lookup = annotation.set_index("_sample_token")

    rows = []
    for sample in expression_samples:
        token = normalize_token(sample)
        matched = token in lookup.index
        source = lookup.loc[token] if matched else pd.Series(dtype=object)

        row = {
            "sample_id": str(sample),
            "annotation_row_matched": matched,
        }
        for column in annotation.columns:
            if column == "_sample_token":
                continue
            row[str(column)] = source.get(column, "")
        rows.append(row)

    design = pd.DataFrame(rows)
    qc = {
        "n_expression_samples": len(expression_samples),
        "n_annotation_rows": int(annotation.shape[0]),
        "sample_id_column": sample_column,
        "annotation_match_fraction": round(
            float(design["annotation_row_matched"].astype(bool).mean()),
            6,
        ),
        "annotation_columns": ";".join(map(str, annotation.columns)),
    }
    return design, qc


def summarize_design_values(design: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in design.columns:
        if any(
            token in str(column).lower()
            for token in [
                "group",
                "condition",
                "treatment",
                "outcome",
                "title",
                "source",
                "characteristic",
                "status",
                "exposure",
            ]
        ):
            counts = (
                design[column]
                .fillna("")
                .astype(str)
                .str.strip()
                .value_counts()
            )
            for value, count in counts.head(30).items():
                if value:
                    rows.append(
                        {
                            "column": str(column),
                            "value": value,
                            "n_samples": int(count),
                        }
                    )
    return pd.DataFrame(rows)


def infer_sc_condition(path: Path) -> str:
    text = str(path).lower()
    if "upec" in text or "uti89" in text:
        return "UPEC"
    if any(token in text for token in ["control", "ctrl", "mock", "pbs"]):
        return "control"
    return ""


def infer_sc_sample_id(path: Path) -> str:
    name = path.name
    stem = re.sub(r"\.(tsv|csv|txt)(\.gz)?$", "", name, flags=re.I)
    stem = re.sub(r"_matrix$", "", stem, flags=re.I)
    return stem


def sc_matrix_candidates(project: Path) -> List[Path]:
    root = project / "02_data_raw" / "GSE252321"
    if not root.exists():
        return []

    candidates = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if "series_matrix" in lower:
            continue
        if any(
            lower.endswith(suffix)
            for suffix in [
                ".tsv",
                ".tsv.gz",
                ".csv",
                ".csv.gz",
                ".txt",
                ".txt.gz",
            ]
        ):
            if any(
                token in lower
                for token in ["matrix", "count", "expression"]
            ):
                candidates.append(path)
    return candidates


def audit_sc_matrix(path: Path) -> Dict[str, object]:
    row = {
        "path": str(path),
        "status": "unreadable",
        "sample_id": infer_sc_sample_id(path),
        "condition": infer_sc_condition(path),
        "gene_column": "",
        "symbol_like_fraction": 0.0,
        "n_numeric_cell_columns": 0,
        "scale_class": "",
        "selection_score": -9999.0,
        "error": "",
    }

    try:
        preview = read_table(path, nrows=80, dtype=str)
        best_column = None
        best_fraction = -1.0
        for column in list(preview.columns[:6]):
            fraction = float(preview[column].astype(str).map(valid_symbol).mean())
            if fraction > best_fraction:
                best_column = str(column)
                best_fraction = fraction

        numeric_columns = []
        numeric_values = []

        for column in preview.columns:
            if str(column) == str(best_column):
                continue
            numeric = pd.to_numeric(preview[column], errors="coerce")
            if numeric.notna().mean() >= 0.85:
                numeric_columns.append(str(column))
                numeric_values.extend(
                    numeric.dropna().astype(float).head(20).tolist()
                )

        values = np.asarray(numeric_values, dtype=float)
        non_integer_fraction = (
            float(np.mean(np.abs(values - np.round(values)) > 1e-8))
            if len(values)
            else 1.0
        )

        row.update(
            {
                "status": "ok",
                "gene_column": best_column or "",
                "symbol_like_fraction": round(max(best_fraction, 0.0), 6),
                "n_numeric_cell_columns": len(numeric_columns),
                "scale_class": (
                    "integer_like_counts"
                    if non_integer_fraction <= 0.05
                    else "continuous_expression"
                ),
                "selection_score": (
                    500 * (best_fraction >= 0.50)
                    + min(len(numeric_columns), 1000)
                    + 100 * bool(row["condition"])
                ),
            }
        )
    except Exception as exc:
        row["error"] = repr(exc)

    return row


def stream_sample_pseudobulk(
    path: Path,
    gene_column: str,
    scale_class: str,
) -> pd.Series:
    separator = sniff_separator(path)
    pieces = []

    for chunk in pd.read_csv(
        path,
        sep=separator,
        compression="infer",
        chunksize=500,
        low_memory=False,
    ):
        if gene_column not in chunk.columns:
            raise RuntimeError(
                f"Gene column {gene_column!r} not found in {path}"
            )

        symbols = chunk[gene_column].map(normalize_symbol)
        keep = symbols.map(valid_symbol)

        numeric_columns = []
        for column in chunk.columns:
            if str(column) == gene_column:
                continue
            numeric = pd.to_numeric(chunk[column], errors="coerce")
            if numeric.notna().mean() >= 0.85:
                chunk[column] = numeric
                numeric_columns.append(str(column))

        if not numeric_columns:
            continue

        values = chunk.loc[keep, numeric_columns]
        genes = symbols.loc[keep]

        if scale_class == "integer_like_counts":
            aggregate = values.sum(axis=1, skipna=True)
        else:
            aggregate = values.mean(axis=1, skipna=True)

        pieces.append(
            pd.DataFrame(
                {
                    "gene_symbol": genes.values,
                    "value": aggregate.values,
                }
            )
        )

    if not pieces:
        raise RuntimeError(f"No pseudobulk values could be computed from {path}")

    combined = pd.concat(pieces, ignore_index=True)
    sample = combined.groupby("gene_symbol")["value"].mean()

    if scale_class == "integer_like_counts":
        total = float(sample.sum())
        if total > 0:
            sample = np.log2(sample / total * 1_000_000 + 1.0)

    return sample


def prepare_sc_sample_pseudobulk(
    project: Path,
    output_processed: Path,
    output_metadata: Path,
    output_tables: Path,
) -> Tuple[bool, str, int]:
    candidates = sc_matrix_candidates(project)
    audit = pd.DataFrame([audit_sc_matrix(path) for path in candidates])

    if audit.empty:
        audit = pd.DataFrame(
            columns=[
                "path",
                "status",
                "sample_id",
                "condition",
                "gene_column",
                "symbol_like_fraction",
                "n_numeric_cell_columns",
                "scale_class",
                "selection_score",
                "error",
            ]
        )

    audit.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A1_GSE252321_flat_matrix_audit.tsv",
        sep="\t",
        index=False,
    )

    eligible = audit[
        (audit["status"] == "ok")
        & (audit["symbol_like_fraction"] >= 0.50)
        & (audit["n_numeric_cell_columns"] >= 50)
        & audit["condition"].astype(str).ne("")
    ].copy()

    if len(eligible) < 4 or eligible["condition"].nunique() < 2:
        return (
            False,
            "Fewer than four usable sample matrices or fewer than two conditions.",
            len(eligible),
        )

    series_list = []
    metadata_rows = []

    for _, row in eligible.sort_values("path").iterrows():
        path = Path(str(row["path"]))
        log(f"Building sample-level pseudobulk: {path.name}")
        sample = stream_sample_pseudobulk(
            path,
            str(row["gene_column"]),
            str(row["scale_class"]),
        )
        sample_id = str(row["sample_id"])
        sample.name = sample_id
        series_list.append(sample)
        metadata_rows.append(
            {
                "sample_id": sample_id,
                "condition": str(row["condition"]),
                "source_matrix": str(path),
                "source_scale_class": str(row["scale_class"]),
                "n_cell_columns": int(row["n_numeric_cell_columns"]),
                "analysis_unit": "biological_sample_whole_object_pseudobulk",
            }
        )

    pseudobulk = pd.concat(series_list, axis=1, join="outer")
    pseudobulk.index.name = "gene_symbol"
    pseudobulk = pseudobulk.reset_index().sort_values("gene_symbol")

    matrix_path = (
        output_processed
        / "GSE252321_U26B2A1_sample_level_pseudobulk_expression.tsv.gz"
    )
    pseudobulk.to_csv(
        matrix_path,
        sep="\t",
        index=False,
        compression="gzip",
    )

    metadata = pd.DataFrame(metadata_rows)
    metadata_path = (
        output_metadata
        / "GSE252321_U26B2A1_sample_level_pseudobulk_design.tsv"
    )
    metadata.to_csv(metadata_path, sep="\t", index=False)

    ready = (
        len(metadata) >= 4
        and metadata["condition"].nunique() >= 2
        and metadata.groupby("condition").size().min() >= 2
    )

    note = (
        "Sample-level whole-object pseudobulk is ready. "
        "Cell-type pseudobulk remains deferred until cell annotations "
        "or a reconstructed annotated object are available."
    )

    return ready, note, len(metadata)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    output_metadata = project / "03_metadata" / PHASE_TAG
    output_processed = project / "03_data_processed" / PHASE_TAG
    output_results = project / "05_results" / PHASE_TAG
    output_tables = project / "06_tables" / PHASE_TAG

    for directory in [
        output_metadata,
        output_processed,
        output_results,
        output_tables,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    datasets = {
        "GSE186800": {
            "matrix": (
                project
                / "03_data_processed"
                / "phaseU4b_repaired_matrices"
                / "GSE186800_repaired_gene_symbol_matrix.tsv.gz"
            ),
            "expected_samples": 20,
            "species": "Mus musculus",
            "role": "recurrent_or_prior_exposure_bladder_model",
        },
        "GSE112098": {
            "matrix": (
                project
                / "03_data_processed"
                / "phaseU6_human_urine_comparator"
                / "GSE112098_series_matrix_repaired_gene_symbol_matrix.tsv.gz"
            ),
            "expected_samples": 73,
            "species": "Homo sapiens",
            "role": "human_urinary_systemic_inflammation_comparator",
        },
    }

    readiness_rows = []
    selected_rows = []

    for accession, config in datasets.items():
        matrix_path = config["matrix"]
        log(f"Repairing {accession} input preparation.")

        if not matrix_path.exists():
            readiness_rows.append(
                {
                    "dataset": accession,
                    "ready_for_scoring": False,
                    "critical_note": f"Missing selected matrix: {matrix_path}",
                }
            )
            continue

        try:
            matrix, matrix_qc = canonicalize_matrix(
                matrix_path,
                int(config["expected_samples"]),
            )

            canonical_path = (
                output_processed
                / f"{accession}_U26B2A1_canonical_gene_symbol_expression.tsv.gz"
            )
            matrix.to_csv(
                canonical_path,
                sep="\t",
                index=False,
                compression="gzip",
            )

            pd.DataFrame([matrix_qc]).to_csv(
                output_tables
                / f"UTI_HostOmics_U26B2A1_{accession}_matrix_qc.tsv",
                sep="\t",
                index=False,
            )

            expression_samples = [
                column
                for column in matrix.columns
                if column != "gene_symbol"
            ]

            (
                annotation_path,
                annotation,
                sample_column,
                overlap,
                annotation_audit,
            ) = select_annotation(
                project,
                accession,
                expression_samples,
            )

            annotation_audit.to_csv(
                output_tables
                / f"UTI_HostOmics_U26B2A1_{accession}_annotation_candidate_audit.tsv",
                sep="\t",
                index=False,
            )

            design, design_qc = canonicalize_design(
                annotation,
                sample_column,
                expression_samples,
            )
            design_qc.update(
                {
                    "selected_annotation": str(annotation_path),
                    "direct_overlap_fraction": overlap,
                }
            )

            design_path = (
                output_metadata
                / f"{accession}_U26B2A1_validated_sample_design.tsv"
            )
            design.to_csv(design_path, sep="\t", index=False)

            pd.DataFrame([design_qc]).to_csv(
                output_tables
                / f"UTI_HostOmics_U26B2A1_{accession}_annotation_qc.tsv",
                sep="\t",
                index=False,
            )

            summarize_design_values(design).to_csv(
                output_tables
                / f"UTI_HostOmics_U26B2A1_{accession}_design_value_summary.tsv",
                sep="\t",
                index=False,
            )

            ready = bool(
                matrix_qc["gene_universe_plausible"]
                and matrix_qc["sample_count_plausible"]
                and design_qc["annotation_match_fraction"] >= 0.90
            )

            readiness_rows.append(
                {
                    "dataset": accession,
                    "species": config["species"],
                    "biological_role": config["role"],
                    "observed_samples": matrix_qc["n_expression_samples"],
                    "canonical_genes": matrix_qc["n_canonical_gene_symbols"],
                    "annotation_match_fraction": design_qc[
                        "annotation_match_fraction"
                    ],
                    "expression_scale_class": matrix_qc[
                        "expression_scale_class"
                    ],
                    "ready_for_scoring": ready,
                    "critical_note": (
                        "Use sample-level dataset-specific scoring; "
                        "do not pool raw expression across species."
                    ),
                }
            )

            selected_rows.append(
                {
                    "dataset": accession,
                    "selected_matrix": str(matrix_path),
                    "canonical_matrix": str(canonical_path),
                    "selected_annotation": str(annotation_path),
                    "validated_design": str(design_path),
                }
            )

        except Exception as exc:
            readiness_rows.append(
                {
                    "dataset": accession,
                    "species": config["species"],
                    "biological_role": config["role"],
                    "observed_samples": "",
                    "canonical_genes": "",
                    "annotation_match_fraction": "",
                    "expression_scale_class": "",
                    "ready_for_scoring": False,
                    "critical_note": repr(exc),
                }
            )

    readiness = pd.DataFrame(readiness_rows)
    readiness.to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A1_bulk_dataset_readiness.tsv",
        sep="\t",
        index=False,
    )
    pd.DataFrame(selected_rows).to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A1_selected_bulk_sources.tsv",
        sep="\t",
        index=False,
    )

    inventory_root = project / "02_data_raw" / "GSE252321"
    inventory_rows = []
    if inventory_root.exists():
        for path in inventory_root.rglob("*"):
            if path.is_file():
                inventory_rows.append(
                    {
                        "path": str(path),
                        "relative_path": str(path.relative_to(inventory_root)),
                        "suffix": path.suffix,
                        "size_bytes": path.stat().st_size,
                    }
                )

    pd.DataFrame(inventory_rows).to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A1_GSE252321_complete_inventory.tsv",
        sep="\t",
        index=False,
    )

    sc_ready, sc_note, n_sc_samples = prepare_sc_sample_pseudobulk(
        project,
        output_processed,
        output_metadata,
        output_tables,
    )

    bulk_ready_count = int(
        readiness["ready_for_scoring"]
        .astype(str)
        .str.lower()
        .isin(["true", "1"])
        .sum()
    )

    if bulk_ready_count == 2 and sc_ready:
        decision = (
            "READY_FOR_U26B2B_BULK_AND_SAMPLE_PSEUDOBULK_SCORING_"
            "CELLTYPE_RECONSTRUCTION_DEFERRED"
        )
    elif bulk_ready_count == 2:
        decision = (
            "READY_FOR_U26B2B_BULK_SCORING_"
            "SINGLE_CELL_TARGETED_RECONSTRUCTION"
        )
    elif bulk_ready_count >= 1:
        decision = "PARTIAL_BULK_READINESS_TARGETED_REVIEW"
    else:
        decision = "TARGETED_INPUT_REVIEW_REQUIRED"

    pd.DataFrame(
        [
            {
                "phase": "U26B2A.1",
                "decision": decision,
                "n_bulk_datasets_ready": bulk_ready_count,
                "GSE252321_sample_pseudobulk_ready": sc_ready,
                "GSE252321_pseudobulk_samples": n_sc_samples,
                "GSE252321_cell_type_pseudobulk": "deferred",
                "cross_species_rule": (
                    "Integrate standardized module effects and direction "
                    "concordance; never pool raw expression."
                ),
                "human_comparator_rule": (
                    "GSE112098 is a urinary systemic-inflammation comparator, "
                    "not direct UTI evidence."
                ),
                "single_cell_rule": (
                    "Use biological sample pseudobulk as the inferential unit. "
                    "Cell-level distributions are descriptive only."
                ),
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": "U26B2B dataset-specific scoring",
            }
        ]
    ).to_csv(
        output_tables
        / "UTI_HostOmics_U26B2A1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_lines = [
        "# Phase U26B2A.1 - Cross-dataset input repair",
        "",
        f"- Version: `{VERSION}`",
        f"- Decision: **{decision}**",
        "- Manuscript and existing Figures 1-6 were not modified.",
        "",
        "## Bulk readiness",
        "",
    ]

    for _, row in readiness.iterrows():
        report_lines.extend(
            [
                f"### {row['dataset']}",
                "",
                f"- Ready: **{row['ready_for_scoring']}**",
                f"- Samples: **{row.get('observed_samples', '')}**",
                f"- Canonical genes: **{row.get('canonical_genes', '')}**",
                (
                    "- Annotation match fraction: "
                    f"**{row.get('annotation_match_fraction', '')}**"
                ),
                (
                    "- Expression scale: "
                    f"**{row.get('expression_scale_class', '')}**"
                ),
                f"- Note: {row['critical_note']}",
                "",
            ]
        )

    report_lines.extend(
        [
            "## GSE252321",
            "",
            f"- Sample-level pseudobulk ready: **{sc_ready}**",
            f"- Pseudobulk biological samples: **{n_sc_samples}**",
            f"- Cell-type pseudobulk: **deferred**",
            f"- Note: {sc_note}",
            "",
            "## Statistical use",
            "",
            (
                "- GSE186800: four-group factorial or planned-contrast "
                "sample-level module analysis."
            ),
            (
                "- GSE112098: sepsis versus vascular-surgery urinary "
                "comparator; interpretation is systemic urinary inflammation."
            ),
            (
                "- GSE252321: whole-object biological-sample pseudobulk is "
                "exploratory when available; cell-type validation awaits "
                "annotated-object reconstruction."
            ),
            (
                "- Cross-dataset integration will use standardized effects, "
                "directional recurrence and native-species module identities."
            ),
        ]
    )

    report_path = (
        output_results
        / "UTI_HostOmics_U26B2A1_cross_dataset_input_repair_report.md"
    )
    report_path.write_text("\n".join(report_lines) + "\n")

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "decision": decision,
        "bulk_ready_count": bulk_ready_count,
        "GSE252321_sample_pseudobulk_ready": sc_ready,
        "GSE252321_pseudobulk_samples": n_sc_samples,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        output_results
        / "UTI_HostOmics_U26B2A1_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2))

    log(f"Bulk datasets ready: {bulk_ready_count}/2")
    log(f"GSE252321 sample pseudobulk ready: {sc_ready}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26B2A.1] ERROR: {exc}", file=sys.stderr)
        raise
