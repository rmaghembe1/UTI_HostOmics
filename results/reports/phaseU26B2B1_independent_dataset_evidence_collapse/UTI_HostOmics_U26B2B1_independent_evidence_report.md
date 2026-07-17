# Phase U26B2B.1 - Independent-dataset evidence collapse

- Version: `U26B2B1_v1.0_2026-07-14`
- Manuscript and existing Figures 1-6 were not modified.
- One primary infection-context effect per dataset and module was used for cross-dataset recurrence.

## Evidence-collapse rules

- GSE112098: age/sex-adjusted sepsis-versus-vascular-surgery effect only; unadjusted results are sensitivity evidence.
- GSE186800: average Gardnerella-versus-PBS effect only; block and interaction effects are reported separately.
- GSE280297: median UPEC-versus-PBS pregnancy effect across bladder, uterus and placenta, retaining tissue coherence.
- GSE252321: one UPEC-versus-control sample-pseudobulk effect, down-weighted because n=2 per group.

## Independent-dataset recurrence

- **limited_independent_support**: 47 modules.
- **context_divergent_or_tissue_specific**: 21 modules.
- **one_FDR_dataset_plus_independent_concordant_effect**: 5 modules.
- **two_dataset_concordant_effect**: 5 modules.

- `LEPTIN_SIGNALING`: one_FDR_dataset_plus_independent_concordant_effect; 1 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=1.00).
- `GLYCOLYSIS`: context_divergent_or_tissue_specific; 1 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction negative (weighted coherence=0.62).
- `COMPLEMENT_C3A_C5A_SIGNALING`: one_FDR_dataset_plus_independent_concordant_effect; 1 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM`: context_divergent_or_tissue_specific; 1 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction negative (weighted coherence=0.62).
- `NFKB_MAPK_INFLAMMATION_ANCHOR`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=1.00).
- `RESISTIN_INFLAMMATORY_SIGNALING`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=1.00).
- `GLUCOCORTICOID_RESPONSE`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=1.00).
- `PREGNANCY_INFLAMMATION_ANCHOR`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=1.00).
- `NEUTROPHIL_NETOSIS_ANCHOR`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `LACTATE_HIF1A_INFLAMMATORY_GLYCOLYSIS`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `FERROPTOSIS_LIPID_PEROXIDATION`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `NITRIC_OXIDE_SYNTHESIS_REGULATION`: context_divergent_or_tissue_specific; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction negative (weighted coherence=0.62).
- `ADIPOKINE_INFLAMMATORY_AXIS`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `ARGININE_NO_UREA`: context_divergent_or_tissue_specific; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction negative (weighted coherence=0.62).
- `TLR4_LPS_SIGNALING_ANCHOR`: one_FDR_dataset_plus_independent_concordant_effect; 1 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=1.00).
- `PI3K_AKT_SIGNALING`: one_FDR_dataset_plus_independent_concordant_effect; 1 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=1.00).
- `COMPLEMENT_OPSONOPHAGOCYTOSIS`: one_FDR_dataset_plus_independent_concordant_effect; 1 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `OXIDATIVE_STRESS_NRF2_ANCHOR`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=1.00).
- `PPARG_ADIPOMETABOLIC_REGULATION`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `ESTROGEN_RECEPTOR_RESPONSE`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `CATECHOLAMINE_IRON_REDOX_INTERFACE`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `AGE_RAGE_SIGNALING`: limited_independent_support; 1 independent FDR<0.10 datasets; 1 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `GLYCOGEN_SYNTHESIS`: two_dataset_concordant_effect; 0 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `AMINO_ACID_TRANSPORT`: two_dataset_concordant_effect; 0 independent FDR<0.10 datasets; 2 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `FATTY_ACID_BETA_OXIDATION`: limited_independent_support; 1 independent FDR<0.10 datasets; 0 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.92).
- `PYRIMIDINE_DEGRADATION`: limited_independent_support; 1 independent FDR<0.10 datasets; 0 datasets with |effect|>=0.5; dominant direction negative (weighted coherence=0.69).
- `PENTOSE_PHOSPHATE_PATHWAY`: context_divergent_or_tissue_specific; 1 independent FDR<0.10 datasets; 0 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.62).
- `COMPLEMENT_ALTERNATIVE`: limited_independent_support; 1 independent FDR<0.10 datasets; 0 datasets with |effect|>=0.5; dominant direction negative (weighted coherence=0.69).
- `PPAR_SREBP_LXR_REGULATION`: limited_independent_support; 1 independent FDR<0.10 datasets; 0 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.69).
- `ESTROGEN_BIOSYNTHESIS`: context_divergent_or_tissue_specific; 1 independent FDR<0.10 datasets; 0 datasets with |effect|>=0.5; dominant direction positive (weighted coherence=0.62).

## GSE186800 interpretation boundary

- FDR<0.10 block or interaction effects: **3**.
- PBS block effects are exposure-stage or experimental-block differences and must not be described as Gardnerella-induced pathway changes.

## GSE280297 pregnancy outcome architecture

- `INFLAMMATORY_CARBON_USE_INDEX`: median tissue effect -1.153; tissue coherence 1.00; direction negative.
- `ESTROGEN_RECEPTOR_RESPONSE`: median tissue effect -0.911; tissue coherence 1.00; direction negative.
- `AMINO_ACID_TRANSPORT`: median tissue effect -0.911; tissue coherence 1.00; direction negative.
- `GLUCOCORTICOID_RESPONSE`: median tissue effect -0.826; tissue coherence 1.00; direction negative.
- `ANDROGEN_RECEPTOR_SIGNALING`: median tissue effect -0.804; tissue coherence 1.00; direction negative.
- `LEPTIN_SIGNALING`: median tissue effect -0.752; tissue coherence 1.00; direction negative.
- `STEROIDOGENESIS_CORE`: median tissue effect 0.698; tissue coherence 1.00; direction positive.
- `INSULIN_RECEPTOR_IRS`: median tissue effect -0.676; tissue coherence 1.00; direction negative.
- `PI3K_AKT_SIGNALING`: median tissue effect -0.635; tissue coherence 1.00; direction negative.
- `COMPLEMENT_TERMINAL_MAC`: median tissue effect 0.574; tissue coherence 0.67; direction positive.
- `PREGNANCY_INFLAMMATION_ANCHOR`: median tissue effect -0.559; tissue coherence 0.67; direction negative.
- `ANDROGEN_TESTOSTERONE_BIOSYNTHESIS`: median tissue effect 0.512; tissue coherence 1.00; direction positive.
- `RESISTIN_INFLAMMATORY_SIGNALING`: median tissue effect -0.506; tissue coherence 0.67; direction negative.
- `PROGESTERONE_BIOSYNTHESIS_RESPONSE`: median tissue effect -0.503; tissue coherence 1.00; direction negative.
- `FATTY_ACID_SYNTHESIS`: median tissue effect -0.501; tissue coherence 1.00; direction negative.
- `COMPLEMENT_C3A_C5A_SIGNALING`: median tissue effect -0.497; tissue coherence 0.67; direction negative.
- `MINERALOCORTICOID_RESPONSE`: median tissue effect -0.495; tissue coherence 1.00; direction negative.
- `COMPLEMENT_CLASSICAL`: median tissue effect 0.474; tissue coherence 1.00; direction positive.
- `STEROID_SULFATION_DESULFATION`: median tissue effect -0.473; tissue coherence 1.00; direction negative.
- `ADRENERGIC_STRESS_SIGNALING`: median tissue effect -0.460; tissue coherence 0.67; direction negative.

## Evidence hierarchy

- Human adjusted FDR evidence is the strongest inferential layer, but it represents systemic urinary inflammation rather than UTI.
- GSE186800 treatment effects provide independent mouse-bladder support; its significant PBS block effects are not infection validation.
- GSE280297 provides pregnancy and tissue architecture, with limited contrast-wide FDR support.
- GSE252321 provides exploratory whole-study UPEC direction only until cell-type pseudobulk reconstruction is available.
