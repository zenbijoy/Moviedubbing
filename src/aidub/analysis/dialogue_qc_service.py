"""
Automated Dialogue Quality Control (QC) Service (Phase 2).

Performs granular acoustic and metadata inspection on synthesized dialogue takes:
- Missing, corrupt, or zero-byte audio files (Hard Error)
- Unexpected dead silence (Hard Error)
- Digital clipping and excessive peak levels (Warning)
- Invalid sample rate or channel configuration (Hard Error / Warning)
- Dialogue slot duration overrun (> 15% delta) (Warning)
- Inter-cue dialogue timing overlaps (Warning)
- Boundary pops, clicks, and discontinuities (Warning)
- Missing speaker or character voice profile (Hard Error)
- Stale audio generated from earlier profile or translation versions (Warning)

Provides actionable repair suggestions for every detected issue.
"""

from __future__ import annotations

import logging
import math
import wave
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import ConfigDict, Field

from aidub.application.voice.scene_performance_service import DialogueCuePerformance
from aidub.contracts.base import ContractModel

logger = logging.getLogger(__name__)


class QCSeverity(StrEnum):
    """Severity classification for quality control findings."""

    HARD_ERROR = "hard_error"  # Blocks delivery, mandatory re-synthesis
    WARNING = "warning"  # Non-blocking, recommended review for artistic intent


class QCIssueType(StrEnum):
    """Categorized dialogue audio defects."""

    MISSING_OR_EMPTY_AUDIO = "missing_or_empty_audio"
    DEAD_SILENCE = "dead_silence"
    DIGITAL_CLIPPING = "digital_clipping"
    EXCESSIVE_PEAK = "excessive_peak"
    INVALID_SAMPLE_RATE = "invalid_sample_rate"
    INVALID_CHANNELS = "invalid_channels"
    DURATION_OVERRUN = "duration_overrun"
    TIMING_OVERLAP = "timing_overlap"
    BOUNDARY_DISCONTINUITY = "boundary_discontinuity"
    MISSING_SPEAKER_OR_PROFILE = "missing_speaker_or_profile"
    STALE_AUDIO = "stale_audio"
    PRONUNCIATION_MISMATCH = "pronunciation_mismatch"


class DialogueQCIssue(ContractModel):
    """A specific quality defect identified in a dialogue take."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    cue_id: str
    issue_type: QCIssueType
    severity: QCSeverity
    description: str
    actionable_repair: str


class DialogueCueQCReport(ContractModel):
    """Inspection report for a single dialogue cue and its audio take."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    cue_id: str
    audio_path: str
    passed: bool = True
    can_deliver: bool = True
    duration_s: float = 0.0
    target_duration_s: float = 0.0
    duration_delta_pct: float = 0.0
    peak_dbfs: float = -99.0
    snr_db: float = 0.0
    silence_ratio: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    issues: list[DialogueQCIssue] = Field(default_factory=list)


class BatchQCReport(ContractModel):
    """Consolidated QC report across multiple scenes and dialogue cues."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    total_cues: int = 0
    passed_cues: int = 0
    hard_errors_count: int = 0
    warnings_count: int = 0
    can_deliver: bool = True
    cue_reports: list[DialogueCueQCReport] = Field(default_factory=list)


class DialogueQCService:
    """
    Automated dialogue quality assurance and verification service.
    """

    SUPPORTED_SAMPLE_RATES: ClassVar[set[int]] = {16000, 22050, 24000, 44100, 48000}

    def inspect_cue(
        self,
        cue: DialogueCuePerformance,
        audio_path: str | None = None,
        next_cue: DialogueCuePerformance | None = None,
        is_stale: bool = False,
        asr_verifier: Any = None,
    ) -> DialogueCueQCReport:
        """
        Inspect a dialogue cue take for physical, acoustic, and timing defects.
        """
        cid = str(cue.cue_id)
        issues: list[DialogueQCIssue] = []

        # 1. Metadata check: character/speaker assignment
        if not str(cue.character_id) or not str(cue.speaker_id):
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.MISSING_SPEAKER_OR_PROFILE,
                    severity=QCSeverity.HARD_ERROR,
                    description="Cue lacks valid character_id or speaker_id.",
                    actionable_repair="Assign an authorized character voice profile to this speaker.",
                )
            )

        # 2. Stale audio check
        if is_stale:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.STALE_AUDIO,
                    severity=QCSeverity.WARNING,
                    description="Audio was synthesized with an earlier voice configuration or translation.",
                    actionable_repair="Regenerate this line using the updated voice profile.",
                )
            )

        # Determine target audio path
        target_path = audio_path
        if not target_path and cue.selected_take_id:
            take = next((t for t in cue.candidate_takes if t.take_id == cue.selected_take_id), None)
            if take:
                target_path = take.audio_path

        if not target_path:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.MISSING_OR_EMPTY_AUDIO,
                    severity=QCSeverity.HARD_ERROR,
                    description="No audio take associated or selected for this dialogue cue.",
                    actionable_repair="Synthesize speech for this cue using the assigned voice engine.",
                )
            )
            return DialogueCueQCReport(
                cue_id=cid,
                audio_path="",
                passed=False,
                can_deliver=False,
                target_duration_s=cue.target_duration_s,
                issues=issues,
            )

        path_obj = Path(target_path)
        if not path_obj.exists() or path_obj.stat().st_size == 0:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.MISSING_OR_EMPTY_AUDIO,
                    severity=QCSeverity.HARD_ERROR,
                    description=f"Audio file '{path_obj.name}' is missing or 0 bytes.",
                    actionable_repair="Re-synthesize this dialogue cue.",
                )
            )
            return DialogueCueQCReport(
                cue_id=cid,
                audio_path=str(path_obj),
                passed=False,
                can_deliver=False,
                target_duration_s=cue.target_duration_s,
                issues=issues,
            )

        # 3. Acoustic inspection via WAV parsing
        duration_s = 0.0
        sample_rate = 0
        channels = 1
        peak_val = 0.0
        silence_samples = 0
        total_samples = 0
        first_sample_mag = 0.0
        last_sample_mag = 0.0

        try:
            with wave.open(str(path_obj), "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                duration_s = float(n_frames) / float(sample_rate) if sample_rate else 0.0

                raw_bytes = wf.readframes(n_frames)
                total_samples = n_frames * channels

                if sampwidth == 2 and raw_bytes:
                    import struct

                    fmt = f"<{n_frames * channels}h"
                    # Read in chunks or slice
                    samples = struct.unpack(fmt, raw_bytes)
                    if samples:
                        first_sample_mag = abs(samples[0]) / 32768.0
                        last_sample_mag = abs(samples[-1]) / 32768.0
                        max_sample = max(abs(s) for s in samples)
                        peak_val = max_sample / 32768.0

                        # Calculate silence ratio (threshold ~ -45 dBFS = 184)
                        silence_thresh = 184
                        silence_samples = sum(1 for s in samples if abs(s) < silence_thresh)
        except Exception as exc:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.MISSING_OR_EMPTY_AUDIO,
                    severity=QCSeverity.HARD_ERROR,
                    description=f"Audio file is corrupted or unreadable as WAV: {exc}",
                    actionable_repair="Re-render audio with standard 48kHz 16-bit PCM WAV.",
                )
            )
            return DialogueCueQCReport(
                cue_id=cid,
                audio_path=str(path_obj),
                passed=False,
                can_deliver=False,
                target_duration_s=cue.target_duration_s,
                issues=issues,
            )

        # 4. Check sample rate
        if sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.INVALID_SAMPLE_RATE,
                    severity=QCSeverity.HARD_ERROR,
                    description=f"Non-standard sample rate {sample_rate}Hz. Film dubbing requires 48kHz or 24kHz.",
                    actionable_repair="Resample audio to 48,000Hz PCM.",
                )
            )

        # 5. Check channels (dialogue takes are typically mono or stereo)
        if channels > 2:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.INVALID_CHANNELS,
                    severity=QCSeverity.WARNING,
                    description=f"Dialogue cue has {channels} channels; expected mono or stereo.",
                    actionable_repair="Downmix dialogue take to mono center channel.",
                )
            )

        # 6. Dead silence check
        silence_ratio = float(silence_samples) / float(total_samples) if total_samples > 0 else 1.0
        if silence_ratio >= 0.98 and duration_s > 0.3:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.DEAD_SILENCE,
                    severity=QCSeverity.HARD_ERROR,
                    description=f"Audio take is completely silent ({silence_ratio * 100:.1f}% silence).",
                    actionable_repair="TTS generation produced empty audio; re-synthesize with adjusted prompt/seed.",
                )
            )

        # 7. Clipping & Peak checks
        peak_dbfs = 20.0 * math.log10(max(1e-5, peak_val))
        if peak_val >= 0.998:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.DIGITAL_CLIPPING,
                    severity=QCSeverity.WARNING,
                    description=f"Audio exhibits digital clipping (peak: {peak_dbfs:.2f} dBFS >= -0.02 dBFS).",
                    actionable_repair="Apply peak normalization to -1.0 dBFS.",
                )
            )
        elif peak_dbfs > -0.5:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.EXCESSIVE_PEAK,
                    severity=QCSeverity.WARNING,
                    description=f"True peak level {peak_dbfs:.2f} dBFS exceeds recommended broadcast ceiling (-1.0 dBFS).",
                    actionable_repair="Reduce gain by 1.5 dB before master mixdown.",
                )
            )

        # 8. Boundary click / discontinuity check
        if first_sample_mag > 0.08 or last_sample_mag > 0.08:
            issues.append(
                DialogueQCIssue(
                    cue_id=cid,
                    issue_type=QCIssueType.BOUNDARY_DISCONTINUITY,
                    severity=QCSeverity.WARNING,
                    description="Sudden non-zero DC boundary sample detected, risking audible click.",
                    actionable_repair="Apply 5ms micro-fade at take boundaries.",
                )
            )

        # 9. Duration slot overrun check
        duration_delta_pct = 0.0
        if cue.target_duration_s > 0.1:
            duration_delta_pct = ((duration_s - cue.target_duration_s) / cue.target_duration_s) * 100.0
            if duration_delta_pct > 15.0:
                issues.append(
                    DialogueQCIssue(
                        cue_id=cid,
                        issue_type=QCIssueType.DURATION_OVERRUN,
                        severity=QCSeverity.WARNING,
                        description=(
                            f"Generated duration ({duration_s:.2f}s) exceeds target slot "
                            f"({cue.target_duration_s:.2f}s) by {duration_delta_pct:.1f}%."
                        ),
                        actionable_repair="Run adaptive duration fitting (shorten text or increase speaking rate).",
                    )
                )

        # 10. Inter-cue timing overlap check
        if next_cue and cue.target_duration_s > 0:
            actual_end_s = cue.start_s + duration_s
            # Allow 50ms grace margin
            if actual_end_s > (next_cue.start_s + 0.05):
                overlap_ms = int((actual_end_s - next_cue.start_s) * 1000)
                issues.append(
                    DialogueQCIssue(
                        cue_id=cid,
                        issue_type=QCIssueType.TIMING_OVERLAP,
                        severity=QCSeverity.WARNING,
                        description=f"Dialogue collides with next cue '{next_cue.cue_id}' by {overlap_ms}ms.",
                        actionable_repair="Apply bounded time-stretching or delay the next cue start time.",
                    )
                )

        # 11. Optional ASR verification
        if asr_verifier:
            try:
                verified_text = asr_verifier(str(path_obj))
                if verified_text and len(verified_text) < 2 and len(cue.target_text) > 5:
                    issues.append(
                        DialogueQCIssue(
                            cue_id=cid,
                            issue_type=QCIssueType.PRONUNCIATION_MISMATCH,
                            severity=QCSeverity.WARNING,
                            description=f"ASR intelligibility verification failed. Recognized '{verified_text}'.",
                            actionable_repair="Regenerate with alternative candidate take or clearer phonetic spelling.",
                        )
                    )
            except Exception as exc:
                logger.debug("ASR verification skipped on %s: %s", cid, exc)

        has_hard_errors = any(i.severity == QCSeverity.HARD_ERROR for i in issues)
        has_warnings = any(i.severity == QCSeverity.WARNING for i in issues)

        return DialogueCueQCReport(
            cue_id=cid,
            audio_path=str(path_obj),
            passed=not has_hard_errors and not has_warnings,
            can_deliver=not has_hard_errors,
            duration_s=round(duration_s, 3),
            target_duration_s=cue.target_duration_s,
            duration_delta_pct=round(duration_delta_pct, 2),
            peak_dbfs=round(peak_dbfs, 2),
            snr_db=round(max(0.0, 30.0 * (1.0 - silence_ratio)), 1),
            silence_ratio=round(silence_ratio, 3),
            sample_rate=sample_rate,
            channels=channels,
            issues=issues,
        )

    def inspect_batch(
        self,
        cues: list[DialogueCuePerformance],
        takes_map: dict[str, str] | None = None,
        stale_cues: set[str] | None = None,
        asr_verifier: Any = None,
    ) -> BatchQCReport:
        """
        Run dialogue QC across a sequence of dialogue cues.
        """
        stale_set = stale_cues or set()
        cue_reports: list[DialogueCueQCReport] = []
        hard_errors = 0
        warnings = 0
        passed_cues = 0

        sorted_cues = sorted(cues, key=lambda c: c.start_s)

        for i, cue in enumerate(sorted_cues):
            cid = str(cue.cue_id)
            next_cue = sorted_cues[i + 1] if i + 1 < len(sorted_cues) else None
            path = takes_map.get(cid) if takes_map else None
            is_stale = cid in stale_set

            rep = self.inspect_cue(
                cue=cue,
                audio_path=path,
                next_cue=next_cue,
                is_stale=is_stale,
                asr_verifier=asr_verifier,
            )
            cue_reports.append(rep)

            if rep.passed:
                passed_cues += 1
            hard_errors += sum(1 for iss in rep.issues if iss.severity == QCSeverity.HARD_ERROR)
            warnings += sum(1 for iss in rep.issues if iss.severity == QCSeverity.WARNING)

        can_deliver = hard_errors == 0

        return BatchQCReport(
            total_cues=len(sorted_cues),
            passed_cues=passed_cues,
            hard_errors_count=hard_errors,
            warnings_count=warnings,
            can_deliver=can_deliver,
            cue_reports=cue_reports,
        )


__all__ = [
    "BatchQCReport",
    "DialogueCueQCReport",
    "DialogueQCIssue",
    "DialogueQCService",
    "QCIssueType",
    "QCSeverity",
]
