# sahandghavidel/ai-video-editor

**Verdict:** Full AI video creation workspace handling scripting, transcription, dubbing, scene transitions, and export.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| ASR | Whisper |
| Translation | OpenAI GPT-4 |
| TTS | ElevenLabs / OpenAI TTS |
| Video Editing | Remotion / FFmpeg scene composition |

## Bengali Readiness
- **Status:** Partial — Via OpenAI text and ElevenLabs API.

## Timing & Synchronization Approach
Timeline segment alignment.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Multi-track scene sequencing and timeline state representation.

## Weaknesses & Critical Risks
- Cloud API heavy; no local model execution.

## License & Project Health
- **License:** MIT; 150+ stars.

## Reuse Recommendation
**Study only (timeline data schema).**

## Confidence & Verification
- **Confidence:** High.
