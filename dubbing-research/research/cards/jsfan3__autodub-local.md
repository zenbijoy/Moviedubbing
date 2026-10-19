# jsfan3/autodub-local

**Verdict:** Modular, clean CLI & Gradio dubbing tool designed specifically for hybrid local/cloud model switching.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| ASR | Whisper / Faster-Whisper |
| Diarization | Pyannote |
| Translation | Ollama / DeepL / OpenRouter |
| TTS / Cloning | XTTS-v2 / ChatTTS / Edge-TTS |
| Audio Mixing | FFmpeg with sidechain ducking |

## Bengali Readiness
- **Status:** Partial — Edge-TTS Bengali works; Ollama translation handles Bengali if using Llama-3.1 or Gemma-2.

## Timing & Synchronization Approach
Segment time-stretch using sox/ffmpeg with threshold fallback.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Clean configuration management and modular provider interfaces.

## Weaknesses & Critical Risks
- Lacks advanced subtitle stabilization.

## License & Project Health
- **License:** MIT; 80+ stars.

## Reuse Recommendation
**Study only.**

## Confidence & Verification
- **Confidence:** High.
