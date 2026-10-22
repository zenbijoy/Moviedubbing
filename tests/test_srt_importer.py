"""
Comprehensive unit tests for SRT Subtitle Importer & Subtitle Pipeline.
"""

import tempfile
import time
from pathlib import Path

from aidub.subtitles.encoding import detect_and_read_subtitle_file
from aidub.subtitles.models import DialogueSegment
from aidub.subtitles.repository import SubtitleRepository
from aidub.subtitles.services import SubtitleService
from aidub.subtitles.srt_parser import SRTParser, ms_to_srt_timestamp, srt_timestamp_to_ms
from aidub.subtitles.validator import SubtitleValidator


def test_timestamp_conversions():
    assert srt_timestamp_to_ms("00:00:09,000") == 9000
    assert srt_timestamp_to_ms("00:01:20.500") == 80500
    assert ms_to_srt_timestamp(9000) == "00:00:09,000"
    assert ms_to_srt_timestamp(80500) == "00:01:20,500"


def test_srt_parser_standard_and_multiline():
    srt_content = """1
00:00:09,000 --> 00:00:10,791
They say that friendships

2
00:00:11,000 --> 00:00:14,500
are never easier to build
than in childhood.
"""
    parser = SRTParser()
    segs = parser.parse_text(srt_content)
    assert len(segs) == 2
    assert segs[0].subtitle_index == 1
    assert segs[0].start_ms == 9000
    assert segs[0].end_ms == 10791
    assert segs[0].original_text == "They say that friendships"

    assert segs[1].start_ms == 11000
    assert segs[1].end_ms == 14500
    assert "are never easier" in segs[1].original_text
    assert "than in childhood." in segs[1].original_text


def test_stutter_and_hesitation_detection():
    srt_content = """1
00:00:01,000 --> 00:00:04,000
I… I… ha… ha… have to tell you something.
"""
    parser = SRTParser()
    segs = parser.parse_text(srt_content)
    assert len(segs) == 1
    assert segs[0].has_hesitation is True
    assert segs[0].original_text == "I… I… ha… ha… have to tell you something."


def test_multi_speaker_detection():
    srt_content = """1
00:00:05,000 --> 00:00:08,000
- M… Matze.
- You like soccer?
"""
    parser = SRTParser()
    segs = parser.parse_text(srt_content)
    assert len(segs) == 1
    assert segs[0].possible_multi_speaker is True
    assert segs[0].speaker_count_estimate >= 2


def test_unicode_languages():
    srt_content = """1
00:00:01,000 --> 00:00:03,000
আমি তোমাকে ভালোবাসি।

2
00:00:04,000 --> 00:00:06,000
नमस्ते दुनिया!

3
00:00:07,000 --> 00:00:09,000
مرحبا بك

4
00:00:10,000 --> 00:00:12,000
こんにちは世界
"""
    parser = SRTParser()
    segs = parser.parse_text(srt_content)
    assert len(segs) == 4
    assert segs[0].original_text == "আমি তোমাকে ভালোবাসি।"
    assert segs[1].original_text == "नमस्ते दुनिया!"
    assert segs[2].original_text == "مرحبا بك"
    assert segs[3].original_text == "こんにちは世界"


def test_utf8_bom_and_encodings():
    with tempfile.NamedTemporaryFile("wb", suffix=".srt", delete=False) as f:
        # UTF-8 with BOM
        content = "\ufeff1\n00:00:01,000 --> 00:00:03,000\nHello World\n".encode("utf-8")
        f.write(content)
        temp_path = Path(f.name)

    text, enc = detect_and_read_subtitle_file(temp_path)
    assert "Hello World" in text
    assert "UTF-8" in enc
    temp_path.unlink()


def test_validator_overlaps_and_warnings():
    segs = [
        DialogueSegment(subtitle_index=1, start_ms=1000, end_ms=4000, original_text="Seg 1"),
        DialogueSegment(
            subtitle_index=2, start_ms=3000, end_ms=6000, original_text="Seg 2"
        ),  # Overlaps
    ]
    report = SubtitleValidator.validate_segments(segs, movie_duration_ms=5000)
    assert report.overlap_count == 1
    assert any(w.category == "timing_overlap" for w in report.warnings)
    assert any(w.category == "exceeds_movie_duration" for w in report.warnings)


def test_large_srt_performance():
    # Generate 10,000 subtitle blocks
    blocks = []
    for i in range(1, 10001):
        s_ms = i * 2000
        e_ms = s_ms + 1500
        s_ts = ms_to_srt_timestamp(s_ms)
        e_ts = ms_to_srt_timestamp(e_ms)
        blocks.append(f"{i}\n{s_ts} --> {e_ts}\nLine {i} performance benchmark\n")

    srt_data = "\n".join(blocks)

    t0 = time.monotonic()
    parser = SRTParser()
    segs = parser.parse_text(srt_data)
    dur = time.monotonic() - t0

    assert len(segs) == 10000
    assert dur < 2.0  # Must parse 10,000 segments in under 2 seconds!


def test_export_and_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SubtitleRepository(tmpdir)
        service = SubtitleService(repo)

        srt_path = Path(tmpdir) / "test.srt"
        srt_path.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello Test\n", encoding="utf-8")

        _track, summary = service.import_subtitle_file(srt_path)
        assert summary.segment_count == 1
        assert summary.format == "SRT"

        loaded = repo.load_track("imported.json")
        assert loaded is not None
        assert len(loaded.segments) == 1
        assert loaded.segments[0].original_text == "Hello Test"
