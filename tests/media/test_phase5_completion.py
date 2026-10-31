"""
Unit tests for Phase 5 completion:
  - Task 5.2: Acoustic Scene Matching, RT60 Estimation & Room Impulse Presets
  - Task 5.4: Subtitle Multi-Format Exporter (SRT, WebVTT, ASS)
"""

from __future__ import annotations

from aidub.media.acoustic_matcher import (
    AcousticMatcher,
    RoomPreset,
)
from aidub.subtitles.export import SubtitleExporter
from aidub.subtitles.qc import SubtitleCue

# ── Task 5.2: Acoustic Scene Matcher Tests ────────────────────────────────────


def test_acoustic_matcher_preset_profiles() -> None:
    for preset in RoomPreset:
        profile = AcousticMatcher.profile_from_preset("scn_001", preset)
        assert profile.preset == preset
        assert profile.noise_floor_dbfs < 0.0
        assert profile.rt60_seconds > 0.0


def test_acoustic_matcher_large_hall_reverb_filter() -> None:
    profile = AcousticMatcher.profile_from_preset("scn_hall", RoomPreset.LARGE_HALL)
    ffmpeg_filter = AcousticMatcher.to_ffmpeg_reverb_filter(profile)
    assert "aecho" in ffmpeg_filter


def test_acoustic_matcher_telephone_radio_filter() -> None:
    profile = AcousticMatcher.profile_from_preset("scn_phone", RoomPreset.TELEPHONE_RADIO)
    ffmpeg_filter = AcousticMatcher.to_ffmpeg_reverb_filter(profile)
    assert "highpass=f=300" in ffmpeg_filter
    assert "lowpass=f=3400" in ffmpeg_filter


# ── Task 5.4: Subtitle Exporter Tests ─────────────────────────────────────────


def test_subtitle_exporter_srt() -> None:
    cues = [
        SubtitleCue(cue_id="1", start_ms=1000, end_ms=3500, text="Hello world"),
        SubtitleCue(cue_id="2", start_ms=4000, end_ms=6000, text="Second subtitle line"),
    ]
    srt = SubtitleExporter.export_srt(cues)
    assert "1" in srt
    assert "00:00:01,000 --> 00:00:03,500" in srt
    assert "Hello world" in srt


def test_subtitle_exporter_webvtt() -> None:
    cues = [
        SubtitleCue(cue_id="1", start_ms=500, end_ms=2500, text="WebVTT test line"),
    ]
    vtt = SubtitleExporter.export_webvtt(cues)
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.500 --> 00:00:02.500" in vtt


def test_subtitle_exporter_ass() -> None:
    cues = [
        SubtitleCue(cue_id="1", start_ms=1200, end_ms=4800, text="First line\nSecond line"),
    ]
    ass = SubtitleExporter.export_ass(cues, title="Movie Dubbing ASS")
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "Dialogue: 0,0:00:01.20,0:00:04.80,Default,,0,0,0,,First line\\NSecond line" in ass
