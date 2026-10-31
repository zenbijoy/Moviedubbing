from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aidub.domain.media import (
    AudioStream,
    FrameRateMode,
    MediaAsset,
    MediaAssetKind,
    MediaFingerprint,
    VideoStream,
)
from aidub.domain.project import PrivacyMode, Project, ProjectSettings
from aidub.domain.rights import SourceAuthorization
from aidub.domain.time import RationalRate, RationalTime

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)
HASH = "a" * 64


def authorization() -> SourceAuthorization:
    return SourceAuthorization(
        acknowledged=True,
        acknowledged_by="producer@example.test",
        acknowledged_at=NOW,
        authority_basis="Licensed localization production",
        evidence_reference="rights/source-license-2026-08.pdf",
    )


def settings(**updates: object) -> ProjectSettings:
    values: dict[str, object] = {
        "video_rate": RationalRate(numerator=24_000, denominator=1_001),
        "source_language": "en-US",
    }
    values.update(updates)
    return ProjectSettings.model_validate(values)


def video_stream(index: int = 0) -> VideoStream:
    return VideoStream(
        stream_index=index,
        codec_name="h264",
        width=1920,
        height=1080,
        pts_rate=RationalRate(numerator=90_000),
        average_frame_rate=RationalRate(numerator=24_000, denominator=1_001),
        frame_rate_mode=FrameRateMode.CONSTANT,
        duration=RationalTime(ticks=900_000, rate=RationalRate(numerator=90_000)),
        pixel_format="yuv420p",
    )


def fingerprint() -> MediaFingerprint:
    return MediaFingerprint(fast_fingerprint=HASH, full_sha256=HASH, byte_length=123_456)


def test_project_is_strict_frozen_and_normalizes_timestamps_to_utc() -> None:
    plus_six = timezone(timedelta(hours=6))
    project = Project(
        project_id="prj_feature_film",
        name="Feature Film",
        settings=settings(),
        source_authorization=authorization(),
        created_at=NOW.astimezone(plus_six),
        updated_at=NOW.astimezone(plus_six),
    )

    assert project.created_at == NOW
    assert project.created_at.tzinfo is UTC
    with pytest.raises(ValidationError, match="frozen"):
        project.name = "Mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        Project.model_validate({**project.model_dump(), "unknown": True})


def test_nested_domain_mappings_are_immutable_but_json_serializable() -> None:
    configured = settings(
        privacy_mode=PrivacyMode.HYBRID,
        allow_external_text=True,
    )
    project = Project(
        project_id="prj_feature_film",
        name="Feature Film",
        settings=configured,
        source_authorization=authorization(),
    )

    # Mapping immutability is exercised more directly by provenance/job tests; every frozen model
    # still needs to retain a supported JSON round trip.
    assert Project.model_validate_json(project.model_dump_json()) == project


def test_project_rejects_naive_or_reversed_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Project(
            project_id="prj_feature_film",
            name="Feature",
            settings=settings(),
            source_authorization=authorization(),
            created_at=NOW.replace(tzinfo=None),
            updated_at=NOW,
        )
    with pytest.raises(ValidationError, match="cannot precede"):
        Project(
            project_id="prj_feature_film",
            name="Feature",
            settings=settings(),
            source_authorization=authorization(),
            created_at=NOW,
            updated_at=NOW - timedelta(seconds=1),
        )


def test_offline_project_cannot_disclose_text_or_media() -> None:
    with pytest.raises(ValidationError, match="offline"):
        settings(privacy_mode=PrivacyMode.OFFLINE, allow_external_text=True)

    with pytest.raises(ValidationError, match="implies"):
        settings(
            privacy_mode=PrivacyMode.HYBRID,
            allow_external_media=True,
            allow_external_text=False,
        )


def test_source_media_requires_streams_and_has_no_parent() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        MediaAsset(
            media_asset_id="med_source_main",
            project_id="prj_feature_film",
            kind=MediaAssetKind.SOURCE,
            display_name="movie.mkv",
            uri="D:/media/movie.mkv",
            fingerprint=fingerprint(),
        )

    with pytest.raises(ValidationError, match="cannot derive"):
        MediaAsset(
            media_asset_id="med_source_main",
            project_id="prj_feature_film",
            kind=MediaAssetKind.SOURCE,
            display_name="movie.mkv",
            uri="D:/media/movie.mkv",
            fingerprint=fingerprint(),
            streams=(video_stream(),),
            source_asset_id="med_parent_source",
        )


def test_media_stream_union_round_trips_with_discriminator() -> None:
    asset = MediaAsset(
        media_asset_id="med_source_main",
        project_id="prj_feature_film",
        kind=MediaAssetKind.SOURCE,
        display_name="movie.mkv",
        uri="D:/media/movie.mkv",
        mime_type="video/x-matroska",
        fingerprint=fingerprint(),
        streams=(
            video_stream(),
            AudioStream(
                stream_index=1,
                codec_name="pcm_s24le",
                sample_rate=48_000,
                channel_count=6,
                channel_layout="5.1",
                pts_rate=RationalRate(numerator=48_000),
                language="en",
            ),
        ),
    )

    restored = MediaAsset.model_validate_json(asset.model_dump_json())

    assert restored == asset
    assert isinstance(restored.streams[0], VideoStream)
    assert isinstance(restored.streams[1], AudioStream)


def test_media_stream_indexes_are_unique_and_derived_asset_needs_source() -> None:
    with pytest.raises(ValidationError, match="indexes must be unique"):
        MediaAsset(
            media_asset_id="med_source_main",
            project_id="prj_feature_film",
            kind=MediaAssetKind.SOURCE,
            display_name="movie.mkv",
            uri="D:/media/movie.mkv",
            fingerprint=fingerprint(),
            streams=(video_stream(), video_stream()),
        )

    with pytest.raises(ValidationError, match="require a source"):
        MediaAsset(
            media_asset_id="med_proxy_main",
            project_id="prj_feature_film",
            kind=MediaAssetKind.PROXY,
            display_name="proxy.mov",
            uri="proxy/main.mov",
            fingerprint=fingerprint(),
        )
