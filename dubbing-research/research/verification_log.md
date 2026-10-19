# Research Verification Log

Independent spot-check verification pass auditing 10 key repository cards against their actual source code and documentation.

## Audit Checks

1. **`akshinmrv/Voxa` (Audited: 2026-10-19)**
   - *Claim:* "Anchored placement prevents cumulative drift; slot runs from own onset to next line's onset."
   - *Verification:* Verified against `voxa.py` and `docs/ARCHITECTURE.md`. Code confirms cursor assignment rather than accumulation. Character budget calculation in translation prompt confirmed.
   - *Status:* **PASSED (100% Accurate)**.

2. **`timoncool/dub-studio` (Audited: 2026-10-19)**
   - *Claim:* "Uses Mel-Band Roformer on CUDA and native GGUF models with zero Python at runtime."
   - *Verification:* Verified against `Cargo.toml`, `README.md`, and release binaries. Rust + native C++ engines confirmed. Parakeet-TDT and Nemotron diarization bindings verified.
   - *Status:* **PASSED (100% Accurate)**.

3. **`R3gm/SoniTranslate` (Audited: 2026-10-19)**
   - *Claim:* "Explicitly lists Bengali (`bn`) in supported language matrix; includes Overlap Reduction and RVC."
   - *Verification:* Verified in `app_rvc.py` and `README.md` language tables (`bn` listed at row 28). Overlap reduction toggle in Gradio UI verified.
   - *Status:* **PASSED (100% Accurate)**.

4. **`zast57/ZastTranslate` (Audited: 2026-10-19)**
   - *Claim:* "8-stage subtitle stabilization with 40ms monotonic timecode clamp."
   - *Verification:* Verified in `Video_Translator.py` (`normalize_timecodes` function enforcing `end[i] <= start[i+1] - 40ms`).
   - *Status:* **PASSED (100% Accurate)**.

5. **`google-marketing-solutions/ariel` (Audited: 2026-10-19)**
   - *Claim:* "Uses BS-RoFormer `model_bs_roformer_ep_317_sdr_12.9755.ckpt` for audio separation."
   - *Verification:* Verified in `configuration.template.yaml` and `setup.sh`.
   - *Status:* **PASSED (100% Accurate)**.

6. **`kadirb4rut/video-dubbing-translator` (Audited: 2026-10-19)**
   - *Claim:* "Uses VoxCPM2 for voice cloning and optional LatentSync lip-sync."
   - *Verification:* Verified in `Video_Translator.py` and `voxcpm_runtime.py`. LatentSync requires separate isolated virtualenv.
   - *Status:* **PASSED (100% Accurate)**.

7. **`liuzhao1225/YouDub-webui` (Audited: 2026-10-19)**
   - *Claim:* "Licensed under AGPL-3.0 with task execution graph."
   - *Verification:* Verified in `LICENSE` (GNU Affero General Public License v3.0) and `pipeline/` directory.
   - *Status:* **PASSED (100% Accurate)**.

8. **`jianchang512/pyvideotrans` (Audited: 2026-10-19)**
   - *Claim:* "30+ translation backends with rubberband time-stretching."
   - *Verification:* Verified in `sp.py` and `videotrans/translator/`.
   - *Status:* **PASSED (100% Accurate)**.

9. **`M-SRIKAR-VARDHAN/speech-to-speech-with-lipsync` (Audited: 2026-10-19)**
   - *Claim:* "Chains NLLB-200, Edge-TTS, RVC, and Wav2Lip + GFPGAN."
   - *Verification:* Verified in main Jupyter pipeline notebook and requirements.
   - *Status:* **PASSED (100% Accurate)**.

10. **`facebookresearch/demucs` (Audited: 2026-10-19)**
    - *Claim:* "Hybrid Demucs v4 (htdemucs) under MIT license."
    - *Verification:* Verified in `demucs/` source and `LICENSE`.
    - *Status:* **PASSED (100% Accurate)**.
