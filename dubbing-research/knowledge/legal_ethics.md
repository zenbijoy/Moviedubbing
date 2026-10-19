# Legal, Ethical & Licensing Guidelines for AI Dubbing
**Date:** 2026-10-19 | **Compliance Protocol (Not Legal Advice)**

---

## 1. Voice Likeness & Personality Rights
- **Biometric Voice Identity:** Synthesizing an identifiable living or deceased actor's voice without explicit authorization infringes on publicity rights, biometric privacy laws, and copyright protections.
- **Safe Harbor Production Practice:**
  - For commercial dubbing: Obtain explicit contractual voice likeness releases.
  - For R&D / Demo showcases: Dub foreign language cinema using **original synthetic character timbres** or generic stylized voice models rather than famous celebrity voices.

---

## 2. Model & Dataset License Compatibility Matrix

| Asset | Official License | Commercial Use Allowed? | DubForge Deployment Rule |
| :--- | :--- | :--- | :--- |
| **XTTS-v2** | Coqui Public Model License (CPML) | **NO** (Strict Non-Commercial) | Prohibited in commercial pipeline; research demo only. |
| **F5-TTS Weights** | CC-BY-NC 4.0 | **NO** (Non-Commercial) | Research only; re-train weights on commercial dataset for prod. |
| **Wav2Lip** | Academic Non-Commercial | **NO** | Replace with **LatentSync** (Apache 2.0) or custom model. |
| **Mel-Band Roformer** | MIT | **YES** | Safe for production deployment. |
| **Whisper (OpenAI)** | MIT | **YES** | Fully permissive commercial use. |
| **W2v-BERT 2.0 (Meta)** | CC-BY-NC 4.0 | **NO** (Original weights) | Check specific fine-tune license before commercializing. |
| **IndicTrans2** | MIT | **YES** | Permissive commercial open source. |
| **Edge-TTS** | Unofficial API wrapper (Microsoft) | **TOS Restricted** | Use for rapid prototyping; replace with self-hosted VITS/Piper in production. |
| **RVC v2** | MIT | **YES** | Permissive audio processing engine. |

---

## 3. Watermarking, Provenance & Responsible Disclosure
1. **Audio Provenance:** Embed imperceptible cryptographic watermarks using **AudioSeal** (Meta, MIT) into all synthesized dialogue tracks to prevent malicious deepfake misuse.
2. **Metadata Transparency:** Attach **C2PA / Coalition for Content Provenance and Authenticity** manifest tags in the MP4 container metadata:
   - `dubbing_engine: DubForge v1.0`
   - `synthesis_type: AI_ADR_Bengali`
   - `disclosure: "Dialogue translated and synthesized via AI voice synthesis."`
