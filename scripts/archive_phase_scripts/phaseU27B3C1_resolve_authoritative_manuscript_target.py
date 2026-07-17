#!/usr/bin/env python3
"""
Phase U27B3C1
Resolve the authoritative manuscript target before Results-section drafting.

The script recursively inventories manuscript-like DOCX files in the project,
extracts text non-destructively, scores candidates using filename, section
coverage, word count and recency, and writes a transparent candidate ranking.

No manuscript or figure file is modified.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence, Tuple
from xml.etree import ElementTree as ET

import pandas as pd


VERSION = "U27B3C1_v1.0_2026-07-16"
TAG = "phaseU27B3C1_manuscript_target_resolution"

MANUSCRIPT_HEADINGS = (
    "abstract",
    "introduction",
    "methods",
    "materials and methods",
    "results",
    "discussion",
    "conclusion",
    "references",
)

POSITIVE_FILENAME_TERMS = {
    "manuscript": 45,
    "main_text": 35,
    "main text": 35,
    "article": 24,
    "submission": 20,
    "draft": 12,
    "revised": 10,
    "revision": 10,
    "complete": 8,
    "final": 8,
    "uti": 6,
    "hostomics": 6,
}

NEGATIVE_FILENAME_TERMS = {
    "legend": -70,
    "figure": -35,
    "supplement": -35,
    "supporting": -30,
    "cover_letter": -60,
    "cover letter": -60,
    "response": -50,
    "rebuttal": -50,
    "matrix": -50,
    "protocol": -45,
    "proposal": -45,
    "reviewer": -40,
    "checklist": -40,
    "template": -35,
    "appendix": -20,
    "table": -20,
}

SKIP_DIRECTORY_NAMES = {
    ".git",
    "__pycache__",
    "03_data_raw",
    "03_data_processed",
    "04_results",
    "05_results",
    "06_figures",
    "06_tables",
    "08_logs",
    "09_archives",
    "10_scripts",
    "node_modules",
}

GENERATED_LEGEND_TAG = "phaseU27B3B_definitive_figure_legend_construction"


def log(message: str) -> None:
    print(f"[U27B3C1] {message}", flush=True)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_docx_text(path: Path) -> str:
    """
    Extract visible paragraph text from word/document.xml without modifying the
    DOCX and without requiring python-docx.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except Exception:
        return ""

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ""

    namespace = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    }

    paragraphs: List[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        pieces = [
            node.text or ""
            for node in paragraph.findall(".//w:t", namespace)
        ]
        text = normalize("".join(pieces))
        if text:
            paragraphs.append(text)

    return "\n".join(paragraphs)


def section_hits(text: str) -> List[str]:
    lower = text.lower()
    hits = []
    for heading in MANUSCRIPT_HEADINGS:
        pattern = rf"(?m)^\s*{re.escape(heading)}\s*$"
        if re.search(pattern, lower):
            hits.append(heading)

    # Fallback for documents whose extracted paragraphs include numbering or
    # punctuation around headings.
    if not hits:
        lines = [normalize(line).lower() for line in text.splitlines()]
        for heading in MANUSCRIPT_HEADINGS:
            if any(
                re.fullmatch(
                    rf"(?:\d+(?:\.\d+)*)?\s*{re.escape(heading)}[:.]?",
                    line,
                )
                for line in lines
            ):
                hits.append(heading)

    return sorted(set(hits))


def filename_score(name: str) -> Tuple[int, List[str], List[str]]:
    lower = name.lower().replace("-", "_")
    score = 0
    positive = []
    negative = []

    for term, weight in POSITIVE_FILENAME_TERMS.items():
        if term in lower:
            score += weight
            positive.append(term)

    for term, weight in NEGATIVE_FILENAME_TERMS.items():
        if term in lower:
            score += weight
            negative.append(term)

    return score, positive, negative


def version_signal(name: str) -> int:
    lower = name.lower()
    matches = re.findall(r"(?:^|[_\-\s])v(\d+(?:\.\d+)*)", lower)
    if not matches:
        return 0

    values = []
    for value in matches:
        try:
            components = [int(part) for part in value.split(".")]
            numeric = components[0] * 100
            if len(components) > 1:
                numeric += min(components[1], 99)
            values.append(numeric)
        except ValueError:
            continue

    return max(values, default=0)


def should_skip(path: Path, project: Path) -> bool:
    try:
        relative_parts = path.relative_to(project).parts
    except ValueError:
        relative_parts = path.parts

    if any(part in SKIP_DIRECTORY_NAMES for part in relative_parts):
        return True

    if GENERATED_LEGEND_TAG in str(path):
        return True

    if path.name.startswith("~$"):
        return True

    return False


def classify_candidate(
    score: float,
    section_count: int,
    word_count: int,
    negative_terms: Sequence[str],
) -> str:
    if negative_terms and score < 45:
        return "NON_MANUSCRIPT_OR_AUXILIARY"
    if section_count >= 5 and word_count >= 2500 and score >= 70:
        return "STRONG_MANUSCRIPT_CANDIDATE"
    if section_count >= 3 and word_count >= 1200 and score >= 40:
        return "PLAUSIBLE_MANUSCRIPT_CANDIDATE"
    if word_count >= 1000 and score >= 20:
        return "WEAK_MANUSCRIPT_CANDIDATE"
    return "NON_MANUSCRIPT_OR_AUXILIARY"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()
    if not project.exists():
        raise FileNotFoundError(f"Project root not found: {project}")

    outtables = project / "06_tables" / TAG
    outmetadata = project / "03_metadata" / TAG
    outresults = project / "05_results" / TAG

    for directory in (outtables, outmetadata, outresults):
        directory.mkdir(parents=True, exist_ok=True)

    docx_files = [
        path
        for path in project.rglob("*.docx")
        if not should_skip(path, project)
    ]

    log(f"DOCX files eligible for inspection: {len(docx_files)}")

    rows: List[Dict[str, object]] = []

    for path in sorted(docx_files):
        stat = path.stat()
        text = extract_docx_text(path)
        words = re.findall(r"\b[\w'-]+\b", text)
        headings = section_hits(text)
        file_score, positive, negative = filename_score(path.name)
        version_value = version_signal(path.name)

        section_score = len(headings) * 12
        word_score = min(len(words) / 500, 25)
        size_score = min(stat.st_size / (1024 * 1024), 10)
        recency_days = max(
            (
                datetime.now().timestamp() - stat.st_mtime
            ) / 86400,
            0,
        )
        recency_score = max(0, 12 - min(recency_days, 120) / 10)
        version_score = min(version_value / 100, 15)

        total_score = round(
            file_score
            + section_score
            + word_score
            + size_score
            + recency_score
            + version_score,
            2,
        )

        candidate_class = classify_candidate(
            total_score,
            len(headings),
            len(words),
            negative,
        )

        rows.append(
            {
                "path": str(path),
                "filename": path.name,
                "relative_path": str(path.relative_to(project)),
                "size_bytes": stat.st_size,
                "modified_time": datetime.fromtimestamp(
                    stat.st_mtime
                ).isoformat(timespec="seconds"),
                "word_count": len(words),
                "section_count": len(headings),
                "sections_found": "; ".join(headings),
                "positive_filename_terms": "; ".join(positive),
                "negative_filename_terms": "; ".join(negative),
                "version_signal": version_value,
                "candidate_score": total_score,
                "candidate_class": candidate_class,
                "contains_results_heading": "results" in headings,
                "contains_discussion_heading": "discussion" in headings,
                "contains_references_heading": "references" in headings,
            }
        )

    inventory = pd.DataFrame(rows)

    if inventory.empty:
        ranked = inventory.copy()
        decision = "NO_MANUSCRIPT_TARGET_FOUND_USER_PATH_REQUIRED"
        top_path = ""
        top_score = ""
        score_margin = ""
    else:
        ranked = inventory.sort_values(
            ["candidate_score", "modified_time"],
            ascending=[False, False],
        ).reset_index(drop=True)
        ranked.insert(0, "rank", range(1, len(ranked) + 1))

        plausible = ranked[
            ranked["candidate_class"].isin(
                [
                    "STRONG_MANUSCRIPT_CANDIDATE",
                    "PLAUSIBLE_MANUSCRIPT_CANDIDATE",
                ]
            )
        ].copy()

        if plausible.empty:
            decision = "NO_CONFIDENT_MANUSCRIPT_TARGET_USER_PATH_REQUIRED"
            top_path = str(ranked.iloc[0]["path"])
            top_score = float(ranked.iloc[0]["candidate_score"])
            score_margin = ""
        else:
            top = plausible.iloc[0]
            top_path = str(top["path"])
            top_score = float(top["candidate_score"])

            if len(plausible) == 1:
                score_margin = top_score
                decision = (
                    "PROVISIONAL_MANUSCRIPT_TARGET_IDENTIFIED_"
                    "REQUIRES_USER_CONFIRMATION"
                )
            else:
                second_score = float(
                    plausible.iloc[1]["candidate_score"]
                )
                score_margin = round(top_score - second_score, 2)

                if (
                    str(top["candidate_class"])
                    == "STRONG_MANUSCRIPT_CANDIDATE"
                    and score_margin >= 18
                ):
                    decision = (
                        "PROVISIONAL_MANUSCRIPT_TARGET_IDENTIFIED_"
                        "REQUIRES_USER_CONFIRMATION"
                    )
                else:
                    decision = (
                        "MULTIPLE_MANUSCRIPT_CANDIDATES_REQUIRE_USER_SELECTION"
                    )

    inventory_path = (
        outtables
        / "UTI_HostOmics_U27B3C1_manuscript_candidate_inventory.tsv"
    )
    ranked.to_csv(inventory_path, sep="\t", index=False)

    top_candidates = ranked.head(10).copy()
    top_candidates.to_csv(
        outtables
        / "UTI_HostOmics_U27B3C1_top_manuscript_candidates.tsv",
        sep="\t",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "phase": "U27B3C1",
                "decision": decision,
                "docx_files_inspected": len(docx_files),
                "strong_candidates": int(
                    (
                        ranked.get(
                            "candidate_class",
                            pd.Series(dtype=str),
                        )
                        == "STRONG_MANUSCRIPT_CANDIDATE"
                    ).sum()
                )
                if not ranked.empty
                else 0,
                "plausible_candidates": int(
                    (
                        ranked.get(
                            "candidate_class",
                            pd.Series(dtype=str),
                        )
                        == "PLAUSIBLE_MANUSCRIPT_CANDIDATE"
                    ).sum()
                )
                if not ranked.empty
                else 0,
                "provisional_target_path": top_path,
                "provisional_target_score": top_score,
                "score_margin_over_second_plausible_candidate": score_margin,
                "files_modified": False,
                "manuscript_modified": False,
                "next_phase": (
                    "User confirms the authoritative manuscript target, then "
                    "U27B3C2 constructs the Results section in frozen "
                    "Figure 1-8 order"
                ),
            }
        ]
    ).to_csv(
        outtables
        / "UTI_HostOmics_U27B3C1_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    target_record = {
        "version": VERSION,
        "decision": decision,
        "provisional_target_path": top_path,
        "provisional_target_score": top_score,
        "score_margin": score_margin,
        "docx_files_inspected": len(docx_files),
        "files_modified": False,
        "manuscript_modified": False,
    }
    (
        outmetadata
        / "UTI_HostOmics_U27B3C1_provisional_target_record.json"
    ).write_text(
        json.dumps(target_record, indent=2),
        encoding="utf-8",
    )

    report_path = (
        outresults
        / "UTI_HostOmics_U27B3C1_manuscript_target_resolution_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B3C1 - Manuscript target resolution\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Eligible DOCX files inspected: **{len(docx_files)}**.\n"
        )
        handle.write(
            f"- Provisional target: `{top_path or 'none'}`.\n"
        )
        handle.write(
            f"- Provisional score: **{top_score or 'not available'}**.\n"
        )
        handle.write(
            f"- Score margin: **{score_margin or 'not available'}**.\n\n"
        )

        handle.write("## Resolution rule\n\n")
        handle.write(
            "The authoritative manuscript is not edited automatically. "
            "Filename signals, manuscript-section coverage, word count, "
            "document size, version indicators and recency are combined only "
            "to rank candidates. The user must confirm the target path before "
            "U27B3C2 modifies or creates a manuscript derivative.\n\n"
        )

        handle.write("## Top candidates\n\n")
        if top_candidates.empty:
            handle.write("No eligible manuscript candidate was found.\n")
        else:
            for _, row in top_candidates.iterrows():
                handle.write(
                    f"- Rank {int(row['rank'])}: `{row['relative_path']}` "
                    f"(score={row['candidate_score']}, "
                    f"class={row['candidate_class']}, "
                    f"words={row['word_count']}, "
                    f"sections={row['sections_found'] or 'none'}).\n"
                )

    (
        outresults
        / "UTI_HostOmics_U27B3C1_run_manifest.json"
    ).write_text(
        json.dumps(target_record, indent=2),
        encoding="utf-8",
    )

    log(f"Decision: {decision}")
    log(f"Provisional target: {top_path or 'none'}")
    log(f"Inventory: {inventory_path}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B3C1] ERROR: {exc}", file=sys.stderr)
        raise
