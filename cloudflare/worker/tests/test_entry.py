from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine
from typing import TypeVar, cast

import entry
from entry import Default
import pytest

from .helpers import FakeEnv, FakeRequest


T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:
    return asyncio.run(cast(Coroutine[object, object, T], coro))


def test_default_entrypoint_fetch_and_scheduled() -> None:
    worker = Default()
    worker.env = FakeEnv()

    fetch_response = _run(worker.fetch(FakeRequest(method="GET", url="https://example.com/health")))
    assert fetch_response.status == 200
    assert fetch_response.body == '{"status": "ok"}'

    _run(worker.scheduled(controller=None, env=worker.env, ctx=None))


def test_default_entrypoint_uses_workers_asgi_fetch_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeASGI:
        called: bool = False

        async def fetch(self, app_obj: object, request: object, env: object) -> object:
            del app_obj, request, env
            self.called = True
            return type("Response", (), {"status": 204, "body": "", "headers": {}})()

    fake_asgi = _FakeASGI()
    monkeypatch.setattr(entry, "workers_asgi", fake_asgi)

    worker = Default()
    worker.env = FakeEnv()

    fetch_response = _run(worker.fetch(FakeRequest(method="GET", url="https://example.com/health")))
    assert fetch_response.status == 204
    assert fake_asgi.called is True
