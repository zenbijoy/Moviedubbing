"""Worker handler registry.

Only stable, explicitly registered job types can execute. Arbitrary module or
callable names are never accepted from a project file.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from aidub.contracts.jobs import JobDescriptor, JobProgress

from .context import WorkerContext

Handler = Callable[[JobDescriptor, WorkerContext], dict[str, Any]]


def _health_check(job: JobDescriptor, context: WorkerContext) -> dict[str, Any]:
    context.checkpoint()
    return {"status": "healthy", "job_type": job.job_type}


def _echo(job: JobDescriptor, context: WorkerContext) -> dict[str, Any]:
    context.checkpoint()
    return {
        "echo_json": json.dumps(
            job.parameters,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    }


def _cooperative_wait(job: JobDescriptor, context: WorkerContext) -> dict[str, Any]:
    duration_ms = int(job.parameters.get("duration_ms", 0))
    if not 0 <= duration_ms <= 60_000:
        raise ValueError("duration_ms must be between 0 and 60000")
    step_ms = max(1, min(50, duration_ms or 1))
    elapsed = 0
    total = max(duration_ms, 1)
    while elapsed < duration_ms:
        context.checkpoint()
        time.sleep(step_ms / 1000)
        elapsed = min(duration_ms, elapsed + step_ms)
        context.progress(
            JobProgress(
                job_id=job.job_id,
                completed_units=max(elapsed, 1),
                total_units=total,
                unit_name="milliseconds",
            )
        )
    context.checkpoint()
    return {"waited_ms": duration_ms}


def _crash(_job: JobDescriptor, _context: WorkerContext) -> dict[str, Any]:
    # This handler exists only for the crash-containment integration test.
    raise SystemExit(87)


def _speech_asr(job: JobDescriptor, context: WorkerContext) -> dict[str, Any]:
    context.checkpoint()
    from aidub.adapters.asr_whisper import FasterWhisperAdapter, FasterWhisperOptions
    from aidub.speech.contracts import SpeechRecognitionRequest
    from aidub.speech.runtime import CallbackRecognitionRuntime

    request = SpeechRecognitionRequest.model_validate(job.parameters["request"])
    options_raw = job.parameters.get("options")
    options = (
        FasterWhisperOptions.model_validate(options_raw)
        if options_raw is not None
        else FasterWhisperOptions()
    )

    source_audio_path = job.parameters.get("source_audio_path")
    adapter = FasterWhisperAdapter(options, source_audio_path=source_audio_path)
    runtime = CallbackRecognitionRuntime(
        is_cancelled=context.is_cancelled,
        on_progress=lambda p: context.progress(
            JobProgress(
                job_id=job.job_id,
                completed_units=p.completed_samples,
                total_units=p.total_samples,
                unit_name="audio_samples",
            )
        ),
    )

    result = adapter.recognize(request, runtime=runtime)
    context.checkpoint()
    return {"result_json": json.dumps(result.model_dump(mode="json"))}


def _speech_diarize(job: JobDescriptor, context: WorkerContext) -> dict[str, Any]:
    context.checkpoint()
    from aidub.adapters.diarization_pyannote import (
        PyannoteDiarizationAdapter,
        PyannoteDiarizationOptions,
        cluster_speaker_embeddings,
    )
    from aidub.domain.time import AudioSampleRange
    from aidub.domain.types import Sha256

    audio_range = AudioSampleRange.model_validate(job.parameters["audio_range"])
    source_sha256 = Sha256(job.parameters["source_audio_sha256"])
    options_raw = job.parameters.get("options")
    options = (
        PyannoteDiarizationOptions.model_validate(options_raw)
        if options_raw is not None
        else PyannoteDiarizationOptions()
    )

    adapter = PyannoteDiarizationAdapter(options)
    raw_result = adapter.diarize(
        audio_range,
        source_sha256,
        source_audio_path=job.parameters.get("source_audio_path"),
    )
    context.checkpoint()

    # Apply acoustic speaker clustering
    clustered_segments = cluster_speaker_embeddings(
        raw_result.segments, threshold=options.clustering_threshold
    )

    final_result = raw_result.model_copy(update={"segments": clustered_segments})
    return {"result_json": json.dumps(final_result.model_dump(mode="json"))}


def _media_separate_stems(job: JobDescriptor, context: WorkerContext) -> dict[str, Any]:
    context.checkpoint()
    from aidub.adapters.separation_demucs import DemucsSeparationOptions
    from aidub.media.stems import StemSelectionPolicy, StemSelector

    source_path = str(job.parameters["source_audio_path"])
    output_dir = str(job.parameters["output_directory"])
    policy_str = job.parameters.get("policy", StemSelectionPolicy.PREFER_STUDIO_ME)
    policy = StemSelectionPolicy(policy_str)

    options_raw = job.parameters.get("options")
    options = (
        DemucsSeparationOptions.model_validate(options_raw)
        if options_raw is not None
        else DemucsSeparationOptions()
    )

    from aidub.adapters.separation_demucs import DemucsSeparationAdapter

    adapter = DemucsSeparationAdapter(options)
    selector = StemSelector(adapter)

    selection = selector.process_stems(
        source_path,
        output_dir,
        policy=policy,
    )
    context.checkpoint()
    return {"result_json": json.dumps(selection.model_dump(mode="json"))}


def _voice_synthesize(job: JobDescriptor, context: WorkerContext) -> dict[str, Any]:
    context.checkpoint()
    from aidub.workers.tts_worker import run_tts_synthesis

    result = run_tts_synthesis(job.parameters)
    context.checkpoint()
    return {"result_json": json.dumps(result)}


def _lipsync_render(job: JobDescriptor, context: WorkerContext) -> dict[str, Any]:
    context.checkpoint()
    from aidub.workers.lipsync_worker import run_lipsync_render

    result = run_lipsync_render(job.parameters)
    context.checkpoint()
    return {"result_json": json.dumps(result)}


HANDLERS: dict[str, Handler] = {
    "system.health": _health_check,
    "system.echo": _echo,
    "system.wait": _cooperative_wait,
    "system.crash_test": _crash,
    "speech.asr": _speech_asr,
    "speech.diarize": _speech_diarize,
    "media.separate_stems": _media_separate_stems,
    "voice.synthesize": _voice_synthesize,
    "lipsync.render": _lipsync_render,
}


def get_handler(job_type: str) -> Handler:
    try:
        return HANDLERS[job_type]
    except KeyError as exc:
        raise ValueError(f"unsupported worker job type: {job_type}") from exc
