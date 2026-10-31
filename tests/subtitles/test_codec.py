from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aidub.domain.time import RationalRate, RationalTime, TimeRange
from aidub.subtitles import (
    SubtitleCodecError,
    SubtitleCue,
    SubtitleDocument,
    SubtitleFormat,
    load_subtitle,
    parse_srt,
    parse_webvtt,
    publish_subtitle,
    render_srt,
    render_webvtt,
)

SRT = """1
00:00:01,250 --> 00:00:03,500
বাংলা সংলাপ

2
00:00:04,000 --> 00:00:05,125
हिन्दी संवाद
দ্বিতীয় পঙ্‌ক্তি
"""


def test_srt_round_trip_preserves_indic_text_and_exact_time() -> None:
    document = parse_srt(SRT, language="bn-BD")

    assert document.cues[0].time_range.start.ticks == 1_250
    assert document.cues[0].time_range.end_exclusive.ticks == 3_500
    assert document.cues[0].text == "বাংলা সংলাপ"
    assert "हिन्दी" in document.cues[1].text

    restored = parse_srt(render_srt(document), language="bn-BD")
    assert [cue.time_range for cue in restored.cues] == [cue.time_range for cue in document.cues]
    assert [cue.text for cue in restored.cues] == [cue.text for cue in document.cues]


def test_webvtt_retains_identifier_settings_and_notes_are_ignored() -> None:
    source = """WEBVTT - multilingual fixture
Kind: captions

NOTE reviewed by localization

opening
00:01.000 --> 00:03.250 align:start position:10%
নমস্কার
"""
    document = parse_webvtt(source, language="bn-BD")

    assert len(document.cues) == 1
    assert document.cues[0].cue_id == "opening"
    assert document.cues[0].settings == "align:start position:10%"
    assert parse_webvtt(render_webvtt(document), language="bn-BD") == document


@pytest.mark.parametrize(
    "source, message",
    [
        ("1\n00:00:02,000 --> 00:00:01,000\nbackwards", "end after"),
        ("1\n00:61:00,000 --> 00:61:01,000\ninvalid", "invalid timestamp"),
        ("1\n00:00:00,000 --> 00:00:01,000\n", "incomplete"),
    ],
)
def test_srt_rejects_invalid_cues(source: str, message: str) -> None:
    with pytest.raises(SubtitleCodecError, match=message):
        parse_srt(source)


def test_cue_rejects_non_millisecond_clock_and_zero_duration() -> None:
    with pytest.raises(ValidationError, match="1000"):
        SubtitleCue(
            time_range=TimeRange(
                start=RationalTime(ticks=0, rate=RationalRate(numerator=24)),
                duration=RationalTime(ticks=1, rate=RationalRate(numerator=24)),
            ),
            text="not a subtitle clock",
        )
    with pytest.raises(ValidationError, match="positive duration"):
        SubtitleCue(
            time_range=TimeRange(
                start=RationalTime(ticks=0, rate=RationalRate(numerator=1_000)),
                duration=RationalTime(ticks=0, rate=RationalRate(numerator=1_000)),
            ),
            text="empty",
        )


def test_limits_are_enforced_during_parse() -> None:
    with pytest.raises(SubtitleCodecError, match="exceeds 1 cues"):
        parse_srt(SRT, maximum_cues=1)
    with pytest.raises(SubtitleCodecError, match="Unicode characters"):
        parse_srt(SRT, maximum_text_characters=2)


def test_publish_and_load_are_utf8_atomic_and_never_overwrite(tmp_path: Path) -> None:
    document = parse_srt(SRT, language="hi-IN")
    target = tmp_path / "international captions.srt"

    assert publish_subtitle(target, document) == target.resolve()
    assert load_subtitle(target, language="hi-IN") == document
    original = target.read_bytes()

    with pytest.raises(FileExistsError):
        publish_subtitle(target, document)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob("*.staged"))


def test_document_rejects_out_of_order_cues() -> None:
    document = parse_srt(SRT)
    with pytest.raises(ValidationError, match="ordered"):
        SubtitleDocument(
            format=SubtitleFormat.SRT,
            cues=tuple(reversed(document.cues)),
        )
