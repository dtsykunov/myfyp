from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from for_us_api.app import create_app
from for_us_api.models import CreateSnapshotRequest
from for_us_api.store import SnapshotStore


def test_get_snapshot_api_returns_stored_payload(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "capturedAt": "2026-02-17T11:00:00Z",
        "pageUrl": "https://www.youtube.com/",
        "videos": ["lzChIIJMpGk"],
        "shorts": ["dQw4w9WgXcQ"],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]

        get_response = client.get(f"/api/snapshots/{snapshot_hash}")

    assert get_response.status_code == 200
    assert get_response.json() == payload


def test_render_snapshot_page_contains_video_and_short_links(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "videos": ["lzChIIJMpGk"],
        "shorts": ["dQw4w9WgXcQ"],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]

        page_response = client.get(f"/{snapshot_hash}")

    assert page_response.status_code == 200
    assert "<h1>For Us Page</h1>" in page_response.text
    assert "https://www.youtube.com/watch?v=lzChIIJMpGk" in page_response.text
    assert "https://www.youtube.com/shorts/dQw4w9WgXcQ" in page_response.text


def test_get_snapshot_api_returns_404_for_unknown_hash(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        response = client.get("/api/snapshots/unknown123")

    assert response.status_code == 404


def test_expired_snapshot_returns_410_for_api_and_page(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    store = SnapshotStore(database_path=database_path)
    store.initialize()
    expired_snapshot = store.create_snapshot(
        CreateSnapshotRequest(videos=["lzChIIJMpGk"], shorts=[]),
        now=datetime.now(timezone.utc) - timedelta(days=8),
    )

    with TestClient(create_app(store=store)) as client:
        api_response = client.get(f"/api/snapshots/{expired_snapshot.hash}")
        page_response = client.get(f"/{expired_snapshot.hash}")

    assert api_response.status_code == 410
    assert page_response.status_code == 410

