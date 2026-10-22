"""
Broadcast stem export staging manager and deliverable packager.

Stems supported:
  - DIALOGUE: Source/Dub dialogue tracks (A1, A2)
  - MUSIC: Score/Diegetic music track (A3)
  - EFFECTS_AMBIENCE: Foley/FX/Ambience tracks (A4, A5)
  - FULL_PRINT_MASTER: Complete mixed audio output
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier
from aidub.ui.timeline.markers import InOutRange
from aidub.ui.timeline.model import TimelineTrack, TrackId

logger = logging.getLogger(__name__)


class StemKind(StrEnum):
    DIALOGUE = "dialogue"
    MUSIC = "music"
    EFFECTS_AMBIENCE = "effects_ambience"
    FULL_PRINT_MASTER = "full_print_master"


class StemExportRequest(ContractModel):
    """Configuration for staging a multi-track audio stem export job."""

    project_id: str
    export_id: Identifier
    selected_stems: list[StemKind] = Field(default_factory=lambda: list(StemKind))
    in_out_range: InOutRange = Field(default_factory=InOutRange)
    sample_rate: int = Field(default=48_000, ge=8_000)
    bit_depth: int = Field(default=24, ge=16, le=32)
    format_extension: str = Field(default="wav", max_length=8)


class StemExportJobSpec(ContractModel):
    """Job payload spec for background audio render workers."""

    stem_kind: StemKind
    output_filename: str
    active_track_ids: list[TrackId]
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=1)


class StemExportManager:
    """
    Prepares multi-track stem export specifications for render queue execution.
    """

    @staticmethod
    def build_export_specs(
        request: StemExportRequest,
        tracks: list[TimelineTrack],
        total_project_duration_ms: int,
    ) -> list[StemExportJobSpec]:
        """
        Build individual rendering job specs for each requested audio stem.
        """
        start_ms = 0
        dur_ms = total_project_duration_ms

        if request.in_out_range.active and request.in_out_range.in_ms is not None:
            start_ms = request.in_out_range.in_ms
            dur_ms = request.in_out_range.duration_ms

        specs: list[StemExportJobSpec] = []
        track_map = {
            StemKind.DIALOGUE: [TrackId.A1, TrackId.A2],
            StemKind.MUSIC: [TrackId.A3],
            StemKind.EFFECTS_AMBIENCE: [TrackId.A4, TrackId.A5],
            StemKind.FULL_PRINT_MASTER: [
                TrackId.A1,
                TrackId.A2,
                TrackId.A3,
                TrackId.A4,
                TrackId.A5,
            ],
        }

        for stem in request.selected_stems:
            target_tracks = track_map.get(stem, [])
            filename = f"{request.project_id}_{stem.value}.{request.format_extension}"

            specs.append(
                StemExportJobSpec(
                    stem_kind=stem,
                    output_filename=filename,
                    active_track_ids=target_tracks,
                    start_ms=start_ms,
                    duration_ms=dur_ms,
                )
            )

        logger.info(
            "stem_export: generated %d export specs for project %s (%dms)",
            len(specs),
            request.project_id,
            dur_ms,
        )
        return specs


__all__ = [
    "StemExportJobSpec",
    "StemExportManager",
    "StemExportRequest",
    "StemKind",
]
