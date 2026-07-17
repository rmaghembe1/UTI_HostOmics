# Phase U26A.2 - GSE280297 identifier and design resolution

- Version: `U26A2_v1.0_2026-07-14`
- Overall decision: **TARGETED_METADATA_REVIEW_REQUIRED**
- Manuscript and existing figures were not modified.

## Identifier diagnosis

The U26A.1 zero-symbol result arose because mouse Ensembl identifiers (`ENSMUSG...`) were removed by a human-Ensembl-specific sanitizer. U26A.2 recognizes mouse Ensembl identifiers and preferentially selects a local gene-symbol matrix when one is available.

## Canonical expression matrix

- **selected_source**: `project://02_data_raw/GSE280297/supplementary/GSE280297_Normalized.counts.csv.gz`
- **canonical_matrix**: `project://04_data_processed/phaseU26A2_GSE280297_identifier_design_resolution/GSE280297_U26A2_canonical_gene_symbol_expression.tsv.gz`
- **mapping_method**: `org.Mm.eg.db`
- **n_input_rows**: `0`
- **n_canonical_gene_symbols**: `0`
- **n_expression_samples**: `60`
- **duplicate_collapse_rule**: `mean`
- **n_mouse_ensembl_ids_observed**: `56748`
- **n_mouse_ensembl_ids_mapped**: `0`

## Metadata completion

- **metadata_match_fraction**: 1.000
- **tissue_completion**: 0.000
- **treatment_completion**: 0.000
- **outcome_completion**: 1.000
- **pregnancy_completion**: 1.000
- **dam_id_completion_all**: 0.000
- **dam_id_completion_pregnant**: 0.000

## Entry interpretation

The expression matrix is assessed separately from metadata. Inspect unresolved sample-design fields before initiating tissue-stratified U26B models.
