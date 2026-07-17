# Phase U26A.4 - Established GSE280297 asset validation

- Version: `U26A4_v1.0_2026-07-14`
- Decision: **TARGETED_MATRIX_REVIEW_REQUIRED**
- Manuscript and existing figures were not modified.

## Established primary assets

- Repaired normalized matrix:
  `project://03_data_processed/phaseU4b_repaired_matrices/GSE280297_normalized_repaired_gene_symbol_matrix.tsv.gz`
- Matching sample annotation:
  `project://07_tables/phaseU4b_repaired_module_scores/GSE280297_normalized_repaired_sample_annotation_v1.tsv`

## Matrix validation

- Canonical gene symbols: **0**
- Expression samples: **57**
- Gene universe plausible: **False**
- Sample count plausible: **True**

## Sample-design validation

- Annotation sample-ID column: `sample_id`
- Direct sample overlap: **1.000**
- Annotation match fraction: **1.000**
- Tissue completion: **1.000**
- Treatment completion: **1.000**
- Outcome completion: **0.789**
- Pregnancy completion: **0.789**
- Dam-ID completion among pregnant samples:
  **0.000**

## U26B interpretation

- `READY_FOR_U26B`: tissue-stratified scoring and dam-aware outcome
  modeling can begin.
- `READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED`: tissue-stratified
  scoring can begin, while maternal/dam-level AUROC and logistic models
  remain deferred.
- `TARGETED_METADATA_REVIEW_REQUIRED`: the matrix is valid, but core
  treatment or outcome metadata require focused reconstruction.
- `TARGETED_MATRIX_REVIEW_REQUIRED`: the selected repaired matrix did
  not pass gene-universe or sample-count checks.
