# AI Dubbing Studio — Comprehensive Codebase Audit (Phase 0)

**Date:** October 29, 2026  
**Auditor:** Senior Engineering Lead  
**Target Application:** AI Dubbing Studio / Moviedubbing (`aidub-studio` v0.1.0.dev0)  
**Host Platform:** Windows 11 (AMD64, 64-bit), Python 3.13.14  
**Hardware Detected:** NVIDIA GeForce RTX 2050 (4.0 GB VRAM, Driver 566.07)  

---

## 1. UI Elements Inventory & Authenticity Audit

Below is the complete census of every visible UI element across the application window, menus, inspector, timeline, and media bin, assessing whether it represents real functionality, partial logic, fake simulation, or a dead stub.

| Element Name | Source File & Line | Claimed Purpose | Classification | Underlying Mechanism / Root Cause |
| :--- | :--- | :--- | :--- | :--- |
| **GPU Telemetry Label** | `_studio_widgets.py:824` / `studio_window.py:824` | Real-time GPU load % | **FAKE / FROZEN** | Calls `nvidia-smi` once on startup via `_TelemetryWorker(QThread)`. Never runs in a timer loop; startup sample remains frozen forever. |
| **VRAM Telemetry Label** | `_studio_widgets.py:825` / `studio_window.py:825` | Real-time VRAM used/total GB | **FAKE / FROZEN** | Sampled once at startup via `nvidia-smi` command. Never polls periodically; remains static even under load. |
| **Jobs Telemetry Label** | `_studio_widgets.py:826` / `studio_window.py:826` | Active background job count | **PARTIAL** | Polled every 500ms via `self.studio.has_active_job()`. Returns binary 1 or 0 rather than a real job queue manager. |
| **Project Name & Lang Tag**| `_studio_widgets.py:870` / `studio_window.py:870` | Display active project & target language | **REAL** | Bound to project change signals. |
| **Media Bin: "Project Media (1)"** | `_timeline_widgets.py:262` | Imported project media files | **PARTIAL** | Displays imported file name if loaded, but static counter "1". |
| **Media Bin: "Folder (1)"** | `_timeline_widgets.py:263` | User media folders | **FAKE** | Hardcoded category tuple `("Folder", "1", False)`. Clicking does nothing. |
| **Media Bin: "Shared Media (0)"** | `_timeline_widgets.py:264` | Shared team media assets | **FAKE** | Hardcoded category tuple `("Shared Media", "0", False)`. Dead stub. |
| **Media Bin: "Sample Colors (25)"** | `_timeline_widgets.py:265` | Color matte generators (Filmora clone) | **FAKE** | Hardcoded category tuple `("Sample Colors", "25", False)`. No assets exist. |
| **Media Bin: "Sample Video (20)"** | `_timeline_widgets.py:266` | Stock footage clips (Filmora clone) | **FAKE** | Hardcoded category tuple `("Sample Video", "20", False)`. Completely fabricated. |
| **Media Bin: "Sample Green Screen (10)"** | `_timeline_widgets.py:267` | Green screen VFX clips (Filmora clone) | **FAKE** | Hardcoded category tuple `("Sample Green Screen", "10", False)`. Fabricated. |
| **Media Bin: "📁+ New Folder"** | `_timeline_widgets.py:292` | Create folder in media bin | **STUB** | Button instantiated with tooltip, but no click handler connected. |
| **Media Bin: "🗑 Delete Folder"** | `_timeline_widgets.py:301` | Delete folder in media bin | **STUB** | Button instantiated with tooltip, but no click handler connected. |
| **Dub Trigger 1: "🎙 Dub Movie"** | `_studio_widgets.py:800` | Header toolbar dubbing button | **PARTIAL** | Opens `DubMovieDialog`. Competing duplicate trigger. |
| **Dub Trigger 2: "🎙 DUB MOVIE"** | `_timeline_widgets.py:155` | Left action bar dub button | **PARTIAL** | Opens `DubMovieDialog`. Competing duplicate trigger. |
| **Dub Trigger 3: "✦ AUTO DUB MASTER"** | `_timeline_timeline.py:855` | Timeline bottom bar direct dub runner | **PARTIAL** | Directly calls `_run_auto_dub_pipeline()`. Bypasses dialog. |
| **Dub Trigger 4: "Dub Movie…" (Menu)** | `studio_window.py:1604, 1628` | Sequence & Dub menu action (`Ctrl+Enter`) | **PARTIAL** | Duplicate action in two top-level menus (`Sequence` and `Dub`). |
| **Dub Trigger 5: "Auto Dub Master" (Menu)** | `studio_window.py:1615` | Sequence menu auto dub action | **PARTIAL** | Duplicate action invoking headless pipeline. |
| **Menu: Sequence** | `studio_window.py:1601` | Video editor sequence menu | **STUB / BLOAT** | Video editor leftover containing duplicated dub commands. |
| **Menu: Markers ("Mark In / Out")** | `studio_window.py:1650` | NLE timeline In/Out points | **PARTIAL** | Sets `_mark_in` / `_mark_out` floats, but not hooked to audio export trimming. |
| **Menu: Graphics** | `studio_window.py:1664` | Subtitle & frame export | **PARTIAL** | Video editor leftover. Subtitle imports should belong in Dubbing/Subtitles. |
| **Timeline: Waveform Display** | `_timeline_timeline.py:236-255` | Audio waveform peaks on A1-A5 clips | **FAKE** | Computes synthetic mathematical curve: `0.35 + 0.65*sin(b_idx*1.85)**2`. Never reads PCM audio samples! Capped at 300 bars. |
| **Timeline: Video Thumbnails** | `_timeline_timeline.py:257-279` | Video clip thumbnail filmstrip | **FAKE / BROKEN** | Takes a single `_video_thumbnail` pixmap and repeats it identically 15 times. If frame decode fails, paints black blocks. |
| **Timeline: Razor Tool (`Ctrl+B`)** | `_timeline_screen.py:910` | Slices audio/sub clips at playhead | **REAL** | Splits clip tuple into two and pushes to undo stack. |
| **Pipeline Step 1: Extract Audio** | `_timeline_screen.py:2670` | Extract 16kHz reference WAV from video | **REAL** | Spawns `ModularExtractionWorker` using FFmpeg. Fails if FFmpeg not on PATH. |
| **Pipeline Step 2: Transcribe (Whisper)** | `_timeline_screen.py:2720` | Faster-Whisper speech-to-text | **REAL** | Runs `ModularTranscriptionWorker` using `faster-whisper`. Populates S1. |
| **Pipeline Step 3: Translate Subtitles** | `_timeline_screen.py:2760` | Translate text from S1 to S2 | **REAL** | Calls Gemini/OpenRouter adapters or offline lexicon. Populates S2. |
| **Pipeline Step 4: Synthesize Voice** | `_timeline_screen.py:2800` | Generate dubbed voice audio files | **REAL** | Calls `EdgeTTSAdapter` to synthesize audio clips into A2. |
| **Pipeline Step 5: Render Master** | `_timeline_screen.py:2840` | Mux original video with dubbed audio | **REAL** | Uses FFmpeg with sidechain ducking. |
| **Pipeline Error Box: "Automation stopped"**| `_timeline_screen.py:3959` | Reports pipeline failure with retry | **BROKEN** | Shows generic error string. "RETRY AUTOMATION" re-triggers the exact failing call without resolving root causes. |
| **Inspector: Character Field** | `_timeline_widgets.py:1697` | Speaker assignment for active take | **STUB / DISCONNECTED** | ComboBox with hardcoded `["SPEAKER_00", "SPEAKER_01", "Narrator"]`. Does not bind to segments. |
| **Inspector: Original Dialogue** | `_timeline_widgets.py:1729` | Source subtitle line text | **PARTIAL** | Placeholder `"Select or import source dialogue"`. Only populates if an `S1` clip is explicitly clicked; clicking `A1` audio leaves it blank! |
| **Inspector: Translation Dialogue** | `_timeline_widgets.py:1747` | Target translated dialogue text | **PARTIAL** | Placeholder `"Translation appears after processing"`. Blank unless `S2` is selected. |
| **Inspector: Timing Card** | `_timeline_widgets.py:1784` | Source vs Dub duration & difference | **STUB** | Displays `"Source Duration: —"`, `"Dub Duration: —"`, `"Difference: —"`. Never bound to TTS duration comparison. |
| **Inspector: Scores Card (5 Metrics)** | `_timeline_widgets.py:1806-1815` | Voice, Emotion, Timing, Lip Sync, Quality | **FAKE / STUB** | Hardcoded strings `"Not measured"` and `"NOT RUN"`. No underlying evaluation engine connected. |
| **Inspector Button: "🎚️ VariAudio"** | `_timeline_widgets.py:1990` | Pitch & formant intonation (Cubase clone) | **STUB / MOCK** | Opens `CubaseVariAudioDialog` with synthetic sine wave curves. |
| **Inspector Button: "📐 Align"** | `_timeline_widgets.py:2000` | VocAlign Pro time-alignment | **STUB / MOCK** | Opens `CubaseAudioAlignDialog`. Dead prototype. |
| **Inspector Button: "⚡ DOP"** | `_timeline_widgets.py:2010` | Direct Offline Processing rack | **STUB / MOCK** | Opens `CubaseDopDialog`. Dead prototype. |
| **Inspector Button: "🎛️ Monitor"** | `_timeline_widgets.py:2020` | Control Room studio loudness radar | **STUB / MOCK** | Opens `CubaseControlRoomDialog`. Dead prototype. |
| **Inspector Button: "🔀 X-Fade"** | `_timeline_widgets.py:2030` | S-Curve boundary crossfade | **STUB / MOCK** | Opens `CubaseCrossfadeDialog`. Dead prototype. |
| **Inspector Button: "🎙️ Punch-In"** | `_timeline_widgets.py:2046` | ADR Punch-In / Punch-Out recording | **STUB / MOCK** | Opens `AdrPunchInDialog`. Dead prototype. |
| **Inspector Button: "🎭 Prosody"** | `_timeline_widgets.py:2056` | Actor prosody & dynamic envelope transfer | **STUB / MOCK** | Opens `ProsodyTransferDialog`. Dead prototype. |
| **Inspector Button: "🇧🇩 Bangla Studio"** | `_timeline_widgets.py:2066` | Bangla dialect & G2P tools | **STUB / MOCK** | Opens `BanglaDubStudioDialog`. Dead prototype. |
| **Inspector Button: "🧬 Clone"** | `_timeline_widgets.py:2082` | Voice cloning studio | **STUB / MOCK** | Opens `VoiceCloneStudioDialog`. Dead prototype. |
| **Inspector Button: "💬 Subs"** | `_timeline_widgets.py:2092` | Subtitle caption studio | **STUB / MOCK** | Opens `SubtitleCaptionStudioDialog`. Redundant with main workflow. |
| **Inspector Button: "🎛️ DSP Suite"** | `_timeline_widgets.py:2102` | Audio DSP (Beat-Sync, Speed Ramp) | **STUB / MOCK** | Opens `AudioDspToolsDialog`. Dead prototype. |
| **Inspector Button: "⚡ Batch"** | `_timeline_widgets.py:2112` | Batch dub queue processor | **STUB / MOCK** | Opens `BatchDubRunnerDialog`. Dead prototype. |
| **Inspector Button: "🎚️ Mixer"** | `_timeline_widgets.py:2122` | Cubase MixConsole window | **PARTIAL** | Opens external mixer window duplicating embedded timeline mixer. |
| **Inspector Button: "👄 LipSync"** | `_timeline_widgets.py:2132` | Neural lip-sync face synthesis | **STUB / MOCK** | Opens `NeuralLipsyncStudioDialog`. Non-functional without external repo setup. |
| **Inspector Button: "📐 Isochrone"** | `_timeline_widgets.py:2142` | Syllable isochronic adapter | **STUB / MOCK** | Opens `IsochronicDialogueAdapterDialog`. Dead prototype. |
| **Inspector Button: "🔁 Retake Take"** | `_timeline_widgets.py:2165` | ADR single-line retake | **STUB** | Stub handler emitting signal with no persistence. |
| **Inspector Button: "⚡ Ripple Edit"** | `_timeline_widgets.py:2173` | Timeline ripple time-shift | **STUB** | Stub handler. |
| **Inspector Button: "📐 Isometric Fit"** | `_timeline_widgets.py:2181` | Syllable duration compression | **STUB** | Stub handler. |
| **Inspector Button: "🌊 Reverb Match"** | `_timeline_widgets.py:2189` | Room acoustic convolution matching | **STUB** | Stub handler. |
| **Multitrack Audio Mixer** | `src/aidub/ui/mixer.py` | 5-track linear faders, Mute, Solo, VU | **PARTIAL** | UI layout is functional and serializes to JSON, but real-time peak audio playback monitoring is disconnected (`N/A`). |

---

## 2. Inventory of Hardcoded Values, Mock Data & Swallowed Exceptions

### A. Hardcoded Values & Mock Data
1. **Media Bin Filmora Categories (`_timeline_widgets.py:261-268`):**
   ```python
   categories = [
       ("Project Media", "1", True),
       ("Folder", "1", False),
       ("Shared Media", "0", False),
       ("Sample Colors", "25", False),
       ("Sample Video", "20", False),
       ("Sample Green Screen", "10", False),
   ]
   ```
2. **Timeline Waveform Calculation (`_timeline_timeline.py:246-255`):**
   ```python
   env = math.sin(norm * math.pi) ** 0.6
   burst = 0.35 + 0.65 * math.sin(b_idx * 1.85 + start * 7.3) ** 2 + 0.15 * math.cos(b_idx * 3.1)
   half_h = max(2.0, min((ch * 0.44), (ch * 0.42) * env * burst))
   ```
3. **Inspector Waveform Visualizer (`_studio_widgets.py:32-36`):**
   ```python
   self.bars = [0.12 + 0.88 * abs(math.sin(i * 0.22) * math.cos(i * 0.08) * math.sin(i * 0.41 + 0.2)) for i in range(60)]
   ```
4. **Hardcoded Inspector Scores (`_timeline_widgets.py:1806-1815`):**
   Static QLabels: `"Voice: Not measured"`, `"Emotion: Not measured"`, `"Timing: Not measured"`, `"Lip Sync: Not measured"`, `"Quality: NOT RUN"`.
5. **Video Thumbnail Repetition (`_timeline_timeline.py:263-278`):**
   A single thumbnail image is stamped repeatedly 15 times along the clip body regardless of actual video content across time.
6. **Fake Worker Progress (`src/aidub/workers/handlers.py:38-58`):**
   `_cooperative_wait` executes `time.sleep(step_ms / 1000)` in a synthetic while loop to simulate progress units.

### B. Swallowed Exceptions (`except: pass` and `except Exception: pass`)
Over 60 instances of bare or generic exception suppression exist across the codebase. Key offenders:
* `_timeline_screen.py:3974-3987`: Catches pipeline error dialog crashes with nested `except Exception: pass`.
* `_timeline_screen.py:2377`: `except Exception: pass` during subtitle segment loading.
* `studio_window.py:1050`: `except Exception: pass` when applying user theme.
* `dub_dialog.py:357`: Silently swallows audio configuration validation failures.
* `media/ffmpeg_ops.py:46, 90, 232`: Suppresses FFprobe and FFmpeg metadata probe crashes, returning empty defaults instead of surfacing failures.
* `media/broadcast_exporter.py:306`: Swallows stream muxing verification errors.

---

## 3. Real Current Architecture & Installed Dependency Environment

### Architecture Overview
```
┌─────────────────────────────────────────────────────────────┐
│                 Desktop GUI Presentation                    │
│   (PySide6 / Qt: AIDubStudioWindow -> TimelineScreen)       │
│                                                             │
│   ┌────────────────┐ ┌───────────────────┐ ┌─────────────┐  │
│   │   Media Bin    │ │  Timeline Canvas  │ │  Inspector  │  │
│   │ (Filmora clone)│ │(QGraphicsScene/View│ │ (30 tools) │  │
│   └────────────────┘ └───────────────────┘ └─────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Disconnected In-Memory State
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application & Workers                    │
│   - TimelineScreen._current_project_data (Untyped dict)     │
│   - ModularExtractionWorker (QThread -> FFmpeg)             │
│   - ModularTranscriptionWorker (QThread -> Faster-Whisper)  │
│   - ModularTranslationWorker (QThread -> Gemini/OpenRouter) │
│   - ModularVoiceSynthesisWorker (QThread -> Edge-TTS)       │
│   - ModularRenderMasterWorker (QThread -> FFmpeg)           │
│   - DubbingEngine (Pipeline Orchestrator in _engine.py)     │
└──────────────────────────────┬──────────────────────────────┘
                               │ Subprocess & Library Calls
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                Low-Level Execution Engines                  │
│   - FFmpeg 8.0.1 (External binary in ~/.local/bin)          │
│   - Faster-Whisper 1.2.1 (CTranslate2 INT8)                 │
│   - Demucs 4.1.0 (htdemucs via PyTorch CPU)                 │
│   - Edge-TTS 7.3.1 (Microsoft Azure Neural WebSocket)       │
│   - Gemini / OpenRouter API Adapters                        │
└─────────────────────────────────────────────────────────────┘
```

### State Management Disconnect
1. There is no unified, authoritative `project.json` containing segments `{id, start, end, speaker, original, translation, tts_path, fitted_path, status, qc_issues}`.
2. State is fragmented across:
   * `TimelineScreen._current_project_data` (an untyped, volatile Python `dict`).
   * `TimelineCanvas._clips_data` (a list of untyped 5-tuples: `(track_id, start_sec, duration_sec, label, score)`).
   * SQLite database `aidub.db` managed by SQLAlchemy (infrequently synchronized with active UI edits).
   * `SessionStore` (`timeline_state.json`) which only stores track volume/mute/solo and window geometry.

### Installed Dependency Environment (`.venv`)
* **Python**: 3.13.14 (64-bit AMD64)
* **PySide6**: 6.12.0 (GUI Presentation)
* **PyTorch**: 2.14.1 (**CPU-only build**, `torch.cuda.is_available() == False`)
* **Torchaudio**: 2.11.0
* **Faster-Whisper**: 1.2.1
* **CTranslate2**: 4.8.3
* **Demucs**: 4.1.0
* **Edge-TTS**: 7.3.1
* **ImageIO-FFmpeg**: 0.6.0
* **Pydantic**: 2.14.1
* **SoundFile**: 0.14.0
* **Pyloudnorm**: 0.2.0
* **Google-GenerativeAI**: 0.8.6
* **OpenAI**: 1.109.1

---

## 4. Root Cause Analysis of Reported Problems

### A. Audio Not Loading / Extracting Properly
1. **Missing PATH Export in MediaRuntime:** `MediaRuntime` located `ffmpeg.exe` at `C:\Users\24030\.local\bin\ffmpeg.exe`. However, it never exported `C:\Users\24030\.local\bin` to `os.environ["PATH"]`. When external tools or spawned child processes attempted to execute `ffmpeg`, Windows threw `FileNotFoundError: [WinError 2] The system cannot find the file specified`.
2. **Untyped Clip Data Disconnect:** Extraction outputs a single audio file (`vocals_audio16k.wav`), but timeline insertion merely prepends a single tuple `("A1", 0.0, dur_s, "Production Dialogue", None)` into an untyped list.
3. **Absence of Real Waveform PCM Reading:** The timeline canvas never decoded or buffered min/max peak samples from the audio file; it drew hardcoded mathematical sine curves capped at 300 bars.

### B. Stem Separation (Demucs) Failure
1. **Exact Reproduction & Traceback:**
   ```
   FileNotFoundError: [WinError 2] The system cannot find the file specified
     File "aidub/media/stem_separator.py", line 69, in separate_stems
       _run(command) # Spawns [python, -m, demucs, --two-stems, vocals, ...]
   ```
   Demucs uses `ffmpeg` internally to load audio files. Because `ffmpeg` was not on system `PATH`, Demucs crashed immediately on invocation.
2. **Fatal Pipeline Abort vs. Degraded Fallback:** In `_engine.py:238-243`, this crash raised `PipelineError(ErrorKind.DEPENDENCY, "stem_separation_failed")`. Rather than falling back to using the original audio mix with sidechain ducking, the engine halted the entire automation run, displaying the fatal error in the UI.

### C. Slowness & Performance Bottlenecks
Profiled startup using `cProfile` (total cold start: **3.112s**):
1. **Synchronous WMI Query (`platform.win32_ver()`):** Blocks the UI main thread for **0.745s** during telemetry initialization.
2. **Massive Global Stylesheet Application:** `QApplication.setStyleSheet()` applies a multi-thousand-line CSS string synchronously, freezing the thread for **0.665s**.
3. **Eager Instantiation of 30 Unused Dialogs & Tools:** `_timeline_widgets.py` and `_timeline_screen.py` construct dozens of Cubase/Filmora dialogs and layouts on startup, consuming **1.011s**.
4. **QGraphicsScene Repaint Overhead:** `_build_scene()` in `_timeline_timeline.py` clears and re-instantiates thousands of individual `QGraphicsItem` instances (text ticks, line ticks, fake waveform paths) across the entire 2h28m duration, instead of using a lightweight custom `QPainter` widget that draws only the visible viewport.

### D. Disorganized UI & Clutter
* **Competing Dub Buttons:** 5 separate controls trigger dubbing (`🎙 Dub Movie` toolbar, `🎙 DUB MOVIE` sidebar, `✦ AUTO DUB MASTER` bottom bar, `Sequence > Dub Movie`, `Dub > Dub Movie`).
* **Foreign Workstation Clones:** Leftover panels copied from Filmora (Sample Colors, Sample Video, Sample Green Screen) and Cubase (VariAudio 3, VocAlign, Direct Offline Processing, Control Room, Punch-In, Crossfade Editor, DSP Suite) have no connection to AI dubbing and litter the UI.

---

## 5. Diagnostic Tooling Verification (`aidub doctor`)

The `python -m aidub doctor` command has been enhanced in `src/aidub/diagnostics/system.py` to inspect:
1. **Python Version**: CPython 3.13.14 (64-bit AMD64).
2. **FFmpeg / FFprobe on PATH**: Detects binary location and whether it is present in `os.environ["PATH"]`.
3. **CUDA & VRAM Telemetry**: Queries `nvidia-smi` for hardware GPU name, driver version, total and used VRAM, and checks `torch.cuda.is_available()`.
4. **Cached Model Artifacts**: Scans `~/.cache/huggingface/hub` and lists cached Whisper and Demucs weights.
5. **Writable Cache Directory**: Verifies write permissions and disk space in `~/.cache/aidub`.
6. **Actionable Remediation Guidance**: Formats specific, copy-pasteable commands for any failing or warning component.

---

## 6. Proposed Architecture Plan (Phases 1–9)

* **Phase 1 (Foundation):** Establish strict `project.json` schema (source file path + hash, probe info, list of segments `{id, start, end, speaker, original, translation, tts_path, fitted_path, status, qc_issues}`). Implement central `JobManager` with real queue states (queued, running, done, failed, cancelled) and background polling of real `pynvml` / `nvidia-smi` stats.
* **Phase 2 (Media Import & Playback):** Purge all Filmora sample folders. Decode audio to cached 48kHz stereo WAV (mixing) and 16kHz mono WAV (ASR). Build real multi-resolution `.peaks` waveform cache spanning 100% of the clip. Draw real video thumbnails. Custom `QPainter` timeline rendering only the visible viewport.
* **Phase 3 (Dialogue Extraction & Demucs):** Run Demucs as an isolated subprocess with `--segment` chunking to fit 4 GB VRAM. Automatically ensure FFmpeg is on PATH. Add graceful fallback to ducked original mix when separation is unavailable.
* **Phase 4 (Transcription):** Faster-Whisper ASR with word timestamps; populate real segment table and `S1` track; export source `.srt`.
* **Phase 5 (Translation):** Segment-by-segment English to Bangla translation with local/online engines. Populate `S2` track and real Subtitle QC checks (CPS, line length, overlaps).
* **Phase 6 (Voice Synthesis & Match Timing):** Edge-TTS Bangla synthesis. Implement real "Match Timing" via `atempo` time-stretching (0.85–1.25x). Populate Inspector Timing Card with measured durations.
* **Phase 7 (Mix & Export):** Multitrack assembly with sidechain ducking (-12 dB) and EBU R128 normalization (-16 LUFS). Stream-copy MP4 export with new audio track.
* **Phase 8 (UI Cleanup):** Streamline to 4 standard workflow tabs: **Ingest → Dubbing → Review → Delivery**. Single primary "Dub Movie" trigger. Strip all 30 dead Cubase buttons behind an experimental toggle.
* **Phase 9 (Acceptance & Validation):** Automated end-to-end test suite and verified Windows deployment package.
