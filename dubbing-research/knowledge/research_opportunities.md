# Research Opportunities: Low-Resource Bengali Dubbing
**Date:** 2026-10-19 | **8 Concrete Publishable Research Directions**

---

### 1. Isochrony-Constrained Bengali NMT via Syllable-Budgeted Decoding
- **Question:** How can an NMT model or LLM systematically generate Bengali translations that match the exact phonetic syllable length of source English sentences without semantic distortion?
- **Dataset:** Samanantar + FLORES-200 with synthetic syllable duration annotations.
- **Baseline:** Standard IndicTrans2 vs Syllable-Aware Direct Preference Optimization (DPO).
- **Target Venue:** *ACL / EMNLP - Workshop on Low-Resource Translation (LoResMT)*.

### 2. Emotion-Preserved Bengali Zero-Shot Voice Conversion in High-Noise Soundscapes
- **Question:** Can disentangled emotion representations from English speech (via Emotion2Vec+) be mapped directly into Bengali acoustic tokens while isolating foreground speech from explosive background noise?
- **Dataset:** SUBESCO (Bangla emotion) + V2C (Movie dubbing).
- **Baseline:** StyleDubber vs Emotion-conditioned RVC v2.
- **Target Venue:** *Interspeech / ICASSP (Speech Synthesis Track)*.

### 3. Context-Aware Bengali Honorific Disambiguation for Cinematic Dialogue
- **Question:** How to prevent 2nd person pronoun collapse (*you* -> *apni/tumi/tui*) across multi-scene movie dialogue using graph-based character relationship memory?
- **Dataset:** Bengali Movie/Drama Subtitle Corpus (Annotated for social hierarchy).
- **Baseline:** Zero-shot Qwen2.5 vs Character-Graph RAG Prompting.
- **Target Venue:** *Bangla Language Processing (BLP Workshop) / EMNLP*.

### 4. Benchmark Dataset: Multimodal Movie Speech in Conversational Bengali
- **Question:** There is no public benchmark evaluating long-form Bengali movie speech with background music, emotional screaming, overlapping dialogue, and video mouth movements.
- **Deliverable:** 25-hour open-source Bengali cinematic speech benchmark with verified phoneme alignments and actor emotion tags.
- **Target Venue:** *NeurIPS (Datasets and Benchmarks Track)*.

### 5. Cross-Lingual Lip Consonant Alignment: English-to-Bengali Viseme Mapping
- **Question:** How do phonetic differences between English bilabials (/p/, /b/, /m/) and Bengali aspirated stops (/pʰ/, /bʱ/) affect perceptual lip-sync believability?
- **Target Venue:** *ACM Multimedia / CVPR Workshops*.

### 6. Low-Compute Selective Lip-Sync Gating
- **Question:** Can visual active-speaker detection combined with face-pose classification reduce diffusion lip-sync compute by 80% while maintaining viewer immersion?
- **Target Venue:** *IEEE Transactions on Multimedia*.

### 7. Dual-Stage Acoustic Cloning: Edge-TTS G2P Priors + Diffusion Pitch Matching
- **Question:** Does conditioning flow-matching voice conversion on native neural G2P synthesis outperform direct end-to-end multi-lingual diffusion for low-resource phonetics?
- **Target Venue:** *Interspeech*.

### 8. Perceptual Metric for Automated Movie Dubbing Believability (Bengali-DubMOS)
- **Question:** Creating a unified objective metric combining UTMOS (naturalness), SyncNet (visual alignment), and Isochrony delta into a single human-correlated score.
- **Target Venue:** *ICASSP*.
