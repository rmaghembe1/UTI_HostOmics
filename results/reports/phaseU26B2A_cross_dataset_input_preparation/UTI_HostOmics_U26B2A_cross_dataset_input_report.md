# Phase U26B2A - Cross-dataset input preparation

- Version: `U26B2A_v1.0_2026-07-14`
- Decision: **TARGETED_INPUT_REVIEW_REQUIRED**
- Manuscript and existing Figures 1-6 were not modified.

## Bulk datasets

### GSE186800

- Ready for scoring: **False**
- Observed samples: ****
- Canonical genes: ****
- Annotation match fraction: ****
- Expression scale: ****
- Note: ValueError('cannot insert gene_symbol, already exists')

### GSE112098

- Ready for scoring: **False**
- Observed samples: ****
- Canonical genes: ****
- Annotation match fraction: ****
- Expression scale: ****
- Note: ValueError('cannot insert gene_symbol, already exists')

## Single-cell dataset

- Ready for sample-by-cell-type pseudobulk scoring: **False**
- Selected h5ad: ``
- Note: No readable h5ad was found. RDS/H5/MTX assets exist; targeted object conversion or R inspection is required.

## GSE280297 refinement carry-forward

- Family-specific permutation FDR < 0.10 hits: **1**
- GSE280297 remains a tissue-resolved effect-direction and pathway-architecture layer.

## Integration rules

- Score each dataset in its native species and technology context.
- Integrate standardized submodule effects and directional recurrence; do not pool raw expression.
- Treat GSE112098 as a human urinary systemic-inflammation comparator rather than UTI-specific evidence.
- Use sample-level pseudobulk for GSE252321; do not treat cells as independent biological replicates.
