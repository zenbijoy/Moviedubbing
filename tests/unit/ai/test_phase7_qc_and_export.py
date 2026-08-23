"""
Unit tests for Phase 7 AI Quality Control, Partial Re-rendering, Master Export & NLE Interchange:
  - Task 7.1: Multi-Dimensional AI Quality Control System & Timeline Heatmap
  - Task 7.2: DAG Dependency-Aware Invalidation & Partial Rerender Engine
  - Task 7.3: Multi-Track Master Deliverable Exporter
  - Task 7.4: Professional NLE Interchange (OpenTimelineIO, CMX 3600 EDL, FCPXML, CSV Cue Sheet)
"""

from __future__ import annotations

import json

import pytest

from aidub.adapters.interchange_otio import (
    NleClipItem,
    NleInterchangeAdapter,
    NleInterchangeTimeline,
    NleTrackItem,
)
from aidub.ai.qc.evaluator import (
    MultiDimensionalQCEvaluator,
    QcSeverityLevel,
    StudioQcPreset,
)
from aidub.application.invalidation import ArtifactStage, DependencyNode, InvalidationGraph
from aidub.contracts.base import Identifier
from aidub.media.render_exporter import (
    AudioStreamTrack,
    ContainerFormat,
    MasterExportOptions,
    MasterMediaExporter,
    SubtitleStreamTrack,
)
from aidub.ui.qc_inspector import QcInspectorController

# ── Task 7.1: Multi-Dimensional AI Quality Control & Heatmap Tests ───────────


def test_multi_dimensional_qc_evaluator() -> None:
    evaluator = MultiDimensionalQCEvaluator(warning_threshold=0.85, blocking_threshold=0.70)

    # Excellent utterance scores -> PASS_GREEN
    report_good = evaluator.evaluate_utterance(
        utterance_id="utt_001",
        transcription_acc=0.98,
        diarization_prec=0.95,
        translation_meaning=0.94,
        timing_fit=0.92,
        voice_quality=0.95,
        lipsync_score=0.90,
        integrated_lufs=-24.0,
        subtitle_cps=14.0,
    )
    assert report_good.severity == QcSeverityLevel.PASS_GREEN
    assert report_good.overall_score >= 0.85
    assert len(report_good.actionable_recommendations) == 0

    # Failing timing & loudness -> BLOCKING_RED with recommendations & auto repair actions
    report_bad = evaluator.evaluate_utterance(
        utterance_id="utt_002",
        transcription_acc=0.95,
        diarization_prec=0.90,
        translation_meaning=0.88,
        timing_fit=0.50,  # Fail
        voice_quality=0.85,
        lipsync_score=0.80,
        integrated_lufs=-12.0,  # Loudness deviation
        subtitle_cps=25.0,     # Too fast
    )
    assert report_bad.overall_score < 0.85
    assert len(report_bad.actionable_recommendations) > 0
    assert len(report_bad.auto_repair_actions) > 0

    # Heatmap generation
    heatmap = evaluator.generate_heatmap("project_001", [report_good, report_bad])
    assert heatmap.total_utterances == 2
    assert heatmap.passed_count == 1
    assert heatmap.overall_project_quality > 0.50


def test_studio_presets_and_auto_repair_actions() -> None:
    evaluator = MultiDimensionalQCEvaluator(preset=StudioQcPreset.BROADCAST_STUDIO)
    report = evaluator.evaluate_utterance(
        "u_preset",
        transcription_acc=0.95,
        diarization_prec=0.92,
        translation_meaning=0.90,
        timing_fit=0.50,
        voice_quality=0.91,
        lipsync_score=0.89,
        integrated_lufs=-12.0,
        subtitle_cps=14.5,
    )
    assert len(report.auto_repair_actions) >= 2

    types = [a.action_type for a in report.auto_repair_actions]
    assert "wsola_timestretch" in types
    assert "normalize_loudness" in types


def test_qc_inspector_controller() -> None:
    ctrl = QcInspectorController("project_001")
    evaluator = MultiDimensionalQCEvaluator()
    r1 = evaluator.evaluate_utterance(
        "u1",
        transcription_acc=0.95,
        diarization_prec=0.92,
        translation_meaning=0.90,
        timing_fit=0.95,
        voice_quality=0.91,
        lipsync_score=0.89,
        integrated_lufs=-24.0,
        subtitle_cps=14.5,
    )
    r2 = evaluator.evaluate_utterance(
        "u2",
        transcription_acc=0.50,
        diarization_prec=0.92,
        translation_meaning=0.50,
        timing_fit=0.40,
        voice_quality=0.91,
        lipsync_score=0.40,
        integrated_lufs=-24.0,
        subtitle_cps=14.5,
    )

    heatmap = evaluator.generate_heatmap("project_001", [r1, r2])
    ctrl.set_heatmap(heatmap)

    all_reports = ctrl.get_filtered_reports()
    assert len(all_reports) == 2

    ctrl.set_filter(severity_filter="pass_green")
    filtered = ctrl.get_filtered_reports()
    assert len(filtered) == 1
    assert filtered[0].utterance_id == "u1"

    # Test auto repair execution
    measured_repair = evaluator.evaluate_utterance(
        "u2",
        transcription_acc=0.98,
        diarization_prec=0.95,
        translation_meaning=0.95,
        timing_fit=0.95,
        voice_quality=0.95,
        lipsync_score=0.95,
        integrated_lufs=-24.0,
        subtitle_cps=14.0,
    )
    repaired = ctrl.execute_auto_repair(
        "u2",
        "auto_fix",
        measured_result=measured_repair,
    )
    assert repaired is not None
    assert repaired.severity == QcSeverityLevel.PASS_GREEN


# ── Task 7.2: DAG Dependency-Aware Invalidation Tests ────────────────────────


def test_dag_invalidation_fine_grained() -> None:
    graph = InvalidationGraph()

    # Build DAG: Translation -> Voice -> Timing -> LipSync -> Mix -> Export
    n_trans = DependencyNode(key="trans_1", stage=ArtifactStage.TRANSLATION, localization_id="bn", utterance_id="u1")
    n_voice = DependencyNode(key="voice_1", stage=ArtifactStage.VOICE, localization_id="bn", utterance_id="u1", character_id="char_hero")
    n_timing = DependencyNode(key="timing_1", stage=ArtifactStage.TIMING, localization_id="bn", utterance_id="u1")
    n_lipsync = DependencyNode(key="lipsync_1", stage=ArtifactStage.LIPSYNC, shot_id="shot_1")
    n_mix = DependencyNode(key="mix_1", stage=ArtifactStage.MIX)
    n_music = DependencyNode(key="music_track", stage=ArtifactStage.STEMS)
    n_export = DependencyNode(key="export_1", stage=ArtifactStage.EXPORT)

    graph.add(n_trans)
    graph.add(n_voice, depends_on=["trans_1"])
    graph.add(n_timing, depends_on=["voice_1"])
    graph.add(n_lipsync, depends_on=["timing_1"])
    graph.add(n_music)
    graph.add(n_mix, depends_on=["lipsync_1", "music_track"])
    graph.add(n_export, depends_on=["mix_1"])

    # Editing 1 translation -> invalidates trans_1, voice_1, timing_1, lipsync_1, mix_1, export_1
    affected_trans = graph.invalidate_translation(localization_id="bn", utterance_id="u1")
    assert "trans_1" in affected_trans
    assert "voice_1" in affected_trans
    assert "export_1" in affected_trans

    # Editing background music track -> invalidates ONLY music_track, mix_1, export_1 without invalidating VOICE or LIPSYNC!
    affected_music = graph.invalidate_music_track(track_key="music_track")
    assert "music_track" in affected_music
    assert "mix_1" in affected_music
    assert "export_1" in affected_music
    assert "voice_1" not in affected_music
    assert "lipsync_1" not in affected_music


def test_partial_render_plan_compute_savings() -> None:
    graph = InvalidationGraph()

    n1 = DependencyNode(key="node_1", stage=ArtifactStage.SOURCE)
    n2 = DependencyNode(key="node_2", stage=ArtifactStage.TRANSCRIPT)
    n3 = DependencyNode(key="node_3", stage=ArtifactStage.TRANSLATION)
    n4 = DependencyNode(key="node_4", stage=ArtifactStage.VOICE)

    graph.add(n1)
    graph.add(n2, depends_on=["node_1"])
    graph.add(n3, depends_on=["node_2"])
    graph.add(n4, depends_on=["node_3"])

    plan = graph.create_partial_render_plan(["node_3", "node_4"])
    assert plan.total_nodes == 4
    assert plan.invalidated_nodes == 2
    assert plan.reusable_cached_nodes == 2
    assert plan.saved_compute_percent == 50.0
    assert plan.execution_order == ("node_3", "node_4")


# ── Task 7.3: Multi-Track Master Deliverable Exporter Tests ───────────────────


def test_master_media_exporter(tmp_path) -> None:
    exporter = MasterMediaExporter()

    options = MasterExportOptions(
        output_filename="master_dubbed_movie",
        output_directory=str(tmp_path),
        container_format=ContainerFormat.MKV,
        fast_video_copy=True,
        ebu_r128_normalize=True,
        target_lufs=-24.0,
        audio_tracks=[
            AudioStreamTrack(track_index=0, language_code="en", title="Original Audio", file_path="orig_audio.wav"),
            AudioStreamTrack(track_index=1, language_code="bn", title="Bengali Dub", file_path="bn_dub.wav"),
        ],
        subtitle_tracks=[
            SubtitleStreamTrack(track_index=0, language_code="en", title="English Subtitles", file_path="en_sub.srt"),
            SubtitleStreamTrack(track_index=1, language_code="bn", title="Bengali Subtitles", file_path="bn_sub.srt"),
        ],
    )

    args = exporter.build_ffmpeg_args("source_video.mp4", options)
    assert "ffmpeg" in args
    assert "-c:v" in args
    assert "copy" in args
    assert "-af" in args
    assert "loudnorm=I=-24.0" in " ".join(args)

    with pytest.raises(FileNotFoundError, match="master export inputs do not exist"):
        exporter.export_master_container("prj_001", "source_video.mp4", options)


# ── Task 7.4: Professional NLE Interchange (OTIO, EDL, FCPXML, CSV) Tests ────


def test_nle_interchange_serializers() -> None:
    timeline = NleInterchangeTimeline(
        project_id=Identifier("prj_001"),
        title="Epic Dubbed Film",
        fps=24.0,
        duration_ms=120000,
        tracks=[
            NleTrackItem(
                track_id=Identifier("trk_dialogue"),
                name="Dubbed Dialogue",
                kind="Audio",
                clips=[
                    NleClipItem(
                        clip_id=Identifier("clip_001"),
                        character_id=Identifier("hero"),
                        source_start_ms=0,
                        source_duration_ms=3000,
                        timeline_start_ms=1000,
                        audio_file_path="takes/take_001.wav",
                        transcript_text="Hello world",
                        translation_text="নমস্কার বিশ্ব",
                    )
                ],
            )
        ],
    )

    # 1. Test OTIO export & import
    otio_str = NleInterchangeAdapter.export_otio_json(timeline)
    otio_json = json.loads(otio_str)
    assert otio_json["OTIO_SCHEMA"] == "Timeline.1"
    assert otio_json["name"] == "Epic Dubbed Film"

    reimported = NleInterchangeAdapter.import_otio_json(otio_str)
    assert reimported.title == "Epic Dubbed Film"
    assert len(reimported.tracks) == 1

    # 2. Test EDL CMX3600 export
    edl_str = NleInterchangeAdapter.export_cmx3600_edl(timeline)
    assert "TITLE: EPIC DUBBED FILM" in edl_str
    assert "001  AX       AA/V" in edl_str

    # 3. Test FCPXML export
    fcpxml_str = NleInterchangeAdapter.export_fcpxml(timeline)
    assert "<fcpxml version=\"1.9\">" in fcpxml_str
    assert "asset-clip" in fcpxml_str

    # 4. Test Dialogue Cue Sheet CSV export
    csv_str = NleInterchangeAdapter.export_dialogue_cue_sheet_csv(timeline)
    assert "Cue_ID,Character_ID,Timeline_Start_ms" in csv_str
    assert "clip_001,hero,1000,3000" in csv_str
