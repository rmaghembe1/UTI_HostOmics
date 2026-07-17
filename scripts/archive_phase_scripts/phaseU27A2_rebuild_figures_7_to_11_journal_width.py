#!/usr/bin/env python3
"""
Phase U27A
Build publication-oriented Figures 7-11 for the UTI HostOmics Project.

The figures integrate:
- one independent infection-context effect per dataset;
- pregnancy preterm-versus-term tissue-collapsed effects;
- U26D2C reliability-weighted broad-cell and refined-subtype localization;
- UPEC-associated cell-composition and fixed targeted-state changes;
- the final endocrine-metabolic-immune network architecture.

No manuscript text is modified in this phase. Figures 1-6 are preserved.
All metabolic panels represent transcriptionally inferred pathway activity,
not direct biochemical flux.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit("ERROR: matplotlib is required.") from exc


VERSION = "U27A2_v1.0_2026-07-14"
TAG = "phaseU27A2_journal_width_figure_repair"

B2B1_TAG = "phaseU26B2B1_independent_dataset_evidence_collapse"
D2B_TAG = "phaseU26D2B_GSE252321_refined_celltype_pseudobulk"
D2C_TAG = "phaseU26D2C_cellular_localization_synthesis"
C1_TAG = "phaseU26C1_interpretation_threshold_and_branch_refinement"

JOURNAL_WIDTH_MM = 180.0
JOURNAL_WIDTH_IN = JOURNAL_WIDTH_MM / 25.4
FAMILY_FIGURE_HEIGHT_IN = 9.35
INTEGRATED_FIGURE_HEIGHT_IN = 8.80

FIGURE_MODULES: Dict[str, List[str]] = {
    "Figure_7": [
        "CHOLESTEROL_BIOSYNTHESIS",
        "CHOLESTEROL_UPTAKE_TRANSPORT_EXPORT",
        "STEROIDOGENESIS_CORE",
        "ESTROGEN_BIOSYNTHESIS",
        "ESTROGEN_RECEPTOR_RESPONSE",
        "GLUCOCORTICOID_RESPONSE",
        "ANDROGEN_RECEPTOR_SIGNALING",
        "PROGESTERONE_BIOSYNTHESIS_RESPONSE",
        "STEROID_SULFATION_DESULFATION",
        "LIPID_DROPLET_DYNAMICS",
        "PPAR_SREBP_LXR_REGULATION",
        "FERROPTOSIS_LIPID_PEROXIDATION",
    ],
    "Figure_8": [
        "LEPTIN_SIGNALING",
        "RESISTIN_INFLAMMATORY_SIGNALING",
        "ADIPOKINE_INFLAMMATORY_AXIS",
        "INSULIN_RECEPTOR_IRS",
        "PI3K_AKT_SIGNALING",
        "GLYCOLYSIS",
        "LACTATE_HIF1A_INFLAMMATORY_GLYCOLYSIS",
        "GLYCOGEN_SYNTHESIS",
        "GLYCOGENOLYSIS",
        "PENTOSE_PHOSPHATE_PATHWAY",
        "TCA_OXPHOS",
        "MTOR_SIGNALING",
    ],
    "Figure_9": [
        "AMINO_ACID_TRANSPORT",
        "SERINE_GLYCINE_ONE_CARBON",
        "GLUTAMINE_GLUTAMATE",
        "TRYPTOPHAN_KYNURENINE",
        "BRANCHED_CHAIN_AMINO_ACIDS",
        "ARGININE_NO_UREA",
        "NITRIC_OXIDE_SYNTHESIS_REGULATION",
        "PURINE_SALVAGE",
        "PURINE_DEGRADATION_URATE",
        "XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM",
        "NAD_METABOLISM",
        "OXIDATIVE_STRESS_NRF2_ANCHOR",
    ],
    "Figure_10": [
        "COMPLEMENT_CLASSICAL",
        "COMPLEMENT_LECTIN",
        "COMPLEMENT_ALTERNATIVE",
        "COMPLEMENT_C3_CONVERTASE_AMPLIFICATION",
        "COMPLEMENT_C3A_C5A_SIGNALING",
        "COMPLEMENT_OPSONOPHAGOCYTOSIS",
        "COMPLEMENT_TERMINAL_MAC",
        "COMPLEMENT_COAGULATION_CROSSTALK",
        "COMPLEMENT_REGULATORS",
    ],
}

CORE_MODULES = [
    "TLR4_LPS_SIGNALING_ANCHOR",
    "LEPTIN_SIGNALING",
    "PI3K_AKT_SIGNALING",
    "INSULIN_RECEPTOR_IRS",
    "GLYCOGEN_SYNTHESIS",
    "COMPLEMENT_C3A_C5A_SIGNALING",
    "COMPLEMENT_OPSONOPHAGOCYTOSIS",
    "ANDROGEN_RECEPTOR_SIGNALING",
    "FATTY_ACID_SYNTHESIS",
    "AMINO_ACID_TRANSPORT",
]

DISPLAY_OVERRIDES = {
    "TLR4_LPS_SIGNALING_ANCHOR": "TLR4-LPS signaling",
    "NFKB_MAPK_INFLAMMATION_ANCHOR": "NF-kB/MAPK inflammation",
    "NEUTROPHIL_NETOSIS_ANCHOR": "Neutrophil/NETosis",
    "OXIDATIVE_STRESS_NRF2_ANCHOR": "Oxidative stress/NRF2",
    "COMPLEMENT_C3A_C5A_SIGNALING": "C3a/C5a signaling",
    "COMPLEMENT_OPSONOPHAGOCYTOSIS": "Complement-opsonophagocytosis",
    "LACTATE_HIF1A_INFLAMMATORY_GLYCOLYSIS": "Lactate-HIF1A glycolysis",
    "XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM": "Xanthine oxidase/purine oxidation",
    "PPAR_SREBP_LXR_REGULATION": "PPAR/SREBP/LXR regulation",
}

DISPLAY_OVERRIDES.update(
    {
        "CHOLESTEROL_BIOSYNTHESIS": "Cholesterol synthesis",
        "CHOLESTEROL_UPTAKE_TRANSPORT_EXPORT": "Cholesterol transport/export",
        "STEROIDOGENESIS_CORE": "Core steroidogenesis",
        "ESTROGEN_BIOSYNTHESIS": "Estrogen synthesis",
        "ESTROGEN_RECEPTOR_RESPONSE": "Estrogen-receptor response",
        "GLUCOCORTICOID_RESPONSE": "Glucocorticoid response",
        "ANDROGEN_RECEPTOR_SIGNALING": "Androgen-receptor signaling",
        "PROGESTERONE_BIOSYNTHESIS_RESPONSE": "Progesterone synthesis/response",
        "STEROID_SULFATION_DESULFATION": "Steroid sulfation/desulfation",
        "LIPID_DROPLET_DYNAMICS": "Lipid-droplet dynamics",
        "FERROPTOSIS_LIPID_PEROXIDATION": "Ferroptosis/lipid peroxidation",
        "LEPTIN_SIGNALING": "Leptin signaling",
        "RESISTIN_INFLAMMATORY_SIGNALING": "Resistin inflammatory signaling",
        "ADIPOKINE_INFLAMMATORY_AXIS": "Adipokine inflammatory axis",
        "INSULIN_RECEPTOR_IRS": "Insulin receptor/IRS",
        "PI3K_AKT_SIGNALING": "PI3K-AKT signaling",
        "GLYCOLYSIS": "Glycolysis",
        "GLYCOGEN_SYNTHESIS": "Glycogen synthesis",
        "GLYCOGENOLYSIS": "Glycogenolysis",
        "PENTOSE_PHOSPHATE_PATHWAY": "Pentose-phosphate pathway",
        "TCA_OXPHOS": "TCA/OXPHOS",
        "MTOR_SIGNALING": "mTOR signaling",
        "AMINO_ACID_TRANSPORT": "Amino-acid transport",
        "SERINE_GLYCINE_ONE_CARBON": "Serine/glycine one-carbon",
        "GLUTAMINE_GLUTAMATE": "Glutamine/glutamate",
        "TRYPTOPHAN_KYNURENINE": "Tryptophan/kynurenine",
        "BRANCHED_CHAIN_AMINO_ACIDS": "Branched-chain amino acids",
        "ARGININE_NO_UREA": "Arginine-NO-urea",
        "NITRIC_OXIDE_SYNTHESIS_REGULATION": "NO-synthesis regulation",
        "PURINE_SALVAGE": "Purine salvage",
        "PURINE_DEGRADATION_URATE": "Purine degradation/urate",
        "NAD_METABOLISM": "NAD metabolism",
        "COMPLEMENT_CLASSICAL": "Classical complement",
        "COMPLEMENT_LECTIN": "Lectin complement",
        "COMPLEMENT_ALTERNATIVE": "Alternative complement",
        "COMPLEMENT_C3_CONVERTASE_AMPLIFICATION": "C3-convertase amplification",
        "COMPLEMENT_TERMINAL_MAC": "Terminal complement/MAC",
        "COMPLEMENT_COAGULATION_CROSSTALK": "Complement-coagulation",
        "COMPLEMENT_REGULATORS": "Complement regulators",
        "FATTY_ACID_SYNTHESIS": "Fatty-acid synthesis",
    }
)


def log(message: str) -> None:
    print(f"[U27A] {message}", flush=True)


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", compression="infer", low_memory=False)


def require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    return path


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )


def display_label(feature_id: str, metadata: Dict[str, str]) -> str:
    if feature_id in DISPLAY_OVERRIDES:
        return DISPLAY_OVERRIDES[feature_id]
    label = metadata.get(feature_id, "")
    if label and label.lower() != "nan":
        return label
    return feature_id.replace("_", " ").title()


def panel_axes(figure: plt.Figure) -> Dict[str, plt.Axes]:
    grid = figure.add_gridspec(
        2,
        2,
        left=0.17,
        right=0.97,
        bottom=0.08,
        top=0.92,
        wspace=0.72,
        hspace=0.56,
    )
    return {
        "A": figure.add_subplot(grid[0, 0]),
        "B": figure.add_subplot(grid[0, 1]),
        "C": figure.add_subplot(grid[1, 0]),
        "D": figure.add_subplot(grid[1, 1]),
    }


def add_panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(
        -0.12,
        1.06,
        label,
        transform=axis.transAxes,
        fontsize=10.5,
        fontweight="bold",
        va="top",
    )


def finite_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(pd.to_numeric, errors="coerce")


def add_heatmap(
    axis: plt.Axes,
    matrix: pd.DataFrame,
    title: str,
    x_label: str = "",
    y_label: str = "",
    annotate: bool = False,
) -> None:
    axis.set_title(title, fontsize=8.4, pad=7)
    if matrix.empty:
        axis.text(
            0.5, 0.5, "No eligible data",
            transform=axis.transAxes,
            ha="center", va="center",
        )
        axis.set_axis_off()
        return

    matrix = finite_matrix(matrix)
    values = matrix.to_numpy(dtype=float)
    image = axis.imshow(values, aspect="auto")

    axis.set_xticks(np.arange(len(matrix.columns)))
    axis.set_xticklabels(
        [str(value).replace("_", " ") for value in matrix.columns],
        rotation=45,
        ha="right",
        fontsize=6.6,
    )
    axis.set_yticks(np.arange(len(matrix.index)))
    axis.set_yticklabels(matrix.index, fontsize=6.6)
    axis.set_xlabel(x_label, fontsize=7.2)
    axis.set_ylabel(y_label, fontsize=7.2)

    if annotate and values.size <= 90:
        for row in range(values.shape[0]):
            for column in range(values.shape[1]):
                value = values[row, column]
                if np.isfinite(value):
                    axis.text(
                        column,
                        row,
                        f"{value:.2f}",
                        ha="center",
                        va="center",
                        fontsize=5.5,
                    )

    colorbar = axis.figure.colorbar(
        image,
        ax=axis,
        fraction=0.045,
        pad=0.025,
    )
    colorbar.ax.tick_params(labelsize=6.0)


def add_barh(
    axis: plt.Axes,
    series: pd.Series,
    title: str,
    x_label: str,
    zero_line: bool = True,
) -> None:
    axis.set_title(title, fontsize=8.4, pad=7)
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        axis.text(
            0.5, 0.5, "No eligible data",
            transform=axis.transAxes,
            ha="center", va="center",
        )
        axis.set_axis_off()
        return

    y = np.arange(len(series))
    axis.barh(y, series.to_numpy())
    axis.set_yticks(y)
    axis.set_yticklabels(series.index, fontsize=6.6)
    axis.invert_yaxis()
    axis.set_xlabel(x_label, fontsize=7.2)
    if zero_line:
        axis.axvline(0, linewidth=0.8)
    axis.tick_params(axis="x", labelsize=6.4)

    span = float(np.nanmax(np.abs(series.to_numpy())))
    offset = span * 0.025 if span > 0 else 0.02
    for index, value in enumerate(series.to_numpy()):
        axis.text(
            value + (offset if value >= 0 else -offset),
            index,
            f"{value:+.2f}",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=5.8,
        )


def independent_effect_matrix(
    effects: pd.DataFrame,
    modules: Sequence[str],
    labels: Dict[str, str],
) -> pd.DataFrame:
    frame = effects[
        effects["feature_id"].astype(str).isin(modules)
    ].copy()

    if frame.empty:
        return pd.DataFrame()

    if "dataset" not in frame.columns:
        return pd.DataFrame()

    value_column = (
        "effect_value"
        if "effect_value" in frame.columns
        else "hedges_g"
        if "hedges_g" in frame.columns
        else ""
    )
    if not value_column:
        return pd.DataFrame()

    frame[value_column] = safe_numeric(frame[value_column])
    matrix = frame.pivot_table(
        index="feature_id",
        columns="dataset",
        values=value_column,
        aggfunc="first",
    )
    matrix = matrix.reindex(
        index=[module for module in modules if module in matrix.index]
    )
    matrix.index = [
        display_label(feature, labels) for feature in matrix.index
    ]
    return matrix


def preterm_series(
    preterm: pd.DataFrame,
    modules: Sequence[str],
    labels: Dict[str, str],
) -> pd.Series:
    frame = preterm[
        preterm["feature_id"].astype(str).isin(modules)
    ].copy()
    if frame.empty:
        return pd.Series(dtype=float)

    value_column = (
        "effect_value"
        if "effect_value" in frame.columns
        else "median_effect"
        if "median_effect" in frame.columns
        else ""
    )
    if not value_column:
        return pd.Series(dtype=float)

    frame[value_column] = safe_numeric(frame[value_column])
    frame = frame.dropna(subset=[value_column])
    frame = frame.drop_duplicates("feature_id")
    frame["label"] = frame["feature_id"].map(
        lambda value: display_label(str(value), labels)
    )
    return frame.set_index("label")[value_column].reindex(
        [
            display_label(module, labels)
            for module in modules
            if module in set(frame["feature_id"])
        ]
    )


def cellular_matrix(
    broad: pd.DataFrame,
    modules: Sequence[str],
    labels: Dict[str, str],
    value_column: str,
) -> pd.DataFrame:
    frame = broad[
        broad["feature_id"].astype(str).isin(modules)
    ].copy()
    if frame.empty or value_column not in frame.columns:
        return pd.DataFrame()

    frame[value_column] = safe_numeric(frame[value_column])
    matrix = frame.pivot_table(
        index="feature_id",
        columns="population",
        values=value_column,
        aggfunc="first",
    )
    preferred = [
        "macrophage_monocyte",
        "dendritic",
        "neutrophil",
        "T_cell",
        "NK_cell",
        "cycling_immune",
    ]
    matrix = matrix.reindex(
        index=[module for module in modules if module in matrix.index],
        columns=[column for column in preferred if column in matrix.columns],
    )
    matrix.index = [
        display_label(feature, labels) for feature in matrix.index
    ]
    return matrix


def subtype_top_series(
    synthesis: pd.DataFrame,
    modules: Sequence[str],
    labels: Dict[str, str],
) -> pd.Series:
    frame = synthesis[
        synthesis["feature_id"].astype(str).isin(modules)
    ].copy()
    if frame.empty:
        return pd.Series(dtype=float)

    score_column = "top_refined_subtype_composite_score"
    if score_column not in frame.columns:
        return pd.Series(dtype=float)

    frame[score_column] = safe_numeric(frame[score_column])
    frame = frame.dropna(subset=[score_column]).sort_values(
        score_column,
        ascending=False,
    )
    frame["label"] = frame.apply(
        lambda row: (
            f"{display_label(str(row['feature_id']), labels)}\n"
            f"[{str(row.get('top_refined_subtype', '')).replace('_', ' ')}]"
        ),
        axis=1,
    )
    return frame.set_index("label")[score_column].head(8)


def evidence_text(
    figure_id: str,
    modules: Sequence[str],
    synthesis: pd.DataFrame,
    labels: Dict[str, str],
) -> str:
    frame = synthesis[
        synthesis["feature_id"].astype(str).isin(modules)
    ].copy()

    lines = [
        f"{figure_id} synthesis",
        "",
        "Evidence layers:",
        "• Independent dataset effects",
        "• Pregnancy preterm-vs-term architecture",
        "• Broad-cell pseudobulk localization",
        "• Refined-subtype attribution",
        "",
    ]

    if not frame.empty and "cellular_localization_class" in frame.columns:
        class_counts = (
            frame["cellular_localization_class"]
            .fillna("unresolved")
            .value_counts()
        )
        lines.append("Cellular classes:")
        for class_name, count in class_counts.items():
            lines.append(
                f"• {class_name.replace('_', ' ')}: {int(count)}"
            )
        lines.append("")

        prioritized = frame.sort_values(
            "median_composite_score",
            ascending=False,
        ).head(3)
        lines.append("Highest cellular support:")
        for _, row in prioritized.iterrows():
            lines.append(
                "• "
                + display_label(str(row["feature_id"]), labels)
                + " — "
                + str(row.get("top_population_by_composite_score", "")).replace(
                    "_", " "
                )
            )

    lines.extend(
        [
            "",
            "Interpretation boundary:",
            "• Hedges g is not used alone.",
            "• Cells are not independent replicates.",
            "• Metabolic activity is transcriptionally inferred.",
        ]
    )
    return "\n".join(lines)


def add_text_panel(axis: plt.Axes, text: str, title: str) -> None:
    axis.set_title(title, fontsize=10)
    axis.text(
        0.02,
        0.98,
        text,
        transform=axis.transAxes,
        va="top",
        ha="left",
        fontsize=7.4,
        linespacing=1.28,
    )
    axis.set_axis_off()


def save_figure(
    figure: plt.Figure,
    output_dir: Path,
    stem: str,
) -> List[Path]:
    outputs = []
    for extension in ["png", "svg", "pdf"]:
        path = output_dir / f"{stem}.{extension}"
        figure.savefig(path, dpi=300, bbox_inches="tight")
        outputs.append(path)
    plt.close(figure)
    return outputs


def build_family_figure(
    figure_id: str,
    modules: Sequence[str],
    effects: pd.DataFrame,
    preterm: pd.DataFrame,
    broad: pd.DataFrame,
    synthesis: pd.DataFrame,
    labels: Dict[str, str],
    output_dir: Path,
) -> Tuple[List[Path], List[Dict[str, str]]]:
    log(f"Building {figure_id}.")
    figure = plt.figure(figsize=(JOURNAL_WIDTH_IN, FAMILY_FIGURE_HEIGHT_IN))
    axes = panel_axes(figure)

    independent = independent_effect_matrix(
        effects, modules, labels
    )
    add_heatmap(
        axes["A"],
        independent,
        "Independent infection-context effects",
        x_label="Dataset",
        y_label="Submodule",
    )

    pregnancy = preterm_series(preterm, modules, labels)
    add_barh(
        axes["B"],
        pregnancy,
        "Pregnancy preterm minus term",
        "Collapsed effect",
    )

    broad_logfc = cellular_matrix(
        broad,
        modules,
        labels,
        "module_mean_gene_log2FC",
    )
    add_heatmap(
        axes["C"],
        broad_logfc,
        "UPEC broad-cell module-gene log2 fold change",
        x_label="Broad immune population",
        y_label="Submodule",
    )

    subtype = subtype_top_series(
        synthesis,
        modules,
        labels,
    )
    add_barh(
        axes["D"],
        subtype,
        "Strongest refined-subtype cellular support",
        "Composite support score",
        zero_line=False,
    )

    for label, axis in axes.items():
        add_panel_label(axis, label)

    figure.suptitle(
        {
            "Figure_7": (
                "Figure 7. Steroid, cholesterol, receptor-response "
                "and lipid-remodeling architecture"
            ),
            "Figure_8": (
                "Figure 8. Adipokine, insulin/IRS, PI3K-AKT "
                "and inflammatory-carbon remodeling"
            ),
            "Figure_9": (
                "Figure 9. Amino-acid, nucleotide, nitrogen "
                "and redox remodeling"
            ),
            "Figure_10": (
                "Figure 10. Complement initiation, amplification, "
                "effector and regulatory architecture*"
            ),
        }[figure_id],
        fontsize=10.6,
        y=0.985,
    )
    if figure_id == "Figure_10":
        figure.text(
            0.17,
            0.025,
            "*Lectin and terminal-MAC modules lacked eligible GSE252321 "
            "cell-level coverage; infection and pregnancy evidence remain "
            "shown where available.",
            fontsize=6.2,
            ha="left",
        )

    outputs = save_figure(
        figure,
        output_dir,
        f"UTI_HostOmics_U27A2_{figure_id}",
    )

    panel_rows = [
        {
            "figure": figure_id,
            "panel": "A",
            "content": "Independent infection-context effects",
            "source": (
                "U26B2B.1 primary independent dataset effects"
            ),
        },
        {
            "figure": figure_id,
            "panel": "B",
            "content": "Pregnancy preterm-versus-term effects",
            "source": (
                "U26B2B.1 GSE280297 preterm-term collapsed"
            ),
        },
        {
            "figure": figure_id,
            "panel": "C",
            "content": "Broad-cell module mean gene log2 fold change",
            "source": "U26D2C broad effect reliability",
        },
        {
            "figure": figure_id,
            "panel": "D",
            "content": "Top refined-subtype composite support",
            "source": "U26D2C module cellular synthesis",
        },
    ]
    return outputs, panel_rows


def paired_core_matrix(
    effects: pd.DataFrame,
    preterm: pd.DataFrame,
    labels: Dict[str, str],
) -> pd.DataFrame:
    infection = independent_effect_matrix(
        effects,
        CORE_MODULES,
        labels,
    )
    pregnancy = preterm_series(
        preterm,
        CORE_MODULES,
        labels,
    )

    if infection.empty:
        matrix = pd.DataFrame(index=pregnancy.index)
    else:
        matrix = infection.copy()

    if not pregnancy.empty:
        matrix["GSE280297 preterm-term"] = pregnancy.reindex(matrix.index)
        missing = pregnancy.index.difference(matrix.index)
        if len(missing):
            additional = pd.DataFrame(
                index=missing,
                columns=matrix.columns,
                dtype=float,
            )
            additional["GSE280297 preterm-term"] = pregnancy.loc[missing]
            matrix = pd.concat([matrix, additional], axis=0)

    return matrix


def add_network(axis: plt.Axes) -> None:
    axis.set_title(
        "Integrated cell-source-resolved mechanistic network",
        fontsize=8.4,
    )
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.set_axis_off()

    nodes = {
        "TLR4": (0.10, 0.72),
        "NF-kB/MAPK": (0.30, 0.82),
        "PI3K-AKT": (0.31, 0.58),
        "Leptin/IRS": (0.10, 0.42),
        "Inflammatory carbon": (0.52, 0.58),
        "Complement C3a/C5a": (0.53, 0.85),
        "NETosis": (0.78, 0.80),
        "Purine-NRF2": (0.52, 0.30),
        "Ferroptosis/lipid": (0.78, 0.30),
        "Steroid response": (0.27, 0.18),
        "Pregnancy outcome": (0.78, 0.08),
    }

    sources = {
        "TLR4": "activated T",
        "NF-kB/MAPK": "dendritic/pan-immune",
        "PI3K-AKT": "regulatory-like T",
        "Leptin/IRS": "T cell/cDC1",
        "Inflammatory carbon": "pan-immune",
        "Complement C3a/C5a": "dendritic / cDC1",
        "NETosis": "neutrophil-linked",
        "Purine-NRF2": "dendritic/T cell",
        "Ferroptosis/lipid": "contextual",
        "Steroid response": "lymphoid + dendritic",
        "Pregnancy outcome": "pregnancy tissues",
    }

    edges = [
        ("TLR4", "NF-kB/MAPK"),
        ("TLR4", "PI3K-AKT"),
        ("Leptin/IRS", "PI3K-AKT"),
        ("PI3K-AKT", "Inflammatory carbon"),
        ("NF-kB/MAPK", "NETosis"),
        ("Complement C3a/C5a", "NETosis"),
        ("Purine-NRF2", "Ferroptosis/lipid"),
        ("Steroid response", "Pregnancy outcome"),
        ("Inflammatory carbon", "Pregnancy outcome"),
        ("Complement C3a/C5a", "Pregnancy outcome"),
        ("Ferroptosis/lipid", "Pregnancy outcome"),
    ]

    for source, target in edges:
        x1, y1 = nodes[source]
        x2, y2 = nodes[target]
        axis.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops={"arrowstyle": "->", "linewidth": 1.0},
        )

    for node, (x, y) in nodes.items():
        axis.scatter([x], [y], s=290)
        axis.text(
            x,
            y,
            node,
            ha="center",
            va="center",
            fontsize=5.8,
            fontweight="bold",
        )
        axis.text(
            x,
            y - 0.060,
            sources[node],
            ha="center",
            va="top",
            fontsize=4.8,
        )


def build_figure_11(
    effects: pd.DataFrame,
    preterm: pd.DataFrame,
    broad: pd.DataFrame,
    synthesis: pd.DataFrame,
    composition: pd.DataFrame,
    targeted: pd.DataFrame,
    labels: Dict[str, str],
    output_dir: Path,
) -> Tuple[List[Path], List[Dict[str, str]]]:
    log("Building Figure_11.")
    figure = plt.figure(figsize=(JOURNAL_WIDTH_IN, INTEGRATED_FIGURE_HEIGHT_IN))
    axes = panel_axes(figure)

    core_matrix = paired_core_matrix(
        effects,
        preterm,
        labels,
    )
    add_heatmap(
        axes["A"],
        core_matrix,
        "Core modules across infection contexts and pregnancy outcome",
        x_label="Evidence context",
        y_label="Core module",
    )

    core_cellular = cellular_matrix(
        broad,
        CORE_MODULES,
        labels,
        "cellular_localization_score",
    )
    add_heatmap(
        axes["B"],
        core_cellular,
        "Core cellular-localization support",
        x_label="Broad immune population",
        y_label="Core module",
    )

    composition_series = (
        composition.set_index("refined_broad_cell_type")[
            "difference_UPEC_minus_control"
        ]
        if not composition.empty
        else pd.Series(dtype=float)
    )
    targeted_series = (
        targeted.set_index("targeted_measure")[
            "difference_UPEC_minus_control"
        ]
        if not targeted.empty
        else pd.Series(dtype=float)
    )
    combined = pd.concat(
        [
            composition_series.rename(
                index=lambda value: str(value).replace("_", " ")
            ),
            targeted_series.rename(
                index=lambda value: str(value).replace("_", " ")
            ),
        ]
    )
    add_barh(
        axes["C"],
        combined,
        "Cell-composition and fixed targeted-state shifts",
        "UPEC minus control fraction",
    )

    add_network(axes["D"])

    for label, axis in axes.items():
        add_panel_label(axis, label)

    figure.suptitle(
        "Figure 11. Integrated endocrine-metabolic-immune model of "
        "urinary inflammation and pregnancy-associated UTI biology",
        fontsize=10.6,
        y=0.98,
    )

    outputs = save_figure(
        figure,
        output_dir,
        "UTI_HostOmics_U27A2_Figure_11",
    )

    panel_rows = [
        {
            "figure": "Figure_11",
            "panel": "A",
            "content": (
                "Core independent infection effects plus preterm-term outcome"
            ),
            "source": "U26B2B.1 independent effects and pregnancy collapse",
        },
        {
            "figure": "Figure_11",
            "panel": "B",
            "content": "Core broad-cell composite localization",
            "source": "U26D2C broad effect reliability",
        },
        {
            "figure": "Figure_11",
            "panel": "C",
            "content": "Cell composition and fixed targeted states",
            "source": "U26D2B composition and targeted-state effects",
        },
        {
            "figure": "Figure_11",
            "panel": "D",
            "content": "Integrated mechanistic network",
            "source": "U26C/U26D2C synthesis architecture",
        },
    ]
    return outputs, panel_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    plt.rcParams.update(
        {
            "font.size": 7.0,
            "axes.titlesize": 8.4,
            "axes.labelsize": 7.2,
            "xtick.labelsize": 6.4,
            "ytick.labelsize": 6.4,
            "legend.fontsize": 6.2,
            "figure.titlesize": 10.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )

    effects_path = require(
        project
        / "06_tables"
        / B2B1_TAG
        / "UTI_HostOmics_U26B2B1_primary_independent_dataset_effects.tsv"
    )
    preterm_path = require(
        project
        / "06_tables"
        / B2B1_TAG
        / "UTI_HostOmics_U26B2B1_GSE280297_preterm_term_collapsed.tsv"
    )
    broad_path = require(
        project
        / "06_tables"
        / D2C_TAG
        / "UTI_HostOmics_U26D2C_broad_effect_reliability.tsv"
    )
    synthesis_path = require(
        project
        / "06_tables"
        / D2C_TAG
        / "UTI_HostOmics_U26D2C_module_cellular_synthesis.tsv"
    )
    composition_path = require(
        project
        / "06_tables"
        / D2B_TAG
        / "UTI_HostOmics_U26D2B_celltype_composition_effects.tsv"
    )
    targeted_path = require(
        project
        / "06_tables"
        / D2B_TAG
        / "UTI_HostOmics_U26D2B_targeted_state_effects.tsv"
    )
    d2c_decision_path = require(
        project
        / "06_tables"
        / D2C_TAG
        / "UTI_HostOmics_U26D2C_phase_decision.tsv"
    )

    out_figures = project / "06_figures" / TAG
    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG

    for directory in [
        out_figures, out_tables, out_metadata, out_results
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    effects = read_tsv(effects_path)
    preterm = read_tsv(preterm_path)
    broad = read_tsv(broad_path)
    synthesis = read_tsv(synthesis_path)
    composition = read_tsv(composition_path)
    targeted = read_tsv(targeted_path)
    decision = read_tsv(d2c_decision_path)

    if not decision["decision"].astype(str).str.startswith("READY").all():
        raise RuntimeError("U26D2C is not in a READY state.")

    label_table = synthesis[
        ["feature_id", "display_label"]
    ].drop_duplicates("feature_id")
    labels = dict(
        zip(
            label_table["feature_id"].astype(str),
            label_table["display_label"].astype(str),
        )
    )

    output_rows: List[Dict[str, object]] = []
    panel_rows: List[Dict[str, str]] = []

    for figure_id, modules in FIGURE_MODULES.items():
        outputs, panels = build_family_figure(
            figure_id,
            modules,
            effects,
            preterm,
            broad,
            synthesis,
            labels,
            out_figures,
        )
        for path in outputs:
            output_rows.append(
                {
                    "figure": figure_id,
                    "path": str(path),
                    "format": path.suffix.lstrip("."),
                    "size_bytes": path.stat().st_size,
                }
            )
        panel_rows.extend(panels)

    outputs, panels = build_figure_11(
        effects,
        preterm,
        broad,
        synthesis,
        composition,
        targeted,
        labels,
        out_figures,
    )
    for path in outputs:
        output_rows.append(
            {
                "figure": "Figure_11",
                "path": str(path),
                "format": path.suffix.lstrip("."),
                "size_bytes": path.stat().st_size,
            }
        )
    panel_rows.extend(panels)

    output_manifest = pd.DataFrame(output_rows)
    output_manifest.to_csv(
        out_tables / "UTI_HostOmics_U27A2_figure_output_manifest.tsv",
        sep="\t",
        index=False,
    )

    panel_manifest = pd.DataFrame(panel_rows)
    panel_manifest.to_csv(
        out_metadata / "UTI_HostOmics_U27A2_panel_source_manifest.tsv",
        sep="\t",
        index=False,
    )

    figure_summary_rows = []
    for figure_id, modules in FIGURE_MODULES.items():
        available = [
            module
            for module in modules
            if module in set(synthesis["feature_id"].astype(str))
        ]
        unavailable = [
            module for module in modules if module not in available
        ]
        figure_summary_rows.append(
            {
                "figure": figure_id,
                "n_requested_modules": len(modules),
                "n_available_modules": len(available),
                "available_modules": ";".join(available),
                "unavailable_modules": ";".join(unavailable),
            }
        )
    figure_summary_rows.append(
        {
            "figure": "Figure_11",
            "n_requested_modules": len(CORE_MODULES),
            "n_available_modules": sum(
                module in set(synthesis["feature_id"].astype(str))
                for module in CORE_MODULES
            ),
            "available_modules": ";".join(
                [
                    module
                    for module in CORE_MODULES
                    if module in set(synthesis["feature_id"].astype(str))
                ]
            ),
            "unavailable_modules": ";".join(
                [
                    module
                    for module in CORE_MODULES
                    if module not in set(synthesis["feature_id"].astype(str))
                ]
            ),
        }
    )
    figure_summary = pd.DataFrame(figure_summary_rows)
    figure_summary.to_csv(
        out_tables / "UTI_HostOmics_U27A2_figure_module_summary.tsv",
        sep="\t",
        index=False,
    )

    expected_figures = {
        "Figure_7", "Figure_8", "Figure_9", "Figure_10", "Figure_11"
    }
    produced_figures = set(output_manifest["figure"].astype(str))
    formats_per_figure = (
        output_manifest.groupby("figure")["format"].nunique()
        if not output_manifest.empty
        else pd.Series(dtype=int)
    )

    ready = (
        produced_figures == expected_figures
        and all(formats_per_figure.get(figure, 0) == 3 for figure in expected_figures)
        and (figure_summary["n_available_modules"] >= 7).all()
    )

    phase_decision = (
        "READY_FOR_U27B_RESULTS_DISCUSSION_AND_LEGEND_INTEGRATION"
        if ready
        else "TARGETED_JOURNAL_WIDTH_FIGURE_REVIEW_REQUIRED"
    )

    pd.DataFrame(
        [
            {
                "phase": "U27A.2",
                "decision": phase_decision,
                "n_figures_expected": 5,
                "n_figures_produced": len(produced_figures),
                "n_output_files": len(output_manifest),
                "png_svg_pdf_for_each_figure": bool(
                    all(
                        formats_per_figure.get(figure, 0) == 3
                        for figure in expected_figures
                    )
                ),
                "manuscript_modified": False,
                "existing_figures_1_to_6_modified": False,
                "metabolic_flux_claims_used": False,
                "cells_treated_as_independent_replicates": False,
                "next_phase": (
                    "U27B integrate Results, Discussion and figure legends"
                    if ready
                    else "Inspect figure renders and repair targeted panels"
                ),
            }
        ]
    ).to_csv(
        out_tables / "UTI_HostOmics_U27A2_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results / "UTI_HostOmics_U27A2_figure_build_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27A.2 - Figures 7-11 build report\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{phase_decision}**\n")
        handle.write(
            f"- Figure families produced: **{len(produced_figures)}/5**.\n"
        )
        handle.write(
            f"- Output files produced: **{len(output_manifest)}**.\n"
        )
        handle.write(
            "- Formats requested for each figure: PNG, SVG and PDF at 180-mm width.\n"
        )
        handle.write(
            "- Manuscript and existing Figures 1-6 were not modified.\n\n"
        )
        handle.write("## Figure architecture\n\n")
        handle.write(
            "- **Figure 7:** steroid, cholesterol, receptor-response and "
            "lipid-remodeling architecture.\n"
        )
        handle.write(
            "- **Figure 8:** adipokine, insulin/IRS, PI3K-AKT and "
            "inflammatory-carbon remodeling.\n"
        )
        handle.write(
            "- **Figure 9:** amino-acid, nucleotide, nitrogen and redox "
            "remodeling.\n"
        )
        handle.write(
            "- **Figure 10:** complement initiation, amplification, effector "
            "and regulatory architecture.\n"
        )
        handle.write(
            "- **Figure 11:** integrated cross-dataset, pregnancy-outcome, "
            "cellular and mechanistic synthesis.\n\n"
        )
        handle.write("## Journal-width repair\\n\\n")
        handle.write(
            "- Figures were rebuilt directly at 180-mm width rather "
            "than reduced from an 18-inch source canvas.\\n"
            "- Dense heatmap cell annotations were removed.\\n"
            "- Module labels were shortened without changing biological meaning.\\n"
            "- Panel, axis, tick and color-bar typography was enlarged.\\n"
            "- Figure 11 network labels were simplified.\\n\\n"
        )
        handle.write("## Interpretation boundaries\\n\\n")
        handle.write(
            "- U26D2C composite support rather than Hedges g alone is used "
            "for cellular prioritization.\n"
        )
        handle.write(
            "- GSE252321 cellular comparisons retain the four biological "
            "samples as inferential units.\n"
        )
        handle.write(
            "- Metabolic panels describe transcriptionally inferred pathway "
            "activity, not measured flux.\n"
        )
        handle.write(
            "- Pregnancy preterm-versus-term effects remain discovery-level "
            "because broad FDR support was absent.\n"
        )

    run_manifest = {
        "version": VERSION,
        "decision": phase_decision,
        "n_figures_produced": int(len(produced_figures)),
        "n_output_files": int(len(output_manifest)),
        "manuscript_modified": False,
        "existing_figures_1_to_6_modified": False,
    }
    (
        out_results / "UTI_HostOmics_U27A2_run_manifest.json"
    ).write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    log(f"Figures produced: {len(produced_figures)}/5")
    log(f"Output files: {len(output_manifest)}")
    log(f"Decision: {phase_decision}")
    log(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27A] ERROR: {exc}", file=sys.stderr)
        raise
