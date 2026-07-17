# UTI HostOmics

This repository accompanies the study:

**Host systems remodeling links uropathogenic *Escherichia coli* sensing to
recurrent and pregnancy-associated urinary tract infection**

The study integrates four public transcriptomic resources to examine
endocrine-metabolic-immune remodeling across urinary tract infection,
recurrence-related bladder perturbation, pregnancy-associated outcomes, and
cell-resolved UPEC host responses.

## Biological scope

The analysis evaluates 78 curated submodules spanning:

- steroid, cholesterol, and endocrine signaling;
- lipid and adipokine biology;
- insulin receptor/IRS and PI3K-AKT signaling;
- inflammatory carbon, amino-acid, nucleotide, NAD, and redox metabolism;
- complement initiation, amplification, inflammatory, opsonophagocytic, and
  regulatory branches;
- immune-context and cell-state programs.

## Public datasets

The source accessions are GSE112098, GSE186800, GSE252321, and GSE280297.
Raw data are not redistributed. See `data/accessions.tsv`.

## Repository structure

- `config/modules/`: curated biological module definitions.
- `data/`: public accession and acquisition documentation.
- `environment/`: software and runtime manifests.
- `figures/main/`: assembled main-figure TIFF files.
- `manuscript/`: journal-targeted working manuscript.
- `references/`: reference-management exports and supporting files.
- `results/`: selected final metadata, reports, and source-value tables.
- `scripts/archive_phase_scripts/`: phase-resolved computational provenance.
- `supplemental/`: supplemental workbook and legends.
- `docs/`: release, audit, and reproducibility documentation.

## Reproducibility status

The phase scripts preserve the complete computational provenance of the active
project. A portability pass is performed before public release to replace
machine-specific assumptions in the final execution entry points. Raw and
large intermediate matrices are reacquired from GEO rather than stored in Git.

## Data and code availability

Public repository: https://github.com/rmaghembe1/UTI_HostOmics

The semantic release tag and archival DOI will be added after the first GitHub release is archived in Zenodo.

## Citation

Citation metadata are provided in `CITATION.cff`. The article DOI will be added
after publication.

## Licensing

Original analysis code is distributed under the MIT License. Original
documentation, figure assemblies, and derived non-restricted tables are
distributed under CC BY 4.0. Third-party GEO source data are not redistributed
and remain subject to their original terms.
