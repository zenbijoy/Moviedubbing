# langswap-app/langswap

**Verdict:** Self-hosted, modern full-stack dubbing suite leveraging F5-TTS, Qwen LLM, and Gradio for local multi-lingual dubs.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | Demucs |
| ASR | Faster-Whisper |
| Translation | Qwen2.5 / Local Ollama / vLLM |
| TTS / Cloning | F5-TTS (Flow-matching zero-shot cloning) |
| Lip-Sync | None |
| Audio Mixing | FFmpeg loudness normalization |

## Bengali Readiness
- **Status:** Partial — Faster-Whisper and Qwen2.5 handle Bengali text; base F5-TTS weights require Bengali phoneme fine-tuning.

## Timing & Synchronization Approach
Speaking rate multiplier inside F5-TTS synthesis combined with pause padding.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Clean F5-TTS integration for zero-shot flow matching.

## Weaknesses & Critical Risks
- F5-TTS official checkpoint is CC-BY-NC (non-commercial); high GPU compute requirement for diffusion flow steps.

## License & Project Health
- **License:** GPL-3.0; 250+ stars, active.

## Reuse Recommendation
**Study only (inspect F5-TTS inference loop).**

## Confidence & Verification
- **Confidence:** High (verified from app repository).
