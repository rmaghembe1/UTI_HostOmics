#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B2E2C_final_scatter_annotation_title_repair.py"
TAG="phaseU27B2E2C_final_scatter_annotation_title_repair"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B2E2C_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B2E2C finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B2E2C_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B2E2C_scatter_annotation_title_repair_report.md"
echo "Figures: $PROJECT_ROOT/06_figures/$TAG"
