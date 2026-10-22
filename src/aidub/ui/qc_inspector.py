"""
Timeline Quality Control Inspector & Heatmap UI Controller.

Allows video editors and quality control engineers to visually inspect project QC heatmaps,
filter dialogue clips by defect severity (Green Pass, Amber Warning, Red Blocking) and category,
and trigger one-click automated repair actions.
"""

from __future__ import annotations

import logging

from pydantic import Field

from aidub.ai.qc.evaluator import (
    MultiDimensionalQCEvaluator,
    StudioQcPreset,
    TimelineQualityHeatmap,
    UtteranceQcReport,
)
from aidub.contracts.base import ContractModel

logger = logging.getLogger(__name__)

# Optional PySide6 import guard for headless execution environments
try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QFormLayout,
        QGroupBox,
        QListWidget,
        QListWidgetItem,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc, assignment]


class QcFilterOptions(ContractModel):
    """Filter criteria for the QC Inspector UI view."""

    severity_filter: str = Field(
        default="all", max_length=32
    )  # "all", "pass_green", "warning_amber", "blocking_red"
    category_filter: str = Field(
        default="all", max_length=32
    )  # "all", "audio", "video", "subtitles", "timing"
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class QcInspectorController:
    """
    State controller for QC Inspector widget (headless safe).
    """

    def __init__(
        self,
        project_id: str = "project_001",
        preset: StudioQcPreset = StudioQcPreset.BROADCAST_STUDIO,
    ) -> None:
        self.project_id = project_id
        self.evaluator = MultiDimensionalQCEvaluator(preset=preset)
        self.heatmap: TimelineQualityHeatmap | None = None
        self.filter_options = QcFilterOptions()

    def set_heatmap(self, heatmap: TimelineQualityHeatmap) -> None:
        self.heatmap = heatmap

    def set_filter(
        self,
        severity_filter: str | None = None,
        category_filter: str | None = None,
    ) -> None:
        updates = {}
        if severity_filter is not None:
            updates["severity_filter"] = severity_filter
        if category_filter is not None:
            updates["category_filter"] = category_filter
        self.filter_options = self.filter_options.model_copy(update=updates)

    def get_filtered_reports(self) -> list[UtteranceQcReport]:
        """Return list of utterance QC reports matching current severity and category filters."""
        if not self.heatmap:
            return []
        reports = self.heatmap.reports

        sf = self.filter_options.severity_filter
        if sf != "all":
            reports = [r for r in reports if r.severity.value == sf]

        cf = self.filter_options.category_filter
        if cf == "audio":
            reports = [
                r
                for r in reports
                if r.dimension_scores.get("loudness", None)
                and r.dimension_scores["loudness"].score < 0.85
            ]
        elif cf == "video":
            reports = [
                r
                for r in reports
                if r.dimension_scores.get("lipsync", None)
                and r.dimension_scores["lipsync"].score < 0.85
            ]
        elif cf == "subtitles":
            reports = [
                r
                for r in reports
                if r.dimension_scores.get("subtitle_speed", None)
                and r.dimension_scores["subtitle_speed"].score < 0.85
            ]
        elif cf == "timing":
            reports = [
                r
                for r in reports
                if r.dimension_scores.get("timing", None)
                and r.dimension_scores["timing"].score < 0.85
            ]

        return reports

    def execute_auto_repair(
        self,
        utterance_id: str,
        action_type: str,
        *,
        measured_result: UtteranceQcReport,
    ) -> UtteranceQcReport | None:
        """
        Execute automated repair action for a specific utterance defect.
        """
        if not self.heatmap:
            return None

        report = next((r for r in self.heatmap.reports if r.utterance_id == utterance_id), None)
        if not report:
            return None

        if str(measured_result.utterance_id) != utterance_id:
            raise ValueError("repair result utterance does not match the requested utterance")

        logger.info("qc_inspector: executed auto-repair '%s' on %s", action_type, utterance_id)

        # Update report in heatmap
        new_reports = [
            measured_result if r.utterance_id == utterance_id else r for r in self.heatmap.reports
        ]
        self.heatmap = self.evaluator.generate_heatmap(self.project_id, new_reports)

        return measured_result


if PYSIDE6_AVAILABLE:

    class QualityControlInspectorWidget(QWidget):
        """PySide6 QWidget for Quality Control Inspector & Timeline Heatmap."""

        report_selected = Signal(str)
        repair_triggered = Signal(str, str)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.controller = QcInspectorController()
            self._init_ui()

        def _init_ui(self) -> None:
            layout = QVBoxLayout(self)

            group = QGroupBox("Timeline Quality Control Heatmap & Issue Inspector", self)
            form = QFormLayout(group)

            self.filter_combo = QComboBox(group)
            self.filter_combo.addItem("All Utterances", "all")
            self.filter_combo.addItem("Green (Passed)", "pass_green")
            self.filter_combo.addItem("Amber (Warnings)", "warning_amber")
            self.filter_combo.addItem("Red (Blocking)", "blocking_red")
            self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
            form.addRow("Severity Filter:", self.filter_combo)

            self.category_combo = QComboBox(group)
            self.category_combo.addItem("All Categories", "all")
            self.category_combo.addItem("Audio Issues", "audio")
            self.category_combo.addItem("Video Lip-Sync", "video")
            self.category_combo.addItem("Subtitle Speed", "subtitles")
            self.category_combo.addItem("Timing Alignment", "timing")
            self.category_combo.currentIndexChanged.connect(self._on_category_changed)
            form.addRow("Category Filter:", self.category_combo)

            self.list_widget = QListWidget(group)
            self.list_widget.currentTextChanged.connect(self._on_item_selected)
            form.addRow("Clip Issues:", self.list_widget)

            self.repair_btn = QPushButton("One-Click Auto Fix Selected Issue", group)
            self.repair_btn.clicked.connect(self._on_repair_clicked)
            form.addRow("Automated Fix:", self.repair_btn)

            self.progress_bar = QProgressBar(group)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            form.addRow("Overall QC Health:", self.progress_bar)

            layout.addWidget(group)

        def _on_filter_changed(self, index: int) -> None:
            filter_val = self.filter_combo.itemData(index)
            if filter_val:
                self.controller.set_filter(severity_filter=filter_val)
                self._refresh_list()

        def _on_category_changed(self, index: int) -> None:
            cat_val = self.category_combo.itemData(index)
            if cat_val:
                self.controller.set_filter(category_filter=cat_val)
                self._refresh_list()

        def _on_item_selected(self, text: str) -> None:
            if text:
                self.report_selected.emit(text)

        def _on_repair_clicked(self) -> None:
            item = self.list_widget.currentItem()
            if item:
                text = item.text()
                # Parse utterance id from item text
                parts = text.split(" — ")
                if parts:
                    uid = parts[0].split("]")[-1].strip()
                    self.repair_triggered.emit(uid, "auto_fix")

        def _refresh_list(self) -> None:
            self.list_widget.clear()
            reports = self.controller.get_filtered_reports()
            for r in reports:
                item = QListWidgetItem(
                    f"[{r.severity.value.upper()}] {r.utterance_id} — Score: {r.overall_score:.2f}"
                )
                self.list_widget.addItem(item)


__all__ = [
    "QcFilterOptions",
    "QcInspectorController",
]
