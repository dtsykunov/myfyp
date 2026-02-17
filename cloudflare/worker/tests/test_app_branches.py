# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine
from datetime import datetime, timedelta, timezone
import json
from typing import TypeVar, cast

import pytest

from for_us_worker import app
from for_us_worker.app import handle_fetch, handle_scheduled

from .helpers import FakeEnv, FakeRequest


T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:
    return asyncio.run(cast(Coroutine[object, object, T], coro))


def _valid_payload() -> str:
    return json.dumps(
        {
            "videos": [{"videoHash": "lzChIIJMpGk", "title": "video title"}],
            "shorts": [{"videoHash": "dQw4w9WgXcQ", "title": "short title"}],
        }
    )


def test_handle_fetch_not_found_and_invalid_hash_paths() -> None:
    env = FakeEnv()

    not_found = _run(handle_fetch(FakeRequest(method="GET", url="https://example.com/nope"), env))
    assert not_found.status == 404

    invalid_hash = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url="https://example.com/api/snapshots/bad",
                headers={"cf-connecting-ip": "198.51.100.1"},
            ),
            env,
        )
    )
    assert invalid_hash.status == 404


def test_handle_fetch_returns_422_for_validation_error_and_400_for_value_error() -> None:
    env = FakeEnv()

    invalid_payload = _run(
        handle_fetch(
            FakeRequest(
                method="POST",
                url="https://example.com/api/snapshots",
                headers={
                    "content-type": "application/json",
                    "cf-connecting-ip": "198.51.100.2",
                },
                body='{"videos":[{"videoHash":"bad","title":"x"}],"shorts":[]}',
            ),
            env,
        )
    )
    assert invalid_payload.status == 422

    invalid_length = _run(
        handle_fetch(
            FakeRequest(
                method="POST",
                url="https://example.com/api/snapshots",
                headers={
                    "content-type": "application/json",
                    "cf-connecting-ip": "198.51.100.3",
                    "content-length": "NaN",
                },
                body=_valid_payload(),
            ),
            env,
        )
    )
    assert invalid_length.status == 400
    assert json.loads(invalid_length.body)["detail"] == "Invalid Content-Length header."


def test_handle_fetch_returns_500_for_unhandled_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    env = FakeEnv()

    async def _boom(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("boom")

    monkeypatch.setattr(app, "allow_snapshot_create", _boom)
    response = _run(
        handle_fetch(
            FakeRequest(
                method="POST",
                url="https://example.com/api/snapshots",
                headers={"cf-connecting-ip": "198.51.100.4"},
                body=_valid_payload(),
            ),
            env,
        )
    )
    assert response.status == 500


def test_get_and_render_snapshot_branches_for_304_404_410_429(monkeypatch: pytest.MonkeyPatch) -> None:
    env = FakeEnv()

    create_response = _run(
        handle_fetch(
            FakeRequest(
                method="POST",
                url="https://example.com/api/snapshots",
                headers={
                    "content-type": "application/json",
                    "cf-connecting-ip": "198.51.100.10",
                },
                body=_valid_payload(),
            ),
            env,
        )
    )
    snapshot_hash = json.loads(create_response.body)["hash"]

    first_get = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/api/snapshots/{snapshot_hash}",
                headers={"cf-connecting-ip": "198.51.100.11"},
            ),
            env,
        )
    )
    assert first_get.status == 200
    etag = first_get.headers["ETag"]

    cached_get = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/api/snapshots/{snapshot_hash}",
                headers={
                    "cf-connecting-ip": "198.51.100.11",
                    "if-none-match": etag,
                },
            ),
            env,
        )
    )
    assert cached_get.status == 304

    missing_get = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url="https://example.com/api/snapshots/Abcd12345678",
                headers={"cf-connecting-ip": "198.51.100.12"},
            ),
            env,
        )
    )
    assert missing_get.status == 404

    expires_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    env.DB.snapshots["ExpiredHash1"] = {
        "hash": "ExpiredHash1",
        "created_at": "2026-02-01T00:00:00+00:00",
        "expires_at": expires_at,
        "payload_json": '{"videos":[],"shorts":[]}',
    }

    expired_get = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url="https://example.com/api/snapshots/ExpiredHash1",
                headers={"cf-connecting-ip": "198.51.100.13"},
            ),
            env,
        )
    )
    assert expired_get.status == 410

    first_page = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/{snapshot_hash}",
                headers={"cf-connecting-ip": "198.51.100.14"},
            ),
            env,
        )
    )
    assert first_page.status == 200
    page_etag = first_page.headers["ETag"]

    cached_page = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/{snapshot_hash}",
                headers={
                    "cf-connecting-ip": "198.51.100.14",
                    "if-none-match": page_etag,
                },
            ),
            env,
        )
    )
    assert cached_page.status == 304

    missing_page = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url="https://example.com/Abcd12345679",
                headers={"cf-connecting-ip": "198.51.100.15"},
            ),
            env,
        )
    )
    assert missing_page.status == 404

    env.DB.snapshots["ExpiredHash2"] = {
        "hash": "ExpiredHash2",
        "created_at": "2026-02-01T00:00:00+00:00",
        "expires_at": expires_at,
        "payload_json": '{"videos":[],"shorts":[]}',
    }
    expired_page = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url="https://example.com/ExpiredHash2",
                headers={"cf-connecting-ip": "198.51.100.16"},
            ),
            env,
        )
    )
    assert expired_page.status == 410

    async def _deny_read(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return type("Decision", (), {"allowed": False, "reason": "denied"})()

    monkeypatch.setattr(app, "allow_snapshot_read", _deny_read)
    throttled_api = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/api/snapshots/{snapshot_hash}",
                headers={"cf-connecting-ip": "198.51.100.17"},
            ),
            env,
        )
    )
    assert throttled_api.status == 429

    throttled = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/{snapshot_hash}",
                headers={"cf-connecting-ip": "198.51.100.17"},
            ),
            env,
        )
    )
    assert throttled.status == 429


def test_read_body_with_limit_errors() -> None:
    invalid_header = FakeRequest(
        method="POST",
        url="https://example.com/api/snapshots",
        headers={"content-length": "not-a-number"},
        body="{}",
    )
    with pytest.raises(ValueError):
        _run(app._read_body_with_limit(invalid_header, 64))

    oversized_header = FakeRequest(
        method="POST",
        url="https://example.com/api/snapshots",
        headers={"content-length": "65"},
        body="{}",
    )
    with pytest.raises(ValueError):
        _run(app._read_body_with_limit(oversized_header, 64))

    oversized_body = FakeRequest(
        method="POST",
        url="https://example.com/api/snapshots",
        headers={"content-length": "1"},
        body="x" * 65,
    )
    with pytest.raises(ValueError):
        _run(app._read_body_with_limit(oversized_body, 64))


def test_handle_scheduled_cleans_expired_snapshot_and_abuse_state() -> None:
    env = FakeEnv()
    env.DB.snapshots["oldhash123456"] = {
        "hash": "oldhash123456",
        "created_at": "2026-02-01T00:00:00+00:00",
        "expires_at": "2026-02-02T00:00:00+00:00",
        "payload_json": '{"videos":[],"shorts":[]}',
    }
    env.DB.abuse_rate_limit[("ip", "read", "2026-02-01T00:00:00+00:00")] = 1
    env.DB.abuse_write_daily[("ip", "2026-02-01")] = 1

    _run(handle_scheduled(env))

    assert "oldhash123456" not in env.DB.snapshots
    assert env.DB.abuse_rate_limit == {}
    assert env.DB.abuse_write_daily == {}


def test_client_ip_resolution() -> None:
    cf_ip_request = FakeRequest(
        method="GET",
        url="https://example.com/health",
        headers={"cf-connecting-ip": "198.51.100.20"},
    )
    assert app._client_ip(cf_ip_request) == "198.51.100.20"

    forwarded = FakeRequest(
        method="GET",
        url="https://example.com/health",
        headers={"x-forwarded-for": "198.51.100.21, 203.0.113.5"},
    )
    assert app._client_ip(forwarded) == "198.51.100.21"

    unknown = FakeRequest(method="GET", url="https://example.com/health")
    assert app._client_ip(unknown) == "unknown"


def test_abuse_limiting_flag_parsing() -> None:
    env = FakeEnv()

    assert app._is_abuse_limiting_enabled(env) is True

    env.ABUSE_LIMITING_ENABLED = "0"
    assert app._is_abuse_limiting_enabled(env) is False

    env.ABUSE_LIMITING_ENABLED = "false"
    assert app._is_abuse_limiting_enabled(env) is False

    env.ABUSE_LIMITING_ENABLED = "off"
    assert app._is_abuse_limiting_enabled(env) is False

    env.ABUSE_LIMITING_ENABLED = "1"
    assert app._is_abuse_limiting_enabled(env) is True


def test_create_snapshot_bypasses_abuse_limiter_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    env = FakeEnv()
    env.ABUSE_LIMITING_ENABLED = "0"

    async def _deny_create(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return type("Decision", (), {"allowed": False, "reason": "denied"})()

    monkeypatch.setattr(app, "allow_snapshot_create", _deny_create)

    response = _run(
        handle_fetch(
            FakeRequest(
                method="POST",
                url="https://example.com/api/snapshots",
                headers={
                    "content-type": "application/json",
                    "cf-connecting-ip": "198.51.100.22",
                },
                body=_valid_payload(),
            ),
            env,
        )
    )
    assert response.status == 201
