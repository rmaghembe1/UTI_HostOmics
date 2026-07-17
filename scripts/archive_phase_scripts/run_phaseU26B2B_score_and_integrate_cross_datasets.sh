#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU26B2B_score_and_integrate_cross_datasets.py"
TAG="phaseU26B2B_cross_dataset_scoring_integration"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU26B2B_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U26B2B finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U26B2B_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U26B2B_cross_dataset_scoring_report.md"
