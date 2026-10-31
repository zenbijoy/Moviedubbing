"""
Real-time Audio Audition and Voice Synthesis Playback Service.

Provides instant audio playback for DAW voice editing, emotion directing,
timbre morphing, and character voice auditioning:
  - In-memory AudioClipData audition via QMediaPlayer / QAudioOutput.
  - Asynchronous Edge-TTS preview voice synthesis.
  - Headless safe fallback for non-GUI test environments.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QObject, QUrl, Signal
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

    _QT_AUDIO_AVAILABLE = True
except ImportError:
    _QT_AUDIO_AVAILABLE = False
    QObject = object  # type: ignore[misc, assignment]


class AuditionService(QObject if _QT_AUDIO_AVAILABLE else object):  # type: ignore[misc]
    """Singleton-capable playback and voice audition engine."""

    if _QT_AUDIO_AVAILABLE:
        playback_started = Signal(str)  # source path
        playback_stopped = Signal()
        position_changed = Signal(float)  # current time in seconds
        duration_changed = Signal(float)  # total duration in seconds
        error_occurred = Signal(str)

    def __init__(self, parent: Any = None) -> None:
        if _QT_AUDIO_AVAILABLE:
            super().__init__(parent)
            self._player: QMediaPlayer | None = QMediaPlayer(self)
            self._audio_output: QAudioOutput | None = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_output)
            self._audio_output.setVolume(0.9)

            self._player.positionChanged.connect(self._on_pos_changed)
            self._player.durationChanged.connect(self._on_dur_changed)
            self._player.playbackStateChanged.connect(self._on_state_changed)
        else:
            self._player = None
            self._audio_output = None

        self._temp_files: list[Path] = []
        self._is_playing: bool = False
        self._current_source: str = ""

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def play_clip(self, clip: AudioClipData) -> str:
        """Save clip to temp wav and play immediately."""
        self.stop(emit_signal=False)
        if clip.samples.size == 0:
            return ""

        temp_wav = Path(tempfile.mktemp(suffix="_audition.wav"))
        ProAudioDspEngine.save_wav(clip, temp_wav)
        self._temp_files.append(temp_wav)
        return self.play_file(str(temp_wav))

    def play_file(self, file_path: str) -> str:
        """Play existing audio file through player."""
        self.stop(emit_signal=False)
        p = Path(file_path)
        if not p.is_file():
            logger.warning("Audition file not found: %s", file_path)
            return ""

        self._current_source = str(p)
        if _QT_AUDIO_AVAILABLE and self._player:
            self._player.setSource(QUrl.fromLocalFile(str(p)))
            self._player.play()
            self._is_playing = True
            self.playback_started.emit(str(p))
            logger.info("Audition playback started: %s", p.name)
        else:
            self._is_playing = True
            logger.info("[Headless] Simulated playback of %s", p.name)
        return str(p)

    def synthesize_and_play(
        self,
        text: str,
        voice_id: str = "bn-BD-NabanitaNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        on_done: Callable[[str], None] | None = None,
    ) -> None:
        """Synthesize preview dialogue asynchronously and auto-play."""
        self.stop(emit_signal=False)
        self._is_playing = True

        def _worker() -> None:
            try:
                import edge_tts

                out_wav = Path(tempfile.mktemp(suffix="_synth_audition.mp3"))

                async def _gen() -> None:
                    communicate = edge_tts.Communicate(
                        text=text or "Hello, preview audition",
                        voice=voice_id,
                        rate=rate,
                        pitch=pitch,
                        volume=volume,
                    )
                    await communicate.save(str(out_wav))

                asyncio.run(_gen())
                self._temp_files.append(out_wav)
                self.play_file(str(out_wav))
                if on_done:
                    on_done(str(out_wav))
            except Exception as ex:
                logger.warning("Edge-TTS synthesis failed (%s), generating acoustic tone fallback", ex)
                # Fallback to acoustic tone so audition never fails!
                sample_rate = 44100
                duration_s = max(1.0, min(3.0, len(text) * 0.08))
                import numpy as np

                t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
                # Warm speech-like harmonic chord
                sig = 0.25 * np.sin(2 * np.pi * 220 * t) + 0.15 * np.sin(2 * np.pi * 440 * t)
                # Envelope
                env = np.ones_like(sig)
                fade = int(0.05 * sample_rate)
                env[:fade] = np.linspace(0, 1, fade)
                env[-fade:] = np.linspace(1, 0, fade)
                sig = (sig * env).astype(np.float32)

                fallback_clip = AudioClipData(samples=sig, sample_rate=sample_rate)
                path = self.play_clip(fallback_clip)
                if on_done:
                    on_done(path)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def stop(self, emit_signal: bool = True) -> None:
        """Stop playback immediately."""
        if _QT_AUDIO_AVAILABLE and self._player:
            self._player.stop()
        self._is_playing = False
        if _QT_AUDIO_AVAILABLE and emit_signal:
            self.playback_stopped.emit()

    def set_volume(self, volume_pct: int) -> None:
        """Set volume from 0 to 100%."""
        if _QT_AUDIO_AVAILABLE and self._audio_output:
            self._audio_output.setVolume(max(0.0, min(1.0, volume_pct / 100.0)))

    def _on_pos_changed(self, pos_ms: int) -> None:
        if _QT_AUDIO_AVAILABLE:
            self.position_changed.emit(pos_ms / 1000.0)

    def _on_dur_changed(self, dur_ms: int) -> None:
        if _QT_AUDIO_AVAILABLE:
            self.duration_changed.emit(dur_ms / 1000.0)

    def _on_state_changed(self, state: Any) -> None:
        if _QT_AUDIO_AVAILABLE:
            from PySide6.QtMultimedia import QMediaPlayer

            self._is_playing = state == QMediaPlayer.PlaybackState.PlayingState
            if not self._is_playing:
                self.playback_stopped.emit()

    def cleanup(self) -> None:
        """Clean up temporary audition files."""
        self.stop()
        for f in self._temp_files:
            try:
                if f.exists():
                    f.unlink()
            except Exception:
                pass
        self._temp_files.clear()


__all__ = ["AuditionService"]
