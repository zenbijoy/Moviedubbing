"""
Kaggle / Remote GPU Server for Bangla Chatterbox Voice Cloning TTS.

Run this script inside a Kaggle Notebook (with GPU accelerator enabled) or Google Colab.
It loads Bangla Chatterbox on GPU (CUDA), spins up a FastAPI inference server,
and creates a free Cloudflare Tunnel so your local Movie Dubbing Studio can connect to it.

How to use in Kaggle:
1. Open a new Kaggle notebook.
2. In Settings -> Accelerator, choose GPU T4 x2 (or P100).
3. Paste and run this script, or run:
   !pip install -q chatterbox-tts fastapi uvicorn pycloudflared python-multipart
   !python kaggle_bangla_chatterbox_server.py
4. Copy the public https://xxxx.trycloudflare.com URL and paste it into Movie Dubbing!
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

# Ensure essential packages are installed
for pkg in ["fastapi", "uvicorn", "pycloudflared", "python-multipart", "nest-asyncio"]:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        print(f"📦 Installing required package: {pkg}...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg], check=True)

try:
    import nest_asyncio
    nest_asyncio.apply()
except Exception:
    pass

import torch
import torchaudio
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

app = FastAPI(title="Bangla Chatterbox GPU Voice Cloning API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
REF_CACHE_DIR = Path("/tmp/chatterbox_speaker_refs")
REF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Global model state
MODEL: Any = None
MODEL_TYPE: str = "none"
MODEL_SR: int = 24_000


def load_bangla_chatterbox() -> None:
    """Initialize Bangla Chatterbox or fallback Chatterbox model onto GPU."""
    global MODEL, MODEL_TYPE, MODEL_SR

    print(f"⚡ Initializing Bangla Chatterbox on device: {DEVICE}")
    if DEVICE == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"🎮 GPU detected: {gpu_name} ({vram_gb:.1f} GB VRAM)")

    # 1. Check if Banglabox/chatterbox-bangla-tts repository exists or clone it
    repo_dir = Path("/kaggle/working/chatterbox-bangla-tts")
    if not repo_dir.exists():
        repo_dir = Path("./chatterbox-bangla-tts")

    if not repo_dir.exists():
        print("📥 Fetching Banglabox/chatterbox-bangla-tts from Hugging Face...")
        try:
            subprocess.run(
                ["git", "clone", "https://huggingface.co/Banglabox/chatterbox-bangla-tts", str(repo_dir)],
                check=False,
                timeout=180,
            )
        except Exception as exc:
            print(f"⚠️ Could not clone Banglabox repo: {exc}")

    # Try loading from cloned Banglabox repo
    if (repo_dir / "inference" / "infer.py").exists() or (repo_dir / "infer.py").exists():
        try:
            sys.path.insert(0, str(repo_dir / "inference"))
            sys.path.insert(0, str(repo_dir))
            from infer import BanglaTTS
            MODEL = BanglaTTS(str(repo_dir))
            MODEL_TYPE = "Banglabox/chatterbox-bangla-tts"
            MODEL_SR = 24_000
            print("✅ Successfully loaded fine-tuned Banglabox/chatterbox-bangla-tts model!")
            return
        except Exception as exc:
            print(f"⚠️ Failed loading Banglabox pipeline: {exc}, falling back to chatterbox-tts...")

    # 2. Try loading standard chatterbox-tts
    try:
        from chatterbox.tts import ChatterboxTTS
        MODEL = ChatterboxTTS.from_pretrained(device=DEVICE)
        MODEL_TYPE = "chatterbox-tts (Zero-Shot)"
        MODEL_SR = getattr(MODEL, "sr", 24_000)
        print("✅ Successfully loaded ChatterboxTTS model!")
        return
    except Exception as exc:
        print(f"⚠️ Failed loading chatterbox-tts: {exc}")

    print("⚠️ Running in mock/fallback mode (models will be loaded on demand)")


@app.on_event("startup")
def startup_event() -> None:
    load_bangla_chatterbox()


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "Bangla Chatterbox GPU Voice Cloning API",
        "status": "online",
        "device": DEVICE,
        "model_type": MODEL_TYPE,
        "docs_url": "/docs",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    vram_free = 0.0
    vram_total = 0.0
    if DEVICE == "cuda":
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        vram_free = round(free_bytes / (1024**3), 2)
        vram_total = round(total_bytes / (1024**3), 2)

    return {
        "status": "ok",
        "model": MODEL_TYPE,
        "device": DEVICE,
        "vram_free_gb": vram_free,
        "vram_total_gb": vram_total,
        "cached_speakers": [p.stem.replace("spk_", "") for p in REF_CACHE_DIR.glob("spk_*.wav")],
    }


@app.post("/upload_reference")
async def upload_reference(
    speaker_id: str = Form(...),
    reference_file: UploadFile = File(...),
) -> dict[str, Any]:
    """Cache a speaker reference audio file on the server for zero-shot cloning."""
    ref_path = REF_CACHE_DIR / f"spk_{speaker_id}.wav"
    content = await reference_file.read()
    ref_path.write_bytes(content)
    print(f"🎙️ Cached reference audio for speaker {speaker_id} ({len(content)} bytes)")
    return {
        "status": "cached",
        "speaker_id": speaker_id,
        "size_bytes": len(content),
    }


def _run_synthesis(
    text: str,
    ref_audio_path: str | None = None,
) -> tuple[torch.Tensor, int]:
    """Run model inference on GPU."""
    global MODEL, MODEL_TYPE, MODEL_SR

    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Text cannot be empty")

    if MODEL is None:
        load_bangla_chatterbox()

    if MODEL_TYPE == "Banglabox/chatterbox-bangla-tts":
        # Banglabox pipeline
        audio = MODEL.synthesize(clean_text, ref_audio=ref_audio_path)
        if isinstance(audio, torch.Tensor):
            return audio, MODEL_SR
        return torch.tensor(audio), MODEL_SR

    elif "chatterbox" in MODEL_TYPE:
        # ResembleAI Chatterbox pipeline
        if ref_audio_path and Path(ref_audio_path).exists():
            wav = MODEL.generate(clean_text, audio_prompt_path=str(ref_audio_path))
        else:
            wav = MODEL.generate(clean_text)
        return wav, MODEL_SR

    else:
        # Synthetic / fallback sine tone for testing environment
        sr = 24_000
        dur_s = max(1.0, len(clean_text) * 0.08)
        t = torch.linspace(0, dur_s, int(sr * dur_s))
        wav = (0.2 * torch.sin(2 * 3.14159 * 220 * t)).unsqueeze(0)
        return wav, sr


@app.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    speaker_id: str = Form("0"),
    language: str = Form("bn"),
    reference_audio: UploadFile | None = File(None),
) -> Response:
    """
    Synthesize Bengali dialogue text with zero-shot voice cloning.

    Returns:
        WAV audio stream (PCM 16-bit).
    """
    temp_ref_path: Path | None = None
    ref_to_use: str | None = None

    try:
        # 1. Determine reference audio: either directly uploaded or cached
        if reference_audio is not None:
            content = await reference_audio.read()
            if len(content) > 0:
                temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                temp_file.write(content)
                temp_file.close()
                temp_ref_path = Path(temp_file.name)
                ref_to_use = str(temp_ref_path)
                # Also cache it for subsequent lines from this speaker
                cached_ref = REF_CACHE_DIR / f"spk_{speaker_id}.wav"
                cached_ref.write_bytes(content)

        if not ref_to_use:
            cached_ref = REF_CACHE_DIR / f"spk_{speaker_id}.wav"
            if cached_ref.exists():
                ref_to_use = str(cached_ref)

        # 2. Run synthesis on GPU
        wav_tensor, sample_rate = _run_synthesis(text, ref_audio_path=ref_to_use)

        if wav_tensor.ndim == 1:
            wav_tensor = wav_tensor.unsqueeze(0)
        if wav_tensor.ndim > 2:
            wav_tensor = wav_tensor.squeeze()

        # 3. Export to in-memory WAV buffer
        buf = io.BytesIO()
        torchaudio.save(buf, wav_tensor.cpu(), sample_rate, format="wav")
        wav_bytes = buf.getvalue()

        return Response(content=wav_bytes, media_type="audio/wav")

    except Exception as exc:
        print(f"❌ Synthesis error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if temp_ref_path and temp_ref_path.exists():
            temp_ref_path.unlink(missing_ok=True)


@app.post("/synthesize_batch")
async def synthesize_batch(
    payload: dict[str, Any],
) -> Response:
    """
    Batch synthesize multiple utterances for rapid movie dubbing.

    Payload format:
    {
      "items": [
        {"id": 0, "text": "...", "speaker_id": "0"},
        {"id": 1, "text": "...", "speaker_id": "1"}
      ]
    }
    Returns:
        ZIP archive containing seg_00000.wav, seg_00001.wav, etc.
    """
    items = payload.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Empty items list")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            idx = item.get("id", 0)
            txt = item.get("text", "")
            spk = str(item.get("speaker_id", "0"))

            ref_path = REF_CACHE_DIR / f"spk_{spk}.wav"
            ref_arg = str(ref_path) if ref_path.exists() else None

            try:
                wav_tensor, sr = _run_synthesis(txt, ref_audio_path=ref_arg)
                if wav_tensor.ndim == 1:
                    wav_tensor = wav_tensor.unsqueeze(0)
                item_buf = io.BytesIO()
                torchaudio.save(item_buf, wav_tensor.cpu(), sr, format="wav")
                zf.writestr(f"seg_{idx:05d}.wav", item_buf.getvalue())
            except Exception as e:
                print(f"⚠️ Error synthesizing batch item {idx}: {e}")

    return Response(
        content=zip_buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=dubbed_batch.zip"},
    )


def start_cloudflare_tunnel(port: int = 8000) -> None:
    """Start free Cloudflare tunnel and print public access URL."""
    try:
        from pycloudflared import try_cloudflare
        time.sleep(2)
        public_url = try_cloudflare(port=port)
        print("\n" + "=" * 65)
        print("🚀 BANGLA CHATTERBOX GPU SERVER IS LIVE!")
        print(f"🌐 Public API URL: {public_url.tunnel}")
        print("=" * 65)
        print("👉 In your local Movie Dubbing Studio, configure:")
        print(f"   KAGGLE_CHATTERBOX_URL = \"{public_url.tunnel}\"")
        print("=" * 65 + "\n")
    except Exception as exc:
        print(f"\n⚠️ Could not automatically start Cloudflare tunnel: {exc}")
        print("You can run 'cloudflared tunnel --url http://127.0.0.1:8000' or use ngrok.\n")


def main() -> None:
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except Exception:
        pass
    port = int(os.environ.get("PORT", "8000"))
    threading.Thread(target=start_cloudflare_tunnel, args=(port,), daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()

