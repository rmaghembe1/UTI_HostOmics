#!/usr/bin/env python3
"""
Phase U26D1A
Validate and convert the four GSE252321 flat gene-by-cell matrices.

Why this phase exists
---------------------
GSE252321 is locally represented as four compressed dense TSV matrices rather
than 10x MatrixMarket triplets. The absence of 10x triplets is therefore not a
missing-data failure.

This phase:
1. Explicitly validates the four Control/UPEC flat matrices.
2. Detects gene-by-cell orientation and the gene-symbol column.
3. Audits numerical scale, non-negativity, integer-likeness, sparsity,
   duplicate genes and per-cell QC.
4. Converts each sample into a memory-efficient cells-by-genes sparse matrix.
5. Writes prefixed cell identifiers and a balanced 2-control/2-UPEC manifest.
6. Determines readiness for marker-based cell-type reconstruction.

No manuscript or existing figures are modified.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
import tarfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    from scipy import sparse
except ImportError as exc:
    raise SystemExit(
        "ERROR: scipy is required for sparse conversion."
    ) from exc


VERSION = "U26D1A_v1.0_2026-07-14"
TAG = "phaseU26D1A_GSE252321_flat_matrix_validation"

EXPECTED_SAMPLES = [
    {
        "sample_id": "GSM7999426_Control_1",
        "condition": "control",
        "replicate": 1,
        "filename": "GSM7999426_Control_1_matrix.tsv.gz",
    },
    {
        "sample_id": "GSM7999427_Control_2",
        "condition": "control",
        "replicate": 2,
        "filename": "GSM7999427_Control_2_matrix.tsv.gz",
    },
    {
        "sample_id": "GSM7999428_UPEC_1",
        "condition": "UPEC",
        "replicate": 1,
        "filename": "GSM7999428_UPEC_1_matrix.tsv.gz",
    },
    {
        "sample_id": "GSM7999429_UPEC_2",
        "condition": "UPEC",
        "replicate": 2,
        "filename": "GSM7999429_UPEC_2_matrix.tsv.gz",
    },
]

GENE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def log(message: str) -> None:
    print(f"[U26D1A] {message}", flush=True)


def open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def sniff_separator(path: Path) -> str:
    with open_text(path) as handle:
        line = handle.readline()
    return "\t" if line.count("\t") >= line.count(",") else ","


def normalize_gene(value: object) -> str:
    return str(value).strip().strip('"').strip("'")


def plausible_gene(value: object) -> bool:
    text = normalize_gene(value)
    return (
        bool(GENE_RE.fullmatch(text))
        and text.lower() not in {"", "nan", "na", "none", "null"}
        and not text.isdigit()
    )


def read_header(path: Path, separator: str) -> List[str]:
    with open_text(path) as handle:
        line = handle.readline().rstrip("\n\r")
    return [field.strip().strip('"') for field in line.split(separator)]


def inspect_preview(
    path: Path,
    separator: str,
    nrows: int = 100,
) -> Dict[str, object]:
    preview = pd.read_csv(
        path,
        sep=separator,
        compression="infer",
        nrows=nrows,
        low_memory=False,
    )

    if preview.shape[1] < 3:
        raise RuntimeError(
            f"{path} has fewer than three columns; not a gene-by-cell matrix."
        )

    candidate_columns = list(preview.columns[:5])
    best_gene_column = ""
    best_gene_fraction = -1.0

    for column in candidate_columns:
        fraction = float(
            preview[column]
            .astype(str)
            .map(plausible_gene)
            .mean()
        )
        if fraction > best_gene_fraction:
            best_gene_fraction = fraction
            best_gene_column = str(column)

    numeric_columns: List[str] = []
    numeric_fractions: List[float] = []

    for column in preview.columns:
        if str(column) == best_gene_column:
            continue
        converted = pd.to_numeric(
            preview[column],
            errors="coerce",
        )
        fraction = float(converted.notna().mean())
        if fraction >= 0.95:
            numeric_columns.append(str(column))
            numeric_fractions.append(fraction)

    orientation = (
        "genes_by_cells"
        if best_gene_fraction >= 0.80
        and len(numeric_columns) >= 50
        else "unresolved"
    )

    return {
        "gene_column": best_gene_column,
        "gene_symbol_fraction_preview": best_gene_fraction,
        "numeric_cell_columns_preview": len(numeric_columns),
        "numeric_fraction_median_preview": (
            float(np.median(numeric_fractions))
            if numeric_fractions
            else 0.0
        ),
        "orientation": orientation,
        "preview_columns": list(map(str, preview.columns[:20])),
    }


def adaptive_bounds(values: np.ndarray) -> Tuple[float, float]:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return np.nan, np.nan
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    if mad == 0:
        return float(np.min(finite)), float(np.max(finite))
    lower = max(float(np.min(finite)), median - 3.0 * 1.4826 * mad)
    upper = min(float(np.max(finite)), median + 3.0 * 1.4826 * mad)
    return lower, upper


def convert_one_matrix(
    path: Path,
    sample_id: str,
    condition: str,
    replicate: int,
    output_root: Path,
    chunk_rows: int,
) -> Tuple[Dict[str, object], pd.DataFrame]:
    separator = sniff_separator(path)
    preview = inspect_preview(path, separator)

    if preview["orientation"] != "genes_by_cells":
        raise RuntimeError(
            f"Could not validate gene-by-cell orientation for {path}"
        )

    gene_column = str(preview["gene_column"])
    header = read_header(path, separator)
    if gene_column not in header:
        raise RuntimeError(
            f"Gene column {gene_column!r} is absent from the raw header."
        )

    gene_index = header.index(gene_column)
    raw_cell_columns = [
        column
        for index, column in enumerate(header)
        if index != gene_index
    ]
    if len(raw_cell_columns) < 50:
        raise RuntimeError(
            f"Only {len(raw_cell_columns)} cell columns found in {path}"
        )

    prefixed_cells = [
        f"{sample_id}::{barcode}"
        for barcode in raw_cell_columns
    ]

    total_counts = np.zeros(len(raw_cell_columns), dtype=np.float64)
    detected_genes = np.zeros(len(raw_cell_columns), dtype=np.int64)
    mitochondrial_counts = np.zeros(
        len(raw_cell_columns),
        dtype=np.float64,
    )

    gene_symbols: List[str] = []
    matrix_chunks: List[sparse.csr_matrix] = []

    invalid_gene_rows = 0
    nonfinite_values = 0
    negative_values = 0
    nonzero_values = 0
    inspected_values = 0
    noninteger_values = 0

    reader = pd.read_csv(
        path,
        sep=separator,
        compression="infer",
        chunksize=chunk_rows,
        low_memory=False,
    )

    for chunk_number, chunk in enumerate(reader, start=1):
        if gene_column not in chunk.columns:
            raise RuntimeError(
                f"Gene column {gene_column!r} disappeared in chunk "
                f"{chunk_number} of {path}"
            )

        genes = chunk[gene_column].map(normalize_gene)
        valid = genes.map(plausible_gene)

        invalid_gene_rows += int((~valid).sum())
        chunk = chunk.loc[valid].copy()
        genes = genes.loc[valid]

        value_columns = [
            column
            for column in chunk.columns
            if str(column) != gene_column
        ]

        if list(map(str, value_columns)) != raw_cell_columns:
            raise RuntimeError(
                f"Cell-column order changed while reading {path}"
            )

        numeric_frame = chunk[value_columns].apply(
            pd.to_numeric,
            errors="coerce",
        )
        values = numeric_frame.to_numpy(dtype=np.float32)

        finite_mask = np.isfinite(values)
        nonfinite_values += int((~finite_mask).sum())
        values[~finite_mask] = 0.0

        negative_values += int((values < 0).sum())

        sample_values = values.ravel()
        if len(sample_values) > 250_000:
            step = max(1, len(sample_values) // 250_000)
            sample_values = sample_values[::step]

        inspected_values += int(len(sample_values))
        noninteger_values += int(
            (
                np.abs(
                    sample_values - np.round(sample_values)
                )
                > 1e-6
            ).sum()
        )

        nonzero_values += int(np.count_nonzero(values))
        total_counts += values.sum(axis=0, dtype=np.float64)
        detected_genes += np.count_nonzero(values > 0, axis=0)

        mitochondrial_mask = (
            genes.astype(str)
            .str.upper()
            .str.startswith("MT-")
            .to_numpy()
        )
        if mitochondrial_mask.any():
            mitochondrial_counts += values[
                mitochondrial_mask,
                :
            ].sum(axis=0, dtype=np.float64)

        gene_symbols.extend(genes.astype(str).tolist())
        matrix_chunks.append(
            sparse.csr_matrix(values)
        )

        if chunk_number % 20 == 0:
            log(
                f"{sample_id}: processed "
                f"{len(gene_symbols):,} gene rows."
            )

    if not matrix_chunks:
        raise RuntimeError(f"No matrix chunks were read from {path}")

    genes_by_cells = sparse.vstack(
        matrix_chunks,
        format="csr",
    )
    cells_by_genes = genes_by_cells.transpose().tocsr()

    n_genes, n_cells = genes_by_cells.shape
    if n_cells != len(raw_cell_columns):
        raise RuntimeError(
            f"Cell count mismatch for {sample_id}: "
            f"matrix={n_cells}, header={len(raw_cell_columns)}"
        )

    duplicate_gene_rows = int(
        pd.Series(gene_symbols).duplicated().sum()
    )

    output_dir = output_root / sample_id
    output_dir.mkdir(parents=True, exist_ok=True)

    sparse_path = (
        output_dir
        / f"{sample_id}_cells_by_genes_expression.npz"
    )
    sparse.save_npz(
        sparse_path,
        cells_by_genes,
        compressed=True,
    )

    genes_path = output_dir / f"{sample_id}_genes.tsv"
    pd.DataFrame(
        {
            "gene_index": np.arange(n_genes),
            "gene_symbol": gene_symbols,
        }
    ).to_csv(
        genes_path,
        sep="\t",
        index=False,
    )

    cells_path = output_dir / f"{sample_id}_cells.tsv.gz"

    pct_mito = np.divide(
        mitochondrial_counts,
        total_counts,
        out=np.zeros_like(mitochondrial_counts),
        where=total_counts > 0,
    ) * 100.0

    lower_counts, upper_counts = adaptive_bounds(total_counts)
    lower_genes, upper_genes = adaptive_bounds(
        detected_genes.astype(float)
    )
    _, upper_mito = adaptive_bounds(pct_mito)

    qc_pass = (
        (total_counts > 0)
        & (detected_genes >= max(100, lower_genes))
        & (
            detected_genes <= upper_genes
            if np.isfinite(upper_genes)
            else True
        )
        & (
            pct_mito <= max(20.0, upper_mito)
            if np.isfinite(upper_mito)
            else True
        )
    )

    cell_metadata = pd.DataFrame(
        {
            "cell_id": prefixed_cells,
            "raw_barcode": raw_cell_columns,
            "sample_id": sample_id,
            "condition": condition,
            "replicate": replicate,
            "total_expression": total_counts,
            "detected_genes": detected_genes,
            "mitochondrial_expression": mitochondrial_counts,
            "pct_mitochondrial": pct_mito,
            "adaptive_qc_pass": qc_pass,
        }
    )
    cell_metadata.to_csv(
        cells_path,
        sep="\t",
        index=False,
        compression="gzip",
    )

    total_matrix_values = int(n_genes * n_cells)
    sparsity_fraction = (
        1.0 - nonzero_values / total_matrix_values
        if total_matrix_values > 0
        else np.nan
    )
    noninteger_fraction = (
        noninteger_values / inspected_values
        if inspected_values > 0
        else np.nan
    )

    scale_class = (
        "integer_like_counts"
        if noninteger_fraction <= 0.05
        and negative_values == 0
        else "continuous_nonnegative_expression"
        if negative_values == 0
        else "continuous_expression_with_negative_values"
    )

    qc = {
        "sample_id": sample_id,
        "condition": condition,
        "replicate": replicate,
        "source_path": str(path),
        "orientation": "genes_by_cells",
        "gene_column": gene_column,
        "n_genes": n_genes,
        "n_cells": n_cells,
        "n_nonzero_values": nonzero_values,
        "sparsity_fraction": sparsity_fraction,
        "invalid_gene_rows": invalid_gene_rows,
        "duplicate_gene_rows": duplicate_gene_rows,
        "nonfinite_values_replaced_with_zero": nonfinite_values,
        "negative_values": negative_values,
        "noninteger_fraction_sampled": noninteger_fraction,
        "scale_class": scale_class,
        "median_total_expression": float(
            np.median(total_counts)
        ),
        "median_detected_genes": float(
            np.median(detected_genes)
        ),
        "median_pct_mitochondrial": float(
            np.median(pct_mito)
        ),
        "adaptive_qc_pass_cells": int(qc_pass.sum()),
        "adaptive_qc_pass_fraction": float(qc_pass.mean()),
        "suggested_total_expression_lower": lower_counts,
        "suggested_total_expression_upper": upper_counts,
        "suggested_detected_genes_lower": lower_genes,
        "suggested_detected_genes_upper": upper_genes,
        "suggested_pct_mito_upper": max(
            20.0,
            upper_mito,
        )
        if np.isfinite(upper_mito)
        else 20.0,
        "sparse_matrix_path": str(sparse_path),
        "genes_path": str(genes_path),
        "cell_metadata_path": str(cells_path),
    }

    return qc, cell_metadata


def inspect_raw_archive(path: Path) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    if not path.exists():
        return pd.DataFrame(rows)

    try:
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                if member.isfile():
                    rows.append(
                        {
                            "member_name": member.name,
                            "size_bytes": member.size,
                            "looks_like_10x_component": bool(
                                re.search(
                                    r"(?i)(matrix\.mtx|barcodes\.tsv|"
                                    r"features\.tsv|genes\.tsv)",
                                    member.name,
                                )
                            ),
                            "looks_like_flat_matrix": bool(
                                re.search(
                                    r"(?i)(matrix.*\.(tsv|txt|csv)(\.gz)?)$",
                                    member.name,
                                )
                            ),
                        }
                    )
    except Exception as exc:
        rows.append(
            {
                "member_name": "",
                "size_bytes": "",
                "looks_like_10x_component": False,
                "looks_like_flat_matrix": False,
                "error": str(exc),
            }
        )
    return pd.DataFrame(rows)


def write_report(
    path: Path,
    qc: pd.DataFrame,
    archive: pd.DataFrame,
    decision: str,
) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26D1A - GSE252321 flat-matrix validation\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            "- Manuscript and existing figures were not modified.\n\n"
        )

        handle.write("## Key diagnosis\n\n")
        handle.write(
            "The dataset is represented as four dense gene-by-cell TSV "
            "matrices, not as 10x MatrixMarket triplets. The zero-triplet "
            "result from U26D1 was therefore a format-detection limitation, "
            "not a missing-input failure.\n\n"
        )

        handle.write("## Matrix validation\n\n")
        for _, row in qc.iterrows():
            handle.write(
                f"- `{row['sample_id']}` ({row['condition']}): "
                f"{int(row['n_cells']):,} cells, "
                f"{int(row['n_genes']):,} gene rows, "
                f"sparsity={float(row['sparsity_fraction']):.3f}, "
                f"scale={row['scale_class']}, "
                f"adaptive QC pass="
                f"{int(row['adaptive_qc_pass_cells']):,}/"
                f"{int(row['n_cells']):,} "
                f"({float(row['adaptive_qc_pass_fraction']):.1%}).\n"
            )
        handle.write("\n")

        handle.write("## Raw archive\n\n")
        if archive.empty:
            handle.write(
                "- The raw archive was unavailable or contained no members.\n\n"
            )
        else:
            n_10x = int(
                archive.get(
                    "looks_like_10x_component",
                    pd.Series(dtype=bool),
                )
                .fillna(False)
                .astype(bool)
                .sum()
            )
            n_flat = int(
                archive.get(
                    "looks_like_flat_matrix",
                    pd.Series(dtype=bool),
                )
                .fillna(False)
                .astype(bool)
                .sum()
            )
            handle.write(
                f"- Archive members: **{len(archive)}**.\n"
            )
            handle.write(
                f"- 10x component-like members: **{n_10x}**.\n"
            )
            handle.write(
                f"- Flat-matrix-like members: **{n_flat}**.\n\n"
            )

        handle.write("## Next analysis\n\n")
        if decision == (
            "READY_FOR_U26D2_FLAT_MATRIX_MARKER_BASED_RECONSTRUCTION"
        ):
            handle.write(
                "Proceed to U26D2 using the converted sparse matrices. "
                "Perform cell QC, within-sample normalization, highly variable "
                "gene selection, balanced integration, unsupervised clustering, "
                "marker-based annotation and sample-by-cell-type pseudobulk. "
                "Biological samples, not cells, remain the inferential units.\n"
            )
        else:
            handle.write(
                "Do not begin annotation until the failed matrix validations "
                "listed in the QC table are repaired.\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    parser.add_argument(
        "--chunk-rows",
        type=int,
        default=256,
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    matrix_root = (
        project
        / "02_data_raw"
        / "GSE252321"
        / "single_cell_matrices"
    )
    archive_path = (
        project
        / "02_data_raw"
        / "GSE252321"
        / "raw_archive"
        / "GSE252321_RAW.tar"
    )

    out_processed = project / "03_data_processed" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_tables = project / "06_tables" / TAG
    out_results = project / "05_results" / TAG

    for directory in [
        out_processed,
        out_metadata,
        out_tables,
        out_results,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    qc_rows: List[Dict[str, object]] = []
    combined_cell_metadata: List[pd.DataFrame] = []
    manifest_rows: List[Dict[str, object]] = []

    for sample in EXPECTED_SAMPLES:
        path = matrix_root / sample["filename"]
        if not path.exists():
            qc_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "condition": sample["condition"],
                    "replicate": sample["replicate"],
                    "source_path": str(path),
                    "orientation": "missing",
                    "n_genes": 0,
                    "n_cells": 0,
                    "scale_class": "missing",
                    "adaptive_qc_pass_fraction": 0.0,
                    "validation_error": "source_file_missing",
                }
            )
            continue

        log(f"Validating and converting {sample['sample_id']}.")
        try:
            qc, cell_metadata = convert_one_matrix(
                path=path,
                sample_id=sample["sample_id"],
                condition=sample["condition"],
                replicate=int(sample["replicate"]),
                output_root=out_processed,
                chunk_rows=int(args.chunk_rows),
            )
            qc["validation_error"] = ""
            qc_rows.append(qc)
            combined_cell_metadata.append(cell_metadata)

            manifest_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "condition": sample["condition"],
                    "replicate": sample["replicate"],
                    "source_path": str(path),
                    "sparse_matrix_path": qc["sparse_matrix_path"],
                    "genes_path": qc["genes_path"],
                    "cell_metadata_path": qc["cell_metadata_path"],
                    "n_cells": qc["n_cells"],
                    "n_genes": qc["n_genes"],
                    "scale_class": qc["scale_class"],
                }
            )
        except Exception as exc:
            qc_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "condition": sample["condition"],
                    "replicate": sample["replicate"],
                    "source_path": str(path),
                    "orientation": "failed",
                    "n_genes": 0,
                    "n_cells": 0,
                    "scale_class": "failed",
                    "adaptive_qc_pass_fraction": 0.0,
                    "validation_error": repr(exc),
                }
            )

    qc_table = pd.DataFrame(qc_rows)
    qc_table.to_csv(
        out_tables
        / "UTI_HostOmics_U26D1A_flat_matrix_QC.tsv",
        sep="\t",
        index=False,
    )

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(
        out_metadata
        / "UTI_HostOmics_U26D1A_sparse_matrix_manifest.tsv",
        sep="\t",
        index=False,
    )

    if combined_cell_metadata:
        pd.concat(
            combined_cell_metadata,
            ignore_index=True,
        ).to_csv(
            out_metadata
            / "UTI_HostOmics_U26D1A_combined_cell_metadata.tsv.gz",
            sep="\t",
            index=False,
            compression="gzip",
        )

    archive_table = inspect_raw_archive(archive_path)
    archive_table.to_csv(
        out_tables
        / "UTI_HostOmics_U26D1A_raw_archive_members.tsv",
        sep="\t",
        index=False,
    )

    valid = qc_table[
        qc_table["validation_error"].fillna("").astype(str).eq("")
    ].copy()

    balanced = (
        len(valid) == 4
        and int((valid["condition"] == "control").sum()) == 2
        and int((valid["condition"] == "UPEC").sum()) == 2
    )
    plausible_cells = bool(
        len(valid) == 4
        and (pd.to_numeric(valid["n_cells"], errors="coerce") >= 100).all()
    )
    plausible_genes = bool(
        len(valid) == 4
        and (pd.to_numeric(valid["n_genes"], errors="coerce") >= 5000).all()
    )
    nonnegative = bool(
        len(valid) == 4
        and (
            pd.to_numeric(
                valid["negative_values"],
                errors="coerce",
            )
            .fillna(1)
            .eq(0)
            .all()
        )
    )
    qc_adequate = bool(
        len(valid) == 4
        and (
            pd.to_numeric(
                valid["adaptive_qc_pass_fraction"],
                errors="coerce",
            )
            .fillna(0)
            .ge(0.40)
            .all()
        )
    )

    if (
        balanced
        and plausible_cells
        and plausible_genes
        and nonnegative
        and qc_adequate
    ):
        decision = (
            "READY_FOR_U26D2_FLAT_MATRIX_MARKER_BASED_RECONSTRUCTION"
        )
    else:
        decision = "TARGETED_FLAT_MATRIX_REVIEW_REQUIRED"

    report_path = (
        out_results
        / "UTI_HostOmics_U26D1A_flat_matrix_validation_report.md"
    )
    write_report(
        report_path,
        qc_table,
        archive_table,
        decision,
    )

    pd.DataFrame(
        [
            {
                "phase": "U26D1A",
                "decision": decision,
                "n_expected_samples": 4,
                "n_validated_samples": len(valid),
                "n_control_samples": int(
                    (valid["condition"] == "control").sum()
                ),
                "n_UPEC_samples": int(
                    (valid["condition"] == "UPEC").sum()
                ),
                "balanced_two_by_two_design": balanced,
                "all_samples_have_at_least_100_cells": plausible_cells,
                "all_samples_have_at_least_5000_genes": plausible_genes,
                "all_expression_nonnegative": nonnegative,
                "all_samples_adaptive_QC_pass_fraction_ge_0_40": qc_adequate,
                "sparse_conversion_completed": len(manifest) == 4,
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U26D2 marker-based cell-type reconstruction and "
                    "sample-by-cell-type pseudobulk"
                    if decision
                    == "READY_FOR_U26D2_FLAT_MATRIX_MARKER_BASED_RECONSTRUCTION"
                    else "Targeted flat-matrix validation repair"
                ),
            }
        ]
    ).to_csv(
        out_tables
        / "UTI_HostOmics_U26D1A_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    run_manifest = {
        "version": VERSION,
        "project_root": str(project),
        "decision": decision,
        "validated_samples": int(len(valid)),
        "sparse_conversion_completed": bool(len(manifest) == 4),
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U26D1A_run_manifest.json"
    ).write_text(
        json.dumps(run_manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Validated samples: {len(valid)}/4")
    if len(valid):
        log(
            "Cells by sample: "
            + ", ".join(
                [
                    f"{row['sample_id']}={int(row['n_cells'])}"
                    for _, row in valid.iterrows()
                ]
            )
        )
    log(f"Sparse conversion complete: {len(manifest) == 4}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26D1A] ERROR: {exc}", file=sys.stderr)
        raise
