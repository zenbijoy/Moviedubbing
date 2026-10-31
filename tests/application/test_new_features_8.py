"""Tests for 8 new professional dubbing features."""
from __future__ import annotations

import numpy as np

from aidub.application.subtitles.timing_engine import SubtitleCue, SubtitleTimingEngine
from aidub.application.voice.voice_match_engine import VoiceMatchEngine
from aidub.application.audio.noise_gate import NoiseGateEngine
from aidub.application.audio.loudness_normalizer import LoudnessNormalizer
from aidub.application.audio.take_compositor import TakeCompositor
from aidub.application.video.scene_splitter import SceneSplitter
from aidub.application.batch.batch_dubber import BatchDubber, DubCue
from aidub.application.export.preset_manager import ExportPresetManager
from aidub.domain.audio_edit import CompingRegion
from aidub.media.pro_audio_editor import AudioClipData


def test_subtitle_timing():
    cues = [SubtitleCue(1.0, 2.0, "hi")]
    shifted = SubtitleTimingEngine.shift(cues, 0.5)
    assert shifted[0].start_s == 1.5
    scaled = SubtitleTimingEngine.scale(cues, 2.0)
    assert scaled[0].end_s == 4.0
    clamped = SubtitleTimingEngine.clamp([SubtitleCue(-1.0, 0.5, "x")], 0.0)
    assert clamped[0].start_s == 0.0
    mind = SubtitleTimingEngine.ensure_min_duration([SubtitleCue(0.0, 0.1, "x")], 0.5)
    assert mind[0].duration_s >= 0.5


def test_voice_match():
    res = VoiceMatchEngine.match_params(220.0, 1.0, 440.0, 1.0)
    assert abs(res["pitch_shift_semitones"] - 12.0) < 1e-6
    assert res["rate_multiplier"] == 1.0
    blended = VoiceMatchEngine.blend_params({"a": 1.0}, {"a": 3.0}, 0.5)
    assert blended["a"] == 2.0


def test_noise_gate():
    samples = np.array([0.5, 0.01, 0.6], dtype=np.float32)
    clip = AudioClipData(samples=samples, sample_rate=1000)
    gated = NoiseGateEngine(threshold_dbfs=-20.0).gate(clip)
    assert gated.samples[1] == 0.0
    assert gated.samples[0] != 0.0
    floor = NoiseGateEngine.estimate_noise_floor(clip)
    assert isinstance(floor, float)


def test_loudness_normalizer():
    samples = np.ones(100, dtype=np.float32) * 0.25
    clip = AudioClipData(samples=samples, sample_rate=1000)
    norm = LoudnessNormalizer.normalize_peak(clip, -6.0)
    peak = float(np.max(np.abs(norm.samples)))
    assert abs(20 * np.log10(peak) - (-6.0)) < 0.5
    rmsn = LoudnessNormalizer.normalize_rms(clip, -20.0)
    assert rmsn.samples.size == 100
    assert isinstance(LoudnessNormalizer.current_peak_dbfs(clip), float)


def test_take_compositor():
    sr = 1000
    clip = AudioClipData(samples=np.ones(2000, dtype=np.float32) * 0.5, sample_rate=sr)
    regions = [CompingRegion(take_id="t1", cue_id="c", start_s=0.0, end_s=1.0, gain_db=0.0)]
    master = TakeCompositor.build_master(regions, {"t1": clip}, sr=sr)
    assert master.samples.size == 1000
    assert TakeCompositor.total_duration(regions) == 1.0


def test_scene_splitter():
    sr = 1000
    # 1s tone, 0.6s silence, 1s tone
    tone = np.ones(1000, dtype=np.float32) * 0.5
    silence = np.zeros(600, dtype=np.float32)
    samples = np.concatenate([tone, silence, tone]).astype(np.float32)
    clip = AudioClipData(samples=samples, sample_rate=sr)
    segs = SceneSplitter(silence_threshold_dbfs=-40.0, min_silence_s=0.5, min_scene_s=0.1).split(clip)
    assert len(segs) == 2


def test_batch_dubber():
    def synth(cue):
        if cue.cue_id == "bad":
            raise RuntimeError("fail")
        return f"/tmp/{cue.cue_id}.wav"
    dubber = BatchDubber(synth)
    cues = [DubCue("a", "hi"), DubCue("bad", "x")]
    res = dubber.run(cues)
    assert BatchDubber.success_count(res) == 1
    assert len(BatchDubber.failed(res)) == 1


def test_export_preset_manager():
    mgr = ExportPresetManager()
    assert "netflix" in mgr.list_keys()
    p = mgr.get("youtube")
    assert p.audio_codec == "aac"
    mgr.add("custom", p)
    assert "custom" in mgr.list_keys()
    assert len(mgr.for_loudness(-14.0)) >= 1
    mgr.remove("custom")
    assert "custom" not in mgr.list_keys()
