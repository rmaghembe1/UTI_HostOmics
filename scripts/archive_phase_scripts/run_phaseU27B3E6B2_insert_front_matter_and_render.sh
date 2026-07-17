#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
EXPECTED="__UTI_HOSTOMICS_PROJECT_ROOT__"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3E6B2_insert_front_matter_and_render.py"
TAG="phaseU27B3E6B2_targeted_front_matter_insertion"
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
LOG="$LOGDIR/phaseU27B3E6B2_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  2>&1 | tee "$LOG"

echo
echo "Phase U27B3E6B2 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E6B2_phase_decision.tsv"
echo "DOCX: $PROJECT_ROOT/09_manuscript_docx/$TAG/UTI_HostOmics_preZotero_manuscript_v6_4_U27B3E6B2_front_matter_complete.docx"
echo "Contact sheet: $PROJECT_ROOT/09_manuscript_docx/$TAG/render_qa/UTI_HostOmics_U27B3E6B2_render_contact_sheet.png"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3E6B2_front_matter_insertion_report.md"
