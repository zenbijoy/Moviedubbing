# TencentARC/AudioStory

**Verdict:** SOTA research framework by Tencent ARC generating structured, long-form narrative audio, Foley sound effects, and background ambiences.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| LLM Reasoner | Decomposes narrative into temporally ordered audio sub-events |
| Bridging Query | Interleaved semantic tokens for intra-event alignment |
| Acoustic Diffusion | DiT (Diffusion Transformer) continuous denoiser |
| Outputs | Cinematic Foley, natural ambiences, cartoon dubbing effects |

## Bengali Readiness
- **Status:** Language-agnostic for Foley/SFX generation; accepts English textual direction prompts.

## Timing & Synchronization Approach
Strict temporal coherence maintained via LLM consistency queries across scene transitions.

## Lip-Sync Approach
N/A.

## Strengths Worth Stealing
- Allows synthesizing missing cinematic background ambiences and Foley effects when original M&E stems are heavily damaged or muffled.

## Weaknesses & Critical Risks
- Heavy GPU footprint; requires high-end CUDA environment.

## License & Project Health
- **License:** Apache-2.0; released late 2025.

## Reuse Recommendation
**Copy ideas (use for background ambience regeneration when dialogue separation leaves acoustic holes).**

## Confidence & Verification
- **Confidence:** High (verified from AudioStory paper and repo).
