# Analysis scripts

## Archive

`scripts/archive_phase_scripts/` preserves the phase-resolved scripts used to
construct the UTI HostOmics analysis. Original machine-specific root paths were
replaced by two explicit placeholders:

- `__UTI_HOSTOMICS_PROJECT_ROOT__`
- `__UTI_HOSTOMICS_REPOSITORY_ROOT__`

This preserves the original workflow logic without publishing a local machine
path.

## Portable runner

Use `run_archived_script.py` to materialize and execute an archived Python,
shell, or R script:

```bash
python scripts/run_archived_script.py \
  phaseU26B2B_score_and_integrate_cross_datasets.py \
  --project-root /path/to/local/UTI_HostOmics_reconstruction
```

Arguments for the archived script can be supplied after `--`.

The reconstruction root is separate from this Git repository because raw GEO
data and large processed matrices are not version-controlled.
