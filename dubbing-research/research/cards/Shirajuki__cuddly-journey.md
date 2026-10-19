# Shirajuki/cuddly-journey

**Verdict:** Specialized OCR-driven pipeline translating hardsubs (burned-in subtitles) into softsubs with synchronized TTS dubbing.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| OCR | PaddleOCR hardsub extraction |
| Translation | DeepL / OpenAI |
| TTS | Edge-TTS |
| Mixing | FFmpeg |

## Bengali Readiness
- **Status:** Partial — OCR struggles on complex Bengali conjuncts; Edge-TTS speaks Bengali.

## Timing & Synchronization Approach
Video timestamp matching derived directly from hardsub video frames.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Extracting clean timing cues from videos lacking audio speech clarity using hardsub OCR.

## Weaknesses & Critical Risks
- Niche use case.

## License & Project Health
- **License:** MIT.

## Reuse Recommendation
**Study only.**

## Confidence & Verification
- **Confidence:** High.
