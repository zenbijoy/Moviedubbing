"""
Broadcast audio mixer: sums stems with gain trims, dynamic sidechain ducking, and auto gain riding.
"""
from __future__ import annotations

import numpy as np

from aidub.application.audio.auto_gain_rider import AutoGainRider
from aidub.application.audio.sidechain_ducker import SidechainDucker
from aidub.media.pro_audio_editor import AudioClipData


class AudioMixer:
    """
    Multitrack stem summing mixer for film and TV delivery.
    Supports per-track gain trims, automatic dialogue gain riding, and music sidechain ducking.
    """

    @classmethod
    def mix(
        cls,
        stems: dict[str, tuple[AudioClipData, float]],
        auto_gain_dialogue: bool = False,
        sidechain_duck_music: bool = False,
        music_duck_db: float = -12.0,
    ) -> AudioClipData:
        """
        Sums stems with per-track gain (in dB).
        `stems`: mapping of stem_name -> (AudioClipData, gain_db).
        """
        if not stems:
            return AudioClipData(samples=np.array([], dtype=np.float32), sample_rate=48000)

        sr = next(iter(stems.values()))[0].sample_rate
        processed_stems: dict[str, tuple[AudioClipData, float]] = dict(stems)

        # 1. Dialogue Auto Gain Riding (if enabled)
        dialogue_stem_name: str | None = None
        for name in processed_stems:
            if any(k in name.lower() for k in ("dialogue", "dub", "voice", "speech")):
                dialogue_stem_name = name
                break

        if auto_gain_dialogue and dialogue_stem_name:
            orig_clip, gain = processed_stems[dialogue_stem_name]
            rider = AutoGainRider(target_rms=0.12, max_gain_db=10.0)
            leveled = rider.process(orig_clip)
            processed_stems[dialogue_stem_name] = (leveled, gain)

        # 2. Sidechain Music Ducking (if enabled)
        if sidechain_duck_music and dialogue_stem_name:
            dial_clip = processed_stems[dialogue_stem_name][0]
            ducker = SidechainDucker(threshold_dbfs=-32.0, duck_db=music_duck_db)

            for name, (clip, gain) in list(processed_stems.items()):
                if any(k in name.lower() for k in ("music", "bgm", "score", "soundtrack")):
                    ducked_clip = ducker.process(clip, dial_clip)
                    processed_stems[name] = (ducked_clip, gain)

        # 3. Summing Stems
        max_len = max(v[0].samples.size for v in processed_stems.values())
        out = np.zeros(max_len, dtype=np.float64)

        for name, (clip, gain) in processed_stems.items():
            lin = 10.0 ** (gain / 20.0)
            seg = clip.samples.astype(np.float64)
            if seg.size < max_len:
                seg = np.pad(seg, (0, max_len - seg.size))
            out += seg * lin

        # 4. Broadcast Peak Limiter Ceiling (-1.0 dBFS = 0.891 linear)
        peak = float(np.max(np.abs(out))) if out.size > 0 else 0.0
        if peak > 0.891:
            out = out * (0.891 / peak)

        return AudioClipData(samples=out.astype(np.float32), sample_rate=sr)


__all__ = ["AudioMixer"]
