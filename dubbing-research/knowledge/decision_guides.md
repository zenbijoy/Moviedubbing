# Decision Guides: Stage-by-Stage Architecture Matrix
**Date:** 2026-10-19 | **Target Constraints: 12-16 GB GPU, Low-Resource Bengali, Local-First**

---

| Stage | If Condition (Scenario) | Then Use (Recommended Choice) | Else Fallback | Trade-off / Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Separation** | Film has loud background music/action SFX | **Mel-Band Roformer (`audio-separator`)** | Meta Demucs v4 | Mel-Band Roformer yields +2.5 dB SDR over Demucs, preventing vocal echo in M&E stem. |
| **Diarization** | Fast processing needed on GPU | **Pyannote.audio 3.1** | NeMo MSDD | Requires free Hugging Face token; handles up to 8 overlapping movie characters. |
| **ASR** | Clean dialogue segments | **Faster-Whisper Large-v3 (INT8)** | W2v-BERT 2.0 | CTranslate2 INT8 runs in 4.6 GB VRAM with word timestamps. |
| **Alignment** | Word-level timing verification | **CTC Forced Alignment (Torchaudio / Stable-TS)** | Whisper internal attention | Guarantees zero timestamp drift across shot boundaries. |
| **Translation** | Movie dialogue has complex character relationships | **Two-Pass: IndicTrans2 -> Qwen2.5-7B Post-Edit** | NLLB-200-1.3B (CTranslate2) | Pass 2 enforces exact syllable budget and correct honorifics (*Apni/Tumi/Tui*). |
| **TTS / Cloning** | Target is commercial / production quality | **Edge-TTS Bengali + RVC v2 Voice Conversion** | IndicF5 / F5-TTS | Flawless Bengali phonetics and zero hallucinations + instant character timbre match. |
| **Emotion** | Scene has intense anger, crying or shouting | **Emotion2Vec+ Feature Extraction + RVC Pitch Offset** | Parselmouth Pitch Scaling | Transmits original actor pitch dynamics without breaking Bengali phonetic intelligibility. |
| **Audio Mixing** | Combining dialogue stem with M&E track | **Pyloudnorm (EBU R128) + Dynamic Ducking** | Pedalboard Compressor | Normalizes dialogue to -14 LUFS and M&E to -23 LUFS; prevents background music drowning dialogue. |
| **Lip-Sync** | Actor face is in clear speaking close-up | **LatentSync (Selective Gating)** | Wav2Lip + GFPGAN | LatentSync eliminates mouth blurring; only process close-up frames to save GPU time. |
| **Subtitles** | Rendering Bengali subtitles for burned-in video | **pysubs2 + libass (Noto Sans Bengali)** | SRT / moviepy basic text | HarfBuzz OpenType shaping is mandatory to avoid broken conjunct glyphs. |
