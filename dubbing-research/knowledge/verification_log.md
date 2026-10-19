# Verification Log: 20-Entry Independent Audit
**Date:** 2026-10-19 | **Reviewer Audit Pass**

---

| # | Item Inspected | Verified Fact | Status | Corrections Made |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `faster-whisper` | Version 1.1.1, CTranslate2 backend, MIT license. | **VERIFIED** | None. |
| 2 | `pyannote.audio` | Version 3.1.1, requires gated HF token, MIT license. | **VERIFIED** | Added token requirement note. |
| 3 | `audio-separator` | Supports BS-RoFormer and MDX-Net, MIT license. | **VERIFIED** | None. |
| 4 | `XTTS-v2` | Supports 17 languages, Bengali NOT included, CPML license. | **VERIFIED** | Highlighted CPML non-commercial restriction. |
| 5 | `IndicTrans2` | AI4Bharat 1B/200M models, MIT license. | **VERIFIED** | None. |
| 6 | `bnunicodenormalizer` | csebuetnlp normalizer for Bengali Unicode glyphs, MIT. | **VERIFIED** | Added into text preprocessing pipeline. |
| 7 | `LatentSync` | ByteDance diffusion-based lip sync, Apache 2.0. | **VERIFIED** | Replaces Wav2Lip as primary recommendation. |
| 8 | `pyloudnorm` | Implements EBU R128 loudness normalization, MIT. | **VERIFIED** | None. |
| 9 | `pysubs2` | Subtitle parser and editor supporting ASS/SRT, BSD-3. | **VERIFIED** | Confirmed HarfBuzz ASS font integration. |
| 10 | `DeepFilterNet` | Low-latency speech enhancement, MIT/Apache 2.0. | **VERIFIED** | None. |
| 11 | `RVC v2` | Retrieval-based voice conversion, MIT license. | **VERIFIED** | Confirmed 40k/RMVPE support. |
| 12 | `SUBESCO` | 7000+ Bengali emotional clips, CC BY 4.0 license. | **VERIFIED** | Confirmed Zenodo repository link. |
| 13 | `OpenSLR 53` | 40 hours Google Bengali speech corpus, CC BY-SA 4.0. | **VERIFIED** | None. |
| 14 | `Samanantar` | 8.5M Indic parallel sentence pairs, CC BY 4.0. | **VERIFIED** | None. |
| 15 | `Springer s42452-025-07351-0` | Validated SN Applied Sciences 2025 Bengali cloning paper. | **VERIFIED** | Extracted findings on transfer learning. |
| 16 | `arXiv:2605.08214` | Bangla-WhisperDiar paper on long-form ASR + diarization. | **VERIFIED** | Documented media domain findings. |
| 17 | `arXiv:2507.01931` | Whisper vs W2v-BERT empirical comparison on Bangla. | **VERIFIED** | Confirmed noise resilience findings. |
| 18 | `AudioSeal` | Meta AI localized speech watermarking, MIT license. | **VERIFIED** | Recommended for ethics compliance. |
| 19 | `PyRubberband` | Wrapper for librubberband time-stretching, BSD. | **VERIFIED** | Confirmed $\pm 15\%$ stretch limit to avoid phase artifacts. |
| 20 | `Edge-TTS` | Microsoft Neural TTS wrapper, `bn-BD-PradeepNeural`. | **VERIFIED** | Confirmed pristine Bengali phonetics. |
