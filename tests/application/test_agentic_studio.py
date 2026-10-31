from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from aidub.application.agentic_studio import (
    AutomationStage,
    StageStatus,
    StudioSessionStore,
    build_quality_report,
    create_automation_plan,
)


def test_plan_exposes_only_dependency_ready_stages() -> None:
    state = create_automation_plan("Feature Film", source_path="feature.mkv")

    assert state.ready_stages() == (AutomationStage.INGEST,)

    now = datetime(2026, 8, 21, tzinfo=UTC)
    state = state.update_stage(
        AutomationStage.INGEST,
        status=StageStatus.SUCCEEDED,
        progress=100,
        detail="Media validated",
        at=now,
    )

    assert state.ready_stages() == (AutomationStage.AUDIO_SEPARATION,)
    assert state.progress == 8


def test_stage_lifecycle_and_quality_gate_are_auditable() -> None:
    state = create_automation_plan("Feature Film")
    started = datetime(2026, 8, 21, tzinfo=UTC)
    running = state.update_stage(
        AutomationStage.INGEST,
        status=StageStatus.RUNNING,
        progress=35,
        detail="Probing streams",
        at=started,
    )
    finished = running.update_stage(
        AutomationStage.INGEST,
        status=StageStatus.SUCCEEDED,
        progress=100,
        detail="Ready",
        at=started + timedelta(seconds=2),
    )

    ingest = finished.stage(AutomationStage.INGEST)
    assert ingest.started_at == started
    assert ingest.finished_at == started + timedelta(seconds=2)

    report = build_quality_report(
        voice=0.96,
        emotion=0.91,
        timing=0.98,
        lip_sync=0.84,
    )
    finished = finished.with_quality_report(report)
    assert finished.quality_report is not None
    assert finished.quality_report.passed is False
    assert [metric.metric for metric in finished.quality_report.blockers] == ["lip_sync"]


def test_session_store_round_trips_atomically(tmp_path: Path) -> None:
    store = StudioSessionStore(tmp_path / "sessions")
    state = create_automation_plan("Feature: Bengali / Final", source_path="feature.mkv")

    saved = store.save(state)
    loaded = store.load(state.project_name)

    assert saved.parent == (tmp_path / "sessions").resolve()
    assert saved.name == "Feature-Bengali-Final.studio.json"
    assert loaded == state
    assert not list(saved.parent.glob("*.tmp"))
