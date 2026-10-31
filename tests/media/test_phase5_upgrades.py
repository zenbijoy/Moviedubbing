"""
Unit tests for Advanced Phase 5 Audio Processing, Subgroup Mix & Subtitle Upgrades:
  - Vectorized Audio Buffer DSP Engine & Memory Pool
  - Subgroup Bus Router & Sidechain Ducking Engine
  - 3D Spatial Audio, 5.1 Surround Gains & Binaural HRTF Panner
  - Subtitle Burn-In Video Filter & SDH Caption Tag Injector
"""

from __future__ import annotations

import numpy as np
import pytest

from aidub.media.dsp_engine import AudioBufferPool, VectorizedDspEngine
from aidub.media.mixer_bus import (
    BusKind,
    DuckingSettings,
    MasterBusRouter,
    SidechainDucker,
)
from aidub.media.spatial_audio import (
    Spatial3DPosition,
    SpatialPanner,
)
from aidub.subtitles.burnin import (
    SdhCaptionInjector,
    SdhSoundEffect,
    SubtitleBurnInConfig,
    SubtitleBurnInEngine,
)
from aidub.subtitles.qc import SubtitleCue
from aidub.ui.timeline.model import TrackId

# ── 1. Vectorized DSP Engine & Buffer Pool ────────────────────────────────────


def test_audio_buffer_pool_acquire_release() -> None:
    pool = AudioBufferPool(chunk_size=1024, max_pooled=5)
    buf1 = pool.acquire()
    assert buf1.shape == (1024,)
    assert buf1.dtype == np.float32

    buf1[0] = 0.5
    pool.release(buf1)

    # Re-acquired buffer must be zeroed out
    buf2 = pool.acquire()
    assert buf2[0] == 0.0


def test_vectorized_dsp_engine_gain_and_clipper() -> None:
    engine = VectorizedDspEngine()
    samples = np.array([0.5, -0.5, 1.2, -1.5], dtype=np.float32)

    # Apply 6dB gain (~2x amplitude)
    gained = engine.process_gain(samples, gain_db=6.0)
    assert gained[0] > 0.9

    # Soft clip values exceeding 0.95
    clipped = engine.process_soft_clipper(gained, threshold=0.95)
    assert np.all(np.abs(clipped) <= 0.95)


# ── 2. Mixer Bus Router & Sidechain Ducking ───────────────────────────────────


def test_sidechain_ducker_reduces_gain_under_dialogue() -> None:
    ducker = SidechainDucker(DuckingSettings(threshold_dbfs=-30.0, duck_reduction_db=12.0))

    # Silence (-60 dBFS) -> full gain
    gain_silent = ducker.compute_ducking_gain(-60.0)
    assert gain_silent == pytest.approx(1.0)

    # Active dialogue (-10 dBFS > -30 dBFS threshold) -> ducking gain reduction
    gain_active = ducker.compute_ducking_gain(-10.0)
    assert gain_active < 0.5  # ~-12dB reduction


def test_master_bus_router_track_destinations() -> None:
    router = MasterBusRouter()
    assert router.route_track(TrackId.A1) == BusKind.DIALOGUE_BUS
    assert router.route_track(TrackId.A2) == BusKind.DIALOGUE_BUS
    assert router.route_track(TrackId.A3) == BusKind.ME_BUS
    assert router.route_track(TrackId.A4) == BusKind.ME_BUS


# ── 3. Spatial 3D Audio & Binaural HRTF ───────────────────────────────────────


def test_spatial_panner_stereo() -> None:
    l_gain, r_gain = SpatialPanner.calculate_stereo_pan(0.0)  # center
    assert l_gain == pytest.approx(0.7071, abs=0.01)
    assert r_gain == pytest.approx(0.7071, abs=0.01)

    l_hard, r_hard = SpatialPanner.calculate_stereo_pan(-90.0)  # hard left
    assert l_hard > 0.9
    assert r_hard == pytest.approx(0.0, abs=0.01)


def test_spatial_panner_51_surround() -> None:
    pos = Spatial3DPosition(azimuth_deg=-30.0, distance_m=2.0)
    gains = SpatialPanner.calculate_surround_51(pos)
    assert gains.fl > 0.0
    assert pos.distance_gain < 1.0  # 1/2m = 0.5 distance attenuation


def test_spatial_panner_binaural_itd() -> None:
    itd_ms = SpatialPanner.calculate_binaural_itd_ms(90.0)  # hard right
    assert itd_ms > 0.5  # ~0.65ms ITD delay for 90 degrees


# ── 4. Subtitle Burn-In Filter & SDH Captions ─────────────────────────────────


def test_sdh_caption_injector() -> None:
    cue = SubtitleCue(cue_id="1", start_ms=0, end_ms=2000, text="What was that?")
    sdh_cue = SdhCaptionInjector.inject_sound_effect(cue, SdhSoundEffect.EXPLOSION)
    assert "[EXPLOSION]" in sdh_cue.text

    speaker_cue = SdhCaptionInjector.inject_speaker_label(sdh_cue, "Tony")
    assert "TONY:" in speaker_cue.text


def test_subtitle_burnin_engine_ffmpeg_filter() -> None:
    config = SubtitleBurnInConfig(ass_file_path="C:/subtitles/subs.ass")
    filter_str = SubtitleBurnInEngine.build_ffmpeg_burnin_filter(config)
    assert "subtitles=filename=" in filter_str
    assert "Fontname=" in filter_str
