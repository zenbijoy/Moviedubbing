# mazzasaverio/youtube-auto-dub

**Verdict:** End-to-end automated YouTube dubbing script featuring Wav2Lip integration and Pyannote diarization.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | Demucs |
| ASR | WhisperX |
| Diarization | Pyannote.audio |
| Translation | Google Translate / DeepL |
| TTS / Cloning | ElevenLabs API / Coqui XTTS |
| Lip-Sync | Wav2Lip |
| Audio Mixing | FFmpeg multi-stem mix |

## Bengali Readiness
- **Status:** Partial — Works if using ElevenLabs Bengali or Edge-TTS; fails on local XTTS.

## Timing & Synchronization Approach
WhisperX word boundary alignment with dynamic silence fill.

## Lip-Sync Approach
Wav2Lip; produces noticeable lower-face resolution blurring unless paired with GFPGAN.

## Strengths Worth Stealing
- Complete multi-speaker pipeline flow from YouTube URL to lip-synced output.

## Weaknesses & Critical Risks
- Wav2Lip visual artifacts; heavy reliance on ElevenLabs paid API for best voice results.

## License & Project Health
- **License:** MIT; 120+ stars.

## Reuse Recommendation
**Copy ideas (Wav2Lip + GFPGAN restoration pass pipeline).**

## Confidence & Verification
- **Confidence:** High.
