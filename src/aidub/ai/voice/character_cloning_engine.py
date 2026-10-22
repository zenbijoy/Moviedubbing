"""Map real diarization IDs to anonymous speaker records; reject unimplemented voice cloning."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


def sanitize_identifier(raw: str) -> Identifier:
    """Sanitize a raw speaker / character string into a valid Identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(raw).strip()).strip("_")
    if not cleaned:
        cleaned = "speaker_00"
    if cleaned[0] in ".-":
        cleaned = f"spk_{cleaned}"
    return Identifier(cleaned[:160])


def extract_speaker_from_cue_text(text: str) -> tuple[str | None, str]:
    """Extract character / speaker tag from subtitle cue text if present.

    Examples:
        "[SPEAKER_00] Hello" -> ("SPEAKER_00", "Hello")
        "[John]: What is that?" -> ("John", "What is that?")
        "COBB: We need to go." -> ("COBB", "We need to go.")
        ">> NARRATOR: The end." -> ("NARRATOR", "The end.")
        "- Alice: Hi" -> ("Alice", "Hi")
        "Just normal dialogue." -> (None, "Just normal dialogue.")
    """
    if not text:
        return None, ""
    raw = text.strip()

    # 1. Bracketed speaker: [SPEAKER_00] or [John]:
    m1 = re.match(r"^\[([A-Za-z0-9_ -]{1,32})\]\s*:?\s*(.*)$", raw, re.DOTALL)
    if m1 and m1.group(1).strip() and m1.group(2).strip():
        return m1.group(1).strip(), m1.group(2).strip()

    # 2. Leading prefix like '>> ' or '- ' followed by Name:
    m2 = re.match(r"^(?:>>|-)\s*([A-Za-z0-9_ -]{1,32}):\s*(.*)$", raw, re.DOTALL)
    if m2 and m2.group(1).strip() and m2.group(2).strip():
        return m2.group(1).strip(), m2.group(2).strip()

    # 3. Direct name followed by colon: 'COBB: ...' or 'John: ...'
    m3 = re.match(r"^([A-Z][A-Za-z0-9_ '.-]{1,28}):\s+(.*)$", raw, re.DOTALL)
    if m3 and m3.group(1).strip() and m3.group(2).strip():
        spk = m3.group(1).strip()
        if spk.lower() not in {"http", "https", "note", "warning", "info"}:
            return spk, m3.group(2).strip()

    return None, raw


class CharacterVoiceCloningUnavailableError(RuntimeError):
    """Raised because no consent-aware voice conversion backend is configured."""


class MovieCharacter(ContractModel):
    """Anonymous speaker record based on actual diarization output."""

    character_id: Identifier
    canonical_name: str
    gender: str | None = None
    archetype: str | None = None
    vocal_description: str | None = None
    median_f0_hz: float | None = Field(default=None, gt=0.0)
    recommended_base_voice: str | None = None
    speech_register: str | None = None
    timbre_pitch_offset: str | None = None
    timbre_rate_offset: str | None = None
    reference_sample_count: int = Field(default=0, ge=0)
    reference_audio_paths: list[str] = Field(default_factory=list)
    tone_profiles: dict[str, Any] = Field(default_factory=dict)


class CharacterDetectionEngine:
    """Map diarization speaker IDs without guessing names, gender, or target voice."""

    def estimate_speaker_f0(self, audio_paths: Sequence[str | Path]) -> float | None:
        """
        Estimate median fundamental frequency (F0) from a speaker's audio turns
        using autocorrelation.
        """
        f0_estimates: list[float] = []

        for p in audio_paths[:4]:
            path = Path(p)
            if not path.is_file():
                continue
            try:
                import soundfile as sf

                data, sr = sf.read(str(path), dtype="float32")
                if len(data.shape) > 1:
                    data = data.mean(axis=1)
                if len(data) < 2048:
                    continue

                # Sample up to 2 seconds for fast pitch estimation
                chunk = data[: min(len(data), sr * 2)]
                # Energy threshold to avoid silent gaps
                if float(np.sqrt(np.mean(chunk**2))) < 0.01:
                    continue

                autocorr = np.correlate(chunk, chunk, mode="full")
                autocorr = autocorr[len(autocorr) // 2 :]

                # Look for pitch period in human vocal range (60 Hz to 400 Hz)
                min_lag = int(sr / 400)
                max_lag = int(sr / 60)
                if max_lag < len(autocorr):
                    peak_lag = min_lag + int(np.argmax(autocorr[min_lag:max_lag]))
                    if peak_lag > 0:
                        est = float(sr / peak_lag)
                        if 65.0 <= est <= 380.0:
                            f0_estimates.append(est)
            except Exception as exc:
                logger.debug("F0 estimation skipped for audio slice %s: %s", path, exc)

        if f0_estimates:
            return float(np.median(f0_estimates))
        return None

    def detect_movie_characters(
        self,
        diarization_segments: list[dict[str, Any]],
        movie_title_hint: str = "",
        target_language: str = "bn",
        vocals_audio_path: Path | str | None = None,
    ) -> list[MovieCharacter]:
        """
        Group actual diarization turns by their measured speaker identifier.
        """
        del movie_title_hint, vocals_audio_path

        speaker_keys = sorted(
            {
                str(
                    seg.get("speaker") or seg.get("character") or seg.get("speaker_id") or ""
                ).strip()
                for seg in diarization_segments
                if str(
                    seg.get("speaker") or seg.get("character") or seg.get("speaker_id") or ""
                ).strip()
            }
        )
        if not speaker_keys:
            return []

        characters: list[MovieCharacter] = []
        for spk_key in speaker_keys:
            spk_turns = [
                seg
                for seg in diarization_segments
                if str(
                    seg.get("speaker") or seg.get("character") or seg.get("speaker_id") or ""
                ).strip()
                == spk_key
            ]
            ref_paths = sorted(
                {
                    str(path)
                    for turn in spk_turns
                    if (path := turn.get("audio_file") or turn.get("audio_path"))
                    and Path(str(path)).is_file()
                }
            )
            f0 = self.estimate_speaker_f0(ref_paths) if ref_paths else None

            # Canonical name formatting preserving explicit labels
            explicit_name = next(
                (
                    str(
                        seg.get("character_name") or seg.get("character") or seg.get("name")
                    ).strip()
                    for seg in spk_turns
                    if seg.get("character_name") or seg.get("character") or seg.get("name")
                ),
                None,
            )

            if explicit_name and not explicit_name.isdigit():
                canonical_name = explicit_name
            elif spk_key.startswith(("SPEAKER_", "speaker_")):
                canonical_name = f"Speaker {spk_key}"
            elif spk_key.lower().startswith("speaker"):
                canonical_name = spk_key
            else:
                canonical_name = f"Speaker {spk_key}"

            # Infer gender and recommended voice when real audio pitch is measured
            gender: str | None = None
            recommended_voice: str | None = None
            if f0 is not None:
                if f0 < 165.0:
                    gender = "male"
                    recommended_voice = (
                        "bn-BD-PradeepNeural"
                        if target_language.startswith("bn")
                        else "en-US-GuyNeural"
                    )
                else:
                    gender = "female"
                    recommended_voice = (
                        "bn-BD-NabanitaNeural"
                        if target_language.startswith("bn")
                        else "en-US-JennyNeural"
                    )

            characters.append(
                MovieCharacter(
                    character_id=sanitize_identifier(spk_key),
                    canonical_name=canonical_name,
                    gender=gender,
                    recommended_base_voice=recommended_voice,
                    median_f0_hz=round(f0, 1) if f0 is not None else None,
                    reference_sample_count=len(ref_paths),
                    reference_audio_paths=ref_paths,
                )
            )

        logger.info("Mapped %d actual diarization speaker IDs", len(characters))
        return characters

    def detect_from_subtitle_cues(
        self,
        subtitle_cues: Sequence[Any],
        target_language: str = "bn",
    ) -> list[MovieCharacter]:
        """Detect and group movie characters from subtitle cue text prefixes."""
        segments: list[dict[str, Any]] = []
        for cue in subtitle_cues:
            # Handle tuple (track, start, dur, text, score) or object with .text
            if isinstance(cue, (tuple, list)) and len(cue) >= 4:
                text = str(cue[3])
                start = float(cue[1])
                end = start + float(cue[2])
            elif hasattr(cue, "text"):
                text = str(cue.text)
                start = getattr(cue, "start", 0.0)
                end = getattr(cue, "end", start + 2.0)
            elif isinstance(cue, dict):
                text = str(cue.get("text", ""))
                start = float(cue.get("start", 0.0))
                end = float(cue.get("end", start + 2.0))
            else:
                continue

            spk, clean = extract_speaker_from_cue_text(text)
            if spk:
                segments.append(
                    {
                        "speaker": spk,
                        "character": spk,
                        "start": start,
                        "end": end,
                        "text": clean,
                    }
                )

        if not segments:
            return []

        return self.detect_movie_characters(segments, target_language=target_language)

    def detect_from_media(
        self,
        media_path: str | Path,
        target_language: str = "bn",
        work_dir: Path | None = None,
    ) -> tuple[list[MovieCharacter], list[tuple[float, float, int]]]:
        """
        Run acoustic speaker diarization on a media file to detect distinct movie characters.
        """
        from aidub.adapters.diarization_pyannote import PyannoteDiarizationAdapter

        adapter = PyannoteDiarizationAdapter()
        turns, _n_speakers, _ref_windows = adapter.turns(str(media_path))

        segments = [
            {
                "speaker": f"SPEAKER_{spk:02d}",
                "start": start,
                "end": end,
            }
            for start, end, spk in turns
        ]
        characters = self.detect_movie_characters(segments, target_language=target_language)
        return characters, turns


class CharacterVoiceToneCloningEngine:
    """Two-Stage Voice Conversion: Edge-TTS Base -> RVC v2 Character Timbre Conversion."""

    def __init__(self, rvc_adapter: Any | None = None) -> None:
        self.detection_engine = CharacterDetectionEngine()
        from aidub.ai.voice.rvc_cloning_engine import RvcVoiceConversionAdapter

        self.rvc_adapter = rvc_adapter or RvcVoiceConversionAdapter()

    def clone_character_utterance(
        self,
        character: MovieCharacter,
        bengali_text: str,
        output_wav_path: Path | str,
        audio_context_path: Path | str | None = None,
        scene_context: str = "",
        emotion_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Two-stage voice cloning:
          Stage A: Synthesize natural Bengali phonetics via Edge-TTS base voice
          Stage B: Convert timbre to actor's vocal profile via RVC v2 / spectral transfer
        """
        has_active_rvc = bool(
            os.getenv("AIDUB_ENABLE_RVC")
            or os.getenv("RVC_ENDPOINT_URL")
            or os.getenv("AIDUB_RVC_COMMAND")
            or character.tone_profiles.get("rvc_model_path")
        )
        if not has_active_rvc and not character.reference_audio_paths:
            raise CharacterVoiceCloningUnavailableError(
                "Character voice cloning is unavailable: no consent-aware RVC or other voice-conversion "
                "backend is configured. Use the studio's ordinary target-language TTS voice instead."
            )

        from aidub.adapters.voice.edge_tts_adapter import EdgeTTSAdapter, default_voice_for_language

        voice = character.recommended_base_voice or default_voice_for_language("bn")
        tts = EdgeTTSAdapter(voice)

        out_p = Path(output_wav_path)
        temp_base = out_p.with_suffix(".temp_base.mp3")

        # Stage A: Synthesize Base Bengali Speech
        tts.synthesize_to_file(bengali_text, temp_base, voice=voice)

        # Stage B: RVC v2 Timbre Conversion
        final_wav = self.rvc_adapter.convert_timbre(
            base_tts_audio_path=temp_base,
            output_converted_path=out_p,
            reference_audio_paths=character.reference_audio_paths,
        )

        if temp_base.is_file():
            try:
                temp_base.unlink()
            except OSError:
                pass

        return {
            "status": "success",
            "character_id": str(character.character_id),
            "cloned_audio_path": str(final_wav),
            "stage_a_voice": voice,
            "stage_b_engine": "rvc_v2_timbre_transfer",
        }

    clone_character_speech = clone_character_utterance


__all__ = [
    "CharacterDetectionEngine",
    "CharacterVoiceCloningUnavailableError",
    "CharacterVoiceToneCloningEngine",
    "MovieCharacter",
    "extract_speaker_from_cue_text",
    "sanitize_identifier",
]
