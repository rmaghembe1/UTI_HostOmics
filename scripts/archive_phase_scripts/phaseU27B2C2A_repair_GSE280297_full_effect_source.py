#!/usr/bin/env python3
"""
Phase U27B2C2A
Recover and lock the full GSE280297 C1-C3 tissue-level module-effect source.

Why this phase is required
--------------------------
U27B2C1 revealed that Figure 3B/E/F/G displayed only two complement modules.
The previously locked file,
UTI_HostOmics_U26B1_1_Figure_10_primary_effect_matrix.tsv,
is a complement-focused figure source rather than the complete 78-module
GSE280297 effect table.

This phase:
1. scans U26B1 and U26B1.1 tables and metadata;
2. identifies long- or wide-format C1-C3 tissue-level effect candidates;
3. rejects complement-focused and figure-specific extracts;
4. selects a full multi-axis source only when coverage thresholds pass;
5. writes a standardized wide effect matrix;
6. updates the locked registry for Figure 3B/E/F/G only;
7. preserves every other source lock unchanged.

No scientific values are recalculated. Existing reported effects are only
reformatted from the selected source table.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


VERSION = "U27B2C2A_v1.0_2026-07-15"
TAG = "phaseU27B2C2A_GSE280297_full_effect_source_repair"
LOCK_TAG = "phaseU27B2A2_final_panel_source_lock"

SCAN_RELATIVE_ROOTS = [
    "06_tables/phaseU26B1_GSE280297_endocrine_metabolic_immune_scoring",
    "06_tables/phaseU26B1_1_GSE280297_stability_refinement",
    "03_metadata/phaseU26B1_GSE280297_endocrine_metabolic_immune_scoring",
    "03_metadata/phaseU26B1_1_GSE280297_stability_refinement",
    "05_results/phaseU26B1_GSE280297_endocrine_metabolic_immune_scoring",
    "05_results/phaseU26B1_1_GSE280297_stability_refinement",
]

TABLE_SUFFIXES = (
    ".tsv",
    ".csv",
    ".txt",
    ".tsv.gz",
    ".csv.gz",
)

EFFECT_COLUMN_PRIORITY = [
    "hedges_g",
    "model_estimate",
    "effect_value",
    "mean_difference_a_minus_b",
    "mean_difference",
    "estimate",
]

CONTRAST_COLUMN_PRIORITY = [
    "contrast_id",
    "contrast",
    "comparison",
]

TISSUE_COLUMN_PRIORITY = [
    "tissue",
    "organ",
    "sample_tissue",
]

FEATURE_COLUMN_PRIORITY = [
    "feature_id",
    "submodule_id",
    "module_id",
]

DISPLAY_COLUMN_PRIORITY = [
    "display_label",
    "module_label",
    "feature_label",
]

COMPLEMENT_PATTERN = re.compile(
    r"complement|c3a|c5a|opson|lectin|terminal.?mac|convertase",
    flags=re.IGNORECASE,
)


def log(message: str) -> None:
    print(f"[U27B2C2A] {message}", flush=True)


def is_table(path: Path) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(suffix) for suffix in TABLE_SUFFIXES)


def read_table(path: Path, nrows: Optional[int] = None) -> pd.DataFrame:
    separator = "," if ".csv" in path.name.lower() else "\t"
    return pd.read_csv(
        path,
        sep=separator,
        compression="infer",
        nrows=nrows,
        low_memory=False,
    )


def first_present(columns: Sequence[str], priorities: Sequence[str]) -> Optional[str]:
    column_set = set(columns)
    for value in priorities:
        if value in column_set:
            return value
    return None


def feature_text(frame: pd.DataFrame) -> pd.Series:
    columns = [
        column
        for column in (
            "feature_id",
            "submodule_id",
            "module_id",
            "display_label",
            "module_label",
            "axis",
        )
        if column in frame.columns
    ]
    if not columns:
        return pd.Series("", index=frame.index)
    text = frame[columns[0]].fillna("").astype(str)
    for column in columns[1:]:
        text = text + " " + frame[column].fillna("").astype(str)
    return text.str.lower()


def inspect_candidate(path: Path) -> Dict[str, object]:
    result: Dict[str, object] = {
        "path": str(path),
        "filename": path.name,
        "size_bytes": path.stat().st_size,
        "read_error": "",
        "n_rows": 0,
        "n_columns": 0,
        "feature_column": "",
        "contrast_column": "",
        "tissue_column": "",
        "effect_column": "",
        "format_type": "ineligible",
        "n_unique_features": 0,
        "n_unique_axes": 0,
        "n_unique_tissues": 0,
        "has_C1": False,
        "has_C2": False,
        "has_C3": False,
        "n_C1_columns": 0,
        "n_C2_columns": 0,
        "n_C3_columns": 0,
        "complement_fraction": np.nan,
        "candidate_score": -999.0,
        "eligible_full_source": False,
    }

    try:
        frame = read_table(path)
    except Exception as exc:
        result["read_error"] = repr(exc)
        return result

    result["n_rows"] = len(frame)
    result["n_columns"] = len(frame.columns)

    feature_column = first_present(frame.columns, FEATURE_COLUMN_PRIORITY)
    contrast_column = first_present(frame.columns, CONTRAST_COLUMN_PRIORITY)
    tissue_column = first_present(frame.columns, TISSUE_COLUMN_PRIORITY)
    effect_column = first_present(frame.columns, EFFECT_COLUMN_PRIORITY)

    result["feature_column"] = feature_column or ""
    result["contrast_column"] = contrast_column or ""
    result["tissue_column"] = tissue_column or ""
    result["effect_column"] = effect_column or ""

    if feature_column:
        result["n_unique_features"] = int(
            frame[feature_column].astype(str).nunique()
        )

    if "axis" in frame.columns:
        result["n_unique_axes"] = int(
            frame["axis"].dropna().astype(str).nunique()
        )

    if tissue_column:
        result["n_unique_tissues"] = int(
            frame[tissue_column].dropna().astype(str).nunique()
        )

    text = feature_text(frame)
    if len(text):
        result["complement_fraction"] = float(
            text.str.contains(COMPLEMENT_PATTERN, na=False).mean()
        )

    wide_columns = [
        str(column)
        for column in frame.columns
        if re.match(r"^C[123]_", str(column))
    ]
    c1_columns = [column for column in wide_columns if column.startswith("C1_")]
    c2_columns = [column for column in wide_columns if column.startswith("C2_")]
    c3_columns = [column for column in wide_columns if column.startswith("C3_")]

    result["n_C1_columns"] = len(c1_columns)
    result["n_C2_columns"] = len(c2_columns)
    result["n_C3_columns"] = len(c3_columns)

    long_candidate = bool(
        feature_column
        and contrast_column
        and tissue_column
        and effect_column
    )
    wide_candidate = bool(
        feature_column
        and len(wide_columns) >= 7
    )

    if long_candidate:
        result["format_type"] = "long"
        contrasts = frame[contrast_column].astype(str)
        result["has_C1"] = bool(
            contrasts.str.contains(r"C1_", regex=True, na=False).any()
        )
        result["has_C2"] = bool(
            contrasts.str.contains(r"C2_", regex=True, na=False).any()
        )
        result["has_C3"] = bool(
            contrasts.str.contains(r"C3_", regex=True, na=False).any()
        )
    elif wide_candidate:
        result["format_type"] = "wide"
        result["has_C1"] = len(c1_columns) >= 3
        result["has_C2"] = len(c2_columns) >= 3
        result["has_C3"] = len(c3_columns) >= 1

    score = -50.0
    if long_candidate:
        score = 120.0
    elif wide_candidate:
        score = 100.0

    score += min(result["n_unique_features"], 100) * 0.8
    score += min(result["n_unique_axes"], 10) * 5.0
    score += min(result["n_unique_tissues"], 3) * 8.0
    score += 20.0 if result["has_C1"] else 0.0
    score += 20.0 if result["has_C2"] else 0.0
    score += 15.0 if result["has_C3"] else 0.0

    complement_fraction = result["complement_fraction"]
    if np.isfinite(complement_fraction):
        score -= 120.0 * max(complement_fraction - 0.25, 0)

    filename = path.name.lower()
    if "figure_10" in filename or "figure10" in filename:
        score -= 140.0
    if "complement" in filename:
        score -= 120.0
    if any(token in filename for token in ("selected", "focus", "top_", "plot_")):
        score -= 50.0
    if "decision" in filename or "manifest" in filename:
        score -= 100.0

    result["candidate_score"] = score

    result["eligible_full_source"] = bool(
        result["format_type"] in {"long", "wide"}
        and result["n_unique_features"] >= 25
        and result["has_C1"]
        and result["has_C2"]
        and result["has_C3"]
        and (
            not np.isfinite(complement_fraction)
            or complement_fraction < 0.50
        )
        and "figure_10" not in filename
        and "complement" not in filename
    )

    return result


def standardize_long(
    frame: pd.DataFrame,
    candidate: pd.Series,
) -> pd.DataFrame:
    feature_column = str(candidate["feature_column"])
    contrast_column = str(candidate["contrast_column"])
    tissue_column = str(candidate["tissue_column"])
    effect_column = str(candidate["effect_column"])

    working = frame.copy()
    contrast_text = working[contrast_column].astype(str)
    working = working[
        contrast_text.str.contains(r"^C[123]_", regex=True, na=False)
    ].copy()

    working["_effect"] = pd.to_numeric(
        working[effect_column],
        errors="coerce",
    )
    working["_feature_id"] = working[feature_column].astype(str)
    working["_contrast_tissue"] = (
        working[contrast_column].astype(str)
        + " | "
        + working[tissue_column].astype(str)
    )

    matrix = working.pivot_table(
        index="_feature_id",
        columns="_contrast_tissue",
        values="_effect",
        aggfunc="mean",
    )
    matrix = matrix.reset_index().rename(
        columns={"_feature_id": "feature_id"}
    )
    matrix.columns.name = None
    return matrix


def standardize_wide(
    frame: pd.DataFrame,
    candidate: pd.Series,
) -> pd.DataFrame:
    feature_column = str(candidate["feature_column"])
    columns = [
        column
        for column in frame.columns
        if re.match(r"^C[123]_", str(column))
    ]
    matrix = frame[[feature_column] + columns].copy()
    matrix = matrix.rename(columns={feature_column: "feature_id"})
    matrix["feature_id"] = matrix["feature_id"].astype(str)
    matrix = matrix.drop_duplicates("feature_id")
    return matrix


def validate_standard_matrix(matrix: pd.DataFrame) -> Dict[str, object]:
    c1 = [column for column in matrix.columns if str(column).startswith("C1_")]
    c2 = [column for column in matrix.columns if str(column).startswith("C2_")]
    c3 = [column for column in matrix.columns if str(column).startswith("C3_")]

    feature_count = int(matrix["feature_id"].astype(str).nunique())
    feature_text_series = matrix["feature_id"].astype(str)
    complement_fraction = float(
        feature_text_series.str.contains(
            COMPLEMENT_PATTERN,
            na=False,
        ).mean()
    )

    return {
        "unique_features": feature_count,
        "C1_columns": len(c1),
        "C2_columns": len(c2),
        "C3_columns": len(c3),
        "complement_fraction_by_feature_id": complement_fraction,
        "validation_pass": bool(
            feature_count >= 25
            and len(c1) >= 3
            and len(c2) >= 3
            and len(c3) >= 1
            and complement_fraction < 0.50
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    candidates: List[Dict[str, object]] = []
    discovered_paths: List[Path] = []

    for relative_root in SCAN_RELATIVE_ROOTS:
        root = project / relative_root
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and is_table(path):
                discovered_paths.append(path)

    log(
        f"Scanning {len(discovered_paths)} U26B1/U26B1.1 tables "
        "for a full C1-C3 source."
    )

    for path in sorted(set(discovered_paths)):
        candidates.append(inspect_candidate(path))

    audit = pd.DataFrame(candidates).sort_values(
        ["eligible_full_source", "candidate_score"],
        ascending=[False, False],
    )
    audit.to_csv(
        outtables
        / "UTI_HostOmics_U27B2C2A_GSE280297_source_candidate_audit.tsv",
        sep="\t",
        index=False,
    )

    eligible = audit[audit["eligible_full_source"]].copy()

    selected_path = ""
    selected_format = ""
    selected_score = np.nan
    standard_matrix = pd.DataFrame()
    validation: Dict[str, object] = {
        "unique_features": 0,
        "C1_columns": 0,
        "C2_columns": 0,
        "C3_columns": 0,
        "complement_fraction_by_feature_id": np.nan,
        "validation_pass": False,
    }

    if not eligible.empty:
        top = eligible.iloc[0]
        selected_path = str(top["path"])
        selected_format = str(top["format_type"])
        selected_score = float(top["candidate_score"])

        source_frame = read_table(Path(selected_path))
        if selected_format == "long":
            standard_matrix = standardize_long(source_frame, top)
        else:
            standard_matrix = standardize_wide(source_frame, top)

        validation = validate_standard_matrix(standard_matrix)

    standardized_path = (
        outtables
        / "UTI_HostOmics_U27B2C2A_GSE280297_full_tissue_effect_matrix.tsv"
    )
    if not standard_matrix.empty:
        standard_matrix.to_csv(
            standardized_path,
            sep="\t",
            index=False,
        )

    registry_path = (
        project
        / "03_metadata"
        / LOCK_TAG
        / "UTI_HostOmics_U27B2A2_final_locked_panel_source_registry.tsv"
    )
    if not registry_path.exists():
        raise FileNotFoundError(
            f"Locked source registry not found: {registry_path}"
        )

    registry = pd.read_csv(
        registry_path,
        sep="\t",
        low_memory=False,
    )

    repaired_registry = registry.copy()
    repair_panels = {"Figure_3B", "Figure_3E", "Figure_3F", "Figure_3G"}
    repair_mask = (
        repaired_registry["panel_key"].astype(str).isin(repair_panels)
        & (
            repaired_registry["source_role"].astype(str)
            == "gse280297_primary_matrix"
        )
    )

    repaired_rows = int(repair_mask.sum())

    if validation["validation_pass"]:
        repaired_registry.loc[
            repair_mask,
            "locked_path",
        ] = str(standardized_path)
        repaired_registry.loc[
            repair_mask,
            "schema_columns",
        ] = ";".join(standard_matrix.columns.astype(str))
        repaired_registry.loc[
            repair_mask,
            "lock_status",
        ] = "LOCKED_U27B2C2A_FULL_GSE280297_REPAIR"
        repaired_registry.loc[
            repair_mask,
            "locked_path_exists",
        ] = True

    repaired_registry_path = (
        outmetadata
        / "UTI_HostOmics_U27B2C2A_repaired_locked_panel_source_registry.tsv"
    )
    repaired_registry.to_csv(
        repaired_registry_path,
        sep="\t",
        index=False,
    )

    old_paths = (
        registry.loc[repair_mask, "locked_path"]
        .astype(str)
        .drop_duplicates()
        .tolist()
    )

    repair_manifest = pd.DataFrame(
        [
            {
                "panel_key": panel,
                "source_role": "gse280297_primary_matrix",
                "old_locked_path": ";".join(old_paths),
                "new_locked_path": (
                    str(standardized_path)
                    if validation["validation_pass"]
                    else ""
                ),
                "repair_applied": bool(validation["validation_pass"]),
            }
            for panel in sorted(repair_panels)
        ]
    )
    repair_manifest.to_csv(
        outtables
        / "UTI_HostOmics_U27B2C2A_Figure3_source_repair_manifest.tsv",
        sep="\t",
        index=False,
    )

    validation_frame = pd.DataFrame(
        [
            {
                "selected_source": selected_path,
                "selected_format": selected_format,
                "selected_candidate_score": selected_score,
                **validation,
                "registry_rows_repaired": repaired_rows,
                "standardized_matrix_path": (
                    str(standardized_path)
                    if standard_matrix.shape[0] > 0
                    else ""
                ),
            }
        ]
    )
    validation_frame.to_csv(
        outtables
        / "UTI_HostOmics_U27B2C2A_standard_matrix_validation.tsv",
        sep="\t",
        index=False,
    )

    if (
        validation["validation_pass"]
        and repaired_rows == 4
        and standardized_path.exists()
        and int(validation["unique_features"]) >= 25
    ):
        decision = (
            "READY_FOR_U27B2C2B_FINAL_FIGURES_1_TO_4_REBUILD"
        )
    else:
        decision = (
            "TARGETED_GSE280297_FULL_EFFECT_SOURCE_IDENTIFICATION_REQUIRED"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B2C2A",
                "decision": decision,
                "tables_scanned": len(audit),
                "eligible_full_source_candidates": len(eligible),
                "selected_source": selected_path,
                "selected_format": selected_format,
                "unique_features_in_standard_matrix": validation[
                    "unique_features"
                ],
                "C1_columns": validation["C1_columns"],
                "C2_columns": validation["C2_columns"],
                "C3_columns": validation["C3_columns"],
                "standard_matrix_validation_pass": validation[
                    "validation_pass"
                ],
                "registry_rows_repaired": repaired_rows,
                "scientific_values_recalculated": False,
                "manuscript_modified": False,
                "figures_modified": False,
                "next_phase": (
                    "U27B2C2B rebuild and final visual repair of Figures 1-4"
                    if decision.startswith("READY_FOR_U27B2C2B")
                    else "Inspect candidate audit and select the correct full source"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B2C2A_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B2C2A_GSE280297_source_repair_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B2C2A - GSE280297 full effect-source repair\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- U26B1/U26B1.1 tables scanned: **{len(audit)}**.\n"
        )
        handle.write(
            f"- Eligible full-source candidates: **{len(eligible)}**.\n"
        )
        handle.write(
            f"- Selected source: `{selected_path or 'none'}`.\n"
        )
        handle.write(
            f"- Selected source format: **{selected_format or 'none'}**.\n"
        )
        handle.write(
            f"- Standardized unique modules: "
            f"**{validation['unique_features']}**.\n"
        )
        handle.write(
            f"- Contrast columns: C1={validation['C1_columns']}, "
            f"C2={validation['C2_columns']}, "
            f"C3={validation['C3_columns']}.\n"
        )
        handle.write(
            f"- Standard-matrix validation: "
            f"**{validation['validation_pass']}**.\n"
        )
        handle.write(
            f"- Figure 3 registry rows repaired: **{repaired_rows}/4**.\n\n"
        )

        handle.write("## Source-integrity correction\n\n")
        handle.write(
            "The complement-focused `Figure_10_primary_effect_matrix` is no "
            "longer used for broad pregnancy panels when a validated full "
            "C1-C3 multi-axis source is recovered. All effect values are "
            "copied from the selected U26B1/U26B1.1 output without "
            "re-estimation.\n"
        )

    (
        outresults
        / "UTI_HostOmics_U27B2C2A_run_manifest.json"
    ).write_text(
        json.dumps(
            {
                "version": VERSION,
                "decision": decision,
                "tables_scanned": len(audit),
                "eligible_candidates": len(eligible),
                "selected_source": selected_path,
                "unique_features": validation["unique_features"],
                "C1_columns": validation["C1_columns"],
                "C2_columns": validation["C2_columns"],
                "C3_columns": validation["C3_columns"],
                "validation_pass": validation["validation_pass"],
                "registry_rows_repaired": repaired_rows,
                "scientific_values_recalculated": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log(f"Tables scanned: {len(audit)}")
    log(f"Eligible full-source candidates: {len(eligible)}")
    log(f"Selected source: {selected_path or 'none'}")
    log(
        f"Standard matrix: {validation['unique_features']} features; "
        f"C1={validation['C1_columns']}, "
        f"C2={validation['C2_columns']}, "
        f"C3={validation['C3_columns']}"
    )
    log(f"Registry rows repaired: {repaired_rows}/4")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B2C2A] ERROR: {exc}", file=sys.stderr)
        raise
