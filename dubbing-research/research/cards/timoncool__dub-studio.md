# timoncool/dub-studio

**Verdict:** SOTA native Windows dubbing studio in Rust + C++/CUDA; zero Python runtime, Mel-Band Roformer, Nemotron diarization, and MCP server.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | Mel-Band Roformer (native BSRoformer.cpp on CUDA) |
| ASR | Parakeet-TDT (GPU) or faster-whisper standalone (CPU) |
| Diarization | NVIDIA Nemotron 3 Diarization (up to 8 speakers) |
| Character Casting | Face recognition + voice co-occurrence binding |
| Translation | Gemma-4 12B (GGUF via llama.cpp) / OpenRouter |
| TTS / Cloning | Higgs Audio v3 GGUF (Boson AI) / Gemini TTS |
| OCR / Inpaint | PP-OCR ONNX on-screen text localization |
| Loudness | -14 LUFS with -1 dBTP ceiling |

## Bengali Readiness
- **Status:** Partial to High — Faster-whisper, Gemma-4, and Gemini TTS natively support Bengali; Higgs Audio GGUF supports multilingual zero-shot cloning.

## Timing & Synchronization Approach
Karaoke word-level timestamp alignment with selective per-segment regeneration (~0.17 s/frame preview).

## Lip-Sync Approach
None (replaces audio and localizes on-screen frame text instead).

## Strengths Worth Stealing
- Single portable .exe, Mel-Band Roformer (SOTA separation), Face+Voice co-occurrence character binding across episodes, embedded MCP server.

## Weaknesses & Critical Risks
- Requires 8GB-16GB NVIDIA GPU for full local pipeline; complex native build toolchain.

## License & Project Health
- **License:** Custom / Source-available; 198 stars, highly active.

## Reuse Recommendation
**Copy ideas (Mel-Band Roformer separation, character face-voice binding, and MCP server architecture).**

## Confidence & Verification
- **Confidence:** Very High (verified from extensive technical docs).
