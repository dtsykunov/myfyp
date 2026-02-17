from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, StringConstraints, field_validator

VideoHash = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{11}$")]
SnapshotHash = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")]


def _empty_recommendation_items() -> list[RecommendationItem]:
    return []


class RecommendationItem(BaseModel):
    """Single recommendation entry extracted from YouTube homepage."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    video_hash: VideoHash = Field(alias="videoHash")
    title: str = Field(min_length=1, max_length=300)
    channel_name: str | None = Field(default=None, alias="channelName", min_length=1, max_length=200)
    channel_link: AnyUrl | None = Field(default=None, alias="channelLink")
    channel_avatar: AnyUrl | None = Field(default=None, alias="channelAvatar")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    view_count: int | None = Field(default=None, alias="viewCount", ge=0)


class RecommendationPayload(BaseModel):
    """Normalized recommendation lists extracted from YouTube homepage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    videos: list[RecommendationItem] = Field(default_factory=_empty_recommendation_items, max_length=200)
    shorts: list[RecommendationItem] = Field(default_factory=_empty_recommendation_items, max_length=200)

    @field_validator("videos", "shorts", mode="before")
    @classmethod
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

    @field_validator("videos", "shorts")
    @classmethod
    def _validate_unique_entries(cls, values: list[RecommendationItem]) -> list[RecommendationItem]:
        hashes = [item.video_hash for item in values]
        if len(hashes) != len(set(hashes)):
            raise ValueError("Duplicate video hashes are not allowed.")
        return values


class CreateSnapshotRequest(RecommendationPayload):
    """Payload accepted by API when creating a shared snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    captured_at: datetime | None = Field(default=None, alias="capturedAt")
    page_url: AnyUrl | None = Field(default=None, alias="pageUrl")


class CreateSnapshotResponse(BaseModel):
    """Response returned after storing a snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    hash: SnapshotHash
    expires_at: datetime = Field(alias="expiresAt")


class StoredSnapshot(BaseModel):
    """Internal persisted snapshot record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hash: SnapshotHash
    created_at: datetime
    expires_at: datetime
    payload: CreateSnapshotRequest
