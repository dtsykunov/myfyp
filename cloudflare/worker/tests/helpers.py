from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


def _empty_snapshots() -> dict[str, dict[str, str]]:
    return {}


def _empty_abuse_rate_limit() -> dict[tuple[str, str, str], int]:
    return {}


def _empty_abuse_write_daily() -> dict[tuple[str, str], int]:
    return {}


@dataclass
class FakePreparedStatement:
    db: "FakeD1Database"
    query: str
    params: tuple[object, ...] = ()

    def bind(self, *params: object) -> "FakePreparedStatement":
        self.params = params
        return self

    async def run(self) -> Mapping[str, object]:
        changes = self.db.run_query(self.query, self.params)
        return {"meta": {"changes": changes}}

    async def first(self) -> Mapping[str, object] | None:
        return self.db.first_query(self.query, self.params)


@dataclass
class FakeD1Database:
    snapshots: dict[str, dict[str, str]] = field(default_factory=_empty_snapshots)
    abuse_rate_limit: dict[tuple[str, str, str], int] = field(default_factory=_empty_abuse_rate_limit)
    abuse_write_daily: dict[tuple[str, str], int] = field(default_factory=_empty_abuse_write_daily)

    def prepare(self, query: str) -> FakePreparedStatement:
        return FakePreparedStatement(self, query)

    def run_query(self, query: str, params: tuple[object, ...]) -> int:
        normalized = " ".join(query.lower().split())
        if "insert or ignore into snapshots" in normalized:
            snapshot_hash = _as_str(params[0])
            if snapshot_hash in self.snapshots:
                return 0
            self.snapshots[snapshot_hash] = {
                "hash": snapshot_hash,
                "created_at": _as_str(params[1]),
                "expires_at": _as_str(params[2]),
                "payload_json": _as_str(params[3]),
            }
            return 1
        if "delete from snapshots where hash" in normalized:
            snapshot_hash = _as_str(params[0])
            return 1 if self.snapshots.pop(snapshot_hash, None) is not None else 0
        if "delete from snapshots where expires_at" in normalized:
            cutoff = _as_str(params[0])
            deleted = 0
            for snapshot_hash in list(self.snapshots):
                if self.snapshots[snapshot_hash]["expires_at"] <= cutoff:
                    self.snapshots.pop(snapshot_hash)
                    deleted += 1
            return deleted
        if "insert into abuse_ip_rate_limit" in normalized:
            ip_hash = _as_str(params[0])
            action = _as_str(params[1])
            window_start = _as_str(params[2])
            limit = _as_int(params[3])
            key = (ip_hash, action, window_start)
            count = self.abuse_rate_limit.get(key, 0)
            if count >= limit:
                return 0
            self.abuse_rate_limit[key] = count + 1
            return 1
        if "insert into abuse_ip_write_daily" in normalized:
            ip_hash = _as_str(params[0])
            quota_date = _as_str(params[1])
            limit = _as_int(params[2])
            key = (ip_hash, quota_date)
            count = self.abuse_write_daily.get(key, 0)
            if count >= limit:
                return 0
            self.abuse_write_daily[key] = count + 1
            return 1
        if "delete from abuse_ip_rate_limit" in normalized:
            cutoff = _as_str(params[0])
            deleted = 0
            for key in list(self.abuse_rate_limit):
                if key[2] < cutoff:
                    self.abuse_rate_limit.pop(key)
                    deleted += 1
            return deleted
        if "delete from abuse_ip_write_daily" in normalized:
            cutoff = _as_str(params[0])
            deleted = 0
            for key in list(self.abuse_write_daily):
                if key[1] < cutoff:
                    self.abuse_write_daily.pop(key)
                    deleted += 1
            return deleted
        raise AssertionError(f"Unsupported run query: {query}")

    def first_query(self, query: str, params: tuple[object, ...]) -> Mapping[str, object] | None:
        normalized = " ".join(query.lower().split())
        if "select hash, created_at, expires_at, payload_json from snapshots where hash" in normalized:
            return self.snapshots.get(_as_str(params[0]))
        raise AssertionError(f"Unsupported first query: {query}")


@dataclass
class FakeEnv:
    DB: FakeD1Database = field(default_factory=FakeD1Database)
    ABUSE_LIMITING_ENABLED: str = "1"


class FakeHeaders:
    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        self._values = {key.lower(): value for key, value in (values or {}).items()}

    def get(self, name: str) -> str | None:
        return self._values.get(name.lower())


class FakeRequest:
    def __init__(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        body: str = "",
    ) -> None:
        self.method = method
        self.url = url
        self.headers = FakeHeaders(headers)
        self._body = body

    async def text(self) -> str:
        return self._body


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise AssertionError(f"Expected str, got {type(value)!r}")
    return value


def _as_int(value: object) -> int:
    if not isinstance(value, int):
        raise AssertionError(f"Expected int, got {type(value)!r}")
    return value
