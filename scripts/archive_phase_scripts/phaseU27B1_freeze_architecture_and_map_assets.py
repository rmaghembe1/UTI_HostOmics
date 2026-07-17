#!/usr/bin/env python3
"""
Phase U27B1
Freeze the final manuscript display architecture and map all source assets.

Outputs
-------
1. Inventory of current Figure 1-11 assets.
2. Canonical source selection for each working figure.
3. Final eight-main-figure plan with panel-level source mapping.
4. Nine supplementary-figure plan with panel-level source mapping.
5. Two-main-table plan.
6. Eight supplementary-table-package plan.
7. Working-to-final figure crosswalk.
8. Architecture decision and trajectory report.

This phase does not modify the manuscript, existing figures, source tables or
scientific values.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

try:
    from PIL import Image
except ImportError:
    Image = None


VERSION = "U27B1_v1.0_2026-07-15"
TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"

CANONICAL_U27A4_TAG = "phaseU27A4_final_visual_audit"

EXCLUDE_NAME_TOKENS = {
    "contact_sheet",
    "preview",
    "audit",
    "panel_collision",
    "one_column",
    "two_column",
    "thumbnail",
    "crop",
}

EXPECTED_SOURCE_TABLES = {
    "U26B1_1_primary_results": (
        "06_tables/phaseU26B1_1_GSE280297_stability_refinement"
    ),
    "U26B2B1_independent_effects": (
        "06_tables/phaseU26B2B1_independent_dataset_evidence_collapse"
    ),
    "U26C1_refined_synthesis": (
        "06_tables/phaseU26C1_interpretation_threshold_and_branch_refinement"
    ),
    "U26D2A_cell_annotations": (
        "03_metadata/phaseU26D2A_GSE252321_marker_celltype_reconstruction"
    ),
    "U26D2A1_refined_annotations": (
        "03_metadata/phaseU26D2A1_GSE252321_annotation_refinement"
    ),
    "U26D2B_celltype_pseudobulk": (
        "06_tables/phaseU26D2B_GSE252321_refined_celltype_pseudobulk"
    ),
    "U26D2C_cellular_synthesis": (
        "06_tables/phaseU26D2C_cellular_localization_synthesis"
    ),
    "U27A4_final_figures": (
        "06_figures/phaseU27A4_final_visual_audit"
    ),
}


MAIN_FIGURES = [
    {
        "figure": "Figure_1",
        "title": "Study architecture, datasets and evidence framework",
        "n_panels": 6,
        "primary_message": (
            "The study integrates cross-dataset infection biology, pregnancy "
            "outcome, endocrine-metabolic modules and cell-resolved validation "
            "under an explicit evidence hierarchy."
        ),
    },
    {
        "figure": "Figure_2",
        "title": "Cross-dataset infection-response core",
        "n_panels": 7,
        "primary_message": (
            "A TLR4-linked leptin/PI3K-AKT core is supported across independent "
            "infection contexts, with provisional complement support."
        ),
    },
    {
        "figure": "Figure_3",
        "title": "Pregnancy-, tissue- and outcome-resolved UTI remodeling",
        "n_panels": 8,
        "primary_message": (
            "Pregnancy-associated UTI remodeling is tissue-specific and "
            "branch-selective rather than a global steroid-metabolic shift."
        ),
    },
    {
        "figure": "Figure_4",
        "title": "Single-cell immune ecosystem and the TNFSF9-Treg axis",
        "n_panels": 8,
        "primary_message": (
            "UPEC induces myeloid expansion while TNFSF9-positive macrophage, "
            "Treg-like and pathway programs remain distributed across multiple "
            "immune states."
        ),
    },
    {
        "figure": "Figure_5",
        "title": "Steroid, cholesterol and lipid-remodeling architecture",
        "n_panels": 7,
        "primary_message": (
            "Steroid synthesis, cholesterol metabolism, receptor response and "
            "lipid-stress programs are biologically separable branches."
        ),
    },
    {
        "figure": "Figure_6",
        "title": "Adipokine, insulin and integrated immunometabolic remodeling",
        "n_panels": 8,
        "primary_message": (
            "Adipokine and insulin signaling couple to inflammatory carbon use, "
            "nitrogen metabolism and purine-redox remodeling."
        ),
    },
    {
        "figure": "Figure_7",
        "title": "Complement branch and cellular architecture",
        "n_panels": 7,
        "primary_message": (
            "Complement remodeling is branch- and cell-specific rather than "
            "uniformly activated."
        ),
    },
    {
        "figure": "Figure_8",
        "title": "Integrated endocrine-metabolic-immune model",
        "n_panels": 6,
        "primary_message": (
            "UTI biology emerges from context-dependent endocrine, metabolic "
            "and immune programs with distinct cellular sources."
        ),
    },
]


MAIN_PANELS = [
    # Figure 1
    ("Figure_1", "A", "Central biological questions",
     "conceptual_rebuild", "working Figure 1; U26A module architecture",
     "01_study_design_and_question_map"),
    ("Figure_1", "B", "Dataset map by species, tissue, specimen and omics layer",
     "table_driven_rebuild", "dataset/sample manifests; working Figure 1",
     "dataset_manifest"),
    ("Figure_1", "C", "Sample and contrast architecture",
     "table_driven_rebuild", "GSE280297 validated design; comparator designs",
     "contrast_manifest"),
    ("Figure_1", "D", "Ten axes and 78-submodule hierarchy",
     "table_driven_rebuild", "U26A expanded submodule library",
     "U26A_module_dictionary"),
    ("Figure_1", "E", "Analytical workflow",
     "conceptual_rebuild", "phase decisions U26A-U27A4",
     "phase_workflow_manifest"),
    ("Figure_1", "F", "Evidence hierarchy",
     "table_driven_rebuild", "U26C1 refined core and claim priorities",
     "U26C1_evidence_tiers"),

    # Figure 2
    ("Figure_2", "A", "One independent infection-context effect per dataset",
     "table_driven_rebuild", "U26B2B1 primary independent effects",
     "U26B2B1_primary_effects"),
    ("Figure_2", "B", "Robust, provisional, secondary and divergent modules",
     "table_driven_rebuild", "U26B2B1 evidence classes",
     "U26B2B1_classification"),
    ("Figure_2", "C", "TLR4-leptin-PI3K/AKT core",
     "table_driven_rebuild", "U26C1 refined synthesis",
     "U26C1_core_network"),
    ("Figure_2", "D", "Provisional complement core",
     "table_driven_rebuild", "U26C1 complement priorities",
     "U26C1_complement_core"),
    ("Figure_2", "E", "Adjusted systemic inflammatory comparator",
     "table_driven_rebuild", "GSE112098 adjusted results",
     "U26B2B_GSE112098"),
    ("Figure_2", "F", "Gardnerella contextual effects and block separation",
     "table_driven_rebuild", "GSE186800 averaged treatment and block effects",
     "U26B2B_GSE186800"),
    ("Figure_2", "G", "Evidence-weighted concordance network",
     "table_driven_rebuild", "U26B2B1 recurrence and U26C network",
     "U26B2B1_U26C_network"),

    # Figure 3
    ("Figure_3", "A", "GSE280297 experimental and tissue design",
     "table_driven_rebuild", "validated 60-sample design",
     "GSE280297_design"),
    ("Figure_3", "B", "Preterm-versus-term effects by tissue",
     "table_driven_rebuild", "U26B1.1 C1 primary results",
     "U26B1_1_C1"),
    ("Figure_3", "C", "Cross-tissue receptor and metabolic attenuation",
     "table_driven_rebuild", "U26B1.1 cross-tissue concordance",
     "U26B1_1_C1_concordance"),
    ("Figure_3", "D", "Steroid synthesis-response decoupling",
     "table_driven_rebuild", "U26C1 branch-selective steroid summary",
     "U26C1_steroid_branching"),
    ("Figure_3", "E", "UPEC pregnancy versus PBS pregnancy",
     "table_driven_rebuild", "U26B1.1 C2 results",
     "U26B1_1_C2"),
    ("Figure_3", "F", "Pregnant versus nonpregnant infected bladder",
     "table_driven_rebuild", "U26B1.1 C3 results",
     "U26B1_1_C3"),
    ("Figure_3", "G", "Tissue-specific complement and inflammatory carbon",
     "table_driven_rebuild", "U26B1.1 tissue heatmaps",
     "U26B1_1_tissue_modules"),
    ("Figure_3", "H", "Pregnancy-outcome working model",
     "conceptual_rebuild", "U26C1 refined pregnancy synthesis",
     "U26C1_pregnancy_model"),

    # Figure 4
    ("Figure_4", "A", "Balanced cellular embedding",
     "scripted_rebuild", "U26D2A balanced cell annotations",
     "U26D2A_embedding"),
    ("Figure_4", "B", "Cluster-marker validation and refined identities",
     "table_driven_rebuild", "U26D2A top markers and U26D2A1 refinement",
     "U26D2A_D2A1_markers"),
    ("Figure_4", "C", "Cell-type composition across four samples",
     "table_driven_rebuild", "U26D2A1 refined composition",
     "U26D2A1_composition"),
    ("Figure_4", "D", "Refined immune subtypes and states",
     "table_driven_rebuild", "U26D2A1 subtype composition",
     "U26D2A1_subtypes"),
    ("Figure_4", "E", "TNFSF9-positive and TNFSF9-high macrophages",
     "table_driven_rebuild", "U26D2A1 fixed targeted populations",
     "U26D2A1_TNFSF9"),
    ("Figure_4", "F", "Strict and expanded Treg-like fractions",
     "table_driven_rebuild", "U26D2A1 fixed targeted populations",
     "U26D2A1_Treg"),
    ("Figure_4", "G", "Sample-by-cell-type pseudobulk core localization",
     "table_driven_rebuild", "U26D2C core cellular attribution",
     "U26D2C_core_localization"),
    ("Figure_4", "H", "TNFSF9-macrophage-Treg inflammation model",
     "conceptual_rebuild", "U26D2A1/U26D2C synthesis",
     "U26D_cellular_model"),

    # Figure 5
    ("Figure_5", "A", "Independent endocrine/lipid infection effects",
     "reuse_and_rebuild", "U27A4 Figure 7A",
     "U27A4_Figure_7A"),
    ("Figure_5", "B", "Pregnancy endocrine/lipid effects",
     "reuse_and_rebuild", "U27A4 Figure 7B",
     "U27A4_Figure_7B"),
    ("Figure_5", "C", "Broad-cell endocrine/lipid localization",
     "reuse_and_rebuild", "U27A4 Figure 7C",
     "U27A4_Figure_7C"),
    ("Figure_5", "D", "Steroid synthesis versus response branch map",
     "table_driven_rebuild", "U26C1 steroid branch summary",
     "U26C1_steroid_quadrant"),
    ("Figure_5", "E", "Pan-immune cholesterol-synthesis suppression",
     "table_driven_rebuild", "U26D2C broad reliability",
     "U26D2C_cholesterol"),
    ("Figure_5", "F", "Lipid-droplet, PPAR/SREBP/LXR and ferroptosis",
     "table_driven_rebuild", "U26D2C broad and subtype reliability",
     "U26D2C_lipid_stress"),
    ("Figure_5", "G", "Highest-support refined cellular subtypes",
     "reuse_and_rebuild", "U27A4 Figure 7D",
     "U27A4_Figure_7D"),

    # Figure 6
    ("Figure_6", "A", "Independent adipokine/insulin/carbon effects",
     "reuse_and_rebuild", "U27A4 Figure 8A",
     "U27A4_Figure_8A"),
    ("Figure_6", "B", "Pregnancy attenuation of leptin/IRS/PI3K-AKT",
     "reuse_and_rebuild", "U27A4 Figure 8B",
     "U27A4_Figure_8B"),
    ("Figure_6", "C", "Broad-cell signaling trajectories",
     "reuse_and_rebuild", "U27A4 Figure 8C",
     "U27A4_Figure_8C"),
    ("Figure_6", "D", "Refined-subtype adipokine and carbon support",
     "reuse_and_rebuild", "U27A4 Figure 8D",
     "U27A4_Figure_8D"),
    ("Figure_6", "E", "Leptin-IRS-PI3K/AKT network",
     "table_driven_rebuild", "U26C1/U26D2C core synthesis",
     "U26C1_U26D2C_metabolic_network"),
    ("Figure_6", "F", "Glycolysis, HIF1A, glycogen and pentose phosphate",
     "table_driven_rebuild", "U26D2C broad/subtype reliability",
     "U26D2C_carbon"),
    ("Figure_6", "G", "Amino-acid transport and arginine-NO-urea",
     "selected_rebuild", "U27A4 Figure 9 source data",
     "U27A4_Figure_9_selected_AA_NO"),
    ("Figure_6", "H", "Purine, NAD and NRF2-redox remodeling",
     "selected_rebuild", "U27A4 Figure 9 source data",
     "U27A4_Figure_9_selected_purine_redox"),

    # Figure 7
    ("Figure_7", "A", "Complement effects organized by stage",
     "reuse_and_rebuild", "U27A4 Figure 10A",
     "U27A4_Figure_10A"),
    ("Figure_7", "B", "Pregnancy complement effects",
     "reuse_and_rebuild", "U27A4 Figure 10B",
     "U27A4_Figure_10B"),
    ("Figure_7", "C", "Broad-cell complement localization",
     "reuse_and_rebuild", "U27A4 Figure 10C",
     "U27A4_Figure_10C"),
    ("Figure_7", "D", "Refined-subtype complement support",
     "reuse_and_rebuild", "U27A4 Figure 10D",
     "U27A4_Figure_10D"),
    ("Figure_7", "E", "Complement branch topology",
     "table_driven_rebuild", "U26C1/U26D2C complement synthesis",
     "U26C1_U26D2C_complement_topology"),
    ("Figure_7", "F", "C3a/C5a versus opsonophagocytosis",
     "table_driven_rebuild", "U26D2C cellular attribution",
     "U26D2C_complement_comparison"),
    ("Figure_7", "G", "Coverage and evidence map",
     "table_driven_rebuild", "U26D2B module coverage",
     "U26D2B_complement_coverage"),

    # Figure 8
    ("Figure_8", "A", "Core modules across infection and pregnancy contexts",
     "reuse_and_rebuild", "U27A4 Figure 11A",
     "U27A4_Figure_11A"),
    ("Figure_8", "B", "Cell-source-resolved core localization",
     "reuse_and_rebuild", "U27A4 Figure 11B",
     "U27A4_Figure_11B"),
    ("Figure_8", "C", "UPEC-associated cell-composition shifts",
     "selected_rebuild", "U27A4 Figure 11C composition subset",
     "U27A4_Figure_11C_composition"),
    ("Figure_8", "D", "Treg-like and TNFSF9 macrophage states",
     "selected_rebuild", "U27A4 Figure 11C targeted-state subset",
     "U27A4_Figure_11C_targeted"),
    ("Figure_8", "E", "Integrated mechanistic network",
     "reuse_and_rebuild", "U27A4 Figure 11D",
     "U27A4_Figure_11D"),
    ("Figure_8", "F", "Evidence hierarchy and limitations",
     "table_driven_rebuild", "U26C1 claim priorities and U26D2C boundaries",
     "U26C1_U26D2C_evidence_boundary"),
]


SUPP_FIGURES = [
    ("Figure_S1", "Dataset acquisition and preprocessing", 6),
    ("Figure_S2", "Module-library construction and coverage", 6),
    ("Figure_S3", "GSE280297 technical and statistical diagnostics", 8),
    ("Figure_S4", "Cross-dataset comparator and sensitivity analyses", 8),
    ("Figure_S5", "Single-cell QC and annotation diagnostics", 8),
    ("Figure_S6", "Complete cell-type and subtype pseudobulk landscape", 8),
    ("Figure_S7", "Full amino-acid, nucleotide, nitrogen and redox atlas", 4),
    ("Figure_S8", "Extended endocrine/lipid and complement branches", 6),
    ("Figure_S9", "Robustness, evidence hierarchy and claim-boundary audit", 6),
]


SUPP_PANELS = [
    ("Figure_S1", "A", "Dataset search and inclusion flow", "dataset manifests"),
    ("Figure_S1", "B", "Raw input types and accessions", "raw-data inventory"),
    ("Figure_S1", "C", "Expression-matrix repair", "U26A5/U26B2A1 reports"),
    ("Figure_S1", "D", "Gene-symbol resolution", "matrix repair audits"),
    ("Figure_S1", "E", "Sample retention", "validated designs"),
    ("Figure_S1", "F", "Final analysis-ready datasets", "phase decisions"),

    ("Figure_S2", "A", "Ten biological axes", "U26A module library"),
    ("Figure_S2", "B", "Seventy-eight submodules", "U26A module library"),
    ("Figure_S2", "C", "Gene-set size distribution", "U26A gene membership"),
    ("Figure_S2", "D", "Human and mouse coverage", "U26B/U26D coverage"),
    ("Figure_S2", "E", "Weak and partial modules", "coverage audits"),
    ("Figure_S2", "F", "Score-eligibility summary", "U26B1/U26D2B"),

    ("Figure_S3", "A", "Canonical matrix validation", "U26A5"),
    ("Figure_S3", "B", "Sample and tissue distribution", "GSE280297 design"),
    ("Figure_S3", "C", "Module-score distributions", "U26B1"),
    ("Figure_S3", "D", "Permutation behavior", "U26B1.1"),
    ("Figure_S3", "E", "Overall FDR landscape", "U26B1.1"),
    ("Figure_S3", "F", "Family-specific FDR landscape", "U26B1.1"),
    ("Figure_S3", "G", "Effect-size stability", "U26B1.1"),
    ("Figure_S3", "H", "Exploratory C4 separation", "U26B1.1 secondary"),

    ("Figure_S4", "A", "GSE112098 adjusted model", "U26B2B"),
    ("Figure_S4", "B", "GSE186800 block effects", "U26B2B"),
    ("Figure_S4", "C", "GSE186800 averaged treatment effects", "U26B2B1"),
    ("Figure_S4", "D", "GSE252321 whole-sample pseudobulk", "U26B2B"),
    ("Figure_S4", "E", "Independent-effect collapse", "U26B2B1"),
    ("Figure_S4", "F", "Dataset weighting sensitivity", "U26B2B1"),
    ("Figure_S4", "G", "Alternative recurrence definitions", "U26B2B1"),
    ("Figure_S4", "H", "Divergent modules", "U26B2B1"),

    ("Figure_S5", "A", "Per-sample library depth", "U26D1A"),
    ("Figure_S5", "B", "Detected genes", "U26D1A"),
    ("Figure_S5", "C", "Mitochondrial fraction", "U26D1A"),
    ("Figure_S5", "D", "Balanced integration", "U26D2A"),
    ("Figure_S5", "E", "Unsupervised clusters", "U26D2A"),
    ("Figure_S5", "F", "Marker-panel validation", "U26D2A"),
    ("Figure_S5", "G", "Annotation confidence", "U26D2A"),
    ("Figure_S5", "H", "Cluster-refinement audit", "U26D2A1"),

    ("Figure_S6", "A", "Broad-cell full module heatmap", "U26D2B"),
    ("Figure_S6", "B", "Refined-subtype full module heatmap", "U26D2B"),
    ("Figure_S6", "C", "Module coverage", "U26D2B"),
    ("Figure_S6", "D", "Cellular-localization classes", "U26D2C"),
    ("Figure_S6", "E", "Variance-sensitive effects", "U26D2C"),
    ("Figure_S6", "F", "Composite localization scores", "U26D2C"),
    ("Figure_S6", "G", "Top broad-cell sources", "U26D2C"),
    ("Figure_S6", "H", "Top refined-subtype sources", "U26D2C"),

    ("Figure_S7", "A", "Independent amino-acid/nucleotide/redox effects",
     "U27A4 Figure 9A"),
    ("Figure_S7", "B", "Pregnancy preterm-term effects",
     "U27A4 Figure 9B"),
    ("Figure_S7", "C", "Broad-cell cellular localization",
     "U27A4 Figure 9C"),
    ("Figure_S7", "D", "Refined-subtype support",
     "U27A4 Figure 9D"),

    ("Figure_S8", "A", "Androgen/testosterone biosynthesis", "U26B1.1"),
    ("Figure_S8", "B", "Testosterone conversion/aromatization", "U26B1.1"),
    ("Figure_S8", "C", "Steroid catabolism/deactivation", "U26B1.1"),
    ("Figure_S8", "D", "Lectin complement outside cellular data", "U26B1.1"),
    ("Figure_S8", "E", "Terminal-MAC outside cellular data", "U26B1.1"),
    ("Figure_S8", "F", "Coverage limitations", "U26D2B"),

    ("Figure_S9", "A", "Alternative effect metrics", "U26B1.1/U26D2C"),
    ("Figure_S9", "B", "Hedges-g variance sensitivity", "U26D2C"),
    ("Figure_S9", "C", "Composite cellular-localization score", "U26D2C"),
    ("Figure_S9", "D", "Evidence tiers", "U26C1"),
    ("Figure_S9", "E", "Claim-language boundaries", "U26D2C"),
    ("Figure_S9", "F", "Study limitations", "U26C1/U26D2C"),
]


MAIN_TABLES = [
    {
        "table": "Table_1",
        "title": "Dataset, sample and analytical-design summary",
        "planned_rows": "one row per dataset/analysis context",
        "columns": (
            "accession; organism; tissue/specimen; exposure/outcome; omics "
            "platform; biological n; contrast; analytical role; adjustment; "
            "principal limitation"
        ),
        "source": "dataset manifests and validated sample designs",
    },
    {
        "table": "Table_2",
        "title": "Evidence-tiered core biological modules",
        "planned_rows": "core, provisional, secondary and selected pregnancy branches",
        "columns": (
            "module; axis; human adjusted-FDR evidence; independent mouse "
            "support; pregnancy direction; broad-cell localization; refined "
            "subtype; evidence class; claim priority; principal limitation"
        ),
        "source": "U26B2B1, U26C1 and U26D2C",
    },
]


SUPP_TABLES = [
    ("Table_S1", "Dataset and sample manifest",
     "dataset accessions; sample metadata; contrasts; inclusion decisions"),
    ("Table_S2", "Expanded module library",
     "78-submodule dictionary; axes; gene membership; species coverage"),
    ("Table_S3", "GSE280297 full results",
     "C1; C2; C3; C4; permutation; stability; tissue collapse"),
    ("Table_S4", "Comparator-dataset results",
     "GSE112098; GSE186800; GSE252321; diagnostics"),
    ("Table_S5", "Cross-dataset evidence collapse",
     "primary effects; recurrence; divergence; evidence classes"),
    ("Table_S6", "Single-cell QC and annotations",
     "QC; clusters; markers; composition; Treg; TNFSF9 macrophages"),
    ("Table_S7", "Cell-type pseudobulk results",
     "manifest; broad results; subtype results; localization; reliability"),
    ("Table_S8", "Figure source data and reproducibility",
     "main/supp source values; panel mapping; scripts; versions; checksums"),
]


WORKING_CROSSWALK = [
    ("Working_Figure_1", "Final_Figure_1", "primary source"),
    ("Working_Figure_2", "Final_Figure_2", "consolidated with working Figure 3"),
    ("Working_Figure_3", "Final_Figure_2", "consolidated with working Figure 2"),
    ("Working_Figure_4", "Final_Figure_3;Final_Figure_4;Figure_S3;Figure_S5",
     "redistributed by content"),
    ("Working_Figure_5", "Final_Figure_3;Final_Figure_4;Figure_S4;Figure_S5",
     "redistributed by content"),
    ("Working_Figure_6", "Final_Figure_3;Final_Figure_4;Figure_S4;Figure_S6",
     "redistributed by content"),
    ("Working_Figure_7", "Final_Figure_5", "U27A4 source archive"),
    ("Working_Figure_8", "Final_Figure_6", "U27A4 source archive"),
    ("Working_Figure_9", "Final_Figure_6 panels G-H;Figure_S7",
     "selected main panels plus complete supplementary atlas"),
    ("Working_Figure_10", "Final_Figure_7", "U27A4 source archive"),
    ("Working_Figure_11", "Final_Figure_8", "U27A4 source archive"),
]


def log(message: str) -> None:
    print(f"[U27B1] {message}", flush=True)


def figure_number_from_name(path: Path) -> Optional[int]:
    name = path.stem
    patterns = [
        r"(?i)(?:^|[_\-\s])Figure[_\-\s]?(\d+)(?:$|[_\-\s])",
        r"(?i)(?:^|[_\-\s])Fig[_\-\s]?(\d+)(?:$|[_\-\s])",
    ]
    for pattern in patterns:
        match = re.search(pattern, name)
        if match:
            number = int(match.group(1))
            if 1 <= number <= 11:
                return number
    return None


def is_excluded_asset(path: Path) -> bool:
    name = path.name.lower()
    return any(token in name for token in EXCLUDE_NAME_TOKENS)


def image_dimensions(path: Path) -> Tuple[Optional[int], Optional[int]]:
    if Image is None or path.suffix.lower() != ".png":
        return None, None
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def candidate_score(path: Path, figure_number: int) -> int:
    text = str(path).lower()
    score = 0

    if path.suffix.lower() == ".svg":
        score += 40
    elif path.suffix.lower() == ".pdf":
        score += 35
    elif path.suffix.lower() == ".png":
        score += 30

    if figure_number >= 7 and CANONICAL_U27A4_TAG.lower() in text:
        score += 1000
    if "final" in text:
        score += 150
    if "submission" in text:
        score += 120
    if "publication" in text:
        score += 80
    if "repaired" in text or "refined" in text:
        score += 50
    if "archive" in text:
        score -= 60
    if "old" in text or "deprecated" in text:
        score -= 200

    try:
        score += int(path.stat().st_mtime // 100000)
    except OSError:
        pass

    return score


def inventory_figure_assets(project: Path) -> pd.DataFrame:
    roots = [
        project / "06_figures",
        project / "07_figures",
        project / "figures",
    ]
    rows: List[Dict[str, object]] = []

    for root in roots:
        if not root.exists():
            continue
        for extension in ("*.png", "*.svg", "*.pdf"):
            for path in root.rglob(extension):
                if is_excluded_asset(path):
                    continue
                figure_number = figure_number_from_name(path)
                if figure_number is None:
                    continue
                width, height = image_dimensions(path)
                rows.append(
                    {
                        "working_figure_number": figure_number,
                        "working_figure": f"Working_Figure_{figure_number}",
                        "path": str(path),
                        "filename": path.name,
                        "format": path.suffix.lower().lstrip("."),
                        "size_bytes": path.stat().st_size,
                        "modified_epoch": path.stat().st_mtime,
                        "png_width_px": width,
                        "png_height_px": height,
                        "candidate_score": candidate_score(
                            path, figure_number
                        ),
                        "canonical_U27A4_source": (
                            figure_number >= 7
                            and CANONICAL_U27A4_TAG.lower()
                            in str(path).lower()
                        ),
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "working_figure_number", "working_figure", "path",
                "filename", "format", "size_bytes", "modified_epoch",
                "png_width_px", "png_height_px", "candidate_score",
                "canonical_U27A4_source",
            ]
        )

    return pd.DataFrame(rows).sort_values(
        ["working_figure_number", "candidate_score"],
        ascending=[True, False],
    )


def select_canonical_assets(inventory: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []

    for number in range(1, 12):
        subset = inventory[
            inventory["working_figure_number"] == number
        ].copy()

        if subset.empty:
            rows.append(
                {
                    "working_figure_number": number,
                    "working_figure": f"Working_Figure_{number}",
                    "asset_found": False,
                    "canonical_stem": "",
                    "canonical_png": "",
                    "canonical_svg": "",
                    "canonical_pdf": "",
                    "formats_available": "",
                    "selection_basis": "no matching asset discovered",
                    "requires_manual_review": True,
                }
            )
            continue

        stems = []
        for path_text in subset["path"].astype(str):
            path = Path(path_text)
            stems.append(str(path.with_suffix("")))
        subset["stem"] = stems

        stem_summary = (
            subset.groupby("stem", as_index=False)
            .agg(
                max_score=("candidate_score", "max"),
                n_formats=("format", "nunique"),
                canonical_U27A4=("canonical_U27A4_source", "max"),
                latest_modified=("modified_epoch", "max"),
            )
        )

        stem_summary["selection_score"] = (
            stem_summary["max_score"]
            + stem_summary["n_formats"] * 30
            + stem_summary["canonical_U27A4"].astype(int) * 500
        )
        selected_stem = (
            stem_summary.sort_values(
                ["selection_score", "latest_modified"],
                ascending=[False, False],
            ).iloc[0]["stem"]
        )

        selected = subset[subset["stem"] == selected_stem]
        paths_by_format = {
            row["format"]: row["path"]
            for _, row in selected.iterrows()
        }
        formats = sorted(paths_by_format)
        complete = all(
            extension in paths_by_format
            for extension in ["png", "svg", "pdf"]
        )

        rows.append(
            {
                "working_figure_number": number,
                "working_figure": f"Working_Figure_{number}",
                "asset_found": True,
                "canonical_stem": selected_stem,
                "canonical_png": paths_by_format.get("png", ""),
                "canonical_svg": paths_by_format.get("svg", ""),
                "canonical_pdf": paths_by_format.get("pdf", ""),
                "formats_available": ";".join(formats),
                "selection_basis": (
                    "U27A4 normalized final asset"
                    if number >= 7
                    and bool(selected["canonical_U27A4_source"].any())
                    else "highest-scoring discovered source asset"
                ),
                "requires_manual_review": not complete or number <= 6,
            }
        )

    return pd.DataFrame(rows)


def source_availability(project: Path) -> pd.DataFrame:
    rows = []
    for source_id, relative in EXPECTED_SOURCE_TABLES.items():
        path = project / relative
        rows.append(
            {
                "source_id": source_id,
                "path": str(path),
                "exists": path.exists(),
                "is_directory": path.is_dir(),
            }
        )
    return pd.DataFrame(rows)


def main_panel_table() -> pd.DataFrame:
    columns = [
        "final_figure", "panel", "panel_title", "construction_mode",
        "primary_source", "source_id",
    ]
    frame = pd.DataFrame(MAIN_PANELS, columns=columns)
    figure_meta = pd.DataFrame(MAIN_FIGURES).rename(
        columns={
            "figure": "final_figure",
            "title": "final_figure_title",
            "n_panels": "planned_panels",
        }
    )
    frame = frame.merge(
        figure_meta[
            [
                "final_figure",
                "final_figure_title",
                "planned_panels",
                "primary_message",
            ]
        ],
        on="final_figure",
        how="left",
    )
    frame["panel_key"] = (
        frame["final_figure"] + frame["panel"].astype(str)
    )
    frame["architecture_status"] = "frozen"
    return frame


def supplementary_panel_table() -> pd.DataFrame:
    columns = [
        "supplementary_figure", "panel", "panel_title", "primary_source"
    ]
    frame = pd.DataFrame(SUPP_PANELS, columns=columns)
    meta = pd.DataFrame(
        SUPP_FIGURES,
        columns=[
            "supplementary_figure",
            "supplementary_figure_title",
            "planned_panels",
        ],
    )
    frame = frame.merge(
        meta,
        on="supplementary_figure",
        how="left",
    )
    frame["panel_key"] = (
        frame["supplementary_figure"] + frame["panel"].astype(str)
    )
    frame["architecture_status"] = "frozen"
    return frame


def validate_architecture(
    main_panels: pd.DataFrame,
    supp_panels: pd.DataFrame,
) -> Dict[str, object]:
    main_counts = (
        main_panels.groupby("final_figure")["panel"].nunique()
    )
    supp_counts = (
        supp_panels.groupby("supplementary_figure")["panel"].nunique()
    )

    main_expected = {
        item["figure"]: item["n_panels"] for item in MAIN_FIGURES
    }
    supp_expected = {
        figure: panels for figure, _, panels in SUPP_FIGURES
    }

    main_pass = all(
        main_counts.get(figure, 0) == expected
        for figure, expected in main_expected.items()
    )
    supp_pass = all(
        supp_counts.get(figure, 0) == expected
        for figure, expected in supp_expected.items()
    )

    return {
        "main_figure_count": len(main_expected),
        "main_panel_count": int(len(main_panels)),
        "main_panel_count_validation_pass": main_pass,
        "supplementary_figure_count": len(supp_expected),
        "supplementary_panel_count": int(len(supp_panels)),
        "supplementary_panel_count_validation_pass": supp_pass,
        "main_table_count": len(MAIN_TABLES),
        "supplementary_table_package_count": len(SUPP_TABLES),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG

    for directory in [out_tables, out_metadata, out_results]:
        directory.mkdir(parents=True, exist_ok=True)

    log("Inventorying current Figure 1-11 assets.")
    inventory = inventory_figure_assets(project)
    inventory.to_csv(
        out_tables
        / "UTI_HostOmics_U27B1_current_figure_asset_inventory.tsv",
        sep="\t",
        index=False,
    )

    canonical = select_canonical_assets(inventory)
    canonical.to_csv(
        out_tables
        / "UTI_HostOmics_U27B1_canonical_working_figure_assets.tsv",
        sep="\t",
        index=False,
    )

    availability = source_availability(project)
    availability.to_csv(
        out_tables
        / "UTI_HostOmics_U27B1_source_availability.tsv",
        sep="\t",
        index=False,
    )

    main_figures = pd.DataFrame(MAIN_FIGURES)
    main_figures["architecture_status"] = "frozen"
    main_figures.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B1_final_main_figure_plan.tsv",
        sep="\t",
        index=False,
    )

    main_panels = main_panel_table()
    main_panels.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv",
        sep="\t",
        index=False,
    )

    supp_figures = pd.DataFrame(
        SUPP_FIGURES,
        columns=["figure", "title", "n_panels"],
    )
    supp_figures["architecture_status"] = "frozen"
    supp_figures.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B1_supplementary_figure_plan.tsv",
        sep="\t",
        index=False,
    )

    supp_panels = supplementary_panel_table()
    supp_panels.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B1_supplementary_panel_mapping.tsv",
        sep="\t",
        index=False,
    )

    main_tables = pd.DataFrame(MAIN_TABLES)
    main_tables["architecture_status"] = "frozen"
    main_tables.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B1_main_table_plan.tsv",
        sep="\t",
        index=False,
    )

    supp_tables = pd.DataFrame(
        SUPP_TABLES,
        columns=["table", "title", "planned_sheets_or_content"],
    )
    supp_tables["architecture_status"] = "frozen"
    supp_tables.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B1_supplementary_table_plan.tsv",
        sep="\t",
        index=False,
    )

    crosswalk = pd.DataFrame(
        WORKING_CROSSWALK,
        columns=[
            "working_figure",
            "final_destination",
            "mapping_rule",
        ],
    )
    crosswalk.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B1_working_to_final_figure_crosswalk.tsv",
        sep="\t",
        index=False,
    )

    validation = validate_architecture(main_panels, supp_panels)

    working_1_to_6_found = int(
        canonical.loc[
            canonical["working_figure_number"].between(1, 6),
            "asset_found",
        ].sum()
    )
    working_7_to_11_canonical = bool(
        canonical.loc[
            canonical["working_figure_number"].between(7, 11),
            "asset_found",
        ].all()
    )
    required_sources_present = int(availability["exists"].sum())
    required_sources_total = len(availability)

    if (
        validation["main_panel_count_validation_pass"]
        and validation["supplementary_panel_count_validation_pass"]
        and working_7_to_11_canonical
        and required_sources_present == required_sources_total
    ):
        if working_1_to_6_found == 6:
            decision = (
                "READY_FOR_U27B2_SCRIPTED_MAIN_FIGURE_CONSOLIDATION"
            )
        else:
            decision = (
                "READY_FOR_U27B2_WITH_TARGETED_WORKING_FIGURE_1_TO_6_"
                "SOURCE_CONFIRMATION"
            )
    else:
        decision = "TARGETED_ARCHITECTURE_OR_SOURCE_REVIEW_REQUIRED"

    decision_row = {
        "phase": "U27B1",
        "decision": decision,
        **validation,
        "working_figures_1_to_6_found": working_1_to_6_found,
        "working_figures_7_to_11_canonical_found": (
            working_7_to_11_canonical
        ),
        "required_source_directories_present": required_sources_present,
        "required_source_directories_total": required_sources_total,
        "architecture_frozen": True,
        "scientific_values_changed": False,
        "manuscript_modified": False,
        "existing_figures_modified": False,
        "next_phase": (
            "U27B2 scripted consolidation of eight main figures"
            if decision.startswith("READY_FOR_U27B2")
            else "Resolve missing source assets or architecture validation"
        ),
    }
    pd.DataFrame([decision_row]).to_csv(
        out_tables
        / "UTI_HostOmics_U27B1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U27B1_architecture_freeze_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B1 - Architecture freeze and asset mapping\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Final main figures: **{validation['main_figure_count']}**.\n"
        )
        handle.write(
            f"- Final main-figure panels: "
            f"**{validation['main_panel_count']}**.\n"
        )
        handle.write(
            f"- Supplementary figures: "
            f"**{validation['supplementary_figure_count']}**.\n"
        )
        handle.write(
            f"- Supplementary-figure panels: "
            f"**{validation['supplementary_panel_count']}**.\n"
        )
        handle.write(
            f"- Main tables: **{validation['main_table_count']}**.\n"
        )
        handle.write(
            f"- Supplementary table packages: "
            f"**{validation['supplementary_table_package_count']}**.\n"
        )
        handle.write(
            f"- Working Figures 1-6 discovered: "
            f"**{working_1_to_6_found}/6**.\n"
        )
        handle.write(
            f"- Canonical Working Figures 7-11 available: "
            f"**{working_7_to_11_canonical}**.\n"
        )
        handle.write(
            f"- Required source directories present: "
            f"**{required_sources_present}/{required_sources_total}**.\n\n"
        )

        handle.write("## Frozen main-display architecture\n\n")
        for item in MAIN_FIGURES:
            handle.write(
                f"- **{item['figure'].replace('_', ' ')}:** "
                f"{item['title']} — {item['n_panels']} panels.\n"
            )

        handle.write("\n## Frozen supplementary architecture\n\n")
        for figure, title, panels in SUPP_FIGURES:
            handle.write(
                f"- **{figure.replace('_', ' ')}:** "
                f"{title} — {panels} panels.\n"
            )

        handle.write("\n## Tables\n\n")
        handle.write(
            "- **Table 1:** dataset, sample and analytical-design summary.\n"
            "- **Table 2:** evidence-tiered core biological modules.\n"
            "- **Tables S1-S8:** structured dataset, module, result, "
            "single-cell, pseudobulk and reproducibility packages.\n\n"
        )

        handle.write("## Construction rule\n\n")
        handle.write(
            "Final Figures 1-4 will be rebuilt from source tables and "
            "validated designs rather than copied as raster panels. Final "
            "Figures 5-8 will use the normalized U27A4 figures as source "
            "archives, with selective panel extraction and scripted "
            "recomposition. The full current amino-acid/nucleotide/redox "
            "atlas becomes Figure S7, while its strongest panels are "
            "incorporated into Final Figure 6.\n\n"
        )

        handle.write("## Integrity boundary\n\n")
        handle.write(
            "This phase freezes display architecture only. No scientific "
            "values, source tables, manuscript text or existing figures were "
            "changed.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "main_figures": validation["main_figure_count"],
        "main_panels": validation["main_panel_count"],
        "supplementary_figures": validation[
            "supplementary_figure_count"
        ],
        "supplementary_panels": validation[
            "supplementary_panel_count"
        ],
        "main_tables": validation["main_table_count"],
        "supplementary_table_packages": validation[
            "supplementary_table_package_count"
        ],
        "architecture_frozen": True,
        "scientific_values_changed": False,
        "manuscript_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U27B1_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(f"Working Figures 1-6 discovered: {working_1_to_6_found}/6")
    log(
        "Canonical Working Figures 7-11 available: "
        f"{working_7_to_11_canonical}"
    )
    log(
        f"Required source directories: "
        f"{required_sources_present}/{required_sources_total}"
    )
    log(
        f"Frozen displays: 8 main figures, "
        f"{validation['main_panel_count']} main panels, "
        f"9 supplementary figures, "
        f"{validation['supplementary_panel_count']} supplementary panels"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B1] ERROR: {exc}", file=sys.stderr)
        raise
