#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3E1_finalize_reference_supplement_submission_architecture.py"
TAG="phaseU27B3E1_reference_supplement_submission_architecture"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3E1_run_${STAMP}.log"

python3 "$SCRIPT" --project-root "$PROJECT_ROOT" 2>&1 | tee "$LOG"

echo
echo "Phase U27B3E1 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E1_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3E1_submission_architecture_report.md"
echo "Cleaned manuscript: $PROJECT_ROOT/09_manuscript_docx/$TAG/UTI_HostOmics_preZotero_manuscript_v6_2_U27B3E1_submission_architecture_cleaned.docx"
echo "Internal reference companion: $PROJECT_ROOT/09_manuscript_docx/$TAG/internal_reference_tracking/UTI_HostOmics_U27B3E1_internal_reference_and_Zotero_tracking.docx"
echo "Render contact sheet: $PROJECT_ROOT/09_manuscript_docx/$TAG/render_qa/UTI_HostOmics_U27B3E1_render_contact_sheet.png"
