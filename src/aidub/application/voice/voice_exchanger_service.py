"""
Professional Voice Exchanger & Timbre Morphing Service.

Provides:
  - 1-Click Voice Swap / Re-Cast across single clips, character cohorts, or entire project.
  - Dual-Voice Timbre Morphing & Cross-Synthesis Blending (e.g. 70% Lead + 30% Grit).
  - Independent Pitch Shifting (+/- 12 semitones) and Formant Modification (+/- 500 cents).
  - Voice model catalog spanning Edge-TTS neural models, RVC models, and local engines.
"""

from __future__ import annotations

import logging
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


@dataclass
class VoiceProfileInfo:
    """Descriptor for an available synthetic or cloned character voice."""

    voice_id: str
    display_name: str
    engine: str
    language: str
    gender: str = "neutral"
    age_category: str = "adult"
    timbre_color: str = "#38BDF8"
    description: str = ""
    is_cloned: bool = False
    reference_sample: str = ""


# Curated high-performance voices across languages
CURATED_VOICE_LIBRARY: list[VoiceProfileInfo] = [
    # Bengali Voices
    VoiceProfileInfo(
        voice_id="bn-BD-PradeepNeural",
        display_name="Pradeep (Male Lead / Protagonist)",
        engine="edge_tts",
        language="bn",
        gender="male",
        age_category="adult",
        timbre_color="#3B82F6",
        description="Resonant, heroic baritone for drama lead and action heroes.",
    ),
    VoiceProfileInfo(
        voice_id="bn-BD-NabanitaNeural",
        display_name="Nabanita (Female Lead / Emotional)",
        engine="edge_tts",
        language="bn",
        gender="female",
        age_category="adult",
        timbre_color="#EC4899",
        description="Warm, emotive soprano for cinematic dialogue, crying and romantic scenes.",
    ),
    VoiceProfileInfo(
        voice_id="bn-IN-BashkarNeural",
        display_name="Bashkar (Mature Male / Antagonist)",
        engine="edge_tts",
        language="bn",
        gender="male",
        age_category="senior",
        timbre_color="#F59E0B",
        description="Deep, raspy and authoritative tone suitable for villains and wise elders.",
    ),
    VoiceProfileInfo(
        voice_id="bn-IN-TanishaaNeural",
        display_name="Tanishaa (Youthful Female / Dynamic)",
        engine="edge_tts",
        language="bn",
        gender="female",
        age_category="young",
        timbre_color="#10B981",
        description="Crisp, energetic speech for modern characters and rapid dialogue.",
    ),
    # English Voices
    VoiceProfileInfo(
        voice_id="en-US-GuyNeural",
        display_name="Guy (US Hollywood Hero)",
        engine="edge_tts",
        language="en",
        gender="male",
        age_category="adult",
        timbre_color="#6366F1",
        description="Deep, natural American cinematic dialogue lead.",
    ),
    VoiceProfileInfo(
        voice_id="en-US-JennyNeural",
        display_name="Jenny (US Cinematic Heroine)",
        engine="edge_tts",
        language="en",
        gender="female",
        age_category="adult",
        timbre_color="#F43F5E",
        description="Versatile expressive actress voice with nuanced micro-inflections.",
    ),
    VoiceProfileInfo(
        voice_id="en-GB-RyanNeural",
        display_name="Ryan (British Cultured / Aristocrat)",
        engine="edge_tts",
        language="en",
        gender="male",
        age_category="adult",
        timbre_color="#8B5CF6",
        description="Refined British RP accent, articulate and sophisticated.",
    ),
    # Hindi Voices
    VoiceProfileInfo(
        voice_id="hi-IN-MadhurNeural",
        display_name="Madhur (Hindi Dramatic Lead)",
        engine="edge_tts",
        language="hi",
        gender="male",
        age_category="adult",
        timbre_color="#EAB308",
        description="Passionate Hindi voice suited for action and intense drama.",
    ),
    VoiceProfileInfo(
        voice_id="hi-IN-SwaraNeural",
        display_name="Swara (Hindi Expressive Female)",
        engine="edge_tts",
        language="hi",
        gender="female",
        age_category="adult",
        timbre_color="#06B6D4",
        description="Melodic, warm Hindi timbre with emotional expressiveness.",
    ),
]


class VoiceExchangerService:
    """Handles character voice swapping, morphing, and formant/pitch shifts."""

    def __init__(self, custom_voices: list[VoiceProfileInfo] | None = None) -> None:
        self._library = list(CURATED_VOICE_LIBRARY)
        if custom_voices:
            self._library.extend(custom_voices)

    def list_voices(self, language: str | None = None, gender: str | None = None) -> list[VoiceProfileInfo]:
        results = self._library
        if language:
            clean_lang = language.lower()[:2]
            results = [v for v in results if v.language.lower().startswith(clean_lang)]
        if gender and gender.lower() != "all":
            results = [v for v in results if v.gender.lower() == gender.lower()]
        return results

    def get_voice(self, voice_id: str) -> VoiceProfileInfo | None:
        return next((v for v in self._library if v.voice_id == voice_id), None)

    @staticmethod
    def morph_voice_audio(
        voice_a_path: Path | str,
        voice_b_path: Path | str,
        output_path: Path | str,
        blend_ratio: float = 0.5,  # 0.0 = 100% Voice A, 1.0 = 100% Voice B
    ) -> Path:
        """
        Cross-synthesize two voice takes by blending acoustic spectral envelopes and waveforms.
        Enables creating unique character timbre blends.
        """
        from aidub.media.pro_audio_editor import AudioClipData

        clip_a = AudioClipData.from_file(voice_a_path)
        clip_b = AudioClipData.from_file(voice_b_path)

        ratio = float(np.clip(blend_ratio, 0.0, 1.0))
        target_sr = clip_a.sample_rate

        # Ensure both clips have matching length
        n = min(clip_a.samples.size, clip_b.samples.size)
        if n == 0:
            return Path(voice_a_path)

        sa = clip_a.samples[:n]
        sb = clip_b.samples[:n]

        # Time-domain linear blend with equal-power pan law
        angle = ratio * (math.pi * 0.5)
        gain_a = math.cos(angle)
        gain_b = math.sin(angle)

        blended = (gain_a * sa) + (gain_b * sb)

        # Spectral envelope coloring: blend magnitude spectra
        n_fft = 1024
        hop = 256
        _, _, stft_a = signal.stft(sa, fs=target_sr, nperseg=n_fft, noverlap=n_fft - hop)
        _, _, stft_b = signal.stft(sb, fs=target_sr, nperseg=n_fft, noverlap=n_fft - hop)

        min_cols = min(stft_a.shape[1], stft_b.shape[1])
        stft_a = stft_a[:, :min_cols]
        stft_b = stft_b[:, :min_cols]

        mag_a = np.abs(stft_a)
        mag_b = np.abs(stft_b)
        phase_a = np.angle(stft_a)

        blended_mag = (1.0 - ratio) * mag_a + ratio * mag_b
        blended_stft = blended_mag * np.exp(1j * phase_a)

        _, morph_samples = signal.istft(blended_stft, fs=target_sr, nperseg=n_fft, noverlap=n_fft - hop)
        final_samples = np.clip(morph_samples[:n], -1.0, 1.0).astype(np.float32)

        out_clip = AudioClipData(samples=final_samples, sample_rate=target_sr)
        return out_clip.save_wav(output_path)

    @staticmethod
    def apply_pitch_and_formant(
        input_wav: Path | str,
        output_wav: Path | str,
        pitch_semitones: float = 0.0,
        formant_shift_cents: float = 0.0,
    ) -> Path:
        """
        Apply pitch shift (+/- 12 semitones) and formant filter manipulation (+/- 500 cents).
        Formant shifting modifies vocal tract length (making voice sound younger, older, deeper
        or feminine) without altering playback speed.
        """
        from aidub.media.pro_audio_editor import AudioClipData, ProAudioDspEngine

        clip = AudioClipData.from_file(input_wav)
        samples = clip.samples
        sr = clip.sample_rate

        if samples.size == 0 or (abs(pitch_semitones) < 0.05 and abs(formant_shift_cents) < 5.0):
            shutil.copyfile(input_wav, output_wav)
            return Path(output_wav)

        out = samples.copy()

        # 1. Pitch shift via resample + time stretch compensation
        if abs(pitch_semitones) >= 0.05:
            # Pitch ratio = 2^(semitones / 12)
            pitch_ratio = 2.0 ** (pitch_semitones / 12.0)
            # Resample alters pitch and speed
            resampled_len = int(samples.size / pitch_ratio)
            if resampled_len > 128:
                resampled = signal.resample(samples, resampled_len)
                # WSOLA time stretch back to original length
                out = ProAudioDspEngine.time_stretch(resampled, sr, pitch_ratio)

        # 2. Formant shift via spectral tilt and resonant shelving filter
        if abs(formant_shift_cents) >= 5.0:
            # Formant factor: > 0 shifts resonances higher (youthful/smaller tract),
            # < 0 shifts lower (deep chest, older/larger tract)
            nyq = sr * 0.5
            shift_ratio = 2.0 ** (formant_shift_cents / 1200.0)

            # High formant: boost 3-5 kHz, reduce low end
            if shift_ratio > 1.0:
                boost_freq = min(nyq * 0.8, 3800.0 * shift_ratio)
                b, a = signal.butter(1, min(nyq * 0.9, boost_freq) / nyq, btype="highpass")
                presence = signal.lfilter(b, a, out)
                out = (0.7 * out) + (0.3 * presence)
            else:
                # Deep formant: boost low mid resonance (200 - 600 Hz)
                low_freq = max(80.0, 300.0 * shift_ratio)
                b, a = signal.butter(1, low_freq / nyq, btype="lowpass")
                chest = signal.lfilter(b, a, out)
                out = (0.7 * out) + (0.35 * chest)

        out_clip = AudioClipData(samples=np.clip(out, -1.0, 1.0).astype(np.float32), sample_rate=sr)
        return out_clip.save_wav(output_wav)


__all__ = [
    "CURATED_VOICE_LIBRARY",
    "VoiceExchangerService",
    "VoiceProfileInfo",
]
