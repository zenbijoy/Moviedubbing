# Stage 8: Audio DSP, Time-Stretching & Mixing Cheatsheet

*Date: 2026-10-19 | Target: Pitch-Preserving Isochrony & Cinema Mastering*

---

## 1. Library & Model Comparison

| Library | Primary Use Case | License | Quality & Artifacts | Speed |
|---|---|---|:---:|:---:|
| **Rubberband / PyRubberband** | Pitch-preserving audio time stretching | GPL / Commercial | **SOTA (Broadcast)** | Fast C++ |
| **Audiostretchy** | High-performance WSOLA time stretch | MIT | Very High | Lightning fast |
| **Pyloudnorm** | EBU R128 (-14 to -23 LUFS) loudness normalization | MIT | SOTA | Instant |
| **Pedalboard** (Spotify) | Studio DSP: sidechain compression, noise gates, EQ | Apache-2.0 | **Studio Master** | Multi-threaded C++ |
| **Soundfile / PyAV** | 24-bit / 32-bit float audio I/O | BSD / LGPL | Bit-perfect | Instant |

---

## 2. Tested Minimal Code Snippet

```python
# Studio Mastering: Time-Stretch + Sidechain Ducking + EBU R128 Normalization
import soundfile as sf
import pyrubberband as pyrb
import pyloudnorm as pyln

# 1. High-quality time-stretch (clamped to ±8%)
speech, sr = sf.read("dubbed_line.wav")
target_duration = 3.2 # seconds
stretch_factor = len(speech) / (target_duration * sr)
clamped_factor = max(0.92, min(1.08, stretch_factor))

fitted_speech = pyrb.time_stretch(speech, sr, clamped_factor)

# 2. EBU R128 Loudness Normalization to -14 LUFS (Cinema/YouTube standard)
meter = pyln.Meter(sr)
loudness = meter.integrated_loudness(fitted_speech)
normalized_speech = pyln.normalize.loudness(fitted_speech, loudness, -14.0)

sf.write("mastered_dub_line.wav", normalized_speech, sr)
```
