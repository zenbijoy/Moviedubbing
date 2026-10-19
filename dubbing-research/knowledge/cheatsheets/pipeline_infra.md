# Stage 10: Pipeline, Quantization & Infra Cheatsheet

*Date: 2026-10-19 | Target: 12–16GB VRAM Zero-OOM Execution*

---

## 1. Libraries & Infrastructure Standards

* **Inference Engines:** **CTranslate2** (for Whisper/NMT), **vLLM / llama.cpp** (for LLM translation), **ONNX Runtime-GPU** (for Separation/VAD).
* **Quantization:** `int8_float16` for speech; `AWQ / GGUF Q4_K_M` for LLMs.
* **Execution Pattern:** **Sequential Process Execution with Cache Eviction**:
  ```python
  import gc, torch
  def cleanup():
      gc.collect()
      if torch.cuda.is_available():
          torch.cuda.empty_cache()
          torch.cuda.ipc_collect()
  ```
* **Orchestration:** `pydantic v2` strict contracts + `uv` virtualenv manager.
