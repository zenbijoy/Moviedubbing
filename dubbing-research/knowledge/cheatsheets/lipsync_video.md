# Stage 7: Lip-Sync & Visual Dubbing Cheatsheet

*Date: 2026-10-19 | Target: Diffusion-grade Visual Lip Alignment under 16GB VRAM*

---

## 1. Library & Model Comparison

| Model / Library | Method | License | Visual Realism | VRAM Required | Gotchas & Artifacts |
|---|---|---|:---:|:---:|---|
| **LatentSync** (`bytedance/LatentSync`) | Audio-conditioned latent diffusion UNet | OpenRAIL++ | **SOTA (Photorealistic)** | ~16–18 GB (requires 16-bit split or Colab) | No blurry box. Natural teeth and tongue motion. *Gotcha:* High VRAM footprint. |
| **Wav2Lip + GFPGAN** | GAN-based mouth inpainting + Face Restoration | Non-commercial | Moderate | ~4.5 GB | Fast, fits easily on 8GB GPUs. *Gotcha:* Teeth can appear blurry without GFPGAN pass. |
| **MuseTalk** (`TMElyralab/MuseTalk`) | Real-time latent face inpainting | MIT | High | ~6.0 GB | Runs at 30+ fps. Good for real-time preview. |
| **SyncNet** | Audio-visual lip synchronization metric (LSE-C / LSE-D) | MIT | Metric only | ~1.0 GB | Objective quality evaluation gate for lip synchronization. |

---

## 2. Tested Minimal Code Snippet

```python
# LatentSync selective close-up invocation
import subprocess

def run_latentsync(video_clip, audio_clip, output_path):
    cmd = [
        "python", "LatentSync/inference.py",
        "--unet_config_path", "LatentSync/configs/unet/second_stage.yaml",
        "--inference_ckpt_path", "checkpoints/latentsync_unet.pt",
        "--video_path", video_clip,
        "--audio_path", audio_clip,
        "--video_out_path", output_path
    ]
    subprocess.run(cmd, check=True)

# Run only if shot detector confirms speaking face close-up
```
