# Amankumar321/AI-Dubber

**Verdict:** Academic pipeline utilizing Microsoft VALL-E X for zero-shot cross-lingual voice cloning from Asian source videos.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| ASR | Whisper |
| Translation | Google Translate |
| TTS / Cloning | VALL-E X |
| Mixing | FFmpeg |

## Bengali Readiness
- **Status:** No — VALL-E X only supports English, Chinese, and Japanese.

## Timing & Synchronization Approach
Acoustic duration predictor from VALL-E X.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Demonstrates VALL-E X cross-lingual acoustic prompting.

## Weaknesses & Critical Risks
- VALL-E X has high hallucination rate and no Bengali support.

## License & Project Health
- **License:** MIT.

## Reuse Recommendation
**Ignore.**

## Confidence & Verification
- **Confidence:** High.
