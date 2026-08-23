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

    # Pipeline mode flags
    mode: str = "auto"          # "auto" | "dub" | "nodub"
    dub: bool = True
    keep_music: bool = True
    diarize: bool = True
    captions: bool = False
    ctx_translate: bool = False

    # Models & Synthesis
    asr_model: str = "large-v3"
    tts_model: str = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    voice_mode: str = "clone"   # "clone" | "autocast" | "auto" | "voice"
    voice_name: str | None = None
    max_stretch: float = 2.0


__all__ = ["PipelineConfig"]
