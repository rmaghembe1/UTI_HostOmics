# Reproducibility guide

## Design principle

Each dataset was analyzed in its native species, tissue, and experimental
design. Raw expression values were not pooled across studies. Cross-context
integration used standardized module effects, recurrence, directional
concordance, and tissue coherence.

## Source data

Download the public GEO records listed in `data/accessions.tsv`. Raw source
files and large processed matrices are intentionally excluded from version
control.

## Pipeline provenance

The directory `scripts/archive_phase_scripts/` contains the phase-resolved
analysis scripts used during the project. Final portable entry points and an
ordered execution map will be added before the v1.0.0 release.

## Output verification

The supplemental workbook contains the final source-value and provenance
tables. Main figures are provided under `figures/main/`.
