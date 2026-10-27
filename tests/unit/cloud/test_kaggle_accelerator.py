"""Unit tests for Kaggle Cloud Accelerator."""

from __future__ import annotations

import json
from pathlib import Path

from aidub.cloud.kaggle_accelerator import (
    KaggleClient,
    KaggleCredentials,
    KaggleNotebookBuilder,
    load_kaggle_credentials,
    save_kaggle_credentials,
)


def test_kaggle_credentials_validation() -> None:
    creds = KaggleCredentials("testuser", "testkey123")
    assert creds.is_valid is True
    assert "Basic " in creds.auth_header

    empty = KaggleCredentials("", "")
    assert empty.is_valid is False


def test_kaggle_save_and_load_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)

    save_kaggle_credentials("filmmaker", "kag_secret_456")
    loaded = load_kaggle_credentials()

    assert loaded is not None
    assert loaded.username == "filmmaker"
    assert loaded.key == "kag_secret_456"


def test_kaggle_notebook_builder_generates_valid_ipynb(tmp_path: Path) -> None:
    nb_file = tmp_path / "dubbing_job.ipynb"
    result = KaggleNotebookBuilder.export_to_file(
        nb_file,
        movie_filename="action_scene.mp4",
        target_language="bn",
        voice_engine="chatterbox",
        enable_lipsync=True,
    )

    assert result.is_file()
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data.get("nbformat") == 4
    assert len(data.get("cells", [])) >= 5
    # Ensure GPU accelerator flag is set
    assert data["metadata"]["kaggle"]["isGpuEnabled"] is True
    assert "nvidiaTeslaT4" in data["metadata"]["kaggle"]["accelerator"]


def test_kaggle_client_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    monkeypatch.setattr("aidub.cloud.kaggle_accelerator.load_kaggle_credentials", lambda: None)
    client = KaggleClient(creds=None)
    ok, msg = client.check_connection()
    assert ok is False
    assert "not configured" in msg
