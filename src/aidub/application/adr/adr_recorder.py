"""
Film ADR (Automated Dialogue Replacement) Engine.
Supports take management, scoring, selection, and seamless punch-in / punch-out crossfading.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

from aidub.media.pro_audio_editor import AudioClipData


@dataclass
class Take:
    take_id: str
    cue_id: str
    audio_path: str
    selected: bool = False
    duration_s: float = 0.0
    label: str = ""


@dataclass
class PunchInSession:
    """Active punch-in / punch-out recording state."""

    cue_id: str = "cue_001"
    punch_in_s: float = 0.0
    punch_out_s: float = 1.0
    pre_roll_s: float = 2.0
    post_roll_s: float = 1.0
    is_armed: bool = True
    is_recording: bool = False
    crossfade_ms: float = 15.0

    def __init__(
        self,
        cue_id: str = "cue_001",
        punch_in_s: float = 0.0,
        punch_out_s: float = 1.0,
        pre_roll_s: float = 2.0,
        post_roll_s: float = 1.0,
        is_armed: bool = True,
        is_recording: bool = False,
        crossfade_ms: float = 15.0,
        **kwargs: Any,
    ) -> None:
        self.cue_id = cue_id
        self.punch_in_s = kwargs.get("punch_in_time", punch_in_s)
        self.punch_out_s = kwargs.get("punch_out_time", punch_out_s)
        self.pre_roll_s = kwargs.get("pre_roll_sec", pre_roll_s)
        self.post_roll_s = kwargs.get("post_roll_sec", post_roll_s)
        self.is_armed = is_armed
        self.is_recording = is_recording
        self.crossfade_ms = kwargs.get("crossfade_ms", crossfade_ms)

    @property
    def punch_in_time(self) -> float:
        return self.punch_in_s

    @punch_in_time.setter
    def punch_in_time(self, val: float) -> None:
        self.punch_in_s = val

    @property
    def punch_out_time(self) -> float:
        return self.punch_out_s

    @punch_out_time.setter
    def punch_out_time(self, val: float) -> None:
        self.punch_out_s = val

    @property
    def pre_roll_sec(self) -> float:
        return self.pre_roll_s

    @pre_roll_sec.setter
    def pre_roll_sec(self, val: float) -> None:
        self.pre_roll_s = val

    @property
    def post_roll_sec(self) -> float:
        return self.post_roll_s

    @post_roll_sec.setter
    def post_roll_sec(self, val: float) -> None:
        self.post_roll_s = val

    @property
    def punch_duration_s(self) -> float:
        return max(0.01, self.punch_out_s - self.punch_in_s)


class ADRRecorder:
    """
    Film ADR studio recording orchestrator.
    Manages take lanes, selection, and seamless punch-in / punch-out take replacement.
    """

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self.takes: Dict[str, List[Take]] = {}
        self.active_session: PunchInSession | None = None

    def add_take(self, take: Take) -> None:
        self.takes.setdefault(take.cue_id, []).append(take)

    def select(self, cue_id: str, take_id: str) -> None:
        for t in self.takes.get(cue_id, []):
            t.selected = t.take_id == take_id

    def best_take(self, cue_id: str) -> Take | None:
        takes = self.takes.get(cue_id, [])
        if not takes:
            return None
        for t in takes:
            if t.selected:
                return t
        return takes[-1]

    def selected_take(self, cue_id: str) -> Take | None:
        return self.best_take(cue_id)

    def take_count(self, cue_id: str) -> int:
        return len(self.takes.get(cue_id, []))

    def arm_punch_in(
        self,
        cue_id: str,
        punch_in_s: float,
        punch_out_s: float,
        pre_roll_s: float = 2.0,
    ) -> PunchInSession:
        """Arms a non-destructive punch-in retake session."""
        self.active_session = PunchInSession(
            cue_id=cue_id,
            punch_in_s=punch_in_s,
            punch_out_s=punch_out_s,
            pre_roll_s=pre_roll_s,
            is_armed=True,
        )
        return self.active_session

    @classmethod
    def splice_punch_in(
        cls,
        base_clip: AudioClipData | np.ndarray | None = None,
        punch_clip: AudioClipData | np.ndarray | None = None,
        punch_in_s: float | None = None,
        punch_out_s: float | None = None,
        crossfade_ms: float = 12.0,
        **kwargs: Any,
    ) -> AudioClipData | np.ndarray:
        """
        Splices a newly recorded punch-in take into the base take with smooth S-curve crossfades.
        Preserves the exact total duration and sample length of base_clip.
        """
        if base_clip is None:
            base_clip = kwargs.get("base_samples")
        if punch_clip is None:
            punch_clip = kwargs.get("punch_samples")
        session: PunchInSession | None = kwargs.get("session")
        if session is not None:
            if punch_in_s is None:
                punch_in_s = session.punch_in_s
            if punch_out_s is None:
                punch_out_s = session.punch_out_s
            crossfade_ms = getattr(session, "crossfade_ms", crossfade_ms)

        if punch_in_s is None:
            punch_in_s = 0.0
        if punch_out_s is None:
            punch_out_s = 1.0

        is_array = isinstance(base_clip, np.ndarray)
        sr = kwargs.get("sample_rate", 44100)

        if isinstance(base_clip, AudioClipData):
            b_clip = base_clip
            sr = b_clip.sample_rate
        else:
            b_clip = AudioClipData(samples=np.asarray(base_clip, dtype=np.float32), sample_rate=sr)

        if isinstance(punch_clip, AudioClipData):
            p_clip = punch_clip
        else:
            p_clip = AudioClipData(samples=np.asarray(punch_clip, dtype=np.float32), sample_rate=sr)

        if b_clip.samples.size == 0:
            return p_clip.samples.copy() if is_array else p_clip.clone()
        if p_clip.samples.size == 0:
            return b_clip.samples.copy() if is_array else b_clip.clone()

        in_sample = int(max(0.0, punch_in_s) * sr)
        out_sample = int(min(b_clip.duration_s, punch_out_s) * sr)

        if in_sample >= out_sample or in_sample >= b_clip.samples.size:
            return b_clip.samples.copy() if is_array else b_clip.clone()

        punch_len = out_sample - in_sample
        p_samples = p_clip.samples
        if p_samples.size != punch_len:
            indices = np.linspace(0, p_samples.size - 1, punch_len)
            p_samples = np.interp(indices, np.arange(p_samples.size), p_samples).astype(np.float32)
        else:
            p_samples = p_samples.copy()

        combined = b_clip.samples.copy()
        combined[in_sample:out_sample] = p_samples

        fade_len = max(2, int(sr * (crossfade_ms / 1000.0)))

        # S-curve anti-click crossfade at punch-in point
        fade_in = min(fade_len, in_sample, punch_len // 2)
        if fade_in > 1:
            t = np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
            f_out = 0.5 * (1.0 + np.cos(t * np.pi))
            f_in = 0.5 * (1.0 - np.cos(t * np.pi))
            start_idx = in_sample
            combined[start_idx : start_idx + fade_in] = (
                b_clip.samples[start_idx : start_idx + fade_in] * f_out
                + p_samples[:fade_in] * f_in
            )

        # S-curve anti-click crossfade at punch-out point
        fade_out = min(fade_len, b_clip.samples.size - out_sample, punch_len // 2)
        if fade_out > 1:
            t = np.linspace(0.0, 1.0, fade_out, dtype=np.float32)
            f_out = 0.5 * (1.0 + np.cos(t * np.pi))
            f_in = 0.5 * (1.0 - np.cos(t * np.pi))
            start_idx = out_sample - fade_out
            combined[start_idx:out_sample] = (
                p_samples[-fade_out:] * f_out
                + b_clip.samples[start_idx:out_sample] * f_in
            )

        if is_array:
            return combined
        return AudioClipData(samples=combined, sample_rate=sr)


__all__ = ["ADRRecorder", "PunchInSession", "Take"]
