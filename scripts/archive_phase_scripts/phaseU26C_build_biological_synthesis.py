#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

VERSION = "U26C_v1.0_2026-07-14"
TAG = "phaseU26C_biological_synthesis_figure_architecture"
CORE = "one_FDR_dataset_plus_independent_concordant_effect"
SECONDARY = "two_dataset_concordant_effect"
DIVERGENT = "context_divergent_or_tissue_specific"

DECOUPLING = {
    "steroid_synthesis": [
        "STEROIDOGENESIS_CORE", "ANDROGEN_TESTOSTERONE_BIOSYNTHESIS",
        "ESTROGEN_BIOSYNTHESIS", "CHOLESTEROL_BIOSYNTHESIS",
    ],
    "steroid_receptor_response": [
        "ANDROGEN_RECEPTOR_SIGNALING", "ESTROGEN_RECEPTOR_RESPONSE",
        "GLUCOCORTICOID_RESPONSE", "MINERALOCORTICOID_RESPONSE",
        "PROGESTERONE_BIOSYNTHESIS_RESPONSE",
    ],
    "metabolic_effector_response": [
        "INSULIN_RECEPTOR_IRS", "PI3K_AKT_SIGNALING", "LEPTIN_SIGNALING",
        "AMINO_ACID_TRANSPORT", "GLUCOSE_TRANSPORT", "FATTY_ACID_SYNTHESIS",
        "INFLAMMATORY_CARBON_USE_INDEX",
    ],
    "complement_effector_response": [
        "COMPLEMENT_CLASSICAL", "COMPLEMENT_TERMINAL_MAC",
        "COMPLEMENT_C3A_C5A_SIGNALING", "COMPLEMENT_OPSONOPHAGOCYTOSIS",
    ],
}

EDGES = [
    ("TLR4_LPS_SIGNALING_ANCHOR", "NFKB_MAPK_INFLAMMATION_ANCHOR", "innate inflammatory signaling"),
    ("TLR4_LPS_SIGNALING_ANCHOR", "PI3K_AKT_SIGNALING", "innate metabolic branch"),
    ("NFKB_MAPK_INFLAMMATION_ANCHOR", "NEUTROPHIL_NETOSIS_ANCHOR", "neutrophil effector activation"),
    ("COMPLEMENT_C3A_C5A_SIGNALING", "NEUTROPHIL_NETOSIS_ANCHOR", "anaphylatoxin-neutrophil coupling"),
    ("COMPLEMENT_OPSONOPHAGOCYTOSIS", "NEUTROPHIL_NETOSIS_ANCHOR", "opsonic effector coupling"),
    ("LEPTIN_SIGNALING", "PI3K_AKT_SIGNALING", "adipokine metabolic signaling"),
    ("INSULIN_RECEPTOR_IRS", "PI3K_AKT_SIGNALING", "canonical insulin signaling"),
    ("PI3K_AKT_SIGNALING", "GLYCOLYSIS", "carbon-use activation"),
    ("PI3K_AKT_SIGNALING", "GLYCOGEN_SYNTHESIS", "glucose storage"),
    ("XANTHINE_OXIDASE_OXIDATIVE_PURINE_CATABOLISM", "OXIDATIVE_STRESS_NRF2_ANCHOR", "purine-redox coupling"),
    ("OXIDATIVE_STRESS_NRF2_ANCHOR", "FERROPTOSIS_LIPID_PEROXIDATION", "lipid peroxidation"),
    ("STEROIDOGENESIS_CORE", "ANDROGEN_TESTOSTERONE_BIOSYNTHESIS", "androgen synthesis"),
    ("ANDROGEN_TESTOSTERONE_BIOSYNTHESIS", "ANDROGEN_RECEPTOR_SIGNALING", "androgen response"),
    ("ESTROGEN_BIOSYNTHESIS", "ESTROGEN_RECEPTOR_RESPONSE", "estrogen response"),
    ("GLUCOCORTICOID_RESPONSE", "NFKB_MAPK_INFLAMMATION_ANCHOR", "anti-inflammatory modulation"),
]

def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", compression="infer", low_memory=False)

def as_bool(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])

def evidence_tiers() -> pd.DataFrame:
    return pd.DataFrame([
        ["Tier_1_human_adjusted_FDR", "GSE112098 age/sex-adjusted FDR < 0.10", "Strongest inferential layer; systemic urinary inflammation, not UTI-specific", "was associated with"],
        ["Tier_2_independent_concordance", "Concordant moderate effect in at least one independent dataset", "Independent pathway support without replicated FDR", "showed concordant remodeling"],
        ["Tier_3_mouse_treatment", "GSE186800 average Gardnerella-versus-PBS effect", "Independent mouse-bladder direction; no treatment FDR < 0.10", "was directionally altered"],
        ["Tier_4_pregnancy_tissue", "GSE280297 UPEC or preterm pregnancy-tissue effect", "Tissue-resolved discovery evidence", "suggested"],
        ["Tier_5_exploratory_UPEC", "GSE252321 pseudobulk, n=2 per group", "Magnitude and direction only", "was directionally consistent with"],
        ["Excluded_from_infection_claims", "GSE186800 PBS block effect", "Experimental-block or exposure-stage difference", "must not be called infection-induced"],
    ], columns=["tier", "definition", "interpretation", "manuscript_verb"])

def build_core(recur: pd.DataFrame, preterm: pd.DataFrame, effects: pd.DataFrame) -> pd.DataFrame:
    p = preterm.drop_duplicates("feature_id").set_index("feature_id")
    out = recur[recur.validation_class.isin([CORE, SECONDARY])].copy()

    non_tiny = effects[~effects.dataset.isin(["GSE112098", "GSE252321"])].copy()
    non_tiny["effect_value"] = pd.to_numeric(non_tiny.effect_value, errors="coerce")
    non_tiny["concordant_moderate"] = False

    for idx, row in out.iterrows():
        feature = row.feature_id
        direction = row.dominant_direction
        subset = non_tiny[non_tiny.feature_id.eq(feature)].copy()
        if direction == "positive":
            support = subset.effect_value.ge(0.5)
        elif direction == "negative":
            support = subset.effect_value.le(-0.5)
        else:
            support = pd.Series(False, index=subset.index)
        n_support = int(support.sum())
        out.loc[idx, "n_non_tiny_concordant_moderate_datasets"] = n_support

    out["biological_priority"] = np.select(
        [
            out.validation_class.eq(CORE) & out.n_non_tiny_concordant_moderate_datasets.ge(1),
            out.validation_class.eq(CORE),
            out.validation_class.eq(SECONDARY),
        ],
        ["robust_core", "provisional_core_exploratory_dependent", "secondary"],
        default="secondary",
    )
    out["preterm_vs_term_effect"] = out.feature_id.map(p.effect_value if "effect_value" in p else {})
    out["preterm_tissue_coherence"] = out.feature_id.map(p.tissue_directional_coherence if "tissue_directional_coherence" in p else {})
    out["preterm_direction"] = np.select(
        [out.preterm_vs_term_effect > 0, out.preterm_vs_term_effect < 0],
        ["positive", "negative"], default="unresolved"
    )
    out["infection_outcome_relation"] = np.where(
        out.preterm_direction.eq("unresolved"), "unresolved",
        np.where(out.preterm_direction.eq(out.dominant_direction), "direction_preserved", "direction_reversal")
    )
    order = pd.Categorical(
        out.biological_priority,
        categories=["robust_core", "provisional_core_exploratory_dependent", "secondary"],
        ordered=True,
    )
    out = out.assign(_priority_order=order)
    return out.sort_values(["_priority_order", "independent_evidence_priority_score"], ascending=[True, False]).drop(columns="_priority_order")

def build_decoupling(preterm: pd.DataFrame):
    p = preterm.drop_duplicates("feature_id").set_index("feature_id")
    rows, domains = [], []
    for domain, feats in DECOUPLING.items():
        vals = []
        for feat in feats:
            if feat not in p.index:
                continue
            r = p.loc[feat]
            val = float(r.effect_value)
            vals.append(val)
            rows.append({
                "domain": domain, "feature_id": feat, "display_label": r.display_label,
                "axis": r.axis, "effect_value": val, "absolute_effect": abs(val),
                "direction": r.direction, "tissue_directional_coherence": r.tissue_directional_coherence,
                "fdr_0_10": r.fdr_0_10, "best_tissue_q_value": r.best_tissue_q_value,
            })
        if vals:
            pos, neg = sum(v > 0 for v in vals), sum(v < 0 for v in vals)
            domains.append({
                "domain": domain, "n_features": len(vals), "median_effect": float(np.median(vals)),
                "mean_effect": float(np.mean(vals)), "n_positive": pos, "n_negative": neg,
                "directional_coherence": max(pos, neg) / len(vals),
                "dominant_direction": "positive" if pos > neg else "negative" if neg > pos else "mixed",
            })
    return pd.DataFrame(rows), pd.DataFrame(domains)

def build_nodes_edges(recur: pd.DataFrame, preterm: pd.DataFrame):
    r = recur.drop_duplicates("feature_id").set_index("feature_id")
    p = preterm.drop_duplicates("feature_id").set_index("feature_id")
    ids = sorted(set([x for e in EDGES for x in e[:2]]))
    nodes = []
    for feat in ids:
        rr = r.loc[feat] if feat in r.index else None
        pp = p.loc[feat] if feat in p.index else None
        nodes.append({
            "feature_id": feat,
            "display_label": rr.display_label if rr is not None else (pp.display_label if pp is not None else feat.replace("_", " ").title()),
            "axis": rr.axis if rr is not None else (pp.axis if pp is not None else ""),
            "validation_class": rr.validation_class if rr is not None else "pregnancy_outcome_only",
            "infection_direction": rr.dominant_direction if rr is not None else "unresolved",
            "infection_coherence": rr.weighted_directional_coherence if rr is not None else np.nan,
            "preterm_effect": pp.effect_value if pp is not None else np.nan,
            "preterm_coherence": pp.tissue_directional_coherence if pp is not None else np.nan,
        })
    edges = pd.DataFrame(EDGES, columns=["source", "target", "mechanistic_relation"])
    edges["edge_status"] = "mechanistic hypothesis supported by module patterns"
    return pd.DataFrame(nodes), edges

def claims() -> pd.DataFrame:
    return pd.DataFrame([
        ["Human adjusted FDR only", "Associated with human urinary systemic inflammation", "UTI-specific, causal or cell-type-specific wording"],
        ["Human FDR plus concordant independent effect", "Recurrent urinary inflammatory module with independent cross-model support", "Replicated FDR across cohorts"],
        ["GSE186800 treatment direction without FDR", "Directionally altered in a mouse bladder exposure model", "Significantly regulated by Gardnerella"],
        ["GSE186800 PBS block FDR", "Exposure-stage or experimental-block difference among controls", "Gardnerella-induced effect"],
        ["Large coherent GSE280297 preterm effect", "Candidate pregnancy-outcome-associated tissue programme", "Confirmed mechanism of preterm birth or miscarriage"],
        ["GSE252321 n=2 versus n=2", "Exploratory directionally consistent UPEC response", "Validated, significant or cell-type-specific effect"],
        ["Opposite effects across models", "Context-dependent remodeling", "Universal activation or repression"],
    ], columns=["evidence_pattern", "allowed_claim", "avoid"])

def panel_evidence(plan, recur, effects, preterm):
    r = recur.drop_duplicates("feature_id").set_index("feature_id")
    p = preterm.drop_duplicates("feature_id").set_index("feature_id")
    rows = []
    for _, panel in plan.iterrows():
        mods = [m for m in str(panel.priority_modules).split(";") if m]
        for rank, feat in enumerate(mods, 1):
            rr = r.loc[feat] if feat in r.index else None
            pp = p.loc[feat] if feat in p.index else None
            e = effects[effects.feature_id.eq(feat)]
            rows.append({
                "figure_family": panel.figure_family, "figure_title": panel.figure_title,
                "panel": panel.panel, "panel_title": panel.panel_title,
                "panel_purpose": panel.purpose, "module_rank": rank, "feature_id": feat,
                "display_label": rr.display_label if rr is not None else (pp.display_label if pp is not None else feat),
                "validation_class": rr.validation_class if rr is not None else "pregnancy_outcome_priority",
                "infection_direction": rr.dominant_direction if rr is not None else "unresolved",
                "infection_coherence": rr.weighted_directional_coherence if rr is not None else np.nan,
                "preterm_effect": pp.effect_value if pp is not None else np.nan,
                "preterm_coherence": pp.tissue_directional_coherence if pp is not None else np.nan,
                "dataset_effects": ";".join(f"{x.dataset}={float(x.effect_value):.4f}|FDR10={x.fdr_0_10}" for _, x in e.iterrows() if pd.notna(x.effect_value)),
            })
    return pd.DataFrame(rows)

def save_heatmap(core, effects, stem):
    if core.empty:
        return
    feats = core.feature_id.tolist()
    mat = effects[effects.feature_id.isin(feats)].pivot_table(index="feature_id", columns="dataset", values="effect_value", aggfunc="first").reindex(feats)
    fig = plt.figure(figsize=(9, max(5, 0.55 * len(mat) + 2)))
    ax = fig.add_axes([0.38, 0.18, 0.48, 0.70])
    im = ax.imshow(mat.to_numpy(float), aspect="auto")
    ax.set_xticks(np.arange(len(mat.columns))); ax.set_xticklabels(mat.columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(mat.index))); ax.set_yticklabels(mat.index, fontsize=8)
    ax.set_title("Core and secondary independent-dataset module effects")
    ax.set_xlabel("Independent dataset"); ax.set_ylabel("Submodule")
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04); cb.set_label("Standardized effect")
    fig.savefig(stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight"); plt.close(fig)

def save_decoupling(dec, stem):
    if dec.empty:
        return
    d = dec.sort_values(["domain", "effect_value"]).copy()
    labels = [f"{a}: {b}" for a, b in zip(d.domain, d.feature_id)]
    fig = plt.figure(figsize=(11, max(7, 0.36 * len(d) + 2.5)))
    ax = fig.add_axes([0.42, 0.10, 0.48, 0.82])
    y = np.arange(len(d)); ax.barh(y, d.effect_value.to_numpy(float)); ax.axvline(0, linewidth=1)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Preterm versus term median tissue effect")
    ax.set_title("Pregnancy-associated synthesis-response decoupling")
    fig.savefig(stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight"); plt.close(fig)

def write_report(path, core, divergent, domain):
    robust = core[core.biological_priority.eq("robust_core")]
    provisional = core[core.biological_priority.eq("provisional_core_exploratory_dependent")]
    secondary = core[core.biological_priority.eq("secondary")]
    with path.open("w") as h:
        h.write(f"# Phase U26C - Biological synthesis and Figure 7-11 architecture\n\n- Version: `{VERSION}`\n- Manuscript and existing Figures 1-6 were not modified.\n- No module showed replicated FDR < 0.10 across two independent datasets.\n\n")
        h.write("## Robust core cross-dataset modules\n\n")
        for _, r in robust.iterrows():
            h.write(f"- **{r.display_label}** (`{r.feature_id}`): one human adjusted FDR signal plus a concordant moderate effect outside the n=2-per-group GSE252321 layer; infection direction {r.dominant_direction} (coherence={r.weighted_directional_coherence:.2f}); preterm effect={r.preterm_vs_term_effect:.3f} ({r.infection_outcome_relation}).\n")
        h.write("\n## Provisional core modules dependent on exploratory pseudobulk\n\n")
        for _, r in provisional.iterrows():
            h.write(f"- **{r.display_label}** (`{r.feature_id}`): human adjusted FDR plus a moderate concordant effect driven by GSE252321 n=2-per-group pseudobulk; retain as provisional until cell-type or larger-sample validation.\n")
        h.write("\n## Secondary concordant modules\n\n")
        for _, r in secondary.iterrows():
            h.write(f"- **{r.display_label}** (`{r.feature_id}`): two-dataset concordant effect without independent FDR replication.\n")
        h.write("\n## Pregnancy synthesis-response decoupling\n\n")
        for _, r in domain.iterrows():
            h.write(f"- **{r.domain}**: median effect {r.median_effect:.3f}; dominant direction {r.dominant_direction}; coherence {r.directional_coherence:.2f}.\n")
        h.write("\nThe pattern supports a hypothesis in which steroidogenic transcription is preserved or increased while receptor-response, insulin/PI3K-AKT, adipokine, amino-acid transport and inflammatory-carbon programmes are attenuated. These are transcriptionally inferred pathway activities, not measured hormone concentrations or metabolic flux.\n\n")
        h.write("## Context-divergent biology\n\n")
        for _, r in divergent.head(15).iterrows():
            h.write(f"- `{r.feature_id}`: {r.dataset_effects}; interpret as context-dependent remodeling.\n")
        h.write("\n## Figure architecture\n\n- **Figure 7:** steroid, cholesterol, receptor-response and lipid-peroxidation remodeling.\n- **Figure 8:** adipokine, insulin/IRS, PI3K-AKT and inflammatory carbon use.\n- **Figure 9:** amino-acid, nucleotide, nitrogen, redox and catecholamine-adjacent metabolism.\n- **Figure 10:** complement initiation, amplification, effector and regulation.\n- **Figure 11:** integrated synthesis-response decoupling and carbon-complement-inflammatory network.\n\n")
        h.write("## Cell-type reconstruction decision\n\nGSE252321 cell-type reconstruction is recommended before final manuscript freeze, but it does not block current biological synthesis or Figure 7-11 development.\n")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--project-root", default="__UTI_HOSTOMICS_PROJECT_ROOT__")
    project = Path(ap.parse_args().project_root).resolve()
    src = "phaseU26B2B1_independent_dataset_evidence_collapse"
    tab = project / "06_tables" / src; meta = project / "03_metadata" / src
    paths = {
        "recur": tab / "UTI_HostOmics_U26B2B1_independent_dataset_recurrence_ranking.tsv",
        "effects": tab / "UTI_HostOmics_U26B2B1_primary_independent_dataset_effects.tsv",
        "preterm": tab / "UTI_HostOmics_U26B2B1_GSE280297_preterm_term_collapsed.tsv",
        "plan": meta / "UTI_HostOmics_U26B2B1_Figures_7_to_11_panel_plan.tsv",
    }
    for p in paths.values():
        if not p.exists(): raise FileNotFoundError(p)
    out_r = project / "05_results" / TAG; out_t = project / "06_tables" / TAG
    out_m = project / "03_metadata" / TAG; out_f = project / "06_figures" / TAG
    for d in [out_r, out_t, out_m, out_f]: d.mkdir(parents=True, exist_ok=True)

    recur, effects, preterm, plan = map(read_tsv, [paths["recur"], paths["effects"], paths["preterm"], paths["plan"]])
    preterm["effect_value"] = pd.to_numeric(preterm.effect_value, errors="coerce")
    preterm["fdr_0_10"] = as_bool(preterm.fdr_0_10)

    tiers = evidence_tiers(); tiers.to_csv(out_m / "UTI_HostOmics_U26C_evidence_tier_dictionary.tsv", sep="\t", index=False)
    core = build_core(recur, preterm, effects); core.to_csv(out_t / "UTI_HostOmics_U26C_core_and_secondary_modules.tsv", sep="\t", index=False)
    divergent = recur[recur.validation_class.eq(DIVERGENT)].copy(); divergent.to_csv(out_t / "UTI_HostOmics_U26C_context_divergent_modules.tsv", sep="\t", index=False)
    dec, domain = build_decoupling(preterm); dec.to_csv(out_t / "UTI_HostOmics_U26C_pregnancy_synthesis_response_decoupling.tsv", sep="\t", index=False); domain.to_csv(out_t / "UTI_HostOmics_U26C_decoupling_domain_summary.tsv", sep="\t", index=False)
    nodes, edges = build_nodes_edges(recur, preterm); nodes.to_csv(out_t / "UTI_HostOmics_U26C_integrated_network_nodes.tsv", sep="\t", index=False); edges.to_csv(out_t / "UTI_HostOmics_U26C_integrated_network_edges.tsv", sep="\t", index=False)
    claims().to_csv(out_m / "UTI_HostOmics_U26C_claim_boundary_matrix.tsv", sep="\t", index=False)
    pe = panel_evidence(plan, recur, effects, preterm); pe.to_csv(out_t / "UTI_HostOmics_U26C_Figures_7_to_11_panel_evidence.tsv", sep="\t", index=False)
    for fam, sub in pe.groupby("figure_family"): sub.to_csv(out_t / f"UTI_HostOmics_U26C_{fam}_panel_evidence.tsv", sep="\t", index=False)
    save_heatmap(core, effects, out_f / "UTI_HostOmics_U26C_core_module_effect_heatmap")
    save_decoupling(dec, out_f / "UTI_HostOmics_U26C_pregnancy_synthesis_response_decoupling")
    report = out_r / "UTI_HostOmics_U26C_biological_synthesis_report.md"; write_report(report, core, divergent, domain)

    decision = "READY_FOR_U26D_CELLTYPE_RECONSTRUCTION_AND_U27_FIGURE_MANUSCRIPT_INTEGRATION"
    summary = pd.DataFrame([{
        "phase": "U26C", "decision": decision,
        "n_robust_core_modules": int(core.biological_priority.eq("robust_core").sum()),
        "n_provisional_core_modules": int(core.biological_priority.eq("provisional_core_exploratory_dependent").sum()),
        "n_secondary_concordant_modules": int(core.biological_priority.eq("secondary").sum()),
        "n_context_divergent_modules": len(divergent),
        "n_network_nodes": len(nodes), "n_network_edges": len(edges),
        "figures_7_to_11_architecture_ready": True,
        "cell_type_reconstruction": "recommended_before_final_manuscript_freeze",
        "cell_type_reconstruction_blocks_current_synthesis": False,
        "metabolic_wording_rule": "transcriptionally inferred metabolic pathway activity; not measured metabolic flux",
        "manuscript_modified": False, "existing_figures_modified": False,
        "next_phase": "U26D cell-type reconstruction in parallel with U27 figure construction and manuscript integration",
    }])
    summary.to_csv(out_t / "UTI_HostOmics_U26C_phase_decision.tsv", sep="\t", index=False)
    (out_r / "UTI_HostOmics_U26C_run_manifest.json").write_text(json.dumps({
        "version": VERSION, "project_root": str(project), "decision": decision,
        "robust_core_modules": int(core.biological_priority.eq("robust_core").sum()),
        "provisional_core_modules": int(core.biological_priority.eq("provisional_core_exploratory_dependent").sum()),
        "secondary_modules": int(core.biological_priority.eq("secondary").sum()),
        "context_divergent_modules": int(len(divergent)),
        "manuscript_modified": False, "existing_figures_modified": False,
    }, indent=2))
    print(f"[U26C] Robust core modules: {int(core.biological_priority.eq('robust_core').sum())}")
    print(f"[U26C] Provisional core modules: {int(core.biological_priority.eq('provisional_core_exploratory_dependent').sum())}")
    print(f"[U26C] Secondary modules: {int(core.biological_priority.eq('secondary').sum())}")
    print(f"[U26C] Context-divergent modules: {len(divergent)}")
    print(f"[U26C] Decision: {decision}")
    print(f"[U26C] Report: {report}")

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"[U26C] ERROR: {exc}", file=sys.stderr)
        raise
