from fractions import Fraction
from pathlib import Path

from aidub.media.probe import MediaProbe


def test_parses_video_audio_subtitles_and_vfr(tmp_path: Path) -> None:
    source = tmp_path / "movie.mkv"
    source.write_bytes(b"media")
    payload = {
        "format": {
            "format_name": "matroska,webm",
            "duration": "120.5",
            "bit_rate": "9000000",
        },
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "24000/1001",
                "r_frame_rate": "30/1",
                "time_base": "1/1000",
                "pix_fmt": "yuv420p",
                "side_data_list": [{"rotation": -90}],
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "time_base": "1/48000",
                "channels": 6,
                "channel_layout": "5.1",
                "tags": {"language": "eng"},
            },
            {
                "index": 2,
                "codec_type": "subtitle",
                "codec_name": "ass",
                "time_base": "1/1000",
                "tags": {"language": "ben", "title": "Bengali"},
            },
        ],
        "chapters": [{}, {}],
    }
    result = MediaProbe._parse(source, payload)
    assert result.format_names == ("matroska", "webm")
    assert result.video_streams[0].average_frame_rate == Fraction(24000, 1001)
    assert result.video_streams[0].likely_variable_frame_rate
    assert result.video_streams[0].rotation_degrees == -90
    assert result.audio_streams[0].channel_layout == "5.1"
    assert result.subtitle_streams[0].language == "ben"
    assert result.chapters == 2
