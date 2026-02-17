# pyright: reportPrivateUsage=false, reportDeprecated=false

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine
from datetime import datetime, timedelta, timezone
from typing import TypeVar, cast

import pytest

from for_us_shared.abuse import AbuseConfig
from for_us_shared.models import CreateSnapshotRequest
from for_us_worker import d1_abuse, d1_store

from .helpers import FakeEnv


T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:
    return asyncio.run(cast(Coroutine[object, object, T], coro))


def _payload() -> CreateSnapshotRequest:
    return CreateSnapshotRequest.parse_obj(
        {"videos": [{"videoHash": "lzChIIJMpGk", "title": "Video"}], "shorts": []}
    )


def test_d1_store_create_get_missing_and_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    env = FakeEnv()
    now = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(d1_store, "_generate_hash", lambda: "AbcdEf123456")
    created = _run(d1_store.create_snapshot(env, _payload(), now=now))
    assert created.hash == "AbcdEf123456"

    present = _run(d1_store.get_snapshot_by_hash(env, "AbcdEf123456", now=now))
    assert present.snapshot is not None
    assert present.is_expired is False

    missing = _run(d1_store.get_snapshot_by_hash(env, "doesnotexist", now=now))
    assert missing.snapshot is None
    assert missing.is_expired is False

    expired_time = now + timedelta(days=8)
    expired = _run(d1_store.get_snapshot_by_hash(env, "AbcdEf123456", now=expired_time))
    assert expired.snapshot is None
    assert expired.is_expired is True


def test_d1_store_create_snapshot_raises_after_collisions(monkeypatch: pytest.MonkeyPatch) -> None:
    env = FakeEnv()
    env.DB.snapshots["AbcdEf123456"] = {
        "hash": "AbcdEf123456",
        "created_at": "2026-02-17T00:00:00+00:00",
        "expires_at": "2026-02-24T00:00:00+00:00",
        "payload_json": '{"videos":[],"shorts":[]}',
    }

    monkeypatch.setattr(d1_store, "_generate_hash", lambda: "AbcdEf123456")

    with pytest.raises(RuntimeError):
        _run(d1_store.create_snapshot(env, _payload(), now=datetime(2026, 2, 17, tzinfo=timezone.utc)))


def test_d1_store_delete_expired_and_helpers() -> None:
    env = FakeEnv()
    env.DB.snapshots["oldhash123456"] = {
        "hash": "oldhash123456",
        "created_at": "2026-02-01T00:00:00+00:00",
        "expires_at": "2026-02-02T00:00:00+00:00",
        "payload_json": '{"videos":[],"shorts":[]}',
    }

    deleted = _run(d1_store.delete_expired_snapshots(env, now=datetime(2026, 2, 3, tzinfo=timezone.utc)))
    assert deleted == 1

    assert d1_store._extract_changes({"meta": {"changes": 2}}) == 2
    assert d1_store._extract_changes({"meta": {"changes": 2.0}}) == 2
    assert d1_store._extract_changes({"meta": {"changes": "2"}}) == 0
    assert d1_store._extract_changes({}) == 0

    assert d1_store._to_utc(datetime(2026, 2, 17, 12, 0)).tzinfo == timezone.utc

    class _Row:
        def to_py(self) -> dict[str, str]:
            return {"hash": "h"}

    assert d1_store._to_mapping(_Row()) == {"hash": "h"}
    assert d1_store._to_mapping({"hash": "h"}) == {"hash": "h"}
    assert d1_store._to_mapping(object()) is None

    with pytest.raises(ValueError):
        d1_store._require_str({"hash": 123}, "hash")


def test_d1_abuse_rate_limits_quotas_and_cleanup() -> None:
    env = FakeEnv()
    now = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)

    cfg = AbuseConfig(post_requests_per_minute=1, read_requests_per_minute=1, write_quota_per_day_per_ip=1)
    create_first = _run(d1_abuse.allow_snapshot_create(env, "198.51.100.10", now=now, config=cfg))
    assert create_first.allowed is True

    create_second = _run(d1_abuse.allow_snapshot_create(env, "198.51.100.10", now=now, config=cfg))
    assert create_second.allowed is False
    assert "Rate limit exceeded" in create_second.reason

    # Different minute avoids rate limiter and exercises daily quota path.
    create_third = _run(
        d1_abuse.allow_snapshot_create(
            env,
            "198.51.100.10",
            now=now + timedelta(minutes=1),
            config=cfg,
        )
    )
    assert create_third.allowed is False
    assert "Daily snapshot creation quota exceeded" in create_third.reason

    read_first = _run(d1_abuse.allow_snapshot_read(env, "198.51.100.20", now=now, config=cfg))
    read_second = _run(d1_abuse.allow_snapshot_read(env, "198.51.100.20", now=now, config=cfg))
    assert read_first.allowed is True
    assert read_second.allowed is False

    stale_rate_key = (d1_abuse._hash_ip("198.51.100.30"), "read", "2026-02-17T08:00:00+00:00")
    env.DB.abuse_rate_limit[stale_rate_key] = 1
    env.DB.abuse_write_daily[(d1_abuse._hash_ip("198.51.100.30"), "2026-02-14")] = 1

    cleaned = _run(d1_abuse.cleanup_abuse_state(env, now=now))
    assert cleaned >= 2

    assert len(d1_abuse._hash_ip("  ")) == 64
    assert d1_abuse._extract_changes({"meta": {"changes": 3}}) == 3
    assert d1_abuse._extract_changes({"meta": {"changes": 3.0}}) == 3
    assert d1_abuse._extract_changes({"meta": {"changes": "3"}}) == 0
    assert d1_abuse._to_utc(datetime(2026, 2, 17, 12, 0)).tzinfo == timezone.utc
