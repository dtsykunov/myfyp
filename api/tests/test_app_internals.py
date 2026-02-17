# pyright: reportPrivateUsage=false

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from starlette.requests import Request

from for_us_api.abuse import AbuseConfig, InMemoryAbuseGuard
from for_us_api.app import _SnapshotHtmlCache, _client_ip, create_app
from for_us_api.models import CreateSnapshotRequest, CreateSnapshotResponse
from for_us_api.models import StoredSnapshot
from for_us_api.store import SnapshotStore


@dataclass
class _StoreStub:
    snapshot: StoredSnapshot | None
    expired: bool

    def initialize(self) -> None:
        return None

    def create_snapshot(self, payload: CreateSnapshotRequest) -> CreateSnapshotResponse:
        del payload
        return CreateSnapshotResponse(hash="Abcd1234", expiresAt=datetime(2026, 2, 24, tzinfo=timezone.utc))

    def get_snapshot(self, snapshot_hash: str) -> tuple[StoredSnapshot | None, bool]:
        del snapshot_hash
        return self.snapshot, self.expired


@dataclass
class _GuardStub:
    allow_read: bool = True
    read_reason: str = ""

    def allow_snapshot_create(self, client_ip: str) -> tuple[bool, str]:
        del client_ip
        return True, ""

    def allow_snapshot_read(self, client_ip: str) -> tuple[bool, str]:
        del client_ip
        if not self.allow_read:
            return False, self.read_reason
        return True, ""


def _request(
    headers: dict[str, str] | None = None,
    client: tuple[str, int] | None = None,
) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "headers": [
            (name.lower().encode("ascii"), value.encode("ascii"))
            for name, value in (headers or {}).items()
        ],
        "query_string": b"",
        "scheme": "http",
        "http_version": "1.1",
        "server": ("testserver", 80),
        "client": client,
    }
    return Request(scope)


def test_snapshot_html_cache_validates_positive_capacity() -> None:
    try:
        _SnapshotHtmlCache(max_entries=0)
    except ValueError as exc:
        assert "max_entries must be positive" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError for non-positive cache capacity")


def test_snapshot_html_cache_expiration_and_lru_eviction() -> None:
    now = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)
    cache = _SnapshotHtmlCache(max_entries=1)

    cache.set("first", "<html>first</html>", now.replace(hour=13), now=now)
    assert cache.get("first", now=now) == "<html>first</html>"

    cache.set("expired", "<html>expired</html>", now.replace(hour=11), now=now)
    assert cache.get("expired", now=now) is None

    cache.set("second", "<html>second</html>", now.replace(hour=13), now=now)
    assert cache.get("first", now=now) is None
    assert cache.get("second", now=now) == "<html>second</html>"


def test_client_ip_prefers_forwarded_header_then_client_then_unknown() -> None:
    forwarded = _request(
        headers={"x-forwarded-for": "198.51.100.1, 203.0.113.1"},
        client=("127.0.0.1", 1234),
    )
    assert _client_ip(forwarded) == "198.51.100.1"

    from_client = _request(client=("203.0.113.20", 443))
    assert _client_ip(from_client) == "203.0.113.20"

    unknown = _request(client=None)
    assert _client_ip(unknown) == "unknown"


def test_snapshot_middleware_rejects_invalid_content_length(tmp_path: Path) -> None:
    store = SnapshotStore(database_path=tmp_path / "snapshots.db")
    app = create_app(store=store)

    with TestClient(app) as client:
        response = client.post(
            "/api/snapshots",
            content='{"videos":[],"shorts":[]}',
            headers={"content-type": "application/json", "content-length": "invalid"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Content-Length header."}


def test_snapshot_middleware_checks_actual_body_size_when_header_underreports(tmp_path: Path) -> None:
    guard = InMemoryAbuseGuard(
        config=AbuseConfig(
            max_snapshot_body_bytes=64,
            post_requests_per_minute=10,
            read_requests_per_minute=10,
            write_quota_per_day_per_ip=10,
        ),
    )
    store = SnapshotStore(database_path=tmp_path / "snapshots.db")
    app = create_app(store=store, abuse_guard=guard)

    with TestClient(app) as client:
        response = client.post(
            "/api/snapshots",
            content="x" * 128,
            headers={
                "content-type": "application/json",
                "content-length": "1",
            },
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large."}


def test_api_and_page_return_410_when_store_reports_expired() -> None:
    app = create_app(
        store=cast(SnapshotStore, _StoreStub(snapshot=None, expired=True)),
        abuse_guard=cast(InMemoryAbuseGuard, _GuardStub()),
    )

    with TestClient(app) as client:
        api_response = client.get("/api/snapshots/Abcd1234")
        page_response = client.get("/Abcd1234")

    assert api_response.status_code == 410
    assert api_response.json() == {"detail": "Snapshot has expired."}
    assert page_response.status_code == 410
    assert "Snapshot expired" in page_response.text


def test_page_returns_429_when_read_not_allowed() -> None:
    app = create_app(
        store=cast(SnapshotStore, _StoreStub(snapshot=None, expired=False)),
        abuse_guard=cast(
            InMemoryAbuseGuard,
            _GuardStub(allow_read=False, read_reason="blocked"),
        ),
    )

    with TestClient(app) as client:
        response = client.get("/Abcd1234")

    assert response.status_code == 429
    assert "Too Many Requests" in response.text
