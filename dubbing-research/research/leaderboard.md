# Open-Source Dubbing Research Leaderboard (Bengali Movie Target)

Ranked based on architectural maturity, timing-drift resilience, Bengali adaptability, VRAM feasibility (12–16GB GPU constraint), and code quality.

## Top 10 Repositories for Bengali Movie Dubbing

| Rank | Repository | Stars | Key Strength to Adopt | Why it Ranks High |
|:---:|---|:---:|---|---|
| **1** | [akshinmrv/Voxa](cards/akshinmrv__Voxa.md) | 16 | **Anchored Placement & Back-Transcribing QC** | Structurally solves cumulative timing drift by assigning onset-to-onset slots instead of accumulating clips. Character-budgeted translation prevents unnatural speedups. Automated back-ASR scoring verifies take fidelity. |
| **2** | [timoncool/dub-studio](cards/timoncool__dub-studio.md) | 198 | **Mel-Band Roformer & Face+Voice Binding** | SOTA vocal separation via BSRoformer.cpp. Face recognition co-occurrence automatically binds character visual identities to speaker voices across movie scenes. Embedded MCP server. Zero Python runtime footprint. |
| **3** | [R3gm/SoniTranslate](cards/R3gm__SoniTranslate.md) | 1,422 | **RVC Voice Conversion & Overlap Reduction** | Battle-tested multi-speaker dubbing (up to 12 speakers). Solves the XTTS Bengali deficiency by synthesizing in clean Edge-TTS and converting timbre with RVC v2 models. Includes dedicated speaker overlap reduction. |
| **4** | [zast57/ZastTranslate](cards/zast57__ZastTranslate.md) | 51 | **8-Stage Subtitle Stabilization** | Crucial post-ASR cleaning pipeline (`MIN_CUE_WORDS=3`, 40ms monotonic gap clamping, anti-dangling fragment merger) that eliminates Whisper acoustic hallucinations before LLM translation. |
| **5** | [google-marketing-solutions/ariel](cards/google-marketing-solutions__ariel.md) | 100+ | **BS-RoFormer & Intonation Prompting** | Production cloud reference using BS-RoFormer (`sdr_12.97`) for zero-bleed stem isolation and Gemini intonation instructions for expressive speech delivery. Interactive draggable timeline editor. |
| **6** | [kadirb4rut/video-dubbing-translator](cards/kadirb4rut__video-dubbing-translator.md) | 12 | **VoxCPM2 48kHz Voice Cloning & LatentSync** | Demonstrates clean integration of OpenBMB's VoxCPM2 for high-sample-rate reference voice cloning and LatentSync environment isolation. |
| **7** | [liuzhao1225/YouDub-webui](cards/liuzhao1225__YouDub-webui.md) | 5,685 | **Resumable Task Graph & Length-Constrained Prompts** | Highly robust multi-step job orchestration with clean caching, partial segment re-rendering, and multi-provider LLM length adaptation. |
| **8** | [jianchang512/pyvideotrans](cards/jianchang512__pyvideotrans.md) | 12,500+ | **Resilient Speed Clamps & Provider Abstractions** | Unmatched breadth of engine fallback routines, bounded rubberband time-stretching (0.8x–1.35x), and rich desktop GUI controls. |
| **9** | [M-SRIKAR-VARDHAN/speech-to-speech-with-lipsync](cards/M-SRIKAR-VARDHAN__speech-to-speech-with-lipsync.md) | 25+ | **Wav2Lip + GFPGAN Face Restoration** | Solves the classic Wav2Lip lower-face blurring issue by chaining GFPGAN super-resolution over the generated mouth region. |
| **10** | [facebookresearch/demucs](cards/facebookresearch__demucs.md) | 8,800+ | **HTDemucs Separation Baseline** | Essential, bulletproof 4-stem audio separation baseline to isolate dialogue from background music and sound effects (M&E). |

---

## "Do Not Bother" List (Avoid Spending Time On)

1. **`g33k0b1/Dubbing-World`**: Empty landing page; zero functional processing code.
2. **`DablewCodes/voicevoyage.ai`**: Undergraduate toy wrapper that merely calls three proprietary commercial cloud APIs (AssemblyAI, DeepL, ElevenLabs).
3. **`Amankumar321/AI-Dubber`**: Hardcoded to VALL-E X which has high hallucination rates and zero Bengali support.
4. **`medahmedkrichen/ViDubb` & `yaranbarzi/aigolden-dubbing`**: Naive exploratory Jupyter notebooks with robotic gTTS and zero stem separation.
5. **`allvoicelab/allvoicelab` & `perso-ai/perso-dubbing-plugin`**: Proprietary cloud wrappers designed to sell commercial API subscriptions.
6. **`grayhatdevelopers/deepdub`**: Outdated legacy models (DeepSpeech, Tacotron2) from 2022 that have been completely superseded by modern diffusion and transformer architectures.
7. **`koesan/ReManga_web`**: Manga comic image translation; irrelevant for movie speech and temporal audio sync.
