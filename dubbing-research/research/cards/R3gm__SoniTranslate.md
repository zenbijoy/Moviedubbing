# R3gm/SoniTranslate

**Verdict:** The undisputed open-source reference standard for multilingual video dubbing with Pyannote diarization, RVC, and Overlap Reduction.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| ASR | Whisper / Faster-Whisper / Kotoba-Whisper |
| Diarization | Pyannote.audio 3.1 (up to 12 speakers) |
| Translation | Google Translate / DeepL / OpenAI GPT-4o |
| TTS | Coqui XTTS v2, OpenVoiceV2, Piper TTS, Edge-TTS |
| Voice Conversion | RVC (Retrieval-based Voice Conversion) |
| Audio Processing | Overlap reduction, vocal enhancement before ASR |

## Bengali Readiness
- **Status:** Yes — Bengali (`bn`) is explicitly listed in the main language table for complete transcription, translation, and Edge/OpenVoice synthesis.

## Timing & Synchronization Approach
Whisper word alignment, speaking speed calibration, and silence padding.

## Lip-Sync Approach
Wav2Lip extension optional.

## Strengths Worth Stealing
- RVC voice timber transfer (`app_rvc.py`), overlap reduction algorithm, multi-speaker assignment (12 speakers), active Colab notebook.

## Weaknesses & Critical Risks
- Gradio UI can become sluggish on videos longer than 30 minutes; heavy Conda dependency stack.

## License & Project Health
- **License:** Apache-2.0; 1.4k+ stars, highly maintained.

## Reuse Recommendation
**Use as dependency / Copy ideas (RVC voice conversion adapter and overlap reduction algorithms).**

## Confidence & Verification
- **Confidence:** High (verified from app_rvc.py and language matrix).
