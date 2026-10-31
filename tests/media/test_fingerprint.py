from pathlib import Path

from aidub.media.fingerprint import fast_fingerprint, full_fingerprint


def test_fingerprints_are_deterministic_and_full_hash_changes(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes((b"movie-frame" * 20_000) + b"end")
    first_fast = fast_fingerprint(source)
    first_full = full_fingerprint(source)
    assert first_fast.fast_sha256 == first_full.fast_sha256
    assert first_full.full_sha256 is not None
    assert first_fast.byte_length == source.stat().st_size

    content = source.read_bytes()
    source.write_bytes(content[:-3] + b"END")
    second = full_fingerprint(source)
    assert second.full_sha256 != first_full.full_sha256
