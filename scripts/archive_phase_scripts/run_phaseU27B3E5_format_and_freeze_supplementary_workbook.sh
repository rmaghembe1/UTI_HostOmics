#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3E5_format_and_freeze_supplementary_workbook.py"
TAG="phaseU27B3E5_supplementary_submission_formatting_and_freeze"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3E5_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B3E5 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E5_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3E5_submission_formatting_and_freeze_report.md"
echo "Workbook: $PROJECT_ROOT/11_supplementary/$TAG/submission_upload_only/UTI_HostOmics_Supplementary_Tables_S1-S10.xlsx"
echo "Contact sheet: $PROJECT_ROOT/11_supplementary/$TAG/render_qa/UTI_HostOmics_U27B3E5_workbook_preview_contact_sheet.png"
