from pathlib import Path
import tempfile
import pytest

from aidub.domain.project_file import (
    ProjectFile,
    SegmentModel,
    StageStatus,
    ProjectProbeInfo,
    ProjectFileSettings,
)


def test_project_file_creation_and_defaults():
    pf = ProjectFile(name="Test Movie Dub")
    assert pf.name == "Test Movie Dub"
    assert pf.version == 1
    assert pf.stage_status.extract == "pending"
    assert len(pf.segments) == 0


def test_segment_model_properties():
    seg = SegmentModel(
        id="seg_01",
        start=1.5,
        end=4.0,
        speaker="SPEAKER_01",
        original="Hello world",
        translation="ওহে বিশ্ব",
    )
    assert seg.duration == pytest.approx(2.5)
    assert seg.status == "pending"
    assert seg.qc_issues == []


def test_project_file_atomic_save_and_load():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "test_proj" / "project.json"
        pf = ProjectFile(
            name="Inception Dub",
            source_file="source.mp4",
            source_hash="sha256_mock_hash",
            settings=ProjectFileSettings(
                source_language="en",
                target_language="bn",
                asr_model_size="base",
            ),
        )
        pf.upsert_segment(
            SegmentModel(id="seg_1", start=0.0, end=2.0, original="Wake up", translation="জেগে ওঠো")
        )
        pf.upsert_segment(
            SegmentModel(id="seg_2", start=2.5, end=5.0, original="We need to go deeper", translation="আমাদের আরো গভীরে যেতে হবে")
        )

        saved_path = pf.save(target)
        assert saved_path.is_file()

        loaded = ProjectFile.load(saved_path)
        assert loaded.name == "Inception Dub"
        assert loaded.source_hash == "sha256_mock_hash"
        assert len(loaded.segments) == 2
        assert loaded.segments[0].id == "seg_1"
        assert loaded.segments[1].translation == "আমাদের আরো গভীরে যেতে হবে"

        # Verify get_segment
        found = loaded.get_segment("seg_2")
        assert found is not None
        assert found.start == 2.5
        assert loaded.get_segment("non_existent") is None

