#!/usr/bin/env python3
"""
Phase U26A.2 - resolve GSE280297 mouse identifiers and reconstruct a deduplicated design.

Non-destructive repair for the UTI HostOmics project. The script:
  1) inspects GSE280297 expression candidates and prefers a credible gene-symbol matrix,
  2) recognizes mouse Ensembl IDs (ENSMUSG...) rather than discarding them,
  3) maps ENSMUSG IDs to symbols when a local GTF/OrgDb mapping is available,
  4) writes one canonical gene-symbol expression matrix,
  5) reconstructs one metadata row per expression sample from local metadata evidence,
  6) recalculates U26A coverage for GSE280297,
  7) issues separate decisions for core U26B scoring and dam-level outcome modeling.

It does not modify the manuscript or existing figures.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

VERSION = "U26A2_v1.0_2026-07-14"
DATASET = "GSE280297"

MOUSE_ENSEMBL_RE = re.compile(r"^ENSMUSG\d+(?:\.\d+)?$", re.I)
HUMAN_ENSEMBL_RE = re.compile(r"^ENSG\d+(?:\.\d+)?$", re.I)
GSM_RE = re.compile(r"GSM\d+", re.I)
GENE_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{1,39}$")

EXCLUDE_FILE_RE = re.compile(
    r"(phaseu26|figure|plot|report|manifest|coverage|priority|contrast|blueprint|"
    r"manuscript|review|contact[_-]?sheet|module[_-]?score|delta)", re.I
)
EXPRESSION_HINT_RE = re.compile(
    r"(clean[_-]?gene[_-]?symbol[_-]?matrix|repaired[_-]?gene[_-]?symbol[_-]?matrix|"
    r"normalized[._-]?counts|gene[_-]?count|count[_-]?matrix|expression)", re.I
)
METADATA_HINT_RE = re.compile(
    r"(meta|sample|design|pheno|clinical|series[_-]?matrix|soft|annotation|coldata)", re.I
)

BANNED_TOKENS = {
    "GENE", "GENES", "SYMBOL", "GENE_SYMBOL", "NA", "N/A", "NULL", "NONE",
    "CONTROL", "PBS", "UTI89", "PRETERM", "TERM", "NONPREGNANT", "PREGNANT",
    "BLADDER", "PLACENTA", "UTERUS", "MOCK", "OUTCOME", "TREATMENT", "CONDITION",
}


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def detect_delimiter(path: Path) -> str:
    try:
        with open_text(path) as handle:
            lines = [handle.readline() for _ in range(5)]
        joined = "".join(lines)
    except Exception:
        return "\t"
    counts = {"\t": joined.count("\t"), ",": joined.count(","), ";": joined.count(";")}
    return max(counts, key=counts.get) if max(counts.values()) > 0 else "\t"


def load_u26a_module(path: Path):
    spec = importlib.util.spec_from_file_location("u26a_base", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import U26A script: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_tsv(path: Path, rows: List[Dict[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def normalize_id(value: object) -> str:
    text = str(value).strip().strip('"').strip("'")
    return re.sub(r"\.\d+$", "", text)


def canonical_symbol(value: object) -> str:
    token = normalize_id(value)
    if not token:
        return ""
    if MOUSE_ENSEMBL_RE.fullmatch(token) or HUMAN_ENSEMBL_RE.fullmatch(token):
        return ""
    if token.upper() in BANNED_TOKENS:
        return ""
    if token.isdigit() or not GENE_SYMBOL_RE.fullmatch(token):
        return ""
    if len(token) > 40:
        return ""
    return token.upper()


def read_first_column(path: Path, limit: int = 100000) -> Tuple[List[str], List[str], str]:
    delimiter = detect_delimiter(path)
    values: List[str] = []
    header: List[str] = []
    with open_text(path) as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        header = next(reader, [])
        for i, row in enumerate(reader):
            if i >= limit:
                break
            if row:
                values.append(str(row[0]).strip())
    return header, values, delimiter


def inspect_expression_candidate(path: Path) -> Dict[str, object]:
    try:
        header, values, delimiter = read_first_column(path)
    except Exception as exc:
        return {
            "path": str(path), "status": f"read_error:{type(exc).__name__}", "score": -9999,
            "n_rows_inspected": 0, "n_sample_columns": 0, "identifier_type": "unresolved",
            "n_unique_symbols": 0, "n_unique_mouse_ensembl": 0,
        }
    mouse_ens = {normalize_id(v).upper() for v in values if MOUSE_ENSEMBL_RE.fullmatch(str(v).strip())}
    symbols = {canonical_symbol(v) for v in values}
    symbols.discard("")
    n_samples = max(0, len(header) - 1)
    n = max(1, len(values))
    mouse_fraction = len(mouse_ens) / n
    symbol_fraction = len(symbols) / n
    if len(symbols) >= 10000 and symbol_fraction >= 0.25:
        id_type = "gene_symbol"
    elif len(mouse_ens) >= 10000 and mouse_fraction >= 0.25:
        id_type = "mouse_ensembl"
    else:
        id_type = "unresolved"
    name = path.name.lower()
    score = 0.0
    if "clean_gene_symbol_matrix" in name:
        score += 220
    elif "repaired_gene_symbol_matrix" in name:
        score += 210
    elif "normalized.counts" in name or "normalized_counts" in name:
        score += 180
    elif "gene_count" in name:
        score += 150
    if id_type == "gene_symbol":
        score += 100
    elif id_type == "mouse_ensembl":
        score += 50
    else:
        score -= 150
    if 50 <= n_samples <= 70:
        score += 80
    elif n_samples > 5:
        score += 20
    if EXCLUDE_FILE_RE.search(str(path)):
        score -= 500
    return {
        "path": str(path), "status": "ok", "score": round(score, 2),
        "delimiter": "TAB" if delimiter == "\t" else delimiter,
        "n_rows_inspected": len(values), "n_sample_columns": n_samples,
        "identifier_type": id_type, "n_unique_symbols": len(symbols),
        "n_unique_mouse_ensembl": len(mouse_ens),
        "first_column_header": header[0] if header else "",
    }


def discover_expression_candidates(dataset_root: Path) -> List[Path]:
    out: List[Path] = []
    for path in dataset_root.rglob("*"):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if not lower.endswith((".csv", ".csv.gz", ".tsv", ".tsv.gz", ".txt", ".txt.gz")):
            continue
        if EXCLUDE_FILE_RE.search(str(path)):
            continue
        if EXPRESSION_HINT_RE.search(lower):
            out.append(path)
    return sorted(set(out))


def parse_gtf_mapping(search_root: Path, wanted: Set[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not wanted:
        return mapping
    gtf_paths = [p for p in search_root.rglob("*") if p.is_file() and p.name.lower().endswith((".gtf", ".gtf.gz"))]
    for path in gtf_paths[:20]:
        try:
            with open_text(path) as handle:
                for line in handle:
                    if not line or line.startswith("#"):
                        continue
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 9:
                        continue
                    attrs = parts[8]
                    gid_match = re.search(r'gene_id "([^"]+)"', attrs)
                    gname_match = re.search(r'gene_name "([^"]+)"', attrs)
                    if not gid_match or not gname_match:
                        continue
                    gid = normalize_id(gid_match.group(1)).upper()
                    if gid in wanted:
                        symbol = canonical_symbol(gname_match.group(1))
                        if symbol:
                            mapping[gid] = symbol
                    if len(mapping) >= len(wanted):
                        return mapping
        except Exception:
            continue
    return mapping


def map_with_mouse_orgdb(ids: Set[str], workdir: Path) -> Dict[str, str]:
    if not ids or shutil.which("Rscript") is None:
        return {}
    infile = workdir / "_u26a2_ensmusg_ids.txt"
    outfile = workdir / "_u26a2_ensmusg_to_symbol.tsv"
    rfile = workdir / "_u26a2_map_mouse_ensembl.R"
    infile.write_text("\n".join(sorted(ids)) + "\n", encoding="utf-8")
    rfile.write_text(r'''
args <- commandArgs(trailingOnly=TRUE)
infile <- args[1]
outfile <- args[2]
if (!requireNamespace("AnnotationDbi", quietly=TRUE) || !requireNamespace("org.Mm.eg.db", quietly=TRUE)) quit(status=3)
ids <- unique(readLines(infile, warn=FALSE))
ids <- sub("\\.[0-9]+$", "", ids)
mp <- AnnotationDbi::mapIds(org.Mm.eg.db::org.Mm.eg.db, keys=ids, keytype="ENSEMBL", column="SYMBOL", multiVals="first")
out <- data.frame(ensembl=names(mp), symbol=as.character(mp), stringsAsFactors=FALSE)
out <- out[!is.na(out$symbol) & nzchar(out$symbol), , drop=FALSE]
write.table(out, file=outfile, sep="\t", row.names=FALSE, quote=FALSE)
''', encoding="utf-8")
    try:
        result = subprocess.run(["Rscript", str(rfile), str(infile), str(outfile)], capture_output=True, text=True, timeout=300)
        if result.returncode != 0 or not outfile.exists():
            return {}
        mapping: Dict[str, str] = {}
        with outfile.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                gid = normalize_id(row.get("ensembl", "")).upper()
                sym = canonical_symbol(row.get("symbol", ""))
                if gid and sym:
                    mapping[gid] = sym
        return mapping
    except Exception:
        return {}
    finally:
        for p in (infile, outfile, rfile):
            try:
                p.unlink()
            except Exception:
                pass


def build_canonical_matrix(source: Path, output: Path, project_root: Path, workdir: Path) -> Tuple[Dict[str, object], List[str], Set[str]]:
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:
        raise RuntimeError("pandas is required for U26A.2 canonical matrix construction") from exc

    delimiter = detect_delimiter(source)
    df = pd.read_csv(source, sep=delimiter, compression="infer", low_memory=False)
    if df.shape[1] < 2:
        raise RuntimeError(f"Selected matrix has fewer than two columns: {source}")
    id_col = df.columns[0]
    raw_ids = df[id_col].astype(str).map(normalize_id)
    mouse_ids = {x.upper() for x in raw_ids if MOUSE_ENSEMBL_RE.fullmatch(x)}
    direct_symbols = raw_ids.map(canonical_symbol)
    mapping: Dict[str, str] = {}
    mapping_method = "direct_gene_symbols"

    if direct_symbols.ne("").sum() < 10000 and len(mouse_ids) >= 10000:
        mapping = parse_gtf_mapping(project_root, mouse_ids)
        mapping_method = "local_gtf"
        if len(mapping) < max(1000, int(0.50 * len(mouse_ids))):
            orgdb_map = map_with_mouse_orgdb(mouse_ids.difference(mapping), workdir)
            mapping.update(orgdb_map)
            mapping_method = "local_gtf_plus_org.Mm.eg.db" if mapping else "org.Mm.eg.db"
        direct_symbols = raw_ids.map(lambda x: mapping.get(x.upper(), ""))

    value_df = df.drop(columns=[id_col]).copy()
    value_df.insert(0, "gene_symbol", direct_symbols.to_numpy())
    df = value_df[value_df["gene_symbol"].astype(str).ne("")].copy()
    value_cols = [c for c in df.columns if c != "gene_symbol"]
    for col in value_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    is_raw_count = bool(re.search(r"raw|gene[_-]?count", source.name, re.I) and not re.search(r"normalized", source.name, re.I))
    agg = "sum" if is_raw_count else "mean"
    grouped = df.groupby("gene_symbol", as_index=False)[value_cols].agg(agg)
    grouped = grouped.sort_values("gene_symbol")
    output.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_csv(output, sep="\t", index=False, compression="gzip")
    symbols = set(grouped["gene_symbol"].astype(str))
    sample_columns = [str(c) for c in value_cols]
    summary = {
        "selected_source": str(source), "canonical_matrix": str(output),
        "mapping_method": mapping_method, "n_input_rows": int(df.shape[0]),
        "n_canonical_gene_symbols": int(len(symbols)), "n_expression_samples": int(len(sample_columns)),
        "duplicate_collapse_rule": agg,
        "n_mouse_ensembl_ids_observed": int(len(mouse_ids)), "n_mouse_ensembl_ids_mapped": int(len(mapping)),
    }
    return summary, sample_columns, symbols


def sample_keys(value: object) -> Set[str]:
    text = str(value).strip()
    keys = {text, re.sub(r"[^A-Za-z0-9]+", "", text).upper()}
    for gsm in GSM_RE.findall(text):
        keys.add(gsm.upper())
    return {k for k in keys if k}


def infer_design_from_text(text: str) -> Dict[str, str]:
    low = text.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", low)
    tissue = ""
    if "placenta" in normalized or "placental" in normalized:
        tissue = "placenta"
    elif "bladder" in normalized:
        tissue = "bladder"
    elif "uterus" in normalized or "uterine" in normalized:
        tissue = "uterus"

    treatment = ""
    if "uti89" in normalized or re.search(r"\bupec\b", normalized):
        treatment = "UTI89"
        if "rfp" in normalized:
            treatment = "UTI89_RFP"
    elif re.search(r"\bpbs\b", normalized) or "mock" in normalized or "vehicle" in normalized:
        treatment = "PBS_or_mock"

    outcome = ""
    if "nonpreg" in normalized or "non preg" in normalized:
        outcome = "nonpregnant"
    elif "preterm" in normalized or "pre term" in normalized or "premature" in normalized:
        outcome = "preterm"
    elif re.search(r"\bterm\b", normalized) or "nonlabor" in normalized or "non labor" in normalized:
        outcome = "term_or_nonlaboring"

    pregnancy = ""
    if outcome == "nonpregnant":
        pregnancy = "nonpregnant"
    elif outcome in {"preterm", "term_or_nonlaboring"} or "pregnant" in normalized or "gestat" in normalized:
        pregnancy = "pregnant"

    dam_id = ""
    dam_patterns = [
        r"\bdam[ _-]*([A-Za-z0-9]+)", r"\bmaternal[ _-]*(?:id)?[ _-]*([A-Za-z0-9]+)",
        r"\bmother[ _-]*(?:id)?[ _-]*([A-Za-z0-9]+)", r"\bfemale[ _-]*(?:id)?[ _-]*([A-Za-z0-9]+)",
    ]
    for pat in dam_patterns:
        m = re.search(pat, normalized, flags=re.I)
        if m:
            dam_id = m.group(1)
            break
    return {"tissue": tissue, "treatment": treatment, "outcome": outcome, "pregnancy_status": pregnancy, "dam_id": dam_id}


def discover_metadata_files(dataset_root: Path, expression_source: Path) -> List[Path]:
    out: List[Path] = []
    for path in dataset_root.rglob("*"):
        if not path.is_file() or path == expression_source:
            continue
        lower = path.name.lower()
        if not lower.endswith((".csv", ".csv.gz", ".tsv", ".tsv.gz", ".txt", ".txt.gz")):
            continue
        if EXCLUDE_FILE_RE.search(str(path)):
            continue
        if METADATA_HINT_RE.search(lower):
            out.append(path)
    return sorted(set(out))


def collect_metadata_evidence(path: Path, sample_key_to_ids: Dict[str, Set[str]], max_rows: int = 20000) -> Dict[str, List[Tuple[str, str]]]:
    evidence: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    delimiter = detect_delimiter(path)
    try:
        with open_text(path) as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            header = next(reader, [])
            if not header:
                return evidence
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                padded = row + [""] * max(0, len(header) - len(row))
                row_text = " | ".join(f"{header[j]}={padded[j]}" for j in range(min(len(header), len(padded))))
                row_keys: Set[str] = set()
                for cell in padded:
                    row_keys.update(sample_keys(cell))
                matched_samples: Set[str] = set()
                for key in row_keys:
                    matched_samples.update(sample_key_to_ids.get(key, set()))
                for sample_id in matched_samples:
                    evidence[sample_id].append((str(path), row_text))
    except Exception:
        return evidence
    return evidence


def reconstruct_metadata(sample_columns: List[str], dataset_root: Path, expression_source: Path) -> Tuple[List[Dict[str, object]], Dict[str, float]]:
    key_to_samples: Dict[str, Set[str]] = defaultdict(set)
    for sample in sample_columns:
        for key in sample_keys(sample):
            key_to_samples[key].add(sample)

    all_evidence: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for sample in sample_columns:
        all_evidence[sample].append(("expression_column", sample))

    metadata_files = discover_metadata_files(dataset_root, expression_source)
    for path in metadata_files:
        ev = collect_metadata_evidence(path, key_to_samples)
        for sample, items in ev.items():
            all_evidence[sample].extend(items)

    rows: List[Dict[str, object]] = []
    for sample in sample_columns:
        items = all_evidence.get(sample, [])
        combined = " || ".join(text for _src, text in items)
        inferred = infer_design_from_text(combined)
        unresolved = [k for k in ("tissue", "treatment", "outcome") if not inferred[k]]
        confidence = "high" if not unresolved else ("moderate" if len(unresolved) == 1 else "low")
        rows.append({
            "sample_id": sample,
            "gsm_accession": next(iter(GSM_RE.findall(combined)), "").upper(),
            **inferred,
            "metadata_confidence": confidence,
            "unresolved_required_fields": ";".join(unresolved),
            "n_evidence_records": len(items),
            "evidence_sources": ";".join(sorted({src for src, _ in items})),
        })

    n = max(1, len(rows))
    metrics = {
        "metadata_match_fraction": sum(int(r["n_evidence_records"]) > 1 for r in rows) / n,
        "tissue_completion": sum(bool(r["tissue"]) for r in rows) / n,
        "treatment_completion": sum(bool(r["treatment"]) for r in rows) / n,
        "outcome_completion": sum(bool(r["outcome"]) for r in rows) / n,
        "pregnancy_completion": sum(bool(r["pregnancy_status"]) for r in rows) / n,
        "dam_id_completion_all": sum(bool(r["dam_id"]) for r in rows) / n,
    }
    pregnant_rows = [r for r in rows if r["pregnancy_status"] == "pregnant"]
    metrics["dam_id_completion_pregnant"] = (
        sum(bool(r["dam_id"]) for r in pregnant_rows) / len(pregnant_rows) if pregnant_rows else 0.0
    )
    return rows, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default="__UTI_HOSTOMICS_PROJECT_ROOT__")
    parser.add_argument("--dataset-root", default="02_data_raw/GSE280297")
    parser.add_argument("--base-script", default="10_scripts/phaseU26A_expanded_endocrine_metabolic_immune_feasibility_audit.py")
    parser.add_argument("--output-tag", default="phaseU26A2_GSE280297_identifier_design_resolution")
    args = parser.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    dataset_root = (root / args.dataset_root).resolve()
    base_script = (root / args.base_script).resolve()
    if not dataset_root.exists():
        eprint(f"ERROR: GSE280297 directory not found: {dataset_root}")
        return 2
    if not base_script.exists():
        eprint(f"ERROR: U26A base script not found: {base_script}")
        return 2

    metadata_dir = root / "03_metadata" / args.output_tag
    results_dir = root / "05_results" / args.output_tag
    tables_dir = root / "06_tables" / args.output_tag
    logs_dir = root / "08_logs" / args.output_tag
    processed_dir = root / "04_data_processed" / args.output_tag
    for d in (metadata_dir, results_dir, tables_dir, logs_dir, processed_dir):
        d.mkdir(parents=True, exist_ok=True)

    candidates = discover_expression_candidates(dataset_root)
    inspections = [inspect_expression_candidate(p) for p in candidates]
    inspections.sort(key=lambda r: float(r.get("score", -9999)), reverse=True)
    write_tsv(tables_dir / "UTI_HostOmics_U26A2_GSE280297_expression_candidate_audit.tsv", inspections, [
        "path", "status", "score", "delimiter", "first_column_header", "n_rows_inspected",
        "n_sample_columns", "identifier_type", "n_unique_symbols", "n_unique_mouse_ensembl",
    ])
    viable = [r for r in inspections if r.get("identifier_type") in {"gene_symbol", "mouse_ensembl"} and int(r.get("n_sample_columns", 0)) >= 5]
    if not viable:
        eprint("ERROR: no viable GSE280297 expression matrix was found")
        return 3
    selected = Path(str(viable[0]["path"]))

    canonical = processed_dir / "GSE280297_U26A2_canonical_gene_symbol_expression.tsv.gz"
    matrix_summary, sample_columns, symbols = build_canonical_matrix(selected, canonical, root, metadata_dir)
    matrix_qc_rows = [{**matrix_summary,
        "gene_universe_plausible": 10000 <= len(symbols) <= 50000,
        "sample_count_plausible": 50 <= len(sample_columns) <= 70,
    }]
    write_tsv(tables_dir / "UTI_HostOmics_U26A2_GSE280297_canonical_matrix_qc.tsv", matrix_qc_rows, [
        "selected_source", "canonical_matrix", "mapping_method", "n_input_rows", "n_canonical_gene_symbols",
        "n_expression_samples", "duplicate_collapse_rule", "n_mouse_ensembl_ids_observed",
        "n_mouse_ensembl_ids_mapped", "gene_universe_plausible", "sample_count_plausible",
    ])

    gene_universe_file = metadata_dir / "GSE280297_U26A2_resolved_gene_universe.txt"
    gene_universe_file.write_text("\n".join(sorted(symbols)) + "\n", encoding="utf-8")

    base = load_u26a_module(base_script)
    coverage_rows: List[Dict[str, object]] = []
    for record in base.submodule_records():
        genes = set(record["genes"])
        detected = sorted(genes.intersection(symbols))
        missing = sorted(genes.difference(symbols))
        coverage_rows.append({
            "dataset": DATASET, "axis": record["axis"], "submodule_id": record["submodule_id"],
            "display_label": record["display_label"], "n_module_genes": len(genes), "n_detected": len(detected),
            "coverage_fraction": round(len(detected) / len(genes), 4) if genes else "",
            "coverage_class": base.classify_coverage(len(genes), len(detected)),
            "detected_genes": ";".join(detected), "missing_genes": ";".join(missing),
            "interpretation_scope": "resolved gene-presence feasibility; differential activity remains to be tested in U26B",
        })
    write_tsv(tables_dir / "UTI_HostOmics_U26A2_GSE280297_submodule_coverage.tsv", coverage_rows, [
        "dataset", "axis", "submodule_id", "display_label", "n_module_genes", "n_detected",
        "coverage_fraction", "coverage_class", "detected_genes", "missing_genes", "interpretation_scope",
    ])

    metadata_rows, metadata_metrics = reconstruct_metadata(sample_columns, dataset_root, selected)
    write_tsv(metadata_dir / "GSE280297_U26A2_deduplicated_sample_design.tsv", metadata_rows, [
        "sample_id", "gsm_accession", "tissue", "treatment", "outcome", "pregnancy_status", "dam_id",
        "metadata_confidence", "unresolved_required_fields", "n_evidence_records", "evidence_sources",
    ])

    expression_ready = (
        10000 <= len(symbols) <= 50000 and 50 <= len(sample_columns) <= 70
    )
    core_metadata_ready = (
        metadata_metrics["tissue_completion"] >= 0.80 and
        metadata_metrics["treatment_completion"] >= 0.70 and
        metadata_metrics["outcome_completion"] >= 0.60
    )
    dam_ready = metadata_metrics["dam_id_completion_pregnant"] >= 0.70

    if expression_ready and core_metadata_ready and dam_ready:
        overall = "READY_FOR_U26B"
    elif expression_ready and core_metadata_ready:
        overall = "READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED"
    else:
        overall = "TARGETED_METADATA_REVIEW_REQUIRED"

    decision_row = {
        "phase": "U26A.2", "overall_decision": overall,
        "expression_identifier_resolution": "resolved" if expression_ready else "unresolved",
        "core_tissue_stratified_scoring": "ready" if expression_ready and core_metadata_ready else "not_ready",
        "dam_level_pregnancy_outcome_model": "ready" if dam_ready else "deferred",
        "n_canonical_gene_symbols": len(symbols), "n_expression_samples": len(sample_columns),
        **{k: round(v, 4) for k, v in metadata_metrics.items()},
        "critical_rule": "start tissue-stratified pathway scoring only with one metadata row per expression sample; do not infer dam-level independence from tissues",
    }
    write_tsv(tables_dir / "UTI_HostOmics_U26A2_phase_decision.tsv", [decision_row], list(decision_row.keys()))

    report = results_dir / "UTI_HostOmics_U26A2_GSE280297_resolution_report.md"
    with report.open("w", encoding="utf-8") as handle:
        handle.write("# Phase U26A.2 - GSE280297 identifier and design resolution\n\n")
        handle.write(f"- Version: `{VERSION}`\n")
        handle.write(f"- Overall decision: **{overall}**\n")
        handle.write("- Manuscript and existing figures were not modified.\n\n")
        handle.write("## Identifier diagnosis\n\n")
        handle.write("The U26A.1 zero-symbol result arose because mouse Ensembl identifiers (`ENSMUSG...`) were removed by a human-Ensembl-specific sanitizer. U26A.2 recognizes mouse Ensembl identifiers and preferentially selects a local gene-symbol matrix when one is available.\n\n")
        handle.write("## Canonical expression matrix\n\n")
        for key, value in matrix_summary.items():
            handle.write(f"- **{key}**: `{value}`\n")
        handle.write("\n## Metadata completion\n\n")
        for key, value in metadata_metrics.items():
            handle.write(f"- **{key}**: {value:.3f}\n")
        handle.write("\n## Entry interpretation\n\n")
        if overall == "READY_FOR_U26B":
            handle.write("GSE280297 can enter tissue-stratified U26B scoring and dam-level pregnancy-outcome modeling.\n")
        elif overall == "READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED":
            handle.write("GSE280297 can enter tissue-stratified U26B scoring. Dam-level AUROC/logistic analyses remain deferred until dam identifiers are completed.\n")
        else:
            handle.write("The expression matrix is assessed separately from metadata. Inspect unresolved sample-design fields before initiating tissue-stratified U26B models.\n")

    manifest = {
        "version": VERSION, "project_root": str(root), "dataset": DATASET, "decision": overall,
        "outputs": {
            "candidate_audit": str(tables_dir / "UTI_HostOmics_U26A2_GSE280297_expression_candidate_audit.tsv"),
            "canonical_matrix": str(canonical), "matrix_qc": str(tables_dir / "UTI_HostOmics_U26A2_GSE280297_canonical_matrix_qc.tsv"),
            "gene_universe": str(gene_universe_file), "coverage": str(tables_dir / "UTI_HostOmics_U26A2_GSE280297_submodule_coverage.tsv"),
            "sample_design": str(metadata_dir / "GSE280297_U26A2_deduplicated_sample_design.tsv"),
            "decision": str(tables_dir / "UTI_HostOmics_U26A2_phase_decision.tsv"), "report": str(report),
        },
    }
    (results_dir / "UTI_HostOmics_U26A2_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[U26A.2] Selected source: {selected}")
    print(f"[U26A.2] Canonical genes: {len(symbols)}")
    print(f"[U26A.2] Expression samples: {len(sample_columns)}")
    print(f"[U26A.2] Decision: {overall}")
    print(f"[U26A.2] Decision table: {tables_dir / 'UTI_HostOmics_U26A2_phase_decision.tsv'}")
    print(f"[U26A.2] Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
