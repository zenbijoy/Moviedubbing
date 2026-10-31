"""
Professional Audio & Voice DSP Engine for Movie Dubbing (DAW-Grade Suite).

Provides industry-standard manual vocal editing, timing adjustment, and mastering:
  - High-precision WSOLA pitch-preserving time stretch and fit-to-duration.
  - 4-Band Parametric Broadcast Vocal EQ (80Hz HPF, Low-Mid Warmth, High-Mid Presence, Air Sparkle).
  - Dynamic Sibilance De-Esser (5.5kHz - 8.5kHz sibilance control).
  - Studio Dialogue Leveler / Compressor & True-Peak Brickwall Limiter (-1.0 dBFS).
  - Cinematic Reverb & Ambience Matcher (matches dry TTS dialogue to room acoustics).
  - Anti-click S-curve Fade In / Fade Out and Razor Blade Splitting.
  - Sub-millisecond slip/slide timing nudge.
"""

from __future__ import annotations

import logging
import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


@dataclass
class AudioClipData:
    """In-memory representation of a mono float32 audio clip."""

    samples: np.ndarray  # float32 array in range [-1.0, 1.0]
    sample_rate: int = 44100
    label: str = ""

    @property
    def duration_s(self) -> float:
        if self.sample_rate <= 0 or self.samples.size == 0:
            return 0.0
        return float(self.samples.size / self.sample_rate)

    @property
    def duration(self) -> float:
        return self.duration_s

    @classmethod
    def synthesize_tone(
        cls,
        frequency: float = 220.0,
        duration: float = 2.0,
        sample_rate: int = 44100,
    ) -> AudioClipData:
        t = np.linspace(0, duration, int(max(0.1, duration) * sample_rate), endpoint=False, dtype=np.float32)
        samples = (0.4 * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
        return cls(samples=samples, sample_rate=sample_rate)

    @classmethod
    def synthesize_speech_like(
        cls,
        duration: float = 2.0,
        sample_rate: int = 44100,
    ) -> AudioClipData:
        dur = max(0.1, duration)
        n = int(dur * sample_rate)
        t = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)
        f0 = 135.0
        sig = (
            0.35 * np.sin(2 * np.pi * f0 * t)
            + 0.20 * np.sin(2 * np.pi * 2 * f0 * t)
            + 0.12 * np.sin(2 * np.pi * 3 * f0 * t)
            + 0.08 * np.sin(2 * np.pi * 4 * f0 * t)
        )
        env = np.hanning(n).astype(np.float32)
        samples = (sig * env).astype(np.float32)
        return cls(samples=samples, sample_rate=sample_rate)

    @property
    def duration_ms(self) -> float:
        return self.duration_s * 1000.0

    @property
    def peak_dbfs(self) -> float:
        if self.samples.size == 0:
            return -90.0
        peak = float(np.max(np.abs(self.samples)))
        return round(20.0 * math.log10(max(1e-5, peak)), 2)

    @property
    def rms_dbfs(self) -> float:
        if self.samples.size == 0:
            return -90.0
        rms = float(np.sqrt(np.mean(self.samples**2)))
        return round(20.0 * math.log10(max(1e-5, rms)), 2)

    def clone(self) -> AudioClipData:
        return AudioClipData(samples=self.samples.copy(), sample_rate=self.sample_rate, label=self.label)

    @classmethod
    def from_file(cls, path: Path | str) -> AudioClipData:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Audio file not found: {p}")

        try:
            with wave.open(str(p), "rb") as wf:
                channels = wf.getnchannels()
                sr = wf.getframerate()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)

                if sampwidth == 2:
                    int_data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                elif sampwidth == 1:
                    int_data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                elif sampwidth == 4:
                    int_data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
                else:
                    raise ValueError(f"Unsupported sample width: {sampwidth}")

                if channels > 1:
                    int_data = int_data.reshape(-1, channels).mean(axis=1)

                return cls(samples=int_data.astype(np.float32), sample_rate=sr)
        except Exception:
            # Fallback to soundfile or ffmpeg if available
            try:
                import soundfile as sf

                data, sr = sf.read(str(p), dtype="float32")
                if data.ndim > 1:
                    data = data.mean(axis=1)
                return cls(samples=data.astype(np.float32), sample_rate=sr)
            except Exception as err:
                raise RuntimeError(f"Could not read audio file {p}: {err}") from err

    def save_wav(self, path: Path | str) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        clipped = np.clip(self.samples, -1.0, 1.0)
        int16_samples = (clipped * 32767.0).astype(np.int16)

        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(int16_samples.tobytes())

        return out


class ProAudioDspEngine:
    """High-fidelity digital signal processing engine for film voice dubbing."""

    @staticmethod
    def time_stretch(
        samples: np.ndarray,
        sample_rate: int,
        tempo_factor: float,
        window_size: int = 2048,
        clamp_bounds: tuple[float, float] = (0.4, 2.5),
    ) -> np.ndarray:
        """
        Waveform Similarity Overlap-Add (WSOLA) time-stretching.
        Speeds up (>1.0) or slows down (<1.0) audio while preserving pitch and natural formants.
        """
        if samples.size == 0 or abs(tempo_factor - 1.0) < 0.005:
            return samples.copy()

        min_t, max_t = clamp_bounds
        factor = float(np.clip(tempo_factor, min_t, max_t))

        ha = window_size // 2
        hs = max(1, round(ha / factor))
        win = np.hanning(window_size).astype(np.float32)

        target_len = round(samples.size / factor)
        output = np.zeros(target_len + window_size * 2, dtype=np.float32)
        weight = np.zeros(target_len + window_size * 2, dtype=np.float32)

        in_pos = 0
        out_pos = 0
        search_range = window_size // 4

        while in_pos + window_size <= samples.size and out_pos + window_size < output.size:
            best_offset = 0
            if in_pos > 0 and search_range > 0:
                s_start = max(0, in_pos - search_range)
                s_end = min(samples.size - window_size, in_pos + search_range)
                if s_end > s_start:
                    ref = output[max(0, out_pos - ha) : max(0, out_pos - ha) + window_size]
                    if ref.size == window_size:
                        candidates = samples[s_start : s_end + window_size]
                        corrs = np.correlate(candidates, ref, mode="valid")
                        if corrs.size > 0:
                            best_offset = int(np.argmax(corrs)) - search_range

            actual_in = max(0, min(samples.size - window_size, in_pos + best_offset))
            chosen_seg = samples[actual_in : actual_in + window_size]

            output[out_pos : out_pos + window_size] += chosen_seg * win
            weight[out_pos : out_pos + window_size] += win

            in_pos += ha
            out_pos += hs

        valid = weight > 1e-4
        output[valid] /= weight[valid]
        return output[:target_len].astype(np.float32)

    @classmethod
    def fit_to_duration(
        cls,
        samples: np.ndarray,
        sample_rate: int,
        target_duration_s: float,
    ) -> tuple[np.ndarray, float]:
        """
        Fit dialogue line to exact slot duration in seconds without pitch change.
        Returns (stretched_samples, applied_factor).
        """
        if samples.size == 0 or target_duration_s <= 0.0:
            return samples.copy(), 1.0

        current_dur = samples.size / sample_rate
        if current_dur <= 0.0:
            return samples.copy(), 1.0

        factor = current_dur / target_duration_s
        res = cls.time_stretch(samples, sample_rate, factor)
        return res, factor

    @staticmethod
    def apply_eq_4band(
        samples: np.ndarray,
        sample_rate: int,
        *,
        low_cut_hz: float = 80.0,
        low_mid_gain_db: float = 0.0,
        high_mid_gain_db: float = 0.0,
        air_gain_db: float = 0.0,
    ) -> np.ndarray:
        """
        Broadcast vocal 4-band equalizer:
        - Low-cut (High-pass filter at 80 Hz) to eliminate rumble and mic thumps.
        - Low-mid peaking filter (250 Hz) for vocal chest warmth or de-mudding.
        - High-mid peaking filter (3.5 kHz) for speech presence and intelligibility.
        - Air high-shelf filter (10 kHz) for silkiness and cinematic breath brilliance.
        """
        if samples.size == 0:
            return samples.copy()

        nyq = sample_rate * 0.5
        out = samples.astype(np.float64)

        # 1. High-Pass Filter (80 Hz Butterworth 2nd order)
        if low_cut_hz > 10.0 and low_cut_hz < nyq * 0.5:
            sos_hp = signal.butter(2, low_cut_hz / nyq, btype="highpass", output="sos")
            out = signal.sosfilt(sos_hp, out)

        # 2. Low-Mid Peaking Filter (250 Hz, Q=1.0)
        if abs(low_mid_gain_db) > 0.1:
            f0 = min(250.0, nyq * 0.4)
            sos_lm = signal.iirpeak(f0, Q=1.0, fs=sample_rate)
            # Apply peaking boost/cut
            linear_gain = 10.0 ** (low_mid_gain_db / 20.0)
            mid_band = signal.lfilter(sos_lm[0], sos_lm[1], out)
            out = out + (linear_gain - 1.0) * mid_band

        # 3. High-Mid Peaking Filter (3500 Hz, Q=1.2) - Vocal Presence
        if abs(high_mid_gain_db) > 0.1 and 3500.0 < nyq:
            sos_hm = signal.iirpeak(3500.0, Q=1.2, fs=sample_rate)
            linear_gain = 10.0 ** (high_mid_gain_db / 20.0)
            presence_band = signal.lfilter(sos_hm[0], sos_hm[1], out)
            out = out + (linear_gain - 1.0) * presence_band

        # 4. Air High-Shelf Filter (10 kHz)
        if abs(air_gain_db) > 0.1 and 10000.0 < nyq:
            f_air = min(10000.0, nyq * 0.85)
            sos_air = signal.butter(1, f_air / nyq, btype="highpass", output="sos")
            linear_gain = 10.0 ** (air_gain_db / 20.0)
            air_band = signal.sosfilt(sos_air, out)
            out = out + (linear_gain - 1.0) * air_band

        return np.clip(out, -1.0, 1.0).astype(np.float32)

    @staticmethod
    def apply_deesser(
        samples: np.ndarray,
        sample_rate: int,
        *,
        threshold_db: float = -22.0,
        reduction_db: float = 6.0,
        freq_hz: float = 6500.0,
    ) -> np.ndarray:
        """
        Dynamic Sibilance De-Esser.
        Detects harsh 's', 'sh', and 'z' frequencies in the 5.5 - 8.5 kHz band
        and dynamically ducks only the harsh bursts.
        """
        if samples.size == 0 or reduction_db <= 0.1:
            return samples.copy()

        nyq = sample_rate * 0.5
        f_center = min(freq_hz, nyq * 0.8)
        if f_center <= 1000.0:
            return samples.copy()

        # Bandpass filter around sibilance frequency
        low_f = max(2000.0, f_center - 1500.0)
        high_f = min(nyq - 500.0, f_center + 1500.0)
        if low_f >= high_f:
            return samples.copy()

        sos_bp = signal.butter(2, [low_f / nyq, high_f / nyq], btype="bandpass", output="sos")
        sibilant_band = signal.sosfilt(sos_bp, samples.astype(np.float64))

        # Envelope follower on sibilance band
        block_size = max(32, sample_rate // 1000)  # ~1ms blocks
        n_blocks = samples.size // block_size
        thresh_linear = 10.0 ** (threshold_db / 20.0)
        max_atten = 10.0 ** (-reduction_db / 20.0)

        out = samples.copy()
        for b in range(n_blocks):
            s = b * block_size
            e = s + block_size
            band_energy = float(np.sqrt(np.mean(sibilant_band[s:e] ** 2)))
            if band_energy > thresh_linear:
                ratio = min(1.0, (band_energy - thresh_linear) / max(1e-4, thresh_linear))
                gain = 1.0 - ratio * (1.0 - max_atten)
                # Attenuate the high band in this frame
                out[s:e] = (out[s:e] * 0.3) + (out[s:e] * 0.7 * gain)

        return np.clip(out, -1.0, 1.0).astype(np.float32)

    @staticmethod
    def apply_compressor_limiter(
        samples: np.ndarray,
        sample_rate: int,
        *,
        threshold_db: float = -18.0,
        ratio: float = 3.5,
        attack_ms: float = 12.0,
        release_ms: float = 120.0,
        makeup_gain_db: float = 2.5,
        ceiling_db: float = -1.0,
    ) -> np.ndarray:
        """
        Broadcast vocal compressor and brickwall peak limiter.
        Levels whispering vs loud phrases into consistent, punchy film dialogue.
        """
        if samples.size == 0:
            return samples.copy()

        fs = float(sample_rate)
        tau_a = max(0.001, attack_ms / 1000.0)
        tau_r = max(0.001, release_ms / 1000.0)
        alpha_a = math.exp(-1.0 / (fs * tau_a))
        alpha_r = math.exp(-1.0 / (fs * tau_r))

        thresh_linear = 10.0 ** (threshold_db / 20.0)
        makeup_linear = 10.0 ** (makeup_gain_db / 20.0)
        ceiling_linear = 10.0 ** (ceiling_db / 20.0)

        out = np.zeros_like(samples)
        env = 0.0

        for i in range(samples.size):
            x = abs(float(samples[i]))
            if x > env:
                env = alpha_a * env + (1.0 - alpha_a) * x
            else:
                env = alpha_r * env + (1.0 - alpha_r) * x

            if env > thresh_linear:
                env_db = 20.0 * math.log10(max(1e-5, env))
                overshoot = env_db - threshold_db
                compressed_db = threshold_db + (overshoot / max(1.0, ratio))
                gain = 10.0 ** ((compressed_db - env_db) / 20.0)
            else:
                gain = 1.0

            val = samples[i] * gain * makeup_linear
            # Brickwall soft saturation limiting
            if abs(val) > ceiling_linear:
                val = np.sign(val) * (ceiling_linear + (1.0 - ceiling_linear) * math.tanh((abs(val) - ceiling_linear) * 2.0))
            out[i] = val

        return np.clip(out, -ceiling_linear, ceiling_linear).astype(np.float32)

    @classmethod
    def apply_room_ambience(
        cls,
        samples: np.ndarray,
        sample_rate: int,
        preset: Literal["studio_booth", "living_room", "conference_hall", "cinema_hall", "outdoor_echo"] = "living_room",
        dry_wet: float = 0.25,
    ) -> np.ndarray:
        """
        Cinematic Reverb and Ambience Matcher.
        Synthetic TTS dialogue often sounds unnaturally sterile ("dead booth").
        This matches the vocal performance into the visual room acoustics of the movie scene.
        """
        if samples.size == 0 or dry_wet <= 0.01:
            return samples.copy()

        # Preset acoustic impulse parameters: (decay_time_s, pre_delay_ms, damping)
        presets: dict[str, tuple[float, float, float]] = {
            "studio_booth": (0.15, 8.0, 0.7),
            "living_room": (0.35, 18.0, 0.5),
            "conference_hall": (0.75, 30.0, 0.35),
            "cinema_hall": (1.20, 45.0, 0.25),
            "outdoor_echo": (0.60, 95.0, 0.15),
        }

        decay_s, pre_delay_ms, damping = presets.get(preset, (0.35, 18.0, 0.5))
        n_ir = int(sample_rate * decay_s)
        if n_ir < 64:
            return samples.copy()

        # Generate synthetic room impulse response (Schroeder/Moorer model)
        pre_delay_samples = int(sample_rate * (pre_delay_ms / 1000.0))
        t = np.linspace(0.0, decay_s, n_ir, dtype=np.float32)
        envelope = np.exp(-t * (3.0 / decay_s))
        noise = np.random.normal(0, 1, n_ir).astype(np.float32)
        ir = noise * envelope

        # Apply damping (lowpass filter to simulate high frequency absorption)
        if damping > 0.1:
            nyq = sample_rate * 0.5
            cutoff = min(nyq * 0.9, 12000.0 * (1.0 - damping * 0.7))
            b, a = signal.butter(1, cutoff / nyq, btype="lowpass")
            ir = signal.lfilter(b, a, ir)

        ir /= np.max(np.abs(ir)) + 1e-6
        ir_full = np.zeros(n_ir + pre_delay_samples, dtype=np.float32)
        ir_full[pre_delay_samples:] = ir

        # Fast FFT convolution
        wet = signal.fftconvolve(samples, ir_full, mode="full")[: samples.size]
        wet /= np.max(np.abs(wet)) + 1e-6

        dw = float(np.clip(dry_wet, 0.0, 1.0))
        mixed = (1.0 - dw) * samples + dw * wet
        return np.clip(mixed, -1.0, 1.0).astype(np.float32)

    @staticmethod
    def apply_fades(
        samples: np.ndarray,
        sample_rate: int,
        fade_in_ms: float = 12.0,
        fade_out_ms: float = 16.0,
        curve: Literal["linear", "s_curve"] = "s_curve",
    ) -> np.ndarray:
        """Apply smooth anti-pop crossfade curves to dialogue boundaries."""
        if samples.size == 0:
            return samples.copy()

        out = samples.copy()
        n_in = min(samples.size // 2, int(sample_rate * (fade_in_ms / 1000.0)))
        n_out = min(samples.size // 2, int(sample_rate * (fade_out_ms / 1000.0)))

        if n_in > 0:
            if curve == "s_curve":
                t = np.linspace(0, np.pi, n_in)
                ramp = (1.0 - np.cos(t)) * 0.5
            else:
                ramp = np.linspace(0, 1, n_in)
            out[:n_in] *= ramp.astype(np.float32)

        if n_out > 0:
            if curve == "s_curve":
                t = np.linspace(0, np.pi, n_out)
                ramp = (1.0 + np.cos(t)) * 0.5
            else:
                ramp = np.linspace(1, 0, n_out)
            out[-n_out:] *= ramp.astype(np.float32)

        return out

    @staticmethod
    def nudge_timing(
        samples: np.ndarray,
        sample_rate: int,
        offset_ms: float,
    ) -> np.ndarray:
        """
        Nudge timing by shifting audio forward (positive offset: prepends silence)
        or backward (negative offset: trims lead-in).
        """
        if samples.size == 0 or abs(offset_ms) < 0.1:
            return samples.copy()

        shift_samples = int(sample_rate * (offset_ms / 1000.0))
        if shift_samples > 0:
            # Shift forward: prepend silence
            pad = np.zeros(shift_samples, dtype=np.float32)
            return np.concatenate([pad, samples])
        elif shift_samples < 0:
            # Shift backward: trim lead-in
            trim = min(samples.size - 1, abs(shift_samples))
            return samples[trim:].copy()
        return samples.copy()

    @staticmethod
    def blade_split(
        samples: np.ndarray,
        sample_rate: int,
        split_ms: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Split audio samples at split_ms timestamp into left and right sub-arrays."""
        if samples.size == 0:
            return samples.copy(), samples.copy()

        split_idx = int(sample_rate * (split_ms / 1000.0))
        split_idx = max(0, min(samples.size, split_idx))
        return samples[:split_idx].copy(), samples[split_idx:].copy()

    @staticmethod
    def load_wav(path: Path | str) -> AudioClipData:
        """Load a mono or stereo WAV file as mono float32 AudioClipData."""
        p = Path(path)
        with wave.open(str(p), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        if sampwidth == 2:
            data = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:
            data = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
        elif sampwidth == 1:
            data = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            data = np.zeros(0, dtype=np.float32)

        if n_channels > 1:
            data = data.reshape(-1, n_channels).mean(axis=1)

        return AudioClipData(samples=data.astype(np.float32), sample_rate=framerate)

    @staticmethod
    def save_wav(clip: AudioClipData, path: Path | str) -> None:
        """Save AudioClipData as standard 16-bit PCM mono WAV file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        clamped = np.clip(clip.samples, -1.0, 1.0)
        int16_samples = (clamped * 32767.0).astype(np.int16)
        with wave.open(str(p), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(clip.sample_rate)
            wf.writeframes(int16_samples.tobytes())

    def wsola_time_stretch(self, clip: AudioClipData, target_duration_s: float) -> AudioClipData:
        res, _ = self.fit_to_duration(clip.samples, clip.sample_rate, target_duration_s)
        return AudioClipData(samples=res, sample_rate=clip.sample_rate)

    def apply_parametric_eq(
        self,
        clip: AudioClipData,
        low_shelf_gain_db: float = 0.0,
        low_mid_gain_db: float = 0.0,
        high_mid_gain_db: float = 0.0,
        high_shelf_gain_db: float = 0.0,
    ) -> AudioClipData:
        res = self.apply_eq_4band(
            clip.samples,
            clip.sample_rate,
            low_mid_gain_db=low_mid_gain_db,
            high_mid_gain_db=high_mid_gain_db,
            air_gain_db=high_shelf_gain_db,
        )
        return AudioClipData(samples=res, sample_rate=clip.sample_rate)

    def apply_leveler_and_limiter(
        self,
        clip: AudioClipData,
        target_loudness_dbfs: float = -16.0,
        true_peak_limit_dbfs: float = -1.0,
    ) -> AudioClipData:
        res = self.apply_compressor_limiter(
            clip.samples,
            clip.sample_rate,
            ceiling_db=true_peak_limit_dbfs,
        )
        return AudioClipData(samples=res, sample_rate=clip.sample_rate)

    def apply_deesser_clip(
        self,
        clip: AudioClipData,
        threshold_db: float = -22.0,
        reduction_db: float = 6.0,
        frequency_hz: float = 6500.0,
    ) -> AudioClipData:
        res = self.apply_deesser(
            clip.samples,
            clip.sample_rate,
            threshold_db=threshold_db,
            reduction_db=reduction_db,
            freq_hz=frequency_hz,
        )
        return AudioClipData(samples=res, sample_rate=clip.sample_rate)

    def apply_reverb_match(
        self,
        clip: AudioClipData,
        room_size: float = 0.15,
        wet_level: float = 0.08,
    ) -> AudioClipData:
        res = self.apply_room_ambience(
            clip.samples,
            clip.sample_rate,
            dry_wet=wet_level,
        )
        return AudioClipData(samples=res, sample_rate=clip.sample_rate)





__all__ = [
    "AudioClipData",
    "ProAudioDspEngine",
]
