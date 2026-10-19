# kadirb4rut/video-dubbing-translator

**Verdict:** Lightweight, inspectable local dubbing pipeline uniquely adopting VoxCPM2 for reference voice cloning with optional LatentSync.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | vocal-remover (vendored snapshot) |
| ASR & Alignment | Whisper + WhisperX word-level alignment |
| Translation | Google Translate via deep-translator |
| TTS / Cloning | VoxCPM2 (48 kHz reference-voice cloning) |
| Lip-Sync | LatentSync (optional separate environment, ~18GB VRAM) |
| Audio Mixing | FFmpeg stem remix with duration matching |

## Bengali Readiness
- **Status:** Partial — Whisper & Google Translate handle Bengali; VoxCPM2 multilingual acoustic checkpoint needs testing on Bengali script.

## Timing & Synchronization Approach
Punctuation-based segmentation followed by segment duration adjustment in audio reconstructor.

## Lip-Sync Approach
LatentSync support via separate isolated Python 3.10 environment; high fidelity diffusion lip-sync.

## Strengths Worth Stealing
- Clean isolated wrapper for LatentSync (`scripts/setup_latentsync.py`) and VoxCPM2 adapter (`voxcpm_runtime.py`).

## Weaknesses & Critical Risks
- Google Translate network dependency; punctuation segmentation can split clauses awkwardly.

## License & Project Health
- **License:** MIT; 12 stars, active personal research project.

## Reuse Recommendation
**Copy ideas (LatentSync integration harness and VoxCPM2 48kHz voice conditioning).**

## Confidence & Verification
- **Confidence:** High (verified against Video_Translator.py and README).
