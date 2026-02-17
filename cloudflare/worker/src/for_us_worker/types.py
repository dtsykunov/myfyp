from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class PreparedStatement(Protocol):
    def bind(self, *params: object) -> "PreparedStatement":
        ...

    async def run(self) -> object:
        ...

    async def first(self) -> object | None:
        ...


class D1Database(Protocol):
    def prepare(self, query: str) -> PreparedStatement:
        ...


class WorkerEnv(Protocol):
    @property
    def DB(self) -> D1Database:
        ...


class HeadersLike(Protocol):
    def get(self, name: str) -> str | None:
        ...


class RequestLike(Protocol):
    @property
    def method(self) -> str:
        ...

    @property
    def url(self) -> str:
        ...

    @property
    def headers(self) -> HeadersLike:
        ...

    async def text(self) -> str:
        ...


class ResponseLike(Protocol):
    status: int
    body: str
    headers: Mapping[str, str]
