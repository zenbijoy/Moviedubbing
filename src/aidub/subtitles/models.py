"""
Rich internal dialogue, track, validation, and summary dataclass models.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class DialogueSegment:
    """Rich atomic dialogue segment model for movie localization pipeline."""

    id: str = field(default_factory=lambda: f"seg_{uuid.uuid4().hex[:8]}")
    subtitle_index: int = 1

    start_ms: int = 0
    end_ms: int = 0
    duration_ms: int = 0

    original_text: str = ""
    translated_text: str = ""
    adapted_text: str = ""

    speaker_id: str | None = None
    character_name: str | None = None

    language: str | None = "en"

    emotion: str | None = None
    emotion_intensity: float | None = None

    speech_style: str | None = None
    has_hesitation: bool = False
    possible_multi_speaker: bool = False
    speaker_count_estimate: int = 1

    voice_id: str | None = None

    # Pipeline Processing Status: imported, translated, adapted, voice_generated, aligned, lip_synced, reviewed, approved, rendered
    status: str = "imported"

    # Human Review Status: unreviewed, reviewed, approved, locked
    review_status: str = "unreviewed"

    confidence: float | None = None
    lip_sync_score: float | None = None

    word_count: int = 0
    character_count: int = 0
    estimated_speech_rate: float = 0.0
    has_question: bool = False
    has_exclamation: bool = False
    segment_hash: str = ""

    def __post_init__(self) -> None:
        if self.duration_ms <= 0 and self.end_ms > self.start_ms:
            self.duration_ms = self.end_ms - self.start_ms
        if self.original_text:
            cleaned = self.original_text.strip()
            words = [w for w in cleaned.split() if w]
            self.word_count = len(words)
            self.character_count = len(cleaned)
            sec = self.duration_ms / 1000.0 if self.duration_ms > 0 else 1.0
            self.estimated_speech_rate = round(self.word_count / sec, 2)
            self.has_question = "?" in cleaned
            self.has_exclamation = "!" in cleaned

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DialogueSegment:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SubtitleTrack:
    """Normalized multi-segment subtitle track."""

    track_id: str = field(default_factory=lambda: f"trk_{uuid.uuid4().hex[:8]}")
    name: str = "Original Subtitles"
    source_file: str = ""
    source_format: str = "srt"
    source_language: str = "en"
    encoding: str = "UTF-8"
    segments: list[DialogueSegment] = field(default_factory=list)
    created_at: str = ""
    content_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "name": self.name,
            "source_file": self.source_file,
            "source_format": self.source_format,
            "source_language": self.source_language,
            "encoding": self.encoding,
            "created_at": self.created_at,
            "content_hash": self.content_hash,
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubtitleTrack:
        raw_segs = data.get("segments", [])
        segs = [DialogueSegment.from_dict(s) for s in raw_segs]
        kw = {k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "segments"}
        return cls(segments=segs, **kw)


@dataclass
class ValidationWarning:
    """Subtitle validation warning item."""

    category: str  # timing_overlap, duration_negative, missing_text, max_duration_exceeded, etc.
    message: str
    subtitle_index: int | None = None
    segment_id: str | None = None
    severity: str = "warning"  # warning, info, critical


@dataclass
class ValidationReport:
    """Subtitle validation report summary."""

    total_parsed: int = 0
    valid_count: int = 0
    warning_count: int = 0
    skipped_count: int = 0
    overlap_count: int = 0
    duplicate_count: int = 0
    multi_speaker_count: int = 0
    warnings: list[ValidationWarning] = field(default_factory=list)


@dataclass
class ImportSummary:
    """Post-import summary report for user display."""

    file_name: str
    format: str
    encoding: str
    detected_language: str
    segment_count: int
    first_timestamp_ms: int
    last_timestamp_ms: int
    movie_duration_ms: int | None
    multi_speaker_count: int
    timing_overlaps: int
    warning_count: int
    status_message: str
    validation_report: ValidationReport | None = None


__all__ = [
    "DialogueSegment",
    "SubtitleTrack",
    "ValidationWarning",
    "ValidationReport",
    "ImportSummary",
]
