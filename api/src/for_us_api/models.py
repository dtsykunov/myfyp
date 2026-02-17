from datetime import datetime
from typing import Annotated

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, StringConstraints, field_validator

VideoHash = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{11}$")]
SnapshotHash = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")]


class RecommendationPayload(BaseModel):
    """Normalized recommendation lists extracted from YouTube homepage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    videos: list[VideoHash] = Field(default_factory=list, max_length=200)
    shorts: list[VideoHash] = Field(default_factory=list, max_length=200)

    @field_validator("videos", "shorts")
    @classmethod
    def _validate_unique_entries(cls, values: list[VideoHash]) -> list[VideoHash]:
        if len(values) != len(set(values)):
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
