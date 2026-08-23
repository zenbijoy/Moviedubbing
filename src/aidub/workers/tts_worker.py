"""TTS synthesis worker — registered as 'voice.synthesize' job handler."""

from __future__ import annotations

import logging

from aidub.adapters.voice.edge_tts_adapter import EdgeTTSVoiceEngine
from aidub.adapters.voice_base import SynthesisRequest, VoiceEngine
from aidub.contracts.base import ContractModel

logger = logging.getLogger(__name__)


class TtsSynthesisJob(ContractModel):
    """Input payload for a TTS synthesis worker job."""

    request: SynthesisRequest
    output_directory: str


def run_tts_synthesis(payload: dict, *, engine: VoiceEngine | None = None) -> dict:
    """
    Worker handler for 'voice.synthesize' job type.

    Args:
        payload: Raw dict job payload (will be parsed as TtsSynthesisJob).
        engine: Optional VoiceEngine override. Edge TTS is used by default.

    Returns:
        dict: SynthesisResult as a dict for persistence.
    """
    job = TtsSynthesisJob.model_validate(payload)
    active_engine = engine or EdgeTTSVoiceEngine()

    result = active_engine.synthesize(job.request, job.output_directory)
    logger.info(
        "tts_worker: synthesized %s (%dms) via %s",
        result.utterance_id,
        result.duration_ms,
        result.engine_kind,
    )
    return result.model_dump(mode="json")
