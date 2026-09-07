"""Validate the contents of a Flet desktop build artifact."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from zipfile import ZipFile

MODEL_RELATIVE_PATH = "models/maintenance_classifier.joblib"
MODEL_FILENAME = "maintenance_classifier.joblib"
MAX_ARCHIVE_SIZE_MB = 300

FORBIDDEN_ROOTS = frozenset(
    {
        ".DS_Store",
        ".agents",
        ".claude",
        ".codex",
        ".codex_work",
        ".codegraph",
        ".cursor",
        ".git",
        ".github",
        ".idea",
        ".maintenance_llm.env",
        ".pytest_cache",
        ".ruff_cache",
        ".serena",
        ".trellis",
        ".venv",
        ".vscode",
        ".worktrees",
        "Notebook",
        "build",
        "build-sidecar",
        "config.user.json",
        "data",
        "dist",
        "docs",
        "node_modules",
        "outputs",
        "public",
        "src",
        "src-tauri",
        "tests",
        "wheels",
    }
)

ROOT_DATA_SUFFIXES = (".csv", ".db", ".jsonl", ".log", ".xls", ".xlsx")


class FletPackageValidationError(ValueError):
    """Raised when a Flet build contains an invalid or incomplete payload."""


def _validate_scope(names: Iterable[str], label: str) -> None:
    normalized_names = [name.replace("\\", "/") for name in names if name]
    roots = {name.split("/", 1)[0] for name in normalized_names}
    unexpected = sorted(FORBIDDEN_ROOTS & roots)
    if unexpected:
        raise FletPackageValidationError(
            f"unexpected files in {label}: {', '.join(unexpected)}"
        )

    root_data_files = sorted(
        name
        for name in normalized_names
        if "/" not in name and name.lower().endswith(ROOT_DATA_SUFFIXES)
    )
    if root_data_files:
        raise FletPackageValidationError(
            f"unexpected root-level data files in {label}: "
            + ", ".join(root_data_files)
        )

    if not any(
        name == MODEL_RELATIVE_PATH or name.endswith(f"/{MODEL_RELATIVE_PATH}")
        for name in normalized_names
    ):
        raise FletPackageValidationError(
            f"maintenance classifier is missing from {label}"
        )


def _validate_archive(archive: Path) -> str:
    with ZipFile(archive) as package:
        _validate_scope(package.namelist(), f"Flet app archive {archive}")

    size_mb = archive.stat().st_size / (1024 * 1024)
    if size_mb > MAX_ARCHIVE_SIZE_MB:
        raise FletPackageValidationError(
            f"Flet app.zip is unexpectedly large ({size_mb:.1f} MiB)"
        )
    return f"Verified {archive}: {size_mb:.1f} MiB"


def _validate_unpacked_app(app_root: Path) -> str:
    names = (
        path.relative_to(app_root).as_posix()
        for path in app_root.rglob("*")
        if path.exists()
    )
    _validate_scope(names, f"unpacked Flet app {app_root}")
    return f"Verified unpacked Flet app: {app_root}"


def validate_artifact(artifact: Path) -> list[str]:
    """Validate a legacy archive or a Flet 0.86+ unpacked desktop app."""

    artifact = Path(artifact)
    if not artifact.is_dir():
        raise FletPackageValidationError(f"Flet artifact directory not found: {artifact}")

    archives = sorted(artifact.rglob("app.zip"))
    unpacked_app_roots = sorted(
        {
            model_file.parent.parent
            for model_file in artifact.rglob(MODEL_FILENAME)
            if model_file.is_file() and model_file.parent.name == "models"
        }
    )

    if not archives and not unpacked_app_roots:
        raise FletPackageValidationError(
            f"no Flet app payload found under {artifact}; expected app.zip or "
            f"unpacked {MODEL_RELATIVE_PATH}"
        )

    messages = [_validate_archive(archive) for archive in archives]
    messages.extend(_validate_unpacked_app(app_root) for app_root in unpacked_app_roots)
    return messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="Flet build output directory")
    args = parser.parse_args(argv)

    try:
        messages = validate_artifact(args.artifact)
    except FletPackageValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
