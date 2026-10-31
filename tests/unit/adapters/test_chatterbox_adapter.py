"""Unit tests for ChatterboxAdapter and ChatterboxVoiceEngine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidub.adapters.voice.chatterbox_adapter import (
    ChatterboxAdapter,
    ChatterboxVoiceEngine,
)
from aidub.adapters.voice_base import (
    SynthesisRequest,
    VoiceEngineError,
    VoiceEngineKind,
)
from aidub.contracts.base import Identifier
from aidub.pipeline.config import PipelineConfig


# Minimal valid WAV header for mock audio tests
_TINY_WAV = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"\x80\xbb\x00\x00\x00w\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


def test_chatterbox_adapter_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    # Direct URL
    adapter1 = ChatterboxAdapter(server_url="https://test-kaggle.trycloudflare.com")
    assert adapter1.server_url == "https://test-kaggle.trycloudflare.com"
    assert adapter1.is_remote is True

    # From environment variable
    monkeypatch.setenv("KAGGLE_CHATTERBOX_URL", "https://env-kaggle.trycloudflare.com")
    adapter2 = ChatterboxAdapter()
    assert adapter2.server_url == "https://env-kaggle.trycloudflare.com"
    assert adapter2.is_remote is True

    # Trailing slash stripping
    adapter3 = ChatterboxAdapter(server_url="https://slash.test/")
    assert adapter3.server_url == "https://slash.test"


def test_chatterbox_adapter_health_check_success() -> None:
    adapter = ChatterboxAdapter(server_url="https://mock-server.com")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "ok",
        "model": "bangla-chatterbox",
        "device": "cuda:0",
        "vram_free_gb": 14.2,
    }
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        health = adapter.check_health()
        assert health["status"] == "ok"
        assert health["model"] == "bangla-chatterbox"
        mock_get.assert_called_once_with("https://mock-server.com/health")


def test_chatterbox_adapter_health_check_offline() -> None:
    adapter = ChatterboxAdapter(server_url="https://unreachable-server.com")
    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        with pytest.raises(VoiceEngineError, match="Failed to connect to Chatterbox server"):
            adapter.check_health()


def test_chatterbox_adapter_health_check_no_url() -> None:
    adapter = ChatterboxAdapter()
    with pytest.raises(VoiceEngineError, match="No remote server URL"):
        adapter.check_health()


def test_chatterbox_adapter_empty_text_raises(tmp_path: Path) -> None:
    adapter = ChatterboxAdapter(server_url="https://mock-server.com")
    with pytest.raises(ValueError, match="cannot be empty"):
        adapter.synthesize_to_file("   ", tmp_path / "out.wav")


def test_chatterbox_adapter_upload_reference(tmp_path: Path) -> None:
    ref_wav = tmp_path / "ref.wav"
    ref_wav.write_bytes(_TINY_WAV)

    adapter = ChatterboxAdapter(server_url="https://mock-server.com")
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        # First upload
        ok1 = adapter.upload_speaker_reference(speaker_id=0, reference_audio_path=ref_wav)
        assert ok1 is True
        assert mock_post.call_count == 1
        assert "0" in adapter._cached_speakers

        # Second call for same speaker should use cache without HTTP request
        ok2 = adapter.upload_speaker_reference(speaker_id=0, reference_audio_path=ref_wav)
        assert ok2 is True
        assert mock_post.call_count == 1  # Not incremented!


def test_chatterbox_adapter_remote_synthesize(tmp_path: Path) -> None:
    ref_wav = tmp_path / "ref.wav"
    ref_wav.write_bytes(_TINY_WAV)
    out_wav = tmp_path / "dubbed_seg.wav"

    adapter = ChatterboxAdapter(server_url="https://mock-server.com")
    mock_resp = MagicMock()
    mock_resp.content = _TINY_WAV
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res_path = adapter.synthesize_to_file(
            text="আমার নাম রবার্ট।",
            output_wav_path=out_wav,
            reference_audio_path=ref_wav,
            speaker_id="spk_0",
            language="bn",
        )
        assert res_path.exists()
        assert res_path.read_bytes() == _TINY_WAV
        assert mock_post.call_count == 1


def test_chatterbox_voice_engine_interface(tmp_path: Path) -> None:
    mock_adapter = MagicMock(spec=ChatterboxAdapter)

    def _mock_synth(text: str, output_wav_path: Path, **kwargs: object) -> Path:
        Path(output_wav_path).write_bytes(_TINY_WAV)
        return Path(output_wav_path)

    mock_adapter.synthesize_to_file.side_effect = _mock_synth

    engine = ChatterboxVoiceEngine(adapter=mock_adapter)
    assert engine.engine_kind == VoiceEngineKind.CHATTERBOX

    req = SynthesisRequest(
        request_id=Identifier("req-001"),
        utterance_id=Identifier("utt-001"),
        voice_profile_id=Identifier("vp-001"),
        text="বাংলা ডাবিং টেস্ট।",
        language="bn-BD",
        seed=123,
    )

    with patch("aidub.adapters.voice.chatterbox_adapter._run"), \
         patch("aidub.adapters.voice.chatterbox_adapter.duration", return_value=1.5):
        # We need the final wav to exist for duration/return
        res = engine.synthesize(req, str(tmp_path))
        assert res.engine_kind == VoiceEngineKind.CHATTERBOX
        assert res.utterance_id == "utt-001"
        assert res.seed_used == 123
        assert res.duration_ms == 1500


def test_pipeline_config_with_chatterbox_url(tmp_path: Path) -> None:
    cfg = PipelineConfig(
        input=tmp_path / "in.mp4",
        output=tmp_path / "out.mp4",
        chatterbox_url="https://kaggle-test.trycloudflare.com",
    )
    # Should automatically set tts_engine to "chatterbox" when URL is given
    assert cfg.tts_engine == "chatterbox"
    assert cfg.chatterbox_url == "https://kaggle-test.trycloudflare.com"

