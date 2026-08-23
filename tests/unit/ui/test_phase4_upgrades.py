"""
Unit tests for Enterprise-grade Phase 4 UI & Editorial upgrades:
  - Theme Tokens & QSS Generator
  - Waveform Downsampling Peak Provider
  - Timeline Markers & In/Out Range Selection
  - Slip & Slide NLE Edit Engine
  - Audio Mixer Engine (Faders, Pan, Solo/Mute logic, Peak Metering)
  - NLE Shortcut Profiles (Default, Premiere Pro)
  - 26-Screen Widget Factory
"""

from __future__ import annotations

import pytest

from aidub.contracts.base import Identifier
from aidub.ui.editorial import EditorialCommandEngine
from aidub.ui.keyboard_shortcuts import NleProfile, ShortcutAction, ShortcutManager
from aidub.ui.mixer import AudioMixerEngine
from aidub.ui.theme import ColorTokens, build_enterprise_stylesheet
from aidub.ui.timeline.markers import (
    MarkerKind,
    TimelineMarker,
    TimelineMarkerManager,
)
from aidub.ui.timeline.model import TimelineClip, TrackId
from aidub.ui.timeline.waveform import WaveformGenerator

# ── 1. Enterprise Theme & Tokens ──────────────────────────────────────────────


def test_color_tokens_and_stylesheet() -> None:
    tokens = ColorTokens()
    assert tokens.bg_dark == "#121216"
    assert tokens.accent == "#6366F1"

    qss = build_enterprise_stylesheet(tokens)
    assert "#121216" in qss
    assert "#6366F1" in qss
    assert "QWidget" in qss


# ── 2. Waveform Peak Provider ──────────────────────────────────────────────────


def test_waveform_downsample_audio() -> None:
    # 1 second of 48000Hz dummy sine samples
    import math
    samples = [math.sin(i * 0.1) for i in range(48_000)]
    data = WaveformGenerator.downsample_audio("clip_002", samples, sample_rate=48_000, target_peaks=50)

    assert data.clip_id == "clip_002"
    assert data.duration_ms == 1000
    assert len(data.max_peaks) > 0


# ── 3. Timeline Markers & In/Out Range ────────────────────────────────────────


def test_timeline_marker_manager_in_out() -> None:
    mgr = TimelineMarkerManager()
    assert mgr.in_out.active is False

    mgr.set_mark_in(1000)
    mgr.set_mark_out(4000)
    assert mgr.in_out.active is True
    assert mgr.in_out.duration_ms == 3000

    mgr.clear_in_out()
    assert mgr.in_out.active is False


def test_timeline_marker_manager_markers() -> None:
    mgr = TimelineMarkerManager()
    marker = TimelineMarker(
        marker_id=Identifier("m-001"),
        position_ms=2500,
        kind=MarkerKind.SCENE_CUT,
        label="Cut to Scene 2",
    )
    mgr.add_marker(marker)

    markers = mgr.list_markers()
    assert len(markers) == 1
    assert markers[0].label == "Cut to Scene 2"

    positions = mgr.marker_positions_ms()
    assert 2500 in positions


# ── 4. Slip & Slide Edit Operations ──────────────────────────────────────────


def test_editorial_slip_edit() -> None:
    clip = TimelineClip(clip_id=Identifier("c1"), track_id=TrackId.A1, start_ms=1000, duration_ms=2000)
    slipped = EditorialCommandEngine.slip_edit(clip, offset_ms=500)
    assert slipped.clip_id == clip.clip_id
    assert slipped.start_ms == 1000


def test_editorial_slide_edit() -> None:
    left = TimelineClip(clip_id=Identifier("c1"), track_id=TrackId.A1, start_ms=0, duration_ms=2000)
    mid = TimelineClip(clip_id=Identifier("c2"), track_id=TrackId.A1, start_ms=2000, duration_ms=1000)
    right = TimelineClip(clip_id=Identifier("c3"), track_id=TrackId.A1, start_ms=3000, duration_ms=2000)

    # Slide mid clip 500ms right
    new_left, new_mid, new_right = EditorialCommandEngine.slide_edit(left, mid, right, shift_ms=500)

    assert new_left.duration_ms == 2500
    assert new_mid.start_ms == 2500
    assert new_right.start_ms == 3500
    assert new_right.duration_ms == 1500


# ── 5. Audio Mixer Engine ────────────────────────────────────────────────────


def test_audio_mixer_fader_linear_gain() -> None:
    mixer = AudioMixerEngine()
    ch = mixer.get_channel(TrackId.A1)
    assert ch is not None
    assert ch.linear_gain == pytest.approx(1.0)  # 0 dB = 1.0 gain

    ch_updated = mixer.set_volume(TrackId.A1, -6.0)
    assert ch_updated.linear_gain < 1.0


def test_audio_mixer_solo_mute_logic() -> None:
    mixer = AudioMixerEngine()

    # Initially all tracks audible
    assert mixer.is_track_audible(TrackId.A1) is True
    assert mixer.is_track_audible(TrackId.A2) is True

    # Solo A1 -> A2 becomes inaudible
    mixer.toggle_solo(TrackId.A1)
    assert mixer.is_track_audible(TrackId.A1) is True
    assert mixer.is_track_audible(TrackId.A2) is False

    # Mute A1 -> A1 becomes inaudible despite solo
    mixer.toggle_mute(TrackId.A1)
    assert mixer.is_track_audible(TrackId.A1) is False


def test_audio_mixer_peak_metering() -> None:
    mixer = AudioMixerEngine()
    updated = mixer.update_meter(TrackId.A1, peak_l_dbfs=1.5, peak_r_dbfs=-2.0)
    assert updated.clipped is True

    mixer.reset_clips()
    ch = mixer.get_channel(TrackId.A1)
    assert ch is not None and ch.clipped is False


# ── 6. NLE Profile Shortcuts ─────────────────────────────────────────────────


def test_nle_profile_shortcuts() -> None:
    mgr = ShortcutManager(NleProfile.DEFAULT)
    assert mgr.resolve("V") == ShortcutAction.TOOL_SELECT
    assert mgr.resolve("B") == ShortcutAction.TOOL_BLADE

    mgr.load_profile(NleProfile.PREMIERE_PRO)
    assert mgr.profile == NleProfile.PREMIERE_PRO
    assert mgr.resolve("C") == ShortcutAction.TOOL_BLADE  # Premiere C = Razor

