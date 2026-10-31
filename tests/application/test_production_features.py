"""Tests for production-level dubbing features."""
from __future__ import annotations

import numpy as np

from aidub.application.audio.sidechain_ducker import SidechainDucker
from aidub.application.audio.auto_gain_rider import AutoGainRider
from aidub.application.audio.reverb_matcher import ReverbMatcher
from aidub.application.subtitles.subtitle_exporter import SubtitleExporter, SubCue
from aidub.application.audio.audio_mixer import AudioMixer
from aidub.application.qc.qc_report import QCReportGenerator, QCCheck
from aidub.application.adr.adr_recorder import ADRRecorder, Take
from aidub.application.lipsync.lip_sync_aligner import LipSyncAligner
from aidub.media.pro_audio_editor import AudioClipData


def test_sidechain_ducker():
    sr = 1000
    music = AudioClipData(samples=np.ones(1000, dtype=np.float32) * 0.5, sample_rate=sr)
    dlg = AudioClipData(samples=np.ones(1000, dtype=np.float32) * 0.8, sample_rate=sr)
    out = SidechainDucker().process(music, dlg)
    assert out.samples.size == 1000
    assert float(np.max(np.abs(out.samples))) <= 0.5 + 1e-6


def test_auto_gain_rider():
    clip = AudioClipData(samples=np.ones(1000, dtype=np.float32) * 0.1, sample_rate=1000)
    out = AutoGainRider(target_rms=0.2).process(clip)
    assert out.samples.size == 1000


def test_reverb_matcher():
    samples = np.exp(-np.linspace(0, 5, 5000)) * np.random.default_rng(0).standard_normal(5000)
    samples = samples.astype(np.float32)
    rt60 = ReverbMatcher.estimate_rt60(samples, 1000)
    assert rt60 >= 0.0
    assert ReverbMatcher.suggested_decay(1.5) == 1.5


def test_subtitle_exporter():
    cues = [SubCue(1, 0.0, 1.0, "hi")]
    srt = SubtitleExporter.to_srt(cues)
    assert "00:00:00,000 --> 00:00:01,000" in srt
    vtt = SubtitleExporter.to_vtt(cues)
    assert vtt.startswith("WEBVTT")


def test_audio_mixer():
    sr = 1000
    a = AudioClipData(samples=np.ones(100, dtype=np.float32) * 0.5, sample_rate=sr)
    b = AudioClipData(samples=np.ones(100, dtype=np.float32) * 0.25, sample_rate=sr)
    out = AudioMixer.mix({"a": (a, 0.0), "b": (b, -6.0)})
    assert out.samples.size == 100


def test_qc_report():
    checks = [QCCheck("lufs", True, -24.0, -24.0), QCCheck("tp", False, 0.0, -1.0)]
    rep = QCReportGenerator.generate(checks)
    assert rep["overall"] == "FAIL"
    assert rep["passed"] == 1


def test_adr_recorder():
    rec = ADRRecorder()
    rec.add_take(Take("t1", "c1", "/a.wav"))
    rec.add_take(Take("t2", "c1", "/b.wav"))
    rec.select("c1", "t2")
    sel = rec.selected_take("c1")
    assert sel.take_id == "t2"
    assert rec.take_count("c1") == 2


def test_lipsync_aligner():
    events = LipSyncAligner.align([("a", 0.0, 0.1), ("p", 0.1, 0.2)])
    assert events[0].viseme == "AA"
    assert events[1].viseme == "BMP"
    assert LipSyncAligner.phoneme_to_viseme("z") == "SZ"
