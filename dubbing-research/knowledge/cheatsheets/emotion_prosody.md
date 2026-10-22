# Stage 6: Emotion & Prosody Transfer Cheatsheet

*Date: 2026-10-19 | Target: Emotional Consistency & Pitch Contour Matching*

---

## 1. Library & Model Comparison

| Library / Tool | Primary Purpose | License | Bangla Readiness | Strengths & Gotchas |
|---|---|---|:---:|---|
| **Emotion2vec+** (`alibaba-damo-academy/emotion2vec`) | Universal speech emotion representation | Apache-2.0 | **Yes (Cross-lingual)** | Extracts frame-level valence, arousal, and discrete emotion categories (anger, grief, joy, fear). |
| **Parselmouth / Praat** | Classical acoustic phonetics (F0, formants, intensity) | GPL-3.0 | Language-agnostic | Pitch contour extraction and jitter/shimmer measurements. |
| **Torchcrepe** (`maxrmorrison/torchcrepe`) | Deep neural pitch (F0) tracker | MIT | Language-agnostic | Differentiable CREPE pitch estimator on GPU; resilient to noisy audio. |
| **SUBESCO** | Bengali Emotional Speech Corpus | Academic / Research | **Native (7,000+ clips)** | Gold standard dataset for training/evaluating Bengali emotion classifiers (20 speakers, 8 emotions). |

---

## 2. Tested Minimal Code Snippet

```python
# Extracting pitch contour (F0) and energy envelope with Parselmouth & PyWorld
import parselmouth
import numpy as np

sound = parselmouth.Sound("source_actor_line.wav")
pitch = sound.to_pitch(time_step=0.01)
f0_values = pitch.selected_array["frequency"]

# Intensity / Energy envelope
intensity = sound.to_intensity(time_step=0.01)
energy = intensity.values[0]

print(f"Mean Pitch: {np.mean(f0_values[f0_values > 0]):.1f} Hz")
print(f"Peak Energy: {np.max(energy):.1f} dB")
```
