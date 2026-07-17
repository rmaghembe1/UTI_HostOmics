#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
cd "$PROJECT_ROOT"

SCRIPT="10_scripts/phaseU26A1_targeted_source_contrast_and_species_repair.py"
LOGDIR="08_logs/phaseU26A1_targeted_source_contrast_species_repair"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/phaseU26A1_run_$(date +%Y%m%d_%H%M%S).log"

python3 "$SCRIPT" --project-root "$PROJECT_ROOT" 2>&1 | tee "$LOG"

echo
echo "Phase U26A.1 finished."
echo "Log: $PROJECT_ROOT/$LOG"
echo "Decision: $PROJECT_ROOT/06_tables/phaseU26A1_targeted_source_contrast_species_repair/UTI_HostOmics_U26A1_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/phaseU26A1_targeted_source_contrast_species_repair/UTI_HostOmics_U26A1_targeted_repair_report.md"
