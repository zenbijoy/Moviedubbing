# Voice Quality Benchmarks & Acoustic Measurement Methodology

## 1. Executive Summary & Non-Negotiable Quality Philosophy

In film and television localization, vocal quality cannot be assessed by a single fabricated number. High speaker-embedding similarity does not guarantee natural cadence, and a synthesized voice with pristine mathematical SNR may sound robotic or unnatural in dramatic context.

The MovieDubbing platform enforces an **evidence-based dual evaluation standard**:
1. **Objective Mathematical DSP Metrics**: Measured directly from audio waveforms on disk (Signal-to-Noise Ratio, clipping, true-peak, silence ratio, and spectral power correlation).
2. **Standardized Human Perceptual Benchmarking**: Standardized MUSHRA / MOS protocols covering pronunciation, dramatic naturalness, emotion preservation, and vocal identity consistency.

---

## 2. Mathematical Acoustic Measurement Suite (`voice_dsp.py`)

All acoustic quality measurements in the Audio Quality Lab and Voice Studio are calculated using deterministically verifiable DSP algorithms in [`src/aidub/media/voice_dsp.py`](file:///c:/Users/24030/moviedubbing/Moviedubbing/src/aidub/media/voice_dsp.py):

### 2.1 Signal-to-Noise Ratio (SNR dB) Estimation
Rather than requiring proprietary neural noise estimators, SNR is estimated via **bimodal energy histogram noise floor separation**:
- Audio samples are segmented into $30\text{ms}$ analysis frames with a $15\text{ms}$ hop.
- Frame RMS energy is calculated: $E_i = \sqrt{\frac{1}{N}\sum_{n=1}^N x[n]^2}$.
- Frames below the dynamic noise threshold ($\min(-40\text{ dBFS}, P_{95} - 22\text{ dB})$) are classified as noise floor; frames above are classified as active speech.
- Estimated SNR:
$$\text{SNR}_{\text{est}} = 10 \cdot \log_{10}\left(\frac{\text{Mean}(E_{\text{speech}}^2)}{\text{Mean}(E_{\text{noise}}^2)}\right)$$
- **Suitability Gates**:
  - $\ge 22\text{ dB}$: Excellent for reference conditioning.
  - $15 \dots 22\text{ dB}$: Usable with minor background artifacts.
  - $< 15\text{ dB}$: High background noise warning.

### 2.2 True Peak & Clipping Detection
- Samples normalized to $[-1.0, 1.0]$.
- Clipping counter triggers when $|x[n]| \ge 0.998$ ($> 99.8\%$ full scale).
- A sample is flagged as clipped if more than $0.05\%$ of frames hit digital ceiling.

### 2.3 Silence Ratio
- Evaluates dead pauses where dialogue energy falls below $-42\text{ dBFS}$.
- Samples with silence ratio $> 45\%$ receive an actionable warning advising the operator to trim silence before cloning.

### 2.4 Relative Acoustic Spectral Similarity
To assess whether synthesized speech preserves the acoustic frequency distribution of the reference actor:
- Normalized Power Spectral Density (PSD) vectors are computed via real FFT: $\vec{S}_{\text{ref}}$ and $\vec{S}_{\text{synth}}$.
- Bounded cosine similarity is calculated:
$$\text{Sim}(\vec{S}_{\text{ref}}, \vec{S}_{\text{synth}}) = \frac{\vec{S}_{\text{ref}} \cdot \vec{S}_{\text{synth}}}{\|\vec{S}_{\text{ref}}\| \|\vec{S}_{\text{synth}}\|}$$
- **CRITICAL TRANSPARENCY DISCLAIMER**:
  > [!IMPORTANT]
  > Acoustic spectral cosine similarity evaluates frequency spectrum distribution. It is an objective DSP tool for catching major timbre mismatches; it does NOT substitute for human auditory perception of vocal authenticity.

---

## 3. Repeatable Benchmark Protocols

For studio releases, models are benchmarked across the following 8 standardized dimensions:

```
+---------------------------------------------------------------------------------------+
|                               STANDARDIZED BENCHMARK PROTOCOL                         |
+------------------------------+--------------------+-----------------------------------+
| Metric Dimension             | Measurement Method | Target Studio Threshold           |
+------------------------------+--------------------+-----------------------------------+
| 1. Pronunciation Accuracy    | Human phoneme audit| WER < 4.0%                        |
| 2. Dramatic Naturalness      | 5-point MOS audit  | MOS >= 4.2                        |
| 3. Emotion Preservation      | Blind classification| >= 85% director intent match     |
| 4. Cross-Scene Consistency   | Spectral + MOS     | Spectral Sim >= 0.82              |
| 5. Cross-Lingual Dubbing     | Native speaker test| >= 90% natural syntax             |
| 6. Timing Adaptation Delta   | FFprobe duration   | Delta <= +-50ms of slot           |
| 7. Generation Latency (RTF)  | Real-Time Factor   | RTF < 0.5x (Local) / < 0.25x (API)|
| 8. Host Memory Footprint     | psutil / torch     | <= 6GB VRAM (Single GPU)          |
+------------------------------+--------------------+-----------------------------------+
```

---

## 4. Test Conditions & Confidence Limitations

1. **Hardware Reproducibility**: All local model benchmarks are conducted on standardized GPU testbeds (NVIDIA RTX 3080 10GB / RTX 4070 12GB, CUDA 12.4, Windows 11).
2. **Audio Calibration**: Test clips are normalized to $-1.0\text{ dBFS}$ true peak at $48,000\text{ Hz}$ 24-bit PCM prior to comparison.
3. **No Synthetic Inflation**: Scores must be derived from actual recorded takes. Automated test runners output raw measurement logs to `tests/unit/media/test_voice_dsp.py`.
