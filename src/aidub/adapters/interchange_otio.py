"""
Professional NLE Interchange Adapter (OpenTimelineIO, CMX 3600 EDL, FCPXML, Premiere XML, CSV Cue Sheet).

Provides project interchange serializers and deserializers for Premiere Pro, Final Cut Pro X,
DaVinci Resolve, and Avid Media Composer.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class InterchangeFormat(StrEnum):
    OTIO = "otio"  # OpenTimelineIO JSON
    EDL = "edl"  # CMX 3600 Edit Decision List
    FCPXML = "fcpxml"  # Final Cut Pro XML
    PREMIERE_XML = "xml"  # Adobe Premiere Pro XML
    CUE_SHEET_CSV = "csv"  # CSV Dialogue Cue Sheet


class NleClipItem(ContractModel):
    """Dialogue clip metadata item in timeline interchange."""

    clip_id: Identifier
    character_id: Identifier
    source_start_ms: int = Field(ge=0)
    source_duration_ms: int = Field(gt=0)
    timeline_start_ms: int = Field(ge=0)
    audio_file_path: str = Field(min_length=1)
    transcript_text: str = Field(default="")
    translation_text: str = Field(default="")


class NleTrackItem(ContractModel):
    """Track metadata item in timeline interchange."""

    track_id: Identifier
    name: str = Field(default="Dialogue Track", max_length=64)
    kind: str = Field(default="Audio", max_length=32)
    clips: list[NleClipItem] = Field(default_factory=list)


class NleInterchangeTimeline(ContractModel):
    """Full timeline interchange model structure."""

    project_id: Identifier
    title: str = Field(default="Movie Dub Project", max_length=128)
    fps: float = Field(default=24.0, gt=0.0)
    duration_ms: int = Field(ge=0)
    tracks: list[NleTrackItem] = Field(default_factory=list)


class NleInterchangeAdapter:
    """
    Serializes and deserializes timeline project structures to OTIO, EDL, FCPXML, Premiere XML, and CSV Cue Sheets.
    """

    @staticmethod
    def export_otio_json(timeline: NleInterchangeTimeline) -> str:
        """
        Serialize timeline to OpenTimelineIO (OTIO) v1 schema JSON format.
        """
        otio_doc = {
            "OTIO_SCHEMA": "Timeline.1",
            "metadata": {
                "aidub_project_id": timeline.project_id,
                "duration_ms": timeline.duration_ms,
            },
            "name": timeline.title,
            "global_start_time": {
                "OTIO_SCHEMA": "RationalTime.1",
                "rate": timeline.fps,
                "value": 0,
            },
            "tracks": {
                "OTIO_SCHEMA": "Stack.1",
                "children": [
                    {
                        "OTIO_SCHEMA": "Track.1",
                        "kind": track.kind,
                        "name": track.name,
                        "children": [
                            {
                                "OTIO_SCHEMA": "Clip.1",
                                "name": clip.clip_id,
                                "source_range": {
                                    "OTIO_SCHEMA": "TimeRange.1",
                                    "duration": {
                                        "OTIO_SCHEMA": "RationalTime.1",
                                        "rate": timeline.fps,
                                        "value": int(
                                            (clip.source_duration_ms / 1000.0) * timeline.fps
                                        ),
                                    },
                                    "start_time": {
                                        "OTIO_SCHEMA": "RationalTime.1",
                                        "rate": timeline.fps,
                                        "value": int(
                                            (clip.source_start_ms / 1000.0) * timeline.fps
                                        ),
                                    },
                                },
                                "media_reference": {
                                    "OTIO_SCHEMA": "ExternalReference.1",
                                    "target_url": clip.audio_file_path,
                                },
                                "metadata": {
                                    "character_id": clip.character_id,
                                    "transcript_text": clip.transcript_text,
                                    "translation_text": clip.translation_text,
                                },
                            }
                            for clip in track.clips
                        ],
                    }
                    for track in timeline.tracks
                ],
            },
        }
        return json.dumps(otio_doc, indent=2)

    @staticmethod
    def import_otio_json(otio_json_str: str) -> NleInterchangeTimeline:
        """
        Deserialize OpenTimelineIO (OTIO) JSON string into NleInterchangeTimeline.
        """
        otio_dict = json.loads(otio_json_str)
        title = otio_dict.get("name", "Imported Project")
        metadata = otio_dict.get("metadata", {})
        pid = Identifier(metadata.get("aidub_project_id", "project_imported"))
        duration_ms = metadata.get("duration_ms", 60000)

        tracks: list[NleTrackItem] = []
        stack = otio_dict.get("tracks", {}).get("children", [])
        for t_idx, trk_dict in enumerate(stack):
            t_name = trk_dict.get("name", f"Track {t_idx + 1}")
            t_kind = trk_dict.get("kind", "Audio")
            clips: list[NleClipItem] = []

            for c_dict in trk_dict.get("children", []):
                c_name = c_dict.get("name", "clip_001")
                c_meta = c_dict.get("metadata", {})
                media_ref = c_dict.get("media_reference", {}).get("target_url", "take.wav")
                s_range = c_dict.get("source_range", {})
                dur_frames = s_range.get("duration", {}).get("value", 72)
                rate = s_range.get("duration", {}).get("rate", 24.0)
                dur_ms = int((dur_frames / rate) * 1000.0)

                clips.append(
                    NleClipItem(
                        clip_id=Identifier(c_name),
                        character_id=Identifier(c_meta.get("character_id", "char_1")),
                        source_start_ms=0,
                        source_duration_ms=dur_ms,
                        timeline_start_ms=0,
                        audio_file_path=media_ref,
                        transcript_text=c_meta.get("transcript_text", ""),
                        translation_text=c_meta.get("translation_text", ""),
                    )
                )

            tracks.append(
                NleTrackItem(
                    track_id=Identifier(f"trk_{t_idx + 1}"),
                    name=t_name,
                    kind=t_kind,
                    clips=clips,
                )
            )

        return NleInterchangeTimeline(
            project_id=pid,
            title=title,
            fps=24.0,
            duration_ms=duration_ms,
            tracks=tracks,
        )

    @staticmethod
    def export_cmx3600_edl(timeline: NleInterchangeTimeline) -> str:
        """
        Serialize timeline to CMX 3600 Edit Decision List (EDL) text format.
        """
        lines: list[str] = [
            f"TITLE: {timeline.title.upper()}",
            "FCM: NON-DROP FRAME",
            "",
        ]

        event_num = 1
        for track in timeline.tracks:
            for clip in track.clips:
                src_in_f = int((clip.source_start_ms / 1000.0) * timeline.fps)
                src_out_f = src_in_f + int((clip.source_duration_ms / 1000.0) * timeline.fps)
                tl_in_f = int((clip.timeline_start_ms / 1000.0) * timeline.fps)
                tl_out_f = tl_in_f + int((clip.source_duration_ms / 1000.0) * timeline.fps)

                def _tc(frames: int, fps: float) -> str:
                    fps_i = int(fps)
                    s = frames // fps_i
                    f = frames % fps_i
                    m = s // 60
                    s = s % 60
                    h = m // 60
                    m = m % 60
                    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

                src_tc = f"{_tc(src_in_f, timeline.fps)} {_tc(src_out_f, timeline.fps)}"
                dst_tc = f"{_tc(tl_in_f, timeline.fps)} {_tc(tl_out_f, timeline.fps)}"

                lines.append(f"{event_num:03d}  AX       AA/V  C        {src_tc} {dst_tc}")
                lines.append(f"* FROM CLIP NAME: {Path(clip.audio_file_path).name}")
                lines.append(f"* CHARACTER: {clip.character_id}")
                lines.append("")
                event_num += 1

        return "\n".join(lines)

    @staticmethod
    def export_fcpxml(timeline: NleInterchangeTimeline) -> str:
        """
        Serialize timeline to Final Cut Pro XML (FCPXML v1.9) document string.
        """
        xml_lines: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<!DOCTYPE fcpxml>",
            '<fcpxml version="1.9">',
            "  <resources>",
            '    <format id="r1" name="FFVideoFormat1080p24" frameDuration="100/2400s" width="1920" height="1080"/>',
            "  </resources>",
            "  <library>",
            f'    <event name="{timeline.title}">',
            f'      <project name="{timeline.title}">',
            '        <sequence format="r1" duration="1000/24s">',
            "          <spine>",
        ]

        for track in timeline.tracks:
            for clip in track.clips:
                dur_s = clip.source_duration_ms / 1000.0
                start_s = clip.timeline_start_ms / 1000.0
                xml_lines.append(
                    f'            <asset-clip name="{clip.clip_id}" offset="{start_s:.2f}s" duration="{dur_s:.2f}s" ref="r1">'
                )
                xml_lines.append(
                    f"              <note>{clip.character_id}: {clip.translation_text}</note>"
                )
                xml_lines.append("            </asset-clip>")

        xml_lines.extend(
            [
                "          </spine>",
                "        </sequence>",
                "      </project>",
                "    </event>",
                "  </library>",
                "</fcpxml>",
            ]
        )

        return "\n".join(xml_lines)

    @staticmethod
    def export_dialogue_cue_sheet_csv(timeline: NleInterchangeTimeline) -> str:
        """
        Serialize timeline to CSV Dialogue Cue Sheet format for dubbing directors & sound engineers.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "Cue_ID",
                "Character_ID",
                "Timeline_Start_ms",
                "Duration_ms",
                "Original_Transcript",
                "Dubbed_Translation",
                "Audio_File_Path",
            ]
        )

        for track in timeline.tracks:
            for clip in track.clips:
                writer.writerow(
                    [
                        clip.clip_id,
                        clip.character_id,
                        clip.timeline_start_ms,
                        clip.source_duration_ms,
                        clip.transcript_text,
                        clip.translation_text,
                        clip.audio_file_path,
                    ]
                )

        return output.getvalue()


__all__ = [
    "InterchangeFormat",
    "NleClipItem",
    "NleInterchangeAdapter",
    "NleInterchangeTimeline",
    "NleTrackItem",
]
