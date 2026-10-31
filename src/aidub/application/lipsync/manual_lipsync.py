"""
Manual Lip-Sync and Viseme Synchronization Application Service.

Provides:
  - Sub-frame and multi-frame audio/video lead-lag offset nudging (ITU-R BT.1359).
  - Manual viseme keyframe override at any playhead timestamp.
  - Per-shot face gating eligibility toggles (force on/off).
  - Quality tier routing: Preview (MuseTalk) vs Cinema (LatentSync).
  - 3D Mocap Rig JSON export for DCC tools (Blender, Unreal Engine, Maya).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aidub.domain.viseme import (
    LipSyncOffset,
    VisemeGroup,
    VisemeKeyframe,
    VisemeTimeline,
)
from aidub.media.lipsync_viseme_engine import VISEME_GEOMETRIES

logger = logging.getLogger(__name__)


class ManualLipSyncService:
    """Orchestrates manual visual dubbing adjustments and ITU broadcast compliance."""

    def __init__(self) -> None:
        self._timelines: dict[str, VisemeTimeline] = {}
        self._offset_history: dict[str, list[LipSyncOffset]] = {}

    def register_timeline(self, timeline: VisemeTimeline) -> None:
        self._timelines[timeline.utterance_id] = timeline
        if timeline.utterance_id not in self._offset_history:
            self._offset_history[timeline.utterance_id] = []

    def get_timeline(self, utterance_id: str) -> VisemeTimeline | None:
        return self._timelines.get(utterance_id)

    def nudge_offset(
        self,
        utterance_id: str,
        delta_ms: float,
        reason: str = "Manual nudge",
    ) -> float:
        """Nudges the lead-lag offset for utterance_id by delta_ms."""
        timeline = self.get_timeline(utterance_id)
        if not timeline:
            raise KeyError(f"Utterance {utterance_id} not registered in lipsync service.")

        new_offset = timeline.nudge_offset(delta_ms)
        record = LipSyncOffset(offset_ms=new_offset, reason=reason)
        self._offset_history[utterance_id].append(record)

        logger.info(
            "ManualLipSync: Nudged utterance %s by %+.1fms (Current: %+.1fms)",
            utterance_id,
            delta_ms,
            new_offset,
        )
        return new_offset

    def override_viseme(
        self,
        utterance_id: str,
        time_s: float,
        viseme: VisemeGroup,
    ) -> VisemeKeyframe | None:
        """Manually sets the mouth viseme pose at playhead time_s."""
        timeline = self.get_timeline(utterance_id)
        if not timeline:
            raise KeyError(f"Utterance {utterance_id} not registered.")
        return timeline.override_viseme_at(time_s, viseme)

    def set_shot_eligibility(self, utterance_id: str, eligible: bool) -> bool:
        """Forces shot eligibility on/off, overriding automatic face gating."""
        timeline = self.get_timeline(utterance_id)
        if not timeline:
            raise KeyError(f"Utterance {utterance_id} not registered.")
        timeline.shot_eligible_for_lipsync = eligible
        return eligible

    def set_quality_tier(self, utterance_id: str, tier: str) -> str:
        """Sets quality tier: 'preview' (MuseTalk fast) or 'cinema' (LatentSync diffusion)."""
        tier_normalized = "cinema" if "cinema" in tier.lower() else "preview"
        timeline = self.get_timeline(utterance_id)
        if not timeline:
            raise KeyError(f"Utterance {utterance_id} not registered.")
        timeline.quality_tier = tier_normalized
        return tier_normalized

    def evaluate_compliance(self, utterance_id: str) -> tuple[bool, str, float]:
        """Evaluates ITU-R BT.1359 broadcast synchronization standard."""
        timeline = self.get_timeline(utterance_id)
        if not timeline:
            return False, "Utterance Not Found", 0.0
        return timeline.evaluate_itu_compliance()

    def export_mocap_json(self, utterance_id: str, output_path: str | Path) -> Path:
        """Exports geometric blendshapes to a standard JSON mocap rig format."""
        timeline = self.get_timeline(utterance_id)
        if not timeline:
            raise KeyError(f"Utterance {utterance_id} not registered.")

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = timeline.to_mocap_dict()
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return out


__all__ = [
    "ManualLipSyncService",
]
