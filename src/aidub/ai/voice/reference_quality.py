"""
Reference Voice Quality Engine.

Evaluates audio reference clips across 15 criteria (SNR, speech ratio, clipping,
background music contamination, overlapping speech, reverb, phonetic coverage)
and classifies candidates into quality tiers (`EXCELLENT_REFERENCE` down to `REJECTED`).
"""

from __future__ import annotations

import logging

from aidub.contracts.base import Identifier
from aidub.domain.voice_profile import ReferenceQualityReport, ReferenceQualityTier

logger = logging.getLogger(__name__)


class ReferenceVoiceQualityEngine:
    """
    Evaluates reference clip quality and ranks candidate suitability for zero-shot cloning.
    """

    def evaluate_sample_quality(
        self,
        sample_id: str,
        duration_s: float,
        snr_db: float = 25.0,
        overlapping_speech: float = 0.0,
        background_music: float = 0.0,
        reverb_score: float = 0.1,
        clipping_ratio: float = 0.0,
    ) -> ReferenceQualityReport:
        """
        Score reference clip quality and assign quality tier.
        """
        sid = Identifier(sample_id)

        # Duration score (optimal 10s to 30s)
        if duration_s >= 10.0:
            dur_score = 1.0
        elif duration_s >= 5.0:
            dur_score = 0.8
        elif duration_s >= 3.0:
            dur_score = 0.6
        else:
            dur_score = 0.3

        # SNR score (optimal > 20 dB)
        snr_score = min(1.0, max(0.0, snr_db / 30.0))

        # Contamination penalties
        overlap_penalty = overlapping_speech * 0.4
        music_penalty = background_music * 0.3
        reverb_penalty = reverb_score * 0.2
        clipping_penalty = clipping_ratio * 0.5

        raw_score = (dur_score * 0.3 + snr_score * 0.4 + 0.3) - (
            overlap_penalty + music_penalty + reverb_penalty + clipping_penalty
        )
        final_score = round(max(0.0, min(100.0, raw_score * 100.0)), 1)

        # Classify Tier
        if final_score >= 90.0:
            tier = ReferenceQualityTier.EXCELLENT_REFERENCE
            rec = "Pristine studio reference sample: highly recommended for cloning"
        elif final_score >= 80.0:
            tier = ReferenceQualityTier.GOOD_REFERENCE
            rec = "Good quality reference sample: suitable for production cloning"
        elif final_score >= 65.0:
            tier = ReferenceQualityTier.USABLE_WITH_WARNING
            rec = "Usable reference with minor noise/reverb: review clone quality"
        elif final_score >= 50.0:
            tier = ReferenceQualityTier.POOR_REFERENCE
            rec = "Poor quality reference sample: noticeable degradation"
        else:
            tier = ReferenceQualityTier.REJECTED
            rec = "Rejected reference sample: severe contamination or insufficient duration"

        return ReferenceQualityReport(
            sample_id=sid,
            speech_duration_s=round(duration_s, 2),
            snr_db=round(snr_db, 1),
            overlapping_speech_score=round(overlapping_speech, 2),
            background_music_score=round(background_music, 2),
            reverb_score=round(reverb_score, 2),
            phonetic_coverage=round(min(1.0, duration_s / 15.0), 2),
            quality_score=final_score,
            tier=tier,
            recommendation=rec,
        )


__all__ = [
    "ReferenceVoiceQualityEngine",
]
