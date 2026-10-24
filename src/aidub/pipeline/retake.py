"""
Production Utterance Retake Service (ADR Script-Supervisor Single-Line Re-Take).

Allows ADR sound editors and translators to re-synthesize and replace a single line
of dialogue instantly (within ~2-4 seconds) without re-running the entire 2-hour movie dubbing pipeline.
Preserves timeline synchronization, recalculates slot fitting, re-assembles vocals,
re-applies dynamic sidechain ducking, and re-muxes the master deliverable.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from aidub.adapters.voice.edge_tts_adapter import EdgeTTSAdapter, default_voice_for_language
from aidub.media.assemble import assemble_timeline, fit_to_slot
from aidub.media.ffmpeg_ops import (
    duration,
    dynamic_sidechain_mix,
    mux,
    probe,
)
from aidub.pipeline.errors import ErrorKind, PipelineError
from aidub.pipeline.manifest import PipelineManifest
from aidub.pipeline.utterance_store import UtteranceStore
from aidub.subtitles.bilingual import write_bilingual_srt, write_srt

logger = logging.getLogger(__name__)


@dataclass
class RetakeResult:
    """Descriptor of the completed single-utterance retake operation."""

    success: bool
    utterance_index: int
    original_text: str
    new_target_text: str
    audio_duration_s: float
    dubbed_vocals_path: str
    dubbed_audio_path: str
    dubbed_video_path: str
    subtitle_path: str
    elapsed_seconds: float


class UtteranceRetakeService:
    """
    Automated NLE Utterance Retake Engine.

    Performs targeted re-synthesis, DSP slot fitting, seamless timeline splicing,
    sidechain mixdown, and deliverable container remuxing for individual dialogue lines.
    """

    def __init__(self, work_dir: Path | str, target_language: str = "bn") -> None:
        self.work_dir = Path(work_dir)
        self.target_language = target_language.replace("-", "_").lower()
        if not self.work_dir.is_dir():
            raise FileNotFoundError(f"Studio work directory not found: {self.work_dir}")

    def retake_utterance(
        self,
        utterance_index: int,
        new_target_text: str,
        *,
        voice_name: str | None = None,
        rate_percent: int = 0,
        pitch_hz: int = 0,
        output_video_path: Path | str | None = None,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> RetakeResult:
        """
        Re-synthesize a single dialogue line and atomically update the project master.

        Args:
            utterance_index: 0-indexed line index to replace.
            new_target_text: Corrected or updated localized text.
            voice_name: Specific TTS voice identifier (defaults to language standard).
            rate_percent: Speaking rate adjustment (-50 to +100).
            pitch_hz: Pitch offset in Hertz (-50 to +50).
            output_video_path: Destination path for remuxed video (or overwrites project output).
            progress_cb: Optional progress callback(percent, message).

        Returns:
            RetakeResult describing all regenerated stems and updated containers.
        """
        start_time = time.perf_counter()
        if not new_target_text or not new_target_text.strip():
            raise PipelineError(
                ErrorKind.USAGE,
                "empty_retake_text",
                "Retake text cannot be empty. Please provide valid dialogue text.",
            )

        if progress_cb:
            progress_cb(5, f"Locating utterance #{utterance_index} in project store...")

        store = UtteranceStore(self.target_language, self.work_dir)
        utterances, meta = store.load_utterances()

        # Fallback to asr_segments.json if store empty
        asr_segments_file = self.work_dir / "asr_segments.json"
        if not utterances and asr_segments_file.is_file():
            with asr_segments_file.open(encoding="utf-8") as f:
                utterances = json.load(f)

        if not utterances:
            raise PipelineError(
                ErrorKind.USAGE,
                "no_utterances_found",
                f"No dialogue utterances found in {self.work_dir}. Run dubbing pipeline first.",
            )

        if utterance_index < 0 or utterance_index >= len(utterances):
            raise PipelineError(
                ErrorKind.USAGE,
                "invalid_utterance_index",
                f"Utterance index {utterance_index} out of bounds (0..{len(utterances) - 1}).",
            )

        target_seg = utterances[utterance_index]
        orig_text = str(target_seg.get("text") or target_seg.get("src", ""))
        seg_start = float(target_seg.get("start", 0.0))
        seg_end = float(target_seg.get("end", seg_start + 1.0))

        # Determine total duration and available slot room
        manifest_file = self.work_dir / "aidub_manifest.json"
        total_dur = 0.0
        origin_video: Path | None = None
        if manifest_file.is_file():
            try:
                with manifest_file.open(encoding="utf-8") as f:
                    mf_data = json.load(f)
                    total_dur = float(mf_data.get("outputs", {}).get("duration_s", 0.0))
                    in_video = mf_data.get("inputs", {}).get("source_video")
                    if in_video and Path(in_video).is_file():
                        origin_video = Path(in_video)
            except Exception:
                pass

        if total_dur <= 0.0:
            total_dur = max(float(u.get("end", 0.0)) for u in utterances) + 1.0

        nxt_s = (
            float(utterances[utterance_index + 1]["start"])
            if (utterance_index + 1) < len(utterances)
            else total_dur
        )
        room_s = max(0.3, nxt_s - seg_start)

        # ------------------------------------------------------------------
        # 1. Synthesize the single replacement take
        # ------------------------------------------------------------------
        if progress_cb:
            progress_cb(25, f"Synthesizing replacement take for #{utterance_index}...")

        eff_voice = voice_name or target_seg.get("voice") or default_voice_for_language(self.target_language)
        tts_engine = EdgeTTSAdapter()
        retake_raw_wav = self.work_dir / f"seg_{utterance_index:03d}_retake_raw.mp3"
        fit_wav_target = self.work_dir / f"seg_{utterance_index:03d}_fit.wav"

        tts_engine.synthesize_to_file(
            text=new_target_text.strip(),
            output_mp3_path=retake_raw_wav,
            voice=eff_voice,
            rate=rate_percent,
            pitch=pitch_hz,
        )

        # ------------------------------------------------------------------
        # 2. Time-fit replacement audio to the editorial slot
        # ------------------------------------------------------------------
        if progress_cb:
            progress_cb(50, "Fitting retake audio into dialogue timeline slot...")

        fitted_wav = fit_to_slot(
            retake_raw_wav,
            room_s,
            fit_wav_target,
            max_stretch=2.0,
        )
        fitted_dur = duration(fitted_wav)

        # ------------------------------------------------------------------
        # 3. Re-assemble dialogue vocal timeline
        # ------------------------------------------------------------------
        if progress_cb:
            progress_cb(65, "Re-assembling broadcast dialogue vocal track...")

        placed_segments: list[tuple[float, Path]] = []
        for i, u in enumerate(utterances):
            u_start = float(u.get("start", 0.0))
            seg_fit = self.work_dir / f"seg_{i:03d}_fit.wav"
            if i == utterance_index:
                placed_segments.append((u_start, fitted_wav))
            elif seg_fit.is_file():
                placed_segments.append((u_start, seg_fit))
            else:
                logger.warning("Segment file missing for #%d: %s", i, seg_fit)

        dub_vocals = self.work_dir / "dubbed_vocals.wav"
        assemble_timeline(placed_segments, total_dur, dub_vocals)

        # ------------------------------------------------------------------
        # 4. Re-mix against background music stems with dynamic ducking
        # ------------------------------------------------------------------
        if progress_cb:
            progress_cb(80, "Mixing dialogue with dynamic sidechain ducking...")

        music_file = self.work_dir / "music.wav"
        final_audio_wav = self.work_dir / "dubbed_audio.wav"
        final_audio_m4a = self.work_dir / "dubbed_audio.m4a"

        if music_file.is_file() and dub_vocals.is_file():
            dynamic_sidechain_mix(dub_vocals, music_file, final_audio_wav)
            dynamic_sidechain_mix(dub_vocals, music_file, final_audio_m4a)
            final_audio = final_audio_wav
        else:
            final_audio = dub_vocals

        # ------------------------------------------------------------------
        # 5. Update metadata stores and bilingual subtitles
        # ------------------------------------------------------------------
        if progress_cb:
            progress_cb(90, "Updating utterance metadata and bilingual subtitles...")

        target_seg["tgt"] = new_target_text.strip()
        target_seg["text"] = orig_text
        target_seg["duration"] = fitted_dur
        target_seg["retake_applied"] = True
        target_seg["retake_timestamp"] = time.time()
        store.save_utterances(utterances, metadata=meta)

        # Write updated SRT files
        sub_cues = []
        for i, u in enumerate(utterances):
            s_val = float(u.get("start", 0.0))
            e_val = float(u.get("end", s_val + 1.0))
            if i == utterance_index:
                e_val = s_val + fitted_dur
            sub_cues.append({
                "start": s_val,
                "end": e_val,
                "src": u.get("text", ""),
                "tgt": u.get("tgt", ""),
            })

        bilingual_srt_path = self.work_dir / "bilingual.srt"
        write_bilingual_srt(sub_cues, bilingual_srt_path)
        mono_srt_path = self.work_dir / f"{self.target_language}.srt"
        write_srt(sub_cues, mono_srt_path, translated=True)

        # ------------------------------------------------------------------
        # 6. Re-mux output video container
        # ------------------------------------------------------------------
        final_video_path = output_video_path or (self.work_dir / f"retake_master_{self.target_language}.mp4")
        final_video_p = Path(final_video_path)

        if origin_video and origin_video.is_file():
            if progress_cb:
                progress_cb(95, "Re-muxing final synchronized video deliverable...")
            mux(origin_video, final_audio, final_video_p)

        elapsed = time.perf_counter() - start_time
        if progress_cb:
            progress_cb(100, f"Retake successfully applied in {elapsed:.1f}s!")

        logger.info(
            "Utterance retake #%d applied in %.2fs: new_text='%s' dur=%.2fs",
            utterance_index,
            elapsed,
            new_target_text,
            fitted_dur,
        )

        return RetakeResult(
            success=True,
            utterance_index=utterance_index,
            original_text=orig_text,
            new_target_text=new_target_text,
            audio_duration_s=fitted_dur,
            dubbed_vocals_path=str(dub_vocals),
            dubbed_audio_path=str(final_audio),
            dubbed_video_path=str(final_video_p) if final_video_p.is_file() else "",
            subtitle_path=str(bilingual_srt_path),
            elapsed_seconds=elapsed,
        )
