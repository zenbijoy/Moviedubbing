"""
Adaptive Duration Fitting Service (Phase 2).

Executes a 4-step hierarchy when synthesized dialogue exceeds its slot:
1. Suggest a shorter translation preserving meaning (requires user approval).
2. Regenerate with supported speech-rate control (0.85x - 1.20x) if engine supports it.
3. Apply bounded time stretching (max ±8% via FFmpeg atempo/WSOLA).
4. Flag for manual timing adjustment if duration remains unacceptable (>15% delta).

Guarantees:
- Never truncates dialogue or applies extreme time compression.
- Preserves original timing metadata while recording actual and fitted durations.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from pydantic import ConfigDict, Field

from aidub.adapters.voice_base import (
    EngineCapability,
    NormalizedPerformance,
    SynthesisRequest,
    VoiceEngine,
)
from aidub.application.timing_fitter import FitStrategy, TimingFitter, TimingFitterConfig
from aidub.application.voice.scene_performance_service import DialogueCuePerformance
from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.types import LanguageTag

logger = logging.getLogger(__name__)


class AdaptiveFittingReport(ContractModel):
    """Execution report detailing how a dialogue cue was fitted to its timeline slot."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    cue_id: str
    original_start_s: float
    original_end_s: float
    target_duration_s: float
    actual_generated_duration_s: float
    fitted_duration_s: float
    fitted_audio_path: str
    strategy_applied: FitStrategy
    rate_applied: float = 1.0
    stretch_pct_applied: float = 0.0
    suggested_shorter_text: str | None = None
    flagged_for_manual_review: bool = False
    review_reason: str = Field(default="")


class AdaptiveDurationFittingService:
    """
    Coordinates translation adaptation, synthesis rate control,
    and bounded time stretching.
    """

    def __init__(self, timing_fitter: TimingFitter | None = None) -> None:
        self.fitter = timing_fitter or TimingFitter(TimingFitterConfig(max_stretch_pct=0.08))

    def fit_dialogue_cue(
        self,
        cue: DialogueCuePerformance,
        input_audio_path: str | Path,
        output_dir: str | Path,
        voice_engine: VoiceEngine | None = None,
        voice_id: str = "",
        shorter_text_suggester: Callable[[str, float], str] | None = None,
        language: str = "bn-BD",
    ) -> AdaptiveFittingReport:
        """
        Fit a dialogue take into cue.target_duration_s following the 4-step hierarchy.
        """
        in_path = Path(input_audio_path)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        cid = str(cue.cue_id)
        target_s = cue.target_duration_s
        target_ms = int(target_s * 1000)

        # 1. Determine actual generated duration
        import wave

        try:
            with wave.open(str(in_path), "rb") as wf:
                actual_frames = wf.getnframes()
                rate = wf.getframerate()
                actual_s = float(actual_frames) / float(rate) if rate else target_s
        except Exception:
            actual_s = target_s

        actual_ms = int(actual_s * 1000)

        # Baseline: If already within tolerance (<= 50ms difference), no action needed
        if abs(actual_ms - target_ms) <= 50:
            fitted_out = out_dir / f"{cid}_fitted.wav"
            import shutil

            shutil.copyfile(str(in_path), str(fitted_out))
            return AdaptiveFittingReport(
                cue_id=cid,
                original_start_s=cue.start_s,
                original_end_s=cue.end_s,
                target_duration_s=target_s,
                actual_generated_duration_s=round(actual_s, 3),
                fitted_duration_s=round(actual_s, 3),
                fitted_audio_path=str(fitted_out),
                strategy_applied=FitStrategy.EXACT_FIT,
                rate_applied=1.0,
                stretch_pct_applied=0.0,
                flagged_for_manual_review=False,
            )

        # ── Step 1: Suggest shorter translation if available
        suggested_shorter: str | None = None
        if actual_ms > target_ms and shorter_text_suggester:
            try:
                suggested_shorter = shorter_text_suggester(cue.target_text, target_s)
                logger.info(
                    "Suggested shorter translation for cue '%s': '%s' -> '%s'",
                    cid,
                    cue.target_text,
                    suggested_shorter,
                )
            except Exception as exc:
                logger.debug("Shorter text suggester failed for cue %s: %s", cid, exc)

        # ── Step 2: Rate control via voice engine if supported
        current_path = in_path
        current_ms = actual_ms
        rate_applied = 1.0

        if (
            voice_engine
            and EngineCapability.RATE_CONTROL in voice_engine.metadata.capabilities
            and abs(current_ms - target_ms) > 50
        ):
            needed_rate = current_ms / max(target_ms, 1)
            # Bounded rate range 0.85x to 1.20x
            clamped_rate = max(0.85, min(1.20, round(needed_rate, 2)))

            if abs(clamped_rate - 1.0) >= 0.04:
                try:
                    req = SynthesisRequest(
                        request_id=Identifier(f"rate_fit_{cid}"),
                        utterance_id=cue.cue_id,
                        voice_profile_id=Identifier(voice_id or "default"),
                        text=cue.target_text,
                        language=LanguageTag(language),
                        pace_multiplier=clamped_rate,
                        target_duration_ms=target_ms,
                        performance=NormalizedPerformance(speaking_rate=clamped_rate),
                    )
                    synth_res = voice_engine.synthesize(req, str(out_dir))
                    if synth_res.output_path and Path(synth_res.output_path).exists():
                        current_path = Path(synth_res.output_path)
                        current_ms = synth_res.duration_ms
                        rate_applied = clamped_rate
                        logger.info(
                            "Re-synthesized cue '%s' with rate %.2fx -> duration %dms (target %dms)",
                            cid,
                            clamped_rate,
                            current_ms,
                            target_ms,
                        )
                except Exception as exc:
                    logger.warning("Rate control re-synthesis failed on cue %s: %s", cid, exc)

        # Check if rate control brought it within tolerance
        if abs(current_ms - target_ms) <= 50:
            return AdaptiveFittingReport(
                cue_id=cid,
                original_start_s=cue.start_s,
                original_end_s=cue.end_s,
                target_duration_s=target_s,
                actual_generated_duration_s=round(actual_s, 3),
                fitted_duration_s=round(current_ms / 1000.0, 3),
                fitted_audio_path=str(current_path),
                strategy_applied=FitStrategy.RATE_CONTROL,
                rate_applied=rate_applied,
                stretch_pct_applied=0.0,
                suggested_shorter_text=suggested_shorter,
                flagged_for_manual_review=False,
            )

        # ── Step 3: Bounded time-stretching (max ±8%)
        fit_calc = self.fitter.fit(
            utterance_id=cid,
            synthesized_ms=current_ms,
            slot_ms=target_ms,
        )

        final_out = out_dir / f"{cid}_final_fitted.wav"

        if fit_calc.strategy_used == FitStrategy.TIME_STRETCH:
            try:
                fitted_path = self.fitter.apply(fit_calc, current_path, final_out)
                return AdaptiveFittingReport(
                    cue_id=cid,
                    original_start_s=cue.start_s,
                    original_end_s=cue.end_s,
                    target_duration_s=target_s,
                    actual_generated_duration_s=round(actual_s, 3),
                    fitted_duration_s=round(fit_calc.fitted_duration_ms / 1000.0, 3),
                    fitted_audio_path=str(fitted_path),
                    strategy_applied=FitStrategy.TIME_STRETCH,
                    rate_applied=rate_applied,
                    stretch_pct_applied=fit_calc.stretch_pct_applied,
                    suggested_shorter_text=suggested_shorter,
                    flagged_for_manual_review=False,
                )
            except Exception as exc:
                logger.warning("Time stretch apply failed on %s: %s", cid, exc)

        # ── Step 4: Flag for manual timing adjustment
        # Do not force extreme time compression!
        # Apply the safe bounded stretch and flag for human review
        try:
            safely_stretched = self.fitter.apply(fit_calc, current_path, final_out)
        except Exception:
            import shutil

            shutil.copyfile(str(current_path), str(final_out))
            safely_stretched = final_out

        remaining_delta_pct = abs(fit_calc.fitted_duration_ms - target_ms) / max(target_ms, 1)

        return AdaptiveFittingReport(
            cue_id=cid,
            original_start_s=cue.start_s,
            original_end_s=cue.end_s,
            target_duration_s=target_s,
            actual_generated_duration_s=round(actual_s, 3),
            fitted_duration_s=round(fit_calc.fitted_duration_ms / 1000.0, 3),
            fitted_audio_path=str(safely_stretched),
            strategy_applied=FitStrategy.HUMAN_REVIEW,
            rate_applied=rate_applied,
            stretch_pct_applied=fit_calc.stretch_pct_applied,
            suggested_shorter_text=suggested_shorter,
            flagged_for_manual_review=True,
            review_reason=(
                f"Remaining timing delta {remaining_delta_pct * 100:.1f}% exceeds safe ±8% stretch limit. "
                "Manual script trim or timeline extension required."
            ),
        )


__all__ = [
    "AdaptiveDurationFittingService",
    "AdaptiveFittingReport",
]
