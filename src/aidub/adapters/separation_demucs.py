"""Demucs local audio source separation engine adapter for M&E stem preservation."""

from __future__ import annotations

import hashlib
import logging
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import Field, model_validator

from aidub.contracts.base import ContractModel, Identifier
from aidub.domain.types import SemanticVersion, Sha256
from aidub.speech.contracts import SpeechEngineIdentity
from aidub.speech.runtime import RecognitionRuntime

logger = logging.getLogger(__name__)


class StemKind(StrEnum):
    """Isolated audio stem types recognized by the production engine."""

    DIALOGUE = "dialogue"
    MUSIC = "music"
    EFFECTS = "effects"
    MUSIC_AND_EFFECTS = "music_and_effects"
    OTHER = "other"


class DemucsSeparationOptions(ContractModel):
    """Configuration options for Demucs AI source separation."""

    model_name: str = Field(default="htdemucs", min_length=1, max_length=64)
    device: str = Field(default="cuda", min_length=1, max_length=32)
    shifts: int = Field(default=1, ge=1, le=10)
    overlap: float = Field(default=0.25, ge=0.0, le=0.9)
    segment_length: float = Field(default=10.0, ge=1.0, le=60.0)

    @model_validator(mode="after")
    def _validate_options(self) -> Self:
        if self.device not in {"cuda", "cpu"}:
            raise ValueError(f"unsupported device: {self.device}")
        return self


class SeparatedStem(ContractModel):
    """An isolated audio stem artifact output file."""

    stem_kind: StemKind
    stem_path: str = Field(min_length=1)
    sample_rate: int = Field(default=48_000, gt=0)
    channels: int = Field(default=2, ge=1, le=8)
    sample_count: int = Field(ge=0)


class SourceSeparationResult(ContractModel):
    """Output descriptor for source separation."""

    engine: SpeechEngineIdentity
    stems: tuple[SeparatedStem, ...] = ()
    me_preserved: bool = Field(default=True)

    def get_stem(self, kind: StemKind) -> SeparatedStem | None:
        for stem in self.stems:
            if stem.stem_kind == kind:
                return stem
        return None


class DemucsSeparationAdapter:
    """Local Demucs source separation engine adapter for dialogue / M&E separation."""

    def __init__(self, options: DemucsSeparationOptions | None = None) -> None:
        self.options = options or DemucsSeparationOptions()
        model_hash = hashlib.sha256(
            f"{self.options.model_name}-{self.options.shifts}".encode()
        ).hexdigest()
        self._identity = SpeechEngineIdentity(
            engine_id=Identifier("demucs-separation"),
            engine_version=SemanticVersion("4.0.0"),
            model_id=Identifier(self.options.model_name),
            model_version=SemanticVersion("4.0.0"),
            model_weights_sha256=Sha256(model_hash),
        )
        self._separator_instance: Any | None = None

    @property
    def identity(self) -> SpeechEngineIdentity:
        return self._identity

    def separate(
        self,
        source_audio_path: str,
        output_directory: str,
        *,
        runtime: RecognitionRuntime | None = None,
    ) -> SourceSeparationResult:
        """Separate audio file into Dialogue, Music, Effects, and Other stems."""

        if runtime is not None:
            runtime.checkpoint()

        source_path = Path(source_audio_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"source audio does not exist: {source_path}")
        try:
            import demucs.api  # type: ignore[import-not-found]
            from demucs.audio import save_audio  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Demucs is not installed; install the production source-separation dependencies"
            ) from exc

        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)

        if self._separator_instance is None:
            self._separator_instance = demucs.api.Separator(
                model=self.options.model_name,
                device=self.options.device,
                shifts=self.options.shifts,
                overlap=self.options.overlap,
            )

        # Execute demucs separation
        _origin, separated = self._separator_instance.separate_audio_file(str(source_path))
        stems: list[SeparatedStem] = []
        sample_rate = int(self._separator_instance.samplerate)

        mapping = {
            "vocals": StemKind.DIALOGUE,
            "drums": StemKind.EFFECTS,
            "bass": StemKind.OTHER,
            "other": StemKind.MUSIC,
        }

        for name, tensor in separated.items():
            if runtime is not None:
                runtime.checkpoint()
            kind = mapping.get(name, StemKind.OTHER)
            stem_file = out_dir / f"stem_{kind.value}.wav"
            save_audio(tensor, stem_file, sample_rate, clip="rescale")
            if not stem_file.is_file() or stem_file.stat().st_size == 0:
                raise RuntimeError(f"Demucs produced an empty {name} stem")
            stems.append(
                SeparatedStem(
                    stem_kind=kind,
                    stem_path=str(stem_file),
                    sample_rate=sample_rate,
                    channels=int(tensor.shape[-2]),
                    sample_count=int(tensor.shape[-1]),
                )
            )

        return SourceSeparationResult(
            engine=self.identity,
            stems=tuple(stems),
            me_preserved=True,
        )

__all__ = [
    "DemucsSeparationAdapter",
    "DemucsSeparationOptions",
    "SeparatedStem",
    "SourceSeparationResult",
    "StemKind",
]
