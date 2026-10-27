# Voice Engine Compatibility & Hardware Matrix

This document provides a comprehensive operational, architectural, and hardware compatibility breakdown for all integrated and supported voice engines in **MovieDubbing**.

---

## 1. Executive Summary & Capabilities Matrix

| Engine Backend | Implementation | Primary License | Zero-Shot Voice Cloning | Emotional Expressiveness | Native Supported Languages | Hardware Requirements |
|---|---|---|---|---|---|---|
| **Microsoft Edge-TTS** | [`EdgeTTSVoiceEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/edge_tts_adapter.py) | Service Terms (Free tier) | ❌ Preset neural voices only | Rate & Pitch modulation | 70+ languages (incl. Bengali `bn-BD`) | CPU only (<50MB RAM) |
| **Gemini 3.8 Flash TTS** | [`GeminiTTSVoiceEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/gemini_tts_adapter.py) | Google Cloud API | ❌ Studio neural presets | High (Prompt directive style) | Multilingual | CPU / Cloud API |
| **ElevenLabs Multilingual** | [`ElevenLabsVoiceEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/elevenlabs_adapter.py) | Commercial API | ✅ Instant Voice Cloning | Stability, Style, Boost | 29+ languages (Multilingual v2) | CPU / Cloud API |
| **F5-TTS (SWivid)** | [`F5TTSVoiceEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/open_models_adapter.py) | **MIT License** | ✅ 3–10s reference audio | High (Flow matching ODE) | Cross-lingual zero-shot | 8GB RAM, 4GB VRAM GPU |
| **CosyVoice (FunAudioLLM)**| [`CosyVoiceEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/open_models_adapter.py) | **Apache 2.0** | ✅ Zero-shot prompt clone | High (Instruction tags) | Cross-lingual & multi-accent | 16GB RAM, 6GB VRAM GPU |
| **OpenVoice V2 (MyShell)** | [`OpenVoiceEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/open_models_adapter.py) | **MIT License** | ✅ Tone Color Converter | Base-TTS dependent | Multilingual | 4GB RAM, 2GB VRAM GPU |
| **Qwen3-TTS (QwenLM candidate)** | [`QwenTTSVoiceEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/open_models_adapter.py) | **Apache 2.0** | ✅ Prompt in-context clone | Very High (Natural dialogue) | 30+ languages | 16GB RAM, 12GB VRAM GPU |
| **Synthetic Reference Engine** | [`SyntheticVoiceEngine`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice_base.py) | **MIT License** | ✅ Deterministic test stub | Full control mapping | All ISO language tags | Zero GPU (<10MB RAM) |

---

## 2. Hardware Probing & Engine Selection Flow

The MovieDubbing engine manager automatically probes system resources at initialization:
1. **CUDA VRAM Verification**: Queries `torch.cuda.get_device_properties()` when PyTorch is available.
2. **System RAM & Disk Space Verification**: Validates $\ge 2.0$ GB free disk space prior to any batch generation.
3. **Graceful Capability Fallback**:
   - If an open-source model (e.g. F5-TTS or CosyVoice) is requested but CUDA or local weights are absent, [`VoiceEngineRegistry`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/adapters/voice/engine_registry.py) degrades gracefully to `EdgeTTSVoiceEngine` or `SyntheticVoiceEngine`, recording the fallback rationale in the cue's audit history.
   - If an emotional tag (e.g., `whisper` or `screaming`) is requested on an engine lacking emotional control, [`ScenePerformanceService`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/application/voice/scene_performance_service.py) normalizes the request to neutral delivery and logs an informative note.

---

## 3. Privacy, Security & Consent Gates

Any engine supporting voice cloning (`ElevenLabs`, `F5-TTS`, `CosyVoice`, `OpenVoice`, `Chatterbox`) requires explicit voice cloning consent verification:
- Before any audio reference is ingested, `consent_authorized: bool = True` must be recorded on the character profile.
- All cloning requests without consent raise `PermissionError` and are blocked from invoking remote or local inference APIs.
