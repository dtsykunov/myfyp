from datetime import datetime
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from for_us_api.app import create_app
from for_us_api.store import SnapshotStore


def _read_snapshot_rows(database_path: Path) -> list[tuple[str, str, str, str]]:
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            SELECT hash, created_at, expires_at, payload_json
            FROM snapshots
            """
        )
        rows = cursor.fetchall()
    return [(str(row[0]), str(row[1]), str(row[2]), str(row[3])) for row in rows]


def test_create_snapshot_persists_payload_and_returns_response(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "capturedAt": "2026-02-17T11:00:00Z",
        "pageUrl": "https://www.youtube.com/",
        "videos": ["lzChIIJMpGk"],
        "shorts": ["dQw4w9WgXcQ"],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        response = client.post("/api/snapshots", json=payload)

    assert response.status_code == 201

    response_body = response.json()
    assert "hash" in response_body
    assert len(response_body["hash"]) == 12
    expires_at = datetime.fromisoformat(response_body["expiresAt"])
    assert expires_at.tzinfo is not None

    rows = _read_snapshot_rows(database_path)
    assert len(rows) == 1
    stored_hash, _created_at, _expires_at, payload_json = rows[0]
    assert stored_hash == response_body["hash"]
    assert json.loads(payload_json) == payload


def test_create_snapshot_rejects_invalid_payload(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "videos": ["invalid-hash"],
        "shorts": [],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        response = client.post("/api/snapshots", json=payload)

    assert response.status_code == 422
    assert _read_snapshot_rows(database_path) == []
