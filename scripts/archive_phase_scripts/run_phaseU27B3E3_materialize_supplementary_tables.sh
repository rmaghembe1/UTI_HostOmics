#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3E3_materialize_supplementary_tables.py"
TAG="phaseU27B3E3_supplementary_table_materialization"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3E3_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B3E3 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E3_phase_decision.tsv"
echo "Summary: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E3_materialization_summary.tsv"
echo "Package: $PROJECT_ROOT/11_supplementary/$TAG/UTI_HostOmics_U27B3E3_Supplementary_Tables_S1-S10.zip"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3E3_supplementary_materialization_report.md"
