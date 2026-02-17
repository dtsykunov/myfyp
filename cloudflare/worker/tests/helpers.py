from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


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
    snapshots: dict[str, dict[str, str]] = field(default_factory=dict)

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
        raise AssertionError(f"Unsupported run query: {query}")

    def first_query(self, query: str, params: tuple[object, ...]) -> Mapping[str, object] | None:
        normalized = " ".join(query.lower().split())
        if "select hash, created_at, expires_at, payload_json from snapshots where hash" in normalized:
            return self.snapshots.get(_as_str(params[0]))
        raise AssertionError(f"Unsupported first query: {query}")


@dataclass
class FakeEnv:
    DB: FakeD1Database = field(default_factory=FakeD1Database)


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
