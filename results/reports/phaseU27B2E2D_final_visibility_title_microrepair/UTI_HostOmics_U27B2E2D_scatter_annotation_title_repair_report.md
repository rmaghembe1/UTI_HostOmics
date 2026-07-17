# Phase U27B2E2D - Final visibility and title micro-repair

- Version: `U27B2E2D_v1.0_2026-07-16`
- Decision: **READY_FOR_U27B2E2E_FINAL_FIGURES_5_TO_8_FREEZE**
- Figures rebuilt: **4/4**.
- Frozen panels represented: **28/28**.
- PNG/SVG/PDF exports: **12/12**.
- Panel crops: **28/28**.
- Scatter annotation audit: **True**.

## Corrected defect

The U27B2E2A conversion searched for ordinary Text objects, whereas the scatter labels were Matplotlib Annotation objects. This phase explicitly removes the Annotation labels, preserves all points, and replaces six priority labels with numeric markers and compact keys.

## Integrity boundary

No numerical values, displayed modules, pathway assignments, source locks, statistical effects or biological interpretations were changed.
