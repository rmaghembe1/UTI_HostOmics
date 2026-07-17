#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-__UTI_HOSTOMICS_PROJECT_ROOT__}"
TAG="phaseU27B3E5_artifact_tool_handoff"
OUTDIR="$PROJECT_ROOT/11_supplementary/$TAG"
STAGE="$OUTDIR/staging/UTI_HostOmics_Project"
BUNDLE="$OUTDIR/UTI_HostOmics_U27B3E5_artifact_tool_input_bundle.zip"
MANIFEST="$OUTDIR/UTI_HostOmics_U27B3E5_artifact_tool_input_manifest.tsv"
README="$OUTDIR/README_UPLOAD_TO_CHATGPT.txt"

INPUT_TAG="phaseU27B3E321_semantic_accession_audit_correction"
RELEASE_TAG="phaseU27B3E411_contact_sheet_semantic_finalization"
AUDIT_TAG="phaseU27B3E4_supplementary_schema_content_audit"
SOURCE_TAG="phaseU27B3E32_repaired_supplementary_rematerialization"

if [ ! -d "$PROJECT_ROOT" ]; then
  echo "ERROR: project root not found: $PROJECT_ROOT" >&2
  exit 1
fi

rm -rf "$OUTDIR"
mkdir -p "$STAGE"

copy_rel() {
  local rel="$1"
  local src="$PROJECT_ROOT/$rel"
  local dst="$STAGE/$rel"
  if [ ! -e "$src" ]; then
    echo "ERROR: required input missing: $src" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$dst")"
  if [ -d "$src" ]; then
    cp -a "$src" "$dst"
  else
    cp -a "$src" "$dst"
  fi
}

# Byte-preserved scientific tables, package metadata, and controlled source ZIP.
copy_rel "11_supplementary/$INPUT_TAG/materialized_tables"
copy_rel "11_supplementary/$INPUT_TAG/manifests"

if [ -f "$PROJECT_ROOT/11_supplementary/$INPUT_TAG/UTI_HostOmics_U27B3E321_supplementary_package_README.md" ]; then
  copy_rel "11_supplementary/$INPUT_TAG/UTI_HostOmics_U27B3E321_supplementary_package_README.md"
fi

if [ -f "$PROJECT_ROOT/11_supplementary/$INPUT_TAG/UTI_HostOmics_U27B3E321_Supplementary_Tables_S1-S10.zip" ]; then
  copy_rel "11_supplementary/$INPUT_TAG/UTI_HostOmics_U27B3E321_Supplementary_Tables_S1-S10.zip"
fi

# U27B3E5 release gate and semantic exception registry.
copy_rel "06_tables/$RELEASE_TAG/UTI_HostOmics_U27B3E411_phase_decision.tsv"
copy_rel "03_metadata/$RELEASE_TAG/UTI_HostOmics_U27B3E411_semantic_exception_registry.tsv"
copy_rel "05_results/$RELEASE_TAG/UTI_HostOmics_U27B3E411_semantic_finalization_report.md"
copy_rel "05_results/$RELEASE_TAG/UTI_HostOmics_U27B3E411_run_manifest.json"

# Source-aware warning register and source-manifest fallback.
copy_rel "06_tables/$AUDIT_TAG/UTI_HostOmics_U27B3E4_warning_register.tsv"
copy_rel "06_tables/$SOURCE_TAG/UTI_HostOmics_U27B3E32_source_manifest.tsv"

# Exact workbook-construction code for provenance.
copy_rel "10_scripts/phaseU27B3E5_format_and_freeze_supplementary_workbook.py"
copy_rel "10_scripts/run_phaseU27B3E5_format_and_freeze_supplementary_workbook.sh"

cat > "$STAGE/U27B3E5_ARTIFACT_TOOL_HANDOFF_README.txt" <<'EOF'
UTI HostOmics U27B3E5 artifact_tool handoff

Purpose
-------
This bundle contains the validated, byte-preserved S1-S10 TSV package and the
release-gate metadata required to construct the submission-facing Excel
workbook in the ChatGPT artifact_tool runtime.

Scientific release gate
-----------------------
READY_FOR_U27B3E5_SUPPLEMENTARY_TABLE_SUBMISSION_FORMATTING_AND_FREEZE

Important
---------
The workbook must be constructed with artifact_tool. The local WSL environment
that produced this handoff did not contain artifact_tool, so workbook creation
was intentionally moved to the ChatGPT artifact runtime rather than replacing
the approved implementation with another spreadsheet library.

No scientific values were recalculated or modified while creating this bundle.
EOF

# Build deterministic file inventory before zipping.
python3 - "$STAGE" "$MANIFEST" <<'PY'
from pathlib import Path
import hashlib
import sys

stage = Path(sys.argv[1])
manifest = Path(sys.argv[2])
rows = []
for path in sorted(stage.rglob('*')):
    if not path.is_file():
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    rows.append((str(path.relative_to(stage)), path.stat().st_size, digest))

manifest.parent.mkdir(parents=True, exist_ok=True)
with manifest.open('w', encoding='utf-8') as handle:
    handle.write('relative_path\tsize_bytes\tsha256\n')
    for rel, size, digest in rows:
        handle.write(f'{rel}\t{size}\t{digest}\n')
print(f'Inventory files: {len(rows)}')
PY

# Copy the inventory inside the staged project.
mkdir -p "$STAGE/03_metadata/$TAG"
cp "$MANIFEST" "$STAGE/03_metadata/$TAG/$(basename "$MANIFEST")"

# Create ZIP using Python to avoid dependence on the zip command.
python3 - "$STAGE" "$BUNDLE" <<'PY'
from pathlib import Path
import sys
import zipfile

stage = Path(sys.argv[1])
bundle = Path(sys.argv[2])
bundle.parent.mkdir(parents=True, exist_ok=True)
if bundle.exists():
    bundle.unlink()

with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    root = stage.parent
    for path in sorted(stage.rglob('*')):
        if path.is_file():
            archive.write(path, arcname=str(path.relative_to(root)))

with zipfile.ZipFile(bundle) as archive:
    failed = archive.testzip()
    members = archive.namelist()
if failed is not None:
    raise SystemExit(f'ZIP integrity failure at member: {failed}')
print(f'ZIP members: {len(members)}')
PY

cat > "$README" <<EOF
U27B3E5 input bundle created successfully.

Upload this file to ChatGPT:
$BUNDLE

The bundle contains the validated S1-S10 TSV package, release decision,
semantic exception registry, warning register, source manifest, and exact
U27B3E5 workbook script.

No workbook was created locally because artifact_tool is not installed in the
WSL Python environment.
EOF

BUNDLE_SHA256="$(sha256sum "$BUNDLE" | awk '{print $1}')"
BUNDLE_SIZE="$(stat -c '%s' "$BUNDLE")"

echo
echo "===== U27B3E5 ARTIFACT_TOOL HANDOFF READY ====="
echo "Bundle: $BUNDLE"
echo "Size bytes: $BUNDLE_SIZE"
echo "SHA256: $BUNDLE_SHA256"
echo "Manifest: $MANIFEST"
echo "README: $README"
echo
echo "Copy to Windows Downloads with:"
echo "cp \"$BUNDLE\" \"${UTI_HOSTOMICS_DOWNLOADS_DIR:-$HOME/Downloads}/\""
