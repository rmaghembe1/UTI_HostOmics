#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU26A2_resolve_GSE280297_identifiers_and_design.py"
TAG="phaseU26A2_GSE280297_identifier_design_resolution"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"
mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU26A2_run_${STAMP}.log"

python3 "$SCRIPT" --project-root "$PROJECT_ROOT" 2>&1 | tee "$LOG"

echo
echo "Phase U26A.2 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U26A2_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U26A2_GSE280297_resolution_report.md"
