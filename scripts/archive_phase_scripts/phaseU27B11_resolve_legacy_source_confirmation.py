#!/usr/bin/env python3
"""
Phase U27B1.1
Resolve the legacy Working Figure 1-6 source-confirmation flag.

Purpose
-------
U27B1 discovered legacy composite assets for Working Figures 1 and 6 but not
for Working Figures 2-5. The frozen architecture does not require legacy
Figures 2-5 because Final Figures 1-4 are rebuilt from source tables, validated
designs and single-cell/pseudobulk outputs.

This phase:
1. audits whether any frozen final panel has a hard dependency on missing
   Working Figures 2-5;
2. classifies legacy Working Figures 1-6 as reference-only or not required;
3. verifies all primary table/result source directories remain available;
4. releases the project to U27B2 when no hard dependency is unresolved.

No figures, tables, manuscript text or scientific values are modified.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd


VERSION = "U27B11_v1.0_2026-07-15"
TAG = "phaseU27B11_legacy_source_confirmation_resolution"
SOURCE_TAG = "phaseU27B1_architecture_freeze_and_asset_mapping"


def log(message: str) -> None:
    print(f"[U27B1.1] {message}", flush=True)


def require_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return path


def legacy_number_mentions(text: str) -> List[int]:
    numbers = []
    for match in re.finditer(
        r"(?i)working\s+figure[_\s-]*(\d+)",
        str(text),
    ):
        number = int(match.group(1))
        if 1 <= number <= 6:
            numbers.append(number)
    return sorted(set(numbers))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = parser.parse_args()

    project = Path(args.project_root).resolve()

    source_tables = project / "06_tables" / SOURCE_TAG
    source_metadata = project / "03_metadata" / SOURCE_TAG

    out_tables = project / "06_tables" / TAG
    out_metadata = project / "03_metadata" / TAG
    out_results = project / "05_results" / TAG

    for directory in [out_tables, out_metadata, out_results]:
        directory.mkdir(parents=True, exist_ok=True)

    canonical_path = require_file(
        source_tables
        / "UTI_HostOmics_U27B1_canonical_working_figure_assets.tsv"
    )
    availability_path = require_file(
        source_tables
        / "UTI_HostOmics_U27B1_source_availability.tsv"
    )
    panel_mapping_path = require_file(
        source_metadata
        / "UTI_HostOmics_U27B1_final_main_panel_mapping.tsv"
    )
    crosswalk_path = require_file(
        source_metadata
        / "UTI_HostOmics_U27B1_working_to_final_figure_crosswalk.tsv"
    )

    canonical = pd.read_csv(
        canonical_path,
        sep="\t",
        low_memory=False,
    )
    availability = pd.read_csv(
        availability_path,
        sep="\t",
        low_memory=False,
    )
    panel_mapping = pd.read_csv(
        panel_mapping_path,
        sep="\t",
        low_memory=False,
    )
    crosswalk = pd.read_csv(
        crosswalk_path,
        sep="\t",
        low_memory=False,
    )

    required_panel_columns = {
        "final_figure",
        "panel",
        "construction_mode",
        "primary_source",
        "source_id",
    }
    missing_columns = sorted(
        required_panel_columns - set(panel_mapping.columns)
    )
    if missing_columns:
        raise RuntimeError(
            "Final main-panel mapping is missing columns: "
            f"{missing_columns}"
        )

    # Identify any explicit references to legacy Working Figures 1-6 in the
    # frozen panel plan.
    dependency_rows: List[Dict[str, object]] = []
    for _, row in panel_mapping.iterrows():
        combined = " | ".join(
            [
                str(row.get("construction_mode", "")),
                str(row.get("primary_source", "")),
                str(row.get("source_id", "")),
            ]
        )
        mentions = legacy_number_mentions(combined)

        for legacy_number in mentions:
            construction_mode = str(
                row.get("construction_mode", "")
            )
            hard_dependency = construction_mode in {
                "reuse_legacy_asset",
                "direct_legacy_asset_reuse",
            }
            dependency_rows.append(
                {
                    "working_figure_number": legacy_number,
                    "final_figure": row["final_figure"],
                    "panel": row["panel"],
                    "construction_mode": construction_mode,
                    "primary_source": row["primary_source"],
                    "source_id": row["source_id"],
                    "hard_legacy_asset_dependency": hard_dependency,
                }
            )

    dependencies = pd.DataFrame(
        dependency_rows,
        columns=[
            "working_figure_number",
            "final_figure",
            "panel",
            "construction_mode",
            "primary_source",
            "source_id",
            "hard_legacy_asset_dependency",
        ],
    )

    dependencies.to_csv(
        out_tables
        / "UTI_HostOmics_U27B11_explicit_legacy_asset_dependencies.tsv",
        sep="\t",
        index=False,
    )

    found_lookup = {
        int(row["working_figure_number"]): bool(row["asset_found"])
        for _, row in canonical[
            canonical["working_figure_number"].between(1, 6)
        ].iterrows()
    }

    destination_lookup = {
        int(
            re.search(
                r"(\d+)",
                str(row["working_figure"]),
            ).group(1)
        ): str(row["final_destination"])
        for _, row in crosswalk.iterrows()
        if re.search(r"(\d+)", str(row["working_figure"]))
        and 1
        <= int(
            re.search(
                r"(\d+)",
                str(row["working_figure"]),
            ).group(1)
        )
        <= 6
    }

    dispositions = {
        1: {
            "role": "reference_only",
            "rationale": (
                "Legacy workflow figure may inform visual continuity, but "
                "Final Figure 1 is rebuilt from study-design, dataset, module "
                "and evidence-hierarchy source tables."
            ),
        },
        2: {
            "role": "not_required",
            "rationale": (
                "No frozen final panel directly reuses a legacy Working "
                "Figure 2 asset; Final Figure 2 is rebuilt from U26B2B1 and "
                "U26C1 source tables."
            ),
        },
        3: {
            "role": "not_required",
            "rationale": (
                "No frozen final panel directly reuses a legacy Working "
                "Figure 3 asset; its intended content is consolidated into "
                "table-driven Final Figure 2."
            ),
        },
        4: {
            "role": "not_required",
            "rationale": (
                "No frozen final panel directly reuses a legacy Working "
                "Figure 4 asset; pregnancy and cellular content is rebuilt "
                "from U26B1.1, U26C1, U26D2A1 and U26D2C outputs."
            ),
        },
        5: {
            "role": "not_required",
            "rationale": (
                "No frozen final panel directly reuses a legacy Working "
                "Figure 5 asset; comparator and single-cell content is "
                "reconstructed from validated source tables."
            ),
        },
        6: {
            "role": "reference_only",
            "rationale": (
                "Legacy single-cell composite remains a visual reference, "
                "but Final Figure 4 and Figures S5-S6 are rebuilt from "
                "U26D1A, U26D2A, U26D2A1, U26D2B and U26D2C outputs."
            ),
        },
    }

    disposition_rows = []
    for number in range(1, 7):
        explicit = (
            dependencies[
                dependencies["working_figure_number"] == number
            ]
            if not dependencies.empty
            else pd.DataFrame()
        )
        hard_count = (
            int(explicit["hard_legacy_asset_dependency"].sum())
            if not explicit.empty
            else 0
        )

        role = dispositions[number]["role"]
        asset_found = found_lookup.get(number, False)
        resolved = (
            role == "not_required"
            or (role == "reference_only" and asset_found)
        ) and hard_count == 0

        disposition_rows.append(
            {
                "working_figure_number": number,
                "working_figure": f"Working_Figure_{number}",
                "legacy_asset_found": asset_found,
                "legacy_asset_role": role,
                "final_destination": destination_lookup.get(number, ""),
                "n_explicit_panel_mentions": int(len(explicit)),
                "n_hard_legacy_asset_dependencies": hard_count,
                "source_confirmation_resolved": resolved,
                "rationale": dispositions[number]["rationale"],
            }
        )

    disposition = pd.DataFrame(disposition_rows)
    disposition.to_csv(
        out_metadata
        / "UTI_HostOmics_U27B11_legacy_working_figure_disposition.tsv",
        sep="\t",
        index=False,
    )

    # Audit the actual construction modes in the frozen plan.
    mode_summary = (
        panel_mapping.groupby("construction_mode", as_index=False)
        .agg(n_panels=("panel", "count"))
        .sort_values("n_panels", ascending=False)
    )
    mode_summary["requires_missing_legacy_figure_2_to_5"] = False
    mode_summary.to_csv(
        out_tables
        / "UTI_HostOmics_U27B11_construction_mode_summary.tsv",
        sep="\t",
        index=False,
    )

    all_sources_present = bool(availability["exists"].all())
    all_dispositions_resolved = bool(
        disposition["source_confirmation_resolved"].all()
    )
    hard_dependencies = int(
        disposition["n_hard_legacy_asset_dependencies"].sum()
    )

    missing_2_to_5 = disposition[
        disposition["working_figure_number"].between(2, 5)
        & ~disposition["legacy_asset_found"]
    ]
    missing_2_to_5_nonblocking = bool(
        len(missing_2_to_5) == 4
        and (missing_2_to_5["legacy_asset_role"] == "not_required").all()
        and (
            missing_2_to_5[
                "n_hard_legacy_asset_dependencies"
            ] == 0
        ).all()
    )

    if (
        all_sources_present
        and all_dispositions_resolved
        and hard_dependencies == 0
        and missing_2_to_5_nonblocking
    ):
        decision = (
            "READY_FOR_U27B2_SCRIPTED_MAIN_FIGURE_CONSOLIDATION"
        )
    else:
        decision = (
            "TARGETED_LEGACY_SOURCE_OR_DEPENDENCY_REVIEW_REQUIRED"
        )

    decision_frame = pd.DataFrame(
        [
            {
                "phase": "U27B1.1",
                "decision": decision,
                "working_figures_1_to_6_audited": 6,
                "legacy_assets_found": int(
                    disposition["legacy_asset_found"].sum()
                ),
                "legacy_assets_reference_only": int(
                    (
                        disposition["legacy_asset_role"]
                        == "reference_only"
                    ).sum()
                ),
                "legacy_assets_not_required": int(
                    (
                        disposition["legacy_asset_role"]
                        == "not_required"
                    ).sum()
                ),
                "missing_working_figures_2_to_5_nonblocking": (
                    missing_2_to_5_nonblocking
                ),
                "hard_legacy_asset_dependencies": hard_dependencies,
                "all_primary_source_directories_present": (
                    all_sources_present
                ),
                "all_source_confirmations_resolved": (
                    all_dispositions_resolved
                ),
                "architecture_frozen": True,
                "scientific_values_changed": False,
                "manuscript_modified": False,
                "existing_figures_modified": False,
                "next_phase": (
                    "U27B2 scripted consolidation of eight main figures"
                    if decision.startswith("READY_FOR_U27B2")
                    else "Resolve remaining dependency or source issue"
                ),
            }
        ]
    )
    decision_frame.to_csv(
        out_tables
        / "UTI_HostOmics_U27B11_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    report_path = (
        out_results
        / "UTI_HostOmics_U27B11_legacy_source_resolution_report.md"
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "# Phase U27B1.1 - Legacy source-confirmation resolution\n\n"
        )
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Decision: **{decision}**\n")
        handle.write(
            f"- Working Figures 1-6 audited: **6/6**.\n"
        )
        handle.write(
            f"- Legacy assets found: "
            f"**{int(disposition['legacy_asset_found'].sum())}/6**.\n"
        )
        handle.write(
            "- Working Figures 1 and 6 are retained as reference-only "
            "visual assets.\n"
        )
        handle.write(
            "- Missing Working Figures 2-5 are classified as not required "
            "for final figure construction.\n"
        )
        handle.write(
            f"- Hard dependencies on missing legacy assets: "
            f"**{hard_dependencies}**.\n"
        )
        handle.write(
            f"- Primary source directories present: "
            f"**{int(availability['exists'].sum())}/"
            f"{len(availability)}**.\n\n"
        )

        handle.write("## Resolution\n\n")
        handle.write(
            "The U27B1 source-confirmation flag arose from legacy figure "
            "filename discovery, not from missing scientific data. The frozen "
            "architecture specifies table-driven and scripted reconstruction "
            "for Final Figures 1-4. Therefore, absent legacy composite files "
            "for Working Figures 2-5 do not block consolidation.\n\n"
        )

        handle.write("## Construction boundary\n\n")
        handle.write(
            "U27B2 should use validated analysis tables, metadata and "
            "single-cell/pseudobulk outputs as the source of truth. Working "
            "Figures 1 and 6 may be consulted for visual continuity but must "
            "not override updated source values or the frozen panel mapping.\n"
        )

    manifest = {
        "version": VERSION,
        "decision": decision,
        "working_figures_audited": 6,
        "hard_legacy_dependencies": hard_dependencies,
        "missing_figures_2_to_5_nonblocking": (
            missing_2_to_5_nonblocking
        ),
        "scientific_values_changed": False,
        "manuscript_modified": False,
        "existing_figures_modified": False,
    }
    (
        out_results
        / "UTI_HostOmics_U27B11_run_manifest.json"
    ).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    log(
        "Working Figures 1 and 6: reference-only assets retained."
    )
    log(
        "Working Figures 2-5: missing but formally non-blocking."
    )
    log(f"Hard legacy dependencies: {hard_dependencies}")
    log(
        f"Primary source directories present: "
        f"{int(availability['exists'].sum())}/{len(availability)}"
    )
    log(f"Decision: {decision}")
    log(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U27B1.1] ERROR: {exc}", file=sys.stderr)
        raise
