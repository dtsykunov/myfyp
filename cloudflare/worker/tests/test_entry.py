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


def test_default_entrypoint_scheduled_falls_back_to_self_env_when_runtime_env_is_none() -> None:
    worker = Default()
    worker.env = FakeEnv()
    worker.env.DB.snapshots["oldhash123456"] = {
        "hash": "oldhash123456",
        "created_at": "2026-02-01T00:00:00+00:00",
        "expires_at": "2026-02-02T00:00:00+00:00",
        "payload_json": '{"videos":[],"shorts":[]}',
    }

    _run(worker.scheduled(controller=None, env=None, ctx=None))

    assert "oldhash123456" not in worker.env.DB.snapshots
