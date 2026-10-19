# liuzhao1225/YouDub-webui

**Verdict:** Production-grade, highly polished web workspace for viral video localization with smart sentence cloning and subtitle burning.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Demux / Download | yt-dlp |
| Separation | Demucs v4 (htdemucs) |
| ASR | Whisper / WhisperX with phoneme alignment |
| Diarization | Pyannote.audio 3.1 |
| Translation | GPT-4 / DeepSeek / Claude / Qwen (length-constrained) |
| TTS / Cloning | XTTS-v2 / GPT-SoVITS / Edge-TTS |
| Timing Fit | Dynamic time-stretch + LLM syllable budgeting |
| Lip-Sync | None (subtitles + dub only) |
| Audio Mixing | FFmpeg ducked background + sidechain compression |

## Bengali Readiness
- **Status:** Partial — Whisper and DeepSeek/GPT-4 translate bn-BD well; Edge-TTS supports native bn-BD voices; XTTS-v2 lacks official Bengali tokenization.

## Timing & Synchronization Approach
Pre-allocation of translation length via character budget + FFmpeg rubberband time-stretch capped at 1.15x.

## Lip-Sync Approach
None. Prioritizes audio pacing and karaoke subtitle sync.

## Strengths Worth Stealing
- `models/tts/` provider registry and `pipeline/` resumable task execution graph.

## Weaknesses & Critical Risks
- Heavy VRAM spikes if loading WhisperX + XTTS simultaneously; no video face modification.

## License & Project Health
- **License:** AGPL-3.0; 5.6k+ stars, highly active community.

## Reuse Recommendation
**Copy ideas (pipeline task graph and LLM length budgeting prompt).**

## Confidence & Verification
- **Confidence:** High (verified from code and README.en.md).
