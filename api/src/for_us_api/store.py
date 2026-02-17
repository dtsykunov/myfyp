from collections import OrderedDict
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import sqlite3
import string
from threading import Lock

from for_us_api.models import CreateSnapshotRequest, CreateSnapshotResponse
from for_us_api.models import StoredSnapshot

DATABASE_PATH_ENV_VAR = "FOR_US_DB_PATH"
DEFAULT_DATABASE_PATH = "data/for-us.db"
DEFAULT_RETENTION_DAYS = 7
DEFAULT_CLEANUP_INTERVAL_WRITES = 100
DEFAULT_MAX_CACHED_SNAPSHOTS = 2000
HASH_ALPHABET = string.ascii_letters + string.digits
HASH_LENGTH = 12
MAX_HASH_GENERATION_ATTEMPTS = 5


def _empty_snapshot_cache() -> OrderedDict[str, StoredSnapshot]:
    return OrderedDict()


@dataclass
class SnapshotStore:
    database_path: Path
    retention_days: int = DEFAULT_RETENTION_DAYS
    cleanup_interval_writes: int = DEFAULT_CLEANUP_INTERVAL_WRITES
    max_cached_snapshots: int = DEFAULT_MAX_CACHED_SNAPSHOTS
    _writes_since_cleanup: int = field(default=0, init=False, repr=False)
    _cleanup_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _snapshot_cache_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _snapshot_cache: OrderedDict[str, StoredSnapshot] = field(
        default_factory=_empty_snapshot_cache, init=False, repr=False
    )

    @classmethod
    def from_environment(cls) -> "SnapshotStore":
        configured_path = os.getenv(DATABASE_PATH_ENV_VAR, DEFAULT_DATABASE_PATH)
        return cls(database_path=Path(configured_path))

    def __post_init__(self) -> None:
        if self.retention_days <= 0:
            raise ValueError("retention_days must be positive.")
        if self.cleanup_interval_writes <= 0:
            raise ValueError("cleanup_interval_writes must be positive.")
        if self.max_cached_snapshots <= 0:
            raise ValueError("max_cached_snapshots must be positive.")

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._configure_database(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    hash TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_snapshots_expires_at
                ON snapshots (expires_at)
                """
            )
        self.delete_expired()

    def create_snapshot(
        self, payload: CreateSnapshotRequest, now: datetime | None = None
    ) -> CreateSnapshotResponse:
        created_at = now or datetime.now(timezone.utc)
        expires_at = created_at + timedelta(days=self.retention_days)
        payload_json = json.dumps(
            payload.model_dump(by_alias=True, mode="json", exclude_none=True),
            separators=(",", ":"),
            sort_keys=True,
        )

        for _ in range(MAX_HASH_GENERATION_ATTEMPTS):
            snapshot_hash = self._generate_hash()
            if self._try_insert_snapshot(snapshot_hash, created_at, expires_at, payload_json):
                self._cache_snapshot(
                    StoredSnapshot(
                        hash=snapshot_hash,
                        created_at=created_at,
                        expires_at=expires_at,
                        payload=payload,
                    )
                )
                self._register_write_and_cleanup_if_needed()
                return CreateSnapshotResponse(hash=snapshot_hash, expiresAt=expires_at)

        raise RuntimeError("Unable to persist snapshot due to hash collisions.")

    def _try_insert_snapshot(
        self,
        snapshot_hash: str,
        created_at: datetime,
        expires_at: datetime,
        payload_json: str,
    ) -> bool:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO snapshots (hash, created_at, expires_at, payload_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        snapshot_hash,
                        created_at.isoformat(),
                        expires_at.isoformat(),
                        payload_json,
                    ),
                )
                connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _generate_hash(self) -> str:
        return "".join(secrets.choice(HASH_ALPHABET) for _ in range(HASH_LENGTH))

    def _configure_database(self, connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")

    def delete_expired(self, now: datetime | None = None) -> int:
        effective_now = now or datetime.now(timezone.utc)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM snapshots
                WHERE expires_at <= ?
                """,
                (effective_now.isoformat(),),
            )
            deleted_rows = int(cursor.rowcount)
            connection.commit()
        self._prune_snapshot_cache(effective_now)
        return deleted_rows

    def get_snapshot(
        self, snapshot_hash: str, now: datetime | None = None
    ) -> tuple[StoredSnapshot | None, bool]:
        effective_now = now or datetime.now(timezone.utc)

        cached_snapshot = self._get_cached_snapshot(snapshot_hash, effective_now)
        if cached_snapshot is not None:
            return cached_snapshot, False

        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT hash, created_at, expires_at, payload_json
                FROM snapshots
                WHERE hash = ?
                """,
                (snapshot_hash,),
            )
            row = cursor.fetchone()

        if row is None:
            return None, False

        created_at = datetime.fromisoformat(str(row[1]))
        expires_at = datetime.fromisoformat(str(row[2]))
        payload = CreateSnapshotRequest.model_validate_json(str(row[3]))
        snapshot = StoredSnapshot(
            hash=str(row[0]),
            created_at=created_at,
            expires_at=expires_at,
            payload=payload,
        )

        is_expired = snapshot.expires_at <= effective_now
        if is_expired:
            self._evict_snapshot_cache(snapshot_hash)
            self._delete_snapshot_by_hash(snapshot_hash)
            return None, True

        self._cache_snapshot(snapshot)
        return snapshot, False

    def _register_write_and_cleanup_if_needed(self) -> None:
        should_cleanup = False
        with self._cleanup_lock:
            self._writes_since_cleanup += 1
            if self._writes_since_cleanup >= self.cleanup_interval_writes:
                self._writes_since_cleanup = 0
                should_cleanup = True

        if should_cleanup:
            self.delete_expired()

    def _get_cached_snapshot(
        self,
        snapshot_hash: str,
        now: datetime,
    ) -> StoredSnapshot | None:
        effective_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        with self._snapshot_cache_lock:
            cached = self._snapshot_cache.get(snapshot_hash)
            if cached is None:
                return None
            if cached.expires_at <= effective_now:
                self._snapshot_cache.pop(snapshot_hash, None)
                return None
            self._snapshot_cache.move_to_end(snapshot_hash)
            return cached

    def _cache_snapshot(self, snapshot: StoredSnapshot) -> None:
        with self._snapshot_cache_lock:
            self._snapshot_cache[snapshot.hash] = snapshot
            self._snapshot_cache.move_to_end(snapshot.hash)
            while len(self._snapshot_cache) > self.max_cached_snapshots:
                self._snapshot_cache.popitem(last=False)

    def _evict_snapshot_cache(self, snapshot_hash: str) -> None:
        with self._snapshot_cache_lock:
            self._snapshot_cache.pop(snapshot_hash, None)

    def _prune_snapshot_cache(self, now: datetime) -> None:
        effective_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        with self._snapshot_cache_lock:
            expired_hashes = [
                snapshot_hash
                for snapshot_hash, snapshot in self._snapshot_cache.items()
                if snapshot.expires_at <= effective_now
            ]
            for snapshot_hash in expired_hashes:
                self._snapshot_cache.pop(snapshot_hash, None)

    def _delete_snapshot_by_hash(self, snapshot_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM snapshots
                WHERE hash = ?
                """,
                (snapshot_hash,),
            )
            connection.commit()
