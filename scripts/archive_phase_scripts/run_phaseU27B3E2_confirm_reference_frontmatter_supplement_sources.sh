#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU27B3E2_confirm_reference_frontmatter_supplement_sources.py"
TAG="phaseU27B3E2_reference_frontmatter_supplement_source_confirmation"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU27B3E2_run_${STAMP}.log"

python3 "$SCRIPT" --project-root "$PROJECT_ROOT" 2>&1 | tee "$LOG"

echo
echo "Phase U27B3E2 finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U27B3E2_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U27B3E2_reference_frontmatter_supplement_report.md"
echo "Front-matter template: $PROJECT_ROOT/07_manuscript/$TAG/UTI_HostOmics_U27B3E2_front_matter_copy_paste_template.md"
