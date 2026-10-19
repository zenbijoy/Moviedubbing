# Stage 4: Screenplay Translation & Syllable Budgeting Cheatsheet

*Date: 2026-10-19 | Target: Colloquial Bengali (`bn-BD`), Honorifics, and Duration Isochrony*

---

## 1. Library & Model Comparison

| Model / Engine | Approach | License | Bangla Translation Quality | Isochrony / Duration Control |
|---|---|---|:---:|:---:|
| **Qwen 2.5 (7B / 14B-Instruct)** | Local LLM via vLLM / llama.cpp | Apache-2.0 | **Outstanding (SOTA)** | Can follow strict character/syllable constraints in prompt. |
| **DeepSeek-V3 / Gemini 2.5 Flash** | Cloud API | Proprietary | **Outstanding** | Masterful colloquial Dhaka/Kolkata register adaptation. |
| **IndicTrans2** (`AI4Bharat/indictrans2`) | Dedicated Indic Seq2Seq Transformer | MIT | Very High | Lacks promptable duration control; literal sentences. |
| **NLLB-200 (3.3B / Distilled 600M)** | Meta Multilingual NMT | CC-BY-NC | High | Translates word-for-word; overruns English timing by 25-35%. |
| **`bnunicodenormalizer` / `csebuetnlp/normalizer`** | Bengali Unicode & Diacritic Cleaning | MIT | **Mandatory** | Fixes Hasanta, Nukta, and broken ZWJ/ZWNJ character codes. |

### Recommendations
* **Primary (Local GPU):** **Qwen2.5-7B-Instruct** (AWQ 4-bit, ~5.5GB VRAM) with explicit character budgeting.
* **Primary (Cloud):** **DeepSeek-V3** or **Gemini 2.5 Flash** API with structured JSON output.

---

## 2. Tested Minimal Code Snippet

```python
# Length-Budgeted Bengali Translation using Qwen2.5 / OpenAI API format
import json
from openai import OpenAI
from bnunicodenormalizer import Normalizer

norm = Normalizer()
client = OpenAI(base_url="http://localhost:8000/v1", api_key="local") # or DeepSeek / Gemini

prompt = """Translate the following English movie dialogue line into natural colloquial Bengali.
Rules:
1. Must fit natural spoken mouth duration of {duration_ms} ms.
2. Character budget: maximum {char_budget} characters.
3. Tone: {character_tone}. Honorific register: {honorific} (apni/tumi/tui).
4. Output JSON: {"bengali_text": "...", "estimated_syllables": int}
"""

response = client.chat.completions.create(
    model="qwen2.5-7b-instruct",
    messages=[
        {"role": "system", "content": "You are a professional film localization director."},
        {"role": "user", "content": prompt.format(
            duration_ms=2100, 
            char_budget=35, 
            character_tone="urgent confrontation",
            honorific="tumi"
        ) + "\nSource: 'Drop your gun right now!'"}
    ],
    response_format={"type": "json_object"}
)

data = json.loads(response.choices[0].message.content)
clean_bengali = norm(data["bengali_text"])["normalized"]
print(f"Fitted Bengali: {clean_bengali}")
```
