#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B2D_build_final_figures_5_to_8.py"
TAG="phaseU27B2D_final_figures_5_to_8_build"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B2D_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B2D finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B2D_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B2D_final_figures_5_to_8_build_report.md"
echo "Figures: $PROJECT_ROOT/06_figures/$TAG"
