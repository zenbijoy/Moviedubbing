"""Chatterbox & Bangla Chatterbox TTS Adapter for Zero-Shot Voice Cloning.

Supports both:
1. Remote Kaggle / Cloudflare Tunnel GPU inference (recommended for movie dubbing).
2. Local Chatterbox inference when CUDA / local models are available.
"""

from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from aidub.adapters.voice_base import (
    SynthesisRequest,
    SynthesisResult,
    VoiceEngineError,
    VoiceEngineKind,
)
from aidub.media.ffmpeg_ops import _run, duration

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 24_000


class ChatterboxAdapter:
    """
    Chatterbox Voice Synthesizer with Zero-Shot Voice Cloning for Bengali (Bangla).

    Connects to a remote GPU server (e.g., running on Kaggle with Cloudflare Tunnel)
    or runs local PyTorch inference if available.
    """

    def __init__(
        self,
        server_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        """
        Initialize the adapter.

        Args:
            server_url: Base URL of remote Kaggle / Cloudflare server (e.g. https://xxx.trycloudflare.com).
                        If None, checks KAGGLE_CHATTERBOX_URL or CHATTERBOX_API_URL environment variables.
            timeout: Request timeout in seconds.
        """
        env_url = os.getenv("KAGGLE_CHATTERBOX_URL") or os.getenv("CHATTERBOX_API_URL")
        self.server_url = (server_url or env_url or "").rstrip("/")
        self.timeout = timeout
        self._cached_speakers: set[str] = set()

    @property
    def is_remote(self) -> bool:
        """Check if remote server URL is configured."""
        return bool(self.server_url)

    def check_health(self) -> dict[str, Any]:
        """
        Ping remote server to verify GPU status and model readiness.

        Returns:
            Dict containing status, device, model name, and VRAM info.

        Raises:
            VoiceEngineError: If server is offline or unreachable.
        """
        if not self.server_url:
            raise VoiceEngineError("chatterbox", "No remote server URL configured. Set KAGGLE_CHATTERBOX_URL or pass server_url.")

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.server_url}/health")
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            raise VoiceEngineError(
                "chatterbox",
                f"Failed to connect to Chatterbox server at {self.server_url}: {exc}",
            ) from exc

    def upload_speaker_reference(
        self,
        speaker_id: int | str,
        reference_audio_path: Path | str,
    ) -> bool:
        """
        Upload speaker's reference audio to remote server for voice cloning cache.

        Args:
            speaker_id: Identifier for the speaker (e.g. 0, 1, 'spk_0').
            reference_audio_path: Path to reference WAV clip (3-12s audio).

        Returns:
            True if successfully uploaded or cached.
        """
        spk_str = str(speaker_id)
        if spk_str in self._cached_speakers:
            return True

        if not self.server_url:
            return False

        ref_p = Path(reference_audio_path)
        if not ref_p.is_file():
            logger.warning("Reference audio file does not exist: %s", ref_p)
            return False

        try:
            with httpx.Client(timeout=self.timeout) as client:
                with open(ref_p, "rb") as f:
                    files = {"reference_file": (ref_p.name, f, "audio/wav")}
                    data = {"speaker_id": spk_str}
                    resp = client.post(
                        f"{self.server_url}/upload_reference",
                        data=data,
                        files=files,
                    )
                    resp.raise_for_status()
                    self._cached_speakers.add(spk_str)
                    logger.info("Uploaded reference audio for speaker %s to %s", spk_str, self.server_url)
                    return True
        except Exception as exc:
            logger.warning("Failed to cache speaker reference remotely: %s", exc)
            return False

    def synthesize_to_file(
        self,
        text: str,
        output_wav_path: Path | str,
        reference_audio_path: Path | str | None = None,
        speaker_id: int | str = 0,
        language: str = "bn",
    ) -> Path:
        """
        Synthesize text into speech with voice cloning.

        Args:
            text: Bengali or localized dialogue text to synthesize.
            output_wav_path: Destination path for output WAV file.
            reference_audio_path: Optional reference audio for speaker voice cloning.
            speaker_id: Speaker identifier for reference lookup.
            language: Target language ('bn' for Bangla).

        Returns:
            Path to the output WAV file.
        """
        if not text.strip():
            raise ValueError("Speech text cannot be empty")

        out_p = Path(output_wav_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if self.is_remote:
            return self._synthesize_remote(
                text=text,
                out_p=out_p,
                reference_audio_path=reference_audio_path,
                speaker_id=speaker_id,
                language=language,
            )
        else:
            return self._synthesize_local(
                text=text,
                out_p=out_p,
                reference_audio_path=reference_audio_path,
            )

    def _synthesize_remote(
        self,
        text: str,
        out_p: Path,
        reference_audio_path: Path | str | None,
        speaker_id: int | str,
        language: str,
    ) -> Path:
        """Synthesize via remote Kaggle / Cloudflare REST API."""
        spk_str = str(speaker_id)
        endpoint = f"{self.server_url}/synthesize"

        # Check if we should upload reference audio
        ref_file_to_send = None
        if reference_audio_path and Path(reference_audio_path).is_file():
            ref_path = Path(reference_audio_path)
            # If not yet cached on server, send it along with request
            if spk_str not in self._cached_speakers:
                ref_file_to_send = ref_path

        try:
            with httpx.Client(timeout=self.timeout) as client:
                data = {
                    "text": text,
                    "speaker_id": spk_str,
                    "language": language,
                }
                if ref_file_to_send:
                    with open(ref_file_to_send, "rb") as rf:
                        files = {"reference_audio": (ref_file_to_send.name, rf, "audio/wav")}
                        resp = client.post(endpoint, data=data, files=files)
                else:
                    resp = client.post(endpoint, data=data)

                resp.raise_for_status()

                if len(resp.content) == 0:
                    raise VoiceEngineError("chatterbox", "Remote server returned empty audio response")

                out_p.write_bytes(resp.content)
                if ref_file_to_send:
                    self._cached_speakers.add(spk_str)

                return out_p

        except httpx.HTTPStatusError as exc:
            out_p.unlink(missing_ok=True)
            err_msg = f"Chatterbox remote server returned error HTTP {exc.response.status_code}: {exc.response.text}"
            logger.error(err_msg)
            raise VoiceEngineError("chatterbox", err_msg) from exc
        except Exception as exc:
            out_p.unlink(missing_ok=True)
            err_msg = f"Chatterbox remote synthesis failed connecting to {self.server_url}: {exc}"
            logger.error(err_msg)
            raise VoiceEngineError("chatterbox", err_msg) from exc

    def _synthesize_local(
        self,
        text: str,
        out_p: Path,
        reference_audio_path: Path | str | None,
    ) -> Path:
        """Synthesize via local Chatterbox / BanglaTTS library if available."""
        try:
            # Check for Banglabox / inference package first
            try:
                from infer import BanglaTTS  # type: ignore[import-not-found]
                tts = BanglaTTS()
                ref_arg = str(reference_audio_path) if reference_audio_path else None
                audio_output = tts.synthesize(text, ref_audio=ref_arg)
                # If returns tensor or path, write out
                import torchaudio  # type: ignore[import-not-found]
                torchaudio.save(str(out_p), audio_output, 24_000)
                return out_p
            except (ImportError, ModuleNotFoundError):
                pass

            # Check standard chatterbox package
            from chatterbox.tts import ChatterboxTTS  # type: ignore[import-not-found]
            import torch  # type: ignore[import-not-found]
            import torchaudio  # type: ignore[import-not-found]

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = ChatterboxTTS.from_pretrained(device=device)

            if reference_audio_path and Path(reference_audio_path).exists():
                wav = model.generate(text, audio_prompt_path=str(reference_audio_path))
            else:
                wav = model.generate(text)

            torchaudio.save(str(out_p), wav, model.sr)
            return out_p

        except Exception as exc:
            out_p.unlink(missing_ok=True)
            raise VoiceEngineError(
                "chatterbox",
                "Chatterbox local synthesis failed. To use Bangla Chatterbox with Kaggle GPU, "
                "set the server URL in settings or via KAGGLE_CHATTERBOX_URL.",
            ) from exc


class ChatterboxVoiceEngine:
    """VoiceEngine interface compliance for Chatterbox Zero-Shot Cloning."""

    def __init__(self, adapter: ChatterboxAdapter | None = None) -> None:
        self.adapter = adapter or ChatterboxAdapter()

    @property
    def engine_kind(self) -> VoiceEngineKind:
        return VoiceEngineKind.CHATTERBOX

    def synthesize(self, request: SynthesisRequest, output_dir: str) -> SynthesisResult:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        raw_wav_path = output_root / f"{request.utterance_id}_{request.seed}_raw.wav"
        final_wav_path = output_root / f"{request.utterance_id}_{request.seed}.wav"

        lang = str(request.language).split("-", maxsplit=1)[0].lower()
        ref_path = request.reference_audio_path if request.reference_audio_path else None

        self.adapter.synthesize_to_file(
            text=request.text,
            output_wav_path=raw_wav_path,
            reference_audio_path=ref_path,
            speaker_id=str(request.voice_profile_id),
            language=lang,
        )

        try:
            # Resample / reformat to requested sample rate using ffmpeg
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(raw_wav_path),
                    "-ac",
                    "1",
                    "-ar",
                    str(request.output_sample_rate),
                    str(final_wav_path),
                ]
            )
        finally:
            raw_wav_path.unlink(missing_ok=True)

        return SynthesisResult(
            request_id=request.request_id,
            utterance_id=request.utterance_id,
            engine_kind=self.engine_kind,
            output_path=str(final_wav_path),
            sample_rate=request.output_sample_rate,
            duration_ms=round(duration(final_wav_path) * 1_000),
            seed_used=request.seed,
        )


__all__ = [
    "ChatterboxAdapter",
    "ChatterboxVoiceEngine",
]

