#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
SCRIPT="$PROJECT_ROOT/10_scripts/phaseU26D2A_reconstruct_GSE252321_celltypes.py"
TAG="phaseU26D2A_GSE252321_marker_celltype_reconstruction"
LOGDIR="$PROJECT_ROOT/08_logs/$TAG"

mkdir -p "$LOGDIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/phaseU26D2A_run_${STAMP}.log"

python3 "$SCRIPT" \
  --project-root "$PROJECT_ROOT" \
  --balanced-cells-per-sample 2500 \
  --n-hvg 2500 \
  --n-components 30 \
  --n-clusters 18 \
  2>&1 | tee "$LOG"

echo
echo "Phase U26D2A finished."
echo "Log: $LOG"
echo "Decision: $PROJECT_ROOT/06_tables/$TAG/UTI_HostOmics_U26D2A_phase_decision.tsv"
echo "Report: $PROJECT_ROOT/05_results/$TAG/UTI_HostOmics_U26D2A_celltype_reconstruction_report.md"
