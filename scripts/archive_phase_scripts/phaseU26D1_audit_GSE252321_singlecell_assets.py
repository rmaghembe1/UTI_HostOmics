#!/usr/bin/env python3
"""
Phase U26D1
GSE252321 single-cell asset discovery and reconstruction-readiness audit.

Purpose
-------
1. Inventory all local GSE252321 assets.
2. Detect valid 10x matrix triplets and annotated single-cell objects.
3. Inspect existing sample-design and cell-annotation candidates.
4. Resolve control/UPEC sample mapping where possible.
5. Decide whether U26D2 can proceed with marker-based cell-type reconstruction.

This phase does not modify the manuscript or existing figures.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


VERSION = "U26D1_v1.0_2026-07-14"
TAG = "phaseU26D1_GSE252321_singlecell_asset_audit"

ANNOTATION_TERMS = {
    "cell_type",
    "celltype",
    "cell type",
    "annotation",
    "broad_class",
    "broadclass",
    "cluster",
    "seurat_clusters",
    "cell_label",
    "celllabel",
    "identity",
    "ident",
}

GROUP_TERMS = {
    "group",
    "condition",
    "treatment",
    "infection",
    "status",
    "phenotype",
    "sample_group",
}

SAMPLE_TERMS = {
    "sample",
    "sample_id",
    "sampleid",
    "library",
    "library_id",
    "orig.ident",
    "orig_ident",
    "gsm",
    "geo_accession",
}


def log(message: str) -> None:
    print(f"[U26D1] {message}", flush=True)


def normalize_token(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def safe_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return -1


def classify_file(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".h5ad"):
        return "h5ad"
    if name.endswith(".loom"):
        return "loom"
    if name.endswith(".rds"):
        return "rds"
    if name.endswith(".h5") or name.endswith(".hdf5"):
        return "h5"
    if name.endswith(".mtx") or name.endswith(".mtx.gz"):
        return "matrix_market"
    if "barcode" in name and (
        name.endswith(".tsv")
        or name.endswith(".tsv.gz")
        or name.endswith(".txt")
        or name.endswith(".txt.gz")
    ):
        return "barcodes"
    if (
        ("feature" in name or "genes" in name)
        and (
            name.endswith(".tsv")
            or name.endswith(".tsv.gz")
            or name.endswith(".txt")
            or name.endswith(".txt.gz")
        )
    ):
        return "features"
    if name.endswith(".csv") or name.endswith(".csv.gz"):
        return "csv"
    if (
        name.endswith(".tsv")
        or name.endswith(".tsv.gz")
        or name.endswith(".txt")
        or name.endswith(".txt.gz")
    ):
        return "text_table"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".pkl") or name.endswith(".pickle"):
        return "pickle"
    return "other"


def find_project_files(project: Path) -> List[Path]:
    paths: List[Path] = []
    for root, dirs, files in os.walk(project):
        dirs[:] = [
            directory
            for directory in dirs
            if directory not in {".git", "__pycache__"}
        ]
        root_path = Path(root)
        for filename in files:
            path = root_path / filename
            text = str(path).lower()
            if "gse252321" in text:
                paths.append(path)
    return sorted(set(paths))


def read_table_preview(path: Path, nrows: int = 5) -> Tuple[List[str], int, str]:
    separators = ["\t", ","]
    last_error = ""
    for sep in separators:
        try:
            frame = pd.read_csv(
                path,
                sep=sep,
                compression="infer",
                nrows=nrows,
                low_memory=False,
            )
            return list(map(str, frame.columns)), int(len(frame)), ""
        except Exception as exc:
            last_error = str(exc)
    return [], 0, last_error


def count_lines(path: Path, max_lines: Optional[int] = None) -> int:
    count = 0
    with open_text(path) as handle:
        for _ in handle:
            count += 1
            if max_lines is not None and count >= max_lines:
                break
    return count


def matrix_market_dimensions(path: Path) -> Tuple[Optional[int], Optional[int], Optional[int], str]:
    try:
        with open_text(path) as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("%"):
                    continue
                parts = stripped.split()
                if len(parts) >= 3:
                    return int(parts[0]), int(parts[1]), int(parts[2]), ""
                return None, None, None, f"Unexpected MatrixMarket header: {stripped}"
    except Exception as exc:
        return None, None, None, str(exc)
    return None, None, None, "No MatrixMarket dimension line found"


def feature_preview(path: Path, n: int = 5) -> Tuple[int, str, str]:
    rows = 0
    preview: List[str] = []
    gene_symbol_column_guess = ""
    try:
        with open_text(path) as handle:
            for line in handle:
                rows += 1
                if len(preview) < n:
                    preview.append(line.rstrip("\n"))
        if preview:
            first_parts = preview[0].split("\t")
            if len(first_parts) >= 2:
                gene_symbol_column_guess = "column_2"
            elif len(first_parts) == 1:
                gene_symbol_column_guess = "column_1"
        return rows, " | ".join(preview), gene_symbol_column_guess
    except Exception as exc:
        return 0, f"ERROR: {exc}", ""


def barcode_preview(path: Path, n: int = 5) -> Tuple[int, str]:
    rows = 0
    preview: List[str] = []
    try:
        with open_text(path) as handle:
            for line in handle:
                rows += 1
                if len(preview) < n:
                    preview.append(line.rstrip("\n"))
        return rows, " | ".join(preview)
    except Exception as exc:
        return 0, f"ERROR: {exc}"


def locate_triplets(paths: Sequence[Path]) -> pd.DataFrame:
    by_directory: Dict[Path, Dict[str, List[Path]]] = {}
    for path in paths:
        file_type = classify_file(path)
        if file_type not in {"matrix_market", "barcodes", "features"}:
            continue
        by_directory.setdefault(
            path.parent,
            {"matrix_market": [], "barcodes": [], "features": []},
        )[file_type].append(path)

    rows = []
    for directory, groups in sorted(by_directory.items()):
        matrices = sorted(groups["matrix_market"])
        barcodes = sorted(groups["barcodes"])
        features = sorted(groups["features"])

        if not matrices:
            continue

        for matrix_path in matrices:
            matrix_stem = normalize_token(
                matrix_path.name
                .replace(".mtx.gz", "")
                .replace(".mtx", "")
            )

            def score(candidate: Path) -> int:
                candidate_token = normalize_token(candidate.name)
                overlap = 0
                if matrix_stem and matrix_stem in candidate_token:
                    overlap += 10
                if candidate.parent == matrix_path.parent:
                    overlap += 5
                return overlap

            barcode_path = (
                sorted(barcodes, key=score, reverse=True)[0]
                if barcodes
                else None
            )
            feature_path = (
                sorted(features, key=score, reverse=True)[0]
                if features
                else None
            )

            n_rows, n_cols, n_nonzero, matrix_error = (
                matrix_market_dimensions(matrix_path)
            )

            n_barcodes = None
            barcode_head = ""
            if barcode_path is not None:
                n_barcodes, barcode_head = barcode_preview(barcode_path)

            n_features = None
            feature_head = ""
            symbol_guess = ""
            if feature_path is not None:
                n_features, feature_head, symbol_guess = feature_preview(
                    feature_path
                )

            row_match = (
                n_rows is not None
                and n_features is not None
                and int(n_rows) == int(n_features)
            )
            col_match = (
                n_cols is not None
                and n_barcodes is not None
                and int(n_cols) == int(n_barcodes)
            )

            sample_candidate = infer_sample_candidate(
                matrix_path,
                directory,
            )
            group_candidate = infer_group_from_text(
                " ".join(
                    [
                        str(matrix_path),
                        str(directory),
                        sample_candidate,
                    ]
                )
            )

            rows.append(
                {
                    "matrix_path": str(matrix_path),
                    "directory": str(directory),
                    "sample_candidate": sample_candidate,
                    "group_candidate_from_path": group_candidate,
                    "barcode_path": (
                        str(barcode_path)
                        if barcode_path is not None
                        else ""
                    ),
                    "feature_path": (
                        str(feature_path)
                        if feature_path is not None
                        else ""
                    ),
                    "matrix_n_features": n_rows,
                    "matrix_n_cells": n_cols,
                    "matrix_n_nonzero": n_nonzero,
                    "barcode_count": n_barcodes,
                    "feature_count": n_features,
                    "feature_symbol_column_guess": symbol_guess,
                    "feature_preview": feature_head,
                    "barcode_preview": barcode_head,
                    "feature_count_matches_matrix": row_match,
                    "barcode_count_matches_matrix": col_match,
                    "valid_10x_triplet": bool(
                        barcode_path is not None
                        and feature_path is not None
                        and row_match
                        and col_match
                    ),
                    "matrix_read_error": matrix_error,
                }
            )

    return pd.DataFrame(rows)


def infer_sample_candidate(matrix_path: Path, directory: Path) -> str:
    candidates = [
        directory.name,
        directory.parent.name,
        matrix_path.name,
    ]
    for candidate in candidates:
        cleaned = re.sub(
            r"(?i)(matrix|filtered|raw|feature|barcode|genes|mtx|gz|tsv)",
            " ",
            candidate,
        )
        cleaned = re.sub(r"[_\-.]+", " ", cleaned).strip()
        if cleaned and normalize_token(cleaned) not in {
            "gse252321",
            "supplementary",
            "matrix",
            "data",
            "raw",
        }:
            return cleaned
    return directory.name


def infer_group_from_text(text: str) -> str:
    token = str(text).lower()
    if re.search(r"\b(upec|infected|infection|uti)\b", token):
        return "UPEC"
    if re.search(r"\b(control|ctrl|mock|pbs|uninfected|naive)\b", token):
        return "control"
    return "unresolved"


def inspect_h5ad(path: Path) -> Dict[str, object]:
    result: Dict[str, object] = {
        "path": str(path),
        "object_type": "h5ad",
        "readable": False,
        "n_obs": np.nan,
        "n_vars": np.nan,
        "obs_columns": "",
        "annotation_columns": "",
        "sample_columns": "",
        "group_columns": "",
        "inspection_method": "",
        "error": "",
    }

    try:
        import anndata as ad  # type: ignore

        object_ = ad.read_h5ad(path, backed="r")
        obs_columns = list(map(str, object_.obs.columns))
        result.update(
            {
                "readable": True,
                "n_obs": int(object_.n_obs),
                "n_vars": int(object_.n_vars),
                "obs_columns": ";".join(obs_columns),
                "annotation_columns": ";".join(
                    [
                        column
                        for column in obs_columns
                        if normalize_token(column)
                        in {normalize_token(term) for term in ANNOTATION_TERMS}
                    ]
                ),
                "sample_columns": ";".join(
                    [
                        column
                        for column in obs_columns
                        if normalize_token(column)
                        in {normalize_token(term) for term in SAMPLE_TERMS}
                    ]
                ),
                "group_columns": ";".join(
                    [
                        column
                        for column in obs_columns
                        if normalize_token(column)
                        in {normalize_token(term) for term in GROUP_TERMS}
                    ]
                ),
                "inspection_method": "anndata_backed",
            }
        )
        try:
            object_.file.close()
        except Exception:
            pass
        return result
    except Exception as exc:
        result["error"] = str(exc)

    try:
        import h5py  # type: ignore

        with h5py.File(path, "r") as handle:
            keys = list(handle.keys())
            obs_columns: List[str] = []
            if "obs" in handle:
                obs_columns = list(map(str, handle["obs"].keys()))
            result.update(
                {
                    "readable": True,
                    "obs_columns": ";".join(obs_columns),
                    "annotation_columns": ";".join(
                        [
                            column
                            for column in obs_columns
                            if normalize_token(column)
                            in {normalize_token(term) for term in ANNOTATION_TERMS}
                        ]
                    ),
                    "sample_columns": ";".join(
                        [
                            column
                            for column in obs_columns
                            if normalize_token(column)
                            in {normalize_token(term) for term in SAMPLE_TERMS}
                        ]
                    ),
                    "group_columns": ";".join(
                        [
                            column
                            for column in obs_columns
                            if normalize_token(column)
                            in {normalize_token(term) for term in GROUP_TERMS}
                        ]
                    ),
                    "inspection_method": (
                        "h5py_keys:" + ";".join(map(str, keys))
                    ),
                    "error": "",
                }
            )
    except Exception as exc:
        result["error"] = str(exc)

    return result


def inspect_h5(path: Path) -> Dict[str, object]:
    result: Dict[str, object] = {
        "path": str(path),
        "object_type": "h5",
        "readable": False,
        "top_level_keys": "",
        "likely_10x_h5": False,
        "likely_annotated_object": False,
        "error": "",
    }
    try:
        import h5py  # type: ignore

        with h5py.File(path, "r") as handle:
            keys = list(map(str, handle.keys()))
            matrix_keys = []
            if "matrix" in handle:
                matrix_keys = list(map(str, handle["matrix"].keys()))
            likely_10x = (
                "matrix" in handle
                and {"data", "indices", "indptr", "shape"}.issubset(
                    set(matrix_keys)
                )
            )
            likely_annotated = (
                "obs" in handle
                or "cell_type" in handle
                or "metadata" in handle
            )
            result.update(
                {
                    "readable": True,
                    "top_level_keys": ";".join(keys),
                    "likely_10x_h5": likely_10x,
                    "likely_annotated_object": likely_annotated,
                }
            )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def inspect_objects(paths: Sequence[Path]) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for path in paths:
        file_type = classify_file(path)
        if file_type == "h5ad":
            rows.append(inspect_h5ad(path))
        elif file_type == "h5":
            rows.append(inspect_h5(path))
        elif file_type in {"loom", "rds"}:
            rows.append(
                {
                    "path": str(path),
                    "object_type": file_type,
                    "readable": False,
                    "likely_annotated_object": True,
                    "inspection_method": "presence_only",
                    "error": (
                        "Object requires a compatible reader; presence "
                        "recorded for targeted inspection."
                    ),
                }
            )
    return pd.DataFrame(rows)


def inspect_table_candidates(paths: Sequence[Path]) -> pd.DataFrame:
    rows = []
    normalized_annotation_terms = {
        normalize_token(term) for term in ANNOTATION_TERMS
    }
    normalized_group_terms = {
        normalize_token(term) for term in GROUP_TERMS
    }
    normalized_sample_terms = {
        normalize_token(term) for term in SAMPLE_TERMS
    }

    for path in paths:
        if classify_file(path) not in {"csv", "text_table"}:
            continue
        if safe_size(path) > 250_000_000:
            continue

        columns, preview_rows, error = read_table_preview(path)
        normalized_columns = {
            normalize_token(column): column for column in columns
        }

        annotation_columns = [
            original
            for normalized, original in normalized_columns.items()
            if normalized in normalized_annotation_terms
            or any(
                term in normalized
                for term in ["celltype", "annotation", "cluster"]
            )
        ]
        sample_columns = [
            original
            for normalized, original in normalized_columns.items()
            if normalized in normalized_sample_terms
            or "sample" in normalized
            or normalized.startswith("gsm")
        ]
        group_columns = [
            original
            for normalized, original in normalized_columns.items()
            if normalized in normalized_group_terms
            or any(
                term in normalized
                for term in ["group", "condition", "treatment", "infect"]
            )
        ]

        filename_text = path.name.lower()
        candidate_role = []
        if annotation_columns:
            candidate_role.append("cell_annotation")
        if sample_columns:
            candidate_role.append("sample_identifier")
        if group_columns:
            candidate_role.append("group_mapping")
        if any(
            term in filename_text
            for term in ["annot", "metadata", "design", "cluster", "celltype"]
        ):
            candidate_role.append("filename_metadata_signal")

        if candidate_role:
            rows.append(
                {
                    "path": str(path),
                    "size_bytes": safe_size(path),
                    "columns": ";".join(columns),
                    "annotation_columns": ";".join(annotation_columns),
                    "sample_columns": ";".join(sample_columns),
                    "group_columns": ";".join(group_columns),
                    "candidate_role": ";".join(sorted(set(candidate_role))),
                    "preview_rows_read": preview_rows,
                    "read_error": error,
                }
            )

    return pd.DataFrame(rows)


def read_candidate_mapping(table_candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if table_candidates.empty:
        return pd.DataFrame(rows)

    for _, candidate in table_candidates.iterrows():
        path = Path(candidate["path"])
        sample_columns = [
            column
            for column in str(candidate.get("sample_columns", "")).split(";")
            if column
        ]
        group_columns = [
            column
            for column in str(candidate.get("group_columns", "")).split(";")
            if column
        ]
        if not sample_columns or not group_columns:
            continue

        try:
            frame = pd.read_csv(
                path,
                sep=None,
                engine="python",
                compression="infer",
                low_memory=False,
            )
        except Exception:
            continue

        sample_column = sample_columns[0]
        for group_column in group_columns:
            if (
                sample_column not in frame.columns
                or group_column not in frame.columns
            ):
                continue
            for _, row in frame[[sample_column, group_column]].dropna().iterrows():
                group = infer_group_from_text(row[group_column])
                if group == "unresolved":
                    continue
                rows.append(
                    {
                        "source_path": str(path),
                        "sample_column": sample_column,
                        "group_column": group_column,
                        "sample_value": str(row[sample_column]),
                        "sample_token": normalize_token(row[sample_column]),
                        "resolved_group": group,
                    }
                )
    return pd.DataFrame(rows).drop_duplicates()


def reconcile_triplet_groups(
    triplets: pd.DataFrame,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    if triplets.empty:
        return triplets

    result = triplets.copy()
    result["group_from_existing_metadata"] = "unresolved"
    result["group_resolution_source"] = "unresolved"

    if not mapping.empty:
        for index, row in result.iterrows():
            sample_tokens = {
                normalize_token(row.get("sample_candidate", "")),
                normalize_token(Path(row["matrix_path"]).stem),
                normalize_token(Path(row["directory"]).name),
            }
            best = None
            best_score = 0
            for _, candidate in mapping.iterrows():
                candidate_token = str(candidate["sample_token"])
                score = 0
                for token in sample_tokens:
                    if not token or not candidate_token:
                        continue
                    if token == candidate_token:
                        score = max(score, 100)
                    elif token in candidate_token or candidate_token in token:
                        score = max(
                            score,
                            min(len(token), len(candidate_token)),
                        )
                if score > best_score:
                    best_score = score
                    best = candidate
            if best is not None and best_score >= 3:
                result.loc[
                    index, "group_from_existing_metadata"
                ] = best["resolved_group"]
                result.loc[
                    index, "group_resolution_source"
                ] = (
                    f"existing_metadata:{best['source_path']}:"
                    f"{best['group_column']}"
                )

    result["resolved_group"] = np.where(
        result["group_from_existing_metadata"] != "unresolved",
        result["group_from_existing_metadata"],
        result["group_candidate_from_path"],
    )
    result["group_resolution_source"] = np.where(
        result["group_from_existing_metadata"] != "unresolved",
        result["group_resolution_source"],
        np.where(
            result["group_candidate_from_path"] != "unresolved",
            "path_or_filename",
            "unresolved",
        ),
    )
    return result


def object_has_annotation(object_audit: pd.DataFrame) -> bool:
    if object_audit.empty:
        return False
    annotation_column_signal = (
        object_audit.get(
            "annotation_columns",
            pd.Series([""] * len(object_audit)),
        )
        .fillna("")
        .astype(str)
        .str.len()
        > 0
    )
    explicit_object_signal = object_audit.get(
        "likely_annotated_object",
        pd.Series([False] * len(object_audit)),
    ).fillna(False).astype(bool)
    return bool((annotation_column_signal | explicit_object_signal).any())


def write_report(
    path: Path,
    inventory: pd.DataFrame,
    triplets: pd.DataFrame,
    objects: pd.DataFrame,
    tables: pd.DataFrame,
    decision: str,
) -> None:
    valid_triplets = (
        triplets[triplets["valid_10x_triplet"]]
        if not triplets.empty
        else pd.DataFrame()
    )
    group_counts = (
        valid_triplets["resolved_group"].value_counts().to_dict()
        if not valid_triplets.empty
        else {}
    )

    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26D1 - GSE252321 single-cell asset audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: `{decision}`\n")
        handle.write(
            "- Manuscript and existing figures were not modified.\n\n"
        )

        handle.write("## Local asset inventory\n\n")
        handle.write(
            f"- GSE252321-associated files discovered: **{len(inventory)}**.\n"
        )
        handle.write(
            f"- Valid 10x matrix triplets: **{len(valid_triplets)}**.\n"
        )
        handle.write(
            f"- Single-cell object candidates: **{len(objects)}**.\n"
        )
        handle.write(
            f"- Metadata/annotation table candidates: **{len(tables)}**.\n\n"
        )

        handle.write("## Resolved biological samples\n\n")
        if valid_triplets.empty:
            handle.write("- No valid 10x triplets were resolved.\n\n")
        else:
            for _, row in valid_triplets.iterrows():
                handle.write(
                    f"- `{row['sample_candidate']}`: "
                    f"{int(row['matrix_n_cells'])} cells, "
                    f"{int(row['matrix_n_features'])} features, "
                    f"group `{row['resolved_group']}` "
                    f"({row['group_resolution_source']}).\n"
                )
            handle.write("\n")

        handle.write("## Group balance\n\n")
        for group, count in sorted(group_counts.items()):
            handle.write(f"- {group}: **{int(count)}** matrices.\n")
        handle.write("\n")

        handle.write("## Interpretation\n\n")
        if decision == "ANNOTATED_OBJECT_AVAILABLE_USE_DIRECT_CELLTYPE_PSEUDOBULK":
            handle.write(
                "An annotated object appears to be available. U26D2 should "
                "prefer its existing cell labels after validating marker "
                "specificity and sample identity.\n"
            )
        elif decision == "READY_FOR_U26D2_MARKER_BASED_CELLTYPE_RECONSTRUCTION":
            handle.write(
                "Four valid biological-sample matrices with a resolved "
                "two-control/two-UPEC design are available. U26D2 can proceed "
                "with QC, integration, marker-based annotation and sample-by-"
                "cell-type pseudobulk scoring.\n"
            )
        elif decision == "READY_FOR_U26D2_WITH_TARGETED_SAMPLE_MAPPING":
            handle.write(
                "The expression matrices appear usable, but sample treatment "
                "mapping is incomplete. U26D2 should not begin inferential "
                "testing until control/UPEC labels are repaired.\n"
            )
        else:
            handle.write(
                "The local single-cell inputs are not yet sufficient for "
                "defensible cell-type reconstruction. Review the audit tables "
                "before downloading or rebuilding additional assets.\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    out_tables = project / "06_tables" / TAG
    out_results = project / "05_results" / TAG
    out_metadata = project / "03_metadata" / TAG
    for directory in [out_tables, out_results, out_metadata]:
        directory.mkdir(parents=True, exist_ok=True)

    log("Discovering project-wide GSE252321 assets.")
    paths = find_project_files(project)

    inventory_rows = []
    for path in paths:
        file_type = classify_file(path)
        inventory_rows.append(
            {
                "path": str(path),
                "relative_path": str(path.relative_to(project)),
                "file_type": file_type,
                "size_bytes": safe_size(path),
                "parent_directory": str(path.parent),
            }
        )
    inventory = pd.DataFrame(inventory_rows)
    inventory.to_csv(
        out_tables / "UTI_HostOmics_U26D1_file_inventory.tsv",
        sep="\t",
        index=False,
    )

    log("Auditing 10x matrix triplets.")
    triplets = locate_triplets(paths)

    log("Inspecting metadata and cell-annotation candidates.")
    table_candidates = inspect_table_candidates(paths)
    mapping = read_candidate_mapping(table_candidates)
    triplets = reconcile_triplet_groups(triplets, mapping)

    triplets.to_csv(
        out_tables / "UTI_HostOmics_U26D1_10x_triplet_audit.tsv",
        sep="\t",
        index=False,
    )
    table_candidates.to_csv(
        out_tables / "UTI_HostOmics_U26D1_metadata_table_candidates.tsv",
        sep="\t",
        index=False,
    )
    mapping.to_csv(
        out_metadata / "UTI_HostOmics_U26D1_candidate_sample_group_mapping.tsv",
        sep="\t",
        index=False,
    )

    log("Inspecting single-cell object candidates.")
    objects = inspect_objects(paths)
    objects.to_csv(
        out_tables / "UTI_HostOmics_U26D1_object_audit.tsv",
        sep="\t",
        index=False,
    )

    valid = (
        triplets[triplets["valid_10x_triplet"]].copy()
        if not triplets.empty
        else pd.DataFrame()
    )
    group_counts = (
        valid["resolved_group"].value_counts().to_dict()
        if not valid.empty
        else {}
    )

    annotated_available = object_has_annotation(objects)
    balanced_design = (
        int(group_counts.get("control", 0)) >= 2
        and int(group_counts.get("UPEC", 0)) >= 2
    )

    if annotated_available:
        decision = (
            "ANNOTATED_OBJECT_AVAILABLE_USE_DIRECT_CELLTYPE_PSEUDOBULK"
        )
    elif len(valid) >= 4 and balanced_design:
        decision = (
            "READY_FOR_U26D2_MARKER_BASED_CELLTYPE_RECONSTRUCTION"
        )
    elif len(valid) >= 4:
        decision = (
            "READY_FOR_U26D2_WITH_TARGETED_SAMPLE_MAPPING"
        )
    else:
        decision = "TARGETED_SINGLECELL_INPUT_REVIEW_REQUIRED"

    report_path = (
        out_results
        / "UTI_HostOmics_U26D1_singlecell_asset_audit_report.md"
    )
    write_report(
        report_path,
        inventory,
        triplets,
        objects,
        table_candidates,
        decision,
    )

    pd.DataFrame(
        [
            {
                "phase": "U26D1",
                "decision": decision,
                "n_GSE252321_files": len(inventory),
                "n_valid_10x_triplets": len(valid),
                "n_control_matrices": int(group_counts.get("control", 0)),
                "n_UPEC_matrices": int(group_counts.get("UPEC", 0)),
                "n_unresolved_matrices": int(
                    group_counts.get("unresolved", 0)
                ),
                "annotated_object_available": annotated_available,
                "n_metadata_table_candidates": len(table_candidates),
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U26D2 cell-type reconstruction and sample-by-cell-type "
                    "pseudobulk scoring"
                    if decision
                    in {
                        "ANNOTATED_OBJECT_AVAILABLE_USE_DIRECT_CELLTYPE_PSEUDOBULK",
                        "READY_FOR_U26D2_MARKER_BASED_CELLTYPE_RECONSTRUCTION",
                    }
                    else "Targeted single-cell input or sample-label repair"
                ),
            }
        ]
    ).to_csv(
        out_tables / "UTI_HostOmics_U26D1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "decision": decision,
        "n_files": int(len(inventory)),
        "n_valid_10x_triplets": int(len(valid)),
        "annotated_object_available": bool(annotated_available),
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results / "UTI_HostOmics_U26D1_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log(f"GSE252321 files: {len(inventory)}")
    log(f"Valid 10x triplets: {len(valid)}")
    log(
        "Resolved groups: "
        f"control={int(group_counts.get('control', 0))}, "
        f"UPEC={int(group_counts.get('UPEC', 0))}, "
        f"unresolved={int(group_counts.get('unresolved', 0))}"
    )
    log(f"Annotated object available: {annotated_available}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26D1] ERROR: {exc}", file=sys.stderr)
        raise
