# lukaszliniewicz/Pandrator

**Verdict:** Comprehensive media translation station converting PDFs/EPUBs to audiobooks and videos to dubbed videos with RVC and XTTS fine-tuning.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| ASR | WhisperX |
| Translation | MarianMT / NLLB-200 / DeepL / Local LLM |
| TTS / Cloning | XTTS v2 with built-in voice fine-tuning + RVC |
| Voice Conversion | RVC (v1 & v2 models) |
| Audio Mixing | Demucs stem remix |

## Bengali Readiness
- **Status:** Partial — NLLB-200 supports Bengali; XTTS fine-tuning module allows training custom Bengali character adapters.

## Timing & Synchronization Approach
SubRip timecode fitting.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Integrated XTTS fine-tuning interface and RVC model pipeline for persistent character voices.

## Weaknesses & Critical Risks
- Heavy desktop GUI dependencies; high initial setup friction.

## License & Project Health
- **License:** GPL-3.0; 80+ stars.

## Reuse Recommendation
**Copy ideas (RVC character voice fine-tuning pipeline).**

## Confidence & Verification
- **Confidence:** High.
