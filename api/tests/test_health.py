from pathlib import Path

from fastapi.testclient import TestClient

from for_us_api.app import create_app
from for_us_api.store import SnapshotStore


def test_health_endpoint_returns_ok(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    client = TestClient(create_app(store=SnapshotStore(database_path=database_path)))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
