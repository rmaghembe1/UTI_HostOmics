# Release checklist

Before creating a public release:

- [ ] Confirm repository URL in README and CITATION.cff.
- [ ] Confirm all four GEO accessions.
- [ ] Confirm no raw data or large intermediate matrices are tracked.
- [ ] Confirm no local Windows or WSL paths remain.
- [ ] Confirm no credential-like strings are present.
- [ ] Confirm Python and shell syntax audits pass.
- [ ] Confirm manuscript, figures, and supplemental files match the frozen release.
- [ ] Create a semantic version tag.
- [ ] Create a GitHub release.
- [ ] Archive the release in Zenodo.
- [ ] Add the Zenodo DOI to README, CITATION.cff, and manuscript.
