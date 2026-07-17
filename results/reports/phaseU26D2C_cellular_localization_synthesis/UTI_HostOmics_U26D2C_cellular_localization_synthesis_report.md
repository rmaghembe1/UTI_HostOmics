# Phase U26D2C - Cellular-localization synthesis

- Version: `U26D2C_v1.0_2026-07-14`
- Decision: **READY_FOR_U27_FIGURE_7_TO_11_BUILD_AND_MANUSCRIPT_INTEGRATION_WITH_CELLULAR_ATTRIBUTION**
- Hedges g was not used alone to rank cellular biology.
- Biological samples remain the inferential units.
- Manuscript and existing Figures 1-6 were not modified.

## Central cellular architecture

UPEC exposure produced a myeloid-dominant compositional shift, with neutrophil and macrophage/monocyte expansion and relative contraction of T-cell, dendritic, NK-cell, cycling-immune and mast-cell fractions. Within the retained populations, the inflammatory-metabolic response was not confined to the expanded myeloid cells: several TLR4/NF-kB, adipokine, glycolytic, NETosis, C3a/C5a and pregnancy-inflammation gene programmes were directionally coherent across lymphoid and myeloid compartments.

## Core module cellular attribution

- **C3a and C5a inflammatory signaling**: `coherent_pan_immune_higher_in_UPEC`; strongest composite broad localization in `dendritic` and refined localization in `XCR1_CLEC9A_cDC1_like`. High/moderate support occurred in 6 broad populations.
- **Glycogen synthesis**: `coherent_pan_immune_higher_in_UPEC`; strongest composite broad localization in `neutrophil` and refined localization in `LY6C2_VCAN_inflammatory_monocyte`. High/moderate support occurred in 4 broad populations.
- **Fatty-acid synthesis**: `branch_divergent`; strongest composite broad localization in `cycling_immune` and refined localization in `IL2RA_TNFRSF18_regulatory_type2_like_T`. High/moderate support occurred in 4 broad populations.
- **Insulin receptor and IRS signaling**: `coherent_pan_immune_higher_in_UPEC`; strongest composite broad localization in `T_cell` and refined localization in `IL2RA_TNFRSF18_regulatory_type2_like_T`. High/moderate support occurred in 4 broad populations.
- **Androgen receptor signaling**: `coherent_pan_immune_higher_in_UPEC`; strongest composite broad localization in `dendritic` and refined localization in `CD209A_CLEC10A_cDC2_like`. High/moderate support occurred in 4 broad populations.
- **Amino-acid transport**: `multi_compartment_contextual`; strongest composite broad localization in `dendritic` and refined localization in `cytotoxic_NK`. High/moderate support occurred in 3 broad populations.
- **Leptin signaling**: `multi_compartment_contextual`; strongest composite broad localization in `T_cell` and refined localization in `XCR1_CLEC9A_cDC1_like`. High/moderate support occurred in 3 broad populations.
- **PI3K-AKT signaling**: `multi_compartment_contextual`; strongest composite broad localization in `T_cell` and refined localization in `IL2RA_TNFRSF18_regulatory_type2_like_T`. High/moderate support occurred in 2 broad populations.
- **TLR4-LPS signaling anchor**: `lymphoid_dominant`; strongest composite broad localization in `T_cell` and refined localization in `conventional_activated_T`. High/moderate support occurred in 2 broad populations.
- **Complement-opsonophagocytosis**: `myeloid_dominant`; strongest composite broad localization in `dendritic` and refined localization in `CD83_CLEC10A_activated_dendritic`. High/moderate support occurred in 1 broad populations.

## Composition effects

- `neutrophil`: control 0.035, UPEC 0.245, difference +0.210.
- `T_cell`: control 0.222, UPEC 0.090, difference -0.132.
- `dendritic`: control 0.268, UPEC 0.165, difference -0.103.
- `macrophage_monocyte`: control 0.340, UPEC 0.437, difference +0.097.
- `cycling_immune`: control 0.053, UPEC 0.017, difference -0.036.
- `NK_cell`: control 0.071, UPEC 0.045, difference -0.025.
- `mast_cell`: control 0.012, UPEC 0.002, difference -0.010.

## Fixed targeted states

- `TNFSF9_high_fraction_within_macrophage`: control 0.037, UPEC 0.080, difference +0.043.
- `TNFSF9_positive_fraction_within_macrophage`: control 0.171, UPEC 0.304, difference +0.132.
- `expanded_Treg_like_fraction_within_T`: control 0.306, UPEC 0.391, difference +0.085.
- `strict_Treg_like_fraction_within_T`: control 0.017, UPEC 0.083, difference +0.066.

## Interpretation safeguards

Very large standardized effects can arise when two samples per group have minimal within-group variance. Such effects are retained for transparency but are flagged as variance-sensitive. Figure and manuscript prioritization uses module-gene fold change, gene-direction coherence and cross-population consistency together with the standardized effect. Cell-type localization is not proof of an exclusive cellular source, and all metabolic modules remain transcriptionally inferred rather than direct metabolic flux measurements.
