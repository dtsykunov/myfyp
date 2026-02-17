# pyright: reportDeprecated=false, reportUnknownVariableType=false, reportUntypedFunctionDecorator=false

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pydantic import AnyUrl, BaseModel, Field, validator
else:  # pragma: no cover - runtime import path differs between pydantic v1 and v2
    try:
        from pydantic.v1 import AnyUrl, BaseModel, Field, validator
    except ImportError:  # pragma: no cover
        from pydantic import AnyUrl, BaseModel, Field, validator

_VIDEO_HASH_PATTERN = r"^[A-Za-z0-9_-]{11}$"
_SNAPSHOT_HASH_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


def _empty_recommendation_items() -> list[RecommendationItem]:
    return []


def _require_video_hash(value: str) -> str:
    if not re.fullmatch(_VIDEO_HASH_PATTERN, value):
        raise ValueError("Invalid YouTube video hash format.")
    return value


def _require_snapshot_hash(value: str) -> str:
    if not re.fullmatch(_SNAPSHOT_HASH_PATTERN, value):
        raise ValueError("Invalid snapshot hash format.")
    return value


class _Model(BaseModel):
    class Config:
        allow_mutation = False
        allow_population_by_field_name = True
        extra = "forbid"


class RecommendationItem(_Model):
    """Single recommendation entry extracted from YouTube homepage."""

    video_hash: str = Field(alias="videoHash")
    title: str = Field(min_length=1, max_length=300)
    channel_name: str | None = Field(default=None, alias="channelName", min_length=1, max_length=200)
    channel_link: AnyUrl | None = Field(default=None, alias="channelLink")
    channel_avatar: AnyUrl | None = Field(default=None, alias="channelAvatar")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    view_count: int | None = Field(default=None, alias="viewCount", ge=0)

    @validator("video_hash")
    def _validate_video_hash(cls, value: str) -> str:
        return _require_video_hash(value)


class RecommendationPayload(_Model):
    """Normalized recommendation lists extracted from YouTube homepage."""

    videos: list[RecommendationItem] = Field(default_factory=_empty_recommendation_items)
    shorts: list[RecommendationItem] = Field(default_factory=_empty_recommendation_items)

    @validator("videos", "shorts", pre=True)
    def _coerce_hash_only_entries(cls, values: object) -> object:
        if not isinstance(values, list):
            return values

        normalized: list[object] = []
        for entry in cast(list[object], values):
            if isinstance(entry, str):
                normalized.append({"videoHash": entry, "title": entry})
                continue
            normalized.append(entry)
        return normalized

    @validator("videos", "shorts")
    def _validate_unique_entries(cls, values: list[RecommendationItem]) -> list[RecommendationItem]:
        hashes = [item.video_hash for item in values]
        if len(hashes) != len(set(hashes)):
            raise ValueError("Duplicate video hashes are not allowed.")
        return values

    @validator("videos", "shorts")
    def _validate_max_entries(cls, values: list[RecommendationItem]) -> list[RecommendationItem]:
        if len(values) > 200:
            raise ValueError("Recommendation list exceeds max size of 200.")
        return values


class CreateSnapshotRequest(RecommendationPayload):
    """Payload accepted by API when creating a shared snapshot."""

    captured_at: datetime | None = Field(default=None, alias="capturedAt")
    page_url: AnyUrl | None = Field(default=None, alias="pageUrl")


class CreateSnapshotResponse(_Model):
    """Response returned after storing a snapshot."""

    hash: str
    expires_at: datetime = Field(alias="expiresAt")

    @validator("hash")
    def _validate_hash(cls, value: str) -> str:
        return _require_snapshot_hash(value)


class StoredSnapshot(_Model):
    """Internal persisted snapshot record."""

    hash: str
    created_at: datetime
    expires_at: datetime
    payload: CreateSnapshotRequest

    @validator("hash")
    def _validate_hash(cls, value: str) -> str:
        return _require_snapshot_hash(value)


def parse_create_snapshot_request_json(raw_json: str) -> CreateSnapshotRequest:
    return CreateSnapshotRequest.parse_raw(raw_json)


def model_to_json_dict(
    model: BaseModel,
    *,
    by_alias: bool = False,
    exclude_none: bool = False,
) -> dict[str, object]:
    return cast(dict[str, object], json.loads(model.json(by_alias=by_alias, exclude_none=exclude_none)))
