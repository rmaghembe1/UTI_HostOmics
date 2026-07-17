#!/usr/bin/env bash

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
EXPECTED="__UTI_HOSTOMICS_PROJECT_ROOT__"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3E6B2A_insert_front_matter_without_render_v2.py"
TAG="phaseU27B3E6B2A_safe_front_matter_insertion"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

if [ "$PROJECT_ROOT" != "$EXPECTED" ]; then
  echo "ERROR: Wrong project root: $PROJECT_ROOT" >&2
  echo "Expected: $EXPECTED" >&2
  exit 1
fi

if [ ! -f "$SCRIPT" ]; then
  echo "ERROR: Script not found: $SCRIPT" >&2
  exit 1
fi

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3E6B2A_v2_run_${STAMP}.log"

echo "===== PHASE U27B3E6B2A V2 ====="
echo "Project: $PROJECT_ROOT"
echo "Script: $SCRIPT"
echo "Log: $LOG"
echo

PYTHONUNBUFFERED=1 python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

STATUS="${PIPESTATUS[0]}"

echo
if [ "$STATUS" -eq 0 ]; then
  echo "Phase U27B3E6B2A v2 finished successfully."
else
  echo "Phase U27B3E6B2A v2 failed with status $STATUS." >&2
fi

echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E6B2A_phase_decision.tsv"
echo "DOCX: $PROJECT_ROOT/09_manuscript_docx/$TAG/UTI_HostOmics_preZotero_manuscript_v6_4_U27B3E6B2A_front_matter_complete_unrendered.docx"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3E6B2A_safe_front_matter_insertion_report.md"

exit "$STATUS"
