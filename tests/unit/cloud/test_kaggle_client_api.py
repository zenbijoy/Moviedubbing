"""
Unit tests for direct Kaggle REST API execution (push, status, download).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidub.cloud.kaggle_accelerator import (
    KaggleClient,
    KaggleCredentials,
)


@pytest.fixture
def test_client() -> KaggleClient:
    creds = KaggleCredentials(username="testuser", key="testkey12345")
    return KaggleClient(creds)


def test_kaggle_client_push_kernel_success(test_client: KaggleClient) -> None:
    mock_resp_data = json.dumps({"url": "https://www.kaggle.com/code/testuser/aidub-feature"}).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_resp_data
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        ok, url = test_client.push_kernel(
            kernel_slug="aidub-feature",
            title="AIDub Feature",
            notebook_data={"cells": []},
            enable_gpu=True,
        )

        assert ok is True
        assert "kaggle.com/code/testuser/aidub-feature" in url
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.full_url.endswith("/kernels/push")


def test_kaggle_client_get_status_complete(test_client: KaggleClient) -> None:
    mock_resp_data = json.dumps({"status": "complete", "message": "Done"}).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_resp_data
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        status, _msg = test_client.get_kernel_status("aidub-feature")
        assert status == "complete"


def test_kaggle_client_download_output(test_client: KaggleClient, tmp_path: Path) -> None:
    dest_dir = tmp_path / "out"

    # Mock JSON response listing files
    mock_list_data = json.dumps({
        "files": [
            {"fileName": "dubbed_master.mp4", "url": "https://kaggle.com/download/dubbed_master.mp4"},
        ]
    }).encode("utf-8")

    mock_resp1 = MagicMock()
    mock_resp1.headers = {"Content-Type": "application/json"}
    mock_resp1.read.return_value = mock_list_data
    mock_resp1.__enter__.return_value = mock_resp1

    mock_file_data = b"FAKE_MP4_CONTENT"
    mock_resp2 = MagicMock()
    mock_resp2.read.return_value = mock_file_data
    mock_resp2.__enter__.return_value = mock_resp2

    with patch("urllib.request.urlopen", side_effect=[mock_resp1, mock_resp2]):
        downloaded = test_client.download_kernel_output("aidub-feature", dest_dir)
        assert len(downloaded) == 1
        assert downloaded[0].name == "dubbed_master.mp4"
        assert downloaded[0].read_bytes() == mock_file_data
