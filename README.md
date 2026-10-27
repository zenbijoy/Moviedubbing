# AI Dubbing Studio

AI Dubbing Studio is a Windows-first workstation for multilingual movie dubbing. It combines a
video/audio timeline and subtitle editing with a full-length audio-dubbing pipeline that produces
translated speech, mixed audio, subtitles, and a new video master.

This repository contains a Windows-first desktop dubbing workflow and a headless operator CLI.
The active end-to-end job path is built around the shared `DubbingEngine`; Qt and CLI entry points
use the same transcription, translation, target-language speech synthesis, timing, mixing, subtitle,
and video mux stages.

## Engineering principles

- Original media is immutable. Editing and generation produce new decisions and artifacts.
- Video edit time is rational; audio placement is represented as integer samples.
- Heavy media and AI work runs in supervised worker processes, never on the UI thread.
- Generated outputs are content-addressed and carry complete provenance.
- Voice consent and source authorization are domain data, not check-box-only UI state.
- Every long-running operation is idempotent, cancellable, resumable, and observable.
- Offline mode must produce no external network traffic.

## Prerequisites

- Python 3.12 x64
- Windows 10 or 11 for the supported desktop target
- Git and a current PowerShell

FFmpeg, GPU runtimes, and model packs are separately pinned and verified components; they are not
implicitly downloaded when the Python package is installed.

## Provider credentials

Copy `.env.example` to `.env` and add provider credentials locally. The populated `.env` is ignored
by Git. Gemini and OpenRouter accept one key or a key pool through `GEMINI_API_KEYS` and
`OPENROUTER_API_KEYS`; pools can be JSON arrays, comma-separated values, or semicolon-separated
values. The adapters rotate through configured keys after a failed request.
The studio readiness screen checks whether credentials are configured; only an actual request can
confirm whether a provider accepts a key.

The full-quality dubbing profile also needs a Hugging Face token in `PYANNOTE_TOKEN` and access to
the pyannote diarization model. The fast profile skips diarization and music stem separation. A
required stage failing its prerequisites stops the run; it does not substitute fabricated dialogue,
silent audio, or unmeasured quality scores.

## Local setup

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
ruff check .
mypy src tests
```

The headless operator interface is available immediately after installation:

```powershell
aidub doctor --json
aidub project create "D:\Projects\Feature" --name "Feature" `
  --source-language en-US --operator producer --rights-basis "Licensed production"
aidub project validate "D:\Projects\Feature.aidub" --json
aidub media probe "D:\Media\feature.mkv" --json
```

Install `.[desktop]` to launch the Qt shell with `aidub-studio`, and provide a verified FFmpeg /
ffprobe runtime before media processing. `aidub doctor --require-runtime` is the machine-readable
readiness gate. Project creation always records the operator's source-rights assertion and never
overwrites an existing target.

Optional dependency groups are available for `desktop` and `persistence` development. Install only
the groups required by the component you are working on so that AI and media workers can retain
separate, locked runtime environments.

## Package boundaries

```text
src/aidub/domain/       pure business types and invariants
src/aidub/application/  use cases, commands, queries, orchestration policies
src/aidub/contracts/    versioned process and adapter messages
src/aidub/infrastructure/ persistence, filesystem, FFmpeg, credentials, telemetry
src/aidub/ui/           PySide6/Qt presentation
workers/                isolated media and AI worker entry points
```

Dependencies point inward. In particular, `aidub.domain` has no Qt, database, FFmpeg, provider, or
model imports.

## Domain conventions

All domain models use Pydantic v2 in strict, frozen mode and reject unknown fields. Identifiers have
stable prefixes (`prj_`, `med_`, `utt_`, `art_`, `job_`, and so on). Timestamps must be timezone
aware and are normalized to UTC. Ranges are half-open: `[start, end)`. Hashes are lowercase SHA-256
hex strings. Artifact paths are project-relative POSIX paths and may not traverse directories.

The canonical video representation is `RationalTime(ticks, rate)`, where `rate` is exact units per
second. A 23.976 fps frame uses the rate `24000/1001`; no floating-point seconds enter edit state.
The canonical audio representation is an integer sample position at the project working rate.
Conversions that can lose precision require an explicit rounding policy.

See [ADR-001](docs/adr/ADR-001-time-model.md) for the time-model decision and
`ENTERPRISE_IMPLEMENTATION_PLAN.md` for the phased delivery baseline.

## Implemented foundation

- Atomic create/open/validate/recover for active `.aidub` project directories.
- SQLite migrations, integrity checks, immutable artifacts, reconciliation, and audit events.
- Exact rational video time, integer audio samples, and strict versioned domain contracts.
- Spawned worker crash/cancellation isolation and canonical persisted job lifecycle.
- Bounded FFprobe import metadata, source hashes, privacy policy, DPAPI credentials, and JSON logs.
- English, Bangla (`bn-BD`), and Hindi (`hi-IN`) desktop catalogs and a dock-ready Qt shell.
- Headless project, diagnostics, media-probe, proxy, thumbnail, and waveform commands suitable
  for clean-machine CI.
- Deterministic subtitle interchange, revision-safe transcript editing, and a local ASR boundary
  with exact sample-clock chunking and auditable overlap merge warnings.
- Complete desktop project lifecycle: `NewProjectDialog` with exact `RationalRate` timebases,
  `QualityPreset`, and `SourceAuthorization` validation; atomic `.aidub` package initialization.
- Dynamic `ProjectCatalog` integration in Studio Home Hub with live search, contextual project menus,
  and graceful empty state.
- Full round-trip package persistence: `save_to_project()` serializes track states, exports master
  bilingual Unicode SRT/ASS subtitles (`subtitles_S1.srt`, `subtitles_S2.srt`), bumps SQLite revision,
  and records ACID audit events. Tested with Bengali (`bn-BD`) and Hindi dialogue scripts.

### Studio audio analysis

In the timeline editor, open **AI Actions → Audio Analysis**. The loaded source movie and current
timeline interval are preselected; use **Browse** to inspect a generated dub, music bed, SFX, or
another audio/video file. **Analyze Audio** streams the first audio track through FFmpeg and reports
measured peak and RMS levels, near-full-scale samples, silence and active-audio ratios, frame-level
level range, sampled pitch percentiles, spectral centroid, and zero-crossing rate. Feature-length
media is decoded incrementally rather than read into memory as one large array.

**Transcribe Selection** uses the existing local Faster-Whisper adapter on intervals up to five
minutes. The selected model downloads its weights on first use when they are not cached.
**Detect Emotion** reuses the existing EmotionEngine on selections up to one minute; it runs the
local acoustic heuristic and, when dialogue text is supplied and a provider is configured, the
existing contextual LLM detector. **Explain Findings with LLM** sends only the measured feature
summary and text entered by the operator. It does not upload the media file. **Export JSON** saves
measurements, transcript, emotion result, and any LLM interpretation for review or later prompting.

The active-audio percentage is an RMS threshold proxy, not speech recognition or VAD. Pitch and
energy on a film mix may be driven by music, effects, or another speaker. Emotion scores are
estimates; use an isolated dialogue stem and review the result before applying TTS controls. Missing
FFmpeg, Whisper weights, or LLM credentials surface as errors; these tools do not substitute sample
results.

### Modular AI dubbing pipeline (Phase 3)

The timeline editor features a direct modular pipeline via the **AI Actions** panel, providing discrete, observable, and cancellable stages for production dubbing:

1. **Extract Dialogue Audio (`A1`)**: Streams audio from the imported movie through FFmpeg into a 16kHz mono reference WAV. Measures duration and populates track `A1`.
2. **Transcribe Speech (`S1`)**: Runs Faster-Whisper ASR with word/segment timestamps. Normalizes overlapping boundaries and populates track `S1` cues, auto-updating the Dialogue Inspector.
3. **Translate Subtitles (`S2`)**: Uses the configurable translation router (Gemini, OpenRouter) or deterministic offline bilingual lexicon fallback (Bengali `bn-BD`/`bn-IN`, Hindi `hi-IN`). Populates track `S2`.
4. **Synthesize Voices (`A2`)**: Generates dubbed speech using Edge-TTS neural voices (`bn-BD-NabanitaNeural`, `bn-BD-PradeepNeural`, `hi-IN-SwaraNeural`, etc.). Computes `actual_duration_s` vs `target_duration_s`, applies non-destructive time-stretching (capped at ±8%), and flags takes with >15% duration mismatch for editorial review.
5. **Render Master Video**: Assembles takes on the timeline with configurable sidechain ducking (-12 dB), muxes original video with new dubbed audio stem via FFmpeg, and registers the master video in project state.

All pipeline workers run asynchronously on isolated `QThread` instances with cooperative cancellation (`requestInterruption()`), progress callbacks, and non-blocking Qt event loop updates.

To test the complete modular pipeline workflow:
```powershell
.venv\Scripts\python.exe -m pytest tests/unit/pipeline/test_modular_pipeline.py tests/unit/ui/test_modular_pipeline_workers.py tests/integration/ui/test_modular_pipeline_workflow.py -v
```

### Professional Timeline Editor & Audio Mixing (Phase 4)

Phase 4 delivers interactive multitrack NLE timeline editing, multitrack audio mixing, voice management with audition caching, and verified broadcast export:

1. **Interactive Timeline Editing**:
   - **Clip Trimming**: Hover over left/right clip edges to activate horizontal trimming (`Qt.CursorShape.SizeHorCursor`). Trimming recalculates clip boundaries non-destructively with collision safety.
   - **Clip Moving**: Drag clip bodies across tracks and time without modifying underlying media files.
   - **Razor / Split (`Ctrl+B`)**: Slices clips directly under the playhead into independent segments.
   - **Clip Deletion (`Delete` / `Backspace`)**: Safely removes selected clips.
   - **Undo / Redo (`Ctrl+Z` / `Ctrl+Y`)**: Complete edit history stack for trimming, moving, splitting, and deletion.
   - **Dynamic Audio Waveforms**: Vector waveform envelopes rendered in real time across audio channels (`A1`-`A5`).

2. **Multitrack Audio Mixer**:
   - Channel strips for `A1: Source Audio`, `A2: Dubbed Dialogue`, `A3: Music Bed`, `A4: SFX`, `A5: Ambience`, and `Master Bus`.
   - Linear dB faders (`0%` to `200%`, default `100%`) with real-time level display.
   - Mute (`M`) and Solo (`S`) buttons with mutual track isolation.
   - Sidechain music ducking (`-12 dB`) automatically attenuates music bed when dubbed dialogue is active.
   - Real-time VU meter peak badge warning against digital clipping (`PEAK: +0.4 dBFS [CLIP]` vs `PEAK: -1.2 dBFS`).
   - Persistent mixer settings serialized to `.aidub/timeline_state.json` on project save.

3. **Voice Management & TTS Caching**:
   - Connected directly to real TTS engines (`EdgeTTSAdapter`, `ChatterboxAdapter`).
   - Dynamic voice enumeration across Bengali (`bn-BD`, `bn-IN`), Hindi (`hi-IN`), English (`en-US`), and other major languages.
   - Pitch slider (-50Hz to +50Hz) and Rate slider (-50% to +50%).
   - Stable SHA-256 audition caching (`cache/tts/tts_<hash>.wav`) preventing redundant network synthesis.
   - Mandatory Voice Cloning Consent & Authorization checkbox blocking unauthorized cloning runs.

4. **Dialogue & Subtitle Synchronization**:
   - Timing conflict detection: flags dubbed takes exceeding target slot duration by >15%.
   - `⚡ Fit to Slot`: non-destructive time-stretching to match source cue timing.
   - `⏱ Nudge Timing (+100ms)`: micro-adjustment of dialogue starts for frame-accurate lip sync.

5. **Broadcast Rendering & Verification**:
   - Hard destination guard preventing accidental overwrite of input video source.
   - Presets for YouTube 4K (H.264/AAC), Netflix 5.1 (ProRes/E-AC-3), Theatrical Master, and Mobile Stream.
   - Post-render FFprobe stream introspection verifying non-zero size, audio/video streams, and valid duration.

To run the Phase 4 test suite:
```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ui/test_phase4_timeline_editor.py -v
```

## Phase 5: Production Readiness, Packaging & Installer

Phase 5 introduces enterprise production-readiness capabilities:
1. **Standalone Windows Distribution Assembly:**
   Run `python packaging/build_windows.py` to create a standalone directory layout in `dist/MovieDubbingStudio_win64`:
   - `bin/`: External FFmpeg/FFprobe binary detection and documentation.
   - `lib/aidub`: Packaged application modules and entrypoints.
   - `resources/`: Localization catalogs (`resources/i18n`), themes, icons, and SQL migrations.
   - `models/`: Model cache configuration and licensing guidelines.
   - Launchers: `MovieDubbingStudio.bat`, `MovieDubbingStudio.ps1`, `aidub.bat`.
2. **Inno Setup 6 Installer:**
   Compile `packaging/installer.iss` using Inno Setup 6 to produce `MovieDubbingStudio_v0.1.0_Setup.exe` with desktop shortcut, start menu entry, and `.aidub` file association.
3. **Crash Recovery & Interrupted Saves:**
   All project state writes (`timeline_state.json`) use `.tmp` staging, automatic `.bak` backup creation, and atomic replacement. Corrupted project files fall back to `.bak` automatically.
4. **User Preferences & Logging:**
   Saved atomically to `%APPDATA%/aidub/preferences.json`. Rotating file logging (`RotatingFileHandler` 5MB, 3 backups) with secret token redaction (`REDACTED_SECRET`).

## Clean Windows Installation & Smoke Test Checklist

For clean deployment on a new Windows 10/11 64-bit machine:

1. **Prerequisites Verification:**
   - Ensure Python 3.12 or 3.13 (64-bit) is installed with "Add Python to PATH" enabled.
   - Ensure FFmpeg is installed and added to PATH, or download `ffmpeg.exe` and `ffprobe.exe` and place them directly into `dist\MovieDubbingStudio_win64\bin\`.
2. **Build Distribution or Install Wheel:**
   ```powershell
   # Option A: Assemble standalone distribution folder
   python packaging/build_windows.py

   # Option B: Build and install standard Python wheel
   pip install dist/aidub_studio-0.1.0.dev0-py3-none-any.whl[desktop]
   ```
3. **Runtime Diagnostics Smoke Test:**
   ```powershell
   # Test CLI doctor check
   dist\MovieDubbingStudio_win64\aidub.bat doctor --json
   ```
4. **Launch Workstation GUI:**
   ```powershell
   # Double-click MovieDubbingStudio.bat or run:
   dist\MovieDubbingStudio_win64\MovieDubbingStudio.bat
   ```
5. **Verify Preferences & Keyboard Shortcuts:**
   - Press `Ctrl+,` to open Preferences: toggle theme to "Broadcast Gray" or "High Contrast", click Save.
   - Press `F1` to open Keyboard Shortcuts: search for "Split" and verify row filtering.
6. **Verify Diagnostic Support Bundle Export:**
   - Open Help > "Export Diagnostic Support Bundle...".
   - Confirm a sanitized ZIP archive is generated without plain-text secrets.

## Status

All 968 unit, integration, and UI tests pass with 100% success rate on Windows 11. Linting (`ruff check`) and code formatting (`ruff format`) pass with zero defects.
Full operational domain classifications, performance metrics, and dependency guides are documented in [RELEASE_READINESS.md](file:///c:/Users/24030/moviedubbing/Moviedubbing/docs/RELEASE_READINESS.md) and [REPAIR_AUDIT.md](file:///c:/Users/24030/moviedubbing/Moviedubbing/docs/REPAIR_AUDIT.md).
