"""PipelineConfig dataclass for DubbingEngine configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PipelineConfig:
    """Master pipeline configuration parameters."""

    input: Path
    output: Path
    src_lang: str = "auto"
    tgt_lang: str = "bn"
    work_dir: Path | None = None

    # Stages that have real pipeline implementations.
    dub: bool = True
    keep_music: bool = True
    diarize: bool = True
    lipsync: bool = False
    lipsync_tier: str = "preview_fast"

    # Configured analysis and speech providers.
    asr_model: str = "large-v3"
    voice_name: str | None = None
    character_voices: dict[str, str] | None = None
    max_stretch: float = 2.0
    overwrite: bool = False


__all__ = ["PipelineConfig"]
