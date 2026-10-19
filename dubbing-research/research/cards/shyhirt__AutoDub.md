# shyhirt/AutoDub

**Verdict:** Clean automated dubbing tool linking Whisper, XTTS-v2, and local Ollama for zero-cost dubbing.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| ASR | Whisper |
| Translation | Ollama (Llama 3 / Mistral) |
| TTS / Cloning | XTTS v2 |
| Audio Mixing | MoviePy / FFmpeg |

## Bengali Readiness
- **Status:** No — XTTS v2 does not officially include Bengali (`bn`) in its 17 supported language tokens.

## Timing & Synchronization Approach
Basic moviepy duration matching.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Concise Ollama local LLM translation integration.

## Weaknesses & Critical Risks
- XTTS v2 failure on unsupported Bengali characters without custom phoneme mapping.

## License & Project Health
- **License:** MIT; 40+ stars.

## Reuse Recommendation
**Study only (Ollama prompt structure).**

## Confidence & Verification
- **Confidence:** High.
