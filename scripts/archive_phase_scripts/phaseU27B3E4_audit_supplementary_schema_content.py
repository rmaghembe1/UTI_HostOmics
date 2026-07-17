#!/usr/bin/env python3
"""
Phase U27B3E4
Table-by-table schema, missingness, content, archive and manuscript-consistency
audit for the semantically corrected Supplementary Tables S1-S10 package.

Input package
-------------
11_supplementary/phaseU27B3E321_semantic_accession_audit_correction

This phase is read-only. It verifies:
- all ten materialized TSVs and their row-level provenance;
- expected source blocks and exact source-row counts;
- source-aware missingness rather than misleading global union-schema
  missingness;
- table-specific biological and statistical constraints;
- semantic accession handling;
- agreement between the supplementary index in the accession-corrected v6.3
  manuscript and S1-S10;
- ZIP integrity and byte agreement between archived and on-disk TSVs.

No scientific value, source file, manuscript, figure, table or package member is
modified.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

import pandas as pd


VERSION = "U27B3E4_v1.0_2026-07-16"
TAG = "phaseU27B3E4_supplementary_schema_content_audit"

DEFAULT_PACKAGE_ROOT = (
    "__UTI_HOSTOMICS_PROJECT_ROOT__/"
    "11_supplementary/"
    "phaseU27B3E321_semantic_accession_audit_correction"
)

DEFAULT_MANUSCRIPT = (
    "__UTI_HOSTOMICS_PROJECT_ROOT__/"
    "09_manuscript_docx/"
    "phaseU27B3E22_targeted_accession_correction/"
    "UTI_HostOmics_preZotero_manuscript_"
    "v6_3_U27B3E22_accession_corrected.docx"
)

CORRECT_ACCESSION = "GSE186800"
WRONG_ACCESSION = "GSE168600"

PROVENANCE_COLUMNS = [
    "_supplementary_table",
    "_table_title",
    "_source_order",
    "_source_role",
    "_source_file",
    "_source_relative_path",
    "_source_sha256",
    "_source_row_number",
]

TABLE_TITLES = {
    "S1": (
        "Dataset architecture, sample design and inclusion roles for "
        "GSE112098, GSE280297, GSE186800 and GSE252321."
    ),
    "S2": (
        "Expanded 78-submodule library organized across ten biological axes."
    ),
    "S3": (
        "Dataset-specific module effects and factorial or adjusted contrasts."
    ),
    "S4": (
        "Cross-dataset recurrence, directional concordance and "
        "evidence-class assignments."
    ),
    "S5": (
        "GSE280297 pregnancy, tissue and outcome-specific module effects."
    ),
    "S6": (
        "GSE252321 quality control, cluster markers, broad populations and "
        "refined subtypes."
    ),
    "S7": (
        "Broad-cell and refined-subtype pseudobulk module localization results."
    ),
    "S8": (
        "Complement-stage and endocrine-metabolic cellular attribution tables."
    ),
    "S9": (
        "Figure 1-8 source-value manifest and panel-level provenance registry."
    ),
    "S10": (
        "Interpretation-boundary, sensitivity and manuscript "
        "claim-traceability register."
    ),
}

EXPECTED_SOURCE_ROLE_ROWS = {
    "S1": {
        "GSE252321 four-sample biological design": 4,
        "GSE112098 validated 73-sample design": 73,
        "GSE186800 validated 20-sample recurrent-UTI design": 20,
        "GSE280297 validated 60-tissue-sample design": 60,
    },
    "S2": {
        "Frozen 78-submodule library": 78,
    },
    "S3": {
        "GSE112098 adjusted human comparator module effects": 20,
        "GSE280297 factorial and tissue-specific module effects": 810,
        "GSE186800 block and interaction module effects": 162,
        "GSE252321 sample-level UPEC-versus-control module effects": 20,
    },
    "S4": {
        "Evidence-class summary": 4,
        "Independent-dataset recurrence ranking": 78,
        "Evidence-weighted synthesis panel support": 60,
    },
    "S5": {
        "Tissue-resolved preterm-versus-term effects": 243,
        "Collapsed pregnancy-outcome effects": 81,
        "Full three-contrast tissue effect matrix": 81,
    },
    "S6": {
        "Flat-matrix and per-sample single-cell QC": 4,
        "Cluster top-marker table": 450,
        "Broad-cell sample composition": 32,
        "Refined-subtype sample composition": 72,
    },
    "S7": {
        "Broad-cell localization summary": 73,
        "Core-module cellular localization": 73,
        "Refined-subtype localization summary": 73,
    },
    "S8": {
        "Core complement and endocrine-metabolic cellular attribution": 10,
        "Module-level cellular synthesis across immune populations": 73,
    },
    "S9": {
        "Frozen Figure 1-8 asset manifest": 83,
        "Figure and panel title registry": 57,
        "Accession-corrected panel legend provenance registry": 57,
    },
    "S10": {
        "Accession-corrected caveat terminology registry": 8,
        "Cellular-localization claim-boundary matrix": 6,
        "Future accession validation rules": 2,
        "Accession correction and preservation traceability": 1,
    },
}

SOURCE_CRITICAL_COLUMNS = {
    "GSE252321 four-sample biological design": [
        "sample_id", "condition", "analysis_unit"
    ],
    "GSE112098 validated 73-sample design": [
        "sample_id", "sample_geo_accession", "organism_ch1"
    ],
    "GSE186800 validated 20-sample recurrent-UTI design": [
        "sample_id", "dataset_id", "inferred_group", "inferred_block"
    ],
    "GSE280297 validated 60-tissue-sample design": [
        "sample_id", "tissue", "treatment", "outcome", "pregnancy_status"
    ],
    "Frozen 78-submodule library": [
        "axis", "submodule_id", "display_label", "n_genes", "genes"
    ],
    "GSE112098 adjusted human comparator module effects": [
        "dataset_id", "contrast_name", "module_name", "direction"
    ],
    "GSE280297 factorial and tissue-specific module effects": [
        "contrast_id", "tissue", "feature_id", "direction"
    ],
    "GSE186800 block and interaction module effects": [
        "dataset", "contrast_id", "feature_id", "effect_value", "direction"
    ],
    "GSE252321 sample-level UPEC-versus-control module effects": [
        "dataset_id", "contrast_name", "module_name", "unit", "direction"
    ],
    "Independent-dataset recurrence ranking": [
        "feature_id", "n_independent_datasets",
        "weighted_directional_coherence", "validation_class"
    ],
    "Tissue-resolved preterm-versus-term effects": [
        "dataset", "tissue", "feature_id", "effect_value", "direction"
    ],
    "Collapsed pregnancy-outcome effects": [
        "dataset", "feature_id", "effect_value", "direction"
    ],
    "Full three-contrast tissue effect matrix": [
        "feature_id",
        "C1_PRETERM_VS_TERM | bladder",
        "C2_UPEC_VS_PBS_PREGNANCY | bladder",
        "C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder",
    ],
    "Flat-matrix and per-sample single-cell QC": [
        "sample_id", "condition", "n_cells", "adaptive_qc_pass_cells"
    ],
    "Cluster top-marker table": [
        "cluster", "rank", "gene_symbol"
    ],
    "Broad-cell sample composition": [
        "sample_id", "condition", "broad_cell_type",
        "n_cells", "fraction_of_QC_cells"
    ],
    "Refined-subtype sample composition": [
        "sample_id", "condition", "refined_cell_subtype",
        "n_cells", "fraction_of_QC_cells"
    ],
    "Broad-cell localization summary": [
        "feature_id", "n_complete_populations",
        "directional_coherence_fraction"
    ],
    "Core-module cellular localization": [
        "feature_id", "n_complete_populations",
        "directional_coherence_fraction"
    ],
    "Refined-subtype localization summary": [
        "feature_id", "n_complete_populations",
        "directional_coherence_fraction"
    ],
    "Core complement and endocrine-metabolic cellular attribution": [
        "feature_id", "top_population_by_composite_score",
        "cellular_localization_class"
    ],
    "Module-level cellular synthesis across immune populations": [
        "feature_id", "top_population_by_composite_score",
        "cellular_localization_class"
    ],
    "Frozen Figure 1-8 asset manifest": [
        "package_path", "checksum_match", "asset_type", "figure_number"
    ],
    "Figure and panel title registry": [
        "figure_number", "panel", "panel_title"
    ],
    "Accession-corrected panel legend provenance registry": [
        "figure_number", "panel", "definitive_panel_legend"
    ],
    "Accession-corrected caveat terminology registry": [
        "caveat_id", "required_statement"
    ],
    "Cellular-localization claim-boundary matrix": [
        "finding_type", "allowed_wording", "avoid_wording"
    ],
    "Future accession validation rules": [
        "rule_id", "term", "rule", "scientific_identity"
    ],
    "Accession correction and preservation traceability": [
        "source_unchanged", "results_wrong_accession_absent",
        "embedded_images_match_frozen_png_masters"
    ],
}

NUMERIC_PROBABILITY_COLUMNS = {
    "p_value",
    "fdr_bh",
    "q_value",
    "q_value_within_contrast",
    "best_tissue_q_value",
    "weighted_directional_coherence",
    "directional_coherence_fraction",
    "gene_direction_coherence",
    "median_gene_direction_coherence",
    "auc_group_a_higher",
    "fraction_of_QC_cells",
    "adaptive_qc_pass_fraction",
}

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def log(message: str) -> None:
    print(f"[U27B3E4] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep="\t",
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )


def blank_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().isin(["", "NA", "NaN", "nan", "None"])


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def read_docx_text(path: Path) -> str:
    if not path.exists():
        return ""

    pieces: List[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not (
                name == "word/document.xml"
                or re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
            ):
                continue
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError:
                continue
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] == "t" and node.text:
                    pieces.append(node.text)
    return "\n".join(pieces)


def find_manifest(package_root: Path, patterns: Sequence[str]) -> Optional[Path]:
    manifest_dir = package_root / "manifests"
    for pattern in patterns:
        matches = sorted(manifest_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def audit_row(
    category: str,
    table_id: str,
    audit_id: str,
    passed: bool,
    observed: object,
    expected: object,
    severity: str,
    note: str,
) -> Dict[str, object]:
    return {
        "category": category,
        "supplementary_table": table_id,
        "audit_id": audit_id,
        "pass": bool(passed),
        "observed": observed,
        "expected": expected,
        "severity": severity,
        "note": note,
    }


def parse_genes(value: str) -> List[str]:
    text = str(value).strip()
    if not text:
        return []
    if ";" in text:
        parts = text.split(";")
    elif "," in text:
        parts = text.split(",")
    elif "|" in text:
        parts = text.split("|")
    else:
        parts = re.split(r"\s+", text)
    return [part.strip() for part in parts if part.strip()]


def numeric_domain_rows(
    table_id: str,
    frame: pd.DataFrame,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    for column in frame.columns:
        lower = column.lower()
        if lower not in NUMERIC_PROBABILITY_COLUMNS:
            continue

        values = frame.loc[~blank_mask(frame[column]), column]
        numeric = pd.to_numeric(values, errors="coerce")
        nonnumeric = int(numeric.isna().sum())
        outside = int(((numeric < 0) | (numeric > 1)).fillna(False).sum())

        rows.append(
            {
                "supplementary_table": table_id,
                "column": column,
                "nonblank_values": len(values),
                "nonnumeric_values": nonnumeric,
                "outside_0_1_values": outside,
                "pass": nonnumeric == 0 and outside == 0,
            }
        )

    for column in frame.columns:
        lower = column.lower()
        if not (
            lower.startswith("n_")
            or lower.endswith("_count")
            or lower in {
                "n_cells", "adaptive_qc_pass_cells", "rank",
                "figure_number", "source_row_number"
            }
        ):
            continue

        values = frame.loc[~blank_mask(frame[column]), column]
        if values.empty:
            continue
        numeric = pd.to_numeric(values, errors="coerce")
        if numeric.notna().sum() == 0:
            continue
        nonnumeric = int(numeric.isna().sum())
        negative = int((numeric < 0).fillna(False).sum())

        rows.append(
            {
                "supplementary_table": table_id,
                "column": column,
                "nonblank_values": len(values),
                "nonnumeric_values": nonnumeric,
                "outside_0_1_values": negative,
                "pass": nonnumeric == 0 and negative == 0,
            }
        )

    return rows


def source_aware_missingness(
    table_id: str,
    frame: pd.DataFrame,
    source_manifest: pd.DataFrame,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    summary_rows: List[Dict[str, object]] = []
    critical_rows: List[Dict[str, object]] = []

    for role, block in frame.groupby("_source_role", sort=False):
        role = str(role)
        manifest_match = source_manifest[
            (source_manifest["supplementary_table"] == table_id)
            & (source_manifest["source_role"] == role)
        ]

        native_columns: List[str] = []
        if not manifest_match.empty and "source_columns" in manifest_match.columns:
            native_columns = [
                value.strip()
                for value in str(
                    manifest_match.iloc[0]["source_columns"]
                ).split(";")
                if value.strip()
            ]

        native_columns_present = [
            column for column in native_columns if column in frame.columns
        ]
        absent_native_columns = sorted(
            set(native_columns) - set(native_columns_present)
        )
        structural_columns = [
            column
            for column in frame.columns
            if column not in PROVENANCE_COLUMNS
            and column not in native_columns
        ]

        native_cells = len(block) * len(native_columns_present)
        native_blank_cells = sum(
            int(blank_mask(block[column]).sum())
            for column in native_columns_present
        )
        provenance_blank_cells = sum(
            int(blank_mask(block[column]).sum())
            for column in PROVENANCE_COLUMNS
            if column in block.columns
        )

        summary_rows.append(
            {
                "supplementary_table": table_id,
                "source_role": role,
                "rows": len(block),
                "native_source_columns": len(native_columns),
                "native_columns_present_in_union": len(native_columns_present),
                "native_columns_absent_from_union": len(absent_native_columns),
                "native_absent_column_names": "; ".join(absent_native_columns),
                "structural_union_only_columns": len(structural_columns),
                "native_source_cells": native_cells,
                "native_blank_cells": native_blank_cells,
                "native_blank_fraction": (
                    native_blank_cells / native_cells
                    if native_cells
                    else 0.0
                ),
                "provenance_blank_cells": provenance_blank_cells,
            }
        )

        required = SOURCE_CRITICAL_COLUMNS.get(role, [])
        for column in required:
            column_present = column in block.columns
            nonblank = (
                int((~blank_mask(block[column])).sum())
                if column_present
                else 0
            )
            critical_rows.append(
                {
                    "supplementary_table": table_id,
                    "source_role": role,
                    "critical_column": column,
                    "column_present": column_present,
                    "nonblank_rows": nonblank,
                    "total_rows": len(block),
                    "pass": column_present and nonblank == len(block),
                }
            )

    return summary_rows, critical_rows


def table_specific_audits(
    frames: Dict[str, pd.DataFrame],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    # S1
    s1 = frames["S1"]
    sample_ids = s1.loc[~blank_mask(s1["sample_id"]), "sample_id"]
    duplicate_count = int(
        s1.loc[~blank_mask(s1["sample_id"])]
        .duplicated(subset=["_source_role", "sample_id"])
        .sum()
    )
    rows.append(
        audit_row(
            "table_specific", "S1", "design_total_rows",
            len(s1) == 157, len(s1), 157, "BLOCKING",
            "Four frozen designs must contribute 4+73+20+60 rows."
        )
    )
    rows.append(
        audit_row(
            "table_specific", "S1", "sample_ids_unique_within_source",
            duplicate_count == 0, duplicate_count, 0, "BLOCKING",
            "Sample identifiers must be unique inside each dataset design."
        )
    )
    if "dam_id" in s1.columns:
        gse280 = s1[
            s1["_source_role"].str.contains("GSE280297", na=False)
        ]
        dam_nonblank = int((~blank_mask(gse280["dam_id"])).sum())
        rows.append(
            audit_row(
                "table_specific", "S1", "dam_identifier_boundary",
                dam_nonblank == 0, dam_nonblank, 0, "BLOCKING",
                "No dam-level identifier is available; tissue samples remain inferential units."
            )
        )

    # S2
    s2 = frames["S2"]
    unique_modules = s2["submodule_id"].nunique()
    unique_axes = s2["axis"].nunique()
    n_gene_mismatch = 0
    duplicate_gene_tokens = 0
    for _, row in s2.iterrows():
        genes = parse_genes(row.get("genes", ""))
        try:
            declared = int(float(row.get("n_genes", "0")))
        except ValueError:
            declared = -1
        if declared != len(genes):
            n_gene_mismatch += 1
        duplicate_gene_tokens += max(0, len(genes) - len(set(genes)))

    rows.extend(
        [
            audit_row(
                "table_specific", "S2", "unique_submodules",
                unique_modules == 78, unique_modules, 78, "BLOCKING",
                "The frozen library contains 78 unique submodules."
            ),
            audit_row(
                "table_specific", "S2", "unique_axes",
                unique_axes == 10, unique_axes, 10, "BLOCKING",
                "The frozen library contains ten biological axes."
            ),
            audit_row(
                "table_specific", "S2", "declared_gene_counts_match",
                n_gene_mismatch == 0, n_gene_mismatch, 0, "BLOCKING",
                "Each n_genes value should match the parsed gene list."
            ),
            audit_row(
                "table_specific", "S2", "duplicate_gene_tokens_within_module",
                duplicate_gene_tokens == 0, duplicate_gene_tokens, 0, "WARNING",
                "Duplicate tokens inside a module should be reviewed."
            ),
        ]
    )

    # S3
    s3 = frames["S3"]
    source_roles = set(s3["_source_role"].unique())
    rows.append(
        audit_row(
            "table_specific", "S3", "four_dataset_effect_sources",
            source_roles == set(EXPECTED_SOURCE_ROLE_ROWS["S3"]),
            "; ".join(sorted(source_roles)),
            "; ".join(sorted(EXPECTED_SOURCE_ROLE_ROWS["S3"])),
            "BLOCKING",
            "All four independently analyzed datasets must be represented."
        )
    )
    gse252 = s3[
        s3["_source_role"].str.contains("GSE252321", na=False)
    ]
    units = sorted(
        set(
            gse252.loc[~blank_mask(gse252["unit"]), "unit"]
            .astype(str)
            .str.lower()
            .tolist()
        )
    )
    rows.append(
        audit_row(
            "table_specific", "S3", "single_cell_biological_unit",
            units == ["sample"],
            "; ".join(units), "sample", "BLOCKING",
            "GSE252321 effects must use four biological samples, not cells."
        )
    )
    if {"n_group_a", "n_group_b"}.issubset(gse252.columns):
        n_a = pd.to_numeric(gse252["n_group_a"], errors="coerce")
        n_b = pd.to_numeric(gse252["n_group_b"], errors="coerce")
        group_sizes_pass = bool(
            (n_a == 2).all() and (n_b == 2).all()
        )
        rows.append(
            audit_row(
                "table_specific", "S3", "single_cell_group_sizes",
                group_sizes_pass,
                f"n_group_a={sorted(n_a.dropna().unique())}; "
                f"n_group_b={sorted(n_b.dropna().unique())}",
                "2 versus 2", "BLOCKING",
                "The sample-level contrast contains two controls and two UPEC samples."
            )
        )

    # S4
    s4 = frames["S4"]
    recurrence = s4[
        s4["_source_role"] == "Independent-dataset recurrence ranking"
    ]
    rows.append(
        audit_row(
            "table_specific", "S4", "recurrence_feature_rows",
            len(recurrence) == 78,
            len(recurrence), 78, "BLOCKING",
            "One recurrence record is expected per submodule."
        )
    )
    if "n_independent_datasets" in recurrence.columns:
        n_ds = pd.to_numeric(
            recurrence["n_independent_datasets"], errors="coerce"
        )
        pass_range = bool(
            n_ds.notna().all()
            and ((n_ds >= 1) & (n_ds <= 4)).all()
        )
        rows.append(
            audit_row(
                "table_specific", "S4", "independent_dataset_count_range",
                pass_range,
                f"min={n_ds.min()}; max={n_ds.max()}",
                "1-4", "BLOCKING",
                "Recurrence counts must refer to independently analyzed datasets."
            )
        )

    # S5
    s5 = frames["S5"]
    tissue = s5[
        s5["_source_role"] == "Tissue-resolved preterm-versus-term effects"
    ]
    tissues = sorted(
        set(tissue.loc[~blank_mask(tissue["tissue"]), "tissue"].str.lower())
    )
    rows.append(
        audit_row(
            "table_specific", "S5", "pregnancy_tissues",
            set(tissues) == {"bladder", "placenta", "uterus"},
            "; ".join(tissues),
            "bladder; placenta; uterus", "BLOCKING",
            "Pregnancy effects must retain all three tissues."
        )
    )
    matrix = s5[
        s5["_source_role"] == "Full three-contrast tissue effect matrix"
    ]
    contrast_columns = [
        column
        for column in matrix.columns
        if any(prefix in column for prefix in ("C1_", "C2_", "C3_"))
    ]
    rows.append(
        audit_row(
            "table_specific", "S5", "pregnancy_contrast_columns",
            len(contrast_columns) == 7,
            len(contrast_columns), 7, "BLOCKING",
            "The frozen matrix has three C1 tissues, three C2 tissues and one C3 bladder contrast."
        )
    )

    # S6
    s6 = frames["S6"]
    qc = s6[s6["_source_role"].str.startswith("Flat-matrix", na=False)]
    raw_cells = pd.to_numeric(qc["n_cells"], errors="coerce")
    qc_cells = pd.to_numeric(qc["adaptive_qc_pass_cells"], errors="coerce")
    rows.extend(
        [
            audit_row(
                "table_specific", "S6", "single_cell_raw_cell_total",
                int(raw_cells.sum()) == 28313,
                int(raw_cells.sum()), 28313, "BLOCKING",
                "The four flat matrices contain 28,313 cells."
            ),
            audit_row(
                "table_specific", "S6", "single_cell_qc_pass_total",
                int(qc_cells.sum()) == 27385,
                int(qc_cells.sum()), 27385, "BLOCKING",
                "A total of 27,385 cells passed QC."
            ),
        ]
    )
    markers = s6[s6["_source_role"] == "Cluster top-marker table"]
    cluster_count = markers["cluster"].nunique()
    marker_duplicate_count = int(
        markers.duplicated(subset=["cluster", "rank"]).sum()
    )
    rows.extend(
        [
            audit_row(
                "table_specific", "S6", "cluster_count",
                cluster_count == 18,
                cluster_count, 18, "BLOCKING",
                "Marker reconstruction resolved 18 clusters."
            ),
            audit_row(
                "table_specific", "S6", "cluster_rank_uniqueness",
                marker_duplicate_count == 0,
                marker_duplicate_count, 0, "BLOCKING",
                "Cluster-marker ranks must be unique inside each cluster."
            ),
        ]
    )
    for role, type_column in (
        ("Broad-cell sample composition", "broad_cell_type"),
        ("Refined-subtype sample composition", "refined_cell_subtype"),
    ):
        block = s6[s6["_source_role"] == role]
        sums = (
            block.groupby("sample_id")["fraction_of_QC_cells"]
            .apply(lambda s: pd.to_numeric(s, errors="coerce").sum())
        )
        max_deviation = float((sums - 1.0).abs().max()) if not sums.empty else math.inf
        rows.append(
            audit_row(
                "table_specific", "S6",
                f"{type_column}_fraction_sum_by_sample",
                max_deviation <= 0.001,
                max_deviation, "<=0.001", "BLOCKING",
                "Composition fractions should sum to one within each sample."
            )
        )

    # S7
    s7 = frames["S7"]
    for role in EXPECTED_SOURCE_ROLE_ROWS["S7"]:
        block = s7[s7["_source_role"] == role]
        unique_features = block["feature_id"].nunique()
        rows.append(
            audit_row(
                "table_specific", "S7",
                f"{role.lower().replace(' ', '_')}_feature_count",
                len(block) == 73 and unique_features == 73,
                f"rows={len(block)}; unique_features={unique_features}",
                "73 rows and 73 unique features", "BLOCKING",
                "Each localization summary should contain one row per score-eligible module."
            )
        )

    # S8
    s8 = frames["S8"]
    core = s8[
        s8["_source_role"].str.startswith("Core complement", na=False)
    ]
    synthesis = s8[
        s8["_source_role"].str.startswith("Module-level", na=False)
    ]
    rows.extend(
        [
            audit_row(
                "table_specific", "S8", "core_attribution_rows",
                len(core) == 10 and core["feature_id"].nunique() == 10,
                f"rows={len(core)}; features={core['feature_id'].nunique()}",
                "10", "BLOCKING",
                "Ten predefined core modules require cellular attribution."
            ),
            audit_row(
                "table_specific", "S8", "module_synthesis_rows",
                len(synthesis) == 73 and synthesis["feature_id"].nunique() == 73,
                f"rows={len(synthesis)}; features={synthesis['feature_id'].nunique()}",
                "73", "BLOCKING",
                "All 73 score-eligible modules require cellular synthesis."
            ),
        ]
    )

    # S9
    s9 = frames["S9"]
    asset = s9[
        s9["_source_role"] == "Frozen Figure 1-8 asset manifest"
    ]
    checksum_values = sorted(
        set(
            asset.loc[~blank_mask(asset["checksum_match"]), "checksum_match"]
            .str.lower()
        )
    )
    panel_title = s9[
        s9["_source_role"] == "Figure and panel title registry"
    ]
    legend = s9[
        s9["_source_role"] == "Accession-corrected panel legend provenance registry"
    ]
    rows.extend(
        [
            audit_row(
                "table_specific", "S9", "frozen_asset_checksums",
                checksum_values == ["true"],
                "; ".join(checksum_values), "true", "BLOCKING",
                "Frozen package assets must match their source checksums."
            ),
            audit_row(
                "table_specific", "S9", "panel_registry_counts",
                len(panel_title) == 57 and len(legend) == 57,
                f"titles={len(panel_title)}; legends={len(legend)}",
                "57 and 57", "BLOCKING",
                "All 57 panels require title and definitive-legend provenance."
            ),
            audit_row(
                "table_specific", "S9", "figures_1_to_8_present",
                set(panel_title["figure_number"]) == set(str(i) for i in range(1, 9)),
                "; ".join(sorted(set(panel_title["figure_number"]))),
                "1; 2; 3; 4; 5; 6; 7; 8", "BLOCKING",
                "The provenance registry must cover all eight main figures."
            ),
        ]
    )

    # S10
    s10 = frames["S10"]
    rules = s10[s10["_source_role"] == "Future accession validation rules"]
    prohibited = rules[
        (rules["term"] == WRONG_ACCESSION)
        & (rules["rule"].str.lower() == "prohibited")
    ]
    correct = rules[
        (rules["term"] == CORRECT_ACCESSION)
        & (rules["rule"].str.lower().isin(["required", "allowed", "canonical"]))
    ]
    rows.extend(
        [
            audit_row(
                "table_specific", "S10", "prohibited_skin_accession_rule",
                len(prohibited) == 1,
                len(prohibited), 1, "BLOCKING",
                "Exactly one semantic prohibition rule should document GSE168600."
            ),
            audit_row(
                "table_specific", "S10", "correct_recurrent_accession_rule",
                len(correct) == 1,
                len(correct), 1, "BLOCKING",
                "Exactly one canonical/required rule should document GSE186800."
            ),
        ]
    )

    return rows


def manuscript_consistency_audit(
    manuscript: Path,
) -> pd.DataFrame:
    text = read_docx_text(manuscript)
    normalized = normalized_text(text)
    rows: List[Dict[str, object]] = []

    for table_id, title in TABLE_TITLES.items():
        table_number = table_id[1:]
        number_patterns = [
            f"table s{table_number}",
            f"supplementary table s{table_number}",
        ]
        number_present = any(pattern in normalized for pattern in number_patterns)

        key_terms = [
            token.lower()
            for token in re.findall(r"[A-Za-z0-9/-]+", title)
            if len(token) >= 7
            and token.lower() not in {
                "supplementary", "organized", "specific", "results"
            }
        ][:5]
        key_hits = sum(term in normalized for term in key_terms)

        rows.append(
            {
                "supplementary_table": table_id,
                "manuscript_table_number_present": number_present,
                "title_anchor_terms": "; ".join(key_terms),
                "title_anchor_hits": key_hits,
                "title_anchor_expected_minimum": min(2, len(key_terms)),
                "title_consistency_pass": (
                    number_present
                    and key_hits >= min(2, len(key_terms))
                ),
            }
        )

    rows.append(
        {
            "supplementary_table": "ACCESSION",
            "manuscript_table_number_present": CORRECT_ACCESSION.lower() in normalized,
            "title_anchor_terms": CORRECT_ACCESSION,
            "title_anchor_hits": int(CORRECT_ACCESSION.lower() in normalized),
            "title_anchor_expected_minimum": 1,
            "title_consistency_pass": (
                CORRECT_ACCESSION.lower() in normalized
                and WRONG_ACCESSION.lower() not in normalized
            ),
        }
    )

    return pd.DataFrame(rows)


def zip_integrity_audit(
    package_root: Path,
    frames: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    zip_candidates = sorted(package_root.glob("*.zip"))
    if len(zip_candidates) != 1:
        return pd.DataFrame(
            [
                {
                    "zip_path": "; ".join(str(path) for path in zip_candidates),
                    "zip_exists_once": len(zip_candidates) == 1,
                    "zip_test_pass": False,
                    "materialized_table_members": 0,
                    "table_hash_matches": 0,
                    "expected_table_hash_matches": 10,
                    "pass": False,
                }
            ]
        )

    zip_path = zip_candidates[0]
    test_pass = False
    table_hash_matches = 0
    table_members = 0

    with zipfile.ZipFile(zip_path) as archive:
        test_pass = archive.testzip() is None
        names = set(archive.namelist())
        for table_id in TABLE_TITLES:
            member = (
                "materialized_tables/"
                f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
            )
            disk_path = (
                package_root
                / "materialized_tables"
                / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
            )
            if member in names:
                table_members += 1
                if (
                    sha256_bytes(archive.read(member))
                    == sha256(disk_path)
                ):
                    table_hash_matches += 1

    passed = (
        test_pass
        and table_members == 10
        and table_hash_matches == 10
    )

    return pd.DataFrame(
        [
            {
                "zip_path": str(zip_path),
                "zip_exists_once": True,
                "zip_test_pass": test_pass,
                "materialized_table_members": table_members,
                "table_hash_matches": table_hash_matches,
                "expected_table_hash_matches": 10,
                "pass": passed,
            }
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    parser.add_argument(
        "--package-root",
        default=DEFAULT_PACKAGE_ROOT,
    )
    parser.add_argument(
        "--manuscript",
        default=DEFAULT_MANUSCRIPT,
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    package_root = Path(args.package_root).resolve()
    manuscript = Path(args.manuscript).resolve()
    materialized_dir = package_root / "materialized_tables"

    if not package_root.exists():
        raise FileNotFoundError(f"Package root not found: {package_root}")
    if not manuscript.exists():
        raise FileNotFoundError(f"Manuscript not found: {manuscript}")

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    source_manifest_path = find_manifest(
        package_root,
        [
            "*source_manifest.tsv",
            "*U27B3E32_source_manifest.tsv",
        ],
    )
    if source_manifest_path is None:
        fallback = (
            project
            / "06_tables"
            / "phaseU27B3E32_repaired_supplementary_rematerialization"
            / "UTI_HostOmics_U27B3E32_source_manifest.tsv"
        )
        if fallback.exists():
            source_manifest_path = fallback
        else:
            raise FileNotFoundError("Source manifest could not be resolved.")

    source_manifest = read_tsv(source_manifest_path)

    frames: Dict[str, pd.DataFrame] = {}
    inventory_rows: List[Dict[str, object]] = []
    source_block_rows: List[Dict[str, object]] = []
    missingness_rows: List[Dict[str, object]] = []
    critical_rows: List[Dict[str, object]] = []
    numeric_rows: List[Dict[str, object]] = []
    general_audit_rows: List[Dict[str, object]] = []

    for table_id in TABLE_TITLES:
        path = (
            materialized_dir
            / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
        )
        exists = path.exists() and path.stat().st_size > 0
        frame = read_tsv(path) if exists else pd.DataFrame()
        frames[table_id] = frame

        inventory_rows.append(
            {
                "supplementary_table": table_id,
                "title": TABLE_TITLES[table_id],
                "path": str(path),
                "exists": exists,
                "sha256": sha256(path) if exists else "",
                "rows": len(frame),
                "columns": len(frame.columns),
                "provenance_columns_complete": (
                    set(PROVENANCE_COLUMNS).issubset(frame.columns)
                ),
            }
        )

        general_audit_rows.append(
            audit_row(
                "general", table_id, "file_exists_and_nonempty",
                exists and not frame.empty,
                f"exists={exists}; rows={len(frame)}",
                "existing nonempty TSV", "BLOCKING",
                "Every supplementary table must be present."
            )
        )
        general_audit_rows.append(
            audit_row(
                "general", table_id, "provenance_schema",
                set(PROVENANCE_COLUMNS).issubset(frame.columns),
                "; ".join(
                    column for column in PROVENANCE_COLUMNS
                    if column in frame.columns
                ),
                "; ".join(PROVENANCE_COLUMNS), "BLOCKING",
                "All rows must retain complete source provenance."
            )
        )

        if frame.empty:
            continue

        # Semantic accession handling.
        wrong_rows = frame[
            frame.apply(
                lambda row: any(
                    WRONG_ACCESSION.lower() in str(value).lower()
                    for value in row.values
                ),
                axis=1,
            )
        ]
        authorized_wrong = 0
        unauthorized_wrong = 0
        for _, row in wrong_rows.iterrows():
            authorized = (
                table_id == "S10"
                and str(row.get("rule_id", ""))
                == "prohibited_unrelated_skin_accession"
                and str(row.get("term", "")) == WRONG_ACCESSION
                and str(row.get("rule", "")).lower() == "prohibited"
            )
            if authorized:
                authorized_wrong += 1
            else:
                unauthorized_wrong += 1

        general_audit_rows.append(
            audit_row(
                "general", table_id, "semantic_accession_cleanliness",
                unauthorized_wrong == 0,
                f"authorized={authorized_wrong}; unauthorized={unauthorized_wrong}",
                "zero unauthorized GSE168600 use", "BLOCKING",
                "The sole allowed GSE168600 string is the explicit S10 prohibition rule."
            )
        )

        expected_roles = EXPECTED_SOURCE_ROLE_ROWS[table_id]
        observed_counts = (
            frame.groupby("_source_role")
            .size()
            .to_dict()
        )
        for role, expected_rows in expected_roles.items():
            observed = int(observed_counts.get(role, 0))
            source_block_rows.append(
                {
                    "supplementary_table": table_id,
                    "source_role": role,
                    "expected_rows": expected_rows,
                    "observed_rows": observed,
                    "pass": observed == expected_rows,
                }
            )

        unexpected_roles = sorted(
            set(observed_counts) - set(expected_roles)
        )
        general_audit_rows.append(
            audit_row(
                "general", table_id, "expected_source_roles_only",
                not unexpected_roles,
                "; ".join(unexpected_roles),
                "none", "BLOCKING",
                "No unplanned source blocks should appear in the controlled table."
            )
        )

        missingness, critical = source_aware_missingness(
            table_id,
            frame,
            source_manifest,
        )
        missingness_rows.extend(missingness)
        critical_rows.extend(critical)
        numeric_rows.extend(numeric_domain_rows(table_id, frame))

    table_specific_rows = table_specific_audits(frames)
    all_audit_rows = general_audit_rows + table_specific_rows

    inventory = pd.DataFrame(inventory_rows)
    source_blocks = pd.DataFrame(source_block_rows)
    missingness = pd.DataFrame(missingness_rows)
    critical = pd.DataFrame(critical_rows)
    numeric = pd.DataFrame(numeric_rows)
    audits = pd.DataFrame(all_audit_rows)
    manuscript_audit = manuscript_consistency_audit(manuscript)
    zip_audit = zip_integrity_audit(package_root, frames)

    # Convert source-block, critical, numeric, manuscript and ZIP checks into
    # the blocking decision matrix.
    derived_rows: List[Dict[str, object]] = []

    for _, row in source_blocks.iterrows():
        derived_rows.append(
            audit_row(
                "source_block",
                row["supplementary_table"],
                f"source_row_count::{row['source_role']}",
                bool(row["pass"]),
                row["observed_rows"],
                row["expected_rows"],
                "BLOCKING",
                "The row-preserving union must match the locked source row count."
            )
        )

    for _, row in critical.iterrows():
        derived_rows.append(
            audit_row(
                "critical_column",
                row["supplementary_table"],
                f"critical_nonmissing::{row['source_role']}::{row['critical_column']}",
                bool(row["pass"]),
                f"{row['nonblank_rows']}/{row['total_rows']}",
                f"{row['total_rows']}/{row['total_rows']}",
                "BLOCKING",
                "Critical identifiers and analysis fields must be complete inside their native source block."
            )
        )

    for _, row in numeric.iterrows():
        derived_rows.append(
            audit_row(
                "numeric_domain",
                row["supplementary_table"],
                f"numeric_domain::{row['column']}",
                bool(row["pass"]),
                (
                    f"nonnumeric={row['nonnumeric_values']}; "
                    f"outside_or_negative={row['outside_0_1_values']}"
                ),
                "0; 0",
                "BLOCKING",
                "Probability/coherence fields must lie in [0,1], and count fields must be nonnegative."
            )
        )

    for _, row in manuscript_audit.iterrows():
        derived_rows.append(
            audit_row(
                "manuscript_consistency",
                row["supplementary_table"],
                "supplementary_index_title_consistency",
                bool(row["title_consistency_pass"]),
                (
                    f"number_present={row['manuscript_table_number_present']}; "
                    f"anchor_hits={row['title_anchor_hits']}"
                ),
                (
                    f"table number present and >= "
                    f"{row['title_anchor_expected_minimum']} title-anchor hits"
                ),
                "BLOCKING",
                "The accession-corrected manuscript must index the same supplementary architecture."
            )
        )

    for _, row in zip_audit.iterrows():
        derived_rows.append(
            audit_row(
                "archive_integrity",
                "PACKAGE",
                "zip_member_and_hash_integrity",
                bool(row["pass"]),
                (
                    f"test={row['zip_test_pass']}; "
                    f"tables={row['materialized_table_members']}; "
                    f"hash_matches={row['table_hash_matches']}"
                ),
                "test=True; tables=10; hash_matches=10",
                "BLOCKING",
                "The controlled ZIP must contain byte-identical copies of all ten tables."
            )
        )

    audits = pd.concat(
        [audits, pd.DataFrame(derived_rows)],
        ignore_index=True,
        sort=False,
    )

    # Missingness warnings are source-aware and descriptive rather than
    # automatically blocking, except for critical columns already audited.
    warning_rows: List[Dict[str, object]] = []
    for _, row in missingness.iterrows():
        if float(row["native_blank_fraction"]) > 0:
            warning_rows.append(
                {
                    "supplementary_table": row["supplementary_table"],
                    "source_role": row["source_role"],
                    "warning_type": "NATIVE_SOURCE_MISSINGNESS",
                    "value": row["native_blank_fraction"],
                    "note": (
                        "Native-source blanks are reported for review. "
                        "They are not structural union-schema blanks and are "
                        "not blocking unless a critical field is affected."
                    ),
                }
            )

    warnings = pd.DataFrame(warning_rows)

    inventory.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_table_inventory.tsv",
        sep="\t", index=False
    )
    source_blocks.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_source_block_row_audit.tsv",
        sep="\t", index=False
    )
    missingness.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_source_aware_missingness_summary.tsv",
        sep="\t", index=False
    )
    critical.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_critical_column_audit.tsv",
        sep="\t", index=False
    )
    numeric.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_numeric_domain_audit.tsv",
        sep="\t", index=False
    )
    audits.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_complete_audit_matrix.tsv",
        sep="\t", index=False
    )
    manuscript_audit.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_manuscript_consistency_audit.tsv",
        sep="\t", index=False
    )
    zip_audit.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_zip_integrity_audit.tsv",
        sep="\t", index=False
    )
    warnings.to_csv(
        outtables / "UTI_HostOmics_U27B3E4_warning_register.tsv",
        sep="\t", index=False
    )

    blocking = audits[audits["severity"] == "BLOCKING"]
    blocking_failures = blocking[~blocking["pass"]]
    warning_failures = audits[
        (audits["severity"] == "WARNING") & (~audits["pass"])
    ]

    if blocking_failures.empty:
        decision = (
            "READY_FOR_U27B3E5_SUPPLEMENTARY_TABLE_"
            "SUBMISSION_FORMATTING_AND_FREEZE"
        )
    else:
        decision = (
            "TARGETED_U27B3E4_SUPPLEMENTARY_SCHEMA_OR_CONTENT_REPAIR_REQUIRED"
        )

    pd.DataFrame(
        [
            {
                "phase": "U27B3E4",
                "decision": decision,
                "supplementary_tables_audited": 10,
                "audit_checks": len(audits),
                "audit_checks_passed": int(audits["pass"].sum()),
                "blocking_checks": len(blocking),
                "blocking_checks_passed": int(blocking["pass"].sum()),
                "blocking_failures": len(blocking_failures),
                "warning_checks_failed": len(warning_failures),
                "source_aware_missingness_warning_rows": len(warnings),
                "zip_integrity_pass": bool(zip_audit.iloc[0]["pass"]),
                "manuscript_consistency_pass": bool(
                    manuscript_audit["title_consistency_pass"].all()
                ),
                "scientific_values_recalculated": False,
                "materialized_tables_modified": False,
                "source_files_modified": False,
                "manuscript_modified": False,
                "next_phase": (
                    "U27B3E5 create submission-facing supplementary workbooks "
                    "and freeze the validated supplementary package"
                    if decision.startswith("READY_FOR_U27B3E5")
                    else "Inspect failed U27B3E4 blocking audits"
                ),
            }
        ]
    ).to_csv(
        outtables / "UTI_HostOmics_U27B3E4_phase_decision.tsv",
        sep="\t", index=False
    )

    failed_path = (
        outtables
        / "UTI_HostOmics_U27B3E4_failed_blocking_audits.tsv"
    )
    blocking_failures.to_csv(failed_path, sep="\t", index=False)

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3E4_supplementary_schema_content_audit_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3E4 - Supplementary schema and content audit\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(f"- Package: `{package_root}`\n")
        handle.write(f"- Manuscript: `{manuscript}`\n")
        handle.write(
            f"- Audit checks passed: "
            f"**{int(audits['pass'].sum())}/{len(audits)}**.\n"
        )
        handle.write(
            f"- Blocking checks passed: "
            f"**{int(blocking['pass'].sum())}/{len(blocking)}**.\n"
        )
        handle.write(
            f"- Blocking failures: **{len(blocking_failures)}**.\n"
        )
        handle.write(
            f"- Source-aware missingness warning rows: "
            f"**{len(warnings)}**.\n"
        )
        handle.write(
            f"- ZIP integrity: **{bool(zip_audit.iloc[0]['pass'])}**.\n"
        )
        handle.write(
            "- Scientific values recalculated: **False**.\n"
        )
        handle.write(
            "- Materialized tables modified: **False**.\n\n"
        )

        handle.write("## Missingness interpretation\n\n")
        handle.write(
            "The S1-S10 files use union schemas because each supplementary "
            "table combines heterogeneous source tables. Columns belonging to "
            "other source blocks are therefore structurally blank and are not "
            "treated as missing data. This audit evaluates completeness inside "
            "each source's native schema and applies blocking checks only to "
            "critical identifiers and analysis fields.\n\n"
        )

        handle.write("## Biological-replicate and accession boundaries\n\n")
        handle.write(
            "GSE252321 dataset-level contrasts remain sample-based at n=2 "
            "controls versus n=2 UPEC samples. Cells are not treated as "
            "independent biological replicates. GSE186800 remains the canonical "
            "recurrent-UTI accession. The sole GSE168600 string is retained only "
            "as the explicit S10 prohibition rule identifying the unrelated "
            "KLF5 skin/sphingolipid dataset.\n\n"
        )

        if not blocking_failures.empty:
            handle.write("## Blocking failures\n\n")
            for _, row in blocking_failures.iterrows():
                handle.write(
                    f"- **{row['supplementary_table']} / "
                    f"{row['audit_id']}**: observed `{row['observed']}`; "
                    f"expected `{row['expected']}`. {row['note']}\n"
                )
        else:
            handle.write("## Release\n\n")
            handle.write(
                "All blocking schema, content, accession, manuscript-index and "
                "archive-integrity checks passed. The package is released for "
                "submission-facing spreadsheet formatting and final freeze.\n"
            )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "package_root": str(package_root),
        "package_sha256": (
            sha256(next(package_root.glob("*.zip")))
            if len(list(package_root.glob("*.zip"))) == 1
            else ""
        ),
        "manuscript": str(manuscript),
        "manuscript_sha256": sha256(manuscript),
        "checks": len(audits),
        "checks_passed": int(audits["pass"].sum()),
        "blocking_checks": len(blocking),
        "blocking_failures": len(blocking_failures),
        "warnings": len(warnings),
        "scientific_values_recalculated": False,
        "materialized_tables_modified": False,
        "source_files_modified": False,
        "manuscript_modified": False,
    }
    (
        outresults / "UTI_HostOmics_U27B3E4_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log(
        f"Audit checks passed: "
        f"{int(audits['pass'].sum())}/{len(audits)}"
    )
    log(
        f"Blocking checks passed: "
        f"{int(blocking['pass'].sum())}/{len(blocking)}"
    )
    log(f"Blocking failures: {len(blocking_failures)}")
    log(f"Missingness warnings: {len(warnings)}")
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E4] ERROR: {exc}", file=sys.stderr)
        raise
