from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from for_us_api.models import (
    CreateSnapshotRequest,
    CreateSnapshotResponse,
    RecommendationPayload,
    RecommendationItem,
    StoredSnapshot,
)


def test_create_snapshot_request_accepts_extension_shape() -> None:
    request = CreateSnapshotRequest.model_validate(
        {
            "capturedAt": "2026-02-17T11:00:00Z",
            "pageUrl": "https://www.youtube.com/",
            "videos": [
                {
                    "videoHash": "lzChIIJMpGk",
                    "title": "deadlock: items for idiot",
                    "channelName": "chalant",
                    "channelLink": "https://www.youtube.com/@itschalant",
                    "channelAvatar": "https://yt3.ggpht.com/avatar",
                    "publishedAt": "2026-02-14T11:00:00Z",
                    "viewCount": 81000,
                }
            ],
            "shorts": [{"videoHash": "dQw4w9WgXcQ", "title": "Short title"}],
        }
    )

    assert request.videos[0].video_hash == "lzChIIJMpGk"
    assert request.videos[0].view_count == 81000
    assert request.shorts[0].video_hash == "dQw4w9WgXcQ"
    assert request.page_url is not None


def test_recommendation_payload_rejects_invalid_hash() -> None:
    with pytest.raises(ValidationError):
        RecommendationPayload.model_validate(
            {"videos": [{"videoHash": "invalid", "title": "x"}], "shorts": []}
        )


def test_recommendation_payload_rejects_duplicates() -> None:
    with pytest.raises(ValidationError):
        RecommendationPayload.model_validate(
            {
                "videos": [
                    {"videoHash": "lzChIIJMpGk", "title": "A"},
                    {"videoHash": "lzChIIJMpGk", "title": "B"},
                ],
                "shorts": [],
            }
        )


def test_recommendation_payload_rejects_too_many_items() -> None:
    too_many_videos = [
        {"videoHash": f"v{index:010d}", "title": f"Video {index}"} for index in range(201)
    ]
    with pytest.raises(ValidationError):
        RecommendationPayload.model_validate({"videos": too_many_videos, "shorts": []})


def test_recommendation_payload_accepts_hash_only_entries_for_backward_compatibility() -> None:
    payload = RecommendationPayload.model_validate(
        {"videos": ["lzChIIJMpGk"], "shorts": ["dQw4w9WgXcQ"]}
    )
    assert payload.videos == [RecommendationItem(videoHash="lzChIIJMpGk", title="lzChIIJMpGk")]
    assert payload.shorts == [RecommendationItem(videoHash="dQw4w9WgXcQ", title="dQw4w9WgXcQ")]


def test_create_snapshot_response_aliases() -> None:
    response = CreateSnapshotResponse(
        hash="abc12345",
        expiresAt=datetime(2026, 2, 24, tzinfo=timezone.utc),
        removeToken="A" * 32,
        url="https://myfyp.link/abc12345",
        removeUrl="https://myfyp.link/api/snapshots/abc12345/remove/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    )

    dumped = response.model_dump(by_alias=True)
    assert dumped["hash"] == "abc12345"
    assert dumped["expiresAt"] == datetime(2026, 2, 24, tzinfo=timezone.utc)
    assert dumped["removeToken"] == "A" * 32
    assert str(dumped["url"]) == "https://myfyp.link/abc12345"
    assert str(dumped["removeUrl"]).endswith("/remove/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")


def test_stored_snapshot_model() -> None:
    snapshot = StoredSnapshot(
        hash="abc12345",
        created_at=datetime(2026, 2, 17, tzinfo=timezone.utc),
        expires_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        payload=CreateSnapshotRequest.model_validate(
            {"videos": [{"videoHash": "lzChIIJMpGk", "title": "Example title"}], "shorts": []}
        ),
    )

    assert snapshot.hash == "abc12345"
    assert snapshot.payload.videos[0].video_hash == "lzChIIJMpGk"
