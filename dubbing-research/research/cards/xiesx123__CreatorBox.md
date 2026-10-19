# xiesx123/CreatorBox

**Verdict:** All-in-one content creator toolbox featuring captioning, video translation, and audio separation.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | Demucs |
| ASR | Faster-Whisper |
| Translation | DeepL / OpenAI |
| TTS | Edge-TTS / CosyVoice |
| Mixing | FFmpeg |

## Bengali Readiness
- **Status:** Partial — CosyVoice provides cross-lingual voice cloning with proper phoneme mapping.

## Timing & Synchronization Approach
Subtitle timecode pacing.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Clean PySide6 desktop interface components.

## Weaknesses & Critical Risks
- Chinese UI focus; fragmented tool modules.

## License & Project Health
- **License:** GPL-3.0.

## Reuse Recommendation
**Study only (inspect PySide6 UI styling).**

## Confidence & Verification
- **Confidence:** High.
