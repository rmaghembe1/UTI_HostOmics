#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B2A2_finalize_panel_source_lock.py"
TAG="phaseU27B2A2_final_panel_source_lock"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B2A2_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B2A.2 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B2A2_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B2A2_final_source_lock_report.md"
