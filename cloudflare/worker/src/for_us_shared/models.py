# pyright: reportDeprecated=false, reportUnknownVariableType=false, reportUntypedFunctionDecorator=false

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    from pydantic import AnyUrl, BaseModel, Field, validator
else:  # pragma: no cover - runtime import path differs between pydantic v1 and v2
    try:
        from pydantic.v1 import AnyUrl, BaseModel, Field, validator
    except ImportError:  # pragma: no cover
        from pydantic import AnyUrl, BaseModel, Field, validator

_BaseModelT = TypeVar("_BaseModelT", bound="BaseModel")

_VIDEO_HASH_PATTERN = r"^[A-Za-z0-9_-]{11}$"
_SNAPSHOT_HASH_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"
_REMOVE_TOKEN_PATTERN = r"^[A-Za-z0-9_-]{16,128}$"


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


def _require_remove_token(value: str) -> str:
    if not re.fullmatch(_REMOVE_TOKEN_PATTERN, value):
        raise ValueError("Invalid remove token format.")
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
    remove_token: str = Field(alias="removeToken")
    url: str | None = Field(default=None)
    remove_url: str | None = Field(default=None, alias="removeUrl")

    @validator("hash")
    def _validate_hash(cls, value: str) -> str:
        return _require_snapshot_hash(value)

    @validator("remove_token")
    def _validate_remove_token(cls, value: str) -> str:
        return _require_remove_token(value)


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


def parse_create_snapshot_request_json_trusted(raw_json: str) -> CreateSnapshotRequest:
    """Parse a previously validated snapshot payload quickly for read paths.

    This intentionally skips schema validation to reduce CPU spent on reads.
    Data written to storage is validated on ingest, so this parser assumes
    persisted payloads follow the expected shape. Malformed entries are ignored.
    """
    raw_payload = json.loads(raw_json)
    if not isinstance(raw_payload, dict):
        raise ValueError("Stored snapshot payload has invalid format.")
    payload_dict = cast(dict[str, object], raw_payload)

    videos = _trusted_recommendation_items(payload_dict.get("videos"))
    shorts = _trusted_recommendation_items(payload_dict.get("shorts"))
    captured_at = _parse_iso_datetime(payload_dict.get("capturedAt"))
    page_url = _optional_non_empty_string(payload_dict.get("pageUrl"))
    return _model_construct(
        CreateSnapshotRequest,
        videos=videos,
        shorts=shorts,
        captured_at=captured_at,
        page_url=page_url,
    )


def model_to_json_dict(
    model: BaseModel,
    *,
    by_alias: bool = False,
    exclude_none: bool = False,
) -> dict[str, object]:
    return cast(dict[str, object], json.loads(model.json(by_alias=by_alias, exclude_none=exclude_none)))


def model_to_json_string(
    model: BaseModel,
    *,
    by_alias: bool = False,
    exclude_none: bool = False,
    compact: bool = False,
    sort_keys: bool = False,
) -> str:
    if compact or sort_keys:
        return model.json(
            by_alias=by_alias,
            exclude_none=exclude_none,
            separators=(",", ":") if compact else None,
            sort_keys=sort_keys,
        )
    return model.json(by_alias=by_alias, exclude_none=exclude_none)


def _model_construct(model_type: type[_BaseModelT], **values: object) -> _BaseModelT:
    construct = getattr(model_type, "construct", None)
    if callable(construct):
        return cast(_BaseModelT, construct(**values))

    model_construct = getattr(model_type, "model_construct", None)  # pragma: no cover
    if callable(model_construct):  # pragma: no cover
        return cast(_BaseModelT, model_construct(**values))  # pragma: no cover

    raise RuntimeError(f"Unable to construct model for {model_type.__name__}.")  # pragma: no cover


def _trusted_recommendation_items(raw_items: object) -> list[RecommendationItem]:
    if not isinstance(raw_items, list):
        return []

    normalized_items: list[RecommendationItem] = []
    seen_hashes: set[str] = set()
    for raw_item in cast(list[object], raw_items):
        item = _trusted_recommendation_item(raw_item)
        if item is None:
            continue
        if item.video_hash in seen_hashes:
            continue
        seen_hashes.add(item.video_hash)
        normalized_items.append(item)
        if len(normalized_items) >= 200:
            break
    return normalized_items


def _trusted_recommendation_item(raw_item: object) -> RecommendationItem | None:
    if isinstance(raw_item, str):
        if not re.fullmatch(_VIDEO_HASH_PATTERN, raw_item):
            return None
        return _model_construct(RecommendationItem, video_hash=raw_item, title=raw_item)

    if not isinstance(raw_item, dict):
        return None
    item_dict = cast(dict[str, object], raw_item)

    video_hash = item_dict.get("videoHash")
    if not isinstance(video_hash, str):
        return None
    if not re.fullmatch(_VIDEO_HASH_PATTERN, video_hash):
        return None

    title = item_dict.get("title")
    normalized_title = title if isinstance(title, str) and title.strip() else video_hash
    channel_name = _optional_non_empty_string(item_dict.get("channelName"))
    channel_link = _optional_non_empty_string(item_dict.get("channelLink"))
    channel_avatar = _optional_non_empty_string(item_dict.get("channelAvatar"))
    published_at = _parse_iso_datetime(item_dict.get("publishedAt"))
    view_count = _parse_non_negative_int(item_dict.get("viewCount"))

    return _model_construct(
        RecommendationItem,
        video_hash=video_hash,
        title=normalized_title,
        channel_name=channel_name,
        channel_link=channel_link,
        channel_avatar=channel_avatar,
        published_at=published_at,
        view_count=view_count,
    )


def _parse_iso_datetime(raw_value: object) -> datetime | None:
    if not isinstance(raw_value, str):
        return None
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _optional_non_empty_string(raw_value: object) -> str | None:
    if not isinstance(raw_value, str):
        return None
    if not raw_value:
        return None
    return raw_value


def _parse_non_negative_int(raw_value: object) -> int | None:
    if not isinstance(raw_value, int):
        return None
    if isinstance(raw_value, bool):
        return None
    if raw_value < 0:
        return None
    return raw_value
