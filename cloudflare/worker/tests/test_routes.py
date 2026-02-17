from __future__ import annotations

import asyncio
import json

from for_us_worker.app import handle_fetch

from tests.helpers import FakeEnv, FakeRequest


def _run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


def test_health_route() -> None:
    response = _run(handle_fetch(FakeRequest(method="GET", url="https://example.com/health"), FakeEnv()))
    assert response.status == 200
    assert response.body == '{"status": "ok"}'


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
    assert "For Us Page by" in page_response.body


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
