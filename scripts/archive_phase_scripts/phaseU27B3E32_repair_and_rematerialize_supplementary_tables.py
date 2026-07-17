#!/usr/bin/env python3
"""
Phase U27B3E3.2
Repair the supplementary source map and rematerialize Supplementary Tables
S1-S10 as a controlled, accession-clean package.

Key repairs
-----------
S1
  Add the validated 60-sample GSE280297 design. The repaired S1 therefore
  contains the four frozen datasets: GSE112098, GSE280297, GSE186800 and
  GSE252321.

S3
  Replace the incomplete three-source map with one biological-replicate or
  dataset-level effect source for each frozen dataset:
  - GSE112098 adjusted human comparator effects
  - GSE280297 all factorial/tissue contrast results
  - GSE186800 block/interaction effects
  - GSE252321 sample-level UPEC-versus-control effects
  Cell-level contrast rows are deliberately not used as independent
  biological-replicate evidence.

S6
  Use explicit QC, cluster-marker, broad-composition and refined-subtype
  composition sources.

S8
  Remove the unsupported JSON run manifest and administrative phase-decision
  row. Use biological cellular-attribution and module-synthesis tables only.

S9
  Replace the superseded U27B3B panel provenance registry with the
  accession-corrected U27B3E22 registry.

S10
  Replace accession-contaminated historical audit sources with the corrected
  caveat registry, claim-boundary matrix, accession-validation rules and
  preservation/accession audit.

Package-control repair
----------------------
The original U27B3E3 run failed while constructing the ZIP because it called
Path.relative_to() on manifest files outside the supplementary directory. This
phase stages every package artifact inside one package root and archives only
paths relative to that root.

Integrity boundary
------------------
No module score, effect estimate, FDR, cell count, source matrix, manuscript,
figure or historical artifact is modified. Materialization is a row-preserving
union with explicit source provenance. The original U27B3E3 ZIP remains
diagnostic and untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import pandas as pd


VERSION = "U27B3E32_v1.0_2026-07-16"
TAG = "phaseU27B3E32_repaired_supplementary_rematerialization"

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


def log(message: str) -> None:
    print(f"[U27B3E3.2] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def read_tabular(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        separator = "\t"
    elif suffix == ".csv":
        separator = ","
    else:
        raise ValueError(f"Unsupported tabular source: {path}")

    return pd.read_csv(
        path,
        sep=separator,
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )


def all_text(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    return "\n".join(
        frame.astype(str).fillna("").to_numpy().ravel().tolist()
    )


def safe_relative(path: Path, project: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve()))
    except ValueError:
        return str(path.resolve())


def source_entry(
    project: Path,
    relative_path: str,
    role: str,
    status: str,
) -> Dict[str, str]:
    return {
        "path": str((project / relative_path).resolve()),
        "relative_path": relative_path,
        "role": role,
        "status": status,
    }


def build_source_map(project: Path) -> Dict[str, List[Dict[str, str]]]:
    return {
        "S1": [
            source_entry(
                project,
                "03_metadata/phaseU26B2A1_cross_dataset_input_repair/"
                "GSE252321_U26B2A1_sample_level_pseudobulk_design.tsv",
                "GSE252321 four-sample biological design",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "03_metadata/phaseU26B2A1_cross_dataset_input_repair/"
                "GSE112098_U26B2A1_validated_sample_design.tsv",
                "GSE112098 validated 73-sample design",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "03_metadata/phaseU26B2A1_cross_dataset_input_repair/"
                "GSE186800_U26B2A1_validated_sample_design.tsv",
                "GSE186800 validated 20-sample recurrent-UTI design",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "03_metadata/phaseU26A5_GSE280297_final_input_resolution/"
                "GSE280297_U26A5_validated_60sample_design.tsv",
                "GSE280297 validated 60-tissue-sample design",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S2": [
            source_entry(
                project,
                "03_metadata/"
                "phaseU26A_expanded_endocrine_metabolic_immune_feasibility/"
                "UTI_HostOmics_U26A_expanded_submodule_library.tsv",
                "Frozen 78-submodule library",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S3": [
            source_entry(
                project,
                "07_tables/phaseU6_human_urine_comparator/"
                "phaseU6_GSE112098_human_urine_module_contrast_v1.tsv",
                "GSE112098 adjusted human comparator module effects",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26B1_GSE280297_endocrine_metabolic_immune_scoring/"
                "UTI_HostOmics_U26B1_all_contrast_results.tsv",
                "GSE280297 factorial and tissue-specific module effects",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26B2B1_independent_dataset_evidence_collapse/"
                "UTI_HostOmics_U26B2B1_GSE186800_block_interaction_effects.tsv",
                "GSE186800 block and interaction module effects",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "07_tables/phaseU8b_single_cell_module_scoring/"
                "phaseU8b_GSE252321_sample_level_UPEC_vs_Control_"
                "module_contrast_v1.tsv",
                "GSE252321 sample-level UPEC-versus-control module effects",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S4": [
            source_entry(
                project,
                "06_tables/"
                "phaseU26B2B1_independent_dataset_evidence_collapse/"
                "UTI_HostOmics_U26B2B1_validation_class_summary.tsv",
                "Evidence-class summary",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26B2B1_independent_dataset_evidence_collapse/"
                "UTI_HostOmics_U26B2B1_"
                "independent_dataset_recurrence_ranking.tsv",
                "Independent-dataset recurrence ranking",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26C_biological_synthesis_figure_architecture/"
                "UTI_HostOmics_U26C_Figure_9_panel_evidence.tsv",
                "Evidence-weighted synthesis panel support",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S5": [
            source_entry(
                project,
                "06_tables/"
                "phaseU26B2B1_independent_dataset_evidence_collapse/"
                "UTI_HostOmics_U26B2B1_"
                "GSE280297_preterm_term_tissue_effects.tsv",
                "Tissue-resolved preterm-versus-term effects",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26B2B1_independent_dataset_evidence_collapse/"
                "UTI_HostOmics_U26B2B1_"
                "GSE280297_preterm_term_collapsed.tsv",
                "Collapsed pregnancy-outcome effects",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU27B2C2A_GSE280297_full_effect_source_repair/"
                "UTI_HostOmics_U27B2C2A_"
                "GSE280297_full_tissue_effect_matrix.tsv",
                "Full three-contrast tissue effect matrix",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S6": [
            source_entry(
                project,
                "06_tables/"
                "phaseU26D1A_GSE252321_flat_matrix_validation/"
                "UTI_HostOmics_U26D1A_flat_matrix_QC.tsv",
                "Flat-matrix and per-sample single-cell QC",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26D2A_GSE252321_marker_celltype_reconstruction/"
                "UTI_HostOmics_U26D2A_cluster_top_markers.tsv",
                "Cluster top-marker table",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26D2A_GSE252321_marker_celltype_reconstruction/"
                "UTI_HostOmics_U26D2A_sample_celltype_composition.tsv",
                "Broad-cell sample composition",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26D2A1_GSE252321_annotation_refinement/"
                "UTI_HostOmics_U26D2A1_sample_subtype_composition.tsv",
                "Refined-subtype sample composition",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S7": [
            source_entry(
                project,
                "06_tables/"
                "phaseU26D2B_GSE252321_refined_celltype_pseudobulk/"
                "UTI_HostOmics_U26D2B_broad_cellular_localization.tsv",
                "Broad-cell localization summary",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26D2B_GSE252321_refined_celltype_pseudobulk/"
                "UTI_HostOmics_U26D2B_"
                "core_module_cellular_localization.tsv",
                "Core-module cellular localization",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26D2B_GSE252321_refined_celltype_pseudobulk/"
                "UTI_HostOmics_U26D2B_subtype_cellular_localization.tsv",
                "Refined-subtype localization summary",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S8": [
            source_entry(
                project,
                "06_tables/"
                "phaseU26D2C_cellular_localization_synthesis/"
                "UTI_HostOmics_U26D2C_"
                "core_module_cellular_attribution.tsv",
                "Core complement and endocrine-metabolic cellular attribution",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU26D2C_cellular_localization_synthesis/"
                "UTI_HostOmics_U26D2C_module_cellular_synthesis.tsv",
                "Module-level cellular synthesis across immune populations",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S9": [
            source_entry(
                project,
                "03_metadata/"
                "phaseU27B3A_complete_eight_figure_package_assembly/"
                "UTI_HostOmics_U27B3A_complete_asset_manifest.tsv",
                "Frozen Figure 1-8 asset manifest",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "03_metadata/"
                "phaseU27B3A_complete_eight_figure_package_assembly/"
                "UTI_HostOmics_U27B3A_figure_and_panel_title_registry.tsv",
                "Figure and panel title registry",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "03_metadata/"
                "phaseU27B3E22_targeted_accession_correction/"
                "UTI_HostOmics_U27B3E22_"
                "panel_legend_provenance_registry.tsv",
                "Accession-corrected panel legend provenance registry",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
        "S10": [
            source_entry(
                project,
                "03_metadata/"
                "phaseU27B3E22_targeted_accession_correction/"
                "UTI_HostOmics_U27B3E22_caveat_terminology_registry.tsv",
                "Accession-corrected caveat terminology registry",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "03_metadata/"
                "phaseU26D2C_cellular_localization_synthesis/"
                "UTI_HostOmics_U26D2C_claim_boundary_matrix.tsv",
                "Cellular-localization claim-boundary matrix",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "03_metadata/"
                "phaseU27B3E22_targeted_accession_correction/"
                "UTI_HostOmics_U27B3E22_accession_validation_rules.tsv",
                "Future accession validation rules",
                "LOCKED_HIGH_CONFIDENCE",
            ),
            source_entry(
                project,
                "06_tables/"
                "phaseU27B3E22_targeted_accession_correction/"
                "UTI_HostOmics_U27B3E22_"
                "preservation_and_accession_audit.tsv",
                "Accession correction and preservation traceability",
                "LOCKED_HIGH_CONFIDENCE",
            ),
        ],
    }


def materialize_table(
    table_id: str,
    title: str,
    sources: Sequence[Dict[str, str]],
    project: Path,
    output_path: Path,
) -> Tuple[pd.DataFrame, List[Dict[str, object]], List[Dict[str, object]]]:
    pieces: List[pd.DataFrame] = []
    manifest_rows: List[Dict[str, object]] = []
    source_lock_rows: List[Dict[str, object]] = []

    for source_order, source in enumerate(sources, start=1):
        path = Path(source["path"])
        exists = path.exists() and path.stat().st_size > 0
        supported = path.suffix.lower() in {".tsv", ".csv"}

        if not exists:
            raise FileNotFoundError(
                f"{table_id} source does not exist: {path}"
            )
        if not supported:
            raise ValueError(
                f"{table_id} source is not TSV/CSV: {path}"
            )

        frame = read_tabular(path)
        if frame.empty:
            raise RuntimeError(
                f"{table_id} source is empty: {path}"
            )

        original_columns = list(frame.columns)
        frame.insert(0, "_source_row_number", range(1, len(frame) + 1))
        frame.insert(0, "_source_sha256", sha256(path))
        frame.insert(0, "_source_relative_path", safe_relative(path, project))
        frame.insert(0, "_source_file", str(path))
        frame.insert(0, "_source_role", source["role"])
        frame.insert(0, "_source_order", source_order)
        frame.insert(0, "_table_title", title)
        frame.insert(0, "_supplementary_table", table_id)
        pieces.append(frame)

        manifest_rows.append(
            {
                "supplementary_table": table_id,
                "table_title": title,
                "source_order": source_order,
                "source_role": source["role"],
                "source_status": source["status"],
                "source_path": str(path),
                "source_relative_path": safe_relative(path, project),
                "source_exists": True,
                "source_supported_tabular_format": True,
                "source_sha256": sha256(path),
                "source_size_bytes": path.stat().st_size,
                "source_rows": len(frame),
                "source_column_count": len(original_columns),
                "source_columns": "; ".join(original_columns),
                "source_read_status": "READY",
            }
        )

        source_lock_rows.append(
            {
                "supplementary_table": table_id,
                "table_title": title,
                "source_sequence": source_order,
                "source_role": source["role"],
                "source_path": str(path),
                "source_relative_path": safe_relative(path, project),
                "source_status": source["status"],
                "assembly_mode": "ROW_PRESERVING_UNION_WITH_PROVENANCE",
                "selection_rationale": source["role"],
                "final_user_confirmation_required": False,
            }
        )

    materialized = pd.concat(
        pieces,
        ignore_index=True,
        sort=False,
    )

    ordered_columns = PROVENANCE_COLUMNS + [
        column
        for column in materialized.columns
        if column not in PROVENANCE_COLUMNS
    ]
    materialized = materialized[ordered_columns]
    materialized.to_csv(
        output_path,
        sep="\t",
        index=False,
    )

    return materialized, manifest_rows, source_lock_rows


def table_source_accessions(frame: pd.DataFrame) -> List[str]:
    if "_source_file" not in frame.columns:
        return []
    text = "\n".join(frame["_source_file"].astype(str).tolist())
    return sorted(
        accession
        for accession in (
            "GSE112098",
            "GSE280297",
            "GSE186800",
            "GSE252321",
        )
        if accession.lower() in text.lower()
    )


def build_content_audit(
    frames: Dict[str, pd.DataFrame],
    source_map: Dict[str, List[Dict[str, str]]],
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []

    for table_id, frame in frames.items():
        text = all_text(frame)
        rows.append(
            {
                "supplementary_table": table_id,
                "audit_id": "nonempty_materialized_table",
                "pass": not frame.empty,
                "observed": len(frame),
                "expected": "> 0 rows",
            }
        )
        rows.append(
            {
                "supplementary_table": table_id,
                "audit_id": "provenance_columns_complete",
                "pass": set(PROVENANCE_COLUMNS).issubset(frame.columns),
                "observed": "; ".join(
                    column
                    for column in PROVENANCE_COLUMNS
                    if column in frame.columns
                ),
                "expected": "; ".join(PROVENANCE_COLUMNS),
            }
        )
        wrong_count = len(
            re.findall(
                re.escape(WRONG_ACCESSION),
                text,
                flags=re.IGNORECASE,
            )
        )
        rows.append(
            {
                "supplementary_table": table_id,
                "audit_id": "wrong_accession_absent",
                "pass": wrong_count == 0,
                "observed": wrong_count,
                "expected": 0,
            }
        )

    s1 = frames["S1"]
    s1_accessions = table_source_accessions(s1)
    s1_source_counts = (
        s1.groupby("_source_role", dropna=False)
        .size()
        .to_dict()
    )
    rows.append(
        {
            "supplementary_table": "S1",
            "audit_id": "four_dataset_design_sources",
            "pass": set(s1_accessions) == {
                "GSE112098",
                "GSE280297",
                "GSE186800",
                "GSE252321",
            },
            "observed": "; ".join(s1_accessions),
            "expected": "GSE112098; GSE280297; GSE186800; GSE252321",
        }
    )
    rows.append(
        {
            "supplementary_table": "S1",
            "audit_id": "expected_total_design_rows",
            "pass": len(s1) == 157,
            "observed": len(s1),
            "expected": 157,
        }
    )

    s2 = frames["S2"]
    rows.append(
        {
            "supplementary_table": "S2",
            "audit_id": "submodule_count",
            "pass": (
                "submodule_id" in s2.columns
                and s2["submodule_id"].nunique() == 78
            ),
            "observed": (
                s2["submodule_id"].nunique()
                if "submodule_id" in s2.columns
                else 0
            ),
            "expected": 78,
        }
    )
    rows.append(
        {
            "supplementary_table": "S2",
            "audit_id": "axis_count",
            "pass": (
                "axis" in s2.columns
                and s2["axis"].nunique() == 10
            ),
            "observed": (
                s2["axis"].nunique()
                if "axis" in s2.columns
                else 0
            ),
            "expected": 10,
        }
    )

    s3_accessions = table_source_accessions(frames["S3"])
    rows.append(
        {
            "supplementary_table": "S3",
            "audit_id": "four_dataset_effect_families",
            "pass": set(s3_accessions) == {
                "GSE112098",
                "GSE280297",
                "GSE186800",
                "GSE252321",
            },
            "observed": "; ".join(s3_accessions),
            "expected": "GSE112098; GSE280297; GSE186800; GSE252321",
        }
    )

    s6_roles = "\n".join(
        frames["S6"]["_source_role"].astype(str).drop_duplicates().tolist()
    ).lower()
    rows.append(
        {
            "supplementary_table": "S6",
            "audit_id": "qc_marker_broad_and_refined_coverage",
            "pass": all(
                token in s6_roles
                for token in ("qc", "marker", "broad", "refined")
            ),
            "observed": s6_roles,
            "expected": "QC; marker; broad composition; refined subtype composition",
        }
    )

    s8_paths = "\n".join(
        frames["S8"]["_source_file"].astype(str).drop_duplicates().tolist()
    ).lower()
    rows.append(
        {
            "supplementary_table": "S8",
            "audit_id": "biological_tabular_sources_only",
            "pass": (
                "run_manifest.json" not in s8_paths
                and "phase_decision.tsv" not in s8_paths
                and "cellular_attribution" in s8_paths
                and "module_cellular_synthesis" in s8_paths
            ),
            "observed": s8_paths,
            "expected": (
                "core_module_cellular_attribution.tsv and "
                "module_cellular_synthesis.tsv only"
            ),
        }
    )

    s9_paths = "\n".join(
        frames["S9"]["_source_file"].astype(str).drop_duplicates().tolist()
    )
    rows.append(
        {
            "supplementary_table": "S9",
            "audit_id": "accession_corrected_panel_registry",
            "pass": (
                "phaseU27B3E22_targeted_accession_correction"
                in s9_paths
                and "phaseU27B3B_definitive_figure_legend_construction/"
                "UTI_HostOmics_U27B3B_panel_legend_provenance_registry.tsv"
                not in s9_paths
            ),
            "observed": s9_paths,
            "expected": "U27B3E22 corrected panel provenance registry",
        }
    )

    s10_text = all_text(frames["S10"])
    rows.append(
        {
            "supplementary_table": "S10",
            "audit_id": "corrected_interpretation_traceability_sources",
            "pass": (
                WRONG_ACCESSION.lower() not in s10_text.lower()
                and "accession_validation_rules" in "\n".join(
                    frames["S10"]["_source_file"].astype(str).tolist()
                )
                and "claim_boundary_matrix" in "\n".join(
                    frames["S10"]["_source_file"].astype(str).tolist()
                )
            ),
            "observed": "; ".join(
                frames["S10"]["_source_role"]
                .astype(str)
                .drop_duplicates()
                .tolist()
            ),
            "expected": (
                "corrected caveats; claim boundary; accession rules; "
                "preservation traceability"
            ),
        }
    )

    return pd.DataFrame(rows)


def write_schema_registry(
    frames: Dict[str, pd.DataFrame],
    path: Path,
) -> None:
    rows: List[Dict[str, object]] = []
    for table_id in sorted(frames, key=lambda value: int(value[1:])):
        frame = frames[table_id]
        for position, column in enumerate(frame.columns, start=1):
            rows.append(
                {
                    "supplementary_table": table_id,
                    "column_position": position,
                    "column_name": column,
                    "column_origin": (
                        "provenance"
                        if column in PROVENANCE_COLUMNS
                        else "source_union"
                    ),
                }
            )
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)


def make_zip(package_root: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(package_root.rglob("*")):
            if not path.is_file():
                continue
            if path.resolve() == zip_path.resolve():
                continue
            archive.write(
                path,
                arcname=str(path.relative_to(package_root)),
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    if not project.exists():
        raise FileNotFoundError(f"Project root not found: {project}")

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG
    package_root = project / "11_supplementary" / TAG
    materialized_dir = package_root / "materialized_tables"
    manifest_dir = package_root / "manifests"

    for directory in (
        outtables,
        outmetadata,
        outresults,
        materialized_dir,
        manifest_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    source_map = build_source_map(project)

    frames: Dict[str, pd.DataFrame] = {}
    manifest_rows: List[Dict[str, object]] = []
    source_lock_rows: List[Dict[str, object]] = []
    summary_rows: List[Dict[str, object]] = []

    for table_number in range(1, 11):
        table_id = f"S{table_number}"
        title = TABLE_TITLES[table_id]
        output_path = (
            materialized_dir
            / f"UTI_HostOmics_Supplementary_Table_{table_id}.tsv"
        )

        frame, table_manifest, table_locks = materialize_table(
            table_id=table_id,
            title=title,
            sources=source_map[table_id],
            project=project,
            output_path=output_path,
        )
        frames[table_id] = frame
        manifest_rows.extend(table_manifest)
        source_lock_rows.extend(table_locks)

        summary_rows.append(
            {
                "supplementary_table": table_id,
                "table_title": title,
                "source_map_rows": len(source_map[table_id]),
                "unique_source_files": len(
                    frame["_source_file"].drop_duplicates()
                ),
                "materialized_output": str(output_path),
                "output_exists": output_path.exists(),
                "output_sha256": sha256(output_path),
                "materialized_rows": len(frame),
                "materialized_columns": len(frame.columns),
                "materialization_status": "MATERIALIZED",
            }
        )
        log(
            f"{table_id}: rows={len(frame)}, "
            f"columns={len(frame.columns)}, "
            f"sources={len(source_map[table_id])}"
        )

    summary = pd.DataFrame(summary_rows)
    manifest = pd.DataFrame(manifest_rows)
    source_lock = pd.DataFrame(source_lock_rows)

    summary_path = (
        outtables
        / "UTI_HostOmics_U27B3E32_materialization_summary.tsv"
    )
    manifest_path = (
        outtables
        / "UTI_HostOmics_U27B3E32_source_manifest.tsv"
    )
    source_lock_path = (
        outmetadata
        / "UTI_HostOmics_U27B3E32_corrected_source_lock_map.tsv"
    )
    schema_path = (
        outtables
        / "UTI_HostOmics_U27B3E32_materialized_schema_registry.tsv"
    )
    content_audit_path = (
        outtables
        / "UTI_HostOmics_U27B3E32_schema_content_accession_audit.tsv"
    )
    unclassified_path = (
        outtables
        / "UTI_HostOmics_U27B3E32_unclassified_source_map_rows.tsv"
    )

    summary.to_csv(summary_path, sep="\t", index=False)
    manifest.to_csv(manifest_path, sep="\t", index=False)
    source_lock.to_csv(source_lock_path, sep="\t", index=False)
    write_schema_registry(frames, schema_path)

    content_audit = build_content_audit(frames, source_map)
    content_audit.to_csv(
        content_audit_path,
        sep="\t",
        index=False,
    )

    pd.DataFrame(
        columns=[
            "supplementary_table",
            "source_role",
            "source_path",
            "reason",
        ]
    ).to_csv(
        unclassified_path,
        sep="\t",
        index=False,
    )

    all_sources_exist = bool(manifest["source_exists"].all())
    all_sources_supported = bool(
        manifest["source_supported_tabular_format"].all()
    )
    all_materialized = bool(
        len(summary) == 10
        and summary["output_exists"].all()
        and (summary["materialized_rows"].astype(int) > 0).all()
    )
    content_pass = bool(content_audit["pass"].all())
    wrong_accession_total = sum(
        len(
            re.findall(
                re.escape(WRONG_ACCESSION),
                all_text(frame),
                flags=re.IGNORECASE,
            )
        )
        for frame in frames.values()
    )

    diagnostic_zip = (
        project
        / "11_supplementary"
        / "phaseU27B3E3_supplementary_table_materialization"
        / "UTI_HostOmics_U27B3E3_Supplementary_Tables_S1-S10.zip"
    )

    readme_path = (
        package_root
        / "UTI_HostOmics_U27B3E32_supplementary_package_README.md"
    )
    with readme_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# UTI HostOmics Supplementary Tables S1-S10\n\n"
        )
        handle.write(f"- Phase: `{VERSION}`\n")
        handle.write(
            f"- Correct recurrent-UTI accession: **{CORRECT_ACCESSION}**\n"
        )
        handle.write(
            f"- Wrong accession occurrences: **{wrong_accession_total}**\n"
        )
        handle.write("- Scientific values recalculated: **No**\n")
        handle.write("- Historical sources overwritten: **No**\n")
        handle.write(
            f"- Successfully materialized tables: "
            f"**{int(summary['output_exists'].sum())}/10**\n\n"
        )
        handle.write("## Provenance model\n\n")
        handle.write(
            "Every row carries the supplementary-table ID, source role, "
            "source file, source-relative path, SHA256 checksum and source-row "
            "number. Composite tables use a union schema and preserve source "
            "values exactly as stored.\n\n"
        )
        handle.write("## Biological-replicate boundary\n\n")
        handle.write(
            "GSE252321 dataset-level effects in S3 are derived from the "
            "four-sample sample-level contrast. Cell-level contrasts are not "
            "presented as independent biological-replicate evidence.\n\n"
        )
        handle.write("## Materialized tables\n\n")
        for _, row in summary.iterrows():
            handle.write(
                f"- **{row['supplementary_table']}**: "
                f"{row['table_title']} "
                f"(rows={row['materialized_rows']}; "
                f"sources={row['unique_source_files']}).\n"
            )
        handle.write("\n## Superseded diagnostic package\n\n")
        handle.write(
            f"The earlier U27B3E3 ZIP remains a diagnostic artifact and is "
            f"not submission-approved: `{diagnostic_zip}`.\n"
        )

    # Stage manifests before control files.
    staged_files = [
        summary_path,
        manifest_path,
        source_lock_path,
        schema_path,
        content_audit_path,
        unclassified_path,
    ]
    for path in staged_files:
        shutil.copy2(path, manifest_dir / path.name)

    if (
        all_sources_exist
        and all_sources_supported
        and all_materialized
        and content_pass
        and wrong_accession_total == 0
    ):
        decision = (
            "READY_FOR_U27B3E4_SUPPLEMENTARY_TABLE_SCHEMA_AND_CONTENT_AUDIT"
        )
    else:
        decision = (
            "TARGETED_U27B3E32_SUPPLEMENTARY_REMATERIALIZATION_REPAIR_REQUIRED"
        )

    decision_path = (
        outtables
        / "UTI_HostOmics_U27B3E32_phase_decision.tsv"
    )
    report_path = (
        outresults
        / "UTI_HostOmics_U27B3E32_repaired_materialization_report.md"
    )

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B3E3.2",
                "decision": decision,
                "supplementary_tables_expected": 10,
                "supplementary_tables_materialized": len(summary),
                "supplementary_tables_failed_or_empty": int(
                    (~summary["output_exists"]).sum()
                    + (summary["materialized_rows"].astype(int) == 0).sum()
                ),
                "all_sources_exist": all_sources_exist,
                "all_sources_supported_tabular_format": (
                    all_sources_supported
                ),
                "schema_content_accession_audits": len(content_audit),
                "schema_content_accession_audits_passed": int(
                    content_audit["pass"].sum()
                ),
                "wrong_accession_occurrences": wrong_accession_total,
                "unclassified_source_map_rows": 0,
                "package_zip_created": False,
                "scientific_values_recalculated": False,
                "source_files_modified": False,
                "historical_artifacts_overwritten": False,
                "diagnostic_U27B3E3_zip_preserved": diagnostic_zip.exists(),
                "next_phase": (
                    "U27B3E4 perform table-by-table schema, content, "
                    "missingness and manuscript-consistency audit"
                    if decision.startswith("READY_FOR_U27B3E4")
                    else "Inspect failed U27B3E32 audits"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        decision_path,
        sep="\t",
        index=False,
    )

    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3E3.2 - Repaired supplementary rematerialization\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Tables materialized: **{len(summary)}/10**.\n"
        )
        handle.write(
            f"- Sources: **{len(manifest)}**, all existing: "
            f"**{all_sources_exist}**.\n"
        )
        handle.write(
            f"- Supported tabular sources only: "
            f"**{all_sources_supported}**.\n"
        )
        handle.write(
            f"- Schema/content/accession audits passed: "
            f"**{int(content_audit['pass'].sum())}/"
            f"{len(content_audit)}**.\n"
        )
        handle.write(
            f"- GSE168600 occurrences: **{wrong_accession_total}**.\n"
        )
        handle.write(
            "- Scientific values recalculated: **False**.\n"
        )
        handle.write(
            "- Historical artifacts overwritten: **False**.\n\n"
        )
        handle.write("## Targeted repairs\n\n")
        handle.write(
            "- S1 now includes the validated 60-sample GSE280297 design.\n"
        )
        handle.write(
            "- S3 now includes dataset-level effects from all four frozen "
            "datasets and uses GSE252321 sample-level rather than cell-level "
            "biological inference.\n"
        )
        handle.write(
            "- S6 now contains explicit QC, marker, broad-composition and "
            "refined-subtype composition sources.\n"
        )
        handle.write(
            "- S8 contains biological cellular-attribution tables only.\n"
        )
        handle.write(
            "- S9 uses the U27B3E22 accession-corrected panel provenance "
            "registry.\n"
        )
        handle.write(
            "- S10 uses accession-clean interpretation-boundary and "
            "traceability sources.\n\n"
        )
        handle.write("## ZIP construction repair\n\n")
        handle.write(
            "All package files are staged under one supplementary package "
            "root before archiving. This removes the cross-directory "
            "`Path.relative_to()` failure from U27B3E3.\n"
        )

    shutil.copy2(decision_path, manifest_dir / decision_path.name)
    shutil.copy2(report_path, manifest_dir / report_path.name)

    zip_path = (
        package_root
        / "UTI_HostOmics_U27B3E32_Supplementary_Tables_S1-S10.zip"
    )
    make_zip(package_root, zip_path)

    zip_created = zip_path.exists() and zip_path.stat().st_size > 0
    decision_frame.loc[0, "package_zip_created"] = zip_created

    if not zip_created:
        decision = (
            "TARGETED_U27B3E32_SUPPLEMENTARY_ZIP_CONSTRUCTION_REPAIR_REQUIRED"
        )
        decision_frame.loc[0, "decision"] = decision
        decision_frame.loc[0, "next_phase"] = (
            "Inspect ZIP construction and package-root staging"
        )

    decision_frame.to_csv(
        decision_path,
        sep="\t",
        index=False,
    )
    shutil.copy2(decision_path, manifest_dir / decision_path.name)

    # Rebuild ZIP once so it includes the final decision.
    make_zip(package_root, zip_path)
    zip_created = zip_path.exists() and zip_path.stat().st_size > 0

    zip_audit_path = (
        outtables
        / "UTI_HostOmics_U27B3E32_package_zip_audit.tsv"
    )
    pd.DataFrame(
        [
            {
                "zip_path": str(zip_path),
                "zip_exists": zip_created,
                "zip_size_bytes": (
                    zip_path.stat().st_size if zip_created else 0
                ),
                "zip_sha256": sha256(zip_path) if zip_created else "",
                "package_root": str(package_root),
                "materialized_table_files": len(
                    list(materialized_dir.glob("*.tsv"))
                ),
                "manifest_files": len(
                    list(manifest_dir.glob("*"))
                ),
            }
        ]
    ).to_csv(
        zip_audit_path,
        sep="\t",
        index=False,
    )

    manifest_json = {
        "version": VERSION,
        "decision": decision_frame.loc[0, "decision"],
        "tables_materialized": len(summary),
        "sources": len(manifest),
        "content_audits": len(content_audit),
        "content_audits_passed": int(content_audit["pass"].sum()),
        "wrong_accession_occurrences": wrong_accession_total,
        "zip_path": str(zip_path),
        "zip_created": zip_created,
        "zip_sha256": sha256(zip_path) if zip_created else "",
        "scientific_values_recalculated": False,
        "source_files_modified": False,
        "historical_artifacts_overwritten": False,
    }
    (
        outresults
        / "UTI_HostOmics_U27B3E32_run_manifest.json"
    ).write_text(
        json.dumps(manifest_json, indent=2),
        encoding="utf-8",
    )

    log(f"Sources: {len(manifest)}")
    log(
        "Content audits passed: "
        f"{int(content_audit['pass'].sum())}/{len(content_audit)}"
    )
    log(f"Wrong accession occurrences: {wrong_accession_total}")
    log(f"ZIP created: {zip_created}")
    log(f"Decision: {decision_frame.loc[0, 'decision']}")
    log(f"ZIP: {zip_path}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E3.2] ERROR: {exc}", file=sys.stderr)
        raise
