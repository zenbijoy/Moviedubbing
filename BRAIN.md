# BRAIN.md: AI Bengali Movie Dubbing Knowledge Base
**Standing Context for DubForge / Moviedubbing** | **Updated:** 2026-10-19  
**Hardware Profile:** Single 12–16 GB GPU (Colab/Kaggle/RTX) | **Architecture:** Local-First Modular ADR

---

## 1. Executive Pipeline Architecture

```
[Original Film Audio & Video]
            │
            ├──► STAGE 1: VOCAL SEPARATION
            │       Model: Mel-Band Roformer (via audio-separator) -> Output: vocals.wav + mne.wav (BGM/SFX)
            │
            ├──► STAGE 2: DIARIZATION & ACTIVE SPEAKER
            │       Model: Pyannote.audio 3.1 + Silero-VAD v5 -> Output: character_timeline.json
            │
            ├──► STAGE 3: SPEECH RECOGNITION & ALIGNMENT
            │       Model: Faster-Whisper Large-v3 (INT8) + Stable-TS -> Output: word_timestamps.json
            │
            ├──► STAGE 4: TWO-PASS TRANSLATION & DURATION BUDGETING
            │       Draft: IndicTrans2 (CTranslate2) -> Edit: Qwen2.5-7B (Syllable Budget & Honorifics)
            │
            ├──► STAGE 5: CLONED BENGALI SPEECH SYNTHESIS
            │       Primary: Edge-TTS (bn-BD) -> Character RVC v2 Voice Conversion (RMVPE)
            │
            ├──► STAGE 6: TIMING CORRECTION & AUDIO MIXING
            │       Tools: PyRubberband (+/-15% stretch) + Pyloudnorm (EBU R128 Dialogue Ducking)
            │
            └──► STAGE 7: SELECTIVE LIP SYNCHRONIZATION
                    Model: LatentSync (Diffusion UNet, close-up shots only) -> Final Video Remux
```

---

## 2. Recommended Production Stack per Stage

1. **Vocal Separation:** **Mel-Band Roformer** (`audio-separator`) — Delivers ~13 dB SDR, isolating pristine dialogue with zero vocal leakage into background music.
2. **VAD & Diarization:** **Pyannote.audio 3.1** — Industry benchmark for multi-speaker overlap handling in conversational media.
3. **ASR & Alignment:** **Faster-Whisper Large-v3** + **Stable-TS** — Sub-second word alignment with CTranslate2 INT8 execution in 4.6 GB VRAM.
4. **Machine Translation:** **IndicTrans2** (Draft) + **Qwen2.5-7B-Instruct** (Post-Edit) — Enforces strict syllable duration budgets and consistent Bengali honorifics (*Apni/Tumi/Tui*).
5. **TTS & Voice Cloning:** **Edge-TTS Bengali** (`bn-BD-PradeepNeural`/`NabanitaNeural`) $\rightarrow$ **RVC v2** — Solves Bengali G2P and zero-shot voice cloning with zero hallucinations.
6. **Emotion Transfer:** **Emotion2Vec+** + **RVC Pitch Guidance** — Replicates original actor dramatic intensity while preserving phonetic intelligibility.
7. **Audio Post-Production:** **Pyloudnorm** (EBU R128) + **Pedalboard** — Broadcast-standard dynamic dialogue ducking (-14 LUFS dialogue / -23 LUFS master).
8. **Lip Synchronization:** **LatentSync** (Selective Face-Gating) — Diffusion-based visual realism without legacy Wav2Lip mouth blur.
9. **Typography & Subtitles:** **pysubs2** + **libass** (Noto Sans Bengali) — Hardware-accelerated HarfBuzz font shaping for complex Bengali conjuncts (যুক্তবর্ণ).
10. **Pipeline Runtime:** **uv** + **Sequential Model Paging** — Memory ceiling strictly capped at $\le 12.0$ GB VRAM.

---

## 3. The Definitive Answer: XTTS-v2 & Bengali

- **Does XTTS-v2 officially support Bengali?**  
  **NO.** XTTS-v2 officially supports only 17 languages (`en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh, ja, hu, ko, hi`). Bengali Unicode characters are absent from its tokenizer vocabulary; inputting raw Bengali produces tokenization crashes or phonetic gibberish. Furthermore, its Coqui Public Model License (CPML) strictly prohibits commercial deployment.
- **The Best Production Alternative:**  
  **Two-Stage Synthesis (Edge-TTS Bengali $\rightarrow$ Character RVC v2)**:
  - *Stage A (Acoustic Base):* Microsoft Azure / Edge-TTS Bengali neural voices (`bn-BD-PradeepNeural` or `bn-BD-NabanitaNeural`) synthesize natural Bengali phonetics, correct juktoborno handling, and native inflection.
  - *Stage B (Timbre Cloning):* RVC v2 (Retrieval-based Voice Conversion) trained on 15–45 seconds of the original actor's isolated vocal stem converts the base voice into the actor's distinct vocal timbre.
  - *Result:* 100% intelligible, zero hallucination, pristine speaker similarity, zero training compute for base TTS.

---

## 4. Top 10 Hard-Won Engineering Gotchas

1. **The Concatenation Drift Disaster:** Concatenating synthesized dialogue clips sequentially causes cumulative millisecond drift. By minute 45, speech is 15 seconds out of sync.  
   *Fix:* Use **Anchored Timeline Placement** — anchor every synthesized line to the original line's exact start timecode.
2. **Bengali Syllable Inflation:** Bengali translations expand by 20% to 35% in syllable count compared to English.  
   *Fix:* Enforce syllable budgeting in the LLM post-editing prompt to condense phrasing before audio synthesis.
3. **The Honorific Roulette:** Off-the-shelf NMT translates English "you" randomly into *Apni*, *Tumi*, and *Tui* within the same scene.  
   *Fix:* Pass explicit scene character relationship metadata to the translation layer.
4. **Vocal Leakage Destroys Dialogue Ducking:** Inadequate separation leaves original English voice fragments in the background music track.  
   *Fix:* Use Mel-Band Roformer; do not rely on Demucs v4 for high-reverb vocal isolation.
5. **CUDA OOM from Multi-Model Stacking:** Loading Roformer, Whisper, LLM, and LatentSync concurrently exceeds 36 GB VRAM.  
   *Fix:* Strict **Sequential Model Paging** — unload models and flush PyTorch CUDA cache between pipeline stages.
6. **Broken Conjunct Rendering (Juktoborno):** Standard video rendering engines render decomposed or broken Bengali ligature glyphs.  
   *Fix:* Use `libass` compiled with FriBidi and HarfBuzz font shaping using `Noto Sans Bengali` or `SolaimanLipi`.
7. **Chipmunk Artifacts from Extreme Time-Stretching:** Pitch shifting dialogue by $> 15\%$ sounds unnatural.  
   *Fix:* Constrain time-stretching to $\pm 12\%$. If a line still overruns, rewrite the translated text.
8. **Hallucination in Whispers & Silences:** Whisper hallucinates repetitive loops during silent background noise or music.  
   *Fix:* Pre-filter all audio segments through Silero-VAD v5 before feeding into Whisper.
9. **Diffusion Lip-Sync Compute Explosion:** Running LatentSync on full 1080p video takes $> 6$ hours for a 2-hour movie.  
   *Fix:* Apply **Selective Face Gating** — run lip-sync only on frames with active speaking front-facing close-up shots.
10. **License Violations in Commercial Stacks:** Using XTTS-v2 (CPML), F5-TTS base weights (CC-BY-NC), or Wav2Lip (Academic) in commercial software violates copyright.  
    *Fix:* Use MIT/Apache-2.0 alternatives (Edge-TTS/RVC v2/LatentSync/Mel-Band Roformer).

---

## 5. Critical "Never Do This" Rules

- **NEVER** run machine translation line-by-line without preceding scene context.
- **NEVER** feed unnormalized Bengali text with mixed Unicode codepoints into TTS.
- **NEVER** delete or overwrite the original M&E (Music & Effects) stems; keep stems isolated for master re-balancing.
- **NEVER** apply global time-stretching across an entire scene audio block; apply stretching only to individual dialogue utterances.
- **NEVER** deploy an automated movie dub without human-in-the-loop review of character honorifics.
