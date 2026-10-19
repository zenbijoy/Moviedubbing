# zast57/ZastTranslate

**Verdict:** Exceptionally well-engineered 1-click local dubbing suite with state-of-the-art 8-stage subtitle stabilization and VoxCPM 2 cloning.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | Demucs v4 |
| ASR | WhisperX with word-level forced alignment |
| Post-ASR | 8-stage subtitle stabilization (anti-dangling, 40ms monotonic clamp) |
| Translation | Qwen2.5-7B / Qwen3.5-9B / EuroLLM-9B |
| TTS / Cloning | VoxCPM 2 (30 languages, CPS calibration) |
| Audio Mixing | Demucs background stem isolation and remixed voice |

## Bengali Readiness
- **Status:** Partial — WhisperX & Qwen handle Bengali text; VoxCPM2 needs Bengali voice reference benchmarking.

## Timing & Synchronization Approach
Smart Dubbing auto-adjusts text length via prompt and clamps speech speed; strictly prevents subtitle drift via 40ms gaps.

## Lip-Sync Approach
None (explicitly omitted to focus on audio-visual timing stability).

## Strengths Worth Stealing
- 8-stage subtitle stabilization pipeline (`normalize_timecodes`, `merge_sentence_fragments`) and Pinokio 1-click deployment.

## Weaknesses & Critical Risks
- Single-voice per video currently (multi-speaker diarization planned in roadmap).

## License & Project Health
- **License:** MIT / Polyform; 51 stars, very active.

## Reuse Recommendation
**Copy ideas (steal the 8-stage subtitle stabilization logic directly into our pre-translation pipeline).**

## Confidence & Verification
- **Confidence:** High (verified from README and architecture).
