# Phase U26A.1 targeted source, contrast, and species repair

- Version: `U26A1_v1.0_2026-07-14`
- Decision: **TARGETED_INPUT_REVIEW_REQUIRED**
- Manuscript and existing figures were not modified.

## Why the repair was required

The first-pass audit demonstrated broad gene-set coverage, but its discovery layer unioned multiple accession-matched files and its metadata scanner accepted duplicated labels and numeric summary columns. The first-pass figure priorities therefore represented provisional gene-presence feasibility, not expression-level biological evidence.

## Selected expression sources

- **GSE186800**: `project://02_data_raw/GSE186800/supplementary/GSE186800_Raw_geneCPM_matrix.txt.gz` (selected).
- **GSE280297**: `project://02_data_raw/GSE280297/supplementary/GSE280297_Normalized.counts.csv.gz` (selected).
- **GSE112098**: `project://02_data_raw/GSE112098/supplementary/GSE112098_IndependentValidationsetMatrix.txt.gz` (selected).
- **GSE252321**: `project://02_data_raw/GSE252321/single_cell_matrices/GSM7999428_UPEC_1_matrix.tsv.gz` (selected).

## Gene-universe QC

- **GSE186800**: 21716 symbols; `resolved_plausible`.
- **GSE280297**: 0 symbols; `unresolved`.
- **GSE112098**: 20782 symbols; `resolved_plausible`.
- **GSE252321**: 15622 symbols; `resolved_plausible`.

## Corrected analytical design

- GSE186800 is a four-group, 5-mouse-per-group factorial bladder experiment.
- GSE280297 must be modeled by tissue and dam/outcome; duplicated summary rows cannot define sample size.
- GSE112098 is a human urinary sepsis comparator and should not be described as UTI-specific evidence.
- GSE252321 requires biological-sample pseudobulk; cells or module-result rows are not independent replicates.
- Mouse datasets require explicit ortholog-aware integration with the human urine dataset.

## U26B entry rule

Proceed only when the phase decision is `READY_FOR_U26B`. U26B should score expression within each dataset, estimate effect sizes and FDRs using the corrected analysis units, and integrate standardized effects rather than raw expression.
