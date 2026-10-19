# Stage 11: Comprehensive Dubbing Evaluation Cheatsheet

*Date: 2026-10-19 | Target: Multimodal Dubbing Metrics Suite*

---

## Evaluation Metric Protocols

| Stage | Metric | Tool / Formula | Benchmark Threshold for GA |
|---|---|---|:---:|
| **ASR Quality** | Word Error Rate (WER) / CER | `jiwer` | WER < 12%, CER < 5% |
| **Translation** | chrF++ / COMET | `sacrebleu` / `unbabel-comet` | chrF++ > 55.0, COMET > 0.82 |
| **TTS Intelligibility** | Synthetic ASR-WER | Back-transcribe via Faster-Whisper | Synthetic WER < 8% |
| **Speaker Similarity** | Cosine Similarity of ECAPA-TDNN | `speechbrain` / `torchaudio` | Cosine Sim > 0.84 |
| **Acoustic Naturalness** | UTMOS / DNSMOS | `UTMOS` neural MOS predictor | MOS > 4.0 / 5.0 |
| **Isochrony Fit** | Duration Delta % | $|T_{target} - T_{orig}| / T_{orig}$ | Delta $\le \pm 5\%$ |
| **Lip-Sync Accuracy** | LSE-C / LSE-D | SyncNet | LSE-C > 6.5, LSE-D < 7.5 |
