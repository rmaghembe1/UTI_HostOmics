# Phase U26D2B - Refined cell-type pseudobulk scoring

- Version: `U26D2B_v1.1_2026-07-14`
- Decision: **READY_FOR_U26D2C_CELLULAR_LOCALIZATION_SYNTHESIS_AND_U27_FIGURE_INTEGRATION**
- Module dictionary: `project://03_metadata/phaseU26A_expanded_endocrine_metabolic_immune_feasibility/UTI_HostOmics_U26A_expanded_submodule_library.tsv`.
- Modules in dictionary: **78**.
- Score-eligible modules: **73**.
- Common mouse genes: **19,386**.
- Complete broad cell populations: **6**.
- Complete refined subtypes: **14**.

## Statistical boundary

Every pathway comparison uses two control and two UPEC biological samples. Cells were aggregated before scoring. The exact permutation p values therefore have very low resolution (minimum observed 0.333) and cannot establish conventional statistical significance. Cellular localization is based primarily on Hedges g, module gene log2 fold change and within-module gene-direction coherence.

## Broad cellular localization priorities

- **Pregnancy-associated inflammation anchor**: strongest absolute effect in `NK_cell` (g=3.489); dominant direction `higher_in_UPEC`; 6 broad populations with |g|>=0.5.
- **Neutrophil and NETosis anchor**: strongest absolute effect in `cycling_immune` (g=1.973); dominant direction `higher_in_UPEC`; 6 broad populations with |g|>=0.5.
- **Resistin-associated inflammatory signaling**: strongest absolute effect in `NK_cell` (g=3.700); dominant direction `higher_in_UPEC`; 6 broad populations with |g|>=0.5.
- **Lactate and HIF1A inflammatory glycolysis**: strongest absolute effect in `T_cell` (g=2.504); dominant direction `higher_in_UPEC`; 6 broad populations with |g|>=0.5.
- **Nitric-oxide synthesis and regulation**: strongest absolute effect in `cycling_immune` (g=5.492); dominant direction `higher_in_UPEC`; 5 broad populations with |g|>=0.5.
- **Arginine, nitric oxide and urea coupling**: strongest absolute effect in `dendritic` (g=6.359); dominant direction `higher_in_UPEC`; 5 broad populations with |g|>=0.5.
- **Leptin signaling**: strongest absolute effect in `macrophage_monocyte` (g=5.159); dominant direction `higher_in_UPEC`; 5 broad populations with |g|>=0.5.
- **Glucocorticoid response**: strongest absolute effect in `T_cell` (g=3.477); dominant direction `higher_in_UPEC`; 5 broad populations with |g|>=0.5.
- **Glycogen synthesis**: strongest absolute effect in `neutrophil` (g=2.610); dominant direction `higher_in_UPEC`; 4 broad populations with |g|>=0.5.
- **NF-kB and MAPK inflammation anchor**: strongest absolute effect in `NK_cell` (g=2.256); dominant direction `higher_in_UPEC`; 6 broad populations with |g|>=0.5.
- **Ferroptosis-linked lipid peroxidation**: strongest absolute effect in `NK_cell` (g=28.218); dominant direction `higher_in_UPEC`; 4 broad populations with |g|>=0.5.
- **Glycolysis**: strongest absolute effect in `dendritic` (g=2.232); dominant direction `higher_in_UPEC`; 4 broad populations with |g|>=0.5.
- **C3a and C5a inflammatory signaling**: strongest absolute effect in `dendritic` (g=1.278); dominant direction `higher_in_UPEC`; 6 broad populations with |g|>=0.5.
- **Insulin receptor and IRS signaling**: strongest absolute effect in `NK_cell` (g=1.399); dominant direction `higher_in_UPEC`; 4 broad populations with |g|>=0.5.
- **Core steroidogenesis**: strongest absolute effect in `cycling_immune` (g=2.964); dominant direction `lower_in_UPEC`; 3 broad populations with |g|>=0.5.
- **Estrogen receptor response**: strongest absolute effect in `NK_cell` (g=1.702); dominant direction `higher_in_UPEC`; 3 broad populations with |g|>=0.5.
- **PI3K-AKT signaling**: strongest absolute effect in `dendritic` (g=1.009); dominant direction `higher_in_UPEC`; 4 broad populations with |g|>=0.5.
- **Androgen receptor signaling**: strongest absolute effect in `NK_cell` (g=0.908); dominant direction `higher_in_UPEC`; 4 broad populations with |g|>=0.5.
- **Xanthine oxidase and oxidative purine catabolism**: strongest absolute effect in `dendritic` (g=1.568); dominant direction `higher_in_UPEC`; 5 broad populations with |g|>=0.5.
- **TLR4-LPS signaling anchor**: strongest absolute effect in `dendritic` (g=1.239); dominant direction `higher_in_UPEC`; 3 broad populations with |g|>=0.5.
- **Alternative complement pathway**: strongest absolute effect in `neutrophil` (g=-0.708); dominant direction `higher_in_UPEC`; 2 broad populations with |g|>=0.5.
- **Complement-opsonophagocytosis**: strongest absolute effect in `dendritic` (g=0.603); dominant direction `higher_in_UPEC`; 1 broad populations with |g|>=0.5.
- **Classical complement pathway**: strongest absolute effect in `dendritic` (g=0.738); dominant direction `lower_in_UPEC`; 1 broad populations with |g|>=0.5.

## Composition and targeted states

- `neutrophil` fraction: control=0.035, UPEC=0.245, difference=0.210.
- `T_cell` fraction: control=0.222, UPEC=0.090, difference=-0.132.
- `dendritic` fraction: control=0.268, UPEC=0.165, difference=-0.103.
- `macrophage_monocyte` fraction: control=0.340, UPEC=0.437, difference=0.097.
- `cycling_immune` fraction: control=0.053, UPEC=0.017, difference=-0.036.
- `NK_cell` fraction: control=0.071, UPEC=0.045, difference=-0.025.
- `mast_cell` fraction: control=0.012, UPEC=0.002, difference=-0.010.
- `TNFSF9_high_fraction_within_macrophage`: control=0.037, UPEC=0.080, difference=0.043.
- `TNFSF9_positive_fraction_within_macrophage`: control=0.171, UPEC=0.304, difference=0.132.
- `expanded_Treg_like_fraction_within_T`: control=0.306, UPEC=0.391, difference=0.085.
- `strict_Treg_like_fraction_within_T`: control=0.017, UPEC=0.083, difference=0.066.
