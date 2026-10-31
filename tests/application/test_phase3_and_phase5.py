"""
Comprehensive tests for Tasks 3.2–3.5 and Phase 5 (5.1, 5.3, 5.4):
  - Voice Rights & Authorization Ledger
  - Utterance Performance & Prosody Controls
  - Bounded Timing Fitter
  - Voice Take Versioning & A/B Comparison
  - Audio DSP Chain
  - Loudness Normalization & True-Peak Mastering
  - Subtitle QC Engine
"""

from __future__ import annotations

import pytest

from aidub.application.performance_service import (
    PerformanceEdit,
    PerformanceService,
    VocalizationKind,
    VocalizationMarker,
)
from aidub.application.take_manager import TakeManager, TakeStatus, VoiceTake
from aidub.application.timing_fitter import FitStrategy, TimingFitter, TimingFitterConfig
from aidub.application.voice_rights_service import LedgerEventKind, VoiceRightsService
from aidub.contracts.base import Identifier
from aidub.domain.base import RightsViolation, utc_now
from aidub.domain.identifiers import ConsentRecordId, ProjectId, VoiceProfileId
from aidub.domain.rights import (
    ConsentRecord,
    ConsentStatus,
    VoiceOrigin,
    VoiceProfile,
    VoiceUse,
)
from aidub.domain.time import TimeRange
from aidub.domain.utterance import Utterance, UtteranceStatus
from aidub.media.audio_chain import AudioDspChain, DspPreset, EqBand, ParametricEq
from aidub.media.loudness_mastering import (
    LoudnessMasteringBus,
    LoudnessMeasurement,
    LoudnessNormalizationConfig,
    LoudnessStandard,
)
from aidub.subtitles.qc import (
    QcViolationKind,
    SubtitleCue,
    SubtitleQcConfig,
    SubtitleQcEngine,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _time_range(start_s: float = 0.0, end_s: float = 2.0) -> TimeRange:
    from aidub.domain.time import RationalRate, RationalTime

    rate = RationalRate(numerator=1_000)
    return TimeRange.from_start_end(
        RationalTime(ticks=int(start_s * 1_000), rate=rate),
        RationalTime(ticks=int(end_s * 1_000), rate=rate),
    )


def _utterance(uid: str = "utt_001") -> Utterance:
    return Utterance(
        utterance_id=Identifier(uid),
        project_id=Identifier("prj_001"),
        source_range=_time_range(0.0, 2.5),
        edit_range=_time_range(0.0, 2.5),
        source_text="Hello, how are you?",
        source_language="en-US",
        confidence=0.95,
    )


def _granted_consent(project_id: str = "prj_001") -> ConsentRecord:
    return ConsentRecord(
        consent_record_id=ConsentRecordId("cns_001"),
        project_id=ProjectId(project_id),
        subject="Jane Actor",
        rights_owner="Studio Corp",
        status=ConsentStatus.GRANTED,
        evidence_reference="CONTRACT-2024-001",
        permitted_uses=frozenset({VoiceUse.DUBBING, VoiceUse.PREVIEW}),
        languages=frozenset({"en-US", "bn-BD"}),
        territories=frozenset({"WORLDWIDE"}),
        approved_by="legal@studio.com",
        approved_at=utc_now(),
    )


def _voice_profile(origin: VoiceOrigin = VoiceOrigin.REFERENCE_CONDITIONED) -> VoiceProfile:
    return VoiceProfile(
        voice_profile_id=VoiceProfileId("vcp_001"),
        project_id=ProjectId("prj_001"),
        display_name="Jane Dub Voice",
        origin=origin,
        engine_id="f5-tts",
        engine_voice_key="jane_ref_v1",
        supported_languages=frozenset({"en-US", "bn-BD"}),
        consent_record_id=ConsentRecordId("cns_001"),
    )


# ── Task 3.2: Voice Rights ────────────────────────────────────────────────────


def test_voice_rights_authorize_success() -> None:
    svc = VoiceRightsService()
    consent = _granted_consent()
    profile = _voice_profile()
    svc.register_consent(consent)
    svc.register_profile(profile)

    result = svc.authorize(
        voice_profile_id="vcp_001",
        project_id="prj_001",
        language="en-US",
        territory="WORLDWIDE",
        use=VoiceUse.DUBBING,
    )

    assert result.voice_profile_id == "vcp_001"
    events = svc.ledger()
    kinds = [e.event_kind for e in events]
    assert LedgerEventKind.CONSENT_REGISTERED in kinds
    assert LedgerEventKind.PROFILE_REGISTERED in kinds
    assert LedgerEventKind.VOICE_AUTHORIZED in kinds


def test_voice_rights_blocks_unregistered_profile() -> None:
    svc = VoiceRightsService()

    with pytest.raises(RightsViolation):
        svc.authorize(
            voice_profile_id="vcp_unknown",
            project_id="prj_001",
            language="en-US",
            territory="WORLDWIDE",
            use=VoiceUse.DUBBING,
        )

    events = svc.ledger()
    assert any(e.event_kind == LedgerEventKind.VOICE_BLOCKED for e in events)


def test_voice_rights_blocks_wrong_language() -> None:
    svc = VoiceRightsService()
    consent = _granted_consent()
    profile = _voice_profile()
    svc.register_consent(consent)
    svc.register_profile(profile)

    with pytest.raises(RightsViolation):
        svc.authorize(
            voice_profile_id="vcp_001",
            project_id="prj_001",
            language="fr-FR",  # not in consent languages
            territory="WORLDWIDE",
            use=VoiceUse.DUBBING,
        )

    events = svc.ledger_for_profile("vcp_001")
    assert any(e.event_kind == LedgerEventKind.VOICE_BLOCKED for e in events)


def test_voice_rights_ledger_is_append_only() -> None:
    svc = VoiceRightsService()
    _profile = _voice_profile(VoiceOrigin.SYNTHETIC_STOCK)
    profile_stock = VoiceProfile(
        voice_profile_id=VoiceProfileId("vcp_stock"),
        project_id=ProjectId("prj_001"),
        display_name="Stock Voice",
        origin=VoiceOrigin.SYNTHETIC_STOCK,
        engine_id="tts",
        engine_voice_key="stock_v1",
        supported_languages=frozenset({"*"}),
    )
    svc.register_profile(profile_stock)
    svc.authorize(
        voice_profile_id="vcp_stock",
        project_id="prj_001",
        language="en-US",
        territory="WORLDWIDE",
        use=VoiceUse.DUBBING,
    )
    snapshot1 = len(svc.ledger())

    # Authorize again — ledger grows, never shrinks
    svc.authorize(
        voice_profile_id="vcp_stock",
        project_id="prj_001",
        language="bn-BD",
        territory="WORLDWIDE",
        use=VoiceUse.PREVIEW,
    )
    assert len(svc.ledger()) > snapshot1


# ── Task 3.3: Performance & Prosody ──────────────────────────────────────────


def test_performance_apply_emotion() -> None:
    svc = PerformanceService()
    utt = _utterance()
    edit = PerformanceEdit(
        utterance_id=Identifier("utt_001"),
        emotion_label="angry",
        emotion_intensity=0.85,
        pace_rate=1.1,
        pitch_semitones=0.0,
        energy=1.3,
    )
    updated = svc.apply_performance(utt, edit)

    assert updated.emotion is not None
    assert updated.emotion.label == "angry"
    assert updated.emotion.intensity == pytest.approx(0.85)
    assert updated.prosody is not None
    assert updated.prosody.rate == pytest.approx(1.1)
    assert updated.revision == 1


def test_performance_locked_utterance_raises() -> None:
    svc = PerformanceService()
    utt = _utterance().model_copy(update={"status": UtteranceStatus.LOCKED})
    edit = PerformanceEdit(utterance_id=Identifier("utt_001"))

    with pytest.raises(ValueError, match="LOCKED"):
        svc.apply_performance(utt, edit)


def test_performance_vocalization_markers() -> None:
    svc = PerformanceService()
    marker = VocalizationMarker(
        utterance_id=Identifier("utt_001"),
        kind=VocalizationKind.SIGH,
        position_ms=500,
        intensity=0.7,
    )
    svc.add_vocalization(marker)

    vocs = svc.get_vocalizations("utt_001")
    assert len(vocs) == 1
    assert vocs[0].kind == VocalizationKind.SIGH


def test_performance_build_synthesis_overrides() -> None:
    svc = PerformanceService()
    utt = _utterance()
    edit = PerformanceEdit(
        utterance_id=Identifier("utt_001"),
        emotion_label="whisper",
        emotion_intensity=0.9,
        pace_rate=0.9,
        pitch_semitones=-2.0,
        energy=0.5,
    )
    updated = svc.apply_performance(utt, edit)
    overrides = svc.build_synthesis_overrides(updated)

    assert overrides["emotion"] == "whisper"
    assert overrides["emotion_intensity"] == pytest.approx(0.9)
    assert overrides["pace_multiplier"] == pytest.approx(0.9)
    assert overrides["pitch_shift_semitones"] == pytest.approx(-2.0)


def test_performance_reset_to_neutral() -> None:
    svc = PerformanceService()
    utt = _utterance()
    edit = PerformanceEdit(
        utterance_id=Identifier("utt_001"),
        emotion_label="angry",
        emotion_intensity=1.0,
    )
    updated = svc.apply_performance(utt, edit)
    reset = svc.reset_performance(updated)

    assert reset.emotion is None
    assert reset.prosody is None
    assert reset.revision == 2


# ── Task 3.4: Timing Fitter ───────────────────────────────────────────────────


def test_timing_fitter_exact_fit() -> None:
    fitter = TimingFitter()
    result = fitter.fit(utterance_id="utt-001", synthesized_ms=2_500, slot_ms=2_520)
    assert result.strategy_used == FitStrategy.EXACT_FIT
    assert result.within_tolerance is True
    assert result.flagged_for_review is False


def test_timing_fitter_silence_trim() -> None:
    fitter = TimingFitter(TimingFitterConfig(silence_trim_max_ms=300, tolerance_ms=50))
    # take is 200ms too long, but there's 200ms trailing silence to trim
    result = fitter.fit(
        utterance_id="utt-002",
        synthesized_ms=3_000,
        slot_ms=2_800,
        trailing_silence_ms=200,
    )
    assert result.strategy_used == FitStrategy.SILENCE_TRIM
    assert result.within_tolerance is True
    assert result.silence_trimmed_ms == 200


def test_timing_fitter_rate_control() -> None:
    fitter = TimingFitter(TimingFitterConfig(tolerance_ms=50))
    # 3000ms take into 2900ms slot — 3.4% compression after rate: within range
    result = fitter.fit(utterance_id="utt-003", synthesized_ms=3_000, slot_ms=2_900)
    assert result.strategy_used in (
        FitStrategy.RATE_CONTROL,
        FitStrategy.TIME_STRETCH,
        FitStrategy.EXACT_FIT,
    )
    assert result.within_tolerance or result.strategy_used in (
        FitStrategy.RATE_CONTROL,
        FitStrategy.TIME_STRETCH,
    )


def test_timing_fitter_time_stretch_within_bounds() -> None:
    cfg = TimingFitterConfig(
        max_stretch_pct=0.08,
        rate_control_min=1.0,  # Disable rate control
        rate_control_max=1.0,
        silence_trim_max_ms=0,
        tolerance_ms=10,
    )
    fitter = TimingFitter(cfg)
    # 3000ms take into 3200ms slot — 6.7% stretch (under 8% limit)
    result = fitter.fit(utterance_id="utt-004", synthesized_ms=3_000, slot_ms=3_200)
    assert result.strategy_used in (
        FitStrategy.TIME_STRETCH,
        FitStrategy.EXACT_FIT,
        FitStrategy.RATE_CONTROL,
    )


def test_timing_fitter_flags_for_review_when_over_limit() -> None:
    cfg = TimingFitterConfig(
        max_stretch_pct=0.08,
        rate_control_min=1.0,
        rate_control_max=1.0,
        silence_trim_max_ms=0,
        tolerance_ms=10,
    )
    fitter = TimingFitter(cfg)
    # 3000ms take into 4500ms slot — 50% gap — impossible without LLM rewrite
    result = fitter.fit(utterance_id="utt-005", synthesized_ms=3_000, slot_ms=4_500)
    assert result.flagged_for_review is True
    assert result.strategy_used == FitStrategy.HUMAN_REVIEW


# ── Task 3.5: Take Manager ───────────────────────────────────────────────────


def _make_take(uid: str, take_num: int, take_id: str | None = None) -> VoiceTake:
    return VoiceTake(
        take_id=Identifier(take_id or f"take-{take_num:03d}"),
        utterance_id=Identifier(uid),
        take_number=take_num,
        audio_path=f"/takes/{uid}/take_{take_num}.wav",
        engine_kind="synthetic",
        seed=take_num * 10,
        duration_ms=2_000 + take_num * 100,
    )


def test_take_manager_add_and_list() -> None:
    mgr = TakeManager()
    mgr.add_take(_make_take("utt-001", 1))
    mgr.add_take(_make_take("utt-001", 2))
    mgr.add_take(_make_take("utt-001", 3))

    takes = mgr.list_takes("utt-001")
    assert len(takes) == 3
    assert [t.take_number for t in takes] == [1, 2, 3]


def test_take_manager_set_master() -> None:
    mgr = TakeManager()
    mgr.add_take(_make_take("utt-001", 1, "take-001"))
    mgr.add_take(_make_take("utt-001", 2, "take-002"))
    mgr.add_take(_make_take("utt-001", 3, "take-003"))

    mgr.set_master("utt-001", "take-002")
    render = mgr.render_take("utt-001")

    assert render is not None
    assert render.take_id == "take-002"
    assert render.status == TakeStatus.MASTER


def test_take_manager_only_one_master() -> None:
    mgr = TakeManager()
    mgr.add_take(_make_take("utt-001", 1, "take-001"))
    mgr.add_take(_make_take("utt-001", 2, "take-002"))

    mgr.set_master("utt-001", "take-001")
    mgr.set_master("utt-001", "take-002")

    # take-001 should no longer be MASTER
    t1 = mgr.get_take("utt-001", "take-001")
    t2 = mgr.get_take("utt-001", "take-002")
    assert t1 is not None and t1.status == TakeStatus.GENERATED
    assert t2 is not None and t2.status == TakeStatus.MASTER


def test_take_manager_ab_preview_selection() -> None:
    mgr = TakeManager()
    mgr.add_take(_make_take("utt-001", 1, "take-001"))
    mgr.add_take(_make_take("utt-001", 2, "take-002"))

    mgr.select_for_preview("utt-001", "take-001")
    mgr.select_for_preview("utt-001", "take-002")  # switches selection

    t1 = mgr.get_take("utt-001", "take-001")
    t2 = mgr.get_take("utt-001", "take-002")
    assert t1 is not None and t1.status == TakeStatus.GENERATED
    assert t2 is not None and t2.status == TakeStatus.SELECTED


def test_take_manager_render_priority() -> None:
    """MASTER > SELECTED > latest GENERATED."""
    mgr = TakeManager()
    mgr.add_take(_make_take("utt-001", 1, "take-001"))
    mgr.add_take(_make_take("utt-001", 2, "take-002"))
    mgr.add_take(_make_take("utt-001", 3, "take-003"))

    mgr.select_for_preview("utt-001", "take-002")
    mgr.set_master("utt-001", "take-003")

    render = mgr.render_take("utt-001")
    assert render is not None and render.take_id == "take-003"


def test_take_manager_enforces_limit() -> None:
    from aidub.application.take_manager import MAX_TAKES_PER_UTTERANCE

    mgr = TakeManager()
    for i in range(1, MAX_TAKES_PER_UTTERANCE + 1):
        mgr.add_take(_make_take("utt-001", i, f"take-{i:03d}"))
    with pytest.raises(ValueError, match="already has"):
        mgr.add_take(_make_take("utt-001", MAX_TAKES_PER_UTTERANCE + 1, "take-extra"))


# ── Task 5.1: Audio DSP Chain ─────────────────────────────────────────────────


def test_audio_dsp_chain_from_flat_preset() -> None:
    chain = AudioDspChain.from_preset("utt-001", DspPreset.FLAT)
    assert chain.utterance_id == "utt-001"
    # FLAT preset has no custom bands/config — chain uses defaults
    # Verify it at least produces a non-empty string (default stages enabled)
    ffmpeg = chain.to_ffmpeg_filter()
    assert isinstance(ffmpeg, str) and len(ffmpeg) > 0


def test_audio_dsp_chain_from_dialogue_preset() -> None:
    chain = AudioDspChain.from_preset("utt-001", DspPreset.DIALOGUE_CLEAN)
    ffmpeg = chain.to_ffmpeg_filter()
    assert "agate" in ffmpeg
    assert "equalizer" in ffmpeg
    assert "acompressor" in ffmpeg


def test_audio_dsp_chain_ffmpeg_filter_contains_all_stages() -> None:
    from aidub.media.audio_chain import Compressor, Deesser, NoiseGate, SpatialPan

    chain = AudioDspChain(
        utterance_id=Identifier("utt-001"),
        noise_gate=NoiseGate(threshold_db=-40.0, enabled=True),
        eq=ParametricEq(
            bands=[EqBand(frequency_hz=1_000.0, gain_db=3.0, q_factor=1.0)],
            enabled=True,
        ),
        compressor=Compressor(threshold_db=-18.0, ratio=3.0, enabled=True),
        deesser=Deesser(enabled=True),
        pan=SpatialPan(pan=0.3, enabled=True),
        output_gain_db=2.0,
    )
    ffmpeg = chain.to_ffmpeg_filter()
    assert "agate" in ffmpeg
    assert "equalizer" in ffmpeg
    assert "acompressor" in ffmpeg
    assert "pan=stereo" in ffmpeg
    assert "volume" in ffmpeg


def test_audio_dsp_chain_disabled_stages_excluded() -> None:
    from aidub.media.audio_chain import NoiseGate

    chain = AudioDspChain(
        utterance_id=Identifier("utt-002"),
        noise_gate=NoiseGate(enabled=False),
    )
    ffmpeg = chain.to_ffmpeg_filter()
    assert "agate" not in ffmpeg


# ── Task 5.3: Loudness Mastering ─────────────────────────────────────────────


def test_loudness_bus_ebu_r128_normalization() -> None:
    bus = LoudnessMasteringBus(LoudnessNormalizationConfig(standard=LoudnessStandard.EBU_R128))
    meas = LoudnessMeasurement(
        integrated_lufs=-30.0,
        loudness_range_lu=8.0,
        true_peak_dbtp=-10.0,  # headroom: +7dB gain pushes peak to -3dBTP (safe)
        short_term_max_lufs=-25.0,
    )
    result = bus.compute_normalization("utt-001", meas)

    assert result.gain_applied_db == pytest.approx(7.0, abs=0.1)
    assert result.output_integrated_lufs == pytest.approx(-23.0, abs=0.5)
    assert result.within_tolerance is True
    assert result.broadcast_compliant is True
    assert result.true_peak_limited is False


def test_loudness_bus_true_peak_limiter_engages() -> None:
    bus = LoudnessMasteringBus(LoudnessNormalizationConfig(standard=LoudnessStandard.EBU_R128))
    meas = LoudnessMeasurement(
        integrated_lufs=-30.0,
        loudness_range_lu=5.0,
        true_peak_dbtp=-2.0,  # +7dB gain would push peak to +5dBTP — must be limited
        short_term_max_lufs=-25.0,
    )
    result = bus.compute_normalization("utt-001", meas)

    assert result.true_peak_limited is True
    assert result.output_true_peak_dbtp <= -1.0


def test_loudness_bus_ffmpeg_filter_string() -> None:
    bus = LoudnessMasteringBus()
    meas = LoudnessMeasurement(
        integrated_lufs=-28.0,
        loudness_range_lu=7.0,
        true_peak_dbtp=-5.0,
        short_term_max_lufs=-23.0,
    )
    ffmpeg = bus.to_ffmpeg_loudnorm_filter(meas)
    assert "loudnorm" in ffmpeg
    assert "I=-23.0" in ffmpeg
    assert "TP=-1.0" in ffmpeg
    assert "measured_I=-28.00" in ffmpeg


# ── Task 5.4: Subtitle QC ─────────────────────────────────────────────────────


def test_subtitle_qc_clean_track_passes() -> None:
    engine = SubtitleQcEngine()
    cues = [
        SubtitleCue(cue_id="1", start_ms=0, end_ms=3_000, text="Hello, world."),
        SubtitleCue(cue_id="2", start_ms=3_200, end_ms=6_000, text="How are you?"),
    ]
    report = engine.check("track-001", cues)
    assert report.passed is True
    assert report.error_count == 0


def test_subtitle_qc_line_too_long() -> None:
    engine = SubtitleQcEngine(SubtitleQcConfig(max_chars_per_line=37))
    cues = [
        SubtitleCue(
            cue_id="1",
            start_ms=0,
            end_ms=5_000,
            text="This is a very long subtitle line that exceeds the maximum character limit",
        ),
    ]
    report = engine.check("track-001", cues)
    assert any(v.kind == QcViolationKind.LINE_TOO_LONG for v in report.violations)
    assert report.passed is False


def test_subtitle_qc_duration_too_short() -> None:
    engine = SubtitleQcEngine()
    cues = [
        SubtitleCue(cue_id="1", start_ms=0, end_ms=400, text="Hi"),  # 0.4s — too short
    ]
    report = engine.check("track-001", cues)
    assert any(v.kind == QcViolationKind.DURATION_TOO_SHORT for v in report.violations)


def test_subtitle_qc_overlapping_cues() -> None:
    engine = SubtitleQcEngine()
    cues = [
        SubtitleCue(cue_id="1", start_ms=0, end_ms=3_000, text="First cue."),
        SubtitleCue(cue_id="2", start_ms=2_500, end_ms=5_000, text="Overlapping cue."),  # overlap!
    ]
    report = engine.check("track-001", cues)
    assert any(v.kind == QcViolationKind.OVERLAPPING_CUES for v in report.violations)
    assert report.passed is False


def test_subtitle_qc_gap_too_short_is_warning() -> None:
    engine = SubtitleQcEngine(SubtitleQcConfig(min_gap_ms=80))
    cues = [
        SubtitleCue(cue_id="1", start_ms=0, end_ms=2_000, text="First."),
        SubtitleCue(cue_id="2", start_ms=2_040, end_ms=4_000, text="Too close."),  # only 40ms gap
    ]
    report = engine.check("track-001", cues)
    gap_violations = [v for v in report.violations if v.kind == QcViolationKind.GAP_TOO_SHORT]
    assert len(gap_violations) == 1
    assert gap_violations[0].severity == "warning"
    assert report.warning_count == 1
    # Warnings do not fail the track
    assert report.passed is True


def test_subtitle_qc_reading_speed_exceeded() -> None:
    engine = SubtitleQcEngine(SubtitleQcConfig(max_reading_speed_cps=17.0))
    # 80 chars in 1.5 seconds = ~53 chars/sec
    cues = [
        SubtitleCue(
            cue_id="1",
            start_ms=0,
            end_ms=1_500,
            text="This is very fast text that nobody can read in this amount of time.",
        ),
    ]
    report = engine.check("track-001", cues)
    assert any(v.kind == QcViolationKind.READING_SPEED_EXCEEDED for v in report.violations)
