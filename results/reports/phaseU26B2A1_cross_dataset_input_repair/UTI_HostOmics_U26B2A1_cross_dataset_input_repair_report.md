# Phase U26B2A.1 - Cross-dataset input repair

- Version: `U26B2A1_v1.0_2026-07-14`
- Decision: **READY_FOR_U26B2B_BULK_AND_SAMPLE_PSEUDOBULK_SCORING_CELLTYPE_RECONSTRUCTION_DEFERRED**
- Manuscript and existing Figures 1-6 were not modified.

## Bulk readiness

### GSE186800

- Ready: **True**
- Samples: **20**
- Canonical genes: **41082**
- Annotation match fraction: **1.0**
- Expression scale: **continuous_transformed_expression**
- Note: Use sample-level dataset-specific scoring; do not pool raw expression across species.

### GSE112098

- Ready: **True**
- Samples: **73**
- Canonical genes: **23952**
- Annotation match fraction: **1.0**
- Expression scale: **continuous_transformed_expression**
- Note: Use sample-level dataset-specific scoring; do not pool raw expression across species.

## GSE252321

- Sample-level pseudobulk ready: **True**
- Pseudobulk biological samples: **4**
- Cell-type pseudobulk: **deferred**
- Note: Sample-level whole-object pseudobulk is ready. Cell-type pseudobulk remains deferred until cell annotations or a reconstructed annotated object are available.

## Statistical use

- GSE186800: four-group factorial or planned-contrast sample-level module analysis.
- GSE112098: sepsis versus vascular-surgery urinary comparator; interpretation is systemic urinary inflammation.
- GSE252321: whole-object biological-sample pseudobulk is exploratory when available; cell-type validation awaits annotated-object reconstruction.
- Cross-dataset integration will use standardized effects, directional recurrence and native-species module identities.
