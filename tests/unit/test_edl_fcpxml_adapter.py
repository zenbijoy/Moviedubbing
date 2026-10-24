"""
Unit tests for CMX3600 EDL and FCPXML 1.10+ Interchange Adapter.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from aidub.contracts.base import Identifier
from aidub.interchange.edl_fcpxml_adapter import EDLFCPXMLAdapter, SMPTETimecode
from aidub.interchange.otio_adapter import OTIOClip, OTIOTimeline, OTIOTrack


def test_smpte_timecode_calculations() -> None:
    # 24 fps: 1000ms = 24 frames = 00:00:01:00
    tc_1s = SMPTETimecode.ms_to_timecode(1000, fps=24.0)
    assert tc_1s == "00:00:01:00"

    # 24 fps: 3600000ms = 1 hour = 01:00:00:00
    tc_1h = SMPTETimecode.ms_to_timecode(3600000, fps=24.0)
    assert tc_1h == "01:00:00:00"

    # Fractional seconds to FCPXML fraction
    frac = SMPTETimecode.seconds_to_fraction(2.5, fps=24.0)
    assert frac == "60/24s"

    # Drop frame at 29.97 fps
    tc_df = SMPTETimecode.ms_to_timecode(1000, fps=29.97, drop_frame=True)
    assert ";" in tc_df


def test_edl_cmx3600_export_structure() -> None:
    clip1 = OTIOClip(
        clip_id=Identifier("c1"),
        name="Dialogue_Scene1",
        source_range_start_ms=0,
        source_range_duration_ms=3000,
        media_reference_path="dialogue_bn.wav",
    )
    clip2 = OTIOClip(
        clip_id=Identifier("c2"),
        name="Dialogue_Scene2",
        source_range_start_ms=1000,
        source_range_duration_ms=4000,
        media_reference_path="dialogue_bn.wav",
    )
    track = OTIOTrack(track_id=Identifier("t1"), kind="Audio", clips=[clip1, clip2])
    timeline = OTIOTimeline(
        timeline_id=Identifier("tl1"),
        name="Movie_Dubbing_Master",
        frame_rate=24.0,
        tracks=[track],
    )

    adapter = EDLFCPXMLAdapter()
    edl_text = adapter.export_cmx3600_edl(timeline, start_timecode_ms=3600000)

    assert "TITLE: MOVIE_DUBBING_MASTER" in edl_text
    assert "FCM: NON-DROP FRAME" in edl_text
    assert "001" in edl_text
    assert "002" in edl_text
    assert "01:00:00:00 01:00:03:00" in edl_text  # Event 1 rec in/out
    assert "01:00:03:00 01:00:07:00" in edl_text  # Event 2 rec in/out


def test_fcpxml_1_10_export_structure() -> None:
    clip = OTIOClip(
        clip_id=Identifier("c1"),
        name="Actor_Line_01",
        source_range_start_ms=500,
        source_range_duration_ms=2500,
        media_reference_path="stems/line01_bn.wav",
    )
    track = OTIOTrack(track_id=Identifier("t1"), kind="Audio", clips=[clip])
    timeline = OTIOTimeline(
        timeline_id=Identifier("tl1"),
        name="Pro_Studio_Project",
        frame_rate=24.0,
        tracks=[track],
    )

    adapter = EDLFCPXMLAdapter()
    fcpxml_str = adapter.export_fcpxml(timeline)

    # Validate that it is well-formed XML
    root = ET.fromstring(fcpxml_str)
    assert root.tag == "fcpxml"
    assert root.attrib.get("version") == "1.10"

    # Validate resources
    resources = root.find("resources")
    assert resources is not None
    format_elem = resources.find("format")
    assert format_elem is not None
    assert format_elem.attrib.get("width") == "1920"

    asset_elem = resources.find("asset")
    assert asset_elem is not None
    assert asset_elem.attrib.get("hasAudio") == "1"

    # Validate library and sequence
    project = root.find(".//project")
    assert project is not None
    assert project.attrib.get("name") == "Pro_Studio_Project"

    # Validate spine and asset-clip
    spine = root.find(".//spine")
    assert spine is not None
    asset_clip = spine.find("asset-clip")
    assert asset_clip is not None
    assert asset_clip.attrib.get("name") == "Actor_Line_01"
    assert "dialogue" in asset_clip.attrib.get("role", "")
