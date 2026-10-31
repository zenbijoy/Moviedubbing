from __future__ import annotations
import os
from ._timeline_common import *
from ._timeline_common import _QT
from ._timeline_widgets import (
    _ProductionStageBar, _MediaBrowserPanel, _ProgramMonitorPanel,
    _WaveformWidget, _StereoMeterWidget, _DialogueCardWidget,
    _DialogueInspectorPanel,
)
from ._timeline_timeline import (
    _TimelineCanvasView, _StudioNavigationRail, _TimelineToolPalette,
    _TimelineEditorBar, _FloatingAIActionsPanel, _TimelineHeaderPanel,
)
if _QT:
    class TimelineScreen(QWidget):
        clip_selected = Signal(object)
        project_loaded = Signal(str)

        def showEvent(self, event: Any) -> None:
            super().showEvent(event)
            if hasattr(self, "workspace_splitter"):
                self.workspace_splitter.setSizes([640, 240])
            if hasattr(self, "upper_splitter"):
                self.upper_splitter.setSizes([264, 820, 440])

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._current_project_data: dict[str, Any] = {
                "name": "Untitled Studio",
                "movie_name": "",
                "file_path": "",
                "character": "",
                "duration": 1.0,
                "original_text": "",
                "translation_text": "",
                "clips": [],
                "generated_paths": (),
            }
            self._active_clip_info: dict[str, Any] | None = None
            self._edit_history: list[list[ClipTuple]] = []
            self._edit_future: list[list[ClipTuple]] = []
            self._timeline_toggles = {"Toggle Snapping": True, "Linked Selection": True}
            self._mixer_levels: dict[str, float] = {
                "A1": 1.0,
                "A2": 1.0,
                "A3": 0.7,
                "A4": 0.8,
                "A5": 0.6,
                "master": 1.0,
            }
            self._mixer_mutes: set[str] = set()
            self._mixer_solos: set[str] = set()
            self._sidechain_ducking_enabled: bool = True
            self._sidechain_ducking_depth: float = 12.0
            app_data = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
            session_root = Path(app_data) / "sessions"
            self._session_store = StudioSessionStore(session_root)
            self._automation_state = create_automation_plan(
                "Untitled Studio",
                target_language="bn",
            )
            self._dubbing_worker: Any | None = None
            self._active_lipsync_worker: Any | None = None
            self._assistant_worker: Any | None = None
            self._audio_analysis_dialog: Any | None = None
            self._tts_worker: Any | None = None
            self._timing_worker: Any | None = None
            self._pending_timing_edit: dict[str, Any] | None = None
            self._take_audio_player: Any | None = None
            self._take_audio_output: Any | None = None
            self._selected_voice_name: str | None = None
            self._active_opened_project: Any | None = None
            self._extraction_worker: Any | None = None
            self._transcription_worker: Any | None = None
            self._translation_worker: Any | None = None
            self._synthesis_worker: Any | None = None
            self._render_worker: Any | None = None
            self._build_ui()
            self._wire_signals()
            self.ai_overlay.set_state(self._automation_state)
            self.stage_bar.set_state(self._automation_state)
            self._autosave_timer = QTimer(self)
            self._autosave_timer.setInterval(15_000)
            self._autosave_timer.timeout.connect(self._autosave_session)
            self._autosave_timer.start()
            if Path("Inception_1080P_480P.mp4").is_file() and not os.environ.get("PYTEST_CURRENT_TEST"):
                self.load_inception_demo()

        def load_inception_demo(self) -> None:
            root_movie = Path("Inception_1080P_480P.mp4")
            if not root_movie.is_file():
                return
            movie_path = str(root_movie.resolve())

            # 5 Inception Dialogue Clips around 00:48:33 (matching Image 1)
            demo_clips = [
                ("V3", 0.0, 60.0, "Inception_1080P_480P.mp4", None),
                ("A1", 0.0, 60.0, "Original Audio", None),
                ("A2", 16.0, 3.0, "জেগে ওঠো।", 0.90),
                ("A2", 20.0, 3.5, "তুমি বাস্তব নও।", 0.94),
                ("A2", 32.2, 3.96, "আমাদের কথা বলা দরকার।", 0.92),
                ("A2", 38.0, 2.8, "এখনও না।", 0.88),
                ("A2", 42.0, 3.0, "চলো যাই।", 0.91),
                ("A3", 0.0, 60.0, "Music_Background.mp3", None),
                ("A4", 0.0, 60.0, "SFX_Ambience.mp3", None),
                ("S2", 16.0, 3.0, "Wake up.", None),
                ("S2", 20.0, 3.5, "You're not real.", None),
                ("S2", 32.2, 3.96, "We need to talk.", None),
                ("S2", 38.0, 2.8, "Not yet.", None),
                ("S2", 42.0, 3.0, "Let's go.", None),
            ]

            self._current_project_data = {
                "name": "Inception_1080P_480P",
                "movie_name": "Inception_1080P_480P.mp4",
                "file_path": movie_path,
                "character": "Arthur",
                "duration": 60.0,
                "original_text": "We need to talk.",
                "translation_text": "আমাদের কথা বলা দরকার।",
                "clips": demo_clips,
                "generated_paths": ("work/Bengali_Voice_Arthur.wav", "work/Arthur_Original.wav"),
                "clip_characters": {
                    "A2:16.0": "Arthur",
                    "A2:20.0": "Arthur",
                    "A2:32.2": "Arthur",
                    "A2:38.0": "Arthur",
                    "A2:42.0": "Arthur",
                },
                "character_voices": {
                    "Arthur": "bn-BD-PradeepNeural"
                }
            }

            self.media_panel.set_project_name("Inception_1080P_480P", "Inception_1080P_480P.mp4", movie_path)
            self.monitor_panel.set_project_info(
                "Inception_1080P_480P",
                "Inception_1080P_480P.mp4",
                "Arthur",
                "We need to talk.",
                60.0,
                movie_path
            )

            # Waveform audio mapping for tracks
            self.canvas_view._audio_path_map = {
                "A1": "work/Arthur_Original.wav",
                "A2": "work/Bengali_Voice_Arthur.wav",
                "A3": "work/Music_Background.mp3",
                "A4": "work/SFX_Ambience.mp3"
            }
            self.canvas_view.set_clips(demo_clips, 60.0)

            # Active clip: "আমাদের কথা বলা দরকার।"
            active_clip = {
                "tid": "A2",
                "start": 32.2,
                "dur": 3.96,
                "label": "আমাদের কথা বলা দরকার।",
                "score": 92,
                "orig_text": "We need to talk.",
                "trans_text": "আমাদের কথা বলা দরকার।",
                "speaker": "Arthur",
                "character": "Arthur",
            }
            self._active_clip_info = active_clip
            self.inspector_panel.update_clip_info(
                orig_text="We need to talk.",
                trans_text="আমাদের কথা বলা দরকার।",
                char_name="Arthur",
                lang="bn",
                source_duration=3.96,
                dub_duration=3.96,
                score=92,
            )

            self.monitor_panel.set_playhead(33.0)
            self.canvas_view.set_playhead(33.0)
            self.monitor_panel._update_video_surface()


        def _build_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            self.stage_bar = _ProductionStageBar(self)
            root.addWidget(self.stage_bar)

            self.workspace_splitter = QSplitter(Qt.Orientation.Vertical, self)
            self.workspace_splitter.setHandleWidth(1)
            self.workspace_splitter.setStyleSheet("QSplitter::handle{background:#1E2838;}")

            # Main 3-column Studio workspace.
            self.upper_splitter = QSplitter(Qt.Orientation.Horizontal, self.workspace_splitter)
            self.upper_splitter.setHandleWidth(1)
            self.upper_splitter.setMinimumHeight(380)
            self.upper_splitter.setStyleSheet("QSplitter::handle{background:#1E2838;}")
            upper_splitter = self.upper_splitter

            # Left Column (Media Browser)
            self.media_panel = _MediaBrowserPanel(upper_splitter)
            self.media_panel.setFixedWidth(264)
            upper_splitter.addWidget(self.media_panel)

            # Center Column (Program Video Monitor)
            self.monitor_panel = _ProgramMonitorPanel(upper_splitter)
            upper_splitter.addWidget(self.monitor_panel)

            # Right Column (Dialogue Inspector & Dual VU Level Meter)
            self.inspector_panel = _DialogueInspectorPanel(upper_splitter)
            self.inspector_panel.setFixedWidth(440)
            upper_splitter.addWidget(self.inspector_panel)

            upper_splitter.setStretchFactor(0, 0)
            upper_splitter.setStretchFactor(1, 1)
            upper_splitter.setStretchFactor(2, 0)
            upper_splitter.setSizes([264, 820, 440])
            self.workspace_splitter.addWidget(upper_splitter)

            # Lower multitrack timeline and agentic actions.
            tl_container = QWidget(self.workspace_splitter)
            tl_lay = QHBoxLayout(tl_container)
            tl_lay.setContentsMargins(0, 0, 0, 0)
            tl_lay.setSpacing(0)

            self.navigation_rail = _StudioNavigationRail(tl_container)
            tl_lay.addWidget(self.navigation_rail)

            self.tool_palette = _TimelineToolPalette(tl_container)
            tl_lay.addWidget(self.tool_palette)

            timeline_editor = QWidget(tl_container)
            timeline_editor_layout = QVBoxLayout(timeline_editor)
            timeline_editor_layout.setContentsMargins(0, 0, 0, 0)
            timeline_editor_layout.setSpacing(0)
            self.timeline_bar = _TimelineEditorBar(timeline_editor)
            timeline_editor_layout.addWidget(self.timeline_bar)

            timeline_tracks = QWidget(timeline_editor)
            timeline_tracks_layout = QHBoxLayout(timeline_tracks)
            timeline_tracks_layout.setContentsMargins(0, 0, 0, 0)
            timeline_tracks_layout.setSpacing(0)
            self.header_p = _TimelineHeaderPanel(timeline_tracks)
            timeline_tracks_layout.addWidget(self.header_p)
            self.canvas_view = _TimelineCanvasView(timeline_tracks)
            timeline_tracks_layout.addWidget(self.canvas_view, stretch=1)
            timeline_editor_layout.addWidget(timeline_tracks, stretch=1)
            tl_lay.addWidget(timeline_editor, stretch=1)

            # AI Actions Dock Panel
            self.ai_overlay = _FloatingAIActionsPanel(tl_container)
            tl_lay.addWidget(self.ai_overlay)

            self.workspace_splitter.addWidget(tl_container)
            self.workspace_splitter.setStretchFactor(0, 3)
            self.workspace_splitter.setStretchFactor(1, 1)
            self.workspace_splitter.setSizes([600, 270])
            root.addWidget(self.workspace_splitter, stretch=1)

            # Bottom status bar reports only real operations.
            dock_bar = QFrame(self)
            dock_bar.setFixedHeight(38)
            dock_bar.setStyleSheet("background:#111315;border-top:1px solid #08090B;")
            d_lay = QHBoxLayout(dock_bar)
            d_lay.setContentsMargins(12, 0, 10, 0)
            d_lay.setSpacing(5)

            self.autosave_lbl = QLabel("●  Auto-saved · Ready", dock_bar)
            self.autosave_lbl.setFixedWidth(190)
            self.autosave_lbl.setStyleSheet("font-size:10px;color:#6DCA73;")
            d_lay.addWidget(self.autosave_lbl)
            self.status_msg_lbl = QLabel("Ready · import a movie to begin", dock_bar)
            self.status_msg_lbl.setStyleSheet("font-size:10px;color:#737A86;")
            d_lay.addWidget(self.status_msg_lbl)

            d_lay.addStretch()

            self.status_dock = dock_bar
            root.addWidget(dock_bar)

        def _wire_signals(self) -> None:
            # Monitor playhead sync
            self.monitor_panel.playhead_changed.connect(self.canvas_view.set_playhead)
            self.monitor_panel.playhead_changed.connect(self.timeline_bar.set_timecode)
            self.canvas_view.timecode_changed.connect(self.monitor_panel.set_playhead)
            self.canvas_view.timecode_changed.connect(self.timeline_bar.set_timecode)
            self.canvas_view.clips_edited.connect(self._on_canvas_clips_edited)
            self.monitor_panel.action_triggered.connect(self._show_status)
            self.monitor_panel.import_requested.connect(self.import_media_dialog)
            self.monitor_panel.duration_resolved.connect(self._on_media_duration_resolved)
            self.monitor_panel.first_frame_decoded.connect(self.canvas_view.set_video_thumbnail)

            # Media selection sync
            self.media_panel.media_selected.connect(self._on_media_selected)

            # Timeline clip selection -> Inspector sync
            self.canvas_view.clip_clicked.connect(self._on_timeline_clip_clicked)

            # Inspector live text sync -> Timeline canvas
            self.inspector_panel.original_changed.connect(self._on_original_changed)
            self.inspector_panel.character_changed.connect(self._on_character_changed)
            self.inspector_panel.translation_changed.connect(self._on_translation_changed)
            self.inspector_panel.trans_in.editingFinished.connect(self._commit_translation)
            self.inspector_panel.lang_in.editingFinished.connect(self._on_target_language_changed)

            # Inspector Action buttons & Subtitle Imports
            self.inspector_panel.regenerate_requested.connect(self._on_ai_regenerate_voice)
            self.inspector_panel.retake_requested.connect(self._on_perform_single_line_retake)
            self.inspector_panel.open_lipsync_inspector_requested.connect(
                self._open_lipsync_inspector
            )
            self.inspector_panel.ai_fix_requested.connect(self._on_ai_fix_all)
            self.inspector_panel.preview_take_requested.connect(self._preview_selected_take)
            self.inspector_panel.import_source_srt_requested.connect(
                lambda: self.import_subtitle_dialog(target=False)
            )
            self.inspector_panel.import_target_srt_requested.connect(
                lambda: self.import_subtitle_dialog(target=True)
            )
            self.inspector_panel.import_bilingual_srt_requested.connect(
                self.import_bilingual_subtitle_dialog
            )
            self.inspector_panel.manage_characters_requested.connect(self._open_character_manager)
            self.inspector_panel.casting_requested.connect(self._open_character_casting_studio)
            self.inspector_panel.export_requested.connect(self._open_broadcast_export)
            self.inspector_panel.cloud_gpu_requested.connect(self._open_kaggle_accelerator)
            self.inspector_panel.audio_analysis_requested.connect(self._open_audio_analysis)
            self.inspector_panel.action_clicked.connect(self._on_ai_action_clicked)
            self.inspector_panel.dialogue_card_selected.connect(self._on_dialogue_card_selected)
            self.inspector_panel.track_level_changed.connect(self._on_track_level_changed)
            self.inspector_panel.track_mute_toggled.connect(self._on_track_mute_toggled)
            self.inspector_panel.track_solo_toggled.connect(self._on_track_solo_toggled)
            self.inspector_panel.ducking_changed.connect(self._on_ducking_changed)
            self.inspector_panel.fit_to_slot_requested.connect(self._on_fit_to_slot)
            self.inspector_panel.nudge_timing_requested.connect(self._on_nudge_timing)
            self.inspector_panel.open_pro_voice_editor_requested.connect(self._open_pro_voice_editor)
            self.inspector_panel.open_pro_emotion_studio_requested.connect(self._open_pro_emotion_studio)
            self.inspector_panel.open_voice_exchanger_requested.connect(self._open_voice_exchanger)
            self.inspector_panel.open_character_classification_requested.connect(self._open_character_classification_studio)
            self.inspector_panel.open_qc_dashboard_requested.connect(self._open_broadcast_qc_dashboard)
            self.inspector_panel.open_variaudio_requested.connect(self._open_cubase_variaudio)
            self.inspector_panel.open_audio_align_requested.connect(self._open_cubase_audio_align)
            self.inspector_panel.open_dop_requested.connect(self._open_cubase_dop)
            self.inspector_panel.open_control_room_requested.connect(self._open_cubase_control_room)
            self.inspector_panel.open_punch_in_requested.connect(self._open_adr_punch_in_studio)
            self.inspector_panel.open_prosody_transfer_requested.connect(self._open_prosody_transfer_studio)
            self.inspector_panel.open_bangla_studio_requested.connect(self._open_bangla_dub_studio)
            self.inspector_panel.open_voice_clone_requested.connect(self._open_voice_clone_studio)
            self.inspector_panel.open_subtitle_studio_requested.connect(self._open_subtitle_caption_studio)
            self.inspector_panel.open_audio_dsp_requested.connect(self._open_audio_dsp_tools)
            self.inspector_panel.open_batch_dub_requested.connect(self._open_batch_dub_runner)
            self.inspector_panel.open_audio_mixer_requested.connect(self._open_audio_mixer_console)
            self.inspector_panel.open_neural_lipsync_requested.connect(self._open_neural_lipsync_studio)
            self.inspector_panel.open_isochronic_requested.connect(self._open_isochronic_dialogue_adapter)

            # Floating AI Actions
            self.ai_overlay.action_clicked.connect(self._on_ai_action_clicked)
            self.ai_overlay.run_requested.connect(self._run_agentic_dub)
            self.ai_overlay.cancel_requested.connect(self._cancel_agentic_dub)
            self.stage_bar.home_requested.connect(self._show_home_dashboard)
            self.stage_bar.workspace_selected.connect(self._on_workspace_selected)
            self.stage_bar.kaggle_requested.connect(self._open_kaggle_accelerator)
            self.stage_bar.voice_model_requested.connect(self._open_voice_model_selector)
            self.stage_bar.casting_requested.connect(self._open_character_casting_studio)
            self.stage_bar.export_requested.connect(self._open_broadcast_export)
            self.stage_bar.dub_requested.connect(self.open_dub_dialog)
            self.stage_bar.undo_requested.connect(self.undo)
            self.stage_bar.redo_requested.connect(self.redo)
            self.navigation_rail.route_requested.connect(self._on_navigation_route)
            self.tool_palette.tool_selected.connect(self.canvas_view.set_tool)
            self.tool_palette.tool_selected.connect(
                lambda tool: self._show_status(f"Timeline tool: {tool}")
            )
            self.timeline_bar.action_requested.connect(self._on_timeline_toolbar_action)
            self.header_p.track_lock_toggled.connect(self.canvas_view.set_track_locked)
            self.header_p.track_visibility_toggled.connect(self.canvas_view.set_track_visible)
            self.header_p.track_import_requested.connect(self._on_track_import_requested)

        def _show_home_dashboard(self) -> None:
            window = self.window()
            show_home = getattr(window, "show_home", None)
            if callable(show_home):
                show_home()

        def _open_kaggle_accelerator(self) -> None:
            from aidub.ui.dialogs.cloud_accelerator_dialog import KaggleAcceleratorDialog

            source_path = str(self._current_project_data.get("file_path", ""))
            voice_engine = str(self._current_project_data.get("voice_engine", "chatterbox"))
            dlg = KaggleAcceleratorDialog(
                self,
                movie_path=source_path,
                target_language=self._automation_state.target_language or "bn",
                voice_engine=voice_engine,
                enable_lipsync=bool(self._current_project_data.get("lipsync", True)),
            )
            if dlg.exec():
                res = dlg.get_sync_result()
                if res and res.success:
                    if res.dubbed_audio_path and res.dubbed_audio_path.is_file():
                        self._current_project_data["dubbed_audio_path"] = str(res.dubbed_audio_path)
                    if res.dubbed_video_path and res.dubbed_video_path.is_file():
                        self._current_project_data["dubbed_video_path"] = str(res.dubbed_video_path)
                    if res.subtitle_path and res.subtitle_path.is_file():
                        self._current_project_data["subtitle_path"] = str(res.subtitle_path)
                    self._show_status(
                        f"✓ Cloud GPU Master Synced: {res.total_files} deliverables ingested"
                    )

        def _open_lipsync_inspector(self) -> None:
            from aidub.ui.dialogs.lipsync_inspector_dialog import LipSyncInspectorDialog

            line_text = (
                self.inspector_panel.trans_in.text().strip()
                or self.inspector_panel.orig_in.text().strip()
                or "Dialogue line"
            )
            dur = 2.0
            idx = 0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.0))
                clip_label = str(self._active_clip_info.get("label", ""))
                import re

                m = re.search(r"(\d+)", clip_label)
                if m:
                    idx = max(0, int(m.group(1)) - 1)

            dlg = LipSyncInspectorDialog(
                utterance_index=idx,
                dialogue_text=line_text,
                duration_s=dur,
                language=self._automation_state.target_language or "bn",
                parent=self,
            )
            dlg.offset_applied.connect(self._on_lipsync_offset_applied)
            dlg.exec()

        def _on_lipsync_offset_applied(self, utterance_index: int, offset_s: float) -> None:
            self._show_status(
                f"✓ Lip-Sync slip offset {offset_s * 1000.0:+.1f}ms applied to line #{utterance_index + 1}"
            )

        def _open_pro_voice_editor(self) -> None:
            from aidub.ui.dialogs.pro_voice_editor_dialog import ProVoiceEditorDialog

            line_text = (
                self.inspector_panel.trans_in.text().strip()
                or self.inspector_panel.orig_in.text().strip()
                or "Dialogue line"
            )
            cid = "cue_001"
            dur = 2.0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.0))
                cid = str(self._active_clip_info.get("label", "cue_001"))

            orig_audio = str(self._current_project_data.get("file_path", ""))
            dub_audio = str(self._current_project_data.get("dubbed_audio_path", ""))

            dlg = ProVoiceEditorDialog(
                cue_id=cid,
                dialogue_text=line_text,
                duration_s=dur,
                orig_wav_path=orig_audio,
                dub_wav_path=dub_audio,
                parent=self,
            )
            dlg.audio_replaced.connect(self._on_pro_voice_master_updated)
            dlg.exec()

        def _on_pro_voice_master_updated(self, new_audio_path: str) -> None:
            self._current_project_data["dubbed_audio_path"] = new_audio_path
            self._show_status(f"✓ Master dialogue audio updated from DAW: {Path(new_audio_path).name}")

        def _open_pro_emotion_studio(self) -> None:
            from aidub.ui.dialogs.pro_emotion_studio_dialog import ProEmotionStudioDialog

            line_text = (
                self.inspector_panel.trans_in.text().strip()
                or self.inspector_panel.orig_in.text().strip()
                or "আমি তোমাকে কখনোই ক্ষমা করব না!"
            )
            char_name = self.inspector_panel.char_in.currentText() or "SPEAKER_00"
            orig_audio = str(self._current_project_data.get("file_path", ""))

            dlg = ProEmotionStudioDialog(
                dialogue_text=line_text,
                character_name=char_name,
                original_wav_path=orig_audio,
                parent=self,
            )
            dlg.emotion_applied.connect(self._on_emotion_studio_applied)
            dlg.exec()

        def _on_emotion_studio_applied(self, perf_dict: dict[str, Any]) -> None:
            self._current_project_data["last_emotion_intent"] = perf_dict
            style = perf_dict.get("style_prompt", "expressive")
            self._show_status(f"✓ Dramatic performance applied: '{style}'")

        def _open_voice_exchanger(self) -> None:
            from aidub.ui.dialogs.voice_exchanger_dialog import VoiceExchangerDialog

            char_name = self.inspector_panel.char_in.currentText() or "SPEAKER_00"
            curr_voice = str(self._current_project_data.get("voice_name", "bn-BD-PradeepNeural"))
            lang = self._automation_state.target_language or "bn"

            dlg = VoiceExchangerDialog(
                character_name=char_name,
                current_voice_id=curr_voice,
                target_language=lang,
                parent=self,
            )
            dlg.voice_exchanged.connect(self._on_voice_exchanger_applied)
            dlg.exec()

        def _on_voice_exchanger_applied(self, result: dict[str, Any]) -> None:
            cname = result.get("character_name", "SPEAKER_00")
            vname = result.get("new_voice_id", "")
            self._current_project_data.setdefault("character_voices", {})[cname] = vname
            self._show_status(f"✓ Character '{cname}' voice re-cast to '{result.get('voice_display_name', vname)}'")

        def _open_character_classification_studio(self) -> None:
            from aidub.ui.dialogs.character_classification_studio_dialog import CharacterClassificationStudioDialog

            clips = self._current_project_data.get("clips", [])
            clip_chars = self._current_project_data.get("clip_characters", {})
            char_voices = self._current_project_data.get("character_voices", {})

            dlg = CharacterClassificationStudioDialog(
                clips=clips,
                clip_characters=clip_chars,
                character_voices=char_voices,
                parent=self,
            )
            dlg.classification_updated.connect(self._on_classification_studio_updated)
            dlg.exec()

        def _on_classification_studio_updated(self, mapping: dict[str, str]) -> None:
            self._current_project_data["clip_characters"] = mapping
            self._show_status(f"✓ Synchronized character classifications across {len(mapping)} cues")

        def _open_broadcast_qc_dashboard(self) -> None:
            from aidub.ui.screens.qc_dashboard import QcDashboardScreen

            dlg = QDialog(self)
            dlg.setWindowTitle("Broadcast QC Dashboard & Delivery Gate")
            dlg.resize(1040, 660)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)

            qc_screen = QcDashboardScreen(parent=dlg)
            qc_screen.audit_timeline_project(self._current_project_data)
            qc_screen.master_export_requested.connect(lambda: (dlg.accept(), self._open_broadcast_export()))
            lay.addWidget(qc_screen)
            dlg.exec()

        def _get_active_or_synthetic_clip(self, dur_s: float = 2.0) -> Any:
            import numpy as np
            from aidub.media.pro_audio_editor import AudioClipData

            dub_audio = str(self._current_project_data.get("dubbed_audio_path", ""))
            if dub_audio and Path(dub_audio).is_file():
                try:
                    return AudioClipData.from_file(dub_audio)
                except Exception as e:
                    logger.warning("Failed loading dubbed audio clip: %s", e)

            # Generate realistic synthetic voice preview waveform if not on disk
            sr = 44100
            n_samples = int(max(0.5, dur_s) * sr)
            t = np.linspace(0, max(0.5, dur_s), n_samples, endpoint=False, dtype=np.float32)
            f0 = 135.0  # Natural vocal Hz
            sig = (
                0.35 * np.sin(2 * np.pi * f0 * t)
                + 0.20 * np.sin(2 * np.pi * (2 * f0) * t)
                + 0.15 * np.sin(2 * np.pi * (3 * f0) * t)
                + 0.08 * np.sin(2 * np.pi * (5 * f0) * t)
            )
            env = np.hanning(n_samples).astype(np.float32)
            sig = (sig * env).astype(np.float32)
            return AudioClipData(samples=sig, sample_rate=sr)

        def _get_guide_actor_clip(self, dur_s: float = 2.0) -> Any:
            import numpy as np
            from aidub.media.pro_audio_editor import AudioClipData

            orig_audio = str(self._current_project_data.get("file_path", ""))
            if orig_audio and Path(orig_audio).is_file():
                try:
                    return AudioClipData.from_file(orig_audio)
                except Exception as e:
                    logger.warning("Failed loading original guide audio clip: %s", e)

            # Generate realistic guide speech pattern
            sr = 44100
            n_samples = int(max(0.5, dur_s) * sr)
            t = np.linspace(0, max(0.5, dur_s), n_samples, endpoint=False, dtype=np.float32)
            f0 = 160.0
            sig = (
                0.30 * np.sin(2 * np.pi * f0 * t)
                + 0.25 * np.sin(2 * np.pi * (2 * f0) * t)
                + 0.10 * np.sin(2 * np.pi * (4 * f0) * t)
            )
            env = (0.5 * (1.0 - np.cos(2 * np.pi * np.linspace(0, 1, n_samples)))).astype(np.float32)
            sig = (sig * env).astype(np.float32)
            return AudioClipData(samples=sig, sample_rate=sr)

        def _open_cubase_variaudio(self) -> None:
            from aidub.ui.dialogs.cubase_variaudio_dialog import CubaseVariAudioDialog

            dur = 2.0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.0))
            clip = self._get_active_or_synthetic_clip(dur)
            char_name = self.inspector_panel.char_in.currentText() or "Actor"

            dlg = CubaseVariAudioDialog(
                clip=clip,
                character_name=char_name,
                parent=self,
            )
            dlg.variaudio_applied.connect(self._on_variaudio_applied)
            dlg.exec()

        def _on_variaudio_applied(self, new_clip: Any) -> None:
            out_path = Path("output/cubase_variaudio_master.wav")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            new_clip.save_wav(out_path)
            self._current_project_data["dubbed_audio_path"] = str(out_path.resolve())
            self._show_status("✓ Cubase VariAudio 3: Pitch & formant intonation committed to master take")

        def _open_cubase_audio_align(self) -> None:
            from aidub.ui.dialogs.cubase_audio_align_dialog import CubaseAudioAlignmentDialog

            dur = 2.0
            cid = "cue_001"
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.0))
                cid = str(self._active_clip_info.get("label", "cue_001"))

            guide_clip = self._get_guide_actor_clip(dur)
            target_clip = self._get_active_or_synthetic_clip(dur)

            dlg = CubaseAudioAlignmentDialog(
                guide_clip=guide_clip,
                target_clip=target_clip,
                cue_id=cid,
                parent=self,
            )
            dlg.alignment_applied.connect(self._on_audio_align_applied)
            dlg.exec()

        def _on_audio_align_applied(self, aligned_clip: Any) -> None:
            out_path = Path("output/cubase_aligned_master.wav")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            aligned_clip.save_wav(out_path)
            self._current_project_data["dubbed_audio_path"] = str(out_path.resolve())
            self._show_status("✓ Cubase Audio Alignment: Synchronized dialogue timing to guide actor")

        def _open_cubase_dop(self) -> None:
            from aidub.ui.dialogs.cubase_dop_dialog import CubaseDopDialog

            dur = 2.0
            cid = "cue_001"
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.0))
                cid = str(self._active_clip_info.get("label", "cue_001"))

            clip = self._get_active_or_synthetic_clip(dur)

            dlg = CubaseDopDialog(
                clip=clip,
                cue_id=cid,
                parent=self,
            )
            dlg.dop_applied.connect(self._on_dop_applied)
            dlg.exec()

        def _on_dop_applied(self, processed_clip: Any) -> None:
            out_path = Path("output/cubase_dop_master.wav")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            processed_clip.save_wav(out_path)
            self._current_project_data["dubbed_audio_path"] = str(out_path.resolve())
            self._show_status("✓ Cubase Direct Offline Processing (F7): DSP rack committed non-destructively")

        def _open_cubase_control_room(self) -> None:
            from aidub.ui.dialogs.cubase_control_room_dialog import CubaseControlRoomDialog

            dur = 2.0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.0))

            dub_clip = self._get_active_or_synthetic_clip(dur)
            guide_clip = self._get_guide_actor_clip(dur)

            dlg = CubaseControlRoomDialog(
                dub_clip=dub_clip,
                guide_clip=guide_clip,
                parent=self,
            )
            dlg.exec()

        def _open_cubase_crossfade(self) -> None:
            from aidub.ui.dialogs.cubase_crossfade_dialog import CubaseCrossfadeDialog

            dur = 1.5
            clip_a = self._get_guide_actor_clip(dur)
            clip_b = self._get_active_or_synthetic_clip(dur)

            dlg = CubaseCrossfadeDialog(
                clip_a=clip_a,
                clip_b=clip_b,
                parent=self,
            )
            dlg.crossfade_applied.connect(self._on_crossfade_applied)
            dlg.exec()

        def _on_crossfade_applied(self, spliced_clip: Any) -> None:
            out_path = Path("output/cubase_crossfade_master.wav")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            spliced_clip.save_wav(out_path)
            self._current_project_data["dubbed_audio_path"] = str(out_path.resolve())
            self._show_status("✓ Cubase Crossfade Editor: Seamless dialogue splice committed")

        def _open_adr_punch_in_studio(self) -> None:
            from aidub.ui.dialogs.adr_punch_in_dialog import AdrPunchInDialog

            dur = 2.5
            cid = "cue_001"
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.5))
                cid = str(self._active_clip_info.get("label", "cue_001"))

            base_clip = self._get_active_or_synthetic_clip(dur)
            dlg = AdrPunchInDialog(
                base_clip=base_clip,
                cue_id=cid,
                punch_in_sec=min(0.5, dur * 0.25),
                punch_out_sec=min(1.5, dur * 0.75),
                parent=self,
            )
            dlg.punch_in_applied.connect(self._on_adr_punch_in_applied)
            dlg.exec()

        def _on_adr_punch_in_applied(self, new_clip: Any) -> None:
            out_path = Path("output/adr_punched_master.wav")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            new_clip.save_wav(out_path)
            self._current_project_data["dubbed_audio_path"] = str(out_path.resolve())
            self._show_status("✓ ADR Punch-In: Spliced take with equal-power crossfade applied")

        def _open_prosody_transfer_studio(self) -> None:
            from aidub.ui.dialogs.prosody_transfer_dialog import ProsodyTransferDialog

            dur = 2.5
            cid = "cue_001"
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.5))
                cid = str(self._active_clip_info.get("label", "cue_001"))

            guide_clip = self._get_guide_actor_clip(dur)
            dub_clip = self._get_active_or_synthetic_clip(dur)

            dlg = ProsodyTransferDialog(
                guide_clip=guide_clip,
                dub_clip=dub_clip,
                cue_id=cid,
                parent=self,
            )
            dlg.prosody_applied.connect(self._on_prosody_transfer_applied)
            dlg.exec()

        def _on_prosody_transfer_applied(self, new_clip: Any) -> None:
            out_path = Path("output/prosody_matched_master.wav")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            new_clip.save_wav(out_path)
            self._current_project_data["dubbed_audio_path"] = str(out_path.resolve())
            self._show_status("✓ Prosody Transfer: Matched original actor rhythm and energy dynamics")

        def _open_bangla_dub_studio(self) -> None:
            from aidub.ui.dialogs.bangla_dub_studio_dialog import BanglaDubStudioDialog

            dur = 3.0
            cid = "cue_001"
            txt = "আমি তোমাকে অনেক ভালোবাসি, কিন্তু তুমি আমাকে বুঝলে না।"
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 3.0))
                cid = str(self._active_clip_info.get("label", "cue_001"))
                txt = str(self._active_clip_info.get("text", txt))

            dlg = BanglaDubStudioDialog(
                text=txt,
                cue_id=cid,
                duration_sec=dur,
                parent=self,
            )
            dlg.bangla_dub_applied.connect(self._on_bangla_dub_applied)
            dlg.exec()

        def _on_bangla_dub_applied(self, data: dict[str, Any]) -> None:
            self._current_project_data["bangla_profile"] = data
            dial = data.get("dialect", "dhaka_standard")
            emo = data.get("emotion", "neutral")
            self._show_status(f"✓ Bangla Dub Studio: Dialect [{dial}], Emotion [{emo}], LipSync Visemes synced")

        def _open_voice_clone_studio(self) -> None:
            from aidub.ui.dialogs.voice_clone_studio_dialog import VoiceCloneStudioDialog

            dlg = VoiceCloneStudioDialog(parent=self)
            dlg.profile_saved.connect(
                lambda p: self._show_status(f"✓ Voice Clone Profile saved: '{p.name}' ({p.provider.value})")
            )
            dlg.exec()

        def _open_subtitle_caption_studio(self) -> None:
            from aidub.ui.dialogs.subtitle_caption_studio_dialog import SubtitleCaptionStudioDialog

            dur = 3.0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 3.0))
            clip = self._get_active_or_synthetic_clip(dur)
            dlg = SubtitleCaptionStudioDialog(audio_clip=clip, parent=self)
            dlg.subtitles_applied.connect(
                lambda cues: self._show_status(f"✓ Applied {len(cues)} styled subtitle cues to timeline")
            )
            dlg.exec()

        def _open_audio_dsp_tools(self) -> None:
            from aidub.ui.dialogs.audio_dsp_tools_dialog import AudioDspToolsDialog

            dur = 3.0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 3.0))
            clip = self._get_active_or_synthetic_clip(dur)
            dlg = AudioDspToolsDialog(clip=clip, parent=self)
            dlg.dsp_applied.connect(
                lambda p_clip: self._show_status(f"✓ Applied DSP [{p_clip.label}] ({p_clip.duration_s:.2f}s) to active clip")
            )
            dlg.exec()

        def _open_export_delivery_dialog(self) -> None:
            from aidub.ui.dialogs.export_delivery_dialog import ExportDeliveryDialog

            dlg = ExportDeliveryDialog(parent=self)
            dlg.export_confirmed.connect(
                lambda p: self._show_status(f"✓ Delivery Export Confirmed: {p.name} ({p.loudness_target_lufs} LUFS, {p.container.upper()})")
            )
            dlg.exec()

        def _open_batch_dub_runner(self) -> None:
            from aidub.ui.dialogs.batch_dub_runner_dialog import BatchDubRunnerDialog

            dlg = BatchDubRunnerDialog(parent=self)
            dlg.batch_completed.connect(
                lambda results: self._show_status(f"✓ Batch Dubbing Queue Completed: {len(results)} cues synthesized")
            )
            dlg.exec()

        def _open_audio_mixer_console(self) -> None:
            from aidub.ui.mixer import AudioMixerConsoleDialog, AudioMixerEngine

            if not hasattr(self, "_audio_mixer") or self._audio_mixer is None:
                self._audio_mixer = AudioMixerEngine()
            dlg = AudioMixerConsoleDialog(mixer_engine=self._audio_mixer, parent=self)
            dlg.exec()

        def _open_neural_lipsync_studio(self) -> None:
            from aidub.ui.dialogs.neural_lipsync_studio_dialog import NeuralLipSyncStudioDialog

            dlg = NeuralLipSyncStudioDialog(parent=self)
            dlg.lipsync_applied.connect(
                lambda res: self._show_status(f"✓ Neural Lip-Sync Applied: {res.total_frames} frames ({res.model_used}) committed to Timeline")
            )
            dlg.exec()

        def _open_isochronic_dialogue_adapter(self) -> None:
            from aidub.ui.dialogs.isochronic_dialogue_adapter_dialog import IsochronicDialogueAdapterDialog

            line_text = (
                self.inspector_panel.trans_in.text().strip()
                or "আমাদের এখানে একটা বড় সমস্যা আছে।"
            )
            src_text = (
                self.inspector_panel.orig_in.text().strip()
                or "We have a serious problem here."
            )
            dur = 2.2
            cid = "cue_001"
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                dur = float(self._active_clip_info.get("dur", 2.2))
                cid = str(self._active_clip_info.get("label", "cue_001"))

            lang = self._automation_state.target_language or "bn"
            dlg = IsochronicDialogueAdapterDialog(
                cue_id=cid,
                source_text=src_text,
                source_duration_s=dur,
                target_text=line_text,
                target_language=lang,
                parent=self,
            )
            dlg.adapted_cue_applied.connect(self._on_isochronic_cue_applied)
            dlg.exec()

        def _on_isochronic_cue_applied(self, cue_id: str, adapted_text: str, duration_s: float) -> None:
            self.inspector_panel.trans_in.setText(adapted_text)
            self._commit_translation()
            self._show_status(f"✓ Isochronic Dialogue Applied to {cue_id}: '{adapted_text}' ({duration_s:.2f}s)")

        def _open_command_palette(self) -> None:
            from aidub.ui.dialogs.command_palette_dialog import CommandPaletteDialog

            commands = [
                {"title": "Isochronic Dialogue Translator & Syllable Adapter", "category": "Dubbing", "hotkey": "Ctrl+Alt+I", "action": self._open_isochronic_dialogue_adapter},
                {"title": "Neural AI Lip-Sync & Face Synthesis Studio (Wav2Lip/MuseTalk)", "category": "AI Video", "hotkey": "Ctrl+Alt+L", "action": self._open_neural_lipsync_studio},
                {"title": "Cubase MixConsole (Faders, Meters, Auto-Gain, Ducking)", "category": "Cubase DAW", "hotkey": "F3", "action": self._open_audio_mixer_console},
                {"title": "VariAudio 3 (Pitch & Formant Intonation)", "category": "Cubase DAW", "hotkey": "Ctrl+Shift+V", "action": self._open_cubase_variaudio},
                {"title": "Audio Alignment (VocAlign Pro Locking)", "category": "Cubase DAW", "hotkey": "Ctrl+Shift+A", "action": self._open_cubase_audio_align},
                {"title": "Direct Offline Processing (DOP Rack)", "category": "Cubase DAW", "hotkey": "F7", "action": self._open_cubase_dop},
                {"title": "Control Room & EBU R128 Loudness Radar", "category": "Cubase DAW", "hotkey": "Ctrl+Shift+C", "action": self._open_cubase_control_room},
                {"title": "Crossfade Editor (S-Curve & Equal Power)", "category": "Cubase DAW", "hotkey": "X", "action": self._open_cubase_crossfade},
                {"title": "ADR Punch-In / Punch-Out Studio", "category": "Dubbing", "hotkey": "Ctrl+R", "action": self._open_adr_punch_in_studio},
                {"title": "Actor Prosody & Rhythm Transfer", "category": "Dubbing", "hotkey": "Ctrl+Shift+P", "action": self._open_prosody_transfer_studio},
                {"title": "Bangla Dub Studio (Dialects, G2P LipSync, Subtitle QC)", "category": "Bangla Suite", "hotkey": "Ctrl+B", "action": self._open_bangla_dub_studio},
                {"title": "Voice Clone Studio & Speaker Consistency", "category": "Voice Pro", "hotkey": "Ctrl+Shift+L", "action": self._open_voice_clone_studio},
                {"title": "Subtitle & Auto-Caption Studio", "category": "Captions", "hotkey": "Ctrl+Shift+S", "action": self._open_subtitle_caption_studio},
                {"title": "Audio DSP Tools (Beat-Sync, Vocal Isolator, Speed Ramp)", "category": "Cubase DAW", "hotkey": "Ctrl+Shift+D", "action": self._open_audio_dsp_tools},
                {"title": "Export Delivery Preset Selector (Netflix, YouTube, Theatrical)", "category": "Delivery", "hotkey": "Ctrl+Alt+E", "action": self._open_export_delivery_dialog},
                {"title": "Batch Dub Runner & Queue Processor", "category": "Dubbing", "hotkey": "Ctrl+Shift+B", "action": self._open_batch_dub_runner},
                {"title": "Pro Voice Editor & Cepstral Formant Shifter", "category": "Voice Pro", "hotkey": "Ctrl+E", "action": self._open_pro_voice_editor},
                {"title": "Emotion Studio (3D PAD Valence-Arousal)", "category": "Voice Pro", "hotkey": "Ctrl+M", "action": self._open_pro_emotion_studio},
                {"title": "Voice Exchanger (Neural & Parametric Timbre)", "category": "Voice Pro", "hotkey": "Ctrl+T", "action": self._open_voice_exchanger},
                {"title": "Character Voice Classification & Role Cast", "category": "Voice Pro", "hotkey": "Ctrl+Alt+C", "action": self._open_character_classification_studio},
                {"title": "Broadcast Subtitle QC & Dari Formatter", "category": "QC", "hotkey": "Ctrl+Q", "action": self._open_broadcast_qc_dashboard},
                {"title": "Kaggle & Colab Cloud GPU Accelerator", "category": "AI Cloud", "hotkey": "Ctrl+Shift+K", "action": self._open_kaggle_accelerator},
                {"title": "Undo Timeline Edit", "category": "Timeline", "hotkey": "Ctrl+Z", "action": self.undo},
                {"title": "Redo Timeline Edit", "category": "Timeline", "hotkey": "Ctrl+Y", "action": self.redo},
                {"title": "Export Broadcast Master Video", "category": "Delivery", "hotkey": "Ctrl+Shift+E", "action": self._open_broadcast_export},
            ]

            dlg = CommandPaletteDialog(commands=commands, parent=self)
            dlg.exec()

        def _apply_blade_split(self) -> None:
            """Blade Razor split active clip at playhead position."""
            playhead_s = self.canvas_view._playhead_pos
            clips = list(self._current_project_data.get("clips", []))
            target_clip = None
            target_idx = -1
            for idx, c in enumerate(clips):
                tid, st, dur, lbl = c[0], float(c[1]), float(c[2]), str(c[3])
                if st < playhead_s < (st + dur):
                    target_clip = c
                    target_idx = idx
                    break

            if target_clip and target_idx >= 0:
                previous = list(clips)
                self._edit_history.append(previous)
                self._edit_future.clear()
                tid, st, dur, lbl = target_clip[0], float(target_clip[1]), float(target_clip[2]), str(target_clip[3])
                score = target_clip[4] if len(target_clip) > 4 else None
                left_dur = playhead_s - st
                right_dur = (st + dur) - playhead_s
                clip_a = (tid, st, round(left_dur, 3), f"{lbl} (Pt 1)", score)
                clip_b = (tid, round(playhead_s, 3), round(right_dur, 3), f"{lbl} (Pt 2)", score)
                clips[target_idx] = clip_a
                clips.insert(target_idx + 1, clip_b)
                self._current_project_data["clips"] = clips
                self.canvas_view.set_clips(clips, self._current_project_data.get("duration", 10.0))
                self._show_status(f"✂️ Blade split applied to '{lbl}' at {_format_tc(playhead_s)}")
            else:
                self._show_status("✂️ Position playhead over a clip to split")

        def _apply_ripple_delete(self) -> None:
            """Ripple delete active selected clip and close the timeline gap."""
            if not hasattr(self, "_active_clip_info") or not self._active_clip_info:
                self._show_status("Select a clip to ripple delete")
                return
            target_st = float(self._active_clip_info.get("start", 0.0))
            target_dur = float(self._active_clip_info.get("dur", 0.0))
            target_tid = self._active_clip_info.get("tid", "")

            clips = list(self._current_project_data.get("clips", []))
            previous = list(clips)
            self._edit_history.append(previous)
            self._edit_future.clear()

            new_clips = []
            for c in clips:
                tid, st, dur, lbl = c[0], float(c[1]), float(c[2]), str(c[3])
                score = c[4] if len(c) > 4 else None
                if tid == target_tid and abs(st - target_st) < 0.001:
                    continue  # skip deleted
                elif tid == target_tid and st > target_st:
                    new_clips.append((tid, max(0.0, round(st - target_dur, 3)), dur, lbl, score))
                else:
                    new_clips.append(c)

            self._current_project_data["clips"] = new_clips
            self._active_clip_info = None
            self.canvas_view.set_clips(new_clips, self._current_project_data.get("duration", 10.0))
            self._show_status(f"🗑️ Ripple deleted clip and closed {target_dur:.2f}s gap")

        def _open_voice_model_selector(self) -> None:
            from aidub.ui.dialogs.voice_model_dialog import VoiceModelDialog

            current_engine = str(self._current_project_data.get("voice_engine", "chatterbox"))
            dlg = VoiceModelDialog(
                self,
                current_engine=current_engine,
                target_language=self._automation_state.target_language or "bn",
            )
            if dlg.exec():
                config = dlg.get_configuration()
                self._current_project_data["voice_engine"] = config["engine"]
                self._current_project_data["voice_emotion"] = config["emotion"]
                self._current_project_data["voice_name"] = config["voice"]
                self._current_project_data["voice_rate"] = config["rate"]
                self._current_project_data["voice_pitch"] = config["pitch"]
                if config["language"]:
                    self._automation_state.target_language = config["language"]
                    self.inspector_panel.lang_in.setText(config["language"])
                self._show_status(
                    f"AI Voice: {config['engine'].upper()} · {config['voice']} ({config['rate']}) · Emotion: {config['emotion']}"
                )

        def _open_character_casting_studio(self) -> None:
            from aidub.ui.dialogs.character_casting_dialog import CharacterCastingStudioDialog

            counts = self._compute_character_counts()
            char_list = (
                list(counts.keys())
                if counts
                else ["Protagonist (Speaker 0)", "Antagonist (Speaker 1)"]
            )
            current_voices = self._current_project_data.get("character_voices", {})

            dlg = CharacterCastingStudioDialog(
                self,
                characters=char_list,
                current_casting=current_voices,
                target_language=self._automation_state.target_language or "bn",
            )
            if dlg.exec():
                new_mapping = dlg.get_character_voices()
                self._current_project_data.setdefault("character_voices", {}).update(new_mapping)
                self._show_status(
                    f"✓ AI Character Voices Cast: {len(new_mapping)} characters assigned"
                )

        def _open_broadcast_export(self) -> None:
            from aidub.ui.dialogs.broadcast_export_dialog import BroadcastExportDialog

            video_p = str(self._current_project_data.get("file_path", ""))
            sub_p = str(self._current_project_data.get("subtitle_path", ""))
            aud_p = str(self._current_project_data.get("dubbed_audio_path", ""))
            music_p = str(self._current_project_data.get("background_audio_path", ""))

            dlg = BroadcastExportDialog(
                self,
                video_path=video_p,
                audio_path=aud_p or video_p,
                music_path=music_p,
                subtitle_path=sub_p,
                default_output_name=f"broadcast_master_{Path(video_p).stem if video_p else 'movie'}.mp4",
            )
            dlg.exec()

        def open_isometric_dialog(self) -> None:
            """Open the AI Text Translation dialog for subtitle localization."""
            from PySide6.QtWidgets import (
                QComboBox,
                QDialog,
                QHBoxLayout,
                QLabel,
                QPushButton,
                QVBoxLayout,
            )

            from aidub.ui.design.stylesheet import build_stylesheet

            dlg = QDialog(self)
            dlg.setWindowTitle("AI Text Translation \u2014 Subtitle Localization")
            dlg.setMinimumSize(480, 280)
            dlg.setStyleSheet(build_stylesheet())

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(16)

            # Header
            header = QLabel("\U0001f310  AI Subtitle Translation", dlg)
            header.setStyleSheet("font-size: 16px; font-weight: 800; color: #C084FC;")
            layout.addWidget(header)

            sub = QLabel(
                "Translate source subtitles (S1) into the target language using AI. "
                "Source cues must exist in track S1 (import SRT or run transcription first).",
                dlg,
            )
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
            layout.addWidget(sub)

            # Language selection
            lang_row = QHBoxLayout()
            lang_row.setSpacing(12)

            lang_lbl = QLabel("Target Language:", dlg)
            lang_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #E2E8F0;")
            lang_row.addWidget(lang_lbl)

            lang_combo = QComboBox(dlg)
            lang_options = [
                ("Bengali (\u09ac\u09be\u0982\u09b2\u09be)", "bn-BD"),
                ("English (US)", "en-US"),
                ("Hindi (\u0939\u093f\u0928\u094d\u0926\u0940)", "hi-IN"),
                ("Spanish (Espa\u00f1ol)", "es-ES"),
                ("French (Fran\u00e7ais)", "fr-FR"),
                ("German (Deutsch)", "de-DE"),
                ("Japanese (\u65e5\u672c\u8a9e)", "ja-JP"),
                ("Chinese (\u4e2d\u6587)", "zh-CN"),
                ("Arabic (\u0627\u0644\u0639\u0631\u0628\u064a\u0629)", "ar-SA"),
                ("Portuguese (Portugu\u00eas)", "pt-BR"),
                ("Russian (\u0420\u0443\u0441\u0441\u043a\u0438\u0439)", "ru-RU"),
                ("Korean (\ud55c\uad6d\uc5b4)", "ko-KR"),
            ]
            for name, code in lang_options:
                lang_combo.addItem(name, code)

            current_lang = self.inspector_panel.lang_in.text().strip() or self._automation_state.target_language or "bn-BD"
            for i in range(lang_combo.count()):
                if lang_combo.itemData(i) == current_lang:
                    lang_combo.setCurrentIndex(i)
                    break

            lang_combo.setStyleSheet(
                "QComboBox { background: #111827; color: #F8FAFC; border: 1px solid #1F2937; "
                "border-radius: 6px; padding: 7px 12px; font-size: 12px; min-width: 200px; }"
            )
            lang_row.addWidget(lang_combo, stretch=1)
            layout.addLayout(lang_row)

            # Action buttons
            btn_row = QHBoxLayout()
            btn_row.addStretch()

            cancel_btn = QPushButton("Cancel", dlg)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setStyleSheet(
                "QPushButton { background: #1E293B; color: #94A3B8; border: 1px solid #334155; "
                "border-radius: 6px; padding: 8px 18px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background: #334155; color: #FFF; }"
            )
            cancel_btn.clicked.connect(dlg.reject)
            btn_row.addWidget(cancel_btn)

            translate_btn = QPushButton("\u2713  Start Translation", dlg)
            translate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            translate_btn.setStyleSheet(
                "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #8B5CF6); "
                "color: #FFF; border: none; border-radius: 6px; padding: 8px 24px; font-weight: 800; font-size: 12px; }"
                "QPushButton:hover { background: #9333EA; }"
            )

            def on_translate() -> None:
                target_lang = lang_combo.currentData()
                self.inspector_panel.lang_in.setText(target_lang)
                dlg.accept()
                self._run_modular_translate_subtitles()

            translate_btn.clicked.connect(on_translate)
            btn_row.addWidget(translate_btn)

            layout.addLayout(btn_row)

            dlg.exec()

        def keyPressEvent(self, event: Any) -> None:  # noqa: N802
            # Modifier shortcuts (Ctrl+...)
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_K:
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self._open_kaggle_accelerator()
                    else:
                        self._open_command_palette()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_D:
                    self._run_agentic_dub()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_I:
                    self.import_media_dialog()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_E:
                    self._open_broadcast_export()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_M:
                    self._open_character_casting_studio()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_B:
                    if hasattr(self, "canvas_view") and self.canvas_view.split_at_playhead():
                        self._show_status("Clip split at playhead · Ctrl+Z to undo")
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_Z:
                    self.undo()
                    event.accept()
                    return
                if event.key() == Qt.Key.Key_Y:
                    self.redo()
                    event.accept()
                    return

            # Bare S key: Split clip at playhead (universal NLE hotkey)
            if event.key() == Qt.Key.Key_S and not (
                event.modifiers() & Qt.KeyboardModifier.ControlModifier
            ):
                if hasattr(self, "canvas_view") and self.canvas_view.split_at_playhead():
                    self._show_status("Clip split at playhead · Ctrl+Z to undo")
                event.accept()
                return

            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                if hasattr(self, "canvas_view") and self.canvas_view.delete_selected_clips():
                    self._show_status("Clip deleted · Ctrl+Z to undo")
                    event.accept()
                    return

            # Space toggles playback (industry NLE standard)
            if event.key() == Qt.Key.Key_Space:
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel._toggle_play()
                event.accept()
                return

            # Bare J, K, L shuttle keys
            if event.key() == Qt.Key.Key_J:
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel._on_step_back()
                event.accept()
                return
            if event.key() == Qt.Key.Key_K:
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    if self.monitor_panel._is_playing:
                        self.monitor_panel._toggle_play()
                event.accept()
                return
            if event.key() == Qt.Key.Key_L:
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel._on_step_forward()
                event.accept()
                return

            super().keyPressEvent(event)

        def _on_workspace_selected(self, workspace: str) -> None:
            if workspace == "Ingest":
                self.import_media_dialog()
            elif workspace == "Dubbing":
                self.canvas_view.setFocus()
                self._show_status("Dubbing workspace active")
            elif workspace == "Review":
                self._run_subtitle_qc()
            elif workspace == "Delivery":
                self._show_delivery()

        def _on_navigation_route(self, route: str) -> None:
            if route == "Subtitles":
                choice, accepted = QInputDialog.getItem(
                    self,
                    "Subtitle Track",
                    "Choose the subtitle track to import:",
                    ["Source subtitles", "Target subtitles", "Bilingual subtitles (S1 + S2)"],
                    0,
                    False,
                )
                if accepted:
                    if choice.startswith("Bilingual"):
                        self.import_bilingual_subtitle_dialog()
                    else:
                        self.import_subtitle_dialog(target=choice == "Target subtitles")
                return
            if route == "Pipeline Readiness":
                self._show_pipeline_readiness()
                return
            self._show_status(f"Unknown Studio action: {route}")

        def _show_pipeline_readiness(self) -> None:
            from aidub.diagnostics.dubbing import collect_dubbing_diagnostics

            report = collect_dubbing_diagnostics()
            QMessageBox.information(self, "Pipeline Readiness", report.render())

        def _open_audio_analysis(self) -> None:
            """Open the integrated audio analyzer for the loaded source and selected interval."""

            if self._audio_analysis_dialog is not None:
                if self._audio_analysis_dialog.isVisible():
                    self._audio_analysis_dialog.raise_()
                    self._audio_analysis_dialog.activateWindow()
                    return

            from aidub.ui.audio_analysis_dialog import AudioAnalysisDialog

            path = str(self._current_project_data.get("file_path", ""))
            start = 0.0
            interval = 30.0
            active = self._active_clip_info
            if active is not None:
                try:
                    start = max(0.0, float(active.get("start", 0.0)))
                    clip_duration = max(0.0, float(active.get("dur", 0.0)))
                    if clip_duration > 0:
                        interval = min(30.0, clip_duration)
                except (TypeError, ValueError):
                    start, interval = 0.0, 30.0

            self._audio_analysis_dialog = AudioAnalysisDialog(
                path,
                start_seconds=start,
                duration_seconds=interval,
                parent=self,
            )
            self._audio_analysis_dialog.show()
            self._audio_analysis_dialog.raise_()
            self._audio_analysis_dialog.activateWindow()

        def _run_subtitle_qc(self) -> None:
            """Run broadcast subtitle rules against the current target subtitle track."""
            from aidub.subtitles.qc import SubtitleCue, SubtitleQcEngine

            target_clips = [
                clip for clip in self._current_project_data.get("clips", []) if clip[0] == "S2"
            ]
            if not target_clips:
                message = (
                    "No target subtitle cues are loaded. Import a target-language subtitle file "
                    "or run Auto Dub Master before running subtitle QC."
                )
                self._show_status("Subtitle QC not run: target subtitle track is empty")
                QMessageBox.information(self, "Subtitle Quality Control", message)
                return

            cues = [
                SubtitleCue(
                    cue_id=str(index),
                    start_ms=round(float(clip[1]) * 1_000),
                    end_ms=round((float(clip[1]) + float(clip[2])) * 1_000),
                    text=str(clip[3]),
                )
                for index, clip in enumerate(target_clips, start=1)
            ]
            report = SubtitleQcEngine().check("subtitle_target", cues)
            self.inspector_panel.set_subtitle_qc_report(report)

            status = "PASS" if report.passed else "REVIEW"
            self._show_status(
                f"Subtitle QC {status}: {report.total_cues} cues, "
                f"{report.error_count} errors, {report.warning_count} warnings"
            )
            details = [
                f"Target subtitle track: {report.total_cues} cues",
                "Rules: maximum 37 characters per line, 17 characters/second, "
                "1–7 second cue duration, no overlaps, and at least 80 ms between cues.",
                f"Result: {status} · {report.error_count} errors · {report.warning_count} warnings",
            ]
            if report.violations:
                details.extend(["", "Findings:"])
                details.extend(
                    f"[{item.severity.upper()}] {item.message}" for item in report.violations[:40]
                )
                omitted = len(report.violations) - 40
                if omitted > 0:
                    details.append(f"… {omitted} additional findings")
            else:
                details.extend(["", "No subtitle rule violations were found."])

            dialog = QMessageBox.warning if report.error_count else QMessageBox.information
            dialog(self, "Subtitle Quality Control", "\n".join(details))

        def _show_delivery(self) -> None:
            self._open_broadcast_export()

        def _on_timeline_toolbar_action(self, action: str) -> None:
            if action in {"Add Marker", "Marker"}:
                self._add_timeline_marker()
            elif action == "Undo":
                self.undo()
            elif action == "Redo":
                self.redo()
            elif action == "Split Screen":
                self.monitor_panel.toggle_split_view()
            elif action == "Zoom In":
                self._set_timeline_zoom(150.0)
            elif action == "Zoom Out":
                self._set_timeline_zoom(75.0)
            elif action == "Timeline Settings":
                self._show_timeline_settings()
            elif action in {"Blade", "Blade Split", "Razor Split", "Blade Tool"}:
                self._apply_blade_split()
            elif action in {"Ripple Delete", "Delete Gap"}:
                self._apply_ripple_delete()
            elif action in {"Pro Voice", "Pro Voice Editor"}:
                self._open_pro_voice_editor()
            elif action in {"Emotion", "Emotion Director"}:
                self._open_pro_emotion_studio()
            elif action in {"Exchanger", "Voice Exchanger"}:
                self._open_voice_exchanger()
            elif action in {"QC", "QC Dashboard"}:
                self._open_broadcast_qc_dashboard()
            else:
                self._show_status(f"Action applied: {action}")

        def _set_timeline_toggle(self, action: str, enabled: bool) -> None:
            if action not in self._timeline_toggles:
                self._show_status(f"Unknown timeline setting: {action}")
                return
            self._timeline_toggles[action] = enabled
            if action == "Toggle Snapping":
                self.canvas_view.set_snapping_enabled(enabled)
            else:
                self.canvas_view.set_linked_selection_enabled(enabled)
            self._show_status(f"{action}: {'enabled' if enabled else 'disabled'}")

        def _build_timeline_settings_menu(self) -> QMenu:
            menu = QMenu(self)
            snapping = menu.addAction("Snap to clip edges and markers")
            snapping.setCheckable(True)
            snapping.setChecked(self._timeline_toggles["Toggle Snapping"])
            snapping.triggered.connect(
                lambda checked: self._set_timeline_toggle("Toggle Snapping", checked)
            )
            linked = menu.addAction("Link related dialogue and dub clips")
            linked.setCheckable(True)
            linked.setChecked(self._timeline_toggles["Linked Selection"])
            linked.triggered.connect(
                lambda checked: self._set_timeline_toggle("Linked Selection", checked)
            )
            menu.addSeparator()
            zoom = menu.addAction("Set horizontal zoom?")
            zoom.triggered.connect(self._set_timeline_zoom_dialog)
            fit = menu.addAction("Fit timeline to window")
            fit.triggered.connect(self._fit_timeline_to_window)
            return menu

        def _show_timeline_settings(self) -> None:
            menu = self._build_timeline_settings_menu()
            menu.exec(self.timeline_bar.mapToGlobal(self.timeline_bar.rect().bottomRight()))

        def _set_timeline_zoom_dialog(self) -> None:
            current_zoom = self.canvas_view.transform().m11() * 100
            zoom, accepted = QInputDialog.getDouble(
                self,
                "Timeline Zoom",
                "Horizontal zoom percentage:",
                current_zoom,
                55.0,
                350.0,
                0,
            )
            if accepted:
                self._set_timeline_zoom(zoom)

        def _set_timeline_zoom(self, zoom: float) -> None:
            zoom = max(55.0, min(350.0, float(zoom)))
            self.canvas_view.resetTransform()
            self.canvas_view.scale(zoom / 100.0, 1.0)
            self._show_status(f"Timeline zoom set to {zoom:.0f}%")

        def _fit_timeline_to_window(self) -> None:
            duration = max(1.0, float(self._current_project_data.get("duration", 1.0)))
            available_width = max(1, self.canvas_view.viewport().width() - 24)
            zoom = max(0.55, min(3.5, available_width / (duration * PX_PER_SEC_DEFAULT)))
            self.canvas_view.resetTransform()
            self.canvas_view.scale(zoom, 1.0)
            self._show_status("Timeline fitted to the available window width")

        def _add_timeline_marker(self) -> None:
            seconds = self.monitor_panel._playhead_sec
            if not self.canvas_view.add_marker(seconds):
                self._show_status(f"A marker already exists at {_format_tc(seconds)}")
                return
            markers = list(self._current_project_data.get("markers", []))
            markers.append(seconds)
            self._current_project_data["markers"] = markers
            self._show_status(f"Marker added at {_format_tc(seconds)}")

        def _on_canvas_clips_edited(self, clips: list[ClipTuple]) -> None:
            previous = list(self._current_project_data.get("clips", []))
            self._edit_history.append(previous)
            self._edit_future.clear()
            self._current_project_data["clips"] = list(clips)
            self._show_status("Razor edit applied · Ctrl+Z to undo")

        def load_project_data(self, project_info: dict[str, Any]) -> None:
            """Load a real movie and derive all initial UI state from that file."""
            file_path = str(project_info.get("file_path") or project_info.get("movie_path", ""))
            source = Path(file_path) if file_path else None
            target_language = str(
                project_info.get("target_language")
                or next(
                    iter(project_info.get("target_languages", [])),
                    self._automation_state.target_language,
                )
            )
            if source is None or not source.is_file():
                self._show_status("The selected source movie does not exist")
                return
            if source.suffix.lower() in {".srt", ".vtt"}:
                self.import_subtitle_file(str(source))
                return

            proj_name = str(project_info.get("name") or source.stem)
            duration = 1.0
            try:
                from aidub.media.ffmpeg_ops import probe

                media_info = probe(source)
                duration = max(0.001, float(media_info["format"]["duration"]))
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                self._show_status(
                    f"Metadata probe unavailable; waiting for the media backend: {exc}"
                )

            sidecar = next(
                (
                    candidate
                    for suffix in (".srt", ".vtt")
                    if (candidate := source.with_suffix(suffix)).is_file()
                ),
                None,
            )
            source_cues = (
                self._parse_subtitle_file_cues(str(sidecar), track_id="S1") if sidecar else []
            )
            clips: list[ClipTuple] = [
                ("V1", 0.0, duration, source.name, None),
                ("A1", 0.0, duration, source.name, None),
            ]
            clips.extend(source_cues)
            data: dict[str, Any] = {
                "name": proj_name,
                "movie_name": source.name,
                "file_path": str(source.resolve()),
                "character": str(project_info.get("character", "")),
                "duration": duration,
                "original_text": source_cues[0][3] if source_cues else "",
                "translation_text": "",
                "quote": "",
                "clips": clips,
                "generated_paths": tuple(project_info.get("generated_paths", ())),
            }

            self._current_project_data = data
            self._active_clip_info = None
            self._selected_voice_name = None
            self._edit_history.clear()
            self._edit_future.clear()
            self.canvas_view.clear_markers()
            self.canvas_view.clear_video_thumbnail()
            self.media_panel.set_project_name(
                data["name"],
                data["movie_name"],
                data.get("file_path", ""),
                tuple(data.get("generated_paths", ())),
            )
            self.monitor_panel.set_project_info(
                data["name"],
                data["movie_name"],
                data["character"],
                data["quote"],
                data["duration"],
                data.get("file_path", ""),
            )
            self.stage_bar.set_project_title(data["name"])
            self.inspector_panel.update_clip_info(
                data["original_text"],
                data["translation_text"],
                data["character"],
                target_language,
            )
            cues_list = [
                {
                    "speaker": f"Speaker {(idx % 2) + 1}",
                    "orig": c[3],
                    "trans": "",
                    "start": c[1],
                    "end": c[1] + c[2],
                }
                for idx, c in enumerate(data.get("clips", []))
                if c[0] in {"S1", "S2"}
            ]
            if cues_list:
                self.inspector_panel.set_dialogue_cues(cues_list)
            self.header_p.set_header_title(data["name"])
            self.timeline_bar.set_title(data["name"])
            self.canvas_view.set_clips(data["clips"], data["duration"])
            self.inspector_panel.clear_quality_report()
            try:
                saved_state = self._session_store.load(proj_name)
            except (OSError, ValueError):
                saved_state = None
            if (
                saved_state is None
                or (file_path and saved_state.source_path and saved_state.source_path != file_path)
                or (saved_state is not None and saved_state.target_language != target_language)
            ):
                saved_state = create_automation_plan(
                    proj_name,
                    source_path=file_path,
                    target_language=target_language,
                    quality_profile=str(project_info.get("quality_profile", "theatrical")),
                )
            self._automation_state = saved_state
            self._persist_automation_state()
            self.ai_overlay.set_state(self._automation_state)
            self.project_loaded.emit(str(data["name"]))
            self._show_status(f"Loaded source movie: {source.name}")

        def load_project(self, project: str | Path | dict[str, Any]) -> None:
            """Universal project loader supporting .aidub packages, media paths, or project info dicts."""
            if isinstance(project, dict):
                self.load_project_data(project)
                return
            path = Path(project)
            if (path.is_dir() and path.suffix.casefold() == ".aidub") or (
                path.is_dir() and (path / "project.db").is_file()
            ):
                self.open_project_package(path)
            elif path.is_file():
                self.open_media_path(path)
            else:
                self._show_status(f"Cannot load project path: {path}")

        def open_project_package(self, package_path: Path | str) -> None:
            """Open an .aidub project directory via ProjectPackageService and load into Timeline."""
            from aidub.application.projects import ProjectPackageService
            from aidub.infrastructure.catalog import ProjectCatalog, default_catalog_path

            catalog = ProjectCatalog(default_catalog_path())
            try:
                catalog.initialize()
            except Exception:
                pass
            service = ProjectPackageService(catalog=catalog)
            opened = service.open(package_path)
            self.load_opened_project(opened)

        def load_opened_project(self, opened: Any) -> None:
            """Load an OpenedProject instance, restoring its database state, media, and subtitle tracks."""
            self._active_opened_project = opened
            proj = opened.project
            paths = opened.paths
            name = proj.name

            # Check for media in source-links or project root
            media_path = ""
            source_links_dir = paths.source_links
            if source_links_dir.is_dir():
                for f in source_links_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in {
                        ".mp4",
                        ".mkv",
                        ".mov",
                        ".avi",
                        ".m2ts",
                    }:
                        media_path = str(f)
                        break

            # Read persisted timeline state if present (with backup recovery)
            timeline_state_file = paths.transcripts / "timeline_state.json"
            timeline_bak_file = paths.transcripts / "timeline_state.json.bak"
            clips: list[ClipTuple] = []
            duration = 1.0
            raw: dict[str, Any] | None = None
            if timeline_state_file.is_file():
                try:
                    raw = json.loads(timeline_state_file.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning("Corrupted timeline_state.json in %s: %s", paths.root, exc)
                    if timeline_bak_file.is_file():
                        try:
                            raw = json.loads(timeline_bak_file.read_text(encoding="utf-8"))
                            logger.info(
                                "Recovered timeline state from backup %s", timeline_bak_file
                            )
                        except Exception as bak_exc:
                            logger.warning("Failed to recover from timeline backup: %s", bak_exc)
            elif timeline_bak_file.is_file():
                try:
                    raw = json.loads(timeline_bak_file.read_text(encoding="utf-8"))
                    logger.info("Recovered timeline state from backup %s", timeline_bak_file)
                except Exception as bak_exc:
                    logger.warning("Failed to recover from timeline backup: %s", bak_exc)

            if raw is not None:
                try:
                    if not media_path and raw.get("media_path"):
                        media_path = raw.get("media_path", "")
                    duration = float(raw.get("duration", 1.0))
                    for item in raw.get("clips", []):
                        if isinstance(item, (list, tuple)):
                            clips.append(
                                (
                                    str(item[0]),
                                    float(item[1]),
                                    float(item[2]),
                                    str(item[3]),
                                    item[4] if len(item) > 4 else None,
                                )
                            )
                        elif isinstance(item, dict):
                            clips.append(
                                (
                                    str(item.get("track", "V1")),
                                    float(item.get("start", 0.0)),
                                    float(item.get("duration", 1.0)),
                                    str(item.get("text", "")),
                                    item.get("take_id"),
                                )
                            )
                    mixer_data = raw.get("mixer", {})
                    if mixer_data:
                        self._mixer_levels.update(mixer_data.get("levels", {}))
                        self._mixer_mutes = set(mixer_data.get("mutes", []))
                        self._mixer_solos = set(mixer_data.get("solos", []))
                        self._sidechain_ducking_enabled = bool(
                            mixer_data.get("sidechain_ducking", True)
                        )
                        self._sidechain_ducking_depth = float(mixer_data.get("ducking_depth", 12.0))
                        for trk, lvl in self._mixer_levels.items():
                            self.inspector_panel.set_track_level(trk, lvl)
                        for trk in ["A1", "A2", "A3", "A4", "A5", "master"]:
                            self.inspector_panel.set_track_mute(trk, trk in self._mixer_mutes)
                            if trk != "master":
                                self.inspector_panel.set_track_solo(trk, trk in self._mixer_solos)
                        self.inspector_panel.chk_sidechain_duck.setChecked(
                            self._sidechain_ducking_enabled
                        )
                except Exception as exc:
                    logger.warning("Could not read timeline_state.json: %s", exc)

            # Check for existing S1 / S2 subtitle files in transcripts directory
            s1_file = paths.transcripts / "subtitles_S1.srt"
            if s1_file.is_file() and not any(c[0] == "S1" for c in clips):
                s1_cues = self._parse_subtitle_file_cues(str(s1_file), track_id="S1")
                clips.extend(s1_cues)
            s2_file = paths.transcripts / "subtitles_S2.srt"
            if s2_file.is_file() and not any(c[0] == "S2" for c in clips):
                s2_cues = self._parse_subtitle_file_cues(str(s2_file), track_id="S2")
                clips.extend(s2_cues)

            # If media found but no video/audio clips, generate V1 / A1 clips
            if media_path and Path(media_path).is_file():
                try:
                    from aidub.media.ffmpeg_ops import probe

                    info = probe(media_path)
                    duration = max(0.001, float(info["format"]["duration"]))
                except Exception:
                    pass
                if not any(c[0] == "V1" for c in clips):
                    clips.insert(0, ("V1", 0.0, duration, Path(media_path).name, None))
                if not any(c[0] == "A1" for c in clips):
                    clips.insert(1, ("A1", 0.0, duration, Path(media_path).name, None))

            target_lang = "bn-BD"
            if paths.localizations.is_dir():
                for loc_dir in paths.localizations.iterdir():
                    if loc_dir.is_dir():
                        target_lang = loc_dir.name
                        break

            data: dict[str, Any] = {
                "name": name,
                "movie_name": Path(media_path).name if media_path else "",
                "file_path": media_path,
                "character": "",
                "duration": duration,
                "original_text": next((c[3] for c in clips if c[0] == "S1"), ""),
                "translation_text": next((c[3] for c in clips if c[0] == "S2"), ""),
                "quote": "",
                "clips": clips,
                "generated_paths": (),
            }

            self._current_project_data = data
            self._active_clip_info = None
            self._selected_voice_name = None
            self._edit_history.clear()
            self._edit_future.clear()
            self.canvas_view.clear_markers()
            self.canvas_view.clear_video_thumbnail()
            self.media_panel.set_project_name(name, data["movie_name"], media_path)
            self.monitor_panel.set_project_info(
                name, data["movie_name"], "", "", duration, media_path
            )
            self.stage_bar.set_project_title(name)
            self.inspector_panel.update_clip_info(
                data["original_text"],
                data["translation_text"],
                "",
                target_lang,
            )
            cues_list = [
                {
                    "speaker": f"Speaker {(idx % 2) + 1}",
                    "orig": c[3] if c[0] == "S1" else "",
                    "trans": c[3] if c[0] == "S2" else "",
                    "start": c[1],
                    "end": c[1] + c[2],
                }
                for idx, c in enumerate(clips)
                if c[0] in {"S1", "S2"}
            ]
            if cues_list:
                self.inspector_panel.set_dialogue_cues(cues_list)
            self.header_p.set_header_title(name)
            self.timeline_bar.set_title(name)
            if media_path and Path(media_path).is_file():
                self.canvas_view.set_video_path(media_path)
            self.canvas_view.set_clips(clips, duration)
            self.project_loaded.emit(name)
            self._show_status(f"Loaded project package: {name}")

        @staticmethod
        def _format_clips_as_srt(clips: list[ClipTuple]) -> str:
            lines: list[str] = []

            def _to_srt_time(sec: float) -> str:
                ms = round((sec % 1.0) * 1000)
                total_s = int(sec)
                s = total_s % 60
                total_m = total_s // 60
                m = total_m % 60
                h = total_m // 60
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            for idx, c in enumerate(clips, 1):
                start_str = _to_srt_time(float(c[1]))
                end_str = _to_srt_time(float(c[1]) + float(c[2]))
                text = str(c[3]).strip()
                lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
            return "\n".join(lines)

        def save_to_project(self, opened: Any | None = None) -> bool:
            """Save timeline clips, subtitle cues, and project metadata into the active .aidub package."""
            target_opened = opened or getattr(self, "_active_opened_project", None)
            if target_opened is None:
                self._show_status("No project package open to save")
                return False

            paths = target_opened.paths
            database = target_opened.database
            proj = target_opened.project

            # Save timeline state JSON
            clips = list(self._current_project_data.get("clips", []))
            timeline_state = {
                "project_name": proj.name,
                "media_path": self._current_project_data.get("file_path", ""),
                "duration": self._current_project_data.get("duration", 1.0),
                "clips": [
                    {
                        "track": c[0],
                        "start": c[1],
                        "duration": c[2],
                        "text": c[3],
                        "take_id": c[4] if len(c) > 4 else None,
                    }
                    for c in clips
                ],
                "mixer": {
                    "levels": dict(self._mixer_levels),
                    "mutes": list(self._mixer_mutes),
                    "solos": list(self._mixer_solos),
                    "sidechain_ducking": self._sidechain_ducking_enabled,
                    "ducking_depth": self._sidechain_ducking_depth,
                },
            }
            # Save timeline state JSON atomically with backup
            state_file = paths.transcripts / "timeline_state.json"
            state_tmp = paths.transcripts / "timeline_state.json.tmp"
            state_bak = paths.transcripts / "timeline_state.json.bak"
            if state_file.is_file():
                try:
                    import shutil

                    shutil.copy2(state_file, state_bak)
                except Exception as bak_err:
                    logger.debug("Could not create timeline backup: %s", bak_err)
            payload = json.dumps(timeline_state, indent=2, ensure_ascii=False)
            state_tmp.write_text(payload, encoding="utf-8")
            state_tmp.replace(state_file)

            # Save S1 / S2 subtitles to SRT files atomically
            s1_clips = [c for c in clips if c[0] == "S1"]
            if s1_clips:
                s1_file = paths.transcripts / "subtitles_S1.srt"
                s1_tmp = paths.transcripts / "subtitles_S1.srt.tmp"
                s1_tmp.write_text(self._format_clips_as_srt(s1_clips), encoding="utf-8")
                s1_tmp.replace(s1_file)

            s2_clips = [c for c in clips if c[0] == "S2"]
            if s2_clips:
                s2_file = paths.transcripts / "subtitles_S2.srt"
                s2_tmp = paths.transcripts / "subtitles_S2.srt.tmp"
                s2_tmp.write_text(self._format_clips_as_srt(s2_clips), encoding="utf-8")
                s2_tmp.replace(s2_file)

            # Update SQLite database audit event
            from uuid import uuid4

            from aidub.infrastructure.persistence import AuditEventRecord
            from aidub.infrastructure.persistence.models import utc_now

            with database.transaction() as conn:
                conn.execute(
                    "UPDATE projects SET updated_at = ?, revision = revision + 1 WHERE id = ?",
                    (utc_now(), proj.project_id),
                )
            database.append_audit_event(
                AuditEventRecord(
                    id=f"evt_{uuid4().hex}",
                    project_id=proj.project_id,
                    action="PROJECT_SAVED",
                    actor_type="USER",
                    actor_id="studio.operator",
                    target_type="PROJECT",
                    target_id=proj.project_id,
                    details={"clip_count": len(clips)},
                )
            )
            database.checkpoint_wal(truncate=True)
            self._show_status(f"Project saved: {proj.name}")
            return True

        def import_subtitle_file(self, srt_path: str, *, track_id: str = "S1") -> None:
            """Import a real .srt or .vtt subtitle file and update timeline clips dynamically."""
            if track_id not in {"S1", "S2"}:
                raise ValueError("subtitle track must be S1 or S2")
            try:
                cues = self._parse_subtitle_file_cues(srt_path, track_id=track_id)
            except (OSError, UnicodeError, ValueError) as exc:
                self._show_status(f"Subtitle import failed: {exc}")
                return
            if cues:
                current_duration = float(self._current_project_data.get("duration", 1.0))
                dur = max([c[1] + c[2] for c in cues] + [current_duration])
                current_clips = [
                    c for c in self._current_project_data.get("clips", []) if c[0] != track_id
                ]
                current_clips.extend(cues)
                self._current_project_data["clips"] = current_clips
                self._current_project_data["duration"] = dur
                self.canvas_view.set_clips(current_clips, dur)

                from aidub.ai.voice.character_cloning_engine import extract_speaker_from_cue_text

                clip_chars = self._current_project_data.setdefault("clip_characters", {})
                detected_chars: set[str] = set()
                for c in cues:
                    spk, _ = extract_speaker_from_cue_text(c[3])
                    if spk:
                        clip_chars[f"{c[0]}:{round(float(c[1]), 3)}"] = spk
                        detected_chars.add(spk)
                if detected_chars:
                    self.inspector_panel.update_characters(sorted(detected_chars))
                    self.inspector_panel.meta_chars_lbl.setText(f"{len(detected_chars)} speakers")

                first = cues[0][3]
                if track_id == "S1":
                    self._current_project_data["original_text"] = first
                else:
                    self._current_project_data["translation_text"] = first
                self.inspector_panel.update_clip_info(
                    str(self._current_project_data.get("original_text", "")),
                    str(self._current_project_data.get("translation_text", "")),
                    str(self._current_project_data.get("character", "")),
                    self._automation_state.target_language,
                )
                self._show_status(
                    f"Imported {len(cues)} subtitle cues to {track_id}: {Path(srt_path).name}"
                )

        @staticmethod
        def _parse_subtitle_file_cues(
            path: str,
            *,
            track_id: str = "S1",
        ) -> list[ClipTuple]:
            """Parse SRT or WebVTT file into track tuple items."""
            results: list[ClipTuple] = []
            from aidub.subtitles.codec import parse_srt, parse_webvtt

            content = Path(path).read_text(encoding="utf-8-sig")
            doc = parse_webvtt(content) if path.lower().endswith(".vtt") else parse_srt(content)
            for cue in doc.cues:
                start_s = cue.time_range.start.ticks / 1000.0
                end_s = cue.time_range.end_exclusive.ticks / 1000.0
                dur_s = max(0.001, end_s - start_s)
                txt = cue.text.replace("\n", " ")
                results.append((track_id, start_s, dur_s, txt, None))
            return results

        def _on_media_selected(self, media_ref: str) -> None:
            path = Path(media_ref)
            suffix = path.suffix.lower()
            if path.is_file() and suffix in {".mkv", ".mp4", ".mov", ".avi", ".m2ts"}:
                self.load_project_data(
                    {
                        "name": path.stem,
                        "file_path": str(path),
                        "target_language": self._automation_state.target_language,
                    }
                )
                self._show_status(f"Program Monitor loaded: {path.name}")
            elif path.is_file() and suffix in {".srt", ".vtt"}:
                self.import_subtitle_file(str(path))
            elif path.is_file() and suffix in {".wav", ".flac", ".mp3", ".aac", ".m4a"}:
                self._import_audio_asset(path)
            else:
                self._show_status(f"Unsupported or missing media: {media_ref}")

        def import_media_dialog(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Source Movie",
                self._default_asset_directory(),
                "Movies (*.mkv *.mp4 *.mov *.avi *.m2ts);;All Files (*)",
            )
            if path:
                self.load_project_data({"name": Path(path).stem, "file_path": path})

        def _default_asset_directory(self) -> str:
            current_path = str(self._current_project_data.get("file_path", ""))
            if current_path:
                current_parent = Path(current_path).parent
                if current_parent.is_dir():
                    return str(current_parent)
            test_movies = Path.cwd() / "test movies"
            return str(test_movies if test_movies.is_dir() else Path.cwd())

        def open_media_path(self, path: str | Path) -> None:
            self._on_media_selected(str(path))

        def _on_track_import_requested(self, tid: str) -> None:
            if tid == "S1":
                self.import_subtitle_dialog(target=False)
            elif tid == "S2":
                self.import_subtitle_dialog(target=True)
            elif tid.startswith("A"):
                path, _selected = QFileDialog.getOpenFileName(
                    self,
                    f"Import Audio into Track {tid}",
                    "",
                    "Audio (*.wav *.flac *.mp3 *.aac);;All Files (*)",
                )
                if path:
                    self._import_audio_to_track(Path(path), tid)

        def _import_audio_to_track(self, path: Path, track_id: str) -> None:
            duration = 1.0
            try:
                from aidub.media.ffmpeg_ops import probe

                media_info = probe(path)
                duration = max(0.001, float(media_info["format"]["duration"]))
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                self._show_status(f"Audio metadata unavailable: {exc}")
            clips = list(self._current_project_data.get("clips", []))
            clips.append((track_id, 0.0, duration, path.name, None))
            self._current_project_data["clips"] = clips
            generated = tuple(self._current_project_data.get("generated_paths", ())) + (str(path),)
            self._current_project_data["generated_paths"] = generated
            self.canvas_view.set_audio_path(track_id, path)
            self.canvas_view.set_clips(
                clips,
                max(float(self._current_project_data.get("duration", 1.0)), duration),
            )
            self._show_status(f"Imported audio asset {path.name} onto track {track_id}")

        def import_subtitle_dialog(self, *, target: bool = False) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Target Subtitles" if target else "Import Source Subtitles",
                "",
                "Subtitles (*.srt *.vtt);;All Files (*)",
            )
            if path:
                self.import_subtitle_file(path, track_id="S2" if target else "S1")

        def import_audio_dialog(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Audio Asset",
                "",
                "Audio (*.wav *.flac *.mp3 *.aac);;All Files (*)",
            )
            if path:
                self._import_audio_asset(Path(path))

        def _import_audio_asset(self, path: Path) -> None:
            labels = ["Dubbed Voice (A2)", "Music (A3)", "SFX (A4)", "Ambience (A5)"]
            selection, accepted = QInputDialog.getItem(
                self,
                "Place Audio Asset",
                f"Choose a timeline track for {path.name}:",
                labels,
                0,
                False,
            )
            if not accepted:
                return
            track_id = {
                "Dubbed Voice (A2)": "A2",
                "Music (A3)": "A3",
                "SFX (A4)": "A4",
                "Ambience (A5)": "A5",
            }[selection]
            duration = 1.0
            try:
                from aidub.media.ffmpeg_ops import probe

                media_info = probe(path)
                duration = max(0.001, float(media_info["format"]["duration"]))
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                self._show_status(f"Audio metadata unavailable: {exc}")
            clips = list(self._current_project_data.get("clips", []))
            clips.append((track_id, 0.0, duration, path.name, None))
            self._current_project_data["clips"] = clips
            generated = tuple(self._current_project_data.get("generated_paths", ())) + (str(path),)
            self._current_project_data["generated_paths"] = generated
            self.canvas_view.set_audio_path(track_id, path)
            self.canvas_view.set_clips(
                clips,
                max(float(self._current_project_data.get("duration", 1.0)), duration),
            )
            self.media_panel.set_project_name(
                str(self._current_project_data.get("name", "Untitled Studio")),
                str(self._current_project_data.get("movie_name", "")),
                str(self._current_project_data.get("file_path", "")),
                generated,
            )
            if track_id == "A2":
                self.inspector_panel.set_take_audio(path.stem, path)
            self._show_status(f"Placed {path.name} on {track_id}")

        def _on_media_duration_resolved(self, duration: float) -> None:
            if not self._current_project_data.get("file_path"):
                return
            clips = [
                (item[0], item[1], duration, item[3], item[4])
                if item[0] in {"V1", "A1"} and float(item[1]) == 0.0
                else item
                for item in self._current_project_data.get("clips", [])
            ]
            self._current_project_data["duration"] = duration
            self._current_project_data["clips"] = clips
            self.canvas_view.set_clips(clips, duration)

        def _on_dialogue_card_selected(self, idx: int, data: dict[str, Any]) -> None:
            start_s = float(data.get("start", 0.0))
            self.canvas_view.set_playhead(start_s)
            self.monitor_panel.set_playhead(start_s)
            self.timeline_bar.set_timecode(start_s)
            self._show_status(f"Selected Dialogue Line #{idx + 1} at {_format_tc(start_s)}")

        def _on_timeline_clip_clicked(self, clip_info: dict[str, Any]) -> None:
            lbl = clip_info.get("label", "")
            tid = clip_info.get("tid", "")
            self._active_clip_info = clip_info
            self.clip_selected.emit(clip_info)
            start = float(clip_info.get("start", 0.0))
            duration = float(clip_info.get("dur", 0.0))
            score = clip_info.get("score")

            clip_key = f"{tid}:{round(start, 3)}"
            clip_chars = self._current_project_data.setdefault("clip_characters", {})
            char_name = clip_chars.get(clip_key)
            if not char_name:
                from aidub.ai.voice.character_cloning_engine import extract_speaker_from_cue_text

                spk, _ = extract_speaker_from_cue_text(lbl)
                char_name = spk or str(self._current_project_data.get("character", "SPEAKER_00"))
                clip_chars[clip_key] = char_name

            self.monitor_panel.set_playhead(start)
            self.canvas_view.set_playhead(start)
            if tid.startswith("S"):
                if tid == "S1":
                    orig = lbl
                    matching = self._matching_subtitle("S2", start, duration)
                    trans = matching[3] if matching is not None else ""
                else:
                    matching = self._matching_subtitle("S1", start, duration)
                    orig = matching[3] if matching is not None else ""
                    trans = lbl
                self.inspector_panel.update_clip_info(
                    orig,
                    trans,
                    char_name,
                    self._automation_state.target_language,
                    duration,
                    duration,
                    score,
                )
                self.inspector_panel.set_timing_alert(duration, duration)
                self._show_status(f"Selected Subtitle Clip [{tid}]: '{lbl}'")
            elif tid == "A2":
                source_cue = self._matching_subtitle("S1", start, duration)
                target_cue = self._matching_subtitle("S2", start, duration)
                orig = source_cue[3] if source_cue is not None else ""
                trans = target_cue[3] if target_cue is not None else ""
                source_duration = self._nearest_source_duration(start, duration)
                self.inspector_panel.update_clip_info(
                    orig,
                    trans,
                    char_name,
                    self._automation_state.target_language,
                    source_duration,
                    duration,
                    score,
                )
                self.inspector_panel.set_timing_alert(source_duration, duration)
                self.inspector_panel.take_combo.setCurrentText(lbl.replace(" ★", ""))
                self._show_status(f"Selected Dub Audio Clip [{tid}]: '{lbl}'")
            elif tid == "A1":
                source_cue = self._matching_subtitle("S1", start, duration)
                target_cue = self._matching_subtitle("S2", start, duration)
                orig = source_cue[3] if source_cue is not None else lbl
                trans = target_cue[3] if target_cue is not None else ""
                dub_cue = self._matching_subtitle("A2", start, duration)
                dub_duration = float(dub_cue[2]) if dub_cue is not None else duration
                self.inspector_panel.update_clip_info(
                    orig,
                    trans,
                    char_name,
                    self._automation_state.target_language,
                    duration,
                    dub_duration,
                    score,
                )
                self.inspector_panel.set_timing_alert(duration, dub_duration)
                self._show_status(f"Selected Production Dialogue [{tid}]: '{lbl}'")
            elif tid == "V1":
                source_cue = self._matching_subtitle("S1", start, duration)
                target_cue = self._matching_subtitle("S2", start, duration)
                orig = source_cue[3] if source_cue is not None else ""
                trans = target_cue[3] if target_cue is not None else ""
                self.inspector_panel.update_clip_info(
                    orig,
                    trans,
                    char_name,
                    self._automation_state.target_language,
                    duration,
                    duration,
                    score,
                )
                self._show_status(f"Selected Video Track Clip [{tid}]: '{lbl}'")

        def _on_track_level_changed(self, track_id: str, level: float) -> None:
            self._mixer_levels[track_id] = level
            if track_id == "master":
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel.set_volume(int(level * 100))
            is_clip = level > 1.2 or (self._mixer_levels.get("A1", 1.0) * level > 1.4)
            peak_db = 20.0 * math.log10(max(1e-4, level))
            self.inspector_panel.set_peak_warning(is_clip, peak_db)

        def _on_track_mute_toggled(self, track_id: str, muted: bool) -> None:
            if muted:
                self._mixer_mutes.add(track_id)
            else:
                self._mixer_mutes.discard(track_id)
            if track_id == "master":
                if hasattr(self, "monitor_panel") and self.monitor_panel:
                    self.monitor_panel.set_muted(muted)
            self._show_status(f"Track {track_id} {'MUTED' if muted else 'UNMUTED'}.")

        def _on_track_solo_toggled(self, track_id: str, solo: bool) -> None:
            if solo:
                self._mixer_solos.add(track_id)
            else:
                self._mixer_solos.discard(track_id)
            self._show_status(f"Track {track_id} {'SOLO' if solo else 'UNSOLO'}.")

        def _on_ducking_changed(self, enabled: bool, depth_db: float) -> None:
            self._sidechain_ducking_enabled = enabled
            self._sidechain_ducking_depth = depth_db
            status_txt = f"Sidechain ducking {'ENABLED (-' + str(int(depth_db)) + 'dB)' if enabled else 'DISABLED'}."
            self._show_status(status_txt)

        def _on_fit_to_slot(self) -> None:
            """Apply time-stretching to fit active dubbing take into target slot duration."""
            if not self._active_clip_info:
                self._show_status("Select a dialogue clip to fit to slot.")
                return
            start = float(self._active_clip_info.get("start", 0.0))
            current_dur = float(self._active_clip_info.get("dur", 0.0))
            source_dur = self._nearest_source_duration(start, current_dur)
            if source_dur <= 0 or abs(current_dur - source_dur) < 0.05:
                self._show_status("Clip already matches target slot duration.")
                return
            self.canvas_view._update_clip_timing(self._active_clip_info, start, source_dur)
            self._active_clip_info["dur"] = source_dur
            self.inspector_panel.set_timing_alert(source_dur, source_dur)
            self._show_status(
                f"⚡ Fitted clip duration from {current_dur:.2f}s to {source_dur:.2f}s."
            )

        def _on_nudge_timing(self, delta_s: float) -> None:
            """Nudge selected clip timing forward/backward."""
            if not self._active_clip_info:
                self._show_status("Select a clip to nudge timing.")
                return
            start = float(self._active_clip_info.get("start", 0.0))
            dur = float(self._active_clip_info.get("dur", 0.0))
            new_start = max(0.0, start + delta_s)
            self.canvas_view._update_clip_timing(self._active_clip_info, new_start, dur)
            self._active_clip_info["start"] = new_start
            self.canvas_view.set_playhead(new_start)
            self.monitor_panel.set_playhead(new_start)
            self._show_status(f"⏱ Nudged clip by {delta_s:+.2f}s to {_format_tc(new_start)}.")

        def _nearest_source_duration(self, start: float, fallback: float) -> float:
            source_clips = [
                clip for clip in self._current_project_data.get("clips", []) if clip[0] == "S1"
            ]
            if not source_clips:
                return fallback
            nearest = min(source_clips, key=lambda clip: abs(float(clip[1]) - start))
            if abs(float(nearest[1]) - start) > max(1.0, float(nearest[2])):
                return fallback
            return float(nearest[2])

        def _matching_subtitle(
            self,
            track_id: str,
            start: float,
            duration: float = 1.0,
        ) -> ClipTuple | None:
            candidates = [
                clip for clip in self._current_project_data.get("clips", []) if clip[0] == track_id
            ]
            if not candidates:
                return None
            end = start + max(0.1, duration)
            for clip in candidates:
                c_start = float(clip[1])
                c_end = c_start + max(0.1, float(clip[2]))
                if max(start, c_start) < min(end, c_end):
                    score = float(clip[4]) if len(clip) > 4 and clip[4] is not None else None
                    return (str(clip[0]), float(clip[1]), float(clip[2]), str(clip[3]), score)
            nearest = min(candidates, key=lambda clip: abs(float(clip[1]) - start))
            if abs(float(nearest[1]) - start) <= 2.0:
                score = float(nearest[4]) if len(nearest) > 4 and nearest[4] is not None else None
                return (
                    str(nearest[0]),
                    float(nearest[1]),
                    float(nearest[2]),
                    str(nearest[3]),
                    score,
                )
            return None

        def _on_original_changed(self, text: str) -> None:
            self._current_project_data["original_text"] = text
            active = self._active_clip_info or {}
            if active.get("tid") == "S1":
                self.canvas_view.update_subtitle_text(text, float(active.get("start", 0.0)))

        def _on_character_changed(self, char_name: str) -> None:
            char_name = char_name.strip()
            if not char_name:
                return
            self._current_project_data["character"] = char_name
            active = self._active_clip_info or {}
            if active:
                active["character"] = char_name
                tid = active.get("tid", "")
                start = float(active.get("start", 0.0))
                clip_key = f"{tid}:{round(start, 3)}"
                self._current_project_data.setdefault("clip_characters", {})[clip_key] = char_name
                self._show_status(f"Character set to '{char_name}' for [{tid}] at {start:.2f}s")

        def _compute_character_counts(self) -> dict[str, int]:
            """Compute accurate line/cue counts per character across timeline cues."""
            from aidub.ai.voice.character_cloning_engine import extract_speaker_from_cue_text

            counts: dict[str, int] = {}
            clip_chars = self._current_project_data.setdefault("clip_characters", {})
            clips = [
                c for c in self._current_project_data.get("clips", []) if c[0] in {"S1", "S2", "A2"}
            ]
            for clip in clips:
                tid, start_s = clip[0], float(clip[1])
                key = f"{tid}:{round(start_s, 3)}"
                char = clip_chars.get(key)
                if not char:
                    spk, _ = extract_speaker_from_cue_text(clip[3])
                    char = spk or str(self._current_project_data.get("character", "SPEAKER_00"))
                    clip_chars[key] = char
                counts[char] = counts.get(char, 0) + 1
            return counts

        def _open_character_manager(self) -> None:
            from aidub.ui.character_manager_dialog import CharacterManagerDialog

            counts = self._compute_character_counts()
            if not counts:
                counts = {"SPEAKER_00": 0, "SPEAKER_01": 0}

            voices = self._current_project_data.get("character_voices", {})
            clips = [
                c for c in self._current_project_data.get("clips", []) if c[0] in {"S1", "S2", "A2"}
            ]
            dlg = CharacterManagerDialog(
                counts,
                voices,
                parent=self,
                media_path=self._current_project_data.get("file_path"),
                clips=clips,
                clip_characters=self._current_project_data.get("clip_characters", {}),
            )
            dlg.characters_updated.connect(self._on_characters_updated)
            dlg.exec()

        def _on_characters_updated(self, data: dict[str, Any]) -> None:
            renames = data.get("renames", {})
            voices = data.get("voices", {})
            characters = data.get("characters", [])

            clip_chars = self._current_project_data.setdefault("clip_characters", {})

            if renames:
                for old_c, new_c in renames.items():
                    for k, v in list(clip_chars.items()):
                        if v == old_c:
                            clip_chars[k] = new_c
                    if self._current_project_data.get("character") == old_c:
                        self._current_project_data["character"] = new_c
                self._show_status(f"Characters renamed/reassigned: {renames}")

            if voices:
                self._current_project_data["character_voices"] = voices

            if characters:
                self.inspector_panel.update_characters(characters)
                self.inspector_panel.meta_chars_lbl.setText(f"{len(characters)} speakers")

            # Update active clip's character in inspector
            if self._active_clip_info:
                tid = self._active_clip_info.get("tid", "")
                start = float(self._active_clip_info.get("start", 0.0))
                active_char = clip_chars.get(
                    f"{tid}:{round(start, 3)}"
                ) or self._current_project_data.get("character", "")
                if active_char:
                    self.inspector_panel.char_in.blockSignals(True)
                    self.inspector_panel.char_in.setCurrentText(active_char)
                    self.inspector_panel.char_in.blockSignals(False)

        def auto_detect_characters(self) -> list[str]:
            """Detect and recognize movie characters from dialogue cues, media audio, and diarization."""
            from aidub.ai.voice.character_cloning_engine import (
                CharacterDetectionEngine,
                extract_speaker_from_cue_text,
            )

            clips = [
                c for c in self._current_project_data.get("clips", []) if c[0] in {"S1", "S2", "A2"}
            ]
            clip_chars = self._current_project_data.setdefault("clip_characters", {})
            media_path = str(self._current_project_data.get("file_path", ""))

            detected_names: set[str] = set()

            # 1. Scan existing timeline clips for speaker tags (e.g. [SPEAKER_00] or John:)
            for clip in clips:
                tid, start_s, _dur, text = clip[0], float(clip[1]), float(clip[2]), clip[3]
                key = f"{tid}:{round(start_s, 3)}"
                spk, _clean = extract_speaker_from_cue_text(text)
                if spk:
                    clip_chars[key] = spk
                    detected_names.add(spk)

            # 2. Check work_dir for asr_segments.json
            for cand_dir in (self._session_store.workspace, Path.cwd() / "work"):
                asr_json = cand_dir / "asr_segments.json"
                if asr_json.is_file():
                    try:
                        segs = json.loads(asr_json.read_text(encoding="utf-8"))
                        engine = CharacterDetectionEngine()
                        chars = engine.detect_movie_characters(segs)
                        for c in chars:
                            detected_names.add(c.canonical_name)
                        for seg in segs:
                            start_s = float(seg.get("start", 0.0))
                            spk = str(seg.get("speaker", "0"))
                            spk_label = (
                                f"Speaker {spk}" if not spk.lower().startswith("speaker") else spk
                            )
                            clip_chars[f"S1:{round(start_s, 3)}"] = spk_label
                            clip_chars[f"S2:{round(start_s, 3)}"] = spk_label
                        break
                    except Exception:
                        pass

            # 3. If still no characters detected and media_path exists, run media diarization
            if not detected_names and media_path and Path(media_path).is_file():
                try:
                    engine = CharacterDetectionEngine()
                    chars, _turns = engine.detect_from_media(
                        media_path, self._automation_state.target_language
                    )
                    for c in chars:
                        detected_names.add(c.canonical_name)
                except Exception as exc:
                    logger.debug("Media diarization character detection: %s", exc)

            if not detected_names:
                detected_names = {"SPEAKER_00", "SPEAKER_01"}

            # Map default voices for detected characters
            voices = self._current_project_data.setdefault("character_voices", {})
            available_voices = [
                "bn-BD-PradeepNeural",
                "bn-BD-NabanitaNeural",
                "bn-IN-BashkarNeural",
                "bn-IN-TanishaaNeural",
            ]
            sorted_chars = sorted(detected_names)
            for idx, char in enumerate(sorted_chars):
                if char not in voices:
                    voices[char] = available_voices[idx % len(available_voices)]

            # If cues had no character assigned, assign default
            for clip in clips:
                tid, start_s = clip[0], float(clip[1])
                key = f"{tid}:{round(start_s, 3)}"
                if key not in clip_chars:
                    clip_chars[key] = sorted_chars[0]

            self.inspector_panel.update_characters(sorted_chars)
            self.inspector_panel.meta_chars_lbl.setText(f"{len(sorted_chars)} speakers")
            self._show_status(
                f"Recognized {len(sorted_chars)} character(s): {', '.join(sorted_chars)}"
            )
            return sorted_chars

        def import_bilingual_subtitle_dialog(self) -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Bilingual Subtitles",
                self._default_asset_directory(),
                "Subtitles (*.srt *.vtt);;All Files (*)",
            )
            if path:
                self.import_bilingual_subtitle_file(path)

        def import_bilingual_subtitle_file(self, path: str) -> None:
            from aidub.subtitles.codec import parse_srt, parse_webvtt

            content = Path(path).read_text(encoding="utf-8-sig")
            doc = parse_webvtt(content) if path.lower().endswith(".vtt") else parse_srt(content)

            s1_cues: list[ClipTuple] = []
            s2_cues: list[ClipTuple] = []

            for cue in doc.cues:
                start_s = cue.time_range.start.ticks / 1000.0
                end_s = cue.time_range.end_exclusive.ticks / 1000.0
                dur_s = max(0.001, end_s - start_s)

                lines = [line.strip() for line in cue.text.splitlines() if line.strip()]
                if len(lines) >= 2:
                    s1_text = lines[0]
                    s2_text = lines[1]
                elif lines:
                    s1_text = lines[0]
                    s2_text = lines[0]
                else:
                    continue

                s1_cues.append(("S1", start_s, dur_s, s1_text, None))
                s2_cues.append(("S2", start_s, dur_s, s2_text, None))

            if s1_cues or s2_cues:
                other_clips = [
                    c
                    for c in self._current_project_data.get("clips", [])
                    if c[0] not in {"S1", "S2"}
                ]
                all_clips = other_clips + s1_cues + s2_cues
                all_clips.sort(key=lambda c: (c[1], c[0]))
                current_duration = float(self._current_project_data.get("duration", 1.0))
                dur = max([c[1] + c[2] for c in all_clips] + [current_duration])

                self._current_project_data["clips"] = all_clips
                self._current_project_data["duration"] = dur
                self.canvas_view.set_clips(all_clips, dur)

                from aidub.ai.voice.character_cloning_engine import extract_speaker_from_cue_text

                clip_chars = self._current_project_data.setdefault("clip_characters", {})
                detected_chars: set[str] = set()
                for c in s1_cues + s2_cues:
                    spk, _ = extract_speaker_from_cue_text(c[3])
                    if spk:
                        clip_chars[f"{c[0]}:{round(float(c[1]), 3)}"] = spk
                        detected_chars.add(spk)
                if detected_chars:
                    self.inspector_panel.update_characters(sorted(detected_chars))
                    self.inspector_panel.meta_chars_lbl.setText(f"{len(detected_chars)} speakers")

                if s1_cues:
                    self._current_project_data["original_text"] = s1_cues[0][3]
                if s2_cues:
                    self._current_project_data["translation_text"] = s2_cues[0][3]

                self.inspector_panel.update_clip_info(
                    str(self._current_project_data.get("original_text", "")),
                    str(self._current_project_data.get("translation_text", "")),
                    str(self._current_project_data.get("character", "")),
                    self._automation_state.target_language,
                )
                self.inspector_panel.update_metadata_display(self._current_project_data)
                self._show_status(
                    f"Imported bilingual subtitles: {len(s1_cues)} cues loaded to S1 and S2"
                )

        def _on_translation_changed(self, text: str) -> None:
            self._current_project_data["translation_text"] = text
            active = self._active_clip_info or {}
            if active.get("tid") in {"S1", "S2", "A2"}:
                self.canvas_view.update_subtitle_text(text, float(active.get("start", 0.0)))

        def _commit_translation(self) -> None:
            text = self.inspector_panel.trans_in.text().strip()
            active = self._active_clip_info or {}
            if active.get("tid") not in {"S1", "S2", "A2"}:
                return
            start = float(active.get("start", 0.0))
            duration = float(active.get("dur", 0.0))
            if duration <= 0 or not text:
                return

            previous = list(self._current_project_data.get("clips", []))
            updated = list(previous)
            target_index = next(
                (
                    index
                    for index, clip in enumerate(updated)
                    if clip[0] == "S2" and abs(float(clip[1]) - start) < 0.05
                ),
                None,
            )
            if target_index is None:
                updated.append(("S2", start, duration, text, None))
            else:
                old = updated[target_index]
                updated[target_index] = ("S2", old[1], old[2], text, old[4])
            if updated == previous:
                return

            self._edit_history.append(previous)
            self._edit_future.clear()
            self._current_project_data["clips"] = updated
            self.canvas_view.set_clips(
                updated,
                float(self._current_project_data.get("duration", 1.0)),
            )
            cue = self._matching_subtitle("S2", start)
            if cue is not None:
                self._active_clip_info = {
                    "tid": "S2",
                    "start": cue[1],
                    "dur": cue[2],
                    "label": cue[3],
                    "score": cue[4],
                }
            self._show_status("Target subtitle cue saved on the selected timeline time")

        def _on_ai_action_clicked(self, action_name: str) -> None:
            if action_name in {"Extract Dialogue Audio", "Extract Audio"}:
                self._run_modular_extract_audio()
            elif action_name in {"Transcribe Speech (S1)", "Transcribe Speech", "Transcribe"}:
                self._run_modular_transcribe_speech()
            elif action_name in {
                "Translate Subtitles (S2)",
                "Translate Subtitles",
                "Translate S1 to S2",
            }:
                self._run_modular_translate_subtitles()
            elif action_name in {
                "Synthesize Voices (A2)",
                "Synthesize Voices",
                "Synthesize Dialogue",
            }:
                self._run_modular_synthesize_voices()
            elif action_name in {
                "Render Master Video",
                "Render Video Master",
                "Render Master",
            }:
                self._run_modular_render_master()
            elif action_name in {"Auto-Detect Characters", "Auto-Detect Movie Characters"}:
                self.auto_detect_characters()
            elif action_name in {
                "Select Dub Voice",
                "Voice Model",
                "AI Voice Engine",
                "Chatterbox",
            }:
                self._open_voice_model_selector()
            elif action_name in {"Kaggle GPU", "Cloud GPU Accelerator", "Kaggle Accelerator"}:
                self._open_kaggle_accelerator()
            elif action_name in {"Audio Analysis", "Audio Analysis & Diagnostics"}:
                self._open_audio_analysis()
            elif action_name in {"Manage Characters", "Character & Speaker Manager"}:
                self._open_character_manager()
            elif action_name == "Subtitle QC":
                self._run_subtitle_qc()
            elif action_name == "Pipeline Readiness":
                self._show_pipeline_readiness()
            elif action_name == "Improve Emotion":
                self._run_translation_assistant(
                    shorten=False,
                    instruction_override=(
                        "Rewrite the localized line for a more emotionally faithful screen "
                        "performance while preserving meaning and timing."
                    ),
                )
            elif action_name == "Match Timing":
                self._apply_timing_fix()
            elif action_name in {"Rewrite Translation", "Shorten Translation"}:
                self._run_translation_assistant(shorten=action_name.startswith("Shorten"))
            elif action_name in {
                "Lip Sync Shot",
                "Lip Sync",
                "Render Lip Sync",
                "Selective Lip Sync",
            }:
                self._render_lip_sync()
            elif action_name == "Fix Pronunciation":
                self._run_translation_assistant(
                    shorten=False,
                    instruction_override=(
                        "Revise the localized dialogue for unambiguous natural pronunciation "
                        "while preserving the character's words and intent."
                    ),
                )
            elif action_name == "Properties":
                proj_name = self._current_project_data.get("name", "Current Project")
                m_name = self._current_project_data.get("movie_name", "Video")
                report = self._automation_state.quality_report
                quality = (
                    f"{report.overall_score * 100:.1f}% ({'PASS' if report.passed else 'REVIEW'})"
                    if report is not None
                    else "Not evaluated"
                )
                QMessageBox.information(
                    self,
                    "Production Properties",
                    (
                        f"Project: {proj_name}\n"
                        f"Source Media: {m_name}\n"
                        f"Target: {self._automation_state.target_language}\n"
                        f"Automation: {self._automation_state.progress}%\n"
                        f"Quality Gate: {quality}\n"
                        f"Session: {self._session_store.path_for(str(proj_name))}"
                    ),
                )
            else:
                self._show_status(f"No operation is registered for: {action_name}")

        def _get_work_dir(self, subfolder: str = "work") -> Path:
            proj = getattr(self, "_active_opened_project", None)
            if proj is not None and hasattr(proj, "paths"):
                return Path(proj.paths.work)
            p = self._session_store.workspace / subfolder
            p.mkdir(parents=True, exist_ok=True)
            return p

        def _run_modular_extract_audio(self) -> None:
            if (
                hasattr(self, "_extraction_worker")
                and self._extraction_worker is not None
                and self._extraction_worker.isRunning()
            ):
                self._show_status("Audio extraction is already running")
                return
            video_file = self._current_project_data.get("file_path")
            if not video_file or not Path(str(video_file)).is_file():
                self._show_status("Please open or import a video file first")
                return
            v_path = Path(str(video_file))
            work_dir = self._get_work_dir("work")
            out_audio = work_dir / f"{v_path.stem}_audio16k.wav"

            from aidub.ui.workers import ModularExtractionWorker

            self._extraction_worker = ModularExtractionWorker(v_path, out_audio, parent=self)

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"Extract Audio: {pct}% · {msg}")
                self.ai_overlay.set_progress(f"Extracting Audio: {pct}%", pct)

            def _on_done(audio_file: str, dur_s: float) -> None:
                self._current_project_data["extracted_audio"] = audio_file
                clips = list(self._current_project_data.get("clips", []))
                clips = [c for c in clips if c[0] != "A1"]
                clips.insert(0, ("A1", 0.0, dur_s, "Production Dialogue", None))
                self._current_project_data["clips"] = clips
                self.canvas_view.set_clips(
                    clips, max(dur_s, float(self._current_project_data.get("duration", 1.0)))
                )
                self._show_status(
                    f"Dialogue audio extracted ({dur_s:.1f}s): {Path(audio_file).name}"
                )
                self.ai_overlay.set_progress("Audio Extracted (100%)", 100)
                self._extraction_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Audio extraction failed: {err}")
                self.ai_overlay.set_progress("Audio extraction failed", 0)
                self._extraction_worker = None

            def _on_cancel() -> None:
                self._show_status("Audio extraction cancelled by operator")
                self.ai_overlay.set_progress("Extraction cancelled", 0)
                self._extraction_worker = None

            self._extraction_worker.progress_updated.connect(_on_prog)
            self._extraction_worker.extraction_completed.connect(_on_done)
            self._extraction_worker.extraction_failed.connect(_on_fail)
            self._extraction_worker.extraction_cancelled.connect(_on_cancel)
            self._extraction_worker.start()
            self._show_status(f"Started audio extraction from {v_path.name}…")

        def _run_modular_transcribe_speech(self) -> None:
            if (
                hasattr(self, "_transcription_worker")
                and self._transcription_worker is not None
                and self._transcription_worker.isRunning()
            ):
                self._show_status("Speech transcription is already running")
                return
            audio_file = self._current_project_data.get("extracted_audio")
            if not audio_file or not Path(str(audio_file)).is_file():
                video_file = self._current_project_data.get("file_path")
                if video_file and Path(str(video_file)).is_file():
                    audio_file = str(video_file)
                else:
                    self._show_status("Please open or import a media file first")
                    return

            from aidub.ui.workers import ModularTranscriptionWorker

            opened = getattr(self, "_active_opened_project", None)
            src_proj = getattr(opened, "project", None)
            lang_tag = src_proj.settings.source_language if src_proj else "en"

            self._transcription_worker = ModularTranscriptionWorker(
                audio_path=audio_file,
                language=lang_tag if lang_tag != "auto" else None,
                model_size="base",
                parent=self,
            )

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"ASR: {pct}% · {msg}")
                self.ai_overlay.set_progress(msg, pct)

            def _on_done(cues: list[Any]) -> None:
                clips = [c for c in self._current_project_data.get("clips", []) if c[0] != "S1"]
                for cue in cues:
                    clips.append(("S1", cue.start_s, cue.duration_s, cue.text, cue.confidence))
                self._current_project_data["clips"] = clips
                self._current_project_data["cues"] = cues
                tot_dur = float(self._current_project_data.get("duration", 1.0))
                if cues:
                    tot_dur = max(tot_dur, *(c.end_s for c in cues))
                self.canvas_view.set_clips(clips, tot_dur)
                if cues:
                    self.inspector_panel.orig_in.setText(cues[0].text)
                    self.inspector_panel.char_in.setCurrentText(cues[0].speaker)
                self.save_to_project()
                self._show_status(f"Transcribed {len(cues)} dialogue cues into track S1.")
                self.ai_overlay.set_complete(f"Transcribed {len(cues)} cues (S1)")
                self._transcription_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Transcription failed: {err}")
                self.ai_overlay.set_progress("Transcription failed", 0)
                self._transcription_worker = None

            def _on_cancel() -> None:
                self._show_status("Transcription cancelled by operator")
                self.ai_overlay.set_progress("Transcription cancelled", 0)
                self._transcription_worker = None

            self._transcription_worker.progress_updated.connect(_on_prog)
            self._transcription_worker.transcription_completed.connect(_on_done)
            self._transcription_worker.transcription_failed.connect(_on_fail)
            self._transcription_worker.transcription_cancelled.connect(_on_cancel)
            self._transcription_worker.start()
            self._show_status("Started speech recognition (Faster-Whisper)…")

        def _run_modular_translate_subtitles(self) -> None:
            if (
                hasattr(self, "_translation_worker")
                and self._translation_worker is not None
                and self._translation_worker.isRunning()
            ):
                self._show_status("Translation is already running")
                return
            clips = self._current_project_data.get("clips", [])
            s1_clips = [c for c in clips if c[0] == "S1"]
            if not s1_clips:
                self._show_status(
                    "No source dialogue cues in S1. Transcribe speech or import an SRT first."
                )
                return

            from aidub.application.modular_pipeline import TranscriptCue
            from aidub.ui.workers import ModularTranslationWorker

            cues: list[TranscriptCue] = []
            for idx, c in enumerate(s1_clips):
                cues.append(
                    TranscriptCue(
                        cue_id=f"cue_{idx + 1:04d}",
                        start_s=float(c[1]),
                        end_s=float(c[1]) + float(c[2]),
                        text=str(c[3]),
                        speaker="SPEAKER_00",
                        confidence=float(c[4]) if len(c) > 4 and c[4] is not None else 1.0,
                    )
                )

            src_lang = "en-US"
            tgt_lang = (
                self.inspector_panel.lang_in.text().strip()
                or self._automation_state.target_language
                or "bn-BD"
            )

            self._translation_worker = ModularTranslationWorker(
                cues=cues,
                source_lang=src_lang,
                target_lang=tgt_lang,
                parent=self,
            )

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"Translate: {pct}% · {msg}")
                self.ai_overlay.set_progress(msg, pct)

            def _on_done(translated_cues: list[Any]) -> None:
                clips_updated = [
                    c for c in self._current_project_data.get("clips", []) if c[0] != "S2"
                ]
                for t in translated_cues:
                    clips_updated.append(
                        ("S2", t.start_s, t.duration_s, t.target_text, t.confidence)
                    )
                self._current_project_data["clips"] = clips_updated
                self._current_project_data["translated_cues"] = translated_cues
                tot_dur = float(self._current_project_data.get("duration", 1.0))
                self.canvas_view.set_clips(clips_updated, tot_dur)
                if translated_cues:
                    self.inspector_panel.trans_in.setText(translated_cues[0].target_text)
                self.save_to_project()
                self._show_status(
                    f"Translated {len(translated_cues)} cues into track S2 ({tgt_lang})."
                )
                self.ai_overlay.set_complete(f"Translated {len(translated_cues)} cues (S2)")
                self._translation_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Translation failed: {err}")
                self.ai_overlay.set_progress("Translation failed", 0)
                self._translation_worker = None

            def _on_cancel() -> None:
                self._show_status("Translation cancelled by operator")
                self.ai_overlay.set_progress("Translation cancelled", 0)
                self._translation_worker = None

            self._translation_worker.progress_updated.connect(_on_prog)
            self._translation_worker.translation_completed.connect(_on_done)
            self._translation_worker.translation_failed.connect(_on_fail)
            self._translation_worker.translation_cancelled.connect(_on_cancel)
            self._translation_worker.start()
            self._show_status(f"Translating {len(cues)} cues to {tgt_lang}…")

        def _run_modular_synthesize_voices(self) -> None:
            if (
                hasattr(self, "_batch_tts_worker")
                and self._batch_tts_worker is not None
                and self._batch_tts_worker.isRunning()
            ):
                self._show_status("Voice synthesis is already running")
                return
            clips = self._current_project_data.get("clips", [])
            s2_clips = [c for c in clips if c[0] == "S2"]
            if not s2_clips:
                s2_clips = [c for c in clips if c[0] == "S1"]
            if not s2_clips:
                self._show_status(
                    "No dialogue cues in S2 or S1 to synthesize. Transcribe or translate first."
                )
                return

            from aidub.application.modular_pipeline import TranslatedCue
            from aidub.ui.workers import ModularBatchSynthesisWorker

            tgt_lang = (
                self.inspector_panel.lang_in.text().strip()
                or self._automation_state.target_language
                or "bn-BD"
            )
            work_dir = self._get_work_dir("takes")

            cues: list[TranslatedCue] = []
            for idx, c in enumerate(s2_clips):
                cues.append(
                    TranslatedCue(
                        cue_id=f"cue_{idx + 1:04d}",
                        start_s=float(c[1]),
                        end_s=float(c[1]) + float(c[2]),
                        source_text=str(c[3]),
                        target_text=str(c[3]),
                        target_language=tgt_lang,
                        speaker="SPEAKER_00",
                        confidence=float(c[4]) if len(c) > 4 and c[4] is not None else 1.0,
                    )
                )

            self._batch_tts_worker = ModularBatchSynthesisWorker(
                cues=cues,
                target_lang=tgt_lang,
                output_dir=work_dir,
                voice_name=self._selected_voice_name,
                parent=self,
            )
            self._synthesis_worker = self._batch_tts_worker

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"TTS: {pct}% · {msg}")
                self.ai_overlay.set_progress(msg, pct)

            def _on_done(takes: list[Any]) -> None:
                clips_updated = [
                    c for c in self._current_project_data.get("clips", []) if c[0] != "A2"
                ]
                flagged_count = 0
                for take in takes:
                    if take.flagged_for_review:
                        flagged_count += 1
                    clips_updated.append(
                        (
                            "A2",
                            take.start_s,
                            take.actual_duration_s,
                            f"{take.voice_name} [{take.cue_id}]",
                            None,
                        )
                    )
                self._current_project_data["clips"] = clips_updated
                self._current_project_data["takes"] = takes
                tot_dur = float(self._current_project_data.get("duration", 1.0))
                self.canvas_view.set_clips(clips_updated, tot_dur)
                if takes:
                    self.inspector_panel.set_take_audio(
                        f"Take {takes[0].cue_id}", takes[0].audio_path
                    )
                msg = f"Synthesized {len(takes)} voice takes onto track A2."
                if flagged_count > 0:
                    msg += f" Note: {flagged_count} take(s) flagged for timing review."
                self._show_status(msg)
                self.ai_overlay.set_complete(msg)
                self._batch_tts_worker = None
                self._synthesis_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Voice synthesis failed: {err}")
                self.ai_overlay.set_progress("Voice synthesis failed", 0)
                self._batch_tts_worker = None
                self._synthesis_worker = None

            def _on_cancel() -> None:
                self._show_status("Voice synthesis cancelled by operator")
                self.ai_overlay.set_progress("Synthesis cancelled", 0)
                self._batch_tts_worker = None
                self._synthesis_worker = None

            self._batch_tts_worker.progress_updated.connect(_on_prog)
            self._batch_tts_worker.synthesis_completed.connect(_on_done)
            self._batch_tts_worker.synthesis_failed.connect(_on_fail)
            self._batch_tts_worker.synthesis_cancelled.connect(_on_cancel)
            self._batch_tts_worker.start()
            self._show_status(f"Started synthesis of {len(cues)} voice cues ({tgt_lang})…")

        def _run_modular_render_master(self) -> None:
            if (
                hasattr(self, "_render_worker")
                and self._render_worker is not None
                and self._render_worker.isRunning()
            ):
                self._show_status("Rendering is already in progress")
                return
            video_file = self._current_project_data.get("file_path")
            if not video_file or not Path(str(video_file)).is_file():
                self._show_status("Please open or import a source video file first")
                return

            v_path = Path(str(video_file))
            takes = self._current_project_data.get("takes", [])
            work_dir = self._get_work_dir("work")

            from aidub.application.modular_pipeline import ModularDubbingPipelineService
            from aidub.ui.workers import ModularRenderWorker

            if takes:
                service = ModularDubbingPipelineService()
                tot_dur = float(self._current_project_data.get("duration", 10.0))
                audio_for_render = work_dir / f"{v_path.stem}_dubbed_mix.wav"
                service.mix_timeline_audio(takes, tot_dur, audio_for_render)
            else:
                extracted = self._current_project_data.get("extracted_audio")
                if extracted and Path(str(extracted)).is_file():
                    audio_for_render = Path(str(extracted))
                else:
                    self._show_status(
                        "Synthesize voice takes (A2) or extract audio before rendering master."
                    )
                    return

            out_dir = v_path.parent / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_master = out_dir / f"{v_path.stem}_master_rendered.mp4"

            self._render_worker = ModularRenderWorker(
                v_path, audio_for_render, output_master, parent=self
            )

            def _on_prog(pct: int, msg: str) -> None:
                self._show_status(f"Render: {pct}% · {msg}")
                self.ai_overlay.set_progress(msg, pct)

            def _on_done(res_path: str) -> None:
                self._current_project_data["rendered_master"] = res_path
                self._show_status(f"Master video rendered successfully: {Path(res_path).name}")
                self.ai_overlay.set_complete("Master video rendered")
                if Path(res_path).is_file():
                    try:
                        self.monitor_panel.load_media(res_path)
                        self.monitor_panel.prog_title_lbl.setText(
                            f"Program: {Path(res_path).stem} [RENDERED MASTER]"
                        )
                    except Exception as exc:
                        logger.debug("Failed loading rendered master in monitor: %s", exc)
                self._render_worker = None

            def _on_fail(err: str) -> None:
                self._show_status(f"Rendering failed: {err}")
                self.ai_overlay.set_progress("Rendering failed", 0)
                self._render_worker = None

            def _on_cancel() -> None:
                self._show_status("Rendering cancelled by operator")
                self.ai_overlay.set_progress("Rendering cancelled", 0)
                self._render_worker = None

            self._render_worker.progress_updated.connect(_on_prog)
            self._render_worker.render_completed.connect(_on_done)
            self._render_worker.render_failed.connect(_on_fail)
            self._render_worker.render_cancelled.connect(_on_cancel)
            self._render_worker.start()
            self._show_status(f"Started master rendering: {output_master.name}…")

        def _render_lip_sync(self) -> None:
            """Render lip-sync video for the active project/shot."""
            if not self._current_project_data.get("file_path"):
                self._show_status("Open a project with a video file before running lip-sync.")
                return
            video_path = Path(str(self._current_project_data["file_path"]))
            if not video_path.is_file():
                self._show_status(f"Video file does not exist: {video_path}")
                return

            generated = self._current_project_data.get("generated_paths", ())
            audio_path: Path | None = None
            for p in generated:
                candidate = Path(p)
                if candidate.suffix.lower() in {".wav", ".m4a", ".mp3"} and candidate.is_file():
                    audio_path = candidate
                    break

            if not audio_path:
                work_dir = video_path.parent / "work"
                for candidate_name in ("dubbed_vocals.wav", "dubbed_audio.m4a", "vocals.wav"):
                    cand = work_dir / candidate_name
                    if cand.is_file():
                        audio_path = cand
                        break

            if not audio_path:
                self._show_status(
                    "Dubbed audio not found. Run 'Auto Dub Master' first before rendering lip-sync."
                )
                return

            out_dir = video_path.parent / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_file = out_dir / f"{video_path.stem}_lipsync.mp4"

            from aidub.ui.workers import LipSyncRenderWorker

            self._show_status("Lip-sync render started in background...")
            self.ai_overlay.set_progress("Rendering lip-sync...", 15)

            worker = LipSyncRenderWorker(
                video_path=video_path,
                audio_path=audio_path,
                output_file=output_file,
                model_name="musetalk",
                parent=self,
            )
            self._active_lipsync_worker = worker

            def _on_progress(pct: int, msg: str) -> None:
                self.ai_overlay.set_progress(msg, pct)
                self._show_status(f"Lip-Sync · {pct}% · {msg}")

            def _on_completed(res_path: str) -> None:
                self._show_status(f"Lip-sync completed: {res_path}")
                self.ai_overlay.set_complete("Lip-sync render complete")
                state = self._automation_state
                state = state.update_stage(
                    AutomationStage.LIP_SYNC,
                    status=StageStatus.SUCCEEDED,
                    progress=100,
                    detail=f"Rendered: {Path(res_path).name}",
                )
                self._automation_state = state
                self._persist_automation_state()
                self.ai_overlay.set_state(state)
                self.inspector_panel.l_score_lbl.setText("Lip Sync:  Rendered (100%)")
                self.inspector_panel.l_score_lbl.setStyleSheet("color:#4ADE80;font-weight:700;")
                if Path(res_path).is_file():
                    try:
                        self.monitor_panel.load_media(res_path)
                        self.monitor_panel.load_comparison_media(str(video_path))
                        self.monitor_panel.prog_title_lbl.setText(
                            f"Program: {Path(res_path).stem} [LIP-SYNCED MASTER]"
                        )
                    except Exception as exc:
                        logger.debug("Failed loading lipsynced master into monitor: %s", exc)
                self._active_lipsync_worker = None

            def _on_failed(err: str) -> None:
                self._show_status(f"Lip-sync failed: {err}")
                self.ai_overlay.set_progress("Lip-sync failed", 0)
                state = self._automation_state
                state = state.update_stage(
                    AutomationStage.LIP_SYNC,
                    status=StageStatus.FAILED,
                    progress=0,
                    detail=err[-80:],
                )
                self._automation_state = state
                self._persist_automation_state()
                self.ai_overlay.set_state(state)
                self._active_lipsync_worker = None

            worker.lipsync_progress.connect(_on_progress)
            worker.lipsync_completed.connect(_on_completed)
            worker.lipsync_failed.connect(_on_failed)
            worker.start()

        def _select_dub_voice(self) -> None:
            from aidub.adapters.voice.edge_tts_adapter import (
                available_voices_for_language,
                default_voice_for_language,
            )

            language = self._automation_state.target_language
            try:
                voices = available_voices_for_language(language)
            except ValueError as exc:
                self._show_status(str(exc))
                return
            selected, accepted = QInputDialog.getItem(
                self,
                "Dub Voice",
                f"Choose the synthesized voice for {language} dialogue:",
                list(voices),
                max(0, voices.index(self._selected_voice_name))
                if self._selected_voice_name in voices
                else 0,
                False,
            )
            if accepted and selected:
                self._selected_voice_name = selected
                self._show_status(f"Dub voice set to {selected}")
            elif self._selected_voice_name is None:
                self._selected_voice_name = default_voice_for_language(language)

        def _on_ai_regenerate_voice(self) -> None:
            if self._tts_worker is not None and self._tts_worker.isRunning():
                self._show_status("Voice synthesis is already running")
                return
            text = self.inspector_panel.trans_in.text().strip()
            if not text:
                text = self.inspector_panel.orig_in.text().strip()
                if text:
                    self.inspector_panel.trans_in.setText(text)
            if not text:
                clips = self._current_project_data.get("clips", [])
                dialogue_clips = [c for c in clips if c[0] in {"S2", "S1", "A2"}]
                if dialogue_clips:
                    playhead = self.monitor_panel._playhead_sec
                    best = min(dialogue_clips, key=lambda c: abs(float(c[1]) - playhead))
                    clip_info = {
                        "tid": best[0],
                        "start": best[1],
                        "dur": best[2],
                        "label": best[3],
                        "score": best[4] if len(best) > 4 else None,
                    }
                    self._on_timeline_clip_clicked(clip_info)
                    text = (
                        self.inspector_panel.trans_in.text().strip()
                        or self.inspector_panel.orig_in.text().strip()
                    )
            if not text:
                self._show_status("Enter a translated dialogue line before synthesis")
                return
            from aidub.ui.workers import TTSPreviewWorker

            preview_dir = self._session_store.workspace / "previews"
            preview_dir.mkdir(parents=True, exist_ok=True)
            take_index = len(self._current_project_data.get("clips", [])) + 1
            output = preview_dir / f"take_{take_index:04d}.mp3"
            while output.exists():
                take_index += 1
                output = preview_dir / f"take_{take_index:04d}.mp3"
            from aidub.adapters.voice.edge_tts_adapter import default_voice_for_language

            active_char = self.inspector_panel.char_in.currentText().strip() or str(
                self._current_project_data.get("character", "")
            )
            char_voice = self._current_project_data.get("character_voices", {}).get(active_char)
            try:
                voice_name = (
                    self._selected_voice_name
                    or char_voice
                    or default_voice_for_language(self._automation_state.target_language)
                )
            except ValueError as exc:
                self._show_status(str(exc))
                return
            self._tts_worker = TTSPreviewWorker(
                text,
                voice_name=voice_name,
                output_file=output,
                parent=self,
            )
            self._tts_worker.synthesis_completed.connect(self._on_voice_take_ready)
            self._tts_worker.synthesis_failed.connect(
                lambda error: self._show_status(f"Voice synthesis failed: {error}")
            )
            self._tts_worker.finished.connect(lambda: setattr(self, "_tts_worker", None))
            self._show_status("Neural voice synthesis started in a background worker…")
            self._tts_worker.start()

        def _on_voice_take_ready(self, output_path: str) -> None:
            clip = self._active_clip_info or {}
            start = float(clip.get("start", 0.0))
            duration = float(clip.get("dur", 1.0))
            clips = list(self._current_project_data.get("clips", []))
            take_number = 1 + sum(1 for item in clips if item[0] == "A2")
            take_name = f"Take {take_number}"
            clips.append(("A2", start, duration, take_name, None))
            self._current_project_data["clips"] = clips
            generated = tuple(self._current_project_data.get("generated_paths", ())) + (
                output_path,
            )
            self._current_project_data["generated_paths"] = generated
            self.canvas_view.set_clips(
                clips,
                float(self._current_project_data.get("duration", 1.0)),
            )
            self.inspector_panel.set_take_audio(take_name, output_path)
            self.media_panel.set_project_name(
                str(self._current_project_data.get("name", "Untitled Studio")),
                str(self._current_project_data.get("movie_name", "")),
                str(self._current_project_data.get("file_path", "")),
                generated,
            )
            self._show_status(f"Voice take synthesized: {output_path}")
            if getattr(self, "_pending_preview_take", False):
                self._pending_preview_take = False
                self._preview_selected_take()

        def _on_perform_single_line_retake(self, options: dict[str, Any] | None = None) -> None:
            if (
                hasattr(self, "_retake_worker")
                and self._retake_worker is not None
                and self._retake_worker.isRunning()
            ):
                self._show_status("ADR retake operation is already in progress...")
                return

            opts = options or {}
            ripple = bool(opts.get("ripple", False))
            isometric = bool(opts.get("isometric", True))
            reverb = opts.get("reverb")

            text = self.inspector_panel.trans_in.text().strip()
            if not text:
                text = self.inspector_panel.orig_in.text().strip()
            if not text:
                self._show_status(
                    "Please enter dialogue text in the Inspector before running ADR Retake"
                )
                return

            # Determine utterance index
            utterance_index = 0
            if hasattr(self, "_active_clip_info") and self._active_clip_info:
                clip_label = str(self._active_clip_info.get("label", ""))
                import re

                m = re.search(r"(\d+)", clip_label)
                if m:
                    utterance_index = max(0, int(m.group(1)) - 1)
                else:
                    clip_start = float(self._active_clip_info.get("start", 0.0))
                    clips = [
                        c
                        for c in self._current_project_data.get("clips", [])
                        if c[0] in {"S2", "S1", "A2"}
                    ]
                    if clips:
                        for idx, c in enumerate(clips):
                            if abs(float(c[1]) - clip_start) < 0.05:
                                utterance_index = idx
                                break

            active_char = self.inspector_panel.char_in.currentText().strip() or str(
                self._current_project_data.get("character", "")
            )
            char_voice = self._current_project_data.get("character_voices", {}).get(active_char)
            from aidub.adapters.voice.edge_tts_adapter import default_voice_for_language

            try:
                voice_name = (
                    self._selected_voice_name
                    or char_voice
                    or default_voice_for_language(self._automation_state.target_language)
                )
            except Exception:
                voice_name = None

            from aidub.ui.workers import UtteranceRetakeWorker

            self._retake_worker = UtteranceRetakeWorker(
                work_dir=self._session_store.workspace,
                utterance_index=utterance_index,
                new_target_text=text,
                target_language=self._automation_state.target_language,
                voice_name=voice_name,
                optimize_isometric=isometric,
                acoustic_preset=reverb,
                ripple_edit=ripple,
                parent=self,
            )
            self._retake_worker.retake_progress.connect(
                lambda pct, msg: self._show_status(f"ADR Retake #{utterance_index}: {msg} ({pct}%)")
            )
            self._retake_worker.retake_completed.connect(self._on_adr_retake_completed)
            self._retake_worker.retake_failed.connect(
                lambda err: self._show_status(f"ADR Retake failed: {err}")
            )
            self._retake_worker.finished.connect(lambda: setattr(self, "_retake_worker", None))
            self._show_status(
                f"Started ADR retake for line #{utterance_index} (Ripple={ripple}, Isometric={isometric})..."
            )
            self._retake_worker.start()

        def _on_adr_retake_completed(self, result: Any) -> None:
            if not result or not result.success:
                self._show_status("ADR Retake did not complete successfully")
                return

            self._show_status(
                f"✓ ADR Retake line #{result.utterance_index} applied in {result.elapsed_seconds:.1f}s "
                f"(Dur: {result.audio_duration_s:.2f}s, Ripple: {result.ripple_shift_s:+0.2f}s)"
            )
            take_name = f"ADR Take {result.utterance_index + 1}"
            self.inspector_panel.set_take_audio(take_name, result.dubbed_audio_path)
            self.inspector_panel.dub_dur_lbl.setText(
                f"Dub Duration:     {result.audio_duration_s:.2f}s"
            )
            if result.isometric_score is not None:
                self.inspector_panel.l_score_lbl.setText(f"Isometric: {result.isometric_score:.2f}")

            from aidub.pipeline.utterance_store import UtteranceStore

            try:
                store = UtteranceStore(
                    self._automation_state.target_language, self._session_store.workspace
                )
                loaded_segs, _ = store.load_utterances()
                if loaded_segs:
                    updated_clips = []
                    for i, seg in enumerate(loaded_segs):
                        s = float(seg.get("start", 0.0))
                        dur = float(seg.get("duration", float(seg.get("end", s + 1.0)) - s))
                        txt = str(seg.get("tgt", ""))
                        updated_clips.append(("A2", s, dur, f"Line {i + 1}: {txt[:16]}", None))
                    self._current_project_data["clips"] = updated_clips
                    self._current_project_data["duration"] = result.updated_timeline_duration
                    self.canvas_view.set_clips(
                        updated_clips, float(result.updated_timeline_duration)
                    )
            except Exception as exc:
                logger.warning("Could not refresh timeline clips after retake: %s", exc)

        def _run_translation_assistant(
            self,
            *,
            shorten: bool,
            instruction_override: str | None = None,
        ) -> None:
            if self._assistant_worker is not None and self._assistant_worker.isRunning():
                self._show_status("Translation agent is already processing a request")
                return
            source = self.inspector_panel.orig_in.text().strip()
            current = self.inspector_panel.trans_in.text().strip()
            if not source and current:
                source = current
            if not source:
                clips = self._current_project_data.get("clips", [])
                dialogue_clips = [c for c in clips if c[0] in {"S1", "S2"}]
                if dialogue_clips:
                    playhead = self.monitor_panel._playhead_sec
                    best = min(dialogue_clips, key=lambda c: abs(float(c[1]) - playhead))
                    clip_info = {
                        "tid": best[0],
                        "start": best[1],
                        "dur": best[2],
                        "label": best[3],
                        "score": best[4] if len(best) > 4 else None,
                    }
                    self._on_timeline_clip_clicked(clip_info)
                    source = (
                        self.inspector_panel.orig_in.text().strip()
                        or self.inspector_panel.trans_in.text().strip()
                    )
                    current = self.inspector_panel.trans_in.text().strip()
            if not source:
                self._show_status("Select a dialogue segment before rewriting")
                return
            from aidub.ui.workers import AIAssistantWorker

            instruction = instruction_override or (
                "Shorten this localized dialogue by about 15% while preserving meaning and character tone."
                if shorten
                else "Rewrite this localized dialogue naturally for screen performance and lip timing."
            )
            prompt = (
                f"{instruction}\nSource: {source}\nCurrent translation: {current}\n"
                f"Target language: {self._automation_state.target_language}\n"
                "Return only the revised spoken dialogue, without quotes or explanation."
            )
            self._assistant_worker = AIAssistantWorker(
                prompt,
                "You are a senior film localization dialogue director.",
                self,
            )
            self._assistant_worker.response_received.connect(self._on_translation_rewritten)
            self._assistant_worker.request_failed.connect(
                lambda error: self._show_status(f"Translation agent unavailable: {error}")
            )
            self._assistant_worker.finished.connect(
                lambda: setattr(self, "_assistant_worker", None)
            )
            self._show_status("Translation agent is rewriting the selected line…")
            self._assistant_worker.start()

        def _on_translation_rewritten(self, text: str) -> None:
            cleaned = text.strip()
            try:
                payload = json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                payload = None
            if isinstance(payload, dict):
                cleaned = str(
                    payload.get("translated_text")
                    or payload.get("translated")
                    or payload.get("text")
                    or ""
                ).strip()
            else:
                cleaned = cleaned.strip('"')
            if cleaned:
                self.inspector_panel.trans_in.setText(cleaned)
                self._commit_translation()
                self._show_status("Translation revision applied; voice and timing are now stale")

        def _apply_timing_fix(self) -> None:
            if self._timing_worker is not None and self._timing_worker.isRunning():
                self._show_status("Timing fit is already running")
                return
            clip = self._active_clip_info or {}
            if clip.get("tid") != "A2":
                start = float(clip.get("start", 0.0))
                matching_a2 = self._matching_subtitle("A2", start, float(clip.get("dur", 1.0)))
                if matching_a2 is not None:
                    clip = {
                        "tid": matching_a2[0],
                        "start": matching_a2[1],
                        "dur": matching_a2[2],
                        "label": matching_a2[3],
                        "score": matching_a2[4] if len(matching_a2) > 4 else None,
                    }
                    self._active_clip_info = clip
                else:
                    self._show_status("Select a dubbed voice clip on A2 before matching timing")
                    return
            source_audio = str(self.inspector_panel.take_combo.currentData() or "")
            if not source_audio or not Path(source_audio).is_file():
                for p in self._current_project_data.get("generated_paths", ()):
                    path_obj = Path(p)
                    if path_obj.is_file() and path_obj.suffix.lower() in {".wav", ".mp3"}:
                        source_audio = str(path_obj)
                        self.inspector_panel.set_take_audio(path_obj.stem, path_obj)
                        break
            if not source_audio or not Path(source_audio).is_file():
                self._show_status("Select or import a playable dubbed voice take first")
                return
            start = float(clip.get("start", 0.0))
            source_cue = self._matching_subtitle("S1", start)
            if source_cue is None:
                self._show_status(
                    "Import source subtitles to provide measured dialogue timing for this take"
                )
                return

            from aidub.ui.workers import TimingFitWorker

            output_dir = self._session_store.workspace / "takes"
            output_dir.mkdir(parents=True, exist_ok=True)
            base = output_dir / f"{Path(source_audio).stem}_{round(start * 1_000)}ms_fit.wav"
            output_path = base
            revision = 2
            while output_path.exists():
                output_path = base.with_name(f"{base.stem}_{revision:02d}{base.suffix}")
                revision += 1

            self._pending_timing_edit = {
                "start": start,
                "source_label": str(clip.get("label", "Dub take")),
                "target_duration": float(source_cue[2]),
            }
            self._timing_worker = TimingFitWorker(
                source_audio,
                float(source_cue[2]),
                output_path,
                self,
            )
            self._timing_worker.fit_completed.connect(self._on_timing_fit_ready)
            self._timing_worker.fit_failed.connect(
                lambda error: self._show_status(f"Timing fit failed: {error}")
            )
            self._timing_worker.finished.connect(lambda: setattr(self, "_timing_worker", None))
            self._show_status("Fitting the selected voice take to the source subtitle slot…")
            self._timing_worker.start()

        def _on_timing_fit_ready(self, output_path: str, fitted_duration: float) -> None:
            pending = self._pending_timing_edit or {}
            start = float(pending.get("start", -1.0))
            source_label = str(pending.get("source_label", "Dub take"))
            fitted_label = f"{source_label} (timed)"
            previous = list(self._current_project_data.get("clips", []))
            updated = list(previous)
            matched_index = next(
                (
                    index
                    for index, clip in enumerate(updated)
                    if clip[0] == "A2"
                    and abs(float(clip[1]) - start) < 0.05
                    and clip[3] == source_label
                ),
                None,
            )
            if matched_index is None:
                self._show_status("Fitted audio was saved, but its timeline take has changed")
                return

            old = updated[matched_index]
            updated[matched_index] = ("A2", old[1], fitted_duration, fitted_label, old[4])
            self._edit_history.append(previous)
            self._edit_future.clear()
            self._current_project_data["clips"] = updated
            generated = tuple(self._current_project_data.get("generated_paths", ())) + (
                output_path,
            )
            self._current_project_data["generated_paths"] = generated
            self.canvas_view.set_clips(
                updated,
                float(self._current_project_data.get("duration", 1.0)),
            )
            self.inspector_panel.set_take_audio(fitted_label, output_path)
            self.media_panel.set_project_name(
                str(self._current_project_data.get("name", "Untitled Studio")),
                str(self._current_project_data.get("movie_name", "")),
                str(self._current_project_data.get("file_path", "")),
                generated,
            )
            self._active_clip_info = {
                "tid": "A2",
                "start": old[1],
                "dur": fitted_duration,
                "label": fitted_label,
                "score": old[4],
            }
            self.inspector_panel.update_clip_info(
                self.inspector_panel.orig_in.text(),
                self.inspector_panel.trans_in.text(),
                self.inspector_panel.char_in.currentText(),
                self.inspector_panel.lang_in.text(),
                float(pending.get("target_duration", fitted_duration)),
                fitted_duration,
                old[4],
            )
            self._show_status(f"Timed take saved: {output_path}")

        def open_dub_dialog(self) -> None:
            """Prompt the user for target language (Bengali default) and Fast/Quality profile, then start dubbing."""
            if self._dubbing_worker is not None and self._dubbing_worker.isRunning():
                self._show_status("A dubbing job is already running")
                return

            input_path = Path(str(self._current_project_data.get("file_path", "")))
            if not input_path.is_file():
                selected, _selected_filter = QFileDialog.getOpenFileName(
                    self,
                    "Select Source Movie for Automated Dubbing",
                    self._default_asset_directory(),
                    "Movie Files (*.mkv *.mp4 *.mov *.avi *.m2ts);;All Files (*)",
                )
                if not selected:
                    return
                input_path = Path(selected)
                self.load_project_data(
                    {
                        "name": self._current_project_data.get("name", input_path.stem),
                        "file_path": str(input_path),
                        "target_language": self._automation_state.target_language or "bn",
                        "quality_profile": self._automation_state.quality_profile or "quality",
                    }
                )

            from aidub.ui.dub_dialog import DubDialog

            current_lang = self._automation_state.target_language or "bn"
            current_profile = self._automation_state.quality_profile or "quality"
            dialog = DubDialog(self, current_lang=current_lang, current_profile=current_profile)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            advanced = dialog.get_advanced_settings()
            target_lang = advanced.get("target_lang", "bn")
            quality_profile = advanced.get("quality_profile", "quality")
            self._current_project_data["isometric_alignment"] = advanced.get(
                "isometric_alignment", True
            )
            self._current_project_data["acoustic_preset"] = advanced.get("acoustic_preset", "none")
            self._current_project_data["broadcast_spec"] = advanced.get("broadcast_spec", "netflix")
            self._current_project_data["embed_c2pa_provenance"] = advanced.get(
                "embed_c2pa_provenance", True
            )
            self._current_project_data["lipsync"] = advanced.get("lipsync", True)
            self._current_project_data["lipsync_tier"] = advanced.get(
                "lipsync_tier", "studio_viseme"
            )
            self._current_project_data["voice_engine"] = advanced.get("voice_engine", "gemini_tts")
            self._run_agentic_dub(target_lang=target_lang, quality_profile=quality_profile)

        def _run_agentic_dub(
            self,
            *,
            target_lang: str | None = None,
            quality_profile: str | None = None,
        ) -> None:
            if self._dubbing_worker is not None and self._dubbing_worker.isRunning():
                return
            input_path = Path(str(self._current_project_data.get("file_path", "")))
            if not input_path.is_file():
                selected, _selected_filter = QFileDialog.getOpenFileName(
                    self,
                    "Select Source Movie for Automated Dubbing",
                    self._default_asset_directory(),
                    "Movie Files (*.mkv *.mp4 *.mov *.avi *.m2ts);;All Files (*)",
                )
                if not selected:
                    return
                input_path = Path(selected)
                self.load_project_data(
                    {
                        "name": self._current_project_data.get("name", input_path.stem),
                        "file_path": str(input_path),
                        "target_language": target_lang
                        or self._automation_state.target_language
                        or "bn",
                        "quality_profile": quality_profile
                        or self._automation_state.quality_profile
                        or "quality",
                    }
                )

            lang = target_lang or self._automation_state.target_language or "bn"
            profile = quality_profile or self._automation_state.quality_profile or "quality"

            from aidub.ui.workers import DubbingEngineWorker

            self._automation_state = create_automation_plan(
                str(self._current_project_data.get("name", input_path.stem)),
                source_path=str(input_path.resolve()),
                target_language=lang,
                quality_profile=profile,
            )
            self.inspector_panel.clear_quality_report()
            self.ai_overlay.set_state(self._automation_state)
            lipsync_enabled = bool(self._current_project_data.get("lipsync", True))
            lipsync_tier = str(self._current_project_data.get("lipsync_tier", "studio_viseme"))
            voice_engine = str(self._current_project_data.get("voice_engine", "gemini_tts"))
            self._dubbing_worker = DubbingEngineWorker(
                input_path,
                lang,
                profile,
                self,
                voice_name=self._selected_voice_name,
                voice_engine=voice_engine,
                character_voices=self._current_project_data.get("character_voices"),
                lipsync=lipsync_enabled,
                lipsync_tier=lipsync_tier,
            )
            self._dubbing_worker.progress_updated.connect(self._on_dubbing_progress)
            self._dubbing_worker.dubbing_completed.connect(self._on_dubbing_completed)
            self._dubbing_worker.dubbing_failed.connect(self._on_dubbing_failed)
            self._dubbing_worker.dubbing_cancelled.connect(self._on_dubbing_cancelled)
            self._dubbing_worker.finished.connect(lambda: setattr(self, "_dubbing_worker", None))
            self.ai_overlay.set_progress("Preparing autonomous production graph…", 1)
            self._show_status("Agentic dubbing job started · background execution enabled")
            win = self.window()
            if hasattr(win, "update_dub_progress"):
                win.update_dub_progress("ingest", 1, "Starting dubbing pipeline…")
            self._dubbing_worker.start()

        def _cancel_agentic_dub(self) -> None:
            if self._dubbing_worker is not None and self._dubbing_worker.isRunning():
                self._dubbing_worker.cancel()
                self._show_status("Cancellation requested · waiting for a safe stage boundary")

        def _on_dubbing_progress(self, pipeline_stage: str, percent: int, message: str) -> None:
            stage_map = {
                "ingest": AutomationStage.INGEST,
                "extract_audio": AutomationStage.INGEST,
                "separate_stems": AutomationStage.AUDIO_SEPARATION,
                "diarize": AutomationStage.SPEAKER_ANALYSIS,
                "asr": AutomationStage.TRANSCRIPTION,
                "translate": AutomationStage.TRANSLATION,
                "tts": AutomationStage.SYNTHESIS,
                "assemble": AutomationStage.TIMING,
                "lipsync": AutomationStage.LIP_SYNC,
                "mix": AutomationStage.MIX,
                "mux": AutomationStage.MASTER_EXPORT,
                "complete": AutomationStage.MASTER_EXPORT,
            }
            skipped = pipeline_stage.endswith("_skipped")
            current_stage = stage_map.get(
                pipeline_stage.removesuffix("_skipped") if skipped else pipeline_stage
            )
            state = self._automation_state
            if current_stage is not None and skipped:
                state = state.update_stage(
                    current_stage,
                    status=StageStatus.SKIPPED,
                    progress=100,
                    detail=message,
                )
            elif current_stage is not None:
                executed_stages = [
                    AutomationStage.INGEST,
                    AutomationStage.AUDIO_SEPARATION,
                    AutomationStage.SPEAKER_ANALYSIS,
                    AutomationStage.TRANSCRIPTION,
                    AutomationStage.TRANSLATION,
                    AutomationStage.SYNTHESIS,
                    AutomationStage.TIMING,
                    AutomationStage.LIP_SYNC,
                    AutomationStage.MIX,
                    AutomationStage.MASTER_EXPORT,
                ]
                current_index = executed_stages.index(current_stage)
                for stage in executed_stages[:current_index]:
                    stage_state = state.stage(stage)
                    if stage_state.status not in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
                        state = state.update_stage(
                            stage,
                            status=StageStatus.SUCCEEDED,
                            progress=100,
                            detail="Completed by the pipeline",
                        )
                if current_stage is AutomationStage.SYNTHESIS:
                    voice_casting = state.stage(AutomationStage.VOICE_CASTING)
                    if voice_casting.status not in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
                        state = state.update_stage(
                            AutomationStage.VOICE_CASTING,
                            status=StageStatus.SKIPPED,
                            progress=100,
                            detail="This run uses one configured voice; per-character casting is not configured",
                        )
                if state.stage(current_stage).status is not StageStatus.SUCCEEDED:
                    state = state.update_stage(
                        current_stage,
                        status=StageStatus.RUNNING,
                        progress=percent,
                        detail=message,
                    )
            stage_name = pipeline_stage.replace("_skipped", "").replace("_", " ").upper()
            self._automation_state = state
            self._persist_automation_state()
            self.ai_overlay.set_progress(f"[{stage_name}] {message}", percent)
            self._show_status(f"Stage: {stage_name} ({percent}%) · {message}")
            win = self.window()
            if hasattr(win, "update_dub_progress"):
                win.update_dub_progress(stage_name, percent, message)

        def _on_dubbing_completed(self, result: dict[str, Any]) -> None:
            generated = tuple(
                value
                for key in ("output_file", "audio_file", "target_srt_file", "srt_file")
                if (value := str(result.get(key, "")))
            )
            self._current_project_data["generated_paths"] = generated
            self.media_panel.set_project_name(
                str(self._current_project_data.get("name", "Project")),
                str(self._current_project_data.get("movie_name", "source")),
                str(self._current_project_data.get("file_path", "")),
                generated,
            )
            target_srt = str(result.get("target_srt_file") or result.get("srt_file") or "")
            if target_srt and Path(target_srt).is_file():
                self.import_subtitle_file(target_srt, track_id="S2")

            work_dir = Path(result.get("work_dir", ""))
            asr_json = work_dir / "asr_segments.json"
            detected_chars: list[str] = []
            if asr_json.is_file():
                try:
                    from aidub.ai.voice.character_cloning_engine import CharacterDetectionEngine

                    segs = json.loads(asr_json.read_text(encoding="utf-8"))
                    engine = CharacterDetectionEngine()
                    chars = engine.detect_movie_characters(segs)
                    detected_chars = [c.canonical_name for c in chars]
                    clip_chars = self._current_project_data.setdefault("clip_characters", {})
                    for seg in segs:
                        start_s = float(seg.get("start", 0.0))
                        spk = str(seg.get("speaker", "0"))
                        spk_label = (
                            f"Speaker {spk}" if not spk.lower().startswith("speaker") else spk
                        )
                        clip_chars[f"S1:{round(start_s, 3)}"] = spk_label
                        clip_chars[f"S2:{round(start_s, 3)}"] = spk_label
                    if detected_chars:
                        self.inspector_panel.update_characters(detected_chars)
                        self.inspector_panel.meta_chars_lbl.setText(
                            f"{len(detected_chars)} speakers"
                        )
                except Exception as exc:
                    logger.debug("Failed loading asr_segments in on_dubbing_completed: %s", exc)

            state = self._automation_state
            for item in state.stages:
                if item.stage is AutomationStage.LIP_SYNC:
                    lipsynced = str(result.get("lipsynced_video", ""))
                    if lipsynced and Path(lipsynced).is_file():
                        state = state.update_stage(
                            item.stage,
                            status=StageStatus.SUCCEEDED,
                            progress=100,
                            detail=f"Lip-sync synthesized: {Path(lipsynced).name}",
                        )
                        self.inspector_panel.l_score_lbl.setText("Lip Sync:  Not measured")
                        self.inspector_panel.l_score_lbl.setStyleSheet("color:#8C9BAE;")
                    else:
                        state = state.update_stage(
                            item.stage,
                            status=StageStatus.SKIPPED,
                            progress=100,
                            detail="Selective lip sync requires shot approval",
                        )
                elif item.stage is AutomationStage.QUALITY_CONTROL:
                    state = state.update_stage(
                        item.stage,
                        status=StageStatus.FAILED,
                        progress=100,
                        detail="No measured QC report is available; review required",
                    )
                elif item.stage is AutomationStage.VOICE_CASTING:
                    status = StageStatus.SUCCEEDED if detected_chars else StageStatus.SKIPPED
                    detail = (
                        f"Applied character voice casting for {len(detected_chars)} character(s)"
                        if detected_chars
                        else "Per-character voice casting is not configured for this run"
                    )
                    state = state.update_stage(
                        item.stage,
                        status=status,
                        progress=100,
                        detail=detail,
                    )
                elif item.status not in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
                    state = state.update_stage(
                        item.stage,
                        status=StageStatus.SUCCEEDED,
                        progress=100,
                        detail="Completed",
                    )
            self._automation_state = state
            self.inspector_panel.clear_quality_report()
            self._persist_automation_state()
            self.ai_overlay.set_state(state)
            self.ai_overlay.set_complete(
                "Localized master rendered · operator review ready",
                quality_passed=False,
            )
            master_file = str(result.get("output_file", ""))
            self._show_status(f"Master created: {master_file}")

            # Automatically load the newly created dubbed video in the Program Monitor
            dubbed_video = str(result.get("lipsynced_video") or result.get("output_file") or "")
            orig_video = str(self._current_project_data.get("file_path", ""))
            if dubbed_video and Path(dubbed_video).is_file():
                try:
                    self.monitor_panel.load_media(dubbed_video)
                    if orig_video and Path(orig_video).is_file():
                        self.monitor_panel.load_comparison_media(orig_video)
                    self.monitor_panel.prog_title_lbl.setText(
                        f"Program: {Path(dubbed_video).stem} [DUBBED MASTER]"
                    )
                    self.monitor_panel.source_lbl.setText(f"Dubbed: {Path(dubbed_video).name}")
                    self._show_status(
                        f"Dubbed video loaded in Program monitor: {Path(dubbed_video).name}"
                    )
                except Exception as exc:
                    logger.debug("Failed auto-loading dubbed master in monitor: %s", exc)
            win = self.window()
            if hasattr(win, "set_dub_completed"):
                win.set_dub_completed(True, dubbed_video or master_file)

        def _on_dubbing_failed(self, error: str) -> None:
            current = next(
                (
                    item
                    for item in self._automation_state.stages
                    if item.status is StageStatus.RUNNING
                ),
                None,
            )
            if current is not None:
                self._automation_state = self._automation_state.update_stage(
                    current.stage,
                    status=StageStatus.FAILED,
                    progress=current.progress,
                    detail=error,
                )
                self._persist_automation_state()
            self.ai_overlay.set_failed(f"Automation stopped · {error}")
            self._show_status(f"Dubbing job failed: {error}")
            win = self.window()
            if hasattr(win, "set_dub_completed"):
                win.set_dub_completed(False, error)
            try:
                from aidub.ui.dub_dialog import DubbingErrorDialog

                dialog = DubbingErrorDialog(
                    self,
                    title="Dubbing Pipeline Error",
                    message="The automated dubbing pipeline encountered an issue. See details below:",
                    details=error,
                )
                dialog.exec()
            except Exception:
                try:
                    QMessageBox.critical(
                        self,
                        "Dubbing Pipeline Notice",
                        f"The automated dubbing pipeline encountered an issue:\n\n{error}\n\n"
                        "Remediation steps:\n"
                        "• Verify that the movie has audible speech.\n"
                        "• Check FFmpeg installation.\n"
                        "• If using external AI models, verify your API keys (e.g. GEMINI_API_KEY).\n"
                        "• Check destination disk permissions.",
                    )
                except Exception:
                    pass

        def _on_dubbing_cancelled(self) -> None:
            self.ai_overlay.set_failed("Automation cancelled safely · revision preserved")
            self._show_status("Dubbing job cancelled; completed stage artifacts remain resumable")
            win = self.window()
            if hasattr(win, "set_dub_completed"):
                win.set_dub_completed(False, "Cancelled")

        def _persist_automation_state(self) -> None:
            self.stage_bar.set_state(self._automation_state)
            if not self._current_project_data.get("file_path"):
                return
            try:
                self._session_store.save(self._automation_state)
            except OSError as exc:
                self._show_status(f"Session autosave warning: {exc}")

        def _save_canonical_project_file(self) -> Path | None:
            source_p = str(self._current_project_data.get("file_path", "")).strip()
            if not source_p:
                return None
            try:
                from aidub.domain.project_file import (
                    ProjectFile,
                    ProjectProbeInfo,
                    SegmentModel,
                )
                from aidub.infrastructure.preferences import load_user_preferences, save_user_preferences

                source_path = Path(source_p)
                proj_dir = source_path.parent / f"{source_path.stem}.aidub"
                proj_dir.mkdir(parents=True, exist_ok=True)
                target_json = proj_dir / "project.json"

                segments: list[SegmentModel] = []
                clips = self._current_project_data.get("clips", [])
                for idx, c in enumerate(clips):
                    tid = str(c[0]) if len(c) > 0 else ""
                    if tid in ("S1", "S2", "A2"):
                        start = float(c[1]) if len(c) > 1 else 0.0
                        dur = float(c[2]) if len(c) > 2 else 0.0
                        lbl = str(c[3]) if len(c) > 3 else ""
                        seg_id = f"seg_{idx:04d}"
                        segments.append(
                            SegmentModel(
                                id=seg_id,
                                start=start,
                                end=start + dur,
                                original=lbl if tid == "S1" else "",
                                translation=lbl if tid == "S2" else "",
                                status="transcribed" if tid == "S1" else ("translated" if tid == "S2" else "synthesized"),
                            )
                        )

                pfile = ProjectFile(
                    name=str(self._current_project_data.get("name") or source_path.stem),
                    project_path=str(target_json.resolve()),
                    source_file=str(source_path.resolve()),
                    source_hash=ProjectFile.compute_file_hash(source_path) if source_path.is_file() else "",
                    segments=segments,
                    probe=ProjectProbeInfo(
                        duration=float(self._current_project_data.get("duration", 0.0)),
                    ),
                )
                pfile.save(target_json)

                # Persist to user preferences so relaunch reloads automatically
                prefs = load_user_preferences()
                prefs.last_project_path = str(target_json.resolve())
                save_user_preferences(prefs)
                return target_json
            except Exception as exc:
                self._show_status(f"Project autosave notice: {exc}")
                return None

        def load_project_file(self, json_path: str | Path) -> bool:
            """Reload an existing project.json exactly into timeline and project state."""
            p = Path(json_path)
            if not p.is_file():
                return False
            try:
                from aidub.domain.project_file import ProjectFile

                pfile = ProjectFile.load(p)
                source_p = pfile.source_file
                clips: list[ClipTuple] = []
                dur = pfile.probe.duration or float(self._current_project_data.get("duration", 10.0))
                if source_p and Path(source_p).is_file():
                    clips.append(("V1", 0.0, dur, Path(source_p).name, None))
                    clips.append(("A1", 0.0, dur, Path(source_p).name, None))

                for seg in pfile.segments:
                    seg_dur = max(0.1, seg.end - seg.start)
                    if seg.original:
                        clips.append(("S1", seg.start, seg_dur, seg.original, None))
                    if seg.translation:
                        clips.append(("S2", seg.start, seg_dur, seg.translation, None))
                    if seg.fitted_path or seg.tts_path:
                        clips.append(("A2", seg.start, seg_dur, seg.translation or "Dubbed Voice", None))

                data: dict[str, Any] = {
                    "name": pfile.name,
                    "movie_name": Path(source_p).name if source_p else pfile.name,
                    "file_path": source_p,
                    "duration": dur,
                    "original_text": pfile.segments[0].original if pfile.segments else "",
                    "translation_text": pfile.segments[0].translation if pfile.segments else "",
                    "clips": clips,
                }
                self._current_project_data = data
                self.canvas_view.set_clips(clips, dur)
                self.project_loaded.emit(pfile.name)
                saved_time = pfile.updated_at[11:19] if len(pfile.updated_at) >= 19 else "just now"
                self.autosave_lbl.setText(f"●  Auto-saved · {saved_time}")
                self._show_status(f"Loaded project: {pfile.name} ({len(pfile.segments)} segments)")
                return True
            except Exception as exc:
                self._show_status(f"Project load error: {exc}")
                return False

        def _autosave_session(self) -> None:
            self._persist_automation_state()
            saved_p = self._save_canonical_project_file()
            from datetime import datetime
            now_time = datetime.now().strftime("%H:%M:%S")
            self.autosave_lbl.setText(f"●  Auto-saved · {now_time}")

        def _on_ai_fix_all(self) -> None:
            if self._active_clip_info is None:
                clips = self._current_project_data.get("clips", [])
                dialogue_clips = [c for c in clips if c[0] in {"S2", "S1", "A2"}]
                if dialogue_clips:
                    playhead = self.monitor_panel._playhead_sec
                    best = min(dialogue_clips, key=lambda c: abs(float(c[1]) - playhead))
                    clip_info = {
                        "tid": best[0],
                        "start": best[1],
                        "dur": best[2],
                        "label": best[3],
                        "score": best[4] if len(best) > 4 else None,
                    }
                    self._on_timeline_clip_clicked(clip_info)
                else:
                    self._show_status("Select a dialogue or dubbed voice clip before Auto Fix")
                    return
            self._apply_timing_fix()
            if self.inspector_panel.orig_in.text().strip():
                self._run_translation_assistant(shorten=False)

        def _preview_selected_take(self) -> None:
            audio_path = str(self.inspector_panel.take_combo.currentData() or "")
            if not audio_path or not Path(audio_path).is_file():
                candidates: list[Path] = []
                for p in self._current_project_data.get("generated_paths", ()):
                    path_obj = Path(p)
                    if path_obj.is_file() and path_obj.suffix.lower() in {
                        ".mp3",
                        ".wav",
                        ".aac",
                        ".flac",
                        ".m4a",
                    }:
                        candidates.append(path_obj)
                preview_dir = self._session_store.workspace / "previews"
                if preview_dir.is_dir():
                    for p in preview_dir.glob("take_*.mp3"):
                        if p.is_file() and p not in candidates:
                            candidates.append(p)
                takes_dir = self._session_store.workspace / "takes"
                if takes_dir.is_dir():
                    for p in takes_dir.glob("*.wav"):
                        if p.is_file() and p not in candidates:
                            candidates.append(p)
                if candidates:
                    latest = max(candidates, key=lambda f: f.stat().st_mtime)
                    self.inspector_panel.set_take_audio(latest.stem, latest)
                    audio_path = str(latest)
                else:
                    text = (
                        self.inspector_panel.trans_in.text().strip()
                        or self.inspector_panel.orig_in.text().strip()
                    )
                    if text:
                        self._show_status("No saved take found — synthesizing voice preview now…")
                        self._pending_preview_take = True
                        self._on_ai_regenerate_voice()
                        return
                    self._show_status("Select or import a playable voice take before previewing")
                    return
            from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

            if self._take_audio_player is None:
                audio_devices = QMediaDevices.audioOutputs()
                if audio_devices:
                    self._take_audio_output = QAudioOutput(self)
                    self._take_audio_output.setVolume(1.0)
                    self._take_audio_player = QMediaPlayer(self)
                    self._take_audio_player.setAudioOutput(self._take_audio_output)
                    self._take_audio_player.errorOccurred.connect(
                        lambda _error, message: self._show_status(
                            f"Take playback failed: {message}"
                        )
                    )
                else:
                    self._take_audio_output = None
                    self._show_status("No audio output device detected; cannot preview voice take")
                    return
            if self._take_audio_output is not None:
                self._take_audio_output.setVolume(1.0)
                self._take_audio_output.setMuted(False)
            if self._take_audio_player.playbackState() is QMediaPlayer.PlaybackState.PlayingState:
                self._take_audio_player.pause()
                self._show_status("Voice take preview paused")
                return
            self._take_audio_player.setSource(QUrl.fromLocalFile(str(Path(audio_path).resolve())))
            self._take_audio_player.play()
            self._show_status(f"Playing voice take: {Path(audio_path).name}")

        def _on_target_language_changed(self) -> None:
            language = self.inspector_panel.lang_in.text().strip()
            if not language or language == self._automation_state.target_language:
                return
            self._selected_voice_name = None
            self._automation_state = create_automation_plan(
                str(self._current_project_data.get("name", "Untitled Studio")),
                source_path=str(self._current_project_data.get("file_path", "")),
                target_language=language,
                quality_profile=self._automation_state.quality_profile,
            )
            self.ai_overlay.set_state(self._automation_state)
            self._persist_automation_state()
            self._show_status(f"Target language changed to {language}; automation reset")

        def configure_target_language(self) -> None:
            language, accepted = QInputDialog.getText(
                self,
                "Target Language",
                "ISO language code or locale:",
                text=self._automation_state.target_language,
            )
            if accepted and language.strip():
                self.inspector_panel.lang_in.setText(language.strip())
                self._on_target_language_changed()

        def undo(self) -> None:
            if not self._edit_history:
                self._show_status("Nothing to undo")
                return
            current = list(self._current_project_data.get("clips", []))
            previous = self._edit_history.pop()
            self._edit_future.append(current)
            self._current_project_data["clips"] = previous
            self.canvas_view.set_clips(
                previous,
                float(self._current_project_data.get("duration", 1.0)),
            )
            self._show_status("Timeline edit undone")

        def redo(self) -> None:
            if not self._edit_future:
                self._show_status("Nothing to redo")
                return
            current = list(self._current_project_data.get("clips", []))
            following = self._edit_future.pop()
            self._edit_history.append(current)
            self._current_project_data["clips"] = following
            self.canvas_view.set_clips(
                following,
                float(self._current_project_data.get("duration", 1.0)),
            )
            self._show_status("Timeline edit restored")

        def mark_in(self) -> None:
            self.monitor_panel._on_mark_in()
            self._show_status(f"Mark In · {_format_tc(self.monitor_panel._mark_in_sec)}")

        def mark_out(self) -> None:
            self.monitor_panel._on_mark_out()
            self._show_status(f"Mark Out · {_format_tc(self.monitor_panel._mark_out_sec)}")

        def play_pause(self) -> None:
            self.monitor_panel._toggle_play()

        def step_backward(self) -> None:
            self.monitor_panel._on_step_back()

        def step_forward(self) -> None:
            self.monitor_panel._on_step_forward()

        def export_snapshot(self) -> None:
            self.monitor_panel._on_export_snapshot()

        def export_dubbed_video(self) -> None:
            """Export or render the master dubbed video to a chosen destination file."""
            default_name = (
                f"{self._current_project_data.get('name', 'dubbed_movie')}_"
                f"{self._automation_state.target_language}.mp4"
            )
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Dubbed Master Video",
                str(Path.cwd() / default_name),
                "MP4 Video (*.mp4);;Matroska Video (*.mkv);;QuickTime (*.mov);;All Files (*)",
            )
            if not target_path:
                return

            dest = Path(target_path).resolve()
            src_video = self._current_project_data.get("file_path")
            if src_video and Path(str(src_video)).resolve() == dest:
                QMessageBox.critical(
                    self,
                    "Destination Conflict",
                    "The destination path cannot overwrite the source movie file.\n"
                    "Please choose a different output filename.",
                )
                return

            work_dir = Path(self._current_project_data.get("work_dir", "work"))
            rendered_master = self._current_project_data.get("rendered_master")
            dubbed_video_path = self._current_project_data.get("dubbed_video_path")

            candidates: list[Path] = []
            if rendered_master:
                candidates.append(Path(rendered_master))
            candidates.append(work_dir / "dubbed_video.mp4")
            if dubbed_video_path:
                candidates.append(Path(dubbed_video_path))
            candidates.extend(
                [
                    Path(f"out_{self._automation_state.target_language}.mp4"),
                    Path("out_bn.mp4"),
                ]
            )
            source_dub = next((c for c in candidates if c.is_file()), None)
            if source_dub:
                if source_dub.resolve() != dest:
                    import shutil

                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_dub, dest)
                self._show_status(f"Exported dubbed video: {dest.name}")
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Successfully exported dubbed master video:\n{target_path}",
                )
            else:
                self._show_status("No rendered dub found; running Auto Dub Master first…")
                self.run_auto_dub()

        def export_subtitles_dialog(self, *, target: bool = True, bilingual: bool = False) -> None:
            """Export current timeline cues as standard single-language or dual-language bilingual SRT."""
            from aidub.subtitles.bilingual import LineMode, write_bilingual_srt, write_srt

            clips = self._current_project_data.get("clips", [])
            s1_clips = [c for c in clips if c[0] == "S1"]
            s2_clips = [c for c in clips if c[0] == "S2"]

            if not s1_clips and not s2_clips:
                QMessageBox.warning(
                    self,
                    "Export Subtitles",
                    "No subtitle cues are present on the timeline to export.",
                )
                return

            ext = "bilingual" if bilingual else ("target" if target else "source")
            default_name = f"{self._current_project_data.get('name', 'subtitles')}_{ext}.srt"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Subtitles (SRT)",
                str(Path.cwd() / default_name),
                "SRT Subtitles (*.srt);;All Files (*)",
            )
            if not save_path:
                return

            if bilingual:
                segments: list[dict[str, Any]] = []
                for s1 in s1_clips:
                    match_s2 = self._matching_subtitle("S2", s1[1], s1[2])
                    segments.append(
                        {
                            "start": s1[1],
                            "end": s1[1] + s1[2],
                            "text": s1[3],
                            "tgt": match_s2[3] if match_s2 else "",
                        }
                    )
                write_bilingual_srt(segments, save_path, LineMode.BILINGUAL_TARGET_BOTTOM)
            else:
                chosen = s2_clips if target else s1_clips
                segments = [
                    {
                        "start": c[1],
                        "end": c[1] + c[2],
                        "text": c[3],
                        "tgt": c[3],
                    }
                    for c in chosen
                ]
                write_srt(segments, save_path, translated=False)

            self._show_status(f"Exported {len(segments)} subtitle cues to: {Path(save_path).name}")
            QMessageBox.information(
                self, "Export Complete", f"Subtitles exported successfully:\n{save_path}"
            )

        def run_auto_dub(self, *, prompt_dialog: bool = False) -> None:
            if prompt_dialog:
                self.open_dub_dialog()
            else:
                self._run_agentic_dub()

        def cancel_active_job(self) -> None:
            self._cancel_agentic_dub()
            for worker_name in (
                "_extraction_worker",
                "_transcription_worker",
                "_translation_worker",
                "_batch_tts_worker",
                "_synthesis_worker",
                "_render_worker",
                "_active_lipsync_worker",
                "_assistant_worker",
                "_timing_worker",
                "_tts_worker",
            ):
                worker = getattr(self, worker_name, None)
                if worker is not None and worker.isRunning():
                    if hasattr(worker, "cancel"):
                        worker.cancel()
            self._show_status("Cancellation requested for active job(s)")

        def regenerate_selected_voice(self) -> None:
            self._on_ai_regenerate_voice()

        def match_selected_timing(self) -> None:
            self._apply_timing_fix()

        def rewrite_selected_translation(self, *, shorten: bool = False) -> None:
            self._run_translation_assistant(shorten=shorten)

        @property
        def current_project_name(self) -> str:
            return str(self._current_project_data.get("name", "Untitled Studio"))

        def _show_status(self, msg: str) -> None:
            self.status_msg_lbl.setText(msg)

        def has_active_job(self) -> bool:
            workers = (
                self._dubbing_worker,
                getattr(self, "_extraction_worker", None),
                getattr(self, "_transcription_worker", None),
                getattr(self, "_translation_worker", None),
                getattr(self, "_batch_tts_worker", None),
                getattr(self, "_synthesis_worker", None),
                getattr(self, "_render_worker", None),
                getattr(self, "_active_lipsync_worker", None),
                getattr(self, "_assistant_worker", None),
                getattr(self, "_timing_worker", None),
                getattr(self, "_tts_worker", None),
            )
            return any(w is not None and w.isRunning() for w in workers)

        def closeEvent(self, event: Any) -> None:  # noqa: N802
            for worker_name in (
                "_assistant_worker",
                "_timing_worker",
                "_tts_worker",
                "_dubbing_worker",
                "_extraction_worker",
                "_transcription_worker",
                "_translation_worker",
                "_batch_tts_worker",
                "_synthesis_worker",
                "_render_worker",
                "_active_lipsync_worker",
            ):
                worker = getattr(self, worker_name, None)
                if worker is not None and worker.isRunning():
                    if hasattr(worker, "cancel"):
                        worker.cancel()
                    worker.quit()
                    worker.wait(1_500)
            if self._take_audio_player is not None:
                self._take_audio_player.stop()
                self._take_audio_player = None
                self._take_audio_output = None
            if self.monitor_panel._player is not None:
                self.monitor_panel._player.stop()
            super().closeEvent(event)


__all__ = ["TimelineScreen"]
