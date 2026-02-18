from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine
import json
from typing import TypeVar, cast

from for_us_worker.app import handle_fetch

from .helpers import FakeEnv, FakeRequest


T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:
    return asyncio.run(cast(Coroutine[object, object, T], coro))


def test_health_route() -> None:
    response = _run(handle_fetch(FakeRequest(method="GET", url="https://example.com/health"), FakeEnv()))
    assert response.status == 200
    assert response.body == '{"status": "ok"}'


def test_root_route_renders_installation_page() -> None:
    response = _run(handle_fetch(FakeRequest(method="GET", url="https://example.com/"), FakeEnv()))
    assert response.status == 200
    assert "myfyp by" in response.body
    assert "Install and Use" in response.body
    assert 'href="/"' in response.body
    assert "https://myfyp.link/myfyp.user.js" in response.body
    assert 'href="/privacy"' in response.body


def test_privacy_route_renders_privacy_page() -> None:
    response = _run(handle_fetch(FakeRequest(method="GET", url="https://example.com/privacy"), FakeEnv()))
    assert response.status == 200
    assert "Privacy Notice" in response.body
    assert 'href="/"' in response.body
    assert "Snapshots are automatically deleted after 7 days." in response.body
    assert 'href="/privacy"' in response.body


def test_userscript_route_redirects_to_canonical_script() -> None:
    response = _run(
        handle_fetch(
            FakeRequest(method="GET", url="https://example.com/myfyp.user.js"),
            FakeEnv(),
        )
    )
    assert response.status == 302
    assert response.headers["location"].endswith("/extension/userscript/myfyp.user.js")
    assert response.headers["cache-control"] == "no-cache"


def test_create_and_get_snapshot_routes() -> None:
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
                body=json.dumps(
                    {
                        "videos": [{"videoHash": "lzChIIJMpGk", "title": "video title"}],
                        "shorts": [{"videoHash": "dQw4w9WgXcQ", "title": "short title"}],
                    }
                ),
            ),
            env,
        )
    )
    assert create_response.status == 201
    created = json.loads(create_response.body)
    snapshot_hash = created["hash"]
    remove_token = created["removeToken"]
    assert created["url"].endswith(f"/{snapshot_hash}")
    assert created["removeUrl"].endswith(
        f"/api/snapshots/{snapshot_hash}/remove/{remove_token}"
    )

    get_response = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/api/snapshots/{snapshot_hash}",
                headers={"cf-connecting-ip": "198.51.100.10"},
            ),
            env,
        )
    )
    assert get_response.status == 200
    payload = json.loads(get_response.body)
    assert payload["videos"][0]["videoHash"] == "lzChIIJMpGk"

    remove_response = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/api/snapshots/{snapshot_hash}/remove/{remove_token}",
            ),
            env,
        )
    )
    assert remove_response.status == 200
    assert json.loads(remove_response.body) == {"detail": "Snapshot removed."}

    deleted_get = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/api/snapshots/{snapshot_hash}",
                headers={"cf-connecting-ip": "198.51.100.10"},
            ),
            env,
        )
    )
    assert deleted_get.status == 404


def test_render_hash_route() -> None:
    env = FakeEnv()
    create_response = _run(
        handle_fetch(
            FakeRequest(
                method="POST",
                url="https://example.com/api/snapshots",
                headers={
                    "content-type": "application/json",
                    "cf-connecting-ip": "198.51.100.20",
                },
                body=json.dumps(
                    {
                        "videos": [{"videoHash": "lzChIIJMpGk", "title": "video title"}],
                        "shorts": [],
                    }
                ),
            ),
            env,
        )
    )
    snapshot_hash = json.loads(create_response.body)["hash"]

    page_response = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/{snapshot_hash}",
                headers={"cf-connecting-ip": "198.51.100.20"},
            ),
            env,
        )
    )
    assert page_response.status == 200
    assert "myfyp by" in page_response.body


def test_create_rate_limit() -> None:
    env = FakeEnv()
    for _ in range(10):
        response = _run(
            handle_fetch(
                FakeRequest(
                    method="POST",
                    url="https://example.com/api/snapshots",
                    headers={
                        "content-type": "application/json",
                        "cf-connecting-ip": "198.51.100.30",
                    },
                    body=json.dumps(
                        {
                            "videos": [{"videoHash": "lzChIIJMpGk", "title": "video title"}],
                            "shorts": [],
                        }
                    ),
                ),
                env,
            )
        )
        assert response.status == 201

    blocked = _run(
        handle_fetch(
            FakeRequest(
                method="POST",
                url="https://example.com/api/snapshots",
                headers={
                    "content-type": "application/json",
                    "cf-connecting-ip": "198.51.100.30",
                },
                body=json.dumps(
                    {
                        "videos": [{"videoHash": "lzChIIJMpGk", "title": "video title"}],
                        "shorts": [],
                    }
                ),
            ),
            env,
        )
    )
    assert blocked.status == 429


def test_remove_snapshot_endpoint_rejects_invalid_token() -> None:
    env = FakeEnv()
    create_response = _run(
        handle_fetch(
            FakeRequest(
                method="POST",
                url="https://example.com/api/snapshots",
                headers={
                    "content-type": "application/json",
                    "cf-connecting-ip": "198.51.100.40",
                },
                body=json.dumps(
                    {
                        "videos": [{"videoHash": "lzChIIJMpGk", "title": "video title"}],
                        "shorts": [],
                    }
                ),
            ),
            env,
        )
    )
    snapshot_hash = json.loads(create_response.body)["hash"]

    invalid_response = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url=f"https://example.com/api/snapshots/{snapshot_hash}/remove/{'B' * 32}",
            ),
            env,
        )
    )
    assert invalid_response.status == 403
    assert json.loads(invalid_response.body) == {"detail": "Invalid remove token."}
