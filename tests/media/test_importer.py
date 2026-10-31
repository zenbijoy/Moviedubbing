from fractions import Fraction
from pathlib import Path

from aidub.domain.media import AudioStream, FrameRateMode, SubtitleStream, VideoStream
from aidub.media.importer import MediaImportService
from aidub.media.probe import (
    AudioStreamInfo,
    ContainerInfo,
    SubtitleStreamInfo,
    VideoStreamInfo,
)


def test_builds_multilingual_domain_media_asset(tmp_path: Path) -> None:
    source = tmp_path / "movie.mkv"
    source.write_bytes(b"legal fixture")
    info = ContainerInfo(
        path=source,
        format_names=("matroska",),
        duration_seconds=1.0,
        bit_rate=1_000_000,
        size_bytes=source.stat().st_size,
        video_streams=(
            VideoStreamInfo(
                index=0,
                codec="h264",
                width=1920,
                height=1080,
                average_frame_rate=Fraction(24),
                real_frame_rate=Fraction(24),
                time_base=Fraction(1, 24_000),
                pixel_format="yuv420p",
                color_range="tv",
                color_space="bt709",
                color_transfer="bt709",
                color_primaries="bt709",
                sample_aspect_ratio="1:1",
                field_order="progressive",
                rotation_degrees=0,
                start_ticks=0,
                duration_ticks=24_000,
            ),
        ),
        audio_streams=(
            AudioStreamInfo(
                index=1,
                codec="pcm_s24le",
                sample_rate=48_000,
                channels=2,
                channel_layout="stereo",
                language="ben",
                time_base=Fraction(1, 48_000),
                start_ticks=0,
                duration_ticks=48_000,
            ),
        ),
        subtitle_streams=(
            SubtitleStreamInfo(
                index=2,
                codec="ass",
                language="hin",
                title="Hindi",
                time_base=Fraction(1, 1_000),
                forced=False,
                hearing_impaired=False,
            ),
        ),
        chapters=0,
    )

    class StubProbe:
        def probe(self, _source: Path | str) -> ContainerInfo:
            return info

    asset = MediaImportService(StubProbe()).inspect(source, project_id="prj_example")
    video = next(item for item in asset.streams if isinstance(item, VideoStream))
    audio = next(item for item in asset.streams if isinstance(item, AudioStream))
    subtitle = next(item for item in asset.streams if isinstance(item, SubtitleStream))
    assert video.frame_rate_mode is FrameRateMode.CONSTANT
    assert audio.language == "bn"
    assert subtitle.language == "hi"
    assert asset.fingerprint.full_sha256 is not None
