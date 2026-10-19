# Bengali Linguistic Pitfalls in Movie Dubbing
**Date:** 2026-10-19 | **Linguistic Engineering Reference**

---

## 1. The Syllable Expansion Problem (English -> Bengali)
English is a stress-timed language with dense monosyllabic words. Bengali is a syllable-timed language where translated sentences typically expand by **20% to 35% in syllable count**.

- *Example:*
  - English: *"Get out of here right now!"* (7 syllables, ~1.2 seconds)
  - Literal Bengali: *"এখান থেকে এই মুহূর্তেই বের হয়ে যাও!"* (14 syllables, ~2.4 seconds)
  - **The Dubbing Failure:** If synthesized literally, speech overruns the shot boundary or must be sped up by 2.0x, sounding like a chipmunk cartoon.
- **The Solution (Adaptive Idiomatic Condensation):**
  - Dubbing-adapted Bengali: *"এখনই বেরো এখান থেকে!"* (8 syllables, ~1.3 seconds) -> Fits original mouth flaps seamlessly.

---

## 2. Honorific System (T-V Distinction: আপনি / তুমি / তুই)
English uses the universal pronoun "you". In Bengali, choosing the wrong honorific shatters character immersion.

| Level | Pronoun | Typical Movie Relationship | Catastrophic Model Error |
| :--- | :--- | :--- | :--- |
| **Formal (Guru)** | আপনি (Apni) | Police officer to judge, stranger to elder, subordinate to boss. | Using *তুমি* makes character sound insolent. |
| **Familiar (Mitro)** | তুমি (Tumi) | Husband and wife, college classmates, affectionate siblings. | Mixing *আপনি* and *তুমি* within the same scene. |
| **Intimate / Harsh (Heen)** | তুই (Tui) | Childhood buddies, underworld gangsters arguing, parent to toddler. | Using *আপনি* during an intense fistfight. |

**Rule:** Every scene must pass character metadata `[speaker, listener, relationship_level]` to the LLM translation prompt.

---

## 3. G2P, Schwa Deletion and Juktoborno (Complex Conjuncts)
1. **Inherent Schwa (অ - /ɔ/ vs /o/):**
   - The Bengali inherent vowel is often pronounced /o/ instead of /ɔ/ depending on following vowels (Vowel Harmony / স্বরসংগতি).
   - Word-final schwa deletion: 'মন' is /mon/, not /mɔnɔ/.
2. **Juktoborno (যুক্তবর্ণ) Pronunciation Shifts:**
   - **ক্ষ (ক+ষ):** Word-initially pronounced /kʰo/ (e.g., ক্ষমা -> /kʰoma/). Word-medially pronounced /kkʰo/ (e.g., পরীক্ষা -> /porikkʰa/).
   - **জ্ঞ (জ+ঞ):** Pronounced /g̃o/ (e.g., জ্ঞান -> /g̃an/).
   - Off-the-shelf English-Indic TTS engines mispronounce these without HarfBuzz + Bengali G2P normalization.
3. **Bangla Unicode Normalizer:**
   - Always run `bnunicodenormalizer` to resolve interchangeable Unicode sequences (e.g. `র` + `়` vs `ড়`, and decomposed `া` + `ে` vs `ো`).

---

## 4. Subtitle Typography & Line-Length Rules
- **Font Selection:** Use `Noto Sans Bengali` or `SolaimanLipi` with full OpenType feature support (`liga`, `clig`) enabled via `libass`.
- **Character Budget:** Max **32-35 characters per line**, max **2 lines** per subtitle card.
- **Minimum Display Duration:** 1.2 seconds; reading speed calculated at **12-14 characters per second**.
