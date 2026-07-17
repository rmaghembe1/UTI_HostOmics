# Phase U27B3E3.2.1 - Semantic accession audit correction

- Version: `U27B3E321_v1.0_2026-07-16`
- Decision: **READY_FOR_U27B3E4_SUPPLEMENTARY_TABLE_SCHEMA_AND_CONTENT_AUDIT**
- Tables preserved byte-for-byte: **10/10**.
- Corrected semantic audits passed: **40/40**.
- Unauthorized `GSE168600` occurrences: **0**.
- Authorized prohibition-rule occurrences: **1**.

## Correction rationale

U27B3E32 used a literal global-string absence test. That rule incorrectly rejected the S10 validation row whose purpose is to document that GSE168600 is prohibited because it is an unrelated KLF5 skin/sphingolipid dataset. The corrected audit evaluates semantic context: dataset use remains prohibited, while the explicit prevention rule is retained.

## Integrity boundary

No materialized table, statistical result, source file, manuscript, figure or legend was changed. This phase corrects only the audit logic and controlled package metadata.
