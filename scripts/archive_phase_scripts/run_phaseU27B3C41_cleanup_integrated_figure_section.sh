#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3C41_cleanup_integrated_figure_section.py"
TAG="phaseU27B3C41_integrated_figure_section_cleanup"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3C41_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B3C4.1 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3C41_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3C41_figure_section_cleanup_report.md"
echo "Cleaned manuscript: $PROJECT_ROOT/09_manuscript_docx/$TAG/UTI_HostOmics_preZotero_manuscript_v5_2_U27B3C41_figure_section_cleaned.docx"
echo "Render contact sheet: $PROJECT_ROOT/09_manuscript_docx/$TAG/render_qa/UTI_HostOmics_U27B3C41_render_contact_sheet.png"
