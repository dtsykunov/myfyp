from pathlib import Path

from fastapi.testclient import TestClient

from for_us_api.abuse import AbuseConfig, InMemoryAbuseGuard
from for_us_api.app import create_app
from for_us_api.store import SnapshotStore


def _make_client(tmp_path: Path, config: AbuseConfig) -> TestClient:
    database_path = tmp_path / "snapshots.db"
    store = SnapshotStore(database_path=database_path)
    guard = InMemoryAbuseGuard(config=config)
    return TestClient(create_app(store=store, abuse_guard=guard))


def test_snapshot_create_rate_limit_returns_429(tmp_path: Path) -> None:
    config = AbuseConfig(
        max_snapshot_body_bytes=64 * 1024,
        post_requests_per_minute=1,
        read_requests_per_minute=120,
        write_quota_per_day_per_ip=100,
    )
    payload = {"videos": ["lzChIIJMpGk"], "shorts": []}

    with _make_client(tmp_path, config) as client:
        first = client.post("/api/snapshots", json=payload)
        second = client.post("/api/snapshots", json=payload)

    assert first.status_code == 201
    assert second.status_code == 429


def test_snapshot_create_daily_quota_returns_429(tmp_path: Path) -> None:
    config = AbuseConfig(
        max_snapshot_body_bytes=64 * 1024,
        post_requests_per_minute=50,
        read_requests_per_minute=120,
        write_quota_per_day_per_ip=1,
    )
    payload = {"videos": ["lzChIIJMpGk"], "shorts": []}

    with _make_client(tmp_path, config) as client:
        first = client.post("/api/snapshots", json=payload)
        second = client.post("/api/snapshots", json=payload)

    assert first.status_code == 201
    assert second.status_code == 429


def test_snapshot_body_too_large_returns_413(tmp_path: Path) -> None:
    config = AbuseConfig(
        max_snapshot_body_bytes=64,
        post_requests_per_minute=50,
        read_requests_per_minute=120,
        write_quota_per_day_per_ip=100,
    )
    large_payload = {
        "capturedAt": "2026-02-17T11:00:00Z",
        "pageUrl": "https://www.youtube.com/" + ("x" * 500),
        "videos": ["lzChIIJMpGk"],
        "shorts": [],
    }

    with _make_client(tmp_path, config) as client:
        response = client.post("/api/snapshots", json=large_payload)

    assert response.status_code == 413


def test_snapshot_read_rate_limit_returns_429(tmp_path: Path) -> None:
    config = AbuseConfig(
        max_snapshot_body_bytes=64 * 1024,
        post_requests_per_minute=50,
        read_requests_per_minute=1,
        write_quota_per_day_per_ip=100,
    )
    payload = {"videos": ["lzChIIJMpGk"], "shorts": []}

    with _make_client(tmp_path, config) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]
        first = client.get(f"/api/snapshots/{snapshot_hash}")
        second = client.get(f"/api/snapshots/{snapshot_hash}")

    assert first.status_code == 200
    assert second.status_code == 429

