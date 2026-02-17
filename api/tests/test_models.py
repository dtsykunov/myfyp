from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from for_us_api.models import (
    CreateSnapshotRequest,
    CreateSnapshotResponse,
    RecommendationPayload,
    StoredSnapshot,
)


def test_create_snapshot_request_accepts_extension_shape() -> None:
    request = CreateSnapshotRequest.model_validate(
        {
            "capturedAt": "2026-02-17T11:00:00Z",
            "pageUrl": "https://www.youtube.com/",
            "videos": ["lzChIIJMpGk"],
            "shorts": ["dQw4w9WgXcQ"],
        }
    )

    assert request.videos == ["lzChIIJMpGk"]
    assert request.shorts == ["dQw4w9WgXcQ"]
    assert request.page_url is not None


def test_recommendation_payload_rejects_invalid_hash() -> None:
    with pytest.raises(ValidationError):
        RecommendationPayload(videos=["invalid"], shorts=[])


def test_recommendation_payload_rejects_duplicates() -> None:
    with pytest.raises(ValidationError):
        RecommendationPayload(videos=["lzChIIJMpGk", "lzChIIJMpGk"], shorts=[])


def test_create_snapshot_response_aliases() -> None:
    response = CreateSnapshotResponse(
        hash="abc12345",
        expiresAt=datetime(2026, 2, 24, tzinfo=timezone.utc),
    )

    dumped = response.model_dump(by_alias=True)
    assert dumped["hash"] == "abc12345"
    assert dumped["expiresAt"] == datetime(2026, 2, 24, tzinfo=timezone.utc)


def test_stored_snapshot_model() -> None:
    snapshot = StoredSnapshot(
        hash="abc12345",
        created_at=datetime(2026, 2, 17, tzinfo=timezone.utc),
        expires_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        payload=RecommendationPayload(videos=["lzChIIJMpGk"], shorts=[]),
    )

    assert snapshot.hash == "abc12345"
    assert snapshot.payload.videos == ["lzChIIJMpGk"]

