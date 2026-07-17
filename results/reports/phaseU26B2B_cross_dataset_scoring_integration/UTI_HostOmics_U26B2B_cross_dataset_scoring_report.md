# Phase U26B2B - Cross-dataset endocrine-metabolic-immune scoring

- Version: `U26B2B_v1.0_2026-07-14`
- Manuscript and existing Figures 1-6 were not modified.
- Raw expression was never pooled across datasets or species.
- GSE252321 cell-type pseudobulk remains deferred.

## GSE186800

- Factorial feature-level results: **405**
- Results at model FDR < 0.05: **0**
- Results at model FDR < 0.10: **3**

- `SERINE_GLYCINE_ONE_CARBON`, GSE186800_BLOCK_MAIN_PBS: beta=0.895, FDR=0.06389.
- `CHOLESTEROL_BIOSYNTHESIS`, GSE186800_BLOCK_MAIN_PBS: beta=1.051, FDR=0.09851.
- `ESTROGEN_BIOSYNTHESIS`, GSE186800_BLOCK_MAIN_PBS: beta=0.807, FDR=0.09851.
- `OXIDATIVE_STRESS_NRF2_ANCHOR`, GSE186800_AVERAGE_TREATMENT: beta=0.263, FDR=0.2069.
- `PPAR_SREBP_LXR_REGULATION`, GSE186800_AVERAGE_TREATMENT: beta=0.459, FDR=0.2069.
- `SPHINGOLIPID_CERAMIDE_METABOLISM`, GSE186800_AVERAGE_TREATMENT: beta=0.642, FDR=0.2069.
- `PHOSPHOLIPID_METABOLISM`, GSE186800_AVERAGE_TREATMENT: beta=0.539, FDR=0.2069.
- `ANDROGEN_RECEPTOR_SIGNALING`, GSE186800_AVERAGE_TREATMENT: beta=0.607, FDR=0.2069.
- `GLYCOGEN_SYNTHESIS`, GSE186800_AVERAGE_TREATMENT: beta=0.594, FDR=0.2069.
- `MTORC1_INSULIN_OUTPUT`, GSE186800_AVERAGE_TREATMENT: beta=0.781, FDR=0.2069.
- `AMPK_INSULIN_COUNTERREGULATION`, GSE186800_AVERAGE_TREATMENT: beta=0.874, FDR=0.2069.
- `PI3K_AKT_SIGNALING`, GSE186800_AVERAGE_TREATMENT: beta=0.712, FDR=0.2069.
- `MTOR_SIGNALING`, GSE186800_AVERAGE_TREATMENT: beta=0.212, FDR=0.2069.
- `INSULIN_RECEPTOR_IRS`, GSE186800_AVERAGE_TREATMENT: beta=0.659, FDR=0.2069.
- `AMPK_SIGNALING`, GSE186800_AVERAGE_TREATMENT: beta=0.572, FDR=0.2069.
- `FATTY_ACID_BETA_OXIDATION`, GSE186800_AVERAGE_TREATMENT: beta=0.402, FDR=0.2069.
- `AMINO_ACID_TRANSPORT`, GSE186800_AVERAGE_TREATMENT: beta=0.541, FDR=0.2069.
- `PPARG_ADIPOMETABOLIC_REGULATION`, GSE186800_AVERAGE_TREATMENT: beta=0.448, FDR=0.2069.
- `ADIPONECTIN_SIGNALING`, GSE186800_AVERAGE_TREATMENT: beta=0.577, FDR=0.2069.
- `LEPTIN_SIGNALING`, GSE186800_AVERAGE_TREATMENT: beta=0.729, FDR=0.2069.

## GSE112098

- Group-resolution status: **resolved_41_sepsis_32_vascular_surgery**
- Unadjusted feature-level results: **82**
- Unadjusted permutation FDR < 0.10: **31**
- Age/sex-adjusted results: **82**
- Adjusted model FDR < 0.10: **32**

## GSE252321

- Whole-object pseudobulk results: **80**
- Group size was two control and two UPEC biological samples. Effects are exploratory; exact two-sided permutation p values cannot provide strong significance at this sample size.

## Cross-dataset recurrence

- `NEUTROPHIL_NETOSIS_ANCHOR`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 3 datasets with |effect|>=0.8; dominant direction positive (coherence=0.56).
- `COMPLEMENT_OPSONOPHAGOCYTOSIS`: multi_context_FDR_supported; 4 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction positive (coherence=0.56).
- `FERROPTOSIS_LIPID_PEROXIDATION`: multi_context_FDR_supported; 4 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction positive (coherence=0.67).
- `GLYCOLYSIS`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction positive (coherence=0.56).
- `XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction positive (coherence=0.56).
- `COMPLEMENT_C3A_C5A_SIGNALING`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction positive (coherence=0.67).
- `LEPTIN_SIGNALING`: multi_context_FDR_supported; 4 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).
- `PYRIMIDINE_DEGRADATION`: multi_context_FDR_supported; 2 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction negative (coherence=0.67).
- `GLUCOCORTICOID_RESPONSE`: multi_context_FDR_supported; 2 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).
- `ESTROGEN_RECEPTOR_RESPONSE`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.67).
- `NFKB_MAPK_INFLAMMATION_ANCHOR`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).
- `PREGNANCY_INFLAMMATION_ANCHOR`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).
- `RESISTIN_INFLAMMATORY_SIGNALING`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).
- `NITRIC_OXIDE_SYNTHESIS_REGULATION`: FDR_plus_independent_effect_support; 2 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction negative (coherence=0.56).
- `ADIPOKINE_INFLAMMATORY_AXIS`: FDR_plus_independent_effect_support; 2 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction positive (coherence=0.56).
- `TESTOSTERONE_CONVERSION_AROMATIZATION`: multi_context_FDR_supported; 2 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction negative (coherence=0.62).
- `PI3K_AKT_SIGNALING`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 0 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).
- `LACTATE_HIF1A_INFLAMMATORY_GLYCOLYSIS`: multi_context_FDR_supported; 2 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.78).
- `COMPLEMENT_ALTERNATIVE`: multi_context_FDR_supported; 2 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction negative (coherence=0.67).
- `ARGININE_NO_UREA`: multi_context_FDR_supported; 2 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction negative (coherence=0.56).
- `OXIDATIVE_STRESS_NRF2_ANCHOR`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 0 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).
- `TLR4_LPS_SIGNALING_ANCHOR`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 0 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).
- `AMPK_INSULIN_COUNTERREGULATION`: two_dataset_moderate_effect; 2 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.56).
- `PYRIMIDINE_SYNTHESIS`: multi_dataset_large_effect; 2 datasets with |effect|>=0.5; 2 datasets with |effect|>=0.8; dominant direction positive (coherence=0.67).
- `PPARG_ADIPOMETABOLIC_REGULATION`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 0 datasets with |effect|>=0.8; dominant direction positive (coherence=0.78).
- `CATECHOLAMINE_IRON_REDOX_INTERFACE`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 0 datasets with |effect|>=0.8; dominant direction positive (coherence=0.78).
- `AGE_RAGE_SIGNALING`: multi_context_FDR_supported; 3 datasets with |effect|>=0.5; 0 datasets with |effect|>=0.8; dominant direction positive (coherence=0.78).
- `INSULIN_RECEPTOR_IRS`: FDR_plus_independent_effect_support; 3 datasets with |effect|>=0.5; 0 datasets with |effect|>=0.8; dominant direction positive (coherence=0.78).
- `GLYCOGEN_SYNTHESIS`: broad_multi_dataset_moderate_effect; 3 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.78).
- `AMPK_SIGNALING`: two_dataset_moderate_effect; 2 datasets with |effect|>=0.5; 1 datasets with |effect|>=0.8; dominant direction positive (coherence=0.89).

## Interpretation rules

- GSE186800 represents a bladder exposure/recurrence model and does not reproduce the pregnancy design of GSE280297.
- GSE112098 is a human urinary systemic-inflammation comparator, not a direct UTI cohort.
- GSE252321 validates whole-study UPEC-responsive direction only; cell-type attribution awaits reconstructed annotations.
- Cross-dataset recurrence supports pathway prioritization, but opposite directions can be biologically meaningful because tissue, host state and exposure differ.
