# Phase U27B3E4.1 - Semantic audit correction

- Version: `U27B3E41_v1.0_2026-07-16`
- Decision: **TARGETED_U27B3E41_SEMANTIC_AUDIT_OR_ASSET_CLASSIFICATION_REVIEW_REQUIRED**
- Corrected audit checks passed: **265/266**.
- Corrected blocking checks passed: **264/265**.
- Blocking failures: **1**.
- S3 `sample_mean` authorized as sample-level: **True**.
- S9 authorized package-level blank rows: **1**.
- S9 unauthorized or unclassified blank rows: **1**.
- ZIP integrity retained: **True**.
- Manuscript consistency retained: **True**.

## S3 correction

The unit value `sample_mean` denotes a contrast of biological-sample means. The locked source is explicitly sample-level and contains 20 module rows evaluated across two control and two UPEC samples. No cell-level source is present in this S3 block.

## S9 correction

Figure-number completeness is evaluated only for figure-linked assets. A blank is authorized only when the row has no panel, no figure-specific path marker and is explicitly recognizable as a package-level contact sheet, manifest/index, README or collective figure/legend bundle.

## Integrity boundary

No supplementary table, ZIP member, scientific value, source file, manuscript, figure or legend was changed. This phase corrects audit semantics only.
