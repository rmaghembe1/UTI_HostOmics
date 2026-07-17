# Phase U27B3E3.2 - Repaired supplementary rematerialization

- Version: `U27B3E32_v1.0_2026-07-16`
- Decision: **TARGETED_U27B3E32_SUPPLEMENTARY_REMATERIALIZATION_REPAIR_REQUIRED**
- Tables materialized: **10/10**.
- Sources: **31**, all existing: **True**.
- Supported tabular sources only: **True**.
- Schema/content/accession audits passed: **37/39**.
- GSE168600 occurrences: **1**.
- Scientific values recalculated: **False**.
- Historical artifacts overwritten: **False**.

## Targeted repairs

- S1 now includes the validated 60-sample GSE280297 design.
- S3 now includes dataset-level effects from all four frozen datasets and uses GSE252321 sample-level rather than cell-level biological inference.
- S6 now contains explicit QC, marker, broad-composition and refined-subtype composition sources.
- S8 contains biological cellular-attribution tables only.
- S9 uses the U27B3E22 accession-corrected panel provenance registry.
- S10 uses accession-clean interpretation-boundary and traceability sources.

## ZIP construction repair

All package files are staged under one supplementary package root before archiving. This removes the cross-directory `Path.relative_to()` failure from U27B3E3.
