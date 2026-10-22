# Stage 9: Subtitles & Bangla Font Shaping Cheatsheet

*Date: 2026-10-19 | Target: Complex Bangla Conjuncts (Juktoborno) in ASS/SRT*

---

## 1. Libraries & Font Shaping Rules

* **Libraries:** `pysubs2` (BSD-3-Clause) for ASS/SRT manipulation, `srt` (MIT).
* **Font Shaping Engine:** `libass` compiled with HarfBuzz and FriBidi.
* **Bangla Fonts:**
  * **Noto Sans Bengali** (Google Open Font License) — Recommended for modern high-DPI screens.
  * **SolaimanLipi** (GPL) — Traditional newspaper/cinema standard font.
  * **Kalpurush** (GPL) — Balanced aesthetic for video subtitles.
* **Gotcha:** Never use standard OpenCV text overlays for Bengali text; OpenCV does not support HarfBuzz complex text shaping, causing broken vowels (*Kar*) and unjoined conjuncts. Always burn subtitles using FFmpeg + `libass`.

---

## 2. Tested Minimal Code Snippet

```python
# Generating Styled Bengali ASS Subtitles with pysubs2
import pysubs2

subs = pysubs2.SSAFile()
style = pysubs2.SSAStyle()
style.fontname = "Noto Sans Bengali"
style.fontsize = 24
style.primarycolor = pysubs2.Color(255, 255, 255)  # White
style.outlinecolor = pysubs2.Color(0, 0, 0)  # Black outline
style.outline = 2
subs.styles["Default"] = style

event = pysubs2.SSAEvent(
    start=pysubs2.make_time(s=1, ms=200),
    end=pysubs2.make_time(s=4, ms=500),
    text="আপনি কি আমাকে শুনতে পাচ্ছেন?",
)
subs.events.append(event)
subs.save("bangla_subtitles.ass")
```
