"""
Multi-Track Audio Stem Package & Cue Sheet Exporter.

Exports consolidated Dialogue, M&E, Music, and Effects audio stem packages
and professional audio cue sheets / ADR reports.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class CueSheetItem(ContractModel):
    """ADR Cue Sheet row item."""

    cue_id: Identifier
    character_name: str = Field(min_length=1)
    timecode_in: str = Field(min_length=8)  # "01:00:05:12"
    timecode_out: str = Field(min_length=8)  # "01:00:08:20"
    source_text: str = Field(min_length=1)
    target_text: str = Field(min_length=1)


class CueSheetReport(ContractModel):
    """Complete ADR Cue Sheet report container."""

    report_id: Identifier
    project_title: str = Field(min_length=1)
    target_language: str = Field(min_length=2)
    items: list[CueSheetItem] = Field(default_factory=list)


class CueSheetExporter:
    """
    Exports audio stem packages and ADR cue sheets.
    """

    def generate_cue_sheet(
        self, project_title: str, target_language: str, items: Sequence[CueSheetItem]
    ) -> CueSheetReport:
        """
        Build ADR Cue Sheet report.
        """
        rid = Identifier(f"cue_{target_language}")
        report = CueSheetReport(
            report_id=rid,
            project_title=project_title,
            target_language=target_language,
            items=list(items),
        )
        logger.info(
            "cue_sheet_exporter: generated cue sheet for '%s' (%s) with %d items",
            project_title,
            target_language,
            len(items),
        )
        return report


__all__ = [
    "CueSheetExporter",
    "CueSheetItem",
    "CueSheetReport",
]
