# Path conventions

The public repository uses explicit path conventions:

- `project://` in provenance tables denotes the root of a local reconstruction
  workspace containing reacquired GEO files and generated intermediate data.
- `repository://` denotes the root of this Git repository.
- `__UTI_HOSTOMICS_PROJECT_ROOT__` and
  `__UTI_HOSTOMICS_REPOSITORY_ROOT__` are placeholders retained in archived
  scripts and resolved by `scripts/run_archived_script.py`.

Raw data are reacquired from the GEO accessions listed in `data/accessions.tsv`.
