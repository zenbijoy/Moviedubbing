from __future__ import annotations

from pathlib import Path

import pytest

from aidub.adapters.separation_demucs import DemucsSeparationAdapter, DemucsSeparationOptions
from aidub.media.probe import AudioStreamInfo, ContainerInfo
from aidub.media.stems import StemSelectionPolicy, StemSelector


def test_stem_selector_prefer_studio_me(tmp_path: Path) -> None:
    out_dir = tmp_path / "stems_studio"
    selector = StemSelector(DemucsSeparationAdapter(DemucsSeparationOptions(device="cpu")))

    container = ContainerInfo(
        path=Path("input.mkv"),
        format_names=("matroska",),
        duration_seconds=10.0,
        bit_rate=1_000_000,
        size_bytes=100_000,
        video_streams=(),
        audio_streams=(
            AudioStreamInfo(
                index=0,
                codec="aac",
                sample_rate=48_000,
                channels=2,
                channel_layout="stereo",
                language="en",
                time_base=None,
                start_ticks=0,
                duration_ticks=480_000,
            ),
            AudioStreamInfo(
                index=1,
                codec="aac",
                sample_rate=48_000,
                channels=2,
                channel_layout="stereo",
                language="m&e",
                time_base=None,
                start_ticks=0,
                duration_ticks=480_000,
            ),
        ),
        subtitle_streams=(),
        chapters=0,
    )

    with pytest.raises(FileNotFoundError, match="studio M&E source does not exist"):
        selector.process_stems(
            source_audio_path="input.mkv",
            output_directory=str(out_dir),
            probe=container,
            policy=StemSelectionPolicy.PREFER_STUDIO_ME,
        )


def test_stem_selector_force_ai_separation(tmp_path: Path) -> None:
    out_dir = tmp_path / "stems_ai"
    selector = StemSelector(DemucsSeparationAdapter(DemucsSeparationOptions(device="cpu")))

    container = ContainerInfo(
        path=Path("input.mkv"),
        format_names=("matroska",),
        duration_seconds=10.0,
        bit_rate=1_000_000,
        size_bytes=100_000,
        video_streams=(),
        audio_streams=(
            AudioStreamInfo(
                index=0,
                codec="aac",
                sample_rate=48_000,
                channels=2,
                channel_layout="stereo",
                language="m&e",
                time_base=None,
                start_ticks=0,
                duration_ticks=480_000,
            ),
        ),
        subtitle_streams=(),
        chapters=0,
    )

    with pytest.raises(FileNotFoundError, match="source audio does not exist"):
        selector.process_stems(
            source_audio_path="input.mkv",
            output_directory=str(out_dir),
            probe=container,
            policy=StemSelectionPolicy.FORCE_AI_SEPARATION,
        )
