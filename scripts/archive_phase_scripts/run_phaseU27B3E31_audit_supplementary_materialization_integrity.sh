#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3E31_audit_supplementary_materialization_integrity.py"
TAG="phaseU27B3E31_supplementary_materialization_integrity_audit"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3E31_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B3E3.1 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E31_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3E31_supplementary_integrity_audit_report.md"
echo "Repair plan: $PROJECT_ROOT/03_metadata/$TAG/UTI_HostOmics_U27B3E31_targeted_source_map_repair_plan.tsv"
