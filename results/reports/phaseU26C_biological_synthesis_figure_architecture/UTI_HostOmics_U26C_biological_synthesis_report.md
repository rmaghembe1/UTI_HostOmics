# Phase U26C - Biological synthesis and Figure 7-11 architecture

- Version: `U26C_v1.0_2026-07-14`
- Manuscript and existing Figures 1-6 were not modified.
- No module showed replicated FDR < 0.10 across two independent datasets.

## Robust core cross-dataset modules

- **Leptin signaling** (`LEPTIN_SIGNALING`): one human adjusted FDR signal plus a concordant moderate effect outside the n=2-per-group GSE252321 layer; infection direction positive (coherence=1.00); preterm effect=-0.752 (direction_reversal).
- **TLR4-LPS signaling anchor** (`TLR4_LPS_SIGNALING_ANCHOR`): one human adjusted FDR signal plus a concordant moderate effect outside the n=2-per-group GSE252321 layer; infection direction positive (coherence=1.00); preterm effect=-0.058 (direction_reversal).
- **PI3K-AKT signaling** (`PI3K_AKT_SIGNALING`): one human adjusted FDR signal plus a concordant moderate effect outside the n=2-per-group GSE252321 layer; infection direction positive (coherence=1.00); preterm effect=-0.635 (direction_reversal).

## Provisional core modules dependent on exploratory pseudobulk

- **C3a and C5a inflammatory signaling** (`COMPLEMENT_C3A_C5A_SIGNALING`): human adjusted FDR plus a moderate concordant effect driven by GSE252321 n=2-per-group pseudobulk; retain as provisional until cell-type or larger-sample validation.
- **Complement-opsonophagocytosis** (`COMPLEMENT_OPSONOPHAGOCYTOSIS`): human adjusted FDR plus a moderate concordant effect driven by GSE252321 n=2-per-group pseudobulk; retain as provisional until cell-type or larger-sample validation.

## Secondary concordant modules

- **Glycogen synthesis** (`GLYCOGEN_SYNTHESIS`): two-dataset concordant effect without independent FDR replication.
- **Amino-acid transport** (`AMINO_ACID_TRANSPORT`): two-dataset concordant effect without independent FDR replication.
- **Fatty-acid synthesis** (`FATTY_ACID_SYNTHESIS`): two-dataset concordant effect without independent FDR replication.
- **Insulin receptor and IRS signaling** (`INSULIN_RECEPTOR_IRS`): two-dataset concordant effect without independent FDR replication.
- **Androgen receptor signaling** (`ANDROGEN_RECEPTOR_SIGNALING`): two-dataset concordant effect without independent FDR replication.

## Pregnancy synthesis-response decoupling

- **steroid_synthesis**: median effect 0.135; dominant direction mixed; coherence 0.50.
- **steroid_receptor_response**: median effect -0.804; dominant direction negative; coherence 1.00.
- **metabolic_effector_response**: median effect -0.676; dominant direction negative; coherence 1.00.
- **complement_effector_response**: median effect 0.381; dominant direction positive; coherence 0.75.

The pattern supports a hypothesis in which steroidogenic transcription is preserved or increased while receptor-response, insulin/PI3K-AKT, adipokine, amino-acid transport and inflammatory-carbon programmes are attenuated. These are transcriptionally inferred pathway activities, not measured hormone concentrations or metabolic flux.

## Context-divergent biology

- `GLYCOLYSIS`: GSE112098:0.5186;GSE186800:-0.0933;GSE252321:1.0086;GSE280297:-0.4066; interpret as context-dependent remodeling.
- `XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM`: GSE112098:0.5130;GSE186800:-0.0147;GSE252321:0.8909;GSE280297:-0.0112; interpret as context-dependent remodeling.
- `NITRIC_OXIDE_SYNTHESIS_REGULATION`: GSE112098:0.1616;GSE186800:-0.1855;GSE252321:0.8087;GSE280297:-0.4823; interpret as context-dependent remodeling.
- `ARGININE_NO_UREA`: GSE112098:0.2147;GSE186800:-0.0814;GSE252321:1.4385;GSE280297:-0.3257; interpret as context-dependent remodeling.
- `PENTOSE_PHOSPHATE_PATHWAY`: GSE112098:0.2952;GSE186800:-0.2188;GSE252321:-0.4690;GSE280297:0.4285; interpret as context-dependent remodeling.
- `ESTROGEN_BIOSYNTHESIS`: GSE112098:-0.2829;GSE186800:0.1224;GSE252321:-0.1834;GSE280297:0.2236; interpret as context-dependent remodeling.
- `UREA_CYCLE`: GSE112098:0.2398;GSE186800:-0.1473;GSE252321:0.1551;GSE280297:-0.0291; interpret as context-dependent remodeling.
- `TESTOSTERONE_CONVERSION_AROMATIZATION`: GSE112098:-0.2152;GSE186800:-0.0796;GSE280297:0.2891; interpret as context-dependent remodeling.
- `GLUCOSE_TRANSPORT`: GSE112098:-0.0074;GSE186800:0.3861;GSE252321:1.3651;GSE280297:-0.3234; interpret as context-dependent remodeling.
- `PLACENTAL_STEROID_METABOLISM`: GSE112098:-0.1552;GSE186800:0.1492;GSE252321:1.0602;GSE280297:-0.0658; interpret as context-dependent remodeling.
- `AMPK_INSULIN_COUNTERREGULATION`: GSE112098:-0.0960;GSE186800:0.8737;GSE252321:-0.0934;GSE280297:0.1432; interpret as context-dependent remodeling.
- `COMPLEMENT_COAGULATION_CROSSTALK`: GSE112098:-0.0119;GSE186800:0.0935;GSE252321:1.2139;GSE280297:-0.0385; interpret as context-dependent remodeling.
- `TCA_OXPHOS`: GSE112098:0.3733;GSE186800:-0.1070;GSE252321:-0.6033;GSE280297:0.4911; interpret as context-dependent remodeling.
- `MTORC1_INSULIN_OUTPUT`: GSE112098:-0.1023;GSE186800:0.7815;GSE252321:-0.2757;GSE280297:0.2898; interpret as context-dependent remodeling.
- `STEROID_SULFATION_DESULFATION`: GSE112098:-0.0709;GSE186800:0.3115;GSE252321:0.2502;GSE280297:-0.6622; interpret as context-dependent remodeling.

## Figure architecture

- **Figure 7:** steroid, cholesterol, receptor-response and lipid-peroxidation remodeling.
- **Figure 8:** adipokine, insulin/IRS, PI3K-AKT and inflammatory carbon use.
- **Figure 9:** amino-acid, nucleotide, nitrogen, redox and catecholamine-adjacent metabolism.
- **Figure 10:** complement initiation, amplification, effector and regulation.
- **Figure 11:** integrated synthesis-response decoupling and carbon-complement-inflammatory network.

## Cell-type reconstruction decision

GSE252321 cell-type reconstruction is recommended before final manuscript freeze, but it does not block current biological synthesis or Figure 7-11 development.
