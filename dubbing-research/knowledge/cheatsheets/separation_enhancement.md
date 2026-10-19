# Stage 3: Audio Stem Separation & Dialogue Enhancement Cheatsheet

*Date: 2026-10-19 | Target: M&E Preservation & Vocal De-reverberation*

---

## 1. Library & Model Comparison

| Model / Library | Primary Purpose | License | SDR (Vocal Isolation) | VRAM | Strengths & Gotchas |
|---|---|---|:---:|---|---|
| **Mel-Band Roformer** (`model_bs_roformer_ep_317`) | SOTA Music & Vocal Separation | MIT | **12.98 dB (SOTA)** | ~2.5 GB | Zero vocal bleed into background M&E. Preserves subtle orchestral cues. Available in pure ONNX / C++. |
| **Demucs v4 (HTDemucs)** (`facebookresearch/demucs`) | 4-stem separation (vocals, drums, bass, other) | MIT | 10.45 dB | ~3.8 GB | Battle-tested baseline. *Gotcha:* Leaves subtle vocal whisper bleed in loud rock/orchestral passages. |
| **DeepFilterNet 3** (`Rikorose/DeepFilterNet`) | Real-time speech noise suppression & de-reverb | MIT | High | ~200 MB (CPU) | Lightning-fast rust/python engine. Removes room echo and HVAC drone from dialogue stems. |
| **Resemble-Enhance** (`resemble-ai/resemble-enhance`) | Super-resolution vocal enhancement | Apache-2.0 | N/A | ~2.5 GB | Restores high-frequency harmonics (up to 44.1kHz) for muffled dialogue. |

### Recommendations
* **Primary:** **Mel-Band Roformer** (via `audio-separator` / ONNX) for vocal vs. M&E split.
* **Secondary Enhancement:** **DeepFilterNet 3** to remove room acoustic reflections before voice cloning.

---

## 2. Tested Minimal Code Snippet

```python
# Mel-Band Roformer separation using audio-separator
from audio_separator.separator import Separator

separator = Separator(
    output_dir="./stems",
    output_format="WAV",
    model_file_dir="./models/separation"
)

# Load SOTA Mel-Band Roformer checkpoint
separator.load_model(model_filename="model_bs_roformer_ep_317_sdr_12.9755.ckpt")
vocal_file, instrumental_file = separator.separate("movie_scene.wav")
print(f"Isolated Vocals: {vocal_file}")
print(f"Preserved M&E (Music & Effects): {instrumental_file}")
```
