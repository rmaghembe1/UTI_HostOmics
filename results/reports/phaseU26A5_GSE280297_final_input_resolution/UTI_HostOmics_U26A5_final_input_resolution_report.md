# Phase U26A.5 - Final GSE280297 input resolution

- Version: `U26A5_v1.0_2026-07-14`
- Decision: **READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED**
- Manuscript and existing figures were not modified.

## Asset resolution

The malformed repaired normalized matrix was excluded because its
`gene_symbol` column contains numeric expression values and samples B1-B3
are absent.

The selected primary matrix is:

`project://03_data_processed/phaseU4b_repaired_matrices/GSE280297_gene_count_repaired_gene_symbol_matrix.tsv.gz`

Its matching annotation is:

`project://07_tables/phaseU4b_repaired_module_scores/GSE280297_gene_count_repaired_sample_annotation_v1.tsv`

## Matrix validation

- Canonical gene symbols: **37154**
- Expression samples: **60**
- Missing expected samples:
  **none**
- Numeric completion:
  **1.000**
- Expression-scale class:
  **continuous_transformed_expression**

## Metadata validation

- Annotation match fraction:
  **1.000**
- Tissue completion:
  **1.000**
- Treatment completion:
  **1.000**
- Outcome completion:
  **1.000**
- Pregnancy-status completion:
  **1.000**
- Dam-ID completion among pregnancy samples:
  **0.000**

Mock/PBS samples are represented as pregnancy controls.
Preterm, term, nonpregnant and mock-control outcomes remain separate.

## Statistical implication

Continuous module scoring and limma/welch-style sample-level contrasts; do not use deseq2 on this transformed matrix.

## U26B entry interpretation

- `READY_FOR_U26B`: tissue-stratified scoring and dam-aware outcome
  modeling can begin.
- `READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED`: tissue-stratified
  endocrine-metabolic-immune scoring can begin now, while maternal/dam-level
  AUROC or logistic models remain deferred.
- `TARGETED_METADATA_REVIEW_REQUIRED`: core metadata remain incomplete.
- `TARGETED_MATRIX_REVIEW_REQUIRED`: matrix structure remains unsuitable.
