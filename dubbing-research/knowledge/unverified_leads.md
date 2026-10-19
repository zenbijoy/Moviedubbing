# Unverified Leads & Dropped Candidates
**Date:** 2026-10-19 | **Filtered Candidates**

---

1. **`banglatts` PyPI package:**
   - *Status:* Dropped from production stack.
   - *Reason:* Single-speaker toy model lacking multi-speaker cloning, emotional variation, or duration control.
2. **XTTS-v2 Native Bengali Support:**
   - *Status:* **CONFIRMED UNSUPPORTED**.
   - *Evidence:* Coqui XTTS-v2 model card and vocabulary explicitly omit Bengali. Supplying raw Bengali Unicode triggers tokenization errors or unintelligible gibberish.
3. **MMS-TTS Bengali for Movie Dubbing:**
   - *Status:* Deprioritized to low tier.
   - *Reason:* Monotone acoustic outputs with noticeable robotic buzz; requires severe post-processing to sound cinematic.
4. **Wav2Lip in Commercial Production:**
   - *Status:* Rejected for commercial dubbing.
   - *Reason:* Academic non-commercial license and severe 96x96 pixel mouth blur artifacts.
