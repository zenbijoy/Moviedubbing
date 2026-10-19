# Actionable Bengali (`bn-BD`) AI Dubbing Plan

Engineering roadmap to achieve studio-quality Bengali movie dubbing under a single 12–16GB GPU constraint (Colab / Kaggle / Local RTX).

---

## 1. Speech Recognition (ASR) for Bengali
* **Primary Recommendation:** `faster-whisper-large-v3` running with CTranslate2 in `int8_float16` mode.
* **Why:** Whisper Large-v3 exhibits strong Bengali comprehension across colloquial Bangladeshi (`bn-BD`) and West Bengal (`bn-IN`) dialects.
* **Refinement Pass:** Feed the audio through WhisperX with phoneme alignment to obtain millisecond-accurate word boundaries for syllable matching.

---

## 2. Translation & Screenplay Localization
* **Recommended Engine:** `Qwen2.5-7B-Instruct` (quantized 4-bit for local GPU, ~5.5GB VRAM) or `DeepSeek-V3` / `Gemini 2.5 Flash` via API.
* **Prompt Engineering Strategy (Length Budgeting):**
```text
Source Line: "{source_text}"
Original Duration: {duration_ms} ms
Maximum Target Characters: {max_chars}
Task: Translate this dialogue into natural colloquial Bengali (Dhaka/cinema register).
Rule: The Bengali translation MUST be spoken naturally in exactly {duration_ms} ms. Match syllable count closely. Do not use archaic bookish words (Sadhu Bhasha).
```

---

## 3. Voice Cloning & Synthesis (Overcoming the XTTS Bengali Barrier)
Since base XTTS-v2 lacks native Bengali tokens, choose one of these two verified production paths:

### Path A: Edge-TTS + Character RVC v2 (Immediate High Quality, 0 VRAM training needed)
1. Synthesize dialogue using Microsoft Edge-TTS high-fidelity neural Bengali voices:
   * `bn-BD-PradeepNeural` (Male protagonist)
   * `bn-BD-NabanitaNeural` (Female lead)
2. Train a lightweight RVC v2 (Retrieval-based Voice Conversion) checkpoint on 5–10 minutes of clean isolated dialogue from the original movie actor.
3. Pass the Edge-TTS audio through RVC v2. Result: Flawless Bengali pronunciation spoken in the exact voice timbre of the original Hollywood/foreign actor.

### Path B: Chatterbox / VoxCPM 2 Bengali LoRA on Kaggle (Full Zero-Shot Offline)
1. Preprocess OpenSLR 53 Bengali Speech corpus (40 hours) and Mozilla Common Voice Bengali.
2. Train LoRA adapter (`rank=16`, `alpha=32`) on the flow-matching acoustic decoder of Chatterbox on Kaggle's free dual NVIDIA T4 GPUs.
3. Export as FP16 SafeTensors (~1.2GB) for local zero-shot inference.

---

## 4. Hardware Memory Budget (Single 12–16GB GPU)
To prevent Out-Of-Memory (OOM) crashes, execute the pipeline sequentially with explicit memory cleanup:

| Stage | Active Model | VRAM Usage | Action After Stage |
|---|---|---|---|
| **Step 1: Separation** | Mel-Band Roformer (ONNX/C++) | ~2.5 GB | Unload weights, `torch.cuda.empty_cache()` |
| **Step 2: ASR & Alignment** | Faster-Whisper + WhisperX | ~3.2 GB | Unload weights |
| **Step 3: Translation** | Local Qwen2.5-7B (4-bit) or Cloud API | ~5.5 GB (or 0 GB if API) | Unload weights |
| **Step 4: TTS & Voice Clone** | Chatterbox / RVC v2 | ~4.0 GB | Unload weights |
| **Step 5: Lip-Sync (Selective)**| LatentSync / Wav2Lip + GFPGAN | ~8.0 GB | Final render |
