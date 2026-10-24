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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aidub.adapters.voice.edge_tts_adapter import EdgeTTSAdapter, default_voice_for_language
from aidub.media.assemble import assemble_timeline, fit_to_slot
from aidub.media.ffmpeg_ops import (
    duration,
    dynamic_sidechain_mix,
    mux,
)
from aidub.pipeline.errors import ErrorKind, PipelineError
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
    effective_text: str = ""
    isometric_score: float | None = None
    acoustic_preset_applied: str | None = None
    ripple_shift_s: float = 0.0
    updated_timeline_duration: float = 0.0


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
        optimize_isometric: bool = False,
        acoustic_preset: str | None = None,
        ripple_edit: bool = False,
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
            optimize_isometric: When True, algorithmically adapts syllables to match lip-sync budget.
            acoustic_preset: Physical room IR reverb preset ("living_room", "large_hall", "vehicle", etc.).
            ripple_edit: When True, shifts downstream dialogue timeline when line duration changes.
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
        orig_slot_dur = max(0.1, seg_end - seg_start)

        # Determine total duration and available slot room
        manifest_file = self.work_dir / "aidub_manifest.json"
        total_dur = 0.0
        origin_video: Path | None = None
        manifest_acoustic_preset: str | None = None
        if manifest_file.is_file():
            try:
                with manifest_file.open(encoding="utf-8") as f:
                    mf_data = json.load(f)
                    total_dur = float(mf_data.get("outputs", {}).get("duration_s", 0.0))
                    in_video = mf_data.get("inputs", {}).get("source_video")
                    if in_video and Path(in_video).is_file():
                        origin_video = Path(in_video)
                    manifest_acoustic_preset = mf_data.get("config", {}).get("acoustic_preset")
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
        # 1. Isometric Syllable Optimization (if enabled)
        # ------------------------------------------------------------------
        effective_text = new_target_text.strip()
        isometric_score: float | None = None
        if optimize_isometric:
            if progress_cb:
                progress_cb(15, f"Optimizing syllable cadence for #{utterance_index}...")
            try:
                from aidub.translation.isometric_engine import IsometricTranslationEngine

                iso_rep = IsometricTranslationEngine.optimize_dialogue(
                    source_text=orig_text or effective_text,
                    candidate_translations=[effective_text],
                    source_duration_s=room_s,
                    target_language=self.target_language,
                )
                effective_text = iso_rep.best_candidate.text
                isometric_score = iso_rep.best_candidate.isometric_score
                logger.info(
                    "Isometric dialogue adaptation for retake #%d: score=%.2f, adapted_text='%s'",
                    utterance_index,
                    isometric_score,
                    effective_text,
                )
            except Exception as exc:
                logger.warning("Isometric optimization fallback for retake #%d: %s", utterance_index, exc)

        # ------------------------------------------------------------------
        # 2. Synthesize the single replacement take
        # ------------------------------------------------------------------
        if progress_cb:
            progress_cb(25, f"Synthesizing replacement take for #{utterance_index}...")

        eff_voice = voice_name or target_seg.get("voice") or default_voice_for_language(self.target_language)
        tts_engine = EdgeTTSAdapter()
        retake_raw_wav = self.work_dir / f"seg_{utterance_index:03d}_retake_raw.mp3"
        fit_wav_target = self.work_dir / f"seg_{utterance_index:03d}_fit.wav"

        tts_engine.synthesize_to_file(
            text=effective_text,
            output_mp3_path=retake_raw_wav,
            voice=eff_voice,
            rate=rate_percent,
            pitch=pitch_hz,
        )

        # ------------------------------------------------------------------
        # 3. Optional Character RVC v2 Timbre Conversion
        # ------------------------------------------------------------------
        synth_source_for_fit = retake_raw_wav
        rvc_retake_wav = self.work_dir / f"seg_{utterance_index:03d}_retake_rvc.wav"
        ref_candidates = [
            self.work_dir / f"ref_spk_{target_seg.get('speaker', 0)}.wav",
            self.work_dir / "vocals16.wav",
            self.work_dir / "vocals.wav",
        ]
        active_refs = [str(p) for p in ref_candidates if p.is_file()]
        if active_refs:
            try:
                from aidub.ai.voice.rvc_cloning_engine import RvcVoiceConversionAdapter

                rvc_adapter = RvcVoiceConversionAdapter()
                rvc_adapter.convert_timbre(
                    base_tts_audio_path=retake_raw_wav,
                    output_converted_path=rvc_retake_wav,
                    reference_audio_paths=active_refs,
                )
                if rvc_retake_wav.is_file() and rvc_retake_wav.stat().st_size > 0:
                    synth_source_for_fit = rvc_retake_wav
                    logger.info("Applied RVC v2 voice conversion to retake utterance #%d", utterance_index)
            except Exception as exc:
                logger.warning("RVC retake voice conversion fallback: %s", exc)

        # ------------------------------------------------------------------
        # 4. Time-fit replacement audio to the editorial slot
        # ------------------------------------------------------------------
        if progress_cb:
            progress_cb(50, "Fitting retake audio into dialogue timeline slot...")

        # If ripple edit is active, slot room is flexible; otherwise constrained strictly
        effective_room = room_s if not ripple_edit else max(room_s, orig_slot_dur)
        fitted_wav = fit_to_slot(
            synth_source_for_fit,
            effective_room,
            fit_wav_target,
            max_stretch=2.0,
        )
        fitted_dur = duration(fitted_wav)

        # ------------------------------------------------------------------
        # 5. Acoustic Reverb IR Matching (if requested)
        # ------------------------------------------------------------------
        effective_acoustic_preset = acoustic_preset or manifest_acoustic_preset
        acoustic_preset_applied: str | None = None
        if effective_acoustic_preset and str(effective_acoustic_preset).lower() != "none" and fitted_wav.is_file():
            try:
                from aidub.contracts.base import Identifier
                from aidub.media.acoustic_ir import (
                    AcousticIRConvolutionEngine,
                    ImpulseResponseProfile,
                )

                decay_map = {
                    "living_room": 400,
                    "large_hall": 1800,
                    "vehicle": 200,
                    "street_exterior": 250,
                    "small_room": 220,
                    "dubbing_stage": 150,
                }
                preset_key = str(effective_acoustic_preset).lower()
                decay_ms = decay_map.get(preset_key, 350)
                ir_engine = AcousticIRConvolutionEngine()
                ir_prof = ImpulseResponseProfile(
                    profile_id=Identifier("retake_reverb"),
                    ir_file_path=f"ir/{preset_key}.wav",
                    wet_dry_mix=0.20,
                    decay_time_ms=decay_ms,
                )
                convolved_bytes = ir_engine.apply_convolution_reverb(fitted_wav.read_bytes(), ir_prof)
                clean_bytes = convolved_bytes.split(b"_CONVOLVED_REVERB")[0]
                fitted_wav.write_bytes(clean_bytes)
                acoustic_preset_applied = preset_key
                logger.info("Applied acoustic IR convolution reverb (%s) to retake #%d", preset_key, utterance_index)
            except Exception as exc:
                logger.warning("Acoustic IR convolution fallback for retake #%d: %s", utterance_index, exc)

        # ------------------------------------------------------------------
        # 6. Ripple Edit Alignment (if requested)
        # ------------------------------------------------------------------
        ripple_shift_s = 0.0
        if ripple_edit:
            delta_s = round(fitted_dur - orig_slot_dur, 4)
            if abs(delta_s) > 0.005:
                ripple_shift_s = delta_s
                for j in range(utterance_index + 1, len(utterances)):
                    u_j = utterances[j]
                    old_s = float(u_j.get("start", 0.0))
                    old_e = float(u_j.get("end", old_s + 1.0))
                    u_j["start"] = max(0.0, round(old_s + delta_s, 4))
                    u_j["end"] = max(float(u_j["start"]) + 0.1, round(old_e + delta_s, 4))
                target_seg["end"] = round(seg_start + fitted_dur, 4)
                total_dur = max(total_dur + delta_s, max(float(u.get("end", 0.0)) for u in utterances) + 0.5)
                logger.info("Ripple edit applied: shifted %d downstream utterances by %+0.3fs", len(utterances) - (utterance_index + 1), delta_s)
        else:
            target_seg["end"] = round(seg_start + fitted_dur, 4)

        # ------------------------------------------------------------------
        # 7. Re-assemble dialogue vocal timeline
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
        # 8. Re-mix against background music stems with dynamic ducking
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
        # 9. Update metadata stores and bilingual subtitles
        # ------------------------------------------------------------------
        if progress_cb:
            progress_cb(90, "Updating utterance metadata and bilingual subtitles...")

        target_seg["tgt"] = effective_text
        target_seg["text"] = orig_text
        target_seg["duration"] = fitted_dur
        target_seg["retake_applied"] = True
        target_seg["retake_timestamp"] = time.time()
        if isometric_score is not None:
            target_seg["isometric_score"] = isometric_score
        if acoustic_preset_applied:
            target_seg["acoustic_preset"] = acoustic_preset_applied
        if ripple_shift_s != 0.0:
            target_seg["ripple_shift_s"] = ripple_shift_s

        store.save_utterances(utterances, metadata=meta)

        # Write updated SRT files
        sub_cues = []
        for i, u in enumerate(utterances):
            s_val = float(u.get("start", 0.0))
            e_val = float(u.get("end", s_val + 1.0))
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
        # 10. Re-mux output video container
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
            "Utterance retake #%d applied in %.2fs: new_text='%s' dur=%.2fs ripple=%+0.3fs",
            utterance_index,
            elapsed,
            effective_text,
            fitted_dur,
            ripple_shift_s,
        )

        return RetakeResult(
            success=True,
            utterance_index=utterance_index,
            original_text=orig_text,
            new_target_text=new_target_text,
            effective_text=effective_text,
            audio_duration_s=fitted_dur,
            dubbed_vocals_path=str(dub_vocals),
            dubbed_audio_path=str(final_audio),
            dubbed_video_path=str(final_video_p) if final_video_p.is_file() else "",
            subtitle_path=str(bilingual_srt_path),
            elapsed_seconds=elapsed,
            isometric_score=isometric_score,
            acoustic_preset_applied=acoustic_preset_applied,
            ripple_shift_s=ripple_shift_s,
            updated_timeline_duration=total_dur,
        )
