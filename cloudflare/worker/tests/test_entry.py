from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine
from typing import TypeVar, cast

from entry import Default

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
