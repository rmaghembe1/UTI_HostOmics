#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3D2_reconstruct_manuscript_v6.py"
TAG="phaseU27B3D2_manuscript_wide_v6_reconstruction"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3D2_run_${STAMP}.log"

python3 "$SCRIPT" --project-root "$PROJECT_ROOT" 2>&1 | tee "$LOG"

echo
echo "Phase U27B3D2 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3D2_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3D2_v6_reconstruction_report.md"
echo "Output manuscript: $PROJECT_ROOT/09_manuscript_docx/$TAG/UTI_HostOmics_preZotero_manuscript_v6_0_U27B3D2_scientifically_harmonized.docx"
echo "Render contact sheet: $PROJECT_ROOT/09_manuscript_docx/$TAG/render_qa/UTI_HostOmics_U27B3D2_render_contact_sheet.png"
