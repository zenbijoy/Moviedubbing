from pathlib import Path
from aidub.media.thumbnail_extractor import ThumbnailExtractor


def test_thumbnail_extractor_nonexistent_file(tmp_path: Path):
    extractor = ThumbnailExtractor(cache_dir=tmp_path / "thumb_cache")
    res = extractor.extract_thumbnail(tmp_path / "missing.mp4", 1.0)
    assert res is None

    strip = extractor.extract_filmstrip(tmp_path / "missing.mp4", 10.0, count=5)
    assert strip == []

