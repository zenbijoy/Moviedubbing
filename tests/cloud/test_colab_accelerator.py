"""Unit tests for Google Colab Free GPU Cloud Accelerator."""

from __future__ import annotations

import json
from pathlib import Path

from aidub.cloud.colab_accelerator import ColabNotebookBuilder


def test_create_colab_notebook_structure():
    nb = ColabNotebookBuilder.create_colab_notebook(
        movie_filename="iron_man.mp4",
        target_language="bn",
        voice_engine="chatterbox",
        enable_lipsync=True,
    )

    assert nb["nbformat"] == 4
    assert nb["metadata"]["accelerator"] == "GPU"
    assert nb["metadata"]["colab"]["gpuType"] == "T4"

    cells = nb["cells"]
    assert len(cells) >= 5

    # Check for faster-whisper and demucs install command
    install_cell = next(
        c for c in cells if any("faster-whisper" in line for line in c.get("source", []))
    )
    assert install_cell is not None

    # Check for target language configuration
    exec_cell = next(
        c for c in cells if any("tgt_lang = 'bn'" in line for line in c.get("source", []))
    )
    assert exec_cell is not None


def test_export_colab_notebook_to_file(tmp_path: Path):
    dest = tmp_path / "colab_test.ipynb"
    exported = ColabNotebookBuilder.export_to_file(
        dest,
        movie_filename="action_scene.mp4",
        target_language="bn",
    )

    assert exported.is_file()
    content = json.loads(exported.read_text(encoding="utf-8"))
    assert content["nbformat"] == 4
    assert len(content["cells"]) >= 5
