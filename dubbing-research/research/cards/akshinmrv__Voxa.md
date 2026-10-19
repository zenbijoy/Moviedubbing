# akshinmrv/Voxa

**Verdict:** Masterclass in timeline synchronization: eliminates cumulative dub drift via anchored placement, length-budgeted translation, and quality gating.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| ASR | Faster-Whisper with word-onset refinement |
| Diarization | Pyannote (optional `--diarize`) |
| Translation | Google / Ollama / OpenAI / Anthropic (context-aware, length-budgeted) |
| TTS | Edge-TTS (100+ locales) / Piper (offline) / XTTS v2 / OpenAI |
| Audio Timing | Anchored placement (no cumulative drift), speed-up only, 2-pass loudnorm |
| Quality Gate | Back-transcription with 2nd ASR to score WER, clipping, and pacing |

## Bengali Readiness
- **Status:** Yes — Full Bengali coverage via Faster-Whisper, Google/OpenAI translation, and Edge-TTS (`bn-BD-NabanitaNeural`).

## Timing & Synchronization Approach
Anchored placement: slot runs from line onset to next line onset; cursor is assigned, never accumulated. Character budget in translation prompt prevents rushing.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Zero-drift anchored placement, 2-pass EBU R128 loudness normalization, automated back-transcription QC scoring loop, single-file CLI simplicity (`voxa.py`).

## Weaknesses & Critical Risks
- Single-file script structure makes deep UI extension harder.

## License & Project Health
- **License:** MIT; 16 stars, exceptionally well-architected.

## Reuse Recommendation
**Copy ideas (must adopt the anchored placement algorithm, character-budgeted translation prompt, and back-transcription QC).**

## Confidence & Verification
- **Confidence:** Very High (verified from source code and architecture doc).
