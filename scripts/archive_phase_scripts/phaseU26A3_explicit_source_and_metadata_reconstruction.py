#!/usr/bin/env python3
"""
Phase U26A.3
Resolve GSE280297 expression identifiers and reconstruct sample design from the
local GEO series matrix without modifying the manuscript or current figures.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

VERSION = "U26A3_v1.0_2026-07-14"
PHASE_TAG = "phaseU26A3_GSE280297_explicit_source_metadata_reconstruction"

SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{1,39}$")
MOUSE_ENSEMBL_RE = re.compile(r"^ENSMUSG\d+(?:\.\d+)?$", re.I)

def log(msg: str) -> None:
    print(f"[U26A.3] {msg}", flush=True)

def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "rt", encoding="utf-8", errors="replace")

def sniff_sep(path: Path) -> str:
    with open_text(path) as fh:
        first = fh.readline()
    return "\t" if first.count("\t") >= first.count(",") else ","

def read_small(path: Path, nrows: int = 500) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep=sniff_sep(path),
        compression="infer",
        nrows=nrows,
        dtype=str,
        low_memory=False,
    )

def normalize_symbol(x: object) -> str:
    s = "" if x is None else str(x).strip().strip('"').strip("'")
    if MOUSE_ENSEMBL_RE.match(s):
        s = re.sub(r"\.\d+$", "", s)
    return s

def symbol_like_fraction(values: Sequence[str]) -> float:
    vals = [
        normalize_symbol(v)
        for v in values
        if str(v).strip() and str(v).lower() != "nan"
    ]
    if not vals:
        return 0.0
    ok = 0
    for s in vals:
        if SYMBOL_RE.match(s) and not MOUSE_ENSEMBL_RE.match(s) and not s.isdigit():
            ok += 1
    return ok / len(vals)

def discover_candidates(rawdir: Path) -> List[Path]:
    patterns = [
        "GSE280297_gene_count_clean_gene_symbol_matrix.tsv.gz",
        "GSE280297_gene_count_repaired_gene_symbol_matrix.tsv.gz",
        "*GSE280297*clean*gene*symbol*matrix*",
        "*GSE280297*repaired*gene*symbol*matrix*",
        "GSE280297_Normalized.counts.csv.gz",
        "GSE280297_gene_count.csv.gz",
        "*GSE280297*count*.csv*",
        "*GSE280297*matrix*.tsv*",
    ]
    seen = set()
    out = []
    for pat in patterns:
        for p in rawdir.rglob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    return out

def explicit_priority(path: Path) -> int:
    n = path.name.lower()
    if "clean_gene_symbol_matrix" in n:
        return 1000
    if "repaired_gene_symbol_matrix" in n:
        return 900
    if "normalized.counts" in n:
        return 500
    if "gene_count.csv" in n:
        return 400
    return 100

def audit_candidate(path: Path) -> Dict[str, object]:
    row = {
        "path": str(path),
        "status": "unreadable",
        "priority": explicit_priority(path),
        "delimiter": "",
        "n_columns": 0,
        "n_rows_inspected": 0,
        "identifier_column": "",
        "identifier_type": "unresolved",
        "symbol_like_fraction": 0.0,
        "n_sample_columns_estimated": 0,
        "selection_score": -9999.0,
    }
    try:
        df = read_small(path, 500)
        row["status"] = "ok"
        row["delimiter"] = sniff_sep(path)
        row["n_columns"] = df.shape[1]
        row["n_rows_inspected"] = df.shape[0]

        best_col = None
        best_frac = -1.0
        best_type = "unresolved"
        for col in list(df.columns[:4]):
            vals = df[col].astype(str).tolist()
            frac = symbol_like_fraction(vals)
            ens = (
                np.mean(
                    [
                        bool(MOUSE_ENSEMBL_RE.match(normalize_symbol(v)))
                        for v in vals
                    ]
                )
                if vals
                else 0.0
            )
            if frac > best_frac:
                best_col = col
                best_frac = frac
                best_type = "gene_symbol" if frac >= 0.50 else "unresolved"
            if ens >= 0.50 and ens > best_frac:
                best_col = col
                best_frac = float(ens)
                best_type = "mouse_ensembl"

        row["identifier_column"] = "" if best_col is None else str(best_col)
        row["identifier_type"] = best_type
        row["symbol_like_fraction"] = round(
            float(best_frac if best_frac >= 0 else 0.0), 4
        )

        n_numeric = 0
        for col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce")
            if vals.notna().mean() >= 0.80:
                n_numeric += 1
        row["n_sample_columns_estimated"] = int(n_numeric)

        bonus = 300 if best_type == "gene_symbol" else 80 if best_type == "mouse_ensembl" else 0
        row["selection_score"] = float(
            row["priority"]
            + bonus
            + min(n_numeric, 60)
            + 100 * row["symbol_like_fraction"]
        )
    except Exception as exc:
        row["error"] = repr(exc)
    return row

def choose_candidate(audit: pd.DataFrame) -> pd.Series:
    ok = audit[audit["status"] == "ok"].copy()
    if ok.empty:
        raise RuntimeError("No readable GSE280297 expression candidates were found.")
    symbol_ok = ok[
        (ok["identifier_type"] == "gene_symbol")
        & (ok["symbol_like_fraction"] >= 0.50)
    ]
    if not symbol_ok.empty:
        return symbol_ok.sort_values(
            ["priority", "selection_score"], ascending=False
        ).iloc[0]
    return ok.sort_values(
        ["selection_score", "priority"], ascending=False
    ).iloc[0]

def load_canonical_symbol_matrix(
    path: Path, identifier_column: str
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    df = pd.read_csv(
        path,
        sep=sniff_sep(path),
        compression="infer",
        low_memory=False,
    )
    if identifier_column not in df.columns:
        identifier_column = df.columns[0]

    probe = df.head(1000)
    best_col = identifier_column
    best_frac = symbol_like_fraction(probe[best_col].astype(str).tolist())
    for col in list(df.columns[:4]):
        frac = symbol_like_fraction(probe[col].astype(str).tolist())
        if frac > best_frac:
            best_col = col
            best_frac = frac
    identifier_column = best_col

    symbols = df[identifier_column].map(normalize_symbol)
    keep = symbols.map(
        lambda s: bool(SYMBOL_RE.match(s))
        and not bool(MOUSE_ENSEMBL_RE.match(s))
        and not s.isdigit()
    )
    df = df.loc[keep].copy()
    df.insert(0, "gene_symbol", symbols.loc[keep].values)

    numeric_cols = []
    for col in df.columns:
        if col in {identifier_column, "gene_symbol"}:
            continue
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().mean() >= 0.80:
            df[col] = converted
            numeric_cols.append(col)

    bup_cols = [
        c for c in numeric_cols
        if re.fullmatch(r"[BUP]\d+", str(c), flags=re.I)
    ]
    sample_cols = bup_cols if len(bup_cols) >= 50 else numeric_cols
    if not sample_cols:
        raise RuntimeError("No numeric expression sample columns could be identified.")

    mat = df[["gene_symbol"] + sample_cols].copy()
    mat = (
        mat.groupby("gene_symbol", as_index=False)[sample_cols]
        .mean(numeric_only=True)
        .sort_values("gene_symbol")
        .reset_index(drop=True)
    )

    qc = {
        "selected_source": str(path),
        "identifier_column": str(identifier_column),
        "mapping_method": "existing_cleaned_gene_symbol_matrix",
        "n_input_rows": int(len(symbols)),
        "n_rows_retained_before_duplicate_collapse": int(keep.sum()),
        "n_canonical_gene_symbols": int(mat["gene_symbol"].nunique()),
        "n_expression_samples": int(len(sample_cols)),
        "duplicate_collapse_rule": "mean",
        "symbol_like_fraction_selected_column": round(float(best_frac), 4),
        "gene_universe_plausible": bool(mat["gene_symbol"].nunique() >= 10000),
        "sample_count_plausible": bool(55 <= len(sample_cols) <= 65),
    }
    return mat, qc

def parse_series_matrix(series_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    records: Dict[str, Dict[str, object]] = {}
    geo_ids: List[str] = []
    raw_rows: List[Dict[str, object]] = []

    with open_text(series_path) as fh:
        for line in fh:
            if not line.startswith("!Sample_"):
                continue
            row = next(
                csv.reader(
                    [line.rstrip("\n")],
                    delimiter="\t",
                    quotechar='"',
                )
            )
            key = row[0].replace("!Sample_", "", 1)
            vals = row[1:]
            if key == "geo_accession":
                geo_ids = [v.strip() for v in vals]
                for gsm in geo_ids:
                    records.setdefault(
                        gsm,
                        {"gsm_accession": gsm, "characteristics": []},
                    )
                continue
            if not geo_ids or len(vals) != len(geo_ids):
                continue
            for gsm, val in zip(geo_ids, vals):
                val = val.strip()
                records.setdefault(
                    gsm,
                    {"gsm_accession": gsm, "characteristics": []},
                )
                if key == "characteristics_ch1":
                    records[gsm]["characteristics"].append(val)
                else:
                    prior = records[gsm].get(key)
                    if prior in (None, ""):
                        records[gsm][key] = val
                    else:
                        records[gsm][key] = f"{prior} | {val}"
                raw_rows.append(
                    {
                        "gsm_accession": gsm,
                        "field": key,
                        "value": val,
                    }
                )

    per = []
    for gsm, rec in records.items():
        chars = rec.pop("characteristics", [])
        rec["characteristics_ch1"] = " | ".join(chars)
        per.append(rec)
    return pd.DataFrame(per), pd.DataFrame(raw_rows)

def sample_text(row: pd.Series) -> str:
    fields = [
        "title",
        "source_name_ch1",
        "characteristics_ch1",
        "description",
        "organism_ch1",
    ]
    return " | ".join(
        str(row.get(f, ""))
        for f in fields
        if str(row.get(f, "")).lower() != "nan"
    )

def infer_tissue(sample_id: str, text: str) -> str:
    t = text.lower()
    if "bladder" in t:
        return "bladder"
    if "placenta" in t or "placental" in t:
        return "placenta"
    if "uterus" in t or "uterine" in t:
        return "uterus"
    m = re.match(r"^([BUP])\d+$", sample_id, flags=re.I)
    if not m:
        return ""
    return {
        "B": "bladder",
        "U": "uterus",
        "P": "placenta",
    }.get(m.group(1).upper(), "")

def infer_treatment(text: str) -> str:
    t = text.lower()
    if re.search(r"\buti[-_ ]?89\b|\buropathogenic\b|\bupec\b", t):
        return "UTI89"
    if re.search(r"\bpbs\b|\bmock\b|\bvehicle\b|\bcontrol\b", t):
        return "PBS_or_control"
    return ""

def infer_outcome(text: str) -> str:
    t = text.lower()
    if re.search(r"\bnon[-_ ]?pregnant\b", t):
        return "nonpregnant"
    if re.search(r"\bpreterm\b|\bpremature\b", t):
        return "preterm"
    if re.search(r"\bterm\b|\bnon[-_ ]?labor", t):
        return "term_or_nonlaboring"
    return ""

def infer_pregnancy(outcome: str, text: str) -> str:
    t = text.lower()
    if outcome == "nonpregnant" or re.search(r"\bnon[-_ ]?pregnant\b", t):
        return "nonpregnant"
    if outcome in {"preterm", "term_or_nonlaboring"} or "pregnan" in t:
        return "pregnant"
    return ""

def infer_dam_id(text: str) -> str:
    patterns = [
        r"\b(?:dam|mouse|animal|mother|maternal)[ _:#-]*([A-Za-z0-9.-]+)\b",
        r"\b(?:dam_id|mouse_id|animal_id)[:= ]+([A-Za-z0-9.-]+)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            val = m.group(1)
            if val.lower() not in {
                "bladder",
                "uterus",
                "placenta",
                "pregnant",
                "uti89",
                "pbs",
            }:
                return val
    return ""

def match_expression_samples(
    sample_cols: Sequence[str], per_sample: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    for sid in sample_cols:
        sid_s = str(sid)
        candidates = []
        for _, r in per_sample.iterrows():
            txt = sample_text(r)
            title = str(r.get("title", ""))
            score = 0
            if re.search(
                rf"(?<![A-Za-z0-9]){re.escape(sid_s)}(?![A-Za-z0-9])",
                title,
                flags=re.I,
            ):
                score += 100
            if re.search(
                rf"(?<![A-Za-z0-9]){re.escape(sid_s)}(?![A-Za-z0-9])",
                txt,
                flags=re.I,
            ):
                score += 30
            if score > 0:
                candidates.append((score, r))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            r = candidates[0][1]
            gsm = str(r.get("gsm_accession", ""))
            txt = sample_text(r)
            n_evidence = len(candidates)
            confidence = (
                "high"
                if candidates[0][0] >= 100
                and (
                    len(candidates) == 1
                    or candidates[0][0] > candidates[1][0]
                )
                else "medium"
            )
        else:
            gsm = ""
            txt = ""
            n_evidence = 0
            confidence = "prefix_only"

        tissue = infer_tissue(sid_s, txt)
        treatment = infer_treatment(txt)
        outcome = infer_outcome(txt)
        pregnancy = infer_pregnancy(outcome, txt)
        dam_id = infer_dam_id(txt)

        unresolved = []
        for key, val in [
            ("tissue", tissue),
            ("treatment", treatment),
            ("outcome", outcome),
            ("pregnancy_status", pregnancy),
        ]:
            if not val:
                unresolved.append(key)

        rows.append(
            {
                "sample_id": sid_s,
                "gsm_accession": gsm,
                "tissue": tissue,
                "treatment": treatment,
                "outcome": outcome,
                "pregnancy_status": pregnancy,
                "dam_id": dam_id,
                "metadata_confidence": confidence,
                "unresolved_required_fields": ";".join(unresolved),
                "n_evidence_records": n_evidence,
                "per_sample_evidence_text": txt,
            }
        )
    return pd.DataFrame(rows)

def load_submodule_library(project: Path) -> Optional[pd.DataFrame]:
    p = (
        project
        / "03_metadata/phaseU26A_expanded_endocrine_metabolic_immune_feasibility"
        / "UTI_HostOmics_U26A_expanded_submodule_library.tsv"
    )
    if p.exists():
        return pd.read_csv(p, sep="\t", dtype=str)
    return None

def find_gene_column(lib: pd.DataFrame) -> str:
    for c in ["genes", "gene_symbols", "members", "gene_list", "symbols"]:
        if c in lib.columns:
            return c
    for c in lib.columns:
        if "gene" in c.lower():
            return c
    raise RuntimeError(
        "Could not identify the gene-list column in the U26A library."
    )

def recalc_coverage(
    lib: Optional[pd.DataFrame], genes: Iterable[str]
) -> pd.DataFrame:
    if lib is None:
        return pd.DataFrame()
    gene_col = find_gene_column(lib)
    universe = {str(g).upper() for g in genes}
    rows = []
    for _, r in lib.iterrows():
        raw = str(r[gene_col])
        members = [
            x.strip()
            for x in re.split(r"[;,| ]+", raw)
            if x.strip() and x.strip().lower() != "nan"
        ]
        detected = [g for g in members if g.upper() in universe]
        frac = len(detected) / len(members) if members else math.nan
        rows.append(
            {
                "axis": r.get("axis", ""),
                "submodule_id": r.get(
                    "submodule_id", r.get("module_id", "")
                ),
                "display_label": r.get(
                    "display_label", r.get("label", "")
                ),
                "n_library_genes": len(members),
                "n_detected_genes": len(detected),
                "coverage_fraction": (
                    round(frac, 4) if members else ""
                ),
                "coverage_class": (
                    "adequate"
                    if members and len(detected) >= 5 and frac >= 0.50
                    else "partial"
                    if members and len(detected) >= 3 and frac >= 0.25
                    else "weak"
                ),
                "detected_genes": ";".join(detected),
            }
        )
    return pd.DataFrame(rows)

def completion(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(
        series.fillna("").astype(str).str.strip().ne("").mean()
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-root",
        default="__UTI_HOSTOMICS_PROJECT_ROOT__",
    )
    args = ap.parse_args()

    project = Path(args.project_root).resolve()
    rawdir = project / "02_data_raw/GSE280297"
    out_meta = project / f"03_metadata/{PHASE_TAG}"
    out_proc = project / f"04_data_processed/{PHASE_TAG}"
    out_res = project / f"05_results/{PHASE_TAG}"
    out_tab = project / f"06_tables/{PHASE_TAG}"
    for d in [out_meta, out_proc, out_res, out_tab]:
        d.mkdir(parents=True, exist_ok=True)

    candidates = discover_candidates(rawdir)
    if not candidates:
        raise FileNotFoundError(
            f"No GSE280297 expression candidates found under {rawdir}"
        )

    audit = pd.DataFrame([audit_candidate(p) for p in candidates])
    audit = audit.sort_values(
        ["selection_score", "priority"], ascending=False
    )
    audit.to_csv(
        out_tab
        / "UTI_HostOmics_U26A3_GSE280297_expression_candidate_audit.tsv",
        sep="\t",
        index=False,
    )

    selected = choose_candidate(audit)
    selected_path = Path(str(selected["path"]))
    log(f"Selected source: {selected_path}")

    if selected["identifier_type"] != "gene_symbol":
        decision = "TARGETED_IDENTIFIER_MAPPING_REQUIRED"
        pd.DataFrame(
            [
                {
                    "phase": "U26A.3",
                    "overall_decision": decision,
                    "selected_source": str(selected_path),
                    "critical_note": (
                        "No plausible local gene-symbol matrix was selected. "
                        "Inspect the candidate audit and use the cleaned or "
                        "repaired symbol matrix before U26B."
                    ),
                }
            ]
        ).to_csv(
            out_tab / "UTI_HostOmics_U26A3_phase_decision.tsv",
            sep="\t",
            index=False,
        )
        log(f"Decision: {decision}")
        return 0

    mat, qc = load_canonical_symbol_matrix(
        selected_path, str(selected["identifier_column"])
    )
    canonical_path = (
        out_proc
        / "GSE280297_U26A3_canonical_gene_symbol_expression.tsv.gz"
    )
    mat.to_csv(
        canonical_path,
        sep="\t",
        index=False,
        compression="gzip",
    )
    qc["canonical_matrix"] = str(canonical_path)
    pd.DataFrame([qc]).to_csv(
        out_tab
        / "UTI_HostOmics_U26A3_GSE280297_canonical_matrix_qc.tsv",
        sep="\t",
        index=False,
    )

    sample_cols = [c for c in mat.columns if c != "gene_symbol"]
    log(f"Canonical genes: {qc['n_canonical_gene_symbols']}")
    log(f"Expression samples: {qc['n_expression_samples']}")

    series_candidates = list(
        rawdir.rglob("GSE280297_series_matrix.txt.gz")
    ) + list(rawdir.rglob("*series_matrix*.txt*"))
    series_candidates = list(dict.fromkeys(series_candidates))
    if not series_candidates:
        raise FileNotFoundError(
            "Local GSE280297 series matrix was not found."
        )
    series_path = series_candidates[0]

    per_sample, raw_meta = parse_series_matrix(series_path)
    raw_meta.to_csv(
        out_meta
        / "GSE280297_U26A3_raw_per_sample_metadata_records.tsv",
        sep="\t",
        index=False,
    )
    per_sample.to_csv(
        out_meta
        / "GSE280297_U26A3_GEO_per_sample_metadata_wide.tsv",
        sep="\t",
        index=False,
    )

    design = match_expression_samples(sample_cols, per_sample)
    design.to_csv(
        out_meta
        / "GSE280297_U26A3_deduplicated_sample_design.tsv",
        sep="\t",
        index=False,
    )

    tissue_c = completion(design["tissue"])
    treatment_c = completion(design["treatment"])
    outcome_c = completion(design["outcome"])
    pregnancy_c = completion(design["pregnancy_status"])
    dam_all_c = completion(design["dam_id"])
    preg = design[design["pregnancy_status"] == "pregnant"]
    dam_preg_c = completion(preg["dam_id"]) if len(preg) else 0.0
    gsm_c = completion(design["gsm_accession"])

    coverage = recalc_coverage(
        load_submodule_library(project),
        mat["gene_symbol"],
    )
    if not coverage.empty:
        coverage.to_csv(
            out_tab
            / "UTI_HostOmics_U26A3_GSE280297_submodule_coverage.tsv",
            sep="\t",
            index=False,
        )

    expr_ready = bool(
        qc["gene_universe_plausible"]
        and qc["sample_count_plausible"]
    )
    core_design_ready = (
        tissue_c >= 0.95
        and treatment_c >= 0.90
        and outcome_c >= 0.90
    )
    dam_ready = dam_preg_c >= 0.90

    if expr_ready and core_design_ready and dam_ready:
        decision = "READY_FOR_U26B"
        core = "ready"
        dam_model = "ready"
    elif expr_ready and core_design_ready:
        decision = "READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED"
        core = "ready"
        dam_model = "deferred"
    elif expr_ready:
        decision = "TARGETED_METADATA_REVIEW_REQUIRED"
        core = "not_ready"
        dam_model = "deferred"
    else:
        decision = "TARGETED_IDENTIFIER_MAPPING_REQUIRED"
        core = "not_ready"
        dam_model = "deferred"

    pd.DataFrame(
        [
            {
                "phase": "U26A.3",
                "overall_decision": decision,
                "expression_identifier_resolution": (
                    "resolved" if expr_ready else "unresolved"
                ),
                "core_tissue_stratified_scoring": core,
                "dam_level_pregnancy_outcome_model": dam_model,
                "n_canonical_gene_symbols": qc[
                    "n_canonical_gene_symbols"
                ],
                "n_expression_samples": qc[
                    "n_expression_samples"
                ],
                "gsm_match_fraction": round(gsm_c, 4),
                "tissue_completion": round(tissue_c, 4),
                "treatment_completion": round(treatment_c, 4),
                "outcome_completion": round(outcome_c, 4),
                "pregnancy_completion": round(pregnancy_c, 4),
                "dam_id_completion_all": round(dam_all_c, 4),
                "dam_id_completion_pregnant": round(dam_preg_c, 4),
                "critical_rule": (
                    "B/U/P prefixes encode tissue only; biological "
                    "independence must be defined by GEO sample and dam "
                    "metadata, never by tissue rows."
                ),
            }
        ]
    ).to_csv(
        out_tab / "UTI_HostOmics_U26A3_phase_decision.tsv",
        sep="\t",
        index=False,
    )

    manifest = {
        "version": VERSION,
        "project_root": str(project),
        "selected_expression_source": str(selected_path),
        "canonical_matrix": str(canonical_path),
        "series_matrix": str(series_path),
        "decision": decision,
    }
    (
        out_res / "UTI_HostOmics_U26A3_run_manifest.json"
    ).write_text(json.dumps(manifest, indent=2))

    report = f"""# Phase U26A.3 - GSE280297 explicit-source and metadata reconstruction

- Version: `{VERSION}`
- Overall decision: **{decision}**
- Manuscript and existing figures were not modified.

## Expression resolution

- Selected source: `{selected_path}`
- Mapping method: existing cleaned/repaired gene-symbol matrix
- Canonical genes: **{qc['n_canonical_gene_symbols']}**
- Expression samples: **{qc['n_expression_samples']}**
- Canonical matrix: `{canonical_path}`

## Sample-design reconstruction

- GEO sample match fraction: **{gsm_c:.3f}**
- Tissue completion: **{tissue_c:.3f}**
- Treatment completion: **{treatment_c:.3f}**
- Outcome completion: **{outcome_c:.3f}**
- Pregnancy-status completion: **{pregnancy_c:.3f}**
- Dam-ID completion among pregnant samples: **{dam_preg_c:.3f}**

The prefixes B, U and P were used only as tissue labels.
Pregnancy outcomes were inferred only from per-sample GEO metadata,
not from the study title.

## U26B entry interpretation

- `READY_FOR_U26B`: expression, core sample design and dam structure are resolved.
- `READY_FOR_U26B_WITH_DAM_LEVEL_MODEL_DEFERRED`: tissue-stratified U26B may start, but dam-level pregnancy-risk modeling remains deferred.
- `TARGETED_METADATA_REVIEW_REQUIRED`: expression is resolved, but one or more core per-sample design fields still require reconstruction.
- `TARGETED_IDENTIFIER_MAPPING_REQUIRED`: no plausible local gene-symbol matrix was available.
"""
    (
        out_res
        / "UTI_HostOmics_U26A3_GSE280297_resolution_report.md"
    ).write_text(report)

    log(f"Decision: {decision}")
    log(
        "Decision table: "
        + str(
            out_tab
            / "UTI_HostOmics_U26A3_phase_decision.tsv"
        )
    )
    log(
        "Report: "
        + str(
            out_res
            / "UTI_HostOmics_U26A3_GSE280297_resolution_report.md"
        )
    )
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[U26A.3] ERROR: {exc}", file=sys.stderr)
        raise
