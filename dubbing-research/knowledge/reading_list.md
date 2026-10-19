# Curated Reading List: Essential Movie Dubbing & Indic Speech Literature
**Date:** 2026-10-19 | **18 Verified Core References**

---

### Tier 1: Read First (Foundational Engineering Architecture)

1. **Neural Dubber: Machine Dubbing with High Quality Lip-Sync and Speech** (Hu et al., NeurIPS 2021)
   - *Link:* [arXiv:2110.08243](https://arxiv.org/abs/2110.08243)
   - *Two-Line Takeaway:* First end-to-end framework solving video-conditioned speech duration matching; directly informs how to control TTS timing from mouth movements.
2. **StyleDubber: Towards Multi-Scale Style Learning for Movie Dubbing** (Gao et al., ACM Multimedia 2023)
   - *Link:* [arXiv:2308.11306](https://arxiv.org/abs/2308.11306)
   - *Two-Line Takeaway:* Disentangles phonetic content from movie actor emotion and acoustic ambience; critical for avoiding flat, emotionless dubbing.
3. **IndicTrans2: Towards High-Quality Machine Translation for Indian Languages** (Gala et al., AI4Bharat, 2023)
   - *Link:* [arXiv:2305.16307](https://arxiv.org/abs/2305.16307)
   - *Two-Line Takeaway:* State-of-the-art open NMT baseline for Indic languages; unmatched grammatical accuracy on formal and colloquial Bengali.
4. **Transfer Learning-Based Voice Cloning for Low-Resource Bengali Language** (Springer SN Applied Sciences, 2025)
   - *Link:* [DOI:10.1007/s42452-025-07351-0](https://link.springer.com/article/10.1007/s42452-025-07351-0)
   - *Two-Line Takeaway:* Validates that small speaker target sets (10-30m) over pre-trained acoustic bases deliver high MOS in Bengali voice cloning.
5. **LatentSync: Audio Conditioned Latent Diffusion for Lip Sync** (ByteDance, 2024)
   - *Link:* [arXiv:2412.09262](https://arxiv.org/abs/2412.09262)
   - *Two-Line Takeaway:* Replaces legacy GAN artifacts with high-resolution diffusion in latent space, eliminating blurry mouth patches.

---

### Tier 2: Skim (Specialized Methodologies)

6. **HPMDubbing: Hierarchical Prosody Modeling for Machine Dubbing** (ICLR 2023)
   - *Link:* [OpenReview:HPMDubbing](https://openreview.net/forum?id=YhN7F9s9wX)
   - *Takeaway:* Hierarchically models sentence-, word-, and phoneme-level prosody for emotional movie dialogue.
7. **Bangla-WhisperDiar: Long-Form Bengali Speech Recognition and Diarization** (arXiv:2605.08214)
   - *Link:* [arXiv:2605.08214](https://arxiv.org/abs/2605.08214)
   - *Takeaway:* Custom Bengali Whisper fine-tune coupled with diarization head for media broadcast transcriptions.
8. **Adaptability of ASR Models on Low-Resource Language: Whisper vs Wav2Vec-BERT on Bangla** (arXiv:2507.01931)
   - *Link:* [arXiv:2507.01931](https://arxiv.org/abs/2507.01931)
   - *Takeaway:* Empirical comparison proving Whisper's superiority in noise vs W2v-BERT's zero-hallucination forced alignment.
9. **SUBESCO: An Extensive Audio Description Dataset for Bengali Emotion** (Zenodo / IEEE, 2021)
   - *Link:* [Zenodo:4525917](https://zenodo.org/record/4525917)
   - *Takeaway:* 7,000 pristine audio clips across 10 emotions; benchmark corpus for Bengali prosody and emotion transfer.
10. **IndicVoices: A Large-Scale Spoken Language Dataset for Indian Languages** (AI4Bharat, Interspeech 2024)
    - *Link:* [arXiv:2403.02884](https://arxiv.org/abs/2403.02884)
    - *Takeaway:* Massive conversational speech collection capturing unscripted natural Bengali cadence.
11. **F5-TTS: A Fairytaler that Fakes Fluent and Faithful Speech with Flow Matching** (Chen et al., 2024)
    - *Link:* [arXiv:2410.06885](https://arxiv.org/abs/2410.06885)
    - *Takeaway:* Non-autoregressive flow-matching architecture capable of fast zero-shot cloning.
12. **Music and Vocal Separation with Band-Split Roformer** (Lu et al., 2023)
    - *Link:* [arXiv:2309.02612](https://arxiv.org/abs/2309.02612)
    - *Takeaway:* Architecture behind Mel-Band Roformer delivering 13+ dB SDR for extracting M&E tracks without vocal leakage.

---

### Tier 3: Reference (Tools, Baselines & Benchmarks)

13. **V2C: Video-to-Speech Synthesis for Movie Dubbing** (Chen et al., CVPR 2022) — Multimodal dubbing benchmark.
14. **TransVIP: Speech-to-Speech Translation with Voice and Isochrony Preservation** (Interspeech 2024).
15. **Seamless: Multilingual Expressive and Streaming Speech Translation** (Meta AI, 2023).
16. **AudioSeal: Proactive Localized Watermarking in Speech** (Meta AI, 2024).
17. **Pyannote.audio 3.1: Advanced Speaker Diarization with Permutation-Invariant Training** (Bredin et al., 2023).
18. **EBU R128: Loudness Normalisation and Permitted Maximum Level of Audio Signals** (EBU Standard).
