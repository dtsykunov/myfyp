# pyright: reportPrivateUsage=false

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from for_us_api import abuse
from for_us_api.formatting import format_compact_views, format_relative_time, to_utc
from for_us_api.http_cache import if_none_match_matches
from for_us_api.models import CreateSnapshotRequest
from for_us_api.models import RecommendationItem, StoredSnapshot
from for_us_api.store import SnapshotStore


def _sample_payload() -> CreateSnapshotRequest:
    return CreateSnapshotRequest(
        videos=[RecommendationItem(videoHash="lzChIIJMpGk", title="Video")],
        shorts=[],
    )


def _sample_snapshot(snapshot_hash: str, expires_at: datetime) -> StoredSnapshot:
    return StoredSnapshot(
        hash=snapshot_hash,
        created_at=datetime(2026, 2, 17, 11, 0, tzinfo=timezone.utc),
        expires_at=expires_at,
        payload=_sample_payload(),
    )


def test_abuse_config_validates_positive_limits() -> None:
    with pytest.raises(ValueError):
        abuse.AbuseConfig(max_snapshot_body_bytes=0)
    with pytest.raises(ValueError):
        abuse.AbuseConfig(post_requests_per_minute=0)
    with pytest.raises(ValueError):
        abuse.AbuseConfig(read_requests_per_minute=0)
    with pytest.raises(ValueError):
        abuse.AbuseConfig(write_quota_per_day_per_ip=0)


def test_fixed_window_limiter_and_daily_quota_reset() -> None:
    times = iter([0.0, 1.0, 61.0])
    limiter = abuse._FixedWindowLimiter(limit=1, window_seconds=60, time_provider=lambda: next(times))
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False
    assert limiter.allow("ip") is True

    days = iter([date(2026, 2, 17), date(2026, 2, 17), date(2026, 2, 18)])
    quota = abuse._DailyQuotaLimiter(limit=1, date_provider=lambda: next(days))
    assert quota.allow("ip") is True
    assert quota.allow("ip") is False
    assert quota.allow("ip") is True


def test_in_memory_abuse_guard_enforces_create_and_read_limits() -> None:
    config = abuse.AbuseConfig(post_requests_per_minute=1, read_requests_per_minute=1, write_quota_per_day_per_ip=1)
    guard = abuse.InMemoryAbuseGuard(config=config)

    assert guard.allow_snapshot_create("198.51.100.1") == (True, "")
    assert guard.allow_snapshot_create("198.51.100.1") == (
        False,
        "Rate limit exceeded for snapshot creation.",
    )

    assert guard.allow_snapshot_read("198.51.100.2") == (True, "")
    assert guard.allow_snapshot_read("198.51.100.2") == (
        False,
        "Rate limit exceeded for snapshot retrieval.",
    )


def test_formatting_and_cache_matching_cover_edge_paths() -> None:
    naive = datetime(2026, 2, 17, 12, 0)
    assert to_utc(naive).tzinfo == timezone.utc

    reference = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)
    future = datetime(2026, 2, 17, 13, 0, tzinfo=timezone.utc)
    assert format_relative_time(future, reference) == "just now"

    assert format_compact_views(9_950) == "9.9K views"
    assert format_compact_views(1_000_000_000) == "1B views"

    assert if_none_match_matches("*", '"api-hash"')


def test_snapshot_store_validates_limits() -> None:
    with pytest.raises(ValueError):
        SnapshotStore(database_path=Path("x.db"), retention_days=0)
    with pytest.raises(ValueError):
        SnapshotStore(database_path=Path("x.db"), cleanup_interval_writes=0)
    with pytest.raises(ValueError):
        SnapshotStore(database_path=Path("x.db"), max_cached_snapshots=0)


def test_snapshot_store_raises_after_hash_collisions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SnapshotStore(database_path=tmp_path / "snapshots.db")
    store.initialize()

    def _always_false(*args: object, **kwargs: object) -> bool:
        del args, kwargs
        return False

    monkeypatch.setattr(store, "_try_insert_snapshot", _always_false)

    with pytest.raises(RuntimeError):
        store.create_snapshot(_sample_payload(), now=datetime(2026, 2, 17, tzinfo=timezone.utc))


def test_try_insert_snapshot_handles_duplicate_hash(tmp_path: Path) -> None:
    store = SnapshotStore(database_path=tmp_path / "snapshots.db")
    store.initialize()

    created_at = datetime(2026, 2, 17, 11, 0, tzinfo=timezone.utc)
    expires_at = datetime(2026, 2, 24, 11, 0, tzinfo=timezone.utc)
    payload_json = '{"videos":[],"shorts":[]}'

    assert store._try_insert_snapshot("dupeHash1", created_at, expires_at, payload_json) is True
    assert store._try_insert_snapshot("dupeHash1", created_at, expires_at, payload_json) is False


def test_get_snapshot_reads_from_db_and_populates_cache(tmp_path: Path) -> None:
    store = SnapshotStore(database_path=tmp_path / "snapshots.db")
    store.initialize()

    created = store.create_snapshot(_sample_payload())
    store._snapshot_cache.clear()

    snapshot, expired = store.get_snapshot(created.hash)
    assert expired is False
    assert snapshot is not None
    assert created.hash in store._snapshot_cache


def test_register_write_triggers_cleanup_and_cache_eviction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SnapshotStore(
        database_path=tmp_path / "snapshots.db",
        cleanup_interval_writes=1,
        max_cached_snapshots=1,
    )
    store.initialize()

    cleanup_calls: list[datetime | None] = []

    def _fake_delete_expired(now: datetime | None = None) -> int:
        cleanup_calls.append(now)
        return 0

    monkeypatch.setattr(store, "delete_expired", _fake_delete_expired)
    store._register_write_and_cleanup_if_needed()
    assert cleanup_calls == [None]

    soon = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)
    later = datetime(2026, 2, 17, 13, 0, tzinfo=timezone.utc)
    store._cache_snapshot(_sample_snapshot("Abcd1234", soon))
    store._cache_snapshot(_sample_snapshot("Efgh5678", later))

    assert "Abcd1234" not in store._snapshot_cache
    assert "Efgh5678" in store._snapshot_cache
