#!/usr/bin/env python3
"""Run an archived UTI HostOmics phase script with portable path substitution.

The archived scripts preserve the original phase-resolved logic. Machine-specific
project paths have been replaced by placeholders. This runner materializes a
temporary copy in which those placeholders point to a user-supplied reconstruction
root and the current repository root.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_TOKEN = "__UTI_HOSTOMICS_PROJECT_ROOT__"
REPOSITORY_TOKEN = "__UTI_HOSTOMICS_REPOSITORY_ROOT__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "script",
        help="Path relative to scripts/archive_phase_scripts or an absolute path.",
    )
    parser.add_argument(
        "--project-root",
        required=True,
        help="Local reconstruction root used for data and generated outputs.",
    )
    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to the archived script after '--'.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repository_root = Path(__file__).resolve().parents[1]
    archive_root = repository_root / "scripts" / "archive_phase_scripts"

    script = Path(args.script)
    if not script.is_absolute():
        script = archive_root / script
    script = script.resolve()

    if not script.exists() or not script.is_file():
        raise FileNotFoundError(f"Archived script not found: {script}")

    project_root = Path(args.project_root).expanduser().resolve()
    project_root.mkdir(parents=True, exist_ok=True)

    text = script.read_text(encoding="utf-8")
    text = text.replace(PROJECT_TOKEN, str(project_root))
    text = text.replace(REPOSITORY_TOKEN, str(repository_root))

    suffix = script.suffix.lower()
    if suffix not in {".py", ".sh", ".r"}:
        raise ValueError(f"Unsupported archived script type: {suffix}")

    with tempfile.TemporaryDirectory(prefix="uti_hostomics_") as tmp:
        materialized = Path(tmp) / script.name
        materialized.write_text(text, encoding="utf-8")
        materialized.chmod(0o755)

        if suffix == ".py":
            command = [sys.executable, str(materialized)]
        elif suffix == ".sh":
            command = ["bash", str(materialized)]
        else:
            rscript = shutil.which("Rscript")
            if not rscript:
                raise RuntimeError("Rscript is required to run archived R scripts.")
            command = [rscript, str(materialized)]

        forwarded = list(args.script_args)
        if forwarded and forwarded[0] == "--":
            forwarded = forwarded[1:]
        command.extend(forwarded)

        environment = os.environ.copy()
        environment["UTI_HOSTOMICS_PROJECT_ROOT"] = str(project_root)
        environment["UTI_HOSTOMICS_REPOSITORY_ROOT"] = str(repository_root)

        print("Repository root:", repository_root)
        print("Project root:", project_root)
        print("Archived script:", script)
        print("Command:", " ".join(command))

        completed = subprocess.run(command, env=environment)
        return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
