# Public release audit

The public repository was assembled from a larger working project through a
controlled staging process.

Before Git initialization, the staged repository was checked for:

- files larger than 25 MB;
- credential-like strings;
- hard-coded local Windows and WSL paths;
- Python syntax errors;
- shell syntax errors;
- inclusion of raw GEO data and large intermediate matrices.

Internal pre-release audit logs and historical occurrence inventories that
contained local-machine path excerpts were retained outside the public
repository. Their removal does not alter manuscript results, source-value
tables, figures, supplemental tables, module definitions, or executable
analysis scripts.

The final release manifest and checksums are generated immediately before the
first Git commit.
