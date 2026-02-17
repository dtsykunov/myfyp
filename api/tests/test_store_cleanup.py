from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from for_us_api.models import CreateSnapshotRequest
from for_us_api.store import SnapshotStore


def _count_rows(database_path: Path) -> int:
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute("SELECT COUNT(*) FROM snapshots")
        row = cursor.fetchone()
    return int(row[0]) if row is not None else 0


def test_initialize_deletes_expired_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    store = SnapshotStore(database_path=database_path)
    store.initialize()
    store.create_snapshot(
        CreateSnapshotRequest(videos=["lzChIIJMpGk"], shorts=[]),
        now=datetime.now(timezone.utc) - timedelta(days=8),
    )

    assert _count_rows(database_path) == 1

    store.initialize()

    assert _count_rows(database_path) == 0

