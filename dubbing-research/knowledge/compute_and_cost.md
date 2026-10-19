# Compute, VRAM Budget & Performance Optimization
**Date:** 2026-10-19 | **Hardware Target: Single 12–16 GB GPU (RTX 3060/4060, T4, V100)**

---

## 1. Realistic VRAM & Runtime per Minute of Film

| Pipeline Stage | Active Model | VRAM Footprint | Processing Time (1 Min Video) | Speedup / Optimization |
| :--- | :--- | :--- | :--- | :--- |
| **1. Vocal Separation** | Mel-Band Roformer (torch.compile) | 4.8 GB | ~18 seconds | Chunking + FP16 |
| **2. VAD & Diarization** | Pyannote 3.1 + Silero-VAD v5 | 2.2 GB | ~8 seconds | ONNX Runtime |
| **3. ASR & Alignment** | Faster-Whisper Large-v3 | 4.6 GB | ~12 seconds | CTranslate2 INT8 |
| **4. Translation** | IndicTrans2 / Qwen2.5-7B (AWQ) | 5.5 GB | ~10 seconds | vLLM 4-bit / CTranslate2 |
| **5. Cloned TTS** | Edge-TTS + RVC v2 (RMVPE) | 3.8 GB | ~15 seconds | Batch inference |
| **6. Audio DSP & Mixing** | Pyloudnorm + PyRubberband | CPU Only | ~3 seconds | Multiprocessing |
| **7. Lip-Sync (Selective)** | LatentSync (Diffusion UNet) | 11.2 GB | ~95 seconds (per 15s face) | Process only speaking close-ups |
| **Total (Excl. Lip-Sync)** | Modular Sequential Paging | **Max $\le 6.0$ GB** | **~66 seconds / min** | Real-time factor: ~1.1x |
| **Total (With Lip-Sync)** | Selective Face Gating | **Max $\le 12.0$ GB** | **~160 seconds / min** | Real-time factor: ~2.6x |

---

## 2. The Golden Rule: Sequential Model Paging

Attempting to keep Roformer, Whisper, Qwen, and LatentSync concurrently in GPU memory requires **>36 GB VRAM** (Immediate CUDA OOM).

### DubForge Sequential Paging Protocol:
```python
import gc
import torch

def unload_stage_model(model):
    del model
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()
```
- **Step 1:** Run Separation across whole film -> write `vocals.wav` and `mne.wav` to disk -> Unload Roformer.
- **Step 2:** Run VAD + ASR -> write `transcript.json` -> Unload Whisper.
- **Step 3:** Run Translation -> write `translated_script.json` -> Unload LLM.
- **Step 4:** Run TTS + RVC -> write `dialogue_stems/` -> Unload RVC.
- **Step 5:** Run Lip-Sync only on tagged close-up shots -> Unload LatentSync.

---

## 3. Resumable Shot-Level Pipeline Architecture
Movies must be processed in discrete scene chunks identified by `PySceneDetect`:
- If an out-of-memory crash occurs on Scene 142 at 1 hour 45 minutes, the pipeline resumes at Scene 142 without re-processing previous scenes.
- State is serialized in a lightweight SQLite or JSON database: `dubbing_manifest.db`.
