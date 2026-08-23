"""
Bounded Timing Fitter: 5-step alignment algorithm to fit synthesized speech into video slots.

Algorithm priority order:
  1. LLM text adaptation (request shorter/longer translation)
  2. Silence/pause optimization (trim natural pauses)
  3. Voice model rate control (speed up/slow down via synthesis parameter)
  4. Bounded high-quality time-stretch (±8% limit using soxr/rubberband)
  5. Flag for human editor review if delta still exceeds threshold
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)

# Alignment algorithm constants
RATE_CONTROL_MIN = 0.85      # Slowest rate via TTS rate control
RATE_CONTROL_MAX = 1.20      # Fastest rate via TTS rate control
STRETCH_MAX_PCT = 0.08       # ±8% maximum time-stretch before flagging
SILENCE_TRIM_MAX_MS = 200    # Maximum silence to trim from start/end
REVIEW_FLAG_THRESHOLD = 0.15  # Flag for editor review if still >15% off


class FitStrategy(StrEnum):
    LLM_ADAPTATION = "llm_adaptation"
    SILENCE_TRIM = "silence_trim"
    RATE_CONTROL = "rate_control"
    TIME_STRETCH = "time_stretch"
    HUMAN_REVIEW = "human_review"
    EXACT_FIT = "exact_fit"


class FitResult(ContractModel):
    """Result of a timing fit operation."""

    utterance_id: Identifier
    source_duration_ms: int = Field(ge=0)
    target_slot_ms: int = Field(ge=0)
    fitted_duration_ms: int = Field(ge=0)
    delta_ms: int
    delta_pct: float
    strategy_used: FitStrategy
    within_tolerance: bool
    flagged_for_review: bool
    rate_applied: float = Field(default=1.0)
    stretch_pct_applied: float = Field(default=0.0)
    silence_trimmed_ms: int = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=1_000)


class TimingFitterConfig(ContractModel):
    """Configuration for the bounded timing fitter."""

    max_stretch_pct: float = Field(default=STRETCH_MAX_PCT, ge=0.0, le=0.30)
    rate_control_min: float = Field(default=RATE_CONTROL_MIN, ge=0.5, le=1.0)
    rate_control_max: float = Field(default=RATE_CONTROL_MAX, ge=1.0, le=2.0)
    silence_trim_max_ms: int = Field(default=SILENCE_TRIM_MAX_MS, ge=0, le=1_000)
    review_flag_threshold: float = Field(default=REVIEW_FLAG_THRESHOLD, ge=0.0, le=1.0)
    tolerance_ms: int = Field(default=50, ge=0, le=500)


class TimingFitter:
    """
    5-step bounded timing alignment algorithm.

    Given a synthesized audio duration and target video slot, determines
    the minimum-distortion strategy to align them within tolerance.

    This service only CALCULATES the alignment parameters; actual
    audio processing (time-stretch, silence trim) is performed by
    the audio render worker using these parameters.
    """

    def __init__(self, config: TimingFitterConfig | None = None) -> None:
        self._config = config or TimingFitterConfig()

    def fit(
        self,
        *,
        utterance_id: str,
        synthesized_ms: int,
        slot_ms: int,
        leading_silence_ms: int = 0,
        trailing_silence_ms: int = 0,
    ) -> FitResult:
        """
        Determine optimal alignment strategy for a synthesized take into a video slot.

        Args:
            utterance_id: The utterance being fitted.
            synthesized_ms: Duration of the synthesized audio take in milliseconds.
            slot_ms: Duration of the target video slot in milliseconds.
            leading_silence_ms: Detected silence at start of take (can be trimmed).
            trailing_silence_ms: Detected silence at end of take (can be trimmed).

        Returns:
            FitResult with the chosen strategy and computed parameters.
        """
        cfg = self._config

        # Already within tolerance — no action needed
        if abs(synthesized_ms - slot_ms) <= cfg.tolerance_ms:
            return FitResult(
                utterance_id=Identifier(utterance_id),
                source_duration_ms=synthesized_ms,
                target_slot_ms=slot_ms,
                fitted_duration_ms=synthesized_ms,
                delta_ms=synthesized_ms - slot_ms,
                delta_pct=0.0,
                strategy_used=FitStrategy.EXACT_FIT,
                within_tolerance=True,
                flagged_for_review=False,
            )

        current_ms = synthesized_ms

        # ── Step 1: LLM text adaptation is an upstream pass, not applied here.
        # The fitter assumes synthesized_ms reflects final LLM-adapted text.

        # ── Step 2: Silence/pause optimization
        silence_trimmed = 0
        if current_ms > slot_ms:
            trimmable = min(
                leading_silence_ms + trailing_silence_ms,
                cfg.silence_trim_max_ms,
                current_ms - slot_ms,
            )
            silence_trimmed = max(0, trimmable)
            current_ms -= silence_trimmed
            if abs(current_ms - slot_ms) <= cfg.tolerance_ms:
                return self._result(
                    utterance_id, synthesized_ms, slot_ms, current_ms,
                    FitStrategy.SILENCE_TRIM,
                    silence_trimmed_ms=silence_trimmed,
                )

        # ── Step 3: Rate control via TTS speed parameter
        rate = slot_ms / max(current_ms, 1)
        rate_clamped = max(cfg.rate_control_min, min(cfg.rate_control_max, rate))
        current_after_rate = int(current_ms / rate_clamped)

        if abs(current_after_rate - slot_ms) <= cfg.tolerance_ms:
            return self._result(
                utterance_id, synthesized_ms, slot_ms, current_after_rate,
                FitStrategy.RATE_CONTROL,
                rate_applied=rate_clamped,
                silence_trimmed_ms=silence_trimmed,
            )

        # ── Step 4: Bounded time-stretch (max ±8%)
        stretch_ratio = slot_ms / max(current_after_rate, 1)
        stretch_pct = stretch_ratio - 1.0  # positive = stretch, negative = compress

        if abs(stretch_pct) <= cfg.max_stretch_pct:
            fitted_ms = int(current_after_rate * stretch_ratio)
            return self._result(
                utterance_id, synthesized_ms, slot_ms, fitted_ms,
                FitStrategy.TIME_STRETCH,
                rate_applied=rate_clamped,
                stretch_pct_applied=round(stretch_pct * 100, 2),
                silence_trimmed_ms=silence_trimmed,
            )

        # ── Step 5: Flag for human editor review
        best_ms = int(current_after_rate * max(
            1.0 - cfg.max_stretch_pct,
            min(1.0 + cfg.max_stretch_pct, stretch_ratio)
        ))
        remaining_delta_pct = abs(best_ms - slot_ms) / max(slot_ms, 1)

        logger.warning(
            "timing_fitter: %s flagged for review — delta %.1f%% exceeds max stretch ±%.0f%%",
            utterance_id,
            remaining_delta_pct * 100,
            cfg.max_stretch_pct * 100,
        )

        return FitResult(
            utterance_id=Identifier(utterance_id),
            source_duration_ms=synthesized_ms,
            target_slot_ms=slot_ms,
            fitted_duration_ms=best_ms,
            delta_ms=best_ms - slot_ms,
            delta_pct=round(remaining_delta_pct, 4),
            strategy_used=FitStrategy.HUMAN_REVIEW,
            within_tolerance=False,
            flagged_for_review=True,
            rate_applied=rate_clamped,
            stretch_pct_applied=round(cfg.max_stretch_pct * 100 * (1 if stretch_pct > 0 else -1), 2),
            silence_trimmed_ms=silence_trimmed,
            notes=f"Remaining delta {remaining_delta_pct*100:.1f}% exceeds ±{cfg.max_stretch_pct*100:.0f}% stretch limit",
        )

    def apply(
        self,
        result: FitResult,
        input_wav: str | Path,
        output_wav: str | Path,
    ) -> Path:
        """
        Apply calculated timing alignment parameters to input audio file using FFmpeg.

        Executes rate adjustments and atempo time-stretches as determined by fit().

        Args:
            result: Computed FitResult containing rate and stretch values.
            input_wav: Path to raw synthesized audio take.
            output_wav: Destination path for fitted audio take.

        Returns:
            Path to final fitted WAV file.
        """
        from aidub.media.ffmpeg_ops import time_stretch

        in_p = Path(input_wav)
        out_p = Path(output_wav)

        factor = result.rate_applied
        if result.stretch_pct_applied != 0.0:
            factor *= (1.0 + (result.stretch_pct_applied / 100.0))

        if abs(factor - 1.0) < 0.005:
            import shutil
            shutil.copyfile(str(in_p), str(out_p))
            return out_p

        logger.debug("Applying timing fit to %s: total stretch factor=%.3fx", in_p.name, factor)
        return time_stretch(in_p, out_p, factor)

    def _result(
        self,
        utterance_id: str,
        source_ms: int,
        slot_ms: int,
        fitted_ms: int,
        strategy: FitStrategy,
        *,
        rate_applied: float = 1.0,
        stretch_pct_applied: float = 0.0,
        silence_trimmed_ms: int = 0,
    ) -> FitResult:
        delta_ms = fitted_ms - slot_ms
        delta_pct = abs(delta_ms) / max(slot_ms, 1)
        within = abs(delta_ms) <= self._config.tolerance_ms
        flagged = not within and delta_pct >= self._config.review_flag_threshold
        return FitResult(
            utterance_id=Identifier(utterance_id),
            source_duration_ms=source_ms,
            target_slot_ms=slot_ms,
            fitted_duration_ms=fitted_ms,
            delta_ms=delta_ms,
            delta_pct=round(delta_pct, 4),
            strategy_used=strategy,
            within_tolerance=within,
            flagged_for_review=flagged,
            rate_applied=rate_applied,
            stretch_pct_applied=stretch_pct_applied,
            silence_trimmed_ms=silence_trimmed_ms,
        )


__all__ = [
    "FitResult",
    "FitStrategy",
    "TimingFitter",
    "TimingFitterConfig",
]
