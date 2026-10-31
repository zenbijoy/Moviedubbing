"""Export preset manager for delivery specs."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExportPreset:
    name: str
    container: str
    video_codec: str
    audio_codec: str
    audio_bitrate_kbps: int
    sample_rate: int
    loudness_target_lufs: float


DEFAULT_PRESETS: dict[str, ExportPreset] = {
    "netflix": ExportPreset("Netflix", "mkv", "h264", "aac", 320, 48000, -24.0),
    "youtube": ExportPreset("YouTube", "mp4", "h264", "aac", 192, 48000, -14.0),
    "theatrical": ExportPreset("Theatrical", "mov", "prores", "pcm", 1536, 48000, -27.0),
    "broadcast": ExportPreset("Broadcast", "mxf", "mpeg2", "pcm", 1536, 48000, -23.0),
}


class ExportPresetManager:
    def __init__(self, presets: dict[str, ExportPreset] | None = None) -> None:
        self.presets = dict(presets or DEFAULT_PRESETS)

    def get(self, key: str) -> ExportPreset:
        if key not in self.presets:
            raise KeyError(f"Unknown preset: {key}")
        return self.presets[key]

    def add(self, key: str, preset: ExportPreset) -> None:
        self.presets[key] = preset

    def remove(self, key: str) -> None:
        self.presets.pop(key, None)

    def list_keys(self) -> list[str]:
        return sorted(self.presets.keys())

    def for_loudness(self, target_lufs: float) -> list[ExportPreset]:
        return [p for p in self.presets.values() if abs(p.loudness_target_lufs - target_lufs) < 1e-6]


__all__ = ["ExportPreset", "ExportPresetManager", "DEFAULT_PRESETS"]
