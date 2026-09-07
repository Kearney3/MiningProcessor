from __future__ import annotations

from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from scripts.validate_flet_package import (
    FletPackageValidationError,
    validate_artifact,
)

MODEL_PATH = "models/maintenance_classifier.joblib"


def _create_unpacked_app(artifact, *, forbidden_root: str | None = None):
    app_root = artifact / "app"
    (app_root / "models").mkdir(parents=True)
    (app_root / MODEL_PATH).write_bytes(b"model")
    (app_root / "main.py").write_text("print('ok')", encoding="utf-8")
    if forbidden_root:
        (app_root / forbidden_root).mkdir()
    return app_root


def _create_legacy_archive(artifact):
    archive = artifact / "data" / "flutter_assets" / "app" / "app.zip"
    archive.parent.mkdir(parents=True)
    with ZipFile(archive, "w", ZIP_DEFLATED) as package:
        package.writestr(MODEL_PATH, b"model")
        package.writestr("main.py", "print('ok')")
    return archive


def test_accepts_unpacked_desktop_app(tmp_path):
    artifact = tmp_path / "build" / "windows"
    app_root = _create_unpacked_app(artifact)

    messages = validate_artifact(artifact)

    assert messages == [f"Verified unpacked Flet app: {app_root}"]


def test_accepts_legacy_app_archive(tmp_path):
    artifact = tmp_path / "build" / "windows"
    archive = _create_legacy_archive(artifact)

    messages = validate_artifact(artifact)

    assert messages == [f"Verified {archive}: 0.0 MiB"]


def test_rejects_forbidden_root_in_unpacked_desktop_app(tmp_path):
    artifact = tmp_path / "build" / "windows"
    _create_unpacked_app(artifact, forbidden_root="data")

    with pytest.raises(FletPackageValidationError, match="unexpected files"):
        validate_artifact(artifact)


def test_rejects_artifact_without_a_supported_payload(tmp_path):
    artifact = tmp_path / "build" / "windows"
    artifact.mkdir(parents=True)

    with pytest.raises(FletPackageValidationError, match="no Flet app payload"):
        validate_artifact(artifact)
