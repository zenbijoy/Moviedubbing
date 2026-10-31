"""Speaker Reference Clip Extractor for Voice Cloning (from dub-studio voices.py)."""

from __future__ import annotations

import logging
from pathlib import Path

from aidub.media.ffmpeg_ops import trim

logger = logging.getLogger(__name__)


def pick_reference(
    segments: list[dict],
    vocals16_path: Path | str,
    work_dir: Path | str,
    ref_windows: dict[int, tuple[float, float]] | None = None,
    max_ref_s: float = 12.0,
) -> dict[int, tuple[Path, str]]:
    """
    Extract per-speaker reference audio clips and matching transcripts for voice cloning.

    Strategy:
    - If ref_windows is provided (from diarization), use the speaker's single longest turn.
    - Otherwise, find the longest ASR segment attributed to that speaker.
    - Trim audio clip to max_ref_s (12.0s max to prevent Qwen3-TTS prompt overflow).
    - Return {speaker_id: (ref_wav_path, ref_text)}.
    """
    w_dir = Path(work_dir)
    w_dir.mkdir(parents=True, exist_ok=True)

    speakers = sorted({int(s.get("speaker", 0)) for s in segments})
    if not speakers:
        speakers = [0]

    ref_map: dict[int, tuple[Path, str]] = {}
    windows = ref_windows or {}

    for spk in speakers:
        spk_segs = [s for s in segments if int(s.get("speaker", 0)) == spk] or segments
        candidate = max(spk_segs, key=lambda s: float(s.get("end", 0)) - float(s.get("start", 0)))

        if spk in windows:
            a, b = windows[spk]
        else:
            a, b = float(candidate.get("start", 0)), float(candidate.get("end", 0))

        ref_wav = w_dir / f"ref_spk_{spk}.wav"
        end_time = min(b, a + max_ref_s)
        trim(vocals16_path, ref_wav, a, end_time)

        ref_text = candidate.get("text", "")
        ref_map[spk] = (ref_wav, ref_text)
        logger.debug("Picked voice ref for speaker %d: %.2fs-%.2fs (text=%r)", spk, a, end_time, ref_text[:30])

    return ref_map


__all__ = ["pick_reference"]
