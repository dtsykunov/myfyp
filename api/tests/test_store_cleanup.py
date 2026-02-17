from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from for_us_api.models import CreateSnapshotRequest, RecommendationItem
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
        CreateSnapshotRequest(
            videos=[RecommendationItem(videoHash="lzChIIJMpGk", title="Sample video")], shorts=[]
        ),
        now=datetime.now(timezone.utc) - timedelta(days=8),
    )

    assert _count_rows(database_path) == 1

    store.initialize()

    assert _count_rows(database_path) == 0


def test_get_snapshot_deletes_expired_row_on_access(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    store = SnapshotStore(database_path=database_path)
    store.initialize()
    expired_snapshot = store.create_snapshot(
        CreateSnapshotRequest(
            videos=[RecommendationItem(videoHash="lzChIIJMpGk", title="Sample video")], shorts=[]
        ),
        now=datetime.now(timezone.utc) - timedelta(days=8),
    )

    snapshot, is_expired = store.get_snapshot(expired_snapshot.hash)

    assert snapshot is None
    assert is_expired is True
    assert _count_rows(database_path) == 0
