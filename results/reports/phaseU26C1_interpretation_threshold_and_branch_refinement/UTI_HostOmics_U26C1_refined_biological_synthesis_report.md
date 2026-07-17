# Phase U26C.1 - Interpretation threshold and branch refinement

- Version: `U26C1_v1.0_2026-07-14`
- Near-neutral threshold: `|effect| < 0.2`.
- Manuscript and existing Figures 1-6 were not modified.

## Corrected cross-state classifications

- **Leptin signaling**: infection direction positive; preterm effect -0.752; refined relation `direction_reversal`.
- **TLR4-LPS signaling anchor**: infection direction positive; preterm effect -0.058; refined relation `pregnancy_near_neutral`.
- **PI3K-AKT signaling**: infection direction positive; preterm effect -0.635; refined relation `direction_reversal`.

## Branch-selective pregnancy architecture

- **steroid_synthesis**: median effect 0.135; branch_selective_steroid_synthesis: core steroidogenesis and androgen/testosterone biosynthesis are positive, whereas estrogen and cholesterol biosynthesis are negative; do not describe the entire synthesis domain as globally increased.
- **steroid_receptor_response**: median effect -0.804; uniform_receptor_response_attenuation: all five receptor-response programmes are negative across the tissue-collapsed comparison.
- **metabolic_effector_response**: median effect -0.676; uniform_metabolic_effector_attenuation: insulin/IRS, PI3K-AKT, leptin, transport and carbon-use programmes are negative.
- **complement_effector_response**: median effect 0.381; branch_selective_complement_remodeling: classical, terminal-MAC and opsonophagocytosis are positive while C3a/C5a signaling is negative.

## Manuscript-facing biological synthesis

The cross-model urinary inflammatory response is centered on a TLR4-linked leptin/PI3K-AKT axis. Leptin and PI3K-AKT show positive effects across all four infection-context datasets and marked attenuation in preterm-associated pregnancy tissues. TLR4-LPS signaling remains a robust infection anchor, but its preterm-versus-term effect is near neutral and must not be called a pregnancy direction reversal.

Pregnancy-associated endocrine remodeling is branch-selective. Core steroidogenesis and androgen/testosterone biosynthesis are positive, whereas estrogen and cholesterol biosynthesis are negative. In contrast, all evaluated steroid receptor-response programmes and all evaluated metabolic-effector programmes are negative. The appropriate working model is therefore selective steroidogenic branch remodeling coupled to broad receptor and metabolic-response attenuation, not globally increased steroid synthesis.

Complement remodeling is also branch-selective: classical, terminal-MAC and opsonophagocytic programmes are positive, whereas C3a/C5a inflammatory signaling is negative. The C3a/C5a and opsonophagocytosis cross-dataset signals remain provisional because their independent moderate support depends mainly on the n=2-versus-n=2 GSE252321 pseudobulk layer.

## Evidence counts

- Robust core modules: **3**.
- Provisional core modules: **2**.
- Secondary concordant modules: **5**.
