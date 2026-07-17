# UTI HostOmics — mSystems manuscript and file audit

**Audit date:** 17 July 2026  
**Target article type:** mSystems Research Article  
**Source working manuscript:** `UTI_HostOmics_v3.docx`  
**Converted manuscript:** `UTI_HostOmics_v4.docx`

## 1. Manuscript conversion completed

The v4 manuscript was rebuilt for the mSystems Research Article structure and visually inspected page by page after rendering.

| Requirement | v4 status | Observed |
|---|---:|---|
| Main text guidance | Pass | 4,876 words; journal guidance is 5,000 words, excluding references, table footnotes, and figure legends |
| Abstract | Pass | 195 words; maximum 250 |
| Importance | Pass | 120 words; maximum 150; reference-free and organism named |
| Running title | Pass | 41 characters; maximum 54 characters and spaces |
| Title-page affiliation format | Pass | Lowercase superscript letters; corresponding author marked with `#` |
| Corresponding-author email | Pass | One email on title page: `rmaghembe@sfuchas.ac.tz` |
| Required major sections | Pass | Abstract; Importance; Introduction; Materials and Methods; Results; Discussion; Data, Metadata, and Code Availability; Acknowledgments; Conflict of Interest; References |
| Citation style | Pass | Numbered citation-sequence style; 57 references; no author–date citations remain |
| Figure order and citation | Pass | Fig. 1–8 cited in numerical order and all cited in the text |
| Supplemental-table citation | Pass | Table S1–S10 cited in the text |
| Figure legends | Pass | Legends follow References and begin `FIG 1.`, `FIG 2.`, etc. |
| Page layout | Pass | US Letter, at least 12-point text, double-spaced body/references/legends, consecutively numbered pages |
| Internal project language | Pass | No phase labels, project footers, internal audit language, or GSE168600 occurrence |
| Visual QA | Pass | All 44 rendered manuscript pages and the supplemental-legends page were inspected; no clipping, overlap, blank transition pages, headers, or footers remain |

## 2. Correct mSystems citation terminology

Use the following forms throughout the submission:

- Main figures in running text: `Fig. 1`, `Fig. 2A to C`, `Fig. 3G and Fig. 7A and B`.
- Main figure legends: `FIG 1.`, `FIG 2.`, and so forth.
- Supplemental items: `Table S1`, `Table S2`, or `Fig. S1` when supplemental figures exist.
- Collective description: `supplemental material`.
- Do not use `Appendix` or `Supplementary Table` for these files.

The manuscript contains no supplemental figures; its supplemental material consists of Tables S1–S10.

## 3. Current file inventory

| File | Purpose | Format/integrity | Status |
|---|---|---|---:|
| `UTI_HostOmics_v4.docx` | Initial-submission manuscript, with eight figures embedded after the legends | Valid DOCX; 3.46 MB; 44-page render passed | Ready |
| `UTI_HostOmics_mSystems_Table_S1-S10.xlsx` | Tables S1–S10 | Valid Excel workbook; 0.50 MB; SHA256 `2ad8345d5ec73ba760a92594a938fac78190ff317ed7a48418cafe7e5b11b7da` | Ready |
| `UTI_HostOmics_mSystems_Supplemental_Legends.docx` | Legends for Tables S1–S10 | Valid DOCX; one-page render passed | Ready |
| `UTI_HostOmics_mSystems_Figures_TIFF.zip` | Separate revision-grade Fig. 1–8 files | Eight RGB LZW TIFFs, 300 dpi, each no larger than 7 × 9 inches and well below 20 MB | Ready |

The initial submission is format-neutral, so the DOCX with embedded figures is acceptable. The separate TIFF package is prepared for a revision/final-file request. Excel is an accepted supplemental-material format. The workbook and legends may be uploaded as two supplemental files; this is within the journal maximum of 10 files and below the 15 MB supplemental-file limit.

## 4. Items still required before submission

The scientific manuscript and associated table/figure files are prepared, but the submission package is **not yet complete**.

1. **Cover letter:** required at initial submission and not yet prepared.
2. **Public code/derived-data release:** the manuscript still contains prospective repository wording. mSystems expects data, metadata, and code to be available for editorial and peer review. A public GitHub release and archived DOI-bearing version should be created, then the URL, release tag, and DOI inserted into the manuscript.
3. **Corresponding-author ORCID:** required in the submission portal.
4. **Portal author information:** all coauthor email addresses and confirmation of affiliations are required.
5. **Reviewer information:** at least three preferred reviewers, with names, emails, and institutions, is required by the submission checklist; preferred editor information should also be prepared.
6. **Portal declarations:** data availability, funding, conflict of interest, ethics applicability, keywords/research areas, and any preprint information must be entered in the submission system.

## 5. Readiness decision

**READY_FOR_GITHUB_ZENODO_RELEASE_AND_FINAL_MSYSTEMS_SUBMISSION_PACKAGE_COMPLETION**

After repository publication, the remaining manuscript edit is limited to replacing the prospective text in `Data, Metadata, and Code Availability` with the final GitHub URL, release tag, and Zenodo DOI. The next submission-facing files should then be the cover letter, final repository-linked manuscript, reviewer/editor list, and a final upload manifest.
