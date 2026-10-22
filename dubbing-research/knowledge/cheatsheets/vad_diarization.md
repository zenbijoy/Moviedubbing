# Stage 2: VAD, Speaker Diarization & Active Speaker Detection Cheatsheet

*Date: 2026-10-19 | Target: Multi-Speaker Movie Dialogue & Overlaps*

---

## 1. Library & Model Comparison

| Library / Model | Primary Purpose | License | VRAM / Latency | Movie Overlap Handling | Strengths & Gotchas |
|---|---|---|---|:---:|---|
| **Pyannote.audio 3.1** | Speaker diarization & neural embeddings | MIT (Gated Model) | ~1.5 GB | **High** | Industry benchmark. Explicit overlapping speech detection (`pyannote/segmentation-3.0`). *Gotcha:* Requires Hugging Face user token and gating approval. |
| **Silero-VAD v5** | Voice Activity Detection & speech chunking | MIT | ~100 MB | Moderate | Microsecond CPU/GPU inference. Cleans background music/silence before ASR. |
| **NVIDIA NeMo Diarization** | MSDD (Multi-scale Diarization-Decoder) | Apache-2.0 | ~3.0 GB | **Very High** | Outstanding on cross-talk and overlapping cinema speech. *Gotcha:* Heavy NeMo framework dependencies. |
| **TalkNet-ASD / Light-ASD** | Active Speaker Detection (Video Face + Voice) | MIT / Apache | ~2.0 GB | **High** | Detects which face on screen is actually talking based on lip motion co-occurrence. Solves camera-cut speaker confusion. |
| **WeSpeaker** | Production speaker embedding toolkit | Apache-2.0 | ~500 MB | Moderate | Fast ResNet/CAM++ embeddings for cosine speaker clustering. |

### Recommendations
* **Primary:** **Silero-VAD v5** (pre-filtering) + **Pyannote.audio 3.1** (diarization & overlap detection).
* **Fallback (Visual Film Matching):** **Light-ASD** to bind audio clusters to on-screen face tracks.

---

## 2. Tested Minimal Code Snippet

```python
# Silero-VAD + Pyannote 3.1 Pipeline
import torch
from pyannote.audio import Pipeline

# 1. Silero VAD Speech Segmentation
vad_model, utils = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad")
(get_speech_timestamps, _, read_audio, *_) = utils
wav = read_audio("movie_scene.wav", sampling_rate=16000)
speech_timestamps = get_speech_timestamps(wav, vad_model, sampling_rate=16000)

# 2. Pyannote Diarization (Multi-Speaker with Overlap)
pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1", use_auth_token="HF_TOKEN_HERE"
)
pipeline.to(torch.device("cuda"))

diarization = pipeline("movie_scene.wav", min_speakers=1, max_speakers=8)
for turn, _, speaker in diarization.itertracks(yield_label=True):
    print(f"Speaker {speaker}: {turn.start:.2f}s -> {turn.end:.2f}s")
```
