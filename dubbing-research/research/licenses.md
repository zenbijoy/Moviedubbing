# License Risk Analysis for Open-Source Dubbing Components

Comprehensive evaluation of software licenses across candidate components for a commercial or studio dubbing release.

| Component / Model | Repository / Author | License | Commercial Viability | Risk Analysis & Action |
|---|---|---|:---:|---|
| **Mel-Band Roformer** | `ZFTurbo / timoncool` | MIT | **APPROVED** | Fully permissive. Safe for commercial and offline desktop distribution. |
| **Demucs v4** | `facebookresearch/demucs` | MIT | **APPROVED** | Permissive MIT license; Meta archived the repo, but forks are clean. |
| **Faster-Whisper** | `SYSTRAN/faster-whisper` | MIT | **APPROVED** | Permissive. CTranslate2 engine is also MIT/Apache compatible. |
| **WhisperX** | `m-bain/whisperX` | BSD-2-Clause | **APPROVED** | Highly permissive. Forced alignment models vary by language. |
| **Pyannote.audio 3.1** | `pyannote/pyannote-audio` | MIT (Code) / Gated Model Terms | **CONDITIONAL** | Code is MIT, but accessing Hugging Face model weights requires agreeing to biometric terms. Cannot be bundled blindly. |
| **Voxa** | `akshinmrv/Voxa` | MIT | **APPROVED** | Clean MIT license. Ideal codebase to borrow timing and QC patterns from. |
| **ZastTranslate** | `zast57/ZastTranslate` | MIT | **APPROVED** | Permissive. Safe to adapt the 8-stage subtitle stabilization code. |
| **SoniTranslate** | `R3gm/SoniTranslate` | Apache-2.0 | **APPROVED** | Permissive with patent grant. Great for borrowing RVC and overlap reduction logic. |
| **YouDub-webui** | `liuzhao1225/YouDub-webui` | AGPL-3.0 | **HIGH RISK (COPYLEFT)** | Strong copyleft. Any system incorporating YouDub code directly must open-source its entire codebase under AGPL. **Recommendation: Study concepts only, write clean-room implementation.** |
| **pyvideotrans** | `jianchang512/pyvideotrans` | GPL-3.0 | **HIGH RISK (COPYLEFT)** | Standard GPL copyleft. Cannot statically link or copy code into a closed proprietary workstation. |
| **XTTS-v2** | `coqui-ai/TTS` | CPML (Coqui Public Model License) | **PROHIBITED** | CPML explicitly forbids commercial use without a paid license. Coqui Inc. has dissolved, meaning commercial licenses cannot be purchased. |
| **F5-TTS Pretrained Weights** | `SWivid/F5-TTS` | CC-BY-NC 4.0 | **PROHIBITED** | Official pretrained checkpoints are strictly Non-Commercial. Safe only if trained from scratch on open licensed audio. |
| **Chatterbox** | `resemble-ai/chatterbox` | Apache-2.0 / BSD | **APPROVED** | Clean permissive license; ideal target for custom Bengali fine-tuning. |
| **LatentSync** | `bytedance/LatentSync` | Apache-2.0 (Code) / OpenRAIL++ (Weights) | **CONDITIONAL** | Allows commercial use subject to OpenRAIL ethical use restrictions (disclosure of synthetic video). |
| **Wav2Lip** | `Rudrabha/Wav2Lip` | Non-Commercial Research Only | **PROHIBITED** | Academic license forbidding commercial exploitation. Use LatentSync instead. |
