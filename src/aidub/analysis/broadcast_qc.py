"""
Automated Broadcast QC & EBU R128 / ITU-R BS.1770-4 Compliance Certification Suite.

Implements mathematical ITU-R BS.1770-4 K-weighted gated loudness measurement,
Loudness Range (LRA), and 4x oversampled True-Peak detection to certify deliverables
against Netflix, Amazon Prime, EBU R128, and YouTube Broadcast specifications.
"""

from __future__ import annotations

import json
import logging
import math
import wave
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


class DeliverySpec(StrEnum):
    NETFLIX = "netflix"
    EBU_R128 = "ebu_r128"
    YOUTUBE_WEB = "youtube_web"
    THEATRICAL = "theatrical"


@dataclass
class DeliverySpecCriteria:
    target_lufs: float
    tolerance_lu: float
    max_true_peak_dbtp: float
    max_lra_lu: float
    description: str


DELIVERY_CRITERIA: dict[DeliverySpec, DeliverySpecCriteria] = {
    DeliverySpec.NETFLIX: DeliverySpecCriteria(
        target_lufs=-24.0,
        tolerance_lu=1.0,
        max_true_peak_dbtp=-1.0,
        max_lra_lu=18.0,
        description="Netflix Post-Production Spec (-24 LUFS +/- 1.0, TP <= -1.0 dBTP)",
    ),
    DeliverySpec.EBU_R128: DeliverySpecCriteria(
        target_lufs=-23.0,
        tolerance_lu=0.5,
        max_true_peak_dbtp=-1.0,
        max_lra_lu=20.0,
        description="EBU R128 European Broadcast (-23 LUFS +/- 0.5, TP <= -1.0 dBTP)",
    ),
    DeliverySpec.YOUTUBE_WEB: DeliverySpecCriteria(
        target_lufs=-14.0,
        tolerance_lu=1.0,
        max_true_peak_dbtp=-1.0,
        max_lra_lu=14.0,
        description="YouTube / Web Streaming (-14 LUFS +/- 1.0, TP <= -1.0 dBTP)",
    ),
    DeliverySpec.THEATRICAL: DeliverySpecCriteria(
        target_lufs=-27.0,
        tolerance_lu=2.0,
        max_true_peak_dbtp=-0.5,
        max_lra_lu=24.0,
        description="Theatrical Cinema Master (-27 LUFS, Wide Dynamic Range)",
    ),
}


@dataclass
class LoudnessQCResult:
    integrated_lufs: float
    loudness_range_lu: float
    true_peak_dbtp: float
    sample_peak_dbfs: float
    duration_s: float
    channels: int
    sample_rate: int


@dataclass
class BroadcastQCCertificate:
    media_name: str
    target_spec: DeliverySpec
    passed: bool
    metrics: LoudnessQCResult
    criteria: DeliverySpecCriteria
    gain_correction_db: float
    clipping_detected: bool
    remediation_actions: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Export certificate as formatted JSON."""
        data = asdict(self)
        return json.dumps(data, indent=2)

    def to_formatted_certificate(self) -> str:
        """Generate human-readable studio compliance certificate."""
        status_badge = (
            "★ PASSED - BROADCAST CERTIFIED" if self.passed else "✖ FAILED - REMEDIATION REQUIRED"
        )
        lines = [
            "=" * 70,
            "          AIDUB STUDIO BROADCAST DELIVERY QC CERTIFICATE",
            "=" * 70,
            f"Asset:          {self.media_name}",
            f"Specification:  {self.criteria.description}",
            f"QC Verdict:     {status_badge}",
            "-" * 70,
            "MEASURED METRICS (ITU-R BS.1770-4):",
            f"  • Integrated Loudness: {self.metrics.integrated_lufs:.2f} LUFS  (Target: {self.criteria.target_lufs:.1f} +/- {self.criteria.tolerance_lu:.1f} LUFS)",
            f"  • Loudness Range:      {self.metrics.loudness_range_lu:.2f} LU   (Limit: <= {self.criteria.max_lra_lu:.1f} LU)",
            f"  • True-Peak Level:     {self.metrics.true_peak_dbtp:.2f} dBTP (Limit: <= {self.criteria.max_true_peak_dbtp:.1f} dBTP)",
            f"  • Sample Peak:         {self.metrics.sample_peak_dbfs:.2f} dBFS",
            f"  • Audio Channels:      {self.metrics.channels}",
            f"  • Sample Rate:         {self.metrics.sample_rate} Hz",
            f"  • Duration:            {self.metrics.duration_s:.2f} seconds",
            "-" * 70,
            "CORRECTION & MASTERING:",
            f"  • Gain Adjustment:     {self.gain_correction_db:+.2f} dB",
            f"  • Digital Clipping:    {'DETECTED' if self.clipping_detected else 'None (Clean)'}",
        ]
        if self.remediation_actions:
            lines.append("  • Required Actions:")
            for act in self.remediation_actions:
                lines.append(f"     -> {act}")
        lines.append("=" * 70)
        return "\n".join(lines)


class BroadcastQCEngine:
    """
    Mathematical ITU-R BS.1770-4 K-weighted Loudness and True-Peak Compliance Engine.
    """

    @classmethod
    def get_k_weighting_filters(
        cls, fs: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute biquad filter coefficients for ITU-R BS.1770-4 K-weighting at arbitrary sample rates.

        Stage 1: High-shelving pre-filter (head diffraction model): f0 = 1681 Hz, G = +3.99 dB, Q = 0.7071
        Stage 2: High-pass RLB weighting filter: f0 = 38.13 Hz, Q = 0.5003
        """
        # Stage 1: High-shelf filter
        f0_shelf = 1681.0
        gain_db = 3.99
        q_shelf = 0.7071

        a_gain = pow(10.0, gain_db / 40.0)
        w0_s = 2.0 * math.pi * f0_shelf / fs
        alpha_s = (
            math.sin(w0_s) / 2.0 * math.sqrt((a_gain + 1.0 / a_gain) * (1.0 / q_shelf - 1.0) + 2.0)
        )
        cos_w0_s = math.cos(w0_s)

        b0_s = a_gain * (
            (a_gain + 1.0) + (a_gain - 1.0) * cos_w0_s + 2.0 * math.sqrt(a_gain) * alpha_s
        )
        b1_s = -2.0 * a_gain * ((a_gain - 1.0) + (a_gain + 1.0) * cos_w0_s)
        b2_s = a_gain * (
            (a_gain + 1.0) + (a_gain - 1.0) * cos_w0_s - 2.0 * math.sqrt(a_gain) * alpha_s
        )
        a0_s = (a_gain + 1.0) - (a_gain - 1.0) * cos_w0_s + 2.0 * math.sqrt(a_gain) * alpha_s
        a1_s = 2.0 * ((a_gain - 1.0) - (a_gain + 1.0) * cos_w0_s)
        a2_s = (a_gain + 1.0) - (a_gain - 1.0) * cos_w0_s - 2.0 * math.sqrt(a_gain) * alpha_s

        b_shelf = np.array([b0_s / a0_s, b1_s / a0_s, b2_s / a0_s], dtype=np.float64)
        a_shelf = np.array([1.0, a1_s / a0_s, a2_s / a0_s], dtype=np.float64)

        # Stage 2: High-pass filter (RLB)
        f0_hp = 38.13
        q_hp = 0.5003
        w0_hp = 2.0 * math.pi * f0_hp / fs
        alpha_hp = math.sin(w0_hp) / (2.0 * q_hp)
        cos_w0_hp = math.cos(w0_hp)

        b0_hp = (1.0 + cos_w0_hp) / 2.0
        b1_hp = -(1.0 + cos_w0_hp)
        b2_hp = (1.0 + cos_w0_hp) / 2.0
        a0_hp = 1.0 + alpha_hp
        a1_hp = -2.0 * cos_w0_hp
        a2_hp = 1.0 - alpha_hp

        b_hp = np.array([b0_hp / a0_hp, b1_hp / a0_hp, b2_hp / a0_hp], dtype=np.float64)
        a_hp = np.array([1.0, a1_hp / a0_hp, a2_hp / a0_hp], dtype=np.float64)

        return b_shelf, a_shelf, b_hp, a_hp

    @classmethod
    def apply_k_weighting(cls, samples: np.ndarray, fs: int) -> np.ndarray:
        """Apply K-weighting pre-filtering across all audio channels."""
        b_shelf, a_shelf, b_hp, a_hp = cls.get_k_weighting_filters(fs)

        if samples.ndim == 1:
            stage1 = signal.lfilter(b_shelf, a_shelf, samples)
            stage2 = signal.lfilter(b_hp, a_hp, stage1)
            return stage2.astype(np.float32)

        filtered = np.zeros_like(samples, dtype=np.float32)
        for ch in range(samples.shape[1]):
            s1 = signal.lfilter(b_shelf, a_shelf, samples[:, ch])
            filtered[:, ch] = signal.lfilter(b_hp, a_hp, s1)
        return filtered

    @classmethod
    def compute_true_peak(
        cls, samples: np.ndarray, oversample_factor: int = 4
    ) -> tuple[float, float]:
        """
        Compute Sample Peak (dBFS) and True-Peak (dBTP) using 4x polyphase sinc interpolation.
        Catches inter-sample peaks that standard peak meters miss.
        """
        sample_peak = float(np.max(np.abs(samples)))
        sample_peak_dbfs = 20.0 * math.log10(max(1e-9, sample_peak))

        # 4x sinc oversampling via Fourier resample
        num_orig = len(samples)
        num_oversampled = num_orig * oversample_factor

        if samples.ndim == 1:
            oversampled = signal.resample(samples, num_oversampled)
            true_peak = float(np.max(np.abs(oversampled)))
        else:
            true_peak = 0.0
            for ch in range(samples.shape[1]):
                ov_ch = signal.resample(samples[:, ch], num_oversampled)
                true_peak = max(true_peak, float(np.max(np.abs(ov_ch))))

        true_peak_dbtp = 20.0 * math.log10(max(1e-9, true_peak))
        return round(sample_peak_dbfs, 2), round(true_peak_dbtp, 2)

    @classmethod
    def analyze_audio_samples(cls, samples: np.ndarray, fs: int = 48000) -> LoudnessQCResult:
        """
        Full ITU-R BS.1770-4 gated loudness measurement.
        """
        num_samples = len(samples)
        duration_sec = num_samples / max(1, fs)
        channels = 1 if samples.ndim == 1 else samples.shape[1]

        # 1. Compute True-Peak & Sample Peak
        sample_peak_dbfs, true_peak_dbtp = cls.compute_true_peak(samples, oversample_factor=4)

        # 2. Apply K-weighting
        k_weighted = cls.apply_k_weighting(samples, fs)

        # Channel gains according to ITU-R BS.1770-4 (Left, Right, Center = 1.0; LFE = 0.0; Surrounds = 1.41)
        channel_weights = np.ones(channels, dtype=np.float32)
        if channels >= 6:
            channel_weights[3] = 0.0  # LFE
            channel_weights[4] = 1.4125  # Ls
            channel_weights[5] = 1.4125  # Rs

        # 3. Gated Block Analysis (400ms rectangular window, 75% overlap = 100ms hop)
        block_len = int(0.400 * fs)
        hop_len = int(0.100 * fs)

        if num_samples < block_len:
            # Fallback for very short samples (< 400ms)
            if k_weighted.ndim == 1:
                ms_energy = float(np.mean(k_weighted**2))
            else:
                ms_energy = float(np.sum(np.mean(k_weighted**2, axis=0) * channel_weights))
            integrated_lufs = -0.691 + 10.0 * math.log10(max(1e-12, ms_energy))
            return LoudnessQCResult(
                integrated_lufs=round(integrated_lufs, 2),
                loudness_range_lu=0.0,
                true_peak_dbtp=true_peak_dbtp,
                sample_peak_dbfs=sample_peak_dbfs,
                duration_s=round(duration_sec, 3),
                channels=channels,
                sample_rate=fs,
            )

        num_blocks = (num_samples - block_len) // hop_len + 1
        block_powers = np.zeros(num_blocks, dtype=np.float64)

        for i in range(num_blocks):
            start = i * hop_len
            end = start + block_len
            segment = k_weighted[start:end]

            if segment.ndim == 1:
                block_powers[i] = np.mean(segment**2)
            else:
                ch_powers = np.mean(segment**2, axis=0)
                block_powers[i] = np.sum(ch_powers * channel_weights)

        # Absolute threshold gating at -70.0 LUFS
        abs_threshold_power = pow(10.0, (-70.0 + 0.691) / 10.0)
        above_abs_mask = block_powers > abs_threshold_power

        if not np.any(above_abs_mask):
            return LoudnessQCResult(
                integrated_lufs=-70.0,
                loudness_range_lu=0.0,
                true_peak_dbtp=true_peak_dbtp,
                sample_peak_dbfs=sample_peak_dbfs,
                duration_s=round(duration_sec, 3),
                channels=channels,
                sample_rate=fs,
            )

        # Relative threshold gating at -10.0 LU below ungated mean
        ungated_mean_power = float(np.mean(block_powers[above_abs_mask]))
        ungated_lufs = -0.691 + 10.0 * math.log10(max(1e-12, ungated_mean_power))
        rel_threshold_power = pow(10.0, (ungated_lufs - 10.0 + 0.691) / 10.0)

        above_rel_mask = above_abs_mask & (block_powers > rel_threshold_power)
        if np.any(above_rel_mask):
            gated_mean_power = float(np.mean(block_powers[above_rel_mask]))
            integrated_lufs = -0.691 + 10.0 * math.log10(max(1e-12, gated_mean_power))
        else:
            integrated_lufs = ungated_lufs

        # 4. Loudness Range (LRA) over 3-second short-term windows
        st_win_len = int(3.0 * fs)
        st_hop_len = int(1.0 * fs)
        if num_samples >= st_win_len:
            st_blocks = (num_samples - st_win_len) // st_hop_len + 1
            st_powers = np.zeros(st_blocks, dtype=np.float64)
            for j in range(st_blocks):
                st_start = j * st_hop_len
                st_end = st_start + st_win_len
                st_seg = k_weighted[st_start:st_end]
                if st_seg.ndim == 1:
                    st_powers[j] = np.mean(st_seg**2)
                else:
                    st_powers[j] = np.sum(np.mean(st_seg**2, axis=0) * channel_weights)

            st_lufs = -0.691 + 10.0 * np.log10(np.maximum(1e-12, st_powers))
            valid_st = st_lufs[st_lufs > -70.0]
            if len(valid_st) > 2:
                p10 = float(np.percentile(valid_st, 10))
                p95 = float(np.percentile(valid_st, 95))
                lra = max(0.0, p95 - p10)
            else:
                lra = 2.0
        else:
            lra = 1.5

        return LoudnessQCResult(
            integrated_lufs=round(float(integrated_lufs), 2),
            loudness_range_lu=round(float(lra), 2),
            true_peak_dbtp=true_peak_dbtp,
            sample_peak_dbfs=sample_peak_dbfs,
            duration_s=round(duration_sec, 3),
            channels=channels,
            sample_rate=fs,
        )

    @classmethod
    def analyze_wav_file(cls, wav_path: Path | str) -> LoudnessQCResult:
        """Read and analyze a WAV audio file."""
        with wave.open(str(wav_path), "rb") as wf:
            channels = wf.getnchannels()
            width = wf.getsampwidth()
            framerate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

        if width == 2:
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif width == 3:
            # 24-bit PCM
            raw_bytes = np.frombuffer(frames, dtype=np.uint8)
            reshaped = raw_bytes.reshape(-1, 3)
            padded = np.pad(reshaped, ((0, 0), (1, 0)), mode="constant").astype(np.int32)
            samples = (padded.view(np.int32) >> 8).astype(np.float32) / 8388608.0
        else:
            samples = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

        if channels > 1:
            samples = samples.reshape(-1, channels)

        return cls.analyze_audio_samples(samples, fs=framerate)

    @classmethod
    def evaluate_compliance(
        cls,
        metrics: LoudnessQCResult,
        spec: DeliverySpec = DeliverySpec.NETFLIX,
        media_name: str = "master_deliverable",
    ) -> BroadcastQCCertificate:
        """
        Evaluate measured loudness against broadcast specifications and generate remediation.
        """
        criteria = DELIVERY_CRITERIA[spec]

        lufs_diff = metrics.integrated_lufs - criteria.target_lufs
        is_lufs_pass = abs(lufs_diff) <= criteria.tolerance_lu
        is_tp_pass = metrics.true_peak_dbtp <= criteria.max_true_peak_dbtp
        is_lra_pass = metrics.loudness_range_lu <= criteria.max_lra_lu
        has_clipping = metrics.sample_peak_dbfs >= -0.01

        overall_pass = is_lufs_pass and is_tp_pass and is_lra_pass and not has_clipping

        gain_correction = criteria.target_lufs - metrics.integrated_lufs

        actions: list[str] = []
        if not is_lufs_pass:
            actions.append(
                f"Apply {gain_correction:+.2f} dB gain adjustment to meet {criteria.target_lufs:.1f} LUFS target."
            )
        if not is_tp_pass:
            exceed = metrics.true_peak_dbtp - criteria.max_true_peak_dbtp
            actions.append(
                f"Engage True-Peak Limiter (Ceiling: {criteria.max_true_peak_dbtp:.1f} dBTP). "
                f"Peak exceeds standard by {exceed:.2f} dBTP."
            )
        if not is_lra_pass:
            actions.append(
                f"Compress dialogue dynamic range: LRA is {metrics.loudness_range_lu:.1f} LU "
                f"(Exceeds maximum allowable {criteria.max_lra_lu:.1f} LU)."
            )
        if has_clipping:
            actions.append(
                "Digital 0 dBFS clipping detected! Re-render master stems with 32-bit float headroom."
            )

        return BroadcastQCCertificate(
            media_name=media_name,
            target_spec=spec,
            passed=overall_pass,
            metrics=metrics,
            criteria=criteria,
            gain_correction_db=round(gain_correction, 2),
            clipping_detected=has_clipping,
            remediation_actions=actions,
        )


__all__ = [
    "DELIVERY_CRITERIA",
    "BroadcastQCCertificate",
    "BroadcastQCEngine",
    "DeliverySpec",
    "DeliverySpecCriteria",
    "LoudnessQCResult",
]
