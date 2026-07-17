#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="__UTI_HOSTOMICS_PROJECT_ROOT__"
SCRIPT_NAME="phaseU26A_expanded_endocrine_metabolic_immune_feasibility_audit.py"
SCRIPT_PATH="$PROJECT_ROOT/10_scripts/$SCRIPT_NAME"
LOG_DIR="$PROJECT_ROOT/08_logs/phaseU26A_expanded_endocrine_metabolic_immune_feasibility"
LOG_FILE="$LOG_DIR/phaseU26A_run_$(date +%Y%m%d_%H%M%S).log"

if [ ! -d "$PROJECT_ROOT" ]; then
  echo "ERROR: Project root does not exist: $PROJECT_ROOT" >&2
  exit 2
fi

if [ ! -f "$SCRIPT_PATH" ]; then
  echo "ERROR: U26A Python script is missing: $SCRIPT_PATH" >&2
  exit 3
fi

mkdir -p "$LOG_DIR"
cd "$PROJECT_ROOT"

python3 "$SCRIPT_PATH" \
  --project-root "$PROJECT_ROOT" \
  --max-files-per-dataset 40 \
  2>&1 | tee "$LOG_FILE"

echo
echo "Phase U26A finished."
echo "Log: $LOG_FILE"
echo "Report: $PROJECT_ROOT/05_results/phaseU26A_expanded_endocrine_metabolic_immune_feasibility/UTI_HostOmics_U26A_feasibility_report.md"
echo "Coverage: $PROJECT_ROOT/06_tables/phaseU26A_expanded_endocrine_metabolic_immune_feasibility/UTI_HostOmics_U26A_submodule_coverage_by_dataset.tsv"
echo "Contrast map: $PROJECT_ROOT/06_tables/phaseU26A_expanded_endocrine_metabolic_immune_feasibility/UTI_HostOmics_U26A_feasible_contrast_map.tsv"
