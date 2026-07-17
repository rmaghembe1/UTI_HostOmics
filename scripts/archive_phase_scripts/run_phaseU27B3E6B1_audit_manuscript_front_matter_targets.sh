#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
EXPECTED="__UTI_HOSTOMICS_PROJECT_ROOT__"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3E6B1_audit_manuscript_front_matter_targets.py"
TAG="phaseU27B3E6B1_manuscript_front_matter_target_audit"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

if [ "$PROJECT_ROOT" != "$EXPECTED" ]; then
  echo "ERROR: Wrong project root: $PROJECT_ROOT" >&2
  echo "Expected: $EXPECTED" >&2
  exit 1
fi

mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3E6B1_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B3E6B1 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E6B1_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3E6B1_manuscript_front_matter_target_audit_report.md"
