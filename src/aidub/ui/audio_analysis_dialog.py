"""Operator-facing audio diagnostics, local transcription, and emotion analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, override

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
    )

    from aidub.ui.workers import (
        AIAssistantWorker,
        AudioAnalysisWorker,
        EmotionAnalysisWorker,
        SpeechTranscriptionWorker,
    )

    _QT = True
except ImportError:
    _QT = False


if _QT:

    class AudioAnalysisDialog(QDialog):
        """Run real analysis tools on an imported source, dub, music, or SFX file."""

        def __init__(
            self,
            media_path: str | Path = "",
            *,
            start_seconds: float = 0.0,
            duration_seconds: float = 30.0,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.setWindowTitle("Audio Analysis & Speech Tools")
            self.setMinimumSize(680, 640)
            self.resize(790, 760)
            self._report: dict[str, Any] | None = None
            self._emotion: dict[str, Any] | None = None
            self._llm_interpretation = ""
            self._analysis_worker: AudioAnalysisWorker | None = None
            self._transcription_worker: SpeechTranscriptionWorker | None = None
            self._emotion_worker: EmotionAnalysisWorker | None = None
            self._assistant_worker: AIAssistantWorker | None = None

            root = QVBoxLayout(self)
            root.setContentsMargins(18, 16, 18, 16)
            root.setSpacing(10)

            title = QLabel("AUDIO ANALYSIS", self)
            title.setStyleSheet("font-size:15px;font-weight:800;color:#E8EAEE;")
            root.addWidget(title)
            intro = QLabel(
                "Measure audio locally, transcribe a short interval, and inspect emotion cues. "
                "No media is uploaded by the local tools.",
                self,
            )
            intro.setWordWrap(True)
            intro.setStyleSheet("color:#A9B2C3;font-size:11px;")
            root.addWidget(intro)

            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            form.setHorizontalSpacing(10)
            form.setVerticalSpacing(8)

            file_row = QHBoxLayout()
            self.file_edit = QLineEdit(str(media_path), self)
            self.file_edit.setPlaceholderText("Choose an audio or video source")
            self.browse_button = QPushButton("Browse…", self)
            self.browse_button.clicked.connect(self._browse)
            file_row.addWidget(self.file_edit, stretch=1)
            file_row.addWidget(self.browse_button)
            file_container = QLabel(self)
            file_container.setLayout(file_row)
            form.addRow("Media", file_container)

            self.start_spin = QDoubleSpinBox(self)
            self.start_spin.setRange(0.0, 99_999_999.0)
            self.start_spin.setDecimals(3)
            self.start_spin.setSuffix(" s")
            self.start_spin.setValue(max(0.0, start_seconds))
            form.addRow("Start", self.start_spin)

            self.duration_spin = QDoubleSpinBox(self)
            self.duration_spin.setRange(0.0, 99_999_999.0)
            self.duration_spin.setDecimals(3)
            self.duration_spin.setSuffix(" s  (0 = to end)")
            self.duration_spin.setValue(max(0.0, duration_seconds))
            form.addRow("Duration", self.duration_spin)
            self.character_edit = QLineEdit("Character", self)
            self.character_edit.setPlaceholderText("Optional speaker / character name")
            form.addRow("Character", self.character_edit)
            root.addLayout(form)

            local_tools = QHBoxLayout()
            self.analyze_button = QPushButton("Analyze Audio", self)
            self.analyze_button.setProperty("primary", True)
            self.analyze_button.clicked.connect(self._start_analysis)
            self.cancel_button = QPushButton("Cancel Analysis", self)
            self.cancel_button.setEnabled(False)
            self.cancel_button.clicked.connect(self._cancel_analysis)
            self.transcribe_button = QPushButton("Transcribe Selection", self)
            self.transcribe_button.setToolTip(
                "Runs the installed Faster-Whisper speech recognizer on the selected interval."
            )
            self.transcribe_button.clicked.connect(self._start_transcription)
            self.model_combo = QComboBox(self)
            self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
            self.model_combo.setCurrentText("large-v3")
            self.model_combo.setToolTip(
                "Faster-Whisper model size. The model is downloaded the first time if it is not cached."
            )
            local_tools.addWidget(self.analyze_button)
            local_tools.addWidget(self.cancel_button)
            local_tools.addWidget(self.transcribe_button)
            local_tools.addWidget(self.model_combo)
            root.addLayout(local_tools)

            self.progress = QProgressBar(self)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setTextVisible(False)
            self.progress.setFixedHeight(6)
            root.addWidget(self.progress)
            self.status = QLabel("Ready. Choose a media interval and run a local tool.", self)
            self.status.setWordWrap(True)
            self.status.setStyleSheet("color:#93A4B8;font-size:10px;")
            root.addWidget(self.status)

            transcript_title = QLabel("Dialogue transcript (optional)", self)
            transcript_title.setStyleSheet("font-size:11px;font-weight:700;color:#CBD5E1;")
            root.addWidget(transcript_title)
            self.transcript_edit = QPlainTextEdit(self)
            self.transcript_edit.setPlaceholderText(
                "Type or paste dialogue here, or use Transcribe Selection to fill it with local ASR."
            )
            self.transcript_edit.setMaximumHeight(86)
            root.addWidget(self.transcript_edit)

            context_title = QLabel("Character / scene context (optional)", self)
            context_title.setStyleSheet("font-size:11px;font-weight:700;color:#CBD5E1;")
            root.addWidget(context_title)
            self.context_edit = QPlainTextEdit(self)
            self.context_edit.setPlaceholderText(
                "For example: character is hiding in a tense scene; line is delivered off-screen."
            )
            self.context_edit.setMaximumHeight(58)
            root.addWidget(self.context_edit)

            self.results = QPlainTextEdit(self)
            self.results.setReadOnly(True)
            self.results.setPlaceholderText("Measured analysis, transcript, and emotion findings appear here.")
            self.results.setMinimumHeight(150)
            root.addWidget(self.results, stretch=1)

            disclosure = QLabel(
                "LLM requests send the measurements and any transcript/context you entered. "
                "The media file itself is not sent. Local emotion results are heuristic and need review.",
                self,
            )
            disclosure.setWordWrap(True)
            disclosure.setStyleSheet("color:#8290A2;font-size:9px;")
            root.addWidget(disclosure)

            actions = QHBoxLayout()
            self.emotion_button = QPushButton("Detect Emotion", self)
            self.emotion_button.setEnabled(False)
            self.emotion_button.setToolTip(
                "Uses the existing EmotionEngine acoustic analysis; supplied dialogue also enables its configured LLM context detector."
            )
            self.emotion_button.clicked.connect(self._start_emotion)
            self.llm_button = QPushButton("Explain Findings with LLM", self)
            self.llm_button.setEnabled(False)
            self.llm_button.clicked.connect(self._start_llm_interpretation)
            self.export_button = QPushButton("Export JSON", self)
            self.export_button.setEnabled(False)
            self.export_button.clicked.connect(self._export_json)
            self.close_button = QPushButton("Close", self)
            self.close_button.clicked.connect(self.close)
            actions.addWidget(self.emotion_button)
            actions.addWidget(self.llm_button)
            actions.addWidget(self.export_button)
            actions.addStretch()
            actions.addWidget(self.close_button)
            root.addLayout(actions)

            self.file_edit.textChanged.connect(self._invalidate_report)
            self.start_spin.valueChanged.connect(self._invalidate_report)
            self.duration_spin.valueChanged.connect(self._invalidate_report)

        def _browse(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose audio or video",
                self.file_edit.text(),
                "Media files (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.wma "
                "*.mp4 *.mkv *.mov *.webm *.avi);;All files (*.*)",
            )
            if path:
                self.file_edit.setText(path)

        def _selection(self) -> tuple[Path, float, float | None]:
            path = Path(self.file_edit.text().strip()).expanduser()
            if not path.is_file():
                raise FileNotFoundError("Choose an existing audio or video file first.")
            duration_value = self.duration_spin.value()
            return (
                path,
                self.start_spin.value(),
                duration_value if duration_value > 0 else None,
            )

        def _start_analysis(self) -> None:
            try:
                path, start, duration = self._selection()
            except (FileNotFoundError, OSError) as exc:
                self.status.setText(str(exc))
                return
            self._report = None
            self._emotion = None
            self._llm_interpretation = ""
            self.emotion_button.setEnabled(False)
            self.llm_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self._set_busy(True)
            self.results.clear()
            self.status.setText("Decoding and measuring the selected interval locally…")
            self.progress.setRange(0, 0 if duration is None else 100)
            self._analysis_worker = AudioAnalysisWorker(path, start, duration, self)
            self._analysis_worker.progress_updated.connect(self._update_progress)
            self._analysis_worker.analysis_completed.connect(self._analysis_completed)
            self._analysis_worker.analysis_failed.connect(self._analysis_failed)
            self._analysis_worker.analysis_cancelled.connect(self._analysis_cancelled)
            self._analysis_worker.start()
            self.cancel_button.setEnabled(True)

        def _update_progress(self, elapsed: float, total: float) -> None:
            if total > 0:
                self.progress.setRange(0, 100)
                self.progress.setValue(max(0, min(100, round(100 * elapsed / total))))
                self.status.setText(f"Measured {elapsed:.1f} of {total:.1f} seconds…")

        def _analysis_completed(self, report: dict[str, Any]) -> None:
            self._report = report
            self._emotion = None
            self._llm_interpretation = ""
            self.results.setPlainText(self._format_report(report))
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self.status.setText("Local audio measurements complete.")
            self._set_busy(False)
            self.emotion_button.setEnabled(report.get("analyzed_seconds", 0) <= 60)
            self.llm_button.setEnabled(True)
            self.export_button.setEnabled(True)

        def _analysis_failed(self, message: str) -> None:
            self._set_busy(False)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status.setText(f"Audio analysis failed: {message}")

        def _analysis_cancelled(self) -> None:
            self._set_busy(False)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status.setText("Audio analysis cancelled.")

        def _cancel_analysis(self) -> None:
            if self._analysis_worker is not None and self._analysis_worker.isRunning():
                self._analysis_worker.cancel()
                self.status.setText("Stopping the FFmpeg decoder…")

        def _start_transcription(self) -> None:
            try:
                path, start, duration = self._selection()
            except (FileNotFoundError, OSError) as exc:
                self.status.setText(str(exc))
                return
            if duration is None or duration > 300:
                self.status.setText("Choose a finite selection of 300 seconds or less for transcription.")
                return
            self._set_busy(True)
            self.status.setText("Starting the local Faster-Whisper recognizer…")
            self.results.clear()
            self._transcription_worker = SpeechTranscriptionWorker(
                path,
                start,
                duration,
                self.model_combo.currentText(),
                self,
            )
            self._transcription_worker.stage_updated.connect(self.status.setText)
            self._transcription_worker.transcription_completed.connect(
                self._transcription_completed
            )
            self._transcription_worker.transcription_failed.connect(
                self._tool_failed
            )
            self._transcription_worker.start()

        def _transcription_completed(self, transcript: str) -> None:
            if transcript:
                existing = self.transcript_edit.toPlainText().strip()
                self.transcript_edit.setPlainText(
                    f"{existing}\n{transcript}".strip() if existing else transcript
                )
                self.results.setPlainText("LOCAL WHISPER TRANSCRIPT\n\n" + transcript)
                self.status.setText("Transcription completed with Faster-Whisper.")
            else:
                self.status.setText("Faster-Whisper returned no speech segments for this interval.")
            self._set_busy(False)

        def _start_emotion(self) -> None:
            if self._report is None:
                self.status.setText("Run Audio Analysis first.")
                return
            try:
                path, start, duration = self._selection()
            except (FileNotFoundError, OSError) as exc:
                self.status.setText(str(exc))
                return
            if duration is None or duration > 60:
                self.status.setText("Select a finite interval of 60 seconds or less for EmotionEngine.")
                return
            self._set_busy(True)
            self.status.setText("Running the existing EmotionEngine on the selected interval…")
            self._emotion_worker = EmotionAnalysisWorker(
                path,
                start,
                duration,
                self.transcript_edit.toPlainText(),
                character_name=self.character_edit.text().strip() or "Character",
                scene_context=(
                    f"{self.context_edit.toPlainText().strip()}\n\n"
                    "Measured acoustic features (not a transcript): "
                    f"{json.dumps({key: value for key, value in self._report.items() if key not in {'file_name', 'measurement_note'}}, ensure_ascii=False)}"
                ).strip(),
                parent=self,
            )
            self._emotion_worker.stage_updated.connect(self.status.setText)
            self._emotion_worker.emotion_completed.connect(self._emotion_completed)
            self._emotion_worker.emotion_failed.connect(self._tool_failed)
            self._emotion_worker.start()

        def _emotion_completed(self, emotion: dict[str, Any]) -> None:
            self._emotion = emotion
            self.results.appendPlainText("\n\nEMOTION ENGINE RESULT")
            self.results.appendPlainText(self._format_emotion(emotion))
            self.status.setText(
                f"Emotion analysis completed using {emotion.get('detection_source', 'unknown method')}."
            )
            self._set_busy(False)
            self.export_button.setEnabled(True)

        def _start_llm_interpretation(self) -> None:
            if self._report is None:
                self.status.setText("Run Audio Analysis first.")
                return
            measurements = {
                key: value
                for key, value in self._report.items()
                if key not in {"file_name", "measurement_note"}
            }
            user_text = self.transcript_edit.toPlainText().strip()
            context = self.context_edit.toPlainText().strip()
            prompt = (
                "Interpret these measured audio features for a film dubbing editor. "
                "Do not claim you listened to the media. The active-audio percentage is only an "
                "energy threshold, not speech detection. Treat pitch on a mixed soundtrack as "
                "uncertain. If transcript text is absent, do not guess the character's semantic "
                "emotion. Give concise findings, practical mix/ADR checks, and clearly separate "
                "measurement from hypothesis.\n\n"
                f"Measured features (JSON):\n{json.dumps(measurements, ensure_ascii=False, indent=2)}\n\n"
                f"Operator-supplied dialogue transcript:\n{user_text or '[not supplied]'}\n\n"
                f"Operator-supplied scene context:\n{context or '[not supplied]'}"
            )
            self._set_busy(True)
            self.status.setText("Sending the feature summary and supplied text to the configured LLM…")
            self._assistant_worker = AIAssistantWorker(prompt, parent=self)
            self._assistant_worker.response_received.connect(self._llm_interpretation_received)
            self._assistant_worker.request_failed.connect(self._tool_failed)
            self._assistant_worker.start()

        def _llm_interpretation_received(self, response: str) -> None:
            self._llm_interpretation = response
            self.results.appendPlainText("\n\nLLM INTERPRETATION")
            self.results.appendPlainText(response)
            self.status.setText("LLM interpretation completed using the configured provider.")
            self._set_busy(False)
            self.export_button.setEnabled(True)

        def _tool_failed(self, message: str) -> None:
            self.status.setText(f"Audio tool failed: {message}")
            self._set_busy(False)

        def _format_report(self, report: dict[str, Any]) -> str:
            rate = report.get("source_sample_rate_hz")
            channels = report.get("source_channels")
            pitch = report.get("pitch_median_hz")
            pitch_text = "No stable pitch estimate" if pitch is None else (
                f"{pitch:.1f} Hz median "
                f"(P10 {report.get('pitch_p10_hz'):.1f}, P90 {report.get('pitch_p90_hz'):.1f})"
            )
            loudness_range = report.get("loudness_range_db")
            loudness_text = "n/a" if loudness_range is None else f"{loudness_range:.2f} dB"
            return "\n".join(
                [
                    "MEASURED AUDIO REPORT",
                    f"File: {report['file_name']}",
                    f"Interval: {report['start_seconds']:.3f}s for {report['analyzed_seconds']:.3f}s",
                    f"Source format: {rate or 'unknown'} Hz, {channels or 'unknown'} channel(s); "
                    f"analysis at {report['analysis_sample_rate_hz']} Hz mono",
                    "",
                    "Signal level",
                    f"  Peak: {report['peak_dbfs']:.2f} dBFS",
                    f"  RMS: {report['rms_dbfs']:.2f} dBFS",
                    f"  Frame loudness range: {loudness_text}",
                    f"  Near full-scale samples: {report['near_full_scale_percent']:.5f}%",
                    f"  Silence estimate (< -55 dBFS): {report['silence_percent']:.2f}%",
                    f"  Active audio (>= -40 dBFS): {report['active_audio_percent']:.2f}%",
                    "",
                    "Pitch / spectral indicators",
                    f"  Sampled pitch: {pitch_text}",
                    f"  Pitch-sample voiced ratio: {report['pitch_voiced_sample_percent']:.2f}%",
                    f"  Spectral centroid: {report['spectral_centroid_hz']:.1f} Hz",
                    f"  Zero-crossing rate: {report['zero_crossing_rate']:.5f}",
                    "",
                    report["measurement_note"],
                ]
            )

        def _format_emotion(self, emotion: dict[str, Any]) -> str:
            return "\n".join(
                [
                    f"  Primary emotion: {emotion.get('primary_emotion', 'unknown')}",
                    f"  Confidence: {float(emotion.get('confidence', 0.0)):.2f}",
                    f"  Valence / arousal / dominance: {emotion.get('valence')} / "
                    f"{emotion.get('arousal')} / {emotion.get('dominance')}",
                    f"  Intensity: {emotion.get('intensity')}",
                    f"  Detection source: {emotion.get('detection_source', 'acoustic_prosody_heuristic')}",
                    f"  Suggested TTS controls: {emotion.get('synthesis_parameters', {})}",
                    "  This is an estimate. Review it against the isolated dialogue and scene.",
                ]
            )

        def _export_json(self) -> None:
            if self._report is None:
                return
            default_path = Path(self._report["file_name"]).with_suffix(".audio-analysis.json")
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export audio analysis report",
                str(default_path),
                "JSON files (*.json)",
            )
            if not path:
                return
            payload = {
                "audio_measurements": self._report,
                "emotion_result": self._emotion,
                "transcript": self.transcript_edit.toPlainText(),
                "scene_context": self.context_edit.toPlainText(),
                "llm_interpretation": self._llm_interpretation or None,
            }
            try:
                Path(path).write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError as exc:
                self.status.setText(f"Could not write report: {exc}")
                return
            self.status.setText(f"Report exported to {path}")

        def _invalidate_report(self, _value: Any = None) -> None:
            if self._report is None:
                return
            self._report = None
            self._emotion = None
            self._llm_interpretation = ""
            self.emotion_button.setEnabled(False)
            self.llm_button.setEnabled(False)
            self.export_button.setEnabled(False)

        def _set_busy(self, busy: bool) -> None:
            self.analyze_button.setEnabled(not busy)
            self.transcribe_button.setEnabled(not busy)
            self.emotion_button.setEnabled(
                not busy and self._report is not None and self._report.get("analyzed_seconds", 0) <= 60
            )
            self.llm_button.setEnabled(not busy and self._report is not None)
            self.cancel_button.setEnabled(
                busy
                and self._analysis_worker is not None
                and self._analysis_worker.isRunning()
            )
            self.file_edit.setEnabled(not busy)
            self.browse_button.setEnabled(not busy)
            self.start_spin.setEnabled(not busy)
            self.duration_spin.setEnabled(not busy)
            self.character_edit.setEnabled(not busy)

        @override
        def closeEvent(self, event: Any) -> None:
            workers = (
                self._analysis_worker,
                self._transcription_worker,
                self._emotion_worker,
                self._assistant_worker,
            )
            running = [worker for worker in workers if worker is not None and worker.isRunning()]
            if running:
                if self._analysis_worker in running:
                    self._analysis_worker.cancel()
                self.status.setText("A background audio tool is still running; wait for it to finish.")
                event.ignore()
                return
            event.accept()


else:

    class AudioAnalysisDialog:
        """Fail clearly if someone imports this dialog without the optional desktop runtime."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("Audio analysis UI requires the optional PySide6 desktop dependency")


__all__ = ["AudioAnalysisDialog"]
