"""
EDL & FCPXML Timeline Interchange Adapter.

Exports CMX3600 Edit Decision Lists (EDL) and Final Cut Pro XML (FCPXML 1.10+) manifests
with frame-accurate SMPTE timecodes, track channel routing, and NLE asset mapping
for seamless round-trip workflows in DaVinci Resolve, Adobe Premiere Pro, and Final Cut Pro.
"""

from __future__ import annotations

import logging
import math
import re
from xml.sax.saxutils import escape

from aidub.interchange.otio_adapter import OTIOTimeline

logger = logging.getLogger(__name__)


class SMPTETimecode:
    """
    Frame-accurate SMPTE timecode conversion for broadcast and cinema NLEs.
    """

    @staticmethod
    def ms_to_timecode(ms: int, fps: float = 24.0, drop_frame: bool = False) -> str:
        """
        Convert milliseconds to SMPTE timecode (HH:MM:SS:FF or HH:MM:SS;FF for drop-frame).
        """
        safe_ms = max(0, ms)
        safe_fps = max(1.0, fps)
        fps_nominal = round(safe_fps)

        if drop_frame and abs(safe_fps - 29.97) < 0.05:
            # Drop-frame calculation for 29.97 fps (SMPTE 12M standard)
            # Drops frame numbers 0 and 1 at the start of every minute, except every 10th minute
            total_frames = int(round(safe_ms * (safe_fps / 1000.0)))
            d = total_frames // 17982
            m = total_frames % 17982
            if m >= 2:
                frame_number = total_frames + 18 * d + 2 * ((m - 2) // 1798)
            else:
                frame_number = total_frames + 18 * d

            ff = frame_number % 30
            ss = (frame_number // 30) % 60
            mm = (frame_number // 1800) % 60
            hh = (frame_number // 108000) % 24
            return f"{hh:02d}:{mm:02d}:{ss:02d};{ff:02d}"

        # Standard Non-Drop Frame (NDF) calculation
        total_frames = int(round(safe_ms * (safe_fps / 1000.0)))
        ff = total_frames % fps_nominal
        total_seconds = total_frames // fps_nominal
        ss = total_seconds % 60
        total_minutes = total_seconds // 60
        mm = total_minutes % 60
        hh = (total_minutes // 60) % 24
        return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

    @staticmethod
    def seconds_to_fraction(seconds: float, fps: float = 24.0) -> str:
        """
        Convert seconds to FCPXML rational time fraction string (e.g. '1001/24000s' or '100/24s').
        """
        safe_sec = max(0.0, seconds)
        safe_fps = max(1.0, fps)
        fps_nominal = round(safe_fps)
        total_frames = int(round(safe_sec * safe_fps))
        return f"{total_frames}/{fps_nominal}s"


class EDLFCPXMLAdapter:
    """
    Production-grade adapter converting timeline structures to CMX3600 EDL and FCPXML 1.10+.
    """

    def export_cmx3600_edl(
        self, timeline: OTIOTimeline, start_timecode_ms: int = 3600000
    ) -> str:
        """
        Export timeline as industry-standard CMX3600 EDL with accurate timecodes.

        Args:
            timeline: The timeline model containing video and audio tracks.
            start_timecode_ms: Timeline record start time in ms (default 01:00:00:00 = 3600000ms).
        """
        fps = timeline.frame_rate
        is_drop = fps in (29.97, 59.94)
        fcm_mode = "DROP FRAME" if is_drop else "NON-DROP FRAME"

        lines = [
            f"TITLE: {timeline.name.upper()}",
            f"FCM: {fcm_mode}",
            "",
        ]

        edit_num = 1
        record_head_ms = start_timecode_ms

        for track in timeline.tracks:
            track_kind = track.kind.lower()
            track_type = "V" if "video" in track_kind else "AA"

            for clip in track.clips:
                src_in_ms = clip.source_range_start_ms
                dur_ms = clip.source_range_duration_ms
                src_out_ms = src_in_ms + dur_ms

                rec_in_ms = record_head_ms
                rec_out_ms = rec_in_ms + dur_ms

                src_in_tc = SMPTETimecode.ms_to_timecode(src_in_ms, fps, is_drop)
                src_out_tc = SMPTETimecode.ms_to_timecode(src_out_ms, fps, is_drop)
                rec_in_tc = SMPTETimecode.ms_to_timecode(rec_in_ms, fps, is_drop)
                rec_out_tc = SMPTETimecode.ms_to_timecode(rec_out_ms, fps, is_drop)

                # CMX3600 reel name: alphanumeric, max 8 chars
                clean_name = re.sub(r"[^A-Z0-9]", "", clip.name.upper()) or "AX"
                reel_name = clean_name[:8]

                # Event record line: Event Reel Track Trans SrcIn SrcOut RecIn RecOut
                lines.append(
                    f"{edit_num:03d}  {reel_name:<8} {track_type:<4} C        "
                    f"{src_in_tc} {src_out_tc} {rec_in_tc} {rec_out_tc}"
                )
                lines.append(f"* FROM CLIP: {clip.name}")
                lines.append(f"* SOURCE FILE: {clip.media_reference_path}")
                lines.append(f"* TRACK TYPE: {track.kind}")

                record_head_ms = rec_out_ms
                edit_num += 1

        logger.info(
            "edl_fcpxml_adapter: generated %d CMX3600 EDL events for '%s'",
            edit_num - 1,
            timeline.name,
        )
        return "\n".join(lines)

    def export_fcpxml(self, timeline: OTIOTimeline) -> str:
        """
        Export timeline as Final Cut Pro XML (FCPXML 1.10+) format with full resources and spine.
        """
        fps = timeline.frame_rate
        fps_nominal = round(fps)
        frame_dur_str = f"1/{fps_nominal}s"

        # Collect unique assets
        asset_map: dict[str, str] = {}
        asset_xml_lines: list[str] = []
        asset_counter = 2

        total_duration_ms = 0
        for track in timeline.tracks:
            track_dur = sum(c.source_range_duration_ms for c in track.clips)
            total_duration_ms = max(total_duration_ms, track_dur)

            for clip in track.clips:
                path = clip.media_reference_path
                if path not in asset_map:
                    asset_id = f"r{asset_counter}"
                    asset_map[path] = asset_id
                    asset_counter += 1

                    clip_dur_sec = max(0.1, clip.source_range_duration_ms / 1000.0)
                    dur_fraction = SMPTETimecode.seconds_to_fraction(clip_dur_sec, fps)

                    is_vid = "video" in track.kind.lower()
                    asset_xml_lines.append(
                        f'    <asset id="{asset_id}" name="{escape(clip.name)}" '
                        f'src="file:///{escape(path.replace("\\", "/"))}" start="0s" '
                        f'duration="{dur_fraction}" hasAudio="1" hasVideo="{1 if is_vid else 0}" '
                        f'audioSources="1" audioChannels="2" audioRate="48000"/>'
                    )

        total_sec = max(0.1, total_duration_ms / 1000.0)
        seq_duration_str = SMPTETimecode.seconds_to_fraction(total_sec, fps)

        xml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<!DOCTYPE fcpxml>",
            '<fcpxml version="1.10">',
            "  <resources>",
            f'    <format id="r1" name="FFVideoFormat1080p{fps_nominal}" frameDuration="{frame_dur_str}" width="1920" height="1080"/>',
        ]
        xml.extend(asset_xml_lines)
        xml.extend([
            "  </resources>",
            f'  <library location="file:///AIDub_Master.fcpbundle">',
            f'    <event name="AIDub Production Event">',
            f'      <project name="{escape(timeline.name)}">',
            f'        <sequence format="r1" duration="{seq_duration_str}" tcStart="0s" tcFormat="NDF">',
            "          <spine>",
        ])

        # Populate Spine with clips
        offset_ms = 0
        for track in timeline.tracks:
            role = "dialogue.dialogue" if "audio" in track.kind.lower() else "video"
            for clip in track.clips:
                asset_id = asset_map.get(clip.media_reference_path, "r2")
                dur_sec = clip.source_range_duration_ms / 1000.0
                src_start_sec = clip.source_range_start_ms / 1000.0
                offset_sec = offset_ms / 1000.0

                dur_str = SMPTETimecode.seconds_to_fraction(dur_sec, fps)
                src_start_str = SMPTETimecode.seconds_to_fraction(src_start_sec, fps)
                offset_str = SMPTETimecode.seconds_to_fraction(offset_sec, fps)

                xml.append(
                    f'            <asset-clip name="{escape(clip.name)}" ref="{asset_id}" '
                    f'offset="{offset_str}" start="{src_start_str}" duration="{dur_str}" '
                    f'role="{role}"/>'
                )
                offset_ms += clip.source_range_duration_ms

        xml.extend([
            "          </spine>",
            "        </sequence>",
            "      </project>",
            "    </event>",
            "  </library>",
            "</fcpxml>",
        ])

        logger.info(
            "edl_fcpxml_adapter: generated complete FCPXML 1.10 manifest for '%s'", timeline.name
        )
        return "\n".join(xml)


__all__ = [
    "EDLFCPXMLAdapter",
    "SMPTETimecode",
]
