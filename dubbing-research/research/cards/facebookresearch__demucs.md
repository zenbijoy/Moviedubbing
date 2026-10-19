# facebookresearch/demucs

**Verdict:** The foundational open-source music and vocal source separation library (Hybrid Demucs / HTDemucs).

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | Hybrid Spectrogram/Waveform Demucs (HTDemucs v4) |
| Outputs | Vocals, Drums, Bass, Other (M&E) |

## Bengali Readiness
- **Status:** Language-agnostic — operates purely on acoustic waveforms.

## Timing & Synchronization Approach
Exact sample-accurate temporal preservation.

## Lip-Sync Approach
N/A.

## Strengths Worth Stealing
- Gold standard for isolating clean vocals while preserving complete background music & sound effects (M&E).

## Weaknesses & Critical Risks
- Repo is archived by Meta; newer Mel-Band Roformer achieves 2-3 dB higher SDR with fewer vocal bleed artifacts.

## License & Project Health
- **License:** MIT; 8.8k+ stars, industry standard.

## Reuse Recommendation
**Use as dependency (baseline separation engine, while evaluating Mel-Band Roformer upgrade).**

## Confidence & Verification
- **Confidence:** Very High (verified from source and architecture).
