# Phase U27B3E4 - Supplementary schema and content audit

- Version: `U27B3E4_v1.0_2026-07-16`
- Decision: **TARGETED_U27B3E4_SUPPLEMENTARY_SCHEMA_OR_CONTENT_REPAIR_REQUIRED**
- Package: `project://11_supplementary/phaseU27B3E321_semantic_accession_audit_correction`
- Manuscript: `project://09_manuscript_docx/phaseU27B3E22_targeted_accession_correction/UTI_HostOmics_preZotero_manuscript_v6_3_U27B3E22_accession_corrected.docx`
- Audit checks passed: **264/266**.
- Blocking checks passed: **263/265**.
- Blocking failures: **2**.
- Source-aware missingness warning rows: **8**.
- ZIP integrity: **True**.
- Scientific values recalculated: **False**.
- Materialized tables modified: **False**.

## Missingness interpretation

The S1-S10 files use union schemas because each supplementary table combines heterogeneous source tables. Columns belonging to other source blocks are therefore structurally blank and are not treated as missing data. This audit evaluates completeness inside each source's native schema and applies blocking checks only to critical identifiers and analysis fields.

## Biological-replicate and accession boundaries

GSE252321 dataset-level contrasts remain sample-based at n=2 controls versus n=2 UPEC samples. Cells are not treated as independent biological replicates. GSE186800 remains the canonical recurrent-UTI accession. The sole GSE168600 string is retained only as the explicit S10 prohibition rule identifying the unrelated KLF5 skin/sphingolipid dataset.

## Blocking failures

- **S3 / single_cell_biological_unit**: observed `sample_mean`; expected `sample`. GSE252321 effects must use four biological samples, not cells.
- **S9 / critical_nonmissing::Frozen Figure 1-8 asset manifest::figure_number**: observed `81/83`; expected `83/83`. Critical identifiers and analysis fields must be complete inside their native source block.
