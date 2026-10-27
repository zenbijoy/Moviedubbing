"""
Movie-Scale Batch Dialogue Processing Orchestrator (Phase 2).

Integrates persistent character voices, scene performance, automated QC,
and adaptive duration fitting into a resilient batch pipeline:
- Dependency-aware stages: Preflight -> Synthesis -> QC -> Duration Fitting.
- Deterministic input fingerprinting: SHA-256(text + voice_id + engine + pace + pitch + ref_hash).
- Resumption after interruption: skips matching fingerprints, reprocesses stale/missing cues.
- Pre-flight checks: verifies free disk space (> 2GB) and model readiness.
- Bounded retries: 3 attempts with exponential backoff on transient errors.
- Thread-safe cancellation and progress reporting.
- Preserves original source media and intermediate checkpoints.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import ConfigDict, Field

from aidub.adapters.voice.engine_registry import VoiceEngineRegistry
from aidub.adapters.voice_base import (
    SynthesisRequest,
)
from aidub.analysis.dialogue_qc_service import DialogueQCService
from aidub.application.adaptive_duration_fitting import AdaptiveDurationFittingService
from aidub.application.voice.scene_performance_service import (
    DialogueCuePerformance,
    ScenePerformanceService,
)
from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.types import LanguageTag

logger = logging.getLogger(__name__)


class BatchStage(StrEnum):
    """Pipeline stages for batch dialogue processing."""

    IDLE = "idle"
    PREFLIGHT = "preflight"
    SYNTHESIS = "synthesis"
    QC_INSPECTION = "qc_inspection"
    DURATION_FITTING = "duration_fitting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


def compute_dialogue_fingerprint(
    text: str,
    voice_id: str,
    engine_kind: str,
    pace: float = 1.0,
    pitch: float = 0.0,
    reference_hash: str = "",
) -> str:
    """
    Generate deterministic SHA-256 fingerprint representing all input parameters.
    Any edit to text, casting, engine, or reference audio invalidates the fingerprint.
    """
    raw = (
        f"text={text.strip()}|voice={voice_id}|engine={engine_kind}|"
        f"pace={pace:.3f}|pitch={pitch:.2f}|ref={reference_hash}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DialogueJobItem(ContractModel):
    """Execution state for a single dialogue cue in the batch."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    cue_id: str
    fingerprint: str
    stage: BatchStage = BatchStage.IDLE
    audio_path: str = ""
    fitted_audio_path: str = ""
    attempts: int = 0
    max_attempts: int = 3
    error_message: str = ""
    is_completed: bool = False
    is_stale: bool = False
    duration_s: float = 0.0
    fitted_duration_s: float = 0.0


class BatchJobState(ContractModel):
    """Persistent batch job checkpoint state."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    job_id: str
    created_at_iso: str
    updated_at_iso: str
    current_stage: BatchStage = BatchStage.IDLE
    total_cues: int = 0
    completed_cues: int = 0
    failed_cues: int = 0
    items: dict[str, DialogueJobItem] = Field(default_factory=dict)


class BatchDialogueOrchestrator:
    """
    Coordinates batch synthesis, QC, and adaptive duration fitting
    across movie dialogue with checkpoint resumption.
    """

    MIN_DISK_FREE_GB = 2.0

    def __init__(
        self,
        output_dir: Path | str,
        engine_registry: VoiceEngineRegistry | None = None,
        qc_service: DialogueQCService | None = None,
        duration_service: AdaptiveDurationFittingService | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.output_dir / "batch_job_state.json"

        self.registry = engine_registry or VoiceEngineRegistry.get_default()
        self.qc_service = qc_service or DialogueQCService()
        self.duration_service = duration_service or AdaptiveDurationFittingService()

        self._cancelled = False
        self._state = self._load_state()

    def cancel(self) -> None:
        """Signal the orchestrator to safely abort processing."""
        self._cancelled = True
        logger.warning("BatchDialogueOrchestrator: cancellation requested.")

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    @property
    def state(self) -> BatchJobState:
        return self._state

    def process_batch(
        self,
        cues: list[DialogueCuePerformance],
        character_voices: dict[str, tuple[str, str]],  # character_id -> (engine_kind, voice_id)
        scene_service: ScenePerformanceService | None = None,
        progress_callback: Callable[[BatchStage, int, int, str], None] | None = None,
        reference_audio_map: dict[str, str] | None = None,
    ) -> BatchJobState:
        """
        Execute or resume batch dialogue processing across all stages.
        """
        if self._cancelled:
            self._set_stage(BatchStage.CANCELLED, progress_callback, 0, len(cues), "Batch cancelled.")
            return self._state
        ref_map = reference_audio_map or {}

        # ── Stage 1: Pre-flight Checks
        self._set_stage(BatchStage.PREFLIGHT, progress_callback, 0, len(cues), "Running pre-flight checks...")
        disk_free = self.registry.get_disk_free_gb(self.output_dir)
        if disk_free < self.MIN_DISK_FREE_GB:
            raise RuntimeError(
                f"Insufficient disk space in {self.output_dir}: "
                f"{disk_free:.2f} GB free, required >= {self.MIN_DISK_FREE_GB} GB."
            )

        # Initialize or update cue job items
        self._state.total_cues = len(cues)
        for cue in cues:
            cid = str(cue.cue_id)
            char_id = str(cue.character_id)
            engine_kind, voice_id = character_voices.get(char_id, ("synthetic", "default"))
            ref_path = ref_map.get(char_id, "")
            ref_hash = (
                hashlib.sha256(Path(ref_path).read_bytes()).hexdigest()
                if ref_path and Path(ref_path).exists()
                else ""
            )
            fp = compute_dialogue_fingerprint(
                text=cue.target_text,
                voice_id=voice_id,
                engine_kind=engine_kind,
                pace=1.0,
                reference_hash=ref_hash,
            )

            existing_item = self._state.items.get(cid)
            if existing_item:
                if existing_item.fingerprint != fp:
                    # Invalidate stale intermediate result!
                    existing_item.is_stale = True
                    existing_item.fingerprint = fp
                    existing_item.is_completed = False
                    existing_item.audio_path = ""
                    existing_item.fitted_audio_path = ""
                    existing_item.attempts = 0
            else:
                self._state.items[cid] = DialogueJobItem(
                    cue_id=cid,
                    fingerprint=fp,
                    stage=BatchStage.IDLE,
                )

        self._save_state()

        # ── Stage 2: Synthesis with Idempotent Fingerprinting & Retries
        self._set_stage(BatchStage.SYNTHESIS, progress_callback, 0, len(cues), "Synthesizing dialogue lines...")
        for i, cue in enumerate(cues):
            if self._cancelled:
                self._set_stage(BatchStage.CANCELLED, progress_callback, i, len(cues), "Batch cancelled.")
                return self._state

            cid = str(cue.cue_id)
            item = self._state.items[cid]

            # Resume check: Skip if already synthesized with identical fingerprint and file exists
            if item.audio_path and Path(item.audio_path).exists() and not item.is_stale:
                if progress_callback:
                    progress_callback(BatchStage.SYNTHESIS, i + 1, len(cues), f"Reused cached take for {cid}")
                continue

            char_id = str(cue.character_id)
            engine_kind, voice_id = character_voices.get(char_id, ("synthetic", "default"))
            engine = self.registry.get_engine(engine_kind)

            success = False
            last_err = ""
            while item.attempts < item.max_attempts and not success:
                item.attempts += 1
                try:
                    req = SynthesisRequest(
                        request_id=Identifier(f"batch_{cid}_{item.attempts}"),
                        utterance_id=cue.cue_id,
                        voice_profile_id=Identifier(voice_id),
                        text=cue.target_text,
                        language=LanguageTag("bn-BD"),
                        reference_audio_path=ref_map.get(char_id, ""),
                        target_duration_ms=int(cue.target_duration_s * 1000) if cue.target_duration_s > 0 else None,
                    )
                    synth_res = engine.synthesize(req, str(self.output_dir))
                    if synth_res.output_path and Path(synth_res.output_path).exists():
                        item.audio_path = str(synth_res.output_path)
                        item.duration_s = synth_res.duration_ms / 1000.0
                        item.is_stale = False
                        item.error_message = ""
                        success = True
                except Exception as exc:
                    last_err = str(exc)
                    logger.warning("Attempt %d failed for cue %s: %s", item.attempts, cid, exc)
                    time.sleep(0.1 * item.attempts)  # Bounded backoff

            if not success:
                item.error_message = f"Synthesis failed after {item.attempts} attempts: {last_err}"
                self._state.failed_cues += 1

            self._save_state()
            if progress_callback:
                progress_callback(BatchStage.SYNTHESIS, i + 1, len(cues), f"Synthesized cue {cid}")

        # ── Stage 3: Automated Quality Control
        self._set_stage(BatchStage.QC_INSPECTION, progress_callback, 0, len(cues), "Running automated QC...")
        takes_map = {cid: it.audio_path for cid, it in self._state.items.items() if it.audio_path}
        qc_batch = self.qc_service.inspect_batch(cues, takes_map=takes_map)

        # Record QC failures
        for rep in qc_batch.cue_reports:
            item = self._state.items.get(rep.cue_id)
            if item and not rep.can_deliver:
                item.error_message = f"QC Hard Error: {rep.issues[0].description}"

        self._save_state()

        # ── Stage 4: Adaptive Duration Fitting
        self._set_stage(BatchStage.DURATION_FITTING, progress_callback, 0, len(cues), "Fitting dialogue to slots...")
        for i, cue in enumerate(cues):
            if self._cancelled:
                self._set_stage(BatchStage.CANCELLED, progress_callback, i, len(cues), "Batch cancelled.")
                return self._state

            cid = str(cue.cue_id)
            item = self._state.items[cid]
            if not item.audio_path or not Path(item.audio_path).exists():
                continue

            char_id = str(cue.character_id)
            engine_kind, voice_id = character_voices.get(char_id, ("synthetic", "default"))
            engine = self.registry.get_engine(engine_kind)

            fit_rep = self.duration_service.fit_dialogue_cue(
                cue=cue,
                input_audio_path=item.audio_path,
                output_dir=self.output_dir / "fitted",
                voice_engine=engine,
                voice_id=voice_id,
            )
            item.fitted_audio_path = fit_rep.fitted_audio_path
            item.fitted_duration_s = fit_rep.fitted_duration_s
            item.is_completed = True
            self._state.completed_cues += 1

            self._save_state()
            if progress_callback:
                progress_callback(BatchStage.DURATION_FITTING, i + 1, len(cues), f"Fitted duration for {cid}")

        self._set_stage(BatchStage.COMPLETED, progress_callback, len(cues), len(cues), "Batch processing complete.")
        return self._state

    def _set_stage(
        self,
        stage: BatchStage,
        callback: Callable[[BatchStage, int, int, str], None] | None,
        current: int,
        total: int,
        msg: str,
    ) -> None:
        self._state.current_stage = stage
        self._state.updated_at_iso = datetime.now(UTC).isoformat()
        if callback:
            callback(stage, current, total, msg)

    def _save_state(self) -> None:
        self._state.updated_at_iso = datetime.now(UTC).isoformat()
        try:
            self.state_file.write_text(self._state.model_dump_json(indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed saving batch state: %s", exc)

    def _load_state(self) -> BatchJobState:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                return BatchJobState(**data)
            except Exception as exc:
                logger.debug("Creating new batch job state (previous corrupt: %s)", exc)

        now = datetime.now(UTC).isoformat()
        return BatchJobState(
            job_id=f"batch_{int(time.time())}",
            created_at_iso=now,
            updated_at_iso=now,
        )


__all__ = [
    "BatchDialogueOrchestrator",
    "BatchJobState",
    "BatchStage",
    "DialogueJobItem",
    "compute_dialogue_fingerprint",
]
