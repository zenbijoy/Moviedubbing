"""
Reference Voice Miner Engine.

Mines clean candidate reference samples directly from EXISTING diarization speaker segments
and dialogue stems, avoiding duplicate diarization processing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from aidub.contracts.base import Identifier
from aidub.domain.voice_profile import ReferenceSample

logger = logging.getLogger(__name__)


class DiarizationSegmentInput:
    """Measured speaker segment from the canonical diarization pipeline."""

    def __init__(
        self,
        segment_id: str,
        speaker_id: str,
        start_ms: int,
        duration_ms: int,
        audio_file_path: str,
        snr_db: float = 20.0,
        reverb_score: float = 0.1,
    ) -> None:
        self.segment_id = segment_id
        self.speaker_id = speaker_id
        self.start_ms = start_ms
        self.duration_ms = duration_ms
        self.audio_file_path = audio_file_path
        self.snr_db = snr_db
        self.reverb_score = reverb_score


class ReferenceVoiceMiner:
    """
    Mines candidate reference samples from existing diarization speaker segments.
    """

    def mine_speaker_references(
        self,
        character_id: str,
        diarization_segments: Sequence[DiarizationSegmentInput],
        min_duration_s: float = 3.0,
        max_samples: int = 10,
    ) -> list[ReferenceSample]:
        """
        Extract clean candidate reference clips for a target speaker from diarization output.
        """
        cid = Identifier(character_id)
        candidates: list[ReferenceSample] = []

        # Filter segments matching target speaker
        matching = [s for s in diarization_segments if s.speaker_id == character_id]

        for seg in matching:
            dur_s = seg.duration_ms / 1000.0
            if dur_s < min_duration_s:
                continue

            # Basic quality heuristic from segment metadata
            from aidub.ai.voice.reference_quality import ReferenceVoiceQualityEngine

            evaluator = ReferenceVoiceQualityEngine()

            report = evaluator.evaluate_sample_quality(
                sample_id=seg.segment_id,
                duration_s=dur_s,
                snr_db=seg.snr_db,
                reverb_score=seg.reverb_score,
            )

            candidates.append(
                ReferenceSample(
                    sample_id=Identifier(seg.segment_id),
                    character_id=cid,
                    emotion_category="neutral",
                    audio_file_path=seg.audio_file_path,
                    duration_s=dur_s,
                    quality_report=report,
                )
            )

        # Sort candidate references by quality score descending
        candidates.sort(key=lambda c: c.quality_report.quality_score, reverse=True)
        return candidates[:max_samples]


__all__ = [
    "DiarizationSegmentInput",
    "ReferenceVoiceMiner",
]
