"""
Interactive Lip-Sync Control Panel & Inspector for NLE Timeline.

Allows video editors to inspect visual eligibility per shot, toggle manual lip-sync overrides,
select quality rendering tiers (Preview vs Cinema Quality), tune visual QC threshold sliders,
and review automated diagnostic repair recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import Field

from aidub.adapters.lipsync_base import LipSyncQualityTier
from aidub.ai.vision.eligibility import (
    EligibilityScore,
    LipSyncEligibilityEvaluator,
    UserOverrideMode,
)
from aidub.ai.vision.visual_qc import VisualQcEvaluator, VisualQcResult
from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)

# Optional PySide6 import guard for headless execution environments
try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QFormLayout,
        QGroupBox,
        QLabel,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc, assignment]


class LipSyncPanelConfig(ContractModel):
    """Configuration model backing the LipSyncControlPanel state."""

    selected_shot_id: Identifier = Field(default=Identifier("shot_0001"))
    quality_tier: LipSyncQualityTier = LipSyncQualityTier.PREVIEW_FAST
    user_override: UserOverrideMode = UserOverrideMode.AUTO
    qc_pass_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    color_match_mode: str = Field(default="histogram", max_length=32)
    anti_flicker_enabled: bool = True
    feather_margin_px: int = Field(default=12, ge=0, le=64)


class LipSyncControlPanelController:
    """
    Business logic and state controller for LipSync control panel (headless safe).
    """

    def __init__(self, config: LipSyncPanelConfig | None = None) -> None:
        self.config = config or LipSyncPanelConfig()
        self.eligibility_evaluator = LipSyncEligibilityEvaluator()
        self.qc_evaluator = VisualQcEvaluator(pass_threshold=self.config.qc_pass_threshold)

    def set_shot(self, shot_id: str) -> None:
        self.config = self.config.model_copy(update={"selected_shot_id": Identifier(shot_id)})

    def set_override(self, override_mode: UserOverrideMode) -> None:
        self.config = self.config.model_copy(update={"user_override": override_mode})

    def set_quality_tier(self, tier: LipSyncQualityTier) -> None:
        self.config = self.config.model_copy(update={"quality_tier": tier})

    def set_qc_threshold(self, threshold: float) -> None:
        self.config = self.config.model_copy(update={"qc_pass_threshold": threshold})
        self.qc_evaluator = VisualQcEvaluator(pass_threshold=threshold)

    def inspect_shot(
        self,
        face_track: Any = None,
        is_off_screen: bool = False,
        is_occluded: bool = False,
        *,
        video_path: str | None = None,
        measured_sync_confidence: float | None = None,
        measured_seam_artifact_score: float | None = None,
    ) -> tuple[EligibilityScore, VisualQcResult]:
        """Assess eligibility and classify QC only when real measurements are supplied."""
        eligibility = self.eligibility_evaluator.evaluate_eligibility(
            shot_id=self.config.selected_shot_id,
            face_track=face_track,
            is_off_screen=is_off_screen,
            is_occluded=is_occluded,
            user_override=self.config.user_override,
        )

        if video_path is None:
            raise RuntimeError("Provide a real rendered shot video before running visual QC.")
        qc_result = self.qc_evaluator.evaluate_shot_video(
            shot_id=self.config.selected_shot_id,
            video_path=video_path,
            measured_sync_confidence=measured_sync_confidence,
            measured_seam_artifact_score=measured_seam_artifact_score,
        )

        return eligibility, qc_result


if PYSIDE6_AVAILABLE:

    class LipSyncControlPanelWidget(QWidget):  # type: ignore[misc]
        """PySide6 QWidget for Lip-Sync control panel."""

        state_changed = Signal(dict)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.controller = LipSyncControlPanelController()
            self._init_ui()

        def _init_ui(self) -> None:
            layout = QVBoxLayout(self)

            group = QGroupBox("Visual Intelligence & Lip-Sync Controls", self)
            form = QFormLayout(group)

            self.override_combo = QComboBox(group)
            for mode in UserOverrideMode:
                self.override_combo.addItem(mode.value, mode)
            self.override_combo.currentIndexChanged.connect(self._on_override_changed)
            form.addRow("Eligibility Override:", self.override_combo)

            self.tier_combo = QComboBox(group)
            for tier in LipSyncQualityTier:
                self.tier_combo.addItem(tier.value, tier)
            self.tier_combo.currentIndexChanged.connect(self._on_tier_changed)
            form.addRow("Quality Tier:", self.tier_combo)

            self.status_label = QLabel("Status: Ready", group)
            form.addRow("Diagnostic Status:", self.status_label)

            layout.addWidget(group)

        def _on_override_changed(self, index: int) -> None:
            mode = self.override_combo.itemData(index)
            if mode:
                self.controller.set_override(mode)
                self.state_changed.emit(self.controller.config.model_dump())

        def _on_tier_changed(self, index: int) -> None:
            tier = self.tier_combo.itemData(index)
            if tier:
                self.controller.set_quality_tier(tier)
                self.state_changed.emit(self.controller.config.model_dump())


__all__ = [
    "LipSyncControlPanelController",
    "LipSyncPanelConfig",
]
