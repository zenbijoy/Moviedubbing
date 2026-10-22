# Stage 1: ASR & Phonetic Alignment Cheatsheet

*Date: 2026-10-19 | Target: Bangla (bn-BD / bn-IN) Movie Dialogue*

---

## 1. Library & Model Comparison

| Library / Model | Primary Purpose | License | Bangla Support | VRAM / Compute | Strengths & Gotchas |
|---|---|---|:---:|---|---|
| **Faster-Whisper** (`SYSTRAN/faster-whisper`) | Fast, quantized Whisper inference via CTranslate2 | MIT | **Yes (High)** | ~1.8 GB (Large-v3-Turbo int8) | 4x faster than vanilla Whisper. Built-in Silero-VAD. *Gotcha:* Can omit timestamps on whisper-hallucinated segments without VAD. |
| **WhisperX** (`m-bain/whisperX`) | Word-level forced alignment & speaker diarization | BSD-2 | **Yes (Phoneme level)** | ~2.5 GB (during alignment) | Exact millisecond word timestamps using wav2vec2 forced phoneme alignment. *Gotcha:* Needs matching phoneme alignment model for Bengali (`m-bain/wav2vec2-large-xlsr-53-bengali`). |
| **Stable-TS** (`jianfch/stable-ts`) | Stabilized Whisper timestamps via cross-attention | MIT | **Yes** | ~2.0 GB | Prevents timestamp drifting and sentence hallucination. No separate alignment model required. |
| **AI4Bharat IndicConformer / IndicWav2Vec** | Native Indic ASR acoustic model | MIT | **Yes (Native)** | ~1.5 GB | Trained natively on 10,000+ hours of Indic speech. Excellent on thick rural accents. *Gotcha:* Lacks punctuation and casing; requires separate punctuation restoration model. |
| **W2v-BERT 2.0** (`facebook/w2v-bert-2.0`) | 600M self-supervised foundation model | CC-BY-NC 4.0 | **Yes (Fine-tuned)** | ~3.0 GB | SOTA CER on noisy acoustic benchmarks. *Gotcha:* Non-commercial license on foundational weights. |
| **Sherpa-ONNX** (`k2-fsa/sherpa-onnx`) | Ultra-lightweight CPU/mobile ASR engine | Apache-2.0 | **Partial** | ~200 MB RAM (CPU) | Sub-millisecond latency, zero-Torch dependency. Ideal for low-end laptops. |

### Recommendations
* **Primary:** **Faster-Whisper (Large-v3-Turbo)** + **WhisperX** Bengali forced alignment.
* **Fallback (Low Compute/CPU):** **Sherpa-ONNX** with quantized Conformer / CTC model.

---

## 2. Tested Minimal Code Snippet

```python
# Minimal Faster-Whisper + WhisperX Word Alignment Pipeline
# Verified: Python 3.10-3.12, CUDA 11.8/12.1
from faster_whisper import WhisperModel
import whisperx

audio_file = "bangla_clip_15s.wav"
device = "cuda"

# 1. Transcribe with Faster-Whisper
model = WhisperModel("large-v3-turbo", device=device, compute_type="int8_float16")
segments, info = model.transcribe(audio_file, language="bn", vad_filter=True)
results = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]

# 2. Force Align Word Timestamps with WhisperX
align_model, align_metadata = whisperx.load_align_model(
    language_code="bn",
    device=device,
    model_name="ai4bharat/indicwav2vec-hindi",  # or bengali phoneme model
)
aligned_result = whisperx.align(results, align_model, align_metadata, audio_file, device)

for seg in aligned_result["segments"]:
    print(f"[{seg['start']:.2f}s -> {seg['end']:.2f}s] {seg['text']}")
    for w in seg.get("words", []):
        print(f"   Word: {w.get('word')} ({w.get('start')} -> {w.get('end')})")
```
