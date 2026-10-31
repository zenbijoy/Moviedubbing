"""Authoritative canonical Project file model (project.json).

Provides:
  - ProjectFile: versioned JSON project document containing source metadata,
    ffprobe media profile, editable speech segments, pipeline stage statuses,
    and editorial settings.
  - SegmentModel: single utterance / subtitle / dub segment with timing, text,
    generated audio paths, status, and QC issue tags.
  - StageStatus: tracking per-stage pipeline execution state.
  - ProjectProbeInfo: ffprobe media parameters.
  - Atomic read/write operations and source file hash computation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PROJECT_JSON_FILENAME = "project.json"


class SegmentModel(BaseModel):
    """A discrete dialogue segment or subtitle event."""

    id: str
    start: float
    end: float
    speaker: str = "SPEAKER_00"
    original: str = ""
    translation: str = ""
    tts_path: str = ""
    fitted_path: str = ""
    status: str = "pending"  # pending, transcribed, translated, synthesized, fitted, approved
    qc_issues: list[str] = Field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class StageStatus(BaseModel):
    """Pipeline automation lifecycle stage statuses."""

    extract: str = "pending"     # pending, running, completed, failed, skipped
    transcribe: str = "pending"
    translate: str = "pending"
    synthesize: str = "pending"
    mix: str = "pending"
    export: str = "pending"


class ProjectProbeInfo(BaseModel):
    """Source media technical parameters discovered via ffprobe."""

    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_codec: str = ""
    sample_rate: int = 48000
    channels: int = 2
    audio_streams: list[dict[str, Any]] = Field(default_factory=list)


class ProjectFileSettings(BaseModel):
    """Per-project editorial and AI configuration."""

    source_language: str = "en"
    target_language: str = "bn"
    asr_model_size: str = "base"
    translation_engine: str = "nllb-200"
    tts_voice: str = "bn-BD-PradeepNeural"
    device: str = "auto"
    sidechain_ducking: bool = True
    ducking_depth_db: float = 12.0


class ProjectFile(BaseModel):
    """Authoritative project document saved to project.json."""

    version: int = 1
    name: str = "Untitled Project"
    project_path: str = ""
    source_file: str = ""
    source_hash: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    probe: ProjectProbeInfo = Field(default_factory=ProjectProbeInfo)
    settings: ProjectFileSettings = Field(default_factory=ProjectFileSettings)
    stage_status: StageStatus = Field(default_factory=StageStatus)
    segments: list[SegmentModel] = Field(default_factory=list)

    @staticmethod
    def compute_file_hash(path: Path | str) -> str:
        """Compute SHA256 checksum of source media file."""
        target = Path(path)
        if not target.is_file():
            return ""
        hasher = hashlib.sha256()
        with target.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def save(self, target_path: Path | str | None = None) -> Path:
        """Atomically persist this project to project.json."""
        if target_path is not None:
            p = Path(target_path)
            if p.is_dir() or p.suffix != ".json":
                p = p / PROJECT_JSON_FILENAME
            self.project_path = str(p.resolve())
        elif self.project_path:
            p = Path(self.project_path)
        else:
            raise ValueError("No project path specified for save")

        p.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(timezone.utc).isoformat()

        tmp_path = p.with_suffix(".tmp")
        payload = self.model_dump_json(indent=2)
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(p)
        logger.info("Project saved atomically to %s", p)
        return p

    @classmethod
    def load(cls, path: Path | str) -> ProjectFile:
        """Load and validate project.json from disk."""
        p = Path(path)
        if p.is_dir():
            p = p / PROJECT_JSON_FILENAME
        if not p.is_file():
            raise FileNotFoundError(f"Project file not found: {p}")

        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        instance = cls.model_validate(data)
        instance.project_path = str(p.resolve())
        logger.info("Loaded project from %s (%d segments)", p, len(instance.segments))
        return instance

    def get_segment(self, segment_id: str) -> SegmentModel | None:
        """Look up segment by ID."""
        for seg in self.segments:
            if seg.id == segment_id:
                return seg
        return None

    def upsert_segment(self, segment: SegmentModel) -> None:
        """Insert or update a segment by its ID."""
        for i, existing in enumerate(self.segments):
            if existing.id == segment.id:
                self.segments[i] = segment
                return
        self.segments.append(segment)
        self.segments.sort(key=lambda s: s.start)


__all__ = [
    "PROJECT_JSON_FILENAME",
    "ProjectFile",
    "ProjectFileSettings",
    "ProjectProbeInfo",
    "SegmentModel",
    "StageStatus",
]
