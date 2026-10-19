# Open Questions & Empirical Resolution Protocols
**Date:** 2026-10-19 | **DubForge Technical Uncertainties**

---

### Question 1: LatentSync Generalization on South Asian Facial Features
- **Uncertainty:** LatentSync was predominantly trained on East Asian and Western datasets (LRS2/LRS3/HDTF). Does it introduce visual distortions or facial skin artifacts on South Asian actors with heavy facial hair (beards/mustaches)?
- **Cheapest Test to Resolve:** Run LatentSync inference on a single 10-second close-up clip of a bearded Bengali actor; visually inspect lip contour and facial hair boundaries around the upper lip.

### Question 2: Syllable Budget Tolerance Threshold for Human Believability
- **Uncertainty:** What is the maximum acceptable deviation in syllable count between English source and Bengali dubbed audio before viewers perceive an obvious mismatch?
- **Cheapest Test to Resolve:** Synthesize 5 dialogue lines with length deviations of $\pm 5\%$, $\pm 10\%$, $\pm 15\%$, and $\pm 25\%$; run blind A/B test with 5 native speakers.

### Question 3: IndicF5 Zero-Shot Expressiveness vs Edge-TTS + RVC v2
- **Uncertainty:** Can an emerging flow-matching model (IndicF5) match the acoustic naturalness and pronunciation stability of Edge-TTS + RVC v2 on dramatic movie dialogue?
- **Cheapest Test to Resolve:** Run both pipelines on 3 identical emotional lines from SUBESCO; compare UTMOS scores and phonetic transcription accuracy.
