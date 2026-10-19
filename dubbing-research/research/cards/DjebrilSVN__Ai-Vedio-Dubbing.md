# DjebrilSVN/Ai-Vedio-Dubbing

**Verdict:** Straightforward end-to-end dubbing pipeline combining Whisper, translation, and TTS voice cloning with background preservation.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | Demucs |
| ASR | Whisper |
| Translation | Google Translate |
| TTS / Cloning | Coqui TTS / XTTS |
| Audio Mixing | FFmpeg overlay |

## Bengali Readiness
- **Status:** Partial — ASR/translation works; XTTS requires fine-tuned Bengali checkpoint.

## Timing & Synchronization Approach
Simple silence padding and speed up via FFmpeg `atempo`.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Minimalist pipeline flow for understanding end-to-end audio demuxing.

## Weaknesses & Critical Risks
- Primitive error handling; naive atempo causes chipmunk artifacts if speed > 1.25x.

## License & Project Health
- **License:** MIT; small educational repo.

## Reuse Recommendation
**Study only.**

## Confidence & Verification
- **Confidence:** Medium.
