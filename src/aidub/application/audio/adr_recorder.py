"""
ADR Recording, Take Lanes, and Take Comping Assembly Service.

Provides Nuendo/ProTools grade dialogue ADR workflow:
  - Multi-take recording per cue (Take 1, Take 2, Take 3...).
  - Active take switching with zero project disruption.
  - Sub-word / sub-phrase comping assembly with smooth anti-click crossfades.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import numpy as np

from aidub.domain.audio_edit import CompingRegion, Take
from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine

logger = logging.getLogger(__name__)


@dataclass
class AdrTakeLane:
    """Manages recording takes and comping regions for a single dialogue cue."""

    cue_id: str
    takes: list[Take] = field(default_factory=list)
    active_take_id: str | None = None
    comping_regions: list[CompingRegion] = field(default_factory=list)

    def get_take(self, take_id: str) -> Take | None:
        for t in self.takes:
            if t.take_id == take_id:
                return t
        return None

    def get_active_take(self) -> Take | None:
        if self.active_take_id:
            return self.get_take(self.active_take_id)
        if self.takes:
            return self.takes[0]
        return None


class AdrRecorderService:
    """Orchestrates ADR retakes, take lanes, and comping assembly."""

    def __init__(
        self,
        storage_dir: Path | str = "work/adr_takes",
        dsp_engine: ProAudioDspEngine | None = None,
    ) -> None:
        self.storage_dir: Path = Path(storage_dir)
        self.dsp_engine: ProAudioDspEngine = dsp_engine or ProAudioDspEngine()
        self._lanes: dict[str, AdrTakeLane] = {}
        self._clip_cache: dict[str, AudioClipData] = {}

    def get_or_create_lane(self, cue_id: str) -> AdrTakeLane:
        if cue_id not in self._lanes:
            self._lanes[cue_id] = AdrTakeLane(cue_id=cue_id)
        return self._lanes[cue_id]

    def register_take(
        self,
        cue_id: str,
        clip: AudioClipData,
        notes: str = "",
        auto_select: bool = True,
    ) -> Take:
        """Stores a new recorded or generated take for the cue."""
        lane = self.get_or_create_lane(cue_id)
        take_id = f"take_{cue_id}_{len(lane.takes) + 1}_{uuid4().hex[:6]}"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        take_path = self.storage_dir / f"{take_id}.wav"

        # Cache in memory and write to disk
        self._clip_cache[take_id] = clip
        self.dsp_engine.save_wav(clip, take_path)

        take = Take(
            take_id=take_id,
            cue_id=cue_id,
            audio_path=str(take_path),
            duration_s=clip.duration_s,
            created_at_s=time.time(),
            is_selected=auto_select,
            loudness_lufs=clip.rms_dbfs,
            true_peak_dbfs=clip.peak_dbfs,
            notes=notes,
        )
        lane.takes.append(take)
        if auto_select:
            lane.active_take_id = take_id
        return take

    def select_active_take(self, cue_id: str, take_id: str) -> bool:
        lane = self.get_or_create_lane(cue_id)
        take = lane.get_take(take_id)
        if not take:
            return False
        for t in lane.takes:
            t.is_selected = (t.take_id == take_id)
        lane.active_take_id = take_id
        return True

    def add_comping_region(
        self,
        cue_id: str,
        take_id: str,
        start_s: float,
        end_s: float,
        crossfade_s: float = 0.020,
        gain_db: float = 0.0,
    ) -> CompingRegion:
        """Adds a slice of take_id into the cue's comping assembly."""
        lane = self.get_or_create_lane(cue_id)
        region = CompingRegion(
            take_id=take_id,
            cue_id=cue_id,
            start_s=start_s,
            end_s=end_s,
            crossfade_duration_s=crossfade_s,
            gain_db=gain_db,
        )
        lane.comping_regions.append(region)
        return region

    def _get_take_clip(self, take: Take) -> AudioClipData:
        if take.take_id in self._clip_cache:
            return self._clip_cache[take.take_id]
        clip = self.dsp_engine.load_wav(Path(take.audio_path))
        self._clip_cache[take.take_id] = clip
        return clip

    def assemble_comped_take(self, cue_id: str) -> AudioClipData:
        """
        Assembles selected comping regions with S-curve crossfades.
        If no comping regions exist, returns the active take directly.
        """
        lane = self.get_or_create_lane(cue_id)
        if not lane.comping_regions:
            active_take = lane.get_active_take()
            if not active_take:
                return AudioClipData(samples=np.zeros(48000, dtype=np.float32), sample_rate=48000)
            return self._get_take_clip(active_take)

        sample_rate = 48000
        assembled_chunks: list[np.ndarray] = []

        for region in lane.comping_regions:
            take = lane.get_take(region.take_id)
            if not take:
                continue
            clip = self._get_take_clip(take)
            sample_rate = clip.sample_rate

            start_idx = int(round(region.start_s * sample_rate))
            end_idx = int(round(region.end_s * sample_rate))
            start_idx = max(0, min(start_idx, clip.samples.size))
            end_idx = max(start_idx, min(end_idx, clip.samples.size))

            chunk = clip.samples[start_idx:end_idx].copy()
            if region.gain_db != 0.0:
                factor = 10.0 ** (region.gain_db / 20.0)
                chunk = np.clip(chunk * factor, -1.0, 1.0)

            # Apply S-curve crossfade to start and end
            fade_len = int(round(region.crossfade_duration_s * sample_rate))
            if fade_len > 1 and chunk.size > (fade_len * 2):
                t = np.linspace(0.0, np.pi, fade_len)
                s_in = 0.5 * (1.0 - np.cos(t))
                s_out = 0.5 * (1.0 + np.cos(t))
                chunk[:fade_len] *= s_in
                chunk[-fade_len:] *= s_out

            assembled_chunks.append(chunk)

        if not assembled_chunks:
            return AudioClipData(samples=np.zeros(sample_rate, dtype=np.float32), sample_rate=sample_rate)

        final_samples = np.concatenate(assembled_chunks).astype(np.float32)
        return AudioClipData(samples=final_samples, sample_rate=sample_rate)


__all__ = [
    "AdrRecorderService",
    "AdrTakeLane",
]
