from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine
import json
from typing import TypeVar, cast

import httpx

from for_us_worker.app import app

from .helpers import FakeEnv


T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:
    return asyncio.run(cast(Coroutine[object, object, T], coro))


async def _request(
    *,
    method: str,
    path: str,
    env: FakeEnv | None,
    json_body: dict[str, object] | None = None,
) -> httpx.Response:
    if env is None:
        if hasattr(app.state, "env"):
            delattr(app.state, "env")
    else:
        app.state.env = env

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://example.com",
    ) as client:
        return await client.request(method, path, json=json_body)


def test_fastapi_routes_create_get_render_and_remove() -> None:
    env = FakeEnv()

    root_response = _run(_request(method="GET", path="/", env=env))
    assert root_response.status_code == 200
    assert "myfyp by" in root_response.text

    privacy_response = _run(_request(method="GET", path="/privacy", env=env))
    assert privacy_response.status_code == 200
    assert "Privacy Notice" in privacy_response.text

    create_response = _run(
        _request(
            method="POST",
            path="/api/snapshots",
            env=env,
            json_body={
                "videos": [{"videoHash": "lzChIIJMpGk", "title": "video title"}],
                "shorts": [{"videoHash": "dQw4w9WgXcQ", "title": "short title"}],
            },
        )
    )
    assert create_response.status_code == 201
    created_payload = create_response.json()
    snapshot_hash = cast(str, created_payload["hash"])
    remove_token = cast(str, created_payload["removeToken"])

    get_response = _run(_request(method="GET", path=f"/api/snapshots/{snapshot_hash}", env=env))
    assert get_response.status_code == 200
    assert get_response.json()["videos"][0]["videoHash"] == "lzChIIJMpGk"

    page_response = _run(_request(method="GET", path=f"/{snapshot_hash}", env=env))
    assert page_response.status_code == 200
    assert "myfyp by" in page_response.text

    remove_response = _run(
        _request(
            method="GET",
            path=f"/api/snapshots/{snapshot_hash}/remove/{remove_token}",
            env=env,
        )
    )
    assert remove_response.status_code == 200
    assert remove_response.json() == {"detail": "Snapshot removed."}


def test_fastapi_routes_icon_not_found_and_remove_validation_paths() -> None:
    env = FakeEnv()

    icon_response = _run(_request(method="GET", path="/favicon.svg", env=env))
    assert icon_response.status_code == 302
    assert icon_response.headers["location"].endswith("/brand/icons/web/favicon.svg")

    not_found_response = _run(_request(method="GET", path="/nope", env=env))
    assert not_found_response.status_code == 404
    assert not_found_response.json() == {"detail": "Not found."}

    nested_not_found_response = _run(_request(method="GET", path="/not/a/route", env=env))
    assert nested_not_found_response.status_code == 404
    assert nested_not_found_response.json() == {"detail": "Not found."}

    invalid_hash_remove = _run(
        _request(
            method="GET",
            path=f"/api/snapshots/bad/remove/{'B' * 32}",
            env=env,
        )
    )
    assert invalid_hash_remove.status_code == 404
    assert invalid_hash_remove.json() == {"detail": "Snapshot not found."}

    invalid_token_remove = _run(
        _request(
            method="GET",
            path="/api/snapshots/Abcd1234/remove/bad-token",
            env=env,
        )
    )
    assert invalid_token_remove.status_code == 403
    assert invalid_token_remove.json() == {"detail": "Invalid remove token."}


def test_fastapi_env_bound_routes_return_500_without_worker_env() -> None:
    response = _run(_request(method="POST", path="/api/snapshots", env=None, json_body={"videos": [], "shorts": []}))
    assert response.status_code == 500
    body = json.loads(response.text)
    assert body["detail"] == "Internal server error: Worker environment is unavailable."
