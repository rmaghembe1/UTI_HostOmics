#!/usr/bin/env python3
"""
Phase U26D2A.1
Biological refinement of GSE252321 cluster annotations and targeted states.

Corrections
-----------
1. Refine clusters using their top-marker identities rather than only the
   original broad panel winner.
2. Reassign macrophage-like cluster 6, inflammatory-monocyte cluster 1,
   activated dendritic cluster 7 and cycling cluster 11.
3. Retain broad cell classes for later pseudobulk while adding defensible
   biological subtypes.
4. Replace per-sample top-20% Treg and CD137L definitions, which force nearly
   identical fractions in every sample, with fixed marker logic:
   - strict and expanded Treg-like candidates from FOXP3, IL2RA, CTLA4 and
     TNFRSF18 expression;
   - TNFSF9-positive macrophages and a pooled fixed TNFSF9-high threshold.
5. Produce corrected sample composition and readiness outputs.

Biological samples remain the inferential units. This phase performs no
cell-level significance testing and modifies neither the manuscript nor
existing Figures 1-6.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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


VERSION = "U26D2A1_v1.0_2026-07-14"
TAG = "phaseU26D2A1_GSE252321_annotation_refinement"
SOURCE_TAG = "phaseU26D2A_GSE252321_marker_celltype_reconstruction"
MATRIX_TAG = "phaseU26D1A_GSE252321_flat_matrix_validation"


CLUSTER_REFINEMENT: Dict[int, Tuple[str, str, str]] = {
    0: (
        "NK_cell",
        "cytotoxic_NK",
        "CCL5/NKG7/GZMA/GZMB/KLRD1/NCR1",
    ),
    1: (
        "macrophage_monocyte",
        "LY6C2_VCAN_inflammatory_monocyte",
        "LY6C2/CHIL3/VCAN/FCGR1/CCL2",
    ),
    2: (
        "mast_cell",
        "CMA1_CPA3_mast",
        "CMA1/CPA3/TPSB2/MCPT4/KIT",
    ),
    3: (
        "neutrophil",
        "IL1B_CXCL2_inflammatory_neutrophil",
        "IL1B/CXCL2/S100A9/CSF3R/MMP9",
    ),
    4: (
        "macrophage_monocyte",
        "ARG1_SPP1_inflammatory_macrophage",
        "ARG1/FN1/SPP1/CCL2/CD14/C3AR1",
    ),
    5: (
        "T_cell",
        "conventional_activated_T",
        "TRAC/CD3D/CD3E/CD3G/LCK",
    ),
    6: (
        "macrophage_monocyte",
        "RETNLA_MRC1_reparative_macrophage",
        "RETNLA/LPL/MRC1/C1QA-C/LYZ1",
    ),
    7: (
        "dendritic",
        "CD83_CLEC10A_activated_dendritic",
        "CD83/CLEC10A/CD209A/CCR7/H2-DMB2",
    ),
    8: (
        "NK_cell",
        "GZMA_GZMB_cytotoxic_NK",
        "NKG7/GZMA/GZMB/PRF1/NCR1/EOMES",
    ),
    9: (
        "neutrophil",
        "S100A8_S100A9_neutrophil",
        "S100A8/S100A9/CXCR2/CSF3R/RETNLG",
    ),
    10: (
        "T_cell",
        "IL2RA_TNFRSF18_regulatory_type2_like_T",
        "IL2RA/TNFRSF18/GATA3/RORA/IL1RL1/KLRG1",
    ),
    11: (
        "cycling_immune",
        "MKI67_TOP2A_cycling_immune",
        "MKI67/TOP2A/PCLAF/UBE2C/BIRC5",
    ),
    12: (
        "macrophage_monocyte",
        "C1Q_APOE_resident_macrophage",
        "APOE/C1QA-C/ADGRE1/MRC1/CX3CR1",
    ),
    13: (
        "dendritic",
        "CD209A_CLEC10A_cDC2_like",
        "CD209A/CLEC10A/MGL2/FLT3",
    ),
    14: (
        "NK_cell",
        "cycling_NK",
        "NKG7/GZMA/NCR1 plus MKI67/TOP2A",
    ),
    15: (
        "macrophage_monocyte",
        "PF4_MRC1_C1Q_macrophage",
        "PF4/MRC1/C1QA-C/ADGRE1/CCL2",
    ),
    16: (
        "T_cell",
        "gamma_delta_like_T",
        "TCRG-C1/TRDC/TRDV4/CXCR6/CD3E",
    ),
    17: (
        "dendritic",
        "XCR1_CLEC9A_cDC1_like",
        "XCR1/CLEC9A/TLR3/IRF8/FLT3/CADM1",
    ),
}

TARGET_GENES = [
    "FOXP3",
    "IL2RA",
    "CTLA4",
    "TNFRSF18",
    "IKZF2",
    "TNFSF9",
    "ADGRE1",
    "LYZ2",
    "CSF1R",
    "CD68",
]


def log(message: str) -> None:
    print(f"[U26D2A.1] {message}", flush=True)


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", compression="infer", low_memory=False)


def normalize_gene(value: object) -> str:
    return str(value).strip().upper()


def log_normalized_gene_values(
    matrix: sparse.csr_matrix,
    gene_indices: Dict[str, int],
    target_sum: float = 10000.0,
) -> pd.DataFrame:
    totals = np.asarray(matrix.sum(axis=1)).ravel().astype(np.float64)
    factors = np.divide(
        target_sum,
        totals,
        out=np.zeros_like(totals),
        where=totals > 0,
    )

    output = {}
    for gene, index in gene_indices.items():
        raw = np.asarray(matrix[:, index].toarray()).ravel().astype(np.float64)
        output[gene] = np.log1p(raw * factors)

    return pd.DataFrame(output)


def load_target_expression(
    manifest_row: pd.Series,
    annotation_sample: pd.DataFrame,
) -> pd.DataFrame:
    matrix = sparse.load_npz(
        Path(str(manifest_row["sparse_matrix_path"]))
    ).tocsr()
    genes = read_tsv(Path(str(manifest_row["genes_path"])))
    cells = read_tsv(Path(str(manifest_row["cell_metadata_path"])))

    if matrix.shape[0] != len(cells):
        raise RuntimeError(
            f"Matrix/cell mismatch for {manifest_row['sample_id']}"
        )

    qc_mask = (
        cells["adaptive_qc_pass"]
        .astype(str)
        .str.lower()
        .isin(["true", "1"])
        .to_numpy()
    )
    matrix = matrix[qc_mask].tocsr()
    cells = cells.loc[qc_mask].reset_index(drop=True)

    if len(cells) != len(annotation_sample):
        raise RuntimeError(
            f"QC cell count differs from annotations for "
            f"{manifest_row['sample_id']}: {len(cells)} vs "
            f"{len(annotation_sample)}"
        )

    if not cells["cell_id"].astype(str).equals(
        annotation_sample["cell_id"].astype(str).reset_index(drop=True)
    ):
        position = pd.Series(
            np.arange(len(cells)),
            index=cells["cell_id"].astype(str),
        )
        requested = annotation_sample["cell_id"].astype(str)
        if not requested.isin(position.index).all():
            raise RuntimeError(
                f"Cell IDs cannot be aligned for {manifest_row['sample_id']}"
            )
        reorder = position.loc[requested].to_numpy(dtype=int)
        matrix = matrix[reorder].tocsr()
        cells = cells.iloc[reorder].reset_index(drop=True)

    gene_lookup: Dict[str, int] = {}
    for index, gene in enumerate(genes["gene_symbol"].map(normalize_gene)):
        if gene and gene not in gene_lookup:
            gene_lookup[gene] = index

    detected = {
        gene: gene_lookup[gene]
        for gene in TARGET_GENES
        if gene in gene_lookup
    }
    missing = sorted(set(TARGET_GENES) - set(detected))
    if missing:
        log(
            f"{manifest_row['sample_id']}: missing targeted genes "
            + ",".join(missing)
        )

    expression = log_normalized_gene_values(matrix, detected)
    for gene in missing:
        expression[gene] = 0.0

    return expression[TARGET_GENES]


def plot_composition(composition: pd.DataFrame, output: Path) -> None:
    pivot = composition.pivot(
        index="sample_id",
        columns="refined_broad_cell_type",
        values="fraction_of_QC_cells",
    ).fillna(0.0)

    figure = plt.figure(figsize=(12, 6))
    axis = figure.add_axes([0.10, 0.24, 0.70, 0.66])
    pivot.plot(kind="bar", stacked=True, ax=axis)
    axis.set_ylabel("Fraction of QC-passing cells")
    axis.set_xlabel("Biological sample")
    axis.set_title("Refined GSE252321 broad cell-type composition")
    axis.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        fontsize=7,
    )
    figure.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(figure)


def plot_targeted_summary(summary: pd.DataFrame, output: Path) -> None:
    plot_frame = summary[
        summary["targeted_measure"].isin(
            [
                "strict_Treg_like_fraction_within_T",
                "expanded_Treg_like_fraction_within_T",
                "TNFSF9_positive_fraction_within_macrophage",
                "TNFSF9_high_fraction_within_macrophage",
            ]
        )
    ].copy()

    pivot = plot_frame.pivot(
        index="sample_id",
        columns="targeted_measure",
        values="value",
    ).fillna(0.0)

    figure = plt.figure(figsize=(11, 6))
    axis = figure.add_axes([0.10, 0.25, 0.70, 0.65])
    pivot.plot(kind="bar", ax=axis)
    axis.set_ylabel("Fraction within parent population")
    axis.set_xlabel("Biological sample")
    axis.set_title("Fixed-definition targeted immune populations")
    axis.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        fontsize=7,
    )
    figure.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    annotations_path = (
        project / "03_metadata" / SOURCE_TAG
        / "UTI_HostOmics_U26D2A_all_QC_cell_annotations.tsv.gz"
    )
    cluster_path = (
        project / "06_tables" / SOURCE_TAG
        / "UTI_HostOmics_U26D2A_cluster_annotations.tsv"
    )
    marker_path = (
        project / "06_tables" / SOURCE_TAG
        / "UTI_HostOmics_U26D2A_cluster_top_markers.tsv"
    )
    manifest_path = (
        project / "03_metadata" / MATRIX_TAG
        / "UTI_HostOmics_U26D1A_sparse_matrix_manifest.tsv"
    )

    for path in [
        annotations_path,
        cluster_path,
        marker_path,
        manifest_path,
    ]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    out_metadata = project / "03_metadata" / TAG
    out_tables = project / "06_tables" / TAG
    out_results = project / "05_results" / TAG
    out_figures = project / "06_figures" / TAG
    for directory in [
        out_metadata,
        out_tables,
        out_results,
        out_figures,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    log("Loading U26D2A cell annotations.")
    annotations = read_tsv(annotations_path)
    original_clusters = read_tsv(cluster_path)
    top_markers = read_tsv(marker_path)
    manifest = read_tsv(manifest_path)

    missing_clusters = sorted(
        set(annotations["cluster"].astype(int).unique())
        - set(CLUSTER_REFINEMENT)
    )
    if missing_clusters:
        raise RuntimeError(
            f"Refinement dictionary missing clusters: {missing_clusters}"
        )

    refinement_rows = []
    for cluster, (broad, subtype, evidence) in CLUSTER_REFINEMENT.items():
        original = original_clusters[
            original_clusters["cluster"].astype(int) == cluster
        ]
        original_label = (
            str(original.iloc[0]["broad_cell_type"])
            if not original.empty
            else ""
        )
        original_confidence = (
            str(original.iloc[0]["annotation_confidence"])
            if not original.empty
            else ""
        )
        marker_preview = ";".join(
            top_markers[
                top_markers["cluster"].astype(int) == cluster
            ]
            .sort_values("rank")
            .head(10)["gene_symbol"]
            .astype(str)
        )
        refinement_rows.append(
            {
                "cluster": cluster,
                "original_broad_cell_type": original_label,
                "original_annotation_confidence": original_confidence,
                "refined_broad_cell_type": broad,
                "refined_cell_subtype": subtype,
                "refinement_evidence": evidence,
                "top_10_markers": marker_preview,
                "label_changed": original_label != broad,
            }
        )

    refinement = pd.DataFrame(refinement_rows).sort_values("cluster")
    refinement.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2A1_cluster_annotation_refinement.tsv",
        sep="\t",
        index=False,
    )

    broad_lookup = dict(
        zip(
            refinement["cluster"].astype(int),
            refinement["refined_broad_cell_type"],
        )
    )
    subtype_lookup = dict(
        zip(
            refinement["cluster"].astype(int),
            refinement["refined_cell_subtype"],
        )
    )

    annotations["refined_broad_cell_type"] = annotations[
        "cluster"
    ].astype(int).map(broad_lookup)
    annotations["refined_cell_subtype"] = annotations[
        "cluster"
    ].astype(int).map(subtype_lookup)

    expression_frames = []
    for _, manifest_row in manifest.iterrows():
        sample_id = str(manifest_row["sample_id"])
        sample_annotations = (
            annotations[
                annotations["sample_id"].astype(str) == sample_id
            ]
            .copy()
            .reset_index(drop=True)
        )
        log(
            f"Extracting fixed targeted markers for {sample_id} "
            f"({len(sample_annotations)} QC cells)."
        )
        expression = load_target_expression(
            manifest_row,
            sample_annotations,
        )
        expression["cell_id"] = sample_annotations["cell_id"].astype(str)
        expression_frames.append(expression)

    targeted_expression = pd.concat(
        expression_frames,
        ignore_index=True,
    )
    targeted_expression = targeted_expression.set_index("cell_id")
    annotation_ids = annotations["cell_id"].astype(str)

    if not annotation_ids.isin(targeted_expression.index).all():
        raise RuntimeError("Targeted expression is missing annotated cells.")

    aligned = targeted_expression.loc[annotation_ids].reset_index()
    for gene in TARGET_GENES:
        annotations[f"{gene}_log_normalized"] = aligned[gene].to_numpy()

    is_t = annotations["refined_broad_cell_type"] == "T_cell"
    support_count = (
        (annotations["IL2RA_log_normalized"] > 0).astype(int)
        + (annotations["CTLA4_log_normalized"] > 0).astype(int)
        + (annotations["TNFRSF18_log_normalized"] > 0).astype(int)
    )
    annotations["strict_Treg_like_candidate"] = (
        is_t
        & (annotations["FOXP3_log_normalized"] > 0)
        & (support_count >= 1)
    )
    annotations["expanded_Treg_like_candidate"] = (
        is_t
        & (
            (annotations["FOXP3_log_normalized"] > 0)
            | (support_count >= 2)
        )
    )

    is_macrophage = (
        annotations["refined_broad_cell_type"]
        == "macrophage_monocyte"
    )
    annotations["TNFSF9_positive_macrophage"] = (
        is_macrophage
        & (annotations["TNFSF9_log_normalized"] > 0)
    )

    positive_values = annotations.loc[
        annotations["TNFSF9_positive_macrophage"],
        "TNFSF9_log_normalized",
    ].to_numpy(dtype=float)
    if len(positive_values) >= 20:
        tnfsf9_high_threshold = float(
            np.quantile(positive_values, 0.75)
        )
    elif len(positive_values):
        tnfsf9_high_threshold = float(np.median(positive_values))
    else:
        tnfsf9_high_threshold = np.inf

    annotations["TNFSF9_high_macrophage"] = (
        is_macrophage
        & (
            annotations["TNFSF9_log_normalized"]
            > tnfsf9_high_threshold
        )
    )

    annotations.to_csv(
        out_metadata
        / "UTI_HostOmics_U26D2A1_refined_all_QC_cell_annotations.tsv.gz",
        sep="\t",
        index=False,
        compression="gzip",
    )

    composition_rows = []
    subtype_rows = []
    targeted_rows = []

    for sample_id, sample_frame in annotations.groupby(
        "sample_id",
        sort=False,
    ):
        condition = str(sample_frame["condition"].iloc[0])
        n_total = len(sample_frame)

        for cell_type, frame in sample_frame.groupby(
            "refined_broad_cell_type"
        ):
            composition_rows.append(
                {
                    "sample_id": sample_id,
                    "condition": condition,
                    "refined_broad_cell_type": cell_type,
                    "n_cells": len(frame),
                    "fraction_of_QC_cells": len(frame) / n_total,
                }
            )

        for subtype, frame in sample_frame.groupby(
            "refined_cell_subtype"
        ):
            subtype_rows.append(
                {
                    "sample_id": sample_id,
                    "condition": condition,
                    "refined_cell_subtype": subtype,
                    "n_cells": len(frame),
                    "fraction_of_QC_cells": len(frame) / n_total,
                }
            )

        t_cells = sample_frame[is_t.loc[sample_frame.index]]
        macrophages = sample_frame[
            is_macrophage.loc[sample_frame.index]
        ]

        strict_treg = int(
            sample_frame["strict_Treg_like_candidate"].sum()
        )
        expanded_treg = int(
            sample_frame["expanded_Treg_like_candidate"].sum()
        )
        tnfsf9_positive = int(
            sample_frame["TNFSF9_positive_macrophage"].sum()
        )
        tnfsf9_high = int(
            sample_frame["TNFSF9_high_macrophage"].sum()
        )

        measures = [
            (
                "strict_Treg_like_fraction_within_T",
                strict_treg,
                len(t_cells),
            ),
            (
                "expanded_Treg_like_fraction_within_T",
                expanded_treg,
                len(t_cells),
            ),
            (
                "TNFSF9_positive_fraction_within_macrophage",
                tnfsf9_positive,
                len(macrophages),
            ),
            (
                "TNFSF9_high_fraction_within_macrophage",
                tnfsf9_high,
                len(macrophages),
            ),
        ]

        for measure, numerator, denominator in measures:
            targeted_rows.append(
                {
                    "sample_id": sample_id,
                    "condition": condition,
                    "targeted_measure": measure,
                    "numerator_cells": numerator,
                    "parent_cells": denominator,
                    "value": (
                        numerator / denominator
                        if denominator > 0
                        else np.nan
                    ),
                    "definition": (
                        "FOXP3 positive plus >=1 of IL2RA/CTLA4/TNFRSF18"
                        if measure.startswith("strict_Treg")
                        else "FOXP3 positive or >=2 of IL2RA/CTLA4/TNFRSF18"
                        if measure.startswith("expanded_Treg")
                        else "TNFSF9 detectable in refined macrophage/monocyte"
                        if measure.startswith("TNFSF9_positive")
                        else (
                            "TNFSF9 above pooled positive-cell 75th "
                            f"percentile ({tnfsf9_high_threshold:.6f})"
                        )
                    ),
                }
            )

    composition = pd.DataFrame(composition_rows)
    subtypes = pd.DataFrame(subtype_rows)
    targeted_summary = pd.DataFrame(targeted_rows)

    composition.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2A1_refined_sample_celltype_composition.tsv",
        sep="\t",
        index=False,
    )
    subtypes.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2A1_sample_subtype_composition.tsv",
        sep="\t",
        index=False,
    )
    targeted_summary.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2A1_fixed_targeted_population_summary.tsv",
        sep="\t",
        index=False,
    )

    threshold_table = pd.DataFrame(
        [
            {
                "target": "TNFSF9_high_macrophage",
                "threshold_source": (
                    "pooled TNFSF9-positive macrophages across all samples"
                ),
                "quantile": 0.75,
                "log_normalized_threshold": tnfsf9_high_threshold,
                "sample_specific_threshold": False,
            }
        ]
    )
    threshold_table.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2A1_fixed_thresholds.tsv",
        sep="\t",
        index=False,
    )

    presence = (
        composition.assign(
            present=composition["n_cells"] >= 30
        )
        .pivot_table(
            index="refined_broad_cell_type",
            columns="sample_id",
            values="present",
            aggfunc="max",
            fill_value=False,
        )
    )
    presence.to_csv(
        out_tables
        / "UTI_HostOmics_U26D2A1_refined_celltype_sample_presence.tsv",
        sep="\t",
    )

    plot_composition(
        composition,
        out_figures
        / "UTI_HostOmics_U26D2A1_refined_celltype_composition.png",
    )
    plot_targeted_summary(
        targeted_summary,
        out_figures
        / "UTI_HostOmics_U26D2A1_fixed_targeted_populations.png",
    )

    required_types = [
        "macrophage_monocyte",
        "dendritic",
        "neutrophil",
        "T_cell",
        "NK_cell",
    ]
    required_all_samples = {
        cell_type: bool(
            cell_type in presence.index
            and int(presence.loc[cell_type].sum()) == 4
        )
        for cell_type in required_types
    }

    n_types_all_samples = int(
        (presence.sum(axis=1) == 4).sum()
    )
    changed_clusters = int(refinement["label_changed"].sum())

    if (
        all(required_all_samples.values())
        and n_types_all_samples >= 5
        and np.isfinite(tnfsf9_high_threshold)
    ):
        decision = (
            "READY_FOR_U26D2B_REFINED_CELLTYPE_PSEUDOBULK_SCORING"
        )
    else:
        decision = "TARGETED_REFINED_ANNOTATION_REVIEW_REQUIRED"

    pd.DataFrame(
        [
            {
                "phase": "U26D2A.1",
                "decision": decision,
                "n_QC_cells": len(annotations),
                "n_clusters_refined": len(refinement),
                "n_clusters_with_changed_broad_label": changed_clusters,
                "n_refined_broad_cell_types": (
                    annotations["refined_broad_cell_type"].nunique()
                ),
                "n_refined_subtypes": (
                    annotations["refined_cell_subtype"].nunique()
                ),
                "n_broad_types_with_at_least_30_cells_in_all_samples": (
                    n_types_all_samples
                ),
                "macrophage_all_samples": required_all_samples[
                    "macrophage_monocyte"
                ],
                "dendritic_all_samples": required_all_samples[
                    "dendritic"
                ],
                "neutrophil_all_samples": required_all_samples[
                    "neutrophil"
                ],
                "T_cell_all_samples": required_all_samples["T_cell"],
                "NK_cell_all_samples": required_all_samples["NK_cell"],
                "per_sample_quantile_targeted_definitions_retired": True,
                "TNFSF9_high_fixed_global_threshold": (
                    tnfsf9_high_threshold
                ),
                "biological_sample_is_inferential_unit": True,
                "cell_level_significance_testing_performed": False,
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U26D2B refined sample-by-cell-type pseudobulk module "
                    "scoring"
                    if decision
                    == "READY_FOR_U26D2B_REFINED_CELLTYPE_PSEUDOBULK_SCORING"
                    else "Review refined cluster mapping and targeted states"
                ),
            }
        ]
    ).to_csv(
        out_tables / "UTI_HostOmics_U26D2A1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U26D2A1_annotation_refinement_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U26D2A.1 - GSE252321 annotation refinement\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- QC-passing cells retained: **{len(annotations):,}**.\n"
        )
        handle.write(
            f"- Clusters receiving a changed broad label: "
            f"**{changed_clusters}**.\n"
        )
        handle.write(
            f"- Refined broad cell classes: "
            f"**{annotations['refined_broad_cell_type'].nunique()}**.\n"
        )
        handle.write(
            f"- Refined biological subtypes/states: "
            f"**{annotations['refined_cell_subtype'].nunique()}**.\n\n"
        )

        handle.write("## Major annotation corrections\n\n")
        for _, item in refinement[refinement["label_changed"]].iterrows():
            handle.write(
                f"- Cluster {int(item['cluster'])}: "
                f"`{item['original_broad_cell_type']}` -> "
                f"`{item['refined_broad_cell_type']}` / "
                f"`{item['refined_cell_subtype']}` based on "
                f"{item['refinement_evidence']}.\n"
            )
        handle.write("\n")

        handle.write("## Targeted-state correction\n\n")
        handle.write(
            "The earlier sample-specific 80th-percentile definitions forced "
            "approximately 20% of each parent population to be called Treg or "
            "CD137L-high and therefore could not test biological enrichment. "
            "They have been retired. Treg-like candidates now use fixed marker "
            "logic, and macrophage TNFSF9-high status uses one pooled threshold "
            "applied unchanged to all four samples.\n\n"
        )

        for _, item in targeted_summary.iterrows():
            handle.write(
                f"- `{item['sample_id']}` "
                f"{item['targeted_measure']}: "
                f"{int(item['numerator_cells'])}/"
                f"{int(item['parent_cells'])} "
                f"({float(item['value']):.3f}).\n"
            )

        handle.write("\n## Statistical boundary\n\n")
        handle.write(
            "Cell identities and targeted-state fractions remain descriptive. "
            "All UPEC-versus-control pathway inference in U26D2B will use the "
            "four biological samples as the independent units.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": decision,
        "n_QC_cells": int(len(annotations)),
        "n_refined_broad_cell_types": int(
            annotations["refined_broad_cell_type"].nunique()
        ),
        "n_refined_subtypes": int(
            annotations["refined_cell_subtype"].nunique()
        ),
        "tnfsf9_high_threshold": (
            float(tnfsf9_high_threshold)
            if np.isfinite(tnfsf9_high_threshold)
            else None
        ),
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results / "UTI_HostOmics_U26D2A1_run_manifest.json"
    ).write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    log(f"QC cells retained: {len(annotations):,}")
    log(f"Clusters with changed broad label: {changed_clusters}")
    log(
        f"Refined broad classes: "
        f"{annotations['refined_broad_cell_type'].nunique()}"
    )
    log(
        f"Fixed pooled TNFSF9-high threshold: "
        f"{tnfsf9_high_threshold:.6f}"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26D2A.1] ERROR: {exc}", file=sys.stderr)
        raise
