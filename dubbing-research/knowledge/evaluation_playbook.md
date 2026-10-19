# Evaluation Playbook: Metrics, Protocols & Gold Test Set
**Date:** 2026-10-19 | **DubForge Engineering Standard**

---

## 1. Automated Metric Suite

| Pipeline Stage | Primary Metric | Target Quality Threshold | Evaluation Tool / Script |
| :--- | :--- | :--- | :--- |
| **ASR (Transcription)** | Word Error Rate (WER) / CER | WER $\le 12.0\%$, CER $\le 4.5\%$ | `jiwer` + `bnunicodenormalizer` |
| **MT (Translation)** | chrF++ and COMET-22 | chrF++ $\ge 58.0$, COMET $\ge 0.82$ | `sacrebleu`, `unbabel-comet` |
| **Translation Isochrony** | Duration Delta % | $|T_{target} - T_{orig}| / T_{orig} \le 10\%$ | Custom timestamp analysis |
| **TTS Naturalness** | UTMOS / NISQA | UTMOS $\ge 3.85 / 5.0$ | UTMOS pre-trained model |
| **Voice Cloning Similarity** | Speaker Embedding Cosine Sim | Cosine Similarity $\ge 0.80$ | SpeechBrain ECAPA-TDNN |
| **Lip Synchronization** | LSE-C / LSE-D | LSE-C $\ge 7.0$, LSE-D $\le 7.5$ | SyncNet Lip-Sync Evaluator |
| **Audio Quality (M&E Mix)** | SDR (Signal-to-Distortion Ratio) | Separation SDR $\ge 12.0$ dB | `museval` / BS-RoFormer evaluation |

---

## 2. Human Evaluation Protocol (MOS & CMOS)

Automated metrics can miss subtle Bengali nuances (e.g. offensive honorific mismatches or unnatural syllable dragging).

### 2.1 Study Design
- **Panel Size:** Minimum 15 native Bengali speakers (balanced between Dhaka and Kolkata dialects).
- **Format:** Double-blind randomized A/B or 5-point Likert Scale (MOS):
  1. **Voice Naturalness:** 1 (Completely robotic) to 5 (Indistinguishable from human voice actor).
  2. **Character Timbre Similarity:** 1 (Completely different person) to 5 (Exact original actor speaking Bengali).
  3. **Emotion & Acting Conviction:** 1 (Monotone / inappropriate) to 5 (Matches dramatic context perfectly).
  4. **Lip-Sync Coherence:** 1 (Blatant desynchronization) to 5 (Natural mouth flap alignment).
  5. **Honorific & Cultural Naturalness:** 1 (Nonsensical pronoun mixing) to 5 (Flawless dramatic dialogue).

---

## 3. Minimal "Gold Test Set" Specification (Build by One Person)

To reliably test pipeline iterations on a single GPU without endless full-length movie renders:

- **Size:** Exactly **20 clips**, each **15 to 30 seconds** long (~7 minutes total audio).
- **Composition:**
  - **Action / High Noise (4 clips):** Explosions, gunfire, vehicle chases (tests Mel-Band Roformer vocal isolation).
  - **Intimate Drama / Whispers (4 clips):** Quiet conversational dialogue, breathing, soft emotion (tests TTS prosody and low-energy VAD).
  - **Heated Confrontation (4 clips):** High emotion, screaming, overlapping interruptions (tests Pyannote diarization and emotion transfer).
  - **Comedy / Rapid Dialogue (4 clips):** High syllable-per-second rate, colloquial jokes, Banglish (tests LLM duration budgeting and rubberband limits).
  - **Crowd / Multi-Speaker (4 clips):** 3 to 4 distinct characters speaking in rapid succession (tests multi-track ADR placement).
- **Ground Truth Deliverables:**
  - `ground_truth_transcription.json`: Time-coded verbatim original English.
  - `ground_truth_speakers.json`: Character ID boundaries.
  - `gold_bengali_script.json`: Human-dubbed Bengali script with verified syllable counts.
