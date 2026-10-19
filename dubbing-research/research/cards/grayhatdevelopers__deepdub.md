# grayhatdevelopers/deepdub

**Verdict:** Implementation of ICAI 2022 paper on automated dubbing and facial synchronization using deep learning.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| ASR | DeepSpeech / Whisper |
| Translation | MarianMT |
| TTS | Tacotron 2 |
| Lip-Sync | GAN-based lip generator |

## Bengali Readiness
- **Status:** No — Outdated English/Spanish model checkpoints.

## Timing & Synchronization Approach
Phoneme duration matching.

## Lip-Sync Approach
Custom GAN facial generator.

## Strengths Worth Stealing
- Academic paper reference for metric evaluation.

## Weaknesses & Critical Risks
- Outdated legacy models (DeepSpeech, Tacotron2).

## License & Project Health
- **License:** GPL-3.0.

## Reuse Recommendation
**Ignore.**

## Confidence & Verification
- **Confidence:** High.
