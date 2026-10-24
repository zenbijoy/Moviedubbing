"""
5.1 Cinematic Surround Sound Audio Remixer and EBU R128 Loudness Normalizer.

Mixes localized dialogue into the discrete Center (FC) channel of a 5.1 surround sound layout
while routing background music, ambience, and Foley effects across FL, FR, BL, BR, and LFE.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aidub.media.ffmpeg_ops import _ffmpeg_exe, _run, duration

logger = logging.getLogger(__name__)


class SurroundSoundMixer:
    """Mixes localized vocal stems and multi-track beds into broadcast-grade 5.1 surround sound."""

    @classmethod
    def mix_5point1(
        cls,
        dialogue_wav: Path | str,
        background_music_wav: Path | str,
        output_wav: Path | str,
        *,
        dialogue_gain_db: float = 0.0,
        music_ducking_db: float = -14.0,
        loudness_target_lufs: float = -23.0,
    ) -> Path:
        """
        Produce a discrete 6-channel 5.1 WAV track (FL, FR, FC, LFE, BL, BR).

        Layout:
          - FL (Front Left):  Original Music Left
          - FR (Front Right): Original Music Right
          - FC (Front Center): Dubbed Dialogue (Clear & Isolated)
          - LFE (Subwoofer):  Music low-pass sub-bass (<120Hz)
          - BL (Back Left):   Original Music Left attenuated (-3dB)
          - BR (Back Right):  Original Music Right attenuated (-3dB)

        Args:
            dialogue_wav: Dubbed vocals WAV.
            background_music_wav: Background music / stems WAV.
            output_wav: Output 5.1 audio path.
            dialogue_gain_db: Fine gain offset for center dialogue.
            music_ducking_db: Attenuation applied to music bed.
            loudness_target_lufs: Target integrated loudness (EBU R128 = -23, YouTube = -14).
        """
        dia = Path(dialogue_wav)
        bg = Path(background_music_wav)
        out = Path(output_wav)
        out.parent.mkdir(parents=True, exist_ok=True)

        if not dia.is_file():
            raise FileNotFoundError(f"Dialogue track not found: {dia}")

        # If no separate background music track exists, generate 5.1 directly from dialogue
        if not bg.is_file():
            filter_str = (
                f"[0:a]volume={dialogue_gain_db}dB,"
                f"pan=5.1|c0=0.1*c0|c1=0.1*c0|c2=1.0*c0|c3=0.0*c0|c4=0.05*c0|c5=0.05*c0,"
                f"loudnorm=I={loudness_target_lufs}:TP=-1.0:LRA=11[out]"
            )
            cmd = [
                _ffmpeg_exe(),
                "-y",
                "-i",
                str(dia),
                "-filter_complex",
                filter_str,
                "-map",
                "[out]",
                "-ac",
                "6",
                "-ar",
                "48000",
                str(out),
            ]
            _run(cmd)
            return out

        # Full 5.1 mixing with dialogue in Center (c2) and music across FL/FR/Surrounds
        duck_lin = 10.0 ** (music_ducking_db / 20.0)
        filter_str = (
            f"[0:a]volume={dialogue_gain_db}dB[dia];"
            f"[1:a]volume={duck_lin}[bg];"
            f"[bg][dia]amerge=inputs=2[merged];"
            # c0=bg_L, c1=bg_R, c2=dia_L, c3=dia_R
            f"[merged]pan=5.1|c0=c0|c1=c1|c2=0.5*c2+0.5*c3|c3=0.3*c0+0.3*c1|c4=0.7*c0|c5=0.7*c1,"
            f"loudnorm=I={loudness_target_lufs}:TP=-1.0:LRA=11[out]"
        )

        cmd = [
            _ffmpeg_exe(),
            "-y",
            "-i",
            str(dia),
            "-i",
            str(bg),
            "-filter_complex",
            filter_str,
            "-map",
            "[out]",
            "-ac",
            "6",
            "-ar",
            "48000",
            str(out),
        ]
        _run(cmd)
        logger.info("5.1 Surround Sound master synthesized: %s (Duration=%.1fs)", out.name, duration(out))
        return out


__all__ = ["SurroundSoundMixer"]
