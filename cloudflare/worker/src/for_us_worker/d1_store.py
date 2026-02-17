from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import secrets
import string
from typing import cast

from for_us_shared.models import CreateSnapshotRequest, StoredSnapshot

from for_us_worker.types import WorkerEnv

_HASH_ALPHABET = string.ascii_letters + string.digits
_HASH_LENGTH = 12
_MAX_HASH_ATTEMPTS = 5
_RETENTION_DAYS = 7


@dataclass(frozen=True)
class SnapshotLookupResult:
    snapshot: StoredSnapshot | None
    is_expired: bool


async def create_snapshot(
    env: WorkerEnv,
    payload: CreateSnapshotRequest,
    now: datetime | None = None,
) -> StoredSnapshot:
    created_at = _to_utc(now or datetime.now(timezone.utc))
    expires_at = created_at + timedelta(days=_RETENTION_DAYS)
    payload_json = json.dumps(
        payload.model_dump(by_alias=True, mode="json", exclude_none=True),
        separators=(",", ":"),
        sort_keys=True,
    )

    for _ in range(_MAX_HASH_ATTEMPTS):
        snapshot_hash = _generate_hash()
        inserted = await _try_insert_snapshot(env, snapshot_hash, created_at, expires_at, payload_json)
        if inserted:
            return StoredSnapshot(
                hash=snapshot_hash,
                created_at=created_at,
                expires_at=expires_at,
                payload=payload,
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
    payload = CreateSnapshotRequest.model_validate_json(_require_str(mapping, "payload_json"))

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


async def delete_snapshot_by_hash(env: WorkerEnv, snapshot_hash: str) -> None:
    await env.DB.prepare(
        """
        DELETE FROM snapshots
        WHERE hash = ?
        """
    ).bind(snapshot_hash).run()


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
) -> bool:
    result = await env.DB.prepare(
        """
        INSERT OR IGNORE INTO snapshots (hash, created_at, expires_at, payload_json)
        VALUES (?, ?, ?, ?)
        """
    ).bind(snapshot_hash, created_at.isoformat(), expires_at.isoformat(), payload_json).run()
    return _extract_changes(result) > 0


def _generate_hash() -> str:
    return "".join(secrets.choice(_HASH_ALPHABET) for _ in range(_HASH_LENGTH))


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
    if isinstance(result, Mapping):
        result_mapping = cast(Mapping[str, object], result)
        meta = result_mapping.get("meta")
        if isinstance(meta, Mapping):
            meta_mapping = cast(Mapping[str, object], meta)
            changes = meta_mapping.get("changes")
            if isinstance(changes, int):
                return changes
    return 0


def _require_str(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Expected '{key}' to be a string.")
    return value
