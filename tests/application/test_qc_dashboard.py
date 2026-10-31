"""
Unit tests for QcDashboardService and DeliveryService.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from aidub.application.export.delivery import DeliveryService
from aidub.application.qc.qc_dashboard import (
    QcDashboardService,
    QcIssueType,
    QcSeverity,
)
from aidub.media.pro_audio_editor import AudioClipData


def test_qc_dashboard_audit_and_blockers() -> None:
    qc = QcDashboardService()

    sr = 48000
    # 1. Clipped audio (0 dBFS peak)
    clip_clipped = AudioClipData(samples=np.full(sr, 1.0, dtype=np.float32), sample_rate=sr)
    issues_clip = qc.audit_cue("cue_bad_vol", clip_clipped, budget_duration_ms=1000)
    assert any(i.issue_type == QcIssueType.AUDIO_CLIPPING for i in issues_clip)

    # 2. Timing Overrun (1500ms audio with 1000ms budget -> +50% overrun)
    clip_over = AudioClipData(samples=np.full(int(sr * 1.5), 0.2, dtype=np.float32), sample_rate=sr)
    issues_over = qc.audit_cue("cue_bad_time", clip_over, budget_duration_ms=1000)
    assert any(i.issue_type == QcIssueType.TIMING_OVERRUN for i in issues_over)

    # 3. Lip-Sync Misalignment (+80ms lead > +45ms)
    clip_good = AudioClipData(samples=np.full(sr, 0.2, dtype=np.float32), sample_rate=sr)
    issues_sync = qc.audit_cue("cue_bad_sync", clip_good, budget_duration_ms=1000, lead_lag_offset_ms=80.0)
    assert any(i.issue_type == QcIssueType.LIPSYNC_MISALIGNMENT for i in issues_sync)

    assert qc.has_delivery_blockers()
    summary = qc.generate_heatmap_summary()
    assert summary["can_export_master"] is False
    assert summary["active_blockers"] >= 3

    # Resolve all blockers
    for b in qc.get_blockers():
        qc.resolve_issue(b.issue_id)

    assert not qc.has_delivery_blockers()
    assert qc.generate_heatmap_summary()["can_export_master"] is True


def test_delivery_service_exports(tmp_path: Path) -> None:
    delivery = DeliveryService()

    sr = 48000
    dia = AudioClipData(samples=np.full(sr, 0.4, dtype=np.float32), sample_rate=sr)
    mne = AudioClipData(samples=np.full(sr, 0.1, dtype=np.float32), sample_rate=sr)

    # Stem exports
    stems = delivery.export_stems(tmp_path, dia, mne)
    assert Path(stems["dialogue_stem"]).exists()
    assert Path(stems["mne_stem"]).exists()
    assert Path(stems["master_mix"]).exists()

    # Cue sheet export
    cues_data = [
        {"cue_id": "c1", "start_ms": 1000, "end_ms": 2500, "speaker": "Hero", "dialogue_text": "Hello", "translated_text": "নমস্কার"},
        {"cue_id": "c2", "start_ms": 2600, "end_ms": 4000, "speaker": "Villain", "dialogue_text": "Wait!", "translated_text": "দাঁড়াও!"},
    ]
    csv_path = delivery.export_cue_sheet(cues_data, tmp_path / "cues.csv")
    assert csv_path.exists()
    assert csv_path.stat().st_size > 50

    # SRT export
    srt_path = delivery.export_subtitles_srt(cues_data, tmp_path / "subs.srt")
    assert srt_path.exists()
    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:01,000 --> 00:00:02,500" in content
    assert "নমস্কার" in content
