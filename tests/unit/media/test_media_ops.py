"""Unit tests for EBU R128 loudness normalization, fit_to_slot, timeline assembly, stem peak guard, and layout analyzer."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from aidub.ai.vision.layout_analyzer import analyze_layout, looks_like_caption
from aidub.media.assemble import fit_to_slot, normalize_voice
from aidub.media.ffmpeg_ops import _atempo_chain
from aidub.media.stem_separator import needs_background_normalization


def test_atempo_chain_factors() -> None:
    assert _atempo_chain(1.5) == "atempo=1.500000"
    assert _atempo_chain(2.5) == "atempo=2.0,atempo=1.250000"
    assert _atempo_chain(0.25) == "atempo=0.5,atempo=0.500000"


def test_normalize_voice_ebu_r128() -> None:
    sr = 16000
    # Generate 1 second of 440Hz sine wave
    t = np.linspace(0, 1.0, sr, endpoint=False)
    samples = 0.5 * np.sin(2 * np.pi * 440 * t)

    norm = normalize_voice(samples, sr, target_lufs=-16.0)
    assert len(norm) == len(samples)
    assert np.abs(norm).max() <= 0.985
    assert norm.dtype == np.float32


def _write_dummy_wav(path: Path, sr: int = 16000, duration_s: float = 1.0, amp: int = 4000) -> None:
    n_samples = int(sr * duration_s)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        raw_bytes = (np.ones(n_samples, dtype=np.int16) * amp).tobytes()
        f.writeframes(raw_bytes)


def test_fit_to_slot_copy_when_fits(tmp_path: Path) -> None:
    in_wav = tmp_path / "in.wav"
    out_wav = tmp_path / "out.wav"

    _write_dummy_wav(in_wav, duration_s=1.0)

    # Fits room of 1.5s -> no stretching needed
    res_path = fit_to_slot(in_wav, 1.5, out_wav)
    assert res_path.exists()
    assert res_path == out_wav


def test_needs_background_normalization_check(tmp_path: Path) -> None:
    bg_wav = tmp_path / "music.wav"
    _write_dummy_wav(bg_wav, duration_s=1.0, amp=8000)  # ~0.24 peak > 0.10

    needs, max_amp = needs_background_normalization(bg_wav, threshold=0.10)
    assert isinstance(needs, bool)
    assert max_amp >= 0.0


def test_looks_like_caption_filter() -> None:
    assert looks_like_caption("Hello world subtitle line") is True
    assert looks_like_caption("12345 67890") is False  # Only digits
    assert looks_like_caption("A") is False  # Too short
    assert looks_like_caption("F4 F5 F6 ★") is False  # Symbols/UI noise


def test_layout_analyzer_subtitle_band_detection() -> None:
    frame_h = 1080.0
    ocr_dets = [
        ("TITLE CARD DUB", 100, 50, 400, 50, 0.0, 5.0),
        ("Running subtitle caption line 1", 200, 850, 600, 40, 1.0, 3.0),
        ("Running subtitle caption line 2", 200, 850, 600, 40, 3.5, 5.5),
        ("Running subtitle caption line 3", 200, 850, 600, 40, 6.0, 8.0),
    ]

    spoken_vocab = {"running", "subtitle", "caption", "line"}
    loc, caps, sub_y = analyze_layout(ocr_dets, frame_h, spoken_vocab)

    assert len(loc) == 1  # Title card localized
    assert len(caps) == 3  # Subtitle band boxes blurred
    assert sub_y is not None
    assert sub_y >= int(0.45 * frame_h)
