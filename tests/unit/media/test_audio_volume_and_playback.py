"""Regression tests for audio loudness, mixing quality, and playback audibility."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from aidub.media.assemble import fit_to_slot, normalize_voice
from aidub.media.ffmpeg_ops import mix, mux, probe


def test_normalize_voice_loudness() -> None:
    # Create 1 second of soft sine wave (peak ~0.10)
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    soft_signal = 0.10 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

    normalized = normalize_voice(soft_signal, sr, target_lufs=-14.0, target_rms_db=-14.0)
    max_amp = float(np.max(np.abs(normalized)))
    # Gain should boost the soft signal by ~10dB towards broadcast dialogue levels (-14 LUFS)
    assert max_amp > 0.25, f"Expected boosted amplitude > 0.25, got {max_amp}"
    assert max_amp <= 0.99, f"Peak limit exceeded: {max_amp}"


def test_fit_to_slot_resampling(tmp_path: Path) -> None:
    # Create a 24000Hz WAV (typical Edge-TTS output)
    src_24k = tmp_path / "src_24k.wav"
    t = np.linspace(0, 1.0, 24000, endpoint=False)
    sig = (0.5 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    sf.write(str(src_24k), sig, 24000)

    # Fit to 0.8s slot (triggers time_stretch)
    fitted = tmp_path / "fitted.wav"
    fit_to_slot(src_24k, 0.8, fitted)

    assert fitted.is_file()
    data, sr = sf.read(str(fitted))
    assert sr == 44100, f"Expected 44100Hz output, got {sr}"
    assert data.ndim == 1, "Expected mono output"


def test_mix_preserves_dialogue_loudness(tmp_path: Path) -> None:
    sr = 44100
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    # Vocal track: 440Hz tone with peak 0.85
    vocals_path = tmp_path / "vocals.wav"
    vocals_data = (0.85 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(vocals_path), vocals_data, sr)

    # Background music: 220Hz stereo tone with peak 0.20
    music_path = tmp_path / "music.wav"
    music_data = np.column_stack(
        [
            0.20 * np.sin(2 * np.pi * 220 * t),
            0.20 * np.sin(2 * np.pi * 220 * t),
        ]
    ).astype(np.float32)
    sf.write(str(music_path), music_data, sr)

    # Mix to WAV
    out_wav = tmp_path / "mixed.wav"
    mix(vocals_path, music_path, out_wav, music_gain=0.30)
    assert out_wav.is_file()

    mixed_data, mixed_sr = sf.read(str(out_wav))
    assert mixed_sr == 44100
    assert mixed_data.ndim == 2, "Expected stereo mixed output"
    max_amp = float(np.max(np.abs(mixed_data)))
    # Vocals must not be halved into inaudibility; limiter preserves punch
    assert max_amp > 0.70, f"Expected mixed peak > 0.70, got {max_amp}"
    assert max_amp <= 1.0, f"Clipping detected: {max_amp}"

    # Mix to M4A
    out_m4a = tmp_path / "mixed.m4a"
    mix(vocals_path, music_path, out_m4a, music_gain=0.30)
    assert out_m4a.is_file()
    meta = probe(out_m4a)
    audio_stream = next(s for s in meta["streams"] if s["codec_type"] == "audio")
    assert audio_stream["codec_name"] == "aac"
    assert audio_stream["channels"] == 2


def test_mux_generates_audible_faststart_video(tmp_path: Path) -> None:
    import subprocess

    from aidub.media.ffmpeg_ops import _ffmpeg_exe

    ffmpeg = _ffmpeg_exe()
    sr = 44100
    dur = 2.0

    # Synthetic test video: 2-second silent lavfi mp4
    video_path = tmp_path / "test_video.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=320x240:rate=24:duration={dur}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )

    # Audio track with clear tone
    audio_path = tmp_path / "loud_audio.wav"
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    audio_data = np.column_stack(
        [
            0.80 * np.sin(2 * np.pi * 440 * t),
            0.80 * np.sin(2 * np.pi * 440 * t),
        ]
    ).astype(np.float32)
    sf.write(str(audio_path), audio_data, sr)

    out_mp4 = tmp_path / "muxed_master.mp4"
    mux(video_path, audio_path, out_mp4)

    assert out_mp4.is_file()
    meta = probe(out_mp4)
    audio_stream = next(s for s in meta["streams"] if s["codec_type"] == "audio")
    assert audio_stream["codec_name"] == "aac"
    assert audio_stream["channels"] == 2
    assert int(audio_stream["sample_rate"]) == 44100

    # Extract audio and verify audibility
    extracted_wav = tmp_path / "extracted.wav"
    subprocess.run(
        [ffmpeg, "-y", "-i", str(out_mp4), "-vn", "-c:a", "pcm_s16le", str(extracted_wav)],
        check=True,
        capture_output=True,
    )
    d, _ = sf.read(str(extracted_wav))
    max_extracted = float(np.max(np.abs(d)))
    assert max_extracted > 0.65, f"Muxed audio is too quiet: peak={max_extracted}"
