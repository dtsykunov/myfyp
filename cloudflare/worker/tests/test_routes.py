from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine
import json
from typing import TypeVar, cast

from for_us_worker.app import handle_fetch

from .helpers import FakeEnv, FakeRequest

_ICON_CDN_BASE_URL = (
    "https://media.githubusercontent.com/media/"
    "dtsykunov/myfyp/refs/heads/master/brand/icons/web"
)


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
    assert response.headers["Cache-Control"].startswith("public, max-age=3600")
    assert response.headers["ETag"] == '"static-home"'
    assert "myfyp by" in response.body
    assert 'myfyp means "my for you page"' in response.body
    assert "share recommendation page" in response.body.lower()
    assert "Install and Use" in response.body
    assert f'href="{_ICON_CDN_BASE_URL}/favicon.svg"' in response.body
    assert f'<img src="{_ICON_CDN_BASE_URL}/favicon.svg" alt="">' in response.body
    assert 'href="/"' in response.body
    assert "https://raw.githubusercontent.com/dtsykunov/myfyp/master/extension/userscript/myfyp.user.js" in response.body
    assert "https://addons.mozilla.org/en-US/firefox/addon/myfyp/" in response.body
    assert 'href="https://chromewebstore.google.com/detail/knjonkdgfkiogiajfcndhfndbajckgei"' in response.body
    assert 'href="https://www.tampermonkey.net/"' in response.body
    assert 'href="/privacy"' in response.body


def test_privacy_route_renders_privacy_page() -> None:
    response = _run(handle_fetch(FakeRequest(method="GET", url="https://example.com/privacy"), FakeEnv()))
    assert response.status == 200
    assert response.headers["Cache-Control"].startswith("public, max-age=3600")
    assert response.headers["ETag"] == '"static-privacy"'
    assert "Privacy Notice" in response.body
    assert f'href="{_ICON_CDN_BASE_URL}/favicon.svg"' in response.body
    assert f'<img src="{_ICON_CDN_BASE_URL}/favicon.svg" alt="">' in response.body
    assert 'href="/"' in response.body
    assert "Snapshots are automatically deleted after 7 days." in response.body
    assert 'href="/privacy"' in response.body


def test_static_pages_return_304_when_etag_matches() -> None:
    root_first = _run(handle_fetch(FakeRequest(method="GET", url="https://example.com/"), FakeEnv()))
    root_second = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url="https://example.com/",
                headers={"if-none-match": root_first.headers["ETag"]},
            ),
            FakeEnv(),
        )
    )
    assert root_second.status == 304
    assert root_second.body == ""
    assert root_second.headers["ETag"] == root_first.headers["ETag"]

    privacy_first = _run(
        handle_fetch(FakeRequest(method="GET", url="https://example.com/privacy"), FakeEnv())
    )
    privacy_second = _run(
        handle_fetch(
            FakeRequest(
                method="GET",
                url="https://example.com/privacy",
                headers={"if-none-match": privacy_first.headers["ETag"]},
            ),
            FakeEnv(),
        )
    )
    assert privacy_second.status == 304
    assert privacy_second.body == ""
    assert privacy_second.headers["ETag"] == privacy_first.headers["ETag"]


def test_userscript_route_returns_not_found() -> None:
    response = _run(
        handle_fetch(
            FakeRequest(method="GET", url="https://example.com/myfyp.user.js"),
            FakeEnv(),
        )
    )
    assert response.status == 404


def test_icon_routes_redirect_to_canonical_brand_assets() -> None:
    icon_paths = [
        "/favicon.ico",
        "/favicon.svg",
        "/favicon-16x16.png",
        "/favicon-32x32.png",
        "/favicon-48x48.png",
        "/apple-touch-icon.png",
        "/android-chrome-192x192.png",
        "/android-chrome-512x512.png",
    ]
    for icon_path in icon_paths:
        response = _run(handle_fetch(FakeRequest(method="GET", url=f"https://example.com{icon_path}"), FakeEnv()))
        assert response.status == 302
        assert response.headers["location"].startswith("https://media.githubusercontent.com/media/")
        assert response.headers["location"].endswith(f"/brand/icons/web{icon_path}")
        assert response.headers["cache-control"] == "public, max-age=86400, immutable"


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
    assert "create;dur=" in create_response.headers["Server-Timing"]
    assert "parse;dur=" in create_response.headers["Server-Timing"]
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
    assert "api;dur=" in get_response.headers["Server-Timing"]
    assert "lookup_payload;dur=" in get_response.headers["Server-Timing"]
    assert get_response.headers["Cache-Control"] == "public, no-cache, max-age=0, must-revalidate"
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
    assert "html;dur=" in page_response.headers["Server-Timing"]
    assert "lookup_snapshot;dur=" in page_response.headers["Server-Timing"]
    assert page_response.headers["Cache-Control"] == "public, no-cache, max-age=0, must-revalidate"
    assert "myfyp by" in page_response.body
    assert f'href="{_ICON_CDN_BASE_URL}/favicon.svg"' in page_response.body
    assert f'<img src="{_ICON_CDN_BASE_URL}/favicon.svg" alt="">' in page_response.body
    assert 'content="noindex,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"' in page_response.body


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
