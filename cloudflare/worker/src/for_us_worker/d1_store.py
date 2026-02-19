from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hmac
import json
import math
import secrets
import string
from typing import cast

from for_us_shared.models import (
    CreateSnapshotRequest,
    StoredSnapshot,
    model_to_json_dict,
    parse_create_snapshot_request_json,
)

from for_us_worker.types import WorkerEnv

_HASH_ALPHABET = string.ascii_letters + string.digits
_HASH_LENGTH = 12
_REMOVE_TOKEN_ALPHABET = string.ascii_letters + string.digits + "_-"
_REMOVE_TOKEN_LENGTH = 32
_MAX_HASH_ATTEMPTS = 5
_RETENTION_DAYS = 7


@dataclass(frozen=True)
class SnapshotLookupResult:
    snapshot: StoredSnapshot | None
    is_expired: bool


@dataclass(frozen=True)
class SnapshotJsonLookupResult:
    payload_json: str | None
    expires_at: datetime | None
    is_expired: bool


@dataclass(frozen=True)
class CreatedSnapshot:
    hash: str
    created_at: datetime
    expires_at: datetime
    payload: CreateSnapshotRequest
    delete_token: str


class DeleteSnapshotResult(Enum):
    DELETED = "deleted"
    NOT_FOUND = "not_found"
    INVALID_TOKEN = "invalid_token"


async def create_snapshot(
    env: WorkerEnv,
    payload: CreateSnapshotRequest,
    now: datetime | None = None,
) -> CreatedSnapshot:
    created_at = _to_utc(now or datetime.now(timezone.utc))
    expires_at = created_at + timedelta(days=_RETENTION_DAYS)
    remove_token = _generate_remove_token()
    payload_json = json.dumps(
        model_to_json_dict(payload, by_alias=True, exclude_none=True),
        separators=(",", ":"),
        sort_keys=True,
    )

    for _ in range(_MAX_HASH_ATTEMPTS):
        snapshot_hash = _generate_hash()
        inserted = await _try_insert_snapshot(
            env=env,
            snapshot_hash=snapshot_hash,
            created_at=created_at,
            expires_at=expires_at,
            payload_json=payload_json,
            remove_token=remove_token,
        )
        if inserted:
            return CreatedSnapshot(
                hash=snapshot_hash,
                created_at=created_at,
                expires_at=expires_at,
                payload=payload,
                delete_token=remove_token,
            )

    raise RuntimeError("Unable to persist snapshot due to hash collisions.")


async def get_snapshot_by_hash(
    env: WorkerEnv,
    snapshot_hash: str,
    now: datetime | None = None,
) -> SnapshotLookupResult:
    effective_now = _to_utc(now or datetime.now(timezone.utc))
    row = await env.DB.prepare(
        """
        SELECT hash, created_at, expires_at, payload_json
        FROM snapshots
        WHERE hash = ?
        """
    ).bind(snapshot_hash).first()

    mapping = _to_mapping(row)
    if mapping is None:
        return SnapshotLookupResult(snapshot=None, is_expired=False)

    created_at = _parse_datetime(_require_str(mapping, "created_at"))
    expires_at = _parse_datetime(_require_str(mapping, "expires_at"))
    payload = parse_create_snapshot_request_json(_require_str(mapping, "payload_json"))

    snapshot = StoredSnapshot(
        hash=_require_str(mapping, "hash"),
        created_at=created_at,
        expires_at=expires_at,
        payload=payload,
    )

    if snapshot.expires_at <= effective_now:
        await delete_snapshot_by_hash(env, snapshot_hash)
        return SnapshotLookupResult(snapshot=None, is_expired=True)

    return SnapshotLookupResult(snapshot=snapshot, is_expired=False)


async def get_snapshot_payload_json_by_hash(
    env: WorkerEnv,
    snapshot_hash: str,
    now: datetime | None = None,
) -> SnapshotJsonLookupResult:
    effective_now = _to_utc(now or datetime.now(timezone.utc))
    row = await env.DB.prepare(
        """
        SELECT hash, expires_at, payload_json
        FROM snapshots
        WHERE hash = ?
        """
    ).bind(snapshot_hash).first()

    mapping = _to_mapping(row)
    if mapping is None:
        return SnapshotJsonLookupResult(payload_json=None, expires_at=None, is_expired=False)

    expires_at = _parse_datetime(_require_str(mapping, "expires_at"))
    if expires_at <= effective_now:
        await delete_snapshot_by_hash(env, snapshot_hash)
        return SnapshotJsonLookupResult(payload_json=None, expires_at=None, is_expired=True)

    return SnapshotJsonLookupResult(
        payload_json=_require_str(mapping, "payload_json"),
        expires_at=expires_at,
        is_expired=False,
    )


async def delete_snapshot_by_hash(env: WorkerEnv, snapshot_hash: str) -> None:
    await env.DB.prepare(
        """
        DELETE FROM snapshots
        WHERE hash = ?
        """
    ).bind(snapshot_hash).run()


async def delete_snapshot_by_hash_and_token(
    env: WorkerEnv,
    snapshot_hash: str,
    remove_token: str,
) -> DeleteSnapshotResult:
    row = await env.DB.prepare(
        """
        SELECT delete_token
        FROM snapshots
        WHERE hash = ?
        """
    ).bind(snapshot_hash).first()
    mapping = _to_mapping(row)
    if mapping is None:
        return DeleteSnapshotResult.NOT_FOUND

    stored_token = mapping.get("delete_token")
    if not isinstance(stored_token, str):
        return DeleteSnapshotResult.INVALID_TOKEN
    if not hmac.compare_digest(stored_token, remove_token):
        return DeleteSnapshotResult.INVALID_TOKEN

    await delete_snapshot_by_hash(env, snapshot_hash)
    return DeleteSnapshotResult.DELETED


async def delete_expired_snapshots(env: WorkerEnv, now: datetime | None = None) -> int:
    effective_now = _to_utc(now or datetime.now(timezone.utc))
    result = await env.DB.prepare(
        """
        DELETE FROM snapshots
        WHERE expires_at <= ?
        """
    ).bind(effective_now.isoformat()).run()
    return _extract_changes(result)


async def _try_insert_snapshot(
    env: WorkerEnv,
    snapshot_hash: str,
    created_at: datetime,
    expires_at: datetime,
    payload_json: str,
    remove_token: str,
) -> bool:
    result = await env.DB.prepare(
        """
        INSERT OR IGNORE INTO snapshots (hash, created_at, expires_at, payload_json, delete_token)
        VALUES (?, ?, ?, ?, ?)
        """
    ).bind(
        snapshot_hash,
        created_at.isoformat(),
        expires_at.isoformat(),
        payload_json,
        remove_token,
    ).run()
    return _extract_changes(result) > 0


def _generate_hash() -> str:
    return "".join(secrets.choice(_HASH_ALPHABET) for _ in range(_HASH_LENGTH))


def _generate_remove_token() -> str:
    return "".join(secrets.choice(_REMOVE_TOKEN_ALPHABET) for _ in range(_REMOVE_TOKEN_LENGTH))


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return _to_utc(parsed)


def _to_mapping(row: object | None) -> Mapping[str, object] | None:
    if row is None:
        return None
    to_py = getattr(row, "to_py", None)
    if callable(to_py):
        converted = to_py()
        if isinstance(converted, Mapping):
            return cast(Mapping[str, object], converted)
    if isinstance(row, Mapping):
        return cast(Mapping[str, object], row)
    return None


def _extract_changes(result: object) -> int:
    result_mapping = _to_mapping(result)
    if result_mapping is None:
        return 0

    meta_mapping = _to_mapping(result_mapping.get("meta"))
    if meta_mapping is None:
        return 0

    changes = meta_mapping.get("changes")
    if isinstance(changes, bool):
        return 0
    if isinstance(changes, int):
        return max(changes, 0)
    if isinstance(changes, float):
        if not math.isfinite(changes):
            return 0
        return max(int(changes), 0)
    return 0


def _require_str(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Expected '{key}' to be a string.")
    return value
