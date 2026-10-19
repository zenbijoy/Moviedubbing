# google-marketing-solutions/ariel

**Verdict:** Google's enterprise Cloud Run solution for AI video ad dubbing with SOTA BS-RoFormer separation and Gemini intonation guidance.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| Separation | audio-separator with BS-RoFormer (`model_bs_roformer_ep_317_sdr_12.9755.ckpt`) |
| ASR | Google Speech / Vertex AI |
| Translation | Gemini 2.5 Pro / Flash with custom translation instructions |
| TTS | Google Cloud TTS / Gemini TTS with Voice Intonation Guidance |
| Timeline Editor | Interactive web UI with draggable utterance start/end times and original audio mute toggle |
| Deployment | GCP Cloud Run + Identity-Aware Proxy (IAP) |

## Bengali Readiness
- **Status:** Yes — Gemini Pro/Flash and Google Cloud TTS provide native, studio-grade Bengali (`bn-BD` and `bn-IN`) support.

## Timing & Synchronization Approach
Interactive timeline editor with draggable start/end cues + speed adjustments.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- BS-RoFormer separation integration (significantly superior to standard Demucs), Gemini intonation instructions for TTS, production GCP deployment architecture.

## Weaknesses & Critical Risks
- Requires Google Cloud project and active billing; not local-first.

## License & Project Health
- **License:** Apache-2.0; official Google repo.

## Reuse Recommendation
**Copy ideas (adopt the BS-RoFormer checkpoint and Gemini TTS intonation prompting design).**

## Confidence & Verification
- **Confidence:** Very High (verified from configuration.yaml and README).
