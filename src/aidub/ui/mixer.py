"""
Broadcast-grade audio mixer engine and channel strip state management.

Features (Master Spec Section 27):
  - Per-track Volume Fader (-60 dB to +12 dB with linear gain conversion)
  - Stereo Panning (-1.0 to +1.0)
  - Mute & Solo solo-logic group solver
  - Channel peak metering (-60 dBFS to +6 dBFS) & clip indicator
"""

from __future__ import annotations

from pydantic import Field

from aidub.contracts.base import ContractModel
from aidub.ui.timeline.model import TrackId


class ChannelStripState(ContractModel):
    """Runtime state of a single mixer channel strip."""

    track_id: TrackId
    volume_db: float = Field(default=0.0, ge=-60.0, le=12.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    muted: bool = False
    solo: bool = False
    peak_l_dbfs: float = Field(default=-60.0, ge=-60.0, le=6.0)
    peak_r_dbfs: float = Field(default=-60.0, ge=-60.0, le=6.0)
    clipped: bool = False
    gain_rider_enabled: bool = False
    gain_rider_target_rms: float = Field(default=0.1, ge=0.001, le=1.0)
    ducking_enabled: bool = False
    ducking_depth_db: float = Field(default=-12.0, ge=-40.0, le=0.0)

    @property
    def linear_gain(self) -> float:
        """Convert volume dB to linear multiplier."""
        if self.volume_db <= -60.0:
            return 0.0
        return float(10.0 ** (self.volume_db / 20.0))


class AudioMixerEngine:
    """
    Manages 9-track studio audio mixer state and solo/mute routing logic.
    """

    def __init__(self) -> None:
        self._channels: dict[TrackId, ChannelStripState] = {
            t_id: ChannelStripState(track_id=t_id) for t_id in TrackId if t_id.value.startswith("A")
        }
        self._master_volume_db: float = 0.0

    def get_channel(self, track_id: TrackId) -> ChannelStripState | None:
        return self._channels.get(track_id)

    def set_volume(self, track_id: TrackId, volume_db: float) -> ChannelStripState:
        """Set track volume in dB."""
        ch = self._require(track_id)
        updated = ch.model_copy(update={"volume_db": max(-60.0, min(12.0, volume_db))})
        self._channels[track_id] = updated
        return updated

    def set_pan(self, track_id: TrackId, pan: float) -> ChannelStripState:
        """Set track panning (-1.0 to +1.0)."""
        ch = self._require(track_id)
        updated = ch.model_copy(update={"pan": max(-1.0, min(1.0, pan))})
        self._channels[track_id] = updated
        return updated

    def toggle_mute(self, track_id: TrackId) -> ChannelStripState:
        """Toggle track mute state."""
        ch = self._require(track_id)
        updated = ch.model_copy(update={"muted": not ch.muted})
        self._channels[track_id] = updated
        return updated

    def toggle_solo(self, track_id: TrackId) -> ChannelStripState:
        """Toggle track solo state."""
        ch = self._require(track_id)
        updated = ch.model_copy(update={"solo": not ch.solo})
        self._channels[track_id] = updated
        return updated

    def set_mute(self, track_id: TrackId, muted: bool) -> ChannelStripState:
        """Set track mute state."""
        ch = self._require(track_id)
        updated = ch.model_copy(update={"muted": bool(muted)})
        self._channels[track_id] = updated
        return updated

    def set_solo(self, track_id: TrackId, solo: bool) -> ChannelStripState:
        """Set track solo state."""
        ch = self._require(track_id)
        updated = ch.model_copy(update={"solo": bool(solo)})
        self._channels[track_id] = updated
        return updated

    def is_track_audible(self, track_id: TrackId) -> bool:
        """
        Determine if track is audible based on Mute and Solo group logic.

        If ANY track is soloed, ONLY soloed tracks are audible (unless muted).
        """
        ch = self._channels.get(track_id)
        if ch is None or ch.muted:
            return False

        any_soloed = any(c.solo for c in self._channels.values())
        if any_soloed:
            return ch.solo
        return True

    def update_meter(
        self, track_id: TrackId, peak_l_dbfs: float, peak_r_dbfs: float
    ) -> ChannelStripState:
        """Update channel peak meter level and clip indicators."""
        ch = self._require(track_id)
        clipped = ch.clipped or peak_l_dbfs > 0.0 or peak_r_dbfs > 0.0
        updated = ch.model_copy(
            update={
                "peak_l_dbfs": round(peak_l_dbfs, 1),
                "peak_r_dbfs": round(peak_r_dbfs, 1),
                "clipped": clipped,
            }
        )
        self._channels[track_id] = updated
        return updated

    def reset_clips(self) -> None:
        """Reset all channel clip indicators."""
        for t_id, ch in self._channels.items():
            self._channels[t_id] = ch.model_copy(update={"clipped": False})

    def set_auto_gain_rider(
        self, track_id: TrackId, enabled: bool, target_rms: float = 0.1
    ) -> ChannelStripState:
        """Configure per-track AutoGainRider."""
        ch = self._require(track_id)
        updated = ch.model_copy(
            update={
                "gain_rider_enabled": bool(enabled),
                "gain_rider_target_rms": max(0.001, min(1.0, float(target_rms))),
            }
        )
        self._channels[track_id] = updated
        return updated

    def set_sidechain_ducking(
        self, track_id: TrackId, enabled: bool, duck_db: float = -12.0
    ) -> ChannelStripState:
        """Configure per-track SidechainDucker (dialogue over music/ambience)."""
        ch = self._require(track_id)
        updated = ch.model_copy(
            update={
                "ducking_enabled": bool(enabled),
                "ducking_depth_db": max(-40.0, min(0.0, float(duck_db))),
            }
        )
        self._channels[track_id] = updated
        return updated

    def process_channel_audio(
        self,
        track_id: TrackId,
        clip: AudioClipData,
        dialogue_sidechain_clip: AudioClipData | None = None,
    ) -> AudioClipData:
        """
        Process audio clip through channel strip DSP chain:
        AutoGainRider -> SidechainDucker -> Channel Volume/Fader Gain.
        """
        from aidub.application.audio.auto_gain_rider import AutoGainRider
        from aidub.application.audio.sidechain_ducker import SidechainDucker

        ch = self._require(track_id)
        if not self.is_track_audible(track_id):
            # Muted or not soloed
            import numpy as np

            return AudioClipData(
                samples=np.zeros_like(clip.samples),
                sample_rate=clip.sample_rate,
                label=f"{clip.label}_muted",
            )

        processed = clip.clone()

        # 1. AutoGainRider
        if ch.gain_rider_enabled:
            rider = AutoGainRider(target_rms=ch.gain_rider_target_rms)
            processed = rider.process(processed)

        # 2. Sidechain Ducker
        if ch.ducking_enabled and dialogue_sidechain_clip is not None:
            ducker = SidechainDucker(duck_db=ch.ducking_depth_db)
            processed = ducker.process(music=processed, dialogue=dialogue_sidechain_clip)

        # 3. Channel Fader Gain
        if abs(ch.volume_db) > 1e-3:
            gain = ch.linear_gain
            processed = AudioClipData(
                samples=processed.samples * gain,
                sample_rate=processed.sample_rate,
                label=processed.label,
            )

        return processed

    def _require(self, track_id: TrackId) -> ChannelStripState:
        ch = self._channels.get(track_id)
        if ch is None:
            raise KeyError(f"audio track {track_id.value!r} is not registered in mixer")
        return ch


try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QDialog,
        QDoubleSpinBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QSlider,
        QVBoxLayout,
        QWidget,
    )

    _QT = True
except ImportError:
    _QT = False
    QWidget = object  # type: ignore[misc, assignment]
    QDialog = object  # type: ignore[misc, assignment]


if _QT:

    class ChannelStripWidget(QFrame):
        """Interactive Cubase-style MixConsole Channel Strip."""

        fader_changed = Signal(object, float)  # track_id, volume_db
        mute_toggled = Signal(object, bool)
        solo_toggled = Signal(object, bool)
        gain_rider_changed = Signal(object, bool, float)
        ducking_changed = Signal(object, bool, float)

        def __init__(
            self,
            track_id: TrackId,
            state: ChannelStripState,
            title: str = "",
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.track_id = track_id
            self.state = state
            self.setFixedWidth(130)
            self.setStyleSheet(
                "QFrame { background: #0F141C; border: 1px solid #1E293B; border-radius: 6px; }"
                "QLabel { color: #E2E8F0; font-size: 10px; font-weight: 600; }"
            )

            lay = QVBoxLayout(self)
            lay.setContentsMargins(6, 8, 6, 8)
            lay.setSpacing(6)

            # Track Title Banner
            self.lbl_title = QLabel(title or track_id.value.upper(), self)
            self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_title.setStyleSheet("background: #1E293B; color: #38BDF8; padding: 4px; border-radius: 3px; font-weight: bold;")
            lay.addWidget(self.lbl_title)

            # Mute & Solo Row
            ms_row = QHBoxLayout()
            self.btn_mute = QPushButton("M", self)
            self.btn_mute.setCheckable(True)
            self.btn_mute.setChecked(state.muted)
            self.btn_mute.setStyleSheet("QPushButton:checked { background: #DC2626; color: white; font-weight: bold; }")
            self.btn_mute.clicked.connect(lambda: self.mute_toggled.emit(self.track_id, self.btn_mute.isChecked()))
            ms_row.addWidget(self.btn_mute)

            self.btn_solo = QPushButton("S", self)
            self.btn_solo.setCheckable(True)
            self.btn_solo.setChecked(state.solo)
            self.btn_solo.setStyleSheet("QPushButton:checked { background: #EAB308; color: black; font-weight: bold; }")
            self.btn_solo.clicked.connect(lambda: self.solo_toggled.emit(self.track_id, self.btn_solo.isChecked()))
            ms_row.addWidget(self.btn_solo)
            lay.addLayout(ms_row)

            # Auto-Gain Rider Group
            gr_box = QGroupBox("Auto-Gain", self)
            gr_box.setStyleSheet("QGroupBox { font-size: 9px; font-weight: bold; color: #94A3B8; margin-top: 4px; padding-top: 4px; }")
            gr_lay = QVBoxLayout(gr_box)
            gr_lay.setContentsMargins(2, 4, 2, 4)
            gr_lay.setSpacing(2)

            self.chk_rider = QCheckBox("Enable Rider", gr_box)
            self.chk_rider.setChecked(state.gain_rider_enabled)
            gr_lay.addWidget(self.chk_rider)

            self.spin_rms = QDoubleSpinBox(gr_box)
            self.spin_rms.setRange(0.01, 0.50)
            self.spin_rms.setSingleStep(0.01)
            self.spin_rms.setValue(state.gain_rider_target_rms)
            self.spin_rms.setToolTip("Target Speech RMS Level")
            gr_lay.addWidget(self.spin_rms)
            self.chk_rider.toggled.connect(lambda c: self.gain_rider_changed.emit(self.track_id, c, self.spin_rms.value()))
            self.spin_rms.valueChanged.connect(lambda v: self.gain_rider_changed.emit(self.track_id, self.chk_rider.isChecked(), v))
            lay.addWidget(gr_box)

            # Sidechain Ducking Group
            dk_box = QGroupBox("Ducking", self)
            dk_box.setStyleSheet("QGroupBox { font-size: 9px; font-weight: bold; color: #94A3B8; margin-top: 4px; padding-top: 4px; }")
            dk_lay = QVBoxLayout(dk_box)
            dk_lay.setContentsMargins(2, 4, 2, 4)
            dk_lay.setSpacing(2)

            self.chk_ducking = QCheckBox("Sidechain", dk_box)
            self.chk_ducking.setChecked(state.ducking_enabled)
            dk_lay.addWidget(self.chk_ducking)

            self.lbl_duck_val = QLabel(f"{state.ducking_depth_db:.0f} dB", dk_box)
            self.lbl_duck_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dk_lay.addWidget(self.lbl_duck_val)

            self.slider_duck = QSlider(Qt.Orientation.Horizontal, dk_box)
            self.slider_duck.setRange(-36, -6)
            self.slider_duck.setValue(int(state.ducking_depth_db))
            self.slider_duck.valueChanged.connect(
                lambda v: (
                    self.lbl_duck_val.setText(f"{v} dB"),
                    self.ducking_changed.emit(self.track_id, self.chk_ducking.isChecked(), float(v)),
                )
            )
            self.chk_ducking.toggled.connect(
                lambda c: self.ducking_changed.emit(self.track_id, c, float(self.slider_duck.value()))
            )
            dk_lay.addWidget(self.slider_duck)
            lay.addWidget(dk_box)

            # Volume Fader & Peak Meter Section
            fader_row = QHBoxLayout()
            fader_row.setSpacing(6)

            # Vertical Volume Slider
            self.slider_fader = QSlider(Qt.Orientation.Vertical, self)
            self.slider_fader.setRange(-60, 12)
            self.slider_fader.setValue(int(state.volume_db))
            self.slider_fader.valueChanged.connect(self._on_fader_moved)
            fader_row.addWidget(self.slider_fader, stretch=1)

            # Peak VU Meter
            meter_col = QVBoxLayout()
            self.clip_indicator = QLabel("●", self)
            self.clip_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.clip_indicator.setStyleSheet("color: #475569; font-size: 11px;")
            meter_col.addWidget(self.clip_indicator)

            self.meter_bar = QProgressBar(self)
            self.meter_bar.setOrientation(Qt.Orientation.Vertical)
            self.meter_bar.setRange(-60, 6)
            self.meter_bar.setValue(int(state.peak_l_dbfs))
            self.meter_bar.setTextVisible(False)
            self.meter_bar.setFixedWidth(12)
            self.meter_bar.setStyleSheet(
                "QProgressBar { background: #0B0E14; border: 1px solid #1E293B; border-radius: 2px; }"
                "QProgressBar::chunk { background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #10B981, stop:0.8 #F59E0B, stop:1 #EF4444); }"
            )
            meter_col.addWidget(self.meter_bar, stretch=1)
            fader_row.addLayout(meter_col)

            lay.addLayout(fader_row, stretch=1)

            # Volume Readout Label
            self.lbl_volume = QLabel(f"{state.volume_db:+.1f} dB", self)
            self.lbl_volume.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_volume.setStyleSheet("font-weight: bold; color: #38BDF8; font-family: monospace;")
            lay.addWidget(self.lbl_volume)

        def _on_fader_moved(self, val: int) -> None:
            self.lbl_volume.setText(f"{val:+.1f} dB")
            self.fader_changed.emit(self.track_id, float(val))

        def update_peaks(self, peak_l: float, peak_r: float, clipped: bool) -> None:
            val = max(peak_l, peak_r)
            self.meter_bar.setValue(int(val))
            if clipped:
                self.clip_indicator.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
            else:
                self.clip_indicator.setStyleSheet("color: #475569; font-size: 11px;")


    class AudioMixerConsoleDialog(QDialog):
        """Cubase MixConsole Window hosting multi-track channel strips."""

        def __init__(
            self,
            mixer_engine: AudioMixerEngine | None = None,
            parent: QWidget | None = None,
            mixer: AudioMixerEngine | None = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("🎛️ Cubase Studio MixConsole (F3) — Master Mix & DSP")
            self.resize(780, 520)
            self.setStyleSheet(
                "QDialog { background-color: #080B11; color: #F8FAFC; font-family: 'Segoe UI', sans-serif; }"
                "QPushButton { background: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 4px; padding: 6px 12px; font-weight: 600; font-size: 11px; }"
                "QPushButton:hover { background: #334155; border-color: #0284C7; }"
            )

            self.engine = mixer or mixer_engine or AudioMixerEngine()

            layout = QVBoxLayout(self)
            layout.setSpacing(10)

            # Top Control Bar
            top_bar = QHBoxLayout()
            title = QLabel("🎛️ Broadcast MixConsole & Sidechain Routing")
            title.setStyleSheet("font-size: 14px; font-weight: 800; color: #38BDF8;")
            top_bar.addWidget(title)
            top_bar.addStretch()

            btn_reset_clips = QPushButton("Reset Clip LEDs", self)
            btn_reset_clips.clicked.connect(self._reset_clips)
            top_bar.addWidget(btn_reset_clips)
            layout.addLayout(top_bar)

            # Strips Rack
            strips_row = QHBoxLayout()
            strips_row.setSpacing(8)

            track_titles = {
                TrackId.A1: "A1: Source Actor",
                TrackId.A2: "A2: AI Dubbed",
                TrackId.A3: "A3: Music / Score",
                TrackId.A4: "A4: SFX & Ambience",
            }

            self.strips: dict[TrackId, ChannelStripWidget] = {}
            for t_id in [TrackId.A1, TrackId.A2, TrackId.A3, TrackId.A4]:
                ch_state = self.engine.get_channel(t_id)
                if ch_state is None:
                    continue
                strip = ChannelStripWidget(
                    track_id=t_id,
                    state=ch_state,
                    title=track_titles.get(t_id, t_id.value),
                    parent=self,
                )
                strip.fader_changed.connect(self.engine.set_volume)
                strip.mute_toggled.connect(self.engine.set_mute)
                strip.solo_toggled.connect(self.engine.set_solo)
                strip.gain_rider_changed.connect(
                    lambda tid, en, rms: self.engine.set_auto_gain_rider(tid, en, rms)
                )
                strip.ducking_changed.connect(
                    lambda tid, en, db: self.engine.set_sidechain_ducking(tid, en, db)
                )
                strips_row.addWidget(strip)
                self.strips[t_id] = strip

            layout.addLayout(strips_row, stretch=1)

            # Close Bar
            bot_bar = QHBoxLayout()
            bot_bar.addStretch()
            btn_close = QPushButton("Close MixConsole", self)
            btn_close.clicked.connect(self.accept)
            bot_bar.addWidget(btn_close)
            layout.addLayout(bot_bar)

        def _reset_clips(self) -> None:
            self.engine.reset_clips()
            for s in self.strips.values():
                s.clip_indicator.setStyleSheet("color: #475569; font-size: 11px;")
else:
    class ChannelStripWidget:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass

    class AudioMixerConsoleDialog:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


__all__ = [
    "AudioMixerConsoleDialog",
    "AudioMixerEngine",
    "ChannelStripState",
    "ChannelStripWidget",
]
