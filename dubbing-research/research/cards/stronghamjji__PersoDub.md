# stronghamjji/PersoDub

**Verdict:** Local-first dubbing framework emphasizing personalized voice cloning and privacy.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | Spleeter / Demucs |
| ASR | Whisper |
| Translation | NLLB-200 / DeepL |
| TTS / Cloning | OpenVoice / XTTS |
| Audio Mixing | Pydub stem mixing |

## Bengali Readiness
- **Status:** Partial — NLLB-200 provides strong Bengali translation; voice cloning requires multilingual tone color converter.

## Timing & Synchronization Approach
Segment length matching with audio truncation/fade-out.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- NLLB-200 translation integration.

## Weaknesses & Critical Risks
- Truncating audio causes lost words on sentence overruns.

## License & Project Health
- **License:** Apache-2.0; moderate activity.

## Reuse Recommendation
**Study only.**

## Confidence & Verification
- **Confidence:** Medium.
