# Human-In-The-Loop (HITL) Workflow & Review Interface
**Date:** 2026-10-19 | **Post-Production Quality Assurance Guide**

---

## 1. Why 100% Fully Automated Dubbing Fails Commercial Broadcast
Even the most advanced multimodal AI models make contextual errors:
1. Misidentifying who is being spoken to, causing sudden *Tui* vs *Apni* flips.
2. Punctuating during mid-sentence breathing pauses, breaking dialogue pacing.
3. Translating cultural puns literally.

---

## 2. The 3-Point Human Intervention Gate
A streamlined web interface (Gradio / Streamlit / React Web-UI) with three review gates:

```
[Audio Extraction & ASR]
         │
         ▼
[Gate 1: Transcript & Character Verification] (1x playback speed)
- Operator confirms speaker diarization IDs (Character A vs B).
- Operator corrects character names and proper nouns (e.g. Gotham -> গথাম).
         │
         ▼
[Translation & Syllable Budgeting]
         │
         ▼
[Gate 2: Script Adaptation & Honorific Check]
- Color-coded honorific selector (Apni / Tumi / Tui).
- Live syllable count indicator vs source audio duration budget (Green = Fits, Red = Overrunning).
         │
         ▼
[Voice Synthesis & Lip-Sync]
         │
         ▼
[Gate 3: ADR Timing & Final QC]
- Waveform scrubber with original audio on Track 1, Cloned Bengali on Track 2, M&E on Track 3.
- Nudge dialogue offset (+/- 50ms) to snap mouth flap onsets.
```

---

## 3. Active Learning & Fine-Tuning Telemetry
Every human correction made in the UI is automatically serialized to a local parquet dataset:
- `user_corrected_translations.parquet`: Feeds DPO (Direct Preference Optimization) for Bengali LLM prompt adaptation.
- `user_corrected_alignments.parquet`: Improves CTC forced-alignment confidence thresholds.
