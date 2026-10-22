"""KrillinAI-style Resumable Pipeline Manifest State Machine (aidub_manifest.json)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "aidub_manifest.json"


@dataclass
class StageStatus:
    """Status tracking for an individual pipeline execution stage."""

    ok: bool
    error: str = ""
    duration_ms: int = 0
    updated_at: str = ""


@dataclass
class PipelineOutputs:
    """Complete output file paths generated across all dubbing stages."""

    origin_video: str = ""
    origin_audio: str = ""
    origin_srt: str = ""
    target_srt: str = ""
    bilingual_srt: str = ""
    dubbed_vocals: str = ""
    dubbed_audio: str = ""
    dubbed_video: str = ""
    lipsynced_video: str = ""
    bench_json: str = ""
    transcript_json: str = ""


@dataclass
class PipelineManifest:
    """
    Stage-tracking state machine for fully restartable dubbing pipeline runs.

    Saved as ``aidub_manifest.json`` after every stage completes. If a job is
    interrupted, subsequent runs load the manifest and skip already completed stages.
    """

    task_id: str
    work_dir: str
    input_url: str = ""
    origin_language: str = ""
    target_language: str = "bn"
    caption_source: str = ""
    pipeline_version: int = 0
    source_signature: str = ""
    config_signature: str = ""
    outputs: PipelineOutputs = field(default_factory=PipelineOutputs)
    stages: dict[str, StageStatus] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def apply_default_outputs(self) -> None:
        """Pre-allocate standard output file paths in work_dir."""
        w = Path(self.work_dir)
        w.mkdir(parents=True, exist_ok=True)

        self.outputs.origin_video = str(w / "origin_video.mp4")
        self.outputs.origin_audio = str(w / "origin_audio.wav")
        self.outputs.origin_srt = str(w / "origin_language.srt")
        self.outputs.target_srt = str(w / "target_language.srt")
        self.outputs.bilingual_srt = str(w / "bilingual.srt")
        self.outputs.dubbed_vocals = str(w / "dubbed_vocals.wav")
        self.outputs.dubbed_audio = str(w / "dubbed_audio.m4a")
        self.outputs.dubbed_video = str(w / "dubbed_video.mp4")
        self.outputs.lipsynced_video = str(w / "lipsynced_video.mp4")
        self.outputs.bench_json = str(w / "bench.json")
        self.outputs.transcript_json = str(w / "transcript.json")

    def mark_stage(self, stage_name: str, ok: bool, error: str = "", duration_ms: int = 0) -> None:
        """Mark completion status of a pipeline stage."""
        self.stages[stage_name] = StageStatus(
            ok=ok,
            error=error,
            duration_ms=duration_ms,
            updated_at=datetime.now(UTC).isoformat(),
        )

    def is_stage_completed(self, stage_name: str) -> bool:
        """Return True if stage has executed successfully."""
        st = self.stages.get(stage_name)
        return st is not None and st.ok

    def save(self) -> None:
        """Atomic write of manifest to disk."""
        manifest_path = Path(self.work_dir) / MANIFEST_FILENAME
        data = {
            "task_id": self.task_id,
            "work_dir": self.work_dir,
            "input_url": self.input_url,
            "origin_language": self.origin_language,
            "target_language": self.target_language,
            "caption_source": self.caption_source,
            "pipeline_version": self.pipeline_version,
            "source_signature": self.source_signature,
            "config_signature": self.config_signature,
            "outputs": asdict(self.outputs),
            "stages": {k: asdict(v) for k, v in self.stages.items()},
            "warnings": self.warnings,
        }

        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, encoding="utf-8", dir=self.work_dir
        ) as tmp:
            tmp.write(json_str)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name

        shutil.copyfile(tmp_name, str(manifest_path))
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass

    @classmethod
    def load(cls, work_dir: Path | str, task_id: str = "default_task") -> PipelineManifest:
        """Load existing manifest from work_dir or return new instance."""
        manifest_path = Path(work_dir) / MANIFEST_FILENAME
        if not manifest_path.exists():
            m = cls(task_id=task_id, work_dir=str(work_dir))
            m.apply_default_outputs()
            return m

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            outputs = PipelineOutputs(**data.get("outputs", {}))
            stages = {k: StageStatus(**v) for k, v in data.get("stages", {}).items()}
            return cls(
                task_id=data.get("task_id", task_id),
                work_dir=data.get("work_dir", str(work_dir)),
                input_url=data.get("input_url", ""),
                origin_language=data.get("origin_language", ""),
                target_language=data.get("target_language", "bn"),
                caption_source=data.get("caption_source", ""),
                pipeline_version=int(data.get("pipeline_version", 0)),
                source_signature=data.get("source_signature", ""),
                config_signature=data.get("config_signature", ""),
                outputs=outputs,
                stages=stages,
                warnings=data.get("warnings", []),
            )
        except Exception as exc:
            logger.warning("Error loading manifest (%s) — creating fresh: %s", manifest_path, exc)
            m = cls(task_id=task_id, work_dir=str(work_dir))
            m.apply_default_outputs()
            return m


__all__ = ["MANIFEST_FILENAME", "PipelineManifest", "PipelineOutputs", "StageStatus"]
