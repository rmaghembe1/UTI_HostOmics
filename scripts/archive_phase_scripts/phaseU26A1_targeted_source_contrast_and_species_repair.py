#!/usr/bin/env python3
"""
Phase U26A.1 - targeted source, contrast, and species repair.

This script repairs the first-pass U26A feasibility audit before expression-level
scoring. It does not modify manuscripts or existing figures. It:
  1) selects one high-confidence expression source per dataset,
  2) rebuilds gene-universe and submodule-coverage tables from those sources,
  3) replaces permissive auto-contrasts with conservative study-design contrasts,
  4) records species/orthology requirements for U26B,
  5) distinguishes gene-coverage feasibility from expression-level testability.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

VERSION = "U26A1_v1.0_2026-07-14"

DATASET_INFO = {
    "GSE186800": {
        "label": "Gardnerella-triggered recurrent UTI bladder model",
        "species": "Mus musculus",
        "preferred": [r"raw_genecpm_matrix", r"genecpm", r"normalized.*count", r"count.*matrix"],
        "expected_n_min": 10000,
        "expected_n_max": 50000,
        "species_action": "map mouse genes to one-to-one human orthologs for cross-dataset integration; retain mouse symbols for within-dataset scoring",
    },
    "GSE280297": {
        "label": "maternal UTI and preterm-birth model",
        "species": "Mus musculus",
        "preferred": [r"normalized\.counts", r"gene_count", r"normalized.*count", r"count.*matrix"],
        "expected_n_min": 10000,
        "expected_n_max": 50000,
        "species_action": "map mouse genes to one-to-one human orthologs for cross-dataset integration; retain mouse symbols for tissue-stratified within-dataset scoring",
    },
    "GSE112098": {
        "label": "human urinary early-sepsis inflammatory comparator",
        "species": "Homo sapiens",
        "preferred": [r"independentvalidationsetmatrix", r"series_matrix", r"normalized.*matrix", r"expression.*matrix"],
        "expected_n_min": 5000,
        "expected_n_max": 60000,
        "species_action": "human symbols can be used directly after probe-to-gene collapse and duplicate-symbol handling",
    },
    "GSE252321": {
        "label": "UPEC-responsive bladder single-cell validation",
        "species": "Mus musculus",
        "preferred": [r"\.h5ad$", r"annotated.*\.rds$", r"seurat.*\.rds$", r"sce.*\.rds$", r"matrix"],
        "expected_n_min": 5000,
        "expected_n_max": 50000,
        "species_action": "retain mouse symbols for within-cell-type scoring; use one-to-one human orthologs only for integrated cross-species summaries",
    },
}

EXCLUDE_RE = re.compile(
    r"(phaseu26a|module[_-]?score|delta|figure|plot|contact[_-]?sheet|report|"
    r"manifest|contrast|priority|research[_-]?question|coverage[_-]?by|"
    r"summary|blueprint|gmt|library|review|manuscript)", re.I
)
META_RE = re.compile(r"(meta|metadata|pheno|clinical|sample[_-]?annotation|coldata|design)", re.I)
ACCESSION_RE = re.compile(r"^(GSM|GSE|SRR|ERR|ERX|SRX|SAMN|SRS|PRJNA)\d+$", re.I)


def load_u26a_module(path: Path):
    spec = importlib.util.spec_from_file_location("u26a_base", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import U26A module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_tsv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: List[Dict[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def source_score(dataset: str, row: Dict[str, str]) -> float:
    path = Path(row.get("path", ""))
    name = path.name.lower()
    full = str(path).lower()
    if not path.exists():
        return -1e9
    if EXCLUDE_RE.search(full):
        return -1e8
    score = 0.0
    for rank, pattern in enumerate(DATASET_INFO[dataset]["preferred"]):
        if re.search(pattern, name, flags=re.I):
            score += 120.0 - 15.0 * rank
            break
    if dataset == "GSE252321" and path.suffix.lower() in {".h5ad", ".rds", ".rda", ".rdata"}:
        score += 80.0
    if META_RE.search(name):
        score -= 80.0
    try:
        score += min(30.0, max(0.0, float(row.get("candidate_score", "0"))))
    except Exception:
        pass
    try:
        n = int(float(row.get("genes_extracted", "0")))
    except Exception:
        n = 0
    if 5000 <= n <= 60000:
        score += 30.0
    elif n > 60000:
        score -= 60.0
    elif n >= 500:
        score += 5.0
    else:
        score -= 20.0
    if row.get("status", "").startswith("ok"):
        score += 10.0
    return score


def sanitize_gene_universe(genes: Set[str]) -> Set[str]:
    out: Set[str] = set()
    banned = {
        "CONTROL", "UPEC", "PBS", "GARDNERELLA", "GARD", "SEPSIS", "SEPTIC",
        "PRETERM", "TERM", "NONPREGNANT", "PREGNANT", "MOCK", "BLADDER",
        "PLACENTA", "UTERUS", "OUTCOME", "TREATMENT", "CONDITION", "GROUP",
    }
    for g in genes:
        token = str(g).strip().upper()
        if not token or token in banned or ACCESSION_RE.fullmatch(token):
            continue
        if re.fullmatch(r"[A-Z]*\d{4,}[A-Z0-9]*", token) and not token.startswith("ENSG"):
            continue
        if len(token) > 25:
            continue
        out.add(token)
    return out


def choose_sources(inventory: List[Dict[str, str]]) -> Tuple[List[Dict[str, object]], Dict[str, Path]]:
    selected: Dict[str, Path] = {}
    rows_out: List[Dict[str, object]] = []
    for dataset in DATASET_INFO:
        candidates = [r for r in inventory if r.get("dataset") == dataset]
        ranked = sorted(((source_score(dataset, r), r) for r in candidates), key=lambda x: x[0], reverse=True)
        best_score, best = ranked[0] if ranked else (-1e9, {})
        best_path = Path(best.get("path", "")) if best else Path()
        status = "selected" if best and best_score > -1e7 and best_path.exists() else "unresolved"
        if status == "selected":
            selected[dataset] = best_path
        rows_out.append({
            "dataset": dataset,
            "dataset_label": DATASET_INFO[dataset]["label"],
            "species": DATASET_INFO[dataset]["species"],
            "selected_expression_source": str(best_path) if status == "selected" else "",
            "selection_score": round(best_score, 2) if math.isfinite(best_score) else "",
            "previous_genes_extracted": best.get("genes_extracted", "") if best else "",
            "selection_status": status,
            "next_best_candidates": " | ".join(
                f"{Path(r.get('path','')).name}:{round(s,1)}" for s, r in ranked[1:4]
            ),
        })
    return rows_out, selected


def corrected_contrasts() -> List[Dict[str, object]]:
    return [
        {
            "dataset": "GSE186800", "analysis_unit": "whole bladder / biological mouse",
            "contrast_or_design": "Gardnerella versus PBS within first exposure",
            "known_group_sizes": "Gard-1 n=5; PBS-1 n=5", "support_class": "moderate_binary",
            "recommended_statistics": "DESeq2/limma-style model; module effect size and FDR; avoid odds ratios",
            "required_u26b_action": "model exposure number and treatment; retain mouse as biological replicate",
        },
        {
            "dataset": "GSE186800", "analysis_unit": "whole bladder / biological mouse",
            "contrast_or_design": "Gardnerella versus PBS within second exposure and treatment-by-exposure interaction",
            "known_group_sizes": "Gard-2 n=5; PBS-2 n=5", "support_class": "moderate_factorial",
            "recommended_statistics": "factorial model with treatment, exposure number, and interaction; module effect size and FDR",
            "required_u26b_action": "use the four original groups, not collapsed duplicate labels",
        },
        {
            "dataset": "GSE280297", "analysis_unit": "individual tissue sample nested within dam",
            "contrast_or_design": "UTI-associated preterm versus UTI-associated term/non-laboring, stratified by bladder, placenta, and uterus",
            "known_group_sizes": "60 GEO samples total: bladder 18; placenta 28; uterus 14; outcome counts require deduplicated sample metadata",
            "support_class": "high_value_requires_metadata_reconstruction",
            "recommended_statistics": "tissue-stratified models; dam-aware or paired/mixed modeling where tissues share a dam; effect sizes and FDR first",
            "required_u26b_action": "reconstruct one row per GEO sample and one dam identifier; do not use duplicated 117/238-row summaries",
        },
        {
            "dataset": "GSE280297", "analysis_unit": "individual dam / outcome",
            "contrast_or_design": "pregnancy-risk endocrine-metabolic inflammation index versus preterm-birth outcome",
            "known_group_sizes": "binary outcome counts to be confirmed after deduplication",
            "support_class": "conditional_binary_outcome",
            "recommended_statistics": "dam-level AUROC and permutation; logistic regression/odds ratios only if effective n and separation are adequate",
            "required_u26b_action": "aggregate tissue scores to dam level using a prespecified rule before outcome modeling",
        },
        {
            "dataset": "GSE112098", "analysis_unit": "human urine sample",
            "contrast_or_design": "early sepsis versus preoperative vascular-surgery comparator",
            "known_group_sizes": "sepsis n=41; vascular-surgery comparator n=32",
            "support_class": "strong_binary_urinary_inflammation_comparator",
            "recommended_statistics": "effect size, FDR, AUROC and permutation; treat as systemic urinary inflammation comparator, not UTI-specific evidence",
            "required_u26b_action": "collapse array probes to genes and adjust for available clinical covariates where possible",
        },
        {
            "dataset": "GSE252321", "analysis_unit": "biological mouse/sample pseudobulk within cell type",
            "contrast_or_design": "UPEC versus control within immune cell populations",
            "known_group_sizes": "two control and two UPEC sequencing samples indicated by deposited matrices; verify in local object",
            "support_class": "small_n_single_cell_validation",
            "recommended_statistics": "sample-level pseudobulk effect sizes; exploratory mixed models; do not treat cells or module rows as independent n",
            "required_u26b_action": "confirm sample_id, condition, and cell_type columns; use biological samples as replicates",
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default="__UTI_HOSTOMICS_PROJECT_ROOT__")
    parser.add_argument("--base-script", default="10_scripts/phaseU26A_expanded_endocrine_metabolic_immune_feasibility_audit.py")
    parser.add_argument("--base-tag", default="phaseU26A_expanded_endocrine_metabolic_immune_feasibility")
    parser.add_argument("--output-tag", default="phaseU26A1_targeted_source_contrast_species_repair")
    args = parser.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    base_script = (root / args.base_script).resolve()
    if not base_script.exists():
        print(f"ERROR: base U26A script not found: {base_script}", file=sys.stderr)
        return 2
    base = load_u26a_module(base_script)

    base_tables = root / "06_tables" / args.base_tag
    inventory_path = base_tables / "UTI_HostOmics_U26A_dataset_source_inventory.tsv"
    if not inventory_path.exists():
        print(f"ERROR: source inventory not found: {inventory_path}", file=sys.stderr)
        return 2

    metadata_dir = root / "03_metadata" / args.output_tag
    results_dir = root / "05_results" / args.output_tag
    tables_dir = root / "06_tables" / args.output_tag
    logs_dir = root / "08_logs" / args.output_tag
    for d in (metadata_dir, results_dir, tables_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)

    inventory = read_tsv(inventory_path)
    selection_rows, selected = choose_sources(inventory)
    write_tsv(tables_dir / "UTI_HostOmics_U26A1_selected_expression_sources.tsv", selection_rows, [
        "dataset", "dataset_label", "species", "selected_expression_source", "selection_score",
        "previous_genes_extracted", "selection_status", "next_best_candidates",
    ])

    r_helper = root / "08_logs" / args.base_tag / "U26A_extract_R_object_features_and_metadata.R"
    records = base.submodule_records()
    module_union = {g for r in records for g in r["genes"]}

    universes: Dict[str, Set[str]] = {}
    universe_rows: List[Dict[str, object]] = []
    source_qc_rows: List[Dict[str, object]] = []

    for dataset, info in DATASET_INFO.items():
        path = selected.get(dataset)
        raw: Set[str] = set()
        extract_status = "unresolved"
        if path is not None:
            raw, _meta, extract_status = base.extract_file(path, r_helper)
        clean = sanitize_gene_universe(raw)
        universes[dataset] = clean
        detected_module_genes = sorted(clean.intersection(module_union))
        n = len(clean)
        plausible = info["expected_n_min"] <= n <= info["expected_n_max"]
        status = "resolved_plausible" if plausible else ("resolved_requires_review" if n else "unresolved")
        out_gene = metadata_dir / f"{dataset}_U26A1_selected_source_gene_universe.txt"
        out_gene.write_text("\n".join(sorted(clean)) + ("\n" if clean else ""), encoding="utf-8")
        universe_rows.append({
            "dataset": dataset, "dataset_label": info["label"], "species": info["species"],
            "selected_expression_source": str(path) if path else "", "n_raw_tokens": len(raw),
            "n_sanitized_gene_symbols": n, "n_curated_module_genes_detected": len(detected_module_genes),
            "gene_universe_status": status, "gene_universe_file": str(out_gene),
            "species_harmonization_requirement": info["species_action"],
        })
        source_qc_rows.append({
            "dataset": dataset, "selected_expression_source": str(path) if path else "",
            "extraction_status": extract_status, "n_sanitized_gene_symbols": n,
            "expected_range": f"{info['expected_n_min']}-{info['expected_n_max']}",
            "plausible_gene_universe": plausible,
            "qc_action": "none" if plausible else "inspect selected source and gene identifier column before U26B",
        })

    write_tsv(tables_dir / "UTI_HostOmics_U26A1_gene_universe_summary.tsv", universe_rows, [
        "dataset", "dataset_label", "species", "selected_expression_source", "n_raw_tokens",
        "n_sanitized_gene_symbols", "n_curated_module_genes_detected", "gene_universe_status",
        "gene_universe_file", "species_harmonization_requirement",
    ])
    write_tsv(tables_dir / "UTI_HostOmics_U26A1_selected_source_qc.tsv", source_qc_rows, [
        "dataset", "selected_expression_source", "extraction_status", "n_sanitized_gene_symbols",
        "expected_range", "plausible_gene_universe", "qc_action",
    ])

    coverage_rows: List[Dict[str, object]] = []
    for r in records:
        genes = set(r["genes"])
        for dataset, universe in universes.items():
            detected = sorted(genes.intersection(universe))
            missing = sorted(genes.difference(universe))
            coverage_rows.append({
                "dataset": dataset, "species": DATASET_INFO[dataset]["species"], "axis": r["axis"],
                "submodule_id": r["submodule_id"], "display_label": r["display_label"],
                "n_module_genes": len(genes), "n_detected": len(detected),
                "coverage_fraction": round(len(detected) / len(genes), 4) if genes else "",
                "coverage_class": base.classify_coverage(len(genes), len(detected)) if universe else "unresolved",
                "detected_genes": ";".join(detected), "missing_genes": ";".join(missing),
                "interpretation_scope": "gene-coverage feasibility only; expression direction and statistical signal remain untested",
            })
    write_tsv(tables_dir / "UTI_HostOmics_U26A1_submodule_coverage_by_selected_source.tsv", coverage_rows, [
        "dataset", "species", "axis", "submodule_id", "display_label", "n_module_genes", "n_detected",
        "coverage_fraction", "coverage_class", "detected_genes", "missing_genes", "interpretation_scope",
    ])

    contrast_rows = corrected_contrasts()
    write_tsv(tables_dir / "UTI_HostOmics_U26A1_corrected_contrast_map.tsv", contrast_rows, [
        "dataset", "analysis_unit", "contrast_or_design", "known_group_sizes", "support_class",
        "recommended_statistics", "required_u26b_action",
    ])

    species_rows = []
    for dataset, info in DATASET_INFO.items():
        species_rows.append({
            "dataset": dataset, "species": info["species"],
            "within_dataset_scoring": "use native species gene symbols after identifier cleanup",
            "cross_dataset_integration": info["species_action"],
            "directionality_rule": "integrate effect directions and standardized module effects; do not pool raw expression across species/tissues",
        })
    write_tsv(tables_dir / "UTI_HostOmics_U26A1_species_harmonization_plan.tsv", species_rows, [
        "dataset", "species", "within_dataset_scoring", "cross_dataset_integration", "directionality_rule",
    ])

    all_sources_resolved = all(r["selection_status"] == "selected" for r in selection_rows)
    all_universes_plausible = all(r["gene_universe_status"] == "resolved_plausible" for r in universe_rows)
    decision = "READY_FOR_U26B" if all_sources_resolved and all_universes_plausible else "TARGETED_INPUT_REVIEW_REQUIRED"
    decision_rows = [{
        "phase": "U26A.1", "decision": decision,
        "all_expression_sources_resolved": all_sources_resolved,
        "all_gene_universes_plausible": all_universes_plausible,
        "u26b_scope": "expression-level submodule scoring with tissue-stratified bulk models and sample-level single-cell pseudobulk",
        "critical_rule": "coverage feasibility is not evidence of differential pathway activity",
    }]
    write_tsv(tables_dir / "UTI_HostOmics_U26A1_phase_decision.tsv", decision_rows, [
        "phase", "decision", "all_expression_sources_resolved", "all_gene_universes_plausible",
        "u26b_scope", "critical_rule",
    ])

    report = results_dir / "UTI_HostOmics_U26A1_targeted_repair_report.md"
    with report.open("w", encoding="utf-8") as h:
        h.write("# Phase U26A.1 targeted source, contrast, and species repair\n\n")
        h.write(f"- Version: `{VERSION}`\n")
        h.write(f"- Decision: **{decision}**\n")
        h.write("- Manuscript and existing figures were not modified.\n\n")
        h.write("## Why the repair was required\n\n")
        h.write("The first-pass audit demonstrated broad gene-set coverage, but its discovery layer unioned multiple accession-matched files and its metadata scanner accepted duplicated labels and numeric summary columns. The first-pass figure priorities therefore represented provisional gene-presence feasibility, not expression-level biological evidence.\n\n")
        h.write("## Selected expression sources\n\n")
        for r in selection_rows:
            h.write(f"- **{r['dataset']}**: `{r['selected_expression_source'] or 'UNRESOLVED'}` ({r['selection_status']}).\n")
        h.write("\n## Gene-universe QC\n\n")
        for r in universe_rows:
            h.write(f"- **{r['dataset']}**: {r['n_sanitized_gene_symbols']} symbols; `{r['gene_universe_status']}`.\n")
        h.write("\n## Corrected analytical design\n\n")
        h.write("- GSE186800 is a four-group, 5-mouse-per-group factorial bladder experiment.\n")
        h.write("- GSE280297 must be modeled by tissue and dam/outcome; duplicated summary rows cannot define sample size.\n")
        h.write("- GSE112098 is a human urinary sepsis comparator and should not be described as UTI-specific evidence.\n")
        h.write("- GSE252321 requires biological-sample pseudobulk; cells or module-result rows are not independent replicates.\n")
        h.write("- Mouse datasets require explicit ortholog-aware integration with the human urine dataset.\n\n")
        h.write("## U26B entry rule\n\n")
        h.write("Proceed only when the phase decision is `READY_FOR_U26B`. U26B should score expression within each dataset, estimate effect sizes and FDRs using the corrected analysis units, and integrate standardized effects rather than raw expression.\n")

    manifest = {
        "version": VERSION,
        "project_root": str(root),
        "decision": decision,
        "outputs": {
            "selected_sources": str(tables_dir / "UTI_HostOmics_U26A1_selected_expression_sources.tsv"),
            "gene_universe_summary": str(tables_dir / "UTI_HostOmics_U26A1_gene_universe_summary.tsv"),
            "coverage": str(tables_dir / "UTI_HostOmics_U26A1_submodule_coverage_by_selected_source.tsv"),
            "contrasts": str(tables_dir / "UTI_HostOmics_U26A1_corrected_contrast_map.tsv"),
            "species_plan": str(tables_dir / "UTI_HostOmics_U26A1_species_harmonization_plan.tsv"),
            "report": str(report),
        },
    }
    (results_dir / "UTI_HostOmics_U26A1_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[U26A.1] Decision: {decision}")
    print(f"[U26A.1] Selected sources: {tables_dir / 'UTI_HostOmics_U26A1_selected_expression_sources.tsv'}")
    print(f"[U26A.1] Gene-universe QC: {tables_dir / 'UTI_HostOmics_U26A1_gene_universe_summary.tsv'}")
    print(f"[U26A.1] Corrected contrasts: {tables_dir / 'UTI_HostOmics_U26A1_corrected_contrast_map.tsv'}")
    print(f"[U26A.1] Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
