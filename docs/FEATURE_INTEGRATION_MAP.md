# MovieDubbing AI Studio — Feature Integration Map

**Document Version:** 2.0.0-RC1  
**Target Repository:** [Moviedubbing (zenbijoy/Moviedubbing)](file:///c:/Users/24030/moviedubbing/Moviedubbing)  
**Verification Baseline:** 972 Automated Tests Passing (100% Pass Rate)

---

## 1. Architectural Integration Paradigm

MovieDubbing adheres strictly to a unidirectional, decoupled data and execution flow:
```
UI Trigger / Event
       ↓
Application Service / Controller
       ↓
Domain Models & Contracts (Typed Pydantic / Dataclasses)
       ↓
Persistence Layer (SQLite project.db & .aidub Package)
       ↓
Background Worker / QThread (Isolated Heavy Inference)
       ↓
Downstream Processing Stages & Artifact Delivery
       ↓
Signal Emission & Real-Time UI Synchronization
```

All heavy model inference (Whisper, Demucs, TTS synthesis, FFmpeg muxing) is isolated outside the Qt UI thread. Cancellation, progress reporting, and error handling are propagated via explicit Qt signals.

---

## 2. End-to-End Workflow Execution Matrix

### Workflow 1: New Project Creation & Package Initialization
* **UI Trigger:** `StudioWindow.action_new_project` (`Ctrl+N`) or `NewProjectDialog.accept()`.
* **Application Service:** [`ProjectPackageService.create()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/application/projects.py#L45).
* **Domain Models:** [`ProjectSettings`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/domain/project.py#L20), [`SourceAuthorization`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/domain/rights.py#L12), [`RationalRate`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/domain/time.py#L15).
* **Persistence:** Creates directory bundle `<name>.aidub/` containing `manifest.json`, `project.db`, `source-links/`, `transcripts/`, `localizations/`, and `recovery/`. Registers entry in [`ProjectCatalog`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/infrastructure/catalog/catalog.py).
* **Worker:** Main UI thread handles atomic directory creation; background catalog sync.
* **Downstream Stages:** Emits `project_created` → [`TimelineScreen.load_opened_project()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/screens/timeline_editor.py#L4624) initializes UI chrome, track definitions, and session store.
* **Test Verification:** [`tests/integration/ui/test_phase6_release_candidate.py::test_rc_project_lifecycle_persistence_and_recovery`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/integration/ui/test_phase6_release_candidate.py#L97).

---

### Workflow 2: Media Import & Preflight Verification
* **UI Trigger:** File menu `Import Media` (`Ctrl+I`), Media Browser drag-and-drop, or Program Monitor import button.
* **Application Service:** [`TimelineScreen.load_project_data()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/screens/timeline_editor.py#L4455), [`probe()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/ffmpeg_ops.py).
* **Domain Models:** Video format metadata dict, time rational scale, duration in seconds.
* **Persistence:** Creates symbolic or hard link in `.aidub/source-links/` or updates `timeline_state.json`.
* **Worker:** Non-blocking `VideoFrameWorker` decodes first visual frame into thumbnail pixmap.
* **Downstream Stages:** Updates Program Monitor, populates `V1` and `A1` base clips on timeline canvas, and enables modular AI actions dock.
* **Test Verification:** [`tests/integration/ui/test_desktop_smoke.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/integration/ui/test_desktop_smoke.py), [`tests/unit/media/test_broadcast_exporter.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/media/test_broadcast_exporter.py).

---

### Workflow 3: Dialogue Extraction & Stem Separation
* **UI Trigger:** AI Dock `Extract Dialogue Audio` button or `TimelineScreen._run_modular_extract_audio()`.
* **Application Service:** [`StemSeparator.separate()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/stem_separator.py#L35), [`RoformerSeparationAdapter`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/separation_roformer.py).
* **Domain Models:** Track stems paths (`vocals.wav`, `accompaniment.wav`, `audio16k.wav`).
* **Persistence:** Audio files written to `.aidub/work/` or session workspace.
* **Worker:** [`ModularExtractionWorker`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/workers.py) runs FFmpeg audio extraction or BS-RoFormer inference in background QThread.
* **Downstream Stages:** Emits `extraction_completed(path, dur)` → adds `A1` audio clip to timeline canvas, links to audio player, and enables Transcription action.
* **Test Verification:** [`tests/unit/adapters/test_roformer_separation.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/adapters/test_roformer_separation.py), [`tests/integration/ui/test_phase6_release_candidate.py::test_rc_modular_pipeline_vertical_slice_and_cancellation`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/integration/ui/test_phase6_release_candidate.py#L232).

---

### Workflow 4: Speech Transcription (ASR) & Word Timestamps
* **UI Trigger:** AI Dock `Transcribe Speech (S1)` button or `TimelineScreen._run_modular_transcribe_speech()`.
* **Application Service:** [`WhisperAsrAdapter.transcribe()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/asr_whisper.py#L50).
* **Domain Models:** [`TranscriptCue`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/application/modular_pipeline.py#L59) with `cue_id`, `start_s`, `end_s`, `text`, `speaker`, `confidence`.
* **Persistence:** Serializes cues to `.aidub/transcripts/subtitles_S1.srt` and updates `project.db`.
* **Worker:** [`ModularTranscriptionWorker`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/workers.py) executes Faster-Whisper ASR with word alignment.
* **Downstream Stages:** Emits `transcription_completed(cues)` → populates `S1` subtitle track, dialogue card list in Dialogue Inspector, and synchronizes Program Monitor playhead.
* **Test Verification:** [`tests/unit/pipeline/test_modular_pipeline.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/pipeline/test_modular_pipeline.py), [`tests/integration/ui/test_phase6_release_candidate.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/integration/ui/test_phase6_release_candidate.py).

---

### Workflow 5: Multi-Speaker Diarization & Character Voice Casting
* **UI Trigger:** `Character Manager` button in Dialogue Inspector or `StudioWindow.action_character_casting` (`Ctrl+M`).
* **Application Service:** [`CharacterDetectionEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ai/voice/character_cloning_engine.py), [`CharacterManagerDialog`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/character_manager_dialog.py).
* **Domain Models:** Speaker turns, character profiles (`name`, `voice_id`, `gender`, `pitch`, `rate`, `reference_audio_path`).
* **Persistence:** Stored in `project_data["character_voices"]` and `project_data["clip_characters"]`.
* **Worker:** Background acoustic embedding extraction or cue-tag regex analysis.
* **Downstream Stages:** Updates character dropdowns across inspector, re-labels timeline cues, and routes specific dialogue takes to distinct TTS speaker models.
* **Test Verification:** [`tests/unit/ui/test_chatterbox_kaggle_ui.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/ui/test_chatterbox_kaggle_ui.py), [`tests/unit/adapters/test_chatterbox_adapter.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/adapters/test_chatterbox_adapter.py).

---

### Workflow 6: Contextual Translation & Isometric Duration Fitting
* **UI Trigger:** AI Dock `Translate Subtitles (S2)` button or `TimelineScreen._run_modular_translate_subtitles()`.
* **Application Service:** [`IsometricTranslationEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/translation/isometric_engine.py), [`LlmProviderRouter`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/providers/router.py).
* **Domain Models:** [`TranslatedCue`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/application/modular_pipeline.py#L82) with `duration_budget_ms`, `source_text`, `target_text`, `target_language`.
* **Persistence:** Written to `.aidub/transcripts/subtitles_S2.srt` and localized directories.
* **Worker:** [`ModularTranslationWorker`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/workers.py) prompts LLM provider router with character context and syllable budget.
* **Downstream Stages:** Emits `translation_completed(translated_cues)` → populates `S2` subtitle track, updates translation input fields in Inspector, and enables voice synthesis.
* **Test Verification:** [`tests/unit/test_isometric_engine.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/test_isometric_engine.py).

---

### Workflow 7: Voice Synthesis & Emotion Conditioning
* **UI Trigger:** AI Dock `Synthesize Voices (A2)` or `VoiceModelDialog.accept()`.
* **Application Service:** [`ModularDubbingService.batch_synthesize_voices()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/application/modular_pipeline.py#L318), [`ChatterboxTTSAdapter`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/chatterbox_adapter.py), [`GeminiTTSAdapter`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/gemini_tts_adapter.py).
* **Domain Models:** [`SynthesizedCueTake`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/application/modular_pipeline.py#L101) (`audio_path`, `voice_name`, `target_duration_s`, `actual_duration_s`, `delta_s`, `delta_pct`).
* **Persistence:** Individual audio takes stored in `.aidub/work/takes/take_cXXXX.wav`.
* **Worker:** [`ModularBatchSynthesisWorker`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/workers.py) handles parallel synthesis with retry and bounded time stretching.
* **Downstream Stages:** Emits `synthesis_completed(takes)` → places takes on `A2` Dub track with waveform visualization; flags takes with duration mismatch (`delta_pct > 15%`) for review.
* **Test Verification:** [`tests/unit/ui/test_modular_pipeline_workers.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/ui/test_modular_pipeline_workers.py), [`tests/unit/adapters/test_voice_engine.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/adapters/test_voice_engine.py).

---

### Workflow 8: Timeline Editing, Razor Split, and Subtitle Sync
* **UI Trigger:** `S` key or `Ctrl+B` (Split at Playhead), `Delete` key (Delete clip), mouse drag (Slip/Move), `Ctrl+Z` (Undo), `Ctrl+Y` (Redo).
* **Application Service:** [`_TimelineCanvasView._split_clip()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/screens/timeline_editor.py#L3310), [`TimelineScreen.undo()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/screens/timeline_editor.py#L7183).
* **Domain Models:** `ClipTuple` (`track_id`, `start_sec`, `duration_sec`, `label`, `score_or_take_id`).
* **Persistence:** `_edit_history` stack; automatically saved to `timeline_state.json`.
* **Worker:** Synchronous UI thread canvas item re-tessellation via `QGraphicsScene`.
* **Downstream Stages:** Emits `clips_edited` → updates `_current_project_data["clips"]`, refreshes inspector cards, and repositions playhead marker.
* **Test Verification:** [`tests/integration/ui/test_phase6_release_candidate.py::test_rc_project_lifecycle_persistence_and_recovery`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/integration/ui/test_phase6_release_candidate.py#L97).

---

### Workflow 9: Multitrack Audio Mixing, Ducking & LUFS Mastering
* **UI Trigger:** Track mixer sliders (`A1`-`A5`, `master`), mute/solo toggles, sidechain ducking checkbox.
* **Application Service:** [`dynamic_sidechain_ducking()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/ffmpeg_ops.py), [`SurroundMixer`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/surround_mixer.py), [`BroadcastQcEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/analysis/broadcast_qc.py).
* **Domain Models:** Mixer levels dict (`{"A1": 0.85, "master": 0.95}`), ducking depth in dB.
* **Persistence:** Saved under `timeline_state.json["mixer"]`.
* **Worker:** Audio preview via `QAudioOutput`; export-time mixing via FFmpeg amix and compand filters.
* **Downstream Stages:** Updates peak warning badges (`PEAK: -1.2 dBFS [PASS]` or red `[CLIP]`), drives Program Monitor volume, and feeds Broadcast Master Exporter.
* **Test Verification:** [`tests/unit/media/test_dynamic_sidechain_ducking.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/media/test_dynamic_sidechain_ducking.py), [`tests/unit/media/test_surround_mixer.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/media/test_surround_mixer.py).

---

### Workflow 10: Selective Lip-Sync & Viseme Inspection
* **UI Trigger:** `Selective Lip Sync` button in Inspector, `LipSyncInspectorDialog`, or `_render_lip_sync()`.
* **Application Service:** [`SelectiveLipSyncEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/selective_lipsync.py), [`VisemeLipSyncEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/viseme_lipsync.py).
* **Domain Models:** Shot intervals, viseme facial landmarks, slip offset (ms).
* **Persistence:** Rendered shot video cached in `.aidub/work/lipsync/`.
* **Worker:** [`LipSyncRenderWorker`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/workers.py) runs facial detection and viseme deformation.
* **Downstream Stages:** Ingests rendered video into Program Monitor, provides split-view A/B visual comparison against original video, and updates lip-sync score badge.
* **Test Verification:** [`tests/unit/ui/test_lipsync_inspector.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/ui/test_lipsync_inspector.py).

---

### Workflow 11: Broadcast Delivery Export (C2PA Provenance & Surround)
* **UI Trigger:** File menu `Broadcast Master Delivery` (`Ctrl+Shift+B`) or `BroadcastExportDialog.accept()`.
* **Application Service:** [`BroadcastMasterExporter.export_master()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/broadcast_exporter.py#L110), [`C2paManifestSigner`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/security/c2pa_manifest.py).
* **Domain Models:** [`BroadcastPreset`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/broadcast_exporter.py#L30) (`NETFLIX_STANDARD`, `EBU_R128`, `THEATRICAL_51`), channel layout (`STEREO`, `SURROUND_51`, `SURROUND_71`).
* **Persistence:** Writes finalized MP4/MKV/MOV, sidecar bilingual SRT, and embedded C2PA provenance manifest. Destination overwrite protection prevents corrupting source movie.
* **Worker:** Dedicated export thread with cancellation and progress reporting.
* **Downstream Stages:** Generates compliance report, presents export completion notification, and opens destination folder.
* **Test Verification:** [`tests/unit/media/test_broadcast_exporter.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/unit/media/test_broadcast_exporter.py), [`tests/integration/ui/test_phase6_release_candidate.py::test_rc_broadcast_export_validation_and_overwrite_protection`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/integration/ui/test_phase6_release_candidate.py#L420).

---

### Workflow 12: Project Save, Backup Recovery & Crash Resilience
* **UI Trigger:** File menu `Save Project` (`Ctrl+S`), autosave timer (every 15s), or application shutdown `closeEvent()`.
* **Application Service:** [`TimelineScreen.save_to_project()`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/screens/timeline_editor.py#L4805), [`StudioSessionStore`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/ui/models.py).
* **Domain Models:** Timeline clip tree, mixer levels, markers, active automation plan.
* **Persistence:** Writes `timeline_state.json.tmp` → atomic rename to `timeline_state.json`; maintains latest backup at `timeline_state.json.bak`.
* **Worker:** Transparent recovery: if `timeline_state.json` contains corrupted bytes, loader automatically falls back to `timeline_state.json.bak` and logs warning.
* **Downstream Stages:** Restores exact timeline state, track levels, solo/mutes, and dialogue cards upon project reopen.
* **Test Verification:** [`tests/integration/ui/test_phase6_release_candidate.py::test_rc_project_lifecycle_persistence_and_recovery`](file:///c:/Users/24030/moviedubbing/Moviedubbing/tests/integration/ui/test_phase6_release_candidate.py#L97).
