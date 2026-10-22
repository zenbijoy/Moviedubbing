"""
Enterprise Master Distribution Package Exporter.

Exports industry-standard delivery packages:
  1. Digital Cinema Package (DCP) XML manifest (CompositionPlaylist CPL & PackingList PKL).
  2. Multi-channel Broadcast Audio Layback (Stereo, 5.1 Surround, 7.1 Surround MXF/ProRes).
  3. OTT Web Streaming Manifests (HLS m3u8 & DASH mpd multi-language streams with WebVTT/TTML closed captions).
"""

from __future__ import annotations

import hashlib
import logging
import os
import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path

from pydantic import Field

from aidub.contracts.base import ContractModel, Identifier

logger = logging.getLogger(__name__)


class DistributionFormat(ContractModel):
    """Container holding generated distribution export files and manifest information."""

    package_id: Identifier
    format_type: str = Field(min_length=1)  # "DCP", "BROADCAST_MXF", "OTT_HLS_DASH"
    target_languages: list[str] = Field(default_factory=list)
    audio_channel_layout: str = Field(default="5.1_Surround", max_length=32)
    manifest_file_path: str = Field(min_length=1)
    checksum_sha256: str = Field(min_length=64, max_length=64)


class DistributionPackageExporter:
    """
    Exports studio distribution delivery packages through configured mastering tools.
    """

    def __init__(self, output_root: str | Path = "exports") -> None:
        self.output_root = Path(output_root)

    def _run_mastering_tool(
        self,
        environment_variable: str,
        *,
        project_id: str,
        expected_output: Path,
        title: str = "",
        languages: Sequence[str] = (),
    ) -> str:
        template = os.environ.get(environment_variable, "").strip()
        if not template:
            raise RuntimeError(
                f"{environment_variable} is not configured; set an industry mastering "
                "command containing {project}, {output}, {title}, or {languages} placeholders"
            )
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            token.format(
                project=project_id,
                output=str(expected_output.resolve()),
                title=title,
                languages=",".join(languages),
            )
            for token in shlex.split(template, posix=os.name != "nt")
        ]
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.returncode != 0:
            details = (process.stderr or process.stdout)[-2_000:]
            raise RuntimeError(
                f"distribution mastering failed with exit code {process.returncode}: {details}"
            )
        if not expected_output.is_file() or expected_output.stat().st_size == 0:
            raise RuntimeError(
                f"mastering command did not create the expected artifact: {expected_output}"
            )
        with expected_output.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def export_dcp_manifest(
        self, project_id: str, title: str, languages: Sequence[str]
    ) -> DistributionFormat:
        """
        Generate Digital Cinema Package (DCP) XML CPL manifest.
        """
        pid = Identifier(project_id)
        pkg_id = Identifier(f"dcp_{project_id}")
        manifest_path = self.output_root / project_id / "dcp_cpl.xml"
        sha256 = self._run_mastering_tool(
            "AIDUB_DCP_COMMAND",
            project_id=project_id,
            expected_output=manifest_path,
            title=title,
            languages=languages,
        )

        logger.info("distribution_exporter: generated DCP manifest for %s (Title: %s)", pid, title)
        return DistributionFormat(
            package_id=pkg_id,
            format_type="DCP",
            target_languages=list(languages),
            audio_channel_layout="5.1_Surround",
            manifest_file_path=str(manifest_path),
            checksum_sha256=sha256,
        )

    def export_broadcast_layback(
        self, project_id: str, channel_layout: str = "7.1_Surround"
    ) -> DistributionFormat:
        """
        Generate multi-channel broadcast MXF/ProRes master audio layback.
        """
        pid = Identifier(project_id)
        pkg_id = Identifier(f"mxf_{project_id}")
        manifest_path = self.output_root / project_id / "master_layback.mxf"
        sha256 = self._run_mastering_tool(
            "AIDUB_MXF_COMMAND",
            project_id=project_id,
            expected_output=manifest_path,
        )

        logger.info(
            "distribution_exporter: generated Broadcast MXF layback for %s (%s)",
            pid,
            channel_layout,
        )
        return DistributionFormat(
            package_id=pkg_id,
            format_type="BROADCAST_MXF",
            target_languages=[],
            audio_channel_layout=channel_layout,
            manifest_file_path=str(manifest_path),
            checksum_sha256=sha256,
        )

    def export_ott_streaming_package(
        self, project_id: str, languages: Sequence[str]
    ) -> DistributionFormat:
        """
        Generate HLS / DASH multi-language web streaming manifest package with WebVTT subtitles.
        """
        pid = Identifier(project_id)
        pkg_id = Identifier(f"ott_{project_id}")
        manifest_path = self.output_root / project_id / "master_stream.m3u8"
        sha256 = self._run_mastering_tool(
            "AIDUB_OTT_COMMAND",
            project_id=project_id,
            expected_output=manifest_path,
            languages=languages,
        )

        logger.info("distribution_exporter: generated OTT HLS/DASH manifest for %s", pid)
        return DistributionFormat(
            package_id=pkg_id,
            format_type="OTT_HLS_DASH",
            target_languages=list(languages),
            audio_channel_layout="Stereo",
            manifest_file_path=str(manifest_path),
            checksum_sha256=sha256,
        )


__all__ = [
    "DistributionFormat",
    "DistributionPackageExporter",
]
