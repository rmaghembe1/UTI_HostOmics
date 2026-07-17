# Phase U26D2A.1 - GSE252321 annotation refinement

- Version: `U26D2A1_v1.0_2026-07-14`
- Decision: **READY_FOR_U26D2B_REFINED_CELLTYPE_PSEUDOBULK_SCORING**
- QC-passing cells retained: **27,385**.
- Clusters receiving a changed broad label: **4**.
- Refined broad cell classes: **7**.
- Refined biological subtypes/states: **18**.

## Major annotation corrections

- Cluster 1: `mixed_low_confidence` -> `macrophage_monocyte` / `LY6C2_VCAN_inflammatory_monocyte` based on LY6C2/CHIL3/VCAN/FCGR1/CCL2.
- Cluster 6: `fibroblast` -> `macrophage_monocyte` / `RETNLA_MRC1_reparative_macrophage` based on RETNLA/LPL/MRC1/C1QA-C/LYZ1.
- Cluster 7: `mixed_low_confidence` -> `dendritic` / `CD83_CLEC10A_activated_dendritic` based on CD83/CLEC10A/CD209A/CCR7/H2-DMB2.
- Cluster 11: `dendritic` -> `cycling_immune` / `MKI67_TOP2A_cycling_immune` based on MKI67/TOP2A/PCLAF/UBE2C/BIRC5.

## Targeted-state correction

The earlier sample-specific 80th-percentile definitions forced approximately 20% of each parent population to be called Treg or CD137L-high and therefore could not test biological enrichment. They have been retired. Treg-like candidates now use fixed marker logic, and macrophage TNFSF9-high status uses one pooled threshold applied unchanged to all four samples.

- `GSM7999426_Control_1` strict_Treg_like_fraction_within_T: 22/1129 (0.019).
- `GSM7999426_Control_1` expanded_Treg_like_fraction_within_T: 404/1129 (0.358).
- `GSM7999426_Control_1` TNFSF9_positive_fraction_within_macrophage: 492/2030 (0.242).
- `GSM7999426_Control_1` TNFSF9_high_fraction_within_macrophage: 93/2030 (0.046).
- `GSM7999427_Control_2` strict_Treg_like_fraction_within_T: 31/2134 (0.015).
- `GSM7999427_Control_2` expanded_Treg_like_fraction_within_T: 541/2134 (0.254).
- `GSM7999427_Control_2` TNFSF9_positive_fraction_within_macrophage: 285/2842 (0.100).
- `GSM7999427_Control_2` TNFSF9_high_fraction_within_macrophage: 79/2842 (0.028).
- `GSM7999428_UPEC_1` strict_Treg_like_fraction_within_T: 54/520 (0.104).
- `GSM7999428_UPEC_1` expanded_Treg_like_fraction_within_T: 207/520 (0.398).
- `GSM7999428_UPEC_1` TNFSF9_positive_fraction_within_macrophage: 757/2822 (0.268).
- `GSM7999428_UPEC_1` TNFSF9_high_fraction_within_macrophage: 203/2822 (0.072).
- `GSM7999429_UPEC_2` strict_Treg_like_fraction_within_T: 39/625 (0.062).
- `GSM7999429_UPEC_2` expanded_Treg_like_fraction_within_T: 240/625 (0.384).
- `GSM7999429_UPEC_2` TNFSF9_positive_fraction_within_macrophage: 953/2809 (0.339).
- `GSM7999429_UPEC_2` TNFSF9_high_fraction_within_macrophage: 247/2809 (0.088).

## Statistical boundary

Cell identities and targeted-state fractions remain descriptive. All UPEC-versus-control pathway inference in U26D2B will use the four biological samples as the independent units.
