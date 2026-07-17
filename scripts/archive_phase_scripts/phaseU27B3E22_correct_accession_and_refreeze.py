#!/usr/bin/env python3
"""
Phase U27B3E2.2
Targeted correction of the recurrent-UTI accession from GSE168600 to GSE186800.

Scientific resolution
---------------------
- GSE186800 is the Gardnerella-triggered recurrent-UTI bladder dataset used by
  the computational analysis.
- GSE168600 is an unrelated KLF5/skin dataset and entered only as a later
  manuscript/audit label substitution.

This phase creates new corrected derivatives. It does not overwrite historical
artifacts or recalculate any scientific value.

Actions
-------
1. Correct the current v6.2 submission-architecture manuscript to v6.3 by
   replacing GSE168600 with GSE186800 in OOXML text parts.
2. Correct the definitive legend package and panel-level legend provenance.
3. Correct the U27B3E2 supplementary source descriptions and source map.
4. Verify that frozen Figure 1-8 masters already contain no GSE168600 text and
   that the manuscript embeds the unchanged frozen PNG masters.
5. Create a canonical corrected Results text snapshot and accession rules.
6. Render the corrected manuscript and create a contact sheet.
7. Record historical erroneous artifacts as superseded rather than modifying
   them in place.

No module score, effect size, p-value, FDR, cell count, figure value or source
matrix is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

import pandas as pd

try:
    from PIL import Image
except ImportError as exc:
    raise RuntimeError("Pillow is required for contact-sheet generation.") from exc


VERSION = "U27B3E22_v1.0_2026-07-16"
TAG = "phaseU27B3E22_targeted_accession_correction"

WRONG = "GSE168600"
CORRECT = "GSE186800"

SOURCE_MANUSCRIPT_REL = (
    "09_manuscript_docx/"
    "phaseU27B3E1_reference_supplement_submission_architecture/"
    "UTI_HostOmics_preZotero_manuscript_v6_2_"
    "U27B3E1_submission_architecture_cleaned.docx"
)

OUTPUT_MANUSCRIPT_NAME = (
    "UTI_HostOmics_preZotero_manuscript_v6_3_"
    "U27B3E22_accession_corrected.docx"
)

LEGEND_SOURCE_TAG = "phaseU27B3B_definitive_figure_legend_construction"
FIGURE_SOURCE_TAG = "phaseU27B3A_complete_eight_figure_package_assembly"
SUPPLEMENT_SOURCE_TAG = (
    "phaseU27B3E2_reference_frontmatter_supplement_source_confirmation"
)
LINEAGE_AUDIT_TAG = "phaseU27B3E21_dataset_accession_lineage_audit"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"w": W_NS, "r": R_NS, "a": A_NS}


def log(message: str) -> None:
    print(f"[U27B3E2.2] {message}", flush=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def count_term(text: str, term: str) -> int:
    return len(re.findall(re.escape(term), text, flags=re.IGNORECASE))


def replace_text(text: str) -> str:
    replacements = [
        (WRONG, CORRECT),
        ("v6.2", "v6.3"),
        ("U27B3E1", "U27B3E22"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def reverse_expected_changes(text: str) -> str:
    replacements = [
        (CORRECT, WRONG),
        ("v6.3", "v6.2"),
        ("U27B3E22", "U27B3E1"),
    ]
    for new, old in replacements:
        text = text.replace(new, old)
    return text


def patch_plain_text(source: Path, output: Path) -> Dict[str, object]:
    raw = source.read_text(encoding="utf-8", errors="ignore")
    corrected = replace_text(raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(corrected, encoding="utf-8")
    return {
        "source_path": str(source),
        "output_path": str(output),
        "source_sha256": sha256_file(source),
        "output_sha256": sha256_file(output),
        "wrong_before": count_term(raw, WRONG),
        "wrong_after": count_term(corrected, WRONG),
        "correct_before": count_term(raw, CORRECT),
        "correct_after": count_term(corrected, CORRECT),
        "content_equivalent_after_reverse_normalization": (
            normalize_text(raw)
            == normalize_text(reverse_expected_changes(corrected))
        ),
    }


def patch_zip_text_parts(source: Path, output: Path) -> Dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    wrong_before = 0
    wrong_after = 0
    correct_before = 0
    correct_after = 0
    patched_members = 0

    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            lower = info.filename.lower()
            is_text_part = lower.endswith((".xml", ".rels", ".txt"))

            if is_text_part:
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = ""

                if text:
                    wrong_before += count_term(text, WRONG)
                    correct_before += count_term(text, CORRECT)
                    patched = replace_text(text)
                    wrong_after += count_term(patched, WRONG)
                    correct_after += count_term(patched, CORRECT)
                    if patched != text:
                        patched_members += 1
                    data = patched.encode("utf-8")

            zout.writestr(info, data)

    return {
        "source_path": str(source),
        "output_path": str(output),
        "source_sha256": sha256_file(source),
        "output_sha256": sha256_file(output),
        "wrong_before": wrong_before,
        "wrong_after": wrong_after,
        "correct_before": correct_before,
        "correct_after": correct_after,
        "patched_archive_members": patched_members,
    }


def extract_docx_text(path: Path) -> str:
    pieces: List[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            lower = name.lower()
            if not (
                lower.startswith("word/")
                and lower.endswith(".xml")
            ):
                continue
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError:
                continue
            for node in root.iter():
                local = node.tag.rsplit("}", 1)[-1]
                if local == "t" and node.text:
                    pieces.append(node.text)
                elif local in {"tab", "br", "cr"}:
                    pieces.append("\n")
    return normalize_text(" ".join(pieces))


def document_paragraphs(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", NS)
    if body is None:
        return []

    paragraphs: List[str] = []
    for element in list(body):
        if element.tag != f"{{{W_NS}}}p":
            continue
        pieces: List[str] = []
        for node in element.iter():
            local = node.tag.rsplit("}", 1)[-1]
            if local == "t":
                pieces.append(node.text or "")
            elif local in {"tab", "br", "cr"}:
                pieces.append("\n")
        paragraphs.append(normalize_text("".join(pieces)))
    return paragraphs


def extract_section_text(path: Path, start_heading: str, end_heading: str) -> str:
    paragraphs = document_paragraphs(path)

    def heading_index(target: str) -> int:
        matches = []
        for index, text in enumerate(paragraphs):
            cleaned = re.sub(
                r"^\d+(?:\.\d+)*\s*", "", text.lower()
            ).rstrip(".: ")
            if cleaned == target.lower():
                matches.append(index)
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one heading {target!r}; observed {matches}."
            )
        return matches[0]

    start = heading_index(start_heading)
    end = heading_index(end_heading)
    if start >= end:
        raise RuntimeError(f"{start_heading} does not precede {end_heading}.")
    return "\n\n".join(paragraphs[start + 1:end])


def ordered_embedded_media_hashes(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as archive:
        document_root = ET.fromstring(archive.read("word/document.xml"))
        relationships_root = ET.fromstring(
            archive.read("word/_rels/document.xml.rels")
        )
        rel_map = {
            rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
            for rel in relationships_root
        }

        hashes: List[str] = []
        for blip in document_root.findall(".//a:blip", NS):
            rel_id = blip.attrib.get(f"{{{R_NS}}}embed", "")
            target = rel_map.get(rel_id, "")
            if not target:
                continue
            archive_path = target.lstrip("/")
            if not archive_path.startswith("word/"):
                archive_path = f"word/{archive_path}"
            if archive_path not in archive.namelist():
                continue
            hashes.append(sha256_bytes(archive.read(archive_path)))
    return hashes


def run_command(command: Sequence[str], env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(command),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )


def extract_pdf_text(path: Path) -> str:
    executable = shutil.which("pdftotext")
    if not executable:
        return ""
    with tempfile.TemporaryDirectory(prefix="u27b3e22_pdf_") as tmp:
        output = Path(tmp) / "out.txt"
        result = run_command([executable, str(path), str(output)])
        if result.returncode != 0 or not output.exists():
            return ""
        return output.read_text(encoding="utf-8", errors="ignore")


def figure_asset_audit(project: Path) -> Tuple[pd.DataFrame, List[Path]]:
    figure_dir = project / "06_figures" / FIGURE_SOURCE_TAG
    rows: List[Dict[str, object]] = []
    png_paths: List[Path] = []

    for number in range(1, 9):
        paths = {
            extension: figure_dir / f"UTI_HostOmics_U27B3A_Figure_{number}.{extension}"
            for extension in ("png", "svg", "pdf")
        }
        png_paths.append(paths["png"])

        svg_text = (
            paths["svg"].read_text(encoding="utf-8", errors="ignore")
            if paths["svg"].exists()
            else ""
        )
        pdf_text = extract_pdf_text(paths["pdf"]) if paths["pdf"].exists() else ""

        rows.append(
            {
                "figure_number": number,
                "png_path": str(paths["png"]),
                "svg_path": str(paths["svg"]),
                "pdf_path": str(paths["pdf"]),
                "png_exists": paths["png"].exists(),
                "svg_exists": paths["svg"].exists(),
                "pdf_exists": paths["pdf"].exists(),
                "png_sha256": sha256_file(paths["png"]) if paths["png"].exists() else "",
                "svg_wrong_accession_occurrences": count_term(svg_text, WRONG),
                "pdf_wrong_accession_occurrences": count_term(pdf_text, WRONG),
                "svg_correct_accession_occurrences": count_term(svg_text, CORRECT),
                "pdf_correct_accession_occurrences": count_term(pdf_text, CORRECT),
                "figure_asset_requires_rebuild": (
                    count_term(svg_text, WRONG) > 0
                    or count_term(pdf_text, WRONG) > 0
                ),
            }
        )

    return pd.DataFrame(rows), png_paths


def make_contact_sheet(paths: Sequence[Path], output: Path, columns: int = 3, cell_width: int = 620, padding: int = 22) -> None:
    images: List[Image.Image] = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        ratio = cell_width / image.width
        images.append(
            image.resize((cell_width, max(1, int(image.height * ratio))))
        )

    if not images:
        raise RuntimeError("No page images were available for the contact sheet.")

    rows = (len(images) + columns - 1) // columns
    row_heights: List[int] = []
    for row in range(rows):
        subset = images[row * columns:(row + 1) * columns]
        row_heights.append(max(image.height for image in subset))

    width = columns * cell_width + (columns + 1) * padding
    height = sum(row_heights) + (rows + 1) * padding
    canvas = Image.new("RGB", (width, height), "white")

    y = padding
    for row in range(rows):
        x = padding
        subset = images[row * columns:(row + 1) * columns]
        for image in subset:
            canvas.paste(image, (x, y))
            x += cell_width + padding
        y += row_heights[row] + padding

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def render_docx(docx_path: Path, render_dir: Path) -> Dict[str, object]:
    render_dir.mkdir(parents=True, exist_ok=True)
    libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
    pdftoppm = shutil.which("pdftoppm")

    if not libreoffice:
        return {
            "render_pass": False,
            "reason": "LibreOffice/soffice not found",
            "page_count": 0,
            "pdf_path": "",
            "contact_sheet": "",
        }
    if not pdftoppm:
        return {
            "render_pass": False,
            "reason": "pdftoppm not found",
            "page_count": 0,
            "pdf_path": "",
            "contact_sheet": "",
        }

    for old in render_dir.glob("page-*.png"):
        old.unlink()

    with tempfile.TemporaryDirectory(prefix="u27b3e22_lo_") as tmp:
        env = os.environ.copy()
        env["HOME"] = tmp
        profile_uri = Path(tmp).resolve().as_uri()
        result = run_command(
            [
                libreoffice,
                "--headless",
                f"-env:UserInstallation={profile_uri}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(render_dir),
                str(docx_path),
            ],
            env=env,
        )

    pdf_path = render_dir / f"{docx_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists():
        return {
            "render_pass": False,
            "reason": result.stderr.strip() or result.stdout.strip() or "LibreOffice conversion failed",
            "page_count": 0,
            "pdf_path": str(pdf_path),
            "contact_sheet": "",
        }

    raster = run_command(
        [
            pdftoppm,
            "-png",
            "-r",
            "140",
            str(pdf_path),
            str(render_dir / "page"),
        ]
    )
    page_paths = sorted(
        render_dir.glob("page-*.png"),
        key=lambda path: int(re.search(r"(\d+)$", path.stem).group(1)),
    )
    if raster.returncode != 0 or not page_paths:
        return {
            "render_pass": False,
            "reason": raster.stderr.strip() or raster.stdout.strip() or "PDF rasterization failed",
            "page_count": len(page_paths),
            "pdf_path": str(pdf_path),
            "contact_sheet": "",
        }

    contact_sheet = render_dir / "UTI_HostOmics_U27B3E22_render_contact_sheet.png"
    make_contact_sheet(page_paths, contact_sheet)
    return {
        "render_pass": bool(contact_sheet.exists() and contact_sheet.stat().st_size > 0),
        "reason": "Render files created",
        "page_count": len(page_paths),
        "pdf_path": str(pdf_path),
        "contact_sheet": str(contact_sheet),
    }


def copy_and_patch_table(source: Path, output: Path) -> Dict[str, object]:
    raw = source.read_text(encoding="utf-8", errors="ignore")
    corrected = raw.replace(WRONG, CORRECT)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(corrected, encoding="utf-8")
    return {
        "source_path": str(source),
        "output_path": str(output),
        "source_sha256": sha256_file(source),
        "output_sha256": sha256_file(output),
        "wrong_before": count_term(raw, WRONG),
        "wrong_after": count_term(corrected, WRONG),
        "correct_before": count_term(raw, CORRECT),
        "correct_after": count_term(corrected, CORRECT),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    source_manuscript = project / SOURCE_MANUSCRIPT_REL
    if not source_manuscript.exists():
        raise FileNotFoundError(f"Source v6.2 manuscript not found: {source_manuscript}")

    outdocx = project / "09_manuscript_docx" / TAG
    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outmanuscript = project / "07_manuscript" / TAG
    outresults = project / "05_results" / TAG
    render_dir = outdocx / "render_qa"

    for directory in (outdocx, outtables, outmetadata, outmanuscript, outresults, render_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source_hash_before = sha256_file(source_manuscript)
    output_manuscript = outdocx / OUTPUT_MANUSCRIPT_NAME

    artifact_rows: List[Dict[str, object]] = []

    manuscript_patch = patch_zip_text_parts(source_manuscript, output_manuscript)
    manuscript_patch["artifact_type"] = "submission_manuscript"
    artifact_rows.append(manuscript_patch)

    source_text = extract_docx_text(source_manuscript)
    corrected_text = extract_docx_text(output_manuscript)
    text_equivalent = (
        normalize_text(source_text)
        == normalize_text(reverse_expected_changes(corrected_text))
    )

    # Correct definitive legend files.
    legend_source_dir = project / "07_manuscript" / LEGEND_SOURCE_TAG
    legend_specs = [
        (
            legend_source_dir / "UTI_HostOmics_U27B3B_definitive_figure_legends.md",
            outmanuscript / "UTI_HostOmics_U27B3E22_definitive_figure_legends_accession_corrected.md",
        ),
        (
            legend_source_dir / "UTI_HostOmics_U27B3B_manuscript_legend_insert.txt",
            outmanuscript / "UTI_HostOmics_U27B3E22_manuscript_legend_insert_accession_corrected.txt",
        ),
    ]

    for source, output in legend_specs:
        if not source.exists():
            raise FileNotFoundError(f"Legend source not found: {source}")
        row = patch_plain_text(source, output)
        row["artifact_type"] = "definitive_legend_text"
        artifact_rows.append(row)

    legend_docx_source = legend_source_dir / "UTI_HostOmics_U27B3B_definitive_figure_legends.docx"
    legend_docx_output = outmanuscript / "UTI_HostOmics_U27B3E22_definitive_figure_legends_accession_corrected.docx"
    if not legend_docx_source.exists():
        raise FileNotFoundError(f"Legend DOCX not found: {legend_docx_source}")
    row = patch_zip_text_parts(legend_docx_source, legend_docx_output)
    row["artifact_type"] = "definitive_legend_docx"
    artifact_rows.append(row)

    # Correct legend provenance and related metadata without overwriting U27B3B.
    legend_metadata_dir = project / "03_metadata" / LEGEND_SOURCE_TAG
    if legend_metadata_dir.exists():
        for source in sorted(legend_metadata_dir.iterdir()):
            if not source.is_file() or source.suffix.lower() not in {".tsv", ".txt", ".md", ".json"}:
                continue
            output = outmetadata / source.name.replace("U27B3B", "U27B3E22")
            row = patch_plain_text(source, output)
            row["artifact_type"] = "legend_or_provenance_metadata"
            artifact_rows.append(row)

    # Correct U27B3E2 supplementary source descriptions and source map.
    supplement_table_dir = project / "06_tables" / SUPPLEMENT_SOURCE_TAG
    supplement_files = [
        "UTI_HostOmics_U27B3E2_supplementary_source_confirmation_summary.tsv",
        "UTI_HostOmics_U27B3E2_supplementary_source_lock_map.tsv",
        "UTI_HostOmics_U27B3E2_supplementary_top_candidate_summary.tsv",
        "UTI_HostOmics_U27B3E2_supplementary_source_candidate_registry.tsv",
    ]
    corrected_supplement_paths: List[Path] = []
    for filename in supplement_files:
        source = supplement_table_dir / filename
        if not source.exists():
            continue
        output = outtables / filename.replace("U27B3E2", "U27B3E22")
        row = copy_and_patch_table(source, output)
        row["artifact_type"] = "supplementary_source_map"
        artifact_rows.append(row)
        corrected_supplement_paths.append(output)

    # Create canonical corrected Results snapshot.
    corrected_results = extract_section_text(output_manuscript, "Results", "Discussion")
    corrected_results_path = outmanuscript / "UTI_HostOmics_U27B3E22_canonical_corrected_results_section.txt"
    corrected_results_path.write_text(corrected_results + "\n", encoding="utf-8")

    # Validate frozen figure masters; do not rebuild when they are already correct.
    figure_audit, png_paths = figure_asset_audit(project)
    figure_audit.to_csv(
        outtables / "UTI_HostOmics_U27B3E22_frozen_figure_accession_audit.tsv",
        sep="\t",
        index=False,
    )

    for path in png_paths:
        if not path.exists():
            raise FileNotFoundError(f"Frozen figure PNG missing: {path}")

    embedded_hashes = ordered_embedded_media_hashes(output_manuscript)
    frozen_png_hashes = [sha256_file(path) for path in png_paths]
    embedded_images_match = embedded_hashes == frozen_png_hashes

    # Record disposition of all U27B3E2.1 targets.
    target_registry_path = (
        project
        / "06_tables"
        / LINEAGE_AUDIT_TAG
        / "UTI_HostOmics_U27B3E21_accession_correction_target_registry.tsv"
    )
    disposition_rows: List[Dict[str, object]] = []
    if target_registry_path.exists():
        targets = pd.read_csv(target_registry_path, sep="\t", low_memory=False)
        for row in targets.itertuples(index=False):
            path = str(getattr(row, "path", ""))
            lower = path.lower()
            if path == str(source_manuscript):
                disposition = "CORRECTED_IN_V6_3_DERIVATIVE"
            elif f"/{LEGEND_SOURCE_TAG.lower()}/" in lower:
                disposition = "CORRECTED_IN_U27B3E22_LEGEND_PACKAGE"
            elif f"/{SUPPLEMENT_SOURCE_TAG.lower()}/" in lower:
                disposition = "CORRECTED_OR_SUPERSEDED_BY_U27B3E22_SOURCE_MAP"
            else:
                disposition = "HISTORICAL_ARTIFACT_RETAINED_READ_ONLY_AND_SUPERSEDED"
            disposition_rows.append(
                {
                    "source_path": path,
                    "classification": str(getattr(row, "classification", "")),
                    "wrong_accession_occurrences": int(getattr(row, "GSE168600_occurrences", 0)),
                    "disposition": disposition,
                    "historical_file_modified": False,
                }
            )

    pd.DataFrame(disposition_rows).to_csv(
        outtables / "UTI_HostOmics_U27B3E22_correction_target_disposition_registry.tsv",
        sep="\t",
        index=False,
    )

    # Canonical future audit rules.
    pd.DataFrame(
        [
            {
                "rule_id": "required_recurrent_UTI_accession",
                "term": CORRECT,
                "rule": "required",
                "scientific_identity": (
                    "Gardnerella-triggered recurrent UTI bladder-reservoir model"
                ),
            },
            {
                "rule_id": "prohibited_unrelated_skin_accession",
                "term": WRONG,
                "rule": "prohibited",
                "scientific_identity": "KLF5 skin and sphingolipid dataset",
            },
        ]
    ).to_csv(
        outmetadata / "UTI_HostOmics_U27B3E22_accession_validation_rules.tsv",
        sep="\t",
        index=False,
    )

    artifact_audit = pd.DataFrame(artifact_rows)
    artifact_audit.to_csv(
        outtables / "UTI_HostOmics_U27B3E22_corrected_artifact_manifest.tsv",
        sep="\t",
        index=False,
    )

    source_hash_after = sha256_file(source_manuscript)
    source_unchanged = source_hash_before == source_hash_after

    corrected_manuscript_wrong_absent = count_term(corrected_text, WRONG) == 0
    corrected_manuscript_correct_present = count_term(corrected_text, CORRECT) > 0
    results_wrong_absent = count_term(corrected_results, WRONG) == 0
    results_correct_present = count_term(corrected_results, CORRECT) > 0

    legend_outputs = [Path(path) for path in artifact_audit.loc[
        artifact_audit["artifact_type"].astype(str).str.contains("legend"),
        "output_path",
    ].tolist()]
    legends_wrong_absent = True
    legends_correct_present = False
    for path in legend_outputs:
        text = extract_docx_text(path) if path.suffix.lower() == ".docx" else path.read_text(encoding="utf-8", errors="ignore")
        legends_wrong_absent = legends_wrong_absent and count_term(text, WRONG) == 0
        legends_correct_present = legends_correct_present or count_term(text, CORRECT) > 0

    supplement_wrong_absent = True
    for path in corrected_supplement_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        supplement_wrong_absent = supplement_wrong_absent and count_term(text, WRONG) == 0

    figures_require_rebuild = bool(figure_audit["figure_asset_requires_rebuild"].any())
    figures_accession_clean = not figures_require_rebuild

    render_info = render_docx(output_manuscript, render_dir)
    pd.DataFrame([render_info]).to_csv(
        outtables / "UTI_HostOmics_U27B3E22_render_audit.tsv",
        sep="\t",
        index=False,
    )

    preservation = pd.DataFrame(
        [
            {
                "source_manuscript": str(source_manuscript),
                "source_sha256_before": source_hash_before,
                "source_sha256_after": source_hash_after,
                "source_unchanged": source_unchanged,
                "corrected_manuscript": str(output_manuscript),
                "corrected_sha256": sha256_file(output_manuscript),
                "text_equivalent_except_accession_and_version_labels": text_equivalent,
                "source_wrong_accession_occurrences": count_term(source_text, WRONG),
                "corrected_wrong_accession_occurrences": count_term(corrected_text, WRONG),
                "corrected_correct_accession_occurrences": count_term(corrected_text, CORRECT),
                "results_wrong_accession_absent": results_wrong_absent,
                "results_correct_accession_present": results_correct_present,
                "embedded_images_before": len(ordered_embedded_media_hashes(source_manuscript)),
                "embedded_images_after": len(embedded_hashes),
                "embedded_images_match_frozen_png_masters": embedded_images_match,
                "figures_require_rebuild": figures_require_rebuild,
                "scientific_values_recalculated": False,
                "source_locks_changed": False,
            }
        ]
    )
    preservation.to_csv(
        outtables / "UTI_HostOmics_U27B3E22_preservation_and_accession_audit.tsv",
        sep="\t",
        index=False,
    )

    all_pass = all(
        [
            source_unchanged,
            text_equivalent,
            corrected_manuscript_wrong_absent,
            corrected_manuscript_correct_present,
            results_wrong_absent,
            results_correct_present,
            legends_wrong_absent,
            legends_correct_present,
            supplement_wrong_absent,
            figures_accession_clean,
            embedded_images_match,
            bool(render_info["render_pass"]),
        ]
    )

    if all_pass:
        decision = "READY_FOR_U27B3E23_ACCESSION_CORRECTION_VISUAL_AUDIT"
    elif figures_require_rebuild:
        decision = "TARGETED_FROZEN_FIGURE_ACCESSION_REBUILD_REQUIRED"
    else:
        decision = "TARGETED_U27B3E22_ACCESSION_CORRECTION_REPAIR_REQUIRED"

    pd.DataFrame(
        [
            {
                "phase": "U27B3E2.2",
                "decision": decision,
                "source_manuscript_unchanged": source_unchanged,
                "corrected_manuscript_created": output_manuscript.exists(),
                "manuscript_wrong_accession_absent": corrected_manuscript_wrong_absent,
                "manuscript_correct_accession_present": corrected_manuscript_correct_present,
                "results_accession_corrected": results_wrong_absent and results_correct_present,
                "definitive_legends_accession_corrected": legends_wrong_absent and legends_correct_present,
                "supplementary_source_maps_accession_corrected": supplement_wrong_absent,
                "frozen_figure_assets_accession_clean": figures_accession_clean,
                "embedded_images_match_frozen_masters": embedded_images_match,
                "render_pass": bool(render_info["render_pass"]),
                "render_pages": int(render_info["page_count"]),
                "scientific_values_recalculated": False,
                "source_locks_changed": False,
                "historical_artifacts_overwritten": False,
                "supplementary_materialization_allowed": False,
                "next_phase": (
                    "U27B3E2.3 visually inspect the corrected v6.3 manuscript and re-release U27B3E3"
                    if decision.startswith("READY_FOR_U27B3E23")
                    else "Inspect failed correction audits"
                ),
            }
        ]
    ).to_csv(
        outtables / "UTI_HostOmics_U27B3E22_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    pd.DataFrame(
        [
            {"field": "correct_accession", "value": CORRECT},
            {"field": "incorrect_accession", "value": WRONG},
            {"field": "source_manuscript", "value": str(source_manuscript)},
            {"field": "corrected_manuscript", "value": str(output_manuscript)},
            {"field": "corrected_results_snapshot", "value": str(corrected_results_path)},
            {"field": "figure_package", "value": str(project / "06_figures" / FIGURE_SOURCE_TAG)},
            {"field": "source_figures_modified", "value": "False"},
        ]
    ).to_csv(
        outmetadata / "UTI_HostOmics_U27B3E22_corrected_lineage_record.tsv",
        sep="\t",
        index=False,
    )

    report_path = outresults / "UTI_HostOmics_U27B3E22_targeted_accession_correction_report.md"
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# Phase U27B3E2.2 - Targeted dataset-accession correction\n\n")
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(f"- Correct accession: **{CORRECT}**.\n")
        handle.write(f"- Incorrect substituted accession removed: **{WRONG}**.\n")
        handle.write(f"- Corrected manuscript: `{output_manuscript}`\n")
        handle.write(f"- Source manuscript unchanged: **{source_unchanged}**.\n")
        handle.write(f"- Text equivalent apart from approved accession/version changes: **{text_equivalent}**.\n")
        handle.write(f"- Corrected Results snapshot: `{corrected_results_path}`\n")
        handle.write(f"- Definitive legends corrected: **{legends_wrong_absent and legends_correct_present}**.\n")
        handle.write(f"- Supplementary source maps corrected: **{supplement_wrong_absent}**.\n")
        handle.write(f"- Frozen figures require rebuild: **{figures_require_rebuild}**.\n")
        handle.write(f"- Embedded figures match frozen PNG masters: **{embedded_images_match}**.\n")
        handle.write(f"- Render pass: **{render_info['render_pass']}**.\n")
        handle.write(f"- Rendered pages: **{render_info['page_count']}**.\n")
        handle.write(f"- Contact sheet: `{render_info['contact_sheet']}`.\n\n")

        handle.write("## Scientific resolution\n\n")
        handle.write(
            "The computational lineage already used GSE186800 matrices, sample designs, "
            "Gardnerella/PBS contrasts and recurrent-UTI model outputs. The later GSE168600 "
            "substitution was therefore corrected as a manuscript, legend and audit-label "
            "error without recalculating scientific values.\n\n"
        )

        handle.write("## Historical-artifact policy\n\n")
        handle.write(
            "Historical files containing the incorrect accession remain unchanged for audit "
            "traceability and are superseded by the U27B3E22 corrected derivatives. Future "
            "audits must require GSE186800 and prohibit GSE168600.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "correct_accession": CORRECT,
        "incorrect_accession": WRONG,
        "source_manuscript": str(source_manuscript),
        "source_sha256": source_hash_before,
        "corrected_manuscript": str(output_manuscript),
        "corrected_sha256": sha256_file(output_manuscript),
        "source_unchanged": source_unchanged,
        "text_equivalent_except_approved_changes": text_equivalent,
        "results_corrected": results_wrong_absent and results_correct_present,
        "legends_corrected": legends_wrong_absent and legends_correct_present,
        "supplementary_maps_corrected": supplement_wrong_absent,
        "figures_require_rebuild": figures_require_rebuild,
        "embedded_images_match": embedded_images_match,
        "render_pass": bool(render_info["render_pass"]),
        "render_pages": int(render_info["page_count"]),
        "scientific_values_recalculated": False,
        "source_locks_changed": False,
        "historical_artifacts_overwritten": False,
        "supplementary_materialization_allowed": False,
    }
    (outresults / "UTI_HostOmics_U27B3E22_run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    log(f"Source manuscript unchanged: {source_unchanged}")
    log(f"Text equivalent except approved changes: {text_equivalent}")
    log(f"Manuscript accession corrected: {corrected_manuscript_wrong_absent and corrected_manuscript_correct_present}")
    log(f"Results accession corrected: {results_wrong_absent and results_correct_present}")
    log(f"Legends accession corrected: {legends_wrong_absent and legends_correct_present}")
    log(f"Supplementary source maps corrected: {supplement_wrong_absent}")
    log(f"Frozen figures require rebuild: {figures_require_rebuild}")
    log(f"Embedded images match frozen masters: {embedded_images_match}")
    log(f"Render pass: {render_info['render_pass']}")
    log(f"Decision: {decision}")
    log(f"Output manuscript: {output_manuscript}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3E2.2] ERROR: {exc}", file=sys.stderr)
        raise
