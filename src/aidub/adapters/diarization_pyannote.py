"""Pyannote.audio local speaker diarization adapter & speaker embedding clustering."""

from __future__ import annotations

import hashlib
import logging
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Self

# Compatibility shims for torchaudio 2.6+ / 2.11+ where AudioMetaData and
# list_audio_backends were refactored, preventing pyannote.audio from crashing on import.
try:
    import torchaudio

    if not hasattr(torchaudio, "AudioMetaData"):
        from dataclasses import dataclass

        @dataclass
        class AudioMetaData:
            sample_rate: int
            num_frames: int
            num_channels: int
            bits_per_sample: int
            encoding: str

        torchaudio.AudioMetaData = AudioMetaData

    if not hasattr(torchaudio, "list_audio_backends"):
        torchaudio.list_audio_backends = lambda: ["soundfile"]
except ImportError:
    pass

# Compatibility shim for modern huggingface_hub (v0.24+) where use_auth_token was
# removed in favor of token, preventing pyannote.audio from crashing on hf_hub_download.
try:
    import huggingface_hub
    import huggingface_hub.file_download

    _orig_hf_hub_download = huggingface_hub.file_download.hf_hub_download

    def _compat_hf_hub_download(*args: Any, **kwargs: Any) -> Any:
        if "use_auth_token" in kwargs:
            auth_val = kwargs.pop("use_auth_token")
            if "token" not in kwargs:
                kwargs["token"] = auth_val
        return _orig_hf_hub_download(*args, **kwargs)

    huggingface_hub.file_download.hf_hub_download = _compat_hf_hub_download
    huggingface_hub.hf_hub_download = _compat_hf_hub_download
except (ImportError, AttributeError):
    pass

from pydantic import Field, model_validator

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.time import AudioSamplePosition, AudioSampleRange
from aidub.domain.types import SemanticVersion, Sha256
from aidub.speech.contracts import SpeechEngineIdentity
from aidub.speech.runtime import RecognitionRuntime

logger = logging.getLogger(__name__)


class PyannoteDiarizationOptions(ContractModel):
    """Configuration options for Pyannote speaker diarization."""

    model_id: str = Field(default="pyannote/speaker-diarization-3.1", min_length=1, max_length=128)
    device: str = Field(default="cuda", min_length=1, max_length=32)
    num_speakers: int | None = Field(default=None, ge=1, le=32)
    min_speakers: int | None = Field(default=None, ge=1, le=32)
    max_speakers: int | None = Field(default=None, ge=1, le=32)
    clustering_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_options(self) -> Self:
        if self.device not in {"cuda", "cpu"}:
            raise ValueError(f"unsupported device: {self.device}")
        if self.min_speakers and self.max_speakers and self.min_speakers > self.max_speakers:
            raise ValueError("min_speakers cannot exceed max_speakers")
        return self


class DiarizedSpeakerSegment(ContractModel):
    """A continuous audio range attributed to a specific speaker identity."""

    segment_id: Identifier
    speaker_id: Identifier
    audio_range: AudioSampleRange
    confidence: float = Field(ge=0.0, le=1.0)
    embedding: tuple[float, ...] = Field(default=())


class SpeakerDiarizationResult(ContractModel):
    """Complete output of a speaker diarization run."""

    engine: SpeechEngineIdentity
    segments: tuple[DiarizedSpeakerSegment, ...] = ()
    speaker_ids: tuple[Identifier, ...] = ()
    der_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @property
    def speaker_count(self) -> int:
        return len(self.speaker_ids)


class PyannoteDiarizationAdapter:
    """Speaker diarization engine adapter supporting Pyannote.audio and acoustic clustering."""

    def __init__(self, options: PyannoteDiarizationOptions | None = None) -> None:
        self.options = options or PyannoteDiarizationOptions()
        model_hash = hashlib.sha256(
            f"{self.options.model_id}-{self.options.clustering_threshold}".encode()
        ).hexdigest()
        self._identity = SpeechEngineIdentity(
            engine_id=Identifier("pyannote-diarization"),
            engine_version=SemanticVersion("3.1.0"),
            model_id=Identifier("pyannote-diarization-3.1"),
            model_version=SemanticVersion("3.1.0"),
            model_weights_sha256=Sha256(model_hash),
        )
        self._pipeline_instance: Any | None = None

    def _pipeline(self) -> Any:
        try:
            import pyannote.audio
        except ImportError as exc:
            raise RuntimeError(
                "Pyannote.audio is not installed; install the production diarization dependencies"
            ) from exc
        if self._pipeline_instance is None:
            token = os.environ.get("AIDUB_PYANNOTE_TOKEN") or os.environ.get("PYANNOTE_TOKEN") or os.environ.get("HF_TOKEN")
            try:
                self._pipeline_instance = pyannote.audio.Pipeline.from_pretrained(
                    self.options.model_id,
                    use_auth_token=token,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Pyannote could not load the diarization model ({exc}); verify Hugging Face access or PYANNOTE_TOKEN"
                ) from exc
            if self._pipeline_instance is None:
                raise RuntimeError(
                    "Pyannote could not load the diarization model; verify Hugging Face access or PYANNOTE_TOKEN"
                )
            try:
                import torch

                device = self.options.device
                if device == "cuda" and not torch.cuda.is_available():
                    device = "cpu"
                self._pipeline_instance.to(torch.device(device))
            except Exception:
                pass
        return self._pipeline_instance

    @property
    def identity(self) -> SpeechEngineIdentity:
        return self._identity

    def diarize(
        self,
        audio_range: AudioSampleRange,
        source_audio_sha256: Sha256,
        *,
        source_audio_path: str | Path | None = None,
        runtime: RecognitionRuntime | None = None,
    ) -> SpeakerDiarizationResult:
        """Diarize an audio range into distinct speaker turns and embeddings."""

        del source_audio_sha256

        if runtime is not None:
            runtime.checkpoint()

        if source_audio_path is None or not Path(source_audio_path).is_file():
            raise RuntimeError("a real source_audio_path is required for speaker diarization")
        diarization_output = self._pipeline()(str(source_audio_path))
        segments: list[DiarizedSpeakerSegment] = []
        speaker_ids_set: set[str] = set()

        sample_rate = audio_range.sample_rate
        offset = audio_range.start.sample_index

        for idx, (turn, _, speaker) in enumerate(diarization_output.itertracks(yield_label=True)):
            if runtime is not None:
                runtime.checkpoint()
            spk_id = f"spk_{speaker.lower().replace(' ', '_')}"
            speaker_ids_set.add(spk_id)

            start_sample = offset + int(turn.start * sample_rate)
            end_sample = offset + int(turn.end * sample_rate)
            count = max(1, end_sample - start_sample)

            seg_range = AudioSampleRange(
                start=AudioSamplePosition(sample_index=start_sample, sample_rate=sample_rate),
                sample_count=count,
            )

            segments.append(
                DiarizedSpeakerSegment(
                    segment_id=Identifier(f"diar_seg_{idx}"),
                    speaker_id=Identifier(spk_id),
                    audio_range=seg_range,
                    confidence=0.0,
                    embedding=(),
                )
            )

        sorted_spk_ids = tuple(Identifier(s) for s in sorted(speaker_ids_set))
        return SpeakerDiarizationResult(
            engine=self.identity,
            segments=tuple(segments),
            speaker_ids=sorted_spk_ids,
            der_score=None,
        )

    def turns(
        self,
        audio_path: str,
        merge_gap: float = 0.8,
        min_speaker_dur: float = 2.5,
    ) -> tuple[list[tuple[float, float, int]], int, dict[int, tuple[float, float]]]:
        """
        Extract speaker turns from audio file for diarize-first ASR & cloning.

        Rules:
        - Merges consecutive same-speaker turns if gap <= merge_gap.
        - Speakers with total duration < min_speaker_dur are reassigned to nearest speaker.
        - Returns ref_windows: each speaker's single longest clean turn (start, end) for cloning.

        Returns:
            Tuple of (turns_list [(start, end, speaker_int)], total_speakers_count, ref_windows_dict).
        """
        raw_turns: list[tuple[float, float, int]] = []
        source = Path(audio_path)
        if not source.is_file():
            raise FileNotFoundError(f"diarization source audio does not exist: {source}")
        try:
            diarization_output = self._pipeline()(str(source))
            speaker_numbers: dict[str, int] = {}
            for turn, _, speaker in diarization_output.itertracks(yield_label=True):
                label = str(speaker)
                speaker_number = speaker_numbers.setdefault(label, len(speaker_numbers))
                raw_turns.append((float(turn.start), float(turn.end), speaker_number))
        except Exception as exc:
            logger.warning(
                "Pyannote diarization failed or model unauthorized: %s. Using single-speaker fallback.",
                exc,
            )
            from aidub.media.ffmpeg_ops import duration

            try:
                dur = duration(source)
            except Exception:
                dur = 30.0
            return [(0.0, dur, 0)], 1, {0: (0.0, dur)}

        raw_turns.sort(key=lambda x: x[0])

        # Merge consecutive same-speaker turns
        merged: list[tuple[float, float, int]] = []
        for a, b, spk in raw_turns:
            if merged and merged[-1][2] == spk and (a - merged[-1][1]) <= merge_gap:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b), spk)
            else:
                merged.append((a, b, spk))

        # Check total speaker durations
        spk_durs: dict[int, float] = defaultdict(float)
        for a, b, spk in merged:
            spk_durs[spk] += b - a

        real_spks = {spk for spk, dur in spk_durs.items() if dur >= min_speaker_dur}
        if not real_spks:
            real_spks = {0}

        # Filter and compute ref_windows (longest turn per speaker)
        final_turns: list[tuple[float, float, int]] = []
        ref_windows: dict[int, tuple[float, float]] = {}

        for a, b, spk in merged:
            target_spk = spk if spk in real_spks else min(real_spks, key=lambda s: abs(s - spk))
            final_turns.append((a, b, target_spk))

            dur = b - a
            if target_spk not in ref_windows or (
                dur > (ref_windows[target_spk][1] - ref_windows[target_spk][0])
            ):
                ref_windows[target_spk] = (a, b)

        n_speakers = len(set(ref_windows.keys()))
        return final_turns, max(1, n_speakers), ref_windows


def cluster_speaker_embeddings(
    segments: tuple[DiarizedSpeakerSegment, ...],
    threshold: float = 0.7,
) -> tuple[DiarizedSpeakerSegment, ...]:
    """Cosine-similarity acoustic speaker clustering to merge duplicate speaker IDs."""

    if not segments:
        return ()

    centroids: list[list[float]] = []
    canonical_spk_ids: list[Identifier] = []

    clustered: list[DiarizedSpeakerSegment] = []

    for seg in segments:
        if not seg.embedding:
            clustered.append(seg)
            continue

        matched_idx: int | None = None
        best_sim = -1.0

        for idx, cent in enumerate(centroids):
            sim = _cosine_similarity(seg.embedding, cent)
            if sim >= threshold and sim > best_sim:
                best_sim = sim
                matched_idx = idx

        if matched_idx is not None:
            canon_spk = canonical_spk_ids[matched_idx]
            # Update centroid
            old_cent = centroids[matched_idx]
            centroids[matched_idx] = [
                0.5 * (a + b) for a, b in zip(old_cent, seg.embedding, strict=True)
            ]
        else:
            canon_spk = Identifier(f"spk_{len(centroids):02d}")
            centroids.append(list(seg.embedding))
            canonical_spk_ids.append(canon_spk)

        clustered.append(
            DiarizedSpeakerSegment(
                segment_id=seg.segment_id,
                speaker_id=canon_spk,
                audio_range=seg.audio_range,
                confidence=seg.confidence,
                embedding=seg.embedding,
            )
        )

    return tuple(clustered)


def _cosine_similarity(v1: tuple[float, ...], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


__all__ = [
    "DiarizedSpeakerSegment",
    "PyannoteDiarizationAdapter",
    "PyannoteDiarizationOptions",
    "SpeakerDiarizationResult",
    "cluster_speaker_embeddings",
]
