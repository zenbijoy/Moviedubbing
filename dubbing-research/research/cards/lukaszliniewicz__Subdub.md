# lukaszliniewicz/Subdub

**Verdict:** Focused CLI video-to-dubbed-video tool specializing in subtitle-driven translation and synchronization.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Input | Video or existing SRT subtitles |
| ASR | Whisper |
| Translation | DeepL / Google / MarianMT |
| TTS | Coqui TTS / Piper / Edge-TTS |
| Audio Mixing | FFmpeg |

## Bengali Readiness
- **Status:** Partial — Works with Edge-TTS and Google Translate.

## Timing & Synchronization Approach
SRT timecode matching with linear time-stretch.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- CLI script built specifically to power downstream Pandrator.

## Weaknesses & Critical Risks
- Audio time-stretching causes distortion if subtitle is overly long.

## License & Project Health
- **License:** GPL-3.0.

## Reuse Recommendation
**Study only.**

## Confidence & Verification
- **Confidence:** High.
