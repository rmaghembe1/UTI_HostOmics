# Phase U26D1A - GSE252321 flat-matrix validation

- Version: `U26D1A_v1.1_2026-07-14`
- Decision: **READY_FOR_U26D2_FLAT_MATRIX_MARKER_BASED_RECONSTRUCTION**
- Manuscript and existing figures were not modified.

## Key diagnosis

The dataset is represented as four dense gene-by-cell TSV matrices, not as 10x MatrixMarket triplets. The zero-triplet result from U26D1 was therefore a format-detection limitation, not a missing-input failure.

## Matrix validation

- `GSM7999426_Control_1` (control): 6,002 cells, 24,821 gene rows, sparsity=0.926, scale=integer_like_counts, adaptive QC pass=5,884/6,002 (98.0%).
- `GSM7999427_Control_2` (control): 8,855 cells, 23,591 gene rows, sparsity=0.955, scale=integer_like_counts, adaptive QC pass=8,497/8,855 (96.0%).
- `GSM7999428_UPEC_1` (UPEC): 7,372 cells, 23,274 gene rows, sparsity=0.947, scale=integer_like_counts, adaptive QC pass=7,091/7,372 (96.2%).
- `GSM7999429_UPEC_2` (UPEC): 6,084 cells, 24,679 gene rows, sparsity=0.929, scale=integer_like_counts, adaptive QC pass=5,913/6,084 (97.2%).

## Raw archive

- Archive members: **4**.
- 10x component-like members: **0**.
- Flat-matrix-like members: **4**.

## Next analysis

Proceed to U26D2 using the converted sparse matrices. Perform cell QC, within-sample normalization, highly variable gene selection, balanced integration, unsupervised clustering, marker-based annotation and sample-by-cell-type pseudobulk. Biological samples, not cells, remain the inferential units.
