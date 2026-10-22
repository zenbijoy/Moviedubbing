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

## Status

`aidub dub --input <movie> --output <new-master.mp4>` runs the real full-source pipeline. It needs
Faster-Whisper, FFmpeg, Edge TTS, a configured translation provider, and—when full speaker/music
separation is enabled—PyAnnote access and Demucs. `--no-diarization` uses one selected target voice
for all recognized dialogue. The app does not perform actor voice cloning or lip-sync generation in
this pipeline.

Some optional enterprise adapters are not implemented yet. Cloud object-storage sync, LoRA voice
training, multi-engine render execution, remote fleet deployment, isolated plugin loading, C2PA
signing, and audio provenance watermarking now fail with explicit unavailable errors. Release/QC
reports require supplied measurements and do not invent passing scores. These limits are also
reflected in the UI; a missing backend never marks a job successful.

The desktop app is still pre-alpha and is not a full CapCut/Premiere replacement. The Inception
media was validated locally for stream metadata, but a complete dubbed master was not rendered in
this verification run. Rotate any credentials exposed outside `.env` before making provider calls.
# Moviedubbing  
