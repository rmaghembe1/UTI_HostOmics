# Phase U26B1.1 - Stability-aware GSE280297 refinement

- Version: `U26B1.1_v1.0_2026-07-14`
- Manuscript and existing Figures 1-6 were not modified.
- C1, C2, and C3 are primary; C4 is secondary exploratory.

## Why refinement was required

The first U26B1 ranking used the maximum absolute effect across all contrasts. The UTI89-RFP comparison often involved n=2 versus n=3 and generated unstable bootstrap intervals, so it was not appropriate for primary figure prioritization.

## Primary permutation evidence

- Primary feature-level results: **567**
- Primary results at permutation FDR < 0.05: **0**
- Primary results at permutation FDR < 0.10: **0**
- Primary results at family-specific FDR < 0.10: **1**

## Axis-level evidence

- **C1_PRETERM_VS_TERM | bladder | lipid_metabolism**: Hedges' g=-0.401, permutation FDR=0.6217.
- **C1_PRETERM_VS_TERM | bladder | immune_context_anchors**: Hedges' g=-0.420, permutation FDR=0.6217.
- **C1_PRETERM_VS_TERM | bladder | steroid_cholesterol_endocrine**: Hedges' g=-0.447, permutation FDR=0.6217.
- **C1_PRETERM_VS_TERM | bladder | nucleotide_nad_nitrogen**: Hedges' g=-0.463, permutation FDR=0.6217.
- **C1_PRETERM_VS_TERM | bladder | carbohydrate_inflammatory_carbon**: Hedges' g=-0.546, permutation FDR=0.6217.
- **C1_PRETERM_VS_TERM | bladder | catecholamine_stress_adjacent**: Hedges' g=-0.587, permutation FDR=0.6217.
- **C1_PRETERM_VS_TERM | bladder | adipokine_signaling**: Hedges' g=-0.643, permutation FDR=0.6217.
- **C1_PRETERM_VS_TERM | bladder | amino_acid_metabolism**: Hedges' g=-0.689, permutation FDR=0.6217.
- **C1_PRETERM_VS_TERM | bladder | insulin_irs_signaling**: Hedges' g=-1.059, permutation FDR=0.6217.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | steroid_cholesterol_endocrine**: Hedges' g=-0.309, permutation FDR=0.7046.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | catecholamine_stress_adjacent**: Hedges' g=-0.314, permutation FDR=0.7046.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | lipid_metabolism**: Hedges' g=-0.361, permutation FDR=0.7046.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | insulin_irs_signaling**: Hedges' g=-0.368, permutation FDR=0.7046.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | amino_acid_metabolism**: Hedges' g=-0.495, permutation FDR=0.7046.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | nucleotide_nad_nitrogen**: Hedges' g=-0.562, permutation FDR=0.7046.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | carbohydrate_inflammatory_carbon**: Hedges' g=-0.582, permutation FDR=0.7046.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | adipokine_signaling**: Hedges' g=-0.214, permutation FDR=0.7078.
- **C2_UPEC_VS_PBS_PREGNANCY | placenta | immune_context_anchors**: Hedges' g=-0.256, permutation FDR=0.7078.
- **C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder | steroid_cholesterol_endocrine**: Hedges' g=0.356, permutation FDR=0.7592.
- **C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder | carbohydrate_inflammatory_carbon**: Hedges' g=0.410, permutation FDR=0.7592.
- **C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder | insulin_irs_signaling**: Hedges' g=0.466, permutation FDR=0.7592.
- **C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder | amino_acid_metabolism**: Hedges' g=0.553, permutation FDR=0.7592.
- **C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder | catecholamine_stress_adjacent**: Hedges' g=0.636, permutation FDR=0.7592.
- **C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder | nucleotide_nad_nitrogen**: Hedges' g=0.693, permutation FDR=0.7592.
- **C3_INFECTED_PREGNANT_VS_NONPREGNANT | bladder | complement_architecture**: Hedges' g=0.765, permutation FDR=0.7592.

## Primary-only Figure 7-10 priorities

### Figure_7

- `GLUCOCORTICOID_RESPONSE`: recurrent_large_effect; max primary |g|=1.197; large primary effects=3; permutation FDR<0.10 results=0.
- `ESTROGEN_RECEPTOR_RESPONSE`: recurrent_large_effect; max primary |g|=1.050; large primary effects=3; permutation FDR<0.10 results=0.
- `ANDROGEN_RECEPTOR_SIGNALING`: recurrent_large_effect; max primary |g|=1.019; large primary effects=2; permutation FDR<0.10 results=0.
- `ANDROGEN_TESTOSTERONE_BIOSYNTHESIS`: recurrent_large_effect; max primary |g|=1.472; large primary effects=2; permutation FDR<0.10 results=0.
- `CHOLESTEROL_BIOSYNTHESIS`: single_large_effect; max primary |g|=1.335; large primary effects=1; permutation FDR<0.10 results=0.
- `STEROID_SULFATION_DESULFATION`: single_large_effect; max primary |g|=0.880; large primary effects=1; permutation FDR<0.10 results=0.
- `STEROIDOGENESIS_CORE`: single_large_effect; max primary |g|=0.880; large primary effects=1; permutation FDR<0.10 results=0.
- `TESTOSTERONE_CONVERSION_AROMATIZATION`: single_large_effect; max primary |g|=1.227; large primary effects=1; permutation FDR<0.10 results=0.
- `FERROPTOSIS_LIPID_PEROXIDATION`: single_large_effect; max primary |g|=1.151; large primary effects=1; permutation FDR<0.10 results=0.
- `FATTY_ACID_SYNTHESIS`: recurrent_moderate_effect; max primary |g|=0.575; large primary effects=0; permutation FDR<0.10 results=0.

### Figure_8

- `AMPK_SIGNALING`: recurrent_large_effect; max primary |g|=0.938; large primary effects=2; permutation FDR<0.10 results=0.
- `INSULIN_RECEPTOR_IRS`: single_large_effect; max primary |g|=1.340; large primary effects=1; permutation FDR<0.10 results=0.
- `PI3K_AKT_SIGNALING`: single_large_effect; max primary |g|=1.290; large primary effects=1; permutation FDR<0.10 results=0.
- `GLYCOLYSIS`: single_large_effect; max primary |g|=1.010; large primary effects=1; permutation FDR<0.10 results=0.
- `GLYCOGEN_SYNTHESIS`: single_large_effect; max primary |g|=1.254; large primary effects=1; permutation FDR<0.10 results=0.
- `TCA_OXPHOS`: single_large_effect; max primary |g|=0.910; large primary effects=1; permutation FDR<0.10 results=0.
- `GLUCONEOGENESIS`: single_large_effect; max primary |g|=1.193; large primary effects=1; permutation FDR<0.10 results=0.
- `ADIPOKINE_INFLAMMATORY_AXIS`: single_large_effect; max primary |g|=0.937; large primary effects=1; permutation FDR<0.10 results=0.
- `LEPTIN_SIGNALING`: single_large_effect; max primary |g|=0.853; large primary effects=1; permutation FDR<0.10 results=0.
- `GLUCOSE_TRANSPORT`: single_large_effect; max primary |g|=1.045; large primary effects=1; permutation FDR<0.10 results=0.

### Figure_9

- `PYRIMIDINE_SYNTHESIS`: recurrent_large_effect; max primary |g|=0.927; large primary effects=2; permutation FDR<0.10 results=0.
- `PYRIMIDINE_DEGRADATION`: recurrent_large_effect; max primary |g|=1.183; large primary effects=2; permutation FDR<0.10 results=0.
- `AMINO_ACID_TRANSPORT`: recurrent_large_effect; max primary |g|=1.053; large primary effects=2; permutation FDR<0.10 results=0.
- `SERINE_GLYCINE_ONE_CARBON`: single_large_effect; max primary |g|=0.987; large primary effects=1; permutation FDR<0.10 results=0.
- `PURINE_SALVAGE`: single_large_effect; max primary |g|=1.371; large primary effects=1; permutation FDR<0.10 results=0.
- `GLUTAMINE_GLUTAMATE`: single_large_effect; max primary |g|=1.025; large primary effects=1; permutation FDR<0.10 results=0.
- `ADRENERGIC_STRESS_SIGNALING`: single_large_effect; max primary |g|=0.982; large primary effects=1; permutation FDR<0.10 results=0.
- `PURINE_DE_NOVO_SYNTHESIS`: single_large_effect; max primary |g|=0.904; large primary effects=1; permutation FDR<0.10 results=0.
- `NITRIC_OXIDE_SYNTHESIS_REGULATION`: single_large_effect; max primary |g|=0.801; large primary effects=1; permutation FDR<0.10 results=0.
- `BRANCHED_CHAIN_AMINO_ACIDS`: single_large_effect; max primary |g|=0.939; large primary effects=1; permutation FDR<0.10 results=0.

### Figure_10

- `COMPLEMENT_TERMINAL_MAC`: single_large_effect; max primary |g|=0.961; large primary effects=1; permutation FDR<0.10 results=0.
- `COMPLEMENT_C3_CONVERTASE_AMPLIFICATION`: single_large_effect; max primary |g|=1.169; large primary effects=1; permutation FDR<0.10 results=0.
- `COMPLEMENT_LECTIN`: single_large_effect; max primary |g|=1.096; large primary effects=1; permutation FDR<0.10 results=0.
- `COMPLEMENT_CLASSICAL`: single_large_effect; max primary |g|=0.934; large primary effects=1; permutation FDR<0.10 results=0.
- `COMPLEMENT_ALTERNATIVE`: single_large_effect; max primary |g|=0.962; large primary effects=1; permutation FDR<0.10 results=0.
- `COMPLEMENT_COAGULATION_CROSSTALK`: single_large_effect; max primary |g|=1.080; large primary effects=1; permutation FDR<0.10 results=0.
- `COMPLEMENT_OPSONOPHAGOCYTOSIS`: single_large_effect; max primary |g|=0.880; large primary effects=1; permutation FDR<0.10 results=0.
- `COMPLEMENT_REGULATORS`: recurrent_moderate_effect; max primary |g|=0.745; large primary effects=0; permutation FDR<0.10 results=0.
- `COMPLEMENT_C3A_C5A_SIGNALING`: recurrent_moderate_effect; max primary |g|=0.607; large primary effects=0; permutation FDR<0.10 results=0.

## Cross-tissue directional coherence

- `INSULIN_RECEPTOR_IRS` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.809.
- `GLUCOCORTICOID_RESPONSE` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.808.
- `ANDROGEN_RECEPTOR_SIGNALING` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.797.
- `AMINO_ACID_TRANSPORT` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.792.
- `ESTROGEN_RECEPTOR_RESPONSE` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.789.
- `PI3K_AKT_SIGNALING` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.763.
- `ANDROGEN_TESTOSTERONE_BIOSYNTHESIS` in C1_PRETERM_VS_TERM: positive across 3 tissues; mean |g|=0.682.
- `STEROIDOGENESIS_CORE` in C1_PRETERM_VS_TERM: positive across 3 tissues; mean |g|=0.664.
- `LEPTIN_SIGNALING` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.599.
- `METHIONINE_SAM_METHYLATION` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.589.
- `COMPLEMENT_REGULATORS` in C2_UPEC_VS_PBS_PREGNANCY: positive across 3 tissues; mean |g|=0.586.
- `STEROID_SULFATION_DESULFATION` in C2_UPEC_VS_PBS_PREGNANCY: negative across 3 tissues; mean |g|=0.550.
- `GLUTAMINE_GLUTAMATE` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.545.
- `MINERALOCORTICOID_RESPONSE` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.530.
- `GLUCOSE_TRANSPORT` in C1_PRETERM_VS_TERM: negative across 3 tissues; mean |g|=0.505.

## Secondary exploratory contrast

- C4 feature-level results retained: **243**.
- C4 is excluded from primary Figure 7-10 ranking and from standalone mechanistic conclusions because its smallest groups contain only two samples.
- Hedges' g may still be displayed as descriptive exploratory evidence, but effect-size confidence intervals are suppressed when either group has fewer than four samples.

## Biological interpretation

GSE280297 should be used as a tissue-resolved effect-direction and pathway-architecture layer. Strong but non-FDR-supported effects are hypothesis-generating until reinforced by the recurrence model, urinary inflammatory comparator, and UPEC-responsive single-cell layer.
