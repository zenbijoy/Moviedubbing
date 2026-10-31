from decimal import Decimal
from pathlib import Path

import pytest

from aidub.domain.time import RationalRate, RationalTime
from aidub.media.commands import (
    ProxySpec,
    ThumbnailSpec,
    WaveformSpec,
    build_ffmpeg_command,
    derivative_cache_key,
)
from aidub.media.derivatives import FFmpegProgressParser


def _runtime_and_source(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "ffmpeg.exe"
    executable.write_bytes(b"fake executable")
    source = tmp_path / "source movie.mkv"
    source.write_bytes(b"source")
    return executable, source


def test_proxy_command_preserves_exact_rate_and_uses_tuple_argv(tmp_path: Path) -> None:
    executable, source = _runtime_and_source(tmp_path)
    output = tmp_path / "proxy.part"
    spec = ProxySpec(frame_rate=RationalRate(numerator=24_000, denominator=1_001))

    plan = build_ffmpeg_command(executable, source, output, spec)

    assert isinstance(plan.argv, tuple)
    assert plan.argv[0] == str(executable.resolve())
    assert plan.argv[plan.argv.index("-i") + 1] == str(source.resolve())
    video_filter = plan.argv[plan.argv.index("-vf") + 1]
    assert "fps=fps=24000/1001" in video_filter
    assert plan.argv[-1] == str(output.resolve())
    assert "-n" in plan.argv


def test_thumbnail_filter_keeps_rational_position_without_float_conversion(
    tmp_path: Path,
) -> None:
    executable, source = _runtime_and_source(tmp_path)
    position = RationalTime(
        ticks=1,
        rate=RationalRate(numerator=24_000, denominator=1_001),
    )

    plan = build_ffmpeg_command(
        executable,
        source,
        tmp_path / "thumb.part",
        ThumbnailSpec(position=position),
    )

    video_filter = plan.argv[plan.argv.index("-vf") + 1]
    assert "1001/24000" in video_filter
    assert "0.041" not in video_filter


def test_cache_key_is_canonical_and_changes_with_material_settings() -> None:
    source_hash = "ab" * 32
    first = ProxySpec(frame_rate=RationalRate(numerator=24_000, denominator=1_001))
    equivalent = ProxySpec(frame_rate=RationalRate(numerator=48_000, denominator=2_002))
    different = ProxySpec(frame_rate=RationalRate(numerator=25))

    first_key = derivative_cache_key(source_hash, first, ffmpeg_version="7.1.1")

    assert first_key == derivative_cache_key(
        source_hash.upper(), equivalent, ffmpeg_version="7.1.1"
    )
    assert first_key != derivative_cache_key(source_hash, different, ffmpeg_version="7.1.1")
    assert first_key != derivative_cache_key(source_hash, first, ffmpeg_version="8.0")


def test_specs_reject_filtergraph_injection() -> None:
    with pytest.raises(ValueError, match="hex color"):
        WaveformSpec(foreground_color="#00FF00,evil=1")


def test_progress_parser_emits_bounded_typed_records() -> None:
    parser = FFmpegProgressParser()

    assert parser.feed_line("frame=240\n") is None
    assert parser.feed_line("fps=23.976\n") is None
    assert parser.feed_line("out_time_us=10010000\n") is None
    assert parser.feed_line("speed=1.25x\n") is None
    update = parser.feed_line("progress=continue\n")

    assert update is not None
    assert update.frame == 240
    assert update.fps == Decimal("23.976")
    assert update.out_time_microseconds == 10_010_000
    assert update.speed == Decimal("1.25")
    assert update.state == "continue"
