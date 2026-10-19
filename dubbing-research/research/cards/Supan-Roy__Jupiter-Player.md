# Supan-Roy/Jupiter-Player

**Verdict:** Specialized media player with real-time on-the-fly subtitle overlay, translation, and auto-dubbing.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Playback | MPV / VLC core |
| ASR | Whisper offline |
| Translation | Argos Translate (offline) / Google |
| TTS | System TTS / Edge-TTS |

## Bengali Readiness
- **Status:** Partial — Offline Argos Translate has weak Bengali models; Edge-TTS works.

## Timing & Synchronization Approach
Real-time playhead synchronization.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Player-level subtitle synchronization without rendering a new video file.

## Weaknesses & Critical Risks
- Not an editor; cannot export studio masters.

## License & Project Health
- **License:** MIT.

## Reuse Recommendation
**Study only.**

## Confidence & Verification
- **Confidence:** High.
