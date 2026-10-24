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
    fast: bool = False

    # Configured analysis and speech providers.
    asr_model: str = "large-v3"
    voice_name: str | None = None
    voice_engine: str = "gemini_tts"
    character_voices: dict[str, str] | None = None
    rvc_cloning: bool = True
    max_stretch: float = 2.0
    overwrite: bool = False

    # Professional Studio & Broadcast Mastering
    isometric_alignment: bool = True
    acoustic_preset: str = "none"
    broadcast_spec: str = "netflix"

    def __post_init__(self) -> None:
        if self.fast:
            self.keep_music = False
            self.diarize = False
            self.lipsync = False
            self.rvc_cloning = False
            if self.asr_model == "large-v3":
                self.asr_model = "base"


__all__ = ["PipelineConfig"]
